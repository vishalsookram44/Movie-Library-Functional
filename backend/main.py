import hashlib
import hmac
import json
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

import jwt
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import distinct
from sqlmodel import Session, delete, func, select

from backend.config import get_settings
from backend.database import create_db_and_tables, get_session
from backend.mailer import email_ready, send_email
from backend.models import DashState, DemoUser, Reading
from backend.security import (create_access_token, decode_access_token,
                              hash_password, verify_password)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="FreshCheck API", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]


class DemoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    biz: str = Field(min_length=1, max_length=120)
    email: EmailStr
    type: str = Field(default="Restaurant", max_length=40)
    msg: str = Field(default="", max_length=1000)


class SetPassword(BaseModel):
    setup_token: str
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


def _profile(u: DemoUser) -> dict:
    return {"authenticated": True, "id": u.id, "name": u.name,
            "business": u.business, "type": u.business_type, "email": u.email,
            "admin": _is_admin(u)}


def _start_session(response: Response, user: DemoUser):
    token = create_access_token({"sub": str(user.id), "purpose": "session"})
    response.set_cookie("access_token", token, httponly=True, samesite="lax",
                        secure=get_settings().env == "production",
                        max_age=60 * 60 * 24)


@app.post("/api/request-demo", status_code=201)
def request_demo(data: DemoRequest, db: SessionDep):
    """Step 1: store the profile. Returns a short-lived token needed for step 2."""
    email = data.email.lower()
    user = db.exec(select(DemoUser).where(DemoUser.email == email)).one_or_none()
    if user and user.password:
        raise HTTPException(400, "An account with this email already exists. Please sign in.")
    if not user:
        user = DemoUser(email=email, name="", business="")
    user.name, user.business = data.name.strip(), data.biz.strip()
    user.business_type, user.message = data.type, data.msg.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id), "purpose": "setup"}, expires_minutes=30)
    return {"setup_token": token, "name": user.name, "business": user.business}


@app.post("/api/set-password")
def set_password(data: SetPassword, request: Request, response: Response, db: SessionDep):
    """Step 2: set the password, sign the user in."""
    try:
        payload = decode_access_token(data.setup_token)
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(400, "Your setup link expired. Please request the demo again.")
    user = db.get(DemoUser, int(payload["sub"])) if payload.get("purpose") == "setup" else None
    if not user or user.password:
        raise HTTPException(400, "This setup link is no longer valid.")
    user.password = hash_password(data.password)
    db.add(user)
    db.commit()
    _start_session(response, user)
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    send_email(  # welcome email; never blocks or breaks sign-up if mail isn't configured
        user.email, "Welcome to FreshCheck",
        f"Hi {user.name},\n\nYour FreshCheck demo account for {user.business} is ready.\n\n"
        f"Open your dashboard: https://{host}/dashboard\n"
        "Sign in with this email address and the password you just created.\n\n"
        "A few things to try:\n"
        "- Click Add sensor and send a simulated reading\n"
        "- Send a temperature outside the safe range to trigger an alert (and an email)\n"
        "- Change a sensor's safe range from its details panel\n\n"
        "Forgot your password? Use the 'Forgot your password?' link in the sign-in popup.\n\n- FreshCheck")
    return _profile(user)


@app.post("/api/login")
def login(data: Login, response: Response, db: SessionDep):
    user = db.exec(select(DemoUser).where(DemoUser.email == data.email.lower())).one_or_none()
    if not user or not user.password or not verify_password(data.password, user.password):
        raise HTTPException(401, "Incorrect email or password.")
    _start_session(response, user)
    return _profile(user)


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


def _current(request: Request, db: SessionDep) -> Optional[DemoUser]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        p = decode_access_token(token)
    except jwt.exceptions.InvalidTokenError:
        return None
    return db.get(DemoUser, int(p["sub"])) if p.get("purpose") == "session" else None


@app.get("/api/me")
def me(user: Annotated[Optional[DemoUser], Depends(_current)]):
    return _profile(user) if user else {"authenticated": False}


class StateIn(BaseModel):
    data: dict


@app.get("/api/state")
def get_state(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    if not user:
        raise HTTPException(401, "Not authenticated")
    row = db.get(DashState, user.id)
    return json.loads(row.data) if row else {}


@app.put("/api/state")
def put_state(body: StateIn, user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    if not user:
        raise HTTPException(401, "Not authenticated")
    row = db.get(DashState, user.id) or DashState(user_id=user.id)
    data = dict(body.data)
    old = json.loads(row.data or "{}")
    for k in ("alerted", "ingestNote"):  # server-owned keys survive dashboard saves
        if k in old and k not in data:
            data[k] = old[k]
    raw = json.dumps(data)
    if len(raw) > 20000:
        raise HTTPException(413, "Too much data")
    row.data = raw
    db.add(row)
    db.commit()
    return {"ok": True}


# ---------------- Sensor readings ----------------
def _device_key(uid: int) -> str:
    """Deterministic per-user device key (no extra column needed)."""
    sig = hmac.new(get_settings().secret_key.encode(), f"device:{uid}".encode(),
                   hashlib.sha256).hexdigest()[:24]
    return f"fc_{uid}_{sig}"


def _device_user(db: SessionDep, x_api_key: Annotated[Optional[str], Header()] = None) -> DemoUser:
    parts = (x_api_key or "").split("_")
    if len(parts) != 3 or not parts[1].isdigit() or not hmac.compare_digest(
            _device_key(int(parts[1])), x_api_key):
        raise HTTPException(401, "Invalid or missing X-API-Key")
    user = db.get(DemoUser, int(parts[1]))
    if not user:
        raise HTTPException(401, "Invalid or missing X-API-Key")
    return user


def _span(seconds: float) -> str:
    m = int(max(0, seconds) // 60)
    return "less than a minute" if m < 1 else f"{m} minute{'s' if m != 1 else ''}" if m < 120 else f"{m / 60:.1f} hours"


LIVE_LO, LIVE_HI = 0.0, 5.0  # safe range for live sensors
MAX_LIVE_SENSORS = 1  # demo limit


class ReadingIn(BaseModel):
    sensor: str = Field(default="Live Sensor", min_length=1, max_length=60)
    temperature: float = Field(ge=-60, le=100)


def _ms(dt: datetime) -> int:
    return int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp() * 1000)


def _store_reading(request: Request, body: ReadingIn, user: DemoUser, db: Session,
                   ts: Optional[datetime] = None) -> dict:
    """Called by the sensor / app / script. Auth: X-API-Key header."""
    name = body.sensor.strip()
    prev = db.exec(select(Reading).where(Reading.user_id == user.id, Reading.sensor == name)
                   .order_by(Reading.created_at.desc()).limit(1)).first()
    if not prev:
        n = db.exec(select(func.count(distinct(Reading.sensor))).where(
                Reading.user_id == user.id,
                Reading.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))).one()
        if n >= MAX_LIVE_SENSORS:
            raise HTTPException(400, "Demo accounts are limited to 1 live sensor for now. Remove the existing one first.")
    db.add(Reading(user_id=user.id, sensor=name, temperature=body.temperature,
                   **({"created_at": ts} if ts else {})))
    if random.random() < 0.05:  # occasional cleanup: keep 7 days
        db.exec(delete(Reading).where(Reading.user_id == user.id,
                Reading.created_at < datetime.now(timezone.utc) - timedelta(days=7)))
    db.commit()
    st = db.get(DashState, user.id)
    prefs = json.loads(st.data) if st else {}
    lo, hi = LIVE_LO, LIVE_HI  # default; overridden by the user's saved range for this sensor
    r = (prefs.get("liveRanges") or {}).get(name)
    if isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) for x in r) and r[0] < r[1]:
        lo, hi = float(r[0]), float(r[1])
    out = not (lo <= body.temperature <= hi)
    emailed = recovered = False
    now = ts or datetime.now(timezone.utc)
    alerted = dict(prefs.get("alerted") or {})  # sensors we already emailed about, until they recover
    was_alerted = bool(alerted.get(name))
    if was_alerted and prev is not None:  # silent for 30+ minutes: treat the next alert as a new one
        pt = prev.created_at if prev.created_at.tzinfo else prev.created_at.replace(tzinfo=timezone.utc)
        if now - pt > timedelta(minutes=30):
            was_alerted = False
    fresh = ts is None or datetime.now(timezone.utc) - ts < timedelta(minutes=10)  # no emails for old data
    if out and not was_alerted and fresh and prefs.get("emailAlerts", True):
        host = request.headers.get("x-forwarded-host") or request.url.netloc
        emailed = send_email(
            user.email, f"FreshCheck alert: {name} is {body.temperature:.1f}°C",
            f"Hi {user.name},\n\n{name} just reported {body.temperature:.1f}°C, outside the safe range "
            f"of {lo:g} to {hi:g}°C.\n\nOpen your dashboard: https://{host}/dashboard\n\n- FreshCheck")
        if emailed:
            _set_pref(db, user, "alerted", {**alerted, name: {"t": int(now.timestamp() * 1000)}})  # when the alert began
    elif not out and alerted.get(name):  # back to normal
        info = alerted.pop(name)
        if fresh and prefs.get("emailAlerts", True):
            began = info.get("t") if isinstance(info, dict) else None
            took = f"It was outside the range for about {_span(now.timestamp() - began / 1000)}.\n\n" if began else ""
            host = request.headers.get("x-forwarded-host") or request.url.netloc
            recovered = send_email(
                user.email, f"FreshCheck: {name} is back to normal ({body.temperature:.1f}°C)",
                f"Hi {user.name},\n\n{name} is back within its safe range: {body.temperature:.1f}°C "
                f"(safe range {lo:g} to {hi:g}°C).\n{took}Open your dashboard: https://{host}/dashboard\n\n- FreshCheck")
        _set_pref(db, user, "alerted", alerted)  # the next alert gets a new email
        print(f"[recovery] sensor={name!r} temp={body.temperature} range={lo:g}-{hi:g} emailed={recovered}")
    if out:
        print(f"[alert] sensor={name!r} temp={body.temperature} range={lo:g}-{hi:g} was_alerted={was_alerted} "
              f"fresh={fresh} emailAlerts={prefs.get('emailAlerts', True)} emailed={emailed}")
    return {"ok": True, "sensor": name, "temperature": body.temperature, "alert": out, "emailed": emailed, "recovered": recovered}


@app.get("/api/readings")
def list_readings(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    """Used by the dashboard: last 60 readings per sensor from the past 24h."""
    if not user:
        raise HTTPException(401, "Not authenticated")
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = db.exec(select(Reading).where(Reading.user_id == user.id, Reading.created_at >= since)
                   .order_by(Reading.created_at.desc()).limit(600)).all()
    out: dict = {}
    for r in rows:
        lst = out.setdefault(r.sensor, [])
        if len(lst) < 60:
            lst.append({"t": _ms(r.created_at), "v": r.temperature})
    return {"sensors": {k: v[::-1] for k, v in out.items()}}


@app.get("/api/device-key")
def device_key(user: Annotated[Optional[DemoUser], Depends(_current)]):
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"key": _device_key(user.id), "email_ready": email_ready()}


@app.delete("/api/readings")
def delete_readings(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep,
                    sensor: Optional[str] = None):
    """Remove one live sensor (and its readings), or all of them if no sensor is given."""
    if not user:
        raise HTTPException(401, "Not authenticated")
    q = delete(Reading).where(Reading.user_id == user.id)
    if sensor:
        q = q.where(Reading.sensor == sensor)
    res = db.exec(q)
    st = db.get(DashState, user.id)
    if st:
        d = json.loads(st.data or "{}")
        al = d.get("alerted") or {}
        if sensor:
            al.pop(sensor, None)
        else:
            al = {}
        d["alerted"] = al
        st.data = json.dumps(d)
        db.add(st)
    db.commit()
    return {"deleted": getattr(res, "rowcount", None)}


@app.post("/api/test-email")
def test_email(user: Annotated[Optional[DemoUser], Depends(_current)]):
    if not user:
        raise HTTPException(401, "Not authenticated")
    if not email_ready():
        raise HTTPException(400, "Email is not configured on the server yet (see README).")
    if not send_email(user.email, "FreshCheck test email",
                      f"Hi {user.name},\n\nThis is a test alert. Email alerts are working.\n\n- FreshCheck"):
        raise HTTPException(502, "The email provider rejected the message. Check the Vercel logs.")
    return {"ok": True, "to": user.email}


@app.post("/api/readings", status_code=201)
def add_reading(request: Request, body: ReadingIn, user: Annotated[DemoUser, Depends(_device_user)], db: SessionDep):
    """Called by a real sensor / script. Auth: X-API-Key header."""
    return _store_reading(request, body, user, db)


@app.post("/api/simulate-reading", status_code=201)
def simulate_reading(request: Request, body: ReadingIn, user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    """Used by the dashboard's Add sensor popup. Auth: login cookie."""
    if not user:
        raise HTTPException(401, "Not authenticated")
    return _store_reading(request, body, user, db)


# ---------------- Password reset ----------------
class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


def _pw_fingerprint(u: DemoUser) -> str:
    """Changes when the password changes, so a reset link works only once."""
    return hashlib.sha256((u.password or "").encode()).hexdigest()[:16]


@app.post("/api/forgot-password")
def forgot_password(data: ForgotIn, request: Request, db: SessionDep):
    user = db.exec(select(DemoUser).where(DemoUser.email == data.email.lower())).one_or_none()
    if user and user.password:
        token = create_access_token({"sub": str(user.id), "purpose": "reset",
                                     "fp": _pw_fingerprint(user)}, expires_minutes=30)
        host = request.headers.get("x-forwarded-host") or request.url.netloc
        send_email(user.email, "Reset your FreshCheck password",
                   f"Hi {user.name},\n\nUse this link within 30 minutes to choose a new password:\n"
                   f"https://{host}/?reset={token}\n\nIf you did not ask for this, you can ignore this email.\n\n- FreshCheck")
    # Same answer whether or not the account exists (no account enumeration)
    return {"message": "If an account exists for that email, a reset link is on its way."}


@app.post("/api/reset-password")
def reset_password(data: ResetIn, response: Response, db: SessionDep):
    bad = HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    try:
        p = decode_access_token(data.token)
    except jwt.exceptions.InvalidTokenError:
        raise bad
    user = db.get(DemoUser, int(p["sub"])) if p.get("purpose") == "reset" else None
    if not user or not user.password or p.get("fp") != _pw_fingerprint(user):
        raise bad
    user.password = hash_password(data.password)
    db.add(user)
    db.commit()
    _start_session(response, user)
    return _profile(user)


# ---------------- Admin: demo requests list ----------------
def _is_admin(u: Optional[DemoUser]) -> bool:
    admins = {e.strip().lower() for e in get_settings().admin_emails.split(",") if e.strip()}
    return bool(u and u.email.lower() in admins)


def _need_admin(user: Optional[DemoUser]):
    if not user:
        raise HTTPException(401, "Not authenticated")
    if not _is_admin(user):
        raise HTTPException(403, "Not authorized")


@app.get("/api/admin/demo-requests")
def admin_list(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    _need_admin(user)
    usage = {uid: (n, last) for uid, n, last in db.exec(
        select(Reading.user_id, func.count(Reading.id), func.max(Reading.created_at))
        .group_by(Reading.user_id)).all()}
    out = []
    for u in db.exec(select(DemoUser).order_by(DemoUser.created_at.desc())).all():
        n, last = usage.get(u.id, (0, None))
        out.append({"id": u.id, "name": u.name, "business": u.business, "type": u.business_type,
                    "email": u.email, "message": u.message, "created": _ms(u.created_at),
                    "active": bool(u.password), "readings": n,
                    "last_reading": _ms(last) if last else None, "you": u.id == user.id})
    return {"requests": out}


@app.delete("/api/admin/demo-requests/{uid}")
def admin_delete(uid: int, user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    _need_admin(user)
    if uid == user.id:
        raise HTTPException(400, "You cannot delete your own account here.")
    target = db.get(DemoUser, uid)
    if not target:
        raise HTTPException(404, "Not found")
    db.exec(delete(Reading).where(Reading.user_id == uid))
    db.exec(delete(DashState).where(DashState.user_id == uid))
    db.delete(target)
    db.commit()
    return {"ok": True}


@app.get("/api/readings/history")
def readings_history(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    """Up to 5000 readings from the past 7 days, as [timestamp_ms, temperature] pairs per sensor."""
    if not user:
        raise HTTPException(401, "Not authenticated")
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = db.exec(select(Reading).where(Reading.user_id == user.id, Reading.created_at >= since)
                   .order_by(Reading.created_at.desc()).limit(5000)).all()
    out: dict = {}
    for r in reversed(rows):
        out.setdefault(r.sensor, []).append([_ms(r.created_at), r.temperature])
    return {"sensors": out}


# ---------------- Sensor Logger (Android app) ingest ----------------
def _user_from_key(db: Session, key: str) -> Optional[DemoUser]:
    parts = (key or "").split("_")
    if not key.isascii() or len(parts) != 3 or not parts[1].isdigit() or not hmac.compare_digest(
            _device_key(int(parts[1])), key):
        return None
    return db.get(DemoUser, int(parts[1]))


def _sl_ms(t) -> Optional[float]:
    """Sensor Logger sends UTC epoch nanoseconds; be lenient about the unit."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    if t > 1e17:
        return t / 1e6
    if t > 1e14:
        return t / 1e3
    if t > 1e11:
        return t
    return t * 1000


def _sl_extract(body: Any):
    """Find temperature readings in a Sensor Logger batch. Returns (readings, sensor names seen)."""
    readings, seen = [], set()
    items = body.get("payload") if isinstance(body, dict) else None
    for r in items if isinstance(items, list) else []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name", ""))
        seen.add(name)
        vals = r.get("values") if isinstance(r.get("values"), dict) else r
        num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)  # noqa: E731
        v = next((x for k, x in vals.items() if "temp" in str(k).lower() and num(x)), None)
        if v is None and "temp" in name.lower():
            v = next((x for k, x in vals.items() if str(k).lower() not in ("time", "accuracy") and num(x)), None)
        if v is not None:
            readings.append((_sl_ms(r.get("time")), float(v)))
    return readings, seen


def _set_pref(db: Session, user: DemoUser, key: str, value) -> None:
    st = db.get(DashState, user.id) or DashState(user_id=user.id)
    d = json.loads(st.data or "{}")
    d[key] = value
    st.data = json.dumps(d)
    db.add(st)
    db.commit()


_SL_CACHE: dict = {}  # (user_id, sensor) -> settings + last stored reading; most pushes then skip the database
_SL_TTL, _SL_TTL_PAUSED = 20.0, 5.0
_SL_PAUSED_MSG = "This sensor was removed in FreshCheck. Use Add sensor > Real sensor to reconnect."


def _uid_from_key(key: str) -> Optional[int]:
    parts = (key or "").split("_")
    if not key.isascii() or len(parts) != 3 or not parts[1].isdigit() or not hmac.compare_digest(
            _device_key(int(parts[1])), key):
        return None
    return int(parts[1])


def _sl_pick(cands, lo, hi, last_ts, last_out):
    """Keep the database light: one reading per 30 s, unless the in/out-of-range status changes."""
    keep = []
    for ts, val in cands:
        out = not (lo <= val <= hi)
        if last_ts is not None and (ts <= last_ts or ((ts - last_ts).total_seconds() < 30 and out == last_out)):
            continue
        keep.append((ts, val))
        last_ts, last_out = ts, out
    return keep


@app.post("/api/ingest/sensor-logger")
def ingest_sensor_logger(request: Request, db: SessionDep, body: Any = Body(default=None),
                         sensor: str = "My Phone",
                         authorization: Annotated[Optional[str], Header()] = None):
    """Push URL for the Sensor Logger app. Auth: 'Authorization: Bearer <device key>'.
    Errors use HTTP 499 + plain text, which Sensor Logger shows to the user."""
    key = (authorization or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    bad_key = PlainTextResponse("Invalid Auth Header. Copy it again from FreshCheck (Bearer + your key).", status_code=499)
    uid = _uid_from_key(key)
    if uid is None:
        return bad_key
    name = (sensor or "").strip()[:60] or "My Phone"

    readings, seen = _sl_extract(body)
    now = datetime.now(timezone.utc)
    cands = []
    for ms, val in readings:
        ts = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else now
        if ts > now + timedelta(minutes=5):
            ts = now
        if ts >= now - timedelta(days=7) and -60 <= val <= 100:
            cands.append((ts, round(val, 2)))
    cands.sort()

    # Fast path: a look-up from the last few seconds says this push needs no database work at all.
    c = _SL_CACHE.get((uid, name))
    if c and time.monotonic() - c["at"] < (_SL_TTL_PAUSED if c["paused"] else _SL_TTL):
        if c["paused"]:
            return PlainTextResponse(_SL_PAUSED_MSG, status_code=499)
        if c.get("blocked"):
            return PlainTextResponse(c["blocked"], status_code=499)
        if not _sl_pick(cands, c["lo"], c["hi"], c["last_ts"], c["last_out"]):
            return {"ok": True, "stored": 0, "seen": sorted(seen)}

    # Slow path: read the account, its settings and the last stored reading, then refresh the cache.
    user = db.get(DemoUser, uid)
    if not user:
        return bad_key
    st = db.get(DashState, uid)
    prefs = json.loads(st.data) if st else {}
    paused = bool((prefs.get("pausedFeeds") or {}).get(name))
    lo, hi = LIVE_LO, LIVE_HI
    r = (prefs.get("liveRanges") or {}).get(name)
    if isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) for x in r) and r[0] < r[1]:
        lo, hi = float(r[0]), float(r[1])
    prev = db.exec(select(Reading).where(Reading.user_id == uid, Reading.sensor == name)
                   .order_by(Reading.created_at.desc()).limit(1)).first()
    last_ts = (prev.created_at if prev.created_at.tzinfo else prev.created_at.replace(tzinfo=timezone.utc)) if prev else None
    last_out = bool(prev) and not (lo <= prev.temperature <= hi)
    c = _SL_CACHE[(uid, name)] = {"at": time.monotonic(), "paused": paused, "lo": lo, "hi": hi,
                                  "last_ts": last_ts, "last_out": last_out}
    if len(_SL_CACHE) > 500:  # tidy up old entries
        for k in [k for k, v in _SL_CACHE.items() if time.monotonic() - v["at"] > 600]:
            _SL_CACHE.pop(k, None)
    if paused:
        return PlainTextResponse(_SL_PAUSED_MSG, status_code=499)
    print(f"[sensor-logger] user={uid} sensor={name!r} names={sorted(seen)} "
          f"temps={[v for _, v in readings][:5]} usable={len(cands)}")

    if not cands:  # connected, but nothing usable: leave a note the dashboard can show
        old = (prefs.get("ingestNote") or {}).get("t", 0)
        if seen and now.timestamp() * 1000 - old > 30000:
            _set_pref(db, user, "ingestNote", {"t": int(now.timestamp() * 1000), "names": sorted(seen)[:12],
                                               "values": [v for _, v in readings][:3]})
        return {"ok": True, "stored": 0, "seen": sorted(seen)}

    stored = 0
    try:
        for ts, val in _sl_pick(cands, lo, hi, last_ts, last_out):
            _store_reading(request, ReadingIn(sensor=name, temperature=val), user, db, ts=ts)
            c["last_ts"], c["last_out"] = ts, not (lo <= val <= hi)
            stored += 1
    except HTTPException as e:
        c["blocked"] = str(e.detail)
        return PlainTextResponse(c["blocked"], status_code=499)
    return {"ok": True, "stored": stored, "seen": sorted(seen)}


@app.get("/api/ingest-status")
def ingest_status(user: Annotated[Optional[DemoUser], Depends(_current)], db: SessionDep):
    if not user:
        raise HTTPException(401, "Not authenticated")
    st = db.get(DashState, user.id)
    return {"note": (json.loads(st.data) if st else {}).get("ingestNote")}

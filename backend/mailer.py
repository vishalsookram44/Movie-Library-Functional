import json
import smtplib
import urllib.request
from email.message import EmailMessage

from backend.config import get_settings


def email_ready() -> bool:
    s = get_settings()
    return bool(s.resend_api_key or (s.smtp_host and s.mail_from))


def send_email(to: str, subject: str, body: str) -> bool:
    """Never raises: a mail problem must not break saving a reading."""
    s = get_settings()
    try:
        if s.resend_api_key:
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=json.dumps({"from": s.mail_from or "FreshCheck <onboarding@resend.dev>",
                                 "to": [to], "subject": subject, "text": body}).encode(),
                headers={"Authorization": f"Bearer {s.resend_api_key}",
                         "Content-Type": "application/json", "User-Agent": "freshcheck/1.0"})
            urllib.request.urlopen(req, timeout=8).read()
            return True
        if s.smtp_host and s.mail_from:
            m = EmailMessage()
            m["From"], m["To"], m["Subject"] = s.mail_from, to, subject
            m.set_content(body)
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=8) as c:
                c.starttls()
                if s.smtp_user:
                    c.login(s.smtp_user, s.smtp_password)
                c.send_message(m)
            return True
    except Exception as e:  # noqa: BLE001
        print("email failed:", e)
    return False

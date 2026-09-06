import base64
import binascii

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.auth import CurrentUserDep, SessionDep
from backend.models import User
from backend.schemas import (
    PasswordUpdate,
    ProfilePictureUpdate,
    UsernameUpdate,
    UserProfileOut,
)
from backend.security import hash_password, verify_password

router = APIRouter(prefix="/api/me", tags=["profile"])

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB


@router.get("", response_model=UserProfileOut)
def get_profile(user: CurrentUserDep):
    return user


@router.put("/username", response_model=UserProfileOut)
def update_username(data: UsernameUpdate, db: SessionDep, user: CurrentUserDep):
    new_username = data.username.strip()

    if not new_username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    existing = db.exec(
        select(User).where(User.username == new_username, User.id != user.id)
    ).one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="That username is already taken")

    user.username = new_username
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/password")
def update_password(data: PasswordUpdate, db: SessionDep, user: CurrentUserDep):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=400, detail="New password must be at least 8 characters"
        )

    user.password = hash_password(data.new_password)
    db.add(user)
    db.commit()
    return {"message": "Password updated"}


@router.put("/picture", response_model=UserProfileOut)
def update_picture(data: ProfilePictureUpdate, db: SessionDep, user: CurrentUserDep):
    image_data = data.image_base64

    if not image_data.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Invalid image format")

    try:
        _, encoded = image_data.split(",", 1)
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Could not decode image")

    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be smaller than 2MB")

    user.profile_picture = image_data
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import or_, select

from backend.auth import OptionalUserDep, SessionDep
from backend.models import User
from backend.schemas import LoginRequest, RegisterRequest, UserOut
from backend.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: SessionDep):
    existing = db.exec(
        select(User).where(
            or_(User.username == data.username, User.email == data.email)
        )
    ).one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    user = User(
        username=data.username,
        email=data.email,
        password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, response: Response, db: SessionDep):
    user = db.exec(
        select(User).where(User.username == data.username)
    ).one_or_none()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
def me(user: OptionalUserDep):
    if user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }

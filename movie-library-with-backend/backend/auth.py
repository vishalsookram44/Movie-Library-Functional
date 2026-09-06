from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session

from backend.database import get_session
from backend.models import User
from backend.security import decode_access_token

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user_optional(request: Request, db: SessionDep) -> Optional[User]:
    """Returns the logged-in user if a valid session cookie is present, else None."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except InvalidTokenError:
        return None
    if user_id is None:
        return None
    return db.get(User, int(user_id))


OptionalUserDep = Annotated[Optional[User], Depends(get_current_user_optional)]


def get_current_user(user: OptionalUserDep) -> User:
    """Raises 401 if there is no logged-in user. Use this to protect routes."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]

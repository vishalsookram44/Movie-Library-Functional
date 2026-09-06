from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr


class CommentCreate(BaseModel):
    movie_id: int
    movie_title: str | None = None
    content: str


class CommentUpdate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    content: str
    movie_id: int
    created_at: datetime
    username: str
    user_id: int


class ReactionRequest(BaseModel):
    reaction: Literal["like", "dislike"]


class ReactionOut(BaseModel):
    movie_id: int
    likes: int
    dislikes: int
    user_reaction: Optional[str] = None


class UsernameUpdate(BaseModel):
    username: str


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class ProfilePictureUpdate(BaseModel):
    image_base64: str


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    profile_picture: Optional[str] = None


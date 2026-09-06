from datetime import datetime

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


class CommentOut(BaseModel):
    id: int
    content: str
    movie_id: int
    created_at: datetime
    username: str

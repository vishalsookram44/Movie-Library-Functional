from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str

    comments: list["Comment"] = Relationship(back_populates="user")


class CommentBase(SQLModel):
    content: str
    movie_id: int = Field(index=True)  # TMDB movie id
    movie_title: Optional[str] = None


class Comment(CommentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user_id: int = Field(foreign_key="user.id")

    user: Optional[User] = Relationship(back_populates="comments")

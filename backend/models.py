from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str
    profile_picture: Optional[str] = None  # base64 data URL, e.g. "data:image/png;base64,..."

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


class MovieReaction(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="uq_movie_user_reaction"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    movie_id: int = Field(index=True)  # TMDB movie id
    user_id: int = Field(foreign_key="user.id", index=True)
    reaction: str  # "like" or "dislike"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


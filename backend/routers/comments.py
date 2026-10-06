from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.auth import CurrentUserDep, SessionDep
from backend.models import Comment
from backend.schemas import CommentCreate, CommentOut, CommentUpdate

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/movies/{movie_id}/comments", response_model=list[CommentOut])
def get_comments(movie_id: int, db: SessionDep):
    comments = db.exec(
        select(Comment)
        .where(Comment.movie_id == movie_id)
        .order_by(Comment.created_at.desc())
    ).all()

    return [
        CommentOut(
            id=c.id,
            content=c.content,
            movie_id=c.movie_id,
            created_at=c.created_at,
            username=c.user.username,
            user_id=c.user_id,
        )
        for c in comments
    ]


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    movie_id: int, data: CommentCreate, db: SessionDep, user: CurrentUserDep
):
    comment = Comment(
        content=data.content,
        movie_id=movie_id,
        movie_title=data.movie_title,
        user_id=user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        content=comment.content,
        movie_id=comment.movie_id,
        created_at=comment.created_at,
        username=user.username,
        user_id=user.id,
    )


@router.put("/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int, data: CommentUpdate, db: SessionDep, user: CurrentUserDep
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments",
        )

    comment.content = data.content
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        content=comment.content,
        movie_id=comment.movie_id,
        created_at=comment.created_at,
        username=user.username,
        user_id=user.id,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: SessionDep, user: CurrentUserDep):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )
    db.delete(comment)
    db.commit()

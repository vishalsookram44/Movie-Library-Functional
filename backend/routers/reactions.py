from fastapi import APIRouter
from sqlmodel import select

from backend.auth import CurrentUserDep, OptionalUserDep, SessionDep
from backend.models import MovieReaction
from backend.schemas import ReactionOut, ReactionRequest

router = APIRouter(prefix="/api", tags=["reactions"])


def _get_counts(db: SessionDep, movie_id: int) -> tuple[int, int]:
    reactions = db.exec(
        select(MovieReaction).where(MovieReaction.movie_id == movie_id)
    ).all()
    likes = sum(1 for r in reactions if r.reaction == "like")
    dislikes = sum(1 for r in reactions if r.reaction == "dislike")
    return likes, dislikes


@router.get("/movies/{movie_id}/reactions", response_model=ReactionOut)
def get_reactions(movie_id: int, db: SessionDep, user: OptionalUserDep):
    likes, dislikes = _get_counts(db, movie_id)

    user_reaction = None
    if user:
        existing = db.exec(
            select(MovieReaction).where(
                MovieReaction.movie_id == movie_id,
                MovieReaction.user_id == user.id,
            )
        ).one_or_none()
        if existing:
            user_reaction = existing.reaction

    return ReactionOut(
        movie_id=movie_id, likes=likes, dislikes=dislikes, user_reaction=user_reaction
    )


@router.post("/movies/{movie_id}/reactions", response_model=ReactionOut)
def set_reaction(
    movie_id: int, data: ReactionRequest, db: SessionDep, user: CurrentUserDep
):
    existing = db.exec(
        select(MovieReaction).where(
            MovieReaction.movie_id == movie_id,
            MovieReaction.user_id == user.id,
        )
    ).one_or_none()

    if existing and existing.reaction == data.reaction:
        # clicking the same reaction again removes it (toggle off)
        db.delete(existing)
        db.commit()
        user_reaction = None
    elif existing:
        # switching from like -> dislike or vice versa
        existing.reaction = data.reaction
        db.add(existing)
        db.commit()
        user_reaction = data.reaction
    else:
        new_reaction = MovieReaction(
            movie_id=movie_id, user_id=user.id, reaction=data.reaction
        )
        db.add(new_reaction)
        db.commit()
        user_reaction = data.reaction

    likes, dislikes = _get_counts(db, movie_id)
    return ReactionOut(
        movie_id=movie_id, likes=likes, dislikes=dislikes, user_reaction=user_reaction
    )

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database import create_db_and_tables
from backend.routers import auth_routes, comments, profile, reactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Movie Library API", lifespan=lifespan)

app.include_router(auth_routes.router)
app.include_router(comments.router)
app.include_router(reactions.router)
app.include_router(profile.router)
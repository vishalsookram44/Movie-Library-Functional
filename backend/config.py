from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_uri: str = "sqlite:///./movie_library.db"
    secret_key: str = "change-this-to-a-random-secret-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires: int = 60 * 24  # minutes (24 hours)
    env: str = "development"

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings():
    return Settings()

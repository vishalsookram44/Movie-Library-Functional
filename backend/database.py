from sqlmodel import SQLModel, Session, create_engine

from backend.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_uri,
    echo=False,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},  # required behind Neon's pooler
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
        

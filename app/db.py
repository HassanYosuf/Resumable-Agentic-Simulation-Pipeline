from datetime import datetime
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///./jobs.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def create_session() -> Session:
    return Session(engine)

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL, ensure_directories

ensure_directories()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    from .models import AssessmentLog, AssessmentQuestion, Concept, ContentChunk, LearnerMastery, Material, Topic

    Base.metadata.create_all(bind=engine)

    database_path = Path(DATABASE_URL.replace("sqlite:///", "", 1))
    if database_path.parent.exists() is False:
        database_path.parent.mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

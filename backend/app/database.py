"""
Database connection, engine configuration, and session management.
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

# If using SQLite relative path, ensure directory exists
if settings.DB_URL.startswith("sqlite"):
    # Extract file path after sqlite:/// or sqlite:////
    db_path = settings.DB_URL.replace("sqlite:///", "").replace("sqlite:////", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DB_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

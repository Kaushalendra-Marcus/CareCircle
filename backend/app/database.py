"""Database engine / session / Base."""
import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_url(url: str) -> str:
    """Accept plain `postgresql://` URLs (default driver psycopg2, often
    absent) by mapping them to the installed psycopg3 (`psycopg`) driver."""
    if re.match(r"^postgresql://", url):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = normalize_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://carecircle:carecircle@localhost:5432/carecircle",
    )
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

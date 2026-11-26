"""Shared pytest fixtures: SQLite-backed app + TestClient."""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_URL = "sqlite:///./test.db"
engine = create_engine(TEST_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def family(client):
    r = client.post("/api/v1/seed").json()
    assert r["recipient"] == "Mum"
    recips = client.get("/api/v1/recipients").json()
    members = client.get("/api/v1/family-members").json()
    rid = recips[0]["id"]
    by_name = {m["name"]: m for m in members}
    assert by_name["Ravi"]["relationship"] == "Son"
    return {"id": rid, "members": by_name}

"""Shared pytest fixtures: SQLite-backed app + TestClient."""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database as dbmod
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
    r = client.post("/api/recipients", json={"name": "Mum"}).json()
    m1 = client.post("/api/members", json={"name": "Ravi"}).json()
    m2 = client.post("/api/members", json={"name": "Priya"}).json()
    return r, m1, m2

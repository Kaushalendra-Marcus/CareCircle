"""CareCircle Lite API (v1)."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .models import AssistantInteraction  # noqa: F401 (register models)
from .models import CareRecipient, CareTask, FamilyMember  # noqa: F401
from .routers import assistant, people, tasks
from .seed import reset_demo, seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Belt and braces: Alembic (entrypoint) is the source of truth for
    # upgrades; create_all keeps `uvicorn app.main:app` working directly.
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO", "false").lower() == "true":
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()
    yield


app = FastAPI(title="CareCircle Lite API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(people.recipients)
app.include_router(people.members)
app.include_router(people.today_router)
app.include_router(assistant.router)


@app.get("/api/health")
@app.get("/api/v1/health")
def health():
    return {"ok": True}


@app.post("/api/v1/seed")
def seed():
    db = SessionLocal()
    try:
        return {"seeded": True, **seed_demo(db)}
    finally:
        db.close()


@app.post("/api/v1/seed/reset")
def seed_reset():
    """Delete demo tasks and re-seed (documented reset command)."""
    db = SessionLocal()
    try:
        return {"reset": True, **reset_demo(db)}
    finally:
        db.close()

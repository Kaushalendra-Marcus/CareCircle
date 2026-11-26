"""CareCircle Lite API."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .models import CareRecipient  # noqa: F401  (register models)
from .models import AiInteractionLog, CareTask, FamilyMember  # noqa: F401
from .routers import assistant, people, tasks
from .seed import seed_demo

app = FastAPI(title="CareCircle Lite API", version="0.1.0")
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
app.include_router(assistant.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO", "false").lower() == "true":
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/seed")
def seed():
    db = SessionLocal()
    try:
        seed_demo(db)
        return {"seeded": True}
    finally:
        db.close()

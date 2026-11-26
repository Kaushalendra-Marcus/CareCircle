"""Pydantic schemas (request/response shapes)."""
from datetime import datetime
from pydantic import BaseModel, Field

CATEGORIES = ("medicine", "appointment", "checkin", "other")


class RecipientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""


class RecipientOut(BaseModel):
    id: int
    name: str
    notes: str

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str = ""


class MemberOut(BaseModel):
    id: int
    name: str
    relation: str

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = "other"
    due_at: datetime
    notes: str = ""
    recipient_id: int


class TaskUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    due_at: datetime | None = None
    notes: str | None = None
    # If supplied, checked against the row version for safe concurrent edits.
    version: int | None = None


class TaskComplete(BaseModel):
    completed_by_id: int | None = None
    completed_by_name: str | None = None
    version: int | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    category: str
    status: str
    due_at: datetime
    notes: str
    recipient_id: int
    completed_by_id: int | None
    completed_by_name: str | None = None
    completed_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class TodayOut(BaseModel):
    date: str
    overdue: list[TaskOut]
    due: list[TaskOut]
    done: list[TaskOut]
    counts: dict


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    recipient_id: int | None = None


class AiLogOut(BaseModel):
    id: int
    question: str
    context: str
    answer: str
    latency_ms: int
    model: str
    created_at: datetime

    model_config = {"from_attributes": True}

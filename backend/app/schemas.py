"""Pydantic v1 API shapes (request/response)."""
from datetime import date, datetime
from pydantic import BaseModel, Field

TASK_TYPES = ("medication", "appointment", "checkin", "general", "other")
# Back-compat aliases accepted on input for older clients.
TASK_TYPE_ALIASES = {"medicine": "medication", "check-in": "checkin"}
PRIORITIES = ("low", "normal", "high")
STATUSES = ("pending", "completed", "cancelled")


def normalize_task_type(v: str) -> str:
    v = (v or "other").strip().lower()
    return TASK_TYPE_ALIASES.get(v, v)


class RecipientOut(BaseModel):
    id: int
    name: str
    date_of_birth: date | None = None
    timezone: str
    notes: str = ""

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relationship: str = ""
    care_recipient_id: int | None = None
    avatar_url: str | None = None


class MemberOut(BaseModel):
    id: int
    care_recipient_id: int | None = None
    name: str
    relationship: str = ""
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    task_type: str = "other"
    due_at: datetime
    priority: str = "normal"
    care_recipient_id: int
    assigned_member_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    task_type: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    status: str | None = None
    assigned_member_id: int | None = None
    # If supplied, checked against the row version for safe concurrent edits.
    version: int | None = None


class TaskComplete(BaseModel):
    completed_by_member_id: int | None = None
    completed_by_name: str | None = None
    version: int | None = None


class TaskOut(BaseModel):
    id: int
    care_recipient_id: int
    title: str
    description: str = ""
    task_type: str
    due_at: datetime
    status: str
    priority: str = "normal"
    assigned_member_id: int | None = None
    assigned_member_name: str | None = None
    completed_by_member_id: int | None = None
    completed_by_name: str | None = None
    completed_at: datetime | None = None
    version: int

    model_config = {"from_attributes": True}


class TodayRecipient(BaseModel):
    id: int
    name: str


class TodaySummary(BaseModel):
    total: int
    completed: int
    pending: int
    overdue: int


class TodayOut(BaseModel):
    date: str
    recipient: TodayRecipient | None = None
    summary: TodaySummary
    overdue: list[TaskOut]
    due: list[TaskOut]
    done: list[TaskOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    care_recipient_id: int | None = None
    family_member_id: int | None = None


class InteractionOut(BaseModel):
    id: int
    care_recipient_id: int | None = None
    family_member_id: int | None = None
    question: str
    context_sent: str
    answer: str
    latency_ms: int
    model_name: str
    created_at: datetime

    model_config = {"from_attributes": True}

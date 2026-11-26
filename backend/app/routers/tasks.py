"""Task CRUD + complete + today endpoints (v1)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import CareRecipient, CareTask, FamilyMember
from ..schemas import (
    PRIORITIES,
    STATUSES,
    TaskComplete,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TodayOut,
    normalize_task_type,
)
from ..today import _aware, group_today, task_to_dict

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _out(t: CareTask) -> dict:
    return task_to_dict(t)


def _due(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    if not db.get(CareRecipient, payload.care_recipient_id):
        raise HTTPException(404, "care recipient not found")
    task_type = normalize_task_type(payload.task_type)
    priority = (payload.priority or "normal").lower()
    if priority not in PRIORITIES:
        raise HTTPException(422, f"priority must be one of {PRIORITIES}")
    if payload.assigned_member_id is not None and not db.get(
        FamilyMember, payload.assigned_member_id
    ):
        raise HTTPException(404, "assigned family member not found")
    task = CareTask(
        care_recipient_id=payload.care_recipient_id,
        title=payload.title.strip(),
        description=payload.description or "",
        task_type=task_type,
        due_at=_due(payload.due_at),
        priority=priority,
        assigned_member_id=payload.assigned_member_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _out(task)


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status: str | None = None,
    care_recipient_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = (
        select(CareTask)
        .options(joinedload(CareTask.completed_by), joinedload(CareTask.assigned_member))
        .order_by(CareTask.due_at)
    )
    if status:
        q = q.where(CareTask.status == status)
    if care_recipient_id is not None:
        q = q.where(CareTask.care_recipient_id == care_recipient_id)
    return [_out(t) for t in db.scalars(q).all()]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    db.refresh(t, ["completed_by", "assigned_member"])
    return _out(t)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    if payload.version is not None and payload.version != t.version:
        raise HTTPException(409, "task changed by someone else — refresh and try again")
    if payload.title is not None:
        t.title = payload.title.strip()
    if payload.description is not None:
        t.description = payload.description
    if payload.task_type is not None:
        t.task_type = normalize_task_type(payload.task_type)
    if payload.due_at is not None:
        t.due_at = _due(payload.due_at)
    if payload.priority is not None:
        if payload.priority.lower() not in PRIORITIES:
            raise HTTPException(422, f"priority must be one of {PRIORITIES}")
        t.priority = payload.priority.lower()
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(422, f"status must be one of {STATUSES}")
        t.status = payload.status
        if payload.status != "completed":
            t.completed_by_member_id = None
            t.completed_at = None
    if payload.assigned_member_id is not None:
        if payload.assigned_member_id != 0 and not db.get(
            FamilyMember, payload.assigned_member_id
        ):
            raise HTTPException(404, "assigned family member not found")
        t.assigned_member_id = payload.assigned_member_id or None
    t.version += 1
    db.commit()
    db.refresh(t)
    db.refresh(t, ["completed_by", "assigned_member"])
    return _out(t)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    db.delete(t)
    db.commit()
    return None


def _resolve_member(db: Session, payload: TaskComplete) -> FamilyMember | None:
    if payload.completed_by_member_id is not None:
        m = db.get(FamilyMember, payload.completed_by_member_id)
        if not m:
            raise HTTPException(404, "family member not found")
        return m
    if payload.completed_by_name:
        name = payload.completed_by_name.strip()
        m = db.scalar(select(FamilyMember).where(FamilyMember.name == name))
        if not m:
            m = FamilyMember(name=name)
            db.add(m)
            db.flush()
        return m
    return None


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, payload: TaskComplete, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    if t.status == "completed":
        raise HTTPException(409, "task is already completed")
    if payload.version is not None and payload.version != t.version:
        raise HTTPException(409, "task changed by someone else — refresh and try again")
    member = _resolve_member(db, payload)
    t.status = "completed"
    t.completed_by_member_id = member.id if member else None
    t.completed_at = datetime.now(timezone.utc)
    t.version += 1
    db.commit()
    db.refresh(t)
    db.refresh(t, ["completed_by", "assigned_member"])
    return _out(t)


@router.post("/{task_id}/reopen", response_model=TaskOut)
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    t.status = "pending"
    t.completed_by_member_id = None
    t.completed_at = None
    t.version += 1
    db.commit()
    db.refresh(t)
    return _out(t)

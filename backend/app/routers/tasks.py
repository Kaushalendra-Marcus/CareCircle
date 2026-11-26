"""Task CRUD + complete + today endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import CareTask, FamilyMember
from ..schemas import TaskComplete, TaskCreate, TaskOut, TaskUpdate, TodayOut
from ..today import group_today, task_to_dict

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _out(t: CareTask) -> dict:
    return task_to_dict(t)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    due = payload.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    task = CareTask(
        title=payload.title.strip(),
        category=payload.category or "other",
        due_at=due,
        notes=payload.notes or "",
        recipient_id=payload.recipient_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _out(task)


@router.get("", response_model=list[TaskOut])
def list_tasks(status: str | None = None, db: Session = Depends(get_db)):
    q = select(CareTask).options(joinedload(CareTask.completed_by)).order_by(
        CareTask.due_at
    )
    if status:
        q = q.where(CareTask.status == status)
    return [_out(t) for t in db.scalars(q).all()]


@router.get("/today", response_model=TodayOut)
def today(recipient_id: int | None = None, db: Session = Depends(get_db)):
    q = select(CareTask).options(joinedload(CareTask.completed_by))
    if recipient_id is not None:
        q = q.where(CareTask.recipient_id == recipient_id)
    tasks = db.scalars(q).all()
    return group_today(list(tasks))


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    db.refresh(t, ["completed_by"])
    return _out(t)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    if payload.version is not None and payload.version != t.version:
        raise HTTPException(
            409,
            "task changed by someone else — refresh and try again",
        )
    if payload.title is not None:
        t.title = payload.title.strip()
    if payload.category is not None:
        t.category = payload.category
    if payload.due_at is not None:
        due = payload.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        t.due_at = due
    if payload.notes is not None:
        t.notes = payload.notes
    t.version += 1
    db.commit()
    db.refresh(t)
    db.refresh(t, ["completed_by"])
    return _out(t)


def _resolve_member(db: Session, payload: TaskComplete) -> FamilyMember | None:
    if payload.completed_by_id is not None:
        m = db.get(FamilyMember, payload.completed_by_id)
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
    if t.status == "done":
        raise HTTPException(409, "task is already done")
    if payload.version is not None and payload.version != t.version:
        raise HTTPException(
            409,
            "task changed by someone else — refresh and try again",
        )
    member = _resolve_member(db, payload)
    t.status = "done"
    t.completed_by_id = member.id if member else None
    t.completed_at = datetime.now(timezone.utc)
    t.version += 1
    db.commit()
    db.refresh(t)
    db.refresh(t, ["completed_by"])
    return _out(t)


@router.post("/{task_id}/reopen", response_model=TaskOut)
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CareTask, task_id)
    if not t:
        raise HTTPException(404, "task not found")
    t.status = "pending"
    t.completed_by_id = None
    t.completed_at = None
    t.version += 1
    db.commit()
    db.refresh(t)
    return _out(t)

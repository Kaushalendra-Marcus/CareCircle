"""Idempotent demo seed + reset. Safe to run any number of times.

Recipient Mum (Asia/Kolkata) with Ravi (son), Priya and Ananya (daughters).
Tasks are generated relative to *now* so the demo always shows a mix of
overdue / due / done whatever day it runs.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CareRecipient, CareTask, FamilyMember

TZ = "Asia/Kolkata"
DEMO_TAG = "demo"


def _member(db: Session, rid: int, name: str, rel: str) -> FamilyMember:
    m = db.scalar(
        select(FamilyMember).where(
            FamilyMember.care_recipient_id == rid, FamilyMember.name == name
        )
    )
    if not m:
        m = FamilyMember(care_recipient_id=rid, name=name, relationship=rel)
        db.add(m)
        db.flush()
    return m


def seed_demo(db: Session) -> dict:
    mum = db.scalar(select(CareRecipient).where(CareRecipient.name == "Mum"))
    if not mum:
        mum = CareRecipient(name="Mum", timezone=TZ, notes="BP + diabetes care")
        db.add(mum)
        db.flush()
    ravi = _member(db, mum.id, "Ravi", "Son")
    priya = _member(db, mum.id, "Priya", "Daughter")
    ananya = _member(db, mum.id, "Ananya", "Daughter")

    # Offsets are real instants from UTC now (stored as timestamptz, shown in
    # the recipient's timezone). The mix below always yields overdue/due/done.
    now = datetime.now(timezone.utc)
    specs = [
        # title, task_type, due offset, status, who, assignee, description
        ("Morning BP tablet", "medication", timedelta(hours=-3), "pending", None, ravi, "With breakfast"),
        ("Morning check-in call", "checkin", timedelta(hours=-4), "completed", ravi, priya, "Ask about sleep + appetite"),
        ("Doctor appointment — Dr. Rao", "appointment", timedelta(hours=+2), "pending", None, priya, "Carry last BP readings"),
        ("Evening BP tablet", "medication", timedelta(hours=+4), "pending", None, ananya, "8 pm with dinner"),
        ("Refill prescription", "general", timedelta(hours=+6), "pending", None, ravi, "Pharmacy closes 9 pm"),
        ("Afternoon walk", "general", timedelta(hours=-6), "completed", ananya, ananya, "10 minutes in the park"),
    ]
    created = 0
    for title, ttype, off, status, who, assignee, desc in specs:
        due = now + off
        # Strictly idempotent: one demo task per title. Re-seeding never
        # duplicates; /seed/reset deletes first when a refresh is wanted.
        exists = db.scalar(
            select(CareTask).where(
                CareTask.care_recipient_id == mum.id,
                CareTask.title == title,
            )
        )
        if exists:
            continue
        db.add(
            CareTask(
                care_recipient_id=mum.id,
                title=title,
                description=desc,
                task_type=ttype,
                due_at=due,
                status=status,
                priority="high" if "BP tablet" in title else "normal",
                assigned_member_id=assignee.id if assignee else None,
                completed_by_member_id=who.id if who else None,
                completed_at=(due + timedelta(minutes=20)) if who else None,
            )
        )
        created += 1
    db.commit()
    return {"recipient": mum.name, "created_tasks": created}


def reset_demo(db: Session) -> dict:
    """Delete demo tasks (demo recipients/members are kept)."""
    demo_tasks = db.scalars(
        select(CareTask).join(CareRecipient).where(CareRecipient.name == "Mum")
    ).all()
    n = len(demo_tasks)
    for t in demo_tasks:
        db.delete(t)
    db.commit()
    out = seed_demo(db)
    out["deleted_tasks"] = n
    return out

"""Demo seed: one recipient, two members, a few tasks across buckets."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from .models import CareRecipient, CareTask, FamilyMember


def seed_demo(db: Session) -> None:
    if db.query(CareRecipient).count():
        return
    mum = CareRecipient(name="Mum", notes="BP + diabetes care")
    db.add(mum)
    db.flush()
    ravi = FamilyMember(name="Ravi", relation="Son")
    priya = FamilyMember(name="Priya", relation="Daughter")
    db.add_all([ravi, priya])
    db.flush()
    now = datetime.now(timezone.utc)
    tasks = [
        # Overdue (morning, still pending)
        ("Morning BP tablet", "medicine", now - timedelta(hours=3), "pending", None, None),
        # Due later today
        ("Evening BP tablet (8 pm)", "medicine", now + timedelta(hours=3), "pending", None, None),
        ("Doctor appointment — Dr. Rao", "appointment", now + timedelta(hours=5), "pending", None, None),
        # Done this morning by Ravi
        ("Morning check-in call", "checkin", now - timedelta(hours=4), "done", ravi, now - timedelta(hours=4, minutes=-20)),
    ]
    for title, cat, due, status, who, done_at in tasks:
        db.add(
            CareTask(
                title=title,
                category=cat,
                due_at=due,
                status=status,
                recipient_id=mum.id,
                completed_by_id=who.id if who else None,
                completed_at=done_at,
            )
        )
    db.commit()

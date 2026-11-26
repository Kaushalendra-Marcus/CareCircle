"""Shared "today" grouping logic (also used by the assistant)."""
from datetime import datetime, timezone


def task_to_dict(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "category": t.category,
        "status": t.status,
        "due_at": t.due_at,
        "notes": t.notes or "",
        "recipient_id": t.recipient_id,
        "completed_by_id": t.completed_by_id,
        "completed_by_name": t.completed_by.name if t.completed_by else None,
        "completed_at": t.completed_at,
        "version": t.version,
    }


def group_today(tasks, now: datetime | None = None) -> dict:
    """Split tasks into overdue / due / done buckets.

    - done: status == "done" and completed today (UTC).
    - overdue: still pending and due_at is in the past.
    - due: still pending and due_at is now or later (rest of today+future).
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.date()
    overdue, due, done = [], [], []
    for t in tasks:
        d = task_to_dict(t)
        due_at = t.due_at
        if due_at is not None and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
            d["due_at"] = due_at
        done_on = t.completed_at or t.due_at
        if done_on is not None and done_on.tzinfo is None:
            done_on = done_on.replace(tzinfo=timezone.utc)
        if t.status == "done":
            if done_on is not None and done_on.date() == today:
                done.append(d)
            else:
                # Done on another day: not part of "today".
                continue
        elif due_at is not None and due_at < now:
            overdue.append(d)
        else:
            due.append(d)
    overdue.sort(key=lambda x: x["due_at"])
    due.sort(key=lambda x: x["due_at"])
    done.sort(key=lambda x: x["due_at"])
    return {
        "date": today.isoformat(),
        "overdue": overdue,
        "due": due,
        "done": done,
        "counts": {
            "overdue": len(overdue),
            "due": len(due),
            "done": len(done),
            "total": len(overdue) + len(due) + len(done),
        },
    }

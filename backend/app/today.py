"""Today grouping in the care recipient's timezone.

Rules (documented assumptions):
- completed = status "completed" AND completed today (recipient-local date).
  A task finished late still shows as completed, never as overdue.
- overdue = status "pending" AND due_at is in the past (includes tasks due
  on earlier days — they stay visible until done or cancelled).
- due = status "pending" AND due_at is now or later.
- cancelled tasks never appear on the dashboard.
- All comparisons use timezone-aware datetimes; naive values are assumed UTC.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def task_to_dict(t) -> dict:
    return {
        "id": t.id,
        "care_recipient_id": t.care_recipient_id,
        "title": t.title,
        "description": t.description or "",
        "task_type": t.task_type,
        "due_at": _aware(t.due_at),
        "status": t.status,
        "priority": t.priority or "normal",
        "assigned_member_id": t.assigned_member_id,
        "assigned_member_name": t.assigned_member.name if t.assigned_member else None,
        "completed_by_member_id": t.completed_by_member_id,
        "completed_by_name": t.completed_by.name if t.completed_by else None,
        "completed_at": _aware(t.completed_at),
        "version": t.version,
    }


def group_today(tasks, now: datetime | None = None, tz: str = "UTC") -> dict:
    zone = ZoneInfo(tz)
    now = _aware(now) or datetime.now(timezone.utc)
    local_now = now.astimezone(zone)
    today = local_now.date()
    overdue, due, done = [], [], []
    for t in tasks:
        if t.status == "cancelled":
            continue
        d = task_to_dict(t)
        if t.status == "completed":
            done_on = _aware(t.completed_at) or _aware(t.due_at)
            if done_on is not None and done_on.astimezone(zone).date() == today:
                done.append(d)
            continue
        due_at = _aware(t.due_at)
        if due_at is not None and due_at < now:
            overdue.append(d)
        else:
            due.append(d)
    overdue.sort(key=lambda x: x["due_at"] or now)
    due.sort(key=lambda x: x["due_at"] or now)
    done.sort(key=lambda x: x["completed_at"] or x["due_at"] or now, reverse=True)
    return {
        "date": today.isoformat(),
        "overdue": overdue,
        "due": due,
        "done": done,
        "summary": {
            "total": len(overdue) + len(due) + len(done),
            "completed": len(done),
            "pending": len(overdue) + len(due),
            "overdue": len(overdue),
        },
    }

"""Grounded template assistant: answers ONLY from today's real task data.

Safety rules enforced here and in the system prompt for the LLM path:
- Never invent completions, family members, or medicines taken.
- Say plainly when information is missing.
- No diagnoses, dosage advice, or treatment recommendations.
"""
from datetime import timezone
from zoneinfo import ZoneInfo


def fmt_time(dt, tz: str) -> str:
    zone = ZoneInfo(tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.astimezone(zone).strftime("%-I:%M %p")
    return s.replace("AM", "am").replace("PM", "pm")


def describe_task(d: dict, tz: str) -> str:
    who = f" (done by {d['completed_by_name']})" if d.get("completed_by_name") else ""
    return f"{d['title']} at {fmt_time(d['due_at'], tz)}{who}"


def build_context(grouped: dict, recipient_name: str, members: list[dict]) -> str:
    fam = ", ".join(
        f"{m['name']} ({m['relationship']})" if m.get("relationship") else m["name"]
        for m in members
    )
    lines = [f"date={grouped['date']}", f"recipient={recipient_name}",
             f"family={fam if fam else 'none listed'}"]
    for bucket in ("overdue", "due", "done"):
        for t in grouped[bucket]:
            lines.append(
                f"{bucket}|{t['title']}|{t['task_type']}|due={t['due_at']}|"
                f"assigned={t.get('assigned_member_name') or '-'}|"
                f"by={t.get('completed_by_name') or '-'}"
            )
    return "\n".join(lines)


MEDICAL_WORDS = ("dose", "dosage", "diagnos", "treat", "prescrib", "side effect", "should i take")


def template_answer(question: str, grouped: dict, name: str, tz: str, members: list[dict]) -> str:
    q = question.strip().lower()
    overdue, due, done = grouped["overdue"], grouped["due"], grouped["done"]

    if any(w in q for w in MEDICAL_WORDS):
        return (
            "I can't give medical advice — please ask the doctor or pharmacist.\n"
            "I can tell you what is scheduled and what the family has recorded as done."
        )
    # Family roster with each member's tasks, in list form.
    if any(w in q for w in ("member", "family members", "everyone", "each person", "each of")):
        return member_task_list(grouped, name, tz, members)
    # Person-specific: "did Ravi ...", medicine questions.
    if "who" in q or "did " in q or "morning medicine" in q or "medication" in q or "tablet" in q or "medicine" in q:
        meds_done = [t for t in done if t["task_type"] == "medication"]
        meds_open = [t for t in overdue + due if t["task_type"] == "medication"]
        if "morning" in q:
            meds_done = [t for t in meds_done if _hour(t, tz) < 12]
            meds_open = [t for t in meds_open if _hour(t, tz) < 12]
        bits = []
        for t in meds_done:
            by = f" by {t['completed_by_name']}" if t.get("completed_by_name") else ""
            bits.append(f"• Yes — {t['title']}{by}")
        for t in meds_open:
            bits.append(f"• Not yet — {t['title']} (due {fmt_time(t['due_at'], tz)}) is still pending")
        if bits:
            return f"For {name}'s medicine:\n" + "\n".join(bits)
        if not done:
            return f"No one has recorded anything as done for {name} today yet."
        items = "; ".join(describe_task(t, tz) for t in done)
        return f"Today for {name}: {items}."
    if "overdue" in q or "missed" in q or "late" in q:
        if not overdue:
            return f"Nothing is overdue for {name}. All good."
        return f"Overdue for {name} — please do these first:\n{_bullets(overdue, tz)}"
    if "evening" in q:
        ev = [t for t in due + overdue if _hour(t, tz) >= 17]
        if not ev:
            return f"Nothing is scheduled for {name} this evening."
        return f"This evening for {name}:\n{_bullets(ev, tz)}"
    if "morning" in q:
        mo = [t for t in due + overdue + done if _hour(t, tz) < 12]
        if not mo:
            return f"Nothing is recorded for {name} this morning."
        return f"This morning for {name}:\n{_bullets(mo, tz)}"
    if any(w in q for w in ("pending", "left", "remaining", "still", "to do", "todo")):
        if not overdue and not due:
            return f"Nothing is pending for {name} — everything today is done."
        parts = [f"Still to do for {name}:"]
        if overdue:
            parts.append(f"\nOverdue ({len(overdue)}):\n{_bullets(overdue, tz)}")
        if due:
            parts.append(f"\nDue ({len(due)}):\n{_bullets(due, tz)}")
        return "\n".join(parts)
    # Default: full summary.
    if not (overdue or due or done):
        return f"No tasks are scheduled for {name} today."
    parts = [f"Here's {name}'s day:"]
    if overdue:
        parts.append(f"\nOverdue ({len(overdue)}) — do first:\n{_bullets(overdue, tz)}")
    if due:
        parts.append(f"\nStill due ({len(due)}):\n{_bullets(due, tz)}")
    if done:
        parts.append(f"\nDone ({len(done)}):\n{_bullets(done, tz)}\nNice work.")
    return "\n".join(parts)


def member_task_list(grouped: dict, name: str, tz: str, members: list[dict]) -> str:
    """One list entry per family member: done + assigned/pending tasks."""
    if not members:
        return f"No family members are listed for {name} yet."
    all_tasks = grouped["overdue"] + grouped["due"] + grouped["done"]
    lines = [f"Family caring for {name}:"]
    for m in members:
        who = m["name"]
        rel = f" ({m['relationship']})" if m.get("relationship") else ""
        done = [t for t in grouped["done"] if t.get("completed_by_name") == who]
        open_ = [
            t for t in grouped["overdue"] + grouped["due"]
            if t.get("assigned_member_name") == who
        ]
        lines.append(f"\n{who}{rel}:")
        if done:
            lines.append("Done:")
            lines.extend(f"• {describe_task(t, tz)}" for t in done)
        if open_:
            lines.append("Still to do:")
            lines.extend(
                f"• {t['title']} (due {fmt_time(t['due_at'], tz)})" for t in open_
            )
        if not done and not open_:
            lines.append("• No tasks recorded today.")
    unassigned = [
        t for t in grouped["overdue"] + grouped["due"]
        if not t.get("assigned_member_name")
    ]
    if unassigned:
        lines.append("\nUnassigned:")
        lines.extend(f"• {t['title']} (due {fmt_time(t['due_at'], tz)})" for t in unassigned)
    return "\n".join(lines)


def _bullets(tasks: list[dict], tz: str) -> str:
    return "\n".join(f"• {describe_task(t, tz)}" for t in tasks)


def _hour(d: dict, tz: str) -> int:
    dt = d["due_at"]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz)).hour


SYSTEM_PROMPT = (
    "You are a calm family care assistant. Answer in 2-3 short sentences, "
    "using ONLY the task context provided. The context labels each task as "
    "overdue (past its due time), due (still upcoming), or done — keep these "
    "categories strictly separate and never call a due task overdue. Never "
    "invent completions, people, or medicines taken. If the answer is not in "
    "the context, say you don't see it recorded. Never give diagnoses, "
    "dosage advice, or treatment recommendations; suggest asking the doctor "
    "instead."
)

"""Template summary builder for the 'Ask about today' assistant.

If GROQ_API_KEY or GEMINI_API_KEY is set, main.py tries that model first;
otherwise (and in tests) this template answer is used. Streaming is done
word-by-word as SSE either way, so the UI behaviour is identical.
"""
from datetime import timezone


def fmt_time(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%-I:%M %p").replace("AM", "am").replace("PM", "pm")


def describe_task(d: dict) -> str:
    who = f" (done by {d['completed_by_name']})" if d.get("completed_by_name") else ""
    return f"{d['title']} at {fmt_time(d['due_at'])}{who}"


def build_summary(grouped: dict, recipient_name: str = "Mum") -> str:
    overdue = grouped["overdue"]
    due = grouped["due"]
    done = grouped["done"]
    if not (overdue or due or done):
        return f"No tasks scheduled for {recipient_name} today. Enjoy the calm day!"
    parts: list[str] = []
    if overdue:
        items = "; ".join(describe_task(t) for t in overdue)
        parts.append(
            f"{len(overdue)} overdue: {items}. Please do these first."
        )
    if due:
        items = "; ".join(describe_task(t) for t in due)
        parts.append(f"{len(due)} still due today: {items}.")
    if done:
        items = "; ".join(describe_task(t) for t in done)
        parts.append(f"{len(done)} done: {items}. Nice work!")
    return f"Here's {recipient_name}'s day: " + " ".join(parts)


def build_context(grouped: dict) -> str:
    lines = [f"date={grouped['date']}"]
    for bucket in ("overdue", "due", "done"):
        for t in grouped[bucket]:
            lines.append(
                f"{bucket}|{t['title']}|{t['category']}|due={t['due_at']}|"
                f"by={t.get('completed_by_name') or '-'}"
            )
    return "\n".join(lines)

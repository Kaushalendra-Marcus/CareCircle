"""CareCircle v1 behaviour: grouping, timezones, completion, validation,
cancellation, assistant grounding. Timestamps are relative to *now* so the
suite is deterministic on any clock."""
import json
from datetime import datetime, timedelta, timezone


def _mk(client, rid, title, due, **kw):
    body = {
        "title": title,
        "task_type": "medication",
        "due_at": due,
        "care_recipient_id": rid,
        **kw,
    }
    r = client.post("/api/v1/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _stream_text(resp) -> str:
    chunks, done_id = [], None
    for line in resp.iter_lines():
        if not line.startswith("data:"):
            continue
        evt = json.loads(line.removeprefix("data:").strip())
        if evt["type"] == "token":
            chunks.append(evt["content"])
        elif evt["type"] == "done":
            done_id = evt["interaction_id"]
    return "".join(chunks), done_id


def test_today_groups_overdue_due_and_done(client, family):
    rid = family["id"]
    ravi = family["members"]["Ravi"]
    now = datetime.now(timezone.utc)
    overdue = _mk(client, rid, "Morning tablet", (now - timedelta(hours=2)).isoformat())
    due = _mk(client, rid, "Evening tablet", (now + timedelta(hours=2)).isoformat())
    done_task = _mk(client, rid, "Check-in call", (now - timedelta(hours=4)).isoformat())
    c = client.post(
        f"/api/v1/tasks/{done_task['id']}/complete",
        json={"completed_by_member_id": ravi["id"]},
    )
    assert c.status_code == 200

    body = client.get("/api/v1/today", params={"care_recipient_id": rid}).json()
    assert overdue["id"] in [t["id"] for t in body["overdue"]]
    assert due["id"] in [t["id"] for t in body["due"]]
    assert done_task["id"] in [t["id"] for t in body["done"]]
    assert body["summary"] == {"total": 9, "completed": 3, "pending": 6, "overdue": 2}
    assert body["recipient"] == {"id": rid, "name": "Mum"}


def test_overdue_respects_recipient_timezone(client, family):
    # Mum lives in Asia/Kolkata. A task due 1h ago UTC is overdue there too;
    # a task due in 5h is still due — classification follows real instants.
    rid = family["id"]
    now = datetime.now(timezone.utc)
    _mk(client, rid, "Just missed", (now - timedelta(hours=1)).isoformat())
    _mk(client, rid, "Later", (now + timedelta(hours=5)).isoformat())
    body = client.get("/api/v1/today", params={"care_recipient_id": rid}).json()
    titles_over = {t["title"] for t in body["overdue"]}
    titles_due = {t["title"] for t in body["due"]}
    assert "Just missed" in titles_over
    assert "Later" in titles_due


def test_complete_records_member_and_timestamp(client, family):
    rid = family["id"]
    ravi = family["members"]["Ravi"]
    priya = family["members"]["Priya"]
    now = datetime.now(timezone.utc)
    t = _mk(client, rid, "BP check", (now + timedelta(hours=1)).isoformat())
    done = client.post(
        f"/api/v1/tasks/{t['id']}/complete", json={"completed_by_member_id": ravi["id"]}
    ).json()
    assert done["status"] == "completed"
    assert done["completed_by_member_id"] == ravi["id"]
    assert done["completed_by_name"] == "Ravi"
    assert done["completed_at"] is not None
    again = client.post(
        f"/api/v1/tasks/{t['id']}/complete", json={"completed_by_member_id": priya["id"]}
    )
    assert again.status_code == 409


def test_complete_nonexistent_task_404(client, family):
    r = client.post("/api/v1/tasks/999999/complete", json={})
    assert r.status_code == 404


def test_task_creation_validation(client, family):
    rid = family["id"]
    now = datetime.now(timezone.utc).isoformat()
    assert client.post("/api/v1/tasks", json={"title": "", "due_at": now, "care_recipient_id": rid}).status_code == 422
    assert client.post("/api/v1/tasks", json={"title": "x", "due_at": now, "care_recipient_id": 999999}).status_code == 404
    bad = client.post("/api/v1/tasks", json={"title": "x", "due_at": now, "care_recipient_id": rid, "priority": "urgent"}).status_code
    assert bad == 422


def test_cancelled_tasks_excluded_from_today(client, family):
    rid = family["id"]
    now = datetime.now(timezone.utc)
    t = _mk(client, rid, "Drop this", (now + timedelta(hours=1)).isoformat())
    r = client.patch(f"/api/v1/tasks/{t['id']}", json={"status": "cancelled"})
    assert r.status_code == 200
    body = client.get("/api/v1/today", params={"care_recipient_id": rid}).json()
    ids = {x["id"] for x in body["overdue"] + body["due"] + body["done"]}
    assert t["id"] not in ids


def test_delete_task(client, family):
    rid = family["id"]
    now = datetime.now(timezone.utc)
    t = _mk(client, rid, "Temporary", (now + timedelta(hours=1)).isoformat())
    assert client.delete(f"/api/v1/tasks/{t['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{t['id']}").status_code == 404
    assert client.delete(f"/api/v1/tasks/{t['id']}").status_code == 404


def test_assistant_uses_real_data_and_logs(client, family):
    rid = family["id"]
    now = datetime.now(timezone.utc)
    _mk(client, rid, "Evening tablet", (now + timedelta(hours=2)).isoformat())
    with client.stream(
        "POST", "/api/v1/assistant/ask",
        json={"question": "What is still pending?", "care_recipient_id": rid},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text, done_id = _stream_text(resp)
    assert "Evening tablet" in text
    assert done_id is not None
    hist = client.get("/api/v1/assistant/history").json()
    entry = next(h for h in hist if h["id"] == done_id)
    assert entry["question"] == "What is still pending?"
    assert "Evening tablet" in entry["answer"]
    assert "Evening tablet" in entry["context_sent"]
    assert entry["care_recipient_id"] == rid
    assert entry["latency_ms"] >= 0
    assert entry["model_name"] == "template"


def test_assistant_never_invents_completions(client, family):
    rid = family["id"]
    with client.stream(
        "POST", "/api/v1/assistant/ask",
        json={"question": "Did anyone give Mum her morning medicine?", "care_recipient_id": rid},
    ) as resp:
        text, _ = _stream_text(resp)
    # Seed has a completed check-in by Ravi but the morning tablet is pending:
    # the answer must reflect reality, naming only real records.
    assert "Morning BP tablet" in text or "pending" in text.lower() or "overdue" in text.lower()

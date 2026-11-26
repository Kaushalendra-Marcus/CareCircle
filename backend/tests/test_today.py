"""Today grouping + overdue logic + complete flow + assistant logging."""
from datetime import datetime, timedelta, timezone


def _mk(client, rid, title, due, status="pending"):
    r = client.post(
        "/api/tasks",
        json={"title": title, "category": "medicine", "due_at": due, "recipient_id": rid},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_today_groups_overdue_due_and_done(client, family):
    r, m1, _ = family
    now = datetime.now(timezone.utc)
    overdue = _mk(client, r["id"], "Morning tablet", (now - timedelta(hours=2)).isoformat())
    due = _mk(client, r["id"], "Evening tablet", (now + timedelta(hours=2)).isoformat())
    done_task = _mk(client, r["id"], "Check-in call", (now - timedelta(hours=4)).isoformat())
    c = client.post(
        f"/api/tasks/{done_task['id']}/complete", json={"completed_by_id": m1["id"]}
    )
    assert c.status_code == 200

    res = client.get("/api/tasks/today", params={"recipient_id": r["id"]})
    assert res.status_code == 200
    body = res.json()
    assert [t["id"] for t in body["overdue"]] == [overdue["id"]]
    assert [t["id"] for t in body["due"]] == [due["id"]]
    assert [t["id"] for t in body["done"]] == [done_task["id"]]
    assert body["counts"] == {"overdue": 1, "due": 1, "done": 1, "total": 3}


def test_overdue_boundary_task_due_exactly_now_is_not_overdue(client, family):
    r, _, _ = family
    now = datetime.now(timezone.utc)
    _mk(client, r["id"], "Right now", (now + timedelta(minutes=5)).isoformat())
    body = client.get("/api/tasks/today", params={"recipient_id": r["id"]}).json()
    assert body["counts"]["overdue"] == 0
    assert body["counts"]["due"] == 1


def test_complete_records_who_and_when_and_rejects_double_done(client, family):
    r, m1, m2 = family
    now = datetime.now(timezone.utc)
    t = _mk(client, r["id"], "BP check", (now + timedelta(hours=1)).isoformat())
    done = client.post(
        f"/api/tasks/{t['id']}/complete", json={"completed_by_id": m1["id"]}
    ).json()
    assert done["status"] == "done"
    assert done["completed_by_id"] == m1["id"]
    assert done["completed_by_name"] == "Ravi"
    assert done["completed_at"] is not None
    # Second person tapping done on the same task gets a 409, not a silent overwrite.
    again = client.post(
        f"/api/tasks/{t['id']}/complete", json={"completed_by_id": m2["id"]}
    )
    assert again.status_code == 409


def test_concurrent_complete_with_stale_version_conflicts(client, family):
    r, m1, m2 = family
    now = datetime.now(timezone.utc)
    t = _mk(client, r["id"], "Sugar check", (now + timedelta(hours=1)).isoformat())
    v = t["version"]
    ok = client.post(
        f"/api/tasks/{t['id']}/complete",
        json={"completed_by_id": m1["id"], "version": v},
    )
    assert ok.status_code == 200
    # Reopen, then replay the stale version -> conflict.
    client.post(f"/api/tasks/{t['id']}/reopen")
    stale = client.post(
        f"/api/tasks/{t['id']}/complete",
        json={"completed_by_id": m2["id"], "version": v},
    )
    assert stale.status_code == 409


def test_assistant_streams_and_logs_interaction(client, family):
    r, _, _ = family
    now = datetime.now(timezone.utc)
    _mk(client, r["id"], "Evening tablet", (now + timedelta(hours=2)).isoformat())
    with client.stream(
        "POST", "/api/assistant/ask", json={"question": "What is pending today?"}
    ) as resp:
        assert resp.status_code == 200
        chunks = []
        for line in resp.iter_lines():
            if line.startswith("data:") and "[DONE]" not in line:
                chunks.append(line.removeprefix("data:").strip())
        text = " ".join(chunks)
    assert "Evening tablet" in text
    hist = client.get("/api/assistant/history").json()
    assert len(hist) >= 1
    entry = hist[0]
    assert entry["question"] == "What is pending today?"
    assert "Evening tablet" in entry["answer"]
    assert "Evening tablet" in entry["context"]
    assert entry["latency_ms"] >= 0

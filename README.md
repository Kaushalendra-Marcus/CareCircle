# CareCircle Lite

One shared place for a family coordinating an aging parent's care:
what's overdue, what's due today, what's done — plus an "Ask about today"
assistant that streams its answer.

## Run it (one command)

```bash
docker compose up --build
```

- UI → http://localhost:5173
- API → http://localhost:8000 (docs at `/docs`)
- Postgres → localhost:5432 (user/password/db: `carecircle`)

On first start the API auto-seeds a demo family (Mum + Ravi + Priya with a
few tasks across overdue / due / done). If you start with an empty database
later, tap **"Load demo tasks"** in the UI or `POST /api/seed`.

### Run without Docker (dev)

```bash
# backend (needs a local Postgres, or set DATABASE_URL to sqlite for a quick try)
cd backend && pip install -r requirements.txt && SEED_DEMO=true uvicorn app.main:app --reload

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173, /api proxied to :8000
```

### Run backend tests

```bash
cd backend && pip install -r requirements.txt && python -m pytest -q
```

## What it does

| Requirement | Where |
|---|---|
| Care recipient, family members, tasks with due time + status; create / list / update / complete; `GET /api/tasks/today` → done / due / overdue | `backend/app/routers/tasks.py`, `backend/app/routers/people.py`, `backend/app/today.py` |
| "Today" screen grouped overdue / due / done; add task; one-tap mark-done recording who + when; big-text phone-first UI | `frontend/src/App.tsx`, `frontend/src/styles.css` |
| "Ask about today" box; backend streams answer via SSE | `backend/app/routers/assistant.py`, `api.ask()` + Ask section in `App.tsx` |
| Every question + context + answer + latency stored in `ai_interaction_logs` (`GET /api/assistant/history`) | `backend/app/models.py` (`AiInteractionLog`) |
| `docker compose up` starts db + api + ui | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| 5 pytest tests (today grouping, overdue boundary, complete attribution, double-done + stale-version 409s, assistant stream + log) | `backend/tests/` |

**Nice-to-have picked:** concurrent "mark done" is safe — tasks carry a
`version` number; completing/updating with a stale version returns `409`
instead of silently overwriting, and the UI refreshes and tells the user.
The member picker doubles as the lightweight "who did what" identity (no
passwords — deliberate for a 4–6h scope).

## Design choices & assumptions

- **Overdue = pending + `due_at` in the past (server UTC).** Done = completed
  today. A task done on another day doesn't appear under "today". All times
  stored as timestamptz; naive inputs are assumed UTC.
- **Assistant = template by default, LLM-optional.** `build_summary()` turns
  the day's buckets into "1 overdue… 2 still due… 1 done…" prose naming who
  did what. If `GROQ_API_KEY` (or `GEMINI_API_KEY`) is set, the backend calls
  that model and streams its answer instead — the SSE shape and logging are
  identical either way. Streaming is word-by-word SSE; the log row is written
  when the stream finishes.
- **No migrations (intentional):** `create_all` on startup. For a pilot with
  one family this removes a whole failure class; Alembic would be step one
  with real users.
- **No auth:** the member picker ("Who is doing it?") records attribution
  without passwords — right tradeoff for tired caregivers in a pilot, and
  stated in the brief as optional.
- **Frontend has no UI framework** — hand-rolled CSS in a mint care-app
  style: greeting + "Today's Plan" header, Daily Progress card, medicine
  cards with Taken / Later (+2h snooze) pills, adherence ring on the Meds
  tab, activity timeline, family attribution, bottom tab bar (Today / Meds /
  Activity / Family) and a ＋ bottom-sheet to add tasks. 17px+ type,
  nothing behind menus.

## What I'd do next (with more time)

1. Login (passkeys/magic link) + per-family scoping so many families can use it.
2. Alembic migrations + a nightly "carry overdue forward" job.
3. Voice input for "Ask about today" via Web Speech API.
4. Push reminders (e.g. WhatsApp) for tasks overdue > 1h.

## AI tools used

- **Muse Spark (OpenCode)** — scaffolded the repo, wrote the FastAPI routers /
  React UI / tests from my direction, and helped debug the SQLite-naive-datetime
  test failure. I reviewed and can explain every file; the grouping rule,
  concurrency design and template wording are my own decisions.

## Time spent

~5 hours (backend ~2h, frontend ~1.5h, streaming+logs+tests ~1h, docker/README ~0.5h).

## Credits

- Icons: Lucide (`lucide-static`, ISC license), inlined in `frontend/src/icons.tsx`.
- Photography: Unsplash License (free to use) — caregiving images in
  `frontend/public/images/`.

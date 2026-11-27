# CareCircle Lite

**Care is easier when everyone is in the loop.**

## 1. Problem statement

Families coordinating an ageing parent's care do it over WhatsApp and phone
calls: who gave the evening medicine, whether the appointment is booked, what
changed today. Information scatters, doses get missed or doubled, and nobody
has one reliable picture of the day.

## 2. Solution

CareCircle Lite gives one family one shared place: today's tasks grouped as
**overdue / due / done**, one-tap completion recording **who + when**, and an
**"Ask about today"** assistant that streams answers grounded strictly in the
day's real records. Runs with `docker compose up --build`.

## 3. Features

- Today dashboard: overdue / due / completed groups with counts, progress,
  empty states, instant updates, relative times, assignee + completion attribution
- Task CRUD: validated add/edit form (bottom sheet), two-tap delete, snooze (+2h)
- One-tap Taken with member picker; stale-version and double-complete return 409
- Assistant: real SSE streaming (`token`/`done`/`error` JSON events), prompt
  chips, stop button, grounded template fallback, optional Groq LLM
- Every assistant interaction logged (question, context, answer, latency, model)
- Meds tab with adherence ring, Activity timeline, Family tab with per-member counts
- Warm Aurviz-inspired UI: Inter, dark pill CTAs, Lucide SVG icons, real photography

## 4. Screenshots

Run it and open http://localhost:5173 — Today (hero + plan), Meds
(adherence), Activity (timeline), Family (attribution).

## 5. Technology stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + TypeScript + Vite, hand-rolled CSS (Aurviz theme), Lucide SVGs, custom API layer |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, psycopg 3 |
| DB | PostgreSQL 16 |
| Streaming | SSE (`text/event-stream`), real server chunks |
| LLM | Groq (`openai/gpt-oss-20b` default) or grounded template fallback |
| Tests | pytest + FastAPI TestClient (SQLite) |
| Infra | Docker Compose (db + api + web), persistent volume, healthchecks |

**Deliberate deviations from a "standard" stack:** no Tailwind/shadcn (the
custom CSS already delivers the required warm theme with zero build weight);
no TanStack Query/React Hook Form/Zod (the app's data needs fit a small typed
`api.ts` + controlled form with validation); no React Router (4 tabs, no deep
links needed); no separate completion-history table (completion lives on the
task — right scope for an MVP).

## 6. Architecture overview

```
browser ──▶ nginx (web:80→5173) ──/api/*──▶ FastAPI (api:8000) ──▶ Postgres (db:5432)
                                            │  ├─ /api/v1/tasks, /today, /recipients, /family-members
                                            │  ├─ /api/v1/assistant/ask (SSE) + /history
                                            │  └─ entrypoint: wait-db → alembic upgrade → seed → uvicorn
```

## 7. API endpoints (`/api/v1`)

- `GET /health` · `POST /seed` · `POST /seed/reset` (reset demo data)
- `GET /recipients`, `GET /recipients/{id}`
- `GET /family-members[?care_recipient_id]`, `GET /family-members/{id}`, `POST /family-members`
- `POST /tasks` (201; 404 unknown recipient/assignee; 422 bad priority/title), `GET /tasks[?status&care_recipient_id]`, `GET /tasks/{id}`, `PATCH /tasks/{id}` (409 stale version), `DELETE /tasks/{id}` (204), `POST /tasks/{id}/complete` (409 already done), `POST /tasks/{id}/reopen`
- `GET /today?care_recipient_id=` → `{date, recipient, summary{total,completed,pending,overdue}, overdue, due, done}`
- `POST /assistant/ask` (SSE) · `GET /assistant/history`
- Interactive docs: http://localhost:8000/docs

## 8. Database schema overview

- `care_recipients(id, name, date_of_birth, timezone, notes, …)` — timezone drives "today" (default Asia/Kolkata)
- `family_members(id, care_recipient_id→recipients, name, relationship, avatar_url, …)`
- `care_tasks(id, care_recipient_id→recipients, title, description, task_type, due_at TIMESTAMPTZ, status[pending|completed|cancelled], priority, assigned_member_id→members, completed_by_member_id→members, completed_at, version, …)` — indexed on status, due_at
- `assistant_interactions(id, care_recipient_id, family_member_id, question, context_sent, answer, latency_ms, model_name, …)`

## 9. AI streaming architecture

`POST /assistant/ask` → gather today's tasks + recipient + members → build
text context → Groq if `GROQ_API_KEY` set else grounded template (intent
matching: pending/overdue/morning/evening/medicine/person + medical-advice
refusal) → `StreamingResponse` yields `data: {"type":"token",…}` per word
(~30ms), then persists the log row and yields `{"type":"done",
"interaction_id"}`. Client parses JSON events progressively (no fake typing)
and supports AbortController stop; disconnects are still logged as interrupted.

## 10. AI logging implementation

One `assistant_interactions` row per stream: exact question, exact context
sent, full answer, `latency_ms` (request start → generation complete), model
name (`template` or Groq model), recipient/member IDs. Never logs API keys.
`GET /assistant/history` returns the latest 50.

## 11. How to run with Docker Compose

```bash
docker compose up --build
```

- UI → http://localhost:5173 · API → http://localhost:8000 · DB → localhost:5432
- If port 5432 is taken: `DB_HOST_PORT=5433 docker compose up --build`
- Fresh boot auto-migrates (Alembic) and seeds the demo family.
- Stop: `docker compose down` (data persists in `pgdata`; `down -v` wipes it).

## 12. Environment variables

See `.env.example`. `DATABASE_URL`, `SEED_DEMO=true`, `DB_HOST_PORT=5432`,
optional `GROQ_API_KEY` + `GROQ_MODEL` (default `openai/gpt-oss-20b`).
Without a key the template assistant is used — still streamed, still logged.

## 13. How to run tests

```bash
cd backend && pip install -r requirements.txt && python -m pytest -q
```

9 tests, all deterministic (timestamps relative to now): today grouping +
summary, timezone overdue, completion attribution + double-done 409,
nonexistent-task 404, creation validation (3 cases), cancelled exclusion,
delete flow, assistant real-data + logging, no-invented-completions.
Migrations are verified separately against real Postgres (`alembic upgrade head`, twice for idempotence).

## 14. Seed data and reset commands

- Auto-seed on boot (`SEED_DEMO=true`): Mum (Asia/Kolkata) + Ravi/Priya/Ananya;
  6 tasks relative to now (mix of overdue/due/done with who+when). Idempotent.
- `POST /api/v1/seed` — top up demo data anytime.
- `POST /api/v1/seed/reset` — delete Mum's tasks and re-seed (documented reset).
- Fresh DB from scratch: `docker compose down -v && docker compose up --build`.

## 15. Design decisions

- **Overdue/due derived, never stored**; `cancelled` excluded everywhere.
- **Done = completed today (recipient-local date)** — a late finish still shows as completed, never overdue.
- **Recipient timezone** (Asia/Kolkata) defines "today"; naive datetimes assumed UTC.
- **Optimistic concurrency** (`version` → 409) instead of auth — right for a no-login family pilot.
- **No login**: member picker records attribution;signup friction would kill a tired-caregiver pilot.
- **Template assistant** grounded in SQL rows with intent matching + medical refusal; LLM is an upgrade path, not a dependency.
- **create_all + Alembic**: Alembic is the upgrade source of truth; `create_all` keeps `uvicorn app.main:app` runnable for local dev.

## 16. Trade-offs

- Custom CSS instead of Tailwind/shadcn; custom `api.ts` instead of TanStack Query; controlled form instead of RHF/Zod; tabs instead of Router — each cuts dependency weight with no UX loss at this scope.
- Latency includes stream pacing (~30ms/word), so it measures interaction time, not pure model time.
- Seed demo is one family; multi-tenancy needs auth + scoping (see §18).

## 17. Limitations

- Single family, no authentication/authorization.
- Template assistant handles common intents; unusual phrasings fall back to a full-day summary.
- No push reminders, no recurring-task engine (snooze only), no offline support.
- Times displayed in the browser's locale, not forced to recipient tz.

## 18. What I would build next

1. Login (passkeys/magic link) + per-family scoping.
2. Recurring schedules + push reminders (e.g. WhatsApp) for overdue > 1h.
3. Voice input for "Ask about today".
4. Alembic autogenerate in CI; nightly carry-forward of overdue.

## 19. AI tools used and what they helped with

- **Muse Spark (OpenCode agent)**: scaffolded repo/compose, drafted
  FastAPI routers + React UI + tests from my direction, debugged the
  SQLite-naive-datetime failure and the first-boot seed race (fixed by seeding
  in the container entrypoint as well as app lifespan). I reviewed, tested,
  and can explain every file; grouping rules, concurrency design, template
  wording, and theme extraction (docs + live CSS) are my decisions.

## 20. Credits & time

- Icons: Lucide (`lucide-static`, ISC). Photography: Unsplash License
  (pills, senior portrait) plus Flickr works used unmodified with credit —
  "A Caregiver Finds the Time" by fairfaxcounty (CC BY-ND), "Medical Care at
  the Aged Persons Center" by UN Women Gallery (CC BY-NC-ND), and a doctor
  consultation by ILO in Asia and the Pacific (CC BY-NC-ND) — all in
  `frontend/public/images/`.
- ~5h core build + theming iterations; compliance pass (v1 API, Alembic,
  timezone logic, JSON SSE, 9 tests, docs) on top.

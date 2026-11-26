"""Streaming 'Ask about today' assistant (SSE, JSON event protocol).

Protocol (text/event-stream, one JSON object per data line):
  data: {"type": "token", "content": "word "}
  data: {"type": "done", "interaction_id": 12}
  data: {"type": "error", "message": "..."}

Every interaction is persisted to assistant_interactions with the question,
the exact context sent, the full answer, latency and model name.
"""
import asyncio
import json
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..assistant_summary import SYSTEM_PROMPT, build_context, template_answer
from ..database import get_db
from ..models import AssistantInteraction, CareRecipient, CareTask, FamilyMember
from ..schemas import AskRequest, InteractionOut
from ..today import group_today

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _gather(db: Session, recipient_id: int | None):
    q = select(CareTask).options(
        joinedload(CareTask.completed_by), joinedload(CareTask.assigned_member)
    )
    if recipient_id is not None:
        q = q.where(CareTask.care_recipient_id == recipient_id)
    tasks = list(db.scalars(q).all())
    recipient = (
        db.get(CareRecipient, recipient_id)
        if recipient_id is not None
        else db.scalar(select(CareRecipient).order_by(CareRecipient.id))
    )
    name = recipient.name if recipient else "Mum"
    tz = (recipient.timezone if recipient else None) or "UTC"
    grouped = group_today(tasks, tz=tz)
    members = [m.name for m in db.scalars(select(FamilyMember).order_by(FamilyMember.id)).all()]
    context = build_context(grouped, name, members)
    return grouped, name, tz, context


def _groq_answer(question: str, context: str) -> str | None:
    """Call Groq if configured; None on any failure (caller falls back)."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}\nToday's tasks:\n{context}"},
            ],
            "max_tokens": 220,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    started = time.perf_counter()
    grouped, name, tz, context = _gather(db, payload.care_recipient_id)
    model = "template"
    try:
        llm = _groq_answer(payload.question, context)
        if llm:
            answer, model = llm, os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        else:
            answer = template_answer(payload.question, grouped, name, tz)
    except Exception:
        answer = template_answer(payload.question, grouped, name, tz)

    async def gen():
        try:
            for word in answer.split(" "):
                yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                await asyncio.sleep(0.03)
            latency_ms = int((time.perf_counter() - started) * 1000)
            row = AssistantInteraction(
                care_recipient_id=payload.care_recipient_id,
                family_member_id=payload.family_member_id,
                question=payload.question,
                context_sent=context,
                answer=answer,
                latency_ms=latency_ms,
                model_name=model,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            yield f"data: {json.dumps({'type': 'done', 'interaction_id': row.id})}\n\n"
        except asyncio.CancelledError:
            # Client disconnected mid-stream: still log what we produced.
            latency_ms = int((time.perf_counter() - started) * 1000)
            db.add(
                AssistantInteraction(
                    care_recipient_id=payload.care_recipient_id,
                    family_member_id=payload.family_member_id,
                    question=payload.question,
                    context_sent=context,
                    answer=answer + " [stream interrupted]",
                    latency_ms=latency_ms,
                    model_name=model,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
            raise
        except Exception as exc:  # never leave the client hanging
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:200]})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/history", response_model=list[InteractionOut])
def history(db: Session = Depends(get_db)):
    return (
        db.scalars(
            select(AssistantInteraction).order_by(AssistantInteraction.id.desc()).limit(50)
        ).all()
    )

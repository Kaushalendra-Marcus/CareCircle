"""Streaming 'Ask about today' assistant endpoint (SSE) + interaction logs."""
import asyncio
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..assistant_summary import build_context, build_summary
from ..database import get_db
from ..models import AiInteractionLog, CareRecipient, CareTask
from ..schemas import AiLogOut, AskRequest
from ..today import group_today

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _gather(db: Session, recipient_id: int | None):
    q = select(CareTask).options(joinedload(CareTask.completed_by))
    if recipient_id is not None:
        q = q.where(CareTask.recipient_id == recipient_id)
    tasks = list(db.scalars(q).all())
    name = "Mum"
    if recipient_id is not None:
        r = db.get(CareRecipient, recipient_id)
        if r:
            name = r.name
    else:
        first = db.scalar(select(CareRecipient).order_by(CareRecipient.id))
        if first:
            name = first.name
    return group_today(tasks), name


def _maybe_llm_answer(question: str, context: str) -> tuple[str | None, str]:
    """Try Groq/Gemini if keys are configured; else return (None, model)."""
    if os.getenv("GROQ_API_KEY"):
        try:
            import httpx

            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                json={
                    "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a family care assistant. Answer briefly (2-3 sentences) using only the provided task context.",
                        },
                        {
                            "role": "user",
                            "content": f"Question: {question}\nToday's tasks:\n{context}",
                        },
                    ],
                    "max_tokens": 200,
                },
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip(), "groq"
        except Exception:
            return None, "template"
    if os.getenv("GEMINI_API_KEY"):
        try:
            import httpx

            key = os.environ["GEMINI_API_KEY"]
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"You are a family care assistant. Answer briefly (2-3 sentences) using only this task context.\nQuestion: {question}\nTasks:\n{context}"
                                }
                            ]
                        }
                    ]
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            return (
                data["candidates"][0]["content"]["parts"][0]["text"].strip(),
                "gemini",
            )
        except Exception:
            return None, "template"
    return None, "template"


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    started = time.perf_counter()
    grouped, name = _gather(db, payload.recipient_id)
    context = build_context(grouped)
    llm_answer, model = _maybe_llm_answer(payload.question, context)
    answer = llm_answer or build_summary(grouped, name)
    if llm_answer is None:
        # Weave the actual question in lightly so it feels responsive.
        q = payload.question.strip().rstrip("?").lower()
        if any(w in q for w in ("pending", "left", "remaining", "still")) and not grouped["overdue"] and not grouped["due"]:
            answer = f"Nothing pending for {name} — everything today is done. {answer}"
        model = "template"

    async def gen():
        # Stream word-by-word so the UI can render progressively.
        for word in answer.split(" "):
            yield f"data: {word} \n\n"
            await asyncio.sleep(0.03)
        latency_ms = int((time.perf_counter() - started) * 1000)
        db.add(
            AiInteractionLog(
                question=payload.question,
                context=context,
                answer=answer,
                latency_ms=latency_ms,
                model=model,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/history", response_model=list[AiLogOut])
def history(db: Session = Depends(get_db)):
    return (
        db.scalars(
            select(AiInteractionLog).order_by(AiInteractionLog.id.desc()).limit(50)
        ).all()
    )

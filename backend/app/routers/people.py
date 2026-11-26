"""Recipients + family members routers (v1)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import CareRecipient, CareTask, FamilyMember
from ..schemas import MemberCreate, MemberOut, RecipientOut, TodayOut
from ..today import group_today

recipients = APIRouter(prefix="/api/v1/recipients", tags=["recipients"])
members = APIRouter(prefix="/api/v1/family-members", tags=["family-members"])
today_router = APIRouter(prefix="/api/v1/today", tags=["today"])


@recipients.get("", response_model=list[RecipientOut])
def list_recipients(db: Session = Depends(get_db)):
    return db.scalars(select(CareRecipient).order_by(CareRecipient.id)).all()


@recipients.get("/{recipient_id}", response_model=RecipientOut)
def get_recipient(recipient_id: int, db: Session = Depends(get_db)):
    r = db.get(CareRecipient, recipient_id)
    if not r:
        raise HTTPException(404, "care recipient not found")
    return r


@members.get("", response_model=list[MemberOut])
def list_members(
    care_recipient_id: int | None = None, db: Session = Depends(get_db)
):
    q = select(FamilyMember).order_by(FamilyMember.id)
    if care_recipient_id is not None:
        q = q.where(FamilyMember.care_recipient_id == care_recipient_id)
    return db.scalars(q).all()


@members.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: int, db: Session = Depends(get_db)):
    m = db.get(FamilyMember, member_id)
    if not m:
        raise HTTPException(404, "family member not found")
    return m


@members.post("", response_model=MemberOut, status_code=201)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    if payload.care_recipient_id is not None and not db.get(
        CareRecipient, payload.care_recipient_id
    ):
        raise HTTPException(404, "care recipient not found")
    m = FamilyMember(
        name=payload.name.strip(),
        relationship=payload.relationship or "",
        care_recipient_id=payload.care_recipient_id,
        avatar_url=payload.avatar_url,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@today_router.get("", response_model=TodayOut)
def today(care_recipient_id: int | None = None, db: Session = Depends(get_db)):
    recipient = None
    tz = "UTC"
    if care_recipient_id is not None:
        recipient = db.get(CareRecipient, care_recipient_id)
        if not recipient:
            raise HTTPException(404, "care recipient not found")
        tz = recipient.timezone or "UTC"
    else:
        recipient = db.scalar(select(CareRecipient).order_by(CareRecipient.id))
        if recipient:
            tz = recipient.timezone or "UTC"
    q = select(CareTask).options(
        joinedload(CareTask.completed_by), joinedload(CareTask.assigned_member)
    )
    if care_recipient_id is not None:
        q = q.where(CareTask.care_recipient_id == care_recipient_id)
    tasks = list(db.scalars(q).all())
    now = datetime.now(timezone.utc)
    grouped = group_today(tasks, now=now, tz=tz)
    return {
        "date": grouped["date"],
        "recipient": {"id": recipient.id, "name": recipient.name} if recipient else None,
        "summary": grouped["summary"],
        "overdue": grouped["overdue"],
        "due": grouped["due"],
        "done": grouped["done"],
    }

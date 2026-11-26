"""Recipients + family members routers."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CareRecipient, FamilyMember
from ..schemas import MemberCreate, MemberOut, RecipientCreate, RecipientOut

recipients = APIRouter(prefix="/api/recipients", tags=["recipients"])
members = APIRouter(prefix="/api/members", tags=["members"])


@recipients.post("", response_model=RecipientOut, status_code=201)
def create_recipient(payload: RecipientCreate, db: Session = Depends(get_db)):
    r = CareRecipient(name=payload.name.strip(), notes=payload.notes or "")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@recipients.get("", response_model=list[RecipientOut])
def list_recipients(db: Session = Depends(get_db)):
    return db.scalars(select(CareRecipient).order_by(CareRecipient.id)).all()


@members.post("", response_model=MemberOut, status_code=201)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    m = FamilyMember(name=payload.name.strip(), relation=payload.relation or "")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@members.get("", response_model=list[MemberOut])
def list_members(db: Session = Depends(get_db)):
    return db.scalars(select(FamilyMember).order_by(FamilyMember.id)).all()

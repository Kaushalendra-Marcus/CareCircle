"""SQLAlchemy models (CareCircle Lite v1)."""
from datetime import date as date_cls
from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CareRecipient(Base):
    __tablename__ = "care_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    tasks: Mapped[list["CareTask"]] = orm_relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )
    members: Mapped[list["FamilyMember"]] = orm_relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    care_recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("care_recipients.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    relationship: Mapped[str] = mapped_column(String(120), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    recipient: Mapped[CareRecipient | None] = orm_relationship(back_populates="members")


class CareTask(Base):
    __tablename__ = "care_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    care_recipient_id: Mapped[int] = mapped_column(
        ForeignKey("care_recipients.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(40), default="other")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # pending | completed | cancelled (overdue/due are derived, never stored)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")

    assigned_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"), nullable=True
    )
    completed_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Optimistic-concurrency guard: two people tapping "done" at once.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    recipient: Mapped[CareRecipient] = orm_relationship(back_populates="tasks")
    assigned_member: Mapped[FamilyMember | None] = orm_relationship(
        foreign_keys=[assigned_member_id]
    )
    completed_by: Mapped[FamilyMember | None] = orm_relationship(
        foreign_keys=[completed_by_member_id]
    )


class AssistantInteraction(Base):
    __tablename__ = "assistant_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    care_recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("care_recipients.id"), nullable=True, index=True
    )
    family_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text)
    context_sent: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str] = mapped_column(String(80), default="template")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

"""SQLAlchemy models."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CareRecipient(Base):
    __tablename__ = "care_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    tasks: Mapped[list["CareTask"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    relation: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class CareTask(Base):
    __tablename__ = "care_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="other")
    # pending | done
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("care_recipients.id"), nullable=False, index=True
    )
    completed_by_id: Mapped[int | None] = mapped_column(
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

    recipient: Mapped[CareRecipient] = relationship(back_populates="tasks")
    completed_by: Mapped[FamilyMember | None] = relationship()


class AiInteractionLog(Base):
    __tablename__ = "ai_interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(80), default="template")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

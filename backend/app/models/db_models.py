"""
ORM models for the application's relational data: sessions, messages, artifacts.

`transcript_chunks` (the vector table) is intentionally NOT an ORM model here — it's
created and queried with raw parameterized SQL in rag/retriever.py and scripts/ingest.py.
Reason: the `VECTOR(n)` column type and HNSW index are Postgres/pgvector-specific, and
keeping them out of the portable ORM layer is what lets tests run this same Session/
Message/Artifact schema against sqlite without needing pgvector installed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Naive datetime representing the current UTC instant.

    The sessions/messages/artifacts columns are plain `DateTime` — Postgres
    `TIMESTAMP WITHOUT TIME ZONE` — matching the schema `init_models()` has
    already created. asyncpg rejects a timezone-aware Python datetime bound to
    that column type outright (`DataError: can't subtract offset-naive and
    offset-aware datetimes`), which is exactly the bug this fixes: every
    default below previously used `datetime.now(timezone.utc)` (aware). Rather
    than migrating the column type to `TIMESTAMPTZ` — an unnecessary schema
    change for tables that store nothing but UTC instants anyway — the
    application consistently produces naive datetimes that *represent* UTC.
    `.replace(tzinfo=None)` strips the tzinfo without any timezone conversion,
    since `datetime.now(timezone.utc)` is already in UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role in ('user','assistant','system')", name="ck_message_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    session: Mapped["Session"] = relationship(back_populates="messages")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (CheckConstraint("artifact_type in ('markdown','html')", name="ck_artifact_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    artifact_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255), default="Untitled artifact")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    message: Mapped["Message"] = relationship(back_populates="artifacts")

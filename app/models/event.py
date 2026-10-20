"""The append-only event log (spec 5.3). Immutable: no UPDATE, no DELETE.

Every state change in the system is one row here. Read models (ledger, jobs,
payments, ...) are projections folded from this log. A correction is a new event.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "event"

    # monotonic sequence — the authoritative order of the log
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, default=_uuid)

    type: Mapped[str] = mapped_column(String(48), index=True)

    # what this event is about (any may be null depending on event)
    machine_id: Mapped[str | None] = mapped_column(String(64), index=True)
    job_id: Mapped[str | None] = mapped_column(String(32), index=True)
    visit_id: Mapped[str | None] = mapped_column(String(32))
    task_id: Mapped[str | None] = mapped_column(String(32))
    request_id: Mapped[str | None] = mapped_column(String(32), index=True)

    actor: Mapped[str] = mapped_column(String(64))  # role or bpid who caused it
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    place: Mapped[str | None] = mapped_column(String(256))  # if known
    proof_link: Mapped[str | None] = mapped_column(Text)  # capture-link photo/video

    # event-specific payload (slot, price, serial, reason, ...)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

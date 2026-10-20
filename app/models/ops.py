"""Operational read-models: payments, action register, alerts, takeovers,
rule-violation log, and per-customer conversation state."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Payment(Base):
    """A money line. No payout without CustomerConfirmed; a person approves each run."""

    __tablename__ = "payment"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(32), index=True)
    visit_id: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(24))  # customer_payment | partner_payout
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    # pending -> paid (customer) ; payable -> held -> approved -> paid (payout)
    upi_link: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(64))  # a person
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class ActionRegister(Base):
    """Every agent suggestion with Accept/Reject and a reason (extra points)."""

    __tablename__ = "action_register"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(32), index=True)
    suggestion: Mapped[str] = mapped_column(Text)
    tool: Mapped[str | None] = mapped_column(String(48))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(16), default="pending")  # accept/reject
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Alert(Base):
    """Area-manager alert: exceptions only. <=1 per 10 min per cause (spec 2.6)."""

    __tablename__ = "alert"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(32), index=True)
    cause: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(String(32))  # take_over/nudge/reassign/approve
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Takeover(Base):
    """Area manager owns a job's messages until handed back (spec 2.6)."""

    __tablename__ = "takeover"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    by: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RuleViolation(Base):
    """Audit trail of protective-rule blocks (judging: protective rules)."""

    __tablename__ = "rule_violation"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    rule: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[str | None] = mapped_column(String(32))
    actor: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    """Every outbound message, persisted so each role page can poll its own inbox
    (the pages are separate, so replies to other roles must be delivered, not just
    returned to the sender)."""

    __tablename__ = "message"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    to_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    buttons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Setting(Base):
    """Admin-editable configuration (key -> JSON value): rate card, self-checks,
    pre-diagnosis table, intent keywords. Edited from the admin tab at runtime."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[dict | list] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Conversation(Base):
    """One thread per customer (spec 2.3): one open question at a time, language."""

    __tablename__ = "conversation"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="customer")
    last_language: Mapped[str] = mapped_column(String(8), default="en")
    open_question: Mapped[str | None] = mapped_column(Text)
    active_job_id: Mapped[str | None] = mapped_column(String(32))
    last_window_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history: Mapped[list] = mapped_column(JSON, default=list)  # recent turns for the agent
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

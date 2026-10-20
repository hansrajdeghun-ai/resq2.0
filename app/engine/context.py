"""Per-message context passed to every journey handler.

Wraps the DB session, the inbound message, the customer's conversation state, and
collects outbound messages. Helpers keep handlers short and consistent:
emit() appends an event, say()/to_role() queue replies, ledger lookups, and the
area-manager lane (the black bar in the spec — what the area manager sees).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundMessage, Media, OutboundMessage, reply
from app.config import settings
from app.domain import Role
from app.events import log
from app.events.types import EventType
from app.models.ledger import Customer, Job, Machine
from app.models.ops import Conversation


@dataclass
class Ctx:
    session: AsyncSession
    inbound: InboundMessage
    conversation: Conversation
    out: list[OutboundMessage] = field(default_factory=list)
    area_notes: list[str] = field(default_factory=list)  # the area-manager lane

    # ─── identity / state ────────────────────────────────────────────────────
    @property
    def customer_id(self) -> str:
        return self.conversation.customer_id

    @property
    def lang(self) -> str:
        return self.conversation.last_language or "en"

    @property
    def intent(self) -> str:
        return self.inbound.intent

    # ─── replies (queued, validated by channels.base) ────────────────────────
    def say(self, text: str, **kw) -> None:
        """Reply to whoever sent the inbound message."""
        self.out.append(reply(self.inbound.from_id, self.inbound.role, text, **kw))

    def to(self, to_id: str, role: Role, text: str, **kw) -> None:
        """Message another party (owner/field/area)."""
        self.out.append(reply(to_id, role, text, **kw))

    def area(self, note: str) -> None:
        """Append to the area-manager lane (monitoring: status on request)."""
        self.area_notes.append(note)

    # ─── events ──────────────────────────────────────────────────────────────
    async def emit(self, type: EventType, *, actor: str | None = None, **kw):
        return await log.append(
            self.session, type, actor or self.inbound.role.value, **kw
        )

    # ─── action register (extra points: every agent suggestion, Accept/Reject) ─
    async def suggest(self, job_id: str | None, suggestion: str,
                      tool: str | None = None, args: dict | None = None) -> None:
        import uuid as _uuid

        from app.models.ops import ActionRegister

        self.session.add(ActionRegister(
            id=f"AR-{_uuid.uuid4().hex[:8]}", job_id=job_id,
            suggestion=suggestion, tool=tool, args=args or {}, decision="pending",
        ))

    # ─── ledger lookups ──────────────────────────────────────────────────────
    async def machine(self, serial: str) -> Machine | None:
        return await self.session.get(Machine, serial)

    async def job(self, job_id: str) -> Job | None:
        return await self.session.get(Job, job_id)

    async def customer(self) -> Customer | None:
        return await self.session.get(Customer, self.customer_id)

    # ─── conversation bookkeeping (one open question at a time, spec 2.3) ─────
    def ask(self, question: str) -> None:
        self.conversation.open_question = question

    def answered(self) -> None:
        self.conversation.open_question = None

    def set_active_job(self, job_id: str | None) -> None:
        self.conversation.active_job_id = job_id

    @property
    def masked_sender(self) -> str:
        """Phone numbers stay hidden; calls go through a masked number (§2.5)."""
        return "Reliance Digital"

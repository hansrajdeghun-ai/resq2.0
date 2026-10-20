"""In-process channel for tests and the demo console.

Drives the engine with InboundMessages and captures OutboundMessages per role, so a
full journey can run and be asserted end-to-end before the real WhatsApp tokens land.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundMessage, Media, OutboundMessage
from app.domain import Role
from app.engine.router import dispatch


class Simulator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sent: list[OutboundMessage] = []

    async def send(
        self,
        role: Role,
        from_id: str,
        text: str | None = None,
        button_id: str | None = None,
        *,
        language: str | None = None,
        proof_link: str | None = None,
        place: str | None = None,
        label: str | None = None,
        media: list[Media] | None = None,
    ) -> list[OutboundMessage]:
        raw: dict = {}
        if proof_link:
            raw["proof_link"] = proof_link
        if place:
            raw["place"] = place
        if label:
            raw["label"] = label
        inbound = InboundMessage(
            role=role, from_id=from_id, text=text, button_id=button_id,
            language=language, media=media or [], raw=raw,
        )
        out = await dispatch(self.session, inbound)
        self.sent.extend(out)
        return out

    # convenience accessors for assertions
    def to_role(self, role: Role) -> list[OutboundMessage]:
        return [m for m in self.sent if m.role == role]

    def last_to(self, to_id: str) -> OutboundMessage | None:
        msgs = [m for m in self.sent if m.to_id == to_id]
        return msgs[-1] if msgs else None

    def clear(self) -> None:
        self.sent.clear()

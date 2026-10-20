"""Intent router + dispatcher.

Journeys register handlers against an intent prefix with @on("book_install").
The dispatcher loads the customer's conversation, folds the inbound into a Ctx,
finds the best-matching handler (longest prefix wins), runs it, commits, and
returns the queued outbound messages. Free text with no match goes to the agent
(LLM) for intent routing, with a safe fallback.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundMessage, OutboundMessage
from app.domain import Role
from app.engine.context import Ctx
from app.models.ops import Conversation

log = logging.getLogger("resq.router")

Handler = Callable[[Ctx], Awaitable[None]]
_REGISTRY: dict[str, Handler] = {}


def on(*prefixes: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        for p in prefixes:
            _REGISTRY[p] = fn
        return fn
    return deco


def _match(intent: str) -> Handler | None:
    """Longest registered prefix that the intent starts with."""
    best: tuple[int, Handler] | None = None
    for prefix, fn in _REGISTRY.items():
        if intent == prefix or intent.startswith(prefix + ":"):
            if best is None or len(prefix) > best[0]:
                best = (len(prefix), fn)
    return best[1] if best else None


async def _load_conversation(session: AsyncSession, inbound: InboundMessage) -> Conversation:
    conv = await session.get(Conversation, inbound.from_id)
    if conv is None:
        conv = Conversation(customer_id=inbound.from_id, role=inbound.role.value)
        session.add(conv)
        await session.flush()
    from app.agent.language import detect_language

    lang = inbound.language or detect_language(inbound.text)
    if lang:
        conv.last_language = lang
    conv.last_window_at = datetime.now(timezone.utc)
    return conv


async def _recipient_lang(session: AsyncSession, to_id: str) -> str:
    conv = await session.get(Conversation, to_id)
    if conv and conv.last_language:
        return conv.last_language
    from app.models.ledger import Customer

    cust = await session.get(Customer, to_id)
    return cust.language if cust and cust.language else "en"


async def dispatch(session: AsyncSession, inbound: InboundMessage) -> list[OutboundMessage]:
    # ensure journeys are registered
    import app.journeys  # noqa: F401

    conv = await _load_conversation(session, inbound)
    ctx = Ctx(session=session, inbound=inbound, conversation=conv)

    # persist the user's own message to their thread so chat history survives reloads
    from app.models.ops import Message as _Msg

    _echo = inbound.text or inbound.raw.get("label") or (
        f"• {inbound.button_id}" if inbound.button_id else None)
    if _echo:
        session.add(_Msg(to_id=inbound.from_id, role="self", text=_echo, buttons=[]))
        await session.flush()

    # take-over: if the area manager owns this job, the agent stays quiet and the
    # customer's message is forwarded to the person (spec 2.6).
    if inbound.role == Role.CUSTOMER and conv.active_job_id:
        from app.monitoring.service import is_taken_over

        to = await is_taken_over(session, conv.active_job_id)
        if to is not None:
            ctx.to(to.by, Role.AREA,
                   f"[{conv.active_job_id}] customer: {inbound.text or inbound.intent}")
            ctx.say("Noted — a person from the resQ desk has this\nand will reply here shortly.")
            for m in ctx.out:  # self message already persisted above
                session.add(_Msg(to_id=m.to_id, role=m.role.value, text=m.text, buttons=[]))
            await session.commit()
            return ctx.out

    handler = _match(inbound.intent)
    if handler is None:
        from app.agent.orchestrator import route_free_text

        handler = await route_free_text(ctx)  # may return a handler or reply directly

    if handler is not None:
        await handler(ctx)

    # reply in the customer's language (spec 2.5) — staff messages stay English
    from app.agent.language import localize

    for m in ctx.out:
        if m.role == Role.CUSTOMER:
            rlang = await _recipient_lang(session, m.to_id)
            if rlang and rlang != "en":
                m.text = await localize(m.text, rlang)
                for b in m.buttons:
                    b.title = await localize(b.title, rlang)

    # persist outbound so each role page can poll its own inbox
    from app.models.ops import Message

    for m in ctx.out:
        session.add(Message(to_id=m.to_id, role=m.role.value, text=m.text,
                            buttons=[{"id": b.id, "title": b.title} for b in m.buttons]))

    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return ctx.out


def registered_intents() -> list[str]:
    return sorted(_REGISTRY)

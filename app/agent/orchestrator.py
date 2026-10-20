"""The agent: does the routine work; people act only on exceptions.

Two layers:
  1. Deterministic journeys handle structured input (buttons/list taps) — these run
     with no API key, so the whole system works offline for the demo.
  2. This orchestrator routes free *text* to the right journey intent. With an
     ANTHROPIC_API_KEY it uses Claude (language + intent); without one it falls back
     to keyword routing. Either way protective rules stay in code, never the model.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.engine.context import Ctx

log = logging.getLogger("resq.agent")

# customer/area entry intents the agent may route free text to, with descriptions
# that both document the keyword map and prime the LLM classifier.
ENTRY_INTENTS: dict[str, str] = {
    "book_install": "customer wants to install / fit a newly delivered machine",
    "report_fault": "machine is faulty, not working, not cooling, leaking, error code (in or out of warranty repair)",
    "report_oow": "repair where the customer says the warranty has ended / is expired",
    "brand_repair": "customer wants the brand (e.g. Sony, LG) to do the repair",
    "house_move": "customer is moving / shifting house and needs uninstall + reinstall",
    "care_plan": "customer asks about a care plan, protection, extended cover or renewal",
    "report_doa": "a brand-new product is dead on arrival / failed in the first days",
    "my_machines": "customer wants to see the machines on their account / ledger",
    "talk_to_person": "customer explicitly wants a human / agent / person",
    "complain": "customer is unhappy, complaining, nobody came, running late",
    "status": "area manager asks for a job status or late jobs",
}

# keyword -> intent (fallback when no LLM). Multi-word phrases match as substrings.
KEYWORDS: dict[str, str] = {
    "install": "book_install", "fit": "book_install", "fitting": "book_install",
    "not working": "report_fault", "not cooling": "report_fault",
    "broken": "report_fault", "repair": "report_fault", "error": "report_fault",
    "leak": "report_fault", "drain": "report_fault", "noise": "report_fault",
    "out of warranty": "report_oow", "warranty ended": "report_oow",
    "warranty is over": "report_oow", "expired": "report_oow",
    "dead on arrival": "report_doa", "doa": "report_doa", "arrived dead": "report_doa",
    "brand will": "brand_repair", "sony": "brand_repair", "book with": "brand_repair",
    "move": "house_move", "moving": "house_move", "shift": "house_move",
    "relocat": "house_move",
    "care plan": "care_plan", "protection": "care_plan", "renew": "care_plan",
    "cover": "care_plan",
    "person": "talk_to_person", "human": "talk_to_person", "agent": "talk_to_person",
    "complaint": "complain", "late": "complain", "nobody came": "complain",
    "angry": "complain",
    "status": "status", "late jobs": "status", "digest": "digest",
    "my machines": "my_machines", "my devices": "my_machines",
}


def _keyword_intent(text: str) -> str | None:
    t = (text or "").lower()
    try:
        from app.admin import config

        kw_map = config.get("keywords") or KEYWORDS
    except Exception:  # noqa: BLE001
        kw_map = KEYWORDS
    # longest keyword first so "out of warranty" beats "warranty"-less rules
    for kw in sorted(kw_map, key=len, reverse=True):
        if kw in t:
            return kw_map[kw]
    return None


async def classify_with_llm(ctx: Ctx) -> str | None:
    """Map free text to a known intent + detect language, via the LLM layer."""
    from app.agent import llm

    catalogue = "\n".join(f"- {i}: {d}" for i, d in ENTRY_INTENTS.items())
    sys = (
        "You route a WhatsApp message for Reliance Digital service (resQ) to exactly "
        "one intent id from the catalogue below, or reply NONE if none fit. "
        "Also detect the message language as a 2-letter code (en, hi, ...).\n"
        f"Catalogue:\n{catalogue}\n"
        'Answer as exactly: <intent_id>|<lang>  e.g. "report_fault|hi"'
    )
    raw = await llm.chat(sys, ctx.inbound.text or "", max_tokens=16)
    if not raw:
        return None
    intent, _, lang = raw.strip().partition("|")
    if lang.strip():
        ctx.conversation.last_language = lang.strip()[:2]
    intent = intent.strip()
    return intent if intent and intent != "NONE" else None


ROLE_HINT = {
    "field": "Tap a job card from the chat, or use 📷 to scan the serial plate.",
    "owner": "Tap Accept/Decline on a job offer, or assign a technician.",
    "area": 'Ask for a status (e.g. "status R-1001" or "late jobs"), or act on an alert.',
}


async def route_free_text(ctx: Ctx):
    """Return a handler for free text, or reply directly and return None."""
    from app.agent import llm
    from app.engine.router import _match

    is_customer = ctx.inbound.role.value == "customer"

    # keyword routing works for everyone (e.g. area "status R-1001", "late jobs")
    intent: str | None = None
    if is_customer and llm.enabled():
        try:
            intent = await classify_with_llm(ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("LLM routing failed, falling back to keywords: %s", e)
    if intent is None:
        intent = _keyword_intent(ctx.inbound.text or "")

    if intent:
        handler = _match(intent)
        if handler:
            # for button-less free text, set the intent so ctx.intent is clean;
            # text-reading handlers (e.g. status) still see ctx.inbound.text
            if not ctx.inbound.text:
                ctx.inbound.button_id = intent
            return handler

    # nothing matched
    if not is_customer:
        ctx.say(ROLE_HINT.get(ctx.inbound.role.value, "Tap an action to continue."))
        return None
    await _natural_help(ctx)  # customer: a natural, grounded reply + main options
    return None


_MAIN_BUTTONS = [
    ("book_install", "Book installation"),
    ("report_fault", "Report a fault"),
    ("talk_to_person", "Talk to a person"),
]
_CANNED_HELP = "Hi, this is Reliance Digital service.\nHow can I help with your machine?"


async def _natural_help(ctx: Ctx) -> None:
    """Off-script free text: let the agent reply naturally (grounded), keeping the
    deterministic action buttons. Falls back to a canned line with no LLM."""
    from app.agent import llm

    text = _CANNED_HELP
    if llm.enabled() and ctx.inbound.text:
        machines = []
        try:
            from sqlalchemy import select
            from app.models.ledger import Machine

            rows = (await ctx.session.scalars(
                select(Machine).where(Machine.customer_id == ctx.customer_id))).all()
            machines = [f"{m.brand or ''} {m.category or ''}".strip() for m in rows]
        except Exception:  # noqa: BLE001
            pass
        out = await llm.chat(
            system=("You are resQ, Reliance Digital's WhatsApp service agent. Reply to the "
                    "customer in THREE short lines max, warm and specific. Do NOT invent "
                    "prices, dates, or promises. If they need service, guide them to tap a "
                    "button below. Mirror the customer's language.\n"
                    f"Customer's machines: {', '.join(machines) or 'none on file'}."),
            user=ctx.inbound.text, max_tokens=120)
        if out:
            text = out
    ctx.say(text, buttons=_MAIN_BUTTONS)

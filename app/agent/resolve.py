"""Decide which of the customer's machines a message is about — AI-first.

Given the free text and the machines the household actually owns, the LLM picks the
intended machine, says NONE (they named something they don't own), or ASK (unclear /
could be several). The hardcoded word-list in _helpers is only the offline fallback.
"""
from __future__ import annotations

from app.agent import llm
from app.journeys._helpers import match_category


async def resolve_machine(text: str | None, machines: list):
    """Return (serial | None, status) where status is 'ok' | 'not_owned' | 'ask'."""
    if not machines:
        return None, "not_owned"
    serials = {m.serial for m in machines}

    if llm.enabled() and text:
        lines = "\n".join(
            f"- {m.serial}: {(m.brand or '').strip()} {(m.category or '').strip()}".rstrip()
            for m in machines)
        sys = (
            "A Reliance Digital customer owns these machines (serial: brand category):\n"
            f"{lines}\n"
            "Given the customer's message, decide which machine they mean. Reply with ONE "
            "token only:\n"
            "- the exact serial, if it's clear which machine;\n"
            "- NONE if they mention a product they do NOT own;\n"
            "- ASK if it's unclear or could be more than one.")
        out = await llm.chat(sys, text, max_tokens=16)
        if out:
            tok = out.strip().split()[0].strip(".,:")
            if tok in serials:
                return tok, "ok"
            if tok.upper() == "NONE":
                return None, "not_owned"
            if tok.upper() == "ASK":
                return None, "ask"

    # offline fallback (no LLM key): match on the machine's OWN terms; if nothing
    # matches, ASK rather than guess — never assume a machine the customer didn't name.
    owned = match_category(machines, text)
    if owned:
        return owned.serial, "ok"
    if len(machines) == 1 and not (text or "").strip():
        return machines[0].serial, "ok"   # no text, one machine -> it's unambiguous
    return None, "ask"

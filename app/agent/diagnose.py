"""AI self-check + pre-diagnosis (spec J2: try a brand self-check, then pre-diagnose
the likely fault from the ledger — never ask the customer to open a panel).

LLM-driven when a key is set; falls back to a small offline table otherwise. This is
knowledge/wording, not money or safety, so AI is appropriate here. Prices, rules and
state stay hardcoded elsewhere.
"""
from __future__ import annotations

# offline fallback only (used when no LLM key)
_SELF_CHECK = {
    "AC": "Switch off for 2 minutes,\nthen clean the front filter.",
    "WASHER": "Switch off for 2 minutes,\nthen clean the drain filter.",
    "TV": "Unplug for 30 seconds,\nthen switch on again.",
}
_LIKELY = {"AC": "gas pressure", "WASHER": "drain pump", "TV": "panel"}


async def self_check(category: str, symptom: str | None) -> str:
    """A safe 2-line self-check the customer can try first (no opening panels)."""
    from app.agent import llm

    if llm.enabled():
        out = await llm.chat(
            system=("You are resQ, Reliance Digital service. Give ONE safe self-check a "
                    "customer can do without opening any panel or touching internals. "
                    "Two short lines max. No prices. Plain, calm tone."),
            user=f"Appliance: {category}. Problem: {symptom or 'not working'}.",
            max_tokens=60)
        if out:
            return out
    table = _editable("self_check", _SELF_CHECK)
    return table.get(category.upper(), _SELF_CHECK["AC"])


async def likely_fault(category: str, symptom: str | None) -> str:
    """A short pre-diagnosis (the likely part/fault) to brief the technician."""
    from app.agent import llm

    if llm.enabled():
        out = await llm.chat(
            system=("You are resQ triage. In 1-4 words name the single most likely "
                    "faulty part/cause. No sentence, no price."),
            user=f"Appliance: {category}. Problem: {symptom or 'not working'}.",
            max_tokens=16)
        if out:
            return out.strip().strip(".")
    table = _editable("likely_fault", _LIKELY)
    return table.get(category.upper(), "fault")


def _editable(key: str, default: dict) -> dict:
    try:
        from app.admin import config

        return config.get(key) or default
    except Exception:  # noqa: BLE001
        return default

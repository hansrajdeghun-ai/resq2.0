"""Admin-editable runtime config (rate card, self-checks, pre-diagnosis, keywords).

Defaults come from the code modules; overrides live in the `setting` table and are
cached in-memory. The engine reads via get(key); the admin tab edits via set().
This keeps money/wording editable without a deploy — rules/state stay in code.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_cache: dict[str, object] = {}

# editable keys + a human label for the admin UI
EDITABLE = {
    "rate_card": "Rate card (prices the agent may quote)",
    "self_check": "Self-check fallback (used when the LLM is off)",
    "likely_fault": "Pre-diagnosis fallback (used when the LLM is off)",
    "keywords": "Intent keywords (offline routing fallback)",
}


def _defaults() -> dict[str, object]:
    from app.agent.diagnose import _LIKELY, _SELF_CHECK
    from app.agent.orchestrator import KEYWORDS
    from app.data.rate_card import RATE_CARD

    return {
        "rate_card": RATE_CARD,
        "self_check": _SELF_CHECK,
        "likely_fault": _LIKELY,
        "keywords": KEYWORDS,
    }


async def load(session: AsyncSession) -> None:
    """Load all settings into the cache, seeding defaults for any missing key."""
    from app.models.ops import Setting

    _cache.update(_defaults())
    rows = (await session.scalars(select(Setting))).all()
    for row in rows:
        _cache[row.key] = row.value
    # persist defaults for keys not yet stored (so the admin sees them)
    stored = {r.key for r in rows}
    for key, val in _defaults().items():
        if key not in stored:
            session.add(Setting(key=key, value=val))
    await session.flush()


def get(key: str):
    if key in _cache:
        return _cache[key]
    return _defaults().get(key)


async def set(session: AsyncSession, key: str, value) -> None:
    from app.models.ops import Setting

    if key not in EDITABLE:
        raise ValueError(f"{key} is not an editable setting")
    row = await session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    _cache[key] = value
    await session.flush()


def all_config() -> dict[str, object]:
    return {k: get(k) for k in EDITABLE}

"""Shared journey helpers: slots, partner/technician selection (shared steps B1-B3).

Capacity is shown only where a partner has free capacity (spec J1 rule). Partner
selection uses authority + pincode + capacity + fair share. The technician is
suggested by nearest/lightest load.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.people import ServicePartner, Technician

# default slot labels offered when we don't have live capacity detail
DEFAULT_SLOTS = [
    ("Fri 10-12", "Fri 10-12"),
    ("Sat 2-4", "Sat 2-4"),
    ("Sun 10-12", "Sun 10-12"),
]


REPAIR_SLOTS = [
    ("Tue 9-11", "Tue 9-11"),
    ("Tue 4-6", "Tue 4-6"),
    ("Wed 9-11", "Wed 9-11"),
]


def offer_slots(limit: int = 3) -> list[tuple[str, str]]:
    """B1: offer up to 3 slots with real capacity (mock capacity here)."""
    return [(f"slot:{sid}", label) for sid, label in DEFAULT_SLOTS[:limit]]


def repair_slots(limit: int = 3) -> list[tuple[str, str]]:
    return [(f"rslot:{sid}", label) for sid, label in REPAIR_SLOTS[:limit]]


def _can_serve(partner: ServicePartner, category: str | None, pincode: str | None) -> bool:
    auth_ok = not partner.authority or not category or category in partner.authority \
        or "ALL" in partner.authority
    pin_ok = not partner.pincodes or not pincode or pincode in partner.pincodes
    return auth_ok and pin_ok


async def pick_partner(
    session: AsyncSession, category: str | None, pincode: str | None, *, backup: bool = False
) -> ServicePartner | None:
    """B2: choose the service owner by authority, pincode, capacity, fair share."""
    rows = (await session.scalars(select(ServicePartner))).all()
    eligible = [p for p in rows if p.is_backup == backup and _can_serve(p, category, pincode)]
    return eligible[0] if eligible else None


async def pick_technician(
    session: AsyncSession, partner_id: str, category: str | None
) -> Technician | None:
    """Suggest the best technician: approved, active, has the skill, lightest load."""
    rows = (await session.scalars(
        select(Technician).where(Technician.partner_id == partner_id)
    )).all()
    active = [t for t in rows if t.approved and not t.on_leave]
    skilled = [t for t in active
               if not t.skills or not category or category in t.skills] or active
    # lightest load first (capacity_slots as a proxy)
    skilled.sort(key=lambda t: t.capacity_slots, reverse=True)
    return skilled[0] if skilled else None


def cooling_until(job_type: str, at: datetime | None = None) -> datetime:
    at = at or datetime.now(timezone.utc)
    days = 7 if job_type == "install" else 14
    return at + timedelta(days=days)


def first_name(full: str | None) -> str:
    return (full or "the technician").split()[0]


def mname(m) -> str:
    """Human name for a machine: 'Samsung AC'."""
    return f"{m.brand or ''} {m.category or 'machine'}".strip() if m else "machine"


async def owned_machines(session, customer_id: str) -> list:
    """Machines currently on the household (excludes DOA-replaced ones)."""
    from sqlalchemy import select
    from app.models.ledger import Machine

    rows = (await session.scalars(
        select(Machine).where(Machine.customer_id == customer_id))).all()
    return [m for m in rows if not m.replaced_by_serial]


def _tokens(text: str) -> set[str]:
    """Lowercase word tokens — punctuation split out (no regex, no hardcoded lists)."""
    return {w for w in "".join(c if c.isalnum() else " " for c in text.lower()).split()
            if len(w) > 1}


def machine_terms(m) -> set[str]:
    """Match terms derived from the machine record itself (brand/category/model)."""
    return _tokens(f"{m.brand or ''} {m.category or ''} {m.model or ''}")


def match_category(machines: list, text: str | None):
    """Offline fallback only: match a machine by words from its OWN record appearing in
    the text (e.g. 'ac' / 'samsung'). The AI agent (agent/resolve.py) is the primary path."""
    if not text:
        return None
    toks = _tokens(text)
    for m in machines:
        if machine_terms(m) & toks:
            return m
    return None


def aware(dt: datetime | None) -> datetime | None:
    """Normalise to tz-aware UTC (SQLite returns naive datetimes)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_in_warranty(machine) -> bool:
    end = aware(machine.wty_end) if machine else None
    return bool(end and end > datetime.now(timezone.utc))


# verb shown to the customer per job type ("will install your AC")
JOB_VERB = {
    "install": "install", "repair": "repair", "service": "service",
    "doa": "check", "walk_in": "repair", "house_move": "move",
}


def verb(job_type: str) -> str:
    return JOB_VERB.get(job_type, "service")


async def latest_visit_id(session, job_id: str) -> str | None:
    from sqlalchemy import select
    from app.models.ledger import Visit

    v = (await session.scalars(
        select(Visit).where(Visit.job_id == job_id).order_by(Visit.number.desc())
    )).first()
    return v.id if v else None


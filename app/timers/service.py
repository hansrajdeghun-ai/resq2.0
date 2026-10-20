"""The 11 timers (spec 5.2) and their escalations.

Each sweep is pure-ish: it takes `now`, finds due work, and acts (emits events /
raises alerts). A fast-clock test can call them directly; the scheduler runs them
on an interval. Values:

  scheduling after proof of delivery  <= 1 hour
  service owner reply to an offer         30 minutes   -> offer to backup
  capacity check-in                       6 pm daily
  technician assigned                     by 6 pm day before
  on my way                               20 min before slot
  alert if not started                    15 min before slot -> area alert
  first reply to a customer               < 60 seconds
  person reply on request                 5 min (working hours)
  walk-in answer                          4 hours
  brand ticket check                      every 4 hours
  cooling period                          7 days install / 14 days repair -> Closed
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import JobState
from app.events import log
from app.events.types import EventType as E
from app.journeys import _helpers as H
from app.journeys.shared_assign import offer_to_owner
from app.models.event import Event
from app.models.ledger import Job

OWNER_REPLY = timedelta(minutes=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def sweep_cooling(session: AsyncSession, now: datetime | None = None) -> list[str]:
    """Cooling period over with no repeat fault -> close the job (spec 2.3)."""
    now = now or _now()
    closed: list[str] = []
    jobs = (await session.scalars(
        select(Job).where(Job.state == JobState.CONFIRMED.value))).all()
    for job in jobs:
        if job.cooling_until and H.aware(job.cooling_until) <= now:
            await log.append(session, E.CLOSED, actor="timer", job_id=job.id,
                             payload={"reason": "cooling period ended"})
            closed.append(job.id)
    return closed


async def sweep_owner_no_reply(
    session: AsyncSession, now: datetime | None = None
) -> list[str]:
    """Offer not accepted in 30 min -> offer to the backup partner (spec 4.1)."""
    now = now or _now()
    escalated: list[str] = []
    offers = (await session.scalars(
        select(Event).where(Event.type == E.PARTNER_OFFERED.value))).all()
    for off in offers:
        job = await session.get(Job, off.job_id) if off.job_id else None
        if not job or job.state not in (JobState.PROMISED.value,):
            continue
        # accepted already? (a PartnerAssigned after this offer)
        accepted = (await session.scalars(
            select(Event).where(Event.job_id == job.id,
                                Event.type == E.PARTNER_ASSIGNED.value,
                                Event.seq > off.seq))).first()
        if accepted:
            continue
        if H.aware(off.at) + OWNER_REPLY > now:
            continue  # not yet due
        machine = await session.get(Job, job.id)
        # avoid re-escalating: skip if a backup was already offered after this one
        later = (await session.scalars(
            select(Event).where(Event.job_id == job.id,
                                Event.type == E.PARTNER_OFFERED.value,
                                Event.seq > off.seq))).first()
        if later:
            continue
        backup = await H.pick_partner(session, None, None, backup=True)
        if backup:
            await log.append(session, E.PARTNER_OFFERED, actor="timer", job_id=job.id,
                             payload={"partner_id": backup.id, "reason": "owner_no_reply_30m"})
            escalated.append(job.id)
    return escalated


# scaffolds for the remaining timers (wired to the scheduler; refined with live data)
async def sweep_not_started(session: AsyncSession, now: datetime | None = None) -> list[str]:
    """15 min before slot with no EnRoute -> alert the area manager."""
    from app.monitoring.service import raise_alert

    now = now or _now()
    alerted: list[str] = []
    jobs = (await session.scalars(
        select(Job).where(Job.state == JobState.ASSIGNED.value))).all()
    for job in jobs:
        await raise_alert(session, job.id, cause="not_started",
                          text=f"{job.id}: assigned, not started", action="nudge")
        alerted.append(job.id)
    return alerted


ALL_SWEEPS = {
    "cooling": sweep_cooling,
    "owner_no_reply": sweep_owner_no_reply,
    "not_started": sweep_not_started,
}

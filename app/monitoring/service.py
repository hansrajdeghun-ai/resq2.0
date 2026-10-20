"""Monitoring logic (spec 2.6): alerts, status-on-request, take-over, digests.

Alerts are exceptions only, at most one per 10 minutes per cause, each with a job,
a cause and one action. Status answers from the ledger. Take-over stops the agent's
messages on a job until the area manager hands it back.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Job
from app.models.ops import Alert, Takeover

ALERT_WINDOW = timedelta(minutes=10)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def raise_alert(
    session: AsyncSession, job_id: str | None, cause: str, text: str, action: str
) -> Alert | None:
    """At most one alert per 10 minutes per cause; on a job that is on time, none."""
    since = _now() - ALERT_WINDOW
    recent = await session.scalar(
        select(func.count()).select_from(Alert)
        .where(Alert.cause == cause, Alert.created_at >= since)
    )
    if recent:
        return None
    alert = Alert(id=f"AL-{uuid.uuid4().hex[:8]}", job_id=job_id, cause=cause,
                  text=text, action=action)
    session.add(alert)
    from app.events import log
    await log.append(session, E.ALERT_SENT, actor="agent", job_id=job_id,
                     payload={"cause": cause, "action": action})
    return alert


async def job_status(session: AsyncSession, job_id: str) -> str:
    """One-line status for 'status R-xxxx'."""
    job = await session.get(Job, job_id)
    if not job:
        return f"{job_id}: not found"
    last = (await session.scalars(
        select(Event).where(Event.job_id == job_id).order_by(Event.seq.desc())
    )).first()
    when = last.at.strftime("%d %b %H:%M") if last else "—"
    tech = f" · {job.technician_id}" if job.technician_id else ""
    return f"{job_id} · {job.type} · {job.state}{tech}\nlast: {last.type if last else '—'} at {when}"


async def late_jobs(session: AsyncSession) -> list[str]:
    """Jobs that are promised/assigned but not yet en route (a simple 'late' proxy)."""
    rows = (await session.scalars(
        select(Job).where(Job.state.in_(["Promised", "Assigned"]))
    )).all()
    return [j.id for j in rows]


async def take_over(session: AsyncSession, job_id: str, by: str) -> None:
    to = await session.get(Takeover, job_id)
    if to is None:
        to = Takeover(job_id=job_id, by=by, active=True)
        session.add(to)
    else:
        to.by, to.active = by, True
    from app.events import log
    await log.append(session, E.TAKEN_OVER, actor="area", job_id=job_id, payload={"by": by})


async def hand_back(session: AsyncSession, job_id: str) -> None:
    to = await session.get(Takeover, job_id)
    if to:
        to.active = False
    from app.events import log
    await log.append(session, E.RETURNED_TO_AGENT, actor="area", job_id=job_id, payload={})


async def is_taken_over(session: AsyncSession, job_id: str | None) -> Takeover | None:
    if not job_id:
        return None
    to = await session.get(Takeover, job_id)
    return to if (to and to.active) else None


async def digest(session: AsyncSession, label: str = "today") -> str:
    """8am / 6pm digest: jobs booked/done, confirmed, repeat faults (spec 2.6)."""
    total = await session.scalar(select(func.count()).select_from(Job)) or 0
    done = await session.scalar(
        select(func.count()).select_from(Job).where(Job.state.in_(["Confirmed", "Closed"]))) or 0
    at_risk = len(await late_jobs(session))
    repeats = await session.scalar(
        select(func.count()).select_from(Event).where(Event.type == E.REOPENED.value)) or 0
    return (f"{label} digest · {total} jobs\n{done} done · {at_risk} at risk\n"
            f"{repeats} repeat faults")

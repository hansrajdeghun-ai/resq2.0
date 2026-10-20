"""Timers (fast clock): cooling-period close and owner-no-reply -> backup."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.channels.simulator import Simulator
from app.domain import JobState, Role
from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Job
from app.timers import service as T
from scripts.seed import seed_demo

pytestmark = pytest.mark.asyncio


async def test_cooling_timer_closes_confirmed_job(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    # drive to confirmed
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job.id}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job.id}",
                   proof_link="https://capture/x", place="Andheri 400069")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job.id}")

    # not due yet
    assert await T.sweep_cooling(session, now=datetime.now(timezone.utc)) == []
    # fast-forward past the cooling period
    future = datetime.now(timezone.utc) + timedelta(days=8)
    closed = await T.sweep_cooling(session, now=future)
    await session.commit()
    assert job.id in closed
    j = await session.get(Job, job.id)
    assert j.state == JobState.CLOSED.value


async def test_owner_no_reply_offers_backup(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    # owner never replies; 31 minutes later the timer offers to backup
    later = datetime.now(timezone.utc) + timedelta(minutes=31)
    escalated = await T.sweep_owner_no_reply(session, now=later)
    await session.commit()
    assert job.id in escalated
    offers = (await session.scalars(
        select(Event).where(Event.job_id == job.id, Event.type == E.PARTNER_OFFERED.value)
    )).all()
    assert any(o.payload.get("reason") == "owner_no_reply_30m" for o in offers)

"""Spine test: an event round-trips into a read model (step 1 verification)."""
from __future__ import annotations

import pytest

from app.domain import JobState
from app.events import log
from app.events.types import EventType
from app.models.event import Event
from app.models.ledger import Job, Machine

pytestmark = pytest.mark.asyncio


async def test_sold_event_binds_machine_to_household(session):
    await log.append(
        session,
        EventType.SOLD,
        actor="store",
        machine_id="SN-AAA-111",
        payload={
            "serial": "SN-AAA-111",
            "brand": "Samsung",
            "model": "1.5T split AC",
            "category": "AC",
            "customer_id": "cust-1",
            "name": "Mr Sharma",
        },
    )
    await session.commit()

    m = await session.get(Machine, "SN-AAA-111")
    assert m is not None
    assert m.brand == "Samsung"
    assert m.customer_id == "cust-1"


async def test_job_state_advances_through_the_log(session):
    kw = {"machine_id": "SN-AAA-111", "job_id": "R-1001", "actor": "agent"}
    await log.append(session, EventType.INSTALL_REQUESTED,
                     payload={"job_type": "install", "customer_id": "c1",
                              "serial": "SN-AAA-111"}, **kw)
    job = await session.get(Job, "R-1001")
    assert job.state == JobState.REQUESTED.value

    await log.append(session, EventType.PROMISED, payload={"slot": "Sun 10-12"}, **kw)
    await log.append(session, EventType.TECHNICIAN_ASSIGNED,
                     payload={"technician_id": "T-1", "visit_id": "V-5001"}, **kw)
    await log.append(session, EventType.EN_ROUTE, payload={}, **kw)
    await log.append(session, EventType.ARRIVED, payload={}, **kw)
    await log.append(session, EventType.WORK_DONE, payload={}, **kw)
    await log.append(session, EventType.CUSTOMER_CONFIRMED, payload={}, **kw)
    await session.commit()

    job = await session.get(Job, "R-1001")
    assert job.state == JobState.CONFIRMED.value
    assert job.technician_id == "T-1"
    assert job.slot == "Sun 10-12"
    assert job.cooling_until is not None  # cooling period opened

    # append-only: every step is a row, nothing overwritten
    from sqlalchemy import func, select

    count = await session.scalar(select(func.count()).select_from(Event))
    assert count == 7

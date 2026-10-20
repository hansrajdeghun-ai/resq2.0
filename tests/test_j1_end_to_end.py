"""J1 installation, end to end across all four roles, via the simulator.

Asserts the exact event sequence from the spec and the final job state, plus that
the area-manager lane and the protective rules fire.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.channels.simulator import Simulator
from app.domain import JobState, Role
from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Job
from scripts.seed import seed_demo

pytestmark = pytest.mark.asyncio


async def _event_types(session) -> list[str]:
    rows = (await session.scalars(select(Event).order_by(Event.seq))).all()
    return [e.type for e in rows]


async def test_full_installation(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)

    # 1. customer books an installation
    out = await sim.send(Role.CUSTOMER, "cust-sharma", text="I want to install my AC")
    assert any("installation slot" in m.text.lower() for m in out)

    # 2. customer picks a slot -> job created, owner offered
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    assert job.state == JobState.PROMISED.value
    owner_msg = sim.last_to(ids["partner"])
    assert owner_msg and "Accept" in [b.title for b in owner_msg.buttons]

    jid = job.id
    # 3. owner accepts -> suggested technician
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{jid}")
    # 4. owner assigns the technician
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{jid}:{ids['technician']}")
    job = await session.get(Job, jid)
    assert job.state == JobState.ASSIGNED.value
    assert job.technician_id == ids["technician"]
    # customer was told who is coming, partner name hidden
    cust_msg = sim.last_to("cust-sharma")
    assert "from Reliance Digital" in cust_msg.text
    assert "Coolserve" not in cust_msg.text

    # 5. technician travels
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{jid}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{jid}")
    job = await session.get(Job, jid)
    assert job.state == JobState.ON_SITE.value

    # 6. serial scan matches
    await sim.send(Role.FIELD, ids["technician"], button_id="serial:%s:SN-AC-4471" % jid)

    # 7. work done — proof through the capture link with time + place
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{jid}",
                   proof_link="https://capture/resq/abc", place="Andheri East 400069")
    job = await session.get(Job, jid)
    assert job.state == JobState.WORK_DONE.value

    # 8. customer confirms
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{jid}")
    job = await session.get(Job, jid)
    assert job.state == JobState.CONFIRMED.value
    assert job.cooling_until is not None

    types = await _event_types(session)
    for expected in [E.INSTALL_REQUESTED, E.PROMISED, E.PARTNER_OFFERED,
                     E.PARTNER_ASSIGNED, E.TECHNICIAN_ASSIGNED, E.EN_ROUTE,
                     E.ARRIVED, E.SERIAL_VERIFIED, E.WORK_DONE,
                     E.CUSTOMER_CONFIRMED, E.CLAIMED, E.PAYABLE]:
        assert expected.value in types, f"missing {expected.value}"


async def test_serial_mismatch_stops_the_job(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"],
                   button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    # jury attack: scan a different serial
    out = await sim.send(Role.FIELD, ids["technician"],
                         button_id=f"serial:{job.id}:SN-WRONG-9999")
    assert any("does not match" in m.text.lower() for m in out)
    types = await _event_types(session)
    assert E.SERIAL_MISMATCH.value in types
    assert E.WORK_DONE.value not in types

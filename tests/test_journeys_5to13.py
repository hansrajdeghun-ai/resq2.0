"""Smoke coverage for J5-J13 + monitoring (status, take-over, payout run)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.channels.simulator import Simulator
from app.domain import JobState, Role
from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Job, Machine
from scripts.seed import seed_demo

pytestmark = pytest.mark.asyncio


async def _types(session):
    return [e.type for e in (await session.scalars(select(Event).order_by(Event.seq))).all()]


async def test_j11_sale_optin_delivery_opens_install(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.STORE, "store-1", button_id="send_optin:cust-sharma:SN-NEW-1:AC")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="optin:yes:SN-NEW-1")
    await sim.send(Role.FIELD, "driver-1", button_id="out_for_delivery:SN-NEW-1:3302")
    out = await sim.send(Role.FIELD, "driver-1", button_id="deliver:SN-NEW-1:3302",
                         proof_link="https://capture/x")
    assert any("installation slot" in m.text.lower() for m in sim.sent)
    t = await _types(session)
    for e in [E.SOLD, E.OPTED_IN, E.OUT_FOR_DELIVERY, E.SERIAL_BOUND, E.DELIVERED]:
        assert e.value in t


async def test_j5_brand_repair_registers_ticket(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id="brand_repair")
    assert any("track it" in m.text.lower() for m in out)
    t = await _types(session)
    assert E.BRAND_TICKET_OPENED.value in t and E.BRAND_VISIT_PROMISED.value in t


async def test_j6_walk_in_handover_code(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.STORE, "store-1", button_id="walk_in_drop:cust-sharma:SN-PH-1")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.FIELD, "bench-1", button_id=f"walk_in_quote:{job.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"walk_in_approve:{job.id}")
    await sim.send(Role.FIELD, "bench-1", button_id=f"walk_in_ready:{job.id}",
                   proof_link="https://capture/x")
    job = await session.get(Job, job.id)
    code = job.extra["pickup_code"]
    # wrong code is blocked (rule 7)
    out = await sim.send(Role.STORE, "store-1", button_id=f"walk_in_collect:{job.id}:0000")
    assert any("does not match" in m.text.lower() for m in out)
    # correct code hands over
    await sim.send(Role.STORE, "store-1", button_id=f"walk_in_collect:{job.id}:{code}")
    job = await session.get(Job, job.id)
    assert job.state == JobState.CLOSED.value
    assert E.HANDED_OVER.value in await _types(session)


async def test_j7_doa_swap_links_old_to_new(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_doa:SN-AC-4471")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.FIELD, "T-ravi", button_id=f"doa_check:{job.id}",
                   proof_link="https://capture/x")
    await sim.send(Role.AREA, "area-andheri", button_id=f"doa_approve:{job.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"doa_swap:{job.id}")
    old = await session.get(Machine, "SN-AC-4471")
    assert old.replaced_by_serial == "SN-AC-4471-R"
    t = await _types(session)
    assert E.DOA_APPROVED.value in t and E.REPLACED.value in t


async def test_j8_house_move_one_request(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", text="we are moving house")
    from app.models.ledger import ServiceRequest
    req = (await session.scalars(select(ServiceRequest))).first()
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"move_approve:{req.id}")
    await sim.send(Role.FIELD, "owner-a", button_id=f"move_uninstalled:{req.id}")
    await sim.send(Role.FIELD, "owner-b", button_id=f"move_installed:{req.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"move_paid:{req.id}")
    t = await _types(session)
    for e in [E.REQUEST_OPENED, E.QUOTE_APPROVED, E.UNINSTALLED, E.INSTALLED, E.REQUEST_CLOSED]:
        assert e.value in t


async def test_j9_care_plan_binds_policy_to_serial(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="care_plan")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="plan_buy")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="plan_paid")
    t = await _types(session)
    assert E.PLAN_QUOTED.value in t and E.PLAN_BOUGHT.value in t and E.POLICY_BOUND.value in t


async def test_j10_talk_to_person_takes_over_and_silences_agent(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    # open an install job so there is an active job
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="talk_to_person")
    assert any(m.role == Role.AREA for m in sim.sent)
    sim.clear()
    # agent no longer does service work; it forwards to the desk and only acks
    out = await sim.send(Role.CUSTOMER, "cust-sharma", text="any update?")
    assert any(m.role == Role.AREA for m in out)  # forwarded to the desk
    cust_msgs = [m for m in out if m.role == Role.CUSTOMER]
    assert all(not m.buttons for m in cust_msgs)  # just an ack, no service options
    assert E.TAKEN_OVER.value in await _types(session)


async def test_j12_roster_add_and_approve(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.OWNER, "P-coolserve", button_id="add_technician:Sunil:field-sunil")
    await sim.send(Role.FIELD, "T-field-sunil", button_id="tech_join")
    await sim.send(Role.FIELD, "T-field-sunil", button_id="tech_skill:AC install")
    await sim.send(Role.AREA, "area-andheri", button_id="tech_approve:T-field-sunil")
    from app.models.people import Technician
    t = await session.get(Technician, "T-field-sunil")
    assert t.approved is True
    assert E.TECHNICIAN_APPROVED.value in await _types(session)


async def test_j13_payout_run_pays_after_cooling(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    # drive an install to confirmed
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

    # cooling not done -> held
    out = await sim.send(Role.AREA, "finance-1", button_id="approve_payout")
    assert any("held" in m.text.lower() for m in out)
    assert E.PAYABLE.value in await _types(session)

    # move cooling into the past -> paid
    job = await session.get(Job, job.id)
    job.cooling_until = datetime.now(timezone.utc) - timedelta(days=1)
    await session.commit()
    await sim.send(Role.AREA, "finance-1", button_id="approve_payout")
    t = await _types(session)
    assert E.PAYOUT_APPROVED.value in t and E.PAID.value in t


async def test_monitoring_status_and_digest(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    out = await sim.send(Role.AREA, "area-andheri", text=f"status {job.id}")
    assert any(job.id in m.text for m in out)
    out = await sim.send(Role.AREA, "area-andheri", button_id="digest")
    assert any("digest" in m.text.lower() for m in out)

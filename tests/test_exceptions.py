"""Exception table coverage (spec 4.1). Each test maps to a row the jury may try.

Rows and where they are handled:
  Serial mismatch at the door          -> SerialMismatch, job stopped, area alerted
  Self-check fixes the fault           -> SelfFixed, closed with no visit
  Owner declines / no reply            -> offer to backup, then escalate + customer retry
  Estimate declined                    -> visit charge only, job not continued
  Brand misses its visit               -> BrandMissed + Escalated, customer told
  Customer replies "Not yet"           -> free revisit (Reopened)
  Part delayed (two visits)            -> customer told before the old date (J3)
  No payout before confirm + cooling   -> Held, not Paid
"""
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
PROOF = {"proof_link": "https://capture.resq/x", "place": "Andheri 400069"}


async def _types(s):
    return [e.type for e in (await s.scalars(select(Event).order_by(Event.seq))).all()]


async def _onsite(session, sim, ids):
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    return job.id


async def test_serial_mismatch_stops_job(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    out = await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-WRONG")
    assert any("does not match" in m.text.lower() for m in out)
    t = await _types(session)
    assert E.SERIAL_MISMATCH.value in t and E.WORK_DONE.value not in t


async def test_self_check_closes_without_visit(session):
    await seed_demo(session); await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_fault")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"self_fixed:{job.id}")
    job = await session.get(Job, job.id)
    assert job.state == JobState.CLOSED.value
    t = await _types(session)
    assert E.SELF_FIXED.value in t and E.TECHNICIAN_ASSIGNED.value not in t


async def test_decline_escalates_and_offers_customer_retry(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_decline:{job.id}")  # -> backup
    out = await sim.send(Role.OWNER, ids["partner"], button_id=f"job_decline:{job.id}")  # -> escalate
    # exactly two offers (primary + backup), then escalate; customer gets retry slots
    offers = sum(1 for x in await _types(session) if x == E.PARTNER_OFFERED.value)
    assert offers == 2
    assert E.ALERT_SENT.value in await _types(session)
    cust = [m for m in out if m.role == Role.CUSTOMER]
    assert cust and cust[-1].buttons  # retry slot buttons offered


async def test_estimate_declined_charges_visit_only(session):
    ids = await seed_demo(session)
    m = await session.get(Machine, "SN-AC-4471")
    m.wty_end = datetime.now(timezone.utc) - timedelta(days=30)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_oow")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job.id}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"oow_diagnose:{job.id}")
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_decline:{job.id}")
    assert any("visit charge" in m.text.lower() and "₹299" in m.text for m in out)
    assert E.ESTIMATE_DECLINED.value in await _types(session)


async def test_brand_miss_escalates_and_tells_customer(session):
    await seed_demo(session); await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="brand_repair")
    job = (await session.scalars(select(Job))).first()
    out = await sim.send(Role.AREA, "area-andheri", button_id=f"brand_missed:{job.id}")
    assert any("escalated" in m.text.lower() for m in out if m.role == Role.CUSTOMER)
    t = await _types(session)
    assert E.BRAND_MISSED.value in t and E.ESCALATED.value in t


async def test_not_yet_opens_free_revisit(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job}", **PROOF)
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_no:{job}")
    assert any("revisit" in m.text.lower() for m in out)
    assert E.REOPENED.value in await _types(session)


async def test_payment_fails_twice_hands_to_desk(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    await sim.send(Role.FIELD, ids["technician"], button_id=f"payment_failed:{job}")
    out = await sim.send(Role.FIELD, ids["technician"], button_id=f"payment_failed:{job}")
    assert any("resQ desk" in m.text for m in out)
    assert E.HANDED_TO_PERSON.value in await _types(session)


async def test_site_not_ready_offers_new_slots(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    out = await sim.send(Role.FIELD, ids["technician"], button_id=f"site_not_ready:{job}",
                         proof_link="https://capture/x")
    assert any(m.role == Role.CUSTOMER and m.buttons for m in out)
    assert E.SITE_NOT_READY.value in await _types(session)


async def test_doa_rejected_escalates_to_desk(session):
    await seed_demo(session); await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_doa:SN-AC-4471")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.FIELD, "T-ravi", button_id=f"doa_check:{job.id}", **PROOF)
    await sim.send(Role.AREA, "area-andheri", button_id=f"doa_reject:{job.id}")
    t = await _types(session)
    assert E.ESCALATED.value in t and E.HANDED_TO_PERSON.value in t


async def test_waiting_confirm_timer_reminds(session):
    from app.timers import service as T
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job}", **PROOF)
    future = datetime.now(timezone.utc) + timedelta(hours=25)
    reminded = await T.sweep_waiting_confirm(session, now=future)
    await session.commit()
    assert job in reminded
    assert E.REMINDER_SENT.value in await _types(session)


async def test_no_payout_before_cooling(session):
    ids = await seed_demo(session); await session.commit()
    sim = Simulator(session)
    job = await _onsite(session, sim, ids)
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job}", **PROOF)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job}")
    out = await sim.send(Role.AREA, "finance-1", button_id="approve_payout")
    assert any("held" in m.text.lower() for m in out)
    t = await _types(session)
    assert E.HELD.value in t and E.PAID.value not in t

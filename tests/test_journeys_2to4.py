"""End-to-end: J2 repair, J3 repair-with-part, J4 out-of-warranty + payment."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.channels.simulator import Simulator
from app.domain import JobState, Role
from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Job
from app.models.ops import Payment
from scripts.seed import seed_demo

pytestmark = pytest.mark.asyncio


async def _types(session):
    return [e.type for e in (await session.scalars(select(Event).order_by(Event.seq))).all()]


async def _drive_to_onsite(sim, ids, book_intent, slot_intent):
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=book_intent)
    job = (await sim.session.scalars(select(Job).order_by(Job.created_at.desc()))).first()
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=slot_intent.format(job=job.id))
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    return job.id


async def test_j2_self_check_fixes_it(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", text="my AC is not cooling")
    job = (await session.scalars(select(Job))).first()
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"self_fixed:{job.id}")
    assert any("no visit" in m.text.lower() for m in out)
    job = await session.get(Job, job.id)
    assert job.state == JobState.CLOSED.value
    t = await _types(session)
    assert E.SELF_CHECK_SENT.value in t and E.SELF_FIXED.value in t


async def test_j2_full_repair_in_warranty(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_fault")
    job = (await session.scalars(select(Job))).first()
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"still_broken:{job.id}")
    assert any("warranty" in m.text.lower() for m in out)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="rslot:Tue 4-6")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job.id}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job.id}",
                   proof_link="https://capture/x", place="Andheri 400069")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job.id}")
    job = await session.get(Job, job.id)
    assert job.state == JobState.CONFIRMED.value
    t = await _types(session)
    for e in [E.WARRANTY_CHECKED, E.PRE_DIAGNOSED, E.SERIAL_VERIFIED, E.WORK_DONE]:
        assert e.value in t


async def test_j3_part_flow_two_visits(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    # get a repair job on site
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_fault")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"still_broken:{job.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="rslot:Tue 4-6")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    # part not in the bag
    await sim.send(Role.FIELD, ids["technician"], button_id=f"part_needed:{job.id}:gas pressure")
    j = await session.get(Job, job.id)
    assert j.state == JobState.WAITING_FOR_PART.value
    # part arrives, visit 2 booked, same technician
    await sim.send(Role.OWNER, ids["partner"], button_id=f"part_received:{job.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"v2slot:{job.id}:Thu 4-6")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job.id}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"part_fitted:{job.id}",
                   proof_link="https://capture/x", place="Andheri 400069")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job.id}")
    j = await session.get(Job, job.id)
    assert j.state == JobState.CONFIRMED.value
    t = await _types(session)
    for e in [E.PART_NEEDED, E.PART_DISPATCHED, E.PART_RECEIVED, E.VISIT_OPENED,
              E.PART_USED, E.RETURN_OPENED]:
        assert e.value in t


async def test_j4_out_of_warranty_pay_by_upi(session):
    ids = await seed_demo(session)
    # make the machine out of warranty
    from app.models.ledger import Machine
    from datetime import datetime, timezone, timedelta
    m = await session.get(Machine, "SN-AC-4471")
    m.wty_end = datetime.now(timezone.utc) - timedelta(days=30)
    await session.commit()
    sim = Simulator(session)
    out = await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_oow")
    assert any("₹299" in m.text for m in out)
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_book:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job.id}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job.id}:SN-AC-4471")
    out = await sim.send(Role.FIELD, ids["technician"], button_id=f"oow_diagnose:{job.id}")
    # estimate = leak_repair 850 + gas_refill 2200 = 3050
    assert any("3050" in m.text for m in sim.sent)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_approve:{job.id}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job.id}",
                   proof_link="https://capture/x", place="Andheri 400069")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"oow_pay:{job.id}")
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_paid:{job.id}")
    pay = await session.get(Payment, f"PAY-{job.id}")
    assert pay.status == "paid" and float(pay.amount) == 3050.0
    t = await _types(session)
    assert E.PAYMENT_RECEIVED.value in t and E.INVOICE_SENT.value in t

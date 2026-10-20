"""Drive all 13 journeys (J1-J13) end to end and print each event sequence.

A hand-in artifact: proves every journey runs and shows its append-only event trail.
Runs offline on in-memory SQLite (no LLM, no network). Usage:

    python -m scripts.run_all_journeys
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.channels.simulator import Simulator
from app.db import Base
from app.domain import Role
from app.models.event import Event
from scripts.seed import seed_demo

settings.anthropic_api_key = ""  # force offline/deterministic
settings.openai_api_key = ""

PROOF = {"proof_link": "https://capture.resq/x", "place": "Andheri 400069"}


async def _fresh():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    import app.models  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    s = async_sessionmaker(engine, expire_on_commit=False)()
    ids = await seed_demo(s)
    await s.commit()
    return engine, s, Simulator(s), ids


async def _events(s) -> list[str]:
    return [e.type for e in (await s.scalars(select(Event).order_by(Event.seq))).all()]


async def _job_id(s):
    from app.models.ledger import Job
    j = (await s.scalars(select(Job).order_by(Job.created_at.desc()))).first()
    return j.id if j else None


async def run(label, steps):
    engine, s, sim, ids = await _fresh()
    ctx = {"sim": sim, "ids": ids, "s": s}
    await steps(ctx)
    await s.commit()
    evs = await _events(s)
    print(f"✓ {label}\n    {len(evs)} events: {' · '.join(evs)}\n")
    await s.close()
    await engine.dispose()


async def _assign_and_visit(ctx, job, fault=False):
    sim, ids = ctx["sim"], ctx["ids"]
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job}")
    await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job}:{ids['technician']}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job}")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
    await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job}", **PROOF)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job}")


async def main():
    async def j1(ctx):
        await ctx["sim"].send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
        await _assign_and_visit(ctx, "R-1001")
    await run("J1 · Installation", j1)

    async def j2(ctx):
        sim = ctx["sim"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_fault")
        job = await _job_id(ctx["s"])
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"still_broken:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="rslot:Tue 4-6")
        await _assign_and_visit(ctx, job)
    await run("J2 · Repair at home", j2)

    async def j3(ctx):
        sim, ids = ctx["sim"], ctx["ids"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_fault")
        job = await _job_id(ctx["s"])
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"still_broken:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="rslot:Tue 4-6")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job}")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job}:{ids['technician']}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"part_needed:{job}:gas pressure")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"part_received:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"v2slot:{job}:Thu 4-6")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"part_fitted:{job}", **PROOF)
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"confirm_work:{job}")
    await run("J3 · Repair with a part (two visits)", j3)

    async def j4(ctx):
        from datetime import datetime, timedelta, timezone
        from app.models.ledger import Machine
        s, sim, ids = ctx["s"], ctx["sim"], ctx["ids"]
        m = await s.get(Machine, "SN-AC-4471")
        m.wty_end = datetime.now(timezone.utc) - timedelta(days=30); await s.commit()
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_oow")
        job = await _job_id(s)
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_book:{job}")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job}")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"assign_tech:{job}:{ids['technician']}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"on_my_way:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"arrived:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"serial:{job}:SN-AC-4471")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"oow_diagnose:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_approve:{job}")
        await sim.send(Role.FIELD, ids["technician"], button_id=f"work_done:{job}", **PROOF)
        await sim.send(Role.FIELD, ids["technician"], button_id=f"oow_pay:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"oow_paid:{job}")
    await run("J4 · Out-of-warranty repair", j4)

    async def j5(ctx):
        await ctx["sim"].send(Role.CUSTOMER, "cust-sharma", button_id="brand_repair")
        job = await _job_id(ctx["s"])
        await ctx["sim"].send(Role.CUSTOMER, "cust-sharma", button_id=f"brand_confirm:{job}")
    await run("J5 · Repair by another brand", j5)

    async def j6(ctx):
        sim = ctx["sim"]
        await sim.send(Role.STORE, "store-1", button_id="walk_in_drop:cust-sharma:SN-PH-1")
        job = await _job_id(ctx["s"])
        await sim.send(Role.FIELD, "bench-1", button_id=f"walk_in_quote:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"walk_in_approve:{job}")
        await sim.send(Role.FIELD, "bench-1", button_id=f"walk_in_ready:{job}", **PROOF)
        from app.models.ledger import Job
        code = (await ctx["s"].get(Job, job)).extra["pickup_code"]
        await sim.send(Role.STORE, "store-1", button_id=f"walk_in_collect:{job}:{code}")
    await run("J6 · Walk-in repair at the store", j6)

    async def j7(ctx):
        sim = ctx["sim"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="report_doa:SN-AC-4471")
        job = await _job_id(ctx["s"])
        await sim.send(Role.FIELD, "T-ravi", button_id=f"doa_check:{job}", **PROOF)
        await sim.send(Role.AREA, "area-andheri", button_id=f"doa_approve:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"doa_swap:{job}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"doa_close:{job}")
    await run("J7 · Dead on arrival", j7)

    async def j8(ctx):
        from app.models.ledger import ServiceRequest
        sim = ctx["sim"]
        await sim.send(Role.CUSTOMER, "cust-sharma", text="we are moving house")
        req = (await ctx["s"].scalars(select(ServiceRequest))).first()
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"move_approve:{req.id}")
        await sim.send(Role.FIELD, "owner-a", button_id=f"move_uninstalled:{req.id}")
        await sim.send(Role.FIELD, "owner-b", button_id=f"move_installed:{req.id}")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"move_paid:{req.id}")
    await run("J8 · House move", j8)

    async def j9(ctx):
        sim = ctx["sim"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="care_plan")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="plan_buy")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="plan_paid")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="service_done")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="plan_renew")
    await run("J9 · Maintenance and care plan", j9)

    async def j10(ctx):
        sim = ctx["sim"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
        job = await _job_id(ctx["s"])
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="complain")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id=f"fix_accept:{job}")
    await run("J10 · Complaint and escalation", j10)

    async def j11(ctx):
        sim = ctx["sim"]
        await sim.send(Role.STORE, "store-1", button_id="send_optin:cust-sharma:SN-NEW-1:AC")
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="optin:yes:SN-NEW-1")
        await sim.send(Role.FIELD, "driver-1", button_id="out_for_delivery:SN-NEW-1:3302")
        await sim.send(Role.FIELD, "driver-1", button_id="deliver:SN-NEW-1:3302", proof_link="https://capture/x")
    await run("J11 · Sale, opt-in and delivery", j11)

    async def j12(ctx):
        sim = ctx["sim"]
        await sim.send(Role.OWNER, "P-coolserve", button_id="add_technician:Sunil:field-sunil")
        await sim.send(Role.FIELD, "T-field-sunil", button_id="tech_join")
        await sim.send(Role.FIELD, "T-field-sunil", button_id="tech_skill:AC install")
        await sim.send(Role.AREA, "area-andheri", button_id="tech_approve:T-field-sunil")
        await sim.send(Role.FIELD, "T-field-sunil", button_id="start_day")
        await sim.send(Role.FIELD, "T-field-sunil", button_id="confirm_capacity:5")
    await run("J12 · Technician roster", j12)

    async def j13(ctx):
        from datetime import datetime, timedelta, timezone
        from app.models.ledger import Job
        s, sim, ids = ctx["s"], ctx["sim"], ctx["ids"]
        await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
        job = await _job_id(s)
        await _assign_and_visit(ctx, job)
        j = await s.get(Job, job)
        j.cooling_until = datetime.now(timezone.utc) - timedelta(days=1); await s.commit()
        await sim.send(Role.AREA, "finance-1", button_id="approve_payout")
        await sim.send(Role.OWNER, ids["partner"], button_id=f"dispute:{job}")
    await run("J13 · Payouts and disputes", j13)

    print("All 13 journeys ran end to end. ✓")


if __name__ == "__main__":
    asyncio.run(main())

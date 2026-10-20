"""Watch a full J1 installation play out across the four WhatsApp numbers.

Run: python -m scripts.demo_j1
Prints each inbound tap and the replies each role receives, plus the area lane.
"""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.channels.simulator import Simulator
from app.db import Base
from app.domain import Role
from scripts.seed import seed_demo

ROLE_ICON = {Role.CUSTOMER: "👤 customer", Role.OWNER: "🏪 owner",
             Role.FIELD: "🔧 field", Role.AREA: "🧭 area"}


def show(title: str, out) -> None:
    print(f"\n── {title} ──")
    for m in out:
        who = ROLE_ICON.get(m.role, m.role)
        btns = "  ".join(f"[{b.title}]" for b in m.buttons)
        line = m.text.replace("\n", " / ")
        print(f"  → {who}: {line}" + (f"   {btns}" if btns else ""))


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    import app.models  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        ids = await seed_demo(s)
        await s.commit()
        sim = Simulator(s)
        P, T = ids["partner"], ids["technician"]

        show("customer: 'my AC needs fitting'",
             await sim.send(Role.CUSTOMER, "cust-sharma", text="my AC needs fitting"))
        show("customer picks Sunday 10-12",
             await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12"))
        show("owner accepts",
             await sim.send(Role.OWNER, P, button_id="job_accept:R-1001"))
        show("owner assigns Ravi",
             await sim.send(Role.OWNER, P, button_id=f"assign_tech:R-1001:{T}"))
        show("Ravi: on my way",
             await sim.send(Role.FIELD, T, button_id="on_my_way:R-1001"))
        show("Ravi: arrived",
             await sim.send(Role.FIELD, T, button_id="arrived:R-1001"))
        show("Ravi scans the serial",
             await sim.send(Role.FIELD, T, button_id="serial:R-1001:SN-AC-4471"))
        show("Ravi: work done (proof via capture link)",
             await sim.send(Role.FIELD, T, button_id="work_done:R-1001",
                            proof_link="https://capture/resq/abc",
                            place="Andheri East 400069"))
        show("customer confirms it works",
             await sim.send(Role.CUSTOMER, "cust-sharma", button_id="confirm_work:R-1001"))

        from app.models.ledger import Job
        job = await s.get(Job, "R-1001")
        print(f"\n✅ {job.id} final state: {job.state} · cooling until {job.cooling_until:%d %b}")


if __name__ == "__main__":
    asyncio.run(main())

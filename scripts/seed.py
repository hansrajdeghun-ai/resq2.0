"""Seed demo data: a household + machine, a service partner + technician, a backup.

Used by tests and the demo when live partner/technician masters aren't available.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import Customer, Machine
from app.models.people import ServicePartner, Technician


async def seed_demo(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)

    customer = Customer(
        id="cust-sharma", name="Mr Sharma", phone="98xxxxx210",
        language="en", opted_in=True,
        address={"city": "Mumbai", "postal_code": "400069", "area": "Andheri East"},
    )
    machine = Machine(
        serial="SN-AC-4471", object_id="900000012345", brand="Samsung",
        model="1.5T split AC", category="AC", customer_id="cust-sharma",
        sales_order_no="6000012345", date_of_purchase=now,
        wty_start=now, wty_end=now + timedelta(days=730), authority="Reliance",
    )
    coolserve = ServicePartner(
        id="P-coolserve", name="Coolserve Services", phone="owner-coolserve",
        pincodes=["400069"], authority=["AC", "ALL"], partner_class="contracted",
    )
    backup = ServicePartner(
        id="P-backup", name="QuickFix", phone="owner-backup",
        pincodes=["400069"], authority=["AC", "ALL"], is_backup=True,
    )
    ravi = Technician(
        id="T-ravi", name="Ravi Kumar", phone="field-ravi", partner_id="P-coolserve",
        skills=["AC", "AC install"], pincode="400069", approved=True, id_checked=True,
        day_started_on=now, capacity_slots=5, rating=4.8,
    )
    session.add_all([customer, machine, coolserve, backup, ravi])
    await session.flush()
    return {"customer": customer.id, "machine": machine.serial,
            "partner": coolserve.id, "backup": backup.id, "technician": ravi.id}


async def _main() -> None:
    from app.db import SessionLocal, init_db

    await init_db()
    async with SessionLocal() as s:
        ids = await seed_demo(s)
        await s.commit()
        print("seeded:", ids)


if __name__ == "__main__":
    asyncio.run(_main())

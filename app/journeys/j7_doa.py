"""J7 — Dead on arrival (spec page 12).

A new product fails in the first days. A technician checks it against the brand's DOA
window + checklist, the brand approves, and the store swaps it. The old machine record
is kept, marked Replaced, with a link to the new serial.

Events: FaultReported · DOACheckOpened · DOAReported · DOAApproved · ReplacementReserved
· Delivered(new) · Collected(old) · Replaced · InstallRequested
"""
from __future__ import annotations

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_job_id


@on("report_doa")
async def report_doa(ctx: Ctx) -> None:
    parts = ctx.intent.split(":")
    serial = parts[1] if len(parts) > 1 else "SN-AC-4471"
    machine = await ctx.machine(serial)
    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)
    await ctx.emit(E.FAULT_REPORTED, actor="agent", job_id=job_id, machine_id=serial,
                   payload={"job_type": "doa", "customer_id": ctx.customer_id,
                            "serial": serial})
    await ctx.emit(E.DOA_CHECK_OPENED, actor="agent", job_id=job_id,
                   payload={"same_day": True})
    cust_id = machine.customer_id if machine else ctx.customer_id
    ctx.to(cust_id, Role.CUSTOMER,
           "Sorry about that.\nA technician will check it today.\nIf faulty, we replace it.",
           buttons=[(f"doa_ok:{job_id}", "OK")])
    ctx.say(f"{job_id}: DOA check opened · same-day slot.")
    ctx.area(f"{job_id}: DOA reported · priority same-day")


@on("doa_check")
async def doa_check(ctx: Ctx) -> None:
    """Technician fills the brand DOA checklist + photos."""
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.DOA_REPORTED, actor="field", job_id=job_id,
                   proof_link=ctx.inbound.raw.get("proof_link"),
                   payload={"checklist": "sealed-system fault", "photos": 3})
    ctx.say(f"{job_id}: DOA report built.\nSent to the brand for approval.",
            buttons=[(f"doa_approve:{job_id}", "Brand approves")])
    ctx.area(f"{job_id}: DOA checklist + 3 photos · sent to brand")


@on("doa_approve")
async def doa_approve(ctx: Ctx) -> None:
    """Brand approves the DOA; the store reserves a replacement unit."""
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.DOA_APPROVED, actor="area", job_id=job_id, payload={})
    await ctx.emit(E.REPLACEMENT_RESERVED, actor="agent", job_id=job_id, payload={})
    job = await ctx.job(job_id)
    ctx.to(job.customer_id, Role.CUSTOMER,
           "Your unit is faulty.\nWe will replace it. Delivery Saturday.",
           buttons=[(f"doa_swap:{job_id}", "OK")])
    ctx.area(f"{job_id}: brand approved DOA · replacement reserved")


@on("doa_swap")
async def doa_swap(ctx: Ctx) -> None:
    """New unit delivered, old collected; old record linked to the new serial."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    old_serial = job.machine_serial
    new_serial = f"{old_serial}-R" if old_serial else "SN-NEW-R"
    await ctx.emit(E.DELIVERED, actor="store", machine_id=new_serial,
                   payload={"serial": new_serial, "customer_id": job.customer_id,
                            "category": "AC", "brand": "Whirlpool"})
    await ctx.emit(E.SERIAL_BOUND, actor="store", machine_id=new_serial,
                   payload={"serial": new_serial, "customer_id": job.customer_id})
    await ctx.emit(E.COLLECTED, actor="store", machine_id=old_serial,
                   payload={"old_serial": old_serial})
    await ctx.emit(E.REPLACED, actor="agent", machine_id=old_serial,
                   payload={"replaced_by_serial": new_serial})
    # mark the old machine Replaced with a link to the new serial
    if old_serial:
        old = await ctx.machine(old_serial)
        if old:
            old.replaced_by_serial = new_serial
    ctx.to(job.customer_id, Role.CUSTOMER,
           "New unit delivered, old one collected.\nNeed installation?",
           buttons=[(f"book_install", "Book installation"),
                    (f"doa_close:{job_id}", "Not needed")])
    ctx.say(f"{job_id}: swapped · old {old_serial} -> new {new_serial}.")
    ctx.area(f"{job_id}: swapped · old collected · new bound")


@on("doa_close")
async def doa_close(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.CLOSED, actor="agent", job_id=job_id, payload={})
    ctx.say("All done.\nYour new unit is in your Reliance record.")
    ctx.area(f"{job_id}: closed · no installation")


@on("doa_ok")
async def doa_ok(ctx: Ctx) -> None:
    ctx.say("Thanks. We will keep you posted today.")

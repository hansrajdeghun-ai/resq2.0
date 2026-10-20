"""Shared assignment steps B2 (offer & assign) — reused by J1, J2, J3, J4, J7.

The service owner accepts/declines a job; on accept the agent suggests a technician;
the owner assigns; the customer is told who is coming (partner name hidden) and the
technician gets the job card. No reply in 30 min -> offer to backup (handled by timers).
"""
from __future__ import annotations

from app.domain import JobState, Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_visit_id
from app.journeys import _helpers as H


async def offer_to_owner(ctx: Ctx, job_id: str, partner, summary: str) -> None:
    """B2: reserve and offer the job to a service owner."""
    await ctx.emit(E.PARTNER_OFFERED, actor="agent", job_id=job_id,
                   payload={"partner_id": partner.id})
    ctx.to(partner.id, Role.OWNER,
           f"{summary}\nAccept this job?",
           buttons=[(f"job_accept:{job_id}", "Accept"),
                    (f"job_decline:{job_id}", "Decline")])


@on("job_accept")
async def owner_accept(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    if not job:
        ctx.say(f"{job_id} no longer exists.\nIt may have been cancelled.")
        return
    if job.technician_id:
        ctx.say(f"{job_id} is already assigned.\nNo action needed.")
        return
    await ctx.emit(E.PARTNER_ASSIGNED, actor="owner", job_id=job_id,
                   payload={"partner_id": ctx.inbound.from_id})
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    category = machine.category if machine else None
    tech = await H.pick_technician(ctx.session, ctx.inbound.from_id, category)
    if tech is None:
        ctx.say("No active technician.\nPlease add one or share back.")
        ctx.area(f"{job_id}: owner has no active technician")
        return
    await ctx.suggest(job_id, f"Assign {H.first_name(tech.name)} to {job_id}",
                      tool="assign_technician", args={"technician_id": tech.id})
    ctx.say(f"Assign a technician for {job_id}:",
            buttons=[(f"assign_tech:{job_id}:{tech.id}",
                      f"{H.first_name(tech.name)} · suggested")])


@on("job_decline")
async def owner_decline(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    if not job:
        ctx.say(f"{job_id} no longer exists.")
        return
    if job.technician_id:
        ctx.say(f"{job_id} is already assigned to another partner.")
        return
    await ctx.emit(E.PARTNER_DECLINED, actor="owner", job_id=job_id, payload={})
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    # cap offers per job: primary + one backup, then escalate (prevents a re-offer loop)
    from sqlalchemy import func, select
    from app.models.event import Event
    offers = await ctx.session.scalar(
        select(func.count()).select_from(Event)
        .where(Event.job_id == job_id, Event.type == E.PARTNER_OFFERED.value)) or 0
    backup = await H.pick_partner(ctx.session, machine.category if machine else None,
                                  None, backup=True)
    if backup and backup.id != ctx.inbound.from_id and offers < 2:
        ctx.say("Shared to the backup partner.")
        await offer_to_owner(ctx, job_id, backup, f"New job · {job_id}\nBackup offer.")
        ctx.area(f"{job_id}: declined · offered to backup")
    else:
        ctx.say("Declined. No other partner is free — the area manager will step in.")
        from app.monitoring.service import raise_alert
        await raise_alert(ctx.session, job_id, cause="no_partner",
                          text=f"{job_id}: no partner accepted", action="reassign")
        # notify the customer and offer a retry (a different slot)
        if job.customer_id:
            slots = H.offer_slots() if job.type == "install" else H.repair_slots()
            ctx.to(job.customer_id, Role.CUSTOMER,
                   "Sorry, we need a little longer to assign a technician.\n"
                   "Pick another slot and we will try again:", buttons=slots)
        ctx.area(f"{job_id}: declined · no backup · customer offered a retry · area alerted")


@on("assign_tech")
async def assign_technician(ctx: Ctx) -> None:
    from app.models.people import Technician

    _, job_id, tech_id = ctx.intent.split(":", 2)
    job = await ctx.job(job_id)
    tech = await ctx.session.get(Technician, tech_id)
    if not job:
        ctx.say(f"{job_id} no longer exists.")
        return
    if not tech:
        ctx.say("That technician is not on the roster.\nAdd them in Admin → People.")
        return
    if job.technician_id:
        ctx.say(f"{job_id} already has a technician.")
        return
    visit_id = await next_visit_id(ctx.session)
    await ctx.emit(E.TECHNICIAN_ASSIGNED, actor="owner", job_id=job_id,
                   payload={"technician_id": tech_id, "visit_id": visit_id,
                            "visit_number": 1, "slot": job.slot,
                            "payable": job.extra.get("payable", True) if job.extra else True})
    ctx.say(f"{H.first_name(tech.name)} is assigned to {job_id}.")

    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "machine"
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"{H.first_name(tech.name)} from Reliance Digital\n"
           f"will {H.verb(job.type)} your {cat} on {job.slot}.")
    ctx.to(tech_id, Role.FIELD,
           f"New job · {job.slot} · {job_id}\n{cat}\nAccept?",
           buttons=[(f"on_my_way:{job_id}", "On my way")])
    ctx.area(f"{job_id}: assigned {H.first_name(tech.name)} · {job.slot}")

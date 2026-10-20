"""J5 — Repair by another brand (spec page 10).

The brand does the repair. The agent registers the complaint with the brand (Kapture
B2B complaint create — mocked until the checksum key arrives), tracks it in the
customer's thread, and escalates if the brand misses the visit. The customer never
has to call the brand.

Events: AuthorityChecked(brand) · BrandTicketOpened · BrandVisitPromised · BrandMissed
· Escalated · CustomerConfirmed · Closed
"""
from __future__ import annotations

from sqlalchemy import select

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_job_id
from app.integrations.kapture import get_kapture
from app.models.ledger import Machine


@on("brand_repair")
async def brand_repair(ctx: Ctx) -> None:
    from app.journeys import _helpers as H

    machines = await H.owned_machines(ctx.session, ctx.customer_id)
    if not machines:
        ctx.say("I don't see a machine on your account yet.")
        return
    machine = H.match_category(machines, ctx.inbound.text) or machines[0]
    brand = (machine.brand if machine else "the brand")
    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)
    await ctx.emit(E.AUTHORITY_CHECKED, actor="agent", job_id=job_id,
                   machine_id=machine.serial if machine else None,
                   payload={"job_type": "brand_repair", "customer_id": ctx.customer_id,
                            "serial": machine.serial if machine else None,
                            "authority": brand})
    # register the complaint with the brand via Kapture (mock when no checksum key)
    result = await get_kapture().b2b_complaint_create(
        {"KAPTURECOMPLTNO": job_id[-10:], "REFERENCETRANSACTION": job_id,
         "CATEGORY": "BRAND_REPAIR"}, transaction_number=job_id)
    ticket = result.get("complaint_return", {}).get("crmcomplaintid", "pending")
    await ctx.emit(E.BRAND_TICKET_OPENED, actor="agent", job_id=job_id,
                   payload={"brand": brand, "ticket": ticket})
    await ctx.emit(E.BRAND_VISIT_PROMISED, actor="agent", job_id=job_id,
                   payload={"brand": brand, "by": "Thursday"})
    ctx.say(f"{brand} repairs this one.\nWe booked it (ref {ticket}) and will track it for you.")
    ctx.area(f"{job_id}: brand repair · {brand} ticket {ticket} · visit by Thursday")


@on("brand_missed")
async def brand_missed(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    await ctx.emit(E.BRAND_MISSED, actor="agent", job_id=job_id, payload={})
    await ctx.emit(E.ESCALATED, actor="agent", job_id=job_id, payload={})
    ctx.to(job.customer_id, Role.CUSTOMER,
           "The brand missed the visit.\nWe escalated it and will get a new time.")
    ctx.area(f"{job_id}: brand missed · escalated")


@on("brand_confirm")
async def brand_confirm(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.CUSTOMER_CONFIRMED, actor="customer", job_id=job_id, payload={})
    await ctx.emit(E.CLOSED, actor="agent", job_id=job_id, payload={})
    ctx.say("Good to hear.\nThe brand repair is in your Reliance record.")
    ctx.area(f"{job_id}: brand repair confirmed · closed")

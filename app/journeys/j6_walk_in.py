"""J6 — Walk-in repair at the store (spec page 11).

The customer leaves the product at the store, tracks it on WhatsApp, and collects it
with a one-time code (rule 7). Prices from the rate card; pay by UPI or at the store.

Events: WalkInReceived · ConditionRecorded · Diagnosed · EstimateApproved · WorkDone ·
ReadyForPickup · PaymentReceived · HandedOver · CustomerConfirmed · Closed
"""
from __future__ import annotations

import random

from app.data import rate_card
from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.errors import ProtectiveRuleError
from app.events.types import EventType as E
from app.ids import next_job_id
from app.rules import protective as pr


@on("walk_in_drop")
async def walk_in_drop(ctx: Ctx) -> None:
    """Store associate scans the product at drop-off (condition photos)."""
    parts = ctx.intent.split(":")
    cust_id = parts[1] if len(parts) > 1 else "cust-sharma"
    serial = parts[2] if len(parts) > 2 else "SN-PH-3390"
    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)
    await ctx.emit(E.WALK_IN_RECEIVED, actor="store", job_id=job_id, machine_id=serial,
                   payload={"job_type": "walk_in", "customer_id": cust_id, "serial": serial,
                            "category": "PHONE"})
    await ctx.emit(E.CONDITION_RECORDED, actor="store", job_id=job_id,
                   proof_link=ctx.inbound.raw.get("proof_link"),
                   payload={"photos": 3})
    ctx.to(cust_id, Role.CUSTOMER,
           f"Job {job_id} for your phone.\nCondition photos recorded.\nUpdate by 3 pm today.")
    ctx.say(f"{job_id}: walk-in received · 3 photos.")
    ctx.area(f"{job_id}: walk-in · condition recorded")


@on("walk_in_quote")
async def walk_in_quote(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    price = rate_card.price_of("PHONE", "screen_replace") or 6400.0
    pr.assert_price_on_card("PHONE", price)
    await ctx.emit(E.DIAGNOSED, actor="field", job_id=job_id, payload={"fault": "screen"})
    await ctx.emit(E.ESTIMATE_SENT, actor="agent", job_id=job_id, payload={"total": price})
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"Screen replacement ₹{price:.0f}.\nApprove to start?",
           buttons=[(f"walk_in_approve:{job_id}", "Approve"),
                    (f"walk_in_decline:{job_id}", "Decline")])
    ctx.area(f"{job_id}: diagnosed · estimate ₹{price:.0f}")


@on("walk_in_approve")
async def walk_in_approve(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.ESTIMATE_APPROVED, actor="customer", job_id=job_id, payload={})
    ctx.say("Approved. The service bench will start.")
    ctx.area(f"{job_id}: estimate approved · in progress")


@on("walk_in_ready")
async def walk_in_ready(ctx: Ctx) -> None:
    """Work done -> ready for pickup with a one-time code (rule 7)."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    await ctx.emit(E.WORK_DONE, actor="field", job_id=job_id,
                   proof_link=ctx.inbound.raw.get("proof_link"), payload={"tested": True})
    code = f"{random.randint(1000, 9999)}"
    job.extra = {**(job.extra or {}), "pickup_code": code}
    await ctx.emit(E.READY_FOR_PICKUP, actor="agent", job_id=job_id, payload={"code": code})
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"Your phone is ready.\nCollect at Reliance Digital.\nYour code: {code}",
           buttons=[(f"walk_in_collect:{job_id}", "Pay at store")])
    ctx.say(f"{job_id}: ready · code {code} sent to customer.")
    ctx.area(f"{job_id}: ready for pickup · code issued")


@on("walk_in_collect")
async def walk_in_collect(ctx: Ctx) -> None:
    """Store enters the customer's one-time code to hand over."""
    parts = ctx.intent.split(":")
    job_id = parts[1]
    entered = parts[2] if len(parts) > 2 else ctx.inbound.raw.get("code")
    job = await ctx.job(job_id)
    expected = (job.extra or {}).get("pickup_code")
    try:
        pr.assert_handover_code(entered, expected)
    except ProtectiveRuleError as e:
        ctx.say("Code does not match.\nHandover only with the one-time code.")
        ctx.area(f"{job_id}: handover blocked — {e.detail}")
        return
    await ctx.emit(E.PAYMENT_RECEIVED, actor="store", job_id=job_id, payload={"mode": "store"})
    await ctx.emit(E.HANDED_OVER, actor="store", job_id=job_id, payload={})
    await ctx.emit(E.CUSTOMER_CONFIRMED, actor="customer", job_id=job_id, payload={})
    await ctx.emit(E.CLOSED, actor="agent", job_id=job_id, payload={})
    ctx.say(f"{job_id}: handed over · code matched · closed.")
    ctx.to(job.customer_id, Role.CUSTOMER, "Collected. Is your phone working well?")
    ctx.area(f"{job_id}: handed over · code match · closed")


@on("walk_in_decline")
async def walk_in_decline(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.ESTIMATE_DECLINED, actor="customer", job_id=job_id, payload={})
    ctx.say("No problem.\nCollect your phone at the store.")

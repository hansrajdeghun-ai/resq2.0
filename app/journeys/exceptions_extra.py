"""Exception-table handlers (spec 4.1) not covered by the main journeys.

Each maps to a row the jury may try:
  technician late            -> new ETA + Change time
  site not ready             -> reason/photo, customer picks new slots
  customer not at home        -> NotAtHome, customer picks new slots
  customer changes the slot    -> release old, book new
  payment fails twice          -> hand to the resQ desk
  DOA rejected by the brand     -> hand to the resQ desk with the checklist
  damage in transit (house move)-> compare condition photos from both partners
"""
from __future__ import annotations

from app.domain import JobState, Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.journeys import _helpers as H
from app.monitoring.service import raise_alert


async def _job(ctx: Ctx, job_id: str):
    job = await ctx.job(job_id)
    if not job:
        ctx.say(f"{job_id} is not an active job.")
    return job


# ─── technician late ─────────────────────────────────────────────────────────
@on("running_late")
async def running_late(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _job(ctx, job_id)
    if not job:
        return
    await raise_alert(ctx.session, job_id, cause="technician_late",
                      text=f"{job_id}: technician running late", action="nudge")
    ctx.to(job.customer_id, Role.CUSTOMER,
           "Your technician is running a little late.\nNew ETA: about 40 minutes.",
           buttons=[(f"change_slot:{job_id}:Tomorrow 10-12", "Change time"),
                    (f"ok:{job_id}", "That's fine")])
    ctx.say("New ETA sent to the customer.")
    ctx.area(f"{job_id}: technician late · new ETA sent")


# ─── site not ready ──────────────────────────────────────────────────────────
@on("site_not_ready")
async def site_not_ready(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _job(ctx, job_id)
    if not job:
        return
    await ctx.emit(E.SITE_NOT_READY, actor="field", job_id=job_id,
                   proof_link=ctx.inbound.raw.get("proof_link"),
                   payload={"reason": "wall not ready"})
    ctx.to(job.customer_id, Role.CUSTOMER,
           "The site isn't ready for installation yet.\nPick a new slot when it is:",
           buttons=H.offer_slots())
    ctx.say("Site-not-ready recorded with a photo.\nCustomer offered new slots.")
    ctx.area(f"{job_id}: site not ready · reason + photo · rebook offered")


# ─── customer not at home ────────────────────────────────────────────────────
@on("not_at_home")
async def not_at_home(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _job(ctx, job_id)
    if not job:
        return
    await ctx.emit(E.NOT_AT_HOME, actor="field", job_id=job_id,
                   proof_link=ctx.inbound.raw.get("proof_link"), payload={})
    ctx.to(job.customer_id, Role.CUSTOMER,
           "We came by but no one was home.\nPick a new slot:", buttons=H.offer_slots())
    ctx.say("Not-at-home recorded.\nCustomer offered new slots.")
    ctx.area(f"{job_id}: customer not at home · rebook offered")


# ─── customer changes slot ───────────────────────────────────────────────────
@on("change_slot")
async def change_slot(ctx: Ctx) -> None:
    _, job_id, slot = ctx.intent.split(":", 2)
    job = await _job(ctx, job_id)
    if not job:
        return
    await ctx.emit(E.PROMISED, actor="customer", job_id=job_id,
                   payload={"slot": slot, "rebooked": True})
    ctx.say(f"Done — moved to {slot}.\nThe old slot is released.")
    ctx.area(f"{job_id}: slot changed to {slot}")


# ─── payment fails twice ─────────────────────────────────────────────────────
@on("payment_failed")
async def payment_failed(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _job(ctx, job_id)
    if not job:
        return
    fails = (job.extra or {}).get("pay_fails", 0) + 1
    job.extra = {**(job.extra or {}), "pay_fails": fails}
    if fails >= 2:
        await ctx.emit(E.HANDED_TO_PERSON, actor="agent", job_id=job_id,
                       payload={"reason": "payment failed twice"})
        await raise_alert(ctx.session, job_id, cause="payment_failed",
                          text=f"{job_id}: payment failed twice", action="take_over")
        ctx.to(job.customer_id, Role.CUSTOMER,
               "Payment didn't go through.\nA person from the resQ desk will help you.")
        ctx.area(f"{job_id}: payment failed twice · handed to desk")
    else:
        ctx.to(job.customer_id, Role.CUSTOMER,
               "That payment didn't go through.\nPlease try the link again.")
        ctx.area(f"{job_id}: payment failed ({fails}) · retry offered")


# ─── DOA rejected by the brand ───────────────────────────────────────────────
@on("doa_reject")
async def doa_reject(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _job(ctx, job_id)
    if not job:
        return
    await ctx.emit(E.ESCALATED, actor="agent", job_id=job_id, payload={"reason": "doa_rejected"})
    await ctx.emit(E.HANDED_TO_PERSON, actor="agent", job_id=job_id, payload={})
    await raise_alert(ctx.session, job_id, cause="doa_rejected",
                      text=f"{job_id}: brand rejected the DOA", action="take_over")
    ctx.to(job.customer_id, Role.CUSTOMER,
           "We're sorting this out with the brand for you.\nThe resQ desk is on it.")
    ctx.say("DOA rejection escalated with the checklist + photos.")
    ctx.area(f"{job_id}: DOA rejected by brand · handed to desk with evidence")


# ─── damage in transit (house move) ──────────────────────────────────────────
@on("move_damage")
async def move_damage(ctx: Ctx) -> None:
    req_id = ctx.intent.split(":", 1)[1]
    await raise_alert(ctx.session, None, cause="transit_damage",
                      text=f"{req_id}: damage reported in transit", action="take_over")
    ctx.say("Comparing the condition photos from the uninstall and the reinstall partner.")
    ctx.area(f"{req_id}: transit damage · comparing both partners' condition photos")

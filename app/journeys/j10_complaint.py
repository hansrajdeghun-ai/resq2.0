"""J10 — Complaint and escalation (spec page 15).

The agent replies with the job facts and three options. "Talk to a person" hands the
thread to the resQ desk, which takes over the job (the agent goes quiet) and sees the
full history — the customer does not repeat the story. The complaint closes only on the
customer's Yes. Repeated patterns are flagged.

Events: ComplaintRaised · HandedToPerson · FixProposed · FixAccepted · GoodwillIssued ·
ComplaintClosed · PatternFlagged · TakenOver · ReturnedToAgent
"""
from __future__ import annotations

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.monitoring import service as M

AREA = "area-andheri"


@on("complain")
async def complain(ctx: Ctx) -> None:
    job_id = ctx.conversation.active_job_id or "R-0000"
    await ctx.emit(E.COMPLAINT_RAISED, actor="customer", job_id=job_id,
                   payload={"text": ctx.inbound.text})
    status = await M.job_status(ctx.session, job_id) if job_id != "R-0000" else "your job"
    await ctx.emit(E.FIX_PROPOSED, actor="agent", job_id=job_id, payload={})
    ctx.say("Sorry about this. Here is where your job stands:\n"
            f"{status.splitlines()[0]}\nWhat would you like?",
            buttons=[(f"fix_accept:{job_id}", "Accept the fix"),
                     (f"complain_change:{job_id}", "Other time"),
                     ("talk_to_person", "Talk to a person")])
    # alert the area manager (exception; deduped)
    await M.raise_alert(ctx.session, job_id, cause="complaint",
                        text=f"{job_id}: customer complaint", action="take_over")
    ctx.area(f"{job_id}: complaint raised · fix proposed")


@on("fix_accept")
async def fix_accept(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.FIX_ACCEPTED, actor="customer", job_id=job_id, payload={})
    await ctx.emit(E.GOODWILL_ISSUED, actor="agent", job_id=job_id,
                   payload={"voucher": 200})
    await ctx.emit(E.COMPLAINT_CLOSED, actor="customer", job_id=job_id, payload={})
    ctx.say("Thank you. A ₹200 voucher is in your account.\nWe will make it right.")
    ctx.area(f"{job_id}: fix accepted · goodwill ₹200 · complaint closed")


@on("talk_to_person")
async def talk_to_person(ctx: Ctx) -> None:
    """Hand the thread to the resQ desk, which takes over the job (spec: works at
    every step of every journey)."""
    job_id = ctx.conversation.active_job_id or "R-0000"
    await ctx.emit(E.HANDED_TO_PERSON, actor="agent", job_id=job_id, payload={})
    await M.take_over(ctx.session, job_id, by=AREA)
    # pin the thread to this job so the take-over gate (router) silences the agent
    # even when there is no real job yet (e.g. "talk to a person" as a first message)
    ctx.set_active_job(job_id)
    ctx.say("A person from the resQ desk will reply in 5 minutes.")
    # the desk sees the full thread (no repeating the story)
    ctx.to(AREA, Role.AREA,
           f"Take over {job_id}.\nCustomer: {ctx.inbound.text or 'asked for a person'}",
           buttons=[(f"hand_back:{job_id}", "Hand back to agent")])
    ctx.area(f"{job_id}: handed to a person · agent quiet")


@on("complain_change")
async def complain_change(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    ctx.say("No problem.\nTell us a better time and we will reschedule.")
    ctx.area(f"{job_id}: customer wants another time")

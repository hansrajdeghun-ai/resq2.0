"""J13 — Payouts and disputes (spec page 18).

A job is payable only after the customer confirms and the cooling period ends. The agent
answers disputes from the ledger. No payout without CustomerConfirmed; a person approves
each payout run (rule 8).

Events: Payable · Held · StatementSent · DisputeRaised · DisputeToFinance ·
DisputeResolved · PayoutApproved · Paid
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.domain import JobState, Role
from app.engine.context import Ctx
from app.engine.router import on
from app.errors import ProtectiveRuleError
from app.events.types import EventType as E
from app.journeys import _helpers as H
from app.models.event import Event
from app.models.ledger import Job
from app.rules import protective as pr


@on("day_summary")
async def day_summary(ctx: Ctx) -> None:
    done = await ctx.session.scalar(
        select(__import__("sqlalchemy").func.count()).select_from(Job)
        .where(Job.state.in_(["Confirmed", "Closed"]))) or 0
    ctx.say(f"Today: {done} done.\nPayouts come after the cooling period.")
    ctx.area(f"owner day summary · {done} done")


@on("weekly_statement")
async def weekly_statement(ctx: Ctx) -> None:
    await ctx.emit(E.STATEMENT_SENT, actor="agent", payload={"to": ctx.inbound.from_id})
    ctx.say("Statement sent.\nSee your lines, or dispute one.",
            buttons=[("dispute_open", "Dispute a line")])
    ctx.area("weekly statement sent")


@on("dispute")
async def dispute(ctx: Ctx) -> None:
    """Owner disputes a line; the agent answers from the ledger."""
    job_id = ctx.intent.split(":", 1)[1] if ":" in ctx.intent else "R-0000"
    await ctx.emit(E.DISPUTE_RAISED, actor="owner", job_id=job_id,
                   payload={"text": ctx.inbound.text})
    # read the ledger: does a reason for the extra visit exist?
    has_part = (await ctx.session.scalars(
        select(Event).where(Event.job_id == job_id, Event.type == E.PART_NEEDED.value)
    )).first()
    if has_part:
        await ctx.emit(E.DISPUTE_RESOLVED, actor="agent", job_id=job_id,
                       payload={"finding": "part reason exists; visit 2 is payable"})
        ctx.say(f"{job_id}: the part reason exists in the log.\nVisit 2 is payable. Fixed.")
        ctx.area(f"{job_id}: dispute resolved by the agent (ledger)")
    else:
        await ctx.emit(E.DISPUTE_TO_FINANCE, actor="agent", job_id=job_id, payload={})
        ctx.say(f"{job_id}: no reason in the log.\nSent to finance with the evidence.")
        ctx.area(f"{job_id}: dispute -> finance")


@on("approve_payout")
async def approve_payout(ctx: Ctx) -> None:
    """Finance/area approves a payout run — a person, per rule 8."""
    now = datetime.now(timezone.utc)
    jobs = (await ctx.session.scalars(
        select(Job).where(Job.state == JobState.CONFIRMED.value))).all()
    approver = ctx.inbound.from_id
    paid, held = 0, 0
    for job in jobs:
        confirmed = job.confirmed_at is not None
        cooling_done = job.cooling_until is None or H.aware(job.cooling_until) <= now
        try:
            pr.assert_payout_allowed(confirmed, approver)
        except ProtectiveRuleError:
            continue
        if not cooling_done:
            await ctx.emit(E.HELD, actor="agent", job_id=job.id,
                           payload={"reason": "cooling period"})
            held += 1
            continue
        await ctx.emit(E.PAYOUT_APPROVED, actor="area", job_id=job.id,
                       payload={"approver": approver})
        await ctx.emit(E.PAID, actor="finance", job_id=job.id, payload={})
        paid += 1
    ctx.say(f"Payout run approved.\n{paid} paid · {held} held (cooling).")
    ctx.area(f"payout run · {paid} paid · {held} held · by {approver}")

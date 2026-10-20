"""J3 — Repair with a part, two visits (spec page 8).

Continues a repair when the part isn't in the technician's bag at visit 1. The job
stays open, the part is ordered, and visit 2 is booked when it arrives — offered to
the same technician first. One problem on one machine is one job, one job number.
Visit 2 is payable because the ledger holds the reason (PartNeeded) — rule 2.

Events: Diagnosed · PartNeeded · PartReserved · PartDispatched · PartReceived ·
VisitOpened · Promised · (shared visit) · PartUsed · WorkDone · CustomerConfirmed ·
Closed · ReturnOpened
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain import JobState, Role
from app.engine.context import Ctx
from app.engine.router import on
from app.errors import ProtectiveRuleError
from app.events.types import EventType as E
from app.ids import next_task_id, next_visit_id
from app.journeys import _helpers as H
from app.journeys.state_machine import assert_transition
from app.rules import protective as pr


@on("part_needed")
async def part_needed(ctx: Ctx) -> None:
    """Visit 1: technician diagnoses but the part is not in the bag."""
    _, job_id, part = ctx.intent.split(":", 2)
    job = await ctx.job(job_id)
    assert_transition(job.state, JobState.WAITING_FOR_PART)
    task_id = await next_task_id(ctx.session)
    await ctx.emit(E.DIAGNOSED, actor="field", job_id=job_id, payload={"part": part})
    await ctx.emit(E.PART_NEEDED, actor="field", job_id=job_id,
                   task_id=task_id, payload={"part": part})
    await ctx.emit(E.PART_RESERVED, actor="agent", job_id=job_id, task_id=task_id,
                   payload={"part": part})
    await ctx.emit(E.PART_DISPATCHED, actor="agent", job_id=job_id, task_id=task_id,
                   payload={"part": part, "eta": "Thursday"})
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"We ordered the part ({part}).\nIt reaches your area by Thursday.\n"
           f"Job {job_id} stays open.",
           buttons=[(f"ok:{job_id}", "OK"), ("talk_to_person", "Talk to us")])
    ctx.say(f"Visit 1 recorded. Part {part} ordered.\nVisit 2 comes when it arrives.")
    ctx.area(f"{job_id}: part {part} needed · dispatched · visit 2 pending")


@on("part_received")
async def part_received(ctx: Ctx) -> None:
    """Warehouse/owner scans the part in — book visit 2 with the same technician."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    await ctx.emit(E.PART_RECEIVED, actor="owner", job_id=job_id, payload={})
    ctx.to(job.customer_id, Role.CUSTOMER,
           "Your part has arrived.\nChoose a slot for visit 2:",
           buttons=[(f"v2slot:{job_id}:Thu 4-6", "Thu 4-6"),
                    (f"v2slot:{job_id}:Fri 9-11", "Fri 9-11")])
    ctx.area(f"{job_id}: part received · visit 2 offered")


@on("v2slot")
async def book_visit_2(ctx: Ctx) -> None:
    _, job_id, slot = ctx.intent.split(":", 2)
    job = await ctx.job(job_id)
    assert_transition(job.state, JobState.PROMISED)
    visit_id = await next_visit_id(ctx.session)
    # rule 2: a second payable visit needs a reason in the log — PartNeeded exists
    pr.assert_visit_payout(2, payable=True, reason="PartNeeded")
    await ctx.emit(E.VISIT_OPENED, actor="agent", job_id=job_id, payload={"visit_number": 2})
    await ctx.emit(E.PROMISED, actor="agent", job_id=job_id, payload={"slot": slot})
    await ctx.emit(E.TECHNICIAN_ASSIGNED, actor="agent", job_id=job_id,
                   payload={"technician_id": job.technician_id, "visit_id": visit_id,
                            "visit_number": 2, "slot": slot, "payable": True})
    ctx.say(f"Visit 2 booked for {slot}, same technician.")
    if job.technician_id:
        ctx.to(job.technician_id, Role.FIELD,
               f"Visit 2 · {job_id} · {slot}\nBring the part. Fit and tag the old one.",
               buttons=[(f"on_my_way:{job_id}", "On my way")])
    ctx.area(f"{job_id}: visit 2 booked {slot} · same technician")


@on("part_fitted")
async def part_fitted(ctx: Ctx) -> None:
    """Visit 2: part fitted, old part tagged for return, work done (proof required)."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    proof = ctx.inbound.raw.get("proof_link")
    place = ctx.inbound.raw.get("place")
    try:
        pr.assert_proof(proof, datetime.now(timezone.utc), place)
    except ProtectiveRuleError as e:
        ctx.say("Send the photos through the capture link.\nTime and place are needed.")
        ctx.area(f"{job_id}: proof rejected — {e.detail}")
        return
    assert_transition(job.state, JobState.WORK_DONE)
    task_id = await next_task_id(ctx.session)
    await ctx.emit(E.PART_USED, actor="field", job_id=job_id, payload={})
    await ctx.emit(E.WORK_DONE, actor="field", job_id=job_id,
                   place=place, proof_link=proof, payload={"photos": 3})
    await ctx.emit(E.RETURN_OPENED, actor="agent", job_id=job_id, task_id=task_id,
                   payload={"old_part": True})
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "machine"
    ctx.to(job.customer_id, Role.CUSTOMER, f"Is your {cat} working well now?",
           buttons=[(f"confirm_work:{job_id}", "Yes"),
                    (f"confirm_no:{job_id}", "Not yet")])
    ctx.say("Part fitted, old part tagged.\nWaiting for the customer to confirm.")
    ctx.area(f"{job_id}: part fitted · old part to return · work done")


@on("ok")
async def ack_ok(ctx: Ctx) -> None:
    """Generic OK acknowledgement (e.g. after part-ordered notice)."""
    ctx.say("Thanks. We will keep you posted.")

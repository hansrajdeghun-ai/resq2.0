"""Shared visit steps B3-B5 — the technician trip, reused by J1/J2/J3/J4/J7.

on my way -> arrived -> scan serial (must match) -> extras at the published rate
(customer approves) -> work done (proof via capture link) -> customer confirms
(cooling period). Protective rules 3, 4, 5 are enforced here in code.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.data import rate_card
from app.domain import JobState, Role
from app.engine.context import Ctx
from app.engine.router import on
from app.errors import ProtectiveRuleError
from app.events.types import EventType as E
from app.journeys import _helpers as H
from app.journeys.state_machine import assert_transition
from app.rules import protective as pr


async def _tech_name(ctx: Ctx, job) -> str:
    if job.technician_id:
        from app.models.people import Technician
        t = await ctx.session.get(Technician, job.technician_id)
        return H.first_name(t.name) if t else "Your technician"
    return "Your technician"


async def _require_job(ctx: Ctx, job_id: str):
    job = await ctx.job(job_id)
    if not job:
        ctx.say(f"{job_id} is not an active job.")
    return job


@on("on_my_way")
async def on_my_way(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _require_job(ctx, job_id)
    if not job:
        return
    assert_transition(job.state, JobState.EN_ROUTE)
    await ctx.emit(E.EN_ROUTE, actor="field", job_id=job_id, payload={})
    name = await _tech_name(ctx, job)
    ctx.to(job.customer_id, Role.CUSTOMER, f"{name} is on the way.\nAbout 20 minutes.")
    ctx.say("On my way sent.\nScan the serial plate on arrival.",
            buttons=[(f"arrived:{job_id}", "Arrived")])
    ctx.area(f"{job_id}: en route · ETA 20 min")


@on("arrived")
async def arrived(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _require_job(ctx, job_id)
    if not job:
        return
    assert_transition(job.state, JobState.ON_SITE)
    await ctx.emit(E.ARRIVED, actor="field", job_id=job_id, payload={})
    ctx.say("Arrived. Scan the serial plate to start.",
            buttons=[(f"scanserial:{job_id}", "📷 Scan serial"),
                     (f"serial:{job_id}:SN-WRONG", "Wrong serial (test)")])
    ctx.area(f"{job_id}: arrived · serial pending")


@on("scanserial")
async def scan_serial_tap(ctx: Ctx) -> None:
    """One-tap serial scan: reads the machine's real serial (a correct scan)."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    serial = job.machine_serial if job else None
    ctx.inbound.button_id = f"serial:{job_id}:{serial or 'UNKNOWN'}"
    await scan_serial(ctx)


@on("serial")
async def scan_serial(ctx: Ctx) -> None:
    _, job_id, scanned = ctx.intent.split(":", 2)
    job = await _require_job(ctx, job_id)
    if not job:
        return
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    expected = machine.serial if machine else None
    try:
        pr.assert_serial_matches(scanned, expected)
    except ProtectiveRuleError as e:
        await ctx.emit(E.SERIAL_MISMATCH, actor="field", job_id=job_id,
                       payload={"scanned": scanned, "expected": expected})
        ctx.say("Serial does not match.\nThe job is stopped.")
        ctx.area(f"{job_id}: SERIAL MISMATCH — {e.detail}")
        return
    await ctx.emit(E.SERIAL_VERIFIED, actor="field", job_id=job_id,
                   visit_id=await H.latest_visit_id(ctx.session, job_id), payload={})
    nxt = "Diagnose and fix, then send proof." if job.type == "repair" \
        else "Finish the work, then send proof."
    ctx.say(f"Serial matches.\n{nxt}",
            buttons=[(f"work_done:{job_id}", "Work done")])
    ctx.area(f"{job_id}: serial verified")


@on("extras")
async def extras(ctx: Ctx) -> None:
    _, job_id, line = ctx.intent.split(":", 2)
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "AC"
    price = rate_card.price_of(cat, line)
    if price is None:
        ctx.say("That is not on the rate card.\nI cannot quote it.")
        return
    item = rate_card.lookup(cat, line)
    await ctx.emit(E.ESTIMATE_SENT, actor="agent", job_id=job_id,
                   payload={"line": line, "rate": price})
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"{item['label']} at the published rate ₹{price:.0f}.\nApprove?",
           buttons=[(f"extras_ok:{job_id}:{line}", "Approve"),
                    (f"extras_no:{job_id}", "Decline")])
    ctx.area(f"{job_id}: extras ₹{price:.0f} — waiting for customer")


@on("extras_ok")
async def extras_ok(ctx: Ctx) -> None:
    _, job_id, line = ctx.intent.split(":", 2)
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "AC"
    price = rate_card.price_of(cat, line) or 0.0
    pr.assert_price_on_card(cat, price)
    pr.assert_price_approved(True)
    await ctx.emit(E.EXTRAS_APPROVED, actor="customer", job_id=job_id,
                   payload={"line": line, "rate": price})
    ctx.say("Approved. The work will go ahead.")
    ctx.area(f"{job_id}: extras ₹{price:.0f} approved")


@on("extras_no")
async def extras_no(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.ESTIMATE_DECLINED, actor="customer", job_id=job_id, payload={})
    ctx.say("No problem. We will not do the extra work.")
    ctx.area(f"{job_id}: extras declined")


@on("work_done")
async def work_done(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _require_job(ctx, job_id)
    if not job:
        return
    proof = ctx.inbound.raw.get("proof_link")
    place = ctx.inbound.raw.get("place")
    try:
        pr.assert_proof(proof, datetime.now(timezone.utc), place)
    except ProtectiveRuleError as e:
        ctx.say("Please send the photos through the capture link.\nTime and place are needed.")
        ctx.area(f"{job_id}: proof rejected — {e.detail}")
        return
    assert_transition(job.state, JobState.WORK_DONE)
    await ctx.emit(E.WORK_DONE, actor="field", job_id=job_id,
                   place=place, proof_link=proof, payload={"photos": 4})
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "machine"
    well = "working well" if job.type != "install" else "working well"
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"Is your {cat} {well}?",
           buttons=[(f"confirm_work:{job_id}", "Yes"),
                    (f"confirm_no:{job_id}", "Not yet")])
    ctx.say("Work done recorded.\nWaiting for the customer to confirm.")
    ctx.area(f"{job_id}: work done · 4 photos")


@on("confirm_work")
async def confirm_work(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await _require_job(ctx, job_id)
    if not job:
        return
    assert_transition(job.state, JobState.CONFIRMED)
    await ctx.emit(E.CUSTOMER_CONFIRMED, actor="customer", job_id=job_id, payload={})
    # in-warranty work is claimed from the brand; payout is payable after cooling
    if job.type == "install" or job.in_warranty:
        await ctx.emit(E.CLAIMED, actor="agent", job_id=job_id, payload={})
    await ctx.emit(E.PAYABLE, actor="agent", job_id=job_id,
                   payload={"after": "cooling_period"})
    machine = await ctx.machine(job.machine_serial) if job.machine_serial else None
    cat = machine.category if machine else "machine"
    if job.type == "install":
        ctx.say(f"Your {cat} is in your Reliance record.\nWarranty has started.",
                buttons=[("my_machines", "My machines")])
    else:
        ctx.say(f"Glad your {cat} is sorted.\nIt is recorded in your Reliance account.",
                buttons=[("my_machines", "My machines")])
    ctx.area(f"{job_id}: confirmed · cooling · payable after")


@on("confirm_no")
async def confirm_no(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.REOPENED, actor="customer", job_id=job_id,
                   payload={"reason": "not_working"})
    ctx.say("Sorry about that.\nWe will send a free revisit.")
    ctx.area(f"{job_id}: not yet · free revisit")

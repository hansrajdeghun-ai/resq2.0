"""J2 — Repair at home (spec page 7).

The customer reports a fault; the agent tries a brand self-check; if unresolved it
reads warranty + authority from the ledger (not the invoice), pre-diagnoses the likely
fault, and books a technician who carries the part. Then the shared visit flow runs.

Events: FaultReported · SelfCheckSent · SelfFixed · RepairRequested · WarrantyChecked
· PreDiagnosed · Promised · PartnerOffered · (shared) ... · Closed
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.agent import diagnose
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_job_id
from app.journeys import _helpers as H
from app.journeys.shared_assign import offer_to_owner
from app.models.ledger import Machine


@on("report_fault")
async def report_fault(ctx: Ctx) -> None:
    machines = await H.owned_machines(ctx.session, ctx.customer_id)
    if not machines:
        ctx.say("I don't see a machine on your account yet.\n"
                "Tell me what you bought and we will help.")
        return
    # the AI decides which owned machine this is about (word-list is only an offline fallback)
    from app.agent.resolve import resolve_machine

    serial, status = await resolve_machine(ctx.inbound.text, machines)
    if status in ("not_owned", "ask"):
        names = ", ".join(H.mname(x) for x in machines)
        ctx.conversation.history = [*(ctx.conversation.history or []),
                                    {"symptom": ctx.inbound.text}]
        lead = (f"I don't see that on your account.\nYou have: {names}. Which should we look at?"
                if status == "not_owned" else "Which machine has the problem?")
        ctx.say(lead, list_rows=[(f"fault_pick:{x.serial}", H.mname(x)) for x in machines],
                list_button="Choose a machine")
        return
    await _start_fault(ctx, await ctx.machine(serial), ctx.inbound.text)


@on("fault_pick")
async def fault_pick(ctx: Ctx) -> None:
    m = await ctx.machine(ctx.intent.split(":", 1)[1])
    if not m:
        ctx.say("That machine is not on your account.")
        return
    symptom = next((h.get("symptom") for h in reversed(ctx.conversation.history or [])
                    if h.get("symptom")), None)
    await _start_fault(ctx, m, symptom)


async def _start_fault(ctx: Ctx, machine, symptom: str | None) -> None:
    cat = machine.category or "AC"
    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)
    await ctx.emit(E.FAULT_REPORTED, actor="agent", job_id=job_id, machine_id=machine.serial,
                   payload={"job_type": "repair", "customer_id": ctx.customer_id,
                            "serial": machine.serial, "category": cat})
    check = await diagnose.self_check(cat, symptom)
    ctx.conversation.history = [*(ctx.conversation.history or []),
                                {"symptom": symptom, "job": job_id}]
    await ctx.emit(E.SELF_CHECK_SENT, actor="agent", job_id=job_id,
                   payload={"self_check": check, "symptom": symptom})
    ctx.say(f"For your {H.mname(machine)} — try this first:\n{check}",
            buttons=[(f"self_fixed:{job_id}", "Fixed it"),
                     (f"still_broken:{job_id}", "Still not working")])
    ctx.area(f"{job_id}: fault reported on {H.mname(machine)} · self-check sent")


@on("self_fixed")
async def self_fixed(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.SELF_FIXED, actor="customer", job_id=job_id, payload={})
    await ctx.emit(E.CLOSED, actor="agent", job_id=job_id,
                   payload={"reason": "self_fixed"})
    ctx.say("Great — glad that sorted it.\nNo visit needed.")
    ctx.area(f"{job_id}: self-check fixed · closed, no visit")


@on("still_broken")
async def still_broken(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    in_warranty = H.is_in_warranty(machine)
    await ctx.emit(E.WARRANTY_CHECKED, actor="agent", job_id=job_id,
                   payload={"in_warranty": in_warranty,
                            "wty_end": machine.wty_end.isoformat() if machine and machine.wty_end else None})
    symptom = next((h.get("symptom") for h in reversed(ctx.conversation.history or [])
                    if h.get("symptom")), None)
    likely = await diagnose.likely_fault(cat, symptom)
    await ctx.emit(E.REPAIR_REQUESTED, actor="agent", job_id=job_id,
                   payload={"job_type": "repair"})
    await ctx.emit(E.PRE_DIAGNOSED, actor="agent", job_id=job_id,
                   payload={"likely": likely})
    price_line = "The repair is free." if in_warranty else "A visit charge of ₹299 applies."
    wty = machine.wty_end.strftime("%b %Y") if machine and machine.wty_end else "unknown"
    cover = f"In warranty to {wty}." if in_warranty else "Out of warranty."
    ctx.say(f"{cover}\n{price_line}\nChoose a slot:", buttons=H.repair_slots())
    ctx.ask("repair_slot")
    ctx.area(f"{job_id}: {'in' if in_warranty else 'out of'} warranty · slots offered")


@on("rslot")
async def book_repair(ctx: Ctx) -> None:
    slot = ctx.intent.split(":", 1)[1] if ":" in ctx.intent else "Tue 4-6"
    job_id = ctx.conversation.active_job_id or await next_job_id(ctx.session)
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    pincode = None
    cust = await ctx.customer()
    if cust:
        pincode = (cust.address or {}).get("postal_code")

    await ctx.emit(E.PROMISED, actor="agent", job_id=job_id, payload={"slot": slot})
    partner = await H.pick_partner(ctx.session, cat, pincode)
    if partner is None:
        ctx.say("All partners are full for that slot.\nLet me offer other days.",
                buttons=H.repair_slots())
        return
    ctx.answered()
    symptom = next((h.get("symptom") for h in reversed(ctx.conversation.history or [])
                    if h.get("symptom")), None)
    likely = await diagnose.likely_fault(cat, symptom)
    ctx.say(f"Booked for {slot}.\nLikely: {likely}. The technician will carry the part.")
    await offer_to_owner(ctx, job_id, partner,
                         f"New repair · {job_id}\n{cat} · {slot}\nLikely: {likely}")
    ctx.area(f"{job_id}: repair booked {slot} · {likely} · offered to owner")

"""J1 — Installation entry (spec page 5). The visit + assignment steps are shared
(shared_assign, shared_visit). This module only books the slot and opens the job.

Events contributed: InstallRequested · Promised · PartnerOffered (then the shared
flow adds PartnerAssigned · TechnicianAssigned · ... · Claimed · Payable).
"""
from __future__ import annotations

from sqlalchemy import select

from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_job_id
from app.journeys import _helpers as H
from app.journeys.shared_assign import offer_to_owner
from app.models.ledger import Machine


def _mname(m) -> str:
    return f"{m.brand or ''} {m.category or 'machine'}".strip()


async def _installable(ctx: Ctx):
    machines = (await ctx.session.scalars(
        select(Machine).where(Machine.customer_id == ctx.customer_id)
    )).all()
    return [m for m in machines if not m.replaced_by_serial]


def _offer_slots_for(ctx: Ctx, m) -> None:
    ctx.conversation.history = [*(ctx.conversation.history or []),
                               {"install_serial": m.serial}]
    ctx.say(f"Your {_mname(m)} is ready to install.\nChoose an installation slot:",
            buttons=H.offer_slots())
    ctx.ask("install_slot")


@on("book_install")
async def book_install(ctx: Ctx) -> None:
    # ground in what the household actually owns (spec 2.5) — AI decides the machine
    from app.agent.resolve import resolve_machine

    installable = await _installable(ctx)
    if not installable:
        ctx.say("I don't see a machine on your account to install.\n"
                "Installation opens after a Reliance Digital delivery.")
        return
    serial, status = await resolve_machine(ctx.inbound.text, installable)
    names = ", ".join(_mname(m) for m in installable)
    if status == "not_owned":
        ctx.say(f"I don't see that on your account.\nYou have: {names}. Install one of these?",
                list_rows=[(f"install_machine:{m.serial}", _mname(m)) for m in installable],
                list_button="Choose a machine")
    elif status == "ask":
        ctx.say("Which machine should we install?",
                list_rows=[(f"install_machine:{m.serial}", _mname(m)) for m in installable],
                list_button="Choose a machine")
        ctx.ask("which_machine")
    else:
        _offer_slots_for(ctx, await ctx.machine(serial))


@on("install_machine")
async def install_machine(ctx: Ctx) -> None:
    serial = ctx.intent.split(":", 1)[1]
    m = await ctx.machine(serial)
    if not m:
        ctx.say("That machine is not on your account.")
        return
    _offer_slots_for(ctx, m)


@on("slot")
async def pick_slot(ctx: Ctx) -> None:
    slot = ctx.intent.split(":", 1)[1] if ":" in ctx.intent else "Sun 10-12"
    cust = await ctx.customer()
    # use the machine the customer chose (if several were offered), else their machine
    chosen = next((h.get("install_serial") for h in reversed(ctx.conversation.history or [])
                   if h.get("install_serial")), None)
    machine = await ctx.machine(chosen) if chosen else (await ctx.session.scalars(
        select(Machine).where(Machine.customer_id == ctx.customer_id))).first()
    category = machine.category if machine else "AC"
    pincode = (cust.address or {}).get("postal_code") if cust else None

    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)

    await ctx.emit(E.INSTALL_REQUESTED, actor="agent", job_id=job_id,
                   machine_id=machine.serial if machine else None,
                   payload={"job_type": "install", "customer_id": ctx.customer_id,
                            "serial": machine.serial if machine else None})
    await ctx.emit(E.PROMISED, actor="agent", job_id=job_id, payload={"slot": slot})

    partner = await H.pick_partner(ctx.session, category, pincode)
    if partner is None:
        ctx.say("All partners are full for that slot.\nLet me offer you other days.",
                buttons=H.offer_slots())
        ctx.area(f"{job_id}: no capacity for {category} in {pincode}")
        return

    ctx.answered()
    ctx.say(f"Booked for {slot}.\nWe will tell you who is coming.")
    await offer_to_owner(ctx, job_id, partner, f"New install · {job_id}\n{category} · {slot}")
    ctx.area(f"{job_id} · Install · {category}\nBooked {slot} · offered to owner")

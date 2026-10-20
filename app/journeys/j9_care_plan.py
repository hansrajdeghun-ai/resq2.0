"""J9 — Maintenance and care plan (spec page 14).

The agent reminds the customer when a service is due (consent only, once a season),
books it, and can offer a care plan from an insurer. The plan is linked to the serial,
not the phone number. A plan repair uses the job flow with no price step.

Events: ReminderSent · ServiceBooked · PlanQuoted · PlanBought · PolicyBound ·
ServiceDone · HealthReported · RenewalSent
"""
from __future__ import annotations

from sqlalchemy import select

from app.data import rate_card
from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.integrations.payments import get_payments
from app.models.ledger import Machine


async def _machine(ctx: Ctx) -> Machine | None:
    from app.journeys import _helpers as H

    machines = await H.owned_machines(ctx.session, ctx.customer_id)
    if not machines:
        return None
    return H.match_category(machines, ctx.inbound.text) or machines[0]


@on("service_reminder")
async def service_reminder(ctx: Ctx) -> None:
    """Agent-initiated, consent only, once a season (spec)."""
    machine = await _machine(ctx)
    cat = machine.category if machine else "AC"
    price = rate_card.price_of(cat, "service") or 499.0
    await ctx.emit(E.REMINDER_SENT, actor="agent",
                   machine_id=machine.serial if machine else None,
                   payload={"category": cat})
    ctx.say(f"Your {cat} is due for a service.\nBook a service · ₹{price:.0f}?",
            buttons=[("service_book", f"Book · ₹{price:.0f}"),
                     ("care_plan", "See care plan"),
                     ("remind_later", "Remind me later")])
    ctx.area(f"reminder sent · {cat} service")


@on("service_book")
async def service_book(ctx: Ctx) -> None:
    await ctx.emit(E.SERVICE_BOOKED, actor="customer", payload={})
    ctx.say("Booked.\nWe will send the normal visit steps.",
            buttons=[("care_plan", "See care plan")])
    ctx.area("service booked")


@on("care_plan")
async def care_plan(ctx: Ctx) -> None:
    machine = await _machine(ctx)
    if not machine:
        ctx.say("I don't see a machine on your account to cover yet.")
        return
    cat = machine.category if machine else "AC"
    price = rate_card.price_of(cat, "care_plan_1y") or 1999.0
    await ctx.emit(E.PLAN_QUOTED, actor="agent",
                   machine_id=machine.serial if machine else None,
                   payload={"category": cat, "price": price})
    ctx.say(f"Cover it for 1 year:\n2 services + repairs · ₹{price:.0f} (plan by insurer).",
            buttons=[("plan_buy", f"Buy · ₹{price:.0f}"),
                     ("service_book", "Just the service")])
    ctx.area(f"care plan offered · {cat} · ₹{price:.0f}")


@on("plan_buy")
async def plan_buy(ctx: Ctx) -> None:
    machine = await _machine(ctx)
    cat = machine.category if machine else "AC"
    price = rate_card.price_of(cat, "care_plan_1y") or 1999.0
    link = await get_payments().create_link(price, ref="careplan")
    ctx.say(f"Pay ₹{price:.0f} by UPI to start cover:\n{link}",
            buttons=[("plan_paid", "I've paid")])
    ctx.area(f"care plan · payment link ₹{price:.0f}")


@on("plan_paid")
async def plan_paid(ctx: Ctx) -> None:
    machine = await _machine(ctx)
    serial = machine.serial if machine else None
    await ctx.emit(E.PLAN_BOUGHT, actor="customer", machine_id=serial, payload={})
    # the insurer carries the obligation; policy bound to the serial, not the phone
    await ctx.emit(E.POLICY_BOUND, actor="agent", machine_id=serial,
                   payload={"policy": "CP-88120"})
    ctx.say("Care plan active.\nPolicy CP-88120, linked to your machine.")
    ctx.area(f"plan bought · policy CP-88120 · serial {serial}")


@on("service_done")
async def service_done(ctx: Ctx) -> None:
    await ctx.emit(E.SERVICE_DONE, actor="field", payload={})
    await ctx.emit(E.HEALTH_REPORTED, actor="agent",
                   payload={"health": "Good", "next": "October"})
    ctx.say("Service done. Health: Good.\nNext service: October.")
    ctx.area("service done · health reported")


@on("plan_renew")
async def plan_renew(ctx: Ctx) -> None:
    await ctx.emit(E.RENEWAL_SENT, actor="agent", payload={})
    ctx.say("Your plan ends in 30 days.\nRenew for ₹1,899?",
            buttons=[("plan_buy", "Renew"), ("remind_later", "Not now")])
    ctx.area("renewal due in 30 days")


@on("remind_later")
async def remind_later(ctx: Ctx) -> None:
    ctx.say("No problem.\nWe will remind you later.")

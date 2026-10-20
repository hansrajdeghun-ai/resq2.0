"""J4 — Out-of-warranty repair (spec page 9).

The customer sees the visit charge before booking and the estimate before the work,
and pays by UPI link. All prices come from the rate card; the technician takes no cash.

Events: FaultReported · WarrantyChecked(expired) · VisitFeeAccepted · Diagnosed ·
EstimateSent · EstimateApproved/Declined · WorkDone · PaymentReceived · InvoiceSent ·
CustomerConfirmed · Closed
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.data import rate_card
from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_job_id
from app.integrations.payments import get_payments
from app.journeys import _helpers as H
from app.journeys.shared_assign import offer_to_owner
from app.models.ledger import Machine
from app.models.ops import Payment
from app.rules import protective as pr

# demo diagnosis -> rate-card lines (gas leak)
OOW_ESTIMATE = {"AC": ["leak_repair", "gas_refill"]}


@on("report_oow")
async def report_oow(ctx: Ctx) -> None:
    machines = await H.owned_machines(ctx.session, ctx.customer_id)
    if not machines:
        ctx.say("I don't see a machine on your account yet.")
        return
    machine = H.match_category(machines, ctx.inbound.text) or machines[0]
    cat = machine.category if machine else "AC"
    job_id = await next_job_id(ctx.session)
    ctx.set_active_job(job_id)
    fee = rate_card.price_of(cat, "visit_fee") or 299.0
    await ctx.emit(E.FAULT_REPORTED, actor="agent", job_id=job_id,
                   machine_id=machine.serial if machine else None,
                   payload={"job_type": "repair", "customer_id": ctx.customer_id,
                            "serial": machine.serial if machine else None,
                            "category": cat, "in_warranty": False})
    await ctx.emit(E.WARRANTY_CHECKED, actor="agent", job_id=job_id,
                   payload={"in_warranty": False})
    wty = machine.wty_end.strftime("%b %Y") if machine and machine.wty_end else "earlier"
    ctx.say(f"Warranty ended {wty}.\nInspection visit: ₹{fee:.0f}.\nBook a visit?",
            buttons=[(f"oow_book:{job_id}", "Book a visit"),
                     (f"oow_not_now:{job_id}", "Not now")])
    ctx.area(f"{job_id}: out of warranty · visit ₹{fee:.0f} offered")


@on("oow_book")
async def oow_book(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    fee = rate_card.price_of(cat, "visit_fee") or 299.0
    await ctx.emit(E.VISIT_FEE_ACCEPTED, actor="customer", job_id=job_id,
                   payload={"fee": fee})
    await ctx.emit(E.PROMISED, actor="agent", job_id=job_id, payload={"slot": "Tue 4-6"})
    cust = await ctx.customer()
    pincode = (cust.address or {}).get("postal_code") if cust else None
    partner = await H.pick_partner(ctx.session, cat, pincode)
    ctx.say(f"Visit booked.\nVisit charge ₹{fee:.0f} (adjusted if you approve the repair).")
    if partner:
        await offer_to_owner(ctx, job_id, partner,
                             f"New OOW repair · {job_id}\n{cat} · Tue 4-6")
    ctx.area(f"{job_id}: visit fee accepted · offered to owner")


@on("oow_diagnose")
async def oow_diagnose(ctx: Ctx) -> None:
    """Technician diagnoses on site; the agent prices the fix from the card."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    lines = OOW_ESTIMATE.get(cat, ["visit_fee"])
    total = sum(rate_card.price_of(cat, ln) or 0.0 for ln in lines)
    for ln in lines:
        pr.assert_price_on_card(cat, rate_card.price_of(cat, ln))
    await ctx.emit(E.DIAGNOSED, actor="field", job_id=job_id, payload={"lines": lines})
    await ctx.emit(E.ESTIMATE_SENT, actor="agent", job_id=job_id,
                   payload={"lines": lines, "total": total})
    detail = "\n".join(f"{rate_card.lookup(cat, ln)['label']} ₹"
                       f"{rate_card.price_of(cat, ln):.0f}" for ln in lines)
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"Estimate ₹{total:.0f} (visit included).\nApprove to go ahead?",
           buttons=[(f"oow_approve:{job_id}", "Approve"),
                    (f"oow_decline:{job_id}", "Decline")])
    ctx.say(f"Estimate sent: ₹{total:.0f}.\nWaiting for approval.")
    ctx.area(f"{job_id}: estimate ₹{total:.0f} sent")


@on("oow_approve")
async def oow_approve(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.ESTIMATE_APPROVED, actor="customer", job_id=job_id, payload={})
    ctx.say("Approved. The technician will start the work.")
    ctx.area(f"{job_id}: estimate approved")


@on("oow_pay")
async def oow_pay(ctx: Ctx) -> None:
    """After work done, send a UPI link (no cash)."""
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    lines = OOW_ESTIMATE.get(cat, ["visit_fee"])
    total = sum(rate_card.price_of(cat, ln) or 0.0 for ln in lines)
    pr.assert_no_cash("upi")
    link = await get_payments().create_link(total, ref=job_id)
    pay = Payment(id=f"PAY-{job_id}", job_id=job_id, kind="customer_payment",
                  amount=total, status="pending", upi_link=link)
    ctx.session.add(pay)
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"Pay ₹{total:.0f} for {job_id} by UPI:\n{link}",
           buttons=[(f"oow_paid:{job_id}", "I've paid")])
    ctx.area(f"{job_id}: UPI link sent ₹{total:.0f}")


@on("oow_paid")
async def oow_paid(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    pay = await ctx.session.get(Payment, f"PAY-{job_id}")
    if pay:
        pay.status = "paid"
    await ctx.emit(E.PAYMENT_RECEIVED, actor="customer", job_id=job_id, payload={})
    await ctx.emit(E.INVOICE_SENT, actor="agent", job_id=job_id, payload={})
    ctx.say("Payment received.\nYour GST invoice is attached.",
            buttons=[("care_plan", "See care plan")])
    ctx.area(f"{job_id}: paid by UPI · invoice sent")


@on("oow_not_now")
async def oow_not_now(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.CLOSED, actor="agent", job_id=job_id, payload={"reason": "declined"})
    ctx.say("No problem.\nReach out whenever you are ready.")


@on("oow_decline")
async def oow_decline(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1]
    job = await ctx.job(job_id)
    machine = await ctx.machine(job.machine_serial) if job and job.machine_serial else None
    cat = machine.category if machine else "AC"
    fee = rate_card.price_of(cat, "visit_fee") or 299.0
    await ctx.emit(E.ESTIMATE_DECLINED, actor="customer", job_id=job_id, payload={})
    link = await get_payments().create_link(fee, ref=f"{job_id}-visit")
    ctx.to(job.customer_id, Role.CUSTOMER,
           f"No problem. Only the visit charge ₹{fee:.0f} applies:\n{link}")
    ctx.area(f"{job_id}: estimate declined · visit fee ₹{fee:.0f} only")

"""J8 — House move (spec page 13).

One request covers uninstall at the old address and install at the new address, by two
service partners. The customer sees one request, one price, one bill; each job has its
own visit, proof and payout.

Events: RequestOpened · JobsOpened · QuoteApproved · Uninstalled · AddressMoved ·
Installed · CustomerConfirmed · PaymentReceived · RequestClosed
"""
from __future__ import annotations

from app.data import rate_card
from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.ids import next_request_id
from app.integrations.payments import get_payments
from app.models.ledger import ServiceRequest


@on("house_move")
async def house_move(ctx: Ctx) -> None:
    req_id = await next_request_id(ctx.session)
    # demo: 2 ACs + 1 TV -> 3 uninstall + 3 install
    n = 3
    uninstall = (rate_card.price_of("MOVE", "uninstall") or 600.0) * n
    install = (rate_card.price_of("MOVE", "install") or 900.0) * n
    total = uninstall + install
    req = ServiceRequest(id=req_id, customer_id=ctx.customer_id, kind="house_move",
                         note=f"{n} machines", extra={"total": total, "jobs": n * 2})
    ctx.session.add(req)
    await ctx.emit(E.REQUEST_OPENED, actor="agent", request_id=req_id,
                   payload={"customer_id": ctx.customer_id})
    await ctx.emit(E.JOBS_OPENED, actor="agent", request_id=req_id,
                   payload={"count": n * 2})
    ctx.set_active_job(None)
    ctx.conversation.history = [*(ctx.conversation.history or []), {"request": req_id}]
    ctx.say(f"Uninstall + reinstall:\n{n} uninstall, {n} install · Total ₹{total:.0f}.\nApprove?",
            buttons=[(f"move_approve:{req_id}", "Approve"),
                     ("talk_to_person", "Talk to us")])
    ctx.area(f"{req_id}: move · {n*2} jobs · ₹{total:.0f} quoted")


@on("move_approve")
async def move_approve(ctx: Ctx) -> None:
    req_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.QUOTE_APPROVED, actor="customer", request_id=req_id, payload={})
    ctx.say("Approved.\nWe will uninstall at the old home and install at the new one.")
    ctx.area(f"{req_id}: quote approved · partner A (old) + partner B (new)")


@on("move_uninstalled")
async def move_uninstalled(ctx: Ctx) -> None:
    req_id = ctx.intent.split(":", 1)[1]
    await ctx.emit(E.UNINSTALLED, actor="field", request_id=req_id, payload={"count": 3})
    await ctx.emit(E.ADDRESS_MOVED, actor="agent", request_id=req_id, payload={})
    ctx.say(f"{req_id}: 3 uninstalled · in transit.")
    ctx.area(f"{req_id}: uninstalled · condition photos · in transit")


@on("move_installed")
async def move_installed(ctx: Ctx) -> None:
    req_id = ctx.intent.split(":", 1)[1]
    req = await ctx.session.get(ServiceRequest, req_id)
    total = (req.extra or {}).get("total", 4500.0) if req else 4500.0
    await ctx.emit(E.INSTALLED, actor="field", request_id=req_id, payload={"count": 3})
    await ctx.emit(E.CUSTOMER_CONFIRMED, actor="customer", request_id=req_id, payload={})
    link = await get_payments().create_link(total, ref=req_id)
    ctx.say(f"All 3 installed in your new home.\nPay ₹{total:.0f} for the move:\n{link}",
            buttons=[(f"move_paid:{req_id}", "Pay by UPI")])
    ctx.area(f"{req_id}: installed · one bill ₹{total:.0f}")


@on("move_paid")
async def move_paid(ctx: Ctx) -> None:
    req_id = ctx.intent.split(":", 1)[1]
    req = await ctx.session.get(ServiceRequest, req_id)
    if req:
        req.status = "closed"
    await ctx.emit(E.PAYMENT_RECEIVED, actor="customer", request_id=req_id, payload={})
    await ctx.emit(E.REQUEST_CLOSED, actor="agent", request_id=req_id, payload={})
    ctx.say("Payment received.\nYour move is complete — two payouts, one bill.")
    ctx.area(f"{req_id}: paid · request closed")

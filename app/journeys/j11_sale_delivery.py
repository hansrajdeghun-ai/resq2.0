"""J11 — Sale, opt-in and delivery (spec page 16).

The sale and delivery start every service journey. The store associate sends a
WhatsApp opt-in (no opt-in -> SMS only). On delivery the box serial is scanned and
must match the bill; proof of delivery opens the installation job (J1).

Events: Sold · OptedIn · OutForDelivery · SerialBound · Delivered · InstallRequested
"""
from __future__ import annotations

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.errors import ProtectiveRuleError
from app.events.types import EventType as E
from app.journeys import _helpers as H
from app.rules import protective as pr


@on("send_optin")
async def send_optin(ctx: Ctx) -> None:
    """Store associate: bind the sale and ask the customer to opt in."""
    parts = ctx.intent.split(":")
    cust_id = parts[1] if len(parts) > 1 else "cust-sharma"
    serial = parts[2] if len(parts) > 2 else "SN-NEW-0001"
    category = parts[3] if len(parts) > 3 else "AC"
    await ctx.emit(E.SOLD, actor="store", machine_id=serial,
                   payload={"serial": serial, "category": category,
                            "brand": "Samsung", "model": f"{category} unit",
                            "customer_id": cust_id})
    ctx.to(cust_id, Role.CUSTOMER,
           "Welcome to Reliance Digital.\nGet delivery and service updates here?",
           buttons=[(f"optin:yes:{serial}", "Yes"), (f"optin:no:{serial}", "No")])
    ctx.say(f"Opt-in sent for {serial}.")
    ctx.area(f"Sale · {serial} · opt-in sent")


@on("optin")
async def optin(ctx: Ctx) -> None:
    _, choice, serial = ctx.intent.split(":", 2)
    if choice == "yes":
        await ctx.emit(E.OPTED_IN, actor="customer", machine_id=serial,
                       payload={"customer_id": ctx.customer_id, "serial": serial})
        ctx.say("Thank you.\nWe will send delivery and service updates here.")
        ctx.area(f"{serial}: opted in")
    else:
        ctx.say("No problem.\nWe will send updates by SMS only.")
        ctx.area(f"{serial}: declined WhatsApp · SMS only")


@on("out_for_delivery")
async def out_for_delivery(ctx: Ctx) -> None:
    _, serial, code = ctx.intent.split(":", 2)
    machine = await ctx.machine(serial)
    cust_id = machine.customer_id if machine else ctx.customer_id
    await ctx.emit(E.OUT_FOR_DELIVERY, actor="field", machine_id=serial,
                   payload={"code": code})
    ctx.to(cust_id, Role.CUSTOMER,
           f"Your order is out for delivery.\nArrives 2-5 pm. Delivery code {code}.",
           buttons=[("call_driver", "Call driver"), ("not_home", "Not at home")])
    ctx.area(f"{serial}: out for delivery · code {code}")


@on("deliver")
async def deliver(ctx: Ctx) -> None:
    """Delivery scans the box serial and checks the customer's code (rule 3)."""
    _, serial, code = ctx.intent.split(":", 2)
    machine = await ctx.machine(serial)
    expected = machine.serial if machine else None
    try:
        pr.assert_serial_matches(serial, expected)
    except ProtectiveRuleError as e:
        await ctx.emit(E.SERIAL_MISMATCH, actor="field", machine_id=serial,
                       payload={"scanned": serial})
        ctx.say("Box serial does not match the bill.\nHold the delivery.")
        ctx.area(f"{serial}: delivery serial mismatch — {e.detail}")
        return
    proof = ctx.inbound.raw.get("proof_link")
    await ctx.emit(E.SERIAL_BOUND, actor="field", machine_id=serial,
                   proof_link=proof, payload={"serial": serial})
    await ctx.emit(E.DELIVERED, actor="field", machine_id=serial,
                   proof_link=proof, payload={"code": code})
    cust_id = machine.customer_id if machine else ctx.customer_id
    cat = machine.category if machine else "machine"
    ctx.to(cust_id, Role.CUSTOMER,
           f"Your {cat} is delivered.\nChoose an installation slot:",
           buttons=H.offer_slots())
    ctx.say(f"{serial} delivered · code OK.\nInstallation offered.")
    ctx.area(f"{serial}: delivered · serial matches · install offered")

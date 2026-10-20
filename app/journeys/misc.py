"""Small shared customer intents: my machines (the ledger), driver, not-at-home."""
from __future__ import annotations

from sqlalchemy import select

from app.engine.context import Ctx
from app.engine.router import on
from app.journeys import _helpers as H
from app.models.ledger import Machine


@on("my_machines")
async def my_machines(ctx: Ctx) -> None:
    """The customer's ledger — every machine bound to the household."""
    machines = (await ctx.session.scalars(
        select(Machine).where(Machine.customer_id == ctx.customer_id)
    )).all()
    if not machines:
        ctx.say("No machines on your account yet.\nThey appear after your first delivery.")
        return
    lines = []
    for m in machines[:3]:
        cover = "in warranty" if H.is_in_warranty(m) else "out of warranty"
        lines.append(f"{m.brand or ''} {m.category or ''} · {cover}".strip())
    ctx.say("Your machines:\n" + "\n".join(lines))
    ctx.area(f"{ctx.customer_id}: viewed my machines ({len(machines)})")


@on("call_driver")
async def call_driver(ctx: Ctx) -> None:
    ctx.say("Connecting you to the driver\nthrough a masked number.")


@on("not_home")
async def not_home(ctx: Ctx) -> None:
    ctx.say("No problem.\nTell us a new delivery time.")


@on("dispute_open")
async def dispute_open(ctx: Ctx) -> None:
    ctx.say("Which line? Reply dispute:<job>\nand we will check the ledger.")

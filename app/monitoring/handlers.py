"""Area-manager intents: status on request, take over, hand back, digest.

These run on the area-manager number (spec 2.6). No separate dashboard — the bottom
lane of every journey plus these replies are what the area manager sees.
"""
from __future__ import annotations

from sqlalchemy import select

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.models.ops import Conversation
from app.monitoring import service as M


@on("status")
async def status(ctx: Ctx) -> None:
    # "status R-1031" or "late jobs today"
    text = (ctx.inbound.text or ctx.intent or "").strip()
    token = text.replace("status", "").strip()
    if token.upper().startswith("R-"):
        ctx.say(await M.job_status(ctx.session, token.upper()))
    else:
        late = await M.late_jobs(ctx.session)
        ctx.say("Late jobs now:\n" + (", ".join(late) if late else "none"))


@on("take_over")
async def take_over(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1] if ":" in ctx.intent else ""
    await M.take_over(ctx.session, job_id, by=ctx.inbound.from_id)
    ctx.say(f"You have taken over {job_id}.\nThe agent will stay quiet on it.")


@on("hand_back")
async def hand_back(ctx: Ctx) -> None:
    job_id = ctx.intent.split(":", 1)[1] if ":" in ctx.intent else ""
    await M.hand_back(ctx.session, job_id)
    # tell the customer(s) on this thread the assistant is back, and un-pin the
    # (possibly placeholder) job so their next message routes to a fresh journey
    convs = (await ctx.session.scalars(
        select(Conversation).where(Conversation.active_job_id == job_id))).all()
    for c in convs:
        ctx.to(c.customer_id, Role.CUSTOMER,
               "You're back with the resQ assistant 🤖\nHow can I help?")
        c.active_job_id = None
    ctx.say(f"{job_id} handed back to the agent.")


@on("digest")
async def digest(ctx: Ctx) -> None:
    ctx.say(await M.digest(ctx.session))

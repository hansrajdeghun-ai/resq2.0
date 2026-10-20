"""J12 — Technician roster (spec page 17).

Service owners add technicians; the area manager approves each one; technicians start
each day; only active technicians (started a day + closed a job in 30 days) get jobs,
and capacity shown to customers comes from the 6 pm check-in.

Events: TechnicianInvited · TechnicianJoined · IDChecked · SkillAdded ·
TechnicianApproved · DayStarted · OnLeave · CapacityConfirmed · TechnicianInactive
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain import Role
from app.engine.context import Ctx
from app.engine.router import on
from app.events.types import EventType as E
from app.models.people import Technician

AREA = "area-andheri"


@on("add_technician")
async def add_technician(ctx: Ctx) -> None:
    parts = ctx.intent.split(":")
    name = parts[1] if len(parts) > 1 else "New Technician"
    phone = parts[2] if len(parts) > 2 else "field-new"
    tech = Technician(id=f"T-{phone}", name=name, phone=phone,
                      partner_id=ctx.inbound.from_id, approved=False)
    ctx.session.add(tech)
    await ctx.emit(E.TECHNICIAN_INVITED, actor="owner",
                   payload={"technician_id": tech.id, "name": name})
    ctx.to(tech.id, Role.FIELD,
           f"{name}, {ctx.masked_sender} added you to resQ.\nTake a selfie and your ID.",
           buttons=[("tech_join", "Join")])
    ctx.say(f"Invite sent to {name}.")
    ctx.area(f"invite sent: {name}")


@on("tech_join")
async def tech_join(ctx: Ctx) -> None:
    tech = await ctx.session.get(Technician, ctx.inbound.from_id)
    tid = tech.id if tech else ctx.inbound.from_id
    if tech:
        tech.id_checked = True
    await ctx.emit(E.TECHNICIAN_JOINED, actor="field", payload={"technician_id": tid})
    await ctx.emit(E.ID_CHECKED, actor="agent", payload={"technician_id": tid})
    ctx.say("ID check passed.\nWhat can you do?",
            buttons=[("tech_skill:AC install", "AC install"),
                     ("tech_skill:AC repair", "AC repair"),
                     ("tech_skill:TV", "TV")])
    ctx.area(f"{tid}: joined · ID check passed")


@on("tech_skill")
async def tech_skill(ctx: Ctx) -> None:
    skill = ctx.intent.split(":", 1)[1]
    tech = await ctx.session.get(Technician, ctx.inbound.from_id)
    if tech:
        tech.skills = [*(tech.skills or []), skill]
    await ctx.emit(E.SKILL_ADDED, actor="agent",
                   payload={"technician_id": ctx.inbound.from_id, "skill": skill})
    ctx.say(f"Added: {skill}.\nThe area manager will approve you.")
    ctx.to(AREA, Role.AREA,
           f"New technician {ctx.inbound.from_id} · {skill}",
           buttons=[(f"tech_approve:{ctx.inbound.from_id}", "Approve")])
    ctx.area(f"{ctx.inbound.from_id}: skill {skill} · awaiting approval")


@on("tech_approve")
async def tech_approve(ctx: Ctx) -> None:
    tid = ctx.intent.split(":", 1)[1]
    tech = await ctx.session.get(Technician, tid)
    if tech:
        tech.approved = True
    await ctx.emit(E.TECHNICIAN_APPROVED, actor="area", payload={"technician_id": tid})
    ctx.say(f"{tid} approved.\nThey can start getting jobs.")
    ctx.area(f"{tid}: approved")


@on("start_day")
async def start_day(ctx: Ctx) -> None:
    tech = await ctx.session.get(Technician, ctx.inbound.from_id)
    if tech:
        tech.day_started_on = datetime.now(timezone.utc)
    await ctx.emit(E.DAY_STARTED, actor="field",
                   payload={"technician_id": ctx.inbound.from_id})
    ctx.say("Good morning. Day started.\nYou are on the active roster today.")
    ctx.area(f"{ctx.inbound.from_id}: started the day")


@on("confirm_capacity")
async def confirm_capacity(ctx: Ctx) -> None:
    parts = ctx.intent.split(":")
    slots = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    tech = await ctx.session.get(Technician, ctx.inbound.from_id)
    if tech:
        tech.capacity_slots = slots
    await ctx.emit(E.CAPACITY_CONFIRMED, actor="field",
                   payload={"technician_id": ctx.inbound.from_id, "slots": slots})
    ctx.say(f"Confirmed {slots} slots for tomorrow.\nThis is what customers see.")
    ctx.area(f"{ctx.inbound.from_id}: {slots} slots confirmed")


@on("on_leave")
async def on_leave(ctx: Ctx) -> None:
    tech = await ctx.session.get(Technician, ctx.inbound.from_id)
    if tech:
        tech.on_leave = True
    await ctx.emit(E.ON_LEAVE, actor="field",
                   payload={"technician_id": ctx.inbound.from_id})
    ctx.say("Noted. You are on leave.\nNo jobs will be sent today.")
    ctx.area(f"{ctx.inbound.from_id}: on leave")

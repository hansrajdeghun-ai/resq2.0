"""Surface-agnostic REST API — consumed by the Chrome extension, the app, and the
web demo console. Same engine + event log as WhatsApp; nothing here is WhatsApp-specific.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundMessage
from app.db import get_session
from app.domain import Role
from app.engine.router import dispatch
from app.models.event import Event
from app.models.ledger import Job, Machine
from app.models.ops import ActionRegister, Alert
from app.monitoring import service as M

router = APIRouter(prefix="/api", tags=["api"])


class SimIn(BaseModel):
    role: Role = Role.CUSTOMER
    from_id: str
    text: str | None = None
    button_id: str | None = None
    label: str | None = None  # friendly label of a tapped button (for chat echo)
    proof_link: str | None = None
    place: str | None = None
    language: str | None = None


def _msg_dict(m) -> dict:
    return {"to": m.to_id, "role": m.role.value, "text": m.text,
            "buttons": [{"id": b.id, "title": b.title} for b in m.buttons],
            "list_rows": [{"id": b.id, "title": b.title} for b in m.list_rows]}


@router.post("/sim")
async def sim(inp: SimIn, session: AsyncSession = Depends(get_session)) -> dict:
    """Drive the engine with one inbound message; return the replies (demo console)."""
    raw = {}
    if inp.proof_link:
        raw["proof_link"] = inp.proof_link
    if inp.place:
        raw["place"] = inp.place
    if inp.label:
        raw["label"] = inp.label
    inbound = InboundMessage(role=inp.role, from_id=inp.from_id, text=inp.text,
                             button_id=inp.button_id, language=inp.language, raw=raw)
    out = await dispatch(session, inbound)
    return {"replies": [_msg_dict(m) for m in out]}


@router.post("/vision/{kind}")
async def vision_read(kind: str, file: UploadFile = File(...),
                     hint: str | None = Form(None)) -> dict:
    """Read serial / error_code / gauge from an uploaded photo (AI vision)."""
    from app.agent import vision

    data = await file.read()
    value = await vision.read(kind, image_bytes=data,
                              media_type=file.content_type or "image/jpeg", hint=hint)
    return {"kind": kind, "value": value}


@router.post("/voice")
async def voice_transcribe(file: UploadFile = File(...),
                          hint: str | None = Form(None)) -> dict:
    """Transcribe an uploaded voice note (Whisper when an OpenAI key is set)."""
    from app.agent import voice

    data = await file.read()
    text = await voice.transcribe(audio_bytes=data,
                                  filename=file.filename or "note.ogg", hint=hint)
    return {"text": text}


@router.get("/inbox/{to_id}")
async def inbox(to_id: str, after: int = 0,
                session: AsyncSession = Depends(get_session)) -> dict:
    """Messages addressed to this persona after a given seq (role-page polling)."""
    from app.models.ops import Message

    rows = (await session.scalars(
        select(Message).where(Message.to_id == to_id, Message.seq > after)
        .order_by(Message.seq))).all()
    return {"messages": [{"seq": m.seq, "role": m.role, "text": m.text,
                          "buttons": m.buttons} for m in rows]}


@router.get("/ledger/{customer_id}")
async def ledger(customer_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    machines = (await session.scalars(
        select(Machine).where(Machine.customer_id == customer_id))).all()
    jobs = (await session.scalars(
        select(Job).where(Job.customer_id == customer_id))).all()
    return {
        "customer_id": customer_id,
        "machines": [{"serial": m.serial, "brand": m.brand, "category": m.category,
                      "wty_end": m.wty_end.isoformat() if m.wty_end else None,
                      "replaced_by": m.replaced_by_serial} for m in machines],
        "jobs": [{"id": j.id, "type": j.type, "state": j.state} for j in jobs],
    }


@router.get("/jobs")
async def jobs(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.scalars(select(Job).order_by(Job.updated_at.desc()))).all()
    return {"jobs": [{"id": j.id, "type": j.type, "state": j.state,
                      "technician": j.technician_id, "partner": j.partner_id,
                      "slot": j.slot, "rate": float(j.rate) if j.rate else None}
                     for j in rows]}


@router.get("/events")
async def events(limit: int = 50, job: str | None = None,
                 session: AsyncSession = Depends(get_session)) -> dict:
    q = select(Event).order_by(Event.seq.desc()).limit(limit)
    if job:
        q = select(Event).where(Event.job_id == job).order_by(Event.seq).limit(limit)
    rows = (await session.scalars(q)).all()
    return {"events": [{"seq": e.seq, "type": e.type, "job": e.job_id,
                        "machine": e.machine_id, "actor": e.actor,
                        "at": e.at.isoformat(), "payload": e.payload} for e in rows]}


@router.get("/alerts")
async def alerts(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.scalars(
        select(Alert).where(Alert.status == "open").order_by(Alert.created_at.desc()))).all()
    return {"alerts": [{"id": a.id, "job": a.job_id, "cause": a.cause,
                        "text": a.text, "action": a.action} for a in rows]}


@router.get("/action-register")
async def action_register(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.scalars(
        select(ActionRegister).order_by(ActionRegister.created_at.desc()))).all()
    return {"items": [{"id": r.id, "job": r.job_id, "suggestion": r.suggestion,
                       "decision": r.decision, "reason": r.reason} for r in rows]}


class Decision(BaseModel):
    decision: str  # accept | reject
    reason: str | None = None
    by: str = "area-desk"


@router.post("/action-register/{item_id}/decision")
async def decide(item_id: str, d: Decision,
                 session: AsyncSession = Depends(get_session)) -> dict:
    item = await session.get(ActionRegister, item_id)
    if not item:
        return {"status": "not found"}
    item.decision = d.decision
    item.reason = d.reason
    item.decided_by = d.by
    await session.commit()
    return {"status": "ok", "id": item_id, "decision": d.decision}


@router.post("/takeover/{job_id}")
async def takeover(job_id: str, by: str = "area-desk",
                   session: AsyncSession = Depends(get_session)) -> dict:
    await M.take_over(session, job_id, by)
    await session.commit()
    return {"status": "taken_over", "job": job_id, "by": by}


@router.post("/handback/{job_id}")
async def handback(job_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    await M.hand_back(session, job_id)
    await session.commit()
    return {"status": "handed_back", "job": job_id}


@router.get("/digest")
async def digest(session: AsyncSession = Depends(get_session)) -> dict:
    return {"digest": await M.digest(session)}


@router.get("/export")
async def export_events(session: AsyncSession = Depends(get_session)):
    """Download the full append-only event log (hand-in artifact)."""
    import json as _json

    from fastapi.responses import Response as _Resp

    rows = (await session.scalars(select(Event).order_by(Event.seq))).all()
    payload = [{"seq": e.seq, "event_id": e.event_id, "type": e.type,
                "machine_id": e.machine_id, "job_id": e.job_id, "visit_id": e.visit_id,
                "task_id": e.task_id, "request_id": e.request_id, "actor": e.actor,
                "at": e.at.isoformat(), "place": e.place, "proof_link": e.proof_link,
                "payload": e.payload} for e in rows]
    body = _json.dumps({"events": payload, "count": len(payload)}, indent=2)
    return _Resp(content=body, media_type="application/json",
                 headers={"Content-Disposition": "attachment; filename=resq_event_log.json"})


@router.get("/qr")
async def qr(data: str):
    """A QR PNG for a payment link (UPI) or any string — generated locally."""
    import io

    import qrcode
    from fastapi.responses import Response as _Resp

    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return _Resp(content=buf.getvalue(), media_type="image/png")


@router.post("/seed")
async def seed(session: AsyncSession = Depends(get_session)) -> dict:
    """Dev helper: seed a household + partner + technician for the demo console."""
    from scripts.seed import seed_demo

    existing = await session.get(Machine, "SN-AC-4471")
    if existing:
        return {"status": "already seeded"}
    ids = await seed_demo(session)
    await session.commit()
    return {"status": "seeded", **ids}


# ─── personas (mock login) + onboarding ──────────────────────────────────────
DEFAULT_AREAS = [{"id": "area-andheri", "name": "Andheri Area Manager"}]


async def _areas(session: AsyncSession) -> list[dict]:
    from app.models.ops import Setting

    row = await session.get(Setting, "area_managers")
    return row.value if row and row.value else DEFAULT_AREAS


@router.get("/personas")
async def personas(session: AsyncSession = Depends(get_session)) -> dict:
    """Everyone you can log in as, by role — powers the mock login picker."""
    from app.models.ledger import Customer
    from app.models.people import ServicePartner, Technician

    customers = (await session.scalars(select(Customer))).all()
    owners = (await session.scalars(select(ServicePartner))).all()
    techs = (await session.scalars(select(Technician))).all()
    return {
        "customer": [{"id": c.id, "name": c.name or c.id} for c in customers],
        "owner": [{"id": o.id, "name": o.name, "backup": o.is_backup} for o in owners],
        "field": [{"id": t.id, "name": t.name, "partner": t.partner_id,
                   "approved": t.approved} for t in techs],
        "area": await _areas(session),
    }


class OnboardOwner(BaseModel):
    name: str
    phone: str | None = None
    pincodes: list[str] = []
    authority: list[str] = ["ALL"]
    is_backup: bool = False


class OnboardTech(BaseModel):
    name: str
    phone: str | None = None
    partner_id: str | None = None
    skills: list[str] = []
    pincode: str | None = None


class OnboardArea(BaseModel):
    name: str


class OnboardCustomer(BaseModel):
    name: str
    phone: str | None = None
    postal_code: str | None = None


@router.post("/onboard/owner")
async def onboard_owner(b: OnboardOwner, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models.people import ServicePartner

    pid = "P-" + b.name.lower().replace(" ", "-")
    session.add(ServicePartner(id=pid, name=b.name, phone=b.phone or pid,
                               pincodes=b.pincodes, authority=b.authority,
                               is_backup=b.is_backup, partner_class="contracted"))
    await session.commit()
    return {"status": "created", "id": pid, "role": "owner"}


@router.post("/onboard/field")
async def onboard_tech(b: OnboardTech, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models.people import Technician

    tid = "T-" + b.name.lower().replace(" ", "-")
    session.add(Technician(id=tid, name=b.name, phone=b.phone or tid,
                           partner_id=b.partner_id, skills=b.skills, pincode=b.pincode,
                           approved=True, id_checked=True, capacity_slots=5))
    await session.commit()
    return {"status": "created", "id": tid, "role": "field"}


@router.post("/onboard/area")
async def onboard_area(b: OnboardArea, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models.ops import Setting

    aid = "area-" + b.name.lower().replace(" ", "-")
    row = await session.get(Setting, "area_managers")
    areas = (row.value if row and row.value else list(DEFAULT_AREAS))
    areas.append({"id": aid, "name": b.name})
    if row:
        row.value = areas
    else:
        session.add(Setting(key="area_managers", value=areas))
    await session.commit()
    return {"status": "created", "id": aid, "role": "area"}


@router.post("/onboard/customer")
async def onboard_customer(b: OnboardCustomer, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models.ledger import Customer

    cid = "cust-" + b.name.lower().replace(" ", "-")
    session.add(Customer(id=cid, name=b.name, phone=b.phone, opted_in=True,
                         address={"postal_code": b.postal_code} if b.postal_code else {}))
    await session.commit()
    return {"status": "created", "id": cid, "role": "customer"}


# ─── admin-editable config ───────────────────────────────────────────────────
class ConfigIn(BaseModel):
    value: dict | list


@router.get("/config")
async def get_config() -> dict:
    from app.admin import config

    return {"editable": config.EDITABLE, "config": config.all_config()}


@router.put("/config/{key}")
async def put_config(key: str, body: ConfigIn,
                     session: AsyncSession = Depends(get_session)) -> dict:
    from app.admin import config

    try:
        await config.set(session, key, body.value)
        await session.commit()
    except ValueError as e:
        return {"status": "error", "detail": str(e)}
    return {"status": "saved", "key": key}


# ─── reset demo ──────────────────────────────────────────────────────────────
@router.post("/reset")
async def reset(session: AsyncSession = Depends(get_session)) -> dict:
    """Wipe all transactional data and re-seed. Keeps admin config."""
    from sqlalchemy import delete

    from app.models.event import Event
    from app.models.ledger import Customer, Job, ServiceRequest, Task, Visit
    from app.models.ops import (ActionRegister, Alert, Conversation, Message,
                                Payment, RuleViolation, Takeover)
    from app.models.people import ServicePartner, Technician
    from scripts.seed import seed_demo

    for model in (Event, Visit, Task, Job, Machine, Customer, ServiceRequest,
                  Technician, ServicePartner, Payment, ActionRegister, Alert,
                  Takeover, RuleViolation, Conversation, Message):
        await session.execute(delete(model))
    # also drop onboarded area managers (stored as a Setting) so they reset to default
    from app.models.ops import Setting
    await session.execute(delete(Setting).where(Setting.key == "area_managers"))
    ids = await seed_demo(session)
    await session.commit()
    return {"status": "reset", **ids}

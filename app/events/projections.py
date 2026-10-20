"""Fold events into read models.

The event log is the source of truth; these tables are a convenience view. Each
handler is idempotent-ish (upsert) so replaying the log rebuilds state. Unknown
events are a safe no-op — the log still records them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import JobState
from app.events.types import EventType as E
from app.models.event import Event
from app.models.ledger import Customer, Job, Machine, Visit

# Events that simply set the job to a new state.
STATE_MAP: dict[str, JobState] = {
    E.INSTALL_REQUESTED.value: JobState.REQUESTED,
    E.REPAIR_REQUESTED.value: JobState.REQUESTED,
    E.PROMISED.value: JobState.PROMISED,
    E.PARTNER_ASSIGNED.value: JobState.PROMISED,
    E.TECHNICIAN_ASSIGNED.value: JobState.ASSIGNED,
    E.EN_ROUTE.value: JobState.EN_ROUTE,
    E.ARRIVED.value: JobState.ON_SITE,
    E.WORK_DONE.value: JobState.WORK_DONE,
    E.CUSTOMER_CONFIRMED.value: JobState.CONFIRMED,
    E.CLOSED.value: JobState.CLOSED,
    E.CANCELLED.value: JobState.CANCELLED,
    E.PART_NEEDED.value: JobState.WAITING_FOR_PART,
    E.ESTIMATE_SENT.value: JobState.WAITING_FOR_APPROVAL,
    E.ESTIMATE_APPROVED.value: JobState.ON_SITE,
    E.VISIT_OPENED.value: JobState.PROMISED,
    E.BRAND_VISIT_PROMISED.value: JobState.WITH_BRAND,
    E.REOPENED.value: JobState.REVISIT,
}

COOLING_DAYS = {"install": 7, "repair": 14}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _get(session: AsyncSession, model, pk):
    return await session.get(model, pk) if pk else None


async def _upsert_machine(session: AsyncSession, event: Event) -> None:
    p = event.payload
    serial = p.get("serial") or event.machine_id
    if not serial:
        return
    m = await _get(session, Machine, serial)
    if not m:
        m = Machine(serial=serial)
        session.add(m)
    for field in (
        "object_id", "brand", "model", "category", "sales_order_no", "authority",
    ):
        if p.get(field) is not None:
            setattr(m, field, p[field])
    for field, col in (("wty_start", "wty_start"), ("wty_end", "wty_end"),
                       ("date_of_purchase", "date_of_purchase")):
        dt = _parse_dt(p.get(field))
        if dt is not None:
            setattr(m, col, dt)
    if p.get("customer_id"):
        m.customer_id = p["customer_id"]


async def _upsert_customer(session: AsyncSession, event: Event) -> None:
    p = event.payload
    cid = p.get("customer_id")
    if not cid:
        return
    c = await _get(session, Customer, cid)
    if not c:
        c = Customer(id=cid)
        session.add(c)
    for field in ("name", "phone", "language", "address"):
        if p.get(field) is not None:
            setattr(c, field, p[field])
    if event.type == E.OPTED_IN.value:
        c.opted_in = True


async def _ensure_job(session: AsyncSession, event: Event) -> Job | None:
    if not event.job_id:
        return None
    job = await _get(session, Job, event.job_id)
    if not job:
        p = event.payload
        job = Job(
            id=event.job_id,
            type=p.get("job_type", "repair"),
            state=JobState.REQUESTED.value,
            machine_serial=p.get("serial") or event.machine_id,
            customer_id=p.get("customer_id"),
            request_id=event.request_id,
        )
        session.add(job)
    return job


async def apply(session: AsyncSession, event: Event) -> None:
    """Fold one event into the read models."""
    # ledger binding events
    if event.type in (E.SOLD.value, E.SERIAL_BOUND.value, E.DELIVERED.value):
        await _upsert_machine(session, event)
        await _upsert_customer(session, event)
    if event.type == E.OPTED_IN.value:
        await _upsert_customer(session, event)

    job = await _ensure_job(session, event)
    if job is None:
        return

    p = event.payload

    # generic state transition
    new_state = STATE_MAP.get(event.type)
    if new_state:
        job.state = new_state.value

    # enrich job fields from payload
    for field in ("partner_id", "technician_id", "slot", "rate",
                  "crm_service_request_id", "in_warranty"):
        if p.get(field) is not None:
            setattr(job, field, p[field])
    if p.get("job_type"):
        job.type = p["job_type"]

    # cooling period starts at customer confirm (spec 2.3)
    if event.type == E.CUSTOMER_CONFIRMED.value:
        job.confirmed_at = event.at
        days = COOLING_DAYS.get(job.type, 7)
        job.cooling_until = event.at + timedelta(days=days)

    # visit lifecycle
    if event.type == E.TECHNICIAN_ASSIGNED.value and p.get("visit_id"):
        v = await _get(session, Visit, p["visit_id"])
        if not v:
            v = Visit(
                id=p["visit_id"],
                job_id=job.id,
                technician_id=p.get("technician_id"),
                number=p.get("visit_number", 1),
                slot=p.get("slot"),
                payable=p.get("payable", True),
            )
            session.add(v)
    if event.type == E.SERIAL_VERIFIED.value and event.visit_id:
        v = await _get(session, Visit, event.visit_id)
        if v:
            v.serial_verified = True

    job.updated_at = event.at

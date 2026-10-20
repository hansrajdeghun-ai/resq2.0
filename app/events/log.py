"""Append-only writer for the event log.

This is the ONLY way state changes enter the system. After persisting the event
it folds it into the read models (projections). Events are never updated/deleted.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.types import EventType
from app.models.event import Event


async def append(
    session: AsyncSession,
    type: EventType | str,
    actor: str,
    *,
    machine_id: str | None = None,
    job_id: str | None = None,
    visit_id: str | None = None,
    task_id: str | None = None,
    request_id: str | None = None,
    place: str | None = None,
    proof_link: str | None = None,
    payload: dict | None = None,
) -> Event:
    event = Event(
        type=type.value if isinstance(type, EventType) else str(type),
        actor=actor,
        machine_id=machine_id,
        job_id=job_id,
        visit_id=visit_id,
        task_id=task_id,
        request_id=request_id,
        place=place,
        proof_link=proof_link,
        payload=payload or {},
    )
    session.add(event)
    await session.flush()  # assign seq / event_id

    # fold into read models (import here to avoid circular import)
    from app.events import projections

    await projections.apply(session, event)
    return event

"""Human-readable id generators (R-xxxx jobs, V- visits, T- tasks, REQ- requests).

Counters are derived from the max existing id so ids stay stable across restarts.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import Job, ServiceRequest, Task, Visit


async def _next(session: AsyncSession, model, prefix: str, start: int) -> str:
    count = await session.scalar(select(func.count()).select_from(model))
    return f"{prefix}{start + (count or 0)}"


async def next_job_id(session: AsyncSession) -> str:
    return await _next(session, Job, "R-", 1001)


async def next_visit_id(session: AsyncSession) -> str:
    return await _next(session, Visit, "V-", 5001)


async def next_task_id(session: AsyncSession) -> str:
    return await _next(session, Task, "T-", 9001)


async def next_request_id(session: AsyncSession) -> str:
    return await _next(session, ServiceRequest, "REQ-", 301)

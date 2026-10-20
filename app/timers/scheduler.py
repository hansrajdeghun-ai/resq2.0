"""APScheduler setup — runs the timer sweeps on an interval.

Started from the FastAPI lifespan. Each sweep opens its own session and commits.
Kept simple: a 60-second tick drives the due-time checks inside each sweep.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import SessionLocal
from app.timers.service import ALL_SWEEPS

log = logging.getLogger("resq.timers")
_scheduler: AsyncIOScheduler | None = None


async def _run_all() -> None:
    async with SessionLocal() as s:
        for name, sweep in ALL_SWEEPS.items():
            try:
                acted = await sweep(s)
                if acted:
                    log.info("timer %s acted on %s", name, acted)
            except Exception as e:  # noqa: BLE001
                log.error("timer %s failed: %s", name, e)
        await s.commit()


def start() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        _scheduler.add_job(_run_all, "interval", seconds=60, id="resq-sweeps")
        _scheduler.start()
        log.info("timers started")
    return _scheduler


def stop() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

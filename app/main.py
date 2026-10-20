"""resQ 2.0 — FastAPI application entry point.

Surface-agnostic engine. Mounts the WhatsApp webhook and the staff/app API.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("resq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # load admin-editable config (seed defaults on first run)
    from app.admin import config as admin_config
    from app.db import SessionLocal
    async with SessionLocal() as s:
        await admin_config.load(s)
        await s.commit()
    log.info("resQ started — env=%s use_mocks=%s db=%s",
             settings.app_env, settings.use_mocks,
             "sqlite" if settings.is_sqlite else "postgres")
    from app.timers import scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title="resQ 2.0", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "use_mocks": settings.use_mocks,
        "kill_switch": settings.kill_switch,
        "kapture_base_url": settings.kapture_base_url,
        "kapture_create_ready": settings.kapture_create_ready,
    }


from app.api.routes import router as api_router  # noqa: E402
from app.channels.whatsapp.webhook import router as wa_router  # noqa: E402

app.include_router(api_router)
app.include_router(wa_router)

# ─── web app: clean paths per role + static assets ────────────────────────────
from fastapi.responses import FileResponse  # noqa: E402

_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "clients", "web")


def _page(name: str):
    return FileResponse(os.path.join(_WEB_DIR, name))


if os.path.isdir(_WEB_DIR):
    @app.get("/")
    async def _login():
        return _page("login.html")

    @app.get("/customer")
    async def _customer():
        return _page("customer.html")

    @app.get("/owner")
    @app.get("/field")
    @app.get("/area")
    async def _role():
        return _page("role.html")

    @app.get("/admin")
    async def _admin():
        return _page("admin.html")

    @app.get("/demo")
    async def _demo():
        return _page("index.html")

    # static assets (css/js) — mounted last so the routes above win
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=False), name="web")

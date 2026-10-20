"""WhatsApp Cloud API webhook — verify (GET) + receive (POST).

Routes each inbound message to a role by the phone_number_id it arrived on (the 4
numbers, spec 2.1), turns it into an InboundMessage, dispatches it through the engine,
and sends the replies. Signature check uses the app secret when configured.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Request, Response

from app.channels.base import InboundMessage, Media
from app.channels.whatsapp import cloud_api
from app.config import settings
from app.db import SessionLocal
from app.domain import Role
from app.engine.router import dispatch

log = logging.getLogger("resq.whatsapp")
router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


def _role_for(phone_number_id: str) -> Role:
    mapping = {
        settings.wa_phone_id_customer: Role.CUSTOMER,
        settings.wa_phone_id_owner: Role.OWNER,
        settings.wa_phone_id_field: Role.FIELD,
        settings.wa_phone_id_area: Role.AREA,
    }
    return mapping.get(phone_number_id, Role.CUSTOMER)


def _verify_signature(body: bytes, header: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        return True  # not configured in dev
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), body,
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.split("=", 1)[1], expected)


@router.get("")
async def verify(request: Request) -> Response:
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == settings.whatsapp_webhook_verify_token):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


def _to_inbound(value: dict, msg: dict) -> InboundMessage:
    role = _role_for(value.get("metadata", {}).get("phone_number_id", ""))
    from_id = msg.get("from", "")
    text, button_id, media = None, None, []
    mtype = msg.get("type")
    if mtype == "text":
        text = msg["text"]["body"]
    elif mtype == "interactive":
        inter = msg["interactive"]
        if inter.get("type") == "button_reply":
            button_id = inter["button_reply"]["id"]
        elif inter.get("type") == "list_reply":
            button_id = inter["list_reply"]["id"]
    elif mtype in ("image", "video", "audio", "document"):
        media = [Media(kind=mtype, url=msg.get(mtype, {}).get("id"))]
    lang = (msg.get("context") or {}).get("language")
    return InboundMessage(role=role, from_id=from_id, text=text,
                          button_id=button_id, media=media, language=lang, raw=msg)


@router.post("")
async def receive(request: Request) -> dict:
    body = await request.body()
    if not _verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        return {"status": "bad signature"}
    data = await request.json()
    handled = 0
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                inbound = _to_inbound(value, msg)
                async with SessionLocal() as s:
                    out = await dispatch(s, inbound)
                await cloud_api.send_all(out)
                handled += 1
    return {"status": "ok", "handled": handled}

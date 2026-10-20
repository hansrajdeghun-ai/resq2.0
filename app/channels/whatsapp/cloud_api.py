"""WhatsApp Cloud API sender — renders OutboundMessage to the Graph API.

One sender per role (each role is a different WhatsApp number / phone_number_id).
Text, reply buttons (<=3) and list messages (<=10 rows) map to §2.5-compliant sends.
Needs WHATSAPP_ACCESS_TOKEN + the 4 phone-number ids (PENDING items #1,#2).
"""
from __future__ import annotations

import logging

import httpx

from app.channels.base import OutboundMessage
from app.config import settings
from app.domain import Role

log = logging.getLogger("resq.whatsapp")


def _graph_url(phone_number_id: str) -> str:
    return f"https://graph.facebook.com/{settings.whatsapp_api_version}/{phone_number_id}/messages"


def _payload(msg: OutboundMessage) -> dict:
    base = {"messaging_product": "whatsapp", "to": msg.to_id}
    if msg.buttons:
        return {**base, "type": "interactive", "interactive": {
            "type": "button",
            "body": {"text": msg.text},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": b.id, "title": b.title}}
                for b in msg.buttons]}}}
    if msg.list_rows:
        return {**base, "type": "interactive", "interactive": {
            "type": "list",
            "body": {"text": msg.text},
            "action": {"button": msg.list_button, "sections": [
                {"rows": [{"id": r.id, "title": r.title} for r in msg.list_rows]}]}}}
    if msg.template:
        return {**base, "type": "template", "template": {
            "name": msg.template, "language": {"code": "en"}}}
    return {**base, "type": "text", "text": {"body": msg.text}}


async def send(msg: OutboundMessage) -> dict:
    phone_id = settings.wa_phone_id_for(msg.role.value)
    if not phone_id or not settings.whatsapp_access_token:
        log.info("[WA mock send] %s -> %s: %s", msg.role.value, msg.to_id,
                 msg.text.replace("\n", " / "))
        return {"mock": True}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            _graph_url(phone_id),
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json=_payload(msg),
        )
    if r.status_code >= 300:
        log.error("WA send failed %s: %s", r.status_code, r.text[:200])
    return r.json() if r.content else {}


async def send_all(messages: list[OutboundMessage]) -> None:
    for m in messages:
        await send(m)

"""GCP Pub/Sub consumer for service-order events (SO PubSub Consumer Guide).

Subscription: fynd-hackathon-sub (project sr-prj-rrl-retail-release-resq).
Body is a JSON array with exactly one service-order object. Idempotent on
service_order_no (upsert). The google-cloud-pubsub import is lazy so the app runs
without the lib / SA key (PENDING item #8).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.integrations.kapture.sync import ingest_service_order

log = logging.getLogger("resq.pubsub")


async def process_body(session: AsyncSession, body: bytes) -> list[str]:
    """Decode a Pub/Sub message body and fold its service order(s) into the ledger."""
    payload = json.loads(body.decode("utf-8"))
    orders = payload if isinstance(payload, list) else [payload]
    handled: list[str] = []
    for so in orders:
        await ingest_service_order(session, so)
        if so.get("service_order_no"):
            handled.append(so["service_order_no"])
    return handled


def run_consumer() -> None:
    """Blocking streaming pull (run in a worker). Real SA key required."""
    from google.cloud import pubsub_v1  # lazy import

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(
        settings.gcp_project_id, settings.pubsub_subscription
    )

    def callback(message) -> None:  # pragma: no cover - needs live subscription
        import asyncio

        async def _run():
            async with SessionLocal() as s:
                await process_body(s, message.data)
                await s.commit()

        try:
            asyncio.run(_run())
            message.ack()
        except Exception as e:  # noqa: BLE001
            log.error("pubsub processing failed: %s", e)
            message.nack()

    streaming = subscriber.subscribe(sub_path, callback=callback)
    log.info("Listening on %s ...", sub_path)
    try:
        streaming.result()
    except KeyboardInterrupt:
        streaming.cancel()
        streaming.result()

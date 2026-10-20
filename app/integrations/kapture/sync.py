"""Turn Kapture reads + Pub/Sub service-order events into ledger events.

Machine-first: every record binds a serial to a household (SerialBound), so the
ledger populates from real Kapture data. Defensive against nulls — the middleware
sends missing fields as null, not omitted.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import log
from app.events.types import EventType


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _category_from_desc(desc: str | None) -> str | None:
    if not desc:
        return None
    d = desc.upper()
    for key in ("AC", "TV", "PANEL", "WASH", "REF", "FRIDGE", "PHONE", "LED"):
        if key in d:
            return {"PANEL": "TV", "LED": "TV", "WASH": "WASHER",
                    "REF": "AC", "FRIDGE": "AC"}.get(key, key)
    return None


async def ingest_rcp_record(session: AsyncSession, rec: dict) -> str | None:
    """One record from /rcp/v1/order/listing -> a SerialBound event. Returns serial."""
    obj = rec.get("object") or {}
    cust = rec.get("customer") or {}
    serial = obj.get("serial_no")
    object_id = obj.get("objectid") or obj.get("object_id")
    if not serial and not object_id:
        return None

    cid = cust.get("bpid") or obj.get("partner_no")
    name = " ".join(x for x in (cust.get("first_name"), cust.get("last_name")) if x) or None

    await log.append(
        session,
        EventType.SERIAL_BOUND,
        actor="kapture",
        machine_id=serial or object_id,
        payload={
            "serial": serial or object_id,
            "object_id": object_id,
            "brand": obj.get("brand"),
            "model": obj.get("article_description"),
            "category": _category_from_desc(obj.get("article_description")),
            "sales_order_no": obj.get("sales_order_no"),
            "customer_id": cid,
            "name": name,
            "phone": cust.get("primary_mobile_number"),
            "address": cust.get("address") or {},
            "wty_start": obj.get("wty_start_date"),
            "wty_end": obj.get("wty_end_date"),
            "contracts": rec.get("contracts") or [],
        },
    )
    return serial or object_id


async def sync_ledger_by_mobile(session: AsyncSession, client, mobile: str) -> list[str]:
    """Pull a household's machines from Kapture and fold them into the ledger."""
    data = await client.rcp_order_listing(mobile_no=mobile)
    serials: list[str] = []
    for rec in data.get("content", []):
        s = await ingest_rcp_record(session, rec)
        if s:
            serials.append(s)
    return serials


async def ingest_service_order(session: AsyncSession, so: dict) -> None:
    """A service-order object (from SO details or the Pub/Sub stream) -> events.

    Binds the machine + customer, then reflects the SO status onto the ledger.
    """
    iobj = so.get("iObject") or so.get("ref_object") or {}
    cust = so.get("customer") or so.get("sold_to_customer") or {}
    serial = iobj.get("serial_no")
    object_id = iobj.get("objectid") or iobj.get("object_id") or so.get("ref_object_id")
    cid = cust.get("bpid") or cust.get("partner_no") or so.get("soldtoparty")

    if serial or object_id:
        await log.append(
            session,
            EventType.SERIAL_BOUND,
            actor="kapture",
            machine_id=serial or object_id,
            payload={
                "serial": serial or object_id,
                "object_id": object_id,
                "brand": iobj.get("brand"),
                "category": (so.get("iris") or {}).get("product_category"),
                "sales_order_no": iobj.get("sales_order_no"),
                "customer_id": cid,
                "name": cust.get("fullname")
                or " ".join(x for x in (cust.get("first_name"), cust.get("last_name")) if x)
                or None,
                "phone": cust.get("phone") or cust.get("primary_mobile_number"),
            },
        )

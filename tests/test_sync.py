"""Ledger sync: Kapture reads + Pub/Sub events fold into the machine-first ledger."""
from __future__ import annotations

import pytest

from app.integrations.kapture import MockKaptureClient
from app.integrations.kapture.sync import sync_ledger_by_mobile
from app.integrations.pubsub.mock import publish_sample
from app.models.ledger import Customer, Machine

pytestmark = pytest.mark.asyncio


async def test_kapture_record_binds_serial_to_household(session):
    # shape mirrors the real /rcp/v1/order/listing response we verified live
    rec = {
        "object": {"serial_no": "2142143243244", "objectid": "1189415487",
                   "brand": "Reconnect", "sales_order_no": "4278399759",
                   "wty_start_date": "2026-08-03T12:27:25.000+00:00",
                   "wty_end_date": "2028-08-02T12:27:25.000+00:00"},
        "customer": {"first_name": "ABHIRUCHI", "last_name": "FOODS",
                     "primary_mobile_number": "7259678000", "bpid": "234162893",
                     "address": {"city": "Bangalore", "postal_code": "560102"}},
        "contracts": [{"contract_no": "6105343538"}],
    }
    from app.integrations.kapture.sync import ingest_rcp_record

    await ingest_rcp_record(session, rec)
    await session.commit()

    m = await session.get(Machine, "2142143243244")
    assert m.brand == "Reconnect"
    assert m.object_id == "1189415487"
    assert m.wty_end is not None
    assert m.customer_id == "234162893"
    c = await session.get(Customer, "234162893")
    assert c.name == "ABHIRUCHI FOODS"
    assert c.phone == "7259678000"


async def test_sync_by_mobile_uses_client(session):
    serials = await sync_ledger_by_mobile(session, MockKaptureClient(), "7259678000")
    await session.commit()
    assert serials  # at least one machine bound
    assert await session.get(Machine, serials[0]) is not None


async def test_pubsub_service_order_folds_into_ledger(session):
    await publish_sample(session)
    await session.commit()
    m = await session.get(Machine, "SN12345678")
    assert m is not None
    assert m.brand == "RELIANCE"
    c = await session.get(Customer, "100000678")
    assert c is not None

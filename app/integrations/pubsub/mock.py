"""Mock Pub/Sub publisher — the sample service-order payload from the guide.

Lets the consumer path run offline. publish_sample() folds one SO into the ledger.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pubsub.consumer import process_body

# Trimmed version of the guide's sample (section 6). snake_case, nulls allowed.
SAMPLE_SO: dict = {
    "service_order_no": "8000012345",
    "user_status": "OPEN",
    "process_type": "ZFSO",
    "ref_object_id": "900000012345",
    "service_req_no": "SR-2026-001",
    "iris": {"product_category": "AC", "symptom_code": "S001"},
    "customer": {
        "soldToParty": "100000678", "bpid": "100000678",
        "first_name": "Rahul", "last_name": "Sharma",
        "primary_mobile_number": "9876543210",
        "address": {"city": "Mumbai", "postal_code": "400001", "region": "MH"},
    },
    "iObject": {
        "object_id": "900000012345", "objectid": "900000012345",
        "serial_no": "SN12345678", "brand": "RELIANCE",
        "sales_order_no": "6000012345",
        "wty_start_date": "2025-01-15T00:00:00.000+0000",
        "wty_end_date": "2027-01-14T23:59:59.000+0000",
        "contracts": [{"contract_no": "4000012345", "contract_type": "RCP",
                       "cont_status": "A", "rcp_sale_price": 4999.0}],
    },
}


async def publish_sample(session: AsyncSession, so: dict | None = None) -> None:
    import json

    body = json.dumps([so or SAMPLE_SO]).encode("utf-8")
    await process_body(session, body)

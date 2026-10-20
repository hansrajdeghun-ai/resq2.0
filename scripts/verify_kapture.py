"""Read-only connectivity check against the live Kapture UAT.

Usage: python -m scripts.verify_kapture [mobileNo]
Hits /rcp/v1/order/listing with the configured Basic auth. Read-only; safe.
"""
from __future__ import annotations

import asyncio
import sys

from app.integrations.kapture.client import KaptureClient


async def main() -> None:
    mobile = sys.argv[1] if len(sys.argv) > 1 else "7259678000"
    client = KaptureClient()
    print(f"GET {client.base_url}/rcp/v1/order/listing?mobileNo={mobile}")
    try:
        data = await client.rcp_order_listing(mobile_no=mobile)
        content = data.get("content", [])
        print(f"OK — {len(content)} record(s)")
        for rec in content[:3]:
            obj = rec.get("object", {})
            cust = rec.get("customer", {})
            print(f"  serial={obj.get('serial_no')} brand={obj.get('brand')} "
                  f"customer={cust.get('first_name')} {cust.get('last_name')} "
                  f"contracts={len(rec.get('contracts', []))}")
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {type(e).__name__}: {e}")
        print("If this is a timeout/403, IP allowlisting (pending item #7) may be needed.")


if __name__ == "__main__":
    asyncio.run(main())

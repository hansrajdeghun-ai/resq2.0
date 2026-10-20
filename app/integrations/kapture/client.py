"""Kapture REST client (API Contract).

Base URL (UAT, live): https://resqplatform.prep.ril.com/api
Auth: HTTP Basic with Kapture credentials.
Listing/detail/lookup APIs: read-only, no checksum.
The two create APIs require an x-checksum (needs the pending checksum key) and go
through write-back; until the key is present, use the mock.

Every response is wrapped in the common envelope {version,timestamp,status,data,pageMeta}.
"""
from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings
from app.integrations.kapture.checksum import for_uri

log = logging.getLogger("resq.kapture")


class KaptureError(RuntimeError):
    pass


class KaptureClient:
    def __init__(
        self,
        base_url: str | None = None,
        credential_id: str | None = None,
        secret_key: str | None = None,
        checksum_key: str | None = None,
        timeout: float = 20.0,
    ):
        self.base_url = (base_url or settings.kapture_base_url).rstrip("/")
        cid = credential_id or settings.kapture_credential_id
        secret = secret_key or settings.kapture_secret_key
        token = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        self._auth_header = f"Basic {token}"
        self.checksum_key = checksum_key or settings.kapture_checksum_key
        self._timeout = timeout
        # TLS verification: a CA bundle path, or True/False (see config).
        if not settings.kapture_verify_ssl:
            self._verify: str | bool = False
        elif settings.kapture_ca_bundle:
            self._verify = settings.kapture_ca_bundle
        else:
            self._verify = True

    # ─── low level ──────────────────────────────────────────────────────────
    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout, verify=self._verify) as c:
            r = await c.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"Authorization": self._auth_header},
            )
        return self._unwrap(r, path)

    async def _post(self, path: str, body: dict, transaction_number: str) -> dict:
        if not self.checksum_key:
            raise KaptureError(
                "checksum key not configured — create APIs are blocked (use mock)"
            )
        headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "x-checksum": for_uri(self.checksum_key, path),
            "transactionNumber": transaction_number,
        }
        async with httpx.AsyncClient(timeout=self._timeout, verify=self._verify) as c:
            r = await c.post(f"{self.base_url}{path}", json=body, headers=headers)
        return self._unwrap(r, path)

    @staticmethod
    def _unwrap(r: httpx.Response, path: str) -> dict:
        if r.status_code != 200:
            raise KaptureError(f"{path} -> HTTP {r.status_code}: {r.text[:200]}")
        env = r.json()
        if env.get("status") not in ("SUCCESS", "S"):
            data = env.get("data", {})
            raise KaptureError(f"{path} -> {data.get('errorCode')}: {data.get('errorMessage')}")
        return env.get("data", {})

    # ─── listing / detail / lookup (read) ───────────────────────────────────
    async def tr_listing(self, object_id: str, page=0, size=20) -> dict:
        return await self._get("/kapture/v1/tr/listing",
                               {"objectId": object_id, "page": page, "size": size})

    async def sales_order_listing(self, object_id: str, page=0, size=20) -> dict:
        return await self._get("/kapture/v1/sales-order/listing",
                               {"objectId": object_id, "page": page, "size": size})

    async def service_order_listing(self, object_id: str, page=0, size=20) -> dict:
        return await self._get("/kapture/v1/service-order/listing",
                               {"objectId": object_id, "page": page, "size": size})

    async def service_order_details(self, service_order_no: str) -> dict:
        return await self._get("/kapture/v1/service-order/details",
                               {"serviceOrderNo": service_order_no})

    async def complaint_listing(self, object_id: str, page=0, size=20) -> dict:
        return await self._get("/kapture/v1/complaint/listing",
                               {"objectId": object_id, "page": page, "size": size})

    async def contract_listing(self, object_id: str, page=0, size=20) -> dict:
        return await self._get("/kapture/v1/contract/listing",
                               {"objectId": object_id, "page": page, "size": size})

    async def service_order_request(self, service_req_no: str) -> dict:
        return await self._get("/service-order/v1/request",
                               {"serviceReqNo": service_req_no})

    async def rcp_order_listing(
        self, object_id: str | None = None, mobile_no: str | None = None, page=0, size=20
    ) -> dict:
        """The ledger read we lead with: object + customer + contracts by mobile or objectId."""
        params: dict = {"page": page, "size": size}
        if object_id:
            params["objectId"] = object_id
        elif mobile_no:
            params["mobileNo"] = mobile_no
        else:
            raise KaptureError("provide objectId or mobileNo")
        return await self._get("/rcp/v1/order/listing", params)

    # ─── create (write-back, checksum required) ─────────────────────────────
    async def b2b_complaint_create(self, body: dict, transaction_number: str) -> dict:
        return await self._post("/b2b-complaint/create", body, transaction_number)

    async def b2b_service_request_create(self, body: dict, transaction_number: str) -> dict:
        return await self._post("/b2b-service-request/create", body, transaction_number)

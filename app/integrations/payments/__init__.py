"""Payment provider factory (UPI). Mock until a real provider + test mode arrive.

No automatic refunds/payouts — a person approves every money action (spec). This
only creates a pay link and records receipt; payouts are gated in J13.
"""
from __future__ import annotations

import uuid

from app.config import settings


class MockPaymentProvider:
    async def create_link(self, amount: float, ref: str) -> str:
        token = uuid.uuid4().hex[:10]
        return f"upi://pay?pa=reliancedigital@upi&am={amount:.2f}&tn={ref}&tr={token}"


class UpiPaymentProvider:  # pragma: no cover - needs real provider creds
    async def create_link(self, amount: float, ref: str) -> str:
        raise NotImplementedError("UPI provider pending — see PENDING item #14")


def get_payments():
    if settings.use_mocks or not settings.upi_provider_url:
        return MockPaymentProvider()
    return UpiPaymentProvider()

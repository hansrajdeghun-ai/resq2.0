"""Kapture integration factory.

get_kapture() returns the mock in mock mode, else the real UAT client.
Reads are live; create APIs fall back to the mock until the checksum key arrives.
"""
from __future__ import annotations

from app.config import settings
from app.integrations.kapture.client import KaptureClient, KaptureError
from app.integrations.kapture.mock import MockKaptureClient


def get_kapture():
    if settings.use_mocks:
        return MockKaptureClient()
    return KaptureClient()


__all__ = ["get_kapture", "KaptureClient", "MockKaptureClient", "KaptureError"]

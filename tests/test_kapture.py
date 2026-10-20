"""Kapture checksum + mock client."""
from __future__ import annotations

import hashlib
import hmac

import pytest

from app.integrations.kapture import MockKaptureClient
from app.integrations.kapture.checksum import compute, for_uri, verify


def test_checksum_matches_hmac_sha256():
    key, uri = "checksum-secret", "/b2b-complaint/create"
    expected = hmac.new(key.encode(), uri.encode(), hashlib.sha256).hexdigest()
    assert for_uri(key, uri) == expected
    assert len(for_uri(key, uri)) == 64


def test_checksum_pipe_join_and_trim():
    key = "k"
    assert compute(key, " a ", None, "b") == compute(key, "a", "", "b")
    assert verify(key, compute(key, "a", "b").upper(), "a", "b")  # case-insensitive


async def test_mock_rcp_listing_shape():
    k = MockKaptureClient()
    data = await k.rcp_order_listing(mobile_no="7259678000")
    rec = data["content"][0]
    assert rec["object"]["serial_no"]
    assert rec["customer"]["bpid"]
    assert isinstance(rec["contracts"], list)


async def test_mock_create_returns_crm_ids():
    k = MockKaptureClient()
    c = await k.b2b_complaint_create({"KAPTURECOMPLTNO": "1"}, "txn-1")
    assert c["complaint_return"]["crmcomplaintid"]
    s = await k.b2b_service_request_create({"KAPTURE_SR_NO": "SR1"}, "txn-2")
    assert s["serreq_return"]["crmservicerequestid"]

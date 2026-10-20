"""Request checksum for the Kapture create APIs (API Contract section 4).

Algorithm : HMAC-SHA256
Key       : shared checksum secret (pending from middleware team)
Encoding  : lowercase hex
Header    : x-checksum
Hashed    : the request URI (relative path, no host, no query string).
            Multiple values are joined with "|" in documented order, trimmed,
            nulls treated as empty strings.
"""
from __future__ import annotations

import hashlib
import hmac


def compute(key: str, *values: str | None) -> str:
    message = "|".join((v or "").strip() for v in values)
    digest = hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest().lower()


def for_uri(key: str, request_uri: str) -> str:
    """Checksum over the relative API path, e.g. '/b2b-complaint/create'."""
    return compute(key, request_uri)


def verify(key: str, candidate: str, *values: str | None) -> bool:
    return hmac.compare_digest(candidate.lower(), compute(key, *values))

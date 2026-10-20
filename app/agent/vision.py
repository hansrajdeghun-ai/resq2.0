"""Photo reading (spec extra points): error code, serial plate, gauge.

Uses Claude vision when ANTHROPIC_API_KEY + image bytes are available; otherwise a
mock that returns a hinted value so the demo flows still work. Callers pass raw image
bytes (downloaded from the WhatsApp media id) or a hint for the mock.
"""
from __future__ import annotations

import logging

log = logging.getLogger("resq.vision")

_PROMPTS = {
    "serial": "Read the serial/IMEI number from this product label. Return only the digits.",
    "error_code": "Read the error code shown on this appliance display. Return only the code.",
    "gauge": "Read the pressure/temperature gauge value. Return only the number and unit.",
}


async def read(kind: str, *, image_bytes: bytes | None = None,
               media_type: str = "image/jpeg", hint: str | None = None) -> str | None:
    """Read `kind` (serial|error_code|gauge) from an image, or fall back to hint."""
    from app.agent import llm

    if llm.enabled() and image_bytes:
        out = await llm.vision(_PROMPTS.get(kind, _PROMPTS["serial"]),
                               image_bytes, media_type)
        if out:
            return out
    return hint  # mock / offline: the caller's known/expected value

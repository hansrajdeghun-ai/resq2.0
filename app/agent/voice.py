"""Voice notes (spec extra points): transcribe a customer's audio to text so the same
intent routing + language mirroring apply.

Uses OpenAI Whisper when an OpenAI key is set; otherwise returns the hint (mock). With
an Anthropic-only setup, transcription needs a separate STT provider (still pending).
"""
from __future__ import annotations

import io
import logging

from app.config import settings

log = logging.getLogger("resq.voice")


async def transcribe(*, audio_bytes: bytes | None = None, filename: str = "note.ogg",
                     hint: str | None = None) -> str | None:
    """Return transcript text, or the hint when no STT provider is available."""
    if audio_bytes and settings.openai_api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            buf = io.BytesIO(audio_bytes)
            buf.name = filename
            r = await client.audio.transcriptions.create(model="whisper-1", file=buf)
            return (r.text or "").strip() or hint
        except Exception as e:  # noqa: BLE001
            log.warning("transcription failed: %s", e)
    return hint

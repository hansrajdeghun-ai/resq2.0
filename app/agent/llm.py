"""Provider-agnostic LLM layer.

Claude preferred; OpenAI used when only an OpenAI key is present. Everything AI-native
(intent routing, translation, photo reading) goes through here, so hardcoded word lists
are only an offline fallback. If no key is set, callers fall back to their heuristics.
"""
from __future__ import annotations

import base64
import logging

from app.config import settings

log = logging.getLogger("resq.llm")


def enabled() -> bool:
    return settings.llm_enabled


async def chat(system: str, user: str, max_tokens: int = 256) -> str | None:
    """One-shot text completion. Returns None if no provider / on error."""
    provider = settings.llm_provider
    try:
        if provider == "anthropic":
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model=settings.anthropic_model, max_tokens=max_tokens,
                system=system, messages=[{"role": "user", "content": user}])
            return (msg.content[0].text if msg.content else "").strip() or None
        if provider == "openai":
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            r = await client.chat.completions.create(
                model=settings.openai_model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}])
            return (r.choices[0].message.content or "").strip() or None
    except Exception as e:  # noqa: BLE001
        log.warning("llm chat failed (%s): %s", provider, e)
    return None


async def vision(prompt: str, image_bytes: bytes, media_type: str = "image/jpeg") -> str | None:
    """Read text/values from an image. Returns None if no provider / on error."""
    provider = settings.llm_provider
    b64 = base64.standard_b64encode(image_bytes).decode()
    try:
        if provider == "anthropic":
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model=settings.anthropic_model, max_tokens=64,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": media_type, "data": b64}},
                    {"type": "text", "text": prompt}]}])
            return (msg.content[0].text if msg.content else "").strip() or None
        if provider == "openai":
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            r = await client.chat.completions.create(
                model=settings.openai_vision_model, max_tokens=64,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{media_type};base64,{b64}"}}]}])
            return (r.choices[0].message.content or "").strip() or None
    except Exception as e:  # noqa: BLE001
        log.warning("llm vision failed (%s): %s", provider, e)
    return None

"""Reply in the language of the customer's last message (spec 2.5).

Detection is cheap (Devanagari -> Hindi; a few romanized cues). Localisation uses
Claude when ANTHROPIC_API_KEY is set (real translation, cached), else a focused
glossary fallback so the core journeys still show Hindi in the demo without a key.
Only customer-facing text is localised; staff (owner/field/area) stays in English.
"""
from __future__ import annotations

import re

from app.config import settings

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# romanized-Hindi word cues, matched on word boundaries (not substrings) so English
# like "chain" or "hair" never trips them.
_HI_WORDS = {"nahi", "karo", "karna", "chahiye", "theek", "thik", "kaam", "lagao",
             "kharab", "dikkat", "chalu", "band", "jaldi", "mera", "meri", "hai"}

# longest-first glossary for the fallback (no API key). Phrases before words.
GLOSSARY_HI: list[tuple[str, str]] = [
    ("Choose an installation slot", "इंस्टॉलेशन स्लॉट चुनें"),
    ("Your machine is ready to install", "आपकी मशीन इंस्टॉल के लिए तैयार है"),
    ("We will tell you who is coming", "हम आपको बताएँगे कौन आ रहा है"),
    ("from Reliance Digital", "रिलायंस डिजिटल से"),
    ("will install your", "आपका इंस्टॉल करेगा"),
    ("is on the way", "रास्ते में है"),
    ("About 20 minutes", "लगभग 20 मिनट"),
    ("Is your", "क्या आपका"),
    ("working well", "ठीक से चल रहा है"),
    ("Warranty has started", "वारंटी शुरू हो गई है"),
    ("is in your Reliance record", "आपके रिलायंस रिकॉर्ड में है"),
    ("Please try this first", "पहले यह आज़माएँ"),
    ("The repair is free", "मरम्मत मुफ़्त है"),
    ("In warranty", "वारंटी में"),
    ("Choose a slot", "स्लॉट चुनें"),
    ("Approve", "स्वीकृत करें"),
    ("Booked for", "बुक किया गया"),
    ("installation", "इंस्टॉलेशन"),
    ("Thank you", "धन्यवाद"),
    ("Yes", "हाँ"),
]

_cache: dict[tuple[str, str], str] = {}


def detect_language(text: str | None) -> str | None:
    """hi for Devanagari or romanized-Hindi words; en for other Latin text; None for
    empty input (a button tap) so the previous language is kept."""
    if not text or not text.strip():
        return None
    if _DEVANAGARI.search(text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & _HI_WORDS:
        return "hi"
    return "en"  # Latin, no Hindi cues -> English (resets a stuck 'hi')


def _glossary(text: str, lang: str) -> str:
    if lang != "hi":
        return text
    out = text
    for en, hi in GLOSSARY_HI:
        out = out.replace(en, hi)
    return out


async def localize(text: str, lang: str | None) -> str:
    """Translate a customer-facing message to `lang`. Uses the LLM when a key is set
    (any language); falls back to the offline glossary otherwise."""
    if not lang or lang == "en":
        return text
    key = (text, lang)
    if key in _cache:
        return _cache[key]
    from app.agent import llm

    out = None
    if llm.enabled():
        out = await llm.chat(
            system=(f"Translate the WhatsApp service message to language code '{lang}'. "
                    "Keep it short and natural, keep IDs/numbers/₹/button-like words as-is. "
                    "Return only the translation, no quotes."),
            user=text, max_tokens=200)
    if not out:
        out = _glossary(text, lang)
    _cache[key] = out
    return out

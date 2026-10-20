"""AI-native polish: language mirroring, action register, photo-read hook."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent import vision
from app.agent.language import detect_language, localize
from app.channels.simulator import Simulator
from app.domain import Role
from app.models.ledger import Job
from app.models.ops import ActionRegister
from scripts.seed import seed_demo


def test_detect_hindi():
    assert detect_language("मेरा AC ठीक करो") == "hi"       # Devanagari
    assert detect_language("AC kharab hai theek karo") == "hi"  # romanized
    assert detect_language("install my ac") == "en"        # Latin -> resets to en
    assert detect_language(None) is None                   # button tap keeps language


async def test_localize_glossary_without_key():
    out = await localize("Choose an installation slot", "hi")
    assert "स्लॉट" in out  # glossary applied, no API key needed


async def test_reply_mirrors_customer_language(session):
    await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    out = await sim.send(Role.CUSTOMER, "cust-sharma",
                         text="install my AC", language="hi")
    # the customer-facing reply should contain Devanagari (localised)
    assert any(any("ऀ" <= ch <= "ॿ" for ch in m.text)
               for m in out if m.role == Role.CUSTOMER)


async def test_action_register_records_suggestion(session):
    ids = await seed_demo(session)
    await session.commit()
    sim = Simulator(session)
    await sim.send(Role.CUSTOMER, "cust-sharma", button_id="slot:Sun 10-12")
    job = (await session.scalars(select(Job))).first()
    await sim.send(Role.OWNER, ids["partner"], button_id=f"job_accept:{job.id}")
    items = (await session.scalars(select(ActionRegister))).all()
    assert any("Assign" in i.suggestion and i.decision == "pending" for i in items)


async def test_vision_mock_returns_hint():
    assert await vision.read("serial", hint="SN-AC-4471") == "SN-AC-4471"
    assert await vision.read("error_code", hint="E21") == "E21"

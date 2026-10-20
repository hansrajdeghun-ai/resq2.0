"""Shared test fixtures: an in-memory SQLite engine with the full schema."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base


@pytest.fixture(autouse=True)
def _offline_llm():
    """Tests run deterministically offline — no real LLM calls even if .env has a key."""
    a, o = settings.anthropic_api_key, settings.openai_api_key
    settings.anthropic_api_key = ""
    settings.openai_api_key = ""
    yield
    settings.anthropic_api_key, settings.openai_api_key = a, o


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    import app.models  # noqa: F401  register tables

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()

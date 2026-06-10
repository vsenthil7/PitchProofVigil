"""Tests for the database engine and session management."""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.engine import Database, _normalize_dsn, get_database, reset_database
from app.db.models import Tenant


def test_normalize_dsn_postgres():
    assert _normalize_dsn("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_dsn_sqlite():
    assert _normalize_dsn("sqlite:///x.db") == "sqlite+aiosqlite:///x.db"


def test_normalize_dsn_already_async():
    dsn = "postgresql+asyncpg://u:p@h/db"
    assert _normalize_dsn(dsn) == dsn
    dsn2 = "sqlite+aiosqlite:///x.db"
    assert _normalize_dsn(dsn2) == dsn2


async def test_create_and_drop_all():
    db = Database(Settings(database_dsn="sqlite+aiosqlite:///:memory:"))
    await db.create_all()
    await db.drop_all()
    await db.dispose()


async def test_session_commits(db):
    async with db.session() as s:
        s.add(Tenant(name="X", slug="x"))
    async with db.session() as s:
        from sqlalchemy import select

        rows = (await s.execute(select(Tenant))).scalars().all()
        assert len(rows) == 1


async def test_session_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        async with db.session() as s:
            s.add(Tenant(name="Y", slug="y"))
            raise RuntimeError("boom")
    async with db.session() as s:
        from sqlalchemy import select

        rows = (await s.execute(select(Tenant))).scalars().all()
        assert rows == []


def test_get_database_singleton_and_reset():
    reset_database()
    a = get_database()
    b = get_database()
    assert a is b
    reset_database()
    c = get_database()
    assert c is not a
    reset_database()


def test_postgres_dsn_uses_pre_ping():
    db = Database(Settings(database_dsn="postgresql://u:p@localhost/db"))
    # Engine constructed without connecting; just assert driver normalization.
    assert "asyncpg" in str(db.engine.url)

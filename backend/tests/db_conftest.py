"""Fixtures for database-backed tests."""
from __future__ import annotations

import pytest_asyncio

from app.core.config import Settings
from app.db.engine import Database
from app.repositories.registry import TenantRepository


@pytest_asyncio.fixture
async def db():
    """A fresh in-memory database with the full schema, per test."""
    database = Database(Settings(database_dsn="sqlite+aiosqlite:///:memory:"))
    await database.create_all()
    try:
        yield database
    finally:
        await database.dispose()


@pytest_asyncio.fixture
async def tenant_id(db):
    """Create a tenant and return its id."""
    async with db.session() as s:
        tenant = await TenantRepository(s).create("Test Tenant", "test-tenant")
        return tenant.id

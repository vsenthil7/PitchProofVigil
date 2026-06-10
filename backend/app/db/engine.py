"""Async database engine and session management.

Supports Postgres (asyncpg) in production and SQLite (aiosqlite) for local dev
and tests. The DSN is resolved from settings; if it points at Postgres we use
the asyncpg driver, otherwise an in-process SQLite file/memory database. A
single ``Database`` object owns the engine and sessionmaker so the rest of the
app depends on one injectable handle.
"""
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from app.core.config import Settings, get_settings


def _normalize_dsn(dsn: str) -> str:
    """Ensure the DSN uses an async driver."""
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    if dsn.startswith("sqlite://") and "+aiosqlite" not in dsn:
        return dsn.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return dsn


class Database:
    """Owns the async engine and session factory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.dsn = _normalize_dsn(self.settings.database_dsn)
        connect_args: dict = {}
        engine_kwargs: dict = {}
        if self.dsn.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            # In-memory SQLite is per-connection; share one connection across
            # the pool so data persists across sessions/requests in dev & tests.
            if ":memory:" in self.dsn:
                from sqlalchemy.pool import StaticPool

                engine_kwargs["poolclass"] = StaticPool
        self.engine: AsyncEngine = create_async_engine(
            self.dsn,
            echo=self.settings.db_echo,
            future=True,
            connect_args=connect_args,
            pool_pre_ping=not self.dsn.startswith("sqlite"),
            **engine_kwargs,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_all(self) -> None:
        """Create tables directly (used in tests; prod uses Alembic)."""
        # Import models so they are registered on SQLModel.metadata.
        from app.db import models as _models  # noqa: F401

        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def drop_all(self) -> None:
        from app.db import models as _models  # noqa: F401

        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a transactional session scope."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()


_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        _database = Database()
    return _database


def reset_database() -> None:
    """Test helper to force a fresh Database on next access."""
    global _database
    _database = None

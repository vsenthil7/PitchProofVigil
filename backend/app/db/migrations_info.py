"""Resolve the Alembic head revision shipped with this image.

Used by the readiness probe to detect schema drift (DB not migrated to head).
Reads the migration scripts via Alembic's own ScriptDirectory so it stays
correct as revisions are added, with a defensive fallback if config can't be
located at runtime.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def head_revision() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        # backend/alembic.ini relative to this file (app/db/migrations_info.py).
        backend_root = Path(__file__).resolve().parents[2]
        cfg = Config(str(backend_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_root / "migrations"))
        script = ScriptDirectory.from_config(cfg)
        return script.get_current_head()
    except Exception:
        return None

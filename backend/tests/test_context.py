"""Tests for app.core.context."""
from __future__ import annotations

from app.core.config import Settings
from app.core.context import AppContext, get_context, reset_context


def test_context_wires_shared_store():
    ctx = AppContext(Settings(use_mocks=True))
    assert ctx.tracer.store is ctx.store
    assert ctx.mcp.store is ctx.store


def test_mode_report():
    ctx = AppContext(Settings(use_mocks=True))
    report = ctx.mode_report()
    assert report == {"gemini": "mock", "phoenix": "mock", "arize_ax": "mock"}


def test_get_context_singleton_and_reset():
    reset_context()
    a = get_context()
    b = get_context()
    assert a is b
    reset_context()
    c = get_context()
    assert c is not a
    reset_context()

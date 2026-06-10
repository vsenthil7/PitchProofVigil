"""Tests for the tool framework and concrete concierge tools."""
from __future__ import annotations

import pytest

from app.orchestration.concierge_tools import (
    FixtureLookupTool,
    GateLookupTool,
    KickoffTool,
    TicketingTool,
    TranslationTool,
)
from app.orchestration.tools import Tool, ToolParam, ToolRegistry, ToolResult


class _EchoTool(Tool):
    name = "echo"
    description = "echoes"
    params = (ToolParam("value", "string", "what to echo"),)

    def _execute(self, value: str) -> ToolResult:
        return ToolResult.success(self.name, echoed=value)


class _BoomTool(Tool):
    name = "boom"
    description = "raises"
    params = ()

    def _execute(self) -> ToolResult:
        raise RuntimeError("kaboom")


def test_tool_invoke_success():
    out = _EchoTool().invoke(value="hi")
    assert out.ok and out.data["echoed"] == "hi"
    assert out.tool == "echo"
    assert out.latency_ms >= 0.0


def test_tool_missing_required_param():
    out = _EchoTool().invoke()
    assert not out.ok
    assert "Missing required" in out.error


def test_tool_exception_becomes_failure():
    out = _BoomTool().invoke()
    assert not out.ok
    assert "kaboom" in out.error


def test_tool_schema():
    schema = _EchoTool().schema()
    assert schema["name"] == "echo"
    assert "value" in schema["parameters"]["properties"]
    assert schema["parameters"]["required"] == ["value"]


def test_result_factories():
    s = ToolResult.success("t", a=1)
    f = ToolResult.failure("t", "bad")
    assert s.ok and s.data == {"a": 1}
    assert not f.ok and f.error == "bad"


def test_registry():
    reg = ToolRegistry()
    t = _EchoTool()
    reg.register(t)
    assert len(reg) == 1
    assert "echo" in reg
    assert reg.get("echo") is t
    assert t in reg.all()
    assert reg.schemas()[0]["name"] == "echo"


def test_registry_duplicate():
    reg = ToolRegistry()
    reg.register(_EchoTool())
    with pytest.raises(ValueError):
        reg.register(_EchoTool())


def test_registry_unknown():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


# ---- Concrete tools ----

def test_fixture_lookup():
    ok = FixtureLookupTool().invoke(team_a="Spain", team_b="Germany")
    assert ok.ok and "fixture" in ok.data
    miss = FixtureLookupTool().invoke(team_a="Narnia")
    assert not miss.ok


def test_kickoff_tool():
    ok = KickoffTool().invoke(team_a="Spain")
    assert ok.ok and ok.data["kickoff_local"] == "2026-06-18T20:00:00"
    miss = KickoffTool().invoke(team_a="Narnia")
    assert not miss.ok


def test_gate_tool():
    ok = GateLookupTool().invoke(team_a="Brazil", section="114")
    assert ok.ok and ok.data["gate"]
    miss = GateLookupTool().invoke(team_a="Narnia", section="1")
    assert not miss.ok


def test_translation_tool():
    ok = TranslationTool().invoke(phrase_key="where_is_my_gate", language="es")
    assert ok.ok and ok.data["phrase"] == "Tu puerta es"
    # Unknown language falls back to English.
    fb = TranslationTool().invoke(phrase_key="where_is_my_gate", language="zz")
    assert fb.ok and fb.data["phrase"] == "Your gate is"
    miss = TranslationTool().invoke(phrase_key="nope", language="es")
    assert not miss.ok


def test_ticketing_tool():
    ok = TicketingTool().invoke()
    assert ok.ok and "FIFA" in ok.data["guidance"]


# ---- P6.M5: GroundedSearchTool ----

def test_grounded_search_mock_mode_returns_results():
    from app.core.config import Settings
    from app.orchestration.grounded_search_tool import GroundedSearchTool

    tool = GroundedSearchTool(settings=Settings(use_mocks=True))
    result = tool.invoke(query="When does Spain play?")
    assert result.ok is True
    assert result.data["source"] == "mock"
    assert len(result.data["results"]) > 0


def test_grounded_search_mock_generic_query_returns_default_subset():
    """A query matching no team/keyword falls back to the first 2 fixtures."""
    from app.core.config import Settings
    from app.orchestration.grounded_search_tool import GroundedSearchTool

    tool = GroundedSearchTool(settings=Settings(use_mocks=True))
    result = tool.invoke(query="zzz nothing matches")
    assert result.ok is True
    assert len(result.data["results"]) == 2


def test_grounded_search_real_mode_no_app_id_falls_back_to_mock():
    from app.core.config import Settings
    from app.orchestration.grounded_search_tool import GroundedSearchTool

    s = Settings(use_mocks=False, jwt_secret="a" * 64)
    # No AGENT_BUILDER_APP_ID -> mock path even in real mode.
    tool = GroundedSearchTool(settings=s)
    result = tool.invoke(query="stadium info")
    assert result.ok is True
    assert result.data["source"] == "mock"


def test_grounded_search_keyword_query_matches_venue():
    from app.core.config import Settings
    from app.orchestration.grounded_search_tool import GroundedSearchTool

    tool = GroundedSearchTool(settings=Settings(use_mocks=True))
    result = tool.invoke(query="which stadium and gate")
    assert result.ok is True
    assert len(result.data["results"]) >= 1


def test_grounded_search_registered_and_general_intent_served():
    """build_tool_registry includes grounded_search; GENERAL maps to it."""
    from app.core.models import IntentType
    from app.orchestration.orchestrator import _INTENT_PLAN, build_tool_registry

    reg = build_tool_registry()
    assert reg.get("grounded_search") is not None
    assert _INTENT_PLAN[IntentType.GENERAL] == ["grounded_search"]


def test_grounded_search_real_dispatch_calls_real_search(monkeypatch):
    """With app_id set and use_mocks=False, _execute dispatches to _real_search."""
    from app.core.config import Settings
    from app.orchestration.grounded_search_tool import GroundedSearchTool
    from app.orchestration.tools import ToolResult

    s = Settings(
        use_mocks=False, jwt_secret="a" * 64,
        google_cloud_project="p", agent_builder_app_id="app-123",
    )
    tool = GroundedSearchTool(settings=s)
    called = {}

    def fake_real(query):
        called["q"] = query
        return ToolResult.success(tool.name, results=[{"venue": "X"}],
                                  source="vertex_ai_search", query=query)

    monkeypatch.setattr(tool, "_real_search", fake_real)
    result = tool.invoke(query="where is the final")
    assert called["q"] == "where is the final"
    assert result.data["source"] == "vertex_ai_search"

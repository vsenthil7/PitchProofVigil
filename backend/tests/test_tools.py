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

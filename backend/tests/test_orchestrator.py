"""Tests for the concierge orchestrator."""
from __future__ import annotations

from app.core.config import Settings
from app.core.models import ConciergeRequest, IntentType, Language
from app.orchestration.orchestrator import (
    ConciergeOrchestrator,
    build_tool_registry,
)
from app.orchestration.resilience import CircuitBreaker, RetryPolicy
from app.orchestration.tools import ToolResult


def _orch():
    return ConciergeOrchestrator(Settings(use_mocks=True))


def test_build_tool_registry():
    reg = build_tool_registry()
    assert len(reg) == 6


def test_kickoff_uses_authoritative_time():
    r = _orch().run(ConciergeRequest(text="When does Spain play Germany?"))
    assert r.response.detected_intent == IntentType.KICKOFF_TIME
    assert "20:00" in r.response.text
    assert r.response.grounded_facts["kickoff_local"] == "2026-06-18T20:00:00"
    assert r.tool_calls[0].ok
    assert r.plan == ["kickoff_time"]


def test_gate_info():
    r = _orch().run(ConciergeRequest(text="What gate for Brazil section 114?"))
    assert r.response.detected_intent == IntentType.GATE_INFO
    assert "Gate" in r.response.text


def test_ticketing():
    r = _orch().run(ConciergeRequest(text="I want to buy a ticket"))
    assert r.response.detected_intent == IntentType.TICKETING
    assert "FIFA" in r.response.text


def test_travel():
    r = _orch().run(ConciergeRequest(text="hotel near France England match"))
    assert r.response.detected_intent == IntentType.TRAVEL
    assert "transit" in r.response.text


def test_general_now_served_by_grounded_search():
    """GENERAL intent now routes to grounded_search (P6.M5), not an empty plan."""
    r = _orch().run(ConciergeRequest(text="hello there"))
    assert r.response.detected_intent == IntentType.GENERAL
    assert r.plan == ["grounded_search"]
    # The reply is now composed from grounded search results, not the fallback.
    assert "tournament data" in r.response.text.lower()
    assert r.response.grounded_facts.get("source") == "mock"


def test_cost_recorded():
    r = _orch().run(ConciergeRequest(text="I want to buy a ticket"))
    assert r.cost["calls"] == 1
    assert r.cost["input_tokens"] > 0


def test_section_extraction_default():
    orch = _orch()
    assert orch._section_from_text("which gate") == "114"
    assert orch._section_from_text("gate for section 220") == "220"


def test_tool_failure_degrades_gracefully():
    # A kickoff query with no known team → tool fails → graceful non-answer.
    r = _orch().run(ConciergeRequest(text="When does kickoff start?"))
    assert r.response.detected_intent == IntentType.KICKOFF_TIME
    # No team matched, so no kwargs and the tool fails; compose degrades.
    assert "don't have" in r.response.text.lower()


def test_invoke_handles_breaker_open():
    # Pre-trip the breaker so _invoke hits the exception path.
    breaker = CircuitBreaker(failure_threshold=1)
    for _ in range(1):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        except RuntimeError:
            pass
    orch = ConciergeOrchestrator(
        Settings(use_mocks=True),
        retry=RetryPolicy(max_attempts=1, sleep=lambda s: None),
        breaker=breaker,
    )
    result = orch._invoke("ticketing_info")
    assert not result.ok
    assert "Circuit is open" in result.error


def test_compose_no_successful_tools():
    orch = _orch()
    text, grounded = orch._compose(
        IntentType.KICKOFF_TIME, [ToolResult.failure("kickoff_time", "x")], "en"
    )
    assert "don't have" in text.lower()
    assert grounded == {}


def test_compose_general_intent():
    orch = _orch()
    text, _ = orch._compose(
        IntentType.GENERAL, [ToolResult.success("x", foo="bar")], "en"
    )
    assert "don't have" in text.lower()


def test_stadium_nav_uses_fixture():
    r = _orch().run(ConciergeRequest(text="find my section at the Spain match"))
    assert r.response.detected_intent == IntentType.STADIUM_NAV
    assert "transit" in r.response.text


def test_real_mode_model_label(monkeypatch):
    orch = ConciergeOrchestrator(Settings(use_mocks=False, jwt_secret="a"*64, google_cloud_project="p"))
    assert orch.mode == "real"
    r = orch.run(ConciergeRequest(text="I want to buy a ticket"))
    assert r.response.model == "gemini-2.0-flash"


def test_general_grounded_result_without_venue(monkeypatch):
    """A grounded_search result lacking 'venue' uses the generic reply branch."""
    from app.orchestration.tools import ToolResult

    o = _orch()
    grounded_tool = o.registry.get("grounded_search")

    def fake_execute(query):
        return ToolResult.success(
            "grounded_search", results=[{"note": "no venue here"}], source="mock",
            query=query,
        )

    monkeypatch.setattr(grounded_tool, "_execute", fake_execute)
    r = o.run(ConciergeRequest(text="something general"))
    assert r.response.detected_intent == IntentType.GENERAL
    assert "most relevant tournament information" in r.response.text.lower()

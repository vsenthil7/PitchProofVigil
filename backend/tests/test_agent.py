"""Tests for app.agent — concierge, fixtures, intent detection, real path."""
from __future__ import annotations

import sys
import types

import pytest

from app.agent import fixtures
from app.agent.concierge import (
    ConciergeAgent,
    _GeminiConcierge,
    _MockConcierge,
    detect_intent,
)
from app.core.config import Settings
from app.core.models import ConciergeRequest, IntentType, Language


@pytest.mark.parametrize(
    "text,expected",
    [
        ("When does Spain play?", IntentType.KICKOFF_TIME),
        ("what time is kickoff", IntentType.KICKOFF_TIME),
        ("which gate do I use", IntentType.GATE_INFO),
        ("I want to buy a ticket", IntentType.TICKETING),
        ("need a hotel near the stadium", IntentType.TRAVEL),
        ("where is the nearest bathroom", IntentType.STADIUM_NAV),
        ("translate this in spanish", IntentType.TRANSLATION),
        ("hello there", IntentType.GENERAL),
    ],
)
def test_detect_intent(text, expected):
    assert detect_intent(text) == expected


def test_find_match_single_and_pair():
    assert fixtures.find_match("Spain") is not None
    assert fixtures.find_match("Spain", "Germany") is not None
    assert fixtures.find_match("Spain", "Brazil") is None
    assert fixtures.find_match("Nowhere") is None


def test_mock_kickoff_correct_for_non_poison():
    agent = _MockConcierge()
    resp = agent.answer(ConciergeRequest(text="When does France play England?"))
    assert resp.detected_intent == IntentType.KICKOFF_TIME
    assert resp.grounded_facts["kickoff_local"] == "2026-06-24T21:00:00"


def test_mock_kickoff_poison_is_wrong():
    agent = _MockConcierge()
    resp = agent.answer(ConciergeRequest(text="When does Spain play Germany?"))
    # poisoned: stated kickoff deviates from authoritative 20:00
    assert resp.grounded_facts["kickoff_local"] == "2026-06-18T18:00:00"


def test_mock_gate_ticketing_travel_general():
    agent = _MockConcierge()
    assert "gate" in agent.answer(
        ConciergeRequest(text="what gate for Brazil section 114")
    ).text.lower()
    assert "ticket" in agent.answer(
        ConciergeRequest(text="buy a ticket")
    ).text.lower()
    assert "transit" in agent.answer(
        ConciergeRequest(text="hotel and travel for Spain")
    ).text.lower()
    assert "don't have" in agent.answer(
        ConciergeRequest(text="hello")
    ).text.lower()


def test_agent_facade_mock_mode_sets_latency():
    agent = ConciergeAgent(Settings(use_mocks=True))
    assert agent.mode == "mock"
    resp = agent.answer(ConciergeRequest(text="buy a ticket"))
    assert resp.latency_ms >= 0.0


def test_gemini_concierge_real_path(monkeypatch):
    """Exercise the real Gemini path with a fake google.genai module."""
    fake_genai = types.ModuleType("genai")

    class FakeResult:
        text = "Kickoff is at 20:00 local time at MetLife Stadium."

    class FakeModels:
        def generate_content(self, model, contents):
            return FakeResult()

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    fake_genai.Client = FakeClient
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(use_mocks=False, jwt_secret="a"*64, google_cloud_project="p")
    agent = ConciergeAgent(settings)
    assert agent.mode == "real"
    assert isinstance(agent._impl, _GeminiConcierge)
    resp = agent.answer(
        ConciergeRequest(text="When does Spain play Germany?", language=Language.ES)
    )
    assert "MetLife" in resp.text
    assert resp.model == settings.gemini_model


def test_gemini_build_prompt_no_match(monkeypatch):
    fake_genai = types.ModuleType("genai")

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = types.SimpleNamespace(
                generate_content=lambda model, contents: types.SimpleNamespace(
                    text="ok"
                )
            )

    fake_genai.Client = FakeClient
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(use_mocks=False, jwt_secret="a"*64, google_cloud_project="p")
    impl = _GeminiConcierge(settings)
    prompt = impl._build_prompt(ConciergeRequest(text="hello"), None)
    assert "No fixture matched" in prompt

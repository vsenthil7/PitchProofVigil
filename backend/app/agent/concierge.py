"""The World Cup concierge agent.

Exposes a single ``ConciergeAgent`` with a uniform ``answer()`` method. Under
the hood it dispatches to a real Gemini-backed implementation when credentials
are present, or a deterministic mock that produces realistic (and
occasionally, controllably, *wrong*) answers so the eval engine has something
to catch.
"""
from __future__ import annotations

import re
import time

from app.agent import fixtures
from app.core.config import Settings, get_settings
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    IntentType,
    Language,
)

_TEAM_PATTERN = re.compile(
    r"\b(spain|germany|brazil|argentina|france|england)\b", re.IGNORECASE
)


def detect_intent(text: str) -> IntentType:
    low = text.lower()
    if any(k in low for k in ("kickoff", "what time", "when does", "when do", "start")):
        return IntentType.KICKOFF_TIME
    if any(k in low for k in ("gate", "entrance", "where do i enter")):
        return IntentType.GATE_INFO
    if any(k in low for k in ("ticket", "buy", "seat", "resale")):
        return IntentType.TICKETING
    if any(k in low for k in ("hotel", "flight", "train", "travel", "metro")):
        return IntentType.TRAVEL
    if any(k in low for k in ("bathroom", "concession", "section", "find my")):
        return IntentType.STADIUM_NAV
    if any(k in low for k in ("translate", "in spanish", "in french")):
        return IntentType.TRANSLATION
    return IntentType.GENERAL


class _MockConcierge:
    """Deterministic concierge used when Gemini credentials are absent.

    Crucially this can emit a *wrong* answer for a known "poisoned" input so
    that the eval engine and regression gate have a real defect to detect in
    demos. This mirrors the kind of silent degradation the product exists to
    catch.
    """

    POISON_TRIGGER = "germany"  # demo: kickoff time regression on this query

    def answer(self, req: ConciergeRequest) -> ConciergeResponse:
        intent = detect_intent(req.text)
        teams = _TEAM_PATTERN.findall(req.text)
        match = fixtures.find_match(*teams[:2]) if teams else None

        grounded: dict = {}
        text = "I'm sorry, I don't have that information yet."

        if intent == IntentType.KICKOFF_TIME and match:
            grounded = {"fixture": match, "kickoff_local": match["kickoff_local"]}
            kickoff = match["kickoff_local"]
            # Inject a deliberate regression for the poisoned trigger.
            if self.POISON_TRIGGER in req.text.lower():
                kickoff = "2026-06-18T18:00:00"  # WRONG by two hours
                grounded["kickoff_local"] = kickoff
            text = f"Kickoff is at {kickoff.split('T')[1][:5]} local time at {match['venue']}."
        elif intent == IntentType.GATE_INFO and match:
            grounded = {"fixture": match, "gate": match["gate_for_section_114"]}
            text = f"Your gate is {match['gate_for_section_114']} for section 114."
        elif intent == IntentType.TICKETING:
            text = "You can manage tickets in the official FIFA app under My Tickets."
        elif intent == IntentType.TRAVEL and match:
            text = f"For {match['venue']} in {match['city']}, public transit is recommended on matchday."
            grounded = {"fixture": match}

        return ConciergeResponse(
            request_id=req.request_id,
            text=text,
            detected_intent=intent,
            language=req.language,
            grounded_facts=grounded,
            model="mock-concierge",
        )


class _GeminiConcierge:
    """Real concierge backed by Google Gemini.

    Imports the Google SDK lazily so the package is only needed when actually
    running against real credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        from google import genai  # lazy import

        self._client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location="us-central1",
        )

    def _build_prompt(self, req: ConciergeRequest, match: dict | None) -> str:
        ground = (
            f"Authoritative fixture data: {match}." if match else "No fixture matched."
        )
        return (
            "You are the official 2026 World Cup fan concierge. Answer ONLY from "
            "the authoritative data provided. If unknown, say so. "
            f"Respond in language code '{req.language.value}'.\n"
            f"{ground}\nFan question: {req.text}"
        )

    def answer(self, req: ConciergeRequest) -> ConciergeResponse:
        intent = detect_intent(req.text)
        teams = _TEAM_PATTERN.findall(req.text)
        match = fixtures.find_match(*teams[:2]) if teams else None
        prompt = self._build_prompt(req, match)

        result = self._client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
        )
        return ConciergeResponse(
            request_id=req.request_id,
            text=result.text,
            detected_intent=intent,
            language=req.language,
            grounded_facts={"fixture": match} if match else {},
            model=self.settings.gemini_model,
        )


class ConciergeAgent:
    """Public agent facade. Chooses real or mock implementation at init."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("gemini")
        if self.mode == "real":
            self._impl: _MockConcierge | _GeminiConcierge = _GeminiConcierge(
                self.settings
            )
        else:
            self._impl = _MockConcierge()

    def answer(self, req: ConciergeRequest) -> ConciergeResponse:
        start = time.perf_counter()
        resp = self._impl.answer(req)
        resp.latency_ms = (time.perf_counter() - start) * 1000.0
        return resp

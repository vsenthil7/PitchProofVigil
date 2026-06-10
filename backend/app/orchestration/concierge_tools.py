"""Concrete tools for the World Cup concierge.

These wrap the authoritative fixture data and translation tables as invokable
tools. In a production deployment the FixtureLookupTool would call a retriever
or Agent Builder grounding; here it reads the in-memory fixtures so behaviour
is deterministic and testable.
"""
from __future__ import annotations

from app.agent import fixtures
from app.orchestration.tools import Tool, ToolParam, ToolResult


class FixtureLookupTool(Tool):
    name = "fixture_lookup"
    description = "Look up an authoritative World Cup fixture by team name(s)."
    params = (
        ToolParam("team_a", "string", "First team name."),
        ToolParam("team_b", "string", "Optional second team.", required=False),
    )

    def _execute(self, team_a: str, team_b: str | None = None) -> ToolResult:
        match = fixtures.find_match(team_a, team_b)
        if match is None:
            return ToolResult.failure(self.name, f"No fixture for {team_a}/{team_b}.")
        return ToolResult.success(self.name, fixture=match)


class KickoffTool(Tool):
    name = "kickoff_time"
    description = "Return the authoritative kickoff time for a fixture."
    params = (
        ToolParam("team_a", "string", "First team name."),
        ToolParam("team_b", "string", "Optional second team.", required=False),
    )

    def _execute(self, team_a: str, team_b: str | None = None) -> ToolResult:
        match = fixtures.find_match(team_a, team_b)
        if match is None:
            return ToolResult.failure(self.name, "No fixture matched.")
        return ToolResult.success(
            self.name,
            kickoff_local=match["kickoff_local"],
            venue=match["venue"],
            fixture=match,
        )


class GateLookupTool(Tool):
    name = "gate_lookup"
    description = "Return the entry gate for a section at a fixture's venue."
    params = (
        ToolParam("team_a", "string", "A team in the fixture."),
        ToolParam("section", "string", "Seating section, e.g. '114'."),
    )

    def _execute(self, team_a: str, section: str) -> ToolResult:
        match = fixtures.find_match(team_a)
        if match is None:
            return ToolResult.failure(self.name, "No fixture matched.")
        return ToolResult.success(
            self.name,
            gate=match["gate_for_section_114"],
            section=section,
            venue=match["venue"],
            fixture=match,
        )


class TranslationTool(Tool):
    name = "translate_phrase"
    description = "Return a localized phrase for a canonical key and language."
    params = (
        ToolParam("phrase_key", "string", "Canonical phrase key."),
        ToolParam("language", "string", "Target language code (es, fr, ...)."),
    )

    def _execute(self, phrase_key: str, language: str) -> ToolResult:
        table = fixtures.TRANSLATIONS.get(phrase_key)
        if table is None:
            return ToolResult.failure(self.name, f"Unknown phrase key: {phrase_key}.")
        phrase = table.get(language, table.get("en"))
        return ToolResult.success(self.name, phrase=phrase, language=language)


class TicketingTool(Tool):
    name = "ticketing_info"
    description = "Return guidance for managing match tickets."
    params = ()

    def _execute(self) -> ToolResult:
        return ToolResult.success(
            self.name,
            guidance="Manage tickets in the official FIFA app under My Tickets.",
        )

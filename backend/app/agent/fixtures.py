"""Grounding data for the World Cup concierge.

In production this would be retrieved from a tournament data store (via Agent
Builder grounding or a retriever tool). For the hackathon it is a small,
authoritative in-memory fixture so both the real and mock agent paths have a
consistent ground truth to be evaluated against.
"""
from __future__ import annotations

# Authoritative facts. The eval engine treats these as ground truth, so a
# response that contradicts them is a factual regression.
FIXTURES: dict[str, dict] = {
    "ESP-GER-2026-06-18": {
        "home": "Spain",
        "away": "Germany",
        "kickoff_local": "2026-06-18T20:00:00",
        "venue": "MetLife Stadium",
        "city": "East Rutherford, NJ",
        "gate_for_section_114": "Gate C",
    },
    "BRA-ARG-2026-06-21": {
        "home": "Brazil",
        "away": "Argentina",
        "kickoff_local": "2026-06-21T17:00:00",
        "venue": "AT&T Stadium",
        "city": "Arlington, TX",
        "gate_for_section_114": "Gate 5",
    },
    "FRA-ENG-2026-06-24": {
        "home": "France",
        "away": "England",
        "kickoff_local": "2026-06-24T21:00:00",
        "venue": "SoFi Stadium",
        "city": "Inglewood, CA",
        "gate_for_section_114": "Gate B",
    },
}

# Canonical translations the translation evaluator checks against.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "where_is_my_gate": {
        "en": "Your gate is",
        "es": "Tu puerta es",
        "fr": "Votre porte est",
        "de": "Ihr Tor ist",
        "pt": "O seu portão é",
    },
    "kickoff_is_at": {
        "en": "Kickoff is at",
        "es": "El saque inicial es a las",
        "fr": "Le coup d'envoi est à",
        "de": "Anstoß ist um",
        "pt": "O pontapé inicial é às",
    },
}


def find_match(team_a: str, team_b: str | None = None) -> dict | None:
    """Return the fixture involving the given team(s), if any."""
    team_a = team_a.strip().lower()
    for fixture in FIXTURES.values():
        teams = {fixture["home"].lower(), fixture["away"].lower()}
        if team_a in teams and (team_b is None or team_b.strip().lower() in teams):
            return fixture
    return None

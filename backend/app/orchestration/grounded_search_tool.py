"""Grounded search tool using Vertex AI Agent Builder (Discovery Engine).

In real mode (USE_MOCKS=false and AGENT_BUILDER_APP_ID set) this queries a
Vertex AI Search serving config for live tournament data. In mock mode (or if
the real call fails) it returns results from the in-memory fixtures, so the
agent degrades gracefully and the dev loop needs no GCP project.

The ``google-cloud-discoveryengine`` SDK is a live-only optional dependency,
imported lazily inside the real path.
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.orchestration.tools import Tool, ToolParam, ToolResult


class GroundedSearchTool(Tool):
    """Search live tournament data via Vertex AI Agent Builder grounding."""

    name = "grounded_search"
    description = (
        "Search for live World Cup tournament data using Vertex AI Agent "
        "Builder grounding. Use for general questions about venues, schedules, "
        "and facilities."
    )
    params = (
        ToolParam("query", "string", "Natural-language search query about World Cup."),
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _execute(self, query: str) -> ToolResult:
        if self.settings.agent_builder_app_id and not self.settings.use_mocks:
            return self._real_search(query)
        return self._mock_search(query)

    def _real_search(self, query: str) -> ToolResult:
        try:  # pragma: no cover - requires live Vertex AI + optional SDK
            from google.cloud import discoveryengine_v1 as discoveryengine  # type: ignore

            client = discoveryengine.SearchServiceClient()
            serving_config = (
                f"projects/{self.settings.google_cloud_project}"
                f"/locations/global/collections/default_collection"
                f"/engines/{self.settings.agent_builder_app_id}"
                f"/servingConfigs/default_search"
            )
            request = discoveryengine.SearchRequest(
                serving_config=serving_config, query=query, page_size=3
            )
            response = client.search(request)
            results = [dict(r.document.struct_data) for r in response.results]
            return ToolResult.success(
                self.name, results=results, source="vertex_ai_search", query=query
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self._mock_search(query, error=str(exc))

    def _mock_search(self, query: str, error: str | None = None) -> ToolResult:
        from app.agent import fixtures

        query_lower = query.lower()
        results: list[dict] = []
        for fixture in fixtures.FIXTURES.values():
            if any(
                team.lower() in query_lower
                for team in (fixture["home"], fixture["away"])
            ) or any(
                word in query_lower
                for word in ("venue", "stadium", "schedule", "kickoff", "gate")
            ):
                results.append(fixture)
        if not results:
            results = list(fixtures.FIXTURES.values())[:2]
        return ToolResult.success(
            self.name, results=results, source="mock", query=query, error=error
        )

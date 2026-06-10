"""The concierge orchestrator.

Routes a request to the right tool(s), invokes them through a circuit breaker
with a retry policy, composes a grounded answer, and records token/cost usage.
The orchestrator emits a rich ``OrchestrationResult`` capturing every tool call
so the tracer can turn it into spans and the eval engine can inspect grounding.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.agent.concierge import detect_intent, _TEAM_PATTERN
from app.core.config import Settings, get_settings
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    IntentType,
)
from app.orchestration.concierge_tools import (
    FixtureLookupTool,
    GateLookupTool,
    KickoffTool,
    TicketingTool,
    TranslationTool,
)
from app.orchestration.cost import CostLedger
from app.orchestration.resilience import CircuitBreaker, RetryPolicy
from app.orchestration.tools import ToolRegistry, ToolResult


@dataclass
class OrchestrationResult:
    response: ConciergeResponse
    tool_calls: list[ToolResult] = field(default_factory=list)
    cost: dict = field(default_factory=dict)
    plan: list[str] = field(default_factory=list)


def build_tool_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(FixtureLookupTool())
    reg.register(KickoffTool())
    reg.register(GateLookupTool())
    reg.register(TranslationTool())
    reg.register(TicketingTool())
    return reg


# Maps an intent to the ordered tool plan that serves it.
_INTENT_PLAN: dict[IntentType, list[str]] = {
    IntentType.KICKOFF_TIME: ["kickoff_time"],
    IntentType.GATE_INFO: ["gate_lookup"],
    IntentType.TICKETING: ["ticketing_info"],
    IntentType.TRAVEL: ["fixture_lookup"],
    IntentType.STADIUM_NAV: ["fixture_lookup"],
}


class ConciergeOrchestrator:
    """Tool-using orchestration over the concierge tools."""

    def __init__(
        self,
        settings: Settings | None = None,
        registry: ToolRegistry | None = None,
        retry: RetryPolicy | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("gemini")
        self.registry = registry or build_tool_registry()
        self.retry = retry or RetryPolicy(max_attempts=2, base_delay_s=0.0)
        self.breaker = breaker or CircuitBreaker(failure_threshold=5)

    def _section_from_text(self, text: str) -> str:
        import re

        m = re.search(r"section\s+(\w+)", text.lower())
        return m.group(1) if m else "114"

    def _invoke(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self.registry.get(tool_name)
        # Resilient invocation: retry around the breaker-protected call.
        def _call() -> ToolResult:
            return self.breaker.call(lambda: tool.invoke(**kwargs))

        try:
            return self.retry.run(_call)
        except Exception as exc:  # breaker open or retry exhausted
            return ToolResult.failure(tool_name, f"{type(exc).__name__}: {exc}")

    def _compose(
        self,
        intent: IntentType,
        results: list[ToolResult],
        language: str,
    ) -> tuple[str, dict]:
        grounded: dict = {}
        ok = [r for r in results if r.ok]
        if not ok:
            return "I'm sorry, I don't have that information yet.", grounded

        primary = ok[0]
        grounded.update(primary.data)

        if intent == IntentType.KICKOFF_TIME:
            kickoff = primary.data["kickoff_local"]
            grounded["kickoff_local"] = kickoff
            hhmm = kickoff.split("T")[1][:5]
            text = f"Kickoff is at {hhmm} local time at {primary.data['venue']}."
        elif intent == IntentType.GATE_INFO:
            text = (
                f"Your gate is {primary.data['gate']} for section "
                f"{primary.data['section']}."
            )
        elif intent == IntentType.TICKETING:
            text = primary.data["guidance"]
        elif intent in (IntentType.TRAVEL, IntentType.STADIUM_NAV):
            fx = primary.data["fixture"]
            text = (
                f"For {fx['venue']} in {fx['city']}, public transit is "
                f"recommended on matchday."
            )
        else:
            text = "I'm sorry, I don't have that information yet."
        return text, grounded

    def run(self, req: ConciergeRequest) -> OrchestrationResult:
        start = time.perf_counter()
        intent = detect_intent(req.text)
        teams = _TEAM_PATTERN.findall(req.text)
        plan = _INTENT_PLAN.get(intent, [])
        ledger = CostLedger()

        results: list[ToolResult] = []
        for tool_name in plan:
            kwargs: dict = {}
            if tool_name in ("kickoff_time", "fixture_lookup") and teams:
                kwargs["team_a"] = teams[0]
                if len(teams) > 1:
                    kwargs["team_b"] = teams[1]
            elif tool_name == "gate_lookup" and teams:
                kwargs["team_a"] = teams[0]
                kwargs["section"] = self._section_from_text(req.text)
            results.append(self._invoke(tool_name, **kwargs))

        text, grounded = self._compose(intent, results, req.language.value)
        model = self.settings.gemini_model if self.mode == "real" else "mock-concierge"
        ledger.add_text(model, req.text, text)

        response = ConciergeResponse(
            request_id=req.request_id,
            text=text,
            detected_intent=intent,
            language=req.language,
            grounded_facts=grounded,
            model=model,
            latency_ms=(time.perf_counter() - start) * 1000.0,
        )
        return OrchestrationResult(
            response=response,
            tool_calls=results,
            cost=ledger.summary(),
            plan=plan,
        )

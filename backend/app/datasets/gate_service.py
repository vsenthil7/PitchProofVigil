"""Gate service — run a candidate over a golden dataset and persist the decision.

Loads a golden dataset, runs each example through the orchestrator + scoring
engine via the CandidateGate, compares against the most recent passing
decision's category scores (baseline), persists the GateDecisionRow, and emits
a metric. The baseline lookup makes regression detection automatic.
"""
from __future__ import annotations

from app.core.models import ConciergeRequest, Language
from app.datasets.eval_service import build_trace
from app.db.models import GateDecisionRow
from app.evaluators.candidate_gate import CandidateGate, CandidateGateResult
from app.evaluators.scoring import GatePolicy, ScoringEngine
from app.observability.metrics import Metrics
from app.orchestration.orchestrator import ConciergeOrchestrator
from app.repositories.registry import (
    GateDecisionRepository,
    GoldenDatasetRepository,
)


class GateService:
    def __init__(
        self,
        tenant_id: str,
        orchestrator: ConciergeOrchestrator,
        engine: ScoringEngine,
        golden_repo: GoldenDatasetRepository,
        decision_repo: GateDecisionRepository,
        metrics: Metrics,
        regression_tolerance: float = 0.05,
    ) -> None:
        self.tenant_id = tenant_id
        self.orchestrator = orchestrator
        self.gate = CandidateGate(engine, regression_tolerance=regression_tolerance)
        self.golden_repo = golden_repo
        self.decision_repo = decision_repo
        self.metrics = metrics

    def _example_to_request(self, example: dict) -> ConciergeRequest:
        return ConciergeRequest(
            text=example["text"],
            language=Language(example.get("language", "en")),
        )

    async def run_candidate(
        self,
        candidate: str,
        dataset_name: str,
        policy: GatePolicy,
    ) -> CandidateGateResult:
        dataset = await self.golden_repo.get(dataset_name)
        examples = dataset.examples if dataset else []

        traces = []
        for example in examples:
            req = self._example_to_request(example)
            result = self.orchestrator.run(req)
            traces.append(build_trace(req, result.response, result.tool_calls))

        # Baseline = category scores of the most recent passing decision.
        latest = await self.decision_repo.latest_passing()
        baseline = latest.category_scores if latest else None

        decision = self.gate.evaluate(
            candidate, traces, policy, baseline_category_scores=baseline
        )

        await self.decision_repo.add(
            GateDecisionRow(
                id=decision.decision_id,
                tenant_id=self.tenant_id,
                candidate=candidate,
                policy_name=decision.policy_name,
                passed=decision.passed,
                aggregate_score=decision.aggregate_score,
                threshold=decision.threshold,
                category_scores=decision.category_scores,
                baseline_deltas=decision.baseline_deltas,
                regressions=decision.regressions,
                reason=decision.reason,
                trace_count=decision.total_traces(),
            )
        )
        self.metrics.observe_gate(decision.passed)
        return decision

    async def run_inline(
        self,
        candidate: str,
        queries: list[str],
        policy: GatePolicy,
        language: Language = Language.EN,
    ) -> CandidateGateResult:
        """Run a gate over ad-hoc queries (no stored dataset required)."""
        traces = []
        for q in queries:
            req = ConciergeRequest(text=q, language=language)
            result = self.orchestrator.run(req)
            traces.append(build_trace(req, result.response, result.tool_calls))
        latest = await self.decision_repo.latest_passing()
        baseline = latest.category_scores if latest else None
        decision = self.gate.evaluate(
            candidate, traces, policy, baseline_category_scores=baseline
        )
        await self.decision_repo.add(
            GateDecisionRow(
                id=decision.decision_id,
                tenant_id=self.tenant_id,
                candidate=candidate,
                policy_name=decision.policy_name,
                passed=decision.passed,
                aggregate_score=decision.aggregate_score,
                threshold=decision.threshold,
                category_scores=decision.category_scores,
                baseline_deltas=decision.baseline_deltas,
                regressions=decision.regressions,
                reason=decision.reason,
                trace_count=decision.total_traces(),
            )
        )
        self.metrics.observe_gate(decision.passed)
        return decision

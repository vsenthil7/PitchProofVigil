"""Multi-model LLM judge ensemble.

Runs multiple LLM judges (same evaluator logic, different Gemini model IDs) and
aggregates by majority vote (on verdict) or mean (on score). Increases judge
reliability by reducing single-model variance.

Configuration:
  JUDGE_MODELS=gemini-2.0-flash,gemini-1.5-pro   (comma-separated)
  JUDGE_AGGREGATION=mean                          (or "majority")
"""
from __future__ import annotations

import dataclasses
import statistics
from typing import Literal

from app.core.config import Settings, get_settings
from app.evaluators.base import (
    EvalContext,
    EvaluationOutcome,
    Evaluator,
    EvaluatorCategory,
    EvaluatorSpec,
    Finding,
    Severity,
    Verdict,
)
from app.evaluators.llm_judge import LLMJudgeEvaluator


class EnsembleJudge(Evaluator):
    """Aggregates verdicts/scores from N LLM judges for increased reliability."""

    spec = EvaluatorSpec(
        name="ensemble_judge",
        version="1.0.0",
        category=EvaluatorCategory.QUALITY,
        title="LLM Judge Ensemble",
        description=(
            "Runs multiple LLM judge models and aggregates by majority vote "
            "(verdict) or mean (score)."
        ),
        default_weight=2.0,
        blocking_by_default=False,
        requires_llm_judge=True,
    )

    def __init__(
        self,
        model_ids: list[str] | None = None,
        aggregation: Literal["majority", "mean"] = "mean",
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.aggregation = aggregation

        if model_ids is None:
            raw = getattr(self.settings, "judge_models", None) or "gemini-2.0-flash"
            model_ids = [m.strip() for m in raw.split(",") if m.strip()]

        self.judges: list[LLMJudgeEvaluator] = []
        for model_id in model_ids:
            patched = dataclasses.replace(self.settings, gemini_model=model_id)
            self.judges.append(LLMJudgeEvaluator(settings=patched))

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        outcomes: list[EvaluationOutcome] = [j._run(ctx) for j in self.judges]
        scores = [o.score for o in outcomes]
        verdicts = [o.verdict for o in outcomes]
        mean_score = statistics.mean(scores) if scores else 0.0

        if self.aggregation == "majority":
            verdict_counts: dict[Verdict, int] = {}
            for v in verdicts:
                verdict_counts[v] = verdict_counts.get(v, 0) + 1
            final_verdict = max(verdict_counts, key=lambda v: verdict_counts[v])
        else:
            fail_below = float(ctx.cfg("fail_below", 2.5)) / 4.0  # normalized 0-1
            warn_below = float(ctx.cfg("warn_below", 3.5)) / 4.0
            if mean_score < fail_below:
                final_verdict = Verdict.FAIL
            elif mean_score < warn_below:
                final_verdict = Verdict.WARN
            else:
                final_verdict = Verdict.PASS

        summary = (
            f"Ensemble ({len(self.judges)} judges, {self.aggregation}): "
            f"score={mean_score:.3f}, verdict={final_verdict.value}"
        )

        findings: list[Finding] = []
        if final_verdict != Verdict.PASS:
            findings.append(
                Finding(
                    code="ensemble_low_score",
                    message=summary,
                    severity=Severity.HIGH
                    if final_verdict == Verdict.FAIL
                    else Severity.MEDIUM,
                    evidence={
                        "individual_scores": scores,
                        "verdicts": [v.value for v in verdicts],
                        "aggregation": self.aggregation,
                    },
                )
            )

        return self._outcome(
            final_verdict,
            mean_score,
            summary,
            confidence=0.95,
            findings=findings,
            metadata={
                "individual_scores": scores,
                "verdicts": [v.value for v in verdicts],
                "aggregation": self.aggregation,
                "model_count": len(self.judges),
            },
        )

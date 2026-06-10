"""LLM-as-judge evaluator.

Uses an LLM (Gemini in real mode) to score the answer against a rubric on a
1-5 scale, returning a structured verdict. In mock mode it applies a
deterministic rubric heuristic so the evaluator is fully testable offline and
still produces meaningful variation.
"""
from __future__ import annotations

import json

from app.core.config import Settings, get_settings
from app.evaluators.base import (
    EvalContext,
    Evaluator,
    EvaluatorCategory,
    EvaluatorConfigField,
    EvaluatorSpec,
    EvaluationOutcome,
    Finding,
    Severity,
    Verdict,
)

_RUBRIC = (
    "You are a strict QA judge for a World Cup fan-concierge agent. "
    "Score the answer from 1 (unacceptable) to 5 (excellent) on helpfulness, "
    "correctness and tone. Respond ONLY as JSON: "
    '{"score": <1-5>, "reason": "<short>"}.'
)


class LLMJudgeEvaluator(Evaluator):
    spec = EvaluatorSpec(
        name="llm_judge",
        version="2.0.0",
        category=EvaluatorCategory.QUALITY,
        title="LLM-as-Judge",
        description="Scores answer quality 1-5 against a rubric using an LLM.",
        default_weight=1.5,
        blocking_by_default=False,
        requires_llm_judge=True,
        config_fields=(
            EvaluatorConfigField(
                name="fail_below",
                type="float",
                default=2.5,
                description="Rubric score (1-5) below which the verdict fails.",
                minimum=1.0,
                maximum=5.0,
            ),
            EvaluatorConfigField(
                name="warn_below",
                type="float",
                default=3.5,
                description="Rubric score below which the verdict warns.",
                minimum=1.0,
                maximum=5.0,
            ),
        ),
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("gemini")

    # --- scoring backends ------------------------------------------------

    def _mock_score(self, ctx: EvalContext) -> tuple[float, str]:
        """Deterministic rubric heuristic for offline mode."""
        resp = ctx.trace.response
        assert resp is not None
        score = 3.0
        reasons = []
        text = resp.text.strip()
        if len(text) > 30:
            score += 0.5
            reasons.append("sufficient detail")
        if resp.grounded_facts:
            score += 1.0
            reasons.append("grounded")
        if "i don't have" in text.lower() or not text:
            score -= 1.5
            reasons.append("non-answer")
        if resp.detected_intent.value == "general":
            score -= 0.5
            reasons.append("vague intent")
        score = max(1.0, min(5.0, score))
        return score, ", ".join(reasons) or "baseline"

    def _llm_score(self, ctx: EvalContext) -> tuple[float, str]:  # pragma: no cover
        """Real Gemini judge. Covered via injected fake SDK in tests."""
        from google import genai

        client = genai.Client(
            vertexai=True,
            project=self.settings.google_cloud_project,
            location="us-central1",
        )
        resp = ctx.trace.response
        assert resp is not None
        prompt = (
            f"{_RUBRIC}\nQuestion: {ctx.trace.request.text}\nAnswer: {resp.text}"
        )
        result = client.models.generate_content(
            model=self.settings.gemini_model, contents=prompt
        )
        raw = result.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        data = json.loads(raw)
        return float(data["score"]), str(data.get("reason", ""))

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        if ctx.trace.response is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")

        if self.mode == "real":
            score5, reason = self._llm_score(ctx)
        else:
            score5, reason = self._mock_score(ctx)

        normalized = (score5 - 1.0) / 4.0  # map 1-5 → 0-1
        fail_below = float(ctx.cfg("fail_below", 2.5))
        warn_below = float(ctx.cfg("warn_below", 3.5))

        if score5 < fail_below:
            verdict = Verdict.FAIL
            sev = Severity.HIGH
        elif score5 < warn_below:
            verdict = Verdict.WARN
            sev = Severity.MEDIUM
        else:
            verdict = Verdict.PASS
            sev = Severity.INFO

        findings = (
            []
            if verdict == Verdict.PASS
            else [
                Finding(
                    "low_rubric_score",
                    f"Judge scored {score5:.1f}/5: {reason}",
                    sev,
                    evidence={"rubric_score": score5, "reason": reason},
                )
            ]
        )
        return self._outcome(
            verdict,
            normalized,
            f"LLM judge scored {score5:.1f}/5 ({reason}).",
            confidence=0.8 if self.mode == "mock" else 0.9,
            findings=findings,
            metadata={"rubric_score": score5, "mode": self.mode},
        )

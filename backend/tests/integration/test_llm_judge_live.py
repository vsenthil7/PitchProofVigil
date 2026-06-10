"""Integration contract test for LLMJudgeEvaluator - requires GOOGLE_CLOUD_PROJECT.

Skipped by default (no creds in CI/sandbox). Run with the integration tier when
GOOGLE_CLOUD_PROJECT and Vertex credentials are present.
"""
import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_PROJECT"),
    reason="Requires GOOGLE_CLOUD_PROJECT (integration tier)",
)
async def test_real_gemini_judge_known_prompt():
    from app.core.config import Settings
    from app.core.models import (
        ConciergeRequest,
        ConciergeResponse,
        IntentType,
        Language,
    )
    from app.evaluators.base import EvalContext
    from app.evaluators.llm_judge import LLMJudgeEvaluator
    from app.phoenix.tracer import Tracer

    s = Settings(
        use_mocks=False,
        jwt_secret=os.environ.get("JWT_SECRET", "a" * 64),
        google_cloud_project=os.environ["GOOGLE_CLOUD_PROJECT"],
    )
    judge = LLMJudgeEvaluator(settings=s)
    req = ConciergeRequest(
        text="What time does Spain vs Germany kick off?", language=Language.EN
    )
    resp = ConciergeResponse(
        request_id=req.request_id,
        text="Spain vs Germany kicks off at 20:00 local at MetLife Stadium.",
        detected_intent=IntentType.KICKOFF_TIME,
        language=Language.EN,
        grounded_facts={"kickoff_local": "2026-06-18T20:00:00"},
        model=s.gemini_model,
    )
    trace = Tracer().record(req, resp)
    outcome = judge.evaluate(EvalContext(trace=trace))
    assert outcome.verdict.value in ("pass", "warn")
    assert 3.0 <= outcome.metadata["rubric_score"] <= 5.0

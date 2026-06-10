"""Default evaluator registry assembly."""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.evaluators.base import EvaluatorRegistry
from app.evaluators.correctness import (
    FactualAccuracyEvaluator,
    GroundednessEvaluator,
    HallucinationEvaluator,
)
from app.evaluators.llm_judge import LLMJudgeEvaluator
from app.evaluators.quality import (
    IntentResolutionEvaluator,
    LatencySLOEvaluator,
    ResponseCompletenessEvaluator,
    TranslationQualityEvaluator,
)
from app.evaluators.safety import (
    PIILeakageEvaluator,
    PromptInjectionEvaluator,
    UnsafeContentEvaluator,
)


def build_default_registry(settings: Settings | None = None) -> EvaluatorRegistry:
    """Construct a registry populated with the full evaluator suite."""
    settings = settings or get_settings()
    registry = EvaluatorRegistry()
    registry.register(FactualAccuracyEvaluator())
    registry.register(GroundednessEvaluator())
    registry.register(HallucinationEvaluator())
    registry.register(TranslationQualityEvaluator())
    registry.register(ResponseCompletenessEvaluator())
    registry.register(LatencySLOEvaluator())
    registry.register(IntentResolutionEvaluator())
    registry.register(PIILeakageEvaluator())
    registry.register(UnsafeContentEvaluator())
    registry.register(PromptInjectionEvaluator())
    registry.register(LLMJudgeEvaluator(settings))
    return registry

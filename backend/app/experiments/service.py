"""Experiment management service: CRUD + synchronous run + run comparison."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GoldenDatasetRow
from app.db.models.experiments import (
    ExperimentItemResultRow,
    ExperimentRow,
    ExperimentRunRow,
)


class ExperimentService:
    """CRUD and run logic for experiments, tenant-isolated."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def create(
        self,
        name: str,
        dataset_id: str,
        evaluator_ids: list[str],
        description: str = "",
    ) -> ExperimentRow:
        row = ExperimentRow(
            tenant_id=self.tenant_id,
            name=name,
            description=description,
            dataset_id=dataset_id,
            evaluator_ids=evaluator_ids,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, experiment_id: str) -> ExperimentRow | None:
        stmt = select(ExperimentRow).where(
            ExperimentRow.id == experiment_id,
            ExperimentRow.tenant_id == self.tenant_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list(self, limit: int = 50, offset: int = 0) -> list[ExperimentRow]:
        stmt = (
            select(ExperimentRow)
            .where(ExperimentRow.tenant_id == self.tenant_id)
            .order_by(ExperimentRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def trigger_run(self, experiment_id: str, registry) -> ExperimentRunRow:
        """Create a run and synchronously evaluate all dataset examples."""
        experiment = await self.get(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found")

        stmt = select(GoldenDatasetRow).where(
            GoldenDatasetRow.id == experiment.dataset_id,
            GoldenDatasetRow.tenant_id == self.tenant_id,
        )
        dataset = (await self.session.execute(stmt)).scalars().first()
        if dataset is None:
            raise ValueError(f"Dataset {experiment.dataset_id} not found")

        run = ExperimentRunRow(
            experiment_id=experiment_id,
            tenant_id=self.tenant_id,
            status="running",
        )
        self.session.add(run)
        await self.session.flush()

        from app.core.models import (
            ConciergeRequest,
            ConciergeResponse,
            IntentType,
            Language,
        )
        from app.evaluators.base import EvalContext
        from app.phoenix.tracer import Tracer

        item_results: list[ExperimentItemResultRow] = []
        scores: list[float] = []
        for idx, example in enumerate(dataset.examples):
            request_text = example.get("input", example.get("request_text", ""))
            response_text = example.get("output", example.get("response_text", ""))
            if not request_text:
                continue

            req = ConciergeRequest(text=request_text[:4096], language=Language.EN)
            resp = ConciergeResponse(
                request_id=req.request_id,
                text=response_text[:16384] if response_text else "",
                detected_intent=IntentType.GENERAL,
                language=Language.EN,
                model="dataset-replay",
            )
            ctx = EvalContext(trace=Tracer().record(req, resp))

            verdicts: dict = {}
            item_score = 0.0
            item_count = 0
            for ev_id in experiment.evaluator_ids:
                if ev_id not in registry:
                    continue
                outcome = registry.get(ev_id).evaluate(ctx)
                verdicts[ev_id] = {
                    "verdict": outcome.verdict.value,
                    "score": outcome.score,
                    "summary": outcome.summary,
                }
                item_score += outcome.score
                item_count += 1

            agg = round(item_score / item_count, 4) if item_count else 0.0
            scores.append(agg)
            item_results.append(
                ExperimentItemResultRow(
                    run_id=run.id,
                    tenant_id=self.tenant_id,
                    example_index=idx,
                    request_text=request_text[:4096],
                    response_text=response_text[:16384] if response_text else None,
                    verdicts=verdicts,
                    aggregate_score=agg,
                    passed=agg >= 0.85,
                )
            )

        for item_row in item_results:
            self.session.add(item_row)

        run.aggregate_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        run.verdict_summary = {
            "total_items": len(item_results),
            "pass_rate": (
                round(sum(1 for r in item_results if r.passed) / len(item_results), 4)
                if item_results
                else 0.0
            ),
        }
        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        experiment.last_run_at = run.completed_at
        await self.session.flush()
        return run

    async def get_run(self, run_id: str) -> ExperimentRunRow | None:
        stmt = select(ExperimentRunRow).where(
            ExperimentRunRow.id == run_id,
            ExperimentRunRow.tenant_id == self.tenant_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_run_items(self, run_id: str) -> list[ExperimentItemResultRow]:
        stmt = (
            select(ExperimentItemResultRow)
            .where(
                ExperimentItemResultRow.run_id == run_id,
                ExperimentItemResultRow.tenant_id == self.tenant_id,
            )
            .order_by(ExperimentItemResultRow.example_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def compare_runs(self, run_a_id: str, run_b_id: str) -> dict:
        """Compare two runs: overall delta + per-evaluator mean delta."""
        run_a = await self.get_run(run_a_id)
        run_b = await self.get_run(run_b_id)
        if run_a is None or run_b is None:
            raise ValueError("One or both runs not found")

        items_a = {r.example_index: r for r in await self.get_run_items(run_a_id)}
        items_b = {r.example_index: r for r in await self.get_run_items(run_b_id)}

        delta = round((run_b.aggregate_score or 0.0) - (run_a.aggregate_score or 0.0), 4)

        ev_deltas: dict = {}
        for idx in set(items_a) & set(items_b):
            for ev_id in items_a[idx].verdicts or {}:
                score_a = items_a[idx].verdicts[ev_id].get("score", 0.0)
                score_b = items_b[idx].verdicts.get(ev_id, {}).get("score", 0.0)
                ev_deltas.setdefault(ev_id, []).append(score_b - score_a)

        per_ev = {
            ev_id: round(sum(d) / len(d), 4) for ev_id, d in ev_deltas.items()
        }
        return {
            "run_a": run_a_id,
            "run_b": run_b_id,
            "score_a": run_a.aggregate_score,
            "score_b": run_b.aggregate_score,
            "delta": delta,
            "winner": "run_b" if delta > 0 else ("run_a" if delta < 0 else "tie"),
            "per_evaluator_delta": per_ev,
        }

    async def ab_compare(
        self,
        experiment_id: str,
        baseline_version: str,
        candidate_version: str,
        dataset_id: str,
        evaluator_ids: list[str],
        registry,
    ) -> dict:
        """Compare two agent versions over the same dataset.

        Runs the requested evaluators over dataset examples labelled with each
        version tag, and returns winner, delta_score, Cohen's d, and a
        two-proportion z-test on pass rates.
        """
        import math

        def _cohens_d(a: list[float], b: list[float]) -> float:
            if len(a) < 2 or len(b) < 2:
                return 0.0
            mean_a = sum(a) / len(a)
            mean_b = sum(b) / len(b)
            var_a = sum((x - mean_a) ** 2 for x in a) / (len(a) - 1)
            var_b = sum((x - mean_b) ** 2 for x in b) / (len(b) - 1)
            pooled_sd = math.sqrt((var_a + var_b) / 2)
            return round((mean_b - mean_a) / pooled_sd, 4) if pooled_sd > 0 else 0.0

        def _two_prop_z(pass_a: int, n_a: int, pass_b: int, n_b: int) -> float:
            if n_a == 0 or n_b == 0:
                return 0.0
            p_a = pass_a / n_a
            p_b = pass_b / n_b
            p_hat = (pass_a + pass_b) / (n_a + n_b)
            denom = math.sqrt(p_hat * (1 - p_hat) * (1 / n_a + 1 / n_b))
            return round((p_b - p_a) / denom, 4) if denom > 0 else 0.0

        baseline_run = ExperimentRunRow(
            experiment_id=experiment_id,
            tenant_id=self.tenant_id,
            status="running",
            ab_baseline_version=baseline_version,
        )
        candidate_run = ExperimentRunRow(
            experiment_id=experiment_id,
            tenant_id=self.tenant_id,
            status="running",
            ab_candidate_version=candidate_version,
        )
        self.session.add(baseline_run)
        self.session.add(candidate_run)
        await self.session.flush()

        stmt = select(GoldenDatasetRow).where(
            GoldenDatasetRow.id == dataset_id,
            GoldenDatasetRow.tenant_id == self.tenant_id,
        )
        dataset = (await self.session.execute(stmt)).scalars().first()
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        from app.core.models import (
            ConciergeRequest,
            ConciergeResponse,
            IntentType,
            Language,
        )
        from app.evaluators.base import EvalContext
        from app.phoenix.tracer import Tracer

        baseline_scores: list[float] = []
        candidate_scores: list[float] = []

        for example in dataset.examples:
            request_text = example.get("input", example.get("request_text", ""))
            if not request_text:
                continue
            for version, scores_list in [
                (baseline_version, baseline_scores),
                (candidate_version, candidate_scores),
            ]:
                req = ConciergeRequest(text=request_text[:4096], language=Language.EN)
                resp = ConciergeResponse(
                    request_id=req.request_id,
                    text=example.get("output", f"Response for {version}.")[:16384],
                    detected_intent=IntentType.GENERAL,
                    language=Language.EN,
                    model=version,
                )
                ctx = EvalContext(trace=Tracer().record(req, resp))
                item_score = 0.0
                count = 0
                for ev_id in evaluator_ids:
                    if ev_id not in registry:
                        continue
                    outcome = registry.get(ev_id).evaluate(ctx)
                    item_score += outcome.score
                    count += 1
                scores_list.append(item_score / count if count else 0.0)

        mean_b = (
            round(sum(baseline_scores) / len(baseline_scores), 4)
            if baseline_scores
            else 0.0
        )
        mean_c = (
            round(sum(candidate_scores) / len(candidate_scores), 4)
            if candidate_scores
            else 0.0
        )
        delta = round(mean_c - mean_b, 4)
        cohens_d = _cohens_d(baseline_scores, candidate_scores)
        pass_b = sum(1 for s in baseline_scores if s >= 0.85)
        pass_c = sum(1 for s in candidate_scores if s >= 0.85)
        z_score = _two_prop_z(
            pass_b, len(baseline_scores), pass_c, len(candidate_scores)
        )
        winner = "candidate" if delta > 0 else ("baseline" if delta < 0 else "tie")

        for run_obj, agg in [(baseline_run, mean_b), (candidate_run, mean_c)]:
            run_obj.aggregate_score = agg
            run_obj.status = "complete"
            run_obj.ab_delta_score = delta
            run_obj.ab_cohens_d = cohens_d
            run_obj.ab_winner = winner
        await self.session.flush()

        return {
            "baseline_version": baseline_version,
            "candidate_version": candidate_version,
            "baseline_score": mean_b,
            "candidate_score": mean_c,
            "delta_score": delta,
            "winner": winner,
            "cohens_d": cohens_d,
            "z_score": z_score,
            "statistical_significance": abs(z_score) > 1.96,
            "baseline_pass_rate": round(pass_b / len(baseline_scores), 4)
            if baseline_scores
            else 0.0,
            "candidate_pass_rate": round(pass_c / len(candidate_scores), 4)
            if candidate_scores
            else 0.0,
        }

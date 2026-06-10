"""Token and cost accounting.

A simple per-model price book and a ledger that accumulates token usage and
dollar cost across an agent run. Estimation falls back to a chars/4 heuristic
when an exact token count is unavailable (mock mode).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1K tokens (input, output). Illustrative public-style pricing.
PRICE_BOOK: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "mock-concierge": (0.0, 0.0),
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    return max(1, (len(text) + 3) // 4)


@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class CostLedger:
    """Accumulates usage and cost across a run."""

    records: list[UsageRecord] = field(default_factory=list)

    def add(self, model: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        in_price, out_price = PRICE_BOOK.get(model, (0.0, 0.0))
        cost = (input_tokens / 1000.0) * in_price + (
            output_tokens / 1000.0
        ) * out_price
        rec = UsageRecord(model, input_tokens, output_tokens, round(cost, 8))
        self.records.append(rec)
        return rec

    def add_text(self, model: str, prompt: str, completion: str) -> UsageRecord:
        return self.add(model, estimate_tokens(prompt), estimate_tokens(completion))

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.records), 8)

    def summary(self) -> dict:
        return {
            "calls": len(self.records),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": self.total_cost_usd,
        }


class CostBudgetEnforcer:
    """Checks per-tenant monthly spend cap before allowing an LLM judge call."""

    def __init__(self, session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def check_budget(
        self, estimated_cost_usd: float = 0.001
    ) -> tuple[bool, str]:
        """Return (allowed, reason). allowed=False blocks the LLM call."""
        from datetime import datetime, timezone

        from sqlalchemy import func, select

        from app.db.models.governance import CostBudgetRow, CostEventRow

        month = datetime.now(timezone.utc).strftime("%Y-%m")

        stmt = select(CostBudgetRow).where(
            CostBudgetRow.tenant_id == self.tenant_id,
            CostBudgetRow.month == month,
        )
        budget = (await self.session.execute(stmt)).scalars().first()
        if budget is None:
            return True, "no_budget_configured"

        stmt2 = select(func.sum(CostEventRow.cost_usd)).where(
            CostEventRow.tenant_id == self.tenant_id,
            CostEventRow.month == month,
        )
        current_spend = (await self.session.execute(stmt2)).scalar() or 0.0

        projected = current_spend + estimated_cost_usd
        if projected > budget.monthly_usd_cap:
            return False, (
                f"BUDGET_EXCEEDED: projected ${projected:.4f} > "
                f"cap ${budget.monthly_usd_cap:.2f}"
            )
        if current_spend >= budget.monthly_usd_cap * budget.alert_threshold_pct:
            return True, (
                f"BUDGET_THRESHOLD_ALERT: "
                f"{current_spend:.4f}/{budget.monthly_usd_cap:.2f}"
            )
        return True, "ok"

    async def record_event(
        self, model: str, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        """Persist a cost event for auditing and aggregation."""
        from datetime import datetime, timezone

        from app.db.models.governance import CostEventRow

        event = CostEventRow(
            tenant_id=self.tenant_id,
            month=datetime.now(timezone.utc).strftime("%Y-%m"),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        self.session.add(event)
        await self.session.flush()

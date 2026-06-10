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

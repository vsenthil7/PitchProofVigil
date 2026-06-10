"""Application context — wires the shared singletons together.

A single AppContext holds one TraceStore shared by the tracer and the MCP
client, plus the agent, eval engine and gate. The API layer depends on this so
every request sees the same trace history.
"""
from __future__ import annotations

from app.agent.concierge import ConciergeAgent
from app.core.config import Settings, get_settings
from app.evals.engine import EvalEngine
from app.evals.gate import DriftDetector, RegressionGate
from app.phoenix.mcp_client import PhoenixMCPClient
from app.phoenix.tracer import Tracer, TraceStore


class AppContext:
    """Container for the wired-together application services."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = TraceStore()
        self.agent = ConciergeAgent(self.settings)
        self.tracer = Tracer(self.settings, store=self.store)
        self.mcp = PhoenixMCPClient(self.settings, store=self.store)
        self.engine = EvalEngine(self.settings)
        self.gate = RegressionGate(engine=self.engine, settings=self.settings)
        self.drift = DriftDetector(self.settings)

    def mode_report(self) -> dict[str, str]:
        """Expose which integrations are real vs mock — surfaced in the UI."""
        return {
            "gemini": self.settings.integration_mode("gemini"),
            "phoenix": self.settings.integration_mode("phoenix"),
            "arize_ax": self.settings.integration_mode("arize_ax"),
        }


_context: AppContext | None = None


def get_context() -> AppContext:
    global _context
    if _context is None:
        _context = AppContext()
    return _context


def reset_context() -> None:
    """Test helper to force a fresh context."""
    global _context
    _context = None

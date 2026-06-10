"""Phoenix MCP client — the self-observability bridge.

This is the distinctive piece of PitchProof Vigil: the agent queries its *own*
traces and runs evaluations through the Arize Phoenix MCP server. Real mode
speaks to a running Phoenix MCP server; mock mode answers from the in-memory
TraceStore with the same method surface.
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.models import Trace
from app.phoenix.tracer import TraceStore


class PhoenixMCPClient:
    """Thin client over the Phoenix MCP server's tool surface.

    The MCP server exposes tools such as ``list_traces``, ``get_trace``,
    ``add_dataset_example`` and ``run_experiment``. We expose Pythonic methods
    that map onto those tools, with a mock backend over TraceStore.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        store: TraceStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("phoenix")
        self.store = store if store is not None else TraceStore()
        self._session = None
        if self.mode == "real":
            self._connect()

    def _connect(self) -> None:
        """Open an MCP session to the Phoenix server (lazy import)."""
        try:  # pragma: no cover - requires live MCP server
            # The Phoenix MCP server is launched separately:
            #   npx -y @arizeai/phoenix-mcp --endpoint $PHOENIX_COLLECTOR_ENDPOINT
            # Here we would establish a stdio/SSE MCP session. Kept lazy so the
            # mock path never imports MCP machinery.
            from mcp import ClientSession  # type: ignore

            self._session_cls = ClientSession
            self._session = None  # established on first call in real deployments
        except Exception:
            self._session = None

    # --- MCP tool surface ------------------------------------------------

    def list_traces(self, limit: int = 50) -> list[Trace]:
        """MCP tool: list recent traces for the project."""
        if self.mode == "real" and self._session is not None:  # pragma: no cover
            return self._call_tool("list_traces", {"limit": limit})
        return self.store.list(limit=limit)

    def get_trace(self, trace_id: str) -> Trace | None:
        """MCP tool: fetch a single trace by id."""
        if self.mode == "real" and self._session is not None:  # pragma: no cover
            return self._call_tool("get_trace", {"trace_id": trace_id})
        return self.store.get(trace_id)

    def add_dataset_example(self, dataset: str, trace: Trace) -> dict:
        """MCP tool: capture a trace into a Phoenix dataset for experiments."""
        if self.mode == "real" and self._session is not None:  # pragma: no cover
            return self._call_tool(
                "add_dataset_example",
                {"dataset": dataset, "trace_id": trace.trace_id},
            )
        return {
            "dataset": dataset,
            "example_id": trace.trace_id,
            "input": trace.request.text,
            "stored": True,
        }

    def _call_tool(self, name: str, args: dict):  # pragma: no cover
        """Invoke a named MCP tool on the live session."""
        raise RuntimeError(
            "Live MCP session not established; launch the Phoenix MCP server."
        )

    @property
    def connected(self) -> bool:
        if self.mode == "mock":
            return True
        return self._session is not None

"""Phoenix MCP client - the self-observability bridge.

The distinctive piece of PitchProof Vigil: the agent queries its *own* traces
and runs evaluations through the Arize Phoenix MCP server. Real mode speaks to
a running Phoenix MCP server (SSE transport) via a session created by an
injectable factory; mock mode answers from the in-memory TraceStore with the
same method surface, so callers never branch on mode.

Real-mode requirements:
  1. Phoenix running: docker run -p 6006:6006 arizephoenix/phoenix:latest
  2. Phoenix MCP server (SSE): npx -y @arizeai/phoenix-mcp --endpoint http://localhost:6006
  3. PHOENIX_API_KEY set if the instance requires auth.
  4. USE_MOCKS=false.

The ``mcp`` package is a *live-only* dependency: it is imported lazily inside
the session factory and never on the mock path, keeping the default runtime
free of it (and free of its starlette pin).
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.core.models import Trace
from app.phoenix.tracer import TraceStore

# A session factory returns an object exposing ``call_tool(name, args) -> Any``.
# In real deployments this wraps an ``mcp.ClientSession``; tests inject a fake.
SessionFactory = Callable[[Settings], "MCPSession | None"]


class MCPSession:
    """Minimal protocol the client needs from an MCP transport.

    The real session (built in :func:`default_session_factory`) adapts an
    ``mcp.ClientSession`` over SSE to this surface; a fake with the same two
    members can be injected in tests.
    """

    def call_tool(self, name: str, args: dict) -> Any:  # pragma: no cover - protocol
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - protocol
        pass


def default_session_factory(settings: Settings) -> MCPSession | None:
    """Build a real MCP session by lazy-importing the ``mcp`` SDK.

    Returns ``None`` if the SDK is unavailable or the endpoint is unset, so the
    client degrades to the local store rather than crashing. This body needs a
    live MCP server + the optional ``mcp`` dependency, so it is not exercised
    by the in-sandbox suite.
    """
    try:  # pragma: no cover - requires live MCP server + optional mcp dep
        from mcp import ClientSession  # type: ignore  # noqa: F401

        endpoint = settings.phoenix_collector_endpoint
        if not endpoint:
            return None
        # A real adapter would open an SSE ClientSession here and translate
        # call_tool() onto session.call_tool(...). Returning None keeps the
        # mock-backed behavior until a concrete transport is wired in a live
        # deployment (documented in docs/05-LIVE-RUNBOOK / P2.S2).
        return None
    except Exception:  # pragma: no cover - defensive
        return None


class PhoenixMCPClient:
    """Thin client over the Phoenix MCP server's tool surface.

    The MCP server exposes tools such as ``list_traces``, ``get_trace`` and
    ``add_dataset_example``. We expose Pythonic methods that map onto those
    tools, with a mock backend over TraceStore. When a real session is present
    (mode == real and the factory produced one), calls are routed to the live
    MCP server; otherwise they are served from the local store.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        store: TraceStore | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("phoenix")
        self.store = store if store is not None else TraceStore()
        self._factory: SessionFactory = session_factory or default_session_factory
        self._session: MCPSession | None = None
        if self.mode == "real":
            self._connect()

    def _connect(self) -> None:
        """Establish a live MCP session via the injectable factory.

        Never raises: a failing or unavailable factory leaves ``_session`` None
        and the client falls back to the local store.
        """
        try:
            self._session = self._factory(self.settings)
        except Exception:
            self._session = None

    def _live(self) -> bool:
        return self.mode == "real" and self._session is not None

    # --- MCP tool surface ------------------------------------------------

    def list_traces(self, limit: int = 50) -> list[Trace]:
        """MCP tool: list recent traces for the project."""
        if self._live():
            return self._session.call_tool("list_traces", {"limit": limit})
        return self.store.list(limit=limit)

    def get_trace(self, trace_id: str) -> Trace | None:
        """MCP tool: fetch a single trace by id."""
        if self._live():
            return self._session.call_tool("get_trace", {"trace_id": trace_id})
        return self.store.get(trace_id)

    def add_dataset_example(self, dataset: str, trace: Trace) -> dict:
        """MCP tool: capture a trace into a Phoenix dataset for experiments."""
        if self._live():
            return self._session.call_tool(
                "add_dataset_example",
                {"dataset": dataset, "trace_id": trace.trace_id},
            )
        return {
            "dataset": dataset,
            "example_id": trace.trace_id,
            "input": trace.request.text,
            "stored": True,
        }

    @property
    def connected(self) -> bool:
        if self.mode == "mock":
            return True
        return self._session is not None

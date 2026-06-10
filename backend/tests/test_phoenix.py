"""Tests for app.phoenix — tracer, store, MCP client."""
from __future__ import annotations

import sys
import types

import pytest

from app.agent.concierge import ConciergeAgent
from app.core.config import Settings
from app.core.models import ConciergeRequest
from app.phoenix.mcp_client import PhoenixMCPClient
from app.phoenix.tracer import Tracer, TraceStore


@pytest.fixture
def populated_store():
    store = TraceStore()
    agent = ConciergeAgent(Settings(use_mocks=True))
    tracer = Tracer(Settings(use_mocks=True), store=store)
    for q in ["When does Spain play Germany?", "buy a ticket", "hello"]:
        req = ConciergeRequest(text=q)
        tracer.record(req, agent.answer(req))
    return store


def test_store_add_get_list_clear_len():
    store = TraceStore()
    assert len(store) == 0
    agent = ConciergeAgent(Settings(use_mocks=True))
    tracer = Tracer(Settings(use_mocks=True), store=store)
    req = ConciergeRequest(text="buy a ticket")
    trace = tracer.record(req, agent.answer(req))
    assert len(store) == 1
    assert store.get(trace.trace_id) is trace
    assert store.get("missing") is None
    assert store.list(limit=10)[0].trace_id == trace.trace_id
    store.clear()
    assert len(store) == 0


def test_tracer_builds_three_spans(populated_store):
    trace = populated_store.list(limit=1)[0]
    assert len(trace.spans) == 3
    kinds = {s.kind.value for s in trace.spans}
    assert kinds == {"AGENT", "RETRIEVER", "LLM"}


def test_tracer_shares_passed_store():
    store = TraceStore()
    tracer = Tracer(Settings(use_mocks=True), store=store)
    assert tracer.store is store


def test_tracer_default_store_when_none():
    tracer = Tracer(Settings(use_mocks=True))
    assert isinstance(tracer.store, TraceStore)


def test_list_order_is_newest_first(populated_store):
    traces = populated_store.list(limit=10)
    assert traces[0].request.text == "hello"


def test_mcp_mock_mode(populated_store):
    mcp = PhoenixMCPClient(Settings(use_mocks=True), store=populated_store)
    assert mcp.connected is True
    assert len(mcp.list_traces()) == 3
    first = mcp.list_traces(limit=1)[0]
    assert mcp.get_trace(first.trace_id) is not None
    assert mcp.get_trace("missing") is None


def test_mcp_add_dataset_example(populated_store):
    mcp = PhoenixMCPClient(Settings(use_mocks=True), store=populated_store)
    trace = populated_store.list(limit=1)[0]
    result = mcp.add_dataset_example("golden", trace)
    assert result["stored"] is True
    assert result["dataset"] == "golden"


def test_mcp_default_store_when_none():
    mcp = PhoenixMCPClient(Settings(use_mocks=True))
    assert isinstance(mcp.store, TraceStore)


def test_tracer_real_mode_register_called(monkeypatch):
    """Real mode should attempt to register a Phoenix tracer provider."""
    calls = {}
    fake_otel = types.ModuleType("phoenix.otel")

    def fake_register(endpoint, project_name):
        calls["endpoint"] = endpoint
        calls["project"] = project_name
        return object()

    fake_otel.register = fake_register
    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.otel = fake_otel
    monkeypatch.setitem(sys.modules, "phoenix", fake_phoenix)
    monkeypatch.setitem(sys.modules, "phoenix.otel", fake_otel)

    tracer = Tracer(Settings(use_mocks=False, jwt_secret="a"*64))
    assert tracer.mode == "real"
    assert calls["project"] == "pitchproof-vigil"
    assert "/v1/traces" in calls["endpoint"]


def test_tracer_real_mode_register_failure(monkeypatch):
    """A failing register must not raise; provider becomes None."""
    fake_otel = types.ModuleType("phoenix.otel")

    def boom(**kwargs):
        raise RuntimeError("no collector")

    fake_otel.register = boom
    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.otel = fake_otel
    monkeypatch.setitem(sys.modules, "phoenix", fake_phoenix)
    monkeypatch.setitem(sys.modules, "phoenix.otel", fake_otel)

    tracer = Tracer(Settings(use_mocks=False, jwt_secret="a"*64))
    assert tracer._tracer_provider is None


def test_tracer_export_noop_in_mock(populated_store):
    tracer = Tracer(Settings(use_mocks=True), store=populated_store)
    # _export returns immediately in mock mode (provider is None)
    trace = populated_store.list(limit=1)[0]
    tracer._export(trace)  # should not raise


def test_tracer_export_real_invokes_exporter(monkeypatch):
    """Real mode with a provider exposing export_trace should call it."""
    captured = {}

    class FakeProvider:
        def export_trace(self, trace):
            captured["trace_id"] = trace.trace_id

    fake_otel = types.ModuleType("phoenix.otel")
    fake_otel.register = lambda **kw: FakeProvider()
    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.otel = fake_otel
    monkeypatch.setitem(sys.modules, "phoenix", fake_phoenix)
    monkeypatch.setitem(sys.modules, "phoenix.otel", fake_otel)

    store = TraceStore()
    agent = ConciergeAgent(Settings(use_mocks=True))
    tracer = Tracer(Settings(use_mocks=False, jwt_secret="a"*64), store=store)
    req = ConciergeRequest(text="buy a ticket")
    trace = tracer.record(req, agent.answer(req))
    assert captured["trace_id"] == trace.trace_id


def test_tracer_export_real_exporter_raises(monkeypatch):
    """An exception inside export_trace must be swallowed."""

    class FakeProvider:
        def export_trace(self, trace):
            raise RuntimeError("collector down")

    fake_otel = types.ModuleType("phoenix.otel")
    fake_otel.register = lambda **kw: FakeProvider()
    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.otel = fake_otel
    monkeypatch.setitem(sys.modules, "phoenix", fake_phoenix)
    monkeypatch.setitem(sys.modules, "phoenix.otel", fake_otel)

    store = TraceStore()
    agent = ConciergeAgent(Settings(use_mocks=True))
    tracer = Tracer(Settings(use_mocks=False, jwt_secret="a"*64), store=store)
    req = ConciergeRequest(text="buy a ticket")
    # Should not raise despite exporter raising.
    tracer.record(req, agent.answer(req))


def test_tracer_export_real_no_export_method(monkeypatch):
    """Provider without export_trace attribute is handled gracefully."""

    class BareProvider:
        pass

    fake_otel = types.ModuleType("phoenix.otel")
    fake_otel.register = lambda **kw: BareProvider()
    fake_phoenix = types.ModuleType("phoenix")
    fake_phoenix.otel = fake_otel
    monkeypatch.setitem(sys.modules, "phoenix", fake_phoenix)
    monkeypatch.setitem(sys.modules, "phoenix.otel", fake_otel)

    store = TraceStore()
    agent = ConciergeAgent(Settings(use_mocks=True))
    tracer = Tracer(Settings(use_mocks=False, jwt_secret="a"*64), store=store)
    req = ConciergeRequest(text="buy a ticket")
    tracer.record(req, agent.answer(req))  # should not raise


def test_mcp_real_mode_without_session_falls_back_to_store(populated_store):
    """Real mode but the factory yields no session -> serve from local store."""
    client = PhoenixMCPClient(
        Settings(use_mocks=False, jwt_secret="a" * 64),
        store=populated_store,
        session_factory=lambda s: None,
    )
    assert client.mode == "real"
    assert client.connected is False
    # Calls still work, served from the store.
    assert isinstance(client.list_traces(limit=5), list)


def test_mcp_real_connect_failure_is_swallowed():
    """A throwing factory leaves the client disconnected, never crashing."""
    def boom(_settings):
        raise RuntimeError("cannot reach MCP server")

    client = PhoenixMCPClient(
        Settings(use_mocks=False, jwt_secret="a" * 64), session_factory=boom
    )
    assert client.connected is False


def test_mcp_real_session_routes_calls(populated_store):
    """A live session routes tool calls to the MCP server, not the store."""
    calls: list[tuple[str, dict]] = []

    class FakeSession:
        def call_tool(self, name, args):
            calls.append((name, args))
            if name == "list_traces":
                return ["live-trace"]
            if name == "get_trace":
                return "live-one"
            return {"stored": True, "live": True}

        def close(self):
            pass

    client = PhoenixMCPClient(
        Settings(use_mocks=False, jwt_secret="a" * 64),
        store=populated_store,
        session_factory=lambda s: FakeSession(),
    )
    assert client.connected is True
    assert client.list_traces(limit=3) == ["live-trace"]
    assert client.get_trace("t1") == "live-one"
    # Build a minimal trace to exercise add_dataset_example routing.
    some = populated_store.list(limit=1)[0]
    result = client.add_dataset_example("ds", some)
    assert result.get("live") is True
    assert [c[0] for c in calls] == ["list_traces", "get_trace", "add_dataset_example"]


def test_default_session_factory_returns_none_without_endpoint():
    """With no collector endpoint, the default factory yields no session."""
    from app.phoenix.mcp_client import default_session_factory
    s = Settings(use_mocks=False, jwt_secret="a" * 64, phoenix_collector_endpoint="")
    assert default_session_factory(s) is None

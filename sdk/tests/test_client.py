"""SDK unit tests - httpx.post mocked."""
from unittest.mock import MagicMock, patch

import pytest

from pitchproof_vigil.client import Client, GateRequest, GateResult


def test_gate_passed():
    body = {
        "passed": True, "aggregate_score": 0.91, "threshold": 0.85,
        "candidate": "v1.3.0", "reason": "All evaluators passed.",
    }
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: body)
        client = Client(base_url="http://localhost:8000", api_key="ppv_test_key")
        result = client.gate.evaluate(
            GateRequest(candidate_version="v1.3.0", dataset_id="golden-wc26")
        )
    assert result.decision == "PASSED"
    assert result.passed is True
    assert result.aggregate_score == 0.91
    # Verify the SDK hit the REAL endpoint with the REAL payload shape.
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/api/gate/dataset")
    assert kwargs["json"] == {"candidate": "v1.3.0", "dataset": "golden-wc26"}
    assert kwargs["headers"]["X-API-Key"] == "ppv_test_key"


def test_gate_blocked_raises_system_exit():
    body = {
        "passed": False, "aggregate_score": 0.72, "threshold": 0.85,
        "candidate": "v1.3.0", "reason": "llm_judge failed below threshold.",
    }
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: body)
        client = Client(base_url="http://localhost:8000", api_key="ppv_test_key")
        result = client.gate.evaluate(
            GateRequest(candidate_version="v1.3.0", dataset_id="golden-wc26")
        )
    assert result.decision == "BLOCKED"
    with pytest.raises(SystemExit):
        result.raise_if_blocked()


def test_gate_passed_raise_if_blocked_is_noop():
    r = GateResult("PASSED", 0.9, 0.85, "ok", "v1", True)
    r.raise_if_blocked()  # must not raise


def test_gate_rate_limit_raises_runtime_error():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=429, text="Too many requests")
        client = Client(base_url="http://localhost:8000", api_key="ppv_test_key")
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            client.gate.evaluate(GateRequest(candidate_version="v1.3.0", dataset_id="ds"))


def test_gate_server_error_raises_runtime_error():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=500, text="boom")
        client = Client(base_url="http://localhost:8000", api_key="ppv_test_key")
        with pytest.raises(RuntimeError, match="Gate API error 500"):
            client.gate.evaluate(GateRequest(candidate_version="v1.3.0", dataset_id="ds"))


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("PPV_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key or PPV_API_KEY"):
        Client(base_url="http://localhost:8000")


def test_client_reads_env(monkeypatch):
    monkeypatch.setenv("PPV_API_KEY", "from-env")
    monkeypatch.setenv("PPV_BASE_URL", "http://env-host:9000")
    c = Client()
    assert c.gate._key == "from-env"
    assert c.gate._base == "http://env-host:9000"

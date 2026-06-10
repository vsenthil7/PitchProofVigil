"""SDK CLI tests."""
from unittest.mock import MagicMock, patch

import pytest

from pitchproof_vigil import cli


def _resp(body):
    return MagicMock(status_code=200, json=lambda: body)


def test_cli_gate_check_passed(capsys):
    body = {"passed": True, "aggregate_score": 0.9, "threshold": 0.85,
            "candidate": "v1", "reason": "ok"}
    with patch("httpx.post", return_value=_resp(body)):
        cli.main(["gate-check", "--version", "v1", "--dataset", "ds",
                  "--api-key", "k", "--base-url", "http://x"])
    out = capsys.readouterr().out
    assert "Decision: PASSED" in out


def test_cli_gate_check_blocked_exits(capsys):
    body = {"passed": False, "aggregate_score": 0.5, "threshold": 0.85,
            "candidate": "v1", "reason": "blocked"}
    with patch("httpx.post", return_value=_resp(body)):
        with pytest.raises(SystemExit):
            cli.main(["gate-check", "--version", "v1", "--dataset", "ds",
                      "--api-key", "k", "--base-url", "http://x"])


def test_cli_gate_check_no_fail(capsys):
    body = {"passed": False, "aggregate_score": 0.5, "threshold": 0.85,
            "candidate": "v1", "reason": "blocked"}
    with patch("httpx.post", return_value=_resp(body)):
        cli.main(["gate-check", "--version", "v1", "--dataset", "ds",
                  "--api-key", "k", "--base-url", "http://x", "--no-fail"])
    assert "Decision: BLOCKED" in capsys.readouterr().out


def test_cli_no_command_exits():
    with pytest.raises(SystemExit):
        cli.main([])

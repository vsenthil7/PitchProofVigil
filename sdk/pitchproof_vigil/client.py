"""PitchProof Vigil - CI gate-check client.

Usage::

    from pitchproof_vigil import Client, GateRequest
    client = Client(base_url="https://ppv.example.com", api_key="ppv_...")
    result = client.gate.evaluate(GateRequest(
        candidate_version="v1.3.0", dataset_id="golden-wc26",
    ))
    result.raise_if_blocked()

Targets the real PitchProof Vigil endpoint ``POST /api/gate/dataset`` (runs a
candidate agent version over a stored golden dataset under the tenant's active
gate policy) and reads the ``GateResponse`` contract
(candidate/passed/aggregate_score/threshold/reason).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is a hard dep of the SDK
    httpx = None  # type: ignore


@dataclass
class GateRequest:
    candidate_version: str
    dataset_id: str
    blocking: bool = True
    evaluator_ids: list[str] = field(default_factory=list)
    policy_name: str = "production"


@dataclass
class GateResult:
    decision: str  # "PASSED" | "BLOCKED"
    aggregate_score: float
    threshold: float
    summary: str
    candidate: str
    passed: bool
    raw: dict = field(default_factory=dict)

    def raise_if_blocked(self) -> None:
        if self.decision == "BLOCKED":
            raise SystemExit(
                f"PitchProof Vigil gate BLOCKED: {self.summary} "
                f"(score={self.aggregate_score:.3f} < "
                f"threshold={self.threshold:.3f})"
            )


class GateClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout

    def evaluate(self, req: GateRequest) -> GateResult:
        if httpx is None:  # pragma: no cover - httpx always present in tests
            raise ImportError("Install httpx: pip install httpx")

        url = f"{self._base}/api/gate/dataset"
        payload = {"candidate": req.candidate_version, "dataset": req.dataset_id}

        response = httpx.post(
            url,
            json=payload,
            headers={"X-API-Key": self._key},
            timeout=self._timeout,
        )
        if response.status_code == 429:
            raise RuntimeError("Rate limit exceeded. Slow down.")
        if response.status_code >= 400:
            raise RuntimeError(
                f"Gate API error {response.status_code}: {response.text}"
            )

        data = response.json()
        decision = "PASSED" if data.get("passed") else "BLOCKED"
        return GateResult(
            decision=decision,
            aggregate_score=data.get("aggregate_score", 0.0),
            threshold=data.get("threshold", 0.85),
            summary=data.get("reason", ""),
            candidate=data.get("candidate", req.candidate_version),
            passed=data.get("passed", False),
            raw=data,
        )


class Client:
    """Top-level PitchProof Vigil SDK client."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url or os.environ.get(
            "PPV_BASE_URL", "http://localhost:8000"
        )
        self._api_key = api_key or os.environ.get("PPV_API_KEY", "")
        if not self._api_key:
            raise ValueError("api_key or PPV_API_KEY env var required.")
        self.gate = GateClient(self._base_url, self._api_key, timeout)

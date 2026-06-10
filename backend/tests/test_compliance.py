"""Compliance export service + API tests (P6.M10)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.compliance.service import ComplianceExportService
from app.db.models import AuditLogRow, EvaluationRow, GateDecisionRow

_FROM = datetime.now(timezone.utc) - timedelta(hours=1)
_TO = datetime.now(timezone.utc) + timedelta(hours=1)


async def test_export_all_types_manifest_and_checksums(db, tenant_id):
    async with db.session() as s:
        for i in range(10):
            s.add(AuditLogRow(tenant_id=tenant_id, actor="t", action=f"a{i}", target=""))
        s.add(EvaluationRow(tenant_id=tenant_id, trace_id="tr", evaluator="llm_judge",
                            version="2", category="quality", verdict="pass",
                            score=0.9, confidence=0.9, summary=""))
        s.add(GateDecisionRow(id="gd1", tenant_id=tenant_id, candidate="v1",
                              policy_name="production", passed=True,
                              aggregate_score=0.9, threshold=0.85, reason="ok"))
        await s.flush()

        with tempfile.TemporaryDirectory() as tmp:
            svc = ComplianceExportService(s, tenant_id, tmp)
            job = svc.create_job(_FROM, _TO,
                                 ["audit_log", "eval_results", "gate_decisions"])
            await svc.run_export(job)

            assert job.status == "complete", job.error
            assert set(job.manifest) == {
                "audit_log.jsonl", "eval_results.jsonl", "gate_decisions.jsonl"
            }
            export_dir = Path(tmp) / job.job_id
            # 10 audit lines.
            lines = (export_dir / "audit_log.jsonl").read_text().splitlines()
            assert len(lines) == 10
            assert json.loads(lines[0])["action"] == "a0"
            # Checksum matches.
            h = hashlib.sha256((export_dir / "audit_log.jsonl").read_bytes()).hexdigest()
            assert job.manifest["audit_log.jsonl"] == h
            # Manifest file written.
            manifest = json.loads((export_dir / "manifest.json").read_text())
            assert manifest["tenant_id"] == tenant_id
            assert manifest["job_id"] == job.job_id


async def test_export_single_type_only(db, tenant_id):
    async with db.session() as s:
        s.add(AuditLogRow(tenant_id=tenant_id, actor="t", action="x", target=""))
        await s.flush()
        with tempfile.TemporaryDirectory() as tmp:
            svc = ComplianceExportService(s, tenant_id, tmp)
            job = svc.create_job(_FROM, _TO, ["audit_log"])
            await svc.run_export(job)
            assert list(job.manifest) == ["audit_log.jsonl"]


def test_get_job_unknown_returns_none():
    assert ComplianceExportService.get_job("does-not-exist") is None


def test_export_job_as_dict():
    from app.compliance.service import ExportJob
    job = ExportJob("jid", "t", _FROM, _TO, ["audit_log"])
    d = job.as_dict()
    assert d["job_id"] == "jid" and d["status"] == "pending"


# ---- API-level (owner has ADMIN) ----

def test_compliance_export_api_full_flow(owner_auth):
    client, headers, _ = owner_auth
    # Seed an audit row by performing an action that writes audit (register already did).
    r = client.post(
        "/api/admin/compliance/export",
        headers=headers,
        json={
            "from_date": _FROM.isoformat(),
            "to_date": _TO.isoformat(),
            "types": ["audit_log"],
        },
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    # BackgroundTasks run after the response in TestClient, so the job should be complete.
    status = client.get(f"/api/admin/compliance/export/{job_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] in ("complete", "pending", "running")


def test_compliance_status_unknown_job_404(owner_auth):
    client, headers, _ = owner_auth
    assert client.get("/api/admin/compliance/export/ghost", headers=headers).status_code == 404


def test_compliance_download_unknown_job_404(owner_auth):
    client, headers, _ = owner_auth
    r = client.get("/api/admin/compliance/export/ghost/download", headers=headers)
    assert r.status_code == 404


def test_compliance_download_completed_job(owner_auth):
    """Full API flow: export -> (background completes) -> download manifest."""
    client, headers, _ = owner_auth
    r = client.post(
        "/api/admin/compliance/export",
        headers=headers,
        json={"from_date": _FROM.isoformat(), "to_date": _TO.isoformat(),
              "types": ["audit_log"]},
    )
    job_id = r.json()["job_id"]
    # In Starlette's TestClient, BackgroundTasks run before the response returns,
    # so the job is complete by now.
    dl = client.get(f"/api/admin/compliance/export/{job_id}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/json")


def test_compliance_download_in_progress_409(owner_auth):
    """A job that exists but is not complete -> 409 on download."""
    client, headers, tenant_id = owner_auth
    from app.compliance.service import ExportJob, _JOBS

    job = ExportJob("inprog-job", tenant_id, _FROM, _TO, ["audit_log"], status="running")
    _JOBS[job.job_id] = job
    try:
        r = client.get(f"/api/admin/compliance/export/{job.job_id}/download", headers=headers)
        assert r.status_code == 409
    finally:
        _JOBS.pop(job.job_id, None)


def test_compliance_status_cross_tenant_403(owner_auth):
    """Polling a job that belongs to another tenant -> 403."""
    client, headers, _ = owner_auth
    from app.compliance.service import ExportJob, _JOBS

    job = ExportJob("other-tenant-job", "some-other-tenant", _FROM, _TO, ["audit_log"])
    _JOBS[job.job_id] = job
    try:
        r = client.get(f"/api/admin/compliance/export/{job.job_id}", headers=headers)
        assert r.status_code == 403
    finally:
        _JOBS.pop(job.job_id, None)

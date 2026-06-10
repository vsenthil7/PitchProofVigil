"""Compliance evidence export service.

Exports AuditLogRow, EvaluationRow, and GateDecisionRow for a date range to
JSONL files with SHA-256 checksums and a manifest. Self-hosted mode writes to a
local directory; cloud mode would upload to GCS/S3.

Job state is tracked in-process (``_JOBS``) to keep the export self-contained;
the durable ``ComplianceExportJobRow`` table (added in P3) is available for a
DB-backed registry in production.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditLogRow
from app.db.models.evaluation import EvaluationRow
from app.db.models.governance import GateDecisionRow
from app.observability.logging import get_logger

_log = get_logger("compliance")

ExportStatus = Literal["pending", "running", "complete", "error"]

_JOBS: dict[str, "ExportJob"] = {}


@dataclass
class ExportJob:
    job_id: str
    tenant_id: str
    from_date: datetime
    to_date: datetime
    types: list[str]
    status: ExportStatus = "pending"
    download_url: str | None = None
    error: str | None = None
    manifest: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "download_url": self.download_url,
            "manifest": self.manifest,
            "error": self.error,
        }


class ComplianceExportService:
    """Creates and tracks compliance export jobs."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str,
        export_dir: str = "/tmp/ppv_exports",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self, from_date: datetime, to_date: datetime, types: list[str]
    ) -> ExportJob:
        job = ExportJob(
            job_id=uuid.uuid4().hex,
            tenant_id=self.tenant_id,
            from_date=from_date,
            to_date=to_date,
            types=types,
        )
        _JOBS[job.job_id] = job
        return job

    @staticmethod
    def get_job(job_id: str) -> "ExportJob | None":
        return _JOBS.get(job_id)

    async def run_export(self, job: ExportJob) -> None:
        """Execute the export (intended for a background task)."""
        job.status = "running"
        try:
            job_dir = self.export_dir / job.job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            manifest: dict[str, str] = {}
            start_time = datetime.now(timezone.utc)

            if "audit_log" in job.types:
                manifest["audit_log.jsonl"] = self._sha256(
                    await self._export_audit_log(job, job_dir)
                )
            if "eval_results" in job.types:
                manifest["eval_results.jsonl"] = self._sha256(
                    await self._export_eval_results(job, job_dir)
                )
            if "gate_decisions" in job.types:
                manifest["gate_decisions.jsonl"] = self._sha256(
                    await self._export_gate_decisions(job, job_dir)
                )

            manifest_path = job_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "job_id": job.job_id,
                        "tenant_id": job.tenant_id,
                        "exported_at": start_time.isoformat(),
                        "from": job.from_date.isoformat(),
                        "to": job.to_date.isoformat(),
                        "files": manifest,
                    },
                    indent=2,
                )
            )
            job.manifest = manifest
            job.download_url = f"/api/admin/compliance/export/{job.job_id}/download"
            job.status = "complete"
            _log.info(
                "compliance_export_complete",
                job_id=job.job_id,
                files=list(manifest.keys()),
            )
        except Exception as exc:  # pragma: no cover - defensive; filesystem errors
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            _log.error("compliance_export_error", job_id=job.job_id, error=str(exc))

    async def _export_audit_log(self, job: ExportJob, dest: Path) -> Path:
        stmt = select(AuditLogRow).where(
            AuditLogRow.tenant_id == self.tenant_id,
            AuditLogRow.created_at >= job.from_date,
            AuditLogRow.created_at <= job.to_date,
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        path = dest / "audit_log.jsonl"
        with open(path, "w") as fh:
            for r in rows:
                fh.write(
                    json.dumps(
                        {
                            "id": r.id,
                            "actor": r.actor,
                            "action": r.action,
                            "target": r.target,
                            "detail": r.detail,
                            "created_at": r.created_at.isoformat(),
                        }
                    )
                    + "\n"
                )
        return path

    async def _export_eval_results(self, job: ExportJob, dest: Path) -> Path:
        stmt = select(EvaluationRow).where(
            EvaluationRow.tenant_id == self.tenant_id,
            EvaluationRow.created_at >= job.from_date,
            EvaluationRow.created_at <= job.to_date,
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        path = dest / "eval_results.jsonl"
        with open(path, "w") as fh:
            for r in rows:
                fh.write(
                    json.dumps(
                        {
                            "id": r.id,
                            "trace_id": r.trace_id,
                            "evaluator": r.evaluator,
                            "verdict": r.verdict,
                            "score": r.score,
                            "created_at": r.created_at.isoformat(),
                        }
                    )
                    + "\n"
                )
        return path

    async def _export_gate_decisions(self, job: ExportJob, dest: Path) -> Path:
        stmt = select(GateDecisionRow).where(
            GateDecisionRow.tenant_id == self.tenant_id,
            GateDecisionRow.created_at >= job.from_date,
            GateDecisionRow.created_at <= job.to_date,
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        path = dest / "gate_decisions.jsonl"
        with open(path, "w") as fh:
            for r in rows:
                fh.write(
                    json.dumps(
                        {
                            "id": r.id,
                            "candidate": r.candidate,
                            "passed": r.passed,
                            "aggregate_score": r.aggregate_score,
                            "threshold": r.threshold,
                            "created_at": r.created_at.isoformat(),
                        }
                    )
                    + "\n"
                )
        return path

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

"""Compliance evidence export API."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require
from app.auth.service import Permission, Principal
from app.compliance.service import ComplianceExportService

router = APIRouter(prefix="/api/admin/compliance", tags=["compliance"])

EXPORT_DIR = "/tmp/ppv_exports"


class ExportRequest(BaseModel):
    from_date: datetime
    to_date: datetime
    types: list[str] = ["audit_log", "eval_results", "gate_decisions"]


@router.post("/export", status_code=202)
async def create_export(
    body: ExportRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require(Permission.ADMIN)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Kick off an async compliance export. Returns job_id immediately."""
    svc = ComplianceExportService(session, principal.tenant_id, EXPORT_DIR)
    job = svc.create_job(body.from_date, body.to_date, body.types)
    background_tasks.add_task(svc.run_export, job)
    return {"job_id": job.job_id, "status": "pending"}


@router.get("/export/{job_id}")
async def get_export_status(
    job_id: str,
    principal: Principal = Depends(require(Permission.ADMIN)),
) -> dict:
    """Poll export job status."""
    job = ComplianceExportService.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if job.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return job.as_dict()


@router.get("/export/{job_id}/download")
async def download_export(
    job_id: str,
    principal: Principal = Depends(require(Permission.ADMIN)),
) -> FileResponse:
    """Download the manifest for a completed export."""
    job = ComplianceExportService.get_job(job_id)
    if job is None or job.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail=f"Export is {job.status}.")
    manifest_path = Path(EXPORT_DIR) / job_id / "manifest.json"
    if not manifest_path.exists():  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail="Manifest not found.")
    return FileResponse(
        str(manifest_path),
        media_type="application/json",
        filename=f"compliance_{job_id}_manifest.json",
    )

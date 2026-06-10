"""Compliance evidence export job tracking."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class ComplianceExportJobRow(SQLModel, table=True):
    """Background job for exporting SOC2/GDPR compliance evidence."""

    __tablename__ = "compliance_export_jobs"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    requested_by: str = Field(default="system")
    date_from: str  # ISO date "YYYY-MM-DD"
    date_to: str  # ISO date "YYYY-MM-DD"
    export_types: list = Field(default_factory=list, sa_column=Column(JSONType))
    status: str = Field(default="pending", index=True)  # pending|running|complete|error
    download_url: str | None = Field(default=None)
    checksum_manifest: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    error_detail: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = Field(default=None)

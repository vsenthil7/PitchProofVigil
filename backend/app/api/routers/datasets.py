"""Dataset router: golden datasets for the gate."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require
from app.api.schemas import CreateDatasetRequest, DatasetResponse
from app.auth.service import Permission, Principal
from app.db.models import GoldenDatasetRow
from app.repositories.registry import GoldenDatasetRepository

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _to_response(row: GoldenDatasetRow) -> DatasetResponse:
    return DatasetResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        example_count=len(row.examples),
    )


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    principal: Principal = Depends(require(Permission.WRITE)),
    session: AsyncSession = Depends(db_session),
) -> DatasetResponse:
    repo = GoldenDatasetRepository(session, principal.tenant_id)
    if await repo.get(body.name) is not None:
        raise HTTPException(status_code=409, detail="dataset exists")
    row = await repo.create(
        GoldenDatasetRow(
            tenant_id=principal.tenant_id,
            name=body.name,
            description=body.description,
            examples=body.examples,
        )
    )
    return _to_response(row)


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[DatasetResponse]:
    repo = GoldenDatasetRepository(session, principal.tenant_id)
    return [_to_response(r) for r in await repo.list()]

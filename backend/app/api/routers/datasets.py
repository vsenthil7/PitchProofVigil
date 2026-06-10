"""Dataset router: golden datasets for the gate."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require
from app.api.schemas import CreateDatasetRequest, DatasetResponse
from app.auth.service import Permission, Principal
from app.db.models import GoldenDatasetRow
from app.idempotency import IdempotencyStore
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
    idempotency_key: str | None = Header(default=None),
) -> DatasetResponse:
    # Replay protection: if this key was already used, return the prior result.
    store = IdempotencyStore(session, principal.tenant_id)
    if idempotency_key:
        prior = await store.get(idempotency_key)
        if prior is not None:
            return DatasetResponse(**prior.response_body)

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
    response = _to_response(row)
    if idempotency_key:
        await store.record(
            idempotency_key, "POST", "/api/datasets", 201, response.model_dump()
        )
    return response


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[DatasetResponse]:
    repo = GoldenDatasetRepository(session, principal.tenant_id)
    return [_to_response(r) for r in await repo.list()]

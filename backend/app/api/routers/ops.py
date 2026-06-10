"""Ops router: audit log and webhook subscription management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_cipher, require
from app.api.schemas.ops import (
    AuditEntryOut,
    CreateWebhookRequest,
    WebhookOut,
)
from app.auth.service import Permission, Principal
from app.repositories.audit import AuditRepository, WebhookRepository

router = APIRouter(prefix="/api", tags=["ops"])


@router.get("/audit", response_model=list[AuditEntryOut])
async def list_audit(
    limit: int = 100,
    action: str | None = None,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[AuditEntryOut]:
    repo = AuditRepository(session, principal.tenant_id)
    rows = (
        await repo.filter_by_action(action, limit=limit)
        if action
        else await repo.list(limit=limit)
    )
    return [
        AuditEntryOut(
            id=r.id,
            actor=r.actor,
            action=r.action,
            target=r.target,
            detail=r.detail,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/webhooks", response_model=WebhookOut, status_code=201)
async def create_webhook(
    body: CreateWebhookRequest,
    principal: Principal = Depends(require(Permission.MANAGE_POLICIES)),
    session: AsyncSession = Depends(db_session),
    cipher=Depends(get_cipher),
) -> WebhookOut:
    repo = WebhookRepository(session, principal.tenant_id, cipher=cipher)
    row = await repo.create(body.url, body.event_type, body.secret)
    return WebhookOut(
        id=row.id, url=row.url, event_type=row.event_type, active=row.active, last_status=row.last_status
    )


@router.get("/webhooks", response_model=list[WebhookOut])
async def list_webhooks(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[WebhookOut]:
    repo = WebhookRepository(session, principal.tenant_id)
    return [
        WebhookOut(id=r.id, url=r.url, event_type=r.event_type, active=r.active, last_status=r.last_status)
        for r in await repo.list()
    ]


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    principal: Principal = Depends(require(Permission.MANAGE_POLICIES)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    repo = WebhookRepository(session, principal.tenant_id)
    if not await repo.deactivate(webhook_id):
        raise HTTPException(status_code=404, detail="webhook not found")
    return {"deactivated": webhook_id}

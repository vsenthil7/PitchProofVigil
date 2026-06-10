"""Tests for the GDPR right-to-erasure endpoint (C3)."""
from __future__ import annotations


def test_owner_erases_own_tenant_data(owner_auth):
    client, headers, tenant_id = owner_auth
    # Seed: an ask creates a trace + evaluations + audit rows.
    client.post("/api/ask", headers=headers, json={"text": "I want a ticket"})

    # Erase.
    r = client.delete(f"/api/admin/tenants/{tenant_id}/data", headers=headers)
    assert r.status_code == 204

    # Verify at the data layer that tenant-scoped rows are gone.
    app = client.app
    import anyio

    async def _check():
        from sqlalchemy import func, select

        from app.db.models import AuditLogRow, EvaluationRow, Tenant, TraceRow, User

        async with app.state.database.session() as s:
            for model in (TraceRow, EvaluationRow, AuditLogRow, User):
                n = (
                    await s.execute(
                        select(func.count()).select_from(model).where(
                            model.tenant_id == tenant_id
                        )
                    )
                ).scalar()
                assert n == 0, f"{model.__name__} not erased ({n} left)"
            t = (
                await s.execute(select(Tenant).where(Tenant.id == tenant_id))
            ).scalars().first()
            assert t is None

    anyio.from_thread.run if False else None
    anyio.run(_check)


def test_erase_cross_tenant_forbidden(owner_auth):
    client, headers, _ = owner_auth
    r = client.delete("/api/admin/tenants/some-other-tenant/data", headers=headers)
    assert r.status_code == 403
    assert "own tenant" in r.json()["error"]["message"]


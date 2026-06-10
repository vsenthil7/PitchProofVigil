"""Tests for the idempotency store and the dataset endpoint replay protection."""
from __future__ import annotations

from app.idempotency import IdempotencyStore


async def test_store_record_and_get(db, tenant_id):
    async with db.session() as s:
        store = IdempotencyStore(s, tenant_id)
        assert await store.get("k1") is None
        await store.record("k1", "POST", "/api/datasets", 201, {"id": "x"})
    async with db.session() as s:
        store = IdempotencyStore(s, tenant_id)
        row = await store.get("k1")
        assert row is not None
        assert row.response_body == {"id": "x"}
        assert row.response_code == 201


async def test_store_tenant_isolation(db, tenant_id):
    async with db.session() as s:
        await IdempotencyStore(s, tenant_id).record("k1", "POST", "/x", 201, {})
    async with db.session() as s:
        assert await IdempotencyStore(s, "other").get("k1") is None


def test_dataset_idempotent_create(owner_auth):
    client, headers, _ = owner_auth
    h = {**headers, "Idempotency-Key": "abc-123"}
    r1 = client.post("/api/datasets", headers=h, json={"name": "d1", "examples": [{"text": "x"}]})
    assert r1.status_code == 201
    # Replay with same key → same response, NO 409 (would happen without idempotency).
    r2 = client.post("/api/datasets", headers=h, json={"name": "d1", "examples": [{"text": "x"}]})
    assert r2.status_code == 201
    assert r2.json()["id"] == r1.json()["id"]
    # Only one dataset actually created.
    assert len(client.get("/api/datasets", headers=headers).json()) == 1


def test_dataset_without_key_still_conflicts(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/datasets", headers=headers, json={"name": "d2"})
    # No idempotency key → second create is a real 409.
    r = client.post("/api/datasets", headers=headers, json={"name": "d2"})
    assert r.status_code == 409

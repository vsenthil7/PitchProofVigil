"""Admin router: health, readiness, and Prometheus metrics."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import get_db, get_metrics_dep
from app.observability.health import HealthService

router = APIRouter(tags=["admin"])


@router.get("/health")
async def health() -> dict:
    return HealthService.liveness()


@router.get("/ready")
async def ready(request: Request) -> dict:
    hs = HealthService(get_db(request))
    report = await hs.readiness()
    return report.as_dict()


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    data, content_type = get_metrics_dep(request).render()
    return Response(content=data, media_type=content_type)


@router.get("/api/security/status")
async def security_status(request: Request) -> dict:
    """Report encryption posture (no secrets, just config health)."""
    from app.crypto import KeyProvider

    provider = KeyProvider(request.app.state.settings)
    return {
        "encryption_at_rest": True,
        "key_ring_size": provider.key_count,
        "using_ephemeral_dev_key": provider.is_ephemeral,
        "rotation_supported": True,
    }

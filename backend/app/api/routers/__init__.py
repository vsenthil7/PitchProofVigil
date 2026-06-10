"""API routers, one module per domain.

Each module exposes a ``router`` (APIRouter). ``all_routers`` is the ordered
list the app factory includes.
"""
from app.api.routers.admin import router as admin_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.auth import router as auth_router
from app.api.routers.datasets import router as dataset_router
from app.api.routers.evaluation import router as eval_router
from app.api.routers.experiments import router as experiments_router
from app.api.routers.gate import router as gate_router
from app.api.routers.ops import router as ops_router
from app.api.routers.policies import router as policy_router
from app.api.routers.compliance import router as compliance_router
from app.api.routers.sso import router as sso_router

all_routers = [
    auth_router,
    eval_router,
    gate_router,
    policy_router,
    dataset_router,
    experiments_router,
    ops_router,
    analytics_router,
    admin_router,
    sso_router,
    compliance_router,
]

__all__ = ["all_routers"]

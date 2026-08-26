from backend.app.routers.auth import router as auth_router
from backend.app.routers.support import router as support_router
from backend.app.routers.finance import router as finance_router
from backend.app.routers.escalations import router as escalations_router
from backend.app.routers.reconciliation import router as reconciliation_router
from backend.app.routers.metrics import router as metrics_router
from backend.app.routers.partners import router as partners_router

__all__ = [
    "auth_router",
    "support_router",
    "finance_router",
    "escalations_router",
    "reconciliation_router",
    "metrics_router",
    "partners_router",
]

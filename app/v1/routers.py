from fastapi import FastAPI
from app.v1.auth.routes import router as auth_router
from app.v1.users.routes import router as users_router
from app.v1.cameras.routes import router as cameras_router
from app.v1.zones.routes import router as zones_router
from app.v1.detections.routes import router as detections_router
from app.v1.incidents.routes import router as incidents_router
from app.v1.notifications.routes import router as notifications_router
from app.v1.dashboard.routes import router as dashboard_router


def configure_app(app: FastAPI) -> None:
    """Register all v1 feature routers under /api/v1 prefix."""
    api_v1_prefix = "/api/v1"
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(users_router, prefix=api_v1_prefix)
    app.include_router(cameras_router, prefix=api_v1_prefix)
    app.include_router(zones_router, prefix=api_v1_prefix)
    app.include_router(detections_router, prefix=api_v1_prefix)
    app.include_router(incidents_router, prefix=api_v1_prefix)
    app.include_router(notifications_router, prefix=api_v1_prefix)
    app.include_router(dashboard_router, prefix=api_v1_prefix)

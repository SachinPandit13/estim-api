from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, traceback
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_pagination import add_pagination

from app.v1.routers import configure_app
from app.db.session import (
    get_pool_status,
    check_and_cleanup_pool,
)

from contextlib import asynccontextmanager

from collections import defaultdict
from app.core.logging_config import setup_logger

from app.db.config import settings
from app.core.request_timing import (
    ApiAuditHandlerStartMiddleware,
    ApiAuditMiddleware,
    install_timing_hooks,
)

logger = setup_logger(__name__)

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request failed: {request.url.path}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JSONResponse(status_code=500, content={"detail": str(e)})


class DatabasePoolMonitoringMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.request_counts = defaultdict(list)
        self.rate_limit_window = 60  # 1 minute
        self.max_requests_per_window = (
            30  # Increased to 30 requests per minute per endpoint
        )

    async def dispatch(self, request: Request, call_next):
        # Check and cleanup pool before request if needed
        cleanup_performed = check_and_cleanup_pool()
        if cleanup_performed:
            logger.warning(
                "Emergency pool cleanup performed before %s %s",
                request.method,
                request.url.path,
            )

        # Log pool status before request
        pool_status = get_pool_status()
        if pool_status:
            checked_out = pool_status.get("checked_out", 0)
            pool_size = pool_status.get("size", 0)
            if checked_out > pool_size * 0.8:  # More than 80% of base pool
                logger.warning(
                    f"High DB pool usage: {checked_out}/{pool_size} connections in use"
                )

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log pool status on error
            pool_status = get_pool_status()
            if pool_status:
                logger.error(f"DB pool status during error: {pool_status}")
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}"
            )
            # Try to cleanup pool on error
            check_and_cleanup_pool()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.v1.ai.executor import start_executor, stop_executor
    from app.v1.ai.worker import worker_manager
    from app.v1.ai.models.registry import model_registry
    from app.v1.ai.evidence import ensure_snapshots_dir

    ensure_snapshots_dir()
    start_executor()
    try:
        model_registry.ensure_person()
    except Exception as exc:
        logger.warning("Person model preload skipped: %s", exc)
    try:
        worker_manager.start_all_enabled()
    except Exception as exc:
        logger.warning("RTSP workers start skipped: %s", exc)
    yield
    worker_manager.stop_all()
    stop_executor()


app = FastAPI(lifespan=lifespan)

# Serve evidence snapshots and uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# add middlewares
# First added is innermost. Audit handler-start sits next to the app;
# ApiAuditMiddleware wraps auth/pool so Network/other includes JWT + pool checks.
# CORS stays last (outermost) so OPTIONS preflights are handled first.

app.add_middleware(ApiAuditHandlerStartMiddleware)
app.add_middleware(ErrorLoggingMiddleware)
app.add_middleware(DatabasePoolMonitoringMiddleware)
# app.add_middleware(LogtoAuthMiddleware)

# rate limit middleware
# app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ApiAuditMiddleware)

# Configure CORS — must be added last so it is outermost and handles OPTIONS preflights first
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_timing_hooks()

# Templates
# templates = Jinja2Templates(directory="app/templates")

# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

add_pagination(app)

configure_app(app)


@app.get("/health/db-pool")
async def db_pool_status():
    """Check database connection pool status"""
    status = get_pool_status()
    if status:
        return {
            "status": "healthy",
            "pool_info": status,
            "message": "Database pool is operational",
        }
    else:
        return {"status": "error", "message": "Unable to get pool status"}


@app.get("/health/ai")
async def ai_health():
    from app.v1.ai.health import get_ai_health

    return get_ai_health()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

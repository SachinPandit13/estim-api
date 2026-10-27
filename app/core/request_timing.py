"""Request-scoped API latency audit: DB, external HTTP, serialization, Python, network."""

from __future__ import annotations

import hashlib
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_timing_ctx: ContextVar[Optional["RequestTiming"]] = ContextVar(
    "api_audit_timing", default=None
)
_serialization_depth: ContextVar[int] = ContextVar(
    "api_audit_serialization_depth", default=0
)
_hooks_installed = False

SKIP_EXACT_PATHS = frozenset({"/", "/questions", "/interview"})
SKIP_PREFIXES = ("/health", "/app/static")

AUDIT_LOGGER_NAME = "api.audit"
DB_DETAIL_LIMIT = 20


def _query_fingerprint(statement: str) -> str:
    """Return a stable, parameter-free query label for audit logs."""
    normalized = " ".join(statement.split())
    operation_match = re.match(r"([A-Za-z]+)", normalized)
    operation = operation_match.group(1).upper() if operation_match else "SQL"

    if operation == "UPDATE":
        table_pattern = r"^UPDATE\s+([A-Za-z0-9_.\"]+)"
    elif operation == "INSERT":
        table_pattern = r"^INSERT\s+INTO\s+([A-Za-z0-9_.\"]+)"
    elif operation == "DELETE":
        table_pattern = r"^DELETE\s+FROM\s+([A-Za-z0-9_.\"]+)"
    else:
        table_pattern = r"\bFROM\s+([A-Za-z0-9_.\"]+)"

    table_match = re.search(table_pattern, normalized, flags=re.IGNORECASE)
    table = table_match.group(1).replace('"', "") if table_match else "unknown"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{operation} {table}#{digest}"


@dataclass
class RequestTiming:
    t0: float
    handler_start: Optional[float] = None
    db_ms: float = 0.0
    external_ms: float = 0.0
    serialization_ms: float = 0.0
    pre_handler_db_ms: float = 0.0
    pre_handler_external_ms: float = 0.0
    pre_handler_serialization_ms: float = 0.0
    db_count: int = 0
    external_count: int = 0
    db_details: list[tuple[str, float]] = field(default_factory=list)


def _current() -> Optional[RequestTiming]:
    return _timing_ctx.get()


def start_request() -> RequestTiming:
    timing = RequestTiming(t0=time.perf_counter())
    _timing_ctx.set(timing)
    return timing


def mark_handler_start() -> None:
    timing = _current()
    if timing is not None and timing.handler_start is None:
        timing.handler_start = time.perf_counter()


def finish_request() -> None:
    _timing_ctx.set(None)


def _started_before_handler(timing: RequestTiming, started_at: float) -> bool:
    return timing.handler_start is None or started_at < timing.handler_start


def add_db(ms: float, statement: str, started_at: float) -> None:
    timing = _current()
    if timing is None:
        return
    timing.db_ms += ms
    timing.db_count += 1
    if _started_before_handler(timing, started_at):
        timing.pre_handler_db_ms += ms
    if len(timing.db_details) < DB_DETAIL_LIMIT:
        timing.db_details.append((_query_fingerprint(statement), ms))


def add_external(ms: float, started_at: float) -> None:
    timing = _current()
    if timing is None:
        return
    timing.external_ms += ms
    timing.external_count += 1
    if _started_before_handler(timing, started_at):
        timing.pre_handler_external_ms += ms


def add_serialization(ms: float, started_at: float) -> None:
    timing = _current()
    if timing is None:
        return
    timing.serialization_ms += ms
    if _started_before_handler(timing, started_at):
        timing.pre_handler_serialization_ms += ms


def should_skip_audit(request: Request) -> bool:
    from app.db.config import settings

    if not settings.AUDIT_ONLY_LOGS:
        return True
    if request.method == "OPTIONS":
        return True
    path = request.url.path
    if path in SKIP_EXACT_PATHS:
        return True
    return any(
        path == prefix or path.startswith(prefix + "/") for prefix in SKIP_PREFIXES
    )


def _breakdown(timing: RequestTiming) -> dict:
    now = time.perf_counter()
    total_ms = max(0.0, (now - timing.t0) * 1000)
    handler_start = timing.handler_start or now
    pre_handler_ms = max(0.0, (handler_start - timing.t0) * 1000)
    handler_ms = max(0.0, (now - handler_start) * 1000)

    pre_handler_accounted = (
        timing.pre_handler_db_ms
        + timing.pre_handler_external_ms
        + timing.pre_handler_serialization_ms
    )
    handler_accounted = (
        timing.db_ms
        - timing.pre_handler_db_ms
        + timing.external_ms
        - timing.pre_handler_external_ms
        + timing.serialization_ms
        - timing.pre_handler_serialization_ms
    )

    # DB/external work performed by middleware is subtracted from the
    # pre-handler residual so it is not also reported as Network/other.
    network_ms = max(0.0, pre_handler_ms - pre_handler_accounted)
    python_ms = max(0.0, handler_ms - handler_accounted)
    return {
        "total_ms": total_ms,
        "db_ms": timing.db_ms,
        "external_ms": timing.external_ms,
        "python_ms": python_ms,
        "serialization_ms": timing.serialization_ms,
        "network_ms": network_ms,
    }


def emit_audit_log(
    method: str, path: str, status_code: int, timing: RequestTiming
) -> None:
    from app.core.logging_config import setup_logger
    from app.db.config import settings

    if not settings.AUDIT_ONLY_LOGS:
        return

    buckets = _breakdown(timing)
    db_details = "; ".join(
        f"{fingerprint} {elapsed_ms:.1f} ms"
        for fingerprint, elapsed_ms in timing.db_details
    )
    if timing.db_count > len(timing.db_details):
        db_details = (
            f"{db_details}; " if db_details else ""
        ) + f"{timing.db_count - len(timing.db_details)} more"
    if not db_details:
        db_details = "none"

    logger = setup_logger(AUDIT_LOGGER_NAME)
    logger.info(
        "[API AUDIT] %s %s -> %s\n"
        "  Total API latency:    %7.1f ms\n"
        "  DB query:             %7.1f ms (%d statements)\n"
        "  DB statements:        %s\n"
        "  External API:         %7.1f ms\n"
        "  Python processing:    %7.1f ms\n"
        "  Serialization:        %7.1f ms\n"
        "  Network/other:        %7.1f ms",
        method,
        path,
        status_code,
        buckets["total_ms"],
        buckets["db_ms"],
        timing.db_count,
        db_details,
        buckets["external_ms"],
        buckets["python_ms"],
        buckets["serialization_ms"],
        buckets["network_ms"],
    )


class ApiAuditHandlerStartMiddleware(BaseHTTPMiddleware):
    """Innermost: marks when the request reaches the route handler."""

    async def dispatch(self, request: Request, call_next):
        from app.db.config import settings

        if not settings.AUDIT_ONLY_LOGS:
            return await call_next(request)
        mark_handler_start()
        return await call_next(request)


class ApiAuditMiddleware(BaseHTTPMiddleware):
    """Just inside CORS: measures full request and logs the 6-bucket breakdown."""

    async def dispatch(self, request: Request, call_next):
        if should_skip_audit(request):
            return await call_next(request)

        timing = start_request()
        try:
            response = await call_next(request)
            buckets = _breakdown(timing)
            try:
                response.headers["X-Process-Time"] = f"{buckets['total_ms']:.1f}"
            except (TypeError, AttributeError, KeyError):
                pass
            emit_audit_log(
                request.method, request.url.path, response.status_code, timing
            )
            return response
        except Exception:
            emit_audit_log(request.method, request.url.path, 500, timing)
            raise
        finally:
            finish_request()


def install_timing_hooks() -> None:
    """Patch SQLAlchemy, httpx, requests, botocore, urllib, and JSON serialization. Idempotent."""
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True
    _install_sqlalchemy_hooks()
    _install_httpx_hooks()
    _install_requests_hooks()
    _install_botocore_hooks()
    _install_urllib_hooks()
    _install_serialization_hooks()


def _install_sqlalchemy_hooks() -> None:
    from sqlalchemy import event

    from app.db.session import engine

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info["api_audit_query_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        start = conn.info.pop("api_audit_query_start", None)
        if start is not None:
            add_db(
                (time.perf_counter() - start) * 1000,
                statement,
                start,
            )

    @event.listens_for(engine, "handle_error")
    def _handle_cursor_error(exception_context):
        conn = exception_context.connection
        if conn is None:
            return
        start = conn.info.pop("api_audit_query_start", None)
        if start is not None:
            add_db(
                (time.perf_counter() - start) * 1000,
                exception_context.statement or "SQL",
                start,
            )


def _install_httpx_hooks() -> None:
    try:
        import httpx
    except ImportError:
        return

    _orig_async_send = httpx.AsyncClient.send
    _orig_sync_send = httpx.Client.send

    async def _timed_async_send(self, request, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return await _orig_async_send(self, request, *args, **kwargs)
        finally:
            add_external((time.perf_counter() - t0) * 1000, t0)

    def _timed_sync_send(self, request, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return _orig_sync_send(self, request, *args, **kwargs)
        finally:
            add_external((time.perf_counter() - t0) * 1000, t0)

    httpx.AsyncClient.send = _timed_async_send  # type: ignore[method-assign]
    httpx.Client.send = _timed_sync_send  # type: ignore[method-assign]


def _install_requests_hooks() -> None:
    try:
        import requests
    except ImportError:
        return

    _orig_send = requests.Session.send

    def _timed_send(self, request, **kwargs):
        t0 = time.perf_counter()
        try:
            return _orig_send(self, request, **kwargs)
        finally:
            add_external((time.perf_counter() - t0) * 1000, t0)

    requests.Session.send = _timed_send  # type: ignore[method-assign]


def _install_botocore_hooks() -> None:
    try:
        from botocore.httpsession import URLLib3Session
    except ImportError:
        return

    _orig_send = URLLib3Session.send

    def _timed_send(self, request, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return _orig_send(self, request, *args, **kwargs)
        finally:
            add_external((time.perf_counter() - t0) * 1000, t0)

    URLLib3Session.send = _timed_send  # type: ignore[method-assign]


def _install_urllib_hooks() -> None:
    import urllib.request

    _orig_urlopen = urllib.request.urlopen

    def _timed_urlopen(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return _orig_urlopen(*args, **kwargs)
        finally:
            add_external((time.perf_counter() - t0) * 1000, t0)

    urllib.request.urlopen = _timed_urlopen  # type: ignore[assignment]


def _install_serialization_hooks() -> None:
    import fastapi.encoders
    import fastapi.routing
    from starlette.responses import JSONResponse as StarletteJSONResponse

    _orig_encoder = fastapi.encoders.jsonable_encoder

    def _timed_encoder(*args, **kwargs):
        depth = _serialization_depth.get()
        token = _serialization_depth.set(depth + 1)
        t0 = time.perf_counter()
        try:
            return _orig_encoder(*args, **kwargs)
        finally:
            _serialization_depth.reset(token)
            if depth == 0:
                add_serialization((time.perf_counter() - t0) * 1000, t0)

    fastapi.encoders.jsonable_encoder = _timed_encoder
    fastapi.routing.jsonable_encoder = _timed_encoder

    _orig_render = StarletteJSONResponse.render

    def _timed_render(self, content):
        t0 = time.perf_counter()
        try:
            return _orig_render(self, content)
        finally:
            add_serialization((time.perf_counter() - t0) * 1000, t0)

    StarletteJSONResponse.render = _timed_render  # type: ignore[method-assign]

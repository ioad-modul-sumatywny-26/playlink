"""Structured JSON logs, request ids and Prometheus metrics.

Logs go to stdout as one JSON object per line (``_msg`` / ``_time`` are the
fields VictoriaLogs reads). ``log_event`` records business events such as room
creation and also counts them for the dashboards.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from config import REGION

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("playlink")

HTTP_REQUESTS = Counter(
    "playlink_http_requests_total",
    "HTTP requests",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "playlink_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
WS_CONNECTIONS = Gauge("playlink_ws_connections", "Open WebSockets", ["kind"])
EVENTS = Counter("playlink_events_total", "Business events", ["event"])


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            **getattr(record, "fields", {}),
            "_time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "_msg": record.getMessage(),
            "level": record.levelname,
            "logger": record.name,
            "region": REGION,
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
    logging.getLogger("uvicorn.access").disabled = True


def short_address(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}"


def log_event(event: str, **fields: object) -> None:
    EVENTS.labels(event).inc()
    logger.info(event, extra={"fields": {"event": event, **fields}})


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 64 else uuid.uuid4().hex[:16]
        request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                "unhandled exception",
                extra={"fields": {"path": request.url.path}},
            )
            raise
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            if route != "/metrics":
                HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
                HTTP_DURATION.labels(request.method, route).observe(
                    time.perf_counter() - started
                )


router = APIRouter(include_in_schema=False)


@router.get("/metrics")
def metrics(request: Request):
    """Scraped on the compose network only; requests via Cloudflare get a 404."""
    if request.headers.get("cf-connecting-ip"):
        raise HTTPException(status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

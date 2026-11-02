"""JSON logs, request ids and Prometheus metrics."""

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability import (
    JsonFormatter,
    ObservabilityMiddleware,
    log_event,
    short_address,
)
from observability import logger as observability_logger


def test_metrics_exposes_http_and_event_counters(client: TestClient):
    client.get("/healthz")
    log_event("room_created", room="r1")
    body = client.get("/metrics").text
    assert (
        'playlink_http_requests_total{method="GET",route="/healthz",status="200"}'
        in body
    )
    assert 'playlink_events_total{event="room_created"}' in body


def test_metrics_hidden_behind_cloudflare(client: TestClient):
    response = client.get("/metrics", headers={"CF-Connecting-IP": "203.0.113.7"})
    assert response.status_code == 404


def test_request_id_is_generated_and_echoed(client: TestClient):
    generated = client.get("/healthz").headers["x-request-id"]
    assert len(generated) == 16
    echoed = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"


def test_json_formatter_outputs_victorialogs_fields():
    record = logging.LogRecord(
        "playlink", logging.INFO, "", 0, "room_created", (), None
    )
    record.fields = {"event": "room_created", "room": "r1"}
    entry = json.loads(JsonFormatter().format(record))
    assert entry["_msg"] == "room_created"
    assert entry["level"] == "INFO"
    assert entry["room"] == "r1"
    assert {"_time", "region", "request_id"} <= entry.keys()


def test_short_address():
    assert short_address("0x1234567890abcdef1234567890abcdef12345678") == "0x1234…5678"


def test_unhandled_exception_is_logged_with_request_id_and_counted():
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append
    # Alembic runs in other tests and its fileConfig() disables existing loggers.
    observability_logger.disabled = False
    observability_logger.addHandler(handler)
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/boom")
    finally:
        observability_logger.removeHandler(handler)

    assert response.status_code == 500
    assert [r.fields["path"] for r in records if r.exc_info] == ["/boom"]

"""Health and readiness probe tests."""

from fastapi.testclient import TestClient

from main import app


def test_healthz_returns_region_and_no_store(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["region"] == "local"
    assert response.headers["cache-control"] == "no-store"


def test_readyz_checks_database(client: TestClient):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_healthz_is_not_rate_limited(client: TestClient):
    app.state.limiter.enabled = True
    try:
        for _ in range(100):
            assert client.get("/healthz").status_code == 200
    finally:
        app.state.limiter.enabled = False

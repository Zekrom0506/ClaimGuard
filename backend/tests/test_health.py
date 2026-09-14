"""Tests for the hello-world, /health and /ready endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import health_checks

client = TestClient(app)


def test_root_returns_message() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "running" in response.json()["message"]


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_dependencies_are_up(monkeypatch) -> None:
    # Replace the real checks so the test does not need a running database.
    monkeypatch.setattr(health_checks, "is_database_reachable", lambda: True)
    monkeypatch.setattr(health_checks, "is_redis_reachable", lambda: True)

    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"database": True, "redis": True}


def test_ready_returns_503_when_database_is_down(monkeypatch) -> None:
    monkeypatch.setattr(health_checks, "is_database_reachable", lambda: False)
    monkeypatch.setattr(health_checks, "is_redis_reachable", lambda: True)

    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["database"] is False

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_internal_mode_blocks_anonymous_public_api(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_ACCESS_REQUIRED", True)
    client = TestClient(app)

    response = client.get("/api/v1/search/stats")

    assert response.status_code == 401
    assert "ovlašćenim korisnicima" in response.json()["detail"]


def test_internal_mode_keeps_health_check_public(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_ACCESS_REQUIRED", True)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

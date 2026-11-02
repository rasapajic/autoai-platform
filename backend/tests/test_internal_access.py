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


def test_rejected_session_is_readable_by_allowed_browser_origin(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_ACCESS_REQUIRED", True)
    origin = settings.get_cors_origins()[0]
    client = TestClient(app)

    for authorization in (None, "Bearer expired-or-invalid"):
        headers = {"Origin": origin}
        if authorization:
            headers["Authorization"] = authorization
        response = client.get("/api/v1/search/makes", headers=headers)

        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["www-authenticate"] == "Bearer"


def test_rejected_session_does_not_allow_untrusted_browser_origin(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_ACCESS_REQUIRED", True)
    response = TestClient(app).get(
        "/api/v1/search/makes", headers={"Origin": "https://untrusted.example"}
    )

    assert response.status_code == 401
    assert "access-control-allow-origin" not in response.headers


from fastapi.testclient import TestClient


def test_backend_app_imports():
    from app.main import app

    assert app.title == "AutoAI Platform API"


def test_health_endpoint_works():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_route_imports():
    from app.api import users

    assert users.router is not None


def test_search_route_imports():
    from app.api import search

    assert search.router is not None

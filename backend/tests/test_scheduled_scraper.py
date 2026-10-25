import pytest

from scripts import scraper


def test_cron_requires_backend_url(monkeypatch):
    monkeypatch.delenv("AUTOAI_BACKEND_URL", raising=False)
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")

    with pytest.raises(RuntimeError, match="AUTOAI_BACKEND_URL is required"):
        scraper.main()


def test_cron_calls_guarded_endpoint_and_validates_all_sources(monkeypatch):
    monkeypatch.setenv("AUTOAI_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")
    monkeypatch.setenv("AUTOAI_CRON_MAX_PAGES", "3")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ok",
                "active_after": 5,
                "new": 2,
                "updated": 3,
                "inactive_after": 1,
                "by_source": {
                    source: {"accepted": 1}
                    for source in scraper.REQUIRED_SOURCES
                },
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(scraper.requests, "post", fake_post)

    assert scraper.main() == 0
    assert captured["url"] == (
        "https://backend.example.test/api/v1/internal/m01/scheduled-refresh"
    )
    assert captured["params"] == {
        "confirm": scraper.REFRESH_CONFIRMATION,
        "max_pages": 3,
    }
    assert captured["headers"] == {
        "X-AutoAI-Admin-Secret": "test-secret",
    }
    assert captured["timeout"] == (30, 1800)


def test_cron_rejects_partial_source_response(monkeypatch):
    monkeypatch.setenv("AUTOAI_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ok",
                "active_after": 4,
                "by_source": {
                    source: {"accepted": 1}
                    for source in scraper.REQUIRED_SOURCES
                    if source != "kleinanzeigen"
                },
            }

    monkeypatch.setattr(scraper.requests, "post", lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(RuntimeError, match="invalid sources: kleinanzeigen"):
        scraper.main()

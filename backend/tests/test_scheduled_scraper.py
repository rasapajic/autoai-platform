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


def test_collection_cron_runs_every_bounded_partition_and_continues_after_one_failure(monkeypatch):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "growth")
    seen = []

    class Response:
        def __init__(self, partition):
            self.partition = partition

        def raise_for_status(self):
            if self.partition.key == "willhaben:category:limousine":
                raise RuntimeError("source blocked")

        def json(self):
            return {"status": "ok", "new": 1, "updated": 0, "start_page": 4, "end_page": 6, "next_page": 7,
                    "by_source": {self.partition.source: {"accepted": 1, "unresolved_make": 0}}}

    def post(url, **kwargs):
        key = kwargs["params"]["partition_key"]
        seen.append(key)
        assert kwargs["params"]["max_pages"] == 3
        assert kwargs["params"]["scan_mode"] == "growth"
        assert kwargs["headers"] == {"X-AutoAI-Admin-Secret": "test-secret"}
        return Response(next(part for part in scraper.COLLECTION_PLAN if part.key == key))

    monkeypatch.setattr(scraper.requests, "post", post)
    assert scraper._collect_windows("https://backend.example.test", "test-secret", 3) == 0
    assert len(seen) == 16
    assert len(set(seen)) == 16


def test_collection_cron_rejects_invalid_mode_before_any_request(monkeypatch):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "unbounded")
    with pytest.raises(RuntimeError, match="must be auto, head or growth"):
        scraper._collect_windows("https://backend.example.test", "test-secret", 3)


def test_cursor_flag_uses_collection_plan_without_legacy_full_refresh(monkeypatch):
    monkeypatch.setenv("AUTOAI_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")
    monkeypatch.setenv("AUTOAI_CATALOG_CURSORS_ENABLED", "true")
    monkeypatch.setattr(scraper, "_collect_windows", lambda base, secret, pages: 0)
    monkeypatch.setattr(scraper.requests, "post", lambda *_args, **_kwargs: pytest.fail("legacy refresh should not run"))
    assert scraper.main() == 0

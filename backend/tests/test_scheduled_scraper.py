import pytest
from types import SimpleNamespace

from scripts import scraper


@pytest.mark.parametrize("hour,minute,expected", [(2, 0, "head"), (2, 14, "head"), (2, 15, "growth"), (2, 30, "growth"), (8, 0, "growth"), (14, 45, "growth"), (20, 0, "growth")])
def test_quarter_hour_modes_keep_one_daily_head_window(monkeypatch, hour, minute, expected):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "auto")
    monkeypatch.setattr(scraper, "datetime", SimpleNamespace(now=lambda _tz: SimpleNamespace(hour=hour, minute=minute)))
    seen = []

    def post(_url, **kwargs):
        params = kwargs["params"]
        seen.append(params["scan_mode"])
        source = next(part.source for part in scraper.COLLECTION_PLAN if part.key == params["partition_key"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "status": "ok", "start_page": 1, "end_page": 3, "next_page": 4,
            "by_source": {source: {"accepted": 1}},
        })

    monkeypatch.setattr(scraper.requests, "post", post)
    assert scraper._collect_windows("https://backend.example.test", "test-secret", 3) == 0
    assert seen == [expected] * (16 if expected == "head" else 23)


def test_cron_recognizes_persisted_pauses_without_requiring_new_rows(monkeypatch, caplog):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "growth")
    seen = []
    def post(_url, **kwargs):
        seen.append(kwargs["params"]["partition_key"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"status": "paused", "reason": "source_http_429", "retry_after": "tomorrow"})
    monkeypatch.setattr(scraper.requests, "post", post)
    assert scraper._collect_windows("https://backend.example.test", "test-secret", 3) == 0
    assert len(seen) == 16


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
    assert len(seen) == 23
    assert len(set(seen)) == 16
    assert seen[0] == "autoscout24:D"
    assert seen.count("autoscout24:D") == 8


@pytest.mark.parametrize("outcome", ["paused", "failed"])
def test_german_extra_windows_stop_after_pause_or_failure(monkeypatch, outcome):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "growth")
    seen = []
    def post(_url, **kwargs):
        key = kwargs["params"]["partition_key"]
        seen.append(key)
        def check():
            if key == "autoscout24:D" and outcome == "failed":
                raise RuntimeError("source error")
        def result():
            if key == "autoscout24:D":
                return {"status": "paused", "reason": "identity_quality"}
            source = next(part.source for part in scraper.COLLECTION_PLAN if part.key == key)
            return {"status": "ok", "start_page": 4, "end_page": 6, "next_page": 7,
                    "by_source": {source: {"accepted": 1}}}
        return SimpleNamespace(raise_for_status=check, json=result)
    monkeypatch.setattr(scraper.requests, "post", post)
    assert scraper._collect_windows("https://backend.example.test", "test-secret", 3) == 0
    assert seen.count("autoscout24:D") == 1
    assert len(seen) == 16


def test_german_windows_reuse_the_backend_cursor_and_reach_next_pages(monkeypatch):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "growth")
    starts = []
    def post(_url, **kwargs):
        params = kwargs["params"]
        assert "start_page" not in params  # Only the backend owns the checkpoint.
        key = params["partition_key"]
        source = next(part.source for part in scraper.COLLECTION_PLAN if part.key == key)
        if key == "autoscout24:D":
            start = 184 + len(starts) * 3
            starts.append(start)
        else:
            start = 1
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "status": "ok", "start_page": start, "end_page": start + 2, "next_page": start + 3,
            "by_source": {source: {"accepted": 60}}})
    monkeypatch.setattr(scraper.requests, "post", post)
    assert scraper._collect_windows("https://backend.example.test", "test-secret", 3) == 0
    assert starts == [184, 187, 190, 193, 196, 199, 202, 205]


def test_collection_cron_rejects_invalid_mode_before_any_request(monkeypatch):
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "unbounded")
    with pytest.raises(RuntimeError, match="must be auto, head or growth"):
        scraper._collect_windows("https://backend.example.test", "test-secret", 3)


def test_cursor_flag_uses_collection_plan_without_legacy_full_refresh(monkeypatch):
    monkeypatch.setenv("AUTOAI_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")
    monkeypatch.setenv("AUTOAI_CATALOG_CURSORS_ENABLED", "true")
    monkeypatch.setattr(scraper, "_collect_windows", lambda base, secret, pages: 0)
    monkeypatch.setattr(scraper, "_repair_jaguar_models", lambda base, secret: None)
    monkeypatch.setattr(scraper.requests, "post", lambda *_args, **_kwargs: pytest.fail("legacy refresh should not run"))
    assert scraper.main() == 0


def test_model_repair_walks_bounded_keyset_batches(monkeypatch):
    seen = []
    def post(url, **kwargs):
        assert url.endswith("/repair-jaguar-models")
        assert kwargs["params"]["dry_run"] == "false"
        assert kwargs["headers"] == {"X-AutoAI-Admin-Secret": "test-secret"}
        seen.append(kwargs["params"].get("after_id"))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "status": "ok", "dry_run": False, "scanned": 500, "changed": 1,
            "next_after_id": "next-id" if len(seen) == 1 else None})
    monkeypatch.setattr(scraper.requests, "post", post)
    scraper._repair_jaguar_models("https://backend.example.test", "test-secret")
    assert seen == [None, "next-id"]


def test_model_repair_failure_does_not_stop_collection(monkeypatch):
    monkeypatch.setenv("AUTOAI_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("AUTOAI_ADMIN_SECRET", "test-secret")
    monkeypatch.setenv("AUTOAI_CATALOG_CURSORS_ENABLED", "true")
    monkeypatch.setattr(scraper, "_repair_jaguar_models", lambda *_: (_ for _ in ()).throw(RuntimeError("maintenance failed")))
    calls = []
    monkeypatch.setattr(scraper, "_collect_windows", lambda *args: calls.append(args) or 0)
    assert scraper.main() == 0
    assert len(calls) == 1

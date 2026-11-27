import asyncio
import copy
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.api.m01_listings as catalog
from scripts import scraper
from app.core.catalog_plan import PARTITION_BY_KEY, page_window
from app.core.source_policy import SOURCE_REGISTRY


@pytest.fixture
def collection(monkeypatch):
    state = {"cursor": None, "pauses": {}, "rows": [], "sessions": [], "fetches": [], "locked": True, "source_locked": True, "database_bytes": 1000, "commit_fails": False}

    class Session:
        def __init__(self):
            self.cursor = copy.deepcopy(state["cursor"])
            self.pauses = copy.deepcopy(state["pauses"])
            self.rows = []
            self.closed = self.rolled_back = False
            state["sessions"].append(self)

        def execute(self, statement, *_args, **_kwargs):
            if getattr(getattr(statement, "table", None), "name", None) == "catalog_collection_pauses":
                params = statement.compile().params
                self.pauses[params["pause_key"]] = SimpleNamespace(pause_key=params["pause_key"], reason=params["reason"], retry_after=params["retry_after"])
                return None
            if "3705" in str(statement):
                return SimpleNamespace(scalar=lambda: state["source_locked"])
            return SimpleNamespace(scalar=lambda: state["database_bytes"] if "pg_database_size" in str(statement) else state["locked"])

        def get(self, model, key):
            if model is catalog.CatalogCollectionPause:
                return self.pauses.get(key)
            return self.cursor

        def add(self, row):
            self.cursor = row

        def commit(self):
            if state["commit_fails"]:
                raise RuntimeError("commit failed")
            state["cursor"] = copy.deepcopy(self.cursor)
            state["pauses"] = copy.deepcopy(self.pauses)
            state["rows"].extend(self.rows)

        def rollback(self):
            self.rolled_back = True
            self.cursor = copy.deepcopy(state["cursor"])
            self.pauses = copy.deepcopy(state["pauses"])
            self.rows = []

        def close(self):
            self.closed = True

    async def fetch(source, max_pages, now, filters=None):
        state["fetches"].append((max_pages, filters.copy()))
        row = {"external_id": f"wh_page_{filters['start_page']}", "source": source.storage_source}
        return [row], {"accepted": 1, "unresolved_make": 0, "unresolved_model": 0}

    def apply(staged, db=None):
        assert db is state["sessions"][-1]
        db.rows.extend(next(iter(staged.values())))
        return {"new": 1, "updated": 0, "active_after": len(state["rows"]) + 1, "deactivated": 0}

    monkeypatch.setattr(catalog, "SessionLocal", Session)
    monkeypatch.setattr(catalog, "_fetch_source_batch", fetch)
    monkeypatch.setattr(catalog, "_apply_scheduled_catalog_refresh", apply)
    monkeypatch.setattr(catalog, "get_enabled_source", lambda key: SOURCE_REGISTRY[key])
    monkeypatch.setattr(catalog.settings, "AUTOAI_ADMIN_SECRET", "test-secret")
    return state


def run_window(mode="growth", partition="willhaben:category:limousine", max_pages=3):
    return asyncio.run(catalog.collect_window(partition_key=partition, confirm="COLLECT_INTERNAL_CATALOG_WINDOW", scan_mode=mode, max_pages=max_pages, x_autoai_admin_secret="test-secret"))


def test_growth_resumes_from_committed_checkpoint_across_sessions(collection):
    first = run_window()
    second = run_window()
    assert (first["start_page"], first["next_page"]) == (1, 4)
    assert (second["start_page"], second["next_page"]) == (4, 7)
    assert len(collection["rows"]) == 2
    assert len(collection["sessions"]) == 2
    assert all(session.closed for session in collection["sessions"])
    assert collection["fetches"][1][1] == {"category": "limousine", "start_page": 4, "strict_window": True}


def test_head_refresh_does_not_reset_growth_checkpoint(collection):
    run_window()
    result = run_window("head")
    assert result["start_page"] == 1
    assert result["next_page"] == 4


def test_failed_fetch_preserves_catalog_and_checkpoint(collection, monkeypatch):
    run_window()
    async def failed(*_args, **_kwargs):
        raise RuntimeError("source_http_403")
    monkeypatch.setattr(catalog, "_fetch_source_batch", failed)
    result = run_window()
    assert result["status"] == "paused" and result["reason"] == "source_http_403"
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1
    assert collection["sessions"][-1].rolled_back


def test_failed_commit_preserves_catalog_and_checkpoint(collection):
    run_window()
    collection["commit_fails"] = True
    with pytest.raises(RuntimeError, match="commit failed"):
        run_window()
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1


def test_partition_lock_rejects_overlap_without_fetching(collection):
    collection["locked"] = False
    with pytest.raises(HTTPException) as error:
        run_window()
    assert error.value.status_code == 409
    assert not collection["fetches"]
    assert collection["cursor"] is None


def test_repeated_page_fingerprint_cannot_advance_checkpoint(collection, monkeypatch):
    run_window()
    fingerprint = collection["cursor"].last_fingerprint
    async def repeated(*_args, **_kwargs):
        return [{"external_id": "wh_page_1", "source": "willhaben"}], {"accepted": 1, "unresolved_make": 0}
    monkeypatch.setattr(catalog, "_fetch_source_batch", repeated)
    result = run_window()
    assert result["status"] == "paused" and result["reason"] == "pagination_stalled"
    assert collection["cursor"].last_fingerprint == fingerprint
    assert collection["cursor"].next_page == 4


def test_low_identity_quality_cannot_advance_checkpoint(collection, monkeypatch):
    async def unknown(*_args, **_kwargs):
        return [{"external_id": "wh_unknown"}], {"accepted": 1, "unresolved_make": 1}
    monkeypatch.setattr(catalog, "_fetch_source_batch", unknown)
    result = run_window()
    assert result["status"] == "paused" and result["reason"] == "identity_quality"
    assert collection["cursor"] is None


def test_short_end_window_retries_one_page_without_skipping(collection, monkeypatch):
    run_window()
    async def short(source, max_pages, _now, filters):
        if max_pages == 3:
            raise RuntimeError("source_window_incomplete")
        return [{"external_id": "wh_last", "source": source.storage_source}], {"accepted": 1, "unresolved_make": 0}
    monkeypatch.setattr(catalog, "_fetch_source_batch", short)
    result = run_window()
    assert result["start_page"] == result["end_page"] == 4
    assert result["next_page"] == 5


def test_unknown_partition_never_opens_a_session(collection):
    with pytest.raises(HTTPException) as error:
        run_window(partition="willhaben:untrusted")
    assert error.value.status_code == 400
    assert not collection["sessions"]


def test_plan_is_bounded_and_partitions_are_distinct():
    assert len(PARTITION_BY_KEY) == 24
    assert set(part.source for part in PARTITION_BY_KEY.values()) == set(SOURCE_REGISTRY)
    assert list(page_window({"start_page": 7}, 3)) == [7, 8, 9]
    with pytest.raises(ValueError):
        page_window({"start_page": 0}, 3)


def test_german_price_partition_keeps_broad_query_pause_and_uses_fixed_filters(collection):
    pause_key = "partition:growth:autoscout24:D"
    collection["pauses"][pause_key] = SimpleNamespace(reason="empty_or_unrecognized_window",
        retry_after=datetime.now(timezone.utc) + timedelta(days=1))
    result = run_window(partition="autoscout24:D:price:5000-9999")
    assert result["status"] == "ok"
    assert pause_key in collection["pauses"]
    assert collection["fetches"] == [(3, {"country": "D", "min_price": 5000, "max_price": 9999,
                                           "start_page": 1, "strict_window": True})]


def test_source_refusal_still_blocks_german_price_partitions(collection):
    collection["pauses"]["source:autoscout24"] = SimpleNamespace(reason="source_http_429",
        retry_after=datetime.now(timezone.utc) + timedelta(days=1))
    result = run_window(partition="autoscout24:D:price:5000-9999")
    assert result["status"] == "paused" and result["reason"] == "source_http_429"
    assert not collection["fetches"]


def test_database_size_guard_stops_growth_before_fetching(collection):
    collection["database_bytes"] = 251 * 1024 * 1024
    with pytest.raises(HTTPException) as error:
        run_window()
    assert error.value.status_code == 507
    assert not collection["fetches"]


def test_wrong_secret_cannot_open_a_collection_session(collection):
    with pytest.raises(HTTPException) as error:
        asyncio.run(catalog.collect_window(partition_key="marktplaats:all", confirm="COLLECT_INTERNAL_CATALOG_WINDOW", scan_mode="growth", max_pages=3, x_autoai_admin_secret="wrong"))
    assert error.value.status_code == 403
    assert not collection["sessions"]


@pytest.mark.parametrize("status", [403, 429])
def test_source_refusal_persists_pause_across_sessions_and_partitions(collection, monkeypatch, status):
    run_window()
    async def refused(*_args, **_kwargs):
        collection["fetches"].append("refused")
        raise RuntimeError(f"source_http_{status}")
    monkeypatch.setattr(catalog, "_fetch_source_batch", refused)
    first = run_window()
    assert first["status"] == "paused" and first["reason"] == f"source_http_{status}"
    count = len(collection["fetches"])
    result = run_window(partition="willhaben:type:10")
    assert result["status"] == "paused"
    assert result["reason"] == f"source_http_{status}"
    assert len(collection["fetches"]) == count
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1
    assert collection["pauses"]["source:willhaben"].retry_after > datetime.now(timezone.utc) + timedelta(hours=23)


def test_expired_source_pause_allows_saved_page_to_resume(collection):
    run_window()
    collection["pauses"]["source:willhaben"] = SimpleNamespace(reason="source_http_429", retry_after=datetime.now(timezone.utc) - timedelta(seconds=1))
    result = run_window()
    assert result["status"] == "ok"
    assert (result["start_page"], result["next_page"]) == (4, 7)


def test_quality_pause_does_not_block_head_refresh(collection, monkeypatch):
    original = catalog._fetch_source_batch
    async def unknown(*_args, **_kwargs):
        return [{"external_id": "unknown"}], {"accepted": 1, "unresolved_make": 1}
    monkeypatch.setattr(catalog, "_fetch_source_batch", unknown)
    assert run_window()["reason"] == "identity_quality"
    monkeypatch.setattr(catalog, "_fetch_source_batch", original)
    assert run_window()["status"] == "paused"
    assert run_window("head")["status"] == "ok"


def test_source_lock_rejects_overlapping_partitions_before_fetch(collection):
    collection["source_locked"] = False
    with pytest.raises(HTTPException) as error:
        run_window()
    assert error.value.detail == "collection_source_busy"
    assert not collection["fetches"]
    assert not collection["pauses"]


def test_storage_guard_also_stops_head_inserts(collection):
    collection["database_bytes"] = 251 * 1024 * 1024
    with pytest.raises(HTTPException) as error:
        run_window("head")
    assert error.value.status_code == 507
    assert not collection["fetches"]


def test_out_of_range_page_does_not_pause_other_partitions_of_source(collection):
    scope, reason, delay = catalog._collection_pause_spec(RuntimeError("source_http_404"), "autoscout24", "autoscout24:A", "growth", True)
    assert scope == "partition:growth:autoscout24:A"
    assert reason == "source_http_404"
    assert delay == timedelta(hours=24)


@pytest.mark.parametrize("message,reason,scope", [
    ("source_empty_or_unrecognized_page", "empty_or_unrecognized_window", "partition:growth:willhaben:category:limousine"),
    ("source_http_404", "source_http_404", "partition:growth:willhaben:category:limousine"),
    ("source_http_429", "source_http_429", "source:willhaben"),
    ("source_http_503", "source_fetch_failed", "source:willhaben"),
])
def test_first_rejection_returns_committed_pause_without_changing_saved_rows_or_cursor(collection, monkeypatch, message, reason, scope):
    run_window()
    saved_cursor = copy.deepcopy(collection["cursor"])
    saved_rows = copy.deepcopy(collection["rows"])
    fetches = []

    async def rejected(*_args, **_kwargs):
        fetches.append(True)
        raise RuntimeError(message)

    monkeypatch.setattr(catalog, "_fetch_source_batch", rejected)
    first = run_window()
    second = run_window()
    assert first == second == {
        "status": "paused", "partition": "willhaben:category:limousine",
        "reason": reason, "retry_after": collection["pauses"][scope].retry_after.isoformat(),
    }
    assert len(fetches) == 1
    assert all(getattr(collection["cursor"], column.name) == getattr(saved_cursor, column.name)
               for column in catalog.CatalogScanCursor.__table__.columns)
    assert collection["rows"] == saved_rows
    assert collection["sessions"][-2].rolled_back
    assert all(session.closed for session in collection["sessions"])


def test_identity_rejection_returns_pause_without_accepting_bad_rows(collection, monkeypatch):
    run_window()
    async def unknown(*_args, **_kwargs):
        return [{"external_id": "unknown"}], {"accepted": 47, "unresolved_make": 5}
    monkeypatch.setattr(catalog, "_fetch_source_batch", unknown)
    result = run_window()
    assert result["status"] == "paused" and result["reason"] == "identity_quality"
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1


def test_failed_pause_commit_is_not_reported_as_a_handled_pause(collection, monkeypatch):
    run_window()
    collection["commit_fails"] = True
    async def refused(*_args, **_kwargs):
        raise RuntimeError("source_http_429")
    monkeypatch.setattr(catalog, "_fetch_source_batch", refused)
    with pytest.raises(RuntimeError, match="commit failed"):
        run_window()
    assert not collection["pauses"]
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1


@pytest.mark.parametrize("error", [KeyError("broken parser"), RuntimeError("unexpected parser failure")])
def test_unexpected_parser_error_remains_fatal_without_source_pause(collection, monkeypatch, error):
    run_window()
    async def broken(*_args, **_kwargs):
        raise error
    monkeypatch.setattr(catalog, "_fetch_source_batch", broken)
    with pytest.raises(type(error), match="parser"):
        run_window()
    assert not collection["pauses"]
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), catalog.aiohttp.ClientConnectionError("offline")])
def test_transport_failure_returns_durable_backoff_without_cursor_progress(collection, monkeypatch, error):
    run_window()
    async def unavailable(*_args, **_kwargs):
        raise error
    monkeypatch.setattr(catalog, "_fetch_source_batch", unavailable)
    result = run_window()
    assert result["status"] == "paused" and result["reason"] == "source_fetch_failed"
    assert collection["cursor"].next_page == 4
    assert len(collection["rows"]) == 1


def test_cron_handles_first_autoscout_pause_like_subsequent_saved_pause(collection, monkeypatch, caplog):
    # Reproduce 27 Nov 15:47 UTC: A/NL/B are newly rejected; all others paused.
    monkeypatch.setenv("AUTOAI_CATALOG_SCAN_MODE", "growth")
    retry_after = datetime.now(timezone.utc) + timedelta(days=1)
    rejected = {"autoscout24:A", "autoscout24:NL", "autoscout24:B"}
    for part in scraper.collection_windows("growth"):
        if part.key not in rejected:
            collection["pauses"][f"partition:growth:{part.key}"] = SimpleNamespace(
                reason="empty_or_unrecognized_window", retry_after=retry_after)
    fetched = []
    async def empty(source, _max_pages, _now, filters):
        fetched.append(filters["country"])
        raise RuntimeError("source_empty_or_unrecognized_page")
    monkeypatch.setattr(catalog, "_fetch_source_batch", empty)
    app = FastAPI()
    app.include_router(catalog.router, prefix="/api/v1/internal/m01")

    with TestClient(app) as client:
        def post(url, **kwargs):
            reply = client.post(url, params=kwargs["params"], headers=kwargs["headers"])
            response = requests.Response()
            response.status_code, response._content = reply.status_code, reply.content
            return response
        monkeypatch.setattr(scraper.requests, "post", post)
        with caplog.at_level("INFO"):
            assert scraper._collect_windows("http://testserver", "test-secret", 3) == 0
            assert scraper._collect_windows("http://testserver", "test-secret", 3) == 0

    assert fetched == ["A", "NL", "B"]  # No second fetch or immediate retry.
    assert collection["cursor"] is None and not collection["rows"]
    assert "accepted_by_source={} failed_partitions=[]" in caplog.text
    assert "completed_windows=0" in caplog.text  # A pause is not successful coverage.

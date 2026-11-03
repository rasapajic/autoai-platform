from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api import m01_listings as catalog


@pytest.fixture
def repair(monkeypatch):
    row = SimpleNamespace(id=UUID(int=1), make="Jaguar", model="F",
                          description="Jaguar F-Type 3.0", url="https://example.test/car/1",
                          price=12000, is_active=True, first_seen_at="original", last_seen_at="original",
                          price_estimated=13000, price_delta_pct=1, price_rating="good", embedding=[1])
    state = {"rows": [row], "committed": False, "rolled_back": False, "closed": False,
             "locked": True, "statements": []}

    class Session:
        def execute(self, statement):
            return SimpleNamespace(scalar=lambda: state["locked"])
        def query(self, model):
            assert model is catalog.Listing
            return self
        def filter(self, condition):
            state["statements"].append(str(condition))
            return self
        def order_by(self, _column):
            return self
        def limit(self, limit):
            assert limit == 501
            return self
        def with_for_update(self):
            return self
        def all(self):
            return state["rows"]
        def commit(self):
            state["committed"] = True
        def rollback(self):
            state["rolled_back"] = True
        def close(self):
            state["closed"] = True

    monkeypatch.setattr(catalog, "SessionLocal", Session)
    monkeypatch.setattr(catalog.settings, "AUTOAI_ADMIN_SECRET", "test-secret")
    return state


def run(**kwargs):
    return catalog.repair_jaguar_models(confirm="REPAIR_EVIDENCED_JAGUAR_MODELS", after_id=kwargs.get("after_id"),
                                       dry_run=kwargs.get("dry_run", True), x_autoai_admin_secret="test-secret")


def test_repair_changes_only_evidenced_model_and_clears_derived_values(repair):
    unknown = deepcopy(repair["rows"][0])
    unknown.id = UUID(int=2)
    unknown.description = "Jaguar F"
    repair["rows"].append(unknown)
    result = run(dry_run=False)
    assert result["changed"] == 1
    assert result["changes"] == [{"before": "F", "after": "F-Type", "count": 1}]
    row = repair["rows"][0]
    assert row.model == "F-Type" and row.price_estimated is None and row.embedding is None
    assert (row.price, row.is_active, row.first_seen_at, row.last_seen_at) == (12000, True, "original", "original")
    assert unknown.model == "F" and unknown.price_estimated == 13000
    assert repair["committed"] and repair["closed"]
    assert run(dry_run=False)["changed"] == 0


def test_repair_preview_rolls_back_without_commit(repair):
    result = run()
    assert result["dry_run"] and result["changed"] == 1
    assert repair["rolled_back"] and not repair["committed"] and repair["closed"]


def test_repair_keyset_limits_each_transaction_to_500(repair):
    repair["rows"] = [SimpleNamespace(id=UUID(int=i), make="Jaguar", model="F", description=None, url=None)
                      for i in range(2, 503)]
    result = run(after_id=UUID(int=1))
    assert result["scanned"] == 500
    assert result["next_after_id"] == str(UUID(int=501))
    assert any("listings.id >" in statement for statement in repair["statements"])
    assert any("lower(listings.make)" in statement for statement in repair["statements"])


def test_repair_rejects_overlap_and_closes_session(repair):
    repair["locked"] = False
    with pytest.raises(HTTPException) as exc:
        run(dry_run=False)
    assert exc.value.status_code == 409
    assert repair["rolled_back"] and repair["closed"] and not repair["committed"]


def test_repair_requires_secret_and_explicit_confirmation(repair):
    with pytest.raises(HTTPException) as exc:
        catalog.repair_jaguar_models(confirm="REPAIR_EVIDENCED_JAGUAR_MODELS", after_id=None,
                                    dry_run=False, x_autoai_admin_secret="wrong")
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        catalog.repair_jaguar_models(confirm="", after_id=None, dry_run=False,
                                    x_autoai_admin_secret="test-secret")
    assert exc.value.status_code == 400

import pytest
from sqlalchemy import create_engine, select

from app.api.search import _model_filter_condition
from app.models import Listing


@pytest.mark.parametrize("model,exact,expected", [
    ("F", True, ["F", "f"]),
    ("F", False, ["F", "F-Pace", "XF", "f", "F%", "F_", "FThing"]),
    ("F%", True, ["F%"]),
    ("F_", True, ["F_"]),
    ("208", True, ["208"]),
])
def test_model_selector_matches_exact_names_without_changing_partial_search(model, exact, expected):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE listings (model TEXT)")
        connection.exec_driver_sql("INSERT INTO listings (model) VALUES (?)", [(name,) for name in ["F", "F-Pace", "XF", "f", "F%", "F_", "FThing", "208", "2008"]])
        rows = connection.execute(select(Listing.model).where(_model_filter_condition(model, exact))).scalars().all()
    assert rows == expected
    engine.dispose()

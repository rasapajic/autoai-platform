from app.api.search import _group_make_counts


def test_make_options_exclude_external_taxonomy_ids():
    assert _group_make_counts([
        ("1036", 141), ("1008", 74), ("10004", 2),
        ("", 1), (None, 1), (" 1000 ", 3),
        ("BMW", 10), ("Ford", 8),
    ]) == [{"make": "BMW", "count": 10}, {"make": "Ford", "count": 8}]


def test_make_options_group_aliases_and_preserve_real_names():
    assert _group_make_counts([
        ("VW", 2), ("Volkswagen", 3), (" BMW ", 1),
        ("bmw", 2), ("Citroen", 1), ("Citroën", 2),
        ("DS Automobiles", 4),
    ]) == [
        {"make": "BMW", "count": 3},
        {"make": "Citroën", "count": 3},
        {"make": "DS Automobiles", "count": 4},
        {"make": "Volkswagen", "count": 5},
    ]

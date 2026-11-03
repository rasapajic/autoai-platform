from html import escape

import pytest

from app.scrapers.kleinanzeigen import _extract_make_model, _parse_listings_from_html
from app.core.listing_normalization import normalize_vehicle_fields


def card(title, before="", body="Gepflegtes Fahrzeug", price="3.500 €"):
    return f'''<article data-adid="123" data-href="/s-anzeige/auto/123-216-456">
      {before}<h2><a href="/s-anzeige/auto/123-216-456">{escape(title)}</a></h2>
      <p>{escape(body)}</p><p>{price}</p><div>12345 Berlin</div>
      <span>EZ 05/2014</span><span>140.000 km</span>
      <img src="https://example.test/image.jpg"></article>'''


@pytest.mark.parametrize("title,make,model", [
    ("Verkaufe einen Volkswagen Touran 1.6 TDI", "Volkswagen", "Touran"),
    ("Verkauf Opel Astra H 1.7CDTDI", "Opel", "Astra"),
    ("chervolet captiva", "Chevrolet", "Captiva"),
    ("Ich verkaufe meinen BMW 320d", "BMW", "320d"),
    ("Zum Verkauf steht ein Audi A4", "Audi", "A4"),
    ("Biete: Jaguar F-Type 3.0", "Jaguar", "F-Type"),
    ("VW Golf", "Volkswagen", "Golf"),
    ("Chevrolet Camaro", "Chevrolet", "Camaro"),
    ("CLS 350 AMG", None, None),
    ("Winterauto", None, None),
])
def test_readable_vehicle_evidence_resolves_sales_wrappers_without_guessing(title, make, model):
    assert _extract_make_model(title) == (make, model)


@pytest.mark.parametrize("title", [
    "Suche Opel Frontera A Sport", "Ich suche einen Tesla Model Y",
    "Winterauto gesucht", "BMW 320d gesucht", "Ankauf Autos aller Art",
    "Wir kaufen Ihr Auto", "Kaufe Mercedes-Benz",
])
def test_buyer_requests_are_excluded_even_with_a_numeric_price(title):
    assert _parse_listings_from_html(card(title)) == []


def test_linked_vehicle_heading_takes_precedence_over_metadata_and_retains_original_evidence():
    title = "Verkauf Opel Astra H 1.7CDTDI"
    rows = _parse_listings_from_html(card(title, before="<h3>6 48465 Schüttorf Heute, 11:06</h3>"))
    assert len(rows) == 1
    row = rows[0]
    assert (row["make"], row["model"]) == ("Opel", "Astra")
    assert row["description"].startswith(title)
    assert normalize_vehicle_fields(row) == {"make": "Opel", "model": "Astra"}
    assert (row["country"], row["price"], row["year"], row["mileage"]) == ("DE", 3500, 2014, 140000)


def test_seller_looking_for_a_new_owner_is_not_a_wanted_ad():
    rows = _parse_listings_from_html(card("VW Golf — suche neuen Besitzer"))
    assert len(rows) == 1 and rows[0]["make"] == "Volkswagen"


def test_unknown_headline_is_not_resolved_from_an_unrelated_brand_in_prose():
    rows = _parse_listings_from_html(card("Winterauto", body="Billiger als ein BMW oder Audi"))
    assert len(rows) == 1
    assert normalize_vehicle_fields(rows[0])["make"] is None

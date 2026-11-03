from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from bs4 import BeautifulSoup

from app.scrapers.willhaben import _parse_ad
from app.scrapers.kleinanzeigen import _parse_listings_from_html
from app.core.source_dates import source_date, structured_card_dates
from app.api.m01_listings import _safe_listing_payload
from app.api.schemas import ListingDetail


def wh(attributes):
    return {"id": "123", "attributes": {"attribute": [
        {"name": key, "values": [value]} for key, value in {"PRICE": "12000", **attributes}.items()
    ]}}


def test_willhaben_keeps_publish_and_change_as_independent_epoch_evidence():
    row = _parse_ad(wh({"PUBLISHED": "1735689600000", "CHANGED": "1735776000000"}))
    assert row["source_dates"]["published"]["value"] == "2025-01-01T00:00:00+00:00"
    assert row["source_dates"]["published"]["semantics"] == "published_or_renewed"
    assert row["source_dates"]["modified"]["value"] == "2025-01-02T00:00:00+00:00"


def test_willhaben_does_not_substitute_publish_time_for_missing_modification():
    row = _parse_ad(wh({"PUBLISHED": "1735689600000", "CHANGED_String": "2025-01-01T13:00:00Z"}))
    assert "published" in row["source_dates"] and "modified" not in row["source_dates"]
    assert _parse_ad(wh({"PUBLISHED_String": "2025-01-01T13:00:00Z"}))["source_dates"] == {}


def test_kleinanzeigen_reads_only_publication_label_before_vehicle_heading():
    html = '''<article data-adid="123" data-href="/s-anzeige/auto/123-216-456">
        <div>01.11.2025</div><h2><a href="/s-anzeige/auto/123-216-456">VW Golf</a></h2>
        <p>Service am 02.11.2025</p><p>3.500 €</p></article>'''
    row = _parse_listings_from_html(html)[0]
    assert row["source_dates"]["published"]["value"] == "2025-11-01"
    assert row["source_dates"]["published"]["precision"] == "date"
    assert "modified" not in row["source_dates"]
    assert _parse_listings_from_html(html.replace("<div>01.11.2025</div>", ""))[0]["source_dates"] == {}


def test_explicit_structured_dates_are_scoped_to_the_listing_card():
    soup = BeautifulSoup('''<time itemprop="dateModified" datetime="2025-12-01T00:00:00Z"></time>
        <article><time itemprop="datePublished" datetime="2025-11-01T10:00:00+01:00"></time></article>''', "html.parser")
    dates = structured_card_dates(soup.article)
    assert dates["published"]["value"] == "2025-11-01T09:00:00+00:00"
    assert "modified" not in dates


def test_ingest_and_detail_keep_autoai_check_separate_and_missing_dates_unknown():
    now = datetime.now(timezone.utc)
    dates = {"published": source_date("2025-11-01", field="card_publication_date", semantics="published")}
    payload = _safe_listing_payload({"source_dates": dates}, now)
    assert payload["last_seen_at"] == now
    assert payload["source_dates"]["published"]["value"] == "2025-11-01"
    detail = ListingDetail.model_validate(SimpleNamespace(id=uuid4(), source="kleinanzeigen", url="https://example.test/123", **payload))
    assert detail.last_seen_at == now and "modified" not in detail.source_dates
    assert "source_dates" not in _safe_listing_payload({"source_dates": {}}, now)

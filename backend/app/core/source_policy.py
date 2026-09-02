from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ListingSource:
    key: str
    storage_source: str
    default_country: str | None
    module: str
    class_name: str


SOURCE_REGISTRY: dict[str, ListingSource] = {
    "willhaben": ListingSource(
        key="willhaben",
        storage_source="willhaben",
        default_country="AT",
        module="app.scrapers.willhaben",
        class_name="WillhabenScraper",
    ),
    "autoscout24": ListingSource(
        key="autoscout24",
        storage_source="autoscout24",
        default_country=None,
        module="app.scrapers.autoscout24",
        class_name="AutoScout24Scraper",
    ),
    "marktplaats": ListingSource(
        key="marktplaats",
        storage_source="marktplaats",
        default_country="NL",
        module="app.scrapers.marktplaats",
        class_name="MarktplaatsScraper",
    ),
    "2dehands": ListingSource(
        key="2dehands",
        storage_source="2dehands",
        default_country="BE",
        module="app.scrapers.tweedehands",
        class_name="TweedehandsScraper",
    ),
    "kleinanzeigen": ListingSource(
        key="kleinanzeigen",
        storage_source="kleinanzeigen",
        default_country="DE",
        module="app.scrapers.kleinanzeigen",
        class_name="KleinanzeigenScraper",
    ),
}


def configured_source_keys() -> set[str]:
    raw = settings.AUTOAI_INTERNAL_LISTING_SOURCES or ""
    return {item.strip() for item in raw.split(",") if item.strip()}


def get_enabled_source(source_key: str) -> ListingSource:
    if not settings.AUTOAI_INTERNAL_LISTING_INGEST_ENABLED:
        raise RuntimeError("internal_listing_ingest_disabled")

    source = SOURCE_REGISTRY.get(source_key)
    if source is None:
        raise ValueError(f"unsupported_source:{source_key}")

    if source_key not in configured_source_keys():
        raise PermissionError(f"source_not_enabled:{source_key}")

    return source

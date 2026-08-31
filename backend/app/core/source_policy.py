from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ListingSource:
    key: str
    storage_source: str
    country: str
    module: str
    class_name: str


SOURCE_REGISTRY: dict[str, ListingSource] = {
    "willhaben": ListingSource(
        key="willhaben",
        storage_source="willhaben",
        country="AT",
        module="app.scrapers.willhaben",
        class_name="WillhabenScraper",
    ),
    "mobile_de": ListingSource(
        key="mobile_de",
        storage_source="mobile.de",
        country="DE",
        module="app.scrapers.mobile_de",
        class_name="MobileDeScraper",
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

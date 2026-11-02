"""Shared bounded collection plan; importable by the minimal cron image."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionPartition:
    key: str
    source: str
    filters: dict


COLLECTION_PLAN = (
    *(CollectionPartition(f"willhaben:category:{category}", "willhaben", {"category": category})
      for category in ("limousine", "suv-gelaendewagen", "cabrio-roadster")),
    *(CollectionPartition(f"willhaben:type:{kind}", "willhaben", {"car_type": kind})
      for kind in ("4", "5", "6", "9", "10")),
    *(CollectionPartition(f"autoscout24:{market}", "autoscout24", {"country": market})
      for market in ("A", "D", "NL", "I", "B")),
    CollectionPartition("marktplaats:all", "marktplaats", {}),
    CollectionPartition("2dehands:all", "2dehands", {}),
    CollectionPartition("kleinanzeigen:all", "kleinanzeigen", {}),
)
PARTITION_BY_KEY = {partition.key: partition for partition in COLLECTION_PLAN}


def page_window(filters: dict, max_pages: int) -> range:
    start = int(filters.get("start_page", 1))
    if start < 1 or not 1 <= max_pages <= 20:
        raise ValueError("invalid_catalog_page_window")
    return range(start, start + max_pages)

"""Shared bounded collection plan; importable by the minimal cron image."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionPartition:
    key: str
    source: str
    filters: dict


BASE_COLLECTION_PLAN = (
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
GERMAN_PRICE_BANDS = (
    (500, 4999), (5000, 9999), (10000, 14999), (15000, 19999),
    (20000, 29999), (30000, 49999), (50000, 99999), (100000, 2000000),
)
GERMAN_GROWTH_PARTITIONS = tuple(
    CollectionPartition(f"autoscout24:D:price:{low}-{high}", "autoscout24",
                        {"country": "D", "min_price": low, "max_price": high})
    for low, high in GERMAN_PRICE_BANDS
)
# Append new keys so existing advisory-lock IDs and checkpoints remain stable.
COLLECTION_PLAN = (*BASE_COLLECTION_PLAN, *GERMAN_GROWTH_PARTITIONS)
PARTITION_BY_KEY = {partition.key: partition for partition in COLLECTION_PLAN}


def collection_windows(scan_mode: str) -> tuple[CollectionPartition, ...]:
    if scan_mode == "head":
        return BASE_COLLECTION_PLAN
    if scan_mode != "growth":
        raise ValueError("invalid_catalog_scan_mode")
    remaining = tuple(part for part in BASE_COLLECTION_PLAN if part.key != "autoscout24:D")
    return (*GERMAN_GROWTH_PARTITIONS, *remaining)


def page_window(filters: dict, max_pages: int) -> range:
    start = int(filters.get("start_page", 1))
    if start < 1 or not 1 <= max_pages <= 20:
        raise ValueError("invalid_catalog_page_window")
    return range(start, start + max_pages)

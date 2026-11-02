"""Run the guarded AutoAI internal catalog refresh from the Railway cron service."""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.catalog_plan import COLLECTION_PLAN

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REFRESH_PATH = "/api/v1/internal/m01/scheduled-refresh"
REFRESH_CONFIRMATION = "REFRESH_ACTIVE_INTERNAL_CATALOG"
REQUIRED_SOURCES = (
    "willhaben",
    "autoscout24",
    "marktplaats",
    "2dehands",
    "kleinanzeigen",
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _max_pages() -> int:
    raw_value = os.getenv("AUTOAI_CRON_MAX_PAGES", "3").strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("AUTOAI_CRON_MAX_PAGES must be an integer") from exc
    if not 1 <= value <= 5:
        raise RuntimeError("AUTOAI_CRON_MAX_PAGES must be between 1 and 5")
    return value


def main() -> int:
    backend_url = _required_env("AUTOAI_BACKEND_URL")
    admin_secret = _required_env("AUTOAI_ADMIN_SECRET")
    max_pages = _max_pages()
    if os.getenv("AUTOAI_CATALOG_CURSORS_ENABLED", "").strip().lower() in {"true", "1", "yes"}:
        return _collect_windows(backend_url, admin_secret, min(max_pages, 3))
    refresh_url = urljoin(f"{backend_url.rstrip('/')}/", REFRESH_PATH.lstrip("/"))

    logger.info("Starting guarded internal catalog refresh (max_pages=%s)", max_pages)
    response = requests.post(
        refresh_url,
        params={
            "confirm": REFRESH_CONFIRMATION,
            "max_pages": max_pages,
        },
        headers={"X-AutoAI-Admin-Secret": admin_secret},
        timeout=(30, 1800),
    )
    response.raise_for_status()
    result = response.json()

    accepted = result.get("by_source", {})
    missing = [
        source
        for source in REQUIRED_SOURCES
        if accepted.get(source, {}).get("accepted", 0) <= 0
    ]
    if result.get("status") != "ok" or result.get("active_after", 0) <= 0 or missing:
        raise RuntimeError(
            "refresh response failed validation"
            + (f"; invalid sources: {','.join(missing)}" if missing else "")
        )

    for source in REQUIRED_SOURCES:
        details = accepted[source]
        logger.info(
            "Source %s: found=%s accepted=%s unresolved_make=%s unresolved_model=%s",
            source, details.get("found", "unknown"), details["accepted"],
            details.get("unresolved_make", "unknown"), details.get("unresolved_model", "unknown"),
        )

    logger.info(
        "Internal catalog refresh complete: active=%s new=%s updated=%s inactive=%s",
        result["active_after"],
        result.get("new", 0),
        result.get("updated", 0),
        result.get("inactive_after", 0),
    )
    return 0


def _collect_windows(backend_url: str, admin_secret: str, max_pages: int) -> int:
    mode = os.getenv("AUTOAI_CATALOG_SCAN_MODE", "auto").strip().lower()
    if mode == "auto":
        now = datetime.now(timezone.utc)
        mode = "head" if now.hour == 2 and now.minute < 15 else "growth"
    if mode not in {"head", "growth"}:
        raise RuntimeError("AUTOAI_CATALOG_SCAN_MODE must be auto, head or growth")
    url = urljoin(f"{backend_url.rstrip('/')}/", "api/v1/internal/m01/collect-window")
    failed = []
    paused = []
    paused_counts = {}
    accepted = {}
    total_new = total_updated = 0
    active_after = database_bytes = None
    logger.info("Starting bounded catalog collection: mode=%s partitions=%s max_pages=%s", mode, len(COLLECTION_PLAN), max_pages)
    for partition in COLLECTION_PLAN:
        try:
            response = requests.post(url, params={
                "confirm": "COLLECT_INTERNAL_CATALOG_WINDOW", "partition_key": partition.key,
                "scan_mode": mode, "max_pages": max_pages,
            }, headers={"X-AutoAI-Admin-Secret": admin_secret}, timeout=(30, 540))
            response.raise_for_status()
            result = response.json()
            if result.get("status") == "paused":
                paused.append(partition.key)
                paused_counts[partition.source] = paused_counts.get(partition.source, 0) + 1
                logger.info("Partition %s paused: reason=%s retry_after=%s", partition.key, result.get("reason"), result.get("retry_after"))
                continue
            details = result.get("by_source", {}).get(partition.source, {})
            if result.get("status") != "ok" or details.get("accepted", 0) <= 0:
                raise RuntimeError("invalid_collection_response")
            accepted[partition.source] = accepted.get(partition.source, 0) + details["accepted"]
            total_new += result.get("new", 0)
            total_updated += result.get("updated", 0)
            active_after = result.get("active_after", active_after)
            database_bytes = result.get("database_bytes_before", database_bytes)
            logger.info("Partition %s: pages=%s-%s next=%s accepted=%s new=%s updated=%s unresolved_make=%s", partition.key, result["start_page"], result["end_page"], result["next_page"], details["accepted"], result.get("new", 0), result.get("updated", 0), details.get("unresolved_make", "unknown"))
        except Exception as exc:
            failed.append(partition.key)
            logger.error("Partition %s request failed (%s); inspect its saved checkpoint before retry", partition.key, type(exc).__name__)
    logger.info("Catalog collection finished: status=%s active=%s new=%s updated=%s database_bytes=%s accepted_by_source=%s failed_partitions=%s paused_partitions=%s", "partial" if failed or paused else "ok", active_after, total_new, total_updated, database_bytes, accepted, failed, paused)
    missing = [source for source in REQUIRED_SOURCES if accepted.get(source, 0) <= 0 and paused_counts.get(source, 0) != sum(part.source == source for part in COLLECTION_PLAN)]
    if missing:
        raise RuntimeError(f"collection incomplete; failed_partitions={','.join(failed)}; invalid sources={','.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

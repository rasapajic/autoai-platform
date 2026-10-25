"""Run the guarded AutoAI internal catalog refresh from the Railway cron service."""

import logging
import os
from urllib.parse import urljoin

import requests

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

    logger.info(
        "Internal catalog refresh complete: active=%s new=%s updated=%s inactive=%s",
        result["active_after"],
        result.get("new", 0),
        result.get("updated", 0),
        result.get("inactive_after", 0),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded, cached source-date enrichment on an authenticated listing view."""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, urljoin
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import text

from app.core.source_dates import source_date, merge_source_dates
from app.core.source_policy import get_enabled_source
from app.models import CatalogCollectionPause
from app.scrapers.willhaben import HEADERS


def willhaben_detail_url(listing):
    parsed = urlparse(listing.url or "")
    identity = str(listing.external_id or "").removeprefix("wh_")
    if (listing.source != "willhaben" or not identity.isdigit() or parsed.scheme != "https"
        or parsed.hostname not in {"www.willhaben.at", "willhaben.at"} or parsed.netloc != parsed.hostname
        or not parsed.path.startswith("/iad/gebrauchtwagen/d/auto/")
        or not re.search(r"(?:/|-)" + re.escape(identity) + r"/?$", parsed.path)):
        return None
    return urlunparse(("https", "www.willhaben.at", parsed.path, "", "", ""))


def visible_willhaben_modified(html, reference=None):
    visible = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    matches = set(re.findall(r"Zuletzt\s+geändert:\s*(\d{2}\.\d{2}\.\d{4}),\s*(\d{2}:\d{2})\s*Uhr", visible))
    if len(matches) != 1:
        return None
    day, clock = next(iter(matches))
    try:
        local = datetime.strptime(day + " " + clock, "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Vienna"))
        if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
            return None
        entry = source_date(local.isoformat(), field="Zuletzt geändert", semantics="modified", reference=reference)
        if entry:
            entry["precision"] = "minute"
            entry["raw"] = day + ", " + clock
        return entry
    except ValueError:
        return None


async def fetch_willhaben_modified(url):
    timeout = aiohttp.ClientTimeout(total=15)
    identity = re.search(r"(?:/|-)(\d+)/?$", urlparse(url).path)[1]
    async with asyncio.timeout(15):
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout, trust_env=True) as session:
            for _ in range(3):
                async with session.get(url, allow_redirects=False) as response:
                    if response.status in {301, 302, 307, 308}:
                        target = urljoin(url, response.headers.get("Location", ""))
                        url = willhaben_detail_url(SimpleNamespace(source="willhaben", external_id="wh_" + identity, url=target))
                        if not url:
                            return response.status, None
                        continue
                    if response.status != 200:
                        return response.status, None
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        raw.extend(chunk)
                        if len(raw) > 5_000_000:
                            return 200, None
                    return 200, visible_willhaben_modified(raw.decode("utf-8", errors="replace"))
    return 302, None


async def refresh_missing_modified(db, listing):
    dates = listing.source_dates if isinstance(listing.source_dates, dict) else {}
    url = willhaben_detail_url(listing)
    if not url:
        return
    now = datetime.now(timezone.utc)
    try:
        get_enabled_source("willhaben")
    except (ValueError, RuntimeError, PermissionError):
        return
    # One date-detail request at a time; independent of collection cursor locks.
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(3707, 1)")).scalar():
        return
    db.refresh(listing)
    dates = listing.source_dates if isinstance(listing.source_dates, dict) else {}
    modified = dates.get("modified") if isinstance(dates.get("modified"), dict) else {}
    for value in (dates.get("_detail_checked_at"), modified.get("observed_at")):
        try:
            checked = datetime.fromisoformat(value)
            if checked.tzinfo and now - timedelta(hours=6) < checked <= now + timedelta(minutes=5):
                return
        except (ValueError, TypeError):
            pass
    for key in ("source:willhaben", "source-date-fetch:willhaben"):
        pause = db.get(CatalogCollectionPause, key)
        if pause is not None and pause.retry_after > now:
            return
    try:
        status, modified = await fetch_willhaben_modified(url)
    except Exception:
        status, modified = 0, None
    try:
        # Re-read after the network call so concurrent collection metadata is kept.
        db.refresh(listing, with_for_update=True)
        listing.source_dates = merge_source_dates(listing.source_dates, {
            "_detail_checked_at": now.isoformat(), "_detail_status": status,
            **({"modified": modified} if modified else {}),
        })
        key = "source:willhaben" if status in {401, 402, 403, 429, 451} else "source-date-fetch:willhaben"
        delay = timedelta(hours=24) if key == "source:willhaben" else timedelta(minutes=30) if status == 0 or status >= 500 else timedelta(seconds=5)
        pause = db.get(CatalogCollectionPause, key)
        deadline = now + delay
        if pause is None:
            db.add(CatalogCollectionPause(pause_key=key, reason=f"source_date_http_{status}", retry_after=deadline))
        elif pause.retry_after < deadline:
            pause.retry_after, pause.reason = deadline, f"source_date_http_{status}"
        db.commit()
    except Exception:
        db.rollback()

import asyncio
import importlib
import logging
import math
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.listing_normalization import normalize_vehicle_fields
from app.core.source_policy import (
    SOURCE_REGISTRY,
    ListingSource,
    configured_source_keys,
    get_enabled_source,
)
from app.models import Listing

logger = logging.getLogger(__name__)
router = APIRouter()

PURGE_CONFIRMATION = "PURGE_LEGACY_LISTINGS"
REFRESH_CONFIRMATION = "REPLACE_ALL_LISTINGS_WITH_FRESH"
SCHEDULED_REFRESH_CONFIRMATION = "REFRESH_ACTIVE_INTERNAL_CATALOG"
HISTORICAL_SOURCE_KEYS = tuple(SOURCE_REGISTRY.keys())
LISTING_WRITE_FIELDS = frozenset(Listing.__table__.columns.keys()) - {"id"}


def require_admin_secret(
    x_autoai_admin_secret: Optional[str] = Header(default=None),
) -> None:
    configured = (settings.AUTOAI_ADMIN_SECRET or "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="AUTOAI_ADMIN_SECRET is not configured")
    supplied = x_autoai_admin_secret or ""
    if not secrets.compare_digest(supplied, configured):
        raise HTTPException(status_code=403, detail="Zabranjen pristup")


def _safe_listing_payload(data: dict, now: datetime) -> dict:
    payload = {
        key: value
        for key, value in data.items()
        if key in LISTING_WRITE_FIELDS and value is not None
    }
    payload["is_active"] = True
    payload["last_seen_at"] = now
    payload["scraped_at"] = now
    return payload


def _prepare_source_batch(
    source: ListingSource,
    listings: list[dict],
    now: datetime,
) -> tuple[list[dict], int]:
    by_external_id: dict[str, dict] = {}
    skipped = 0

    for data in listings:
        external_id = str(data.get("external_id") or "").strip()
        url = str(data.get("url") or "").strip()
        price = data.get("price")

        try:
            valid_price = price is not None and not isinstance(price, bool) and math.isfinite(float(price)) and float(price) > 0
        except (TypeError, ValueError, OverflowError):
            valid_price = False

        if not external_id or not url.startswith(("http://", "https://")) or not valid_price:
            skipped += 1
            continue

        payload = _safe_listing_payload(data, now)
        payload.update(normalize_vehicle_fields(data))
        payload["external_id"] = external_id
        payload["url"] = url
        payload["source"] = source.storage_source
        if not payload.get("country") and source.default_country:
            payload["country"] = source.default_country
        payload["first_seen_at"] = now

        if external_id in by_external_id:
            skipped += 1
        by_external_id[external_id] = payload

    return list(by_external_id.values()), skipped


def _load_scraper(source: ListingSource):
    module = importlib.import_module(source.module)
    scraper_class = getattr(module, source.class_name)
    return scraper_class()


async def _fetch_source_batch(
    source: ListingSource,
    max_pages: int,
    now: datetime,
) -> tuple[list[dict], dict]:
    raw_listings = []
    last_error: Exception | None = None
    attempts = 3
    for attempt in range(1, attempts + 1):
        scraper = _load_scraper(source)
        try:
            raw_listings = await scraper.scrape_listings({}, max_pages=max_pages)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "M0.1 %s attempt %s/%s failed: %s",
                source.key,
                attempt,
                attempts,
                type(exc).__name__,
            )
        if raw_listings:
            break
        if attempt < attempts:
            await asyncio.sleep(attempt * 2)

    if not raw_listings and last_error:
        raise last_error

    prepared, skipped = _prepare_source_batch(source, raw_listings, now)
    return prepared, {
        "found": len(raw_listings),
        "accepted": len(prepared),
        "skipped": skipped,
        "unresolved_make": sum(row.get("make") is None for row in prepared),
        "unresolved_model": sum(row.get("model") is None for row in prepared),
    }


def _require_all_historical_sources() -> list[ListingSource]:
    configured = configured_source_keys()
    missing = [key for key in HISTORICAL_SOURCE_KEYS if key not in configured]
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"required_sources_not_enabled:{','.join(missing)}",
        )

    sources = []
    for key in HISTORICAL_SOURCE_KEYS:
        try:
            sources.append(get_enabled_source(key))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return sources


async def _stage_all_sources(max_pages: int) -> tuple[dict[str, list[dict]], dict]:
    sources = _require_all_historical_sources()
    now = datetime.now(timezone.utc)
    staged: dict[str, list[dict]] = {}
    results: dict[str, dict] = {}
    seen_external_ids: set[str] = set()

    for source in sources:
        try:
            batch, result = await _fetch_source_batch(source, max_pages, now)
        except Exception as exc:
            logger.exception("M0.1 source probe failed for %s", source.key)
            raise HTTPException(
                status_code=502,
                detail=f"source_probe_failed:{source.key}:{type(exc).__name__}",
            ) from exc

        results[source.key] = result
        if not batch:
            raise HTTPException(
                status_code=502,
                detail=f"source_returned_no_valid_listings:{source.key}",
            )

        duplicate_ids = sorted(
            payload["external_id"]
            for payload in batch
            if payload["external_id"] in seen_external_ids
        )
        if duplicate_ids:
            raise HTTPException(
                status_code=502,
                detail=f"duplicate_external_id_across_sources:{duplicate_ids[0]}",
            )
        seen_external_ids.update(payload["external_id"] for payload in batch)
        staged[source.key] = batch

    return staged, {"checked_at": now.isoformat(), "by_source": results}


def _apply_scheduled_catalog_refresh(staged: dict[str, list[dict]]) -> dict:
    """Merge a partial search sample without deactivating unseen listings."""
    source_names = [source.storage_source for source in SOURCE_REGISTRY.values()]
    db = SessionLocal()
    new_count = 0
    updated_count = 0

    try:
        active_before = (
            db.query(func.count(Listing.id))
            .filter(Listing.source.in_(source_names), Listing.is_active == True)
            .scalar()
            or 0
        )
        external_ids = [row["external_id"] for rows in staged.values() for row in rows]
        existing_by_id = {
            row.external_id: row
            for row in db.query(Listing).filter(Listing.external_id.in_(external_ids)).all()
        }

        for source_rows in staged.values():
            for payload in source_rows:
                existing = existing_by_id.get(payload["external_id"])
                if existing:
                    if existing.source != payload["source"]:
                        raise ValueError("external_id_source_conflict")
                    previous_identity = normalize_vehicle_fields({
                        key: getattr(existing, key, None)
                        for key in ("make", "model", "description", "url")
                    })
                    if payload.get("make") is None and previous_identity["make"]:
                        payload["make"] = previous_identity["make"]
                    if payload.get("model") is None and payload.get("make") == previous_identity["make"]:
                        payload["model"] = previous_identity["model"]
                    identity_changed = any(
                        key in payload and getattr(existing, key, None) != payload[key]
                        for key in ("make", "model", "price")
                    )
                    if identity_changed:
                        for key in ("price_estimated", "price_delta_pct", "price_rating", "embedding"):
                            setattr(existing, key, None)
                    for key, value in payload.items():
                        if key in {"external_id", "first_seen_at"}:
                            continue
                        setattr(existing, key, value)
                    updated_count += 1
                else:
                    db.add(Listing(**payload))
                    new_count += 1

        db.flush()
        active_after = (
            db.query(func.count(Listing.id))
            .filter(Listing.source.in_(source_names), Listing.is_active == True)
            .scalar()
            or 0
        )
        inactive_after = (
            db.query(func.count(Listing.id))
            .filter(Listing.source.in_(source_names), Listing.is_active == False)
            .scalar()
            or 0
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("M0.2 scheduled catalog refresh rolled back")
        raise
    finally:
        db.close()

    return {
        "active_before": active_before,
        "new": new_count,
        "updated": updated_count,
        "active_after": active_after,
        "inactive_after": inactive_after,
        "deactivated": 0,
        "coverage": "partial_sample",
    }


@router.get("/status")
def m01_status(x_autoai_admin_secret: Optional[str] = Header(default=None)):
    require_admin_secret(x_autoai_admin_secret)
    db = SessionLocal()
    try:
        rows = (
            db.query(Listing.source, func.count(Listing.id))
            .filter(Listing.is_active == True)
            .group_by(Listing.source)
            .all()
        )
        total_all = db.query(func.count(Listing.id)).scalar() or 0
        total_active = sum(count for _, count in rows)
        return {
            "status": "ok",
            "phase": "M0.3 Normalized Incremental Catalog",
            "ingest_enabled": settings.AUTOAI_INTERNAL_LISTING_INGEST_ENABLED,
            "configured_sources": sorted(configured_source_keys()),
            "required_sources": list(HISTORICAL_SOURCE_KEYS),
            "active_by_source": {source: count for source, count in rows},
            "total_active": total_active,
            "total_all": total_all,
        }
    finally:
        db.close()


@router.post("/purge-legacy-listings")
def purge_legacy_listings(
    confirm: str = Query(...),
    x_autoai_admin_secret: Optional[str] = Header(default=None),
):
    """Emergency standalone purge. Prefer ``refresh-all`` for an atomic replacement."""
    require_admin_secret(x_autoai_admin_secret)
    if confirm != PURGE_CONFIRMATION:
        raise HTTPException(status_code=400, detail=f"confirm must equal {PURGE_CONFIRMATION}")

    db = SessionLocal()
    try:
        before = db.query(func.count(Listing.id)).scalar() or 0
        deleted = db.query(Listing).delete(synchronize_session=False)
        db.commit()
        after = db.query(func.count(Listing.id)).scalar() or 0
        logger.warning(
            "M0.1 standalone listing purge completed: before=%s deleted=%s after=%s",
            before,
            deleted,
            after,
        )
        return {
            "status": "ok",
            "action": "purge_legacy_listings",
            "before": before,
            "deleted": deleted,
            "after": after,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/probe-all")
async def probe_all_sources(
    max_pages: int = Query(1, ge=1, le=10),
    x_autoai_admin_secret: Optional[str] = Header(default=None),
):
    """Fetch and validate every historical source without changing the database."""
    require_admin_secret(x_autoai_admin_secret)
    _, report = await _stage_all_sources(max_pages)
    return {
        "status": "ok",
        "action": "probe_all_sources",
        "database_changed": False,
        **report,
    }


@router.post("/refresh-all")
async def refresh_all_sources(
    confirm: str = Query(...),
    max_pages: int = Query(3, ge=1, le=20),
    x_autoai_admin_secret: Optional[str] = Header(default=None),
):
    """Atomically replace the old catalog with fresh rows from all five sources.

    Every source is fetched and validated first. If one source fails or returns no
    usable listings, the existing database is left untouched.
    """
    require_admin_secret(x_autoai_admin_secret)
    if confirm != REFRESH_CONFIRMATION:
        raise HTTPException(status_code=400, detail=f"confirm must equal {REFRESH_CONFIRMATION}")

    staged, report = await _stage_all_sources(max_pages)
    fresh_rows = [row for source_rows in staged.values() for row in source_rows]

    db = SessionLocal()
    try:
        before = db.query(func.count(Listing.id)).scalar() or 0
        deleted = db.query(Listing).delete(synchronize_session=False)
        db.add_all(Listing(**payload) for payload in fresh_rows)
        db.flush()
        after = db.query(func.count(Listing.id)).scalar() or 0
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("M0.1 atomic all-source refresh rolled back")
        raise
    finally:
        db.close()

    logger.warning(
        "M0.1 atomic refresh completed: before=%s deleted=%s inserted=%s after=%s",
        before,
        deleted,
        len(fresh_rows),
        after,
    )
    return {
        "status": "ok",
        "action": "refresh_all_sources",
        "before": before,
        "deleted": deleted,
        "inserted": len(fresh_rows),
        "after": after,
        **report,
    }


@router.post("/scheduled-refresh")
async def scheduled_refresh_all_sources(
    confirm: str = Query(...),
    max_pages: int = Query(3, ge=1, le=5),
    x_autoai_admin_secret: Optional[str] = Header(default=None),
):
    """Refresh the internal active catalog without deleting listing records.

    All five sources are staged first. Existing rows are updated in place and
    new rows are inserted. Absence from a partial page sample never proves a
    listing unavailable. Any failure rolls back the complete transaction.
    """
    require_admin_secret(x_autoai_admin_secret)
    if confirm != SCHEDULED_REFRESH_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f"confirm must equal {SCHEDULED_REFRESH_CONFIRMATION}",
        )

    staged, report = await _stage_all_sources(max_pages)
    counts = _apply_scheduled_catalog_refresh(staged)
    logger.warning(
        "M0.2 scheduled refresh completed: active_before=%s new=%s updated=%s "
        "active_after=%s inactive_after=%s",
        counts["active_before"],
        counts["new"],
        counts["updated"],
        counts["active_after"],
        counts["inactive_after"],
    )
    return {
        "status": "ok",
        "action": "scheduled_refresh_all_sources",
        **counts,
        **report,
    }


@router.post("/ingest/{source_key}")
async def ingest_source(
    source_key: str,
    max_pages: int = Query(3, ge=1, le=50),
    x_autoai_admin_secret: Optional[str] = Header(default=None),
):
    require_admin_secret(x_autoai_admin_secret)

    try:
        source = get_enabled_source(source_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    try:
        prepared, report = await _fetch_source_batch(source, max_pages, now)
    except Exception as exc:
        logger.exception("M0.1 ingest failed for %s", source_key)
        raise HTTPException(status_code=502, detail=f"scraper_failed:{type(exc).__name__}") from exc

    db = SessionLocal()
    new_count = 0
    updated_count = 0

    try:
        for payload in prepared:
            external_id = payload["external_id"]
            existing = db.query(Listing).filter(Listing.external_id == external_id).first()
            if existing:
                for key, value in payload.items():
                    if key in {"external_id", "first_seen_at"}:
                        continue
                    setattr(existing, key, value)
                updated_count += 1
            else:
                db.add(Listing(**payload))
                new_count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "status": "ok",
        "phase": "M0.1 All-source Live Listings Recovery",
        "source": source_key,
        "country": source.default_country or "MULTI",
        **report,
        "new": new_count,
        "updated": updated_count,
        "checked_at": now.isoformat(),
    }

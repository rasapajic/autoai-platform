import importlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.source_policy import SOURCE_REGISTRY, get_enabled_source
from app.models import Listing

logger = logging.getLogger(__name__)
router = APIRouter()

PURGE_CONFIRMATION = "PURGE_LEGACY_LISTINGS"


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
        if hasattr(Listing, key) and value is not None
    }
    payload.pop("id", None)
    payload["is_active"] = True
    payload["last_seen_at"] = now
    payload["scraped_at"] = now
    return payload


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
            "phase": "M0.1 Live Listings Recovery",
            "ingest_enabled": settings.AUTOAI_INTERNAL_LISTING_INGEST_ENABLED,
            "configured_sources": sorted(SOURCE_REGISTRY.keys()),
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
            "M0.1 legacy listing purge completed: before=%s deleted=%s after=%s",
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


@router.post("/ingest/{source_key}")
async def ingest_source(
    source_key: str,
    max_pages: int = Query(3, ge=1, le=20),
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

    module = importlib.import_module(source.module)
    scraper_class = getattr(module, source.class_name)
    scraper = scraper_class()

    try:
        listings = await scraper.scrape_listings({}, max_pages=max_pages)
    except Exception as exc:
        logger.exception("M0.1 ingest failed for %s", source_key)
        raise HTTPException(status_code=502, detail=f"scraper_failed:{exc}") from exc

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    new_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        for data in listings:
            external_id = data.get("external_id")
            url = data.get("url")
            price = data.get("price")

            if not external_id or not url or not price:
                skipped_count += 1
                continue
            try:
                if float(price) <= 0:
                    skipped_count += 1
                    continue
            except (TypeError, ValueError):
                skipped_count += 1
                continue

            payload = _safe_listing_payload(data, now)
            payload["source"] = source.storage_source
            payload["country"] = source.country

            existing = db.query(Listing).filter(Listing.external_id == external_id).first()
            if existing:
                for key, value in payload.items():
                    if key in {"external_id", "first_seen_at"}:
                        continue
                    setattr(existing, key, value)
                updated_count += 1
            else:
                payload["external_id"] = external_id
                payload["first_seen_at"] = now
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
        "phase": "M0.1 Live Listings Recovery",
        "source": source_key,
        "country": source.country,
        "found": len(listings),
        "new": new_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "checked_at": now.isoformat(),
    }

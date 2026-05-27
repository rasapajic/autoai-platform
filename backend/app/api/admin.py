import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

ADMIN_SECRET = "autoai-admin-2024"


def check_secret(secret: Optional[str]):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Zabranjen pristup")


def _save_listings(db, listings: list) -> tuple:
    from app.models import Listing
    new_count = 0
    updated_count = 0
    for data in listings:
        external_id = data.get("external_id")
        if not external_id:
            continue
        existing = db.query(Listing).filter(Listing.external_id == external_id).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            existing.is_active = True
            new_price = data.get("price")
            if new_price and existing.price != float(new_price):
                existing.price = new_price
            updated_count += 1
        else:
            listing = Listing(**{k: v for k, v in data.items() if hasattr(Listing, k) and v is not None})
            db.add(listing)
            new_count += 1
    db.commit()
    return new_count, updated_count


async def _run_scraper(portal: str):
    allowed = ["willhaben", "mobile_de"]
    if portal not in allowed:
        raise HTTPException(status_code=400, detail=f"Portal mora biti jedan od: {allowed}")
    try:
        if portal == "willhaben":
            from app.scrapers.willhaben import WillhabenScraper
            scraper = WillhabenScraper()
        else:
            from app.scrapers.mobile_de import MobileDeScraper
            scraper = MobileDeScraper()

        logger.info(f"🕷️ Pokrenuto: {portal}")
        listings = await scraper.scrape_listings({}, max_pages=3)

        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            new_count, updated_count = _save_listings(db, listings)
        finally:
            db.close()

        logger.info(f"✅ {portal}: {new_count} novih, {updated_count} ažuriranih")
        return {"status": "ok", "portal": portal, "found": len(listings), "new": new_count, "updated": updated_count}

    except Exception as e:
        logger.error(f"❌ {portal}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape/{portal}/run")
async def trigger_scrape_get(portal: str, secret: str):
    check_secret(secret)
    return await _run_scraper(portal)


@router.get("/scrape/status")
async def scrape_status(secret: str):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = db.query(Listing.source, func.count(Listing.id)).filter(Listing.is_active == True).group_by(Listing.source).all()
        return {"status": "ok", "sources": {s: c for s, c in rows}, "total": sum(c for _, c in rows)}
    finally:
        db.close()
@router.get("/cleanup/willhaben-bad-prices")
async def cleanup_bad_prices(secret: str):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    db = SessionLocal()
    try:
        count = db.query(Listing).filter(
            Listing.source == "willhaben",
            Listing.price < 500
        ).delete()
        db.commit()
        return {"deleted": count}
    finally:
        db.close()

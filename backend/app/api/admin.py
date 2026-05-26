import asyncio
import logging
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

ADMIN_SECRET = "autoai-admin-2024"


def check_secret(secret: Optional[str]):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Zabranjen pristup")


@router.post("/scrape/{portal}")
async def trigger_scrape(portal: str, secret: Optional[str] = Header(None, alias="x-admin-secret")):
    check_secret(secret)
    return await _run_scraper(portal)


@router.get("/scrape/{portal}/run")
async def trigger_scrape_get(portal: str, secret: str):
    """
    GET verzija — otvori direktno u browseru:
    /api/v1/admin/scrape/willhaben/run?secret=autoai-admin-2024
    """
    check_secret(secret)
    return await _run_scraper(portal)


async def _run_scraper(portal: str):
    allowed = ["willhaben", "mobile_de"]
    if portal not in allowed:
        raise HTTPException(status_code=400, detail=f"Portal mora biti jedan od: {allowed}")

    try:
        if portal == "willhaben":
            from app.scrapers.willhaben import WillhabenScraper
            scraper = WillhabenScraper()
        elif portal == "mobile_de":
            from app.scrapers.mobile_de import MobileDeScraper
            scraper = MobileDeScraper()

        logger.info(f"🕷️ Ručno pokretanje scrapera: {portal}")
        listings = await scraper.scrape_listings({}, max_pages=3)

        from app.core.db import SessionLocal
        from app.core.celery_tasks import save_listings
        db = SessionLocal()
        try:
            new_count, updated_count = save_listings(db, listings)
        finally:
            db.close()

        logger.info(f"✅ {portal}: {new_count} novih, {updated_count} ažuriranih")
        return {
            "status": "ok",
            "portal": portal,
            "found": len(listings),
            "new": new_count,
            "updated": updated_count,
        }

    except Exception as e:
        logger.error(f"❌ Greška: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape/status")
async def scrape_status(secret: str):
    check_secret(secret)

    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func

    db = SessionLocal()
    try:
        rows = (
            db.query(Listing.source, func.count(Listing.id))
            .filter(Listing.is_active == True)
            .group_by(Listing.source)
            .all()
        )
        return {
            "status": "ok",
            "sources": {source: count for source, count in rows},
            "total": sum(count for _, count in rows),
        }
    finally:
        db.close()

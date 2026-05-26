import asyncio
import logging
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

# Tajni ključ za zaštitu — postavi isti u Railway Environment Variables
# kao ADMIN_SECRET=neka_tajna_vrednost
ADMIN_SECRET = "autoai-admin-2024"


def check_secret(secret: Optional[str]):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Zabranjen pristup")


@router.post("/scrape/{portal}")
async def trigger_scrape(portal: str, secret: Optional[str] = Header(None, alias="x-admin-secret")):
    """
    Ručno pokretanje scrapera za određeni portal.
    Pozovi sa headerom: x-admin-secret: autoai-admin-2024

    Portali: willhaben, mobile_de
    """
    check_secret(secret)

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

        # Pokreni scraper (max 3 stranice za brzi test)
        listings = await scraper.scrape_listings({}, max_pages=3)

        # Sačuvaj u bazu
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
async def scrape_status(secret: Optional[str] = Header(None, alias="x-admin-secret")):
    """Statistika — koliko oglasa ima po portalu."""
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


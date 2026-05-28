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


async def _run_scraper(portal: str):
    allowed = [
        "willhaben", "autoscout24", "marktplaats", "2dehands",
        "subito", "leboncoin", "kleinanzeigen", "bilbasen", "mobile_de"
    ]
    if portal not in allowed:
        raise HTTPException(status_code=400, detail=f"Portal mora biti jedan od: {allowed}")
    try:
        if portal == "willhaben":
            from app.scrapers.willhaben import WillhabenScraper
            scraper = WillhabenScraper()
        elif portal == "autoscout24":
            from app.scrapers.autoscout24 import AutoScout24Scraper
            scraper = AutoScout24Scraper()
        elif portal == "marktplaats":
            from app.scrapers.marktplaats import MarktplaatsScraper
            scraper = MarktplaatsScraper()
        elif portal == "2dehands":
            from app.scrapers.tweedehands import TweedehandsScraper
            scraper = TweedehandsScraper()
        elif portal == "subito":
            from app.scrapers.subito import SubitoScraper
            scraper = SubitoScraper()
        elif portal == "leboncoin":
            from app.scrapers.leboncoin import LeBonCoinScraper
            scraper = LeBonCoinScraper()
        elif portal == "kleinanzeigen":
            from app.scrapers.kleinanzeigen import KleinanzeigenScraper
            scraper = KleinanzeigenScraper()
        elif portal == "bilbasen":
            from app.scrapers.bilbasen import BilbasenScraper
            scraper = BilbasenScraper()
        else:
            from app.scrapers.mobile_de import MobileDeScraper
            scraper = MobileDeScraper()

        listings = await scraper.scrape_listings({}, max_pages=3)

        from app.core.db import SessionLocal
        from app.models import Listing
        db = SessionLocal()
        try:
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
                    new_url = data.get("url")
                    if new_url:
                        existing.url = new_url
                    updated_count += 1
                else:
                    listing = Listing(**{k: v for k, v in data.items() if hasattr(Listing, k) and v is not None})
                    db.add(listing)
                    new_count += 1
            db.commit()
        finally:
            db.close()

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


@router.get("/stats/price-ratings")
async def price_rating_stats(secret: str):
    """Statistika price_rating distribucije"""
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func
    db = SessionLocal()
    try:
        total  = db.query(func.count(Listing.id)).filter(Listing.is_active == True).scalar()
        rated  = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price_rating != None).scalar()
        ratings = dict(
            db.query(Listing.price_rating, func.count(Listing.id))
            .filter(Listing.is_active == True, Listing.price_rating != None)
            .group_by(Listing.price_rating).all()
        )
        by_source = {}
        sources = db.query(Listing.source).filter(Listing.is_active == True).distinct().all()
        for (src,) in sources:
            r = db.query(func.count(Listing.id)).filter(
                Listing.is_active == True,
                Listing.source == src,
                Listing.price_rating != None,
            ).scalar()
            t = db.query(func.count(Listing.id)).filter(
                Listing.is_active == True,
                Listing.source == src,
            ).scalar()
            by_source[src] = {"rated": r, "total": t, "pct": round(r/t*100, 1) if t else 0}
        return {
            "total":        total,
            "rated":        rated,
            "unrated":      total - rated,
            "pct_rated":    round(rated / total * 100, 1) if total else 0,
            "distribution": ratings,
            "by_source":    by_source,
        }
    finally:
        db.close()


@router.get("/cleanup/source")
async def cleanup_by_source(source: str, secret: str, deactivate_only: bool = False):
    """Briše ili deaktivira sve oglase određenog izvora"""
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    db = SessionLocal()
    try:
        q = db.query(Listing).filter(Listing.source == source)
        count = q.count()
        if deactivate_only:
            q.update({"is_active": False})
            db.commit()
            return {"status": "ok", "action": "deactivated", "source": source, "count": count}
        else:
            q.delete()
            db.commit()
            return {"status": "ok", "action": "deleted", "source": source, "count": count}
    finally:
        db.close()


@router.get("/cleanup/bad-prices")
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
        return {"status": "ok", "deleted": count}
    finally:
        db.close()


@router.get("/cleanup/old-listings")
async def cleanup_old_listings(secret: str, days: int = 14):
    """Deaktivira oglase koje nismo videli duže od N dana"""
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = db.query(Listing).filter(
            Listing.last_seen_at < cutoff,
            Listing.is_active == True,
        ).update({"is_active": False})
        db.commit()
        return {"status": "ok", "deactivated": count, "older_than_days": days}
    finally:
        db.close()


@router.get("/fix/willhaben-urls")
async def fix_willhaben_urls(secret: str):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(
            Listing.source == "willhaben",
            Listing.url.like("https://www.willhaben.at/gebrauchtwagen/%")
        ).all()
        count = 0
        for l in listings:
            l.url = l.url.replace(
                "https://www.willhaben.at/gebrauchtwagen/",
                "https://www.willhaben.at/iad/gebrauchtwagen/"
            )
            count += 1
        db.commit()
        return {"status": "ok", "fixed": count}
    finally:
        db.close()


@router.get("/db/overview")
async def db_overview(secret: str):
    """Kompletan pregled stanja baze"""
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func
    db = SessionLocal()
    try:
        total_active = db.query(func.count(Listing.id)).filter(Listing.is_active == True).scalar()
        total_all    = db.query(func.count(Listing.id)).scalar()

        by_source = dict(
            db.query(Listing.source, func.count(Listing.id))
            .filter(Listing.is_active == True)
            .group_by(Listing.source).all()
        )

        with_price     = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price != None).scalar()
        with_year      = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.year != None).scalar()
        with_mileage   = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.mileage != None).scalar()
        with_fuel      = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.fuel_type != None).scalar()
        with_images    = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.images != None, Listing.images != '[]').scalar()
        with_rating    = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price_rating != None).scalar()

        avg_price = db.query(func.avg(Listing.price)).filter(
            Listing.is_active == True, Listing.price != None, Listing.price > 0
        ).scalar()

        return {
            "total_active":    total_active,
            "total_all":       total_all,
            "inactive":        total_all - total_active,
            "by_source":       by_source,
            "completeness": {
                "with_price":   f"{with_price} ({round(with_price/total_active*100,1) if total_active else 0}%)",
                "with_year":    f"{with_year} ({round(with_year/total_active*100,1) if total_active else 0}%)",
                "with_mileage": f"{with_mileage} ({round(with_mileage/total_active*100,1) if total_active else 0}%)",
                "with_fuel":    f"{with_fuel} ({round(with_fuel/total_active*100,1) if total_active else 0}%)",
                "with_images":  f"{with_images} ({round(with_images/total_active*100,1) if total_active else 0}%)",
                "with_rating":  f"{with_rating} ({round(with_rating/total_active*100,1) if total_active else 0}%)",
            },
            "avg_price_eur": round(float(avg_price), 0) if avg_price else None,
        }
    finally:
        db.close()

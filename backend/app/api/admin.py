import logging
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def check_secret(secret: Optional[str]):
    configured = (settings.AUTOAI_ADMIN_SECRET or "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="AUTOAI_ADMIN_SECRET is not configured")
    if not secrets.compare_digest(secret or "", configured):
        raise HTTPException(status_code=403, detail="Zabranjen pristup")


async def _run_scraper(portal: str, max_pages: int = 3):
    allowed = [
        "willhaben", "autoscout24", "marktplaats", "2dehands",
        "subito", "leboncoin", "kleinanzeigen", "bilbasen", "mobile_de",
        "lacentrale", "tutti",
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
        elif portal == "kleinanzeigen":
            from app.scrapers.kleinanzeigen import KleinanzeigenScraper
            scraper = KleinanzeigenScraper()
        elif portal == "subito":
            from app.scrapers.subito import SubitoScraper
            scraper = SubitoScraper()
        elif portal == "leboncoin":
            from app.scrapers.leboncoin import LeBonCoinScraper
            scraper = LeBonCoinScraper()
        elif portal == "bilbasen":
            from app.scrapers.bilbasen import BilbasenScraper
            scraper = BilbasenScraper()
        elif portal == "lacentrale":
            from app.scrapers.lacentrale import LaCentraleScraper
            scraper = LaCentraleScraper()
        elif portal == "tutti":
            from app.scrapers.tutti import TuttiScraper
            scraper = TuttiScraper()
        else:
            from app.scrapers.mobile_de import MobileDeScraper
            scraper = MobileDeScraper()

        listings = await scraper.scrape_listings({}, max_pages=max_pages)

        from app.core.db import SessionLocal
        from app.models import Listing
        db = SessionLocal()
        try:
            new_count = 0
            updated_count = 0
            skipped_no_price = 0
            for data in listings:
                external_id = data.get("external_id")
                if not external_id:
                    continue
                # ✅ Preskoči oglase bez cene
                price = data.get("price")
                if not price or float(price) <= 0:
                    skipped_no_price += 1
                    continue
                existing = db.query(Listing).filter(Listing.external_id == external_id).first()
                if existing:
                    existing.last_seen_at = datetime.utcnow()
                    existing.is_active = True
                    if price and existing.price != float(price):
                        existing.price = price
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

        return {
            "status": "ok", "portal": portal,
            "found": len(listings), "new": new_count,
            "updated": updated_count, "skipped_no_price": skipped_no_price,
        }
    except Exception as e:
        logger.error(f"❌ {portal}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape/{portal}/run")
async def trigger_scrape_get(portal: str, secret: str, max_pages: int = 3):
    check_secret(secret)
    return await _run_scraper(portal, max_pages=max_pages)


@router.get("/scrape/all/run")
async def scrape_all_portals(secret: str, max_pages: int = 5):
    """Pokreni sve aktivne scrapers odjednom — za punjenje na 50k oglasa."""
    check_secret(secret)
    portals = ["autoscout24", "willhaben", "marktplaats", "2dehands", "kleinanzeigen"]
    results = {}
    total_new = 0
    for portal in portals:
        try:
            result = await _run_scraper(portal, max_pages=max_pages)
            results[portal] = result
            total_new += result.get("new", 0)
        except Exception as e:
            results[portal] = {"status": "error", "error": str(e)}
    return {"status": "ok", "total_new": total_new, "by_portal": results}


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


# ✅ NOVI ENDPOINT — Kreira DB indekse za brzu pretragu
@router.get("/db/create-indexes")
async def create_indexes(secret: str):
    """Kreira PostgreSQL indekse za brzu pretragu 50k+ oglasa."""
    check_secret(secret)
    from app.core.db import engine
    from sqlalchemy import text

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_listings_make        ON listings(make)",
        "CREATE INDEX IF NOT EXISTS idx_listings_model       ON listings(model)",
        "CREATE INDEX IF NOT EXISTS idx_listings_price       ON listings(price)",
        "CREATE INDEX IF NOT EXISTS idx_listings_year        ON listings(year)",
        "CREATE INDEX IF NOT EXISTS idx_listings_mileage     ON listings(mileage)",
        "CREATE INDEX IF NOT EXISTS idx_listings_fuel_type   ON listings(fuel_type)",
        "CREATE INDEX IF NOT EXISTS idx_listings_country     ON listings(country)",
        "CREATE INDEX IF NOT EXISTS idx_listings_source      ON listings(source)",
        "CREATE INDEX IF NOT EXISTS idx_listings_is_active   ON listings(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_listings_price_rating ON listings(price_rating)",
        "CREATE INDEX IF NOT EXISTS idx_listings_scraped_at  ON listings(scraped_at DESC)",
        # Kompozitni indeksi za najčešće upite
        "CREATE INDEX IF NOT EXISTS idx_listings_active_price ON listings(is_active, price) WHERE is_active = TRUE AND price IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_listings_active_make  ON listings(is_active, make)  WHERE is_active = TRUE",
    ]

    created = []
    errors  = []
    with engine.connect() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
                idx_name = idx_sql.split("idx_")[1].split(" ")[0]
                created.append(f"idx_{idx_name}")
            except Exception as e:
                errors.append({"sql": idx_sql[:60], "error": str(e)})

    return {
        "status": "ok",
        "created": len(created),
        "indexes": created,
        "errors": errors,
    }


@router.get("/db/overview")
async def db_overview(secret: str):
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
            .filter(Listing.is_active == True).group_by(Listing.source).all()
        )
        with_price   = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price != None).scalar()
        with_year    = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.year != None).scalar()
        with_mileage = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.mileage != None).scalar()
        with_fuel    = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.fuel_type != None).scalar()
        with_images  = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.images != None, Listing.images != '[]').scalar()
        with_rating  = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price_rating != None).scalar()
        avg_price    = db.query(func.avg(Listing.price)).filter(Listing.is_active == True, Listing.price != None, Listing.price > 0).scalar()
        def pct(n): return round(n/total_active*100, 1) if total_active else 0
        return {
            "total_active": total_active, "total_all": total_all,
            "inactive": total_all - total_active, "by_source": by_source,
            "completeness": {
                "with_price":   f"{with_price} ({pct(with_price)}%)",
                "with_year":    f"{with_year} ({pct(with_year)}%)",
                "with_mileage": f"{with_mileage} ({pct(with_mileage)}%)",
                "with_fuel":    f"{with_fuel} ({pct(with_fuel)}%)",
                "with_images":  f"{with_images} ({pct(with_images)}%)",
                "with_rating":  f"{with_rating} ({pct(with_rating)}%)",
            },
            "avg_price_eur": round(float(avg_price), 0) if avg_price else None,
        }
    finally:
        db.close()


@router.get("/stats/price-ratings")
async def price_rating_stats(secret: str):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func
    db = SessionLocal()
    try:
        total = db.query(func.count(Listing.id)).filter(Listing.is_active == True).scalar()
        rated = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.price_rating != None).scalar()
        ratings = dict(
            db.query(Listing.price_rating, func.count(Listing.id))
            .filter(Listing.is_active == True, Listing.price_rating != None)
            .group_by(Listing.price_rating).all()
        )
        by_source = {}
        sources = db.query(Listing.source).filter(Listing.is_active == True).distinct().all()
        for (src,) in sources:
            r = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.source == src, Listing.price_rating != None).scalar()
            t = db.query(func.count(Listing.id)).filter(Listing.is_active == True, Listing.source == src).scalar()
            by_source[src] = {"rated": r, "total": t, "pct": round(r/t*100, 1) if t else 0}
        return {
            "total": total, "rated": rated, "unrated": total - rated,
            "pct_rated": round(rated/total*100, 1) if total else 0,
            "distribution": ratings, "by_source": by_source,
        }
    finally:
        db.close()


@router.get("/cleanup/source")
async def cleanup_by_source(source: str, secret: str, deactivate_only: bool = False):
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
        count = db.query(Listing).filter(Listing.price < 500).delete()
        db.commit()
        return {"status": "ok", "deleted": count}
    finally:
        db.close()


@router.get("/cleanup/old-listings")
async def cleanup_old_listings(secret: str, days: int = 30):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = db.query(Listing).filter(
            Listing.last_seen_at < cutoff, Listing.is_active == True,
        ).update({"is_active": False})
        db.commit()
        return {"status": "ok", "deactivated": count, "older_than_days": days}
    finally:
        db.close()


@router.get("/cleanup/emoji-makes")
async def cleanup_emoji_makes(secret: str):
    """Uklanja emoji iz make/model polja."""
    check_secret(secret)
    import re
    from app.core.db import SessionLocal
    from app.models import Listing

    def strip_emoji(text: str) -> str:
        if not text:
            return text
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            u"\U0001f926-\U0001f937"
            u"\U00010000-\U0010ffff"
            u"\u2640-\u2642"
            u"\u2600-\u2B55"
            u"\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
            "]+",
            flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub('', text).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else text

    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(Listing.is_active == True).all()
        count = 0
        for l in listings:
            changed = False
            if l.make:
                new_make = strip_emoji(l.make)
                if new_make != l.make:
                    l.make = new_make
                    changed = True
            if l.model:
                new_model = strip_emoji(l.model)
                if new_model != l.model:
                    l.model = new_model
                    changed = True
            if changed:
                count += 1
        db.commit()
        return {"status": "ok", "cleaned": count, "total_checked": len(listings)}
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


@router.get("/ai/train")
async def train_price_model(secret: str, min_listings: int = 300):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    import pandas as pd
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(
            Listing.price != None, Listing.year != None, Listing.mileage != None,
            Listing.is_active == True, Listing.price > 500, Listing.price < 300000,
        ).all()
        if len(listings) < min_listings:
            return {"status": "insufficient_data", "available": len(listings), "required": min_listings}
        df = pd.DataFrame([{
            "make": l.make or "", "model": l.model or "", "year": l.year or 0,
            "mileage": l.mileage or 0, "fuel_type": l.fuel_type or "",
            "transmission": l.transmission or "", "country": l.country or "",
            "engine_cc": l.engine_cc or 0, "price": float(l.price),
        } for l in listings])
        from app.ai.price_estimator import PriceEstimator
        estimator = PriceEstimator()
        result = estimator.train(df)
        return {"status": "ok", "trained_on": len(listings), **result}
    except Exception as e:
        logger.error(f"❌ Treniranje neuspelo: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/ai/status")
async def ai_model_status(secret: str):
    check_secret(secret)
    from pathlib import Path
    from app.core.db import SessionLocal
    from app.models import Listing
    from sqlalchemy import func
    model_path = Path("/app/app/ai/models/price_model.pkl")
    db = SessionLocal()
    try:
        total = db.query(func.count(Listing.id)).filter(
            Listing.is_active == True, Listing.price != None,
            Listing.year != None, Listing.mileage != None,
        ).scalar()
        rated = db.query(func.count(Listing.id)).filter(
            Listing.is_active == True, Listing.price_rating != None,
        ).scalar()
        return {
            "model_exists": model_path.exists(),
            "model_size_kb": round(model_path.stat().st_size/1024, 1) if model_path.exists() else 0,
            "trainable_listings": total, "rated_listings": rated,
            "ready_to_train": total >= 300,
        }
    finally:
        db.close()


@router.get("/ai/apply-ratings")
async def apply_ratings_to_all(secret: str, limit: int = 1000):
    check_secret(secret)
    from app.core.db import SessionLocal
    from app.models import Listing
    from app.ai.price_estimator import PriceEstimator
    estimator = PriceEstimator.load()
    if not estimator.is_trained:
        raise HTTPException(status_code=400, detail="Model nije istreniran. Pokreni /ai/train prvo.")
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(
            Listing.is_active == True, Listing.price_rating == None,
            Listing.price != None, Listing.year != None,
        ).limit(limit).all()
        count = 0
        for l in listings:
            try:
                result = estimator.predict({
                    "make": l.make or "", "model": l.model or "", "year": l.year or 0,
                    "mileage": l.mileage or 0, "fuel_type": l.fuel_type or "",
                    "transmission": l.transmission or "", "country": l.country or "",
                    "engine_cc": l.engine_cc or 0,
                })
                l.price_estimated = result["estimated_price"]
                if l.price and result["estimated_price"]:
                    delta = ((float(l.price) - result["estimated_price"]) / result["estimated_price"]) * 100
                    l.price_delta_pct = round(delta, 2)
                    if delta < -15:   l.price_rating = "great"
                    elif delta < -5:  l.price_rating = "good"
                    elif delta < 5:   l.price_rating = "fair"
                    elif delta < 15:  l.price_rating = "high"
                    else:             l.price_rating = "overpriced"
                count += 1
            except Exception as e:
                logger.warning(f"Rating greška za {l.id}: {e}")
        db.commit()
        return {"status": "ok", "rated": count, "limit": limit}
    finally:
        db.close()

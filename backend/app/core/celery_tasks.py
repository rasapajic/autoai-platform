from celery import Celery
from celery.schedules import crontab
from datetime import datetime
import logging

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Listing, ScraperRun

logger = logging.getLogger(__name__)

celery_app = Celery(
    "autoai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Belgrade",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    # ✅ Willhaben (Austrija) — svakih 6 sati
    "scrape-willhaben": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": ("willhaben", {}),
    },
    # ✅ AutoScout24 (EU) — svakih 6 sati offset 3h
    "scrape-autoscout24": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="3,9,15,21"),
        "args": ("autoscout24", {}),
    },
    # ✅ Marktplaats (Holandija) — svakih 8 sati
    "scrape-marktplaats": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=30, hour="1,9,17"),
        "args": ("marktplaats", {}),
    },
    # 🚫 Mobile.de — blokira server-side zahteve (403)
    # "scrape-mobile-de": { ... },
    # Cleanup starih oglasa — svaki dan u ponoć
    "cleanup-old-listings": {
        "task": "app.core.celery_tasks.cleanup_old_listings",
        "schedule": crontab(minute=0, hour=0),
    },
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_portal(self, portal: str, filters: dict):
    db = SessionLocal()
    run = ScraperRun(portal=portal, status="running")
    db.add(run)
    db.commit()

    try:
        logger.info(f"🕷️ Počinjem scraping: {portal}")

        if portal == "willhaben":
            from app.scrapers.willhaben import WillhabenScraper
            scraper = WillhabenScraper()
        elif portal == "autoscout24":
            from app.scrapers.autoscout24 import AutoScout24Scraper
            scraper = AutoScout24Scraper()
        elif portal == "marktplaats":
            from app.scrapers.marktplaats import MarktplaatsScraper
            scraper = MarktplaatsScraper()
        elif portal == "mobile_de":
            from app.scrapers.mobile_de import MobileDeScraper
            scraper = MobileDeScraper()
        else:
            raise ValueError(f"Nepoznat portal: {portal}")

        import asyncio
        listings = asyncio.run(scraper.scrape_listings(filters, max_pages=10))
        run.listings_found = len(listings)

        new_count, updated_count = save_listings(db, listings)
        run.listings_new = new_count
        run.listings_updated = updated_count
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(f"✅ {portal}: {new_count} novih, {updated_count} ažuriranih")

        if new_count > 0:
            estimate_prices.delay(portal)

        return {"portal": portal, "found": len(listings), "new": new_count, "updated": updated_count}

    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.error(f"❌ Greška pri scrapingu {portal}: {exc}")
        raise self.retry(exc=exc)

    finally:
        db.close()


def save_listings(db, listings: list) -> tuple:
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


@celery_app.task
def estimate_prices(portal: str = None):
    db = SessionLocal()
    try:
        query = db.query(Listing).filter(Listing.price_estimated == None, Listing.is_active == True)
        if portal:
            query = query.filter(Listing.source == portal)
        listings = query.limit(500).all()
        if not listings:
            return {"estimated": 0}

        from app.ai.price_estimator import PriceEstimator
        estimator = PriceEstimator.load()

        count = 0
        for listing in listings:
            try:
                result = estimator.predict({
                    "make": listing.make or "", "model": listing.model or "",
                    "year": listing.year or 0, "mileage": listing.mileage or 0,
                    "fuel_type": listing.fuel_type or "", "transmission": listing.transmission or "",
                    "country": listing.country or "", "engine_cc": listing.engine_cc or 0,
                })
                listing.price_estimated = result["estimated_price"]
                if listing.price and result["estimated_price"]:
                    delta = ((float(listing.price) - result["estimated_price"]) / result["estimated_price"]) * 100
                    listing.price_delta_pct = round(delta, 2)
                    if delta < -15: listing.price_rating = "great"
                    elif delta < -5: listing.price_rating = "good"
                    elif delta < 5: listing.price_rating = "fair"
                    elif delta < 15: listing.price_rating = "high"
                    else: listing.price_rating = "overpriced"
                count += 1
            except Exception as e:
                logger.warning(f"Procena nije uspela za {listing.id}: {e}")

        db.commit()
        logger.info(f"💰 Procenio cene za {count} oglasa")
        return {"estimated": count}
    finally:
        db.close()


@celery_app.task
def cleanup_old_listings():
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        count = db.query(Listing).filter(
            Listing.last_seen_at < cutoff, Listing.is_active == True
        ).update({"is_active": False})
        db.commit()
        logger.info(f"🧹 Deaktivirao {count} starih oglasa")
        return {"deactivated": count}
    finally:
        db.close()

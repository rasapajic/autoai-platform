from celery import Celery
from celery.schedules import crontab
from datetime import datetime
import logging

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Listing, ScraperRun
from app.scrapers.autoscout24 import AutoScout24Scraper
from app.scrapers.polovni import PolvoniScraper
from app.scrapers.mobile_de import MobileDeScraper

logger = logging.getLogger(__name__)

# ─── Celery setup ─────────────────────────────────────────────
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

# ─── Automatski raspored scrapinga ────────────────────────────
celery_app.conf.beat_schedule = {
    # AutoScout24 — svakih 6 sati
    "scrape-autoscout24": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": ("autoscout24", {}),
    },
    # Polovniautomobili — svakih 4 sata
    "scrape-polovni": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=30, hour="*/4"),
        "args": ("polovni", {}),
    },
    # Mobile.de — svakih 6 sati
    "scrape-mobile-de": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="1,7,13,19"),
        "args": ("mobile_de", {}),
    },
    # Cleanup starih oglasa — svaki dan u ponoć
    "cleanup-old-listings": {
        "task": "app.core.celery_tasks.cleanup_old_listings",
        "schedule": crontab(minute=0, hour=0),
    },
}


# ─── Scraping task ────────────────────────────────────────────
@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_portal(self, portal: str, filters: dict):
    """
    Glavni task za scraping jednog portala.
    Automatski se ponovi do 3 puta ako dođe do greške.
    """
    db = SessionLocal()
    run = ScraperRun(portal=portal, status="running")
    db.add(run)
    db.commit()

    try:
        logger.info(f"🕷️ Počinjem scraping: {portal}")

        # Izaberi pravi scraper
        scrapers = {
            "autoscout24": AutoScout24Scraper(),
            "polovni":     PolvoniScraper(),
            "mobile_de":   MobileDeScraper(),
        }

        if portal not in scrapers:
            raise ValueError(f"Nepoznat portal: {portal}")

        scraper = scrapers[portal]

        # Scraping
        import asyncio
        listings = asyncio.run(scraper.scrape_listings(filters, max_pages=10))
        run.listings_found = len(listings)

        # Čuvanje u bazu
        new_count, updated_count = save_listings(db, listings)
        run.listings_new = new_count
        run.listings_updated = updated_count
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(f"✅ {portal}: {new_count} novih, {updated_count} ažuriranih od {len(listings)}")

        # Pokreni procenu cene za nove oglase
        if new_count > 0:
            estimate_prices.delay(portal)

        return {
            "portal": portal,
            "found": len(listings),
            "new": new_count,
            "updated": updated_count,
        }

    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.error(f"❌ Greška pri scrapingu {portal}: {exc}")
        raise self.retry(exc=exc)

    finally:
        db.close()


def save_listings(db, listings: list[dict]) -> tuple[int, int]:
    """Čuva oglase u bazu — insertuje nove, ažurira postojeće."""
    new_count = 0
    updated_count = 0

    for data in listings:
        external_id = data.get("external_id")
        if not external_id:
            continue

        existing = db.query(Listing).filter(
            Listing.external_id == external_id
        ).first()

        if existing:
            # Ažuriraj cenu i last_seen
            old_price = existing.price
            new_price = data.get("price")

            existing.last_seen_at = datetime.utcnow()
            existing.is_active = True

            if new_price and old_price != float(new_price):
                existing.price = new_price  # trigger čuva price_history

            updated_count += 1
        else:
            # Novi oglas
            listing = Listing(**{
                k: v for k, v in data.items()
                if hasattr(Listing, k) and v is not None
            })
            db.add(listing)
            new_count += 1

    db.commit()
    return new_count, updated_count


# ─── Procena cene task ────────────────────────────────────────
@celery_app.task
def estimate_prices(portal: str = None):
    """
    Pokretanje ML modela za procenu cene svih oglasa
    koji još nemaju procenu.
    """
    db = SessionLocal()
    try:
        query = db.query(Listing).filter(
            Listing.price_estimated == None,
            Listing.is_active == True,
        )
        if portal:
            query = query.filter(Listing.source == portal)

        listings = query.limit(500).all()

        if not listings:
            return {"estimated": 0}

        # Uvezi model (lazy import da ne usporava ostale taskove)
        from app.ai.price_estimator import PriceEstimator
        estimator = PriceEstimator.load()

        count = 0
        for listing in listings:
            try:
                result = estimator.predict({
                    "make":         listing.make or "",
                    "model":        listing.model or "",
                    "year":         listing.year or 0,
                    "mileage":      listing.mileage or 0,
                    "fuel_type":    listing.fuel_type or "",
                    "transmission": listing.transmission or "",
                    "country":      listing.country or "",
                    "engine_cc":    listing.engine_cc or 0,
                })

                listing.price_estimated = result["estimated_price"]
                if listing.price and result["estimated_price"]:
                    delta = ((float(listing.price) - result["estimated_price"])
                             / result["estimated_price"]) * 100
                    listing.price_delta_pct = round(delta, 2)

                    if delta < -15:
                        listing.price_rating = "great"
                    elif delta < -5:
                        listing.price_rating = "good"
                    elif delta < 5:
                        listing.price_rating = "fair"
                    elif delta < 15:
                        listing.price_rating = "high"
                    else:
                        listing.price_rating = "overpriced"

                count += 1
            except Exception as e:
                logger.warning(f"Procena nije uspela za {listing.id}: {e}")

        db.commit()
        logger.info(f"💰 Procenio cene za {count} oglasa")
        return {"estimated": count}

    finally:
        db.close()


# ─── Cleanup task ─────────────────────────────────────────────
@celery_app.task
def cleanup_old_listings():
    """Deaktivira oglase koje nismo vidjeli >7 dana."""
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        count = db.query(Listing).filter(
            Listing.last_seen_at < cutoff,
            Listing.is_active == True,
        ).update({"is_active": False})
        db.commit()
        logger.info(f"🧹 Deaktivirao {count} starih oglasa")
        return {"deactivated": count}
    finally:
        db.close()

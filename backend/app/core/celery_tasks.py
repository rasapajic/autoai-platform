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

# ✅ BEAT SCHEDULE — svi aktivni portali, razmaknutih startova da ne udaraju u isto vreme
celery_app.conf.beat_schedule = {

    # ═══════════════════════════════════════════
    # AutoScout24 — najveći EU portal, 4x dnevno
    # ═══════════════════════════════════════════
    "scrape-autoscout24": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="0,6,12,18"),
        "args": ("autoscout24", {"max_pages": 50}),
    },

    # ═══════════════════════════════════════════
    # Willhaben — Austrija, 4x dnevno
    # ═══════════════════════════════════════════
    "scrape-willhaben": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=15, hour="1,7,13,19"),
        "args": ("willhaben", {"max_pages": 30}),
    },

    # ═══════════════════════════════════════════
    # Marktplaats — Holandija, 3x dnevno
    # ═══════════════════════════════════════════
    "scrape-marktplaats": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=30, hour="2,10,18"),
        "args": ("marktplaats", {"max_pages": 30}),
    },

    # ═══════════════════════════════════════════
    # Kleinanzeigen — Nemačka, 3x dnevno
    # ═══════════════════════════════════════════
    "scrape-kleinanzeigen": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=45, hour="2,10,18"),
        "args": ("kleinanzeigen", {"max_pages": 30}),
    },

    # ═══════════════════════════════════════════
    # Tweedehands — Belgija/Holandija, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-tweedehands": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="3,15"),
        "args": ("tweedehands", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # LaCentrale — Francuska, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-lacentrale": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=15, hour="4,16"),
        "args": ("lacentrale", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # LeBonCoin — Francuska, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-leboncoin": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=30, hour="4,16"),
        "args": ("leboncoin", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # Subito — Italija, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-subito": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=45, hour="4,16"),
        "args": ("subito", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # Tutti — Švajcarska, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-tutti": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour="5,17"),
        "args": ("tutti", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # Bilbasen — Danska, 1x dnevno
    # ═══════════════════════════════════════════
    "scrape-bilbasen": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=0, hour=8),
        "args": ("bilbasen", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # Polovni — Srbija/region, 2x dnevno
    # ═══════════════════════════════════════════
    "scrape-polovni": {
        "task": "app.core.celery_tasks.scrape_portal",
        "schedule": crontab(minute=30, hour="8,20"),
        "args": ("polovni", {"max_pages": 20}),
    },

    # ═══════════════════════════════════════════
    # Procena cena — svakih sat vremena
    # ═══════════════════════════════════════════
    "estimate-prices-hourly": {
        "task": "app.core.celery_tasks.estimate_prices",
        "schedule": crontab(minute=0),
        "args": (),
    },

    # ═══════════════════════════════════════════
    # Cleanup starih oglasa — svaki dan u 23:00
    # ═══════════════════════════════════════════
    "cleanup-old-listings": {
        "task": "app.core.celery_tasks.cleanup_old_listings",
        "schedule": crontab(minute=0, hour=23),
    },
}


# ─────────────────────────────────────────────────────
# PORTAL → SCRAPER MAPA
# ─────────────────────────────────────────────────────
PORTAL_MAP = {
    "autoscout24":   ("app.scrapers.autoscout24",  "AutoScout24Scraper"),
    "willhaben":     ("app.scrapers.willhaben",     "WillhabenScraper"),
    "marktplaats":   ("app.scrapers.marktplaats",   "MarktplaatsScraper"),
    "kleinanzeigen": ("app.scrapers.kleinanzeigen", "KleinanzeigenScraper"),
    "tweedehands":   ("app.scrapers.tweedehands",   "TweedehandsScraper"),
    "lacentrale":    ("app.scrapers.lacentrale",    "LaCentraleScraper"),
    "leboncoin":     ("app.scrapers.leboncoin",     "LeBonCoinScraper"),
    "subito":        ("app.scrapers.subito",        "SubitoScraper"),
    "tutti":         ("app.scrapers.tutti",         "TuttiScraper"),
    "bilbasen":      ("app.scrapers.bilbasen",      "BilbasenScraper"),
    "polovni":       ("app.scrapers.polovni",       "PlovniScraper"),
    "mobile_de":     ("app.scrapers.mobile_de",     "MobileDeScraper"),
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_portal(self, portal: str, filters: dict):
    """Glavni task za scraping jednog portala."""
    db = SessionLocal()
    run = ScraperRun(portal=portal, status="running")
    db.add(run)
    db.commit()

    try:
        logger.info(f"🕷️  START scraping: {portal}")

        if portal not in PORTAL_MAP:
            raise ValueError(f"Nepoznat portal: {portal}")

        module_path, class_name = PORTAL_MAP[portal]
        import importlib
        module = importlib.import_module(module_path)
        ScraperClass = getattr(module, class_name)
        scraper = ScraperClass()

        # ✅ max_pages iz filtera ili default 30
        max_pages = filters.pop("max_pages", 30)

        import asyncio
        listings = asyncio.run(scraper.scrape_listings(filters, max_pages=max_pages))
        run.listings_found = len(listings)

        new_count, updated_count = save_listings(db, listings)
        run.listings_new      = new_count
        run.listings_updated  = updated_count
        run.status            = "success"
        run.finished_at       = datetime.utcnow()
        db.commit()

        logger.info(f"✅ {portal}: {new_count} novih, {updated_count} ažuriranih od {len(listings)} pronađenih")

        if new_count > 0:
            estimate_prices.delay(portal)

        return {
            "portal":   portal,
            "found":    len(listings),
            "new":      new_count,
            "updated":  updated_count,
        }

    except Exception as exc:
        run.status        = "failed"
        run.error_message = str(exc)[:500]
        run.finished_at   = datetime.utcnow()
        db.commit()
        logger.error(f"❌ Greška pri scrapingu {portal}: {exc}")
        raise self.retry(exc=exc)

    finally:
        db.close()


def save_listings(db, listings: list) -> tuple:
    """Čuva listu oglasa u bazu, vraća (novi, ažurirani)."""
    new_count     = 0
    updated_count = 0

    for data in listings:
        external_id = data.get("external_id")
        if not external_id:
            continue

        existing = db.query(Listing).filter(Listing.external_id == external_id).first()

        if existing:
            existing.last_seen_at = datetime.utcnow()
            existing.is_active    = True
            new_price = data.get("price")
            if new_price and existing.price != float(new_price):
                existing.price = new_price
            updated_count += 1
        else:
            safe_data = {
                k: v for k, v in data.items()
                if hasattr(Listing, k) and v is not None
            }
            listing = Listing(**safe_data)
            db.add(listing)
            new_count += 1

    db.commit()
    return new_count, updated_count


@celery_app.task
def estimate_prices(portal: str = None):
    """Procenjuje cene za oglase koji još nemaju price_estimated."""
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

        from app.ai.price_estimator import PriceEstimator
        estimator = PriceEstimator.load()

        count = 0
        for listing in listings:
            try:
                result = estimator.predict({
                    "make":         listing.make         or "",
                    "model":        listing.model        or "",
                    "year":         listing.year         or 0,
                    "mileage":      listing.mileage      or 0,
                    "fuel_type":    listing.fuel_type    or "",
                    "transmission": listing.transmission or "",
                    "country":      listing.country      or "",
                    "engine_cc":    listing.engine_cc    or 0,
                })
                estimated = result["estimated_price"]
                listing.price_estimated = estimated

                if listing.price and estimated:
                    delta = ((float(listing.price) - estimated) / estimated) * 100
                    listing.price_delta_pct = round(delta, 2)
                    if   delta < -15: listing.price_rating = "great"
                    elif delta <  -5: listing.price_rating = "good"
                    elif delta <   5: listing.price_rating = "fair"
                    elif delta <  15: listing.price_rating = "high"
                    else:             listing.price_rating = "overpriced"
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
    """Deaktivira oglase koje nismo videli >7 dana."""
    from datetime import timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        count = db.query(Listing).filter(
            Listing.last_seen_at < cutoff,
            Listing.is_active   == True,
        ).update({"is_active": False})
        db.commit()
        logger.info(f"🧹 Deaktivirao {count} starih oglasa")
        return {"deactivated": count}
    finally:
        db.close()


@celery_app.task
def scrape_all_portals_now():
    """Ručno pokretanje svih portala odjednom — korisno za inicijalno punjenje baze."""
    portals = [
        ("autoscout24",   50),
        ("willhaben",     30),
        ("marktplaats",   30),
        ("kleinanzeigen", 30),
        ("tweedehands",   20),
        ("lacentrale",    20),
        ("leboncoin",     20),
        ("subito",        20),
        ("tutti",         20),
        ("bilbasen",      20),
        ("polovni",       20),
    ]
    for portal, pages in portals:
        scrape_portal.delay(portal, {"max_pages": pages})
        logger.info(f"🚀 Pokrenuo task za {portal} ({pages} stranica)")

    return {"launched": len(portals)}

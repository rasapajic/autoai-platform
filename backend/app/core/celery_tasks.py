"""
Emergency data-source freeze.

All automated and manual Celery jobs that could add, modify, rate, or delete
external listing data are intentionally disabled. Re-enabling them requires
a documented source-rights review and an explicit code change.
"""

import logging

from celery import Celery

from app.core.config import settings

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

# No scheduled jobs may update external listing data while the legal-source
# freeze is active.
celery_app.conf.beat_schedule = {}


def _disabled_result(action: str, **extra):
    logger.warning("AutoAI data update blocked: %s", action)
    return {
        "status": "disabled",
        "reason": "external_source_rights_not_verified",
        "action": action,
        **extra,
    }


@celery_app.task(bind=True, max_retries=0)
def scrape_portal(self, portal: str, filters: dict | None = None):
    return _disabled_result("scrape_portal", portal=portal, found=0, new=0, updated=0)


def save_listings(db, listings: list) -> tuple[int, int]:
    logger.warning("AutoAI listing write blocked during data-source freeze")
    return 0, 0


@celery_app.task
def estimate_prices(portal: str | None = None):
    return _disabled_result("estimate_prices", portal=portal, estimated=0)


@celery_app.task
def cleanup_old_listings():
    return _disabled_result("cleanup_old_listings", deleted=0)


@celery_app.task
def scrape_all_portals_now():
    return _disabled_result("scrape_all_portals_now", launched=0)

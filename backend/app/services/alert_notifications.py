from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.config import settings
from app.core.email import is_deliverable_email, send_email
from app.models import Alert, Listing, User


MAX_LISTINGS_PER_ALERT = 10
logger = logging.getLogger(__name__)


def run_saved_search_notifications_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        return send_saved_search_notifications(db)
    finally:
        db.close()


def send_saved_search_notifications(db: Session) -> dict[str, int]:
    now = datetime.utcnow()
    alerts = (
        db.query(Alert)
        .join(User, User.id == Alert.user_id)
        .filter(Alert.is_active == True, User.is_active == True)
        .all()
    )

    grouped: dict[User, list[tuple[Alert, list[Listing]]]] = defaultdict(list)

    for alert in alerts:
        if not _frequency_due(alert, now):
            continue

        matches = find_new_matching_listings(db, alert, now)
        if matches:
            grouped[alert.user].append((alert, matches))

    emails_sent = 0
    emails_skipped = 0
    invalid_emails_skipped = 0
    emails_failed = 0
    alerts_notified = 0
    listings_notified = 0

    for user, sections in grouped.items():
        if not is_deliverable_email(user.email):
            emails_skipped += 1
            invalid_emails_skipped += 1
            logger.info("Email notifikacija preskocena zbog invalidne adrese za user_id=%s", user.id)
            continue

        subject = "AutoAI - novi oglasi za tvoje potrage"
        body = build_summary_email(user, sections)

        try:
            sent = send_email(user.email, subject, body)
        except Exception as exc:
            emails_failed += 1
            logger.warning("Email notifikacija nije poslata za user_id=%s: %s", user.id, exc)
            continue

        if sent:
            emails_sent += 1
            for alert, matches in sections:
                alert.last_sent_at = now
                alerts_notified += 1
                listings_notified += len(matches)
        else:
            emails_skipped += 1

    if emails_sent:
        db.commit()

    return {
        "active_alerts_checked": len(alerts),
        "emails_sent": emails_sent,
        "emails_skipped": emails_skipped,
        "invalid_emails_skipped": invalid_emails_skipped,
        "emails_failed": emails_failed,
        "alerts_notified": alerts_notified,
        "listings_notified": listings_notified,
    }


def find_new_matching_listings(db: Session, alert: Alert, now: datetime) -> list[Listing]:
    since = _naive_utc(alert.last_sent_at or alert.created_at) or (now - timedelta(days=1))
    filters = alert.filters or {}

    query = db.query(Listing).filter(
        Listing.is_active == True,
        Listing.first_seen_at > since,
    )

    query_text = filters.get("query_text") or filters.get("query")
    if query_text:
        term = f"%{query_text}%"
        query = query.filter(or_(
            Listing.make.ilike(term),
            Listing.model.ilike(term),
            Listing.variant.ilike(term),
            Listing.description.ilike(term),
        ))

    if filters.get("make"):
        query = query.filter(Listing.make.ilike(f"%{filters['make']}%"))
    if filters.get("model"):
        query = query.filter(Listing.model.ilike(f"%{filters['model']}%"))
    if filters.get("min_price"):
        query = query.filter(Listing.price >= _number(filters["min_price"]))
    if filters.get("max_price"):
        query = query.filter(Listing.price <= _number(filters["max_price"]))
    if filters.get("min_year"):
        query = query.filter(Listing.year >= _number(filters["min_year"]))
    if filters.get("max_year"):
        query = query.filter(Listing.year <= _number(filters["max_year"]))
    if filters.get("min_km"):
        query = query.filter(Listing.mileage >= _number(filters["min_km"]))
    if filters.get("max_km"):
        query = query.filter(Listing.mileage <= _number(filters["max_km"]))
    if filters.get("fuel_type"):
        query = query.filter(Listing.fuel_type == filters["fuel_type"])
    if filters.get("transmission"):
        query = query.filter(Listing.transmission == filters["transmission"])
    if filters.get("body_type"):
        query = query.filter(Listing.body_type == filters["body_type"])
    if filters.get("country"):
        query = query.filter(Listing.country.ilike(f"%{filters['country']}%"))
    if filters.get("price_rating"):
        query = query.filter(Listing.price_rating == filters["price_rating"])
    if filters.get("source"):
        query = query.filter(Listing.source == filters["source"])

    return (
        query
        .order_by(Listing.first_seen_at.desc())
        .limit(MAX_LISTINGS_PER_ALERT)
        .all()
    )


def build_summary_email(user: User, sections: list[tuple[Alert, list[Listing]]]) -> str:
    lines = [
        f"Zdravo {user.name or user.email},",
        "",
        "Pronasli smo nove oglase za tvoje sacuvane potrage:",
        "",
    ]

    for alert, listings in sections:
        lines.append(f"## {alert.name}")
        lines.append(f"Kriterijumi: {_format_filters(alert.filters or {})}")
        lines.append("")

        for listing in listings:
            price = f"{int(listing.price):,} {listing.currency}".replace(",", ".") if listing.price else "Cena na upit"
            lines.append(
                f"- {listing.year or ''} {listing.make or ''} {listing.model or ''} "
                f"({listing.country or '-'}, {listing.mileage or '-'} km) - {price}"
            )
            lines.append(f"  {settings.FRONTEND_URL}/listing/{listing.id}")

        lines.append("")

    lines.extend([
        "Notifikacije mozes pauzirati u sekciji Moj nalog > Moja potraga.",
        "",
        "AutoAI",
    ])
    return "\n".join(lines)


def _frequency_due(alert: Alert, now: datetime) -> bool:
    last_sent_at = _naive_utc(alert.last_sent_at)
    if not last_sent_at:
        return True
    if alert.frequency == "instant":
        return True
    if alert.frequency == "weekly":
        return last_sent_at <= now - timedelta(days=7)
    return last_sent_at <= now - timedelta(days=1)


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_filters(filters: dict) -> str:
    if not filters:
        return "Svi oglasi"

    labels = {
        "query_text": "tekst",
        "make": "marka",
        "model": "model",
        "min_price": "cena od",
        "max_price": "cena do",
        "min_year": "godiste od",
        "max_year": "godiste do",
        "min_km": "km od",
        "max_km": "km do",
        "fuel_type": "gorivo",
        "transmission": "menjac",
        "body_type": "karoserija",
        "country": "zemlja",
        "price_rating": "ocena cene",
        "source": "izvor",
    }
    return ", ".join(
        f"{labels.get(key, key)}: {value}"
        for key, value in filters.items()
        if value not in (None, "")
    )

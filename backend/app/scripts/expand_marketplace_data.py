import argparse
import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

from app.api.stats import coverage_stats
from app.core.db import SessionLocal
from app.scrapers.autoscout24 import AutoScout24Scraper
from app.scrapers.willhaben import WillhabenScraper
from app.scripts.scrape_autoscout24 import upsert_autoscout24_listings
from app.scripts.scrape_willhaben import (
    cleanup_existing_willhaben_duplicates,
    upsert_willhaben_listings,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_MAKES = ["BMW", "Audi", "Volkswagen", "Mercedes-Benz", "Toyota", "Tesla"]
DEFAULT_AUTOSCOUT_COUNTRIES = ["DE", "AT", "BE", "NL", "FR", "IT"]
WEIGHTED_EU_COUNTRY_BATCHES = {
    "DE": 7,
    "AT": 2,
    "FR": 2,
    "IT": 2,
    "NL": 1,
    "BE": 1,
}


def main() -> int:
    args = parse_args()
    report = run_expansion(
        strategy=args.strategy,
        sources=args.sources,
        countries=args.countries,
        makes=args.makes,
        limit_per_batch=args.limit_per_batch,
        max_pages=args.max_pages,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


def run_expansion(
    strategy: str = "standard",
    sources: str = "autoscout24,willhaben",
    countries: str = "DE,AT,BE,NL,FR,IT",
    makes: str = ",".join(DEFAULT_MAKES),
    limit_per_batch: int = 20,
    max_pages: int = 2,
) -> dict[str, Any]:
    args = SimpleNamespace(
        strategy=strategy,
        sources=sources,
        countries=countries,
        makes=makes,
        limit_per_batch=limit_per_batch,
        max_pages=max_pages,
    )
    parsed_makes = parse_csv(makes) or DEFAULT_MAKES
    parsed_countries = weighted_country_sequence(args) if strategy == "weighted-eu" else parse_csv(countries) or DEFAULT_AUTOSCOUT_COUNTRIES
    sources = set(parse_csv(args.sources) or ["autoscout24", "willhaben"])

    db = SessionLocal()
    try:
        before = coverage_stats(db)
        report = {
            "config": {
                "sources": sorted(sources),
                "makes": parsed_makes,
                "countries": parsed_countries,
                "strategy": strategy,
                "limit_per_batch": limit_per_batch,
                "max_pages": max_pages,
            },
            "autoscout24": {"imported": 0, "created": 0, "updated": 0, "skipped": 0, "fetched": 0, "batches": []},
            "willhaben": {"imported": 0, "created": 0, "updated": 0, "skipped": 0, "fetched": 0, "batches": []},
            "coverage_before": summarize_coverage(before),
            "errors": [],
        }

        if "autoscout24" in sources:
            try:
                run_autoscout24_batches(db, parsed_countries, parsed_makes, limit_per_batch, max_pages, report)
            except Exception as exc:
                logger.exception("AutoScout24 expansion source failed")
                report["errors"].append({"source": "autoscout24", "error": str(exc)})

        if "willhaben" in sources:
            try:
                run_willhaben_batches(db, parsed_makes, min(limit_per_batch, 20), max_pages, report)
            except Exception as exc:
                logger.exception("willhaben expansion source failed")
                report["errors"].append({"source": "willhaben", "error": str(exc)})

        after = coverage_stats(db)
        report["coverage_after"] = summarize_coverage(after)
        report["active_listings_delta"] = after["active_listings"] - before["active_listings"]
        return report
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe batch import for marketplace data expansion")
    parser.add_argument(
        "--sources",
        default="autoscout24,willhaben",
        help="Comma-separated sources: autoscout24,willhaben",
    )
    parser.add_argument(
        "--countries",
        default="DE,AT,BE,NL,FR,IT",
        help="Comma-separated AutoScout24 countries: DE,AT,BE,NL,FR,IT",
    )
    parser.add_argument(
        "--makes",
        default=",".join(DEFAULT_MAKES),
        help="Comma-separated makes to scrape",
    )
    parser.add_argument(
        "--strategy",
        default="standard",
        choices=["standard", "weighted-eu"],
        help="Batch distribution strategy. weighted-eu prioritizes Germany toward realistic EU coverage.",
    )
    parser.add_argument("--limit-per-batch", type=int, default=20, help="Listings per make/country batch, capped safely")
    parser.add_argument("--max-pages", type=int, default=2, help="Max result pages per batch")
    return parser.parse_args()


def weighted_country_sequence(args: argparse.Namespace) -> list[str]:
    allowed = parse_csv(args.countries) or DEFAULT_AUTOSCOUT_COUNTRIES
    sequence = []
    for country in DEFAULT_AUTOSCOUT_COUNTRIES:
        if country not in allowed:
            continue
        sequence.extend([country] * WEIGHTED_EU_COUNTRY_BATCHES.get(country, 1))
    return sequence


def run_autoscout24_batches(db, countries: list[str], makes: list[str], limit: int, max_pages: int, report: dict) -> None:
    safe_limit = max(1, min(limit, 50))
    rounds_by_country = {}
    for country in countries:
        rounds_by_country[country] = rounds_by_country.get(country, 0) + 1
        for make in makes:
            filters = {"country": country, "make": make}
            logger.info("AutoScout24 batch country=%s make=%s limit=%s", country, make, safe_limit)
            listings = asyncio.run(
                AutoScout24Scraper().scrape_listings(filters, max_pages=max_pages, limit=safe_limit)
            )
            result = upsert_autoscout24_listings(db, listings)
            add_batch_report(
                report["autoscout24"],
                {"country": country, "make": make, "batch_round": rounds_by_country[country]},
                result,
                len(listings),
            )


def run_willhaben_batches(db, makes: list[str], limit: int, max_pages: int, report: dict) -> None:
    safe_limit = max(1, min(limit, 20))
    cleanup = cleanup_existing_willhaben_duplicates(db)
    report["willhaben"]["cleanup"] = cleanup
    for make in makes:
        filters = {"country": "AT", "make": make}
        logger.info("willhaben batch country=AT make=%s limit=%s", make, safe_limit)
        listings = asyncio.run(
            WillhabenScraper().scrape_listings(filters, max_pages=max_pages, limit=safe_limit)
        )
        result = upsert_willhaben_listings(db, listings)
        add_batch_report(report["willhaben"], {"country": "AT", "make": make}, result, len(listings))


def add_batch_report(section: dict, batch: dict[str, str], result: dict[str, int], fetched: int) -> None:
    section["imported"] += result.get("created", 0)
    section["created"] += result.get("created", 0)
    section["updated"] += result.get("updated", 0)
    section["skipped"] += result.get("skipped", 0)
    section["fetched"] += fetched
    section["batches"].append({
        **batch,
        "fetched": fetched,
        "imported": result.get("created", 0),
        "created": result.get("created", 0),
        "updated": result.get("updated", 0),
        "skipped": result.get("skipped", 0),
    })


def summarize_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_listings": coverage.get("total_listings", 0),
        "active_listings": coverage.get("active_listings", 0),
        "source_coverage": coverage.get("source_coverage", {}),
        "by_country": coverage.get("by_country", {}),
        "valuation_readiness": coverage.get("valuation_readiness", {}),
    }


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())

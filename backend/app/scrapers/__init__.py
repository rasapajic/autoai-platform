"""
AutoAI external source ingestion is frozen.

Importing any scraper is blocked by default so admin endpoints, scripts,
Celery tasks, and ad-hoc executions cannot fetch third-party listings.
Re-enable only after the source has documented commercial usage rights.
"""


class ScrapingDisabledError(RuntimeError):
    pass


raise ScrapingDisabledError(
    "AutoAI external data updates are disabled pending verified source rights."
)

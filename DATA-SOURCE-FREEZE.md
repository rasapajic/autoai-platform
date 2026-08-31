# AutoAI external data-source policy

**Original freeze effective:** 2026-08-12  
**M0.1 internal recovery amendment:** 2026-08-31

AutoAI's public/commercial external listing pipeline remains fail-closed while
source usage rights are unverified.

The original freeze covered scheduled and manual scrapers, Celery update jobs,
scraper Docker entrypoints, admin-triggered imports, valuation jobs and cleanup
jobs that mutate third-party listing data.

## M0.1 internal recovery exception

For the internal **M0.1 Live Listings Recovery** phase, controlled manual
listing recovery is permitted only when all of the following are true:

1. `AUTOAI_INTERNAL_LISTING_INGEST_ENABLED=true` is explicitly set in the runtime;
2. the source is present in `AUTOAI_INTERNAL_LISTING_SOURCES`;
3. the request uses the new environment-backed admin secret;
4. ingestion is manually triggered through the M0.1 internal endpoint;
5. no unattended schedule, Celery beat job or public/commercial listing service
   is enabled by this exception.

M0.1 starts with Austria and Germany only: `willhaben` and `mobile_de`.

Before a source is enabled for public/commercial production, AutoAI still
requires documented rights for access/use, metadata, descriptions, images,
storage, attribution, translation, derived valuation, contact handling,
monetization, retention and deletion.

Default public/commercial policy remains: **deny unless explicitly approved**.

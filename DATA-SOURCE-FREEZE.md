# AutoAI external data-source policy

**Original freeze effective:** 2026-08-12  
**M0.1 internal recovery amendment:** 2026-08-31  
**M0.2 internal schedule amendment:** 2026-10-25

AutoAI's public/commercial external listing pipeline remains fail-closed while
source usage rights are unverified.

The original freeze covered scheduled and manual scrapers, Celery update jobs,
scraper Docker entrypoints, admin-triggered imports, valuation jobs and cleanup
jobs that mutate third-party listing data.

## M0.2 internal scheduled-refresh exception

Controlled unattended refresh is permitted only for the existing internal
Railway cron service `appealing-communication`, scheduled at 02:00 and 14:00
UTC, and only when all of the following are true:

1. `AUTOAI_INTERNAL_LISTING_INGEST_ENABLED=true` is explicitly set;
2. `AUTOAI_INTERNAL_LISTING_SOURCES` contains exactly the approved internal set;
3. the cron and backend share a newly generated environment-backed admin secret;
4. the cron calls only the guarded internal scheduled-refresh endpoint;
5. at most three pages are requested per source per cycle;
6. every source produces a fresh, valid, non-empty staged batch before the
   database transaction starts;
7. catalog rows are updated in place or marked inactive, never deleted by the
   scheduled operation;
8. no public/commercial listing service is enabled by this exception.

The approved internal source set is limited to `willhaben`, `autoscout24`,
`marktplaats`, `2dehands`, and `kleinanzeigen`. A failure, empty batch,
cross-source external-ID collision, or database error aborts the complete cycle
and preserves the previously committed catalog.

The M0.1 manual recovery endpoints remain secret-protected. Destructive
replacement is reserved for explicitly confirmed emergency recovery and is
never called by the schedule.

Before a source is enabled for public/commercial production, AutoAI still
requires documented rights for access/use, metadata, descriptions, images,
storage, attribution, translation, derived valuation, contact handling,
monetization, retention and deletion.

Default public/commercial policy remains: **deny unless explicitly approved**.

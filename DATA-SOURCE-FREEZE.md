# AutoAI external data-source freeze

**Effective:** 2026-08-12

AutoAI must not fetch, refresh, import, rate, clean up, or otherwise mutate
third-party listing data while source usage rights are unverified.

The freeze covers:

- scheduled and manual scrapers;
- Celery worker and beat update jobs;
- scraper Docker entrypoints;
- manual admin-triggered scraper imports;
- automated valuation or cleanup jobs that mutate the existing listing set.

Re-enabling any source requires all of the following:

1. a documented commercial right to access and use the source;
2. documented rights for metadata, descriptions, images, storage, attribution,
   translation, derived valuation, contact handling, and monetization;
3. source-specific retention and deletion rules;
4. a reviewed code change that enables only that approved source.

Default policy: **deny unless explicitly approved**.

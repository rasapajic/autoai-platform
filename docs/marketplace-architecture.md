# AutoAI Marketplace Architecture

This document defines the MVP marketplace architecture for:

- AutoScout24
- Mobile.de
- PolovniAutomobili
- willhaben

It is architecture only. Scraping remains disabled/manual until each portal adapter is implemented and tested safely.

## Goals

- Use one normalized vehicle schema across all portals.
- Keep every listing traceable to its source portal.
- Deduplicate listings within and across portals.
- Track listing freshness and price history.
- Support safe manual scraping first, scheduled scraping later.
- Keep portal-specific parsing isolated behind adapters.

## Normalized Vehicle Schema

The canonical listing shape should map into the existing `listings` table. Portal adapters must emit this normalized payload before persistence.

Required identity fields:

| Field | Type | Notes |
|---|---|---|
| `external_id` | string | Stable portal listing id with source prefix, e.g. `as24_123`. |
| `source` | string | One of `autoscout24`, `mobile_de`, `polovni`, `willhaben`. |
| `url` | string | Canonical listing URL. |

Vehicle fields:

| Field | Type | Notes |
|---|---|---|
| `make` | string | Canonical make name, e.g. `Volkswagen`, not `VW`. |
| `model` | string | Canonical model where possible. |
| `variant` | string/null | Trim/version text. |
| `year` | integer/null | Prefer first registration year. |
| `first_registration` | date/null | Use when portal exposes month/year. |
| `mileage` | integer/null | Kilometers only. |
| `fuel_type` | enum/null | `diesel`, `petrol`, `hybrid`, `electric`, `lpg`, `cng`. |
| `transmission` | enum/null | `manual`, `automatic`. |
| `engine_cc` | integer/null | `0` or null for EV. |
| `engine_power_kw` | integer/null | Convert PS/HP to kW. |
| `body_type` | enum/null | `sedan`, `suv`, `hatchback`, `kombi`, `coupe`, `cabrio`, `van`, `pickup`. |
| `color` | string/null | Normalized lower-case color. |
| `doors` | integer/null | |
| `seats` | integer/null | |

Pricing fields:

| Field | Type | Notes |
|---|---|---|
| `price` | decimal/null | Numeric amount only. |
| `currency` | string | Usually `EUR`; Serbian RSD listings should either stay RSD or be converted by a later pricing layer. |
| `price_negotiable` | boolean | True when listing says negotiable/VB/dogovor. |

Location fields:

| Field | Type | Notes |
|---|---|---|
| `country` | string | ISO-like country code: `DE`, `AT`, `RS`. |
| `city` | string/null | |
| `postal_code` | string/null | |
| `latitude` / `longitude` | decimal/null | Only if portal exposes or geocoder is later added. |

Condition/history fields:

| Field | Type | Notes |
|---|---|---|
| `condition` | string/null | `used`, `new`, `damaged`. |
| `owners_count` | integer/null | |
| `service_history` | boolean/null | |
| `accident_free` | boolean/null | |

Content/meta fields:

| Field | Type | Notes |
|---|---|---|
| `description` | text/null | Plain text, no HTML. |
| `images` | string array | Image URLs only. |
| `features` | string array | Normalized feature labels where possible. |
| `dealer` | object/null | Adapter may emit dealer payload for later upsert. |
| `scraped_at` | datetime | Time this payload was collected. |

Valuation fields:

| Field | Type | Notes |
|---|---|---|
| `price_estimated` | decimal/null | Filled by valuation pipeline, not adapter. |
| `price_delta_pct` | decimal/null | Filled by valuation pipeline. |
| `price_rating` | string/null | `great`, `good`, `fair`, `high`, `overpriced`. |

## Source Tracking

Use stable source identifiers:

| Portal | `source` | Prefix | Countries |
|---|---|---|---|
| AutoScout24 | `autoscout24` | `as24_` | DE, AT, EU-wide |
| Mobile.de | `mobile_de` | `mob_` | DE, EU-wide |
| PolovniAutomobili | `polovni` | `pola_` | RS, region |
| willhaben | `willhaben` | `wh_` | AT |

Every persisted listing must keep:

- `source`
- `external_id`
- `url`
- `first_seen_at`
- `last_seen_at`
- `scraped_at`
- `is_active`

The combination `source + portal native id` must produce `external_id`. The current DB has `external_id` unique globally, so prefixes are mandatory.

## Portal Adapter Contract

Each portal adapter should implement the same conceptual interface:

```python
class MarketplaceAdapter:
    SOURCE_NAME: str
    BASE_URL: str

    def build_search_url(self, filters: dict, page: int) -> str:
        ...

    async def scrape_listings(self, filters: dict, max_pages: int) -> list[dict]:
        ...

    async def scrape_detail(self, url: str) -> dict:
        ...

    def parse_search_item(self, raw: dict) -> dict | None:
        ...

    def normalize(self, raw: dict) -> dict:
        ...
```

Adapters may use portal-specific selectors, query params, JSON-LD, or page structure, but must return only the normalized schema to persistence.

## Portal-Specific Adapter Notes

### AutoScout24

- Prefer stable listing ids from page attributes or canonical URL.
- Country may come from filter, URL, or seller block.
- Detail scraping should enrich features, full image list, description, dealer data.
- Source prefix: `as24_`.

### Mobile.de

- Prefer JSON-LD structured data when available.
- Fallback DOM parsing only when structured data is absent.
- Make/model IDs are portal-specific and should remain inside the adapter.
- Source prefix: `mob_`.

### PolovniAutomobili

- Serbian listings may show both EUR and RSD; adapter must keep explicit currency.
- Location should default to `RS` unless the listing clearly states another country.
- Normalize Serbian terms: `dizel -> diesel`, `benzin -> petrol`, `automatik -> automatic`.
- Source prefix: `pola_`.

### willhaben

- Austria-focused marketplace, default country `AT`.
- Adapter should isolate willhaben search params and anti-bot behavior from other portals.
- Native listing id should come from canonical URL or page metadata.
- Source prefix: `wh_`.

## Deduplication Strategy

Deduplication has two layers.

### Layer 1: Exact Portal Identity

Primary upsert key:

```text
external_id = source_prefix + native_listing_id
```

If an existing listing has the same `external_id`:

- update price when changed
- update `last_seen_at`
- update `scraped_at`
- keep `first_seen_at`
- preserve related price history
- keep `is_active = true`

### Layer 2: Cross-Portal Candidate Matching

For MVP, do not merge cross-portal duplicates automatically. Instead, compute a candidate fingerprint for future use:

```text
fingerprint = normalized(make, model, year, mileage_bucket, price_bucket, country, city)
```

Recommended buckets:

- mileage bucket: nearest 5,000 km
- price bucket: nearest 500 EUR
- city normalized lower-case

Future behavior:

- If same fingerprint appears across sources, mark as possible duplicate.
- Do not delete or merge until confidence logic exists.
- Prefer showing duplicates separately rather than losing marketplace coverage.

## Persistence Flow

1. Adapter collects raw portal item.
2. Adapter normalizes item to canonical listing payload.
3. Persistence validates required identity fields.
4. Upsert by `external_id`.
5. If price changed, append to `price_history`.
6. Set `last_seen_at = now`.
7. Set `scraped_at = now`.
8. Trigger valuation/indexing asynchronously when available.

Existing `save_listings()` in `celery_tasks.py` should remain the MVP persistence entry point, but should later be hardened with validation and dealer upsert.

## Freshness Tracking

Use existing fields:

- `first_seen_at`: first time AutoAI saw the listing.
- `last_seen_at`: last scrape run where listing was observed.
- `scraped_at`: last time the listing payload was fetched/updated.
- `is_active`: false when listing is no longer observed.

Freshness policy:

| Condition | Action |
|---|---|
| Listing seen in current run | `is_active = true`, update `last_seen_at`, update `scraped_at`. |
| Listing not seen for 7 days | mark `is_active = false`. |
| Listing reappears later | set `is_active = true`, update `last_seen_at`. |
| Price changed | update listing price and add price history point. |

MVP cleanup task may keep the current 7-day cutoff. Later, each source can have its own cutoff if scrape frequency differs.

## Scraper Scheduling

Scheduled scraping should remain disabled by default for local MVP testing.

Configuration:

```text
ENABLE_SCHEDULED_SCRAPING=false
```

Manual MVP commands should be preferred:

```bash
docker compose exec backend celery -A app.core.celery_tasks call app.core.celery_tasks.scrape_portal --args='["mobile_de", {"make": "BMW"}]'
```

Recommended future schedule after adapters are stable:

| Portal | Frequency | Notes |
|---|---|---|
| PolovniAutomobili | every 4-6 hours | Smaller target market, useful for Serbia MVP. |
| AutoScout24 | every 6-8 hours | Broad EU coverage. |
| Mobile.de | every 6-8 hours | Germany-heavy coverage. |
| willhaben | every 6-8 hours | Austria-specific coverage. |

Safety rules:

- Start with `max_pages = 1-2` manually.
- Increase only after selectors and rate limits are validated.
- Use retries with backoff.
- Record failures in `scraper_runs`.
- Never run all portals aggressively by default in development.

## Timeout and Retry Policy

MVP defaults:

- page navigation timeout: 30 seconds
- selector wait timeout: 10 seconds
- max Celery retries: 3
- retry delay: 120 seconds

Future minimal improvement:

- adapter-level `REQUEST_TIMEOUT_SECONDS`
- source-specific `max_pages`
- source-specific backoff after repeated failures

## Adapter File Layout

Current:

```text
backend/app/scrapers/
  base.py
  autoscout24.py
  mobile_de.py
  polovni.py
```

Recommended addition when implementing willhaben:

```text
backend/app/scrapers/willhaben.py
```

Recommended later split, only if complexity grows:

```text
backend/app/marketplaces/
  schemas.py
  adapters/
    autoscout24.py
    mobile_de.py
    polovni.py
    willhaben.py
  normalizers.py
  dedupe.py
```

Do not move existing files until the current MVP is stable.

## MVP Readiness Checklist

- [ ] Define adapter output validation before DB save.
- [ ] Add `willhaben` adapter skeleton.
- [ ] Add source-specific manual scrape command examples.
- [ ] Keep scheduled scraping disabled by default.
- [ ] Seed demo data for local UI testing.
- [ ] Add scraper smoke tests with static sample HTML/JSON, not live portals.
- [ ] Add dedupe candidate fingerprint field or service later.
- [ ] Add freshness dashboard/admin view later.


# AutoAI internal catalog: growth gates

The accepted product target is hundreds of thousands of current listings.
The approved compact interface is preserved during this work.

## M0.3 — implemented foundation

- Canonical makes and basic model labels across the five enabled adapters.
- Readable source labels take precedence over raw Willhaben taxonomy IDs.
- Titles/URL slugs can resolve an ID only when they start with a recognized
  manufacturer; unresolved fields remain unknown.
- Real numeric models are retained. Model generation, trim and engine matching
  still need a more detailed vehicle taxonomy before high-confidence valuation.
- Partial refreshes update/insert in place and preserve unseen catalog rows.
- One batched existing-ID lookup replaces a database lookup per incoming row.
- Stale valuation fields are cleared when the identity or observed price changes.
- Per-source accepted and unresolved-field counts are logged.

This release does not claim a 200,000-listing catalog. It retains the existing
bounded scheduled sample and does not enable automated AI valuation.

## Next gate — persistent collection windows

Implement and verify per-source/partition page cursors with database checkpoints.
Advance a cursor only with a committed batch; retry failed windows without
skipping pages. Prevent overlapping runs from overwriting a newer checkpoint.
Record page exhaustion separately from an unavailable/blocked source.

Keep each run bounded by page count, elapsed time and memory. Do not implement
one synchronous request that loads hundreds of thousands of rows. Validate
source pagination and any result caps using real bounded observations.

## Volume gates

| Gate | Required evidence |
| --- | --- |
| 10,000 | Stable resumable windows; normalized-field coverage by source; same-source ID deduplication; bounded run time |
| 50,000 | Recovery after interruption; country/source distribution; freshness reporting; database query/load measurements |
| 200,000+ | Sustainable source coverage and collection cost; cross-source duplicate handling; sufficiently populated comparison cohorts |

Do not infer availability from absence in a limited search sample. Retain the
last-observed timestamp and separately verify removal/expiry. Exclude stale or
unresolved records from valuation cohorts rather than claiming that every stored
listing is a usable comparable.

## Comparison quality

Build cohorts by make, model generation, engine, transmission, year, mileage and
market. Report the number of usable independent comparables and uncertainty.
A large total catalog alone is not evidence that a particular vehicle has a
reliable market-price estimate.

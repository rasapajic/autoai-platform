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

Automated AI valuation remains disabled. An observed listing is not necessarily
an eligible independent comparable.

## M0.4 — persistent collection windows

The feature flag `AUTOAI_CATALOG_CURSORS_ENABLED=true` on the cron service
enables a fixed internal plan: eight Willhaben categories/body types, five
AutoScout24 country markets, and one partition per remaining source (16 total).
Each request fetches at most three pages from one partition. A PostgreSQL
transaction lock prevents concurrent requests for the same partition, and its
page cursor commits in the same transaction as the catalog rows. Failed requests
retain their previous checkpoint. An ambiguous client timeout requires checking
`GET /api/v1/internal/m01/collection-status` before a manual retry.

The 02:00 UTC run refreshes the first pages; 08:00, 14:00 and 20:00 UTC advance
saved cursors (M0.6 unattended cadence). `AUTOAI_CATALOG_SCAN_MODE` accepts
`auto` (default), `head` or `growth`.
The feature flag is off by default and removing it restores the existing bounded
refresh. No public/commercial ingestion or valuation flag is enabled.

Unknown/empty/blocked pages stop their partition without advancing it. They are
not claimed as confirmed exhaustion. A short window retries a single page at
the same checkpoint. Repeated identical batches and more than 10% unresolved
makes also prevent advancement. Other partitions continue, with partial failures
listed explicitly; a completely failed source makes the cron fail.

Growth stops above 250 MiB of database size, leaving room on the existing
500 MB volume. This is a conservative database guard, not a measurement of free
volume space or WAL growth; storage monitoring remains necessary.

Keep each run bounded by page count, elapsed time and memory. Do not implement
one synchronous request that loads hundreds of thousands of rows. Validate
source pagination and any result caps using real bounded observations. Complete
exhaustion tracking, source result-cap partitioning and freshness validation
remain future gates. This release does not claim a 200,000-listing catalog.

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

### M0.5 — observed mixed-category cards

Production diagnostics found AutoScout24 NL cards headed `Trucks-Lkw`,
`Caravans-Wohnm` and `Oldtimer` among a car search. Explicit truck, motorhome
and trailer category prefixes are excluded before parsing; `Oldtimer` may
precede a recognized manufacturer and is not itself a make. This is a narrow
source-label correction, not a claim that every body type is now classified.
Microcar and Panther Westwinds are recognized readable manufacturer names;
unknown names remain unknown and the 10% identity guard is retained.
Further bounded diagnostics identified repeated `Chery Tiggo` headlines in the
two Willhaben SUV partitions. Chery and the observed Tiggo 4/7/8/9 labels are
recognized from readable names; the numeric source code 10057 alone still
resolves to unknown. See the [manufacturer model range](https://chery.at/).

Manufacturer references: [AutoScout24 catalog](https://admin.autoscout24.com/)
and [Ligier manufacturer history](https://www.ligier.fr/ligier-group/notre-histoire/).
Regression tests use the observed public search headlines. Diagnostic samples
are bounded to five records with truncated fields and are only in the guarded
internal report/logs.

Build cohorts by make, model generation, engine, transmission, year, mileage and
market. Report the number of usable independent comparables and uncertainty.
A large total catalog alone is not evidence that a particular vehicle has a
reliable market-price estimate.

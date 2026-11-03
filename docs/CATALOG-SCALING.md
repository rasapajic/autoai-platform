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

The 02:00 UTC slot refreshes the first pages; other quarter-hour slots advance
saved cursors (M0.8 fast collection). `AUTOAI_CATALOG_SCAN_MODE` accepts
`auto` (default), `head` or `growth`.
The feature flag is off by default and removing it restores the existing bounded
refresh. No public/commercial ingestion or valuation flag is enabled.

Unknown/empty/blocked pages stop their partition without advancing it. They are
not claimed as confirmed exhaustion. A short window retries a single page at
the same checkpoint. Repeated identical batches and more than 10% unresolved
makes also prevent advancement. Other partitions continue, with partial failures
listed explicitly; a completely failed source makes the cron fail.

All collection modes stop above 250 MiB of database size, leaving room on the existing
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
As deeper SUV windows exposed Omoda headlines, additional readable manufacturer
names were added from the primary AutoScout24 catalog. Numeric source IDs still
carry no manufacturer meaning. Supported native numeric model names remain
explicit (including Omoda 5/7/9, Jaecoo 5/7/8 and Lynk & Co 01/02/08).
Model references: [Omoda/Jaecoo Austria](https://www.omodajaecoo.at/)
and [Lynk & Co Austria](https://www.lynkco.com/de-at).

Manufacturer references: [AutoScout24 catalog](https://admin.autoscout24.com/)
and [Ligier manufacturer history](https://www.ligier.fr/ligier-group/notre-histoire/).
Regression tests use the observed public search headlines. Diagnostic samples
are bounded to five records with truncated fields and are only in the guarded
internal report/logs.

Build cohorts by make, model generation, engine, transmission, year, mileage and
market. Report the number of usable independent comparables and uncertainty.
A large total catalog alone is not evidence that a particular vehicle has a
reliable market-price estimate.


## M0.8 — fast cadence and durable pauses

The owner requested faster initial filling on 2026-11-03. The cron schedule is
`*/15 * * * *`, retaining the same bounded per-partition page count. Auto mode
uses head only for the 02:00–02:14 UTC slot and growth otherwise. The runtime
skips cron occurrences while its previous execution remains active; source and
partition transaction locks also reject overlapping endpoint requests.

A new additive `catalog_collection_pauses` table persists retry deadlines across
process restarts. Refusals/rate limits (401/402/403/429/451) pause the whole source
for 24 hours. Other fetch failures pause it for 30 minutes. Empty, unrecognized,
out-of-range or repeated pagination windows pause only that mode/partition for
24 hours, leaving other markets and the head refresh available. Identity-quality
rejection pauses that mode/partition for one hour. Rows and cursors roll back
before the independent pause transaction is committed. Database write failures
are not classified as source refusals. Expired deadlines allow the saved page to
resume. Paused responses perform no upstream fetch and are reported explicitly;
they are not counted as valid observations or successful coverage.

The database-size guard now applies to head mode too, because head refresh can
insert new rows. This faster schedule does not establish source coverage or a
specific daily yield. Volume, freshness and independent-comparable gates remain.

## M0.9 — German coverage and classified-ad identity

On 2026-11-03 the owner requested stronger German coverage after observing an
Austria-heavy catalog. Growth mode now plans 23 sequential windows across the
same 16 fixed partitions: AutoScout24 Germany gets eight windows (up to three
pages each), and every other partition keeps its one window. Germany is visited
first; its seven extra windows reuse the existing backend checkpoint and run
after the other partitions. Head mode still visits each partition once.

A failed or paused partition is not requested again in the same run. Extra
German windows are deferred in that case, with completed/deferred window counts
logged separately from accepted rows and unique failed/paused partitions. The
backend remains responsible for atomic cursor commits, quality checks, storage
guards and durable pauses. Neither schedule nor source allowlist changes.

Kleinanzeigen identity parsing now uses the linked vehicle heading before other
headings, removes narrow observed sales wrappers and recognizes the observed
`chervolet` misspelling as Chevrolet. Explicit wanted/buying headlines are
excluded; unknown model-only headlines are not assigned a guessed manufacturer.
The original heading precedes the remaining source text in stored descriptions.
Existing records are not mass-deleted or deactivated. These changes do not prove
all German inventory is covered or that cross-source duplicates are resolved.

### M0.10 — independent German price queries

The first M0.9 production cycle advanced the broad German query from page 184
through 198, then received an empty/unrecognized response at the window starting
199. This is not confirmed exhaustion or evidence of a specific source page cap.
Its saved cursor and 24-hour partition pause are retained without retrying it.

Growth instead uses eight fixed German integer-EUR price queries: 500–4,999,
5,000–9,999, 10,000–14,999, 15,000–19,999, 20,000–29,999, 30,000–49,999,
50,000–99,999 and 100,000–2,000,000. Source price parameters are also checked
against parsed card prices; out-of-band cards cannot fill a partition. Each
query owns its checkpoint, fingerprint and partition pause. Source-level
refusals still block every query for that source. No pause is deleted/reset.

The allowlist now has 24 fixed keys, appended after the original 16 to preserve
advisory-lock IDs. A growth run visits 23 distinct queries (eight German price
queries plus the original other 15); head still visits the original 16 only.
The broad German query is retained for head and diagnostics, and excluded from
growth. This supersedes M0.9's repeated broad-query windows. Country/source
coverage and finer partitioning remain subject to observed result limits.

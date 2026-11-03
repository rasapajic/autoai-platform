# AutoAI external data-source policy

**Original freeze effective:** 2026-08-12  
**M0.1 internal recovery amendment:** 2026-08-31  
**M0.2 internal schedule amendment:** 2026-10-25

**M0.3 internal catalog-quality amendment:** 2026-11-02

The existing internal refresh now normalizes vehicle labels and accumulates
verified observations without deactivating listings absent from its partial
search sample. Numeric taxonomy IDs are never treated as manufacturer names or
guessed from an ID map. This amendment does not change the source allowlist,
schedule, configured page limit or public/commercial restrictions.

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
7. catalog rows are updated in place or inserted, never deleted or marked
   inactive merely because they are absent from the sampled pages;
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


## M0.4 internal collection-window exception

The owner-approved catalog growth work extends the existing internal exception
with resumable collection. When `AUTOAI_CATALOG_CURSORS_ENABLED=true`, the same
cron calls the guarded `/collect-window` endpoint instead of the all-source
refresh. This specifically supersedes M0.2 conditions 4–6: at most three pages
are fetched **per fixed partition**, and each successful partition commits
independently with its saved page cursor. There are 16 allowlisted partitions:
eight Willhaben category/body-type partitions, five AutoScout24 countries
(A, D, NL, I, B), and one each for Marktplaats, 2dehands and Kleinanzeigen.
No arbitrary source, URL or filter can be supplied through this endpoint.

The existing schedule, source allowlist, internal enable flag and admin secret
remain required. Growth requests respect the database-size guard and strict
page validation. Empty, blocked, unrecognized or low-identity-quality windows
do not advance a cursor. Partial failures are explicitly logged and retried
at their saved checkpoint. Unseen catalog rows are neither deleted nor marked
inactive. Public/commercial ingestion and automated valuation remain disabled.
Removing the cursor feature flag restores the existing M0.2/M0.3 refresh.

## M0.6 unattended collection cadence

On 2026-11-02 the owner explicitly authorized continuing internal collection
without requesting permission for routine runs. The existing cron now runs
at 02:00, 08:00, 14:00 and 20:00 UTC. In cursor auto mode only 02:00 refreshes
the first pages; the other three runs advance committed checkpoints. This
supersedes the earlier twice-daily schedule while retaining all source,
per-partition page, identity, locking and storage safeguards. Bounded manual
growth runs are also authorized within those limits. This does not enable
public/commercial ingestion, AI valuation or changes to the approved interface.


## M0.8 fast initial filling

On 2026-11-03 the owner explicitly requested faster collection than four daily
runs. The existing internal cron runs every 15 minutes, superseding M0.6's
cadence. Page limits and approved sources remain unchanged. Durable source and
partition pauses prevent repeatedly requesting a refusing/rate-limited source,
an invalid window or a low-quality batch on each scheduled occurrence. The
storage guard applies to all collection modes. The approved interface and
public/commercial restrictions remain unchanged.

## M0.9 German growth priority

On 2026-11-03 the owner approved stronger German collection and repair of
Kleinanzeigen headline parsing. In growth mode, the existing AutoScout24 Germany
partition may be visited up to eight times sequentially per cron execution,
reusing its committed cursor. This supersedes the prior single visit per fixed
partition for that German growth partition only. Each request still fetches at
most three pages; there are at most 23 windows over the same 16 fixed partitions.
All other partitions retain their one window, and head mode remains one visit
per partition. Failed/paused German windows prevent further attempts in that
execution. Existing durable retry deadlines are not cleared early.

The same five-source allowlist, internal access gate, 15-minute schedule,
source/partition locks, identity threshold and database-size guard remain in
force. Unknown vehicle identities are not guessed, and wanted/buying ads are
excluded from newly collected sales offers. This exception does not enable
public/commercial ingestion or valuation, change the interface, add a source,
or authorize mass deletion/deactivation of stored records.

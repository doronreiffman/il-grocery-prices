# Decisions

Decisions whose rationale outlives a single change. Never edit a past entry; a superseding decision is a new entry that names the old one.

## 2026-10-31 — A Lambda, not Airflow, for collecting

**Decision:** the collector is a small scheduled Lambda in il-central-1, invoked by EventBridge Scheduler once per chain.
**Why:** the job is a few short runs a morning; a Lambda fits inside the free tier and follows the owner's flights-archive collector. Airflow arrives with the processing pipeline, where it earns its place.
**Context:** `docs/collector.md`, "Non-goals" and "Calls made in this draft"; plan `docs/collector-plan.md`.

## 2026-10-31 — Object Lock, governance mode, ten years

**Decision:** the bucket is created with Object Lock, and every stored raw file, manifest and check record carries governance-mode retention of ten years.
**Why:** the chains keep only their latest files online, so a stored morning cannot be fetched again; nothing stored, including a bad download, may disappear unless the owner overrides with the special permission governance mode allows. Object Lock has to be on when the bucket is created; adding it later means replacing the bucket. Same as flights-archive (owner, 2026-10-31).
**Context:** `docs/collector.md`, "Storage" and "Owner's decisions"; the plan sets retention per object so the state files stay plain, overwritable puts.

## 2026-10-31 — NCR chains through the web form

**Decision:** Rami Levy, Osher Ad and Yochananof are read through the web login the gov.il chain list links (https://url.publishedprices.co.il), with the username the list prints and an empty password; FTP only on the owner's word.
**Why:** the government's list links that web form and prints the usernames for it; the FTP route an open-source scraper uses is not the route the list gives.
**Context:** `docs/collector.md`, "Chains in version one" and "Calls made in this draft"; https://www.gov.il/he/pages/cpfta_prices_regulations (updated 12.08.2026, read 2026-10-31).

## 2026-11-01 — Fail loud on portal changes; alert on missing data, not on errors

**Decision:** an unexpected portal shape (a download link on an unknown host, an unsafe or unreadable listing, a listing with nothing for the day) stops that chain's run and alerts; a refusal latches the chain until the owner clears it; emails go out only for a file listed but not stored, a failed or missing retry run, retry runs that listed nothing, or a newly stopped chain, never for an error that recovers; runs against one portal host start at least 15 minutes (Lambda's maximum run) apart.
**Why:** the chains keep only their latest files online, so a silently lost morning is the failure to prevent; fetching from an unknown host or pressing on after a refusal risks the owner's standing with the portals; flights-archive's error-based alarm flooded the inbox on 2026-10-31 with nothing lost; two sessions at once on one host risk a "too many requests" answer, which would latch a chain. Rejected: skipping odd rows silently (a portal change would read as a quiet morning), alerting on store coverage before thresholds are measured (the spec waits two weeks).
**Context:** controller rulings R15, R19, R23, R30, R31 (`docs/collector-plan.md`, "Deviations" and "Rulings made during the build"); `docs/collector.md`, "Anti-goals" and "Alerts".


## 2026-11-01 — Shufersal: store list and full files only; each full kind run twice in the morning

**Decision:** Shufersal's runs collect `Stores`, `PriceFull` and `PromoFull` only (`Chain.kinds`), one kind an invocation, each full kind twice in the morning (06:45 and 07:00, 07:15 and 07:30; the second carries on where the first stopped) and once at the retry; the update files (`Price`, `Promo`) wait for a polling run. Supersedes, for Shufersal only, the 2026-10-31 owner decision that the morning run also stores the update files listed at that moment.
**Why:** from il-central-1 on 2026-11-01 Shufersal's listing pages took 15 to 39 s each, so a full kind took two 15-minute runs, and its update files come out every hour, so a morning pair or a 09:30 retry can meet a fresh batch (279 promotion update files were listed at 08:14Z; the price updates were not counted) and may never finish, and the check would fail a retry that runs out of time. Rejected: keeping the update files as a best effort with no retry (alerts on slow days, and the batch still moves under the runs); a chain of runs that hands each next run its page (new code, and the hourly batch still makes "done" a moving target); a long-running container (new infrastructure).
**Context:** owner's choice in conversation, 2026-11-01 ("1", twice: Option 1, the timetable, then option 1, full files only); `docs/portals.md`, Shufersal, "Speed"; `docs/operations.md`, "What runs when"; `docs/collector-plan.md`, Deviations, 2026-11-01. Risk kept on purpose: a retry that runs out of time is a failed run even with nothing missing, since it could not read the whole listing.

## 2026-11-02 — A published day is corrected, never quietly

**Decision:** a day already on the site changes only through a manual run given a one-line reason; the republished day keeps its earlier figures on its page and in its day file (a `revisions` list), and a scheduled run whose numbers differ from the published ones fails loudly instead of replacing them.
**Why:** the headline basket's worth is a number anyone can reproduce; a number that changes when the code changes, with no trace, is the first anti-goal. Rejected: "the first published number stands for good" (keeps a known-wrong number public, its own quiet dishonesty); silent replacement by the latest run (the anti-goal itself).
**Context:** `docs/headline-basket.md`, rule B12 and call 1; the builder check's one question, 2026-11-02; owner's approval of the design, 2026-11-02.

## 2026-11-02 — Derived tables overwritable, records write-once; rules as SQL over Parquet, no Airflow or dbt in the first slice

**Decision:** the extraction writes every row of a day's full price files to overwritable Parquet tables (`tables/`); the basket's day records (`basket/`) are write-once, one per run, like manifests; the basket rules are SQL run by DuckDB from Python; the first slice has no Airflow and no dbt.
**Why:** the raw files are the truth and a parser fix must rebuild a day without ceremony, while a record of what was computed must never vanish; SQL over Parquet is what dbt models later, so the second slice can adopt the rules unchanged; two steps and two schedules do not earn an orchestrator (the 2026-10-31 entry "A Lambda, not Airflow, for collecting" already placed Airflow with the processing pipeline where it earns its place). Rejected: extracting only the basket's rows (the same scan, and history and the wide index would need the raw files read again); Python-only rules (the same tests, but no path to dbt).
**Context:** `docs/headline-basket.md`, "The pipeline" and calls 6 and 9; owner's approval, 2026-11-02.

## 2026-11-02 — The revision gate rests on the published copy, not on a local folder

**Decision:** a published day may be replaced only by a build that compared against the copy in the site bucket: `scripts/sync.sh` pulls `days/` from the bucket before a hand build (`--exact-timestamps`, so the bucket's copy wins), `scripts/publish.sh` copies the bucket's `days/` and runs `basket.guard` before any upload (a local day that differs from the published one is refused unless it is a revision: `revised` set and a longer `revisions` list), the `*.json` upload never deletes, and the site bucket keeps every version. Step two's scheduled build reads the published day from the bucket, never from a folder.
**Why:** rule B12 ("corrected, never quietly") was enforced only in the build against `site/days/`, so a build into an unsynced folder followed by an upload would have silently replaced a published day, its revision reason with it, with nothing to recover from; the final review of step one named it the one one-way door. Rejected: trusting the operating note alone (a process guard around a one-way door); refusing every differing upload (a revision could never be published).
**Context:** `docs/headline-basket.md` B12; `src/basket/guard.py`, `scripts/publish.sh`, `scripts/sync.sh`, `site-template.yaml` (`VersioningConfiguration`); the whole-branch review and fix wave of 2026-11-02 (commit 21ab7bc).

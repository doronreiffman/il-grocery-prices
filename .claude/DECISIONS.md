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

# The update files, through the day (design)

Grade: production. The collector is live, and every file it stores is locked for ten years.
Status: draft of 2026-11-06, for the owner's approval before any code. The owner decided on 2026-11-05 that the collector will also collect and keep, write-once, the chains' update files (`Price`, `Promo`) published through the day, for all five chains, Shufersal included. Every choice the owner has not made is marked "Call" and listed at the end. Built and deployed only on the owner's go.

## Why

Each chain publishes two kinds of update file through the day beside the morning's full files: `Price` and `Promo`. Regulation 3(2) of the 2014 price-transparency regulations asks for an update file within an hour of a till change, covering every change since opening (read from a copy in the project's research notes, kept outside this repository; the official text was not read: UNVERIFIED, and the schedule below does not depend on it). Today the collector keeps only the update files its morning runs happen to list: for Rami Levy, Osher Ad, Carrefour and Yochananof those published by about 09:30 to 11:20 Israel time; for Shufersal none (its runs collect `Stores`, `PriceFull` and `PromoFull` only, owner's decision of 2026-11-01). A promotion that starts and ends within a day, or appears only in an update file, is never seen from the full files, and the site's direction is promotions ("Is this deal real?", "Wait for the sale?", "Real deals this week"). The owner also wants every available file kept, used or not.

What the week of 2026-11-01 to 2026-11-06 shows, from the manifests (16 to 19 a day), is what the morning runs saw by the time of each chain's retry run; everything published later is unseen today:

| Chain | `Price` seen by the retry | `Promo` seen by the retry | Rhythm in the names |
|---|---|---|---|
| Rami Levy (by 09:33) | 268 to 275 a day | 82 to 139 | about 90 `Price` an hour from 07:00 (one per store: 99 stores), 50 to 60 `Promo` an hour; a full Saturday (2026-10-31) held 1,206 `Price` and 105 `Promo` ([portals.md](portals.md), "What the directory held") |
| Yochananof (by 10:03) | 139 to 142 | 41 to 94 | 46 or 47 `Price` an hour at 07:00, 08:00 and 09:00 (one per store), 46 `Promo` at 08:00 and 09:00 |
| Osher Ad (by 11:18) | 50 to 60 (21 on 2026-11-02, before its run moved to 08:18) | 6 to 54 | 15 to 24 `Price` an hour at 09:00 to 11:00 (24 stores) |
| Carrefour (by 09:39) | 81 to 242 | 104 to 135 | `Price` at 07:00 to 09:00; most stores' `Promo` at 09:00 (99 to 127 of 147 stores) |
| Shufersal | none collected | none collected | the one record, 2026-11-01's manual runs: 272 stores' `Promo` stamped 09:xx, 3 at 02:xx and 4 at 03:xx (279 of 418 stores, listed at 10:14); 20 stores' `Price`, all 09:xx |

One afternoon was recorded: 2026-11-01's manual Rami Levy run at 14:02 (`120241Z-main-4c25`) listed 651 `Price` (87, 93, 92, 89, 78, 38, 89 and 80 for the hours 07:00 to 14:00) and 407 `Promo` (76, 70, 59, 68, 59 for 10:00 to 14:00). So the hourly rhythm holds through the afternoon, and the morning runs see about a fifth of Rami Levy's day.

Two portal facts shape the design (both from [portals.md](portals.md)):

- The NCR portal (Rami Levy, Osher Ad, Yochananof) and Carrefour keep the day's files listed through the day and past midnight: at 00:13 on 2026-11-01 the NCR directory still held all of 2026-10-31's 1,946 price and promotion files (the 2,362 entries add up to them, 2026-11-01's first 162, the three store lists and store 039's 251 old-scheme files); Carrefour's page for 2026-10-31 (`?date=`) answered that day's 575 files in the same probe. By 14:02 on 2026-11-01 the previous day's files were gone from NCR's directory (the 1,826 entries then were that day's 1,574, store 039's 251 and one more). So for these four chains a poll sees everything published since the last one, and a lost poll costs nothing as long as a later poll of the day runs.
- Shufersal's listing shows only the latest file per store and kind ([README.md](../README.md)), on 22 pages of 20 rows for each kind (page 1's pager named 22 in every run of 2026-11-06 that read it; the probe of 2026-10-31 saw 22 for all four price and promotion categories), and a page took a median 34.7 s (`PriceFull`, 6 pages) and 41.75 s (`PromoFull`, 26 pages) that morning, up to 60.0 s. A file a store replaces before a run reaches its row is gone for good. So for Shufersal, how often a store replaces its update file, which is not measured, decides how much a poll can keep, and no poll can read a kind's list in one run at today's page speeds (section 3).

## Goals

- Every update file a poll lists is stored, byte for byte, write-once, under the Israel date in its name, like every other file.
- Rami Levy, Osher Ad, Carrefour and Yochananof: every update file in the day's listing at the last poll of the day is stored (what they publish after it, and what Shufersal replaces between visits, is the gap this design names and measures, not hides).
- Shufersal: each update kind's list read in full at least once a day, and as often as the host's speed and the cost allow.
- The morning's full files stay the priority: no poll shares a host with a morning run, and the morning check keeps its meaning.
- One email a day at most, and only for data lost or a day no poll read, never for a poll that stopped on time or a listing that failed once.
- The first week measures what is unknown today (each chain's afternoon volume, Shufersal's replacement rhythm, file sizes late in the day) and the owner decides the cadence and the cost from the measurements.

## Non-goals

- No change to the morning runs, their times, or rulings R35, R36 and R37 for the full kinds.
- No reading of a listing sorted by time (Shufersal's header links offer `sort=Time`; it is a new portal call: section 3, fallback).
- No per-day sweep of the previous day's files (`day: previous`) in the first build: measured first (section 4, `other_days`).
- No parsing of the files; no thresholds on counts (a chain's day may hold 6 or 1,400 update files).
- No new infrastructure: the same function, bucket, role and alert topic.

## Anti-goals (a failure even if everything else works)

- A poll that shares a host with a morning run, or starts within 15 minutes of one on the same host.
- A poll that makes the morning's full files later or less complete: a Shufersal pass in the morning gap must end before the 09:30 retry starts.
- A check that emails every day: a poll stopped on time, a listing that failed once, a quiet Saturday must stay quiet.
- Storage that grows faster than estimated with no one seeing it: the week's measurement is a gate, not a note.
- More than two polls in flight at once, or any poll in flight while the basket's five extractions run (12:03 to 12:18): the account allows five concurrent Lambda runs in il-central-1, and the flight-board collector must never be starved (section 6).
- A block met by a poll that the owner learns of a day late, after the next morning's runs did nothing.

## 1. A third collecting mode: `poll`

`{"mode": "poll", "chain": "<slug>", "kinds": [...]}` runs the existing run loop (`src/collector/run.py`) exactly as `main` and `retry` do: read the listing, keep the day's names of the kinds asked for, skip names already stored, download one at a time with the 0.5 s pause, check the body, store write-once, write a manifest under `manifests/date=<day>/<chain>-<HHMMSS>Z-poll-<4 hex>.json`. The day is the Israel date when the run starts, as today; a file belongs to the day in its name.

- For the four chains without page records, `kinds` is left out and the run takes the chain's five kinds, as the morning runs do. Full files published late (a store that opens late) are collected by the way; stored names cost one listing entry each and no request.
- For Shufersal, `kinds` names one update kind, `["Promo"]` or `["Price"]` (categories 3 and 1 in `src/collector/sources/shufersal.py`), one kind an invocation as the full kinds run today. `Chain.kinds` keeps its meaning, the kinds the morning collects and the check holds the retries to (rulings R4 and R35), so it stays `Stores`, `PriceFull`, `PromoFull`; a poll run may ask for any of the five kinds, and a main or retry run still may not ask for one outside `Chain.kinds`. Call.
- Idempotency is what it is today: the run reads the day's stored names once (`stored_names`) and never fetches one; a put carries `IfNoneMatch="*"`, so a race with another run stores a body once; a different body under a stored name is kept beside it with twelve hex digits of its hash (`docs/collector.md`, "Storage"). An hourly NCR file has a new name each hour (the time is in the name), so the question never arises there; a Shufersal file replaced under the same name is a conflict copy, recorded in the manifest.
- A poll run never emails, with one exception (Call, section 5): a poll run that latches a chain publishes the `stopped` alert at once, since the next check is at 11:48 the next day, after that morning's runs have done nothing. The check's rule R26 applies: the chain is marked alerted only once the publish succeeded, so a lost email is sent again by the check.
- The manifest gains `other_days`: for each Israel date other than the run's, how many names of the kinds asked for the listing carried (today the run skips them without a count). It costs nothing and measures two things the design leaves open: how many of a day's files the next morning's main run still sees (the case for a previous-day sweep), and how much of Shufersal's list is stale.

## 2. The polling schedule

Israel time, as every schedule (`template.yaml`, `ScheduleExpressionTimezone`). Each run has Lambda's 900 s; runs on one host start at least 15 minutes apart (ruling R30); one chain never runs twice at once.

Rami Levy, Yochananof and Osher Ad share `url.publishedprices.co.il`, so a poll of the three takes a 45-minute slot; Carrefour has a host of its own. Every two hours from 12:20, and once more at 23:20 so the day's last poll is as late as the day allows:

| Chain | Poll runs (`{"mode": "poll", "chain": ...}`) |
|---|---|
| Rami Levy | 12:20, 14:20, 16:20, 18:20, 20:20, 22:20, 23:20 |
| Yochananof | 12:35, 14:35, 16:35, 18:35, 20:35, 22:35, 23:35 |
| Osher Ad | 12:50, 14:50, 16:50, 18:50, 20:50, 22:50, 23:50 |
| Carrefour | 13:05, 15:05, 17:05, 19:05, 21:05, 23:05 |

Why two hours: Rami Levy publishes about 150 update files an hour (90 `Price`, 50 to 60 `Promo`), and its retry run of 2026-11-01 (`101751Z-retry-851b`) stored 580 files inside one run, so a file costs under 1.4 s with its pause: 300 files in about 5 to 7 minutes, with room for a slow host. The first poll at 12:20 takes what the 09:33 retry did not (about 420 files, 7 to 10 minutes). Three hours would put a 450-file poll near the run's limit on a slow day, and a poll that stops on time leaves its rest to the next one, so a backlog could grow through the day. The directory holds the day, so the number of polls is about spreading downloads and shortening the gap at midnight, not about catching files before they vanish. Osher Ad's last run ends at 00:05: its day is set when it starts (23:50), and names dated the next day are skipped and counted in `other_days`. Osher Ad's afternoon publishing is unseen (its morning files are stamped 07:00 to 11:00); its seven polls cost about a minute each and the first week shows whether they find anything.

Shufersal's passes, each kind two runs 15 minutes apart, the second resuming where the first stopped (section 3):

| Kind | Pass 1 (the morning gap) | Pass 2 | Pass 3 |
|---|---|---|---|
| `Promo` | 07:45, 08:00 | 13:10, 13:25 | 20:10, 20:25 |
| `Price` | 08:15, 08:30 | 13:40, 13:55 | 20:40, 20:55 |

Why these: the Shufersal host is free from 07:45 (the second `PromoFull` run, 07:30, has ended) to 09:30 (the `Stores` retry), so a pass of each kind fits the gap and leaves the morning untouched; on 2026-11-01 seven stores' latest `Promo` was stamped 02:xx or 03:xx and 272 stores' 09:xx, so a batch before the morning exists and is replaced by about 09:00, and the gap pass is where it is caught. `Promo` goes first in every pass: promotions are what the site needs. Three passes a day are the design's starting cadence, not a measurement: how often a store replaces its update file is unknown, and the first week's records say whether three passes catch each store's files or miss most of them (section 7). Call.

How the polls sit beside the rest of the day: the morning runs (06:30 to 11:33) and the 11:48 check are unchanged; the basket's five extractions start at 12:03 and can run to 12:18, and no poll starts before 12:20; the basket run at 12:33 overlaps Rami Levy's 12:20 poll, two runs of different functions on different hosts. At any moment at most two polls are in flight (a Shufersal run and one of the other four: their windows never overlap each other), and the template tests pin it (section 8). In all, 39 poll runs a day beside today's 17 schedules.

## 3. Shufersal

**Can an update kind be read within a run?** No, not at today's speeds. A kind is 22 pages; at the 2026-11-06 medians a `Price` pass is 22 × 34.7 s = 763 s of page reads and a `Promo` pass 22 × 41.75 s = 919 s, against the 810 s a run has before the 90 s time rule (ruling R32) stops it; downloads are cheap (2026-11-01's `Promo` run, `081443Z-main-c96c`, listed and stored 279 files in 702 s on a day pages took 15 to 39 s, so its 22 pages took most of the run and a file well under a second). On a 60 s-a-page morning neither kind gets past page 13 in one run. So an update kind is read the way a full kind is read since ruling R37: across runs.

**What carries over from q21's resume.** All of it, mechanically: a Shufersal poll run records every page it reads (`pages`), and `collector.pages.start_for` and `read_in_full` work per kind from the day's manifests, so `Price` and `Promo` get page records, a resume at the furthest page taken, the one-page overlap for fresh links, the detours to failed files' pages, the step-back when the list shrank, and the order check. The list of an update kind holds one row per store, in file-name order (kind, chain, sub-chain, store, date, time), so a store that publishes a new file changes the name in its row and not the row's place; the order check (`in_order`) holds and the resume page stays right. The names a run `listed` and never stored before it stopped (`not_attempted`) are taken again by the next run from the overlap page, with fresh links.

One thing does not carry over: R37 reads the day as one reading. Once a kind's pages join up from page 1 to the last page, every later run of the day starts a fresh pass at page 1 (`start_for`: "read in full: a fresh pass"). An update kind is read several times a day, so the second run of the 13:10 pass would see the morning pass's complete reading and start at page 1 instead of resuming at the page the 13:10 run stopped on. So, for update kinds only (Call: full kinds keep R37's start rule word for word, so the morning's behaviour and its tests do not move):

- A kind's poll runs of the day, in order of `listing_read_at` (not of run id: a run id's time is UTC, and an Israel day begins two or three hours before its UTC day), are cut into passes. A pass runs from its first run to the run whose pages make the pass's own manifests read in full by R37's joining; the next run begins a new pass. A run blocked by the portal is left out, as R37 leaves it out.
- A poll run of a paged kind starts from the current pass: when the last pass is incomplete, R37's start rule over that pass's manifests alone (a resume at its furthest page, detours to its failed files' pages); when it is complete, or there is none yet, a fresh pass from page 1.
- With a page out of order that day, R37's rule holds as it does for full kinds: a fresh pass from page 1, and only a whole pass in one run completes a reading.

**What carries over from q24's page retry.** A retried page is a page read like any other inside the adapter, so the retry applies to update kinds with no change; whatever q24 records about retried pages, update kinds' page records carry the same fields. The q24 design was not on disk when this was written (checked 2026-11-06), so this rests on the owner's decision as recorded, not on its design.

**What a pass of two runs gives.** On a median day the first run reads about 15 `Promo` pages with their downloads and stops on time; the second reads page 1, then page 15 again and on to 22, about 9 pages, in about 7 minutes, and ends with no error: the pass is complete in about 25 minutes of host time. On a 60 s-a-page day the first run reaches about page 10 and the second, with 14 pages to read, stops near page 21: the pass stays open and the next pass's first run resumes it (at 13:10, hours later; stores that replaced their file in between on the pages already read are not seen until the pass after). The check records each pass's outcome, so the week shows how many passes completed.

**Fallback, if a kind's list cannot be read in full in a day, or stores replace faster than three passes visit them.** In this order, each the owner's call:

1. A third run in each pass (15 minutes more of host time; 6 more runs a day), when the records show passes stopping one run short.
2. A listing read sorted by time: Shufersal's page offers header links `sort=Time&sortdir=ASC` ([portals.md](portals.md), "Paging"); read newest first, a pass would stop at the first page whose names are all older than the pass before, so an idle pass costs one page and a 272-file batch 14. It is a new portal call, unobserved from AWS, with its own risks (ties among files stamped the same minute can repeat or skip rows across pages when the sort has no tiebreaker; the name-order check does not apply), so it needs a probe on the owner's go, one request by hand, and a design amendment before any code. Not chosen now (Call): the rhythm is unknown, and the design's first week measures it with no new call.
3. Fewer passes, or Shufersal's update files dropped, under the owner's rule that a chain that causes major trouble is dropped rather than fought.

## 4. What a poll stores and records

- Raw files, manifests, the latch: unchanged (`src/collector/store.py`). A poll's manifest is a run manifest with `mode: "poll"`, `kinds`, `listed`, `files`, `failed`, `not_attempted`, `unparsed`, `blocked`, `error`, `code_sha`, `pages` (Shufersal) and the new `other_days`.
- How a run knows what is stored: `stored_names` lists `raw/chain=<slug>/date=<day>/` once at the start (one to three listing pages at a few thousand keys a day) and the run never fetches a stored name. Two polls of one chain never run at once (15 minutes apart, 900 s runs), so no two runs race for the same file; a manual run beside a scheduled one would, and the write-once put settles it: one body stored, the other run's manifest says `exists`.
- Nothing is ever stored twice under one key, and nothing is deleted: the same lock, the same role (`s3:PutObject` and `s3:PutObjectRetention` under `raw/` and `manifests/`, `s3:GetObject`, `s3:ListBucket`; no `Delete`).
- A Shufersal poll run reads the day's Shufersal manifests, as its full-kind runs do since R37: one listing and one read per earlier manifest of the day (up to 20 by the evening).

## 5. How the check judges an update-file day

"Complete" cannot mean "every update file the chain published": Shufersal lists only the latest file per store and kind, so a file replaced between two visits was never listed by anyone; the other portals list the day's files, but files published after the day's last poll were listed by no run either. So the check judges what was listed and whether the day was read:

- **The morning, judged at 11:48 of the same day, as today.** The morning judgement reads the day's `main` and `retry` manifests only; the day's poll manifests (Shufersal's 07:45 to 08:45 passes) are left out of `missing`, `listed` and `manifests`, since a pass that stopped on time has listed names it has not yet stored and the afternoon pass takes them. `stored` counts every stored name, so a poll's files never hurt. Rulings R35, R36 and R37 read `main` and `retry` runs of the full kinds and do not change; a poll run never lists a full kind for Shufersal and is not a retry for the others. Call.
- **The update day, judged the next morning.** The 11:48 check of day D also judges D−1 from every manifest of D−1, polls included, and D−1's stored names, and writes the result in D's check record under `update_day` (one record, one email a morning; a reader of D−1's update day opens D's record). It emails for two things, and records the rest:
  - `missing`: a name any run of D−1 listed that is not stored. The same sentence as the morning's, with the day in it.
  - `failed`: an update kind the chain collects that no poll run read in full on D−1: for Shufersal, a kind with no completed pass that day; for the others, no poll run that ended with no error and was not blocked (its listing read whole, as R36 reads a run without page records). A whole day of failed polls is a portal change, a bad deploy or the switch left off, and nothing else tells the owner; the dead-man ping covers only the 11:48 check. Suppressed when a poll run of D−1 was blocked: the `stopped` alert covers it (as R35 does).
  - Quiet, recorded: each poll run's outcome (`polls`: run id, kinds, listed, stored, failed, error, blocked); per update kind the completed passes (each the run ids R37's joining names) and the open pass, if any, with what of the list it did not read (the words `unread` already uses); `by_hour`, the stored update files of D−1 per kind by the hour in their names, which is the week's measurement of each chain's rhythm. A poll stopped on time, a listing that failed and a later poll read, fewer files than yesterday: all quiet. A persistent portal change surfaces the next morning through ruling R4 anyway.
- Ruling: this becomes R38 in [collector-plan.md](collector-plan.md), "Rulings made during the build", worded by the builder from the three bullets above, with the passes rule of section 3.
- The first judged day after the deploy emails "no poll run read ... on D−1" for every chain unless manual poll runs ran that day; the deploy procedure runs one per chain before the switch goes on, as it runs one main run per chain today (section 7).
- healthchecks.io: unchanged. The 11:48 check pings; no poll pings.

## 6. Concurrency, Lambda time and cost

**Concurrency.** The account's Lambda quota in il-central-1 is 5 concurrent executions (recorded 2026-10-29 when AWS refused a reserved-concurrency setting for the flight-board collector; its notes, outside this repository). Who runs: the flight-board collector every 2 minutes with a 100 s timeout at 256 MB (its `template.yaml`, read 2026-11-06), so at most 1; the grocery morning, up to 3 at once between 06:39 and 06:54 (Shufersal, an NCR chain, Carrefour); the basket's five extractions at 12:03 (`template.yaml`, `ExtractShufersal` to `ExtractYochananof`), 5 at once; the basket run at 12:33. The polls add at most 2 at any moment (one Shufersal run, one of the other four; the four never overlap each other) and none between 12:03 and 12:18, so the worst moment with polls is 2 polls + the flight collector = 3 of 5, two spare for a manual run. The 12:03 window already holds 5 extractions and, when the flight collector fires in the same seconds, 6: the design adds nothing to it and names it for the owner (Lambda retries a throttled asynchronous invocation from its queue rather than dropping it, as AWS documents asynchronous invocation; not re-read this session: UNVERIFIED). A template test pins both rules (section 8).

**Lambda time a day.** Runs and expected durations, from the week's manifests and the page times:

| Runs | A day | Expected seconds | GB-s a day (512 MB) | GB-s a month |
|---|---|---|---|---|
| Rami Levy polls | 7 | about 400 (300 files at about 1 s, login, listing) | 1,400 | 42,000 |
| Yochananof, Osher Ad, Carrefour polls | 7, 7, 6 | about 150, 100, 60 | 1,050 | 32,000 |
| Shufersal passes (3 a kind, 2 runs each) | 12 | about 650 (the first run 810, the second about 450) | 3,900 | 117,000 |
| New, expected | 39 | | 6,350 | about 191,000 |
| New, worst case (every run 900 s) | 39 | 900 | 17,550 | about 527,000 |

Beside: the collector today, about 120,000 GB-s a month (the eight Shufersal runs near 15 minutes each and the eight others of a few minutes; the manifests hold no durations, so this is read from their shapes: UNVERIFIED until the month's CloudWatch figure is read); the basket, about 19,000 (Shufersal's extraction 126 s at 2 GB, the others shorter, the basket run 8 s; [operations.md](operations.md), "Sizing") and up to 95,000 by its own design's estimate; the flight-board collector, 720 short runs a day at 256 MB, a few tens of thousands at most (its durations not read: UNVERIFIED). The free tier is 400,000 GB-s a month for the account ([headline-basket.md](headline-basket.md), "Cost"). Expected total with the polls: about 350,000 to 430,000, at the tier's edge; beyond it $0.0000166667 a GB-s at the US East x86 rate (arm64 and il-central-1 rates UNVERIFIED, as that section says): $0 to $0.50 a month expected, about $5 to $6 a month if every poll ran its full 900 s. Invocations: 39 more a day, 1,200 a month, inside the million free.

**S3 requests.** About 4,000 to 5,000 more puts a day ("Storage" below) at $0.0055 per 1,000 ([collector.md](collector.md), "Cost"): $0.65 to $0.85 a month, more than today's $0.35 and more than these files' storage costs in their first year. Polls' lists and reads (a listing of the day's keys per run, Shufersal's manifest reads): about 400 a day, under $0.07 a month at the put rate, an upper bound.

**Storage.** Sizes measured over the week's stored files (each name once), morning files only, so the afternoon is an estimate:

| Chain, kind | Files measured | Median | Mean | Largest | What the afternoon record shows |
|---|---|---|---|---|---|
| Rami Levy `Price` | 2,011 | 30.7 KB | 64.6 KB | 977 KB | a growing share of near-1 MB files: by hour, the mean is 22 KB at 07:00, 61 KB at 08:00, 110 KB at 13:00 and 357 KB at 14:00 (80 files) while the median stays 25 to 54 KB; its `PriceFull` median is 872 KB, so by the afternoon some stores' hourly `Price` file is the size of a full price file (the regulation's "every change since opening" would explain it: UNVERIFIED by reading the files) |
| Rami Levy `Promo` | 972 | 2.2 KB | 8.5 KB | 253 KB | median 1.4 KB at 07:00, 31 to 37 KB at 13:00 and 14:00 |
| Yochananof `Price` / `Promo` | 752 / 379 | 0.7 / 1.3 KB | 2.1 / 1.8 KB | 20 / 6 KB | |
| Osher Ad `Price` / `Promo` | 259 / 172 | 2.1 / 1.6 KB | 6.4 / 2.8 KB | 57 / 16 KB | |
| Carrefour `Price` / `Promo` | 901 / 619 | 2.1 / 1.0 KB | 9.8 / 1.4 KB | 144 / 33 KB | |
| Shufersal `Price` / `Promo` | 19 / 279 (2026-11-01) | 0.6 / 0.8 KB | 0.6 / 1.4 KB | 0.7 / 72 KB | |

A day, estimated: Rami Levy 1,200 to 1,400 `Price` (1,206 on the one full day measured; about 90 an hour from 07:00 on weekdays, the end of its day unseen) at 60 to 360 KB each (the morning mean; the 14:00 mean) is 70 to 500 MB, and 400 to 800 `Promo` at 2 to 35 KB is 1 to 28 MB; Yochananof, Osher Ad and Carrefour together about 1,900 files and 7 MB; Shufersal 300 to 800 files at about 1 KB (and up to 418 a kind an hour if every store published hourly: under 15 MB a day). In all about 4,000 to 5,000 files and 80 to 550 MB a day, almost all of it Rami Levy's `Price` files; the full files today are 250 to 300 MB a day ([collector.md](collector.md), "Cost"). At $0.025 a GB-month (same source), locked ten years and never deleted:

| | Low (80 MB a day) | High (550 MB a day) |
|---|---|---|
| A month | 2.4 GB | 16.5 GB |
| After one year | 29 GB, $0.73 a month | 198 GB, $4.95 a month |
| After ten years | 290 GB, $7.30 a month | 1,980 GB, $49.50 a month |
| Paid over the ten years | about $440 | about $2,970 |

The spread is Rami Levy's afternoon `Price` files, and the first week settles it: the sizes stored are in every manifest. Note for the owner: if those files repeat every change since opening, the day's last file holds what the earlier ones hold, and keeping every hour's file is a choice about storage, not about data lost; the owner's decision is to keep all, and the week's number is when to confirm it. The bucket passes the 50 GB at which [collector.md](collector.md) said colder storage would be looked at within about five months either way; Object Lock blocks deletions, and whether a lifecycle move to a colder class is allowed on a locked object was not checked this session: UNVERIFIED.

**Total new cost, a month.** Year one: about $1 to $4 (requests $0.65 to $0.85, storage growing to $0.73 or $4.95 by its end, Lambda $0 to $0.50 expected); worst case about $5 to $6 more if every poll ran its full 900 s. Year ten: storage alone $7 to $50 a month. healthchecks.io: nothing new. The account's $5 monthly budget alarm ([headline-basket.md](headline-basket.md), "Cost") would sound within the first year at the high bound, which is the point of measuring first.

## 7. Rollout, each step on the owner's go

1. **Build.** Test-first, the mutation check, a fresh review, as every collector change (`docs/collector.md`, "Testing and shipping"); the docs of section 9 changed in the same branch. The template carries a `PollScheduleState` switch of its own, `DISABLED` by default, as the basket's `BasketScheduleState`, so the morning keeps running while polls are tested and the owner can turn polls off without touching it.
2. **The four quick chains.** Deploy with the four chains' poll schedules and the switch off; in the afternoon, one manual poll run per chain, one at a time (the NCR chains never together); read each manifest (`listed`, `stored`, `failed`, `other_days`) and its `REPORT` duration; a manual check the next morning after 11:48 shows the `update_day` section. Then the switch on. Read for three days: the `update_day` sections (no email but for data lost; `by_hour` showing the afternoon rhythm), the REPORT durations against the table in section 6, and the day's bytes (`aws s3 ls --summarize` on `raw/chain=ramilevy/date=<day>/`, read-only).
3. **Shufersal.** Add its twelve pass runs (section 2) and deploy; the gap passes run before the 09:30 retry and the records show whether they ever delay it (they must not). Read for seven days: page times for `Price` and `Promo` (`pages`), how many passes completed (`update_day`), and the hour histogram of each pass's `listed` names (each name's time is a store's latest file: a histogram clustered at 09:xx is a batch rhythm; one spread over the hours is hourly replacement, and three passes then miss most files). The owner picks the cadence or a fallback (section 3).
4. **The measurement review**, after seven days of both: MB a day per chain, GB-s a month from CloudWatch, pass completion, `other_days` in the morning main runs (how much of the previous day the next morning still sees: the case for a previous-day sweep). The owner confirms or changes the cadence, the cost and whether every hourly Rami Levy `Price` file stays. The measured figures replace the estimates in [operations.md](operations.md), "Cost".
5. **Closes** when seven consecutive days show every quick chain's update day judged with no email but a true loss, each Shufersal update kind read in full at least once on five of seven days, and the costs written down from measurements.

## 8. Tests and mutations

Test-first; test data never reads the clock (fixed `listing_read_at` values and days; the Shufersal adapter takes its clock and timer as callables). A mutation for every rule in `scripts/mutation_check.py`, each named, and the proof that it is caught:

- Handler: `poll` is a collecting mode (`COLLECTING`; mutation: `poll` removed, a poll event refused); a poll's run id carries `poll`; a poll run that latches a chain publishes the stopped alert and marks it alerted only after the publish (mutation: marked before; publish removed).
- Run loop: a poll run may ask for kinds outside `Chain.kinds`, a main or retry run may not (one mutation each way); `other_days` counts the skipped names per date and never the run's own day (mutation: the run's day counted; the counter left at zero).
- Pages: passes cut at the run that completes a reading, in `listing_read_at` order (mutations: run-id order; the cut one run late; the completed pass's manifests kept, which makes the second run of a later pass start at page 1); a full kind's start rule unchanged (a regression test with a morning's shape: after a full reading, a fresh pass with detours, as today).
- Check: the morning judgement reads `main` and `retry` manifests only (mutation: a poll's `not_attempted` name raises `missing` at 11:48); the update day judged is the day before the check's (mutation: the same day); its `missing` covers every run of that day, polls included; `failed` for a kind with no completed pass, and for a chain without page records when no poll run ended clean; suppressed when a poll run was blocked; R35, R36 and R37 unchanged on the morning (the existing tests, plus one with poll manifests present); `by_hour` from stored names of the update kinds only.
- Template: every poll schedule follows `PollScheduleState` and every other the collector's switch; no poll starts between the extractions' start and 15 minutes after it (mutation: a poll moved to 12:10); no three poll schedules can be in flight at once, no poll within 15 minutes of two others (mutation: Carrefour moved onto an NCR chain's minute plus five); the existing host, chain and minute tests over the new schedules; every poll event is one the handler takes; Shufersal's poll events name one update kind each; the operations table equals the schedules (existing); the gap passes end before the Shufersal `Stores` retry starts (mutation: a pass at 09:20).
- Replay: the 2026-11-06 Shufersal morning's shape as a `Promo` pass of two runs at its page times, showing the second run resuming and the pass completing, and a third pass's first run starting fresh with the morning pass complete.
- Coverage stays at or above 95% on `collector`; the handoff runs the whole mutation check (1,059 entries at main 8a8bc00, all caught: [README.md](../README.md)).

## 9. Docs that change on build

- [collector.md](collector.md): the Status line (this design); "What it does", "Goals", "Non-goals" (the polling non-goal, superseded: owner 2026-11-05), "How a morning runs" (step 3: polls; step 4: the update day), "Alerts" (the two update-day emails, the poll's stopped email), "Cost", "Owner's decisions" (decision 1 superseded for update files).
- [operations.md](operations.md): "What runs when" (the table gains 39 rows or a polls table; the prose: the switch, the passes, the update day in the next morning's record), "Deploy" (step 3: nine parameters, `PollScheduleState`; step 6: the manual poll runs; step 7 and 8: the `update_day` section and `other_days`; step 9: the poll switch), "Dropping a chain" (its poll schedules), "Cost" (the section 6 figures, then the measured ones).
- [portals.md](portals.md): Shufersal "Speed" gains the update kinds' page times once measured; "Rami Levy, through NCR" gets the directory's day-and-a-bit retention stated in one place (now spread over two bullets).
- [collector-plan.md](collector-plan.md): ruling R38 under "Rulings made during the build"; a Deviations entry.
- [shufersal-resume.md](shufersal-resume.md): "Non-goals" ("No schedule change") and section 2's start rule gain one line each pointing here for update kinds.
- [README.md](../README.md): "What it does today" (the collector's run count and hours; the archive bullet's "for all but Shufersal, also the update files already listed that morning"); the how-it-works picture's alt text and both images (`docs/img/flow-*.png`, which say 06:30 to 11:18); "Alerts for missing data, not for errors"; the test and mutation counts; "Cheap, boring infrastructure".
- [docs/README.md](README.md): this note added to the list.
- `template.yaml` comments (the schedule rationale) and `tests/test_template.py`'s `SCHEDULES` table.

## 10. Left to the builder

Field and section names (`other_days`, `update_day`, `polls`, `passes`, `by_hour`), the exact alert sentences, where the pass-cutting lives (`collector.pages` is the natural place), how the handler distinguishes a poll's immediate stopped email from the check's, the template's switch name, the test layout and the replay's fixtures, within the rules above. The builder may place a rule in another module if the tests read the same.

## Calls made in this draft (the owner can overturn any)

1. Three Shufersal passes a day per kind (07:45, 13:10, 20:10), two runs each, as the starting cadence; the first week decides.
2. No time-sorted Shufersal read now; a probe only if the week shows replacement faster than the passes.
3. The four quick chains poll every two hours from 12:20 and once more at 23:20, all five kinds, no `kinds` in the event.
4. No previous-day sweep in the first build; `other_days` in every manifest measures what it would recover.
5. The update day is judged by the next morning's 11:48 check and written into that day's check record; two emails only: a listed name not stored, a kind no poll read all day.
6. The morning judgement reads `main` and `retry` manifests only; polls of the same day are left out of it.
7. A poll run that latches a chain emails at once (the one collecting run that emails), under R26's marking.
8. Passes are cut by completed readings for update kinds only; full kinds keep R37's start rule.
9. A poll run may ask for any kind; `Chain.kinds` stays the morning's set.
10. A `PollScheduleState` switch of the polls' own.
11. Every hourly file is kept, Rami Levy's near-full-size afternoon `Price` files included, pending the week's measurement.

## Risks kept

- Shufersal's replaced files: a store that publishes twice between two visits of its row loses the first file, silently; the hour histograms measure how often, and the fallbacks of section 3 answer it.
- Files published after a chain's last poll of the day (23:05 to 23:50) and before midnight are not collected until a sweep exists; `other_days` in the next morning's main run counts them.
- A lost update file is reported up to 36 hours after it was published; for the NCR chains it may still be in the directory then, and nothing yet re-fetches a past day (the sweep would).
- A block during a poll stops the chain's next morning too, by the hard rule; the immediate email (call 7) is what gives the owner the evening to clear it.
- Lambda's free tier is shared by three functions in one account, and the expected total sits at its edge; a week of every poll running its full 900 s costs about $2 beyond it, and the $5 budget alarm is the guard.
- The storage estimate's high bound is six times its low bound, from one afternoon's record of one chain; the week's measurement is a gate the owner reads, not a figure to carry forward.

# The collector: design

**Status:** design, 2026-10-31: builder check done and folded in; the owner's two decisions recorded. Since then: built from this design and live since 1 November 2026; what changed during the build is in [collector-plan.md](collector-plan.md), "Deviations" and "Rulings made during the build", and the collector as it runs today is in [operations.md](operations.md).
**Grade:** a portfolio project, but the collector is the one part held to production grade: a morning it misses cannot be recovered.

## What the project is

A public site that prices the same everyday basket at Israel's biggest supermarket chains every morning, from the price files the law makes them publish, with an AI that reads product names and promotion fine print and a published score for how often it is right. This note covers only the first piece, the collector. The site, the processing pipeline and the AI parts get their own design later; the collector ships first.

## Why the collector comes first

The chains keep only their latest files online. Shufersal's listing shows only the latest file per store and type; Victory's listing held only that day's files; the regulations make chains *keep* files for three months (reg. 5), not keep them *online*. History exists only if someone collects it every day, so every day before the collector runs is history lost. It is also the best-understood piece: it follows the pattern of the owner's flights-archive collector.

## What it does

Every morning, in AWS's Tel Aviv region, for each chain in scope: read the chain's file listing; download that day's store list, every store's full price file and full promotions file, and any update files already listed for that day; store each file exactly as received, write-once, in a private S3 bucket; write a manifest of what was expected, fetched and missing; and email the owner only when a chain's morning is still incomplete after the retry run. (Shufersal: its store list and full files only since 2026-11-01, owner's decision.)

## Legal basis

- Section 30(ה) of the Food and Pharma Competition Promotion Law, 2014 (text on Hebrew Wikisource, revision of 2026-07-21): anyone may access the published data and use it "freely and at no charge, for private or commercial purposes".
- Regulation 4(2) of the price-transparency regulations (2014): "every web user can retrieve any file on an ongoing basis".
- The Consumer Protection Authority's chain list (https://www.gov.il/he/pages/cpfta_prices_regulations, updated 12.08.2026, read by the owner's browser 2026-10-31) links each chain's site and, for the NCR-hosted chains, prints the username to use with "password not needed, the field can be left empty".
- Raw files stay private. Only derived numbers are ever published, credited to the chains' published files.

## Goals

- Every day from the first deploy: the store list, every store's full price and full promotions files, and the update files already listed at the morning run, for each chain in scope, stored byte for byte as received. (Shufersal: its store list and full files only since 2026-11-01, owner's decision.)
- Every morning, a record of what is missing, and an email when a file the chain listed for that day is still not stored.
- Polite and identified: one request at a time, a contact address in the User-Agent.
- About $1 to $3 a month in the first year.

## Non-goals (version one)

- Parsing prices or promotions. The collector reads listings, file names and the store list only; reading prices and promotions is the processing pipeline's job, designed later.
- Polling through the day for update files. The morning run stores the update files listed at that moment (owner, 2026-10-31); every run carries a run id so a polling run can be added later without reworking storage. (Shufersal: its store list and full files only since 2026-11-01, owner's decision.)
- Republishing raw files.
- Airflow. The collector is a small scheduled Lambda; Airflow arrives with the processing pipeline, where it earns its place.
- Chains outside the list below.

## Anti-goals (a failure even if everything else works)

- Working around a block. A 401, 403 or 429, a captcha or verification page, or an HTML page where a file belongs stops that chain and raises one alert; the chain stays stopped until the owner clears it (or drops the chain), as in flights-archive. Never a browser User-Agent, another IP, a proxy, or any other way around it. One exception: a refusal from Shufersal's file host after a signed link's expiry time is the collector's own slowness, not a block; the collector reads the listing again for fresh links.
- Losing a morning silently.
- An alert flood from errors that recover by themselves. (flights-archive's alarm emailed on every error in two consecutive 5-minute windows and flooded the inbox on 2026-10-31 with nothing lost; this collector alerts on missing data, not on errors.)
- Credentials, the owner's email or a health-check URL in the repo.

## Chains in version one

The owner's rule: few chains are enough, and any chain that causes major trouble is dropped rather than fought.

| Chain | Share, 2020 | Where the files are | What a visitor needs | Known risk |
|---|---|---|---|---|
| Shufersal | 31.2% | https://prices.shufersal.co.il | Nothing | About 418 stores, 22 listing pages per file type; download links are signed and expire 30 minutes after the listing loads |
| Rami Levy | 13.2% | NCR "Published Prices", https://url.publishedprices.co.il | Username `RamiLevi`, no password (gov.il list) | The web portal's mechanics (login, file list, download) are unknown; a probe comes first. The web form the government links is the route; an FTP route the open-source scraper uses is not, unless the owner says so |
| Osher Ad | 8.5% | NCR | Username `osherad`, no password | Same |
| Carrefour (Yeinot Bitan in 2020) | 7.4% | https://prices.carrefour.co.il | Nothing | Reported blocked from outside Israel; whether AWS Tel Aviv addresses get through is unknown; a probe comes first, dropped if blocked |
| Yochananof | 6.4% | NCR | Username `yohananof`, no password | Same as Rami Levy |

Shares are the Knesset Research Center's 2020 figures as reported by bizzness.net (23.12.2021); current shares are unknown. The five held about two thirds of the market.

Left out on purpose: Victory, H. Cohen and Mahsanei HaShuk (their portal's terms claim ownership of "the price list", which clashes with s.30(ה); owner, 2026-10-31); chains whose list entry prints a password (Salach Dabach, Paz Yellow, Super Yuda); Netiv HaHesed (a captcha page).

The usernames are public (the government prints them) and there are no passwords, so they live in a config file in the repo with the gov.il page cited next to them.

## How a morning runs

1. **Schedule.** EventBridge Scheduler in the Asia/Jerusalem time zone, so daylight saving needs no handling: a main run, a retry run a few hours later that fetches only what is still missing, and a check after it. Starting times: main 06:30, retry 09:30, check 10:00. Full files are due by each store's opening (reg. 3(1)); Shufersal's appeared at 03:00 and 03:40 on a Saturday. The times get tuned from the first week's manifests.
2. **One invocation per chain**, so one chain's trouble never touches another. A chain whose run approaches Lambda's 15-minute limit is split into separate invocations by file type (Shufersal is about 840 downloads a morning).
3. **Per chain:** skip the chain if it is stopped; read the listing; pick that day's store file, each store's full price and full promotions files, and any update files listed for that day, (Shufersal: none since 2026-11-01, owner's decision) where "that day" is the Israel calendar date in the file name; skip any file already stored; download one file at a time with a short pause; check it looks like what it claims (gzip, XML or a ZIP of XML, not HTML, not empty); store it write-once; record it in the manifest. Every run has a run id, so a manual re-run never collides with a stored manifest. A Shufersal run first reads the day's earlier Shufersal manifests and picks up each full kind's list (about 21 pages) where they stopped, instead of reading it from the start each time, and records each listing page it reads ([shufersal-resume.md](shufersal-resume.md); ruling R37 in [collector-plan.md](collector-plan.md)).
4. **The check** emails when any file the chain listed for that day is still not stored after the retry run (always, from day one), when a chain is stopped, when a run failed outright, when no run that day listed a chain's full price files, or its full promotion files, or when Shufersal's runs together did not read a full kind's whole list. The manifest keeps the two kinds of gap apart: "the store published nothing" and "listed but not stored"; only the second is the collector's failure.
5. **Coverage** (stores that published that day's full price file, against the stores in that day's store list, read from the store file) is recorded from day one but not alerted on for the first two weeks. Stores closed on Shabbat and holidays need not publish (reg. 3(1) says "every day a branch is open"), so after two weeks a threshold per chain and weekday is set from what was measured. A chain that publishes no store list that day falls back to its latest stored one.

## Storage

- One private bucket in il-central-1: versioning on, public access blocked, encrypted.
- Raw files: `raw/chain=<slug>/date=YYYY-MM-DD/<file name as published>`.
- Write-once: every write uses `If-None-Match: *`, so a re-run never replaces a stored file (the flights-archive pattern). A different file arriving under a stored name is kept beside it with a short content hash added to its name, and noted in the manifest.
- Object Lock, set when the bucket is created (it cannot be added to an existing bucket's template without replacing the bucket): governance mode, ten-year default retention, as flights-archive (owner, 2026-10-31). Governance mode lets the owner override with a special permission; anything stored, including a bad download, stays unless he does.
- Manifests: `manifests/date=YYYY-MM-DD/<chain>-<run id>.json`: listing time, stores expected, files fetched (name, size, SHA-256), files missing, errors, a fingerprint of the collector's code, and, for Shufersal, each listing page the run read (`pages`: its number, rows, first and last name, the last page its pager names, its time, whether its names were in order, and how far the run took it).
- A small state file per chain holds the "stopped" latch, cleared only by the owner (a manual invocation with an unblock flag, as in flights-archive).

## Identification

- User-Agent `il-grocery-prices/<version> (+<repo URL>; <contact email>)`, set at deploy, never written into the repo. While the repo is private its URL returns 404; the contact email is what matters until launch.
- One request at a time per chain, a short pause between files, at most one retry per file inside a run; the retry run is the real retry.

## Alerts

- One email topic, subscribed to the owner's address (a deploy parameter).
- Email when: a file listed for that day is still not stored after the retry run; a chain is stopped (one email per stop, not one a day); a run failed outright; no run that day listed a chain's full price files, or its full promotion files; or Shufersal's runs together did not read a full kind's whole list (the email names the pages no run read). Coverage emails start only once thresholds exist (see "How a morning runs").
- A retry run that stopped itself short of time is a failed run, with one exception (rulings R36 and R37): each kind it covers was read in full that day, every name it listed was also listed by another run that read that kind, and nothing listed is missing. Then no email goes, and the check record names the run under `short_of_time`. "Read in full" is judged from the listing pages the day's runs read, joined across runs: for Shufersal, the pages its manifests record must join up from page 1 to the last page; a run of another chain, which records no pages, reads its kinds in full when it ended with no error and was not blocked. The retry's names need another run to have listed them: one that read the whole list on its own, or, when the other runs' pages join up into a full reading without the retry's own, one whose pages carry that reading further along the list than the pages joined before them (the reading is joined from the front of the list; among pages that start at the same place, the furthest-reaching are joined first). A run that read only part of the list, where other runs' pages already cover that part, vouches for no name. Nothing missing is not enough on its own: a run that stops while reading the listing never lists the rest, so files it never reached are missing without showing as missing. Nor is a full reading: it covers only the list that was up when it was read, so a retry that listed names no other run saw may have stopped short of more.
- A daily dead-man check: the check run pings healthchecks.io (period one day); if the ping doesn't arrive, healthchecks.io emails. This catches the case where nothing ran at all.
- Individual download errors are logged, never emailed.

## Security

- The Lambda's role may read and write under `raw/`, `manifests/` and `state/`, and may not delete.
- AWS: the owner's personal account through the `flights-sam` profile, region il-central-1, a separate stack `il-grocery-prices`. Nothing touches the owner's employer.

## Testing and shipping (the owner's standard)

- Unit tests against saved listing pages and small trimmed sample files, recorded once from the real portals.
- A mutation check: break the code on purpose and prove the tests catch it.
- A fresh reviewer reads the code before it ships.
- First deploy with the schedule off; one manual run per chain; check the bucket and the manifest; then the schedule goes on, on the owner's go.

## Cost (estimates)

- Volume: Shufersal's full files were about 162 MB on 2026-10-31 (measured from its listing). The other four chains have fewer stores (counts unknown). Estimate: 250 to 300 MB a day, so 8 to 9 GB a month.
- S3 storage at $0.025 per GB-month (il-central-1, per flights-archive `docs/publishing.md`): about $0.25 the first month, about $2.70 a month after a year. Lifecycle moves to colder storage are left until the bucket passes about 50 GB.
- S3 writes: about 2,000 a day at $0.0055 per 1,000 (same source): about $0.35 a month.
- Lambda: a few invocations of up to 15 minutes a day, inside the monthly free tier.
- Total: about $1 to $3 a month in the first year.

## Owner's decisions (2026-10-31)

1. **Update files:** the morning run also stores the update files listed at that moment; no polling through the day in version one. (Shufersal: its store list and full files only since 2026-11-01, owner's decision.)
2. **Object Lock:** on, governance mode, ten-year default retention.

## Calls made in this draft (the owner can overturn any)

- Alerts fire on files listed but not stored, not on coverage, for the first two weeks (from the builder check: a coverage threshold would let a few percent of listed files vanish silently every day).
- A stopped chain stays stopped until the owner clears it, matching flights-archive's latch; an expired Shufersal link is not a block.
- NCR chains through the web form the government links; FTP only on the owner's word.
- The collector reads the store list's content (store numbers), the one file it opens.
- A Lambda, not Airflow, for collecting.

## Left to the builder

- The NCR portal's mechanics, through a first probe: one login with a published username, today's file list, one download.
- Whether Carrefour answers from il-central-1, through the same kind of probe; dropped if it doesn't.
- The pause length, timeouts, and the split of long chains into several invocations. (Set: a 0.5 s pause, a 30 s timeout per socket operation, 60 s for Shufersal (`Chain.timeout`); the split: Shufersal one kind an invocation, each full kind twice in the morning, owner's decision, 2026-11-01.)
- Each chain's coverage threshold, set from the first two weeks.
- Code layout, the test fixtures, the deploy template.

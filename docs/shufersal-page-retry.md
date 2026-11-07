# Shufersal: a listing page that times out is asked again (design)

Grade: production. The collector is live and its files feed the public basket page every morning.
Status: approved by the owner on 2026-11-06, after a builder check (Opus) whose three questions are settled below as marked calls. The owner chose this fix (a timed-out listing page asked again, up to two more tries, on top of the resume of [shufersal-resume.md](shufersal-resume.md)) and skipped one question, which failures the tries cover; that choice and every other the owner did not make is marked "Call" and listed at the end. Not chosen, 2026-11-06: a longer socket wait (120 s) alone, a longer wait and a retry together, and watching more mornings first.

## Why

The resume went live on 2026-11-05 at 17:47Z and 2026-11-06 was its first morning. Shufersal runs one kind an invocation (main 04:30Z Stores, 04:45Z and 05:00Z PriceFull, 05:15Z and 05:30Z PromoFull; retries 07:30Z, 07:45Z, 08:15Z), each with 900 s. What the day's eight manifests show:

| Run (UTC) | Kind | Pages read | Ended | Lambda time |
|---|---|---|---|---|
| 043032Z main | Stores | none | page 1 timed out | 61.6 s |
| 044522Z main | PriceFull | none | page 1 timed out | 60.6 s |
| 050003Z main | PriceFull | 1 to 6 of 22, 117 files | page 7 timed out | 425.0 s |
| 051514Z main | PromoFull | 1 to 7 of 22, 134 files | page 8 timed out | 536.1 s |
| 053015Z main | PromoFull | 1, then 7 to 13, 119 files | page 14 timed out | 564.7 s |
| 073010Z retry | Stores | 1, in 59.0 s | complete | |
| 074536Z retry | PriceFull | none | page 1 timed out | 60.9 s |
| 081551Z retry | PromoFull | 1, then 13 to 22, 164 files | complete | |

The Lambda times are the `REPORT` durations as the main session read them from the collector's CloudWatch log (not re-read here); they agree with the manifests' page times plus about 1.2 s a file plus the 60 s wait. The resume worked: PromoFull was read in full across three runs, 417 files. PriceFull reached page 6 of 22, 117 of 417 stores, and the check's failed alert said so: "the PriceFull list was not read in full: pages 7 to 22 never read". Of about 39 page requests, 6 passed Shufersal's 60 s socket timeout (`Chain.timeout`, `src/collector/chains.py`), and each ended its run with 5.5 to 14 of its 15 minutes unused; no run came near Lambda's limit. The first day of per-page timing measured PriceFull at a median of 34.7 s a page (29.1 to 44.9 s, 6 pages) and PromoFull at 41.75 s (28.8 to 60.0 s, 26 pages); the Stores retry's one page took 59.0 s and PromoFull's page 13 in 053015Z 60.0 s, both just inside the wait (the wait bounds one socket read; PromoFull's `seconds` include Http's 0.5 s pause, while the Stores page was its run's first request and had none). Earlier days: medians of 25 to 35 s on 2026-11-01, about 40 to 45 s on 2026-11-05 (worked out from run times). There is a hint of slow spells rather than single slow pages: the 04:30Z and 04:45Z runs both died on page 1, fifteen minutes apart, while 05:00Z's page 1 took 32.4 s.

How a timeout reaches the code (checked in Python 3.13.18 on this Mac; the Lambda runtime is python3.13): a socket read, a TLS read or a TLS handshake that passes the wait raises `TimeoutError` (the `ssl` module's text is "The read operation timed out", the six failures' text); `urllib` wraps only the connect-and-send step's errors in `URLError`, so a timeout while waiting for the answer or reading it arrives bare, and a connect or handshake timeout arrives as a `URLError` whose `reason` is the `TimeoutError`. `Http` (`src/collector/http.py`) turns any of them into `HttpError`, chained `from` the original, and never retries; the run loop stops on a listing's `HttpError` with `error: "listing failed: …"` and does not read the listing again (`_next` in `src/collector/run.py`; the Task 8 entry of `docs/collector-plan.md`, "Deviations"). The resume design kept this as a non-goal ("No retry of a single slow page", its line 31), because at 60 s a page a retry alone would not have saved 2026-11-05; this change reopens it on top of the resume.

## Goals

- A Shufersal listing page that times out costs the run one wait and a pause, not the rest of its time: it is asked for again, up to two more times, while the time rule allows.
- Every try is on the record, so the next morning's read can say how many pages needed a second or third try, and whether the tries saved runs.

## Non-goals

- No change to the 60 s socket wait, the 90 s time rule, the schedules or the resume; no change to other chains (Carrefour's listing is one request, the NCR chains' a session that logs in afresh; none of their 2026-11-06 runs had an error).
- File downloads: the run loop already gives each one more try (`ATTEMPTS = 2`, run.py).
- No retry of a block, ever (a 401, 403 or 429, or a captcha or verification page stops the chain), and none of a page that was served but does not read as the listing (`ListingUnreadable`: the portal changed).
- No retry of a dropped connection, a cut-short body or a server error (5xx). Call, the question the owner skipped: timeouts only, as the main session recommended. Every failure seen from Shufersal is a timeout, and a timeout is the one failure whose cause (a slow page) and whose remedy (ask again) are known; a 5xx or a dropped connection has never been seen from this portal, says something new about it, and should show plainly in the run's error the first time rather than be smoothed over; widening the rule later is a one-line change, with the evidence. No backoff beyond the fixed pause either: a spell outlasts any pause a run can afford (below).

## Anti-goals

- Tries that hammer a struggling server: at most two more requests a page, ten seconds apart, one request at a time as always, and a run gives up on a page after three.
- A run that no longer leaves time to write its manifest: the time check runs before every request, tries included.
- The check reading a retried page differently, or an older manifest no longer reading.
- An alert or a manifest that hides that tries were used.

## What changes

### 1. Which requests, how many tries, which failures

`_read_page` in `src/collector/sources/shufersal.py` is the one function that requests a listing page; the listing of every Shufersal kind (Stores included: its page 1 timed out at 04:30Z) and the expired-link refresh (`_fresh_link`) both reach it through `_pages` and `_PageReader`, so the rule lives there and covers both. Call: the refresh's pages get the same tries, since a timed-out refresh page is the same slow page. The refresh reads the category again from page 1 to the page that lists the file, and the download's two attempts wrap it, so one expired link can cost up to two timed-out tries on every page the refresh reads, on each attempt: bounded only by the 90 s time rule, as a refresh over slow pages is today. No 2026-11-06 run took that path (no manifest's `failed` holds an expiry): each page's files are fetched right after the page is read, well inside a link's 30 minutes.

A page's request that fails with a timeout is made again, up to two more times (`PAGE_TRIES = 3`); any other `HttpError` is raised at once, as today, and a `Blocked` try stops the chain at once. To tell a timeout apart, Call: `Http` raises `HttpTimeout`, a subclass of `HttpError`, when the cause is a `TimeoutError` or a `URLError` whose `reason` is one; `Http` still never retries, and every `except HttpError` keeps catching it. When the third try fails too, the adapter raises an `HttpError` naming the page and the tries, chained from the last failure, and the run loop records it as today: `listing failed: PriceFull page 7 timed out on 3 tries: GET https://prices.shufersal.co.il/FileObject/UpdateCategory failed: The read operation timed out`. In a refresh, the adapter's text (without the run loop's `listing failed:`) is the file's failure, as a refresh's `HttpError` is today.

### 2. The pause and the time check

Before a second or third try the adapter sleeps `RETRY_PAUSE = 10.0` s (Call), then asks the run's time check, then sends the request, so every request still starts with at least 90 s left (`MIN_TIME_LEFT`, run.py). The pause is for politeness: the portal has just spent up to 60 s on a request its client abandoned (whether it goes on rendering the page after the client has gone is not known: UNVERIFIED), and ten seconds is a clear gap at a cost of at most 20 s a page. A longer pause does not ride out a slow spell: the 04:30Z and 04:45Z spell lasted at least a quarter of an hour, and a run can afford no pause of that length; what a retry can win is the page that hovers at the edge of the wait (59.0 s and 60.0 s pages were read that morning). The risk kept: a page read on its second try in 50 s has cost the run 120 s, two pages' worth of time for one; the time rule bounds it and the page record shows it. The invariant of `docs/collector-plan.md`, Task 11 ("`MIN_TIME_LEFT` above the longest timeout plus the manifest write"), now reads: above the longest wait plus the retry pause plus the manifest write. The longest span between a passing time check and the manifest write is one timed-out try and the pause that follows it, 60 + 10 = 70 s, so the manifest is written with at least about 20 s left, where today it is about 30 (as today, a body that trickles is not bounded by the per-operation wait). When the time check stops a run between tries, the run ends with `stopped: under 90 s left`, exactly as any time stop (ruling R36 matches that text exactly). The `OutOfTime` text names the page and the try, but on the listing path the run loop records only the time stop (`_next` in `run.py`), so the manifest's list of failed tries (section 3) is what shows that a try was used; in a refresh the text is the file's failure, as today.

### 3. How tries are recorded and logged

- The page record (`PageRead`, `src/collector/sources/__init__.py`; the manifest's `pages`) gains `tries`: the requests it took to read the page, 1 as today. `seconds` stays the successful request's time, Http's 0.5 s pause included and the retry pause left out, so page times stay comparable with 2026-11-06's.
- Each failed try gets one log line at WARNING: `shufersal PriceFull page 7: try 1 of 3 timed out after 60.2 s; again in 10 s`. The page's INFO line (`shufersal PriceFull page 7 of 22: 20 rows in 41.2 s`) gains `(try 2)` when the page took more than one.
- A page whose every try failed has no page record, as a timed-out page has none today; the run's error names the page and the tries (section 1), and the failed alert quotes it.
- Every failed try is also kept in the manifest, in a list of its own beside `pages`: one entry a timed-out try, with its kind, page, try number and the seconds it waited, reported by the adapter as it reports pages. Call (after the builder check): the manifest, not the log alone, so the morning's read sees every try used from the manifests, including the two shapes the run's error does not show: a try that timed out before the time check stopped the run (the error stays exactly `stopped: under 90 s left`, which R36 matches), and a try that timed out before a later try of the same page failed another way (a 500 or a block, raised at once, its own error the run's). The check never reads the list; an older manifest has none, which reads as no failed try. A refresh's failed tries are logged only, since a refresh reports no pages; when every try of a refresh page fails, the file's failure names the page and the tries (the plan's reading, accepted by the owner on 2026-11-06).
- Older manifests, without `tries`, read as before: `collector.pages` and `collector.check` never read the field (they read `kind`, `page`, `first`, `last`, `last_page`, `in_order` and `taken_through`), and a retried page is one record, as every page read is today.

### 4. What the check and the email say

Nothing new. Ruling R37's joining and `read_in_full` do not change: a page read on its second try joins as a page read on its first, and a page whose tries all failed is a page never read, named in the alert's "pages 7 to 22 never read" as today. Ruling R36 does not change: the time stop is matched exactly, and the error of a page that failed every try starts `listing failed`, never that text. Call 1 of the resume design stays (owner, 2026-11-06): a retry run whose listing failed for any reason other than running out of time makes the check email, whether or not other runs read the kind in full; after this change, that reason is a page whose every try failed, and the alert says so: `retry run 074536Z-retry-5e4c (PriceFull) ended with: listing failed: PriceFull page 1 timed out on 3 tries: …`. The check record gains no field: the tries are in the manifests.

## 2026-11-06 replayed (expected, not measured)

At that morning's pace (pages 29 to 45 s for PriceFull and 29 to 60 s for PromoFull, about 1.2 s a file, worked out above):

- **04:30Z Stores and 04:45Z PriceFull.** Two more tries, about 04:31:40Z and 04:32:50Z (and 04:46:30Z, 04:47:40Z). Both runs died on page 1 fifteen minutes apart, so the spell lasted at least from 04:30Z to 04:46Z, and tries two minutes apart are unlikely to have outlived it: each run most likely ends about 140 s later than it did, with `listing failed: Stores page 1 timed out on 3 tries`. Nothing gained. The 07:30Z Stores retry's 59.0 s page survives as it did.
- **05:00Z PriceFull.** Page 7 timed out at about 425 s in. A second try at 435 s: pages read at 05:15Z and after took 42 to 51 s, so it more likely than not comes back in about 45 s, leaving about 330 s of work before the time rule: page 7's files and about four more pages, to page 11 or so, some 100 more stores. The run ends on the time rule, not on an error.
- **05:15Z and 05:30Z PromoFull.** A second try of page 8 at about 546 s likely reads it (05:30Z's pages took 40 to 51 s); the run reaches about page 10. The 05:30Z run then resumes at page 10 and meets page 14 about four minutes earlier than it did, at a clock time whose speed is unknown (its page 13 took 60.0 s at about 05:38Z and page 14 then timed out). PromoFull is complete either way, as it was; the 08:15Z retry has less to do.
- **07:45Z PriceFull retry.** Page 1 timed out; the portal sat at the edge then (59.0 s at 07:30Z, 33.3 s at 08:15Z), so whether a second or third try at 07:47:50Z or 07:49:00Z gets through is a toss-up. If one does, the run resumes at about page 11 and reads to about page 20 or 21 before the time rule stops it, with the alert naming the last page or two never read; if none does, the day ends as it did apart from the 05:00Z run's gain.

So the morning most likely still alerts on PriceFull, with about 220 to about 400 of 417 stores stored instead of 117, depending on the 07:45Z toss-up; PromoFull complete as it was. A retry beats one slow page; it does not beat a slow spell, and if spells recur the next question is the wait or the schedule, not more tries.

## Cost

- **Requests to Shufersal.** At most two more a page, ten seconds apart. A timed-out try costs about 70 s with its pause, so a run can fit about ten of them at the very most before the time rule ends it, against one today; the morning's eight Shufersal runs, about 80 at the very worst, against 39 page requests made on 2026-11-06 (6 timed out).
- **Lambda.** The tries use time a run already has, so the most they can add in a day is the time the runs now leave unused: on 2026-11-06, 3,691 s over six runs, about 1,850 GB-seconds at 512 MB, about 55,000 a month, inside the free tier's 400,000; the ceiling already stated for all 17 runs (about 230,000 GB-seconds a month, `docs/operations.md`, "Cost") does not move. At the US East x86 rate ($0.0000166667 per GB-second, `docs/headline-basket.md`, "Cost"), with none of the free tier left, about $0.92 a month, an upper bound; the arm64 il-central-1 rate is UNVERIFIED there and here.
- **S3.** No new reads or writes; a page record gains one small field.
- **Total:** $0 a month in all likelihood, under $1 at the very worst.

## Testing

Test-first, as every collector change (`docs/collector.md`, "Testing and shipping"); test data never reads the clock (a fake `sleep` that records its calls and may move the test's `Clock`, the adapter's `timer` ticks, `TimeoutError` raised by the fake network, as `tests/test_replay.py` does). A mutation for every rule in `scripts/mutation_check.py`, named as the q21 entries are; coverage stays at or above 95%; a fresh reviewer reads the change before it ships; the owner gives the go for the deploy.

- `Http` (`tests/test_http.py`): a bare `TimeoutError` from the body, a `URLError` whose reason is a `TimeoutError` (connect) and one carrying the handshake text raise `HttpTimeout`, an `HttpError` chained from the original, and `Http` still sends one request; a dropped connection, a DNS failure, a 500, a cut-short body raise a plain `HttpError`. Mutations: a timeout raised as a plain `HttpError`; every network failure raised as a timeout; a `URLError`'s timeout not read as one.
- The adapter (`tests/test_shufersal.py`): a page whose first request times out is asked again and its rows given, the record saying `tries` 2 and the successful request's `seconds`; a page read on the third try, `tries` 3; three timeouts raise an `HttpError` naming the kind, the page and the tries, chained from the last, with no record for that page and the pages before it recorded; the pause of 10 s before the second and third try and none before the first; the time check asked after the pause and before each try (a `sleep` that moves the clock under 90 s makes the next try an `OutOfTime` naming the page and the try, with no request sent); a 500, a dropped connection and a cut-short body not asked again; a 403 on the second try a `Blocked`, with no third; the same tries for a Stores page, a detour or step-back page, and a refresh page. Mutations: a timed-out page not asked again (`PAGE_TRIES` 1); a fourth try; no pause; the pause after the time check; the time not checked before a second try; any `HttpError` retried; a block retried; `tries` not recorded; the failed try's seconds kept; the error not naming the page and the tries.
- The run loop (`tests/test_run.py`): the manifest's page record carries `tries`; the run's error reads `listing failed: PriceFull page 7 timed out on 3 tries: …`; the page's log line carries the try; the manifest's list of failed tries holds one entry for each timed-out try (a try followed by a served page, by the time stop, and by a 500), and none on a run with no timeout. Mutations: the log line without the try; a failed try not listed; the list left out of the manifest when the run stops on time.
- The check (`tests/test_pages.py`, `tests/test_check.py`): a day's records with `tries` 3 on a page join, resume and alert exactly as the same records with `tries` 1 and as the same records without the field. No mutation: the rule is that the code reads nothing new, and there is nothing to break; the tests pin it.
- The replay (`tests/test_replay.py`): 2026-11-06's 05:00Z PriceFull run, pages 1 to 6 at the measured pace, page 7 timing out once and then served; the run reads on and ends on the time rule, and the check names the pages after it. The mutation "a timed-out page not asked again" is caught by the replay too (`SHUFERSAL_REPLAYED`). The existing 2026-11-05 replay (`test_the_2026_11_05_morning_replayed`), whose fake network times out only the retries' second request, keeps that morning as a slow spell: every try of that page times out, so its alerts stay as they are and only the error text (`… page 2 timed out on 3 tries: …`) and the clock change. Call (after the builder check): serving the second try instead would write into the tests a complete, silent 2026-11-05 that nobody measured.

## Docs that change on build

- `docs/collector-plan.md`: ruling R38 after R37 in "Rulings made during the build", in R37's form (the rule as built, Why, Cost if wrong); a "Deviations" entry dated with the build; the Task 11 invariant sentence (the 2026-11-01 entry) gains the retry pause.
- `docs/collector.md`: "How a morning runs", step 3 (the Shufersal sentence gains the tries); "Identification" ("at most one retry per file inside a run" gains the listing page's two more tries); "Alerts" unchanged in substance.
- `docs/operations.md`: "What runs when" (the resume sentence gains the tries); Deploy step 6, the page log line and "Shufersal's full files take two runs each"; the manifest's `pages` fields gain `tries`; "Cost", the Lambda line.
- `docs/portals.md`, "Shufersal", "Speed": 2026-11-06's measured page times (PriceFull median 34.7 s, 29.1 to 44.9, 6 pages; PromoFull 41.75 s, 28.8 to 60.0, 26 pages; Stores 59.0 s; 6 of 39 requests passed the 60 s wait: page 1 at 04:30Z, 04:45Z and 07:45Z, page 7 at about 05:07Z, page 8 at about 05:24Z, page 14 at about 05:39Z), the hint of spells, and that a timed-out page is now asked again (this design).
- `docs/shufersal-resume.md`, line 31: "No retry of a single slow page" becomes the record of what was decided and when, pointing at this design.
- `README.md`: the test and mutation counts.
- Three wording fixes parked from the resume's build, folded in on the owner's word (2026-11-06), each checked against the files today:
  - (a) The sentence on who vouches for a stopped retry is stricter than the code in a rare shape (a block that extends the joined reading vouches for every name it listed, even where another run's pages overlap it). Word for word, "a part that other runs' pages already cover vouches for no name", it is in `docs/collector-plan.md:336` (R37, "R36 as amended") and `src/collector/check.py:38` and `:185` (the module docstring and `_seen_by_others`), and becomes "a part that the pages joined before it already cover vouches for no name". `docs/collector.md:91`, `docs/operations.md:23` and `docs/shufersal-resume.md:114` say it as "A run that read only part of the list, where other runs' pages already cover that part, vouches for no name", reworded to the same meaning ("… where the pages joined before it already cover that part …"), not by find-and-replace.
  - (b) `docs/shufersal-resume-plan.md:395`, the final whole-branch review's Deviations line, names `docs/collector-plan.md`, `docs/collector.md`, `docs/operations.md` and `check.py` for fix (1) and leaves out `docs/shufersal-resume.md`, which carries the same sentence at :114. Still so today.
  - (c) "a clean run without page records" at `docs/collector-plan.md:335` and `:337` ("the clean runs without page records") and `docs/shufersal-resume.md:112` clashes with ruling R33's "clean" (a manual run that listed something); it reads "a run without page records that ended with no error and was not blocked", as `docs/operations.md`'s `read_in_full` entry already does. All three places carry the phrase today.

## Rollout

Deploy on the owner's go after the 11:48 Israel-time check and before the next 06:30 run, so one morning's runs share one code fingerprint and its check reads one shape. The first morning is read from the Shufersal manifests (`pages[].tries`, the list of failed tries, any `timed out on 3 tries` error, the `REPORT` durations against 2026-11-06's), the check record and any alert. The item closes on the first morning whose manifests show a page read on its second or third try with its rows given and whose check reads as the rules above say; if a week passes with no timeout, it closes on the tests, with a note that production has not yet exercised the rule.

## Calls made in this draft (the owner can overturn any)

1. Timeouts only: a dropped connection, a cut-short body or a server error is not asked again (the question the owner skipped; the reason in "Non-goals").
2. A pause of 10 s before a second or third try, before the time check, so every request starts with at least 90 s left.
3. The refresh's pages get the same tries.
4. `Http` tells a timeout apart as `HttpTimeout`, a subclass of `HttpError`; `Http` still never retries.
5. Tries are recorded as `tries` on the page record, in the run's error when every try fails (`listing failed: <kind> page <n> timed out on 3 tries: <the last try's error>`), in the manifest's list of failed tries (every timed-out try, whatever ended the run) and in a WARNING line per failed try; no new field in the check record.
6. A replay test of the 05:00Z PriceFull run's shape; the existing 2026-11-05 replay kept as a slow spell.
7. The closing rule in "Rollout".

## Left to the builder

The names (`HttpTimeout`, `PAGE_TRIES`, `RETRY_PAUSE`, `tries`), the exact log and error texts, how the adapter gets its `sleep` (a constructor argument with `time.sleep` as the default, as `Http` has one), whether the replay joins `tests/test_replay.py` or gets a file of its own, and the test layout, within the rules above.

## Changed during the build

This draft, as approved, stays the record of what was intended. Where the build changed it, the change is below; ruling R38 in [collector-plan.md](collector-plan.md), "Rulings made during the build", states the rule as built.

- The time is checked before the pause as well as after it (section 2 and Call 2 above had the pause first and one time check after it). On 2026-11-06 the final review found that a pause could be taken without time to spare: a timed-out try can itself leave the run under 90 s, and the pause still followed. With the check before the pause, a pause is never taken without time to spare, and the manifest is written with at least about 30 s left, as before the retries, not about 20 s. This tightens Call 2; the owner confirmed it on 2026-11-07.

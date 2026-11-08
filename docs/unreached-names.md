# A time-stopped run's unreached names (design)

Grade: production. The collector is live, and every file it stores is locked for ten years.
Status: draft of 2026-11-08, written by Fable 5.1 for the owner's approval; nothing built. The owner asked for this fix on 2026-11-07, after q23's final review found the gap: before the poll switch goes on, either the update day flags a chain whose day's last poll stopped on time, or the run counts what it held unreached, and either way without new requests to the portals. Every choice the owner has not made is marked "Call" and listed at the end, with the questions.

## Why

The run loop reads a listing one row at a time and downloads each file before asking for the next row (`src/collector/run.py:9-10`). After each row it checks the time, and with under 90 s left it stops before asking for the next one (`run.py:169-171`, `_check_time` at `run.py:290-292`; ruling R32, `MIN_TIME_LEFT` at `run.py:63`). So the rows the listing had not yet given are in none of the manifest's lists: not `listed`, not `not_attempted`. The module says so itself ("Names the listing had not yet given when the run stopped are in none of them: the retry run lists them", `run.py:38-39`), and [operations.md](operations.md), line 182, wrote it down at q23's build as a reading note. The one place a name can enter `not_attempted` is `_fetch`, when the time runs out between the loop's check and the download's (`run.py:248-253`), and it stops the run right after, so `not_attempted` holds at most one name a run. The tests pin today's behaviour: `tests/test_run.py`, `test_time_checked_after_a_download` (line 620: three rows, two given, `not_attempted` empty), `test_time_checked_between_listing_items` (608) and `test_stops_before_timeout_and_records_not_attempted` (591); all three pass on this branch.

**The morning is covered, nearly.** A run with no page records reads a kind in full only when it ended with no error (`src/collector/pages.py:77`), so a time-stopped main or retry run never counts as a full reading; a stopped main run's error is left to the retry, which lists the whole day again and skips what is stored (`src/collector/check.py:19-20`; `run.py:229-230`); a stopped retry is a failed run unless R36 excuses it (`check.py:237-263`). One narrow shape slips through on the four quick chains: R36's excuse holds when every name the retry listed was listed by a run that read the kind in full and nothing is missing (`check.py:254-263`); a retry that re-fetched the main run's failed names, stored them, and then stopped on time before reaching files published since the main's read listed only names the main listed, so it is excused, and the files it never reached are lost with no email. R37's words name the risk ("the part past where the retry stopped may hold names no run listed", `check.py:47-48`); today nothing measures it.

**The update day is not covered.** The check judges the day before from its polls (`check.py:311-337`; design [update-files.md](update-files.md), section 5; ruling R39). A kind fails only when no pass read it in full (`check.py:319-320`); for a chain without page records a pass is any poll that ended with no error (`pages.py:77`, `pages.py:146-164`), so one clean poll at 12:20 satisfies the day. `not_tried` counts the names in `not_attempted` that are still not stored (`check.py:318`, `333`), which is at most one a stopped poll. A day whose last poll of a kind stopped on time, after an earlier clean poll, loses every file that poll held unreached, with no email and almost nothing in `not_tried`. That breaks the design's own goal for these chains ("every update file in the day's listing at the last poll of the day is stored", [update-files.md](update-files.md), line 32).

**What is knowable without a request.** The three NCR chains' adapter logs in, reads the whole directory, checks every name and only then gives the first row (`src/collector/sources/ncr.py:24-27`, `73-80`: a list, then `yield from listed`); Carrefour's reads its one page the same way (`src/collector/sources/carrefour.py:14`, `38-45`). Both are proved: `tests/test_ncr.py:195-201` and `tests/test_carrefour.py:124` assert no request until the first row is asked for and the whole listing read by then. So once a run of these four chains has its first row, the rest of the listing sits in the generator's memory, and reading it on costs nothing. Shufersal's listing is the opposite: it yields a page's rows and requests the next page only when asked for the row after them (`src/collector/sources/shufersal.py:86-93`), each request after the run's time check (`shufersal.py:257-258`), so after a time stop the only rows in memory are the rest of the page in hand, and the pages after it are not knowable. For Shufersal the page records already say what was not read (`pages.py`, `unread`, line 85). Carrefour is not an NCR chain (`ncr.py:1`; `src/collector/chains.py:53`), though the brief for this note said so; nothing below depends on it.

**Where else a run stops on time, checked.** Before the listing (`run.py:165`): nothing read, nothing held. Inside an adapter's own request, raised as `OutOfTime` (`run.py:210-211`): NCR's listing answers (`ncr.py:136-137`), which happen before the first row, so the generator ends with nothing held, and Shufersal's pages, between pages, so nothing is held either. In a download (`run.py:258-260`): only Shufersal's refresh of an expired link (`shufersal.py:120-125`), a paged source. So the loop's check and `_fetch`'s are the two places a run stops with rows in hand, and both are in `_Run.collect`'s one `except _Stop` (`run.py:173-174`). Manual runs cannot re-fetch a past day (the day is always the invocation's, `src/collector/handler.py:129`; [update-files.md](update-files.md), "Risks kept"), so nothing below is a recovery path: it is knowing.

## Goals

- A manifest of a run of Rami Levy, Osher Ad, Carrefour or Yochananof that stopped on time names every file of its day it listed and did not reach.
- The update day's `not_tried` is the true count of what the time rule cost, and a day that lost files is not read as clean.
- Not one request more to any portal.

## Non-goals

- No change to the 90 s rule, the schedules, the poll switch or the passes rule (R39).
- No change to Shufersal's listing, page records, resume (q21, [shufersal-resume.md](shufersal-resume.md)) or page tries (q24, [shufersal-page-retry.md](shufersal-page-retry.md)); its update day waits for its polls ([update-files-plan.md](update-files-plan.md), Task 10).
- No sweep of the day before (the design's non-goal stands); no re-fetch of a past day.
- No new manifest field and no new alert kind.

## Anti-goals

- A request made after the time rule said stop, or a manifest written later than today (R38's invariant: at least about 30 s left).
- An email for a poll that stopped on time when nothing was lost: a later poll took what it held.
- A loss reported twice: by the morning's check and the update day's, or by two update-day alerts.
- The morning judgement's rulings (R4, R31, R35 to R37) changed in code or in meaning.
- A drained row doing anything a taken row does beyond being counted: no download, no page record moved.

## The options

**A. The run counts what it held.** After a time stop, a run whose listing is not paged reads the rest of the listing from memory, taking nothing, and records each row of its day and of a kind it asked for as a taken row minus the download: in `listed`, and in `not_attempted` when not stored before. For the four quick chains that is the whole listing as it stood when the run read it, so the manifest is complete and the update day's existing arithmetic (`not_tried` = names in `not_attempted` still not stored, `check.py:318`) becomes exact: a name a later poll stored drops out, a name no poll stored is a file lost. What it cannot know: files published after the run read the listing (the next poll's, or nobody's after the day's last poll: the design's risk, [update-files.md](update-files.md), line 232) and, for Shufersal, anything past the page in hand.

**B. The check flags a chain whose last poll of a kind stopped on time.** From the manifests already written: the last poll of the day that covers the kind (by `listing_read_at`) has `error` equal to `OUT_OF_TIME`. No run changes. What it cannot know: whether anything was lost. A poll stops on time only while downloading, but the rows it had not yet reached can be names already stored (skipped in microseconds, `run.py:229-230`), names of another day, or new files: B emails on the first two as on the third, which the design's anti-goal forbids ("a poll stopped on time … must stay quiet", [update-files.md](update-files.md), line 51), and it says nothing about an earlier poll whose unreached names no later poll took. For Shufersal B is the only signal there can be, and its record already carries it: each poll's `error` and the open pass are in `update_day` today (`check.py:327-331`, `348-349`).

**C. Both.** A for the count; B as the alert's trigger. B adds nothing A does not know better for the quick chains, and for Shufersal the trigger is a question for Task 10, where the passes are designed.

**Recommendation: A.** It answers the owner's requirement in the form that keeps the design's email rule intact (an email only for data lost), it makes the record the design promised to read in the first week true (`not_tried`, rollout step 2), and it costs no request because the four adapters' listings are already whole in memory after their first row. Call 1.

## What changes

### 1. The run loop: after a time stop, the rest of an unpaged listing is read from memory

When `_Run.collect` catches `_Stop` (`run.py:173-174`) and the result's `error` is exactly `OUT_OF_TIME` (`run.py:65`; R36 matches the same text) and the listing was created (a stop before it, `run.py:165`, has none) and the source is not a `PagedSource` (`src/collector/sources/__init__.py:100`; the same test the run uses at `run.py:180-181`), the run asks the listing for its remaining rows until it ends. Each row goes through the take's classification and nothing else (`run.py:219-230`): a kind not asked for is skipped; a name of another day is counted in `other_days` once; a name seen already in this run is skipped; otherwise the name joins `listed`, and joins `not_attempted` unless it was stored before the run. No download, no store, no state write, no time check. A `PagedSource` is not drained, even its page in hand: its page records (`taken_through`) are what the resume and the joining read, and a page half-drained would either move them or leave `listed` and the records disagreeing (Call 4). A stop for any other reason (a block, an unreadable listing, a failed listing) drains nothing: the chain is latched or the run has failed, and the `stopped` or `failed` alert covers the day (Call 3). The drain ends at the listing's end or at `OutOfTime`, the one thing an adapter that honours the lent time check (`sources/__init__.py:7-10`) can raise with no time left; anything else propagates as the unexpected error it would be in the loop (Call 10). The manifest's `error` stays `OUT_OF_TIME`; `unparsed` stays 0, as on every stopped run (R13's rule, `run.py:75-76`; Call 5). The drain runs over at most the directory's few thousand entries in memory (2,362 on 2026-11-01, [update-files.md](update-files.md), line 26), milliseconds, before the manifest write in `collect_chain`'s `finally` (`run.py:119-120`), so R38's margin for the manifest stands.

### 2. The manifest

No new field. For an unpaged listing, `listed` now holds every name of the day and the kinds asked for that the listing gave, a stopped run included; `not_attempted` every such name not stored before the run and never tried, which is the meaning both already have (`run.py:36-39`); `other_days` counts the rest of the listing's other-day names too (Call 6); `not_attempted` stays a subset of `listed`. The module docstring's sentence on the names the listing had not yet given is rewritten: in `listed` and `not_attempted` for a listing that is not paged, in none of them for a paged one, whose page records say what was not read. Manifests written before this change read as before: no reader changes what it reads, and the handler's summary line already logs the `not_attempted` count (`handler.py:162-164`).

### 3. The check: the update day

`_judge_updates` (`check.py:311-337`) changes in two lines and, on the owner's word, a third:

- `untried` also leaves out the names a `main` or `retry` run of that day listed (`listed_by_morning`, `check.py:316`), as `unstored` does (`check.py:317`): those were judged at that day's 11:48 and are never reported twice (Call 7). Today `untried` subtracts only the stored names and `unstored` (`check.py:318`).
- `not_tried` holds the names, per kind and sorted, not a count (Call 8): the count is their length, and an alert or a reader needs the names. The record's shape is still free to change: `update_day` is null while the switch is off and the switch has never been on (`check.py:134-135`; `handler.py:188-190`).
- **Question 1 for the owner.** The design's call 7 (owner, 2026-11-06) says `not_attempted` names are counted, not emailed, on the ground that a slow Shufersal evening leaves such names on the day's last run ([update-files.md](update-files.md), line 126; call 7 at line 219; `check.py:91-94`). That ground does not hold for the four quick chains: their polls are sized to finish (300 files in 5 to 7 minutes, [update-files.md](update-files.md), line 79), their listings are whole, and a name in `untried` after this change is a file of the day that no run stored: data lost, which is what the design says an email is for (line 35). Recommended: the untried names join the chain's `missing` alert, one alert per chain, one sentence, the two counts apart, the names once: `<slug>: <n> update files listed on <day> and not stored (<k> tried and failed, <m> never tried: a poll stopped on time before reaching them): <up to ten names>.` (`update file` for one; a zero part left out; beyond ten, `, and <n> more (the check record lists them all)` as today, `check.py:230-234`). No alert when both parts are empty. The `failed` alert is unchanged, so a day whose only poll stopped on time gets `failed` (no pass read in full) and, when it held names, `missing`, two sentences in the one email, as a morning does today. If the owner keeps call 7, only the two record changes above are built, and the email texts stay word for word (Call 9).

### 4. The check: the morning

No code changes. R4, R31 and R35 to R37 read the same manifests with the same rules, but a time-stopped main or retry run of a quick chain now lists the rest of its listing, so three things follow, each worth the owner's eye (Question 2):

- A retry that stops on time with files unreached gets, beside today's `failed` alert ("ended with: stopped: under 90 s left", `check.py:281-282`), a `missing` alert naming them (`check.py:199-203`), as it already does for the one name `_fetch` records today. Some of those names can be update files that a poll stores two hours later; the alert is true when sent (the retry fell short, and the day's own record says so), and the next day's `update_day` leaves them out (`listed_by_morning`).
- R36's excuse closes its narrow gap on the quick chains: a retry's unreached names are now in its `listed`, so when they were published after the main run's read, no run vouches for them (`check.py:254-263`) and the retry is a failed run, which is R37's intent.
- A main run's time stop still leaves the day to the retry, which lists everything again; the main's longer `listed` changes nothing there (`missing` is judged after the retry, from stored names).

### 5. Shufersal: nothing moves

A `PagedSource` is not drained, so a Shufersal run's `listed`, `not_attempted`, `pages`, `taken_through` and `timeouts` are exactly what they are today, and so are `start_for`, `pass_start`, `read_in_full`, `passes` and `unread` (`pages.py`), the one-page overlap, the detours, the step-back and the tries. The four replay tests (`tests/test_replay.py:99`, `225`, `325`, `375`) pin it. Shufersal's update day keeps its gap until its polls are designed (Task 10): there, "the day's last pass is open" is the only signal possible, and whether it emails is that design's question (Question 3).

## Effects on the rulings

- R32 (90 s): unchanged. The drain follows the stop and makes no request.
- R33, R34 (the NCR second read happens before the first row): unchanged.
- R35 (a full kind no run listed): unchanged in code; a stopped quick-chain run now lists the full-kind names it held, which can only turn a wrong "no run listed a PriceFull" into silence, never the reverse.
- R36 and R37: unchanged in code and in words; their inputs from the quick chains are complete (section 4). Shufersal's inputs are unchanged.
- R38: unchanged; the manifest margin stands (section 1).
- R39: its "Recorded, never emailed" bullet ([collector-plan.md](collector-plan.md), line 370) is amended for `not_tried` (names, the morning's left out, and the email if the owner says so); the rest stands. This note's ruling is R40 (Call 11).

## Cost

$0.00 a month beyond [update-files.md](update-files.md), section 6 ([operations.md](operations.md), "Cost"): no portal request; no new S3 request (the manifest is one put as today, a stopped run's up to about 70 KB larger, some 1,400 names at about 50 bytes; the check record carries the same names once more); Lambda time in milliseconds inside a run that has already stopped. The drain only ever touches memory the adapter already holds.

## Tests and mutations

Test-first; test data never reads the clock (`tests/test_run.py`'s `Clock` and `FakeSource`, lines 81 to 153). Each rule names its test and the break `scripts/mutation_check.py` plants (each entry `"name": (TARGET, text to break, replacement)`, `mutation_check.py:143` on; the text must occur exactly once, so the entries anchored on `except _Stop:\n    pass` and on the loop body, lines 532 to 534, are re-anchored when those lines change). The four run tests named in "Why" change their expectations instead of gaining siblings.

- **Run: the rest of an unpaged listing is listed after a time stop** (`test_time_checked_after_a_download`: the third row given, listed, in `not_attempted`; `test_time_checked_between_listing_items`: rows stored before the run listed and not in `not_attempted`, the unstored one in both; `test_stops_before_timeout_and_records_not_attempted`: `not_attempted` holds the fetch's name and the rows after it, in order). Break: the drain removed (`FakeSource.given` and `not_attempted` short). Break: a drained stored name put in `not_attempted`.
- **Run: nothing is downloaded or stored by the drain** (the same tests assert `source.downloaded`, `source.events` and the stored bodies). Break: the drain calls the take instead of the classification (a download after the stop).
- **Run: a drained row of another day is counted in `other_days`, a kind not asked for skipped, a repeat counted once** (new, one test with the three shapes after the stop). Break: `other_days` not counted on drained rows.
- **Run: only a time stop drains** (`test_blocked_on_a_download_latches_and_stops`, line 454, already asserts `given == 2` and `not_attempted == []` with a row after the block; `test_listing_unreadable_from_a_download_stops_the_run`, line 398, the same for an unreadable refresh). Break: the `OUT_OF_TIME` condition dropped.
- **Run: a paged listing is not drained** (new, with `FakePagedSource`, line 814: a time stop mid-page; `given`, `listed`, `pages[-1]["taken_through"]` unchanged and no page reported after the stop). Break: the `PagedSource` guard dropped. Caught also by the replays (`tests/test_replay.py`).
- **Run: the drain ends at `OutOfTime` with what it had; a stop before the listing drains nothing** (new: `FakeSource` entries with an `OutOfTime` after the stop, the rows before it listed, the manifest's `error` still the time stop and no exception; `test_time_short_at_the_start_reads_nothing`, line 629, as today). Break: `OutOfTime` in the drain escapes (the invocation fails).
- **Adapters: no request after the first row** (`tests/test_ncr.py:195` and `tests/test_carrefour.py:124` gain one assertion each: the listing exhausted, `portal.requested` unchanged). Break: a request planted between rows in each `listing` (`yield from listed` replaced by a loop that requests the file page after each row). The existing "names checked only as they are given" entries (`mutation_check.py:434`, `452`) stay.
- **Check: a name the morning listed is left out of `not_tried`** (new, in the shape of `test_a_name_the_morning_listed_is_never_reported_again`). Break: `listed_by_morning` dropped from `untried`.
- **Check: `not_tried` holds the names per kind, sorted; a name a later poll stored or a poll failed is not among them** (`test_a_name_a_poll_never_tried_is_counted_not_emailed`, line 1475, and `test_the_record_holds_each_poll_and_each_pass`, line 1599, updated). Breaks: `not_tried` left empty (`mutation_check.py:762`, re-anchored); a missing name counted too (`763`); a stored name kept.
- **Check, if the owner says email: the untried names in the `missing` alert with both counts, none when nothing was lost, the `failed` alert unchanged** (the test above renamed and extended; a day whose only poll stopped on time with names held gives both alerts). Breaks: the untried names not emailed (the reverse of `mutation_check.py:761`, which is dropped); the counts swapped; an email with both parts empty.
- **Morning: unchanged** (`tests/test_check.py:592` to `721`, R36 and R37's tests, pass untouched; no code changes there, so no new mutation).
- Coverage stays at or above 95% on `collector`; the whole mutation check runs before the review (1,174 entries at main 459c128, all caught, [README.md](../README.md)); a fresh reviewer reads the change; the owner gives the go for the deploy.

## Docs that change on build

- `src/collector/run.py`: the module docstring's lines 21 to 25 and 36 to 39 (the drain and where the unreached names go); `src/collector/check.py`: lines 91 to 94 (`not_tried`, and the email if chosen); `src/collector/sources/__init__.py`, line 7 to 10: one sentence, that an unpaged listing's rows are whole in memory after the first and the run reads them on after a time stop.
- [collector-plan.md](collector-plan.md): ruling R40 after R39 in "Rulings made during the build", in R38's form (the rule as built, Why, Cost if wrong); a "Deviations" entry dated with the build.
- [update-files.md](update-files.md): section 5's `not_attempted` sentence (line 126), call 7 (line 219), "Risks kept" (line 231) and rollout step 2 (line 178: "`not_tried` near zero" becomes "`not_tried` empty"), each as a dated addendum pointing here, the approved text kept.
- [operations.md](operations.md): line 182 (the reading note that states the gap), the `not_tried` entry of "Reading an update day" (line 237) and its first-weeks line (262), the `missing` email's text (line 243) if it changes.
- [collector.md](collector.md): "Alerts", line 95 (the sentence "counted … not emailed") if the owner says email; "How a morning runs", step 4 (line 73), the same.
- [README.md](../README.md): the test and mutation counts (lines 27 and 60). [docs/README.md](README.md): this note in the list.
- Nothing in [shufersal-resume.md](shufersal-resume.md) or [shufersal-page-retry.md](shufersal-page-retry.md).

## Rollout

Deploy on the owner's go after an 11:48 check and before the next 06:30 run, as every collector change, and after q23's own deploy of 2026-11-08 (polls off): this is a second deploy, before `PollScheduleState` goes to `ENABLED`. The first proof is the manual polls of [operations.md](operations.md), Deploy step 6: Rami Levy's first manual poll meets the day's backlog since its 09:33 retry (about 150 files an hour, [update-files.md](update-files.md), line 79) and on a mid-afternoon start is likely to stop on time; its manifest then shows `not_attempted` with every name it did not reach, and the next manual poll's `listed` holds each of them. The next morning's manual check (`"update_day": true`, step 7) shows that chain's `polls` with the stopped poll's `not_attempted` count and `not_tried` holding only what no later poll stored. The item closes on the first update day with a poll that stopped on time whose `not_attempted` names all appear in the next poll's `listed` and whose check record reads as sections 3 and 4 say; if a week of polls passes with no time stop, it closes on the tests, with a note that production has not yet exercised the rule (Call 12).

## Calls made in this draft (the owner can overturn any)

1. Option A, the count in the run; not B, not both.
2. The drained names join `listed` and `not_attempted`; no new manifest field.
3. Only a time stop drains; a block, an unreadable listing or a failed listing drains nothing.
4. A paged listing is not drained, not even the page in hand.
5. `unparsed` stays 0 on a stopped run, drained or not.
6. The drain counts other-day names in `other_days` as the take does.
7. `untried` leaves out names a morning run of the day listed.
8. `not_tried` holds the names per kind, sorted, not counts.
9. If emailed, the untried names go into the chain's `missing` alert in one sentence with both counts; no new alert kind, and the `failed` alert is unchanged.
10. The drain ends at the listing's end or at `OutOfTime`; anything else is a bug and propagates.
11. Ruling R40, amending R39's `not_tried` bullet.
12. The closing rule in "Rollout".

## Questions for the owner, ranked

1. **Email the untried names of the four quick chains, folded into the `missing` alert (section 3)?** This overturns call 7 of 2026-11-06 for these chains. Recommended: yes. They are files of the day no run stored, the design's rule is an email for data lost, and the ground for call 7 (Shufersal's slow evenings) does not apply to listings that are whole in memory; Shufersal keeps call 7 until Task 10. If no: the record alone shows them, and the rollout's reading of `not_tried` is the only eye on them.
2. **Accept the morning's two visible effects on the quick chains (section 4): a time-stopped retry's `missing` alert naming the files it never reached, some of which a poll may store two hours later, and R36's excuse no longer granted when such files exist?** Recommended: yes. The alternative, a field outside `listed`, keeps the morning's inputs as they are and leaves R36's narrow gap open.
3. **Leave Shufersal's update day as it is until Task 10 designs its polls?** Recommended: yes; its page records already carry the open pass, and whether an open last pass emails belongs with the passes' cadence.

## Left to the builder

The drain's name and where the take's classification is factored out of `_take` (`run.py:215-233`) so both paths share it; the exact alert sentence within Call 9; the test layout; which existing mutation entries are re-anchored; within the rules above.

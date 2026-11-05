# Shufersal: reading the file list across runs (implementation plan)

Grade: production (live collector)

What ships: every Shufersal run records each listing page it reads (kind, page number, rows, first and last name, the pager's last page, seconds, whether its names are in order, and how far the run took it) in its manifest and logs one line per page. Before reading a kind, a Shufersal run reads the day's earlier Shufersal manifests and starts where they stopped: page 1, then the furthest page an earlier run read (one page of overlap), stepping back if the list shifted, after a one-page detour for any failed file earlier on the list; a kind already read in full gets a fresh pass, and a day with no usable record starts at page 1 as today. The check judges "read in full" from the pages the day's runs read, joined across runs (ruling R37, amending R36), records `read_in_full` per full kind, and the failed alert says which pages were never read. Other chains, the schedules, the 60 s socket timeout and the 90 s time rule do not change.

Tasks:

1. The Shufersal adapter records each page it reads, with its order check
2. The Shufersal adapter starts each kind where it is told to
3. "Read in full" across runs: the joining rule (R37) as pure functions
4. Where a run starts: the start point from the day's earlier manifests
5. The run loop: reads the earlier manifests, hands over the start points, keeps the page records
6. The check: R37 in the check record, the excuse and the alert
7. The 2026-11-05 morning, replayed
8. The docs: R37 and what changed, in plain words
9. Full test run, coverage and the full mutation check
10. A fresh review

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** on a slow morning, the day's Shufersal runs of a kind together read the whole list, every page read is timed and recorded, and the check says how much of the list was never read.

**Architecture:** the adapter keeps the paging (it reports each page through an `on_page` callback before giving its rows, and marks the last row it gives from a page); the run loop reads the day's earlier manifests, asks a new pure module `src/collector/pages.py` for a start point per kind, hands it to the adapter, and owns the page records (it alone knows how far into a page it got); the check uses the same module to judge "read in full" across runs. The joining rule lives in one place, so the run loop's "already read in full" and the check's verdict can never disagree.

**Tech Stack:** Python 3.13 standard library only (`dataclasses`, `itertools`, `time.monotonic`, `logging`); pytest, pytest-cov. No new dependency.

**Spec:** `docs/shufersal-resume.md` (its "Calls" are decided: build them as written). Read it first, in full, then `docs/collector.md` ("How a morning runs", "Alerts", "Testing and shipping") and ruling R36 in `docs/collector-plan.md` (last line of "Rulings made during the build").

## Global Constraints

- Storage stays write-once: this change adds no write. The manifest is still the one `put_record` (`IfNoneMatch="*"`, governance Object Lock, ten years); the new reads are one listing of `manifests/date=<day>/shufersal-` and a read of each manifest under it. The role already has `s3:ListBucket` and `s3:GetObject` on `manifests/*` (`template.yaml`, `ReadStored`): no template change.
- Every datetime is time-zone aware; never a naive `astimezone()`. Page seconds come from a monotonic float timer, not from a datetime.
- Test data never reads the clock: fixed times, `gzip.compress(..., mtime=0)`, and the adapter's timer injected (`ShufersalSource(timer=...)`) wherever a test reads `seconds`.
- Fixtures keep the portal's real structure with synthetic values and no `sig=` values: build pages with `tests/test_shufersal.py`'s `page()` helper (the fixture's own markup, `sig=SCRUBBED`), never new HTML.
- Names compare as plain Python strings, as the listing gives them (the name cell, without `.gz`); `listed` holds stored names (`<name>.gz`, ruling R16), so a stored name is compared with page names after `removesuffix(".gz")`.
- No schedule change, no new runs, no change to other chains' behaviour, no change to the 60 s socket timeout (`Chain.timeout`) or the 90 s time rule (`MIN_TIME_LEFT`), no retry of a single slow page, no sort parameter on Shufersal's request.
- Every rule gets a mutation in `scripts/mutation_check.py` in the task that adds it; only pytest exit 1 counts as caught. An existing mutation whose text the change moves is re-pointed at the new text, never dropped (the script prints `STALE` for each). Coverage floor 95% on `collector`.
- Docs (this plan included) in plain words, never "we".
- Cost: one S3 listing and up to eight small manifest reads per Shufersal run, well under $0.01 a month; Lambda time unchanged or less.
- Commits go to this branch, `q21-shufersal-resume`, one per task. No push, no deploy, no `gh` and no AWS call during the build: deploy happens only on the owner's go, from main, after a merge, and is outside this plan.

## Review Focus

1. **The list shrank between runs** (fewer pages than the resume page): the run starts at the last page the pager now names, steps back from there if needed, and does not request a page past the end (which the portal answers with the last page again). Test in Task 2 (`test_a_resume_page_past_the_last_starts_at_the_last`).
2. **A page whose last rows do not parse** (or are another kind): the run still counts the page as taken to its last row, so the block's end is open and the day is not reported short every morning. Tests in Task 1 (`test_the_last_row_given_from_each_page_ends_it`) and Task 5 (`test_the_last_row_given_takes_the_page_to_its_end`).
3. **Deploy day:** the morning's first runs wrote manifests without `pages`, later ones with. A pre-change manifest with no error still reads its kind in full (R36 as today); one with an error is no usable record, and the resume uses the records there are. Tests in Task 3 (`test_manifests_without_pages_and_no_error_read_in_full`), Task 4 (`test_a_mix_of_old_and_new_manifests_uses_the_records_there_are`) and Task 6 (`test_a_pre_change_manifest_ended_clean_reads_in_full`).
4. **A detour page past the current last page** (the list shrank after the failed file was listed): the portal serves the last page again under the asked number; that record is a block of its own and never opens the reading's end. Test in Task 3 (`test_a_detour_page_alone_is_a_block_of_its_own`).
5. **The store list** (`Stores`, one page, no pager): its record has `last_page: null`, it reads in full on its own, and a stopped `Stores` retry is judged as before. Tests in Task 1 (`test_one_page_category_records_no_last_page`) and Task 3 (`test_a_one_page_list_with_no_pager_reads_in_full`).

---

### Task 1: The Shufersal adapter records each page it reads, with its order check

**Files:**
- Modify: `src/collector/sources/__init__.py` (add `PageRead`, `Start`, `PagedSource`; `Listed` gains `ends_page`)
- Modify: `src/collector/sources/shufersal.py` (page reading split into read, report, give; timer; lenient pager reading for pages after 1)
- Test: `tests/test_shufersal.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Produces (in `collector.sources`):

```python
@dataclass(frozen=True)
class Listed:
    name: FileName
    url: str
    ends_page: bool = False  # the last row a paged listing gives from its page: taking it takes the page to its last row

@dataclass(frozen=True)
class PageRead:
    kind: str
    page: int
    rows: int
    first: str               # the first row's file name as listed (any date, parsed or not)
    last: str                # the last row's
    last_page: int | None    # the last page this page's pager names; None when it names none
    seconds: float           # the request's time, rounded to 0.1 s (Http's 0.5 s pause included)
    in_order: bool

@dataclass(frozen=True)
class Start:
    page: int = 1                   # 1: a fresh pass; more: after page 1, resume at this page
    furthest: str | None = None     # the furthest name the earlier runs took (the step-back compares with it)
    detours: tuple[int, ...] = ()   # pages read once each, before page 1

class PagedSource(Source):  # a plain class, so the run loop can tell a paged adapter with isinstance
    def listing(self, http, kinds, short_of_time=never_short,
                starts: Mapping[str, Start] | None = None,
                on_page: Callable[[PageRead], None] | None = None) -> Iterator[Listed]: ...
```

- `ShufersalSource(PagedSource).__init__(self, now=_utc_now, timer: Callable[[], float] = time.monotonic)`. This task honours only `Start()` (a fresh pass); Task 2 adds the rest.
- `on_page(read)` is called for each page once it is read and every row on it checked (cells, link), before its first row is given; a page that fails a check raises as today and is not reported. The refresh after an expired link (`_fresh_link`) reports nothing: it serves one download, not the listing.
- `in_order`: every name on the page sorts at or after the one before it (`<=`), and, when the page read just before it was the page with the number one less, the page's first name sorts at or after that page's last name. Pages read out of number order (a detour, the jump from page 1 to the resume page, a step back) are not compared with each other.
- `last_page`: page 1 keeps its strict reading (`_last_page`, ListingUnreadable when the pager names no readable last page); on other pages the `>>` link's page number is read leniently, `None` when there is no pager or no readable `>>`. Page 1 with no pager records `None` (one page, as the adapter reads it).

- [ ] **Step 1: Write the failing tests** in `tests/test_shufersal.py`, a section `# ---- the record of each page read ----`, with a helper:

```python
def ticks(step):
    """The adapter's timer in a test: each call `step` seconds after the one before, from 0."""
    calls = itertools.count()
    return lambda: next(calls) * step
```

  - `test_each_page_read_is_reported_before_its_rows_are_given`: pages 1 to 3 of category 2 (`page(2, names(p), last=3)`), `ShufersalSource(timer=ticks(41.2))`, `on_page` and the loop over the listing both append to one `events` list. Assert `events == [("page", 1), *20 rows, ("page", 2), *20 rows, ("page", 3), *20 rows]` and `reads[0] == PageRead("PriceFull", 1, 20, names(1)[0], names(1)[-1], 3, 41.2, True)`.
  - `test_a_page_without_a_pager_records_no_last_page`: page 2 served with `last=None` → `reads[1].last_page is None`, and the listing goes on to page 3.
  - `test_a_later_pager_without_a_readable_last_page_is_recorded_not_refused`: page 2's pager with no `>>` link → `last_page is None`, no ListingUnreadable (page 1's strict test, `test_pager_without_a_readable_last_page_is_unreadable`, stays as it is).
  - `test_one_page_category_records_no_last_page`: the Stores fixture → `PageRead("Stores", 1, 1, "Stores7290027600007-000-20261031-020", same, None, 41.2, True)`.
  - `test_the_last_row_given_from_each_page_ends_it`: page 1 holds `[*names(1)[:18], NAME_THAT_DOES_NOT_PARSE, a Price name]` → the 18th item has `ends_page=True`, every other item `False`; page 2's 20th item has it.
  - `test_a_page_out_of_order_is_recorded_and_the_listing_goes_on`: page 2's names reversed → `[r.in_order for r in reads] == [True, False, True]`, and all 60 rows are still given.
  - `test_a_page_starting_before_the_last_name_of_the_page_before_is_out_of_order`: page 3 holds `names(1)` (earlier than page 2's) → `in_order` False for page 3 only.
  - `test_a_name_repeated_across_a_page_boundary_is_in_order`: page 2's first name equals page 1's last → `in_order` True.
  - `test_a_page_that_fails_its_checks_is_not_reported`: page 2 with a link off the file host → ListingUnreadable, and `reads` holds page 1 only.
  - `test_a_listing_with_no_callback_reads_as_before`: `listing(http, ("PriceFull",))` with no `on_page` gives the same names as with one.
  - Existing equality assertions on a page's last `Listed` get `ends_page=True`; nothing else in the file changes.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_shufersal.py -q`. Expected: the new tests fail (no `PageRead`, no `timer`).
- [ ] **Step 3: Implement** the interfaces above. Suggested shape: `_read_page(http, kind, page, short_of_time, timer) -> (rows: list[tuple[str, str]], grid, seconds)` does the time check, the timed request, the "no rows" and row checks; `_pages(http, kind, short_of_time, start, on_page, timer)` yields `(PageRead, rows)` for each page whose rows are given and calls `on_page` for every page read; `listing` turns rows into `Listed` items (unparsed counted as today), marking the last one given from each page. `_fresh_link` reads through the same `_pages` with `Start()` and no `on_page`.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_shufersal.py tests/test_run.py tests/test_chains.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, each name ending `(q21 pages)`, target `SHUFERSAL`: "a page reported after its rows", "rows not checked for order", "a page's first name not compared with the page before", "the page boundary compared strictly" (`<=` → `<`), "every row given ends its page", "a page's last row ends it only when it parses", "seconds not timed" (recorded as 0.0), "a later page's pager read strictly" (raises). Re-point the existing Shufersal mutations the rewrite moved ("all pages read before the first row", "Shufersal page read short of time", "Shufersal listing not given the time check", "Shufersal refresh not given the time check"). Run `.venv/bin/python scripts/mutation_check.py "q21 pages" "Shufersal" "all pages read"`. Expected: every one CAUGHT, none STALE.
- [ ] **Step 6: Commit** `git add src/collector/sources tests/test_shufersal.py scripts/mutation_check.py && git commit -m "Shufersal adapter: a record of each listing page read, with its order check (q21)"`.

### Task 2: The Shufersal adapter starts each kind where it is told to

**Files:**
- Modify: `src/collector/sources/shufersal.py`
- Test: `tests/test_shufersal.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `Start`, `PageRead`, `on_page` from Task 1.
- Produces: `ShufersalSource.listing(..., starts=...)` reads, per kind, with `start = starts.get(kind, Start())`:
  1. each page in `start.detours`, once, in the order given, rows given;
  2. page 1 (its pager gives the last page, as today), rows given;
  3. when `start.page > 1` and the last page is more than 1: page `p = min(start.page, last)`; while `p > 2` and that page's first name sorts after `start.furthest`, page `p - 1` (each page read while stepping back is reported, its rows not given); the rows of the page where it stopped are given;
  4. then every page after that one, to the last, each read when the caller asks for it (pages read while stepping back are read again when reached: their links stay fresh and one page at a time stays the rule).
- The time check is asked before every page read, detours and steps back included (OutOfTime `before page <n> of the <kind> listing`, as today).

- [ ] **Step 1: Write the failing tests**, a section `# ---- where each kind starts ----`, with a helper `listing_pages(portal)` → the `page=` numbers of the listing requests, in order. Category 2 pages built `page(2, names(p), last=21)` unless a test says otherwise.
  - `test_a_fresh_pass_reads_page_1_to_the_last`: `starts={"PriceFull": Start()}` → `[1, 2, ..., 21]`.
  - `test_a_resumed_kind_reads_page_1_then_the_resume_page_again_and_on`: `Start(page=12, furthest=names(12)[0])` → `[1, 12, 13, ..., 21]`; the names given are `names(1) + names(12) + ... + names(21)`.
  - `test_detours_come_first_once_each`: `Start(page=12, furthest=names(12)[0], detours=(5, 7))` → `[5, 7, 1, 12, ..., 21]`.
  - `test_a_fresh_pass_with_a_detour_reads_it_before_page_1`: `Start(detours=(5,))` → `[5, 1, 2, ..., 21]`.
  - `test_a_shifted_list_steps_back_until_the_first_name_is_not_after_the_furthest`: `Start(page=12, furthest=names(10)[5])` → `[1, 12, 11, 10, 11, 12, 13, ..., 21]`; names given start `names(1) + names(10) + names(11)`; `[r.page for r in reads][:4] == [1, 12, 11, 10]`.
  - `test_no_step_back_when_the_first_name_is_the_furthest`: `Start(page=12, furthest=names(12)[0])` → no page 11 requested.
  - `test_the_step_back_stops_at_page_2`: `Start(page=4, furthest=names(1)[5])` → `[1, 4, 3, 2, 3, 4, ..., 21]`.
  - `test_a_resume_page_past_the_last_starts_at_the_last`: pager names 21, `Start(page=22, furthest=names(21)[3])` → `[1, 21]`, page 22 never requested.
  - `test_a_resume_on_a_one_page_list_reads_page_1_only`: page 1 with no pager → `[1]`.
  - `test_pages_read_out_of_number_order_are_not_compared`: detour 5 then page 1, and the step back 12 → 11 → 10: every `in_order` is True.
  - `test_each_kind_starts_at_its_own_point`: kinds `("PriceFull", "PromoFull")`, a start for PromoFull only → PriceFull reads from page 1 to its last, PromoFull from its start.
  - `test_the_time_is_asked_before_detours_and_steps_back`: `ShortFrom(n)` stops with `OutOfTime("before page 11 of the PriceFull listing")` in the step-back case, and with `"before page 5 ..."` in the detour case.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_shufersal.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement** the reading order in `_pages`.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_shufersal.py tests/test_run.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, names ending `(q21 start)`, target `SHUFERSAL`: "no overlap: the resume reads the page after the furthest", "page 1 skipped on a resume", "detours after page 1", "no step back", "the step back goes below page 2", "the step back on an equal first name" (`>` → `>=`), "a resume page past the last read as given" (`min` dropped), "starts ignored". Run `.venv/bin/python scripts/mutation_check.py "q21 start"`. Expected: all CAUGHT.
- [ ] **Step 6: Commit** `"Shufersal adapter: start each kind where the run says: detours, page 1, the resume page again, a step back if the list shifted (q21)"`.

### Task 3: "Read in full" across runs: the joining rule (R37) as pure functions

**Files:**
- Create: `src/collector/pages.py`
- Modify: `src/collector/run.py` (the field `RunResult.pages` only; Task 5 fills it) and `tests/test_run.py` (`test_manifest_bytes` gains `"pages": []`)
- Test: `tests/test_pages.py` (new)
- Modify: `scripts/mutation_check.py` (add `PAGES = ("src/collector/pages.py", ["tests/test_pages.py"])` and `PAGES_FOR_CHECK = ("src/collector/pages.py", ["tests/test_check.py"])`)

**Interfaces:**
- Consumes: manifests as stored (JSON dicts, one chain, one day, in key order); each page record is `asdict(PageRead) | {"taken_through": str | None}` (Task 5 writes them).
- Produces:

```python
def read_in_full(manifests: list[dict], kind: str) -> list[str] | None
    """The run ids whose readings of `kind` join up from page 1 to the last page (ruling R37), in the
    manifests' order; None when they do not."""
def unread(manifests: list[dict], kind: str) -> str
    """What of `kind`'s list no counted run read, for the failed alert."""
def has_pages(manifests: list[dict], kind: str) -> bool
    """Whether any manifest of the day recorded a page of `kind`."""
```

- The rule, from the design's section 3 (build it as written):
  - **Counted runs:** the manifests covering `kind`, not blocked; a run that stopped on time or on an error counts for the pages it read.
  - **Legacy:** a counted manifest with no page records (the key absent, or an empty list: other chains, and Shufersal before this change) and no error reads `kind` in full on its own, as R36 reads it today.
  - **Blocks:** a run's records of `kind` with `taken_through` set, in the order read, split wherever a page number is not one more than the one before. A block starts at its first page's `first`, or before everything when that page is 1; it ends at its last page's `taken_through`, or after everything when that page is the run's own last page (its page-1 record's `last_page`, or 1 when that is `None`; no page-1 record, no open end) and `taken_through == last`.
  - **Joining:** blocks of every counted run, sorted by start (from page 1 first, then by name; among equal starts the one ending furthest first), walked from the front: the reading's end moves to a block's end when the block starts at or before it. The kind is read in full when the end opens. A run contributes when one of its blocks moved the end forward.
  - **Order:** if any record of `kind` in the day's manifests (blocked runs included) has `in_order: false`, joining is off: only a run whose own single block runs from page 1 to an open end counts.
  - **Result:** the legacy runs' ids plus, when the pages join up, the contributing runs' ids (or, with joining off, the runs that read every page in one go), in manifest order; None when that is empty.
- `unread`: L = the largest last page the counted runs' page-1 records name (`last_page or 1`). A page is read when some counted record of it has `taken_through == last`, read in part when some record has `taken_through` set and none read it. Text, parts joined with ", ": `"<pages> never read"`, `"<pages> read in part"`; when neither applies, `"every page was read, but the pages read do not join up"`; with no counted page-1 record, `"page 1 never read, so the last page is not known"`. When joining is off, add ` (page <n> of run <id> was out of order, so only a run that read every page in one go counts)` for the first such record. `<pages>`: sorted ranges, each `a` or `a to b`, joined with ", ", after `page ` for one page in all and `pages ` otherwise (`{20, 21}` → `pages 20 to 21`; `{3, 17, 18, 19, 20, 21}` → `pages 3, 17 to 21`).

- [ ] **Step 1: Write the failing tests** in `tests/test_pages.py`, with helpers:
  - `name(i, kind="PriceFull")` → `f"{kind}7290027600007-001-{i:03d}-20261105-030000"`; page p of a 21-page list holds rows `20(p-1)+1` to `20p`.
  - `rec(page, taken=20, *, last_page=..., in_order=True, kind="PriceFull")` → a page record (`taken` a row number on the page or None; `last_page` defaults to 21 for page 1, None otherwise).
  - `run(run_id, *records, kinds=("PriceFull",), error=None, blocked=None, listed=())` → `json.loads(manifest_bytes(RunResult(..., pages=[...])))`, its mode read from the run id. Add the field it needs here, `RunResult.pages: list[dict] = field(default_factory=list)`; everything else in run.py is Task 5's.
  - `STOPPED = "stopped: under 90 s left"`; `A = run("044522Z-main-a001", *(rec(p) for p in range(1, 12)), rec(12, taken=1), error=STOPPED)`; `B = run("050002Z-main-a002", rec(1), *(rec(p) for p in range(12, 22)))`.

  Tests:
  - `test_one_run_from_page_1_to_the_last_reads_in_full` → `["…"]`.
  - `test_a_run_that_stopped_short_does_not_read_in_full`: `[A]` → None.
  - `test_two_runs_join_when_the_second_starts_where_the_first_stopped`: `[A, B]` → `["044522Z-main-a001", "050002Z-main-a002"]` (the 2026-11-05 shape).
  - `test_a_run_that_adds_nothing_does_not_contribute`: `[A, B, retry reading page 1 only]` → the retry's id not in the result.
  - `test_a_gap_between_runs_is_not_read_in_full`: B starting at page 13 → None.
  - `test_the_last_page_counts_only_to_the_row_taken`: B's page 21 taken through row 5 → None (design, Call 6).
  - `test_the_end_is_the_runs_own_pager_reading`: B's page-1 record names 22, B ends at 21 → None.
  - `test_an_out_of_order_page_turns_joining_off`: A's page 7 `in_order=False` → `[A, B]` is None; adding `C` (pages 1 to 21 in one go) → `["C…"]`; the out-of-order page in a blocked run turns joining off too.
  - `test_a_blocked_run_does_not_count`: B blocked → None.
  - `test_a_run_with_an_error_counts_for_the_pages_it_read`: B with `error="listing failed: …"` → joined.
  - `test_manifests_without_pages_and_no_error_read_in_full`: the key absent, and `pages: []`, each with no error → its id; with an error → None.
  - `test_other_kinds_pages_do_not_count`: PromoFull records → PriceFull None.
  - `test_a_page_with_nothing_taken_is_left_out`: B read `1, 14, 13, 12, 13, …, 21` with 14 and 13's first reads untaken → joined.
  - `test_a_detour_page_alone_is_a_block_of_its_own`: a run that read detour page 25 (served as page 21's rows, `taken` 20) then page 1 and stopped → not open, None alone.
  - `test_a_one_page_list_with_no_pager_reads_in_full`: Stores `rec(1, taken=1, last_page=None, rows=1)` → read in full.
  - `test_unread_names_the_pages_never_read`: A plus a run reading 1, 12 to 16 → `"pages 17 to 21 never read"`.
  - `test_unread_names_a_page_read_in_part`: with page 16 taken through row 3 → `"pages 17 to 21 never read, page 16 read in part"`.
  - `test_unread_when_every_page_was_read_but_the_readings_do_not_join` → `"every page was read, but the pages read do not join up"`.
  - `test_unread_names_the_out_of_order_page` → ends `" (page 7 of run 044522Z-main-a001 was out of order, so only a run that read every page in one go counts)"`.
  - `test_unread_without_page_1` → `"page 1 never read, so the last page is not known"`.
  - `test_unread_page_ranges` → `"pages 3, 17 to 21 never read"`.
  - `test_has_pages`: True with any record of the kind (blocked runs included), False for legacy manifests and other kinds.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_pages.py -q`. Expected: fail (no module).
- [ ] **Step 3: Implement** `src/collector/pages.py` (imports `collector.sources` only; a module docstring states R37 in plain words).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_pages.py tests/test_run.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, names ending `(R37 join)`, target `PAGES`: "a blocked run counted", "a legacy run with an error read in full", "pages not split into blocks at a jump", "a block from page 1 not open at the front", "the last page open without every row taken", "the end read from the highest page, not the run's own pager", "a block starting exactly where the reading ends left out" (`<=` → `<`), "a gap joined" (the start-before-end condition dropped), "an out-of-order page ignored", "an out-of-order page in a blocked run ignored", "a run that adds nothing named a contributor", "unread counts a page read in part as read". Run `.venv/bin/python scripts/mutation_check.py "R37 join"`. Expected: all CAUGHT.
- [ ] **Step 6: Commit** `"pages.py: the day's readings of a kind joined across runs, and what was never read (ruling R37, q21)"`.

### Task 4: Where a run starts: the start point from the day's earlier manifests

**Files:**
- Modify: `src/collector/pages.py`
- Test: `tests/test_pages.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `read_in_full` (Task 3), `Start` (Task 1).
- Produces: `start_for(manifests: list[dict], kind: str, stored: set[str]) -> Start`, `stored` being the stored names (`<name>.gz`) of the chain's day.
- The cases (design, section 2), in this order:
  1. **No usable record → `Start()`:** no earlier run covers `kind`; or no earlier counted run recorded a page of it and it is not read in full; or any record of `kind` that day (blocked runs included) has `in_order: false`.
  2. **Failed files:** for each counted earlier run, each name in its `listed` that is not in `stored` sits on that run's page record whose `first <= name.removesuffix(".gz") <= taken_through`; those pages, other than page 1 (read anyway), are the candidate detours.
  3. **Read in full → a fresh pass:** `Start(detours=<every candidate page>, sorted)`.
  4. **Not read in full → resume:** the furthest name is the largest `taken_through` over the counted runs' records of `kind`, and the resume page that record's page number (the larger page when two records share the name). `Start(page=<it>, furthest=<it>, detours=<candidate pages before it>)`; a resume page of 1 is a fresh pass.
- Blocked earlier runs are left out (counted runs only), as the check leaves them out.

- [ ] **Step 1: Write the failing tests** (same helpers as Task 3):
  - `test_no_earlier_run_starts_at_page_1` → `Start()`.
  - `test_earlier_runs_without_pages_that_ended_with_an_error_start_at_page_1` → `Start()`.
  - `test_an_out_of_order_page_that_day_starts_at_page_1`: A with page 7 out of order → `Start()`; the same when the page is a blocked run's.
  - `test_the_2026_11_05_shape_resumes_at_page_12` → `start_for([A], "PriceFull", stored_for_A) == Start(page=12, furthest=name(221))`.
  - `test_the_furthest_name_across_runs` → the furthest of several runs' `taken_through`, with its page.
  - `test_a_blocked_run_is_not_resumed_from`: a blocked run that read further → the start comes from the other runs.
  - `test_read_in_full_starts_a_fresh_pass`: `[A, B]`, everything stored → `Start()`.
  - `test_a_failed_file_earlier_on_the_list_gets_a_detour`: `name(85)+".gz"` listed by A, not stored, resume at 12 → `Start(page=12, furthest=name(221), detours=(5,))`.
  - `test_a_fresh_pass_detours_to_a_failed_files_page_first`: `[A, B]` with `name(85)` not stored → `Start(detours=(5,))`.
  - `test_no_detour_for_page_1_or_the_resume_page_or_after`: failed names on pages 1, 12 and 15 → no detours.
  - `test_a_failed_name_is_found_without_its_gz`: a failed name that is a page's `taken_through` itself (row 20) is on that page.
  - `test_detours_are_sorted_and_each_once`: failed names on pages 7, 5, 7 → `(5, 7)`.
  - `test_other_kinds_runs_are_ignored`.
  - `test_a_mix_of_old_and_new_manifests_uses_the_records_there_are`: a pre-change manifest with an error and no `pages`, then A → resume at 12.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_pages.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement** `start_for`.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_pages.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, names ending `(q21 resume)`, target `PAGES`: "an out-of-order page ignored for the start", "a blocked run resumed from", "resume from the first page read, not the furthest", "a fresh pass when not read in full", "a resume when read in full", "no detours", "a detour for page 1", "a detour for the resume page", "a stored name located with its .gz". Run `.venv/bin/python scripts/mutation_check.py "q21 resume"`. Expected: all CAUGHT.
- [ ] **Step 6: Commit** `"pages.py: where a Shufersal run starts each kind, from the day's earlier manifests (q21)"`.

### Task 5: The run loop: reads the earlier manifests, hands over the start points, keeps the page records

**Files:**
- Modify: `src/collector/run.py`
- Test: `tests/test_run.py`
- Modify: `scripts/mutation_check.py`
- `src/collector/handler.py`: no change (it already hands the run loop the store).

**Interfaces:**
- Consumes: `PagedSource`, `PageRead`, `Start`, `Listed.ends_page` (Task 1); `start_for` (Task 4).
- Produces:
  - `RunResult.pages: list[dict]`, in the manifest as `pages`: one record per page reported, in the order read, `asdict(read) | {"taken_through": None}`. A source that is not a `PagedSource` leaves it empty (every other chain's manifest carries `"pages": []`).
  - For a `PagedSource` only, before the listing: one `store.read_records(manifest_key(day, slug, "").removesuffix(".json"))`, the starts `{kind: start_for(earlier, kind, self.stored) for kind in self.kinds}`, and `listing(http, kinds, short_of_time, starts=..., on_page=self._page)`. Other sources are called exactly as today, and no manifest is read.
  - Each item a paged listing gives sets the latest record's `taken_through` before anything else is done with it (the day and kind filter, the download): to the record's `last` when `item.ends_page`, else to `item.name.raw`. A row given and then stopped before its download (`not_attempted`) counts as taken; a page reported and never given (a step back) keeps `None`.
  - One log line per page, `logging.getLogger("collector.run")` at INFO: `"shufersal PriceFull page 7 of 21: 20 rows in 41.2 s"`, the "of" number being this run's page-1 reading of the kind (`last_page or 1`), `?` before page 1 is read (a detour).

- [ ] **Step 1: Write the failing tests** in `tests/test_run.py`, with `FakePagedSource(PagedSource)`: like `FakeSource`, but a `PageRead` entry is passed to `on_page`, and the `starts` it was handed are kept; and a helper writing an earlier manifest with page records (`tests/test_pages.py`'s `rec`, `name`, `run` may be imported).
  - `test_a_paged_source_is_handed_a_start_per_kind`, parametrized over the design's four cases, each with its `Start` written out as in Task 4's tests: not yet read in full → `Start(page=12, furthest=name(221))`; a failed file earlier on the list → the same with `detours=(5,)`; read in full → `Start()`; no usable record (an out-of-order page) → `Start()`. Asserts the handed `starts == {"PriceFull": <that Start>}`.
  - `test_earlier_manifests_are_the_chains_own_for_the_day`: another chain's and another day's manifests do not change the start.
  - `test_a_source_that_does_not_page_reads_no_manifests_and_records_no_pages`: `FakeSource` with a store that counts `read_records` calls → 0 calls, `pages == []`.
  - `test_each_page_is_recorded_with_how_far_the_run_took_it`: two pages, the clock runs short after the 3rd row of page 2 → `pages[0]["taken_through"] == pages[0]["last"]`, `pages[1]["taken_through"] == <3rd row>`.
  - `test_a_row_of_another_day_counts_as_taken`: the last row given is yesterday's → it is `taken_through`.
  - `test_a_row_stopped_before_its_download_counts_as_taken`: the row in `not_attempted` is `taken_through`.
  - `test_the_last_row_given_takes_the_page_to_its_end`: `ends_page=True` on a row that is not the page's `last` → `taken_through == last`.
  - `test_a_page_read_and_left_has_nothing_taken`: two `PageRead`s in a row (a step back) → the first keeps `None`.
  - `test_page_records_are_in_the_manifest_whatever_the_run_ends_with`: ListingUnreadable after page 1's rows → the manifest's `pages` holds page 1.
  - `test_each_page_gets_a_log_line`: `caplog` holds `"shufersal PriceFull page 7 of 21: 20 rows in 41.2 s"`, and a detour before page 1 logs `"... page 5 of ?: ..."`.
  - `test_the_real_shufersal_adapter_resumes_where_the_last_run_stopped`: a 4-page list (`page(2, names(p), last=4)`), an earlier manifest in the store whose records carry test_shufersal's `names(p)` (pages 1 to 3, page 3 taken through row 4, its files stored); `ShufersalSource(timer=ticks(30.0))` over test_shufersal's fake network → listing pages requested `[1, 3, 4]` (a fresh pass would read page 2), and the new manifest's `pages` are pages 1, 3 and 4, each taken to its last row.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_run.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement** in `_Run` (`collect`, a `_page` callback, the taken-through update ahead of `_take`).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_run.py tests/test_handler.py tests/test_shufersal.py tests/test_pages.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, names ending `(q21 run)`, target `RUN`: "earlier manifests not read" (`starts={}`), "starts read for a source that does not page", "taken through not recorded", "taken through recorded after the day filter", "taken through recorded after the download", "ends_page ignored", "pages left out of the manifest". Re-point the run loop's existing mutations on the listing call ("run lends the listing no time check", "listing read before the files are fetched (R16)", "listing read twice"). Run `.venv/bin/python scripts/mutation_check.py "q21 run" "listing"`. Expected: all CAUGHT, none STALE.
- [ ] **Step 6: Commit** `"Run loop: read the day's earlier manifests, hand Shufersal its start points, record and log each page read (q21)"`.

### Task 6: The check: R37 in the check record, the excuse and the alert

**Files:**
- Modify: `src/collector/check.py`
- Test: `tests/test_check.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `read_in_full`, `unread`, `has_pages` (Task 3).
- Produces:
  - The check record gains, per chain, `read_in_full`: `{kind: read_in_full(manifests, kind)}` for each of `FULL_KINDS` the chain collects (other chains included: their runs read by the legacy rule).
  - R36 amended (`_short_of_time`): a retry whose error is exactly `OUT_OF_TIME` is excused when nothing is missing, `read_in_full(manifests, kind)` is not None for every kind it covers, and every name it listed was listed by another run among those ids (the retry's own names never vouch for themselves).
  - `_failure` gains, after R35's reasons, for each full kind the chain collects that some manifest recorded pages of (`has_pages`) and that is not read in full, when no retry run of the chain was blocked: `f"the {kind} list was not read in full: {unread(manifests, kind)}"`. Chains and days with no page records get no new reason (other chains unchanged, and so is a deploy day's first morning).
  - R4 is unchanged (design, Call 1): a retry whose list read failed for another reason still alerts, read in full or not.

- [ ] **Step 1: Write the failing tests** in `tests/test_check.py`, section `# ---- the day's pages joined across runs (ruling R37) ----`, with `paged(store, run_id, kind, records, listed=(), error=None, blocked=None)` writing a manifest through `RunResult(pages=...)` and `legacy(store, run_id, kinds, listed, error=None)` writing one without the `pages` key; `SHUFERSAL_FULL = {"shufersal": ("PriceFull", "PromoFull")}`.
  - `test_read_in_full_is_recorded_per_full_kind`: the 2026-11-05 PriceFull shape plus a clean PromoFull run → `record["chains"]["shufersal"]["read_in_full"] == {"PriceFull": ["044522Z-main-a001", "050002Z-main-a002"], "PromoFull": [...]}`; a clean NCR-style chain records its retry's id.
  - `test_a_stopped_retry_on_a_day_read_in_full_across_runs_is_quiet`: A and B join, the retry's fresh pass stopped on time after listing names A or B listed, nothing missing → no alert, `short_of_time == ["074536Z-retry-2933 (PriceFull)"]`.
  - `test_a_stopped_retry_whose_names_only_it_listed_still_fails`: the retry listed a name neither A nor B did → failed alert names the retry's time stop.
  - `test_a_full_kind_not_read_in_full_names_the_pages_never_read`: PromoFull main runs read 1 to 16, the retry stopped on time → alert text exactly `"shufersal: the day's runs fell short: retry run 081551Z-retry-9283 (PromoFull) ended with: stopped: under 90 s left; the PromoFull list was not read in full: pages 17 to 21 never read."`.
  - `test_not_read_in_full_alerts_on_its_own`: every run ended clean but the readings leave a gap → `"shufersal: the day's runs fell short: the PriceFull list was not read in full: every page was read, but the pages read do not join up."`.
  - `test_a_blocked_run_does_not_join_in_the_check` and `test_an_out_of_order_page_turns_joining_off_in_the_check` (the alert carries the out-of-order clause).
  - `test_no_sentence_when_a_retry_was_blocked`: the stopped alert covers it (as R35).
  - `test_no_sentence_without_page_records`: an NCR-style chain whose runs all ended with errors → R4's reasons only.
  - `test_a_pre_change_manifest_ended_clean_reads_in_full`: `legacy(...)` with no error, a paged retry stopped on time listing its names → quiet.
  - Every existing R36 test passes unchanged (their manifests carry `pages: []`, read by the legacy rule).
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_check.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement**; update `check.py`'s docstring (the R36 paragraph becomes R36 as amended by R37).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_check.py tests/test_handler.py tests/test_pages.py -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, names ending `(R37)`, target `CHECK` unless named: "read_in_full left out of the record", "the retry's own names vouch for it", "a kind not read in full excuses the retry", "not read in full never alerts", "not read in full alerts with a retry blocked", "not read in full alerts on a chain with no page records", "the pages never read left out of the sentence". Re-point the R36 mutations whose text moved: those on the excuse stay on `CHECK`; those on what reads a listing in full ("a run that ended with an error read as a listing read in full (R36)", "a blocked run read as a listing read in full (R36)", "only a main run read as a listing read in full (R36)") move to `PAGES_FOR_CHECK`, so the R36 tests still prove them. Run `.venv/bin/python scripts/mutation_check.py "R36" "R37"`. Expected: all CAUGHT, none STALE.
- [ ] **Step 6: Commit** `"Check: ruling R37: read in full judged from the pages the day's runs read, recorded per full kind, and the pages never read named in the failed alert (q21)"`.

### Task 7: The 2026-11-05 morning, replayed

**Files:**
- Create: `tests/test_replay.py` (it crosses the adapter, the run loop and the check, so it has a file of its own)

**Interfaces:**
- Consumes: `collect_chain`, `ShufersalSource(timer=...)`, `check_day`, test_shufersal's `connect`, `served`, `page`, `gz`, `listing_url`, test_run's `Clock`.

The morning, synthetic (design, "Why" and "2026-11-05 replayed"): day 2026-11-05; each full kind 21 pages of 20 rows, page 1's pager on every page naming 21 (`page(cat, rows, last=21)`); row i of a kind is `f"{kind}7290027600007-001-{i:03d}-20261105-030000"`, i = 1 to 420. Pace, from the design's "40 to 45 s a page and 1 to 2 s a download": PriceFull 42 s a page and 1.5 s a download, PromoFull 45 s and 2 s, each route moving the run's `Clock` back by that much; each run starts with 900 s left, a fresh `Http` and a fresh `ShufersalSource(timer=lambda: -clock.left)`. A retry's second page read raises `TimeoutError("timed out")` (the 60 s socket timeout). Runs, in time order, into one `MemoryStore`: PriceFull `044522Z-main-a001`, `050002Z-main-a002`; PromoFull `051514Z-main-b001`, `053014Z-main-b002`; retries `074536Z-retry-2933` (PriceFull) and `081551Z-retry-9283` (PromoFull), as in the design. Then `check_day(store, ["shufersal"], DAY, kinds={"shufersal": ("PriceFull", "PromoFull")})`.

Expected (worked out from the pace and the 90 s rule; the test asserts each):

| Run | Listing pages requested | Ends with | Page records, and how far taken |
|---|---|---|---|
| PriceFull main 1 | 1 to 12 | `stopped: under 90 s left` | page 12 taken through row 221, which is `not_attempted` |
| PriceFull main 2 | 1, 12 to 21 | no error, 200 files stored | 11 records, every page taken in full, each `seconds == 42.0` |
| PromoFull main 1 | 1 to 10 | `stopped: under 90 s left` | page 10 taken through row 181, stored |
| PromoFull main 2 | 1, 10 to 19 | `stopped: under 90 s left` | page 19 taken through row 361, which is `not_attempted` |
| PriceFull retry | 1, 2 | `listing failed: …timed out` | page 1 (a fresh pass: PriceFull was read in full) |
| PromoFull retry | 1, 19 | `listing failed: …timed out` | page 1 (resumed at page 19, which timed out) |

The check: `read_in_full == {"PriceFull": ["044522Z-main-a001", "050002Z-main-a002"], "PromoFull": None}`; a `missing` alert for row 361's PromoFull file; the failed alert reads `"shufersal: the day's runs fell short: retry run 074536Z-retry-2933 (PriceFull) ended with: listing failed: <the timeout text>; retry run 081551Z-retry-9283 (PromoFull) ended with: listing failed: <the timeout text>; the PromoFull list was not read in full: pages 20 to 21 never read, page 19 read in part."`. So PriceFull reads in full by the second main run and the email still goes for the retry's failed read (Call 1); PromoFull's email says how much of the list was read.

- [ ] **Step 1: Write the test** `test_the_2026_11_05_morning_replayed`, one test asserting the table and the check, with a docstring naming the design section and saying that the counts are synthetic (expected, not measured). If a row of the table does not come out as written, check the arithmetic against the pace before touching code, and log the difference in this plan's "Deviations".
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_replay.py -q`. Expected: pass (Tasks 1 to 6 built the behaviour; a failure here is a bug in them or in the table).
- [ ] **Step 3: Prove it bites:** run `.venv/bin/python scripts/mutation_check.py "no overlap" "page 1 skipped on a resume"` with `tests/test_replay.py` added to those two entries' test lists. Expected: CAUGHT.
- [ ] **Step 4: Commit** `"Test: 2026-11-05's Shufersal morning replayed on the resume (q21)"`.

### Task 8: The docs: R37 and what changed, in plain words

**Files:**
- Modify: `docs/collector-plan.md`, `docs/collector.md`, `docs/portals.md`, `docs/operations.md`

- [ ] **Step 1: `docs/collector-plan.md`**, "Rulings made during the build": add `- Ruling R37 (2026-11-05, the owner's choice of fix, design docs/shufersal-resume.md; amends R36): …` after R36, in R36's form (the rule, then "Why", then "Cost if wrong"). It states: the page records and the log line; the start cases (no usable record, detour, fresh pass, resume with one page of overlap and the step back); "read in full" across runs (counted runs, blocks, taken-through, joining, the order rule, the legacy rule); R36's conditions as amended (read in full by R37; the stopped retry's names listed by another run among those that joined up; nothing missing); the new sentence in the failed alert, only for kinds with page records and never with a retry blocked; `read_in_full` in the check record; and the readings this plan chose where the design left room (the order check compares only consecutive page numbers; blocked runs are not resumed from; a fresh pass detours to every failed file's page but page 1; pages read in part named apart from pages never read). Why: 2026-11-03 and 2026-11-05 (the design's table). Cost if wrong: the design's "Risks kept".
- [ ] **Step 2: `docs/collector.md`:** "How a morning runs" step 3 (a Shufersal run reads the day's earlier manifests and picks up where they stopped, pointing to `shufersal-resume.md`); "Storage", the manifests line (the listing pages read, Shufersal's); "Alerts", the R36 bullet (read in full judged across runs, R37; the failed alert names the pages never read).
- [ ] **Step 3: `docs/portals.md`, "Shufersal":** a bullet **Order**: every run from 2026-11-03 to 2026-11-05 listed its names in file-name order, each run's list the start of the longest's (observed, not promised; the collector checks it on each page). In **Speed**: 2026-11-05's pace worked out from run times (about 40 to 45 s a page, 1 to 2 s a download; page 2 passed the 60 s socket timeout in both retries), and that each page's time is now logged and kept in the manifest.
- [ ] **Step 4: `docs/operations.md`:** "What runs when" (Shufersal's second run of a full kind picks up where the first stopped instead of reading from page 1 again; the R36 paragraph becomes R37, with the new sentence); step 6's "Shufersal's full files take two runs each" (a third run, if needed, also resumes); step 8 (the manifest's `pages`, field by field; the check record's `read_in_full`); the logs (the per-page line, with its example); "Cost" (one listing and up to eight manifest reads per Shufersal run, well under $0.01 a month).
- [ ] **Step 5: Verify** `.venv/bin/python -m pytest tests/test_template.py -q` (it pins the operations doc's commands and timetable). Expected: pass. Then `grep -n "from page 1 again\|read that kind's whole listing" docs/*.md` finds nothing stale; every fact added is checked against the code built in Tasks 1 to 6 or the design's measured lines.
- [ ] **Step 6: Commit** `"Docs: ruling R37 and the Shufersal resume in the design, portal and operations notes (q21)"`.

### Task 9: Full test run, coverage and the full mutation check

- [ ] **Step 1:** `.venv/bin/python -m pytest --cov=collector --cov=src/basket --cov-fail-under=95` (CI's command). Expected: every test passes (baseline 1,207, about 90 more), coverage at or above 95% (baseline 99.82%), and `src/collector/pages.py` at 100%.
- [ ] **Step 2:** `.venv/bin/python scripts/mutation_check.py`. It edits source files in place: run nothing else from this checkout until it prints "Files restored." Expected: every mutation CAUGHT, none MISSED, STALE or ERROR (baseline 976, about 55 more).
- [ ] **Step 3:** `cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: clean (no template change).
- [ ] **Step 4:** update README.md's two count lines (the "Tests" row and "Tests that are themselves tested") to the numbers Steps 1 and 2 printed, with the date; commit `"README: test and mutation counts after the Shufersal resume (q21)"`.

### Task 10: A fresh review

- [ ] **Step 1:** dispatch a reviewer subagent that has not seen the build, on Fable (`model: "fable"`), or on the newest Opus (`opus`) while Fable is at its usage limit, naming the swap. Give it: the branch's diff against main (`git diff main...q21-shufersal-resume`), `docs/shufersal-resume.md`, this plan, `docs/collector.md` and R36 and R37 in `docs/collector-plan.md`. Ask for findings by severity against the design's Anti-goals ("a day reported complete when part of the list was never read"; "a run that skips a page because the list shifted between runs"), the Calls, and this plan's Review Focus. The reviewer reads only: no commits, no `gh`, no push, no AWS, no network.
- [ ] **Step 2:** check each finding against its source before acting on it (a finding is a claim); fix what holds, test-first, each fix with its mutation; log every change from this plan in "Deviations" below; re-run Task 9's Steps 1 and 2.
- [ ] **Step 3:** stop. Merge, push and deploy are the owner's go, from main, after a merge; the deploy and the first morning's reading are outside this plan.

## Deviations

- 2026-11-05, Task 1: also changed `tests/test_chains.py`, which pins `Listed`'s fields and each adapter's `listing` parameters, so the new `ends_page` and Shufersal's `starts` and `on_page` failed two of its tests. `Listed`'s fields now include `ends_page` (default False); a `PagedSource` adapter is compared with `PagedSource.listing`, any other with `Source.listing`; new tests pin `PagedSource.listing`'s parameters, defaults and types, `Start()` as a fresh pass, and `PageRead` and `Start` as frozen.
- 2026-11-05, Task 2: three mutations beyond the brief's eight, for rules this task's tests cover and no mutation broke: "a page stepped back over gives its rows", "a page stepped back over not reported" and "pages read out of number order compared" (Task 1's order rule, untestable until pages were read out of number order); 11 `(q21 start)` mutations in all. Two of the new tests (`test_a_fresh_pass_reads_page_1_to_the_last`, `test_a_resume_on_a_one_page_list_reads_page_1_only`) passed before the change, since Task 1 already read a fresh pass and a one-page list that way.
- 2026-11-05, Task 3: five mutations beyond the brief's twelve, for parts of the rule that none of the twelve broke: "a page past the run's own last page opens the end", "blocks not taken from the front", "blocks that start together not taken furthest first", "with joining off, a run that read every page in one go not counted" and "other kinds' pages counted"; 17 `(R37 join)` mutations in all. Two tests beyond the brief's list (`test_with_joining_off_a_detour_before_a_whole_pass_still_counts`, `test_unread_reads_to_the_largest_last_page_any_pager_named`) and a few more asserts in its tests (a run that adds nothing standing first in the day, page records beside a manifest without them, a detour beside a run short of page 21's last row, a run that did not read page 1). One reading where the brief left room: with joining off, a run counts when one of its blocks runs from page 1 to an open end, so a fresh pass that detoured first still counts (the design's "a single run that read page 1 to the last page in one go"). `pages.py` imports nothing from the project yet: Task 4's `Start` is its first import from `collector.sources`.
- 2026-11-05, Task 4 (controller ruling from Task 3's review): in `pages.py`, a page the run took only part-way ends its block, even mid-run, so R37 holds without relying on the run loop stopping there (today a run leaves a page part-way only by stopping). One test (`test_a_page_taken_part_way_ends_its_block`) and one mutation ("a page taken part-way mid-run joined (R37 join)"); the existing "pages not split into blocks at a jump (R37 join)" re-pointed at the rewritten line. 18 `(R37 join)` mutations in all.
- 2026-11-05, Task 4: six mutations beyond the brief's nine, each for a rule of the start that none of the nine broke: "another kind's run counted", "the smaller page taken when two records hold the furthest name", "a resume at page 1 kept as a resume", "detours not sorted", "a detour read twice" and "a stored file given a detour"; 15 `(q21 resume)` mutations in all. One test beyond the brief's list (`test_a_resume_at_page_1_is_a_fresh_pass`: a run that read page 1 and then timed out) and a few more asserts (the larger page when two records hold the furthest name, another kind's own start with its detour, a deploy-day manifest that ended clean). A and B in `tests/test_pages.py` now carry `listed`, the stored names of the rows they took, which the joining tests do not read. Readings where the brief left room: a failed name counts on every page record of its run that holds it (a run that read a page twice, as a detour and in its pass, holds it on both); a resume at page 1 is a fresh pass with a detour to every failed file's page, as in case 3. A failed name sits on a page after the resume page only when the list moved between runs; `test_no_detour_for_page_1_or_the_resume_page_or_after` builds that case (the list grew by four pages).
- 2026-11-05, Task 4 review fix: Task 4 landed as two commits (c542140, the part-way block rule; 1b22dde, the start) and this fix. The review found a resume at page 1 carrying its detours untested; `test_a_resume_at_page_1_keeps_its_detours` (the list shrank, so a later run's page 1 took the furthest name, and a failed file on page 5 still gets its detour) and the mutation "a resume at page 1 drops its detours" pin it. By the controller's ruling, a day not read in full only because of a gap between blocks still resumes at the furthest page: `test_a_gap_between_blocks_still_resumes_at_the_furthest_page` and the mutation "resume at the end of the joined reading" pin it. 17 `(q21 resume)` mutations in all. The resume's `Start` now takes keywords.
- 2026-11-05, Task 5: eight mutations beyond the brief's seven, for rules this task's tests cover and none of the seven broke: "another chain's manifests read", "another day's manifests read", "taken through set on a page before the latest", "a page recorded taken before a row is given", "page logged below INFO", "page count read from any page", "page count not per kind" and "a one-page list's count not 1"; 15 `(q21 run)` mutations in all. `test_earlier_manifests_are_the_chains_own_for_the_day` runs once for another chain and once for another day; `test_page_records_are_in_the_manifest_whatever_the_run_ends_with` runs for three endings (an unreadable listing, time, a block) where the brief named one; `test_each_page_gets_a_log_line` also logs another kind's detour after PriceFull's page 1 (`of ?`) and the one-page Stores list (`of 1`). `FakePagedSource` subclasses `FakeSource` as well as `PagedSource`, so it gives rows, raises and downloads as `FakeSource` does. The real-adapter test builds its earlier manifest from a `RunResult`, since `tests/test_pages.py`'s `run` is dated 2026-11-05 and test_shufersal's names 2026-10-31. Readings where the brief left room: the listing stays one call, `listing(http, kinds, short_of_time, **paged)`, with `paged` empty for a source that does not page; the update of `taken_through` is the first thing `_take` does; a failed read of the earlier manifests fails the run as an unexpected error (the manifest is still written), as a failed read of the latch does, with no fall-back to a fresh pass. The log line keeps the brief's wording for a page of one row ("1 rows").
- 2026-11-05, Task 6 (controller ruling): beside the runs among `read_in_full`'s ids, a retry's names are vouched for by any other run that read the kind in full on its own (`read_in_full([run], kind)` is not None), where the brief had "listed by another run among those ids": `read_in_full` names only the runs that moved the joined reading on, so on a fast morning with two whole passes it names the first, and a file published between them, listed only by the second pass and a stopped retry, would raise the false alarm ruling R36 removed on 2026-11-04. A run that read only part of the list still vouches for nothing. Pinned by `test_a_second_whole_pass_vouches_for_a_file_published_between_the_passes`, `test_a_run_that_read_part_of_the_list_does_not_vouch` and the mutation "a second whole pass does not vouch (R37)".
- 2026-11-05, Task 6: (1) The vouching runs come from the other runs' reading with the retry's pages left out (`read_in_full` over the day's manifests without the retry), not from `read_in_full` over all of them. A stopped retry's fresh pass downloads nothing, every file being stored, so it reads further than the morning's first run before it stops; joined with the retry's pages, the reading names the retry and the second run and leaves the first out, and the names only the first run and the retry listed (pages 2 to 11 on 2026-11-05's shape) would alert on a complete morning, the same false alarm as above. The excuse still needs `read_in_full` over every manifest, the retry's included, for each kind it covers. Pinned by `test_a_retry_that_read_further_than_a_run_before_it_is_still_vouched_for` and the mutation "the vouching runs found with the retry's own pages (R37)". (2) A run vouches only for names of a kind it read (the kind read from the name, as R35 reads it): a run over both full kinds that read PriceFull in full and PromoFull in part vouches for the retry's PriceFull names only. R36 took the clean runs' names together, which held while a clean run read every kind it covered in full. Pinned by `test_a_run_vouches_only_for_the_kinds_it_read` and "a run vouches for every kind it listed (R37)". (3) The brief's "a kind not read in full excuses the retry (R37)" breaks R37's reading of "read in full" back to R36's (some run of the kind ended with no error and was not blocked), since R36's re-pointed "a retry short of time excused with no listing read in full" already removes the check itself; `test_a_retry_that_listed_nothing_needs_its_kind_read_in_full_from_the_pages` catches it. (4) Mutations beyond the brief's seven and the ruling's one: "a full kind the chain does not collect recorded", "a full kind the chain does not collect judged", "a run that read part of the list vouches", (1)'s and (2)'s; 13 `(R37)` check mutations in all. Tests beyond the brief's ten and the ruling's two: (1)'s, (2)'s and (3)'s, `test_a_full_kind_the_chain_does_not_collect_is_neither_recorded_nor_judged`, and `test_a_retry_never_vouches_for_its_own_names`, which pins the brief's rule with a resumed retry that took the list to its last row and then met the time check: it still alerts, though the day was read in full and nothing is missing. (5) R35's "a full kind no run listed passes" re-pointed at the rewritten join of the reasons; R36's "a blocked run read as a listing read in full" now breaks pages.py's leaving out of blocked runs, its other two moved mutations the legacy rule. The tests reuse `tests/test_pages.py`'s 2026-11-05 shapes (`A`, `B`, `rec`, `pages`, `gz`, `late`), as `tests/test_run.py` does.
- 2026-11-05, Task 8: beyond the four docs the brief names, the design (`docs/shufersal-resume.md`: the step back explained the right way round in section 2, section 3's block rule with the part-way page, and a closing "Changed during the build" that lists the build's decisions and points to R37) and prose-only fixes the reviews found: the step back explained backwards in the adapter's `_reads` docstring and in its test's docstring; `check.py`'s R36-as-amended paragraph in short sentences; `run.py`'s "called as before page records" (and the same slip in `pages.py` and in a `tests/test_run.py` docstring); `tests/test_replay.py`'s comment on `limit`, which caps the run's requests and does not by itself catch a page read twice; a comment in `scripts/mutation_check.py`. No code changed. Two places where the brief and the code differ, the code kept: R37 states the stopped retry's excuse as built (each kind it covers read in full with its own pages included; only the vouching runs are found without them), where the controller's note read the full reading without them; and the cost line counts what the eight scheduled Shufersal runs read (8 listings and 28 manifest reads a day, at most seven reads a run), where the plan said up to eight reads a run.
- 2026-11-05, final whole-branch review fixes: (1) R37's excuse said as the code gives it, in `docs/collector-plan.md` ("R36 as amended"), `docs/collector.md`, `docs/operations.md` and `check.py` (the module docstring and `_seen_by_others`): a run that read only part of the list vouches only when, with the retry's pages left out, its pages carry the joined reading further than the pages joined before them; a part other runs' pages already cover vouches for no name, where the docs had said a part that joins with others' into a full reading vouches. (2) `test_a_failed_read_of_the_earlier_manifests_fails_the_run` and the mutation "a failed read of the earlier manifests falls back to a fresh pass (q21 run)" pin the ruling that a failed read of the day's earlier manifests fails the run as an unexpected error. (3) `run.py` reads the earlier manifests before it sets `listing_read_at`, so a failed read leaves it null, as `docs/operations.md` says (the test asserts it); "listing read before the files are fetched (R16)", "listing read twice", "run lends the listing no time check" and "time not checked before the listing" re-pointed at the moved lines. (4) Wording: `docs/operations.md`'s `read_in_full` entry drops "clean" (R33's word for something else) for the legacy rule as the code reads it (no page records, not blocked, no error, one that listed nothing included), and says the whole passes of a day with a page out of order stand beside those runs; `check.py`'s record paragraph and `read_in_full`'s docstring say what it returns; R37's "which reading on covers" says what it covers. (5) 1,312 tests, coverage 99.83%, 1,059 mutations, all caught; cfn-lint clean; README's counts updated.

# Headline Basket Implementation Plan (step two: every morning)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade:** production-lean, the collector's grade: it runs unattended every morning and publishes to a public address, so every rule has a test and a mutation, a fresh reviewer reads every task, and a dead-man check watches it; no retries, no incremental processing, no dashboards, no second region.

**Monthly cost (estimate; sources in "Cost" below):** about $0.10 to $0.90 in year one, rising with the tables kept (about 95 MB a day); worst case about $3.50. The account's $5 budget alarm stands.

**Goal:** the page at https://d153udx05irk2f.cloudfront.net rebuilds itself every morning from the archive, with no hand in it, and tells the owner when it did not.

**Architecture:** a second Lambda function, `BasketFunction`, in the collector's stack (`template.yaml`), running the same `src/basket/` code the hand build runs, over a work folder under `/tmp` filled from the archive bucket and emptied after each run. Two event modes, as the collector's handler has: `extract` (one chain's full price files for the day into one Parquet table under `tables/`), five schedules 15 minutes after the collector's check (11:00 Israel time today), one per chain; and `basket` (the five tables, the store lists and the day's manifests into the day's record, the two pages and the day file; the record locked under `basket/`, the pages uploaded to the site bucket, one CloudFront invalidation, one healthchecks.io ping), one schedule 30 minutes after that (11:30 today). Neither runs before the day's check record exists (call 11). The published day is read from the site bucket, never a folder (`.claude/DECISIONS.md` 2026-11-02, "The revision gate rests on the published copy"); the scheduled run never revises, so a day whose numbers differ fails loudly. DuckDB arrives in a Lambda layer built by `sam build` from a hash-pinned wheel for Lambda's arm64 Linux, so the function's own package stays `src/` and the record's code fingerprint equals the one computed on the Mac. Failing loudly is a `/fail` ping to the dead-man check with the error text; no new CloudWatch alarm (design call 10).

**Tech Stack:** Python 3.13 on Lambda arm64 (Amazon Linux 2023), `duckdb==1.5.6` (the `manylinux_2_28_aarch64` wheel, 18.6 MB zipped, 55 MB unzipped, uploaded to PyPI 2026-09-28), boto3 from the runtime, SAM (`AWS::Serverless::Function`, `AWS::Serverless::LayerVersion` with `BuildMethod: makefile`), EventBridge Scheduler (`ScheduleV2`), healthchecks.io.

**Spec:** `docs/headline-basket.md`, "The pipeline" (Step two), rules B1, B8, B10, B11, B12, "Cost", calls 1, 7, 9, 10 and "Left to the builder"; `docs/operations.md`, "What runs when" and "The headline basket, by hand"; `.claude/OPEN_ISSUES.md`, Showcase, "Headline basket, step two" (the measurements). Executors read the spec and this plan.

## Calls made in this plan (the owner approved them in chat on 2026-11-03; calls 11 to 13 came from the builder check and were approved the same night)

1. **DuckDB in a layer**, built by `sam build` through a Makefile that runs pip with `--platform manylinux_2_28_aarch64` (AWS's documented way for native wheels is pip's `--platform` flag, https://docs.aws.amazon.com/lambda/latest/dg/python-package.html; the wheel carries no `manylinux2014` tag; Lambda's python3.13 runs on Amazon Linux 2023, https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html, whose glibc is 2.34, https://docs.aws.amazon.com/linux/al2023/ug/glibc-gcc-and-binutils.html, newer than the wheel's 2.28; all read 2026-11-03). SAM builds a layer whose `Metadata` says `BuildMethod: makefile` by running the target `build-<LogicalId>` of the `Makefile` at the root of its `ContentUri`, with the output folder in `$(ARTIFACTS_DIR)` (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/building-layers.html, read 2026-11-03). The command ran on this Mac on 2026-11-03 from Python 3.14's pip with the hash pin: 53 MB in `python/`, the `.so` 54,606,888 bytes. The function's zip is `src/` alone, so `basket.record.code_fingerprint()` in Lambda hashes the same files as on the Mac. Alternative rejected: Docker builds (`sam build --use-container`), one more moving part.
2. **"Collected by" (B11)** is the basket event's `collected_by` in the template, `"11:00"`, and a template test pins it to the extraction schedules' hour and minute. Nothing in the run reads the clock for it, so the record stays deterministic. Alternative rejected: each extraction writing its start time into `report.json`, a new field for a value the template already fixes.
3. **Failing loudly** is a `/fail` ping carrying the error text, after a `/start` ping at the run's start (healthchecks.io then also shows the run's duration); a successful run pings the plain URL with the run's summary. An extraction run never pings: a chain whose extraction failed shows at 11:30 as a missing table, named. Pings that fail are logged, never raised.
4. **The role** grants what the code does and nothing else: reads of `raw/`, `manifests/`, `checks/` (call 11), `tables/` and `basket/` (call 13), plain writes of `tables/`, locked writes of `basket/`, a list of the archive bucket, reads of the site bucket's `days/`, a list of it, writes of its two pages and `days/`, and one CloudFront invalidation. The design's role text gains the `tables/` and `basket/` reads (Task 9).
5. **The site bucket and the distribution** reach the collector's stack as two deploy parameters, pattern-checked (the bucket `il-grocery-prices-site-sitebucket-*`, as `scripts/publish.sh` checks), and the code refuses any other bucket name. Alternative rejected: cross-stack exports, which would stop the site stack from ever being deleted while imported.
6. **Manual runs** carry an optional `"day"` (YYYY-MM-DD); a scheduled event has none and takes the Israel date of the run.
7. **The basket file moves into the package** (`basket/v1.json` → `src/basket/baskets/v1.json`), since the function's zip is `src/` and the basket is code the record names by version. Its bytes do not change, so v1 stays as approved. The design's "The list lives in the repo as `basket/v1.json`" is amended to the new path (Task 9). Found while planning; the owner approved it 2026-11-03. The root `basket/` folder then goes, and with it the reason CI measures coverage as `--cov=src/basket`.
8. **A store list is looked for 14 days back** when the day has none (the Mac's build looks back without limit over the synced folders; S3 has no cheap "latest folder before" and a chain two weeks without a store list is a collector problem). Found further back: `NoStoreList`, fail loudly.
9. **The record goes up whatever happened**: a run that stops on `RevisionNeeded`, a failed site check or a failed upload still uploads the private record it wrote (B12: every build of every day exists), then pings `/fail`.
10. **An extraction run downloads every full price file of the day** (B1's "latest per store" is applied by `basket.extract.day_files` on the work folder, as on the Mac); the basket run downloads tables, store lists and manifests only. Rami Levy's 72 passed-over files cost about 40 MB a run; selecting before the download would move a rule out of the code the Mac runs. Not worth it at this grade.
11. **Nothing of step two runs before the day's check record exists** (from the builder check, 2026-11-03; approved by the owner the same night, with q12's schedule change riding in Task 10's deploy). Both modes first look for a key under `checks/date=<day>/` and refuse (`MorningNotChecked`, a `/fail` ping from the basket run) when there is none: the collector's 10:45 check is the last run of the morning, so its record is the proof that "collected by" the extraction's time is true, whatever the timetable says. This restores the design's `checks/` read to the role. It matters now because QUEUE q12 (Osher Ad's main run after its 08:00 files) moves that chain's retry to about 11:15 and the check to about 11:45 by the collector's own pinned rules (a retry three hours after its main run; the check 30 minutes after the last retry can have finished), which is after step two's 11:00. So: step two's crons and the `collected_by` literal are chosen when Task 10 deploys, from the check's time then (today 11:00 and 11:30; with q12 landed, 12:00 and 12:30), Task 8's test `test_extraction_starts_after_the_collectors_check_can_have_finished` forces the move whenever the check moves, and B11's "11:00" in the design becomes "the extraction's scheduled start" (Task 9). The owner's decision (2026-11-03): q12's schedule change rides in Task 10's deploy, so step two's crons are set once.
12. **A manual run for a day earlier than the site's latest leaves the pages alone** (from the builder check): the day file and the record are still written, the two pages and the invalidation only when the run's day is the latest on the site, or the site has none. Otherwise a manual run for 2026-11-02 after later hand builds would put that day back on the front page, which the hand build avoids only by "build the latest last".
13. **The role reads `basket/` too**: a locked write refused by S3 (botocore retrying a put whose answer was lost) is compared through `head_object`, which needs `s3:GetObject`, as the collector's `ReadStored` grants on `checks/` for the same reason (`src/collector/store.py`, `put_record`).

## Global Constraints

- Everything in `docs/headline-basket-plan.md`, "Global Constraints", still holds (time-zone-aware datetimes; test data never reads the clock; fixtures synthetic; raw files never in the repo; a test and a named mutation for every rule; coverage floor 95%; the words; money as `Decimal`; store keys with leading zeros stripped; AWS writes on the owner's go; subagents never `gh` or push).
- No dependency younger than one month, pinned: `duckdb==1.5.6` is the only one; the layer pins it by version and SHA-256 (`364992ba1089a2b327391cfcb68fd0bd0ce9090cf293baef861a0ba6847abfee`, the `cp313-manylinux_2_26_aarch64.manylinux_2_28_aarch64` wheel on PyPI, uploaded 2026-09-28T13:38:11Z), and one test holds the layer's pin equal to `requirements-dev.txt`'s.
- The scheduled run never revises (B12, call 1 of the design): `build_day` is called with `revise=None`, and nothing in the handler may pass a reason.
- Nothing deletes, anywhere: no `s3:Delete*` in the role, no `delete_object` in the code (`tests/test_store.py::test_no_method_ever_deletes` has the pattern to copy for the archive and the site).
- Every AWS command in `docs/operations.md` names `--profile flights-sam --region il-central-1` (`tests/test_template.py` pins it).
- Every task runs the full `scripts/mutation_check.py` before committing, with nothing else running from the checkout; CI runs `pytest --cov=collector --cov=src/basket --cov-fail-under=95`, the mutation check and `cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`.
- Commit after each task with the message given; departures go in `## Deviations` at the end of this file.

## Review Focus

Failure modes the spec implies but no step-one test exercises, most likely first; each has its test in the task named.

1. **A warm container's `/tmp` fills up.** Lambda keeps `/tmp` between invocations of one container; a run that leaves its work folder behind makes the next Shufersal run fail on disk. Expected: the work folder is gone after every run, success or failure. Task 6, `test_work_folder_is_removed_after_success_and_after_failure`.
2. **A chain's extraction did not run** (a schedule off, a throttled invocation, a crash). Expected: the 11:30 run names the chain and publishes nothing, and the owner hears within the hour. Task 6, `test_missing_table_names_the_chain_uploads_nothing_and_pings_fail`.
3. **A second run of a published day** (the manual run after step one's hand upload; a manual run after the scheduled one). Expected: "unchanged", the pages uploaded, the day file not, a second record. Task 6, `test_unchanged_day_uploads_pages_not_the_day_file`.
4. **A thin morning**: a chain whose extraction found no files writes an empty table (B8). Expected: the run publishes, the chain shows "0 of M" and is out of the ranking; no crash. Task 6, `test_a_chain_with_no_files_publishes_with_the_chain_out_of_the_ranking`.
5. **healthchecks.io is down or slow** at 11:30. Expected: the run's outcome does not depend on the ping. Task 6, `test_a_failing_ping_is_logged_not_raised`.

## Cost (monthly; the figures behind the header)

- **Lambda compute.** Extraction, estimated 3 times the Mac's time at 2 GB (Lambda's arm64 core at 2 GB is slower than this Mac's; an assumption until Task 10 measures): 5 runs × about 300 s × 2 GB = 3,000 GB-s a day; the basket run about 60 s × 2 GB = 120; about 95,000 GB-s a month. Worst case, every run its full 900 s: 10,800 a day, 324,000 a month. With the collector's up to 230,000 (design, "Cost"), likely inside the free tier's 400,000 GB-s; worst case about 150,000 over, $2.50 at $0.0000166667 per GB-s. Sources: https://aws.amazon.com/lambda/pricing/ read 2026-11-03 (the x86 US East rate and the free tier; the arm64 rate and il-central-1's rates were not readable on the page: UNVERIFIED, arm64 is priced below x86 there by AWS's own description).
- **Ephemeral storage.** 2,048 MB, of which 512 MB are free: 1.5 GB × about 1,600 s a day = 2,400 GB-s a day, 72,000 a month, at $0.0000000309 per GB-s: $0.002 (same page).
- **S3.** Tables about 95 MB a day (measured 2026-11-02): 2.9 GB a month more, $0.07 the first month and $0.07 more each month at $0.025 per GB-month (il-central-1, flights-archive `docs/publishing.md`); about $0.85 a month after a year. About 900 reads and 15 writes a day: under $0.15.
- **CloudFront.** One invalidation path a day; the first 1,000 a month are free (flights-archive `docs/publishing.md`).
- **healthchecks.io.** A second check on the owner's account; whether the free plan allows it: UNVERIFIED (the owner sees it in the dashboard).
- **Total:** about $0.10 to $0.90 a month in year one; worst case about $3.50.

---

### Task 1: The basket file moves into the package

**Files:**
- Move: `basket/v1.json` → `src/basket/baskets/v1.json` (`git mv`; bytes unchanged)
- Modify: `src/basket/basket_file.py` (add `DEFAULT_BASKET`), `src/basket/build.py:212` (the `--basket` default), `tests/test_basket_file.py:171-174`, `CLAUDE.md:25` and its "Working notes" coverage remark, `docs/operations.md:209`, `docs/headline-basket.md:61`
- Test: `tests/test_basket_file.py`

**Interfaces:**
- Produces: `basket.basket_file.DEFAULT_BASKET: Path` = `Path(__file__).parent / "baskets" / "v1.json"`; `python -m basket.build` without `--basket` loads it.

- [ ] **Step 1: Write the failing test.** Replace `test_v1_basket_loads` in `tests/test_basket_file.py`:

```python
def test_v1_basket_is_the_default_and_loads():
    assert DEFAULT_BASKET == Path(basket_file.__file__).parent / "baskets" / "v1.json"
    basket = load_basket(DEFAULT_BASKET)  # the default limits, 25 to 40
    assert basket.version == "v1"
    assert len(basket.items) == 32
```

- [ ] **Step 2: Run it to see it fail.** `.venv/bin/pytest tests/test_basket_file.py -q` → `ImportError` on `DEFAULT_BASKET`.
- [ ] **Step 3: Move the file and add the constant.** `git mv basket/v1.json src/basket/baskets/v1.json`; `DEFAULT_BASKET` in `basket_file.py`; `build.py`'s `--basket` default becomes `DEFAULT_BASKET` (help text: "default: the package's v1"); the module docstring's example run stays without `--basket`.
- [ ] **Step 4: Update the four docs lines** to `src/basket/baskets/v1.json`; in `CLAUDE.md`'s working notes, drop "(CI measures `--cov=src/basket`: the root `basket/` folder shadows the package name)" and keep the CI flag as it is (CI is not changed).
- [ ] **Step 5: Run the suite and the mutation check.** `.venv/bin/pytest -q` → all pass; `.venv/bin/python scripts/mutation_check.py` → exit 0.
- [ ] **Step 6: Commit.** `git add -A basket src/basket tests/test_basket_file.py CLAUDE.md docs && git commit -m "basket: v1.json moves into the package so the Lambda ships it; DEFAULT_BASKET"`

### Task 2: DuckDB's temp folder and memory ceiling from the environment

**Files:**
- Create: `src/basket/duck.py`
- Modify: `src/basket/extract.py:write_table` (`duckdb.connect()` → `duck.connect()`), `src/basket/rules.py:open_day` (same)
- Test: `tests/test_duck.py`
- Mutation: `DUCK = ("src/basket/duck.py", ["tests/test_duck.py"])` in `scripts/mutation_check.py`

**Interfaces:**
- Produces: `basket.duck.connect(env: Mapping[str, str] | None = None) -> duckdb.DuckDBPyConnection`: an in-memory connection; when `env` (default `os.environ`) holds a non-blank `DUCKDB_TEMP_DIRECTORY` it runs `SET temp_directory = ?`, and for `DUCKDB_MEMORY_LIMIT` `SET memory_limit = ?`; both as prepared parameters. Constants `TEMP_DIRECTORY_VAR`, `MEMORY_LIMIT_VAR`.

Why: in Lambda `/var/task` is read-only and DuckDB's default `temp_directory` is `.tmp` under the working directory, and its default `memory_limit` is 80% of what it reads as the machine's RAM (measured here: `6.3 GiB` on this Mac, `.tmp`), which is not the function's 2 GB; the CSV-to-Parquet copy of Shufersal's 2.3 million rows is the extraction's peak (937 MB resident on the Mac). The Lambda sets `/tmp/duckdb` and `1200MB`; the Mac leaves both unset.

- [ ] **Step 1: Write the failing tests** in `tests/test_duck.py`:

```python
def test_unset_leaves_duckdbs_defaults():
    con = connect({})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == ".tmp"

def test_temp_directory_and_memory_limit_are_set_from_the_environment(tmp_path):
    con = connect({TEMP_DIRECTORY_VAR: str(tmp_path / "duck"), MEMORY_LIMIT_VAR: "100MB"})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == str(tmp_path / "duck")
    assert con.execute("SELECT current_setting('memory_limit')").fetchone()[0] == "95.3 MiB"

def test_blank_values_count_as_unset():
    con = connect({TEMP_DIRECTORY_VAR: " ", MEMORY_LIMIT_VAR: ""})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == ".tmp"

def test_extract_and_rules_connect_through_duck(monkeypatch, tmp_path):
    """Both call sites take their connection from duck.connect, so the Lambda's settings reach both."""
    calls = []
    monkeypatch.setattr(duck, "connect", lambda env=None: calls.append("connect") or duckdb.connect())
    row = Row("1", None, "7290000000001", "7290000000001", True, "x", Decimal("1.00"), "1", "יחידות", "", "", "f.gz")
    write_table([row], table_path(tmp_path, "osherad", date(2026, 1, 1)))
    with open_day(tmp_path, date(2026, 1, 1), ["osherad"]) as con:
        assert con.execute("SELECT count(*) FROM prices").fetchone()[0] == 1
    assert calls == ["connect", "connect"]
```

- [ ] **Step 2: Run them to see them fail.** `.venv/bin/pytest tests/test_duck.py -q` → `ModuleNotFoundError: basket.duck`.
- [ ] **Step 3: Implement `duck.py`** and route the two call sites through it (`from basket import duck` and `duck.connect()`, so the monkeypatch above takes).
- [ ] **Step 4: Add the mutation** `DUCK` with one entry: the `SET memory_limit` line removed (caught by the second test) and one: the blank check removed (caught by the third).
- [ ] **Step 5: Run the suite and the mutation check.** Both green.
- [ ] **Step 6: Commit.** `git commit -am "basket: DuckDB's temp folder and memory ceiling from the environment (duck.connect); extract and rules use it"` (add the new files first).

### Task 3: The archive side of the scheduled build

**Files:**
- Create: `src/basket/archive.py`
- Test: `tests/test_archive.py` (uses `MemoryArchive`; one test each on `S3Archive` over `tests/test_store.py`'s `FakeS3` for the listing and the plain put)
- Mutation: `ARCHIVE = ("src/basket/archive.py", ["tests/test_archive.py"])`

**Interfaces:**
- Consumes: `collector.store._Store`'s bare operations (`_keys(prefix)`, `_get(key)`, `_put_plain(key, body, content_type)`, `put_record(key, body, now)` locked), `S3Store`, `MemoryStore`, `raw_key(slug, day, name)`, `manifest_key(day, slug, run_id)`; `collector.names.parse_file_name`, `collector.store.published_name`; `basket.extract.table_path(tables_dir, slug, day)`; `basket.stores._is_store_list(name, day)` (make it public as `is_store_list` with the same body; `stores.py` keeps a one-line alias).
- Produces, in `basket/archive.py`:

```python
STORE_LIST_LOOKBACK_DAYS = 14
TABLE_FILES = ("prices.parquet", "report.json")

def table_key(slug: str, day: date, name: str) -> str      # "tables/prices/chain=<slug>/date=<day>/<name>"
def record_key(day: date, run_id: str) -> str              # "basket/date=<day>/basket-<run id>.json"

class _Archive:
    """The archive bucket for the scheduled build, over a _Store's bare operations."""
    def day_checked(self, day: date) -> bool
    def day_price_file_keys(self, slug: str, day: date) -> list[str]
    def fetch_raw(self, slug: str, day: date, raw_dir: Path) -> list[str]
    def fetch_store_list(self, slug: str, day: date, raw_dir: Path) -> date | None
    def fetch_manifests(self, slug: str, day: date, manifests_dir: Path) -> int
    def fetch_table(self, slug: str, day: date, tables_dir: Path) -> bool
    def put_table(self, slug: str, day: date, tables_dir: Path) -> list[str]
    def put_basket_record(self, path: Path, now: datetime) -> str

class S3Archive(_Archive, S3Store): ...
class MemoryArchive(_Archive, MemoryStore): ...
```

Behaviour the tests pin: `day_checked` is whether any key sits under `check_key(day, "")`'s folder (`checks/date=<day>/`; `collector.store.check_key`). `day_price_file_keys` lists `raw/chain=<slug>/date=<day>/` and keeps the keys whose stored name, read as `parse_file_name(published_name(name))`, is a `PriceFull` of that day (a conflict copy counts by its published name and is fetched under its stored name; `PromoFull` and `Stores` keys are not), sorted. `fetch_raw` writes each under `raw_dir/chain=<slug>/date=<day>/<stored name>` and returns the stored names. `fetch_store_list` tries `day`, then each earlier day down to `day - 13`, listing `raw_key(slug, d, "Stores")` and keeping the names `is_store_list(name, d)` accepts; the first day with one gets its greatest name written under `raw_dir/chain=<slug>/date=<d>/` (where `basket.stores.day_store_list` finds it), returning `d`; `None` after 14 days. `fetch_manifests` writes every object under `manifests/date=<day>/<slug>-` into `manifests_dir/date=<day>/` and returns the count. `fetch_table` writes both `TABLE_FILES` from `table_key` beside `table_path(tables_dir, slug, day)`, returning `False` (and writing nothing) when either is missing. `put_table` puts both from that folder, plain (`application/vnd.apache.parquet`, `application/json`), returning the keys. `put_basket_record` reads the file's `run_id` and `day` from its JSON and calls `put_record(record_key(day, run_id), body, now)`, returning the key: write-once and locked, like a manifest.

- [ ] **Step 1: Write the failing tests** in `tests/test_archive.py`, one per behaviour above, named for it: `test_keys`, `test_day_checked_is_whether_the_day_has_a_check_record` (none → `False`; one under `checks/date=<day>/` → `True`; one under the day before only → `False`), `test_day_price_file_keys_are_the_days_pricefull_files_only` (a PriceFull of the day, a PromoFull, a Stores, a PriceFull of the day before, a conflict copy `…gz.0123456789ab`), `test_fetch_raw_writes_under_the_days_folder_and_returns_stored_names`, `test_fetch_store_list_takes_the_day_then_looks_back` (none on the day, one three days back → written under `date=<day-3>`, returns that day; then `day_store_list(raw_dir, slug, day)` finds it), `test_fetch_store_list_stops_after_fourteen_days` (one 14 days back → `None`; one 13 days back → found), `test_fetch_manifests_takes_the_chains_only`, `test_fetch_table_needs_both_files` (parquet alone → `False`, nothing written), `test_put_table_puts_both_files_plain` (through `FakeS3`: no `ObjectLockMode` in the sent kwargs, the content types), `test_put_basket_record_is_write_once_and_locked` (`lock_of` → `("GOVERNANCE", now + 3650 days)`; the same bytes again → no error; other bytes under the same key → `AlreadyStored`), `test_s3_archive_lists_through_the_paginator` (a `FakeS3(page_size=2)` with three PriceFull keys), `test_no_method_ever_deletes` (the pattern of `tests/test_store.py`, over `_Archive`'s source).
- [ ] **Step 2: Run them to see them fail.** `ModuleNotFoundError: basket.archive`.
- [ ] **Step 3: Implement `archive.py`** as specified; `is_store_list` made public in `stores.py`.
- [ ] **Step 4: Add the mutations** under `ARCHIVE`: the PriceFull filter dropped (`parsed.kind != "PriceFull"` → `parsed.kind != "Stores"`); the look-back's `14` → `1`; `fetch_table` writing the parquet when the report is missing; `put_basket_record` calling `_put_plain` instead of `put_record`.
- [ ] **Step 5: Run the suite and the mutation check.** Both green.
- [ ] **Step 6: Commit.** `git commit -m "basket: archive.py, the archive bucket side of the scheduled build (fetch raw, store list, manifests, tables; put tables plain and the record locked)"`

### Task 4: The site side

**Files:**
- Create: `src/basket/site.py`
- Test: `tests/test_site.py`
- Mutation: `SITE = ("src/basket/site.py", ["tests/test_site.py"])`

**Interfaces:**
- Produces, in `basket/site.py`:

```python
PAGES = ("index.html", "method.html")
HTML = "text/html; charset=utf-8"
JSON = "application/json; charset=utf-8"
CACHE_CONTROL = "max-age=300"

def day_key(day: date) -> str                               # "days/<day>.json"

class _Site:
    """The site bucket and its distribution, over three bare operations:
    _put(key, body, content_type, cache_control) -> None; _get(key) -> bytes | None; _invalidate(reference) -> str."""
    def published_day(self, day: date) -> bytes | None
    def latest_published_day(self) -> date | None
    def upload(self, site_dir: Path, day: date, with_pages: bool, with_day: bool) -> list[str]
    def invalidate(self, reference: str) -> str

class S3Site(_Site):
    def __init__(self, s3, cloudfront, bucket: str, distribution_id: str)   # a fourth bare operation: _keys(prefix) -> list[str]

class MemorySite(_Site):
    objects: dict[str, tuple[bytes, str, str]]   # key → (body, content type, cache-control)
    invalidations: list[str]
```

`latest_published_day` is the greatest `YYYY-MM-DD` among the keys under `days/` that read as `days/<date>.json` (others ignored), or `None`. `upload` puts `index.html` and `method.html` from `site_dir` as `HTML` when `with_pages`, then `days/<day>.json` as `JSON` when `with_day`, each with `CACHE_CONTROL`, and returns the keys in that order; it refuses (`FileNotFoundError`) when a page it is to put is missing. `S3Site._invalidate` calls `cloudfront.create_invalidation(DistributionId=…, InvalidationBatch={"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": reference})` and returns `Invalidation.Id`. `S3Site._get` reads a missing key as `None` (the codes `collector.store.MISSING` names).

- [ ] **Step 1: Write the failing tests**: `test_published_day_is_none_before_the_first_upload`, `test_latest_published_day_is_the_greatest_day_file` (none → `None`; `days/2026-11-02.json`, `days/2026-11-03.json` and a stray `days/notes.txt` → 2026-11-03), `test_upload_puts_the_pages_then_the_day_file_with_content_types_and_cache_control`, `test_upload_without_the_day_file_leaves_days_alone`, `test_upload_without_the_pages_puts_the_day_file_only`, `test_upload_refuses_a_missing_page`, `test_invalidate_sends_one_path_and_the_reference` (through a fake CloudFront client recording the kwargs and answering `{"Invalidation": {"Id": "I1"}}`), `test_s3_site_reads_a_missing_day_as_none` (a `FakeS3` with nothing), `test_no_method_ever_deletes`.
- [ ] **Step 2: Run them to see them fail.** `ModuleNotFoundError: basket.site`.
- [ ] **Step 3: Implement `site.py`.**
- [ ] **Step 4: Add the mutations** under `SITE`: `with_day` ignored (the day file always put); `with_pages` ignored; `CACHE_CONTROL` dropped from the put; `"/*"` → `"/index.html"`; `latest_published_day` returning the smallest day.
- [ ] **Step 5: Run the suite and the mutation check.** Both green.
- [ ] **Step 6: Commit.** `git commit -m "basket: site.py, the site bucket and distribution side (published day, the three uploads, one invalidation)"`

### Task 5: The handler's config, events and the extract mode

**Files:**
- Create: `src/basket/handler.py`
- Test: `tests/test_basket_handler.py` (the golden tree of `tests/test_build.py` is importable: `from test_build import golden_tree, DAY, SLUGS, price_file_name`)
- Mutation: `BASKET_HANDLER = ("src/basket/handler.py", ["tests/test_basket_handler.py"])`

**Interfaces:**
- Consumes: `basket.archive.MemoryArchive`, `basket.extract.extract`, `collector.run.new_run_id`, `collector.http.check_user_agent`, `collector.handler.ping` and `ping_user_agent`.
- Produces, in `tests/test_basket_handler.py`, the helper Task 6 reuses: `archive_from(data: Path) -> MemoryArchive`: every file under `data/raw/chain=<slug>/date=<d>/<name>` stored under `raw_key(slug, d, name)`, every file under `data/manifests/date=<d>/<file>` under `manifests/date=<d>/<file>`, and one check record `{"day": "<DAY>", "alerts": []}` under `check_key(DAY, "090000Z-check-0001")`, through `MemoryArchive.put_raw` and `put_record` at a fixed `now`.
- Produces, in `basket/handler.py`:

```python
REQUIRED = ("BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT")
SITE_BUCKET_PREFIX = "il-grocery-prices-site-sitebucket-"
MODES = ("extract", "basket")
ISRAEL = ZoneInfo("Asia/Jerusalem")
CLOCK = re.compile(r"^[0-2][0-9]:[0-5][0-9]$")

@dataclass(frozen=True)
class Config:
    bucket: str; site_bucket: str; distribution_id: str; healthcheck_url: str; user_agent: str; retention_days: int
    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config"   # ValueError: a missing variable; a site bucket outside SITE_BUCKET_PREFIX; a bad User-Agent (check_user_agent)

@dataclass
class Deps:
    archive: Any            # an _Archive
    site: Any               # a _Site
    ping: Callable[[str, str], None]   # (url, message); failures logged by run(), never raised

def event_day(event: dict, now: datetime) -> date           # event["day"] as ISO, else now in Israel; ValueError on a bad value
def run(cfg: Config, event: dict, deps: Deps, now: datetime, tmp_root: Path) -> dict
def handler(event, context)  # pragma: no cover
```

`run` refuses (`ValueError`) a mode outside `MODES`, an `extract` event whose `chain` is not in `basket.chains.SLUGS`, a `basket` event whose `collected_by` is missing or not `CLOCK`, and a naive `now`; then, in either mode, it refuses with `MorningNotChecked` (a class in `handler.py`; the message names the day and `checks/date=<day>/`: "the collector's check has not written its record for <day>: the morning is not over, or the check failed") when `deps.archive.day_checked(day)` is `False` (call 11); it makes a work folder `tempfile.mkdtemp(prefix="basket-", dir=tmp_root)` and removes it (`shutil.rmtree`) in a `finally`. The extract mode: `run_id = new_run_id(now, "extract")`; `names = deps.archive.fetch_raw(slug, day, work / "raw")`; `report = extract(work / "raw", slug, day, work / "tables")`, timed with `time.perf_counter()` for the summary only; `keys = deps.archive.put_table(slug, day, work / "tables")`; the summary `{"mode": "extract", "chain", "day", "run_id", "files": len(report.files), "skipped": len(report.skipped), "stores", "rows", "seconds", "keys"}`, logged as one JSON line (`log.info`) and returned. `handler` builds `Config.from_env(os.environ)`, `S3Archive(boto3.client("s3"), cfg.bucket, cfg.retention_days)`, `S3Site(boto3.client("s3"), boto3.client("cloudfront"), cfg.site_bucket, cfg.distribution_id)`, `partial(ping, user_agent=ping_user_agent(cfg.user_agent))`, and calls `run(..., datetime.now(timezone.utc), Path(tempfile.gettempdir()))`.

- [ ] **Step 1: Write the failing tests**: `test_config_from_env_reads_the_five_and_the_retention`, `test_config_refuses_a_site_bucket_outside_the_prefix` (the archive bucket's name → `ValueError` naming `SITE_BUCKET_PREFIX`), `test_config_refuses_a_missing_variable`, `test_event_day_is_the_events_or_the_israel_date` (`now` = 2026-11-02 22:30Z → 2026-11-03), `test_event_day_refuses_a_bad_date`, `test_run_refuses_unknown_mode_chain_and_naive_now`, `test_run_refuses_a_day_without_a_check_record` (the golden archive without its check record → `MorningNotChecked` naming the day; nothing written; with a record under `check_key(DAY, "090000Z-check-0001")` the run goes on), `test_extract_fetches_the_days_files_extracts_and_puts_the_table` (a `MemoryArchive` filled from `golden_tree` by walking `data/raw` into `raw_key`s; the summary's `rows` and `files` equal `report.json`'s; both `TABLE_FILES` keys present and plain), `test_extract_of_a_day_with_no_files_puts_an_empty_table` (`stores == 0`, the parquet has the twelve columns and no rows), `test_extract_leaves_tmp_root_empty` (after the run, `list(tmp_root.iterdir()) == []`).
- [ ] **Step 2: Run them to see them fail.** `ModuleNotFoundError: basket.handler`.
- [ ] **Step 3: Implement `handler.py`** through the extract mode; the basket mode raises `NotImplementedError` for now.
- [ ] **Step 4: Add the mutations** under `BASKET_HANDLER`: the prefix check removed; the `day_checked` refusal removed; `shutil.rmtree` removed; the extract mode putting the table before extracting (`put_table` moved above `extract`; caught by the row test).
- [ ] **Step 5: Run the suite and the mutation check.** Both green.
- [ ] **Step 6: Commit.** `git commit -m "basket: handler.py, the Lambda's config, events and the extract mode"`

### Task 6: The basket mode

**Files:**
- Modify: `src/basket/handler.py`
- Test: `tests/test_basket_handler.py`

**Interfaces:**
- Consumes: Tasks 3 to 5; `basket.build.build_day`, `RevisionNeeded`, `NoStoreList`; `basket.rules.MissingTable`; `basket.check.check_site`; `basket.guard.guard_days`; `basket.basket_file.DEFAULT_BASKET`.
- Produces: `run` for `{"mode": "basket", "collected_by": "HH:MM", "day"?: ...}`; `class SiteCheckFailed(Exception)` (the problems, one a line).

The basket mode, in order, over `work`: (1) `deps.ping(f"{cfg.healthcheck_url}/start", "")`. (2) For each slug in `SLUGS`: `fetch_table` → `False` raises `MissingTable(f"no table for chain {slug!r} on {day}: its extraction run did not run or did not finish ({table_key(...)})")`; `fetch_store_list` (a `None` is left for `build_day` to refuse as `NoStoreList`); `fetch_manifests`. (3) `deps.site.published_day(day)` → when bytes, written to both `work/site/days/<day>.json` (what `build_day` compares with) and `work/published/days/<day>.json` (what the guard compares with); else `work/published/days/` made empty; `latest = deps.site.latest_published_day()` and `with_pages = latest is None or day >= latest` (call 12). (4) `outcome = build_day(day, work, work / "site", DEFAULT_BASKET, now, revise=None, rebuild=False, collected_by=event["collected_by"])`. (5) `problems = check_site(work / "site")`; any → `SiteCheckFailed`. (6) `guard_days(work / "site" / "days", work / "published" / "days")`; any → `SiteCheckFailed`. (7) `uploaded = deps.site.upload(work / "site", day, with_pages=with_pages, with_day=not outcome.unchanged)`. (8) `invalidation = deps.site.invalidate(outcome.record.run_id) if uploaded else None`. (9) The summary `{"mode": "basket", "day", "run_id", "headline": list(outcome.headline_lines), "unchanged", "pages": with_pages, "uploaded", "invalidation", "record": <key>}`. In a `finally` around steps 2 to 8, every `work/basket/date=<day>/basket-*.json` goes up through `put_basket_record` (there is one or none). Then, on success, `deps.ping(cfg.healthcheck_url, json.dumps(summary))`; on any exception, `deps.ping(f"{cfg.healthcheck_url}/fail", f"{type(err).__name__}: {err}"[:100_000])` and the exception is re-raised. A ping that raises is logged at WARNING with the URL's last path segment, never raised. The work folder is removed last.

- [ ] **Step 1: Write the failing tests** over a `MemoryArchive` filled from `golden_tree` plus the five tables (made by running the extract mode once per chain in a fixture), a `MemorySite`, and a recording ping (`tests/test_handler.py`'s `Recorder` pattern):
  - `test_first_run_publishes_the_day_and_pings` (uploads `["index.html", "method.html", "days/2026-01-01.json"]`; one invalidation whose reference is the run id; the record locked under `record_key`; pings `[/start, <url>]` with the summary JSON as the second body; the day file's `collected_by` is the event's; its `code_sha` equals `code_fingerprint()`).
  - `test_unchanged_day_uploads_pages_not_the_day_file` (run twice: the second's `unchanged` is `True`, uploads the two pages, a second record, the published day's bytes untouched).
  - `test_an_earlier_day_than_the_sites_latest_uploads_its_day_file_not_the_pages` (the site holds `days/2026-01-02.json` already; the run for `DAY` = 2026-01-01 uploads `["days/2026-01-01.json"]` only, `pages` is `False`, one invalidation; the index object's bytes untouched).
  - `test_an_earlier_day_already_published_and_unchanged_uploads_nothing_and_does_not_invalidate` (the site holds the run's day and a later one; `uploaded == []`, `invalidation is None`; the record uploaded; the success ping sent).
  - `test_differing_numbers_fail_loudly_and_publish_nothing` (publish once; `reprice` one store; run again → `RevisionNeeded` raised; the site's objects unchanged; no new invalidation; the second record uploaded all the same; pings `[/start, /fail]` with the body starting `RevisionNeeded:` and naming `chains.<slug>.total`).
  - `test_missing_table_names_the_chain_uploads_nothing_and_pings_fail` (one chain's table keys removed → `MissingTable` naming the slug and the key; nothing uploaded; no record).
  - `test_a_chain_with_no_files_publishes_with_the_chain_out_of_the_ranking` (one chain's raw files removed before its extraction; its table empty; the run publishes; the day file's chain has `with_file == 0`, `in_ranking == False`).
  - `test_site_check_failure_uploads_nothing` (monkeypatch `handler.check_site` to return `["index.html: x"]` → `SiteCheckFailed`; nothing uploaded; the record uploaded; `/fail` pinged).
  - `test_guard_failure_uploads_nothing` (monkeypatch `handler.guard_days` likewise).
  - `test_collected_by_is_required_and_a_clock` (missing → `ValueError`; `"11:00:00"` → `ValueError`; checked before any fetch: the archive's reads recorded as none).
  - `test_a_failing_ping_is_logged_not_raised` (a ping raising `OSError` on every call; the run publishes; `caplog` holds a WARNING naming `start` and one naming the success ping).
  - `test_work_folder_is_removed_after_success_and_after_failure`.
  - `test_the_scheduled_run_never_revises` (the source of `handler.py` holds no `revise=` other than `revise=None`, and no `--revise`; the pattern of `test_no_method_ever_deletes`).
- [ ] **Step 2: Run them to see them fail.** `NotImplementedError`.
- [ ] **Step 3: Implement the basket mode** as specified.
- [ ] **Step 4: Add the mutations** under `BASKET_HANDLER`: `revise=None` → `revise="scheduled"` (caught by the differing-numbers test and the never-revises test); the `finally` record upload moved inside the success path (caught by the differing-numbers test); `with_day=not outcome.unchanged` → `with_day=True`; `day >= latest` → `day <= latest`; the `/fail` ping removed; the `MissingTable` raise replaced by `continue`; the `/start` ping removed.
- [ ] **Step 5: Run the suite with coverage, and the mutation check.** `.venv/bin/pytest --cov=collector --cov=src/basket --cov-fail-under=95 -q` → green; `.venv/bin/python scripts/mutation_check.py` → exit 0.
- [ ] **Step 6: Commit.** `git commit -am "basket: the handler's basket mode: tables, lists, manifests and the published day in; build, check, guard, upload, invalidate; the record locked whatever happened; start, success and fail pings"`

### Task 7: The DuckDB layer

**Files:**
- Create: `layer/Makefile`, `layer/requirements.txt` (the layer builds into `.aws-sam/`, already gitignored)
- Test: `tests/test_basket_template.py` (started here with the layer's two files; Task 8 adds the template's pins)

**Interfaces:**
- Produces: `sam build` builds `DuckDbLayer` (Task 8's resource, `ContentUri: layer/`, `Metadata: {BuildMethod: makefile}`) by running the Makefile's target `build-DuckDbLayer`, which installs the pinned wheel into `$(ARTIFACTS_DIR)/python`.

`layer/requirements.txt`:

```
duckdb==1.5.6 --hash=sha256:364992ba1089a2b327391cfcb68fd0bd0ce9090cf293baef861a0ba6847abfee
```

`layer/Makefile` (one target, tab-indented):

```make
build-DuckDbLayer:
	python3 -m pip install --require-hashes --only-binary=:all: --no-deps --platform manylinux_2_28_aarch64 --implementation cp --python-version 3.13 --target "$(ARTIFACTS_DIR)/python" -r requirements.txt
```

`python3` here is any Python 3 with pip (this Mac's is 3.14, pip 26.1): with `--only-binary`, `--platform` and `--python-version`, pip downloads for the target, not for itself (proven here 2026-11-03, see call 1). The target's name and `$(ARTIFACTS_DIR)` are SAM's rules for a makefile-built layer (same source); SAM runs the Makefile at the root of `ContentUri`.

- [ ] **Step 1: Write the failing tests** in `tests/test_basket_template.py`: `test_layer_pins_duckdb_by_version_and_hash` (the requirements line is exactly the one above, and its version equals the `duckdb==` line of `requirements-dev.txt`), `test_layer_makefile_builds_for_lambdas_arm64_linux` (the target is `build-DuckDbLayer`; the command holds `--platform manylinux_2_28_aarch64`, `--python-version 3.13`, `--only-binary=:all:`, `--require-hashes`, `--implementation cp`, `"$(ARTIFACTS_DIR)/python"`).
- [ ] **Step 2: Run them to see them fail.** `FileNotFoundError: layer/requirements.txt`.
- [ ] **Step 3: Write the two files.**
- [ ] **Step 4: Prove the build on the Mac** (network, no AWS): `rm -rf /tmp/layer-check && ARTIFACTS_DIR=/tmp/layer-check make -C layer build-DuckDbLayer && ls -la /tmp/layer-check/python/_duckdb*.so && du -sh /tmp/layer-check/python` → the `.so` is `_duckdb.cpython-313-aarch64-linux-gnu.so`, about 55 MB in all (the 250 MB unzipped limit is far). Record the figure in `## Deviations`. The `.so` cannot be imported on the Mac; Task 10's first run proves it in Lambda.
- [ ] **Step 5: Run the suite and the mutation check.** Both green.
- [ ] **Step 6: Commit.** `git add layer tests/test_basket_template.py && git commit -m "basket: the DuckDB layer, built by sam build from a hash-pinned wheel for Lambda's arm64 Linux"`

### Task 8: The template

**Files:**
- Modify: `template.yaml` (four parameters, three resources, one output), `tests/test_template.py` (the resources count, the parameters count, the doc tests of Task 9), `scripts/mutation_check.py`
- Test: `tests/test_basket_template.py`
- Mutation: `BASKET_TEMPLATE = ("template.yaml", ["tests/test_basket_template.py"])`, plus named entries as in Task 8 Step 4

**Interfaces:**
- Consumes: `basket.handler.MODES`, `REQUIRED`, `SITE_BUCKET_PREFIX`; `basket.chains.SLUGS`; `basket.archive.table_key`, `record_key`; `basket.site.day_key`, `PAGES`; `basket.duck.TEMP_DIRECTORY_VAR`, `MEMORY_LIMIT_VAR`.
- Produces: the stack `il-grocery-prices` with:

Parameters: `SiteBucketName` (String, `AllowedPattern: 'il-grocery-prices-site-sitebucket-.+'`), `SiteDistributionId` (String, `AllowedPattern: 'E[A-Z0-9]+'`), `BasketHealthcheckUrl` (String, `NoEcho: true`, the `HealthcheckUrl` pattern), `BasketScheduleState` (String, `Default: DISABLED`, `AllowedValues: [ENABLED, DISABLED]`); none of the other four changes.

Resources: `DuckDbLayer` (`AWS::Serverless::LayerVersion`: `ContentUri: layer/`, `CompatibleRuntimes: [python3.13]`, `CompatibleArchitectures: [arm64]`, `RetentionPolicy: Delete`, `Metadata: {BuildMethod: makefile}`); `BasketLogs` (`AWS::Logs::LogGroup`, `LogGroupName: !Sub "/${AWS::StackName}/basket"`, 30 days); `BasketFunction` (`AWS::Serverless::Function`: `CodeUri: src/`, `Handler: basket.handler.handler`, `Runtime: python3.13`, `Architectures: [arm64]`, `MemorySize: 2048`, `Timeout: 900`, `EphemeralStorage: {Size: 2048}`, `Layers: [!Ref DuckDbLayer]`, `EventInvokeConfig: {MaximumRetryAttempts: 0}`, `LoggingConfig: {LogGroup: !Ref BasketLogs}`; `Environment.Variables`: `BUCKET: !Ref ArchiveBucket`, `SITE_BUCKET: !Ref SiteBucketName`, `DISTRIBUTION_ID: !Ref SiteDistributionId`, `HEALTHCHECK_URL: !Ref BasketHealthcheckUrl`, `USER_AGENT: !Ref UserAgent`, `RETENTION_DAYS: "3650"`, `DUCKDB_TEMP_DIRECTORY: /tmp/duckdb`, `DUCKDB_MEMORY_LIMIT: 1200MB`; `Policies`: one inline statement list with Sids `ReadArchive` (`s3:GetObject` on `raw/*`, `manifests/*`, `checks/*`, `tables/*`, `basket/*` of the archive: the check record is the gate of call 11, and a refused locked write of a record is compared through `head_object`, call 13), `WriteTables` (`s3:PutObject` on `tables/*`), `WriteOnceLockedRecords` (`s3:PutObject`, `s3:PutObjectRetention` on `basket/*`), `ListArchive` (`s3:ListBucket` on the archive's ARN), `ReadPublishedDays` (`s3:GetObject` on `!Sub "arn:aws:s3:::${SiteBucketName}/days/*"`), `WriteSite` (`s3:PutObject` on `…/index.html`, `…/method.html`, `…/days/*`), `ListSite` (`s3:ListBucket` on `!Sub "arn:aws:s3:::${SiteBucketName}"`), `Invalidate` (`cloudfront:CreateInvalidation` on `!Sub "arn:aws:cloudfront::${AWS::AccountId}:distribution/${SiteDistributionId}"`); `Events`: `ExtractShufersal`, `ExtractRamiLevy`, `ExtractOsherAd`, `ExtractCarrefour`, `ExtractYochananof` at `cron(0 11 * * ? *)` with `{"mode": "extract", "chain": "<slug>"}`, and `Basket` at `cron(30 11 * * ? *)` with `{"mode": "basket", "collected_by": "11:00"}`; every event `ScheduleV2`, `Asia/Jerusalem`, `State: !Ref BasketScheduleState`, `FlexibleTimeWindow: {Mode: "OFF"}`, `RetryPolicy: {MaximumRetryAttempts: 0}`). A comment block above the events, in the collector's manner: the extractions read S3 only and touch no portal, so they share a minute; the basket run starts 15 minutes after the last extraction can have finished; the switch is the basket's own so the collector keeps running while step two is tested.

Output: `BasketFunctionName: {Value: !Ref BasketFunction}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_basket_template.py`, with fixtures `basket_function`, `basket_statements`, `basket_schedules` (the shapes of `tests/test_template.py`'s `function`, `statements`, `schedules`, over `BasketFunction`): `test_function_runs_the_basket_handler_on_python_313_arm64_with_the_layer`, `test_function_has_two_gb_two_gb_of_tmp_and_lambdas_longest_run`, `test_lambda_never_retries_a_failed_run`, `test_environment_is_what_the_handler_and_duckdb_read` (the keys are `set(REQUIRED) | {"RETENTION_DAYS", TEMP_DIRECTORY_VAR, MEMORY_LIMIT_VAR}`; the Refs as above; `/tmp/duckdb`, `1200MB`), `test_logs_go_to_a_group_created_first`, `test_role_is_one_inline_policy`, `test_role_cannot_delete_bypass_the_lock_or_change_either_bucket` (no `s3:Delete*`, no bypass, no `s3:PutBucket*`, no `*` in an action, Allow only), `test_role_grants_exactly_what_the_code_does` (the eight Sids with their sorted actions and resources, as `test_template.py` does), `test_role_prefixes_are_the_codes_keys` (`raw_key`, `manifest_key`, `check_key`, `table_key`, `record_key`, `day_key` prefixes, `PAGES`), `test_parameters_are_the_eight_and_only_the_two_switches_have_defaults`, `test_site_parameters_are_pattern_checked` (the bucket pattern starts with `SITE_BUCKET_PREFIX`; the distribution pattern; the health-check URL `NoEcho` with the collector's pattern), `test_schedules_follow_the_baskets_own_switch_in_israel_time`, `test_five_extractions_share_one_minute_one_per_chain` (the chains are exactly `SLUGS`), `test_every_event_is_one_the_handler_takes` (each event through `run`'s validation: `mode in MODES`, the chain in `SLUGS`, `collected_by` matching `CLOCK`; drive `run` with a `Deps` whose archive raises a marker on the first fetch, so a valid event stops there and an invalid one raises `ValueError` first), `test_collected_by_is_the_extractions_start` (equals `f"{hour:02d}:{minute:02d}"` of the extraction cron), `test_basket_runs_after_the_last_extraction_can_have_finished` (basket minute ≥ extraction minute + Timeout/60 + 15), `test_extraction_starts_after_the_collectors_check_can_have_finished` (extraction minute ≥ the collector's `Check` minute + the collector's Timeout/60, read from `CollectorFunction`), `test_layer_is_built_by_the_makefile_for_python_313_arm64` (the resource's properties and `Metadata`), `test_the_stack_outputs_the_basket_function`.
- [ ] **Step 2: Update `tests/test_template.py`**: `test_the_stack_holds_only_its_four_resources` → `..._seven_resources` with the three new types; `test_parameters_are_the_four_...` → `..._eight_...` (the two switches have defaults, nothing else).
- [ ] **Step 3: Run the two files to see them fail.**
- [ ] **Step 4: Write the template** as specified; `cfn-lint --regions il-central-1 -- template.yaml site-template.yaml` → clean.
- [ ] **Step 5: Add the mutations**: `BASKET_TEMPLATE` (a general entry), and named ones in the manner of `R7_TABLE`: `BASKET_OWN_SWITCH` (one basket event's `State: !Ref BasketScheduleState` → `!Ref ScheduleState`), `BASKET_AFTER_EXTRACT` (`cron(30 11` → `cron(10 11`), `EXTRACT_AFTER_CHECK` (`cron(0 11` → `cron(50 10` on one event), `COLLECTED_BY_PINNED` (`"collected_by": "11:00"` → `"10:45"`), `NO_DELETE_BASKET` (`s3:PutObject` in `WriteSite` → `s3:DeleteObject`), `READ_RECORDS_FOR_RETRY` (the `basket/*` resource of `ReadArchive` removed), `TMP_SIZE` (`Size: 2048` → `Size: 512`), `LAYER_ATTACHED` (`Layers:` line removed).
- [ ] **Step 6: Run the suite and the mutation check.** Both green.
- [ ] **Step 7: Commit.** `git commit -am "basket: BasketFunction, its layer, logs, role and six schedules in the collector's stack, off by default; the site bucket and distribution as parameters"`

### Task 9: The operating note and the design's amendments

**Files:**
- Modify: `docs/operations.md` (the deploy command of step 3 gains the four parameters; a new section "The headline basket, every morning" after "The headline basket, by hand"; one paragraph in "by hand" on what the hand build is for once step two runs), `docs/headline-basket.md` ("The basket", "Who picks": the file's path; B11: "the time its extraction is scheduled for" in place of the literal 11:00, and that the extraction runs only once the day's check record exists; "The pipeline", Step two: the role as granted (reads of `tables/` and `basket/` added), the check-record gate, the `/start` and `/fail` pings, the layer, `collected_by` from the event, pages only for the site's latest day, and the times as "after the collector's check" rather than literal hours; "Cost": this plan's figures with their sources), `CLAUDE.md` (Active threads: Showcase; the test baseline after Task 8), `tests/test_template.py` (the doc tests)
- Test: `tests/test_template.py`, `tests/test_basket_template.py`

The new section, in the operating note's voice (plain words, no "we"), covers: what runs when (a table of the six schedules in the "What runs when" format, the basket row's event `{"mode": "basket", "collected_by": "11:00"}`); where things land (`tables/prices/chain=<slug>/date=<day>/prices.parquet` and `report.json`, overwritable; `basket/date=<day>/basket-<run id>.json`, locked; the site bucket's three files; the log group `/il-grocery-prices/basket`); deploying step two (healthchecks.io: a second check, period 1 day, grace 2 hours; `sam build` now downloads the DuckDB wheel from PyPI into the layer; the deploy command with all eight parameters, `BasketScheduleState=DISABLED` first; the function's name from the output `BasketFunctionName`); the manual runs (five `extract` events with `"day"`, one at a time or together, `--invocation-type Event`, watched in the logs for `rows`, `seconds` and Lambda's `REPORT` line's `Max Memory Used`; then the `basket` event with `"day"` and `"collected_by"` set to the extraction's scheduled time, a plain invoke with `--cli-read-timeout 900`; on a day step one published by hand, `unchanged` is the expected outcome, and the record, the pages and the ping are checked as in "The two gates"); turning it on (`BasketScheduleState=ENABLED` on the owner's go; the next morning: the six log lines, the record under `basket/date=<day>/`, the ping on healthchecks.io, the page's date); what a `/fail` email means and what to read (the log group around the basket run's time; `MorningNotChecked` means the collector's check has not run or failed, read `/il-grocery-prices/collector`; `MissingTable` names the chain whose extraction run to read; `RevisionNeeded` means a code or rule change moved a published number: a hand build with `--revise` and a reason, "Revising a day"); that a manual run for an earlier day writes its day file and record but leaves the front page to the site's latest day; and that the hand build remains for revisions and for days the morning missed. The section's times are written once, in the timetable table, and the prose says "the extraction's time" and "the basket run's time", so a later move (QUEUE q12) touches the table and the template only.

- [ ] **Step 1: Extend the doc tests** in `tests/test_template.py`: `test_the_docs_events_are_ones_the_handler_takes` judges a payload with `mode in basket.handler.MODES` by the basket handler's rules (chain in `SLUGS`; `collected_by` matching `CLOCK`) and the rest by the collector's, and requires at least one `extract` and one `basket` payload; `test_the_docs_timetable_is_the_schedules` compares the doc's rows with the union of both functions' daily schedules; add `test_the_doc_runs_each_extraction_by_hand` (the `extract` payloads' chains, with `day` removed, equal the scheduled ones). Run them: they fail on the doc as it stands.
- [ ] **Step 2: Write the docs** as specified. Every figure in the new section is one this plan or Task 7 measured, or is marked for Task 10 to fill ("measured on the first run: …").
- [ ] **Step 3: Run the suite and the mutation check.** Both green (the `OPERATIONS` mutation entry still catches a dropped `--profile`).
- [ ] **Step 4: Commit.** `git commit -am "docs: the headline basket every morning (what runs, deploying step two, the manual runs, the fail email); design amended for step two as built"`

### Task 10: Deploy, measure, turn on (every write on the owner's go)

**Files:**
- Modify: `docs/headline-basket-step-two-plan.md` (`## Deviations`: the measurements), `docs/operations.md` (the measured figures), `.claude/OPEN_ISSUES.md` Showcase "step two" and `.claude/QUEUE.md` q14 (the main session writes the records, not the implementer)

Prerequisites: Tasks 1 to 9 merged to `main` and pushed, CI green; `git status --porcelain src/` empty (the record's fingerprint must match a commit); `gh auth status` shows doronreiffman; `aws sts get-caller-identity --profile flights-sam` shows 137953273942 and doron-admin.

- [ ] **Step 1: The owner creates the healthchecks.io check** (period 1 day, grace 2 hours) and gives its ping URL in chat; the owner reads the site stack's outputs for the two site values (`aws cloudformation describe-stacks --stack-name il-grocery-prices-site --query "Stacks[0].Outputs" --output table --profile flights-sam --region il-central-1`).
- [ ] **Step 2: Build and deploy with the basket's schedules off**, on the owner's go: `sam build` (the layer downloads 18.6 MB from PyPI), then the deploy command of `docs/operations.md` step 3 with all eight parameters, `ScheduleState=ENABLED` (the collector stays live) and `BasketScheduleState=DISABLED`; review the change set: one new function, one layer, one log group, six schedules and their roles, nothing on the collector's function beyond no-ops. Record the deploy time in `## Deviations`.
- [ ] **Step 0: The timetable** (call 11, owner's decision 2026-11-03): q12's schedule change rides in this deploy. Its own change comes first (Osher Ad's main run after its 08:00 files, keeping the NCR host's 15-minute spacing; its retry three hours on; the check 30 minutes after the last retry can have finished; the collector's tests pin all three), then step two's six crons and `collected_by` are set from the new check time (extraction = check + 15 min, basket = extraction + 30 min), and the docs' two timetables with them. Task 8's tests pass on the deployed template. The q12 change is its own commit, Fable-reviewed like any task, and its QUEUE line closes with this deploy.
- [ ] **Step 3: Five manual extractions of the latest day already on the site** (so the manual basket run's pages are the ones already showing; call 12), one event at a time, `--invocation-type Event`, each `{"mode": "extract", "chain": "<slug>", "day": "<day>"}`; read each run's JSON line and `REPORT` line: `rows` equal to the Mac's for that day (Shufersal 2,322,336 on 2026-11-02), `seconds`, `Duration`, `Max Memory Used`. Record the five in `## Deviations` and in `docs/operations.md`. A chain whose `Duration` passes 600 s or whose memory passes 1,800 MB is noted for a split or more memory (the design's "Left to the builder"); nothing is changed in this task without the owner.
- [ ] **Step 4: The manual basket run** of the same day: `{"mode": "basket", "day": "<day>", "collected_by": "<the extraction's scheduled time>"}` with `--cli-read-timeout 900`. Expected: the answer's `unchanged` is `true`, `pages` is `true`, `uploaded` is the two pages, one `invalidation`, a `record` key; `aws s3api head-object` on the record shows `GOVERNANCE` and a date ten years on; the record's `code_sha` equals `PYTHONPATH=src .venv/bin/python -c 'from basket.record import code_fingerprint; print(code_fingerprint())'` on the deployed commit; the published day file's bytes unchanged (`aws s3api head-object` ETag equal to before); https://d153udx05irk2f.cloudfront.net/ answers 200 with `noindex`; healthchecks.io shows the start and the ping with the summary. Record the run's duration.
- [ ] **Step 5: Turn the basket's schedules on**, on the owner's go: the same deploy with `BasketScheduleState=ENABLED`. Next morning after 11:45 Israel time: the six log lines, `basket/date=<day>/` holds one record, `days/<day>.json` is on the site with `collected_by` equal to the extraction's scheduled time, the page shows the day, healthchecks.io shows the ping. The main session then moves q14 to Done with the record's key as proof and replaces the OPEN_ISSUES entry with the live state (function name, schedules, the check's grace, where to read).

## Deviations

(Appended during execution: what reality forced, and why.)

- 2026-11-03, setup: the work ran on branch `q14-step-two` in the same checkout, not a worktree, as step one did: the venv and the synced day live here and one implementer ran at a time.
- 2026-11-03, Task 2: a fifth test pins the bare `connect()` reading `os.environ` (the Lambda's only path), with its mutation; two mutations pin the two call sites; `import duckdb` left `extract.py` once nothing else used it.
- 2026-11-03, Task 3: the fetches read through `read_raw` (a key listed then gone raises `KeyError`), not the bare `_get`; 21 mutations instead of the four named; the store-list lookup lists the prefix `Stores` (case-sensitive) where the Mac's parse is not (latent: every chain's list starts with a capital S, and `scripts/sync.sh` syncs `Stores*` only).
- 2026-11-03, Task 4: `_Site` has four bare operations (`_keys` for `latest_published_day`), not three; a `days/` key shaped like a date that is no real day (`days/2026-11-31.json`) is skipped, not raised.
- 2026-11-03, Task 5: one S3 client serves the archive and the site; `collected_by` is checked with `fullmatch`; `run` refuses a naive `now` in every path, `event_day` only when it has to read it.
- 2026-11-03, Task 6, two rulings: the basket run pings `/start` before the check-record test, so `MorningNotChecked` pings `/fail` like every other failure (call 11; the brief had the gate first), while a bad event pings nothing and the extract run never pings; the basket file and the item floor are module constants (`BASKET_FILE`, `MIN_ITEMS`) the tests monkeypatch to the golden basket. On the failure path the work folder is removed before the `/fail` ping (one `/fail` site covers `MorningNotChecked`, raised before the folder exists); nothing depends on the order. A failed ping is logged by kind (`start`, `success`, `fail`) and the URL, its host and the check's id are masked out of the error's text; the controller's first resolution had named the id, which would have put the secret in CloudWatch, and was corrected before the review.
- 2026-11-03, Task 7, the layer proven on the Mac: `python/` 53 MB, `_duckdb.cpython-313-aarch64-linux-gnu.so` 54,606,888 bytes, from Python 3.14's pip with the hash pin.
- 2026-11-03, Task 7b (inserted: QUEUE q12 rides in this deploy, owner 2026-11-03): Osher Ad's main run 06:48 → 08:18 (its files on 2026-11-02 were stamped 07:00 to 09:00, most 08:00, the store list 08:05; the 09:00 update files, 32 of 83, still fall to the retry), its retry 09:48 → 11:18, the check 10:45 → 11:48 (11:18 + 15 + 15); four cron mutations re-aimed; the hand build's `--collected-by` becomes 11:48 in both commands; the design's B11 clock for the hand build follows.
- 2026-11-03, Task 8: from the moved check, the extractions are at 12:03 and the basket run at 12:33, `collected_by` "12:03" (call 11's formula; the plan's 11:00 and 11:30 were today's values). The role grants no read on `checks/`: the gate is a list, which `ListArchive` covers, so call 11's "restores the design's `checks/` read to the role" is withdrawn and call 4's list drops `checks/`; call 13 (the `basket/` read for a refused locked write) stands. 18 collector mutations re-aimed because the basket function repeats their text; the outputs test renamed for the third output. Parked with a ruling: the extractions start exactly when the check can have finished (11:48 + Lambda's 15 min), with no lag margin, unlike the check and the basket run; kept, because the check-record gate turns an overrun into `MorningNotChecked` and the basket run's `/fail` names it, and the check itself takes seconds (the 2026-11-02 record was written 3 s after its start).
- 2026-11-03, Task 9, two rulings: the docs follow the code, so one CloudFront invalidation follows any upload, an earlier day's new day file included (call 12 said the invalidation goes with the pages; the day JSON must be fresh at the edge too); the record goes up once the build has written it, so a run refused before the build (`MorningNotChecked`, `MissingTable`, `NoStoreList`) leaves none (call 9's "whatever happened" narrowed). The deploy steps 2, 3 and 9 and "Dropping a chain" moved to the eight parameters and the second check, since the site parameters have no default.

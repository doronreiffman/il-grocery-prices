# Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade:** portfolio project; the collector is held to production grade because a missed morning cannot be recovered.

**Goal:** a scheduled Lambda in il-central-1 that stores, every morning and write-once, each in-scope chain's store list, full price and full promotions files and the update files listed at that moment, and emails the owner only when a listed file is not stored, a chain is stopped, or a run fails.

**Architecture:** one Lambda, invoked by EventBridge Scheduler once per chain (and per file type for Shufersal) in three modes: `main`, `retry`, `check`, plus a manual `unblock`. Each chain has a source adapter (Shufersal, NCR "Published Prices", Carrefour) behind one interface; a shared run loop selects that day's files, downloads one at a time, validates, and writes them byte for byte to an Object Lock bucket with `IfNoneMatch="*"`, then writes a manifest. The check run compares what was listed against what the bucket holds. Patterns follow `/Users/doronreiffman/Projects/flights-archive` (`src/collector/store.py`, `handler.py`, `template.yaml`, `scripts/mutation_check.py`, `.github/workflows/ci.yml`).

**Tech Stack:** Python 3.13 (stdlib `urllib`, `http.cookiejar`, `html.parser`, `xml.etree`, `gzip`), boto3 (provided by the Lambda runtime), AWS SAM, pytest, pytest-cov, cfn-lint.

**Spec:** `docs/collector.md` (approved by the owner 2026-10-31). Read it first; this plan argues from it.

## Global Constraints

- AWS: profile `flights-sam`, region `il-central-1`, stack `il-grocery-prices`. Before any AWS command, `aws sts get-caller-identity --profile flights-sam` must show account 137953273942 and user doron-admin.
- GitHub: `gh auth status` must show doronreiffman active before any `gh` call or push. Subagents never run `gh` or push; the main session does.
- On the owner's go only: every `git push`, `sam deploy`, any AWS write, enabling the schedules.
- Chains in v1 and nothing else: `shufersal`, `ramilevy`, `osherad`, `carrefour`, `yochananof`. NCR usernames `RamiLevi`, `osherad`, `yohananof`, no password, cited to https://www.gov.il/he/pages/cpfta_prices_regulations (updated 12.08.2026).
- Blocks: 401, 403 or 429, a captcha or verification page, or HTML where a file belongs stops the chain, latches it until the owner clears it, and raises one alert. Never a browser User-Agent, another IP, a proxy, or another route. Exception: a 403 from Shufersal's file host (`pricesprodpublic.blob.core.windows.net`) at or after the link's `se=` expiry time means re-read the listing for a fresh link, once.
- NCR chains through the web login the gov.il list links (`https://url.publishedprices.co.il`), never FTP, unless the owner says otherwise.
- Keys: raw `raw/chain=<slug>/date=YYYY-MM-DD/<file name as published>`; a different body under a stored name goes to `<that key>.<first 12 hex of its SHA-256>`; manifests `manifests/date=YYYY-MM-DD/<slug>-<run id>.json`; check records `checks/date=YYYY-MM-DD/check-<run id>.json`; latch `state/<slug>.json`.
- Every raw, manifest and check write: `IfNoneMatch="*"`, `ObjectLockMode="GOVERNANCE"`, retain until now + 3650 days, `ChecksumAlgorithm="SHA256"` (flights-archive `store.py` `_put_locked`). Retention is set per object, not as a bucket default, so the state files stay plain, overwritable puts; the effect on stored files is the spec's ten-year governance lock.
- A run collects the current Israel calendar date (`zoneinfo` `Asia/Jerusalem` at run time); a file belongs to the date in its name, never to the time it was fetched. Every datetime is time-zone aware; never a naive `astimezone()` (this Mac runs on Asia/Jerusalem and CI on UTC, so a naive conversion passes in CI and is wrong here: flights-archive learned this).
- User-Agent `il-grocery-prices/<version> (+<repo URL>; <contact email>)`, from the deploy parameter `UserAgent`; the code refuses one without `+https://` and `@`. The owner's email, the health-check URL and any session token never go in the repo.
- One request at a time per chain; 0.5 s pause between files; at most one retry per file inside a run.
- Schedules, time zone `Asia/Jerusalem`: main from 06:30, retry from 09:30, check 10:00; per-chain invocations staggered 5 minutes apart; `MaximumRetryAttempts: 0` on the function's async config (Scheduler invokes asynchronously); schedules `DISABLED` by default through a `ScheduleState` parameter.
- Lambda: python3.13, arm64, 512 MB, 900 s timeout; a run stops downloading when under 60 s remain and records the rest as not attempted.
- The role may `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on the bucket (raw/, manifests/, checks/, state/) and `sns:Publish` on the alert topic; never `s3:DeleteObject*` or `s3:PutObjectRetention` beyond what a put needs.
- Fixtures under `tests/fixtures/` keep each portal's real structure (tags, attributes, layout, file names) with at most three items per file and synthetic prices, names and barcodes; signed-URL `sig=` values, cookies and CSRF tokens are scrubbed. Raw data is never published.
- Every component has tests; every rule gets a mutation in `scripts/mutation_check.py`; coverage floor 95% on `collector`; CI runs pytest, the mutation check and `cfn-lint --regions il-central-1`.
- No dependency younger than one month; pin versions.
- Docs in plain words; no "we".

## Review Focus

1. **A listing that parses to zero rows** (portal changed its page) must fail the run with "listing unreadable" and email, never read as "nothing published today". Test in Task 5 (`test_zero_rows_is_unreadable`) and Task 9 (`test_failed_run_alerts`).
2. **Time running out mid-chain**: the run stops when under 60 s remain, stores nothing half-written, writes its manifest with the rest as not attempted, and the retry run finishes the job. Test in Task 8 (`test_stops_before_timeout_and_records_not_attempted`).
3. **Shufersal link expiry vs a real block**: a 403 from the blob host after `se=` refreshes the link once; before `se=`, or from the listing host, it latches. Test in Task 5 (`test_expired_link_refreshes`, `test_403_before_expiry_blocks`).
4. **Old files in a listing**: closed stores' months-old files and yesterday's files are not selected and never count as "listed but not stored". Test in Task 8 (`test_only_that_days_files_selected`).
5. **Same-day re-run**: an identical body under a stored name is `EXISTS` (no conflict copy, no error); only a different body makes a conflict copy. Test in Task 7 (`test_identical_body_is_exists`, `test_different_body_gets_hash_suffix`).

---

### Task 1: Project setup, the probe, and the fixtures

The portals' mechanics are partly unknown (NCR login and listing; Carrefour's listing; NCR and Carrefour file names). This task finds out, from this Mac (in Israel), and records what later tasks code against.

**Files:**
- Create: `CLAUDE.md`, `.gitignore`, `pyproject.toml`, `requirements-dev.txt`, `src/requirements.txt` (empty: boto3 comes with Lambda), `.github/workflows/ci.yml`, `.claude/QUEUE.md`, `.claude/DECISIONS.md`, `.claude/OPEN_ISSUES.md`
- Create: `scripts/probe.py`, `docs/portals.md`, `tests/fixtures/<slug>/...`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Produces: `tests/fixtures/shufersal/` (one listing page per category: `listing-cat<1..5>.html`; one each of `Stores`, `PriceFull`, `PromoFull` `.gz`), `tests/fixtures/ncr/` (login page, the listing response as served, the same three file kinds, for one NCR chain), `tests/fixtures/carrefour/` (listing page and the three kinds); `docs/portals.md`, which states per portal: listing URL(s) and paging, request method and parameters, response format, file-name pattern, how a download link is formed, cookies or tokens needed, what a refusal looks like.

- [ ] **Step 1: Write `CLAUDE.md`** carrying the hard rules from the Global Constraints (personal accounts only, the AWS and GitHub checks, the owner's-go list, the block rule, raw never published, the chains in scope) plus a pointer to `docs/collector.md`. Copy the shape of flights-archive's `CLAUDE.md` "Hard rules"; keep it under 40 lines.
- [ ] **Step 2: Write `.claude/QUEUE.md`** (`## Queue` with `[q1] Collector: build per docs/collector-plan.md`; `## Done / Dropped`), and `DECISIONS.md` with three entries from the spec: Lambda not Airflow for collecting; Object Lock governance ten years; NCR via the web form. `OPEN_ISSUES.md` starts empty with the section headers `## Collector` and `## Portals`. (The global queue-guard hook lives in a repo this project must not touch; leave it to the owner.)
- [ ] **Step 3: Write `pyproject.toml`** (`pythonpath = ["src", "tests"]`, `testpaths = ["tests"]`), `requirements-dev.txt` (`pytest==9.*`, `pytest-cov`, `cfn-lint==1.58.0`, `boto3` pinned to a release at least a month old), and `.github/workflows/ci.yml` as flights-archive's, with `--cov=collector --cov-fail-under=95` (the mutation and cfn-lint steps join in Tasks 2 and 10).
- [ ] **Step 4: Write `scripts/probe.py`**: `python3 scripts/probe.py <slug>` reads the User-Agent from the environment variable `GROCERY_USER_AGENT` (refuses without `+https://` and `@`), reads the chain's listing (logging in with the published username for NCR chains), prints counts of rows by kind and by date, downloads one `Stores`, the smallest `PriceFull` and the smallest `PromoFull` of that day, one request at a time with a 2 s pause, at most 10 requests per run, and saves raw responses under a gitignored `probe-out/<slug>/`. It stops at the first refusal and prints it.
- [ ] **Step 5: Run the probe** for `shufersal`, `ramilevy` and `carrefour` (the owner supplies `GROCERY_USER_AGENT`). If NCR's web listing needs JavaScript to produce its file list, stop and report to the owner before going further (FTP needs his word). If Carrefour refuses from here, note it; it is retested from il-central-1 in Task 11.
- [ ] **Step 6: Build the fixtures** from `probe-out/` by hand or with a small script: keep structure, cut each XML to three items, replace prices, names and barcodes with synthetic values, scrub `sig=`, cookies and tokens, re-gzip.
- [ ] **Step 7: Write `docs/portals.md`** from what the probe saw, one section per portal.
- [ ] **Step 8: Write `tests/test_fixtures.py`**: `test_fixtures_have_no_secrets` (no file under `tests/fixtures/` contains `sig=` followed by a non-placeholder, `csrf`, `Set-Cookie`, `cftoken` or `@`), `test_fixture_xml_trimmed` (every gz fixture decompresses to at most three `Item` or `Promotion` elements).
- [ ] **Step 9: Run** `pytest -q`. Expected: 2 passed.
- [ ] **Step 10: Commit** `git add -A . ':!probe-out' && git commit -m "setup: project rules, probe, portal notes, trimmed fixtures"` (check `git status` first: nothing under `probe-out/`).

### Task 2: File names, payload checks, the store list, and the mutation harness

**Files:**
- Create: `src/collector/__init__.py`, `src/collector/names.py`, `src/collector/payload.py`, `src/collector/storelist.py`, `scripts/mutation_check.py`
- Test: `tests/test_names.py`, `tests/test_payload.py`, `tests/test_storelist.py`

**Interfaces:**
- Produces:
  - `names.KINDS = ("Stores", "PriceFull", "PromoFull", "Price", "Promo")`
  - `@dataclass(frozen=True) class FileName: raw: str; kind: str; chain_id: str; store: str | None; day: datetime.date`
  - `names.parse_file_name(name: str) -> FileName | None` (accepts a name with or without `.gz`/`.xml`; `None` for anything else)
  - `class payload.BadPayload(Exception)`; `payload.looks_like_html(data: bytes) -> bool`; `payload.check_payload(name: str, data: bytes) -> None`
  - `storelist.store_ids(data: bytes) -> set[str]` (gzip or plain XML)
  - `scripts/mutation_check.py` with the flights-archive harness and a `MUTATIONS` table later tasks add to.

- [ ] **Step 1: Write the failing tests.** `test_names.py`: `PriceFull7290027600007-002-045-20261031-030000` → kind `PriceFull`, chain `7290027600007`, store `045`, day 2026-10-31; `Stores7290027600007-000-20261031-020` → kind `Stores`, store `None`, day 2026-10-31; `Promo…-020000.gz` parses; `PriceFull` is never read as `Price` (longest kind first); one NCR and one Carrefour name from `docs/portals.md`; `"index.html"` → `None`. `test_payload.py`: gzip magic passes; `<?xml` passes; `b""` raises `BadPayload`; `b"<!DOCTYPE html>"` and `b"  <html"` → `looks_like_html` true and `check_payload` raises; a gzip whose content is HTML raises. `test_storelist.py`: the Shufersal and NCR `Stores` fixtures give their store ids (as strings, leading zeros kept as published).
- [ ] **Step 2: Run** `pytest tests/test_names.py tests/test_payload.py tests/test_storelist.py`. Expected: fail on import.
- [ ] **Step 3: Implement** the three modules (regex for names; magic bytes and a lower-cased prefix check after stripping whitespace for HTML; `xml.etree` for store ids, tag name from the fixtures, gunzipping when the magic says so).
- [ ] **Step 4: Run the tests.** Expected: pass.
- [ ] **Step 5: Write `scripts/mutation_check.py`** on flights-archive's harness with entries: "PriceFull read as Price", "day taken from the clock", "HTML accepted as a file", "empty file accepted". Run `python scripts/mutation_check.py`. Expected: every mutation caught. Add the mutation step to `ci.yml`.
- [ ] **Step 6: Commit** `git commit -m "names, payload checks, store list, mutation harness"`.

### Task 3: The HTTP client

**Files:**
- Create: `src/collector/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Produces:
  - `class Blocked(Exception)` with `.status: int | None`, `.url: str`, `.reason: str`
  - `class HttpError(Exception)` (timeouts, 5xx, other 4xx)
  - `@dataclass class Response: url: str; status: int; body: bytes; headers: dict[str, str]`
  - `class Http: __init__(self, user_agent: str, timeout: float = 30.0, pause: float = 0.5, opener=None, sleep=time.sleep)`; `get(url: str) -> Response`; `post(url: str, form: dict[str, str]) -> Response`; cookies kept per instance.

- [ ] **Step 1: Write the failing tests** with a fake opener: User-Agent sent on every request; `Http("bad")` raises `ValueError` (no `+https://`, no `@`); 401, 403, 429 raise `Blocked` with the status; a 200 whose body contains a captcha or verification marker (`cf-chl`, `captcha`, `Attention Required`) raises `Blocked`; 500 and a timeout raise `HttpError`; a cookie set on the first response is sent on the second; `sleep(0.5)` is called between two requests and not before the first; no request is retried.
- [ ] **Step 2: Run.** Expected: fail on import.
- [ ] **Step 3: Implement** `Http` on `urllib.request` with an `HTTPCookieProcessor` and a redirect handler that keeps the same host (flights-archive `core.py` refuses cross-host redirects; follow it).
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "429 not a block", "captcha page accepted", "User-Agent dropped", "pause skipped". Run the mutation check; all caught.
- [ ] **Step 6: Commit.**

### Task 4: The source interface and the chain list

**Files:**
- Create: `src/collector/chains.py`, `src/collector/sources/__init__.py`
- Test: `tests/test_chains.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Listed: name: FileName; url: str`
  - `class Source(Protocol): def listing(self, http: Http, kinds: tuple[str, ...]) -> Iterator[Listed]; def download(self, http: Http, item: Listed) -> bytes`
  - `@dataclass(frozen=True) class Chain: slug: str; name: str; portal: Literal["shufersal", "ncr", "carrefour"]; base_url: str; username: str | None = None`
  - `chains.CHAINS: dict[str, Chain]` with exactly the five slugs; `chains.source_for(chain: Chain) -> Source`

- [ ] **Step 1: Write the failing tests:** exactly the five slugs; the three NCR chains carry their usernames and no password field exists anywhere on `Chain`; every `base_url` is https; `source_for` returns the matching adapter class (adapters may be stubs until Tasks 5 and 6).
- [ ] **Step 2: Run.** Expected: fail.
- [ ] **Step 3: Implement.** A comment above the usernames cites the gov.il page and its update date.
- [ ] **Step 4: Run.** Expected: pass. **Step 5: Commit.**

### Task 5: The Shufersal source

**Files:**
- Create: `src/collector/sources/shufersal.py`
- Test: `tests/test_shufersal.py`

**Interfaces:**
- Consumes: `Http`, `Blocked`, `Listed`, `parse_file_name`.
- Produces: `class ShufersalSource(Source)` with `__init__(self, now: Callable[[], datetime] = <aware UTC now>)`; `CATEGORY = {"Price": 1, "PriceFull": 2, "Promo": 3, "PromoFull": 4, "Stores": 5}`; `class ListingUnreadable(Exception)` (also used by other sources; put it in `sources/__init__.py`).

- [ ] **Step 1: Write the failing tests** with a fake `Http` serving the fixtures: `listing(http, ("PriceFull",))` reads `/FileObject/UpdateCategory?catID=2&storeId=0&page=<n>` from page 1 until a page has no rows, yielding one `Listed` per row with the absolute download URL; rows whose name doesn't parse are skipped; `test_zero_rows_is_unreadable`: a first page that is HTML with no rows raises `ListingUnreadable`; `test_expired_link_refreshes`: a 403 from `pricesprodpublic.blob.core.windows.net` when the fake clock is past the URL's `se=` re-reads that category's listing, finds the same file name, and downloads it once; `test_403_before_expiry_blocks`: the same 403 before `se=` raises `Blocked`; a 403 from the listing host raises `Blocked`.
- [ ] **Step 2: Run.** Expected: fail.
- [ ] **Step 3: Implement** with `html.parser`; the clock is injected (`now: Callable[[], datetime]`, UTC); `se=` parsed from the query string.
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "expiry refresh on any 403", "stops after page 1", "zero rows read as empty day". All caught.
- [ ] **Step 6: Commit.**

### Task 6: The NCR and Carrefour sources

**Files:**
- Create: `src/collector/sources/ncr.py`, `src/collector/sources/carrefour.py`
- Test: `tests/test_ncr.py`, `tests/test_carrefour.py`

**Interfaces:**
- Consumes: as Task 5, and `docs/portals.md` for each portal's mechanics.
- Produces: `class NcrSource(Source)` with `__init__(self, username: str)`; `class CarrefourSource(Source)`.

- [ ] **Step 1: Write the failing tests** from the fixtures: NCR logs in with the username and an empty password, then lists; the listing yields `Listed` items for the requested kinds only; a login answer that isn't a successful login raises `Blocked`; zero rows raises `ListingUnreadable`; a download returns the body. Carrefour: listing parsed, kinds filtered, zero rows raises `ListingUnreadable`.
- [ ] **Step 2: Run.** Expected: fail. **Step 3: Implement** per `docs/portals.md`. **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "NCR sends a password", "kinds filter ignored", "failed login treated as success". All caught. **Step 6: Commit.**

### Task 7: Storage

**Files:**
- Create: `src/collector/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `raw_key(slug: str, day: date, name: str) -> str`; `manifest_key(day: date, slug: str, run_id: str) -> str`; `check_key(day: date, run_id: str) -> str`; `state_key(slug: str) -> str`
  - `class PutOutcome(Enum): STORED = "stored"; EXISTS = "exists"; CONFLICT_STORED = "conflict"`
  - `class S3Store: __init__(self, client, bucket: str, retention_days: int = 3650, lock_mode: str = "GOVERNANCE")`; `put_raw(key: str, body: bytes, now: datetime) -> PutOutcome`; `put_record(key: str, body: bytes, now: datetime) -> None` (manifests and checks, write-once, locked); `stored_names(slug: str, day: date) -> set[str]` (published names; a conflict copy counts as its original name); `read_raw(key: str) -> bytes`; `read_records(prefix: str) -> list[bytes]`; `read_state(slug: str) -> dict`; `write_state(slug: str, state: dict) -> None`
  - `class MemoryStore` with the same methods, for tests elsewhere.

- [ ] **Step 1: Write the failing tests** with a fake boto3 client recording calls: `put_raw` sends `IfNoneMatch="*"`, `ObjectLockMode="GOVERNANCE"`, retain-until `now + 3650 days`, `ChecksumAlgorithm="SHA256"`; `test_identical_body_is_exists`: a 412 on put, then the stored object's SHA-256 equals the body's → `EXISTS`, no second put; `test_different_body_gets_hash_suffix`: a 412 with a different stored body → a put to `<key>.<sha12>` and `CONFLICT_STORED`; `stored_names` maps `X.gz.<sha12>` back to `X.gz`; `write_state` is a plain put (no lock, no `IfNoneMatch`); no method ever calls `delete_object`.
- [ ] **Step 2: Run.** Expected: fail. **Step 3: Implement**, following flights-archive `store.py`. **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "IfNoneMatch dropped", "conflict overwrites", "identical re-run makes a conflict copy", "retention shortened". All caught. **Step 6: Commit.**

### Task 8: The run loop

**Files:**
- Create: `src/collector/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `Chain`, `Source`, `Http`, `Blocked`, `HttpError`, `ListingUnreadable`, `check_payload`, `BadPayload`, `looks_like_html`, `S3Store`/`MemoryStore`, the key functions.
- Produces:
  - `@dataclass class RunResult: chain: str; run_id: str; mode: str; day: date; listing_read_at: str; listed: list[str]; files: dict[str, dict]; failed: dict[str, str]; not_attempted: list[str]; blocked: str | None; error: str | None` where `files[name] = {"outcome": "stored" | "exists" | "conflict", "size": int, "sha256": str}`
  - `collect_chain(chain: Chain, source: Source, http: Http, store, day: date, run_id: str, mode: str, kinds: tuple[str, ...], time_left: Callable[[], float], now: Callable[[], datetime]) -> RunResult`
  - `manifest_bytes(result: RunResult, code_sha: str) -> bytes` (JSON, sorted keys)
  - `new_run_id(now: datetime, mode: str) -> str` (`<HHMMSS>Z-<mode>-<4 random hex>`)

- [ ] **Step 1: Write the failing tests** with fake sources and `MemoryStore`:
  - `test_only_that_days_files_selected`: a listing with that day's files, yesterday's, and a closed store's May file → only that day's are listed and fetched.
  - files already in `stored_names` are skipped (not downloaded) and not in `files`; each fetched file's entry carries its outcome, size and SHA-256.
  - a stopped chain (`read_state` says `stopped`) does nothing and returns `blocked="stopped earlier"`.
  - `Blocked` from listing or download: writes state `{"stopped": true, "since": <iso>, "reason": <text>, "alerted": false}`, stops, `blocked` set, nothing after it fetched.
  - HTML where a file belongs: same as `Blocked`; another `BadPayload`: one retry, then `failed[name]`.
  - `HttpError` on a download: one retry, then `failed[name]`; the run goes on.
  - `ListingUnreadable`: `error="listing unreadable: …"`, nothing stored.
  - `test_stops_before_timeout_and_records_not_attempted`: `time_left` drops under 60 s after two files → the rest are `not_attempted`, the manifest is still written.
  - the manifest is written with `put_record` to `manifest_key(day, slug, run_id)` in every outcome, including blocked and unreadable.
- [ ] **Step 2: Run.** Expected: fail. **Step 3: Implement.** **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "clock date instead of file date", "stored files fetched again", "no latch on block", "timeout guard removed", "manifest skipped on error". All caught. **Step 6: Commit.**

### Task 9: The check, the handler, and alerts

**Files:**
- Create: `src/collector/check.py`, `src/collector/handler.py`
- Test: `tests/test_check.py`, `tests/test_handler.py`

**Interfaces:**
- Consumes: `RunResult` manifests via `read_records`, `stored_names`, `store_ids`, state.
- Produces:
  - `@dataclass class Alert: chain: str; kind: Literal["missing", "stopped", "failed"]; text: str`
  - `check_day(store, slugs: list[str], day: date) -> tuple[list[Alert], dict]` (the dict is the check record: per chain, listed, stored, missing names, coverage = stores with a stored `PriceFull` / `store_ids` of that day's stored `Stores` file, or the latest stored one)
  - `@dataclass class Config: bucket: str; user_agent: str; alert_topic_arn: str; healthcheck_url: str; retention_days: int`; `Config.from_env(env) -> Config`
  - `@dataclass class Deps: store; http_for: Callable[[str], Http]; publish: Callable[[str, str], None]; ping: Callable[[str, str], None]; time_left: Callable[[], float]; code_sha: str` (`publish(subject, body)` wraps SNS; `ping(url, message)` wraps healthchecks.io; `handler` builds the real ones)
  - `run(cfg: Config, event: dict, deps: Deps, now: datetime) -> dict`; `handler(event, context)`; event `{"mode": "main" | "retry" | "check" | "unblock", "chain": "<slug>", "kinds": [...]}` (`kinds` optional, default all five; `chain` absent for `check`).

- [ ] **Step 1: Write the failing tests:**
  - `check_day`: a name listed in any of that day's manifests and absent from `stored_names` → one `missing` alert naming the chain and the count; a conflict copy counts as stored; a stopped chain whose state says `alerted: false` → one `stopped` alert and the state updated to `alerted: true`; a second check that day → no second `stopped` alert; `test_failed_run_alerts`: no `retry` manifest for a chain that day, or one with `error` set → `failed` alert; coverage is in the record and never raises an alert.
  - `handler.run`: `main`/`retry` build the source and call `collect_chain` with the event's kinds and an Israel-date `day`, and never call `publish` (individual errors are logged, not emailed); `check` publishes one SNS message only when there are alerts, always writes the check record, and pings `healthcheck_url` (a failed ping is logged, not raised); `unblock` clears the chain's state; an unknown mode or chain raises `ValueError`; `Config.from_env` refuses a User-Agent without `+https://` and `@`.
- [ ] **Step 2: Run.** Expected: fail. **Step 3: Implement.** **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Mutations:** "missing files not alerted", "stopped alerted every check", "coverage alerts", "retry manifest not required", "ping failure raises". All caught. **Step 6: Commit.**

### Task 10: The deploy template and the operations doc

**Files:**
- Create: `template.yaml`, `docs/operations.md`
- Test: `tests/test_template.py`

**Interfaces:**
- Consumes: `collector.handler.handler`.
- Produces: stack `il-grocery-prices` with parameters `UserAgent`, `AlertEmail`, `HealthcheckUrl`, `ScheduleState` (default `DISABLED`).

- [ ] **Step 1: Write the failing tests** (load the YAML with a CloudFormation-tag-aware loader, as flights-archive `tests/test_template.py`): the bucket has `ObjectLockEnabled: true`, versioning, all four public-access blocks, `DeletionPolicy: Retain`; the role grants no `s3:Delete*`; the function is python3.13, arm64, 512 MB, 900 s, with async `MaximumRetryAttempts: 0`; every schedule uses `ScheduleExpressionTimezone: Asia/Jerusalem` and `State: !Ref ScheduleState`; there is a main and a retry schedule for each of the five chains (Shufersal split into a `PriceFull` + `Price` invocation, a `PromoFull` + `Promo` invocation and a `Stores` invocation), and one check at 10:00; no two schedules share a start minute; `UserAgent` has an `AllowedPattern` requiring `+https://` and `@`.
- [ ] **Step 2: Run.** Expected: fail. **Step 3: Write `template.yaml`.** **Step 4: Run** the tests and `cfn-lint --regions il-central-1 -- template.yaml`. Expected: pass, no errors. Add cfn-lint to CI.
- [ ] **Step 5: Write `docs/operations.md`**: deploy (as flights-archive's, with the account check), the healthchecks.io check to create (period 1 day, grace 2 hours), confirming the SNS email, a manual run per chain, `unblock`, dropping a chain (delete its schedules and its entry in `CHAINS`; stored files stay), and the cost.
- [ ] **Step 6: Mutations:** "schedule enabled by default", "delete allowed", "UTC schedule". All caught. **Step 7: Commit.**

### Task 11: First deploy, schedule off (the owner's go)

Not code: a checklist the main session runs with the owner.

- [ ] **Step 1:** Whole-branch review by a fresh reviewer (Fable; the newest Opus if Fable is at its limit, named in the report). Fold findings; rerun pytest, the mutation check and cfn-lint.
- [ ] **Step 2:** Owner creates the healthchecks.io check and supplies `HealthcheckUrl`, `AlertEmail`, `UserAgent`. Push on his go; CI green.
- [ ] **Step 3:** On his go: `sam build` and `sam deploy` with `ScheduleState=DISABLED`; confirm the SNS subscription email.
- [ ] **Step 4:** Invoke `main` once per chain by hand; check the bucket (files under `raw/`, Object Lock retention set on one object) and each manifest. Carrefour's result from il-central-1 decides whether it stays; a refusal means drop it (record in `OPEN_ISSUES.md`).
- [ ] **Step 5:** Invoke `check`; confirm the check record and the healthchecks.io ping.
- [ ] **Step 6:** On his go: redeploy with `ScheduleState=ENABLED`. The next morning, read the manifests and the check record.
- [ ] **Step 7:** Update `.claude/QUEUE.md` (q1 done, with the proof) and flights-archive's q19.

## Deviations

(Append here when reality forces a change from this plan: what changed, why, and when.)

- **2026-11-01, Task 1, pins:** `requirements-dev.txt` pins `pytest==9.1.1`, `pytest-cov==7.1.0`, `cfn-lint==1.57.1`, `boto3==1.43.106`, the newest releases at least a month old (`pip install --uploaded-prior-to P31D`). The plan's `pytest==9.*` resolves to 9.2.0 and its `cfn-lint==1.58.0` is younger than a month; flights-archive's `boto3==1.43.119` was pinned 2026-10-27.
- **2026-11-01, Task 1, fixture secret test:** it checks CSRF token *values* (each must be `SCRUBBED` or empty), not the word "csrf": NCR's real pages carry `<meta name="csrftoken">`, which Task 6 needs. The email pattern requires a domain starting with a letter (ruling R2's example matches NCR's `logo@2x.png`). It also refuses `cftpSID`, NCR's session cookie name. The trim test counts `Item`, `Promotion`, `PromotionItem` and `Store` (three at most each) and requires at least one of the file's main record.
- **2026-11-01, Task 1, fixtures:** `tests/fixtures/ncr/` adds `file-page.html` (the page after login, which holds the listing's token and page size). NCR's `listing.json` keeps 14 of 2,362 entries and Carrefour's `listing.html` 9 of 575 files, with the totals adjusted to match.
- **2026-11-01, Task 1, findings for later tasks** (detail in `docs/portals.md`, "What the later tasks must handle"): Carrefour's and Rami Levy's Stores files are plain UTF-16 LE XML with a BOM, so Task 2's payload check must accept that (and a UTF-8 BOM before `<Root>`), not only gzip and `<?xml`; a Shufersal page past the last returns the last page again, so Task 5 cannot read "until a page has no rows" and must stop at the pager's last page; NCR store 039 publishes lower-case names without a sub-chain (`pricefull7290058140886-039-202610310517.gz`), which Task 2's name parser must accept or knowingly skip; NCR's page size changes per session.
- **2026-11-01, Task 2, checks wider than the plan's:** `parse_file_name` reads Rami Levy store 039's lower-case names (kind case-insensitive, returned as in `KINDS`; store from the group before the date; day from the first `YYYYMMDD` of a date-and-time run). `check_payload` also accepts a UTF-8 BOM before `<?xml` or `<Root>` and a UTF-16 LE BOM, and requires a gzip to hold one of the same XML starts; `looks_like_html` looks inside a gzip and through a UTF-16 BOM, so accepting UTF-16 does not let a UTF-16 HTML page through. The mutation check has 20 entries, not 4: one per rule. Its pytest runs set `PYTHONDONTWRITEBYTECODE=1`: Python trusts a cached `.pyc` whose source has the same size and whole-second mtime, so a same-length mutation could otherwise stay cached after the file is restored.
- **2026-11-01, Task 2, ruling R12:** `check_payload` unzips a gzip body in full (`gzip.decompress`, which checks the length and CRC) and refuses a cut-short or corrupt one, not just its first bytes: a short file stored write-once would never be fetched again, since later runs skip stored names. Mutations "truncated gzip accepted" and "cut-short gzip escapes as EOFError" bring the check to 22.
- **2026-11-01, Task 3, the HTTP client, wider than the plan:** ruling R3: the captcha and verification words (`cf-chl`, `captcha`, `Attention Required`) are sought only in a body that looks like HTML (a `text/html` content type, or `looks_like_html`), never in a gzip, other data or the headers: the words can turn up by chance in a file, and NCR's Content-Security-Policy header names reCAPTCHA on every answer. A verification page is a block whatever its status, not only with 401, 403 or 429. A body shorter than its `Content-Length` raises `HttpError` (belt and braces for R12). A redirect to another scheme, host or port raises `HttpError` naming it. The opener takes no proxy (`ProxyHandler({})`): urllib otherwise uses one from the environment, or on macOS from the system settings. `Blocked.url` keeps the query string (the Shufersal adapter reads `se=` from it); the message leaves it out. Tests pass a fake network to `build_opener`, so the cookie jar, redirect rule and proxy setting under test are production's. The mutation check gains 28 entries, one per rule (50 in all).
- **2026-11-01, Task 5, the Shufersal source, wider than the plan:** paging follows ruling R11, not "until a page has no rows": page 1's `>>` link names the last page, a category with no pager is one page, and a page with no rows, or a pager that names no last page by number, raises `ListingUnreadable`. The listing reads a page only once the caller has taken the previous page's rows (R16), and checks all of a page's rows before giving the first: eight cells, and a link that is https on `pricesprodpublic.blob.core.windows.net` (R15), ASCII with no spaces or control characters, and ends in the row's name plus `.gz`. That last check exists because the run loop files a download under the link's last path segment while the day comes from the name cell. Names that do not parse are counted in `unparsed`, now declared on `Source` so Task 6's adapters keep the count too (R13, R16). Rows of a kind not asked for are left out, as `Source.listing` promises. An expired link's refresh reads the category from page 1 up to the page that lists the file; a file no longer listed raises `HttpError`; the refresh can also raise `Blocked` or `ListingUnreadable`, as the listing can. `se=` is read only in the shape the links carry (`YYYY-MM-DDTHH:MM:SSZ`, UTC); a 403 whose link has no `se=` of that shape is a block. Ruling R17 widens the constraint's "at or after `se=`" by two minutes: a 403 from the file host counts as expiry from `se=` minus 120 seconds on, slack for Azure's clock running ahead of the collector's; earlier, it is a block. The mutation check gains 43 entries (115 in all).

"""The scheduled build's Lambda entry point: one invocation per event, as the collector's handler is. EventBridge
Scheduler sends the events each morning; the owner sends the same with a "day" to run an earlier day by hand.

    {"mode": "extract", "chain": "<slug>"}         the chain's day of full files into its prices, promotions and
                                                   items tables
    {"mode": "basket", "collected_by": "HH:MM"}    the site run: the shopper site's day, the basket's among it,
                                                   built, checked, guarded and published

"day" (YYYY-MM-DD) is optional in both; without it the day is the Israel calendar date when the invocation starts.
Every field is checked before anything is read. Then neither mode runs until the collector's check has written its
record for the day under `checks/date=<day>/` (MorningNotChecked): the check is the morning's last run, so its record
shows that every chain's runs are over. Each run works in a folder of its own under `tmp_root` (`/tmp` in Lambda),
`basket-` and a random suffix, and removes it when it ends, failed or not: a warm Lambda keeps `/tmp` from one
invocation to the next. A run Lambda kills at its timeout never gets to remove its folder, nor DuckDB its spill files,
so each run, before it makes its own, removes every `basket-*` folder under `tmp_root`, and DuckDB's temp folder
(DUCKDB_TEMP_DIRECTORY) when it holds anything: one invocation runs in an execution environment at a time, so what
they hold is always an earlier run's. DuckDB's folder is swept only when it is a folder of its own under `tmp_root`.
A removal that fails is logged as a warning and the run goes on.

The extract mode fetches the chain's full price and promotion files of the day (`PriceFull`, `PromoFull`) and its
store list from the archive bucket into the work folder, runs `shopper.extract.extract_chain_day` over them as the
Mac does (the prices table as `basket.extract` has always written it, then the store list, the columns, the
promotions table and the items table), and puts each table's files that are present back under `tables/`, plain,
replacing an earlier run's. Carrefour's columns are those of CARREFOUR_TABLE, the hand-kept table, read at call time so
the tests can give the golden day's own. A promotion format change, or a promotion file that does not read, stops the
chain's promotions and not the run: its prices and items tables go up, its promotions folder's report naming the error.
Whatever stops the run once the prices table is written (no store list, a failure in the shopper's steps), the files
written so far go up before the error is raised, so the basket run keeps the chain's prices table as before the
shopper's steps. Its summary, logged as one JSON line and returned, counts the files read and passed over, the stores
and rows in the prices table and the rows whose price could not be read, and gives the prices extraction's own seconds
(the fetch and the put left out) and the keys put; then the promotions' counts (None when they were not read), the
promotions error (None when there was none), each column's items, wide items, hole and promotion hole, and the
seconds of the promotions and of the items steps.

The basket mode is the shopper site's run (the shopper plan's Task 23; the 12:33 event keeps "basket", question M
(b)): it builds, checks, guards and publishes the site's whole day, the basket's day among it. In order:

1. The fetch, into the work folder laid out as the Mac's synced `data/` and `site/`. From the archive: each chain's
   prices table of the day (MissingTable, naming the chain and the table's key, when its extraction run did not run or
   did not finish), its store list and its manifests; each chain's items table, with its report, of the day and of
   the 90 days before it, every column of the chain in it: the day's own missing is MissingTable, naming the chain and
   the key (its extraction stops before the items table when the chain has no store list), a past day's missing is a
   hole in each of the chain's columns, as `shopper.history.load` reads it; the latest covered registry before the
   day; every scoring summary. The frozen forecasts files the build scores are read by the archive's freezer itself
   (`shopper.freeze.ArchiveFreezer`), not fetched. From the site: the day's published `days/<d>.json` and
   `site-days/<d>.json`, the latest published site-day file before the day (the build tells by it the days newly out of
   reach) and `forecasts/ledger.csv`, each under `site/` for the build to compare with and under `published/` for the
   guard; for the guard alone, the published `forecasts/<d>.csv.gz` and the `scores/<t>.csv.gz` of each day due for
   scoring (`shopper.score.due`), and the published `p/` keys. Past days' forecasts and scores files are not fetched:
   the check resolves the record page's links to them by the ledger and the newest site-day file (the pre-flights' B5
   and B2). One chain's missing table or store list therefore stops the run for all five chains, as a missing prices
   table stops the basket's (taken on knowingly; the message says so).
2. The build, `shopper.build.build_site`, through the archive's freezer, with the tables kept (`extract=False`) and
   never with a reason to revise: it scores each day due (its scores file put once, locked), freezes the day's
   forecasts (put once, locked; F6) and publishes the site-day and basket day files by B12. RevisionNeeded (the day's
   numbers differ from its published copy), ForecastsDiffer (the archive holds a forecasts file of the day with other
   rows, question E) and NoStoreList stop the run, nothing uploaded, each message saying what to do (`WHAT_NOW`): only a
   hand build revises, with a one-line reason, once the published ledger names the day's forecasts file when the
   archive holds one; a differing freeze is put up by a rerun at the commit that froze the day.
3. The check (`shopper.check.check_site`) and the guard (`shopper.guard.guard_site`, its latest-day and product-page
   rules only when the pages go up, the second pre-flight's S17): SiteCheckFailed, nothing uploaded.
4. The upload (`basket.site.upload`): the data files the build lists new, always (Call 9), then, only when the day is
   the site's latest or later, every page under `p/`, `browse/` and `search/` and the fixed pages, so a run for an
   earlier day leaves every page as the later day's; one invalidation when anything went up.
5. Put back, plain, after the upload: the day's covered registry and the summary of each day scored. A day is scored
   once its summary is in the archive, so a run whose upload fails leaves its days due, and the next run publishes the
   same scores file (the archive's bytes) before it marks them scored.

The run's record goes up to the archive, write-once and locked, whatever stopped the run once the record was written.
The summary gives the day, the basket's run id and headline, whether its day file and the site-day file were
unchanged, whether the pages went up, the data files uploaded (by key) and the pages (by count), the invalidation's id,
the record's key, the day's forecasts file as the freezer gave it (its status, "frozen", "late", "same" or "none", its
SHA-256 and whether on time), the days scored, each chain's promotions error, the alerts, and the seconds of each step:
the fetch, the build and, within it, the scoring and the one pass, the check, the guard, the upload, and the total
(measured, not tuned: the plan's Task 25a speeds the run up).

The basket mode reports to healthchecks.io: `/start` before it looks for the check record; then, when the run succeeds,
the plain URL with the run's summary, or, when it succeeds with alerts, `/fail` after the upload with the alert lines
and the summary: each chain whose promotions could not be read, by the extraction's message naming its field
(question M (a)); each stored scores file whose rows differ from this run's, kept and published as the record, with
both SHA-256s; the days that went out of the read's reach this morning (Task 19's ruling). When anything fails it pings
`/fail` with the error's name and text, MorningNotChecked included. A /fail body is cut to its first 100,000 bytes of
UTF-8, since healthchecks.io keeps the first 100 kB of a body; a character the cut would split is dropped. An event
refused as bad (ValueError) sends no ping. A ping that fails is logged as a warning naming its kind (start, success or
fail) and the run goes on: its outcome never hangs on healthchecks.io. The ping URL is a secret: no part of it reaches
the log, the error's text included.

The extract mode never pings. A chain whose prices extraction failed, or whose run Lambda killed (memory over the
function's, or the timeout: then nothing goes up), shows in the site run as a missing table, unless an earlier run of
the day put one (a put adds or replaces; nothing deletes). A run stopped in a later step has put its prices table but
not its items table: a chain with no store list, or a run stopped in the promotions or the items table, shows in the
site run as a missing items table of the day (again unless an earlier run of the day put one).

Environment: BUCKET (the archive bucket), SITE_BUCKET (the site stack's bucket: refused unless its name starts with
SITE_BUCKET_PREFIX, so the archive bucket is never taken for it), DISTRIBUTION_ID, HEALTHCHECK_URL, USER_AGENT (each
required), RETENTION_DAYS (default 3650), DUCKDB_TEMP_DIRECTORY (optional: the folder `basket.duck` gives DuckDB). The one S3
client, the archive's and the site's, holds a connection for each upload worker (`S3_CONFIG`; botocore's default pool
holds 10, fewer than the 16).
"""
import json
import logging
import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from botocore.config import Config as ClientConfig

from basket.archive import S3Archive, kind_key, table_key
from basket.basket_file import DEFAULT_BASKET
from basket.build import RevisionNeeded
from basket.chains import CARREFOUR_COLUMNS, SLUGS
from basket.duck import TEMP_DIRECTORY_VAR
from basket.rules import MissingTable
from basket.site import UPLOAD_WORKERS, S3Site, day_key, day_of
from basket.stores import NoStoreList
from collector.handler import ping, ping_user_agent
from collector.http import check_user_agent
from collector.run import new_run_id
from collector.store import RETENTION_DAYS
from shopper.build import LEDGER, build_site
from shopper.check import check_site
from shopper.extract import extract_chain_day
from shopper.freeze import ArchiveFreezer, ForecastsDiffer, scores_site_key, site_key
from shopper.guard import guard_site
from shopper.score import due
from shopper.siteday import site_day_path

# INFO on the package's logger itself, so the runs' summaries reach CloudWatch whatever level the runtime gives
# the root logger, as the collector's handler does for its package.
logging.getLogger("basket").setLevel(logging.INFO)
log = logging.getLogger(__name__)

REQUIRED = ("BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT")
SITE_BUCKET_PREFIX = "il-grocery-prices-site-sitebucket-"
MODES = ("extract", "basket")
ISRAEL = ZoneInfo("Asia/Jerusalem")
CLOCK = re.compile(r"^[0-2][0-9]:[0-5][0-9]$")
BASKET_FILE = DEFAULT_BASKET  # read at call time, as MIN_ITEMS is: the tests give the golden day's own
MIN_ITEMS = 25  # the fewest items the basket may hold, as the hand build's default
CARREFOUR_TABLE = CARREFOUR_COLUMNS  # read at call time, as BASKET_FILE is: the tests give the golden day's own
EXTRACT_KINDS = ("PriceFull", "PromoFull")  # the extract mode's files of the day
FAIL_BYTES = 100_000  # a /fail ping's body: the error's name and text, cut to this many bytes of UTF-8
PING_PATHS = {"start": "/start", "success": "", "fail": "/fail"}  # each ping's kind and its path after the URL
S3_CONFIG = ClientConfig(max_pool_connections=UPLOAD_WORKERS)  # a connection for each upload worker
ALERTED = "SiteAlert: the site went up, and:"  # the head of the /fail body for a run that published with alerts
# What to do, said after the message of each refusal the build gives (the module's docstring, 2).
WHAT_NOW = {
    RevisionNeeded: ("The site run never revises a published day: build the day by hand with a one-line reason to "
                     "revise (scripts/sync.sh, shopper.build's revise option, then scripts/publish.sh), once the "
                     "published ledger names the day's forecasts file when the archive holds one."),
    ForecastsDiffer: ("Nothing went up. Rerun the site run at the commit that froze the day; a hand build can then put "
                      "up pages from later code, with a one-line reason to revise when its numbers differ."),
    NoStoreList: "One chain's missing store list stops the site run for all five chains.",
}


class MorningNotChecked(Exception):
    """The collector's check has not written its record for the day."""


class SiteCheckFailed(Exception):
    """The built site failed the site check (`shopper.check`) or the publish guard (`shopper.guard`); the problems, one
    a line."""


@dataclass(frozen=True)
class Config:
    bucket: str
    site_bucket: str
    distribution_id: str
    healthcheck_url: str
    user_agent: str
    retention_days: int
    duckdb_temp_directory: Path | None = None  # DuckDB's temp folder, swept at run start; None when unset

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        missing = [name for name in REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ValueError(f"missing environment variables: {', '.join(missing)}")
        if not env["SITE_BUCKET"].startswith(SITE_BUCKET_PREFIX):
            raise ValueError(f"SITE_BUCKET must be the site stack's bucket, whose name starts with {SITE_BUCKET_PREFIX}, "
                             f"not {env['SITE_BUCKET']!r}")
        spill = env.get(TEMP_DIRECTORY_VAR, "").strip()  # as basket.duck reads it
        return cls(bucket=env["BUCKET"], site_bucket=env["SITE_BUCKET"], distribution_id=env["DISTRIBUTION_ID"],
                   healthcheck_url=env["HEALTHCHECK_URL"], user_agent=check_user_agent(env["USER_AGENT"]),
                   retention_days=int(env.get("RETENTION_DAYS", RETENTION_DAYS)),
                   duckdb_temp_directory=Path(spill) if spill else None)


@dataclass
class Deps:
    """What run() works through: the archive bucket (an `_Archive`), the site bucket and its distribution (a
    `_Site`), and `ping(url, message)` to healthchecks.io. The extract mode uses the archive alone."""

    archive: Any
    site: Any
    ping: Callable[[str, str], None]


def _aware(now: datetime) -> datetime:
    # A naive time would be read as this machine's zone: Asia/Jerusalem on the Mac, UTC in CI.
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must carry a time zone")
    return now


def event_day(event: dict, now: datetime) -> date:
    """The day the event names under "day" (YYYY-MM-DD), else the Israel date at `now`, which must then carry a time
    zone. Raises ValueError for a "day" that is not such a date."""
    if "day" not in event:
        return _aware(now).astimezone(ISRAEL).date()
    value = event["day"]
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):  # TypeError: a day that is no string
        raise ValueError(f"the event's day must be a date as YYYY-MM-DD, not {value!r}") from None


def run(cfg: Config, event: dict, deps: Deps, now: datetime, tmp_root: Path) -> dict:
    """Do what `event` asks (see the module's docstring), in a work folder under `tmp_root`; `now` is the invocation's
    start, aware. Raises ValueError for a bad event or a naive `now`, before anything is read, and MorningNotChecked
    while the day has no check record, before anything is fetched. Returns a summary, also logged. The basket mode
    pings healthchecks.io from its start on, its failures included."""
    mode = event.get("mode") if isinstance(event, dict) else None
    if mode not in MODES:
        raise ValueError(f"the event's mode must be extract or basket, not {mode!r} (event {event!r})")
    if mode == "extract":
        if event.get("chain") not in SLUGS:
            raise ValueError(f"unknown chain {event.get('chain')!r}: one of {', '.join(SLUGS)}")
    else:
        collected_by = event.get("collected_by")
        if not isinstance(collected_by, str) or not CLOCK.fullmatch(collected_by):
            raise ValueError(f"the basket event's collected_by must be a time as HH:MM, not {collected_by!r}")
    _aware(now)
    day = event_day(event, now)
    pings = mode == "basket"  # the extract mode never pings
    if pings:
        _ping(deps, cfg.healthcheck_url, "start", "")
    try:
        if not deps.archive.day_checked(day):
            raise MorningNotChecked(f"the collector's check has not written its record for {day}: the morning is "
                                    f"not over, or the check failed (checks/date={day}/)")
        _sweep(tmp_root, cfg.duckdb_temp_directory)
        work = Path(tempfile.mkdtemp(prefix="basket-", dir=tmp_root))
        try:
            if mode == "extract":
                summary = _extract(event["chain"], day, deps, now, work)
            else:
                summary = _basket(event, deps, now, work, day)
                if summary["alerts"]:  # the site went up: the alerts, after the upload (question M (a))
                    _ping(deps, cfg.healthcheck_url, "fail", _cut(_alert(summary), FAIL_BYTES))
                else:
                    _ping(deps, cfg.healthcheck_url, "success", json.dumps(summary))
        finally:
            _remove(work)
    except Exception as err:
        if pings:
            _ping(deps, cfg.healthcheck_url, "fail", _cut(f"{type(err).__name__}: {err}", FAIL_BYTES))
        raise
    log.info(json.dumps(summary, sort_keys=True))
    return summary


def _alert(summary: dict) -> str:
    """The /fail body of a run that published with alerts: what went up, each alert a line, then the summary."""
    return "\n".join([ALERTED, *summary["alerts"], "", json.dumps(summary)])


def _cut(text: str, limit: int) -> str:
    """`text` cut to its first `limit` bytes of UTF-8, less a character the cut would split."""
    return text.encode()[:limit].decode(errors="ignore")


def _sweep(tmp_root: Path, spill: Path | None) -> None:
    """Remove what runs Lambda killed at its timeout left: the `basket-*` folders under `tmp_root` (earlier runs' work
    folders) and DuckDB's temp folder `spill` (its spill files). How many of each, logged when there were any."""
    stale = [path for path in tmp_root.glob("basket-*") if path.is_dir()]
    for path in stale:
        _remove(path)
    if stale:
        log.info("removed the work folders earlier runs left under %s: %d", tmp_root, len(stale))
    if spill is not None and spill.is_dir():
        _sweep_spill(tmp_root, spill)


def _sweep_spill(tmp_root: Path, spill: Path) -> None:
    """Remove DuckDB's temp folder `spill` when it holds anything (`basket.duck` makes it again when it next
    connects), and say how many entries it held. Only a folder of its own strictly under `tmp_root`: the setting
    names it, and a wrong one must not empty /tmp or anything outside it, so a link, `tmp_root` itself or a folder
    elsewhere is left as it is, with a warning. A folder that cannot be listed is a warning too."""
    if spill.is_symlink() or tmp_root.resolve() not in spill.resolve().parents:
        log.warning("DuckDB's temp folder %s is not a folder of its own under %s: left as it is", spill, tmp_root)
        return
    try:
        left = list(spill.iterdir())
    except OSError as error:
        log.warning("could not read DuckDB's temp folder %s: %s: %s", spill, type(error).__name__, error)
        return
    if left:
        _remove(spill)
        log.info("removed what earlier runs left in DuckDB's temp folder %s: %d", spill, len(left))


def _remove(path: Path) -> None:
    """Remove `path` and all it holds. What cannot be removed is left and logged as a warning, one a part, and the
    run goes on: /tmp is the next run's to sweep, never a reason to fail this one."""
    shutil.rmtree(path, onexc=_not_removed)


def _not_removed(function, path, error: BaseException) -> None:
    log.warning("could not remove %s: %s: %s", path, type(error).__name__, error)


def _ping(deps: Deps, base: str, kind: str, message: str) -> None:
    """Ping healthchecks.io at `base` and the path of the ping's kind (PING_PATHS). A failure is logged by the kind,
    with the URL masked out of the error's text, and never raised."""
    try:
        deps.ping(base + PING_PATHS[kind], message)
    except Exception as exc:  # healthchecks.io down or slow: the run's outcome stands
        log.warning("the %s ping to healthchecks.io failed: %s: %s", kind, type(exc).__name__, _masked(str(exc), base))


def _masked(text: str, url: str) -> str:
    """`text` with the URL, its host and each segment of its path replaced by "<hidden>"; an error's text can quote
    the URL it failed on, and the ping URL is a secret."""
    parts = urlsplit(url)
    for secret in (url, parts.netloc, *parts.path.split("/")):
        if secret:
            text = text.replace(secret, "<hidden>")
    return text


def _extract(slug: str, day: date, deps: Deps, now: datetime, work: Path) -> dict:
    run_id = new_run_id(now, "extract")
    raw, tables = work / "raw", work / "tables"
    deps.archive.fetch_raw(slug, day, raw, kinds=EXTRACT_KINDS)
    deps.archive.fetch_store_list(slug, day, raw)  # None: the extraction refuses the chain after its prices table
    try:
        report = extract_chain_day(raw, slug, day, tables, table=CARREFOUR_TABLE)
    finally:  # whatever stopped it, what the extraction wrote goes up: a chain stopped after its prices keeps them
        keys = deps.archive.put_tables(slug, day, tables)
    prices = report.prices
    return {"mode": "extract", "chain": slug, "day": day.isoformat(), "run_id": run_id, "files": len(prices.files),
            "skipped": len(prices.skipped), "stores": prices.stores, "rows": prices.rows,
            "unreadable_prices": prices.unreadable_prices, "seconds": round(report.seconds["prices"], 1),
            "keys": keys, **report.summary()}


def _since(started: float) -> float:
    """The seconds since `started` (`time.perf_counter`), to a tenth."""
    return round(time.perf_counter() - started, 1)


def _copy(site, key: str, *folders: Path) -> None:
    """The site's published file at `key`, when there is one, written at that key under each of `folders`."""
    body = site.published(key)
    if body is None:
        return
    for folder in folders:
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)


def _published(site, day: date, due_days: list[date], site_dir: Path, published_dir: Path) -> None:
    """The site's published copies the build and the guard read (the module's docstring, 1)."""
    earlier = [seen for seen in map(day_of, site.keys("site-days/")) if seen is not None and seen < day]
    compared = [day_key(day), site_day_path(Path(), day).as_posix(), LEDGER]
    compared += [site_day_path(Path(), max(earlier)).as_posix()] if earlier else []
    for key in compared:  # the build compares with them, and so does the guard
        _copy(site, key, site_dir, published_dir)
    for key in [site_key(day), *(scores_site_key(t) for t in due_days)]:  # the guard alone
        _copy(site, key, published_dir)


def _alerts(outcome) -> list[str]:
    """What the run alerts for after the upload (the module's docstring), one line each."""
    alerts = [f"promotions not read: {message}" for message in outcome.promotions_errors.values()]
    alerts += [f"scores differ, the stored file kept: {message}" for message in outcome.scores_differ]
    if outcome.newly_out_of_reach:
        alerts.append("out of reach, never scored: " + ", ".join(t.isoformat() for t in outcome.newly_out_of_reach))
    return alerts


def _basket(event: dict, deps: Deps, now: datetime, work: Path, day: date) -> dict:
    started = time.perf_counter()
    tables, raw, site, published = work / "tables", work / "raw", work / "site", work / "published"
    seconds: dict[str, float] = {}
    records = []
    try:
        for slug in SLUGS:
            if not deps.archive.fetch_table(slug, day, tables):
                raise MissingTable(f"no table for chain {slug!r} on {day}: its extraction run did not run or did not "
                                   f"finish ({table_key(slug, day, 'prices.parquet')})")
            deps.archive.fetch_store_list(slug, day, raw)  # None: build_day refuses the chain as NoStoreList
            deps.archive.fetch_manifests(slug, day, work / "manifests")
        read = deps.archive.fetch_history(day, tables)
        for slug in SLUGS:
            key = kind_key("items", slug, day, "items.parquet")
            if key not in read:
                raise MissingTable(f"no items table for chain {slug!r} on {day}: its extraction run did not run or did "
                                   f"not finish its items table, as when the chain has no store list ({key}); one "
                                   "chain's missing table stops the site run for all five chains")
        deps.archive.fetch_covered(day, tables)
        scored = [summary.day for summary in deps.archive.fetch_summaries(tables)]
        _published(deps.site, day, due(deps.archive.frozen_days(), scored, day), site, published)
        latest = deps.site.latest_published_day()
        with_pages = latest is None or day >= latest  # the pages show the site's latest day
        product_pages = deps.site.keys("p/")
        seconds["fetch"] = _since(started)
        step = time.perf_counter()
        try:
            outcome = build_site(day, work, site, now, collected_by=event["collected_by"],
                                 freezer=ArchiveFreezer(deps.archive, now), revise=None, extract=False,
                                 basket_path=BASKET_FILE, min_items=MIN_ITEMS)
        except tuple(WHAT_NOW) as error:
            raise type(error)(f"{error}\n{WHAT_NOW[type(error)]}") from error
        seconds["build"] = _since(step)
        seconds |= {name: round(took, 1) for name, took in outcome.seconds.items()}
        step = time.perf_counter()
        problems = check_site(site)
        if problems:
            raise SiteCheckFailed("\n".join(["the site check failed:", *problems]))
        seconds["check"] = _since(step)
        step = time.perf_counter()
        problems = guard_site(site, published, product_pages, with_pages=with_pages)
        if problems:
            raise SiteCheckFailed("\n".join(["the publish guard failed:", *problems]))
        seconds["guard"] = _since(step)
        step = time.perf_counter()
        uploaded = deps.site.upload(site, outcome.data, with_pages=with_pages)
        invalidation = deps.site.invalidate(outcome.basket.record.run_id) if uploaded else None
        seconds["upload"] = _since(step)
        # Put back after the upload (the module's docstring, 5): a summary marks its day scored.
        deps.archive.put_covered(day, tables)
        for t in outcome.scored:
            deps.archive.put_summary(t, tables)
    finally:  # every build of every day is kept, a refused one included
        for path in sorted((work / "basket" / f"date={day.isoformat()}").glob("basket-*.json")):
            records.append(deps.archive.put_basket_record(path, now))
    seconds["total"] = _since(started)
    data = [key for key in uploaded if key in outcome.data]
    frozen = outcome.frozen
    return {"mode": "basket", "day": day.isoformat(), "run_id": outcome.basket.record.run_id,
            "headline": list(outcome.basket.headline_lines), "unchanged": outcome.basket.unchanged,
            "site_day_unchanged": outcome.unchanged, "pages": with_pages, "uploaded": data,
            "pages_uploaded": len(uploaded) - len(data), "invalidation": invalidation,
            "record": records[0] if records else None,
            "forecasts": {"status": "none", "sha256": None, "on_time": None} if frozen is None else {
                "status": frozen.status, "sha256": frozen.sha256, "on_time": frozen.on_time},
            "scored": [t.isoformat() for t in outcome.scored], "promotions_errors": dict(outcome.promotions_errors),
            "alerts": _alerts(outcome), "seconds": seconds}


def handler(event, context):
    import boto3

    cfg = Config.from_env(os.environ)
    s3 = boto3.client("s3", config=S3_CONFIG)
    deps = Deps(archive=S3Archive(s3, cfg.bucket, cfg.retention_days),
                site=S3Site(s3, boto3.client("cloudfront"), cfg.site_bucket, cfg.distribution_id),
                ping=partial(ping, user_agent=ping_user_agent(cfg.user_agent)))
    return run(cfg, event, deps, datetime.now(timezone.utc), Path(tempfile.gettempdir()))

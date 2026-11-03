"""The scheduled build's Lambda entry point: one invocation per event, as the collector's handler is. EventBridge
Scheduler sends the events each morning; the owner sends the same with a "day" to run an earlier day by hand.

    {"mode": "extract", "chain": "<slug>"}         the chain's full price files of the day into its table
    {"mode": "basket", "collected_by": "HH:MM"}    the day's record, pages and day file (not built yet)

"day" (YYYY-MM-DD) is optional in both; without it the day is the Israel calendar date when the invocation starts.
Every field is checked before anything is read. Then neither mode runs until the collector's check has written its
record for the day under `checks/date=<day>/` (MorningNotChecked): the check is the morning's last run, so its record
shows that every chain's runs are over. Each run works in a folder of its own under `tmp_root` (`/tmp` in Lambda) and
removes it when it ends, failed or not: a warm Lambda keeps `/tmp` from one invocation to the next.

The extract mode fetches the chain's price files of the day from the archive bucket into the work folder, runs
`basket.extract` over them as the Mac does, and puts the table and its report back under `tables/`, replacing an
earlier run's. Its summary, logged as one JSON line and returned, counts the files read and passed over and the
stores and rows in the table, and gives the extraction's own seconds (the fetch and the put left out).

Environment: BUCKET (the archive bucket), SITE_BUCKET (the site stack's bucket: refused unless its name starts with
SITE_BUCKET_PREFIX, so the archive bucket is never taken for it), DISTRIBUTION_ID, HEALTHCHECK_URL, USER_AGENT (each
required), RETENTION_DAYS (default 3650).
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
from zoneinfo import ZoneInfo

from basket.archive import S3Archive
from basket.chains import SLUGS
from basket.extract import extract
from basket.site import S3Site
from collector.handler import ping, ping_user_agent
from collector.http import check_user_agent
from collector.run import new_run_id
from collector.store import RETENTION_DAYS

# INFO on the package's logger itself, so the runs' summaries reach CloudWatch whatever level the runtime gives
# the root logger, as the collector's handler does for its package.
logging.getLogger("basket").setLevel(logging.INFO)
log = logging.getLogger(__name__)

REQUIRED = ("BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT")
SITE_BUCKET_PREFIX = "il-grocery-prices-site-sitebucket-"
MODES = ("extract", "basket")
ISRAEL = ZoneInfo("Asia/Jerusalem")
CLOCK = re.compile(r"^[0-2][0-9]:[0-5][0-9]$")


class MorningNotChecked(Exception):
    """The collector's check has not written its record for the day."""


@dataclass(frozen=True)
class Config:
    bucket: str
    site_bucket: str
    distribution_id: str
    healthcheck_url: str
    user_agent: str
    retention_days: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        missing = [name for name in REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ValueError(f"missing environment variables: {', '.join(missing)}")
        if not env["SITE_BUCKET"].startswith(SITE_BUCKET_PREFIX):
            raise ValueError(f"SITE_BUCKET must be the site stack's bucket, whose name starts with {SITE_BUCKET_PREFIX}, "
                             f"not {env['SITE_BUCKET']!r}")
        return cls(bucket=env["BUCKET"], site_bucket=env["SITE_BUCKET"], distribution_id=env["DISTRIBUTION_ID"],
                   healthcheck_url=env["HEALTHCHECK_URL"], user_agent=check_user_agent(env["USER_AGENT"]),
                   retention_days=int(env.get("RETENTION_DAYS", RETENTION_DAYS)))


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
    while the day has no check record, before anything is fetched. Returns a summary, also logged."""
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
    if not deps.archive.day_checked(day):
        raise MorningNotChecked(f"the collector's check has not written its record for {day}: the morning is not "
                                f"over, or the check failed (checks/date={day}/)")
    work = Path(tempfile.mkdtemp(prefix="basket-", dir=tmp_root))
    try:
        if mode == "extract":
            summary = _extract(event["chain"], day, deps, now, work)
        else:
            raise NotImplementedError("the basket mode is not built yet")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log.info(json.dumps(summary, sort_keys=True))
    return summary


def _extract(slug: str, day: date, deps: Deps, now: datetime, work: Path) -> dict:
    run_id = new_run_id(now, "extract")
    deps.archive.fetch_raw(slug, day, work / "raw")
    started = time.perf_counter()
    report = extract(work / "raw", slug, day, work / "tables")
    seconds = time.perf_counter() - started
    keys = deps.archive.put_table(slug, day, work / "tables")
    return {"mode": "extract", "chain": slug, "day": day.isoformat(), "run_id": run_id, "files": len(report.files),
            "skipped": len(report.skipped), "stores": report.stores, "rows": report.rows, "seconds": round(seconds, 1),
            "keys": keys}


def handler(event, context):  # pragma: no cover - the boto3 clients and the wall clock; run() is tested
    import boto3

    cfg = Config.from_env(os.environ)
    s3 = boto3.client("s3")
    deps = Deps(archive=S3Archive(s3, cfg.bucket, cfg.retention_days),
                site=S3Site(s3, boto3.client("cloudfront"), cfg.site_bucket, cfg.distribution_id),
                ping=partial(ping, user_agent=ping_user_agent(cfg.user_agent)))
    return run(cfg, event, deps, datetime.now(timezone.utc), Path(tempfile.gettempdir()))

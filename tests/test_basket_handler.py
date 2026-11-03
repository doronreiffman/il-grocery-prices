"""The scheduled build's Lambda entry point (`basket.handler`): the config, the event's day, the refusals before
anything is read, the check-record gate, and the extract mode.

run() is driven with a Deps over a MemoryArchive filled from test_build's golden day (`archive_from`, which the basket
mode's tests reuse), a MemorySite and a recorded ping, and a tmp_root of the test's own, so a work folder left behind
shows.
"""
import gzip
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pytest

from basket import extract as extract_module
from basket import handler as handler_module
from basket.archive import TABLE_FILES, MemoryArchive, table_key
from basket.handler import REQUIRED, SITE_BUCKET_PREFIX, Config, Deps, MorningNotChecked, event_day, run
from basket.pricefile import BadPriceFile
from basket.site import MemorySite
from collector.store import RETENTION_DAYS, check_key, raw_key
from test_build import DAY, PRICES, SLUGS, golden_tree, price_file_name
from test_extract import TABLE_COLUMNS

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)  # 11:00 in Israel, the golden day's morning
NAIVE = datetime(2026, 1, 1, 11, 0)
CHECK = check_key(DAY, "090000Z-check-0001")
UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
ENV = {"BUCKET": "il-grocery-prices-archivebucket-0123456789ab",
       "SITE_BUCKET": "il-grocery-prices-site-sitebucket-0123456789ab", "DISTRIBUTION_ID": "E0123456789ABC",
       "HEALTHCHECK_URL": "https://hc-ping.example/0000-test", "USER_AGENT": UA}
CFG = Config(bucket="il-grocery-prices-archivebucket-0123456789ab",
             site_bucket="il-grocery-prices-site-sitebucket-0123456789ab", distribution_id="E0123456789ABC",
             healthcheck_url="https://hc-ping.example/0000-test", user_agent=UA, retention_days=3650)
# The golden day's rows per chain: two stores of three codes each, less Yochananof's store 2 without EGGS, plus
# the placeholder row in Shufersal's store 1 (test_build's PRICES and PLACEHOLDER).
ROWS = {"shufersal": 7, "ramilevy": 6, "osherad": 6, "carrefour": 6, "yochananof": 5}


class RecordingArchive(MemoryArchive):
    """A MemoryArchive that records every listing and read in `reads`: ("list", prefix) and ("get", key)."""

    def __init__(self):
        super().__init__()
        self.reads = []

    def _keys(self, prefix):
        self.reads.append(("list", prefix))
        return super()._keys(prefix)

    def _get(self, key):
        self.reads.append(("get", key))
        return super()._get(key)


class Recorder:
    """A ping: records each call's arguments in `calls`."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


def archive_from(data: Path) -> MemoryArchive:
    """The archive bucket as the collector leaves it for the day under `data` (a golden_tree's data folder): every
    raw file under its raw key, every manifest under its key, and the check's record of DAY, all stored at NOW.
    Its `reads` start empty."""
    archive = RecordingArchive()
    for path in sorted((data / "raw").glob("chain=*/date=*/*")):
        slug = path.parent.parent.name.removeprefix("chain=")
        day = date.fromisoformat(path.parent.name.removeprefix("date="))
        archive.put_raw(raw_key(slug, day, path.name), path.read_bytes(), NOW)
    for path in sorted((data / "manifests").glob("date=*/*")):
        day = date.fromisoformat(path.parent.name.removeprefix("date="))
        archive.put_record(f"manifests/date={day.isoformat()}/{path.name}", path.read_bytes(), NOW)
    archive.put_record(CHECK, json.dumps({"day": DAY.isoformat(), "alerts": []}).encode(), NOW)
    archive.reads.clear()
    return archive


def deps_of(archive: MemoryArchive) -> Deps:
    return Deps(archive=archive, site=MemorySite(), ping=Recorder())


def parquet_of(body: bytes, folder: Path) -> tuple[list[tuple[str, str]], int]:
    """A Parquet file's columns (name, type) and its number of rows."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "prices.parquet"
    path.write_bytes(body)
    with duckdb.connect() as con:
        columns = [(name, kind) for name, kind, *_ in
                   con.execute("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning = false)", [str(path)]).fetchall()]
        [(rows,)] = con.execute("SELECT count(*) FROM read_parquet(?, hive_partitioning = false)", [str(path)]).fetchall()
    return columns, rows


@pytest.fixture
def data(tmp_path):
    return golden_tree(tmp_path / "golden")


@pytest.fixture
def tmp_root(tmp_path):
    root = tmp_path / "tmp"
    root.mkdir()
    return root


# ---- the config ----

def test_config_from_env_reads_the_five_and_the_retention():
    assert REQUIRED == ("BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT")
    assert Config.from_env(ENV) == CFG
    assert CFG.retention_days == RETENTION_DAYS
    assert Config.from_env(ENV | {"RETENTION_DAYS": "30"}).retention_days == 30


@pytest.mark.parametrize("site_bucket", ["il-grocery-prices-archivebucket-0123456789ab",
                                         "il-grocery-prices-site-0123456789ab",
                                         "x-il-grocery-prices-site-sitebucket-0123456789ab"])
def test_config_refuses_a_site_bucket_outside_the_prefix(site_bucket):
    with pytest.raises(ValueError, match=re.escape(SITE_BUCKET_PREFIX)):
        Config.from_env(ENV | {"SITE_BUCKET": site_bucket})
    # the prefix the hand upload refuses every other bucket by (scripts/publish.sh)
    assert SITE_BUCKET_PREFIX == "il-grocery-prices-site-sitebucket-"
    assert f"\nBUCKET_PREFIX={SITE_BUCKET_PREFIX}\n" in (ROOT / "scripts" / "publish.sh").read_text()


@pytest.mark.parametrize("name", ["BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT"])
def test_config_refuses_a_missing_variable(name):
    with pytest.raises(ValueError, match=name):
        Config.from_env({key: value for key, value in ENV.items() if key != name})
    with pytest.raises(ValueError, match=name):
        Config.from_env(ENV | {name: "  "})


@pytest.mark.parametrize("user_agent", ["il-grocery-prices/0.1 (owner@example.org)",
                                        "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices)"])
def test_config_refuses_a_user_agent_without_the_url_and_an_email(user_agent):
    with pytest.raises(ValueError, match="User-Agent"):
        Config.from_env(ENV | {"USER_AGENT": user_agent})


# ---- the event's day ----

def test_event_day_is_the_events_or_the_israel_date():
    late = datetime(2026, 11, 2, 22, 30, tzinfo=timezone.utc)  # 00:30 on 3 November in Israel
    assert event_day({"mode": "extract", "chain": "ramilevy"}, late) == date(2026, 11, 3)
    assert event_day({"mode": "extract", "chain": "ramilevy"}, late.astimezone(ZoneInfo("Asia/Jerusalem"))) == date(2026, 11, 3)
    assert event_day({"mode": "extract", "chain": "ramilevy", "day": "2026-10-30"}, late) == date(2026, 10, 30)
    # a manual run's day needs no clock; the Israel date needs a time zone
    assert event_day({"day": "2026-10-30"}, datetime(2026, 11, 2, 22, 30)) == date(2026, 10, 30)
    with pytest.raises(ValueError, match="time zone"):
        event_day({"mode": "extract", "chain": "ramilevy"}, datetime(2026, 11, 2, 22, 30))


@pytest.mark.parametrize("day", ["2026-11-31", "yesterday", "", 20261103, None])
def test_event_day_refuses_a_bad_date(day):
    with pytest.raises(ValueError, match="day"):
        event_day({"mode": "extract", "chain": "ramilevy", "day": day}, NOW)


# ---- the refusals ----

@pytest.mark.parametrize("event, now, match", [
    ({"mode": "collect", "chain": "ramilevy"}, NOW, "mode"),
    ({"chain": "ramilevy"}, NOW, "mode"),
    ("extract", NOW, "mode"),
    ({"mode": "extract"}, NOW, "chain"),
    ({"mode": "extract", "chain": "victory"}, NOW, "chain"),
    ({"mode": "basket"}, NOW, "collected_by"),
    ({"mode": "basket", "collected_by": "11:00:00"}, NOW, "collected_by"),
    ({"mode": "basket", "collected_by": "11:00\n"}, NOW, "collected_by"),
    ({"mode": "basket", "collected_by": 1100}, NOW, "collected_by"),
    ({"mode": "extract", "chain": "ramilevy"}, NAIVE, "time zone"),
    ({"mode": "extract", "chain": "ramilevy", "day": "2026-01-01"}, NAIVE, "time zone"),
    ({"mode": "basket", "collected_by": "11:00", "day": "2026-01-01"}, NAIVE, "time zone"),
    ({"mode": "extract", "chain": "ramilevy", "day": "2026-13-01"}, NOW, "day"),
])
def test_run_refuses_unknown_mode_chain_and_naive_now(data, tmp_root, event, now, match):
    """Each before anything is read: no listing, no read, no work folder."""
    archive = archive_from(data)
    deps = deps_of(archive)
    before = dict(archive.objects)
    with pytest.raises(ValueError, match=match):
        run(CFG, event, deps, now, tmp_root)
    assert archive.reads == [] and archive.objects == before
    assert list(tmp_root.iterdir()) == []
    assert deps.ping.calls == [] and deps.site.objects == {}


def test_run_refuses_a_day_without_a_check_record(data, tmp_root):
    archive = archive_from(data)
    record = archive.objects.pop(CHECK)  # the morning as it stands before the collector's check has run
    before = dict(archive.objects)
    for event in ({"mode": "extract", "chain": "ramilevy"}, {"mode": "basket", "collected_by": "11:00"}):
        with pytest.raises(MorningNotChecked, match=re.escape("for 2026-01-01: ") + ".*checks/date=2026-01-01/"):
            run(CFG, event, deps_of(archive), NOW, tmp_root)
        assert archive.objects == before  # nothing written
        assert archive.reads == [("list", "checks/date=2026-01-01/")]  # nothing fetched: the check's folder only
        assert list(tmp_root.iterdir()) == []
        archive.reads.clear()
    archive.put_record(CHECK, record.body, NOW)
    summary = run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive), NOW, tmp_root)
    assert (summary["day"], summary["rows"]) == ("2026-01-01", ROWS["ramilevy"])


# ---- the extract mode ----

@pytest.mark.parametrize("slug", SLUGS)
def test_extract_fetches_the_days_files_extracts_and_puts_the_table(data, tmp_root, tmp_path, slug):
    archive = archive_from(data)
    deps = deps_of(archive)
    summary = run(CFG, {"mode": "extract", "chain": slug}, deps, NOW, tmp_root)
    # the check's folder, then the chain's price files of the day, and nothing else of the archive
    assert archive.reads == [("list", "checks/date=2026-01-01/"), ("list", raw_key(slug, DAY, "")),
                             *[("get", raw_key(slug, DAY, price_file_name(slug, store))) for store in PRICES[slug]]]
    keys = [table_key(slug, DAY, name) for name in TABLE_FILES]
    assert summary == {"mode": "extract", "chain": slug, "day": "2026-01-01", "run_id": summary["run_id"], "files": 2,
                       "skipped": 0, "stores": 2, "rows": ROWS[slug], "seconds": summary["seconds"], "keys": keys}
    assert re.fullmatch(r"090000Z-extract-[0-9a-f]{4}", summary["run_id"])  # the run's start in UTC
    assert isinstance(summary["seconds"], float) and summary["seconds"] >= 0
    # the summary counts what the extraction's report says
    report = json.loads(archive.read_raw(keys[1]))
    assert report["files"] == [price_file_name(slug, store) for store in PRICES[slug]]
    assert (summary["files"], summary["skipped"], summary["stores"], summary["rows"]) == (
        len(report["files"]), len(report["skipped"]), report["stores"], report["rows"])
    # the table holds the day's rows, and both files went up plain, replaceable by a re-run
    assert parquet_of(archive.read_raw(keys[0]), tmp_path / "read") == (TABLE_COLUMNS, ROWS[slug])
    assert {key: archive.objects[key].lock_mode for key in archive.objects if key.startswith("tables/")} == {
        keys[0]: None, keys[1]: None}
    assert deps.ping.calls == [] and deps.site.objects == {}


def test_extract_of_a_day_with_no_files_puts_an_empty_table(tmp_path, tmp_root):
    data = golden_tree(tmp_path / "golden", PRICES | {"osherad": {}})  # the store list, and no price file
    archive = archive_from(data)
    later = datetime(2026, 1, 3, 20, 0, tzinfo=timezone.utc)  # a manual run, days on: the event's day counts
    summary = run(CFG, {"mode": "extract", "chain": "osherad", "day": "2026-01-01"}, deps_of(archive), later, tmp_root)
    assert (summary["day"], summary["files"], summary["skipped"], summary["stores"], summary["rows"]) == (
        "2026-01-01", 0, 0, 0, 0)
    assert summary["keys"] == [table_key("osherad", DAY, name) for name in TABLE_FILES]
    assert parquet_of(archive.read_raw(summary["keys"][0]), tmp_path / "read") == (TABLE_COLUMNS, 0)
    assert json.loads(archive.read_raw(summary["keys"][1]))["rows"] == 0


def test_extract_leaves_tmp_root_empty(data, tmp_root, monkeypatch):
    """The run works in a folder of its own under tmp_root and removes it, after a failure too."""
    during = []

    def extract_seen(*args):
        during.append([path.name for path in tmp_root.iterdir()])
        return extract_module.extract(*args)

    monkeypatch.setattr(handler_module, "extract", extract_seen)
    archive = archive_from(data)
    run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive), NOW, tmp_root)
    [[work]] = during
    assert work.startswith("basket-")
    assert list(tmp_root.iterdir()) == []

    unreadable = "PriceFull7290058140886-001-003-20260101-080000.gz"
    archive.put_raw(raw_key("ramilevy", DAY, unreadable), gzip.compress(b"<html></html>", mtime=0), NOW)
    with pytest.raises(BadPriceFile):
        run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive), NOW, tmp_root)
    assert len(during) == 2
    assert list(tmp_root.iterdir()) == []


# ---- logging ----

def test_the_summary_is_logged_once_as_one_json_line(data, tmp_root, caplog):
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        summary = run(CFG, {"mode": "extract", "chain": "carrefour"}, deps_of(archive_from(data)), NOW, tmp_root)
    [record] = [r for r in caplog.records if r.name == "basket.handler"]
    assert record.levelno == logging.INFO
    assert "\n" not in record.getMessage() and json.loads(record.getMessage()) == summary


def test_the_basket_package_logs_at_info():
    """Lambda's runtime may give the root logger WARNING; the summary still reaches CloudWatch."""
    assert logging.getLogger("basket").level == logging.INFO
    assert handler_module.log.getEffectiveLevel() == logging.INFO

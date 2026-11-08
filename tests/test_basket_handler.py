"""The scheduled build's Lambda entry point (`basket.handler`): the config, the event's day, the refusals before
anything is read, the check-record gate, the extract mode and the basket mode.

run() is driven with a Deps over a MemoryArchive filled from test_build's golden day (`archive_from`), a MemorySite and
a recorded ping, and a tmp_root of the test's own, so a work folder left behind shows. The basket mode's tests start
from the morning as the extractions leave it (`morning`: the golden archive with the five chains' tables), and build
with the golden day's basket and an item floor of 1, since its codes are synthetic.
"""
import gzip
import inspect
import json
import logging
import re
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pytest

from basket import build as build_module
from basket import handler as handler_module
from basket.archive import TABLE_FILES, TABLES, MemoryArchive, kind_key, record_key, table_key
from basket.basket_file import DEFAULT_BASKET
from basket.chains import CARREFOUR_COLUMNS
from basket.build import RevisionNeeded
from basket.guard import guard_days
from basket.handler import (REQUIRED, SITE_BUCKET_PREFIX, Config, Deps, MorningNotChecked, SiteCheckFailed, event_day,
                            run)
from basket.pricefile import BadPriceFile
from basket.record import code_fingerprint
from basket.rules import MissingTable
from basket.site import CACHE_CONTROL, HTML, JSON, MemorySite
from basket.stores import NoStoreList
from collector.store import LOCK_MODE, RETENTION_DAYS, check_key, raw_key
from shopper import extract as shop_extract
from test_build import BASKET, DAY, MILK, PRICES, SLUGS, golden_tree, price_file_name, reprice, store_list
from test_extract import TABLE_COLUMNS
from test_shop_extract import COLUMN, GOLDEN_COLUMNS, on, promo_file, promo_file_name, read, with_promotions

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)  # 11:00 in Israel, the golden day's morning
RUN_AT = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)  # 11:30 in Israel, the basket run's time
AGAIN = datetime(2026, 1, 1, 9, 45, tzinfo=timezone.utc)  # a second basket run the same morning
NAIVE = datetime(2026, 1, 1, 11, 0)
CHECK = check_key(DAY, "090000Z-check-0001")
UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
ENV = {"BUCKET": "il-grocery-prices-archivebucket-0123456789ab",
       "SITE_BUCKET": "il-grocery-prices-site-sitebucket-0123456789ab", "DISTRIBUTION_ID": "E0123456789ABC",
       "HEALTHCHECK_URL": "https://hc-ping.example/0000-test", "USER_AGENT": UA}
CFG = Config(bucket="il-grocery-prices-archivebucket-0123456789ab",
             site_bucket="il-grocery-prices-site-sitebucket-0123456789ab", distribution_id="E0123456789ABC",
             healthcheck_url="https://hc-ping.example/0000-test", user_agent=UA, retention_days=3650)
URL = CFG.healthcheck_url
BASKET_EVENT = {"mode": "basket", "collected_by": "11:00"}
PUBLISHED = ["index.html", "method.html", "days/2026-01-01.json"]
HEADLINE = ["Lowest listed total today: Osher Ad, ₪22.65.",
            "Highest: Carrefour, ₪27.16, 20% more. 3 everyday items, listed shelf prices before promotions, from the "
            "chains' price files of Thursday 1 January 2026."]  # the golden day's two lines (test_build)
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
    """A ping: records each call's arguments in `calls`, and what `watch()` gives at each call in `seen` when given;
    raises `raises` when given."""

    def __init__(self, raises=None, watch=None):
        self.calls, self.seen = [], []
        self.raises, self.watch = raises, watch

    def __call__(self, *args):
        self.calls.append(args)
        if self.watch is not None:
            self.seen.append(self.watch())
        if self.raises is not None:
            raise self.raises


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


def test_config_reads_duckdbs_temp_folder_as_basket_duck_does():
    """The folder the run sweeps is the one `basket.duck` gives DuckDB: the same variable, read without the spaces
    around it, and none when unset or blank."""
    assert CFG.duckdb_temp_directory is None
    assert Config.from_env(ENV | {"DUCKDB_TEMP_DIRECTORY": " /tmp/duckdb "}).duckdb_temp_directory == Path("/tmp/duckdb")
    assert Config.from_env(ENV | {"DUCKDB_TEMP_DIRECTORY": "  "}).duckdb_temp_directory is None


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
    # the extract mode never pings; the basket mode pings /start, then /fail for the refusal
    for event, pings in (({"mode": "extract", "chain": "ramilevy"}, []),
                         ({"mode": "basket", "collected_by": "11:00"}, [f"{URL}/start", f"{URL}/fail"])):
        deps = deps_of(archive)
        with pytest.raises(MorningNotChecked, match=re.escape("for 2026-01-01: ") + ".*checks/date=2026-01-01/"):
            run(CFG, event, deps, NOW, tmp_root)
        assert archive.objects == before  # nothing written
        assert archive.reads == [("list", "checks/date=2026-01-01/")]  # nothing fetched: the check's folder only
        assert list(tmp_root.iterdir()) == []
        assert [url for url, _ in deps.ping.calls] == pings and deps.site.objects == {}
        archive.reads.clear()
    archive.put_record(CHECK, record.body, NOW)
    summary = run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive), NOW, tmp_root)
    assert (summary["day"], summary["rows"]) == ("2026-01-01", ROWS["ramilevy"])


# ---- the extract mode ----

def every_key(slug: str) -> list[str]:
    """The keys of the chain's three tables of the day, in the order `put_tables` puts them."""
    return [kind_key(kind, slug, DAY, name) for kind, names in TABLES.items() for name in names]


@pytest.fixture
def golden_columns(monkeypatch):
    """The golden day's Carrefour stores placed by its own table, never the hand-kept one (S18)."""
    monkeypatch.setattr(handler_module, "CARREFOUR_TABLE", GOLDEN_COLUMNS)


@pytest.mark.parametrize("slug", SLUGS)
def test_extract_fetches_the_days_files_extracts_and_puts_the_table(tmp_path, tmp_root, golden_columns, slug):
    data = with_promotions(golden_tree(tmp_path / "golden"))
    archive = archive_from(data)
    deps = deps_of(archive)
    summary = run(CFG, {"mode": "extract", "chain": slug}, deps, NOW, tmp_root)
    # the check's folder; the chain's price and promotion files of the day, from one listing; its store list; and
    # nothing else of the archive
    files = sorted([price_file_name(slug, store) for store in PRICES[slug]]
                   + [promo_file_name(slug, store) for store in PRICES[slug]])
    assert archive.reads == [("list", "checks/date=2026-01-01/"), ("list", raw_key(slug, DAY, "")),
                             *[("get", raw_key(slug, DAY, name)) for name in files],
                             ("list", raw_key(slug, DAY, "")), ("get", raw_key(slug, DAY, store_list(slug)[0]))]
    keys = every_key(slug)
    assert summary == {"mode": "extract", "chain": slug, "day": "2026-01-01", "run_id": summary["run_id"], "files": 2,
                       "skipped": 0, "stores": 2, "rows": ROWS[slug], "unreadable_prices": 0,
                       "seconds": summary["seconds"], "keys": keys, "promotions": summary["promotions"],
                       "promotions_error": None, "columns": summary["columns"],
                       "promotion_seconds": summary["promotion_seconds"], "items_seconds": summary["items_seconds"]}
    assert re.fullmatch(r"090000Z-extract-[0-9a-f]{4}", summary["run_id"])  # the run's start in UTC
    for name in ("seconds", "promotion_seconds", "items_seconds"):
        assert isinstance(summary[name], float) and summary[name] >= 0
    # the summary counts what the extraction's report says
    report = json.loads(archive.read_raw(keys[1]))
    assert report["files"] == [price_file_name(slug, store) for store in PRICES[slug]]
    assert (summary["files"], summary["skipped"], summary["stores"], summary["rows"], summary["unreadable_prices"]) == (
        len(report["files"]), len(report["skipped"]), report["stores"], report["rows"], report["unreadable_prices"])
    # the prices table holds the day's rows, and every file went up plain, replaceable by a re-run
    assert parquet_of(archive.read_raw(keys[0]), tmp_path / "read") == (TABLE_COLUMNS, ROWS[slug])
    assert {key: archive.objects[key].lock_mode for key in archive.objects if key.startswith("tables/")} == {
        key: None for key in keys}
    assert deps.ping.calls == [] and deps.site.objects == {}


@pytest.mark.parametrize("slug", SLUGS)
def test_extract_puts_the_three_tables_and_reports_them(tmp_path, tmp_root, golden_columns, slug):
    """The promotions, texts and items tables go up beside the prices table, and the summary gives what their
    reports say: the promotions' counts, no error, and each column's items, wide items and holes."""
    data = with_promotions(golden_tree(tmp_path / "golden"))
    archive = archive_from(data)
    summary = run(CFG, {"mode": "extract", "chain": slug}, deps_of(archive), NOW, tmp_root)
    got = tmp_path / "got"
    for key in every_key(slug):   # the keys are the local paths under a folder named tables
        (got / key).parent.mkdir(parents=True, exist_ok=True)
        (got / key).write_bytes(archive.read_raw(key))
    tables = got / "tables"
    column = COLUMN[slug]
    assert [(row["column"], row["promotion_id"], row["code"], row["wide"]) for row in read(
        tables / "promotions" / f"chain={slug}" / "date=2026-01-01" / "promotions.parquet", "code")] == [
        (column, "1", MILK, True)]
    assert [row["promotion_id"] for row in read(
        tables / "promotions" / f"chain={slug}" / "date=2026-01-01" / "texts.parquet", "promotion_id")] == ["1"]
    items = read(tables / "items" / f"chain={slug}" / "date=2026-01-01" / "items.parquet", "code")
    assert [(row["column"], row["code"], row["on_promotion"]) for row in items if row["code"] == MILK] == [
        (column, MILK, True)]
    promotions = json.loads((tables / "promotions" / f"chain={slug}" / "date=2026-01-01" / "report.json").read_text())
    assert summary["promotions"] == {"files": len(promotions["files"]), "passed_over": len(promotions["passed_over"]),
                                     "outside": len(promotions["outside"]), **{
        name: promotions[name] for name in ("promotions", "coupons", "gifts", "basket_rewards", "dropped_links",
                                            "expired", "before_start", "rows")}}
    report = json.loads((tables / "items" / f"chain={slug}" / "date=2026-01-01" / "report.json").read_text())
    assert summary["columns"] == {key: {name: one[name] for name in ("items", "wide", "hole", "promo_hole")}
                                  for key, one in report["columns"].items()}
    assert summary["columns"][column] == {"items": 3, "wide": 3, "hole": False, "promo_hole": False}
    assert summary["promotions_error"] is None and report["promotions_error"] is None


def test_the_extract_summary_names_a_promotions_error(tmp_path, tmp_root):
    """A promotion format change at one store: the run succeeds; the summary names the chain, the field and its
    value; no promotions or texts table goes up, the promotions folder's report alone; the items table goes up with
    every column a promotion hole."""
    data = with_promotions(golden_tree(tmp_path / "golden"))
    name = promo_file_name("ramilevy", "002")
    (data / "raw" / "chain=ramilevy" / "date=2026-01-01" / name).write_bytes(
        promo_file("ramilevy", "002", on(MILK, reward="99")))
    archive = archive_from(data)
    summary = run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive), NOW, tmp_root)
    error = "ramilevy: RewardType 99 not seen in the chain's files"
    assert (summary["promotions_error"], summary["promotions"]) == (error, None)
    assert summary["columns"] == {"ramilevy": {"items": 3, "wide": 3, "hole": False, "promo_hole": True}}
    assert summary["keys"] == [*[table_key("ramilevy", DAY, name) for name in TABLE_FILES],
                               kind_key("promotions", "ramilevy", DAY, "report.json"),
                               *[kind_key("items", "ramilevy", DAY, name) for name in TABLES["items"]]]
    assert sorted(key for key in archive.objects if key.startswith("tables/")) == sorted(summary["keys"])
    assert json.loads(archive.read_raw(kind_key("promotions", "ramilevy", DAY, "report.json"))) == {
        "slug": "ramilevy", "day": "2026-01-01", "promotions_error": error}
    assert json.loads(archive.read_raw(kind_key("items", "ramilevy", DAY, "report.json")))["promotions_error"] == error


@pytest.mark.parametrize("stop", ["no store list", "a shopper step's failure"])
def test_a_chain_stopped_after_its_prices_keeps_its_prices_table(tmp_path, tmp_root, monkeypatch, stop):
    """Whatever stops the run after the prices table was written, what was written goes up before the error is
    raised: a chain with no store list keeps its prices table in the archive, as before the shopper's steps (the basket
    run then refuses it as NoStoreList), and a failure in those steps never takes the basket's prices table away."""
    data = with_promotions(golden_tree(tmp_path / "golden"))
    if stop == "no store list":
        (data / "raw" / "chain=osherad" / "date=2026-01-01" / store_list("osherad")[0]).unlink()
        raised = NoStoreList
        written = [table_key("osherad", DAY, name) for name in TABLE_FILES]
    else:
        def failing(*args, **kwargs):
            raise RuntimeError("the items table could not be written")
        monkeypatch.setattr(shop_extract, "write_items", failing)
        raised = RuntimeError   # the texts table is the items step's, so it is not there
        written = [*[table_key("osherad", DAY, name) for name in TABLE_FILES],
                   *[kind_key("promotions", "osherad", DAY, name) for name in ("promotions.parquet", "report.json")]]
    archive = archive_from(data)
    with pytest.raises(raised):
        run(CFG, {"mode": "extract", "chain": "osherad"}, deps_of(archive), NOW, tmp_root)
    assert sorted(key for key in archive.objects if key.startswith("tables/")) == sorted(written)
    assert list(tmp_root.iterdir()) == []


def test_the_extract_places_carrefours_stores_by_the_hand_kept_table():
    assert handler_module.CARREFOUR_TABLE is CARREFOUR_COLUMNS


def test_extract_of_a_day_with_no_files_puts_an_empty_table(tmp_path, tmp_root):
    data = golden_tree(tmp_path / "golden", PRICES | {"osherad": {}})  # the store list, and no price file
    archive = archive_from(data)
    later = datetime(2026, 1, 3, 20, 0, tzinfo=timezone.utc)  # a manual run, days on: the event's day counts
    summary = run(CFG, {"mode": "extract", "chain": "osherad", "day": "2026-01-01"}, deps_of(archive), later, tmp_root)
    assert (summary["day"], summary["files"], summary["skipped"], summary["stores"], summary["rows"]) == (
        "2026-01-01", 0, 0, 0, 0)
    assert summary["keys"] == every_key("osherad")  # every table, of no rows
    assert summary["columns"] == {"osherad": {"items": 0, "wide": 0, "hole": True, "promo_hole": False}}
    assert parquet_of(archive.read_raw(summary["keys"][0]), tmp_path / "read") == (TABLE_COLUMNS, 0)
    assert json.loads(archive.read_raw(summary["keys"][1]))["rows"] == 0


def test_the_extract_summary_counts_the_unreadable_prices(data, tmp_root):
    """The rows whose price could not be read are in the table with no price; the summary says how many, as the
    extraction's report and the basket record do, so the log shows them without opening the report."""
    reprice(data, "ramilevy", "001", ("not a price", "4.90", "11.90"))
    summary = run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive_from(data)), NOW, tmp_root)
    assert (summary["rows"], summary["unreadable_prices"]) == (ROWS["ramilevy"], 1)


def test_extract_leaves_tmp_root_empty(data, tmp_root, monkeypatch):
    """The run works in a folder of its own under tmp_root and removes it, after a failure too."""
    during = []

    def extract_seen(*args, **kwargs):
        during.append([path.name for path in tmp_root.iterdir()])
        return shop_extract.extract_chain_day(*args, **kwargs)

    monkeypatch.setattr(handler_module, "extract_chain_day", extract_seen)
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


def test_a_stale_work_folder_from_an_earlier_run_is_gone_after_this_one(data, tmp_root, caplog):
    """A run Lambda killed at its timeout never reached its `finally`, and a warm Lambda keeps /tmp: the next run in
    that environment removes the folder it left. Only `basket-*` folders: anything else under tmp_root stays."""
    stale = tmp_root / "basket-stale"
    (stale / "tables").mkdir(parents=True)
    (stale / "tables" / "rows.csv").write_bytes(b"store,code\n")
    other = tmp_root / "other"
    other.mkdir()
    (other / "kept.txt").write_text("kept")
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        run(CFG, {"mode": "extract", "chain": "ramilevy"}, deps_of(archive_from(data)), NOW, tmp_root)
    assert [path.name for path in tmp_root.iterdir()] == ["other"]
    assert (other / "kept.txt").read_text() == "kept"
    messages = [r.getMessage() for r in caplog.records if r.name == "basket.handler" and r.levelno == logging.INFO]
    assert messages[0] == f"removed the work folders earlier runs left under {tmp_root}: 1"
    assert len(messages) == 2  # the sweep's line, then the summary


def test_what_duckdb_left_in_its_temp_folder_is_gone_before_the_run(data, tmp_root, monkeypatch, caplog):
    """DuckDB spills to its temp folder above its memory limit and removes the files when it closes; a run Lambda
    killed mid-spill leaves them, and a warm Lambda keeps /tmp. The next run removes the folder before it starts
    (`basket.duck` makes it again) and says how many entries it held; an empty or missing folder passes unremarked."""
    spill = tmp_root / "duckdb"
    (spill / "nested").mkdir(parents=True)
    (spill / "duckdb_temp_storage-0.tmp").write_bytes(b"spilled")
    (spill / "nested" / "more.tmp").write_bytes(b"spilled")
    seen = []

    def extract_seen(*args, **kwargs):
        seen.append(spill.exists())
        return shop_extract.extract_chain_day(*args, **kwargs)

    monkeypatch.setattr(handler_module, "extract_chain_day", extract_seen)
    cfg = replace(CFG, duckdb_temp_directory=spill)
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        run(cfg, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
    assert seen == [False] and not spill.exists()
    messages = [r.getMessage() for r in caplog.records if r.name == "basket.handler" and r.levelno == logging.INFO]
    assert messages[0] == f"removed what earlier runs left in DuckDB's temp folder {spill}: 2"
    assert len(messages) == 2  # the sweep's line, then the summary

    caplog.clear()
    spill.mkdir()  # as basket.duck leaves it after a run that did not spill
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        run(cfg, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
        spill.rmdir()
        run(cfg, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
    assert [r.levelno for r in caplog.records if r.name == "basket.handler"] == [logging.INFO, logging.INFO]


@pytest.mark.parametrize("where", ["elsewhere", "tmp_root", "a link"])
def test_a_duckdb_folder_not_its_own_under_tmp_root_is_left_alone(data, tmp_root, tmp_path, caplog, where):
    """The setting names the folder the sweep removes, so a wrong one must not empty /tmp or anything outside it:
    a folder outside `tmp_root`, `tmp_root` itself or a link is left as it is, with a warning, and the run goes on."""
    if where == "elsewhere":
        spill = tmp_path / "elsewhere"
        spill.mkdir()
        kept = spill / "kept.tmp"
    elif where == "tmp_root":
        spill, kept = tmp_root, tmp_root / "kept.tmp"
    else:
        (tmp_root / "real").mkdir()
        kept = tmp_root / "real" / "kept.tmp"
        spill = tmp_root / "duckdb"
        spill.symlink_to(tmp_root / "real", target_is_directory=True)
    kept.write_bytes(b"kept")
    cfg = replace(CFG, duckdb_temp_directory=spill)
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        summary = run(cfg, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
    assert summary["rows"] == ROWS["osherad"]
    assert kept.read_bytes() == b"kept" and spill.exists()
    warnings = [r.getMessage() for r in caplog.records if r.name == "basket.handler" and r.levelno == logging.WARNING]
    assert warnings == [f"DuckDB's temp folder {spill} is not a folder of its own under {tmp_root}: left as it is"]


def test_a_duckdb_folder_that_cannot_be_read_is_logged_and_the_run_stands(data, tmp_root, caplog):
    """A folder whose entries cannot be listed is left as it is, with a warning naming it, and the run goes on, as
    a failed removal does."""
    spill = tmp_root / "duckdb"
    spill.mkdir()
    (spill / "spilled.tmp").write_bytes(b"spilled")
    spill.chmod(0o000)  # its entries cannot be listed
    cfg = replace(CFG, duckdb_temp_directory=spill)
    try:
        with caplog.at_level(logging.INFO, logger="basket.handler"):
            summary = run(cfg, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
    finally:
        spill.chmod(0o700)
    assert summary["rows"] == ROWS["osherad"]
    assert (spill / "spilled.tmp").exists()
    [warning] = [r.getMessage() for r in caplog.records if r.name == "basket.handler" and r.levelno == logging.WARNING]
    assert warning.startswith(f"could not read DuckDB's temp folder {spill}: PermissionError: ")


def test_a_folder_the_run_cannot_remove_is_logged_and_the_run_stands(data, tmp_root, monkeypatch, caplog):
    """A removal that fails leaves what it could not remove and logs a warning naming it, rather than passing in
    silence; the run's outcome stands. The next run's sweep tries again."""
    locked = []

    def extract_locking(raw, slug, day, tables, **kwargs):
        report = shop_extract.extract_chain_day(raw, slug, day, tables, **kwargs)
        folder = tables.parent / "locked"
        folder.mkdir()
        (folder / "kept.txt").write_text("kept")
        folder.chmod(0o500)  # its entries cannot be removed
        locked.append(folder)
        return report

    monkeypatch.setattr(handler_module, "extract_chain_day", extract_locking)
    try:
        with caplog.at_level(logging.INFO, logger="basket.handler"):
            summary = run(CFG, {"mode": "extract", "chain": "osherad"}, deps_of(archive_from(data)), NOW, tmp_root)
    finally:
        for folder in locked:
            folder.chmod(0o700)
    assert summary["rows"] == ROWS["osherad"]
    [folder] = locked
    warnings = [r.getMessage() for r in caplog.records if r.name == "basket.handler" and r.levelno == logging.WARNING]
    assert warnings and all(message.startswith("could not remove ") for message in warnings)
    assert warnings[0].startswith(f"could not remove {folder / 'kept.txt'}: PermissionError: ")
    assert (folder / "kept.txt").exists()
    assert json.loads([r.getMessage() for r in caplog.records if r.levelno == logging.INFO][-1]) == summary


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


# ---- the basket mode ----

def extracted(archive: MemoryArchive, tmp_root: Path, chains=SLUGS) -> MemoryArchive:
    """The archive after the extract mode has run for each of `chains`, as the morning's schedules run it; its
    `reads` cleared."""
    for slug in chains:
        run(CFG, {"mode": "extract", "chain": slug}, deps_of(archive), NOW, tmp_root)
    archive.reads.clear()
    return archive


@pytest.fixture
def golden_basket(monkeypatch):
    """The golden day's basket and an item floor of 1 in place of v1's and its 25: the golden codes are synthetic."""
    monkeypatch.setattr(handler_module, "BASKET_FILE", BASKET)
    monkeypatch.setattr(handler_module, "MIN_ITEMS", 1)


@pytest.fixture
def morning(data, tmp_root, golden_basket):
    """The archive as the basket run finds it: the golden day, its check record and the five chains' tables."""
    return extracted(archive_from(data), tmp_root)


def records_of(archive: MemoryArchive) -> list[str]:
    return sorted(key for key in archive.objects if key.startswith("basket/"))


def pinged(deps: Deps) -> list[str]:
    return [url for url, _ in deps.ping.calls]


def test_first_run_publishes_the_day_and_pings(morning, tmp_root):
    deps = deps_of(morning)
    summary = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    run_id = summary["run_id"]
    assert re.fullmatch(r"093000Z-basket-[0-9a-f]{4}", run_id)  # the run's start in UTC
    assert summary == {"mode": "basket", "day": "2026-01-01", "run_id": run_id, "headline": HEADLINE,
                       "unchanged": False, "pages": True, "uploaded": PUBLISHED, "invalidation": "memory-1",
                       "record": record_key(DAY, run_id)}
    assert sorted(deps.site.objects) == sorted(PUBLISHED)
    assert deps.site.invalidations == [run_id]  # one invalidation, under the run's id
    # the record, write-once and locked, the only one
    assert records_of(morning) == [record_key(DAY, run_id)]
    stored = morning.objects[record_key(DAY, run_id)]
    assert stored.lock_mode == LOCK_MODE and json.loads(stored.body)["run_id"] == run_id
    # /start, then the plain URL with the summary
    assert pinged(deps) == [f"{URL}/start", URL]
    assert deps.ping.calls[0][1] == "" and json.loads(deps.ping.calls[1][1]) == summary
    public = json.loads(deps.site.objects["days/2026-01-01.json"][0])
    assert public["collected_by"] == "11:00"  # the event's, not the run's 11:30
    assert public["code_sha"] == code_fingerprint() and public["run_id"] == run_id
    assert list(tmp_root.iterdir()) == []


def test_unchanged_day_uploads_pages_not_the_day_file(morning, tmp_root):
    deps = deps_of(morning)
    first = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    published = deps.site.objects["days/2026-01-01.json"]
    second = run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert (second["unchanged"], second["pages"], second["uploaded"]) == (True, True, ["index.html", "method.html"])
    assert second["headline"] == HEADLINE
    assert deps.site.objects["days/2026-01-01.json"] == published  # the day file as first published
    assert deps.site.invalidations == [first["run_id"], second["run_id"]]
    assert records_of(morning) == sorted([first["record"], second["record"]])  # every build of the day is kept
    assert first["record"] != second["record"]


def test_an_earlier_day_than_the_sites_latest_uploads_its_day_file_not_the_pages(morning, tmp_root):
    deps = deps_of(morning)
    later = {"days/2026-01-02.json": (b'{"day": "2026-01-02"}', JSON, CACHE_CONTROL),
             "index.html": (b"<p>2 January</p>", HTML, CACHE_CONTROL),
             "method.html": (b"<p>the method, 2 January</p>", HTML, CACHE_CONTROL)}
    deps.site.objects.update(later)
    summary = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    assert (summary["unchanged"], summary["pages"], summary["uploaded"]) == (False, False, ["days/2026-01-01.json"])
    assert deps.site.invalidations == [summary["run_id"]]
    assert {key: deps.site.objects[key] for key in later} == later  # the front page stays the later day's
    assert sorted(deps.site.objects) == sorted([*later, "days/2026-01-01.json"])


def test_an_earlier_day_already_published_and_unchanged_uploads_nothing_and_does_not_invalidate(morning, tmp_root):
    deps = deps_of(morning)
    first = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    deps.site.objects["days/2026-01-02.json"] = (b'{"day": "2026-01-02"}', JSON, CACHE_CONTROL)
    site = dict(deps.site.objects)
    deps.ping.calls.clear()
    second = run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert (second["unchanged"], second["pages"], second["uploaded"], second["invalidation"]) == (True, False, [], None)
    assert deps.site.objects == site and deps.site.invalidations == [first["run_id"]]
    assert records_of(morning) == sorted([first["record"], second["record"]])
    assert pinged(deps) == [f"{URL}/start", URL] and json.loads(deps.ping.calls[1][1]) == second


def test_differing_numbers_fail_loudly_and_publish_nothing(data, morning, tmp_root):
    deps = deps_of(morning)
    first = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    site = dict(deps.site.objects)
    # Yochananof's store 1 publishes again under the same name, its milk 6.60 -> 6.63: the archive keeps the new
    # file beside the first, as the collector does, and the chain's extraction runs again
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))
    name = price_file_name("yochananof", "001")
    body = (data / "raw" / "chain=yochananof" / f"date={DAY.isoformat()}" / name).read_bytes()
    morning.put_raw(raw_key("yochananof", DAY, name), body, NOW)
    extracted(morning, tmp_root, ["yochananof"])
    deps.ping.calls.clear()
    with pytest.raises(RevisionNeeded, match=re.escape("chains.yochananof.total")) as raised:
        run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert deps.site.objects == site and deps.site.invalidations == [first["run_id"]]  # nothing went up
    [second] = [key for key in records_of(morning) if key != first["record"]]  # the refused run's record, all the same
    assert morning.objects[second].lock_mode == LOCK_MODE
    assert pinged(deps) == [f"{URL}/start", f"{URL}/fail"]
    body = deps.ping.calls[1][1]
    assert body == f"RevisionNeeded: {raised.value}" and "chains.yochananof.total" in body
    assert list(tmp_root.iterdir()) == []


def test_missing_table_names_the_chain_uploads_nothing_and_pings_fail(morning, tmp_root):
    for name in TABLE_FILES:  # Osher Ad's extraction did not run
        del morning.objects[table_key("osherad", DAY, name)]
    deps = deps_of(morning)
    with pytest.raises(MissingTable) as raised:
        run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    message = str(raised.value)
    assert "'osherad'" in message and table_key("osherad", DAY, "prices.parquet") in message
    assert "2026-01-01" in message
    assert deps.site.objects == {} and deps.site.invalidations == []
    assert records_of(morning) == []  # stopped before the build: no record
    assert pinged(deps) == [f"{URL}/start", f"{URL}/fail"]
    assert deps.ping.calls[1][1] == f"MissingTable: {message}"
    assert list(tmp_root.iterdir()) == []


def test_a_chain_with_no_files_publishes_with_the_chain_out_of_the_ranking(data, tmp_root, golden_basket):
    archive = archive_from(data)
    for store in PRICES["osherad"]:  # Osher Ad's store list came, and no price file
        del archive.objects[raw_key("osherad", DAY, price_file_name("osherad", store))]
    extracted(archive, tmp_root)
    deps = deps_of(archive)
    summary = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    assert summary["uploaded"] == PUBLISHED
    osherad = json.loads(deps.site.objects["days/2026-01-01.json"][0])["chains"]["osherad"]
    assert (osherad["included"], osherad["with_file"], osherad["in_ranking"]) == (2, 0, False)
    assert summary["headline"][0] == "Lowest listed total today: Rami Levy, ₪23.30."
    assert pinged(deps) == [f"{URL}/start", URL]


def test_site_check_failure_uploads_nothing(morning, tmp_root, monkeypatch):
    checked = []

    def check_site(site_dir):
        checked.append(sorted(path.name for path in site_dir.iterdir()))
        return ["index.html: x"]

    monkeypatch.setattr(handler_module, "check_site", check_site)
    deps = deps_of(morning)
    with pytest.raises(SiteCheckFailed) as raised:
        run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    assert str(raised.value) == "the site check failed:\nindex.html: x"
    assert checked == [[".basket-site", "days", "index.html", "method.html"]]  # the built site
    assert deps.site.objects == {} and deps.site.invalidations == []
    assert len(records_of(morning)) == 1  # the record went up all the same
    assert pinged(deps) == [f"{URL}/start", f"{URL}/fail"]
    assert deps.ping.calls[1][1] == "SiteCheckFailed: the site check failed:\nindex.html: x"


def test_guard_failure_uploads_nothing(morning, tmp_root, monkeypatch):
    """The guard is given the built day file and the site's published copy; the first run's guard is the real one,
    the second's finds a problem, in a text of Hebrew letters (two bytes each in UTF-8) too long for the ping."""
    seen = []

    def guard(local_days, published_days):
        seen.append({name: {path.name: path.read_bytes() for path in folder.iterdir()}
                     for name, folder in (("local", local_days), ("published", published_days))})
        return guard_days(local_days, published_days) if len(seen) == 1 else ["days/2026-01-01.json: " + "א" * 200_000]

    monkeypatch.setattr(handler_module, "guard_days", guard)
    deps = deps_of(morning)
    first = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    published = deps.site.objects["days/2026-01-01.json"][0]
    assert seen == [{"local": {"2026-01-01.json": published}, "published": {}}]  # nothing published yet
    site = dict(deps.site.objects)
    deps.ping.calls.clear()
    with pytest.raises(SiteCheckFailed) as raised:
        run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert str(raised.value).startswith("the published-day guard failed:\ndays/2026-01-01.json: אאא")
    assert seen[1] == {"local": {"2026-01-01.json": published}, "published": {"2026-01-01.json": published}}
    assert deps.site.objects == site and deps.site.invalidations == [first["run_id"]]
    assert len(records_of(morning)) == 2
    assert pinged(deps) == [f"{URL}/start", f"{URL}/fail"]
    body = deps.ping.calls[1][1]
    # cut to healthchecks.io's 100 kB by bytes, the ASCII head's 71 leaving an odd count for the two-byte letters: the
    # half letter at the cut is dropped, never sent broken
    assert body.startswith("SiteCheckFailed: the published-day guard failed:\n")
    assert f"SiteCheckFailed: {raised.value}".startswith(body) and len(body.encode()) == 99_999


def test_collected_by_is_required_and_a_clock(morning, tmp_root):
    deps = deps_of(morning)
    for event in ({"mode": "basket"}, {"mode": "basket", "collected_by": "11:00:00"}):
        with pytest.raises(ValueError, match="collected_by"):
            run(CFG, event, deps, RUN_AT, tmp_root)
    assert morning.reads == []  # checked before any fetch, the check record's included
    assert deps.ping.calls == [] and deps.site.objects == {} and list(tmp_root.iterdir()) == []


def test_a_day_without_a_check_record_pings_fail(morning, tmp_root):
    morning.objects.pop(CHECK)
    deps = Deps(archive=morning, site=MemorySite(), ping=Recorder(watch=lambda: list(morning.reads)))
    with pytest.raises(MorningNotChecked) as raised:
        run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    assert deps.ping.calls == [(f"{URL}/start", ""), (f"{URL}/fail", f"MorningNotChecked: {raised.value}")]
    gate = ("list", "checks/date=2026-01-01/")
    assert deps.ping.seen == [[], [gate]]  # /start before the gate, /fail after it
    assert morning.reads == [gate] and records_of(morning) == []
    assert deps.site.objects == {} and list(tmp_root.iterdir()) == []


def test_a_failing_ping_is_logged_not_raised(morning, tmp_root, caplog):
    """Each failed ping is logged by its kind; the ping URL is a secret, and no part of it reaches the log, though the
    error's own text quotes it."""
    error = OSError(f"{URL}/start: no answer from hc-ping.example for check 0000-test")
    deps = Deps(archive=morning, site=MemorySite(), ping=Recorder(raises=error))
    hidden = "OSError: <hidden>/start: no answer from <hidden> for check <hidden>"
    with caplog.at_level(logging.INFO, logger="basket.handler"):
        summary = run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    assert summary["uploaded"] == PUBLISHED and sorted(deps.site.objects) == sorted(PUBLISHED)
    assert pinged(deps) == [f"{URL}/start", URL]
    warnings = [(r.levelno, r.getMessage()) for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [(logging.WARNING, f"the start ping to healthchecks.io failed: {hidden}"),
                        (logging.WARNING, f"the success ping to healthchecks.io failed: {hidden}")]
    # a failing /fail ping leaves the run's own error to be raised
    for name in TABLE_FILES:
        del morning.objects[table_key("osherad", DAY, name)]
    with caplog.at_level(logging.INFO, logger="basket.handler"), pytest.raises(MissingTable):
        run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING][2:] == [
        f"the start ping to healthchecks.io failed: {hidden}", f"the fail ping to healthchecks.io failed: {hidden}"]
    for part in ("0000-test", "hc-ping.example", URL):  # the check's id, the host, the URL: none is logged
        assert part not in caplog.text


def test_work_folder_is_removed_after_success_and_after_failure(morning, tmp_root, monkeypatch):
    during = []

    def build_seen(*args, **kwargs):
        during.append([path.name for path in tmp_root.iterdir()])
        return build_module.build_day(*args, **kwargs)

    monkeypatch.setattr(handler_module, "build_day", build_seen)
    deps = Deps(archive=morning, site=MemorySite(),
                ping=Recorder(watch=lambda: [path.name for path in tmp_root.iterdir()]))
    run(CFG, BASKET_EVENT, deps, RUN_AT, tmp_root)
    [[work]] = during
    assert work.startswith("basket-")
    assert deps.ping.seen == [[], [work]]  # the success ping goes out before the work folder is removed
    assert list(tmp_root.iterdir()) == []

    monkeypatch.setattr(handler_module, "check_site", lambda site_dir: ["index.html: x"])
    with pytest.raises(SiteCheckFailed):
        run(CFG, BASKET_EVENT, deps, AGAIN, tmp_root)
    assert len(during) == 2 and during[1][0].startswith("basket-")
    assert list(tmp_root.iterdir()) == []


def test_the_scheduled_run_builds_the_approved_basket_at_the_hand_builds_floor():
    """The two constants the basket mode's tests replace hold the approved basket and the hand build's item floor."""
    assert handler_module.BASKET_FILE == DEFAULT_BASKET
    assert handler_module.MIN_ITEMS == 25 == inspect.signature(build_module.build_day).parameters["min_items"].default


def test_the_scheduled_run_never_revises():
    """A day whose numbers differ stops the scheduled run; only a hand build revises, with a reason."""
    source = inspect.getsource(handler_module)
    assert re.findall(r"\brevise\s*=\s*[^,)\s]+", source) == ["revise=None"]
    assert "--revise" not in source

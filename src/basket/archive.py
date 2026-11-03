"""The archive bucket's side of the scheduled build: the day's files fetched into the folders the Mac's
build reads, and the build's results put back.

The scheduled build runs `basket.extract` and `basket.build` over a work folder laid out as the Mac's
synced `data/`:

    <raw dir>/chain=<slug>/date=<day>/<stored name>     the raw files, named as stored
    <manifests dir>/date=<day>/<slug>-<run id>.json     the chain's manifests of the day
    <tables dir>/prices/chain=<slug>/date=<day>/        prices.parquet and report.json

and puts back, beside the collector's keys:

    tables/prices/chain=<slug>/date=<day>/prices.parquet   plain; each extraction run replaces it
    tables/prices/chain=<slug>/date=<day>/report.json      plain, the same
    basket/date=<day>/basket-<run id>.json                 the run's record, write-once and locked

A table is derived and a re-run replaces it, so it goes up plain. A record is one run's own and never
changes, so it goes up as a manifest does (`_Store.put_record`): write-once, under a ten-year governance
lock; the same bytes again are the same put retried, other bytes under its key are AlreadyStored.

Which files. The day's price files are the `PriceFull` files under `raw/chain=<slug>/date=<day>/` whose
name says that kind and that day (B1, as `basket.extract.day_files` reads them); a conflict copy counts by
its published name and is fetched under its stored name. Every one is fetched: `day_files` then takes each
store's latest from the work folder, as on the Mac. The store list is the greatest name of the day that
`basket.stores.is_store_list` accepts (B2), else that of each earlier day in turn, back to 13 days before
the day: S3 has no cheap "latest folder before", and a chain with no store list for two weeks is the
collector's problem, which the build refuses as NoStoreList. A table is fetched whole or not at all.

The day is ready once the collector's check has written a record under `checks/date=<day>/`
(`day_checked`): the check is the morning's last run.

S3Archive and MemoryArchive are the collector's S3Store and MemoryStore with these methods; `_Archive`
uses their bare list, read and plain put (`_keys`, `_get`, `_put_plain`), `read_raw` and `put_record`.
Nothing here ever deletes.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from basket.extract import table_path
from basket.stores import is_store_list
from collector.names import parse_file_name
from collector.store import MemoryStore, S3Store, check_key, manifest_key, published_name, raw_key

STORE_LIST_LOOKBACK_DAYS = 14
TABLE_FILES = ("prices.parquet", "report.json")
_CONTENT_TYPES = {"prices.parquet": "application/vnd.apache.parquet", "report.json": "application/json"}


def table_key(slug: str, day: date, name: str) -> str:
    return f"tables/prices/chain={slug}/date={day.isoformat()}/{name}"


def record_key(day: date, run_id: str) -> str:
    return f"basket/date={day.isoformat()}/basket-{run_id}.json"


def _stored_name(key: str) -> str:
    return key.rsplit("/", 1)[-1]


def _day_folder(raw_dir: Path, slug: str, day: date) -> Path:
    return raw_dir / f"chain={slug}" / f"date={day.isoformat()}"


class _Archive:
    """The archive bucket for the scheduled build, over a _Store's bare operations."""

    def day_checked(self, day: date) -> bool:
        """Whether the collector's check has written a record for the day."""
        folder = check_key(day, "x").rsplit("/", 1)[0] + "/"
        return bool(self._keys(folder))

    def day_price_file_keys(self, slug: str, day: date) -> list[str]:
        """The keys of the chain's `PriceFull` files of the day, conflict copies included, sorted."""
        keys = []
        for key in self._keys(raw_key(slug, day, "")):
            parsed = parse_file_name(published_name(_stored_name(key)))
            if parsed is None or parsed.kind != "PriceFull" or parsed.day != day:
                continue
            keys.append(key)
        return sorted(keys)

    def fetch_raw(self, slug: str, day: date, raw_dir: Path) -> list[str]:
        """Write the day's price files under `raw_dir/chain=<slug>/date=<day>/`; their stored names."""
        folder = _day_folder(raw_dir, slug, day)
        folder.mkdir(parents=True, exist_ok=True)
        names = []
        for key in self.day_price_file_keys(slug, day):
            name = _stored_name(key)
            (folder / name).write_bytes(self.read_raw(key))
            names.append(name)
        return names

    def fetch_store_list(self, slug: str, day: date, raw_dir: Path) -> date | None:
        """Write the latest store list from the day back to 13 days before it into that day's folder, where
        `basket.stores.day_store_list` finds it; the day it is from, or None when none of those days has one."""
        for back in range(STORE_LIST_LOOKBACK_DAYS):
            listed_day = day - timedelta(days=back)
            names = [name for name in map(_stored_name, self._keys(raw_key(slug, listed_day, "Stores")))
                     if is_store_list(name, listed_day)]
            if names:
                name = max(names)
                folder = _day_folder(raw_dir, slug, listed_day)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(self.read_raw(raw_key(slug, listed_day, name)))
                return listed_day
        return None

    def fetch_manifests(self, slug: str, day: date, manifests_dir: Path) -> int:
        """Write the chain's manifests of the day into `manifests_dir/date=<day>/`; how many there were."""
        folder = manifests_dir / f"date={day.isoformat()}"
        folder.mkdir(parents=True, exist_ok=True)
        keys = self._keys(manifest_key(day, slug, "").removesuffix(".json"))  # manifests/date=<day>/<slug>-
        for key in keys:
            (folder / _stored_name(key)).write_bytes(self.read_raw(key))
        return len(keys)

    def fetch_table(self, slug: str, day: date, tables_dir: Path) -> bool:
        """Write the chain's table and report of the day beside `table_path`; False, writing nothing, when
        either is missing."""
        folder = table_path(tables_dir, slug, day).parent
        bodies = {name: self._get(table_key(slug, day, name)) for name in TABLE_FILES}
        if None in bodies.values():
            return False
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in bodies.items():
            (folder / name).write_bytes(body)
        return True

    def put_table(self, slug: str, day: date, tables_dir: Path) -> list[str]:
        """Put the chain's table and report of the day from beside `table_path`, plain; their keys."""
        folder = table_path(tables_dir, slug, day).parent
        keys = []
        for name in TABLE_FILES:
            key = table_key(slug, day, name)
            self._put_plain(key, (folder / name).read_bytes(), _CONTENT_TYPES[name])
            keys.append(key)
        return keys

    def put_basket_record(self, path: Path, now: datetime) -> str:
        """Put the run's record under the key its day and run id give, write-once and locked; the key.
        `now` must carry a time zone."""
        body = path.read_bytes()
        record = json.loads(body)
        key = record_key(date.fromisoformat(record["day"]), record["run_id"])
        self.put_record(key, body, now)
        return key


class S3Archive(_Archive, S3Store):
    """The archive bucket, through a boto3 S3 client."""


class MemoryArchive(_Archive, MemoryStore):
    """The same in a dict, for tests."""

"""The archive bucket's side of the scheduled build: the day's files fetched into the folders the Mac's
build reads, and the build's results put back.

The scheduled build runs `basket.extract` and `basket.build` over a work folder laid out as the Mac's
synced `data/`:

    <raw dir>/chain=<slug>/date=<day>/<stored name>     the raw files, named as stored
    <manifests dir>/date=<day>/<slug>-<run id>.json     the chain's manifests of the day
    <tables dir>/<kind>/chain=<slug>/date=<day>/        each kind's table files (TABLES)

and puts back, beside the collector's keys:

    tables/prices/chain=<slug>/date=<day>/              prices.parquet and report.json, plain
    tables/promotions/chain=<slug>/date=<day>/          promotions.parquet, texts.parquet and report.json, plain
    tables/items/chain=<slug>/date=<day>/               items.parquet and report.json, plain
    tables/covered/date=<day>/                          covered.parquet, the shopper site's registry, plain
    tables/scored/date=<day>/                           summary.json, the shopper site's scoring summary, plain
    basket/date=<day>/basket-<run id>.json              the run's record, write-once and locked
    forecasts/date=<day>/forecasts.csv.gz               the shopper site's forecasts of the day, write-once and locked
    scores/date=<day>/scores.csv.gz                     the scores of the day's forecasts, write-once and locked

A table's key is its file's path under the tables folder (`kind_key`; `table_key` is the prices table's): the kind,
the chain, the day, the name; a table of no chain (the shopper site's covered registry, its scored summaries) has no
chain segment. A table is derived and a re-run replaces it, so it goes up plain. Of each kind's files, those present
go up (`put_tables`): after a promotion format change the promotions folder holds its report alone, and only that
goes up (the shopper site's plan, the first pre-flight's S7). Nothing deletes, so an earlier run's promotions table of
the day can stay in the archive beside that report: a reader takes a chain's promotion state from the items table's
report. A record is one run's own and never changes, so it goes up as a manifest does (`_Store.put_record`):
write-once, under a ten-year governance lock; the same bytes again are the same put retried, other bytes under its key
are AlreadyStored.

Which files. The day's files of a kind (`PriceFull`, `PromoFull`) are those under `raw/chain=<slug>/date=<day>/` whose
name says that kind and that day (B1, as `basket.extract.day_files` reads them), a name read in any case; a conflict
copy counts by its published name and is fetched under its stored name. Every one of the kinds asked for is fetched,
from one listing of the day's folder: `day_files` then takes each store's latest from the work folder, as on the
Mac. The store list is the greatest name of the day that
`basket.stores.is_store_list` accepts (B2), read from a list of the day's whole folder (an S3 prefix matches in one
case only, and that parse reads a name in any case), else that of each earlier day in turn, back to 13 days before
the day: S3 has no cheap "latest folder before", and a chain with no store list for two weeks is the
collector's problem, which the build refuses as NoStoreList. A table is fetched whole or not at all: its files are
written only when every one of its kind's files is there (`fetch_table` the prices table, `fetch_items` the items
table).

The shopper site's run reads more. Its history (`fetch_history`) is each chain's items table of the day and of the
`shopper.history.READ_DAYS` (90) days before it, never a later day's, each fetched whole or not at all: a day missing
is an extraction that never ran, which `shopper.history.load` reads as a hole (the day's own as MissingTable). Its
covered registry of the day before (`fetch_covered`) is the latest `tables/covered/date=<d>/covered.parquet` of a day
before the run's, found by listing `tables/covered/`, since a run may have missed days; the run's own registry goes
back plain (`put_covered`), replaced by a re-run of the day as every table is.

The day's forecasts file (`put_frozen`) is put as a record is: write-once and locked, its content type gzip. The archive
only stores it: whether a stored file and a new one are the same forecasts is the freezer's to say
(`shopper.freeze`, question E), so the same bytes again are the same put retried and other bytes under the key are
AlreadyStored. `frozen_days` lists the days that hold one. `last_modified` gives an object's time as S3 reports it
(`LastModified`), which the freezer reads back to say whether a file was stored before its day's cutoff (F6): a
MemoryArchive keeps such a time per key, the put's `now` unless it is given an `s3_clock` (a function returning an
aware time), which tests fix.

Scoring (F7). A day's scores file (`put_scores`) is put as the forecasts file is: write-once and locked, as gzip, the
freezer saying whether a stored one and a new one are the same scores. Its summary (`shopper.score.summary_json`) is
derived and goes up plain from the work folder (`put_summary`), only once the day's scores file is in the archive (a
ValueError before: the build puts it after the scores file, Tasks 19 and 23). A day is scored once its summary is in the
archive (`scored_days`), so a run that stopped between the two leaves the day due (within the read's reach:
`shopper.score.due`), and the next build meets the same scores file. `fetch_summaries` writes every summary into the
work folder and returns them, read through `shopper.score.read_summary`, as `DaySummary` objects (the first pre-flight's
N17), earliest first.

The day is ready once the collector's check has written a record under `checks/date=<day>/`
(`day_checked`): the check is the morning's last run.

S3Archive and MemoryArchive are the collector's S3Store and MemoryStore with these methods; `_Archive`
uses their bare list, read and plain put (`_keys`, `_get`, `_put_plain`), `read_raw` and `put_record`.
Nothing here ever deletes.
"""
import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from botocore.exceptions import ClientError

from basket.chains import SLUGS
from basket.stores import is_store_list
from collector.names import parse_file_name
from collector.store import MISSING, MemoryStore, S3Store, check_key, error_code, manifest_key, published_name, raw_key
from shopper.freeze import archive_key, scores_archive_key
from shopper.history import READ_DAYS
from shopper.score import DaySummary, read_summary, summary_path

STORE_LIST_LOOKBACK_DAYS = 14
# Each kind of table a chain's extraction writes for a day, and its files, in the order they go up.
TABLES = {"prices": ("prices.parquet", "report.json"),
          "promotions": ("promotions.parquet", "texts.parquet", "report.json"),
          "items": ("items.parquet", "report.json")}
TABLE_FILES = TABLES["prices"]
COVERED = ("covered", "covered.parquet")   # the shopper site's registry: its kind, with no chain, and its file
SCORED = ("scored", "summary.json")        # the shopper site's scoring summaries: their kind, with no chain, and file
_CONTENT_TYPES = {".parquet": "application/vnd.apache.parquet", ".json": "application/json"}


def kind_key(kind: str, slug: str | None, day: date, name: str) -> str:
    """tables/<kind>/chain=<slug>/date=<day>/<name>; with no chain (`slug` None), tables/<kind>/date=<day>/<name>."""
    chain = "" if slug is None else f"chain={slug}/"
    return f"tables/{kind}/{chain}date={day.isoformat()}/{name}"


def table_key(slug: str, day: date, name: str) -> str:
    """The prices table's key."""
    return kind_key("prices", slug, day, name)


def record_key(day: date, run_id: str) -> str:
    return f"basket/date={day.isoformat()}/basket-{run_id}.json"


def summary_key(day: date) -> str:
    """tables/scored/date=<day>/summary.json: the day's scoring summary, a table of no chain."""
    kind, name = SCORED
    return kind_key(kind, None, day, name)


def _stored_name(key: str) -> str:
    return key.rsplit("/", 1)[-1]


def _day_folder(raw_dir: Path, slug: str, day: date) -> Path:
    return raw_dir / f"chain={slug}" / f"date={day.isoformat()}"


def _local(tables_dir: Path, key: str) -> Path:
    """A table's file under `tables_dir`: the path its key names, less its "tables/"."""
    return tables_dir.joinpath(*key.split("/")[1:])


class _Archive:
    """The archive bucket for the scheduled build, over a _Store's bare operations."""

    def day_checked(self, day: date) -> bool:
        """Whether the collector's check has written a record for the day."""
        folder = check_key(day, "x").rsplit("/", 1)[0] + "/"
        return bool(self._keys(folder))

    def day_file_keys(self, slug: str, day: date, kind: str) -> list[str]:
        """The keys of the chain's files of `kind` of the day, conflict copies included, sorted."""
        return self._day_file_keys(slug, day, (kind,))

    def _day_file_keys(self, slug: str, day: date, kinds: tuple[str, ...]) -> list[str]:
        """The same for each of `kinds`, from one listing of the day's folder."""
        keys = []
        for key in self._keys(raw_key(slug, day, "")):
            parsed = parse_file_name(published_name(_stored_name(key)))
            if parsed is None or parsed.kind not in kinds or parsed.day != day:
                continue
            keys.append(key)
        return sorted(keys)

    def fetch_raw(self, slug: str, day: date, raw_dir: Path, kinds: tuple[str, ...] = ("PriceFull",)) -> list[str]:
        """Write the day's files of `kinds` under `raw_dir/chain=<slug>/date=<day>/`; their stored names."""
        folder = _day_folder(raw_dir, slug, day)
        folder.mkdir(parents=True, exist_ok=True)
        names = []
        for key in self._day_file_keys(slug, day, tuple(kinds)):
            name = _stored_name(key)
            (folder / name).write_bytes(self.read_raw(key))
            names.append(name)
        return names

    def fetch_store_list(self, slug: str, day: date, raw_dir: Path) -> date | None:
        """Write the latest store list from the day back to 13 days before it into that day's folder, where
        `basket.stores.day_store_list` finds it; the day it is from, or None when none of those days has one."""
        for back in range(STORE_LIST_LOOKBACK_DAYS):
            listed_day = day - timedelta(days=back)
            # the whole folder: a prefix matches in one case only, and the Mac's parse reads a name in any case
            names = [name for name in map(_stored_name, self._keys(raw_key(slug, listed_day, "")))
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
        """Write the chain's prices table and report of the day beside `basket.extract.table_path`; False, writing
        nothing, when either is missing."""
        return self._fetch_whole("prices", slug, day, tables_dir)

    def fetch_items(self, slug: str, day: date, tables_dir: Path) -> bool:
        """Write the chain's items table and report of the day beside `shopper.items.items_path`; False, writing
        nothing, when either is missing."""
        return self._fetch_whole("items", slug, day, tables_dir)

    def _fetch_whole(self, kind: str, slug: str, day: date, tables_dir: Path) -> bool:
        """Write each of the kind's files (TABLES) of the chain's day at the path its key names under `tables_dir`;
        False, writing nothing, when any is missing."""
        bodies = {key: self._get(key) for key in (kind_key(kind, slug, day, name) for name in TABLES[kind])}
        if None in bodies.values():
            return False
        for key, body in bodies.items():
            path = _local(tables_dir, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return True

    def fetch_history(self, day: date, tables_dir: Path) -> list[str]:
        """Write each chain's items table of the day and of the READ_DAYS days before it, those whole in the archive;
        the keys of the items tables written, sorted."""
        keys = []
        for slug in SLUGS:
            for back in range(READ_DAYS + 1):
                read_day = day - timedelta(days=back)
                if self.fetch_items(slug, read_day, tables_dir):
                    keys.append(kind_key("items", slug, read_day, TABLES["items"][0]))
        return sorted(keys)

    def fetch_covered(self, day: date, tables_dir: Path) -> date | None:
        """Write the latest covered registry of a day before `day` at the path its key names under `tables_dir`; its
        day, or None, writing nothing, when there is none."""
        kind, name = COVERED
        prefix = kind_key(kind, None, day, name).rsplit("date=", 1)[0]   # tables/covered/
        days = []
        for key in self._keys(prefix):
            try:
                listed = date.fromisoformat(key[len(prefix):].split("/", 1)[0].removeprefix("date="))
            except ValueError:
                continue
            if key == kind_key(kind, None, listed, name) and listed < day:   # a registry, as this code names one
                days.append(listed)
        if not days:
            return None
        latest = max(days)
        key = kind_key(kind, None, latest, name)
        path = _local(tables_dir, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.read_raw(key))
        return latest

    def put_tables(self, slug: str, day: date, tables_dir: Path) -> list[str]:
        """Put the chain's tables of the day from under `tables_dir`, each file at the path its key names there:
        of each kind's files (TABLES), those present, plain; their keys, in TABLES' order."""
        keys = []
        for kind, names in TABLES.items():
            for name in names:
                key = kind_key(kind, slug, day, name)
                path = _local(tables_dir, key)
                if path.is_file():
                    self._put_file(key, path)
                    keys.append(key)
        return keys

    def put_covered(self, day: date, tables_dir: Path) -> str:
        """Put the day's covered registry from under `tables_dir`, at the path its key names there, plain; the key."""
        kind, name = COVERED
        key = kind_key(kind, None, day, name)
        self._put_file(key, _local(tables_dir, key))
        return key

    def put_frozen(self, day: date, body: bytes, now: datetime) -> str:
        """Put the day's forecasts file under its key, write-once and locked as a record is, as gzip; the key. The same
        bytes again are the same put retried; other bytes under the key are AlreadyStored. `now` must carry a time zone."""
        key = archive_key(day)
        self.put_record(key, body, now, "application/gzip")
        return key

    def frozen_days(self) -> list[date]:
        """The days whose forecasts file is in the archive, earliest first."""
        return self._days_with(archive_key)

    def put_scores(self, day: date, body: bytes, now: datetime) -> str:
        """Put the day's scores file under its key, write-once and locked as a record is, as gzip; the key. The same
        bytes again are the same put retried; other bytes under the key are AlreadyStored. `now` must carry a time
        zone."""
        key = scores_archive_key(day)
        self.put_record(key, body, now, content_type="application/gzip")
        return key

    def scored_days(self) -> list[date]:
        """The days whose scoring summary is in the archive, earliest first: the days scored."""
        return self._days_with(summary_key)

    def put_summary(self, day: date, tables_dir: Path) -> str:
        """Put the day's scoring summary from under `tables_dir` (`shopper.score.summary_path`), plain; the key. A
        ValueError, putting nothing, when the archive holds no scores file for the day: a summary goes up only after
        its scores file, so a day `scored_days` lists has one."""
        if self.last_modified(scores_archive_key(day)) is None:
            raise ValueError(f"no scores file for {day.isoformat()} in the archive: its summary goes up after it")
        key = summary_key(day)
        self._put_file(key, summary_path(tables_dir, day))
        return key

    def fetch_summaries(self, tables_dir: Path) -> list[DaySummary]:
        """Write every scoring summary at its path under `tables_dir`; the summaries, earliest first."""
        found = []
        for day in self.scored_days():
            body = self.read_raw(summary_key(day))
            path = summary_path(tables_dir, day)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            found.append(read_summary(body))
        return found

    def _days_with(self, key_of: Callable[[date], str]) -> list[date]:
        """The days whose key `key_of` names holds a file in the archive, earliest first; only keys this code writes."""
        prefix = key_of(date.min).rsplit("date=", 1)[0]   # forecasts/, tables/scored/
        days = []
        for key in self._keys(prefix):
            try:
                listed = date.fromisoformat(key[len(prefix):].split("/", 1)[0].removeprefix("date="))
            except ValueError:
                continue
            if key == key_of(listed):   # a file, as this code names one
                days.append(listed)
        return sorted(days)

    def _put_file(self, key: str, path: Path) -> None:
        """Put a table's file plain, its content type by its suffix: a re-run replaces it."""
        self._put_plain(key, path.read_bytes(), _CONTENT_TYPES[path.suffix])

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

    def last_modified(self, key: str) -> datetime | None:
        """The object's time as S3 reports it (`LastModified`, aware); None when the key holds nothing."""
        try:
            answer = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as err:
            if error_code(err) in MISSING:
                return None
            raise
        return answer["LastModified"]


class MemoryArchive(_Archive, MemoryStore):
    """The same in a dict, for tests. Each key has a time as S3 would give it: the `now` of the locked put that wrote it,
    or the time `s3_clock()` gives when it is given one (it must return an aware time); a plain put has none without a
    clock, as it has no `now`."""

    def __init__(self, *args, s3_clock: Callable[[], datetime] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.s3_clock = s3_clock
        self.times: dict[str, datetime | None] = {}

    def _put_locked(self, key: str, body: bytes, until: datetime, content_type: str | None = None) -> bool:
        stored = super()._put_locked(key, body, until, content_type)
        if stored:   # the put's `now` is the end of its lock less the retention
            self.times[key] = until - self.retention if self.s3_clock is None else self.s3_clock()
        return stored

    def _put_plain(self, key: str, body: bytes, content_type: str) -> None:
        super()._put_plain(key, body, content_type)
        self.times[key] = None if self.s3_clock is None else self.s3_clock()

    def last_modified(self, key: str) -> datetime | None:
        """The key's time (the class's docstring); None when it holds nothing or has none."""
        return self.times.get(key)

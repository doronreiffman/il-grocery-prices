"""History and coverage: the items tables of the day and the 90 days before it, read per column; the covered registry,
carried from day to day; and the 30- and 90-day windows (docs/shopper-site.md P1, P6, Call 10 and "Build and
hosting", with its "Changed after the survey", S1 and "The column"; the plan's Task 8 and question G, the second
pre-flight's S1 and S4).

What is read. The site run for day d reads each chain's items table (`shopper.items`) of d and of the READ_DAYS (90)
days before it, d - 90 to d: P6's 90-day window ends the day before d, and d itself is the page's day. A table of a
later day is never read, whatever the folder holds. A table is its `items.parquet` with its `report.json`; one without
the other is none. The day's own is required (MissingTable, naming the chain and the path, as a missing prices table
stops the basket run); a missing earlier one is an extraction that never ran.

Column-days. Every column of each chain read (`shopper.columns.columns_of`) has a `ColumnDay` for each of the 91
days, from its chain's report of that day: whether the table was there (`present`), whether the column is a hole that
day (B8 per column, as Task 6 wrote it: fewer than half its included stores with a price file, or none included),
whether it is a promotion hole, the chain's promotions error, and the column's counts. A column-day has a record when
its table was there and the column is no hole; a hole is the column's own, so Express can be a hole on a morning its
chain's other columns have records. A chain's table missing for a past day is a hole for each of its columns that day,
and a promotion hole too: nothing is known of its promotions, which is not the same as none. `ColumnDay` is named
apart from `basket.rules.ChainDay` (the first pre-flight's N13).

Pairs and points. A pair is a (column, product) with a point for each day read on which the column's table has a row
for the product (a row per column and GS1 barcode listed above ₪0.01, Task 6): the listed price, the stores' range,
how many stores list it, whether it is wide, on promotion (None when the chain's promotions were not read), the next
start and the promotions on it. A hole day's rows are points too, for the page to show as from too few files; the
windows and the registry skip them. `History.pairs` streams the pairs from DuckDB, by code, then column, the points by
day.

The covered registry (P1 under S1, Call 10, question G). A product is covered once it is wide at some column on some
day with a record at that column; a wide row on a hole day covers nothing (S1: a hole makes no listed-price claim).
Once covered, it stays in the registry for good: each day's registry is the latest earlier one carried forward and
joined with the days read, so a product last listed long before the read keeps its page. Per product and column the
registry keeps the column's name for it and B7's size, both as of its latest day listed there (a row on any day, a
hole day's included: a name is no price claim), that day, and its last wide day with a record there; per product its
first covered day, the earliest wide day with a record at any column. Of the registry's and the read's, a column's
name and size are from the later listing, the read's on the same day; its last wide day is the later. A product's
title is the longest of its columns' names, a tie to the first in code-point order (Call 4); its size is the one most
of its columns state, a tie to the smaller amount (B7's rule, `basket.rules.most_common_size`, over columns), or None
when none states one. The registry is written to `tables/covered/date=<d>/covered.parquet` (`covered_path`; the
archive's key `basket.archive.kind_key("covered", None, d, "covered.parquet")`, the second pre-flight's S4), one row
per (product, column) by code, then column; `basket.archive.fetch_covered` takes the latest one before the day.

The windows (P6, per column). A window of `length` days (30 or 90) is the `length` calendar days ending the day
before the page's day, counting only the days on which the pair's column has a record and the pair a listed price;
holes and days not listed are skipped, never filled. It is short when it counts fewer than 20 of 30 or 60 of 90 days
(ENOUGH); `since` is its first counted day and `listed` the counted days' listed prices, in day order.
"""
import json
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

from basket import duck
from basket.extract import copy_sql, sql_text, write_csv
from basket.rules import MissingTable, most_common_size
from basket.units import Size, plain
from shopper.columns import columns_of
from shopper.items import items_path

READ_DAYS = 90                  # the days read before the page's day: P6's 90-day window
ENOUGH = {30: 20, 90: 60}       # a window of fewer days of records than these is short (P6)
BATCH = 10_000                  # rows fetched from DuckDB at a time
REGISTRY = (("code", "VARCHAR"), ("column", "VARCHAR"), ("name", "VARCHAR"), ("size_amount", "VARCHAR"),
            ("size_kind", "VARCHAR"), ("last_listed", "DATE"), ("last_wide", "DATE"), ("first_covered", "DATE"))
REGISTRY_NULLABLE = ("size_amount", "size_kind", "last_wide")
_REGISTRY_NAMES = ", ".join(f'"{name}"' for name, _ in REGISTRY)
_POINTS = """
    SELECT code, "column", day, listed, low, high, listing, wide, on_promotion, next_start, promotions
    FROM items ORDER BY code, "column", day
"""
# Per (product, column) read: its latest day listed with that day's name and size, and its first and last wide days
# with a record at the column.
_LISTINGS = """
    WITH marked AS (
        SELECT i.*, r.day IS NOT NULL AS record
        FROM items i LEFT JOIN record_days r ON r.col = i."column" AND r.day = i.day),
    latest AS (
        SELECT code, "column", max(day) AS last_listed,
               min(day) FILTER (WHERE wide AND record) AS first_wide,
               max(day) FILTER (WHERE wide AND record) AS last_wide
        FROM marked GROUP BY code, "column")
    SELECT l.code, l."column", i.name, i.size_amount, i.size_kind, l.last_listed, l.first_wide, l.last_wide
    FROM latest l JOIN items i ON i.code = l.code AND i."column" = l."column" AND i.day = l.last_listed
    ORDER BY l.code, l."column"
"""


@dataclass(frozen=True)
class Point:
    """A pair's row of one day: the column's listed price (P2), its stores' range, how many list it, wide (B6), on
    promotion (None when the chain's promotions were not read), the next start and the promotions on it (Task 6's
    structs, () when unread)."""
    day: date
    listed: Decimal | None
    low: Decimal | None
    high: Decimal | None
    listing: int
    wide: bool
    on_promotion: bool | None
    next_start: date | None
    promotions: tuple[dict, ...]


@dataclass(frozen=True)
class ColumnDay:
    """A column's day, from its chain's items report; `present` False when the chain's table of the day is missing."""
    column: str
    slug: str
    day: date
    present: bool
    hole: bool
    promo_hole: bool
    promotions_error: str | None
    included: int
    with_file: int
    counted: int
    promo_files: int

    @property
    def record(self) -> bool:
        """The column has a record that day: its chain's table was there and the column is no hole."""
        return self.present and not self.hole


@dataclass(frozen=True)
class Pair:
    """A (column, product), with a point for each day read on which the column lists it."""
    column: str
    code: str
    points: dict[date, Point]


@dataclass(frozen=True)
class Covered:
    """A covered product: its title, each column's name for it, its size, its first covered day and each column's
    last wide day with a record."""
    code: str
    title: str
    names: dict[str, str]
    size: tuple[Decimal, str] | None
    first_covered: date
    last_wide: dict[str, date]


@dataclass(frozen=True)
class Window:
    """P6's window: the days counted, the first of them, their listed prices in day order, and whether it is short."""
    days: int
    since: date | None
    listed: tuple[Decimal, ...]
    short: bool


@dataclass(frozen=True)
class _Listing:
    """A (product, column)'s registry entry: the name and size of its latest day listed, that day, its last wide
    day with a record, and (from the read only) its first."""
    name: str
    size: Size | None
    last_listed: date
    last_wide: date | None
    first_wide: date | None = None


class History:
    """The days read for `day`: every column-day, by (column, day), and the items tables read, each with its day."""

    def __init__(self, day: date, column_days: dict[tuple[str, date], ColumnDay], tables: Mapping[Path, date]):
        self.day = day
        self.column_days = column_days
        self.tables = dict(tables)

    def pairs(self) -> Iterator[Pair]:
        """Every pair read, by code, then column, streamed from DuckDB."""
        if not self.tables:
            return
        with self._connect() as con:
            result = con.execute(_POINTS)
            key, points = None, {}
            while batch := result.fetchmany(BATCH):
                for code, column, day, listed, low, high, listing, wide, on_promotion, next_start, promotions in batch:
                    if (code, column) != key:
                        if key is not None:
                            yield Pair(column=key[1], code=key[0], points=points)
                        key, points = (code, column), {}
                    points[day] = Point(day=day, listed=listed, low=low, high=high, listing=listing, wide=wide,
                                        on_promotion=on_promotion, next_start=next_start,
                                        promotions=tuple(promotions or ()))
            if key is not None:
                yield Pair(column=key[1], code=key[0], points=points)

    def record_days(self, column: str) -> int:
        """The column's days with a record, of the days read up to the day."""
        return sum(1 for (key, day), found in self.column_days.items()
                   if key == column and day <= self.day and found.record)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """A connection with the view `items`: every row of the tables read, with its table's day."""
        con = duck.connect()
        con.execute("CREATE TEMP TABLE item_tables (path VARCHAR, day DATE)")
        con.executemany("INSERT INTO item_tables VALUES (?, ?)", [(str(path), day) for path, day in self.tables.items()])
        paths = "[" + ", ".join(sql_text(path) for path in self.tables) + "]"
        con.execute(f"""
            CREATE VIEW items AS
            SELECT t.day, i.* EXCLUDE (filename)
            FROM read_parquet({paths}, filename = true, hive_partitioning = false) i
            JOIN item_tables t ON t.path = i.filename
        """)
        return con


def covered_path(tables_dir: Path, day: date) -> Path:
    """tables/covered/date=<day>/covered.parquet under `tables_dir`."""
    return tables_dir / "covered" / f"date={day.isoformat()}" / "covered.parquet"


def _present(path: Path) -> bool:
    return path.is_file() and path.with_name("report.json").is_file()


def _column_day(column: str, slug: str, day: date, report: Mapping) -> ColumnDay:
    found = report["columns"][column]
    return ColumnDay(column=column, slug=slug, day=day, present=True, hole=found["hole"],
                     promo_hole=found["promo_hole"], promotions_error=report["promotions_error"],
                     included=found["included"], with_file=found["with_file"], counted=found["counted"],
                     promo_files=found["promo_files"])


def _missing(column: str, slug: str, day: date) -> ColumnDay:
    """A column-day whose chain's table is missing: a hole, and a promotion hole."""
    return ColumnDay(column=column, slug=slug, day=day, present=False, hole=True, promo_hole=True,
                     promotions_error=None, included=0, with_file=0, counted=0, promo_files=0)


def load(tables_dir: Path, day: date, slugs: Sequence[str]) -> History:
    """The history for `day`: each chain's items tables of day - 90 to day under `tables_dir`, every column of each.
    MissingTable when a chain's table of the day itself is missing."""
    column_days: dict[tuple[str, date], ColumnDay] = {}
    tables: dict[Path, date] = {}
    for slug in slugs:
        for back in range(READ_DAYS + 1):
            read_day = day - timedelta(days=back)
            path = items_path(tables_dir, slug, read_day)
            if not _present(path):
                if read_day == day:
                    raise MissingTable(f"no items table for chain {slug!r} on {day.isoformat()}: {path}")
                for column in columns_of(slug):
                    column_days[(column.key, read_day)] = _missing(column.key, slug, read_day)
                continue
            report = json.loads(path.with_name("report.json").read_text())
            tables[path] = read_day
            for column in columns_of(slug):
                column_days[(column.key, read_day)] = _column_day(column.key, slug, read_day, report)
    return History(day, dict(sorted(column_days.items())), dict(sorted(tables.items(), key=lambda item: item[1])))


def _size(amount: str | None, kind: str | None) -> Size | None:
    return None if amount is None else Size(Decimal(amount), kind)


def _read_listings(history: History) -> dict[str, dict[str, _Listing]]:
    """Per product read, by code, then column: its listing (the module's docstring)."""
    found: dict[str, dict[str, _Listing]] = {}
    if not history.tables:
        return found
    with history._connect() as con:
        con.execute("CREATE TEMP TABLE record_days (col VARCHAR, day DATE)")
        records = [(column, day) for (column, day), column_day in history.column_days.items() if column_day.record]
        if records:
            con.executemany("INSERT INTO record_days VALUES (?, ?)", records)
        for code, column, name, amount, kind, last_listed, first_wide, last_wide in con.execute(_LISTINGS).fetchall():
            found.setdefault(code, {})[column] = _Listing(name, _size(amount, kind), last_listed, last_wide, first_wide)
    return found


def _read_registry(path: Path) -> tuple[dict[str, dict[str, _Listing]], dict[str, date]]:
    """A registry as written: per product its listings by column, and its first covered day."""
    listings: dict[str, dict[str, _Listing]] = {}
    first: dict[str, date] = {}
    with duck.connect() as con:
        rows = con.execute(f"SELECT {_REGISTRY_NAMES} FROM read_parquet({sql_text(path)}, hive_partitioning = false)"
                           ).fetchall()
    for code, column, name, amount, kind, last_listed, last_wide, first_covered in rows:
        listings.setdefault(code, {})[column] = _Listing(name, _size(amount, kind), last_listed, last_wide)
        first[code] = first_covered
    return listings, first


def _later(before: _Listing | None, now: _Listing) -> _Listing:
    """A column's entry from the registry and from the read: the name and size of the later listing (the read's on
    the same day), the later last wide day."""
    if before is None:
        return now
    latest = now if now.last_listed >= before.last_listed else before
    wide = [day for day in (before.last_wide, now.last_wide) if day is not None]
    return _Listing(latest.name, latest.size, latest.last_listed, max(wide, default=None))


def _write_registry(entries: Mapping[str, Mapping[str, _Listing]], first: Mapping[str, date], out: Path) -> None:
    rows = ((code, column, listing.name, None if listing.size is None else plain(listing.size.amount),
             None if listing.size is None else listing.size.kind, listing.last_listed.isoformat(),
             None if listing.last_wide is None else listing.last_wide.isoformat(), first[code].isoformat())
            for code, columns in entries.items() for column, listing in columns.items())
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp, duck.connect() as con:
        csv_path = Path(temp) / "rows.csv"
        write_csv(rows, csv_path, REGISTRY)
        con.execute(copy_sql(csv_path, out, REGISTRY, REGISTRY_NULLABLE))


def covered(history: History, previous: Path | None, out: Path) -> dict[str, Covered]:
    """The covered registry of the history's day (the module's docstring), from the days read and the registry at
    `previous` (the latest before the day, or None for none); written to `out`, and returned by code."""
    carried: dict[str, dict[str, _Listing]] = {}
    first: dict[str, date] = {}
    if previous is not None:
        carried, first = _read_registry(previous)
    read = _read_listings(history)
    for code, columns in read.items():
        days = [listing.first_wide for listing in columns.values()]
        if any(day is not None for day in days):   # wide at some column, on a day with a record there
            first[code] = min(day for day in (first.get(code), *days) if day is not None)
    entries: dict[str, dict[str, _Listing]] = {}
    for code in sorted(first):
        columns = dict(carried.get(code, {}))
        for column, listing in read.get(code, {}).items():
            columns[column] = _later(columns.get(column), listing)
        entries[code] = dict(sorted(columns.items()))
    _write_registry(entries, first, out)
    found = {}
    for code, columns in entries.items():
        names = {column: listing.name for column, listing in columns.items()}
        size = most_common_size(Counter(listing.size for listing in columns.values() if listing.size is not None))
        found[code] = Covered(
            code=code, title=min(names.values(), key=lambda name: (-len(name), name)), names=names,
            size=None if size is None else (size.amount, size.kind), first_covered=first[code],
            last_wide={column: listing.last_wide for column, listing in columns.items()
                       if listing.last_wide is not None})
    return found


def window(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date, length: int) -> Window:
    """P6's window of `length` days (30 or 90) ending the day before `day`, at the pair's column."""
    counted = []
    for back in range(length, 0, -1):
        seen = day - timedelta(days=back)
        found, point = column_days.get((pair.column, seen)), pair.points.get(seen)
        if found is not None and found.record and point is not None and point.listed is not None:
            counted.append(point)
    return Window(days=len(counted), since=counted[0].day if counted else None,
                  listed=tuple(point.listed for point in counted), short=len(counted) < ENOUGH[length])

"""The day's table: one chain's full price files for one day, as one Parquet table of every row.

Files (rule B1). A chain's files for a day are the `PriceFull` files under
`raw/chain=<slug>/date=<day>/` whose name says that kind and that day; other kinds, other days and
names that do not parse are not read. `day_files` takes another kind when asked (`PromoFull`, for the
shopper site's promotion files), by the same rules. A store's key is the store number in the file name with
leading zeros stripped ("093" and "93" are one store, "000" is "0"); the number inside the file is
never read (Carrefour's disagree with their names). The sub-chain is keyed the same way, and is None
for Rami Levy store 039's names, which carry none. A conflict copy (a stored name plus a dot and 12
hex digits) is read by its published name. When a store has more than one file that day, the latest
is used: the greatest stored name in plain string order, since the time comes before any suffix; the
others are passed over and listed.

Rows (rule B3). One row per code as published in a file; the same code again in the same file
replaces the earlier row, counted as `repeated` when the price is the same amount and `conflicting`
when it is not. A price is read as a decimal with at most two places and kept to two places ("450"
is 450.00). A price that is no number, has more than two places, or does not fit the table's
DECIMAL(12,2) is None, and the rows left with no price are counted as `unreadable_prices`. A file of
no `<Item>` gives no rows, so its store is absent from the table and not counted in `stores`. A file
that does not read stops the extraction with BadPriceFile: a day is never built short of a store
without a word.

The table holds every row, not only a basket's, at
`tables/prices/chain=<slug>/date=<day>/prices.parquet`, overwritten by each run, with `report.json`
beside it. The rows go through a CSV in a temporary folder inside the table's own folder, every field
quoted, and DuckDB copies that CSV into Parquet; so in Lambda the CSV is inside the run's work folder,
and never in the system temp folder. The CSV writes None as "", and the three columns that may be None (sub-chain,
normalized code, price) never hold "" otherwise, so "" there is read back as NULL; elsewhere "" stays
"".

    python -m basket.extract --raw data/raw --tables data/tables --day 2026-11-02 --chain ramilevy
"""
import argparse
import csv
import json
import tempfile
import time
from collections.abc import Collection, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from basket import duck
from basket.barcode import is_gs1, normalize
from basket.pricefile import Item, read_items
from collector.names import parse_file_name
from collector.store import published_name

CENT = Decimal("0.01")
PRICE_LIMIT = Decimal(10) ** 10  # DECIMAL(12,2) holds ten digits before the point
COLUMNS = (
    ("store", "VARCHAR"), ("sub_chain", "VARCHAR"), ("code", "VARCHAR"), ("code_norm", "VARCHAR"),
    ("gs1", "BOOLEAN"), ("name", "VARCHAR"), ("price", "DECIMAL(12,2)"), ("quantity", "VARCHAR"),
    ("unit", "VARCHAR"), ("unit_of_measure", "VARCHAR"), ("updated", "VARCHAR"), ("file", "VARCHAR"),
)
NULLABLE = ("sub_chain", "code_norm", "price")


@dataclass(frozen=True)
class DayFile:
    """The file a store's rows come from that day: the keys from its name, the stored name, the local path."""
    store: str
    sub_chain: str | None
    name: str
    path: Path


@dataclass(frozen=True)
class Row:
    """One code at one store; the fields in the table's column order. `file` is the stored file name."""
    store: str
    sub_chain: str | None
    code: str
    code_norm: str | None
    gs1: bool
    name: str
    price: Decimal | None
    quantity: str
    unit: str
    unit_of_measure: str
    updated: str
    file: str


@dataclass(frozen=True)
class RowCounts:
    """One file's rows, those of them with no price, and its codes seen again at the same and at another price."""
    rows: int
    unreadable_prices: int
    repeated: int
    conflicting: int


@dataclass(frozen=True)
class ExtractReport:
    """What one extraction read and wrote; `day` as YYYY-MM-DD, `files` in the table's store order."""
    slug: str
    day: str
    files: list[str]
    skipped: list[str]
    stores: int
    rows: int
    unreadable_prices: int
    repeated: int
    conflicting: int


def store_key(published: str) -> str:
    """A published store or sub-chain number as a key: leading zeros stripped, "0" for zeros only."""
    return published.lstrip("0") or "0"


def day_files(raw_dir: Path, slug: str, day: date, kind: str = "PriceFull") -> tuple[list[DayFile], list[str]]:
    """The latest file of `kind` of each store that day, by store key as a number; the names passed over, sorted."""
    folder = raw_dir / f"chain={slug}" / f"date={day.isoformat()}"
    by_store: dict[str, dict[str, DayFile]] = {}
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        parsed = parse_file_name(published_name(path.name))
        if parsed is None or parsed.kind != kind or parsed.day != day:
            continue
        store = store_key(parsed.store)
        sub_chain = None if parsed.sub_chain is None else store_key(parsed.sub_chain)
        by_store.setdefault(store, {})[path.name] = DayFile(store, sub_chain, path.name, path)
    files, skipped = [], []
    for named in by_store.values():
        latest = max(named)
        files.append(named[latest])
        skipped += [name for name in named if name != latest]
    return sorted(files, key=lambda f: (int(f.store), f.store)), sorted(skipped)


def _price(text: str) -> Decimal | None:
    """The price to two places; None for no number, more than two places, or too large for the table."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or -value.as_tuple().exponent > 2 or abs(value) >= PRICE_LIMIT:
        return None
    return value.quantize(CENT)


def rows_from(day_file: DayFile) -> tuple[list[Row], RowCounts]:
    """The file's rows, one per code as published, the last of a code's rows winning; and their counts."""
    latest: dict[str, Row] = {}
    repeated = conflicting = 0
    for item in read_items(day_file.name, day_file.path.read_bytes()):
        row = _row(day_file, item)
        earlier = latest.get(row.code)
        if earlier is not None:
            if earlier.price == row.price:
                repeated += 1
            else:
                conflicting += 1
        latest[row.code] = row
    rows = list(latest.values())
    unreadable = sum(row.price is None for row in rows)
    return rows, RowCounts(rows=len(rows), unreadable_prices=unreadable, repeated=repeated, conflicting=conflicting)


def _row(day_file: DayFile, item: Item) -> Row:
    return Row(store=day_file.store, sub_chain=day_file.sub_chain, code=item.code, code_norm=normalize(item.code),
               gs1=is_gs1(item.code), name=item.name, price=_price(item.price), quantity=item.quantity,
               unit=item.unit, unit_of_measure=item.unit_of_measure, updated=item.updated, file=day_file.name)


def write_table(rows: Iterable[Row], out: Path) -> int:
    """Write `rows` to the Parquet file `out`, replacing it; the number of rows. No rows still writes the columns."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        csv_path = Path(temp) / "rows.csv"
        count = _write_csv(rows, csv_path)
        with duck.connect() as con:
            con.execute(copy_sql(csv_path, out))
    return count


def _write_csv(rows: Iterable[Row], path: Path) -> int:
    return write_csv(((row.store, row.sub_chain, row.code, row.code_norm, row.gs1, row.name, row.price, row.quantity,
                       row.unit, row.unit_of_measure, row.updated, row.file) for row in rows), path, COLUMNS)


def write_csv(rows: Iterable[Sequence[object]], path: Path, columns: Sequence[tuple[str, str]]) -> int:
    """Write `rows` (each a value per column of `columns`) to the CSV `path` as `copy_sql` reads it: a header of the
    column names, every field quoted, None as "", True and False as "true" and "false"; the number of rows."""
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow([name for name, _ in columns])
        for row in rows:
            writer.writerow(["true" if value is True else "false" if value is False else value for value in row])
            count += 1  # None is written as ""
    return count


def copy_sql(csv_path: Path, out: Path, columns: Sequence[tuple[str, str]] = COLUMNS,
             nullable: Collection[str] = NULLABLE) -> str:
    """SQL copying the CSV `write_csv` wrote into the Parquet file `out`: every CSV column read as text, a quoted ""
    kept as text; then each column cast to its type, "" read as NULL in the `nullable` columns only, and a list
    column (a type ending in "[]") read from its JSON text."""
    read_as_text = ", ".join(f"'{name}': 'VARCHAR'" for name, _ in columns)
    selected = ", ".join(_typed(name, kind, nullable) for name, kind in columns)
    return (f"COPY (SELECT {selected} FROM read_csv({sql_text(csv_path)}, columns = {{{read_as_text}}}, "
            f"header = true, delim = ',', quote = '\"', escape = '\"', allow_quoted_nulls = false)) "
            f"TO {sql_text(out)} (FORMAT parquet)")


def _typed(name: str, kind: str, nullable: Collection[str]) -> str:
    """The column cast to its type; "" is NULL in a column that may be None; a list through JSON."""
    text = f"NULLIF(\"{name}\", '')" if name in nullable else f'"{name}"'
    if kind.endswith("[]"):
        text = f"CAST({text} AS JSON)"
    return f'CAST({text} AS {kind}) AS "{name}"'


def sql_text(path: Path) -> str:
    """A path as an SQL string literal."""
    return "'" + str(path).replace("'", "''") + "'"


def table_path(tables_dir: Path, slug: str, day: date) -> Path:
    return tables_dir / "prices" / f"chain={slug}" / f"date={day.isoformat()}" / "prices.parquet"


def extract(raw_dir: Path, slug: str, day: date, tables_dir: Path) -> ExtractReport:
    """Write the chain's table for the day and `report.json` beside it; the report."""
    files, skipped = day_files(raw_dir, slug, day)
    counts: list[RowCounts] = []

    def every_row() -> Iterator[Row]:
        for day_file in files:
            rows, file_counts = rows_from(day_file)
            counts.append(file_counts)
            yield from rows

    out = table_path(tables_dir, slug, day)
    write_table(every_row(), out)
    report = ExtractReport(
        slug=slug, day=day.isoformat(), files=[f.name for f in files], skipped=skipped,
        stores=sum(1 for c in counts if c.rows), rows=sum(c.rows for c in counts),
        unreadable_prices=sum(c.unreadable_prices for c in counts), repeated=sum(c.repeated for c in counts),
        conflicting=sum(c.conflicting for c in counts))
    (out.parent / "report.json").write_text(json.dumps(asdict(report), sort_keys=True, indent=1))
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract one chain's day of full price files into a Parquet table.")
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--tables", type=Path, required=True)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--chain", required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    report = extract(args.raw, args.chain, args.day, args.tables)
    print(json.dumps(asdict(report), sort_keys=True, indent=1))
    print(f"extracted in {time.perf_counter() - started:.1f} seconds")


if __name__ == "__main__":
    main()

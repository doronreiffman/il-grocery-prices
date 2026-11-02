"""The day's table: one chain's full price files for a day, the latest per store, into one Parquet table."""
import gzip
import json
from dataclasses import asdict, astuple
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from basket.extract import (DayFile, ExtractReport, RowCounts, day_files, extract, main, rows_from,
                            store_key, table_path, write_table)
from basket.pricefile import BadPriceFile, read_items

FIXTURES = Path(__file__).parent / "fixtures"
NCR_722 = FIXTURES / "ncr" / "PriceFull7290058140886-001-722-20261101-001016.gz"
NCR_039 = FIXTURES / "ncr" / "pricefull7290058140886-039-202611010514.gz"
SHUFERSAL_030 = FIXTURES / "shufersal" / "PriceFull7290027600007-001-030-20261031-030000.gz"
CARREFOUR_472 = FIXTURES / "carrefour" / "PriceFull7290055700007-001-472-20261031-051016.gz"
BASKET = FIXTURES / "basket" / "PriceFull7290000000001-001-001-20260101-000000.gz"
SLUG = "ramilevy"
DAY = date(2026, 11, 2)
EARLY_722 = "PriceFull7290058140886-001-722-20261102-001016.gz"
LATE_722 = "PriceFull7290058140886-001-722-20261102-071016.gz"
STORE_039 = "pricefull7290058140886-039-202611020514.gz"
TABLE_COLUMNS = [
    ("store", "VARCHAR"), ("sub_chain", "VARCHAR"), ("code", "VARCHAR"), ("code_norm", "VARCHAR"),
    ("gs1", "BOOLEAN"), ("name", "VARCHAR"), ("price", "DECIMAL(12,2)"), ("quantity", "VARCHAR"),
    ("unit", "VARCHAR"), ("unit_of_measure", "VARCHAR"), ("updated", "VARCHAR"), ("file", "VARCHAR"),
]


def raw_tree(tmp_path: Path, files: dict[str, bytes], slug: str = SLUG, day: date = DAY) -> Path:
    """Lay `files` (name -> bytes) under raw/chain=<slug>/date=<day>/; the raw directory."""
    folder = tmp_path / "raw" / f"chain={slug}" / f"date={day.isoformat()}"
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    return tmp_path / "raw"


def _day_file(tmp_path: Path, name: str, data: bytes) -> DayFile:
    path = tmp_path / name
    path.write_bytes(data)
    return DayFile(store="1", sub_chain="1", name=name, path=path)


def _price_file(*items: tuple[str, str]) -> bytes:
    """A gzipped price file in the common layout, one `<Item>` per (code, price)."""
    body = "".join(f"<Item><ItemCode>{code}</ItemCode><ItemName>מוצר</ItemName><ItemPrice>{price}</ItemPrice></Item>"
                   for code, price in items)
    return gzip.compress(f"<Root><Items>{body}</Items></Root>".encode(), mtime=0)


def _read_table(path: Path) -> list[tuple]:
    with duckdb.connect() as con:
        return con.execute("SELECT * FROM read_parquet(?, hive_partitioning = false)", [str(path)]).fetchall()


def _describe(path: Path) -> list[tuple[str, str]]:
    with duckdb.connect() as con:
        return [(name, kind) for name, kind, *_ in
                con.execute("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning = false)", [str(path)]).fetchall()]


def test_store_key():
    assert [store_key(s) for s in ("093", "000", "39", "0413")] == ["93", "0", "39", "413"]


def test_day_files_takes_the_latest_name_per_store(tmp_path):
    raw = raw_tree(tmp_path, {EARLY_722: NCR_722.read_bytes(), LATE_722: NCR_722.read_bytes()})
    files, skipped = day_files(raw, SLUG, DAY)
    assert files == [DayFile("722", "1", LATE_722, raw / f"chain={SLUG}" / "date=2026-11-02" / LATE_722)]
    assert skipped == [EARLY_722]


def test_day_files_ignores_other_days_and_kinds(tmp_path):
    raw = raw_tree(tmp_path, {
        LATE_722: NCR_722.read_bytes(),
        "PriceFull7290058140886-001-731-20261101-081016.gz": NCR_722.read_bytes(),  # another day's name
        "PromoFull7290058140886-001-733-20261102-001049.gz": NCR_722.read_bytes(),
        "Stores7290058140886-000-20261102-050500.xml": b"<Root/>",
        "notes.txt": b"",
    })
    files, skipped = day_files(raw, SLUG, DAY)
    assert [f.name for f in files] == [LATE_722]
    assert skipped == []


def test_day_files_of_a_chain_with_no_folder_are_none(tmp_path):
    assert day_files(tmp_path / "raw", SLUG, DAY) == ([], [])


def test_conflict_copy_never_beats_a_later_time(tmp_path):
    copy_722 = EARLY_722 + ".0123456789ab"
    early_731 = "PriceFull7290058140886-001-731-20261102-001016.gz"
    copy_731 = "PriceFull7290058140886-001-731-20261102-071016.gz.0123456789ab"
    data = NCR_722.read_bytes()
    raw = raw_tree(tmp_path, {copy_722: data, LATE_722: data, early_731: data, copy_731: data})
    files, skipped = day_files(raw, SLUG, DAY)
    assert [f.name for f in files] == [LATE_722, copy_731]  # a conflict copy is read, by its time
    assert skipped == sorted([copy_722, early_731])


def test_sub_chain_and_store_are_keys(tmp_path):
    shufersal = "PriceFull7290027600007-005-093-20261102-030000.gz"
    raw = raw_tree(tmp_path, {shufersal: SHUFERSAL_030.read_bytes()}, slug="shufersal")
    raw_tree(tmp_path, {STORE_039: NCR_039.read_bytes()})
    [be_093], _ = day_files(raw, "shufersal", DAY)
    assert be_093 == DayFile("93", "5", shufersal, raw / "chain=shufersal" / "date=2026-11-02" / shufersal)
    [rami_039], _ = day_files(raw, SLUG, DAY)
    assert (rami_039.store, rami_039.sub_chain) == ("39", None)  # store 039's names carry no sub-chain


def test_files_are_sorted_by_store_as_a_number(tmp_path):
    names = [f"PriceFull7290058140886-001-{store}-20261102-001016.gz" for store in ("100", "020", "003")]
    raw = raw_tree(tmp_path, {name: NCR_722.read_bytes() for name in names})
    files, _ = day_files(raw, SLUG, DAY)
    assert [f.store for f in files] == ["3", "20", "100"]


def test_rows_last_duplicate_wins_and_conflicts_are_counted(tmp_path):
    rows, counts = rows_from(_day_file(tmp_path, BASKET.name, BASKET.read_bytes()))
    prices = {row.code: row.price for row in rows}
    assert prices["2000000000015"] == Decimal("6.00")
    assert counts == RowCounts(rows=2, unreadable_prices=1, repeated=0, conflicting=1)


def test_a_repeat_at_the_same_price_is_counted_as_repeated(tmp_path):
    data = _price_file(("111", "5.00"), ("111", "5.0"), ("222", "1.00"))
    rows, counts = rows_from(_day_file(tmp_path, "p.gz", data))
    assert [row.code for row in rows] == ["111", "222"]
    assert counts == RowCounts(rows=2, unreadable_prices=0, repeated=1, conflicting=0)


def test_unreadable_price_is_none_and_counted(tmp_path):
    data = _price_file(("1", "abc"), ("2", "7.123"), ("3", "7.12"))
    rows, counts = rows_from(_day_file(tmp_path, "p.gz", data))
    assert [row.price for row in rows] == [None, None, Decimal("7.12")]
    assert counts.unreadable_prices == 2


@pytest.mark.parametrize("text", ["", "NaN", "Infinity", "10000000000"])
def test_a_price_that_is_no_amount_or_too_large_for_the_table_is_unreadable(tmp_path, text):
    [row], counts = rows_from(_day_file(tmp_path, "p.gz", _price_file(("1", text))))
    assert row.price is None
    assert counts.unreadable_prices == 1


def test_the_largest_price_the_table_holds_is_read(tmp_path):
    [row], _ = rows_from(_day_file(tmp_path, "p.gz", _price_file(("1", "9999999999.99"))))
    assert row.price == Decimal("9999999999.99")


def test_code_norm_and_gs1(tmp_path):
    data = _price_file(("0007290000066738", "5.00"), ("1501", "5.00"), ("12-34", "5.00"))
    rows, _ = rows_from(_day_file(tmp_path, "p.gz", data))
    assert [(row.code_norm, row.gs1) for row in rows] == [("7290000066738", True), ("1501", False), (None, False)]


def test_store_comes_from_the_name_not_the_file(tmp_path):
    assert b"<StoreID>903</StoreID>" in gzip.decompress(CARREFOUR_472.read_bytes())
    day = date(2026, 10, 31)
    raw = raw_tree(tmp_path, {CARREFOUR_472.name: CARREFOUR_472.read_bytes()}, slug="carrefour", day=day)
    [day_file], _ = day_files(raw, "carrefour", day)
    rows, _ = rows_from(day_file)
    assert {(row.store, row.sub_chain, row.file) for row in rows} == {("472", "1", CARREFOUR_472.name)}


def test_price_has_two_places(tmp_path):
    rows, _ = rows_from(_day_file(tmp_path, "p.gz", _price_file(("1", "450"), ("2", "7.2"))))
    assert [str(row.price) for row in rows] == ["450.00", "7.20"]


def test_table_round_trips_hebrew_quotes_commas_and_newlines(tmp_path):
    rows, _ = rows_from(_day_file(tmp_path, BASKET.name, BASKET.read_bytes()))
    out = tmp_path / "tables" / "prices.parquet"
    assert write_table(rows, out) == 2
    second_name = read_items(BASKET.name, BASKET.read_bytes())[1].name
    assert second_name in [row[5] for row in _read_table(out)]
    assert _read_table(out) == [astuple(row) for row in rows]


def test_table_keeps_none_as_null_and_empty_text_as_empty(tmp_path):
    path = tmp_path / "p.gz"
    path.write_bytes(_price_file(("12-34", "abc")))  # no quantity, unit or update time: ""
    [row], _ = rows_from(DayFile(store="39", sub_chain=None, name="p.gz", path=path))
    assert (row.sub_chain, row.code_norm, row.price, row.quantity) == (None, None, None, "")
    out = tmp_path / "prices.parquet"
    write_table([row], out)
    assert _read_table(out) == [astuple(row)]


def test_a_file_that_does_not_read_stops_the_extraction(tmp_path):
    raw = raw_tree(tmp_path, {LATE_722: gzip.compress(b"<html></html>", mtime=0)})
    with pytest.raises(BadPriceFile):
        extract(raw, SLUG, DAY, tmp_path / "tables")


def test_extract_writes_parquet_and_report(tmp_path):
    raw = raw_tree(tmp_path, {EARLY_722: NCR_722.read_bytes(), LATE_722: NCR_722.read_bytes(),
                              STORE_039: NCR_039.read_bytes()})
    tables = tmp_path / "tables"
    report = extract(raw, SLUG, DAY, tables)
    out = table_path(tables, SLUG, DAY)
    assert out == tables / "prices" / "chain=ramilevy" / "date=2026-11-02" / "prices.parquet"
    assert report == ExtractReport(slug=SLUG, day="2026-11-02", files=[STORE_039, LATE_722], skipped=[EARLY_722],
                                   stores=2, rows=6, unreadable_prices=0, repeated=0, conflicting=0)
    assert (out.parent / "report.json").read_text() == json.dumps(asdict(report), sort_keys=True, indent=1)
    table = _read_table(out)
    assert len(table) == 6
    assert {(row[0], row[1], row[11]) for row in table} == {("39", None, STORE_039), ("722", "1", LATE_722)}


def test_a_file_of_no_items_adds_no_store(tmp_path):
    raw = raw_tree(tmp_path, {LATE_722: NCR_722.read_bytes(), STORE_039: _price_file()})
    report = extract(raw, SLUG, DAY, tmp_path / "tables")
    assert (report.files, report.stores, report.rows) == ([STORE_039, LATE_722], 1, 3)


def test_extract_with_no_files_writes_an_empty_table(tmp_path):
    report = extract(tmp_path / "raw", SLUG, DAY, tmp_path / "tables")
    out = table_path(tmp_path / "tables", SLUG, DAY)
    assert (report.files, report.stores, report.rows) == ([], 0, 0)
    assert _read_table(out) == []
    assert _describe(out) == TABLE_COLUMNS


def test_extract_overwrites_the_day_s_table(tmp_path):
    raw = raw_tree(tmp_path, {LATE_722: NCR_722.read_bytes()})
    extract(raw, SLUG, DAY, tmp_path / "tables")
    (raw / f"chain={SLUG}" / "date=2026-11-02" / LATE_722).write_bytes(_price_file(("1", "1.00")))
    extract(raw, SLUG, DAY, tmp_path / "tables")
    assert len(_read_table(table_path(tmp_path / "tables", SLUG, DAY))) == 1


def test_main_prints_the_report_and_the_seconds(tmp_path, capsys):
    raw = raw_tree(tmp_path, {LATE_722: NCR_722.read_bytes()})
    main(["--raw", str(raw), "--tables", str(tmp_path / "tables"), "--day", "2026-11-02", "--chain", SLUG])
    report_text, seconds = capsys.readouterr().out.rstrip("\n").rsplit("\n", 1)
    assert json.loads(report_text) == json.loads((table_path(tmp_path / "tables", SLUG, DAY).parent / "report.json").read_text())
    assert seconds.startswith("extracted in ") and seconds.endswith(" seconds")

"""History and coverage: 90 days of items tables read per column, the covered registry carried day to day, and the
30- and 90-day windows (docs/shopper-site.md P1, P6 and Call 10, with its "Changed after the survey", S1; the plan's
Task 8 and the second pre-flight's S1 and S4).

The items tables here are written with Task 6's own columns and report (`shopper.items.COLUMNS`, `ColumnReport`,
`ItemsReport`) through `basket.extract`'s writer; one test reads a table `shopper.items.write_items` wrote itself."""
import json
import random
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from basket.extract import copy_sql, write_csv
from basket.rules import MissingTable
from shopper.columns import columns_of
from shopper.history import (BATCH, READ_DAYS, ColumnDay, Covered, History, Pair, Point, Window, counted, covered,
                             covered_path, load, window)
from shopper.items import COLUMNS as ITEM_COLUMNS, NULLABLE, ColumnReport, ItemsReport, items_path
import shopper_random

DAY = date(2026, 11, 20)
SHUF, RAMI = "shufersal", "ramilevy"
SHELI, DEAL, EXPRESS, UNIVERSE = "shufersal-sheli", "shufersal-deal", "shufersal-express", "shufersal-universe"
SHUF_COLUMNS = (DEAL, EXPRESS, SHELI, UNIVERSE)   # name order, as shopper.columns gives them
A, B, C = "2000000000046", "2000000000053", "2000000000060"   # synthetic GS1 codes
NAME = "מוצר"   # the fixtures' placeholder name
PROMOTION = {"promotion_id": "7", "description": "מבצע", "start": "2026-11-15", "end": "2026-11-30", "kind": "3",
             "buy": "1.000", "price": "7.90", "price_exact": "79/10", "per": None, "low": None, "high": None,
             "valid": True, "why": None, "restrictions": [], "programmes": [], "min_spend": None, "stores": 4,
             "wide": True}


def back(days: int) -> date:
    return DAY - timedelta(days=days)


def _row(column, code, listed="10.00", wide=True, name=NAME, size=None, on_promotion=False, next_start=None,
         promotions=(), listing=4, low=None, high=None):
    """One row of an items table, in Task 6's columns; `on_promotion` and `promotions` None as Task 6 writes them when
    the chain's promotions were not read."""
    amount, kind = (None, None) if size is None else size
    return (column, code, name, amount, kind, listed, low or listed, high or listed, listing, wide, on_promotion,
            None if next_start is None else next_start.isoformat(),
            None if promotions is None else json.dumps(list(promotions), ensure_ascii=False))


def _table(tables: Path, slug: str, day: date, rows=(), holes=(), promo_holes=(), error=None):
    """The chain's items table of the day and its report: every column of the chain, 4 included stores each, a hole
    (1 of 4 with a file) for the columns in `holes`, a promotion hole for those in `promo_holes` (every column when
    the chain's promotions were not read, `error`)."""
    out = items_path(tables, slug, day)
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out.with_name("rows.csv")
    write_csv(rows, csv_path, ITEM_COLUMNS)
    with duckdb.connect() as con:
        con.execute(copy_sql(csv_path, out, ITEM_COLUMNS, NULLABLE))
    csv_path.unlink()
    reports = {}
    for column in columns_of(slug):
        key = column.key
        with_file = 1 if key in holes else 4
        promo_hole = error is not None or key in promo_holes
        mine = [row for row in rows if row[0] == key]
        reports[key] = ColumnReport(column=key, included=4, with_file=with_file, hole=key in holes, counted=with_file,
                                    promo_files=0 if promo_hole else with_file, promo_hole=promo_hole,
                                    items=len(mine), wide=sum(bool(row[9]) for row in mine), on_promotion=0,
                                    valid_deals=0, under_floor=False)
    report = ItemsReport(slug=slug, day=day.isoformat(), columns=reports, outside=[], promotions_error=error, texts=0,
                         promotions=None)
    out.with_name("report.json").write_text(json.dumps(asdict(report)))


def _registry(path: Path) -> list[dict]:
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT * FROM read_parquet('{path}', hive_partitioning = false) ORDER BY code, \"column\"")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


# The days read (P6: the 90-day window ends the day before, so the day and the 90 before it)

def test_the_days_own_items_table_is_required(tmp_path):
    _table(tmp_path, RAMI, back(1), [_row(RAMI, A)])
    with pytest.raises(MissingTable, match=r"ramilevy.*2026-11-20"):
        load(tmp_path, DAY, [RAMI])
    report = items_path(tmp_path, RAMI, DAY).with_name("report.json")
    report.parent.mkdir(parents=True)
    report.write_text("{}")
    with pytest.raises(MissingTable):   # a report without its table is no table
        load(tmp_path, DAY, [RAMI])
    _table(tmp_path, RAMI, DAY, [_row(RAMI, A)])
    report.unlink()
    with pytest.raises(MissingTable):   # nor a table without its report
        load(tmp_path, DAY, [RAMI])
    _table(tmp_path, RAMI, DAY, [_row(RAMI, A)])
    assert load(tmp_path, DAY, [RAMI]).column_days[(RAMI, DAY)].record


def test_a_missing_earlier_table_is_a_hole_in_each_of_the_chains_columns(tmp_path):
    for day in (DAY, back(2)):
        _table(tmp_path, SHUF, day, [_row(DEAL, A)])
        _table(tmp_path, RAMI, day, [_row(RAMI, A)])
    _table(tmp_path, RAMI, back(3), [_row(RAMI, A)])   # no Shufersal items table: its extraction did not run or stopped
    history = load(tmp_path, DAY, [SHUF, RAMI])
    for key in SHUF_COLUMNS:
        found = history.column_days[(key, back(3))]
        assert found == ColumnDay(column=key, slug=SHUF, day=back(3), present=False, hole=True, promo_hole=True,
                                  promotions_error=None, included=0, with_file=0, counted=0, promo_files=0)
        assert not found.record
        assert history.column_days[(key, back(2))].record
    assert history.column_days[(RAMI, back(3))].record


def test_a_hole_day_has_no_record(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(2), [_row(DEAL, A)], holes=(DEAL,))
    found = load(tmp_path, DAY, [SHUF]).column_days[(DEAL, back(2))]
    assert (found.present, found.hole, found.with_file, found.included) == (True, True, 1, 4)
    assert not found.record


def test_a_column_hole_is_that_columns_alone(tmp_path):
    """Express a hole on a day its chain's other columns have records (5 November's morning)."""
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(1), [_row(key, A) for key in SHUF_COLUMNS], holes=(EXPRESS,))
    history = load(tmp_path, DAY, [SHUF])
    assert {key: history.column_days[(key, back(1))].record for key in SHUF_COLUMNS} == {
        DEAL: True, EXPRESS: False, SHELI: True, UNIVERSE: True}


def test_a_column_day_carries_its_report(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)], promo_holes=(SHELI,))
    _table(tmp_path, RAMI, DAY, [_row(RAMI, A)], error="ramilevy: RewardType '99' in PromoFull-1")
    history = load(tmp_path, DAY, [SHUF, RAMI])
    deal, sheli, rami = (history.column_days[(key, DAY)] for key in (DEAL, SHELI, RAMI))
    assert (deal.present, deal.promo_hole, deal.counted, deal.promo_files, deal.promotions_error) == (
        True, False, 4, 4, None)
    assert (sheli.promo_hole, sheli.promo_files, sheli.record) == (True, 0, True)   # a promotion hole has prices
    assert (rami.promo_hole, rami.promotions_error) == (True, "ramilevy: RewardType '99' in PromoFull-1")


def test_later_days_are_not_read(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(4), [_row(DEAL, A, "9.00"), _row(SHELI, B)])
    before = load(tmp_path, DAY, [SHUF])
    _table(tmp_path, SHUF, DAY + timedelta(days=1), [_row(DEAL, A, "5.00"), _row(SHELI, C)], holes=(DEAL,))
    after = load(tmp_path, DAY, [SHUF])
    assert after.column_days == before.column_days
    assert list(after.pairs()) == list(before.pairs())
    assert max(day for _, day in after.column_days) == DAY


def test_ninety_one_days_are_read_and_no_more(tmp_path):
    for days in range(-1, READ_DAYS + 2):   # day + 1 back to day - 91
        _table(tmp_path, RAMI, back(days), [_row(RAMI, A, f"{10 + days}.00")])
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    history = load(tmp_path, DAY, [SHUF, RAMI])
    assert READ_DAYS == 90
    read = [back(days) for days in range(READ_DAYS, -1, -1)]   # day - 90 .. day
    assert sorted({day for _, day in history.column_days}) == read
    assert len(history.column_days) == 91 * 5   # every column of each chain, every day read
    (rami,) = [pair for pair in history.pairs() if pair.column == RAMI]
    assert list(rami.points) == read
    assert rami.points[back(90)].listed == Decimal("100.00")
    assert history.record_days(RAMI) == 91 and history.record_days(DEAL) == 1


def test_the_items_table_task_6_writes_is_read(tmp_path):
    from test_items import DAY as ITEMS_DAY, A as ITEM, SHELI as ITEM_SHELI, _at, _run
    report, rows = _run(tmp_path, _at(("1", "2"), (ITEM, "11.90")))
    history = load(tmp_path / "tables", ITEMS_DAY, [SHUF])
    found = history.column_days[(ITEM_SHELI, ITEMS_DAY)]
    sheli = report.columns[ITEM_SHELI]
    assert (found.included, found.with_file, found.hole, found.counted, found.promo_hole, found.record) == (
        sheli.included, sheli.with_file, sheli.hole, sheli.counted, sheli.promo_hole, True)
    (pair,) = history.pairs()
    row = rows[(ITEM_SHELI, ITEM)]
    assert (pair.column, pair.code) == (ITEM_SHELI, ITEM)
    assert pair.points[ITEMS_DAY] == Point(day=ITEMS_DAY, listed=row["listed"], low=row["low"], high=row["high"],
                                           listing=2, wide=True, on_promotion=None, next_start=None, promotions=())


# The pairs

def test_pairs_come_by_code_then_column_with_a_point_for_each_day_listed(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(SHELI, B), _row(DEAL, B, "4.50", wide=False, listing=1, low="4.00",
                                                       high="5.00"),
                                 _row(DEAL, A, on_promotion=True, next_start=DAY + timedelta(days=3),
                                      promotions=[PROMOTION])])
    _table(tmp_path, SHUF, back(2), [_row(DEAL, A, "11.90")], holes=(DEAL,))
    _table(tmp_path, RAMI, DAY, [_row(RAMI, code, on_promotion=None, promotions=None) for code in (A, B)],
           error="ramilevy: x")
    history = load(tmp_path, DAY, [SHUF, RAMI])
    pairs = list(history.pairs())
    assert [(pair.code, pair.column) for pair in pairs] == [(A, RAMI), (A, DEAL), (B, RAMI), (B, DEAL), (B, SHELI)]
    deal_a = pairs[1]
    assert list(deal_a.points) == [back(2), DAY]   # a hole day's row is kept: the window and covered skip it
    assert deal_a.points[back(2)].listed == Decimal("11.90")
    today = deal_a.points[DAY]
    assert (today.on_promotion, today.next_start) == (True, DAY + timedelta(days=3))
    (promotion,) = today.promotions
    assert (promotion["promotion_id"], promotion["price"], promotion["start"], promotion["valid"]) == (
        "7", Decimal("7.90"), date(2026, 11, 15), True)
    assert pairs[3].points[DAY] == Point(day=DAY, listed=Decimal("4.50"), low=Decimal("4.00"), high=Decimal("5.00"),
                                         listing=1, wide=False, on_promotion=False, next_start=None, promotions=())
    unread = pairs[0].points[DAY]
    assert (unread.on_promotion, unread.promotions) == (None, ())


def test_record_days_count_the_columns_days_with_a_record(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(1), [_row(DEAL, A)], holes=(DEAL,))
    _table(tmp_path, SHUF, back(5), [_row(SHELI, A)], promo_holes=(DEAL,))
    history = load(tmp_path, DAY, [SHUF])
    assert {key: history.record_days(key) for key in SHUF_COLUMNS} == {DEAL: 2, EXPRESS: 3, SHELI: 3, UNIVERSE: 3}


# The covered registry (P1 under S1, Call 10)

def test_covered_is_wide_in_some_column_once(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, B, wide=False)])
    _table(tmp_path, SHUF, back(5), [_row(DEAL, A), _row(SHELI, A, wide=False), _row(SHELI, B, wide=False)])
    out = covered_path(tmp_path, DAY)
    found = covered(load(tmp_path, DAY, [SHUF]), None, out)
    assert list(found) == [A]   # B is listed, never wide
    assert found[A] == Covered(code=A, title=NAME, names={DEAL: NAME, SHELI: NAME}, size=None,
                               first_covered=back(5), last_wide={DEAL: back(5)})
    assert out.is_file()


def test_a_product_wide_only_on_hole_days_is_not_covered(tmp_path):
    """S1: a hole column-day makes no listed-price claim, so its wide rows cover nothing and set no last wide day."""
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)], holes=(DEAL,))
    _table(tmp_path, SHUF, back(2), [_row(EXPRESS, C), _row(DEAL, A)], holes=(EXPRESS, DEAL))
    _table(tmp_path, SHUF, back(4), [_row(DEAL, A), _row(EXPRESS, C, wide=False)])
    found = covered(load(tmp_path, DAY, [SHUF]), None, covered_path(tmp_path, DAY))
    assert list(found) == [A]
    assert (found[A].first_covered, found[A].last_wide) == (back(4), {DEAL: back(4)})


def test_a_product_stays_covered_after_the_read_window(tmp_path):
    """Call 10: once covered, always in the registry, with its names, size and last wide days, however long ago."""
    old = back(120)
    _table(tmp_path, RAMI, old, [_row(RAMI, A, size=("500", "gml"))])
    first = covered(load(tmp_path, old, [RAMI]), None, covered_path(tmp_path, old))
    _table(tmp_path, RAMI, DAY, [_row(RAMI, B)])
    history = load(tmp_path, DAY, [RAMI])
    assert all(pair.code == B for pair in history.pairs())   # A is beyond the read
    found = covered(history, covered_path(tmp_path, old), covered_path(tmp_path, DAY))
    assert list(found) == [A, B]
    assert found[A] == first[A] == Covered(code=A, title=NAME, names={RAMI: NAME}, size=(Decimal(500), "gml"),
                                           first_covered=old, last_wide={RAMI: old})
    again = covered(history, covered_path(tmp_path, DAY), tmp_path / "again.parquet")
    assert again == found   # read back from the registry as written


def test_the_registry_keeps_each_columns_last_wide_day(tmp_path):
    old = back(150)
    _table(tmp_path, SHUF, old, [_row(EXPRESS, A), _row(DEAL, A)])
    covered(load(tmp_path, old, [SHUF]), None, covered_path(tmp_path, old))
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A, wide=False), _row(SHELI, A, wide=False)])
    _table(tmp_path, SHUF, back(3), [_row(SHELI, A), _row(DEAL, A, wide=False)])
    _table(tmp_path, SHUF, back(10), [_row(DEAL, A), _row(SHELI, A, wide=False)])
    found = covered(load(tmp_path, DAY, [SHUF]), covered_path(tmp_path, old), covered_path(tmp_path, DAY))
    assert found[A].last_wide == {DEAL: back(10), EXPRESS: old, SHELI: back(3)}
    assert found[A].first_covered == old
    assert [(row["column"], row["last_wide"], row["first_covered"]) for row in
            _registry(covered_path(tmp_path, DAY))] == [(DEAL, back(10), old), (EXPRESS, old, old),
                                                        (SHELI, back(3), old)]


def test_first_covered_is_the_first_wide_day_with_a_record(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(6), [_row(SHELI, A)])
    _table(tmp_path, SHUF, back(7), [_row(DEAL, A)])
    _table(tmp_path, SHUF, back(8), [_row(DEAL, A)], holes=(DEAL,))
    _table(tmp_path, SHUF, back(9), [_row(DEAL, A, wide=False)])
    found = covered(load(tmp_path, DAY, [SHUF]), None, covered_path(tmp_path, DAY))
    assert found[A].first_covered == back(7)
    assert found[A].last_wide == {DEAL: DAY, SHELI: back(6)}


def test_each_columns_name_is_its_latest_days_and_the_title_the_longest(tmp_path):
    """A name is no price claim: a hole day's row names the product too. The title is the longest of the names, a tie
    to the first in code-point order (Call 4)."""
    _table(tmp_path, SHUF, DAY, [_row(SHELI, A, name="מוצר ב")])
    _table(tmp_path, SHUF, back(2), [_row(DEAL, A, name="מוצר")], holes=(DEAL,))
    _table(tmp_path, SHUF, back(6), [_row(DEAL, A, name="מוצר ארוך מאוד")])
    _table(tmp_path, SHUF, back(7), [_row(UNIVERSE, A, name="מוצר א")])
    found = covered(load(tmp_path, DAY, [SHUF]), None, covered_path(tmp_path, DAY))
    assert found[A].names == {DEAL: "מוצר", SHELI: "מוצר ב", UNIVERSE: "מוצר א"}
    assert found[A].title == "מוצר א"


def test_a_names_later_listing_wins_over_the_registrys(tmp_path):
    old = back(100)
    _table(tmp_path, RAMI, old, [_row(RAMI, A, name="מוצר ישן מאוד")])
    covered(load(tmp_path, old, [RAMI]), None, covered_path(tmp_path, old))
    _table(tmp_path, RAMI, DAY, [_row(RAMI, A, wide=False, size=("1", "unit"))])
    found = covered(load(tmp_path, DAY, [RAMI]), covered_path(tmp_path, old), covered_path(tmp_path, DAY))
    assert (found[A].names, found[A].title, found[A].size) == ({RAMI: NAME}, NAME, (Decimal(1), "unit"))
    assert found[A].last_wide == {RAMI: old}   # listed since, never wide again


def test_the_size_is_the_one_most_columns_state_on_their_latest_day(tmp_path):
    _table(tmp_path, SHUF, DAY, [_row(DEAL, A, size=("1000", "gml")), _row(SHELI, A, size=("500", "gml")),
                                 _row(UNIVERSE, A), _row(DEAL, B, size=("2", "unit")), _row(SHELI, B, size=("1", "unit"))])
    _table(tmp_path, SHUF, back(1), [_row(EXPRESS, A, size=("500", "gml")), _row(DEAL, A, size=("500", "gml"))])
    found = covered(load(tmp_path, DAY, [SHUF]), None, covered_path(tmp_path, DAY))
    assert found[A].size == (Decimal(500), "gml")   # Express (its latest day) and Sheli; Deal today 1000, Universe none
    assert found[B].size == (Decimal(1), "unit")     # a tie to the smaller amount (B7's tie)


def test_the_registry_is_written_at_its_key(tmp_path):
    _table(tmp_path, RAMI, DAY, [_row(RAMI, A, size=("1.5", "gml"))])
    out = covered_path(tmp_path, DAY)
    assert out == tmp_path / "covered" / "date=2026-11-20" / "covered.parquet"
    covered(load(tmp_path, DAY, [RAMI]), None, out)
    assert _registry(out) == [{"code": A, "column": RAMI, "name": NAME, "size_amount": "1.5", "size_kind": "gml",
                               "last_listed": DAY, "last_wide": DAY, "first_covered": DAY}]
    assert [path.name for path in out.parent.iterdir()] == ["covered.parquet"]   # no staging file left


def test_an_empty_read_carries_the_registry_alone(tmp_path):
    _table(tmp_path, RAMI, DAY)
    assert covered(load(tmp_path, DAY, [RAMI]), None, covered_path(tmp_path, DAY)) == {}
    assert _registry(covered_path(tmp_path, DAY)) == []


# The windows (P6)

def _pair(column: str, listed: dict[date, str]) -> Pair:
    return Pair(column=column, code=A, points={day: Point(day=day, listed=Decimal(price), low=Decimal(price),
                                                          high=Decimal(price), listing=4, wide=True,
                                                          on_promotion=False, next_start=None, promotions=())
                                               for day, price in listed.items()})


def _days(column: str, days, holes=(), slug=SHUF) -> dict[tuple[str, date], ColumnDay]:
    return {(column, day): ColumnDay(column=column, slug=slug, day=day, present=True, hole=day in holes,
                                     promo_hole=False, promotions_error=None, included=4,
                                     with_file=1 if day in holes else 4, counted=4, promo_files=4)
            for day in days}


def test_the_window_ends_the_day_before(tmp_path):
    days = [back(31), back(30), back(29), DAY]
    pair = _pair(DEAL, {back(31): "1.00", back(30): "2.00", back(29): "3.00", DAY: "4.00"})
    found = window(pair, _days(DEAL, days), DAY, 30)
    assert found == Window(days=2, since=back(30), listed=(Decimal("2.00"), Decimal("3.00")), short=True)


def test_short_windows():
    for length, enough in ((30, 20), (90, 60)):
        for days, short in ((enough - 1, True), (enough, False)):
            listed = {back(n): "5.00" for n in range(1, days + 1)}
            found = window(_pair(DEAL, listed), _days(DEAL, listed), DAY, length)
            assert (found.days, found.short, found.since) == (days, short, back(days))


def test_a_window_skips_holes_and_days_not_listed():
    listed = {back(n): f"{n}.00" for n in (2, 3, 5, 7, 9)}
    column_days = {**_days(DEAL, [back(n) for n in range(1, 9)], holes=(back(3), back(7))),
                   **_days(SHELI, [back(9)], holes=())}   # day - 9 has no record at Deal: another column's is no record
    found = window(_pair(DEAL, listed), column_days, DAY, 30)
    assert found == Window(days=2, since=back(5), listed=(Decimal("5.00"), Decimal("2.00")), short=True)


def test_a_window_reads_its_own_columns_days(tmp_path):
    listed = {back(n): "5.00" for n in (1, 2)}
    column_days = {**_days(DEAL, listed), **_days(SHELI, listed, holes=tuple(listed))}
    assert window(_pair(DEAL, listed), column_days, DAY, 30).days == 2
    assert window(_pair(SHELI, listed), column_days, DAY, 30) == Window(days=0, since=None, listed=(), short=True)


def test_a_history_is_its_day_and_column_days(tmp_path):
    found = History(DAY, _days(DEAL, [DAY, back(1)], holes=(back(1),)), {})
    assert (found.day, found.record_days(DEAL), list(found.pairs())) == (DAY, 1, [])
    assert covered(found, None, covered_path(tmp_path, DAY)) == {}   # no table read: the registry alone


# The speedups (the plan's Task 25a): the code as it stood before each, kept here, against the code as it is

_POINTS_BEFORE = """
    SELECT code, "column", day, listed, low, high, listing, wide, on_promotion, next_start, promotions
    FROM items ORDER BY code, "column", day
"""


def _pairs_before(history: History):
    """`History.pairs` as it stood before Task 25a: DuckDB's own Decimals, each point made by keyword."""
    if not history.tables:
        return
    with history._connect() as con:
        result = con.execute(_POINTS_BEFORE)
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


def test_the_pairs_stream_as_before(tmp_path):
    """Task 25a: the stream reads each price as its text, made a Decimal once, and makes each point by position; the
    pairs are the same as before, compared by `repr` so that each Decimal's places are compared too (5.40 is not
    5.4 there), over two chains' random tables of 91 days (missing tables, holes, unread promotions, prices that
    change, promotions with conditions), more rows than one fetch. Pair by pair, so that a failure names the pairs
    rather than make pytest diff two strings of millions of characters."""
    rng = random.Random(8)
    first = back(READ_DAYS)
    for slug, codes in ((SHUF, 60), (RAMI, 40)):
        shopper_random.write_tables(rng, tmp_path, slug, first, DAY, [shopper_random.code(n) for n in range(codes)])
    history = load(tmp_path, DAY, [SHUF, RAMI])
    found, before = list(history.pairs()), list(_pairs_before(history))
    assert sum(len(pair.points) for pair in found) > BATCH
    assert [(pair.column, pair.code) for pair in found] == [(pair.column, pair.code) for pair in before]
    differ = [f"{new.column} {new.code}" for new, old in zip(found, before) if repr(new) != repr(old)]
    assert not differ, f"{len(differ)} pairs differ, the first {differ[:3]}"


def _counted_before(pair, column_days, day, length):
    """`counted` as it stood before Task 25a's window walk: each day of the window made anew."""
    points = []
    for back in range(length, 0, -1):
        seen = day - timedelta(days=back)
        found, point = column_days.get((pair.column, seen)), pair.points.get(seen)
        if found is not None and found.record and point is not None and point.listed is not None:
            points.append(point)
    return points


def test_a_windows_points_as_before():
    """Task 25a: `counted` takes the window's days from a cache of each day and length; the points are the same as
    before over random pairs (holes of every kind, days with no column-day, days not listed or with no listed price),
    for windows of 1, 30 and 90 days ending on several days."""
    rng = random.Random(6)
    for n in range(200):
        column_days = shopper_random.column_days(rng, DEAL, SHUF, back(READ_DAYS + 5), DAY)
        pair = shopper_random.pair(rng, DEAL, shopper_random.code(n), back(READ_DAYS + 5), DAY)
        for day in (DAY, back(1), back(3) + timedelta(days=n % 7)):
            for length in (1, 30, READ_DAYS):
                assert counted(pair, column_days, day, length) == _counted_before(pair, column_days, day, length)

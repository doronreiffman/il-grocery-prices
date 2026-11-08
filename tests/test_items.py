"""The day's items table, a row per column and product, and the reader's input (P1's day test, P2, the day's promotions;
the plan's Task 6 and the second pre-flight's B1, S3, S9, S11, S12 (d) and S19)."""
import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import duckdb
import pytest

from basket.barcode import is_gs1, normalize
from basket.chains import EXCLUDED
from basket.extract import Row, extract, table_path, write_table
from basket.rules import apply_filters, chain_day, chain_prices, chain_sizes, open_day, stores_with_file_keys
from basket.stores import Store, chain_stores, included
from basket.units import Size
from shopper.columns import members, outside
from shopper.deals import StorePrices, deal, deal_from_row
from shopper.items import HORIZON, items_path, texts_path, write_items
from shopper.promofile import PromotionFormatChanged
from shopper.promos import extract_promotions, promotions_path
from test_build import DAY as GOLDEN_DAY, EGGS, MILK, PASTA, golden_tree
from test_promos import _file, _group, _item, _name, _promotion

DAY = date(2026, 11, 7)
SLUG = "shufersal"
SHELI, DEAL, EXPRESS, UNIVERSE = "shufersal-sheli", "shufersal-deal", "shufersal-express", "shufersal-universe"
A, B, C, D, E = "2000000000046", "2000000000053", "2000000000060", "2000000000077", "2000000000084"  # synthetic
INTERNAL = "1234567"   # a chain's own code: no GS1 check digit, so no product (P1)
NAME = "מוצר"          # the fixtures' placeholder name


def _store(store_id, sub_chain):
    return Store(store_id, sub_chain, "סניף", "1")


# The synthetic Shufersal day: Sheli (sub-chain 1) stores 1 and 2, Deal (2) stores 3 and 4, store 6 in sub-chain 6
# (Yesh Chesed, in no column), and store 779, on the list in Express (7) with its price file named under Be's 005, as
# store 779 was on 2026-11-02. Universe (8) has no store.
STORES = (_store("1", "1"), _store("2", "1"), _store("3", "2"), _store("4", "2"), _store("6", "6"), _store("779", "7"))
FILE_SUB_CHAIN = {"779": "5"}   # the sub-chain a store's price file is named under, where it is not the list's


def _row(stores, store, code, price, name=NAME, quantity="", unit=""):
    sub_chain = FILE_SUB_CHAIN.get(store) or next(s.sub_chain for s in stores if s.id == store)
    return Row(store, sub_chain, code, normalize(code), is_gs1(code), name, Decimal(price), quantity, unit, "", "",
               f"PriceFull-{store}")


def _prices(tables, priced, stores=STORES):
    """The day's prices table, written with basket.extract's writer: `priced` maps a store to its rows, each (code,
    price) or (code, price, name)."""
    write_table([_row(stores, store, *listed) for store, rows in priced.items() for listed in rows],
                table_path(tables, SLUG, DAY))


def _promotions(raw, tables, stores, ids, files):
    """The day's promotions table (Task 5) over the columns' counted stores, as Task 7 counts them: each column's
    members with a price file that counts. `files` maps a store to the promotions its file holds."""
    folder = raw / f"chain={SLUG}" / f"date={DAY.isoformat()}"
    folder.mkdir(parents=True, exist_ok=True)
    for store, promotions in files.items():
        (folder / _name(store)).write_bytes(_file(store, *promotions))
    with open_day(tables, DAY, [SLUG]) as con:
        with_file = set(stores_with_file_keys(con, {SLUG: set(ids)}, {SLUG: EXCLUDED[SLUG].sub_chains})[SLUG])
    counted = {key: set(members_ & with_file) for key, members_ in members(SLUG, stores, ids).items()}
    in_no_column = {store.id for store in outside(SLUG, stores, ids)} & with_file
    return extract_promotions(raw, SLUG, DAY, counted, tables, in_no_column)


def _read(path, order='"column", code'):
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT * FROM read_parquet('{path}', hive_partitioning = false) ORDER BY {order}")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def _run(tmp_path, priced, promotions=None, stores=STORES, error=None):
    """Write the day's prices (and with `promotions`, its promotions) table, then the items table; the report and the
    rows by (column, code)."""
    raw, tables = tmp_path / "raw", tmp_path / "tables"
    _prices(tables, priced, stores)
    ids = included(list(stores), SLUG)
    promo = None if promotions is None else _promotions(raw, tables, stores, ids, promotions)
    report = write_items(tables, SLUG, DAY, stores, ids, EXCLUDED[SLUG].sub_chains, promo, error)
    rows = _read(items_path(tables, SLUG, DAY))
    return report, {(row["column"], row["code"]): row for row in rows}


def _at(stores_ids, *rows):
    """Each of `stores_ids` listing `rows`."""
    return {store: list(rows) for store in stores_ids}


def _price_on(row):
    return [(p["promotion_id"], p["kind"], p["price"], p["valid"], p["why"], p["wide"]) for p in row["promotions"]]


# P2 per column (B5, B4, B2)

def test_a_whole_chains_median_is_the_baskets(tmp_path):
    data = golden_tree(tmp_path)
    raw, tables = data / "raw", data / "tables"
    for slug in ("ramilevy", "osherad", "yochananof"):   # each chain one column, its key the slug
        extract(raw, slug, GOLDEN_DAY, tables)
        stores, _ = chain_stores(raw, slug, GOLDEN_DAY)
        ids = included(stores, slug)
        report = write_items(tables, slug, GOLDEN_DAY, stores, ids, EXCLUDED[slug].sub_chains, None, None)
        with open_day(tables, GOLDEN_DAY, [slug]) as con:
            apply_filters(con, {slug: ids}, {slug: EXCLUDED[slug].sub_chains})
            prices = chain_prices(con, [MILK, PASTA, EGGS])
            sizes = chain_sizes(con, [MILK, PASTA, EGGS])
        rows = _read(items_path(tables, slug, GOLDEN_DAY))
        assert {row["code"]: (row["listed"], row["low"], row["high"], row["listing"],
                              Size(Decimal(row["size_amount"]), row["size_kind"])) for row in rows} == {
            code: (price.median, price.low, price.high, price.listing, sizes[(chain, code)])
            for (chain, code), price in prices.items()}
        assert {row["column"] for row in rows} == {slug} and list(report.columns) == [slug]
        assert (report.columns[slug].included, report.columns[slug].with_file) == (2, 2)


def test_each_columns_median_is_over_its_own_stores(tmp_path):
    priced = {"1": [(A, "11.90"), (B, "5.01")], "2": [(A, "11.90"), (B, "5.02")], "3": [(A, "9.90")],
              "4": [(A, "9.90")]}
    _, rows = _run(tmp_path, priced)
    assert {key: (row["listed"], row["low"], row["high"], row["listing"]) for key, row in rows.items()} == {
        (DEAL, A): (Decimal("9.90"), Decimal("9.90"), Decimal("9.90"), 2),
        (SHELI, A): (Decimal("11.90"), Decimal("11.90"), Decimal("11.90"), 2),
        (SHELI, B): (Decimal("5.015"), Decimal("5.01"), Decimal("5.02"), 2)}   # exact: half an agora kept


def test_placeholders_are_left_out_of_the_median(tmp_path):
    _, rows = _run(tmp_path, {"1": [(A, "0.01")], "2": [(A, "11.90")]})
    assert (rows[(SHELI, A)]["listed"], rows[(SHELI, A)]["listing"]) == (Decimal("11.90"), 1)


def test_internal_codes_get_no_row(tmp_path):
    _, rows = _run(tmp_path, _at(("1", "2"), (A, "5.00"), (INTERNAL, "5.00")))
    assert set(rows) == {(SHELI, A)}


def test_the_size_is_the_columns_most_common(tmp_path):
    stores = STORES + (_store("7", "1"),)
    priced = {"1": [(A, "5.00", NAME, "1", "ליטר"), (B, "5.00")], "2": [(A, "5.00", NAME, "1000", "מיליליטר")],
              "7": [(A, "5.00", NAME, "500", "גרם")], "3": [(A, "5.00", NAME, "500", "גרם")]}
    _, rows = _run(tmp_path, priced, stores=stores)
    assert (rows[(SHELI, A)]["size_amount"], rows[(SHELI, A)]["size_kind"]) == ("1000", "gml")   # two litres, one 500 g
    assert (rows[(DEAL, A)]["size_amount"], rows[(DEAL, A)]["size_kind"]) == ("500", "gml")
    assert (rows[(SHELI, B)]["size_amount"], rows[(SHELI, B)]["size_kind"]) == (None, None)     # no size stated


# P1's day test: wide (B6 per column)

def test_wide_is_half_the_columns_stores_with_a_file(tmp_path):
    # Sheli: 5 included, 4 with a file (store 9 has none); Deal: 3 with a file
    stores = (_store("1", "1"), _store("2", "1"), _store("7", "1"), _store("8", "1"), _store("9", "1"),
              _store("3", "2"), _store("4", "2"), _store("10", "2"))
    priced = {"1": [(A, "5.00")], "2": [(A, "5.00")], "7": [(C, "1.00")], "8": [(C, "1.00")],
              "3": [(B, "5.00")], "4": [(C, "1.00")], "10": [(C, "1.00")]}
    report, rows = _run(tmp_path, priced, stores=stores)
    assert (report.columns[SHELI].included, report.columns[SHELI].with_file) == (5, 4)
    assert rows[(SHELI, A)]["wide"] is True    # 2 of 4 with a file
    assert rows[(DEAL, B)]["wide"] is False    # 1 of 3
    assert (report.columns[SHELI].wide, report.columns[DEAL].wide) == (2, 1)


# B8 per column: holes (the second pre-flight's B1)

def test_a_column_under_half_its_stores_is_a_hole_while_the_chain_is_not(tmp_path):
    stores = (_store("1", "1"), _store("2", "1"), _store("7", "1"), _store("8", "1"),
              _store("3", "2"), _store("4", "2"), _store("10", "2"), _store("11", "2"))
    priced = {"1": [(A, "5.00")], **_at(("3", "4", "10", "11"), (A, "4.00"))}
    report, rows = _run(tmp_path, priced, stores=stores)
    assert chain_day(SLUG, 8, 5).in_ranking   # the chain, 5 of its 8 stores with a file, is no hole
    assert (report.columns[SHELI].with_file, report.columns[SHELI].hole) == (1, True)
    assert (report.columns[DEAL].with_file, report.columns[DEAL].hole) == (4, False)
    assert rows[(SHELI, A)]["listed"] == Decimal("5.00")   # a hole's rows are written; later tasks mark them


def test_a_column_at_half_its_stores_is_no_hole(tmp_path):
    stores = (_store("1", "1"), _store("2", "1"), _store("7", "1"), _store("8", "1"))
    report, _ = _run(tmp_path, _at(("1", "2"), (A, "5.00")), stores=stores)
    sheli = report.columns[SHELI]
    assert (sheli.included, sheli.with_file, sheli.hole) == (4, 2, False)


def test_a_column_with_no_included_store_is_a_hole(tmp_path):
    report, _ = _run(tmp_path, _at(("1", "2"), (A, "5.00")))
    assert (report.columns[UNIVERSE].included, report.columns[UNIVERSE].with_file, report.columns[UNIVERSE].hole) == (
        0, 0, True)


def test_a_store_named_under_be_is_included_in_its_column_and_never_has_a_file(tmp_path):
    priced = {**_at(("1", "2"), (A, "5.00")), "779": [(C, "7.00"), (A, "1.00")]}
    report, rows = _run(tmp_path, priced)
    express = report.columns[EXPRESS]
    assert (express.included, express.with_file, express.hole, express.items) == (1, 0, True, 0)
    assert (EXPRESS, C) not in rows and (EXPRESS, A) not in rows


def test_stores_in_no_column_get_no_rows(tmp_path):
    report, rows = _run(tmp_path, {"6": [(C, "3.00"), (A, "1.00")], **_at(("1", "2"), (A, "5.00"))})
    assert set(rows) == {(SHELI, A)}
    assert rows[(SHELI, A)]["listing"] == 2
    assert report.outside == ["6"]
    assert list(report.columns) == [DEAL, EXPRESS, SHELI, UNIVERSE]   # every column of the chain, in name order


def test_the_name_is_the_most_common_then_the_longest(tmp_path):
    stores = STORES + (_store("7", "1"),)
    longer, first, second = NAME + " ארוך", NAME + " אא", NAME + " אב"
    priced = {"1": [(A, "5.00", NAME), (B, "5.00", NAME), (C, "5.00", second)],
              "2": [(A, "5.00", NAME), (B, "5.00", longer), (C, "5.00", first)],
              "7": [(A, "5.00", longer)]}
    _, rows = _run(tmp_path, priced, stores=stores)
    assert rows[(SHELI, A)]["name"] == NAME      # the most common, though shorter
    assert rows[(SHELI, B)]["name"] == longer    # a tie: the longest
    assert rows[(SHELI, C)]["name"] == first     # a tie of one length: the first in code-point order


# The day's promotions

LISTED = _at(("1", "2", "3", "4"), (A, "5.00"), (B, "5.00"), (C, "5.00"), (D, "5.00"))


def _one(promotion_id, *items, **more):
    return _promotion(promotion_id, _group(items=list(items)), **more)


def test_on_promotion_counts_a_wide_kind_link_whose_price_is_not_read(tmp_path):
    disagrees = _one("10", _item(A, reward="2", rate="20", price="3.00"))   # 20% off 5.00 is 4.00, not 3.00
    report, rows = _run(tmp_path, LISTED, {"1": [disagrees], "2": [disagrees]})
    row = rows[(SHELI, A)]
    assert row["on_promotion"] is True
    assert _price_on(row) == [("10", "percent_off", Decimal("3.00"), False, "the rate and the price disagree", True)]
    assert (report.columns[SHELI].on_promotion, report.columns[SHELI].valid_deals) == (1, 0)


def test_a_valid_wide_deal_is_on_promotion_and_counted(tmp_path):
    fixed = _one("11", _item(A, reward="3", price="4.00"))
    report, rows = _run(tmp_path, LISTED, {"1": [fixed], "2": [fixed]})
    assert rows[(SHELI, A)]["on_promotion"] is True and rows[(SHELI, B)]["on_promotion"] is False
    assert _price_on(rows[(SHELI, A)]) == [("11", "fixed_price", Decimal("4.00"), True, None, True)]
    assert (report.columns[SHELI].on_promotion, report.columns[SHELI].valid_deals) == (1, 1)
    assert rows[(DEAL, A)]["on_promotion"] is False and rows[(DEAL, A)]["promotions"] == []   # Deal's stores carry none


def test_a_zero_link_only_item_is_not_on_promotion_and_shows_price_not_read(tmp_path):
    zero = _one("20", _item(A, reward="0", price="4.00"))
    _, rows = _run(tmp_path, LISTED, {"1": [zero], "2": [zero]})
    row = rows[(SHELI, A)]
    assert row["on_promotion"] is False
    assert _price_on(row) == [("20", None, None, False, "no kind link", True)]
    assert row["promotions"][0]["price_exact"] is None


def test_a_promotion_at_some_stores_is_not_on_promotion(tmp_path):
    stores = STORES + (_store("7", "1"),)
    fixed = _one("30", _item(A, reward="3", price="4.00"))
    _, rows = _run(tmp_path, {**LISTED, "7": [(A, "5.00")]}, {"1": [fixed]}, stores=stores)
    row = rows[(SHELI, A)]
    assert row["on_promotion"] is False   # 1 of Sheli's 3 counted stores
    assert [(p["promotion_id"], p["stores"], p["wide"]) for p in row["promotions"]] == [("30", 1, False)]


def test_a_coupon_never_reaches_the_outcome(tmp_path):
    coupon = _one("40", _item(A, reward="3", price="4.00"), coupon="1")
    report, rows = _run(tmp_path, LISTED, {"1": [coupon], "2": [coupon]})
    assert rows[(SHELI, A)]["on_promotion"] is False and rows[(SHELI, A)]["promotions"] == []
    assert (report.promotions["coupons"], report.columns[SHELI].on_promotion) == (2, 0)


def test_next_start_is_within_fourteen_days(tmp_path):
    def starting(promotion_id, code, days, reward="3"):
        start = (DAY + timedelta(days=days)).isoformat()
        return _one(promotion_id, _item(code, reward=reward, price="4.00"), start=start, end="2026-12-31")

    assert HORIZON == 14
    carried = [starting("50", A, 14), starting("51", A, 15), starting("52", B, 15), starting("53", C, 0),
               starting("54", C, 3), starting("55", D, 2, reward="0")]
    _, rows = _run(tmp_path, LISTED, {"1": carried, "2": carried})
    assert rows[(SHELI, A)]["next_start"] == DAY + timedelta(days=14)    # d + 14 in, d + 15 out
    assert rows[(SHELI, B)]["next_start"] is None
    assert rows[(SHELI, C)]["next_start"] == DAY + timedelta(days=3)     # not the promotion of the day itself
    assert rows[(SHELI, D)]["next_start"] is None                        # a zero link starts nothing
    assert (rows[(SHELI, A)]["on_promotion"], rows[(SHELI, C)]["on_promotion"]) == (False, True)
    assert [p["promotion_id"] for p in rows[(SHELI, A)]["promotions"]] == ["50", "51"]   # those starting after it too


def test_a_promotion_at_some_stores_starts_nothing(tmp_path):
    stores = STORES + (_store("7", "1"),)
    soon = _one("56", _item(A, reward="3", price="4.00"), start="2026-11-09", end="2026-11-30")
    _, rows = _run(tmp_path, {**LISTED, "7": [(A, "5.00")]}, {"1": [soon]}, stores=stores)
    assert rows[(SHELI, A)]["next_start"] is None


def test_unread_promotions_make_a_promotion_hole_in_every_column_and_no_promotion_rows(tmp_path):
    report, rows = _run(tmp_path, LISTED, error="a promotion field changed")
    assert all(column.promo_hole for column in report.columns.values())
    assert all((row["on_promotion"], row["next_start"], row["promotions"]) == (None, None, None)
               for row in rows.values())
    assert (report.promotions_error, report.promotions, report.texts) == ("a promotion field changed", None, 0)
    assert not texts_path(tmp_path / "tables", SLUG, DAY).exists()
    assert report.columns[SHELI].counted == report.columns[SHELI].with_file == 2


def test_a_column_with_promotion_files_from_under_half_its_counted_stores_is_a_promotion_hole(tmp_path):
    stores = (_store("1", "1"), _store("2", "1"), _store("7", "1"), _store("8", "1"),
              _store("3", "2"), _store("4", "2"), _store("10", "2"), _store("11", "2"))
    fixed = _one("60", _item(A, reward="3", price="4.00"))
    priced = _at(("1", "2", "7", "8", "3", "4", "10", "11"), (A, "5.00"))
    report, _ = _run(tmp_path, priced, {"1": [fixed], "3": [fixed], "4": [fixed]}, stores=stores)
    sheli, deal_ = report.columns[SHELI], report.columns[DEAL]
    assert (sheli.counted, sheli.promo_files, sheli.promo_hole) == (4, 1, True)
    assert (deal_.counted, deal_.promo_files, deal_.promo_hole) == (4, 2, False)   # half is enough


def test_the_deal_price_is_exact_in_the_table(tmp_path):
    six = _one("70", _item(A, reward="1", min_qty="6", price="8.72"))
    _, rows = _run(tmp_path, _at(("1", "2"), (A, "2.00")), {"1": [six], "2": [six]})
    (struct,) = rows[(SHELI, A)]["promotions"]
    assert (struct["price_exact"], struct["price"], struct["buy"], struct["valid"]) == (
        "109/75", Decimal("1.45"), Decimal("6.000"), True)


def test_a_deal_read_back_from_the_table_is_the_deal(tmp_path):
    """A real write and read of the struct through deal_from_row (Task 4's carry): every kind, a weighed link, a MinQty
    of three places, percent off with its stores' range, a zero link and a deal that does not validate."""
    listed = {"1": [(A, "5.50"), (B, "120.00"), (C, "5.00"), (D, "5.00"), (E, "5.00")],
              "2": [(A, "5.50"), (B, "120.00"), (C, "5.00"), (D, "5.00"), (E, "5.00")]}
    at_1 = [_one("80", _item(A, reward="2", rate="20", price="4.40")),
            _one("81", _item(B, reward="1", min_qty="1.5", price="75.00", weighed="1")),
            _one("82", _item(C, reward="10", min_qty="1.125", price="3.00")),
            _one("83", _item(D, reward="0", price="1.00")), _one("84", _item(E, reward="3", price="11.00"))]
    at_2 = [_one("80", _item(A, reward="2", rate="20", price="4.50"))] + at_1[1:]
    raw, tables = tmp_path / "raw", tmp_path / "tables"
    _prices(tables, listed)
    ids = included(list(STORES), SLUG)
    promo = _promotions(raw, tables, STORES, ids, {"1": at_1, "2": at_2})
    write_items(tables, SLUG, DAY, STORES, ids, EXCLUDED[SLUG].sub_chains, promo, None)
    rows = {row["code"]: row for row in _read(items_path(tables, SLUG, DAY)) if row["column"] == SHELI}
    links = {row["code_norm"]: row for row in _read(promotions_path(tables, SLUG, DAY), "code")}
    for code, row in rows.items():
        link = links[code]
        stores = None if link["discounted_median"] is None else StorePrices(
            link["discounted_median"], link["discounted_low"], link["discounted_high"])
        expected = deal(SLUG, json.loads(link["fields"])["item"], row["listed"], stores)
        (struct,) = row["promotions"]
        assert deal_from_row(struct) == expected, code
    assert (rows[A]["promotions"][0]["low"], rows[A]["promotions"][0]["high"]) == (Decimal("4.40"), Decimal("4.50"))
    assert (rows[B]["promotions"][0]["per"], rows[B]["promotions"][0]["price_exact"]) == ("kg", "50")
    assert (rows[C]["promotions"][0]["buy"], rows[C]["promotions"][0]["price"]) == (Decimal("1.125"), Decimal("2.67"))
    assert rows[C]["promotions"][0]["price_exact"] == "8/3"   # 3.00 for 1.125, written half up for the eye
    assert rows[E]["promotions"][0]["valid"] is False   # 11.00 is not below twice 5.00


def test_a_min_qty_the_table_cannot_hold_stops_the_chains_promotions(tmp_path):
    odd = _one("85", _item(A, reward="1", min_qty="1.2345", price="3.00"))
    with pytest.raises(PromotionFormatChanged, match=r"MinQty '1\.2345'"):
        _run(tmp_path, _at(("1", "2"), (A, "5.00")), {"1": [odd], "2": [odd]})
    assert not items_path(tmp_path / "tables", SLUG, DAY).exists()


def test_a_deal_price_too_large_to_show_keeps_its_fraction(tmp_path):
    huge = _one("86", _item(A, reward="3", price="12345678901.00"))
    _, rows = _run(tmp_path, _at(("1", "2"), (A, "5.00")), {"1": [huge], "2": [huge]})
    (struct,) = rows[(SHELI, A)]["promotions"]
    assert (struct["price"], struct["price_exact"], struct["valid"]) == (None, "12345678901", False)
    assert deal_from_row(struct).price == Fraction(12345678901)


def test_an_item_takes_the_kind_link_of_the_lowest_group_as_a_number(tmp_path):
    two_groups = _promotion("90", _group("10", [_item(A, reward="3", price="3.00")]),
                            _group("9", [_item(A, reward="3", price="4.00")]))
    zero_first = _promotion("91", _group("1", [_item(B, reward="0", price="1.00")]),
                            _group("2", [_item(B, reward="3", price="4.50")]))
    _, rows = _run(tmp_path, LISTED, {"1": [two_groups, zero_first], "2": [two_groups, zero_first]})
    assert _price_on(rows[(SHELI, A)]) == [("90", "fixed_price", Decimal("4.00"), True, None, True)]   # group 9's
    assert _price_on(rows[(SHELI, B)]) == [("91", "fixed_price", Decimal("4.50"), True, None, True)]   # not the 0 link


def test_an_items_promotions_are_listed_by_start_then_id_as_a_number(tmp_path):
    first = _one("200", _item(A, reward="3", price="4.20"), start="2026-11-01")
    hundred = _one("100", _item(A, reward="3", price="4.00"), start="2026-11-05")
    ninety_nine = _one("99", _item(A, reward="3", price="4.10"), start="2026-11-05")
    carried = [hundred, ninety_nine, first]
    _, rows = _run(tmp_path, LISTED, {"1": carried, "2": carried})
    assert [p["promotion_id"] for p in rows[(SHELI, A)]["promotions"]] == ["200", "99", "100"]
    struct = rows[(SHELI, A)]["promotions"][0]
    assert (struct["description"], struct["start"], struct["end"], struct["restrictions"], struct["programmes"],
            struct["min_spend"], struct["per"]) == ("מבצע לדוגמה 200", date(2026, 11, 1), date(2026, 11, 28), [], [],
                                                    None, "unit")


def test_a_promotions_conditions_reach_its_struct(tmp_path):
    club = _promotion("110", _group(items=[_item(A, reward="3", price="4.00")], min_purchase="100"), club="1 - a club")
    _, rows = _run(tmp_path, LISTED, {"1": [club], "2": [club]})
    (struct,) = rows[(SHELI, A)]["promotions"]
    assert (struct["restrictions"], struct["programmes"], struct["min_spend"]) == (["club"], ["a club"],
                                                                                 Decimal("100.00"))


# The reader's input (the design's "What the site needs from the reader"; the second pre-flight's S9)

def test_texts_carry_every_input_field_and_the_listed_prices(tmp_path):
    groups = (_group("1", [_item(A, reward="3", price="4.00"), _item(B, reward="3", price="4.00")]),
              _group("2", [], min_purchase="100"))
    text = _promotion("120", *groups)
    other_text = _promotion("120", *groups, description="מבצע אחר")   # the same promotion, another description
    priced = {**_at(("1", "2"), (A, "5.00"), (B, "6.00")), **_at(("3", "4"), (A, "4.00"))}
    report, _ = _run(tmp_path, priced, {"1": [text], "2": [text], "3": [text], "4": [other_text]})
    texts = _read(texts_path(tmp_path / "tables", SLUG, DAY), "promotion_id, description")
    assert report.texts == 2 == len(texts)
    first = next(t for t in texts if t["description"] == "מבצע לדוגמה 120")
    assert (first["chain"], first["promotion_id"], first["start_at"], first["end_at"], first["update_time"],
            first["stores"]) == (SLUG, "120", "2026-11-01T00:00:00.000", "2026-11-28T23:59:00.000",
                                 "2026-10-26T00:00:00.000", 3)
    fields = json.loads(first["fields"])
    assert list(fields) == ["promotion", "groups"]
    assert fields["promotion"]["PromotionID"] == "120" and "Groups" not in fields["promotion"]
    assert [(g["group"]["GroupID"], [item["ItemCode"] for item in g["items"]]) for g in fields["groups"]] == [
        ("1", [A, B]), ("2", [])]
    assert fields["groups"][1]["group"]["MinPurchaseAmount"] == "100"
    listed = json.loads(first["listed"])
    assert listed == {DEAL: {A: "4.00"}, SHELI: {A: "5.00", B: "6.00"}}   # by column, then code; B unlisted at Deal
    assert (list(listed), list(listed[SHELI])) == ([DEAL, SHELI], [A, B])
    second = next(t for t in texts if t["description"] == "מבצע אחר")
    assert (second["stores"], json.loads(second["listed"])) == (1, {DEAL: {A: "4.00"}})   # store 4, a Deal store


def test_the_report_is_written_beside_the_table(tmp_path):
    fixed = _one("130", _item(A, reward="3", price="4.00"))
    later = _one("131", _item(B, reward="3", price="4.00"), start="2026-11-09")   # valid, but not on the day
    report, _ = _run(tmp_path, {**_at(("1", "2"), (A, "5.00"), (B, "5.00")), "3": [(A, "4.00")]},
                     {"1": [fixed, later], "2": [fixed, later]})
    written = json.loads((items_path(tmp_path / "tables", SLUG, DAY).parent / "report.json").read_text())
    assert written == json.loads(json.dumps(asdict(report)))
    sheli = report.columns[SHELI]
    assert (sheli.items, sheli.wide, sheli.on_promotion, sheli.valid_deals, sheli.under_floor) == (2, 2, 1, 1, True)
    assert (report.slug, report.day, report.promotions_error, report.texts) == (SLUG, "2026-11-07", None, 2)
    assert report.promotions["files"] == [_name("1"), _name("2")] and "texts" not in report.promotions


def test_a_whole_chain_is_never_under_the_floor(tmp_path):
    data = golden_tree(tmp_path)
    raw, tables = data / "raw", data / "tables"
    extract(raw, "osherad", GOLDEN_DAY, tables)
    stores, _ = chain_stores(raw, "osherad", GOLDEN_DAY)
    report = write_items(tables, "osherad", GOLDEN_DAY, stores, included(stores, "osherad"), frozenset(), None, None)
    assert report.columns["osherad"].under_floor is False


# basket.rules read through another view, for every code (the second pre-flight's S3)

def test_chain_prices_and_sizes_read_the_view_named_for_every_code(tmp_path):
    with duckdb.connect() as con:
        con.execute("CREATE VIEW other AS SELECT * FROM (VALUES ('x', '8', '1', 2.00::DECIMAL(12,2), '1', 'ליטר'), "
                    "('x', '8', '2', 3.00::DECIMAL(12,2), '1', 'ליטר'), ('x', '9', '1', 1.00::DECIMAL(12,2), '', '')) "
                    "t(chain, code_norm, store, price, quantity, unit)")
        every = chain_prices(con, None, rows="other")
        some = chain_prices(con, ["8"], rows="other")
        sizes = chain_sizes(con, None, rows="other")
        sized = chain_sizes(con, ["9"], rows="other")
    assert {key: (price.median, price.listing) for key, price in every.items()} == {
        ("x", "8"): (Decimal("2.50"), 2), ("x", "9"): (Decimal("1.00"), 1)}
    assert list(some) == [("x", "8")]
    assert sizes == {("x", "8"): Size(Decimal(1000), "gml"), ("x", "9"): None} and sized == {("x", "9"): None}

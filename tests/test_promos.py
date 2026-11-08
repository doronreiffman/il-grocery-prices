"""The day's promotions table: a row per column, promotion, group and item code, counted at the column's counted stores
(P3, Call 7; the plan's Task 5 and the second pre-flight's S2, S3, S9 to S12 and S19)."""
import gzip
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import duckdb
import pytest

from basket.barcode import is_gs1, normalize
from basket.extract import Row, table_path, write_table
from basket.pricefile import BadPriceFile
from basket.rules import MissingTable, store_prices_sql
from shopper.promofile import PromotionFormatChanged
from shopper.promos import extract_promotions, promotions_path

FIXTURES = Path(__file__).parent / "fixtures"
SHUFERSAL = "7290027600007"
DAY = date(2026, 11, 7)
ITEM_TAGS = ("ItemCode", "ItemType", "RewardType", "MinQty", "MaxQty", "DiscountRate", "DiscountedPrice",
             "DiscountedPricePerMida", "bIsWeighted")
A, B, C = "2000000000046", "2000000000053", "2000000000060"   # synthetic barcodes, as the fixtures carry


def _item(code=A, reward="3", min_qty="1", rate="", price="5.00", weighed="0"):
    values = {"ItemCode": code, "ItemType": "1", "RewardType": reward, "MinQty": min_qty, "MaxQty": "",
              "DiscountRate": rate, "DiscountedPrice": price, "DiscountedPricePerMida": "", "bIsWeighted": weighed}
    return "<PromotionItem>" + "".join(f"<{tag}>{values[tag]}</{tag}>" for tag in ITEM_TAGS) + "</PromotionItem>"


def _group(group_id="1", items=(), min_purchase="", discount_type=""):
    return (f"<Group><GroupID>{group_id}</GroupID><MinPurchaseAmount>{min_purchase}</MinPurchaseAmount>"
            f"<DiscountType>{discount_type}</DiscountType><PromotionItems>{''.join(items)}</PromotionItems></Group>")


def _promotion(promotion_id, *groups, start="2026-11-01", end="2026-11-28", club="0 - a label", coupon="0",
               updated="2026-10-26T00:00:00.000", description=None):
    groups = groups or (_group(items=[_item()]),)
    fields = {"PromotionUpdateTime": updated, "AllowMultipleDiscounts": "1", "PromotionID": promotion_id,
              "PromotionDescription": f"מבצע לדוגמה {promotion_id}" if description is None else description,
              "PromotionStartDateTime": f"{start}T00:00:00.000", "PromotionEndDateTime": f"{end}T23:59:00.000",
              "PromotionStartHour": "", "PromotionEndHour": "", "PromotionDays": "", "RedemptionLimit": "",
              "MinNoOfItemOffered": "10", "ClubID": club, "IsGiftItem": "", "AdditionalIsCoupon": coupon,
              "AdditionalRestrictions": "", "Remarks": ""}
    return ("<Promotion>" + "".join(f"<{tag}>{escape(value)}</{tag}>" for tag, value in fields.items())
            + "<Groups>" + "".join(groups) + "</Groups></Promotion>")


def _file(store, *promotions, extra_root=""):
    xml = (f"<Root><ChainID>{SHUFERSAL}</ChainID><SubChainID>001</SubChainID><StoreID>{store}</StoreID>"
           "<BikoretNo>0</BikoretNo><Promotions>" + "".join(promotions) + "</Promotions>" + extra_root + "</Root>")
    return gzip.compress(xml.encode(), mtime=0)


def _name(store, sub_chain="001", time="030000"):
    return f"PromoFull{SHUFERSAL}-{sub_chain}-{int(store):03d}-20261107-{time}.gz"


def _write_day(tmp_path, files, priced=None, slug="shufersal", day=DAY):
    """The raw files of the day and its prices table, written with basket.extract's writer (`priced`: store -> its
    (code, price) rows; none by default). The raw and the tables folders."""
    raw, tables = tmp_path / "raw", tmp_path / "tables"
    folder = raw / f"chain={slug}" / f"date={day.isoformat()}"
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    rows = [Row(store, "1", code, normalize(code), is_gs1(code), "מוצר", Decimal(price), "", "", "", "", "PriceFull")
            for store, items in (priced or {}).items() for code, price in items]
    write_table(rows, table_path(tables, slug, day))
    return raw, tables


def _read(path):
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT * FROM read_parquet('{path}', hive_partitioning = false) "
                             "ORDER BY \"column\", promotion_id, group_id, code")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def _run(tmp_path, files, counted, outside=frozenset(), priced=None, slug="shufersal", day=DAY):
    raw, tables = _write_day(tmp_path, files, priced, slug, day)
    report = extract_promotions(raw, slug, day, counted, tables, outside)
    return report, _read(promotions_path(tables, slug, day))


def _keys(rows, *names):
    return [tuple(row[name] for name in names) for row in rows]


FIXTURE_DAYS = {  # each promotion fixture: its chain, its day, a column of its chain and its store
    "shufersal/PromoFull7290027600007-000-878-20261031-030000.gz": ("shufersal", date(2026, 10, 31), "shufersal-deal",
                                                                    "878"),
    "shufersal/PromoFull7290027600007-001-001-20261107-030000.gz": ("shufersal", DAY, "shufersal-sheli", "1"),
    "ncr/PromoFull7290058140886-001-731-20261101-001049.gz": ("ramilevy", date(2026, 11, 1), "ramilevy", "731"),
    "ncr/PromoFull7290103152017-001-001-20261107-110530.gz": ("osherad", DAY, "osherad", "1"),
    # store 472 is a type-2 store in no column of the real table; the test's own counted puts it in City
    "carrefour/PromoFull7290055700007-001-472-20261031-051058.gz": ("carrefour", date(2026, 10, 31), "carrefour-city",
                                                                    "472"),
    "ncr/PromoFull7290803800003-000-001-20261107-004032.gz": ("yochananof", DAY, "yochananof", "1"),
}
FIFTY, HUNDRED = Decimal("50.00"), Decimal("100.00")
FIXTURE_ROWS = {  # (promotion, group, code, kind, min spend); every row 1 store of 1 counted, wide
    "shufersal/PromoFull7290027600007-000-878-20261031-030000.gz": [],   # three coupons
    "shufersal/PromoFull7290027600007-001-001-20261107-030000.gz": [
        ("900001", "1", A, "percent_off", None), ("900002", "1", B, "fixed_price", HUNDRED),
        ("900002", "2", "0000000000000", None, HUNDRED)],   # the basket condition, a RewardType 0 link
    "ncr/PromoFull7290058140886-001-731-20261101-001049.gz": [   # 900003 is a coupon
        ("900001", "1", A, "n_for_m", FIFTY), ("900002", "1", B, "n_for_m", FIFTY)],
    "ncr/PromoFull7290103152017-001-001-20261107-110530.gz": [   # 900001's first group has no items; 0.00 is none
        ("900001", "2", A, "fixed_price", None), ("900002", "1", B, "n_for_m", None),
        ("900003", "1", C, "n_for_m", None)],
    "carrefour/PromoFull7290055700007-001-472-20261031-051058.gz": [   # 900002 is a coupon; 900003 ends on the day
        ("900001", "1", A, "fixed_price", FIFTY), ("900003", "1", C, "n_for_m", FIFTY)],
    "ncr/PromoFull7290803800003-000-001-20261107-004032.gz": [
        ("900001", "1", A, "n_for_m", FIFTY), ("900001", "2", B, None, FIFTY), ("900002", "1", C, "fixed_price", None)],
}


@pytest.mark.parametrize("fixture", sorted(FIXTURE_DAYS))
def test_each_fixture_gives_its_rows(tmp_path, fixture):
    slug, day, column, store = FIXTURE_DAYS[fixture]
    path = FIXTURES / fixture
    report, rows = _run(tmp_path, {path.name: path.read_bytes()}, {column: {store}}, slug=slug, day=day,
                        priced={store: [(A, "12.90")]})
    assert _keys(rows, "promotion_id", "group_id", "code", "kind", "min_spend") == FIXTURE_ROWS[fixture]
    assert all((row["column"], row["stores"], row["promotion_stores"], row["counted"], row["wide"], row["variants"])
               == (column, 1, 1, 1, True, 1) for row in rows)
    assert (report.files, report.counted, report.promo_files, report.rows) == ([path.name], {column: 1}, {column: 1},
                                                                               len(rows))
    if slug == "shufersal" and rows:   # percent off 50 at 6.45, the store's own price 12.90
        assert _keys(rows[:1], "discounted_median", "discounted_low", "discounted_high", "with_store_price",
                     "agrees_with_store") == [(Decimal("6.45"), Decimal("6.45"), Decimal("6.45"), 1, 1)]
    if slug == "yochananof":   # a weighed "N kg for ₪M", and a promotion for the chain's employees' club
        assert (rows[0]["weighed"], rows[2]["restrictions"], rows[2]["programmes"]) == (True, ["club"],
                                                                                       ["מועדון עובדים"])


def test_rows_are_keyed_by_promotion_group_and_code(tmp_path):
    early, late = "2026-10-26T00:00:00.000", "2026-10-27T00:00:00.000"
    most = _promotion("10", _group(items=[_item(price="4.00")]), updated=early)
    fewer = _promotion("10", _group(items=[_item(price="4.10")]), updated=late)
    nine = _promotion("20", _group(items=[_item(B, price="7.00")]), updated=early)
    ten = _promotion("20", _group(items=[_item(B, price="7.50")]), updated=late)
    files = {_name("1"): _file("1", fewer), _name("2"): _file("2", most, most),   # store 2 lists it twice
             _name("3"): _file("3", most), _name("9"): _file("9", nine), _name("10"): _file("10", ten)}
    report, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2", "3", "9", "10"}})
    # one row a link, whatever its copies; the variant most stores carry (not the lowest store's, store 1's), and on a
    # tie the lowest store's (9 before 10, as numbers)
    assert _keys(rows, "promotion_id", "stores", "variants", "update_time", "discounted_price") == [
        ("10", 3, 2, early, "4.00"), ("20", 2, 2, early, "7.00")]
    fields = json.loads(rows[0]["fields"])
    assert list(fields) == ["promotion", "group", "item"]   # the pre-flight's S11
    assert (fields["promotion"]["PromotionUpdateTime"], fields["group"], fields["item"]["DiscountedPrice"]) == (
        early, {"GroupID": "1", "MinPurchaseAmount": "", "DiscountType": ""}, "4.00")
    assert "Groups" not in fields["promotion"] and "PromotionItems" not in fields["group"]
    assert (report.promotions, report.rows) == (6, 2)   # store 2's two copies both read
    assert [text.stores for text in report.texts] == [("1", "2", "3"), ("9", "10")]   # each store once


def test_a_store_listing_a_link_twice_counts_once_at_its_lowest_price(tmp_path):
    twice = (_promotion("63", _group(items=[_item(price="9.00")])),
             _promotion("63", _group(items=[_item(price="3.00")])))
    files = {_name("1"): _file("1", *twice), _name("2"): _file("2", _promotion("63", _group(items=[_item()])))}
    _, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2"}})
    assert _keys(rows, "stores", "discounted_median", "discounted_low", "discounted_high") == [
        (2, Decimal("4.00"), Decimal("3.00"), Decimal("5.00"))]   # 3.00 and 5.00, not 9.00


def test_wide_is_half_the_columns_counted_stores(tmp_path):
    files = {_name("1"): _file("1", _promotion("11"), _promotion("12")), _name("2"): _file("2", _promotion("12")),
             _name("3"): _file("3"), _name("4"): _file("4", _promotion("13")), _name("5"): _file("5", _promotion("13")),
             _name("6"): _file("6")}   # Deal's store 7 is counted with no promotion file
    report, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2", "3"}, "shufersal-deal": {"4", "5", "6", "7"}})
    assert _keys(rows, "column", "promotion_id", "stores", "counted", "wide") == [
        ("shufersal-deal", "13", 2, 4, True), ("shufersal-sheli", "11", 1, 3, False),
        ("shufersal-sheli", "12", 2, 3, True)]
    assert (report.counted, report.promo_files) == ({"shufersal-deal": 4, "shufersal-sheli": 3},
                                                    {"shufersal-deal": 3, "shufersal-sheli": 3})


def test_a_promotion_wide_in_one_column_is_not_wide_in_another(tmp_path):
    files = {_name("4"): _file("4", _promotion("30")), _name("5"): _file("5", _promotion("30")),
             **{_name(store): _file(store, _promotion("31")) for store in ("1", "2", "3")}}
    _, rows = _run(tmp_path, files, {"shufersal-deal": {"4", "5"}, "shufersal-sheli": {"1", "2", "3"}})
    assert _keys(rows, "column", "promotion_id", "stores", "counted", "wide") == [
        ("shufersal-deal", "30", 2, 2, True), ("shufersal-sheli", "31", 3, 3, True)]


def test_files_of_stores_not_counted_are_not_read(tmp_path):
    # store 413 (B2 leaves it out) and store 779, whose price file was named under Be's 005 on 2026-11-02, so it is
    # not counted: their promotion files are passed over unread
    store_413, store_779 = _name("413", "002"), _name("779", "007")
    report, rows = _run(tmp_path, {_name("1"): _file("1", _promotion("10")), store_413: b"not read",
                                   store_779: b"not read"}, {"shufersal-express": {"1"}})
    assert (report.files, report.passed_over, report.outside) == ([_name("1")], sorted([store_413, store_779]), [])
    assert _keys(rows, "promotion_id") == [("10",)]


def test_counted_stores_in_no_column_are_passed_over_unread(tmp_path):
    yesh_chesed = _name("60", "006")   # a counted store in no column (sub-chain 6)
    report, _ = _run(tmp_path, {_name("1"): _file("1", _promotion("10")), yesh_chesed: b"not read"},
                     {"shufersal-sheli": {"1"}}, outside={"60"})
    assert (report.files, report.passed_over, report.outside) == ([_name("1")], [], [yesh_chesed])


def test_each_stores_latest_file_is_read(tmp_path):
    early, late = _name("1", time="030000"), _name("1", time="090000")
    report, rows = _run(tmp_path, {early: _file("1", _promotion("10")), late: _file("1", _promotion("20"))},
                        {"shufersal-sheli": {"1"}})
    assert (report.files, report.passed_over, _keys(rows, "promotion_id")) == ([late], [early], [("20",)])


def test_a_voucher_of_thousands_of_items_is_counted_not_kept(tmp_path):
    voucher = _promotion("80", _group(items=[_item(f"{n:013d}", reward="0", price="") for n in range(1, 2001)]),
                         coupon="1")
    report, rows = _run(tmp_path, {_name("1"): _file("1", voucher, _promotion("81"))}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "promotion_id") == [("81",)]
    assert (report.promotions, report.coupons, report.dropped_links) == (2, 1, 2000)


def test_a_reward_type_12_or_6_promotion_is_dropped_whole_and_counted(tmp_path):
    card = _promotion("40", _group(items=[_item(A, reward="12", price="10.00"), _item(B, reward="1", min_qty="2",
                                                                                      price="9.00")]),
                      _group("2", items=[_item(C, reward="1", min_qty="3", price="12.00")]))
    gift = _promotion("41", _group(items=[_item(A, reward="6", price=""), _item(B, reward="3", price="4.00")]))
    report, rows = _run(tmp_path, {_name("1"): _file("1", card, gift, _promotion("42"))}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "promotion_id") == [("42",)]   # the "N for ₪M" links went with their promotions
    assert (report.basket_rewards, report.gifts, report.dropped_links) == (1, 1, 5)


def test_zero_links_are_kept_without_a_kind(tmp_path):
    two_groups = _promotion("50", _group(items=[_item(A, reward="0", price="21.90")]),
                            _group("2", items=[_item(B, reward="3", price="8.00")]))
    _, rows = _run(tmp_path, {_name("1"): _file("1", two_groups)}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "group_id", "code", "reward_type", "kind") == [("1", A, "0", None), ("2", B, "3", "fixed_price")]


def test_min_spend_on_an_item_less_group(tmp_path):
    promotion = _promotion("55", _group(items=[_item()]), _group("2", min_purchase="75.00"))   # the pre-flight's S5
    _, rows = _run(tmp_path, {_name("1"): _file("1", promotion)}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "group_id", "min_spend") == [("1", Decimal("75.00"))]


def test_min_spend_on_the_zero_group_is_the_promotions(tmp_path):
    promotion = _promotion("56", _group(items=[_item(A, reward="0", price="")], min_purchase="75.00"),
                           _group("2", items=[_item(B, reward="1", min_qty="2", price="9.00")]))   # S2
    _, rows = _run(tmp_path, {_name("1"): _file("1", promotion)}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "group_id", "kind", "min_spend") == [("1", None, Decimal("75.00")),
                                                            ("2", "n_for_m", Decimal("75.00"))]


def test_a_min_spend_too_large_for_the_table_stops_the_chain(tmp_path):
    promotion = _promotion("57", _group(items=[_item()], min_purchase="10000000000.00"))
    raw, tables = _write_day(tmp_path, {_name("1"): _file("1", promotion)})
    with pytest.raises(PromotionFormatChanged, match=r"^MinPurchaseAmount 10000000000.00 does not fit the table$"):
        extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1"}}, tables, frozenset())


def test_percent_off_carries_the_stores_median_range_and_agreement(tmp_path):
    def percent_off(*items):
        return _promotion("60", _group(items=list(items)))
    files = {_name("1"): _file("1", percent_off(_item(A, "2", rate="20", price="4.40")),
                               _promotion("61", _group(items=[_item(C, price="3.00")]))),
             _name("2"): _file("2", percent_off(_item(A, "2", rate="20", price="4.48"))),
             _name("3"): _file("3", percent_off(_item(A, "2", rate="20", price="4.50"))),
             _name("4"): _file("4", percent_off(_item(B, "2", rate="20", price="2.00")))}   # the promotion, not A
    priced = {"1": [(A, "5.50")], "2": [(A, "5.60")], "3": [(A, "5.50")], "4": [(A, "5.50"), (B, "2.50")]}
    _, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2", "3", "4"}}, priced=priced)
    # A: 4.40 at 5.50 and 4.48 at 5.60 agree with their own store's price x 0.80, 4.50 at 5.50 does not; store 4
    # carries the promotion but not the link, and lists A without it
    assert _keys(rows, "promotion_id", "code", "discounted_median", "discounted_low", "discounted_high",
                 "with_store_price", "agrees_with_store", "stores", "promotion_stores", "counted", "wide") == [
        ("60", A, Decimal("4.48"), Decimal("4.40"), Decimal("4.50"), 3, 2, 3, 4, 4, True),
        ("60", B, Decimal("2.00"), Decimal("2.00"), Decimal("2.00"), 1, 1, 1, 4, 4, False),
        ("61", C, Decimal("3.00"), Decimal("3.00"), Decimal("3.00"), None, None, 1, 1, 4, False)]   # not percent off


def test_a_store_price_too_large_for_the_table_is_no_price(tmp_path):
    files = {_name("1"): _file("1", _promotion("62", _group(items=[_item(price="1000000000.00")]))),
             _name("2"): _file("2", _promotion("62", _group(items=[_item(price="4.00")])))}
    _, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2"}})
    assert _keys(rows, "stores", "discounted_median", "discounted_low", "discounted_high") == [
        (2, Decimal("4.00"), Decimal("4.00"), Decimal("4.00"))]


def test_an_expired_promotion_is_counted_and_a_future_one_kept(tmp_path):
    promotions = [_promotion("70", end="2026-11-06"), _promotion("71", end="2026-11-07"),
                  _promotion("72", start="2026-11-08"), _promotion("73", start="2026-11-07")]
    report, rows = _run(tmp_path, {_name("1"): _file("1", *promotions)}, {"shufersal-sheli": {"1"}})
    assert _keys(rows, "promotion_id", "start", "end") == [("71", date(2026, 11, 1), date(2026, 11, 7)),
                                                          ("72", date(2026, 11, 8), date(2026, 11, 28)),
                                                          ("73", date(2026, 11, 7), date(2026, 11, 28))]
    assert (report.promotions, report.expired, report.before_start, report.dropped_links) == (4, 1, 1, 1)


def test_hebrew_quotes_commas_and_line_breaks_round_trip(tmp_path):
    description = 'מבצע "1+1", בדיקה\nשורה <שנייה> & סוף'
    club = '(1=מועדון "א", ב|0=C)'
    promotion = _promotion("90", _group(items=[_item(price="")]), description=description, club=club)
    report, rows = _run(tmp_path, {_name("1"): _file("1", promotion)}, {"shufersal-sheli": {"1"}})
    row = rows[0]
    assert (row["description"], row["restrictions"], row["programmes"]) == (description, ["club", "other"],
                                                                            ['מועדון "א", ב', "C"])
    fields = json.loads(row["fields"])
    assert (fields["promotion"]["PromotionDescription"], fields["promotion"]["ClubID"]) == (description, club)
    assert (row["discounted_price"], row["min_qty"], row["max_qty"], row["discounted_median"]) == ("", "1", "", None)
    assert [text.description for text in report.texts] == [description]


def test_two_stores_copies_with_different_descriptions_give_two_texts(tmp_path):
    files = {_name("1"): _file("1", _promotion("75", description="מבצע לדוגמה 1"), _promotion("76", coupon="1"),
                               _promotion("77", end="2026-11-06")),
             _name("2"): _file("2", _promotion("75", description="מבצע לדוגמה 2")),
             _name("3"): _file("3", _promotion("75", description="מבצע לדוגמה 1"))}
    report, rows = _run(tmp_path, files, {"shufersal-sheli": {"1", "2"}, "shufersal-deal": {"3"}})
    # the second pre-flight's S9: every kept copy's text, all stores; the coupon and the expired promotion carry none
    assert [(text.promotion_id, text.description, text.start_at, text.end_at, text.stores)
            for text in report.texts] == [
        ("75", "מבצע לדוגמה 1", "2026-11-01T00:00:00.000", "2026-11-28T23:59:00.000", ("1", "3")),
        ("75", "מבצע לדוגמה 2", "2026-11-01T00:00:00.000", "2026-11-28T23:59:00.000", ("2",))]
    assert report.texts[0].record.fields["PromotionDescription"] == "מבצע לדוגמה 1"   # store 1's copy, for its fields
    assert len(rows) == 2


def test_a_day_with_no_files_writes_the_columns(tmp_path):
    raw, tables = _write_day(tmp_path, {})
    report = extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1", "2"}, "shufersal-deal": set()},
                                tables, frozenset())
    path = promotions_path(tables, "shufersal", DAY)
    assert path == tables / "promotions" / "chain=shufersal" / "date=2026-11-07" / "promotions.parquet"
    with duckdb.connect() as con:
        schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}', hive_partitioning = false)").fetchall()
        assert con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone() == (0,)
    assert [(name, kind) for name, kind, *_ in schema] == [
        ("column", "VARCHAR"), ("promotion_id", "VARCHAR"), ("description", "VARCHAR"), ("start_at", "VARCHAR"),
        ("end_at", "VARCHAR"), ("start", "DATE"), ("end", "DATE"), ("update_time", "VARCHAR"),
        ("restrictions", "VARCHAR[]"), ("programmes", "VARCHAR[]"), ("min_spend", "DECIMAL(12,2)"),
        ("group_id", "VARCHAR"), ("code", "VARCHAR"), ("code_norm", "VARCHAR"), ("gs1", "BOOLEAN"),
        ("reward_type", "VARCHAR"), ("kind", "VARCHAR"), ("min_qty", "VARCHAR"), ("max_qty", "VARCHAR"),
        ("discount_rate", "VARCHAR"), ("discounted_price", "VARCHAR"), ("weighed", "BOOLEAN"), ("fields", "VARCHAR"),
        ("variants", "INTEGER"), ("discounted_median", "DECIMAL(12,3)"), ("discounted_low", "DECIMAL(12,3)"),
        ("discounted_high", "DECIMAL(12,3)"), ("with_store_price", "INTEGER"), ("agrees_with_store", "INTEGER"),
        ("stores", "INTEGER"), ("promotion_stores", "INTEGER"), ("counted", "INTEGER"), ("wide", "BOOLEAN")]
    written = json.loads((path.parent / "report.json").read_text())
    assert written == {"slug": "shufersal", "day": "2026-11-07", "counted": {"shufersal-deal": 0, "shufersal-sheli": 2},
                       "files": [], "passed_over": [], "outside": [],
                       "promo_files": {"shufersal-deal": 0, "shufersal-sheli": 0}, "promotions": 0, "coupons": 0,
                       "gifts": 0, "basket_rewards": 0, "dropped_links": 0, "expired": 0, "before_start": 0,
                       "rows": 0}   # the texts stay out of the report
    assert written == report.summary() and report.texts == ()


def test_a_format_change_raises_naming_the_field_and_writes_no_table(tmp_path):
    # the root field comes after the file's promotions, so the reader refuses it only at </Root>: the file's records
    # are taken whole first, so its unknown RewardType is never reached before the root's refusal
    unknown = _promotion("95", _group(items=[_item(reward="99")]))
    changed = _name("2")
    raw, tables = _write_day(tmp_path, {_name("1"): _file("1", _promotion("10")),
                                        changed: _file("2", _promotion("10"), unknown, extra_root="<Extra>1</Extra>")})
    with pytest.raises(PromotionFormatChanged) as refused:
        extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1", "2"}}, tables, frozenset())
    assert str(refused.value) == f"{changed}: root fields changed: added ['Extra'], missing []"
    folder = promotions_path(tables, "shufersal", DAY).parent
    assert not folder.exists() or list(folder.iterdir()) == []


@pytest.mark.parametrize("group, message", [
    (_group(items=[_item(reward="99")]), "shufersal: RewardType 99 not seen in the chain's files"),
    (_group(items=[_item()], discount_type="9"), "shufersal: DiscountType 9 not seen in the chain's files"),
], ids=["reward type", "discount type"])
def test_an_unknown_reward_type_in_a_kept_promotion_raises(tmp_path, group, message):
    raw, tables = _write_day(tmp_path, {_name("1"): _file("1", _promotion("96", group))})
    with pytest.raises(PromotionFormatChanged, match=f"^{message}$"):
        extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1"}}, tables, frozenset())
    assert not promotions_path(tables, "shufersal", DAY).exists()


def test_a_counted_stores_file_that_does_not_read_stops_with_bad_price_file(tmp_path):
    raw, tables = _write_day(tmp_path, {_name("1"): b"<html>not a promotion file</html>"})
    with pytest.raises(BadPriceFile):   # Task 7 takes it as a format change (the second pre-flight's S8)
        extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1"}}, tables, frozenset())
    assert not promotions_path(tables, "shufersal", DAY).exists()


def test_a_day_without_its_prices_table_stops_with_missing_table(tmp_path):
    raw = tmp_path / "raw"
    (raw / "chain=shufersal" / "date=2026-11-07").mkdir(parents=True)
    with pytest.raises(MissingTable, match="shufersal"):
        extract_promotions(raw, "shufersal", DAY, {"shufersal-sheli": {"1"}}, tmp_path / "tables", frozenset())


def test_store_prices_sql_reads_the_view_named_with_or_without_the_codes(tmp_path):
    with duckdb.connect() as con:
        con.execute("CREATE VIEW other AS SELECT * FROM (VALUES ('s', '7', '1', 4.00), ('s', '7', '1', 3.50), "
                    "('s', '8', '1', 2.00), ('s', '7', '2', 5.00)) v(chain, code_norm, store, price)")
        every = con.execute(f"SELECT * FROM ({store_prices_sql('other', codes=False)}) ORDER BY ALL").fetchall()
        some = con.execute(f"SELECT * FROM ({store_prices_sql('other')}) ORDER BY ALL", [["8"]]).fetchall()
    assert every == [("s", "7", "1", Decimal("3.50"), 2), ("s", "7", "2", Decimal("5.00"), 1),
                     ("s", "8", "1", Decimal("2.00"), 1)]   # one price a store, its lowest; its rows beside it
    assert some == [("s", "8", "1", Decimal("2.00"), 1)]

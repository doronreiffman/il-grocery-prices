"""The promotion survey: one chain's day of promotion files measured, each store's latest file once, nothing written."""
import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from basket.build import NoStoreList
from basket.extract import extract
from shopper.survey import BIG_COUPON, carried_by_half, main, survey

FIXTURES = Path(__file__).parent / "fixtures"
RAMI_LEVY = FIXTURES / "ncr" / "PromoFull7290058140886-001-731-20261101-001049.gz"
CARREFOUR = FIXTURES / "carrefour" / "PromoFull7290055700007-001-472-20261031-051058.gz"
SHUFERSAL = FIXTURES / "shufersal" / "PromoFull7290027600007-000-878-20261031-030000.gz"
RAMI_DAY = date(2026, 11, 1)
CARREFOUR_DAY = date(2026, 10, 31)
RAMI = "7290058140886"
ITEM_TAGS = ("ItemCode", "ItemType", "RewardType", "MinQty", "MaxQty", "DiscountRate", "DiscountedPrice",
             "DiscountedPricePerMida", "bIsWeighted")


def _stores_xml(chain_id: str, stores: dict[str, str]) -> bytes:
    """A store list: store id -> its sub-chain."""
    by_sub_chain: dict[str, list[str]] = {}
    for store, sub_chain in stores.items():
        by_sub_chain.setdefault(sub_chain, []).append(store)
    body = "".join(f"<SubChain><SubChainID>{sub}</SubChainID><Stores>"
                   + "".join(f"<Store><StoreID>{s}</StoreID><StoreName>סניף לדוגמה</StoreName><StoreType>1</StoreType>"
                             "</Store>" for s in ids) + "</Stores></SubChain>" for sub, ids in by_sub_chain.items())
    return f"<Root><ChainID>{chain_id}</ChainID><SubChains>{body}</SubChains></Root>".encode()


def _price_file(*items: tuple[str, str]) -> bytes:
    body = "".join(f"<Item><ItemCode>{code}</ItemCode><ItemName>מוצר</ItemName><ItemPrice>{price}</ItemPrice></Item>"
                   for code, price in items)
    return gzip.compress(f"<Root><Items>{body}</Items></Root>".encode(), mtime=0)


def _item(code="2000000000046", reward="3", min_qty="1", max_qty="", rate="", price="5.00"):
    values = {"ItemCode": code, "ItemType": "1", "RewardType": reward, "MinQty": min_qty, "MaxQty": max_qty,
              "DiscountRate": rate, "DiscountedPrice": price, "DiscountedPricePerMida": "", "bIsWeighted": "0"}
    return "<PromotionItem>" + "".join(f"<{tag}>{values[tag]}</{tag}>" for tag in ITEM_TAGS) + "</PromotionItem>"


def _group(group_id="1", items=None, min_purchase="", discount_type=""):
    inside = "" if items is None else "<PromotionItems>" + "".join(items) + "</PromotionItems>"
    return (f"<Group><GroupID>{group_id}</GroupID><MinPurchaseAmount>{min_purchase}</MinPurchaseAmount>"
            f"<DiscountType>{discount_type}</DiscountType>{inside}</Group>")


def _promotion(promotion_id, groups=None, start="2026-11-01", end="2026-11-28", club="0", gift="", coupon="0",
               description=None, remarks=True):
    groups = [_group(items=[_item()])] if groups is None else groups
    description = f"מבצע לדוגמה {promotion_id}" if description is None else description
    return (f"<Promotion><PromotionUpdateTime>2026-10-26T00:00:00.000</PromotionUpdateTime>"
            f"<PromotionID>{promotion_id}</PromotionID><PromotionDescription>{description}</PromotionDescription>"
            f"<PromotionStartDateTime>{start}T00:00:00.000</PromotionStartDateTime>"
            f"<PromotionEndDateTime>{end}T23:59:00.000</PromotionEndDateTime>"
            f"<ClubID>{club}</ClubID><IsGiftItem>{gift}</IsGiftItem><AdditionalIsCoupon>{coupon}</AdditionalIsCoupon>"
            + ("<Remarks/>" if remarks else "") + "<Groups>" + "".join(groups) + "</Groups></Promotion>")


def _promo_file(store: str, *promotions: str) -> bytes:
    return gzip.compress((f"<Root><ChainID>{RAMI}</ChainID><SubChainID>001</SubChainID><StoreID>{store}</StoreID>"
                          "<BikoretNo>0</BikoretNo><Promotions>" + "".join(promotions)
                          + "</Promotions></Root>").encode(), mtime=0)


def _day(tmp_path: Path, slug: str, day: date, chain_id: str, stores: dict[str, str], files: dict[str, bytes],
         priced: dict[str, list[tuple[str, str]]] | None = None) -> tuple[Path, Path]:
    """A chain's day: its store list, a price file for each store of `priced` (store -> its items; every store by
    default, each one item), the promotion files `files`; and its prices table extracted. The raw and tables dirs."""
    raw, tables = tmp_path / "raw", tmp_path / "tables"
    folder = raw / f"chain={slug}" / f"date={day.isoformat()}"
    folder.mkdir(parents=True)
    stamp = day.strftime("%Y%m%d")
    (folder / f"Stores{chain_id}-000-{stamp}-050500.xml").write_bytes(_stores_xml(chain_id, stores))
    priced = {store: [("2000000000015", "10.90")] for store in stores} if priced is None else priced
    for store, items in priced.items():
        (folder / f"PriceFull{chain_id}-001-{store}-{stamp}-001016.gz").write_bytes(_price_file(*items))
    for name, data in files.items():
        (folder / name).write_bytes(data)
    extract(raw, slug, day, tables)
    return raw, tables


def _rami_name(store: str, time: str = "001049") -> str:
    return f"PromoFull{RAMI}-001-{store}-20261101-{time}.gz"


def _rami(tmp_path, files: dict[str, bytes], stores=("731",), priced=None, sub_chains=None):
    stores = {store: (sub_chains or {}).get(store, "001") for store in stores}
    raw, tables = _day(tmp_path, "ramilevy", RAMI_DAY, RAMI, stores, files, priced)
    return survey(raw, tables, "ramilevy", RAMI_DAY)


def test_counts_each_stores_latest_file_once(tmp_path):
    early, late = _rami_name("731", "001049"), _rami_name("731", "071049")
    found = _rami(tmp_path, {early: RAMI_LEVY.read_bytes(), late: RAMI_LEVY.read_bytes()})
    assert (found["files"], found["passed_over"]) == ([late], [early])
    assert (found["promotions"], found["links"], found["links_per_store"]) == (3, 3, {"731": 3})
    assert found["field_sets"]["promotion"][0]["files"] == 1


def test_files_of_stores_not_included_are_passed_over_unread(tmp_path):
    store_039 = f"promofull{RAMI}-039-202611010514.gz"  # Rami Levy's store 039 is left out (B2)
    found = _rami(tmp_path, {_rami_name("731"): RAMI_LEVY.read_bytes(), store_039: b"not read"},
                  stores=("731", "039"))
    assert (found["files"], found["not_included"]) == ([_rami_name("731")], [store_039])
    assert found["stores"] == {"included": 1, "counted": 1, "with_promotion_file": 1,
                               "counted_with_promotion_file": 1}


def test_counts_gift_codes_against_min_qty(tmp_path):
    found = _rami(tmp_path, {_rami_name("731"): RAMI_LEVY.read_bytes()})
    assert found["gift_vs_min_qty"] == {"links": 3, "equal": 3, "by_value": {"2": [2, 2], "6": [1, 1]}}


def test_a_gift_code_that_differs_from_min_qty_is_not_equal(tmp_path):
    promotion = _promotion("1", gift="2.00", groups=[_group(items=[_item(min_qty="2", max_qty="3")])])
    other = _promotion("2", gift="3", groups=[_group(items=[_item(min_qty="2", max_qty="3")])])
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", promotion, other)})
    assert found["gift_vs_min_qty"] == {"links": 2, "equal": 1, "by_value": {"2.00": [1, 1], "3": [1, 0]}}


def test_counts_promotions_listed_before_their_start(tmp_path):
    promotions = [_promotion("1", start="2026-11-02"), _promotion("2", start="2026-11-01"),
                  _promotion("3", start="2026-11-11"), _promotion("4", start="2026-10-01", end="2026-10-31"),
                  _promotion("5", start="2026-10-01", end="2026-11-01")]
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", *promotions)})
    assert found["before_start"] == {"promotions": 2, "days_ahead": {"1": 1, "10": 1}}
    assert (found["ended"], found["unreadable_dates"]) == (1, 0)  # ending on the day is not ended


def test_a_field_a_chain_lacks_is_not_counted_and_an_unreadable_date_is(tmp_path):
    bare_group = "<Group><GroupID>1</GroupID><PromotionItems>" + _item() + "</PromotionItems></Group>"
    promotion = _promotion("1", start="soon", groups=[bare_group]).replace("<ClubID>0</ClubID>", "")
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", promotion)})
    assert (found["values"]["ClubID"], found["values"]["DiscountType"]) == ({}, {})
    assert found["min_purchase_amount"] == {"1": {"groups": 1, "without_items": 0, "empty": 0, "zero": 0,
                                                  "above_zero": 0, "above_zero_without_items": 0, "top": {}}}
    assert (found["unreadable_dates"], found["before_start"]["promotions"]) == (1, 0)


def test_a_day_with_no_store_list_stops_the_survey(tmp_path):
    raw, tables = _day(tmp_path, "ramilevy", RAMI_DAY, RAMI, {"731": "001"}, {_rami_name("731"): RAMI_LEVY.read_bytes()})
    next(raw.rglob("Stores*")).unlink()
    with pytest.raises(NoStoreList, match="ramilevy"):
        survey(raw, tables, "ramilevy", RAMI_DAY)


@pytest.mark.parametrize("carriers, stores, carried", [
    ({"a": {"1", "2"}, "b": {"3"}}, {"1", "2", "3"}, 1),   # 2 of 3 stores: carried; 1 of 3: not
    ({"a": {"1", "2"}}, {"1", "2", "3", "4"}, 1),           # exactly half is enough
    ({"a": {"1", "9"}}, {"1", "2", "3"}, 0),                # a store outside the set is not counted
], ids=["two of three", "two of four", "outside"])
def test_carried_by_half(carriers, stores, carried):
    assert carried_by_half(carriers, stores) == {"stores": len(stores), "promotions": len(carriers),
                                                 "carried_by_half": carried}


def test_share_carried_by_half_the_stores(tmp_path):
    files = {_rami_name("1"): _promo_file("1", _promotion("10"), _promotion("20")),
             _rami_name("2"): _promo_file("2", _promotion("10")),
             _rami_name("3"): _promo_file("3", _promotion("30", coupon="1"))}
    # store 4 is included with no price file, so it is not counted; store 3 is counted with a promotion file
    found = _rami(tmp_path, files, stores=("1", "2", "3", "4"), priced={s: [("2000000000015", "1.00")] for s in "123"},
                  sub_chains={"3": "2", "4": "2"})
    wide = found["chain_wide"]
    assert wide["counted"] == {"stores": 3, "promotions": 3, "carried_by_half": 1}  # 10 in 2 of 3
    assert wide["included"] == {"stores": 4, "promotions": 3, "carried_by_half": 1}  # 10 in 2 of 4
    assert wide["counted_not_coupons"] == {"stores": 3, "promotions": 2, "carried_by_half": 1}
    assert {sub: {key: by[key] for key in ("counted", "included")} for sub, by in wide["by_sub_chain"].items()} == {
        "1": {"counted": {"stores": 2, "promotions": 2, "carried_by_half": 2},
              "included": {"stores": 2, "promotions": 2, "carried_by_half": 2}},
        "2": {"counted": {"stores": 1, "promotions": 1, "carried_by_half": 1},
              "included": {"stores": 2, "promotions": 1, "carried_by_half": 1}}}
    assert found["stores"] == {"included": 4, "counted": 3, "with_promotion_file": 3, "counted_with_promotion_file": 3}


def test_codes_on_a_link_carried_by_half_the_counted_stores(tmp_path):
    def one(promotion_id, code, coupon="0"):
        return _promotion(promotion_id, coupon=coupon, groups=[_group(items=[_item(code)])])
    files = {_rami_name("1"): _promo_file("1", one("10", "2000000000046"), one("20", "2000000000053")),
             _rami_name("2"): _promo_file("2", one("10", "2000000000046")),
             _rami_name("3"): _promo_file("3", one("30", "2000000000060", coupon="1"))}
    found = _rami(tmp_path, files, stores=("1", "2", "3", "4"), priced={s: [("2000000000015", "1.00")] for s in "123"},
                  sub_chains={"3": "2", "4": "2"})
    wide = found["chain_wide"]
    # ...046 is on promotion 10 at 2 of the 3 counted stores; ...053 at 1 of 3; the coupon's ...060 is not counted
    assert wide["codes_counted_not_coupons"] == {"stores": 3, "codes": 2, "chain_wide": 1}
    assert {sub: by["codes_counted_not_coupons"] for sub, by in wide["by_sub_chain"].items()} == {
        "1": {"stores": 2, "codes": 2, "chain_wide": 2}, "2": {"stores": 1, "codes": 0, "chain_wide": 0}}


def test_field_sets_per_file_and_tag_sets_per_element(tmp_path):
    files = {_rami_name("1"): _promo_file("1", _promotion("10"), _promotion("20", remarks=False)),
             _rami_name("2"): _promo_file("2", _promotion("10"))}
    found = _rami(tmp_path, files, stores=("1", "2"))
    promotion = ["AdditionalIsCoupon", "ClubID", "Groups", "IsGiftItem", "PromotionDescription",
                 "PromotionEndDateTime", "PromotionID", "PromotionStartDateTime", "PromotionUpdateTime"]
    with_remarks = sorted(promotion + ["Remarks"])
    assert found["field_sets"]["promotion"] == [{"tags": with_remarks, "files": 2}]  # a file's union
    assert found["element_sets"]["promotion"] == [{"tags": with_remarks, "missing": [], "elements": 2},
                                                  {"tags": promotion, "missing": ["Remarks"], "elements": 1}]
    assert found["element_sets"]["item"] == [{"tags": sorted(ITEM_TAGS), "missing": [], "elements": 3}]


def test_value_counts_and_descriptions_for_the_eye(tmp_path):
    raw, tables = _day(tmp_path, "carrefour", CARREFOUR_DAY, "7290055700007", {"472": "001"},
                       {CARREFOUR.name: CARREFOUR.read_bytes()})
    found = survey(raw, tables, "carrefour", CARREFOUR_DAY)
    values = found["values"]
    assert values["RewardType"] == {"10": [1, 1], "2": [1, 1], "3": [1, 1]}  # [elements, distinct promotions]
    assert values["IsGiftItem"] == {"": [1, 1], "1": [1, 1], "3": [1, 1]}
    assert (values["ClubID"], values["AdditionalIsCoupon"]) == ({"0": [3, 3]}, {"0": [2, 2], "1": [1, 1]})
    assert values["DiscountType"] == {"": [2, 2], "0": [1, 1]}
    assert values["bIsWeighted"] == {"0": [3, 3]}
    assert found["samples"]["IsGiftItem"]["3"] == ["מבצע לדוגמה 3"]
    assert found["gift_vs_min_qty"] == {"links": 2, "equal": 2, "by_value": {"1": [1, 1], "3": [1, 1]}}  # "" is none
    assert found["distinct_texts"] == 3


def test_the_price_fields_each_reward_type_carries(tmp_path):
    raw, tables = _day(tmp_path, "shufersal", date(2026, 10, 31), "7290027600007", {"878": "001"},
                       {SHUFERSAL.name: SHUFERSAL.read_bytes()})
    found = survey(raw, tables, "shufersal", date(2026, 10, 31))
    # Shufersal's coupons: RewardType 0 with both price fields empty
    assert found["price_fields"] == {"0": {"links": 3, "discounted_price": 0, "discount_rate": 0}}
    items = [_item("2000000000046", reward="0", rate="", price="21.90"), _item("2000000000053", reward="2", rate="20")]
    found = _rami(tmp_path / "rami", {_rami_name("731"): _promo_file("731", _promotion("1", groups=[_group(items=items)]))})
    assert found["price_fields"] == {"0": {"links": 1, "discounted_price": 1, "discount_rate": 0},
                                     "2": {"links": 1, "discounted_price": 1, "discount_rate": 1}}


def test_at_most_five_descriptions_for_a_value(tmp_path):
    promotions = [_promotion(str(n), description=f"מבצע לדוגמה {n % 7}") for n in range(12)]
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", *promotions)})
    assert found["samples"]["ClubID"]["0"] == [f"מבצע לדוגמה {n}" for n in range(5)]  # distinct, first seen first
    assert found["distinct_texts"] == 12  # the id is part of a text's key


def test_min_purchase_amount_by_group_position(tmp_path):
    two_groups = [_group("1", items=[_item()]), _group("2", min_purchase="50.00")]  # the second group has no items
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", _promotion("1", groups=two_groups),
                                                            _promotion("2", groups=[_group(items=[_item()],
                                                                                           min_purchase="0.00")]))})
    assert found["groups_per_promotion"] == {"1": 1, "2": 1}
    assert found["min_purchase_amount"] == {
        "1": {"groups": 2, "without_items": 0, "empty": 1, "zero": 1, "above_zero": 0, "above_zero_without_items": 0,
              "top": {"": 1, "0.00": 1}},
        "2": {"groups": 1, "without_items": 1, "empty": 0, "zero": 0, "above_zero": 1, "above_zero_without_items": 1,
              "top": {"50.00": 1}}}


def test_link_variants_across_stores(tmp_path):
    same = _promotion("10", groups=[_group(items=[_item("2000000000046"), _item("2000000000053")])])
    cheaper = _promotion("10", groups=[_group(items=[_item("2000000000046"), _item("2000000000053", price="4.00")])])
    renamed = _promotion("10", groups=[_group(items=[_item("2000000000046"), _item("2000000000053", price="4.00")])],
                         description="מבצע לדוגמה 11")
    files = {_rami_name("1"): _promo_file("1", same), _rami_name("2"): _promo_file("2", same),
             _rami_name("3"): _promo_file("3", cheaper), _rami_name("4"): _promo_file("4", renamed)}
    found = _rami(tmp_path, files, stores=("1", "2", "3", "4"))
    # store 3 prices the second item lower; store 4 also renames the promotion, so both links have two variants
    assert found["variants"] == {"links": 2, "with_more_than_one": 2,
                                 "fields": {"item.DiscountedPrice": 1, "promotion.PromotionDescription": 2}}


def test_big_coupons(tmp_path):
    items = [_item(f"{n:013d}") for n in range(BIG_COUPON + 1)]
    files = {_rami_name("731"): _promo_file("731", _promotion("1", coupon="1", groups=[_group(items=items)]),
                                            _promotion("2", coupon="1", groups=[_group(items=items[1:])]),
                                            _promotion("3", groups=[_group(items=items)]))}
    found = _rami(tmp_path, files)
    assert found["big_coupons"] == {"promotions": [{"promotion": "1", "links": BIG_COUPON + 1, "stores": 1}],
                                    "links": BIG_COUPON + 1}
    assert found["links"] == 3 * BIG_COUPON + 2


@pytest.mark.parametrize("prices, outcome", [
    ({"472": "5.50"}, "agrees"),                    # 5.50 x 0.80 = 4.40
    ({"472": "22.00"}, "reads_as_the_discount"),    # 22.00 x 0.20 = 4.40
    ({"472": "9.00"}, "disagrees"),
    ({"472": "5.49"}, "agrees"),                    # 4.392 rounds to 4.39, within an agora of 4.40
    ({"472": "5.48"}, "disagrees"),                 # 4.384 rounds to 4.38
    ({"472": "5.48", "473": "5.49"}, "agrees"),     # the median 5.485: 4.388 rounds to 4.39, unrounded 0.012 off
    ({}, "no_listed_price"),
], ids=["agrees", "the discount", "disagrees", "an agora off", "two agorot off", "rounded to agorot", "no price"])
def test_percent_off_against_the_days_median_price(tmp_path, prices, outcome):
    priced = {store: [("2000000000015", "1.00"), ("2000000000053", price)] for store, price in prices.items()}
    priced = priced or {"472": [("2000000000015", "1.00")]}
    raw, tables = _day(tmp_path, "carrefour", CARREFOUR_DAY, "7290055700007", {"472": "001", "473": "001"},
                       {CARREFOUR.name: CARREFOUR.read_bytes()}, priced)
    found = survey(raw, tables, "carrefour", CARREFOUR_DAY)["percent_off"]
    assert found["links"] == 1 and found[outcome] == 1
    assert sum(found[key] for key in ("agrees", "reads_as_the_discount", "disagrees", "no_listed_price",
                                      "no_rate", "no_discounted_price")) == 1


def test_percent_off_against_the_median_and_against_the_stores_own_price(tmp_path):
    priced = {"472": [("2000000000053", "5.50")], "473": [("2000000000053", "6.50")]}  # median 6.00: 4.80
    raw, tables = _day(tmp_path, "carrefour", CARREFOUR_DAY, "7290055700007", {"472": "001", "473": "001"},
                       {CARREFOUR.name: CARREFOUR.read_bytes()}, priced)
    found = survey(raw, tables, "carrefour", CARREFOUR_DAY)["percent_off"]
    assert (found["disagrees"], found["with_store_price"], found["agrees_with_store_price"]) == (1, 1, 1)


def test_percent_off_with_no_rate_or_no_discounted_price(tmp_path):
    items = [_item("2000000000046", reward="2", rate="", price="4.00"),
             _item("2000000000053", reward="2", rate="20", price="")]
    found = _rami(tmp_path, {_rami_name("731"): _promo_file("731", _promotion("1", groups=[_group(items=items)]))},
                  priced={"731": [("2000000000046", "5.00"), ("2000000000053", "5.00")]})
    assert (found["percent_off"]["no_rate"], found["percent_off"]["no_discounted_price"]) == (1, 1)


def test_the_survey_writes_no_file(tmp_path):
    raw, tables = _day(tmp_path, "ramilevy", RAMI_DAY, RAMI, {"731": "001"}, {_rami_name("731"): RAMI_LEVY.read_bytes()})
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    survey(raw, tables, "ramilevy", RAMI_DAY)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


def test_the_read_is_timed_and_its_peak_memory_given(tmp_path):
    found = _rami(tmp_path, {_rami_name("731"): RAMI_LEVY.read_bytes()})
    assert found["seconds"] >= 0 and found["peak_memory_mb"] > 0
    assert (found["chain"], found["day"]) == ("ramilevy", "2026-11-01")


def test_main_prints_json_per_chain(tmp_path, capsys):
    _day(tmp_path, "ramilevy", RAMI_DAY, RAMI, {"731": "001"}, {_rami_name("731"): RAMI_LEVY.read_bytes()})
    main(["--data", str(tmp_path), "--day", "2026-11-01", "--chain", "ramilevy"])
    printed = json.loads(capsys.readouterr().out)
    assert (printed["chain"], printed["promotions"]) == ("ramilevy", 3)
    assert printed["samples"]["ClubID"]["0"][0] == "מבצע לדוגמה 1"  # printed for the eye, as written

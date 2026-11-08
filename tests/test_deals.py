"""The deal price (P4 as the survey amendment's S4 reads it; the plan's question C; the pre-flight's S4, S6 and S10)."""
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from shopper.deals import Deal, StorePrices, agrees, deal, deal_from_row
from shopper.promofile import PromotionFormatChanged, Tally, read_promotions

FIXTURES = Path(__file__).parent / "fixtures"
CARREFOUR = FIXTURES / "carrefour" / "PromoFull7290055700007-001-472-20261031-051058.gz"
RAMI_LEVY = FIXTURES / "ncr" / "PromoFull7290058140886-001-731-20261101-001049.gz"
YOCHANANOF = FIXTURES / "ncr" / "PromoFull7290803800003-000-001-20261107-004032.gz"
ONE = Decimal(1)


def _item(path, promotion_id, **changes):
    """The item fields of the fixture promotion's first link, with `changes` written over them."""
    for record in read_promotions(path.name, path.read_bytes(), lambda promotion: True, Tally()):
        if record.fields["PromotionID"] == promotion_id:
            return {**record.links[0].item, **changes}
    raise LookupError(promotion_id)


def _same(price):
    """Every carrying store at one `DiscountedPrice`."""
    return StorePrices(Decimal(price), Decimal(price), Decimal(price))


def test_fixed_price():
    found = deal("carrefour", _item(CARREFOUR, "900001"), Decimal("10.90"))   # RewardType 3 at 8.72
    assert found == Deal(Fraction("8.72"), "unit", ONE, None, None, True, None)


def test_percent_off_is_the_stores_price_checked_by_the_rate():
    item = _item(CARREFOUR, "900002")   # RewardType 2, DiscountRate 20.00
    assert deal("carrefour", item, Decimal("5.50"), _same("4.40")) == Deal(
        Fraction("4.40"), "unit", ONE, Decimal("4.40"), Decimal("4.40"), True, None)
    assert deal("carrefour", item, Decimal("5.50"), _same("4.42")) == Deal(
        Fraction("4.42"), "unit", ONE, Decimal("4.42"), Decimal("4.42"), False, "the rate and the price disagree")
    # 5.55 x 0.90 = 4.995, rounded half up to 5.00: 5.01 is within an agora of that, not of 4.995
    assert deal("carrefour", {**item, "DiscountRate": "10.00"}, Decimal("5.55"), _same("5.01")).valid


def test_percent_off_takes_the_stores_median_not_the_variants_price():
    item = _item(CARREFOUR, "900002", DiscountedPrice="4.10")
    stores = StorePrices(Decimal("4.40"), Decimal("4.10"), Decimal("4.50"))
    assert deal("carrefour", item, Decimal("5.50"), stores) == Deal(
        Fraction("4.40"), "unit", ONE, Decimal("4.10"), Decimal("4.50"), True, None)
    # with no stores given, the variant's own price is a one-store median
    assert deal("carrefour", _item(CARREFOUR, "900002"), Decimal("5.50")) == Deal(
        Fraction("4.40"), "unit", ONE, Decimal("4.40"), Decimal("4.40"), True, None)


def test_a_drifting_rate_is_price_not_read():
    # Rami Levy's shape: the price is the store's own x 0.75, the rate field reads 25.32
    item = _item(RAMI_LEVY, "900002", RewardType="2", MinQty="1", DiscountRate="25.32", DiscountedPrice="7.50")
    assert deal("ramilevy", item, Decimal("10.00"), _same("7.50")) == Deal(   # 10.00 x 0.7468 = 7.47
        Fraction("7.50"), "unit", ONE, Decimal("7.50"), Decimal("7.50"), False, "the rate and the price disagree")
    assert deal("ramilevy", {**item, "DiscountRate": "25.00"}, Decimal("10.00"), _same("7.50")).valid


def test_n_for_m_is_m_over_n():
    found = deal("ramilevy", _item(RAMI_LEVY, "900001"), Decimal("2.00"))   # RewardType 10: 6 for 8.72
    assert found == Deal(Fraction(872, 600), "unit", Decimal(6), None, None, True, None)
    assert type(found.price) is Fraction and found.price == Fraction(109, 75)


def test_a_weighed_two_for_100_stored_as_1_5_for_75_is_50_a_kilogram():
    stored = _item(YOCHANANOF, "900001", MinQty="1.50", DiscountedPrice="75.00")   # RewardType 1, bIsWeighted 1
    assert deal("yochananof", stored, Decimal("59.90")) == Deal(Fraction(50), "kg", Decimal("1.5"), None, None,
                                                               True, None)
    as_written = _item(YOCHANANOF, "900001", MinQty="2", DiscountedPrice="100.00")
    assert deal("yochananof", as_written, Decimal("59.90")).price == Fraction(50)


def test_the_range_is_exclusive():
    fixed = _item(CARREFOUR, "900001")

    def priced(price):
        return deal("carrefour", {**fixed, "DiscountedPrice": price}, Decimal("10.90"))

    assert (priced("0.01").valid, priced("0.01").why) == (False, "not above ₪0.01")
    assert priced("0.02").valid
    assert (priced("21.80").valid, priced("21.80").why) == (False, "not below twice the listed price")
    assert priced("21.79").valid
    three = deal("carrefour", _item(CARREFOUR, "900003", DiscountedPrice="0.04"), Decimal("10.90"))   # 3 for 0.04
    assert (three.price, three.valid) == (Fraction(1, 75), True)


def test_percent_off_without_a_listed_price_keeps_its_price_and_is_not_valid():
    stores = StorePrices(Decimal("4.40"), Decimal("4.30"), Decimal("4.50"))
    assert deal("carrefour", _item(CARREFOUR, "900002"), None, stores) == Deal(
        Fraction("4.40"), "unit", ONE, Decimal("4.30"), Decimal("4.50"), False, "no listed price")
    assert deal("carrefour", _item(CARREFOUR, "900001"), None) == Deal(
        Fraction("8.72"), "unit", ONE, None, None, False, "no listed price")


def test_no_price_fields():
    unread = Deal(None, "unit", ONE, None, None, False, "no price in the fields")
    assert deal("carrefour", _item(CARREFOUR, "900001", DiscountedPrice=""), Decimal("10.90")) == unread
    assert deal("carrefour", _item(CARREFOUR, "900002", DiscountedPrice=""), Decimal("5.50")) == unread
    assert deal("carrefour", _item(CARREFOUR, "900003", MinQty=""), Decimal("10.90")) == unread
    assert deal("carrefour", _item(CARREFOUR, "900003", MinQty="0"), Decimal("10.90")) == unread
    assert deal("carrefour", _item(CARREFOUR, "900003", MinQty="-3"), Decimal("10.90")) == unread
    assert deal("carrefour", _item(CARREFOUR, "900003", DiscountedPrice="-"), Decimal("10.90")) == Deal(
        None, "unit", Decimal(3), None, None, False, "no price in the fields")


def test_a_zero_link_has_no_deal():
    # Rami Levy writes a DiscountedPrice on the condition side of its two-group promotions (S2)
    item = _item(RAMI_LEVY, "900002", RewardType="0")
    assert deal("ramilevy", item, Decimal("5.50")) == Deal(None, "unit", ONE, None, None, False, "no kind link")


def test_an_unknown_reward_type_stops_naming_the_chain():
    with pytest.raises(PromotionFormatChanged, match="^carrefour: RewardType 7 "):
        deal("carrefour", _item(CARREFOUR, "900001", RewardType="7"), Decimal("10.90"))


def test_agrees_within_an_agora_of_the_figure_rounded_half_up():
    assert agrees(Decimal("4.40"), Decimal("5.50"), Decimal("20.00"))
    assert agrees(Decimal("4.41"), Decimal("5.50"), Decimal("20.00"))       # an agora off
    assert not agrees(Decimal("4.42"), Decimal("5.50"), Decimal("20.00"))
    assert agrees(Decimal("4.38"), Decimal("4.85"), Decimal("10"))          # 4.365 half up is 4.37, half even 4.36
    assert not agrees(Decimal("5.02"), Decimal("5.55"), Decimal("10.00"))   # 4.995 to 5.00


def test_a_rate_not_above_0_and_below_100_is_not_read():
    item = _item(CARREFOUR, "900002")
    disagree = (False, "the rate and the price disagree")
    for rate, price in (("0", "5.50"), ("100", "0.00"), ("", "4.40"), ("-", "4.40")):
        found = deal("carrefour", {**item, "DiscountRate": rate}, Decimal("5.50"), _same(price))
        assert (found.valid, found.why) == disagree, rate


def _struct(price, exact, per, buy, low, high, valid, why):
    """A deal as Task 6 writes it in the items table's `promotions` struct (the pre-flight's S11), as DuckDB reads it
    back: DECIMAL as `Decimal`, `price_exact` the `Fraction`'s text, NULL as None."""
    return {"promotion_id": "900001", "kind": "n_for_m", "buy": buy, "price": price, "price_exact": exact, "per": per,
            "low": low, "high": high, "valid": valid, "why": why, "restrictions": [], "programmes": [],
            "min_spend": None, "stores": 3, "wide": True}


def test_a_deal_rebuilt_from_the_items_struct_is_the_deal():
    six_for = deal("ramilevy", _item(RAMI_LEVY, "900001"), Decimal("2.00"))   # 6 for 8.72
    weighed = deal("yochananof", _item(YOCHANANOF, "900001", MinQty="1.50", DiscountedPrice="75.00"), Decimal("59.90"))
    percent = deal("carrefour", _item(CARREFOUR, "900002", DiscountedPrice="4.10"), Decimal("5.50"),
                   StorePrices(Decimal("4.40"), Decimal("4.10"), Decimal("4.50")))
    zero = deal("ramilevy", _item(RAMI_LEVY, "900002", RewardType="0"), Decimal("5.50"))
    rows = [
        (six_for, _struct(Decimal("1.45"), "109/75", "unit", Decimal("6.000"), None, None, True, None)),
        (weighed, _struct(Decimal("50.00"), "50", "kg", Decimal("1.500"), None, None, True, None)),
        (percent, _struct(Decimal("4.40"), "22/5", "unit", Decimal("1.000"), Decimal("4.100"), Decimal("4.500"), True,
                          None)),
        (zero, _struct(None, None, "unit", Decimal("1.000"), None, None, False, "no kind link")),
    ]
    for found, row in rows:
        rebuilt = deal_from_row(row)
        assert rebuilt == found
        assert rebuilt.price is None or type(rebuilt.price) is Fraction
    assert deal_from_row(rows[0][1]).price == Fraction(109, 75)   # not 1.45, the two places written for the eye

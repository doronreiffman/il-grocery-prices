"""The deal price (P4 as the survey amendment's S4 reads it; the plan's question C; the pre-flight's S4, S6 and S10)."""
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from shopper.deals import Deal, StorePrices, agrees, deal, deal_from_row, to_agora
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
    # RewardType 1, bIsWeighted 1; the chain's own kilogram figure, ₪50.000, says the price is the total (q46)
    stored = _item(YOCHANANOF, "900001", MinQty="1.50", DiscountedPrice="75.00", DiscountedPricePerMida="50.000")
    assert deal("yochananof", stored, Decimal("59.90")) == Deal(Fraction(50), "kg", Decimal("1.5"), None, None,
                                                               True, None)
    as_written = _item(YOCHANANOF, "900001", MinQty="2", DiscountedPrice="100.00", DiscountedPricePerMida="50.000")
    assert deal("yochananof", as_written, Decimal("59.90")).price == Fraction(50)


def _weighed_n_for_m(minimum, price, figure):
    """Rami Levy's weighed "N for ₪M" link (RewardType 10, bIsWeighted 1) with its `MinQty`, `DiscountedPrice` and the
    chain's own kilogram figure, `DiscountedPricePerMida`."""
    return _item(RAMI_LEVY, "900001", bIsWeighted="1", MinQty=minimum, DiscountedPrice=price,
                 DiscountedPricePerMida=figure)


def test_a_weighed_n_for_m_whose_figure_is_its_price_is_a_kilograms_price():
    # Rami Levy's chicken legs (22 November 2026): MinQty 0.010 (any weight), ₪28.90 and its figure ₪28.900; read as
    # the total for 0.01 kg it was ₪2,890 a kilogram, never valid (q46)
    assert deal("ramilevy", _weighed_n_for_m("0.010", "28.90", "28.900"), Decimal("34.90")) == Deal(
        Fraction("28.90"), "kg", ONE, None, None, True, None)
    # a minimum above a placeholder is no condition either, as on a fixed price: Rami Levy's red peppers, ₪5.50 a
    # kilogram over 0.3 kg (an internal code, which no page reads)
    assert deal("ramilevy", _weighed_n_for_m("0.300", "5.50", "5.500"), Decimal("7.90")) == Deal(
        Fraction("5.50"), "kg", ONE, None, None, True, None)


def test_a_weighed_n_for_m_its_figure_disagrees_with_is_not_read():
    # the fixture's link: ₪8.72 for 1.9 kg beside a figure of ₪0.872, a kilogram's price by neither reading
    assert deal("yochananof", _item(YOCHANANOF, "900001"), Decimal("9.90")) == Deal(
        None, "kg", ONE, None, None, False, "the price and its kilogram price disagree")
    assert deal("yochananof", _item(YOCHANANOF, "900001", DiscountedPricePerMida=""), Decimal("9.90")) == Deal(
        None, "kg", ONE, None, None, False, "no price in the fields")


def test_a_weighed_n_for_m_without_a_minimum_is_not_read_even_where_its_figure_is_its_price():
    # an "N for ₪M" with no N is not read before the figure is asked, weighed or not; a weighed fixed price with the
    # same fields reads a kilogram's ₪28.90 (q46's review, 2026-11-22; no row of the tables has this shape)
    for minimum in ("", "0", "-0.010"):
        assert deal("ramilevy", _weighed_n_for_m(minimum, "28.90", "28.900"), Decimal("34.90")) == Deal(
            None, "kg", ONE, None, None, False, "no price in the fields"), minimum


def _weighed(minimum, price, figure):
    """A weighed fixed-price link (RewardType 3, bIsWeighted 1) with its `MinQty`, `DiscountedPrice` and the chain's
    own kilogram figure, `DiscountedPricePerMida`."""
    return _item(CARREFOUR, "900001", bIsWeighted="1", MinQty=minimum, DiscountedPrice=price,
                 DiscountedPricePerMida=figure)


def test_a_weighed_fixed_price_with_a_minimum_is_the_total_for_it():
    # Osher Ad's ground veal, "2 for ₪120" (10 November 2026): ₪114.00 for 1.9 kg or more, its figure ₪60.000 a kilogram
    assert deal("osherad", _weighed("1.900", "114.00", "60.000"), Decimal("69.90")) == Deal(
        Fraction(60), "kg", Decimal("1.9"), None, None, True, None)
    # Carrefour's pastrami (16 November 2026): ₪22.00 for 250 g or more, ₪88.000 a kilogram
    assert deal("carrefour", _weighed("0.250", "22.00", "88.000"), Decimal("103.00")) == Deal(
        Fraction(88), "kg", Decimal("0.25"), None, None, True, None)
    # the price is the total ÷ the minimum, exactly; the figure, rounded by the chain, only checks it
    chicken = deal("osherad", _weighed("1.850", "41.63", "22.500"), Decimal("26.90"))
    assert (chicken.price, chicken.buy, to_agora(chicken.price)) == (Fraction(4163, 185), Decimal("1.85"),
                                                                     Decimal("22.50"))


def test_a_weighed_fixed_price_with_a_placeholder_minimum_is_a_kilograms_price():
    # every chain writes 0.01 when any weight qualifies, Shufersal 0.10 too: the figure is the price itself
    for minimum in ("0.010", "0.10", "1"):
        assert deal("carrefour", _weighed(minimum, "49.90", "49.900"), Decimal("59.90")) == Deal(
            Fraction("49.90"), "kg", ONE, None, None, True, None), minimum
    # a kilogram's price is asked first: a minimum just above 1 whose total would also agree stays no condition
    assert deal("carrefour", _weighed("1.001", "0.50", "0.500"), Decimal("0.60")) == Deal(
        Fraction("0.50"), "kg", ONE, None, None, True, None)


def test_a_weighed_fixed_prices_figure_agrees_within_an_agora():
    for figure in ("49.91", "49.89"):   # the price is DiscountedPrice, the figure only checks it
        assert deal("carrefour", _weighed("0.010", "49.90", figure), Decimal("59.90")) == Deal(
            Fraction("49.90"), "kg", ONE, None, None, True, None), figure
    for figure in ("60.01", "59.99"):
        assert deal("osherad", _weighed("1.900", "114.00", figure), Decimal("69.90")) == Deal(
            Fraction(60), "kg", Decimal("1.9"), None, None, True, None), figure


def test_a_weighed_fixed_price_without_a_listed_price_keeps_its_price_and_is_not_valid():
    assert deal("osherad", _weighed("1.900", "114.00", "60.000"), None) == Deal(
        Fraction(60), "kg", Decimal("1.9"), None, None, False, "no listed price")
    assert deal("carrefour", _weighed("0.010", "49.90", "49.900"), None) == Deal(
        Fraction("49.90"), "kg", ONE, None, None, False, "no listed price")


def test_a_weighed_fixed_price_its_figure_disagrees_with_is_not_read():
    disagree = Deal(None, "kg", ONE, None, None, False, "the price and its kilogram price disagree")
    assert deal("osherad", _weighed("1.900", "114.00", "57.000"), Decimal("69.90")) == disagree
    assert deal("osherad", _weighed("1.900", "114.00", "60.011"), Decimal("69.90")) == disagree
    assert deal("osherad", _weighed("1.900", "114.00", "59.989"), Decimal("69.90")) == disagree
    assert deal("carrefour", _weighed("0.010", "49.90", "49.911"), Decimal("59.90")) == disagree
    assert deal("carrefour", _weighed("0.010", "49.90", "49.889"), Decimal("59.90")) == disagree
    for minimum in ("", "0", "-1.900"):   # no minimum to divide by: only the price itself can agree
        assert deal("osherad", _weighed(minimum, "114.00", "60.000"), Decimal("69.90")) == disagree, minimum
    # a minimum below 0 is never divided by, even where a figure below 0 would agree with it
    assert deal("osherad", _weighed("-1.900", "114.00", "-60.000"), Decimal("69.90")) == disagree
    unread = Deal(None, "kg", ONE, None, None, False, "no price in the fields")
    for figure in ("", "-"):
        assert deal("osherad", _weighed("1.900", "114.00", figure), Decimal("69.90")) == unread, figure
    assert deal("osherad", _weighed("1.900", "", "60.000"), Decimal("69.90")) == unread


def test_a_fixed_price_by_the_piece_never_reads_the_figure():
    # by the piece the figure is another measure's price (₪0.872 beside ₪8.72), and a minimum is not divided by
    assert deal("carrefour", _item(CARREFOUR, "900001", MinQty="2"), Decimal("10.90")) == Deal(
        Fraction("8.72"), "unit", ONE, None, None, True, None)
    assert deal("carrefour", _item(CARREFOUR, "900001", DiscountedPricePerMida=""), Decimal("10.90")).valid


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
    weighed = deal("yochananof", _item(YOCHANANOF, "900001", MinQty="1.50", DiscountedPrice="75.00",
                                       DiscountedPricePerMida="50.000"), Decimal("59.90"))
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


@pytest.mark.parametrize("text", ["1E+5000", "1E-5000"], ids=["huge", "tiny"])
def test_a_field_of_an_exponent_no_chain_writes_is_not_read(text):
    # read, each would be a Fraction past the 4,300 digits Python prints, or a rate of nothing that agrees
    unread = (None, False, "no price in the fields")
    for found in (deal("carrefour", _item(CARREFOUR, "900001", DiscountedPrice=text), Decimal("10.90")),
                  deal("carrefour", _item(CARREFOUR, "900003", MinQty=text), Decimal("10.90")),
                  deal("carrefour", _item(CARREFOUR, "900002", DiscountedPrice=text), Decimal("5.50"))):
        assert (found.price, found.valid, found.why) == unread
    rate = deal("carrefour", _item(CARREFOUR, "900002", DiscountRate=text), Decimal("5.50"), _same("5.50"))
    assert (rate.valid, rate.why) == (False, "the rate and the price disagree")


def test_the_deal_for_the_eye_is_to_the_agora_half_up_from_the_exact_price():
    """`to_agora`: the one rule for writing a deal price (a Fraction) to two places (the pre-flight's S6): half up, a tie
    away from zero, read from the exact price, never from a rounded one. The items table and the words both write it."""
    assert to_agora(Fraction("4.34") / 3) == Decimal("1.45")            # 1.4466...
    assert to_agora(Fraction(10, 3)) == Decimal("3.33")                 # 3.3333...
    assert to_agora(Fraction("1.445")) == Decimal("1.45")               # a tie goes up
    assert to_agora(Fraction("1.4449999")) == Decimal("1.44")
    assert to_agora(Fraction("-1.445")) == Decimal("-1.45")             # and away from zero below it
    assert str(to_agora(Fraction("7.9"))) == "7.90" and str(to_agora(Fraction(0))) == "0.00"

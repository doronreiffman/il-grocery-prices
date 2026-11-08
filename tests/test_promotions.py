"""Which promotions count, their conditions from the chains' fields, and a format change stopping the chain (P3, P5,
P10)."""
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from basket.chains import SLUGS
from shopper.promofile import Link, PromotionFormatChanged, PromotionRead, Tally, read_promotions
from shopper.promotions import (GIFT_VALUES, KNOWN_FIELDS, Target, check_codes, dates, gift_value, has_price_effect,
                                in_day, is_coupon, keep, kind, min_spend, not_shelf, number, target)

FIXTURES = Path(__file__).parent / "fixtures"
SHUFERSAL_NOV_7 = FIXTURES / "shufersal" / "PromoFull7290027600007-001-001-20261107-030000.gz"
PROMO_FIXTURES = {  # each chain's promotion fixtures
    "shufersal": [FIXTURES / "shufersal" / "PromoFull7290027600007-000-878-20261031-030000.gz", SHUFERSAL_NOV_7],
    "ramilevy": [FIXTURES / "ncr" / "PromoFull7290058140886-001-731-20261101-001049.gz"],
    "osherad": [FIXTURES / "ncr" / "PromoFull7290103152017-001-001-20261107-110530.gz"],
    "carrefour": [FIXTURES / "carrefour" / "PromoFull7290055700007-001-472-20261031-051058.gz"],
    "yochananof": [FIXTURES / "ncr" / "PromoFull7290803800003-000-001-20261107-004032.gz"],
}
LEVELS = ("root", "promotion", "group", "item")


def _everything(promotion):
    return True


def _own_sets(path):
    """Each level's element tag sets in the fixture, as the reader saw them."""
    tally = Tally()
    list(read_promotions(path.name, path.read_bytes(), _everything, tally))
    return tally.sets


def _promotion(club="0", gift="", coupon="0", start="2026-11-01T00:00:00.000", end="2026-11-28T23:59:00.000"):
    return {"PromotionID": "900001", "PromotionStartDateTime": start, "PromotionEndDateTime": end, "ClubID": club,
            "IsGiftItem": gift, "AdditionalIsCoupon": coupon}


def _group(group_id="1", min_spend="", discount_type=""):
    return {"GroupID": group_id, "MinPurchaseAmount": min_spend, "DiscountType": discount_type}


def _item(reward, price=""):
    return {"ItemCode": "2000000000046", "ItemType": "1", "RewardType": reward, "MinQty": "1", "MaxQty": "",
            "DiscountRate": "", "DiscountedPrice": price, "DiscountedPricePerMida": "", "bIsWeighted": "0"}


def _record(*groups):
    """A promotion of the groups given, each as (its fields, its items)."""
    fields = _promotion()
    return PromotionRead(fields, tuple(group for group, _ in groups),
                         tuple(Link(fields, group, item) for group, items in groups for item in items))


def _links(*rewards):
    """A promotion of one group whose items carry the reward types given, in order."""
    return _record((_group(), [_item(reward) for reward in rewards]))


def test_known_fields_are_each_chains_fixtures():
    assert sorted(KNOWN_FIELDS) == sorted(SLUGS)
    assert sorted(FIXTURES.rglob("PromoFull*")) == sorted(path for paths in PROMO_FIXTURES.values() for path in paths)
    for slug, paths in PROMO_FIXTURES.items():
        seen = [_own_sets(path) for path in paths]
        for level in LEVELS:
            assert getattr(KNOWN_FIELDS[slug], level) == set().union(*(sets[level] for sets in seen)), (slug, level)


@pytest.mark.parametrize("slug", ["ramilevy", "osherad", "carrefour", "shufersal", "yochananof"])
def test_an_item_without_max_qty_stops_only_the_chains_that_never_carry_one(slug):
    name, data = SHUFERSAL_NOV_7.name, SHUFERSAL_NOV_7.read_bytes()
    if slug in ("shufersal", "yochananof"):
        assert len(list(read_promotions(name, data, _everything, Tally(), KNOWN_FIELDS[slug]))) == 2
        return
    with pytest.raises(PromotionFormatChanged) as refused:
        list(read_promotions(name, data, _everything, Tally(), KNOWN_FIELDS[slug]))
    assert str(refused.value) == f"{name}: item fields changed: added [], missing ['MaxQty']"


@pytest.mark.parametrize("slug", sorted(PROMO_FIXTURES))
def test_every_fixture_passes_its_chains_checks(slug):
    for path in PROMO_FIXTURES[slug]:
        tally = Tally()
        for record in read_promotions(path.name, path.read_bytes(), keep(slug), tally, KNOWN_FIELDS[slug]):
            check_codes(slug, record)
            assert not_shelf(slug, record) is None
            in_day(record.fields, date(2026, 11, 7))
        assert tally.promotions > 0


@pytest.mark.parametrize("slug, club_id, restrictions, names", [
    ("osherad", "0", (), ()),
    ("shufersal", "0 - כלל הלקוחות", (), ()),  # all customers: no restriction, and the label names no programme
    ("shufersal", "2 - a label", ("chain_card",), ("a label",)),
    ("yochananof", "1 - a label", ("club",), ("a label",)),
    ("ramilevy", "((1=A|1=B))&(3=C)", ("club", "other"), ("A", "B", "C")),
    ("ramilevy", "((3=C))&(1=A)", ("club", "other"), ("C", "A")),  # the words in K's order, the names in the field's
    ("ramilevy", "3", ("other",), ()),  # a bare code: its restriction, no name
    ("carrefour", "(0=A|0=B)", ("other",), ("A", "B")),  # a programme named under code 0 restricts
    ("carrefour", "(0=A|0=B  C|0=D|0=B  C)", ("other",), ("A", "B  C", "D")),  # as published, no repeats
    ("carrefour", "()", (), ()),
    ("carrefour", "(2=A|2=B)", ("chain_card",), ("A", "B")),
])
def test_club_id_forms(slug, club_id, restrictions, names):
    found = target(slug, club_id)
    assert found == Target(restrictions, names)
    assert found.restricted == bool(restrictions)


@pytest.mark.parametrize("club_id", ["4", "(5=A)", "(1A)", "1 = A"])
def test_an_unknown_club_form_or_code_stops_the_chain_naming_the_field(club_id):
    with pytest.raises(PromotionFormatChanged) as refused:
        target("ramilevy", club_id)
    assert str(refused.value) == f"ramilevy: ClubID form not seen in the chain's files: {club_id!r}"


@pytest.mark.parametrize("slug, code, refused", [
    ("carrefour", "7", True),
    ("osherad", "0", True),  # Osher Ad's files carry no RewardType 0
    ("shufersal", "12", False),
])
def test_an_unknown_reward_type_stops_the_chain_naming_the_field(slug, code, refused):
    record = _links("3", code)
    calls = [lambda: kind(slug, _item(code)), lambda: has_price_effect(slug, _item(code)),
             lambda: check_codes(slug, record), lambda: not_shelf(slug, record)]
    if not refused:
        assert [call() for call in calls] == [None, False, None, "basket_reward"]
        return
    for call in calls:
        with pytest.raises(PromotionFormatChanged) as stopped:
            call()
        assert str(stopped.value) == f"{slug}: RewardType {code} not seen in the chain's files"


@pytest.mark.parametrize("slug, code, refused", [("yochananof", "1", True), ("osherad", "0", True),
                                                 ("yochananof", "0", False), ("osherad", "", False)])
def test_an_unknown_discount_type_stops_the_chain(slug, code, refused):
    record = _record((_group("1"), [_item("3")]), (_group("2", discount_type=code), []))  # an item-less group's too
    if not refused:
        check_codes(slug, record)
        return
    with pytest.raises(PromotionFormatChanged) as stopped:
        check_codes(slug, record)
    assert str(stopped.value) == f"{slug}: DiscountType {code} not seen in the chain's files"


def test_gift_values_are_watched_by_their_form():
    for slug, values in GIFT_VALUES.items():
        assert "" in values
        for value in values:
            gift_value(slug, value)
    gift_value("ramilevy", "11")  # a new quantity passes
    for value in ["Y", "-1", "1 - x", "0"]:
        with pytest.raises(PromotionFormatChanged) as stopped:
            gift_value("ramilevy", value)
        assert str(stopped.value) == f"ramilevy: IsGiftItem {value!r} is not a quantity"


def test_a_coupon_is_not_kept():
    assert is_coupon(_promotion(coupon="1")) and not is_coupon(_promotion(coupon="0"))
    keeps = keep("shufersal")
    assert keeps(_promotion(coupon="1")) is False
    assert keeps(_promotion(club="0 - a label", gift="1.5", coupon="0")) is True
    tally = Tally()  # the fixture of 31 October holds three coupons
    path = PROMO_FIXTURES["shufersal"][0]
    assert list(read_promotions(path.name, path.read_bytes(), keeps, tally, KNOWN_FIELDS["shufersal"])) == []
    assert (tally.promotions, tally.dropped_promotions) == (3, 3)


@pytest.mark.parametrize("club_id, gift, message", [
    ("(1A)", "", "ramilevy: ClubID form not seen in the chain's files: '(1A)'"),
    ("0", "Y", "ramilevy: IsGiftItem 'Y' is not a quantity"),
])
def test_keep_checks_a_coupons_codes_too(club_id, gift, message):
    with pytest.raises(PromotionFormatChanged, match=f"^{re.escape(message)}$"):
        keep("ramilevy")(_promotion(club=club_id, gift=gift, coupon="1"))


@pytest.mark.parametrize("rewards, found", [
    (["12", "1"], "basket_reward"),  # its "N for ₪M" links are the reward's own terms
    (["6"], "gift"),
    (["0", "1", "2", "3", "10"], None),
    (["1", "3", "12"], "basket_reward"),  # on the record's last link
])
def test_a_promotion_with_a_reward_type_6_or_12_link_is_not_a_shelf_deal(rewards, found):
    assert not_shelf("shufersal", _links(*rewards)) == found


@pytest.mark.parametrize("code, found", [("1", "n_for_m"), ("10", "n_for_m"), ("2", "percent_off"),
                                         ("3", "fixed_price")])
def test_kinds_and_price_effects(code, found):
    assert kind("shufersal", _item(code)) == found and has_price_effect("shufersal", _item(code))
    for item in (_item("0"), _item("0", price="5.00")):  # a zero link, priced or not
        assert kind("shufersal", item) is None and not has_price_effect("shufersal", item)
    for other in ("6", "12"):
        assert kind("shufersal", _item(other)) is None and not has_price_effect("shufersal", _item(other))


def test_in_day_boundaries():
    promotion = _promotion(start="2026-11-07T00:00:00.000", end="2026-11-28T02:59:00.000")
    assert dates(promotion) == (date(2026, 11, 7), date(2026, 11, 28))
    assert in_day(promotion, date(2026, 11, 7))  # starts on the day
    assert in_day(promotion, date(2026, 11, 28))  # ends on the day
    assert not in_day(promotion, date(2026, 11, 29))  # ended the day before
    assert not in_day(promotion, date(2026, 11, 6))  # starts the day after


@pytest.mark.parametrize("field", ["PromotionStartDateTime", "PromotionEndDateTime"])
def test_an_unreadable_date_is_a_format_change(field):
    promotion = _promotion() | {field: "28/11/2026 23:59"}
    with pytest.raises(PromotionFormatChanged) as refused:
        in_day(promotion, date(2026, 11, 7))
    assert str(refused.value) == f"{field} '28/11/2026 23:59' is not a date"


def test_min_spend_from_any_group():
    assert min_spend([_group("1"), _group("2", "50.00")]) == Decimal("50.00")
    zero_group = (_group("1", "75.00"), [_item("0")])  # the condition's group carries the basket
    kind_group = (_group("2"), [_item("10", price="10.00")])
    assert min_spend(_record(zero_group, kind_group).groups) == Decimal("75.00")
    assert min_spend([_group("1"), _group("2"), _group("3", "20.00"), _group("4")]) == Decimal("20.00")
    assert min_spend([_group("1"), _group("2"), _group("3"), _group("4", "30.00")]) == Decimal("30.00")
    assert min_spend([_group("1", "50.00"), _group("2", "75.00")]) == Decimal("75.00")
    assert min_spend([_group("1", "75.00"), _group("2", "50.00")]) == Decimal("75.00")
    assert min_spend([_group("1", "0.00"), _group("2")]) is None
    assert min_spend([]) is None


@pytest.mark.parametrize("amount", ["75,00", "₪75", "1E+5000", "1E-5000"])
def test_an_unreadable_min_spend_is_a_format_change(amount):
    with pytest.raises(PromotionFormatChanged) as refused:  # read as none, a ₪75 basket would show as no condition
        min_spend([_group("1"), _group("2", amount)])
    assert str(refused.value) == f"MinPurchaseAmount {amount!r} is not an amount"


# number's bound: a value no chain could publish as a price, a quantity, a rate or an amount reads as no number

@pytest.mark.parametrize("text", ["1E+5000", "1E-5000", "1." + "2" * 5000, "1000000000000", "0.0000000000001",
                                  "0E-5000", "-1E+13"],
                         ids=["huge", "tiny", "5,000 places", "13 digits", "13 places", "zero at 5,000 places",
                              "minus 14 digits"])
def test_a_number_past_twelve_places_or_twelve_digits_is_no_number(text):
    # the first three make a Fraction whose numerator or denominator is past the 4,300 digits Python prints
    assert number(text) is None


@pytest.mark.parametrize("text", ["8.72", "0.000000000001", "999999999999.999999999999", "1E+11", "1E-12", "-3", "0",
                                  "75.00"])
def test_a_number_within_twelve_places_and_twelve_digits_reads(text):
    assert number(text) == Decimal(text)


def test_a_gift_value_of_an_exponent_no_chain_writes_is_a_format_change():
    for value in ("1E+5000", "1E-5000"):
        with pytest.raises(PromotionFormatChanged, match=r"^ramilevy: IsGiftItem '1E[+-]5000' is not a quantity$"):
            gift_value("ramilevy", value)

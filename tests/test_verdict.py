"""The verdict's rules, S0 to S8, and the front list (`shopper.verdict`; docs/store-first.md, "The rules"; the plan's
Task 1 and its "Where the design leaves room").

The pairs and column-days are built by hand, as tests/test_measures.py builds them, with promotion structs as
`shopper.items` writes them and `shopper.history` reads them back (dates and Decimals); the windows are
`shopper.history`'s and `shopper.measures`', tested there. Every figure is synthetic, the barcode included."""
import random
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

import shopper_random
from basket.record import money
from shopper.deals import to_agora
from shopper.history import READ_DAYS, ColumnDay, Pair, Point
from shopper.measures import promotion_points
from shopper.verdict import (CALLS, DEAL_MIN, Day, DealRow, Verdict, checked, counts_today, day_price, front_list,
                             on_list, passes_bar, tracked, usual_price, verdict)

DAY = date(2026, 11, 20)
COLUMN = "shufersal-deal"
CODE = "2000000000046"   # a synthetic GS1 code
D = Decimal


def back(n: int) -> date:
    return DAY - timedelta(days=n)


def _struct(price: str | Fraction | None = "4.20", *, wide: bool = True, valid: bool = True, kind: str | None = "3",
            start: date = back(60), end: date = DAY + timedelta(days=7), buy: str = "1.000", restrictions=(),
            promotion_id: str = "1") -> dict:
    """A promotion struct as the items table holds it, read back: a fixed price of `price` unless said."""
    exact = None if price is None else Fraction(price)
    return {"promotion_id": promotion_id, "description": "מבצע בדיקה", "start": start, "end": end, "kind": kind,
            "buy": D(buy), "price": None if exact is None else to_agora(exact),
            "price_exact": None if exact is None else str(exact), "per": "unit", "low": None, "high": None,
            "valid": valid, "why": None if valid else "not below twice the listed price",
            "restrictions": list(restrictions), "programmes": [], "min_spend": None, "stores": 4, "wide": wide}


def _point(day: date, listed: str = "5.00", *structs: dict, on_promotion: bool | None = None,
           unread: bool = False) -> Point:
    """A point on `day`; on promotion when a struct is wide, has a kind and runs that day, as the items table says,
    unless `on_promotion` says otherwise; `unread` as on a day whose promotions were not read (None, no struct)."""
    if unread:
        on_promotion, structs = None, ()
    elif on_promotion is None:
        on_promotion = any(found["wide"] and found["kind"] is not None and found["start"] <= day <= found["end"]
                           for found in structs)
    return Point(day=day, listed=D(listed), low=D(listed), high=D(listed), listing=4, wide=True,
                 on_promotion=on_promotion, next_start=None, promotions=tuple(structs))


def _shelf(n: int, listed: str = "5.00") -> Point:
    """n days back, at the listed price, no promotion."""
    return _point(back(n), listed)


def _sale(n: int, price: str, listed: str = "5.00") -> Point:
    """n days back, on a promotion that counts at `price`."""
    return _point(back(n), listed, _struct(price))


def _unknown(n: int, listed: str = "5.00") -> Point:
    """n days back, a sale day of unknown price: on promotion, its only struct's price not valid."""
    return _point(back(n), listed, _struct("13", valid=False))


def _today(listed: str = "5.00", *structs: dict, **kwargs) -> Point:
    return _point(DAY, listed, *structs, **kwargs)


def _pair(points) -> Pair:
    return Pair(column=COLUMN, code=CODE, points={point.day: point for point in points})


def _column_days(holes=(), promo_holes=(), missing=(), first: int = READ_DAYS) -> dict[tuple[str, date], ColumnDay]:
    """The column's days from `first` (90) days back to the day, each a record with its promotions read unless it is a
    price hole (1 of 4 stores with a file), a promotion hole (1 of 4 with a promotion file) or its chain's table is
    missing."""
    found = {}
    for n in range(first, -1, -1):
        day = back(n)
        present = day not in missing
        with_file = 0 if not present else 1 if day in holes else 4
        promo_hole = day in promo_holes or not present
        found[(COLUMN, day)] = ColumnDay(column=COLUMN, slug="shufersal", day=day, present=present,
                                         hole=day in holes or not present, promo_hole=promo_hole,
                                         promotions_error=None, included=4 if present else 0, with_file=with_file,
                                         counted=with_file, promo_files=1 if promo_hole and present else with_file)
    return found


def _judge(points, **days) -> Verdict:
    return verdict(_pair(points), COLUMN, _column_days(**days), DAY)


def _history(n: int = 30, listed: str = "5.00") -> list[Point]:
    """The n days before the day at the listed price, no promotion."""
    return [_shelf(back_n, listed) for back_n in range(1, n + 1)]


# ---- S0 and S1 ----

def test_a_tracked_day_has_prices_and_promotions_read():
    """S0, per product: a day counts when the column's prices and promotions were read and the product is listed."""
    points = [_shelf(n) for n in range(1, READ_DAYS + 1) if n != 40]          # not listed 40 days back
    column_days = _column_days(holes={back(10)}, promo_holes={back(20)}, missing={back(30)})
    found = tracked(_pair(points), column_days, DAY)
    assert [day.day for day in found] == [back(n) for n in range(READ_DAYS, 0, -1) if n not in (10, 20, 30, 40)]
    assert {(day.listed, day.price, day.on_sale) for day in found} == {(D("5.00"), D("5.00"), False)}
    # today and a day before the 90 are never tracked
    older = _pair([_shelf(READ_DAYS + 1), _today()])
    assert tracked(older, _column_days(first=READ_DAYS + 1), DAY) == ()


def test_the_day_price_is_the_lower_of_listed_and_the_lowest_counting_deal():
    """S1: the lower of the listed price and the lowest deal among the promotions that count (S3's filter)."""
    structs = (_struct("4.50"), _struct("4.20"), _struct("3.00", wide=False), _struct("2", valid=False),
               _struct("1.50", kind=None), _struct("1.00", end=back(1)), _struct("1.00", start=DAY + timedelta(days=1)))
    assert day_price(_today("5.00", *structs), DAY) == D("4.20")
    assert day_price(_today("5.00", _struct("5.50")), DAY) == D("5.00")       # a valid deal above the listed price
    assert day_price(_today("5.00"), DAY) == D("5.00")
    # figures as shown: a listed median of 4.995 shows 5.00, a deal of 10/3 shows 3.33
    assert str(day_price(_today("4.995"), DAY)) == "5.00"
    assert str(day_price(_today("5.00", _struct(Fraction(10, 3))), DAY)) == "3.33"


def test_counts_today_is_wide_valid_with_a_kind_and_running():
    assert counts_today(_struct(), DAY)
    assert counts_today(_struct(start=DAY, end=DAY), DAY)
    for struct in (_struct(wide=False), _struct(valid=False), _struct(kind=None), _struct(end=back(1)),
                   _struct(start=DAY + timedelta(days=1))):
        assert not counts_today(struct, DAY), struct


def test_a_sale_day_of_unknown_price_has_no_day_price_and_is_on_sale():
    """S1 and S7: on promotion with no price that counts is a sale day of unknown price."""
    found = tracked(_pair([_unknown(1)]), _column_days(), DAY)
    assert found == (Day(day=back(1), listed=D("5.00"), price=None, on_sale=True),)
    assert tracked(_pair([_sale(1, "4.00")]), _column_days(), DAY) == (
        Day(day=back(1), listed=D("5.00"), price=D("4.00"), on_sale=True),)


# ---- S2 ----

def test_the_usual_price_is_the_higher_middle():
    assert usual_price([D("3"), D("1"), D("2")]) == D("2")
    assert usual_price([D("1"), D("2"), D("3"), D("4")]) == D("3")
    assert usual_price([D("7.90")] * 13 + [D("9.90")] * 13) == D("9.90")
    assert usual_price([D("9.90")] * 13 + [D("7.90")] * 13) == D("9.90")       # sorted first
    assert usual_price([D("4.00")]) == D("4.00")


def test_unknown_price_days_never_push_the_usual_price_up():
    """Call 9: the unknown-price sale days have no day price, so they never stand in at the listed price."""
    points = [*(_sale(n, "4.00", listed="6.00") for n in range(1, 11)), *(_unknown(n, "6.00") for n in range(11, 19)),
              *(_shelf(n, "6.00") for n in range(19, 28)), _today("6.00", _struct("3.00"))]
    found = _judge(points)
    assert (found.call, found.usual, found.saving, len(found.priced), len(found.days)) == (
        "deal", D("4.00"), D("1.00"), 19, 27)
    assert sum(day.on_sale for day in found.days) == 18


# ---- S3 and S4 ----

def test_todays_price_is_the_lowest_counting_deal_club_only_included():
    found = _judge([*_history(), _today("5.00", _struct("4.20"), _struct("3.90", restrictions=["club"]))])
    assert (found.today_price, found.struct["restrictions"], found.counting) == (D("3.90"), ["club"], True)
    # a tie goes to the first struct; the lowest is the lowest exact price, not the first of those shown the same
    tie = _judge([*_history(), _today("5.00", _struct("3.90", restrictions=["club"]), _struct("3.90"))])
    assert tie.struct["restrictions"] == ["club"]
    exact = _judge([*_history(), _today("5.00", _struct("3.334", promotion_id="1"),
                                        _struct(Fraction(10, 3), promotion_id="2"))])
    assert (exact.struct["promotion_id"], exact.today_price) == ("2", D("3.33"))
    # a counting deal above the listed price is still today's price
    above = _judge([*_history(), _today("5.00", _struct("5.50"))])
    assert (above.call, above.today_price, above.saving) == ("no_deal", D("5.50"), D("-0.50"))


def _against(usual: str, deal: str | Fraction) -> Verdict:
    return _judge([*_history(listed=usual), _today(usual, _struct(deal))])


def test_deal_from_one_shekel_on_figures_as_shown():
    """S4 and call 13 (Review Focus 3): the saving compares as shown, to the agora."""
    found = _against("5.00", "4.00")
    assert (found.call, found.usual, found.today_price, found.saving) == ("deal", D("5.00"), D("4.00"), D("1.00"))
    found = _against("5.00", "4.01")
    assert (found.call, found.saving) == ("no_deal", D("0.99"))
    # "3 for ₪10.00" shows ₪3.33: ₪1.00 off a usual ₪4.33 as shown, though the exact saving is ₪0.9966...
    found = _against("4.33", Fraction(10, 3))
    assert (found.call, found.today_price, found.saving) == ("deal", D("3.33"), D("1.00"))
    assert str(found.saving) == "1.00" and DEAL_MIN == D("1.00")


def test_the_shades():
    """S5, a deal's only: ₪1.00 to ₪2.99, ₪3.00 to ₪4.99, ₪5.00 or more."""
    for saving, shade in (("1.00", "deal-1"), ("2.99", "deal-1"), ("3.00", "deal-2"), ("4.99", "deal-2"),
                          ("5.00", "deal-3"), ("19.90", "deal-3")):
        found = _against("25.00", str(D("25.00") - D(saving)))
        assert (found.call, found.saving, found.shade) == ("deal", D(saving), shade)
    found = _against("5.00", "4.50")
    assert (found.call, found.shade) == ("no_deal", None)
    assert _judge([*_history(), _today()]).shade is None


# ---- the calls without a verdict, in the plan's order ----

def _cases():
    sale = _struct("3.00")
    return {
        "too_few": ([*_history(), _today("5.00", sale)], {"holes": {DAY}}),
        "not_sold": (_history(), {}),
        "unread_today": ([*_history(), _today("5.00", sale)], {"promo_holes": {DAY}}),
        "no_sale": ([*_history(), _today()], {}),
        "some_stores": ([*_history(), _today("5.00", _struct("3.00", wide=False))], {}),
        "price_unread": ([*_history(), _today("5.00", _struct("13", valid=False))], {}),
        "new": ([_today("5.00", sale)], {}),
        "no_history": ([*(_point(back(n), unread=True) for n in range(1, 6)), _today("5.00", sale)],
                       {"promo_holes": {back(n) for n in range(1, 6)}}),
        "mostly_unknown": ([*(_unknown(n) for n in range(1, 15)), *(_shelf(n) for n in range(15, 28)),
                            _today("5.00", sale)], {}),
        "13 of 27": ([*(_unknown(n) for n in range(1, 14)), *(_shelf(n) for n in range(14, 28)),
                      _today("5.00", sale)], {}),
        "13 of 26": ([*(_unknown(n) for n in range(1, 14)), *(_shelf(n) for n in range(14, 27)),
                      _today("5.00", sale)], {}),
    }


@pytest.mark.parametrize("case, expected", [
    ("too_few", ("too_few", None)), ("not_sold", ("not_sold", None)), ("unread_today", ("unread_today", None)),
    ("no_sale", ("no_sale", None)), ("some_stores", ("some_stores", None)), ("price_unread", ("price_unread", None)),
    ("new", ("new", None)), ("no_history", ("no_history", None)), ("mostly_unknown", ("mostly_unknown", None)),
    ("13 of 27", ("deal", 14)), ("13 of 26", ("deal", 13))])
def test_each_no_verdict_call(case, expected):
    """Review Focus 2: today unreadable, or nothing to judge, gives no verdict; 13 unknown days of 27 or of 26 are not
    more than half, so they are judged on the priced days."""
    points, days = _cases()[case]
    found = _judge(points, **days)
    assert found.call in CALLS
    if expected[1] is None:
        assert (found.call, found.usual, found.saving, found.shade) == (expected[0], None, None, None)
    else:
        assert (found.call, len(found.priced), found.usual, found.saving) == (expected[0], expected[1], D("5.00"),
                                                                            D("2.00"))


def test_the_calls_before_todays_promotions_know_no_price_today():
    """too_few, not_sold and unread_today: no struct, no today's price, no last this low, no last sale."""
    for case in ("too_few", "not_sold", "unread_today"):
        points, days = _cases()[case]
        found = _judge(points, **days)
        assert (found.struct, found.today_price, found.last_low, found.last_sale, found.on_sale_today,
                found.counting) == (None, None, None, None, False, False), case
        assert len(found.days) == 30
    assert verdict(None, COLUMN, _column_days(), DAY) == Verdict(
        column=COLUMN, call="not_sold", days=(), today_price=None, struct=None, usual=None, saving=None, last_low=None,
        last_sale=None, on_sale_today=False)
    assert verdict(None, COLUMN, _column_days(holes={DAY}), DAY).call == "too_few"


def test_a_point_today_without_a_listed_price_is_not_sold():
    point = Point(day=DAY, listed=None, low=None, high=None, listing=0, wide=False, on_promotion=False, next_start=None,
                  promotions=())
    assert _judge([*_history(), point]).call == "not_sold"


def test_the_calls_without_a_counting_promotion_take_the_listed_price():
    for case in ("no_sale", "some_stores", "price_unread"):
        points, days = _cases()[case]
        found = _judge(points, **days)
        assert (found.today_price, found.struct, found.counting) == (D("5.00"), None, False), case
    assert _judge(*_cases()["price_unread"][:1]).on_sale_today is True
    assert _judge(*_cases()["some_stores"][:1]).on_sale_today is False


def test_a_wide_promotion_of_unknown_price_comes_before_one_at_some_stores():
    found = _judge([*_history(), _today("5.00", _struct("3.00", wide=False), _struct("13", valid=False))])
    assert found.call == "price_unread"


def test_a_zero_link_promotion_is_not_a_sale():
    """A RewardType 0 struct has no kind: running and wide, it is no sale, not even one of unknown price."""
    zero = _struct(None, kind=None, valid=False)
    found = _judge([*_history(), _today("5.00", zero, on_promotion=False)])
    assert (found.call, found.on_sale_today) == ("no_sale", False)
    assert day_price(_today("5.00", zero, on_promotion=False), DAY) == D("5.00")


# ---- S6 and S7 ----

def test_last_this_low():
    """S6: the latest priced day at or below today's price, an equal price included."""
    points = [*_history(), _sale(20, "3.90"), _sale(10, "4.00"), _unknown(5), _today("5.00", _struct("4.00"))]
    found = _judge(points)
    assert (found.last_low.day, found.last_low.price) == (back(10), D("4.00"))
    lower = _judge([*points[:-1], _today("5.00", _struct("3.95"))])
    assert (lower.last_low.day, lower.last_low.price) == (back(20), D("3.90"))
    assert _judge([*points[:-1], _today("5.00", _struct("3.80"))]).last_low is None
    # on a no_sale, today's price is the listed price: the latest day at or below 5.00
    plain = _judge([*points[:-1], _today("5.00")])
    assert (plain.call, plain.today_price, plain.last_low.day) == ("no_sale", D("5.00"), back(1))
    # on unread_today, today's price is not known
    unread = _judge([*points[:-1], _today("5.00", _struct("4.00"))], promo_holes={DAY})
    assert (unread.call, unread.today_price, unread.last_low) == ("unread_today", None, None)


def test_how_often_and_the_last_sale_before_this_one():
    """S7, over the tracked days: runs by on_sale, an untracked day neither breaking nor extending one."""
    def history(today: Point, **days) -> Verdict:
        points = [*_history(), *(_sale(n, "4.00") for n in (10, 9, 8)), *(_sale(n, "3.50") for n in (4, 3, 2, 1)),
                  today]
        return _judge(points, **days)

    # three back is a promotion hole: the run of 4 to 1 back is one run, running into today, so the last sale before
    # this one is the run of 10 to 8
    found = history(_today("5.00", _struct("3.50")), promo_holes={back(3)})
    assert (found.on_sale_today, found.last_sale.day, found.last_sale.price) == (True, back(8), D("4.00"))
    assert sum(day.on_sale for day in found.days) == 6 and len(found.days) == 29
    # with no sale today, the latest run is the last sale
    found = history(_today(), promo_holes={back(3)})
    assert (found.call, found.on_sale_today, found.last_sale.day, found.last_sale.price) == (
        "no_sale", False, back(1), D("3.50"))
    # a sale starting today: the run that ended before is the last one
    starting = _judge([*_history(), *(_sale(n, "4.00") for n in (10, 9, 8)), _today("5.00", _struct("3.50"))])
    assert starting.last_sale.day == back(8)
    # a last day of unknown price
    unknown = _judge([*_history(), _sale(6, "4.00"), _unknown(5), _today()])
    assert (unknown.last_sale.day, unknown.last_sale.price) == (back(5), None)
    # no sale before this one
    only = _judge([*_history(), *(_sale(n, "4.00") for n in (2, 1)), _today("5.00", _struct("4.00"))])
    assert only.last_sale is None
    assert _judge([*_history(), _today()]).last_sale is None


# ---- the front list ----

def test_the_bar_is_twenty_days_with_records_in_the_thirty():
    assert not passes_bar(_pair(_history(19)), _column_days(), DAY)
    assert passes_bar(_pair(_history(20)), _column_days(), DAY)
    assert passes_bar(_pair(_history(20)), _column_days(promo_holes={back(5)}), DAY)    # a promotion hole is a record
    assert not passes_bar(_pair(_history(20)), _column_days(holes={back(5)}), DAY)       # a price hole is not
    assert not passes_bar(_pair([_shelf(n) for n in range(12, 32)]), _column_days(), DAY)   # 19 of them in the 30


def _verdict(call: str, saving: str | None, struct: dict | None = None) -> Verdict:
    return Verdict(column=COLUMN, call=call, days=(), today_price=D("3.00"), struct=struct,
                   usual=None if saving is None else D("3.00") + D(saving),
                   saving=None if saving is None else D(saving), last_low=None, last_sale=None,
                   on_sale_today=struct is not None)


def test_the_front_list():
    rows = [DealRow(COLUMN, code, f"מוצר {code}", _verdict("deal", saving, _struct()))
            for code, saving in (("10", "2.00"), ("8", "1.00"), ("9", "2.00"), ("7", "3.00"), ("11", "1.00"))]
    assert [row.code for row in front_list(rows)] == ["7", "9", "10", "8", "11"]
    assert [row.code for row in front_list(reversed(rows))] == ["7", "9", "10", "8", "11"]
    passing, failing = _pair(_history(20)), _pair(_history(19))
    days = _column_days()
    deal, no_deal = _judge([*_history(20), _today("5.00", _struct("4.00"))]), _judge(
        [*_history(20), _today("5.00", _struct("4.50"))])
    assert (deal.call, no_deal.call) == ("deal", "no_deal")
    assert on_list(deal, passing, days, DAY) and not on_list(deal, failing, days, DAY)
    assert not on_list(no_deal, passing, days, DAY)
    assert checked(no_deal, passing, days, DAY) and checked(deal, passing, days, DAY)
    assert not checked(no_deal, failing, days, DAY)
    no_sale = _judge([*_history(20), _today()])
    assert not checked(no_sale, passing, days, DAY) and not on_list(no_sale, passing, days, DAY)


# ---- random histories ----

def test_random_histories_keep_the_rules():
    """Over tests/shopper_random.py's histories, today a record with its promotions read: the usual price is a priced
    price, the saving is usual minus today's, every Day is one promotion_points reads, a deal exactly from ₪1.00."""
    rng = random.Random(33)
    calls = set()
    for n in range(400):
        column_days = shopper_random.column_days(rng, COLUMN, "shufersal", back(READ_DAYS + 5), back(1))
        column_days[(COLUMN, DAY)] = _column_days()[(COLUMN, DAY)]
        pair = shopper_random.pair(rng, COLUMN, shopper_random.code(n), back(READ_DAYS + 5), DAY)
        found = verdict(pair, COLUMN, column_days, DAY)
        calls.add(found.call)
        read = promotion_points(pair, column_days, DAY)
        assert [day.day for day in found.days] == [point.day for point in read]
        assert [day.listed for day in found.days] == [D(money(point.listed)) for point in read]
        assert all(day.price is None or day.price <= day.listed for day in found.days)
        if found.call in ("deal", "no_deal"):
            assert found.usual in [day.price for day in found.priced]
            assert found.saving == found.usual - found.today_price
            assert (found.call == "deal") == (found.saving >= DEAL_MIN)
            assert found.counting
        else:
            assert (found.usual, found.saving) == (None, None)
    assert calls >= {"deal", "no_deal", "no_sale", "not_sold"}, calls

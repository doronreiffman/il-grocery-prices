"""The forecast's target, who gets a forecast and inputs pinned to the day (docs/shopper-site.md F1, F2 and F3, with its
"Changed after the survey", S1, and Call 22; the plan's Task 10 and the second pre-flight's B1 and S1).

Pairs and column-days are built by hand in the shapes `shopper.history` yields them (a struct's `start` and `end` are
dates, as DuckDB gives them back); one test reads a pair back from items tables through `load` and `History.pairs`."""
from datetime import date, timedelta
from decimal import Decimal

from shopper.forecast import (FIRST_RECORD_DAY, MAX_HOLES, TARGET_VERSION, Outcome, closed_days, eligible, outcome)
from shopper.history import READ_DAYS, ColumnDay, Pair, Point, load
from shopper.items import HORIZON
from test_history import _row, _table

DAY = date(2026, 11, 30)
SHUF = "shufersal"
DEAL, EXPRESS, SHELI = "shufersal-deal", "shufersal-express", "shufersal-sheli"
CODE = "2000000000046"   # a synthetic GS1 code
NONE = Outcome(value=0, holes=0, first_day=None, promotion_id=None)


def ahead(days: int) -> date:
    return DAY + timedelta(days=days)


def _promotion(promotion_id="7", wide=True, kind="3", start=None, end=None):
    """One promotion on the item, in the items table's struct (`start` and `end` dates, as read back)."""
    return {"promotion_id": promotion_id, "description": "מבצע", "start": start or date(2026, 1, 1),
            "end": end or date(2027, 1, 1), "kind": kind, "buy": Decimal("1.000"), "price": Decimal("7.90"),
            "price_exact": "79/10", "per": None, "low": None, "high": None, "valid": True, "why": None,
            "restrictions": [], "programmes": [], "min_spend": None, "stores": 4, "wide": wide}


def _point(day: date, wide=True, on_promotion=False, next_start=None, promotions=()) -> Point:
    return Point(day=day, listed=Decimal("10.00"), low=Decimal("10.00"), high=Decimal("10.00"), listing=4, wide=wide,
                 on_promotion=on_promotion, next_start=next_start, promotions=tuple(promotions))


def _on(day: date, *promotions, **kwargs) -> Point:
    """A point on a wide promotion that day (the items table's `on_promotion`)."""
    return _point(day, on_promotion=True, promotions=promotions or (_promotion(),), **kwargs)


def _pair(points: dict[date, Point], column=DEAL) -> Pair:
    return Pair(column=column, code=CODE, points=points)


def _column_day(column: str, day: date, price_hole=False, promo_hole=False, present=True, slug=SHUF) -> ColumnDay:
    """A column-day as `shopper.history` reads it: 4 included stores, all with a price file and a promotion file,
    except where it is a price hole (1 of 4 with a price file), a promotion hole (no promotion file) or its chain's
    table was missing."""
    with_file = 1 if price_hole else 4
    return ColumnDay(column=column, slug=slug, day=day, present=present, hole=price_hole or not present,
                     promo_hole=promo_hole or not present, promotions_error=None, included=4, with_file=with_file,
                     counted=with_file, promo_files=0 if promo_hole else with_file)


def _days(column: str, offsets, price_holes=(), promo_holes=(), missing=(), absent=(), slug=SHUF):
    """The column's days at DAY + each offset in `offsets`; the offsets in `price_holes`, `promo_holes` and `missing`
    (the chain's table not there) are holes of that kind, and those in `absent` have no column-day at all."""
    return {(column, ahead(n)): _column_day(column, ahead(n), n in price_holes, n in promo_holes, n not in missing,
                                            slug)
            for n in offsets if n not in absent}


# The outcome (F1)

def test_a_promotion_on_day_14_counts_and_on_day_15_does_not():
    column_days = _days(DEAL, range(-20, 21))
    on_14 = _pair({ahead(14): _on(ahead(14))})
    on_15 = _pair({ahead(15): _on(ahead(15))})
    assert outcome(on_14, column_days, DAY) == Outcome(value=1, holes=0, first_day=ahead(14), promotion_id="7")
    assert outcome(on_15, column_days, DAY) == NONE


def test_a_promotion_on_the_day_itself_does_not_count():
    column_days = _days(DEAL, range(-20, 21))
    assert outcome(_pair({DAY: _on(DAY)}), column_days, DAY) == NONE
    assert outcome(_pair({ahead(1): _on(ahead(1))}), column_days, DAY).first_day == ahead(1)


def test_an_at_some_stores_promotion_does_not_count():
    column_days = _days(DEAL, range(-20, 21))
    narrow = _promotion("5", wide=False)
    # on a day when no wide promotion runs, the items table says on_promotion False whatever structs the item holds
    at_some_stores = _pair({ahead(3): _point(ahead(3), promotions=(narrow,)),
                            ahead(4): _point(ahead(4), promotions=(narrow, _promotion("6", wide=False, kind=None)))})
    assert outcome(at_some_stores, column_days, DAY) == NONE


def test_an_item_not_listed_in_the_window_has_outcome_0():
    assert outcome(_pair({}), _days(DEAL, range(-20, 21)), DAY) == NONE


def test_the_outcome_names_the_first_day_and_the_smallest_wide_promotion_by_number():
    column_days = _days(DEAL, range(-20, 21))
    pair = _pair({
        ahead(5): _on(ahead(5), _promotion("10"), _promotion("9"), _promotion("100")),
        ahead(2): _on(ahead(2), _promotion("30"), _promotion("12")),
        ahead(9): _on(ahead(9), _promotion("1")),
    })
    assert outcome(pair, column_days, DAY) == Outcome(value=1, holes=0, first_day=ahead(2), promotion_id="12")
    ten_nine = _pair({ahead(5): _on(ahead(5), _promotion("10"), _promotion("9"))})
    assert outcome(ten_nine, column_days, DAY).promotion_id == "9"   # by number: "10" is the smaller as text


def test_the_evidence_is_a_wide_promotion_with_a_kind_running_that_day():
    column_days = _days(DEAL, range(-20, 21))
    day = ahead(4)
    pair = _pair({day: _on(
        day,
        _promotion("1", wide=False),                    # at some stores
        _promotion("2", kind=None),                     # a link of no price effect (price not read)
        _promotion("3", start=ahead(5)),                # listed, not started
        _promotion("4", end=ahead(3)),                  # ended
        _promotion("8", start=day, end=day),            # starts and ends that day: runs
        _promotion("9"),
    )})
    assert outcome(pair, column_days, DAY).promotion_id == "8"
    only_others = _pair({day: _on(day, _promotion("1", wide=False), _promotion("3", start=ahead(5)))})
    assert outcome(only_others, column_days, DAY) == Outcome(value=1, holes=0, first_day=day, promotion_id=None)


def test_four_holes_score_and_five_do_not():
    pair = _pair({ahead(14): _on(ahead(14))})
    kinds = dict(price_holes=(2,), promo_holes=(3,), missing=(4,), absent=(5,))   # four holes, one of each kind
    four = outcome(pair, _days(DEAL, range(-20, 21), **kinds), DAY)
    assert four == Outcome(value=1, holes=4, first_day=ahead(14), promotion_id="7")
    five = outcome(pair, _days(DEAL, range(-20, 21), **{**kinds, "price_holes": (2, 6)}), DAY)
    assert five == Outcome(value=None, holes=5, first_day=None, promotion_id=None)   # a promotion seen is not scored
    assert outcome(_pair({}), _days(DEAL, range(-20, 21), price_holes=range(1, 6)), DAY).value is None


def test_a_price_hole_is_an_outcome_hole():
    """Express on 5 November: 21 of its 94 included stores had a price file, every one with a promotion file."""
    def express(day: date) -> ColumnDay:
        return ColumnDay(column=EXPRESS, slug=SHUF, day=day, present=True, hole=True, promo_hole=False,
                         promotions_error=None, included=94, with_file=21, counted=21, promo_files=21)
    pair = _pair({}, EXPRESS)
    column_days = {(EXPRESS, ahead(n)): _column_day(EXPRESS, ahead(n)) for n in range(1, 15)}
    for n in (1, 2, 3, 4):
        column_days[(EXPRESS, ahead(n))] = express(ahead(n))
    assert outcome(pair, column_days, DAY) == Outcome(value=0, holes=4, first_day=None, promotion_id=None)
    column_days[(EXPRESS, ahead(5))] = express(ahead(5))
    assert outcome(pair, column_days, DAY).value is None


def test_a_column_with_no_counted_store_is_a_hole():
    """Its stores published nothing: no store counted, so no promotion hole (0 × 2 < 0 is false), yet a price hole."""
    empty = ColumnDay(column=EXPRESS, slug=SHUF, day=ahead(1), present=True, hole=True, promo_hole=False,
                      promotions_error=None, included=94, with_file=0, counted=0, promo_files=0)
    assert not empty.record
    column_days = {**_days(EXPRESS, range(6, 15)),
                   **{(EXPRESS, ahead(n)): ColumnDay(**{**empty.__dict__, "day": ahead(n)}) for n in range(1, 6)}}
    assert outcome(_pair({}, EXPRESS), column_days, DAY) == Outcome(value=None, holes=5, first_day=None,
                                                                    promotion_id=None)


def test_a_hole_days_promotion_is_not_read():
    """A hole makes no claim (S1): a wide promotion on a price hole day neither makes outcome 1 nor is evidence."""
    pair = _pair({ahead(3): _on(ahead(3)), ahead(6): _on(ahead(6), _promotion("40"))})
    column_days = _days(DEAL, range(-20, 21), price_holes=(3,), promo_holes=())
    assert outcome(pair, column_days, DAY) == Outcome(value=1, holes=1, first_day=ahead(6), promotion_id="40")
    assert outcome(_pair({ahead(3): _on(ahead(3))}), column_days, DAY) == Outcome(
        value=0, holes=1, first_day=None, promotion_id=None)


def test_a_day_the_history_does_not_hold_is_a_hole():
    column_days = _days(DEAL, range(-20, 8))   # nothing after day 7
    found = outcome(_pair({}), column_days, DAY)
    assert (found.value, found.holes) == (None, 7)


def test_a_hole_in_another_column_is_not_a_hole_here():
    """Express is a hole for five days; its chain's other columns have records."""
    column_days = {**_days(EXPRESS, range(-20, 21), price_holes=range(1, 6)), **_days(DEAL, range(-20, 21)),
                   **_days(SHELI, range(-20, 21), promo_holes=range(3, 7))}
    pair = {ahead(14): _on(ahead(14))}
    assert outcome(_pair(pair, DEAL), column_days, DAY) == Outcome(value=1, holes=0, first_day=ahead(14),
                                                                   promotion_id="7")
    assert outcome(_pair(pair, EXPRESS), column_days, DAY).value is None
    assert outcome(_pair(pair, SHELI), column_days, DAY).holes == 4


# Who gets a forecast (F2, Call 22)

def test_who_gets_a_forecast():
    column_days = _days(DEAL, range(-5, 1))
    cases = {
        "yes": _point(DAY),
        "not_wide": _point(DAY, wide=False),
        "on_promotion": _on(DAY),
        "starts_soon": _point(DAY, next_start=ahead(3)),
    }
    for answer, point in cases.items():
        assert eligible(_pair({DAY: point}), column_days, DAY) == answer
    assert eligible(_pair({}), column_days, DAY) == "not_wide"   # not listed that day: not listed widely


def test_the_answers_have_an_order():
    column_days = _days(DEAL, range(-5, 1))
    on_and_soon = _on(DAY, next_start=ahead(9))
    assert eligible(_pair({DAY: on_and_soon}), column_days, DAY) == "on_promotion"
    assert eligible(_pair({DAY: _on(DAY, wide=False)}), column_days, DAY) == "not_wide"
    assert eligible(_pair({DAY: _point(DAY, wide=False, next_start=ahead(2))}), column_days, DAY) == "not_wide"


def test_a_hole_column_day_gets_no_forecast():
    """S1: a column-day that is no record answers "hole", whatever the row says; so does a promotion hole."""
    point = _point(DAY)
    for kind in ({"price_holes": (0,)}, {"promo_holes": (0,)}, {"missing": (0,)}, {"absent": (0,)}):
        assert eligible(_pair({DAY: point}), _days(DEAL, range(-5, 1), **kind), DAY) == "hole"
    assert eligible(_pair({}), _days(DEAL, range(-5, 1), price_holes=(0,)), DAY) == "hole"
    assert eligible(_pair({DAY: point}), _days(DEAL, range(-5, 1)), DAY) == "yes"
    # another column's hole is not this one's
    other = {**_days(DEAL, range(-5, 1)), **_days(EXPRESS, range(-5, 1), price_holes=(0,))}
    assert eligible(_pair({DAY: point}), other, DAY) == "yes"


# The closed days (question F (b) and (c))

def test_t_equal_to_d_minus_14_is_closed_and_d_minus_13_is_not():
    column_days = _days(DEAL, range(-READ_DAYS - 1, 2))
    points = {ahead(n): _point(ahead(n)) for n in (-READ_DAYS - 1, -READ_DAYS, -15, -14, -13, -1, 0)}
    points[ahead(-5)] = _on(ahead(-5))   # the window of d - 14 ends at d, and of d - 15 at d - 1
    found = closed_days(_pair(points), column_days, DAY)
    assert [t for t, _ in found] == [ahead(-READ_DAYS), ahead(-15), ahead(-14)]   # d - 91 and d - 13 are not
    assert [result.value for _, result in found] == [0, 1, 1]   # d - 90's window (d - 89 to d - 76) holds none
    assert dict(found)[ahead(-14)] == Outcome(value=1, holes=0, first_day=ahead(-5), promotion_id="7")


def test_closed_days_are_the_eligible_ones_with_their_outcomes():
    column_days = _days(DEAL, range(-60, 2))
    points = {
        ahead(-40): _point(ahead(-40)),                              # eligible; the promotion at -38 follows
        ahead(-39): _point(ahead(-39), wide=False),                  # not wide
        ahead(-38): _on(ahead(-38)),                                 # on promotion
        ahead(-37): _point(ahead(-37), next_start=ahead(-30)),       # starts soon
        ahead(-30): _on(ahead(-30)),
        ahead(-20): _point(ahead(-20)),                              # eligible, nothing after
    }
    found = closed_days(_pair(points), column_days, DAY)
    assert found == [(ahead(-40), Outcome(1, 0, ahead(-38), "7")), (ahead(-20), NONE)]


def test_a_closed_day_with_more_than_four_holes_is_left_out():
    """Question F (c): the scoring rule applied to the history. -40's window (-39 to -26) holds 5 holes, -41's
    (-40 to -27) holds 4."""
    column_days = _days(DEAL, range(-60, 2), price_holes=(-30, -29, -28, -27, -26))
    points = {ahead(-40): _point(ahead(-40)), ahead(-41): _point(ahead(-41)), ahead(-20): _point(ahead(-20))}
    found = closed_days(_pair(points), column_days, DAY)
    assert [t for t, _ in found] == [ahead(-41), ahead(-20)]
    assert found[0][1].holes == 4


def test_a_closed_day_that_was_a_hole_is_left_out():
    column_days = _days(DEAL, range(-60, 2), price_holes=(-30,))
    points = {ahead(-30): _point(ahead(-30)), ahead(-29): _point(ahead(-29))}
    assert [t for t, _ in closed_days(_pair(points), column_days, DAY)] == [ahead(-29)]


# Inputs pinned to the day (F3)

def test_later_days_change_nothing():
    """The same answers with and without points after d: an outcome of the last closed day ends at d."""
    points = {ahead(n): _point(ahead(n)) for n in range(-30, 1)}
    points[ahead(-25)] = _on(ahead(-25))
    full = dict(points)
    full[ahead(1)] = _on(ahead(1))            # d - 14's window ends at d: a promotion the day after is not in it
    full[ahead(2)] = _on(ahead(2))
    full.update({ahead(n): _point(ahead(n), wide=False) for n in range(3, 10)})
    column_days = _days(DEAL, range(-READ_DAYS - 1, 1))
    full_days = {**column_days, **_days(DEAL, range(1, 20), price_holes=(2,))}
    for day in (DAY, ahead(-1)):
        assert eligible(_pair(full), full_days, day) == eligible(_pair(points), column_days, day) == "yes"
        assert closed_days(_pair(full), full_days, day) == closed_days(_pair(points), column_days, day)
    last = closed_days(_pair(points), column_days, DAY)[-1]
    assert last == (ahead(-14), NONE)


# Through the history

def test_a_pair_read_back_from_items_tables_has_its_outcomes(tmp_path):
    promotion = {"promotion_id": "7", "description": "מבצע", "start": "2026-11-01", "end": "2026-12-31", "kind": "3",
                 "buy": "1.000", "price": "7.90", "price_exact": "79/10", "per": None, "low": None, "high": None,
                 "valid": True, "why": None, "restrictions": [], "programmes": [], "min_spend": None, "stores": 4,
                 "wide": True}
    first = DAY - timedelta(days=READ_DAYS)
    for back in range(READ_DAYS + 1):
        day = first + timedelta(days=back)
        listed = [_row(DEAL, CODE)]
        if day in (DAY - timedelta(days=10), DAY - timedelta(days=3)):
            listed = [_row(DEAL, CODE, on_promotion=True, promotions=[promotion])]
        holes = (DEAL,) if day == DAY - timedelta(days=12) else ()
        _table(tmp_path, SHUF, day, listed, holes=holes)
    history = load(tmp_path, DAY, [SHUF])
    (pair,) = [found for found in history.pairs() if found.column == DEAL]
    assert eligible(pair, history.column_days, DAY) == "yes"
    assert eligible(pair, history.column_days, DAY - timedelta(days=10)) == "on_promotion"
    assert eligible(pair, history.column_days, DAY - timedelta(days=12)) == "hole"
    assert outcome(pair, history.column_days, DAY - timedelta(days=14)) == Outcome(
        value=1, holes=1, first_day=DAY - timedelta(days=10), promotion_id="7")
    found = dict(closed_days(pair, history.column_days, DAY))
    assert DAY - timedelta(days=14) in found and DAY - timedelta(days=12) not in found
    assert found[DAY - timedelta(days=14)].value == 1
    assert found[DAY - timedelta(days=20)] == Outcome(value=1, holes=1, first_day=DAY - timedelta(days=10),
                                                      promotion_id="7")
    assert found[DAY - timedelta(days=90)] == NONE


def test_the_target_versions_fixed_values():
    assert (MAX_HOLES, FIRST_RECORD_DAY, TARGET_VERSION, HORIZON) == (4, 30, "1", 14)

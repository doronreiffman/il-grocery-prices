"""The forecast's target, who gets a forecast and inputs pinned to the day (docs/shopper-site.md F1, F2 and F3, with its
"Changed after the survey", S1, and Call 22; the plan's Task 10 and the second pre-flight's B1 and S1); the version 1
model, its two baselines and the forecasts file (F4, F5, question F; the plan's Task 11).

Pairs and column-days are built by hand in the shapes `shopper.history` yields them (a struct's `start` and `end` are
dates, as DuckDB gives them back); a hand-built `History` streams such pairs to `forecasts`; two tests read pairs back
from items tables through `load` and `History.pairs`. Every expected share is worked out by hand in the fixture's
docstring."""
import csv
import gzip
import io
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from shopper.forecast import (A_MIN_DAYS, DAYS_SINCE_CAP, FILE_FIELDS, FIRST_RECORD_DAY, MAX_HOLES, MODEL_VERSION, N0,
                              TARGET_VERSION, Forecast, Outcome, closed_days, eligible, forecasts, forecasts_csv,
                              outcome)
from shopper.history import READ_DAYS, ColumnDay, History, Pair, Point, load
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


# The model, the two baselines and the forecasts file (F4, F5)

CODES = ("2000000000015", "2000000000022", "2000000000039", "2000000000046", "2000000000053", "2000000000060",
         "2000000000077", "2000000000084", "2000000000091", "2000000000107", "2000000000114", "2000000000121",
         "2000000000138", "2000000000145")   # synthetic GS1 codes


class _Read(History):
    """A history of hand-built pairs, streamed by code, then column, as `History.pairs` streams them."""

    def __init__(self, column_days, pairs):
        super().__init__(DAY, column_days, {})
        self._pairs = sorted(pairs, key=lambda pair: (pair.code, pair.column))

    def pairs(self):
        yield from self._pairs


def _shape(code: str, on=(), off=(), column=DEAL) -> Pair:
    """A pair listed widely at DAY + each offset: on a wide promotion on the `on` offsets, off it on the `off` ones."""
    points = {ahead(n): _on(ahead(n)) for n in on}
    points.update({ahead(n): _point(ahead(n)) for n in off})
    return Pair(column=column, code=code, points=points)


def _records(*columns, first=-READ_DAYS):
    """A record on every day from DAY + `first` to DAY at each column."""
    found = {}
    for column in columns:
        found.update(_days(column, range(first, 1)))
    return found


def _hazard_pairs(column=DEAL) -> list[Pair]:
    """Three pairs to learn from and five probes, at one column. The closed days (offset: days since the last run
    ended, outcome; a run's day is on promotion, so it is no closed day):
      A (runs at -80 and -62): -75 (5, 1: -62 in -74 to -61), -70 (10, 1), -55 (7, 0)
      B (a run at -30): -85 (none, 0), -40 (none, 1: -30 in -39 to -26), -20 (10, 0)
      C (runs at -50 and -35): -45 (5, 1), -40 (10, 1)
    The hazard: 5 days 2 of 2, 10 days 2 of 3, 7 days 0 of 1, none 1 of 2; the column's share 5 of 8. B says yes only
    on A's -55 (-62 + 18 = -44, in -54 to -41; outcome 0), so B's yes share is 0 and its no share 5 of 7.
    The probes, listed off promotion on DAY and with no closed day (n 0, so p is the hazard and A the column's share):
    D (run at -10) 10 days since, E (-5) 5, F (no run) none, G (-7) 7, H (-3) 3, a bucket with no closed day."""
    return [_shape(CODES[0], on=(-80, -62), off=(-75, -70, -55), column=column),
            _shape(CODES[1], on=(-30,), off=(-85, -40, -20), column=column),
            _shape(CODES[2], on=(-50, -35), off=(-45, -40), column=column),
            _shape(CODES[3], on=(-10,), off=(0,), column=column),
            _shape(CODES[4], on=(-5,), off=(0,), column=column),
            _shape(CODES[5], off=(0,), column=column),
            _shape(CODES[6], on=(-7,), off=(0,), column=column),
            _shape(CODES[7], on=(-3,), off=(0,), column=column)]


def _b_pairs(column=DEAL) -> list[Pair]:
    """Two pairs to learn from and two probes, at one column. The closed days (offset: B's answer, outcome):
      L (runs -80 to -79, -70 to -69, and -60): -75 (no: one run before it, 1), -65 (yes: -69 + 9 = -60, 1),
        -55 (yes: -60 + 9 = -51, 0)
      N (a run at -35): -50 (no, 0: -35 is past -36), -45 (no, 1), -40 (no, 1)
    B's yes days 1 of 2, its no days 3 of 4; the column's share 4 of 6. The hazard: L's -75 and -65 4 days since, both
    1; L's -55 5 days, 0; N's none, 2 of 3. The probes, off promotion on DAY: PY (runs -20 to -19 and -3 to -2, so the
    next starts at -2 + 16 = DAY + 14) says yes, 2 days since; PN (no run) says no."""
    return [_shape(CODES[8], on=(-80, -79, -70, -69, -60), off=(-75, -65, -55), column=column),
            _shape(CODES[9], on=(-35,), off=(-50, -45, -40), column=column),
            _shape(CODES[10], on=(-20, -19, -3, -2), off=(-10, 0), column=column),
            _shape(CODES[11], off=(0,), column=column)]


def _blend_pairs(column=DEAL) -> list[Pair]:
    """X: 20 closed days, -90 to -71, and a run at -60, so 4 of them (-74 to -71) have outcome 1: A 1 of 5 from the
    pair; Y: 19 closed days, -90 to -72, the same run, 3 with outcome 1: A the column's share; Z: 20 closed days, -50 to
    -31, none with outcome 1. The column's share 7 of 59 (4 + 3 + 0 of 20 + 19 + 20). No closed day has a run before
    it, so the hazard's one bucket (none) and B's no share are 7 of 59 too. X and Y are listed off promotion on DAY,
    60 days after their run: a bucket with no closed day, so their hazard is the column's share."""
    return [_shape(CODES[0], on=(-60,), off=(*range(-90, -70), 0), column=column),
            _shape(CODES[1], on=(-60,), off=(*range(-90, -71), 0), column=column),
            _shape(CODES[2], off=tuple(range(-50, -30)), column=column)]


def _by_code(rows):
    return {row.code: row for row in rows}


def test_the_hazard_by_days_since():
    rows = forecasts(_Read(_records(DEAL), _hazard_pairs()), DAY)
    share = Fraction(5, 8)
    assert [(row.column, row.code, row.days_since, row.p) for row in rows] == [
        (DEAL, CODES[3], 10, Fraction(2, 3)), (DEAL, CODES[4], 5, Fraction(1)), (DEAL, CODES[5], None, Fraction(1, 2)),
        (DEAL, CODES[6], 7, Fraction(0)), (DEAL, CODES[7], 3, share)]
    assert {(row.n, row.a, row.a_from, row.b_says, row.b) for row in rows} == {(0, share, "column", False,
                                                                                Fraction(5, 7))}


def test_the_hazard_is_per_column():
    # one chain's two columns, the same shapes: a closed day at -20, 10 days after a run at -30, outcome 1 at Deal (a
    # run at -10) and 0 at Express; each column's probe is 10 days after a run at -10
    pairs = [_shape(CODES[0], on=(-30, -10), off=(-20,)), _shape(CODES[5], on=(-10,), off=(0,)),
             _shape(CODES[0], on=(-30,), off=(-20,), column=EXPRESS), _shape(CODES[3], on=(-10,), off=(0,),
                                                                             column=EXPRESS)]
    rows = forecasts(_Read(_records(DEAL, EXPRESS), pairs), DAY)
    assert [(row.column, row.code, row.days_since, row.p) for row in rows] == [
        (DEAL, CODES[5], 10, Fraction(1)), (EXPRESS, CODES[3], 10, Fraction(0))]


def test_days_since_over_60_is_60():
    # closed days 60 days after a run (-29, outcome 1: a run at -20) and 74 (-14, outcome 0), and one with none (-50, 0)
    pairs = [_shape(CODES[0], on=(-89, -20), off=(-29,)), _shape(CODES[1], on=(-88,), off=(-14,)),
             _shape(CODES[2], off=(-50,)),
             _shape(CODES[3], on=(-61,), off=(0,)), _shape(CODES[4], on=(-60,), off=(0,))]
    rows = _by_code(forecasts(_Read(_records(DEAL), pairs), DAY))
    assert DAYS_SINCE_CAP == 60
    assert (rows[CODES[3]].days_since, rows[CODES[3]].p) == (60, Fraction(1, 2))   # 61 days: "60 or more"
    assert (rows[CODES[4]].days_since, rows[CODES[4]].p) == (60, Fraction(1, 2))
    assert rows[CODES[4]].a == Fraction(1, 3)


def test_a_falls_back_to_the_column_under_20_days():
    rows = _by_code(forecasts(_Read(_records(DEAL), _blend_pairs()), DAY))
    assert A_MIN_DAYS == 20
    assert (rows[CODES[0]].n, rows[CODES[0]].a, rows[CODES[0]].a_from) == (20, Fraction(1, 5), "pair")
    assert (rows[CODES[1]].n, rows[CODES[1]].a, rows[CODES[1]].a_from) == (19, Fraction(7, 59), "column")
    assert CODES[2] not in rows    # Z is not listed on DAY


def test_the_blend_weight_is_n_over_n_plus_30():
    rows = _by_code(forecasts(_Read(_records(DEAL), _blend_pairs()), DAY))
    assert N0 == 30
    weight = Fraction(20, 20 + 30)
    assert rows[CODES[0]].p == weight * Fraction(1, 5) + (1 - weight) * Fraction(7, 59) == Fraction(223, 1475)
    assert rows[CODES[0]].days_since == 60
    assert rows[CODES[1]].p == Fraction(7, 59)       # A and the hazard both the column's share


def test_b_says_yes_when_the_last_gap_repeats_in_the_window():
    probes = {CODES[2]: (False, _shape(CODES[2], on=(-5,), off=(0,))),                         # one run
              CODES[3]: (True, _shape(CODES[3], on=(-20, -19, -3, -2), off=(-10, 0))),         # -2 + 16 = DAY + 14
              CODES[4]: (False, _shape(CODES[4], on=(-21, -20, -3, -2), off=(-10, 0))),        # -2 + 17 = DAY + 15
              CODES[5]: (True, _shape(CODES[5], on=(-10, -9, -5, -4, -3), off=(-7, 0))),       # -3 + 4 = DAY + 1
              CODES[6]: (False, _shape(CODES[6], on=(-10, -9, -5, -4), off=(-7, 0))),          # -4 + 4 = DAY itself
              CODES[7]: (False, _shape(CODES[7], off=(0,)))}                                   # no run
    learner = _shape(CODES[9], on=(-35,), off=(-50, -45, -40))
    rows = _by_code(forecasts(_Read(_records(DEAL), [learner, *(pair for _, pair in probes.values())]), DAY))
    assert {code: row.b_says for code, row in rows.items()} == {code: says for code, (says, _) in probes.items()}


def test_b_scored_at_its_calibrated_rate():
    rows = _by_code(forecasts(_Read(_records(DEAL), _b_pairs()), DAY))
    assert (rows[CODES[10]].b_says, rows[CODES[10]].b) == (True, Fraction(1, 2))
    assert (rows[CODES[11]].b_says, rows[CODES[11]].b) == (False, Fraction(3, 4))
    # no closed day at Express on which B said yes: a yes there takes the column's share, 2 of 3
    express = [_shape(CODES[9], on=(-35,), off=(-50, -45, -40), column=EXPRESS),
               _shape(CODES[10], on=(-20, -19, -3, -2), off=(-10, 0), column=EXPRESS)]
    (row,) = forecasts(_Read(_records(EXPRESS), express), DAY)
    assert (row.b_says, row.b, row.a) == (True, Fraction(2, 3), Fraction(2, 3))


def test_no_forecast_before_the_columns_30th_day_of_records():
    # Deal has records from DAY - 29 (its 30th day of records is DAY), Express from DAY - 28 (29 days); both have a
    # closed day to learn from
    pairs = [_shape(CODES[0], on=(-10,), off=(-20,)), _shape(CODES[1], off=(0,)),
             _shape(CODES[0], on=(-10,), off=(-20,), column=EXPRESS), _shape(CODES[1], off=(0,), column=EXPRESS)]
    column_days = {**_records(DEAL, first=-29), **_records(EXPRESS, first=-28)}
    history = _Read(column_days, pairs)
    assert (history.record_days(DEAL), history.record_days(EXPRESS), FIRST_RECORD_DAY) == (30, 29, 30)
    assert [(row.column, row.code, row.p) for row in forecasts(history, DAY)] == [(DEAL, CODES[1], Fraction(1))]


def test_a_column_with_no_closed_days_gets_no_forecast():
    # a probe listed off promotion every day, but none of its days a closed one (a hole every other day from -90
    # to -1 puts more than 4 holes in every window), and no other pair
    column_days = _days(DEAL, range(-READ_DAYS, 1), price_holes=range(-READ_DAYS + 1, 0, 2))
    pair = _shape(CODES[0], off=tuple(range(-READ_DAYS, 1)))
    assert closed_days(pair, column_days, DAY) == []
    assert forecasts(_Read(column_days, [pair]), DAY) == []


def test_only_eligible_pairs_get_a_forecast():
    others = [Pair(column=DEAL, code=CODES[10], points={DAY: _on(DAY)}),
              Pair(column=DEAL, code=CODES[11], points={DAY: _point(DAY, next_start=ahead(3))}),
              Pair(column=DEAL, code=CODES[12], points={DAY: _point(DAY, wide=False)})]
    rows = forecasts(_Read(_records(DEAL), [*_hazard_pairs(), *others]), DAY)
    assert [row.code for row in rows] == list(CODES[3:8])


def test_forecasts_read_nothing_after_the_day():
    pairs = [*_hazard_pairs(), *_b_pairs(EXPRESS), *_blend_pairs(SHELI)]
    later = [Pair(column=pair.column, code=pair.code,
                  points={**pair.points, **{ahead(n): _on(ahead(n)) for n in range(1, 20)}}) for pair in pairs]
    column_days = _records(DEAL, EXPRESS, SHELI)
    later_days = {**column_days, **_days(DEAL, range(1, 20)), **_days(EXPRESS, range(1, 20), price_holes=(3,))}
    assert forecasts(_Read(later_days, later), DAY) == forecasts(_Read(column_days, pairs), DAY)


def test_forecasts_read_through_load(tmp_path):
    # Deal's tables from DAY - 29 (30 days of records); a learner off promotion on -29 (outcome 0) and -20 (outcome
    # 1: a run at -10), and a probe listed on DAY
    promotion = {"promotion_id": "7", "description": "מבצע", "start": "2026-11-01", "end": "2026-12-31", "kind": "3",
                 "buy": "1.000", "price": "7.90", "price_exact": "79/10", "per": None, "low": None, "high": None,
                 "valid": True, "why": None, "restrictions": [], "programmes": [], "min_spend": None, "stores": 4,
                 "wide": True}
    for back in range(30):
        day = DAY - timedelta(days=back)
        rows = []
        if back in (29, 20):
            rows = [_row(DEAL, CODES[0])]
        if back == 10:
            rows = [_row(DEAL, CODES[0], on_promotion=True, promotions=[promotion])]
        if back == 0:
            rows = [_row(DEAL, CODES[1])]
        _table(tmp_path, SHUF, day, rows)
    history = load(tmp_path, DAY, [SHUF])
    half = Fraction(1, 2)
    assert forecasts(history, DAY) == [Forecast(column=DEAL, code=CODES[1], p=half, a=half, b=half, b_says=False,
                                                days_since=None, n=0, a_from="column")]


# The forecasts file

def _rows_of(body: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(gzip.decompress(body).decode())))


def test_the_file_names_the_versions_n0_and_the_code():
    body = forecasts_csv(forecasts(_Read(_records(DEAL), _hazard_pairs()), DAY), "f00d")
    header, *rows = _rows_of(body)
    assert tuple(header) == FILE_FIELDS == (
        "column", "barcode", "p_model", "p_a", "p_b", "b_says", "days_since", "n", "a_from", "model_version",
        "target_version", "n0", "code_sha")
    assert len(rows) == 5
    assert {tuple(row[9:]) for row in rows} == {(MODEL_VERSION, TARGET_VERSION, "30", "f00d")} == {("1", "1", "30",
                                                                                                    "f00d")}


def _forecast(column, code, p=Fraction(1, 2), a=Fraction(1, 4), b=Fraction(3, 4), b_says=False, days_since=None,
              n=0, a_from="column"):
    return Forecast(column=column, code=code, p=p, a=a, b=b, b_says=b_says, days_since=days_since, n=n, a_from=a_from)


def test_the_file_is_sorted_and_its_bytes_reproducible():
    rows = [_forecast(EXPRESS, CODES[0]), _forecast(DEAL, CODES[2]), _forecast(SHELI, CODES[1]),
            _forecast(DEAL, CODES[1]), _forecast(EXPRESS, CODES[3])]
    body = forecasts_csv(rows, "f00d")
    assert [tuple(row[:2]) for row in _rows_of(body)[1:]] == [
        (DEAL, CODES[1]), (DEAL, CODES[2]), (EXPRESS, CODES[0]), (EXPRESS, CODES[3]), (SHELI, CODES[1])]
    assert forecasts_csv(list(reversed(rows)), "f00d") == forecasts_csv(rows, "f00d") == body
    assert body[4:8] == b"\x00\x00\x00\x00"           # gzip's header time: none


def test_probabilities_are_written_to_six_decimals_half_up():
    rows = [_forecast(DEAL, CODES[0], p=Fraction(1, 2_000_000), a=Fraction(2, 3), b=Fraction(1, 3), b_says=True,
                      days_since=60, n=20, a_from="pair"),
            _forecast(DEAL, CODES[1], p=Fraction(1), a=Fraction(0), b=Fraction(1_234_567, 10_000_000))]
    assert _rows_of(forecasts_csv(rows, "f00d"))[1:] == [
        [DEAL, CODES[0], "0.000001", "0.666667", "0.333333", "1", "60", "20", "pair", "1", "1", "30", "f00d"],
        [DEAL, CODES[1], "1.000000", "0.000000", "0.123457", "0", "", "0", "column", "1", "1", "30", "f00d"]]


# Call 19: the golden forecasts of a fixed history, pinned to the model version. Each row's figures are the fixtures'
# hand-worked shares (their docstrings): Deal the hazard's probes, Express B's, Sheli the blend's.
GOLDEN = {
    "1": [
        "shufersal-deal,2000000000046,0.666667,0.625000,0.714286,0,10,0,column,1,1,30,f00d",
        "shufersal-deal,2000000000053,1.000000,0.625000,0.714286,0,5,0,column,1,1,30,f00d",
        "shufersal-deal,2000000000060,0.500000,0.625000,0.714286,0,,0,column,1,1,30,f00d",
        "shufersal-deal,2000000000077,0.000000,0.625000,0.714286,0,7,0,column,1,1,30,f00d",
        "shufersal-deal,2000000000084,0.625000,0.625000,0.714286,0,3,0,column,1,1,30,f00d",
        "shufersal-express,2000000000114,0.666667,0.666667,0.500000,1,2,0,column,1,1,30,f00d",
        "shufersal-express,2000000000121,0.666667,0.666667,0.750000,0,,0,column,1,1,30,f00d",
        "shufersal-sheli,2000000000015,0.151186,0.200000,0.118644,0,60,20,pair,1,1,30,f00d",
        "shufersal-sheli,2000000000022,0.118644,0.118644,0.118644,0,60,19,column,1,1,30,f00d",
    ],
}


def test_golden_forecasts_are_pinned_to_the_version_name():
    assert MODEL_VERSION in GOLDEN, "a new version needs its golden rows"
    pairs = [*_hazard_pairs(), *_b_pairs(EXPRESS), *_blend_pairs(SHELI)]
    body = forecasts_csv(forecasts(_Read(_records(DEAL, EXPRESS, SHELI), pairs), DAY), "f00d")
    lines = gzip.decompress(body).decode().splitlines()
    assert lines[0] == ",".join(FILE_FIELDS)
    assert lines[1:] == GOLDEN[MODEL_VERSION]


def test_the_models_fixed_values():
    assert (MODEL_VERSION, N0, DAYS_SINCE_CAP, A_MIN_DAYS) == ("1", 30, 60, 20)

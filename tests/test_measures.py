"""The measured facts that outlived P7 and P8 (store first, q33): the runs on promotion over P6's 90-day window, which
the forecast reads (`runs`, `days_since`), the days the verdict reads (`promotion_points`), whole numbers half up, and
the front list's bar's constants (`shopper.measures`; the plan's Task 9; the second pre-flight's S1, S11 and N2).

The pairs and column-days are built by hand, as `tests/test_history.py` builds them for the windows; the windows
themselves are `shopper.history`'s and tested there."""
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from shopper.history import ENOUGH, ColumnDay, Pair, Point
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS, Run, days_since, promotion_points, runs, whole

DAY = date(2026, 11, 20)
DEAL, SHELI = "shufersal-deal", "shufersal-sheli"
CODE = "2000000000046"   # a synthetic GS1 code


def back(days: int) -> date:
    return DAY - timedelta(days=days)


def listed_from(first: int, last: int, price: str) -> dict[date, str]:
    """`price` on each day from `first` to `last` days back, inclusive."""
    return {back(n): price for n in range(first, last + 1)}


def _pair(column: str, listed: dict[date, str], promoted=(), unread=()) -> Pair:
    """A pair listing `listed` (day -> price); on the `promoted` days it is on promotion, on the `unread` days the
    chain's promotions were not read (None), on the others it is not."""
    points = {}
    for day, price in listed.items():
        on = None if day in unread else day in promoted
        points[day] = Point(day=day, listed=Decimal(price), low=Decimal(price), high=Decimal(price), listing=4,
                            wide=True, on_promotion=on, next_start=None, promotions=())
    return Pair(column=column, code=CODE, points=points)


def _days(column: str, days, holes=(), promo_holes=()) -> dict[tuple[str, date], ColumnDay]:
    return {(column, day): ColumnDay(column=column, slug="shufersal", day=day, present=True, hole=day in holes,
                                     promo_hole=day in promo_holes, promotions_error=None, included=4,
                                     with_file=1 if day in holes else 4, counted=4,
                                     promo_files=1 if day in promo_holes else 4)
            for day in days}


def test_whole_is_half_up_and_a_tie_goes_away_from_zero():
    """A share as a whole number (the record page's percents, the chart's heights): half up, a tie away from zero, as
    `Decimal`'s ROUND_HALF_UP."""
    assert [whole(Fraction(n, 8)) for n in (99, 100, 101)] == [12, 13, 13]          # 12.375, 12.5, 12.625
    assert whole(Fraction(336, 10)) == 34 and whole(Fraction(4)) == 4 and whole(Fraction(0)) == 0
    assert whole(Fraction(-100, 8)) == -13 and whole(Fraction(-99, 8)) == -12


def test_the_front_lists_bar_is_twenty_of_the_30_days():
    """The front list's bar (`shopper.verdict.passes_bar`, docs/store-first.md): 20 days with records in the 30 before
    today, P6's line for a 30-day window that is not short."""
    assert (MIN_FRONT_DAYS, RECENT_DAYS) == (20, 30) and MIN_FRONT_DAYS == ENOUGH[RECENT_DAYS]


# The runs on promotion (P8's, which the forecast reads)

def test_a_hole_inside_a_run_does_not_break_it():
    listed = listed_from(1, 12, "10.00")
    del listed[back(6)]                  # a day with a record on which the product is not listed
    promoted = [back(n) for n in (12, 11, 9, 8, 7, 5)]
    # day 10 is a hole, its row says "not on promotion"; day 6 has a record and no row: both inside the run
    pair = _pair(DEAL, listed, promoted=promoted)
    column_days = _days(DEAL, [*listed, back(6)], holes=[back(10)])
    assert runs(pair, column_days, DAY) == [Run(start=back(12), end=back(5))]


def test_a_day_off_promotion_breaks_a_run():
    listed = listed_from(1, 12, "10.00")
    pair = _pair(DEAL, listed, promoted=[back(n) for n in (12, 11, 9, 8)])     # day 10 is on record and off promotion
    assert runs(pair, _days(DEAL, listed), DAY) == [Run(start=back(12), end=back(11)),
                                                    Run(start=back(9), end=back(8))]
    assert runs(_pair(DEAL, listed), _days(DEAL, listed), DAY) == []
    assert runs(_pair(DEAL, {}), {}, DAY) == []


def test_a_day_whose_promotions_were_not_read_neither_extends_nor_breaks_a_run():
    listed = listed_from(1, 12, "10.00")
    promoted = [back(n) for n in (12, 11, 9, 8)]
    unread = [back(10), back(7)]                                  # day 10 inside the run, day 7 at its end
    pair = _pair(DEAL, listed, promoted=promoted, unread=unread)
    column_days = _days(DEAL, listed, promo_holes=unread)
    assert runs(pair, column_days, DAY) == [Run(start=back(12), end=back(8))]


def test_runs_are_over_the_90_day_window_and_the_columns_own_records():
    listed = {**listed_from(91, 92, "10.00"), **listed_from(88, 90, "10.00"), **listed_from(1, 3, "10.00")}
    promoted = [back(n) for n in (92, 91, 90, 89, 2, 1)]
    pair = _pair(DEAL, listed, promoted=promoted)
    column_days = _days(DEAL, listed)
    assert runs(pair, column_days, DAY) == [Run(start=back(90), end=back(89)), Run(start=back(2), end=back(1))]
    assert runs(pair, _days(SHELI, listed), DAY) == []            # another column's records are no records


def test_days_since():
    found = [Run(date(2026, 11, 3), date(2026, 11, 9)), Run(date(2026, 11, 24), date(2026, 11, 30))]
    assert days_since(found, date(2026, 12, 6)) == 6              # from the last run's end, 30 November
    assert days_since(found, date(2026, 12, 1)) == 1
    near = [Run(date(2026, 11, 1), date(2026, 11, 3)), Run(date(2026, 11, 5), date(2026, 11, 6)),
            Run(date(2026, 11, 20), date(2026, 11, 20))]
    assert days_since([], date(2026, 12, 6)) is None
    assert days_since(near, date(2026, 11, 20)) == 0


def test_the_days_whose_promotions_were_read():
    """`promotion_points`: the 90-day window's counted days whose promotions were read, in day order: the days the
    runs and the verdict's tracked days are read from (Task 9's review, runs at the window's ends)."""
    listed = listed_from(1, 6, "10.00")
    pair = _pair(DEAL, listed, unread=[back(4)])
    column_days = _days(DEAL, listed, holes=[back(2)], promo_holes=[back(4)])
    assert [point.day for point in promotion_points(pair, column_days, DAY)] == [back(6), back(5), back(3), back(1)]

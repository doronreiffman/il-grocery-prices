"""The measured facts: the gap (P7), the promotion history (P8) and the front page's test (Q3 (b)), per column
(`shopper.measures`; the plan's Task 9; the second pre-flight's S1, S11 and N2).

The pairs and column-days are built by hand, as `tests/test_history.py` builds them for the windows; the windows
themselves are `shopper.history`'s and tested there."""
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from shopper.deals import Deal
from shopper.history import ColumnDay, Pair, Point, Window, window
from shopper.measures import (MIN_FRONT_DAYS, Change, Gap, Run, days_since, depth, gap, gaps, on_front,
                              promotion_days, runs)

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


def _deal(price: str | Fraction, valid: bool = True) -> Deal:
    return Deal(price=Fraction(price), per="unit", buy=Decimal(1), low=None, high=None, valid=valid,
                why=None if valid else "the rate and the price disagree")


def _gap(deal: str, listed: dict[date, str], column: str = DEAL) -> Gap | None:
    return gap(Fraction(deal), _pair(column, listed), _days(column, listed), DAY)


def _on_front(deal: Deal, listed: dict[date, str], wide: bool = True, holes=(), today: bool = True) -> bool:
    days = [*listed, *([DAY] if today else [])]
    return on_front(deal, wide, _pair(DEAL, listed), _days(DEAL, days, holes=holes), DAY)


# The gap (P7)

def test_the_designs_example():
    """Page day 20 November 2026; 10.90 from 22 August to 27 October, 11.90 from 28 October; a deal of 7.90."""
    listed = {date(2026, 8, 22) + timedelta(days=n): "10.90" for n in range(67)}              # to 27 October
    listed |= {date(2026, 10, 28) + timedelta(days=n): "11.90" for n in range(23)}            # to 19 November
    pair, column_days = _pair(DEAL, listed), _days(DEAL, listed)
    found = gap(Fraction("7.90"), pair, column_days, DAY)
    assert found == Gap(
        deal=Fraction(79, 10), median30=Decimal("11.90"), below=Fraction(4), percent=34, low30=Decimal("10.90"),
        low90=Decimal("10.90"), at_or_below=0, window30=window(pair, column_days, DAY, 30),
        window90=window(pair, column_days, DAY, 90),
        changes=(Change(day=date(2026, 10, 28), before=Decimal("10.90"), after=Decimal("11.90")),))
    assert (found.window30.days, found.window30.since, found.window30.short) == (30, date(2026, 10, 21), False)
    assert (found.window90.days, found.window90.since, found.window90.short) == (90, date(2026, 8, 22), False)


def test_depth():
    """N2: depth is the gap over the 30-day median, never over the deal."""
    example = _gap("7.90", {**listed_from(24, 90, "10.90"), **listed_from(1, 23, "11.90")})
    assert depth(example) == Fraction(40, 119)     # 4.00 / 11.90, not 4.00 / 7.90
    eight = _gap("6.00", listed_from(1, 30, "8.00"))
    assert depth(eight) == Fraction(1, 4)          # 2.00 / 8.00, not 2.00 / 6.00
    dearer = _gap("10.00", listed_from(1, 30, "8.00"))
    assert depth(dearer) == Fraction(-1, 4)        # a deal above the median is not below it


def test_no_gap_without_a_day_of_records_in_30():
    assert _gap("7.90", {}) is None
    assert _gap("7.90", listed_from(31, 60, "10.00")) is None        # records, but none in the past 30 days
    assert _gap("7.90", listed_from(1, 1, "10.00")) is not None
    # another column's days are no records here
    pair = _pair(DEAL, listed_from(1, 5, "10.00"))
    assert gap(Fraction("7.90"), pair, _days(SHELI, pair.points), DAY) is None


def test_the_median_is_the_30_day_windows_own_and_sorted():
    # day order 5, 9, 7: the middle of the sorted prices is 7, the middle in day order is 9
    odd = _gap("1.00", {back(3): "5.00", back(2): "9.00", back(1): "7.00"})
    assert odd.median30 == Decimal("7.00")
    # an even count is the mean of the two middle prices
    even = _gap("1.00", {**listed_from(16, 30, "10.00"), **listed_from(1, 15, "11.00")})
    assert even.median30 == Decimal("10.50")
    # the 90-day median would be 10.00 here: the prices of the past 30 days alone are 20.00 and 30.00
    older = _gap("1.00", {**listed_from(31, 90, "10.00"), **listed_from(1, 30, "20.00")})
    assert older.median30 == Decimal("20.00")


def test_the_percent_is_whole_and_half_up():
    assert _gap("7.00", listed_from(1, 30, "8.00")).percent == 13       # 12.5
    assert _gap("7.01", listed_from(1, 30, "8.00")).percent == 12       # 12.375
    assert _gap("4.00", listed_from(1, 30, "8.00")).percent == 50
    below = _gap("7.90", listed_from(1, 30, "11.90"))
    assert (below.below, below.percent) == (Fraction(4), 34)            # 33.6, not 33
    # a deal above the median: a negative figure, a tie away from zero as Decimal's ROUND_HALF_UP
    above = _gap("9.00", listed_from(1, 30, "8.00"))
    assert (above.below, above.percent) == (Fraction(-1), -13)          # -12.5
    assert _gap("8.00", listed_from(1, 30, "8.00")).percent == 0


def test_the_low_and_the_days_at_or_below_the_deal():
    listed = {**listed_from(61, 90, "7.00"), **listed_from(31, 60, "7.90"), **listed_from(1, 30, "11.90")}
    found = _gap("7.90", listed)
    assert (found.low30, found.low90) == (Decimal("11.90"), Decimal("7.00"))
    assert found.at_or_below == 60      # 30 days at 7.00 and 30 listed at exactly the deal price: at or below


def test_the_days_at_or_below_read_the_exact_deal_price():
    price = Fraction("4.34") / 3        # 1.4466...: its two places, 1.45, are what the shelf lists
    listed = listed_from(1, 30, "1.45")
    assert round(price, 2) == Fraction("1.45")
    assert gap(price, _pair(DEAL, listed), _days(DEAL, listed), DAY).at_or_below == 0
    assert gap(Fraction("1.45"), _pair(DEAL, listed), _days(DEAL, listed), DAY).at_or_below == 30


def test_a_short_window_still_has_its_gap():
    found = _gap("7.90", listed_from(1, 5, "10.00"))
    assert (found.window30.days, found.window30.short, found.window90.short) == (5, True, True)
    assert found.median30 == Decimal("10.00")


def test_the_gap_reads_the_columns_own_days():
    listed = listed_from(1, 30, "10.00")
    pair = _pair(DEAL, listed)
    column_days = {**_days(DEAL, listed, holes=[back(n) for n in range(1, 11)]), **_days(SHELI, listed)}
    found = gap(Fraction("7.90"), pair, column_days, DAY)     # ten of Deal's days are holes, Sheli's records are not Deal's
    assert (found.window30.days, found.window90.days) == (20, 20)


def test_changes_are_the_30_day_windows_own():
    listed = {**listed_from(46, 90, "10.00"), **listed_from(32, 45, "10.50"),    # a change on day 45: before the window
              back(31): "11.00",                                                   # a change on day 31: the day before it
              **listed_from(16, 30, "12.00"),                                      # a change on day 30: the window's first
              **listed_from(1, 15, "9.50")}                                        # a change on day 15
    found = _gap("7.90", listed)
    assert found.changes == (Change(day=back(30), before=Decimal("11.00"), after=Decimal("12.00")),
                             Change(day=back(15), before=Decimal("12.00"), after=Decimal("9.50")))
    assert _gap("7.90", listed_from(1, 90, "10.00")).changes == ()


def test_a_change_across_a_hole_is_dated_the_day_it_is_seen():
    listed = {back(5): "10.90", back(4): "99.00", back(3): "11.90", back(2): "11.90"}
    pair = _pair(DEAL, listed)
    found = gap(Fraction("7.90"), pair, _days(DEAL, listed, holes=[back(4)]), DAY)
    assert found.changes == (Change(day=back(3), before=Decimal("10.90"), after=Decimal("11.90")),)
    # a price spelled with another number of places is the same price
    spelled = {back(2): "10.9", back(1): "10.90"}
    assert gap(Fraction("7.90"), _pair(DEAL, spelled), _days(DEAL, spelled), DAY).changes == ()


# The front page's test (Q3 (b))

def test_the_front_page_needs_twenty_days():
    assert MIN_FRONT_DAYS == 20
    assert not _on_front(_deal("7.90"), listed_from(1, 19, "10.00"))
    assert _on_front(_deal("7.90"), listed_from(1, 20, "10.00"))
    assert _on_front(_deal("7.90"), listed_from(1, 21, "10.00"))
    # the 20 are of the past 90 days, not of the past 30
    assert _on_front(_deal("7.90"), listed_from(40, 59, "10.00"))
    assert not _on_front(_deal("7.90"), listed_from(91, 120, "10.00"))      # beyond the 90 days


def test_a_hole_is_no_day_of_records_for_the_front_page():
    listed = listed_from(1, 20, "10.00")
    assert _on_front(_deal("7.90"), listed)
    assert not _on_front(_deal("7.90"), listed, holes=[back(7)])           # 19 days of records
    assert _on_front(_deal("7.90"), {**listed, back(21): "10.00"}, holes=[back(7)])


def test_a_deal_equal_to_the_90_day_low_is_not_on_the_front_page():
    listed = {**listed_from(1, 40, "9.00"), **listed_from(41, 50, "7.90")}
    assert not _on_front(_deal("7.90"), listed)
    assert _on_front(_deal("7.89"), listed)


def test_the_front_test_reads_the_exact_deal_price():
    """3 for ₪4.34 is 1.4466... a unit; against a 90-day low of ₪1.45 it is below, though two places read 1.45."""
    price = Fraction("4.34") / 3
    assert round(price, 2) == Fraction("1.45")
    listed = {**listed_from(1, 25, "1.45"), **listed_from(26, 40, "1.60")}
    assert _on_front(_deal(price), listed)
    assert not _on_front(_deal("1.45"), listed)


def test_a_price_raised_before_the_promotion_does_not_lift_the_low():
    """7.90 for 60 days, 11.90 for the last 14 (or the last 30): the 90-day low stays 7.90, so a deal of 7.90 is
    no deal below it; the 30-day low, once the raise fills the window, would say it is."""
    raised_14 = {**listed_from(15, 74, "7.90"), **listed_from(1, 14, "11.90")}
    assert not _on_front(_deal("7.90"), raised_14)
    raised_30 = {**listed_from(31, 90, "7.90"), **listed_from(1, 30, "11.90")}
    assert _gap("7.90", raised_30).low30 == Decimal("11.90")
    assert not _on_front(_deal("7.90"), raised_30)
    assert _on_front(_deal("7.80"), raised_30)


def test_an_invalid_or_some_stores_deal_is_not_on_the_front_page():
    listed = listed_from(1, 30, "10.00")
    assert _on_front(_deal("7.90"), listed)
    assert not _on_front(_deal("7.90", valid=False), listed)                  # the deal does not validate (P4)
    assert not _on_front(_deal("7.90"), listed, wide=False)                   # carried by some stores only (P3)
    assert not _on_front(_deal("7.90", valid=False), listed, wide=False)
    no_price = Deal(price=None, per="unit", buy=Decimal(1), low=None, high=None, valid=False, why="no price")
    assert not _on_front(no_price, listed)


def test_a_column_with_no_record_today_has_no_front_row():
    """S1: on a column-day that is no record, the prices are from too few files: no front row."""
    listed = listed_from(1, 30, "10.00")
    assert _on_front(_deal("7.90"), listed)
    assert not _on_front(_deal("7.90"), listed, holes=[DAY], today=True)
    assert not _on_front(_deal("7.90"), listed, today=False)        # no column-day at all for the page's day


def test_the_front_test_reads_the_columns_own_days():
    listed = listed_from(1, 30, "10.00")
    pair = _pair(DEAL, listed)
    assert on_front(_deal("7.90"), True, pair, _days(DEAL, [*listed, DAY]), DAY)
    assert not on_front(_deal("7.90"), True, pair, _days(SHELI, [*listed, DAY]), DAY)


# The promotion history (P8)

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
    # nor is it a day with records for the count: 4 on promotion of the 10 days read
    assert promotion_days(pair, column_days, DAY) == (4, 10)


def test_runs_are_over_the_90_day_window_and_the_columns_own_records():
    listed = {**listed_from(91, 92, "10.00"), **listed_from(88, 90, "10.00"), **listed_from(1, 3, "10.00")}
    promoted = [back(n) for n in (92, 91, 90, 89, 2, 1)]
    pair = _pair(DEAL, listed, promoted=promoted)
    column_days = _days(DEAL, listed)
    assert runs(pair, column_days, DAY) == [Run(start=back(90), end=back(89)), Run(start=back(2), end=back(1))]
    assert promotion_days(pair, column_days, DAY) == (4, 6)       # day 91 and 92 are beyond the 90 days
    assert runs(pair, _days(SHELI, listed), DAY) == []            # another column's records are no records
    assert promotion_days(pair, _days(SHELI, listed), DAY) == (0, 0)


def test_the_days_on_promotion_of_the_days_with_records():
    listed = listed_from(1, 87, "10.00")
    promoted = [back(n) for n in (*range(80, 87), *range(60, 65))]                  # 12 days on promotion
    pair = _pair(DEAL, listed, promoted=promoted)
    assert promotion_days(pair, _days(DEAL, listed), DAY) == (12, 87)
    holes = [back(n) for n in (83, 62, 40)]                                         # two on promotion, one not
    assert promotion_days(pair, _days(DEAL, listed, holes=holes), DAY) == (10, 84)


def test_gaps_and_days_since():
    found = [Run(date(2026, 11, 3), date(2026, 11, 9)), Run(date(2026, 11, 24), date(2026, 11, 30))]
    assert gaps(found) == [14]                                    # 10 to 23 November: strictly between the runs
    assert days_since(found, date(2026, 12, 6)) == 6              # from the last run's end, 30 November
    assert days_since(found, date(2026, 12, 1)) == 1
    near = [Run(date(2026, 11, 1), date(2026, 11, 3)), Run(date(2026, 11, 5), date(2026, 11, 6)),
            Run(date(2026, 11, 20), date(2026, 11, 20))]
    assert gaps(near) == [1, 13]
    assert gaps([Run(date(2026, 11, 3), date(2026, 11, 9))]) == []
    assert gaps([]) == []
    assert days_since([], date(2026, 12, 6)) is None
    assert days_since(near, date(2026, 11, 20)) == 0

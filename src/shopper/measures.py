"""The measured facts of a deal at a column: the gap (P7), the promotion history (P8) and the front page's test
(docs/shopper-site.md P6 to P8 and Q3 (b), with "Changed after the survey", S1; the plan's Task 9, the second
pre-flight's S1 and N2). Every fact is about one pair, a product at one column, and reads that column's own days.

The days. P6's windows (`shopper.history.window`, `counted`): the calendar days ending the day before the page's day,
counting only the days on which the column has a record and the product a listed price. The 30-day window gives the
median and the changes, the 90-day window the lows, the days at or below the deal, the history and the front page's
test. A day that is no record (a hole, or a table never extracted) is skipped, never filled.

The gap (P7). With no day of records in the past 30 there is none (`gap` gives None). Otherwise:

- `median30`: the median of the 30-day window's listed prices (B5's `basket.rules.median`: the middle price, or the
  mean of the two middle ones). It is above ₪0.01, as every listed price in the items table is.
- `below`: `median30` minus the deal, exact, negative when the deal is above the median; `percent` is that over the
  median as a whole percent, half up (a tie goes away from zero, as `Decimal`'s ROUND_HALF_UP does). `depth` is the
  same share, exact: (median30 - deal) / median30, the median being the reference, never the deal (N2).
- `low30` and `low90`: the lowest listed price of each window; `at_or_below`: the days of the 90 on which the item was
  listed at or below the deal. The listed price is the shelf price, before promotions.
- `changes`: each pair of consecutive counted days of the 90-day window whose listed prices differ, with the later of
  the two in the 30-day window; its day is the later one, its `since` the earlier. The earlier may lie before the
  window, so a rise on the window's first day shows. A day skipped between the two (a hole) does not hide a change;
  it is dated the day the new price is seen, and `since` keeps the last day the old one was seen, so the words can
  give both days when the change lies somewhere between them (Task 9's review).

The deal is a `Fraction`, and every comparison reads it exactly (the pre-flight's S6): 3 for ₪4.34 is 1.4466... a
unit, below a listed ₪1.45, though its two places say 1.45.

The front page's test (Q3 (b), the design's rule): the deal is wide in the column (carried by at least half its counted
stores), valid (P4), the item has at least MIN_FRONT_DAYS (20) days of records in the past 90 at the column, and the
deal is below every listed price of those days (strictly: a deal equal to the 90-day low is not). A listed price
raised shortly before the promotion cannot lift the 90-day low. S1 adds that the page's own day must be a record at the
column: on a hole day the prices are from too few files and the column has no front row. The row shows the 30-day
median and is ordered by `depth`, so the item also needs a day of records in the past 30: wherever `on_front` says
yes, `gap` is a gap (Task 9's review). The words "in the same store
format" (question O) are the words module's.

The promotion history (P8), over the 90-day window. A run is a maximal sequence of consecutive counted days on
promotion (`Point.on_promotion`: a promotion carried by at least half the column's counted stores, with a kind, running
that day). A day skipped neither extends nor breaks a run: a hole, a day on which the product is not listed, and a day
whose promotions were not read (`ColumnDay.promo_hole`: the chain's promotions failed or fewer than half the counted
stores had a promotion file) say nothing about promotions, which is not the same as none. Such a day is not one of the
days with records that `promotion_days` counts either. A day on record, listed and off promotion breaks the run.
`promotion_points` gives the days the history reads, and `promoted_today` reads the page's day itself the same way
(None when the history would not count it or its promotions were not read), so the words can tell a run seen to the
window's last day read from one that ended there.
`gaps` counts the calendar days strictly between one run's end and the next one's start; `days_since` the days from the
last run's end to the page's day.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from basket.rules import median
from shopper.deals import Deal
from shopper.history import READ_DAYS, ColumnDay, Pair, Point, Window, counted, window

MIN_FRONT_DAYS = 20     # the front page's test: at least this many days of records in the past 90 (Q3 (b))
RECENT_DAYS = 30        # P7's short window: the median and the changes


@dataclass(frozen=True)
class Change:
    """A change in the listed price: the day it is first seen, the last day the price before it was seen (`since`) and
    the prices before and after."""
    day: date
    since: date
    before: Decimal
    after: Decimal


@dataclass(frozen=True)
class Gap:
    """P7's measured facts (the module's docstring)."""
    deal: Fraction
    median30: Decimal
    below: Fraction             # median30 - deal
    percent: int                # below over the median, whole percent, half up
    low30: Decimal
    low90: Decimal
    at_or_below: int            # days of the 90 listed at or below the deal
    window30: Window
    window90: Window
    changes: tuple[Change, ...]


@dataclass(frozen=True)
class Run:
    """A run on promotion: its first and last day."""
    start: date
    end: date


def _whole(value: Fraction) -> int:
    """`value` as a whole number, half up: a tie goes away from zero."""
    whole = int(abs(value) + Fraction(1, 2))
    return whole if value >= 0 else -whole


def _changes(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[Change, ...]:
    points = counted(pair, column_days, day, READ_DAYS)
    first = day - timedelta(days=RECENT_DAYS)
    return tuple(Change(day=later.day, since=earlier.day, before=earlier.listed, after=later.listed)
                 for earlier, later in zip(points, points[1:])
                 if later.listed != earlier.listed and later.day >= first)


def gap(deal: Fraction, pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> Gap | None:
    """The deal's gap at the pair's column on `day` (the module's docstring); None with no day of records in 30."""
    recent = window(pair, column_days, day, RECENT_DAYS)
    if not recent.days:
        return None
    long = window(pair, column_days, day, READ_DAYS)
    middle = median(sorted(recent.listed))
    below = Fraction(middle) - deal
    return Gap(deal=deal, median30=middle, below=below, percent=_whole(100 * below / Fraction(middle)),
               low30=min(recent.listed), low90=min(long.listed),
               at_or_below=sum(1 for listed in long.listed if Fraction(listed) <= deal),
               window30=recent, window90=long, changes=_changes(pair, column_days, day))


def depth(gap: Gap) -> Fraction:
    """(median30 - deal) / median30, exact (N2)."""
    return gap.below / Fraction(gap.median30)


def on_front(deal: Deal, wide: bool, pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay],
             day: date) -> bool:
    """Whether the deal is listed on the front page (the module's docstring): `wide` is whether the deal's promotion is
    carried by at least half the column's counted stores (P3: the promotions struct's `wide`, not the items row's
    `wide`, which says how many stores list the product)."""
    today = column_days.get((pair.column, day))
    if not (wide and deal.valid and deal.price is not None and today is not None and today.record):
        return False
    if not window(pair, column_days, day, RECENT_DAYS).days:     # no 30-day median to show: `gap` is None
        return False
    long = window(pair, column_days, day, READ_DAYS)
    return long.days >= MIN_FRONT_DAYS and deal.price < Fraction(min(long.listed))


def promotion_points(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> list[Point]:
    """The 90-day window's counted points on whose day the column's promotions were read."""
    return [point for point in counted(pair, column_days, day, READ_DAYS)
            if not column_days[(pair.column, point.day)].promo_hole]


def runs(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> list[Run]:
    """The runs on promotion over P6's 90-day window, in day order (the module's docstring)."""
    found: list[Run] = []
    start = end = None
    for point in promotion_points(pair, column_days, day):
        if not point.on_promotion:
            if start is not None:
                found.append(Run(start, end))
                start = None
            continue
        if start is None:
            start = point.day
        end = point.day
    if start is not None:
        found.append(Run(start, end))
    return found


def gaps(runs: Sequence[Run]) -> list[int]:
    """The days strictly between each run's end and the next run's start."""
    return [(later.start - earlier.end).days - 1 for earlier, later in zip(runs, runs[1:])]


def days_since(runs: Sequence[Run], day: date) -> int | None:
    """The days from the last run's end to `day`; None with no run."""
    return (day - runs[-1].end).days if runs else None


def promotion_days(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[int, int]:
    """(the days on a wide promotion, the days with records whose promotions were read), over the 90-day window."""
    points = promotion_points(pair, column_days, day)
    return sum(1 for point in points if point.on_promotion), len(points)


def promoted_today(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> bool | None:
    """Whether the pair is on a wide promotion on `day` itself, read as `promotion_points` reads a day of the window;
    None when that rule would not read it (no record at the column, no listed price, its promotions not read)."""
    seen = promotion_points(pair, column_days, day + timedelta(days=1))
    return seen[-1].on_promotion if seen and seen[-1].day == day else None

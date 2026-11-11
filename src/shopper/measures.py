"""The measured facts that outlived P7 and P8 (store first, q33): the runs on promotion over P6's 90-day window, which
the forecast reads (`runs`, `days_since`), the days the verdict reads (`promotion_points`), a share as a whole number
half up (`whole`), and the front list's bar (docs/shopper-site.md P6 and P8; the plan's Task 9, the second
pre-flight's S1 and N2; docs/store-first.md, "The front page's list"). Every fact is about one pair, a product at one
column, and reads that column's own days. P7's gap, its lows and changes, the old front page's test and P8's counts
and gaps went with their page parts (the store-first plan's Task 6).

The days. P6's windows (`shopper.history.window`, `counted`): the calendar days ending the day before the page's day,
counting only the days on which the column has a record and the product a listed price. A day that is no record (a
hole, or a table never extracted) is skipped, never filled.

The runs (P8's, read by the forecast), over the 90-day window. A run is a maximal sequence of consecutive counted days
on promotion (`Point.on_promotion`: a promotion carried by at least half the column's counted stores, with a kind,
running that day). A day skipped neither extends nor breaks a run: a hole, a day on which the product is not listed,
and a day whose promotions were not read (`ColumnDay.promo_hole`: the chain's promotions failed or fewer than half the
counted stores had a promotion file) say nothing about promotions, which is not the same as none. A day on record,
listed and off promotion breaks the run. `promotion_points` gives the days the runs read, and the verdict's tracked
days (`shopper.verdict.tracked`); `days_since` the days from the last run's end to the page's day.

The front list's bar (`shopper.verdict.passes_bar`): at least MIN_FRONT_DAYS (20) days of records in the RECENT_DAYS
(30) before the day, P6's line for a 30-day window that is not short.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from shopper.history import READ_DAYS, ColumnDay, Pair, Point, counted

MIN_FRONT_DAYS = 20     # the front list's bar: at least this many days of records in the past 30 (Q3 (b), deploy prep)
RECENT_DAYS = 30        # the bar's window


@dataclass(frozen=True)
class Run:
    """A run on promotion: its first and last day."""
    start: date
    end: date


def whole(value: Fraction) -> int:
    """`value` as a whole number, half up: a tie goes away from zero."""
    whole = int(abs(value) + Fraction(1, 2))
    return whole if value >= 0 else -whole


def promotion_points(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date,
                     length: int = READ_DAYS) -> list[Point]:
    """The window's counted points (the 90-day window's, or `length` days') on whose day the column's promotions were
    read."""
    return [point for point in counted(pair, column_days, day, length)
            if not column_days[(pair.column, point.day)].promo_hole]


def runs(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> list[Run]:
    """The runs on promotion over P6's 90-day window, in day order (the module's docstring)."""
    return runs_of(promotion_points(pair, column_days, day))


def runs_of(points: Sequence[Point]) -> list[Run]:
    """The runs over `promotion_points`' points, in day order (the module's docstring)."""
    found: list[Run] = []
    start = end = None
    for point in points:
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


def days_since(runs: Sequence[Run], day: date) -> int | None:
    """The days from the last run's end to `day`; None with no run."""
    return (day - runs[-1].end).days if runs else None

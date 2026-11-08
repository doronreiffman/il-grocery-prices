"""The forecast's target, who gets a forecast, and the closed days the model learns from (docs/shopper-site.md F1, F2
and F3, with its "Changed after the survey", S1 and "The column", and Call 22; the plan's Task 10, question F and the
second pre-flight's B1 and S1). The model, its two baselines and the forecasts file join this module in Task 11.

The target, version 1 (F1). For a product at a column on day d: 1 if a promotion carried by at least half the column's
counted stores, with a link of kind 1, 2, 3 or 10 on the item (S2: `on_promotion`), is listed in the morning full files
of at least one of days d + 1 to d + 14; club-only and "price not read" in; coupons, `RewardType` 6 and 12 promotions
and `RewardType` 0 links out (Tasks 3, 5, 6). A column-day with a promotion hole (the column's counted stores with a
promotion file fewer than half, or the chain's promotions unread) or whose chain's items table is missing is a hole for
that column only. So is a price hole (B1): a column-day with no record, whose price files come from fewer than half
the column's included stores, `basket.rules.chain_day(...).in_ranking` false, as `shopper.history.ColumnDay.record`
reads it. A day the history does not hold is a hole too. Every hole is one column's: another column's hole, in the same
chain, is no hole here.

Reading the window. The window is the 14 days after d, never d itself. Each day of it is a hole (counted) or is read: it
is on a wide promotion when its row for the item says `on_promotion`. A hole day is not read, as `shopper.history`'s
windows and registry skip it: a hole makes no claim (S1), so a wide promotion seen on a morning with too few files
neither makes the outcome 1 nor is its evidence. With more than MAX_HOLES (4) holes in the window the outcome has no
value (F7: unscored and counted, a rule fixed in advance, the same for the model and both baselines); with fewer it is
1 when any day read is on a wide promotion, else 0. Its evidence (F7) is the first day read on one and the smallest
`PromotionID`, by number (`shopper.items.by_number`), of the promotions on the item that day that are wide, have a kind
and run that day; None when the row's structs show none (the struct shows one link of a promotion, and its `wide` can
differ from `on_promotion`, which reads every link). `first_day` and `promotion_id` are None without a value.

Who gets a forecast (F2, Call 22). `eligible` answers for the day itself: "hole" when the column-day is a hole of any
kind (S1: no forecast on a morning with too few files, or whose promotions could not be read: whether the item is on
promotion today is not known), else "not_wide" when the column does not list the item widely that day (`Point.wide`; an
item not listed at all is not listed widely), else "on_promotion" when it is on a wide promotion today (it has no
"wait" question), else "starts_soon" when a wide promotion is listed to start within d + 1 to d + 14 (`next_start`; the
page says "listed to start on <date>", it is counted, not scored), else "yes". Only "yes" gets a forecast.

Inputs pinned to the day (F3). A forecast for day d reads only tables of days up to d, and learns only from the days t
whose windows have closed by then, t at most d - 14 (their outcomes are in d's tables), and within the 90 days read
(`shopper.history.READ_DAYS`): `closed_days` is those t at the pair's column that are eligible ("yes") and whose
window holds at most 4 holes (question F (b) and (c): a window the scoring rule would leave unscored is left out of the
history too), each with its outcome, by day. Nothing after d is read: `eligible` reads the day itself, `outcome` days
t + 1 to t + 14 and no more. A test builds the same answers with and without points after d.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from shopper.history import READ_DAYS, ColumnDay, Pair, Point
from shopper.items import HORIZON, by_number

MAX_HOLES = 4           # more holes than this in a window leave the outcome without a value (F7)
FIRST_RECORD_DAY = 30   # a column's forecasts start on its 30th day of records (Task 11)
TARGET_VERSION = "1"    # every forecasts file names it; a new definition is a new version (F1, Call 13)


@dataclass(frozen=True)
class Outcome:
    """F1 over the 14 days after a day: 1 or 0, None with more than MAX_HOLES holes; the holes counted; and, for a 1,
    the first day read on a wide promotion and the smallest `PromotionID` among the wide promotions on the item that
    day (None when the structs show none)."""
    value: int | None
    holes: int
    first_day: date | None
    promotion_id: str | None


def _hole(column_days: Mapping[tuple[str, date], ColumnDay], column: str, day: date) -> bool:
    """The column's day is a hole: no column-day held, its chain's table missing, a price hole or a promotion hole."""
    found = column_days.get((column, day))
    return found is None or not found.record or found.promo_hole


def _running(point: Point) -> list[str]:
    """The ids of the promotions on the item that are wide, have a kind and run on the point's day."""
    return [found["promotion_id"] for found in point.promotions
            if found["wide"] and found["kind"] is not None and found["start"] <= point.day <= found["end"]]


def outcome(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> Outcome:
    """F1 for the pair on `day`, over days day + 1 to day + HORIZON at the pair's column (the module's docstring)."""
    holes, first = 0, None
    for ahead in range(1, HORIZON + 1):
        seen = day + timedelta(days=ahead)
        if _hole(column_days, pair.column, seen):
            holes += 1
            continue
        point = pair.points.get(seen)
        if first is None and point is not None and point.on_promotion:
            first = point
    if holes > MAX_HOLES:
        return Outcome(value=None, holes=holes, first_day=None, promotion_id=None)
    if first is None:
        return Outcome(value=0, holes=holes, first_day=None, promotion_id=None)
    wide = _running(first)
    return Outcome(value=1, holes=holes, first_day=first.day, promotion_id=min(wide, key=by_number, default=None))


def eligible(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> str:
    """Who gets a forecast on `day`: "hole", "not_wide", "on_promotion", "starts_soon" or "yes" (the module's
    docstring)."""
    if _hole(column_days, pair.column, day):
        return "hole"
    point = pair.points.get(day)
    if point is None or not point.wide:
        return "not_wide"
    if point.on_promotion:
        return "on_promotion"
    if point.next_start is not None:
        return "starts_soon"
    return "yes"


def closed_days(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay],
                day: date) -> list[tuple[date, Outcome]]:
    """The days t from day - READ_DAYS to day - HORIZON on which the pair is eligible and whose windows hold at most
    MAX_HOLES holes, each with its outcome, earliest first."""
    found = []
    for back in range(READ_DAYS, HORIZON - 1, -1):
        seen = day - timedelta(days=back)
        if eligible(pair, column_days, seen) != "yes":
            continue
        result = outcome(pair, column_days, seen)
        if result.value is not None:
            found.append((seen, result))
    return found

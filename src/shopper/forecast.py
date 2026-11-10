"""The forecast's target, who gets a forecast, the closed days the model learns from, the version 1 model, its two
baselines and the forecasts file (docs/shopper-site.md F1 to F5, with its "Changed after the survey", S1, "The column"
and "Where the key lives", and Calls 19 and 22; the plan's Tasks 10 and 11, question F and the second pre-flight's B1
and S1).

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

The model, version 1 (F4, question F). Everything is learnt per column (S1: the design's "for each chain" and "the
chain's share" are the column's), from the closed days of every pair at the column. A column's share is the share of
outcome 1 over all its closed days. A pair's feature on a day is the days since its last run on promotion ended: P8's
runs and days since (`shopper.measures.runs` and `days_since`: calendar days from the last run's end), within the 90
days read and before the day; above DAYS_SINCE_CAP (60) it counts as 60 ("60 or more"), and with no run seen it is
none. The hazard of a bucket (0 to 60, or none) is the column's share over its closed days in that bucket; a bucket
with no closed day takes the column's share. Baseline A (F5) is the pair's share over its n closed days, or the
column's share when n is under A_MIN_DAYS (20) (`a_from` says which). The model's probability is
p = w × A + (1 − w) × the hazard of the pair's bucket on day d, with w = n ÷ (n + N0) and N0 = 30, fixed before version
1's first frozen day.

Baseline B, "the last gap repeats" (F5, question F (e)). With two or more runs before the day, the next run is taken to
start at the last run's end plus the days from the end of the run before it to the start of the last run; B says yes
when that date falls in d + 1 to d + 14, and no otherwise (no with fewer than two runs). Its probability is the
column's share over its closed days on which B gave the same answer, each closed day's answer read from the runs
before that day; when B gave that answer on none of them, it is the column's share (question F (d)).

The runs of a closed day. A pair's runs are read once, for day d (the read's days d − 90 to d − 1); a closed day t
then has the runs among them that ended before t. They are the runs `runs` would find for t within the read: an
eligible day is one the run rule counts (a record, the promotions read, the item listed) and is off promotion, so it
ends any run before it and no run spans it. Each pair's closed days are computed once and shared by the model and both
baselines.

Who gets a forecast. A column's forecasts start on its 30th day of records (`History.record_days`, at least
FIRST_RECORD_DAY); a column with no closed day at all has nothing to learn from and gets none that day, rather than a
share of 0 out of 0. Only a pair that `eligible` answers "yes" for on day d gets one. `forecasts` lists them by column,
then barcode.

The forecasts file (F6's rows; "Where the key lives": one file a day, rows keyed by column and barcode). Sorted by
column, then barcode; its fields FILE_FIELDS: the column's key ("shufersal-deal"), the barcode, the model's
probability, A and B, B's answer (1 or 0), the days since as the model used them (60 for "60 or more", empty for
none), n, where A came from ("pair" or "column"), and on every row the model's and the target's versions, N0 and the
code fingerprint the caller gives. Probabilities are written to PLACES (6) decimals, half up, from their exact
fractions. The CSV is gzipped with no time in its header, so the same rows give the same bytes.
"""
import csv
import gzip
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction

from shopper.history import READ_DAYS, ColumnDay, History, Pair, Point
from shopper.items import HORIZON, by_number
from shopper.measures import Run, days_since, runs

MAX_HOLES = 4           # more holes than this in a window leave the outcome without a value (F7)
FIRST_RECORD_DAY = 30   # a column's forecasts start on its 30th day of records (Task 11)
TARGET_VERSION = "1"    # every forecasts file names it; a new definition is a new version (F1, Call 13)
MODEL_VERSION = "1"     # the model of F4 and F5 as below; any change to them is a new version (F9, Call 19)
N0 = 30                 # the blend's constant: the pair's own share weighs n / (n + N0) (F4)
DAYS_SINCE_CAP = 60     # days since the last run ended, counted as this above it ("60 or more", question F (a))
A_MIN_DAYS = 20         # baseline A is the pair's share from this many closed days, else the column's (F5)
PLACES = 6              # the forecasts file's decimals for a probability, half up
AHEAD = range(1, HORIZON + 1)   # the window's days after a day t: t + 1 to t + HORIZON, never t itself (F1)
FILE_FIELDS = ("column", "barcode", "p_model", "p_a", "p_b", "b_says", "days_since", "n", "a_from",
               "model_version", "target_version", "n0", "code_sha")   # named apart from shopper.columns.COLUMNS


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


def _read(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[bool, Point | None]:
    """A day as the target reads it at the pair's column: whether it is a hole, and the pair's point (None if none)."""
    return _hole(column_days, pair.column, day), pair.points.get(day)


def _judged(window: Sequence[tuple[bool, Point | None]]) -> Outcome:
    """F1 over a window's days in day order, each as `_read` gives it (the module's docstring)."""
    holes, first = 0, None
    for hole, point in window:
        if hole:
            holes += 1
            continue
        if first is None and point is not None and point.on_promotion:
            first = point
    if holes > MAX_HOLES:
        return Outcome(value=None, holes=holes, first_day=None, promotion_id=None)
    if first is None:
        return Outcome(value=0, holes=holes, first_day=None, promotion_id=None)
    wide = _running(first)
    return Outcome(value=1, holes=holes, first_day=first.day, promotion_id=min(wide, key=by_number, default=None))


def outcome(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> Outcome:
    """F1 for the pair on `day`, over days day + 1 to day + HORIZON at the pair's column (the module's docstring)."""
    return _judged([_read(pair, column_days, day + timedelta(days=ahead)) for ahead in AHEAD])


def _answer(hole: bool, point: Point | None) -> str:
    """Who gets a forecast on a day, read as `_read` gives it (the module's docstring)."""
    if hole:
        return "hole"
    if point is None or not point.wide:
        return "not_wide"
    if point.on_promotion:
        return "on_promotion"
    if point.next_start is not None:
        return "starts_soon"
    return "yes"


def eligible(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> str:
    """Who gets a forecast on `day`: "hole", "not_wide", "on_promotion", "starts_soon" or "yes" (the module's
    docstring)."""
    return _answer(*_read(pair, column_days, day))


def closed_days(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay],
                day: date) -> list[tuple[date, Outcome]]:
    """The days t from day - READ_DAYS to day - HORIZON on which the pair is eligible and whose windows hold at most
    MAX_HOLES holes, each with its outcome, earliest first. Each day of day - READ_DAYS to day is read once and every
    t's answer and window taken from those readings, not looked up again for each t (the plan's Task 25a)."""
    start = day - timedelta(days=READ_DAYS)
    read = [_read(pair, column_days, start + timedelta(days=n)) for n in range(READ_DAYS + 1)]
    found = []
    for back in range(READ_DAYS, HORIZON - 1, -1):
        seen = day - timedelta(days=back)
        at = READ_DAYS - back                                       # seen's reading in `read`
        if _answer(*read[at]) != "yes":
            continue
        result = _judged(read[at + AHEAD.start:at + AHEAD.stop])
        if result.value is not None:
            found.append((seen, result))
    return found


@dataclass(frozen=True)
class Forecast:
    """A pair's forecast for the day (F4, F5): the model's probability `p`, baseline A's `a` (the pair's share or the
    column's: `a_from`), baseline B's answer `b_says` and probability `b`, and the features: the days since the last
    run ended as the model used them (at most DAYS_SINCE_CAP, None with no run) and `n`, the pair's closed days."""
    column: str
    code: str
    p: Fraction
    a: Fraction
    b: Fraction
    b_says: bool
    days_since: int | None
    n: int
    a_from: str


class _Tally:
    """Closed days and how many of them have outcome 1."""
    __slots__ = ("days", "ones")

    def __init__(self) -> None:
        self.days = 0
        self.ones = 0

    def add(self, value: int) -> None:
        self.days += 1
        self.ones += value

    def share(self) -> Fraction:
        return Fraction(self.ones, self.days)


def _since(found: Sequence[Run], day: date) -> int | None:
    """The days since the last of `found` ended, as the model uses them: above DAYS_SINCE_CAP counted as it."""
    since = days_since(found, day)
    return None if since is None else min(since, DAYS_SINCE_CAP)


def _b_says(found: Sequence[Run], day: date) -> bool:
    """Baseline B on `day`, from the runs before it (the module's docstring)."""
    if len(found) < 2:
        return False
    previous, last = found[-2], found[-1]
    start = last.end + (last.start - previous.end)
    return day + timedelta(days=1) <= start <= day + timedelta(days=HORIZON)


def _key(row: Forecast) -> tuple[str, str]:
    return row.column, row.code


def forecasts(history: History, day: date) -> list[Forecast]:
    """The day's forecasts (the module's docstring): one per pair eligible on `day` at a column on or past its 30th
    day of records with a closed day to learn from, by column, then barcode."""
    column_days = history.column_days
    started = {column for column, _ in column_days if history.record_days(column) >= FIRST_RECORD_DAY}
    shares: dict[str, _Tally] = {}
    hazard: dict[tuple[str, int | None], _Tally] = {}
    rule_b: dict[tuple[str, bool], _Tally] = {}
    waiting = []
    for pair in history.pairs():
        if pair.column not in started:
            continue
        pool = pair.column   # the hazard learns from the column's own pairs (S1), not the chain's or every column's
        found = runs(pair, column_days, day)
        share = shares.setdefault(pair.column, _Tally())
        closed = closed_days(pair, column_days, day)
        for seen, result in closed:
            before = [run for run in found if run.end < seen]
            hazard.setdefault((pool, _since(before, seen)), _Tally()).add(result.value)
            rule_b.setdefault((pair.column, _b_says(before, seen)), _Tally()).add(result.value)
            share.add(result.value)
        if eligible(pair, column_days, day) == "yes":
            own = [result.value for _, result in closed]   # A's days: the pair's closed days
            waiting.append((pair.column, pair.code, pool, len(own), sum(own), _since(found, day),
                            _b_says(found, day)))
    rows = []
    for column, code, pool, n, ones, since, says in waiting:
        if not shares[column].days:
            continue   # no closed day at the column: nothing to learn from
        share = shares[column].share()
        if n >= A_MIN_DAYS:
            a, a_from = Fraction(ones, n), "pair"
        else:
            a, a_from = share, "column"
        bucket = hazard.get((pool, since))
        rate = share if bucket is None else bucket.share()
        weight = Fraction(n, n + N0)
        answered = rule_b.get((column, says))
        b = share if answered is None else answered.share()
        rows.append(Forecast(column=column, code=code, p=weight * a + (1 - weight) * rate, a=a, b=b, b_says=says,
                             days_since=since, n=n, a_from=a_from))
    return sorted(rows, key=_key)


def _places(value: Fraction) -> str:
    """`value`, from 0 to 1, to PLACES decimals, half up, exact."""
    scaled = math.floor(value * 10 ** PLACES + Fraction(1, 2))
    whole, part = divmod(scaled, 10 ** PLACES)
    return f"{whole}.{part:0{PLACES}d}"


def forecasts_csv(rows: Sequence[Forecast], code_sha: str) -> bytes:
    """The day's forecasts file (the module's docstring), gzipped with no time in its header."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(FILE_FIELDS)
    for row in sorted(rows, key=_key):
        writer.writerow((row.column, row.code, _places(row.p), _places(row.a), _places(row.b), int(row.b_says),
                         "" if row.days_since is None else row.days_since, row.n, row.a_from,
                         MODEL_VERSION, TARGET_VERSION, N0, code_sha))
    return gzip.compress(out.getvalue().encode(), mtime=0)

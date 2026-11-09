"""The record's numbers: the Brier scores, their intervals, the calibration, the gate's conditions and the scorecard
(docs/shopper-site.md F7's Brier score, F8, F9 and F11, with its "Changed after the survey", S1 and "Words", and Calls
16, 19 and 20; the plan's Task 14). Everything here reads the scored days' summaries (Task 13's `DaySummary`), never
the files, so anyone holding the published scores files and this code gets the same numbers.

Which days count. A column's record counts the days frozen on time (Call 16: frozen before its midnight by S3's time,
or not counted): a late day is shown as late, and its scores count for nothing. A day counts at a column when its
summary holds a scored row there; a column-day whose rows were all unscored (more than 4 holes) has no score of its
own, rather than 0 out of 0. Each version's days are its own (F9, Call 19): a version is the model's and the target's
versions together, every version has its own rows, and the version in force is the code's
(`shopper.forecast.MODEL_VERSION` and `TARGET_VERSION`), so a new version starts its count from zero.

The Brier score (F7). The mean over a day's scored rows, then the mean of those daily means over the days: a day of many
rows weighs no more than a day of few. Every column pooled takes a day's rows over all its columns, then the mean over
days. The skill against a baseline is 1 - (the model's Brier score / the baseline's); there is none when the baseline's
is 0.

Intervals (F8, Call 20). A moving-block bootstrap over the scored days in date order: blocks of BLOCK (14) consecutive
scored days, since consecutive days' windows share up to 13 of their 14 outcome days. Each draw takes as many blocks as
cover the days, each block's start floor(random() x the number of starts) from one `random.Random(SEED)` per call,
joins them and cuts the result to the number of days; DRAWS (10,000) draws. Each draw gives the model's Brier score
less A's and less B's (the mean of the daily differences) and the two skills; the LEVEL (95%) interval of each runs
from the 2.5th to the 97.5th percentile of its draws, linear between the two neighbouring draws. Under MIN_DAYS (28, two
blocks) scored days there is no interval ("too few days"); a skill whose baseline's Brier score is 0 in some draw has
no interval. Floats are used here only, for speed; the seed, the block and the draws are fixed in the code and printed
on the record page, so the intervals are the same on every run.

Calibration (F8). The scored rows bucketed by the model's probability into ten bins of width 0.1 (Task 13's bins:
[0, 0.1), ..., [0.9, 1]), summed over the days: per bin the count, the mean forecast and the share of outcome 1. The
calibration error is the count-weighted mean absolute gap between the two: the sum over the bins of the count times
the gap, over the rows.

The gate (F9, Q6), per column, over the days of the version in force frozen on time, at that column only. (1) "days": at
least GATE_DAYS (90) scored days. (2) "brier": the model's Brier score below both baselines' and the 95% interval of
each difference wholly below zero (an upper end of 0 touches zero and fails). (3) "calibration": the calibration error
at most CAL_MAX (0.03), and no bin holding BIN_SHARE (1%) or more of the scored rows whose mean and share are apart by
more than BIN_OFF (0.10). Every condition is evaluated and shown, with a reason for each part that fails. In step one
the gate never opens, whatever its conditions (`open` is False): opening on the owner's go, and closing when the latest
60 scored days lose to a baseline, are step three's. Every comparison is on the exact fractions, but for an
interval's end against zero (a float of the bootstrap).

The numbers' form. Brier scores, skills, shares and calibration are exact fractions inside, given as `Decimal`s of
PLACES (12) decimals, half away from zero (each scored square has 12). The scorecard writes them as that decimal text
and the intervals' ends as floats, so it holds only what JSON holds and reads back equal: the site-day file carries it,
and the guard renders the record page's tables again from it (Tasks 19 and 21).

The scorecard (F11). How many columns are tested at once (nine: the design's "Words", since F9's 95% over nine columns
makes one lucky opening likelier than over five) and how many versions were tried; the bootstrap's block, draws, seed,
level and least days; the version in force. Per column, a row per version, in the order each was first frozen, with
its months and its whole: the days on time, late and scored; of the days on time the rows, the scored, the unscored
and the outcomes 1, the outcome-1 share, the three Brier scores, the two skills, the intervals and the calibration's
ten rows and error. And each column's gate. Days with no file at all are the ledger's to count. Every column pooled
(`brier` and the others with no column) is not on the scorecard: the design defines no pooled record.
"""
import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction

from shopper.columns import COLUMNS
from shopper.forecast import MODEL_VERSION, TARGET_VERSION
from shopper.score import BINS, ColumnSummary, DaySummary

BLOCK = 14                   # consecutive scored days a bootstrap block holds (F8)
DRAWS = 10_000               # the bootstrap's draws (F8)
SEED = 20261107              # the bootstrap's seed, fixed in the code and printed on the record page (Call 20)
LEVEL = 95                   # the intervals' level, in percent (F9)
MIN_DAYS = 2 * BLOCK         # the fewest scored days with an interval: two blocks ("too few days" under it)
GATE_DAYS = 90               # scored days of the version in force, frozen on time, the gate needs (F9)
CAL_MAX = Decimal("0.03")    # the highest calibration error the gate passes (F9)
BIN_SHARE = Decimal("0.01")  # a bin holding this share of the scored rows or more is checked (F9)
BIN_OFF = Decimal("0.10")    # how far a checked bin's mean forecast and share of 1 may be apart (F9)
PLACES = 12                  # the decimals of the record's numbers
SHOWN = 4                    # the decimals of a figure in a gate's reason
IN_FORCE = (MODEL_VERSION, TARGET_VERSION)
STATS = ("model_minus_a", "model_minus_b", "skill_a", "skill_b")


@dataclass(frozen=True)
class Interval:
    """A bootstrap interval's two ends."""
    low: float
    high: float


@dataclass(frozen=True)
class Gate:
    """A column's gate: F9's three conditions ("days", "brier", "calibration") and whether each holds, a reason for
    each part that fails (or that every condition holds), and whether it is open: never, in step one."""
    column: str
    conditions: dict[str, bool]
    reasons: list[str]
    open: bool


@dataclass(frozen=True)
class _Day:
    """A scored day at a column: its scored rows and the day's exact Brier scores for the model, A and B."""
    day: date
    scored: int
    model: Fraction
    a: Fraction
    b: Fraction


def _decimal(value: Fraction, places: int = PLACES) -> Decimal:
    """`value` to `places` decimals, half away from zero, exact."""
    scaled = math.floor(abs(value) * 10 ** places + Fraction(1, 2))
    return Decimal(-scaled if value < 0 else scaled).scaleb(-places)


def _text(value: Fraction | None) -> str | None:
    """A record's number as the scorecard writes it: PLACES decimals as text, or None."""
    return None if value is None else format(_decimal(value), "f")


def _shown(value: Fraction, places: int = SHOWN) -> str:
    return format(_decimal(value, places), "f")


def _of(summary: DaySummary, column: str | None) -> ColumnSummary | None:
    """The day's summary at the column or, for None, every column's summed; None when the day holds none."""
    if column is not None:
        return summary.by_column.get(column)
    parts = list(summary.by_column.values())
    if not parts:
        return None
    return ColumnSummary(forecasts=sum(part.forecasts for part in parts), scored=sum(part.scored for part in parts),
                         unscored=sum(part.unscored for part in parts),
                         outcome_1=sum(part.outcome_1 for part in parts),
                         sq_model=sum((part.sq_model for part in parts), Decimal(0)),
                         sq_a=sum((part.sq_a for part in parts), Decimal(0)),
                         sq_b=sum((part.sq_b for part in parts), Decimal(0)),
                         bins=tuple((sum(part.bins[i][0] for part in parts),
                                     sum((part.bins[i][1] for part in parts), Decimal(0)),
                                     sum(part.bins[i][2] for part in parts)) for i in range(BINS)))


def _of_version(summaries: Iterable[DaySummary], version: tuple[str, str]) -> list[DaySummary]:
    """The days of a version: its model's and its target's versions both."""
    return [found for found in summaries if (found.model_version, found.target_version) == version]


def _counted(summaries: Iterable[DaySummary], version: tuple[str, str]) -> list[DaySummary]:
    """The days that count for a version's record: of that version and frozen on time (Call 16)."""
    return [found for found in _of_version(summaries, version) if found.on_time]


def _daily(summaries: Iterable[DaySummary], column: str | None) -> list[_Day]:
    """The days with a scored row at the column, in date order, each with its exact Brier scores."""
    days = []
    for summary in sorted(summaries, key=lambda found: found.day):
        found = _of(summary, column)
        if found is not None and found.scored:
            days.append(_Day(summary.day, found.scored, Fraction(found.sq_model) / found.scored,
                             Fraction(found.sq_a) / found.scored, Fraction(found.sq_b) / found.scored))
    return days


def _brier(days: Sequence[_Day]) -> tuple[Fraction, Fraction, Fraction] | None:
    """The mean of the daily Brier scores over the days, for the model, A and B; None without a day."""
    if not days:
        return None
    return (sum(day.model for day in days) / len(days), sum(day.a for day in days) / len(days),
            sum(day.b for day in days) / len(days))


def _skill(model: Fraction, baseline: Fraction) -> Fraction | None:
    """1 - model / baseline; None when the baseline's Brier score is 0."""
    return None if baseline == 0 else 1 - model / baseline


def brier(summaries: Sequence[DaySummary], column: str | None = None) -> tuple[Decimal, Decimal, Decimal] | None:
    """The model's, A's and B's Brier scores over the days given (the mean of the daily means), at the column or every
    column pooled; None without a scored day. The days are taken as given: the gate and the scorecard choose them."""
    found = _brier(_daily(summaries, column))
    return None if found is None else (_decimal(found[0]), _decimal(found[1]), _decimal(found[2]))


def _percentile(ordered: Sequence[float], q: Fraction) -> float:
    """The q-quantile of sorted draws, linear between the two neighbouring draws."""
    position = q * (len(ordered) - 1)
    below = math.floor(position)
    return ordered[below] + (ordered[below + 1] - ordered[below]) * float(position - below)


def _bootstrap(days: Sequence[_Day]) -> dict[str, Interval | None]:
    """The moving-block bootstrap's intervals over the days (the module's docstring)."""
    n = len(days)
    series = ([float(day.model) for day in days], [float(day.a) for day in days], [float(day.b) for day in days],
              [float(day.model - day.a) for day in days], [float(day.model - day.b) for day in days])
    starts = n - BLOCK + 1
    blocks = -(-n // BLOCK)                 # as many blocks as cover the days
    cut = n - (blocks - 1) * BLOCK          # the last block's days kept: each draw cut to the number of days
    tables = [([sum(values[s:s + BLOCK]) for s in range(starts)], [sum(values[s:s + cut]) for s in range(starts)])
              for values in series]
    rng = random.Random(SEED)
    draws: dict[str, list[float]] = {name: [] for name in STATS}
    undefined = set()
    for _ in range(DRAWS):
        picked = [math.floor(rng.random() * starts) for _ in range(blocks)]
        head, tail = picked[:-1], picked[-1]
        m, a, b, minus_a, minus_b = (sum(map(whole.__getitem__, head)) + last[tail] for whole, last in tables)
        draws["model_minus_a"].append(minus_a / n)
        draws["model_minus_b"].append(minus_b / n)
        for name, baseline in (("skill_a", a), ("skill_b", b)):
            if baseline == 0:   # a draw whose baseline scored 0 has no skill, so the skill has no interval
                undefined.add(name)
            else:
                draws[name].append(1 - m / baseline)
    low, high = Fraction(100 - LEVEL, 200), Fraction(100 + LEVEL, 200)
    spans: dict[str, Interval | None] = {}
    for name in STATS:
        ordered = sorted(draws[name])
        spans[name] = None if name in undefined else Interval(_percentile(ordered, low), _percentile(ordered, high))
    return spans


def _spans(days: Sequence[_Day]) -> dict[str, Interval | None] | None:
    """The intervals over the days, or None under MIN_DAYS of them."""
    return None if len(days) < MIN_DAYS else _bootstrap(days)


def intervals(summaries: Sequence[DaySummary], column: str | None = None) -> dict[str, Interval | None] | None:
    """The 95% intervals of the model's Brier score less A's and less B's and of the two skills, over the days given
    with a scored row at the column (or at any column, pooled); None under 28 such days. A skill's interval is None
    when its baseline's Brier score is 0 in some draw."""
    return _spans(_daily(summaries, column))


def _bins(summaries: Iterable[DaySummary], column: str | None) -> list[tuple[int, Fraction, int]]:
    """The ten bins' counts, sums of p and outcomes 1, summed over the days."""
    totals = [[0, Fraction(0), 0] for _ in range(BINS)]
    for summary in summaries:
        found = _of(summary, column)
        if found is not None:
            for total, (count, p, ones) in zip(totals, found.bins):
                total[0] += count
                total[1] += Fraction(p)
                total[2] += ones
    return [(count, p, ones) for count, p, ones in totals]


def _gap(count: int, p: Fraction, ones: int) -> Fraction:
    """A bin's mean forecast less its share of 1, without its sign."""
    return abs(p / count - Fraction(ones, count))


def _error(bins: Sequence[tuple[int, Fraction, int]]) -> Fraction | None:
    """The count-weighted mean absolute gap over the bins; None without a scored row."""
    filled = [(count, _gap(count, p, ones)) for count, p, ones in bins if count]
    if not filled:
        return None
    return sum(count * gap for count, gap in filled) / sum(count for count, _ in filled)


def _edges(index: int) -> tuple[Decimal, Decimal]:
    """A bin's two ends: 0.0 and 0.1 for the first, 0.9 and 1.0 for the last."""
    return Decimal(index).scaleb(-1), Decimal(index + 1).scaleb(-1)


def _rows(bins: Sequence[tuple[int, Fraction, int]]) -> list[dict]:
    rows = []
    for index, (count, p, ones) in enumerate(bins):
        low, high = _edges(index)
        rows.append({"low": low, "high": high, "count": count,
                     "mean_p": _decimal(p / count) if count else None,
                     "share": _decimal(Fraction(ones, count)) if count else None})
    return rows


def calibration(summaries: Sequence[DaySummary], column: str | None = None) -> tuple[list[dict], Decimal | None]:
    """The ten bins over the days given, each {"low", "high", "count", "mean_p", "share"} (the last two None for an
    empty bin), and the calibration error (None without a scored row)."""
    bins = _bins(summaries, column)
    error = _error(bins)
    return _rows(bins), None if error is None else _decimal(error)


def holds_share(count: int, rows: int) -> bool:
    """Whether a bin of `count` scored rows holds BIN_SHARE (1%) or more of `rows` (F9; the record page's sentence per
    bin, F11, reads it too)."""
    return count >= Fraction(BIN_SHARE) * rows


def _off(bins: Sequence[tuple[int, Fraction, int]]) -> list[tuple[int, Fraction, Fraction]]:
    """The bins holding BIN_SHARE or more of the scored rows whose mean and share are more than BIN_OFF apart: each
    its index, its share of the rows and its gap."""
    rows = sum(count for count, _, _ in bins)
    return [(index, Fraction(count, rows), _gap(count, p, ones)) for index, (count, p, ones) in enumerate(bins)
            if count and holds_share(count, rows) and _gap(count, p, ones) > Fraction(BIN_OFF)]


def _beats(days: Sequence[_Day], reasons: list[str]) -> bool:
    """F9's second condition over the days; a reason added for each part that fails."""
    found = _brier(days)
    if found is None:
        reasons.append("no scored day to compare with the baselines")
        return False
    model, a, b = found
    holds = True
    for name, baseline in (("A", a), ("B", b)):
        if not model < baseline:
            reasons.append(f"the model's Brier score {_shown(model)} is not below baseline {name}'s {_shown(baseline)}")
            holds = False
    spans = _spans(days)
    if spans is None:
        reasons.append(f"too few scored days for an interval: {len(days)}, of the {MIN_DAYS} needed")
        return False
    for name in ("A", "B"):
        span = spans[f"model_minus_{name.lower()}"]
        if not span.high < 0:
            reasons.append(f"the {LEVEL}% interval of the model's Brier score less baseline {name}'s is not wholly "
                           f"below zero: {span.low:.{SHOWN}f} to {span.high:.{SHOWN}f}")
            holds = False
    return holds


def _calibrated(bins: Sequence[tuple[int, Fraction, int]], reasons: list[str]) -> bool:
    """F9's third condition over the bins; a reason added for each part that fails."""
    error = _error(bins)
    if error is None:
        reasons.append("no scored row to check the calibration on")
        return False
    holds = True
    if error > Fraction(CAL_MAX):
        reasons.append(f"the calibration error is {_shown(error)}, above {CAL_MAX}")
        holds = False
    for index, share, gap in _off(bins):
        low, high = _edges(index)
        reasons.append(f"the bin from {low} to {high} holds {_shown(share * 100, 2)}% of the scored rows and is off "
                       f"by {_shown(gap)}, more than {BIN_OFF}")
        holds = False
    return holds


def gate(summaries: Sequence[DaySummary], column: str) -> Gate:
    """The column's gate (the module's docstring): its conditions over the days of the version in force frozen on
    time at that column; closed in step one."""
    counted = _counted(summaries, IN_FORCE)
    days = _daily(counted, column)
    bins = _bins(counted, column)
    reasons: list[str] = []
    enough = len(days) >= GATE_DAYS
    if not enough:
        reasons.append(f"{len(days)} scored day{'' if len(days) == 1 else 's'} of the version in force "
                       f"(model {MODEL_VERSION}, target {TARGET_VERSION}) frozen on time; {GATE_DAYS} needed")
    conditions = {"days": enough, "brier": _beats(days, reasons), "calibration": _calibrated(bins, reasons)}
    if all(conditions.values()):
        reasons.append("every condition holds; the gate opens only on the owner's go, in step three")
    return Gate(column=column, conditions=conditions, reasons=reasons, open=False)


def _month(day: date) -> str:
    return day.isoformat()[:7]


def _plain(row: dict) -> dict:
    """A calibration row with its decimals as text."""
    return {key: format(value, "f") if isinstance(value, Decimal) else value for key, value in row.items()}


def _record(held: Sequence[DaySummary], version: tuple[str, str], column: str | None) -> dict:
    """The record of a version's days holding the column (a month's or the whole), as the scorecard writes it."""
    counted = _counted(held, version)
    parts = [_of(summary, column) for summary in counted]
    days = _daily(counted, column)
    found = _brier(days)
    spans = _spans(days)
    bins = _bins(counted, column)
    scored, ones = sum(part.scored for part in parts), sum(part.outcome_1 for part in parts)
    return {
        "days_on_time": len(counted), "days_late": len(held) - len(counted), "days_scored": len(days),
        "forecasts": sum(part.forecasts for part in parts), "scored": scored,
        "unscored": sum(part.unscored for part in parts), "outcome_1": ones,
        "outcome_1_share": _text(Fraction(ones, scored)) if scored else None,
        "brier": None if found is None else {"model": _text(found[0]), "a": _text(found[1]), "b": _text(found[2])},
        "skill": None if found is None else {"a": _text(_skill(found[0], found[1])),
                                             "b": _text(_skill(found[0], found[2]))},
        "intervals": None if spans is None else {
            name: None if span is None else {"low": span.low, "high": span.high} for name, span in spans.items()},
        "calibration": {"bins": [_plain(row) for row in _rows(bins)], "error": _text(_error(bins))},
    }


def _versions(summaries: Sequence[DaySummary], column: str | None) -> list[dict]:
    """A row per version holding the column, in the order each was first frozen, with its months and its whole."""
    held = sorted((summary for summary in summaries if _of(summary, column) is not None), key=lambda found: found.day)
    rows = []
    for version in dict.fromkeys((summary.model_version, summary.target_version) for summary in held):
        mine = _of_version(held, version)
        months = {month: [summary for summary in mine if _month(summary.day) == month]
                  for month in sorted({_month(summary.day) for summary in mine})}
        rows.append({"model_version": version[0], "target_version": version[1],
                     "all": _record(mine, version, column),
                     "months": [{"month": month, **_record(days, version, column)} for month, days in months.items()]})
    return rows


def scorecard(summaries: Sequence[DaySummary]) -> dict:
    """The record page's numbers (the module's docstring), per column in `COLUMNS`' order, with each column's gate as
    its fields (`Gate(**card["columns"][key]["gate"])` is the column's `Gate`)."""
    summaries = list(summaries)
    return {
        "columns_tested": len(COLUMNS),
        "versions_tried": len({(summary.model_version, summary.target_version) for summary in summaries
                               if summary.by_column}),
        "version_in_force": {"model_version": MODEL_VERSION, "target_version": TARGET_VERSION},
        "bootstrap": {"block": BLOCK, "draws": DRAWS, "seed": SEED, "level": LEVEL, "min_days": MIN_DAYS},
        "columns": {column.key: {"name": column.name, "versions": _versions(summaries, column.key),
                                 "gate": asdict(gate(summaries, column.key))} for column in COLUMNS},
    }

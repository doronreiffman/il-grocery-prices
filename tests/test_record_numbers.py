"""The record's numbers (docs/shopper-site.md F7's Brier score, F8, F9 and F11, with its "Changed after the survey", S1
and "Words", and Call 20; the plan's Task 14).

Every input is a scored day's summary in the shape Task 13's `summarize` gives it (`DaySummary`, a `ColumnSummary` per
column), built by hand: a day of 100 scored rows whose sums of squares give the Brier scores beside each helper, and
ten bins whose counts, sums of p and outcomes 1 give the calibration worked out by hand. The bootstrap is seeded, so
its intervals are the same each run; one test recomputes them with the design's block, draws and seed written out as
numbers, in the plainest loop."""
import json
import math
import random
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

import pytest

from shopper.columns import COLUMNS
from shopper.record import (
    BIN_OFF,
    BIN_SHARE,
    BLOCK,
    CAL_MAX,
    DRAWS,
    GATE_DAYS,
    SEED,
    Gate,
    Interval,
    brier,
    calibration,
    gate,
    intervals,
    scorecard,
)
from shopper.score import ColumnSummary, DaySummary

D = Decimal
DEAL, RAMI, OSHER = "shufersal-deal", "ramilevy", "osherad"
START = date(2026, 12, 1)                    # the first scored day of the tests


def _bins(*filled: tuple[int, int, str, int]) -> tuple[tuple[int, Decimal, int], ...]:
    """Ten bins, empty but for those given as (index, count, sum of p, outcomes 1)."""
    bins = [(0, D(0), 0)] * 10
    for index, count, total, ones in filled:
        bins[index] = (count, D(total), ones)
    return tuple(bins)


# 40 rows at about 0.15 of which 6 came out 1 (no gap), 60 at about 0.35 of which 18 did (a gap of 3 in 60):
# the calibration error is 3 / 100 = 0.03 exactly, and no bin is off by more than 0.10 (0.05 at most).
GOOD_BINS = _bins((1, 40, "6", 6), (3, 60, "21", 18))


def _part(sq_model, sq_a, sq_b, bins=GOOD_BINS, unscored=0) -> ColumnSummary:
    """A column's day: as many scored rows as the bins hold, the sums of squares given."""
    scored = sum(count for count, _, _ in bins)
    return ColumnSummary(forecasts=scored + unscored, scored=scored, unscored=unscored,
                         outcome_1=sum(ones for _, _, ones in bins), sq_model=D(sq_model), sq_a=D(sq_a),
                         sq_b=D(sq_b), bins=bins)


def _day(n: int, columns: dict[str, ColumnSummary], on_time=True, model="1", target="1") -> DaySummary:
    """Day START + n's summary; a late day's file went up after its midnight (Israel time is UTC+2 in winter)."""
    day = START + timedelta(days=n)
    at = datetime.combine(day, time(10, 40), tzinfo=timezone.utc) if on_time else \
        datetime.combine(day, time(22, 5), tzinfo=timezone.utc)
    return DaySummary(day=day, frozen_at=at, on_time=on_time, model_version=model, target_version=target,
                      by_column=columns)


def _good(n: int, bins=GOOD_BINS) -> ColumnSummary:
    """A day the model wins on: its Brier score 0.100 to 0.102, A's 0.120 to 0.124, B's 0.150, by 100 rows."""
    return _part(D(10) + D(n % 3) / 10, D(12) + D(n % 5) / 10, "15", bins)


def _good_days(count: int, column=DEAL, start=0, **day) -> list[DaySummary]:
    return [_day(n, {column: _good(n)}, **day) for n in range(start, start + count)]


ALL_HOLD = {"days": True, "brier": True, "calibration": True}


# --- the Brier score (F7): the mean over a day's scored forecasts, then over days

def test_brier_is_a_mean_of_daily_means():
    days = [_day(0, {DEAL: _part("0.5", "0.6", "0.8", _bins((2, 2, "0.5", 1))),          # 0.25, 0.3, 0.4 by 2 rows
                     RAMI: _part("0.8", "1.6", "0.8", _bins((1, 8, "1", 1)))}),          # 0.1, 0.2, 0.1 by 8 rows
            _day(1, {DEAL: _part("0.8", "1.6", "0.8", _bins((1, 8, "1", 1)))})]          # 0.1, 0.2, 0.1 by 8 rows
    # At Deal: (0.25 + 0.1) / 2 = 0.175, never the rows pooled ((0.5 + 0.8) / 10 = 0.13).
    assert brier(days, DEAL) == (D("0.175"), D("0.25"), D("0.25"))
    # Rami Levy has one day.
    assert brier(days, RAMI) == (D("0.1"), D("0.2"), D("0.1"))
    # Every column: a day's rows pooled over its columns (the model's (0.5 + 0.8) / 10 = 0.13 on day 0, B's
    # (0.8 + 0.8) / 10 = 0.16), then the mean over days.
    assert brier(days) == (D("0.115"), D("0.21"), D("0.13"))


def test_a_day_without_a_scored_row_is_no_scored_day():
    """A column-day whose rows were all unscored (more than 4 holes) has no Brier score of its own: it is left out,
    not counted as 0 out of 0."""
    unscored = ColumnSummary(forecasts=5, scored=0, unscored=5, outcome_1=0, sq_model=D(0), sq_a=D(0), sq_b=D(0),
                             bins=_bins())
    days = [_day(0, {DEAL: unscored}), _day(1, {DEAL: _part("10", "12", "15")})]
    assert brier(days, DEAL) == (D("0.1"), D("0.12"), D("0.15"))
    assert brier([_day(0, {DEAL: unscored})], DEAL) is None
    assert brier([], DEAL) is None
    assert brier(days, OSHER) is None
    # A day with no forecasts at all: Task 13's summary of no column and no versions. It is no day anywhere.
    empty = DaySummary(day=START, frozen_at=datetime(2026, 12, 1, 10, 40, tzinfo=timezone.utc), on_time=True,
                       model_version="", target_version="", by_column={})
    assert brier([empty]) is None and brier([empty], DEAL) is None
    card = scorecard([empty])
    assert card["versions_tried"] == 0 and "all_columns" not in card
    assert card["columns"][DEAL]["versions"] == []


def test_the_record_numbers_are_exact_to_twelve_places_half_up():
    days = [_day(n, {DEAL: _part("1", "3", "7", _bins((1, 3, "0.45", 1)))}) for n in range(2)]   # 1/3, 1, 7/3
    assert brier(days, DEAL) == (D("0.333333333333"), D("1.000000000000"), D("2.333333333333"))
    days = [_day(n, {DEAL: _part("2", "3", "7", _bins((1, 3, "0.45", 1)))}) for n in range(2)]   # 2/3: half up
    assert brier(days, DEAL)[0] == D("0.666666666667")


# --- intervals (F8): a moving-block bootstrap over the scored days

def _reference(days: list[DaySummary], column: str) -> dict[str, tuple[float, float]]:
    """The design's bootstrap in its plainest form, its numbers written out: blocks of 14 consecutive scored days,
    each start floor(random() x the starts), as many blocks as cover the days, cut to the number of days; 10,000
    draws from random.Random(20261107); the 2.5th and 97.5th percentiles, linear between neighbours."""
    means = [(Fraction(found.sq_model) / found.scored, Fraction(found.sq_a) / found.scored,
              Fraction(found.sq_b) / found.scored) for found in (day.by_column[column] for day in days)]
    m, a, b = ([float(day[i]) for day in means] for i in range(3))
    minus_a, minus_b = [float(day[0] - day[1]) for day in means], [float(day[0] - day[2]) for day in means]
    rng = random.Random(20261107)
    n = len(days)
    starts = n - 14 + 1
    draws = {"model_minus_a": [], "model_minus_b": [], "skill_a": [], "skill_b": []}
    for _ in range(10_000):
        picked = []
        while len(picked) < n:
            start = math.floor(rng.random() * starts)
            picked.extend(range(start, start + 14))
        picked = picked[:n]
        draws["model_minus_a"].append(sum(minus_a[i] for i in picked) / n)
        draws["model_minus_b"].append(sum(minus_b[i] for i in picked) / n)
        draws["skill_a"].append(1 - sum(m[i] for i in picked) / sum(a[i] for i in picked))
        draws["skill_b"].append(1 - sum(m[i] for i in picked) / sum(b[i] for i in picked))

    def percentile(values, q):
        ordered = sorted(values)
        position = q * (len(ordered) - 1)
        below = math.floor(position)
        return ordered[below] + (ordered[below + 1] - ordered[below]) * (position - below)

    return {name: (percentile(values, 0.025), percentile(values, 0.975)) for name, values in draws.items()}


def _varied(n: int) -> ColumnSummary:
    """A day whose three scores move apart from day to day."""
    return _part(D(8) + D(n * 7 % 11) / 10, D(10) + D(n * 5 % 13) / 10, D(11) + D(n * 3 % 7) / 10)


def test_the_seed_block_and_draws_are_the_designs():
    assert (BLOCK, DRAWS, SEED) == (14, 10_000, 20261107)
    days = [_day(n, {DEAL: _varied(n)}) for n in range(40)]      # 40 days: three blocks, the last cut to 12 days
    found = intervals(days, DEAL)
    expected = _reference(days, DEAL)
    assert set(found) == set(expected)
    for name, (low, high) in expected.items():
        assert found[name] == Interval(pytest.approx(low, rel=1e-9, abs=1e-12),
                                       pytest.approx(high, rel=1e-9, abs=1e-12)), name
        assert low < high, name                                   # a spread, so a wrong rule shows


def test_the_bootstrap_is_the_same_each_run():
    days = [_day(n, {DEAL: _varied(n)}) for n in range(30)]
    assert intervals(days, DEAL) == intervals(days, DEAL)


def test_constant_differences_give_a_point_interval():
    """Known by hand (the design's "Testing"): when the model's Brier score is the same distance below A's and below
    B's on every day, every draw's mean difference is that distance, so each interval is a single point."""
    days = [_day(n, {DEAL: _part(D(8) + D(n % 7) / 10, D(10) + D(n % 7) / 10, D(13) + D(n % 7) / 10)})
            for n in range(30)]                                   # the scores move; A is 0.02 above, B 0.05
    found = intervals(days, DEAL)
    for name, distance in (("model_minus_a", -0.02), ("model_minus_b", -0.05)):
        assert found[name].low == found[name].high, name
        assert found[name].low == pytest.approx(distance, abs=1e-12), name
    # The same day every day: every draw is that day, so the skills are points too: 1 - 0.10 / 0.12 and 1 - 0.10 / 0.15.
    same = intervals([_day(n, {DEAL: _part("10", "12", "15")}) for n in range(30)], DEAL)
    assert same["skill_a"].low == same["skill_a"].high == pytest.approx(1 / 6, abs=1e-12)
    assert same["skill_b"].low == same["skill_b"].high == pytest.approx(1 / 3, abs=1e-12)


def test_no_interval_under_28_days():
    """Two blocks of 14 at least ("too few days" before)."""
    assert intervals(_good_days(27), DEAL) is None
    assert set(intervals(_good_days(28), DEAL)) == {"model_minus_a", "model_minus_b", "skill_a", "skill_b"}
    # Counted at the column: 28 days at Deal, 27 at Rami Levy.
    days = [_day(n, {DEAL: _good(n), **({RAMI: _good(n)} if n else {})}) for n in range(28)]
    assert intervals(days, DEAL) is not None
    assert intervals(days, RAMI) is None
    assert intervals(days) is not None


def test_a_zero_baseline_has_no_skill():
    """A baseline whose Brier score is 0 on every drawn day leaves the skill undefined (a division by 0): its interval
    is None, never a crash; the differences still have theirs."""
    days = [_day(n, {DEAL: _part("1", "0" if n < 20 else "2", "15")}) for n in range(30)]
    found = intervals(days, DEAL)
    assert found["skill_a"] is None
    assert found["model_minus_a"] is not None and found["skill_b"] is not None
    # A's Brier score 0 on every day: no skill against A at all; against B, 1 - 0.01 / 0.15.
    flat = scorecard([_day(n, {DEAL: _part("1", "0", "15")}) for n in range(30)])["columns"][DEAL]
    assert flat["versions"][0]["all"]["skill"] == {"a": None, "b": "0.933333333333"}
    assert flat["versions"][0]["all"]["intervals"]["skill_a"] is None


# --- calibration (F8): ten bins of width 0.1, the count-weighted mean absolute gap

def test_calibration_error_by_hand():
    """30 rows at a mean of 0.15 of which 6 came out 1 (a gap of 0.05), 10 at 0.75 of which 5 did (0.25), over two
    days: (30 x 0.05 + 10 x 0.25) / 40 = 0.1, where the bins weighted equally would give 0.15."""
    days = [_day(0, {DEAL: _part("1", "1", "1", _bins((1, 20, "3", 4), (7, 4, "3", 2)))}),
            _day(1, {DEAL: _part("1", "1", "1", _bins((1, 10, "1.5", 2), (7, 6, "4.5", 3)))})]
    rows, error = calibration(days, DEAL)
    assert error == D("0.1")
    assert [(row["low"], row["high"]) for row in rows] == [(D(i) / 10, D(i + 1) / 10) for i in range(10)]
    assert rows[1] == {"low": D("0.1"), "high": D("0.2"), "count": 30, "mean_p": D("0.15"), "share": D("0.2")}
    assert rows[7] == {"low": D("0.7"), "high": D("0.8"), "count": 10, "mean_p": D("0.75"), "share": D("0.5")}
    assert rows[0] == {"low": D("0.0"), "high": D("0.1"), "count": 0, "mean_p": None, "share": None}
    assert [row["count"] for row in rows] == [0, 30, 0, 0, 0, 0, 0, 10, 0, 0]
    # Every column: Deal's bins and Rami Levy's summed. Rami Levy's 10 rows at 0.75, all 1, make bin 7 20 rows at
    # 0.75 of which 15 came out 1 (no gap): (30 x 0.05 + 20 x 0) / 50 = 0.03.
    days.append(_day(2, {RAMI: _part("1", "1", "1", _bins((7, 10, "7.5", 10)))}))
    rows, error = calibration(days)
    assert (rows[7]["count"], rows[7]["mean_p"], rows[7]["share"]) == (20, D("0.75"), D("0.75"))
    assert error == D("0.03")
    assert calibration(days, DEAL)[1] == D("0.1")


def test_calibration_without_a_scored_row():
    rows, error = calibration([], DEAL)
    assert error is None
    assert [row["count"] for row in rows] == [0] * 10


# --- the gate (F9), per column, closed in step one

def _touching(n: int) -> ColumnSummary:
    """The model level with A on every day but one, 0.01 below it there; B well above: most draws of model - A that
    miss that day are exactly 0, so the interval's upper end is 0."""
    return _part("10", "11" if n == 45 else "10", "15")


CASES = {
    "89 days": (_good_days(89), "days", "89 scored days of the version in force"),
    "Brier above B": ([_day(n, {DEAL: _part(D(10) + D(n % 3) / 10, D(12) + D(n % 5) / 10, "9")}) for n in range(90)],
                      "brier", "is not below baseline B's 0.0900"),
    "an interval touching zero": ([_day(n, {DEAL: _touching(n)}) for n in range(90)], "brier",
                                  "less baseline A's is not wholly below zero"),
    "error 0.031": ([_day(n, {DEAL: _good(n, _bins((1, 40, "6", 6), (3, 60, "21.1", 18)))}) for n in range(90)],
                    "calibration", "the calibration error is 0.0310, above 0.03"),
    "a bin of 1% off by 0.11": ([_day(n, {DEAL: _good(n, _bins((1, 40, "6", 6), (3, 59, "21", 21), (8, 1, "0.89", 1)))})
                                 for n in range(90)], "calibration",
                                "the bin from 0.8 to 0.9 holds 1.00% of the scored rows and is off by 0.1100"),
}


@pytest.mark.parametrize("case", list(CASES))
def test_the_gate_fails_on_each_condition_alone(case):
    days, failing, reason = CASES[case]
    found = gate(days, DEAL)
    assert found.conditions == {**ALL_HOLD, failing: False}
    assert any(reason in line for line in found.reasons), found.reasons
    assert found.open is False


def test_the_gate_holds_at_its_boundaries():
    """90 days exactly, a calibration error of 0.03 exactly (the good days'), a bin of 1% off by 0.10 exactly, and a
    bin under 1% off by 0.11: every condition holds."""
    assert gate(_good_days(90), DEAL).conditions == ALL_HOLD
    at_tenth = [_day(n, {DEAL: _good(n, _bins((1, 40, "6", 6), (3, 59, "21", 21), (9, 1, "0.9", 1)))})
                for n in range(90)]
    assert gate(at_tenth, DEAL).conditions == ALL_HOLD
    under_share = [_day(n, {DEAL: _good(n, _bins((1, 40, "6", 6), (3, 60, "21", 21), (8, 1, "0.89", 1)))})
                   for n in range(90)]                              # 90 of 9,090 rows: under 1%
    assert gate(under_share, DEAL).conditions == ALL_HOLD
    assert (GATE_DAYS, CAL_MAX, BIN_SHARE, BIN_OFF) == (90, D("0.03"), D("0.01"), D("0.10"))


def test_a_late_day_does_not_count_toward_the_gate():
    days = _good_days(90)
    days[10] = _day(10, {DEAL: _good(10)}, on_time=False)
    found = gate(days, DEAL)
    assert found.conditions == {**ALL_HOLD, "days": False}
    assert any("89 scored days" in line for line in found.reasons)
    # 91 days of which one late: 90 count.
    assert gate(_good_days(90) + [_day(90, {DEAL: _good(90)}, on_time=False)], DEAL).conditions == ALL_HOLD
    # A late day's scores count for nothing either: 100 rows at 0.95 of which none came out 1 would lift the
    # calibration error to (90 x 3 + 95) / 9,100 = 0.040 and put a bin of 1.1% off by 0.95.
    bad = _day(90, {DEAL: _part("90", "1", "1", _bins((9, 100, "95", 0)))}, on_time=False)
    assert gate(_good_days(90) + [bad], DEAL).conditions == ALL_HOLD


def test_a_new_version_starts_from_zero():
    """Version 1 is the version in force (`shopper.forecast.MODEL_VERSION`); 100 days of an earlier version 0 count
    for nothing toward it, nor do 90 days of version 1's model against another target."""
    days = _good_days(100, model="0") + _good_days(10, start=100)
    found = gate(days, DEAL)
    assert found.conditions["days"] is False
    assert any("10 scored days" in line for line in found.reasons)
    assert gate(_good_days(90, target="2"), DEAL).conditions["days"] is False
    assert gate(_good_days(100, model="0") + _good_days(90, start=100), DEAL).conditions == ALL_HOLD


def test_each_columns_gate_reads_its_own_days():
    """Deal's 90 days pass; Rami Levy's model loses to B on the same days; Osher Ad has 10 days."""
    days = [_day(n, {DEAL: _good(n), RAMI: _part(D(10) + D(n % 3) / 10, D(12) + D(n % 5) / 10, "9"),
                     **({OSHER: _good(n)} if n < 10 else {})}) for n in range(90)]
    assert gate(days, DEAL) == Gate(column=DEAL, conditions=ALL_HOLD, reasons=gate(days, DEAL).reasons, open=False)
    assert gate(days, RAMI).conditions == {**ALL_HOLD, "brier": False}
    assert gate(days, OSHER).conditions["days"] is False
    assert gate(days, RAMI).column == RAMI


def test_the_gate_stays_closed_in_step_one():
    found = gate(_good_days(90), DEAL)
    assert found.conditions == ALL_HOLD
    assert found.open is False
    assert found.reasons == ["every condition holds; the gate opens only on the owner's go, in step three"]


def test_a_column_with_no_day_is_closed_on_every_condition():
    found = gate([], DEAL)
    assert found.conditions == {"days": False, "brier": False, "calibration": False}
    assert found.open is False and len(found.reasons) == 3
    assert found.reasons[0].startswith("0 scored days of the version in force")
    assert gate(_good_days(1), DEAL).reasons[0].startswith("1 scored day of the version in force")


# --- the scorecard (F11): per column, per version, per month and in all; the gate per column

def test_the_scorecard_counts_the_columns_tested():
    """The design's "Words": the record page says how many columns are tested at once (nine), as it says how many
    versions were tried."""
    card = scorecard(_good_days(100, model="0") + _good_days(10, start=100))
    assert card["columns_tested"] == 9
    assert card["versions_tried"] == 2
    assert list(card["columns"]) == [column.key for column in COLUMNS]
    assert card["columns"][DEAL]["name"] == "Shufersal Deal"
    assert [(row["model_version"], row["target_version"]) for row in card["columns"][DEAL]["versions"]] == \
        [("0", "1"), ("1", "1")]
    assert card["columns"][RAMI]["versions"] == []
    assert all(column["gate"]["open"] is False for column in card["columns"].values())


def test_the_scorecard_prints_the_bootstrap_and_the_version_in_force():
    """Its blocks, and no block of every column pooled: the design defines no pooled Brier score, skill or interval
    (Task 14's review; dropped in the final review's fix wave)."""
    card = scorecard([])
    assert card["bootstrap"] == {"block": 14, "draws": 10_000, "seed": 20261107, "level": 95, "min_days": 28}
    assert card["version_in_force"] == {"model_version": "1", "target_version": "1"}
    assert card["versions_tried"] == 0
    assert set(card) == {"columns_tested", "versions_tried", "version_in_force", "bootstrap", "columns"}


def test_the_scorecard_by_month_with_a_late_day_shown_and_not_counted():
    """40 days from 1 December: 31 in December, of them day 5 late, and 9 in January. Every day the same: the model
    0.10, A 0.12, B 0.15, 24 of 100 rows 1."""
    days = [_day(n, {DEAL: _part("10", "12", "15")}, on_time=n != 5) for n in range(40)]
    days[5] = _day(5, {DEAL: _part("90", "1", "1")}, on_time=False)          # a late day the model lost: not counted
    row = scorecard(days)["columns"][DEAL]["versions"][0]
    december, january = row["months"]
    assert (december["month"], january["month"]) == ("2026-12", "2027-01")
    assert (december["days_on_time"], december["days_late"], december["days_scored"]) == (30, 1, 30)
    assert (january["days_on_time"], january["days_late"], january["days_scored"]) == (9, 0, 9)
    whole = row["all"]
    assert (whole["days_on_time"], whole["days_late"], whole["days_scored"]) == (39, 1, 39)
    assert (whole["forecasts"], whole["scored"], whole["unscored"], whole["outcome_1"]) == (3900, 3900, 0, 936)
    assert whole["outcome_1_share"] == "0.240000000000"
    assert whole["brier"] == {"model": "0.100000000000", "a": "0.120000000000", "b": "0.150000000000"}
    assert whole["skill"] == {"a": "0.166666666667", "b": "0.333333333333"}        # 1 - 0.10/0.12, 1 - 0.10/0.15
    assert whole["intervals"]["model_minus_a"] == {"low": pytest.approx(-0.02), "high": pytest.approx(-0.02)}
    assert december["intervals"] is not None and january["intervals"] is None      # 30 days and 9 ("too few days")
    assert whole["calibration"]["error"] == "0.030000000000"
    assert whole["calibration"]["bins"][3] == {"low": "0.3", "high": "0.4", "count": 2340, "mean_p": "0.350000000000",
                                               "share": "0.300000000000"}
    assert whole["calibration"]["bins"][0] == {"low": "0.0", "high": "0.1", "count": 0, "mean_p": None, "share": None}
    assert row["all"]["brier"]["model"] == format(brier([d for d in days if d.on_time], DEAL)[0], "f")


def test_the_scorecards_gate_is_the_columns_gate():
    days = _good_days(90)
    card = scorecard(days)
    assert card["columns"][DEAL]["gate"] == asdict(gate(days, DEAL))
    assert Gate(**card["columns"][DEAL]["gate"]) == gate(days, DEAL)


def test_each_column_has_its_own_rows_and_the_scorecard_none_pooled():
    days = [_day(n, {DEAL: _part("10", "12", "15"), RAMI: _part("30", "12", "15")}) for n in range(3)]
    card = scorecard(days)
    assert brier(days)[0] == D("0.2") and "all_columns" not in card     # pooled, 40 / 200 a day: never on the card
    assert card["columns"][DEAL]["versions"][0]["all"]["brier"]["model"] == "0.100000000000"
    assert card["columns"][RAMI]["versions"][0]["all"]["brier"]["model"] == "0.300000000000"


def test_the_scorecard_reads_back_from_its_json():
    """The site-day file carries the scorecard and the guard renders the record page again from it (Tasks 19 and
    21), so it holds only what JSON holds and reads back equal."""
    card = scorecard(_good_days(40) + [_day(40, {DEAL: _good(40)}, on_time=False)])
    assert json.loads(json.dumps(card)) == card

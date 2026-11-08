"""Scoring (docs/shopper-site.md F7, with its "Changed after the survey", S1 and "Where the key lives", and Calls 14
and 21; the plan's Task 13, the first pre-flight's S9 and N17 and the second's B1).

A frozen day T's forecasts file (Task 11's `forecasts_csv`, rows keyed by column) is scored by the build of T + 14
against a history of that day: pairs and column-days built by hand in the shapes `shopper.history` yields them (Task
10's tests' helpers), and once through `load` from items tables. Every expected sum is worked by hand from the
frozen file's six-decimal strings beside the test."""
import csv
import gzip
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from basket.archive import MemoryArchive
from shopper.forecast import FILE_FIELDS, MAX_HOLES, Forecast, forecasts_csv
from shopper.freeze import ISRAEL, ArchiveFreezer, Frozen, ledger
from shopper.history import READ_DAYS, History, Pair, load
from shopper.items import HORIZON
from shopper.score import (
    SCORE_FIELDS,
    UNSCORED,
    ColumnSummary,
    DaySummary,
    due,
    out_of_reach,
    reaches,
    read_summary,
    scores_csv,
    summarize,
    summary_json,
    summary_path,
)
from test_forecast import CODES, DEAL, EXPRESS, SHELI, SHUF, _column_day, _forecast, _on, _point, _promotion
from test_history import _row, _table

T = date(2026, 11, 30)                                   # the frozen day
BUILD = T + timedelta(days=HORIZON)                      # 2026-12-14: the build that scores it
FROZEN_AT = datetime(2026, 11, 30, 10, 40, 5, tzinfo=timezone.utc)
D = Decimal


def on(n: int) -> date:
    return T + timedelta(days=n)


def _days(column: str, price_holes=(), promo_holes=(), missing=(), absent=()):
    """The column's days the build of BUILD reads, BUILD - 90 to BUILD (offsets -76 to 14 from T); those at the
    offsets given are holes of that kind, and those in `absent` have no column-day at all."""
    return {(column, on(n)): _column_day(column, on(n), n in price_holes, n in promo_holes, n not in missing)
            for n in range(HORIZON - READ_DAYS, HORIZON + 1) if n not in absent}


class _Read(History):
    """A history of hand-built pairs for the build of `day`, streamed by code, then column, as `History.pairs`."""

    def __init__(self, column_days, pairs, day=BUILD):
        super().__init__(day, column_days, {})
        self._pairs = sorted(pairs, key=lambda pair: (pair.code, pair.column))

    def pairs(self):
        yield from self._pairs


def _one(code: str, column: str = DEAL, n: int = 2, *promotions) -> Pair:
    """A pair on a wide promotion on T + n (outcome 1)."""
    return Pair(column=column, code=code, points={on(n): _on(on(n), *promotions)})


def _zero(code: str, column: str = DEAL) -> Pair:
    """A pair listed in the window, never on a wide promotion (outcome 0)."""
    return Pair(column=column, code=code, points={on(2): _point(on(2))})


def _frozen(rows, on_time=True, at=FROZEN_AT, day=T, body=None) -> Frozen:
    body = forecasts_csv(rows, "f00d") if body is None else body
    return Frozen(day=day, body=body, sha256=hashlib.sha256(body).hexdigest(), frozen_at=at, on_time=on_time,
                  status="frozen" if on_time else "late")


def _rows_of(body: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(gzip.decompress(body).decode())))


def _bins(**filled) -> tuple:
    """Ten bins, each (count, sum of p, outcomes 1): `b7=(1, "0.75", 1)` fills the eighth, the rest are empty."""
    return tuple((filled[f"b{i}"][0], D(filled[f"b{i}"][1]), filled[f"b{i}"][2]) if f"b{i}" in filled
                 else (0, D(0), 0) for i in range(10))


def _empty(forecasts: int) -> ColumnSummary:
    """A column whose `forecasts` rows are all unscored."""
    return ColumnSummary(forecasts=forecasts, scored=0, unscored=forecasts, outcome_1=0, sq_model=D(0), sq_a=D(0),
                         sq_b=D(0), bins=_bins())


# Test 1's day: Deal scores an outcome 1 and an outcome 0; Express has five holes in the window, so its row is unscored.
SAME_ROWS = [_forecast(DEAL, CODES[0], p=Fraction(3, 4), a=Fraction(1, 2), b=Fraction(1, 4)),
             _forecast(DEAL, CODES[1], p=Fraction(1, 5), a=Fraction(1, 10), b=Fraction(3, 5)),
             _forecast(EXPRESS, CODES[0], p=Fraction(1, 2), a=Fraction(1, 4), b=Fraction(3, 4))]
SAME_DAYS = {**_days(DEAL), **_days(EXPRESS, price_holes=(1, 2, 3, 4, 5))}
SAME_PAIRS = [_one(CODES[0]), _zero(CODES[1]), _one(CODES[0], EXPRESS, 6)]
# By hand, Deal: the model (0.75 - 1)² + (0.2 - 0)² = 0.0625 + 0.04; A (0.5 - 1)² + (0.1 - 0)² = 0.25 + 0.01;
# B (0.25 - 1)² + (0.6 - 0)² = 0.5625 + 0.36; the bins 0.75 (outcome 1) in the eighth, 0.2 (outcome 0) in the third.
SAME_DEAL = ColumnSummary(forecasts=2, scored=2, unscored=0, outcome_1=1, sq_model=D("0.1025"), sq_a=D("0.26"),
                          sq_b=D("0.9225"), bins=_bins(b7=(1, "0.75", 1), b2=(1, "0.2", 0)))
SAME_SUMMARY = DaySummary(day=T, frozen_at=FROZEN_AT, on_time=True, model_version="1", target_version="1",
                          by_column={DEAL: SAME_DEAL, EXPRESS: _empty(1)})


def _same_day():
    frozen = _frozen(SAME_ROWS)
    return frozen, scores_csv(frozen, _Read(SAME_DAYS, SAME_PAIRS))


# Which days are due

def test_a_missed_scoring_is_done_by_the_next_build():
    frozen = [date(2026, 11, n) for n in range(1, 11)] + [date(2026, 11, 20)]
    scored = [date(2026, 11, n) for n in (1, 2, 3)]          # by the builds of 15, 16 and 17 November
    # the builds of 18, 19 and 20 November did not run: the build of the 21st scores their days and its own, oldest first
    assert due(frozen, scored, date(2026, 11, 21)) == [date(2026, 11, n) for n in (4, 5, 6, 7)]
    assert due(reversed(frozen), set(scored), date(2026, 11, 21)) == [date(2026, 11, n) for n in (4, 5, 6, 7)]
    assert due([*frozen, *frozen], scored, date(2026, 11, 21)) == [date(2026, 11, n) for n in (4, 5, 6, 7)]


def test_a_day_is_due_on_day_t_plus_14_and_not_before():
    frozen = [T]
    assert due(frozen, [], BUILD) == [T]                      # t = d - 14
    assert due(frozen, [], BUILD - timedelta(days=1)) == []   # t = d - 13: day t + 14's tables are not there yet
    assert due(frozen, [], BUILD + timedelta(days=30)) == [T]


def test_a_scored_day_is_never_due_again_and_an_unfrozen_one_never_due():
    assert due([T], [T], BUILD + timedelta(days=3)) == []
    assert due([], [T], BUILD) == []
    assert due([T, on(1)], [on(1)], BUILD + timedelta(days=1)) == [T]
    assert out_of_reach([T], [T], on(200)) == [] and out_of_reach([], [], on(200)) == []


def test_a_day_past_the_reads_reach_is_listed_apart_and_nothing_raises():
    frozen = [T, on(1), on(2)]
    # the build of T + 92 reads from T + 2: T's window starts on T + 1, before the read, so it can no longer be scored
    assert due(frozen, [], on(READ_DAYS + 2)) == [on(1), on(2)]
    assert out_of_reach(frozen, [], on(READ_DAYS + 2)) == [T]
    # the build of T + 91 still reads T's whole window: due, and nothing out of reach
    assert due(frozen, [], on(READ_DAYS + 1)) == frozen and out_of_reach(frozen, [], on(READ_DAYS + 1)) == []
    # long after, every unscored day is listed apart, oldest first, and a scored one is in neither list
    assert out_of_reach(reversed(frozen), [on(1)], on(400)) == [T, on(2)] and due(frozen, [on(1)], on(400)) == []
    assert (reaches(T, on(READ_DAYS + 1)), reaches(T, on(READ_DAYS + 2))) == (True, False)
    # and what `due` gives, scores_csv scores: the edge of the read is no refusal
    frozen_t = _frozen(SAME_ROWS)
    scores_csv(frozen_t, _Read(SAME_DAYS, SAME_PAIRS, day=on(READ_DAYS + 1)))


# The scores file

def test_model_and_baselines_are_scored_on_the_same_rows():
    frozen, scores = _same_day()
    header, *rows = _rows_of(scores)
    assert [row[len(FILE_FIELDS):] for row in rows] == [
        ["1", "0", "2026-12-02", "7", "", "day and PromotionID"],
        ["0", "0", "", "", "", ""],
        ["", "5", "", "", "more than 4 holes", ""]]
    summary = summarize(scores, frozen)
    assert summary == SAME_SUMMARY
    # every scored row scores all three; the unscored one none of them, the model's included
    assert summary.by_column[EXPRESS].sq_model == summary.by_column[EXPRESS].sq_a == D(0)
    assert summary.by_column[DEAL].scored == 2 == len([row for row in rows if row[0] == DEAL])


def test_more_than_four_holes_is_unscored_and_counted():
    kinds = dict(price_holes=(1,), promo_holes=(2,), missing=(3,), absent=(4,))   # four holes, one of each kind
    column_days = {**_days(DEAL), **_days(EXPRESS, **{**kinds, "price_holes": (1, 5)}), **_days(SHELI, **kinds)}
    rows = [_forecast(DEAL, CODES[0]), _forecast(EXPRESS, CODES[0]), _forecast(SHELI, CODES[0])]
    pairs = [_zero(CODES[0]), _one(CODES[0], EXPRESS, 6), _one(CODES[0], SHELI, 6)]
    frozen = _frozen(rows)
    scores = scores_csv(frozen, _Read(column_days, pairs))
    assert [row[len(FILE_FIELDS):] for row in _rows_of(scores)[1:]] == [
        ["0", "0", "", "", "", ""],                            # another column's holes are no holes here (B1)
        ["", "5", "", "", "more than 4 holes", ""],            # a promotion seen, and still unscored
        ["1", "4", "2026-12-06", "7", "", "day and PromotionID"]]
    assert UNSCORED == f"more than {MAX_HOLES} holes" == "more than 4 holes"
    # p 0.5, A 0.25, B 0.75 on each row: Deal's outcome 0, Sheli's 1
    assert summarize(scores, frozen).by_column == {
        DEAL: ColumnSummary(forecasts=1, scored=1, unscored=0, outcome_1=0, sq_model=D("0.25"), sq_a=D("0.0625"),
                            sq_b=D("0.5625"), bins=_bins(b5=(1, "0.5", 0))),
        EXPRESS: _empty(1),
        SHELI: ColumnSummary(forecasts=1, scored=1, unscored=0, outcome_1=1, sq_model=D("0.25"), sq_a=D("0.5625"),
                             sq_b=D("0.0625"), bins=_bins(b5=(1, "0.5", 1)))}


def test_the_evidence_is_the_first_day_and_its_smallest_promotion_id():
    rows = [_forecast(DEAL, code) for code in CODES[:3]]
    pairs = [
        Pair(column=DEAL, code=CODES[0], points={
            on(1): _point(on(1)),
            on(3): _on(on(3), _promotion("30"), _promotion("12"), _promotion("9", wide=False)),
            on(5): _on(on(5), _promotion("1"))}),
        # on a wide promotion, though the row's struct shows the promotion's link at some stores only (Task 6)
        Pair(column=DEAL, code=CODES[1], points={on(4): _on(on(4), _promotion("5", wide=False))}),
        _zero(CODES[2]),
    ]
    scores = scores_csv(_frozen(rows), _Read(_days(DEAL), pairs))
    assert [row[len(FILE_FIELDS):] for row in _rows_of(scores)[1:]] == [
        ["1", "0", "2026-12-03", "12", "", "day and PromotionID"],
        ["1", "0", "2026-12-04", "", "", "day only"],
        ["0", "0", "", "", "", ""]]


def test_an_item_no_longer_listed_scores_0():
    rows = [_forecast(DEAL, CODES[0]), _forecast(DEAL, CODES[1])]
    scores = scores_csv(_frozen(rows), _Read(_days(DEAL, price_holes=(9,)), [_one(CODES[1])]))
    assert [row[:2] + row[len(FILE_FIELDS):] for row in _rows_of(scores)[1:]] == [
        [DEAL, CODES[0], "0", "1", "", "", "", ""],            # not in the history at all: its column's days alone
        [DEAL, CODES[1], "1", "1", "2026-12-02", "7", "", "day and PromotionID"]]


def test_the_scores_file_is_the_frozen_rows_then_the_outcomes():
    frozen, scores = _same_day()
    header, *rows = _rows_of(scores)
    assert SCORE_FIELDS == ("outcome", "holes", "first_day", "promotion_id", "unscored", "evidence")
    assert tuple(header) == (*FILE_FIELDS, *SCORE_FIELDS)
    assert [row[:len(FILE_FIELDS)] for row in rows] == _rows_of(frozen.body)[1:]     # the frozen rows, as they stand
    assert scores_csv(frozen, _Read(SAME_DAYS, list(reversed(SAME_PAIRS)))) == scores    # the same bytes again
    assert scores[4:8] == b"\x00\x00\x00\x00"                  # gzip's header time: none
    assert gzip.decompress(scores).decode().splitlines()[1] == (
        "shufersal-deal,2000000000015,0.750000,0.500000,0.250000,0,,0,column,1,1,30,f00d,1,0,2026-12-02,7,,"
        "day and PromotionID")


def test_scoring_needs_the_whole_window_in_the_history():
    frozen = _frozen(SAME_ROWS)
    with pytest.raises(ValueError, match="2026-11-30"):
        scores_csv(frozen, _Read(SAME_DAYS, SAME_PAIRS, day=BUILD - timedelta(days=1)))   # day T + 14 not there yet
    with pytest.raises(ValueError, match="2026-11-30"):
        scores_csv(frozen, _Read(SAME_DAYS, SAME_PAIRS, day=on(READ_DAYS + 2)))           # T + 1 before the read
    late = scores_csv(frozen, _Read(SAME_DAYS, SAME_PAIRS, day=on(READ_DAYS + 1)))       # T + 1 the read's first day
    assert _rows_of(late)[1][len(FILE_FIELDS):] == ["1", "0", "2026-12-02", "7", "", "day and PromotionID"]


def test_the_probabilities_are_the_frozen_six_decimal_strings():
    rows = [_forecast(DEAL, CODES[0], p=Fraction(1, 3), a=Fraction(2, 3), b=Fraction(1, 7))]
    frozen = _frozen(rows)
    assert _rows_of(frozen.body)[1][2:5] == ["0.333333", "0.666667", "0.142857"]
    found = summarize(scores_csv(frozen, _Read(_days(DEAL), [_zero(CODES[0])])), frozen).by_column[DEAL]
    # 0.333333² and so on, exactly: not (1/3)², and no float in between
    assert (found.sq_model, found.sq_a, found.sq_b) == (D("0.111110888889"), D("0.444444888889"), D("0.020408122449"))
    assert found.bins[3] == (1, D("0.333333"), 0)


def test_a_frozen_file_of_another_target_version_is_refused():
    text = gzip.decompress(forecasts_csv([_forecast(DEAL, CODES[0])], "f00d")).decode()
    other = text.replace(",1,1,30,f00d", ",1,2,30,f00d")      # target version 2
    with pytest.raises(ValueError, match="target version"):
        scores_csv(_frozen([], body=gzip.compress(other.encode(), mtime=0)), _Read(_days(DEAL), [_zero(CODES[0])]))


def test_a_frozen_file_with_other_fields_is_refused():
    body = gzip.compress(b"column,barcode,p\nshufersal-deal,2000000000015,0.5\n", mtime=0)
    with pytest.raises(ValueError, match="fields"):
        scores_csv(_frozen([], body=body), _Read(_days(DEAL), []))


def test_a_day_with_no_forecasts():
    frozen = _frozen([])
    scores = scores_csv(frozen, _Read(_days(DEAL), []))
    assert _rows_of(scores) == [[*FILE_FIELDS, *SCORE_FIELDS]]
    assert summarize(scores, frozen) == DaySummary(day=T, frozen_at=FROZEN_AT, on_time=True, model_version="",
                                                   target_version="", by_column={})


def test_a_frozen_day_scored_through_load(tmp_path):
    promotion = {"promotion_id": "7", "description": "מבצע", "start": "2026-11-01", "end": "2026-12-31", "kind": "3",
                 "buy": "1.000", "price": "7.90", "price_exact": "79/10", "per": None, "low": None, "high": None,
                 "valid": True, "why": None, "restrictions": [], "programmes": [], "min_spend": None, "stores": 4,
                 "wide": True}
    for n in range(0, HORIZON + 1):                            # the tables of T to BUILD; earlier days are holes
        rows = [_row(DEAL, CODES[0]), _row(EXPRESS, CODES[0])]
        if n == 6:
            rows = [_row(DEAL, CODES[0], on_promotion=True, promotions=[promotion]), _row(EXPRESS, CODES[0])]
        _table(tmp_path, SHUF, on(n), rows, holes=(EXPRESS,) if n in (1, 2, 3, 4, 5) else ())
    history = load(tmp_path, BUILD, [SHUF])
    rows = [_forecast(DEAL, CODES[0]), _forecast(EXPRESS, CODES[0]), _forecast(SHELI, CODES[1])]
    frozen = _frozen(rows)
    assert [row[len(FILE_FIELDS):] for row in _rows_of(scores_csv(frozen, history))[1:]] == [
        ["1", "0", "2026-12-06", "7", "", "day and PromotionID"],
        ["", "5", "", "", "more than 4 holes", ""],
        ["0", "0", "", "", "", ""]]


# The summary

def test_a_late_days_summary_is_not_on_time():
    late_at = datetime(2026, 12, 1, 0, 0, 1, tzinfo=ISRAEL)   # S3's time a second past the cutoff
    frozen = _frozen(SAME_ROWS, on_time=False, at=late_at)
    summary = summarize(scores_csv(frozen, _Read(SAME_DAYS, SAME_PAIRS)), frozen)
    assert (summary.on_time, summary.frozen_at) == (False, late_at)
    assert summary.by_column == SAME_SUMMARY.by_column        # scored all the same; the record leaves it out of the gate


def test_the_summary_recomputes_from_the_published_file():
    frozen, scores = _same_day()
    lines = gzip.decompress(frozen.body).decode().splitlines()
    published = "\n".join([lines[0] + ",outcome,holes,first_day,promotion_id,unscored,evidence",
                           lines[1] + ",1,0,2026-12-02,7,,day and PromotionID",
                           lines[2] + ",0,0,,,,",
                           lines[3] + ",,5,,,more than 4 holes,"]) + "\n"
    copy = gzip.compress(published.encode(), compresslevel=1, mtime=0)   # an outsider's copy, other gzip bytes
    assert gzip.decompress(copy) == gzip.decompress(scores)
    assert summarize(copy, frozen) == summarize(scores, frozen) == SAME_SUMMARY
    # and from the bytes the archive holds once they are put
    stored = ArchiveFreezer(MemoryArchive(), datetime(2026, 12, 14, 12, 33, tzinfo=ISRAEL)).put_scores(T, scores)
    assert summarize(stored, frozen) == SAME_SUMMARY


def test_a_scores_file_of_another_days_forecasts_is_refused():
    frozen, scores = _same_day()
    other = _frozen([_forecast(DEAL, CODES[0])], day=on(1))
    with pytest.raises(ValueError, match="2026-12-01"):
        summarize(scores, other)


def test_a_day_of_two_model_versions_is_refused():
    text = gzip.decompress(forecasts_csv([_forecast(DEAL, CODES[0]), _forecast(DEAL, CODES[1])], "f00d")).decode()
    first, second, third = text.splitlines()
    mixed = "\n".join([first, second, third.replace(",column,1,1,", ",column,2,1,")]) + "\n"
    frozen = _frozen([], body=gzip.compress(mixed.encode(), mtime=0))
    scores = scores_csv(frozen, _Read(_days(DEAL), [_zero(CODES[0]), _zero(CODES[1])]))
    with pytest.raises(ValueError, match="version"):
        summarize(scores, frozen)


def test_bins_are_tenths_with_1_in_the_last():
    tenths = [(Fraction(0), 0), (Fraction(6, 100), 1), (Fraction(99_999, 1_000_000), 0), (Fraction(1, 10), 1),
              (Fraction(15, 100), 0), (Fraction(95, 100), 1), (Fraction(999_999, 1_000_000), 0), (Fraction(1), 1)]
    rows = [_forecast(DEAL, CODES[i], p=p) for i, (p, _) in enumerate(tenths)]
    pairs = [_one(CODES[i]) if one else _zero(CODES[i]) for i, (_, one) in enumerate(tenths)]
    frozen = _frozen(rows)
    found = summarize(scores_csv(frozen, _Read(_days(DEAL), pairs)), frozen).by_column[DEAL]
    # [0, 0.1): 0, 0.06 and 0.099999; [0.1, 0.2): 0.1 and 0.15; [0.9, 1]: 0.95, 0.999999 and 1
    assert found.bins == _bins(b0=(3, "0.159999", 1), b1=(2, "0.25", 1), b9=(3, "2.949999", 2))
    assert len(found.bins) == 10 and sum(count for count, _, _ in found.bins) == found.scored == 8


def test_each_column_is_summed_apart():
    rows = [_forecast(DEAL, CODES[0], p=Fraction(3, 4)), _forecast(EXPRESS, CODES[0], p=Fraction(1, 5))]
    frozen = _frozen(rows)
    found = summarize(scores_csv(frozen, _Read({**_days(DEAL), **_days(EXPRESS)},
                                               [_one(CODES[0]), _zero(CODES[0], EXPRESS)])), frozen)
    # two columns of one chain; A 0.25 and B 0.75 on both rows
    assert found.by_column == {
        DEAL: ColumnSummary(forecasts=1, scored=1, unscored=0, outcome_1=1, sq_model=D("0.0625"), sq_a=D("0.5625"),
                            sq_b=D("0.0625"), bins=_bins(b7=(1, "0.75", 1))),
        EXPRESS: ColumnSummary(forecasts=1, scored=1, unscored=0, outcome_1=0, sq_model=D("0.04"), sq_a=D("0.0625"),
                               sq_b=D("0.5625"), bins=_bins(b2=(1, "0.2", 0)))}


def test_a_summary_reads_back_as_written():
    body = summary_json(SAME_SUMMARY)
    assert read_summary(body) == SAME_SUMMARY
    assert summary_json(read_summary(body)) == body
    assert isinstance(read_summary(body), DaySummary)
    found = json.loads(body)
    assert found == {
        "day": "2026-11-30", "frozen_at": "2026-11-30T10:40:05Z", "on_time": True, "model_version": "1",
        "target_version": "1",
        "by_column": {
            DEAL: {"forecasts": 2, "scored": 2, "unscored": 0, "outcome_1": 1, "sq_model": "0.1025", "sq_a": "0.26",
                   "sq_b": "0.9225", "bins": [[0, "0", 0], [0, "0", 0], [1, "0.2", 0], [0, "0", 0], [0, "0", 0],
                                              [0, "0", 0], [0, "0", 0], [1, "0.75", 1], [0, "0", 0], [0, "0", 0]]},
            EXPRESS: {"forecasts": 1, "scored": 0, "unscored": 1, "outcome_1": 0, "sq_model": "0", "sq_a": "0",
                      "sq_b": "0", "bins": [[0, "0", 0]] * 10}}}
    # the exact sums as scored, digit for digit
    frozen, scores = _same_day()
    assert json.loads(summary_json(summarize(scores, frozen)))["by_column"][DEAL]["sq_model"] == "0.102500000000"


def test_a_summarys_time_is_written_in_utc_and_a_naive_one_refused():
    in_israel = DaySummary(day=T, frozen_at=datetime(2026, 11, 30, 12, 40, 5, tzinfo=ISRAEL), on_time=True,
                           model_version="1", target_version="1", by_column={})
    assert json.loads(summary_json(in_israel))["frozen_at"] == "2026-11-30T10:40:05Z"
    assert read_summary(summary_json(in_israel)).frozen_at == in_israel.frozen_at
    with pytest.raises(ValueError, match="time zone"):
        summary_json(DaySummary(day=T, frozen_at=datetime(2026, 11, 30, 10, 40, 5), on_time=True, model_version="1",
                                target_version="1", by_column={}))


def test_a_summarys_time_is_its_ledger_lines():
    at = datetime(2026, 11, 30, 10, 40, 5, 250_000, tzinfo=timezone.utc)   # a time with a part of a second
    frozen = _frozen([], at=at)
    written = json.loads(summary_json(summarize(scores_csv(frozen, _Read(_days(DEAL), [])), frozen)))["frozen_at"]
    assert written == "2026-11-30T10:40:05Z"                                 # to the second, as the ledger
    assert ledger(None, frozen).decode().splitlines()[1].endswith("," + written)


def test_the_summary_path():
    assert summary_path(Path("tables"), T) == Path("tables/scored/date=2026-11-30/summary.json")

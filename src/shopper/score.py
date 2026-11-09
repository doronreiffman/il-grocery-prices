"""Scoring: each frozen day's forecasts scored against their outcomes, and the day's summary (docs/shopper-site.md
F7, with its "Changed after the survey", S1, "The column" and "Where the key lives", and Calls 14 and 21; the plan's
Task 13, the first pre-flight's S9 and N17 and the second's B1).

Which days. The build of day d scores each day t whose forecasts are frozen (`basket.archive`'s `frozen_days`), that is
not scored yet (no summary in the archive: `scored_days`) and whose window has closed, t at most d - 14 (HORIZON):
day t + 14's tables exist by then, so the outcomes are known (Call 14). Scoring needs no clock, so a day whose build
did not run is scored by a later one, as long as that build's read still holds the day's whole window: day t + 1 at
most READ_DAYS (90) days before the build's day, so up to the build of t + 91 (`reaches`). `due` lists those days,
oldest first. A day past that reach can no longer be scored from the build's read: `out_of_reach` lists it apart, oldest
first, for the build to report, and nothing stops; it stays without a summary, so a longer read could still score it.
A day frozen late is scored too, and its summary says it was not frozen on time: the gate counts only days frozen on
time (F6, F9).

The scores file (F7, Call 21). One file per frozen day, for every column: each row of the frozen file as it stands (its
fields `shopper.forecast.FILE_FIELDS`, the probabilities as their six-decimal strings), then SCORE_FIELDS:

- `outcome`: F1's, 1 or 0, from `shopper.forecast.outcome` over days t + 1 to t + 14 at the row's column; empty when
  the window holds more than MAX_HOLES (4) holes, a rule fixed in advance and the same for the model and both baselines;
- `holes`: the window's holes at the row's column, as `shopper.forecast` counts them (a column-day with no record, a
  promotion hole, its chain's table missing, a day not read): a hole is the column's own (S1, the second pre-flight's
  B1), so another column's, in the same chain, is none here;
- `first_day` and `promotion_id`: an outcome 1's evidence, the first day in the window the item was on a wide promotion
  at the column, and the smallest `PromotionID`, by number, of the wide promotions with a kind running on the item that
  day; both empty for an outcome 0 or an unscored row;
- `unscored`: why the row is unscored (UNSCORED, "more than 4 holes"), empty for a scored row;
- `evidence`: what an outcome 1's evidence holds: "day and PromotionID", or "day only" when the item's row of that day
  names no such promotion (the row keeps one link of each promotion on the item, and that link's `wide` can differ from
  the item's `on_promotion`, which reads every link: Task 6), `promotion_id` then empty; empty for an outcome 0 or an
  unscored row.

The rows keep the frozen file's order (by column, then barcode); the CSV is gzipped with no time in its header, so the
same rows give the same bytes. It goes to `scores/date=<t>/scores.csv.gz` in the archive, once and locked
(`shopper.freeze.ArchiveFreezer.put_scores`), and with the archive's bytes to `scores/<t>.csv.gz` on the site. A row's
pair is the history's for its column and barcode; an item the history holds no row of at all (no longer listed) is
scored on its column's days alone, its outcome 0 unless the window holds more than 4 holes. The build reads the pairs
from the window's tables alone (`window_history`: those of t + 1 to t + 14, the only days `outcome` reads, every
column-day kept), so the same file comes from 14 of the 91 days' rows (the plan's Task 25a). The history must hold the
whole window: day t + 14 at most the history's day (else the outcome is not known yet, and `outcome` would read the days
not yet there as holes) and day t + 1 at most READ_DAYS (90) days before it (`reaches`; else the window was not read): a
ValueError otherwise, since a scores file is never rewritten; `due` never lists such a day. The target is version 1's
(TARGET_VERSION): a frozen file naming another is refused, since its outcome would be another target's.

The summary. Per day and per column (S1), its counts and sums from the published scores file alone, so anyone holding it
can recompute them: the forecasts, the scored, the unscored, the scored with outcome 1, the sums of (p - outcome)² over
the scored rows for the model, A and B, and the calibration's ten bins of width 0.1 by the model's probability (F8):
[0, 0.1), [0.1, 0.2), ..., [0.9, 1], 1 in the last, each with its count of scored rows, their sum of p and their
outcomes 1. A row is scored or not by its outcome alone, and a scored row scores all three, so the model and both
baselines are summed over exactly the same rows (F5, F7). The probabilities are the file's six-decimal strings read as
`Decimal`; a square has twelve decimals, and a day's sums stay far inside `Decimal`'s 28 digits, so no sum is rounded.
With the day, the frozen file's S3 time and whether that was on time (the ledger's line has the time)
and the rows' model and target versions (one of each a day, else a ValueError; an empty day has neither, ""), it is a
`DaySummary`: the record (Task 14) reads only these, never the files. A scores file is summarized only beside the frozen
file it was made from: its rows must begin with that file's rows (a ValueError else).

`summary_json` writes a summary for `tables/scored/date=<t>/summary.json` (`summary_path` under the work folder's
tables; plain and derived like every table, the same file again from the same scores file): the sums as exact decimal
text, the time as the ledger's line writes it (`shopper.freeze.utc_text`: UTC to the second, with a Z), so a summary's
time is its day's ledger time. `read_summary` reads it back as written.
"""
import csv
import gzip
import io
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from shopper.forecast import FILE_FIELDS, MAX_HOLES, TARGET_VERSION, Outcome, outcome
from shopper.freeze import Frozen, utc_text
from shopper.history import READ_DAYS, History, Pair
from shopper.items import HORIZON

SCORE_FIELDS = ("outcome", "holes", "first_day", "promotion_id", "unscored", "evidence")
UNSCORED = f"more than {MAX_HOLES} holes"   # why a row is unscored (F7)
BINS = 10                                    # the calibration's bins of width 0.1 (F8)
_P, _A, _B = (FILE_FIELDS.index(name) for name in ("p_model", "p_a", "p_b"))
_MODEL, _TARGET = FILE_FIELDS.index("model_version"), FILE_FIELDS.index("target_version")
_OUTCOME = len(FILE_FIELDS)                  # a scores row's first cell after the frozen row's


@dataclass(frozen=True)
class ColumnSummary:
    """A column's day: its forecasts, scored and unscored, the scored with outcome 1, the sums of (p - outcome)² over
    the scored for the model, A and B, and ten bins by the model's p, each (count, sum of p, outcomes 1)."""
    forecasts: int
    scored: int
    unscored: int
    outcome_1: int
    sq_model: Decimal
    sq_a: Decimal
    sq_b: Decimal
    bins: tuple[tuple[int, Decimal, int], ...]


@dataclass(frozen=True)
class DaySummary:
    """A frozen day's scoring: its frozen file's S3 time and whether that was on time, the versions, and each column's
    summary."""
    day: date
    frozen_at: datetime
    on_time: bool
    model_version: str
    target_version: str
    by_column: dict[str, ColumnSummary]


def reaches(t: date, day: date) -> bool:
    """Whether the build of `day` reads day t's window from its first day: t + 1 at most READ_DAYS before the day."""
    return t + timedelta(days=1) >= day - timedelta(days=READ_DAYS)


def _closed(frozen_days: Iterable[date], scored_days: Iterable[date], day: date) -> list[date]:
    """The frozen days not scored whose window has closed by `day` (t at most day - 14), oldest first."""
    scored = set(scored_days)
    last = day - timedelta(days=HORIZON)
    return sorted(t for t in set(frozen_days) if t <= last and t not in scored)


def due(frozen_days: Iterable[date], scored_days: Iterable[date], day: date) -> list[date]:
    """The frozen days the build of `day` scores (the module's docstring): t at most day - 14, not scored, its window
    within the build's read; oldest first."""
    return [t for t in _closed(frozen_days, scored_days, day) if reaches(t, day)]


def out_of_reach(frozen_days: Iterable[date], scored_days: Iterable[date], day: date) -> list[date]:
    """The frozen days not scored whose window has closed but begins before the build of `day`'s read: never scored
    by this build, to be reported (the module's docstring); oldest first."""
    return [t for t in _closed(frozen_days, scored_days, day) if not reaches(t, day)]


def summary_path(tables_dir: Path, day: date) -> Path:
    """scored/date=<day>/summary.json under `tables_dir`."""
    return tables_dir / "scored" / f"date={day.isoformat()}" / "summary.json"


def _read(body: bytes, fields: Sequence[str]) -> list[list[str]]:
    """The rows of a gzipped CSV whose header is `fields`; a ValueError for another header."""
    header, *rows = csv.reader(io.StringIO(gzip.decompress(body).decode()))
    if tuple(header) != tuple(fields):
        raise ValueError(f"a file with the fields {header}, not {list(fields)}")
    return rows


def _cells(result: Outcome) -> tuple:
    """A row's SCORE_FIELDS from its outcome."""
    if result.value is None:
        return "", result.holes, "", "", UNSCORED, ""
    if result.value == 0:
        return 0, result.holes, "", "", "", ""
    evidence = "day only" if result.promotion_id is None else "day and PromotionID"
    return 1, result.holes, result.first_day.isoformat(), result.promotion_id or "", "", evidence


def window_history(history: History, t: date) -> History:
    """The history with only its items tables of t + 1 to t + HORIZON, the days `outcome` reads for day t, and every
    column-day (the module's docstring): `scores_csv` gives day t's file from it as from the whole read."""
    last = t + timedelta(days=HORIZON)
    return History(history.day, history.column_days,
                   {path: seen for path, seen in history.tables.items() if t < seen <= last})


def scores_csv(frozen: Frozen, history: History) -> bytes:
    """The scores file of the frozen day (the module's docstring), from the history of the build that scores it."""
    day = frozen.day
    last = day + timedelta(days=HORIZON)
    if last > history.day:
        raise ValueError(f"the forecasts of {day.isoformat()} cannot be scored on {history.day.isoformat()}: "
                         f"their window ends on {last.isoformat()}")
    if not reaches(day, history.day):
        raise ValueError(f"the forecasts of {day.isoformat()} cannot be scored on {history.day.isoformat()}: "
                         f"their window starts before the {READ_DAYS} days read")
    rows = _read(frozen.body, FILE_FIELDS)
    targets = {row[_TARGET] for row in rows}
    if targets - {TARGET_VERSION}:
        raise ValueError(f"the forecasts of {day.isoformat()} name target version {sorted(targets)}; this code scores "
                         f"target version {TARGET_VERSION} only")
    wanted = {(row[0], row[1]) for row in rows}
    column_days = history.column_days
    results = {(pair.column, pair.code): outcome(pair, column_days, day)
               for pair in history.pairs() if (pair.column, pair.code) in wanted}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow((*FILE_FIELDS, *SCORE_FIELDS))
    for row in rows:
        key = (row[0], row[1])
        result = results[key] if key in results else outcome(Pair(column=key[0], code=key[1], points={}),
                                                              column_days, day)
        writer.writerow((*row, *_cells(result)))
    return gzip.compress(out.getvalue().encode(), mtime=0)


class _Tally:
    """A column's day as it is summed."""

    def __init__(self) -> None:
        self.forecasts = self.scored = self.unscored = self.outcome_1 = 0
        self.sq_model = self.sq_a = self.sq_b = Decimal(0)
        self.bins = [(0, Decimal(0), 0)] * BINS

    def add(self, value: int, p: Decimal, a: Decimal, b: Decimal) -> None:
        """A scored row: its outcome and the model's, A's and B's probabilities."""
        self.scored += 1
        self.outcome_1 += value
        self.sq_model += (p - value) ** 2
        self.sq_a += (a - value) ** 2
        self.sq_b += (b - value) ** 2
        tenth = min(int(p * BINS), BINS - 1)   # [0, 0.1) to [0.9, 1]: 1 in the last
        count, total, ones = self.bins[tenth]
        self.bins[tenth] = (count + 1, total + p, ones + value)

    def summary(self) -> ColumnSummary:
        return ColumnSummary(forecasts=self.forecasts, scored=self.scored, unscored=self.unscored,
                             outcome_1=self.outcome_1, sq_model=self.sq_model, sq_a=self.sq_a, sq_b=self.sq_b,
                             bins=tuple(self.bins))


def summarize(scores: bytes, frozen: Frozen) -> DaySummary:
    """The day's summary (the module's docstring), from its scores file and the frozen file it was made from."""
    rows = _read(scores, (*FILE_FIELDS, *SCORE_FIELDS))
    if [row[:_OUTCOME] for row in rows] != _read(frozen.body, FILE_FIELDS):
        raise ValueError(f"the scores file is not of the forecasts frozen on {frozen.day.isoformat()}: its rows differ")
    versions = {(row[_MODEL], row[_TARGET]) for row in rows}
    if len(versions) > 1:
        raise ValueError(f"the forecasts of {frozen.day.isoformat()} name more than one version: {sorted(versions)}")
    model_version, target_version = versions.pop() if versions else ("", "")
    tallies: dict[str, _Tally] = {}
    for row in rows:
        tally = tallies.setdefault(row[0], _Tally())   # each column apart (S1)
        tally.forecasts += 1
        if row[_OUTCOME] == "":   # unscored: no outcome, so none of the three is scored
            tally.unscored += 1
            continue
        tally.add(int(row[_OUTCOME]), Decimal(row[_P]), Decimal(row[_A]), Decimal(row[_B]))
    return DaySummary(day=frozen.day, frozen_at=frozen.frozen_at, on_time=frozen.on_time, model_version=model_version,
                      target_version=target_version,
                      by_column={column: tally.summary() for column, tally in sorted(tallies.items())})


def summary_json(summary: DaySummary) -> bytes:
    """The summary file (the module's docstring)."""
    columns = {column: {"forecasts": found.forecasts, "scored": found.scored, "unscored": found.unscored,
                        "outcome_1": found.outcome_1, "sq_model": format(found.sq_model, "f"),
                        "sq_a": format(found.sq_a, "f"), "sq_b": format(found.sq_b, "f"),
                        "bins": [[count, format(total, "f"), ones] for count, total, ones in found.bins]}
               for column, found in summary.by_column.items()}
    return json.dumps({"day": summary.day.isoformat(), "frozen_at": utc_text(summary.frozen_at),
                       "on_time": summary.on_time, "model_version": summary.model_version,
                       "target_version": summary.target_version, "by_column": columns},
                      sort_keys=True, indent=1).encode()


def read_summary(body: bytes) -> DaySummary:
    """A summary file read back (summary_json's inverse)."""
    found = json.loads(body)
    by_column = {column: ColumnSummary(forecasts=held["forecasts"], scored=held["scored"], unscored=held["unscored"],
                                       outcome_1=held["outcome_1"], sq_model=Decimal(held["sq_model"]),
                                       sq_a=Decimal(held["sq_a"]), sq_b=Decimal(held["sq_b"]),
                                       bins=tuple((count, Decimal(total), ones) for count, total, ones in held["bins"]))
                 for column, held in found["by_column"].items()}
    return DaySummary(day=date.fromisoformat(found["day"]), frozen_at=datetime.fromisoformat(found["frozen_at"]),
                      on_time=found["on_time"], model_version=found["model_version"],
                      target_version=found["target_version"], by_column=by_column)

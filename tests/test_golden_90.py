"""The golden 90 days end to end (docs/shopper-site.md, "Testing"; the plan's Task 25): the history of
tests/shopper_golden.py, 1 January to 30 April 2026 at the five chains with Shufersal and Carrefour each a chain of two
formats, built a day at a time through the real code, once a module (the plan's "Deviations" give the time). The
expected values are worked by hand in tests/shopper_golden.py's docstring, which names each one.

The run is the site run's: `build_site` for every day from the first forecast day (30 January) to 30 April at 12:33
Israel time, freezing and scoring through the archive's freezer over a MemoryArchive whose S3 clock gives the run's
time and 7 seconds, every build given the same code fingerprint and run ids ending 0000 (`fixed_provenance`). The
module's run is made with the process's zone set to Asia/Jerusalem; the determinism test, the last one here, runs the
same days again in a process of its own under TZ=UTC.

The outputs are pinned (tests/golden/golden-90.sha256, `shopper_golden.manifest`): each built day's written files, and
every file the run leaves on the site and in the scoring summaries, so a change that moves any byte of them fails here
(the plan's Task 25a proves its speed-ups by it). A change meant to move them pins them anew:
`GOLDEN_90_REPIN=1 $PY -m pytest tests/test_golden_90.py -k pinned`, the reason in its commit.
"""
import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from html import unescape
from pathlib import Path

import pytest

from basket.archive import MemoryArchive
from basket.chains import SLUGS
from shopper.columns import COLUMNS
from shopper.forecast import forecasts
from shopper.freeze import cutoff
from shopper.history import load
from shopper.record import gate
from shopper.score import read_summary
from shopper_golden import (DAYS, F3_DAY, FINGERPRINT, G1, G2, G3, G4, G5, G6, build_day, day_of, exact_digests,
                            fixed_provenance, manifest, run)

TESTS = Path(__file__).parent
ROOT = TESTS.parent
PIN = TESTS / "golden" / "golden-90.sha256"
OTHER_RUN_SECONDS = 1800      # the second run's limit: it takes as long as the module's own, about 4 minutes


@contextmanager
def zone(name: str):
    """The process's local time zone set to `name` while inside (`time.tzset`), then back."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = old
        time.tzset()


@pytest.fixture(scope="module")
def golden(tmp_path_factory):
    """The module's run, made with the process's zone set to Asia/Jerusalem."""
    with zone("Asia/Jerusalem"):
        return run(tmp_path_factory.mktemp("golden-90") / "run")


def _text(markup: str) -> str:
    """Markup as its words: tags dropped, entities read, spaces collapsed."""
    return " ".join(unescape(re.sub(r"<[^>]+>", "", markup)).split())


def _section(page: str, column: str) -> str:
    """A column's section of a page, its chart left out."""
    found = re.search(rf'<section data-column="{column}"[^>]*>.*?</section>', page, re.S)
    assert found, column
    return re.sub(r"<svg.*?</svg>", "", found.group(0), flags=re.S)


def _front_rows(page: str) -> list[tuple[str, str]]:
    """The front page's rows: each one's column and its cells' words."""
    return [(column, _text(cells)) for column, cells in re.findall(r'<tr data-column="([^"]+)"[^>]*>(.*?)</tr>', page)]


def _csv(body: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(gzip.decompress(body).decode())))


def _rows(golden, kind: str, n: int) -> dict[tuple[str, str], dict]:
    """Day n's forecasts or scores file as published, its rows by (column, barcode)."""
    rows = _csv((golden.site / kind / f"{day_of(n).isoformat()}.csv.gz").read_bytes())
    return {(row["column"], row["barcode"]): row for row in rows}


def _summaries(golden) -> list:
    return [read_summary(path.read_bytes())
            for path in sorted((golden.data / "tables" / "scored").glob("date=*/summary.json"))]


# ---- the pages: P7 and the front page, P8's runs, the windows and the holes ----

G3_STORY = ("Deal price ₪7.90: ₪3.50, 31%, below the 30-day median listed price of ₪11.40 (of the 30 days with records "
            "before today).",
            "The lowest listed price was ₪10.90 in the 30 days before today and ₪10.90 on the 74 days with records of "
            "the 90 before today; listed at ₪7.90 or less on 0 of the 74.",
            "The listed price rose from ₪10.90 to ₪11.90 on 1 March 2026.")
RUNS = ("from 30 January 2026 or earlier to 1 February 2026; 16 to 22 February 2026; 9 to 15 March 2026; 30 March to "
        "5 April 2026; 20 to 26 April 2026.")


def test_the_golden_pages_windows_and_gaps(golden):
    # G3 on 16 March (day 75), its 7.90 promotion's first day: Sheli's P7 against Sheli's own 30-day median, and the
    # front page's one row, Sheli's; Deal lists G3 at 9.90 with no promotion and has no row
    index = golden.page(75, "index.html")
    assert [column for column, _ in _front_rows(index)] == ["shufersal-sheli"]
    (_, row), = _front_rows(index)
    assert "Deal price ₪7.90 per unit" in row and "₪11.40" in row and "31%" in row
    assert " ".join(G3_STORY) in _text(index)
    assert ("Today the five chains list 1 promotion across a store format on 1 product; 1 of them is below every "
            "listed price of the past 90 days in their store format, on an item with at least 20 days of records "
            "there in the past 30.") in _text(index)
    page = golden.page(75, f"p/{G3}.html")
    sheli, deal = _text(_section(page, "shufersal-sheli")), _text(_section(page, "shufersal-deal"))
    assert " ".join(G3_STORY[:2]) in sheli and G3_STORY[2] in sheli
    assert "Listed price ₪9.90, before promotions" in deal and "Deal price" not in deal
    # G1's runs, gaps and days since on the last day (30 April): at Osher Ad, a whole chain with a record every day; at
    # Deal, whose holes of 19 and 20 February sit inside a run and break none; at Rami Levy, whose holes of 9 and 10
    # February sit between two runs, where a one-day run could hide
    page = golden.page(DAYS, f"p/{G1}.html")
    assert (f"On a promotion listed across Osher Ad on 31 of the 90 days with records before today, as listed in the "
            f"morning's files. Runs before today: {RUNS} Days between runs: 14; 14; 14; 14. The last run ended on 26 "
            "April 2026, 4 days ago.") in _text(_section(page, "osherad"))
    assert (f"On a promotion listed across Shufersal Deal on 29 of the 88 days with records before today, as listed in "
            f"the morning's files. Runs before today: {RUNS} Days between runs: 14; 14; 14; 14. The last run ended on "
            "26 April 2026, 4 days ago.") in _text(_section(page, "shufersal-deal"))
    rami = _text(_section(page, "ramilevy"))
    assert (f"On a promotion listed across Rami Levy on 31 of the 88 days with records before today, as listed in the "
            f"morning's files. Runs seen before today: {RUNS} Days between runs: at most 14; 14; 14; 14.") in rami
    assert "The listed price did not change on the 88 days with records of the 90 before today." in rami
    # G4 at Rami Levy alone, weighed: "2 for ₪100" stored as 1.5 for ₪75.00, ₪50.00 a kilogram; its chain's holes of 9
    # and 10 February skipped in every window
    index = golden.page(85, "index.html")
    assert [column for column, _ in _front_rows(index)] == ["shufersal-sheli", "ramilevy"]   # by depth: 34%, then 28%
    rami = dict(_front_rows(index))["ramilevy"]
    assert "Deal price ₪50.00 per kilogram, buy 1.5" in rami and "₪69.90" in rami and "28%" in rami
    section = _text(_section(golden.page(85, f"p/{G4}.html"), "ramilevy"))
    assert ("Deal price ₪50.00: ₪19.90, 28%, below the 30-day median listed price of ₪69.90 (of the 30 days with "
            "records before today). The lowest listed price was ₪69.90 in the 30 days before today and ₪69.90 on the "
            "82 days with records of the 90 before today; listed at ₪50.00 or less on 0 of the 82.") in section
    section = _text(_section(golden.page(DAYS, f"p/{G4}.html"), "ramilevy"))
    assert ("On a promotion listed across Rami Levy on 14 of the 88 days with records before today, as listed in the "
            "morning's files. Run seen before today: 26 March to 8 April 2026. The last run ended on 8 April 2026, 22 "
            "days ago.") in section
    # G5 on 9 April (day 99): on promotion at Deal alone, carried by store 21 alone that day, half Deal's two counted
    # stores, so listed across Deal; at ₪4.50, Deal's 90-day low, it is not below every listed price and has no front row
    page = golden.page(99, f"p/{G5}.html")
    deal, sheli = _text(_section(page, "shufersal-deal")), _text(_section(page, "shufersal-sheli"))
    assert "Deal price ₪4.50 per unit" in deal and "at some stores" not in deal
    assert ("Deal price ₪4.50: ₪1.50, 25%, below the 30-day median listed price of ₪6.00 (of the 30 days with records "
            "before today). The lowest listed price was ₪6.00 in the 30 days before today and ₪4.50 on the 88 days "
            "with records of the 90 before today; listed at ₪4.50 or less on 15 of the 88.") in deal
    assert "Deal price" not in sheli and "No promotion listed across Shufersal Sheli" in sheli
    assert [column for column, _ in _front_rows(golden.page(99, "index.html"))] == ["shufersal-sheli"]   # G3's alone
    # Deal's holes of 19 and 20 February (days 50 and 51): Deal's files missing, Sheli's and Yesh Chesed's there. On 19
    # February every column with a record has its G1 row, Deal none; G1's Deal section has too few files and no price
    index = golden.page(50, "index.html")
    assert [column for column, _ in _front_rows(index)] == [
        "carrefour-city", "carrefour-market", "osherad", "ramilevy", "shufersal-sheli", "yochananof"]
    page = golden.page(50, f"p/{G1}.html")
    assert "too few files today: 0 of 2 stores" in _text(_section(page, "shufersal-deal"))
    assert "Listed price" not in _text(_section(page, "shufersal-deal"))
    assert "Listed price ₪5.00, before promotions" in _text(_section(page, "shufersal-sheli"))
    for n in (50, 51):
        columns = json.loads((golden.site / "site-days" / f"{day_of(n).isoformat()}.json").read_text())["columns"]
        assert {key: (columns[key]["record"], columns[key]["hole"], columns[key]["with_file"])
                for key in ("shufersal-deal", "shufersal-sheli")} == {
            "shufersal-deal": (False, True, 0), "shufersal-sheli": (True, False, 2)}
    days = re.search(r'<table class="days">.*?</table>', (golden.site / "record.html").read_text(), re.S).group(0)
    shown = {name: cells for name, cells in
             ((_text(head), [_text(cell) for cell in re.findall(r"<td>(.*?)</td>", cells)])
              for head, cells in re.findall(r'<tr><th scope="row">(.*?)</th>(.*?)</tr>', days))}
    assert shown["Shufersal Deal"] == ["89", "19 to 20 February 2026", "none", "none"]
    assert shown["Rami Levy"] == ["89", "9 to 10 February 2026", "none", "none"]
    assert shown["Shufersal Sheli"] == ["91", "none", "none", "none"]
    assert shown["Shufersal Express"] == ["0", "30 January to 30 April 2026", "none", "none"]   # no store: a hole


# ---- the forecasts, the baselines and the scores, by hand ----

def _forecast(p, a, b, says, since, n, origin):
    return {"p_model": p, "p_a": a, "p_b": b, "b_says": says, "days_since": since, "n": n, "a_from": origin}


FIELDS = ("p_model", "p_a", "p_b", "b_says", "days_since", "n", "a_from")
ALONE = ("carrefour-city", "carrefour-market", "osherad", "yochananof")   # G1, G2 and G6 each, no hole


def test_the_golden_forecasts_baselines_and_scores(golden):
    # forecasts start on a column's 30th day of records: none on 29 January, 19 rows on 30 January
    tables = golden.data / "tables"
    assert forecasts(load(tables, day_of(29), SLUGS), day_of(29)) == []
    first = _rows(golden, "forecasts", 30)
    assert len(first) == 19 and (("osherad", G1) not in first)     # G1 on its promotion that day: no forecast
    assert {key[0] for key in first} == {*ALONE, "ramilevy", "shufersal-sheli", "shufersal-deal"}
    for column in ALONE:     # A and B from the column: G2 has 16 closed days, under 20
        assert {field: first[(column, G2)][field] for field in FIELDS} == _forecast(
            "0.148816", "0.219512", "0.219512", "0", "", "16", "column")
    # 1 March (day 60), every column's rows
    rows = _rows(golden, "forecasts", 60)
    expected = {}
    for column in ALONE:
        expected[(column, G1)] = _forecast("1.000000", "1.000000", "1.000000", "1", "7", "32", "pair")
        for code in (G2, G6):
            expected[(column, code)] = _forecast("0.016447", "0.000000", "0.163636", "0", "", "46", "pair")
    expected[("ramilevy", G1)] = _forecast("1.000000", "1.000000", "1.000000", "1", "7", "30", "pair")
    for code in (G2, G4, G6):
        expected[("ramilevy", code)] = _forecast("0.011924", "0.000000", "0.120000", "0", "", "44", "pair")
    for column in ("shufersal-sheli", "shufersal-deal"):
        expected[(column, G1)] = _forecast("1.000000", "1.000000", "1.000000", "1", "7", "32", "pair")
        for code in (G2, G3, G5, G6):
            expected[(column, code)] = _forecast("0.008399", "0.000000", "0.089109", "0", "", "46", "pair")
    assert {key: {field: row[field] for field in FIELDS} for key, row in rows.items()} == expected
    assert {(row["model_version"], row["target_version"], row["n0"], row["code_sha"]) for row in rows.values()} == {
        ("1", "1", "30", FINGERPRINT)}     # Call 19: the golden forecasts pinned to the version name
    scores = _rows(golden, "scores", 60)
    for key, row in scores.items():
        if key[1] == G1:
            assert (row["outcome"], row["holes"], row["first_day"], row["promotion_id"], row["evidence"]) == (
                "1", "0", "2026-03-09", "13", "day and PromotionID")
        else:
            assert (row["outcome"], row["holes"], row["first_day"], row["unscored"]) == ("0", "0", "", "")
    summary = json.loads((tables / "scored" / "date=2026-03-01" / "summary.json").read_text())["by_column"]
    assert summary["carrefour-city"] == {
        "forecasts": 3, "scored": 3, "unscored": 0, "outcome_1": 1, "sq_model": "0.000541007618",
        "sq_a": "0", "sq_b": "0.053553480992",
        "bins": [[2, "0.032894", 0], *([[0, "0", 0]] * 8), [1, "1.000000", 1]]}
    # 15 March (day 74): G3 at Sheli, its last day before the promotion of 16 March, outcome 1 on that day
    row = _rows(golden, "scores", 74)[("shufersal-sheli", G3)]
    assert {field: row[field] for field in FIELDS} == _forecast("0.005464", "0.000000", "0.069767", "0", "", "60",
                                                                "pair")
    assert (row["outcome"], row["first_day"], row["promotion_id"]) == ("1", "2026-03-16", "30")
    assert _rows(golden, "scores", 74)[("shufersal-deal", G3)]["outcome"] == "0"      # Deal's G3: no promotion
    # 16 March (day 75) at Sheli: G3 on promotion, no forecast; the others learn from G3's closed day 61, outcome 1
    rows = {key: row for key, row in _rows(golden, "forecasts", 75).items() if key[0] == "shufersal-sheli"}
    assert {key[1]: {field: row[field] for field in FIELDS} for key, row in rows.items()} == {
        G1: _forecast("1.000000", "1.000000", "1.000000", "1", "1", "40", "pair"),
        **{code: _forecast("0.006647", "0.000000", "0.072519", "0", "", "61", "pair") for code in (G2, G5, G6)}}
    # 31 March (day 90): G5 at Deal, outcome 1 on 9 April, when store 21 alone carries it; at Sheli, outcome 0
    scores = _rows(golden, "scores", 90)
    row = scores[("shufersal-deal", G5)]
    assert {field: row[field] for field in FIELDS} == _forecast("0.003846", "0.000000", "0.057325", "0", "", "74",
                                                                "pair")
    assert (row["outcome"], row["first_day"], row["promotion_id"]) == ("1", "2026-04-09", "50")
    assert scores[("shufersal-sheli", G5)]["outcome"] == "0"
    # a price hole is an outcome hole (B1): Deal's 19 and 20 February in the window of 9 February, Rami Levy's 9 and
    # 10 February in that of 30 January; and no forecast on a hole (Rami Levy on 9 February, Deal on 19 February)
    assert {row["holes"] for key, row in _rows(golden, "scores", 40).items() if key[0] == "shufersal-deal"} == {"2"}
    assert {row["holes"] for key, row in _rows(golden, "scores", 40).items() if key[0] == "shufersal-sheli"} == {"0"}
    assert {row["holes"] for key, row in _rows(golden, "scores", 30).items() if key[0] == "ramilevy"} == {"2"}
    assert not any(key[0] == "ramilevy" for key in _rows(golden, "forecasts", 40))
    assert not any(key[0] == "shufersal-deal" for key in _rows(golden, "forecasts", 50))
    # the scored days: 30 January to 16 April, each day's file scored on its fourteenth day after
    assert [day for day, outcome in golden.outcomes.items() if outcome.scored] == [
        day_of(n) for n in range(44, DAYS + 1)]
    assert [outcome.scored for outcome in golden.outcomes.values() if outcome.scored][0] == [day_of(30)]


# ---- the record page: its intervals and calibration recomputed from the published files ----

def _decimal(value: Fraction, places: int) -> Decimal:
    """Half away from zero, as the record's numbers are given."""
    scaled = math.floor(abs(value) * 10 ** places + Fraction(1, 2))
    return Decimal(-scaled if value < 0 else scaled).scaleb(-places)


def _four(value: Decimal | None, places: int = 4) -> str:
    """As the page shows a record's number: its 12-place figure to `places`, half up; "none" for none."""
    if value is None:
        return "none"
    return str(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def _quantile(ordered: list[float], q: Fraction) -> float:
    position = q * (len(ordered) - 1)
    below = math.floor(position)
    return ordered[below] + (ordered[below + 1] - ordered[below]) * float(position - below)


def _resampled(days: list[tuple[Fraction, Fraction, Fraction]], seed: int, block: int, draws: int, level: int) -> dict:
    """The moving-block bootstrap as the record page says it is drawn: each draw as many blocks of `block` days as
    cover the days, each block's start floor(random() x the starts), joined and cut to the days."""
    n, rng = len(days), random.Random(seed)
    starts, blocks = n - block + 1, -(-n // block)
    values = [(float(m), float(a), float(b), float(m - a), float(m - b)) for m, a, b in days]
    found = {"model_minus_a": [], "model_minus_b": [], "skill_a": [], "skill_b": []}
    undefined = set()
    for _ in range(draws):
        picked = [math.floor(rng.random() * starts) for _ in range(blocks)]
        series = [values[start + i] for start in picked for i in range(block)][:n]
        m, a, b, minus_a, minus_b = (sum(day[i] for day in series) for i in range(5))
        found["model_minus_a"].append(minus_a / n)
        found["model_minus_b"].append(minus_b / n)
        for name, baseline in (("skill_a", a), ("skill_b", b)):
            if baseline == 0:
                undefined.add(name)
            else:
                found[name].append(1 - m / baseline)
    low, high = Fraction(100 - level, 200), Fraction(100 + level, 200)
    return {name: None if name in undefined else (_quantile(sorted(draws_), low), _quantile(sorted(draws_), high))
            for name, draws_ in found.items()}


def _cell(value: str, spans: dict | None | str, name: str, level: int) -> tuple[str, str]:
    if spans == "too few":
        return value, "too few days"
    span = spans[name]
    return value, "no interval" if span is None else f"{level}%: {span[0]:.4f} to {span[1]:.4f}"


def _period_rows(days: list, seed: int, block: int, draws: int, level: int, least: int) -> list[tuple[str, str]]:
    """A scores row's seven cells (each its figure and its note) over the days' (model, A, B) Brier scores."""
    count = len(days)
    model, a, b = (_decimal(sum(day[i] for day in days) / count, 12) for i in range(3))
    exact = [sum(day[i] for day in days) / count for i in range(3)]
    skills = [None if baseline == 0 else _decimal(1 - exact[0] / baseline, 12) for baseline in exact[1:]]
    spans = "too few" if count < least else _resampled(days, seed, block, draws, level)
    return [(_four(model), ""), (_four(a), ""), (_four(b), ""),
            _cell(_four(model - a), spans, "model_minus_a", level), _cell(_four(model - b), spans, "model_minus_b", level),
            _cell(_four(skills[0]), spans, "skill_a", level), _cell(_four(skills[1]), spans, "skill_b", level)]


def _counts(rows_by_day: dict, days: list[date]) -> list[tuple[str, str]]:
    """A counts row's cells over the days: on time and late, with a scored row, the forecasts, the scored, the
    unscored, and the outcome-1 share as a whole percent, half up."""
    rows = [row for day in days for row in rows_by_day[day]]
    scored = [row for row in rows if row[3] is not None]
    share = _decimal(Fraction(sum(row[3] for row in scored), len(scored)), 12) * 100
    cells = (len(days), 0, sum(1 for day in days if any(row[3] is not None for row in rows_by_day[day])),
             f"{len(rows):,}", f"{len(scored):,}", f"{len(rows) - len(scored):,}",
             f"{share.quantize(Decimal(1), rounding=ROUND_HALF_UP)}%")
    return [(str(cell), "") for cell in cells]


def _page_rows(section: str, table: str) -> dict[str, list[tuple[str, str]]]:
    """A section's scores or counts table, by period: each cell's figure and its note."""
    found = re.search(rf'<table class="{table}">.*?</table>', section, re.S).group(0)
    rows = {}
    for period, cells in re.findall(r'<tr><th scope="row">(.*?)</th>(.*?)</tr>', found):
        parsed = [re.fullmatch(r"([^<]*)(?:<small>(.*)</small>)?", cell).groups()
                  for cell in re.findall(r"<td>(.*?)</td>", cells)]
        rows[period] = [(value, note or "") for value, note in parsed]
    return rows


def test_the_golden_intervals_and_calibration(golden):
    record = (golden.site / "record.html").read_text(encoding="utf-8")
    seed, block, draws, level, least = _printed(record)
    ledger = {}
    for line in (golden.site / "forecasts" / "ledger.csv").read_text().splitlines()[1:]:
        day, _, at = line.split(",")
        ledger[date.fromisoformat(day)] = datetime.fromisoformat(at)
    files = sorted((golden.site / "scores").glob("*.csv.gz"))
    assert len(files) == 77
    # each column's rows by day, each its p, A, B and outcome (None when unscored)
    by_column: dict[str, dict[date, list[tuple[Fraction, Fraction, Fraction, int | None]]]] = {}
    for path in files:
        day = date.fromisoformat(path.name.removesuffix(".csv.gz"))
        assert ledger[day] < cutoff(day)          # every day frozen on time, so every one counts
        for row in _csv(path.read_bytes()):
            by_column.setdefault(row["column"], {}).setdefault(day, []).append(
                (Fraction(row["p_model"]), Fraction(row["p_a"]), Fraction(row["p_b"]),
                 None if row["outcome"] == "" else int(row["outcome"])))
    assert set(by_column) == {*ALONE, "ramilevy", "shufersal-sheli", "shufersal-deal"}
    for column in COLUMNS:
        section = _section(record, column.key)
        if column.key not in by_column:
            assert "No forecast of this column has been scored yet." in section
            continue
        held = {day: [row for row in rows if row[3] is not None] for day, rows in by_column[column.key].items()}
        daily = {day: tuple(sum((row[i] - row[3]) ** 2 for row in rows) / len(rows) for i in range(3))
                 for day, rows in sorted(held.items()) if rows}
        months = {date.fromisoformat(month + "-01").strftime("%B %Y"): month
                  for month in sorted({day.strftime("%Y-%m") for day in held})}
        in_period = {"All": sorted(held), **{name: [day for day in sorted(held) if day.strftime("%Y-%m") == month]
                                             for name, month in months.items()}}
        assert _page_rows(section, "scores") == {
            period: _period_rows([daily[day] for day in days if day in daily], seed, block, draws, level, least)
            for period, days in in_period.items()}
        assert _page_rows(section, "counts") == {period: _counts(by_column[column.key], days)
                                                 for period, days in in_period.items()}
        rows = [row for day in sorted(held) for row in held[day]]
        bins = [[row for row in rows if min(int(row[0] * 10), 9) == index] for index in range(10)]
        shown = [(f"{len(found):,}", _four(_decimal(sum(row[0] for row in found) / len(found), 12), 3),
                  _four(_decimal(Fraction(sum(row[3] for row in found), len(found)), 12), 3)) if found
                 else ("0", "none", "none") for found in bins]
        table = re.search(r'<table class="calibration">.*?</table>', section, re.S).group(0)
        assert [tuple(_text(cell) for cell in re.findall(r"<td>(.*?)</td>", cells))
                for cells in re.findall(r"</th>(<td>.*?)</tr>", table)] == shown
        error = sum(abs(sum(row[0] for row in found) / len(found) - Fraction(sum(row[3] for row in found), len(found)))
                    * len(found) for found in bins if found) / len(rows)
        assert f"<p>Calibration error: {_four(_decimal(error, 12))}.</p>" in section


def _printed(record: str) -> tuple[int, int, int, int, int]:
    """The bootstrap's numbers as the record page prints them: the seed, the block, the draws, the level, the least
    days."""
    block, draws, seed, level, least = re.search(
        r"blocks of (\d+) scored days, ([\d,]+) draws, seed (\d+), (\d+)% intervals; none under (\d+) scored days",
        record).groups()
    return int(seed), int(block), int(draws.replace(",", "")), int(level), int(least)


# ---- the gate's conditions, each failing alone ----

def _held(summary, column: str, **fields):
    return replace(summary, by_column={**summary.by_column, column: replace(summary.by_column[column], **fields)})


def test_the_gates_conditions_each_fail_alone(golden):
    summaries = _summaries(golden)
    assert len(summaries) == 77
    # the golden's own gates on 30 April: closed at every column, its days short of 90
    card = json.loads((golden.site / "site-days" / "2026-04-30.json").read_text())["scorecard"]
    scored = {column.key: 77 for column in COLUMNS} | {"shufersal-deal": 75, "ramilevy": 75,
                                                       "shufersal-express": 0, "shufersal-universe": 0}
    for key, found in card["columns"].items():
        assert found["gate"]["open"] is False and found["gate"]["conditions"]["days"] is False
        assert found["gate"]["reasons"][0] == (f"{scored[key]} scored days of the version in force (model 1, target "
                                               "1) frozen on time; 90 needed")
    # Osher Ad's summaries edited so every condition holds: 91 days (the last 14 again, dated 17 to 30 April), A and B
    # each 0.1 a row above the model, and the bins calibrated (the outcomes 0 at 0, the outcomes 1 at 1)
    key = "osherad"
    extra = [replace(summary, day=summary.day + timedelta(days=14)) for summary in summaries[-14:]]

    def passing(summary):
        held = summary.by_column[key]
        rise = held.scored * Decimal("0.1")
        bins = ((held.scored - held.outcome_1, Decimal(0), 0), *((0, Decimal(0), 0),) * 8,
                (held.outcome_1, Decimal(held.outcome_1), held.outcome_1))
        return _held(summary, key, sq_a=held.sq_model + rise, sq_b=held.sq_model + rise, bins=bins)

    base = [passing(summary) for summary in summaries + extra]
    assert len(base) == 91
    found = gate(base, key)
    assert found.conditions == {"days": True, "brier": True, "calibration": True} and found.open is False
    assert found.reasons == ["every condition holds; the gate opens only on the owner's go, in a later version of this "
                             "site"]
    # each condition failing alone
    alone = {
        "days": base[:89],
        "brier": [_held(summary, key, sq_a=summary.by_column[key].sq_model) for summary in base],
        "calibration": [_held(summary, key, bins=((0, Decimal(0), 0),) * 5 + (
            (summary.by_column[key].scored - summary.by_column[key].outcome_1,
             Decimal("0.5") * (summary.by_column[key].scored - summary.by_column[key].outcome_1), 0),)
            + ((0, Decimal(0), 0),) * 3 + (summary.by_column[key].bins[9],)) for summary in base],
    }
    for failing, edited in alone.items():
        found = gate(edited, key)
        assert found.conditions == {name: name != failing for name in ("days", "brier", "calibration")}, failing
        assert found.open is False


# ---- the pinned bytes ----

def test_the_golden_bytes_are_pinned(golden):
    found = manifest(golden)
    if os.environ.get("GOLDEN_90_REPIN") == "1":
        PIN.write_text(found)
        pytest.skip(f"pinned anew: {PIN}")
    pinned = PIN.read_text()
    moved = sorted(set(found.splitlines()) ^ set(pinned.splitlines()), key=lambda line: line[66:])
    assert found == pinned, f"{len(moved)} lines differ from the pinned ones, the first: {moved[:12]}"
    for key, stored in golden.archive.objects.items():     # the site publishes the archive's bytes
        kind, day = key.split("/")[0], key.split("=")[1].split("/")[0]
        assert (golden.site / kind / f"{day}.csv.gz").read_bytes() == stored.body


# ---- F3: day d with and without the later days ----

def test_day_d_is_the_same_with_and_without_later_days(golden, tmp_path):
    """Day 88 (29 March) built again from the state just before its build, with every later day's raw files and
    tables there too (the prices, promotions, items and covered tables of 30 March to 30 April): the same files and
    the same frozen and scored bytes as the day's build had without them."""
    day = day_of(F3_DAY)
    for folder in ("data", "site"):
        shutil.copytree(golden.before / folder, tmp_path / folder)
    data = tmp_path / "data"
    later = 0
    for kind in ("raw", "tables/prices", "tables/promotions", "tables/items", "tables/covered"):
        for found in sorted((golden.data / kind).glob("**/date=*")):
            if date.fromisoformat(found.name.removeprefix("date=")) > day:
                shutil.copytree(found, data / found.relative_to(golden.data))
                later += 1
    assert later == 32 * 5 + 32 * 5 * 3 + 32      # 32 later days: raw and three tables a chain, and a registry each
    archive = MemoryArchive()
    archive.objects, archive.times = (dict(held) for held in golden.archive_before)
    with fixed_provenance():
        outcome = build_day(day, data, tmp_path / "site", archive, golden.root / "basket.json")
    assert {path: hashlib.sha256((tmp_path / "site" / path).read_bytes()).hexdigest()
            for path in [*outcome.data, *outcome.pages]} == {path: digests[0]
                                                            for path, digests in golden.written[day].items()}
    new = {key: stored.body for key, stored in archive.objects.items() if key not in golden.archive_before[0]}
    assert set(new) == {f"forecasts/date={day.isoformat()}/forecasts.csv.gz",
                        f"scores/date={(day - timedelta(days=14)).isoformat()}/scores.csv.gz"}
    assert all(golden.archive.objects[key].body == body for key, body in new.items())


# ---- the basket keeps each chain's median ----

def test_the_basket_keeps_the_chains_median(golden):
    """G6 is priced apart at Shufersal's formats and at Carrefour's: the basket's chain price is the median over every
    included store with a file, the store in no column's own price here, never a column's."""
    def item(n: int, slug: str) -> dict:
        public = json.loads((golden.site / "days" / f"{day_of(n).isoformat()}.json").read_text())
        return public["chains"][slug]
    shufersal = item(60, "shufersal")
    assert shufersal["items"][G6] == {"double_coded": 0, "high": "8.20", "listing": 5, "low": "7.00", "median": "7.60"}
    assert item(60, "carrefour")["items"][G6]["median"] == "8.30"
    # Deal's holes: the chain's day has 3 of its 5 stores' files, no hole, and the median of the three
    held = item(50, "shufersal")
    assert (held["in_ranking"], held["included"], held["with_file"]) == (True, 5, 3)
    assert held["items"][G6] == {"double_coded": 0, "high": "8.20", "listing": 3, "low": "7.60", "median": "8.00"}
    assert item(40, "ramilevy")["in_ranking"] is False       # Rami Levy's day of no files is the basket's hole
    # the product page shows the formats apart: Sheli's median of its two stores, Deal's of its two
    page = (golden.site / "p" / f"{G6}.html").read_text(encoding="utf-8")
    assert "Listed price ₪8.10, before promotions" in _text(_section(page, "shufersal-sheli"))
    assert "Listed price ₪7.10, before promotions" in _text(_section(page, "shufersal-deal"))
    basket = _text((golden.site / "basket.html").read_text(encoding="utf-8"))
    assert golden.outcomes[day_of(DAYS)].basket.headline_lines[0] == "Lowest listed total today: Osher Ad, ₪14.70."
    assert "Highest: Carrefour, ₪15.80, 7% more." in basket


# ---- determinism: the same days, the same bytes ----

def test_the_same_days_give_the_same_bytes(golden, tmp_path):
    """A second run of the same days (`shopper_golden.main`, in a process of its own under TZ=UTC; the module's run was
    made under Asia/Jerusalem) writes every file of every day, every frozen and scored file and every summary with the
    same bytes. Its provenance is the module's (`fixed_provenance`); no page carries a run id. It runs here, last, so a
    test that fails before it stops the module without it (the mutation check's -x)."""
    env = os.environ | {"TZ": "UTC", "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(TESTS)))}
    done = subprocess.run([sys.executable, str(TESTS / "shopper_golden.py"), str(tmp_path)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=OTHER_RUN_SECONDS)
    assert done.returncode == 0, (done.stdout + done.stderr)[-3000:]
    theirs = json.loads((tmp_path / "digests.json").read_text())
    ours = exact_digests(golden)
    assert ours["days"] == theirs["days"]
    assert ours["final"] == theirs["final"]
    assert len(ours["days"]) == 91 and len(ours["final"]) > 500
    for path in golden.site.rglob("*.html"):
        assert "Z-site-" not in path.read_text(encoding="utf-8") and "Z-basket-" not in path.read_text(encoding="utf-8")

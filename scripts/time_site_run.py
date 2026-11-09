#!/usr/bin/env python3
"""Time the site run's compute over synthetic items tables (the plan's Task 25a).

    PYTHONPATH=src python scripts/time_site_run.py --work <folder> [--make [--scale 1.0] [--days 91]] [--bare]
                                                   [--profile N]

`--make` writes the tables first, under <folder>/tables (any made before are removed): `--days` days of items tables
for every chain, ending on DAY, each column at `--scale` times the items, wide and on-promotion counts of its report of
7 November 2026 (REAL; 1.0 is 131,035 rows a day), every row a pair of its own (a column's codes are distinct, drawn
from a pool of POOL codes times the scale), and the frozen forecasts file of the day scored. Names and barcodes are
synthetic: nothing from the archive is read or written. The listed price steps every 30 days; a wide item is on a
promotion 7 days in 21; no column-day is a hole.

Then the build's compute, step by step as `shopper.build.build_site` runs it and through its own functions: the
history (`load`), the covered registry, the scoring of the one due day (`build._score`, through a freezer that holds
the frozen file in memory), the scorecard over as many scored days as the days held give (copies of that day's
summary), the one pass (the forecasts, every covered product's page and the front rows: `build._Pages` and
`build._Watched`), the forecasts file, and the pages moved in with the front, browse and search pages. Each step
prints its CPU seconds (`time.process_time`: every thread of the process, DuckDB's included) and its wall seconds;
then the totals and the peak resident memory. Figures only.

On macOS each step also prints the share of its CPU time spent on the performance cores and an estimate of its CPU
seconds had it all run there: its instructions retired over the instructions a second it retired on those cores
(`proc_pid_rusage`, RUSAGE_INFO_V6). A loaded Mac moves work to the efficiency cores, where the same work takes two to
three times the CPU seconds; the estimate is what an idle Mac would show, and compares runs made under other loads.

`--bare` adds a bare pass over `History.pairs()` (the stream alone, apart from the run's total). `--profile N` adds
cProfile's top functions, by cumulative and by own time, over the pass of the first N products (by code; at least
3,000 for the plan's sample) and over the scoring of the due day.
"""
import argparse
import cProfile
import ctypes
import hashlib
import json
import math
import os
import pstats
import resource
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from basket.chains import SLUGS  # noqa: E402
from shopper import build  # noqa: E402
from shopper.columns import COLUMNS, columns_of  # noqa: E402
from shopper.forecast import FIRST_RECORD_DAY, Forecast, forecasts, forecasts_csv  # noqa: E402
from shopper.freeze import Frozen  # noqa: E402
from shopper.history import History, covered, covered_path, load  # noqa: E402
from shopper.items import COLUMNS as ITEM_COLUMNS, HORIZON, ColumnReport, ItemsReport, items_path  # noqa: E402
from shopper.pages import render_front  # noqa: E402
from shopper.record import Gate, scorecard  # noqa: E402
from shopper.score import read_summary, summary_path  # noqa: E402
from shopper.search import browse_pages, pieces  # noqa: E402

DAY = date(2026, 11, 20)
SCORED = DAY - timedelta(days=HORIZON)         # the morning's one due day
COLLECTED_BY = "12:03"
CODE_SHA = "0123456789ab"
FROZEN_AT = datetime(2026, 11, 6, 10, 33, tzinfo=timezone.utc)
# Each column's items, wide and on-promotion counts in its items report of 7 November 2026: 131,035 items a day.
REAL = {
    "carrefour-city": (16754, 6980, 4476), "carrefour-market": (17668, 8333, 4513), "osherad": (9526, 6247, 2441),
    "ramilevy": (25993, 10998, 6744), "shufersal-deal": (11774, 7686, 3641), "shufersal-express": (9826, 3347, 1567),
    "shufersal-sheli": (10723, 6145, 2942), "shufersal-universe": (11892, 9037, 4090),
    "yochananof": (16879, 10187, 3761)}
POOL = 45_000                                   # the codes the columns draw from, at scale 1 (Task 19's)
# A column's codes are the pool's indexes i x STEP mod the pool, i below its items: distinct, since each step is a
# prime above any pool, so prime to it.
STEPS = (104_729, 1_299_709, 15_485_863, 179_424_673, 2_038_074_743, 1_000_003, 10_000_019, 100_000_007,
         1_000_000_007)
MADE = "made.json"


def _scaled(count: int, scale: float) -> int:
    return max(1, round(count * scale))


def _column_rows(key: str, index: int, step: int, pool: int, counts: tuple[int, int, int], chain: int,
                 day: date) -> str:
    """The SELECT of one column's synthetic rows for a day."""
    items, wide, _ = counts
    struct = dict(ITEM_COLUMNS)["promotions"]
    n = f"((i * {step}) % {pool})"
    on = f"(i < {wide} AND ({index} + i) % 21 < 7)"
    return f"""
        SELECT '{key}' AS "column", '2' || lpad(CAST({n} AS VARCHAR), 12, '0') AS code,
               chr(CAST(1488 + {n} % 27 AS INTEGER)) || chr(CAST(1488 + ({n} // 27) % 27 AS INTEGER)) || ' '
                   || CAST({n} AS VARCHAR) || repeat(' x', {chain}) AS name,
               NULL::VARCHAR AS size_amount, NULL::VARCHAR AS size_kind,
               CAST(5 + ((i * 31) % 4000) / 100.0 + ((({index} + i) // 30) % 3) * 0.5 AS DECIMAL(13,3)) AS listed,
               CAST(5 + ((i * 31) % 4000) / 100.0 AS DECIMAL(12,2)) AS low,
               CAST(6 + ((i * 31) % 4000) / 100.0 AS DECIMAL(12,2)) AS high,
               10 AS listing, i < {wide} AS wide, {on} AS on_promotion, NULL::DATE AS next_start,
               CAST(CASE WHEN {on} THEN [struct_pack(
                   promotion_id := CAST(1000 + i % 500 AS VARCHAR), description := 'promotion',
                   "start" := DATE '{day.isoformat()}' - CAST(({index} + i) % 21 AS INTEGER),
                   "end" := DATE '{day.isoformat()}' + CAST(7 - ({index} + i) % 21 AS INTEGER),
                   kind := 'fixed_price', buy := 1::DECIMAL(12,3),
                   price := CAST(3 + ((i * 31) % 4000) / 100.0 AS DECIMAL(12,2)),
                   price_exact := CAST(300 + (i * 31) % 4000 AS VARCHAR) || '/100', per := 'unit',
                   low := NULL::DECIMAL(12,3), high := NULL::DECIMAL(12,3), valid := true, why := NULL::VARCHAR,
                   restrictions := ['club'], programmes := []::VARCHAR[], min_spend := NULL::DECIMAL(12,2),
                   stores := 10, wide := true)] ELSE [] END AS {struct}) AS promotions
        FROM range({items}) t(i)"""


def make(work: Path, scale: float, days: int) -> None:
    """The synthetic tables (the module's docstring) and the frozen file of SCORED."""
    if days <= HORIZON:
        raise SystemExit(f"--days must be above {HORIZON}: the scored day's window must be held")
    tables = work / "tables"
    shutil.rmtree(tables, ignore_errors=True)
    pool = max(round(POOL * scale), max(_scaled(counts[0], scale) for counts in REAL.values()))
    assert all(math.gcd(step, pool) == 1 for step in STEPS)
    names = ", ".join(f'"{name}"' for name, _ in ITEM_COLUMNS)
    with duckdb.connect() as con:
        for back in range(days):
            day = DAY - timedelta(days=back)
            index = (day - date(2026, 1, 1)).days
            for chain, slug in enumerate(SLUGS):
                selects, reports = [], {}
                for column in columns_of(slug):
                    position = COLUMNS.index(column)
                    counts = tuple(_scaled(count, scale) for count in REAL[column.key])
                    selects.append(_column_rows(column.key, index, STEPS[position], pool, counts, chain, day))
                    reports[column.key] = ColumnReport(
                        column=column.key, included=20, with_file=20, hole=False, counted=20, promo_files=20,
                        promo_hole=False, items=counts[0], wide=counts[1], on_promotion=counts[2],
                        valid_deals=counts[2], under_floor=False)
                out = items_path(tables, slug, day)
                out.parent.mkdir(parents=True, exist_ok=True)
                con.execute(f"COPY (SELECT {names} FROM ({' UNION ALL '.join(selects)}) ORDER BY \"column\", code) "
                            f"TO '{out}' (FORMAT parquet)")
                report = ItemsReport(slug=slug, day=day.isoformat(), columns=reports, outside=[],
                                     promotions_error=None, texts=0, promotions=None)
                out.with_name("report.json").write_text(json.dumps(asdict(report)))
        paths = ", ".join(f"'{items_path(tables, slug, SCORED)}'" for slug in SLUGS)
        rows = con.execute(f"""SELECT "column", code FROM read_parquet([{paths}], hive_partitioning = false)
                               WHERE wide AND NOT on_promotion ORDER BY "column", code""").fetchall()
    stand_in = [Forecast(column=column, code=code, p=Fraction(n % 997, 997), a=Fraction(n % 991, 991),
                         b=Fraction(n % 983, 983), b_says=n % 2 == 0, days_since=None if n % 3 else n % 61,
                         n=n % 90, a_from="pair" if n % 90 >= 20 else "column")
                for n, (column, code) in enumerate(rows)]
    (work / "frozen.csv.gz").write_bytes(forecasts_csv(stand_in, CODE_SHA))
    (work / MADE).write_text(json.dumps({"scale": scale, "days": days, "pool": pool,
                                         "rows_a_day": sum(_scaled(c[0], scale) for c in REAL.values()),
                                         "frozen_rows": len(stand_in)}))


class _Freezer:
    """The archive's freezer as the scoring step calls it, holding the frozen file of SCORED in memory."""
    writes = True

    def __init__(self, frozen: Frozen):
        self._frozen = frozen

    def frozen(self, day: date) -> Frozen | None:
        return self._frozen if day == self._frozen.day else None

    def put_scores(self, day: date, body: bytes) -> bytes:
        return body


class _Sample(History):
    """The history with only the pairs given, each passing through `seen` as it streams (as `build._Watched` passes
    the whole history's): the one pass over a sample, for the profile."""

    def __init__(self, history: History, pairs: list, seen: Callable):
        super().__init__(history.day, history.column_days, history.tables)
        self._pairs, self._seen = pairs, seen

    def pairs(self):
        for pair in self._pairs:
            self._seen(pair)
            yield pair


_V6 = ("user_time", "system_time", "pkg_idle_wkups", "interrupt_wkups", "pageins", "wired_size", "resident_size",
       "phys_footprint", "proc_start_abstime", "proc_exit_abstime", "child_user_time", "child_system_time",
       "child_pkg_idle_wkups", "child_interrupt_wkups", "child_pageins", "child_elapsed_abstime",
       "diskio_bytesread", "diskio_byteswritten", "cpu_time_qos_default", "cpu_time_qos_maintenance",
       "cpu_time_qos_background", "cpu_time_qos_utility", "cpu_time_qos_legacy", "cpu_time_qos_user_initiated",
       "cpu_time_qos_user_interactive", "billed_system_time", "serviced_system_time", "logical_writes",
       "lifetime_max_phys_footprint", "instructions", "cycles", "billed_energy", "serviced_energy",
       "interval_max_phys_footprint", "runnable_time", "flags", "user_ptime", "system_ptime", "pinstructions",
       "pcycles", "energy_nj", "penergy_nj", "secure_time_in_system", "secure_ptime_in_system", "neural_footprint",
       "lifetime_max_neural_footprint", "interval_max_neural_footprint", *(f"reserved_{n}" for n in range(9)))


class _RusageV6(ctypes.Structure):
    """macOS's `struct rusage_info_v6` (sys/resource.h)."""
    _fields_ = [("uuid", ctypes.c_uint8 * 16), *((name, ctypes.c_uint64) for name in _V6)]


class _Timebase(ctypes.Structure):
    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


def _cores() -> Callable[[], tuple[float, float, int, int]] | None:
    """A reader of the process's (CPU seconds, of them on the performance cores, instructions retired, of them on the
    performance cores), or None off macOS."""
    try:
        system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        base = _Timebase()
        system.mach_timebase_info(ctypes.byref(base))
    except OSError:
        return None
    tick = base.numer / base.denom / 1e9                 # seconds a tick of the rusage times

    def read() -> tuple[float, float, int, int]:
        info = _RusageV6()
        if system.proc_pid_rusage(os.getpid(), 6, ctypes.byref(info)) != 0:
            raise OSError("proc_pid_rusage")
        return ((info.user_time + info.system_time) * tick, (info.user_ptime + info.system_ptime) * tick,
                info.instructions, info.pinstructions)
    return read


class Steps:
    """Each step's CPU and wall seconds, and on macOS its share on the performance cores and its estimate there (the
    module's docstring), printed as it ends."""

    def __init__(self) -> None:
        self.taken: list[tuple[str, float, float, float | None]] = []
        self.cores = _cores()

    def run(self, name: str, work: Callable[[], tuple[object, str]], total: bool = True) -> object:
        cpu, wall, cores = time.process_time(), time.perf_counter(), self.cores and self.cores()
        result, detail = work()
        took_cpu, took_wall, estimate, share = time.process_time() - cpu, time.perf_counter() - wall, None, ""
        if cores:
            after = self.cores()
            used, on_p, instructions, on_p_instructions = (later - earlier for later, earlier in zip(after, cores))
            if on_p > 0:
                estimate = instructions / (on_p_instructions / on_p)
                share = f"{on_p / used:4.0%} on P{estimate:9.1f} s if all on P"
        if total:
            self.taken.append((name, took_cpu, took_wall, estimate))
        print(f"{name:<34}{took_cpu:9.1f} s CPU{took_wall:9.1f} s wall {share}   {detail}", flush=True)
        return result

    def total(self) -> None:
        cpu, wall = sum(step[1] for step in self.taken), sum(step[2] for step in self.taken)
        estimates = [step[3] for step in self.taken]
        all_p = f"{sum(estimates):9.1f} s if all on P" if None not in estimates else ""
        print(f"{'total':<34}{cpu:9.1f} s CPU{wall:9.1f} s wall {all_p}   peak resident {_peak()}", flush=True)


def _peak() -> str:
    return f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20:,.0f} MiB"   # bytes on macOS


def _profiled(label: str, work: Callable[[], object]) -> None:
    profile = cProfile.Profile()
    profile.enable()
    work()
    profile.disable()
    for order in ("cumulative", "tottime"):
        print(f"\n--- profile: {label}, by {order} ---", flush=True)
        pstats.Stats(profile, stream=sys.stdout).strip_dirs().sort_stats(order).print_stats(25)


def _bare(history: History) -> tuple[None, str]:
    pairs = points = 0
    for pair in history.pairs():
        pairs += 1
        points += len(pair.points)
    return None, f"{pairs:,} pairs, {points:,} points"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Time the site run's compute over synthetic items tables.")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--make", action="store_true", help="write the synthetic tables first")
    parser.add_argument("--scale", type=float, default=1.0, help="with --make: times 7 November's counts")
    parser.add_argument("--days", type=int, default=91, help="with --make: the days of tables, ending on DAY")
    parser.add_argument("--bare", action="store_true", help="also time a bare pass over the pairs")
    parser.add_argument("--profile", type=int, metavar="N", help="also profile the pass over N products and scoring")
    args = parser.parse_args(argv)
    work, steps = args.work, Steps()
    tables, site = work / "tables", work / "site"
    if args.make:
        steps.run("make the tables (not counted)", lambda: (make(work, args.scale, args.days), ""), total=False)
    made = json.loads((work / MADE).read_text())
    print(f"scale {made['scale']}, {made['days']} days of tables, {made['rows_a_day']:,} rows a day, pool "
          f"{made['pool']:,}; Python {sys.version.split()[0]}, DuckDB {duckdb.__version__}", flush=True)
    for folder in (site, work / "staging", tables / "covered", tables / "scored"):
        shutil.rmtree(folder, ignore_errors=True)

    history = steps.run("history (load)", lambda: (found := load(tables, DAY, SLUGS), f"{len(found.tables)} tables"))
    if args.bare:
        steps.run("a bare pass over the pairs", lambda: _bare(history), total=False)
    found = steps.run("the covered registry", lambda: (
        registry := covered(history, None, covered_path(tables, DAY)), f"{len(registry):,} covered"))

    body = (work / "frozen.csv.gz").read_bytes()
    frozen = Frozen(day=SCORED, body=body, sha256=hashlib.sha256(body).hexdigest(), frozen_at=FROZEN_AT,
                    on_time=True, status="same")
    freezer = _Freezer(frozen)
    scores = steps.run("scoring the due day", lambda: (
        stored := build._score(freezer, SCORED, history, tables)[0],
        f"{made['frozen_rows']:,} rows, {len(stored):,} B"))
    summary = read_summary(summary_path(tables, SCORED).read_bytes())
    held = made["days"] - FIRST_RECORD_DAY - HORIZON + 1     # the days frozen and scored with this many days held
    known = [replace(summary, day=SCORED - timedelta(days=back)) for back in range(max(held, 1))][::-1]
    card = steps.run("the scorecard", lambda: (scorecard(known), f"{len(known)} scored days"))
    gates = {key: Gate(**card["columns"][key]["gate"]) for key in card["columns"]}

    staging = work / "staging"

    def one_pass():
        pages = build._Pages(found, history, COLLECTED_BY, gates, {}, staging)
        rows = forecasts(build._Watched(history, pages), DAY)
        pages.finish()
        return (pages, rows), f"{len(rows):,} forecasts, {len(pages.written):,} product pages, {len(pages.rows):,} " \
                             "front rows"

    pages, rows = steps.run("the one pass", one_pass)
    steps.run("the forecasts file", lambda: (made_csv := forecasts_csv(rows, CODE_SHA), f"{len(made_csv):,} B"))

    def the_rest():
        for path in pages.written:
            target = site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(staging / path, target)
        browse = browse_pages(found, DAY, COLLECTED_BY)
        fixed = {"index.html": render_front(pages.rows, pages.counts(), DAY, COLLECTED_BY, pages.marking_none(),
                                            next(iter(browse), None)), **browse, **pieces(found)}
        for path, page in fixed.items():
            build._write(site, path, page)
        sizes = sorted((site / path).stat().st_size for path in pages.written)
        return None, (f"{len(fixed):,} fixed pages; product pages median {sizes[len(sizes) // 2]:,} B, largest "
                      f"{sizes[-1]:,} B" if sizes else f"{len(fixed):,} fixed pages")

    steps.run("pages moved in, front/browse/search", the_rest)
    steps.total()
    print(f"scores {len(scores):,} B", flush=True)

    if args.profile:
        sample, codes = [], set()
        for pair in history.pairs():
            if pair.code not in codes and len(codes) == args.profile:
                break
            codes.add(pair.code)
            sample.append(pair)
        some = {code: found[code] for code in sorted(codes) if code in found}
        print(f"\nprofiled sample: {len(codes):,} products, {len(sample):,} pairs, {len(some):,} covered", flush=True)
        shutil.rmtree(work / "profiled", ignore_errors=True)

        def sample_pass():
            pages = build._Pages(some, history, COLLECTED_BY, gates, {}, work / "profiled")
            forecasts(_Sample(history, sample, pages), DAY)
            pages.finish()

        _profiled(f"the pass over {len(codes):,} products", sample_pass)
        _profiled("scoring the due day", lambda: build._score(freezer, SCORED, history, tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())

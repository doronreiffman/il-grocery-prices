"""The shopper site's build: one day's whole site, by hand on the Mac and in the site run in Lambda (docs/shopper-site.md,
"Build and hosting" and its "The daily build" 2, F6, F7, Calls 8 to 10, 15 and 16, and "Changed after the survey";
the plan's Task 19, its questions D and E, and the pre-flights' N8, N9, N13, S13, S14 and B2).

    PYTHONPATH=src python -m shopper.build --day 2026-11-20 --collected-by 11:48 [--revise REASON] [--rebuild]

The folders. The data folder (`--data`, default `data`) mirrors the archive: `raw/`, `manifests/`,
`tables/{prices,promotions,items,covered,scored}/`, `forecasts/date=*/` and `scores/date=*/`; on the Mac
`scripts/sync.sh` brings them, read-only, and in Lambda the site run fetches what the build reads. The site folder
(`--site`, default `site`) holds what goes up, with the published copies the build compares with: `days/`,
`site-days/` and `forecasts/ledger.csv`. `build_site` is imported under its own name beside the basket's
`basket.page.build_site` (the first pre-flight's N13).

The freezer. The Mac's command builds through the read-only freezer (`shopper.freeze.ReadOnlyFreezer`), the Lambda
through the archive's; only a freezer that writes scores and freezes (question D). The Mac's build therefore never
scores, never freezes, and never adds a ledger line: it takes the day's forecasts file as the sync brought it with the
published ledger's line for it, as they are. A day the published ledger names whose file the sync did not bring is not
synced, not "never frozen"; a synced file the ledger lacks, or one whose time is not the ledger's, is no record the site
shows: either stops the build (NotSynced), before any page is written, so a synced file's time never becomes a ledger's.

A day published without forecasts stays so (the task review's finding 1). The Mac stops (NotFrozenYet) on a day with
forecast rows, no synced file and no ledger line before the day's cutoff (midnight ending it, Israel time): the site run
can still freeze that day, and a site-day file the Mac published with forecasts "none" would refuse the site run's
freeze under B12 while the hand revision that could publish it is refused as not synced. So the site run freezes the
day first, or the Mac builds after midnight, when no freezer can freeze it any more. And the site run freezes nothing
for a day whose published site-day file already says forecasts "none": the day stays as published (frozen after a
Mac build past its midnight, it would be late, and counted nowhere, anyway).

In order:

1. Extract (`extract`, the Mac's command): each chain's day through `shopper.extract.extract_chain_day` when its prices
   or its items table (each with its report) is missing, and every chain's with `rebuild`; the seconds are the
   printout's alone. The Lambda passes `extract=False`, having fetched the tables, and a missing table of the day then
   stops the build (MissingTable): an absent raw folder never becomes an empty table.
2. The history (`shopper.history.load`: the day and the 90 before it, every column; MissingTable for a chain's items
   table of the day) and the covered registry (`covered`), carried from the latest registry before the day and written
   for the day under `tables/covered/date=<day>/`.
3. Scoring, only when `freezer.writes`: each due day (`shopper.score.due`: frozen, its window closed, no summary, its
   window within the read), oldest first, is scored from the history's tables of its window (`window_history`,
   `scores_csv`), its scores file put once through the freezer, and the bytes the archive then holds published; its
   summary (`summarize` of those bytes) is written under `tables/scored/date=<t>/` after the put. A stored scores file
   whose rows differ (ScoresDiffer) is the record: its bytes are published, the summary is made from them, the build
   goes on, and the outcome carries the message for the site run to alert with after the upload. Frozen days whose
   window the read no longer holds (`out_of_reach`) are listed, in the outcome and the site-day file, and never scored.
4. The scorecard (`shopper.record.scorecard`) over the summaries of the days the build's day can know of, t + 14 at most
   the day, so an earlier day's rebuild gives the scorecard it had (F3); each column's gate is read from it.
5. One pass over the pairs (`History.pairs`, the build's longest step) serves the forecasts (`shopper.forecast.forecasts`)
   and, beside them, every covered product's page (`render_product`), the front page's rows (`front_rows_of`), the
   count line's numbers and the chains whose files mark a restricted promotion. A covered product the read no longer
   holds gets its page after the pass, with no pair (Call 10: once covered, always a page, rebuilt daily). The pages are
   drawn into a folder apart and move into the site folder only once the day is published (9), so a refused build
   leaves every page as it was.
6. The freeze (F6, question E): the day's forecasts file (`forecasts_csv`, rows sorted, the code fingerprint in every
   row) through `freezer.freeze`; a day with no forecast row freezes nothing (forecasts begin on a column's 30th day of
   records), unless the archive holds a file for it already, which the freezer then compares; the site run freezes
   nothing for a day published with forecasts "none", and the Mac stops (NotFrozenYet) on a day the site run can still
   freeze (above). ForecastsDiffer stops the build, nothing written to the site folder.
7. The ledger (Call 17): with a freezer that writes, the published ledger with the day's line added when it is not
   there (`shopper.freeze.ledger`); with the read-only freezer, the published ledger as it is (above).
8. The basket (`basket.build.build_day(..., write_pages=False)`, its tables kept: they are this build's own, the
   second pre-flight's N9): its private record and its day file by B12, as ever.
9. The site-day file by B12 (`shopper.siteday`): RevisionNeeded stops the build when the published one holds other
   numbers and no one-line reason is given (`revise`, the basket's too).
10. The files: the day's forecasts file on the site when the ledger gains its line in this run (`forecasts/<d>.csv.gz`,
    the archive's bytes), the ledger when it changed, each scored day's scores file, the site-day file when it is not
    unchanged; then every page: each product's, `index.html`, `method.html`, `record.html` (the day frozen and in the
    ledger before it is drawn, so it never lists its own day as one with no file), `basket.html` (an item linked when
    its page is built), the browse pages, the search pieces, `search.js` and the marker `.shopper-site`. The pages show
    the day as published: its "collected by" time and code fingerprint are the published site-day file's, the product
    pages drawn again when the time differs from this run's.

The count line (question A, S1): the promotions listed across a column today, distinct by chain and promotion id, are
those of the items table's structs that run today (P3), are listed across the column and have a kind, at a column
with a record today and its promotions read; the products are their barcodes; the products below are the barcodes with
a front page row. The club-only filter's label names the chains whose files mark no restricted promotion today: chains
with promotions read at some column today and no struct marking a restriction there (a chain whose promotions were not
read is never said to mark none).

The outcome lists the pages written and, apart, the data files new to the site (Call 9: they always go up): the
site-day and basket day files when not unchanged, the ledger and the day's forecasts file when the ledger gained its
line, each scored day's scores file. It lists every frozen day out of the read's reach, as the site-day file does, and
apart those that went out of reach this morning, absent from the previous published site-day file's list (the latest
before the day in the site folder; with none, every one): the site run's /fail is for those alone, so a day out of
reach alerts once, not every morning after (the ruling on the task review's (b)). It also gives the seconds the scoring
(3) and the one pass (5) took, for the site run's summary (the plan's Task 23: measured, not tuned), and logs each as it
ends, a line a step (`STEP_LINE`, as the site run logs its own steps), so a run refused or killed later still leaves
them (the task review's finding 2). Only `main` reads the time of day, and gives it as `now`.
"""
import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from basket.archive import kind_key
from basket.basket_file import DEFAULT_BASKET, BadBasket, load_basket
from basket.build import BuildOutcome, RevisionNeeded, build_day
from basket.chains import CARREFOUR_COLUMNS, SLUGS
from basket.extract import table_path
from basket.pricefile import BadPriceFile
from basket.record import code_fingerprint
from basket.rules import MissingTable
from basket.stores import NoStoreList, chain_stores, included
from collector.run import new_run_id
from shopper.columns import COLUMNS, members, outside, under_floor
from shopper.extract import extract_chain_day
from shopper.forecast import forecasts, forecasts_csv
from shopper.freeze import (ForecastsDiffer, Frozen, ReadOnlyFreezer, ScoresDiffer, cutoff, days_with, ledger,
                            scores_site_key, site_key)
from shopper.history import Covered, History, Pair, covered, covered_path, load
from shopper.items import HORIZON, items_path
from shopper.pages import (ColumnsToday, Counts, FrontRow, front_rows_of, render_basket, render_front, render_method,
                           render_record)
from shopper.product import page_path, render_product, running_today
from shopper.record import Gate, scorecard
from shopper.score import (DaySummary, due, out_of_reach, read_summary, scores_csv, summarize, summary_json,
                           summary_path, window_history)
from shopper.search import SCRIPT, browse_pages, pieces
from shopper.siteday import Inputs, publish_site_day, site_day, site_day_path, write_site_day

__all__ = ["LEDGER", "MARKER", "ForecastsDiffer", "NotFrozenYet", "NotSynced", "SiteOutcome", "build_site", "main",
           "read_ledger"]

MARKER = ".shopper-site"
LEDGER = "forecasts/ledger.csv"
STEP_LINE = "step %s: %.1f s"   # a step's line in the run's log: its name and its seconds
log = logging.getLogger(__name__)


class NotFrozenYet(Exception):
    """The Mac's build of a day the site run can still freeze, before its cutoff (the module's docstring)."""


class NotSynced(Exception):
    """The Mac's synced forecasts file of the day and the published ledger disagree (the module's docstring)."""


@dataclass(frozen=True)
class SiteOutcome:
    """What the build did: the day and the run; whether the site-day file was left as published; the basket's build;
    the day's forecasts file as the freezer gave it (None when none is frozen); the days scored by this run, the days due
    (scored only through a freezer that writes), those out of reach and, of them, those the previous published site-day
    file did not list (the only ones the site run alerts for); the pages written and the data files new to the
    site, as site paths; each chain's promotions error, by slug; each ScoresDiffer's message; each chain's extraction
    seconds (None for tables kept); the site-day file as the pages show it, and whether this run revised it; the
    seconds of the scoring and of the one pass."""
    day: date
    run_id: str
    unchanged: bool
    basket: BuildOutcome
    frozen: Frozen | None
    scored: list[date]
    pages: list[str]
    data: list[str]
    promotions_errors: dict[str, str]
    due: list[date]
    out_of_reach: list[date]
    newly_out_of_reach: list[date]
    scores_differ: list[str]
    extraction_seconds: dict[str, float | None]
    site_day: dict
    revised: bool
    seconds: dict[str, float]


class _Watched(History):
    """The history, its pairs passing through `seen` as they stream: one pass serves the forecasts and the pages."""

    def __init__(self, history: History, seen):
        super().__init__(history.day, history.column_days, history.tables)
        self._seen = seen

    def pairs(self):
        for pair in super().pairs():
            self._seen(pair)
            yield pair


class _Pages:
    """What the one pass gathers beside the forecasts, a product (its pairs, by code) at a time: each covered product's
    page, drawn into `out`; the front page's rows; the count line's promotions and products; the chains marking a
    restricted promotion today (the module's docstring)."""

    def __init__(self, covered_now: Mapping[str, Covered], history: History, collected_by: str,
                 gates: Mapping[str, Gate], errors: Mapping[str, str], out: Path):
        self.covered, self.column_days, self.day = covered_now, history.column_days, history.day
        self.collected_by, self.gates, self.errors, self.out = collected_by, gates, errors, out
        self.code: str | None = None
        self.pairs: dict[str, Pair] = {}
        self.seen: set[str] = set()
        self.rows: list[FrontRow] = []
        self.promotions: set[tuple[str, str]] = set()
        self.products: set[str] = set()
        self.marking: set[str] = set()
        self.written: list[str] = []
        (out / "p").mkdir(parents=True, exist_ok=True)

    def __call__(self, pair: Pair) -> None:
        if pair.code != self.code:
            self._product()
            self.code, self.pairs = pair.code, {}
        self.pairs[pair.column] = pair
        self._today(pair)

    def _today(self, pair: Pair) -> None:
        """The pair's promotions today, for the count line and the club-only label."""
        today = self.column_days[(pair.column, self.day)]
        point = pair.points.get(self.day)
        if point is None or today.promo_hole:      # nothing read, or from too few promotion files
            return
        if any(struct["restrictions"] for struct in point.promotions):
            self.marking.add(today.slug)
        if not today.record:                        # a hole makes no claim (S1)
            return
        listed = [struct for struct in running_today(point, self.day) if struct["wide"] and struct["kind"] is not None]
        self.promotions |= {(today.slug, struct["promotion_id"]) for struct in listed}
        if listed:
            self.products.add(pair.code)

    def _product(self) -> None:
        """The product whose pairs are gathered: its page and its front page rows."""
        if self.code is None:
            return
        self.seen.add(self.code)
        found = self.covered.get(self.code)
        if found is None:
            return
        self._page(found, self.pairs)
        self.rows += front_rows_of(self.code, found.title, self.pairs, self.column_days, self.day)

    def _page(self, found: Covered, pairs: Mapping[str, Pair]) -> None:
        path = page_path(found.code)
        (self.out / path).write_text(render_product(found, pairs, self.column_days, self.day, self.collected_by,
                                                    self.gates, self.errors), encoding="utf-8")
        self.written.append(path)

    def finish(self) -> None:
        """The last product, then every covered product the read no longer holds, with no pair."""
        self._product()
        self.code, self.pairs = None, {}
        for code in sorted(set(self.covered) - self.seen):
            self._page(self.covered[code], {})

    def counts(self) -> Counts:
        """The count line's numbers (the module's docstring)."""
        return Counts(promotions=len(self.promotions), products=len(self.products),
                      below=len({row.code for row in self.rows}))

    def marking_none(self) -> list[str]:
        """The chains whose files mark no restricted promotion today: promotions read at some column of theirs today,
        none marking a restriction there."""
        read = {found.slug for (_, seen), found in self.column_days.items() if seen == self.day and not found.promo_hole}
        return [slug for slug in SLUGS if slug in read and slug not in self.marking]


def _kept(tables_dir: Path, slug: str, day: date) -> bool:
    """Whether the chain's prices and items tables of the day are there, each with its report."""
    return all(path.is_file() and path.with_name("report.json").is_file()
               for path in (table_path(tables_dir, slug, day), items_path(tables_dir, slug, day)))


def _extract(raw_dir: Path, tables_dir: Path, day: date, rebuild: bool) -> dict[str, float | None]:
    """Each chain's day extracted unless its tables are there and no rebuild is asked; the seconds, None for kept."""
    seconds: dict[str, float | None] = {}
    for slug in SLUGS:
        if _kept(tables_dir, slug, day) and not rebuild:
            seconds[slug] = None
            continue
        started = time.perf_counter()
        extract_chain_day(raw_dir, slug, day, tables_dir)
        seconds[slug] = time.perf_counter() - started
    return seconds


def _fetched(tables_dir: Path, day: date) -> dict[str, float | None]:
    """With no extraction: every chain's prices table of the day must be there (MissingTable), as its items table must
    (`load`)."""
    for slug in SLUGS:
        path = table_path(tables_dir, slug, day)
        if not (path.is_file() and path.with_name("report.json").is_file()):
            raise MissingTable(f"no prices table for chain {slug!r} on {day.isoformat()}: {path}")
    return dict.fromkeys(SLUGS)


def _relative(local: Callable[[Path, date], Path]) -> Callable[[date], str]:
    """A local path function as the key of a file under its folder, for `shopper.freeze.days_with`."""
    return lambda day: local(Path(), day).as_posix()


def _summaries(tables_dir: Path) -> list[DaySummary]:
    """Every scoring summary under the tables folder, earliest first."""
    return [read_summary(summary_path(tables_dir, day).read_bytes())
            for day in days_with(tables_dir, _relative(summary_path))]


def _previous_registry(tables_dir: Path, day: date) -> date | None:
    """The day of the latest covered registry before `day` (as `basket.archive.fetch_covered` takes it), or None."""
    return max((found for found in days_with(tables_dir, _relative(covered_path)) if found < day), default=None)


def _score(freezer, t: date, history: History, tables_dir: Path) -> tuple[bytes, str | None]:
    """Day t scored (the module's docstring, 3): the bytes the site publishes, and ScoresDiffer's message or None."""
    frozen = freezer.frozen(t)
    body = scores_csv(frozen, window_history(history, t))
    message = None
    try:
        stored = freezer.put_scores(t, body)
    except ScoresDiffer as differ:          # the stored file is the record
        stored, message = freezer.stored_scores(t), str(differ)
    path = summary_path(tables_dir, t)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(summary_json(summarize(stored, frozen)))
    return stored, message


def _site_days(site_dir: Path) -> list[date]:
    """The days of the site-day files in the site folder, earliest first."""
    found = []
    for path in (site_dir / "site-days").glob("*.json"):
        try:
            seen = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if path == site_day_path(site_dir, seen):
            found.append(seen)
    return sorted(found)


def _published_none(site_dir: Path, day: date) -> bool:
    """Whether the day's published site-day file says no forecasts file is frozen for it."""
    path = site_day_path(site_dir, day)
    return path.is_file() and json.loads(path.read_text(encoding="utf-8"))["forecasts"]["status"] == "none"


def _newly(far: list[date], site_dir: Path, day: date) -> list[date]:
    """The days out of reach that the previous published site-day file (the latest before the day) did not list: on
    their first morning out of reach, the only one the site run alerts for. With no earlier file, every one."""
    earlier = [seen for seen in _site_days(site_dir) if seen < day]
    if not earlier:
        return list(far)
    listed = set(json.loads(site_day_path(site_dir, earlier[-1]).read_text(encoding="utf-8"))["out_of_reach"])
    return [t for t in far if t.isoformat() not in listed]


def read_ledger(body: bytes | None) -> dict[date, datetime]:
    """The days a ledger names, each with its file's S3 time ({} for no ledger); the site check reads it too."""
    if body is None:
        return {}
    found = {}
    for line in body.decode().splitlines()[1:]:
        day, _, at = line.split(",")
        found[date.fromisoformat(day)] = datetime.fromisoformat(at)
    return found


def _ledger(writes: bool, published: bytes | None, frozen: Frozen | None, day: date) -> bytes | None:
    """The ledger after the freeze (the module's docstring, 7, and "The freezer")."""
    if writes:
        return published if frozen is None else ledger(published, frozen)
    named = day in read_ledger(published)
    if frozen is None:
        if named:
            raise NotSynced(f"the published ledger names a forecasts file for {day.isoformat()} that the synced data "
                            "does not hold: run scripts/sync.sh first")
        return published
    if not named:
        raise NotSynced(f"the synced data holds a forecasts file for {day.isoformat()} that the published ledger lacks: "
                        "only the site run in Lambda adds a ledger line, so let it publish the day, or sync again")
    try:
        ledger(published, frozen)
    except ValueError as error:
        raise NotSynced(f"the synced forecasts file for {day.isoformat()} is not the published ledger's: {error}") \
            from error
    return published


def _inputs(history: History, registry: date | None) -> Inputs:
    """Every items table read and the registry carried, by archive key."""
    tables = [kind_key("items", path.parent.parent.name.removeprefix("chain="), day, "items.parquet")
              for path, day in history.tables.items()]
    return Inputs(items_tables=tuple(sorted(tables)),
                  registry=None if registry is None else kind_key("covered", None, registry, "covered.parquet"))


def _columns_today(raw_dir: Path, day: date) -> ColumnsToday:
    """The method page's account of the columns, from each chain's store list of the day."""
    found, beside = {}, {}
    for slug in SLUGS:
        stores = chain_stores(raw_dir, slug, day)[0]
        ids = included(stores, slug)
        found.update(members(slug, stores, ids))
        beside[slug] = outside(slug, stores, ids)
    in_order = {column.key: found[column.key] for column in COLUMNS}
    return ColumnsToday(members=in_order, outside=beside, under_floor=under_floor(in_order), carrefour=CARREFOUR_COLUMNS)


def _write(site_dir: Path, path: str, body: bytes | str) -> str:
    target = site_dir / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, str):
        target.write_text(body, encoding="utf-8")
    else:
        target.write_bytes(body)
    return path


def _drawn(history: History, covered_now, collected_by: str, gates, errors, out: Path) -> _Pages:
    """The product pages drawn again, in a pass of their own, at another "collected by" time."""
    again = _Pages(covered_now, history, collected_by, gates, errors, out)
    for pair in history.pairs():
        again(pair)
    again.finish()
    return again


def build_site(day: date, data_dir: Path, site_dir: Path, now: datetime, collected_by: str, freezer,
               revise: str | None = None, rebuild: bool = False, extract: bool = True,
               basket_path: Path = DEFAULT_BASKET, min_items: int = 25) -> SiteOutcome:
    """Build the day's whole site (the module's docstring); `now` must carry a time zone."""
    run_id = new_run_id(now, "site")   # first: it refuses a naive `now`, which would be read as this machine's zone
    raw_dir, tables_dir = data_dir / "raw", data_dir / "tables"
    extracted = _extract(raw_dir, tables_dir, day, rebuild) if extract else _fetched(tables_dir, day)
    history = load(tables_dir, day, SLUGS)
    registry = _previous_registry(tables_dir, day)
    covered_now = covered(history, None if registry is None else covered_path(tables_dir, registry),
                          covered_path(tables_dir, day))
    reports = {slug: json.loads(items_path(tables_dir, slug, day).with_name("report.json").read_text())
               for slug in SLUGS}
    errors = {slug: report["promotions_error"] for slug, report in reports.items()
              if report["promotions_error"] is not None}

    summaries = _summaries(tables_dir)
    frozen_days, scored_before = list(freezer.frozen_days()), [summary.day for summary in summaries]
    due_days, far = due(frozen_days, scored_before, day), out_of_reach(frozen_days, scored_before, day)
    scores: dict[date, bytes] = {}
    differ: list[str] = []
    started = time.perf_counter()
    if freezer.writes:
        for t in due_days:
            scores[t], message = _score(freezer, t, history, tables_dir)
            differ += [message] if message else []
        summaries = _summaries(tables_dir)
    seconds = {"scoring": time.perf_counter() - started}
    log.info(STEP_LINE, "scoring", seconds["scoring"])
    known = [summary for summary in summaries if summary.day + timedelta(days=HORIZON) <= day]
    card = scorecard(known)
    gates = {key: Gate(**card["columns"][key]["gate"]) for key in card["columns"]}
    code_sha = code_fingerprint()

    with tempfile.TemporaryDirectory(prefix="shopper-pages-") as staging:
        started = time.perf_counter()
        pages = _Pages(covered_now, history, collected_by, gates, errors, Path(staging) / "first")
        rows = forecasts(_Watched(history, pages), day)
        pages.finish()
        seconds["pass"] = time.perf_counter() - started
        log.info(STEP_LINE, "pass", seconds["pass"])
        frozen = None
        published_none = _published_none(site_dir, day)
        if (rows or freezer.frozen(day) is not None) and not (freezer.writes and published_none):
            frozen = freezer.freeze(day, forecasts_csv(rows, code_sha))
        ledger_path = site_dir / LEDGER
        published = ledger_path.read_bytes() if ledger_path.is_file() else None
        new_ledger = _ledger(freezer.writes, published, frozen, day)
        if not freezer.writes and frozen is None and rows and not published_none and now < cutoff(day):
            raise NotFrozenYet(f"{day.isoformat()} has forecasts the site run can still freeze, before midnight ending "
                               "the day, Israel time: let the site run freeze the day, then sync, or build after "
                               "midnight")

        basket_outcome = build_day(day, data_dir, site_dir, basket_path, now, revise, rebuild=False,
                                   min_items=min_items, collected_by=collected_by, write_pages=False)
        counts = pages.counts()
        new = site_day(day, run_id, code_sha, now, collected_by, _inputs(history, registry), history.column_days,
                       reports, counts, pages.rows, frozen, card, [summary.day for summary in known], far)
        shown, unchanged, revised = publish_site_day(new, site_dir, now, revise)

        data = []
        if new_ledger != published:
            if frozen is not None:
                data.append(_write(site_dir, site_key(day), frozen.body))
            data.append(_write(site_dir, LEDGER, new_ledger))
        data += [_write(site_dir, scores_site_key(t), body) for t, body in scores.items()]
        if not unchanged:
            write_site_day(shown, site_dir)
            data.append(f"site-days/{day.isoformat()}.json")
        if not basket_outcome.unchanged:
            data.append(f"days/{day.isoformat()}.json")

        shown_by = shown["collected_by"]
        if shown_by != collected_by:
            pages = _drawn(history, covered_now, shown_by, gates, errors, Path(staging) / "again")
        for path in pages.written:
            target = site_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(pages.out / path, target)
    written = list(pages.written)

    basket = load_basket(basket_path, min_items=min_items)
    ledger_days = {seen: at for seen, at in read_ledger(new_ledger).items() if seen <= day}
    files = ([LEDGER] if new_ledger is not None else []) + [site_key(seen) for seen in ledger_days]
    files += [scores_site_key(summary.day) for summary in known]
    browse = browse_pages(covered_now, day, shown_by)
    fixed = {
        "index.html": render_front(pages.rows, counts, day, shown_by, pages.marking_none(), next(iter(browse), None)),
        "method.html": render_method(basket, basket_outcome.exclusions, _columns_today(raw_dir, day), day, shown_by,
                                     shown["code_sha"], basket_outcome.public),
        "record.html": render_record(shown["scorecard"], ledger_days, files, history.column_days, day, shown_by),
        "basket.html": render_basket(basket_outcome.public, basket, basket_outcome.exclusions, day, shown_by,
                                     set(covered_now)),
        **browse,
        **pieces(covered_now),
        "search.js": SCRIPT.read_bytes(),
    }
    written += [_write(site_dir, path, body) for path, body in fixed.items()]
    (site_dir / MARKER).write_text("", encoding="utf-8")
    return SiteOutcome(day=day, run_id=run_id, unchanged=unchanged, basket=basket_outcome, frozen=frozen,
                       scored=sorted(scores), pages=written, data=data, promotions_errors=errors, due=due_days,
                       out_of_reach=far, newly_out_of_reach=_newly(far, site_dir, day), scores_differ=differ, extraction_seconds=extracted, site_day=shown,
                       revised=revised, seconds=seconds)


def _days(days) -> str:
    return ", ".join(day.isoformat() for day in days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one day's shopper site on the Mac (the read-only freezer).")
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--collected-by", metavar="HH:MM", required=True,
                        help="the time by which the day's files had been collected (B11): the check's")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--basket", type=Path, default=DEFAULT_BASKET, help="default: the package's v1")
    parser.add_argument("--min-items", type=int, default=25)
    parser.add_argument("--rebuild", action="store_true", help="extract every chain's tables of the day again")
    parser.add_argument("--revise", metavar="REASON", help="republish a published day whose numbers changed")
    args = parser.parse_args(argv)
    try:
        outcome = build_site(args.day, args.data, args.site, datetime.now(timezone.utc), args.collected_by,
                             ReadOnlyFreezer(args.data), revise=args.revise, rebuild=args.rebuild,
                             basket_path=args.basket, min_items=args.min_items)
    except (BadBasket, BadPriceFile, ForecastsDiffer, MissingTable, NoStoreList, NotFrozenYet, NotSynced,
            RevisionNeeded) as error:
        print(error, file=sys.stderr)
        return 1
    for slug, took in outcome.extraction_seconds.items():
        print(f"{slug}: tables kept" if took is None else f"{slug}: extracted in {took:.1f} s")
    for error in outcome.promotions_errors.values():
        print(f"promotions not read: {error}")
    products = sum(path.startswith("p/") for path in outcome.pages)
    print(f"covered: {products:,} products")
    frozen = outcome.frozen
    if frozen is None:
        print(f"forecasts: none frozen for {args.day.isoformat()}")
    else:
        rows = outcome.site_day["forecasts"]["rows"]
        print(f"forecasts: {frozen.status}, {rows:,} {'row' if rows == 1 else 'rows'}, SHA-256 {frozen.sha256}, "
              f"S3 time {outcome.site_day['forecasts']['frozen_at']}")
    if outcome.due:     # the read-only freezer scores nothing
        print(f"due, scored only by the site run in Lambda: {_days(outcome.due)}")
    if outcome.out_of_reach:
        print(f"out of reach, never scored: {_days(outcome.out_of_reach)}")
    rows, counts = len(outcome.site_day["front_rows"]), outcome.site_day["counts"]
    print(f"front page: {rows:,} {'row' if rows == 1 else 'rows'}; the count line: {counts['promotions']:,} "
          f"promotions on {counts['products']:,} products, {counts['below']:,} below")
    print(*outcome.basket.headline_lines, sep="\n")
    for what, path, state in (
            ("basket day", args.site / "days" / f"{args.day.isoformat()}.json", outcome.basket),
            ("site day", args.site / "site-days" / f"{args.day.isoformat()}.json", outcome)):
        done = "unchanged" if state.unchanged else "revised" if state.revised else "published"
        print(f"{what}: {done}: {path}")
    print(f"pages: {products:,} product pages and {len(outcome.pages) - products:,} others")
    print(f"data files new to the site: {', '.join(outcome.data) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

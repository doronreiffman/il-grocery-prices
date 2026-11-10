"""The shopper site's build (`shopper.build`; the plan's Task 19): one day's whole site, by hand on the Mac (the read-only
freezer, question D) and in Lambda's site run (the archive's freezer), and the command.

The tree is the basket's golden day (tests/test_build.py: each chain's price files and store list, no promotion file),
extracted, then given a history at Osher Ad by hand (tests/test_history.py's items tables): 40 days of three products,
a fourth, B, listed across the column before today and not today, and a fifth, C, never listed across it; today Osher
Ad's table is written by hand too, milk on a promotion for club members at ₪3.00. A registry of 100 days back holds a
product, A, the read no longer reaches. The archive is a MemoryArchive with its S3 clock. The one pass's counts are
tested apart, over pairs built by hand as tests/test_product.py builds them. Names, barcodes and prices are
synthetic."""
import gzip
import hashlib
import json
import os
import re
import shutil
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from html import unescape
from pathlib import Path

import pytest

from basket.archive import MemoryArchive
from basket.build import RevisionNeeded
from basket.chains import SLUGS
from basket.extract import table_path
from basket.rules import MissingTable
from shopper import build as shop_build
from shopper.build import MARKER, NotFrozenYet, NotSynced, build_site, main
from shopper.extract import extract_chain_day
from shopper.forecast import Forecast, forecasts_csv
from shopper.freeze import (ArchiveFreezer, Frozen, ReadOnlyFreezer, archive_key, ledger, scores_archive_key,
                            scores_site_key, site_key)
from shopper.columns import COLUMNS
from shopper.history import History, covered, covered_path, load
from shopper.items import items_path
from shopper.pages import Counts
from shopper.product import page_path
from shopper.score import DaySummary, read_summary, summary_json, summary_path
from shopper.search import SCRIPT
from shopper.siteday import site_day_path
from test_build import BASKET, DAY, EGGS, MILK, PASTA, golden_tree
import test_product as product
from test_history import _row, _table

# Synthetic GS1 codes: A beyond the read, B not listed across its column today, C never listed across it
A, B, C = "2000000000046", "2000000000053", "2000000000060"
OSHER = "osherad"
NOW = datetime(2026, 1, 1, 10, 33, tzinfo=timezone.utc)          # 12:33 in Israel
LATER = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
STAMP = datetime(2026, 1, 1, 10, 33, 7, tzinfo=timezone.utc)     # S3's time of every put
AFTER = datetime(2026, 1, 1, 22, 30, tzinfo=timezone.utc)         # 00:30 on 2 January in Israel: past DAY's cutoff
AFTER_LATER = AFTER + timedelta(hours=1)
T = DAY - timedelta(days=14)                                       # the day the build of DAY scores
FAR = DAY - timedelta(days=120)                                    # a frozen day past the read's reach
DEAL = {"promotion_id": "7", "description": "PLACEHOLDER", "start": "2025-12-28", "end": "2026-01-10", "kind": "3",
        "buy": "1", "price": "3.00", "price_exact": "3", "per": "unit", "low": None, "high": None, "valid": True,
        "why": None, "restrictions": ["club"], "programmes": [], "min_spend": None, "stores": 4, "wide": True}
_TEMPLATES: dict[bool, Path] = {}
_ROOT: list[Path] = []


@pytest.fixture(scope="module", autouse=True)
def _templates(tmp_path_factory):
    """Each kind of tree is built once a module, in a folder of its own, and copied for each test."""
    _ROOT[:] = [tmp_path_factory.mktemp("templates")]
    _TEMPLATES.clear()


def _history(data: Path, days: int) -> None:
    """Osher Ad's items tables of `days` days before DAY and of DAY itself (replacing the extracted one)."""
    tables = data / "tables"
    for n in range(1, days + 1):
        _table(tables, OSHER, DAY - timedelta(days=n),
               rows=[_row(OSHER, MILK, "6.15"), _row(OSHER, PASTA, "4.90"), _row(OSHER, EGGS, "11.60"),
                     _row(OSHER, B, "9.90"), _row(OSHER, C, "2.50", wide=False)])
    _table(tables, OSHER, DAY, rows=[_row(OSHER, MILK, "6.15", on_promotion=True, promotions=[DEAL]),
                                     _row(OSHER, PASTA, "4.90"), _row(OSHER, EGGS, "11.60"),
                                     _row(OSHER, B, "9.90", wide=False), _row(OSHER, C, "2.50", wide=False)])


def _registry(data: Path, root: Path) -> None:
    """A registry of DAY - 100 holding A, covered 200 days back and not listed since."""
    old = DAY - timedelta(days=200)
    _table(root / "old", OSHER, old, rows=[_row(OSHER, A, "5.00")])
    covered(load(root / "old", old, [OSHER]), None, covered_path(data / "tables", DAY - timedelta(days=100)))


def tree(root: Path, history: bool = True) -> Path:
    """The tree (the module's docstring) under `root`, copied from one built per kind; the data folder."""
    if history not in _TEMPLATES:
        template = _ROOT[0] / ("history" if history else "golden")
        data = golden_tree(template)
        for slug in SLUGS:
            extract_chain_day(data / "raw", slug, DAY, data / "tables")
        if history:
            _history(data, 40)
            _registry(data, template)
        _TEMPLATES[history] = data
    data = root / "data"
    shutil.copytree(_TEMPLATES[history], data)
    return data


def _build(data: Path, site: Path, freezer=None, now: datetime | None = None, **more):
    """A build of DAY: the site run's (the freezer given) at 12:33 Israel time; the Mac's, by default, past DAY's
    cutoff, when its forecasts can no longer be frozen (finding 1's ruling)."""
    if now is None:
        now = AFTER if freezer is None else NOW
    return build_site(DAY, data, site, now, "11:48", ReadOnlyFreezer(data) if freezer is None else freezer,
                      basket_path=BASKET, min_items=1, **more)


def _archive() -> MemoryArchive:
    return MemoryArchive(s3_clock=lambda: STAMP)


def _put_frozen(archive: MemoryArchive, day: date, at: datetime, body: bytes | None = None) -> None:
    """A day's forecasts file already in the archive, put at `at` by S3's clock."""
    archive.s3_clock = lambda: at
    archive.put_frozen(day, _frozen_file() if body is None else body, at)
    archive.s3_clock = lambda: STAMP


def _frozen_file(rows=((OSHER, PASTA), (OSHER, MILK))) -> bytes:
    return forecasts_csv([Forecast(column=column, code=code, p=Fraction(1, 4), a=Fraction(1, 5), b=Fraction(1, 3),
                                   b_says=False, days_since=None, n=27, a_from="pair") for column, code in rows],
                         "f00df00df00d")


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _site_day(site: Path) -> dict:
    return json.loads(site_day_path(site, DAY).read_text(encoding="utf-8"))


def _text(path: Path) -> str:
    return " ".join(unescape(path.read_text(encoding="utf-8")).split())


def _snapshot(*folders: Path) -> dict[str, tuple[bytes, int]]:
    return {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for folder in folders
            for path in sorted(folder.rglob("*")) if path.is_file()}


def _published_ledger(site: Path, *frozen: Frozen) -> bytes:
    body = None
    for each in frozen:
        body = ledger(body, each)
    path = site / "forecasts" / "ledger.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def _synced(data: Path, day: date, body: bytes, at: datetime) -> Frozen:
    """A forecasts file as scripts/sync.sh brings it: the archive's bytes, S3's time kept."""
    path = data / archive_key(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    os.utime(path, (at.timestamp(), at.timestamp()))
    return Frozen(day=day, body=body, sha256=_sha(body), frozen_at=at, on_time=True, status="same")


# ---- the pages ----

def test_the_build_writes_every_covered_products_page_and_the_marker(tmp_path):
    """Call 10: once covered, always a page, rebuilt every day: the products listed across a column today, B (covered,
    listed today but not across) and A (covered 200 days back, beyond the read) alike, and never C, listed and never
    across; then the fixed pages, the browse pages, the search pieces, `search.js` and the marker."""
    data, site = tree(tmp_path), tmp_path / "site"
    outcome = _build(data, site)
    codes = sorted([MILK, PASTA, EGGS, A, B])
    assert sorted(path.stem for path in (site / "p").glob("*.html")) == codes          # never C's
    assert (site / MARKER).is_file() and MARKER == ".shopper-site" and (site / MARKER).read_text() == ""
    for name in ("index.html", "method.html", "record.html", "basket.html"):
        assert (site / name).read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (site / "search.js").read_bytes() == SCRIPT.read_bytes()
    assert (site / "search" / "pieces.json").is_file() and list((site / "browse").glob("*.html"))
    written = sorted(str(path.relative_to(site)) for path in site.rglob("*") if path.is_file())
    assert sorted(outcome.pages + outcome.data + [MARKER]) == written
    assert set(outcome.pages) >= {page_path(code) for code in codes} | {"index.html", "search.js", "basket.html"}
    assert "<h1>" in (site / page_path(A)).read_text(encoding="utf-8")


def test_every_product_link_resolves_to_a_page_the_build_wrote(tmp_path):
    """Every product the front page, the basket page and the browse pages link, and every barcode the search pieces
    send to `p/<barcode>.html`, is a page the build wrote (Task 18's carry: the codes in the page paths' form)."""
    data, site = tree(tmp_path), tmp_path / "site"
    _build(data, site)
    linked = set()
    for name in ("index.html", "basket.html", "record.html", "method.html"):
        linked |= set(re.findall(r'href="(p/[^"]+)"', (site / name).read_text(encoding="utf-8")))
    for page in (site / "browse").glob("*.html"):
        linked |= {path.removeprefix("../") for path in re.findall(r'href="(\.\./p/[^"]+)"', page.read_text())}
    for piece in (site / "search").glob("*.json"):
        if piece.name != "pieces.json":
            linked |= {page_path(entry[0]) for entry in json.loads(piece.read_text(encoding="utf-8"))}
    assert page_path(MILK) in linked and page_path(A) in linked                    # the front row's and the browse's
    browse = re.findall(r'href="(browse/[^"]+)"', (site / "index.html").read_text(encoding="utf-8"))
    assert browse and all((site / path).is_file() for path in browse)            # the path to every product
    assert re.search(rf'href="{page_path(MILK)}"', (site / "index.html").read_text(encoding="utf-8"))
    assert re.search(rf'href="{page_path(MILK)}"', (site / "basket.html").read_text(encoding="utf-8"))
    assert not [path for path in linked if not (site / path).is_file()]


def test_the_front_page_has_the_days_row_and_count_line(tmp_path):
    """Milk's ₪3.00 at Osher Ad, below every listed price of its 40 days of records: one row, and the counts (one
    promotion listed across a column today, on one product, one of them on the front page): the lead line's and the
    fold-out's (the owner's plain words, 2026-11-10)."""
    data, site = tree(tmp_path), tmp_path / "site"
    _build(data, site)
    front = _text(site / "index.html")
    assert "1 product passed today." in front
    assert ("Today the five chains list 1 promotion carried by at least half of a store format's stores, on 1 "
            "product.") in front
    found = _site_day(site)
    assert found["counts"] == {"promotions": 1, "products": 1, "below": 1}
    assert [(row["column"], row["barcode"], row["deal"]) for row in found["front_rows"]] == [(OSHER, MILK, "3.00")]
    assert found["columns"][OSHER]["counts"]["front_rows"] == 1
    assert "Osher Ad's files mark no deal" not in front                 # its promotion is for club members


def test_the_lead_line_says_none_yet_before_a_column_has_20_days_of_records(tmp_path):
    """The golden day alone: no column has a record before today, so no product can be listed yet, and the lead line
    says so (`shopper.pages.front_ready`, from the history's column-days), never that none is below."""
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    _build(data, site)
    front = _text(site / "index.html")
    assert "None yet: a product needs 20 days of price history first." in front
    assert "None passed today." not in front


def test_the_lead_line_says_none_today_once_a_column_has_20_days_of_records(tmp_path):
    """Osher Ad's 40 days of records, milk's deal at ₪7.00 above its listed ₪6.15: no row, and the lead line says none
    passed today, not "None yet"."""
    data, site = tree(tmp_path), tmp_path / "site"
    above = {**DEAL, "price": "7.00", "price_exact": "7"}
    _table(data / "tables", OSHER, DAY, rows=[_row(OSHER, MILK, "6.15", on_promotion=True, promotions=[above]),
                                              _row(OSHER, PASTA, "4.90"), _row(OSHER, EGGS, "11.60"),
                                              _row(OSHER, B, "9.90", wide=False), _row(OSHER, C, "2.50", wide=False)])
    _build(data, site)
    assert _site_day(site)["counts"] == {"promotions": 1, "products": 1, "below": 0}
    front = _text(site / "index.html")
    assert "None passed today." in front and "None yet" not in front


def test_the_record_page_counts_the_day_just_frozen(tmp_path):
    """Task 18's review carry: the day is frozen and in the ledger before the record page is drawn, so the page never
    lists its own day as one with no forecasts file."""
    data, site = tree(tmp_path), tmp_path / "site"
    archive = _archive()
    _put_frozen(archive, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    after = DAY + timedelta(days=3)          # an earlier day's rebuild meets a ledger that runs past it
    later = Frozen(day=after, body=_frozen_file(), sha256=_sha(_frozen_file()), frozen_at=NOW + timedelta(days=3),
                   on_time=True, status="same")
    _published_ledger(site, ArchiveFreezer(archive, NOW).frozen(T), later)
    _build(data, site, ArchiveFreezer(archive, NOW))
    record = _text(site / "record.html")
    assert site_key(after) not in (site / "record.html").read_text(encoding="utf-8")
    assert "Forecasts frozen on 2 days, from 18 December 2025 to 1 January 2026: 2 on time, 0 late." in record
    assert "with no forecasts file: 19 to 31 December 2025." in record
    for path in ("forecasts/ledger.csv", site_key(T), site_key(DAY), scores_site_key(T)):
        assert f'href="{path}"' in (site / "record.html").read_text(encoding="utf-8")


# ---- the site run's freezer: freezing, scoring, the ledger ----

def test_the_site_run_freezes_scores_and_grows_the_ledger(tmp_path):
    data, site = tree(tmp_path), tmp_path / "site"
    archive = _archive()
    _put_frozen(archive, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    earlier = _published_ledger(site, ArchiveFreezer(archive, NOW).frozen(T))
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    # today's forecasts: Osher Ad's pasta and eggs (milk is on promotion today), frozen once, the same bytes on the site
    frozen = archive.objects[archive_key(DAY)].body
    assert (outcome.frozen.status, outcome.frozen.body, outcome.frozen.frozen_at) == ("frozen", frozen, STAMP)
    assert [line.split(",")[:2] for line in gzip.decompress(frozen).decode().splitlines()[1:]] == [
        [OSHER, PASTA], [OSHER, EGGS]]
    assert (site / site_key(DAY)).read_bytes() == frozen
    line = f"2026-01-01,{_sha(frozen)},2026-01-01T10:33:07Z\n".encode()
    assert (site / "forecasts" / "ledger.csv").read_bytes() == earlier + line
    # day T scored: the archive's bytes on the site, the summary from them, milk's outcome 1 (on promotion today)
    assert (outcome.due, outcome.scored, outcome.out_of_reach, outcome.scores_differ) == ([T], [T], [], [])
    stored = archive.objects[scores_archive_key(T)].body
    assert (site / scores_site_key(T)).read_bytes() == stored
    summary = read_summary(summary_path(data / "tables", T).read_bytes())
    assert (summary.day, summary.by_column[OSHER].scored, summary.by_column[OSHER].outcome_1) == (T, 2, 1)
    found = _site_day(site)
    assert found["forecasts"] == {"status": "frozen", "sha256": _sha(frozen), "frozen_at": "2026-01-01T10:33:07Z",
                                  "on_time": True, "rows": 2}
    assert found["scored_days"] == [T.isoformat()]
    assert found["scorecard"]["columns"][OSHER]["versions"][0]["all"]["scored"] == 2
    assert sorted(outcome.data) == sorted(["site-days/2026-01-01.json", "days/2026-01-01.json", site_key(DAY),
                                           "forecasts/ledger.csv", scores_site_key(T)])


def test_an_unchanged_rerun_changes_no_record(tmp_path):
    """A same-day rerun meets the frozen file ("same") and the scored day's summary: the site-day file, the ledger and
    the archive stay as they are, and no data file is new."""
    data, site = tree(tmp_path), tmp_path / "site"
    archive = _archive()
    _put_frozen(archive, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    _published_ledger(site, ArchiveFreezer(archive, NOW).frozen(T))
    _build(data, site, ArchiveFreezer(archive, NOW))
    before = (_snapshot(site / "site-days", site / "forecasts", site / "days"), dict(archive.objects))
    again = _build(data, site, ArchiveFreezer(archive, LATER), now=LATER)
    assert again.unchanged and again.basket.unchanged and again.frozen.status == "same"
    assert (again.due, again.scored, again.data) == ([], [], [])
    assert (_snapshot(site / "site-days", site / "forecasts", site / "days"), dict(archive.objects)) == before


def test_a_stored_scores_file_that_differs_is_the_record(tmp_path):
    """Task 19's carry: on ScoresDiffer the archive's scores file is the record: its bytes go on the site, the summary is
    made from them, the build goes on, and the outcome names both SHA-256s for the alert after the upload."""
    first = _archive()
    _put_frozen(first, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    _build(tree(tmp_path / "a"), tmp_path / "a" / "site", ArchiveFreezer(first, NOW))
    made = first.objects[scores_archive_key(T)].body
    lines = gzip.decompress(made).decode().splitlines()
    header = lines[0].split(",")
    flipped = []
    for line in lines[1:]:
        cells = line.split(",")
        if cells[header.index("outcome")] == "1":
            cells[header.index("outcome")] = "0"
            for name in ("first_day", "promotion_id", "evidence"):
                cells[header.index(name)] = ""
        flipped.append(",".join(cells))
    other = gzip.compress(("\n".join([lines[0], *flipped]) + "\n").encode(), mtime=0)
    archive = _archive()
    _put_frozen(archive, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    archive.put_scores(T, other, datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    data, site = tree(tmp_path / "b"), tmp_path / "b" / "site"
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert outcome.scored == [T] and (site / scores_site_key(T)).read_bytes() == other
    assert archive.objects[scores_archive_key(T)].body == other
    (message,) = outcome.scores_differ
    assert _sha(other) in message and _sha(made) in message and T.isoformat() in message
    summary = read_summary(summary_path(data / "tables", T).read_bytes())
    assert summary.by_column[OSHER].outcome_1 == 0                    # from the stored file, not this run's rows
    assert archive_key(DAY) in archive.objects                         # and the build went on


def test_a_frozen_day_past_the_reads_reach_is_listed_never_scored(tmp_path):
    data, site = tree(tmp_path), tmp_path / "site"
    archive = _archive()
    _put_frozen(archive, FAR, datetime(2025, 9, 3, 10, 0, tzinfo=timezone.utc))
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert (outcome.due, outcome.scored, outcome.out_of_reach) == ([], [], [FAR])
    assert scores_archive_key(FAR) not in archive.objects
    assert _site_day(site)["out_of_reach"] == [FAR.isoformat()]


def test_a_day_with_no_forecast_freezes_nothing(tmp_path):
    """Forecasts begin on a column's 30th day of records (F6): a build with no forecast row freezes no file, and the
    ledger gains no line, so the record never starts on a day with nothing frozen."""
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    archive = _archive()
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert outcome.frozen is None and archive.objects == {}
    assert not (site / "forecasts").exists()
    assert _site_day(site)["forecasts"]["status"] == "none"
    assert "No forecasts have been frozen yet" in _text(site / "record.html")


def test_a_stored_file_for_a_day_now_without_forecasts_still_stops(tmp_path):
    """Question E: a rerun whose forecasts differ from the stored file stops, though this run made none."""
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    archive = _archive()
    _put_frozen(archive, DAY, NOW)
    with pytest.raises(shop_build.ForecastsDiffer):
        _build(data, site, ArchiveFreezer(archive, NOW))
    assert not (site / "index.html").exists() and not list(site.rglob("*.html"))


# ---- the Mac: the read-only freezer ----

def test_the_hand_build_freezes_nothing(tmp_path):
    """Question D: the Mac scores and freezes nothing: day T is due, and its synced file is not scored; today's file is
    not frozen; `data/forecasts`, `data/scores` and the summaries are untouched, and the published ledger gains no
    line (only the site run in Lambda adds one: a synced file's time never becomes a ledger's)."""
    data, site = tree(tmp_path), tmp_path / "site"
    frozen_t = _synced(data, T, _frozen_file(), datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    published = _published_ledger(site, frozen_t)
    before = _snapshot(data / "forecasts", data / "scores", data / "tables" / "scored")
    outcome = _build(data, site)
    assert (outcome.due, outcome.scored, outcome.frozen) == ([T], [], None)
    assert _snapshot(data / "forecasts", data / "scores", data / "tables" / "scored") == before
    assert not (data / "scores").exists() and not (data / "tables" / "scored").exists()
    assert (site / "forecasts" / "ledger.csv").read_bytes() == published
    assert not (site / "scores").exists() and not (site / site_key(DAY)).exists()
    assert _site_day(site)["forecasts"]["status"] == "none" and _site_day(site)["scored_days"] == []


def test_the_hand_build_publishes_the_archives_file_as_synced(tmp_path):
    """A day the site run froze: the Mac's build takes the synced file and the published ledger's line, as they are."""
    data, site = tree(tmp_path), tmp_path / "site"
    body = _frozen_file(((OSHER, EGGS),))
    frozen = _synced(data, DAY, body, STAMP)
    published = _published_ledger(site, frozen)
    outcome = _build(data, site)
    assert outcome.frozen.status == "same" and outcome.frozen.body == body
    assert not (site / site_key(DAY)).exists()                  # on the site already, with its ledger line
    assert (site / "forecasts" / "ledger.csv").read_bytes() == published
    assert _site_day(site)["forecasts"]["sha256"] == _sha(body)
    assert "forecasts/ledger.csv" not in outcome.data and site_key(DAY) not in outcome.data


@pytest.mark.parametrize("case", ["named, not synced", "synced, not named", "another time"])
def test_the_hand_build_tells_not_synced_from_never_frozen(tmp_path, case):
    """Task 12's ruling: a day the published ledger names whose file the sync did not bring is "not synced", not
    "never frozen"; a synced file the ledger lacks, or one whose time is not the ledger's, is not the site run's
    record: the build stops and writes no page."""
    data, site = tree(tmp_path), tmp_path / "site"
    body = _frozen_file()
    frozen = Frozen(day=DAY, body=body, sha256=_sha(body), frozen_at=STAMP, on_time=True, status="same")
    if case == "named, not synced":
        _published_ledger(site, frozen)
    elif case == "synced, not named":
        _synced(data, DAY, body, STAMP)
    else:
        _synced(data, DAY, body, STAMP + timedelta(seconds=1))
        _published_ledger(site, frozen)
    with pytest.raises(NotSynced) as raised:
        _build(data, site)
    assert "2026-01-01" in str(raised.value)
    assert not list(site.rglob("*.html")) and not site_day_path(site, DAY).exists()


# ---- what the build reads, and the extraction ----

def test_the_build_names_its_inputs(tmp_path):
    """The site-day file names every items table the build read (the day's five and Osher Ad's 40 before it) by its key,
    and the registry it carried forward."""
    data, site = tree(tmp_path), tmp_path / "site"
    older = covered_path(data / "tables", DAY - timedelta(days=150))
    older.parent.mkdir(parents=True)
    shutil.copy(covered_path(data / "tables", DAY - timedelta(days=100)), older)     # the latest before the day is read
    _build(data, site)
    inputs = _site_day(site)["inputs"]
    tables = [f"tables/items/chain={slug}/date={DAY.isoformat()}/items.parquet" for slug in SLUGS]
    tables += [f"tables/items/chain=osherad/date={(DAY - timedelta(days=n)).isoformat()}/items.parquet"
               for n in range(1, 41)]
    assert inputs == {"items_tables": sorted(tables), "registry": "tables/covered/date=2025-09-23/covered.parquet"}
    assert covered_path(data / "tables", DAY).is_file()               # the day's registry, carried forward
    chains = _site_day(site)["chains"]
    assert chains[OSHER] == {"promotions_error": None,
                             "items_table": "tables/items/chain=osherad/date=2026-01-01/items.parquet"}


def test_the_day_is_extracted_when_missing_and_kept_otherwise(tmp_path):
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    kept = {slug: items_path(data / "tables", slug, DAY).stat().st_mtime_ns for slug in SLUGS}
    first = _build(data, site)
    assert first.extraction_seconds == {slug: None for slug in SLUGS}
    assert {slug: items_path(data / "tables", slug, DAY).stat().st_mtime_ns for slug in SLUGS} == kept
    items_path(data / "tables", "ramilevy", DAY).unlink()
    again = _build(data, site, now=LATER)
    assert [slug for slug, took in again.extraction_seconds.items() if took is not None] == ["ramilevy"]
    assert items_path(data / "tables", "ramilevy", DAY).is_file()
    table_path(data / "tables", "yochananof", DAY).unlink()
    third = _build(data, site, now=LATER)
    assert [slug for slug, took in third.extraction_seconds.items() if took is not None] == ["yochananof"]
    rebuilt = _build(data, site, now=LATER, rebuild=True)
    assert all(isinstance(took, float) for took in rebuilt.extraction_seconds.values())
    assert rebuilt.basket.extraction_seconds == {slug: None for slug in SLUGS}   # extracted once (N9)


def test_the_site_run_never_extracts(tmp_path):
    """`extract=False` (the Lambda, having fetched the tables): a missing table of the day stops the build, never an
    extraction of a raw folder that may be absent."""
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    items_path(data / "tables", "carrefour", DAY).unlink()
    with pytest.raises(MissingTable, match="carrefour"):
        _build(data, site, extract=False)
    assert not items_path(data / "tables", "carrefour", DAY).exists()
    data, site = tree(tmp_path / "prices", history=False), tmp_path / "prices" / "site"
    table_path(data / "tables", "shufersal", DAY).unlink()
    with pytest.raises(MissingTable, match="shufersal"):
        _build(data, site, extract=False)
    assert not table_path(data / "tables", "shufersal", DAY).exists()


def test_a_chains_promotions_error_is_the_chains(tmp_path):
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    error = "carrefour: PromoFull7290055700007-001-002-20260101-0800.gz: RewardType 7 not seen in the chain's files"
    _table(data / "tables", "carrefour", DAY, rows=[_row("carrefour-market", MILK, "7.35")], error=error)
    outcome = _build(data, site)
    assert outcome.promotions_errors == {"carrefour": error}               # the whole message, for the alert
    assert _site_day(site)["chains"]["carrefour"]["promotions_error"] == {
        "kind": "format changed", "file": "PromoFull7290055700007-001-002-20260101-0800.gz", "field": "RewardType"}
    assert "Promotions from Carrefour's files could not be read today." in _text(site / page_path(MILK))


# ---- the basket, B12 and the pages as published ----

def test_the_basket_day_and_basket_html(tmp_path):
    """The basket priced as ever (its day file, its record), its page `basket.html` in the site's frame; the basket's
    own index page and marker are not written."""
    data, site = tree(tmp_path), tmp_path / "site"
    outcome = _build(data, site)
    assert json.loads((site / "days" / "2026-01-01.json").read_text(encoding="utf-8")) == outcome.basket.public
    assert outcome.basket.record_path.is_file() and not (site / ".basket-site").exists()
    basket = _text(site / "basket.html")
    assert "Lowest listed total today: Osher Ad, ₪22.65." in basket
    assert "The product pages show Shufersal's and Carrefour's store formats apart" in basket


def test_a_refused_build_writes_no_page(tmp_path):
    """B12: a day published with other numbers stops the build with RevisionNeeded, and the site folder keeps every
    page as it was (the product pages are drawn in the one pass beside the forecasts, kept apart until the day is
    published)."""
    data, site = tree(tmp_path), tmp_path / "site"
    _build(data, site)
    published = json.loads(site_day_path(site, DAY).read_text(encoding="utf-8"))
    site_day_path(site, DAY).write_text(json.dumps(published | {"counts": {"promotions": 9, "products": 9,
                                                                           "below": 9}}), encoding="utf-8")
    for page in site.rglob("*.html"):
        page.write_text("OLD", encoding="utf-8")
    pages = _snapshot(site)
    with pytest.raises(RevisionNeeded, match="counts differ"):
        _build(data, site, now=AFTER_LATER)
    assert _snapshot(site) == pages
    revised = _build(data, site, now=AFTER_LATER, revise="a counting fix")
    assert _site_day(site)["revised"]["reason"] == "a counting fix" and not revised.unchanged
    assert (site / page_path(MILK)).read_text(encoding="utf-8") != "OLD"


def test_the_pages_show_the_day_as_published(tmp_path, monkeypatch):
    """An unchanged rerun given another collected-by time, at other code, keeps the site-day file as published, and
    every page shows the published time, the product pages included, and the method page the published fingerprint."""
    data, site = tree(tmp_path), tmp_path / "site"
    build_site(DAY, data, site, AFTER, "11:48", ReadOnlyFreezer(data), basket_path=BASKET, min_items=1)
    first = _site_day(site)["code_sha"]
    monkeypatch.setattr(shop_build, "code_fingerprint", lambda: "0123456789ab")
    again = build_site(DAY, data, site, AFTER_LATER, "15:00", ReadOnlyFreezer(data), basket_path=BASKET, min_items=1)
    assert again.unchanged and _site_day(site)["collected_by"] == "11:48"
    method = (site / "method.html").read_text(encoding="utf-8")
    assert first in method and "0123456789ab" not in method
    for path in (site / "index.html", site / "record.html", site / page_path(MILK), site / page_path(A),
                 next((site / "browse").glob("*.html"))):
        page = _text(path)
        assert "collected by 11:48 Israel time" in page and "15:00" not in page


# ---- the command ----

def test_the_command_prints_what_it_did(tmp_path, capsys):
    data, site = tree(tmp_path), tmp_path / "site"
    args = ["--day", "2026-01-01", "--data", str(data), "--site", str(site), "--basket", str(BASKET), "--min-items", "1",
            "--collected-by", "11:48"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "osherad: tables kept" in out
    assert "covered: 5 products" in out and "pages: 5 product pages" in out
    assert "forecasts: none frozen for 2026-01-01" in out
    assert f"published: {site_day_path(site, DAY)}" in out and f"published: {site / 'days' / '2026-01-01.json'}" in out
    assert "front page: 1 row" in out
    assert _site_day(site)["collected_by"] == "11:48"
    assert main(args) == 0
    assert f"unchanged: {site_day_path(site, DAY)}" in capsys.readouterr().out
    items_path(data / "tables", "ramilevy", DAY).unlink()
    assert main(args) == 0
    out = capsys.readouterr().out
    assert re.search(r"^ramilevy: extracted in \d+\.\d s$", out, re.MULTILINE)
    published = json.loads(site_day_path(site, DAY).read_text(encoding="utf-8"))
    site_day_path(site, DAY).write_text(json.dumps(published | {"counts": {"promotions": 0, "products": 0,
                                                                           "below": 0}}), encoding="utf-8")
    assert main(args) == 1
    assert "counts differ" in capsys.readouterr().err
    assert main(args + ["--revise", "a counting fix"]) == 0
    assert f"revised: {site_day_path(site, DAY)}" in capsys.readouterr().out
    (data / archive_key(DAY)).parent.mkdir(parents=True)
    (data / archive_key(DAY)).write_bytes(_frozen_file())
    assert main(args) == 1
    assert "2026-01-01" in capsys.readouterr().err


# ---- the one pass's counts ----

def test_the_count_line_counts_promotions_listed_across_a_column_today(tmp_path):
    """Question A under S1: a promotion listed across a column today counts once a chain and id (at Deal and Sheli,
    one); a link with no kind, one at some stores, one not running today, one on a hole and one on a column whose
    promotions were not read count nothing; the products are the barcodes those promotions are on."""
    deal, sheli, express, universe = "shufersal-deal", "shufersal-sheli", "shufersal-express", "shufersal-universe"
    days = product._days(holes={(express, product.DAY)}, promo_holes={(universe, product.DAY)})
    pages = shop_build._Pages({}, History(product.DAY, days, {}), "12:03", {}, {}, tmp_path)
    tomorrow = product.DAY + timedelta(days=1)

    def pair(code, column, *structs):
        return replace(product._pair(column, product._listed("10.00"), promotions=list(structs)), code=code)

    one = product._struct("7.90", promotion_id="1")
    for each in (pair("1", deal, one, product._struct(None, kind=None, valid=False, promotion_id="2"),
                      product._struct("8.00", wide=False, promotion_id="3")),
                 pair("1", sheli, one),
                 pair("2", express, product._struct("7.90", promotion_id="4")),
                 pair("3", "ramilevy", one, product._struct("7.90", start=tomorrow, promotion_id="5")),
                 pair("4", universe, product._struct("7.90", promotion_id="6", restrictions=["club"])),
                 pair("5", deal, product._struct("8.00", wide=False, promotion_id="7")),
                 pair("6", "carrefour-city", product._struct("7.90", wide=False, start=tomorrow, promotion_id="8",
                                                            restrictions=["club"]))):
        pages(each)
    pages.finish()
    assert pages.promotions == {("shufersal", "1"), ("ramilevy", "1")}
    assert pages.counts() == Counts(promotions=2, products=2, below=0) and pages.products == {"1", "3"}
    # Carrefour's files mark a restricted promotion (not running, not across: still marked); Universe's restriction is
    # from too few promotion files and marks nothing; every chain's promotions are read at some column today
    assert pages.marking == {"carrefour"}
    assert pages.marking_none() == ["shufersal", "ramilevy", "osherad", "yochananof"]
    unread = product._days(promo_holes={(column.key, product.DAY) for column in COLUMNS if column.slug == "osherad"})
    assert shop_build._Pages({}, History(product.DAY, unread, {}), "12:03", {}, {}, tmp_path / "x").marking_none() == [
        "shufersal", "ramilevy", "carrefour", "yochananof"]           # never said of a chain not read today


def test_the_command_says_what_the_hand_build_left_to_the_site_run(tmp_path, capsys):
    """The day's file as synced, the days due that only the site run scores, those out of reach, a chain's promotions
    not read: each said in a line, with no product name."""
    data, site = tree(tmp_path), tmp_path / "site"
    error = "carrefour: PromoFull7290055700007-001-002-20260101-0800.gz: RewardType 7 not seen in the chain's files"
    _table(data / "tables", "carrefour", DAY, rows=[_row("carrefour-market", MILK, "7.35")], error=error)
    body = _frozen_file(((OSHER, EGGS),))
    frozen = [_synced(data, T, _frozen_file(), datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc)),
              _synced(data, FAR, _frozen_file(), datetime(2025, 9, 3, 10, 0, tzinfo=timezone.utc)),
              _synced(data, DAY, body, STAMP)]
    _published_ledger(site, *frozen)
    assert main(["--day", "2026-01-01", "--data", str(data), "--site", str(site), "--basket", str(BASKET),
                 "--min-items", "1", "--collected-by", "11:48"]) == 0
    out = capsys.readouterr().out
    assert (f"forecasts: same, 1 row, SHA-256 {_sha(body)}, S3 time 2026-01-01T10:33:07Z") in out
    assert "due, scored only by the site run in Lambda: 2025-12-18" in out
    assert "out of reach, never scored: 2025-09-03" in out
    assert f"promotions not read: {error}" in out
    assert "data files new to the site: site-days/2026-01-01.json, days/2026-01-01.json" in out
    assert "חלב" not in out and "ספגטי" not in out



def test_the_scorecard_reads_only_the_days_the_build_can_know_of(tmp_path):
    """F3: a summary of a day whose window closes after the build's day (a later build's) is no part of this day's
    record, so an earlier day's rebuild keeps its scorecard and its scored days."""
    data, site = tree(tmp_path), tmp_path / "site"
    for seen in (T, DAY - timedelta(days=13)):
        path = summary_path(data / "tables", seen)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(summary_json(DaySummary(day=seen, frozen_at=datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc),
                                                 on_time=True, model_version="1", target_version="1", by_column={})))
    _build(data, site)
    assert _site_day(site)["scored_days"] == [T.isoformat()]


def test_the_site_publishes_the_scores_file_the_archive_holds(tmp_path):
    """Task 13's carry: the site's scores file is what `put_scores` returns: a stored file of the same rows in other
    gzip bytes is published as stored."""
    first = _archive()
    _put_frozen(first, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    _build(tree(tmp_path / "a"), tmp_path / "a" / "site", ArchiveFreezer(first, NOW))
    made = first.objects[scores_archive_key(T)].body
    stored = gzip.compress(gzip.decompress(made), compresslevel=1, mtime=0)
    assert stored != made                                                # the premise
    archive = _archive()
    _put_frozen(archive, T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    archive.put_scores(T, stored, datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    data, site = tree(tmp_path / "b"), tmp_path / "b" / "site"
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert (site / scores_site_key(T)).read_bytes() == stored and outcome.scores_differ == []



# ---- finding 1: a day the Mac publishes without forecasts stays so ----

def test_the_hand_build_stops_before_the_cutoff_on_a_day_the_site_run_can_freeze(tmp_path):
    """Finding 1's ruling (a): a day with forecasts, no synced file and no ledger line, before its cutoff, is one the
    site run can still freeze; a hand build that published it without would leave the site run's freeze unpublishable,
    so it stops, writing no page, and says what to do."""
    data, site = tree(tmp_path), tmp_path / "site"
    with pytest.raises(NotFrozenYet) as raised:
        _build(data, site, now=NOW)
    message = str(raised.value)
    assert "2026-01-01" in message and "site run" in message and "midnight" in message
    assert not list(site.rglob("*.html")) and not site_day_path(site, DAY).exists()
    assert _build(data, site, now=datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc)).frozen is None   # at the cutoff


def test_a_day_with_no_forecast_builds_by_hand_before_the_cutoff(tmp_path):
    data, site = tree(tmp_path, history=False), tmp_path / "site"
    assert _build(data, site, now=NOW).frozen is None


def test_the_site_run_never_freezes_a_day_published_without_forecasts(tmp_path):
    """Finding 1's ruling (b): the site-day file of the day already says forecasts "none": the site run freezes
    nothing, though before the cutoff by its clock, and the day goes up unchanged."""
    data, site = tree(tmp_path), tmp_path / "site"
    _build(data, site)                                                  # the Mac, past the cutoff: "none"
    assert _site_day(site)["forecasts"]["status"] == "none"
    archive = _archive()
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert outcome.frozen is None and archive_key(DAY) not in archive.objects and outcome.unchanged
    assert not (site / "forecasts").exists()


def test_a_hand_build_past_the_cutoff_then_the_site_run_freezes_nothing_and_refuses_nothing(tmp_path):
    """The whole sequence: the Mac builds the day after its midnight, then the site run builds it: no freeze, no
    refusal, the site-day file as the Mac published it."""
    data, site = tree(tmp_path), tmp_path / "site"
    _build(data, site, now=AFTER)
    published = site_day_path(site, DAY).read_bytes()
    archive = _archive()
    outcome = _build(data, site, ArchiveFreezer(archive, AFTER_LATER), now=AFTER_LATER)
    assert (outcome.frozen, outcome.unchanged, archive.objects) == (None, True, {})
    assert site_day_path(site, DAY).read_bytes() == published
    # a day published without forecasts is no day the site run can still freeze: the Mac never stops on it
    assert _build(data, site, now=NOW).unchanged


# ---- a day out of reach alerts once ----

def test_a_day_first_out_of_reach_is_told_apart_from_those_already_out(tmp_path):
    """The ruling on the reviewer's (b): the site-day file lists every frozen day out of the read's reach, and the
    outcome names apart those the previous published site-day file did not list, the only ones the site run's /fail
    is for."""
    data, site = tree(tmp_path), tmp_path / "site"
    archive = _archive()
    later = DAY - timedelta(days=100)
    _put_frozen(archive, FAR, datetime(2025, 9, 3, 10, 0, tzinfo=timezone.utc))
    _put_frozen(archive, later, datetime(2025, 9, 23, 10, 0, tzinfo=timezone.utc))
    for seen, listed in ((DAY - timedelta(days=3), []), (DAY - timedelta(days=2), [FAR.isoformat()])):
        path = site_day_path(site, seen)                                # the latest before the day is the previous
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"day": seen.isoformat(), "out_of_reach": listed}), encoding="utf-8")
    for stray in ("20251231.json", "notes.json"):                       # no site-day file's name: passed over
        (site / "site-days" / stray).write_text(json.dumps({"out_of_reach": []}), encoding="utf-8")
    outcome = _build(data, site, ArchiveFreezer(archive, NOW))
    assert (outcome.out_of_reach, outcome.newly_out_of_reach) == ([FAR, later], [later])
    assert _site_day(site)["out_of_reach"] == [FAR.isoformat(), later.isoformat()]
    again = _build(data, site, ArchiveFreezer(archive, LATER), now=LATER)   # the day's own file is no previous one
    assert again.unchanged and again.newly_out_of_reach == [later]
    alone = tmp_path / "alone"
    first = _build(tree(alone), alone / "site", ArchiveFreezer(archive, NOW))
    assert first.newly_out_of_reach == [FAR, later]                     # no earlier file: every one is new

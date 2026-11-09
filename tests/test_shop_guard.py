"""The shopper site's publish guard (`shopper.guard`; the plan's Task 21): before any upload, a build may not replace
a published forecasts or scores file, shorten the published ledger, publish a site-day file that is not a revision, or
lose a published product page, and its record page must show the scorecard its newest site-day file holds.

A build is made as `shopper.build` leaves one: the basket's day file, the site-day file (`tests/test_siteday.py`'s), the
day's forecasts file (`tests/test_freeze.py`'s) and the ledger naming it, a scores file, `record.html` drawn by
`render_record` from the site-day file's scorecard, and a stand-in page for each product. The published folder is a copy
of the build's data folders, as `scripts/publish.sh` copies them from the bucket. Names and barcodes are synthetic."""
import gzip
import re
import shutil
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

from basket.page import render_day
from shopper.freeze import ArchiveFreezer, ledger, scores_site_key, site_key
from shopper.guard import guard_site, main
from shopper.pages import Counts, render_record
from shopper.record import scorecard
from shopper.siteday import publish_site_day, write_site_day
from test_freeze import forecasts_of
from test_guard import NAME as BASKET_DAY, published_day, revision_of
from test_product import DAY, _days
from test_shop_build import _templates      # the build's tree is made once a module (autouse there, so here too)
from test_siteday import DEAL, FROZEN_AT, LATER, _card, _frozen, _site_day
import test_shop_build as built

SITE_DAY = f"site-days/{DAY.isoformat()}.json"
PAGES = ("p/2000000000046.html", "p/2000000000053.html")
SCORED = date(2026, 11, 5)
SCORES = gzip.compress(b"day,column,code,p,outcome\n2026-11-05,shufersal-deal,2000000000046,0.5,1\n", mtime=0)
SYNC = "run scripts/sync.sh first"
NOT_A_REVISION = f"{{}} differs from the published day and is not a revision of it: {SYNC}"
DATA_FOLDERS = ("days", "site-days", "forecasts", "scores")


def record_of(shown: dict) -> str:
    """The record page the build draws from the site-day file `shown`: its scorecard, the ledger's day, its files."""
    return render_record(shown["scorecard"], {DAY: FROZEN_AT}, ["forecasts/ledger.csv", site_key(DAY)],
                         _days(), DAY, "11:48")


def a_site(root: Path, shown: dict | None = None, pages=PAGES) -> Path:
    """A build's site folder (the module's docstring); `shown` the site-day file, as `_site_day` gives it."""
    site = root / "site"
    shown = _site_day() if shown is None else shown
    write_site_day(shown, site)
    files = {f"days/{BASKET_DAY}": render_day(published_day()).encode(), site_key(DAY): _frozen().body,
             scores_site_key(SCORED): SCORES, "forecasts/ledger.csv": ledger(None, _frozen()),
             "record.html": record_of(shown).encode(), **{key: b"<html></html>" for key in pages}}
    for key, body in files.items():
        (site / key).parent.mkdir(parents=True, exist_ok=True)
        (site / key).write_bytes(body)
    return site


def a_bucket(root: Path, site: Path) -> Path:
    """The published folder: a copy of the site's data folders, as the bucket holds them."""
    bucket = root / "published"
    bucket.mkdir()
    for folder in DATA_FOLDERS:
        if (site / folder).is_dir():
            shutil.copytree(site / folder, bucket / folder)
    return bucket


def both(tmp_path: Path, **more) -> tuple[Path, Path]:
    """A build and the bucket as it published that same build."""
    site = a_site(tmp_path, **more)
    return site, a_bucket(tmp_path, site)


def next_day_ledger(published: bytes) -> bytes:
    """The ledger with the next day's line added, as the build adds it."""
    return ledger(published, replace(_frozen(), day=DAY + timedelta(days=1), frozen_at=FROZEN_AT + timedelta(days=1)))


def revised_site_day(tmp_path: Path, first: dict) -> dict:
    """`first` revised as the build revises a published site-day file: other numbers and a reason."""
    shown, _, revised = publish_site_day(_site_day(counts=Counts(4, 2, 1)), _published(tmp_path, first), LATER,
                                         "a reader fix")
    assert revised
    return shown


def _published(tmp_path: Path, shown: dict) -> Path:
    write_site_day(shown, tmp_path / "earlier")
    return tmp_path / "earlier"


# ---- the build as published ----

def test_an_empty_bucket_passes(tmp_path):
    site = a_site(tmp_path)
    assert guard_site(site, tmp_path / "absent", PAGES) == []      # the bucket is empty before the first upload
    (tmp_path / "empty").mkdir()
    assert guard_site(site, tmp_path / "empty", ()) == []


def test_a_build_equal_to_the_published_site_passes(tmp_path):
    site, bucket = both(tmp_path)
    assert guard_site(site, bucket, PAGES) == []


def test_a_build_that_adds_to_the_published_site_passes(tmp_path):
    """A new day's files, a new forecasts file, a longer ledger, a new product: all new, none replaced; and a published
    file the build lacks is left alone (nothing deletes)."""
    site, bucket = both(tmp_path)
    (site / site_key(DAY + timedelta(days=1))).write_bytes(forecasts_of(Fraction(1, 3)))
    (site / scores_site_key(SCORED + timedelta(days=1))).write_bytes(SCORES + b"\x00")
    (site / "site-days" / "2026-11-19.json").write_text(render_day(_site_day(day=DAY - timedelta(days=1))))
    (site / "forecasts/ledger.csv").write_bytes(next_day_ledger((site / "forecasts/ledger.csv").read_bytes()))
    (site / "p/2000000000060.html").write_text("<html></html>")
    (bucket / "scores/2026-10-01.csv.gz").write_bytes(SCORES)
    assert guard_site(site, bucket, PAGES) == []


# ---- the basket's days and the site's days ----

def test_a_basket_day_that_is_not_a_revision_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    (site / "days" / BASKET_DAY).write_text(render_day(published_day() | {"collected_by": "10:45"}))
    assert guard_site(site, bucket, PAGES) == [NOT_A_REVISION.format(f"days/{BASKET_DAY}")]


def test_a_basket_day_that_is_a_revision_passes(tmp_path):
    site, bucket = both(tmp_path)
    (site / "days" / BASKET_DAY).write_text(render_day(revision_of(published_day())))
    assert guard_site(site, bucket, PAGES) == []


def test_a_site_day_that_is_not_a_revision_is_refused(tmp_path):
    """The basket's rule over `site-days/`, a problem naming that folder: other numbers with no revision recorded, and
    a revision that does not add to the published file's, are both refused."""
    first = _site_day()
    other = _site_day(counts=Counts(4, 2, 1))
    site, bucket = both(tmp_path / "other", shown=other)
    write_site_day(first, bucket)
    assert guard_site(site, bucket, PAGES) == [NOT_A_REVISION.format(SITE_DAY)]
    revised = revised_site_day(tmp_path / "stale", first)
    site, bucket = both(tmp_path / "stale", shown=revised)
    write_site_day(revised, bucket)          # the bucket already holds this revision: the build adds none to it
    other_revision = revised | {"counts": {"promotions": 9, "products": 9, "below": 9}}
    write_site_day(other_revision, site)
    assert guard_site(site, bucket, PAGES) == [NOT_A_REVISION.format(SITE_DAY)]


def test_a_site_day_that_is_a_revision_passes(tmp_path):
    first = _site_day()
    revised = revised_site_day(tmp_path / "revised", first)
    site, bucket = both(tmp_path / "revised", shown=revised)
    write_site_day(first, bucket)
    assert guard_site(site, bucket, PAGES) == []


def test_a_site_day_with_more_revisions_and_no_reason_is_refused(tmp_path):
    first = _site_day()
    revised = revised_site_day(tmp_path / "revised", first)
    site, bucket = both(tmp_path / "revised", shown=revised | {"revised": None})
    write_site_day(first, bucket)
    assert guard_site(site, bucket, PAGES) == [NOT_A_REVISION.format(SITE_DAY)]


def test_an_unreadable_site_day_is_refused_naming_the_file(tmp_path):
    site, bucket = both(tmp_path)
    (site / SITE_DAY).write_text("{")
    problems = guard_site(site, bucket, PAGES)
    assert f"{site / SITE_DAY}: not a day file (a JSON object)" in problems


# ---- the forecasts and scores files ----

def test_a_replaced_forecasts_file_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    (site / site_key(DAY)).write_bytes(forecasts_of(Fraction(1, 3)))
    assert guard_site(site, bucket, PAGES) == [
        f"{site_key(DAY)} differs from the published file: a published forecasts file is never replaced"]


def test_the_same_rows_in_other_bytes_are_a_replaced_forecasts_file(tmp_path):
    """The rule is on bytes: the ledger holds the file's SHA-256, so the same rows in another gzip are another file,
    and so is a file of the same length with one byte changed."""
    site, bucket = both(tmp_path)
    body = (site / site_key(DAY)).read_bytes()
    (site / site_key(DAY)).write_bytes(gzip.compress(gzip.decompress(body), compresslevel=1, mtime=0))
    assert len(guard_site(site, bucket, PAGES)) == 1
    (site / site_key(DAY)).write_bytes(body[:20] + bytes([body[20] ^ 1]) + body[21:])
    assert len(guard_site(site, bucket, PAGES)) == 1


def test_a_replaced_scores_file_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    (site / scores_site_key(SCORED)).write_bytes(SCORES + b"\x00")
    assert guard_site(site, bucket, PAGES) == [
        f"{scores_site_key(SCORED)} differs from the published file: a published scores file is never replaced"]


def test_a_forecasts_or_scores_file_the_bucket_lacks_or_holds_alone_passes(tmp_path):
    site, bucket = both(tmp_path)
    (bucket / site_key(DAY)).unlink()
    (bucket / scores_site_key(SCORED)).unlink()
    assert guard_site(site, bucket, PAGES) == []
    (site / site_key(DAY)).unlink()
    (site / scores_site_key(SCORED)).unlink()
    (bucket / site_key(DAY)).write_bytes(forecasts_of())
    assert guard_site(site, bucket, PAGES) == []


def test_the_ledger_is_not_a_forecasts_file(tmp_path):
    """`forecasts/ledger.csv` is judged by its own rule (it grows), never as a file that may not change."""
    site, bucket = both(tmp_path)
    (site / "forecasts/ledger.csv").write_bytes(next_day_ledger((site / "forecasts/ledger.csv").read_bytes()))
    assert guard_site(site, bucket, PAGES) == []


# ---- the ledger ----

def test_a_ledger_that_does_not_extend_the_published_one_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    longer = next_day_ledger((bucket / "forecasts/ledger.csv").read_bytes())
    (bucket / "forecasts/ledger.csv").write_bytes(longer)                         # the bucket holds two days
    (site / "forecasts/ledger.csv").write_bytes(longer.split(b"\n", 2)[0] + b"\n" + longer.split(b"\n", 2)[1] + b"\n")
    shortened = guard_site(site, bucket, PAGES)
    assert shortened == ["forecasts/ledger.csv does not begin with the published ledger: it only gains lines"]
    (site / "forecasts/ledger.csv").write_bytes(longer.replace(b"2026-11-20,", b"2026-11-19,"))   # a line changed
    assert guard_site(site, bucket, PAGES) == shortened
    (site / "forecasts/ledger.csv").write_bytes(b"day,sha256,frozen_at\n")        # a header and no lines
    assert guard_site(site, bucket, PAGES) == shortened


def test_a_ledger_the_build_lacks_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    (site / "forecasts/ledger.csv").unlink()
    assert guard_site(site, bucket, PAGES) == [f"forecasts/ledger.csv is published and not in the build: {SYNC}"]


def test_a_ledger_that_extends_the_published_one_passes(tmp_path):
    site, bucket = both(tmp_path)
    assert guard_site(site, bucket, PAGES) == []                                   # the same ledger
    (site / "forecasts/ledger.csv").unlink()                                        # none published yet
    (bucket / "forecasts/ledger.csv").unlink()
    assert guard_site(site, bucket, PAGES) == []                                   # no ledger in either
    (site / "forecasts/ledger.csv").write_bytes(ledger(None, _frozen()))
    assert guard_site(site, bucket, PAGES) == []                                   # the first ledger


# ---- the record page ----

def test_a_record_page_that_differs_from_its_site_day_is_refused(tmp_path):
    """The page drawn from another scorecard differs in the column whose record is not the file's, and only there."""
    site, bucket = both(tmp_path)
    (site / "record.html").write_text(record_of({"scorecard": scorecard([])}))
    assert guard_site(site, bucket, PAGES) == [
        f"record.html differs from {SITE_DAY} in the scorecard of {DEAL}"]


def test_each_column_that_differs_is_named(tmp_path):
    site, bucket = both(tmp_path)
    page = (site / "record.html").read_text()
    for key in ("ramilevy", "shufersal-sheli"):
        section = re.search(rf'<section data-column="{key}">.*?</section>', page, re.DOTALL).group(0)
        page = page.replace(section, section.replace("does not hold", "holds", 1))
    (site / "record.html").write_text(page)
    assert guard_site(site, bucket, PAGES) == [
        f"record.html differs from {SITE_DAY} in the scorecard of {key}" for key in ("ramilevy", "shufersal-sheli")]


def test_a_record_page_that_differs_outside_the_columns_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    page = (site / "record.html").read_text()
    (site / "record.html").write_text(page.replace("Model versions scored so far", "Model versions", 1))
    assert guard_site(site, bucket, PAGES) == [
        f"record.html differs from {SITE_DAY} in the scorecard outside the columns"]


def test_a_record_page_without_the_scorecard_names_every_column(tmp_path):
    site, bucket = both(tmp_path)
    (site / "record.html").write_text("<html></html>")
    assert len(guard_site(site, bucket, PAGES)) == 9


def test_the_record_page_is_compared_with_the_newest_site_day_file(tmp_path):
    older = _site_day(day=DAY - timedelta(days=1), scorecard=scorecard([]))
    site, bucket = both(tmp_path)
    write_site_day(older, site)
    assert guard_site(site, bucket, PAGES) == []       # drawn from the newest file's scorecard
    (site / "record.html").write_text(record_of(older))
    assert guard_site(site, bucket, PAGES) == [f"record.html differs from {SITE_DAY} in the scorecard of {DEAL}"]


def test_a_record_page_cannot_be_compared_without_a_site_day_with_a_closed_scorecard(tmp_path):
    site, bucket = both(tmp_path)
    (site / SITE_DAY).write_text(render_day({"day": DAY.isoformat()}))
    assert guard_site(site, bucket, PAGES)[-1] == f"{SITE_DAY}: its scorecard cannot be rendered ('scorecard')"
    open_gate = _card()
    open_gate["columns"][DEAL]["gate"]["open"] = True
    (site / SITE_DAY).write_text(render_day(_site_day(scorecard=open_gate)))
    assert guard_site(site, bucket, PAGES)[-1] == (
        f"{SITE_DAY}: its scorecard cannot be rendered (the gate is open at {DEAL}, and step one shows no odds)")
    (site / SITE_DAY).write_text("not json")
    assert "cannot be rendered" in guard_site(site, bucket, PAGES)[-1]
    shutil.rmtree(site / "site-days")
    assert guard_site(site, bucket, PAGES)[-1] == (
        "no site-day file in the build: record.html has none to be compared with")
    (site / "record.html").unlink()
    assert guard_site(site, bucket, PAGES)[-1] == "record.html is not in the build"


# ---- the product pages (question H) ----

def test_a_build_missing_a_published_product_page_is_refused(tmp_path):
    site, bucket = both(tmp_path)
    (site / PAGES[1]).unlink()
    assert guard_site(site, bucket, PAGES) == [
        f"1 published product page is not in the build ({PAGES[1]}): a product page is never dropped; "
        "a build from a partly synced data folder lacks some"]
    many = [f"p/{n:013d}.html" for n in range(7)]
    problem = guard_site(site, bucket, [*PAGES[:1], *many])
    assert problem == [
        f"7 published product pages are not in the build ({', '.join(many[:5])} and 2 more): a product page is never "
        "dropped; a build from a partly synced data folder lacks some"]


def test_a_published_key_that_is_no_product_page_is_not_asked_for(tmp_path):
    site, bucket = both(tmp_path)
    others = ["None", "index.html", "browse/05d2.html", "q/2000000000046.html", "p/", "p/notes.txt"]
    assert guard_site(site, bucket, [*PAGES, *others]) == []


def test_an_earlier_day_with_fewer_covered_products_passes_the_guard(tmp_path):
    """An earlier day's build has the pages of the products covered by then, so some published page is not in it; its
    pages are not uploaded (`with_pages` false), so the rule does not apply (the second pre-flight's S17)."""
    site, bucket = both(tmp_path)
    (site / PAGES[1]).unlink()
    assert guard_site(site, bucket, PAGES, with_pages=False) == []
    assert len(guard_site(site, bucket, PAGES)) == len(guard_site(site, bucket, PAGES, with_pages=True)) == 1


def test_the_other_rules_apply_when_the_pages_do_not_go_up(tmp_path):
    site, bucket = both(tmp_path)
    (site / site_key(DAY)).write_bytes(forecasts_of(Fraction(1, 3)))
    assert len(guard_site(site, bucket, PAGES, with_pages=False)) == 1


# ---- all the rules, in order ----

def test_every_rule_is_checked_and_named_in_order(tmp_path):
    site, bucket = both(tmp_path)
    (site / "days" / BASKET_DAY).write_text(render_day(published_day() | {"collected_by": "10:45"}))
    write_site_day(_site_day(counts=Counts(4, 2, 1)), site)
    (site / site_key(DAY)).write_bytes(forecasts_of(Fraction(1, 3)))
    (site / scores_site_key(SCORED)).write_bytes(SCORES + b"\x00")
    (site / "forecasts/ledger.csv").unlink()
    (site / "record.html").unlink()
    (site / PAGES[0]).unlink()
    assert guard_site(site, bucket, PAGES) == [
        NOT_A_REVISION.format(f"days/{BASKET_DAY}"), NOT_A_REVISION.format(SITE_DAY),
        f"{site_key(DAY)} differs from the published file: a published forecasts file is never replaced",
        f"{scores_site_key(SCORED)} differs from the published file: a published scores file is never replaced",
        f"forecasts/ledger.csv is published and not in the build: {SYNC}",
        "record.html is not in the build",
        f"1 published product page is not in the build ({PAGES[0]}): a product page is never dropped; "
        "a build from a partly synced data folder lacks some"]


# ---- the build as `shopper.build` writes it ----

def test_a_build_passes_the_guard_against_its_own_published_copy_and_a_rerun_too(tmp_path):
    """The record page a real build draws (from the site-day file as built, then, on a rerun, as published and read
    back with its keys sorted) is the scorecard section the guard renders from the file on disk; the pages the build
    wrote are the published pages. Nothing about the build is refused by the guard it will meet."""
    data, site = built.tree(tmp_path), tmp_path / "site"
    archive = built._archive()
    built._put_frozen(archive, built.T, datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc))
    built._published_ledger(site, ArchiveFreezer(archive, built.NOW).frozen(built.T))
    outcome = built._build(data, site, ArchiveFreezer(archive, built.NOW))
    pages = [path for path in outcome.pages if path.startswith("p/")]
    assert len(pages) == 5 and "site-days/2026-01-01.json" in outcome.data
    assert guard_site(site, tmp_path / "empty-bucket", pages) == []
    bucket = a_bucket(tmp_path, site)
    again = built._build(data, site, ArchiveFreezer(archive, built.LATER), now=built.LATER)
    assert again.unchanged
    assert guard_site(site, bucket, pages) == []
    (site / pages[0]).unlink()
    assert len(guard_site(site, bucket, pages)) == 1


# ---- the command ----

def keys_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "keys.txt"
    path.write_text(text)
    return path


def test_main_exit_codes(tmp_path, capsys):
    site, bucket = both(tmp_path)
    keys = keys_file(tmp_path, "\n".join(PAGES) + "\n")
    assert main([str(site), str(bucket), str(keys)]) == 0
    assert capsys.readouterr() == ("", "")
    (site / PAGES[1]).unlink()
    assert main([str(site), str(bucket), str(keys)]) == 1
    assert capsys.readouterr() == ("", guard_site(site, bucket, PAGES)[0] + "\n")
    (site / site_key(DAY)).write_bytes(forecasts_of(Fraction(1, 3)))
    assert main([str(site), str(bucket), str(keys)]) == 1
    assert capsys.readouterr().err.count("\n") == 2          # one problem a line


def test_main_reads_the_keys_split_by_any_white_space(tmp_path, capsys):
    """`aws s3api list-objects-v2 --output text` may put the keys on one tab-separated line or several: the pages the
    build has pass whichever way the keys come, and the one it lacks is named alone."""
    site, bucket = both(tmp_path)
    for text in (f"{PAGES[0]}\t{PAGES[1]}\n", f"{PAGES[0]}\n\n{PAGES[1]}", f"{PAGES[0]} {PAGES[1]}", PAGES[0], ""):
        assert main([str(site), str(bucket), str(keys_file(tmp_path, text))]) == 0, text
    (site / PAGES[1]).unlink()
    capsys.readouterr()
    for text in (f"{PAGES[0]}\t{PAGES[1]}\n", f"{PAGES[0]}\n\n{PAGES[1]}"):
        assert main([str(site), str(bucket), str(keys_file(tmp_path, text))]) == 1
        assert f"1 published product page is not in the build ({PAGES[1]})" in capsys.readouterr().err


def test_main_stops_on_a_folder_or_file_that_is_not_there(tmp_path, capsys):
    site, bucket = both(tmp_path)
    keys = keys_file(tmp_path, "")
    assert main([str(tmp_path / "absent"), str(bucket), str(keys)]) == 2
    assert capsys.readouterr().err == f"no folder at {tmp_path / 'absent'}: no site to guard\n"
    assert main([str(site), str(bucket), str(tmp_path / "no-keys.txt")]) == 2
    assert capsys.readouterr().err == f"no file at {tmp_path / 'no-keys.txt'}: no list of the published product pages\n"
    assert main([str(site), str(tmp_path / "absent"), str(keys)]) == 0        # an empty bucket holds nothing
    capsys.readouterr()
    assert main([str(site), str(bucket)]) == 2
    assert capsys.readouterr().err.startswith("usage: python -m shopper.guard")

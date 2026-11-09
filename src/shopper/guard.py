"""The shopper site's publish guard: before any upload, a build may not replace a published record, shorten the
published ledger, show a record page its site-day file does not hold, or lose a published product page
(docs/shopper-site.md, "Checks before upload"; the plan's Task 21, its question H and the second pre-flight's S17).

    PYTHONPATH=src python -m shopper.guard site <published data, copied from the bucket> <file of published p/ keys>

A build compares its numbers with the files in its own `site/` folder; a build into a `site/` that `scripts/sync.sh`
did not fill, or from a data folder only partly synced, sees none of what is published and would write over it. The
upload scripts (the plan's Tasks 22 and 23) therefore copy the bucket's `days/`, `site-days/`, `forecasts/` and
`scores/` into a temporary folder and list its `p/` keys into a file, and run this before any upload. `guard_site`
gives the problems, one a line, in the order below; a published file the build lacks passes (nothing deletes):

1. `days/`, the basket's day files, and 2. `site-days/`, the site's: by `basket.guard.guard_days`, whose test serves
   both folders. A day file that differs from the published one must be a revision of it (`revised` an object, and more
   `revisions` than the published file has); an unreadable file is named. A problem in `site-days/` names that folder.
3. `forecasts/<day>.csv.gz` and 4. `scores/<day>.csv.gz`: a file the published folder holds must have the same bytes.
   The archive's file is the record (a rerun after a failed upload, or a stored scores file whose rows differ, publishes
   the archive's bytes), so any other bytes are another file, even the same rows in another gzip. A file the published
   folder lacks is new.
5. `forecasts/ledger.csv`: the published ledger must be the start of the build's, byte for byte (the ledger only gains
   lines, `shopper.freeze.ledger`); a build that lacks the published ledger is refused, since its record page would
   name no frozen day. No published ledger, nothing to keep.
6. `record.html`: its scorecard section must be the one `shopper.pages.scorecard_section` gives for the scorecard in the
   newest site-day file of the build, the same renderer that drew the page, so a page drawn from other numbers, or
   changed by hand, is refused. A problem names each column whose section differs, or says the difference is outside
   the columns. A page or a site-day file that is missing, a site-day file that does not read or whose scorecard cannot
   be rendered (an open gate stops the page: step one shows no odds; a figure that is no number) is a problem too, never
   a crash.
7. `p/*.html`: every published product page key must be in the build (question H: a product that was covered keeps its
   page, and a build from a partly synced data folder lacks some). Only when the pages go up: a run for a day earlier
   than the site's latest uploads its data files and no page, and its registry lacks the products first covered after
   that day, so the caller passes `with_pages` false for it (S17) and this rule is not applied. A key that is not a
   `p/*.html` key is no product page.

Exit 0 with no problem; 1 with problems, one a line on stderr; 2 when the site folder or the file of keys is absent or
the arguments are not three. A published folder that does not exist holds nothing (the bucket is empty before the first
upload). The file of keys is read split on any white space, as `aws s3api list-objects-v2 --output text` may write it.
"""
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from basket.guard import guard_days
from shopper.build import LEDGER
from shopper.pages import scorecard_section

SHOWN = 5
SECTION = re.compile(r'<section data-column="([^"]+)">.*?</section>', re.DOTALL)


def guard_site(site_dir: Path, published_dir: Path, published_pages: Iterable[str],
               with_pages: bool = True) -> list[str]:
    """The problems, one line each, with uploading `site_dir` over `published_dir` and the published product page keys
    `published_pages` (the module's docstring); [] when none. `with_pages` is false for a run whose pages do not go
    up."""
    site, published = Path(site_dir), Path(published_dir)
    problems = guard_days(site / "days", published / "days")
    problems += [problem.replace("days/", "site-days/", 1) if problem.startswith("days/") else problem
                 for problem in guard_days(site / "site-days", published / "site-days")]
    problems += _replaced(site, published, "forecasts") + _replaced(site, published, "scores")
    problems += _ledger(site, published) + _record(site)
    return problems + (_pages(site, published_pages) if with_pages else [])


def _replaced(site: Path, published: Path, folder: str) -> list[str]:
    """The forecasts or scores files of the build whose bytes are not the published file's."""
    return [f"{folder}/{local.name} differs from the published file: a published {folder} file is never replaced"
            for local in sorted((site / folder).glob("*.csv.gz"))
            if (published / folder / local.name).is_file()
            and (published / folder / local.name).read_bytes() != local.read_bytes()]


def _ledger(site: Path, published: Path) -> list[str]:
    """The ledger of the build when it is not the published one with lines after it."""
    there, here = published / LEDGER, site / LEDGER
    if not there.is_file():
        return []
    if not here.is_file():
        return [f"{LEDGER} is published and not in the build: run scripts/sync.sh first"]
    if not here.read_bytes().startswith(there.read_bytes()):
        return [f"{LEDGER} does not begin with the published ledger: it only gains lines"]
    return []


def _record(site: Path) -> list[str]:
    """`record.html` against the scorecard of the newest site-day file (the module's docstring, 6)."""
    page = site / "record.html"
    if not page.is_file():
        return ["record.html is not in the build"]
    days = sorted((site / "site-days").glob("*.json"))
    if not days:
        return ["no site-day file in the build: record.html has none to be compared with"]
    name = f"site-days/{days[-1].name}"
    try:
        expected = scorecard_section(json.loads(days[-1].read_text(encoding="utf-8"))["scorecard"])
    except (ArithmeticError, ValueError, LookupError, TypeError, AttributeError) as error:   # not JSON, no scorecard,
        # an open gate, a figure that is no number, a version with no scored forecast and a filled bin
        return [f"{name}: its scorecard cannot be rendered ({error})"]
    shown = page.read_text(encoding="utf-8", errors="replace")
    if expected in shown:
        return []
    differing = [section.group(1) for section in SECTION.finditer(expected) if section.group(0) not in shown]
    return [f"record.html differs from {name} in the scorecard of {key}" for key in differing] or [
        f"record.html differs from {name} in the scorecard outside the columns"]


def _pages(site: Path, published_pages: Iterable[str]) -> list[str]:
    """One problem naming the published product pages the build lacks, the first few of them."""
    missing = sorted({key for key in published_pages
                      if key.startswith("p/") and key.endswith(".html") and not (site / key).is_file()})
    if not missing:
        return []
    count = len(missing)
    named = ", ".join(missing[:SHOWN]) + (f" and {count - SHOWN:,} more" if count > SHOWN else "")
    what = "1 published product page is" if count == 1 else f"{count:,} published product pages are"
    return [f"{what} not in the build ({named}): a product page is never dropped; "
            "a build from a partly synced data folder lacks some"]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m shopper.guard <site folder> <published data folder> <file of published p/ keys>",
              file=sys.stderr)
        return 2
    site, published, keys = Path(argv[0]), Path(argv[1]), Path(argv[2])
    if not site.is_dir():
        print(f"no folder at {site}: no site to guard", file=sys.stderr)
        return 2
    if not keys.is_file():
        print(f"no file at {keys}: no list of the published product pages", file=sys.stderr)
        return 2
    problems = guard_site(site, published, keys.read_text(encoding="utf-8").split())
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

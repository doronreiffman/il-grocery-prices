"""Check a built basket site before upload (docs/headline-basket.md, "Words" and "Before anything is published"):
no page says a NEVER phrase or "we", "our" or "us"; every page carries the credit line, `noindex` and no
script; the index page carries every ALWAYS phrase, and says REVISED on a revised day and only there.

    PYTHONPATH=src .venv/bin/python -m basket.check site

Runs before every upload (`scripts/publish.sh`); the shopper site's check (`shopper.check`) imports how a page is
read (`flatten`, `strip_tags`, `says`), the index page's rules (`index_problems`, run there over `basket.html`) and
`main`. Each `.html` under the folder is read two ways: as written (attributes and markup included) and with tags
stripped (the text a reader sees). In both, entities are unescaped, whitespace is collapsed, curly single quotes
(U+2018, U+2019) read as the straight apostrophe and case is ignored, so an entity, a tag, a line break or a
typographic apostrophe cannot hide a phrase. A NEVER phrase found in either is a problem, and so is REVISED on the
index page of a day not revised. A phrase that must be there (the credit line's fixed start, "Not shopping advice.",
and on the index page every ALWAYS phrase, and REVISED on a revised day) counts only in the text a reader sees.
`noindex` and `<script` are tags, looked for as written. The words "we", "our" and "us" are matched whole in the
text a reader sees; attributes hold chain slugs and codes, not words.

The day is revised when the newest `days/<day>.json` (ISO dates sort as dates) has `"revised"` set to an
object, as `basket.build` writes it; null, or no day file, is a day never revised. The marker
`.basket-site`, which `basket.page.build_site` writes, marks the folder as a basket site. Exit 0 clean; 1
with problems, one a line on stderr naming the file and the rule; 2 when there is no page to check.
"""
import html
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from basket.page import MARKER
from basket.words import ALWAYS, NEVER, REVISED

CREDIT_START = ("Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish "
                "under")  # `basket.words.credit`'s fixed start; the rest names the day and the time
NOT_ADVICE = "Not shopping advice."
NOTICES = {"the credit line": CREDIT_START, f'"{NOT_ADVICE}"': NOT_ADVICE}  # every page, in the text read
NOINDEX = '<meta name="robots" content="noindex">'
APOSTROPHES = ("\u2018", "\u2019")  # curly single quotes, read as the straight apostrophe
SCRIPT = "<script"
PRONOUNS = re.compile(r"\b(?:we|our|us)\b", re.I)
INDEX = "index.html"
DAY_FILES = "days/????-??-??.json"


class NoPages(Exception):
    """The folder has no HTML pages, so a clean check would prove nothing."""


def flatten(text: str) -> str:
    """`text` with entities unescaped, each run of whitespace one space and the ends trimmed, curly single quotes
    straightened, and in lower case. `str.split` and `str.replace` rather than a regular expression and
    `str.translate`, several times quicker on a page of non-ASCII text: the shopper site's check reads tens of
    thousands of pages before each upload."""
    flat = " ".join(html.unescape(text).split())
    for quote in APOSTROPHES:
        flat = flat.replace(quote, "'")
    return flat.lower()


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]*>", " ", text)


def says(phrase: str, *versions: str) -> bool:
    """Whether `phrase`, flattened, is in any of the flattened `versions` of a page."""
    return any(flatten(phrase) in version for version in versions)


def _day(site_dir: Path) -> tuple[str, dict | None]:
    """The newest day file's name and its `revised` (None for a day never revised); ("no day file", None)
    without one."""
    days = sorted(site_dir.glob(DAY_FILES))
    if not days:
        return "no day file", None
    newest = days[-1]
    return newest.relative_to(site_dir).as_posix(), json.loads(newest.read_text(encoding="utf-8")).get("revised")


def index_problems(site_dir: Path, written: str, read: str, page: str = INDEX) -> list[str]:
    """The index page's rules over a page read both ways, each problem naming `page`: every ALWAYS phrase, and
    REVISED exactly when the newest day file is revised."""
    problems = [f"{page}: missing an always phrase: {phrase!r}" for phrase in ALWAYS if not says(phrase, read)]
    day, revised = _day(site_dir)
    if isinstance(revised, dict):
        if not says(REVISED, read):
            problems.append(f"{page}: no {REVISED!r} on a revised day ({day})")
    elif says(REVISED, written, read):
        problems.append(f"{page}: {REVISED!r} on a day not revised ({day})")
    return problems


def check_site(site_dir: Path) -> list[str]:
    """The site's problems, one line each naming the file and the rule; [] for a site fit to upload."""
    site_dir = Path(site_dir)
    pages = sorted(path for path in site_dir.rglob("*.html") if path.is_file())
    if not pages:
        raise NoPages(f"no HTML pages under {site_dir}")
    problems = []
    for path in pages:
        name = path.relative_to(site_dir).as_posix()
        raw = path.read_text(encoding="utf-8")
        written, read = flatten(raw), flatten(strip_tags(raw))
        problems += [f"{name}: a never phrase: {phrase!r}" for phrase in NEVER if says(phrase, written, read)]
        problems += [f"{name}: missing {which}" for which, notice in NOTICES.items() if not says(notice, read)]
        if not says(NOINDEX, written):
            problems.append(f"{name}: missing noindex")
        if SCRIPT in written:
            problems.append(f"{name}: a script")
        words = sorted({found.group(0).lower() for found in PRONOUNS.finditer(read)})
        problems += [f"{name}: the word {word!r}" for word in words]
        if name == INDEX:
            problems += index_problems(site_dir, written, read)
    if not (site_dir / INDEX).is_file():
        problems.append(f"{INDEX}: missing")
    if not (site_dir / MARKER).is_file():
        problems.append(f"{MARKER}: missing; not a basket site")
    return problems


def main(argv: list[str], check: Callable[[Path], list[str]] = check_site) -> int:
    """The command over the folder `argv[0]`, by `check` (this site's, or the shopper site's): the exit code."""
    try:
        problems = check(Path(argv[0]))
    except NoPages as err:
        print(err, file=sys.stderr)
        return 2
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Check a built basket site before upload (docs/headline-basket.md, "Words" and "Before anything is published"):
no page says a NEVER phrase or "we", "our" or "us"; every page carries the credit line, `noindex` and no
script; the index page carries every ALWAYS phrase and says REVISED only on a revised day.

    PYTHONPATH=src .venv/bin/python -m basket.check site

Runs before every upload. Each `.html` under the folder is read two ways: as written (attributes and markup
included) and with tags stripped (the text a reader sees). In both, entities are unescaped, whitespace is
collapsed and case is ignored, so an entity, a tag or a line break cannot hide a phrase. A NEVER phrase found
in either is a problem, and so is REVISED on the index page. A phrase that must be there (the credit line's
fixed start, "Not shopping advice.", and on the index page every ALWAYS phrase) counts only in the text a
reader sees. `noindex` and `<script` are tags, looked for as written. The words "we", "our" and "us" are
matched whole in the text a reader sees; attributes hold chain slugs and codes, not words.

The day is revised when the newest `days/<day>.json` (ISO dates sort as dates) has `"revised"` set; null, or
no day file, is a day never revised. The marker `.basket-site`, which `basket.page.build_site` writes, marks
the folder as a basket site. Exit 0 clean; 1 with problems, one a line on stderr naming the file and the
rule; 2 when there is no page to check.
"""
import html
import json
import re
import sys
from pathlib import Path

from basket.page import MARKER
from basket.words import ALWAYS, NEVER, REVISED

CREDIT_START = ("Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish "
                "under")  # `basket.words.credit`'s fixed start; the rest names the day and the time
NOT_ADVICE = "Not shopping advice."
NOTICES = {"the credit line": CREDIT_START, f'"{NOT_ADVICE}"': NOT_ADVICE}  # every page, in the text read
NOINDEX = '<meta name="robots" content="noindex">'
SCRIPT = "<script"
PRONOUNS = re.compile(r"\b(?:we|our|us)\b", re.I)
INDEX = "index.html"
DAY_FILES = "days/????-??-??.json"


class NoPages(Exception):
    """The folder has no HTML pages, so a clean check would prove nothing."""


def flatten(text: str) -> str:
    """`text` with entities unescaped, whitespace collapsed and in lower case."""
    return re.sub(r"\s+", " ", html.unescape(text)).lower()


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]*>", " ", text)


def _says(phrase: str, *versions: str) -> bool:
    return any(flatten(phrase) in version for version in versions)


def _day(site_dir: Path) -> tuple[str, dict | None]:
    """The newest day file's name and its `revised` (None for a day never revised); ("no day file", None)
    without one."""
    days = sorted(site_dir.glob(DAY_FILES))
    if not days:
        return "no day file", None
    newest = days[-1]
    return newest.relative_to(site_dir).as_posix(), json.loads(newest.read_text(encoding="utf-8")).get("revised")


def _index_problems(site_dir: Path, written: str, read: str) -> list[str]:
    problems = [f"{INDEX}: missing an always phrase: {phrase!r}" for phrase in ALWAYS if not _says(phrase, read)]
    day, revised = _day(site_dir)
    if revised is None and _says(REVISED, written, read):
        problems.append(f"{INDEX}: {REVISED!r} on a day not revised ({day})")
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
        problems += [f"{name}: a never phrase: {phrase!r}" for phrase in NEVER if _says(phrase, written, read)]
        problems += [f"{name}: missing {which}" for which, notice in NOTICES.items() if not _says(notice, read)]
        if not _says(NOINDEX, written):
            problems.append(f"{name}: missing noindex")
        if SCRIPT in written:
            problems.append(f"{name}: a script")
        words = sorted({found.group(0).lower() for found in PRONOUNS.finditer(read)})
        problems += [f"{name}: the word {word!r}" for word in words]
        if name == INDEX:
            problems += _index_problems(site_dir, written, read)
    if not (site_dir / INDEX).is_file():
        problems.append(f"{INDEX}: missing")
    if not (site_dir / MARKER).is_file():
        problems.append(f"{MARKER}: missing; not a basket site")
    return problems


def main(argv: list[str]) -> int:
    try:
        problems = check_site(Path(argv[0]))
    except NoPages as err:
        print(err, file=sys.stderr)
        return 2
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

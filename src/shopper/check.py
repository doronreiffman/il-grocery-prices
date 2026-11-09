"""Check a built shopper site before any upload (docs/shopper-site.md, "Checks before upload", Call 11 and the anti-goal
"a page that looks current but is not", with "Changed after the survey", "Where the key lives"; the plan's Task 20 and
its pre-flights' B5, B2, N3, N4, N7, N8, N9 and N13).

    PYTHONPATH=src .venv/bin/python -m shopper.check site

How a page is read is the basket check's (`basket.check`): as written (attributes and markup included) and with tags
stripped (the text a reader sees), entities unescaped, whitespace collapsed, curly single quotes straightened and case
ignored, so neither an entity, a tag nor a line break can hide a phrase (`flatten`, `says`). What the check knows of the
day comes from the newest site-day file, `site-days/<day>.json` (ISO dates sort as dates): the day, each column's gate,
each chain's promotions error and every day scored to date. Every `.html` under the folder is checked:

- Each chain's span (`CHAIN_SPAN`, which holds every chain-supplied text, escaped) must hold no markup, `<` or `>`; then
  it is cut out, so a chain's own words count for no rule below: a product named with a NEVER phrase or the word "us"
  passes, and no phrase a page must carry can come from a chain's text. A span holding markup is refused and left in,
  so what it holds is read as the page's own.
- No NEVER phrase as written or as read, except inside `method.html`'s `<ul id="never-words">`, whose items must be
  NEVER, in order, and which is cut out before the phrases are sought; "we", "our" and "us" never, as whole words in
  the text read.
- The credit line's fixed start (`shopper.words.CREDIT_START`) and "Not shopping advice." in the text read; `noindex`
  as written; and in the page's header the date line of the newest site-day file's day (`date_line`), whatever the rest
  of the page says.
- `<script` only as `<script src="search.js" defer></script>`; no `src` and no `<link>` to another origin (a URL with a
  scheme, "https:" or "data:", or a host, "//").
- Every relative `href` and `src` resolves to a file in the build, and one with a fragment to a page that holds that id
  (`method.html#headline-basket`). The exceptions are the record's files, which went up on their own day and are never
  deleted (B5): a link to `forecasts/<d>.csv.gz` resolves when the build's `forecasts/ledger.csv` names day d, and one
  to `scores/<d>.csv.gz` when the newest site-day file lists d as scored (B2: it lists every day scored to date, and
  Lambda's build folder holds only the run day's site-day file). A link from the root ("/...") or out of the folder
  ("../" past it) resolves to nothing the check can see.

Then by page. `index.html` and every `p/*.html` carry every ALWAYS phrase in the text read. A product page holds at most
60,000 bytes (`MAX_PAGE`), and in each of its sections of a column (`data-column`): when the column's own gate is closed
in the newest site-day file, F10's sentence naming the column (`no_odds_yet`), and once that is cut out, no odds word
(`ODDS_WORDS`), matched as whole words in the text read (N4: "21 in" holds no "1 in"); when the section's chain
(`data-chain`) had its promotions unread that day, P10's sentence naming the chain (`unreadable`), on each of the chain's
columns (question M (g): both Carrefour's). A section of a column the site-day file does not name is refused. A
probability on a closed column's page is caught when the page is drawn (`render_product` refuses an open gate), not
here: no figure pattern tells it from P7's "34%" (N9). `basket.html` is held to the basket's index rules
(`basket.check.index_problems`, naming basket.html: N3): the basket's ALWAYS phrases, and "Revised on" exactly when the
newest `days/` file is revised. Each search piece, `search/*.json`, holds at most 150,000 bytes (`PIECE_MAX`). And
`index.html` and the marker `.shopper-site` are there.

Exit 0 clean; 1 with problems, one a line on stderr naming the file and the rule; 2 when there is no page to check
(`basket.check.main`). `check_site` is imported under its own name beside `basket.check.check_site` (the first
pre-flight's N13).
"""
import html
import json
import posixpath
import re
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

from basket.check import INDEX, NOINDEX, NOT_ADVICE, PRONOUNS, NoPages, flatten, index_problems, says, strip_tags
from basket.check import main as check_main
from shopper.build import LEDGER, MARKER, read_ledger
from shopper.freeze import scores_site_key, site_key
from shopper.product import CHAIN_SPAN, MAX_PAGE
from shopper.search import PIECE_MAX
from shopper.words import ALWAYS, CREDIT_START, NEVER, ODDS_WORDS, date_line, no_odds_yet, unreadable

__all__ = ["SEARCH_SCRIPT", "NoPages", "check_site", "main"]

METHOD, BASKET = "method.html", "basket.html"
PRODUCT = re.compile(r"p/[^/]+\.html")                        # a product page, p/<barcode>.html
PIECES = "search/*.json"
SITE_DAYS = "site-days/????-??-??.json"
SEARCH_SCRIPT = '<script src="search.js" defer></script>'      # the front page's one script (shopper.pages)
SCRIPT = "<script"
NOTICES = {"the credit line": CREDIT_START, f'"{NOT_ADVICE}"': NOT_ADVICE}   # every page, in the text read
SPAN = re.compile("(.*?)".join(map(re.escape, CHAIN_SPAN.split("{}"))), re.S)
MARKUP = re.compile("[<>]")
NEVER_LIST = '<ul id="never-words">'                           # method.html's NEVER list (shopper.pages)
LISTED = re.compile(re.escape(NEVER_LIST) + "(.*?)</ul>", re.S)
ITEM = re.compile(r"<li>(.*?)</li>", re.S)
HEADER = re.compile(r"<header\b[^>]*>(.*?)</header>", re.S | re.I)
SECTION = re.compile(r"<section\b([^>]*)>(.*?)</section>", re.S | re.I)
TAG = re.compile(r"<([a-z][a-z0-9-]*)(\s[^>]*)?>", re.I)
ATTRIBUTE = re.compile(r"""([^\s"'<>/=]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""")
ODDS = {word: re.compile(rf"\b{re.escape(flatten(word))}\b") for word in ODDS_WORDS}     # whole words (N4)


def _attributes(text: str | None) -> dict[str, str]:
    """A tag's attributes by lower-case name, each value unescaped; the first of a name given twice."""
    found: dict[str, str] = {}
    for name, double, single, bare in ATTRIBUTE.findall(text or ""):
        found.setdefault(name.lower(), html.unescape(double or single or bare))
    return found


def _tags(raw: str) -> list[tuple[str, dict[str, str]]]:
    """Every start tag of the page: its lower-case name and its attributes."""
    return [(found.group(1).lower(), _attributes(found.group(2))) for found in TAG.finditer(raw)]


def _elsewhere(url: str) -> bool:
    """Whether a URL names another origin: it has a scheme ("https:", "data:") or a host ("//")."""
    found = urlsplit(url)
    return bool(found.scheme or found.netloc)


def _cut_spans(raw: str) -> tuple[str, bool]:
    """The page with each chain span that holds no markup cut out (a space in its place), and whether a span held
    markup (left in: what it holds is read as the page's own)."""
    marked = False

    def cut(found: re.Match) -> str:
        nonlocal marked
        if MARKUP.search(found.group(1)):
            marked = True
            return found.group(0)
        return " "

    return SPAN.sub(cut, raw), marked


def _never_list(raw: str) -> tuple[str, list[str]]:
    """method.html with its NEVER list cut out, and the list's problems: none when its items are NEVER, in order."""
    found = LISTED.search(raw)
    if found is None:
        return raw, [f"{METHOD}: no never list ({NEVER_LIST})"]
    items = [html.unescape(item).strip() for item in ITEM.findall(found.group(1))]
    cut = raw[:found.start()] + " " + raw[found.end():]
    if tuple(items) == NEVER:
        return cut, []
    missing = [phrase for phrase in NEVER if phrase not in items]
    extra = [item for item in items if item not in NEVER]
    return cut, [f"{METHOD}: the never list is not NEVER, in order (missing {missing}, extra {extra})"]


def _dated(raw: str, line: str) -> bool:
    """Whether the page's header carries the date line `line`."""
    header = HEADER.search(raw)
    return header is not None and says(line, flatten(strip_tags(header.group(1))))


def _section_problems(name: str, attributes: Mapping[str, str], body: str, shown: Mapping) -> list[str]:
    """A product page's section of a column: F10 when the column's gate is closed, P10 when its chain's promotions
    were not read (the module's docstring)."""
    column, chain = attributes["data-column"], attributes.get("data-chain")
    block = shown["columns"].get(column)
    if block is None:
        return [f"{name}: a section of {column!r}, which the site-day file does not name"]
    read = flatten(strip_tags(body))
    problems = []
    if not block["gate"]["open"]:
        if not says(no_odds_yet(column), read):
            problems.append(f"{name}: no F10 sentence in the section of {column}, its gate closed")
        rest = read.replace(flatten(no_odds_yet(column)), " ")
        problems += [f"{name}: the odds word {word!r} in the section of {column}, its gate closed"
                     for word, pattern in ODDS.items() if pattern.search(rest)]
    unread = chain in shown["chains"] and shown["chains"][chain]["promotions_error"] is not None
    if unread and not says(unreadable(chain), read):
        problems.append(f"{name}: no P10 sentence in the section of {column}: {chain}'s promotions were not read")
    return problems


def _page(site_dir: Path, name: str, path: Path, day: date | None, shown: Mapping | None,
          line: str) -> tuple[list[str], list[str], set[str]]:
    """The page's own problems (the module's docstring), its links (each `href` and `src` once, in order) and its
    ids; `day` and `shown` the newest site-day file's (None without one), `line` the day's date line."""
    raw, marked = _cut_spans(path.read_text(encoding="utf-8"))
    problems = [f"{name}: markup inside a chain's span"] if marked else []
    if name == METHOD:
        raw, listed = _never_list(raw)
        problems += listed
    written, read = flatten(raw), flatten(strip_tags(raw))
    problems += [f"{name}: a never phrase: {phrase!r}" for phrase in NEVER if says(phrase, written, read)]
    problems += [f"{name}: missing {which}" for which, notice in NOTICES.items() if not says(notice, read)]
    if not says(NOINDEX, written):
        problems.append(f"{name}: missing noindex")
    if day is not None and not _dated(raw, line):
        problems.append(f"{name}: no date line of {day.isoformat()} in its header")
    words = sorted({found.group(0).lower() for found in PRONOUNS.finditer(read)})
    problems += [f"{name}: the word {word!r}" for word in words]
    if SCRIPT in written.replace(flatten(SEARCH_SCRIPT), " "):
        problems.append(f"{name}: a script other than {SEARCH_SCRIPT}")
    tags = _tags(raw)
    loaded = [found["src"] for _, found in tags if "src" in found]
    loaded += [found["href"] for tag, found in tags if tag == "link" and "href" in found]
    problems += [f"{name}: loads from another origin: {url!r}" for url in loaded if _elsewhere(url)]
    product = PRODUCT.fullmatch(name) is not None
    if name == INDEX or product:
        problems += [f"{name}: missing an always phrase: {phrase!r}" for phrase in ALWAYS if not says(phrase, read)]
    if product:
        size = path.stat().st_size
        if size > MAX_PAGE:
            problems.append(f"{name}: {size:,} bytes, over the {MAX_PAGE:,} bytes a product page may hold")
        if shown is not None:
            for attributes, body in SECTION.findall(raw):
                found = _attributes(attributes)
                if "data-column" in found:
                    problems += _section_problems(name, found, body, shown)
    if name == BASKET:
        problems += index_problems(site_dir, written, read, BASKET)
    links = [value for _, found in tags for key, value in found.items() if key in ("href", "src")]
    return problems, list(dict.fromkeys(links)), {found["id"] for _, found in tags if "id" in found}


def _newest(site_dir: Path) -> tuple[date | None, dict | None]:
    """The newest site-day file's day and content; (None, None) without one."""
    days = sorted(site_dir.glob(SITE_DAYS))
    if not days:
        return None, None
    newest = days[-1]
    return date.fromisoformat(newest.stem), json.loads(newest.read_text(encoding="utf-8"))


def _records(site_dir: Path, shown: Mapping | None) -> set[str]:
    """The record files a link may name though the build does not hold them (B5): the forecasts file of each day the
    build's ledger names, and the scores file of each day the newest site-day file lists as scored (B2)."""
    ledger = site_dir / LEDGER
    frozen = read_ledger(ledger.read_bytes() if ledger.is_file() else None)
    scored = [] if shown is None else shown["scored_days"]
    return {site_key(day) for day in frozen} | {scores_site_key(date.fromisoformat(day)) for day in scored}


def _link_problem(name: str, url: str, files: set[str], records: set[str], ids: Mapping[str, set[str]]) -> str | None:
    """The problem with a link from the page `name`, or None: a link to another origin is not this rule's; a relative
    one resolves to a file in the build (with a fragment, to a page holding that id) or to a record file (`_records`)."""
    if _elsewhere(url):
        return None
    link = urlsplit(url)
    path = unquote(link.path)
    if path.startswith("/"):
        return f"{name}: a link to {url!r} from the root, not relative to the page"
    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
    if target == ".." or target.startswith("../"):
        return f"{name}: a link to {url!r} leaves the build"
    if target in files:
        if link.fragment and link.fragment not in ids.get(target, set()):
            return f"{name}: a link to {url!r}: {target} holds no id {link.fragment!r}"
        return None
    if target in records:
        return None
    return f"{name}: a link to {url!r} reaches no file in the build"


def check_site(site_dir: Path) -> list[str]:
    """The site's problems, one line each naming the file and the rule; [] for a site fit to upload."""
    site_dir = Path(site_dir)
    pages = sorted(path for path in site_dir.rglob("*.html") if path.is_file())
    if not pages:
        raise NoPages(f"no HTML pages under {site_dir}")
    day, shown = _newest(site_dir)
    line = "" if day is None else date_line(day)
    problems: list[str] = []
    links: dict[str, list[str]] = {}
    ids: dict[str, set[str]] = {}
    for path in pages:
        name = path.relative_to(site_dir).as_posix()
        found, links[name], ids[name] = _page(site_dir, name, path, day, shown, line)
        problems += found
    files = {path.relative_to(site_dir).as_posix() for path in site_dir.rglob("*") if path.is_file()}
    records = _records(site_dir, shown)
    for name, urls in links.items():
        problems += [problem for url in urls if (problem := _link_problem(name, url, files, records, ids))]
    for path in sorted(site_dir.glob(PIECES)):
        if (size := path.stat().st_size) > PIECE_MAX:
            problems.append(f"{path.relative_to(site_dir).as_posix()}: {size:,} bytes, over the {PIECE_MAX:,} bytes "
                            "a search piece may hold")
    if shown is None:
        problems.append("site-days/: no site-day file, so no day to read the pages by")
    if not (site_dir / INDEX).is_file():
        problems.append(f"{INDEX}: missing")
    if not (site_dir / MARKER).is_file():
        problems.append(f"{MARKER}: missing; not a shopper site")
    return problems


def main(argv: list[str]) -> int:
    """The command, `basket.check.main` by this check: exit 0 clean, 1 with problems, 2 with no page."""
    return check_main(argv, check_site)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

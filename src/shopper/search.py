"""Search and browse: how a name is normalised, the index pieces `search.js` reads, and the browse pages
(docs/shopper-site.md, "What a visitor sees" and "Build and hosting"; the plan's Task 17 and its "Where the design leaves
room", Search; the first pre-flight's N2, N7, N12 and N18).

Normalising. A name and a query are compared after the same four steps: lower-case (Latin letters), then each character
through `NORMALIZE` (the quotes `'` and `"` and the Hebrew geresh U+05F3 and gershayim U+05F4 are dropped; the five
final letters become their plain forms, ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ; a tab, a line break and a no-break space become a
space), then runs of spaces collapse to one, then the ends are trimmed. `NORMALIZE` is the one table: `static/search.js`
holds the same JSON between two `/*NORMALIZE*/` markers, a test reads it back, and the script's answers on 30 names are
tested against `normalize` here. Casing is the language's own (`str.lower`, `toLowerCase`).

The pieces. Every covered product has one entry, in exactly one piece: the piece of the first character of its
normalised title, the longest of its columns' names (`Covered.title`). An entry is the flat JSON list `[barcode, title
as published, normalised title, the other columns' normalised names, sorted]`, so every column's name is searchable, and
the product's page is `p/<barcode>.html`. A piece is a JSON list of entries in name order (the normalised title, then the
barcode), `search/<hex>.json`, <hex> the first character's code point in lower-case hex of at least four digits
("05e9"). When that is over PIECE_MAX (150,000 bytes) the letter is split by the normalised title's second character
(a space for a one-character title), `search/<hex>-<hex>.json`, and the whole letter's piece is not written.
`search/pieces.json` lists the keys written, sorted, without the folder or `.json`; the script reads it first. What a
piece covers is therefore the products whose longest name starts with the query's letters: a name is found by typing
the start of the longest name, and the browse pages reach the rest. A piece or a sub-piece over the limit is refused by
the upload check (Task 20), not here.

The browse pages. `browse/<hex>.html` for each Hebrew letter (alef to tav, after normalising: the finals are plain) that
starts some covered product's longest name, and `browse/other.html` for every product whose longest name does not start
with a Hebrew letter: a Latin name, a digit, a sign. A page lists its products in name order, each a link to
`../p/<barcode>.html` with the name as published, escaped, in a span of its own (`CHAIN_SPAN`), and the barcode; a row of
links to every browse page sits above the list. The pages need no script: they are the path to every product. They carry
the band, the date line and the credit line as the other pages do, `noindex`, and no script. A letter nobody starts
a name with has no page.
"""
import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from html import escape
from pathlib import Path

from basket.page import STYLE
from basket.words import METHOD_LINK
from shopper.history import Covered
from shopper.words import SITE_NAME, credit, date_line

PIECE_MAX = 150_000
SCRIPT = Path(__file__).parent / "static" / "search.js"
NORMALIZE: dict[str, str] = {
    "'": "", '"': "", "\u05f3": "", "\u05f4": "",            # the quotes, geresh and gershayim: dropped
    "\u05da": "\u05db", "\u05dd": "\u05de", "\u05df": "\u05e0", "\u05e3": "\u05e4", "\u05e5": "\u05e6",   # final letters
    "\t": " ", "\n": " ", "\r": " ", "\u00a0": " ",         # kinds of space
}
# Every chain-supplied text: escaped, in a span of its own, so the site check reads it for markup only (Call 11).
CHAIN_SPAN = '<span class="as-listed" lang="he" dir="rtl">{}</span>'
HEBREW_LETTERS = ("\u05d0", "\u05ea")        # alef to tav
OTHER = "other"
OTHER_HEADING = "Names that do not start with a Hebrew letter"
BROWSE_STYLE = """
.letters { display: flex; flex-wrap: wrap; gap: var(--s2); list-style: none; padding: 0; margin: 0 0 var(--s4); }
.letters a { display: block; padding: var(--s1) var(--s3); background: var(--surface); border: 1px solid var(--border);
             border-radius: 6px; text-decoration: none; }
.letters a[aria-current] { border-color: var(--accent); font-weight: 700; }
ul.names { list-style: none; padding: 0; margin: 0; }
ul.names li { padding: var(--s1) 0; border-bottom: 1px solid var(--border); }
ul.names small { color: var(--text-3); font-variant-numeric: tabular-nums; }
"""


def normalize(text: str) -> str:
    """`text` as search compares it (the module's docstring, "Normalising")."""
    mapped = "".join(NORMALIZE.get(char, char) for char in text.lower())
    return " ".join(part for part in mapped.split(" ") if part)


def _first(name: str) -> str:
    """The character a normalised name is filed under; a space for a name that normalised to nothing."""
    return name[:1] or " "


def _second(name: str) -> str:
    return name[1:2] or " "


def _key(*chars: str) -> str:
    return "search/" + "-".join(f"{ord(char):04x}" for char in chars) + ".json"


def _encode(entries: list) -> bytes:
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _entry(item: Covered) -> list[str]:
    """[barcode, title as published, normalised title, the other columns' normalised names, sorted]."""
    title = normalize(item.title)
    others = sorted({name for name in map(normalize, item.names.values()) if name and name != title})
    return [item.code, item.title, title, *others]


def pieces(covered: Mapping[str, Covered]) -> dict[str, bytes]:
    """`search/<key>.json` for every piece and `search/pieces.json`, the keys written (the module's docstring)."""
    entries = sorted((_entry(item) for item in covered.values()), key=lambda entry: (entry[2], entry[0]))
    by_first = defaultdict(list)
    for entry in entries:
        by_first[_first(entry[2])].append(entry)
    files = {}
    for first, group in sorted(by_first.items()):
        whole = _encode(group)
        if len(whole) <= PIECE_MAX:
            files[_key(first)] = whole
            continue
        by_second = defaultdict(list)
        for entry in group:
            by_second[_second(entry[2])].append(entry)
        for second, part in sorted(by_second.items()):
            files[_key(first, second)] = _encode(part)
    listed = sorted(name[len("search/"):-len(".json")] for name in files)
    return {**files, "search/pieces.json": _encode(listed)}


def _browse_key(title: str) -> str:
    """The hex of the Hebrew letter the longest name starts with, else `other`."""
    first = _first(normalize(title))
    return f"{ord(first):04x}" if HEBREW_LETTERS[0] <= first <= HEBREW_LETTERS[1] else OTHER


def browse_path(title: str) -> str:
    """The browse page a product with this longest name is on."""
    return f"browse/{_browse_key(title)}.html"


def browse_pages(covered: Mapping[str, Covered], day: date, collected_by: str) -> dict[str, str]:
    """`browse/<hex>.html` for each Hebrew letter that starts a product's longest name and `browse/other.html` when some
    product's does not; every covered product is on exactly one."""
    groups = defaultdict(list)
    for item in covered.values():
        groups[_browse_key(item.title)].append(item)
    keys = sorted(groups, key=lambda key: (key == OTHER, key))
    return {f"browse/{key}.html": _browse_page(key, groups[key], keys, day, collected_by) for key in keys}


def _text(text: str) -> str:
    return escape(text, quote=False)


def _he(text: str) -> str:
    return f'<span lang="he" dir="rtl">{_text(text)}</span>'


def _browse_page(key: str, items: list[Covered], keys: list[str], day: date, collected_by: str) -> str:
    links = []
    for other in keys:
        label = "Other" if other == OTHER else _he(chr(int(other, 16)))
        current = ' aria-current="page"' if other == key else ""
        links.append(f'<li><a href="{other}.html"{current}>{label}</a></li>')
    heading = OTHER_HEADING if key == OTHER else "Names that start with " + _he(chr(int(key, 16)))
    names = sorted(items, key=lambda item: (normalize(item.title), item.code))
    rows = "".join(f'<li><a href="../p/{escape(item.code)}.html">{CHAIN_SPAN.format(_text(item.title))}</a> '
                   f"<small>{_text(item.code)}</small></li>" for item in names)
    nav = "".join(links)
    count = f"{len(names):,} {'product' if len(names) == 1 else 'products'}"
    main = (f'<h1>{heading}</h1>\n<nav aria-label="First letters"><ul class="letters">{nav}</ul></nav>\n'
            f'<p>{count}</p>\n<section><ul class="names">{rows}</ul></section>')
    title = (OTHER_HEADING if key == OTHER else f"Names that start with {chr(int(key, 16))}") + f" - {SITE_NAME}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>{_text(title)}</title>
<style>{STYLE}{BROWSE_STYLE}</style>
</head>
<body>
<header class="band"><div class="wrap"><a href="../index.html">{_text(SITE_NAME)}</a><p class="dateline">{_text(date_line(day))}</p></div></header>
<main>
{main}
</main>
<footer><div class="wrap"><p>{_text(credit(day, collected_by))} <a href="../method.html">{_text(METHOD_LINK)}</a></p></div></footer>
</body>
</html>
"""

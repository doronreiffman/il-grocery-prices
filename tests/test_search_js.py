"""search.js (`src/shopper/static/search.js`; the plan's Task 17, and the store picker, docs/store-first.md, q33) under
Node, through `tests/search_harness.js`. Search: its normalisation agrees with `shopper.search`'s, it names the piece a
query belongs in, it matches in name order and stops at 50, it asks for a barcode's page by HEAD and says what the site
has, and it asks from the site's root on a page in a folder. The picker: its store names are the columns, a remembered
pick counts only when it is one of them and storage never stops the script, the header names the pick on every page
but the root, the root never sends anyone on and offers a remembered pick first, as "Your store" above the headline
(the owner, 2026-11-16: docs/site-look.md, "The front page stays put, with a shortcut to your store"), a store page
remembers its store, and a product page opens the pick's part and lists the rest under "Elsewhere today". Node is a CI
tool for this one file (Node 22.11.0 there); a machine without it fails these tests, as it should.

The fake page (the harness's `page`) is a small DOM, a search box (`#q`) alone unless a test gives one, with a storage, a
location and a fetch that records its requests; the answers are the results box's HTML, the page's HTML after the
script, what the storage holds and where `location.replace` was sent (nowhere, now, on any page).

The word index (the product-names plan's Task 2): the script's tokens, word entries, steps, `pickNode` and `wordsFor`
are held to their Python twins in `shopper.wordindex`, each name walked by code point, and with `?words=on` in the page's
address a search reads the word index after today's lookup; without it the script searches as before."""
import json
import random
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from shopper.columns import COLUMNS
from shopper.search import normalize, pieces, today_lookup
from shopper.wordindex import (MANIFEST, Extra, Node, as_word_entry, entry, files, lookup, node_key, order_key, pick, step,
                               tokens)
from shopper.words import not_sold
from test_wordindex import NODES, STEP_CASES, STEP_QUERY, STEP_TIES, _catalogue, _item, _searches
from words_registry import extras, registry

ROOT = Path(__file__).parent.parent
NO_PAGE = "This site has no page for that barcode."
NOTHING = "Nothing found."
FAILED = "Could not reach the site just now."
CODE = "7290000000017"


def _run(op, payload):
    done = subprocess.run(["node", "tests/search_harness.js", op], input=json.dumps(payload), capture_output=True,
                          text=True, cwd=ROOT, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _page(inputs, responses):
    return _run("page", {"inputs": inputs, "responses": responses})


def _entry(code, title, *names):
    return [code, title, *(names or (normalize(title),))]


# normalising

NAMES = [
    "קוטג' תנובה 5%", 'גר"ם', "צ\u05f3יפס", "מ\u05f4ל", "\u05da\u05dd\u05df\u05e3\u05e5", "שלום עולם", "Coca COLA", "ÉCLAIR",
    "  spaces   everywhere  ", "tab\tnewline\ncr\rnbsp\u00a0end", "", "   ", "5% שמן 1.5L", 'א " ב', "İSTANBUL", "ΑΣ ΣΑΣ",
    "ß ẞ", "ǅ", "🍫 שוקולד", "שוקולד מריר 70%", "חלב 3% 1 ליטר", "ילד'ים", "MIXED שפה Mixed", "פ\u05f4ץ ף ץ", "ﬁsh",
    "א\u05b0ב", "a\u200bb", "a\ufeffb", "x\x1fy", "ＡＢＣ ａｂｃ",
]


def test_normalize_agrees_with_python():
    assert len(NAMES) == 30
    assert _run("normalize", NAMES) == [normalize(name) for name in NAMES]


# the piece a query belongs in

PIECES = ["0061", "05d0", "05e9-0020", "05e9-05d0", "05e9-05de", "1f36b"]


@pytest.mark.parametrize("query, key", [
    ("אבג", "05d0"), ("א", "05d0"),            # a whole letter
    ("שמן", "05e9-05de"), ("שא", "05e9-05d0"), ("ש מ", "05e9-0020"),   # a split letter: the second letter picks
    ("ש", None),                               # a split letter needs a second letter
    ("שזכ", None), ("שך", None),               # a second letter no piece has (a final letter is a plain one)
    ("קוטג", None), ("", None), ("   ", None),   # no piece for the letter; nothing typed
    ("Apple", "0061"), ("APPLE", "0061"),      # Latin in lower case
    ('"אבג', "05d0"), ("  אבג  ", "05d0"),     # as typed: quotes and spaces do not count
    ("🍫x", "1f36b"),                          # a code point above U+FFFF, in hex of its own
])
def test_the_piece_for_a_split_letter(query, key):
    assert _run("pieceFor", {"pieces": PIECES, "queries": [query]}) == [key]


# the matches

def test_matches_at_most_50_in_name_order():
    entries = [_entry(f"72900{i:08d}", f"חלב {i:02d}") for i in range(60)]
    entries += [_entry("7290000009999", "שמן")]   # no match
    shuffled = random.Random(7).sample(entries, len(entries))
    found = _run("matches", {"entries": shuffled, "query": "חלב"})
    assert [entry[0] for entry in found] == [f"72900{i:08d}" for i in range(50)]   # the first 50 by name, not the first met


def test_matches_with_a_tie_go_by_code_and_none_for_no_query():
    entries = [_entry("7290000000003", "חלב"), _entry("7290000000001", "חלב"), _entry("7290000000002", "חלב")]
    assert [e[0] for e in _run("matches", {"entries": entries, "query": "חל"})] == [
        "7290000000001", "7290000000002", "7290000000003"]
    assert _run("matches", {"entries": entries, "query": ""}) == []
    assert _run("matches", {"entries": entries, "query": "  "}) == []


def test_matches_read_every_name_and_the_query_as_typed():
    cheese = _entry("7290000000001", "גבינה צהובה פרוסה", "גבינה צהובה פרוסה", "פרוסות גבינה")
    cola = _entry("7290000000002", "Coca-Cola ZERO", "coca-cola zero")
    oil = _entry("7290000000003", "שמן זית", "שמנ זית")
    entries = [cheese, cola, oil]

    def codes(query):
        return [entry[0] for entry in _run("matches", {"entries": entries, "query": query})]

    assert codes("פרוסות") == [cheese[0]]            # a name of another column
    assert codes("גבינה") == [cheese[0]]
    assert codes("צהובה פרוסות") == []               # never across two names
    assert codes("COLA") == [cola[0]]                # Latin in any case
    assert codes("שמן") == [oil[0]]                  # a final letter typed for a plain one
    assert codes('"שמ') == [oil[0]]                  # quotes do not count
    assert codes("זית") == [oil[0]]                  # inside a name, not only at its start
    assert codes("xyz") == []


# barcodes

@pytest.mark.parametrize("query, code", [
    ("7290000000017", "7290000000017"), ("07290000000017", "7290000000017"),   # leading zeros stripped
    ("00000000012345", "12345"), (" 7290000000017 ", "7290000000017"),
    ("12345678", "12345678"), ("12345678901234", "12345678901234"),           # 8 and 14 digits
    ("1234567", None), ("123456789012345", None),                             # 7 and 15
    ("7290000a00017", None), ("729 0000 00017", None), ("\u0667\u0669\u0660\u0660\u0660\u0660\u0660\u0660", None),   # not ASCII digits
    ("00000000", None), ("", None), ("חלב", None),                            # no digits left
])
def test_barcode_of(query, code):
    assert _run("barcodeOf", [query]) == [code]


@pytest.mark.parametrize("status", [403, 404, 500, 204, 301])
def test_a_barcode_is_asked_for_by_its_page(status):
    found = _page([{"value": "0" + CODE}], {"search/pieces.json": {"status": 200, "body": []},
                                              f"p/{CODE}.html": {"status": status}})
    assert {"url": f"p/{CODE}.html", "method": "HEAD"} in found["requests"]
    assert NO_PAGE in found["html"]
    assert "href" not in found["html"]


def test_a_barcode_with_a_page_is_linked():
    found = _page([{"value": CODE}], {"search/pieces.json": {"status": 200, "body": []},
                                      f"p/{CODE}.html": {"status": 200}})
    assert [r for r in found["requests"] if r["url"] != "search/pieces.json"] == [{"url": f"p/{CODE}.html", "method": "HEAD"}]
    assert f'<a href="p/{CODE}.html">' in found["html"]
    assert NO_PAGE not in found["html"]


@pytest.mark.parametrize("typed", ["1234567", "123456789012345", "7290000a00017", "חלב"])
def test_only_a_barcode_is_asked_for_by_its_page(typed):
    found = _page([{"value": typed}], {"search/pieces.json": {"status": 200, "body": []}})
    assert [r for r in found["requests"] if r["method"] == "HEAD"] == []


def test_a_late_answer_for_an_old_barcode_is_ignored():
    older, newer = "7290000000017", "7290000000024"
    found = _page([{"value": older, "wait": False}, {"value": newer}],
                  {"search/pieces.json": {"status": 200, "body": []},
                   f"p/{older}.html": {"status": 200, "delay": 150}, f"p/{newer}.html": {"status": 403}})
    assert NO_PAGE in found["html"]
    assert older not in found["html"]


def test_a_barcode_check_that_gets_no_answer_does_not_say_the_page_is_missing():
    found = _page([{"value": CODE}], {"search/pieces.json": {"status": 200, "body": []},
                                      f"p/{CODE}.html": {"reject": True}})
    assert FAILED in found["html"]
    assert NO_PAGE not in found["html"]


# the names

def test_a_name_is_searched_in_the_piece_its_letters_name():
    pieces = ["05d0", "05e9-05de", "05e9-05e7"]
    oil = _entry("7290000000009", '<b>שמן "x"</b>', '<b>שמנ "x"</b>')
    yeast = _entry("7290000000008", "שמרים")
    responses = {"search/pieces.json": {"status": 200, "body": pieces},
                 "search/05e9-05de.json": {"status": 200, "body": [oil, yeast]}}
    found = _page([{"value": "ש"}, {"value": "שמ"}, {"value": "שמן"}], responses)
    assert found["requests"] == [{"url": "search/pieces.json", "method": "GET"},
                                 {"url": "search/05e9-05de.json", "method": "GET"}]   # each once; the list on the first key
    assert 'href="p/7290000000009.html"' in found["html"]
    assert "&lt;b&gt;" in found["html"] and "<b>" not in found["html"]   # the title is escaped, in a span of its own
    assert '<span class="as-listed" lang="he" dir="rtl">' in found["html"]
    assert "7290000000008" not in found["html"]   # the yeast does not match "שמנ"


def test_one_letter_searches_nothing_but_the_list_is_fetched_on_the_first_keystroke():
    found = _page([{"value": "ש"}], {"search/pieces.json": {"status": 200, "body": ["05e9"]}})
    assert found["requests"] == [{"url": "search/pieces.json", "method": "GET"}]
    assert found["html"] == ""


def test_a_name_nothing_has_says_so():
    responses = {"search/pieces.json": {"status": 200, "body": ["05e9"]},
                 "search/05e9.json": {"status": 200, "body": [_entry("7290000000008", "שמרים")]}}
    assert NOTHING in _page([{"value": "שק"}], responses)["html"]   # the piece is there, no name has it
    assert NOTHING in _page([{"value": "קוטג"}], responses)["html"]   # no piece for the letter


def test_the_list_stops_at_50_and_says_so():
    responses = {"search/pieces.json": {"status": 200, "body": ["05d7"]},
                 "search/05d7.json": {"status": 200, "body": [_entry(f"72900{i:08d}", f"חלב {i:02d}") for i in range(60)]}}
    html = _page([{"value": "חל"}], responses)["html"]
    assert html.count("<li>") == 50
    # deploy prep: exactly 50 matches show the line too, so it never says there are more
    assert "<p>Showing up to 50 names. Type more of the name to narrow them.</p>" in html


def test_a_list_that_cannot_be_fetched_says_so_and_is_fetched_again_on_the_next_key():
    responses = {"search/pieces.json": [{"status": 500}, {"status": 200, "body": ["05e9"]}],
                 "search/05e9.json": {"status": 200, "body": [_entry("7290000000008", "שמרים")]}}
    first = _page([{"value": "שמ"}], responses)
    assert FAILED in first["html"]
    second = _page([{"value": "שמ"}, {"value": "שמר"}], responses)   # the first key fails, the second asks again
    assert 'href="p/7290000000008.html"' in second["html"]
    assert [r["url"] for r in second["requests"]].count("search/pieces.json") == 2


def test_a_title_and_a_code_are_escaped_in_the_results():
    entry = ["7290&\"<x>'1", "<b>A&B \"q\" it's</b>", "<b>a&b qq its</b>"]
    responses = {"search/pieces.json": {"status": 200, "body": ["0061"]},
                 "search/0061.json": {"status": 200, "body": [entry]}}
    html = _page([{"value": "a&b"}], responses)["html"]
    code, title = "7290&amp;&quot;&lt;x&gt;&#39;1", "&lt;b&gt;A&amp;B &quot;q&quot; it&#39;s&lt;/b&gt;"
    assert html == (f'<ul><li><a href="p/{code}.html"><span class="as-listed" lang="he" dir="rtl">{title}</span></a> '
                    f"<small>{code}</small></li></ul>")


@pytest.mark.parametrize("typed", ["ש ", "ש'", '"ש"', " ש", "ש\u00a0"])
def test_the_two_characters_are_counted_after_normalising(typed):
    found = _page([{"value": typed}], {"search/pieces.json": {"status": 200, "body": ["05e9"]}})
    assert found["requests"] == [{"url": "search/pieces.json", "method": "GET"}]   # one letter and a mark is one letter
    assert found["html"] == ""


# the picker: its names and words

KEYS = [column.key for column in COLUMNS]
PICK = "Pick your store"
ELSEWHERE = "Elsewhere today"
PARTS = ["carrefour-city", "osherad", "ramilevy", "yochananof"]   # a product page's parts, in COLUMNS order
BADGES = ["ramilevy", "osherad", "yochananof"]                    # its badges, by saving


def test_the_scripts_store_names_are_the_columns():
    script = (ROOT / "src" / "shopper" / "static" / "search.js").read_text(encoding="utf-8")
    parts = script.split("/*COLUMNS*/")
    assert len(parts) == 3, "search.js holds its store names between two /*COLUMNS*/ markers"
    assert json.loads(parts[1]) == [[column.key, column.name] for column in COLUMNS]


def test_the_scripts_not_sold_line_is_the_words():
    # shopper.words.not_sold without the last-seen day: the script writes the line only for a store type the page has
    # no part for, so it knows no day the product was last seen there.
    assert _run("notSoldLine", KEYS) == [not_sold(key, None) for key in KEYS]


# the pick (Review Focus 1: a pick that no longer fits is no pick, and storage never stops the script)

@pytest.mark.parametrize("storage, pick", [
    *[({"value": key}, key) for key in KEYS],                                                 # each of the nine
    ({"value": "carrefour"}, None), ({"value": "Osherad"}, None), ({"value": ""}, None),      # an old value, garbage
    ({"value": "toString"}, None), ({"value": "__proto__"}, None),                            # names every object has
    ({"value": None}, None),                                                                  # nothing remembered
    ({"throws": True}, None),                                                                 # getItem throws
    (None, None),                                                                             # reading storage threw
])
def test_read_pick(storage, pick):
    assert _run("readPick", [storage]) == [pick]


def test_write_pick_never_throws():
    calls = [{"storage": {"value": None}, "key": "osherad"}, {"storage": {"throws": True}, "key": "osherad"},
             {"storage": None, "key": "osherad"}]
    assert _run("writePick", calls) == [{"threw": False, "stored": {"store": "osherad"}},   # under the one key
                                        {"threw": False, "stored": {}}, {"threw": False, "stored": {}}]


# the root and the header

def test_root_of():
    assert _run("rootOf", ["index.html#pick", "../index.html#pick", "../../index.html#pick"]) == ["", "../", "../../"]
    assert _run("rootOf", ["../index.html", "../about.html#pick"]) == ["", ""]   # not the picker's: the page's folder


def test_header_for():
    assert _run("headerFor", [["carrefour-market", "../"], ["osherad", ""], [None, "../"]]) == [
        {"name": "Carrefour Market", "href": "../store/carrefour-market.html", "change": "../index.html#pick"},
        {"name": "Osher Ad", "href": "store/osherad.html", "change": "index.html#pick"}, None]


# a product page's parts and badges (Review Focus 4: a pick the page has no part for, no badges)

def _layout(open_=None, not_sold=None, elsewhere=(), heading=False):
    return {"open": open_, "notSold": not_sold, "elsewhere": list(elsewhere), "heading": heading}


@pytest.mark.parametrize("pick, parts, badges, layout", [
    # a pick among the parts: its part open, the other badges under Elsewhere today
    ("osherad", PARTS, BADGES, _layout("osherad", elsewhere=["ramilevy", "yochananof"], heading=True)),
    # no other badge (the pick's own alone, or none): no heading over an empty row (the whole-branch review)
    ("osherad", PARTS, ["osherad"], _layout("osherad")),
    ("osherad", ["osherad"], [], _layout("osherad")),
    # sold there before, not today: its part (with its last-seen line) open, every badge under Elsewhere
    ("carrefour-city", PARTS, BADGES, _layout("carrefour-city", elsewhere=BADGES, heading=True)),
    # a pick the page has no part for: the not-sold line, then every badge
    ("shufersal-deal", PARTS, BADGES, _layout(not_sold="shufersal-deal", elsewhere=BADGES, heading=True)),
    # sold nowhere today: the line and an empty row, with no heading over it
    ("shufersal-deal", ["carrefour-city"], [], _layout(not_sold="shufersal-deal")),
    ("shufersal-deal", [], [], _layout(not_sold="shufersal-deal")),
    # no pick: the row first, as the picker, the first badge open, no heading
    (None, PARTS, BADGES, _layout("ramilevy", elsewhere=BADGES)),
    (None, PARTS, [], _layout("carrefour-city")),     # no badges: the first part
    (None, [], [], _layout()),                         # nothing at all
])
def test_arrange(pick, parts, badges, layout):
    assert _run("arrange", [[pick, parts, badges]]) == [layout]


def test_on_badge():
    # Question 1 (answered 2026-11-11): with no pick, a tap also sets it; with a pick (call 6), it only shows its part.
    assert _run("onBadge", [[None, "osherad"], ["ramilevy", "osherad"], ["osherad", "osherad"]]) == [
        {"show": "osherad", "setPick": "osherad"}, {"show": "osherad", "setPick": None},
        {"show": "osherad", "setPick": None}]


# the pages, as Tasks 3 and 5 render them

def _el(tag, attributes=None, *children):
    return [tag, attributes or {}, list(children)]


def _header(up):
    """Every page's header: the store line, `p.store`, holding the pick link, whose href leads up to the site's root
    (`shopper.shell.band`)."""
    return _el("header", {}, _el("p", {"class": "store"}, _el("a", {"id": "pick-link", "href": f"{up}index.html#pick"},
                                                                PICK)))


def _root_page(up="", search=False):
    """The root page: the hero (the headline's block), then the picker. `up` and `search` make a root page no build
    writes, one in a folder with a search box, to show what the script reads its root from."""
    links = [_el("a", {"href": f"{up}store/{column.key}.html"}, column.name) for column in COLUMNS]
    box = [_el("input", {"id": "q"})] if search else []
    return [_header(up), _el("main", {}, _el("div", {"class": "hero"}, _el("h1", {}, "Deal or No Deal?")),
                             _el("section", {"id": "pick", "data-page": "root"}, *links), *box)]


def _store_page(key):
    return [_header("../"), _el("main", {"data-store": key}, _el("input", {"id": "q"}))]


def _product_page(parts, badges):
    """A product page: the badge row after the name block, its heading hidden, then every part in COLUMNS order."""
    row = [_el("a", {"data-column": key, "href": f"#c-{key}"}, key) for key in badges]
    sections = [_el("section", {"data-column": key, "id": f"c-{key}"}, key) for key in parts]
    heading = _el("h2", {"class": "elsewhere", "hidden": ""}, ELSEWHERE)
    return [_header("../"),
            _el("main", {}, _el("h1", {}, "חלב"), heading, _el("nav", {"class": "badges"}, *row), *sections)]


def _site(dom, storage=None, **more):
    return _run("page", {"dom": dom, "storage": {} if storage is None else storage, **more})


def _open(page):
    """The parts shown, in page order."""
    return re.findall(r'<section data-column="([\w-]+)" id="c-[\w-]+">', page)


def _listed(page):
    """The badges shown, in page order."""
    return re.findall(r'<a data-column="([\w-]+)" href="#c-[\w-]+">', page)


def _named(up, key, name):
    return (f'<header><p class="store"><a href="{up}store/{key}.html">{name}</a> · '
            f'<a id="pick-link" href="{up}index.html#pick">change</a></p></header>')


def _asking(up="", hidden=False):
    """The header as the build writes it, "Pick your store", untouched by the script; its store line hidden or not."""
    line = '<p class="store" hidden>' if hidden else '<p class="store">'
    return f'<header>{line}<a id="pick-link" href="{up}index.html#pick">{PICK}</a></p></header>'


def _shortcut(up, key, name):
    """The root's shortcut to the remembered store type, first in the main part, right before the headline's block."""
    return (f'<main><p class="yours"><a href="{up}store/{key}.html"><small>Your store</small> {name}</a></p>'
            '<div class="hero">')


@pytest.mark.parametrize("dom", [None, _root_page(), _store_page("osherad"), _product_page(PARTS, BADGES)])
def test_the_script_marks_every_page_js(dom):
    # Only .js rules hide anything, so a page whose script did not run shows every part.
    found = _run("page", {"dom": dom} if dom else {})
    assert found["page"].startswith('<html class="js">')


@pytest.mark.parametrize("before", [{}, {"store": "osherad"}, {"store": "ramilevy"}, {"store": "garbage"}])
def test_a_store_page_remembers_its_store(before):
    found = _site(_store_page("osherad"), before)
    assert found["stored"] == {"store": "osherad"}    # another store type's page replaces the pick (Review Focus 5)
    assert found["replaced"] == []


@pytest.mark.parametrize("hash_", ["", "#pick"])
@pytest.mark.parametrize("storage", [{"store": "ramilevy"}, {}, {"store": "garbage"}, "blocked", "throws"])
def test_the_root_never_sends_anyone_on(storage, hash_):
    # The owner (2026-11-16): the site's name leads to the front page, and the shopper stays there; "change"
    # (index.html#pick) is an ordinary link to the picker. A remembered pick, none, one that no longer fits, storage
    # blocked: location.replace is never called, and the root never writes the pick.
    found = _site(_root_page(), storage, hash=hash_)
    assert found["replaced"] == []
    assert found["stored"] == (storage if isinstance(storage, dict) else None)


@pytest.mark.parametrize("hash_", ["", "#pick"])
@pytest.mark.parametrize("column", COLUMNS, ids=lambda column: column.key)
def test_the_root_offers_the_remembered_store_first(column, hash_):
    # "Your store", then the store type's name, a link to its front page, first on the page, right before the
    # headline's block; the header's store line hidden there and left as the build wrote it (call 10).
    page = _site(_root_page(), {"store": column.key}, hash=hash_)["page"]
    assert _shortcut("", column.key, column.name) in page
    assert page.count('class="yours"') == 1
    assert _asking(hidden=True) in page


@pytest.mark.parametrize("storage", [{}, {"store": "garbage"}, "blocked", "throws"])
def test_the_root_with_no_store_remembered_has_no_shortcut(storage):
    page = _site(_root_page(), storage)["page"]
    assert "yours" not in page and "Your store" not in page
    assert _asking() in page


def test_the_roots_shortcut_and_search_go_from_the_root():
    # The pick link's address is read as before, its line hidden or not: on a root page in a folder (none is built so),
    # the shortcut and a search both start from the site's root.
    responses = {"../search/pieces.json": {"status": 200, "body": []}, f"../p/{CODE}.html": {"status": 200}}
    found = _site(_root_page("../", search=True), {"store": "osherad"}, inputs=[{"value": CODE}], responses=responses)
    assert _shortcut("../", "osherad", "Osher Ad") in found["page"]
    assert _asking(up="../", hidden=True) in found["page"]
    assert found["requests"] == [{"url": "../search/pieces.json", "method": "GET"},
                                 {"url": f"../p/{CODE}.html", "method": "HEAD"}]


@pytest.mark.parametrize("dom, up", [
    (_store_page("carrefour-market"), "../"), (_product_page(["carrefour-market"], ["carrefour-market"]), "../")])
def test_the_header_names_the_pick_on_every_page_but_the_root(dom, up):
    found = _site(dom, {"store": "carrefour-market"}, hash="#pick")
    assert _named(up, "carrefour-market", "Carrefour Market") in found["page"]
    assert "yours" not in found["page"]                       # the shortcut is the root's alone


@pytest.mark.parametrize("storage", [{}, {"store": "garbage"}, "blocked"])
def test_the_header_without_a_pick_asks_for_one(storage):
    found = _site(_product_page(PARTS, BADGES), storage)
    assert _asking("../") in found["page"]


@pytest.mark.parametrize("storage", [{}, {"store": "ramilevy"}, "blocked"])
def test_a_store_pages_header_names_its_own_store(storage):
    # On its first visit too, and with storage blocked: the page is that store type's.
    assert _named("../", "osherad", "Osher Ad") in _site(_store_page("osherad"), storage)["page"]


def test_a_product_page_opens_the_picks_part_and_lists_the_rest_elsewhere():
    found = _site(_product_page(PARTS, BADGES), {"store": "osherad"})
    page = found["page"]
    assert _open(page) == ["osherad"]                          # the pick's part; the others hidden
    assert _listed(page) == ["ramilevy", "yochananof"]         # the pick's badge not under Elsewhere today
    assert (f'<section data-column="osherad" id="c-osherad">osherad</section>'      # the row moved after the open part,
            f'<h2 class="elsewhere">{ELSEWHERE}</h2><nav class="badges">') in page   # its heading shown
    assert "Not sold at" not in page
    assert found["stored"] == {"store": "osherad"}             # opening a product page never changes the pick


def test_elsewhere_today_never_heads_an_empty_row():
    # The pick's own badge is the row's only one, as on every page of a product one store type sells: its part open,
    # no badge shown, and "Elsewhere today" left hidden over the empty row (the whole-branch review).
    page = _site(_product_page(PARTS, ["osherad"]), {"store": "osherad"})["page"]
    assert _open(page) == ["osherad"] and _listed(page) == []
    assert f'<h2 class="elsewhere" hidden>{ELSEWHERE}</h2>' in page and "Not sold at" not in page


@pytest.mark.parametrize("parts, badges", [(PARTS, BADGES), (["carrefour-city"], [])])
def test_a_product_page_without_the_picks_part_says_not_sold(parts, badges):
    page = _site(_product_page(parts, badges), {"store": "shufersal-deal"})["page"]
    assert _open(page) == []
    assert _listed(page) == badges                             # every badge, or an empty row
    hidden = "" if badges else " hidden"                       # no heading over an empty row
    assert ('</h1><p class="not-sold">Not sold at Shufersal Deal today</p>'
            f'<h2 class="elsewhere"{hidden}>{ELSEWHERE}</h2><nav class="badges">') in page


@pytest.mark.parametrize("storage", [{}, {"store": "garbage"}])
def test_a_product_page_with_no_pick_opens_the_first_badge_and_keeps_the_row_first(storage):
    page = _site(_product_page(PARTS, BADGES), storage)["page"]
    assert _open(page) == ["ramilevy"]
    assert _listed(page) == BADGES
    assert f'</h1><h2 class="elsewhere" hidden>{ELSEWHERE}</h2><nav class="badges">' in page   # as the picker
    assert "Not sold at" not in page


def test_a_badge_tap_shows_its_part_and_keeps_the_pick():
    found = _site(_product_page(PARTS, BADGES), {"store": "osherad"}, clicks=["yochananof"])
    assert _open(found["page"]) == ["osherad", "yochananof"]   # shown on this page, beside the pick's part
    assert found["stored"] == {"store": "osherad"}             # call 6: the pick stays as it was


def test_a_badge_tap_with_no_pick_shows_its_part_and_sets_the_pick():
    found = _site(_product_page(PARTS, BADGES), {}, clicks=["yochananof", "osherad"])
    assert _open(found["page"]) == ["osherad", "ramilevy", "yochananof"]
    assert found["stored"] == {"store": "yochananof"}          # Question 1: the first tap picks; the next only shows


def test_search_from_a_store_page_asks_from_the_root():
    code = _site(_store_page("osherad"), inputs=[{"value": CODE}],
                 responses={"../search/pieces.json": {"status": 200, "body": []}, f"../p/{CODE}.html": {"status": 200}})
    assert code["requests"] == [{"url": "../search/pieces.json", "method": "GET"},
                                {"url": f"../p/{CODE}.html", "method": "HEAD"}]
    assert f'<a href="../p/{CODE}.html">' in code["html"]
    name = _site(_store_page("osherad"), inputs=[{"value": "שמר"}],
                 responses={"../search/pieces.json": {"status": 200, "body": ["05e9"]},
                            "../search/05e9.json": {"status": 200, "body": [_entry("7290000000008", "שמרים")]}})
    assert [r["url"] for r in name["requests"]] == ["../search/pieces.json", "../search/05e9.json"]
    assert '<a href="../p/7290000000008.html">' in name["html"]


@pytest.mark.parametrize("storage", ["blocked", "throws"])
def test_blocked_storage_leaves_search_working(storage):
    # Reading localStorage throws ("blocked"), or getItem and setItem do: no error stops the script (the harness exits 1
    # on one), search works, and a product page is as with no pick.
    found = _site(_store_page("osherad"), storage, inputs=[{"value": "שמר"}],
                  responses={"../search/pieces.json": {"status": 200, "body": ["05e9"]},
                             "../search/05e9.json": {"status": 200, "body": [_entry("7290000000008", "שמרים")]}})
    assert '<a href="../p/7290000000008.html">' in found["html"]
    page = _site(_product_page(PARTS, BADGES), storage, clicks=["osherad"])["page"]
    assert _open(page) == ["osherad", "ramilevy"]
    assert _listed(page) == BADGES


def test_a_pick_link_with_no_href_leaves_search_working():
    # The root is then the page's own folder, as before q33, and nothing stops the script (the harness exits 1 on a throw).
    page = [_el("header", {}, _el("a", {"id": "pick-link"}, PICK)),
            _el("main", {"data-store": "osherad"}, _el("input", {"id": "q"}))]
    found = _site(page, {}, inputs=[{"value": "שמר"}],
                  responses={"search/pieces.json": {"status": 200, "body": ["05e9"]},
                             "search/05e9.json": {"status": 200, "body": [_entry("7290000000008", "שמרים")]}})
    assert '<a href="p/7290000000008.html">' in found["html"]
    assert found["stored"] == {"store": "osherad"}


# the word index, held to its Python twin (the product-names plan's Task 2)

ON = "?words=on"
FLAGGED = "<p>There may be more matches. Type more letters to find them.</p>"
MEASURE = re.compile(r'<p class="measure">Word index: (\d+) files? read \((\d+) KB\), (\d+) ms\.</p>$')


def _parsed(built):
    """Built files (key -> bytes) as the harness takes them: key -> JSON."""
    return {key: json.loads(body) for key, body in built.items()}


def _words(built, queries):
    """The script's `wordsFor` over the built files, for each [query, today]: {shown: barcodes, flagged, read}."""
    return _run("words", {"files": _parsed(built), "queries": queries})


def _python(built, query, today):
    found = lookup(built.get, query, today)
    return {"shown": [item[0] for item in found.shown], "flagged": found.flagged, "read": found.read}


def _served(*builds, failing=(), rejecting=()):
    """The fake fetch's answers: every built file, then a 403 for each key in `failing` and no answer at all (the
    network down) for each in `rejecting`."""
    responses = {key: {"status": 200, "body": json.loads(body)} for built in builds for key, body in built.items()}
    responses.update({key: {"status": 403} for key in failing})
    responses.update({key: {"reject": True} for key in rejecting})
    return responses


def _search(typed, responses, search=ON):
    """A search box page with `search` as its address's query string, each of `typed` typed in turn."""
    return _run("page", {"search": search, "inputs": [{"value": value} for value in typed], "responses": responses})


def _listed_codes(html):
    return re.findall(r'<li><a href="p/([^"]+)\.html">', html)


def _milk_index(n=120):
    """`n` products "שוקולד חלב <n>" ("חלב" and "שוקולד" whole tokens, "שוק" and "שוקו" only starts) and three "חלב
    טרי <n>", the only titles that start with ח: today's pieces and the word index cut at 2,000 bytes, so "חלב" is a
    big node in parts and today's search for it finds three."""
    covered = _catalogue(*(_item(f"72900000{number:05d}", {"ramilevy": f"שוקולד חלב {number}"}) for number in range(n)),
                         *(_item(f"72900000{900 + number:05d}", {"osherad": f"חלב טרי {number}"}) for number in range(3)))
    return covered, pieces(covered), dict(files(covered, None, 2000))


def _small_index():
    """Four products, three with a name in English the model wrote (no title starts with a Latin letter)."""
    a = _item("7290000000031", {"ramilevy": "חלב תנובה 3%"})
    b = _item("7290000000048", {"ramilevy": "משקה חלב"})
    c = _item("7290000000055", {"ramilevy": "שוקו בשקית"})
    d = _item("7290000000062", {"ramilevy": "חחלב"})      # holds "חלב" inside a word only
    covered = _catalogue(a, b, c, d)
    extra = {a.code: Extra("Tnuva milk 3%", ("Tnuva milk 3%", "חלב טרי")), b.code: Extra("Milk drink", ("Milk drink",)),
             c.code: Extra("Chocolate milk", ("Chocolate milk",))}
    return covered, pieces(covered), dict(files(covered, extra))


def test_tokens_agree_with_python():
    names = ["דאו.דריי", "3%", "½", "שָׁלוֹם", "a_b", "x2y", "٣", "a-b", "\U0001d400lpha.b", "a.b a b.a", "%", "",
             "\U0001d400 \U0001d400\U0001d400.x"]
    names += sorted({normalize(name) for item in registry(400, "q50-a").values() for name in item.names.values()})
    assert _run("tokensOf", names) == [tokens(name) for name in names]
    assert tokens("\U0001d400lpha.b") == ["\U0001d400lpha.b", "\U0001d400lpha", "b"]   # one character, not two


def test_as_word_entry_agrees_with_python():
    today = [item for key, body in pieces(registry(400, "q50-a")).items() if key != "search/pieces.json"
             for item in json.loads(body)]
    assert len(today) == 400
    assert _run("asWordEntry", today) == [as_word_entry(item) for item in today]


def test_steps_agree_with_python():
    everything = [item for item, _ in STEP_CASES] + STEP_TIES
    queries = [STEP_QUERY, "milk", "MILK 3 pack", "fresh", "3", "cream milk", "semimilk", "milk 3%", "pack", "fresh 3",
               "zzz", ""]
    calls = [[query, item] for query in queries for item in everything]
    assert _run("stepOf", calls) == [list(step(query, item)) for query, item in calls]
    # Their order: every crafted entry that holds both words of the search, in one leaf the manifest names.
    leaf = {MANIFEST: json.dumps({"v": 1, "nodes": {"mi": [len(everything), 0, 1]}}).encode(),
            node_key("mi"): json.dumps(everything).encode()}
    expected = _python(leaf, STEP_QUERY, [])
    assert expected["shown"] == [item[0] for item in sorted(everything, key=lambda item: order_key(STEP_QUERY, item))
                                 if item[0] not in {"7290000000701", "7290000000702", "7290000000703"}]
    assert _words(leaf, [[STEP_QUERY, []]]) == [expected]


def test_ties_go_by_title_then_barcode_in_code_point_order():
    # Python orders strings by code point, the script's `<` by UTF-16 unit; they differ for a character from U+E000 to
    # U+FFFF (here a full-width "a") against one above U+FFFF (U+1D400), and the script must order as Python does.
    covered = _catalogue(_item("7290000000093", {"ramilevy": "חלב טרי"}), _item("7290000000086", {"ramilevy": "חלב טרי"}),
                         _item("7290000000079", {"ramilevy": "חלב \U0001d400"}), _item("7290000000062", {"ramilevy": "חלב \uff41"}))
    built = dict(files(covered))
    expected = _python(built, "חלב", [])
    assert expected["shown"] == ["7290000000086", "7290000000093", "7290000000062", "7290000000079"]
    assert _words(built, [["חלב", []]]) == [expected]


def test_pick_agrees_with_python():
    calls = [[NODES, ["abc"]], [NODES, ["abcz"]], [NODES, ["ab"]], [NODES, ["abd"]], [NODES, ["abde"]], [NODES, ["ax"]],
             [NODES, ["abx"]], [NODES, ["cd", "ax"]], [NODES, ["cd", "abc"]], [NODES, ["abc", "cd"]],
             [NODES, ["xy", "abd"]], [NODES, ["ef", "gh"]], [NODES, ["ef", "abd"]], [NODES, ["gh", "ab"]],
             [NODES, ["abc", "xz"]], [NODES, ["pr", "pq"]], [NODES, ["a", "abc"]], [NODES, ["a", "b"]]]
    # A prefix's length and its order go by code point: "\U0001d400b" is two characters, shorter than "abc", and a
    # full-width "a" (U+FF41) comes before U+1D400.
    wide = {"\U0001d400b": [3, 0, 0], "\uff41b": [3, 0, 0], "abc": [3, 0, 0], "ab": [10, 2, 0]}
    calls += [[wide, ["\U0001d400b", "\uff41b"]], [wide, ["abc", "\U0001d400b"]], [wide, ["\U0001d400"]]]
    expected = [pick({"v": 1, "nodes": nodes}, words) for nodes, words in calls]
    assert expected[-3:] == [Node("leaf", "\uff41b", 3, 0), Node("leaf", "\U0001d400b", 3, 0), None]   # one character walks nothing
    found = _run("pickNode", [[{"v": 1, "nodes": nodes}, words] for nodes, words in calls])
    assert found == [None if node is None else asdict(node) for node in expected]


def test_word_lookup_agrees_with_python():
    covered = registry(400, "q50-a")
    extra = extras(covered, "q50-a")
    entries = [entry(item, extra.get(code)) for code, item in covered.items()]
    built = dict(files(covered, extra, 600))
    todays = pieces(covered)
    calls = [[query, today_lookup(todays.get, query)] for query in _searches(covered, extra, entries)]
    expected = [_python(built, query, today) for query, today in calls]
    assert _words(built, calls) == expected
    kinds = {("flagged" if found["flagged"] else "read" if len(found["read"]) > 1 else
              "manifest only" if found["read"] else "nothing read") for found in expected}
    assert kinds == {"flagged", "read", "manifest only", "nothing read"}


def test_a_manifest_and_files_from_two_builds_never_throw_and_show_each_product_once():
    covered = registry(400, "q50-a")
    extra = extras(covered, "q50-a")
    entries = [entry(item, extra.get(code)) for code, item in covered.items()]
    other = registry(400, "q50-b")
    mixed = {**dict(files(covered, extra, 600)), MANIFEST: dict(files(other, extras(other, "q50-b"), 600))[MANIFEST]}
    todays = pieces(covered)
    calls = [[query, today_lookup(todays.get, query)] for query in _searches(covered, extra, entries)[::7]]
    found = _words(mixed, calls)                         # the harness exits 1 on a throw
    assert found == [_python(mixed, query, today) for query, today in calls]
    assert any(len(result["read"]) > 1 and result["shown"] for result in found)
    for (query, today), result in zip(calls, found):
        assert len(result["shown"]) == len(set(result["shown"])) <= 50, query
        assert {item[0] for item in today} <= set(result["shown"]), query
    # Parts from two builds: part 1 as an earlier build left it, holding part 0's products again.
    covered, _, built = _milk_index()
    mixed = {**built, node_key("חלב", 1): built[node_key("חלב", 0)]}
    today = [as_today for as_today in json.loads(pieces(covered)["search/05d7.json"])[:1]]
    for query in ("חלב", "חלב שוק"):
        [result] = _words(mixed, [[query, today]])
        assert len(result["shown"]) == len(set(result["shown"])) == 50 and result["shown"].count(today[0][0]) == 1
        assert result == _python(mixed, query, today)


def test_an_unknown_manifest_version_reads_no_word_file():
    covered, todays, built = _small_index()
    today = today_lookup(todays.get, "חלב")
    assert [item[0] for item in today] == ["7290000000062", "7290000000031"]    # "חחלב" holds it inside a word
    read = _words(built, [["חלב", today]])
    assert read == [_python(built, "חלב", today)] and "7290000000048" in read[0]["shown"]   # version 1: read
    today_only = {"shown": ["7290000000031", "7290000000062"], "flagged": False, "read": [MANIFEST]}
    manifest = json.loads(built[MANIFEST])
    for other in ({**manifest, "v": 2}, {**manifest, "v": "1"}, {"nodes": manifest["nodes"]}, [manifest], None):
        broken = {**built, MANIFEST: json.dumps(other).encode()}
        assert _words(broken, [["חלב", today]]) == [today_only] and _python(broken, "חלב", today) == today_only
    page = _search(["חלב"], _served(todays, {**built, MANIFEST: json.dumps({**manifest, "v": 2}).encode()}))
    assert [r["url"] for r in page["requests"] if r["url"].startswith("search/w/")] == [MANIFEST]
    assert _listed_codes(page["html"]) == today_only["shown"]


def test_with_the_switch_a_search_with_no_piece_reads_the_word_index():
    covered, todays, built = _small_index()
    assert today_lookup(todays.get, "milk") == []                       # no title starts with a Latin letter
    english = [item[0] for item in lookup(built.get, "milk", []).shown]
    hebrew = [item[0] for item in lookup(built.get, "חלב", []).shown]
    assert sorted(english) == ["7290000000031", "7290000000048", "7290000000055"]
    assert hebrew == ["7290000000031", "7290000000048"]                 # "חחלב" holds it inside a word only
    cases = [("milk", _served(todays, built), english),                                  # no piece for the letters
             ("חלב", _served(todays, built, failing=["search/pieces.json"]), hebrew),       # the list of pieces fails
             ("חלב", _served(todays, built, failing=["search/05d7.json"]), hebrew)]         # the piece fails
    for typed, responses, expected in cases:
        html = _search([typed], responses)["html"]
        assert _listed_codes(html) == expected, typed
        assert FAILED not in html and NOTHING not in html, typed


def test_with_the_switch_offline_shows_the_failure_message():
    covered, todays, built = _small_index()
    everything = [*todays, *built]
    offline = _search(["חלב"], _served(rejecting=everything))
    assert FAILED in offline["html"] and NOTHING not in offline["html"]
    assert MANIFEST in [r["url"] for r in offline["requests"]]          # the word step ran, and read no manifest either
    # The letters have no piece, and the manifest cannot be read.
    for broken in ({"failing": [MANIFEST]}, {"rejecting": [MANIFEST]}):
        html = _search(["milk"], _served(todays, built, **broken))["html"]
        assert FAILED in html and NOTHING not in html
    # Today's piece failed and the word index has nothing: what today's search would have found is not known.
    html = _search(["חלבון"], _served(todays, built, failing=["search/05d7.json"]))["html"]
    assert FAILED in html and NOTHING not in html
    # Everything read, and nothing found: nothing found.
    for typed in ("milkshake", "חלבון", "xq"):
        html = _search([typed], _served(todays, built))["html"]
        assert NOTHING in html and FAILED not in html, typed


def test_without_the_switch_no_word_file_is_fetched():
    covered, todays, built = _small_index()
    on_main = ('<ul><li><a href="p/7290000000055.html"><span class="as-listed" lang="he" dir="rtl">שוקו בשקית</span></a> '
               "<small>7290000000055</small></li></ul>")
    for search in ("", "?words=off", "?words=ON", "?word=on", "?x=words=on"):
        page = _search(["חלב", "milk", "שוקו"], _served(todays, built), search)
        assert [r["url"] for r in page["requests"]] == ["search/pieces.json", "search/05d7.json", "search/05e9.json"]
        assert page["html"] == on_main, search
        page = _search(["milk"], _served(todays, built), search)
        assert page["html"] == f"<p>{NOTHING} Try fewer letters, or browse by first letter.</p>", search


def test_a_word_file_that_parses_but_is_not_a_list_shows_todays_list():
    """A word file that is JSON but no list (an object, a number, a string, true: another layout's file, or an error
    answer in JSON) gives today's list ranked, in the script as in Python, and never throws (Review Focus 2; the Phase 1
    review's F3)."""
    covered, todays, built = _milk_index()
    today = today_lookup(todays.get, "חלב")
    ranked = [item[0] for item in sorted(map(as_word_entry, today), key=lambda item: order_key("חלב", item))]
    for odd in ({"entries": []}, 5, "חלב טרי", True):
        for part in (0, 1):
            broken = {**built, node_key("חלב", part): json.dumps(odd, ensure_ascii=False).encode()}
            expected = _python(broken, "חלב", today)
            assert (expected["shown"], expected["flagged"]) == (ranked, False)
            assert expected["read"][-1] == node_key("חלב", part)                 # the odd part, read last
            assert _words(broken, [["חלב", today]]) == [expected], (odd, part)   # the harness exits 1 on a throw


def test_a_word_that_names_an_inherited_property_is_no_node():
    """The manifest's nodes are its own keys only: a search word such as "constructor" or "__proto__", whose every
    shorter start is a big node, ends on no node, as in Python, never on what every JavaScript object inherits (the Phase
    1 review's F3)."""
    nodes = {word[:end]: [500, 3, 0] for word in ("constructor", "__proto__") for end in range(2, len(word))}
    manifest = {"v": 1, "nodes": nodes}
    calls = [["constructor"], ["__proto__"], ["co", "constructor"], ["constructo"]]
    expected = [pick(manifest, words) for words in calls]
    assert expected == [None, None, None, Node("start", "constructo", 500, 3)]
    assert _run("pickNode", [[manifest, words] for words in calls]) == [
        None if node is None else asdict(node) for node in expected]   # the harness exits 1 on a throw


def test_with_the_switch_a_missing_word_file_shows_todays_list():
    covered, todays, built = _milk_index()
    nodes = json.loads(built[MANIFEST])["nodes"]
    assert nodes["חלב"][1] > 1                                        # a big node, in parts
    today = today_lookup(todays.get, "חלב")
    assert len(today) == 3
    ranked = [item[0] for item in sorted(map(as_word_entry, today), key=lambda item: order_key("חלב", item))]
    for part in (0, 1):
        failing = node_key("חלב", part)
        assert [item[0] for item in lookup({**built, failing: None}.get, "חלב", today).shown] == ranked
        html = _search(["חלב"], _served(todays, built, failing=[failing]))["html"]
        assert _listed_codes(html) == ranked
        assert FAILED not in html and NOTHING not in html
        assert int(MEASURE.search(html)[1]) == 1 + part                # the manifest, and the parts read before it


def test_the_flagged_list_says_so():
    covered, todays, built = _milk_index()
    assert lookup(built.get, "שוקו שוק", today_lookup(todays.get, "שוקו שוק")).flagged
    html = _search(["שוקו שוק"], _served(todays, built))["html"]
    assert len(_listed_codes(html)) == 50 and FLAGGED in html
    assert html.index(FLAGGED) > html.index("</ul>")                   # after the list, before the measure line
    assert MEASURE.search(html[html.index(FLAGGED) + len(FLAGGED):])
    for typed in ("חלב שוק", "שוקו"):
        assert not lookup(built.get, typed, today_lookup(todays.get, typed)).flagged
        assert FLAGGED not in _search([typed], _served(todays, built))["html"], typed


def test_the_measure_line_only_with_the_switch():
    covered, todays, built = _milk_index()
    found = lookup(built.get, "חלב", today_lookup(todays.get, "חלב"))
    size = sum(len(built[key]) for key in found.read)
    assert len(found.read) > 2 and size > 2000
    html = _search(["חלב"], _served(todays, built))["html"]
    line = MEASURE.search(html)
    assert line and html.endswith(line[0])
    assert (int(line[1]), int(line[2])) == (len(found.read), int(size / 1000 + 0.5))
    assert f"Word index: {len(found.read)} files read (" in line[0]
    one = _search(["xq"], _served(todays, built))["html"]              # the manifest alone: one file
    assert MEASURE.search(one)[0].startswith('<p class="measure">Word index: 1 file read (')
    for search in ("", "?words=off"):
        html = _search(["חלב", "xq"], _served(todays, built), search)["html"]
        assert "Word index" not in html and "measure" not in html

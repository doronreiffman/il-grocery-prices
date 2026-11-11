"""search.js (`src/shopper/static/search.js`; the plan's Task 17, and the store picker, docs/store-first.md, q33) under
Node, through `tests/search_harness.js`. Search: its normalisation agrees with `shopper.search`'s, it names the piece a
query belongs in, it matches in name order and stops at 50, it asks for a barcode's page by HEAD and says what the site
has, and it asks from the site's root on a page in a folder. The picker: its store names are the columns, a remembered
pick counts only when it is one of them and storage never stops the script, the header names the pick, the root sends a
remembered pick to its store page unless "change" asked for the picker, a store page remembers its store, and a product
page opens the pick's part and lists the rest under "Elsewhere today". Node is a CI tool for this one file (Node 22.11.0
there); a machine without it fails these tests, as it should.

The fake page (the harness's `page`) is a small DOM, a search box (`#q`) alone unless a test gives one, with a storage, a
location and a fetch that records its requests; the answers are the results box's HTML, the page's HTML after the
script, what the storage holds and where `location.replace` was sent."""
import json
import random
import re
import subprocess
from pathlib import Path

import pytest

from shopper.columns import COLUMNS
from shopper.search import normalize
from shopper.words import not_sold

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


# the root, the redirect and the header

def test_root_of():
    assert _run("rootOf", ["index.html#pick", "../index.html#pick", "../../index.html#pick"]) == ["", "../", "../../"]
    assert _run("rootOf", ["../index.html", "../about.html#pick"]) == ["", ""]   # not the picker's: the page's folder


@pytest.mark.parametrize("pick, hash_, url", [
    ("osherad", "", "store/osherad.html"), ("shufersal-deal", "", "store/shufersal-deal.html"),
    ("osherad", "#q", "store/osherad.html"),        # any other hash
    ("osherad", "#pick", None),                     # "change": the picker, not straight back
    (None, "", None), (None, "#pick", None),        # no pick
])
def test_redirect_for(pick, hash_, url):
    assert _run("redirectFor", [[pick, hash_]]) == [url]


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
    ("osherad", ["osherad"], [], _layout("osherad", heading=True)),
    # sold there before, not today: its part (with its last-seen line) open, every badge under Elsewhere
    ("carrefour-city", PARTS, BADGES, _layout("carrefour-city", elsewhere=BADGES, heading=True)),
    # a pick the page has no part for: the not-sold line, then every badge
    ("shufersal-deal", PARTS, BADGES, _layout(not_sold="shufersal-deal", elsewhere=BADGES, heading=True)),
    # sold nowhere today: the line and an empty row
    ("shufersal-deal", ["carrefour-city"], [], _layout(not_sold="shufersal-deal", heading=True)),
    ("shufersal-deal", [], [], _layout(not_sold="shufersal-deal", heading=True)),
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
    """Every page's header: the pick link, whose href leads up to the site's root."""
    return _el("header", {}, _el("a", {"id": "pick-link", "href": f"{up}index.html#pick"}, PICK))


def _root_page():
    links = [_el("a", {"href": f"store/{column.key}.html"}, column.name) for column in COLUMNS]
    return [_header(""), _el("main", {}, _el("section", {"id": "pick", "data-page": "root"}, *links))]


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
    return (f'<header><a href="{up}store/{key}.html">{name}</a> · '
            f'<a id="pick-link" href="{up}index.html#pick">change</a></header>')


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


@pytest.mark.parametrize("storage, hash_, replaced", [
    ({"store": "ramilevy"}, "", ["store/ramilevy.html"]),      # a remembered pick: straight to its page
    ({"store": "ramilevy"}, "#pick", []),                      # "change": the picker stays
    ({}, "", []), ({"store": "garbage"}, "", []),              # no pick, or one that no longer fits
])
def test_the_root_sends_a_remembered_pick_to_its_store_page_and_change_does_not(storage, hash_, replaced):
    found = _site(_root_page(), storage, hash=hash_)
    assert found["replaced"] == replaced
    assert found["stored"] == storage                          # the root never writes the pick


@pytest.mark.parametrize("dom, up", [
    (_root_page(), ""), (_store_page("carrefour-market"), "../"),
    (_product_page(["carrefour-market"], ["carrefour-market"]), "../")])
def test_the_header_names_the_pick_on_every_page(dom, up):
    found = _site(dom, {"store": "carrefour-market"}, hash="#pick")
    assert _named(up, "carrefour-market", "Carrefour Market") in found["page"]


@pytest.mark.parametrize("storage", [{}, {"store": "garbage"}, "blocked"])
def test_the_header_without_a_pick_asks_for_one(storage):
    found = _site(_product_page(PARTS, BADGES), storage)
    assert f'<header><a id="pick-link" href="../index.html#pick">{PICK}</a></header>' in found["page"]


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


@pytest.mark.parametrize("parts, badges", [(PARTS, BADGES), (["carrefour-city"], [])])
def test_a_product_page_without_the_picks_part_says_not_sold(parts, badges):
    page = _site(_product_page(parts, badges), {"store": "shufersal-deal"})["page"]
    assert _open(page) == []
    assert _listed(page) == badges                             # every badge, or an empty row
    assert ('</h1><p class="not-sold">Not sold at Shufersal Deal today</p>'
            f'<h2 class="elsewhere">{ELSEWHERE}</h2><nav class="badges">') in page


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

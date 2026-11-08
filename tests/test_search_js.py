"""search.js (`src/shopper/static/search.js`; the plan's Task 17) under Node, through `tests/search_harness.js`: its
normalisation agrees with `shopper.search`'s, it names the piece a query belongs in, it matches in name order and stops
at 50, it asks for a barcode's page by HEAD and says what the site has. Node is a CI tool for this one file (Node
22.11.0 there); a machine without it fails these tests, as it should.

The fake page is a search box (`#q`) and a fetch that records its requests; the answers are the results box's HTML."""
import json
import random
import subprocess
from pathlib import Path

import pytest

from shopper.search import normalize

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
    assert "first 50" in html


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

"""Search and browse (`shopper.search`; the plan's Task 17): the normalisation table and its twin in `search.js`, the
index pieces, the browse pages. Names are synthetic. The script's own behaviour is `tests/test_search_js.py`'s."""
import json
import re
from collections import Counter
from datetime import date

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from shopper import search
from shopper.history import Covered
from shopper.search import NORMALIZE, PIECE_MAX, SCRIPT, browse_pages, browse_path, normalize, pieces
from shopper.words import CREDIT_START, NEVER, SITE_NAME, date_line

DAY = date(2026, 11, 6)
DEAL, RAMI = "shufersal-deal", "ramilevy"
PIECE_KEY = re.compile(r"search/(.+)\.json")


def _item(code, names):
    """A covered product; its title the longest name, a tie to the first in code-point order, as the registry has it."""
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=None, first_covered=date(2026, 10, 1), last_wide={})


def _catalogue(*items):
    return {item.code: item for item in items}


A = _item("7290000000001", {DEAL: "גבינה צהובה פרוסה", RAMI: "פרוסות גבינה"})   # the names start with two letters
B = _item("7290000000002", {DEAL: "Coca-Cola ZERO 1.5L"})                       # no Hebrew name
C = _item("7290000000003", {RAMI: "3 במחיר 2 שוקולד"})                           # begins with a digit
D = _item("7290000000004", {DEAL: "שמן זית כתית", RAMI: "שמן זית כתית"})         # both columns say the same
E = _item("7290000000005", {DEAL: "שוקולד חלב", RAMI: "שוקולד חלב מ\"ל"})         # a double quote inside the name
F = _item("7290000000006", {DEAL: "קוטג' תנובה 5%", RAMI: "קוטג תנובה 5% 250 גרם"})
CATALOGUE = _catalogue(A, B, C, D, E, F)
SHIN, ALEF, GIMEL, QOF = "05e9", "05d0", "05d2", "05e7"


def _read(files):
    """The entries of every piece by key, `pieces.json` apart."""
    return {key: json.loads(body) for key, body in files.items() if key != "search/pieces.json"}


# normalising

@pytest.mark.parametrize("text, expected", [
    ("קוטג'", "קוטג"),                        # an apostrophe goes
    ('גר"ם', "גרמ"),                          # a double quote goes (and the final letter turns plain)
    ("צ\u05f3יפס", "ציפס"),                   # geresh goes
    ("מ\u05f4ל", "מל"),                       # gershayim goes
    ("\u05da\u05dd\u05df\u05e3\u05e5", "כמנפצ"),   # the five final letters turn plain
    ("שלום", "שלומ"),
    ("Coca COLA zero", "coca cola zero"),    # Latin is lower-cased
    ("ÉCLAIR Noir", "éclair noir"),
    ("  שוקולד \t חלב\n\r\u00a0 מריר ", "שוקולד חלב מריר"),   # spaces collapse; every kind of space is one
    ("a\tb", "a b"), ("a\nb", "a b"), ("a\rb", "a b"), ("a\u00a0b", "a b"),
    ("it's", "its"), ('say "hi"', "say hi"),   # spaces collapse; tab, newline and no-break space are spaces
    ('א " ב', "א ב"),                         # a quote between spaces leaves one space
    ("5% שמן 1.5L", "5% שמנ 1.5l"),          # digits and signs stay
    ("", ""),
    ("   ", ""),
])
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_normalize_is_idempotent():
    for text in ("קוטג' 5%", "\u05da\u05dd\u05df\u05e3\u05e5", "  A  b ", 'מ"ל'):
        assert normalize(normalize(text)) == normalize(text)


# the pieces

def test_every_covered_product_is_in_one_piece():
    files = pieces(CATALOGUE)
    found = [(key, entry[0]) for key, entries in _read(files).items() for entry in entries]
    assert sorted(code for _, code in found) == sorted(CATALOGUE)   # each product once, across all the pieces
    for key, code in found:   # in the piece of the first letter of its longest name, normalised
        assert key == f"search/{ord(normalize(CATALOGUE[code].title)[0]):04x}.json", (key, code)
    keys = sorted(PIECE_KEY.fullmatch(key)[1] for key in files if key != "search/pieces.json")
    assert keys == [f"{ord('3'):04x}", f"{ord('c'):04x}", GIMEL, QOF, SHIN]
    assert json.loads(files["search/pieces.json"]) == keys


def test_a_piece_lists_the_code_the_title_as_published_and_the_normalised_names():
    [entry] = _read(pieces(_catalogue(F)))[f"search/{QOF}.json"]
    assert entry == ["7290000000006", "קוטג תנובה 5% 250 גרם", "קוטג תנובה 5% 250 גרמ", "קוטג תנובה 5%"]


def test_a_piece_lists_its_products_in_name_order():
    items = [_item(f"72900000010{i}", {DEAL: name}) for i, name in enumerate(("שקד", "שוקולד", "שמן", "שוקולד"))]
    [entries] = _read(pieces(_catalogue(*items))).values()
    assert [entry[2] for entry in entries] == ["שוקולד", "שוקולד", "שמנ", "שקד"]
    assert [entry[0] for entry in entries[:2]] == sorted(entry[0] for entry in entries[:2])   # a tie goes by code


def test_every_columns_name_is_searchable():
    entries = {entry[0]: entry for found in _read(pieces(CATALOGUE)).values() for entry in found}
    for code, item in CATALOGUE.items():
        for name in item.names.values():
            assert normalize(name) in entries[code][2:], (code, name)
        assert entries[code][1] == item.title   # the title is shown as published
    assert normalize(A.names[RAMI]) in entries[A.code][2:]   # a name whose first letter is not the title's


def test_pieces_are_the_same_bytes_twice():
    assert pieces(CATALOGUE) == pieces(dict(reversed(CATALOGUE.items())))


def _crowd(count_per_second, seconds, first="ש"):
    """Many products whose names begin with `first`, a spread of second letters: well over 150 KB in one piece."""
    return _catalogue(*(_item(f"72900{n:08d}", {DEAL: f"{first}{second}{i:04d} " + "x" * 30})
                        for n, (second, i) in enumerate((s, i) for s in seconds for i in range(count_per_second))))


def test_a_piece_over_150_kb_splits_by_its_second_letter():
    assert PIECE_MAX == 150_000
    seconds = "מוקרנל"
    crowd = _crowd(334, seconds)
    crowd.update(_catalogue(A))   # a small letter beside the crowd stays whole
    files = pieces(crowd)
    keys = sorted(PIECE_KEY.fullmatch(key)[1] for key in files if key != "search/pieces.json")
    assert f"search/{SHIN}.json" not in files
    assert keys == sorted([GIMEL] + [f"{SHIN}-{ord(second):04x}" for second in seconds])
    assert json.loads(files["search/pieces.json"]) == keys
    sizes = {key: len(body) for key, body in files.items() if key != "search/pieces.json"}
    assert 150_000 < sum(sizes.values()) < 300_000   # the premise: one piece would have been over the limit, under 300 KB
    assert max(sizes.values()) <= 150_000
    found = [entry[0] for entries in _read(files).values() for entry in entries]
    assert sorted(found) == sorted(crowd)   # each product in one piece still
    for key, entries in _read(files).items():
        if "-" in key:   # a split piece holds only names whose second letter its key says
            assert {ord(normalize(entry[1])[1]) for entry in entries} == {int(key.split("-")[1][:4], 16)}


def test_a_piece_is_split_only_when_over_the_limit(monkeypatch):
    crowd = _crowd(40, "מ")
    monkeypatch.setattr(search, "PIECE_MAX", 10**9)
    [whole] = [body for key, body in pieces(crowd).items() if key != "search/pieces.json"]
    monkeypatch.setattr(search, "PIECE_MAX", len(whole))
    assert f"search/{SHIN}.json" in pieces(crowd)   # exactly the limit: whole
    monkeypatch.setattr(search, "PIECE_MAX", len(whole) - 1)
    assert f"search/{SHIN}.json" not in pieces(crowd)   # a byte over: split


def test_the_scripts_table_is_the_pythons():
    script = SCRIPT.read_text(encoding="utf-8")
    parts = script.split("/*NORMALIZE*/")
    assert len(parts) == 3, "search.js holds its table between two /*NORMALIZE*/ markers"
    assert json.loads(parts[1]) == NORMALIZE


def test_the_table_strips_the_quotes_and_turns_the_final_letters_plain():
    assert {char: NORMALIZE[char] for char in "'\"\u05f3\u05f4"} == {"'": "", '"': "", "\u05f3": "", "\u05f4": ""}
    assert {char: NORMALIZE[char] for char in "\u05da\u05dd\u05df\u05e3\u05e5"} == {
        "\u05da": "\u05db", "\u05dd": "\u05de", "\u05df": "\u05e0", "\u05e3": "\u05e4", "\u05e5": "\u05e6"}


# the browse pages

def _linked(pages):
    """The product codes each page links, by page."""
    return {key: re.findall(r'href="\.\./p/(\d+)\.html"', body) for key, body in pages.items()}


def test_browse_pages_reach_every_product():
    pages = browse_pages(CATALOGUE, DAY, "11:48")
    assert sorted(pages) == sorted([f"browse/{GIMEL}.html", f"browse/{QOF}.html", f"browse/{SHIN}.html",
                                    "browse/other.html"])
    linked = _linked(pages)
    assert Counter(code for codes in linked.values() for code in codes) == Counter(list(CATALOGUE))   # each product once
    assert linked[f"browse/{GIMEL}.html"] == [A.code]
    assert linked[f"browse/{QOF}.html"] == [F.code]
    assert linked[f"browse/{SHIN}.html"] == [E.code, D.code]   # name order: שוקולד חלב, then שמן זית כתית
    for item in CATALOGUE.values():
        assert browse_path(item.title) in pages


def test_a_product_with_no_hebrew_name_is_on_other():
    pages = browse_pages(_catalogue(B, C), DAY, "11:48")
    assert list(pages) == ["browse/other.html"]
    assert _linked(pages)["browse/other.html"] == [C.code, B.code]   # "3 ..." before "coca-cola ..."
    assert browse_path(B.title) == browse_path(C.title) == "browse/other.html"
    assert browse_path(D.title) == f"browse/{SHIN}.html"


def test_a_final_letter_starts_the_page_of_its_plain_letter():
    item = _item("7290000000007", {DEAL: "\u05dd" + "אבג"})   # a name that begins with a final mem
    assert browse_path(item.title) == "browse/05de.html" == list(browse_pages(_catalogue(item), DAY, "11:48"))[0]


def test_every_browse_page_links_every_other_and_the_site():
    pages = browse_pages(CATALOGUE, DAY, "11:48")
    for key, body in pages.items():
        letters = re.findall(r'<a href="([^"/]+\.html)"(?: aria-current="page")?>', body)
        assert sorted(letters) == sorted(name.removeprefix("browse/") for name in pages), key
        assert body.count('aria-current="page"') == 1
        assert f'<a href="{key.removeprefix("browse/")}" aria-current="page">' in body
        assert 'href="../index.html"' in body and 'href="../method.html"' in body


def test_a_browse_page_has_the_frame_the_other_pages_have():
    for body in browse_pages(CATALOGUE, DAY, "11:48").values():
        assert '<meta name="robots" content="noindex">' in body
        assert SITE_NAME in body and date_line(DAY) in body
        assert flatten(CREDIT_START) in flatten(body)
        assert "collected by 11:48 Israel time" in body
        assert "Not shopping advice." in body
        assert "<script" not in body
        assert body.startswith("<!doctype html>")
        text = flatten(strip_tags(body))
        assert not PRONOUNS.search(text)
        assert not [phrase for phrase in NEVER if flatten(phrase) in text], text


def test_a_name_is_escaped_in_its_own_span():
    item = _item("7290000000008", {DEAL: '<b>FAKE "x"\n'})
    pages = browse_pages(_catalogue(item), DAY, "11:48")
    body = pages["browse/other.html"]
    assert '<span class="as-listed" lang="he" dir="rtl">&lt;b&gt;FAKE "x"\n</span>' in body
    assert "<b>" not in body


def test_browse_pages_are_the_same_bytes_twice():
    assert browse_pages(CATALOGUE, DAY, "11:48") == browse_pages(dict(reversed(CATALOGUE.items())), DAY, "11:48")


def test_no_products_no_pages():
    assert pieces({}) == {"search/pieces.json": b"[]"}
    assert browse_pages({}, DAY, "11:48") == {}

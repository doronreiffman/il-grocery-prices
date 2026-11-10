"""The front, method, record and basket pages (`shopper.pages`; the plan's Task 18), and what they need of the basket's
pages and build: `basket.page.render_index` in the site's frame, the basket's method as parts, and
`basket.build.build_day(write_pages=False)` (the second pre-flight's S6 and S13).

Pairs, points and column-days are built by hand, as tests/test_product.py builds them (its helpers are imported); the
scored days' summaries as tests/test_record_numbers.py builds them; the basket's public day and the golden build tree
are the basket tests' own. Names, barcodes and store names are synthetic."""
import hashlib
import json
import os
import re
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from basket.chains import CARREFOUR_COLUMNS
from basket.page import Frame, method_parts, render_day, render_index, render_method as basket_method
from basket.stores import Store
from basket.words import ALWAYS as BASKET_ALWAYS, CHAIN_NAMES, METHOD_INTRO, TITLE as BASKET_TITLE
from shopper.columns import BY_KEY, COLUMNS, FLOOR
from shopper.history import ColumnDay
from shopper.pages import (BASKET_PAGE, BASKET_SECTION, CONDITIONS, NO_DEALS, SCORED_SO_FAR, ColumnsToday, Counts,
                           FrontRow, front_rows_of, ordered, render_basket, render_front, render_method, render_record,
                           scorecard_section)
from shopper.product import CHAIN_SPAN, page_path
from shopper.items import HORIZON
from shopper.record import scorecard
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, CREDIT_START, FINE_PRINT, FRONT_RULE, FRONT_TITLE, GAP_HEADING,
                           HIRING, NEVER, club_label, columns_tested, count_line, date_line, formats_note,
                           gap_sentences, no_odds_yet, shown_below, unreadable)
from test_build import NOW, LATER, PAST, build_at, day_file, golden_tree
from test_page import BASKET, EXCLUSIONS, a_public
from test_product import CODE, DAY, SPAN, _days, _listed, _pair, _struct, back
from test_record_numbers import START, _bins, _day, _good, _part

DEAL, SHELI, EXPRESS, UNIVERSE = "shufersal-deal", "shufersal-sheli", "shufersal-express", "shufersal-universe"
CITY, MARKET, RAMI = "carrefour-city", "carrefour-market", "ramilevy"
MILK, PASTA, EGGS = (item.code for item in BASKET.items)
BASKET_DAY = date(2026, 11, 2)
SCRIPT = '<script src="search.js" defer></script>'
NEVER_LIST = re.compile(r'<ul id="never-words">(.*?)</ul>', re.DOTALL)


def _visible(page: str) -> str:
    """The page's text as the site check reads it, with every chain span cut out (Call 11)."""
    return flatten(strip_tags(SPAN.sub(" ", page)))


def _no_never_phrase_and_no_pronoun(page: str) -> None:
    """No NEVER phrase as written or as read, outside the method page's list, and no "we", "our" or "us"."""
    cut = NEVER_LIST.sub(" ", SPAN.sub(" ", page))
    for version in (flatten(strip_tags(cut)), flatten(cut)):
        assert not [phrase for phrase in NEVER if flatten(phrase) in version]
    assert not PRONOUNS.search(flatten(strip_tags(cut)))


# ---- the front page's rows ----

def _two_columns(**more) -> dict:
    """Deal lists it at 11.90 with a deal at 7.90 (depth 4.00 / 11.90, 34%); Sheli at 20.00 with a deal at 10.00 (50%):
    Sheli's is the deeper, though the dearer."""
    return {DEAL: _pair(DEAL, _listed("11.90"), promotions=[_struct("7.90", promotion_id="1")]),
            SHELI: _pair(SHELI, _listed("20.00"), promotions=[_struct("10.00", promotion_id="2")]), **more}


def test_front_rows_one_per_column_and_product_by_depth():
    """Question A under S1: a product with deals at Sheli and at Deal has a row at each, each against its own column's
    30-day median; the rows are by depth, deepest first, whatever the price."""
    rows = front_rows_of(CODE, "TITLE", _two_columns(), _days(), DAY)
    assert [row.column for row in rows] == [DEAL, SHELI]                     # in name order, before `ordered`
    assert {row.column: row.gap.median30 for row in rows} == {DEAL: Decimal("11.90"), SHELI: Decimal("20.00")}
    assert {row.column: row.deal.price for row in rows} == {DEAL: Fraction("7.90"), SHELI: Fraction("10.00")}
    assert [row.column for row in ordered(rows)] == [SHELI, DEAL]
    assert all((row.code, row.title) == (CODE, "TITLE") for row in rows)


def test_a_column_has_one_row_its_lowest_deal_passing_the_front_test():
    """Two promotions at one column pass: one row, the lower deal price, compared exactly."""
    deals = [_struct("8.50", promotion_id="1"), _struct(Fraction("23.69") / 3, kind="n_for_m", buy="3",
                                                        promotion_id="2"), _struct("7.90", promotion_id="3")]
    rows = front_rows_of(CODE, "T", {DEAL: _pair(DEAL, _listed("11.90"), promotions=deals)}, _days(), DAY)
    assert len(rows) == 1
    assert rows[0].deal.price == Fraction("23.69") / 3                    # 7.8966..., below 7.90 though shown 7.90


def test_a_row_only_for_a_deal_passing_the_front_test_and_running_today():
    """A promotion at some stores, one whose price was not read, one starting tomorrow and one ended yesterday give no
    row; nor does a column with 19 days of records in the 30 (Task 9's test, read through the front page)."""
    tomorrow, yesterday = DAY + timedelta(days=1), DAY - timedelta(days=1)
    deals = [_struct("7.90", wide=False), _struct("7.90", valid=False, why="the rate and the price disagree"),
             _struct("7.90", start=tomorrow), _struct("7.90", start=back(9), end=yesterday)]
    pairs = {DEAL: _pair(DEAL, _listed("11.90"), promotions=deals),
             SHELI: _pair(SHELI, _listed("11.90", 0, 19), promotions=[_struct("7.90")])}
    assert front_rows_of(CODE, "T", pairs, _days(), DAY) == []
    pairs[SHELI] = _pair(SHELI, _listed("11.90", 0, 20), promotions=[_struct("7.90")])
    assert [row.column for row in front_rows_of(CODE, "T", pairs, _days(), DAY)] == [SHELI]


def test_a_hole_column_day_has_no_front_row():
    """The second pre-flight's S1: on a column-day with files from fewer than half its stores the prices are from too
    few files, and the column has no front row; another column of the chain still has its own."""
    rows = front_rows_of(CODE, "T", _two_columns(), _days(holes={(DEAL, DAY)}), DAY)
    assert [row.column for row in rows] == [SHELI]


def test_a_deal_whose_figure_equals_the_low_has_no_front_row():
    """Task 15's carry: 3 for ₪4.34 is ₪1.4466... a unit, shown ₪1.45; beside a 90-day low of ₪1.45 it is below the
    low exactly but not as shown, so no front row can show a deal next to an equal low (`on_front` compares the shown
    figures, Task 15's fix round 2)."""
    three = _struct(Fraction("4.34") / 3, kind="n_for_m", buy="3")
    assert front_rows_of(CODE, "T", {DEAL: _pair(DEAL, _listed("1.45"), promotions=[three])}, _days(), DAY) == []
    rows = front_rows_of(CODE, "T", {DEAL: _pair(DEAL, _listed("1.47"), promotions=[three])}, _days(), DAY)
    assert rows[0].deal.price == Fraction(434, 300) and rows[0].deal.buy == 3


def test_a_front_row_keeps_the_promotions_conditions():
    struct = _struct("7.90", restrictions=["club", "other"], programmes=["מועדון", "אפליקציה"], min_spend="150")
    row = front_rows_of(CODE, "T", {DEAL: _pair(DEAL, _listed("11.90"), promotions=[struct])}, _days(), DAY)[0]
    assert (row.restrictions, row.programmes, row.min_spend) == (("club", "other"), ("מועדון", "אפליקציה"),
                                                                 Decimal("150"))


def test_ordered_by_depth_then_column_then_code():
    one, = front_rows_of("2000000000046", "T", {DEAL: _pair(DEAL, _listed("10.00"), promotions=[_struct("5.00")])},
                         _days(), DAY)
    same_depth = [replace(one, column=SHELI), replace(one, code="900"), replace(one, code="1000"), one,
                  replace(one, column=CITY)]
    assert [(row.column, row.code) for row in ordered(same_depth)] == [
        (CITY, "2000000000046"), (DEAL, "900"), (DEAL, "1000"), (DEAL, "2000000000046"), (SHELI, "2000000000046")]


# ---- the front page ----

def _rows() -> list[FrontRow]:
    return front_rows_of(CODE, "גבינה צהובה 200 גרם", _two_columns(), _days(), DAY)


def _front(rows=None, counts=Counts(1840, 6210, 410), marking=("shufersal",), browse="browse/05d2.html") -> str:
    return render_front(_rows() if rows is None else rows, counts, DAY, "12:03", marking, browse)


def test_the_front_page_has_the_always_phrases_and_one_script():
    """The design's "Words": the four ALWAYS phrases on the front page, with or without a row; the search box and
    exactly the one script (Q2); `noindex`, the date line and the credit line (the shared shell)."""
    for page in (_front(), _front(rows=[])):
        text = _visible(page)
        for phrase in ALWAYS:
            assert flatten(phrase) in text, phrase
        assert page.count("<script") == 1 and page.count(SCRIPT) == 1
        assert '<input id="q"' in page
        assert '<meta name="robots" content="noindex">' in page
        assert flatten(date_line(DAY)) in text and flatten(CREDIT_START) in text and "not shopping advice." in text
        _no_never_phrase_and_no_pronoun(page)
    assert NO_DEALS in _front(rows=[]) and NO_DEALS not in _front()
    # deploy prep: the empty table says that no promotion passes the rule, never that no deal is listed, under a count
    # line of thousands of promotions
    assert f'<td colspan="6">No promotion passes the rule today.</td>' in _front(rows=[])


def test_the_front_page_says_the_rule_in_the_formats_words():
    """Question O: the title, the rule naming the store format, and the count line ending "in their store format"."""
    page = _front()
    assert f">{FRONT_TITLE}</h1>" in page
    assert f"The rule: {FRONT_RULE}." in page
    assert count_line(1840, 6210, 410) in page
    assert "in the same store format" in FRONT_RULE and count_line(1, 1, 1).endswith(
        "in their store format, on an item with at least 20 days of records there in the past 30.")
    # what a row needs, in the front test's own days (deploy prep: 20 of the 30, so its 30-day median is not short)
    assert ("<p>Each deal is a promotion carried by at least half of its store format's stores with files that day, on "
            "an item with at least 20 days of records there in the 30 days before today.</p>") in page


def test_a_front_row_shows_its_deal_median_depth_and_conditions():
    """One row per (column, product): the product's link with its name in its span, the column's name, the deal price
    per unit or kilogram with "buy N", the column's 30-day median listed price, the depth as a whole percent from the
    shown figures, the conditions with their source and the fine print label."""
    struct = _struct(Fraction("3.01") / 2, kind="n_for_m", buy="2", per="kg", restrictions=["club"],
                     programmes=["מועדון"], min_spend="150")
    rows = front_rows_of(CODE, "שם", {DEAL: _pair(DEAL, _listed("2.05"), promotions=[struct])}, _days(), DAY)
    assert rows[0].gap.percent == 27 and shown_below(rows[0].gap) == (Decimal("0.54"), 26)    # 1.505 shown 1.51
    page = _front(rows=rows)
    row = re.search(r"<tr data-column[^>]*>(.*?)</tr>", page, re.DOTALL).group(1)
    assert f'<a href="{page_path(CODE)}">{CHAIN_SPAN.format("שם")}</a>' in row
    assert "<td>Shufersal Deal</td>" in row
    assert "Deal price ₪1.51 per kilogram, buy 2" in row
    assert "<td>₪2.05</td>" in row and "<td>26%</td>" in row and "27%" not in row
    assert (f"club members only ({CHAIN_SPAN.format('מועדון')}), from the chain's fields; minimum spend ₪150.00, "
            f"from the chain's fields; {FINE_PRINT}") in row


def test_the_filters_need_no_script():
    """A radio per column and one for all, the club-only and minimum-spend checkboxes, `club_label` beside the first,
    each input ruled by CSS alone (`:checked` and the sibling combinator); a row says what the filters read."""
    restricted = _struct("7.90", restrictions=["chain_card"], promotion_id="1")
    spend = _struct("10.00", min_spend="200", promotion_id="2")
    rows = front_rows_of(CODE, "T", {DEAL: _pair(DEAL, _listed("11.90"), promotions=[restricted]),
                                     SHELI: _pair(SHELI, _listed("20.00"), promotions=[spend])}, _days(), DAY)
    page = _front(rows=rows, marking=("shufersal", "osherad"))
    assert '<input type="radio" name="column" id="f-all" checked>' in page
    for column in COLUMNS:
        radio = f'<input type="radio" name="column" id="f-{column.key}">'
        assert f'{radio}<label for="f-{column.key}">{column.name}</label>' in page
        assert (f'#f-{column.key}:checked ~ .table tbody tr[data-column]:not([data-column="{column.key}"]) '
                "{ display: none; }") in page
    assert re.search(r'<input type="checkbox" id="f-club"><label for="f-club">[^<]+</label> <small>\('
                     + re.escape(club_label(("shufersal", "osherad"))) + r"\)</small>", page)
    assert ('<input type="checkbox" id="f-spend"><label for="f-spend">Hide deals with a minimum spend (from the '
            "chains' fields)</label>") in page           # deploy prep: it reads the fields alone, as the club one
    assert "#f-club:checked ~ .table tbody tr[data-club] { display: none; }" in page
    assert "#f-spend:checked ~ .table tbody tr[data-spend] { display: none; }" in page
    assert re.search(r'<tr data-column="shufersal-deal" data-club="">', page)
    assert re.search(r'<tr data-column="shufersal-sheli" data-spend="">', page)
    plain = front_rows_of(CODE, "T", _two_columns(), _days(), DAY)
    assert re.findall(r"<tr data-column=\"[^\"]+\"( [^>]*)?>", _front(rows=plain)) == ["", ""]


def test_the_story_is_the_top_rows_p7():
    """One deal's story, in the product page's words: the top row's P7 sentences, with its product's link."""
    rows = _rows()
    top = ordered(rows)[0]
    assert top.column == SHELI
    page = _front(rows=list(reversed(rows)))
    story = re.search(r'<section class="story">(.*?)</section>', page, re.DOTALL).group(1)
    assert GAP_HEADING in story
    assert " ".join(gap_sentences(top.gap)) in story
    assert f'<a href="{page_path(CODE)}">' in story and BY_KEY[SHELI].name in story
    assert '<section class="story">' not in _front(rows=[])


def test_the_hiring_line_and_the_links():
    """Question M (f): the hiring line; the footer reaches the basket, the record and the method pages, and the browse
    pages when there are any."""
    page = _front()
    hiring = re.search(r'<p class="hiring">(.*?)</p>', page).group(1)
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', hiring)
    assert [(label, href) for href, label in links] == list(HIRING)
    for path in ("basket.html", "record.html", "method.html", "browse/05d2.html"):
        assert f'href="{path}"' in page
    assert 'href="browse/' not in _front(browse=None)


def test_the_front_page_is_the_same_bytes_whatever_the_rows_order():
    rows = _rows()
    assert _front(rows=rows) == _front(rows=list(reversed(rows)))


# ---- the method page ----

def _store(id_: str, sub_chain: str | None, name: str | None = None) -> Store:
    return Store(id_, sub_chain, name or f"סניף {id_}", "1")


METHOD_EXCLUSIONS = {"shufersal": [_store("601", "5", "בי 601"), Store("413", "2", "שופרסל ONLINE", "2")],
                     "ramilevy": [Store("39", None, "מרלוג אינטרנט", "2")], "osherad": [],
                     "carrefour": [Store("471", "1", "קרפור אונליין", "2")], "yochananof": []}
MEMBERS = {column.key: frozenset({f"{index}1", f"{index}2"}) for index, column in enumerate(COLUMNS)}
OUTSIDE = {"shufersal": [_store("901", "6", "יש חסד 901"), _store("902", "18")], "carrefour": [_store("1", "1")]}
TABLE = {"62": CITY, "2": MARKET, "64": CITY}


def _columns(**more) -> ColumnsToday:
    return ColumnsToday(**({"members": MEMBERS, "outside": OUTSIDE, "under_floor": [UNIVERSE], "carrefour": TABLE}
                           | more))


def _method(columns: ColumnsToday | None = None, exclusions=METHOD_EXCLUSIONS) -> str:
    return render_method(BASKET, exclusions, columns or _columns(), BASKET_DAY, "12:03", "0123456789ab", a_public())


def test_the_method_pages_never_list_is_the_words_list():
    """The design's "Words": the NEVER list as `<ul id="never-words">`, its items NEVER exactly, in order; no NEVER
    phrase anywhere else on the page."""
    page = _method()
    items = re.findall(r"<li>(.*?)</li>", NEVER_LIST.search(page).group(1))
    assert items == [phrase.replace("&", "&amp;") for phrase in NEVER]
    assert page.count('id="never-words"') == 1
    _no_never_phrase_and_no_pronoun(page)


def test_the_method_page_lists_each_column_its_stores_and_the_stores_in_none():
    """Each of the nine with how its stores are chosen and how many are included today; Carrefour's table store by
    store under its two columns, with how it was drawn; the included stores in no column, chain by chain, each by id
    and its listed name in the chain's span (Yesh Chesed's and Carrefour's outside the table); a column under the floor
    named; Rami Levy, Osher Ad and Yochananof each one format (question O)."""
    page = _method()
    nine = re.search(r'<table class="columns">(.*?)</table>', page, re.DOTALL).group(1)
    for column in COLUMNS:
        assert f"<td>{column.name}</td>" in nine
    assert "<td>sub-chain 2 on the day's store list</td>" in nine and "<td>2</td>" in nine
    carrefour = re.search(r'<section id="carrefour">(.*?)</section>', page, re.DOTALL).group(1)
    assert "grouped by the promotions they carry, measured on 5 and 7 November 2026" in carrefour
    assert "the word most of its stores' names carry" in carrefour
    assert "<b>Carrefour City</b>: stores 62 and 64." in carrefour and "<b>Carrefour Market</b>: store 2." in carrefour
    real = render_method(BASKET, METHOD_EXCLUSIONS, _columns(carrefour=CARREFOUR_COLUMNS), BASKET_DAY, "12:03", "x",
                         a_public())
    for store, key in CARREFOUR_COLUMNS.items():
        listed = re.search(rf"<b>{BY_KEY[key].name}</b>: stores ([^.]*)\.", real).group(1)
        assert store in re.split(r", | and ", listed)
    outside = re.search(r'<section id="outside">(.*?)</section>', page, re.DOTALL).group(1)
    assert f"store 901, sub-chain 6, {CHAIN_SPAN.format('יש חסד 901')}" in outside
    assert f"store 902, sub-chain 18, {CHAIN_SPAN.format('סניף 902')}" in outside
    assert f"store 1 {CHAIN_SPAN.format('סניף 1')}" in outside
    assert "Yesh Chesed" in outside
    floor = re.search(r'<section id="floor">(.*?)</section>', page, re.DOTALL).group(1)
    assert f"Shufersal Universe: 2 included stores today, under the floor of {FLOOR}" in floor
    assert "No column" in _method(_columns(under_floor=[]))
    assert "Rami Levy, Osher Ad and Yochananof are each shown as one format, whole." in page
    intro = re.search(r'<section id="columns"><h2>What a column is</h2><p>(.*?)</p>', page).group(1)
    assert (f"each of their formats with at least {FLOOR} included stores on the store lists of 7 November 2026 is a "
            "column of its own (the floor below; the smaller ones then are in no column)") in intro   # re-review, N2
    assert "every measure on the front, product and record pages is a column's" in intro
    assert "The headline basket, in its section below, takes each chain's median instead." in intro
    assert "each format is a column of its own" not in intro and "every measure here" not in intro      # review, 3
    assert "Every included store is in a column today." in _method(_columns(outside={}))


def test_the_method_page_names_the_stores_left_out_by_rule():
    """ALWAYS_SENTENCE says this page gives the rules that leave stores out (Task 15's carry; deploy prep): the store
    list's rule with the basket's list of the stores it leaves out, which of them sit in a column's part of the store
    list (Deal's store 413, Rami Levy's 39), and the file-name rule with Express's store 779, left out through its
    files' names while the list puts it in Express."""
    page = _method()
    columns = re.search(r'<section id="columns">(.*?)</section>', page, re.DOTALL).group(1)
    assert "Shufersal's store 413 (Shufersal Deal) and Rami Levy's store 39 (Rami Levy)" in columns
    assert "store 779" in columns and "Shufersal Express" in columns
    assert "and store 413 “" in page                       # the basket's own list of the stores left out
    none_in_a_column = {**METHOD_EXCLUSIONS, "shufersal": METHOD_EXCLUSIONS["shufersal"][:1], "ramilevy": []}
    assert "in a column's part" not in _method(exclusions=none_in_a_column) and "store 779" in _method()


def test_the_method_pages_store_counts_are_the_store_lists():
    """The final review's finding 7: the columns table counts each column's included stores by the day's store list
    (`ColumnsToday.members`), store 779 among Express's, so its heading says so, and the paragraph on store 779 says
    the table counts such a store, though none of its files counts: not "included today" beside "left out"."""
    page = _method()
    columns = re.search(r'<section id="columns">(.*?)</section>', page, re.DOTALL).group(1)
    assert '<th scope="col">Included stores on today\'s store list</th>' in columns
    assert "Included stores today" not in page
    assert ("The table above counts by the store list, so such a store is among its column's included stores there, "
            "though none of its files counts.") in columns


def test_the_method_page_states_the_rules_with_the_codes_constants():
    """P1 to P10 and F1 to F11 in plain words, with the constants the code fixes (n0, the seed, the block, the
    draws)."""
    page = _method()
    rules = re.search(r'<section id="rules">(.*?)</section>', page, re.DOTALL).group(1)
    for name in [f"P{n} " for n in range(1, 11)] + [f"F{n} " for n in range(1, 12)]:
        assert f"<b>{name}" in rules, name
    for figure in ("n0 = 30", "blocks of 14 consecutive scored days", "10,000 draws", "seed 20261107",
                   "at least 90 scored days", "at most 0.03", "more than 4 holes", "d + 1 to d + 14"):
        assert figure in rules, figure
    assert unreadable("carrefour") in rules and no_odds_yet(DEAL).split(".")[0] in rules
    # P7's front test as built (deploy prep): 20 days of records in the past 30, the low over the past 90
    assert ("the item has at least 20 days of records in the past 30, with the deal price as shown below every listed "
            "price of the past 90 days as shown.") in rules
    assert "rebuilt every morning, which says when it was last seen listed across each column" in rules   # deploy prep
    assert "0123456789ab" in page and 'href="site-days/2026-11-02.json"' in page
    reproduce = re.search(r'<section id="reproduce">(.*?)</section>', page, re.DOTALL).group(1)
    assert "the same numbers on every page, the record's intervals to rounding (F8)." in reproduce    # review, 4
    # deploy prep: true on any day, past the archive's 91st day too: which products have a page, their names and sizes,
    # and when each was last seen listed across a column come from the covered registry, carried from day to day
    assert ("Take each chain's full price and promotion files and its store list of every day from 90 days before "
            "this site's first day to the day, as the chains published them,") in reproduce
    assert ("A page's measures read the day and the 90 days before it; which products have a page, their names and "
            "sizes, and when each was last seen listed across a column come from a record carried from day to day "
            "since the site's first.") in reproduce


def test_the_method_page_carries_the_baskets_method_as_its_own_section():
    """The second pre-flight's S6: the basket's method parts, byte for byte, inside a section whose id is not the
    inner heading's; ids once each."""
    page = _method()
    parts = "".join(method_parts(BASKET, METHOD_EXCLUSIONS, a_public(), BASKET_PAGE))
    assert f'<section id="{BASKET_SECTION}"><h2>{BASKET_TITLE}</h2>{parts}</section>' in page
    assert BASKET_SECTION != "basket" and METHOD_INTRO in parts
    ids = re.findall(r' id="([^"]+)"', page)
    assert len(ids) == len(set(ids))


def test_the_baskets_method_on_the_method_page_speaks_of_the_basket_page():
    """Task 18's review, finding 2: inside the site's method page the basket's words name the basket page, so "What
    this page does not claim" and "every number on the page" stay true there; the basket's own page keeps its words."""
    section = re.search(rf'<section id="{BASKET_SECTION}">(.*)</section>', _method(), re.DOTALL).group(1)
    assert "<h2>What the basket page does not claim</h2>" in section
    assert "The day file holds every number on the basket page and the counts behind them" in section
    assert "What this page does not claim" not in section
    assert "The day file holds every number on the page" not in section
    own = basket_method(BASKET, EXCLUSIONS, a_public())
    assert "<h2>What this page does not claim</h2>" in own and "every number on the page and the counts" in own


def test_basket_method_parts_are_the_baskets_method_page():
    """`basket.page.render_method` joins `method_parts` after its heading, byte for byte as before."""
    page = basket_method(BASKET, EXCLUSIONS, a_public())
    assert "\n".join(method_parts(BASKET, EXCLUSIONS, a_public())) in page


# ---- the record page ----

def _column_days(day: date, holes=(), promo_holes=(), missing=()) -> dict[tuple[str, date], ColumnDay]:
    found = {}
    for column in COLUMNS:
        for n in range(91):
            seen = day - timedelta(days=n)
            hole = (column.key, seen) in holes
            found[(column.key, seen)] = ColumnDay(
                column=column.key, slug=column.slug, day=seen, present=(column.key, seen) not in missing, hole=hole,
                promo_hole=(column.key, seen) in promo_holes, promotions_error=None, included=20,
                with_file=5 if hole else 20, counted=20, promo_files=20)
    return found


RECORD_DAY = date(2026, 12, 31)


def _record(card=None, ledger=None, files=(), column_days=None) -> str:
    return render_record(scorecard([]) if card is None else card, ledger or {}, files,
                         column_days or _column_days(RECORD_DAY), RECORD_DAY, "12:03")


def _scored() -> dict:
    """32 days at Deal from 1 December to 1 January, the model winning, and a late day on 30 November before them;
    each day's 101 rows in three bins, the last holding 1 of 101, under 1%."""
    bins = _bins((1, 40, "6", 6), (3, 60, "21", 18), (9, 1, "0.95", 1))
    return scorecard([_day(-1, {DEAL: _good(0, bins)}, on_time=False),
                      *(_day(n, {DEAL: _good(n, bins)}) for n in range(32))])


def test_the_record_page_from_the_scorecard():
    """Before any scored day: "No forecast has been scored yet", the nine columns tested at once, each column's gate
    closed with its conditions and the reasons, the fine print sentence."""
    page = _record()
    text = _visible(page)
    assert "No forecast has been scored yet." in page
    assert columns_tested(9) in page
    # deploy prep: the lede says when freezing starts, as the code has it (a column's 30th day of records, with a
    # closed day to learn from: shopper.forecast), and as F2 says
    assert ("From a column's 30th day of records, once it has a closed day to learn from (F2), this site freezes that "
            "column's forecasts every day before their outcomes are known and scores them 14 days later against two "
            "rules of thumb (F5).") in page
    for column in COLUMNS:
        section = re.search(rf'<section data-column="{column.key}">(.*?)</section>', page, re.DOTALL).group(1)
        assert "Gate: closed." in section
        assert section.count("does not hold") == 3
        assert "0 scored days of the version in force (model 1, target 1) frozen on time; 90 needed" in section
    assert "Promotion fine print is not read yet." in page
    assert "Model versions scored so far: 0" in page
    assert "seed 20261107" in page and "10,000 draws" in page and "blocks of 14 scored days" in page
    assert flatten(CREDIT_START) in text and flatten(date_line(RECORD_DAY)) in text and "<script" not in page
    _no_never_phrase_and_no_pronoun(page)


def test_the_record_page_shows_each_columns_scores_by_month_and_in_all():
    """F11: per column and version, the whole and each month; the late day shown as late in its own month and counted
    in nothing, so the record visibly starts on the first day frozen on time (F6); intervals from 28 scored days."""
    card = _scored()
    page = _record(card)
    deal = re.search(r'<section data-column="shufersal-deal">(.*?)</section>', page, re.DOTALL).group(1)
    assert "<h3>Model 1, target 1</h3>" in deal
    def rows(table: str) -> dict[str, list[str]]:
        body = re.search(rf'<table class="{table}">(.*?)</table>', deal, re.DOTALL).group(1)
        return {period: re.findall(r"<td>(.*?)</td>", cells)
                for period, cells in re.findall(r'<tr><th scope="row">([^<]+)</th>(.*?)</tr>', body)}

    counts, scores = rows("counts"), rows("scores")
    assert list(counts) == list(scores) == ["All", "November 2026", "December 2026", "January 2027"]
    assert counts["All"] == ["32", "1", "32", "3,232", "3,232", "0", "25%"]
    assert counts["November 2026"][:3] == ["0", "1", "0"] and scores["November 2026"] == ["none"] * 7
    assert counts["December 2026"][:3] == ["31", "0", "31"]
    assert counts["January 2027"][:3] == ["1", "0", "1"] and "<small>too few days</small>" in scores["January 2027"][3]
    whole = card["columns"][DEAL]["versions"][0]["all"]
    model, a = Decimal(whole["brier"]["model"]), Decimal(whole["brier"]["a"])
    assert f"{(model - a).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)}" in deal
    span = whole["intervals"]["model_minus_a"]
    assert f"95%: {span['low']:.4f} to {span['high']:.4f}" in deal
    assert "No forecast has been scored yet." not in page
    assert "Model versions scored so far: 1" in page
    assert "No forecast of this column has been scored yet." in page          # the other columns
    _no_never_phrase_and_no_pronoun(page)


def test_the_record_pages_tables_say_they_count_the_days_scored_so_far():
    """Task 18's review, finding 1: a day is scored 14 days after it is frozen, so the tables hold fewer days than the
    ledger; the sentence before them and their heads say so, and never call their count the days frozen."""
    ledger = {START + timedelta(days=n): datetime.combine(START + timedelta(days=n), time(10, 40), tzinfo=timezone.utc)
              for n in range(46)}
    page = _record(_scored(), ledger)
    section = scorecard_section(_scored())
    assert section.index(SCORED_SO_FAR) < section.index("<table")
    assert "scored 14 days after it is frozen" in SCORED_SO_FAR
    heads = re.findall(r'<th scope="col">([^<]+)</th>', re.search(r'<table class="counts">(.*?)</thead>', section,
                                                                    re.DOTALL).group(1))
    assert heads[1:4] == ["Files scored, frozen on time", "Files scored, frozen late (not counted)",
                          "Days with a scored forecast"]
    assert "Days frozen on time" not in page and "Days late, not counted" not in page
    assert "Forecasts frozen on 46 days, from 1 December 2026 to 15 January 2027: 46 on time, 0 late." in page
    assert SCORED_SO_FAR.startswith("Each column's tables below count only")
    assert SCORED_SO_FAR not in _record() and "<table" not in scorecard_section(scorecard([]))    # re-review, N1


def test_the_scored_so_far_sentence_holds_whenever_the_page_is_built():
    """Task 18's review and the final review's triage (364): the sentence is drawn from the scorecard alone, so it says
    nothing the ledger would have to bear out: a page built 14 days or more after the last freeze (a late or backfill
    build) has every frozen day scored, and "the latest days frozen are not in them yet" would be false there."""
    assert SCORED_SO_FAR == ("Each column's tables below count only the days whose forecasts file has been scored so "
                             f"far: a day's file is scored {HORIZON} days after it is frozen (the days frozen are "
                             "counted further down).")


def test_the_record_page_shows_calibration_and_a_sentence_per_bin_of_one_percent_or_more():
    """F8 and F11: the calibration table and an inline chart, hidden from screen readers; one sentence per bin holding
    1% or more of the version's scored forecasts, none for a bin under it."""
    page = _record(_scored())
    deal = re.search(r'<section data-column="shufersal-deal">(.*?)</section>', page, re.DOTALL).group(1)
    assert '<table class="calibration">' in deal
    assert re.search(r'<svg class="calibration"[^>]* aria-hidden="true"', deal)
    assert deal.count("<circle") == 3
    assert ("Of the scored forecasts from 0.1 to 0.2 (40% of this version's), 15% had a promotion listed across "
            "Shufersal Deal in the 14 days after.") in deal
    assert "from 0.3 to 0.4 (59% of this version's), 30% had" in deal
    assert "from 0.9 to 1.0 (" not in deal
    assert "Calibration error:" in deal


def test_a_baseline_scoring_zero_has_no_skill_and_a_day_of_unscored_rows_scores_nothing():
    """Task 14's widened types: a skill against a baseline whose Brier score is 0 is none, with no interval; a version
    whose rows were all unscored has its counts and no score, and nothing has been scored yet."""
    zero = scorecard([_day(n, {DEAL: _part("10", "0", "15")}) for n in range(28)])
    deal = re.search(r'<section data-column="shufersal-deal">(.*?)</section>', _record(zero), re.DOTALL).group(1)
    whole = re.search(r'<table class="scores">.*?<tr><th scope="row">All</th>(.*?)</tr>', deal, re.DOTALL).group(1)
    assert re.findall(r"<td>(.*?)</td>", whole)[5] == "none<small>no interval</small>"
    unscored = scorecard([_day(0, {DEAL: _part("0", "0", "0", bins=_bins(), unscored=5)})])
    page = _record(unscored)
    assert "No forecast has been scored yet." in page and "Calibration error: none." in page
    assert "<td>5</td><td>0</td><td>5</td>" in page                     # 5 forecasts, 0 scored, 5 unscored


def test_the_scorecard_section_is_the_record_pages_and_the_scorecards_alone():
    """The guard renders the record page's tables again from the site-day file's scorecard (Task 21): the section is
    in the page as `scorecard_section` gives it, and the same bytes from the scorecard read back from JSON as the
    site-day file is written, its keys sorted (the gate's conditions then come back in another order)."""
    card = _scored()
    assert scorecard_section(card) in _record(card)
    assert scorecard_section(json.loads(json.dumps(card))) == scorecard_section(card)
    assert scorecard_section(json.loads(render_day(card))) == scorecard_section(card)
    assert list(json.loads(render_day(card))["columns"][DEAL]["gate"]["conditions"]) != list(CONDITIONS)   # the premise
    assert scorecard_section(card) != scorecard_section(scorecard([]))


def test_the_scorecard_section_gives_the_columns_in_their_order_whatever_the_mappings():
    """The columns come in `COLUMNS`' order, not the order of the scorecard's mapping, which a file read back may change."""
    card = _scored()
    reversed_card = card | {"columns": dict(reversed(card["columns"].items()))}
    assert scorecard_section(reversed_card) == scorecard_section(card)
    assert re.findall(r'<section data-column="([^"]+)"', scorecard_section(reversed_card)) == [
        column.key for column in COLUMNS]


def test_an_open_gate_stops_the_record_page():
    card = scorecard([])
    card["columns"][DEAL]["gate"]["open"] = True
    with pytest.raises(ValueError, match="shufersal-deal"):
        scorecard_section(card)


def test_the_record_page_links_the_files_as_test_records_and_says_when_the_record_starts():
    """Q1, F6: every day's forecasts and scores files and the ledger, labelled as test records, not advice; the days
    frozen, late and missed by the ledger; the record starts on the first day frozen on time."""
    late = datetime(2026, 11, 30, 22, 5, tzinfo=timezone.utc)          # after midnight in Israel
    ledger = {date(2026, 11, 30): late, **{START + timedelta(days=n): datetime.combine(
        START + timedelta(days=n), time(10, 40), tzinfo=timezone.utc) for n in range(30) if n != 4}}
    files = ["scores/2026-12-01.csv.gz", "forecasts/2026-12-02.csv.gz", "forecasts/ledger.csv",
             "forecasts/2026-12-01.csv.gz"]
    page = _record(_scored(), ledger, files)
    section = re.search(r'<section id="files">(.*?)</section>', page, re.DOTALL).group(1)
    assert "test records, not advice" in section
    for path in files:
        assert f'<a href="{path}">{path}</a>' in section
    assert section.index("forecasts/ledger.csv") < section.index("forecasts/2026-12-02.csv.gz") \
        < section.index("forecasts/2026-12-01.csv.gz") < section.index("scores/2026-12-01.csv.gz")
    assert "Forecasts frozen on 30 days, from 30 November 2026 to 30 December 2026: 29 on time, 1 late." in page
    assert "The record starts on 1 December 2026, the first day frozen on time." in page
    assert "Days since 30 November 2026 with no forecasts file: 5 December 2026; 31 December 2026." in page
    empty = _record()
    assert "No forecasts have been frozen yet" in empty and 'id="files"' in empty


def test_the_record_page_says_the_days_read_and_the_column_days_short_of_files():
    """The design's record page: the days the site has, and each column's days short of files."""
    days = _column_days(RECORD_DAY, holes={(DEAL, date(2026, 12, n)) for n in (3, 4, 5)} | {(DEAL, date(2026, 12, 9))},
                        promo_holes={(CITY, date(2026, 12, 7))},
                        missing={(column.key, RECORD_DAY - timedelta(days=n)) for column in COLUMNS
                                 for n in range(60, 91)})
    page = _record(column_days=days)
    section = re.search(r'<section id="days">(.*?)</section>', page, re.DOTALL).group(1)
    assert "The site's build reads the 91 days from 2 October 2026 to 31 December 2026." in section
    # deploy prep: such a day is in P8's count of days with records and named beside it, so it is not left out of it
    assert ("a day whose promotions were short of files or not read is counted as neither on nor off promotion (P8);"
            in section)
    assert "This page reads" not in section                                                    # the review, finding 5
    deal = re.search(r"<tr><th scope=\"row\">Shufersal Deal</th>(.*?)</tr>", section).group(1)
    assert re.findall(r"<td>([^<]*)</td>", deal) == ["56", "3 to 5 December 2026; 9 December 2026", "none",
                                                      "2 October to 1 November 2026"]
    city = re.search(r"<tr><th scope=\"row\">Carrefour City</th>(.*?)</tr>", section).group(1)
    assert re.findall(r"<td>([^<]*)</td>", city)[2] == "7 December 2026"


# ---- the basket page ----

def _basket_page(pages=frozenset({MILK})) -> str:
    return render_basket(a_public(), BASKET, EXCLUSIONS, BASKET_DAY, "12:03", set(pages))


def test_basket_html_keeps_the_baskets_always_phrases_links_covered_items_only_and_says_formats_differ():
    """Question M (c) and (d) and the amendment: the basket's page with the site's band and credit line, its own ALWAYS
    phrases, an item linked to its product page only when the build has one, the formats sentence under its table, its
    method link to its section of the method page; never ALWAYS_SENTENCE (Task 15's carry), no script."""
    page = _basket_page()
    text = _visible(page)
    for phrase in BASKET_ALWAYS:
        assert flatten(phrase) in text, phrase
    assert f'<a href="{page_path(MILK)}">' in page
    assert f'href="{page_path(PASTA)}"' not in page and f'href="{page_path(EGGS)}"' not in page
    prices = re.search(r'<section><h2 id="prices">.*?</section>', page, re.DOTALL).group(0)
    assert prices.endswith(f"</table></div><p>{formats_note()}</p></section>")
    assert flatten(ALWAYS_SENTENCE) not in text
    assert flatten(CREDIT_START) in text and flatten(date_line(BASKET_DAY)) in text
    assert '<a href="index.html">Five chains, listed prices</a>' in page
    assert f'<a href="method.html#{BASKET_SECTION}">' in page
    assert f"<h1>{BASKET_TITLE}</h1>" in page and "<script" not in page
    assert 'href="p/' not in _basket_page(pages=())


def test_basket_html_links_an_item_whose_code_has_leading_zeros():
    """The final review's finding 12: the build's product pages go by the barcode with its leading zeros stripped, and
    a basket item's code is as the basket file writes it, so the link compares the two stripped."""
    zeros = replace(BASKET, items=tuple(replace(item, code="0" + item.code) for item in BASKET.items))
    public = json.dumps(a_public())
    for item in BASKET.items:                           # the day as the basket's build gives it for those codes
        public = public.replace(f'"{item.code}"', f'"0{item.code}"')
    page = render_basket(json.loads(public), zeros, EXCLUSIONS, BASKET_DAY, "12:03", {MILK})
    assert f'<a href="{page_path(MILK)}">' in page
    assert f'href="{page_path("0" + MILK)}"' not in page and page.count('href="p/') == 1


def test_render_index_without_a_frame_is_unchanged():
    """The basket's own index and method pages, byte for byte as at Task 16's commit (their SHA-256 there)."""
    from test_page import STORES, index, method
    pinned = {"1700a3aa625e52bc4a1cf1e77991bc34c83eb8c174eabceccb4d58f2c757eaf1": index(),
              "6c873ce3a1bb6100a5cbd51e4399e23a70f0027b9d609cd266e3c681b0e391c3": method(),
              "5601fb1eca6bcc60c7c571db4876b69e2a7bf5478f2cfbdfdd82d504aae02fb2": index(a_public(
                  stores={**STORES, "ramilevy": (60, 1), "carrefour": (100, 2), "yochananof": (40, 3)}))}
    for sha, page in pinned.items():
        assert hashlib.sha256(page.encode()).hexdigest() == sha
    assert render_index(a_public(), BASKET, EXCLUSIONS, None) == index()


def test_a_frame_replaces_the_band_credit_and_method_link():
    frame = Frame(band="<header>BAND</header>", credit="CREDIT", item_link=lambda code: None, method_href="M.html",
                  note="NOTE.")
    page = render_index(a_public(), BASKET, EXCLUSIONS, frame)
    assert "<header>BAND</header>" in page and "<p>CREDIT <a href=\"M.html\">" in page
    assert '<header class="band"><div class="wrap"><h1>' not in page
    assert "<p>NOTE.</p></section>" in page


# ---- the basket's build, without its pages ----

def test_write_pages_false_skips_the_pages_and_writes_the_day_file(tmp_path):
    """The second pre-flight's S13: the site run builds the basket's day with `write_pages=False`: no `index.html`,
    `method.html` or marker, the day file written when not unchanged and left as it is when unchanged; the outcome
    carries the day as shown and each chain's stores left out, for basket.html and the method page."""
    data, site = golden_tree(tmp_path), tmp_path / "site"
    outcome = build_at(data, site, NOW, write_pages=False)
    assert not [name for name in ("index.html", "method.html", ".basket-site") if (site / name).exists()]
    assert json.loads(day_file(site).read_text(encoding="utf-8")) == outcome.public
    assert [store.id for store in outcome.exclusions["shufersal"]] == ["413"]
    assert set(outcome.exclusions) == set(CHAIN_NAMES)
    os.utime(day_file(site), ns=(PAST, PAST))
    again = build_at(data, site, LATER, write_pages=False)
    assert again.unchanged and day_file(site).stat().st_mtime_ns == PAST
    assert again.public == outcome.public and again.public["collected_by"] == "14:05"   # as published, not rebuilt
    assert not (site / "index.html").exists()


def test_the_basket_build_still_writes_its_pages_by_default(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    outcome = build_at(data, site, NOW)
    assert all((site / name).exists() for name in ("index.html", "method.html", ".basket-site"))
    assert outcome.public == json.loads(day_file(site).read_text(encoding="utf-8"))

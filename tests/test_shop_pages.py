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
from pathlib import Path

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from basket.chains import CARREFOUR_COLUMNS
from basket.page import Frame, method_parts, render_day, render_index, render_method as basket_method
from basket.stores import Store
from basket.words import ALWAYS as BASKET_ALWAYS, CHAIN_NAMES, METHOD_INTRO, TITLE as BASKET_TITLE, joined
from shopper.columns import BY_KEY, COLUMNS, FLOOR
import shopper.pages as pages_module
from shopper.history import READ_DAYS, ColumnDay
from shopper.pages import (BASKET_PAGE, BASKET_SECTION, CONDITIONS, NO_DEALS, PICK_GROUPS, PICK_TITLE, ROOT_LINE,
                           SCORED_SO_FAR, ColumnsToday, StoreFront, column_ready, render_basket, render_method,
                           render_record, render_root, render_store, scorecard_section, shown_rows, store_path)
from shopper.product import BADGE_STYLE, CHAIN_SPAN, page_path
from shopper.search import browse_pages
from shopper.shell import SCRIPT_TAG
from shopper.items import HORIZON
from shopper.record import scorecard
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS
from shopper.verdict import DEAL_MIN, FRONT_LIMIT, SHADES, DealRow, checked, front_list, on_list, verdict
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, CHAINS_LINE, CREDIT_START, FOLD_INTRO, FRONT_SUBTITLE, FRONT_TITLE,
                           HIRING, NEVER, NO_VERDICT, NONE_YET, SEARCH_LABEL, SITE_NAME, STORE_RULES, columns_tested,
                           date_line, formats_note, headline, how_often, last_low, no_odds_yet, reason, unreadable)
from test_build import NOW, LATER, PAST, build_at, day_file, golden_tree
from test_page import BASKET, EXCLUSIONS, a_public
from test_product import CODE, DAY, SPAN, _days, _listed, _pair, _render, _struct, _typical, back
from test_record_numbers import START, _bins, _day, _good, _part

DEAL, SHELI, EXPRESS, UNIVERSE = "shufersal-deal", "shufersal-sheli", "shufersal-express", "shufersal-universe"
CITY, MARKET, RAMI, OSHER = "carrefour-city", "carrefour-market", "ramilevy", "osherad"
MILK, PASTA, EGGS = (item.code for item in BASKET.items)
BASKET_DAY = date(2026, 11, 2)
SCRIPT = '<script src="search.js" defer></script>'
NEVER_LIST = re.compile(r'<ul id="never-words">(.*?)</ul>', re.DOTALL)
STORE_FIRST = (Path(__file__).parent.parent / "docs" / "store-first.md").read_text(encoding="utf-8")
SEARCH_JS = (Path(__file__).parent.parent / "src" / "shopper" / "static" / "search.js").read_text(encoding="utf-8")


def _visible(page: str) -> str:
    """The page's text as the site check reads it, with every chain span cut out (Call 11)."""
    return flatten(strip_tags(SPAN.sub(" ", page)))


def _no_never_phrase_and_no_pronoun(page: str) -> None:
    """No NEVER phrase as written or as read, outside the method page's list, and no "we", "our" or "us"."""
    cut = NEVER_LIST.sub(" ", SPAN.sub(" ", page))
    for version in (flatten(strip_tags(cut)), flatten(cut)):
        assert not [phrase for phrase in NEVER if flatten(phrase) in version]
    assert not PRONOUNS.search(flatten(strip_tags(cut)))


# ---- the root page, the picker (store first, q33, the plan's Task 5) ----

# The design's order, by chain ("What a visitor sees" 1), never COLUMNS' (by name)
PICK_ORDER = ["shufersal-deal", "shufersal-express", "shufersal-sheli", "shufersal-universe", "carrefour-city",
              "carrefour-market", "ramilevy", "osherad", "yochananof"]
PICK_LINK = '<p class="store"><a id="pick-link" href="{up}index.html#pick">Pick your store</a></p>'


def _root() -> str:
    return render_root(DAY, "12:03")


def _header(page: str) -> str:
    return re.search(r"<header\b.*?</header>", page, re.DOTALL).group(0)


def test_the_root_is_the_picker_grouped_by_chain():
    """The design's "What a visitor sees" 1 and 3: the title question, the line on what the site does, the picker
    ("Which store are you in?", the nine store types grouped by chain, each a link to its front page), and the hiring
    line kept from the old front page; no deal, no table, no search box, and the one script."""
    assert PICK_TITLE == "Which store are you in?"
    assert ROOT_LINE == ("Pick the store you're in, then look up a product: each sale is checked against what it "
                         "usually costs there.")
    assert PICK_GROUPS == (("shufersal", ("shufersal-deal", "shufersal-express", "shufersal-sheli",
                                          "shufersal-universe")),
                           ("carrefour", ("carrefour-city", "carrefour-market")), ("ramilevy", ("ramilevy",)),
                           ("osherad", ("osherad",)), ("yochananof", ("yochananof",)))
    assert [store_path(key) for key in PICK_ORDER] == [f"store/{key}.html" for key in PICK_ORDER]
    page = _root()
    picker = re.search(r'<section id="pick" data-page="root">(.*?)</section>', page, re.DOTALL).group(1)
    assert picker.startswith(f"<h2>{PICK_TITLE}</h2><h3>Shufersal</h3><ul>")
    assert re.findall(r"<h3>([^<]+)</h3>", picker) == ["Shufersal", "Carrefour", "Rami Levy", "Osher Ad", "Yochananof"]
    links = re.findall(r'<li><a href="([^"]+)">([^<]+)</a></li>', picker)
    assert links == [(f"store/{key}.html", BY_KEY[key].name) for key in PICK_ORDER]
    assert sorted(PICK_ORDER) == sorted(column.key for column in COLUMNS)              # each of the nine, once
    assert (f'<h1>{FRONT_TITLE}</h1>\n<p class="lede">{ROOT_LINE}</p>\n<section id="pick" data-page="root">') in page
    assert f"<title>{FRONT_TITLE} - {SITE_NAME}</title>" in page
    hiring = re.search(r'<p class="hiring">(.*?)</p>', page).group(1)
    assert [(label, href) for href, label in re.findall(r'<a href="([^"]+)">([^<]+)</a>', hiring)] == list(HIRING)
    for absent in ("<table", "<tr", 'class="deals"', '<input id="q"', "data-store", "data-column", "<details"):
        assert absent not in page, absent
    assert page.count("<script") == 1 and SCRIPT in page
    footer = re.search(r"<footer>(.*?)</footer>", page, re.DOTALL).group(1)
    assert re.findall(r'<a href="([^"]+)">', footer) == ["basket.html", "record.html", "method.html"]
    _no_never_phrase_and_no_pronoun(page)
    assert _root() == render_root(DAY, "12:03")


# ---- a store type's front page: its deals by saving, the top 100, under a headline (store first, q33) ----

TITLE = "גבינה צהובה 200 גרם"


def _deal_row(column=SHELI, listed="10.00", price="7.00", code=CODE, title=TITLE, first=0, **struct) -> DealRow:
    """A row of `column`'s front list as the build makes it: the product listed at `listed` from `first` days back to
    90 (every day of the 91 by default), today's promotion at `price` a unit, its verdict worked by `shopper.verdict`
    over every column's 91 days. 10.00 against 7.00 is ₪3.00 off, shade deal-2."""
    pair = replace(_pair(column, _listed(listed, first), promotions=[_struct(price, **struct)]), code=code)
    return DealRow(column=column, code=code, title=title, verdict=verdict(pair, column, _days(), DAY))


def _front(column=SHELI, rows=None, checked=None, ready=True, promotions=1840, products=6210) -> StoreFront:
    """A store type's front as the build hands it in: its deals in `front_list`'s order, all of them; `checked` two more
    than the rows by default."""
    rows = [_deal_row(column)] if rows is None else rows
    return StoreFront(column=column, ready=ready, rows=tuple(front_list(rows)),
                      checked=len(rows) + 2 if checked is None else checked, promotions=promotions, products=products)


def _storepage(front=None, days=None, marking=("shufersal",), browse="browse/05d2.html") -> str:
    return render_store(_front() if front is None else front, _days() if days is None else days, DAY, "12:03",
                        marking, browse)


def _lede(page: str) -> str:
    return re.search(r'<p class="lede">(.*?)</p>', page).group(1)


def _table_rows(page: str) -> list[str]:
    """The table's rows: each one's barcode, from its product link."""
    return re.findall(r'<tr data-column="[^"]+"[^>]*><th scope="row"><a href="\.\./p/([^"]+)\.html">', page)


def test_each_store_page_names_its_store_and_puts_search_first():
    """Each of the nine: `<main data-store="<key>">` (search.js sets the pick from it), the store's name in the tab's
    title and over the page's title, then the subtitle, the search box, the headline, the deals and the fold-out, in
    the design's order ("What a visitor sees" 4); no store radios (the page is one store type's)."""
    for column in COLUMNS:
        page = _storepage(_front(column.key, rows=[]))
        assert f'<main data-store="{column.key}">' in page and page.count("data-store") == 1
        assert f"<title>{column.name} - {SITE_NAME}</title>" in page
        main = page[page.index("<main"):]
        assert main.startswith(f'<main data-store="{column.key}">\n<p class="at">{column.name}</p>\n'
                               f'<h1 id="deals">{FRONT_TITLE}</h1>\n<p class="sub">{FRONT_SUBTITLE}</p>\n'
                               '<section class="search">')
        assert main.index('<section class="search">') < main.index('<p class="lede">') < main.index(
            '<section class="deals">') < main.index("<details>")
        assert 'type="radio"' not in page and "f-all" not in page
    assert store_path(SHELI) == "store/shufersal-sheli.html"


def test_a_store_page_has_the_always_phrases_and_the_search_box():
    """The design's "Words": the four ALWAYS phrases on a store page, with or without a row, on a hole or a promotion
    hole too (the site check holds every store page to them), from the fold-out's note; the search box,
    `<input id="q">`, labelled in the design's words, with its browse link from the site's root; `noindex`, the date
    line and the credit line (the shared shell)."""
    holes = (_days(holes={(SHELI, DAY)}), _days(promo_holes={(SHELI, DAY)}))
    pages = [_storepage(), _storepage(_front(rows=[])), _storepage(_front(rows=[], checked=0, ready=False)),
             *(_storepage(days=days) for days in holes)]
    assert SEARCH_LABEL == "Type a product name or the barcode" and f'the search box ("{SEARCH_LABEL}")' in STORE_FIRST
    for page in pages:
        text = _visible(page)
        for phrase in ALWAYS:
            assert flatten(phrase) in text, phrase
        assert page.count("<script") == 1 and page.count(SCRIPT_TAG.format(up="../")) == 1
        assert ('<section class="search"><label for="q">Type a product name or the barcode</label>'
                '<input id="q" type="search" autocomplete="off"><p><a href="../browse/05d2.html">Browse by first letter'
                '</a></p></section>') in page
        assert '<meta name="robots" content="noindex">' in page
        assert flatten(date_line(DAY)) in text and flatten(CREDIT_START) in text and "not shopping advice." in text
        _no_never_phrase_and_no_pronoun(page)
    # the owner's plain words (2026-11-10): the empty table repeats nothing of the lead line above it
    assert '<td colspan="4">No deals to show.</td>' in _storepage(_front(rows=[])) and NO_DEALS not in _storepage()
    assert '<input id="q" type="search" autocomplete="off"></section>' in _storepage(browse=None)


def test_every_page_header_names_the_site_the_chains_and_the_day():
    """The owner's plain words (2026-11-10): the site's name, the pick link (store first, q33), the five chains in slug
    order on one line, and the date line, "Prices of" the day."""
    for page, up in ((_storepage(), "../"), (_root(), "")):
        assert (f'<header class="band"><div class="wrap"><a href="{up}index.html">Deal or No Deal</a>'
                f'{PICK_LINK.format(up=up)}'
                '<p class="dateline">Shufersal · Rami Levy · Osher Ad · Carrefour · Yochananof</p>'
                '<p class="dateline">Prices of Friday 20 November 2026</p></div></header>') in page


def test_a_store_types_list_is_its_deals_passing_the_bar_by_saving():
    """Goal 6 and "The front page's list": a product is listed when its verdict there is Deal and it has 20 days with
    records in the 30 before today; by the saving, largest first, then by barcode as a number (200 before 1000); a no
    deal and a deal under the bar are not listed, and the headline's M counts the no deal, not the one under the bar.
    The rows are made as the build makes them (`on_list`, `checked`, `front_list`) and the page shows them as given."""
    made = {"1000": (_listed(), "8.50"), "300": (_listed(), "7.00"), "400": (_listed(), "9.50"),
            "500": (_listed("10.00", 0, 19), "5.00"), "200": (_listed(), "8.50")}
    rows, checked_ = [], 0           # 1.50, 3.00, 0.50 (no deal), 5.00 over 19 days with records in the 30, 1.50
    for code, (listed, price) in made.items():
        pair = replace(_pair(SHELI, listed, promotions=[_struct(price)]), code=code)
        found = verdict(pair, SHELI, _days(), DAY)
        rows += [DealRow(SHELI, code, "T", found)] if on_list(found, pair, _days(), DAY) else []
        checked_ += checked(found, pair, _days(), DAY)
    assert {row.code: row.verdict.call for row in rows} == {"1000": "deal", "300": "deal", "200": "deal"}
    page = _storepage(StoreFront(SHELI, True, tuple(front_list(rows)), checked_, 4, 5))
    assert _table_rows(page) == ["300", "200", "1000"]
    assert _lede(page) == "At Shufersal Sheli today: 3 of 4 promotions are actually deals."
    badges = re.findall(r'<span class="badge ([^"]+)">([^<]+)</span>', page)
    assert badges == [("deal-2", "At Shufersal Sheli: DEAL · ₪3.00 off"), ("deal-1", "At Shufersal Sheli: DEAL · ₪1.50 off"),
                      ("deal-1", "At Shufersal Sheli: DEAL · ₪1.50 off")]


def test_the_list_shows_the_top_100():
    """The design's "top 100 shown, the rest reached through search and browse": 101 deals give 100 rows, the 101st
    left out, and the headline counts all 101, the same set as the list (FRONT_LIMIT)."""
    assert FRONT_LIMIT == 100
    rows = [_deal_row(code=str(1000 + n)) for n in range(101)]
    page = _storepage(_front(rows=rows, checked=120))
    shown = _table_rows(page)
    assert shown == [str(1000 + n) for n in range(100)] and "1100" not in shown
    assert _lede(page) == "At Shufersal Sheli today: 101 of 120 promotions are actually deals."
    assert shown_rows(_front(rows=rows), _days()[(SHELI, DAY)]) == _front(rows=rows).rows[:100]


def test_the_headline_counts_the_same_set():
    """The headline under the search box: N, the rows of the list, all of them, and M, the products with a promotion
    that counts today passing the 20-day bar (`checked`), as the build hands them in; the design's example, a singular
    verb for one deal, and "no promotions to check" with M of none."""
    two = [_deal_row(code="1"), _deal_row(code="2", price="8.00")]
    assert _lede(_storepage(_front(rows=two, checked=5))) == headline(SHELI, 2, 5) == (
        "At Shufersal Sheli today: 2 of 5 promotions are actually deals.")
    assert _lede(_storepage(_front(rows=two[:1], checked=3))) == "At Shufersal Sheli today: 1 of 3 promotions is actually a deal."
    assert _lede(_storepage(_front(rows=[], checked=2))) == "At Shufersal Sheli today: 0 of 2 promotions are actually deals."
    assert _lede(_storepage(_front(rows=[], checked=0))) == "At Shufersal Sheli today: no promotions to check."
    assert _lede(_storepage(_front(MARKET, rows=[], checked=0))).startswith("At Carrefour Market today: ")


def test_none_yet_until_the_store_type_has_20_days():
    """"Until any product passes, the existing lead line stays": while the store type has no record on 20 of the 30
    days before today (`column_ready`), no product can pass the bar, and the headline gives way to "None yet"."""
    assert _lede(_storepage(_front(rows=[], checked=0, ready=False))) == (
        "None yet: a product needs 20 days of price history first.")
    assert _lede(_storepage(_front(rows=[], checked=3, ready=False))) == NONE_YET
    assert _lede(_storepage(_front(rows=[], checked=0, ready=True))) != NONE_YET


def test_a_store_type_is_ready_once_it_has_20_days_of_records_in_the_30():
    """The store page's "None yet" (the owner, 2026-11-10), for one store type: a product's days of records at a
    column are days the column has one (P6), so until the column has a record on 20 of the 30 days before today none
    of its products can pass the front list's bar (`shopper.verdict.passes_bar`). A hole, a day the chain's table is
    missing, a day 31 back, today and another column's days count nothing."""
    def of(column, backs, days=None):
        days = _days() if days is None else days
        return {(column, back(n)): days[(column, back(n))] for n in backs}

    assert column_ready(_days(), DEAL, DAY) and not column_ready({}, DEAL, DAY)
    assert column_ready(of(DEAL, range(1, 21)), DEAL, DAY)                            # 20 of the 30
    assert column_ready(of(DEAL, [*range(1, 20), 30]), DEAL, DAY)                     # 30 back is in the 30
    assert not column_ready(of(DEAL, range(1, 20)), DEAL, DAY)                        # 19
    assert not column_ready(of(DEAL, range(0, 20)), DEAL, DAY)                        # today is not before today
    assert not column_ready(of(DEAL, [*range(1, 20), 31]), DEAL, DAY)                 # 31 back is not in the 30
    both = {**of(DEAL, range(1, 20)), **of(SHELI, range(1, 21))}
    assert not column_ready(both, DEAL, DAY) and column_ready(both, SHELI, DAY)       # never another column's days
    assert not column_ready(of(DEAL, range(1, 21), _days(holes={(DEAL, back(5))})), DEAL, DAY)
    missing = of(DEAL, range(1, 21))
    missing[(DEAL, back(5))] = replace(missing[(DEAL, back(5))], present=False)
    assert not column_ready(missing, DEAL, DAY)



def test_a_store_type_not_read_today_says_so_and_lists_none():
    """Review Focus 2: on a promotion hole (Shufersal Deal on 2026-11-08) the page says "Sale prices could not be read
    today." and lists no deal; on a hole (prices from too few files) it says the too-few line and lists none; a hole
    first, then the promotion hole, then "None yet". Another store type's hole lists this one's deals as ever."""
    promo_hole = _storepage(days=_days(promo_holes={(SHELI, DAY)}))
    hole = _storepage(days=_days(holes={(SHELI, DAY)}))
    for page in (promo_hole, hole):
        assert _table_rows(page) == [] and "No deals to show." in page and "One of today's deals" not in page
    assert _lede(promo_hole) == "Sale prices could not be read today."
    assert _lede(hole) == "too few files today: 5 of 20 stores"
    both = _days(holes={(SHELI, DAY)}, promo_holes={(SHELI, DAY)})
    assert _lede(_storepage(days=both)) == _lede(hole)
    assert _lede(_storepage(_front(ready=False), days=_days(promo_holes={(SHELI, DAY)}))) == _lede(promo_hole)
    other = _storepage(days=_days(holes={(DEAL, DAY)}, promo_holes={(DEAL, DAY)}))
    assert _table_rows(other) == [CODE] and _lede(other).startswith("At Shufersal Sheli today: 1 of 3 ")


def test_a_row_shows_the_badge_its_condition_todays_price_and_the_usual_price():
    """The design's list: the product (its link, its name in the chain's span, its barcode), the deal badge with its
    shade and the condition beside it when there is one, today's price and the usual price, each as shown; a weighed
    product's a kilogram's. "2 for ₪7.00" for club members, against 6.50 every day: ₪3.50 a unit, ₪3.00 off."""
    heads = "".join(f'<th scope="col">{head}</th>' for head in ("Product", "Deal", "Price today", "Usually"))
    two = _deal_row(listed="6.50", price=Fraction(7, 2), kind="n_for_m", buy="2", restrictions=["club"])
    page = _storepage(_front(rows=[two]))
    assert f"<thead><tr>{heads}</tr></thead>" in page
    row = re.search(r"<tr data-column[^>]*>(.*?)</tr>", page).group(1)
    assert row == (f'<th scope="row"><a href="../{page_path(CODE)}">{CHAIN_SPAN.format(TITLE)}</a><small>{CODE}</small>'
                   '</th><td><span class="badge deal-2">At Shufersal Sheli: DEAL · ₪3.00 off</span>'
                   "<small>Club members only; When you buy 2</small></td><td>₪3.50</td><td>₪6.50</td>")
    kg = _deal_row(RAMI, listed="69.90", price="50.00", per="kg", buy="1.5", kind="n_for_m")
    cells = re.search(r"<tr data-column[^>]*>(.*?)</tr>", _storepage(_front(RAMI, rows=[kg]))).group(1)
    assert ('<span class="badge deal-3">At Rami Levy: DEAL · ₪19.90 off a kilogram</span><small>When you buy 1.5 '
            "kilograms</small></td><td>₪50.00 a kilogram</td><td>₪69.90 a kilogram</td>") in cells
    plain = re.search(r"<tr data-column[^>]*>(.*?)</tr>", _storepage()).group(1)
    assert '<span class="badge deal-2">At Shufersal Sheli: DEAL · ₪3.00 off</span></td>' in plain     # no condition
    assert BADGE_STYLE in page


def test_the_filters_need_no_script():
    """The club-only and minimum-spend checkboxes, each ruled by CSS alone (`:checked` and the sibling combinator); a
    row carries what the filters read from the promotion its verdict judges (`data-club` for any restriction,
    `data-spend` for a minimum spend). No store radio: the page is one store type's. The labels are the owner's plain
    words (2026-11-10); their caveats are the fold-out's."""
    restricted = _deal_row(DEAL, code="1", restrictions=["chain_card"])
    spend = _deal_row(DEAL, code="2", price="8.00", min_spend="200")
    page = _storepage(_front(DEAL, rows=[restricted, spend, _deal_row(DEAL, code="3", price="9.00")]))
    assert ('<section class="deals"><input type="checkbox" id="f-club"><label for="f-club">Hide club-only deals</label>'
            '<input type="checkbox" id="f-spend"><label for="f-spend">Hide deals with a minimum spend</label>'
            '<div class="table"') in page
    assert "#f-club:checked ~ .table tbody tr[data-club] { display: none; }" in page
    assert "#f-spend:checked ~ .table tbody tr[data-spend] { display: none; }" in page
    assert 'type="radio"' not in page and not re.search(r"#f-(?!club|spend)", page)
    assert re.findall(r"<tr data-column=\"shufersal-deal\"( [^>]*)?>", page) == [' data-club=""', ' data-spend=""', ""]


def test_the_fold_out_says_how_a_deal_passes_for_that_store_type():
    """The fold-out "How a deal passes", closed (no `open`, no script), in the design's order: its first line, the
    design's verbatim; the rules in shopper words; what the two filters hide, with the store's own chain when its files
    mark no restricted promotion today (never another chain); one deal's story; the store type's promotions line;
    the note carrying the four ALWAYS phrases; the method page, from the site's root."""
    assert FOLD_INTRO == "Promotions checked against what the product usually costs, sales included, over up to 3 months."
    assert f'"How a deal passes": "{FOLD_INTRO}"' in STORE_FIRST
    page = _storepage(marking=("shufersal", "osherad"))
    fold, = re.findall(r"<details>(.*?)</details>", page, re.DOTALL)
    assert "<details open" not in page and page.count("<details") == 1
    rules = "".join(f"<li>{rule}</li>" for rule in STORE_RULES)
    story = re.search(r"<h3>One of today's deals</h3>.*?(?=<p>Today Shufersal Sheli lists)", fold).group(0)
    assert fold == (
        f"<summary>How a deal passes</summary><p>{FOLD_INTRO}</p><ul>{rules}</ul>"
        "<p>\"Hide club-only deals\" hides the deals the chains' fields mark for club members, the chain's card holders "
        "or some customers only. Today Shufersal's files mark no deal this way.</p>"
        "<p>\"Hide deals with a minimum spend\" hides the deals whose fields give a minimum spend.</p>"
        f"{story}"
        "<p>Today Shufersal Sheli lists 1,840 promotions carried by at least half its stores, on 6,210 products.</p>"
        f'<p class="note">{ALWAYS_SENTENCE}</p>'
        '<p><a href="../method.html">All the rules: How this is made</a></p>')
    assert all(flatten(phrase) in _visible(f'<p class="note">{ALWAYS_SENTENCE}</p>') for phrase in ALWAYS)
    osher = _storepage(_front(OSHER, rows=[]), marking=("shufersal", "osherad"))
    assert "Today Osher Ad's files mark no deal this way." in osher and "Shufersal's files" not in osher
    assert "mark no deal" not in _storepage(marking=("osherad",)) and "mark no deal" not in _storepage(marking=())
    assert "One of today's deals" not in _storepage(_front(rows=[]))


def test_the_story_is_the_top_rows_verdict():
    """One of today's deals, in the product page's words: the top row's product, from the site's root, its badge in
    its shade, its reason, last this low and how often."""
    top, second = _deal_row(code="2", price="7.00"), _deal_row(code="1", price="8.50")
    page = _storepage(_front(rows=[second, top]))
    found = top.verdict
    said = "".join(f"<p>{line}</p>" for line in (reason(found), last_low(found), how_often(found)))
    assert (f"<h3>One of today's deals</h3><p class=\"story-head\"><a href=\"../{page_path('2')}\">"
            f'{CHAIN_SPAN.format(TITLE)}</a></p><p class="badge deal-2">At Shufersal Sheli: DEAL · ₪3.00 off</p>'
            f"{said}") in page
    assert said == ("<p>Usually ₪10.00, sales included (90 days tracked).</p><p>Lowest in the 90 days tracked.</p>"
                    "<p>On sale on 0 of the 90 days tracked.</p>")


def test_a_store_pages_links_lead_up_to_the_root():
    """The footer reaches the basket, the record and the method pages, and the browse pages when there are any, each
    from the site's root; the hiring line is the root's alone."""
    page = _storepage()
    footer = re.search(r"<footer>(.*?)</footer>", page, re.DOTALL).group(1)
    assert re.findall(r'<a href="([^"]+)">', footer) == ["../browse/05d2.html", "../basket.html", "../record.html",
                                                          "../method.html"]
    assert 'href="browse/' not in _storepage(browse=None) and 'href="../browse/' not in _storepage(browse=None)
    assert '<p class="hiring">' not in page


def test_the_store_page_is_the_same_bytes_whatever_the_rows_order():
    """A pure function of its inputs: the rows come in `front_list`'s order whatever order they were made in, and the
    column-days and the chains marking none in any order give the same bytes."""
    rows = [_deal_row(code="1", price="8.50"), _deal_row(code="2"), _deal_row(code="3", price="8.50")]
    page = _storepage(_front(rows=rows), marking=("shufersal", "osherad"))
    assert page == _storepage(_front(rows=list(reversed(rows))), marking=("osherad", "shufersal"))
    assert page == _storepage(_front(rows=rows), days=dict(reversed(list(_days().items()))), marking=("osherad", "shufersal"))


# ---- every page: the header and the one script (store first, q33) ----

def _every_page() -> list[tuple[str, str]]:
    """One page of each kind with its way up to the site's root: the root, a store page, the method, record and basket
    pages, a product page and a browse page."""
    covered, pairs = _typical()
    browse = browse_pages({CODE: covered}, DAY, "12:03")
    return [(_root(), ""), (_storepage(), "../"), (_method(), ""), (_record(), ""), (_basket_page(), ""),
            (_render(covered, pairs), "../"), (next(iter(browse.values())), "../")]


def test_every_page_carries_the_one_script_at_its_depth():
    """Q2's one script (store-first.md): `search.js` in every page's head, at the page's own depth ("../" for p/,
    browse/ and store/ pages), and no other."""
    for page, up in _every_page():
        assert page.count("<script") == 1, up
        assert f"</style>\n{SCRIPT_TAG.format(up=up)}\n</head>" in page, up


def test_the_header_says_pick_your_store_before_a_pick():
    """The design's header before a pick, on every page, store pages included (the controller's ruling: search.js
    names the remembered pick); its pick link leads up to the picker, `#pick` on the root, whose section is the
    script's (`data-page="root"`); no page but a product page has the badge row, which the script arranges."""
    for page, up in _every_page():
        header = _header(page)
        assert PICK_LINK.format(up=up) in header and header.count("<a ") == 2, up
        assert "store/" not in header and "change" not in header
    assert '<section id="pick" data-page="root">' in _root()
    for page, _ in _every_page()[:5]:
        assert '<nav class="badges">' not in page and "<nav" not in page


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


def _rules_of(page: str) -> str:
    return re.search(r'<section id="rules">(.*?)</section>', page, re.DOTALL).group(1)


def _rule(rules: str, name: str) -> str:
    """One rule's words on the method page, found by the start of its name ("S4 ")."""
    return re.search(rf"<li><b>{re.escape(name)}[^<]*</b> <span>(.*?)</span></li>", rules, re.DOTALL).group(1)


def _bands(shades) -> list[str]:
    """S5's bands as the method page states them, from SHADES' floors: "₪1.00 to ₪2.99", …, "₪5.00 or more"."""
    floors = sorted(floor for floor, _ in shades)
    return ([f"₪{low} to ₪{high - Decimal('0.01')}" for low, high in zip(floors, floors[1:])]
            + [f"₪{floors[-1]} or more"])


def test_the_method_page_states_the_rules_with_the_codes_constants(monkeypatch):
    """P1 to P6, P10, S0 to S8, the front page's list, the pick and F1 to F11 in plain words, with the constants the
    code fixes (n0, the seed, the block, the draws). Store first (q33): S0 to S8 and the front page's list replace P7,
    P8 and P9, each figure from the code's own constant, so a changed constant changes the page (DEAL_MIN, SHADES,
    READ_DAYS, MIN_FRONT_DAYS, RECENT_DAYS, FRONT_LIMIT); S2's even count the higher middle; "listed price" with its
    definition; the pick kept in the browser under search.js's one key and sent nowhere."""
    page = _method()
    rules = _rules_of(page)
    names = [f"P{n}" for n in (1, 2, 3, 4, 5, 6, 10)] + [f"S{n}" for n in range(9)] + [f"F{n}" for n in range(1, 12)]
    assert re.findall(r"<b>([PSF]\d+) ", rules) == names                    # in this order: P7, P8 and P9 are gone
    assert not [gone for gone in ("P7", "P8", "P9") if gone in page]       # nor named anywhere on the page
    assert "<b>The front page's list.</b>" in rules and "<b>The store you pick.</b>" in rules
    for figure in ("n0 = 30", "blocks of 14 consecutive scored days", "10,000 draws", "seed 20261107",
                   "at least 90 scored days", "at most 0.03", "more than 4 holes", "d + 1 to d + 14"):
        assert figure in rules, figure
    assert unreadable("carrefour") in rules and no_odds_yet(DEAL).split(".")[0] in rules
    # "listed price" with its definition (store-first.md, "Words"), and the chart's name for it
    assert _rule(rules, "P2 ").startswith("A column's listed price for a product on a day is its price as listed in "
                                          "the chain's price files, before promotions: the median of the product's "
                                          "price across the column's included stores")
    assert "The price chart calls it the shelf price." in _rule(rules, "P2 ")
    assert ('no listed price is claimed, every promotion that day is shown "at some stores", with no verdict (S4), no '
            "promotion is said to be listed to start, and the day counts in no window, front page or "
            "forecast.") in rules                                                                   # deploy prep
    # P6 as built: the windows' days, and every count a page gives over them out of its days (S8)
    assert ("The front page's list counts such days in the past 30; the verdict counts its days tracked (S0) in the "
            "past 90, and every count a page gives over them says how many days it is out of (S8).") in rules
    assert "of the N days" not in rules and "days of records since" not in rules
    assert "{" not in rules and "}" not in rules                    # every constant written in, none left as a name
    assert "rebuilt every morning, which says when it was last seen listed across each column" in rules   # deploy prep
    # the rules as built (`shopper.verdict`'s docstring), each figure from its constant
    s2, s4, s5 = (_rule(rules, f"S{n} ") for n in (2, 4, 5))
    assert "with an even number of days, the higher of the two middle values," in s2 and f"{READ_DAYS} days" in s2
    assert "the lower of the two middle values" not in rules
    assert f"is ₪{DEAL_MIN} or more, worked on the figures as shown" in s4
    assert all(NO_VERDICT[call] in s4 for call in NO_VERDICT)
    assert f"one for each band: {joined(_bands(SHADES))};" in s5 and "₪1.00 to ₪2.99" in s5
    front = _rule(rules, "The front page's list.")
    assert f"on at least {MIN_FRONT_DAYS} of the {RECENT_DAYS} days before the page's day" in front
    assert "20 of the 30 days" in front and f"the top {FRONT_LIMIT} are shown" in front
    assert "sorted by the saving as shown, largest first, then by barcode as a number;" in front
    assert NONE_YET in front
    assert "(S7)" in _rule(rules, "F4 ") and "the verdict and the measured history (S4 to S8)" in _rule(rules, "F10 ")
    # the pick: kept in the browser under search.js's one key, sent nowhere
    pick = _rule(rules, "The store you pick.")
    key = re.search(r'const PICK_KEY = "([^"]+)";', SEARCH_JS).group(1)
    assert f'kept in this browser\'s local storage, under the one key "{key}", and sent nowhere' in pick
    assert f'"{PICK_TITLE}"' in pick and "nine" in pick
    _no_never_phrase_and_no_pronoun(page)
    assert "0123456789ab" in page and 'href="site-days/2026-11-02.json"' in page
    reproduce = re.search(r'<section id="reproduce">(.*?)</section>', page, re.DOTALL).group(1)
    assert "the same numbers on every page, the record's intervals to rounding (F8)." in reproduce    # review, 4
    # deploy prep: true on any day, past the archive's 91st day too: which products have a page, their names and sizes,
    # and when each was last seen listed across a column come from the covered registry, carried from day to day
    # the owner's words (2026-11-10): the archive holds no day before the collection's first; the record carried from
    # day to day is said without the code each day was built by (the owner, the same day's second read)
    assert ("Take each chain's full price and promotion files and its store list of every day from 90 days before "
            "this site's first day to the day (this site has none from before 1 November 2026, when its collection "
            "began, and reads such a day as one without records), as the chains published them,") in reproduce
    assert ("A page's measures read the day and the 90 days before it; which products have a page, their names and "
            "sizes, and when each was last seen listed across a column come from a record carried from day to day "
            "since the site's first. The day's inputs are named in") in reproduce
    assert "built by the code" not in reproduce
    # a changed constant changes the page
    for name, value in (("DEAL_MIN", Decimal("2.50")), ("READ_DAYS", 60), ("MIN_FRONT_DAYS", 15), ("RECENT_DAYS", 21),
                        ("FRONT_LIMIT", 40), ("SHADES", ((Decimal("8.00"), "deal-3"), (Decimal("4.50"), "deal-2"),
                                                         (Decimal("2.50"), "deal-1")))):
        monkeypatch.setattr(pages_module, name, value)
    changed = _rules_of(_method())
    s2, s4, s5 = (_rule(changed, f"S{n} ") for n in (2, 4, 5))
    assert "60 days" in s2 and "90 days" not in s2
    assert "is ₪2.50 or more" in s4 and "₪1.00" not in s4
    assert "₪2.50 to ₪4.49, ₪4.50 to ₪7.99 and ₪8.00 or more" in s5 and "₪1.00" not in s5
    front = _rule(changed, "The front page's list.")
    assert "on at least 15 of the 21 days" in front and "the top 40 are shown" in front
    assert "20 of the 30" not in front


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
    # closed day to learn from: shopper.forecast), and as F2 says; and that a column's forecasts are frozen on the days
    # F2 gives it forecasts, not every day: a hole for the column, or a day its promotions were not read, gives none
    assert ("From a column's 30th day of records, once it has a closed day to learn from, this site freezes that "
            "column's forecasts on each day the rules allow (F2), before their outcomes are known, and scores them 14 "
            "days later against two rules of thumb (F5).") in page
    for column in COLUMNS:
        section = re.search(rf'<section data-column="{column.key}">(.*?)</section>', page, re.DOTALL).group(1)
        assert "Gate: closed." in section
        assert section.count("does not hold") == 3
        assert "0 scored days of the version in force (model 1, target 1) frozen on time; 90 needed" in section
    assert "Promotion fine print is not read yet." in page
    assert "Model versions scored so far: 0" in page
    assert "seed 20261107" in page and "10,000 draws" in page and "blocks of 14 scored days" in page
    assert flatten(CREDIT_START) in text and flatten(date_line(RECORD_DAY)) in text and page.count("<script") == 1
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
    method link to its section of the method page; never ALWAYS_SENTENCE (Task 15's carry); the site's one script
    (store first, q33) and no other."""
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
    assert (f'<a href="index.html">Deal or No Deal</a>{PICK_LINK.format(up="")}<p class="dateline">{CHAINS_LINE}</p>'
            in page)
    assert f'<a href="method.html#{BASKET_SECTION}">' in page
    assert f"<h1>{BASKET_TITLE}</h1>" in page and page.count("<script") == 1
    assert f'</style>\n{SCRIPT}\n</head>' in page
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

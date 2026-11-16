"""The product pages (`shopper.product`; the plan's Task 16, then store first, q33: docs/store-first.md, "What a visitor
sees" 5 to 8, "The chart", "Words" and "Testing"; the store-first plan's Task 3; then the site's look, q36:
docs/site-look.md, "The label", "A product page", "The barcode", and the site-look plan's Task 8): the badge row, a
section per store type (a column) with its verdict as a shelf label (the reason, the conditions, a coming sale, and the
price part with today's price and the product's barcode), its chart, last this low, how often and the fold-out "How
this is worked out", on the shared shell (`shopper.shell`), which links the site's one stylesheet (`shopper.assets`; its
rules are tests/test_look.py's). Pairs, points and column-days are built by hand, as tests/test_measures.py builds them;
names, barcodes and programmes are synthetic. Each page's verdicts are worked by `shopper.verdict`, as the
build works them."""
import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from html import unescape

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from basket.record import money
from basket.words import too_few
from shopper import product, shell, words
from shopper.assets import STYLESHEET
from shopper.bars import drawing, mark
from shopper.chart import render_chart
from shopper.columns import BY_KEY, COLUMNS
from shopper.deals import to_agora
from shopper.history import ColumnDay, Covered, Pair, Point
from shopper.product import CHAIN_SPAN, MAX_PAGE, page_path, render_product
from shopper.record import Gate
from shopper.search import browse_pages, browse_path
from shopper.verdict import verdict
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, AT_SOME_STORES, CHAINS_LINE, FINE_PRINT, FROM_FIELDS, MORNING,
                           NEVER, ODDS_WORDS, PRICE_NOT_READ, SITE_NAME, credit, date_line, last_across,
                           no_odds_yet, unreadable)

DAY = date(2026, 11, 20)
CODE = "2000000000046"
DEAL, SHELI, CITY, MARKET, RAMI = "shufersal-deal", "shufersal-sheli", "carrefour-city", "carrefour-market", "ramilevy"
OSHER, YOCHANANOF = "osherad", "yochananof"
STORES = 20
SPAN = re.compile(r'<span class="as-listed" lang="he" dir="rtl">.*?</span>', re.DOTALL)
SECTION = re.compile(r'<section data-column="([^"]+)" id="c-([^"]+)" data-chain="([^"]+)">(.*?)</section>', re.DOTALL)
FOLD = re.compile(r"<details><summary>([^<]*)</summary>(.*?)</details>", re.DOTALL)
NAV = re.compile(r'<nav class="badges">(.*?)</nav>', re.DOTALL)
BADGE = re.compile(r'<a data-column="([^"]+)" href="#c-([^"]+)" class="badge ([^"]+)">(.*?)</a>')
TAG = re.compile(r'<div class="tag ([^"]+)"><div class="say">(.*?)</div>(?:<div class="pay">(.*?)</div>)?</div>'
                 r'(?=<div class="history">|<p class="fact">|<details>)', re.DOTALL)
NO_BARS = "12345678901"          # 11 digits: no barcode can be drawn (Review Focus 1)


def back(days: int) -> date:
    return DAY - timedelta(days=days)


def _days(holes=(), promo_holes=()) -> dict[tuple[str, date], ColumnDay]:
    """Every column's 91 days read, d - 90 to d; a hole at 5 of its 20 stores with a file."""
    found = {}
    for column in COLUMNS:
        for n in range(91):
            day = back(n)
            hole = (column.key, day) in holes
            found[(column.key, day)] = ColumnDay(
                column=column.key, slug=column.slug, day=day, present=True, hole=hole,
                promo_hole=(column.key, day) in promo_holes, promotions_error=None, included=STORES,
                with_file=5 if hole else STORES, counted=5 if hole else STORES, promo_files=STORES)
    return found


def _struct(price="7.90", *, kind="fixed_price", per="unit", buy="1", low=None, high=None, valid=True, why=None,
            restrictions=(), programmes=(), min_spend=None, stores=STORES, wide=True, start=None, end=None,
            promotion_id="1") -> dict:
    """A promotion on the item as the items table's struct holds it, read back from DuckDB (Task 6)."""
    exact = None if price is None else Fraction(price)
    return {"promotion_id": promotion_id, "description": "PLACEHOLDER-DESCRIPTION", "start": start or back(3),
            "end": end or DAY + timedelta(days=5), "kind": kind, "buy": Decimal(buy),
            "price": None if exact is None else to_agora(exact), "price_exact": None if exact is None else str(exact),
            "per": per, "low": None if low is None else Decimal(low), "high": None if high is None else Decimal(high),
            "valid": valid, "why": why, "restrictions": list(restrictions), "programmes": list(programmes),
            "min_spend": None if min_spend is None else Decimal(min_spend), "stores": stores, "wide": wide}


def _sale(price: str, day: date, promotion_id="90") -> dict:
    """A promotion that counts on `day` alone (a day of a past sale with its price read)."""
    return _struct(price, start=day, end=day, promotion_id=promotion_id)


def _listed(price="10.00", first=0, last=90) -> dict[date, str]:
    """`price` on each day from `first` to `last` days back, inclusive (0 is the page's day)."""
    return {back(n): price for n in range(first, last + 1)}


def _pair(column: str, listed: dict[date, str], *, on=(), promotions=(), next_start=None, wide=True,
          sales=None) -> Pair:
    """A pair listing `listed`; on promotion on the `on` days; today's promotions `promotions`, and each earlier day's
    those `sales` gives it."""
    points = {}
    for day, price in listed.items():
        today = day == DAY
        points[day] = Point(day=day, listed=Decimal(price), low=Decimal(price), high=Decimal(price) + 1,
                            listing=STORES - 2, wide=wide or not today, on_promotion=day in on,
                            next_start=next_start if today else None,
                            promotions=tuple(promotions) if today else tuple((sales or {}).get(day, ())))
    return Pair(column=column, code=CODE, points=points)


def _covered(names: dict[str, str], size=None, last_wide=None, code=CODE) -> Covered:
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=size, first_covered=back(80),
                   last_wide={column: DAY for column in names} if last_wide is None else last_wide)


def _verdicts(pairs, column_days) -> dict:
    """Every column's verdict on the page's day, as the build works each section's."""
    return {column.key: verdict(pairs.get(column.key), column.key, column_days, DAY) for column in COLUMNS}


def _render(covered, pairs, column_days=None, gates=None, errors=None) -> str:
    days = _days() if column_days is None else column_days
    return render_product(covered, pairs, _verdicts(pairs, days), days, DAY, "12:03", gates or {}, errors or {})


def _sections(page: str) -> dict[str, str]:
    found = {}
    for column, key, _, body in SECTION.findall(page):
        assert key == column
        found[column] = body
    return found


def _fold(body: str) -> str:
    """A section's fold-out: what its <details> holds after its summary."""
    (summary, inside), = FOLD.findall(body)
    assert summary == words.WORKED_OUT
    return inside


def _visible(page: str) -> str:
    """The page's text as the site check reads it, with every chain span cut out (Call 11)."""
    return flatten(strip_tags(SPAN.sub(" ", page)))


def _read(markup: str) -> str:
    """Markup as a reader reads it: its tags removed, nothing put in their place, its entities read."""
    return unescape(re.sub(r"<[^>]*>", "", markup))


def _paragraphs(body: str) -> list[str]:
    """A section's paragraphs as read (`_read`)."""
    return [_read(said) for said in re.findall(r"<p(?: class=\"[^\"]*\")?>(.*?)</p>", body)]


def _label(body: str) -> tuple[str, str, str | None]:
    """A section's shelf label: its class, its saying part and its price part (None when it has none)."""
    (shade, say, pay), = TAG.findall(body)
    return shade, say, (pay if '<div class="pay">' in body else None)


def _history(body: str) -> str:
    """A section's chart, its key and its table: from `<div class="history">` to the facts or the fold-out."""
    start = body.find('<div class="history">')
    if start < 0:
        return ""
    ends = (body.find('<p class="fact">', start), body.find("<details>", start))
    return body[start:min(at for at in ends if at >= 0)]


def _typical() -> tuple[Covered, dict[str, Pair]]:
    """Two columns listing it, one promotion (at Deal, 7.90 a unit, for club members): Deal on sale 40 to 45 days back
    with its sale price not read, so 84 of its 90 tracked days have a day price; Rami Levy with no sale."""
    deal = _struct("7.90", restrictions=["club"])
    listed = {**_listed("10.90", 31, 90), **_listed("11.90", 0, 30)}
    pairs = {DEAL: _pair(DEAL, listed, on=[back(n) for n in range(40, 46)], promotions=[deal]),
             RAMI: _pair(RAMI, _listed("11.50"))}
    return _covered({DEAL: "גבינה צהובה 200 גרם", RAMI: "גבינה צהובה פרוסה 200 גרם"}, size=(Decimal(200), "gml")), pairs


def _one(price="6.00", *structs, column=DEAL, **more) -> tuple[Covered, dict[str, Pair]]:
    """One column listing it at `price` every day of the 91, today's promotions `structs`."""
    return _covered({column: "שם"}), {column: _pair(column, _listed(price), promotions=structs, **more)}


def _largest() -> tuple[Covered, dict[str, Pair]]:
    """The plan's case: nine columns, each with 90 days of a daily price change, a sale of three days every week with
    its price read, three promotions today, 40-character names; each deal with one realistic set of conditions, a club
    programme and a minimum spend (round 2's ruling)."""
    names = {column.key: (f"שם מוצר ארוך {index} " + "א" * 40)[:40] for index, column in enumerate(COLUMNS)}
    club = ["מועדון הלקוחות של הרשת"]
    deals = [_struct("7.90", restrictions=["club"], programmes=club, min_spend="150", promotion_id="100"),
             _struct("4.40", kind="percent_off", low="4.35", high="4.60", restrictions=["club"], programmes=club,
                     min_spend="200", promotion_id="101"),
             _struct(Fraction("10.01") / 3, kind="n_for_m", buy="3", restrictions=["club"], programmes=club,
                     min_spend="300", promotion_id="102")]
    listed = {back(n): ("10.90" if n % 2 else "11.90") for n in range(91)}
    on = [back(n) for n in range(1, 91) if n % 7 < 3]
    sales = {day: (_sale("7.90", day),) for day in on}
    pairs = {column.key: _pair(column.key, listed, on=[*on, DAY], promotions=deals, sales=sales,
                               next_start=DAY + timedelta(days=9)) for column in COLUMNS}
    return _covered(names, size=(Decimal(1000), "gml")), pairs


# The page's rules

def test_page_path():
    assert page_path(CODE) == f"p/{CODE}.html"
    assert MAX_PAGE == 60_000


def test_every_always_phrase_and_no_never_phrase():
    for page in (_render(*_typical()), _render(*_largest())):
        text = _visible(page)
        for phrase in ALWAYS:
            assert flatten(phrase) in text, phrase
        assert flatten(ALWAYS_SENTENCE) in text
        assert page.count(ALWAYS_SENTENCE) == 1                         # once, after the sections
        assert page.index(ALWAYS_SENTENCE) > page.rindex("</section>")
        for version in (text, flatten(SPAN.sub(" ", page))):
            assert not [phrase for phrase in NEVER if flatten(phrase) in version]
            assert not PRONOUNS.search(version)


def test_each_column_section_carries_f10_naming_the_column_and_no_probability():
    """F10 in every section's fold-out, naming the column (the amendment's "Words"), and, cut out, no odds word and no
    percentage (the spec's check: no probability while the gate is closed; N9: at render time)."""
    covered, pairs = _largest()
    page = _render(covered, pairs)
    sections = _sections(page)
    assert list(sections) == [column.key for column in COLUMNS]
    for column, body in sections.items():
        f10 = no_odds_yet(column)
        assert body.count(f10) == 1 and f10 in _fold(body), column
        others = [no_odds_yet(other.key) for other in COLUMNS if other.key != column]
        assert not [sentence for sentence in others if sentence in body]
        cut = flatten(strip_tags(SPAN.sub(" ", body.replace(f10, " "))))
        for word in (*ODDS_WORDS, "probab", "likel", "expect"):
            assert flatten(word) not in cut, (column, word)
        assert "%" not in cut, column


def test_a_gate_given_open_stops_the_page():
    """Step one has no odds line: an open gate is a bug upstream, never a page without F10."""
    covered, pairs = _typical()
    closed = Gate(column=DEAL, conditions={"days": False, "brier": False, "calibration": False}, reasons=["x"],
                  open=False)
    assert no_odds_yet(DEAL) in _render(covered, pairs, gates={DEAL: closed})
    with pytest.raises(ValueError, match="shufersal-deal"):
        _render(covered, pairs, gates={DEAL: Gate(column=DEAL, conditions={}, reasons=[], open=True)})


def test_a_chains_name_is_escaped_in_its_own_span():
    """Review Focus 4: a name that looks like markup or a NEVER word is escaped inside its own span, and kept out of
    the page's <title>, which no span can hold."""
    name = '<b>FAKE "x"\n'
    page = _render(_covered({DEAL: name}), {DEAL: _pair(DEAL, _listed())})
    escaped = CHAIN_SPAN.format('&lt;b&gt;FAKE "x"\n')
    assert page.count(escaped) == 2                     # the title and the names' list
    assert "<b>FAKE" not in page
    assert re.search(r"<title>([^<]*)</title>", page).group(1) == f"{CODE} - {SITE_NAME}"
    assert "fake" not in _visible(page)                 # only inside the span: the site check cuts it out


def test_a_programmes_name_is_escaped_in_the_chains_span():
    """S3: every programme's name beside `targets()`, as published, in the chain's span, in the fold-out only."""
    deal = _struct(restrictions=["other"], programmes=['<i>תו "זהב"</i>', "FAKE & co"])
    page = _render(*_one("10.00", deal))
    assert CHAIN_SPAN.format('&lt;i&gt;תו "זהב"&lt;/i&gt;') in page
    assert CHAIN_SPAN.format("FAKE &amp; co") in page
    assert "<i>תו" not in page                 # the page's own <i> are the badge's separator and the price's ₪
    deals = re.search(r'<ul class="deals">(.*?)</ul>', _fold(_sections(page)[DEAL]), re.DOTALL).group(1)
    assert (f"some customers only ({CHAIN_SPAN.format('&lt;i&gt;תו \"זהב\"&lt;/i&gt;')}, "
            f"{CHAIN_SPAN.format('FAKE &amp; co')}), {FROM_FIELDS}") in deals
    assert page.count("FAKE &amp; co") == 1                            # beside the verdict, the condition alone


def test_a_weighed_deal_is_per_kilogram():
    """P4: a weighed link's deal price is a kilogram's: the saving, the usual price and today's price on the label say
    so, the condition is in kilograms, and the fold-out lists the deal per kilogram."""
    deal = _struct("50.00", per="kg", kind="n_for_m", buy="1.5")
    body = _sections(_render(*_one("69.90", deal)))[DEAL]
    assert ('<div class="tag deal-3"><div class="say"><p class="verdict">At Shufersal Deal: <b>DEAL · ₪19.90 off a '
            'kilogram</b></p>') in body
    assert "<p class=\"reason\">Usually ₪69.90 a kilogram, sales included (90 days tracked).</p>" in body
    assert '<p class="price">Price today: <b><i>₪</i>50<sup>.00</sup></b><small> a kilogram</small></p>' in body
    assert "When you buy 1.5 kilograms" in body
    fold = _fold(body)
    assert fold.count("Deal price ₪50.00 per kilogram") == 1 and "buy 1.5" in fold
    assert "per unit" not in body


def test_a_promotions_error_says_so_in_each_of_the_chains_sections():
    """P10, question M (g): every section of the chain's columns, both Carrefour columns, and no other chain's."""
    names = {CITY: "שם", MARKET: "שם", RAMI: "שם"}
    pairs = {column: _pair(column, _listed()) for column in names}
    page = _render(_covered(names), pairs, errors={"carrefour": "RewardType 99 not seen in the chain's files"})
    sections = _sections(page)
    for column in (CITY, MARKET):
        assert sections[column].count(unreadable("carrefour")) == 1, column
        assert sections[column].index(unreadable("carrefour")) < sections[column].index("No sale today")
    assert "could not be read" not in sections[RAMI]
    assert "RewardType" not in page                     # the error's own text is the owner's email, not the page's


def test_a_product_beyond_the_read_says_when_last_seen_at_each_column():
    """Call 10, question G: a product whose pairs lie beyond the 90 days read keeps its page, and each column's section
    says it is not sold there today and when it was last seen listed across it; with no history, no chart."""
    names = {DEAL: "שם", SHELI: "שם אחר", RAMI: "שם"}
    last = {DEAL: date(2026, 6, 1), SHELI: date(2026, 7, 15)}
    page = _render(_covered(names, last_wide=last), {})
    sections = _sections(page)
    assert list(sections) == [RAMI, DEAL, SHELI]                   # name order
    assert "Not sold at Shufersal Deal today, last seen 1 June" in sections[DEAL]
    assert "Not sold at Shufersal Sheli today, last seen 15 July" in sections[SHELI]
    assert "<p class=\"not-sold\">Not sold at Rami Levy today</p>" in sections[RAMI]   # never wide there
    for column, body in sections.items():
        assert no_odds_yet(column) in _fold(body)
        assert "<svg" not in body and "days tracked" not in body and 'class="badge' not in body
        assert 'class="tag' not in body and 'class="pay"' not in body


def test_a_column_not_wide_today_says_when_last_listed_across():
    covered, pairs = _typical()
    narrow = {**pairs, RAMI: _pair(RAMI, _listed("11.50"), wide=False)}
    covered = Covered(code=CODE, title=covered.title, names=covered.names, size=covered.size,
                      first_covered=covered.first_covered, last_wide={DEAL: DAY, RAMI: back(4)})
    sections = _sections(_render(covered, narrow))
    assert last_across(RAMI, back(4)) in _fold(sections[RAMI])
    assert "last seen listed across" not in sections[DEAL]


def test_the_largest_page_is_under_60_kb():
    """Nine columns, each with 90 days of a daily price change, weekly sale runs, three promotions, 40-character
    names (the plan's Step 1), each part a label with its price part and the product's barcode (the site look's)."""
    page = _render(*_largest())
    assert page.count('<use href="#ean"/>') == 9 and page.count('<p class="price">') == 9
    assert len(page.encode("utf-8")) <= MAX_PAGE, len(page.encode("utf-8"))


def test_the_page_is_the_same_bytes_twice():
    covered, pairs = _largest()
    first = _render(covered, pairs)
    reordered = {column: pairs[column] for column in reversed(list(pairs))}
    names = {column: covered.names[column] for column in reversed(list(covered.names))}
    again = Covered(code=CODE, title=covered.title, names=names, size=covered.size,
                    first_covered=covered.first_covered, last_wide=covered.last_wide)
    days = dict(reversed(list(_days().items())))
    verdicts = dict(reversed(list(_verdicts(pairs, days).items())))
    assert first == _render(covered, pairs) == render_product(again, reordered, verdicts, days, DAY, "12:03", {}, {})


# The sections

def test_a_section_per_column_listing_it_or_with_its_history_in_name_order():
    covered, pairs = _typical()
    sections = SECTION.findall(_render(covered, pairs))
    assert [(column, slug) for column, _, slug, _ in sections] == [(RAMI, "ramilevy"), (DEAL, "shufersal")]
    for column, _, _, body in sections:
        assert body.startswith(f"<h2>{BY_KEY[column].name}</h2>")
    # a column with history in the read has its section, whatever names the registry gives
    history = {**pairs, SHELI: _pair(SHELI, _listed("9.00", 10, 40))}
    assert list(_sections(_render(covered, history))) == [RAMI, DEAL, SHELI]
    assert product.section_keys(covered, history) == [RAMI, DEAL, SHELI]


def test_each_section_says_the_verdict_with_the_store_types_name():
    """Anti-goal 1: the store type's name is inside every verdict, so a pick left over from last week shows itself."""
    body = _sections(_render(*_one("6.00", _struct("4.50"), on=[DAY])))[DEAL]
    assert '<p class="verdict">At Shufersal Deal: <b>DEAL · ₪1.50 off</b></p>' in body
    market = _sections(_render(*_one("6.00", _struct("4.50"), column=MARKET)))[MARKET]
    assert '<p class="verdict">At Carrefour Market: <b>DEAL · ₪1.50 off</b></p>' in market


def test_a_deal_is_a_green_label_in_its_shade():
    """The site look's label: a deal's verdict on a label in the shade of its saving (S5's class; its greens are the
    stylesheet's), the store type's name over the verdict in bold, then the reason; read as text, it is `badge`."""
    covered, pairs = _typical()
    found = _verdicts(pairs, _days())[DEAL]
    body = _sections(_render(covered, pairs))[DEAL]
    assert ('<div class="tag deal-2"><div class="say"><p class="verdict">At Shufersal Deal: <b>DEAL · ₪3.00 off</b>'
            '</p><p class="reason">') in body
    (verdict_line,) = re.findall(r'<p class="verdict">(.*?)</p>', body)
    assert _read(verdict_line) == words.badge(found) == "At Shufersal Deal: DEAL · ₪3.00 off"
    shades = {}
    for usual, price in (("5.00", "4.00"), ("5.00", "2.00"), ("10.00", "5.00")):
        shades[usual, price] = _label(_sections(_render(*_one(usual, _struct(price))))[DEAL])[0]
    assert shades == {("5.00", "4.00"): "deal-1", ("5.00", "2.00"): "deal-2", ("10.00", "5.00"): "deal-3"}


def test_no_deal_is_the_yellow_label():
    """S5 and anti-goal 5: a no deal is said in words, "NO DEAL", on the yellow label (`no-deal`: its colours are the
    stylesheet's `--nd` tokens, tests/test_look.py), so colour is never the only signal; then its reason."""
    body = _sections(_render(*_one("5.00", _struct("4.50"))))[DEAL]
    assert ('<div class="tag no-deal"><div class="say"><p class="verdict">At Shufersal Deal: <b>NO DEAL</b></p>'
            '<p class="reason">Only ₪0.50 below its usual ₪5.00 (90 days tracked).</p></div>') in body
    assert body.count("NO DEAL") == 1 and "grey" not in body


def test_the_reason_line_names_its_days():
    """S8: every reason names the days it rests on, the days with a day price (6 of Deal's 90 tracked days were on
    sale at a price not read), right after the badge."""
    body = _sections(_render(*_typical()))[DEAL]
    paragraphs = _paragraphs(body)
    assert paragraphs[:2] == ["At Shufersal Deal: DEAL · ₪3.00 off",
                             "Usually ₪10.90, sales included (84 days with a known price)."]
    assert '<div class="tag deal-2">' in body
    # a short history says how short; an always-on sale says how often it has been at today's price
    short = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed("6.00", 0, 5), promotions=[_struct("4.50")])})
    assert "Usually ₪6.00, sales included (5 days tracked)." in short
    always = {day: (_sale("7.90", day),) for day in _listed("9.90", 1, 90)}
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed("9.90"), on=list(_listed("9.90")),
                                                        promotions=[_struct("7.90")], sales=always)})
    assert '<p class="verdict">At Shufersal Deal: <b>NO DEAL</b></p>' in page
    assert "It's been ₪7.90 or less on 90 of the 90 days tracked." in page


def _no_verdict_case(call: str):
    """A page whose Deal section gets `call`, and its column-days."""
    days = _days()
    listed = _listed("10.00")
    if call == "unread_today":
        return _one("10.00", _struct("7.90")), _days(promo_holes={(DEAL, DAY)})
    if call == "no_sale":
        return _one("10.00"), days
    if call == "some_stores":
        return _one("10.00", _struct("7.90", wide=False)), days
    if call == "price_unread":
        return _one("10.00", _struct(None, valid=False, why="no price in the fields"), on=[DAY]), days
    if call == "new":
        return (_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, {DAY: "10.00"}, promotions=[_struct("7.90")])}), days
    if call == "mostly_unknown":
        return _one("10.00", _struct("7.90"), on=[back(n) for n in range(0, 61)]), days
    if call == "too_few":                # a hole today: files from 5 of the column's 20 stores
        return _one("10.00", _struct("7.90")), _days(holes={(DEAL, DAY)})
    if call == "not_sold":               # listed until 10 days ago
        pair = _pair(DEAL, _listed("10.00", 10, 60))
        return (_covered({DEAL: "שם"}, last_wide={DEAL: back(10)}), {DEAL: pair}), days
    assert call == "no_history"          # seen before today only on days whose promotions were not read
    unread = _days(promo_holes={(DEAL, back(n)) for n in range(1, 91)})
    return (_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, listed, promotions=[_struct("7.90")])}), unread


@pytest.mark.parametrize("call", list(words.NO_VERDICT))
def test_each_line_that_is_not_a_verdict_is_a_plain_label(call):
    """S4 and the site look's label: no verdict, NO_VERDICT's line instead, verbatim, as the verdict of a plain label
    (`none`), with no deal's words; then its price part (`test_the_price_part_sets_todays_price_as_on_a_shelf_edge`)."""
    (covered, pairs), days = _no_verdict_case(call)
    found = _verdicts(pairs, days)[DEAL]
    assert found.call == call
    body = _sections(_render(covered, pairs, column_days=days))[DEAL]
    assert f'<div class="tag none"><div class="say"><p class="verdict">{words.NO_VERDICT[call]}</p>' in body
    assert _label(body)[0] == "none" and body.count('<div class="tag') == 1
    assert 'class="badge' not in body and "DEAL ·" not in body and "NO DEAL" not in body
    assert "Usually ₪" not in body and "It's been" not in body and "Only ₪" not in body
    # a sale whose price could not be read has no price today (the owner, 2026-11-11): no Today in the chart's table,
    # no today in its spoken summary, no dot at its right end, and no "Last this low"; no sale and a sale at some
    # stores take the listed price as today's
    if call in ("unread_today", "price_unread", "no_sale", "some_stores"):
        known = call in ("no_sale", "some_stores")
        said = ('<th scope="col">Today</th>' in body, "today ₪" in body, "Last this low" in body)
        assert said == (known,) * 3, call
        assert known or "<circle" not in body, call


@pytest.mark.parametrize("call", ["too_few", "not_sold"])
def test_too_few_files_and_not_sold_have_no_label(call):
    """The site look's label, call by call: a hole's too-few-files line and the not-sold slot stand alone, with no
    label and no price part; the chart, when there is one, follows."""
    (covered, pairs), days = _no_verdict_case(call)
    assert _verdicts(pairs, days)[DEAL].call == call
    body = _sections(_render(covered, pairs, column_days=days))[DEAL]
    line = (f'<p class="few">{too_few(5, STORES)}</p>' if call == "too_few"
            else '<p class="not-sold">Not sold at Shufersal Deal today, last seen 10 November</p>')
    assert body.startswith(f"<h2>Shufersal Deal</h2>{line}")
    assert 'class="tag' not in body and 'class="pay"' not in body and 'class="verdict"' not in body
    assert body.index(line) < body.index('<div class="history">')


def test_the_price_part_sets_todays_price_as_on_a_shelf_edge():
    """The site look's price part: today's price as on a shelf edge, as `price_line` shows it, the shekels large and
    the point and the agorot raised; read as text it is `price_line`. A weighed deal's price is a kilogram's, its unit
    in small print after it. With no price today (an unread sale price, sale prices not read today) there is no price
    line, and a hole's line and the not-sold slot have no price part at all."""
    covered, pairs = _one("14.00")
    found = _verdicts(pairs, _days())[DEAL]
    assert found.call == "no_sale"
    price = '<p class="price">Price today: <b><i>₪</i>14<sup>.00</sup></b></p>'
    assert _label(_sections(_render(covered, pairs))[DEAL])[2] == price + mark(CODE)
    assert _read(price) == words.price_line(found) == "Price today: ₪14.00"
    for listed, offer, figure in (("6.00", "4.50", "4<sup>.50</sup>"), ("1299.90", "1234.05", "1234<sup>.05</sup>")):
        body = _sections(_render(*_one(listed, _struct(offer))))[DEAL]
        assert f'<p class="price">Price today: <b><i>₪</i>{figure}</b></p>' in body, offer
    weighed_covered, weighed_pairs = _one("69.90", _struct("50.00", per="kg", kind="n_for_m", buy="1.5"))
    weighed = _sections(_render(weighed_covered, weighed_pairs))[DEAL]
    line = '<p class="price">Price today: <b><i>₪</i>50<sup>.00</sup></b><small> a kilogram</small></p>'
    assert line in weighed
    assert _read(line) == words.price_line(_verdicts(weighed_pairs, _days())[DEAL]) == "Price today: ₪50.00 a kilogram"
    for call in ("unread_today", "price_unread", "too_few", "not_sold"):
        (covered, pairs), days = _no_verdict_case(call)
        body = _sections(_render(covered, pairs, column_days=days))[DEAL]
        assert 'class="price"' not in body and "Price today" not in body, call
        assert ('class="pay"' in body) is (call in ("unread_today", "price_unread")), call


def test_the_label_carries_the_products_barcode():
    """The site look's barcode: drawn once a page, right after the barcode line (`drawing`, so `id="ean"` once), and
    shown by reference at the end of every label's price part (`mark`); an unread sale price's part holds the mark
    alone."""
    assert drawing(CODE) and mark(CODE)
    covered, pairs = _largest()
    page = _render(covered, pairs)
    (line,) = re.findall(r"<p>Barcode [^<]*</p>", page)
    assert f'{line}\n{drawing(CODE)}\n<h2 class="elsewhere" hidden>' in page
    assert page.count(drawing(CODE)) == 1 and page.count('id="ean"') == 1 and page.count('<svg class="defs"') == 1
    sections = _sections(page)
    for key, body in sections.items():
        pay = _label(body)[2]
        assert pay.endswith(mark(CODE)) and body.count(mark(CODE)) == 1 and body.count("<use") == 1, key
    assert page.count(mark(CODE)) == len(sections) == 9
    (covered, pairs), days = _no_verdict_case("price_unread")
    assert _label(_sections(_render(covered, pairs, column_days=days))[DEAL])[2] == mark(CODE)


def test_a_product_with_no_bars_has_no_drawing_and_no_mark():
    """Review Focus 1: a code no barcode can be drawn for (here 11 digits) has no drawing and no mark: its price part
    holds the price alone, or is left out with no price today, and the barcode line still gives its digits."""
    assert drawing(NO_BARS) == mark(NO_BARS) == ""
    covered, pairs = _one("14.00")
    page = _render(replace(covered, code=NO_BARS), pairs)
    assert '<svg class="defs"' not in page and 'id="ean"' not in page and "<use" not in page and "<svg" in page
    assert f"<p>Barcode {NO_BARS}</p>" in page
    assert _label(_sections(page)[DEAL])[2] == '<p class="price">Price today: <b><i>₪</i>14<sup>.00</sup></b></p>'
    (covered, pairs), days = _no_verdict_case("price_unread")
    body = _sections(_render(replace(covered, code=NO_BARS), pairs, column_days=days))[DEAL]
    assert _label(body)[2] is None and 'class="pay"' not in body
    assert '<div class="tag none"><div class="say">' in body and "</p></div></div>" in body


def test_a_page_with_no_label_carries_no_drawing():
    """The barcode's drawing goes on a page only when a part shows its mark (the controller's ruling of 2026-11-16: no
    dead bytes): a page whose every part is a hole's line or the not-sold slot carries neither; one label is enough for
    the drawing, once."""
    names = {DEAL: "שם", RAMI: "שם"}
    pairs = {DEAL: _pair(DEAL, _listed("10.00")), RAMI: _pair(RAMI, _listed("10.00", 10, 60))}
    covered = _covered(names, last_wide={DEAL: DAY, RAMI: back(10)})
    days = _days(holes={(DEAL, DAY)})
    verdicts = _verdicts(pairs, days)
    assert (verdicts[DEAL].call, verdicts[RAMI].call) == ("too_few", "not_sold")
    page = _render(covered, pairs, column_days=days)
    assert '<svg class="defs"' not in page and 'id="ean"' not in page and "<use" not in page
    assert f"<p>Barcode {CODE}</p>\n<h2 " in page
    selling = {**pairs, RAMI: _pair(RAMI, _listed("10.00"))}                  # Rami Levy sells it today
    page = _render(covered, selling, column_days=days)
    assert page.count(drawing(CODE)) == 1 and page.count(mark(CODE)) == 1


def test_the_chart_takes_todays_shelf_price_from_the_day():
    """The plan's "The chart, call by call": a section's history is drawn with today's shelf price, as shown, on a day
    with records; with none on a hole, for a product not sold today, and on an unread sale price or sale prices not
    read today (the owner's rulings of 2026-11-11 and 2026-11-16, and the design's state table), whose chart's today
    column then holds "today" alone."""
    covered, pairs = _typical()
    found = _verdicts(pairs, _days())[DEAL]
    history = _history(_sections(_render(covered, pairs))[DEAL])
    assert history == render_chart(found, DAY, Decimal(money(pairs[DEAL].points[DAY].listed)))
    assert history == render_chart(found, DAY, Decimal("11.90")) != render_chart(found, DAY, None)
    for call in ("too_few", "not_sold", "price_unread", "unread_today"):
        (covered, pairs), days = _no_verdict_case(call)
        found = _verdicts(pairs, days)[DEAL]
        assert found.call == call and found.days
        body = _sections(_render(covered, pairs, column_days=days))[DEAL]
        assert _history(body) == render_chart(found, DAY, None), call
        point = pairs[DEAL].points.get(DAY)
        assert (point is None) is (call == "not_sold")
        if point is not None:                       # a shelf price there to draw, and not drawn
            assert _history(body) != render_chart(found, DAY, Decimal(money(point.listed))), call
        if call in ("price_unread", "unread_today"):
            (now,) = re.findall(r'<svg class="now" aria-hidden="true">(.*?)</svg>', body)
            assert "<circle" not in now and "₪" not in now and _read(now) == "today", call


def test_the_facts_follow_the_history():
    """The site look's product page: the label, then the history (the chart, its key and its table), then "Last this
    low" and "How often on sale" as two ruled facts, then the fold-out."""
    sales = {back(n): (_sale("6.90", back(n)),) for n in (12, 11, 10)}
    pairs = {DEAL: _pair(DEAL, _listed("10.00"), on=[*sales, DAY], promotions=[_struct("7.00")], sales=sales)}
    found = _verdicts(pairs, _days())[DEAL]
    body = _sections(_render(_covered({DEAL: "שם"}), pairs))[DEAL]
    low, often = (f'<p class="fact">{said}</p>' for said in (words.last_low(found), words.how_often(found)))
    assert low == '<p class="fact">Last this low: 10 November, at ₪6.90.</p>'
    assert often.startswith('<p class="fact">On sale on 3 of the 90 days tracked.')
    history = _history(body)
    assert history.startswith('<div class="history"><div class="chart">')
    assert f"</div></div>{history}{low}{often}<details>" in body
    assert body.index('<div class="tag deal-2">') < body.index(history)


def test_an_unread_sale_price_counts_today_as_on_sale():
    """price_unread: on sale today, its price not read, so "How often on sale" counts today's sale as this one and
    names the last sale before it, with no price today beside it."""
    sales = {back(n): (_sale("7.90", back(n)),) for n in (12, 11, 10)}
    unread = _struct(None, valid=False, why="no price in the fields")
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed("10.00"), on=[*sales, back(2), back(1), DAY],
                                                        promotions=[unread], sales=sales)})
    body = _sections(page)[DEAL]
    assert f"<p class=\"verdict\">{words.NO_VERDICT['price_unread']}</p>" in body
    assert "The last sale before this one ended 10 November, at ₪7.90." in body
    assert "<circle" not in body and "Last this low" not in body and "Lowest in the" not in body


def test_a_hole_day_shows_too_few_files_and_no_listed_price_claim():
    """The second pre-flight's S1: a column-day with files from fewer than half its stores shows `too_few` in place of
    a verdict, its price in the fold-out as from too few files, and no listed-price claim; a product it does not list is
    never said not sold."""
    covered, pairs = _typical()
    page = _render(covered, pairs, column_days=_days(holes=[(DEAL, DAY), (SHELI, DAY)]))
    sections = _sections(page)
    body = sections[DEAL]
    assert f'<p class="few">{too_few(5, STORES)}</p>' in body
    assert "₪11.90" in _fold(body) and too_few(5, STORES) in _fold(body)
    assert "Listed price" not in body and 'class="badge' not in body and "Not sold" not in body
    assert "Listed price ₪11.50" in sections[RAMI]
    # a section on a hole whose few files do not list the product says so, never that it is not sold there
    named = Covered(code=CODE, title=covered.title, names={**covered.names, SHELI: "שם"}, size=None,
                    first_covered=back(80), last_wide={SHELI: back(9)})
    sheli = _sections(_render(named, {**pairs, SHELI: _pair(SHELI, _listed("9.00", 1, 40))},
                              column_days=_days(holes=[(SHELI, DAY)])))[SHELI]
    assert f'<p class="few">{too_few(5, STORES)}</p>' in sheli
    assert "Not sold" not in sheli and "last seen" not in sheli and '<p class="today">' not in sheli


def test_a_hole_day_says_no_last_listed_across():
    """Fix round 1 (the review's Important 1): on a hole the few files cannot tell whether the product is listed across
    the column today, so the section never says when it last was, whether those files list it or not."""
    covered, pairs = _typical()
    registry = Covered(code=CODE, title=covered.title, names=covered.names, size=covered.size,
                       first_covered=covered.first_covered, last_wide={DEAL: back(1), RAMI: back(1)})
    listed = {day: point for day, point in pairs[DEAL].points.items()}
    listed[DAY] = Point(day=DAY, listed=Decimal("11.90"), low=Decimal("11.90"), high=Decimal("12.90"), listing=5,
                        wide=False, on_promotion=False, next_start=None, promotions=())   # all 5 stores with a file
    holed = _days(holes=[(DEAL, DAY), (RAMI, DAY)])
    gone = {day: point for day, point in pairs[RAMI].points.items() if day != DAY}
    sections = _sections(_render(registry, {DEAL: Pair(column=DEAL, code=CODE, points=listed),
                                            RAMI: Pair(column=RAMI, code=CODE, points=gone)}, column_days=holed))
    for column in (DEAL, RAMI):
        assert too_few(5, STORES) in sections[column]
        assert "last seen" not in sections[column], column
    assert "stores ₪11.90 to ₪12.90, 5 of 5 list it" in sections[DEAL]
    # on a day with records it is said as before: in the fold-out when listed but not across, beside "Not sold" when
    # not listed at all
    sections = _sections(_render(registry, {DEAL: Pair(column=DEAL, code=CODE, points=listed),
                                            RAMI: Pair(column=RAMI, code=CODE, points=gone)}))
    assert last_across(DEAL, back(1)) in _fold(sections[DEAL])
    assert "Not sold at Rami Levy today, last seen 19 November" in sections[RAMI]


def test_a_hole_morning_lists_no_promotion_across_the_column():
    """Deploy prep (the owner, 2026-11-10): on a morning that is a hole for a column (files from 5 of its 20 stores),
    whether a promotion is listed across the column is judged over those few files, so every promotion in its fold-out
    shows "at some stores", and no coming sale is said (the items row's `next_start`, judged wide over the same few
    files); the section's too-few-files line stays, and another column's day with records is as before."""
    covered, typical = _typical()
    start = DAY + timedelta(days=9)                     # each column's items row lists a wide promotion to start
    pairs = {key: replace(pair, points={**pair.points, DAY: replace(pair.points[DAY], next_start=start)})
             for key, pair in typical.items()}
    page = _render(covered, pairs, column_days=_days(holes=[(DEAL, DAY)]))
    body = _sections(page)[DEAL]
    assert too_few(5, STORES) in body
    assert "A sale starts" not in body
    items = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="deals">(.*?)</ul>', body, re.DOTALL).group(1))
    assert items == ["<b>Deal price ₪7.90 per unit</b><small>club members only, from the chain's fields; "
                     f"{FINE_PRINT}</small><small>{MORNING}; {AT_SOME_STORES}</small>"]
    assert _sections(page)[RAMI].count(words.coming_sale(start)) == 1               # another column's day with records
    # the same day with records: listed across, and the coming sale
    body = _sections(_render(covered, pairs))[DEAL]
    assert f"<small>{MORNING}</small>" in body and AT_SOME_STORES not in body
    assert body.count(words.coming_sale(start)) == 1


def test_a_not_sold_section_says_when_last_seen():
    """Store first, "What a visitor sees" 7: a store type that sold it before and not today says so, with the last day
    it was seen listed across it (Call 10's line), its history still shown; with no such day, the line alone."""
    pair = _pair(DEAL, _listed("10.00", 10, 60))
    page = _render(_covered({DEAL: "שם"}, last_wide={DEAL: date(2026, 11, 3)}), {DEAL: pair})
    body = _sections(page)[DEAL]
    assert '<p class="not-sold">Not sold at Shufersal Deal today, last seen 3 November</p>' in body
    assert '<div class="history">' in body and "On sale on 0 of the 51 days tracked." in body
    assert 'class="badge' not in body and "Listed price" not in body
    bare = _sections(_render(_covered({DEAL: "שם"}, last_wide={}), {DEAL: pair}))[DEAL]
    assert '<p class="not-sold">Not sold at Shufersal Deal today</p>' in bare


def test_the_condition_beside_the_verdict():
    """S3: the promotion the verdict judges names its conditions beside it, in shopper words."""
    deal = _struct("3.00", kind="n_for_m", buy="2", restrictions=["club"])
    body = _sections(_render(*_one("6.00", deal)))[DEAL]
    paragraphs = _paragraphs(body)
    assert paragraphs[:3] == ["At Shufersal Deal: DEAL · ₪3.00 off", "Usually ₪6.00, sales included (90 days tracked).",
                              "Club members only; When you buy 2"]
    assert _label(body)[1].endswith('<p class="conditions">Club members only; When you buy 2</p>')
    assert "Club members only" not in _sections(_render(*_one("6.00", _struct("3.00"))))[DEAL]


def test_a_coming_sale_line():
    """F2 in shopper words: an item listing a wide promotion to start within 14 days; none on a hole morning."""
    start = DAY + timedelta(days=9)
    body = _sections(_render(*_one("10.00", next_start=start)))[DEAL]
    assert _label(body)[1].endswith("<p>A sale starts on 29 November</p>")          # the label's last line
    assert "A sale starts" not in _render(*_one("10.00"))
    holed = _render(*_one("10.00", next_start=start), column_days=_days(holes=[(DEAL, DAY)]))
    assert "A sale starts" not in holed


def test_the_fold_out_holds_the_range_the_definition_every_promotion_and_no_odds():
    """"How this is worked out": today's listed price, defined, with the stores' range and how many list it; every
    promotion running today with its source labels and the fine print, "at some stores" on one not listed across the
    column; then F10's sentence."""
    deals = [_struct("7.90", restrictions=["club"]), _struct("8.50", wide=False, promotion_id="2")]
    covered, pairs = _typical()
    pairs = {**pairs, DEAL: _pair(DEAL, {**_listed("10.90", 31, 90), **_listed("11.90", 0, 30)}, promotions=deals)}
    fold = _fold(_sections(_render(covered, pairs))[DEAL])
    assert ("<p class=\"today\">Listed price ₪11.90, before promotions, as listed in the chain's price files<small>stores "
            "₪11.90 to ₪12.90, 18 of 20 list it</small></p>") in fold
    items = re.findall(r"<li>(.*?)</li>", fold)
    assert len(items) == 2 and all(FINE_PRINT in item and MORNING in item for item in items)
    assert AT_SOME_STORES not in items[0] and AT_SOME_STORES in items[1]
    assert fold.endswith(f"<p>{no_odds_yet(DEAL)}</p>")
    assert fold.index("Listed price") < fold.index("<ul") < fold.index(no_odds_yet(DEAL))


def test_todays_listed_price_and_its_stores_range():
    """P2: today's listed price with the design's phrases beside it, and the stores' range labelled as the stores'
    (never a "listed price", so ALWAYS_SENTENCE stays true)."""
    fold = _fold(_sections(_render(*_typical()))[DEAL])
    assert ("Listed price ₪11.90, before promotions, as listed in the chain's price files<small>stores ₪11.90 to "
            "₪12.90, 18 of 20 list it</small>") in fold


def test_each_promotion_today_with_its_conditions_from_the_fields():
    """P4, P5, S3: the deal price, buy N, the stores' range for percent off; the restrictions by `targets` from the
    fields with the programmes beside them; the minimum spend; then the fine print, the morning's files and, when the
    promotion is not wide, "at some stores". A promotion that has not started or has ended is not today's."""
    deals = [_struct("10/3", kind="n_for_m", buy="3", restrictions=["club", "chain_card"], min_spend="150"),
             _struct("4.40", kind="percent_off", low="4.35", high="4.60", wide=False, promotion_id="2"),
             _struct("1.00", start=DAY + timedelta(days=2), promotion_id="3"),
             _struct("1.50", end=back(1), promotion_id="4")]
    page = _render(*_one("10.00", *deals))
    items = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="deals">(.*?)</ul>', page, re.DOTALL).group(1))
    assert items == [
        "<b>Deal price ₪3.33 per unit</b>, buy 3<small>club members only, and the chain's card holders only, "
        f"{FROM_FIELDS}; minimum spend ₪150.00, {FROM_FIELDS}; {FINE_PRINT}</small><small>{MORNING}</small>",
        f"<b>Deal price ₪4.40 per unit</b>, stores' deal prices ₪4.35 to ₪4.60<small>{FINE_PRINT}</small>"
        f"<small>{MORNING}; {AT_SOME_STORES}</small>"]
    assert "PLACEHOLDER-DESCRIPTION" not in page            # the chain's text is not shown
    # beside the verdict, the judged promotion's conditions in shopper words
    assert "Club members only; The chain's card holders only; When you buy 3; Minimum spend ₪150.00" in page


def test_a_promotion_starting_or_ending_today_runs_today():
    """P3: a promotion runs on its start day and on its end day."""
    deals = [_struct("7.00", start=DAY, promotion_id="1"), _struct("8.00", end=DAY, promotion_id="2"),
             _struct("9.00", start=DAY + timedelta(days=1), promotion_id="3")]
    body = _sections(_render(*_one("10.00", *deals)))[DEAL]
    assert "Deal price ₪7.00 per unit" in body and "Deal price ₪8.00 per unit" in body
    assert "₪9.00" not in body


def test_every_promotion_says_fine_print_not_read():
    """S12 (b): P5's fine print label beside every promotion, read or not (step one reads no fine print)."""
    deals = [_struct("7.90"), _struct(None, valid=False, why="no kind link", kind=None, promotion_id="2"),
             _struct("5.00", wide=False, promotion_id="3")]
    page = _render(*_one("10.00", *deals))
    items = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="deals">(.*?)</ul>', page, re.DOTALL).group(1))
    assert len(items) == 3
    for item in items:
        assert FINE_PRINT in item and MORNING in item


def test_an_invalid_deal_shows_price_not_read_only():
    """P4: a deal whose fields do not validate is listed with "price not read", no price beside it, never its why; with
    no other promotion, the section says its sale price could not be read."""
    deal = _struct("25.00", valid=False, why="not below twice the listed price", kind="percent_off", low="24.00",
                   high="26.00")
    page = _render(*_one("10.00", deal, on=[DAY]))
    body = _sections(page)[DEAL]
    assert f"<b>{PRICE_NOT_READ}</b><small>" in _fold(body)
    assert "₪25.00" not in page and "₪24.00" not in page and "twice" not in page
    assert f"<p class=\"verdict\">{words.NO_VERDICT['price_unread']}</p>" in body


def test_names_each_with_the_columns_listing_it():
    """Call 4: the title is the longest name, and each distinct name is shown once with the columns that list it."""
    names = {DEAL: "קצר", SHELI: "שם ארוך יותר", RAMI: "קצר"}
    page = _render(_covered(names), {column: _pair(column, _listed()) for column in names})
    assert f"<h1>{CHAIN_SPAN.format('שם ארוך יותר')}</h1>" in page
    listed = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="names">(.*?)</ul>', page, re.DOTALL).group(1))
    assert listed == [f"{CHAIN_SPAN.format('קצר')} (as Rami Levy and Shufersal Deal list it)",
                      f"{CHAIN_SPAN.format('שם ארוך יותר')} (as Shufersal Sheli lists it)"]


def test_the_barcode_and_the_size_the_chains_state():
    covered, pairs = _typical()
    assert f"<p>Barcode {CODE} · 200 g/ml</p>" in _render(covered, pairs)
    bare = Covered(code=CODE, title="שם", names={DEAL: "שם"}, size=None, first_covered=back(80), last_wide={})
    assert f"<p>Barcode {CODE}</p>" in _render(bare, {DEAL: _pair(DEAL, _listed())})


# The badge row, "Elsewhere today"

def _shops() -> tuple[Covered, dict[str, Pair]]:
    """Seven columns: deals of ₪3.00 at Deal and at Yochananof, ₪1.00 at Rami Levy; no deals of ₪0.50 at Sheli and
    ₪0.50 above its usual at Osher Ad; no sale at Carrefour Market; Carrefour City sold before, not today."""
    def at(column, price, *structs):
        return _pair(column, _listed(price), promotions=structs)
    pairs = {DEAL: at(DEAL, "10.00", _struct("7.00")), YOCHANANOF: at(YOCHANANOF, "10.00", _struct("7.00")),
             RAMI: at(RAMI, "8.00", _struct("7.00")), SHELI: at(SHELI, "7.50", _struct("7.00")),
             OSHER: at(OSHER, "6.50", _struct("7.00")), MARKET: at(MARKET, "9.00"),
             CITY: _pair(CITY, _listed("9.00", 5, 40))}
    return _covered({column: "שם" for column in pairs}), pairs


def test_elsewhere_today_has_a_badge_per_store_type_selling_it_by_saving():
    """The plan's "The badge row": one badge per store type with a point today, deals and no deals by saving as shown,
    largest first (a tie in COLUMNS order), the rest after them in COLUMNS order; none for a store type not listing it
    today; each links to its section."""
    covered, pairs = _shops()
    page = _render(covered, pairs)
    (row,) = NAV.findall(page)
    badges = BADGE.findall(row)
    assert [key for key, _, _, _ in badges] == [DEAL, YOCHANANOF, RAMI, SHELI, OSHER, MARKET]
    assert [(shade, _read(said)) for _, _, shade, said in badges] == [
        ("deal-2", "Shufersal Deal · DEAL · ₪3.00 off"), ("deal-2", "Yochananof · DEAL · ₪3.00 off"),
        ("deal-1", "Rami Levy · DEAL · ₪1.00 off"), ("no-deal", "Shufersal Sheli · NO DEAL"),
        ("no-deal", "Osher Ad · NO DEAL"), ("none", "Carrefour Market · no sale today")]
    ids = set(re.findall(r'\sid="([^"]+)"', page))
    assert all(key == target and f"c-{target}" in ids for key, target, _, _ in badges)
    assert len(badges) == row.count("<a ")
    assert CITY in _sections(page) and f'data-column="{CITY}" href' not in row


def test_the_badges_without_a_verdict_follow_in_columns_order():
    """The row's tail: after the deals and no deals, every badge with no verdict, in COLUMNS order whatever its call
    (here a sale at some stores at Carrefour City, an unread sale price at Osher Ad, no sale at Yochananof)."""
    unread = _struct(None, valid=False, why="no price in the fields")
    pairs = {YOCHANANOF: _pair(YOCHANANOF, _listed("9.00")),
             OSHER: _pair(OSHER, _listed("9.00"), on=[DAY], promotions=[unread]),
             CITY: _pair(CITY, _listed("9.00"), promotions=[_struct("7.00", wide=False)]),
             RAMI: _pair(RAMI, _listed("10.00"), promotions=[_struct("7.00")])}
    (row,) = NAV.findall(_render(_covered({column: "שם" for column in pairs}), pairs))
    assert [(key, shade) for key, _, shade, _ in BADGE.findall(row)] == [
        (RAMI, "deal-2"), (CITY, "none"), (OSHER, "none"), (YOCHANANOF, "none")]


def test_the_markup_search_js_reads():
    """search.js's header: a product page has nav.badges (empty when nothing sells it today), its badges
    a[data-column] linking to #c-<key>, a section[data-column] with id c-<key> per part, and the row's heading
    h2.elsewhere, hidden in the HTML, before the row; one of each."""
    for covered, pairs in (_typical(), _shops(), (_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed("1.00", 3, 9))})):
        page = _render(covered, pairs)
        assert page.count('<nav class="badges">') == 1 and page.count("<nav") == 1
        assert page.count('<h2 class="elsewhere" hidden>Elsewhere today</h2>\n<nav class="badges">') == 1
        for key in _sections(page):
            assert page.count(f'<section data-column="{key}" id="c-{key}" ') == 1
        row = NAV.findall(page)[0]
        assert all(key in _sections(page) for key in re.findall(r'<a data-column="([^"]+)" href="#c-\1"', row))
    nowhere = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed("1.00", 3, 9))})
    assert '<nav class="badges"></nav>' in nowhere


def test_elsewhere_badges_read_as_their_words():
    """The site look's small labels: each badge is the store type's name, a separator the stylesheet hides, and the
    verdict, or the line of a call without one, in bold; read as text it is `short_badge`, so the name and the verdict
    never run together."""
    covered, pairs = _shops()
    verdicts = _verdicts(pairs, _days())
    (row,) = NAV.findall(_render(covered, pairs))
    badges = re.findall(r'<a data-column="([^"]+)".*?</a>', row)
    assert len(badges) == 6
    for key, markup in zip(badges, re.findall(r'<a data-column=".*?</a>', row)):
        found = verdicts[key]
        assert markup == (f'<a data-column="{key}" href="#c-{key}" class="badge {product.badge_class(found)}">'
                          f'{BY_KEY[key].name}<i> · </i><b>{words.short_verdict(found)}</b></a>'), key
        assert _read(markup) == words.short_badge(found), key
    assert ('<a data-column="carrefour-market" href="#c-carrefour-market" class="badge none">Carrefour Market<i> · </i>'
            '<b>no sale today</b></a>') in row


def test_with_the_script_blocked_every_store_types_part_is_in_the_html():
    """The design's "Testing": with the script blocked, every store type's part is in the page, in COLUMNS order, with
    its label (its verdict words and its reason), its chart, last this low and how often."""
    covered, pairs = _largest()
    days = _days()
    verdicts = _verdicts(pairs, days)
    page = _render(covered, pairs)
    sections = _sections(page)
    assert list(sections) == [column.key for column in COLUMNS]
    for key, body in sections.items():
        found = verdicts[key]
        assert found.call == "deal"
        assert _paragraphs(_label(body)[1])[:2] == [words.badge(found), words.reason(found)], key
        for said in (words.last_low(found), words.how_often(found)):
            assert said and f'<p class="fact">{said}</p>' in body, (key, said)
        assert f'role="img" aria-label="{words.chart_summary(found)}"' in body
        assert body.index('<div class="tag') < body.index(words.reason(found)) < body.index(
            '<div class="history">') < body.index(words.last_low(found)) < body.index(
            words.how_often(found)) < body.index("<details>")


def test_nothing_is_hidden_without_the_script():
    """"Nothing is hidden without the script" (the plan), as the script hides parts with its own `hidden` attribute
    (Task 4): the only `hidden` in the HTML is the Elsewhere heading's. What the style hides is the stylesheet's
    (tests/test_look.py's `test_nothing_is_hidden_but_by_a_named_rule`)."""
    for covered, pairs in (_typical(), _largest(), _shops()):
        page = _render(covered, pairs)
        assert re.findall(r"<[^>]*\shidden(?=[\s>=])[^>]*>", page) == ['<h2 class="elsewhere" hidden>']


def test_a_product_sold_nowhere_today_has_no_badges_and_every_part():
    """Review Focus 4 and the second pre-flight's S7: a covered product no column lists today has an empty badge row,
    every part, each saying where it is not sold and when it was last seen, with its history, and still carries the
    four ALWAYS phrases."""
    names = {DEAL: "שם", SHELI: "שם", RAMI: "שם"}
    pairs = {column: _pair(column, _listed("10.00", 10, 60)) for column in names}
    page = _render(_covered(names, last_wide={column: back(10) for column in names}), pairs)
    assert NAV.findall(page) == [""]
    sections = _sections(page)
    assert list(sections) == [RAMI, DEAL, SHELI]
    for key, body in sections.items():
        assert f"Not sold at {BY_KEY[key].name} today, last seen 10 November" in body
        assert '<div class="history">' in body and "On sale on 0 of the 51 days tracked." in body
        assert no_odds_yet(key) in _fold(body)
    text = _visible(page)
    assert all(flatten(phrase) in text for phrase in ALWAYS)
    assert "Listed price ₪" not in page and "Deal price" not in page       # nothing listed today, nothing priced


def test_p7_p8_and_p9_are_gone():
    """Store first's "Changes to the shopper-site design": P7's sentences, P8's, the price-change text and P9's table
    give way to the verdict, the chart, "Last this low", "How often on sale" and "Elsewhere today". The only table
    left is each chart's own (the site look's: lowest, highest, usual and today)."""
    for page in (_render(*_largest()), _render(*_typical())):
        text = _visible(page)
        for gone in ("The deal against its listed prices", "How often it goes on promotion", "30-day median", "Today at each column",
                     "Run before today", "Runs before today", "The listed price did not change", "rose from",
                     "On a promotion listed across", "Listed to start"):
            assert flatten(gone) not in text and gone not in page, gone
        assert set(re.findall(r"<table[^>]*>", page)) == {'<table class="stats">'}


# The badge's class

def test_the_badge_class():
    """S5's shade of a deal, no deal's class, and none for every call without a verdict."""
    days = _days()
    shades = {}
    for usual, price in (("5.00", "4.00"), ("5.00", "2.01"), ("5.00", "2.00"), ("10.00", "5.00"), ("5.00", "4.01")):
        found = _verdicts({DEAL: _pair(DEAL, _listed(usual), promotions=[_struct(price)])}, days)[DEAL]
        shades[(usual, price)] = product.badge_class(found)
    assert shades == {("5.00", "4.00"): "deal-1", ("5.00", "2.01"): "deal-1", ("5.00", "2.00"): "deal-2",
                      ("10.00", "5.00"): "deal-3", ("5.00", "4.01"): "no-deal"}
    for call in ("unread_today", "no_sale", "new"):
        (covered, pairs), column_days = _no_verdict_case(call)
        assert product.badge_class(_verdicts(pairs, column_days)[DEAL]) == "none"


# The shell

HEAD = f'<link rel="stylesheet" href="../{STYLESHEET}">\n<script src="../search.js" defer></script>'


def test_the_shell_band_and_footer():
    """The site's look (q36): a product page names its kind on its body, and its band is the brand, the pick link and
    the date line, with no chains' line (the front page's alone); the footer, the credit line and the page's links."""
    covered, pairs = _typical()
    page = _render(covered, pairs)
    assert page.startswith("<!doctype html>") and '<meta name="robots" content="noindex">' in page
    assert ('</head>\n<body class="t-product">\n<header class="band"><div class="wrap">'
            '<a class="brand" href="../index.html"><b>Deal</b> or No Deal</a>'
            '<p class="store"><a id="pick-link" href="../index.html#pick">Pick your store</a></p>'
            f'<p class="dateline">{date_line(DAY)}</p></div></header>\n<main>') in page
    assert CHAINS_LINE not in page
    footer = re.search(r"<footer>(.*?)</footer>", page, re.DOTALL).group(1)
    assert credit(DAY, "12:03") in footer
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', footer)
    assert links == [(f"../{browse_path(covered.title)}", "Browse by first letter"), ("../record.html", "Track record"),
                     ("../method.html", "How this is made")]


def test_the_brand_dresses_its_first_word():
    """The site look's header: the site's name as its wordmark, linking up to the root, its first word in `<b>` (the
    green label); read as text it is the site's name."""
    page = _render(*_typical())
    (brand,) = re.findall(r'<a class="brand" href="\.\./index\.html">(.*?)</a>', page)
    assert brand == "<b>Deal</b> or No Deal"
    assert re.sub(r"<[^>]*>", "", brand) == SITE_NAME


def test_a_product_page_links_the_stylesheet_and_the_one_script():
    """S12 (b), Q2 as store-first.md changes it, and the site's look (q36): the one shared stylesheet and `search.js`,
    the site's one script, end the head, each from the site's root (`../`), and nothing else is loaded; the header's
    pick link up to the picker (`#pick`), which search.js reads the site's root from."""
    for page in (_render(*_typical()), _render(*_largest())):
        assert page.count("<link") == 1 and page.count("<script") == 1 and "javascript:" not in page.lower()
        assert f"</title>\n{HEAD}\n</head>" in page
        assert "<style" not in page and "style=" not in page
        assert '<a id="pick-link" href="../index.html#pick">Pick your store</a>' in page
        assert not re.search(r"\son\w+=", page)                                  # no inline handler either
        rest = page.replace(HEAD, "")
        assert not re.search(r"https?:|//|@import|url\(|<link|<img|<iframe|src=", rest.lower())


def test_page_refuses_a_kind_it_does_not_know():
    """The body's class names the page's kind, one of the shell's seven; any other kind is refused."""
    assert shell.KINDS == ("front", "store", "product", "browse", "method", "record", "basket")
    for kind in shell.KINDS:
        assert f'</head>\n<body class="t-{kind}">\n' in shell.page("T", "<p>M</p>", DAY, "12:03", (), kind)
    for kind in ("", "shop", "t-product", "Product"):
        with pytest.raises(ValueError, match="kind"):
            shell.page("T", "<p>M</p>", DAY, "12:03", (), kind)


def test_the_product_page_and_the_browse_pages_share_one_shell():
    """Task 17's carry: one shell for browse, product and the root pages: the same head, band and footer frame, the
    title and the body's kind aside."""
    covered, pairs = _typical()
    product_page = _render(covered, pairs)
    browse = browse_pages({CODE: covered}, DAY, "12:03")[browse_path(covered.title)]

    def frame(page: str) -> tuple[str, str]:
        """The head and band with the title and the body's kind taken out, and the footer up to its first link."""
        top = re.sub(r'<title>.*?</title>|<body class="t-[a-z]+">', "", page[:page.index("<main>")], flags=re.DOTALL)
        return top, page[page.index("</main>"):page.index("<a ", page.index("<footer>"))]
    assert frame(product_page) == frame(browse)
    assert f"</title>\n{HEAD}\n</head>" in product_page and f"</title>\n{HEAD}\n</head>" in browse
    assert '<body class="t-product">' in product_page and '<body class="t-browse">' in browse

"""The product pages (`shopper.product`; the plan's Task 16): a section per column and P9's row across the nine, on the
shared shell (`shopper.shell`) with the base style (`basket.page.BASE_STYLE`, split from the basket's block, the first
pre-flight's S11). Pairs, points and column-days are built by hand, as tests/test_measures.py builds them; names,
barcodes and programmes are synthetic."""
import hashlib
import re
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from basket.page import BASE_STYLE, BASKET_STYLE, STYLE
from basket.words import too_few
from shopper.columns import BY_KEY, COLUMNS
from shopper.deals import to_agora
from shopper.history import ColumnDay, Covered, Pair, Point
from shopper.measures import gap
from shopper.product import CHAIN_SPAN, MAX_PAGE, page_path, render_product
from shopper.record import Gate
from shopper.search import browse_pages, browse_path
from shopper.words import (ACROSS_HEADING, ALWAYS, ALWAYS_SENTENCE, AT_SOME_STORES, FINE_PRINT, FROM_FIELDS,
                           GAP_HEADING, HISTORY_HEADING, MORNING, NEVER, NOT_LISTED, ODDS_WORDS, PRICE_NOT_READ,
                           SITE_NAME, chart_key, credit, date_line, gap_sentences, last_across, no_odds_yet,
                           price_history, starts_on, unreadable)

DAY = date(2026, 11, 20)
CODE = "2000000000046"
DEAL, SHELI, CITY, MARKET, RAMI = "shufersal-deal", "shufersal-sheli", "carrefour-city", "carrefour-market", "ramilevy"
STORES = 20
SPAN = re.compile(r'<span class="as-listed" lang="he" dir="rtl">.*?</span>', re.DOTALL)
SECTION = re.compile(r'<section data-column="([^"]+)" data-chain="([^"]+)">(.*?)</section>', re.DOTALL)
CELL = re.compile(r'<td data-column="([^"]+)">(.*?)</td>', re.DOTALL)


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


def _listed(price="10.00", first=0, last=90) -> dict[date, str]:
    """`price` on each day from `first` to `last` days back, inclusive (0 is the page's day)."""
    return {back(n): price for n in range(first, last + 1)}


def _pair(column: str, listed: dict[date, str], *, on=(), promotions=(), next_start=None, wide=True) -> Pair:
    """A pair listing `listed`; on promotion on the `on` days; today's promotions `promotions`."""
    points = {}
    for day, price in listed.items():
        today = day == DAY
        points[day] = Point(day=day, listed=Decimal(price), low=Decimal(price), high=Decimal(price) + 1,
                            listing=STORES - 2, wide=wide or not today, on_promotion=day in on,
                            next_start=next_start if today else None, promotions=tuple(promotions) if today else ())
    return Pair(column=column, code=CODE, points=points)


def _covered(names: dict[str, str], size=None, last_wide=None, code=CODE) -> Covered:
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=size, first_covered=back(80),
                   last_wide={column: DAY for column in names} if last_wide is None else last_wide)


def _render(covered, pairs, column_days=None, gates=None, errors=None) -> str:
    return render_product(covered, pairs, _days() if column_days is None else column_days, DAY, "12:03",
                          gates or {}, errors or {})


def _sections(page: str) -> dict[str, str]:
    return {column: body for column, _, body in SECTION.findall(page)}


def _typical() -> tuple[Covered, dict[str, Pair]]:
    """Two columns listing it, one promotion (at Deal, 7.90 a unit, for club members)."""
    deal = _struct("7.90", restrictions=["club"])
    listed = {**_listed("10.90", 31, 90), **_listed("11.90", 0, 30)}
    pairs = {DEAL: _pair(DEAL, listed, on=[back(n) for n in range(40, 46)], promotions=[deal]),
             RAMI: _pair(RAMI, _listed("11.50"))}
    return _covered({DEAL: "גבינה צהובה 200 גרם", RAMI: "גבינה צהובה פרוסה 200 גרם"}, size=(Decimal(200), "gml")), pairs


def _visible(page: str) -> str:
    """The page's text as the site check reads it, with every chain span cut out (Call 11)."""
    return flatten(strip_tags(SPAN.sub(" ", page)))


def _largest() -> tuple[Covered, dict[str, Pair]]:
    """The plan's case: nine columns, three promotions each, a daily price change for 90 days, 40-character names; each
    deal with one realistic set of conditions, a club programme and a minimum spend (round 2's ruling), and three
    week-long runs on promotion in the history."""
    names = {column.key: (f"שם מוצר ארוך {index} " + "א" * 40)[:40] for index, column in enumerate(COLUMNS)}
    club = ["מועדון הלקוחות של הרשת"]
    deals = [_struct("7.90", restrictions=["club"], programmes=club, min_spend="150", promotion_id="100"),
             _struct("4.40", kind="percent_off", low="4.35", high="4.60", restrictions=["club"], programmes=club,
                     min_spend="200", promotion_id="101"),
             _struct(Fraction("10.01") / 3, kind="n_for_m", buy="3", restrictions=["club"], programmes=club,
                     min_spend="300", promotion_id="102")]
    listed = {back(n): ("10.90" if n % 2 else "11.90") for n in range(91)}
    on = [back(n) for first in (5, 30, 60) for n in range(first, first + 7)]
    pairs = {column.key: _pair(column.key, listed, on=on, promotions=deals, next_start=DAY + timedelta(days=9))
             for column in COLUMNS}
    return _covered(names, size=(Decimal(1000), "gml")), pairs


# The page's rules

def test_page_path():
    assert page_path(CODE) == f"p/{CODE}.html"
    assert MAX_PAGE == 60_000


def test_every_always_phrase_and_no_never_phrase():
    page = _render(*_typical())
    text = _visible(page)
    for phrase in ALWAYS:
        assert flatten(phrase) in text, phrase
    assert flatten(ALWAYS_SENTENCE) in text
    for version in (text, flatten(SPAN.sub(" ", page))):
        assert not [phrase for phrase in NEVER if flatten(phrase) in version]
        assert not PRONOUNS.search(version)


def test_a_page_of_a_product_listed_nowhere_today_carries_every_always_phrase():
    """The second pre-flight's S7: a covered product no column lists today still carries the four phrases."""
    covered, pairs = _typical()
    gone = {column: _pair(column, {day: price for day, price in
                                   {back(n): "10.00" for n in range(10, 60)}.items()}) for column in pairs}
    page = _render(covered, gone)
    text = _visible(page)
    for phrase in ALWAYS:
        assert flatten(phrase) in text, phrase
    assert "Listed price ₪" not in page and "Deal price" not in page       # nothing listed today, nothing priced
    for body in _sections(page).values():
        assert NOT_LISTED in body


def test_each_column_section_carries_f10_naming_the_column_and_no_probability():
    """F10 in every section, naming the column (the amendment's "Words"), and, cut out, no odds word and no
    percentage beside P7's own (the spec's check: no probability while the gate is closed; N9: at render time)."""
    covered, pairs = _largest()
    page = _render(covered, pairs)
    sections = _sections(page)
    assert list(sections) == [column.key for column in COLUMNS]
    for column, body in sections.items():
        f10 = no_odds_yet(column)
        assert body.count(f10) == 1, column
        others = [no_odds_yet(other.key) for other in COLUMNS if other.key != column]
        assert not [sentence for sentence in others if sentence in body]
        rest = body.replace(f10, " ")
        rest = re.sub(r"Deal price ₪[\d.]+: [^<]*?\(of the [^)]*\)\.", " ", rest)       # P7's first sentence
        cut = flatten(strip_tags(SPAN.sub(" ", rest)))
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
    """S3: every programme's name beside `targets()`, as published, in the chain's span."""
    deal = _struct(restrictions=["other"], programmes=['<i>תו "זהב"</i>', "FAKE & co"])
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=[deal])})
    assert CHAIN_SPAN.format('&lt;i&gt;תו "זהב"&lt;/i&gt;') in page
    assert CHAIN_SPAN.format("FAKE &amp; co") in page
    assert "<i>" not in page
    deals = re.search(r'<ul class="deals">(.*?)</ul>', page, re.DOTALL).group(1)
    assert (f"some customers only ({CHAIN_SPAN.format('&lt;i&gt;תו \"זהב\"&lt;/i&gt;')}, "
            f"{CHAIN_SPAN.format('FAKE &amp; co')}), {FROM_FIELDS}") in deals


def test_p9_has_nine_cells_in_name_order_without_rank_words():
    """P9: one row, a cell per column in name order whether it lists the product or not, no ranking word."""
    covered, pairs = _typical()
    page = _render(covered, pairs)
    across = re.search(r'<section class="across">(.*?)</section>', page, re.DOTALL).group(1)
    assert f">{ACROSS_HEADING}</h2>" in across
    cells = CELL.findall(across)
    assert [column for column, _ in cells] == [column.key for column in COLUMNS]
    heads = re.findall(r'<th scope="col">([^<]+)</th>', across)
    assert heads == [column.name for column in COLUMNS]
    found = dict(cells)
    assert "Listed price ₪11.90" in found[DEAL] and "Deal price ₪7.90 per unit" in found[DEAL]
    assert f"club members only, {FROM_FIELDS}; {FINE_PRINT}" in found[DEAL] and MORNING in found[DEAL]
    assert "Listed price ₪11.50" in found[RAMI] and "Deal price" not in found[RAMI]
    for column in (SHELI, CITY, MARKET):
        assert found[column] == NOT_LISTED
    text = flatten(strip_tags(across))
    for word in ("cheap", "lowest", "highest", "best", "rank", "save", "more than", "less than", "better", "worse"):
        assert word not in text, word


def test_p9_marks_a_cells_conditions_in_the_sections_words():
    """The controller's ruling 3: the cell's conditions are `targets()` and the minimum spend, the programmes' names
    left to the section; an unread deal is "price not read"; a deal at some stores is not P9's."""
    deals = [_struct("7.90", restrictions=["club", "other"], programmes=["תוכנית"], min_spend="150"),
             _struct(None, valid=False, why="no price in the fields", promotion_id="2"),
             _struct("5.00", wide=False, promotion_id="3")]
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=deals)})
    cell = dict(CELL.findall(re.search(r'<section class="across">(.*?)</section>', page, re.DOTALL).group(1)))[DEAL]
    # fix round 1: each condition with its source and each deal with the fine print, in the section's own words
    # (the design's "Always": the source of every condition; step one: "fine print not read" beside every promotion)
    assert (f"<small>Deal price ₪7.90 per unit; club members only, and some customers only, {FROM_FIELDS}; minimum "
            f"spend ₪150.00, {FROM_FIELDS}; {FINE_PRINT}</small>") in cell
    assert f"<small>{PRICE_NOT_READ}; {FINE_PRINT}</small>" in cell
    assert cell.count(FINE_PRINT) == 2                                  # one for each wide deal
    assert "₪5.00" not in cell and "תוכנית" not in cell                # the programmes' names are the section's
    assert cell.count(MORNING) == 1


def test_a_weighed_deal_is_per_kilogram():
    """P4: a weighed link's deal price is a kilogram's, shown per kilogram, in its section and in P9."""
    deal = _struct("49.90", per="kg", kind="n_for_m", buy="1.5")
    page = _render(_covered({DEAL: "בשר"}), {DEAL: _pair(DEAL, _listed("59.90"), promotions=[deal])})
    assert page.count("Deal price ₪49.90 per kilogram") == 2
    assert "per unit" not in page
    assert page.count("buy 1.5") == 2                               # the section's and P9's


def test_a_promotions_error_says_so_in_each_of_the_chains_sections():
    """P10, question M (g): every section of the chain's columns, both Carrefour columns, and no other chain's."""
    names = {CITY: "שם", MARKET: "שם", RAMI: "שם"}
    pairs = {column: _pair(column, _listed()) for column in names}
    page = _render(_covered(names), pairs, errors={"carrefour": "RewardType 99 not seen in the chain's files"})
    sections = _sections(page)
    for column in (CITY, MARKET):
        assert sections[column].count(unreadable("carrefour")) == 1, column
    assert "could not be read" not in sections[RAMI]
    assert "RewardType" not in page                     # the error's own text is the owner's email, not the page's


def test_a_product_beyond_the_read_says_when_last_listed_across_each_column():
    """Call 10, question G: a product whose pairs lie beyond the 90 days read keeps its page, and each column's
    section says when it was last listed across it; with no history, P8 and the history say nothing."""
    names = {DEAL: "שם", SHELI: "שם אחר", RAMI: "שם"}
    last = {DEAL: date(2026, 6, 1), SHELI: date(2026, 7, 15)}
    page = _render(_covered(names, last_wide=last), {})
    sections = _sections(page)
    assert list(sections) == [RAMI, DEAL, SHELI]                   # name order
    assert last_across(DEAL, date(2026, 6, 1)) in sections[DEAL]
    assert last_across(SHELI, date(2026, 7, 15)) in sections[SHELI]
    assert "last listed across" not in sections[RAMI]              # never wide there: no such day to give
    for column, body in sections.items():
        assert NOT_LISTED in body and no_odds_yet(column) in body
        assert "<svg" not in body and "The listed price" not in body


def test_a_column_not_wide_today_says_when_last_listed_across():
    covered, pairs = _typical()
    narrow = {**pairs, RAMI: _pair(RAMI, _listed("11.50"), wide=False)}
    covered = Covered(code=CODE, title=covered.title, names=covered.names, size=covered.size,
                      first_covered=covered.first_covered, last_wide={DEAL: DAY, RAMI: back(4)})
    sections = _sections(_render(covered, narrow))
    assert last_across(RAMI, back(4)) in sections[RAMI]
    assert "last listed across" not in sections[DEAL]


def test_the_largest_page_is_under_60_kb():
    page = _render(*_largest())
    assert len(page.encode("utf-8")) <= MAX_PAGE, len(page.encode("utf-8"))


def test_the_page_is_the_same_bytes_twice():
    covered, pairs = _largest()
    first = _render(covered, pairs)
    reordered = {column: pairs[column] for column in reversed(list(pairs))}
    names = {column: covered.names[column] for column in reversed(list(covered.names))}
    again = Covered(code=CODE, title=covered.title, names=names, size=covered.size,
                    first_covered=covered.first_covered, last_wide=covered.last_wide)
    days = _days()
    assert first == _render(covered, pairs) == _render(again, reordered, dict(reversed(list(days.items()))))


# The sections

def test_a_section_per_column_listing_it_or_with_its_history_in_name_order():
    covered, pairs = _typical()
    sections = SECTION.findall(_render(covered, pairs))
    assert [(column, slug) for column, slug, _ in sections] == [(RAMI, "ramilevy"), (DEAL, "shufersal")]
    for column, _, body in sections:
        assert f"<h2>{BY_KEY[column].name}</h2>" in body
    # a column with history in the read has its section, whatever names the registry gives
    history = {**pairs, SHELI: _pair(SHELI, _listed("9.00", 10, 40))}
    assert list(_sections(_render(covered, history))) == [RAMI, DEAL, SHELI]


def test_todays_listed_price_and_its_stores_range():
    """P2: today's listed price with the design's phrases beside it, and the stores' range labelled as the stores'
    (never a "listed price", so ALWAYS_SENTENCE stays true)."""
    body = _sections(_render(*_typical()))[DEAL]
    assert ("Listed price ₪11.90, before promotions, as listed in the chain's price files<small>stores ₪11.90 to "
            "₪12.90, 18 of 20 list it</small>") in body


def test_a_hole_day_shows_too_few_files_and_no_listed_price_claim():
    """The second pre-flight's S1: a column-day with files from fewer than half its stores shows `too_few`, its
    prices marked as from too few files, and no listed-price claim; a product it does not list is not said unlisted."""
    covered, pairs = _typical()
    page = _render(covered, pairs, column_days=_days(holes=[(DEAL, DAY), (SHELI, DAY)]))
    sections = _sections(page)
    body = sections[DEAL]
    assert too_few(5, STORES) in body and "₪11.90" in body
    assert "Listed price" not in body
    cells = dict(CELL.findall(re.search(r'<section class="across">(.*?)</section>', page, re.DOTALL).group(1)))
    assert too_few(5, STORES) in cells[DEAL] and "Listed price" not in cells[DEAL]
    assert cells[SHELI] == f"<small>{too_few(5, STORES)}</small>"        # few files: not "not listed today"
    assert "Listed price ₪11.50" in sections[RAMI]
    # a section on a hole whose few files do not list the product says so, never that it is not listed
    named = Covered(code=CODE, title=covered.title, names={**covered.names, SHELI: "שם"}, size=None,
                    first_covered=back(80), last_wide={})
    sheli = _sections(_render(named, {**pairs, SHELI: _pair(SHELI, _listed("9.00", 1, 40))},
                              column_days=_days(holes=[(SHELI, DAY)])))[SHELI]
    assert re.search(r'<p class="today">(.*?)</p>', sheli).group(1) == f'<span class="few">{too_few(5, STORES)}</span>'
    assert NOT_LISTED not in sheli


def test_a_hole_day_says_no_last_listed_across():
    """Fix round 1 (the review's Important 1): on a hole the few files cannot tell whether the product is listed across
    the column today, so the section never says when it last was, whether those files list it or not."""
    covered, pairs = _typical()
    registry = Covered(code=CODE, title=covered.title, names=covered.names, size=covered.size,
                       first_covered=covered.first_covered, last_wide={DEAL: back(1), RAMI: back(1)})
    listed = {day: point for day, point in pairs[DEAL].points.items()}
    listed[DAY] = Point(day=DAY, listed=Decimal("11.90"), low=Decimal("11.90"), high=Decimal("12.90"), listing=5,
                        wide=True, on_promotion=False, next_start=None, promotions=())   # all 5 stores with a file
    holed = _days(holes=[(DEAL, DAY), (RAMI, DAY)])
    gone = {day: point for day, point in pairs[RAMI].points.items() if day != DAY}
    sections = _sections(_render(registry, {DEAL: Pair(column=DEAL, code=CODE, points=listed),
                                            RAMI: Pair(column=RAMI, code=CODE, points=gone)}, column_days=holed))
    for column in (DEAL, RAMI):
        assert too_few(5, STORES) in sections[column]
        assert "last listed across" not in sections[column], column
    assert "stores ₪11.90 to ₪12.90, 5 of 5 list it" in sections[DEAL]
    # on a day with records it is said as before
    assert last_across(RAMI, back(1)) in _sections(_render(registry, {DEAL: pairs[DEAL], RAMI: Pair(
        column=RAMI, code=CODE, points=gone)}))[RAMI]

def test_each_promotion_today_with_its_conditions_from_the_fields():
    """P4, P5, S3: the deal price, buy N, the stores' range for percent off; the restrictions by `targets` from the
    fields with the programmes beside them; the minimum spend; then the fine print, the morning's files and, when the
    promotion is not wide, "at some stores". A promotion that has not started or has ended is not today's."""
    deals = [_struct("10/3", kind="n_for_m", buy="3", restrictions=["club", "chain_card"], min_spend="150"),
             _struct("4.40", kind="percent_off", low="4.35", high="4.60", wide=False, promotion_id="2"),
             _struct("1.00", start=DAY + timedelta(days=2), promotion_id="3"),
             _struct("1.50", end=back(1), promotion_id="4")]
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=deals)})
    items = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="deals">(.*?)</ul>', page, re.DOTALL).group(1))
    assert items == [
        "<b>Deal price ₪3.33 per unit</b>, buy 3<small>club members only, and the chain's card holders only, "
        f"{FROM_FIELDS}; minimum spend ₪150.00, {FROM_FIELDS}; {FINE_PRINT}</small><small>{MORNING}</small>",
        f"<b>Deal price ₪4.40 per unit</b>, stores ₪4.35 to ₪4.60<small>{FINE_PRINT}</small>"
        f"<small>{MORNING}; {AT_SOME_STORES}</small>"]
    assert "PLACEHOLDER-DESCRIPTION" not in page            # the chain's text is not shown


def test_a_promotion_starting_or_ending_today_runs_today():
    """P3: a promotion runs on its start day and on its end day."""
    deals = [_struct("7.00", start=DAY, promotion_id="1"), _struct("8.00", end=DAY, promotion_id="2"),
             _struct("9.00", start=DAY + timedelta(days=1), promotion_id="3")]
    body = _sections(_render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=deals)}))[DEAL]
    assert "Deal price ₪7.00 per unit" in body and "Deal price ₪8.00 per unit" in body
    assert "₪9.00" not in body


def test_every_promotion_says_fine_print_not_read():
    """S12 (b): P5's fine print label beside every promotion, read or not (step one reads no fine print)."""
    deals = [_struct("7.90"), _struct(None, valid=False, why="no kind link", kind=None, promotion_id="2"),
             _struct("5.00", wide=False, promotion_id="3")]
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=deals)})
    items = re.findall(r"<li>(.*?)</li>", re.search(r'<ul class="deals">(.*?)</ul>', page, re.DOTALL).group(1))
    assert len(items) == 3
    for item in items:
        assert FINE_PRINT in item and MORNING in item


def test_an_invalid_deal_shows_price_not_read_only():
    """P4: a deal whose fields do not validate is listed with "price not read", no price beside it, never its why."""
    deal = _struct("25.00", valid=False, why="not below twice the listed price", kind="percent_off", low="24.00",
                   high="26.00")
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), promotions=[deal])})
    body = _sections(page)[DEAL]
    assert f"<b>{PRICE_NOT_READ}</b><small>" in body
    assert "₪25.00" not in page and "₪24.00" not in page and "twice" not in page
    assert GAP_HEADING not in body                           # no P7 for a deal not valid


def test_p7_for_each_valid_wide_deal():
    """P7's three sentences for each valid deal of a wide promotion today, none for one at some stores."""
    deals = [_struct("7.90"), _struct("8.50", promotion_id="2"), _struct("6.00", wide=False, promotion_id="3")]
    listed = {**_listed("10.90", 31, 90), **_listed("11.90", 0, 30)}
    pair = _pair(DEAL, listed, promotions=deals)
    body = _sections(_render(_covered({DEAL: "שם"}), {DEAL: pair}))[DEAL]
    assert body.count(GAP_HEADING) == 1
    p7 = body[body.index(GAP_HEADING):body.index(HISTORY_HEADING)]
    said = [gap_sentences(gap(Fraction(price), pair, _days(), DAY)) for price in ("7.90", "8.50")]
    # round 2's ruling: each deal's first two sentences, then the pair's 30-day changes once, after them
    assert re.findall(r"<p>(.*?)</p>", p7) == [" ".join(said[0][:2]), " ".join(said[1][:2]), said[0][2]]
    assert said[0][2] == said[1][2] and p7.count(said[0][2]) == 1
    assert "Deal price ₪6.00:" not in body


def test_a_promotion_listed_to_start_soon_says_so():
    """F2, Call 22: an item with a wide promotion listed to start within 14 days (the items row's `next_start`)."""
    start = DAY + timedelta(days=9)
    page = _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed(), next_start=start)})
    assert _sections(page)[DEAL].count(starts_on(start)) == 1
    assert "Listed to start" not in _render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, _listed())})


def test_the_history_heading_p8_and_the_listed_price_history_as_text():
    covered, pairs = _typical()
    body = _sections(_render(covered, pairs))[DEAL]
    history = body[body.index(HISTORY_HEADING):]
    assert "On a promotion listed across Shufersal Deal on 6 of the 90 days with records before today" in history
    assert price_history(pairs[DEAL], _days(), DAY) in history
    assert "The listed price rose from ₪10.90 to ₪11.90 on 21 October 2026." in history


def test_the_chart_marks_promotion_days():
    """S12 (b): the window's daily listed prices, holes left as gaps, the days on a wide promotion marked; hidden from
    screen readers, with its two-item key of the site's phrases (the controller's ruling 2)."""
    listed = {**_listed("10.00", 1, 90), DAY: "10.00"}
    del listed[back(50)]                                           # a day not listed: a gap in the line
    pair = _pair(DEAL, listed, on=[back(n) for n in (40, 39, 38, 10)])
    page = _render(_covered({DEAL: "שם"}), {DEAL: pair}, column_days=_days(holes=[(DEAL, back(20))]))
    svg = re.search(r'<svg class="chart"[^>]*>(.*?)</svg>', page, re.DOTALL)
    assert 'aria-hidden="true"' in svg.group(0)
    marks = re.search(r'<path class="on" d="([^"]+)"', svg.group(1)).group(1)
    assert re.findall(r"M(\d+) 56h(\d+)v6h-\d+z", marks) == [("200", "12"), ("320", "4")]   # 40 to 38 back, 10 back
    line = re.search(r'<path d="([^"]+)"', svg.group(1)).group(1)
    assert line.count("M") == 3                                    # broken at the day not listed and at the hole
    key = re.search(r'<p class="key">(.*?)</p>', page, re.DOTALL).group(1)
    assert flatten(strip_tags(key)).strip() == flatten(" ".join(chart_key(DEAL)))


def test_a_product_first_listed_today_has_no_history_to_show():
    """With no day of records before today, no listed-price history and no chart: nothing is drawn from nothing."""
    body = _sections(_render(_covered({DEAL: "שם"}), {DEAL: _pair(DEAL, {DAY: "10.00"})}))[DEAL]
    assert "Listed price ₪10.00" in body and no_odds_yet(DEAL) in body
    assert "<svg" not in body and "The listed price" not in body

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


# The shell and the style

def test_the_shell_band_and_footer():
    covered, pairs = _typical()
    page = _render(covered, pairs)
    assert page.startswith("<!doctype html>") and '<meta name="robots" content="noindex">' in page
    assert (f'<header class="band"><div class="wrap"><a href="../index.html">{SITE_NAME}</a>'
            f'<p class="dateline">{date_line(DAY)}</p></div></header>') in page
    footer = re.search(r"<footer>(.*?)</footer>", page, re.DOTALL).group(1)
    assert credit(DAY, "12:03") in footer
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', footer)
    assert links == [(f"../{browse_path(covered.title)}", "Browse by first letter"), ("../record.html", "Track record"),
                     ("../method.html", "How this is made")]


def test_no_script_on_a_product_page():
    """S12 (b), Q2: `search.js` is the site's one script, and product pages carry none."""
    for page in (_render(*_typical()), _render(*_largest())):
        assert "<script" not in page.lower() and "javascript:" not in page.lower()
        assert not re.search(r"\son\w+=", page)                                  # no inline handler either
        assert not re.search(r"https?:|//|@import|url\(|<link|<img|<iframe|src=", page.lower())


def test_the_product_page_and_the_browse_pages_share_one_shell():
    """Task 17's carry: one shell for browse, product and the root pages: the same head, band and footer frame."""
    covered, pairs = _typical()
    product = _render(covered, pairs)
    browse = browse_pages({CODE: covered}, DAY, "12:03")[browse_path(covered.title)]

    def frame(page: str) -> tuple[str, str]:
        """The head and band with the title and style taken out, and the footer up to its first link."""
        head = re.sub(r"<title>.*?</title>|<style>.*?</style>", "", page[:page.index("<main>")], flags=re.DOTALL)
        return head, page[page.index("</main>"):page.index("<a ", page.index("<footer>"))]
    assert frame(product) == frame(browse)
    for page in (product, browse):
        assert f"<style>{BASE_STYLE}" in page and BASKET_STYLE not in page


def test_the_style_split_keeps_the_baskets_block_byte_for_byte():
    """The first pre-flight's S11: `STYLE` is the block the basket's pages carried before the split (its SHA-256 then),
    cut into the base rules and the basket's own, each a whole set of rules."""
    assert hashlib.sha256(STYLE.encode()).hexdigest() == (
        "8179d0e4d8567b8c1426100ab5f171aee6dd502f2d84fc87ae5848f83ce768b4")
    for part in (BASE_STYLE, BASKET_STYLE):
        assert part.count("{") == part.count("}")
    assert len(BASE_STYLE) + len(BASKET_STYLE) == len(STYLE) + len("@media (max-width: 37.5rem) {\n}\n")
    for rule in ("--bg:", "@media (prefers-color-scheme: dark)", ".band {", "main > section {", "th, td {", "footer {"):
        assert rule in BASE_STYLE and rule not in BASKET_STYLE, rule
    for rule in (".tiles {", "ol.bars li {", "table.prices {", "table.basket {", "ol.rules li {", "details {"):
        assert rule in BASKET_STYLE and rule not in BASE_STYLE, rule

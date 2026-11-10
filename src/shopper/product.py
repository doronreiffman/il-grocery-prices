"""The product pages: one per covered product, `p/<barcode>.html`, with a section per column and P9's row across the
nine (docs/shopper-site.md, "What a visitor sees" 2, P2 to P10, F2, F10 and "Words", with "Changed after the survey",
S1 and "The column"; the plan's Task 16, its questions A, G and M (g), the second pre-flight's S1, S7, S11 and S12, and
the controller's rulings on Task 16's words). Every word is `shopper.words`' or `basket.words`'; every chain-supplied
text (a product's names, a programme's) is escaped inside `CHAIN_SPAN`, so the site check reads it for markup only.

The page, top to bottom, on the shared shell (`shopper.shell`: the band with the site's name and the date line, the
footer with the credit line and the links to the product's browse page, the record and the method page). The tab's
title is the barcode, never a chain's name, which no span can hold there. Then the title, the longest name; each
distinct name once, with the columns that list it so (`as_listed`); the barcode and the size the chains state; and
ALWAYS_SENTENCE, which carries the four ALWAYS phrases whatever the product's day (S7).

A section per column that lists the product or has its history, in name order (`shopper.columns.COLUMNS`), marked with
its column and its chain (`data-column`, `data-chain`), headed with the column's name:

- P10 first: when the chain's promotions could not be read today (`promotions_errors`, by chain), `unreadable(slug)`,
  on every section of the chain's columns (both Carrefour columns).
- Today (P2). On a day with a record at the column: the listed price with "before promotions" and "as listed in the
  chain's price files", the stores' range beneath it labelled as the stores' (`basket.words.range_note`), never as a
  listed price; "not listed today" when the column's files do not list it. On a hole (S1: files from fewer than half
  the column's stores) `basket.words.too_few` comes first and no listed price is claimed: the median is shown as from
  too few files, and a product those files do not list is not said to be unlisted. On a day with records, when the
  product is not listed across the column, the last day it was (`last_across`, the registry's), if there is one; a
  hole says nothing of it, since its few files cannot tell whether today is across.
- Each promotion running today (P3: started on or before the day, ending on or after it, by the items table's dates),
  rebuilt by `shopper.deals.deal_from_row` (S11): its deal price, a unit's or a kilogram's (P4), "buy N" for "N for ₪M",
  the stores' range for percent off; or "price not read" alone when the deal is not valid, never a price beside it
  (P4); then its conditions, each with its source (P5): the restrictions by `targets` with every programme's name in
  its span, the minimum spend, and "fine print not read" always (step one reads no fine print); then "as listed in the
  morning's files", and "at some stores" when fewer than half the column's counted stores carry it, or on a hole
  morning, whose few files cannot tell whether a promotion is listed across the column (deploy prep: every promotion
  of a hole is "at some stores"). The chain's own description is not shown.
- `starts_on` when the items row lists a wide promotion starting in the next 14 days (F2, Call 22).
- "The deal against its listed prices": P7's first two sentences for each valid deal of a wide promotion today, then
  its third, the pair's changes in the past 30 days, once, since it is the same for every deal (Task 16, round 2); none
  on a hole morning.
- "How often it goes on promotion": P8's sentences, F10's sentence naming the column (the gate is closed in step one:
  an open gate stops the page, since step one has no odds line), the listed-price history as text
  (`price_history`, the changes of the 90-day window, the newest five with the count of the rest) and a chart of it.

The chart, hidden from screen readers (the text says the same): the listed price as shown on each counted day of the
90-day window (P6: a record at the column and a listed price), four units a day, so a hole or a day not listed is a
gap in the line, never filled; the window's lowest and highest shown prices at the right; the days on a promotion
listed across the column marked beneath (P8's days: `shopper.measures.promotion_points`); and a key of the two marks.

P9's row: "Today at each column, in name order", a cell for each of the nine columns, listing the product or not: its
listed price today or "not listed today" (on a hole, the price under `too_few`, or `too_few` alone), and the deal price
of each wide promotion today, none on a hole ("price not read" when not valid) with its conditions in the section's
words, each with its source (the programmes' names left to the section), and "fine print not read". Sorted by name,
never by price; no ranking word.

No script. The page is a pure function of its inputs: the same bytes whatever order the mappings come in.
"""
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from basket.record import money
from basket.units import Size
from basket.words import range_note, size_text, too_few
from shopper.columns import BY_KEY, COLUMNS
from shopper.deals import Deal, deal_from_row
from shopper.history import READ_DAYS, ColumnDay, Covered, Pair, Point, counted
from shopper.measures import gap, promotion_points, whole
from shopper.record import Gate
from shopper.search import CHAIN_SPAN, browse_path
from shopper.shell import page, text
from shopper.words import (ACROSS_HEADING, ALWAYS_SENTENCE, AT_SOME_STORES, BARCODE, BROWSE_LINK, FINE_PRINT,
                           FROM_FIELDS, GAP_HEADING, HISTORY_HEADING, METHOD_TITLE, MORNING, NOT_LISTED,
                           PRICE_NOT_READ, RECORD_TITLE, SITE_NAME, as_listed, buy, chart_key, deal_price,
                           gap_sentences, history_sentences, last_across, listed_price, minimum_spend, no_odds_yet,
                           price_history, starts_on, stores_range, targets, unreadable)

__all__ = ["CHAIN_SPAN", "MAX_PAGE", "field_conditions", "page_path", "render_product", "running_today"]

MAX_PAGE = 60_000      # bytes a product page may hold (the design's check)
DAY_WIDTH = 4          # the chart's units a day
TOP, BOTTOM = 6, 50    # the chart's line between these heights
MARK = 56              # where the promotion days are marked
PRODUCT_STYLE = """
.names { list-style: none; padding: 0; margin: 0 0 var(--s3); }
main > section h3 { font-size: 1rem; margin: var(--s4) 0 var(--s2); }
.today small, .deals small { display: block; color: var(--text-3); font-size: .8125rem; }
.few, .warn { color: var(--warn); }
.deals { padding-left: 1.25rem; margin: 0 0 var(--s3); }
.deals li { margin: 0 0 var(--s2); }
.chart { display: block; width: 100%; max-width: 32rem; height: auto; margin: var(--s2) 0; }
.chart path { fill: none; stroke: var(--accent); stroke-width: 1.5; }
.chart .on { fill: var(--warn); stroke: none; }
.chart text { fill: var(--text-3); font-size: 9px; }
.key { color: var(--text-3); font-size: .8125rem; }
.key i { display: inline-block; width: .75rem; height: .375rem; margin-right: .25rem; vertical-align: middle; }
.key .line { background: var(--accent); }
.key .on { background: var(--warn); margin-left: .75rem; }
table.across { min-width: 60rem; }
"""


def page_path(code: str) -> str:
    """The product's page in the site: p/<barcode>.html."""
    return f"p/{code}.html"


def _span(value: str) -> str:
    return CHAIN_SPAN.format(text(value))


def running_today(point: Point | None, day: date) -> list[dict]:
    """The point's promotions running on `day` (P3: started on or before it and ending on or after it); the front
    page's rows read them so too."""
    if point is None:
        return []
    return [struct for struct in point.promotions if struct["start"] <= day <= struct["end"]]


def _valid(struct: Mapping) -> Deal | None:
    """The promotion's deal (S11) when its price is read and valid, else None."""
    deal = deal_from_row(struct)
    return deal if deal.valid and deal.price is not None else None


def field_conditions(struct: Mapping, programmes: bool = True) -> list[str]:
    """A promotion's conditions from the fields, as HTML, each with its source (P5, S3), from a struct's (or a front
    page row's) `restrictions`, `programmes` and `min_spend`; every programme's name in the chain's span, unless
    `programmes` is False (P9's cells leave the names to the section)."""
    found = []
    phrase = targets(struct["restrictions"])
    names = struct["programmes"] if programmes else []
    if phrase or names:
        programmes = f"({', '.join(_span(name) for name in names)})" if names else ""
        found.append(f"{' '.join(part for part in (text(phrase), programmes) if part)}, {text(FROM_FIELDS)}")
    if struct["min_spend"] is not None:
        found.append(f"{text(minimum_spend(struct['min_spend']))}, {text(FROM_FIELDS)}")
    return found


def _promotion(struct: Mapping, record: bool) -> str:
    """One promotion today in its section (the module's docstring); `record` False on a hole morning, when every one is
    "at some stores"."""
    deal = _valid(struct)
    if deal is None:
        head = f"<b>{text(PRICE_NOT_READ)}</b>"
    else:
        head = f"<b>{text(deal_price(deal.price, deal.per))}</b>"
        if deal.buy != 1:
            head += f", {text(buy(deal.buy))}"
        if deal.low is not None and deal.high is not None:
            head += f", {text(stores_range(deal.low, deal.high))}"
    conditions = "; ".join([*field_conditions(struct), text(FINE_PRINT)])
    across = struct["wide"] and record
    listed = text(MORNING) if across else f"{text(MORNING)}; {text(AT_SOME_STORES)}"
    return f"<li>{head}<small>{conditions}</small><small>{listed}</small></li>"


def _today(key: str, today: ColumnDay, point: Point | None, covered: Covered) -> str:
    """The section's today: the listed price and its range, a hole's too few files, or not listed; and, on a day
    with records when the product is not listed across the column, the last day it was."""
    stores = "" if point is None else (
        f"<small>{text(range_note(money(point.low), money(point.high), point.listing, today.with_file))}</small>")
    if today.record:
        shown = text(NOT_LISTED) if point is None else text(listed_price(point.listed)) + stores
    else:
        few = f'<span class="few">{text(too_few(today.with_file, today.included))}</span>'
        shown = few if point is None else f"{few} ₪{money(point.listed)}{stores}"
    last = covered.last_wide.get(key)
    if today.record and not (point is not None and point.wide) and last is not None:   # a hole cannot tell
        shown += f"<small>{text(last_across(key, last))}</small>"
    return f'<p class="today">{shown}</p>'


def _x(day: date, first: date) -> int:
    return (day - first).days * DAY_WIDTH


def _runs(days: Sequence[date]) -> list[tuple[date, date]]:
    """Consecutive days, in order, as (first, last)."""
    found: list[tuple[date, date]] = []
    for seen in days:
        if found and found[-1][1] + timedelta(days=1) == seen:
            found[-1] = (found[-1][0], seen)
        else:
            found.append((seen, seen))
    return found


def _chart(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date, key: str) -> str:
    """The window's daily listed prices as shown, the promotion days marked, and the key (the module's docstring);
    "" with no day counted."""
    points = counted(pair, column_days, day, READ_DAYS)
    if not points:
        return ""
    first = day - timedelta(days=READ_DAYS)
    shown = {point.day: Decimal(money(point.listed)) for point in points}
    low, high = min(shown.values()), max(shown.values())

    def height(price: Decimal) -> int:
        if high == low:
            return (TOP + BOTTOM) // 2
        return TOP + whole(Fraction(high - price) / Fraction(high - low) * (BOTTOM - TOP))

    heights = {price: height(price) for price in set(shown.values())}    # each shown price's, worked once
    line = []
    for start, end in _runs([point.day for point in points]):
        level = heights[shown[start]]
        line.append(f"M{_x(start, first)} {level}")
        for each in (start + timedelta(days=n) for n in range(1, (end - start).days + 1)):
            if heights[shown[each]] != level:
                level = heights[shown[each]]
                line.append(f"H{_x(each, first)}V{level}")
        line.append(f"H{_x(end, first) + DAY_WIDTH}")
    on = [point.day for point in promotion_points(pair, column_days, day) if point.on_promotion]
    widths = [(_x(start, first), _x(end, first) - _x(start, first) + DAY_WIDTH) for start, end in _runs(on)]
    marks = "".join(f"M{x} {MARK}h{width}v6h-{width}z" for x, width in widths)
    marked = f'<path class="on" d="{marks}"/>' if marks else ""
    right = READ_DAYS * DAY_WIDTH + 4
    labels = [(heights[high], high)] if high == low else [(TOP, high), (BOTTOM, low)]
    prices = "".join(f'<text x="{right}" y="{y + 3}">₪{price}</text>' for y, price in labels)
    line_key, on_key = chart_key(key)
    return (f'<svg class="chart" viewBox="0 0 {right + 40} 64" aria-hidden="true" focusable="false">'
            f'<path d="{"".join(line)}"/>{marked}{prices}</svg>'
            f'<p class="key"><i class="line"></i>{text(line_key)} <i class="on"></i>{text(on_key)}</p>')


def _section(key: str, covered: Covered, pair: Pair | None, column_days: Mapping[tuple[str, date], ColumnDay],
             day: date, promotions_errors: Mapping[str, str]) -> str:
    """A column's section (the module's docstring)."""
    column = BY_KEY[key]
    point = None if pair is None else pair.points.get(day)
    parts = [f"<h2>{text(column.name)}</h2>"]
    if column.slug in promotions_errors:
        parts.append(f'<p class="warn">{text(unreadable(column.slug))}</p>')
    today = column_days[(key, day)]
    parts.append(_today(key, today, point, covered))
    running = running_today(point, day)
    if running:
        parts.append(f'<ul class="deals">{"".join(_promotion(struct, today.record) for struct in running)}</ul>')
    if point is not None and point.next_start is not None:
        parts.append(f"<p>{text(starts_on(point.next_start))}</p>")
    measured = []
    for struct in running:
        deal = _valid(struct)
        if struct["wide"] and today.record and deal is not None:
            found = gap(deal.price, pair, column_days, day)
            if found is not None:
                measured.append(gap_sentences(found))
    if measured:      # each deal's first two sentences, then the pair's changes once: the same for every deal
        parts += [f"<h3>{text(GAP_HEADING)}</h3>", *(f"<p>{text(' '.join(said[:2]))}</p>" for said in measured),
                  f"<p>{text(measured[0][2])}</p>"]
    parts.append(f"<h3>{text(HISTORY_HEADING)}</h3>")
    history = () if pair is None else history_sentences(pair, column_days, day)
    if history:
        parts.append(f"<p>{text(' '.join(history))}</p>")
    parts.append(f"<p>{text(no_odds_yet(key))}</p>")
    if pair is not None:
        said = price_history(pair, column_days, day)
        if said is not None:
            parts.append(f"<p>{text(said)}</p>")
        parts.append(_chart(pair, column_days, day, key))
    return f'<section data-column="{key}" data-chain="{column.slug}">{"".join(parts)}</section>'


def _cell(key: str, pair: Pair | None, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> str:
    """P9's cell for a column (the module's docstring)."""
    today = column_days[(key, day)]
    point = None if pair is None else pair.points.get(day)
    if today.record:
        if point is None:
            return text(NOT_LISTED)
        shown = text(listed_price(point.listed))
    else:
        few = f"<small>{text(too_few(today.with_file, today.included))}</small>"
        if point is None:
            return few
        shown = f"₪{money(point.listed)}{few}"
    deals = []
    for struct in running_today(point, day):
        if not (struct["wide"] and today.record):           # a hole lists no promotion across the column
            continue
        deal = _valid(struct)
        said = PRICE_NOT_READ if deal is None else deal_price(deal.price, deal.per)
        if deal is not None and deal.buy != 1:
            said += f", {buy(deal.buy)}"
        conditions = field_conditions(struct, programmes=False)       # the section's words, each with its source
        deals.append(f"<small>{'; '.join([text(said), *conditions, text(FINE_PRINT)])}</small>")
    if deals:
        deals.append(f"<small>{text(MORNING)}</small>")
    return shown + "".join(deals)


def _across(pairs: Mapping[str, Pair], column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> str:
    """P9's row: a cell for each of the nine columns, in name order."""
    heads = "".join(f'<th scope="col">{text(column.name)}</th>' for column in COLUMNS)
    cells = "".join(f'<td data-column="{column.key}">{_cell(column.key, pairs.get(column.key), column_days, day)}</td>'
                    for column in COLUMNS)
    return (f'<section class="across"><h2 id="across">{text(ACROSS_HEADING)}</h2>'
            '<div class="table" tabindex="0" role="region" aria-labelledby="across"><table class="across">'
            f"<thead><tr>{heads}</tr></thead><tbody><tr>{cells}</tr></tbody></table></div></section>")


def _names(covered: Covered) -> str:
    """Each distinct name once, as published, with the columns that list it so, by its first column's name."""
    by_name: dict[str, list[str]] = {}
    for column in COLUMNS:
        if column.key in covered.names:
            by_name.setdefault(covered.names[column.key], []).append(column.key)
    items = "".join(f"<li>{_span(name)} {text(as_listed(columns))}</li>" for name, columns in by_name.items())
    return f'<ul class="names">{items}</ul>'


def render_product(covered: Covered, pairs: Mapping[str, Pair], column_days: Mapping[tuple[str, date], ColumnDay],
                   day: date, collected_by: str, gates: Mapping[str, Gate],
                   promotions_errors: Mapping[str, str]) -> str:
    """The product's page for `day` (the module's docstring): `pairs` and `gates` by column, `promotions_errors` by
    chain; `column_days` holds every column's day. ValueError for an open gate: step one has no odds line."""
    opened = sorted(key for key, found in gates.items() if found.open)
    if opened:
        raise ValueError(f"the gate is open at {', '.join(opened)}, and step one shows no odds")
    keys = [column.key for column in COLUMNS if column.key in covered.names or column.key in pairs]
    size = "" if covered.size is None else f" · {text(size_text(Size(*covered.size)))}"
    main = "\n".join([f"<h1>{_span(covered.title)}</h1>", _names(covered),
                      f"<p>{text(BARCODE)} {text(covered.code)}{size}</p>",
                      f'<p class="lede">{text(ALWAYS_SENTENCE)}</p>',
                      *(_section(key, covered, pairs.get(key), column_days, day, promotions_errors) for key in keys),
                      _across(pairs, column_days, day)])
    links = ((BROWSE_LINK, browse_path(covered.title)), (RECORD_TITLE, "record.html"), (METHOD_TITLE, "method.html"))
    return page(f"{covered.code} - {SITE_NAME}", main, day, collected_by, links, PRODUCT_STYLE)

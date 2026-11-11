"""The product pages: one per covered product, `p/<barcode>.html`, a part per store type (a column) answering "Deal" or
"No deal" against what the product usually costs there, sales included (docs/store-first.md, "What a visitor sees" 5
to 8, "The chart", "Words" and "Changes to the shopper-site design"; docs/shopper-site.md's P2 to P5, P10, F2, F10 and
Call 10, as kept; the store-first plan's Task 3 and its "Where the design leaves room"; before it, the shopper plan's
Task 16, its questions A, G and M (g), and the second pre-flight's S1, S7, S11 and S12). Every word is
`shopper.words`' or `basket.words`'; every chain-supplied text (a product's names, a programme's) is escaped inside
`CHAIN_SPAN`, so the site check reads it for markup only. The verdicts are `shopper.verdict`'s, one per section, worked
by the build's one pass and handed in.

The page, top to bottom, on the shared shell (`shopper.shell`: the band with the site's name and the date line, the
footer with the credit line and the links to the product's browse page, the record and the method page). The tab's
title is the barcode, never a chain's name, which no span can hold there. Then:

- the title, the longest name; each distinct name once, with the columns that list it so (`as_listed`); the barcode
  and the size the chains state;
- the badge row: its heading, `<h2 class="elsewhere" hidden>` "Elsewhere today", then `<nav class="badges">`, a badge
  `<a data-column="<key>" href="#c-<key>">` per store type with a point today (on a hole too: its few files list it),
  each the store type's name and its verdict, or its no-verdict line, in `short_badge`'s words; the deals and no deals
  first, by saving as shown, largest first, a tie in COLUMNS order, then the rest in COLUMNS order. The row is there,
  empty, when nothing sells the product today;
- a section per column that lists the product or has its history, in name order (`shopper.columns.COLUMNS`),
  `<section data-column="<key>" id="c-<key>" data-chain="<chain>">`, headed with the column's name (the parts below);
- ALWAYS_SENTENCE, once, which carries the four ALWAYS phrases whatever the product's day (S7).

A section, in this order:

- P10, when the chain's promotions could not be read today (`promotions_errors`, by chain): `unreadable(slug)`, on
  every section of the chain's columns (both Carrefour columns).
- The verdict: a deal or a no deal is a badge, `<p class="badge <class>">` (`badge_class`: S5's shade, "no-deal"'s
  neutral grey), in `badge`'s words, which name the store type ("At Carrefour Market: DEAL · ₪1.90 off"), then the
  reason (`reason`, naming its days tracked, S8). Any other call has no badge and a plain line: `basket.words.too_few`
  on a hole (prices from files of fewer than half the column's stores; the verdict's first call, so a product the few
  files miss is never said not sold), `not_sold` with the last day the registry saw it listed across the column
  (`last_wide`, Call 10's), or NO_VERDICT's line.
- The conditions of the promotion the verdict judges (S3's), in shopper words (`conditions`), when it has any.
- The coming sale (F2, Call 22: the items row lists a wide promotion starting in the next 14 days), `coming_sale`;
  none on a hole morning, whose few files cannot tell whether a promotion is listed across the column (deploy prep).
- The chart (`shopper.chart.render_chart`, from the verdict), then "Last this low" (`last_low`, S6) and "How often on
  sale" (`how_often`, S7), each when it has something to say.
- The fold-out, `<details>` "How this is worked out", holding in this order:
  - today's listed price (P2), with "before promotions" and "as listed in the chain's price files" (its definition),
    the stores' range beneath it labelled as the stores' (`basket.words.range_note`), never as a listed price; on a
    hole the median as from too few files (`too_few`), never a listed-price claim. Nothing when the product has no
    point today: the verdict's line says so. On a day with records, when the product is listed but not across the
    column, the last day it was (`last_across`); a hole says nothing of it, since its few files cannot tell;
  - each promotion running today (P3: started on or before the day, ending on or after it, by the items table's
    dates), rebuilt by `shopper.deals.deal_from_row` (S11): its deal price, a unit's or a kilogram's (P4), "buy N" for
    "N for ₪M", the stores' range for percent off; or "price not read" alone when the deal is not valid, never a price
    beside it (P4); then its conditions, each with its source (P5): the restrictions by `targets` with every
    programme's name in its span, the minimum spend, and "fine print not read" always (step one reads no fine print);
    then "as listed in the morning's files", and "at some stores" when fewer than half the column's counted stores
    carry it, or on a hole morning (deploy prep: every promotion of a hole is "at some stores"). The chain's own
    description is not shown;
  - F10's sentence naming the column (the gate is closed in step one: an open gate stops the page, since step one has
    no odds line).

Nothing is hidden without the script (the plan): the only `hidden` attribute is the row's heading's, and the style
hides only what has one (`[hidden]{display:none!important}`, BADGE_STYLE's), sets no `display` on a section, a badge or
the heading, and so cannot show a part the script hid. `search.js` reads this markup (its header comment), and every
fact stays in the HTML with the script blocked. BADGE_STYLE holds the shades, light and dark, for the product and the
store pages; PRODUCT_STYLE is it and the product page's own rules, the chart's strokes among them (its SVG draws none).

The shell (`shopper.shell`) loads the site's one script, `search.js`, as on every page; no fact needs it. The page is
a pure function of its inputs: the same bytes whatever order the mappings come in.
"""
from collections.abc import Mapping
from datetime import date

from basket.record import money
from basket.units import Size
from basket.words import range_note, size_text, too_few
from shopper.chart import render_chart
from shopper.columns import BY_KEY, COLUMNS
from shopper.deals import Deal, deal_from_row
from shopper.history import ColumnDay, Covered, Pair, Point
from shopper.record import Gate
from shopper.search import CHAIN_SPAN, browse_path
from shopper.shell import page, text
from shopper.verdict import Verdict
from shopper.words import (ALWAYS_SENTENCE, AT_SOME_STORES, BARCODE, BROWSE_LINK, ELSEWHERE, FINE_PRINT, FROM_FIELDS,
                           METHOD_TITLE, MORNING, NO_VERDICT, PRICE_NOT_READ, RECORD_TITLE, SITE_NAME, WORKED_OUT,
                           as_listed, badge, buy, coming_sale, conditions, deal_price, how_often, last_across, last_low,
                           listed_price, minimum_spend, no_odds_yet, not_sold, reason, short_badge, stores_range,
                           targets, unreadable)

__all__ = ["BADGE_STYLE", "CHAIN_SPAN", "MAX_PAGE", "badge_class", "field_conditions", "page_path", "render_product",
           "running_today", "section_keys"]

MAX_PAGE = 60_000      # bytes a product page may hold (the design's check)
# S5's shades, light and dark: each badge's text at least 4.5:1 on its background (tests/test_product.py)
BADGE_STYLE = """
:root {
  --deal-1-bg: #d7f2df; --deal-1-text: #0f4d27; --deal-2-bg: #2a7f4b; --deal-2-text: #ffffff;
  --deal-3-bg: #14532d; --deal-3-text: #ffffff; --no-deal-bg: #e4e6e5; --no-deal-text: #2b2e2c;
  --none-bg: #ffffff; --none-text: #3f4a43;
}
@media (prefers-color-scheme: dark) {
  :root {
    --deal-1-bg: #1b3d29; --deal-1-text: #c3f2d4; --deal-2-bg: #2f7d4f; --deal-2-text: #ffffff;
    --deal-3-bg: #7ee0a5; --deal-3-text: #052e16; --no-deal-bg: #393c3a; --no-deal-text: #eceeed;
    --none-bg: #151a17; --none-text: #b7c0ba;
  }
}
[hidden]{display:none!important}
.badge { width: fit-content; max-width: 100%; padding: var(--s1) var(--s3); border: 1px solid transparent;
         border-radius: 999px; font-weight: 650; font-variant-numeric: tabular-nums; text-decoration: none; }
.badge.deal-1 { background: var(--deal-1-bg); color: var(--deal-1-text); }
.badge.deal-2 { background: var(--deal-2-bg); color: var(--deal-2-text); }
.badge.deal-3 { background: var(--deal-3-bg); color: var(--deal-3-text); }
.badge.no-deal { background: var(--no-deal-bg); color: var(--no-deal-text); }
.badge.none { background: var(--none-bg); color: var(--none-text); border-color: var(--border); font-weight: 500; }
"""
PRODUCT_STYLE = BADGE_STYLE + """\
.names { list-style: none; padding: 0; margin: 0 0 var(--s3); }
nav.badges { display: flex; flex-wrap: wrap; gap: var(--s2); margin: 0 0 var(--s4); }
.reason { color: var(--text-2); }
.today small, .deals small { display: block; color: var(--text-3); font-size: .8125rem; }
.few, .warn { color: var(--warn); }
.deals { padding-left: 1.25rem; margin: 0 0 var(--s3); }
.deals li { margin: 0 0 var(--s2); }
details { margin: var(--s4) 0 0; }
summary { cursor: pointer; color: var(--accent); margin: 0 0 var(--s3); }
.chart { display: block; max-width: 100%; height: auto; margin: var(--s3) 0 var(--s1); }
.chart path { fill: none; stroke-width: 2; }
.chart .listed { stroke: var(--bar); }
.chart .sale { stroke: var(--accent); stroke-width: 3; }
.chart .unread { stroke: var(--accent); stroke-width: 5; stroke-opacity: .5; }
.chart line.today { stroke: var(--text-2); stroke-width: 1.5; stroke-dasharray: 4 3; }
.chart circle.today { fill: var(--text-2); }
.chart text { fill: var(--text-3); }
.key { color: var(--text-3); font-size: .8125rem; }
.key i { display: inline-block; width: .75rem; height: .375rem; margin-right: .25rem; vertical-align: middle; }
.key .listed { background: var(--bar); }
.key .sale { background: var(--accent); }
.key .unread { background: var(--accent); opacity: .5; }
"""


def page_path(code: str) -> str:
    """The product's page in the site: p/<barcode>.html."""
    return f"p/{code}.html"


def section_keys(covered: Covered, pairs: Mapping[str, Pair]) -> list[str]:
    """The columns a product page has a section for, in name order: those whose registry names the product, and those
    with its history in the days read (the build works a verdict for each)."""
    return [column.key for column in COLUMNS if column.key in covered.names or column.key in pairs]


def badge_class(found: Verdict) -> str:
    """A badge's shade (S5): a deal's band, "no-deal"'s grey, or "none" for a call without a verdict."""
    if found.call == "deal":
        return found.shade
    if found.call == "no_deal":
        return "no-deal"
    return "none"


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


def field_conditions(struct: Mapping) -> list[str]:
    """A promotion's conditions from the fields, as HTML, each with its source (P5, S3), from a struct's (or a front
    page row's) `restrictions`, `programmes` and `min_spend`; every programme's name in the chain's span."""
    found = []
    phrase = targets(struct["restrictions"])
    names = struct["programmes"]
    if phrase or names:
        programmes = f"({', '.join(_span(name) for name in names)})" if names else ""
        found.append(f"{' '.join(part for part in (text(phrase), programmes) if part)}, {text(FROM_FIELDS)}")
    if struct["min_spend"] is not None:
        found.append(f"{text(minimum_spend(struct['min_spend']))}, {text(FROM_FIELDS)}")
    return found


def _promotion(struct: Mapping, record: bool) -> str:
    """One promotion today in its fold-out (the module's docstring); `record` False on a hole morning, when every one
    is "at some stores"."""
    deal = _valid(struct)
    if deal is None:
        head = f"<b>{text(PRICE_NOT_READ)}</b>"
    else:
        head = f"<b>{text(deal_price(deal.price, deal.per))}</b>"
        if deal.buy != 1:
            head += f", {text(buy(deal.buy))}"
        if deal.low is not None and deal.high is not None:
            head += f", {text(stores_range(deal.low, deal.high))}"
    labels = "; ".join([*field_conditions(struct), text(FINE_PRINT)])
    across = struct["wide"] and record
    listed = text(MORNING) if across else f"{text(MORNING)}; {text(AT_SOME_STORES)}"
    return f"<li>{head}<small>{labels}</small><small>{listed}</small></li>"


def _today(key: str, today: ColumnDay, point: Point | None, covered: Covered) -> str:
    """The fold-out's today: the listed price and its range, or a hole's median from too few files; and, on a day with
    records when the product is listed but not across the column, the last day it was; "" with no point today."""
    if point is None:
        return ""                      # the verdict's line says it: not sold today, or a hole's too few files
    stores = f"<small>{text(range_note(money(point.low), money(point.high), point.listing, today.with_file))}</small>"
    if today.record:
        shown = text(listed_price(point.listed)) + stores
    else:
        few = f'<span class="few">{text(too_few(today.with_file, today.included))}</span>'
        shown = f"{few} ₪{money(point.listed)}{stores}"
    last = covered.last_wide.get(key)
    if today.record and not point.wide and last is not None:   # a hole cannot tell
        shown += f"<small>{text(last_across(key, last))}</small>"
    return f'<p class="today">{shown}</p>'


def _worked_out(key: str, today: ColumnDay, point: Point | None, covered: Covered, day: date) -> str:
    """The fold-out "How this is worked out" (the module's docstring)."""
    parts = [_today(key, today, point, covered)]
    running = running_today(point, day)
    if running:
        parts.append(f'<ul class="deals">{"".join(_promotion(struct, today.record) for struct in running)}</ul>')
    parts.append(f"<p>{text(no_odds_yet(key))}</p>")
    return f"<details><summary>{text(WORKED_OUT)}</summary>{''.join(parts)}</details>"


def _said(key: str, found: Verdict, today: ColumnDay, covered: Covered) -> list[str]:
    """The verdict: a badge and the reason; or, with no verdict, its plain line (the module's docstring)."""
    if found.call in ("deal", "no_deal"):
        return [f'<p class="badge {badge_class(found)}">{text(badge(found))}</p>',
                f'<p class="reason">{text(reason(found))}</p>']
    if found.call == "too_few":
        return [f'<p class="few">{text(too_few(today.with_file, today.included))}</p>']
    if found.call == "not_sold":
        return [f'<p class="not-sold">{text(not_sold(key, covered.last_wide.get(key)))}</p>']
    return [f"<p>{text(NO_VERDICT[found.call])}</p>"]


def _section(key: str, covered: Covered, pair: Pair | None, found: Verdict,
             column_days: Mapping[tuple[str, date], ColumnDay], day: date, promotions_errors: Mapping[str, str]) -> str:
    """A column's section (the module's docstring)."""
    column = BY_KEY[key]
    point = None if pair is None else pair.points.get(day)
    parts = [f"<h2>{text(column.name)}</h2>"]
    if column.slug in promotions_errors:
        parts.append(f'<p class="warn">{text(unreadable(column.slug))}</p>')
    today = column_days[(key, day)]
    parts += _said(key, found, today, covered)
    named = [] if found.struct is None else conditions(found.struct)
    if named:
        parts.append(f'<p class="conditions">{text("; ".join(named))}</p>')
    if point is not None and point.next_start is not None and today.record:   # a hole's few files judge no start
        parts.append(f"<p>{text(coming_sale(point.next_start))}</p>")
    parts.append(render_chart(found, day))
    parts += [f"<p>{text(line)}</p>" for line in (last_low(found), how_often(found)) if line is not None]
    parts.append(_worked_out(key, today, point, covered, day))
    return f'<section data-column="{key}" id="c-{key}" data-chain="{column.slug}">{"".join(parts)}</section>'


def _rank(found: Verdict, place: int) -> tuple:
    """A badge's place in the row: a verdict by its saving as shown, largest first, before any call without one; a tie
    in COLUMNS order."""
    return (1, 0, place) if found.saving is None else (0, -found.saving, place)


def _row(pairs: Mapping[str, Pair], verdicts: Mapping[str, Verdict], day: date) -> list[str]:
    """The badge row and its hidden heading (the module's docstring)."""
    selling = [column.key for column in COLUMNS if column.key in pairs and day in pairs[column.key].points]
    places = {column.key: place for place, column in enumerate(COLUMNS)}
    selling.sort(key=lambda key: _rank(verdicts[key], places[key]))
    badges = "".join(f'<a data-column="{key}" href="#c-{key}" class="badge {badge_class(verdicts[key])}">'
                     f"{text(short_badge(verdicts[key]))}</a>" for key in selling)
    return [f'<h2 class="elsewhere" hidden>{text(ELSEWHERE)}</h2>', f'<nav class="badges">{badges}</nav>']


def _names(covered: Covered) -> str:
    """Each distinct name once, as published, with the columns that list it so, by its first column's name."""
    by_name: dict[str, list[str]] = {}
    for column in COLUMNS:
        if column.key in covered.names:
            by_name.setdefault(covered.names[column.key], []).append(column.key)
    items = "".join(f"<li>{_span(name)} {text(as_listed(columns))}</li>" for name, columns in by_name.items())
    return f'<ul class="names">{items}</ul>'


def render_product(covered: Covered, pairs: Mapping[str, Pair], verdicts: Mapping[str, Verdict],
                   column_days: Mapping[tuple[str, date], ColumnDay], day: date, collected_by: str,
                   gates: Mapping[str, Gate], promotions_errors: Mapping[str, str]) -> str:
    """The product's page for `day` (the module's docstring): `pairs`, `verdicts` and `gates` by column (a verdict for
    each of `section_keys`), `promotions_errors` by chain; `column_days` holds every column's day. ValueError for an
    open gate: step one has no odds line."""
    opened = sorted(key for key, found in gates.items() if found.open)
    if opened:
        raise ValueError(f"the gate is open at {', '.join(opened)}, and step one shows no odds")
    size = "" if covered.size is None else f" · {text(size_text(Size(*covered.size)))}"
    main = "\n".join([f"<h1>{_span(covered.title)}</h1>", _names(covered),
                      f"<p>{text(BARCODE)} {text(covered.code)}{size}</p>",
                      *_row(pairs, verdicts, day),
                      *(_section(key, covered, pairs.get(key), verdicts[key], column_days, day, promotions_errors)
                        for key in section_keys(covered, pairs)),
                      f'<p class="lede">{text(ALWAYS_SENTENCE)}</p>',
                      ])
    links = ((BROWSE_LINK, browse_path(covered.title)), (RECORD_TITLE, "record.html"), (METHOD_TITLE, "method.html"))
    return page(f"{covered.code} - {SITE_NAME}", main, day, collected_by, links, PRODUCT_STYLE)

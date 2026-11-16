"""The product pages: one per covered product, `p/<barcode>.html`, a part per store type (a column) answering "Deal" or
"No deal" against what the product usually costs there, sales included (docs/store-first.md, "What a visitor sees" 5
to 8, "The chart", "Words" and "Changes to the shopper-site design"; docs/shopper-site.md's P2 to P5, P10, F2, F10 and
Call 10, as kept; the store-first plan's Task 3 and its "Where the design leaves room"; before it, the shopper plan's
Task 16, its questions A, G and M (g), and the second pre-flight's S1, S7, S11 and S12; the look, docs/site-look.md's
"The label", "A product page" and "The barcode", and the site-look plan's Task 8 and its "The label, call by call").
Every word is `shopper.words`' or `basket.words`'; every chain-supplied text (a product's names, a programme's) is
escaped inside `CHAIN_SPAN`, so the site check reads it for markup only. The verdicts are `shopper.verdict`'s, one per
section, worked by the build's one pass and handed in.

The page, top to bottom, on the shared shell (`shopper.shell`: the band with the site's name and the date line, the
footer with the credit line and the links to the product's browse page, the record and the method page). The tab's
title is the barcode, never a chain's name, which no span can hold there. Then:

- the title, the longest name; each distinct name once, with the columns that list it so (`as_listed`); the barcode
  and the size the chains state;
- the barcode's drawing (`shopper.bars.drawing`, `<svg class="defs">` holding the path `id="ean"`), once, right after
  the barcode line, when the code has bars and a part shows its mark (a label; NO_LABEL's parts show none), so a page
  carries no drawing nothing uses;
- the badge row: its heading, `<h2 class="elsewhere" hidden>` "Elsewhere today", then `<nav class="badges">`, a badge
  `<a data-column="<key>" href="#c-<key>" class="badge <class>">` per store type with a point today (on a hole too:
  its few files list it), each the store type's name, a separator the stylesheet hides (`<i> · </i>`) and, in `<b>`,
  its verdict or its no-verdict line, read as text in `short_badge`'s words; the deals and no deals first, by saving as
  shown, largest first, a tie in COLUMNS order, then the rest in COLUMNS order. The row is there, empty, when nothing
  sells the product today;
- a section per column that lists the product or has its history, in name order (`shopper.columns.COLUMNS`),
  `<section data-column="<key>" id="c-<key>" data-chain="<chain>">`, headed with the column's name (the parts below);
- ALWAYS_SENTENCE, once, which carries the four ALWAYS phrases whatever the product's day (S7).

A section, in this order, on one line:

- P10, when the chain's promotions could not be read today (`promotions_errors`, by chain): `unreadable(slug)`, on
  every section of the chain's columns (both Carrefour columns).
- The verdict as a shelf label, `<div class="tag <class>">` (`badge_class`: a deal's S5 shade, green; `no-deal`, the
  yellow label; `none`, the plain label of a line that is not a verdict), in two parts:
  - the saying part, `<div class="say">`: the verdict, `<p class="verdict">`: a deal's or a no deal's `badge` words,
    which name the store type, its verdict in `<b>` ("At Carrefour Market: <b>DEAL · ₪1.90 off</b>"), then the reason
    (`reason`, naming its days, S8); any other call, NO_VERDICT's line alone. Then the conditions of the promotion the
    verdict judges (S3's), in shopper words (`conditions`), when it has any; then the coming sale (F2, Call 22: the
    items row lists a wide promotion starting in the next 14 days), `coming_sale`; never on a hole morning, whose few
    files cannot tell whether a promotion is listed across the column (deploy prep): a hole's part has no label;
  - the price part, `<div class="pay">`: today's price as on a shelf edge, `<p class="price">`, in `price_line`'s words
    with its figure split at the point, the shekels then the point and the agorot in `<sup>`, and a weighed product's
    unit in `<small>` ("Price today: <b><i>₪</i>14<sup>.00</sup></b>"), when today's price is known; then the barcode's
    mark (`shopper.bars.mark`), when the code has bars. With neither the part is left out.
  The calls without a label (NO_LABEL): a hole's `basket.words.too_few` line, `<p class="few">` (prices from files of
  fewer than half the column's stores; the verdict's first call, so a product the few files miss is never said not
  sold); and the empty slot, `<p class="not-sold">`, `not_sold` with the last day the registry saw it listed across
  the column (`last_wide`, Call 10's).
- The history (`shopper.chart.render_chart`, from the verdict and today's shelf price): today's listed price, as shown,
  on a day with records, but none on an unread sale price or sale prices not read today (the owner's rulings of
  2026-11-11 and 2026-11-16: a shelf price at the line's end reads as what the shopper pays today); none on a hole or
  with no point today. Then "Last this low" (`last_low`, S6) and "How often on sale" (`how_often`, S7), each
  `<p class="fact">` when it has something to say.
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

Nothing is hidden without the script (the plan): the only `hidden` attribute is the row's heading's, and the site's
stylesheet hides only what has one (`[hidden]{display:none!important}`), so it cannot show a part the script hid.
`search.js` reads this markup (its header comment), and every fact stays in the HTML with the script blocked. The page
holds no style of its own: the label's greens and yellow, light and dark, and every rule of the page, the chart's
strokes and the barcode's bars among them (their SVGs draw none), are the site's one stylesheet's
(docs/site-look.md), which the shell links.

The shell (`shopper.shell`) links the site's one stylesheet and loads its one script, `search.js`, as on every page,
and names the page's kind on its body ("product"); no fact needs the script. The page is a pure function of its
inputs: the same bytes whatever order the mappings come in.
"""
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from basket.record import money
from basket.units import Size
from basket.words import range_note, size_text, too_few
from shopper.bars import drawing, mark
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
                           listed_price, minimum_spend, no_odds_yet, not_sold, price_line, reason, short_badge,
                           stores_range, targets, unreadable, verdict_words)

__all__ = ["CHAIN_SPAN", "MAX_PAGE", "badge_class", "field_conditions", "page_path", "render_product", "running_today",
           "section_keys"]

MAX_PAGE = 60_000      # bytes a product page may hold (the design's check)
NO_LABEL = ("too_few", "not_sold")              # a line of their own, no label: no price part, no barcode's mark
NO_PRICE_TODAY = ("price_unread", "unread_today")   # no shelf price at today's end of the chart (the module's docstring)


def page_path(code: str) -> str:
    """The product's page in the site: p/<barcode>.html."""
    return f"p/{code}.html"


def section_keys(covered: Covered, pairs: Mapping[str, Pair]) -> list[str]:
    """The columns a product page has a section for, in name order: those whose registry names the product, and those
    with its history in the days read (the build works a verdict for each)."""
    return [column.key for column in COLUMNS if column.key in covered.names or column.key in pairs]


def badge_class(found: Verdict) -> str:
    """A label's and a badge's class: a deal's S5 shade (its green), "no-deal" (the yellow label), or "none" (the plain
    label) for a call without a verdict."""
    if found.call == "deal":
        return found.shade
    if found.call == "no_deal":
        return "no-deal"
    return "none"


def _span(value: str) -> str:
    return CHAIN_SPAN.format(text(value))


def running_today(point: Point | None, day: date) -> list[dict]:
    """The point's promotions running on `day` (P3: started on or before it and ending on or after it); the build's
    promotions line reads them so too."""
    if point is None:
        return []
    return [struct for struct in point.promotions if struct["start"] <= day <= struct["end"]]


def _valid(struct: Mapping) -> Deal | None:
    """The promotion's deal (S11) when its price is read and valid, else None."""
    deal = deal_from_row(struct)
    return deal if deal.valid and deal.price is not None else None


def field_conditions(struct: Mapping) -> list[str]:
    """A promotion's conditions from the fields, as HTML, each with its source (P5, S3), from a struct's
    `restrictions`, `programmes` and `min_spend`; every programme's name in the chain's span."""
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


def _price(found: Verdict) -> str:
    """Today's price as on a shelf edge (the module's docstring): `price_line`'s words, its figure as shown split at
    the point, a kilogram's unit in small print; "" without today's price."""
    line = price_line(found)
    if line is None:
        return ""
    shown = str(found.today_price)                        # as `price_line` shows it
    said, _, unit = line.partition(f"₪{shown}")           # "Price today: ", then " a kilogram" or ""
    shekels, point, agorot = shown.partition(".")
    small = f"<small>{text(unit)}</small>" if unit else ""
    return f'<p class="price">{text(said)}<b><i>₪</i>{shekels}<sup>{point}{agorot}</sup></b>{small}</p>'


def _label(key: str, found: Verdict, today: ColumnDay, point: Point | None, covered: Covered) -> str:
    """The verdict as a shelf label, its saying part and its price part; or, for NO_LABEL's calls, their line alone
    (the module's docstring)."""
    if found.call in NO_LABEL:          # the drawing's rule reads the same set (`render_product`)
        if found.call == "too_few":
            return f'<p class="few">{text(too_few(today.with_file, today.included))}</p>'
        return f'<p class="not-sold">{text(not_sold(key, covered.last_wide.get(key)))}</p>'
    if found.call in ("deal", "no_deal"):
        said = verdict_words(found)
        at = badge(found).removesuffix(said)              # "At Carrefour Market: "
        say = [f'<p class="verdict">{text(at)}<b>{text(said)}</b></p>', f'<p class="reason">{text(reason(found))}</p>']
    else:
        say = [f'<p class="verdict">{text(NO_VERDICT[found.call])}</p>']
    named = [] if found.struct is None else conditions(found.struct)
    if named:
        say.append(f'<p class="conditions">{text("; ".join(named))}</p>')
    if point is not None and point.next_start is not None:   # never on a hole: its few files judge no start (NO_LABEL)
        say.append(f"<p>{text(coming_sale(point.next_start))}</p>")
    pay = _price(found) + mark(covered.code)
    part = f'<div class="pay">{pay}</div>' if pay else ""
    return f'<div class="tag {badge_class(found)}"><div class="say">{"".join(say)}</div>{part}</div>'


def _listed_today(found: Verdict, today: ColumnDay, point: Point | None) -> Decimal | None:
    """Today's shelf price for the chart (the plan's "The chart, call by call"): the point's listed price, as shown, on
    a day with records; None on a hole or with no point today, and on NO_PRICE_TODAY's calls (the module's
    docstring)."""
    if point is None or point.listed is None or not today.record:
        return None
    if found.call in NO_PRICE_TODAY:
        return None
    return Decimal(money(point.listed))


def _section(key: str, covered: Covered, pair: Pair | None, found: Verdict,
             column_days: Mapping[tuple[str, date], ColumnDay], day: date, promotions_errors: Mapping[str, str]) -> str:
    """A column's section (the module's docstring)."""
    column = BY_KEY[key]
    point = None if pair is None else pair.points.get(day)
    parts = [f"<h2>{text(column.name)}</h2>"]
    if column.slug in promotions_errors:
        parts.append(f'<p class="warn">{text(unreadable(column.slug))}</p>')
    today = column_days[(key, day)]
    parts.append(_label(key, found, today, point, covered))
    parts.append(render_chart(found, day, _listed_today(found, today, point)))
    parts += [f'<p class="fact">{text(line)}</p>' for line in (last_low(found), how_often(found)) if line is not None]
    parts.append(_worked_out(key, today, point, covered, day))
    return f'<section data-column="{key}" id="c-{key}" data-chain="{column.slug}">{"".join(parts)}</section>'


def _rank(found: Verdict, place: int) -> tuple:
    """A badge's place in the row: a verdict by its saving as shown, largest first, before any call without one; a tie
    in COLUMNS order."""
    return (1, 0, place) if found.saving is None else (0, -found.saving, place)


def _badge(key: str, found: Verdict) -> str:
    """A badge of the row (the module's docstring): the store type's name, the hidden separator and, in bold, the
    rest of `short_badge`."""
    name, sep, said = short_badge(found).partition(" · ")
    return (f'<a data-column="{key}" href="#c-{key}" class="badge {badge_class(found)}">'
            f"{text(name)}<i>{sep}</i><b>{text(said)}</b></a>")


def _row(pairs: Mapping[str, Pair], verdicts: Mapping[str, Verdict], day: date) -> list[str]:
    """The badge row and its hidden heading (the module's docstring)."""
    selling = [column.key for column in COLUMNS if column.key in pairs and day in pairs[column.key].points]
    places = {column.key: place for place, column in enumerate(COLUMNS)}
    selling.sort(key=lambda key: _rank(verdicts[key], places[key]))
    badges = "".join(_badge(key, verdicts[key]) for key in selling)
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
    keys = section_keys(covered, pairs)
    marked = any(verdicts[key].call not in NO_LABEL for key in keys)      # a label shows the barcode's mark
    bars = drawing(covered.code) if marked else ""
    main = "\n".join([f"<h1>{_span(covered.title)}</h1>", _names(covered),
                      f"<p>{text(BARCODE)} {text(covered.code)}{size}</p>",
                      *([bars] if bars else []),
                      *_row(pairs, verdicts, day),
                      *(_section(key, covered, pairs.get(key), verdicts[key], column_days, day, promotions_errors)
                        for key in keys),
                      f'<p class="lede">{text(ALWAYS_SENTENCE)}</p>',
                      ])
    links = ((BROWSE_LINK, browse_path(covered.title)), (RECORD_TITLE, "record.html"), (METHOD_TITLE, "method.html"))
    return page(f"{covered.code} - {SITE_NAME}", main, day, collected_by, links, "product")

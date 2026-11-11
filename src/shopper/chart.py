"""The price chart: one SVG per store type (a column) for its part of a product page, drawn from that column's verdict
(docs/store-first.md, "The chart" and "Page size"; the plan's Task 2 and its "Where the design leaves room", "The
chart"; the controller's ruling on the labels). A shopper in the aisle reads it at a glance: the store type's tracked
days, then today; the shelf price grey, the sale days green, and today's price dashed across, so every earlier day at
or below it stands out.

The drawing rules:

- Across: each calendar day from the verdict's first tracked day (S0) to today is DAY_WIDTH (4) units, the first
  tracked day at x 0 and today at (today - first) * DAY_WIDTH. The span is what was tracked, never a fixed 90 days,
  so a short history draws a short chart. A day's marks run from its x to the next day's.
- Up: the price per item, the highest at TOP and the lowest at BOTTOM, between the lowest and the highest of the prices
  drawn: the listed prices as shown, the day prices (S1) and today's price, so the grey line and today's dot both fit.
  One price throughout sits midway. Heights are whole units, half up (`shopper.measures.whole`).
- `<path class="listed">`: the listed price as shown on every tracked day, sale days included: the shelf price, grey.
  Each run of consecutive tracked days is one line from its start (an M) that steps only where the height changes,
  so a run of one price is one segment (the design's first simplification, built in). A day not tracked (a hole, a
  promotion hole, a day the product was not listed) breaks it, and the next tracked day starts again: a gap, never
  filled in.
- `<path class="sale">`: the day price on the tracked days on sale with a price, green, drawn the same way over the
  runs of consecutive such days. A day not on sale has none.
- `<path class="unread">`: a mark at FOOT, below every price, under each sale day of unknown price (S1), consecutive
  ones as one mark: on sale, no price drawn.
- With today's price known (S6's today; unknown on too_few, not_sold and unread_today, which get no today mark):
  `<line class="today">` at its height from x 0 to the plot's right edge, the end of today's day, and
  `<circle class="today">` at today's x.
- `<text>` labels, right of the plot, in `shopper.words.chart_label`'s words: the usual price (S2: a verdict of deal
  or no deal), the lowest and the highest day prices of the tracked days (day prices, never the listed prices drawn,
  so an always-on product's highest is its sale price; neither when no day has a price), and today's price. Each sits
  at its price's height, moved apart just enough that none is drawn over another (LINE units between centres, ties
  in ORDER), all between TOP and BOTTOM. The labels' column is as wide as CHAR units a character of the longest.
- `<title>`, the SVG's first child, is the text alternative (`shopper.words.chart_summary`, which names the same
  labels), named by `aria-labelledby`; its id, `chart-<column>`, is unique on a page of one chart per column.
- After the SVG, the key as text (`<p class="key">`): CHART_KEY's words for each kind of mark drawn, each after an
  `<i>` swatch of its class and set apart by " · ", as CHAINS_LINE's names are, so colour is never the only signal.

The SVG states its size in units (`width`, `height`, `font-size`), so it is drawn at that size without a style, and a
style that sets only a maximum width and `height: auto` keeps a short history short. The colours, the dashes and the
strokes are PRODUCT_STYLE's (`.chart .listed` grey, `.chart .sale` green, `.today` dashed: Task 3), tested there.

"" when the verdict has no tracked day: nothing is drawn from nothing. A pure function of its inputs: the days are
drawn in day order, whatever order they come in.
"""
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from shopper.measures import whole
from shopper.shell import text
from shopper.verdict import Verdict
from shopper.words import CHART_KEY, chart_label, chart_summary

DAY_WIDTH = 4                                   # units a day
TOP, BOTTOM = 10, 100                           # the prices' heights, the highest to the lowest
FOOT = 108                                      # the marks of the sale days of unknown price
HEIGHT = 114                                    # the chart's
DOT = 4                                         # today's dot's radius
FONT = 12                                       # the labels' size
CHAR = 7                                        # the width a label's character is given
PAD = 6                                         # between the plot's right edge and the labels
LINE = 14                                       # the least distance between two labels' centres
BASELINE = 4                                    # a label's baseline below its centre
ORDER = ("highest", "usually", "today", "lowest")      # labels at one height, top to bottom


def _x(day: date, first: date) -> int:
    return (day - first).days * DAY_WIDTH


def _runs(stretch: Sequence[tuple[date, int]]) -> list[list[tuple[date, int]]]:
    """(day, height) pairs in day order, split where a calendar day is missing."""
    found: list[list[tuple[date, int]]] = []
    for seen, height in stretch:
        if found and found[-1][-1][0] + timedelta(days=1) == seen:
            found[-1].append((seen, height))
        else:
            found.append([(seen, height)])
    return found


def _line(stretch: Sequence[tuple[date, int]], first: date) -> str:
    """A path's data over (day, height) pairs in day order: each run of consecutive days from an M, stepping only where
    the height changes, to the end of its last day."""
    parts = []
    for run in _runs(stretch):
        (start, level), *rest = run
        parts.append(f"M{_x(start, first)} {level}")
        for seen, height in rest:
            if height != level:
                parts.append(f"H{_x(seen, first)}V{height}")
                level = height
        parts.append(f"H{_x(run[-1][0], first) + DAY_WIDTH}")
    return "".join(parts)


def _placed(levels: Sequence[int]) -> list[int]:
    """Label centres for `levels`, top to bottom: each pushed down to LINE below the one above, then, from the last,
    back up to BOTTOM and LINE above the one below."""
    placed = list(levels)
    for n in range(1, len(placed)):
        placed[n] = max(placed[n], placed[n - 1] + LINE)
    limit = BOTTOM
    for n in reversed(range(len(placed))):
        placed[n] = min(placed[n], limit)
        limit = placed[n] - LINE
    return placed


def render_chart(found: Verdict, day: date) -> str:
    """The column's price chart on `day`, then its key (the module's docstring); "" with no tracked day."""
    if not found.days:
        return ""
    days = sorted(found.days, key=lambda each: each.day)
    first = days[0].day
    priced = [each.price for each in days if each.price is not None]
    known = [] if found.today_price is None else [found.today_price]       # today's price, when it is known
    shown = [*(each.listed for each in days), *priced, *known]
    low, high = min(shown), max(shown)

    def height(price: Decimal) -> int:
        if high == low:
            return (TOP + BOTTOM) // 2
        return TOP + whole(Fraction(high - price) / Fraction(high - low) * (BOTTOM - TOP))

    edge = _x(day, first) + DAY_WIDTH
    drawn = [f'<path class="listed" d="{_line([(each.day, height(each.listed)) for each in days], first)}"/>']
    sale = [(each.day, height(each.price)) for each in days if each.on_sale and each.price is not None]
    unread = [(each.day, FOOT) for each in days if each.on_sale and each.price is None]
    if sale:
        drawn.append(f'<path class="sale" d="{_line(sale, first)}"/>')
    if unread:
        drawn.append(f'<path class="unread" d="{_line(unread, first)}"/>')
    if found.today_price is not None:
        level = height(found.today_price)
        drawn.append(f'<line class="today" x1="0" y1="{level}" x2="{edge}" y2="{level}"/>')
        drawn.append(f'<circle class="today" cx="{_x(day, first)}" cy="{level}" r="{DOT}"/>')
    labels = [*([("usually", found.usual)] if found.usual is not None else []),
              *([("lowest", min(priced)), ("highest", max(priced))] if priced else []),
              *(("today", price) for price in known)]
    labels.sort(key=lambda label: (height(label[1]), ORDER.index(label[0])))
    levels = _placed([height(price) for _, price in labels])
    said = [chart_label(kind, price) for kind, price in labels]
    drawn += [f'<text x="{edge + PAD}" y="{centre + BASELINE}">{text(words)}</text>'
              for centre, words in zip(levels, said)]
    width = edge + (PAD + CHAR * max(map(len, said)) if said else 0)
    marks = [("listed", CHART_KEY[0]), *([("sale", CHART_KEY[1])] if sale else []),
             *([("unread", CHART_KEY[2])] if unread else [])]
    key = " · ".join(f'<i class="{name}"></i>{text(words)}' for name, words in marks)
    return (f'<svg class="chart" role="img" aria-labelledby="chart-{found.column}" viewBox="0 0 {width} {HEIGHT}" '
            f'width="{width}" height="{HEIGHT}" font-size="{FONT}">'
            f'<title id="chart-{found.column}">{text(chart_summary(found))}</title>{"".join(drawn)}</svg>'
            f'<p class="key">{key}</p>')

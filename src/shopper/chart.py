"""The price chart: for one store type (a column), the history in its part of a product page, drawn from the column's
verdict, the day and today's shelf price (docs/site-look.md, "The chart"; docs/store-first.md, "The rules" S0 to S8;
the site-look plan's Task 5 and its "Where the design leaves room", "The chart, call by call"). A shopper in the aisle
reads it at a glance: a ₪ axis at the left, the store type's tracked days across with their dates along the bottom,
the shelf price and the sale price as step lines, and today's prices written at the lines' right end.

Four SVGs in a row, and only one of them scales, so no word ever shrinks:

- `<svg class="ax">`, the axis: a figure per step at its height, top to bottom, "₪26" for a whole shekel and "₪4.50"
  for a half, anchored AXIS_X pixels in. The steps (`axis`) run over the lowest and the highest of the prices drawn:
  the shelf prices, the sale prices, the usual price and today's two prices. The step is the smallest of 1, 2, 5, 10,
  20, 50 ... shekels that holds them in two to five steps, half a shekel for prices less than a shekel apart; one price
  or two close ones get a step of room on the side with less; and the axis starts a step lower when the lowest price
  would be within 8% of its bottom, so no price sits on the date line. Not from zero: a shelf price moves by a shekel
  or two, which a zero-based axis would flatten. A price's height (`up`) is its place from the top step (0) to the
  bottom (PLOT), whole pixels, half up (`shopper.measures.whole`).
- `<svg class="lines">`, the only one with a viewBox: one unit a day across, the first tracked day (S0) at 0 and today
  the last, so the span counts today; one unit a pixel up. preserveAspectRatio="none" stretches it to its column's
  width, whatever the number of days, and the stylesheet keeps every stroke's width. It holds no text; its text
  alternative is its aria-label, `shopper.words.chart_summary`. In order: a gridline at each step above the bottom; the
  usual price (S2, with a Deal or No deal) over the shelf line's days; the shelf price (`listed`) on every tracked day,
  sale days included, and today with today's shelf price; the sale price on the tracked days on sale with a price, and
  today when a promotion counts; a tick standing on the date line (at TICK) under each sale day whose price could not be
  read (S1), and under today on price_unread. Each is a step line: each run of consecutive days from an M, stepping
  only where the height changes, to the end of its last day. So a day with no record (a hole, a promotion hole, a day
  the product was not listed) is a gap in every line, the usual one too, and a run of one price is one segment.
- `<svg class="over">`, lying over the lines and placing its words by percentage. The usual price's words at the
  right: above its line, unless a shelf or sale point on the last 30% of the span's days (each day reaching past 70%
  of the span: the last ceil(0.3 x span)) runs within 21 pixels above it or the line is under 20 pixels from the top,
  then below; above again when below is as busy, or the line is under 20 pixels from the date line. Then the first
  tracked day's date at the left, and between it and today a mark and a name at each month's first day when the span
  is WEEKLY_UNDER days or more, else a mark and a date every seventh day back from today. Every mark is drawn. A name
  whose day's share of the span is outside NAMED is never written, so on a screen of 48rem or more, where all the
  rest show, none runs into the first date's words or out of the plot into the today column. A phone's plot is 142
  pixels narrower than its screen (178 at 320), and there `class="near"` hides a name outside NEAR and, on a weekly
  span of ALTERNATE_WEEKS days or more, every name an odd number of weeks before today (7, 21, 35 days back). With
  NEAR alone, on a 320-pixel screen, the week names would come within 5 pixels of each other from 28 days, and the
  one a week before today would run out of the plot below about a 400-pixel screen (into "today" at 320). Hiding the
  odd weeks keeps the names a phone shows 46 pixels or more apart at 320, each ending inside the plot (but a month's
  name at 84%, up to half a pixel past it).
- `<svg class="now">`, today's column: a dot at today's shelf price and at today's sale price, top to bottom, each with
  its price beside it in its line's colour, the labels LABEL_GAP pixels apart at least and none below the date line;
  the lower price (what the shopper pays; both when equal) in bold (`now`). Then "today" (TODAY_WORD) under them.

The chart, call by call (the plan). Today's shelf point is `listed_today`, which the product page gives when today is
a record day with a listed price and the call is neither price_unread nor unread_today: on those two today shows no
price, the shelf line ending the day before (the owner, 2026-11-11 and 2026-11-16: a shopper holding a sale tag does
not pay the shelf price). Today's sale point is the verdict's today's price when a promotion counts and that price is
known. On price_unread the tick under today marks a sale whose price could not be read.

After the chart, the key (`<p class="key">`): CHART_KEY's words for each kind of mark drawn, today's included, each
after an `<i>` swatch of its class and set apart by " · ", so colour is never the only signal. Then the table
(`<table class="stats">`), a head over a figure in each cell, STATS_HEADS' order: Lowest and Highest over the tracked
days' day prices and today's price (`shopper.verdict.extremes`, the design's call 3), each over the latest day at that
price (`short_day`, or TODAY_WORD for today's); Usual with a usual price; Today with today's price. No table with no
cell.

No `style`, `width` or `height` attribute anywhere: positions are SVG attributes, sizes are the stylesheet's (`.chart`,
`.key` and `.stats` in look.css). "" when the verdict has no tracked day: nothing is drawn from nothing. A pure
function of its inputs: the days are drawn in day order, whatever order they come in.
"""
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from html import escape
from math import ceil, floor

from basket.record import money
from shopper.measures import whole
from shopper.shell import text
from shopper.verdict import Verdict, extremes
from shopper.words import CHART_KEY, STATS_HEADS, TODAY_WORD, chart_label, chart_summary, month_name, short_day

PLOT = 200                       # the plot's height in pixels; the SVGs beside it are 224 high with the dates
AXIS_X, NOW_X = 40, 12           # the axis column's anchor (46 wide, less 6), the today column's text start (64 wide)
LABEL_GAP = 17                   # today's two labels' least distance, centre to centre
NEAR = (Fraction(22, 100), Fraction(84, 100))    # a date outside this share of the span is hidden on a phone
# A date's name outside this share of the span is not written at all, its mark kept. Measured in headless Chrome under
# look.css and its fonts (2026-11-16): the narrowest plot that shows every name is 516.7 pixels (a 1,024-pixel window,
# where the script's two columns start; 594 at 768, 602 at 1,280); the widest first date, "28 May", is 40.8 pixels
# wide, as is the widest name (the months' at most 23.9); a name starts 5 pixels after its mark. So on any plot of
# 516.7 pixels or more (a screen of 48rem or more, where every name shows) a name from 8% clears the first date by 5.5
# pixels or more, and one up to 91% ends inside the plot, short of the today column. A phone hides more (NEAR and
# ALTERNATE_WEEKS), so the names it shows stay inside the plot down to a 320-pixel screen.
NAMED = (Fraction(8, 100), Fraction(91, 100))
# From this many days, a weekly span's names an odd number of weeks before today are hidden on a phone too. A week is
# 7/span x 178 pixels on a 320-pixel screen; a 40.8-pixel name with 5 pixels before the next one needs 45.8, which
# holds up to 27 days (46.1) but not at 28 (7/28 x 178 = 44.5). Every other week: 14/45 x 178 = 55.4 at the least.
ALTERNATE_WEEKS = 28
WEEKLY_UNDER = 46                # days in the span below which the dates are a week apart, else the months
TICK = Decimal("196.5")          # the unread ticks' line: 7 pixels standing on the date line
DATES_Y = 217                    # the dates' baseline, under the date line; a date's mark runs from PLOT 6 down


def axis(low: Decimal, high: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """(bottom, top, step) for the lowest and the highest of the prices drawn (the module's docstring)."""
    steps = [Decimal("0.5")] if 0 < high - low < 1 else []
    steps += [m * 10 ** k for k in range(0, 9) for m in (1, 2, 5)]        # 1, 2, 5, 10, 20, 50, …
    for step in steps:
        bottom, top = floor(low / step) * step, ceil(high / step) * step
        while (top - bottom) / step < 2:                  # one price, or two close ones: room on the side with less
            if bottom >= step and low - bottom <= top - high:
                bottom -= step
            else:
                top += step
        if low - bottom < Decimal("0.08") * (top - bottom) and bottom >= step:   # no price on the date line
            bottom -= step
        if (top - bottom) / step <= 5:
            return Decimal(bottom), Decimal(top), Decimal(step)
    raise ValueError(f"no axis of at most five steps holds ₪{low} to ₪{high}")


def _runs(stretch: Sequence[tuple[int, int | Decimal]]) -> list[list[tuple[int, int | Decimal]]]:
    """(x, height) pairs in day order, split where a day is missing."""
    runs: list[list[tuple[int, int | Decimal]]] = []
    for x, height in stretch:
        if runs and runs[-1][-1][0] + 1 == x:
            runs[-1].append((x, height))
        else:
            runs.append([(x, height)])
    return runs


def _line(stretch: Sequence[tuple[int, int | Decimal]]) -> str:
    """A step line's path data over (x, height) pairs in day order: each run of consecutive days from an M, stepping
    only where the height changes, to the end of its last day."""
    parts = []
    for run in _runs(stretch):
        (start, level), *rest = run
        parts.append(f"M{start} {level}")
        for x, height in rest:
            if height != level:
                parts.append(f"H{x}V{height}")
                level = height
        parts.append(f"H{run[-1][0] + 1}")
    return "".join(parts)


def _apart(levels: Sequence[int]) -> list[int]:
    """Label centres for `levels`, top to bottom: each pushed down to LABEL_GAP below the one above, then, from the
    last, back up to the date line (PLOT) and LABEL_GAP above the one below."""
    placed = list(levels)
    for n in range(1, len(placed)):
        placed[n] = max(placed[n], placed[n - 1] + LABEL_GAP)
    limit = PLOT
    for n in reversed(range(len(placed))):
        placed[n] = min(placed[n], limit)
        limit = placed[n] - LABEL_GAP
    return placed


def _percent(share: Fraction) -> str:
    """A share of the span as a percentage, two places half up, trailing zeros dropped: "17.58", "50"."""
    hundredths = whole(share * 10_000)
    return f"{hundredths // 100}.{hundredths % 100:02d}".rstrip("0").rstrip(".")


def _shekels(tick: Decimal) -> str:
    """An axis figure: "₪26" for a whole shekel, "₪4.50" for a half."""
    return f"₪{tick:.0f}" if tick % 1 == 0 else f"₪{money(tick)}"


def render_chart(found: Verdict, day: date, listed_today: Decimal | None = None) -> str:
    """The column's price chart on `day`, then its key and its table (the module's docstring); "" with no tracked day.
    `listed_today` is today's shelf price, None when today shows none."""
    if not found.days:
        return ""
    days = sorted(found.days, key=lambda each: each.day)
    first = days[0].day
    span = (day - first).days + 1                   # today included
    last = span - 1                                 # today's x

    def x(seen: date) -> int:
        return (seen - first).days

    sold = [each for each in days if each.on_sale and each.price is not None]
    selling = found.counting and found.today_price is not None                  # today's sale point
    points = [*([("listed", listed_today)] if listed_today is not None else []),
              *([("sale", found.today_price)] if selling else [])]
    drawn = [*(each.listed for each in days), *(each.price for each in sold),
             *([] if found.usual is None else [found.usual]), *(price for _, price in points)]
    bottom, top, step = axis(min(drawn), max(drawn))

    def up(price: Decimal) -> int:
        return whole(Fraction(top - price) / Fraction(top - bottom) * PLOT)

    shelf = [(x(each.day), up(each.listed)) for each in days]
    sale = [(x(each.day), up(each.price)) for each in sold]
    unread = [(x(each.day), TICK) for each in days if each.on_sale and each.price is None]
    if listed_today is not None:
        shelf.append((last, up(listed_today)))
    if selling:
        sale.append((last, up(found.today_price)))
    if found.call == "price_unread":                # today on sale, its price not read
        unread.append((last, TICK))

    ticks = [bottom + step * n for n in range(int((top - bottom) / step) + 1)]          # bottom to top
    ax = "".join(f'<text x="{AXIS_X}" y="{up(tick) + 4}">{_shekels(tick)}</text>' for tick in reversed(ticks))
    paths = [("grid", "".join(f"M0 {up(tick)}H{span}" for tick in ticks[1:]))]
    over = []
    if found.usual is not None:                     # S2: a Deal or No deal
        level = up(found.usual)
        paths.append(("usual", _line([(at, level) for at, _ in shelf])))
        busy = [height for at, height in (*shelf, *sale) if 10 * (at + 1) > 7 * span]     # the last 30% of the days
        above = level >= 20 and not any(level - 21 <= height <= level - 1 for height in busy)
        below = level <= PLOT - 20 and not any(level + 1 <= height <= level + 21 for height in busy)
        y = level - 6 if above or not below else level + 15
        over.append(f'<text class="usually" x="100%" dx="-12" y="{y}">{text(chart_label("usually", found.usual))}'
                    "</text>")
    paths += [("listed", _line(shelf)), *([("sale", _line(sale))] if sale else []),
              *([("unread", _line(unread))] if unread else [])]
    lines = "".join(f'<path class="{name}" d="{d}"/>' for name, d in paths)

    over.append(f'<text y="{DATES_Y}">{text(short_day(first))}</text>')
    monthly = span >= WEEKLY_UNDER
    for at in range(1, last):
        seen = first + timedelta(days=at)
        if (seen.day == 1) if monthly else (last - at) % 7 == 0:
            share = Fraction(at, span)
            p = _percent(share)
            over.append(f'<line x1="{p}%" x2="{p}%" y1="{PLOT}" y2="{PLOT + 6}"/>')
            if share < NAMED[0] or share > NAMED[1]:            # its name would overlap: the mark alone
                continue
            near = "" if NEAR[0] <= share <= NEAR[1] else ' class="near"'
            if not monthly and span >= ALTERNATE_WEEKS and (last - at) // 7 % 2:     # an odd week back: not on a phone
                near = ' class="near"'
            name = month_name(seen) if monthly else short_day(seen)
            over.append(f'<text{near} x="{p}%" dx="5" y="{DATES_Y}">{text(name)}</text>')

    order = sorted(points, key=lambda point: up(point[1]))         # top to bottom; a tie keeps the shelf first
    heights = [up(price) for _, price in order]
    paid = max(heights, default=None)                              # the lower price: what the shopper pays
    now = []
    for (mark, price), height, centre in zip(order, heights, _apart(heights)):
        bold = " now" if height == paid else ""
        now.append(f'<circle class="{mark}" cy="{height}" r="4.5"/>'
                   f'<text class="{mark}{bold}" x="{NOW_X}" y="{centre + 5}">₪{money(price)}</text>')
    now.append(f'<text class="end" x="{NOW_X}" y="{DATES_Y}">{text(TODAY_WORD)}</text>')

    marks = [("listed", CHART_KEY[0]), *([("sale", CHART_KEY[1])] if sale else []),
             *([("unread", CHART_KEY[2])] if unread else [])]
    key = " · ".join(f'<i class="{name}"></i>{text(words)}' for name, words in marks)

    cells = []
    ends = extremes(found)
    if ends is not None:                            # the design's call 3: today counts
        cells += [(head, f"₪{money(price)}<small>{text(TODAY_WORD if seen is None else short_day(seen))}</small>")
                  for head, (price, seen) in zip(STATS_HEADS[:2], ends, strict=True)]
    if found.usual is not None:
        cells.append((STATS_HEADS[2], f"₪{money(found.usual)}"))
    if found.today_price is not None:
        cells.append((STATS_HEADS[3], f"₪{money(found.today_price)}"))
    heads = "".join(f'<th scope="col">{text(head)}</th>' for head, _ in cells)
    figures = "".join(f"<td>{figure}</td>" for _, figure in cells)
    table = f'<table class="stats"><tr>{heads}</tr><tr>{figures}</tr></table>' if cells else ""

    return (f'<div class="history"><div class="chart"><svg class="ax" aria-hidden="true">{ax}</svg>'
            f'<div class="plot"><svg class="lines" role="img" aria-label="{escape(chart_summary(found))}" '
            f'viewBox="0 0 {span} {PLOT}" preserveAspectRatio="none">{lines}</svg>'
            f'<svg class="over" aria-hidden="true">{"".join(over)}</svg></div>'
            f'<svg class="now" aria-hidden="true">{"".join(now)}</svg></div>'
            f'<p class="key">{key}</p>{table}</div>')

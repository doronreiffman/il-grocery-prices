"""The price chart: for one store type (a column), the history in its part of a product page, drawn from the column's
verdict and the day (docs/site-look.md, "The chart", as the owner redrew it on 2026-11-16 after reading the built
pages: "yes - one line. obviously."; docs/store-first.md, "The rules" S0 to S8; the site-look plan's Task 5 and Task
12's fix round). It reads like a familiar price-history chart: a ₪ axis at the left, the store type's tracked days
across with their dates along the bottom, one line of what the product cost each day, a sale a drop in it, and
today's price written at its end.

The line. A tracked day's price is its day price (S1: the lower of the listed price and the lowest promotion that
counts that day); today's is the verdict's today's price (S3), the label's "Price today", so the chart's last point is
the figure the label shows. A sale day's listed price is drawn nowhere. The line is an ink step line (`paid`) on the
days no promotion counted and the same line in the sale's green, heavier (`sale`), on the days one did, today's
included when one counts today (`found.counting`); the steps down into a sale and back out of it are the sale's, so a
sale reads as one notch. A day with no price (no record that day, promotions not read, the product not listed, or a
sale day whose price could not be read) is joined when BRIDGE (7) days or fewer lie in a row between two days with a
price: the line goes on dotted at the last price (`gap`, or `gap sale` after a sale day, so a sale with a missing
morning stays one green notch), and steps, still dotted, at the next day with a price. More than BRIDGE such days and
the line stops and starts again, nothing drawn across: the product was away. Nothing is carried past the last day with
a price, nor before the first.

Four SVGs in a row, and only one of them scales, so no word ever shrinks:

- `<svg class="ax">`, the axis: a figure per step at its height, top to bottom, "₪26" for a whole shekel and "₪4.50"
  for a half, anchored AXIS_X pixels in. The steps (`axis`) run over the lowest and the highest of the prices drawn:
  the days' prices, today's price and the usual price. The step is the smallest of 1, 2, 5, 10, 20, 50 ... shekels
  that holds them in two to five steps, half a shekel for prices less than a shekel apart; one price or two close ones
  get a step of room on the side with less; and the axis starts a step lower when the lowest price would be within 8%
  of its bottom, so no price sits on the date line. Not from zero: a price moves by a shekel or two, which a zero-based
  axis would flatten. A price's height (`up`) is its place from the top step (0) to the bottom (PLOT), whole pixels,
  half up (`shopper.measures.whole`).
- `<svg class="lines">`, the only one with a viewBox: one unit a day across, the first tracked day (S0) at 0 and today
  the last, so the span counts today; one unit a pixel up. preserveAspectRatio="none" stretches it to its column's
  width, whatever the number of days, and the stylesheet keeps every stroke's width. It holds no text; its text
  alternative is its aria-label, `shopper.words.chart_summary`. In order: a gridline at each step above the bottom
  (`grid`); the usual price (S2, with a Deal or No deal) as dashes (`usual`) on every day of the span but those on
  which the line, dotted or drawn, runs within CLEAR pixels of its height (where the price is the usual price the line
  says so; where it is somewhere else the dashes show where it usually is); the dotted stretches (`gap`, `gap sale`);
  the line (`paid`, `sale`); a tick standing on the date line (at TICK) under each sale day whose price could not be
  read (S1), and under today on price_unread (`unread`). The usual dashes and the ticks are level lines over their
  days (`_line`): each run of consecutive days from an M, to the end of its last day. The line is drawn stroke by
  stroke (`_Pen`), so a run of one price is one segment and a change of price one step, at the day it changes.
- `<svg class="over">`, lying over the lines and placing its words by percentage. The usual price's words at the
  right, LIFT pixels above its level, unless the line runs within 21 pixels above it on the last 30% of the span's days
  (each day reaching past 70% of the span: a point, a dotted day, or a step crossing that band), then 15 below; above
  again when below is as busy, or the level is under 20 pixels from the date line. Above is allowed at the very top of
  the plot: the words then stand in the chart's top margin. Then the first tracked day's date at the left, and
  between it and today a mark and a name at each month's first day when the span is WEEKLY_UNDER days or more, else a
  mark and a date every seventh day back from today. Every mark is drawn. A name whose day's share of the span is
  outside NAMED is never written, so on a screen of 48rem or more, where all the rest show, none runs into the first
  date's words or out of the plot into the today column. A phone's plot is 142 pixels narrower than its screen (178 at
  320), and there `class="near"` hides a name outside NEAR and, on a weekly span of ALTERNATE_WEEKS days or more,
  every name an odd number of weeks before today (7, 21, 35 days back). With NEAR alone, on a 320-pixel screen, the
  week names would come within 5 pixels of each other from 28 days, and the one a week before today would run out of
  the plot below about a 400-pixel screen (into "today" at 320). Hiding the odd weeks keeps the week names a phone
  shows 46 pixels or more apart at 320, each ending inside the plot (but a month's name at 84%, up to half a pixel
  past it).
- `<svg class="now">`, today's column. With a price today: one dot at its height, the price beside it in the line's
  colour there (the sale's green when a promotion counts, `class="sale"`, else ink, `class="paid"`), and "today"
  (TODAY_WORD) WORD_DROP pixels under the price. With none (price_unread, unread_today, not_sold, too_few): the line
  ends at its last day with a price and "today" stands alone on the dates' line (the owner, 2026-11-11 and
  2026-11-16: no price at today on an unread sale price or on a day whose sale prices were not read); on price_unread
  the tick under today marks a sale whose price could not be read.

After the chart, the key (`<p class="key">`), only for the marks that need words: CHART_KEY's "on sale" when a sale
stretch is drawn (today's included), "on sale, price not read" when a tick is, each after an `<i>` swatch of its class
and set apart by " · ", so colour is never the only signal. The plain line has no entry, and a chart with neither mark
has no key. Then the table (`<table class="stats">`), a head over a figure in each cell, STATS_HEADS' order: Lowest
and Highest over the tracked days' day prices and today's price (`shopper.verdict.extremes`, the design's call 3),
each over the latest day at that price (`short_day`, or TODAY_WORD for today's), now exactly the line's lowest and
highest points; Today with today's price. No Usual cell: the chart writes the usual price at its own height.

No `style`, `width` or `height` attribute anywhere: positions are SVG attributes, sizes are the stylesheet's (`.chart`,
`.key` and `.stats` in look.css). "" when no tracked day has a price: there is no line to draw (`new` and `no_history`
have no tracked day; a product whose every tracked day is a sale day of unknown price has none with a price). A pure
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
NEAR = (Fraction(22, 100), Fraction(84, 100))    # a date outside this share of the span is hidden on a phone
# A date's name outside this share of the span is not written at all, its mark kept. Measured in headless Chrome under
# look.css and its fonts (2026-11-16): the narrowest plot that shows every name is 516.7 pixels (a 1,024-pixel window,
# where the script's two columns start; 594 at 768, 602 at 1,280); the widest first date, "28 May", is 40.8 pixels
# wide, as is the widest name (the months' at most 23.9); a name starts 5 pixels after its mark. So on any plot of
# 516.7 pixels or more (a screen of 48rem or more, where every name shows) a name from 8% clears the first date by 5.5
# pixels or more, and one up to 91% ends inside the plot, short of the today column. A phone hides more (NEAR and
# ALTERNATE_WEEKS), so the names it shows stay inside the plot down to a 320-pixel screen, but for a month's name at
# exactly 84%, which ends up to half a pixel past it.
NAMED = (Fraction(8, 100), Fraction(91, 100))
# From this many days, a weekly span's names an odd number of weeks before today are hidden on a phone too. A week is
# 7/span x 178 pixels on a 320-pixel screen; a 40.8-pixel name with 5 pixels before the next one needs 45.8, which
# holds up to 27 days (46.1) but not at 28 (7/28 x 178 = 44.5). Every other week: 14/45 x 178 = 55.4 at the least.
ALTERNATE_WEEKS = 28
WEEKLY_UNDER = 46                # days in the span below which the dates are a week apart, else the months
TICK = Decimal("196.5")          # the unread ticks' line: 7 pixels standing on the date line
DATES_Y = 217                    # the dates' baseline, under the date line; a date's mark runs from PLOT 6 down
BRIDGE = 7                       # days with no price in a row, at most, that the dotted line carries a price over
CLEAR = 6                        # the usual price's dashes keep this many pixels from the line, or are not drawn
WORD_DROP = 14                   # "today" under today's price: its baseline below the price's
LIFT = 8                         # the usual price's words above its level: their baseline, so no descender or halo
#                                  touches a line running along it (6 in the first build, where a "y" nicked the line)


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
    """A level line's path data over (x, height) pairs in day order, all at one height (the usual dashes', the
    ticks'): each run of consecutive days from an M to the end of its last day."""
    return "".join(f"M{run[0][0]} {run[0][1]}H{run[-1][0] + 1}" for run in _runs(stretch))


class _Pen:
    """One path's data, drawn stroke by stroke from (x, height) to (x, height), each level or upright: a stroke that
    starts where the last one ended goes on from it, a level stroke after a level stroke only moves its end, anything
    else starts with an M."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.at: tuple[int, int] | None = None

    def stroke(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        if start != self.at:
            self.parts.append(f"M{start[0]} {start[1]}")
        level = start[1] == end[1]
        if level and start == self.at and self.parts[-1].startswith("H"):
            self.parts[-1] = f"H{end[0]}"
        else:
            self.parts.append(f"H{end[0]}" if level else f"V{end[1]}")
        self.at = end

    @property
    def d(self) -> str:
        return "".join(self.parts)


def _percent(share: Fraction) -> str:
    """A share of the span as a percentage, two places half up, trailing zeros dropped: "17.58", "50"."""
    hundredths = whole(share * 10_000)
    return f"{hundredths // 100}.{hundredths % 100:02d}".rstrip("0").rstrip(".")


def _shekels(tick: Decimal) -> str:
    """An axis figure: "₪26" for a whole shekel, "₪4.50" for a half."""
    return f"₪{tick:.0f}" if tick % 1 == 0 else f"₪{money(tick)}"


def render_chart(found: Verdict, day: date) -> str:
    """The column's price chart on `day`, then its key and its table (the module's docstring); "" when no tracked day
    has a price."""
    if not found.priced:
        return ""
    days = sorted(found.days, key=lambda each: each.day)
    first = days[0].day
    span = (day - first).days + 1                   # today included
    last = span - 1                                 # today's x

    def x(seen: date) -> int:
        return (seen - first).days

    known = [(x(each.day), each.price, each.on_sale) for each in days if each.price is not None]
    if found.today_price is not None:               # today's point: the label's "Price today"
        known.append((last, found.today_price, found.counting))
    drawn = [*(price for _, price, _ in known), *([] if found.usual is None else [found.usual])]
    bottom, top, step = axis(min(drawn), max(drawn))

    def up(price: Decimal) -> int:
        return whole(Fraction(top - price) / Fraction(top - bottom) * PLOT)

    points = [(at, up(price), sale) for at, price, sale in known]
    pens = {"gap": _Pen(), "gap sale": _Pen(), "paid": _Pen(), "sale": _Pen()}
    line_at: dict[int, int] = {}                    # the line's height on each day it runs, dotted or drawn
    steps: list[tuple[int, int, int]] = []          # (x, from, to): where the line changes height
    for n, (at, level, sale) in enumerate(points):
        if n:
            before, was, was_sale = points[n - 1]
            away = at - before - 1                  # days with no price between the two
            dotted = "gap sale" if was_sale else "gap"            # the dotted line goes on in the colour it carries
            if 0 < away <= BRIDGE:
                pens[dotted].stroke((before + 1, was), (at, was))
                line_at.update((between, was) for between in range(before + 1, at))
            if away <= BRIDGE and was != level:
                owner = dotted if away else "sale" if sale or was_sale else "paid"
                pens[owner].stroke((at, was), (at, level))
                steps.append((at, was, level))
        pens["sale" if sale else "paid"].stroke((at, level), (at + 1, level))
        line_at[at] = level
    unread = [(x(each.day), TICK) for each in days if each.on_sale and each.price is None]
    if found.call == "price_unread":                # today on sale, its price not read
        unread.append((last, TICK))

    ticks = [bottom + step * n for n in range(int((top - bottom) / step) + 1)]          # bottom to top
    ax = "".join(f'<text x="{AXIS_X}" y="{up(tick) + 4}">{_shekels(tick)}</text>' for tick in reversed(ticks))
    paths = [("grid", "".join(f"M0 {up(tick)}H{span}" for tick in ticks[1:]))]
    over = []
    if found.usual is not None:                     # S2: a Deal or No deal
        level = up(found.usual)
        clear = [(at, level) for at in range(span) if at not in line_at or abs(line_at[at] - level) >= CLEAR]
        if clear:
            paths.append(("usual", _line(clear)))
        late = [(height, height) for at, height in line_at.items() if 10 * (at + 1) > 7 * span]   # the last 30%
        late += [(min(was, to), max(was, to)) for at, was, to in steps if 10 * (at + 1) > 7 * span]
        above = not any(low <= level - 1 and high >= level - 21 for low, high in late)
        below = level <= PLOT - 20 and not any(low <= level + 21 and high >= level + 1 for low, high in late)
        y = level - LIFT if above or not below else level + 15
        over.append(f'<text class="usually" x="100%" dx="-12" y="{y}">{text(chart_label("usually", found.usual))}'
                    "</text>")
    paths += [(name, pens[name].d) for name in ("gap", "gap sale", "paid", "sale") if pens[name].parts]
    if unread:
        paths.append(("unread", _line(unread)))
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

    if found.today_price is not None:               # one dot, its price, and "today" under the price
        mark = "sale" if found.counting else "paid"
        height = up(found.today_price)
        now = (f'<circle class="{mark}" cy="{height}" r="4.5"/>'
               f'<text class="{mark}" x="{NOW_X}" y="{height + 5}">₪{money(found.today_price)}</text>'
               f'<text class="end" x="{NOW_X}" y="{height + 5 + WORD_DROP}">{text(TODAY_WORD)}</text>')
    else:
        now = f'<text class="end" x="{NOW_X}" y="{DATES_Y}">{text(TODAY_WORD)}</text>'

    marks = [*([("sale", CHART_KEY[0])] if pens["sale"].parts else []),
             *([("unread", CHART_KEY[1])] if unread else [])]
    key = " · ".join(f'<i class="{name}"></i>{text(words)}' for name, words in marks)
    key = f'<p class="key">{key}</p>' if marks else ""

    ends = extremes(found)                          # the design's call 3: today counts; never None here
    cells = [(head, f"₪{money(price)}<small>{text(TODAY_WORD if seen is None else short_day(seen))}</small>")
             for head, (price, seen) in zip(STATS_HEADS[:2], ends, strict=True)]
    if found.today_price is not None:
        cells.append((STATS_HEADS[2], f"₪{money(found.today_price)}"))
    heads = "".join(f'<th scope="col">{text(head)}</th>' for head, _ in cells)
    figures = "".join(f"<td>{figure}</td>" for _, figure in cells)

    return (f'<div class="history"><div class="chart"><svg class="ax" aria-hidden="true">{ax}</svg>'
            f'<div class="plot"><svg class="lines" role="img" aria-label="{escape(chart_summary(found))}" '
            f'viewBox="0 0 {span} {PLOT}" preserveAspectRatio="none">{lines}</svg>'
            f'<svg class="over" aria-hidden="true">{"".join(over)}</svg></div>'
            f'<svg class="now" aria-hidden="true">{now}</svg></div>'
            f'{key}<table class="stats"><tr>{heads}</tr><tr>{figures}</tr></table></div>')

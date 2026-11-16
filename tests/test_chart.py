"""The price chart (`shopper.chart`; docs/site-look.md, "The chart"; the site-look plan's Task 5 and its "Where the
design leaves room", "The chart, call by call"): a ₪ axis, the dates along the bottom, step lines, today's prices at
the right end, then the key and the table; and its words (`shopper.words`: CHART_KEY, `chart_label`).

Most verdicts are built by hand, since the chart is a function of the verdict, the day and today's shelf price alone;
the cases that turn on a day the column could not read (a promotion hole between two tracked days, and the calls that
know no price today) go through `shopper.verdict.verdict`, with pairs and column-days built as tests/test_verdict.py
builds them. The chart is read as XML. The heights are worked by hand from the axis rule and written out. Every figure
is synthetic."""
import random
import re
import xml.etree.ElementTree as ElementTree
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from basket.check import PRONOUNS, flatten
from shopper import chart
from shopper.deals import to_agora
from shopper.history import READ_DAYS, ColumnDay, Pair, Point
from shopper.verdict import Day, Verdict, verdict
from shopper.words import CHART_KEY, NEVER, STATS_HEADS, chart_label, chart_summary, short_day

DAY = date(2026, 11, 20)
COLUMN = "shufersal-deal"
CODE = "2000000000046"   # a synthetic GS1 code
D = Decimal
COUNTING = ("deal", "no_deal", "mostly_unknown")      # the calls with a promotion counting today (built by hand)


def back(n: int) -> date:
    return DAY - timedelta(days=n)


# ---- verdicts by hand ----

def _shelf(n: int, listed: str = "5.00") -> Day:
    """n days back at the listed price, not on sale."""
    return Day(back(n), D(listed), D(listed), False)


def _sale(n: int, price: str, listed: str = "5.00") -> Day:
    """n days back, on sale at the day price `price`."""
    return Day(back(n), D(listed), D(price), True)


def _unknown(n: int, listed: str = "5.00") -> Day:
    """n days back, a sale day of unknown price."""
    return Day(back(n), D(listed), None, True)


def _verdict(days, today: str | None = "4.00", usual: str | None = "5.00", call: str = "deal",
             column: str = COLUMN) -> Verdict:
    """A verdict over `days` as given (in any order); `today` and `usual` None when unknown; a promotion counts today
    on the calls in COUNTING."""
    today_price = None if today is None else D(today)
    usual_price = None if usual is None else D(usual)
    saving = None if today_price is None or usual_price is None else usual_price - today_price
    return Verdict(column=column, call=call, days=tuple(days), today_price=today_price,
                   struct={"per": "unit"} if call in COUNTING else None, usual=usual_price, saving=saving,
                   last_low=None, last_sale=None, on_sale_today=call in (*COUNTING, "price_unread"))


def _daily(first: date, today: date, listed: str = "5.00") -> list[Day]:
    """Every day from `first` to the day before `today` at the listed price, not on sale."""
    return [Day(first + timedelta(days=n), D(listed), D(listed), False) for n in range((today - first).days)]


# ---- verdicts through shopper.verdict ----

def _struct(price: str = "4.00", *, start: date = DAY, end: date = DAY + timedelta(days=7)) -> dict:
    """A wide, valid fixed-price promotion struct as the items table holds it, read back; from today unless said."""
    exact = Fraction(price)
    return {"promotion_id": "1", "description": "מבצע בדיקה", "start": start, "end": end, "kind": "3",
            "buy": D("1.000"), "price": to_agora(exact), "price_exact": str(exact), "per": "unit", "low": None,
            "high": None, "valid": True, "why": None, "restrictions": [], "programmes": [], "min_spend": None,
            "stores": 4, "wide": True}


def _point(day: date, listed: str = "5.00", *structs: dict) -> Point:
    on_promotion = any(found["start"] <= day <= found["end"] for found in structs)
    return Point(day=day, listed=D(listed), low=D(listed), high=D(listed), listing=4, wide=True,
                 on_promotion=on_promotion, next_start=None, promotions=tuple(structs))


def _column_days(holes=(), promo_holes=()) -> dict[tuple[str, date], ColumnDay]:
    """The column's days from 90 back to the day, each a record with its promotions read unless it is a price hole (1
    of 4 stores with a file) or a promotion hole (1 of 4 with a promotion file)."""
    found = {}
    for n in range(READ_DAYS, -1, -1):
        day = back(n)
        with_file = 1 if day in holes else 4
        promo_hole = day in promo_holes
        found[(COLUMN, day)] = ColumnDay(column=COLUMN, slug="shufersal", day=day, present=True, hole=day in holes,
                                         promo_hole=promo_hole, promotions_error=None, included=4,
                                         with_file=with_file, counted=with_file,
                                         promo_files=1 if promo_hole else with_file)
    return found


def _judged(points, **days) -> Verdict:
    pair = Pair(column=COLUMN, code=CODE, points={point.day: point for point in points})
    return verdict(pair, COLUMN, _column_days(**days), DAY)


def _history(listed: str = "5.00") -> list[Point]:
    """Five days back to yesterday at the listed price, no promotion."""
    return [_point(back(n), listed) for n in range(5, 0, -1)]


# ---- reading the chart ----

def _read(html: str) -> dict[str, ElementTree.Element | None]:
    """The chart's parts by name: the axis, the lines, the overlay, the today column, the key and the table (None
    without one), each checked to be where the markup's order puts it."""
    history = ElementTree.fromstring(html)
    assert (history.tag, history.get("class")) == ("div", "history")
    drawing, key, *table = history
    assert (drawing.tag, drawing.get("class"), key.tag, key.get("class")) == ("div", "chart", "p", "key")
    ax, plot, now = drawing
    lines, over = plot
    assert [(each.tag, each.get("class")) for each in (ax, plot, lines, over, now)] == [
        ("svg", "ax"), ("div", "plot"), ("svg", "lines"), ("svg", "over"), ("svg", "now")]
    assert [(each.tag, each.get("class")) for each in table] in ([], [("table", "stats")])
    return {"ax": ax, "lines": lines, "over": over, "now": now, "key": key, "table": table[0] if table else None}


def _paths(lines: ElementTree.Element) -> dict[str, str]:
    return {path.get("class"): path.get("d") for path in lines.iter("path")}


def _pieces(d: str) -> list[list[tuple[int, int, Decimal]]]:
    """A path's subpaths, each from an M, as its horizontal pieces (x from, x to, height)."""
    found: list[list[tuple[int, int, Decimal]]] = []
    x, y = 0, D(0)
    for command, a, b in re.findall(r"([MHV])([\d.]+)(?: ([\d.]+))?", d):
        if command == "M":
            x, y = int(a), D(b)
            found.append([])
        elif command == "H":
            found[-1].append((x, int(a), y))
            x = int(a)
        else:
            y = D(a)
    return found


def _covered(d: str, x: int) -> list[Decimal]:
    """The heights a path draws across the day at x."""
    return [y for run in _pieces(d) for start, end, y in run if start <= x and x + 1 <= end]


def _now(now: ElementTree.Element) -> list[tuple]:
    """The today column's marks: a dot as ("circle", its class, its height), a label as ("text", its class, its y,
    its words)."""
    return [("circle", each.get("class"), int(each.get("cy"))) if each.tag == "circle" else
            ("text", each.get("class"), int(each.get("y")), each.text) for each in now]


def _dates(over: ElementTree.Element) -> list[tuple]:
    """The overlay's dates, the usual price's label left out: a mark as ("line", its x), a date as (its words, its
    class, its x)."""
    return [("line", each.get("x1")) if each.tag == "line" else (each.text, each.get("class"), each.get("x"))
            for each in over if each.get("class") != "usually"]


def _table(table: ElementTree.Element) -> list[tuple[str, str, str | None]]:
    """The table's cells: its head, its figure, and the day under it (None without)."""
    heads, figures = table
    assert [cell.get("scope") for cell in heads] == ["col"] * len(heads)
    return [(head.text, cell.text, None if cell.find("small") is None else cell.find("small").text)
            for head, cell in zip(heads, figures, strict=True)]


def _rich() -> Verdict:
    """60 tracked days: price changes, two sale runs, sale days of unknown price, a deal today."""
    days = [_shelf(n, "5.50" if n > 40 else "5.00") for n in range(60, 0, -1)]
    for n in (30, 29, 28, 9, 8):
        days[60 - n] = _sale(n, "4.20")
    for n in (20, 19):
        days[60 - n] = _unknown(n)
    return _verdict(days, today="3.90")


# ---- the axis ----

@pytest.mark.parametrize(("low", "high", "expected"), [
    ("17.90", "24.90", (16, 26, 2)), ("5.00", "5.00", (4, 6, 1)), ("6.90", "8.90", (6, 9, 1)),
    ("4.20", "4.50", (D("4.0"), D("5.0"), D("0.5"))), ("3.00", "3.40", (D("2.5"), D("3.5"), D("0.5"))),
    ("10.10", "13.90", (9, 14, 1)), ("10.10", "14.90", (8, 16, 2)), ("19.90", "69.90", (0, 80, 20)),
    ("99.90", "129.90", (90, 130, 10)), ("1000.00", "1450.00", (800, 1600, 200)), ("0.40", "0.40", (0, 2, 1))])
def test_the_axis_takes_round_steps(low, high, expected):
    """Steps of 1, 2, 5 times a power of ten, the smallest that holds every price in two to five; half a shekel for
    prices less than a shekel apart; room on the side with less for one price or two close ones; a step lower when
    the lowest price would be within 8% of the bottom."""
    assert chart.axis(D(low), D(high)) == expected


def test_no_price_sits_on_the_date_line():
    """Review Focus 2: over 1,000 pairs of shekel prices from 0.10 to 2,000.00, half of them less than ₪1.50 apart,
    two to five round steps that hold both, and the lowest at least 8% of the axis above its bottom unless the bottom
    is 0. Never an error."""
    rng = random.Random(36)
    steps = {D("0.5"), *(D(m) * 10 ** k for k in range(9) for m in (1, 2, 5))}
    for n in range(1_000):
        first = rng.randint(10, 200_000)
        second = min(first + rng.randint(0, 150), 200_000) if n % 2 else rng.randint(10, 200_000)
        low, high = sorted((D(first) / 100, D(second) / 100))
        bottom, top, step = chart.axis(low, high)
        count = (top - bottom) / step
        assert step in steps and count == int(count) and 2 <= count <= 5, (low, high)
        assert bottom % step == 0 and bottom <= low and top >= high, (low, high)
        assert step != D("0.5") or 0 < high - low < 1, (low, high)
        assert bottom == 0 or low - bottom >= D("0.08") * (top - bottom), (low, high)
    # beyond any price (₪1 to ₪1,000,000,000,000), no step holds it in five: refused, never drawn wrong
    with pytest.raises(ValueError, match="no axis"):
        chart.axis(D("1.00"), D("1000000000000.00"))


def test_the_axis_holds_every_price_drawn_today_included():
    """The axis runs over the shelf prices, the sale prices, the usual price and today's two prices, so today's dots
    lie on the plot: a shelf price today above every day before and a sale price today below every one. Its words at
    the left, ₪ and whole shekels, top to bottom at each step's height; a gridline at each step above the bottom."""
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="2.00", usual="5.00")
    parts = _read(chart.render_chart(found, DAY, D("6.00")))
    # axis(2.00, 6.00) is (1, 6, 1): 40 pixels a shekel, ₪6 at 0, ₪5 at 40, ₪2 at 160
    assert [(each.get("x"), each.get("y"), each.text) for each in parts["ax"]] == [
        ("40", "4", "₪6"), ("40", "44", "₪5"), ("40", "84", "₪4"), ("40", "124", "₪3"), ("40", "164", "₪2"),
        ("40", "204", "₪1")]
    assert [entry[:3] for entry in _now(parts["now"]) if entry[0] == "circle"] == [
        ("circle", "listed", 0), ("circle", "sale", 160)]
    paths = _paths(parts["lines"])
    assert paths["grid"] == "M0 160H10M0 120H10M0 80H10M0 40H10M0 0H10"
    assert paths["listed"] == "M0 40H9V0H10" and paths["sale"] == "M9 160H10"
    # half a shekel for prices less than a shekel apart, written with its agorot
    found = _verdict([_shelf(n, "4.50") for n in range(9, 0, -1)], today="4.20", usual="4.50", call="no_deal")
    parts = _read(chart.render_chart(found, DAY, D("4.50")))
    assert [(each.get("y"), each.text) for each in parts["ax"]] == [("4", "₪5"), ("104", "₪4.50"), ("204", "₪4")]
    assert _paths(parts["lines"])["grid"] == "M0 100H10M0 0H10"


# ---- how it is drawn ----

def test_only_the_lines_scale_and_they_hold_no_text():
    """Design test 4: four SVGs, and the only one with a viewBox is the lines', which stretches
    (preserveAspectRatio="none") and holds no text; no width, height or style anywhere, so the stylesheet sizes
    everything and no word shrinks."""
    html = chart.render_chart(_rich(), DAY, D("5.00"))
    svgs = re.findall(r"<svg[^>]*>", html)
    assert len(svgs) == 4
    (scaled,) = [tag for tag in svgs if "viewBox" in tag]
    assert scaled.startswith('<svg class="lines" ') and scaled.endswith(' preserveAspectRatio="none">')
    lines = re.search(r'<svg class="lines".*?</svg>', html).group(0)
    assert "<text" not in lines and "</text>" not in lines
    assert list(_read(html)["lines"].iter("text")) == []
    assert not re.search(r"\s(width|height|style)=", html) and "<style" not in html


def test_a_day_is_one_unit_and_today_is_the_last():
    """Across: a unit a day from the first tracked day, today the last, so the span counts today; never a fixed 90
    days. With today's shelf price, the shelf line of a history listed every day runs to the span's end."""
    for tracked, span in ((13, 14), (READ_DAYS, 91)):
        found = _verdict([_shelf(n) for n in range(tracked, 0, -1)], today="5.00", usual=None, call="no_sale")
        parts = _read(chart.render_chart(found, DAY, D("5.00")))
        assert parts["lines"].get("viewBox") == f"0 0 {span} 200"
        assert _paths(parts["lines"])["listed"] == f"M0 100H{span}"
    # the first tracked day sets the start, wherever it sits in the window
    found = _verdict([_shelf(3), _shelf(1)], today="5.00", usual=None, call="no_sale")
    parts = _read(chart.render_chart(found, DAY, D("5.00")))
    assert parts["lines"].get("viewBox") == "0 0 4 200"
    assert _paths(parts["lines"])["listed"] == "M0 100H1M2 100H4"


def test_a_day_with_no_record_is_a_gap_in_every_line():
    """A promotion hole between two tracked days is not tracked (S0): the shelf, sale and usual lines each stop at the
    end of the day before it and start again with an M at the day after it, nothing drawn across it."""
    sale = _struct("4.00", start=back(4), end=back(2))
    points = [_point(back(5)), *(_point(back(n), "5.00", sale) for n in (4, 3, 2)), _point(back(1)),
              _point(DAY, "5.00", _struct("3.00"))]
    found = _judged(points, promo_holes={back(3)})
    assert [each.day for each in found.days] == [back(5), back(4), back(2), back(1)]
    assert (found.call, found.usual, found.today_price) == ("deal", D("5.00"), D("3.00"))
    paths = _paths(_read(chart.render_chart(found, DAY, D("5.00")))["lines"])
    # axis(3.00, 5.00) is (2, 5, 1): ₪5 at 0, ₪4 at 67, ₪3 at 133; the hole at x 2
    assert paths["listed"] == "M0 0H2M3 0H6"
    assert paths["usual"] == "M0 0H2M3 0H6"
    assert paths["sale"] == "M1 67H2M3 67H4M5 133H6"
    for name in ("listed", "usual", "sale"):
        assert _covered(paths[name], 2) == [], name


def test_the_shelf_price_every_day_and_the_sale_price_on_sale_days():
    """The shelf price on every tracked day, sale days included; the sale price on the sale days with a price, at its
    own height, each run of them a line of its own; a day off sale has none."""
    days = [_shelf(5), _sale(4, "4.00"), _sale(3, "4.50"), _shelf(2), _sale(1, "4.00")]
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.00", usual="5.00"), DAY))["lines"])
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0, ₪4.50 at 50, ₪4 at 100
    assert paths["listed"] == "M0 0H5"
    assert paths["sale"] == "M1 100H2V50H3M4 100H6"
    for off_sale in (0, 3):
        assert _covered(paths["sale"], off_sale) == []


def test_the_shelf_line_runs_through_today_only_with_todays_shelf_price():
    """With today's shelf price the shelf line's last run ends at the span's end and today's column has its dot and
    its price; without it (price_unread, unread_today, not_sold, too_few) the line ends the day before and the
    column holds "today" alone."""
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="5.00", usual=None, call="no_sale")
    parts = _read(chart.render_chart(found, DAY, D("5.00")))
    assert _paths(parts["lines"])["listed"] == "M0 100H10"
    assert _now(parts["now"]) == [("circle", "listed", 100), ("text", "listed now", 105, "₪5.00"),
                                  ("text", "end", 217, "today")]
    parts = _read(chart.render_chart(found, DAY))
    assert _paths(parts["lines"])["listed"] == "M0 100H9"
    assert _now(parts["now"]) == [("text", "end", 217, "today")]
    # the calls with no price today, through the verdict: the line ends the day before, "today" alone
    unread = _point(DAY, "5.00", {**_struct("13.00"), "valid": False})       # listed across the column, not read
    for found in (_judged([*_history(), unread]), _judged([*_history(), _point(DAY, "5.00", _struct())],
                                                          promo_holes={DAY})):
        assert found.call in ("price_unread", "unread_today") and found.today_price is None
        parts = _read(chart.render_chart(found, DAY))
        assert _paths(parts["lines"])["listed"] == "M0 100H5"
        assert _now(parts["now"]) == [("text", "end", 217, "today")]


def test_a_sale_that_starts_today_is_a_short_green_line_ending_in_its_dot():
    """Review Focus 5: a deal whose sale starts today draws today's sale price as a sale line one day long, at the
    span's end, its dot at the same height; the key names it."""
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="4.00", usual="5.00")
    html = chart.render_chart(found, DAY, D("5.00"))
    # axis(4.00, 5.00) is (3, 5, 1): ₪4 at 100; the span is 10
    assert '<path class="sale" d="M9 100H10"/>' in html
    parts = _read(html)
    assert ("circle", "sale", 100) in _now(parts["now"])
    assert "".join(parts["key"].itertext()) == "shelf price · on sale"


def test_a_sale_day_of_unknown_price_is_a_tick_on_the_date_line():
    """A sale day whose price could not be read (S1) is a tick standing on the date line under that day, consecutive
    ones as one; no sale line and no price for it, the shelf line still drawn. price_unread adds today's."""
    days = [_shelf(3), _unknown(2), _shelf(1)]
    html = chart.render_chart(_verdict(days, today="4.00", usual="5.00"), DAY)
    assert '<path class="unread" d="M1 196.5H2"/>' in html
    days = [_shelf(5), _unknown(4), _unknown(3), _shelf(2), _unknown(1)]
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.00", usual="5.00"), DAY))["lines"])
    assert paths["unread"] == "M1 196.5H3M4 196.5H5" and chart.TICK == D("196.5")
    assert paths["listed"] == "M0 0H5"       # the shelf price still drawn on those days
    # price_unread: today's tick, and no price today
    parts = _read(chart.render_chart(_verdict(days, today=None, usual=None, call="price_unread"), DAY))
    assert _paths(parts["lines"])["unread"] == "M1 196.5H3M4 196.5H6"
    assert _now(parts["now"]) == [("text", "end", 217, "today")]
    unread = _point(DAY, "5.00", {**_struct("13.00"), "valid": False})
    found = _judged([*_history(), unread])
    assert found.call == "price_unread"
    paths = _paths(_read(chart.render_chart(found, DAY))["lines"])
    assert paths["unread"] == "M5 196.5H6" and "sale" not in paths
    # unread_today knows no sale today: no tick under today
    found = _judged([*_history(), _point(DAY, "5.00", _struct())], promo_holes={DAY})
    assert found.call == "unread_today" and "unread" not in _paths(_read(chart.render_chart(found, DAY))["lines"])


def test_todays_prices_are_written_in_their_lines_colours():
    """Today's shelf price in the shelf line's colour and today's sale price in the sale line's, each beside its dot,
    the lower (what the shopper pays) in bold; two labels closer than 17 pixels moved apart, and none below the date
    line."""
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="4.00", usual="5.00")
    assert _now(_read(chart.render_chart(found, DAY, D("5.00")))["now"]) == [
        ("circle", "listed", 0), ("text", "listed", 5, "₪5.00"), ("circle", "sale", 100),
        ("text", "sale now", 105, "₪4.00"), ("text", "end", 217, "today")]
    # two prices 10 pixels apart: axis(4.95, 5.00) is (4.5, 5.5, 0.5), ₪5.00 at 100 and ₪4.95 at 110
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="4.95", usual="5.00", call="no_deal")
    assert _now(_read(chart.render_chart(found, DAY, D("5.00")))["now"]) == [
        ("circle", "listed", 100), ("text", "listed", 105, "₪5.00"), ("circle", "sale", 110),
        ("text", "sale now", 122, "₪4.95"), ("text", "end", 217, "today")]
    # one price twice, at the foot: axis(0.10, 1.90) is (0, 2, 1), ₪0.10 at 190; both bold, the lower label at 200
    days = [_unknown(3, "1.90"), _unknown(2, "1.90"), _shelf(1, "1.90")]
    found = _verdict(days, today="0.10", usual=None, call="mostly_unknown")
    marks = _now(_read(chart.render_chart(found, DAY, D("0.10")))["now"])
    assert marks == [("circle", "listed", 190), ("text", "listed now", 188, "₪0.10"), ("circle", "sale", 190),
                     ("text", "sale now", 205, "₪0.10"), ("text", "end", 217, "today")]
    centres = [mark[2] - 5 for mark in marks[:-1] if mark[0] == "text"]
    assert centres[1] - centres[0] == chart.LABEL_GAP == 17 and max(centres) <= 200


def test_the_usual_line_and_its_label():
    """With a Deal or No deal, the usual price is a line over the shelf line's days, gaps and all, its words at the
    right: above the line, unless a shelf or sale price on the last 30% of the span's days runs within 21 pixels above
    it, then below; above again when a price runs within 21 pixels below too."""
    def drawn(listed, today, call="deal", shelf_today="5.00"):
        days = [_shelf(9 - x, price) for x, price in enumerate(listed)]
        return _read(chart.render_chart(_verdict(days, today=today, usual="5.00", call=call), DAY, D(shelf_today)))

    def label(parts):
        (said,) = [each for each in parts["over"] if each.get("class") == "usually"]
        assert [each.get("class") for each in parts["over"]][0] == "usually"       # first in the overlay
        return said.get("x"), said.get("dx"), int(said.get("y")), said.text

    # axis(4.00, 6.00) is (3, 6, 1): ₪6 at 0, ₪5.10 at 60, ₪5 at 67, ₪4 at 133; x 7 to 9 are the last 30%
    quiet = ["6.00", "6.00", *["5.00"] * 7]
    parts = drawn(quiet, "4.00")
    assert _paths(parts["lines"])["usual"] == "M0 67H10"
    assert _paths(parts["lines"])["listed"] == "M0 0H2V67H10"
    assert label(parts) == ("100%", "-12", 61, chart_label("usually", D("5.00")))
    # ₪5.10 on the last days and today, 7 pixels above: below the line
    busy = ["6.00", "6.00", *["5.00"] * 5, "5.10", "5.10"]
    assert label(drawn(busy, "4.00", shelf_today="5.10"))[2] == 82
    # ₪5.10 before the last 30% only (x 6): above; on its first day alone (x 7): below
    assert label(drawn(["6.00", "6.00", *["5.00"] * 4, "5.10", "5.00", "5.00"], "4.00"))[2] == 61
    assert label(drawn(["6.00", "6.00", *["5.00"] * 5, "5.10", "5.00"], "4.00"))[2] == 82
    # busy below too, today's sale ₪4.85 15 pixels under it (axis (4, 6, 1), ₪5 at 100): above
    assert label(drawn(busy, "4.85", call="no_deal", shelf_today="5.10"))[2] == 94
    # at the axis's top (axis (3, 5, 1), ₪5 at 0) there is no room above: below
    assert label(drawn(["5.00"] * 9, "4.00"))[2] == 15
    # no usual line nor label without a Deal or No deal
    parts = _read(chart.render_chart(_verdict([_shelf(2), _shelf(1)], today="5.00", usual=None, call="no_sale"), DAY))
    assert "usual" not in _paths(parts["lines"])
    assert [each for each in parts["over"] if each.get("class") == "usually"] == []


def test_the_dates_by_span():
    """Along the bottom: the first tracked day's date at the left; under 46 days a mark and a date every seventh day
    back from today, from 46 days a mark and a name at each month's first day; never one on today, which the today
    column names. A name nearer than 22% of the span to the first date or 16% to today is hidden on a phone (its
    class), its mark kept."""
    found = _verdict(_daily(date(2026, 11, 1), date(2026, 11, 14)), today="5.00", usual=None, call="no_sale")
    parts = _read(chart.render_chart(found, date(2026, 11, 14)))
    assert parts["lines"].get("viewBox") == "0 0 14 200"
    assert _dates(parts["over"]) == [("1 Nov", None, None), ("line", "42.86%"), ("7 Nov", None, "42.86%")]
    first, line, mark = parts["over"]
    assert (first.get("y"), line.get("y1"), line.get("y2"), line.get("x2"), mark.get("dx"), mark.get("y")) == (
        "217", "200", "206", "42.86%", "5", "217")
    found = _verdict(_daily(date(2026, 8, 16), date(2026, 11, 13)), today="5.00", usual=None, call="no_sale")
    parts = _read(chart.render_chart(found, date(2026, 11, 13)))
    assert parts["lines"].get("viewBox") == "0 0 90 200"
    assert _dates(parts["over"]) == [("16 Aug", None, None), ("line", "17.78%"), ("Sep", "near", "17.78%"),
                                     ("line", "51.11%"), ("Oct", None, "51.11%"), ("line", "85.56%"),
                                     ("Nov", "near", "85.56%")]
    assert chart.NEAR == (Fraction(22, 100), Fraction(84, 100))
    # the weeks up to 45 days, the months from 46; a mark two days after the first date keeps its mark alone (NAMED)
    assert chart.WEEKLY_UNDER == 46
    names, marks = {}, {}
    for span in (45, 46):
        first = date(2026, 11, 13) - timedelta(days=span - 1)
        found = _verdict(_daily(first, date(2026, 11, 13)), today="5.00", usual=None, call="no_sale")
        over = _read(chart.render_chart(found, date(2026, 11, 13)))["over"]
        names[span] = [each.text for each in over if each.tag == "text"]
        marks[span] = [each.get("x1") for each in over if each.tag == "line"]
    assert names == {45: ["30 Sep", "9 Oct", "16 Oct", "23 Oct", "30 Oct", "6 Nov"], 46: ["29 Sep", "Nov"]}
    assert marks == {45: ["4.44%", "20%", "35.56%", "51.11%", "66.67%", "82.22%"], 46: ["4.35%", "71.74%"]}


def test_a_name_never_runs_into_the_first_date_or_out_of_the_plot():
    """At every width, a date's name is written only within NAMED's share of the span, its mark always: nearer the
    first date it would run into the first date's words, nearer today out of the plot into the today column (fix
    round 1, measured: the module's NAMED). An edge itself is written; the upper one only a span longer than the
    window's 91 days can reach, so a synthetic 100-day span pins it. Apart from it, the phone's near rule takes its
    edges as shown too."""
    assert chart.NAMED == (Fraction(8, 100), Fraction(91, 100))

    def dates(first: date, span: int) -> list[tuple]:
        today = first + timedelta(days=span - 1)
        found = _verdict(_daily(first, today), today="5.00", usual=None, call="no_sale")
        return _dates(_read(chart.render_chart(found, today))["over"])

    # the review's spans: a week mark a day or two after the first date, 3.33% to 4.44% in
    assert dates(date(2026, 11, 8), 23) == [("8 Nov", None, None), ("line", "4.35%"), ("line", "34.78%"),
                                            ("16 Nov", None, "34.78%"), ("line", "65.22%"), ("23 Nov", None, "65.22%")]
    assert dates(date(2026, 11, 1), 30)[:3] == [("1 Nov", None, None), ("line", "3.33%"), ("line", "26.67%")]
    # the lower edge: 8% is written, 7.84% is not
    assert dates(date(2026, 10, 28), 50) == [("28 Oct", None, None), ("line", "8%"), ("Nov", "near", "8%"),
                                             ("line", "68%"), ("Dec", None, "68%")]
    assert dates(date(2026, 10, 28), 51) == [("28 Oct", None, None), ("line", "7.84%"), ("line", "66.67%"),
                                             ("Dec", None, "66.67%")]
    # the upper edge, on 91 days: 90.11% is written, 91.21% is not
    assert dates(date(2026, 9, 10), 91)[-2:] == [("line", "90.11%"), ("Dec", "near", "90.11%")]
    assert dates(date(2026, 9, 9), 91)[-2:] == [("Nov", None, "58.24%"), ("line", "91.21%")]
    # the upper edge itself, on a synthetic 100 days: 1 November at x 91 (91%) is written, at x 92 (92%) is not
    assert dates(date(2026, 8, 2), 100)[-2:] == [("line", "91%"), ("Nov", "near", "91%")]
    assert dates(date(2026, 8, 1), 100)[-2:] == [("Oct", None, "61%"), ("line", "92%")]
    # NEAR's edges are shown on a phone: 22% and 84% exactly carry no near class
    assert dates(date(2026, 10, 21), 50)[1:3] == [("line", "22%"), ("Nov", None, "22%")]
    assert dates(date(2026, 10, 20), 50)[-2:] == [("line", "84%"), ("Dec", None, "84%")]


def test_a_phone_shows_every_other_weeks_name_from_28_days():
    """On a weekly span of ALTERNATE_WEEKS (28) days or more, the names an odd number of weeks before today (7, 21, 35
    days back) are hidden on a phone too (`class="near"`), so the names a 178-pixel plot shows are 14 days apart and
    never touch (fix round 2); every mark stays, and a desktop shows every name as before. Under 28 days every week's
    name is far enough apart already. Today is 30 November in each."""
    assert chart.ALTERNATE_WEEKS == 28

    def dates(span: int) -> list[tuple]:
        today = date(2026, 11, 30)
        found = _verdict(_daily(today - timedelta(days=span - 1), today), today="5.00", usual=None, call="no_sale")
        return _dates(_read(chart.render_chart(found, today))["over"])

    # 27 days: 7 days back (23 Nov) shown; 21 back hidden by NEAR alone (18.52%)
    assert dates(27) == [("4 Nov", None, None), ("line", "18.52%"), ("9 Nov", "near", "18.52%"), ("line", "44.44%"),
                         ("16 Nov", None, "44.44%"), ("line", "70.37%"), ("23 Nov", None, "70.37%")]
    # 28 days: 7 days back hidden (71.43%, inside NEAR), 14 back shown
    assert dates(28) == [("3 Nov", None, None), ("line", "21.43%"), ("9 Nov", "near", "21.43%"), ("line", "46.43%"),
                         ("16 Nov", None, "46.43%"), ("line", "71.43%"), ("23 Nov", "near", "71.43%")]
    # 45 days: 7, 21 and 35 back hidden, 14 and 28 back shown; 42 back (4.44%) a mark alone
    assert dates(45) == [("17 Oct", None, None), ("line", "4.44%"), ("line", "20%"), ("26 Oct", "near", "20%"),
                         ("line", "35.56%"), ("2 Nov", None, "35.56%"), ("line", "51.11%"),
                         ("9 Nov", "near", "51.11%"), ("line", "66.67%"), ("16 Nov", None, "66.67%"),
                         ("line", "82.22%"), ("23 Nov", "near", "82.22%")]


def test_a_short_history_has_its_first_date_and_today():
    """Review Focus 5: one tracked day and today: its date at the left, "today" at the right, no mark between."""
    found = _verdict([_shelf(1)], today="4.00", usual="5.00")
    parts = _read(chart.render_chart(found, DAY, D("5.00")))
    assert parts["lines"].get("viewBox") == "0 0 2 200"
    assert _dates(parts["over"]) == [("19 Nov", None, None)]
    assert _now(parts["now"])[-1] == ("text", "end", 217, "today")


# ---- the key and the table ----

def test_the_key_names_only_the_marks_drawn():
    """After the chart, CHART_KEY's words for each kind of mark drawn, today's included, each after a swatch of its
    class, in CHART_KEY's order and set apart by " · "."""
    def key(found, shelf_today=None):
        found_key = _read(chart.render_chart(found, DAY, shelf_today))["key"]
        return [each.get("class") for each in found_key], "".join(found_key.itertext())

    assert key(_verdict([_shelf(2), _shelf(1)], today="5.00", usual=None, call="no_sale"), D("5.00")) == (
        ["listed"], "shelf price")
    assert key(_verdict([_shelf(2), _sale(1, "4.00")], today="5.00", usual=None, call="no_sale")) == (
        ["listed", "sale"], "shelf price · on sale")
    assert key(_verdict([_shelf(2), _unknown(1)], today="5.00", usual=None, call="no_sale")) == (
        ["listed", "unread"], "shelf price · on sale, price not read")
    assert key(_verdict([_sale(3, "4.00"), _unknown(2), _shelf(1)])) == (
        ["listed", "sale", "unread"], "shelf price · on sale · on sale, price not read")
    # today's marks count: a sale from today, a sale today whose price was not read
    assert key(_verdict([_shelf(2), _shelf(1)]), D("5.00"))[0] == ["listed", "sale"]
    assert key(_verdict([_shelf(2), _shelf(1)], today=None, usual=None, call="price_unread"))[0] == [
        "listed", "unread"]
    assert CHART_KEY == ("shelf price", "on sale", "on sale, price not read")


def test_the_table_counts_today_in_lowest_and_highest():
    """The design's call 3: Lowest and Highest over the tracked days' day prices and today's price, each over the
    latest day at that price, "today" when it is today's; Usual with a Deal or No deal; Today with today's price. The
    design's example, a deal at a new low; no table with nothing to put in it."""
    days = [Day(date(2026, 11, 10), D("22.90"), D("22.90"), False),
            Day(date(2026, 11, 11), D("26.90"), D("19.90"), True),
            Day(date(2026, 11, 12), D("22.90"), D("22.90"), False),
            Day(date(2026, 11, 13), D("24.90"), D("24.90"), False)]
    found = _verdict(days, today="17.90", usual="22.90")
    parts = _read(chart.render_chart(found, date(2026, 11, 14), D("22.90")))
    assert _table(parts["table"]) == [("Lowest", "₪17.90", "today"), ("Highest", "₪24.90", "13 Nov"),
                                      ("Usual", "₪22.90", None), ("Today", "₪17.90", None)]
    assert [head for head, _, _ in _table(parts["table"])] == list(STATS_HEADS)
    # no sale: no Usual
    found = _verdict([_shelf(2, "6.00"), _shelf(1)], today="5.00", usual=None, call="no_sale")
    assert _table(_read(chart.render_chart(found, DAY, D("5.00")))["table"]) == [
        ("Lowest", "₪5.00", "today"), ("Highest", "₪6.00", short_day(back(2))), ("Today", "₪5.00", None)]
    # no price today: no Today, the days before still give Lowest and Highest
    for found in (_judged([*_history(), _point(DAY, "5.00", _struct())], promo_holes={DAY}), _judged(_history())):
        assert found.call in ("unread_today", "not_sold")
        assert _table(_read(chart.render_chart(found, DAY))["table"]) == [
            ("Lowest", "₪5.00", short_day(back(1))), ("Highest", "₪5.00", short_day(back(1)))]
    # nothing known: no table
    found = _verdict([_unknown(2), _unknown(1)], today=None, usual=None, call="too_few")
    html = chart.render_chart(found, DAY)
    assert _read(html)["table"] is None and "<table" not in html


def test_the_text_alternative_is_the_summary(monkeypatch):
    """The lines are an image whose aria-label is `chart_summary`, escaped for an attribute; the other three SVGs are
    hidden from screen readers."""
    found = _verdict([_shelf(2), _sale(1, "4.00")], today="4.00")
    parts = _read(chart.render_chart(found, DAY, D("5.00")))
    assert parts["lines"].get("role") == "img"
    assert parts["lines"].get("aria-label") == chart_summary(found) == (
        "Price chart: usually ₪5.00, lowest ₪4.00, highest ₪5.00, today ₪4.00.")
    assert [parts[name].get("aria-hidden") for name in ("ax", "over", "now")] == ["true"] * 3
    monkeypatch.setattr(chart, "chart_summary", lambda found: 'Price "chart" & <more>')
    html = chart.render_chart(found, DAY, D("5.00"))
    assert 'aria-label="Price &quot;chart&quot; &amp; &lt;more&gt;"' in html
    assert _read(html)["lines"].get("aria-label") == 'Price "chart" & <more>'


# ---- simplicity, purity, size ----

def test_a_run_of_one_price_is_one_segment():
    """27 days at one price are one horizontal segment from the start (store first's first simplification); a change
    of price is one step, at the day it changes."""
    found = _verdict([_shelf(n) for n in range(27, 0, -1)], today="5.00", usual=None, call="no_sale")
    assert _paths(_read(chart.render_chart(found, DAY))["lines"])["listed"] == "M0 100H27"
    assert _paths(_read(chart.render_chart(found, DAY, D("5.00")))["lines"])["listed"] == "M0 100H28"
    found = _verdict([_shelf(n, "5.00" if n > 10 else "4.50") for n in range(27, 0, -1)], today="4.50", usual=None,
                     call="no_sale")
    # axis(4.50, 5.00) is (4.0, 5.0, 0.5): ₪5 at 0, ₪4.50 at 100
    assert _paths(_read(chart.render_chart(found, DAY))["lines"])["listed"] == "M0 0H17V100H27"


def test_no_chart_without_a_tracked_day():
    assert chart.render_chart(_verdict([]), DAY) == ""
    assert chart.render_chart(_verdict([]), DAY, D("5.00")) == ""
    new = _judged([_point(DAY, "5.00", _struct("4.00"))])        # first seen today
    assert new.call == "new" and new.days == ()
    assert chart.render_chart(new, DAY) == ""


def test_the_chart_is_the_same_bytes_twice():
    """A pure function: the same bytes twice, and whatever order the days come in."""
    days = [_shelf(9), _sale(8, "4.00"), _unknown(6), _shelf(5, "5.50"), _sale(3, "4.20"), _shelf(1)]
    found = _verdict(days, today="4.10")
    drawn = chart.render_chart(found, DAY, D("5.00"))
    assert drawn == chart.render_chart(found, DAY, D("5.00"))
    shuffled = list(days)
    random.Random(7).shuffle(shuffled)
    assert shuffled != days
    assert chart.render_chart(_verdict(shuffled, today="4.10"), DAY, D("5.00")) == drawn
    assert chart.render_chart(_verdict(reversed(days), today="4.10"), DAY, D("5.00")) == drawn


def test_ninety_days_of_daily_changes_stay_small():
    """90 tracked days, the shelf price changing every day and a three-day sale every week at a price of its own, with
    today's two prices, the key and the table: under 3,500 bytes."""
    days = []
    for n in range(READ_DAYS, 0, -1):
        listed = f"{10 + n % 7}.{n % 10}0"
        days.append(_sale(n, f"{7 + n % 3}.{n % 9}5", listed) if n % 7 < 3 else _shelf(n, listed))
    drawn = chart.render_chart(_verdict(days, today="7.15", usual="12.40"), DAY, D("12.90"))
    parts = _read(drawn)
    assert len(_pieces(_paths(parts["lines"])["listed"])) == 1
    assert len(_pieces(_paths(parts["lines"])["sale"])) == 13
    assert len(drawn.encode()) < 3_500, len(drawn.encode())


# ---- the words ----

def test_the_chart_words_are_plain():
    """The chart's words say no NEVER phrase and no "we", "our" or "us"; a label is a kind and a price as shown."""
    assert [chart_label(kind, D("8.90")) for kind in ("usually", "lowest", "highest", "today")] == [
        "usually ₪8.90", "lowest ₪8.90", "highest ₪8.90", "today ₪8.90"]
    assert chart_label("usually", D("6.9")) == "usually ₪6.90"
    with pytest.raises(ValueError):
        chart_label("cheapest", D("1.00"))
    found = _verdict([_shelf(2), _sale(1, "4.00")], today="4.00")
    for said in (*CHART_KEY, *STATS_HEADS, chart_summary(found), chart_label("usually", D("1.00"))):
        assert not PRONOUNS.search(flatten(said)), said
        for phrase in NEVER:
            assert flatten(phrase) not in flatten(said), (phrase, said)

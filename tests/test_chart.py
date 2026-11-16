"""The price chart (`shopper.chart`; docs/site-look.md, "The chart", as the owner redrew it on 2026-11-16 after reading
the built pages: one line, the price paid each day; the site-look plan's Task 5, then Task 12's fix round): a ₪ axis,
the dates along the bottom, the line, today's price at its end, then the key and the table; and its words
(`shopper.words`: CHART_KEY, STATS_HEADS, `chart_label`).

Most verdicts are built by hand, since the chart is a function of the verdict and the day alone; the cases that turn
on a day the column could not read (a promotion hole between two tracked days, and the calls that know no price today)
go through `shopper.verdict.verdict`, with pairs and column-days built as tests/test_verdict.py builds them. The chart
is read as XML. The heights are worked by hand from the axis rule and written out. Every figure is synthetic."""
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


def _no_price_today(call: str) -> Verdict:
    """Five days at ₪5.00 to yesterday, then today with no price, through the verdict: a sale whose price was not read
    (price_unread), sale prices not read (unread_today), not listed (not_sold), a hole (too_few)."""
    unread = _point(DAY, "5.00", {**_struct("13.00"), "valid": False})       # listed across the column, not read
    found = {"price_unread": lambda: _judged([*_history(), unread]),
             "unread_today": lambda: _judged([*_history(), _point(DAY, "5.00", _struct())], promo_holes={DAY}),
             "not_sold": lambda: _judged(_history()),
             "too_few": lambda: _judged([*_history(), _point(DAY, "5.00", _struct())], holes={DAY})}[call]()
    assert (found.call, found.today_price) == (call, None)
    return found


# ---- reading the chart ----

def _read(html: str) -> dict[str, ElementTree.Element | None]:
    """The chart's parts by name: the axis, the lines, the overlay, the today column, the key (None without one) and
    the table, each checked to be where the markup's order puts it."""
    history = ElementTree.fromstring(html)
    assert (history.tag, history.get("class")) == ("div", "history")
    drawing, *after = history
    assert (drawing.tag, drawing.get("class")) == ("div", "chart")
    key = after.pop(0) if after and after[0].tag == "p" else None
    assert key is None or key.get("class") == "key"
    assert [(each.tag, each.get("class")) for each in after] == [("table", "stats")]
    ax, plot, now = drawing
    lines, over = plot
    assert [(each.tag, each.get("class")) for each in (ax, plot, lines, over, now)] == [
        ("svg", "ax"), ("div", "plot"), ("svg", "lines"), ("svg", "over"), ("svg", "now")]
    return {"ax": ax, "lines": lines, "over": over, "now": now, "key": key, "table": after[0]}


def _paths(lines: ElementTree.Element) -> dict[str, str]:
    found = {path.get("class"): path.get("d") for path in lines.iter("path")}
    assert len(found) == len(list(lines.iter("path")))              # each class once
    return found


def _pieces(d: str) -> list[list[tuple[int, int, Decimal]]]:
    """A path's subpaths, each from an M, as its horizontal pieces (x from, x to, height)."""
    found: list[list[tuple[int, int, Decimal]]] = []
    x, y = 0, D(0)
    for command, a, b in re.findall(r"([MHV])(-?[\d.]+)(?: (-?[\d.]+))?", d):
        if command == "M":
            x, y = int(a), D(b)
            found.append([])
        elif command == "H":
            found[-1].append((x, int(a), y))
            x = int(a)
        else:
            y = D(a)
    return found


def _covered(d: str | None, x: int) -> list[Decimal]:
    """The heights a path draws across the day at x (none for a path not drawn)."""
    return [y for run in _pieces(d or "") for start, end, y in run if start <= x and x + 1 <= end]


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


def _key(parts) -> tuple[list[str], str] | None:
    """The key's swatches' classes and its words; None with no key."""
    if parts["key"] is None:
        return None
    return [each.get("class") for each in parts["key"]], "".join(parts["key"].itertext())


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


def test_the_axis_holds_the_prices_paid_today_included():
    """The axis runs over the prices drawn: each day's price, today's price and the usual price, so today's dot lies
    on the plot; a sale day's listed price is drawn nowhere, so one above every price paid does not raise the axis. Its
    words at the left, ₪ and whole shekels, top to bottom at each step's height; a gridline at each step above the
    bottom."""
    days = [*(_shelf(n) for n in range(9, 1, -1)), _sale(1, "4.00", listed="9.00")]
    parts = _read(chart.render_chart(_verdict(days, today="2.00", usual="5.00"), DAY))
    # axis(2.00, 5.00) is (1, 5, 1): 50 pixels a shekel, ₪5 at 0, ₪4 at 50, ₪2 at 150; ₪9.00 would make it (0, 10, 2)
    assert [(each.get("x"), each.get("y"), each.text) for each in parts["ax"]] == [
        ("40", "4", "₪5"), ("40", "54", "₪4"), ("40", "104", "₪3"), ("40", "154", "₪2"), ("40", "204", "₪1")]
    assert [entry for entry in _now(parts["now"]) if entry[0] == "circle"] == [("circle", "sale", 150)]
    paths = _paths(parts["lines"])
    assert paths["grid"] == "M0 150H10M0 100H10M0 50H10M0 0H10"
    assert paths["paid"] == "M0 0H8" and paths["sale"] == "M8 0V50H9V150H10"
    # half a shekel for prices less than a shekel apart, written with its agorot
    found = _verdict([_shelf(n, "4.50") for n in range(9, 0, -1)], today="4.20", usual="4.50", call="no_deal")
    parts = _read(chart.render_chart(found, DAY))
    assert [(each.get("y"), each.text) for each in parts["ax"]] == [("4", "₪5"), ("104", "₪4.50"), ("204", "₪4")]
    assert _paths(parts["lines"])["grid"] == "M0 100H10M0 0H10"


# ---- how it is drawn ----

def test_only_the_lines_scale_and_they_hold_no_text():
    """Design test 4: four SVGs, and the only one with a viewBox is the lines', which stretches
    (preserveAspectRatio="none") and holds no text; no width, height or style anywhere, so the stylesheet sizes
    everything and no word shrinks."""
    html = chart.render_chart(_rich(), DAY)
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
    days. The line of a history priced every day runs through today, to the span's end."""
    for tracked, span in ((13, 14), (READ_DAYS, 91)):
        found = _verdict([_shelf(n) for n in range(tracked, 0, -1)], today="5.00", usual=None, call="no_sale")
        parts = _read(chart.render_chart(found, DAY))
        assert parts["lines"].get("viewBox") == f"0 0 {span} 200"
        assert _paths(parts["lines"])["paid"] == f"M0 100H{span}"
    # the first tracked day sets the start, wherever it sits in the window
    found = _verdict([_shelf(3), _shelf(1)], today="5.00", usual=None, call="no_sale")
    parts = _read(chart.render_chart(found, DAY))
    assert parts["lines"].get("viewBox") == "0 0 4 200"
    assert _paths(parts["lines"])["paid"] == "M0 100H1M2 100H4"


# ---- one line: the price paid each day ----

def test_one_line_the_price_paid_each_day():
    """The owner, 2026-11-16: one line. Every day with a price is in exactly one of `paid` (an ink step line) and
    `sale` (the sale's green, heavier), each at its day price; `sale` holds the days a promotion counted, with the
    steps down into a sale and back out of it, so a sale reads as one notch. A sale day's listed price (₪6.00 here) is
    at no height in any path, and no path is named `listed`."""
    days = [_shelf(5), _sale(4, "4.00", "6.00"), _sale(3, "4.50", "6.00"), _shelf(2), _sale(1, "4.00", "6.00")]
    found = _verdict(days, today="4.00", usual="5.00")
    paths = _paths(_read(chart.render_chart(found, DAY))["lines"])
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0, ₪4.50 at 50, ₪4 at 100; ₪6.00 would be above it
    assert paths["paid"] == "M0 0H1M3 0H4"
    assert paths["sale"] == "M1 0V100H2V50H3V0M4 0V100H6"
    assert "listed" not in paths and set(paths) == {"grid", "usual", "paid", "sale"}
    expected = {0: ("paid", 0), 1: ("sale", 100), 2: ("sale", 50), 3: ("paid", 0), 4: ("sale", 100), 5: ("sale", 100)}
    for x, (name, height) in expected.items():
        assert _covered(paths[name], x) == [height] and _covered(paths[{"paid": "sale", "sale": "paid"}[name]], x) == []
    assert "-" not in "".join(paths.values())


def test_a_run_of_one_price_is_one_segment():
    """27 days at one price are one horizontal segment from the start (store first's first simplification), today
    included when its price is known; a change of price is one step, at the day it changes."""
    found = _verdict([_shelf(n) for n in range(27, 0, -1)], today="5.00", usual=None, call="no_sale")
    assert _paths(_read(chart.render_chart(found, DAY))["lines"])["paid"] == "M0 100H28"
    found = _verdict([_shelf(n) for n in range(27, 0, -1)], today=None, usual=None, call="not_sold")
    assert _paths(_read(chart.render_chart(found, DAY))["lines"])["paid"] == "M0 100H27"
    found = _verdict([_shelf(n, "5.00" if n > 10 else "4.50") for n in range(27, 0, -1)], today="4.50", usual=None,
                     call="no_sale")
    # axis(4.50, 5.00) is (4.0, 5.0, 0.5): ₪5 at 0, ₪4.50 at 100
    assert _paths(_read(chart.render_chart(found, DAY))["lines"])["paid"] == "M0 0H17V100H28"


# ---- today ----

@pytest.mark.parametrize("call", ["deal", "no_deal", "mostly_unknown", "no_sale", "some_stores"])
def test_today_is_the_labels_price_one_dot_and_today_under_it(call):
    """The chart's last point is the verdict's today's price (S3), the label's "Price today": one dot at its height,
    beside it the price in the line's colour there (the sale's green when a promotion counts, else ink) and "today"
    under it, 14 pixels below the price's baseline. Nothing on the dates' line under today."""
    usual = "5.00" if call in ("deal", "no_deal") else None
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="4.00", usual=usual, call=call)
    html = chart.render_chart(found, DAY)
    parts = _read(html)
    mark, other = ("sale", "paid") if call in COUNTING else ("paid", "sale")
    # axis(4.00, 5.00) is (3, 5, 1): ₪4 at 100
    assert _now(parts["now"]) == [("circle", mark, 100), ("text", mark, 105, "₪4.00"), ("text", "end", 119, "today")]
    assert (f'<svg class="now" aria-hidden="true"><circle class="{mark}" cy="100" r="4.5"/>'
            f'<text class="{mark}" x="12" y="105">₪4.00</text><text class="end" x="12" y="119">today</text></svg>'
            ) in html
    paths = _paths(parts["lines"])
    assert _covered(paths[mark], 9) == [100] and _covered(paths.get(other), 9) == []
    assert "unread" not in paths


@pytest.mark.parametrize("call", ["price_unread", "unread_today", "not_sold", "too_few"])
def test_with_no_price_today_the_line_ends_the_day_before(call):
    """With no price today (an unread sale price, sale prices not read today, not sold, too few files) the line ends
    at its last day with a price and today's column holds "today" alone, on the dates' line (the owner's rulings of
    2026-11-11 and 2026-11-16: no price at today); an unread sale price keeps its tick under today."""
    parts = _read(chart.render_chart(_no_price_today(call), DAY))
    paths = _paths(parts["lines"])
    assert paths["paid"] == "M0 100H5" and "sale" not in paths
    assert _now(parts["now"]) == [("text", "end", 217, "today")]
    assert paths.get("unread") == ("M5 196.5H6" if call == "price_unread" else None)


def test_a_sale_that_starts_today_is_the_step_down_and_one_day_ending_in_its_dot():
    """Review Focus 5: a deal whose sale starts today is the step down at today and today's one day, in the sale's
    green, ending in its dot at the same height; the key names it."""
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="4.00", usual="5.00")
    html = chart.render_chart(found, DAY)
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0, ₪4 at 100; the span is 10
    assert '<path class="paid" d="M0 0H9"/><path class="sale" d="M9 0V100H10"/>' in html
    parts = _read(html)
    assert ("circle", "sale", 100) in _now(parts["now"])
    assert _key(parts) == (["sale"], "on sale")


# ---- days with no price ----

def test_seven_days_with_no_price_are_joined_by_a_dotted_stretch():
    """Up to BRIDGE (7) days in a row with no price between two days with one: the line goes on dotted at the last
    price (`gap`), and the step to the next price is inside the dotted path; no number counts a carried day."""
    assert chart.BRIDGE == 7
    days = [_shelf(10), _shelf(2, "4.00"), _shelf(1, "4.00")]                  # back 9 to back 3: 7 days
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.00", usual=None, call="no_sale"), DAY))["lines"])
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0, ₪4 at 100; x 1 to 7 carried
    assert paths["gap"] == "M1 0H8V100"
    assert paths["paid"] == "M0 0H1M8 100H11"
    for x in range(1, 8):
        assert _covered(paths["gap"], x) == [0] and _covered(paths["paid"], x) == []


def test_eight_days_with_no_price_are_left_open():
    """More than BRIDGE days in a row with no price: a gap, nothing drawn over them, and no step across it."""
    days = [_shelf(11), _shelf(2, "4.00"), _shelf(1, "4.00")]                  # back 10 to back 3: 8 days
    parts = _read(chart.render_chart(_verdict(days, today="4.00", usual=None, call="no_sale"), DAY))
    paths = _paths(parts["lines"])
    assert paths["paid"] == "M0 0H1M9 100H12"
    assert "gap" not in paths and "gap sale" not in paths and "V" not in paths["paid"]


def test_the_dotted_stretch_carries_the_colour_of_the_day_it_carries():
    """A day with no price after a sale day goes on dotted in the sale's colour (`gap sale`), so a sale with a missing
    morning stays one green notch; the steps in and out of it stay green."""
    days = [_shelf(4), _sale(3, "4.00"), _sale(1, "4.00")]                      # back 2 missing
    paths = _paths(_read(chart.render_chart(_verdict(days, today="5.00", usual=None, call="no_sale"), DAY))["lines"])
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0, ₪4 at 100
    assert paths["gap sale"] == "M2 100H3" and "gap" not in paths
    assert paths["sale"] == "M1 0V100H2M3 100H4V0"
    assert paths["paid"] == "M0 0H1M4 0H5"


def test_a_promotion_hole_between_two_tracked_days_is_joined():
    """Through the verdict: a promotion hole is not a tracked day (S0), so it has no price, and one between two sale
    days is carried dotted in the sale's colour; the deal today steps down from the day before."""
    sale = _struct("4.00", start=back(4), end=back(2))
    points = [_point(back(5)), *(_point(back(n), "5.00", sale) for n in (4, 3, 2)), _point(back(1)),
              _point(DAY, "5.00", _struct("3.00"))]
    found = _judged(points, promo_holes={back(3)})
    assert [each.day for each in found.days] == [back(5), back(4), back(2), back(1)]
    assert (found.call, found.usual, found.today_price) == ("deal", D("5.00"), D("3.00"))
    paths = _paths(_read(chart.render_chart(found, DAY))["lines"])
    # axis(3.00, 5.00) is (2, 5, 1): ₪5 at 0, ₪4 at 67, ₪3 at 133; the hole at x 2
    assert paths["gap sale"] == "M2 67H3"
    assert paths["sale"] == "M1 0V67H2M3 67H4V0M5 0V133H6"
    assert paths["paid"] == "M0 0H1M4 0H5"
    assert paths["usual"] == "M1 0H4M5 0H6"


def test_nothing_is_carried_past_the_last_price_or_before_the_first():
    """The line starts at the first day with a price and ends at the last: days with no price before the first or
    after the last are not drawn (their ticks are)."""
    days = [_unknown(5), _unknown(4), _shelf(3), _shelf(2), _unknown(1)]
    paths = _paths(_read(chart.render_chart(_verdict(days, today=None, usual=None, call="price_unread"), DAY))["lines"])
    assert paths["paid"] == "M2 100H4" and "gap" not in paths
    assert paths["unread"] == "M0 196.5H2M4 196.5H6"


def test_a_sale_day_of_unknown_price_is_a_tick_on_the_date_line():
    """A sale day whose price could not be read (S1) has no price, so the line runs across it only as a day with no
    price (dotted, when the run is short), and a tick stands on the date line under that day, consecutive ones as one;
    price_unread adds today's."""
    days = [_shelf(3), _unknown(2), _shelf(1)]
    html = chart.render_chart(_verdict(days, today="5.00", usual=None, call="no_sale"), DAY)
    assert '<path class="gap" d="M1 100H2"/><path class="paid" d="M0 100H1M2 100H4"/>' in html
    assert '<path class="unread" d="M1 196.5H2"/>' in html
    days = [_shelf(5), _unknown(4), _unknown(3), _shelf(2), _unknown(1)]
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.00", usual="5.00"), DAY))["lines"])
    assert paths["unread"] == "M1 196.5H3M4 196.5H5" and chart.TICK == D("196.5")
    # axis(4.00, 5.00) is (3, 5, 1): the dotted stretch at ₪5 over x 1, 2 and 4, then the step to today's ₪4
    assert paths["gap"] == "M1 0H3M4 0H5V100" and paths["paid"] == "M0 0H1M3 0H4" and paths["sale"] == "M5 100H6"
    # price_unread: today's tick, and no price today
    parts = _read(chart.render_chart(_verdict(days, today=None, usual=None, call="price_unread"), DAY))
    assert _paths(parts["lines"])["unread"] == "M1 196.5H3M4 196.5H6"
    assert _now(parts["now"]) == [("text", "end", 217, "today")]


# ---- the usual price ----

def test_the_usual_dashes_stand_wherever_the_line_is_not():
    """With a Deal or No deal, the usual price's dashes run on every day of the span, today's included, but those on
    which the line, the dotted stretch included, runs within CLEAR (6) pixels of its height."""
    assert chart.CLEAR == 6
    days = [_shelf(5, "5.00"), _shelf(4, "5.02"), _shelf(2, "5.03"), _shelf(1, "5.00")]      # back 3 missing
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.95", usual="5.00", call="no_deal"), DAY))["lines"])
    # axis(4.95, 5.03) is (4.5, 5.5, 0.5), 2 pixels an agora: ₪5.00 at 100, ₪5.02 at 96 (and carried over x 2), ₪5.03
    # at 94, today's ₪4.95 at 110
    assert paths["gap"] == "M2 96H3V94"
    assert paths["usual"] == "M3 100H4M5 100H6"
    # a gap left open has no line, so the dashes run across it
    days = [_shelf(10), _shelf(1)]                                               # back 9 to back 2: 8 days
    paths = _paths(_read(chart.render_chart(_verdict(days, today="4.00", usual="5.00"), DAY))["lines"])
    # axis(4.00, 5.00) is (3, 5, 1): ₪5 at 0
    assert paths["usual"] == "M1 0H9M10 0H11" and "gap" not in paths


def test_the_usual_words_are_written_even_with_no_dash():
    """A No deal whose price is its usual price every day, today's included: the line says it, so no dash is drawn,
    and the words still stand, LIFT (8) pixels above the level."""
    assert chart.LIFT == 8
    found = _verdict([_shelf(n) for n in range(9, 0, -1)], today="5.00", usual="5.00", call="no_deal")
    parts = _read(chart.render_chart(found, DAY))
    assert "usual" not in _paths(parts["lines"])
    said = [each for each in parts["over"] if each.get("class") == "usually"]
    assert [(each.get("x"), each.get("dx"), each.get("y"), each.text) for each in said] == [
        ("100%", "-12", "92", chart_label("usually", D("5.00")))]


def test_the_usual_words_stand_above_their_level_unless_the_line_runs_there():
    """The usual price's words at the right, LIFT pixels above its level, unless the line runs within 21 pixels above
    it in the last 30% of the span's days (a point, a dotted stretch, or a step crossing that band), then 15 below;
    above again when below is as busy, or when the level is under 20 pixels from the date line, so the words never
    stand on it. At the very top of the plot they stand above, in the chart's top margin."""
    def label(prices: list[str], today: str, call: str = "deal", usual: str = "5.00") -> int:
        days = [_shelf(9 - x, price) for x, price in enumerate(prices)]
        found = _verdict(days, today=today, usual=usual, call=call)
        over = _read(chart.render_chart(found, DAY))["over"]
        (said,) = [each for each in over if each.get("class") == "usually"]
        assert [each.get("class") for each in over][0] == "usually"           # first in the overlay
        return int(said.get("y"))

    # axis (4, 6, 1), a pixel an agora: ₪6 at 0, ₪5.10 at 90, ₪5 at 100, ₪4.90 at 110, ₪4.50 at 150; x 7 to 9 are the
    # last 30% of the 10 days (each reaching past 7 days)
    quiet = ["6.00", "6.00", *["5.00"] * 7]
    assert label(quiet, "4.50") == 92
    # ₪5.10 on the last days and today, 10 pixels above: below
    assert label(["6.00", "6.00", *["5.00"] * 5, "5.10", "5.10"], "5.10", call="no_deal") == 115
    # ₪5.10 at x 5, before the last 30%, its steps at x 5 and 6 too: above, though below is free
    assert label(["6.00", "6.00", "5.00", "5.00", "5.00", "5.10", "5.00", "5.00", "5.00"], "5.00", call="no_deal") == 92
    # no day in the band, but the step up at x 7 crosses it: below
    assert label(["6.00", "6.00", *["5.00"] * 5, "6.00", "6.00"], "6.00", call="no_deal") == 115
    # busy below too, today's ₪4.90 10 pixels under it: above
    assert label(["6.00", "6.00", *["5.00"] * 5, "5.10", "5.10"], "4.90", call="no_deal") == 92
    # at the axis's top: axis(4.00, 5.00) is (3, 5, 1), ₪5 at 0, so the words stand in the top margin; today's step
    # crosses the band below, and so does nothing in the second, whose drop comes before the last 30%: above there too
    assert label(["5.00"] * 9, "4.00") == -8
    assert label([*["5.00"] * 6, *["4.00"] * 3], "4.00") == -8
    # the level under 20 pixels from the date line: axis(4.18, 6.00) is (4, 6, 1), the usual ₪4.18 at 182 and ₪4.30 at
    # 170 on the last days and today, 12 pixels above; below is free, but the words would stand on the date line: above
    assert label(["6.00", *["4.18"] * 5, *["4.30"] * 3], "4.30", call="no_deal", usual="4.18") == 174
    # no usual dashes nor words without a Deal or No deal
    parts = _read(chart.render_chart(_verdict([_shelf(2), _shelf(1)], today="5.00", usual=None, call="no_sale"), DAY))
    assert "usual" not in _paths(parts["lines"])
    assert [each for each in parts["over"] if each.get("class") == "usually"] == []


# ---- the dates ----

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
    """Review Focus 5: one tracked day and today: its date at the left, "today" under today's price at the right, no
    mark between; drawn as wide as any other (the span is two days)."""
    found = _verdict([_shelf(1)], today="4.00", usual="5.00")
    parts = _read(chart.render_chart(found, DAY))
    assert parts["lines"].get("viewBox") == "0 0 2 200"
    assert _dates(parts["over"]) == [("19 Nov", None, None)]
    assert _now(parts["now"])[-1] == ("text", "end", 119, "today")


# ---- the key and the table ----

def test_the_key_names_only_the_marks_that_need_words():
    """After the chart, CHART_KEY's words for each mark that needs them, today's included, each after a swatch of its
    class, in CHART_KEY's order and set apart by " · ": "on sale" with a sale stretch, "on sale, price not read" with a
    tick. The plain line has no entry, and a chart with neither mark has no key at all; never "shelf price"."""
    def key(found):
        return _key(_read(chart.render_chart(found, DAY)))

    assert key(_verdict([_shelf(2), _shelf(1)], today="5.00", usual=None, call="no_sale")) is None
    assert '<p class="key">' not in chart.render_chart(_verdict([_shelf(2)], today="5.00", usual=None,
                                                                call="no_sale"), DAY)
    assert key(_verdict([_shelf(2), _sale(1, "4.00")], today="5.00", usual=None, call="no_sale")) == (
        ["sale"], "on sale")
    assert key(_verdict([_shelf(2), _unknown(1)], today="5.00", usual=None, call="no_sale")) == (
        ["unread"], "on sale, price not read")
    assert key(_verdict([_sale(3, "4.00"), _unknown(2), _shelf(1)])) == (
        ["sale", "unread"], "on sale · on sale, price not read")
    # today's marks count: a sale from today, a sale today whose price was not read
    assert key(_verdict([_shelf(2), _shelf(1)])) == (["sale"], "on sale")
    assert key(_verdict([_shelf(2), _shelf(1)], today=None, usual=None, call="price_unread")) == (
        ["unread"], "on sale, price not read")
    assert CHART_KEY == ("on sale", "on sale, price not read")
    assert "shelf price" not in chart.render_chart(_rich(), DAY)


def test_the_table_is_lowest_highest_and_today():
    """STATS_HEADS: Lowest and Highest over the tracked days' day prices and today's price (the design's call 3), each
    over the latest day at that price, "today" when it is today's, and Today with today's price; no Usual cell, since
    the chart writes the usual price at its own height. The design's example, a deal at a new low."""
    days = [Day(date(2026, 11, 10), D("22.90"), D("22.90"), False),
            Day(date(2026, 11, 11), D("26.90"), D("19.90"), True),
            Day(date(2026, 11, 12), D("22.90"), D("22.90"), False),
            Day(date(2026, 11, 13), D("24.90"), D("24.90"), False)]
    html = chart.render_chart(_verdict(days, today="17.90", usual="22.90"), date(2026, 11, 14))
    assert _table(_read(html)["table"]) == [("Lowest", "₪17.90", "today"), ("Highest", "₪24.90", "13 Nov"),
                                            ("Today", "₪17.90", None)]
    assert [head for head, _, _ in _table(_read(html)["table"])] == list(STATS_HEADS)
    assert STATS_HEADS == ("Lowest", "Highest", "Today") and "Usual" not in html
    # no sale: the same three
    found = _verdict([_shelf(2, "6.00"), _shelf(1)], today="5.00", usual=None, call="no_sale")
    assert _table(_read(chart.render_chart(found, DAY))["table"]) == [
        ("Lowest", "₪5.00", "today"), ("Highest", "₪6.00", short_day(back(2))), ("Today", "₪5.00", None)]
    # no price today: no Today, the days before still give Lowest and Highest
    for call in ("unread_today", "not_sold"):
        assert _table(_read(chart.render_chart(_no_price_today(call), DAY))["table"]) == [
            ("Lowest", "₪5.00", short_day(back(1))), ("Highest", "₪5.00", short_day(back(1)))]


def test_the_text_alternative_is_the_summary(monkeypatch):
    """The lines are an image whose aria-label is `chart_summary`, escaped for an attribute; the other three SVGs are
    hidden from screen readers."""
    found = _verdict([_shelf(2), _sale(1, "4.00")], today="4.00")
    parts = _read(chart.render_chart(found, DAY))
    assert parts["lines"].get("role") == "img"
    assert parts["lines"].get("aria-label") == chart_summary(found) == (
        "Price chart: usually ₪5.00, lowest ₪4.00, highest ₪5.00, today ₪4.00.")
    assert [parts[name].get("aria-hidden") for name in ("ax", "over", "now")] == ["true"] * 3
    monkeypatch.setattr(chart, "chart_summary", lambda found: 'Price "chart" & <more>')
    html = chart.render_chart(found, DAY)
    assert 'aria-label="Price &quot;chart&quot; &amp; &lt;more&gt;"' in html
    assert _read(html)["lines"].get("aria-label") == 'Price "chart" & <more>'


# ---- no chart, purity, size ----

def test_no_chart_without_a_tracked_day_that_has_a_price():
    """No line to draw, no chart: no tracked day at all (new, no_history), or none with a price (every one a sale day
    of unknown price), whatever today's price."""
    assert chart.render_chart(_verdict([]), DAY) == ""
    new = _judged([_point(DAY, "5.00", _struct("4.00"))])        # first seen today
    assert new.call == "new" and new.days == ()
    assert chart.render_chart(new, DAY) == ""
    unknown = [_unknown(2), _unknown(1)]
    assert chart.render_chart(_verdict(unknown, today=None, usual=None, call="price_unread"), DAY) == ""
    assert chart.render_chart(_verdict(unknown, today="4.00", usual=None, call="mostly_unknown"), DAY) == ""


def test_the_chart_is_the_same_bytes_twice():
    """A pure function: the same bytes twice, and whatever order the days come in."""
    days = [_shelf(9), _sale(8, "4.00"), _unknown(6), _shelf(5, "5.50"), _sale(3, "4.20"), _shelf(1)]
    found = _verdict(days, today="4.10")
    drawn = chart.render_chart(found, DAY)
    assert drawn == chart.render_chart(found, DAY)
    shuffled = list(days)
    random.Random(7).shuffle(shuffled)
    assert shuffled != days
    assert chart.render_chart(_verdict(shuffled, today="4.10"), DAY) == drawn
    assert chart.render_chart(_verdict(reversed(days), today="4.10"), DAY) == drawn


def test_ninety_days_of_daily_changes_stay_small():
    """90 tracked days, the price changing every day and a three-day sale every week at a price of its own, with
    today's price, the key and the table: under 3,500 bytes; every day with a price drawn once."""
    days = []
    for n in range(READ_DAYS, 0, -1):
        listed = f"{10 + n % 7}.{n % 10}0"
        days.append(_sale(n, f"{7 + n % 3}.{n % 9}5", listed) if n % 7 < 3 else _shelf(n, listed))
    drawn = chart.render_chart(_verdict(days, today="7.15", usual="12.40"), DAY)
    paths = _paths(_read(drawn)["lines"])
    assert [len(_covered(paths["paid"], x)) + len(_covered(paths["sale"], x)) for x in range(91)] == [1] * 91
    assert len(_pieces(paths["sale"])) == 13                     # 13 sale runs, the last running on into today's
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

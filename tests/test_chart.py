"""The price chart (`shopper.chart`; docs/store-first.md, "The chart" and "Page size"; the plan's Task 2 and its "Where
the design leaves room", "The chart") and its words (`shopper.words`: CHART_KEY, `chart_label`, `chart_summary`).

Most verdicts are built by hand, since the chart is a function of the verdict alone; the cases that turn on a day the
column could not read (a promotion hole between two tracked days, and the three calls that know no price today) go
through `shopper.verdict.verdict`, with pairs and column-days built as tests/test_verdict.py builds them. The SVG is
read as XML. Every figure is synthetic."""
import random
import re
import xml.etree.ElementTree as ElementTree
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from basket.check import PRONOUNS, flatten
from shopper.chart import BASELINE, BOTTOM, DAY_WIDTH, FOOT, LINE, TOP, render_chart
from shopper.deals import to_agora
from shopper.history import READ_DAYS, ColumnDay, Pair, Point
from shopper.verdict import Day, Verdict, verdict
from shopper.words import CHART_KEY, NEVER, chart_label, chart_summary

DAY = date(2026, 11, 20)
COLUMN = "shufersal-deal"
CODE = "2000000000046"   # a synthetic GS1 code
D = Decimal
MIDDLE = (TOP + BOTTOM) // 2


def back(n: int) -> date:
    return DAY - timedelta(days=n)


def _x(day: date, first: date) -> int:
    return (day - first).days * DAY_WIDTH


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
    """A verdict over `days` as given (in any order); `today` and `usual` None when unknown."""
    today_price = None if today is None else D(today)
    usual_price = None if usual is None else D(usual)
    saving = None if today_price is None or usual_price is None else usual_price - today_price
    return Verdict(column=column, call=call, days=tuple(days), today_price=today_price, struct=None,
                   usual=usual_price, saving=saving, last_low=None, last_sale=None,
                   on_sale_today=today is not None)


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


# ---- reading the chart ----

def _read(html: str) -> tuple[ElementTree.Element, ElementTree.Element]:
    """The SVG and the key after it."""
    svg, key = ElementTree.fromstring(f"<div>{html}</div>")
    return svg, key


def _paths(svg: ElementTree.Element) -> dict[str, str]:
    return {path.get("class"): path.get("d") for path in svg.iter("path")}


def _pieces(d: str) -> list[list[tuple[int, int, int]]]:
    """A path's subpaths, each from an M, as its horizontal pieces (x from, x to, height)."""
    found: list[list[tuple[int, int, int]]] = []
    x = y = 0
    for command, a, b in re.findall(r"([MHV])(\d+)(?: (\d+))?", d):
        if command == "M":
            x, y = int(a), int(b)
            found.append([])
        elif command == "H":
            found[-1].append((x, int(a), y))
            x = int(a)
        else:
            y = int(a)
    return found


def _covered(d: str, x: int) -> list[int]:
    """The heights a path draws across the day starting at x."""
    return [y for run in _pieces(d) for start, end, y in run if start <= x and x + DAY_WIDTH <= end]


def _labels(svg: ElementTree.Element) -> dict[str, tuple[int, int]]:
    """Each label's words, with its x and its y."""
    return {found.text: (int(found.get("x")), int(found.get("y"))) for found in svg.iter("text")}


def _width(svg: ElementTree.Element) -> int:
    return int(svg.get("viewBox").split()[2])


def _names_the_labels(svg: ElementTree.Element, found: Verdict) -> None:
    """The title is chart_summary and names exactly the labels drawn: the label rule's two copies, the chart's and
    the words', agree for this verdict."""
    summary = chart_summary(found)
    assert svg[0].tag == "title" and svg[0].text == summary
    named = [] if summary == "Price chart." else summary.removeprefix("Price chart: ").removesuffix(".").split(", ")
    assert sorted(named) == sorted(label.text for label in svg.iter("text")), summary


# ---- the tests ----

def test_the_span_is_the_tracked_days_then_today():
    """Across: each calendar day from the first tracked day to today is DAY_WIDTH units, the first tracked day at x 0
    and today at (today - first) * DAY_WIDTH; the span is what was tracked, never a fixed 90 days."""
    found = _verdict([_shelf(n) for n in range(20, 0, -1)])
    svg, _ = _read(render_chart(found, DAY))
    assert _paths(svg)["listed"].startswith("M0 ")
    assert int(svg.find("circle").get("cx")) == (DAY - back(20)).days * DAY_WIDTH == 80
    short = _width(_read(render_chart(_verdict([_shelf(n) for n in range(5, 0, -1)]), DAY))[0])
    long = _width(_read(render_chart(_verdict([_shelf(n) for n in range(27, 0, -1)]), DAY))[0])
    assert short < long
    assert long - short == (27 - 5) * DAY_WIDTH        # the same labels: the difference is the days
    # the first tracked day sets the start, wherever it sits in the window
    late = _read(render_chart(_verdict([_shelf(3), _shelf(1)]), DAY))[0]
    assert _paths(late)["listed"] == f"M0 {TOP}H4M8 {TOP}H12"
    assert int(late.find("circle").get("cx")) == 12


def test_untracked_days_are_gaps():
    """A promotion hole between two tracked days is not tracked (S0): the listed line stops at the end of the day
    before it and starts again (an M) at the day after it, with no segment across; a day not tracked before today
    leaves the line short of today."""
    points = [_point(back(n)) for n in range(5, 0, -1)] + [_point(DAY, "5.00", _struct("4.00"))]
    found = _judged(points, promo_holes={back(3)})
    assert [each.day for each in found.days] == [back(5), back(4), back(2), back(1)]
    svg, _ = _read(render_chart(found, DAY))
    listed = _paths(svg)["listed"]
    assert listed == f"M0 {TOP}H8M12 {TOP}H20"
    assert _covered(listed, _x(back(3), back(5))) == []
    assert len(_pieces(listed)) == 2
    # a hole yesterday: the line ends with the day before it, short of today's dot
    found = _judged(points, holes={back(1)})
    svg, _ = _read(render_chart(found, DAY))
    assert _paths(svg)["listed"] == f"M0 {TOP}H16"
    assert int(svg.find("circle").get("cx")) == 20


def test_the_listed_price_grey_and_sale_days_green():
    """The listed price on every tracked day, sale days included; the day price green on the sale days with a price, at
    its own height; a day not on sale has no sale stretch."""
    days = [_shelf(4), _sale(3, "4.00"), _sale(2, "4.50"), _shelf(1)]
    svg, key = _read(render_chart(_verdict(days, today="4.00"), DAY))
    paths = _paths(svg)
    assert paths["listed"] == f"M0 {TOP}H16"
    assert paths["sale"] == f"M4 {BOTTOM}H8V{MIDDLE}H12"
    assert _covered(paths["sale"], 4) == [BOTTOM] and _covered(paths["sale"], 8) == [MIDDLE]
    for off_sale in (0, 12):
        assert _covered(paths["sale"], off_sale) == []
    assert "unread" not in paths
    # two sale runs apart are two stretches
    days = [_sale(5, "4.00"), _shelf(4), _sale(3, "4.00"), _sale(2, "4.00"), _shelf(1)]
    assert _paths(_read(render_chart(_verdict(days), DAY))[0])["sale"] == f"M0 {BOTTOM}H4M8 {BOTTOM}H16"
    # no sale day, no sale path, and the key names only the shelf price
    svg, key = _read(render_chart(_verdict([_shelf(2), _shelf(1)], today="5.00", call="no_sale", usual=None), DAY))
    assert set(_paths(svg)) == {"listed"}
    assert "".join(key.itertext()) == CHART_KEY[0]
    assert [found.get("class") for found in key] == ["listed"]


def test_a_sale_day_of_unknown_price_is_marked_without_a_price():
    """A sale day of unknown price (S1) gets a mark at the foot, below every price, and no price: no sale stretch and
    no label of its own; consecutive ones are one mark."""
    days = [_shelf(4), _unknown(3), _unknown(2), _shelf(1)]
    svg, key = _read(render_chart(_verdict(days, today="4.00"), DAY))
    paths = _paths(svg)
    assert paths["unread"] == f"M4 {FOOT}H12"
    assert FOOT > BOTTOM
    assert "sale" not in paths
    assert paths["listed"] == f"M0 {TOP}H16"      # the shelf price still drawn on those days
    assert set(_labels(svg)) == {"usually ₪5.00", "lowest ₪5.00", "highest ₪5.00", "today ₪4.00"}
    assert "".join(key.itertext()) == " · ".join((CHART_KEY[0], CHART_KEY[2]))
    # with a sale stretch too, the key names all three marks, in CHART_KEY's order, each set apart
    days = [_sale(3, "4.00"), _unknown(2), _shelf(1)]
    _, key = _read(render_chart(_verdict(days), DAY))
    assert "".join(key.itertext()) == "shelf price · on sale · on sale, price not read"
    assert [found.get("class") for found in key] == ["listed", "sale", "unread"]


def test_todays_price_is_a_dot_with_a_dashed_line_across():
    """Today's price as a dot at today's x and its height, with a line at that height from x 0 to the plot's right
    edge (the end of today's day), so every earlier day at or below it stands out; the labels start after it."""
    found = _verdict([_shelf(n) for n in range(10, 0, -1)], today="4.00", usual="5.00")
    svg, _ = _read(render_chart(found, DAY))
    line, circle = svg.find("line"), svg.find("circle")
    assert line.get("class") == circle.get("class") == "today"
    edge = _x(DAY, back(10)) + DAY_WIDTH
    assert (line.get("x1"), line.get("x2")) == ("0", str(edge))
    assert line.get("y1") == line.get("y2") == str(BOTTOM)
    assert (circle.get("cx"), circle.get("cy")) == (str(_x(DAY, back(10))), str(BOTTOM))
    assert all(x > edge for x, _ in _labels(svg).values())
    # today above the usual price: the dot and the line at its own height, never the usual price's
    found = _verdict([_shelf(2, "4.00"), _shelf(1, "4.00")], today="5.00", usual="4.00", call="no_deal")
    svg, _ = _read(render_chart(found, DAY))
    assert svg.find("circle").get("cy") == svg.find("line").get("y1") == str(TOP)


def test_no_today_mark_without_todays_price():
    """too_few, not_sold and unread_today know no price today, nor does price_unread, a sale whose price could not be
    read (the owner, 2026-11-11): no dot, no line and no today label, though the tracked days are drawn and
    labelled."""
    history = [_point(back(n), "5.00") for n in range(5, 0, -1)]
    today = _point(DAY, "5.00", _struct("4.00"))
    unread = _point(DAY, "5.00", {**_struct("13.00"), "valid": False})       # listed across the column, price not read
    cases = {"too_few": _judged([*history, today], holes={DAY}),
             "not_sold": _judged(history),
             "unread_today": _judged([*history, today], promo_holes={DAY}),
             "price_unread": _judged([*history, unread])}
    for call, found in cases.items():
        assert found.call == call and found.today_price is None
        svg, _ = _read(render_chart(found, DAY))
        assert svg.find("line") is None and svg.find("circle") is None, call
        assert set(_labels(svg)) == {"lowest ₪5.00", "highest ₪5.00"}, call
        assert _paths(svg)["listed"] == f"M0 {MIDDLE}H20", call
        _names_the_labels(svg, found)


def test_the_labels_name_the_usual_lowest_and_highest_prices():
    """The labels, at the right: the usual price when there is one, the lowest and the highest DAY prices of the
    tracked days (none with no day price), and today's price, each in chart_label's words."""
    assert [chart_label(kind, D("8.90")) for kind in ("usually", "lowest", "highest", "today")] == [
        "usually ₪8.90", "lowest ₪8.90", "highest ₪8.90", "today ₪8.90"]
    assert chart_label("today", D("6.9")) == "today ₪6.90"
    with pytest.raises(ValueError):
        chart_label("cheapest", D("1.00"))
    days = [_shelf(5), _sale(4, "4.00"), _sale(3, "4.50"), _shelf(2), _shelf(1)]
    found = _verdict(days, today="4.20")
    svg, _ = _read(render_chart(found, DAY))
    # each at its price's height: 5.00 at TOP, 4.20 at 82, 4.00 at BOTTOM; the tie at 5.00 set LINE apart
    assert {words: y - BASELINE for words, (_, y) in _labels(svg).items()} == {
        "highest ₪5.00": TOP, "usually ₪5.00": TOP + LINE, "today ₪4.20": 82, "lowest ₪4.00": BOTTOM}
    _names_the_labels(svg, found)
    # always on: listed ₪12.90, on sale at ₪9.90 every day; the highest is the day price, not the listed one drawn
    days = [_sale(n, "9.90", listed="12.90") for n in range(9, 0, -1)]
    found = _verdict(days, today="9.90", usual="9.90", call="no_deal")
    svg, _ = _read(render_chart(found, DAY))
    assert set(_labels(svg)) == {"usually ₪9.90", "lowest ₪9.90", "highest ₪9.90", "today ₪9.90"}
    _names_the_labels(svg, found)
    assert _paths(svg)["listed"] == f"M0 {TOP}H36"     # the shelf price still drawn, at the top
    # no day price: no lowest or highest label
    days = [_unknown(3), _unknown(2), _unknown(1)]
    found = _verdict(days, today="4.00", usual=None, call="mostly_unknown")
    svg, _ = _read(render_chart(found, DAY))
    assert set(_labels(svg)) == {"today ₪4.00"}
    _names_the_labels(svg, found)
    # nothing known at all: the summary and the chart both name no label
    found = _verdict(days, today=None, usual=None, call="too_few")
    svg, _ = _read(render_chart(found, DAY))
    assert _labels(svg) == {} and chart_summary(found) == "Price chart."
    _names_the_labels(svg, found)


def test_the_labels_are_never_drawn_over_each_other():
    """Labels at one height or close are moved apart, at least LINE units between centres, ties ordered highest,
    usually, today, lowest, and kept inside the chart."""
    days = [_shelf(n, "8.90") for n in range(6, 1, -1)] + [_sale(1, "6.90", listed="8.90")]
    svg, _ = _read(render_chart(_verdict(days, today="6.90", usual="8.90"), DAY))
    labels = _labels(svg)
    order = sorted(labels, key=lambda name: labels[name][1])
    assert order == ["highest ₪8.90", "usually ₪8.90", "today ₪6.90", "lowest ₪6.90"]
    heights = [labels[name][1] for name in order]
    assert all(below - above >= LINE for above, below in zip(heights, heights[1:]))
    assert 0 < heights[0] and heights[-1] <= int(svg.get("viewBox").split()[3])


def test_a_text_alternative_inside_the_svg():
    """The SVG is an image named by its <title>, its first child, whose id is the column's (one chart per column on a
    page) and whose text is chart_summary: the labels' words."""
    days = [_shelf(n, "8.90") for n in range(6, 1, -1)] + [_sale(1, "6.90", listed="8.90")]
    found = _verdict(days, today="6.90", usual="8.90")
    assert chart_summary(found) == "Price chart: usually ₪8.90, lowest ₪6.90, highest ₪8.90, today ₪6.90."
    svg, _ = _read(render_chart(found, DAY))
    assert svg.get("class") == "chart" and svg.get("role") == "img"
    title = svg[0]
    assert title.tag == "title" and title.text == chart_summary(found)
    assert title.get("id") == svg.get("aria-labelledby") == f"chart-{COLUMN}"
    _names_the_labels(svg, found)
    other = _read(render_chart(_verdict(days, column="ramilevy"), DAY))[0][0]
    assert other.get("id") == "chart-ramilevy" != title.get("id")
    # fewer labels, fewer words; none, none
    assert chart_summary(_verdict([_unknown(1)], today="4.00", usual=None)) == "Price chart: today ₪4.00."
    assert chart_summary(_verdict([_unknown(1)], today=None, usual=None, call="too_few")) == "Price chart."


def test_a_run_of_one_price_is_one_segment():
    """27 days at one price are one horizontal segment from the start (the design's first simplification)."""
    found = _verdict([_shelf(n) for n in range(27, 0, -1)])
    listed = _paths(_read(render_chart(found, DAY))[0])["listed"]
    assert listed == f"M0 {TOP}H108"
    # a change of price is one step, at the day it changes
    found = _verdict([_shelf(n, "5.00" if n > 10 else "4.50") for n in range(27, 0, -1)])
    assert _paths(_read(render_chart(found, DAY))[0])["listed"] == f"M0 {TOP}H68V{MIDDLE}H108"


def test_heights_span_the_lowest_and_highest_prices_shown():
    """Up: between the lowest and the highest of the listed prices drawn, the day prices and today's price, so the grey
    line and today's dot both fit; one price throughout sits midway."""
    # today below every day: the dot at the foot of the prices
    svg, _ = _read(render_chart(_verdict([_shelf(2), _sale(1, "4.50")], today="3.00"), DAY))
    assert svg.find("circle").get("cy") == str(BOTTOM)
    assert _paths(svg)["listed"] == f"M0 {TOP}H8"
    # today above every day: at the top
    svg, _ = _read(render_chart(_verdict([_shelf(2, "4.00"), _shelf(1, "3.00")], today="6.00", usual="4.00",
                                         call="no_deal"), DAY))
    assert svg.find("circle").get("cy") == str(TOP)
    assert _paths(svg)["listed"] == f"M0 {MIDDLE + 15}H4V{BOTTOM}H8"     # 4.00 a third of the way up from 3.00
    # a listed price above every day price: the grey line at the top, the sale at the foot
    svg, _ = _read(render_chart(_verdict([_sale(2, "9.90", "12.90"), _sale(1, "9.90", "12.90")], today="9.90",
                                         usual="9.90", call="no_deal"), DAY))
    assert _paths(svg)["listed"] == f"M0 {TOP}H8" and _paths(svg)["sale"] == f"M0 {BOTTOM}H8"
    # one price throughout: midway
    svg, _ = _read(render_chart(_verdict([_shelf(2), _shelf(1)], today="5.00", call="no_deal"), DAY))
    assert _paths(svg)["listed"] == f"M0 {MIDDLE}H8" and svg.find("circle").get("cy") == str(MIDDLE)


def test_no_chart_without_a_tracked_day():
    assert render_chart(_verdict([]), DAY) == ""
    new = _judged([_point(DAY, "5.00", _struct("4.00"))])        # first seen today
    assert new.call == "new" and new.days == ()
    assert render_chart(new, DAY) == ""


def test_the_chart_is_the_same_bytes_twice():
    """A pure function: the same bytes twice, and whatever order the days come in."""
    days = [_shelf(9), _sale(8, "4.00"), _unknown(6), _shelf(5, "5.50"), _sale(3, "4.20"), _shelf(1)]
    found = _verdict(days, today="4.10")
    drawn = render_chart(found, DAY)
    assert drawn == render_chart(found, DAY)
    shuffled = list(days)
    random.Random(7).shuffle(shuffled)
    assert shuffled != days
    assert render_chart(_verdict(shuffled, today="4.10"), DAY) == drawn
    assert render_chart(_verdict(reversed(days), today="4.10"), DAY) == drawn


def test_ninety_days_of_daily_changes_stay_small():
    """90 tracked days, the listed price changing every day, a three-day sale every week at a price of its own and a
    sale day of unknown price every fortnight: under 3,000 bytes, key included."""
    days = []
    for n in range(READ_DAYS, 0, -1):
        listed = f"{10 + n % 7}.{n % 10}0"
        if n % 14 == 0:
            days.append(_unknown(n, listed))
        elif n % 7 < 3:
            days.append(_sale(n, f"{7 + n % 3}.{n % 9}5", listed))
        else:
            days.append(_shelf(n, listed))
    drawn = render_chart(_verdict(days, today="7.15", usual="12.40"), DAY)
    svg, _ = _read(drawn)
    assert len(_pieces(_paths(svg)["listed"])) == 1
    assert len(drawn.encode()) < 3_000, len(drawn.encode())


def test_the_chart_words_are_plain():
    """The chart's words say no NEVER phrase and no "we", "our" or "us"."""
    found = _verdict([_shelf(2), _sale(1, "4.00")], today="4.00")
    for said in (*CHART_KEY, chart_summary(found), *(chart_label(kind, D("1.00"))
                                                     for kind in ("usually", "lowest", "highest", "today"))):
        assert not PRONOUNS.search(flatten(said)), said
        for phrase in NEVER:
            assert flatten(phrase) not in flatten(said), (phrase, said)
    assert CHART_KEY == ("shelf price", "on sale", "on sale, price not read")

"""The verdict: for one product at one store type (a column), whether today's promotion is a deal against what the
product usually costs there, sales included, and the measured facts beside it; and each store type's front list
(docs/store-first.md, "The rules", S0 to S8 and "The front page's list"; the plan's Task 1 and its "Where the design
leaves room"). Pure functions over the history `shopper.history.load` reads: no table of its own.

Figures as shown (call 13). Every comparison works on two-place figures, half up: a listed price as
`basket.record.money` writes it, a deal's price as `shopper.deals.to_agora` writes it. A day price, the usual price,
today's price and the saving are `Decimal`s with two places, so "3 for ₪10.00", shown ₪3.33, is ₪1.00 off a usual
₪4.33 although its exact saving is ₪0.9966.

S3's filter (`counts_today`). A promotion counts on a day when its struct (one of the items table's `promotions`) is
`wide` (carried by at least half the column's counted stores), `valid` (its price read, P4), has a kind, and runs that
day (start <= day <= end). A struct with no kind, a `RewardType` 0 link, never counts and is never a sale, as the
items table never puts such an item on promotion. Club-only and buy-2 promotions count, their conditions kept.

S0 Days tracked, read per product. The tracked days of the day's verdict are the days of the READ_DAYS (90) before
it, today excluded, that `shopper.measures.promotion_points` reads: the column has a record (prices from enough
files), its promotions were read (no promotion hole) and the product is listed with a listed price. A day the product
is not listed is not one of its tracked days, so a product's days tracked are its own, as the golden's worked values
read them.

S1 Day price. On a tracked day, the lower of the listed price and the lowest price among the promotions that count that
day. A day on promotion (`Point.on_promotion`: a wide struct with a kind running that day) with no promotion that
counts is a sale day of unknown price: no day price, but on sale.

S2 Usual price. The day prices of the tracked days, sorted; the middle one, and of an even count the higher of the two
middle ones (element len // 2), so a product on sale on exactly half its days keeps its shelf price as usual. A sale day
of unknown price has no day price, so it never pushes the usual price up.

S3 Today's price. The lowest exact price among today's promotions that count; that promotion is the verdict's `struct`
(a tie to the first, in the items table's order), and its price as shown is today's price. With no promotion counting
today, today's price is the listed price (S6's today).

S4 The call, the first that applies (the plan's order):
  1. too_few: today the column is a hole (prices from too few files);
  2. not_sold: no point today, or no listed price;
  3. unread_today: today the column's promotions were not read;
  4. with no promotion counting today: price_unread when a wide promotion with a kind runs today (its price not
     read), else some_stores when one with a kind runs at fewer than half the stores, else no_sale;
  5. new: no point on any day before today;
  6. mostly_unknown: the sale days of unknown price are more than half the tracked days;
  7. no_history: no tracked day has a day price;
  8. deal when the saving, the usual price minus today's price, is DEAL_MIN (₪1.00) or more; else no_deal.
  Only deal and no_deal have a usual price and a saving.

S5 Shade. A deal's saving of ₪1.00 to ₪2.99 is deal-1, ₪3.00 to ₪4.99 deal-2, ₪5.00 or more deal-3 (SHADES); a call
other than deal has none.

S6 Last this low. The latest tracked day with a day price at or below today's price, an equal price included; none
when no such day is in the window.

S7 How often on sale. Every tracked day counts, sale days of unknown price included: `sum(day.on_sale for day in
days)`. The runs on sale are made over the tracked days in order, so a day not tracked neither breaks nor extends a
run. When today is on sale (`Point.on_promotion`) and the latest run reaches the last tracked day, that run is this
sale; the last sale before it is the latest earlier run. The verdict gives that run's last day (`last_sale`), whose
`price` is None when it could not be read.

S8 Days tracked. Every verdict carries its tracked days (`days`) and those with a day price (`priced`), so every reason
can name the number of days it rests on.

The calls before today's promotions (too_few, not_sold, unread_today) know no price today: no struct, no today's price,
no last this low, no last sale, and not on sale today. Their tracked days are given all the same.

The front list (per store type). A product is listed (`on_list`) when its call is deal and it passes the bar
(`passes_bar`: at least MIN_FRONT_DAYS, 20, days with records in the RECENT_DAYS, 30, before the day, P6's window, a
promotion hole being a record); it is checked (`checked`, the headline's M) when a promotion counts today and it
passes the bar. `front_list` sorts the listed rows by saving, largest first, then by barcode as a number
(`shopper.items.by_number`), and returns all of them; the page shows the first FRONT_LIMIT (100).

This module imports nothing from `shopper.words`, `shopper.product`, `shopper.pages` or `shopper.chart`, which import
it.
"""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from basket.record import money
from shopper.deals import deal_from_row, to_agora
from shopper.history import READ_DAYS, ColumnDay, Pair, Point, window
from shopper.items import by_number
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS, promotion_points

DEAL_MIN = Decimal("1.00")                                                       # S4
SHADES = ((Decimal("5.00"), "deal-3"), (Decimal("3.00"), "deal-2"), (Decimal("1.00"), "deal-1"))   # S5, deepest first
FRONT_LIMIT = 100
CALLS = ("deal", "no_deal", "too_few", "not_sold", "unread_today", "no_sale", "some_stores", "price_unread",
         "new", "mostly_unknown", "no_history")


@dataclass(frozen=True)
class Day:
    """One tracked day (S0) of the window: its listed price as shown, its day price (S1, None on a sale day of unknown
    price) and whether it was on sale (S7: `Point.on_promotion`)."""
    day: date
    listed: Decimal
    price: Decimal | None
    on_sale: bool


@dataclass(frozen=True)
class Verdict:
    """A product's verdict at a column on a day (the module's docstring)."""
    column: str
    call: str                    # one of CALLS
    days: tuple[Day, ...]        # the tracked days of the READ_DAYS before the day, in day order
    today_price: Decimal | None  # S6's today: S3's price when a promotion counts, else the listed price; None when unknown
    struct: Mapping | None       # S3: the counting promotion with the lowest exact price; a tie to the first
    usual: Decimal | None        # S2, with call deal or no_deal
    saving: Decimal | None       # usual - today_price, with call deal or no_deal
    last_low: Day | None         # S6
    last_sale: Day | None        # S7: the last day of the last sale before this one
    on_sale_today: bool

    @property
    def priced(self) -> tuple[Day, ...]:
        """The tracked days with a day price."""
        return tuple(day for day in self.days if day.price is not None)

    @property
    def shade(self) -> str | None:
        """S5: a deal's band; None for any other call."""
        if self.call != "deal":
            return None
        return next(name for floor, name in SHADES if self.saving >= floor)

    @property
    def counting(self) -> bool:
        """Whether a promotion counts today."""
        return self.struct is not None


@dataclass(frozen=True)
class DealRow:
    """A row of a store type's front list: the column, the barcode, the product's title and its verdict there."""
    column: str
    code: str
    title: str
    verdict: Verdict


def _running(struct: Mapping, day: date) -> bool:
    """A promotion with a kind running on `day`; a `RewardType` 0 struct, with no kind, never is."""
    return struct["kind"] is not None and struct["start"] <= day <= struct["end"]


def counts_today(struct: Mapping, day: date) -> bool:
    """S3's filter: the promotion is wide, valid, has a kind and runs on `day`."""
    return bool(struct["wide"] and struct["valid"] and _running(struct, day))


def day_price(point: Point, day: date) -> Decimal | None:
    """S1: the lower of the listed price and the lowest promotion counting on `day`, as shown; None on a sale day of
    unknown price (on promotion, no promotion counting)."""
    listed = Decimal(money(point.listed))
    deals = [to_agora(deal_from_row(found).price) for found in point.promotions if counts_today(found, day)]
    if deals:
        return min(listed, *deals)
    return None if point.on_promotion else listed


def tracked(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[Day, ...]:
    """S0 and S1: the tracked days of the READ_DAYS before `day`, in day order, each with its day price."""
    return tuple(Day(point.day, Decimal(money(point.listed)), day_price(point, point.day), bool(point.on_promotion))
                 for point in promotion_points(pair, column_days, day, READ_DAYS))


def usual_price(prices: Sequence[Decimal]) -> Decimal:
    """S2: the middle of the sorted prices, the higher middle of an even count."""
    ordered = sorted(prices)
    return ordered[len(ordered) // 2]


def _last_sale(days: Sequence[Day], on_sale_today: bool) -> Day | None:
    """S7: the last day of the last run on sale before this one (the module's docstring)."""
    ends = [found for found, after in zip(days, (*days[1:], None))
            if found.on_sale and (after is None or not after.on_sale)]          # each run's last day
    if on_sale_today and ends and ends[-1] is days[-1]:
        ends = ends[:-1]          # this sale, running into today
    return ends[-1] if ends else None


def _unknown_today(call: str, column: str, days: tuple[Day, ...]) -> Verdict:
    """A call before today's promotions: no price, promotion, last this low or last sale today."""
    return Verdict(column=column, call=call, days=days, today_price=None, struct=None, usual=None, saving=None,
                   last_low=None, last_sale=None, on_sale_today=False)


def _judged(call: str, column: str, days: tuple[Day, ...], today_price: Decimal, struct: Mapping | None,
            on_sale_today: bool, usual: Decimal | None = None, saving: Decimal | None = None) -> Verdict:
    """A call with today's price known: S6 and S7 read against it."""
    low = [found for found in days if found.price is not None and found.price <= today_price]
    return Verdict(column=column, call=call, days=days, today_price=today_price, struct=struct, usual=usual,
                   saving=saving, last_low=low[-1] if low else None, last_sale=_last_sale(days, on_sale_today),
                   on_sale_today=on_sale_today)


def verdict(pair: Pair | None, column: str, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> Verdict:
    """The pair's verdict at `column` on `day` (the module's docstring); `pair` None when the column never listed the
    product in the days read."""
    today = column_days[(column, day)]
    point = None if pair is None else pair.points.get(day)
    days = () if pair is None else tracked(pair, column_days, day)
    if not today.record:
        return _unknown_today("too_few", column, days)
    if point is None or point.listed is None:
        return _unknown_today("not_sold", column, days)
    if today.promo_hole:
        return _unknown_today("unread_today", column, days)
    on_sale_today = bool(point.on_promotion)
    counting = [struct for struct in point.promotions if counts_today(struct, day)]
    if not counting:
        running = [struct for struct in point.promotions if _running(struct, day)]
        call = ("price_unread" if any(struct["wide"] for struct in running)
                else "some_stores" if running else "no_sale")
        return _judged(call, column, days, Decimal(money(point.listed)), None, on_sale_today)
    best = min(counting, key=lambda struct: deal_from_row(struct).price)     # the lowest exact price, a tie to the first
    price = deal_from_row(best).price
    today_price = to_agora(price)
    priced = [found.price for found in days if found.price is not None]
    unknown = len(days) - len(priced)
    if not any(seen < day for seen in pair.points):
        return _judged("new", column, days, today_price, best, on_sale_today)
    if 2 * unknown > len(days):
        return _judged("mostly_unknown", column, days, today_price, best, on_sale_today)
    if not priced:
        return _judged("no_history", column, days, today_price, best, on_sale_today)
    usual = usual_price(priced)
    saving = usual - today_price
    call = "deal" if saving >= DEAL_MIN else "no_deal"
    return _judged(call, column, days, today_price, best, on_sale_today, usual, saving)


def passes_bar(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> bool:
    """The front list's bar: at least MIN_FRONT_DAYS days with records in the RECENT_DAYS before `day` (P6's window)."""
    return window(pair, column_days, day, RECENT_DAYS).days >= MIN_FRONT_DAYS


def on_list(found: Verdict, pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> bool:
    """Whether the product is on its store type's front list: a deal that passes the bar."""
    return found.call == "deal" and passes_bar(pair, column_days, day)


def checked(found: Verdict, pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> bool:
    """Whether the product is one the headline counts as checked (M): a promotion counts today and it passes the bar."""
    return found.counting and passes_bar(pair, column_days, day)


def front_list(rows: Iterable[DealRow]) -> list[DealRow]:
    """The rows by saving, largest first, then by barcode as a number; all of them."""
    return sorted(rows, key=lambda row: (-row.verdict.saving, by_number(row.code)))

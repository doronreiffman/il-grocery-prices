"""The shopper site's words: the word lists, the credit and date lines, the names of the views, the sentences of P7,
F10 and P10, by column, and the verdict's (docs/shopper-site.md, "Words", "What a visitor sees", P5 to P10, F10, and
"Changed after the survey", its "Words"; docs/store-first.md, "Words"; the plan's Task 15, questions J, K, M (f) and O;
the first pre-flight's S10, the second's S7, N4, N7 and N23; Task 9's review rulings on a change's dates; the
store-first plan's Task 3 and its "Words this plan adds").

The lists. ALWAYS holds the four phrases the design puts beside every listed price and every promotion, and
ALWAYS_SENTENCE holds all four in one fixed sentence, so a product page carries them even for a product listed nowhere
today (S7). It is written for the product pages, whose listed prices are a store format's medians with the stores left
out by rule (such as Shufersal Deal's online store) set aside, by the rules the method page gives (it names the stores
the store list leaves out and store 779, not a later store left out by its files' names); never for basket.html,
whose prices are each chain's median and which keeps the basket's own sentence. NEVER is the basket's list followed
by the design's own, unchanged in step one: a bare "will" would trip the method page's plain sentences, and step three's
odds line revisits F11's "will" and "likely" (N23). ODDS_WORDS are the words a closed column's section may hold only
inside F10's sentence (`no_odds_yet`). Every sentence here is free of a NEVER phrase, of "we", "our" and "us", and,
F10's sentence aside, of every odds word.

Names. A column is named by `shopper.columns` ("Shufersal Deal"; a whole chain by its own name); a chain by
`basket.words.CHAIN_NAMES`. F10's sentence names the column, P10's the chain, on each of its columns (question M (g)).
The site's name is "Deal or No Deal" (question J, as the owner changed it on 2026-11-10), one constant, so a rename is
one line; every page's header names the five chains under it (`CHAINS_LINE`) and then the day (`date_line`).

The front page in plain words (the owner, 2026-11-10, the review round after them, and the owner's final framing that
evening: is the promotion a shopper sees actually a deal?). The title asks that question; a line under it
(`FRONT_SUBTITLE`) says what each promotion is checked against, "up to" 3 months of shelf prices, since the records
start on 1 November 2026 and the 90-day window holds fewer days until late January; one lead line (`lead_line`) says
how many passed, the site-day file's `below`, or why none did, with no total beside it: the products on promotion the build counts are only those carried by at least half
of a format's stores, which the fold-out's count says (`promotions_line`, the final review's finding 4). The rule in
full is the fold-out's (`shopper.pages`), in the store format's words, since a deal is tested against its own column's
listed prices and another format of the same chain may list the item lower (question O).

Counts over days (P6). Every count over a window's days is out of its days with records: "of the N days with records
before today", N the days of the window (which ends the day before the page's day) on which the column has a record and
the product a listed price; a short window (fewer than 20 of 30, or 60 of 90) says instead "of the 23 days of records
since 1 November 2026 before today", and one day of records says that day after "before today": "the one day of records
before today (19 November 2026)", never "since" it (q31); P7's lows say "of them", "of those 85" or "of the 90 days with
records".

What the words state (Task 15's review, fix round 1): never more than the figures shown and the records support. Every
comparison or change a sentence states is worked on the two-place figures it shows (half up: a listed price by
`basket.record.money`, a deal price by `shopper.deals.to_agora`), so the page agrees with itself; the exact prices stay
for ranking and depth (`shopper.measures`), which the words never state, and the front page's test compares the shown
figures too (`shopper.measures.on_front`, fix round 2). And only consecutive days with records pin a date: an edge with
a gap in the records beside it (a hole, a day the product is not listed, a day whose promotions were not read) is a
bound, wherever it sits.

P7, three sentences, no verdict word. The deal against the 30-day median: "Deal price ₪7.90: ₪4.00, 34%, below the
30-day median listed price of ₪11.90 (of the 30 days with records before today).", with one day of records "(of the one
day of records before today, 19 November 2026)", the date after a comma inside the brackets (q31), the amount and the
whole percent (half up) worked from the median and the deal as shown ("under 1%" for a gap above ₪0 that rounds to 0%:
deploy prep), or "not below" when the shown deal is not under the shown median. The lows, each over the days of records
its window holds, by the change sentence's window kinds (P6, deploy prep), said once when both windows hold the same
days, and the days at or below the deal, counted on the shown figures: "The lowest listed price was ₪11.90 in the 30
days before today and ₪10.90 in the 90 days before today; listed at ₪7.90 or less on 0 of the 90 days with records.", or
at launch "The lowest listed price over the 15 days of records before today (the first on 1 November 2026) was ₪10.00;
listed at ₪7.90 or less on 0 of them.", or with a short 90-day window beside a full 30-day one "… in the 30 days before
today and ₪9.00 over the 39 days of records before today (the first on 12 October 2026); listed at ₪7.90 or less on 0 of
those 39."; one day of records: "The listed price on the one day of records before today (5 November 2026) was ₪10.00,
above ₪7.90." ("below ₪7.90" when it was, as shown, and "the same as the deal price" at it: q31), a 30-day window of one
day beside more in the 90 "on the one day of records before today (19 November 2026)"; a short window's note
(`window_note`) spells one day "one day of records since 19 November 2026", never "1 day", though a count over one day
says it as that day (q31). The changes: a change is one in the shown figures (a median of ₪1.445 moving to ₪1.45 is
none: both show ₪1.45); "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026." between two consecutive days
with records; across a gap in the records the change lies somewhere between the two days, so both are given ("rose from
₪10.90 (15 November 2026) to ₪11.90 (17 November 2026)"), never one date the files cannot pin; several in day order,
joined by "then". With none: "The listed price did not change in the 30 days before today." when each of the 30 has a
record, else "did not change on the 25 days with records of the 30 before today" (or a short window's words), since the
files say nothing of the other days; over one day of records nothing is said, since one day has nothing to compare
(q31), though a change from a record before the 30 to its one day is.

P7's change list shows at most CHANGES_SHOWN (5) changes, the newest, in day order (Task 16, round 2). When more were
seen, a tail says how many, in the very phrase the sentence uses for its window when nothing changed: "…, then fell from
₪11.90 to ₪10.90 on 19 November 2026 (the last 5 of 30 changes seen in the 30 days before today)." P7 is the front
page's story now (`shopper.pages`); the product page's verdict, chart and fold-out replaced it there (store first, q33).

The product page's fold-out labels (Task 16, kept by store first): the design's and the brief's phrases put together,
never a claim of their own. Today's listed price carries "before promotions" and "as listed in the chain's price files"
(`listed_price`), the listed price's definition; a deal's price is a unit's or a kilogram's (`deal_price`, P4), with "buy
N" for "N for ₪M"; a percent-off deal's range is the stores' (`stores_range`), never a listed price, so ALWAYS_SENTENCE
stays true; "minimum spend ₪150.00".

Conditions (P5, question K and S3). A promotion's restrictions read from `ClubID` are K's phrase for each code present,
joined in the order club, card, other ("club members only, and some customers only"); the programmes' names go beside
them, as published, in the chain's own span (the product page's). The front page's fold-out names the chains whose
files mark no restricted promotion that day ("Today Shufersal's files mark no deal this way.", `marked_none`), after
what the club-only filter hides.

The price chart (store first, q33: docs/store-first.md, "The chart"; the plan's "Words this plan adds", provisional
until the owner's read). Its labels are a kind and a price as shown, "usually ₪8.90", "lowest ₪6.90", "highest
₪8.90", "today ₪6.90" (`chart_label`); its key, after the SVG, is CHART_KEY's three marks, the shelf price in
shopper text; its text alternative, the SVG's title, names the labels in CHART_KINDS' order: "Price chart: usually
₪8.90, lowest ₪6.90, highest ₪8.90, today ₪6.90." (`chart_summary`), each when the chart draws it (`shopper.chart`:
the usual price with a verdict of deal or no deal, the lowest and highest day prices of the tracked days when one has
a price, today's price when it is known), and "Price chart." with none.

The verdict (store first, q33: docs/store-first.md, "Words", verbatim; the plan's "Words this plan adds", provisional
until the owner's read), from a `shopper.verdict.Verdict`. Shopper text says a day as its day and month, no year
(`on_day`: "12 October"), and "shelf price", never "listed price", which the fold-out defines. The badge names the store
type, so a pick left over from last week shows itself: "At Carrefour Market: DEAL · ₪1.90 off" or "At Carrefour
Market: NO DEAL" (`badge`); the badge row's own, under "Elsewhere today" (ELSEWHERE), puts the name first: "Rami Levy ·
DEAL · ₪1.90 off", "Rami Levy · NO DEAL", or a call without a verdict as its line in lower case without its full stop,
"Rami Levy · no sale today" ("too few files today" on a hole, "not sold today"; `short_badge`). The reason (`reason`,
S8) names the days it rests on, those with a day price: a deal "Usually ₪11.90, sales included (9 days tracked)."; a no
deal with no saving or a negative one, the always-on form, "It's been ₪10.90 or less on 9 of the 9 days tracked."
(today's price, and the days at or below it); a saving above ₪0.00 and below ₪1.00, the small form, "Only ₪0.40 below
its usual ₪3.20 (12 days tracked)."; one day is "1 day". A weighed product's saving and usual price are a kilogram's
("DEAL · ₪19.90 off a kilogram", "Usually ₪69.90 a kilogram, …"), as its deal price is (P4). The conditions of the
promotion judged (`conditions`): question K's phrases with a capital letter, "Club members only", "The chain's card
holders only", "Some customers only", then "When you buy 2" ("When you buy 1.5 kilograms"), then "Minimum spend
₪150.00"; a programme's name is the fold-out's, in the chain's span. Without a verdict, NO_VERDICT's line by call (the
design's six, and the plan's "No price history yet."), `basket.words.too_few` on a hole, or `not_sold`: "Not sold at
Carrefour Market today, last seen 3 November" ("today" alone with no such day). Last this low (S6, `last_low`): "Last
this low: 12 October, at ₪9.90." or "Lowest in the 10 days tracked.", only when today's price is known and a day before
today has a day price. How often (S7, `how_often`), over every tracked day: "On sale on 12 of the 60 days tracked.",
then "The last sale before this one ended 12 October, at ₪9.90." when today is on sale, "The last sale ended …" when it
is not, the price left out when it was not read; nothing with no tracked day. A coming sale (F2, `coming_sale`): "A
sale starts on 14 November". The fold-out's name: "How this is worked out" (WORKED_OUT).
"""
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from basket.chains import SLUGS
from basket.record import money
from basket.units import plain
from basket.words import CHAIN_NAMES, METHOD_TITLE, NEVER as BASKET_NEVER, joined
from shopper.columns import BY_KEY, COLUMNS, columns_of
from shopper.deals import to_agora
from shopper.forecast import FIRST_RECORD_DAY
from shopper.history import READ_DAYS, Window
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS, Change, Gap, whole
from shopper.promotions import RESTRICTIONS
from shopper.verdict import Verdict

SITE_NAME = "Deal or No Deal"                       # question J, as the owner changed it on 2026-11-10
CHAINS_LINE = " · ".join(CHAIN_NAMES[slug] for slug in SLUGS)              # every page's header, under the name
FRONT_TITLE = "Is it actually a deal?"           # Q4, the owner's final framing of 2026-11-10
# under the title: READ_DAYS (90) as 3 months, "up to" while the records hold fewer (they start on 1 November 2026)
FRONT_SUBTITLE = f"Promotions checked against up to {READ_DAYS // 30} months of shelf prices."
GAP_HEADING = "The deal against its listed prices"                        # Q4, the front page's story
RECORD_TITLE = "Track record"
ALWAYS = ("listed price", "as listed in the chain's price files", "before promotions", "listed in the morning's files")
ALWAYS_SENTENCE = ("Every listed price here is as listed in the chain's price files, before promotions: the median "
                   "across the stores of its store format that list the item, apart from the stores left out by rule "
                   f"({METHOD_TITLE} gives the rules); every promotion is as listed in the morning's files.")
# S7: the four ALWAYS phrases in one sentence, for every product page (never basket.html: the module's docstring)
NEVER = BASKET_NEVER + ("fake", "fake discount", "fake sale", "real deal", "scam", "rip-off", "trick", "inflated",
                        "misleading", "deceptive", "pretends", "true price", "you save", "best deal", "guaranteed",
                        "will be on sale", "will go on sale", "expected to", "likely to")
ODDS_WORDS = ("odds", "chance", "1 in", "forecast")
FROM_FIELDS = "from the chain's fields"
FROM_TEXT = "read from the fine print"
FINE_PRINT = "fine print not read: club-only or other conditions may apply"
PRICE_NOT_READ = "price not read"
AT_SOME_STORES = "at some stores"
TARGET_PHRASES = {"club": "club members only", "chain_card": "the chain's card holders only",
                  "other": "some customers only"}                         # question K, by RESTRICTIONS' words
CREDIT_START = (f"Prices and promotions from the price and promotion files {joined(list(CHAIN_NAMES.values()))} "
                "publish under section 30 of the Food and Pharma Competition Promotion Law, 2014:")   # N7
HIRING = (("Built by Doron Reiffman", "https://www.linkedin.com/in/doronreiffman"), (METHOD_TITLE, "method.html"),
          (RECORD_TITLE, "record.html"), ("Code on GitHub", "https://github.com/doronreiffman/il-grocery-prices"))
MORNING = "as listed in the morning's files"
CHANGES_SHOWN = 5          # P7's change sentence lists the newest five
NUMBER_WORDS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
                "Twelve")
# The product page's labels (the plan's Task 16, its controller's rulings): the design's and the brief's phrases put
# together, never a sentence of their own
BARCODE = "Barcode"
PER = {"unit": "per unit", "kg": "per kilogram"}             # P4: a weighed deal's price is a kilogram's
BROWSE_LINK = "Browse by first letter"                       # search.js's own "browse by first letter"
# The price chart (store first, q33; the module's docstring)
CHART_KEY = ("shelf price", "on sale", "on sale, price not read")    # the grey line, the green stretches, the foot marks
CHART_KINDS = ("usually", "lowest", "highest", "today")               # the labels, in the text alternative's order
# The verdict (store first, q33; the module's docstring)
ELSEWHERE = "Elsewhere today"                    # the badge row's heading
WORKED_OUT = "How this is worked out"            # the fold-out
NO_VERDICT = {                                   # the design's six lines by call, then the plan's provisional one
    "no_sale": "No sale today",
    "new": "New today: no price history yet.",
    "some_stores": "On sale at some stores only",
    "price_unread": "On sale, but the sale price could not be read",
    "unread_today": "Sale prices could not be read today",
    "mostly_unknown": "On sale most days; earlier sale prices could not be read",
    "no_history": "No price history yet.",
}
SHORT = {"too_few": "too few files today", "not_sold": "not sold today"}    # the badge row's, for the two other calls


def _day(day: date) -> str:
    return f"{day:%-d %B %Y}"


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def date_line(day: date) -> str:
    """The last line of every page's header, under the site's name and the chains' line."""
    return f"Prices of {day:%A %-d %B %Y}"


def credit(day: date, collected_by: str) -> str:
    """The credit line in every page's footer."""
    return (f"{CREDIT_START} the files of {_day(day)}, collected by {collected_by} Israel time. Listed prices and "
            "listed promotions, not a promise of what a till charges. Not shopping advice.")


def no_odds_yet(column: str) -> str:
    """F10's fixed sentence, naming the column (the amendment's "Words"): forecasts start on a column's 30th day of
    records and are frozen only on the days F2 allows, never "every day" (the owner, 2026-11-10)."""
    return (f"No odds yet for {BY_KEY[column].name}. From a store format's {FIRST_RECORD_DAY}th day of records, this "
            "site freezes forecasts on each day its rules allow and scores them two weeks later; the odds appear here "
            f"once they beat two rules of thumb over 90 days ({RECORD_TITLE}).")


def unreadable(slug: str) -> str:
    """P10's sentence, naming the chain; it goes on every section of the chain's columns (question M (g))."""
    return f"Promotions from {CHAIN_NAMES[slug]}'s files could not be read today."


def as_listed(columns: Sequence[str]) -> str:
    """Which columns list a name as published (Call 4): "(as Rami Levy lists it)", in the columns' order."""
    names = [column.name for column in COLUMNS if column.key in set(columns)]
    if not names:
        raise ValueError("a name is listed by at least one column")
    return f"(as {joined(names)} {_plural(len(names), 'lists', 'list')} it)"


def listed_price(price: Decimal) -> str:
    """Today's listed price (P2) as shown (`basket.record.money`), with the ALWAYS phrases a listed price takes."""
    return f"Listed price ₪{money(price)}, before promotions, as listed in the chain's price files"


def deal_price(price: Fraction, per: str) -> str:
    """A deal's price as shown (`shopper.deals.to_agora`), a unit's or a kilogram's (P4)."""
    return f"Deal price ₪{to_agora(price)} {PER[per]}"


def buy(quantity: Decimal) -> str:
    """The condition of "N for ₪M" (P4)."""
    return f"buy {plain(quantity)}"


def stores_range(low: Decimal, high: Decimal) -> str:
    """A percent-off deal's range over the stores carrying it (S4), labelled as the stores' deal prices, never a listed
    price nor the listed price's own range beside it (deploy prep)."""
    return f"stores' deal prices ₪{money(low)} to ₪{money(high)}"


def minimum_spend(amount: Decimal) -> str:
    """P5's minimum spend, from `MinPurchaseAmount`."""
    return f"minimum spend ₪{money(amount)}"


def chart_label(kind: str, price: Decimal) -> str:
    """A label on the price chart, one of CHART_KINDS and the price as shown: "usually ₪8.90"."""
    if kind not in CHART_KINDS:
        raise ValueError(f"no chart label {kind!r}")
    return f"{kind} ₪{money(price)}"


def chart_summary(found: Verdict) -> str:
    """The price chart's text alternative: its labels in CHART_KINDS' order, each when the chart draws it (the module's
    docstring); "Price chart." with none."""
    priced = [day.price for day in found.priced]
    prices = {"usually": found.usual, "lowest": min(priced, default=None), "highest": max(priced, default=None),
              "today": found.today_price}
    said = [chart_label(kind, prices[kind]) for kind in CHART_KINDS if prices[kind] is not None]
    return f"Price chart: {', '.join(said)}." if said else "Price chart."


def last_across(column: str, day: date) -> str:
    """When a product was last seen listed across a column (Call 10): "seen", since the registry keeps the last such
    day with a record, and a hole day after it could have been one (deploy prep)."""
    return f"last seen listed across {BY_KEY[column].name} on {_day(day)}"


def lead_line(below: int, ready: bool) -> str:
    """The front page's lead line (the owner's final framing, 2026-11-10; question A: the products are barcodes):
    `below` passed, the barcodes with a front row, each passing every front condition. With none: "None yet" while no
    column can have a product with MIN_FRONT_DAYS days of records in the RECENT_DAYS (`ready` false:
    `shopper.pages.front_ready`), else none passed today. Never "listed": the site's word for shelf prices."""
    if below:
        return f"{below:,} {_plural(below, 'product', 'products')} passed today."
    if not ready:
        return f"None yet: a product needs {MIN_FRONT_DAYS} days of price history first."
    return "None passed today."


def promotions_line(promotions: int, products: int) -> str:
    """The front page's fold-out count: the promotions listed across a column today, distinct by chain and id, and
    their products (`shopper.build`), said as what they are, carried by at least half of a format's stores (the final
    review's finding 4), never every promotion in the chains' files."""
    return (f"Today the five chains list {promotions:,} {_plural(promotions, 'promotion', 'promotions')} carried by at "
            f"least half of a store format's stores, on {products:,} {_plural(products, 'product', 'products')}.")


def marked_none(marking_none: Sequence[str]) -> str:
    """The fold-out's sentence after what the club-only filter hides (question K): the chains (slugs) whose files mark
    no restricted promotion today, in slug order; "" when every chain's files mark one."""
    named = [f"{CHAIN_NAMES[slug]}'s" for slug in SLUGS if slug in set(marking_none)]
    return f"Today {joined(named)} files mark no deal this way." if named else ""


def targets(restrictions: Sequence[str]) -> str:
    """Question K's phrase for each restriction present (`shopper.promotions.Target.restrictions`), each once, in the
    order club, card, other, joined (S3); "" for none."""
    phrases = [phrase for code, phrase in TARGET_PHRASES.items() if code in set(restrictions)]
    if len(phrases) < 2:
        return "".join(phrases)
    return f"{', '.join(phrases[:-1])}, and {phrases[-1]}"


def window_note(window: Window) -> str:
    """A short window's days (P6): "23 days of records since 1 November 2026"; one day spelled "one day of records
    since 19 November 2026", never "1 day" (deploy prep), though a count over one day says it as that day (`_count`,
    q31)."""
    if window.since is None:
        return "no days of records"
    count = "one day" if window.days == 1 else f"{window.days} days"
    return f"{count} of records since {_day(window.since)}"


def _the_days(window: Window) -> str:
    """The days a count over `window` is out of (P6): "the 90 days with records", or a short window's note."""
    if window.short:
        return f"the {window_note(window)}"
    return f"the {window.days} {_plural(window.days, 'day', 'days')} with records"


def _count(window: Window, inside: bool = False) -> str:
    """`_the_days`, said to be before today: P6's window ends the day before the page's day. One day of records is said
    as that day, its date after "before today" (q31): "the one day of records before today (19 November 2026)", or
    "the one day of records before today, 19 November 2026" `inside` a sentence's own brackets, so none nest; never
    "since 19 November 2026 before today"."""
    if window.days == 1:                                            # q31: one date form for one day
        when = f", {_day(window.since)}" if inside else f" ({_day(window.since)})"
        return f"the one day of records before today{when}"
    return f"{_the_days(window)} before today"


def coming_sale(start: date) -> str:
    """An item with a wide promotion listed to start within 14 days (F2, Call 22), in shopper words: measured, and not
    forecast."""
    return f"A sale starts on {on_day(start)}"


def formats_note() -> str:
    """The basket page's sentence: the basket keeps each chain's median (the amendment's S1)."""
    split = joined([f"{CHAIN_NAMES[slug]}'s" for slug in SLUGS if len(columns_of(slug)) > 1])
    return (f"The product pages show {split} store formats apart; the basket takes each chain's median over its "
            "included stores whose file lists the item.")


def columns_tested(count: int) -> str:
    """The record page's sentence on how many columns are tested at once (the amendment's "Words", F9); no closing
    rule, which no step has built (deploy prep)."""
    number = NUMBER_WORDS[count] if count < len(NUMBER_WORDS) else f"{count:,}"
    return (f"{number} {_plural(count, 'column is', 'columns are')} tested at once: the more are tested, the likelier "
            "one passes the gate by luck.")


def date_range(start: date, end: date) -> str:
    """A run's days, both pinned: "3 to 9 November 2026", "31 October to 2 November 2026", "5 November 2026"."""
    if start == end:
        return _day(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day} to {_day(end)}"
    if start.year == end.year:
        return f"{start:%-d %B} to {_day(end)}"
    return f"{_day(start)} to {_day(end)}"


# P7

def _shown(amount: Decimal) -> Decimal:
    """A listed price as the page shows it: to the agora, half up (`basket.record.money`)."""
    return Decimal(money(amount))


def shown_below(gap: Gap) -> tuple[Decimal, int] | None:
    """The deal's gap below the 30-day median as the pages show it: the amount and the whole percent (half up), worked
    from the median and the deal as shown (the module's docstring); None when the shown deal is not below the shown
    median. P7's first sentence and the front page's depth column both read it."""
    median, deal = _shown(gap.median30), to_agora(gap.deal)
    amount = median - deal
    if amount <= 0:
        return None
    return amount, whole(100 * Fraction(amount) / Fraction(median))


def percent_text(percent: int) -> str:
    """A shown gap's whole percent as the pages write it (`shown_below`'s, never None): "under 1%" when the gap is
    above ₪0 but rounds to 0%, never "₪0.10, 0%, below" (deploy prep); P7's first sentence and the front page's depth
    column both write it so."""
    return "under 1%" if percent == 0 else f"{percent}%"


def _against_median(gap: Gap) -> str:
    """The deal against the 30-day median, worked from both as shown (`shown_below`)."""
    said = f"the 30-day median listed price of ₪{_shown(gap.median30)}"
    found = shown_below(gap)
    if found is None:
        return f"not below {said}"
    amount, percent = found
    return f"₪{amount}, {percent_text(percent)}, below {said}"


def _change(change: Change) -> str:
    before, after = _shown(change.before), _shown(change.after)
    verb = "rose" if after > before else "fell"
    if change.since + timedelta(days=1) == change.day:
        return f"{verb} from ₪{before} to ₪{after} on {_day(change.day)}"
    return f"{verb} from ₪{before} ({_day(change.since)}) to ₪{after} ({_day(change.day)})"


def _window_phrase(recent: Window, length: int) -> str:
    """The days a change sentence over `recent`, a window of `length` days, speaks of: all of them only when each has
    a record."""
    if recent.days == length:
        return f"in the {length} days before today"
    if recent.short:
        return f"on {_count(recent)}"
    return f"on {_the_days(recent)} of the {length} before today"


def _unchanged(recent: Window, length: int) -> str:
    return f"The listed price did not change {_window_phrase(recent, length)}."


def _changes_sentence(found: Sequence[Change], recent: Window, length: int) -> str | None:
    """The changes the shown figures show, the newest CHANGES_SHOWN in day order, joined by "then", with a tail when
    more were seen; or that there was none over `recent`, a window of `length` days (P7's third sentence, and the
    product page's history over the 90); None when there was none over one day of records, which has nothing to
    compare (q31)."""
    stated = [change for change in found if _shown(change.before) != _shown(change.after)]
    if not stated:
        return None if recent.days == 1 else _unchanged(recent, length)
    tail = ""
    if len(stated) > CHANGES_SHOWN:
        tail = f" (the last {CHANGES_SHOWN} of {len(stated)} changes seen {_window_phrase(recent, length)})"
    return f"The listed price {', then '.join(_change(change) for change in stated[-CHANGES_SHOWN:])}{tail}."


def _one_day(window: Window) -> str:
    """A window of one day of records, said as that day: "on the one day of records before today (5 November 2026)"."""
    return f"on {_count(window)}"


def _over(window: Window, length: int) -> str:
    """The days a low is over (P7's second sentence), by the window kinds of the change sentence (P6): all of them when
    each has a record; else "over" its days with records, never "on", which could read as the price on every one of
    them, and a short window's first day after its count (the owner, 2026-11-10); one day of records as that day, as
    the one-day form says it (deploy prep)."""
    if window.days == length:
        return _window_phrase(window, length)                       # "in the 30 days before today"
    if window.days == 1:                                            # the 30's one day beside more in the 90
        return _one_day(window)
    if window.short:
        return f"over the {window.days} days of records before today (the first on {_day(window.since)})"
    return f"over the {window.days} days with records of the {length} before today"


def _lows(gap: Gap, deal: Decimal) -> str:
    """P7's second sentence: the lowest listed price over each window's days of records, said once when both windows
    hold the same days, and on how many of the 90's days with records the item was listed at or below the deal, both
    as shown (P6's "of the N days with records": "of them", "of those 45", or "of the 90 days with records" for a full
    window); one day of records is said as that day's price, never "0 of the 1 day", and above, at or below the deal,
    the true one of the three on the figures shown (deploy prep), "at" as "the same as the deal price" (q31)."""
    long = gap.window90
    if long.days == 1:                                  # the 30's one day too: a gap needs a day of records in the 30
        listed = _shown(gap.low90)
        where = "above" if listed > deal else "at" if listed == deal else "below"
        against = "the same as the deal price" if where == "at" else f"{where} ₪{deal}"     # q31: names the deal
        return f"The listed price {_one_day(long)} was ₪{listed}, {against}."
    at_or_below = sum(1 for listed in long.listed if _shown(listed) <= deal)
    if gap.window30.days == long.days:                  # the same days: every one of the 90's is in the 30
        return (f"The lowest listed price {_over(long, READ_DAYS)} was ₪{money(gap.low90)}; listed at ₪{deal} or "
                f"less on {at_or_below} of them.")
    of = f"of the {READ_DAYS} days with records" if long.days == READ_DAYS else f"of those {long.days}"
    return (f"The lowest listed price was ₪{money(gap.low30)} {_over(gap.window30, RECENT_DAYS)} and "
            f"₪{money(gap.low90)} {_over(long, READ_DAYS)}; listed at ₪{deal} or less on {at_or_below} {of}.")


def gap_sentences(gap: Gap) -> tuple[str, ...]:
    """P7's three sentences for a deal's gap (`shopper.measures.gap`; the module's docstring), or its first two when the
    30 days hold one day of records and no change (q31)."""
    deal = to_agora(gap.deal)
    said = (f"Deal price ₪{deal}: {_against_median(gap)} (of {_count(gap.window30, inside=True)}).", _lows(gap, deal))
    changed = _changes_sentence(gap.changes, gap.window30, RECENT_DAYS)
    return said if changed is None else (*said, changed)


# The verdict (store first, q33)

def on_day(day: date) -> str:
    """A day in shopper text: its day and month, no year ("12 October")."""
    return f"{day:%-d %B}"


def _tracked(count: int) -> str:
    return f"{count} {_plural(count, 'day', 'days')} tracked"


def _per(found: Verdict) -> str:
    """" a kilogram" after a weighed product's prices, whose deal price is a kilogram's (P4); else ""."""
    return " a kilogram" if found.struct is not None and found.struct["per"] == "kg" else ""


def _verdict(found: Verdict) -> str:
    """The verdict's words: "DEAL · ₪1.90 off" or "NO DEAL"."""
    if found.call == "deal":
        return f"DEAL · ₪{found.saving} off{_per(found)}"
    if found.call == "no_deal":
        return "NO DEAL"
    raise ValueError(f"no verdict for the call {found.call!r}")


def badge(found: Verdict) -> str:
    """A deal's or a no deal's badge, naming the store type: "At Carrefour Market: DEAL · ₪1.90 off"."""
    return f"At {BY_KEY[found.column].name}: {_verdict(found)}"


def short_badge(found: Verdict) -> str:
    """A badge of the row under "Elsewhere today": the store type's name, then the verdict, or the line of a call
    without one in lower case, without its full stop ("Rami Levy · no sale today")."""
    if found.call in ("deal", "no_deal"):
        said = _verdict(found)
    else:
        line = SHORT.get(found.call) or NO_VERDICT[found.call]
        said = (line[0].lower() + line[1:]).removesuffix(".")
    return f"{BY_KEY[found.column].name} · {said}"


def reason(found: Verdict) -> str | None:
    """The reason beside a verdict (S8: the days with a day price it rests on): the deal's, the always-on form when the
    saving is ₪0.00 or less, else the small form; None without a verdict."""
    if found.call not in ("deal", "no_deal"):
        return None
    days = _tracked(len(found.priced))
    if found.call == "deal":
        return f"Usually ₪{found.usual}{_per(found)}, sales included ({days})."
    if found.saving <= 0:
        at_or_below = sum(1 for day in found.priced if day.price <= found.today_price)
        return f"It's been ₪{found.today_price}{_per(found)} or less on {at_or_below} of the {days}."
    return f"Only ₪{found.saving} below its usual ₪{found.usual}{_per(found)} ({days})."


def not_sold(column: str, last: date | None) -> str:
    """The line of a store type not selling it today, with the last day it was seen listed across it (Call 10's)."""
    seen = "" if last is None else f", last seen {on_day(last)}"
    return f"Not sold at {BY_KEY[column].name} today{seen}"


def conditions(struct: Mapping) -> list[str]:
    """The conditions of a promotion (a struct of the items table's `promotions`) in shopper words: question K's
    phrases with a capital letter, in the order club, card, other; the quantity; the minimum spend."""
    found = [phrase[0].upper() + phrase[1:] for code, phrase in TARGET_PHRASES.items()
             if code in set(struct["restrictions"])]
    if struct["buy"] != 1:
        found.append(f"When you buy {plain(struct['buy'])}{' kilograms' if struct['per'] == 'kg' else ''}")
    if struct["min_spend"] is not None:
        found.append(f"Minimum spend ₪{money(struct['min_spend'])}")
    return found


def last_low(found: Verdict) -> str | None:
    """S6: the latest day at or below today's price, or that none was; None unless today's price is known and a day
    before today has a day price."""
    if found.today_price is None or not found.priced:
        return None
    if found.last_low is None:
        return f"Lowest in the {_tracked(len(found.priced))}."
    return f"Last this low: {on_day(found.last_low.day)}, at ₪{found.last_low.price}."


def how_often(found: Verdict) -> str | None:
    """S7: the tracked days on sale, unknown prices included, and the last sale's end and price; None with no tracked
    day."""
    if not found.days:
        return None
    said = f"On sale on {sum(day.on_sale for day in found.days)} of the {_tracked(len(found.days))}."
    sale = found.last_sale
    if sale is None:
        return said
    before = " before this one" if found.on_sale_today else ""
    price = "" if sale.price is None else f", at ₪{sale.price}"
    return f"{said} The last sale{before} ended {on_day(sale.day)}{price}."

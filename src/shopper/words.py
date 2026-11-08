"""The shopper site's words: the word lists, the credit and date lines, the names of the views, and the sentences of P7,
P8, F10 and P10, by column (docs/shopper-site.md, "Words", "What a visitor sees", P5 to P10, F10, and "Changed after the
survey", its "Words"; the plan's Task 15, questions J, K, M (f) and O; the first pre-flight's S10, the second's S7, N4,
N7 and N23; Task 9's review rulings on P8's count, a change's dates and the runs at the window's ends).

The lists. ALWAYS holds the four phrases the design puts beside every listed price and every promotion, and
ALWAYS_SENTENCE holds all four in one fixed sentence, so a product page carries them even for a product listed nowhere
today (S7). It is written for the product pages, whose listed prices are a store format's medians with the stores left
out by rule (such as Shufersal Deal's online store) set aside, as the method page names them; never for basket.html,
whose prices are each chain's median and which keeps the basket's own sentence. NEVER is the basket's list followed
by the design's own, unchanged in step one: a bare "will" would trip the method page's plain sentences, and step three's
odds line revisits F11's "will" and "likely" (N23). ODDS_WORDS are the words a closed column's section may hold only
inside F10's sentence (`no_odds_yet`). Every sentence here is free of a NEVER phrase, of "we", "our" and "us", and,
F10's sentence aside, of every odds word.

Names. A column is named by `shopper.columns` ("Shufersal Deal"; a whole chain by its own name); a chain by
`basket.words.CHAIN_NAMES`. F10's sentence names the column, P10's the chain, on each of its columns (question M (g)).
The front page's rule and its count line say "in the same store format" and "in their store format", since a deal is
tested against its own column's listed prices and another format of the same chain may list the item lower (question
O). The site's name, "Five chains, listed prices" (question J), stays true of nine columns: they are the formats of five
chains.

Counts over days (P6). Every count over days says "of the N days with records before today", N the days of the window
(which ends the day before the page's day) on which the column has a record and the product a listed price; a short
window (fewer than 20 of 30, or 60 of 90) says instead "of the 23 days of records since 1 November 2026 before today".
P7 and P8 count the 90-day window's days the same way, so a section never shows two numbers for its days with records:
the days whose promotions could not be read are said beside the count, never taken out of it (Task 9's review,
ruling 1).

What the words state (Task 15's review, fix round 1): never more than the figures shown and the records support. Every
comparison or change a sentence states is worked on the two-place figures it shows (half up: a listed price by
`basket.record.money`, a deal price by `shopper.deals.to_agora`), so the page agrees with itself; the exact prices stay
for ranking and depth (`shopper.measures`), which the words never state, and the front page's test compares the shown
figures too (`shopper.measures.on_front`, fix round 2). And only consecutive days with records pin a date: an edge with
a gap in the records beside it (a hole, a day the product is not listed, a day whose promotions were not read) is a
bound, wherever it sits.

P7, three sentences, no verdict word. The deal against the 30-day median: "Deal price ₪7.90: ₪4.00, 34%, below the
30-day median listed price of ₪11.90 (of the 30 days with records before today).", the amount and the whole percent
(half up) worked from the median and the deal as shown, or "not below" when the shown deal is not under the shown
median. The lows and the days at or below the deal, counted on the shown figures: "The lowest listed price was ₪10.90
over the 30 days before today and ₪10.90 over the 90; listed at ₪7.90 or less on 0 of the 90 days with records before
today." The changes: a change is one in the shown figures (a median of ₪1.445 moving to ₪1.45 is none: both show
₪1.45); "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026." between two consecutive days with records;
across a gap in the records the change lies somewhere between the two days, so both are given ("rose from ₪10.90 (15
November 2026) to ₪11.90 (17 November 2026)"), never one date the files cannot pin; several in day order, joined by
"then". With none: "The listed price did not change in the 30 days before today." when each of the 30 has a record,
else "did not change on the 25 days with records of the 30 before today" (or a short window's words), since the files
say nothing of the other days.

The listed-price history on a product page (`price_history`, the plan's Task 16): P7's change sentence over the 90-day
window, every change of the window (`shopper.measures.changes`) on the same rules: the shown figures, both days across
a gap in the records. With none: "The listed price did not change in the 90 days before today." when each of the 90
has a record, else "did not change on the 85 days with records of the 90 before today" (or a short window's words);
with no day of records in the 90, nothing.

Both change lists (P7's and the history's) show at most CHANGES_SHOWN (5) changes, the newest, in day order and in
the same words (Task 16, round 2: a page of nine columns whose prices change daily stays under 60 KB). When more were
seen, a tail says how many, in the very phrase the sentence uses for its window when nothing changed: "…, then fell from
₪11.90 to ₪10.90 on 19 November 2026 (the last 5 of 89 changes seen in the 90 days before today)."

P8, from the 90-day window (`shopper.measures`), naming the column as the amendment's "Words" do, so a promotion carried
by fewer than half the column's stores is never denied: "On a promotion listed across Shufersal Deal on 12 of the 87
days with records before today, as listed in the morning's files." ("(promotions could not be read on 2)" before the
comma when some were not read), or "No promotion listed across Shufersal Deal in the 87 days with records before today."
when none was seen and every day was read; "Runs seen before today: 3 to 9 November 2026; 24 to 30 November 2026."
(three of the 90 days not read, one of them outside the runs: "Runs before today:" only when every day outside them was
read); "Days between runs: 14."; "The last run ended on 30 November 2026, 6 days ago." A run's start is pinned only when
the day before it is a day with records whose promotions were read, and its end only when the day after it is (or is
today, read): otherwise the start is "from 22 August 2026 or earlier", the end "to 19 November 2026 or later" and the
days since its end "at most 3 days ago". A day of the window the files say nothing of (a hole, a day the product is not
listed, a day whose promotions were not read) could hold a one-day run nobody saw (fix round 2): one inside the days
between two runs makes them "at most 7"; one after the last run, or a today the files say nothing of, makes it "the last
run seen"; one anywhere outside the runs makes the list "Runs seen before today:". Such a day inside a run hides none. A
run reaching yesterday when today's files list the product on a wide promotion is not over: the section says so first
("On a promotion listed across Shufersal Deal today, as listed in the morning's files.") and says no end. Nor is an end
said when no day after the run was read (today's files saying nothing either way): the run may still be on. With no day
of records in the 90 there is no history to count.

The product page's labels (Task 16): the design's and the brief's phrases put together, never a claim of their own.
Today's listed price carries "before promotions" and "as listed in the chain's price files" (`listed_price`); a deal's
price is a unit's or a kilogram's (`deal_price`, P4), with "buy N" for "N for ₪M"; a percent-off deal's range is the
stores' (`stores_range`), never a listed price, so ALWAYS_SENTENCE stays true; "minimum spend ₪150.00"; "not listed
today"; P9's heading, "Today at each column, in name order"; the chart's key, "listed price" and P8's "a promotion
listed across Shufersal Deal".

Conditions (P5, question K and S3). A promotion's restrictions read from `ClubID` are K's phrase for each code present,
joined in the order club, card, other ("club members only, and some customers only"); the programmes' names go beside
them, as published, in the chain's own span (the product page's). The club-only filter's label names the chains whose
files mark no restricted promotion that day ("from the chains' fields; Shufersal's files mark none").
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
from shopper.history import READ_DAYS, ColumnDay, Pair, Window, window
from shopper.measures import (RECENT_DAYS, Change, Gap, Run, changes, days_since, gaps, promoted_today,
                              promotion_days, promotion_points, runs, whole)
from shopper.promotions import RESTRICTIONS

SITE_NAME = "Five chains, listed prices"                                  # question J
FRONT_TITLE = "Deals below their recent listed prices"                    # Q4
# P7, Q3; "in the same store format": question O
FRONT_RULE = ("promotion prices lower than every price the chain listed for the item in the same store format over the "
              "past 90 days with records")
GAP_HEADING = "The deal against its listed prices"                        # Q4
HISTORY_HEADING = "How often it goes on promotion"                        # Q4
RECORD_TITLE = "Track record"
ALWAYS = ("listed price", "as listed in the chain's price files", "before promotions", "listed in the morning's files")
ALWAYS_SENTENCE = ("Every listed price here is as listed in the chain's price files, before promotions: the median "
                   "across the stores of its store format that list the item, apart from the stores left out by rule "
                   f"({METHOD_TITLE} names them); every promotion is as listed in the morning's files.")
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
CHANGES_SHOWN = 5          # a change sentence lists the newest five, so a product page stays under its 60 KB
NUMBER_WORDS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
                "Twelve")
# The product page's labels (the plan's Task 16, its controller's rulings): the design's and the brief's phrases put
# together, never a sentence of their own
BARCODE = "Barcode"
NOT_LISTED = "not listed today"                              # P9, and a section's today
PER = {"unit": "per unit", "kg": "per kilogram"}             # P4: a weighed deal's price is a kilogram's
ACROSS_HEADING = "Today at each column, in name order"       # P9
BROWSE_LINK = "Browse by first letter"                       # search.js's own "browse by first letter"


def _day(day: date) -> str:
    return f"{day:%-d %B %Y}"


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def date_line(day: date) -> str:
    """The line under the site's name in every page's header."""
    return f"from the chains' price and promotion files of {day:%A %-d %B %Y}"


def credit(day: date, collected_by: str) -> str:
    """The credit line in every page's footer."""
    return (f"{CREDIT_START} the files of {_day(day)}, collected by {collected_by} Israel time. Listed prices and "
            "listed promotions, not a promise of what a till charges. Not shopping advice.")


def no_odds_yet(column: str) -> str:
    """F10's fixed sentence, naming the column (the amendment's "Words")."""
    return (f"No odds yet for {BY_KEY[column].name}. Every day this site freezes a forecast for each item and "
            "scores it two weeks later; the odds appear here once they beat two rules of thumb over 90 days "
            f"({RECORD_TITLE}).")


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
    """A percent-off deal's range over the stores carrying it (S4), labelled as the stores', never a listed price."""
    return f"stores ₪{money(low)} to ₪{money(high)}"


def minimum_spend(amount: Decimal) -> str:
    """P5's minimum spend, from `MinPurchaseAmount`."""
    return f"minimum spend ₪{money(amount)}"


def chart_key(column: str) -> tuple[str, str]:
    """The history chart's two marks: the line of listed prices, and the days on a promotion listed across the
    column, in P8's words."""
    return ALWAYS[0], f"a promotion {across(column)}"


def across(column: str) -> str:
    """The design's "listed chain-wide", per column: a promotion carried by at least half the column's counted
    stores."""
    return f"listed across {BY_KEY[column].name}"


def last_across(column: str, day: date) -> str:
    """When a product was last listed across a column (Call 10)."""
    return f"last listed across {BY_KEY[column].name} on {_day(day)}"


def count_line(promotions: int, products: int, below: int) -> str:
    """The front page's count line (question A: the products and those below are barcodes; question O's ending)."""
    return (f"Today the five chains list {promotions:,} {_plural(promotions, 'promotion', 'promotions')} on "
            f"{products:,} {_plural(products, 'product', 'products')}; {below:,} of them "
            f"{_plural(below, 'is', 'are')} below every listed price of the past 90 days in their store format.")


def club_label(marking_none: Sequence[str]) -> str:
    """The club-only filter's label (question K), naming the chains (slugs) whose files mark no restricted promotion."""
    named = [f"{CHAIN_NAMES[slug]}'s" for slug in SLUGS if slug in set(marking_none)]
    label = "from the chains' fields"
    return f"{label}; {joined(named)} files mark none" if named else label


def targets(restrictions: Sequence[str]) -> str:
    """Question K's phrase for each restriction present (`shopper.promotions.Target.restrictions`), each once, in the
    order club, card, other, joined (S3); "" for none."""
    phrases = [phrase for code, phrase in TARGET_PHRASES.items() if code in set(restrictions)]
    if len(phrases) < 2:
        return "".join(phrases)
    return f"{', '.join(phrases[:-1])}, and {phrases[-1]}"


def window_note(window: Window) -> str:
    """A short window's days (P6): "23 days of records since 1 November 2026"."""
    if window.since is None:
        return "no days of records"
    return f"{window.days} {_plural(window.days, 'day', 'days')} of records since {_day(window.since)}"


def _the_days(window: Window) -> str:
    """The days a count over `window` is out of (P6): "the 90 days with records", or a short window's note."""
    if window.short:
        return f"the {window_note(window)}"
    return f"the {window.days} {_plural(window.days, 'day', 'days')} with records"


def _count(window: Window) -> str:
    """`_the_days`, said to be before today: P6's window ends the day before the page's day."""
    return f"{_the_days(window)} before today"


def starts_on(start: date) -> str:
    """An item with a wide promotion listed to start within 14 days (F2, Call 22): measured, and not forecast."""
    return f"Listed to start on {_day(start)}."


def formats_note() -> str:
    """The basket page's sentence: the basket keeps each chain's median (the amendment's S1)."""
    split = joined([f"{CHAIN_NAMES[slug]}'s" for slug in SLUGS if len(columns_of(slug)) > 1])
    return (f"The product pages show {split} store formats apart; the basket takes each chain's median over all its "
            "included stores.")


def columns_tested(count: int) -> str:
    """The record page's sentence on how many columns are tested at once (the amendment's "Words", F9)."""
    number = NUMBER_WORDS[count] if count < len(NUMBER_WORDS) else f"{count:,}"
    return (f"{number} {_plural(count, 'column is', 'columns are')} tested at once: the more are tested, the likelier "
            "one passes the gate by luck, which is why it closes again on a losing run (F9).")


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


def _against_median(gap: Gap) -> str:
    """The deal against the 30-day median, worked from both as shown (the module's docstring)."""
    median, deal = _shown(gap.median30), to_agora(gap.deal)
    said = f"the 30-day median listed price of ₪{median}"
    amount = median - deal
    if amount <= 0:
        return f"not below {said}"
    return f"₪{amount}, {whole(100 * Fraction(amount) / Fraction(median))}%, below {said}"


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


def _changes_sentence(found: Sequence[Change], recent: Window, length: int) -> str:
    """The changes the shown figures show, the newest CHANGES_SHOWN in day order, joined by "then", with a tail when
    more were seen; or that there was none over `recent`, a window of `length` days (P7's third sentence, and the
    product page's history over the 90)."""
    stated = [change for change in found if _shown(change.before) != _shown(change.after)]
    if not stated:
        return _unchanged(recent, length)
    tail = ""
    if len(stated) > CHANGES_SHOWN:
        tail = f" (the last {CHANGES_SHOWN} of {len(stated)} changes seen {_window_phrase(recent, length)})"
    return f"The listed price {', then '.join(_change(change) for change in stated[-CHANGES_SHOWN:])}{tail}."


def gap_sentences(gap: Gap) -> tuple[str, str, str]:
    """P7's three sentences for a deal's gap (`shopper.measures.gap`; the module's docstring)."""
    deal = to_agora(gap.deal)
    first = f"Deal price ₪{deal}: {_against_median(gap)} (of {_count(gap.window30)})."
    at_or_below = sum(1 for listed in gap.window90.listed if _shown(listed) <= deal)
    second = (f"The lowest listed price was ₪{money(gap.low30)} over the {RECENT_DAYS} days before today and "
              f"₪{money(gap.low90)} over the {READ_DAYS}; listed at ₪{deal} or less on {at_or_below} of "
              f"{_count(gap.window90)}.")
    return first, second, _changes_sentence(gap.changes, gap.window30, RECENT_DAYS)


def price_history(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> str | None:
    """The product page's listed-price history as text: P7's change sentence over the 90-day window (every change of
    the window, `shopper.measures.changes`), or that there was none on its days; None with no day of records in the
    90."""
    long = window(pair, column_days, day, READ_DAYS)
    if not long.days:
        return None
    return _changes_sentence(changes(pair, column_days, day, READ_DAYS), long, READ_DAYS)


# P8

def _run(start: date, end: date, open_start: bool, open_end: bool) -> str:
    if not (open_start or open_end):
        return date_range(start, end)
    return f"from {_day(start)}{' or earlier' if open_start else ''} to {_day(end)}{' or later' if open_end else ''}"


def history_sentences(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[str, ...]:
    """P8's sentences for the pair on `day` (the module's docstring), from `shopper.measures`' history of the 90-day
    window and its reading of `day` itself."""
    name = BY_KEY[pair.column].name
    across = f"a promotion listed across {name}"
    records = window(pair, column_days, day, READ_DAYS)
    today = promoted_today(pair, column_days, day)
    now = (f"On {across} today, {MORNING}.",) if today else ()
    if not records.days:
        return now
    on, read = promotion_days(pair, column_days, day)
    unread = records.days - read
    found = runs(pair, column_days, day)
    if found or unread:
        note = f" (promotions could not be read on {unread})" if unread else ""
        count = f"On {across} on {on} of {_count(records)}{note}, {MORNING}."
    else:
        count = f"No promotion listed across {name} in {_count(records)}."
    sentences = [*now, count]
    if not found:
        return tuple(sentences)
    read_days = {point.day for point in promotion_points(pair, column_days, day)}
    one = timedelta(days=1)

    def pinned_start(run: Run) -> bool:
        """The day before the run is a day with records whose promotions were read."""
        return run.start - one in read_days

    def pinned_end(run: Run) -> bool:
        """The day after the run is such a day, or is today and today was read."""
        return run.end + one in read_days or (run.end + one == day and today is not None)

    first = day - timedelta(days=READ_DAYS)
    unseen = [first + timedelta(days=n) for n in range(READ_DAYS) if first + timedelta(days=n) not in read_days]

    def hidden(after: date, before: date) -> bool:
        """A day strictly between the two that the files say nothing of: a one-day run may hide there."""
        return any(after < each < before for each in unseen)

    last = found[-1]
    outside = (hidden(first - one, found[0].start) or hidden(last.end, day)
               or any(hidden(earlier.end, later.start) for earlier, later in zip(found, found[1:])))
    shown = [_run(run.start, run.end, not pinned_start(run), not pinned_end(run)) for run in found]
    sentences.append(f"{_plural(len(found), 'Run', 'Runs')}{' seen' if outside else ''} before today: "
                     f"{'; '.join(shown)}.")
    if len(found) > 1:
        between = [f"{'at most ' if hidden(earlier.end, later.start) else ''}{days}"
                   for earlier, later, days in zip(found, found[1:], gaps(found))]
        sentences.append(f"Days between runs: {'; '.join(between)}.")
    ended = today is False or any(seen > last.end for seen in read_days)
    if not today and ended:
        ago = days_since(found, day)
        ago_text = f"{ago} {_plural(ago, 'day', 'days')} ago"
        seen = hidden(last.end, day) or today is None             # today unknown could hold a later run
        the_last = f"The last run{' seen' if seen else ''} ended on {_day(last.end)}"
        if pinned_end(last):
            sentences.append(f"{the_last}, {ago_text}.")
        else:
            sentences.append(f"{the_last} or later, at most {ago_text}.")
    return tuple(sentences)

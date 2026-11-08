"""The shopper site's words: the word lists, the credit and date lines, the names of the views, and the sentences of P7,
P8, F10 and P10, by column (docs/shopper-site.md, "Words", "What a visitor sees", P5 to P10, F10, and "Changed after the
survey", its "Words"; the plan's Task 15, questions J, K, M (f) and O; the first pre-flight's S10, the second's S7, N4,
N7 and N23; Task 9's review rulings on P8's count, a change's dates and the runs at the window's ends).

The lists. ALWAYS holds the four phrases the design puts beside every listed price and every promotion, and
ALWAYS_SENTENCE holds all four in one fixed sentence, so a product page carries them even for a product listed nowhere
today (S7). NEVER is the basket's list followed by the design's own, unchanged in step one: a bare "will" would trip the
method page's plain sentences, and step three's odds line revisits F11's "will" and "likely" (N23). ODDS_WORDS are the
words a closed column's section may hold only inside F10's sentence (`no_odds_yet`). Every sentence here is free of a
NEVER phrase, of "we", "our" and "us", and, F10's sentence aside, of every odds word.

Names. A column is named by `shopper.columns` ("Shufersal Deal"; a whole chain by its own name); a chain by
`basket.words.CHAIN_NAMES`. F10's sentence names the column, P10's the chain, on each of its columns (question M (g)).
The front page's rule and its count line say "in the same store format" and "in their store format", since a deal is
tested against its own column's listed prices and another format of the same chain may list the item lower (question
O). The site's name, "Five chains, listed prices" (question J), stays true of nine columns: they are the formats of five
chains.

Counts over days (P6). Every count over days says "of the N days with records", N the days of the window on which the
column has a record and the product a listed price; a short window (fewer than 20 of 30, or 60 of 90) says instead
"of the 23 days of records since 1 November 2026". P7 and P8 count the 90-day window's days the same way, so a section
never shows two numbers for its days with records: the days whose promotions could not be read are said beside the
count, never taken out of it (Task 9's review, ruling 1).

P7, three sentences, no verdict word. The deal against the 30-day median: "Deal price ₪7.90: ₪4.00, 34%, below the
30-day median listed price of ₪11.90 (of the 30 days with records).", or "not below" when the deal is not under it, and
"less than ₪0.01" for a gap under half an agora. The lows and the days at or below the deal: "The lowest listed price
was ₪10.90 over the past 30 days and ₪10.90 over the past 90; listed at ₪7.90 or less on 0 of the 90 days with
records." Money is written to the agora, half up: a listed price by `basket.record.money`, a deal price or a gap (exact
fractions) by `shopper.deals.to_agora`. The days at or below are counted against the exact deal, and listed prices are
medians of two-place store prices, so they fall on half agorot: when the deal's figure rounds down, "at ₪3.33 or less"
names exactly the days counted; when it rounds up, "at ₪1.45 or less" would take in a listed ₪1.45 that the count
leaves out, so the sentence says "below ₪1.45". The changes: "The listed price rose from ₪10.90 to ₪11.90 on 28 October
2026." for a change between two consecutive days with records; across a gap in the records the change lies somewhere
between the two days, so both are given ("rose from ₪10.90 (15 November 2026) to ₪11.90 (17 November 2026)"), never one
date the files cannot pin (ruling 2); several changes in day order, joined by "then". With none: "The listed price did
not change in the past 30 days." when each of the 30 days has a record, else "did not change on the 25 days with
records of the past 30" (or a short window's words), since the files say nothing of the other days.

P8, from the 90-day window (`shopper.measures`): "On a promotion on 12 of the 87 days with records, as listed in the
morning's files." ("(promotions could not be read on 2)" before the comma when some were not read), or "No promotion
listed in the 87 days with records." when none was seen and every day was read; "Runs: 3 to 9 November 2026; 24 to 30
November 2026."; "Days between runs: 14."; "The last run ended on 30 November 2026, 6 days ago." The window ends
yesterday, so its ends are said as the files allow (ruling 3): when today's files list the product on a wide promotion,
the section says so first ("On a promotion today, as listed in the morning's files.") and words the history as before
today ("Before today: …", "Runs before today: …"), never that a run ended; a run seen from the first day of the window
whose promotions were read may have begun earlier ("from 22 August 2026 or earlier to 27 August 2026"); and, the
mirror, a run seen to the last day read may have gone on when today's files say nothing either way ("to 19 November
2026 or later"), and then no end is stated. A run's other ends are its days as seen: a gap in the records inside or
beside a run neither breaks nor extends it (P8). With no day of records in the 90 there is no history to count.

Conditions (P5, question K and S3). A promotion's restrictions read from `ClubID` are K's phrase for each code present,
joined in the order club, card, other ("club members only, and some customers only"); the programmes' names go beside
them, as published, in the chain's own span (the product page's). The club-only filter's label names the chains whose
files mark no restricted promotion that day ("from the chains' fields; Shufersal's files mark none").
"""
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from fractions import Fraction

from basket.chains import SLUGS
from basket.record import money
from basket.words import CHAIN_NAMES, METHOD_TITLE, NEVER as BASKET_NEVER, joined
from shopper.columns import BY_KEY, COLUMNS, columns_of
from shopper.deals import to_agora
from shopper.history import READ_DAYS, ColumnDay, Pair, Window, window
from shopper.measures import (RECENT_DAYS, Change, Gap, days_since, gaps, promoted_today, promotion_days,
                              promotion_points, runs)
from shopper.promotions import RESTRICTIONS

SITE_NAME = "Five chains, listed prices"                                  # question J
FRONT_TITLE = "Deals below their recent listed prices"                    # Q4
FRONT_RULE = ("promotion prices lower than every price the chain listed for the item in the same store format over the "
              "past 90 days with records")                                # P7, Q3; "in the same store format": question O
GAP_HEADING = "The deal against its listed prices"                        # Q4
HISTORY_HEADING = "How often it goes on promotion"                        # Q4
RECORD_TITLE = "Track record"
ALWAYS = ("listed price", "as listed in the chain's price files", "before promotions", "listed in the morning's files")
ALWAYS_SENTENCE = ("Every listed price here is as listed in the chain's price files, before promotions, the median "
                   "across the stores of its store format that list the item; every promotion is as listed in the "
                   "morning's files.")                                    # S7: the four ALWAYS phrases, on every page
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
NUMBER_WORDS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
                "Twelve")


def _day(day: date) -> str:
    return f"{day:%-d %B %Y}"


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def date_line(day: date) -> str:
    """The line under the site's name in every page's header."""
    return f"from the chains' price and promotion files of {day:%A %-d %B %Y}"


def credit(day: date, collected_by: str) -> str:
    """The credit line in every page's footer."""
    return (f"{CREDIT_START} the files of {_day(day)}, collected by {collected_by} Israel time. Listed prices and listed "
            "promotions, not a promise of what a till charges. Not shopping advice.")


def no_odds_yet(column: str) -> str:
    """F10's fixed sentence, naming the column (the amendment's "Words")."""
    return (f"No odds yet for {BY_KEY[column].name}. Every day this site freezes a forecast for each item and scores it "
            "two weeks later; the odds appear here once they beat two rules of thumb over 90 days "
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


def across(column: str) -> str:
    """The design's "listed chain-wide", per column: a promotion carried by at least half the column's counted stores."""
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

def _deal_price(price: Fraction) -> str:
    return f"₪{to_agora(price)}"


def _against_median(gap: Gap) -> str:
    median = f"the 30-day median listed price of ₪{money(gap.median30)}"
    if gap.below <= 0:
        return f"not below {median}"
    amount = to_agora(gap.below)
    shown = f"₪{amount}" if amount > 0 else "less than ₪0.01"
    return f"{shown}, {gap.percent}%, below {median}"


def _at_or_below(deal: Fraction) -> str:
    """The days counted at or below the exact deal, in its figure for the eye (the module's docstring)."""
    shown = to_agora(deal)
    return f"below ₪{shown}" if shown > deal else f"at ₪{shown} or less"


def _change(change: Change) -> str:
    verb = "rose" if change.after > change.before else "fell"
    if change.since + timedelta(days=1) == change.day:
        return f"{verb} from ₪{money(change.before)} to ₪{money(change.after)} on {_day(change.day)}"
    return (f"{verb} from ₪{money(change.before)} ({_day(change.since)}) to ₪{money(change.after)} "
            f"({_day(change.day)})")


def _unchanged(recent: Window) -> str:
    if recent.days == RECENT_DAYS:
        return f"The listed price did not change in the past {RECENT_DAYS} days."
    if recent.short:
        return f"The listed price did not change on {_the_days(recent)}."
    return f"The listed price did not change on {_the_days(recent)} of the past {RECENT_DAYS}."


def gap_sentences(gap: Gap) -> tuple[str, str, str]:
    """P7's three sentences for a deal's gap (`shopper.measures.gap`; the module's docstring)."""
    first = (f"Deal price {_deal_price(gap.deal)}: {_against_median(gap)} "
             f"(of {_the_days(gap.window30)}).")
    second = (f"The lowest listed price was ₪{money(gap.low30)} over the past 30 days and ₪{money(gap.low90)} over the "
              f"past 90; listed {_at_or_below(gap.deal)} on {gap.at_or_below} of {_the_days(gap.window90)}.")
    if gap.changes:
        third = f"The listed price {', then '.join(_change(change) for change in gap.changes)}."
    else:
        third = _unchanged(gap.window30)
    return first, second, third


# P8

def _run(start: date, end: date, open_start: bool, open_end: bool) -> str:
    if not (open_start or open_end):
        return date_range(start, end)
    return f"from {_day(start)}{' or earlier' if open_start else ''} to {_day(end)}{' or later' if open_end else ''}"


def history_sentences(pair: Pair, column_days: Mapping[tuple[str, date], ColumnDay], day: date) -> tuple[str, ...]:
    """P8's sentences for the pair on `day` (the module's docstring), from `shopper.measures`' history of the 90-day
    window and its reading of `day` itself."""
    records = window(pair, column_days, day, READ_DAYS)
    today = promoted_today(pair, column_days, day)
    now = (f"On a promotion today, {MORNING}.",) if today else ()
    if not records.days:
        return now
    on, read = promotion_days(pair, column_days, day)
    unread = records.days - read
    found = runs(pair, column_days, day)
    note = f" (promotions could not be read on {unread})" if unread else ""
    if found or unread:
        count = f"a promotion on {on} of {_the_days(records)}{note}, {MORNING}."
        sentences = [*now, f"Before today: on {count}" if today else f"On {count}"]
    else:
        count = f"promotion listed in {_the_days(records)}."
        sentences = [*now, f"Before today: no {count}" if today else f"No {count}"]
    if not found:
        return tuple(sentences)
    seen = promotion_points(pair, column_days, day)
    last = found[-1]
    open_start = found[0].start == seen[0].day
    open_end = last.end == seen[-1].day and today is not False and not (today and last.end == day - timedelta(days=1))
    shown = [_run(run.start, run.end, open_start and index == 0, open_end and index == len(found) - 1)
             for index, run in enumerate(found)]
    sentences.append(f"{_plural(len(found), 'Run', 'Runs')}{' before today' if today else ''}: {'; '.join(shown)}.")
    if len(found) > 1:
        sentences.append(f"Days between runs: {'; '.join(str(between) for between in gaps(found))}.")
    if not today and not open_end:
        ago = days_since(found, day)
        sentences.append(f"The last run ended on {_day(last.end)}, {ago} {_plural(ago, 'day', 'days')} ago.")
    return tuple(sentences)

"""The site's words (`shopper.words`; the plan's Task 15): the design's "Words", "What a visitor sees", P6 to P8, P10,
F10 and the amendment's "Words"; the plan's questions J, K, M (f) and O; the first pre-flight's S10, the second's S7,
N4, N7 and N23; Task 9's review rulings on P8's count, a change's dates and the runs at the window's ends; and Task
15's review rulings (fix round 1) on the shown figures, the bounds beside a gap in the records, the column in P8 and
"before today".

The design's quoted sentences are read from docs/shopper-site.md (and the plan's answers from
docs/shopper-site-plan.md), so a change on either side shows. The pairs and column-days are built as
tests/test_measures.py builds them."""
import re
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from basket.check import PRONOUNS, flatten, strip_tags
from basket.words import CHAIN_NAMES, NEVER as BASKET_NEVER
from shopper.columns import COLUMNS
from shopper.history import Window
from shopper.measures import gap
from shopper.promotions import RESTRICTIONS
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, AT_SOME_STORES, CREDIT_START, FINE_PRINT, FROM_FIELDS, FROM_TEXT,
                           FRONT_RULE, FRONT_TITLE, GAP_HEADING, HIRING, HISTORY_HEADING, METHOD_TITLE, NEVER,
                           ODDS_WORDS, PRICE_NOT_READ, RECORD_TITLE, SITE_NAME, TARGET_PHRASES, across, as_listed,
                           club_label, columns_tested, count_line, credit, date_line, date_range, formats_note,
                           gap_sentences, history_sentences, last_across, no_odds_yet, price_history, starts_on,
                           targets, unreadable, window_note)
from shopper.words import (ACROSS_HEADING, BARCODE, BROWSE_LINK, CHANGES_SHOWN, NOT_LISTED, PER, buy, chart_key,
                           deal_price, listed_price, minimum_spend, percent_text, shown_below, stores_range)
from test_measures import DAY, DEAL, _days, _pair, back, listed_from

ROOT = Path(__file__).parent.parent
DESIGN = (ROOT / "docs" / "shopper-site.md").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "shopper-site-plan.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
FRIDAY = date(2026, 11, 6)
MORNING = "as listed in the morning's files"


def _line(text: str, start: str) -> str:
    [line] = [line for line in text.splitlines() if line.startswith(start)]
    return line


def _quoted(text: str) -> list[str]:
    return re.findall(r'"([^"]+)"', text)


def _found(pattern: str, text: str = DESIGN) -> str:
    match = re.search(pattern, text)
    assert match, pattern
    return match.group(1)


def _example():
    """Task 9's worked example (the first pre-flight's S10): page day 20 November 2026; 10.90 from 22 August to 27
    October, 11.90 from 28 October: 90 days with records."""
    listed = {date(2026, 8, 22) + timedelta(days=n): "10.90" for n in range(67)}
    listed |= {date(2026, 10, 28) + timedelta(days=n): "11.90" for n in range(23)}
    return listed


def _gap(deal, listed, holes=()):
    return gap(Fraction(deal), _pair(DEAL, listed), _days(DEAL, listed, holes=holes), DAY)


def _history(listed, promoted=(), unread=(), holes=(), today=None, page_day=DAY, extra_days=()):
    """P8's sentences for a Deal pair listing `listed` (day -> price). `today`: None leaves the page's day without a
    column-day (nothing read of it); True or False lists the product that day, on or off promotion; "unread" makes the
    day's promotions unread; "hole" makes it a hole."""
    listed = dict(listed)
    days = [*listed, *extra_days]
    promo_holes = list(unread)
    promoted = list(promoted)
    if today is not None:
        listed[page_day] = "10.00"
        days.append(page_day)
        if today is True:
            promoted.append(page_day)
        if today == "unread":
            promo_holes.append(page_day)
        if today == "hole":
            holes = [*holes, page_day]
    pair = _pair(DEAL, listed, promoted=promoted, unread=unread)
    return history_sentences(pair, _days(DEAL, days, holes=holes, promo_holes=promo_holes), page_day)


# The lists

def test_the_lists_are_the_designs_verbatim():
    always = _quoted(_line(DESIGN, "Always: "))
    assert ALWAYS == tuple(always[:4])                                  # the four beside prices and promotions
    assert (FROM_FIELDS, FROM_TEXT) == tuple(always[4:6])               # the sources of a condition
    assert f'"{FINE_PRINT}"' in DESIGN and FINE_PRINT.startswith(always[6] + ":")
    # S7: one fixed sentence holds the four, so every product page carries them, a product listed nowhere today too
    assert all(phrase in ALWAYS_SENTENCE for phrase in ALWAYS)
    # true of a product page's prices with the stores left out by rule (Deal's online store 413, Express's 779), which
    # the method page names (fix round 1, ruling 5); in the site's public words, no "column"
    assert "apart from the stores left out by rule" in ALWAYS_SENTENCE and METHOD_TITLE in ALWAYS_SENTENCE
    # deploy prep: the method page gives the rules (by the store list, and by a file's name, store 779's case) but names
    # only the stores the store list leaves out and store 779, never a later store left out by its files' names
    assert f"({METHOD_TITLE} gives the rules)" in ALWAYS_SENTENCE and "names them" not in ALWAYS_SENTENCE
    assert "column" not in ALWAYS_SENTENCE
    never = _quoted(_line(DESIGN, "Never: "))
    basket_part = never[:never.index("the chain charges") + 1]
    assert set(basket_part) <= set(BASKET_NEVER)                        # the basket's list, whole, first
    assert NEVER == BASKET_NEVER + tuple(never[len(basket_part):])      # then the design's own, in its order (N23)
    assert ODDS_WORDS == tuple(_quoted(_found(r"no other odds word (\([^)]*\))")))
    assert (FRONT_TITLE, GAP_HEADING, HISTORY_HEADING) == tuple(_quoted(_line(DESIGN, "The public names (Q4)"))[:3])
    assert f'**"{METHOD_TITLE}"** (`method.html`)' in DESIGN and f'**"{RECORD_TITLE}"** (`record.html`)' in DESIGN
    assert f'"{PRICE_NOT_READ}"' in DESIGN and f'"{AT_SOME_STORES}"' in DESIGN
    # question K: the phrases by code, in the order the field reads its codes (club, card, other: N2)
    k = _line(PLAN, "- (Owner, 2026-11-07: as recommended.) **K.")
    assert tuple(TARGET_PHRASES) == tuple(RESTRICTIONS.values())
    assert tuple(TARGET_PHRASES.values()) == tuple(_quoted(k)[:3])
    # question J, still true of nine columns: they are the formats of five chains
    assert f'Recommended working title: "{SITE_NAME}"' in PLAN and len(CHAIN_NAMES) == 5
    # question M (f): the hiring line, its LinkedIn link the README's
    assert HIRING == (("Built by Doron Reiffman", "https://www.linkedin.com/in/doronreiffman"),
                      ("How this is made", "method.html"), ("Track record", "record.html"),
                      ("Code on GitHub", "https://github.com/doronreiffman/il-grocery-prices"))
    assert f"({HIRING[0][1]})" in README and HIRING[3][1] in PLAN


def test_credit_date_line_and_f10_are_the_designs():
    assert credit(FRIDAY, "12:03") == _found(r'the credit line in the footer \("([^"]+)"\)')
    assert credit(FRIDAY, "12:03").startswith(CREDIT_START)            # N7: the start the site check looks for
    assert "section 30 of the Food and Pharma Competition Promotion Law, 2014" in CREDIT_START
    assert credit(date(2026, 12, 25), "11:48").endswith(
        "the files of 25 December 2026, collected by 11:48 Israel time. Listed prices and listed promotions, not a "
        "promise of what a till charges. Not shopping advice.")
    assert date_line(FRIDAY) == _found(r'the date line: "([^"]+)"')
    assert date_line(date(2026, 11, 9)) == "from the chains' price and promotion files of Monday 9 November 2026"
    # F10, naming the column (the amendment's "Words": "No odds yet for Shufersal Deal.")
    f10 = _found(r'one fixed sentence: "(No odds yet for Shufersal\. [^"]+)"')
    assert '("No odds yet for Shufersal Deal.")' in DESIGN
    assert no_odds_yet("shufersal-deal") == f10.replace("for Shufersal.", "for Shufersal Deal.")
    for column in COLUMNS:
        assert no_odds_yet(column.key) == f10.replace("for Shufersal.", f"for {column.name}.")
    assert "two weeks later" in f10
    # P10's sentence, per chain (on each of its columns: question M (g))
    p10 = _found(r'\("(Promotions from Carrefour\'s files could not be read today)"\)')
    assert unreadable("carrefour") == p10 + "."
    assert unreadable("ramilevy") == "Promotions from Rami Levy's files could not be read today."


def test_the_front_rule_and_count_line_name_the_store_format():
    """Question O: a deal is tested against its own column's listed prices, so the words say "in the same store
    format" and "in their store format"; another format of the same chain may list the item lower. Deploy prep: "every
    listed price", the site's term for a column's median, since the test compares the deal with the daily medians, never
    a single store's price (`shopper.measures.on_front`)."""
    rule = _found(r'with the rule under it \("([^"]+)"')
    assert FRONT_RULE == rule == ("promotion prices lower than every listed price of the item in the same store format "
                                  "over the past 90 days with records")
    assert f'"{FRONT_RULE}"' in PLAN
    # the count line, as the design now quotes it (the final review's finding 4: "across a store format"; deploy prep:
    # the front test's own days, so K is every product the line describes)
    assert count_line(1840, 6210, 410) == _found(r'a count line \("([^"]+)"') + "."
    assert count_line(1840, 6210, 410).endswith(
        "410 of them are below every listed price of the past 90 days in their store format, on items with at least 20 "
        "days of records there in the past 30.")


def test_the_count_line_says_its_promotions_are_listed_across_a_store_format():
    """The final review's finding 4: the count is of the promotions listed across a column today (`shopper.build`'s
    count line), not every promotion in the chains' files, most of which run at some stores only; so the line says
    what it counts, as every other sentence of the site does."""
    for promotions in (1, 1840):
        line = count_line(promotions, 6210, 410)
        noun = "promotion" if promotions == 1 else "promotions"
        assert f"list {promotions:,} {noun} across a store format on 6,210 products;" in line


def test_count_line_with_thousands_separators():
    assert count_line(1_234_567, 21_973, 1_000) == (
        "Today the five chains list 1,234,567 promotions across a store format on 21,973 products; 1,000 of them are "
        "below every listed price of the past 90 days in their store format, on items with at least 20 days of "
        "records there in the past 30.")
    assert count_line(1, 1, 1) == ("Today the five chains list 1 promotion across a store format on 1 product; 1 of "
                                   "them is below every listed price of the past 90 days in their store format, on an "
                                   "item with at least 20 days of records there in the past 30.")
    assert count_line(2, 2, 0).endswith(" 0 of them are below every listed price of the past 90 days in their store "
                                        "format, on items with at least 20 days of records there in the past 30.")
    assert count_line(0, 0, 0).startswith(
        "Today the five chains list 0 promotions across a store format on 0 products; 0 of them are ")


def test_club_label_names_the_chains_marking_none():
    k = _line(PLAN, "- (Owner, 2026-11-07: as recommended.) **K.")
    assert f'("{club_label(["shufersal"])}"' in k
    assert club_label([]) == "from the chains' fields"
    assert club_label(["yochananof", "shufersal"]) == ("from the chains' fields; Shufersal's and Yochananof's files "
                                                      "mark none")
    assert club_label(["osherad", "ramilevy", "carrefour"]) == ("from the chains' fields; Rami Levy's, Osher Ad's and "
                                                                "Carrefour's files mark none")


def test_targets_join_every_code_present():
    """S3: K's phrase for each code present, joined, in the order club, card, other (N2), each code once."""
    assert '("club members only, and some customers only")' in DESIGN
    assert targets(["club"]) == "club members only"
    assert targets(["chain_card"]) == "the chain's card holders only"
    assert targets(["other"]) == "some customers only"
    assert targets(["club", "other"]) == "club members only, and some customers only"
    assert targets(["other", "club"]) == "club members only, and some customers only"
    assert targets(["chain_card", "other"]) == "the chain's card holders only, and some customers only"
    assert targets(["other", "chain_card", "club"]) == ("club members only, the chain's card holders only, and some "
                                                         "customers only")
    assert targets(["other", "other"]) == "some customers only"
    assert targets([]) == ""


def test_column_words():
    assert as_listed(["ramilevy"]) == "(as Rami Levy lists it)"
    assert as_listed(["shufersal-sheli", "shufersal-deal"]) == "(as Shufersal Deal and Shufersal Sheli list it)"
    assert as_listed(["shufersal-sheli", "shufersal-express", "shufersal-deal", "shufersal-deal"]) == (
        "(as Shufersal Deal, Shufersal Express and Shufersal Sheli list it)")
    with pytest.raises(ValueError):
        as_listed([])
    assert across("shufersal-deal") == "listed across Shufersal Deal"   # the design's "listed chain-wide", by column
    assert across("ramilevy") == "listed across Rami Levy"
    # deploy prep: "seen", since the registry knows record days only, and a hole day after it could have been across
    assert last_across("carrefour-city", date(2026, 11, 3)) == (
        "last seen listed across Carrefour City on 3 November 2026")
    assert last_across("yochananof", date(2027, 1, 1)) == "last seen listed across Yochananof on 1 January 2027"


def test_the_short_sentences():
    assert window_note(Window(23, date(2026, 11, 1), (), True)) == "23 days of records since 1 November 2026"
    assert window_note(Window(1, date(2026, 11, 19), (), True)) == "1 day of records since 19 November 2026"
    assert window_note(Window(0, None, (), True)) == "no days of records"
    assert starts_on(date(2026, 11, 9)) == "Listed to start on 9 November 2026."
    # deploy prep: B5's median is over the stores whose file lists the item, not over all the included stores
    assert formats_note() == ("The product pages show Shufersal's and Carrefour's store formats apart; the basket "
                              "takes each chain's median over its included stores whose file lists the item.")
    # deploy prep: no closing rule is built (F9 states none), so the sentence names none
    assert columns_tested(9) == ("Nine columns are tested at once: the more are tested, the likelier one passes the "
                                 "gate by luck.")
    assert columns_tested(2).startswith("Two columns are tested at once: ")
    assert columns_tested(1).startswith("One column is tested at once: ")
    assert columns_tested(13).startswith("13 columns are tested at once: ")
    assert date_range(date(2026, 11, 3), date(2026, 11, 9)) == "3 to 9 November 2026"
    assert date_range(date(2026, 10, 31), date(2026, 11, 2)) == "31 October to 2 November 2026"
    assert date_range(date(2026, 12, 28), date(2027, 1, 3)) == "28 December 2026 to 3 January 2027"
    assert date_range(date(2026, 11, 5), date(2026, 11, 5)) == "5 November 2026"


# P7

BEFORE = "before today"
ACROSS = "a promotion listed across Shufersal Deal"


def test_p7_sentences_for_the_designs_example():
    """The design's example on Task 9's history: so "of the 90 days with records" (the first pre-flight's S10), each
    window's count said to be of the days before today (fix round 1, ruling 4)."""
    assert "₪4.00, 34%, below the 30-day median listed price of ₪11.90" in DESIGN
    assert gap_sentences(_gap("7.90", _example())) == (
        "Deal price ₪7.90: ₪4.00, 34%, below the 30-day median listed price of ₪11.90 (of the 30 days with records "
        "before today).",
        "The lowest listed price was ₪10.90 in the 30 days before today and ₪10.90 in the 90 days before today; "
        "listed at ₪7.90 or less on 0 of the 90 days with records.",
        "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026.")
    # a deal not below the median, or equal to it
    above = gap_sentences(_gap("12.50", _example()))
    assert above[0] == ("Deal price ₪12.50: not below the 30-day median listed price of ₪11.90 (of the 30 days with "
                        "records before today).")
    assert above[1].endswith("listed at ₪12.50 or less on 90 of the 90 days with records.")
    assert gap_sentences(_gap("11.90", _example()))[0].startswith("Deal price ₪11.90: not below the 30-day median ")
    # the lows of each window, and a median of three places written to the agora, half up (₪1.445 is ₪1.45)
    raised = {**listed_from(61, 90, "7.00"), **listed_from(1, 60, "11.90")}
    assert gap_sentences(_gap("7.90", raised))[1] == (
        "The lowest listed price was ₪11.90 in the 30 days before today and ₪7.00 in the 90 days before today; "
        "listed at ₪7.90 or less on 30 of the 90 days with records.")
    assert gap_sentences(_gap("1.00", {back(2): "1.44", back(1): "1.45"}))[0].startswith(
        "Deal price ₪1.00: ₪0.45, 31%, below the 30-day median listed price of ₪1.45 ")


def test_p7_and_p8_with_a_short_window():
    """P6: a window of fewer than 20 of 30 or 60 of 90 days of records says so, and P8 counts the same days P7 does."""
    listed = listed_from(1, 5, "10.00")                                   # 15 to 19 November
    assert gap_sentences(_gap("7.90", listed)) == (
        "Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the 5 days of records since "
        "15 November 2026 before today).",
        "The lowest listed price was ₪10.00 on the 5 days of records since 15 November 2026 before today; listed at "
        "₪7.90 or less on 0 of the 5 days of records.",
        "The listed price did not change on the 5 days of records since 15 November 2026 before today.")
    assert _history(listed, promoted=[back(2), back(1)], today=False) == (
        f"On {ACROSS} on 2 of the 5 days of records since 15 November 2026 before today, {MORNING}.",
        "Run seen before today: 18 to 19 November 2026.",
        "The last run ended on 19 November 2026, 1 day ago.")
    one = gap_sentences(_gap("7.90", {back(1): "10.00"}))
    assert one[0].endswith("(of the 1 day of records since 19 November 2026 before today).")
    # 25 of 30 days with records is no short 30-day window, but every day of the 30 is not known
    holed = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00"), holes=[back(n) for n in range(1, 6)]))
    assert holed[0].endswith("(of the 25 days with records before today).")
    assert holed[2] == "The listed price did not change on the 25 days with records of the 30 before today."
    full = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00")))
    assert full[2] == "The listed price did not change in the 30 days before today."


def test_the_lows_say_the_days_of_records_each_is_over():
    """Deploy prep (the owner, 2026-11-10): each low is said over the days of records its window holds (P6), in the
    change sentence's own window words, so the sentence stays true with 15 days of records at launch; one phrase when
    both windows hold the same days; and the days at or below are "of the N days with records" of the 90's (P6)."""
    launch = gap_sentences(_gap("7.90", listed_from(1, 15, "10.00")))       # 5 to 19 November: 15 days of records
    assert launch[1] == ("The lowest listed price was ₪10.00 on the 15 days of records since 5 November 2026 before "
                         "today; listed at ₪7.90 or less on 0 of the 15 days of records.")
    one = gap_sentences(_gap("7.90", {back(1): "10.00"}))
    assert one[1] == ("The lowest listed price was ₪10.00 on the 1 day of records since 19 November 2026 before today; "
                      "listed at ₪7.90 or less on 0 of the 1 day of records.")
    # gaps in both windows: 25 of the 30 days and 85 of the 90 hold records
    gapped = {**listed_from(31, 90, "7.50"), **listed_from(1, 30, "10.00")}
    holes = [back(n) for n in range(1, 6)]
    assert gap_sentences(_gap("7.90", gapped, holes=holes))[1] == (
        "The lowest listed price was ₪10.00 on the 25 days with records of the 30 before today and ₪7.50 on the 85 "
        "days with records of the 90 before today; listed at ₪7.90 or less on 60 of the 85 days with records.")
    # a full 30-day window and a short 90-day one, 45 days of records since 6 October
    short = {**listed_from(31, 45, "9.00"), **listed_from(1, 30, "10.00")}
    assert gap_sentences(_gap("7.90", short))[1] == (
        "The lowest listed price was ₪10.00 in the 30 days before today and ₪9.00 on the 45 days of records since 6 "
        "October 2026 before today; listed at ₪7.90 or less on 0 of the 45 days of records.")
    # a short 30-day window beside older records: 10 of the 30, 70 of the 90
    older = {**listed_from(31, 90, "9.50"), **listed_from(1, 10, "10.00")}
    assert gap_sentences(_gap("7.90", older))[1] == (
        "The lowest listed price was ₪10.00 on the 10 days of records since 10 November 2026 before today and ₪9.50 "
        "on the 70 days with records of the 90 before today; listed at ₪7.90 or less on 0 of the 70 days with records.")


def test_p7_changes_in_order_and_across_a_hole():
    """Task 9's review: a change is dated on its day only when the two record days are consecutive; across a hole both
    record days are given, never one date the files cannot pin."""
    listed = {**listed_from(46, 90, "10.00"), **listed_from(32, 45, "10.50"), back(31): "11.00",
              **listed_from(16, 30, "12.00"), **listed_from(1, 15, "9.50")}
    assert gap_sentences(_gap("7.90", listed))[2] == (
        "The listed price rose from ₪11.00 to ₪12.00 on 21 October 2026, then fell from ₪12.00 to ₪9.50 on 5 November "
        "2026.")
    across_hole = {back(5): "10.90", back(4): "99.00", back(3): "11.90", back(2): "11.90"}
    assert gap_sentences(_gap("7.90", across_hole, holes=[back(4)]))[2] == (
        "The listed price rose from ₪10.90 (15 November 2026) to ₪11.90 (17 November 2026).")
    fell = {back(3): "11.90", back(1): "10.90"}                             # day 2 not listed: no record of a price
    assert gap_sentences(_gap("7.90", fell))[2] == (
        "The listed price fell from ₪11.90 (17 November 2026) to ₪10.90 (19 November 2026).")


def test_a_change_the_shown_figures_do_not_show_is_not_stated():
    """Fix round 1, ruling 2 (the review's Important 3): a median of ₪1.445 is shown ₪1.45, so its move to ₪1.45 is
    no change in the figures shown, and "rose from ₪1.45 to ₪1.45" is never said."""
    assert gap_sentences(_gap("1.00", {back(3): "1.445", back(2): "1.45", back(1): "1.45"}))[2] == (
        "The listed price did not change on the 3 days of records since 17 November 2026 before today.")
    assert gap_sentences(_gap("1.00", {back(3): "1.44", back(2): "1.445", back(1): "1.45"}))[2] == (
        "The listed price rose from ₪1.44 to ₪1.45 on 18 November 2026.")


def test_p7_figures_are_the_shown_figures():
    """Fix round 1, ruling 2 (the review's Important 3 and Minor 1): the gap and its percent are worked from the shown
    median and the shown deal price, and the days at or below are counted on the shown figures, so the page agrees with
    itself; the exact price still ranks and decides the front page (shopper.measures), never stated."""
    # 3 for ₪10.01 is 3.3366... a unit, shown ₪3.34; a median of ₪3.335 is shown ₪3.34 too
    probe = gap_sentences(_gap(Fraction("10.01") / 3, listed_from(1, 30, "3.335")))
    assert probe[0].startswith("Deal price ₪3.34: not below the 30-day median listed price of ₪3.34 ")
    assert probe[1] == ("The lowest listed price was ₪3.34 on the 30 days of records since 21 October 2026 before "
                        "today; listed at ₪3.34 or less on 30 of the 30 days of records.")
    # a deal of ₪1.445, shown ₪1.45, against ₪1.50: ₪0.05 and 3%, not the exact gap's ₪0.06 and 4%
    assert gap_sentences(_gap("1.445", listed_from(1, 30, "1.50")))[0] == (
        "Deal price ₪1.45: ₪0.05, 3%, below the 30-day median listed price of ₪1.50 (of the 30 days with records "
        "before today).")
    # 3 for ₪4.34 (1.4466...) against a listed ₪1.45: equal as shown, so not below it, and listed at it on every day
    up = gap_sentences(_gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")))
    assert up[0].startswith("Deal price ₪1.45: not below the 30-day median listed price of ₪1.45 ")
    assert up[1].endswith("listed at ₪1.45 or less on 30 of the 30 days of records.")
    # 3 for ₪10 (3.3333...), shown ₪3.33, against a median of ₪3.335 shown ₪3.34: ₪0.01 below, and no day at or below
    down = gap_sentences(_gap(Fraction(10, 3), listed_from(1, 30, "3.335")))
    assert down[0].startswith("Deal price ₪3.33: ₪0.01, under 1%, below the 30-day median listed price of ₪3.34 ")
    assert down[1].endswith("listed at ₪3.33 or less on 0 of the 30 days of records.")



def test_a_gap_that_rounds_to_zero_percent_is_under_one_percent():
    """Deploy prep (the owner, 2026-11-10): a gap above ₪0 whose whole percent rounds to 0 says "under 1%", never
    "₪0.10, 0%, below"; from half a percent it is a whole percent as before. `shown_below` keeps the number."""
    assert percent_text(0) == "under 1%" and percent_text(1) == "1%" and percent_text(34) == "34%"
    tiny = _gap("99.51", listed_from(1, 30, "100.00"))                      # ₪0.49, 0.49%
    assert shown_below(tiny) == (Decimal("0.49"), 0)
    assert gap_sentences(tiny)[0] == ("Deal price ₪99.51: ₪0.49, under 1%, below the 30-day median listed price of "
                                      "₪100.00 (of the 30 days with records before today).")
    half = _gap("99.50", listed_from(1, 30, "100.00"))                      # ₪0.50, 0.5%: 1%, half up
    assert shown_below(half) == (Decimal("0.50"), 1)
    assert gap_sentences(half)[0].startswith("Deal price ₪99.50: ₪0.50, 1%, below ")
    assert gap_sentences(_gap("100.00", listed_from(1, 30, "100.00")))[0].startswith(
        "Deal price ₪100.00: not below the 30-day median")


def _price_history(listed, holes=()):
    """The product page's listed-price history for a Deal pair listing `listed` (day -> price), on the page's day."""
    return price_history(_pair(DEAL, listed), _days(DEAL, listed, holes=holes), DAY)


def test_the_listed_price_history_over_the_90_days():
    """The product page's history as text (Task 16; the controller's ruling 1): P7's change sentence over the 90-day
    window, on Task 15's rules: the shown figures, a date only between consecutive days with records, before today."""
    assert _price_history(_example()) == "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026."
    listed = {**listed_from(46, 90, "10.00"), **listed_from(32, 45, "10.50"), back(31): "11.00",
              **listed_from(16, 30, "12.00"), **listed_from(1, 15, "9.50")}
    assert _price_history(listed) == (
        "The listed price rose from ₪10.00 to ₪10.50 on 6 October 2026, then rose from ₪10.50 to ₪11.00 on 20 "
        "October 2026, then rose from ₪11.00 to ₪12.00 on 21 October 2026, then fell from ₪12.00 to ₪9.50 on 5 "
        "November 2026.")
    # P7 says the 30 days' changes only, the history the 90's
    assert gap_sentences(_gap("7.90", listed))[2] == (
        "The listed price rose from ₪11.00 to ₪12.00 on 21 October 2026, then fell from ₪12.00 to ₪9.50 on 5 November "
        "2026.")
    # across a gap in the records, both days
    across_hole = {back(5): "10.90", back(4): "99.00", back(3): "11.90", back(2): "11.90"}
    assert _price_history(across_hole, holes=[back(4)]) == (
        "The listed price rose from ₪10.90 (15 November 2026) to ₪11.90 (17 November 2026).")
    # a change the shown figures do not show is none
    assert _price_history({back(3): "1.445", back(2): "1.45", back(1): "1.45"}) == (
        "The listed price did not change on the 3 days of records since 17 November 2026 before today.")


def test_the_listed_price_history_unchanged_says_its_days():
    """With no change, the days the files say it of: all 90, those with records of the 90, or a short window's."""
    assert _price_history(listed_from(1, 90, "10.00")) == "The listed price did not change in the 90 days before today."
    assert _price_history(listed_from(1, 90, "10.00"), holes=[back(n) for n in range(1, 6)]) == (
        "The listed price did not change on the 85 days with records of the 90 before today.")
    assert _price_history(listed_from(1, 59, "10.00")) == (
        "The listed price did not change on the 59 days of records since 22 September 2026 before today.")
    assert _price_history(listed_from(1, 5, "10.00")) == (
        "The listed price did not change on the 5 days of records since 15 November 2026 before today.")
    # today's own price is no day of the window; with no day of records in the 90, nothing is said
    assert _price_history({**listed_from(1, 5, "10.00"), DAY: "11.00"}) == _price_history(listed_from(1, 5, "10.00"))
    assert _price_history({DAY: "11.00"}) is None
    assert _price_history(listed_from(1, 5, "10.00"), holes=[back(n) for n in range(1, 6)]) is None



def _changing(count: int, start: int = 1) -> dict:
    """A listed price that changes `count` times over the days before today, a change every other day, newest first
    seen `start` days back: ₪10.00, then ₪11.00, ₪10.00, … ."""
    return {back(start + n): ("10.00" if (count - n // 2) % 2 == 0 else "11.00") for n in range(2 * count + 1)}


def test_a_change_list_holds_the_newest_five():
    """Task 16, round 2 (the 60 KB cap): both change lists, P7's 30 days and the history's 90, show at most
    CHANGES_SHOWN (5) changes, the newest, in day order; past five, a tail says how many were seen, in the very
    window phrase the sentence uses when nothing changed."""
    assert CHANGES_SHOWN == 5
    five = _changing(5)
    assert len(gap_sentences(_gap("7.90", five))[2].split(", then ")) == 5
    assert "(the last" not in gap_sentences(_gap("7.90", five))[2] and "(the last" not in _price_history(five)
    six = _changing(6)
    days = sorted(six)
    assert gap_sentences(_gap("7.90", six))[2] == (
        f"The listed price fell from ₪11.00 to ₪10.00 on {days[3]:%-d %B %Y}, then rose from ₪10.00 to ₪11.00 on "
        f"{days[5]:%-d %B %Y}, then fell from ₪11.00 to ₪10.00 on {days[7]:%-d %B %Y}, then rose from ₪10.00 to "
        f"₪11.00 on {days[9]:%-d %B %Y}, then fell from ₪11.00 to ₪10.00 on {days[11]:%-d %B %Y} (the last 5 of 6 "
        "changes seen on the 13 days of records since 7 November 2026 before today).")
    assert days[3] - days[1] == timedelta(days=2) and "rose from ₪10.00 to ₪11.00 on" not in gap_sentences(
        _gap("7.90", six))[2].split(", then ")[0]                       # the oldest change is the one left out
    # the window phrase is the unchanged sentence's own: every day with a record, or those with records of the 90
    daily = {back(n): ("10.00" if n % 2 else "11.00") for n in range(1, 91)}
    assert _price_history(daily).endswith(" (the last 5 of 89 changes seen in the 90 days before today).")
    assert _price_history(daily, holes=[back(2)]).endswith(
        " (the last 5 of 87 changes seen on the 89 days with records of the 90 before today).")
    assert gap_sentences(_gap("7.90", daily))[2].endswith(
        " (the last 5 of 30 changes seen in the 30 days before today).")   # one on the window's first day


def test_a_change_across_a_gap_keeps_its_bounds_in_the_capped_list():
    """Inside the newest five, a change across a hole still gives both record days, never one date."""
    listed = _changing(6)
    days = sorted(listed)
    hole = days[-2]                                                       # between the last two changes' days
    listed[hole] = "99.00"
    said = _price_history(listed, holes=[hole])
    shown = said.split(", then ")
    assert len(shown) == 5 and "(the last 5 of 6 changes seen" in said
    assert shown[-1].startswith(f"fell from ₪11.00 ({days[-3]:%-d %B %Y}) to ₪10.00 ({days[-1]:%-d %B %Y})")


def test_the_product_pages_labels():
    """Task 16's labels (the controller's rulings): the design's and the brief's phrases put together. Today's listed
    price carries the three ALWAYS phrases a listed price takes; a deal's price is a unit's or a kilogram's (P4), to the
    agora half up; the stores' range is labelled as the stores'; P9's heading and the chart's key."""
    assert listed_price(Decimal("11.895")) == (
        "Listed price ₪11.90, before promotions, as listed in the chain's price files")
    assert all(phrase in listed_price(Decimal(1)).lower() for phrase in ALWAYS[:3])
    assert PER == {"unit": "per unit", "kg": "per kilogram"}
    assert deal_price(Fraction(10, 3), "unit") == "Deal price ₪3.33 per unit"
    assert deal_price(Fraction("4.34") / 3, "kg") == "Deal price ₪1.45 per kilogram"
    assert buy(Decimal("3.000")) == "buy 3" and buy(Decimal("1.500")) == "buy 1.5"
    # deploy prep: never the listed price's own "stores ₪X to ₪Y" beside it in the same section
    assert stores_range(Decimal("4.355"), Decimal("4.6")) == "stores' deal prices ₪4.36 to ₪4.60"
    assert minimum_spend(Decimal("150")) == "minimum spend ₪150.00"
    assert (NOT_LISTED, ACROSS_HEADING, BROWSE_LINK, BARCODE) == (
        "not listed today", "Today at each column, in name order", "Browse by first letter", "Barcode")
    assert chart_key("shufersal-deal") == ("listed price", "a promotion listed across Shufersal Deal")
    assert chart_key("ramilevy")[1] == f"a promotion {across('ramilevy')}"


# P8

def test_p8_sentences_in_the_designs_forms():
    """Page day 6 December 2026; 87 days with records (three days of the 90 the product is not listed); on promotion
    from 3 to 9 and from 24 to 30 November, 12 days listed of them; off promotion today. P8 names the column, as the
    amendment's "Words" do (fix round 1, ruling 3)."""
    page_day = date(2026, 12, 6)
    window = [page_day - timedelta(days=n) for n in range(90, 0, -1)]
    not_listed = {date(2026, 10, 15), date(2026, 11, 5), date(2026, 11, 26)}
    listed = {day: "10.00" for day in window if day not in not_listed}
    promoted = [day for day in listed if date(2026, 11, 3) <= day <= date(2026, 11, 9)
                or date(2026, 11, 24) <= day <= date(2026, 11, 30)]
    assert _history(listed, promoted, today=False, page_day=page_day, extra_days=not_listed) == (
        f"On {ACROSS} on 12 of the 87 days with records before today, {MORNING}.",
        "Runs seen before today: 3 to 9 November 2026; 24 to 30 November 2026.",
        "Days between runs: 14.",
        "The last run ended on 30 November 2026, 6 days ago.")


def test_p8_never_denies_a_promotion_at_some_stores():
    """The review's Important 4: a promotion carried by fewer than half the column's stores is no run, so P8 says no
    promotion was listed across the column, never that none was listed."""
    assert _history(listed_from(1, 90, "10.00"), today=False) == (
        "No promotion listed across Shufersal Deal in the 90 days with records before today.",)
    sheli = history_sentences(_pair("shufersal-sheli", listed_from(1, 90, "10.00")),
                              _days("shufersal-sheli", listed_from(1, 90, "10.00")), DAY)
    assert sheli == ("No promotion listed across Shufersal Sheli in the 90 days with records before today.",)


def test_p8_runs_and_the_days_between_them():
    listed = listed_from(1, 90, "10.00")
    promoted = [back(n) for n in (30, 29, 28, 20, 19, 18, 5, 4)]
    assert _history(listed, promoted, today=False) == (
        f"On {ACROSS} on 8 of the 90 days with records before today, {MORNING}.",
        "Runs before today: 21 to 23 October 2026; 31 October to 2 November 2026; 15 to 16 November 2026.",
        "Days between runs: 7; 12.",
        "The last run ended on 16 November 2026, 4 days ago.")


def test_p8_counts_the_days_with_records_p7_counts():
    """Task 9's review, ruling 1: one N for "days with records" in a section; the days whose promotions could not be
    read are said, not dropped from N."""
    listed = listed_from(1, 6, "10.00")                                   # 14 to 19 November
    promoted = [back(n) for n in range(1, 6)]
    found = _history(listed, promoted, unread=[back(3)], today=False)
    assert found == (
        f"On {ACROSS} on 4 of the 6 days of records since 14 November 2026 before today (promotions could not be read "
        f"on 1), {MORNING}.",
        "Run seen before today: 15 to 19 November 2026.",
        "The last run ended on 19 November 2026, 1 day ago.")
    same = "of the 6 days of records since 14 November 2026 before today"
    assert same in gap_sentences(_gap("7.90", listed))[0] and same in found[0]
    # none on promotion, some days not read: the count, not "no promotion listed"
    assert _history(listed_from(1, 5, "10.00"), unread=[back(2), back(1)]) == (
        f"On {ACROSS} on 0 of the 5 days of records since 15 November 2026 before today (promotions could not be read "
        f"on 2), {MORNING}.",)


def test_p8_on_promotion_today():
    """Ruling 3 (a): the window ends yesterday, so a run reaching it is not over when today's files list the product
    on promotion: today is said, and the history is worded as before today."""
    listed = listed_from(1, 90, "10.00")
    assert _history(listed, [back(n) for n in range(1, 11)], today=True) == (
        f"On {ACROSS} today, {MORNING}.",
        f"On {ACROSS} on 10 of the 90 days with records before today, {MORNING}.",
        "Run before today: 10 to 19 November 2026.")
    assert _history(listed, today=True) == (
        f"On {ACROSS} today, {MORNING}.",
        "No promotion listed across Shufersal Deal in the 90 days with records before today.")
    # the run seen to 17 November, the two days after it holes: before today it may have gone on
    found = _history(listed, [back(n) for n in range(3, 11)], holes=[back(2), back(1)], today=True)
    assert found[1:] == (f"On {ACROSS} on 8 of the 88 days with records before today, {MORNING}.",
                         "Run seen before today: from 10 November 2026 to 17 November 2026 or later.")
    # a run that ended before the days off promotion that led to today's: still no end said beside today's promotion
    assert _history(listed, [back(n) for n in range(5, 11)], today=True) == (
        f"On {ACROSS} today, {MORNING}.",
        f"On {ACROSS} on 6 of the 90 days with records before today, {MORNING}.",
        "Run before today: 10 to 15 November 2026.")
    assert _history({}, today=True) == (f"On {ACROSS} today, {MORNING}.",)
    assert _history({}) == ()


def test_p8_runs_at_the_windows_ends():
    """Ruling 3 (b): a run seen from the window's first day read may have started earlier; and its mirror, a run seen
    to the last day read when today's state is not known, may go on, and then no end is said."""
    listed = listed_from(1, 90, "10.00")
    first = [back(n) for n in range(85, 91)]                              # 22 to 27 August, the window's first days
    assert _history(listed, first, today=False) == (
        f"On {ACROSS} on 6 of the 90 days with records before today, {MORNING}.",
        "Run before today: from 22 August 2026 or earlier to 27 August 2026.",
        "The last run ended on 27 August 2026, 85 days ago.")
    # the window's first day a hole: the run seen from the first day read
    assert _history(listed, first, holes=[back(90)], today=False)[1] == (
        "Run seen before today: from 23 August 2026 or earlier to 27 August 2026.")
    last = [back(n) for n in range(1, 6)]                                 # 15 to 19 November
    for today in (None, "unread", "hole"):
        assert _history(listed, last, today=today) == (
            f"On {ACROSS} on 5 of the 90 days with records before today, {MORNING}.",
            "Run before today: from 15 November 2026 to 19 November 2026 or later.")
    assert _history(listed, last, today=False)[1:] == ("Run before today: 15 to 19 November 2026.",
                                                       "The last run ended on 19 November 2026, 1 day ago.")
    # an open run beside a pinned one: only the end the files cannot pin is said open
    assert _history(listed, [*first, back(5), back(4)], today=False)[1:3] == (
        "Runs before today: from 22 August 2026 or earlier to 27 August 2026; 15 to 16 November 2026.",
        "Days between runs: 79.")
    assert _history(listed, [*first, back(2), back(1)])[1:] == (
        "Runs before today: from 22 August 2026 or earlier to 27 August 2026; from 18 November 2026 to 19 November "
        "2026 or later.",
        "Days between runs: 82.")
    whole = [back(n) for n in range(1, 91)]
    assert _history(listed, whole)[1] == (
        "Run before today: from 22 August 2026 or earlier to 19 November 2026 or later.")


def test_an_end_beside_a_gap_in_the_records_is_a_bound():
    """Fix round 1, ruling 1 (the review's Important 1): off promotion today, but the two days before it holes, so the
    run seen to 17 November may have run to 19 November: its end is "or later", its days ago "at most"."""
    listed = listed_from(1, 90, "10.00")
    promoted = [back(n) for n in range(3, 11)]
    assert _history(listed, promoted, holes=[back(2), back(1)], today=False) == (
        f"On {ACROSS} on 8 of the 88 days with records before today, {MORNING}.",
        "Run seen before today: from 10 November 2026 to 17 November 2026 or later.",
        "The last run seen ended on 17 November 2026 or later, at most 3 days ago.")
    # an unread day beside the end is a bound too, and a day read after it says the run did end
    assert _history(listed, promoted, unread=[back(2)])[1:] == (
        "Run seen before today: from 10 November 2026 to 17 November 2026 or later.",
        "The last run seen ended on 17 November 2026 or later, at most 3 days ago.")
    # a day the product is not listed is no reading of it either
    unlisted = {day: price for day, price in listed.items() if day != back(2)}
    assert _history(unlisted, promoted, today=False, extra_days=[back(2)])[2] == (
        "The last run seen ended on 17 November 2026 or later, at most 3 days ago.")


def test_run_edges_and_the_days_between_runs_beside_a_gap_are_bounds():
    """Fix round 1, ruling 1 (the review's Important 2): mid-window, a hole after one run's end and an unread day before
    the next one's start leave both edges and the days between them unpinned."""
    listed = listed_from(1, 90, "10.00")
    promoted = [back(n) for n in (30, 29, 28, 20, 19, 18)]
    assert _history(listed, promoted, unread=[back(21)], holes=[back(27)], today=False) == (
        f"On {ACROSS} on 6 of the 89 days with records before today (promotions could not be read on 1), {MORNING}.",
        "Runs seen before today: from 21 October 2026 to 23 October 2026 or later; from 31 October 2026 or earlier "
        "to 2 November 2026.",
        "Days between runs: at most 7.",
        "The last run ended on 2 November 2026, 18 days ago.")
    # one edge unpinned is enough: here only the next run's start, the day before it not read
    assert _history(listed, promoted, unread=[back(21)], today=False)[2] == "Days between runs: at most 7."
    # each gap is said alone: a pinned one beside a bound one
    three = [*promoted, back(5), back(4)]
    assert _history(listed, three, holes=[back(27)], today=False)[2] == "Days between runs: at most 7; 12."


# Every sentence

def _every_sentence() -> list[str]:
    listed = listed_from(1, 90, "10.00")
    gaps = [_gap("7.90", _example()), _gap("12.50", _example()), _gap("7.90", listed_from(1, 5, "10.00")),
            _gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")), _gap(Fraction(10, 3), listed_from(1, 30, "3.33")),
            _gap("7.90", {back(5): "10.90", back(4): "99.00", back(3): "11.90"}, holes=[back(4)]),
            _gap("7.90", {back(3): "11.90", back(1): "10.90"}), _gap("1.445", listed_from(1, 30, "1.50")),
            _gap(Fraction("10.01") / 3, listed_from(1, 30, "3.335")),
            _gap(Fraction(10, 3), listed_from(1, 30, "3.335"))]
    histories = [_history(listed, [back(n) for n in (30, 29, 20, 5)], today=False),
                 _history(listed, [back(n) for n in range(1, 11)], today=True), _history(listed, today=True),
                 _history(listed, [back(n) for n in range(85, 91)], unread=[back(40)], today=None),
                 _history(listed_from(1, 5, "10.00"), unread=[back(1)]),
                 _history(listed, [back(n) for n in (30, 29, 28, 20, 19, 18)], unread=[back(21)], holes=[back(27)],
                          today=False)]
    slugs = list(CHAIN_NAMES)
    return [SITE_NAME, FRONT_TITLE, FRONT_RULE, GAP_HEADING, HISTORY_HEADING, METHOD_TITLE, RECORD_TITLE,
            ALWAYS_SENTENCE, FROM_FIELDS, FROM_TEXT, FINE_PRINT, PRICE_NOT_READ, AT_SOME_STORES,
            *TARGET_PHRASES.values(), *(name for name, _ in HIRING), formats_note(), columns_tested(9),
            columns_tested(1), credit(FRIDAY, "12:03"), date_line(FRIDAY), count_line(1840, 6210, 410),
            count_line(1, 1, 1), club_label([]), club_label(slugs), club_label(["shufersal"]),
            targets(list(TARGET_PHRASES)), targets(["club", "other"]), starts_on(FRIDAY),
            window_note(Window(23, FRIDAY, (), True)),
            *(text for column in COLUMNS for text in (no_odds_yet(column.key), across(column.key),
                                                      last_across(column.key, FRIDAY), as_listed([column.key]))),
            as_listed([column.key for column in COLUMNS]), *(unreadable(slug) for slug in slugs),
            *(text for found in gaps for text in gap_sentences(found)),
            *(text for found in histories for text in found),
            listed_price(Decimal("11.90")), deal_price(Fraction(1), "unit"), deal_price(Fraction(1), "kg"),
            buy(Decimal(3)), stores_range(Decimal(1), Decimal(2)), minimum_spend(Decimal(150)), NOT_LISTED,
            ACROSS_HEADING, BROWSE_LINK, BARCODE, *(text for column in COLUMNS for text in chart_key(column.key)),
            *(_price_history(listed) for listed in (_example(), listed_from(1, 90, "10.00"), listed_from(1, 5, "10.00"),
                                                    {back(3): "11.90", back(1): "10.90"},
                                                    {back(n): ("10.90" if n % 2 else "11.90") for n in range(1, 91)}))]


def test_no_sentence_says_a_never_phrase_or_we():
    """Every word list and function over a spread of inputs, flattened as the site check flattens (`basket.check`):
    entities, tags, whitespace, curly quotes and case cannot hide a phrase."""
    for text in _every_sentence():
        for version in (flatten(text), flatten(strip_tags(text))):
            for phrase in NEVER:
                assert flatten(phrase) not in version, (phrase, text)
            assert not PRONOUNS.search(version), text


def test_no_sentence_but_f10s_says_an_odds_word():
    """The site check cuts F10's sentence out of a closed column's section and then refuses any odds word, matched
    as a plain substring here (stricter than the word match the second pre-flight's N4 asks of the check)."""
    f10 = {no_odds_yet(column.key) for column in COLUMNS}
    for text in _every_sentence():
        if text not in f10:
            for word in ODDS_WORDS:
                assert flatten(word) not in flatten(text), (word, text)


def test_a_run_may_hide_in_a_day_the_files_say_nothing_of():
    """Fix round 2, ruling 2: a hole or an unread day could hold a one-day run nobody saw. After the last run it makes
    that run "the last run seen"; inside the days between two runs it makes them "at most"; anywhere outside the runs
    it makes the list the runs seen. A day the files say nothing of inside a run hides none."""
    listed = listed_from(1, 90, "10.00")
    pinned = [back(n) for n in range(5, 11)]                              # 10 to 15 November, both edges read
    assert _history(listed, pinned, unread=[back(2)], today=False)[1:] == (
        "Run seen before today: 10 to 15 November 2026.",
        "The last run seen ended on 15 November 2026, 5 days ago.")
    assert _history(listed, pinned, holes=[back(2)], today=False)[2] == (
        "The last run seen ended on 15 November 2026, 5 days ago.")
    assert _history(listed, pinned, unread=[back(7)], today=False)[1:] == (
        "Run before today: 10 to 15 November 2026.", "The last run ended on 15 November 2026, 5 days ago.")
    # a hole inside the days between two runs, beside neither run
    two = [back(n) for n in (30, 29, 28, 20, 19, 18)]
    assert _history(listed, two, holes=[back(24)], today=False)[1:] == (
        "Runs seen before today: 21 to 23 October 2026; 31 October to 2 November 2026.",
        "Days between runs: at most 7.",
        "The last run ended on 2 November 2026, 18 days ago.")
    # before the first run only: the list is of the runs seen, the days between and the last end stand
    assert _history(listed, two, holes=[back(60)], today=False)[1:] == (
        "Runs seen before today: 21 to 23 October 2026; 31 October to 2 November 2026.",
        "Days between runs: 7.",
        "The last run ended on 2 November 2026, 18 days ago.")


def test_the_last_run_is_the_last_seen_when_today_is_not_known():
    """Fix round 3: every day before today read and the run's end pinned, but today's files say nothing of the product
    (no column-day, its promotions unread, a hole), so today could hold a later run: "the last run seen". The list of
    runs is of the days before today, all read, and keeps "Run before today"."""
    listed = listed_from(1, 90, "10.00")
    pinned = [back(n) for n in range(5, 11)]                              # 10 to 15 November, both edges read
    for today in (None, "unread", "hole"):
        assert _history(listed, pinned, today=today)[1:] == (
            "Run before today: 10 to 15 November 2026.",
            "The last run seen ended on 15 November 2026, 5 days ago.")
    assert _history(listed, pinned, today=False)[2] == "The last run ended on 15 November 2026, 5 days ago."

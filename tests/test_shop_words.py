"""The site's words (`shopper.words`; the plan's Task 15): the design's "Words", "What a visitor sees", P6 to P8, P10, F10
and the amendment's "Words"; the plan's questions J, K, M (f) and O; the first pre-flight's S10, the second's S7, N4,
N7 and N23; and Task 9's review rulings on P8's count, a change's dates and the runs at the window's ends.

The design's quoted sentences are read from docs/shopper-site.md (and the plan's answers from docs/shopper-site-plan.md),
so a change on either side shows. The pairs and column-days are built as tests/test_measures.py builds them."""
import re
from datetime import date, timedelta
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
                           gap_sentences, history_sentences, last_across, no_odds_yet, starts_on, targets, unreadable,
                           window_note)
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
    format" and "in their store format"; another format of the same chain may list the item lower."""
    rule = _found(r'with the rule under it \("([^"]+)"')
    assert FRONT_RULE == rule.replace(" for the item over ", " for the item in the same store format over ")
    assert f'"{FRONT_RULE}"' in PLAN
    line = _found(r'a count line \("([^"]+)"')
    assert count_line(1840, 6210, 410) == line.replace("at that chain", "in their store format") + "."
    assert count_line(1840, 6210, 410).endswith(
        "410 of them are below every listed price of the past 90 days in their store format.")


def test_count_line_with_thousands_separators():
    assert count_line(1_234_567, 21_973, 1_000) == (
        "Today the five chains list 1,234,567 promotions on 21,973 products; 1,000 of them are below every listed "
        "price of the past 90 days in their store format.")
    assert count_line(1, 1, 1) == ("Today the five chains list 1 promotion on 1 product; 1 of them is below every "
                                   "listed price of the past 90 days in their store format.")
    assert count_line(0, 0, 0).startswith("Today the five chains list 0 promotions on 0 products; 0 of them are ")


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
    assert across("shufersal-deal") == "listed across Shufersal Deal"       # the design's "listed chain-wide", per column
    assert across("ramilevy") == "listed across Rami Levy"
    assert last_across("carrefour-city", date(2026, 11, 3)) == "last listed across Carrefour City on 3 November 2026"
    assert last_across("yochananof", date(2027, 1, 1)) == "last listed across Yochananof on 1 January 2027"


def test_the_short_sentences():
    assert window_note(Window(23, date(2026, 11, 1), (), True)) == "23 days of records since 1 November 2026"
    assert window_note(Window(1, date(2026, 11, 19), (), True)) == "1 day of records since 19 November 2026"
    assert window_note(Window(0, None, (), True)) == "no days of records"
    assert starts_on(date(2026, 11, 9)) == "Listed to start on 9 November 2026."
    assert formats_note() == ("The product pages show Shufersal's and Carrefour's store formats apart; the basket "
                              "takes each chain's median over all its included stores.")
    assert columns_tested(9) == ("Nine columns are tested at once: the more are tested, the likelier one passes the "
                                 "gate by luck, which is why it closes again on a losing run (F9).")
    assert columns_tested(2).startswith("Two columns are tested at once: ")
    assert columns_tested(1).startswith("One column is tested at once: ")
    assert columns_tested(13).startswith("13 columns are tested at once: ")
    assert date_range(date(2026, 11, 3), date(2026, 11, 9)) == "3 to 9 November 2026"
    assert date_range(date(2026, 10, 31), date(2026, 11, 2)) == "31 October to 2 November 2026"
    assert date_range(date(2026, 12, 28), date(2027, 1, 3)) == "28 December 2026 to 3 January 2027"
    assert date_range(date(2026, 11, 5), date(2026, 11, 5)) == "5 November 2026"


# P7

def test_p7_sentences_for_the_designs_example():
    """The design's example on Task 9's history: so "of the 90 days with records" (the first pre-flight's S10)."""
    assert "₪4.00, 34%, below the 30-day median listed price of ₪11.90" in DESIGN
    assert gap_sentences(_gap("7.90", _example())) == (
        "Deal price ₪7.90: ₪4.00, 34%, below the 30-day median listed price of ₪11.90 (of the 30 days with records).",
        "The lowest listed price was ₪10.90 over the past 30 days and ₪10.90 over the past 90; listed at ₪7.90 or less "
        "on 0 of the 90 days with records.",
        "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026.")
    # a deal not below the median, or equal to it
    above = gap_sentences(_gap("12.50", _example()))
    assert above[0] == ("Deal price ₪12.50: not below the 30-day median listed price of ₪11.90 (of the 30 days with "
                        "records).")
    assert above[1].endswith("listed at ₪12.50 or less on 90 of the 90 days with records.")
    assert gap_sentences(_gap("11.90", _example()))[0].startswith("Deal price ₪11.90: not below the 30-day median ")
    # the lows of each window, and a median of three places written to the agora, half up (₪1.445 is ₪1.45)
    raised = {**listed_from(61, 90, "7.00"), **listed_from(1, 60, "11.90")}
    assert gap_sentences(_gap("7.90", raised))[1] == (
        "The lowest listed price was ₪11.90 over the past 30 days and ₪7.00 over the past 90; listed at ₪7.90 or less "
        "on 30 of the 90 days with records.")
    assert gap_sentences(_gap("1.00", {back(2): "1.44", back(1): "1.45"}))[0].startswith(
        "Deal price ₪1.00: ₪0.45, 31%, below the 30-day median listed price of ₪1.45 ")


def test_p7_and_p8_with_a_short_window():
    """P6: a window of fewer than 20 of 30 or 60 of 90 days of records says so, and P8 counts the same days P7 does."""
    listed = listed_from(1, 5, "10.00")                                   # 15 to 19 November
    assert gap_sentences(_gap("7.90", listed)) == (
        "Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the 5 days of records since "
        "15 November 2026).",
        "The lowest listed price was ₪10.00 over the past 30 days and ₪10.00 over the past 90; listed at ₪7.90 or less "
        "on 0 of the 5 days of records since 15 November 2026.",
        "The listed price did not change on the 5 days of records since 15 November 2026.")
    assert _history(listed, promoted=[back(2), back(1)], today=False) == (
        f"On a promotion on 2 of the 5 days of records since 15 November 2026, {MORNING}.",
        "Run: 18 to 19 November 2026.",
        "The last run ended on 19 November 2026, 1 day ago.")
    one = gap_sentences(_gap("7.90", {back(1): "10.00"}))
    assert one[0].endswith("(of the 1 day of records since 19 November 2026).")
    # 25 of 30 days with records is no short 30-day window, but every day of the 30 is not known
    holed = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00"), holes=[back(n) for n in range(1, 6)]))
    assert holed[0].endswith("(of the 25 days with records).")
    assert holed[2] == "The listed price did not change on the 25 days with records of the past 30."
    full = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00")))
    assert full[2] == "The listed price did not change in the past 30 days."


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


def test_p7_figures_for_a_deal_of_more_than_two_places():
    """A deal price is written to the agora, half up, from its exact value (S6); the count of days at or below it reads
    the exact value (Task 9). So when the figure rounds up, "at ₪1.45 or less" would take in a listed ₪1.45 the count
    leaves out: the sentence says "below ₪1.45". A gap under half an agora is "less than ₪0.01"."""
    up = gap_sentences(_gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")))      # 1.4466...
    assert up[0] == ("Deal price ₪1.45: less than ₪0.01, 0%, below the 30-day median listed price of ₪1.45 (of the 30 "
                     "days with records).")
    assert up[1] == ("The lowest listed price was ₪1.45 over the past 30 days and ₪1.45 over the past 90; listed below "
                     "₪1.45 on 0 of the 30 days of records since 21 October 2026.")
    down = gap_sentences(_gap(Fraction(10, 3), listed_from(1, 30, "3.33")))         # 3.3333...
    assert down[0].startswith("Deal price ₪3.33: not below the 30-day median listed price of ₪3.33 ")
    assert down[1].endswith("listed at ₪3.33 or less on 30 of the 30 days of records since 21 October 2026.")


# P8

def test_p8_sentences_in_the_designs_forms():
    """Page day 6 December 2026; 87 days with records (three days of the 90 the product is not listed); on promotion
    from 3 to 9 and from 24 to 30 November, 12 days listed of them; off promotion today."""
    page_day = date(2026, 12, 6)
    window = [page_day - timedelta(days=n) for n in range(90, 0, -1)]
    not_listed = {date(2026, 10, 15), date(2026, 11, 5), date(2026, 11, 26)}
    listed = {day: "10.00" for day in window if day not in not_listed}
    promoted = [day for day in listed if date(2026, 11, 3) <= day <= date(2026, 11, 9)
                or date(2026, 11, 24) <= day <= date(2026, 11, 30)]
    assert _history(listed, promoted, today=False, page_day=page_day, extra_days=not_listed) == (
        f"On a promotion on 12 of the 87 days with records, {MORNING}.",
        "Runs: 3 to 9 November 2026; 24 to 30 November 2026.",
        "Days between runs: 14.",
        "The last run ended on 30 November 2026, 6 days ago.")
    assert _history(listed, today=False, page_day=page_day, extra_days=not_listed) == (
        "No promotion listed in the 87 days with records.",)


def test_p8_runs_and_the_days_between_them():
    listed = listed_from(1, 90, "10.00")
    promoted = [back(n) for n in (30, 29, 28, 20, 19, 18, 5, 4)]
    assert _history(listed, promoted, today=False) == (
        f"On a promotion on 8 of the 90 days with records, {MORNING}.",
        "Runs: 21 to 23 October 2026; 31 October to 2 November 2026; 15 to 16 November 2026.",
        "Days between runs: 7; 12.",
        "The last run ended on 16 November 2026, 4 days ago.")


def test_p8_counts_the_days_with_records_p7_counts():
    """Task 9's review, ruling 1: one N for "days with records" in a section; the days whose promotions could not be
    read are said, not dropped from N."""
    listed = listed_from(1, 6, "10.00")                                   # 14 to 19 November
    promoted = [back(n) for n in range(1, 6)]
    found = _history(listed, promoted, unread=[back(3)], today=False)
    assert found == (
        f"On a promotion on 4 of the 6 days of records since 14 November 2026 (promotions could not be read on 1), "
        f"{MORNING}.",
        "Run: 15 to 19 November 2026.",
        "The last run ended on 19 November 2026, 1 day ago.")
    same = "of the 6 days of records since 14 November 2026"
    assert same in gap_sentences(_gap("7.90", listed))[0] and same in found[0]
    # none on promotion, some days not read: the count, not "no promotion listed"
    assert _history(listed_from(1, 5, "10.00"), unread=[back(2), back(1)]) == (
        f"On a promotion on 0 of the 5 days of records since 15 November 2026 (promotions could not be read on 2), "
        f"{MORNING}.",)


def test_p8_on_promotion_today():
    """Ruling 3 (a): the window ends yesterday, so a run reaching it is not over when today's files list the product
    on promotion: today is said, and the history is worded as before today."""
    listed = listed_from(1, 90, "10.00")
    assert _history(listed, [back(n) for n in range(1, 11)], today=True) == (
        f"On a promotion today, {MORNING}.",
        f"Before today: on a promotion on 10 of the 90 days with records, {MORNING}.",
        "Run before today: 10 to 19 November 2026.")
    assert _history(listed, today=True) == (
        f"On a promotion today, {MORNING}.",
        "Before today: no promotion listed in the 90 days with records.")
    # the run seen to 17 November, the two days after it holes: before today it may have gone on
    found = _history(listed, [back(n) for n in range(3, 11)], holes=[back(2), back(1)], today=True)
    assert found[1:] == (f"Before today: on a promotion on 8 of the 88 days with records, {MORNING}.",
                         "Run before today: from 10 November 2026 to 17 November 2026 or later.")
    assert _history({}, today=True) == (f"On a promotion today, {MORNING}.",)
    assert _history({}) == ()


def test_p8_runs_at_the_windows_ends():
    """Ruling 3 (b): a run seen from the window's first day read may have started earlier; and its mirror, a run seen
    to the last day read when today's state is not known, may go on."""
    listed = listed_from(1, 90, "10.00")
    first = [back(n) for n in range(85, 91)]                              # 22 to 27 August, the window's first days
    assert _history(listed, first, today=False) == (
        f"On a promotion on 6 of the 90 days with records, {MORNING}.",
        "Run: from 22 August 2026 or earlier to 27 August 2026.",
        "The last run ended on 27 August 2026, 85 days ago.")
    # the window's first day a hole: the run seen from the first day read
    assert _history(listed, first, holes=[back(90)], today=False)[1] == (
        "Run: from 23 August 2026 or earlier to 27 August 2026.")
    last = [back(n) for n in range(1, 6)]                                 # 15 to 19 November
    for today in (None, "unread", "hole"):
        assert _history(listed, last, today=today) == (
            f"On a promotion on 5 of the 90 days with records, {MORNING}.",
            "Run: from 15 November 2026 to 19 November 2026 or later.")
    assert _history(listed, last, today=False)[1:] == ("Run: 15 to 19 November 2026.",
                                                       "The last run ended on 19 November 2026, 1 day ago.")
    # an open run beside a pinned one: only the end the files cannot pin is said open
    assert _history(listed, [*first, back(5), back(4)], today=False)[1:3] == (
        "Runs: from 22 August 2026 or earlier to 27 August 2026; 15 to 16 November 2026.", "Days between runs: 79.")
    assert _history(listed, [*first, back(2), back(1)])[1:] == (
        "Runs: from 22 August 2026 or earlier to 27 August 2026; from 18 November 2026 to 19 November 2026 or later.",
        "Days between runs: 82.")
    whole = [back(n) for n in range(1, 91)]
    assert _history(listed, whole)[1] == "Run: from 22 August 2026 or earlier to 19 November 2026 or later."


# Every sentence

def _every_sentence() -> list[str]:
    listed = listed_from(1, 90, "10.00")
    gaps = [_gap("7.90", _example()), _gap("12.50", _example()), _gap("7.90", listed_from(1, 5, "10.00")),
            _gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")), _gap(Fraction(10, 3), listed_from(1, 30, "3.33")),
            _gap("7.90", {back(5): "10.90", back(4): "99.00", back(3): "11.90"}, holes=[back(4)]),
            _gap("7.90", {back(3): "11.90", back(1): "10.90"})]
    histories = [_history(listed, [back(n) for n in (30, 29, 20, 5)], today=False),
                 _history(listed, [back(n) for n in range(1, 11)], today=True), _history(listed, today=True),
                 _history(listed, [back(n) for n in range(85, 91)], unread=[back(40)], today=None),
                 _history(listed_from(1, 5, "10.00"), unread=[back(1)])]
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
            *(text for found in histories for text in found)]


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

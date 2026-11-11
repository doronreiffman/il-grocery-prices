"""The site's words (`shopper.words`; the plan's Task 15): the design's "Words", "What a visitor sees", P6, P7, P10,
F10 and the amendment's "Words"; the plan's questions J, K, M (f) and O; the first pre-flight's S10, the second's S7,
N4, N7 and N23; Task 9's review rulings on a change's dates; Task 15's review rulings (fix round 1) on the shown figures,
the bounds beside a gap in the records and "before today"; and store first's verdict words (docs/store-first.md,
"Words"; the store-first plan's Task 3). P8's sentences, the listed-price history and P9's words went with their page
parts (store first, q33).

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
from shopper import words
from shopper.columns import BY_KEY, COLUMNS
from shopper.history import READ_DAYS, Window, window
from shopper.measures import gap
from shopper.promotions import RESTRICTIONS
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, AT_SOME_STORES, CHAINS_LINE, CREDIT_START, FINE_PRINT, FROM_FIELDS,
                           FROM_TEXT, FRONT_SUBTITLE, FRONT_TITLE, GAP_HEADING, HIRING, METHOD_TITLE,
                           NEVER, ODDS_WORDS, PRICE_NOT_READ, RECORD_TITLE, SITE_NAME, TARGET_PHRASES, as_listed,
                           columns_tested, credit, date_line, date_range, formats_note, gap_sentences, last_across,
                           lead_line, marked_none, no_odds_yet, promotions_line, targets, unreadable, window_note)
from shopper.words import (BARCODE, BROWSE_LINK, CHANGES_SHOWN, PER, buy, deal_price, listed_price, minimum_spend,
                           percent_text, shown_below, stores_range)
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
    assert (FRONT_TITLE, GAP_HEADING) == tuple(_quoted(_line(DESIGN, "The public names (Q4)"))[:2])
    assert f'**"{METHOD_TITLE}"** (`method.html`)' in DESIGN and f'**"{RECORD_TITLE}"** (`record.html`)' in DESIGN
    assert f'"{PRICE_NOT_READ}"' in DESIGN and f'"{AT_SOME_STORES}"' in DESIGN
    # question K: the phrases by code, in the order the field reads its codes (club, card, other: N2)
    k = _line(PLAN, "- (Owner, 2026-11-07: as recommended.) **K.")
    assert tuple(TARGET_PHRASES) == tuple(RESTRICTIONS.values())
    assert tuple(TARGET_PHRASES.values()) == tuple(_quoted(k)[:3])
    # question J, as the owner changed it on 2026-11-10: one constant, so a rename is one line
    assert SITE_NAME == "Deal or No Deal"
    j = _line(PLAN, "- (Owner, 2026-11-07: as recommended.) **J.")
    assert f'Changed by the owner on 2026-11-10: "{SITE_NAME}"' in j
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
    assert date_line(date(2026, 11, 10)) == "Prices of Tuesday 10 November 2026"       # the owner, 2026-11-10
    # the chains' line under the site's name, in slug order (the owner, 2026-11-10)
    assert CHAINS_LINE == "Shufersal · Rami Levy · Osher Ad · Carrefour · Yochananof"
    assert CHAINS_LINE == _found(r'the five chains\' names \("([^"]+)"\)')
    # F10, naming the column (the amendment's "Words": "No odds yet for Shufersal Deal.")
    f10 = _found(r'one fixed sentence: "(No odds yet for Shufersal\. [^"]+)"')
    assert '("No odds yet for Shufersal Deal.")' in DESIGN
    assert no_odds_yet("shufersal-deal") == f10.replace("for Shufersal.", "for Shufersal Deal.")
    for column in COLUMNS:
        assert no_odds_yet(column.key) == f10.replace("for Shufersal.", f"for {column.name}.")
    assert "two weeks later" in f10
    # deploy prep (the owner, 2026-11-10): forecasts are frozen from a format's 30th day of records (FIRST_RECORD_DAY), on
    # the days F2 allows, never "every day"
    assert no_odds_yet("shufersal-deal") == (
        "No odds yet for Shufersal Deal. From a store format's 30th day of records, this site freezes forecasts on each "
        "day its rules allow and scores them two weeks later; the odds appear here once they beat two rules of thumb "
        "over 90 days (Track record).")
    # P10's sentence, per chain (on each of its columns: question M (g))
    p10 = _found(r'\("(Promotions from Carrefour\'s files could not be read today)"\)')
    assert unreadable("carrefour") == p10 + "."
    assert unreadable("ramilevy") == "Promotions from Rami Levy's files could not be read today."


def test_the_front_title_and_lead_line_are_the_owners_plain_words():
    """The owner's final framing (2026-11-10, 22:30): the site asks whether a promotion is actually a deal. The title
    is that question; a line under it says what each promotion is checked against, "up to" 3 months (READ_DAYS, 90
    days), since the records start on 1 November 2026 and the 90-day window holds fewer days until late January; the
    lead line says how many passed (the site-day file's `below`: those passing every front condition), with no total
    beside it, since the products on promotion the build counts are only those carried by at least half of a format's
    stores (the fold-out's count says so). The design quotes each form."""
    assert FRONT_TITLE == _quoted(_line(DESIGN, "The public names (Q4)"))[0] == "Is it actually a deal?"
    assert FRONT_SUBTITLE == "Promotions checked against up to 3 months of shelf prices."
    assert f'"{FRONT_SUBTITLE}"' in DESIGN
    assert lead_line(37, True) == _found(r'one lead line under it: "([^"]+)"') == "37 products passed today."
    assert lead_line(1, True) == "1 product passed today."
    assert lead_line(1_000, True) == "1,000 products passed today."
    # no deal: before some store format has 20 days of records in the 30, none can pass yet
    assert lead_line(0, False) == "None yet: a product needs 20 days of price history first."
    assert lead_line(0, True) == "None passed today."
    assert lead_line(37, False) == lead_line(37, True)                   # a row says enough: its column is ready
    for form in (lead_line(0, False), lead_line(0, True)):
        assert f'"{form}"' in DESIGN


def test_the_promotions_line_says_what_it_counts():
    """The final review's finding 4, kept in the fold-out's plain words: the count is of the promotions listed across a
    column today (`shopper.build`), carried by at least half of a store format's stores, not every promotion in the
    chains' files, most of which run at some stores only."""
    assert promotions_line(1840, 6210) == _found(r'today\'s counts \("([^"]+)"\)') == (
        "Today the five chains list 1,840 promotions carried by at least half of a store format's stores, on 6,210 "
        "products.")
    assert promotions_line(1, 1) == ("Today the five chains list 1 promotion carried by at least half of a store "
                                     "format's stores, on 1 product.")
    assert promotions_line(1_234_567, 21_973) == ("Today the five chains list 1,234,567 promotions carried by at least "
                                                  "half of a store format's stores, on 21,973 products.")


def test_marked_none_names_the_chains_marking_none():
    """Question K's label, now a sentence of the fold-out: the chains whose files mark no restricted promotion today,
    in slug order; nothing when every chain marks one."""
    assert marked_none([]) == ""
    assert marked_none(["shufersal"]) == "Today Shufersal's files mark no deal this way."
    assert marked_none(["yochananof", "shufersal"]) == ("Today Shufersal's and Yochananof's files mark no deal this "
                                                       "way.")
    assert marked_none(["osherad", "ramilevy", "carrefour"]) == ("Today Rami Levy's, Osher Ad's and Carrefour's files "
                                                                 "mark no deal this way.")


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
    # deploy prep: "seen", since the registry knows record days only, and a hole day after it could have been across
    assert last_across("carrefour-city", date(2026, 11, 3)) == (
        "last seen listed across Carrefour City on 3 November 2026")
    assert last_across("yochananof", date(2027, 1, 1)) == "last seen listed across Yochananof on 1 January 2027"


def test_the_short_sentences():
    assert window_note(Window(23, date(2026, 11, 1), (), True)) == "23 days of records since 1 November 2026"
    # deploy prep: one day spelled as P7's one-day form spells it, never "1 day" beside "one day"
    assert window_note(Window(1, date(2026, 11, 19), (), True)) == "one day of records since 19 November 2026"
    assert window_note(Window(2, date(2026, 11, 18), (), True)) == "2 days of records since 18 November 2026"
    assert window_note(Window(0, None, (), True)) == "no days of records"
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


def test_p7_with_a_short_window():
    """P6: a window of fewer than 20 of 30 or 60 of 90 days of records says so."""
    listed = listed_from(1, 5, "10.00")                                   # 15 to 19 November
    assert gap_sentences(_gap("7.90", listed)) == (
        "Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the 5 days of records since "
        "15 November 2026 before today).",
        "The lowest listed price over the 5 days of records before today (the first on 15 November 2026) was ₪10.00; "
        "listed at ₪7.90 or less on 0 of them.",
        "The listed price did not change on the 5 days of records since 15 November 2026 before today.")
    one = gap_sentences(_gap("7.90", {back(1): "10.00"}))
    assert one[0].endswith("(of the one day of records before today, 19 November 2026).")       # q31
    assert len(one) == 2                                  # q31: one day of records has nothing to compare
    # 25 of 30 days with records is no short 30-day window, but every day of the 30 is not known
    holed = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00"), holes=[back(n) for n in range(1, 6)]))
    assert holed[0].endswith("(of the 25 days with records before today).")
    assert holed[2] == "The listed price did not change on the 25 days with records of the 30 before today."
    full = gap_sentences(_gap("7.90", listed_from(1, 30, "10.00")))
    assert full[2] == "The listed price did not change in the 30 days before today."


def test_the_lows_say_the_days_of_records_each_is_over():
    """Deploy prep (the owner, 2026-11-10): each low is said over the days of records its window holds (P6), in the
    window kinds of the change sentence (every day, a short window, a window with gaps), so the sentence stays true
    with 15 days of records at launch; a low is "over" its days, never "on" them, which could read as the price on
    every one of them, and a short window's first day follows its count; one phrase when both windows hold the same
    days; the days at or below keep P6's "of the N days with records" sense: "of them", "of those 45", or "of the 90
    days with records" for a full window; one day of records is said as that day's price, never "0 of the 1 day"."""
    launch = gap_sentences(_gap("7.90", listed_from(1, 15, "10.00")))       # 5 to 19 November: 15 days of records
    assert launch[1] == ("The lowest listed price over the 15 days of records before today (the first on 5 November "
                         "2026) was ₪10.00; listed at ₪7.90 or less on 0 of them.")
    assert gap_sentences(_gap("10.00", listed_from(1, 15, "10.00")))[1].endswith(
        "listed at ₪10.00 or less on 15 of them.")
    # one day of records: its price, above, at or below the deal, the true one of the three on the figures shown
    # (deploy prep: both figures are shown, so "at or below" claimed less than they show)
    assert gap_sentences(_gap("7.90", {back(1): "10.00"}))[1] == (
        "The listed price on the one day of records before today (19 November 2026) was ₪10.00, above ₪7.90.")
    assert gap_sentences(_gap("7.90", {back(1): "7.90"}))[1] == (                            # q31: names the deal
        "The listed price on the one day of records before today (19 November 2026) was ₪7.90, the same as the deal "
        "price.")
    assert gap_sentences(_gap("7.90", {back(1): "7.50"}))[1] == (
        "The listed price on the one day of records before today (19 November 2026) was ₪7.50, below ₪7.90.")
    # a listed ₪7.895 is shown ₪7.90: at the deal as shown, though below it exactly
    assert gap_sentences(_gap("7.90", {back(1): "7.895"}))[1].endswith("was ₪7.90, the same as the deal price.")
    # a deal of 3 for ₪10 (₪3.333…) is shown ₪3.33: a listed ₪3.335, shown ₪3.34, is above it as shown
    assert gap_sentences(_gap(Fraction(10, 3), {back(1): "3.335"}))[1].endswith("was ₪3.34, above ₪3.33.")
    assert gap_sentences(_gap("7.90", {back(2): "10.00"}))[1] == (
        "The listed price on the one day of records before today (18 November 2026) was ₪10.00, above ₪7.90.")
    # gaps in both windows: 25 of the 30 days and 85 of the 90 hold records
    gapped = {**listed_from(31, 90, "7.50"), **listed_from(1, 30, "10.00")}
    holes = [back(n) for n in range(1, 6)]
    assert gap_sentences(_gap("7.90", gapped, holes=holes))[1] == (
        "The lowest listed price was ₪10.00 over the 25 days with records of the 30 before today and ₪7.50 over the "
        "85 days with records of the 90 before today; listed at ₪7.90 or less on 60 of those 85.")
    # a full 30-day window and a short 90-day one, 45 days of records since 6 October
    short = {**listed_from(31, 45, "9.00"), **listed_from(1, 30, "10.00")}
    assert gap_sentences(_gap("7.90", short))[1] == (
        "The lowest listed price was ₪10.00 in the 30 days before today and ₪9.00 over the 45 days of records before "
        "today (the first on 6 October 2026); listed at ₪7.90 or less on 0 of those 45.")
    # a short 30-day window beside older records: 10 of the 30, 70 of the 90
    older = {**listed_from(31, 90, "9.50"), **listed_from(1, 10, "10.00")}
    assert gap_sentences(_gap("7.90", older))[1] == (
        "The lowest listed price was ₪10.00 over the 10 days of records before today (the first on 10 November 2026) "
        "and ₪9.50 over the 70 days with records of the 90 before today; listed at ₪7.90 or less on 0 of those 70.")
    # a full 90-day window keeps its words: "in the 90 days before today", "of the 90 days with records"
    assert gap_sentences(_gap("7.90", {**listed_from(31, 90, "7.50"), **listed_from(1, 30, "10.00")}))[1] == (
        "The lowest listed price was ₪10.00 in the 30 days before today and ₪7.50 in the 90 days before today; listed "
        "at ₪7.90 or less on 60 of the 90 days with records.")


def test_one_day_of_records_in_the_30_beside_more_in_the_90():
    """Deploy prep (the main session's call, 2026-11-10): a 30-day window of one day of records beside a longer 90-day
    one says its one day as the one-day form does, "on the one day of records before today (19 November 2026)", never
    "over the 1 days of records before today (the first on …)"."""
    listed = {back(1): "10.00", **listed_from(31, 70, "9.00")}
    found = gap_sentences(_gap("7.90", listed))
    # P7's first sentence spells the one day the same way (deploy prep); the change from 20 October lies inside the 30
    assert found[0] == ("Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the one day "
                        "of records before today, 19 November 2026).")                        # q31
    assert found[2] == "The listed price rose from ₪9.00 (20 October 2026) to ₪10.00 (19 November 2026)."
    assert found[1] == ("The lowest listed price was ₪10.00 on the one day of records before today (19 November 2026) "
                        "and ₪9.00 over the 41 days of records before today (the first on 11 September 2026); listed at "
                        "₪7.90 or less on 0 of those 41.")


def test_one_day_of_records_is_said_as_that_day():
    """q31 (the owner, 2026-11-10): a window of one day of records is said as that day, its date in brackets after
    "before today", never "since 19 November 2026 … before today" nor "1 of the one day"; inside P7's first sentence's
    own brackets the date follows a comma, so no brackets nest. The lows' "at" form names the deal. With one day of
    records there is nothing to compare, so no sentence says the listed price did not change on it; a change from a
    record before the 30 is still said (the test above). Two days keep their words."""
    one = {back(1): "10.00"}
    # P7: the median's one day inside its brackets, the lows, and no change sentence
    assert gap_sentences(_gap("7.90", one)) == (
        "Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the one day of records "
        "before today, 19 November 2026).",
        "The listed price on the one day of records before today (19 November 2026) was ₪10.00, above ₪7.90.")
    assert gap_sentences(_gap("10.00", one))[1] == (
        "The listed price on the one day of records before today (19 November 2026) was ₪10.00, the same as the deal "
        "price.")
    # the 30's one day beside more in the 90 at the same price: no change, and nothing said of it
    older = gap_sentences(_gap("7.90", {**one, **listed_from(31, 70, "10.00")}))
    assert len(older) == 2 and older[0].endswith("(of the one day of records before today, 19 November 2026).")
    said = [*gap_sentences(_gap("7.90", one)), *older]
    assert not [line for line in said if "since" in line or " of the one day" in line or "did not change" in line]
    # two days of records keep their words
    two = {back(2): "10.00", back(1): "10.00"}
    assert gap_sentences(_gap("7.90", two)) == (
        "Deal price ₪7.90: ₪2.10, 21%, below the 30-day median listed price of ₪10.00 (of the 2 days of records since "
        "18 November 2026 before today).",
        "The lowest listed price over the 2 days of records before today (the first on 18 November 2026) was ₪10.00; "
        "listed at ₪7.90 or less on 0 of them.",
        "The listed price did not change on the 2 days of records since 18 November 2026 before today.")


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
    assert probe[1] == ("The lowest listed price over the 30 days of records before today (the first on 21 October "
                        "2026) was ₪3.34; listed at ₪3.34 or less on 30 of them.")
    # a deal of ₪1.445, shown ₪1.45, against ₪1.50: ₪0.05 and 3%, not the exact gap's ₪0.06 and 4%
    assert gap_sentences(_gap("1.445", listed_from(1, 30, "1.50")))[0] == (
        "Deal price ₪1.45: ₪0.05, 3%, below the 30-day median listed price of ₪1.50 (of the 30 days with records "
        "before today).")
    # 3 for ₪4.34 (1.4466...) against a listed ₪1.45: equal as shown, so not below it, and listed at it on every day
    up = gap_sentences(_gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")))
    assert up[0].startswith("Deal price ₪1.45: not below the 30-day median listed price of ₪1.45 ")
    assert up[1].endswith("listed at ₪1.45 or less on 30 of them.")
    # 3 for ₪10 (3.3333...), shown ₪3.33, against a median of ₪3.335 shown ₪3.34: ₪0.01 below, and no day at or below
    down = gap_sentences(_gap(Fraction(10, 3), listed_from(1, 30, "3.335")))
    assert down[0].startswith("Deal price ₪3.33: ₪0.01, under 1%, below the 30-day median listed price of ₪3.34 ")
    assert down[1].endswith("listed at ₪3.33 or less on 0 of them.")



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


def _changing(count: int, start: int = 1) -> dict:
    """A listed price that changes `count` times over the days before today, a change every other day, newest first
    seen `start` days back: ₪10.00, then ₪11.00, ₪10.00, … ."""
    return {back(start + n): ("10.00" if (count - n // 2) % 2 == 0 else "11.00") for n in range(2 * count + 1)}


def test_a_change_list_holds_the_newest_five():
    """Task 16, round 2: P7's change list shows at most CHANGES_SHOWN (5) changes, the newest, in day order; past five,
    a tail says how many were seen, in the very window phrase the sentence uses when nothing changed."""
    assert CHANGES_SHOWN == 5
    five = _changing(5)
    assert len(gap_sentences(_gap("7.90", five))[2].split(", then ")) == 5
    assert "(the last" not in gap_sentences(_gap("7.90", five))[2]
    six = _changing(6)
    days = sorted(six)
    assert gap_sentences(_gap("7.90", six))[2] == (
        f"The listed price fell from ₪11.00 to ₪10.00 on {days[3]:%-d %B %Y}, then rose from ₪10.00 to ₪11.00 on "
        f"{days[5]:%-d %B %Y}, then fell from ₪11.00 to ₪10.00 on {days[7]:%-d %B %Y}, then rose from ₪10.00 to "
        f"₪11.00 on {days[9]:%-d %B %Y}, then fell from ₪11.00 to ₪10.00 on {days[11]:%-d %B %Y} (the last 5 of 6 "
        "changes seen on the 13 days of records since 7 November 2026 before today).")
    assert days[3] - days[1] == timedelta(days=2) and "rose from ₪10.00 to ₪11.00 on" not in gap_sentences(
        _gap("7.90", six))[2].split(", then ")[0]                       # the oldest change is the one left out
    # the window phrase is the unchanged sentence's own: every day with a record, or those with records of the 30
    daily = {back(n): ("10.00" if n % 2 else "11.00") for n in range(1, 91)}
    assert gap_sentences(_gap("7.90", daily))[2].endswith(
        " (the last 5 of 30 changes seen in the 30 days before today).")   # one on the window's first day
    assert gap_sentences(_gap("7.90", daily, holes=[back(2)]))[2].endswith(
        " (the last 5 of 28 changes seen on the 29 days with records of the 30 before today).")


def test_a_change_across_a_gap_keeps_its_bounds_in_the_capped_list():
    """Inside the newest five, a change across a hole still gives both record days, never one date."""
    listed = _changing(6)
    days = sorted(listed)
    hole = days[-2]                                                       # between the last two changes' days
    listed[hole] = "99.00"
    said = gap_sentences(_gap("7.90", listed, holes=[hole]))[2]
    shown = said.split(", then ")
    assert len(shown) == 5 and "(the last 5 of 6 changes seen" in said
    assert shown[-1].startswith(f"fell from ₪11.00 ({days[-3]:%-d %B %Y}) to ₪10.00 ({days[-1]:%-d %B %Y})")


def test_the_product_pages_labels():
    """Task 16's labels (the controller's rulings): the design's and the brief's phrases put together. Today's listed
    price carries the three ALWAYS phrases a listed price takes; a deal's price is a unit's or a kilogram's (P4), to the
    agora half up; the stores' range is labelled as the stores'."""
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
    assert (BROWSE_LINK, BARCODE) == ("Browse by first letter", "Barcode")


# Every sentence

def _every_sentence() -> list[str]:
    listed = listed_from(1, 90, "10.00")
    gaps = [_gap("7.90", _example()), _gap("12.50", _example()), _gap("7.90", listed_from(1, 5, "10.00")),
            _gap(Fraction("4.34") / 3, listed_from(1, 30, "1.45")), _gap(Fraction(10, 3), listed_from(1, 30, "3.33")),
            _gap("7.90", {back(5): "10.90", back(4): "99.00", back(3): "11.90"}, holes=[back(4)]),
            _gap("7.90", {back(3): "11.90", back(1): "10.90"}), _gap("1.445", listed_from(1, 30, "1.50")),
            _gap(Fraction("10.01") / 3, listed_from(1, 30, "3.335")),
            _gap(Fraction(10, 3), listed_from(1, 30, "3.335"))]
    slugs = list(CHAIN_NAMES)
    return [SITE_NAME, CHAINS_LINE, FRONT_TITLE, FRONT_SUBTITLE, GAP_HEADING, METHOD_TITLE, RECORD_TITLE,
            ALWAYS_SENTENCE, FROM_FIELDS, FROM_TEXT, FINE_PRINT, PRICE_NOT_READ, AT_SOME_STORES,
            *TARGET_PHRASES.values(), *(name for name, _ in HIRING), formats_note(), columns_tested(9),
            columns_tested(1), credit(FRIDAY, "12:03"), date_line(FRIDAY), lead_line(410, True), lead_line(1, True),
            lead_line(0, False), lead_line(0, True), promotions_line(1840, 6210),
            promotions_line(1, 1), marked_none(slugs), marked_none(["shufersal"]),
            targets(list(TARGET_PHRASES)), targets(["club", "other"]),
            window_note(Window(23, FRIDAY, (), True)),
            *(text for column in COLUMNS for text in (no_odds_yet(column.key), last_across(column.key, FRIDAY),
                                                      as_listed([column.key]))),
            as_listed([column.key for column in COLUMNS]), *(unreadable(slug) for slug in slugs),
            *(text for found in gaps for text in gap_sentences(found)),
            listed_price(Decimal("11.90")), deal_price(Fraction(1), "unit"), deal_price(Fraction(1), "kg"),
            buy(Decimal(3)), stores_range(Decimal(1), Decimal(2)), minimum_spend(Decimal(150)), BROWSE_LINK,
            BARCODE]


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


# Store first (q33): the verdict's words (docs/store-first.md, "Words", verbatim; the plan's "Words this plan adds")

STORE_FIRST = (ROOT / "docs" / "store-first.md").read_text(encoding="utf-8")
OCT = date(2026, 10, 1)


def _table(where: str) -> list[str]:
    """The quoted words of the design's Words table row `where`."""
    return _quoted(_line(STORE_FIRST, f"| {where} |"))


def _days_of(*prices, on=()):
    """Tracked days from 1 October, one a day: each price (None for a sale day of unknown price), on sale on the `on`
    indexes (an unknown price is always on sale)."""
    from shopper.verdict import Day
    return tuple(Day(OCT + timedelta(days=n), Decimal("12.90"), None if price is None else Decimal(price),
                     price is None or n in on) for n, price in enumerate(prices))


def _verdict(call="deal", column="carrefour-market", days=(), today=None, usual=None, saving=None, struct=None,
             low=None, sale=None, on_sale=False):
    from shopper.verdict import Verdict
    return Verdict(column=column, call=call, days=days, today_price=None if today is None else Decimal(today),
                   struct=struct, usual=None if usual is None else Decimal(usual),
                   saving=None if saving is None else Decimal(saving), last_low=low, last_sale=sale,
                   on_sale_today=on_sale)


def _condition_struct(**more) -> dict:
    found = {"restrictions": [], "programmes": [], "min_spend": None, "buy": Decimal("1"), "per": "unit"}
    return found | more


def test_on_day_is_a_shopper_date():
    """Shopper text says the day and month, no year: "12 October"."""
    assert words.on_day(date(2026, 10, 12)) == "12 October"
    assert words.on_day(date(2027, 1, 3)) == "3 January"


def test_the_verdicts_words_are_the_designs_verbatim():
    """The design's Words table, each row's examples: the badges, the three reasons, the condition, last this low,
    how often, the no-verdict lines, the coming sale and "Elsewhere today"."""
    nine = _days_of(*["10.90"] * 9)
    deal = _verdict(days=_days_of(*["11.90"] * 9), today="10.00", usual="11.90", saving="1.90", struct={"per": "unit"})
    assert [words.badge(deal)] == _table("Deal badge")
    assert words.reason(deal) == "Usually ₪11.90, sales included (9 days tracked)." == _table("Deal reason")[0]
    no_deal = _verdict("no_deal", days=nine, today="10.90", usual="10.90", saving="0.00", struct={"per": "unit"})
    assert [words.badge(no_deal)] == _table("No deal badge")
    assert [words.reason(no_deal)] == _table("No deal reason, always on")
    small = _verdict("no_deal", days=_days_of(*["3.20"] * 12), today="2.80", usual="3.20", saving="0.40",
                     struct={"per": "unit"})
    assert [words.reason(small)] == _table("No deal reason, small")
    assert [*words.conditions(_condition_struct(restrictions=["club"])),
            *words.conditions(_condition_struct(buy=Decimal("2")))] == _table("Condition")
    low = _verdict(days=_days_of(*["12.90"] * 3), today="9.90")
    found = _days_of(*["12.90"] * 9, "9.90")
    lowered = _verdict(days=found, today="9.90", low=found[-1])
    assert words.last_low(lowered) == "Last this low: 10 October, at ₪9.90."
    from shopper.verdict import Day
    on_12 = Day(date(2026, 10, 12), Decimal("12.90"), Decimal("9.90"), False)
    assert [words.last_low(_verdict(days=(*_days_of(*["12.90"] * 9), on_12), today="9.90", low=on_12)),
            words.last_low(_verdict(days=_days_of(*["12.90"] * 10), today="9.90"))] == _table("Last this low")
    assert words.last_low(low) == "Lowest in the 3 days tracked."
    assert [words.how_often(_verdict(days=_days_of(*["9.90"] * 9, on=range(9))))] == _table("How often")
    lines = _table("No verdict")
    assert [words.NO_VERDICT[call] for call in ("no_sale", "new", "some_stores", "price_unread", "unread_today",
                                                "mostly_unknown")] == lines[:6]
    assert words.not_sold("carrefour-market", date(2026, 11, 3)) == lines[6]
    assert [words.coming_sale(date(2026, 11, 14))] == _table("Coming sale")
    assert [words.ELSEWHERE] == _table("Other store types")
    assert f'the fold-out "{words.WORKED_OUT}"' in STORE_FIRST
    # S7's example in the design's rules
    sale = Day(date(2026, 10, 12), Decimal("12.90"), Decimal("9.90"), True)
    sixty = _verdict(days=_days_of(*["12.90"] * 48, *[None] * 12), sale=sale, on_sale=True)
    assert f'"{words.how_often(sixty)}"' in STORE_FIRST


def test_the_no_verdict_lines_and_the_plans_words():
    """The design's six lines, the plan's provisional one for no day price, and the not-sold line with and without
    its last-seen day; `reason` is None for every call without a verdict."""
    assert words.NO_VERDICT == {
        "no_sale": "No sale today", "new": "New today: no price history yet.",
        "some_stores": "On sale at some stores only", "price_unread": "On sale, but the sale price could not be read",
        "unread_today": "Sale prices could not be read today",
        "mostly_unknown": "On sale most days; earlier sale prices could not be read",
        "no_history": "No price history yet."}
    assert words.not_sold("ramilevy", date(2026, 11, 3)) == "Not sold at Rami Levy today, last seen 3 November"
    assert words.not_sold("ramilevy", None) == "Not sold at Rami Levy today"
    for call in ("too_few", "not_sold", *words.NO_VERDICT):
        assert words.reason(_verdict(call, days=_days_of("9.90"), today="9.90")) is None, call
        with pytest.raises(ValueError, match=call):                    # a badge only for a deal or a no deal
            words.badge(_verdict(call))


def test_the_reason_counts_the_days_with_a_price():
    """S8: the reason names the days it rests on, those with a day price, never the tracked days whose sale price was
    not read; one day is "1 day"."""
    days = _days_of("11.90", None, "11.90", "11.90", on=())
    deal = _verdict(days=days, today="9.90", usual="11.90", saving="2.00", struct={"per": "unit"})
    assert words.reason(deal) == "Usually ₪11.90, sales included (3 days tracked)."
    always = _verdict("no_deal", days=_days_of("9.90", None, "9.90", "10.90"), today="9.90", usual="9.90",
                      saving="0.00", struct={"per": "unit"})
    assert words.reason(always) == "It's been ₪9.90 or less on 2 of the 3 days tracked."
    small = _verdict("no_deal", days=_days_of("5.00", None, "5.00"), today="4.10", usual="5.00", saving="0.90",
                     struct={"per": "unit"})
    assert words.reason(small) == "Only ₪0.90 below its usual ₪5.00 (2 days tracked)."
    one = _verdict(days=_days_of("6.00"), today="4.50", usual="6.00", saving="1.50", struct={"per": "unit"})
    assert words.reason(one) == "Usually ₪6.00, sales included (1 day tracked)."
    assert words.last_low(one) == "Lowest in the 1 day tracked."
    assert words.how_often(_verdict(days=_days_of("6.00", on=[0]))) == "On sale on 1 of the 1 day tracked."
    # a saving above ₪0.00 and below ₪1.00 is the small form; at ₪0.00 or below, the always-on form
    above = _verdict("no_deal", days=_days_of("5.00", "5.00"), today="5.40", usual="5.00", saving="-0.40",
                     struct={"per": "unit"})
    assert words.reason(above) == "It's been ₪5.40 or less on 2 of the 2 days tracked."
    tiny = _verdict("no_deal", days=_days_of("5.00", "5.00"), today="4.99", usual="5.00", saving="0.01",
                    struct={"per": "unit"})
    assert words.reason(tiny) == "Only ₪0.01 below its usual ₪5.00 (2 days tracked)."


def test_how_often_and_the_last_sale():
    """S7: every tracked day counts, unknown prices too; the last sale before this one when today is on sale, the
    last sale when it is not; its price left out when it was not read; nothing with no tracked day."""
    from shopper.verdict import Day
    days = _days_of("9.90", None, "12.90", "12.90", on=[0])
    ended = Day(date(2026, 10, 12), Decimal("12.90"), Decimal("9.90"), True)
    unread = Day(date(2026, 10, 12), Decimal("12.90"), None, True)
    assert words.how_often(_verdict(days=days, sale=ended, on_sale=True)) == (
        "On sale on 2 of the 4 days tracked. The last sale before this one ended 12 October, at ₪9.90.")
    assert words.how_often(_verdict(days=days, sale=ended, on_sale=False)) == (
        "On sale on 2 of the 4 days tracked. The last sale ended 12 October, at ₪9.90.")
    assert words.how_often(_verdict(days=days, sale=unread, on_sale=True)) == (
        "On sale on 2 of the 4 days tracked. The last sale before this one ended 12 October.")
    assert words.how_often(_verdict(days=days, sale=unread)) == (
        "On sale on 2 of the 4 days tracked. The last sale ended 12 October.")
    assert words.how_often(_verdict(days=days)) == "On sale on 2 of the 4 days tracked."
    assert words.how_often(_verdict(days=())) is None                          # never "0 days tracked"


def test_last_this_low_needs_todays_price_and_a_day_price():
    """S6 shows only when today's price is known and a day before today has a day price; never "0 days tracked"."""
    assert words.last_low(_verdict(days=_days_of("9.90"))) is None                        # today unknown
    assert words.last_low(_verdict(days=(), today="9.90")) is None                        # nothing before today
    assert words.last_low(_verdict(days=_days_of(None, None), today="9.90")) is None      # no day price
    assert words.last_low(_verdict(days=_days_of(None, "12.00"), today="9.90")) == "Lowest in the 1 day tracked."


def test_the_badge_rows_words():
    """The plan's "Words this plan adds": each badge under "Elsewhere today" names its store type, then the verdict,
    or the no-verdict line in lower case without its full stop."""
    deal = _verdict(column="ramilevy", today="7.00", usual="8.90", saving="1.90", struct={"per": "unit"})
    assert words.short_badge(deal) == "Rami Levy · DEAL · ₪1.90 off"
    assert words.short_badge(_verdict("no_deal", column="ramilevy", today="8.90", usual="8.90", saving="0.00",
                                      struct={"per": "unit"})) == "Rami Levy · NO DEAL"
    said = {call: words.short_badge(_verdict(call, column="ramilevy")) for call in ("too_few", "not_sold",
                                                                                   *words.NO_VERDICT)}
    assert said == {"too_few": "Rami Levy · too few files today", "not_sold": "Rami Levy · not sold today",
                    "no_sale": "Rami Levy · no sale today", "new": "Rami Levy · new today: no price history yet",
                    "some_stores": "Rami Levy · on sale at some stores only",
                    "price_unread": "Rami Levy · on sale, but the sale price could not be read",
                    "unread_today": "Rami Levy · sale prices could not be read today",
                    "mostly_unknown": "Rami Levy · on sale most days; earlier sale prices could not be read",
                    "no_history": "Rami Levy · no price history yet"}


def test_a_weighed_verdict_is_a_kilograms():
    """The plan's words for weighed products: the saving and the usual price a kilogram's, the condition in
    kilograms."""
    kg = {"per": "kg"}
    deal = _verdict(column="ramilevy", days=_days_of(*["69.90"] * 82), today="50.00", usual="69.90", saving="19.90",
                    struct=kg)
    assert words.badge(deal) == "At Rami Levy: DEAL · ₪19.90 off a kilogram"
    assert words.short_badge(deal) == "Rami Levy · DEAL · ₪19.90 off a kilogram"
    assert words.reason(deal) == "Usually ₪69.90 a kilogram, sales included (82 days tracked)."
    assert words.reason(_verdict("no_deal", days=_days_of("9.90"), today="9.90", usual="9.90", saving="0.00",
                                 struct=kg)) == "It's been ₪9.90 a kilogram or less on 1 of the 1 day tracked."
    assert words.reason(_verdict("no_deal", days=_days_of("9.90"), today="9.50", usual="9.90", saving="0.40",
                                 struct=kg)) == "Only ₪0.40 below its usual ₪9.90 a kilogram (1 day tracked)."
    assert words.conditions(_condition_struct(buy=Decimal("1.500"), per="kg")) == ["When you buy 1.5 kilograms"]


def test_the_conditions_in_shopper_words():
    """Question K's phrases with a capital letter, then the quantity, then the minimum spend; none for a plain
    promotion; never a programme's name (the fold-out's, in the chain's span)."""
    assert words.conditions(_condition_struct()) == []
    assert words.conditions(_condition_struct(restrictions=["other", "chain_card", "club"], programmes=["תו זהב"],
                                              buy=Decimal("3"), min_spend=Decimal("150"))) == [
        "Club members only", "The chain's card holders only", "Some customers only", "When you buy 3",
        "Minimum spend ₪150.00"]


def test_the_store_first_words_say_no_never_phrase_or_we():
    """Every new word, over the calls and forms above: no NEVER phrase, no "we", "our" or "us", no odds word."""
    from shopper.verdict import Day
    sale = Day(date(2026, 10, 12), Decimal("12.90"), Decimal("9.90"), True)
    verdicts = [_verdict(days=_days_of("11.90", None), today="9.90", usual="11.90", saving="2.00",
                         struct={"per": per}, low=sale, sale=sale, on_sale=on_sale)
                for per in ("unit", "kg") for on_sale in (True, False)]
    verdicts += [_verdict("no_deal", days=_days_of("9.90"), today=today, usual="9.90", saving=saving,
                          struct={"per": "unit"}) for today, saving in (("9.90", "0.00"), ("9.50", "0.40"))]
    verdicts += [_verdict(call, days=_days_of("9.90"), today="9.90") for call in ("too_few", "not_sold",
                                                                                   *words.NO_VERDICT)]
    said = [words.ELSEWHERE, words.WORKED_OUT, *words.NO_VERDICT.values(), words.on_day(FRIDAY),
            words.not_sold("osherad", FRIDAY), words.not_sold("osherad", None), words.coming_sale(FRIDAY),
            *words.conditions(_condition_struct(restrictions=list(TARGET_PHRASES), buy=Decimal("2"),
                                                min_spend=Decimal("150")))]
    for found in verdicts:
        said += [words.short_badge(found), *([words.badge(found)] if found.call in ("deal", "no_deal") else [])]
        said += [line for line in (words.reason(found), words.last_low(found), words.how_often(found)) if line]
    for text in said:
        for version in (flatten(text), flatten(strip_tags(text))):
            assert not [phrase for phrase in NEVER if flatten(phrase) in version], text
            assert not PRONOUNS.search(version), text
            assert not [word for word in ODDS_WORDS if flatten(word) in version], text

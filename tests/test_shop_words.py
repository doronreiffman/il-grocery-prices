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
from shopper.columns import COLUMNS
from shopper.history import ColumnDay
from shopper.promotions import RESTRICTIONS
from shopper.verdict import DEAL_MIN, FRONT_LIMIT
from shopper.words import (ALWAYS, ALWAYS_SENTENCE, AT_SOME_STORES, CHAINS_LINE, CREDIT_START, FINE_PRINT, FROM_FIELDS,
                           FROM_TEXT, FRONT_SUBTITLE, FRONT_TITLE, HIRING, METHOD_TITLE, NEVER, ODDS_WORDS,
                           PRICE_NOT_READ, RECORD_TITLE, SITE_NAME, TARGET_PHRASES, as_listed, columns_tested, credit,
                           date_line, date_range, formats_note, last_across, marked_none, no_odds_yet, targets,
                           unreadable)
from shopper.words import (BARCODE, BROWSE_LINK, FOLD_INTRO, NONE_YET, NOT_READ_TODAY, PER, SEARCH_LABEL, STORE_RULES,
                           STORY_HEADING, buy, deal_price, headline, listed_price, minimum_spend, store_lead,
                           store_promotions_line, stores_range)

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
    assert FRONT_TITLE == _quoted(_line(DESIGN, "The public names (Q4)"))[0]
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


def test_the_front_title_and_subtitle_are_the_owners_plain_words():
    """The owner's final framing (2026-11-10, 22:30): the site asks whether a promotion is actually a deal. The title
    is that question; a line under it says what each promotion is checked against, "up to" 3 months (READ_DAYS, 90
    days), since the records start on 1 November 2026 and the 90-day window holds fewer days until late January."""
    assert FRONT_TITLE == _quoted(_line(DESIGN, "The public names (Q4)"))[0] == "Is it actually a deal?"
    assert FRONT_SUBTITLE == "Promotions checked against up to 3 months of shelf prices."
    assert f'"{FRONT_SUBTITLE}"' in DESIGN


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
    slugs = list(CHAIN_NAMES)
    return [SITE_NAME, CHAINS_LINE, FRONT_TITLE, FRONT_SUBTITLE, METHOD_TITLE, RECORD_TITLE,
            ALWAYS_SENTENCE, FROM_FIELDS, FROM_TEXT, FINE_PRINT, PRICE_NOT_READ, AT_SOME_STORES,
            *TARGET_PHRASES.values(), *(name for name, _ in HIRING), formats_note(), columns_tested(9),
            columns_tested(1), credit(FRIDAY, "12:03"), date_line(FRIDAY), marked_none(slugs), marked_none(["shufersal"]),
            targets(list(TARGET_PHRASES)), targets(["club", "other"]),
            *(text for column in COLUMNS for text in (no_odds_yet(column.key), last_across(column.key, FRIDAY),
                                                      as_listed([column.key]), headline(column.key, 1130, 4210),
                                                      headline(column.key, 1, 1), headline(column.key, 0, 0),
                                                      store_promotions_line(column.key, 1840, 6210),
                                                      store_promotions_line(column.key, 1, 1))),
            as_listed([column.key for column in COLUMNS]), *(unreadable(slug) for slug in slugs),
            listed_price(Decimal("11.90")), deal_price(Fraction(1), "unit"), deal_price(Fraction(1), "kg"),
            buy(Decimal(3)), stores_range(Decimal(1), Decimal(2)), minimum_spend(Decimal(150)), BROWSE_LINK,
            BARCODE, SEARCH_LABEL, FOLD_INTRO, NONE_YET, NOT_READ_TODAY, STORY_HEADING, *STORE_RULES]


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


# Store first (q33): a store type's front page (docs/store-first.md, "What a visitor sees" 4 and "Words"; the plan's
# "Words this plan adds", provisional until the owner's read)

def _column_day(record=True, promo_hole=False) -> ColumnDay:
    return ColumnDay(column="shufersal-sheli", slug="shufersal", day=FRIDAY, present=True, hole=not record,
                     promo_hole=promo_hole, promotions_error=None, included=20, with_file=20 if record else 5,
                     counted=20 if record else 5, promo_files=5 if promo_hole else 20)


def test_the_store_pages_words():
    """The design's front headline, search box and fold-out line verbatim; the plan's forms: the headline's noun always
    plural, its verb by N, "no promotions to check" when M is none, thousands separated; the store type's promotions
    line; the story's heading; "None yet", the design's "existing lead line"; the promotion hole's line, the no-verdict
    line with its full stop; and the fold-out's rules, pinned, with the code's own constants."""
    assert [headline("carrefour-market", 1130, 4210)] == _table("Front headline")
    assert headline("shufersal-sheli", 1, 3) == "At Shufersal Sheli today: 1 of 3 promotions is actually a deal."
    assert headline("shufersal-sheli", 0, 3) == "At Shufersal Sheli today: 0 of 3 promotions are actually deals."
    assert headline("shufersal-sheli", 2, 2) == "At Shufersal Sheli today: 2 of 2 promotions are actually deals."
    assert headline("ramilevy", 0, 0) == "At Rami Levy today: no promotions to check."
    assert headline("ramilevy", 1_234, 21_973) == "At Rami Levy today: 1,234 of 21,973 promotions are actually deals."
    assert f'the search box ("{SEARCH_LABEL}")' in STORE_FIRST and SEARCH_LABEL == "Type a product name or the barcode"
    assert ["How a deal passes", FOLD_INTRO] == _table("Front fold-out")
    assert store_promotions_line("shufersal-sheli", 1840, 6210) == (
        "Today Shufersal Sheli lists 1,840 promotions carried by at least half its stores, on 6,210 products.")
    assert store_promotions_line("ramilevy", 1, 1) == (
        "Today Rami Levy lists 1 promotion carried by at least half its stores, on 1 product.")
    assert STORY_HEADING == "One of today's deals"
    assert NONE_YET == "None yet: a product needs 20 days of price history first." and f'"{NONE_YET}"' in STORE_FIRST
    assert NOT_READ_TODAY == words.NO_VERDICT["unread_today"] + "." == "Sale prices could not be read today."
    assert (DEAL_MIN, FRONT_LIMIT) == (Decimal("1.00"), 100)
    assert STORE_RULES == (
        "A promotion is checked when at least half of the store type's stores that sent price files today carry it "
        "and its sale price could be read.",
        "The product needs a listed price there on at least 20 of the 30 days before today.",
        "What it usually costs is the middle of its day prices over the days tracked in the 90 days before today: each "
        "day, the lower of its listed price and its sale price that day, so sales are included.",
        "It is a deal when today's price is at least ₪1.00 below what it usually costs; a promotion for club members "
        "or for buying 2 counts too, its condition from the chain's fields named beside it.",
        "A day is tracked when the store type's prices and promotions were both read that day; a day not read is left "
        "out, never filled in.",
        "Deals are listed by the shekels saved, biggest first; the top 100 are shown, and every other product is a "
        "search away.")


def test_the_store_pages_lead_line():
    """`store_lead`, the first that applies: a hole today (prices from too few files) says the too-few line; a
    promotion hole, that sale prices could not be read; a store type without 20 days of records in the 30, "None
    yet"; else the headline over the front's rows, all of them, and its checked."""
    from shopper.pages import StoreFront
    front = StoreFront("shufersal-sheli", True, (), 3, 1840, 6210)
    assert store_lead(front, _column_day()) == "At Shufersal Sheli today: 0 of 3 promotions are actually deals."
    assert store_lead(front, _column_day(record=False)) == "too few files today: 5 of 20 stores"
    assert store_lead(front, _column_day(record=False, promo_hole=True)) == "too few files today: 5 of 20 stores"
    assert store_lead(front, _column_day(promo_hole=True)) == NOT_READ_TODAY
    unready = StoreFront("shufersal-sheli", False, (), 3, 1840, 6210)
    assert store_lead(unready, _column_day()) == NONE_YET
    assert store_lead(unready, _column_day(promo_hole=True)) == NOT_READ_TODAY

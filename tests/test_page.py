"""The words and the pages: the headline, the credit line, the index and method pages, the day's JSON."""
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from html import unescape
from pathlib import Path

import pytest

from basket.barcode import normalize
from basket.basket_file import load_basket
from basket.chains import SLUGS
from basket.extract import ExtractReport
from basket.page import build_site, render_day, render_index, render_method
from basket.record import build_record, public_day
from basket.rules import ChainPrice, Headline, LeftOut, chain_day, price_basket
from basket.stores import Store
from basket.words import (ALWAYS, MEDIAN_SENTENCE, NEVER, REVISED, TITLE, bar_label, credit, headline_lines,
                          left_out_line, range_note, revised_line, too_few)

BASKET = load_basket(Path(__file__).parent / "baskets" / "basket-test.json", min_items=1)
MILK, PASTA, EGGS = (item.code for item in BASKET.items)  # 1000 gml, 500 gml, 12 unit
DAY = date(2026, 11, 2)
BUILT = datetime(2026, 11, 2, 9, 30, tzinfo=timezone.utc)
# (included stores, stores with a file): Osher Ad has too few files (1 of 24) and is out of the ranking (B8).
STORES = {"shufersal": (320, 318), "ramilevy": (60, 58), "osherad": (24, 1), "carrefour": (100, 96),
          "yochananof": (40, 40)}
# (median, low, high, stores listing it) per chain and code. Totals of MILK and PASTA: Rami Levy 12.00,
# Yochananof 12.30, Shufersal 13.50, Carrefour 14.85 (24% more). PASTA ties at 6.10 (Rami Levy, Yochananof).
# EGGS is left out: Carrefour's 40 of 96 is under half (B6). Osher Ad's prices are the lowest but count nowhere.
PRICES = {
    "shufersal": {MILK: ("6.50", "5.90", "7.20", 300), PASTA: ("7.00", "6.50", "7.90", 310),
                  EGGS: ("12.90", "12.00", "13.50", 290)},
    "ramilevy": {MILK: ("5.90", "5.50", "6.40", 55), PASTA: ("6.10", "6.00", "6.30", 56),
                 EGGS: ("11.90", "11.90", "11.90", 50)},
    "osherad": {MILK: ("5.00", "5.00", "5.00", 1), PASTA: ("6.00", "6.00", "6.00", 1),
                EGGS: ("11.00", "11.00", "11.00", 1)},
    "carrefour": {MILK: ("6.90", "6.50", "7.50", 91), PASTA: ("7.95", "7.90", "8.20", 90),
                  EGGS: ("13.90", "13.90", "13.90", 40)},
    "yochananof": {MILK: ("6.20", "6.20", "6.20", 40), PASTA: ("6.10", "6.10", "6.10", 40),
                   EGGS: ("12.50", "12.50", "12.50", 39)},
}
BE = [Store("601", "5", "בי באר שבע", "1"), Store("602", "5", "בי חיפה", "1"), Store("603", "5", "בי אילת", "1")]
EXCLUSIONS = {"shufersal": [*BE, Store("413", "7", "שופרסל ONLINE", "2")],
              "ramilevy": [Store("39", None, "מרלוג אינטרנט", "2")],
              "osherad": [],
              "carrefour": [Store("471", "1", "קרפור אונליין", "2")],
              "yochananof": []}
RTL = '<span dir="rtl" lang="he">'


def a_public(prices: dict = PRICES, stores: dict = STORES, double_coded: dict[str, int] | None = None) -> dict:
    """The public day the rules and the record give for `prices` and `stores` (`public_day(build_record(...))`)."""
    days = [chain_day(slug, *stores[slug]) for slug in SLUGS]
    found = {(slug, normalize(code)): ChainPrice(Decimal(median), Decimal(low), Decimal(high), listing,
                                                 (double_coded or {}).get(slug, 0) if code == MILK else 0)
             for slug, items in prices.items() for code, (median, low, high, listing) in items.items()}
    result = price_basket(BASKET, days, found, {})
    reports = {slug: ExtractReport(slug=slug, day=DAY.isoformat(), files=[], skipped=[], stores=stores[slug][1],
                                   rows=0, unreadable_prices=0, repeated=0, conflicting=0) for slug in SLUGS}
    record = build_record(DAY, BASKET, result, days, {slug: () for slug in SLUGS}, reports,
                          {slug: 0 for slug in SLUGS}, {slug: () for slug in SLUGS}, "093000Z-basket-0a1b",
                          "0123456789ab", BUILT, "11:00")
    return public_day(record)


def with_prices(**changes: dict[str, tuple[str, str, str, int]]) -> dict:
    """PRICES with some chains' items replaced."""
    return {slug: PRICES[slug] | changes.get(slug, {}) for slug in PRICES}


def index(public: dict | None = None) -> str:
    return render_index(public or a_public(), BASKET, EXCLUSIONS)


def method(public: dict | None = None) -> str:
    return render_method(BASKET, EXCLUSIONS, public or a_public())


def visible(page: str) -> str:
    """The page's text as a reader sees it: tags dropped, entities read, spaces collapsed, lower case."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", page)).split()).lower()


def cells(page: str) -> dict[str, dict[str, set[str]]]:
    """Per table row (by code), per chain: the cell's classes."""
    rows = re.findall(r'<tr data-code="(\d+)"[^>]*>(.*?)</tr>', page, re.DOTALL)
    return {code: {chain: set(classes.split()) for chain, classes in
                   re.findall(r'<td data-chain="(\w+)"(?: class="([^"]*)")?>', row)} for code, row in rows}


def bar_rows(page: str) -> dict[str, str]:
    """Per chain: its entry in the list of totals."""
    return dict(re.findall(r'<li data-chain="(\w+)"[^>]*>(.*?)</li>', page, re.DOTALL))


# ---- the words ----

def test_headline_lines_exact():
    headline = Headline("ramilevy", Decimal("312.45"), "carrefour", Decimal("398.10"), 27)
    assert headline_lines(headline, 30, date(2026, 11, 2)) == (
        "Lowest listed total today: Rami Levy, ₪312.45.",
        "Highest: Carrefour, ₪398.10, 27% more. 30 everyday items, listed shelf prices before promotions, "
        "from the chains' price files of Monday 2 November 2026.")
    unrounded = Headline("osherad", Decimal("12.405"), "shufersal", Decimal("13.6"), 10)  # exact sums of medians
    first, second = headline_lines(unrounded, 2, date(2026, 11, 3))
    assert first == "Lowest listed total today: Osher Ad, ₪12.41."
    assert second.startswith("Highest: Shufersal, ₪13.60, 10% more. 2 everyday items")
    assert second.endswith("price files of Tuesday 3 November 2026.")


def test_headline_without_comparison():
    items = "3 everyday items, listed shelf prices before promotions, from the chains' price files of Monday 2 November 2026."
    assert headline_lines(None, 3, DAY) == (
        "No comparison today: fewer than three chains published enough files.", items)
    assert headline_lines(None, 3, DAY, nothing_counted=True) == (
        "No comparison today: no basket item passed the day's checks.", items)


def test_index_with_fewer_than_three_chains_in_the_ranking_says_so_and_shows_no_totals():
    thin = STORES | {"carrefour": (100, 10), "yochananof": (40, 5)}  # two chains left in the ranking
    public = a_public(stores=thin)
    assert public["chains"]["ramilevy"]["total"] == "23.90" and public["headline"] is None
    page = index(public)
    assert "No comparison today: fewer than three chains published enough files." in page
    assert "3 everyday items, listed shelf prices before promotions" in page  # the table's rows
    assert "<svg" not in page and "₪23.90" not in page and "<tfoot>" not in page  # no bars, no totals
    assert "₪5.90" in page  # the table still shows each price
    assert not any("low" in classes for row in cells(page).values() for classes in row.values())
    assert too_few(10, 100) in bar_rows(page)["carrefour"]
    assert bar_label(58) in bar_rows(page)["ramilevy"]


def test_index_when_no_item_counts_says_so_and_shows_no_totals():
    short = {slug: {code: (median, low, high, 1) for code, (median, low, high, _) in items.items()}
             for slug, items in PRICES.items()}  # one store lists each item: every item fails coverage (B6)
    public = a_public(prices=short)
    assert public["items_in"] == [] and all(chain["total"] is None for chain in public["chains"].values())
    page = index(public)
    assert "No comparison today: no basket item passed the day's checks." in page
    assert "3 everyday items, listed shelf prices before promotions" in page
    assert "<svg" not in page and "<tfoot>" not in page and 'class="total"' not in page
    assert "₪5.90" in page


def test_credit_line_exact():
    assert credit(date(2026, 11, 2), "11:00") == (
        "Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish under "
        "section 30 of the Food and Pharma Competition Promotion Law, 2014: the files of 2 November 2026, "
        "collected by 11:00 Israel time. Listed prices, not a promise of what a till charges. Not shopping advice.")
    assert "the files of 9 November 2026, collected by 09:47 Israel time." in credit(date(2026, 11, 9), "09:47")


def test_small_labels_exact():
    assert bar_label(92) == "from 92 stores' files"
    assert range_note("3.90", "4.20", 91, 96) == "stores ₪3.90 to ₪4.20, 91 of 96 list it"
    assert too_few(1, 24) == "too few files today: 1 of 24 stores"


def test_left_out_lines_name_the_item_the_chains_and_the_counts_or_sizes():
    assert left_out_line(LeftOut(EGGS, "coverage", {"carrefour": "40 of 96", "shufersal": "100 of 318"}), BASKET) == (
        "Test eggs ×12: left out today; fewer than half the stores with a file list it at Carrefour (40 of 96) "
        "and Shufersal (100 of 318).")
    assert left_out_line(LeftOut(PASTA, "size", {"ramilevy": "450 gml"}), BASKET) == (
        "Test pasta 500 g: left out today; the size in the files differs from the basket's 500 g/ml: "
        "Rami Levy 450 g/ml.")
    assert left_out_line(LeftOut(EGGS, "size", {"carrefour": "10 unit", "osherad": "6 unit", "ramilevy": "500 gml"}),
                         BASKET).endswith("basket's 12 units: Carrefour 10 units, Osher Ad 6 units and Rami Levy 500 g/ml.")
    with pytest.raises(ValueError, match="'price'"):
        left_out_line(LeftOut(EGGS, "price", {}), BASKET)


# ---- the index page ----

def test_index_has_always_words_and_no_never_words():
    for public in (a_public(), a_public(stores=STORES | {"carrefour": (100, 10), "yochananof": (40, 5)})):
        page = index(public)
        for phrase in ALWAYS:
            assert phrase in page, phrase
        for page_ in (page, method(public)):
            for phrase in NEVER:
                assert phrase not in page_.lower() and phrase not in visible(page_), phrase
            assert REVISED not in page_
            assert not re.search(r"\b(we|our|us)\b", visible(page_))
    page = index()
    assert "Lowest listed total today: Rami Levy, ₪12.00." in page
    assert ("Highest: Carrefour, ₪14.85, 24% more. 2 everyday items, listed shelf prices before promotions, "
            "from the chains' price files of Monday 2 November 2026.") in page
    assert f"<title>{TITLE}</title>" in page and f"<h1>{TITLE}</h1>" in page
    assert MEDIAN_SENTENCE in page


def test_every_page_has_noindex_credit_one_style_and_no_script():
    the_credit = credit(DAY, "11:00")
    for page in (index(), method()):
        assert page.startswith("<!doctype html>\n<html lang=\"en\">")
        assert '<meta charset="utf-8">' in page
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
        assert '<meta name="robots" content="noindex">' in page
        assert page.count("<style>") == 1 and page.count("<style") == 1
        assert "<script" not in page.lower()
        footer = re.search(r"<footer>(.*?)</footer>", page, re.DOTALL)
        assert footer and the_credit in footer.group(1)
        assert '<a href="method.html">' in footer.group(1)
    assert '<a href="index.html">' in method()


def test_lowest_marked_per_row():
    table = cells(index())
    assert list(table) == [MILK, PASTA, EGGS]  # the basket's order
    assert list(table[MILK]) == ["ramilevy", "yochananof", "shufersal", "carrefour", "osherad"]  # by rank
    low = {code: sorted(chain for chain, classes in row.items() if "low" in classes) for code, row in table.items()}
    # Osher Ad's 5.00 and 6.00 are lower still, but it is out of the ranking; EGGS counts in no total.
    assert low == {MILK: ["ramilevy"], PASTA: ["ramilevy", "yochananof"], EGGS: []}


def test_chain_out_of_ranking_is_marked_and_has_no_bar():
    page = index()
    bars = bar_rows(page)
    assert list(bars) == ["ramilevy", "yochananof", "shufersal", "carrefour", "osherad"]
    assert "<svg" not in bars["osherad"] and "₪" not in bars["osherad"]
    assert too_few(1, 24) in bars["osherad"]
    for slug, (_, with_file) in STORES.items():
        if slug != "osherad":
            assert "<svg" in bars[slug] and bar_label(with_file) in bars[slug]
    assert page.count("<svg") == 4
    assert all("out" in cells(page)[code]["osherad"] for code in (MILK, PASTA, EGGS))
    assert not any("out" in classes for code in (MILK, PASTA, EGGS)
                   for chain, classes in cells(page)[code].items() if chain != "osherad")
    assert "Osher Ad: too few files today: 1 of 24 stores. Its prices are shown, marked †, and count in no total." in page


def test_an_item_a_chain_does_not_list_says_so():
    prices = PRICES | {"osherad": {code: price for code, price in PRICES["osherad"].items() if code != EGGS}}
    page = index(a_public(prices=prices))
    assert '<td data-chain="osherad" class="out">not listed</td>' in page
    assert cells(page)[EGGS]["osherad"] == {"out"}


def test_bars_are_scaled_to_the_highest_total_and_ties_share_a_rank():
    page = index(a_public(prices=with_prices(yochananof={MILK: ("5.90", "5.90", "5.90", 40)})))  # 12.00, as Rami Levy
    bars = bar_rows(page)
    widths = {slug: re.search(r'<rect class="fill" width="([\d.]+)"', row).group(1)
              for slug, row in bars.items() if "<svg" in row}
    assert widths == {"ramilevy": "80.81", "yochananof": "80.81", "shufersal": "90.91", "carrefour": "100.00"}
    ranks = {slug: re.search(r'<span class="rank">(\d+)</span>', row).group(1) for slug, row in bars.items()
             if "<svg" in row}
    assert ranks == {"ramilevy": "1", "yochananof": "1", "shufersal": "3", "carrefour": "4"}
    assert "Lowest listed total today: Rami Levy, ₪12.00." in page  # the headline names one of the two
    assert "₪14.85" in bars["carrefour"] and bar_label(96) in bars["carrefour"]


def test_range_note_wide_range_renders():
    assert range_note("0.10", "10000.00", 1, 96) == "stores ₪0.10 to ₪10000.00, 1 of 96 list it"
    page = index(a_public(prices=with_prices(carrefour={MILK: ("6.90", "0.10", "10000.00", 91)})))
    assert "stores ₪0.10 to ₪10000.00, 91 of 96 list it" in page  # as the files give it, never clipped
    assert range_note("5.50", "6.40", 55, 58) in index()


def test_notes_name_the_left_out_items_the_stores_and_the_median_sentence():
    page = index()
    notes = re.search(r'<section class="notes">(.*?)</section>', page, re.DOTALL).group(1)
    assert left_out_line(LeftOut(EGGS, "coverage", {"carrefour": "40 of 96"}), BASKET) in notes
    assert ("Shufersal: files from 318 of its 320 stores; left out by rule: 3 stores of the Be sub-chain and "
            f"store 413 “{RTL}שופרסל</span> ONLINE”.") in notes
    assert f"Rami Levy: files from 58 of its 60 stores; left out by rule: store 39 “{RTL}מרלוג אינטרנט</span>”." in notes
    assert "Osher Ad: files from 1 of its 24 stores; no store left out by rule." in notes
    assert MEDIAN_SENTENCE in notes
    assert "under two codes" not in notes  # no store double-coded an item


def test_double_coded_stores_named_only_when_any():
    page = index(a_public(double_coded={"ramilevy": 2, "carrefour": 1}))
    assert ("An item a store listed under two codes counts once there, at the lower price; this happened "
            "2 times at Rami Levy and 1 time at Carrefour.") in page  # the chains in the page's order


def test_revised_line_shown_only_when_revised():
    assert REVISED not in index()
    public = a_public()
    first = {"carrefour": "14.85", "osherad": None, "ramilevy": "12.00", "shufersal": "13.50", "yochananof": "12.30"}
    public["revisions"] = [{"run_id": "093000Z-basket-0a1b", "code_sha": "0123456789ab",
                            "built_at": "2026-11-02T09:30:00+00:00", "totals": first}]
    public["revised"] = {"on": "2026-11-03", "reason": "a parser fix"}
    line = ("Revised on 3 November 2026: a parser fix. First published: Rami Levy ₪12.00, Yochananof ₪12.30, "
            "Shufersal ₪13.50, Carrefour ₪14.85.")
    assert revised_line(date(2026, 11, 3), "a parser fix", first) == line
    assert line in index(public)
    assert revised_line(date(2026, 11, 3), "a fix", {"carrefour": "101.20", "ramilevy": "99.50"}).endswith(
        "First published: Rami Levy ₪99.50, Carrefour ₪101.20.")  # by amount, not as text
    assert revised_line(date(2026, 11, 3), "a rule fix", {"osherad": None}) == (
        "Revised on 3 November 2026: a rule fix. First published: no totals.")


# ---- the method page and the day's JSON ----

def test_method_page_lists_every_item_and_exclusion():
    page = method()
    table = re.search(r'<table class="basket">(.*?)</table>', page, re.DOTALL).group(1)
    for item, size in zip(BASKET.items, ("1000 g/ml", "500 g/ml", "12 units")):
        row = re.search(rf"<tr>\s*<td>{item.code}</td>(.*?)</tr>", table, re.DOTALL).group(1)
        assert item.name_en in row and f"{RTL}{item.name_he}</span>" in row
        assert size in row and item.category in row
    for store in BE:
        assert f"{RTL}{store.name}</span>" in page
    assert "3 stores of the Be sub-chain" in page
    assert f"store 413 “{RTL}שופרסל</span> ONLINE”" in page
    assert f"store 39 “{RTL}מרלוג אינטרנט</span>”" in page
    assert f"store 471 “{RTL}קרפור אונליין</span>”" in page
    assert "Osher Ad: none." in page and "Yochananof: none." in page
    for rule in range(1, 13):
        assert f"<b>B{rule} " in page
    for heading in ("What this page does not claim", "To reproduce this number"):
        assert f"<h2>{heading}</h2>" in page
    assert "section 30 of the Food and Pharma Competition Promotion Law, 2014" in page
    assert "A different basket gives a different order." in page
    assert '<a href="days/2026-11-02.json">days/2026-11-02.json</a>' in page
    assert "0123456789ab" in page  # the code's fingerprint, from the day


def test_hebrew_names_are_rtl():
    for page in (index(), method()):
        for item in BASKET.items:
            assert f"{RTL}{item.name_he}</span>" in page
        outside = re.sub(rf"{RTL}[^<]*</span>", "", page)
        assert not re.search(r"[\u0590-\u05FF]", outside)  # no Hebrew outside a right-to-left span


def test_day_json_is_the_public_dict():
    public = a_public()
    text = render_day(public)
    assert text == json.dumps(public, sort_keys=True, indent=1, ensure_ascii=False)
    assert json.loads(text) == public


def test_build_site_writes_marker_and_day_file_only_when_asked(tmp_path):
    public = a_public()
    site = tmp_path / "site"
    build_site(public, BASKET, EXCLUSIONS, site, write_day=False)
    assert (site / "index.html").read_text(encoding="utf-8") == index(public)
    assert (site / "method.html").read_text(encoding="utf-8") == method(public)
    assert (site / ".basket-site").read_bytes() == b""
    assert not (site / "days").exists()
    build_site(public, BASKET, EXCLUSIONS, site, write_day=True)
    day_file = site / "days" / "2026-11-02.json"
    assert day_file.read_text(encoding="utf-8") == render_day(public)
    day_file.write_text("published earlier", encoding="utf-8")
    build_site(public, BASKET, EXCLUSIONS, site, write_day=False)
    assert day_file.read_text(encoding="utf-8") == "published earlier"  # left as it is

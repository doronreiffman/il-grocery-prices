"""The dbt layer on the golden 90 days (docs/dbt-layer.md, section 4, "The weakness of format: sql, and its cover"): the
golden's synthetic files of tests/shopper_golden.py, extracted by the project's own Python
(`shopper.extract.extract_chain_day`), and the whole dbt project built on the tables that gives. No table here is typed
by hand. The models must give the values the golden works by hand in its docstring ("The verdicts", "The basket"),
the verdicts among them those tests/test_golden_90.py's `test_the_golden_verdicts` asserts of the Python.

The days. The golden's files of `GOLDEN_DAYS` are written: day 1 (1 January 2026) for the store lists, which hold for
every later day but Shufersal's, and days 92 to 120 (2 to 30 April), Shufersal's list of day 92 naming Universe's
three stores. Shufersal is extracted on each of its 29 days, 92 to 120, the four other chains on day 120 alone: 33
chain-days. So Universe's whole history is here, and every chain's 30 April.

The published files are synthetic too (`published`): the numbers the golden's docstring works by hand, in the fields
the dbt sources read, laid out as the site lays them out, for the comparisons with the published files to read. Two of
their store-type and chain days are not what the golden build gives, each a known difference (`GOLDEN_VARS`), and the
basket's day file of 29 April gives the four chains with no table that day wrong figures, which no comparison may read.

The build (`clean`) is `dbt build` with the unit tests left out, on its own temporary database and folders
(tests/dbt_run.py), its vars (`GOLDEN_VARS`) the golden's folders and its two known differences.

The data tests (docs/dbt-layer.md, section 3) pass on the clean build, and each is proved to fail on bad rows of its
own: `plant_bad_rows` breaks a copy of the golden's tables, each bad row one clause of one test, and the bad-rows build
(`bad`) must give each data test exactly its count (`EXPECTED_BAD`), so a weakened rule shows as a count that moved.
"""
import json
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from basket.barcode import is_gs1
from basket.chains import SLUGS
from collector.names import FileName, parse_file_name
from collector.store import published_name
from dbt_run import DbtRun, query, run_dbt
from shopper.extract import extract_chain_day
from shopper_golden import G1, G2, G3, G4, G5, G6, U1, U2, U3, U4, U5, U6, U7, U8, day_of, write_basket, write_day
from test_build import CHAIN_IDS
from test_dbt_project import OWNER_S_FOUR

GOLDEN_DAYS = (1, *range(92, 121))      # day 1 for the store lists; Shufersal's last 29 days, 92 to 120
SHUFERSAL_DAYS = range(92, 121)          # the days Shufersal is extracted; the four other chains are on LAST alone
LAST = 120                               # 30 April 2026, the golden's last day
D = Decimal
# The owner's reasons for the four known differences (2026-11-25), each whole as dbt/dbt_project.yml's folded text
# gives it; tests/test_dbt_project.py holds their kind, key and day (OWNER_S_FOUR), not their words.
WEIGHED = ("published before the 22 November fix to weighed N for ₪M prices; that chain's items tables of 1 to 22 "
           "November were written again after it")
SLOW_MORNING = ("published from 171 Shufersal stores' files, the slow morning's; that day's prices table was rebuilt "
                "later from 416")


@dataclass(frozen=True)
class Golden:
    """The golden's folders: the tables the extraction wrote, the synthetic published files, the basket's file."""
    tables: Path
    site: Path
    basket_file: Path


def front(deals: int, checked: int, promotions: int | None, products: int | None,
          rows: tuple[tuple[str, str, str, str, int], ...] = ()) -> dict:
    """A store type's block in a site-day file, as src/shopper/siteday.py's `_column` writes the fields the dbt source
    reads: N (`deals`), M (`checked`), the promotions line's promotions and products (None on a hole or a promotion
    hole) and the rows shown, each (barcode, today's price, the usual price, the saving, its days with a day price)."""
    return {"front": {"deals": deals, "checked": checked, "promotions": promotions, "products": products,
                      "rows": [{"barcode": code, "today": today, "usual": usual, "saving": saving, "days": days}
                               for code, today, usual, saving, days in rows]}}


def basket_item(median: str, low: str, high: str, listing: int, double_coded: int = 0) -> dict:
    """An item of a chain in a basket day file, as src/basket/record.py writes it: money as text, two places."""
    return {"median": median, "low": low, "high": high, "listing": listing, "double_coded": double_coded}


def basket_chain(total: str, g6: tuple[str, str, str], stores: int) -> dict:
    """A chain's block in a basket day file: G1 at 5.00 and G2 at 2.50 at every store, G6 as given, its total."""
    return {"total": total, "items": {G1: basket_item("5.00", "5.00", "5.00", stores),
                                      G2: basket_item("2.50", "2.50", "2.50", stores), G6: basket_item(*g6, stores)}}


def publish(site: Path, folder: str, body: dict) -> None:
    """Write `body` as `<folder>/<its day>.json` under `site`, keys sorted, as `basket.page.render_day` writes the
    basket's day files and the site-day files alike."""
    (site / folder).mkdir(parents=True, exist_ok=True)
    (site / folder / f"{body['day']}.json").write_text(json.dumps(body, sort_keys=True, indent=1, ensure_ascii=False),
                                                       encoding="utf-8")


# The rows Universe's front shows on 30 April, by saving ("The verdicts", Universe, day 120), each with the days its
# reason rests on.
UNIVERSE_SHOWN = ((U2, "6.90", "8.90", "2.00", 27), (U3, "7.90", "9.90", "2.00", 26), (U8, "4.50", "6.00", "1.50", 27),
                  (U7, "4.00", "5.00", "1.00", 27))
# A basket day's figures for a chain with no prices table that day, wrong on purpose: no comparison may read them.
NO_TABLE = {"total": "0.30", "items": {code: basket_item("0.10", "0.10", "0.10", 9) for code in (G1, G2, G6)}}


def published(site: Path) -> None:
    """The synthetic published files under `site`: the fields the dbt sources read, laid out as the site lays them
    out, the numbers from the golden's docstring but where said:

    - `site-days/2026-04-30.json`: Shufersal Universe's front ("The verdicts", Universe, day 120): the front list's 4
      deals of the 6 checked, its rows U2, U3, U8 and U7 by saving, each with the days its reason rests on; and the 9
      promotions on 9 products of the promotions line, Universe's promotions running on day 120 at its three stores
      (60 and 62 to 68 and 70; 69 at store 81 alone does not count). Shufersal Deal's front: no promotion runs there
      on day 120 (G1's run of 110 to 116 and G5's promotion 50 of 99 to 106 have ended), so 0 of 0 and 0 promotions.
      Shufersal Sheli's front as the full golden's 90 days give it ("The verdicts", G3 at Sheli, day 120): 1 deal of
      1, G3 3.00 off its usual 10.90 over 90 days, its promotion 30 on one product. The golden build reads Shufersal's
      last 29 days alone, on all of which G3 is on sale at 7.90, so it gives 0 of 1: a known difference.
    - `days/2026-04-30.json`: each chain's G1, G2 and G6 ("The basket": G6 the median of the chain's stores, G1 and G2
      one price at every store) and its total, Osher Ad 14.70, Rami Levy 15.00, Shufersal 15.10 and Carrefour 15.80;
      Yochananof's G6 published at 7.80, its total 15.30, where its two stores' 7.80 and 8.00 give 7.90: a known
      difference.
    - `days/2026-04-29.json`: Shufersal's figures, the same as on 30 April (its five stores outside Universe list the
      basket at the same prices every day), and the four other chains' wrong on purpose (NO_TABLE): they have no prices
      table that day.
    """
    day = day_of(LAST).isoformat()
    publish(site, "site-days", {"day": day, "columns": {
        "shufersal-universe": front(4, 6, 9, 9, UNIVERSE_SHOWN),
        "shufersal-deal": front(0, 0, 0, 0),
        "shufersal-sheli": front(1, 1, 1, 1, ((G3, "7.90", "10.90", "3.00", 90),))}})
    shufersal = basket_chain("15.10", ("7.60", "7.00", "8.20"), 5)
    publish(site, "days", {"day": day, "items_in": [G1, G2, G6], "chains": {
        "shufersal": shufersal,
        "ramilevy": basket_chain("15.00", ("7.50", "7.40", "7.60"), 2),
        "osherad": basket_chain("14.70", ("7.20", "7.10", "7.30"), 2),
        "carrefour": basket_chain("15.80", ("8.30", "7.90", "8.60"), 5),
        "yochananof": basket_chain("15.30", ("7.80", "7.80", "8.00"), 2)}})
    publish(site, "days", {"day": day_of(LAST - 1).isoformat(), "items_in": [G1, G2, G6], "chains": {
        "shufersal": shufersal, **{slug: NO_TABLE for slug in SLUGS if slug != "shufersal"}}})


@pytest.fixture(scope="module")
def golden(tmp_path_factory) -> Golden:
    """The golden's files of GOLDEN_DAYS, the tables of its 33 chain-days extracted from them, the synthetic published
    files and the golden basket."""
    root = tmp_path_factory.mktemp("dbt-golden")
    raw, tables, site = root / "raw", root / "tables", root / "site"
    for n in GOLDEN_DAYS:
        write_day(raw, n)
    for n in SHUFERSAL_DAYS:
        extract_chain_day(raw, "shufersal", day_of(n), tables)
    for slug in SLUGS:
        if slug != "shufersal":
            extract_chain_day(raw, slug, day_of(LAST), tables)
    published(site)
    return Golden(tables, site, write_basket(root / "basket.json"))


def known(kind: str, key: str, n: int, reason: str) -> dict:
    """An entry of the var known_differences: a published day of day n today's tables no longer give, and why."""
    return {"kind": kind, "key": key, "day": day_of(n).isoformat(), "reason": reason}


# The golden's two known differences (`published`), each with its reason.
GOLDEN_KNOWN = (
    known("store_page", "shufersal-sheli", LAST, "published from the full golden's 90 days; the golden build reads "
                                                 "Shufersal's last 29 days alone, which give 0 of 1"),
    known("basket", "yochananof", LAST, "published at 7.80 for G6 on purpose, where the golden's two stores give 7.90"),
)


@pytest.fixture(scope="module")
def GOLDEN_VARS(golden) -> dict:
    """The golden build's vars: the golden's folders and its two known differences (GOLDEN_KNOWN). A fixture, as the
    folders are the module's temporary ones; named as the plan names it. The dict is shared by every test in the
    module: a test that needs another list copies it (`[*GOLDEN_VARS["known_differences"], ...]`), never changes it in
    place."""
    return {"tables": str(golden.tables), "site": str(golden.site), "basket_file": str(golden.basket_file),
            "known_differences": list(GOLDEN_KNOWN)}


@pytest.fixture(scope="module")
def clean(GOLDEN_VARS, tmp_path_factory):
    """Every model built on the golden's tables and every data test run on them, the unit tests left out."""
    return run_dbt(["build", "--exclude", "test_type:unit"], tmp_path_factory.mktemp("clean"), GOLDEN_VARS)


def _nodes(run, kind: str) -> set[str]:
    """The names of the project's nodes of a resource type, from the run's manifest."""
    return {node["name"] for node in run.manifest["nodes"].values() if node["resource_type"] == kind}


def test_the_clean_build_succeeds(clean):
    """The build exits 0, every model of the project built and every data test passed."""
    assert clean.code == 0, clean.output
    models, data_tests = _nodes(clean, "model"), _nodes(clean, "test")
    assert len(models) == 14
    status = {name: clean.results.get(name, ("not run", None))[0] for name in models | data_tests}
    assert status == dict.fromkeys(models, "success") | dict.fromkeys(data_tests, "pass")


def test_product_deals_gives_the_golden_s_eight_rows_at_universe(clean):
    """At Shufersal Universe on 30 April, a row for each product a promotion counts for (U1 to U8), each as the golden
    works it ("The verdicts", Universe, day 120): today's price, the usual price and the saving, the days tracked,
    priced and on sale, whether it passes the front list's bar, and the verdict. No U9 row (its promotion at store 81
    alone, not wide) and no U10 row (its 6.50 twice the listed 3.00 or more, not valid)."""
    found = query(clean.database, "select barcode, today_price, usual_price, saving, days_tracked, days_priced, "
                                  "days_on_sale, checked, verdict from product_deals "
                                  "where store_type = 'shufersal-universe' and day = date '2026-04-30'")
    assert {row[0]: row[1:] for row in found} == {
        U1: (D("9.90"), D("9.90"), D("0.00"), 27, 27, 27, True, "no deal"),
        U2: (D("6.90"), D("8.90"), D("2.00"), 27, 27, 10, True, "deal"),
        U3: (D("7.90"), D("9.90"), D("2.00"), 26, 26, 13, True, "deal"),
        U4: (D("3.20"), D("4.50"), D("1.30"), 5, 5, 0, False, "deal"),
        U5: (D("5.00"), None, None, 0, 0, 0, False, "no verdict"),
        U6: (D("4.01"), D("5.00"), D("0.99"), 27, 27, 0, True, "no deal"),
        U7: (D("4.00"), D("5.00"), D("1.00"), 27, 27, 0, True, "deal"),
        U8: (D("4.50"), D("6.00"), D("1.50"), 27, 27, 0, True, "deal"),
    }
    assert len(found) == 8


def test_store_type_deals_gives_6_checked_and_4_deals_at_universe(clean):
    """Universe's store page on 30 April: M, the 6 checked (U1, U2, U3, U6, U7, U8), and N, the 4 deals among them (U2,
    U3, U7, U8); U1 on sale on every one of its tracked days, and on more than half; U3 on exactly half, not more."""
    assert query(clean.database, "select checked, deals, on_sale_every_tracked_day, on_sale_more_than_half "
                                 "from store_type_deals "
                                 "where store_type = 'shufersal-universe' and day = date '2026-04-30'") == [
        (6, 4, 1, 1)]


def test_basket_prices_gives_the_golden_s_medians(clean):
    """Each chain's G1, G2 and G6 on 30 April ("The basket"): G6 the median over the chain's stores, Shufersal's the
    7.60 of its five stores' 7.00 to 8.20 (Universe's three list no basket item), Carrefour's the 8.30 of its five,
    each other chain's the mean of its two stores; G1 at 5.00 and G2 at 2.50 at every store; no store double-coded."""
    found = query(clean.database, "select chain, barcode, median, low, high, stores_listing, double_coded "
                                  "from basket_prices where day = date '2026-04-30'")
    stores = {"shufersal": 5, "carrefour": 5, "ramilevy": 2, "osherad": 2, "yochananof": 2}
    g6 = {"shufersal": ("7.600", "7.00", "8.20"), "carrefour": ("8.300", "7.90", "8.60"),
          "ramilevy": ("7.500", "7.40", "7.60"), "osherad": ("7.200", "7.10", "7.30"),
          "yochananof": ("7.900", "7.80", "8.00")}
    expected = {}
    for chain, count in stores.items():
        expected[(chain, G1)] = ("5.000", "5.00", "5.00", count, 0)
        expected[(chain, G2)] = ("2.500", "2.50", "2.50", count, 0)
        expected[(chain, G6)] = (*g6[chain], count, 0)
    assert {(chain, code): (str(median), str(low), str(high), listing, double)
            for chain, code, median, low, high, listing, double in found} == expected
    assert len(found) == 15


def test_promotion_reach_at_universe_on_its_last_day(clean):
    """Universe's promotions on listed products running on 30 April: 10 (60 and 62 to 70; 61 ended on day 101), 9 at
    its three stores, so at most branches, and 69 at store 81 alone, at some; none with a restriction or a minimum
    spend."""
    assert query(clean.database, "select promotions, at_most_branches, at_some_branches, restricted, with_min_spend "
                                 "from promotion_reach "
                                 "where store_type = 'shufersal-universe' and day = date '2026-04-30'") == [
        (10, 9, 1, 0, 0)]


def test_the_owner_s_four_known_differences_render_as_written(tmp_path):
    """known_differences built from the project's own list, with no list given in its place: its anchor and alias,
    its folded text, the ₪ sign and each apostrophe, doubled in the SQL, give the owner's four rows, each reason
    whole. `run`, so the model alone is built: `build` would also run every data test that reads it, and under the
    project's own vars such a test would read the checkout's data/ and site/."""
    done = run_dbt(["run", "--select", "known_differences"], tmp_path / "work")
    assert done.code == 0, done.output
    assert done.results == {"known_differences": ("success", None)}
    found = query(done.database, "select kind, key, day, reason from known_differences")
    assert sorted((kind, key, day.isoformat()) for kind, key, day, _ in found) == OWNER_S_FOUR
    assert {(kind, key, day.isoformat()): reason for kind, key, day, reason in found} == {
        ("basket", "shufersal", "2026-11-09"): SLOW_MORNING, ("store_page", "ramilevy", "2026-11-21"): WEIGHED,
        ("store_page", "ramilevy", "2026-11-22"): WEIGHED, ("store_page", "yochananof", "2026-11-22"): WEIGHED}


# The data tests on the bad rows (Tasks 8 to 10 of docs/dbt-layer-plan.md). Each data test's name, to the status and
# the failures (the rows it returns, one for each row, file, key or barcode its description names) it must give on the
# bad rows `plant_bad_rows` plants. A test fails on its own bad rows alone, so a rule weakened in a test shows as a
# count that moved, and a bad row that broke a second test shows there.
EXPECTED_BAD: dict[str, tuple[str, int]] = {
    # the prices tables
    "prices_one_row_per_chain_day_store_and_code": ("fail", 1),
    "prices_one_file_per_store_and_day": ("fail", 1),
    "prices_each_row_from_a_pricefull_file_of_its_day": ("fail", 2),
    "prices_gs1_is_the_check_digit": ("fail", 2),
    # the promotions tables
    "promotions_one_row_per_day_store_type_promotion_group_and_code": ("fail", 1),
    "promotions_wide_is_half_the_counted_stores": ("fail", 4),
    "promotions_run_today_and_start_before_they_end": ("fail", 2),
    "promotions_kind_follows_the_reward_type": ("fail", 3),
    "promotions_minimum_spend_above_zero": ("fail", 1),
    "promotions_store_prices_in_order": ("fail", 4),
    "promotions_counted_is_the_reports": ("fail", 2),
    # the items tables and their reports
    "items_one_row_per_day_store_type_and_product": ("fail", 1),
    "items_store_type_is_one_of_the_nine_under_its_chain": ("fail", 2),
    "items_listed_price_in_range_and_listed_somewhere": ("fail", 5),
    "items_wide_is_half_the_stores_with_a_file": ("fail", 2),
    "items_on_promotion_follows_its_promotions": ("fail", 6),
    "items_promotions_start_before_they_end_run_today_and_appear_once": ("fail", 4),
    "items_valid_deal_prices_are_above_an_agora_and_below_twice_the_listed": ("fail", 3),
    "items_report_holes_follow_their_counts": ("fail", 4),
    "items_every_chain_every_day": ("warn", 5),
    "items_agree_with_their_reports": ("fail", 4),
    # across tables
    "listed_price_is_the_median_of_the_prices_table": ("fail", 7),
    "promotions_at_most_branches_agree_across_tables": ("fail", 1),
    # against the published files
    "store_type_deals_match_published": ("fail", 4),
    "product_deals_match_published_rows": ("fail", 6),
    "promotion_reach_matches_published": ("fail", 1),
    "basket_prices_match_published": ("fail", 7),
    "basket_prices_at_shufersal_match_published": ("warn", 1),
    "known_differences_still_differ": ("fail", 8),
}
# The GS1 test's four codes, synthetic, as basket.barcode.is_gs1 reads them; LONG's and SHORT's weighted sums, worked
# as is_gs1 works a sum, end in 0.
WRONG_CHECK = "2000000000238"     # 13 digits, its check digit 8 where the rule gives 7
VALID_13 = "2000000000244"        # 13 digits, its check digit right
LONG = "200000000000251"          # 15 digits, its check digit right: GS1 but for its length
SHORT = "2000008"                 # 7 digits, its check digit right: GS1 but for its length
assert not is_gs1(WRONG_CHECK) and is_gs1(WRONG_CHECK[:-1] + "7") and is_gs1(VALID_13)
assert not is_gs1(LONG) and not is_gs1(SHORT)
assert all(sum(int(digit) * (3 if place % 2 else 1) for place, digit in enumerate(reversed(code))) % 10 == 0
           for code in (LONG, SHORT))
# Shufersal's file names the bad prices rows take, beside Universe's own of 30 April
# (PriceFull7290027600007-008-08<n>-20260430-080000.gz).
SECOND_FILE = "PriceFull7290027600007-008-082-20260430-090000.gz"   # a later full price file of store 82's day
PRICE_FILE = "Price7290027600007-008-083-20260430-080000.gz"         # a price file of the day, not a full one
DAY_BEFORE_FILE = "PriceFull7290027600007-008-081-20260429-080000.gz"   # a full price file of 29 April
# Carrefour store 1's own name of 30 April (PriceFull7290055700007-001-001-20260430-080000.gz) in a shape the collector
# also reads as that store's full price file of the day: the kind in lower case, the time run on into the date, the
# extension in upper case and a conflict copy's suffix. Right, so it fails only a rule that refuses one of them.
VARIANT_FILE = "pricefull7290055700007-001-001-202604300800.GZ.0123456789ab"
assert parse_file_name(published_name(VARIANT_FILE)) == FileName(
    raw=VARIANT_FILE.removesuffix(".0123456789ab"), kind="PriceFull", chain_id="7290055700007", store="001",
    day=day_of(LAST), sub_chain="001")
# The items tables' bad rows' codes (`plant_bad_rows`), synthetic GS1 barcodes that no golden file lists, so no prices
# or promotions row meets them; each named for what its row breaks or proves.
LOW_ABOVE, HIGH_BELOW, ONE_AGORA, AT_NO_STORE, NO_LISTED, PROMOTED = (
    "2000000000305", "2000000000312", "2000000000329", "2000000000336", "2000000000343", "2000000000350")
ONE_OF_FOUR, ON_UNKNOWN, DEALS, ONE_OF_THREE, NOT_ON, NO_KIND = (
    "2000000000367", "2000000000374", "2000000000381", "2000000000398", "2000000000404", "2000000000411")
BOTH_UNKNOWN, LIST_UNKNOWN = ("2000000000428", "2000000000435")
assert all(is_gs1(code) for code in (LOW_ABOVE, HIGH_BELOW, ONE_AGORA, AT_NO_STORE, NO_LISTED, PROMOTED, ONE_OF_FOUR,
                                     ON_UNKNOWN, DEALS, ONE_OF_THREE, NOT_ON, NO_KIND, BOTH_UNKNOWN, LIST_UNKNOWN))
# The codes of the bad rows across tables (`plant_bad_rows`, Task 10), synthetic GS1 barcodes that no golden file
# lists, and a chain's internal code, not GS1.
PRICED_ONLY, LEFT_OUT_ONLY, DOUBLE, NO_PRICES = ("2000000000442", "2000000000459", "2000000000466", "2000000000473")
INTERNAL = "12345"
assert all(is_gs1(code) for code in (PRICED_ONLY, LEFT_OUT_ONLY, DOUBLE, NO_PRICES)) and not is_gs1(INTERNAL)
# Rami Levy store 39's full price file of 30 April, a store B2 leaves out by number; its sub-chain is Rami Levy's.
STORE_39_FILE = f"PriceFull{CHAIN_IDS['ramilevy']}-001-039-20260430-080000.gz"
# The days with a day price of Sheli's G3 on 30 April in the bad-rows build: its 28 days of records before it, 2 to 29
# April, but the promotion hole of 28 April and the hole of 29 April (`plant_bad_rows`), each a day not tracked.
SHELI_G3_DAYS = 26
UNREAD = "carrefour: a promotion file that does not read"   # the 28 April copy's promotions error, synthetic
# The fields of a struct of an items row's promotions list, in the table's order (src/shopper/items.py, _STRUCT).
PROMOTION_FIELDS = ("promotion_id", "description", "start", "end", "kind", "buy", "price", "price_exact", "per", "low",
                    "high", "valid", "why", "restrictions", "programmes", "min_spend", "stores", "wide")


def _rewrite(path: Path, *statements: str) -> None:
    """Run `statements` over the Parquet file at `path`, read as the table `staged`, and write it back in place with
    every column's type kept: `staged` takes the file's types, a row inserted or changed is cast to them, and the file
    written is checked to have them. The folder's chain and day are not columns of the file (hive_partitioning off)."""
    def read(file: Path) -> str:
        return f"read_parquet('{file}', hive_partitioning = false)"
    written = path.with_suffix(".rewritten")
    with duckdb.connect() as con:
        types = con.execute(f"describe select * from {read(path)}").fetchall()
        con.execute(f"create table staged as select * from {read(path)}")
        for statement in statements:
            con.execute(statement)
        con.execute(f"copy staged to '{written}' (format parquet)")
        assert con.execute(f"describe select * from {read(written)}").fetchall() == types
    written.replace(path)


def _at_city(promotion_id: str, template: Path, changes: dict[str, str] | None = None) -> str:
    """An insert of a Carrefour City promotions row on U1, which Carrefour does not list: Universe's promotion 60 on U1
    (in `template`, Shufersal's table of the day) under `promotion_id`, at City's 2 counted stores, both carrying it,
    and wide. So it is right by every rule but its `changes`, each a column (quoted where SQL needs it) and its new
    value as SQL."""
    values = {'"column"': "'carrefour-city'", "promotion_id": f"'{promotion_id}'", "stores": "2",
              "promotion_stores": "2", "counted": "2", "wide": "true", **(changes or {})}
    replaced = ", ".join(f"{value} as {column}" for column, value in values.items())
    return (f"insert into staged select * replace ({replaced}) from read_parquet('{template}', "
            f"hive_partitioning = false) where \"column\" = 'shufersal-universe' and promotion_id = '60' "
            f"and group_id = '1' and code = '{U1}'")


def _item(code: str, template: str, changes: dict[str, str] | None = None) -> str:
    """An insert of an items row of `code`: the G2 row of the store type `template` (listed 2.500 at every store, wide,
    not on promotion, no promotion on it) under `code`. So it is right by every rule but its `changes`, each a column
    (quoted where SQL needs it) and its new value as SQL."""
    values = {"code": f"'{code}'", **(changes or {})}
    replaced = ", ".join(f"{value} as {column}" for column, value in values.items())
    return (f"insert into staged select * replace ({replaced}) from staged "
            f"where \"column\" = '{template}' and code = '{G2}'")


def _promotion(promotion_id: str, changes: dict[str, str] | None = None) -> str:
    """A struct of an items row's promotions list as SQL, its fields in the table's order: a fixed price of 2.00 from 30
    April to 6 May at both of a Carrefour store type's counted stores, wide and valid. So it is right by every rule but
    its `changes`, each a field and its new value as SQL."""
    values = {"promotion_id": f"'{promotion_id}'", "description": f"'מבצע לדוגמה {promotion_id}'",
              "start": "date '2026-04-30'", "end": "date '2026-05-06'", "kind": "'fixed_price'", "buy": "1.000",
              "price": "2.00", "price_exact": "'2'", "per": "'unit'", "low": "null", "high": "null", "valid": "true",
              "why": "null", "restrictions": "[]", "programmes": "[]", "min_spend": "null", "stores": "2",
              "wide": "true", **(changes or {})}
    assert set(values) == set(PROMOTION_FIELDS)
    return "{" + ", ".join(f"'{field}': {values[field]}" for field in PROMOTION_FIELDS) + "}"


def _report(folder: Path, columns: dict[str, dict], **fields) -> None:
    """Change the items report in `folder`: each store type's counts and flags in `columns`, and the report's own
    `fields`, each one the report already has; written back as src/shopper/items.py writes it."""
    path = folder / "report.json"
    report = json.loads(path.read_text())
    for column, changes in columns.items():
        assert set(changes) <= set(report["columns"][column])
        report["columns"][column] |= changes
    assert set(fields) <= set(report)
    path.write_text(json.dumps(report | fields, sort_keys=True, indent=1))


def plant_bad_rows(tables: Path, site: Path) -> None:
    """Plant the data tests' bad rows in a copy of the golden's tables (`tables`) and published files (`site`), on 30
    April unless said. Each breaks one clause of one data test and keeps every other rule, but DEALS's three promotions
    (below); none is in what another test reads, unless said. The published files keep the golden's.

    Shufersal's prices table, at Universe's stores (U1 to U10 are no basket product):
    - store 81's U1 row twice (the one row per chain, day, store and code);
    - store 82's U2 row under a second full price file of the day (one file per store and day);
    - every row of store 83 under a `Price` file of the day, and every row of store 81 under a `PriceFull` file of 29
      April (each row from a full price file of its day: one row a file);
    - at store 82, four new codes: WRONG_CHECK flagged GS1 and VALID_13 flagged not; LONG and SHORT flagged not, which
      is right, so they fail only a rule that takes 15 or 7 digits (the GS1 flag is the check digit's).

    Carrefour's prices table: store 1's rows under VARIANT_FILE, which is right, so it fails only a rule that refuses
    the kind in lower case, a time run on into the date or a conflict copy's name (each row from a full price file).

    Carrefour's promotions table, which is empty, gains City rows on U1 (`_at_city`): Carrefour does not list U1, so
    neither promotion_reach nor the items table reads them. Promotion 901 twice (the uniqueness). Wide: 902 not wide at
    2 of 2, 903 at 2 stores of a promotion carried by 1, 912 at no store, and 913 of a promotion carried by 3 of the 2
    counted (the clean build's promotion 69, 1 of 3 and not wide, catches a weakened half). 904 ended on 29 April, and
    905 starting after it ends (run today, start before the end). The kind: 906 of reward type 2 with the kind
    fixed_price, 907 of reward type 6 and 918 of reward type 12. 908 at a minimum spend of 0.00. The stores' prices:
    909 its lowest above the median, 916 with no lowest beside a median and a highest, and 917 with none of the three,
    which is right; 910 fixed-price with a count of stores priced; 914 a percent-off row with more stores agreeing (2)
    than priced (1), and 915 with 1 of 2, which is right. Counted: 911 at 3 counted stores where the report says 2, and
    919 under carrefour-online, a store type no report holds; neither promotion_reach nor the items table reads it.
    Shufersal's table gains Universe's promotion 60 on U1 under a second group, which is unique, so it fails only a
    uniqueness without the group; promotion_reach counts a promotion once however many groups name it.

    The items tables and their reports, Carrefour's unless said. Every row added or changed moves its report's counts
    with it, so the agreement of the tables with their reports fails on its own four store-type days alone. The new
    codes (LOW_ABOVE and the others) are listed by no golden file, so no prices or promotions row meets them, and each
    new row is a store type's G2 row under its code (`_item`), each new promotion `_promotion`'s, but what is said.
    - Two copies of Carrefour's day, made before its bad rows, under 28 April and 1 May; Carrefour has no prices or
      promotions table on either day. The 28 April copy's promotions were not read: its report gives a promotions error
      (UNREAD) and both promotion holes, and its rows no promotions, on_promotion or next_start, as the extraction
      writes such a day, but Market's G2 is not on promotion where it should be NULL (on promotion). Its promotion
      files stay 2 of 2, so the holes stand on the error alone: right, so they fail only a hole rule that forgets the
      error. With the two copies Carrefour lacks 29 April and the four other chains lack 1 May (every chain, every day:
      five warnings, where a chain checked to its own last day gives one).
    - 1 May: City's NOT_ON is not on promotion, with a wide fixed price running on it (5.00, twice its listed 2.500:
      not valid) (on promotion); a rule that asked for a valid deal would clear it and fail the clean build's U10, on
      promotion with a deal not valid. Market's NO_KIND has a wide promotion running with no kind and is not on
      promotion, which is right, so it fails only a rule that drops the kind.
    - Market: G2 twice (the uniqueness); G1 not wide at 2 of 2 (wide); G6 on promotion with no promotion on it (on
      promotion); BOTH_UNKNOWN with no on_promotion and no promotions list, and LIST_UNKNOWN not on promotion with no
      promotions list, on a day the promotions were read (on promotion); LOW_ABOVE's lowest price above its listed one,
      HIGH_BELOW's highest below it, ONE_AGORA listed at 0.010, AT_NO_STORE listed at no store (so not wide, which is
      right) and NO_LISTED with no listed price (the listed price); PROMOTED's six promotions, none running, wide and
      valid: 951 ended on 29 April, 952 starting after it ends, 953 twice, from 1 May, and 954 with no start (start,
      end and once), and 955 once, from 1 May, which is right, so it fails only a rule that drops a promotion starting
      after the day. PROMOTED is not on promotion, which is right, so it fails only an on-promotion rule that drops the
      start or the end, and its report counts no valid deal, so it fails only an agreement that does. Market's report
      is a hole with every file (the holes).
    - City: its report's included stores and stores with a file are 4, so G1, G2 and G6, at 2 of 4, are wide at
      exactly half, which is right; ONE_OF_FOUR is wide at 1 of 4 (wide); ON_UNKNOWN has no on_promotion (on
      promotion); both hold promotion 964, wide with no kind, once each, which is right, so it fails only a rule that
      takes one promotion on two rows for one promotion twice on a row. DEALS has three valid deals, not wide: 961 at
      0.01, 962 at 5.00, twice its listed 2.500, and 963 with no price (the valid deals); City's report counts them, so
      an agreement that counted wide deals alone would fail it. Each is at 1 store, which at City's 2 counted stores
      rule P3 calls wide: the one rule these three break beyond their own, and no test reads a promotion's stores
      against its wide. They are not wide so that no promotion counts at City on 30 April. City's report has no
      promotion file of its 2 counted stores and no promotion hole (the holes).
    - Rows under store types the report lacks (the store type): G2 under carrefour-express, and U1 under shufersal-deal,
      at 1 store, not wide, with no promotions (but Task 10's 984, below) and not on promotion, which a wide,
      on-promotion or agreement rule that met reports without the chain would read against Shufersal Deal's, and a wide
      or on-promotion rule that kept a row meeting no report would fail.
    - Shufersal: Universe's ONE_OF_THREE at 1 of its 3 stores and not wide, which is right, so it fails only a weakened
      half. Express's report, of a store type with no store and no row: on 29 April 3 included, 1 with a file and a
      hole, 3 counted, 1 with a promotion file and a promotion hole; on 28 April 2 and 1 and no hole, 2 and 1 and no
      promotion hole: right, so they fail only a weakened half or a hole at exactly half. On 27 April 2 included, none
      with a file and no hole; on 26 April 2 counted, both with a promotion file and a promotion hole (the holes).
    - The agreement, each report one count off its table: Express's of 30 April 1 row where its table has none, Rami
      Levy's 3 wide of its 4, Yochananof's 1 on promotion of none, and Sheli's 2 valid deals of 1.

    Across tables (Task 10), at the three chains of one store type unless said. First, copies made from the golden's
    own tables before any other bad row, each a day the golden lacks: Yochananof's prices and items tables of 30 April
    under 28 April, its store 1's G6 at 7.70 and the items row moved with it (listed 7.850, lowest 7.70), and its items
    table alone under 29 April; Rami Levy's prices table alone under 28 April, its store 1's G6 at 7.30; Osher Ad's
    items table alone under 28 and 29 April. A copied prices table's file names carry its own day. Each chain still
    lacks 1 May alone, so every chain, every day keeps its five warnings.
    - The listed price against the prices table: Rami Levy store 2's G4 at 70.10, its items row left at 69.90 (G4 is no
      basket product); PRICED_ONLY, a GS1 code at Rami Levy store 1 with no items row; Yochananof's items rows of G6 at a
      listed 7.950, of G2 at a lowest 2.40 and of G1 at a highest 5.10, and Osher Ad's of G1 at 3 stores, each the one
      figure that differs; and Osher Ad's NO_PRICES, an items row (`_item`'s) that no price row lists. Right, so each
      fails only a check without one of its rules: Rami Levy store 39's price file of the day (STORE_39_FILE), G4 at
      68.90 and LEFT_OUT_ONLY, a store B2 leaves out by number (the rows that count); INTERNAL, a code not GS1, at Rami
      Levy store 1; Yochananof's DOUBLE at store 1 under two codes with the same digits at 3.00 and 3.10, its items row
      3.00 at 1 store (one price a store, its lowest); Osher Ad's G6 at 7.10 and 7.19, the items row moved with it
      (listed 7.145, highest 7.19); Yochananof's 28 April (the join's day); its 29 April and Osher Ad's 28 and 29
      April, an items table and no prices table (Osher Ad's 28 April on a day Yochananof and Rami Levy have one); and
      Rami Levy's 28 April, a prices table and no items table (on a day Yochananof and Osher Ad have one).
    - The promotions at most branches: Osher Ad's promotions table gains 982 on G2, wide, a fixed price running, which
      no items row carries. Right: Rami Levy's 981 on G1 and G2 in both tables, one promotion on two rows (both items
      rows on promotion, the report's on promotion and valid deals 2); Yochananof's 29 April G2 carrying 983, wide and
      running, on a day Yochananof has no promotions row (its report's on promotion and valid deals 1); and Task 9's
      rows at Carrefour, none wide, with a kind and running on 30 April, and NOT_ON's 971 on 1 May, a day Carrefour has
      no promotions row. And, right, Task 9's U1 under shufersal-deal in Carrefour's table carries 984, wide, a fixed
      price running (its on_promotion left false, a row meeting no report): read by store type and day without the
      chain, it would count at Shufersal Deal.

    Against the published files (Task 10). Shufersal Sheli's report of 28 April is a promotion hole (no promotion file of
    its 2 counted stores) and of 29 April a hole (no included store): neither day has a product_deals row at Sheli, and
    their pages publish 0 of 0 and no promotions count, as the site writes such a day. The site-day files:
    - 30 April: Universe's M 7 (N 4 right) and its promotions 8; its shown rows U2's usual 8.80, U3's today 7.80, U8's
      saving 1.40 and U7's days 26, each the one figure that differs; Carrefour City's N 1 where the model gives 0 of
      0, M right, and its promotions 0 (Carrefour has promotions rows, none on a product it lists); Yochananof's 1 of 1
      where the model gives 0 of 0, its 2 promotions on a day Yochananof has no promotions row, and a shown row of G3
      with Sheli's figures for G3 (product_deals has a G3 row at Sheli that day, none at Yochananof); Osher Ad's 0 of 0
      and 1 promotion (982), as the model gives.
    - 29 April (new): Sheli's hole; City's, on a day Carrefour has no items table; Deal's 1 of 0 where the model gives 0
      of 0; Universe's 2 of 3 and 3 promotions as the model gives, but U3's shown usual 9.80.
    - 28 April (new): Sheli's promotion hole; Universe's 2 of 3 as the model gives, but its promotions 4 where the model
      gives 3 (listed: it differs by its promotions count alone). 1 May (new): Deal's 1 of 1 and a shown row of G5, on a
      day Shufersal has
      no items table; City's 0 of 0 and 3 promotions, on a day Carrefour has no promotions row.
    The basket day files: 30 April: Rami Levy's G6 median 7.40, G1 lowest 4.90 and G2 highest 2.60, each the one figure
    that differs, and a G4 item, which is no basket product; Osher Ad's G1 at 3 stores and G2 at 1 double-coded store;
    Shufersal's G6 at 6 stores (its standing warning); and, right, Osher Ad's G6 at 7.15, 7.10 and 7.19, the model's
    7.145 rounded half up. 28 April (new): Yochananof's G1 and G2 as the model gives them and no G6, which Yochananof's
    copied prices table of that day prices."""
    day = f"date={day_of(LAST).isoformat()}"
    # Task 10's copies, from the golden's own tables before any other bad row (the docstring's "Across tables").
    for kind, slug, n in (("prices", "yochananof", LAST - 2), ("items", "yochananof", LAST - 2),
                          ("items", "yochananof", LAST - 1), ("prices", "ramilevy", LAST - 2),
                          ("items", "osherad", LAST - 2), ("items", "osherad", LAST - 1)):
        shutil.copytree(tables / kind / f"chain={slug}" / day,
                        tables / kind / f"chain={slug}" / f"date={day_of(n).isoformat()}")
    on_28 = f"date={day_of(LAST - 2).isoformat()}"
    for slug in ("yochananof", "ramilevy"):
        _rewrite(tables / "prices" / f"chain={slug}" / on_28 / "prices.parquet",
                 "update staged set file = replace(file, '-20260430-', '-20260428-')",
                 f"update staged set price = {'7.70' if slug == 'yochananof' else '7.30'} "
                 f"where store = '1' and code = '{G6}'")
    _rewrite(tables / "items" / "chain=yochananof" / on_28 / "items.parquet",
             f"update staged set listed = 7.850, low = 7.70 where code = '{G6}'")
    _rewrite(tables / "prices" / "chain=shufersal" / day / "prices.parquet",
             f"insert into staged select * from staged where store = '81' and code = '{U1}'",
             f"update staged set file = '{SECOND_FILE}' where store = '82' and code = '{U2}'",
             f"update staged set file = '{PRICE_FILE}' where store = '83'",
             f"update staged set file = '{DAY_BEFORE_FILE}' where store = '81'",
             *(f"insert into staged select * replace ('{code}' as code, '{code}' as code_norm, {flag} as gs1) "
               f"from staged where store = '82' and code = '{U7}'"
               for code, flag in ((WRONG_CHECK, "true"), (VALID_13, "false"), (LONG, "false"), (SHORT, "false"))))
    _rewrite(tables / "prices" / "chain=carrefour" / day / "prices.parquet",
             f"update staged set file = '{VARIANT_FILE}' where store = '1'")
    universe = tables / "promotions" / "chain=shufersal" / day / "promotions.parquet"
    _rewrite(tables / "promotions" / "chain=carrefour" / day / "promotions.parquet",
             _at_city("901", universe), _at_city("901", universe),
             _at_city("902", universe, {"wide": "false"}),
             _at_city("903", universe, {"promotion_stores": "1"}),
             _at_city("904", universe, {'"start"': "date '2026-04-20'", '"end"': "date '2026-04-29'"}),
             _at_city("905", universe, {'"start"': "date '2026-05-07'", '"end"': "date '2026-05-06'"}),
             _at_city("906", universe, {"reward_type": "'2'"}),
             _at_city("907", universe, {"reward_type": "'6'", "kind": "null"}),
             _at_city("908", universe, {"min_spend": "0.00"}),
             _at_city("909", universe, {"discounted_low": "9.950", "discounted_high": "9.950"}),
             _at_city("910", universe, {"with_store_price": "2"}),
             _at_city("911", universe, {"counted": "3"}),
             _at_city("912", universe, {"stores": "0", "wide": "false"}),
             _at_city("913", universe, {"promotion_stores": "3"}),
             _at_city("914", universe, {"reward_type": "'2'", "kind": "'percent_off'", "with_store_price": "1",
                                        "agrees_with_store": "2"}),
             _at_city("915", universe, {"reward_type": "'2'", "kind": "'percent_off'", "with_store_price": "2",
                                        "agrees_with_store": "1"}),
             _at_city("916", universe, {"discounted_low": "null"}),
             _at_city("917", universe, {"discounted_low": "null", "discounted_median": "null",
                                        "discounted_high": "null"}),
             _at_city("918", universe, {"reward_type": "'12'", "kind": "null"}),
             _at_city("919", universe, {'"column"': "'carrefour-online'"}))
    _rewrite(universe, "insert into staged select * replace ('2' as group_id) from staged "
                       f"where \"column\" = 'shufersal-universe' and promotion_id = '60' and code = '{U1}'")
    items = tables / "items"
    carrefour, shufersal = items / "chain=carrefour" / day, items / "chain=shufersal"
    unread, after = (items / "chain=carrefour" / f"date={day_of(n).isoformat()}" for n in (LAST - 2, LAST + 1))
    for copy in (unread, after):
        shutil.copytree(carrefour, copy)
    _rewrite(unread / "items.parquet", "update staged set on_promotion = null, next_start = null, promotions = null",
             f"update staged set on_promotion = false where \"column\" = 'carrefour-market' and code = '{G2}'")
    _report(unread, {"carrefour-city": {"promo_hole": True}, "carrefour-market": {"promo_hole": True}},
            promotions_error=UNREAD, promotions=None)
    too_dear = _promotion("971", {"price": "5.00", "price_exact": "'5'", "valid": "false",
                                  "why": "'not below twice the listed price'"})
    no_kind, on_two_rows = (_promotion(promotion_id, {"kind": "null", "price": "null", "price_exact": "null",
                                                      "valid": "false", "why": "'no kind link'"})
                            for promotion_id in ("972", "964"))
    _rewrite(after / "items.parquet", _item(NOT_ON, "carrefour-city", {"promotions": f"[{too_dear}]"}),
             _item(NO_KIND, "carrefour-market", {"promotions": f"[{no_kind}]"}))
    _report(after, {"carrefour-city": {"items": 4, "wide": 4}, "carrefour-market": {"items": 4, "wide": 4}})
    ended = _promotion("951", {"start": "date '2026-04-20'", "end": "date '2026-04-29'"})
    backwards = _promotion("952", {"start": "date '2026-05-07'", "end": "date '2026-05-06'"})
    later, later_once = (_promotion(promotion_id, {"start": "date '2026-05-01'", "end": "date '2026-05-05'"})
                         for promotion_id in ("953", "955"))
    no_start = _promotion("954", {"start": "null"})
    at_one_agora, at_twice, no_price = (
        _promotion(promotion_id, {"price": price, "price_exact": exact, "stores": "1", "wide": "false"})
        for promotion_id, price, exact in (("961", "0.01", "'1/100'"), ("962", "5.00", "'5'"), ("963", "null", "null")))
    _rewrite(carrefour / "items.parquet",
             _item(G2, "carrefour-market", {'"column"': "'carrefour-express'"}),
             _item(U1, "carrefour-market", {'"column"': "'shufersal-deal'", "listing": "1", "wide": "false",
                                            "promotions": "null"}),
             _item(LOW_ABOVE, "carrefour-market", {"low": "2.60", "high": "2.70"}),
             _item(HIGH_BELOW, "carrefour-market", {"low": "2.40", "high": "2.45"}),
             _item(ONE_AGORA, "carrefour-market", {"listed": "0.010", "low": "0.01", "high": "0.01"}),
             _item(AT_NO_STORE, "carrefour-market", {"listing": "0", "wide": "false"}),
             _item(NO_LISTED, "carrefour-market", {"listed": "null"}),
             _item(PROMOTED, "carrefour-market",
                   {"promotions": f"[{ended}, {backwards}, {later}, {later}, {no_start}, {later_once}]"}),
             _item(BOTH_UNKNOWN, "carrefour-market", {"on_promotion": "null", "promotions": "null"}),
             _item(LIST_UNKNOWN, "carrefour-market", {"promotions": "null"}),
             _item(ONE_OF_FOUR, "carrefour-city", {"listing": "1", "promotions": f"[{on_two_rows}]"}),
             _item(ON_UNKNOWN, "carrefour-city", {"on_promotion": "null", "promotions": f"[{on_two_rows}]"}),
             _item(DEALS, "carrefour-city", {"promotions": f"[{at_one_agora}, {at_twice}, {no_price}]"}),
             f"update staged set wide = false where \"column\" = 'carrefour-market' and code = '{G1}'",
             f"update staged set on_promotion = true where \"column\" = 'carrefour-market' and code = '{G6}'",
             f"insert into staged select * from staged where \"column\" = 'carrefour-market' and code = '{G2}'")
    _report(carrefour, {
        "carrefour-market": {"hole": True, "items": 12, "wide": 10, "on_promotion": 1},
        "carrefour-city": {"included": 4, "with_file": 4, "promo_files": 0, "items": 6, "wide": 6, "valid_deals": 3}})
    _rewrite(shufersal / day / "items.parquet",
             _item(ONE_OF_THREE, "shufersal-sheli", {'"column"': "'shufersal-universe'", "listing": "1",
                                                     "wide": "false"}))
    _report(shufersal / day, {"shufersal-universe": {"items": 11}, "shufersal-express": {"items": 1},
                              "shufersal-sheli": {"valid_deals": 2}})
    for n, express in ((LAST - 1, {"included": 3, "with_file": 1, "hole": True, "counted": 3, "promo_files": 1,
                                   "promo_hole": True}),
                       (LAST - 2, {"included": 2, "with_file": 1, "hole": False, "counted": 2, "promo_files": 1,
                                   "promo_hole": False}),
                       (LAST - 3, {"included": 2, "with_file": 0, "hole": False}),
                       (LAST - 4, {"counted": 2, "promo_files": 2, "promo_hole": True})):
        _report(shufersal / f"date={day_of(n).isoformat()}", {"shufersal-express": express})
    _report(items / "chain=ramilevy" / day, {"ramilevy": {"wide": 3}})
    _report(items / "chain=yochananof" / day, {"yochananof": {"on_promotion": 1}})
    # Task 10: across tables (the docstring's "Across tables"). The prices tables of 30 April.
    _rewrite(tables / "prices" / "chain=ramilevy" / day / "prices.parquet",
             f"update staged set price = 70.10 where store = '2' and code = '{G4}'",
             *(f"insert into staged select * replace ('{code}' as code, '{code}' as code_norm, {flag} as gs1) "
               f"from staged where store = '1' and code = '{G2}'" for code, flag in ((PRICED_ONLY, "true"),
                                                                                    (INTERNAL, "false"))),
             *(f"insert into staged select * replace ('39' as store, '{STORE_39_FILE}' as file, '{code}' as code, "
               f"'{code}' as code_norm, {price} as price) from staged where store = '1' and code = '{source}'"
               for code, price, source in ((G4, "68.90", G4), (LEFT_OUT_ONLY, "2.50", G2))))
    _rewrite(tables / "prices" / "chain=osherad" / day / "prices.parquet",
             f"update staged set price = 7.19 where store = '2' and code = '{G6}'")
    _rewrite(tables / "prices" / "chain=yochananof" / day / "prices.parquet",
             *(f"insert into staged select * replace ('{code}' as code, '{DOUBLE}' as code_norm, {price} as price) "
               f"from staged where store = '1' and code = '{G2}'" for code, price in ((DOUBLE, "3.00"),
                                                                                     ("0" + DOUBLE, "3.10"))))
    # The items tables and their reports, each count moved with its rows.
    _rewrite(items / "chain=osherad" / day / "items.parquet",
             f"update staged set listed = 7.145, high = 7.19 where code = '{G6}'",
             f"update staged set listing = 3 where code = '{G1}'",
             _item(NO_PRICES, "osherad"))
    _report(items / "chain=osherad" / day, {"osherad": {"items": 4, "wide": 4}})
    _rewrite(items / "chain=yochananof" / day / "items.parquet",
             f"update staged set listed = 7.950 where code = '{G6}'",
             f"update staged set low = 2.40 where code = '{G2}'",
             f"update staged set high = 5.10 where code = '{G1}'",
             _item(DOUBLE, "yochananof", {"listed": "3.000", "low": "3.00", "high": "3.00", "listing": "1"}))
    _report(items / "chain=yochananof" / day, {"yochananof": {"items": 4, "wide": 4}})
    _rewrite(items / "chain=ramilevy" / day / "items.parquet",
             f"update staged set on_promotion = true, promotions = [{_promotion('981')}] "
             f"where code in ('{G1}', '{G2}')")
    _report(items / "chain=ramilevy" / day, {"ramilevy": {"on_promotion": 2, "valid_deals": 2}})
    on_29 = items / "chain=yochananof" / f"date={day_of(LAST - 1).isoformat()}"
    from_29 = _promotion("983", {"start": "date '2026-04-29'"})
    _rewrite(on_29 / "items.parquet",
             f"update staged set on_promotion = true, promotions = [{from_29}] where code = '{G2}'")
    _report(on_29, {"yochananof": {"on_promotion": 1, "valid_deals": 1}})
    at_deal = _promotion("984")
    _rewrite(carrefour / "items.parquet",
             f"update staged set promotions = [{at_deal}] where \"column\" = 'shufersal-deal' and code = '{U1}'")
    # The promotions tables of 30 April: each row Universe's promotion 60 on U1 under another store type and code,
    # running from 30 April to 6 May at the store type's 2 counted stores, wide.
    def running(promotion_id: str, column: str, code: str) -> str:
        return _at_city(promotion_id, universe, {'"column"': f"'{column}'", "code": f"'{code}'",
                                                 "code_norm": f"'{code}'", '"start"': "date '2026-04-30'",
                                                 '"end"': "date '2026-05-06'"})
    _rewrite(tables / "promotions" / "chain=osherad" / day / "promotions.parquet", running("982", "osherad", G2))
    _rewrite(tables / "promotions" / "chain=ramilevy" / day / "promotions.parquet",
             running("981", "ramilevy", G1), running("981", "ramilevy", G2))
    # Against the published files (the docstring's "Against the published files"): Sheli's reports.
    _report(shufersal / f"date={day_of(LAST - 2).isoformat()}",
            {"shufersal-sheli": {"promo_files": 0, "promo_hole": True}})
    _report(shufersal / f"date={day_of(LAST - 1).isoformat()}", {"shufersal-sheli": {"included": 0, "hole": True}})
    # The site-day files.
    site_day = json.loads((site / "site-days" / f"{day_of(LAST).isoformat()}.json").read_text(encoding="utf-8"))
    columns = site_day["columns"]
    universe_shown = [(U2, "6.90", "8.80", "2.00", 27), (U3, "7.80", "9.90", "2.00", 26),
                      (U8, "4.50", "6.00", "1.40", 27), (U7, "4.00", "5.00", "1.00", 26)]
    columns["shufersal-universe"] = front(4, 7, 8, 9, tuple(universe_shown))
    columns["carrefour-city"] = front(1, 0, 0, 0)
    columns["yochananof"] = front(1, 1, 2, 2, ((G3, "7.90", "7.90", "0.00", SHELI_G3_DAYS),))
    columns["osherad"] = front(0, 0, 1, 1)
    publish(site, "site-days", site_day)
    publish(site, "site-days", {"day": day_of(LAST - 1).isoformat(), "columns": {
        "shufersal-sheli": front(0, 0, None, None), "carrefour-city": front(0, 0, 0, 0),
        "shufersal-deal": front(1, 0, 0, 0),
        "shufersal-universe": front(2, 3, 3, 3, ((U2, "6.90", "8.90", "2.00", 26),
                                                 (U3, "7.90", "9.80", "2.00", 25)))}})
    publish(site, "site-days", {"day": day_of(LAST - 2).isoformat(), "columns": {
        "shufersal-sheli": front(0, 0, None, None), "shufersal-universe": front(2, 3, 4, 3)}})
    publish(site, "site-days", {"day": day_of(LAST + 1).isoformat(), "columns": {
        "shufersal-deal": front(1, 1, 0, 0, ((G5, "4.50", "6.00", "1.50", 88),)), "carrefour-city": front(0, 0, 3, 3)}})
    # The basket day files.
    basket_day = json.loads((site / "days" / f"{day_of(LAST).isoformat()}.json").read_text(encoding="utf-8"))
    chains = basket_day["chains"]
    chains["ramilevy"]["items"][G6]["median"] = "7.40"
    chains["ramilevy"]["items"][G1]["low"] = "4.90"
    chains["ramilevy"]["items"][G2]["high"] = "2.60"
    chains["ramilevy"]["items"][G4] = basket_item("69.90", "69.90", "69.90", 2)
    chains["osherad"]["items"][G6] = basket_item("7.15", "7.10", "7.19", 2)
    chains["osherad"]["items"][G1]["listing"] = 3
    chains["osherad"]["items"][G2]["double_coded"] = 1
    chains["shufersal"]["items"][G6]["listing"] = 6
    publish(site, "days", basket_day)
    publish(site, "days", {"day": day_of(LAST - 2).isoformat(), "items_in": [G1, G2, G6], "chains": {
        "yochananof": {"total": "7.50", "items": {G1: basket_item("5.00", "5.00", "5.00", 2),
                                                  G2: basket_item("2.50", "2.50", "2.50", 2)}}}})


# The bad-rows build's known differences beyond the golden's two (BAD_VARS), each for a clause of
# known_differences_still_differ or of a comparison's skip, its reason saying why it must fail or pass there.
PLANTED = "planted: "
BAD_KNOWN = (
    # Each must fail known_differences_still_differ: it matches, or lacks a side.
    known("basket", "carrefour", LAST, PLANTED + "matches: Carrefour's published basket is the model's, while Rami "
                                                 "Levy's differs that day"),
    known("store_page", "shufersal-deal", LAST, PLANTED + "matches: Deal's published 0 of 0 is the model's, while "
                                                         "City's differs that day and Deal's on 29 April and 1 May"),
    known("store_page", "osherad", LAST, PLANTED + "matches: Osher Ad's published 0 of 0 is the model's; a store page "
                                                   "under a chain's name, which no basket skip may take for a basket"),
    known("basket", "shufersal", LAST - 1, PLANTED + "matches on 29 April, while Shufersal's basket differs on 30 "
                                                     "April"),
    known("store_page", "carrefour-city", LAST - 1, PLANTED + "no items report that day, while City has one on 28 "
                                                              "and 30 April and Deal has one that day"),
    known("store_page", "yochananof", LAST - 1, PLANTED + "no page published that day, so none differs"),
    known("basket", "ramilevy", LAST - 2, PLANTED + "no basket published that day, so none differs; Rami Levy's "
                                                    "differs on 30 April"),
    known("basket", "yochananof", LAST - 1, PLANTED + "no prices table that day, so nothing published is compared"),
    # Each must pass it: it differs by one comparison alone.
    known("store_page", "shufersal-deal", LAST - 1, PLANTED + "differs by N alone"),
    known("store_page", "shufersal-universe", LAST - 1, PLANTED + "differs by a shown row alone"),
    known("store_page", "shufersal-universe", LAST - 2, PLANTED + "differs by its promotions count alone"),
)


@pytest.fixture(scope="module")
def BAD_VARS(golden, GOLDEN_VARS, tmp_path_factory) -> dict:
    """The bad-rows build's vars: GOLDEN_VARS on a copy of the golden's tables and published files, the bad rows
    planted in the copy, and the known differences BAD_KNOWN beside the golden's two. Shared by every test in the
    module, as GOLDEN_VARS is: copy it, never change it."""
    root = tmp_path_factory.mktemp("dbt-bad")
    tables, site = root / "tables", root / "site"
    shutil.copytree(golden.tables, tables)
    shutil.copytree(golden.site, site)
    plant_bad_rows(tables, site)
    return {**GOLDEN_VARS, "tables": str(tables), "site": str(site),
            "known_differences": [*GOLDEN_VARS["known_differences"], *BAD_KNOWN]}


@pytest.fixture(scope="module")
def bad(BAD_VARS, tmp_path_factory) -> tuple[DbtRun, DbtRun]:
    """Every model built on the bad rows (`dbt run`), then every data test run on them, the unit tests left out (`dbt
    test`), on one database. Not one `dbt build`: there a failing test on a source stops the models built from it
    (docs/dbt-layer.md, section 3), and their tests could not be seen to fail."""
    root = tmp_path_factory.mktemp("bad")
    database = root / "bad.duckdb"
    built = run_dbt(["run"], root / "run", BAD_VARS, database=database)
    return built, run_dbt(["test", "--exclude", "test_type:unit"], root / "test", BAD_VARS, database=database)


def test_the_bad_rows_trip_exactly_their_tests(bad):
    """On the bad rows every model still builds, and every data test fails, or warns, with exactly its own count."""
    built, tested = bad
    assert built.code == 0, built.output
    assert tested.code == 1, tested.output
    assert tested.results == EXPECTED_BAD


def test_every_data_test_has_its_bad_row(clean):
    """Every data test of the project is in EXPECTED_BAD, so each is proved to fail on bad rows of its own."""
    assert set(EXPECTED_BAD) == _nodes(clean, "test")


def test_every_data_test_is_described(clean):
    """Every data test has a description as dbt reads it (the clean build's manifest): a singular test's from its
    folder's _<group>.yml, a generic test's from beside it."""
    assert [node["name"] for node in clean.manifest["nodes"].values()
            if node["resource_type"] == "test" and not (node.get("description") or "").strip()] == []


def test_dbt_tags_the_prices_uniqueness_alone_slow(clean):
    """dbt's own reading of the tags (the clean build's manifest), beside tests/test_dbt_project.py's reading of the
    files (`test_the_one_slow_test_is_the_prices_uniqueness`): the one node tagged slow is the prices' uniqueness."""
    assert {node["name"] for node in clean.manifest["nodes"].values() if "slow" in node.get("tags", [])} == {
        "prices_one_row_per_chain_day_store_and_code"}

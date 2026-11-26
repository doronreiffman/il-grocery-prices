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
the dbt sources read, laid out as the site lays them out, for the comparisons with the published files to read.

The build (`clean`) is `dbt build` with the unit tests left out, on its own temporary database and folders
(tests/dbt_run.py), its vars (`GOLDEN_VARS`) the golden's folders and no known difference.
"""
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from basket.chains import SLUGS
from dbt_run import query, run_dbt
from shopper.extract import extract_chain_day
from shopper_golden import G1, G2, G6, U1, U2, U3, U4, U5, U6, U7, U8, day_of, write_basket, write_day

GOLDEN_DAYS = (1, *range(92, 121))      # day 1 for the store lists; Shufersal's last 29 days, 92 to 120
SHUFERSAL_DAYS = range(92, 121)          # the days Shufersal is extracted; the four other chains are on LAST alone
LAST = 120                               # 30 April 2026, the golden's last day
D = Decimal


@dataclass(frozen=True)
class Golden:
    """The golden's folders: the tables the extraction wrote, the synthetic published files, the basket's file."""
    tables: Path
    site: Path
    basket_file: Path


def published(site: Path) -> None:
    """The synthetic published files of 30 April under `site`: the fields the dbt sources read, laid out as the site
    lays them out (keys sorted, as `basket.page.render_day` writes the basket's day files and the site-day files
    alike), the numbers from the golden's docstring:

    - `site-days/2026-04-30.json`: Shufersal Universe's front ("The verdicts", Universe, day 120): the front list's 4
      deals of the 6 checked, its rows U2, U3, U8 and U7 by saving, each with the days its reason rests on; and the 9
      promotions on 9 products of the promotions line, Universe's promotions running on day 120 at its three stores
      (60 and 62 to 68 and 70; 69 at store 81 alone does not count). Shufersal Deal's front: no promotion runs there
      on day 120 (G1's run of 110 to 116 and G5's promotion 50 of 99 to 106 have ended), so 0 of 0.
    - `days/2026-04-30.json`: each chain's G1, G2 and G6 ("The basket": G6 the median of the chain's stores, G1 and G2
      one price at every store) and its total, Osher Ad 14.70, Rami Levy 15.00, Shufersal 15.10, Yochananof 15.40 and
      Carrefour 15.80.
    """
    day = day_of(LAST).isoformat()
    rows = ((U2, "6.90", "8.90", "2.00", 27), (U3, "7.90", "9.90", "2.00", 26), (U8, "4.50", "6.00", "1.50", 27),
            (U7, "4.00", "5.00", "1.00", 27))
    shown = [{"barcode": code, "today": today, "usual": usual, "saving": saving, "days": days}
             for code, today, usual, saving, days in rows]
    site_day = {"day": day, "columns": {
        "shufersal-universe": {"front": {"deals": 4, "checked": 6, "promotions": 9, "products": 9, "rows": shown}},
        "shufersal-deal": {"front": {"deals": 0, "checked": 0, "promotions": 0, "products": 0, "rows": []}}}}

    def item(median: str, low: str, high: str, listing: int) -> dict:
        return {"median": median, "low": low, "high": high, "listing": listing, "double_coded": 0}

    def chain(total: str, g6: tuple[str, str, str], stores: int) -> dict:
        return {"total": total, "items": {G1: item("5.00", "5.00", "5.00", stores),
                                          G2: item("2.50", "2.50", "2.50", stores), G6: item(*g6, stores)}}

    basket_day = {"day": day, "items_in": [G1, G2, G6], "chains": {
        "shufersal": chain("15.10", ("7.60", "7.00", "8.20"), 5),
        "ramilevy": chain("15.00", ("7.50", "7.40", "7.60"), 2),
        "osherad": chain("14.70", ("7.20", "7.10", "7.30"), 2),
        "carrefour": chain("15.80", ("8.30", "7.90", "8.60"), 5),
        "yochananof": chain("15.40", ("7.90", "7.80", "8.00"), 2)}}
    for folder, body in (("site-days", site_day), ("days", basket_day)):
        (site / folder).mkdir(parents=True, exist_ok=True)
        (site / folder / f"{day}.json").write_text(json.dumps(body, sort_keys=True, indent=1, ensure_ascii=False),
                                                   encoding="utf-8")


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


@pytest.fixture(scope="module")
def GOLDEN_VARS(golden) -> dict:
    """The golden build's vars: the golden's folders and no known difference. A fixture, as the folders are the
    module's temporary ones; named as the plan names it."""
    return {"tables": str(golden.tables), "site": str(golden.site), "basket_file": str(golden.basket_file),
            "known_differences": []}


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

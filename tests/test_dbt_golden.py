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
from dbt_run import DbtRun, query, run_dbt
from shopper.extract import extract_chain_day
from shopper_golden import G1, G2, G6, U1, U2, U3, U4, U5, U6, U7, U8, day_of, write_basket, write_day
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
    module's temporary ones; named as the plan names it. The dict is shared by every test in the module: a test that
    needs another list copies it (`[*GOLDEN_VARS["known_differences"], ...]`), never changes it in place."""
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
    "promotions_wide_is_half_the_counted_stores": ("fail", 2),
    "promotions_run_today_and_start_before_they_end": ("fail", 2),
    "promotions_kind_follows_the_reward_type": ("fail", 2),
    "promotions_minimum_spend_above_zero": ("fail", 1),
    "promotions_store_prices_in_order": ("fail", 2),
    "promotions_counted_is_the_reports": ("fail", 1),
}
# The GS1 test's three codes, synthetic, as basket.barcode.is_gs1 reads them.
WRONG_CHECK = "2000000000238"     # 13 digits, its check digit 8 where the rule gives 7
VALID_13 = "2000000000244"        # 13 digits, its check digit right
LONG = "200000000000251"          # 15 digits, its check digit right: GS1 but for its length
assert not is_gs1(WRONG_CHECK) and is_gs1(WRONG_CHECK[:-1] + "7") and is_gs1(VALID_13) and not is_gs1(LONG)
assert sum(int(digit) * (3 if place % 2 else 1) for place, digit in enumerate(reversed(LONG))) % 10 == 0
# Shufersal's file names the bad prices rows take, beside Universe's own of 30 April
# (PriceFull7290027600007-008-08<n>-20260430-080000.gz).
SECOND_FILE = "PriceFull7290027600007-008-082-20260430-090000.gz"   # a later full price file of store 82's day
PRICE_FILE = "Price7290027600007-008-083-20260430-080000.gz"         # a price file of the day, not a full one
DAY_BEFORE_FILE = "PriceFull7290027600007-008-081-20260429-080000.gz"   # a full price file of 29 April


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


def plant_bad_rows(tables: Path, site: Path) -> None:
    """Plant the data tests' bad rows in a copy of the golden's tables (`tables`) and published files (`site`), all on
    30 April. Each breaks one clause of one data test and keeps every other rule; none is in what another test reads,
    unless said. The published files keep the golden's.

    Shufersal's prices table, at Universe's stores (U1 to U10 are no basket product):
    - store 81's U1 row twice (the one row per chain, day, store and code);
    - store 82's U2 row under a second full price file of the day (one file per store and day);
    - every row of store 83 under a `Price` file of the day, and every row of store 81 under a `PriceFull` file of 29
      April (each row from a full price file of its day: one row a file);
    - at store 82, three new codes: WRONG_CHECK flagged GS1, VALID_13 flagged not, and LONG flagged not, which is
      right, so it fails only a rule that takes 15 digits (the GS1 flag is the check digit's).

    Carrefour's promotions table, which is empty, gains City rows on U1 (`_at_city`): Carrefour does not list U1, so
    neither promotion_reach nor the items table reads them. Promotion 901 twice (the uniqueness); 902 not wide at 2 of
    2, and 903 at 2 stores of a promotion carried by 1 (wide: the clean build's promotion 69, 1 of 3 and not wide,
    catches a weakened half); 904 ended on 29 April, and 905 starting after it ends (run today, start before the end);
    906 of reward type 2 with the kind fixed_price, and 907 of reward type 6 (the kind follows the reward type); 908 at
    a minimum spend of 0.00; 909 its lowest store price above the median, and 910 fixed-price with a count of stores
    priced (the stores' prices in order, the counts on percent off only); 911 at 3 counted stores where the report
    says 2. Shufersal's table gains Universe's promotion 60 on U1 under a second group, which is unique, so it fails
    only a uniqueness without the group; promotion_reach counts a promotion once however many groups name it."""
    day = f"date={day_of(LAST).isoformat()}"
    _rewrite(tables / "prices" / "chain=shufersal" / day / "prices.parquet",
             f"insert into staged select * from staged where store = '81' and code = '{U1}'",
             f"update staged set file = '{SECOND_FILE}' where store = '82' and code = '{U2}'",
             f"update staged set file = '{PRICE_FILE}' where store = '83'",
             f"update staged set file = '{DAY_BEFORE_FILE}' where store = '81'",
             *(f"insert into staged select * replace ('{code}' as code, '{code}' as code_norm, {flag} as gs1) "
               f"from staged where store = '82' and code = '{U7}'"
               for code, flag in ((WRONG_CHECK, "true"), (VALID_13, "false"), (LONG, "false"))))
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
             _at_city("911", universe, {"counted": "3"}))
    _rewrite(universe, "insert into staged select * replace ('2' as group_id) from staged "
                       f"where \"column\" = 'shufersal-universe' and promotion_id = '60' and code = '{U1}'")


@pytest.fixture(scope="module")
def BAD_VARS(golden, GOLDEN_VARS, tmp_path_factory) -> dict:
    """The bad-rows build's vars: GOLDEN_VARS on a copy of the golden's tables and published files, the bad rows
    planted in the copy. Shared by every test in the module, as GOLDEN_VARS is: copy it, never change it."""
    root = tmp_path_factory.mktemp("dbt-bad")
    tables, site = root / "tables", root / "site"
    shutil.copytree(golden.tables, tables)
    shutil.copytree(golden.site, site)
    plant_bad_rows(tables, site)
    return {**GOLDEN_VARS, "tables": str(tables), "site": str(site)}


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

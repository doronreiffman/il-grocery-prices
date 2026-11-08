"""One chain's day for the shopper site (`shopper.extract`): its prices, promotions and items tables in that order, by
column; a promotion format change or a bad promotion file leaving the prices and items standing (P10; the plan's
Task 7 and the second pre-flight's S2, S8 and S18).

Most tests run over the golden day of tests/test_build.py with one promotion file per store (`with_promotions`), and
place its Carrefour stores by a table of their own (GOLDEN_COLUMNS, S18), never by the hand-kept one.
"""
import gzip
import json
import logging
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from basket.chains import SLUGS
from basket.extract import extract, table_path
from basket.pricefile import BadPriceFile
from basket.stores import NoStoreList
from shopper import extract as shop_extract
from shopper.extract import ChainDayReport, extract_chain_day, main
from shopper.items import items_path, texts_path
from shopper.promos import promotions_path
from test_build import CHAIN_IDS, DAY, EGGS, MILK, PASTA, PRICES, SUB_CHAINS, golden_tree, price_file, store_list
from test_promos import _group, _item, _promotion

# The golden day's Carrefour stores placed by a table of the test's own (S18): store 1 in City, store 2 in no column.
# The hand-kept table has store 2 in Market and store 1 in none, so a step that took it would show.
GOLDEN_COLUMNS = {"1": "carrefour-city"}
COLUMN = {"shufersal": "shufersal-sheli", "ramilevy": "ramilevy", "osherad": "osherad",
          "carrefour": "carrefour-city", "yochananof": "yochananof"}   # the column the golden day's stores are in
IN_COLUMN = {slug: ["001", "002"] for slug in SLUGS} | {"carrefour": ["001"]}   # its stores there, as named
EVERY_COLUMN = {"shufersal": ["shufersal-deal", "shufersal-express", "shufersal-sheli", "shufersal-universe"],
                "carrefour": ["carrefour-city", "carrefour-market"]}


def promo_file_name(slug: str, store: str, sub_chain: str | None = None) -> str:
    return f"PromoFull{CHAIN_IDS[slug]}-{sub_chain or SUB_CHAINS[slug]}-{store}-20260101-080000.gz"


def promo_file(slug: str, store: str, *promotions: str, extra_root: str = "") -> bytes:
    """A gzipped full promotion file of the chain's store holding `promotions`, its root the fields every chain's
    files carry (`extra_root` added to it)."""
    xml = (f"<Root><ChainID>{CHAIN_IDS[slug]}</ChainID><SubChainID>{SUB_CHAINS[slug]}</SubChainID>"
           f"<StoreID>{store}</StoreID><BikoretNo>0</BikoretNo><Promotions>" + "".join(promotions) + "</Promotions>"
           + extra_root + "</Root>")
    return gzip.compress(xml.encode(), mtime=0)


def on(code: str, promotion_id: str = "1", **item) -> str:
    """A promotion running on the golden day: a fixed price of 5.00 on `code`, or the link `item` gives."""
    return _promotion(promotion_id, _group(items=[_item(code, **({"price": "5.00"} | item))]), start="2025-12-01",
                      end="2026-01-31")


ON_MILK = on(MILK)


def day_folder(data: Path, slug: str) -> Path:
    return data / "raw" / f"chain={slug}" / f"date={DAY.isoformat()}"


def with_promotions(data: Path) -> Path:
    """The golden day's data folder with one promotion file per store of each chain, each holding ON_MILK."""
    for slug, stores in PRICES.items():
        for store in stores:
            (day_folder(data, slug) / promo_file_name(slug, store)).write_bytes(promo_file(slug, store, ON_MILK))
    return data


def read(path: Path, order: str) -> list[dict]:
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT * FROM read_parquet('{path}', hive_partitioning = false) ORDER BY {order}")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def names_in(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


@pytest.fixture
def data(tmp_path):
    return with_promotions(golden_tree(tmp_path / "golden"))


def run_day(data: Path, slug: str, **more) -> ChainDayReport:
    return extract_chain_day(data / "raw", slug, DAY, data / "tables", table=GOLDEN_COLUMNS, **more)


# ---- the three tables ----

@pytest.mark.parametrize("slug", SLUGS)
def test_extract_chain_day_writes_the_three_tables(data, tmp_path, slug):
    tables = data / "tables"
    report = run_day(data, slug)
    column, stores = COLUMN[slug], IN_COLUMN[slug]
    # the prices table first, as basket.extract writes it
    assert report.prices == extract(data / "raw", slug, DAY, tmp_path / "alone")
    assert table_path(tables, slug, DAY).read_bytes() == table_path(tmp_path / "alone", slug, DAY).read_bytes()
    # the promotions table, counted at the column's stores with a price file
    assert names_in(promotions_path(tables, slug, DAY).parent) == ["promotions.parquet", "report.json", "texts.parquet"]
    assert report.promotions.files == [promo_file_name(slug, store) for store in stores]
    assert report.promotions.counted == {key: len(stores) if key == column else 0
                                         for key in EVERY_COLUMN.get(slug, [slug])}
    assert [(row["column"], row["promotion_id"], row["code"], row["stores"], row["counted"], row["wide"])
            for row in read(promotions_path(tables, slug, DAY), '"column", code')] == [
        (column, "1", MILK, len(stores), len(stores), True)]
    assert [row["promotion_id"] for row in read(texts_path(tables, slug, DAY), "promotion_id")] == ["1"]
    # the items table, its column's codes, MILK on promotion
    rows = read(items_path(tables, slug, DAY), '"column", code')
    assert [(row["column"], row["code"], row["on_promotion"]) for row in rows] == [
        (column, code, code == MILK) for code in sorted((MILK, PASTA, EGGS))]
    assert report.items.promotions_error is None and report.items.texts == 1
    assert report.items.columns[column].counted == len(stores) and not report.items.columns[column].promo_hole
    assert json.loads((items_path(tables, slug, DAY).parent / "report.json").read_text())["promotions_error"] is None
    assert set(report.seconds) == {"prices", "promotions", "items"}


def test_carrefours_columns_are_the_table_given(data):
    """Store 1 in City by the test's table, store 2 in none: store 2's promotion file is passed over as a counted
    store in no column, and its prices are in no row."""
    tables = data / "tables"
    report = run_day(data, "carrefour")
    assert (report.promotions.counted, report.promotions.outside) == (
        {"carrefour-city": 1, "carrefour-market": 0}, [promo_file_name("carrefour", "002")])
    assert {(row["column"], row["listed"]) for row in read(items_path(tables, "carrefour", DAY), "code")} == {
        ("carrefour-city", Decimal(price)) for price in PRICES["carrefour"]["001"]}   # store 1's prices alone
    assert report.items.outside == ["2"]


def test_the_columns_are_the_days_store_list(tmp_path):
    """Shufersal's list puts store 1 in sub-chain 1 (Sheli), store 2 in 2 (Deal), store 6 in 6 (Yesh Chesed, in no
    column) and store 779 in 7 (Express), its files named under Be's 005, as store 779's were on 2026-11-02: rows in
    Sheli and Deal, none for store 6's code; store 779 is a member of Express that is never counted, so its promotion
    file is passed over unread (Call 7; the second pre-flight's N13), and store 6's is passed over as a counted store in
    no column (S2). Store 150, in sub-chain 15 (in no column) with a promotion file and no price file, is not counted:
    its file is passed over, not listed as a counted store's."""
    data = tmp_path / "data"
    folder = day_folder(data, "shufersal")
    folder.mkdir(parents=True)
    on_list = {"1": ["1"], "2": ["2"], "6": ["6"], "7": ["779"], "15": ["150"]}
    stores = "".join(f"<SubChain><SubChainID>{sub}</SubChainID><Stores>" + "".join(
        f"<Store><StoreID>{store}</StoreID><StoreType>1</StoreType><StoreName>סניף</StoreName></Store>"
        for store in ids) + "</Stores></SubChain>" for sub, ids in on_list.items())
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><Chain><ChainID>{CHAIN_IDS["shufersal"]}</ChainID><SubChains>'
           f"{stores}</SubChains></Chain>")
    (folder / store_list("shufersal")[0]).write_bytes(gzip.compress(xml.encode(), mtime=0))
    listing = {("001", "001"): (MILK, "6.90", "10"), ("002", "002"): (PASTA, "5.50", "20"),
               ("006", "006"): (EGGS, "12.90", "60"), ("005", "779"): (MILK, "7.00", "79")}
    for (sub, store), (code, price, promotion_id) in listing.items():
        prices = tuple(price if listed == code else None for listed in (MILK, PASTA, EGGS))
        (folder / f"PriceFull{CHAIN_IDS['shufersal']}-{sub}-{store}-20260101-080000.gz").write_bytes(
            price_file("shufersal", prices))
        (folder / promo_file_name("shufersal", store, sub)).write_bytes(
            promo_file("shufersal", store, on(code, promotion_id)))
    (folder / promo_file_name("shufersal", "150", "015")).write_bytes(promo_file("shufersal", "150", on(MILK, "15")))
    tables = data / "tables"
    report = extract_chain_day(data / "raw", "shufersal", DAY, tables)
    promo = report.promotions
    assert promo.counted == {"shufersal-deal": 1, "shufersal-express": 0, "shufersal-sheli": 1,
                             "shufersal-universe": 0}
    assert promo.files == [promo_file_name("shufersal", "001", "001"), promo_file_name("shufersal", "002", "002")]
    assert promo.outside == [promo_file_name("shufersal", "006", "006")]
    assert promo.passed_over == sorted([promo_file_name("shufersal", "150", "015"),
                                        promo_file_name("shufersal", "779", "005")])
    assert [(row["column"], row["promotion_id"], row["code"]) for row in
            read(promotions_path(tables, "shufersal", DAY), '"column"')] == [
        ("shufersal-deal", "20", PASTA), ("shufersal-sheli", "10", MILK)]
    assert [(row["column"], row["code"], row["on_promotion"]) for row in
            read(items_path(tables, "shufersal", DAY), '"column"')] == [
        ("shufersal-deal", PASTA, True), ("shufersal-sheli", MILK, True)]
    express = report.items.columns["shufersal-express"]
    assert (express.included, express.with_file, express.hole, express.counted) == (1, 0, True, 0)
    assert report.items.outside == ["6", "150"]   # the included stores in no column, a file or not


# ---- when the promotions cannot be read ----

FORMAT_CHANGES = {   # store 2's file, and the error each gives: the chain, then the field and its value
    "an unknown RewardType": (dict(promotions=[on(MILK, reward="99")]), "ramilevy: RewardType 99 not seen in the "
                                                                          "chain's files"),
    "a start that is no date": (dict(promotions=[_promotion("1", start="2025-12-xx")]),
                                "ramilevy: PromotionStartDateTime '2025-12-xxT00:00:00.000' is not a date"),
    "a root field added": (dict(promotions=[ON_MILK], extra_root="<Extra>1</Extra>"),
                           f"ramilevy: {promo_file_name('ramilevy', '002')}: root fields changed: added ['Extra'], "
                           "missing []"),
    "a MinQty the items table cannot hold": (dict(promotions=[on(MILK, "2", reward="1", min_qty="1.2345",
                                                                 price="3.00")]),
                                             "ramilevy: MinQty '1.2345' does not fit the items table"),
}


@pytest.mark.parametrize("change", sorted(FORMAT_CHANGES))
def test_a_format_change_keeps_prices_and_items_and_names_the_field(data, caplog, change):
    """The chain's promotions stop, not the chain: the prices table stands, the items table is written with no
    promotions and the error, which names the chain, the field and its value, and is logged at ERROR. An earlier
    run's promotions and texts tables of the day are gone from the folder, which holds only its report, naming the
    error (the first pre-flight's S7). The MinQty case is refused by the items table, after the promotions table was
    written."""
    tables = data / "tables"
    run_day(data, "ramilevy")   # an earlier run of the day, whose promotions were read
    assert promotions_path(tables, "ramilevy", DAY).exists() and texts_path(tables, "ramilevy", DAY).exists()
    fields, error = FORMAT_CHANGES[change]
    (day_folder(data, "ramilevy") / promo_file_name("ramilevy", "002")).write_bytes(
        promo_file("ramilevy", "002", *fields["promotions"], extra_root=fields.get("extra_root", "")))
    with caplog.at_level(logging.ERROR, logger="shopper.extract"):
        report = run_day(data, "ramilevy")
    assert table_path(tables, "ramilevy", DAY).exists() and report.prices.rows == 6
    folder = promotions_path(tables, "ramilevy", DAY).parent
    assert names_in(folder) == ["report.json"]
    assert json.loads((folder / "report.json").read_text()) == {"slug": "ramilevy", "day": "2026-01-01",
                                                                "promotions_error": error}
    assert report.promotions is None and report.items.promotions_error == error
    rows = read(items_path(tables, "ramilevy", DAY), "code")
    assert [(row["code"], row["on_promotion"], row["promotions"]) for row in rows] == [
        (code, None, None) for code in sorted((MILK, PASTA, EGGS))]
    assert json.loads((items_path(tables, "ramilevy", DAY).parent / "report.json").read_text())[
        "promotions_error"] == error
    assert report.items.columns["ramilevy"].promo_hole
    assert report.summary()["promotions_error"] == error and report.summary()["promotions"] is None
    assert report.summary()["columns"] == {"ramilevy": {"items": 3, "wide": 3, "hole": False, "promo_hole": True}}
    [record] = [r for r in caplog.records if r.name == "shopper.extract"]
    assert record.levelno == logging.ERROR and error in record.getMessage()


@pytest.mark.parametrize("body", [b"<html>blocked</html>", gzip.compress(b"<Root><Promotions>", mtime=0)[:20]])
def test_a_bad_promotion_file_keeps_prices_and_items_and_names_the_file(data, body):
    """A promotion file that does not read (an HTML page, a gzip cut short) stops the chain's promotions as a format
    change does, its error naming the chain and the file (the second pre-flight's S8)."""
    tables = data / "tables"
    name = promo_file_name("osherad", "001")
    (day_folder(data, "osherad") / name).write_bytes(body)
    report = run_day(data, "osherad")
    assert report.items.promotions_error.startswith(f"osherad: {name}: ")
    assert names_in(promotions_path(tables, "osherad", DAY).parent) == ["report.json"]
    assert items_path(tables, "osherad", DAY).exists() and table_path(tables, "osherad", DAY).exists()


def test_a_bad_price_file_still_stops_the_chain(data):
    """B1 stands for prices: a price file that does not read stops the chain before anything else is written."""
    name = "PriceFull7290103152017-001-003-20260101-090000.gz"
    (day_folder(data, "osherad") / name).write_bytes(b"<html>blocked</html>")
    with pytest.raises(BadPriceFile, match=name):
        run_day(data, "osherad")
    assert not (data / "tables" / "promotions").exists() and not (data / "tables" / "items").exists()


def test_no_store_list_stops_the_chain_after_its_prices(data):
    """An earlier run's promotions and items files of the day are gone too: the folders hold only this run's."""
    run_day(data, "yochananof")   # an earlier run of the day, with its store list
    (day_folder(data, "yochananof") / store_list("yochananof")[0]).unlink()
    with pytest.raises(NoStoreList, match="'yochananof'"):
        run_day(data, "yochananof")
    tables = data / "tables"
    assert names_in(table_path(tables, "yochananof", DAY).parent) == ["prices.parquet", "report.json"]
    assert names_in(promotions_path(tables, "yochananof", DAY).parent) == []
    assert names_in(items_path(tables, "yochananof", DAY).parent) == []


def test_a_failure_after_the_promotions_leaves_only_this_runs_files(data, monkeypatch):
    """A failure nothing catches stops the chain; the day's folders hold what this run wrote, never an earlier run's
    texts or items table beside it."""
    tables = data / "tables"
    run_day(data, "osherad")   # an earlier run of the day

    def failing(*args, **kwargs):
        raise RuntimeError("the items table could not be written")

    monkeypatch.setattr(shop_extract, "write_items", failing)
    with pytest.raises(RuntimeError):
        run_day(data, "osherad")
    assert names_in(promotions_path(tables, "osherad", DAY).parent) == ["promotions.parquet", "report.json"]
    assert names_in(items_path(tables, "osherad", DAY).parent) == []


# ---- the seconds, the summary and the command ----

def test_each_step_is_timed(data):
    ticks = iter([10.0, 11.5, 14.0, 20.25])
    report = run_day(data, "osherad", timer=lambda: next(ticks))
    assert report.seconds == {"prices": 1.5, "promotions": 2.5, "items": 6.25}


def test_the_summary_counts_the_promotions_and_each_columns_items(data):
    report = run_day(data, "shufersal")
    promo = report.promotions
    assert report.summary() == {
        "promotions": {"files": 2, "passed_over": 0, "outside": 0, "promotions": promo.promotions, "coupons": 0,
                       "gifts": 0, "basket_rewards": 0, "dropped_links": 0, "expired": 0, "before_start": 0,
                       "rows": 1},
        "promotions_error": None,
        "columns": {key: {"items": 3 if key == "shufersal-sheli" else 0, "wide": 3 if key == "shufersal-sheli" else 0,
                          "hole": key != "shufersal-sheli", "promo_hole": False}   # no counted store, no hole
                    for key in EVERY_COLUMN["shufersal"]},
        "promotion_seconds": round(report.seconds["promotions"], 1), "items_seconds": round(report.seconds["items"], 1)}
    assert promo.promotions == 2


def test_main_writes_each_chains_tables_and_prints_counts_only(data, capsys):
    assert main(["--data", str(data), "--day", "2026-01-01", "--chains", "osherad", "yochananof"]) == 0
    lines = capsys.readouterr().out.splitlines()
    printed = [json.loads(line) for line in lines]
    assert [(line["chain"], line["day"], line["rows"], line["promotions_error"]) for line in printed] == [
        ("osherad", "2026-01-01", 6, None), ("yochananof", "2026-01-01", 5, None)]
    assert printed[1]["columns"] == {"yochananof": {"items": 3, "wide": 3, "hole": False, "promo_hole": False}}
    assert all(MILK not in line and "מבצע" not in line for line in lines)   # counts only: no code, no text
    assert items_path(data / "tables", "yochananof", DAY).exists()


def test_main_stops_on_a_chain_without_a_store_list(data, capsys):
    (day_folder(data, "osherad") / store_list("osherad")[0]).unlink()
    assert main(["--data", str(data), "--day", "2026-01-01", "--chains", "osherad"]) == 1
    assert "'osherad'" in capsys.readouterr().err


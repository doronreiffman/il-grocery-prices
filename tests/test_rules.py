"""The rules: the day's tables become each chain's price for every basket item and its basket total."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from basket.barcode import is_gs1, normalize
from basket.basket_file import load_basket
from basket.extract import COLUMNS, Row, table_path, write_table
from basket.rules import (ChainDay, ChainPrice, ChainResult, Headline, LeftOut, MissingTable, apply_filters,
                          chain_day, chain_prices, chain_sizes, gap_percent, open_day, price_basket,
                          stores_with_file, stores_with_file_keys)
from basket.units import Size

BASKET = load_basket(Path(__file__).parent / "baskets" / "basket-test.json", min_items=1)
MILK, PASTA, EGGS = (item.code for item in BASKET.items)  # 1000 gml, 500 gml, 12 unit
CODES = [MILK, PASTA, EGGS]
CHAINS = ("a", "b", "c", "d", "e")
DAY = date(2026, 1, 1)
NOT_STATED = ("0", "לא ידוע")


def row(store: str, code: str, price: str | None, sub_chain: str | None = "1",
        size: tuple[str, str] = NOT_STATED) -> Row:
    """One row of a day's table; `size` is the (quantity, unit) the file states."""
    quantity, unit = size
    return Row(store=store, sub_chain=sub_chain, code=code, code_norm=normalize(code), gs1=is_gs1(code),
               name="מוצר", price=None if price is None else Decimal(price), quantity=quantity, unit=unit,
               unit_of_measure="", updated="2026-01-01 00:00", file=f"PriceFull-{store}.gz")


def day_tables(tmp_path: Path, chains: dict[str, list[Row]]) -> Path:
    """One table per chain for DAY under tmp_path/tables; the tables directory."""
    tables = tmp_path / "tables"
    for slug, rows in chains.items():
        write_table(rows, table_path(tables, slug, DAY))
    return tables


def opened(tmp_path: Path, chains: dict[str, list[Row]], included: dict[str, set[str]],
           excluded_sub_chains: dict[str, frozenset[str]] | None = None) -> duckdb.DuckDBPyConnection:
    """The day of `chains` opened and filtered; no sub-chain left out unless given."""
    con = open_day(day_tables(tmp_path, chains), DAY, list(chains))
    apply_filters(con, included, excluded_sub_chains or {slug: frozenset() for slug in chains})
    return con


def price(median: str, listing: int = 4) -> ChainPrice:
    """A chain price whose stores all list the same price."""
    value = Decimal(median)
    return ChainPrice(median=value, low=value, high=value, listing=listing)


def every_item_at(slugs: str, median: str = "5.00", listing: int = 4) -> dict[tuple[str, str], ChainPrice]:
    """Every basket item at each chain of `slugs`, at one price."""
    return {(slug, code): price(median, listing) for slug in slugs for code in CODES}


def test_filters_drop_excluded_stores_placeholders_and_null_prices(tmp_path):
    chains = {"a": [row("1", MILK, "5.90"), row("1", PASTA, "0.01"), row("1", EGGS, "0.02"),
                    row("2", MILK, None), row("2", PASTA, "0.00"), row("3", MILK, "4.00")]}
    with opened(tmp_path, chains, {"a": {"1", "2"}}) as con:
        columns = [column[0] for column in con.execute("SELECT * FROM prices LIMIT 0").description]
        kept = con.execute("SELECT chain, store, code, price FROM rows ORDER BY store, code").fetchall()
    assert columns == ["chain", *(name for name, _ in COLUMNS)]
    assert kept == [("a", "1", MILK, Decimal("5.90")), ("a", "1", EGGS, Decimal("0.02"))]


def test_rows_of_an_excluded_sub_chain_drop_by_the_file_name(tmp_path):
    chains = {"a": [row("7", MILK, "5.90", sub_chain="5"), row("8", MILK, "6.10", sub_chain="1"),
                    row("9", MILK, "6.30", sub_chain=None)],
              "b": [row("7", MILK, "5.90", sub_chain="5")]}
    included = {"a": {"7", "8", "9"}, "b": {"7"}}
    with opened(tmp_path, chains, included, {"a": frozenset({"5"}), "b": frozenset()}) as con:
        kept = con.execute("SELECT chain, store FROM rows ORDER BY chain, store").fetchall()
        with_file = stores_with_file(con, included)
    assert kept == [("a", "8"), ("a", "9"), ("b", "7")]
    assert with_file == {"a": 3, "b": 1}


def test_stores_with_file_counts_before_the_placeholder_rule(tmp_path):
    chains = {"a": [row("1", MILK, "5.90"), row("2", MILK, "0.01"), row("3", MILK, "4.00")],
              "b": [row("1", MILK, "5.90")]}
    included = {"a": {"1", "2"}, "b": {"1", "9"}}
    with opened(tmp_path, chains, included) as con:
        with_file = stores_with_file(con, included)
        listed = con.execute("SELECT chain, store FROM rows ORDER BY chain, store").fetchall()
    assert with_file == {"a": 2, "b": 1}
    assert listed == [("a", "1"), ("b", "1")]


def test_stores_with_file_keys_lists_the_stores(tmp_path):
    chains = {"a": [row("10", MILK, "5.90"), row("2", MILK, "6.10"), row("2", PASTA, "3.00"), row("9", MILK, "0.01"),
                    row("3", MILK, "4.00")],
              "b": []}
    included = {"a": {"2", "9", "10", "11"}, "b": {"1"}}
    with opened(tmp_path, chains, included) as con:
        keys = stores_with_file_keys(con, included)
        counts = stores_with_file(con, included)
    assert keys == {"a": ("2", "9", "10"), "b": ()}  # by number; store 3 is not included, store 11 sent no file
    assert counts == {"a": 3, "b": 0}


def test_median_is_exact_for_even_and_odd_counts(tmp_path):
    chains = {"a": [row("1", MILK, "7.00"), row("2", MILK, "5.00"),
                    row("1", PASTA, "20.00"), row("2", PASTA, "5.00"), row("3", PASTA, "7.00"),
                    row("1", EGGS, "5.10"), row("2", EGGS, "5.05")]}
    with opened(tmp_path, chains, {"a": {"1", "2", "3"}}) as con:
        prices = chain_prices(con, CODES)
    assert prices == {
        ("a", MILK): ChainPrice(Decimal("6.00"), Decimal("5.00"), Decimal("7.00"), 2),
        ("a", PASTA): ChainPrice(Decimal("7.00"), Decimal("5.00"), Decimal("20.00"), 3),
        ("a", EGGS): ChainPrice(Decimal("5.075"), Decimal("5.05"), Decimal("5.10"), 2),
    }
    assert str(prices[("a", EGGS)].median) == "5.075"  # exact: no float on the way


def test_median_ignores_an_outlier(tmp_path):
    chains = {"a": [row(store, MILK, value) for store, value in
                    (("1", "10000.00"), ("2", "5.90"), ("3", "5.90"), ("4", "5.90"))]}
    with opened(tmp_path, chains, {"a": {"1", "2", "3", "4"}}) as con:
        prices = chain_prices(con, [MILK])
    assert prices == {("a", MILK): ChainPrice(Decimal("5.90"), Decimal("5.90"), Decimal("10000.00"), 4)}


def test_code_matched_by_normalized_form(tmp_path):
    chains = {"a": [row("1", "0" + MILK, "5.90")]}
    with opened(tmp_path, chains, {"a": {"1"}}) as con:
        by_basket_code = chain_prices(con, [MILK])
        by_padded_code = chain_prices(con, ["0" + MILK])
    assert by_basket_code == by_padded_code == {("a", MILK): price("5.90", listing=1)}
    result = price_basket(BASKET, [chain_day("a", 1, 1)], by_basket_code, {})
    assert result.chains["a"].items == {MILK: price("5.90", listing=1)}


def test_chain_sizes_take_the_most_common_readable_size_ties_to_the_smaller(tmp_path):
    litre, thousand_ml, half_kilo = ("1", "ליטר"), ("1000", "מיליליטר"), ("500", "גרם")
    milk = [("1", litre), ("2", litre), ("3", thousand_ml), ("4", thousand_ml),  # 1000 gml, four rows over two pairs
            ("5", half_kilo), ("6", half_kilo), ("7", half_kilo),  # the most common readable pair, three rows
            ("8", NOT_STATED), ("9", NOT_STATED), ("10", NOT_STATED), ("11", NOT_STATED)]
    chains = {"a": [row(store, MILK, "5.00", size=size) for store, size in milk]
              + [row("1", PASTA, "5.00", size=half_kilo), row("2", PASTA, "5.00", size=("400", "גרם"))]
              + [row("1", EGGS, "5.00", size=("1", "יחידות")), row("2", EGGS, "5.00")]}
    with opened(tmp_path, chains, {"a": {str(store) for store in range(1, 12)}}) as con:
        sizes = chain_sizes(con, CODES)
    assert sizes == {("a", MILK): Size(Decimal(1000), "gml"), ("a", PASTA): Size(Decimal(400), "gml"),
                     ("a", EGGS): None}


def test_coverage_guard_half_of_stores_with_file():
    with_file = {"a": 4, "b": 4, "c": 3, "d": 4, "e": 4}
    days = [chain_day(slug, count, count) for slug, count in with_file.items()]
    listing = {(slug, code): count for slug, count in with_file.items() for code in CODES}
    listing |= {("b", MILK): 2, ("b", PASTA): 1, ("c", EGGS): 1}
    del listing[("d", EGGS)]
    prices = {key: price("5.00", count) for key, count in listing.items()}
    result = price_basket(BASKET, days, prices, {})
    assert result.items_in == (MILK,)
    assert result.left_out == (LeftOut(PASTA, "coverage", {"b": "1 of 4"}),
                               LeftOut(EGGS, "coverage", {"c": "1 of 3", "d": "0 of 4"}))
    assert all(chain.total == Decimal("5.00") for chain in result.chains.values())


def test_size_guard_only_a_stated_size_can_block():
    days = [chain_day(slug, 4, 4) for slug in CHAINS]
    sizes = {(slug, item.code): item.size for slug in CHAINS for item in BASKET.items}
    sizes |= {("b", MILK): Size(Decimal(500), "gml"), ("c", MILK): None, ("c", PASTA): None,
              ("e", EGGS): Size(Decimal(6), "unit")}
    del sizes[("d", PASTA)]
    result = price_basket(BASKET, days, every_item_at("abcde"), sizes)
    assert result.items_in == (PASTA,)
    assert result.left_out == (LeftOut(MILK, "size", {"b": "500 gml"}), LeftOut(EGGS, "size", {"e": "6 unit"}))


def test_chain_with_too_few_files_is_out_of_ranking_but_priced():
    assert chain_day("e", 3, 1) == ChainDay("e", included=3, with_file=1, in_ranking=False)
    assert chain_day("a", 4, 2) == ChainDay("a", included=4, with_file=2, in_ranking=True)
    days = [chain_day(slug, 4, 4) for slug in "abcd"] + [chain_day("e", 3, 1)]
    prices = every_item_at("abcd") | {("e", MILK): price("4.00", listing=1), ("e", EGGS): price("9.00", listing=1)}
    sizes = {("e", EGGS): Size(Decimal(6), "unit")}  # would block eggs, were e in the ranking
    result = price_basket(BASKET, days, prices, sizes)
    assert result.items_in == (MILK, PASTA, EGGS)
    assert result.left_out == ()
    assert result.chains["e"] == ChainResult(total=None, rank=None,
                                             items={MILK: price("4.00", listing=1), EGGS: price("9.00", listing=1)})
    assert result.chains["a"] == ChainResult(total=Decimal("15.00"), rank=1, items={code: price("5.00") for code in CODES})


def test_empty_chain_table_gives_zero_with_file(tmp_path):
    chains = {slug: [row(store, code, median, size=size) for store in ("1", "2")
                     for code, size in ((MILK, ("1", "ליטר")), (PASTA, ("500", "גרם")), (EGGS, ("12", "יחידות")))]
              for slug, median in (("a", "5.00"), ("b", "6.00"), ("c", "7.00"), ("d", "8.00"))}
    chains["e"] = []
    included = {slug: {"1", "2"} for slug in CHAINS}
    with opened(tmp_path, chains, included) as con:
        with_file = stores_with_file(con, included)
        prices = chain_prices(con, CODES)
        sizes = chain_sizes(con, CODES)
    assert with_file == {"a": 2, "b": 2, "c": 2, "d": 2, "e": 0}
    days = [chain_day(slug, len(included[slug]), with_file[slug]) for slug in CHAINS]
    assert days[-1] == ChainDay("e", included=2, with_file=0, in_ranking=False)
    assert chain_day("e", 0, 0).in_ranking is False  # no included store at all
    result = price_basket(BASKET, days, prices, sizes)
    assert result.items_in == (MILK, PASTA, EGGS)
    assert [(slug, chain.total, chain.rank) for slug, chain in result.chains.items()] == [
        ("a", Decimal("15.00"), 1), ("b", Decimal("18.00"), 2), ("c", Decimal("21.00"), 3),
        ("d", Decimal("24.00"), 4), ("e", None, None)]
    assert result.chains["e"].items == {}
    assert result.headline == Headline("a", Decimal("15.00"), "d", Decimal("24.00"), 60)


def test_fewer_than_three_chains_no_headline():
    two = [chain_day("a", 4, 4), chain_day("b", 4, 4)] + [chain_day(slug, 9, 4) for slug in "cde"]
    result = price_basket(BASKET, two, every_item_at("abcde"), {})
    assert result.headline is None
    assert [(slug, chain.rank) for slug, chain in result.chains.items()] == [
        ("a", 1), ("b", 1), ("c", None), ("d", None), ("e", None)]
    three = [chain_day("a", 4, 4), chain_day("b", 4, 4), chain_day("c", 4, 4)] + [chain_day(s, 9, 4) for s in "de"]
    assert price_basket(BASKET, three, every_item_at("abcde"), {}).headline == Headline(
        "a", Decimal("15.00"), "c", Decimal("15.00"), 0)


def test_totals_rank_and_gap():
    def day_with_milk_at(milk: dict[str, str]):
        """Pasta 25.00 and eggs 15.00 at every chain, milk as given; e out of the ranking; days in reverse order."""
        prices = {(slug, code): price(median, 1) for slug in CHAINS for code, median in ((PASTA, "25.00"), (EGGS, "15.00"))}
        prices |= {(slug, MILK): price(median, 1) for slug, median in milk.items()}
        days = [chain_day("e", 3, 1)] + [chain_day(slug, 1, 1) for slug in "dcba"]
        return price_basket(BASKET, days, prices, {})

    result = day_with_milk_at({"a": "60.00", "b": "87.40", "c": "60.00", "d": "70.00", "e": "1.00"})
    assert [(slug, chain.total, chain.rank) for slug, chain in result.chains.items()] == [
        ("a", Decimal("100.00"), 1), ("c", Decimal("100.00"), 1), ("d", Decimal("110.00"), 3),
        ("b", Decimal("127.40"), 4), ("e", None, None)]
    assert result.headline == Headline("a", Decimal("100.00"), "b", Decimal("127.40"), 27)
    assert day_with_milk_at({"a": "60.00", "b": "87.50", "c": "60.00", "d": "70.00"}).headline.gap_percent == 28
    assert gap_percent(Decimal("100.00"), Decimal("126.50")) == 27  # half up, not to even


def test_missing_table_raises_naming_the_chain(tmp_path):
    tables = day_tables(tmp_path, {"a": [], "b": []})
    with pytest.raises(MissingTable, match="chain 'c'"):
        open_day(tables, DAY, ["a", "b", "c"])


def test_no_items_counted_gives_no_totals_and_no_headline():
    days = [chain_day(slug, 4, 4) for slug in "dcba"] + [chain_day("e", 3, 1)]
    prices = every_item_at("abcd") | {("b", PASTA): price("5.00", listing=1)}
    del prices[("c", EGGS)]
    sizes = {("a", MILK): Size(Decimal(500), "gml")}
    result = price_basket(BASKET, days, prices, sizes)
    assert result.items_in == ()
    assert result.left_out == (LeftOut(MILK, "size", {"a": "500 gml"}), LeftOut(PASTA, "coverage", {"b": "1 of 4"}),
                               LeftOut(EGGS, "coverage", {"c": "0 of 4"}))
    assert [(slug, chain.total, chain.rank) for slug, chain in result.chains.items()] == [
        (slug, None, None) for slug in CHAINS]
    assert result.chains["a"].items == {code: price("5.00") for code in CODES}  # prices still shown
    assert result.headline is None
    assert [day.slug for day in days if day.in_ranking] == ["d", "c", "b", "a"]  # B8 unchanged

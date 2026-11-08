"""The rules: one day's tables become each chain's price for every basket item and its basket total.

Rows (B2, B4). The chains' tables for the day are read as one view, `prices`, each row marked with
its chain's slug; a chain whose table is absent stops the day with MissingTable (an extraction that
found no files writes an empty table, which is not absent). A row counts, in the view `rows`, when
its store is one of the chain's included stores, its sub-chain is not one the chain leaves out, and
its price is above ₪0.01. The sub-chain is the one in the row's file name, which wins over the store
list's; a row with no sub-chain is never left out by it. A price of ₪0.01 or less is a placeholder,
and a row with no price says nothing. An included store has a file that day when it has a row in
`prices` whose sub-chain the chain does not leave out, before the placeholder rule, so a store whose
only rows are placeholders still published one, and a store the list puts in a kept sub-chain but whose
file name puts it in a sub-chain left out (Shufersal's store 779 on 2026-11-02: sub-chain 7 in the
list, 005 in its file name) did not; the stores with a file are listed by key as numbers, as the
extraction sorts them ("9" before "10").

Chain price (B5). A chain's price for an item is the median of the prices of its rows listing the
item, matched by the code with leading zeros stripped: the middle price over the stores listing it,
or the mean of the two middle ones, worked out in Decimal from the exact prices, never through
floating point. A store counts once: one that lists the item under more than one code with the same
digits once leading zeros are stripped ("0" + code and the code) is double-coded, and its price is
the lowest of its rows'. The lowest and highest store prices, the number of stores listing the item
and the number of them double-coded are kept beside it.

Which rows. Prices (B5) and sizes (B7) are read from the view `rows` unless another view is named, keyed by its
`chain` column, for the codes asked for, or for every code in the view when given none: the shopper site names a view
of the same rows whose `chain` is a store format (`shopper.items`), so both rules hold per format with no second copy.

Chain size (B7). A chain's size for an item is the most common readable size over its rows
(`basket.units.normal_size`), each size counted over every row that states it however it is spelled
("1 ליטר" and "1000 מיליליטר" are one size); a tie goes to the smaller amount. It is None when no row
states a readable size.

A chain's day (B8). A chain is in the ranking when it has included stores and at least half of them
have a file that day. A chain out of the ranking keeps its item prices but has no total and no rank,
and it neither keeps an item out nor lets one in.

Guards (B6, B7). An item counts that day when, at every chain in the ranking, at least half of the
chain's stores with a file list it (coverage, `covers`), and no chain in the ranking states a size other than
the basket's (size); a chain that states none does not count against it. Coverage is checked first.
An item that fails is left out of every chain's total and named with the chains that kept it out and
their share ("1 of 4") or size ("500 gml").

Totals (B9). A chain's total is the sum of its prices for the items that count. Chains rank from the
lowest total; equal totals share a rank, and the next rank counts every chain above it (1, 1, 3).
With three or more chains in the ranking, the headline names the lowest and the highest total (of
equal totals, the first and the last by slug) and the gap, (highest - lowest) x 100 / lowest,
rounded half up to a whole percent; with fewer, there is no headline. When no item counts, no chain
has a total or a rank and there is no headline; a chain B8 put in the ranking stays there all the
same.

Order (B10). Every mapping by chain in the result, the chains' results and a left-out item's details,
is keyed by slug in sorted order, whatever the order of the chain days given.
"""
from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb

from basket import duck
from basket.barcode import normalize
from basket.basket_file import Basket, BasketItem
from basket.extract import table_path
from basket.units import Size, normal_size, plain


class MissingTable(Exception):
    """A chain's table for the day is absent: its extraction did not run, or stopped before writing it."""


@dataclass(frozen=True)
class ChainPrice:
    """A chain's price for an item (B5), its stores' lowest and highest price, the stores listing it, and
    how many of those list it under more than one code (each counted once, at its lowest price)."""
    median: Decimal
    low: Decimal
    high: Decimal
    listing: int
    double_coded: int = 0


@dataclass(frozen=True)
class ChainDay:
    """A chain's included stores, those of them with a file that day, and whether it is in the ranking (B8)."""
    slug: str
    included: int
    with_file: int
    in_ranking: bool


@dataclass(frozen=True)
class LeftOut:
    """A basket item out of the day's totals: "coverage" with {chain: "n of m"} or "size" with {chain: "500 gml"},
    the chains sorted."""
    code: str
    reason: str
    details: dict[str, str]


@dataclass(frozen=True)
class Headline:
    lowest: str
    lowest_total: Decimal
    highest: str
    highest_total: Decimal
    gap_percent: int


@dataclass(frozen=True)
class ChainResult:
    """A chain's total and rank (None out of the ranking, or when no item counts) and its price for each basket
    item it lists, by code."""
    total: Decimal | None
    rank: int | None
    items: dict[str, ChainPrice]


@dataclass(frozen=True)
class DayResult:
    """The basket codes that count and those left out, in the basket's order; the chains by slug, sorted;
    the headline, or None."""
    items_in: tuple[str, ...]
    left_out: tuple[LeftOut, ...]
    chains: dict[str, ChainResult]
    headline: Headline | None


def open_day(tables_dir: Path, day: date, slugs: Sequence[str]) -> duckdb.DuckDBPyConnection:
    """An in-memory connection with the view `prices`: every row of the chains' tables for `day`, with `chain`.

    Raises MissingTable naming the first chain whose table is absent."""
    paths = {slug: table_path(tables_dir, slug, day) for slug in slugs}
    for slug, path in paths.items():
        if not path.is_file():
            raise MissingTable(f"no table for chain {slug!r} on {day.isoformat()}: {path}")
    con = duck.connect()
    union = " UNION ALL ".join(
        f"SELECT {_literal(slug)} AS chain, * FROM read_parquet({_literal(str(path))}, hive_partitioning = false)"
        for slug, path in paths.items())
    con.execute(f"CREATE VIEW prices AS {union}")
    return con


def apply_filters(con: duckdb.DuckDBPyConnection, included: dict[str, set[str]],
                  excluded_sub_chains: dict[str, frozenset[str]]) -> None:
    """Add the view `rows`: the rows of `prices` that count (B2's sub-chain rule by file name, B4)."""
    con.execute("CREATE TEMP TABLE included (chain VARCHAR, store VARCHAR)")
    con.execute("CREATE TEMP TABLE excluded_sub_chains (chain VARCHAR, sub_chain VARCHAR)")
    _insert_keys(con, "included", included)
    _insert_keys(con, "excluded_sub_chains", excluded_sub_chains)
    con.execute("""
        CREATE VIEW rows AS
        SELECT p.* FROM prices p JOIN included i ON i.chain = p.chain AND i.store = p.store
        WHERE p.price IS NOT NULL AND p.price > 0.01
          AND NOT EXISTS (SELECT 1 FROM excluded_sub_chains x WHERE x.chain = p.chain AND x.sub_chain = p.sub_chain)
    """)


def _insert_keys(con: duckdb.DuckDBPyConnection, table: str, keys: Mapping[str, Set[str]]) -> None:
    pairs = [(chain, key) for chain in sorted(keys) for key in sorted(keys[chain])]
    if pairs:
        con.executemany(f"INSERT INTO {table} VALUES (?, ?)", pairs)


def stores_with_file_keys(con: duckdb.DuckDBPyConnection, included: dict[str, set[str]],
                          excluded_sub_chains: Mapping[str, Set[str]]) -> dict[str, tuple[str, ...]]:
    """Per chain of `included`, by slug: its included stores with a row in `prices` whose file-name sub-chain is not
    one of the chain's `excluded_sub_chains` (B2, as `apply_filters` leaves rows out), placeholders and all, by
    number."""
    present: dict[str, set[str]] = {chain: set() for chain in sorted(included)}
    for chain, store, sub_chain in con.execute("SELECT DISTINCT chain, store, sub_chain FROM prices").fetchall():
        if store in included.get(chain, ()) and sub_chain not in excluded_sub_chains.get(chain, ()):
            present[chain].add(store)
    return {chain: tuple(sorted(stores, key=lambda store: (int(store), store))) for chain, stores in present.items()}


def stores_with_file(con: duckdb.DuckDBPyConnection, included: dict[str, set[str]],
                     excluded_sub_chains: Mapping[str, Set[str]]) -> dict[str, int]:
    """Per chain of `included`, by slug: how many of its included stores have a file (`stores_with_file_keys`)."""
    return {chain: len(stores) for chain, stores in stores_with_file_keys(con, included, excluded_sub_chains).items()}


def store_prices_sql(rows: str = "rows", codes: bool = True) -> str:
    """B5's one price a store, as SQL over the view `rows`: per (chain, normalized code, store) listed in it, the
    store's lowest price (`price`) and how many of its rows list the code (`codes`: more than one is a double-coded
    store). With `codes`, only the normalized codes of one bound list parameter (`?`); without, every code."""
    where = " WHERE code_norm IN (SELECT unnest(?::VARCHAR[]))" if codes else ""
    return (f"SELECT chain, code_norm, store, min(price) AS price, count(*) AS codes FROM {rows}{where}"
            " GROUP BY chain, code_norm, store")


def _bound(codes: Sequence[str] | None) -> list:
    """The parameters of a query filtered by `codes` (normalized), or none for every code."""
    return [] if codes is None else [[normalize(code) for code in codes]]


def chain_prices(con: duckdb.DuckDBPyConnection, codes: Sequence[str] | None,
                 rows: str = "rows") -> dict[tuple[str, str], ChainPrice]:
    """Per (chain, normalized code) listed in the view `rows`, keyed by its `chain` column: the chain's price for the
    item (B5), one price a store; for the normalized `codes`, or with None for every code."""
    found = con.execute(f"""
        SELECT chain, code_norm, list(price ORDER BY price, store), count(*), count(*) FILTER (WHERE codes > 1)
        FROM ({store_prices_sql(rows, codes is not None)})
        GROUP BY chain, code_norm ORDER BY chain, code_norm
    """, _bound(codes)).fetchall()
    return {(chain, code): ChainPrice(median(prices), prices[0], prices[-1], listing, double_coded)
            for chain, code, prices, listing, double_coded in found}


def median(ordered: list[Decimal]) -> Decimal:
    """B5's median: the middle value of `ordered` (sorted, not empty), or the mean of its two middle values, in
    Decimal."""
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def chain_sizes(con: duckdb.DuckDBPyConnection, codes: Sequence[str] | None,
                rows: str = "rows") -> dict[tuple[str, str], Size | None]:
    """Per (chain, normalized code) listed in the view `rows`, keyed by its `chain` column: the chain's size for the
    item (B7), or None; for the normalized `codes`, or with None for every code."""
    where = "" if codes is None else " WHERE code_norm IN (SELECT unnest(?::VARCHAR[]))"
    found = con.execute(f"SELECT chain, code_norm, quantity, unit, count(*) FROM {rows}{where}"
                        " GROUP BY ALL ORDER BY ALL", _bound(codes)).fetchall()
    counted: dict[tuple[str, str], Counter[Size]] = {}
    for chain, code, quantity, unit, count in found:
        sizes = counted.setdefault((chain, code), Counter())
        size = normal_size(quantity, unit)
        if size is not None:
            sizes[size] += count
    return {key: most_common_size(sizes) for key, sizes in counted.items()}


def most_common_size(sizes: Counter[Size]) -> Size | None:
    """The size with the most rows, a tie to the smaller amount; None for no size. (The shopper site's covered
    registry counts columns with it, `shopper.history`.)"""
    return min(sizes, key=lambda size: (-sizes[size], size.amount, size.kind), default=None)


def covers(listing: int, with_file: int) -> bool:
    """B6's coverage: `listing` stores list the item, at least half of the chain's `with_file` stores with a file."""
    return listing * 2 >= with_file


def chain_day(slug: str, included: int, with_file: int) -> ChainDay:
    """The chain's day (B8): in the ranking when it has included stores and at least half have a file."""
    return ChainDay(slug, included, with_file, included > 0 and with_file * 2 >= included)


def gap_percent(low: Decimal, high: Decimal) -> int:
    """(high - low) x 100 / low as a whole percent, rounded half up."""
    return int(((high - low) * 100 / low).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def price_basket(basket: Basket, days: Sequence[ChainDay], prices: dict[tuple[str, str], ChainPrice],
                 sizes: dict[tuple[str, str], Size | None]) -> DayResult:
    """The day's result: the guards (B6, B7) over the chains in the ranking, then totals, ranks and headline (B9)."""
    ranking = sorted((day for day in days if day.in_ranking), key=lambda day: day.slug)
    items_in: list[str] = []
    left_out: list[LeftOut] = []
    for item in basket.items:
        kept_out = _guard(item, ranking, prices, sizes)
        if kept_out is None:
            items_in.append(item.code)
        else:
            left_out.append(kept_out)
    normalized = {item.code: normalize(item.code) for item in basket.items}
    listed = {day.slug: {code: prices[(day.slug, norm)] for code, norm in normalized.items()
                         if (day.slug, norm) in prices} for day in days}
    totals: dict[str, Decimal] = {}
    if items_in:  # with no item counted there is nothing to total, rank or compare
        totals = {day.slug: sum((listed[day.slug][code].median for code in items_in), Decimal(0)) for day in ranking}
    ranks = {slug: 1 + sum(other < totals[slug] for other in totals.values()) for slug in totals}
    chains = {slug: ChainResult(totals.get(slug), ranks.get(slug), listed[slug]) for slug in sorted(listed)}
    headline = None
    if len(totals) >= 3:
        order = sorted(totals, key=lambda slug: (totals[slug], slug))
        lowest, highest = order[0], order[-1]
        headline = Headline(lowest, totals[lowest], highest, totals[highest],
                            gap_percent(totals[lowest], totals[highest]))
    return DayResult(tuple(items_in), tuple(left_out), chains, headline)


def _guard(item: BasketItem, ranking: Sequence[ChainDay], prices: dict[tuple[str, str], ChainPrice],
           sizes: dict[tuple[str, str], Size | None]) -> LeftOut | None:
    """Why `item` is left out over the chain days in `ranking` (sorted by slug), coverage (B6) before size (B7);
    None when it counts."""
    code = normalize(item.code)
    listing = {day.slug: prices[(day.slug, code)].listing if (day.slug, code) in prices else 0 for day in ranking}
    short = {day.slug: f"{listing[day.slug]} of {day.with_file}" for day in ranking
             if not covers(listing[day.slug], day.with_file)}
    if short:
        return LeftOut(item.code, "coverage", short)
    stated = {day.slug: sizes.get((day.slug, code)) for day in ranking}
    differing = {slug: f"{plain(size.amount)} {size.kind}" for slug, size in stated.items()
                 if size is not None and size != item.size}
    if differing:
        return LeftOut(item.code, "size", differing)
    return None


def _literal(text: str) -> str:
    """`text` as an SQL string literal."""
    return "'" + text.replace("'", "''") + "'"

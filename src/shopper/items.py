"""The day's items table and the reader's input: one chain's day, a row per column and product with the column's listed
price, its stores' range, whether the column lists it widely and the day's promotions on it; and a row per distinct
promotion text for the reader (docs/shopper-site.md P1 to P5 and "What the site needs from the reader", with its
"Changed after the survey", S1 to S5; the plan's Task 6 and its second pre-flight's B1, S3, S9, S11 and S19).

The columns and their stores. A chain's columns and each one's stores that day are `shopper.columns.members` over the
day's store list and its included stores (B2's store-list half); the included stores in no column (`outside`) are
listed in the report and are in no row. A column's stores with a file are its members with a row in the day's prices
table under a file-name sub-chain the chain keeps (`basket.rules.stores_with_file_keys`), so store 779, on the list in
Express and named under Be's 005 in its files, is a member of Express that never has a file.

The rows (P1, P2). One per (column, GS1 barcode) listed above ₪0.01 at a store of the column that day. The rows that
count (`basket.rules.apply_filters`: included stores, B2's file-name half, B4's placeholders left out) are joined to the
day's (store, column) pairs in one view, `column_rows`, whose `chain` field is the column, codes passing the GS1 check
only (P1: a chain's internal codes are no product). Over that view the basket's own rules give each column its figures,
with no second copy: `listed` is B5's median over the column's stores listing the code, one price a store, exact
(DECIMAL(13,3) holds any median of the prices the prices table holds, two places below ₪10,000,000,000), with `low`,
`high` and `listing` (`basket.rules.chain_prices`); the size
is B7's most common readable size (`basket.rules.chain_sizes`), as `size_amount` (the amount as plain text, exact
whatever its places) and `size_kind`, or NULL for none. `name` is the name most of the column's rows give the code, a
tie going to the longest, then to the first in code-point order. `wide` is B6 per column (`basket.rules.covers`):
`listing` is at least half the column's stores with a file. That is P1's day test.

Holes (B8 per column; the second pre-flight's B1). A column is a hole when `basket.rules.chain_day` over its included
stores and its stores with a file leaves it out of the ranking: it has no included store, or fewer than half of them
have a file. A hole's rows are written all the same; the pages show them as from too few files. A column is a promotion
hole when fewer than half its counted stores (its stores with a price file that counts, P2's) have a promotion file,
or when the chain's promotions were not read.

The day's promotions (P3 to P5, S2). When the chain's promotions were read, they come from the day's promotions table
(`shopper.promos`): each of its rows on the item is one link of a promotion of the column that runs on the day or
starts after it (expired promotions, coupons, gifts and basket rewards never reach it). `on_promotion` is true when a
row of the column on the item is wide (carried by at least half the column's counted stores), has a kind and runs on
the day (`shopper.promotions.in_day`), whether its deal is valid or not. `next_start` is the earliest start in d + 1 to
d + HORIZON (14) among the column's wide rows on the item with a kind that start after the day, or NULL. `promotions`
holds one struct per promotion on the item, by start, then by id as a number. Of a promotion's links on the item, the
one shown is a link with a kind before a `RewardType` 0 link, then the lowest `GroupID` as a number, then the lowest
code; an item named only by 0 links has a struct with no kind and no price ("price not read", never on promotion). The
deal is `shopper.deals.deal` over the link's item fields (the row's `fields` JSON, its "item", S11) against the
column's `listed`, a percent-off deal at the row's `discounted_median`, `discounted_low` and `discounted_high`. A
percent-off row without them (no carrying store's `DiscountedPrice` the promotions table could hold) has no price:
its deal never falls back to the link's own `DiscountedPrice`, which that table set aside. The price is written
twice: `price_exact`, the `Fraction`'s text ("109/75"), from which `shopper.deals.deal_from_row` rebuilds the deal;
and `price`, to the agora half up, for the eye only, NULL when it would not fit DECIMAL(12,2).
`buy` is written on every struct. A `MinQty` that DECIMAL(12,3) cannot hold exactly (more than three places, or a
billion or more) would come back as another `buy`, so `write_items` raises `PromotionFormatChanged` naming the field
before any table is written, for its caller to treat as a format change of the chain's promotions (P10); none of the
five chains' "N for ₪M" links of 5 and 7 November had more than two places. When the chain's promotions were not
read (`promo` None, with `promotions_error` saying why), `on_promotion`, `next_start` and `promotions` are NULL in
every row and every column is a promotion hole.

The reader's input (the second pre-flight's S9). When promotions were read, `texts.parquet` beside the promotions
table holds one row per distinct (`PromotionID`, `PromotionDescription`, start, end) as published, over every store's
copy (`PromoReport.texts`): the chain, those four, `update_time`, `fields` (JSON text: the promotion's fields, then its
groups in file order, each with its fields and its items' fields), `listed` (JSON text: by column, each column holding
a store that carries the text, then by code, each of the text's item codes the column lists, at its `listed` as text)
and `stores` (the counted stores carrying it).

How. Each table goes through a CSV in a temporary folder inside its own folder, written with `basket.extract`'s
`write_csv` and copied into Parquet with its `copy_sql` (S19), the struct list read back from its JSON text. The links
are read in the items' order and joined to them as they are written, so a chain's links are never all held at once.
`items.parquet` is at `tables/items/chain=<slug>/date=<day>/`, overwritten by each run, with `report.json` beside it;
`texts.parquet` at `tables/promotions/chain=<slug>/date=<day>/`. The day's prices table must be there (`MissingTable`
otherwise, as `basket.rules.open_day` raises), and so must its promotions table when promotions were read.
"""
import json
import math
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence, Set
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import duckdb

from basket.barcode import normalize
from basket.chains import CARREFOUR_COLUMNS
from basket.extract import copy_sql, sql_text, write_csv
from basket.rules import (ChainPrice, apply_filters, chain_day, chain_prices, chain_sizes, covers, open_day,
                          stores_with_file_keys)
from basket.stores import Store
from basket.units import Size, plain
from shopper.columns import members, outside, under_floor
from shopper.deals import StorePrices, deal
from shopper.promofile import PromotionFormatChanged
from shopper.promos import PERCENT_OFF, PromoReport, PromoText, promotions_path
from shopper.promotions import in_day

HORIZON = 14                 # days ahead a start is looked for: the design's d + 1 to d + 14
THREE = Decimal("0.001")
BUY_LIMIT = Decimal(10) ** 9   # DECIMAL(12,3) holds nine digits before the point
MAX_CENTS = 10 ** 12           # DECIMAL(12,2) holds ten
BATCH = 10_000                 # links fetched at a time

_STRUCT = ('STRUCT(promotion_id VARCHAR, description VARCHAR, "start" DATE, "end" DATE, kind VARCHAR, '
           "buy DECIMAL(12,3), price DECIMAL(12,2), price_exact VARCHAR, per VARCHAR, low DECIMAL(12,3), "
           "high DECIMAL(12,3), valid BOOLEAN, why VARCHAR, restrictions VARCHAR[], programmes VARCHAR[], "
           "min_spend DECIMAL(12,2), stores INTEGER, wide BOOLEAN)[]")
COLUMNS = (("column", "VARCHAR"), ("code", "VARCHAR"), ("name", "VARCHAR"), ("size_amount", "VARCHAR"),
           ("size_kind", "VARCHAR"), ("listed", "DECIMAL(13,3)"), ("low", "DECIMAL(12,2)"), ("high", "DECIMAL(12,2)"),
           ("listing", "INTEGER"), ("wide", "BOOLEAN"), ("on_promotion", "BOOLEAN"), ("next_start", "DATE"),
           ("promotions", _STRUCT))
NULLABLE = ("size_amount", "size_kind", "on_promotion", "next_start", "promotions")
TEXT_COLUMNS = (("chain", "VARCHAR"), ("promotion_id", "VARCHAR"), ("description", "VARCHAR"), ("start_at", "VARCHAR"),
                ("end_at", "VARCHAR"), ("update_time", "VARCHAR"), ("fields", "VARCHAR"), ("listed", "VARCHAR"),
                ("stores", "INTEGER"))
_LINKS = """
    SELECT "column", code_norm, promotion_id, group_id, code, description, "start", "end", kind, fields,
           discounted_median, discounted_low, discounted_high, restrictions, programmes, min_spend, stores, wide
    FROM read_parquet({path}, hive_partitioning = false) WHERE gs1
    ORDER BY "column", code_norm, promotion_id, group_id, code
"""


@dataclass(frozen=True)
class ColumnReport:
    """One column's day (the module's docstring); `valid_deals` counts its (item, promotion) pairs running on the day
    whose deal is valid, wide or not."""
    column: str
    included: int
    with_file: int
    hole: bool          # B8 per column: not `basket.rules.chain_day(...).in_ranking`
    counted: int
    promo_files: int
    promo_hole: bool    # promo_files * 2 < counted, or the chain's promotions unread
    items: int
    wide: int
    on_promotion: int
    valid_deals: int
    under_floor: bool


@dataclass(frozen=True)
class ItemsReport:
    """What one chain-day's items table read and wrote."""
    slug: str
    day: str
    columns: dict[str, ColumnReport]   # every column of the chain, in name order
    outside: list[str]                 # included stores in no column, by number
    promotions_error: str | None
    texts: int
    promotions: dict | None            # the PromoReport's counts (its `summary`), or None when unread


def items_path(tables_dir: Path, slug: str, day: date) -> Path:
    return tables_dir / "items" / f"chain={slug}" / f"date={day.isoformat()}" / "items.parquet"


def texts_path(tables_dir: Path, slug: str, day: date) -> Path:
    return promotions_path(tables_dir, slug, day).with_name("texts.parquet")


def _by_number(text: str) -> tuple:
    """A sort key for a published id: ids of ASCII digits first, in numeric order ("9" before "10", "009" before "9",
    the text breaking a tie), then any other text. Numeric order without `int()`, which refuses a text past 4,300
    digits: with leading zeros stripped, a shorter number is the smaller, and one of the same length orders as its
    text, so an id of any length orders."""
    if text.isascii() and text.isdigit():
        digits = text.lstrip("0")
        return (0, len(digits), digits, text)
    return (1, 0, "", text)


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _two(price: Fraction | None) -> str | None:
    """The deal price to the agora, half up, for the eye; None for none, or when it would not fit DECIMAL(12,2)."""
    if price is None:
        return None
    cents = math.floor(abs(price) * 100 + Fraction(1, 2))
    if cents >= MAX_CENTS:
        return None
    return format(Decimal(-cents if price < 0 else cents).scaleb(-2), "f")


def _buy(buy: Decimal, item: Mapping[str, str]) -> str:
    """`buy` as the table holds it exactly; P10 when DECIMAL(12,3) cannot, since it would come back another."""
    if abs(buy) >= BUY_LIMIT or buy != buy.quantize(THREE):
        raise PromotionFormatChanged(f"MinQty {item['MinQty']!r} does not fit the items table")
    return format(buy, "f")


def _column_rows(con: duckdb.DuckDBPyConnection, columns: Mapping[str, Set[str]]) -> None:
    """The view `column_rows`: the rows of `rows` at each column's stores, the column in `chain`, GS1 codes only."""
    con.execute("CREATE TEMP TABLE store_columns (store VARCHAR, col VARCHAR)")
    pairs = [(store, key) for key, ids in columns.items() for store in sorted(ids)]
    if pairs:
        con.executemany("INSERT INTO store_columns VALUES (?, ?)", pairs)
    con.execute("""
        CREATE VIEW column_rows AS
        SELECT c.col AS chain, r.* EXCLUDE (chain) FROM rows r JOIN store_columns c ON c.store = r.store
        WHERE r.gs1
    """)


def _names(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], str]:
    """Per (column, code) in `column_rows`: the name of most rows, a tie to the longest, then the first in code-point
    order."""
    counted: dict[tuple[str, str], Counter[str]] = {}
    for column, code, name, count in con.execute(
            "SELECT chain, code_norm, name, count(*) FROM column_rows GROUP BY ALL").fetchall():
        counted.setdefault((column, code), Counter())[name] = count
    return {key: min(names, key=lambda name: (-names[name], -len(name), name)) for key, names in counted.items()}


def _link_groups(result: duckdb.DuckDBPyConnection) -> Iterator[tuple[tuple[str, str], list[dict[str, Any]]]]:
    """The promotions table's links, a (column, code) at a time, in that order."""
    names = [column[0] for column in result.description]
    key, group = None, []
    while batch := result.fetchmany(BATCH):
        for values in batch:
            link = dict(zip(names, values))
            here = (link["column"], link["code_norm"])
            if here != key:
                if group:
                    yield key, group
                key, group = here, []
            group.append(link)
    if group:
        yield key, group


def _shown(links: list[dict[str, Any]]) -> dict[str, Any]:
    """A promotion's link shown for the item: a kind before none, then the lowest GroupID as a number, then the code."""
    return min(links, key=lambda link: (link["kind"] is None, _by_number(link["group_id"]), link["code"]))


def _struct(slug: str, link: dict[str, Any], listed: Decimal) -> dict[str, Any]:
    """The struct of one promotion on the item, its deal from the shown link."""
    stores = None if link["discounted_median"] is None else StorePrices(
        link["discounted_median"], link["discounted_low"], link["discounted_high"])
    item = link["item"]
    if stores is None and link["kind"] == PERCENT_OFF:   # no store's price the promotions table could hold
        item = {**item, "DiscountedPrice": ""}
    found = deal(slug, item, listed, stores)
    return {"promotion_id": link["promotion_id"], "description": link["description"],
            "start": link["start"].isoformat(), "end": link["end"].isoformat(), "kind": link["kind"],
            "buy": _buy(found.buy, item), "price": _two(found.price),
            "price_exact": None if found.price is None else str(found.price), "per": found.per,
            "low": _text(found.low), "high": _text(found.high), "valid": found.valid, "why": found.why,
            "restrictions": link["restrictions"], "programmes": link["programmes"],
            "min_spend": _text(link["min_spend"]), "stores": link["stores"], "wide": link["wide"]}


def _on_item(slug: str, day: date, links: list[dict[str, Any]], listed: Decimal) -> tuple[bool, date | None, list, int]:
    """The item's day in its column: on promotion, the next start, the structs and the valid deals of the day."""
    on, starts, by_promotion = False, [], {}
    for link in links:
        fields = json.loads(link["fields"])
        link["item"], link["in_day"] = fields["item"], in_day(fields["promotion"], day)
        if link["wide"] and link["kind"] is not None:
            on = on or link["in_day"]
            if day < link["start"] <= day + timedelta(days=HORIZON):
                starts.append(link["start"])
        by_promotion.setdefault(link["promotion_id"], []).append(link)
    shown = [_shown(promotion) for promotion in by_promotion.values()]
    structs = [_struct(slug, link, listed) for link in shown]
    valid = sum(1 for link, struct in zip(shown, structs) if link["in_day"] and struct["valid"])
    structs.sort(key=lambda struct: (struct["start"], _by_number(struct["promotion_id"])))
    return on, min(starts, default=None), structs, valid


def _rows(slug: str, day: date, prices: Mapping[tuple[str, str], ChainPrice],
          sizes: Mapping[tuple[str, str], Size | None], names: Mapping[tuple[str, str], str],
          with_file: Mapping[str, int], links: Iterator | None, counts: dict[str, Counter]) -> Iterator[tuple]:
    """The table's rows in (column, code) order, the links joined as they come; each column's counts kept."""
    pending = None if links is None else next(links, None)
    for key in sorted(prices):
        column, code = key
        price, size = prices[key], sizes.get(key)
        wide = covers(price.listing, with_file[column])
        on = next_start = structs = None
        if links is not None:
            while pending is not None and pending[0] < key:
                pending = next(links, None)
            here = pending[1] if pending is not None and pending[0] == key else []
            on, next_start, structs, valid = _on_item(slug, day, here, price.median)
            counts[column]["on_promotion"] += on
            counts[column]["valid_deals"] += valid
        counts[column]["items"] += 1
        counts[column]["wide"] += wide
        yield (column, code, names[key], None if size is None else plain(size.amount),
               None if size is None else size.kind, _text(price.median), _text(price.low), _text(price.high),
               price.listing, wide, on, None if next_start is None else next_start.isoformat(),
               None if structs is None else json.dumps(structs, ensure_ascii=False))


def _texts(slug: str, texts: Sequence[PromoText], columns: Mapping[str, Set[str]],
           prices: Mapping[tuple[str, str], ChainPrice]) -> Iterator[tuple]:
    """The reader's input, a row per distinct text (the module's docstring)."""
    for text in texts:
        record = text.record
        carrying = set(text.stores)
        codes = sorted({code for link in record.links if (code := normalize(link.item["ItemCode"])) is not None})
        listed = {column: {code: _text(prices[(column, code)].median) for code in codes if (column, code) in prices}
                  for column, ids in columns.items() if ids & carrying}
        fields = {"promotion": dict(record.fields),
                  "groups": [{"group": dict(group), "items": [dict(link.item) for link in record.links
                                                              if link.group is group]}
                             for group in record.groups]}
        yield (slug, text.promotion_id, text.description, text.start_at, text.end_at,
               record.fields["PromotionUpdateTime"], json.dumps(fields, ensure_ascii=False),
               json.dumps(listed, ensure_ascii=False), len(text.stores))


def _write(con: duckdb.DuckDBPyConnection, rows: Iterator[tuple], out: Path, columns: Sequence[tuple[str, str]],
           nullable: Sequence[str]) -> None:
    """`rows` through a CSV in a temporary folder inside `out`'s folder, into the Parquet file `out`."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        csv_path = Path(temp) / "rows.csv"
        write_csv(rows, csv_path, columns)
        con.execute(copy_sql(csv_path, out, columns, nullable))


def write_items(tables_dir: Path, slug: str, day: date, stores: Sequence[Store], included: Set[str],
                excluded_sub_chains: frozenset[str], promo: PromoReport | None, promotions_error: str | None,
                table: Mapping[str, str] = CARREFOUR_COLUMNS) -> ItemsReport:
    """Write the chain's items table for the day with `report.json` beside it, and, when its promotions were read
    (`promo`, Task 5's report), the texts table; the report. `stores`: the day's store list; `included` its included
    ids; `promotions_error`: why the promotions were not read, when they were not."""
    columns = members(slug, stores, included, table)
    in_no_column = sorted({store.id for store in outside(slug, stores, included, table)}, key=_by_number)
    keys, sub_chains = {slug: set(included)}, {slug: excluded_sub_chains}
    out = items_path(tables_dir, slug, day)
    counts: dict[str, Counter] = {key: Counter() for key in columns}
    with open_day(tables_dir, day, [slug]) as con:   # MissingTable before anything is written
        apply_filters(con, keys, sub_chains)
        file_keys = set(stores_with_file_keys(con, keys, sub_chains)[slug])
        with_file = {key: len(ids & file_keys) for key, ids in columns.items()}
        _column_rows(con, columns)
        prices = chain_prices(con, None, rows="column_rows")
        sizes = chain_sizes(con, None, rows="column_rows")
        names = _names(con)
        links = None
        if promo is not None:
            links = _link_groups(con.execute(_LINKS.format(path=sql_text(promotions_path(tables_dir, slug, day)))))
        _write(con, _rows(slug, day, prices, sizes, names, with_file, links, counts), out, COLUMNS, NULLABLE)
        if promo is not None:
            _write(con, _texts(slug, promo.texts, columns, prices), texts_path(tables_dir, slug, day), TEXT_COLUMNS, ())
    floor = set(under_floor(columns))
    reports = {}
    for key, ids in columns.items():
        counted = with_file[key] if promo is None else promo.counted[key]
        promo_files = 0 if promo is None else promo.promo_files[key]
        reports[key] = ColumnReport(
            column=key, included=len(ids), with_file=with_file[key],
            hole=not chain_day(key, len(ids), with_file[key]).in_ranking, counted=counted, promo_files=promo_files,
            promo_hole=promo is None or promo_files * 2 < counted, items=counts[key]["items"], wide=counts[key]["wide"],
            on_promotion=counts[key]["on_promotion"], valid_deals=counts[key]["valid_deals"], under_floor=key in floor)
    report = ItemsReport(slug=slug, day=day.isoformat(), columns=reports, outside=in_no_column,
                         promotions_error=promotions_error, texts=0 if promo is None else len(promo.texts),
                         promotions=None if promo is None else promo.summary())
    (out.parent / "report.json").write_text(json.dumps(asdict(report), sort_keys=True, indent=1))
    return report

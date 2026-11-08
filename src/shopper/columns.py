"""The columns: the store formats the shopper site shows, each its own unit (docs/shopper-site.md, "Changed after the
survey", S1 and "The column").

What a column is. Shufersal and Carrefour are each a set of formats that carry their own promotions and prices, so the
site treats a format, not the chain, as its unit: every measure (coverage, listed prices, "wide" promotions, the
history, the target, the forecasts, the record, the gate) is per column. There are nine, fixed in code for target
version 1 (`COLUMNS`, in name order): Shufersal Sheli, Deal, Express and Universe; Carrefour City and Carrefour Market;
Rami Levy, Osher Ad and Yochananof, each of the last three whole. A column's key is the text every later table and
file carries ("shufersal-deal"; a whole chain's is its slug). The English names are this site's renderings of the store
list's Hebrew sub-chain names; Carrefour's list names no format, so its two are named after the word most of their
stores' names carry ("סיטי", City; "מרקט", Market).

Who is a member, each day. Only included stores (B2's store-list half, `basket.stores.included`): a Shufersal store's
column is its sub-chain on that day's store list when that is one of the four (1 Sheli, 2 Deal, 7 Express, 8 Universe),
else none; a Carrefour store's is `basket.chains.CARREFOUR_COLUMNS`, and a store the table lacks is in no column; every
store of Rami Levy, Osher Ad or Yochananof is in its chain's one column. A store that moves sub-chain on the list moves
column from that day. B2's file-name half stays in `basket.rules`: store 779, Express on the list and named under Be's
005 in its files, is a member of Express that never has a counted file. The included stores in no column (Shufersal's
Yesh Chesed and its five smallest formats, Carrefour's stores outside the table) are named on the method page
(`outside`).

The floor and why the set is fixed. A format of a split chain is a column when it has at least FLOOR (30) included
stores; a chain is shown whole whatever its size, which is why Osher Ad's 24 stores are a column and Yesh Chesed's 22
are not. The floor was applied once, on the store lists of FIXED_ON (7 November 2026), and `FORMATS_ON_FIXED_DAY` is
its evidence: Shufersal's included stores by sub-chain that day (1: 71, 2: 76, 3: 2, 6: 22, 7: 94, 8: 31, 15: 9, 18: 11,
32: 2, 36: 1; 5 November's list gives the same), and Carrefour's store groups over 5 and 7 November (City 75, Market 44,
then groups of 18 and 7 and the two type-2 stores). A column whose included stores later fall under the floor stays a
column, and `under_floor` names it for the method page. Adding or dropping a column, or taking in Yesh Chesed once 90
days show whether its thin Saturday recurs, is a new target version, never an edit here.

How Carrefour's table was drawn. `shopper.survey`'s `store_groups` grouped the counted stores of 5 and 7 November by
the promotions they carry (each store's set of the promotions that are no coupons; two stores joined at a Jaccard index
of at least 1/2): 67, 43, 18, 7 and 1 stores on 7 November, 74, 44, 18, 7 and 2 on 5 November, no store counted on both
days in two groups. Each of the two large groups' stores over both days is one column (75 and 44); the other 27
included stores are in none.

How a new Carrefour store is placed. It is in no column until placed: run the survey for a day it is counted
(`PYTHONPATH=src python -m shopper.survey --data data --day <day> --chain carrefour`) and find it in `store_groups`;
if it sits in the City or the Market group, the owner's word adds it to `CARREFOUR_COLUMNS` in a commit naming the store
and the day. A table that changes moves the columns' history from that day, as a store opening does.
"""
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date

from basket.chains import CARREFOUR_COLUMNS, SLUGS
from basket.stores import Store

FLOOR = 30                    # included stores, for a format of a split chain (the design's "The set is fixed")
FIXED_ON = date(2026, 11, 7)  # the day the nine were fixed on, for target version 1 (Carrefour's also read 5 November)
BY_TABLE = "carrefour"        # the chain whose columns CARREFOUR_COLUMNS sets


@dataclass(frozen=True)
class Column:
    """One column: its key, its chain, its name on the site and, at Shufersal, the store list's sub-chain key."""
    key: str
    slug: str
    name: str
    sub_chain: str | None = None


COLUMNS: tuple[Column, ...] = (
    Column("carrefour-city", "carrefour", "Carrefour City"),
    Column("carrefour-market", "carrefour", "Carrefour Market"),
    Column("osherad", "osherad", "Osher Ad"),
    Column("ramilevy", "ramilevy", "Rami Levy"),
    Column("shufersal-deal", "shufersal", "Shufersal Deal", "2"),
    Column("shufersal-express", "shufersal", "Shufersal Express", "7"),
    Column("shufersal-sheli", "shufersal", "Shufersal Sheli", "1"),
    Column("shufersal-universe", "shufersal", "Shufersal Universe", "8"),
    Column("yochananof", "yochananof", "Yochananof"),
)
BY_KEY: dict[str, Column] = {column.key: column for column in COLUMNS}
_BY_CHAIN: dict[str, tuple[Column, ...]] = {slug: tuple(c for c in COLUMNS if c.slug == slug) for slug in SLUGS}

# Each split chain's formats on the day the nine were fixed, by included stores: the floor's evidence. Shufersal's by
# the store list's sub-chain on 7 November, B2 applied; Carrefour's by its store groups over 5 and 7 November.
FORMATS_ON_FIXED_DAY: dict[str, dict[str, int]] = {
    "shufersal": {"1": 71, "2": 76, "3": 2, "6": 22, "7": 94, "8": 31, "15": 9, "18": 11, "32": 2, "36": 1},
    "carrefour": {"carrefour-city": 75, "carrefour-market": 44, "third set": 18, "fourth set": 7, "type-2 stores": 2},
}


def chosen(formats: Mapping[str, int], floor: int = FLOOR) -> set[str]:
    """The formats with at least `floor` included stores."""
    return {name for name, stores in formats.items() if stores >= floor}


def columns_of(slug: str) -> tuple[Column, ...]:
    """The chain's columns, in name order. KeyError for a chain not in `basket.chains.SLUGS`."""
    return _BY_CHAIN[slug]


def _split(slug: str) -> bool:
    return len(columns_of(slug)) > 1


def column_of(slug: str, store: Store, table: Mapping[str, str] = CARREFOUR_COLUMNS) -> str | None:
    """The key of the store's column on the day of its list, or None for a store in no column. It does not ask whether
    the store is included: `members` and `outside` do."""
    columns = columns_of(slug)
    if slug == BY_TABLE:
        return table.get(store.id)
    if not _split(slug):
        return columns[0].key
    return next((column.key for column in columns if column.sub_chain == store.sub_chain), None)


def members(slug: str, stores: Sequence[Store], included: Set[str],
            table: Mapping[str, str] = CARREFOUR_COLUMNS) -> dict[str, frozenset[str]]:
    """Every column of the chain, in name order, with its included stores that day (`stores` the day's list, `included`
    its included ids); a column with none has an empty set, never a missing key."""
    found: dict[str, set[str]] = {column.key: set() for column in columns_of(slug)}
    for store in stores:
        if store.id in included:
            key = column_of(slug, store, table)
            if key is not None:
                found[key].add(store.id)
    return {key: frozenset(ids) for key, ids in found.items()}


def outside(slug: str, stores: Sequence[Store], included: Set[str],
            table: Mapping[str, str] = CARREFOUR_COLUMNS) -> list[Store]:
    """The included stores in no column, in the list's order: exactly the included stores `members` leaves out."""
    return [store for store in stores if store.id in included and column_of(slug, store, table) is None]


def under_floor(members: Mapping[str, Set[str]]) -> list[str]:
    """The columns of a split chain with fewer than FLOOR stores that day, in the mapping's order: still columns, named
    on the method page. A whole chain's column is never named, whatever its size."""
    return [key for key, ids in members.items() if _split(BY_KEY[key].slug) and len(ids) < FLOOR]

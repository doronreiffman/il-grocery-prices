"""The five chains of the headline basket and the stores each one leaves out (rule B2).

Every store of a chain counts, except those named here: whole sub-chains, and single stores by id.
Keys are the published numbers with leading zeros stripped. Shufersal's sub-chain 5 "Be" is out
because its stores carry 12% of the barcodes all five chains share (measured 2026-11-02), which is
not a grocery assortment, and its store 413 "שופרסל ONLINE" by its name. Any other chain's online or
non-grocery store goes here by id with its name in `why`; in the other four chains' store lists of
2026-11-02 two stores' names say so: Carrefour's store 471 "קרפור אונליין" (Carrefour online) and
Rami Levy's store 039 "מרלוג אינטרנט" (internet logistics centre). A chain with no such store has an
empty entry. The method page names each store left out.

`CARREFOUR_COLUMNS` is the shopper site's: which of Carrefour's stores are in its two columns
(`shopper.columns`, which says how the table was drawn and how a new store is placed).
"""
from dataclasses import dataclass

SLUGS = ("shufersal", "ramilevy", "osherad", "carrefour", "yochananof")


@dataclass(frozen=True)
class Exclusion:
    """The sub-chains and the store ids a chain leaves out, as keys, and why."""
    sub_chains: frozenset[str]
    stores: frozenset[str]
    why: str


EXCLUDED: dict[str, Exclusion] = {
    "shufersal": Exclusion(
        frozenset({"5"}), frozenset({"413"}),
        "sub-chain 5 'Be', 97 stores on 2026-11-02, carries 12% of the shared barcodes; store 413 'שופרסל ONLINE'"),
    "ramilevy": Exclusion(
        frozenset(), frozenset({"39"}),
        "store 039 'מרלוג אינטרנט', StoreType 2, the chain's internet logistics centre; store list of 2026-11-02"),
    "osherad": Exclusion(frozenset(), frozenset(), ""),
    "carrefour": Exclusion(
        frozenset(), frozenset({"471"}), "store 471 'קרפור אונליין   כפר סבא @ קרפור (5304)', online by its name"),
    "yochananof": Exclusion(frozenset(), frozenset(), ""),
}

# Carrefour's stores by the shopper site's column: store key -> "carrefour-city" or "carrefour-market". Hand-kept, drawn
# on 2026-11-08 from the promotion groups of the counted stores of 5 and 7 November 2026 (`shopper.survey`'s
# `store_groups`): each column is one group's stores over both days, named by the word most of their names carry on the
# store list. The other 27 included stores (groups of 18 and 7, and the type-2 stores 472 and 473) are in no column.
_CARREFOUR_CITY = (
    "62", "64", "67", "80", "83", "84", "85", "89", "108", "116", "132", "140", "183", "213", "256", "329", "337",
    "345", "353", "400", "401", "404", "405", "406", "407", "408", "411", "413", "414", "415", "417", "418", "419",
    "421", "422", "426", "427", "430", "431", "432", "434", "439", "440", "442", "443", "445", "446", "449", "450",
    "451", "457", "458", "460", "461", "462", "463", "464", "465", "466", "470", "515", "523", "558", "580", "610",
    "620", "698", "701", "752", "820", "850", "870", "906", "914", "981",
)
_CARREFOUR_MARKET = (
    "2", "12", "19", "26", "37", "46", "55", "60", "61", "63", "65", "68", "73", "74", "81", "119", "124", "125",
    "205", "221", "402", "403", "409", "410", "412", "423", "424", "425", "428", "433", "435", "436", "438", "441",
    "444", "448", "452", "455", "456", "459", "468", "469", "493", "830",
)
CARREFOUR_COLUMNS: dict[str, str] = {**dict.fromkeys(_CARREFOUR_CITY, "carrefour-city"),
                                     **dict.fromkeys(_CARREFOUR_MARKET, "carrefour-market")}

"""The five chains of the headline basket and the stores each one leaves out (rule B2).

Every store of a chain counts, except those named here: whole sub-chains, and single stores by id.
Keys are the published numbers with leading zeros stripped. Shufersal's sub-chain 5 "Be" is out
because its stores carry 12% of the barcodes all five chains share (measured 2026-11-02), which is
not a grocery assortment, and its store 413 "שופרסל ONLINE" by its name. Any other chain's online or
non-grocery store goes here by id with its name in `why`; in the other four chains' store lists of
2026-11-02 one store's name says online: Carrefour's store 471 "קרפור אונליין" (Carrefour online).
A chain with no such store has an empty entry. Rami Levy's store 039 "מרלוג אינטרנט" stays in, as
rule B2 says. The method page names each store left out.
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
    "ramilevy": Exclusion(frozenset(), frozenset(), ""),
    "osherad": Exclusion(frozenset(), frozenset(), ""),
    "carrefour": Exclusion(
        frozenset(), frozenset({"471"}), "store 471 'קרפור אונליין   כפר סבא @ קרפור (5304)', online by its name"),
    "yochananof": Exclusion(frozenset(), frozenset(), ""),
}

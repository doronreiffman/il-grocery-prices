"""Stand-in names, for measuring the word index at a given size with no model text (the product-names plan's Task 3,
its call 1). A hand-sent site run with `"words_probe": "realistic"` or `"ceiling"` files them as each product's model
names, at the word index's fixed keys, read only behind the script's switch. The next morning's run, which sends no
probe, writes every key the published names give and a manifest that names none of the others: the probe's files at
keys the published names never give stay in the bucket, unnamed (nothing in the code deletes, and the site bucket's
rules expire only earlier versions). Task 9 removes the probe.

The stand-ins copy the way the design measured its sizes (docs/product-names.md, section 5): there each product took
one of the trial's 50 model readings, picked by its barcode's hash, so that each reading's words sat on about 1 product
in 50 and piled up as a model's common words do. Here the 50 readings (`READINGS`) are made of published words. The
covered products, in the order of their barcodes' SHA-256s, are the donors, `DONORS` to a reading: reading r takes the
products 4r to 4r + 3 of that order (a registry of fewer than 200 products is gone over again from its start). Its
English name is the first donor's normalised title, then its other names, distinct and sorted (as
`shopper.wordindex.entry` orders them), each Hebrew letter written in Latin letters by `TABLE` (any other character
kept). Each of its Hebrew names is a further donor's normalised title. Each name is packed to the size's length: its
words in order, each one that still fits with a space before it, and the rest skipped; a name none of whose words fits
is its first word cut to the length. At the ceiling each name is packed again to the ceiling's length, its words gone
over again and again until none fits: the English from all the first donor's words, so that it gains some, and each
Hebrew name from its own realistic words, so that it gains bytes and no word. A product takes the reading its
barcode's SHA-256, read as a number, gives modulo 50. A function of the registry alone: no clock, no randomness, and the
same in any order. `shown` is always "": a stand-in is searched, never shown. The sizes this gives, on the registry
of 23 November 2026, against the design's: the plan's "Deviations" (Phase 1's fix wave, F1).

The sizes, `SIZES`, each (English length, Hebrew names, each one's length): "realistic" is the trial's Opus readings'
means, rounded (English 26.1 characters; 2.76 Hebrew names of 13.4); "ceiling" is the design's bounds
(docs/product-names.md, section 1). An unknown size is a KeyError: the site run refuses one before anything is read.
"""
import hashlib
from collections.abc import Mapping

from shopper.history import Covered
from shopper.search import normalize
from shopper.wordindex import Extra

SIZES = {"realistic": (26, 3, 13), "ceiling": (60, 3, 30)}
REALISTIC = "realistic"      # the size every reading is first packed to
CEILING = "ceiling"          # the size whose names are packed again, their words repeated
READINGS = 50                # the trial's readings, each on about 1 product in 50
DONORS = 4                   # a reading's products: the English name's, then one for each Hebrew name
# Each Hebrew letter's Latin letters; a final letter is already its plain form after `normalize`.
TABLE = dict(zip("אבגדהוזחטיכלמנסעפצקרשת", ("a", "b", "g", "d", "h", "v", "z", "ch", "t", "y", "k", "l", "m", "n", "s",
                                            "e", "p", "ts", "k", "r", "sh", "t")))


def _hash(code: str) -> bytes:
    return hashlib.sha256(code.encode("utf-8")).digest()


def _packed(text: str, length: int, again: bool = False) -> str:
    """`text`'s words, in order, each one that still fits within `length` with a space before it, the rest skipped;
    with `again`, gone over again while one more fits. None fitting, the first word cut to `length`."""
    words = [word for word in text.split(" ") if word]
    kept, used = [], -1
    while True:
        before = len(kept)
        for word in words:
            if used + 1 + len(word) <= length:
                kept.append(word)
                used += 1 + len(word)
        if not again or len(kept) == before:
            break
    return " ".join(kept) if kept else (words[0][:length] if words else "")


def _reading(donors: list[Covered], size: str) -> Extra:
    """One reading's stand-in names at `size` (the module's docstring)."""
    english, count, each = SIZES[REALISTIC]
    first, *others = donors
    title = normalize(first.title)
    names = [title, *sorted({name for name in map(normalize, first.names.values()) if name and name != title})]
    latin = "".join(TABLE.get(char, char) for char in " ".join(names))
    en = _packed(latin, english)
    hebrew = [_packed(normalize(donor.title), each) for donor in others[:count]]
    if size == CEILING:
        english, count, each = SIZES[CEILING]
        en = _packed(latin, english, again=True)
        hebrew = [_packed(name, each, again=True) for name in hebrew]
    return Extra(shown="", names=(en, *hebrew))


def stand_ins(covered: Mapping[str, Covered], size: str) -> dict[str, Extra]:
    """Each covered product's stand-in names at `size`, one of SIZES (the module's docstring), by barcode."""
    if size not in SIZES:   # even with nothing to file
        raise KeyError(size)
    order = sorted(covered, key=lambda code: (_hash(code), code))
    if not order:
        return {}
    readings = [_reading([covered[order[(DONORS * number + n) % len(order)]] for n in range(DONORS)], size)
                for number in range(READINGS)]
    return {code: readings[int.from_bytes(_hash(code), "big") % READINGS] for code in covered}

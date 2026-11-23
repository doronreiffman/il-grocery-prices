"""Stand-in names, for measuring the word index at a given size with no model text (the product-names plan's Task 3,
its call 1). A hand-sent site run with `"words_probe": "realistic"` or `"ceiling"` files them as each product's model
names, at the word index's fixed keys, read only behind the script's switch; the next morning's run replaces them. Task
9 removes the probe.

A product's stand-ins are made from its own published words alone. The English name, `en`: the product's normalised
title, then its other names, distinct and sorted (as `shopper.wordindex.entry` orders them), each Hebrew letter written
in Latin letters by `TABLE` (any other character kept), cut at a word boundary to the size's English length; at the
ceiling it is then repeated, a space between, to exactly that length, never ending on a space. The Hebrew names: the
normalised title's words rotated by 1, 2 and 3 places (as many as the size's count), each cut at a word boundary to the
size's length; a title of one word rotates to itself, which the index files once. A first word longer than the length
by itself is cut inside it. `shown` is always "": a stand-in is searched, never shown.

The sizes, `SIZES`, each (English length, Hebrew names, each one's length): "realistic" is the trial's Opus readings'
means, rounded (English 26.1 characters; 2.76 Hebrew names of 13.4); "ceiling" is the design's bounds
(docs/product-names.md, section 1). An unknown size is a KeyError: the site run refuses one before anything is read.
"""
from collections.abc import Mapping

from shopper.history import Covered
from shopper.search import normalize
from shopper.wordindex import Extra

SIZES = {"realistic": (26, 3, 13), "ceiling": (60, 3, 30)}
CEILING = "ceiling"          # the size whose English name is repeated to its length
# Each Hebrew letter's Latin letters; a final letter is already its plain form after `normalize`.
TABLE = dict(zip("אבגדהוזחטיכלמנסעפצקרשת", ("a", "b", "g", "d", "h", "v", "z", "ch", "t", "y", "k", "l", "m", "n", "s",
                                            "e", "p", "ts", "k", "r", "sh", "t")))


def _cut(text: str, length: int) -> str:
    """`text` cut at the last space that leaves it at most `length` characters; a first word longer than that is cut
    inside it."""
    if len(text) <= length:
        return text
    space = text.rfind(" ", 0, length + 1)
    return text[:space] if space > 0 else text[:length]


def _repeated(text: str, length: int) -> str:
    """`text` repeated, a space between, to exactly `length` characters; a cut that would end on a space takes the next
    character instead."""
    padded = " ".join([text] * (length // (len(text) + 1) + 2))
    cut = padded[:length]
    return cut[:-1] + padded[length] if cut.endswith(" ") else cut


def _stand_in(item: Covered, size: str) -> Extra:
    english, count, each = SIZES[size]
    title = normalize(item.title)
    others = sorted({name for name in map(normalize, item.names.values()) if name and name != title})
    en = _cut("".join(TABLE.get(char, char) for char in " ".join([title, *others])), english)
    if size == CEILING:
        en = _repeated(en, english)
    words = title.split(" ")
    turns = [turn % len(words) for turn in range(1, count + 1)]
    hebrew = [_cut(" ".join(words[turn:] + words[:turn]), each) for turn in turns]
    return Extra(shown="", names=(en, *hebrew))


def stand_ins(covered: Mapping[str, Covered], size: str) -> dict[str, Extra]:
    """Each covered product's stand-in names at `size`, one of SIZES (the module's docstring), by barcode."""
    return {code: _stand_in(item, size) for code, item in covered.items()}

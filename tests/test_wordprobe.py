"""The probe's stand-in names (`shopper.wordprobe`; the product-names plan's Task 3, its call 1, as the Phase 1 review's
F1 changed it): 50 readings made of the published words of donor products picked by the barcodes' SHA-256, each product
taking one by its own barcode's hash, so that a reading's words sit on many products, as the design's measured readings'
did; packed with whole words to the realistic size, and again to the ceiling's; never shown. The products are
`tests/words_registry.py`'s seeded synthetic registry, with a few written here; names and barcodes are synthetic."""
import hashlib
from datetime import date

import pytest

from shopper.history import Covered
from shopper.search import normalize
from shopper.wordindex import Extra, tokens
from shopper.wordprobe import DONORS, READINGS, SIZES, TABLE, stand_ins
from words_registry import registry

DAY = date(2026, 10, 1)
# The brief's table, letter by letter.
LETTERS = {"א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch", "ט": "t", "י": "y",
           "כ": "k", "ל": "l", "מ": "m", "נ": "n", "ס": "s", "ע": "e", "פ": "p", "צ": "ts", "ק": "k", "ר": "r",
           "ש": "sh", "ת": "t"}
# Four barcodes whose SHA-256s come in this order (the test below checks it), so each is that donor of every reading.
ENGLISH_DONOR, FIRST, SECOND, THIRD = "2000000000015", "2000000000022", "2000000000039", "2000000000046"
LONG, ONE_WORD, ONE_LONG_WORD, LATIN = "2000000000053", "2000000000060", "2000000000077", "2000000000084"


def _item(code, names):
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=None, first_covered=DAY, last_wide={})


def _hashed(codes):
    """The barcodes in the order of their SHA-256s, the order the donors are taken in."""
    return sorted(codes, key=lambda code: hashlib.sha256(code.encode()).digest())


def _reading_of(code):
    return int.from_bytes(hashlib.sha256(code.encode()).digest(), "big") % READINGS


def _products():
    """The seeded registry, and four written here: a long title, one word, a first word longer than the realistic
    length, and a Latin title with Hebrew in another name."""
    covered = registry(400, "wordprobe")
    for item in (
            _item(LONG, {"ramilevy": "שוקולד חלב מריר עם אגוזי לוז שלמים ושקדים קלויים במיוחד",
                         "osherad": "שוקולד מריר"}),
            _item(ONE_WORD, {"ramilevy": "במבה"}),
            _item(ONE_LONG_WORD, {"ramilevy": "סופרמרקטשוקולדמרירמיוחדמאוד לבן"}),
            _item(LATIN, {"ramilevy": "Coca-Cola Zero 1.5L", "osherad": "קוקה קולה זירו"})):
        covered[item.code] = item
    return covered


def _starts(words):
    """Every start of every word: a packed name keeps whole words, and cuts one only when none fits."""
    return {word[:end] for word in words for end in range(1, len(word) + 1)}


def test_the_sizes_the_table_and_the_readings_are_the_rulings():
    assert SIZES == {"realistic": (26, 3, 13), "ceiling": (60, 3, 30)}
    assert TABLE == LETTERS
    assert (READINGS, DONORS) == (50, 4)
    with pytest.raises(KeyError):
        stand_ins({}, "Realistic")                       # an unknown size, even with nothing to file


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_are_deterministic_and_show_nothing(size):
    covered = _products()
    found = stand_ins(covered, size)
    assert found == stand_ins(dict(reversed(list(covered.items()))), size)   # the same in any order
    assert set(found) == set(covered)
    assert all(isinstance(extra, Extra) and extra.shown == "" for extra in found.values())
    assert stand_ins({}, size) == {}                    # no product: no donor, and nothing to file


def test_stand_ins_are_made_as_the_docstring_says():
    """Four products: every reading's donors are the four, in their hashes' order. The English name: the first donor's
    normalised title, then its other names, distinct and sorted ("חלב שוקולד" before "שוקולד"), transliterated, packed
    with whole words, each that still fits; at the ceiling packed again to 60, its words gone over until none fits. Each
    Hebrew name: a further donor's normalised title packed to 13 ("בטעם" skipped, and the 27-letter word too); a title
    none of whose words fits cut to 13; at the ceiling, its realistic words repeated to 30."""
    products = [_item(ENGLISH_DONOR, {"ramilevy": "שוקולד חלב מריר", "osherad": "חלב שוקולד", "yochananof": "שוקולד"}),
                _item(FIRST, {"ramilevy": "חטיף תירס בטעם בוטנים אמיתיים"}),
                _item(SECOND, {"ramilevy": "סופרמרקטשוקולדמרירמיוחדמאוד לבן"}),
                _item(THIRD, {"ramilevy": "סופרמרקטשוקולדמרירמיוחדמאוד"})]
    covered = {item.code: item for item in reversed(products)}
    assert _hashed(covered) == [ENGLISH_DONOR, FIRST, SECOND, THIRD]
    realistic = Extra("", ("shvkvld chlb mryr chlb", "חטיפ תירס", "לבנ", "סופרמרקטשוקול"))    # final letters plain
    ceiling = Extra("", ("shvkvld chlb mryr chlb shvkvld shvkvld shvkvld chlb mryr", "חטיפ תירס חטיפ תירס חטיפ תירס",
                         "לבנ לבנ לבנ לבנ לבנ לבנ לבנ", "סופרמרקטשוקול סופרמרקטשוקול"))
    assert stand_ins(covered, "realistic") == {code: realistic for code in covered}
    assert stand_ins(covered, "ceiling") == {code: ceiling for code in covered}
    assert [len(name) for name in ceiling.names] == [56, 29, 27, 27]   # the next word would pass 60 or 30


@pytest.mark.parametrize("size", list(SIZES))
def test_each_product_takes_one_of_50_readings_by_its_barcode_s_hash(size):
    """As the design gave each product one of the trial's 50 readings by its barcode's hash: the products whose hashes
    give the same reading share one stand-in, and there are 50."""
    covered = registry(400, "wordprobe")
    found = stand_ins(covered, size)
    shared = {}
    for code, extra in found.items():
        shared.setdefault(_reading_of(code), set()).add(extra)
    assert len(shared) == READINGS and all(len(held) == 1 for held in shared.values())
    assert len(set(found.values())) == READINGS


@pytest.mark.parametrize("size", list(SIZES))
def test_a_stand_in_brings_words_its_product_lacks(size):
    """Each Hebrew stand-in name is another product's title, so it brings tokens the product's own names lack, as a
    model's reading does (the stand-ins of Task 3 rotated the product's own title, and brought almost none). Here 399
    of the 400, about 4.8 new tokens a product: the one is a product whose reading's words are all its own, which the
    registry's small vocabulary allows."""
    covered = registry(400, "wordprobe")
    new = []
    for code, extra in stand_ins(covered, size).items():
        own = {token for name in covered[code].names.values() for token in tokens(normalize(name))}
        new.append(len({token for name in extra.names[1:] for token in tokens(normalize(name))} - own))
    assert sum(count > 0 for count in new) >= 0.95 * len(new) and sum(new) / len(new) > 4


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_keep_to_their_size(size):
    """Each name at most its length, whole words a space apart; three Hebrew names; at the ceiling each name full: none
    of its own words fits after it."""
    english, count, each = SIZES[size]
    for code, extra in stand_ins(_products(), size).items():
        en, *hebrew = extra.names
        assert len(hebrew) == count, code
        for name, length in ((en, english), *((name, each) for name in hebrew)):
            assert 0 < len(name) <= length and name == name.strip() and "  " not in name, code
            if size == "ceiling":
                assert len(name) + 1 + min(map(len, name.split(" "))) > length, code


def test_the_ceiling_repeats_the_realistic_hebrew_names_words():
    """The ceiling adds bytes to each Hebrew name, never words: its words are the realistic name's."""
    covered = _products()
    realistic, ceiling = stand_ins(covered, "realistic"), stand_ins(covered, "ceiling")
    for code in covered:
        for low, high in zip(realistic[code].names[1:], ceiling[code].names[1:]):
            assert set(high.split(" ")) == set(low.split(" ")) and len(high) > len(low), code


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_hold_only_published_words(size):
    """No model text: each English word is a published name's word written in the table's Latin letters (or the start
    of one, cut when none fits), with no letter of the table left; each Hebrew name's words are words of the products'
    normalised titles, or their starts."""
    covered = _products()
    latin = _starts("".join(TABLE.get(char, char) for char in word)
                    for item in covered.values() for name in item.names.values() for word in normalize(name).split(" "))
    titles = _starts(word for item in covered.values() for word in normalize(item.title).split(" "))
    for code, extra in stand_ins(covered, size).items():
        en, *hebrew = extra.names
        assert not set(en) & set(TABLE), code
        assert set(en.split(" ")) <= latin, code
        for name in hebrew:
            assert set(name.split(" ")) <= titles, code

"""The probe's stand-in names (`shopper.wordprobe`; the product-names plan's Task 3, its call 1): made from each
product's own published words, transliterated and rotated, at the realistic size and at the ceiling, never shown. The
products are `tests/words_registry.py`'s seeded synthetic registry, with a few written here; names and barcodes are
synthetic."""
from datetime import date

import pytest

from shopper.history import Covered
from shopper.search import normalize
from shopper.wordindex import Extra
from shopper.wordprobe import SIZES, TABLE, stand_ins
from words_registry import registry

DAY = date(2026, 10, 1)
# The brief's table, letter by letter.
LETTERS = {"א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch", "ט": "t", "י": "y",
           "כ": "k", "ל": "l", "מ": "m", "נ": "n", "ס": "s", "ע": "e", "פ": "p", "צ": "ts", "ק": "k", "ר": "r",
           "ש": "sh", "ת": "t"}
LONG, ONE_WORD, ONE_LONG_WORD, LATIN = "2000000000015", "2000000000022", "2000000000039", "2000000000046"


def _item(code, names):
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=None, first_covered=DAY, last_wide={})


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


def test_the_sizes_and_the_table_are_the_briefs():
    assert SIZES == {"realistic": (26, 3, 13), "ceiling": (60, 3, 30)}
    assert TABLE == LETTERS


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_are_deterministic_and_show_nothing(size):
    covered = _products()
    found = stand_ins(covered, size)
    assert found == stand_ins(dict(reversed(list(covered.items()))), size)   # the same in any order
    assert set(found) == set(covered)
    assert all(isinstance(extra, Extra) and extra.shown == "" for extra in found.values())


def test_stand_ins_are_made_as_the_brief_says():
    """`en`: the normalised title, then the other names, distinct and sorted ("חלב שוקולד" before "שוקולד"),
    transliterated, cut at a word boundary to the length, and at the ceiling repeated to exactly 60. The Hebrew names:
    the title's words rotated by 1, 2 and 3, each cut at a word boundary to its length."""
    item = _item("2000000000015", {"ramilevy": "שוקולד חלב מריר", "osherad": "חלב שוקולד", "yochananof": "שוקולד"})
    [realistic] = stand_ins({item.code: item}, "realistic").values()
    assert realistic.names == ("shvkvld chlb mryr chlb", "חלב מריר", "מריר שוקולד", "שוקולד חלב")
    [ceiling] = stand_ins({item.code: item}, "ceiling").values()
    text = "shvkvld chlb mryr chlb shvkvld shvkvld"
    assert ceiling.names == ((text + " " + text)[:60], "חלב מריר שוקולד", "מריר שוקולד חלב", "שוקולד חלב מריר")
    # 29 letters in Latin, repeated: the 60th character would be a space, so the next one takes its place
    one = _item("2000000000053", {"ramilevy": "סופרמרקטשוקולדמרירמיוחדמאוד"})
    word = "svprmrktshvkvldmryrmyvchdmavd"
    assert stand_ins({one.code: one}, "ceiling")[one.code].names[0] == f"{word} {word}s"


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_fill_their_size(size):
    english, count, each = SIZES[size]
    found = stand_ins(_products(), size)
    for code, extra in found.items():
        en, *hebrew = extra.names
        assert len(en) <= english and en == en.strip() and "  " not in en, code
        if size == "ceiling":
            assert len(en) == english, code
        assert len(hebrew) == count, code
        assert all(0 < len(name) <= each for name in hebrew), code
    assert found[LONG].names[0] == {"realistic": "shvkvld chlb mryr em agvzy",
                                    "ceiling": "shvkvld chlb mryr em agvzy lvz shlmym vshkdym klvyym bmyvchd"}[size]
    # A first word longer than the length is cut inside it: the English one at 26, the Hebrew one at 13.
    word = "svprmrktshvkvldmryrmyvchdmavd"
    assert found[ONE_LONG_WORD].names == {
        "realistic": (word[:26], "לבנ", "סופרמרקטשוקול", "לבנ"),
        "ceiling": (f"{word} lbn {word[:26]}", "לבנ", "סופרמרקטשוקולדמרירמיוחדמאוד", "לבנ")}[size]
    assert found[ONE_WORD].names[1:] == ("במבה",) * 3                # one word rotates to itself
    assert found[LATIN].names[0].startswith("coca-cola zero 1.5l kvkh")


@pytest.mark.parametrize("size", list(SIZES))
def test_stand_ins_hold_only_the_table_s_letters_and_the_names_own(size):
    """No model text: `en` holds the table's letters, spaces and the names' own characters that are not letters of the
    table; each Hebrew name holds only the normalised title's characters."""
    covered = _products()
    made = set("".join(TABLE.values()))
    for code, extra in stand_ins(covered, size).items():
        item = covered[code]
        title = normalize(item.title)
        own = {char for name in item.names.values() for char in normalize(name)}
        en, *hebrew = extra.names
        assert not set(en) & set(TABLE), code
        assert set(en) <= made | {" "} | (own - set(TABLE)), code
        for name in hebrew:
            assert set(name) <= set(title), code

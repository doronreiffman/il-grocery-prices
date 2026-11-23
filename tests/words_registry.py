"""A seeded synthetic registry for the word index's tests (`tests/test_wordindex.py`) and the brute-force answer the
index is checked against. Everything is made here from a seeded `random.Random`: barcodes, names, sizes and the model's
names; nothing reads the clock.

`registry(n, seed)` gives `n` covered products whose names are drawn from a small vocabulary by Zipf weights (the first
word of a list the most common), Hebrew mostly and Latin now and then, with punctuation inside a word ("דאו.דריי",
"3%", "coca-cola", "1.5L"), quotes the normalising drops ("קוטג'", 'בד"צ'), final letters, a Hebrew point (category Mn)
and a letter outside the basic plane (U+1D400), and some with a size. `extras(covered, seed)` gives about half of them
model names. `brute(entries, query, today)` is what the word index must add to today's list, worked from every entry
with no index at all."""
import random
from datetime import date
from decimal import Decimal
from functools import cache

from shopper.history import Covered
from shopper.search import normalize
from shopper.wordindex import SHOWN, Extra, order_key, tokens

COLUMNS = ("shufersal-deal", "ramilevy", "osherad", "carrefour-city", "yochananof")
HEBREW = ("חלב", "שוקולד", "גבינה", "תנובה", "לבן", "מריר", "יוטבתה", "טרי", "קוטג'", "שמנת", "חלבון", "שוקולדים",
          "דאו.דריי", "3%", "5%", "9%", "לחם", "מלא", "פרוס", "במבה", "ביסלי", "גריל", "אסם", "עלית", "קפה", "נמס",
          "פסטה", "ספגטי", "רוטב", "עגבניות", "שמן", "זית", "כתית", "מים", "מינרלים", "סודה", "תפוזים", "אורז",
          "בסמטי", "סוכר", "קמח", "לבנה", "משקה", "סויה", 'בד"צ', "חטיף", "פִיתה", "ש.ב.", "גבינות", "צהובה")
LATIN = ("Milk", "chocolate", "DARK", "coca-cola", "Zero", "cheese", "cottage", "diet", "max", "\U0001d400lpha",
         "choco", "light", "1.5L", "Tnuva", "elite")
ENGLISH = ("milk", "chocolate", "cheese", "bread", "coffee", "pasta", "oil", "water", "snack", "rice", "sugar", "flour",
           "yogurt", "cream", "juice", "orange", "dark", "white", "olive", "\U0001d400lpha")
SIZES = (None, None, None, (Decimal("80"), "gml"), (Decimal("250"), "gml"), (Decimal("500"), "gml"),
         (Decimal("1000"), "gml"), (Decimal("1500"), "gml"), (Decimal("6"), "unit"))
FIRST = date(2026, 10, 1)


def _zipf(words: tuple[str, ...]) -> list[float]:
    return [1 / rank for rank in range(1, len(words) + 1)]


def _words(rng: random.Random, count: int) -> list[str]:
    hebrew, latin = rng.choices(HEBREW, _zipf(HEBREW), k=count), rng.choices(LATIN, _zipf(LATIN), k=count)
    return [latin[n] if rng.random() < 0.15 else hebrew[n] for n in range(count)]


def registry(n: int, seed: str) -> dict[str, Covered]:
    """`n` covered products, each named in one to three columns; a column's name is the product's words, shuffled, now
    and then with one more; the title is the longest name, a tie to the first in code-point order, as the registry has
    it."""
    rng = random.Random(seed)
    covered = {}
    for number in range(n):
        code = f"7290{number:09d}"
        base = _words(rng, rng.randint(1, 3))
        names = {}
        for column in sorted(rng.sample(COLUMNS, rng.randint(1, 3))):
            words = rng.sample(base, len(base))
            if rng.random() < 0.3:
                words.append(_words(rng, 1)[0])
            names[column] = " ".join(words)
        title = min(names.values(), key=lambda name: (-len(name), name))
        covered[code] = Covered(code=code, title=title, names=names, size=rng.choice(SIZES), first_covered=FIRST,
                                last_wide={column: FIRST for column in names})
    return covered


def extras(covered: dict[str, Covered], seed: str) -> dict[str, Extra]:
    """Model names for about half the products: an English name of one to three words, shown or (one time in five,
    as for a held reading) not, then none to two everyday Hebrew names."""
    rng = random.Random(seed)
    found = {}
    for code in sorted(covered):
        if rng.random() < 0.5:
            continue
        english = " ".join(rng.choices(ENGLISH, _zipf(ENGLISH), k=rng.randint(1, 3))).capitalize()
        hebrew = tuple(" ".join(_words(rng, rng.randint(1, 2))) for _ in range(rng.randint(0, 2)))
        found[code] = Extra(shown=english if rng.random() < 0.8 else "", names=(english, *hebrew))
    return found


@cache
def _starts(names: tuple[str, ...]) -> frozenset[str]:
    """Every start, one character or more, of every token of the names."""
    return frozenset(token[:end] for name in names for token in tokens(name) for end in range(1, len(token) + 1))


def _matches(entry: list, words: list[str]) -> bool:
    starts = _starts(tuple(entry[4:]))
    return all(word in starts for word in words)


def matches(entry: list, query: str) -> bool:
    """The word index's match, worked without the index: every word of the normalised query starts some token of some
    name of the entry."""
    return _matches(entry, normalize(query).split(" "))


def brute(entries: list[list], query: str, today: list[list]) -> list[str]:
    """The barcodes the word index must add to `today`, in order: none when today's list is full or no word has two
    characters (the index is not read); else every entry that matches and is not in `today`, ranked by `order_key`,
    the first `SHOWN - len(today)`."""
    words = normalize(query).split(" ")
    if len(today) >= SHOWN or not any(len(word) >= 2 for word in words):
        return []
    known = {entry[0] for entry in today}
    found = [entry for entry in entries if entry[0] not in known and _matches(entry, words)]
    return [entry[0] for entry in sorted(found, key=lambda entry: order_key(query, entry))][:SHOWN - len(today)]

"""Sizes: a product's quantity and unit as a price file states them, in one scale (rule B7).

A price file states a size as `Quantity` (a number) and `UnitQty` (a Hebrew unit string). A size is
read into an amount and a kind: kilos become grams and litres millilitres (times 1000), and grams and
millilitres are one kind, "gml", so a litre and a thousand grams are the same size; counted items are
the kind "unit". The unit strings read are the published vocabulary of the selection day in `UNITS`,
after trimming the spaces around them; any other string, "לא ידוע" ("unknown") and an empty one
among them, is "not stated". So is a quantity that is not a number, is not finite ("NaN",
"Infinity") or is not above zero (38,941 rows of 2026-11-02 state 0.00).

A count of one is not a size either: it carries none. 791,019 rows of 2026-11-02 say "1 unit",
among them products with real weights, so one unit must not count as a disagreement with a size in
grams or millilitres. A count above one ("6 units") is a size.

Amounts are Decimal, never float, and are kept plain: 1.50 is 1.5, and 1000 is never 1E+3.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

ONE = Decimal(1)
THOUSAND = Decimal(1000)

# The unit strings of 2026-11-02, the selection day, with their rows over the five chains' tables
# (5,140,268 rows, 21 strings). Every string of at least 1,000 rows is decided here: read, or left
# "not stated" with the reason.
UNITS: dict[str, tuple[str, Decimal]] = {
    "גרם": ("gml", ONE),  # 2,435,915
    "יחידות": ("unit", ONE),  # 932,478
    "מיליליטר": ("gml", ONE),  # 870,925
    "קילוגרם": ("gml", THOUSAND),  # 393,400
    # "לא ידוע" 251,026: "unknown", the files' own word for a size not stated
    "ליטר": ("gml", THOUSAND),  # 225,788
    # "מטרים" 22,272: metres, the length of a roll (toilet paper, paper towels, foil, cling film);
    # neither a weight, a volume nor a count, so not a size the basket compares
    "יח'": ("unit", ONE),  # 4,207
    'מ"ל': ("gml", ONE),  # 2,454
    'ק"ג': ("gml", THOUSAND),  # 761
    # Below the 1,000-row threshold, and read because each spells a unit already read above
    "ליטרים": ("gml", THOUSAND),  # 663
    "קילוגרמים": ("gml", THOUSAND),  # 141
    "יח": ("unit", ONE),  # 13
    "מ'ל": ("gml", ONE),  # 5
    "גרמים": ("gml", ONE),  # 1
    "קילו": ("gml", THOUSAND),  # none that day
    "יחידה": ("unit", ONE),  # none that day
    # Below the threshold and not read: "קרמול" 130, "מטר" 58, "1" 23, "100 יח'" 4, "קרטון" 3, 'ס"מ' 1
}


@dataclass(frozen=True)
class Size:
    """A stated size: `amount` in grams or millilitres when `kind` is "gml", in items when it is "unit"."""
    amount: Decimal
    kind: str


def normal_size(quantity: str, unit: str) -> Size | None:
    """The size a (quantity, unit) pair states, or None when it states none (see the module's rules)."""
    known = UNITS.get(unit.strip())
    if known is None:
        return None
    kind, factor = known
    try:
        amount = Decimal(quantity)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    if kind == "unit" and amount == 1:
        return None
    return Size(Decimal(plain(amount * factor)), kind)


def plain(d: Decimal) -> str:
    """`d` written as a plain number: no exponent and no trailing zeros after the point."""
    return format(d.normalize(), "f")

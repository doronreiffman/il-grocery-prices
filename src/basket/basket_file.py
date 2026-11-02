"""The basket file: the fixed list of products the basket prices, read and checked.

The file is JSON: a version, the day the list holds from (`since`), the day its products were chosen
on (`selection_day`) and the items. An item has a barcode, a name in English and in Hebrew, a size
(`amount` as a string, `kind` "gml" or "unit", as `basket.units` has them), a category and, optionally,
`coverage`: a dict kept exactly as given, for the reader of the file and used by no rule. The days are
the file's own; nothing here reads the clock.

A list is refused with `BadBasket` when:
- a code is not a real GS1 barcode (`basket.barcode.is_gs1`);
- two items have one code once leading zeros are stripped: a product is a barcode, and is listed once;
- a name, English or Hebrew, is empty;
- a size's kind is neither "gml" nor "unit", or its amount is not a number above zero;
- it holds fewer than `min_items` or more than `max_items` items;
- the file is not in this layout: not JSON, a field missing, text where a number or a date belongs.

A message about an item names the item's code.

Amounts are Decimal, never float, and are kept plain, as in `basket.units`.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from basket.barcode import is_gs1, normalize
from basket.units import Size, plain

KINDS = frozenset({"gml", "unit"})
DEFAULT_BASKET = Path(__file__).parent / "baskets" / "v1.json"  # the package's approved basket


class BadBasket(Exception):
    """The basket file breaks one of its rules."""


@dataclass(frozen=True)
class BasketItem:
    code: str
    name_en: str
    name_he: str
    size: Size
    category: str
    coverage: dict[str, str] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Basket:
    version: str
    since: date
    selection_day: date
    items: tuple[BasketItem, ...]


def load_basket(path: Path, min_items: int = 25, max_items: int = 40) -> Basket:
    """The basket `path` holds, or `BadBasket` naming the first rule it breaks."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        version = _text(document, "version")
        since = date.fromisoformat(_text(document, "since"))
        selection_day = date.fromisoformat(_text(document, "selection_day"))
        listed = document["items"]
        if not isinstance(listed, list):
            raise TypeError("items is not a list")
    except (KeyError, TypeError, ValueError) as error:
        raise BadBasket(f"{path}: not in the basket file's layout ({error!r})") from error
    items: list[BasketItem] = []
    first_with: dict[str, str] = {}
    for raw in listed:
        item = _read_item(raw)
        digits = normalize(item.code)
        if digits in first_with:
            raise BadBasket(f"item {item.code!r} is item {first_with[digits]!r} again: a product is listed once")
        first_with[digits] = item.code
        items.append(item)
    if not min_items <= len(items) <= max_items:
        raise BadBasket(f"{len(items)} items; the basket holds {min_items} to {max_items}")
    return Basket(version, since, selection_day, tuple(items))


def _read_item(raw: object) -> BasketItem:
    """One item of the file, or `BadBasket` for the first rule it breaks (the duplicate rule is the list's)."""
    try:
        code = _text(raw, "code")
        name_en = _text(raw, "name_en")
        name_he = _text(raw, "name_he")
        amount = Decimal(_text(raw["size"], "amount"))
        kind = _text(raw["size"], "kind")
        category = _text(raw, "category")
        coverage = raw.get("coverage", {})
        if not isinstance(coverage, dict):
            raise TypeError("coverage is not a dict")
    except (KeyError, TypeError, InvalidOperation) as error:
        label = raw.get("code") if isinstance(raw, dict) else raw
        raise BadBasket(f"item {label!r}: not in the basket file's layout ({error!r})") from error
    if not is_gs1(code):
        raise BadBasket(f"item {code!r}: not a GS1 barcode (8 to 14 digits, the last a check digit that holds)")
    if not name_en.strip() or not name_he.strip():
        raise BadBasket(f"item {code!r}: a name is empty")
    if kind not in KINDS:
        raise BadBasket(f"item {code!r}: size kind {kind!r} is neither 'gml' nor 'unit'")
    if not amount.is_finite() or amount <= 0:
        raise BadBasket(f"item {code!r}: size amount {amount} is not a number above zero")
    return BasketItem(code, name_en, name_he, Size(Decimal(plain(amount)), kind), category, coverage)


def _text(raw: object, key: str) -> str:
    """`raw[key]`, which must be text."""
    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} is not text")
    return value

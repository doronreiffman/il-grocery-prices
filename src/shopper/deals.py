"""The deal price (P4 as the survey amendment's S4 reads it; docs/shopper-site.md; the plan's question C and the
pre-flight's S4, S6 and S10).

A deal's price is a unit's price after the promotion when buying the least that qualifies, a kilogram's when the link
is weighed (`bIsWeighted` 1): the research sample's "2 for ₪100" on meat is stored as 1.5 for ₪75, the same ₪50 a
kilogram. By the link's kind (`shopper.promotions.kind`):

- A fixed price (`RewardType` 3) is the link's `DiscountedPrice`.
- "N for ₪M" (1 and 10) is `DiscountedPrice` ÷ `MinQty`, with "buy N" kept as the condition (`buy`; 1.5 for that
  meat). Both read from the fields of the variant most of the column's stores carry (Task 5), and a price is read
  when both read as numbers, N above 0.
- Percent off (2) is the stores' own figure: the median of the column's counted stores' `DiscountedPrice` on the
  link, its lowest and highest kept and shown as P2 shows the listed range. The rate is the check: the price agrees
  when `DiscountRate` is above 0 and below 100 and the price is within ₪0.01 of the column's median listed price ×
  (1 − rate/100) rounded half up to agorot (`rate_agrees` and its `agrees`, the one such rule; Task 5 applies it
  to each store's own price).
  The design first computed the price from the rate and kept `DiscountedPrice` as the check; the survey's shelf links
  of 7 November (coupons out) found `DiscountedPrice` to be each store's own price after the rate (Shufersal 240,777
  of 241,320, Carrefour all 13,664 with a store price), so S4 (the owner, 2026-11-08) turned them round. Checked so,
  Shufersal's percent-off links agree with their own formats' medians on 236,672 of 241,320 (98%). At Rami Levy the
  shelf `DiscountedPrice` is the store's own price × 0.75 or × 0.50 exactly (775 and 408 links), while the rate reads
  50.00 on 509 of its 2,045 shelf percent-off links and 25.32 to 25.70 on most of the others. A drifting rate
  disagrees wherever it moves the figure by more than an agora (25.32% off ₪10.00 is ₪7.47, the price ₪7.50): on 7
  November 138 of the 2,045 agreed with the chain's median listed price, Rami Levy being one column. Yochananof's 162
  links at rates of 3 to 6% agreed with neither price. The links that disagree show "price not read" until the
  reader, rather than a price a few agorot off.
- A `RewardType` 0 link has no kind and no deal (S2).

Then, for every kind, the deal is valid only when its price is above ₪0.01 and below twice the listed price (both
ends exclusive; per kilogram when weighed). With no listed price there is nothing to check against, so no deal is
valid. A deal that is not valid keeps any price it read, so a page can show it, says why, and is never ranked.
The price is a `Fraction` and every check reads it exactly (the pre-flight's S6): 3 for ₪0.04 is 1/75 of a shekel,
above the floor, though it would round to ₪0.01. Two places are only for writing it out (Task 6), and a deal read
back from the items table takes its price from the fraction's text (`deal_from_row`, the pre-flight's S11).
"""
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

from shopper.promotions import kind, number

AGREE = Decimal("0.01")         # question C: the percent-off rate check, to the agora
_FLOOR = Fraction(1, 100)       # the design's range: a deal above ₪0.01
_ONE = Decimal(1)
_NO_PRICE = "no price in the fields"


@dataclass(frozen=True)
class StorePrices:
    """One link's `DiscountedPrice` over the column's counted stores carrying it: B5's median, the lowest and the
    highest (Task 5's `discounted_median`, `discounted_low` and `discounted_high`)."""
    median: Decimal
    low: Decimal
    high: Decimal


@dataclass(frozen=True)
class Deal:
    """A link's deal (the module's docstring)."""
    price: Fraction | None   # a unit's price (a kilogram's when weighed) when buying the least that qualifies; exact
    per: str                 # "unit" or "kg" (bIsWeighted 1)
    buy: Decimal             # N for "N for ₪M" (1.5 for a weighed 1.5 for ₪75), else 1
    low: Decimal | None      # percent off: the stores' DiscountedPrice range; else None
    high: Decimal | None
    valid: bool
    why: str | None          # when not valid: why, in the page's words


def agrees(price: Decimal, base: Decimal, rate: Decimal) -> bool:
    """Whether `price` is within ₪0.01 of `base` × (1 − rate/100) rounded half up to agorot (question C). Exact while
    `base` and `rate` hold 28 digits between them, `Decimal`'s precision (the tables' prices hold 12)."""
    figure = (base * (100 - rate) / 100).quantize(AGREE, rounding=ROUND_HALF_UP)
    return abs(price - figure) <= AGREE


def rate_agrees(text: str, price: Decimal, base: Decimal) -> bool:
    """Question C's percent-off check: the `DiscountRate` as published (`text`) reads as a number above 0 and below 100,
    and `price` agrees with `base` at that rate (`agrees`). The deal checks it against the column's median listed price,
    Task 5 measures it against each store's own; the bound comes first, so a rate such as 1E+30, whose figure would not
    compute, never agrees."""
    rate = number(text)
    return rate is not None and 0 < rate < 100 and agrees(price, base, rate)


def _checked(price: Fraction, per: str, buy: Decimal, low: Decimal | None, high: Decimal | None,
             listed: Decimal | None, disagrees: bool) -> Deal:
    """The deal with its checks in order: a listed price to check against, the rate (percent off), the range."""
    why = None
    if listed is None:
        why = "no listed price"
    elif disagrees:
        why = "the rate and the price disagree"
    elif price <= _FLOOR:
        why = "not above ₪0.01"
    elif price >= 2 * Fraction(listed):
        why = "not below twice the listed price"
    return Deal(price, per, buy, low, high, why is None, why)


def deal(slug: str, item: Mapping[str, str], listed: Decimal | None, stores: StorePrices | None = None) -> Deal:
    """The deal of one link (`item`, the link's fields as published) against the column's median listed price
    (`listed`, Task 6), percent off at the carrying stores' `DiscountedPrice` (`stores`; with none, the link's own
    `DiscountedPrice` as a one-store median). A `RewardType` the chain's files never carried stops the chain (P10)."""
    found = kind(slug, item)
    per = "kg" if item["bIsWeighted"] == "1" else "unit"
    if found is None:
        return Deal(None, per, _ONE, None, None, False, "no kind link")
    amount = number(item["DiscountedPrice"])
    if found == "percent_off":
        if stores is None and amount is not None:
            stores = StorePrices(amount, amount, amount)
        if stores is None:
            return Deal(None, per, _ONE, None, None, False, _NO_PRICE)
        price = Fraction(stores.median)
        disagrees = listed is not None and not rate_agrees(item["DiscountRate"], stores.median, listed)
        return _checked(price, per, _ONE, stores.low, stores.high, listed, disagrees)
    quantity: Decimal | None = _ONE
    if found == "n_for_m":
        quantity = number(item["MinQty"])
        if quantity is not None and quantity <= 0:
            quantity = None
    if amount is None or quantity is None:
        return Deal(None, per, _ONE if quantity is None else quantity, None, None, False, _NO_PRICE)
    return _checked(Fraction(amount) / Fraction(quantity), per, quantity, None, None, listed, False)


def deal_from_row(struct: Mapping[str, Any]) -> Deal:
    """The deal a row of the items table's `promotions` struct holds (Task 6; the pre-flight's S11), the one place a
    `Deal` is rebuilt: the price from `price_exact`, the `Fraction`'s text ("109/75"), None when NULL, and never from
    the two-place `price`, which is for the eye."""
    exact = struct["price_exact"]
    return Deal(None if exact is None else Fraction(exact), struct["per"], struct["buy"], struct["low"],
                struct["high"], struct["valid"], struct["why"])

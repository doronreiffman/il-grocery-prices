"""Which promotions count, their conditions from the chains' fields, and a format change stopping the chain (P3, P5's
field half, P10; docs/shopper-site.md, with its "Changed after the survey", S2, S3 and S5, and the plan's question N).

Every value here was read from the files: the survey of every included store's full promotion file of 5 and 7
November 2026 (`shopper.survey`; the figures in docs/operations.md, "Measured for the shopper site"). Each chain's
promotion fixtures hold its field sets, no more and no fewer (tests/test_promotions.py).

P3, which promotions count. A promotion is in a day when the date part of its start is on or before the day and the
date part of its end on or after it (the files' times are Israel wall-clock with no zone, so only the dates are
compared; a date that does not read is a format change). Dropped and counted: coupons (`AdditionalIsCoupon` 1), and,
as S2 reads the files, any promotion holding a link of `RewardType` 12 (a basket-level reward: paying by card,
delivery over a basket, a voucher) or 6 (a gift), whole, not link by link: Shufersal's two 12 promotions carry
"N for ₪M" links that are the card payers' own terms, so keeping the other links would show them as deals open to
all. `RewardType` is an item field, so that test reads a promotion's links once the reader yields them; `keep`, which
sees only a promotion's own fields, drops coupons as they are read. The kinds: 1 and 10 "N for ₪M", 2 percent off,
3 a fixed price, as the texts read at all five chains. S2's second reading: a `RewardType` 0 link has no kind and
never a price effect, whether or not it carries a `DiscountedPrice` (Rami Levy writes one on the condition side of
its two-group promotions, Shufersal on nearly every coupon's), so an item is on promotion only through a link of a
kind.

P5, the conditions the fields give. Minimum spend is the largest `MinPurchaseAmount` above zero over every group of
the promotion, the item-less groups and the `RewardType` 0 group included, since that is where the files put it
(never on the group with the deal, in the promotions that hold a 0 group); an amount that does not read is a format
change, since read as none it would show the deal without its condition. Restrictions come from `ClubID`, read by its
form, each form the survey saw read by one rule (S3): a bare "0" and "()" are none; a bare code 1 to 3 is that
restriction, with no name; "N - label" (Shufersal, Yochananof) is read by its leading code only, 0 none and 1 to 3 by
RESTRICTIONS (question K's codes: 1 club, 2 the chain's card, 3 other), the label the programme's name when the code
is not 0; and the list (Rami Levy, Carrefour), `N=name` terms joined by `|` and `&` inside parentheses, is read term
by term, its parentheses dropped, code 1 to 3 by RESTRICTIONS and a programme named under code 0 "other", since
Carrefour names its credit and app clubs there. Every name is kept as published, in the field's order, once.

P10, the codes half (the field sets are `shopper.promofile`'s half). A code outside what a chain's files were seen to
carry stops that chain's promotions with an error naming the chain, the field and the value: a `ClubID` of any other
form or a code above 3; a `RewardType` outside REWARD_TYPES[slug] (each chain's own codes, so Osher Ad's first 0
stops it); a `DiscountType` outside DISCOUNT_TYPES[slug] (watched only: no rule reads it); an `IsGiftItem` that is
neither empty nor a positive number. `IsGiftItem` marks no gift at any chain: where set it is the deal's quantity
(equal to the link's `MinQty` on 100% of Osher Ad's set links, 98.6% of Carrefour's, 93.3% of Rami Levy's and every
Shufersal value from 1.5 to 6.5; Yochananof's are kilograms), so it is read for nothing but its form (question N),
and a new quantity, Rami Levy's first "11 for ₪20", passes; GIFT_VALUES keeps the values seen as the evidence.
`keep` checks the target and the gift value of every promotion, coupons included, so a changed code stops the chain
even on a promotion it then drops; `check_codes` covers the groups and links of a kept promotion, which `keep` cannot
see, and `not_shelf` checks the links of the promotion it drops.
"""
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from shopper.promofile import FieldSets, PromotionFormatChanged, PromotionRead

ROOT = frozenset({"ChainID", "SubChainID", "StoreID", "BikoretNo", "Promotions"})
PROMOTION = frozenset({"PromotionUpdateTime", "AllowMultipleDiscounts", "PromotionID", "PromotionDescription",
                       "PromotionStartDateTime", "PromotionEndDateTime", "PromotionStartHour", "PromotionEndHour",
                       "PromotionDays", "RedemptionLimit", "MinNoOfItemOffered", "ClubID", "IsGiftItem",
                       "AdditionalIsCoupon", "AdditionalRestrictions", "Remarks", "Groups"})
GROUP = frozenset({"GroupID", "MinPurchaseAmount", "DiscountType", "PromotionItems"})
ITEM = frozenset({"ItemCode", "ItemType", "RewardType", "MinQty", "MaxQty", "DiscountRate", "DiscountedPrice",
                  "DiscountedPricePerMida", "bIsWeighted"})
_ONE_ITEM_SET = FieldSets(frozenset({ROOT}), frozenset({PROMOTION}), frozenset({GROUP}), frozenset({ITEM}))
# Second-group items without MaxQty: Shufersal 9,831 and Yochananof 652 on 7 November (S5 (a)).
_ITEMS_WITH_OR_WITHOUT_MAX_QTY = FieldSets(frozenset({ROOT}), frozenset({PROMOTION}), frozenset({GROUP}),
                                           frozenset({ITEM, ITEM - {"MaxQty"}}))
KNOWN_FIELDS: dict[str, FieldSets] = {
    "shufersal": _ITEMS_WITH_OR_WITHOUT_MAX_QTY,
    "ramilevy": _ONE_ITEM_SET,
    "osherad": _ONE_ITEM_SET,
    "carrefour": _ONE_ITEM_SET,
    "yochananof": _ITEMS_WITH_OR_WITHOUT_MAX_QTY,
}
REWARD_TYPES: dict[str, frozenset[str]] = {
    "shufersal": frozenset({"0", "1", "2", "3", "6", "10", "12"}),
    "ramilevy": frozenset({"0", "1", "2", "3", "10"}),
    "osherad": frozenset({"1", "3", "10"}),
    "carrefour": frozenset({"0", "1", "2", "3", "10", "12"}),
    "yochananof": frozenset({"0", "1", "2", "3", "10"}),
}
KINDS = {"1": "n_for_m", "10": "n_for_m", "2": "percent_off", "3": "fixed_price"}   # RewardType 0 has no kind (S2)
NOT_SHELF = {"6": "gift", "12": "basket_reward"}   # a promotion holding one such link is no shelf deal (S2)
DISCOUNT_TYPES: dict[str, frozenset[str]] = {
    "shufersal": frozenset({"", "0", "1"}),
    "ramilevy": frozenset({"", "0", "1"}),
    "osherad": frozenset({"", "1"}),
    "carrefour": frozenset({"", "0", "1"}),
    "yochananof": frozenset({"", "0"}),
}
GIFT_VALUES: dict[str, frozenset[str]] = {   # as published ("2.0", not "2"); the evidence, not the check (question N)
    "shufersal": frozenset({"", "0.5", "1.5", "2.5", "3.5", "4.5", "6.5"}),
    "ramilevy": frozenset({""} | {str(n) for n in range(1, 11)}),
    "osherad": frozenset({""} | {str(n) for n in range(1, 11)} | {"12"}),
    "carrefour": frozenset({""} | {str(n) for n in range(1, 9)} | {"10"}),
    "yochananof": frozenset({"", "0.5", "2.0", "3.0", "4.0"}),
}
# Question K's codes; a programme named under code 0 in a list is "other" (S3).
RESTRICTIONS = {"1": "club", "2": "chain_card", "3": "other"}
_ORDER = ("club", "chain_card", "other")
_NO_RESTRICTION = "0"
_CODES = frozenset("0123456789")


@dataclass(frozen=True)
class Target:
    """Who a promotion is for, from its `ClubID` (P5)."""
    restrictions: tuple[str, ...]   # the codes present, as words, in the order club, chain_card, other; () for none
    names: tuple[str, ...]          # every programme named, as published, in the field's order, without repeats

    @property
    def restricted(self) -> bool:
        return bool(self.restrictions)


def number(text: str) -> Decimal | None:
    """The text as a finite decimal, or None."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def date_part(text: str) -> date | None:
    """The date part of a promotion's date and time ("2026-11-01T00:00:00.000"), or None."""
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _code(text: str) -> bool:
    return bool(text) and set(text) <= _CODES


def _terms(club_id: str) -> list[tuple[str, str | None, bool]] | None:
    """The field's (code, name or None, from a list) terms by its form; None for a form not seen."""
    if club_id == "()":
        return []
    if _code(club_id):
        return [(club_id, None, False)]
    code, dash, label = club_id.partition(" - ")
    if dash and _code(code) and label:
        return [(code, label, False)]
    if not (club_id.startswith("(") and club_id.endswith(")")):
        return None
    terms = []
    for term in club_id.replace("(", "").replace(")", "").replace("&", "|").split("|"):
        code, equals, name = term.partition("=")
        if not (equals and _code(code) and name):
            return None
        terms.append((code, name, True))
    return terms


def target(slug: str, club_id: str) -> Target:
    """The restrictions and programmes `club_id` names (P5's field half, S3); P10 on a form or code not seen."""
    terms = _terms(club_id)
    if terms is None:
        raise PromotionFormatChanged(f"{slug}: ClubID form not seen in the chain's files: {club_id!r}")
    words: set[str] = set()
    names: list[str] = []
    for code, name, listed in terms:
        if code == _NO_RESTRICTION and not listed:
            continue  # none: the dash form's label for code 0 is "all customers", no programme
        if code == _NO_RESTRICTION:
            words.add("other")  # a programme named under code 0 restricts (S3)
        elif code in RESTRICTIONS:
            words.add(RESTRICTIONS[code])
        else:
            raise PromotionFormatChanged(f"{slug}: ClubID form not seen in the chain's files: {club_id!r}")
        if name is not None and name not in names:
            names.append(name)
    return Target(tuple(word for word in _ORDER if word in words), tuple(names))


def gift_value(slug: str, value: str) -> None:
    """P10 unless `value` is empty or a positive number: `IsGiftItem` is watched by its form (question N)."""
    if value == "":
        return
    amount = number(value)
    if amount is None or amount <= 0:
        raise PromotionFormatChanged(f"{slug}: IsGiftItem {value!r} is not a quantity")


def is_coupon(promotion: Mapping[str, str]) -> bool:
    return promotion["AdditionalIsCoupon"] == "1"


def keep(slug: str) -> Callable[[Mapping[str, str]], bool]:
    """`shopper.promofile.read_promotions`' `keep` for the chain: every promotion's target and gift value checked
    (P10), coupons included, then the coupons dropped (P3)."""
    def keeps(promotion: Mapping[str, str]) -> bool:
        target(slug, promotion["ClubID"])
        gift_value(slug, promotion["IsGiftItem"])
        return not is_coupon(promotion)
    return keeps


def _reward_type(slug: str, item: Mapping[str, str]) -> str:
    """The link's `RewardType`, P10 when the chain's files were never seen to carry it."""
    code = item["RewardType"]
    if code not in REWARD_TYPES[slug]:
        raise PromotionFormatChanged(f"{slug}: RewardType {code} not seen in the chain's files")
    return code


def kind(slug: str, item: Mapping[str, str]) -> str | None:
    """The link's kind of deal (KINDS); None for `RewardType` 0, 6 and 12."""
    return KINDS.get(_reward_type(slug, item))


def has_price_effect(slug: str, item: Mapping[str, str]) -> bool:
    """Whether the link prices the item: a link of a kind; a `RewardType` 0 link never, priced or not (S2)."""
    return kind(slug, item) is not None


def not_shelf(slug: str, record: PromotionRead) -> str | None:
    """"gift" or "basket_reward" when any of the promotion's links carries `RewardType` 6 or 12 (the first such link's),
    so the whole promotion is dropped and counted (S2); None for a shelf promotion. Every link's code is checked."""
    found = None
    for link in record.links:
        code = _reward_type(slug, link.item)
        if found is None and code in NOT_SHELF:
            found = NOT_SHELF[code]
    return found


def check_codes(slug: str, record: PromotionRead) -> None:
    """P10 over what `keep` cannot see: every group's `DiscountType` and every link's `RewardType`."""
    for group in record.groups:
        if group["DiscountType"] not in DISCOUNT_TYPES[slug]:
            raise PromotionFormatChanged(f"{slug}: DiscountType {group['DiscountType']} not seen in the chain's files")
    for link in record.links:
        _reward_type(slug, link.item)


def _day(promotion: Mapping[str, str], field: str) -> date:
    found = date_part(promotion[field])
    if found is None:
        raise PromotionFormatChanged(f"{field} {promotion[field]!r} is not a date")
    return found


def dates(promotion: Mapping[str, str]) -> tuple[date, date]:
    """The date parts of `PromotionStartDateTime` and `PromotionEndDateTime`; P10 when one does not read."""
    return _day(promotion, "PromotionStartDateTime"), _day(promotion, "PromotionEndDateTime")


def in_day(promotion: Mapping[str, str], day: date) -> bool:
    """Whether the promotion runs on `day`: it starts on or before it and ends on or after it (P3)."""
    start, end = dates(promotion)
    return start <= day <= end


def min_spend(groups: Iterable[Mapping[str, str]]) -> Decimal | None:
    """The largest `MinPurchaseAmount` above zero over every group, or None (S2); P10 on an amount that does not read,
    since read as none it would show a deal without its condition."""
    amounts = []
    for group in groups:
        text = group["MinPurchaseAmount"]
        amount = number(text)
        if amount is None and text != "":
            raise PromotionFormatChanged(f"MinPurchaseAmount {text!r} is not an amount")
        if amount is not None and amount > 0:
            amounts.append(amount)
    return max(amounts) if amounts else None

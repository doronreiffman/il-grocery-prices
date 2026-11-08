"""Promotion files: each promotion a full promotion file holds, with its groups and item links, read as a stream.

A full promotion file (`PromoFull`) is a `<Root>` holding the store's fields (`ChainID`, `SubChainID`, `StoreID`,
`BikoretNo`) and `<Promotions>`. Each `<Promotion>` holds its fields (`PromotionID`, its dates, `ClubID`,
`IsGiftItem`, `AdditionalIsCoupon` and the rest), then `<Groups>`; each `<Group>` its fields (`GroupID`,
`MinPurchaseAmount`, `DiscountType`) and `<PromotionItems>`; each `<PromotionItem>` one item's fields (`ItemCode`,
`RewardType`, `MinQty`, `DiscountRate`, `DiscountedPrice` and the rest). A file comes in the layouts a price file comes
in, a gzip, a ZIP or plain XML with or without a UTF-8 BOM, read through `basket.pricefile`'s `bodies` and
`parse_events`, so it is refused with BadPriceFile as a price file is: empty, an HTML page, a bad gzip or ZIP, or XML
that does not parse. Each field is the element's text with the whitespace around it stripped, and "" when the element
is empty.

What is dropped as read, and why: `keep` is asked once of each promotion's fields, when its `<Groups>` starts, so a
promotion's fields are its children before `<Groups>` and a field after it is refused; with `known`, they are checked
(P10, below) before `keep` reads them, so a missing field is a refusal, never a KeyError. A promotion not kept has its
items counted and never built into links. Coupons are the reason: in one Shufersal store's file of 2026-10-31 (the
design's research sample, UNVERIFIED there) 21,244 links, about three quarters of them two meal-card vouchers'.
A promotion kept is yielded whole when its `</Promotion>` ends: its fields, every group's fields in file order (a group
with no items included, since minimum spend can sit on a second group that has none, docs/shopper-site.md P3 and P5)
and every link. A group's links are built when the group ends, so a group's fields after its items are taken. Every
element is cleared and taken off its parent once read, so a file is held as its bytes, the elements open or just
parsed and one kept promotion, never as a whole tree.

P10, the field half: with `known`, each element's set of child tags must equal its level's (the root, a promotion, a
group, an item), a dropped promotion's elements included, and a set that differs stops the read naming the file, the
level and the tags added and missing. An element inside a field is refused too, since it would read as an empty field.
Every tag seen at each level is kept in the tally for the survey. The codes inside the fields (`RewardType`, the
target, the gift code) are P10's other half, left to the step that classifies promotions.
"""
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from basket.pricefile import bodies, parse_events


@dataclass(frozen=True)
class FieldSets:
    """Each level's child tags, as a chain's files carry them (P10)."""
    root: frozenset[str]        # <Root>'s child tags (ChainID, SubChainID, StoreID, BikoretNo, Promotions, ...)
    promotion: frozenset[str]   # a <Promotion>'s child tags, Groups included
    group: frozenset[str]       # a <Group>'s child tags, PromotionItems included
    item: frozenset[str]        # a <PromotionItem>'s child tags


@dataclass(frozen=True)
class Link:
    """One item of one group of one promotion; texts stripped, "" when empty."""
    promotion: Mapping[str, str]    # the promotion's fields, Groups left out
    group: Mapping[str, str]        # the group's fields, PromotionItems left out
    item: Mapping[str, str]


@dataclass(frozen=True)
class PromotionRead:
    """One kept promotion, yielded when its `</Promotion>` ends."""
    fields: Mapping[str, str]                   # the promotion's fields, Groups left out
    groups: tuple[Mapping[str, str], ...]       # every group's fields in file order, item-less groups included
    links: tuple[Link, ...]                     # every item of every group, in file order


@dataclass
class Tally:
    """What reads counted, over every file they were given: every promotion asked of `keep`, those not kept, the links
    of those kept and the items of those not kept, and each level's tags."""
    promotions: int = 0
    links: int = 0
    dropped_promotions: int = 0
    dropped_links: int = 0
    seen: dict[str, set[str]] = field(default_factory=dict)   # level -> every tag seen, for the survey


class PromotionFormatChanged(Exception):
    """P10: a field or code the chain's files are not known to carry."""


# What an element is, told by what its parent is and, under the root, a promotion and a group, by its own tag.
_ROOT, _PROMOTIONS, _PROMOTION, _GROUPS, _GROUP, _ITEMS, _ITEM = range(7)
_ROOT_FIELD, _PROMOTION_FIELD, _GROUP_FIELD, _ITEM_FIELD = range(7, 11)


def read_promotions(name: str, data: bytes, keep: Callable[[Mapping[str, str]], bool], tally: Tally,
                    known: FieldSets | None = None) -> Iterator[PromotionRead]:
    """Each promotion in `data` that `keep` keeps, in file order, counted in `tally`; `name` goes in a refusal's
    message. With `known`, every element's tags are checked against their level's (P10)."""
    for body in bodies(name, data):
        yield from _read(name, body, keep, tally, known)


def _read(name: str, body: bytes, keep: Callable[[Mapping[str, str]], bool], tally: Tally,
          known: FieldSets | None) -> Iterator[PromotionRead]:
    """The promotions kept in one XML body."""
    roles: list[int] = []               # what each open element is, the root's first
    open_elements: list[ET.Element] = []
    root_tags: set[str] = set()
    for event, element in parse_events(name, body, ("start", "end")):
        tag = element.tag
        if event == "start":
            parent = roles[-1] if roles else None
            if parent is None:
                role = _ROOT
            elif parent == _ROOT:
                root_tags.add(tag)
                role = _PROMOTIONS if tag == "Promotions" else _ROOT_FIELD
            elif parent == _PROMOTIONS:
                role = _PROMOTION
                promotion: dict[str, str] = {}
                fields = MappingProxyType(promotion)
                promotion_tags: set[str] = set()
                kept: bool | None = None  # not asked yet
                groups: list[Mapping[str, str]] = []
                links: list[Link] = []
            elif parent == _PROMOTION:
                if kept is not None:
                    raise PromotionFormatChanged(f"{name}: {tag} after Groups")
                promotion_tags.add(tag)
                if tag == "Groups":
                    role = _GROUPS
                    kept = _ask(name, keep, fields, promotion_tags, known, tally)  # final tags: none after Groups
                else:
                    role = _PROMOTION_FIELD
            elif parent == _GROUPS:
                role = _GROUP
                group: dict[str, str] = {}
                group_tags: set[str] = set()
                items: list[Mapping[str, str]] = []
            elif parent == _GROUP:
                group_tags.add(tag)
                role = _ITEMS if tag == "PromotionItems" else _GROUP_FIELD
            elif parent == _ITEMS:
                role = _ITEM
                item = {} if kept else None  # a dropped promotion's items are never built
                item_tags: set[str] = set()
            elif parent == _ITEM:
                item_tags.add(tag)
                role = _ITEM_FIELD
            else:  # the parent is a field
                raise PromotionFormatChanged(f"{name}: {tag} inside {open_elements[-1].tag}")
            roles.append(role)
            open_elements.append(element)
            continue
        role = roles.pop()
        open_elements.pop()
        if role == _ITEM_FIELD:
            if item is not None:
                item[tag] = _text(element)
        elif role == _ITEM:
            _check(name, "item", item_tags, known, tally)
            if item is None:
                tally.dropped_links += 1
            else:
                tally.links += 1
                items.append(MappingProxyType(item))
        elif role == _GROUP_FIELD:
            if kept:
                group[tag] = _text(element)
        elif role == _GROUP:
            _check(name, "group", group_tags, known, tally)
            if kept:
                view = MappingProxyType(group)
                groups.append(view)
                links.extend(Link(fields, view, one) for one in items)
        elif role == _PROMOTION_FIELD:
            promotion[tag] = _text(element)
        elif role == _PROMOTION:
            if kept is None:  # no Groups: asked at its end, so every promotion is asked once
                kept = _ask(name, keep, fields, promotion_tags, known, tally)
            if kept:
                yield PromotionRead(fields, tuple(groups), tuple(links))
        elif role == _ROOT:
            _check(name, "root", root_tags, known, tally)
        element.clear()  # read: its text and children go, and so does its place in its parent
        if open_elements:
            open_elements[-1].remove(element)


def _ask(name: str, keep: Callable[[Mapping[str, str]], bool], fields: Mapping[str, str], tags: set[str],
         known: FieldSets | None, tally: Tally) -> bool:
    """Whether to keep the promotion of `fields`, counted; its `tags` are checked first, so `keep` never reads a field
    the promotion lacks."""
    _check(name, "promotion", tags, known, tally)
    tally.promotions += 1
    kept = bool(keep(fields))
    if not kept:
        tally.dropped_promotions += 1
    return kept


def _check(name: str, level: str, tags: set[str], known: FieldSets | None, tally: Tally) -> None:
    """Adds `tags` to the level's seen; with `known`, refuses a set of tags that is not the level's."""
    tally.seen.setdefault(level, set()).update(tags)
    if known is not None:
        expected = getattr(known, level)
        if tags != expected:
            raise PromotionFormatChanged(f"{name}: {level} fields changed: added {sorted(tags - expected)}, "
                                         f"missing {sorted(expected - tags)}")


def _text(element: ET.Element) -> str:
    """The element's text, stripped; "" when it has none."""
    return (element.text or "").strip()

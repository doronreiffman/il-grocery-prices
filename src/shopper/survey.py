"""The promotion survey: what one chain's promotion files of one day hold, measured so the shopper site's constants come
from the files and not from a guess (docs/shopper-site.md, P3, P4, P5 and P10; the plan's question B).

Which files. The chain's included stores (B2: its day's store list, `basket.stores.included`) are read, each by its
latest `PromoFull` file of the day (`basket.extract.day_files`, as B1 takes price files); a store's earlier files are
passed over, and the files of stores not included are passed over unread, both listed. The counted stores are P2's:
the included stores with a price file that counts that day (`basket.rules.stores_with_file_keys` over the day's prices
table), so the prices table must be there. Every promotion is read, coupons included (`shopper.promofile`, keeping all).

What is measured, over every file read (each store's copy of a promotion counts):
- each level's field set per file (the root, a promotion, a group, an item: the tags a file's elements carry, all
  together) and how many files carry each; and each element's own tag set, counted, with the level's tags it lacks;
- the values of `ClubID`, `IsGiftItem`, `AdditionalIsCoupon` (a promotion's), `DiscountType` (a group's), `RewardType`
  and `bIsWeighted` (an item's), each as [elements, distinct promotion ids]; `MinPurchaseAmount` by the group's
  position in its promotion (1 for the first), with how many of those groups have no items; the groups a promotion has;
- how often a set `IsGiftItem` equals the link's `MinQty`, as numbers when both read as one;
- per `RewardType`, the links that carry a `DiscountedPrice` and those that carry a `DiscountRate` (P3's "no price
  effect" is a `RewardType` 0 link with neither);
- up to five distinct `PromotionDescription`s per value of each of those six fields, in the order first seen, for the
  eye: `survey` returns them, and the command prints them only with `--samples`, to be read at the terminal (never
  redirected, piped or saved to any file, and never quoted beyond a word or two);
- the distinct texts, one per (id, description, start, end) as the reader would take them;
- the promotions listed before their start (the start's date after the day; dates are compared by their date part
  only, as P3 does), by how many days ahead, those ended before the day, and the promotions whose start or end does
  not read as a date;
- the share of promotions carried by at least half the stores (P3's "chain-wide": a store carries a promotion when its
  file holds that id), over the counted stores, over the included stores beside it, over the counted stores for the
  promotions none of whose copies is a coupon, and per sub-chain of the store list; and, in the unit the site uses, the
  item codes a promotion that is no coupon links at any counted store, and those of them on a link (promotion id, group
  id, item code, as the promotions table keys its rows) carried by at least half the counted stores, for the chain and
  per sub-chain;
- the links per store, and the coupons over BIG_COUPON items in a store's file (the vouchers);
- the link variants: per (promotion id, group id, item code), whether the stores' copies differ in any field of the
  promotion, the group or the item, and which fields differ, each counted once per link;
- on percent-off links (`RewardType` 2), whether `DiscountedPrice` is within ₪0.01 of the day's median price (B5,
  `basket.rules.chain_prices`) × (1 − `DiscountRate`/100), rounded half up to agorot (the plan's question C), else
  whether it reads as the discount itself (median × rate/100), and beside it the same test against the store's own
  price that day;
- the seconds the survey took and the process's peak memory (`resource.getrusage`).

    PYTHONPATH=src python -m shopper.survey --data data --day 2026-11-07 [--chain shufersal] [--samples]
"""
import argparse
import json
import resource
import sys
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import duckdb

from basket.barcode import normalize
from basket.chains import EXCLUDED, SLUGS
from basket.extract import DayFile, day_files
from basket.rules import apply_filters, chain_prices, open_day, stores_with_file_keys
from basket.stores import chain_stores, included
from shopper.promofile import PromotionRead, Tally, read_promotions

KIND = "PromoFull"
LEVELS = ("root", "promotion", "group", "item")
CODE_FIELDS = {"ClubID": "promotion", "IsGiftItem": "promotion", "AdditionalIsCoupon": "promotion",
               "DiscountType": "group", "RewardType": "item", "bIsWeighted": "item"}
SAMPLES = 5            # descriptions shown per (field, value)
BIG_COUPON = 1000      # a coupon over this many links in one file is listed
TOP_AMOUNTS = 10       # MinPurchaseAmount values shown per group position
PERCENT_OFF = "2"
CENT = Decimal("0.01")
OUTCOMES = ("no_rate", "no_discounted_price", "no_listed_price", "agrees", "reads_as_the_discount", "disagrees")


def _keep_all(promotion: Mapping[str, str]) -> bool:
    return True


def _number(text: str) -> Decimal | None:
    """The text as a finite decimal, or None."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _same_amount(a: str, b: str) -> bool:
    """Whether two fields hold the same number ("2" and "2.00"), or the same text when either is no number."""
    x, y = _number(a), _number(b)
    return x == y if x is not None and y is not None else a == b


def _date(text: str) -> date | None:
    """The date part of a promotion's date and time ("2026-11-01T00:00:00.000"), or None."""
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def carried_by_half(carriers: Mapping[str, set[str]], stores: set[str]) -> dict[str, int]:
    """Over `stores`: the promotions any of them carries, and those carried by at least half of them (P3)."""
    held = [len(by & stores) for by in carriers.values()]
    held = [count for count in held if count]
    return {"stores": len(stores), "promotions": len(held),
            "carried_by_half": sum(1 for count in held if count * 2 >= len(stores))}


def codes_chain_wide(links: Mapping[tuple[str, str, str], set[str]], stores: set[str]) -> dict[str, int]:
    """Over `stores`: the item codes any of them links (each link a (promotion id, group id, item code) and the stores
    carrying it), and those of them on a link carried by at least half of them."""
    linked, wide = set(), set()
    for (_, _, code), by in links.items():
        held = len(by & stores)
        if held:
            linked.add(code)
            if held * 2 >= len(stores):
                wide.add(code)
    return {"stores": len(stores), "codes": len(linked), "chain_wide": len(wide)}


@dataclass
class _Variant:
    """One link's copies: the first copy's fields, every distinct copy seen, the fields any copy differs in, and the
    stores carrying it."""
    first: tuple[Mapping[str, str], Mapping[str, str], Mapping[str, str]]
    seen: set[tuple[int, int, int]]
    stores: set[str]
    differ: set[str] = field(default_factory=set)


@dataclass
class _Measure:
    """What the survey adds up over a chain's files."""
    day: date
    files: list[str] = field(default_factory=list)
    promotions: int = 0
    links: int = 0
    field_sets: dict[str, Counter] = field(default_factory=lambda: {level: Counter() for level in LEVELS})
    element_sets: dict[str, Counter] = field(default_factory=lambda: {level: Counter() for level in LEVELS})
    values: dict[str, Counter] = field(default_factory=lambda: {name: Counter() for name in CODE_FIELDS})
    value_ids: dict[str, dict[str, set[str]]] = field(default_factory=lambda: {name: {} for name in CODE_FIELDS})
    samples: dict[str, dict[str, list[str]]] = field(default_factory=lambda: {name: {} for name in CODE_FIELDS})
    amounts: dict[int, Counter] = field(default_factory=dict)
    amount_counts: dict[int, Counter] = field(default_factory=dict)
    groups_per_promotion: Counter = field(default_factory=Counter)
    gift: dict[str, list[int]] = field(default_factory=dict)
    price_fields: dict[str, list[int]] = field(default_factory=dict)   # RewardType -> [links, price set, rate set]
    texts: set[tuple[str, str, str, str]] = field(default_factory=set)
    before_start: dict[tuple[str, date], int] = field(default_factory=dict)
    unreadable_dates: int = 0
    ended: set[tuple[str, str]] = field(default_factory=set)
    carriers: dict[str, set[str]] = field(default_factory=dict)
    coupon_ids: set[str] = field(default_factory=set)
    links_per_store: dict[str, int] = field(default_factory=dict)
    big_coupons: dict[str, list[int]] = field(default_factory=dict)   # id -> [most links in a file, stores]
    big_coupon_links: int = 0
    variants: dict[tuple[str, str, str], _Variant] = field(default_factory=dict)
    percent_off: list[tuple[str, str, str, str]] = field(default_factory=list)  # store, code, rate, discounted price

    def add_file(self, day_file: DayFile) -> None:
        tally = Tally()
        links = 0
        for record in read_promotions(day_file.name, day_file.path.read_bytes(), _keep_all, tally):
            links += len(record.links)
            self._add_promotion(day_file.store, record)
        self.files.append(day_file.name)
        self.promotions += tally.promotions
        self.links += tally.links
        self.links_per_store[day_file.store] = links
        for level, tags in tally.seen.items():
            self.field_sets[level][frozenset(tags)] += 1
        for level, sets in tally.sets.items():
            self.element_sets[level].update(sets)

    def _add_promotion(self, store: str, record: PromotionRead) -> None:
        fields = record.fields
        promotion_id = fields.get("PromotionID", "")
        description = fields.get("PromotionDescription", "")
        start_text, end_text = fields.get("PromotionStartDateTime", ""), fields.get("PromotionEndDateTime", "")
        self.texts.add((promotion_id, description, start_text, end_text))
        self.carriers.setdefault(promotion_id, set()).add(store)
        if fields.get("AdditionalIsCoupon") == "1":
            self.coupon_ids.add(promotion_id)
            if len(record.links) > BIG_COUPON:
                seen = self.big_coupons.setdefault(promotion_id, [0, 0])
                seen[0], seen[1] = max(seen[0], len(record.links)), seen[1] + 1
                self.big_coupon_links += len(record.links)
        start, end = _date(start_text), _date(end_text)
        self.unreadable_dates += start is None or end is None
        if start is not None and start > self.day:
            self.before_start[(promotion_id, start)] = (start - self.day).days
        if end is not None and end < self.day:
            self.ended.add((promotion_id, end_text))
        for name, level in CODE_FIELDS.items():
            if level == "promotion":
                self._value(name, fields.get(name), promotion_id, description)
        self.groups_per_promotion[len(record.groups)] += 1
        with_items = Counter(id(link.group) for link in record.links)
        for position, group in enumerate(record.groups, start=1):
            self._value("DiscountType", group.get("DiscountType"), promotion_id, description)
            self._amount(position, group.get("MinPurchaseAmount"), id(group) not in with_items)
        promotion_hash = hash(frozenset(fields.items()))
        group_hashes = {id(group): hash(frozenset(group.items())) for group in record.groups}
        for link in record.links:
            item = link.item
            for name in ("RewardType", "bIsWeighted"):
                self._value(name, item.get(name), promotion_id, description)
            gift = fields.get("IsGiftItem", "")
            if gift:
                counts = self.gift.setdefault(gift, [0, 0])
                counts[0] += 1
                counts[1] += _same_amount(gift, item.get("MinQty", ""))
            reward = item.get("RewardType")
            if reward is not None:
                carried = self.price_fields.setdefault(reward, [0, 0, 0])
                carried[0] += 1
                carried[1] += bool(item.get("DiscountedPrice"))
                carried[2] += bool(item.get("DiscountRate"))
            if reward == PERCENT_OFF:
                self.percent_off.append((store, item.get("ItemCode", ""), item.get("DiscountRate", ""),
                                         item.get("DiscountedPrice", "")))
            self._variant(store, (promotion_id, link.group.get("GroupID", ""), item.get("ItemCode", "")),
                          (promotion_hash, group_hashes[id(link.group)], hash(frozenset(item.items()))),
                          (fields, link.group, item))

    def _value(self, name: str, value: str | None, promotion_id: str, description: str) -> None:
        if value is None:
            return
        self.values[name][value] += 1
        self.value_ids[name].setdefault(value, set()).add(promotion_id)
        shown = self.samples[name].setdefault(value, [])
        if len(shown) < SAMPLES and description not in shown:
            shown.append(description)

    def _amount(self, position: int, value: str | None, without_items: bool) -> None:
        counts = self.amount_counts.setdefault(position, Counter())
        counts["groups"] += 1
        counts["without_items"] += without_items
        if value is None:
            return
        self.amounts.setdefault(position, Counter())[value] += 1
        amount = _number(value)
        if value == "":
            counts["empty"] += 1
        elif amount == 0:
            counts["zero"] += 1
        elif amount is not None and amount > 0:
            counts["above_zero"] += 1
            counts["above_zero_without_items"] += without_items

    def _variant(self, store: str, key: tuple[str, str, str], hashes: tuple[int, int, int],
                 copy: tuple[Mapping[str, str], Mapping[str, str], Mapping[str, str]]) -> None:
        known = self.variants.get(key)
        if known is None:
            self.variants[key] = _Variant(copy, {hashes}, {store})
            return
        known.stores.add(store)
        if hashes in known.seen:
            return
        known.seen.add(hashes)
        for level, first, this in zip(("promotion", "group", "item"), known.first, copy):
            known.differ.update(f"{level}.{name}" for name in first.keys() | this.keys()
                                if first.get(name) != this.get(name))

    def percent_off_outcomes(self, con: duckdb.DuckDBPyConnection) -> dict[str, int]:
        """Each percent-off link's outcome against the day's median price, and against the store's own price."""
        codes = sorted({code for _, code, _, _ in self.percent_off})
        medians = {code: price.median for (_, code), price in chain_prices(con, codes).items()}
        own = dict(((store, code), price) for store, code, price in con.execute(
            "SELECT store, code_norm, min(price) FROM rows WHERE code_norm IN (SELECT unnest(?::VARCHAR[])) "
            "GROUP BY store, code_norm", [[normalize(code) for code in codes]]).fetchall())
        found = Counter({outcome: 0 for outcome in OUTCOMES})
        found["with_store_price"] = found["agrees_with_store_price"] = 0
        for store, code, rate_text, price_text in self.percent_off:
            rate, price = _number(rate_text), _number(price_text)
            if rate is None:
                found["no_rate"] += 1
                continue
            if price is None:
                found["no_discounted_price"] += 1
                continue
            store_price = own.get((store, normalize(code)))
            if store_price is not None:
                found["with_store_price"] += 1
                found["agrees_with_store_price"] += abs(price - _cents(store_price * (100 - rate) / 100)) <= CENT
            median = medians.get(normalize(code))
            if median is None:
                found["no_listed_price"] += 1
            elif abs(price - _cents(median * (100 - rate) / 100)) <= CENT:
                found["agrees"] += 1
            elif abs(price - _cents(median * rate / 100)) <= CENT:
                found["reads_as_the_discount"] += 1
            else:
                found["disagrees"] += 1
        return {"links": len(self.percent_off), **found}


def _sets(counted: Counter, every: set[str] | None, unit: str) -> list[dict]:
    """Tag sets, the most common first; with `every`, each set's missing tags beside it."""
    shown = []
    for tags, count in sorted(counted.items(), key=lambda pair: (-pair[1], sorted(pair[0]))):
        entry = {"tags": sorted(tags)}
        if every is not None:
            entry["missing"] = sorted(every - tags)
        entry[unit] = count
        shown.append(entry)
    return shown


def survey(raw_dir: Path, tables_dir: Path, slug: str, day: date) -> dict:
    """The chain's promotion files of the day, measured (the module's docstring); nothing is written."""
    started = time.perf_counter()
    stores, listed_on = chain_stores(raw_dir, slug, day)
    included_ids = included(stores, slug)
    sub_chain_of = {store.id: store.sub_chain for store in stores if store.id in included_ids}
    files, passed_over = day_files(raw_dir, slug, day, kind=KIND)
    measure = _Measure(day)
    for day_file in files:
        if day_file.store in included_ids:
            measure.add_file(day_file)
    left_out = EXCLUDED[slug].sub_chains
    with open_day(tables_dir, day, [slug]) as con:
        apply_filters(con, {slug: included_ids}, {slug: left_out})
        counted = set(stores_with_file_keys(con, {slug: included_ids}, {slug: left_out})[slug])
        percent_off = measure.percent_off_outcomes(con)
    with_file = set(measure.links_per_store)
    not_coupons = {pid: by for pid, by in measure.carriers.items() if pid not in measure.coupon_ids}
    links_not_coupons = {key: v.stores for key, v in measure.variants.items() if key[0] not in measure.coupon_ids}
    by_sub_chain = {}
    for sub_chain in sorted({sub for sub in sub_chain_of.values()}, key=str):
        members = {store for store, sub in sub_chain_of.items() if sub == sub_chain}
        by_sub_chain[str(sub_chain)] = {"counted": carried_by_half(measure.carriers, members & counted),
                                        "included": carried_by_half(measure.carriers, members),
                                        "codes_counted_not_coupons": codes_chain_wide(links_not_coupons,
                                                                                      members & counted)}
    union = {level: set().union(*counted_sets) if (counted_sets := measure.element_sets[level]) else set()
             for level in LEVELS}
    return {
        "chain": slug, "day": day.isoformat(), "store_list_of": listed_on.isoformat(),
        "stores": {"included": len(included_ids), "counted": len(counted), "with_promotion_file": len(with_file),
                   "counted_with_promotion_file": len(with_file & counted)},
        "files": measure.files, "passed_over": passed_over,
        "not_included": [f.name for f in files if f.store not in included_ids],
        "promotions": measure.promotions, "links": measure.links,
        "field_sets": {level: _sets(measure.field_sets[level], None, "files") for level in LEVELS},
        "element_sets": {level: _sets(measure.element_sets[level], union[level], "elements") for level in LEVELS},
        "values": {name: {value: [count, len(measure.value_ids[name][value])]
                          for value, count in sorted(counts.items())} for name, counts in measure.values.items()},
        "min_purchase_amount": {str(position): {
            **{key: measure.amount_counts[position][key] for key in
               ("groups", "without_items", "empty", "zero", "above_zero", "above_zero_without_items")},
            "top": dict(sorted(measure.amounts.get(position, Counter()).most_common(TOP_AMOUNTS)))}
            for position in sorted(measure.amount_counts)},
        "groups_per_promotion": {str(n): count for n, count in sorted(measure.groups_per_promotion.items())},
        "gift_vs_min_qty": {"links": sum(links for links, _ in measure.gift.values()),
                            "equal": sum(equal for _, equal in measure.gift.values()),
                            "by_value": dict(sorted(measure.gift.items()))},
        "price_fields": {reward: {"links": links, "discounted_price": price, "discount_rate": rate}
                         for reward, (links, price, rate) in sorted(measure.price_fields.items())},
        "distinct_texts": len(measure.texts),
        "before_start": {"promotions": len(measure.before_start),
                         "days_ahead": {str(days): count for days, count in
                                        sorted(Counter(measure.before_start.values()).items())}},
        "ended": len(measure.ended),
        "unreadable_dates": measure.unreadable_dates,
        "chain_wide": {"counted": carried_by_half(measure.carriers, counted),
                       "included": carried_by_half(measure.carriers, set(included_ids)),
                       "counted_not_coupons": carried_by_half(not_coupons, counted),
                       "codes_counted_not_coupons": codes_chain_wide(links_not_coupons, counted),
                       "by_sub_chain": by_sub_chain},
        "links_per_store": dict(sorted(measure.links_per_store.items(), key=lambda pair: (int(pair[0]), pair[0]))),
        "big_coupons": {"promotions": [{"promotion": pid, "links": most, "stores": stores_with}
                                       for pid, (most, stores_with) in sorted(measure.big_coupons.items())],
                        "links": measure.big_coupon_links},
        "variants": {"links": len(measure.variants),
                     "with_more_than_one": sum(1 for v in measure.variants.values() if len(v.seen) > 1),
                     "fields": dict(sorted(Counter(name for v in measure.variants.values()
                                                   for name in v.differ).items()))},
        "percent_off": percent_off,
        "seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_bytes() / 1e6, 1),
        "samples": measure.samples,
    }


def _peak_bytes() -> int:
    """The process's peak resident memory: `ru_maxrss` is bytes on macOS and kilobytes on Linux."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Measure what each chain's promotion files of one day hold.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--chain", choices=SLUGS)
    parser.add_argument("--samples", action="store_true",
                        help="also print up to five promotion texts per code, for the eye at the terminal only")
    args = parser.parse_args(None if argv is None else list(argv))
    for slug in [args.chain] if args.chain else SLUGS:
        found = survey(args.data / "raw", args.data / "tables", slug, args.day)
        if not args.samples:
            del found["samples"]  # the archive's texts are printed only when asked
        print(json.dumps(found, ensure_ascii=False, indent=1, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

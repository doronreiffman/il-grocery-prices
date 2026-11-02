"""The words a visitor reads: the headline, the credit line, the labels beside the numbers, the notes and
the method page's text.

The sentences are fixed by the design (`docs/headline-basket.md`, "What a visitor sees" and "Words"). The
index page carries every phrase of ALWAYS; no page carries a phrase of NEVER, anywhere, not even in a
comment or an attribute. REVISED is said on a revised day's page and on no other (B12).

A headline names the lowest and the highest listed total and the gap, then the items, the day and
"before promotions". Without a headline the page says why: fewer than three chains in the ranking (B8),
or, with three or more, no basket item passed the day's checks (B6, B7, B9).

Money comes as the record's strings ("312.45") or as Decimal, which is rounded as the record rounds
(`basket.record.money`). A day is written "Monday 2 November 2026" in the headline and "2 November 2026"
elsewhere. A size is "1000 g/ml" (grams and millilitres are one kind, B7) or "12 units". Store and
sub-chain numbers are keys, as `basket.stores` reads them ("039" is store 39).
"""
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from basket.basket_file import Basket
from basket.chains import EXCLUDED
from basket.record import money
from basket.rules import Headline, LeftOut
from basket.stores import Store
from basket.units import Size, plain

TITLE = "One basket, five chains"
METHOD_TITLE = "How this is made"
CHAIN_NAMES = {"shufersal": "Shufersal", "ramilevy": "Rami Levy", "osherad": "Osher Ad", "carrefour": "Carrefour",
               "yochananof": "Yochananof"}
SUB_CHAIN_NAMES = {"shufersal": {"5": "Be"}}  # by key: a sub-chain left out whole is named by its name here
ALWAYS = ("listed price", "in the chain's price file", "before promotions", "lowest listed total for this basket",
          "median")
NEVER = ("cheapest chain", "cheaper than", "you'll pay", "you will pay", "saves you", "at the till", "real prices",
         "the chain charges")
REVISED = "Revised on"
MEDIAN_SENTENCE = ("A chain's price for an item is the median of its stores' listed prices, so no single store need "
                   "list exactly this total.")
PRICES_SENTENCE = ("Every price here is a listed price in the chain's price file, before promotions: for each item, "
                   "the chain's median across its stores. A lowest listed total for this basket says nothing about "
                   "any other basket.")
NO_CHAINS = "No comparison today: fewer than three chains published enough files."
NO_ITEMS = "No comparison today: no basket item passed the day's checks."
NOTHING_LEFT_OUT = "No basket item was left out today."
SIZE_KINDS = {"gml": "g/ml", "unit": "units"}
METHOD_LINK = "How this is made →"
BACK_LINK = "← " + TITLE
DIFFERENT_BASKET = "A different basket gives a different order."
METHOD_INTRO = ("One fixed basket of everyday products, each identified by its barcode so that the product is the "
                "same at every chain, priced at five chains from the price files they publish under the law. A "
                "chain's price for an item is the median of its stores' listed prices; its total is the sum over "
                "the items that count that day.")
LAW = ("The five chains publish these price files under section 30 of the Food and Pharma Competition Promotion "
       "Law, 2014. Every number here is derived from those files; no file and no store's price list is "
       "republished.")

# The rules (docs/headline-basket.md, "The number: rules"), shortened, in plain words.
RULES = (
    ("B1 Files.", "For each chain and day, the full price files (PriceFull) the chain published that day; a store "
                  "that published more than once counts with its latest file. The store is the number in the "
                  "file's name."),
    ("B2 Stores.", "Every store of the five chains counts, except those listed under \"Stores left out\": the "
                   "online stores named in the chains' store lists, and Shufersal's Be sub-chain, whose stores carry "
                   "12% of the barcodes the five chains share (measured on 2 November 2026)."),
    ("B3 Rows.", "One price per store and barcode; a barcode listed twice in one file counts once, with its "
                 "later row."),
    ("B4 Placeholders.", "A price of ₪0.01 or less is dropped as a placeholder, and counted."),
    ("B5 A chain's price.", "The median of the item's listed price across the chain's stores whose file lists it; "
                            "with an even count, the mean of the two middle prices. A store that lists the item "
                            "under two codes counts once, at the lower price. Rounded to agorot for display only."),
    ("B6 Coverage.", "An item counts on a day only if, at every chain in the ranking, at least half of the stores "
                     "with a file list it. Otherwise it is left out of every chain's total that day and named in "
                     "the notes."),
    ("B7 Size.", "Each chain's most common stated size for the item must be the basket's size: kilograms and "
                 "litres are converted, grams and millilitres compared alike, and a size not stated does not "
                 "count against the item. Otherwise the item is left out that day for every chain."),
    ("B8 A chain's day.", "A chain whose files come from fewer than half of its stores is shown as \"too few files "
                          "today\" and left out of the ranking and the totals; its prices are still shown, marked. "
                          "With fewer than three chains in the ranking, the page makes no comparison and says so."),
    ("B9 Totals.", "A chain's total is the sum of its prices for the items that count. Chains rank from the lowest "
                   "total; equal totals share a rank. The gap is (highest − lowest) ÷ lowest, as a whole percent."),
    ("B10 The record.", "Each build writes a record of the day with every number on the page and the counts behind "
                        "them. The day file on this site holds those numbers and counts, and names no store."),
    ("B11 As of.", "The page's date is the date in the files' names; \"collected by\" is the Israel time the day's "
                   "extraction started."),
    ("B12 Corrections.", "A published day changes only for a stated reason. The page then gives the date of the "
                         "change and its reason, and keeps the totals first published."),
)
NOT_CLAIMED = (
    "What a till charges: these are listed prices, not a promise of a price at checkout.",
    "Promotions: every price is before promotions; club, card and multi-buy deals are not counted.",
    f"Any other basket: the order holds for this basket only. {DIFFERENT_BASKET}",
    "Any single store: a chain's price is the median across its stores; the range beneath it gives the lowest "
    "and the highest store price without naming the store.",
    "Any other day: the numbers hold for the files of the date shown.",
)


def headline_lines(headline: Headline | None, item_count: int, day: date,
                   nothing_counted: bool = False) -> tuple[str, str]:
    """The headline's two lines; without a headline, why there is none (`nothing_counted`: no item passed the
    day's checks, else fewer than three chains in the ranking) and the items line."""
    items = (f"{item_count} everyday {'item' if item_count == 1 else 'items'}, listed shelf prices before promotions, "
             f"from the chains' price files of {day:%A %-d %B %Y}.")
    if headline is None:
        return NO_ITEMS if nothing_counted else NO_CHAINS, items
    return (f"Lowest listed total today: {CHAIN_NAMES[headline.lowest]}, ₪{money(headline.lowest_total)}.",
            f"Highest: {CHAIN_NAMES[headline.highest]}, ₪{money(headline.highest_total)}, "
            f"{headline.gap_percent}% more. {items}")


def credit(day: date, collected_by: str) -> str:
    """The credit line every page carries."""
    return ("Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish under "
            f"section 30 of the Food and Pharma Competition Promotion Law, 2014: the files of {day:%-d %B %Y}, "
            f"collected by {collected_by} Israel time. Listed prices, not a promise of what a till charges. "
            "Not shopping advice.")


def bar_label(with_file: int) -> str:
    return f"from {with_file} stores' files"


def range_note(low: str, high: str, listing: int, with_file: int) -> str:
    """The range across a chain's stores, as the files give it, and how many of its stores with a file list it."""
    return f"stores ₪{low} to ₪{high}, {listing} of {with_file} list it"


def too_few(with_file: int, included: int) -> str:
    return f"too few files today: {with_file} of {included} stores"


def out_note(slug: str, with_file: int, included: int) -> str:
    """The note on a chain out of the ranking (B8)."""
    return f"{CHAIN_NAMES[slug]}: {too_few(with_file, included)}. Its prices are shown, marked †, and count in no total."


def size_text(size: Size) -> str:
    return f"{plain(size.amount)} {SIZE_KINDS[size.kind]}"


def _seen_size(detail: str) -> str:
    """A size as a left-out item's details give it ("500 gml"), in the page's words ("500 g/ml")."""
    amount, kind = detail.rsplit(" ", 1)
    return f"{amount} {SIZE_KINDS.get(kind, kind)}"


def joined(parts: Sequence[str]) -> str:
    """"a", "a and b", "a, b and c"."""
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def left_out_line(item: LeftOut, basket: Basket) -> str:
    """Why a basket item is out of the day's totals: the chains below half coverage (B6), or the sizes seen (B7)."""
    product = next(each for each in basket.items if each.code == item.code)
    if item.reason == "coverage":
        chains = joined([f"{CHAIN_NAMES[slug]} ({share})" for slug, share in item.details.items()])
        return f"{product.name_en}: left out today; fewer than half the stores with a file list it at {chains}."
    if item.reason == "size":
        seen = joined([f"{CHAIN_NAMES[slug]} {_seen_size(size)}" for slug, size in item.details.items()])
        return (f"{product.name_en}: left out today; the size in the files differs from the basket's "
                f"{size_text(product.size)}: {seen}.")
    raise ValueError(f"no words for a reason {item.reason!r}")


def left_out_stores(slug: str, stores: Sequence[Store]) -> str:
    """The stores a chain leaves out (B2), "" for none: a sub-chain left out whole by its count and name, a store
    left out by its number by its number and name."""
    exclusion = EXCLUDED[slug]
    by_sub_chain: dict[str, int] = {}
    named = []
    for store in stores:
        if store.id in exclusion.stores:
            named.append(f"store {store.id} “{store.name}”")
        else:
            by_sub_chain[store.sub_chain] = by_sub_chain.get(store.sub_chain, 0) + 1
    names = SUB_CHAIN_NAMES.get(slug, {})
    groups = [f"{count} stores of the {names[key]} sub-chain" if key in names else f"{count} stores of sub-chain {key}"
              for key, count in sorted(by_sub_chain.items())]
    return joined(groups + named) if groups or named else ""


def excluded_line(slug: str, stores: Sequence[Store]) -> str:
    """A chain's stores left out, for the method page."""
    return f"{CHAIN_NAMES[slug]}: {left_out_stores(slug, stores) or 'none'}."


def basket_intro(basket: Basket) -> str:
    count = len(basket.items)
    return (f"Basket {basket.version}, chosen from the files of {basket.selection_day:%-d %B %Y}: "
            f"{count} {'product' if count == 1 else 'products'} all five chains listed, each identified by its "
            "barcode, with its names and size written by hand.")


def stores_line(slug: str, included: int, with_file: int, stores: Sequence[Store]) -> str:
    """Which stores a chain's number rests on, and the stores it leaves out by rule."""
    left_out = left_out_stores(slug, stores)
    rest = f"left out by rule: {left_out}" if left_out else "no store left out by rule"
    return f"{CHAIN_NAMES[slug]}: files from {with_file} of its {included} stores; {rest}."


def double_coded_line(counts: Mapping[str, int]) -> str | None:
    """How often a store listed an item under two codes, per chain in the order given (B5); None when never.
    The count is per item: a store that did so for two items counts twice."""
    times = [f"{count} {'time' if count == 1 else 'times'} at {CHAIN_NAMES[slug]}"
             for slug, count in counts.items() if count > 0]
    if not times:
        return None
    return ("An item a store listed under two codes counts once there, at the lower price; this happened "
            f"{joined(times)}.")


def reproduce(day: date, basket_version: str, code_sha: str) -> str:
    """How anyone with the chains' files gets the same numbers."""
    return (f"Take each chain's full price files of {day:%-d %B %Y}, the latest one per store, as the chains "
            f"published them; basket {basket_version}, listed above; and the rules above. The day file holds every "
            "number on the page and the counts behind them: the stores with a file, the rows read, the rows "
            "dropped as placeholders, and how many stores list each item. It names the code that built it by its "
            f"fingerprint, {code_sha}. The same files, basket and code give the same numbers.")


def revised_line(on: date, reason: str, first_totals: Mapping[str, str | None]) -> str:
    """The line on a revised day (B12): the date, the reason and the totals first published, lowest first."""
    ranked = sorted((Decimal(total), slug, total) for slug, total in first_totals.items() if total is not None)
    first = ", ".join(f"{CHAIN_NAMES[slug]} ₪{total}" for _, slug, total in ranked) or "no totals"
    return f"{REVISED} {on:%-d %B %Y}: {reason}. First published: {first}."

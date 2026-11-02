"""The store list: a chain's stores, and the ones the basket counts (rule B2).

Reading. A chain's `Stores` file is gzipped or plain XML, UTF-8 or UTF-16 with a byte order mark
(Shufersal's is gzipped UTF-8 with root <Chain>; Rami Levy's and Carrefour's are plain UTF-16 with
root <Root>). Each <Store> gives one Store: its id from `StoreID` or `StoreId`, its sub-chain from the
`SubChainID` or `SubChainId` of the <SubChain> holding it (None outside one), its `StoreName` and its
`StoreType`, each trimmed. Ids and sub-chains are keys: leading zeros stripped ("039" is "39"). A
<Store> with no id is skipped, as the collector's store list does.

Counting. The included stores are those of the list that the chain's entry in `basket.chains.EXCLUDED`
does not leave out, by id or by sub-chain; they are the M of rule B8. When the basket is priced, rows
are filtered again by the sub-chain in their file name, which wins over the list's.

Which list. A day's store list is the `Stores` file in that day's folder whose name says that day,
the greatest stored name if there are several; else that of the latest earlier day that has one. A
conflict copy is read by its published name.
"""
import gzip
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from basket.chains import EXCLUDED
from basket.extract import store_key
from collector.names import parse_file_name
from collector.payload import GZIP_MAGIC
from collector.store import published_name

STORE_ID_TAGS = ("StoreID", "StoreId")
SUB_CHAIN_TAGS = ("SubChainID", "SubChainId")


@dataclass(frozen=True)
class Store:
    """One store of a chain's list; `id` and `sub_chain` as keys, `name` and `store_type` as published."""
    id: str
    sub_chain: str | None
    name: str
    store_type: str


def read_stores(data: bytes) -> list[Store]:
    """The stores of a `Stores` file, in the file's order.

    Raises xml.etree.ElementTree.ParseError when the file is not XML.
    """
    xml = gzip.decompress(data) if data.startswith(GZIP_MAGIC) else data
    return list(_stores_in(ET.fromstring(xml), None))


def _stores_in(element: ET.Element, sub_chain: str | None) -> Iterator[Store]:
    for child in element:
        if child.tag == "SubChain":
            published = _text(child, SUB_CHAIN_TAGS)
            yield from _stores_in(child, store_key(published) if published else None)
        elif child.tag == "Store":
            store_id = _text(child, STORE_ID_TAGS)
            if store_id:
                yield Store(store_key(store_id), sub_chain, _text(child, ("StoreName",)),
                            _text(child, ("StoreType",)))
        else:
            yield from _stores_in(child, sub_chain)


def _text(element: ET.Element, tags: tuple[str, ...]) -> str:
    """The trimmed text of the first child named one of `tags`; "" when there is none."""
    for tag in tags:
        child = element.find(tag)
        if child is not None:
            return (child.text or "").strip()
    return ""


def _left_out(store: Store, slug: str) -> bool:
    exclusion = EXCLUDED[slug]
    return store.id in exclusion.stores or store.sub_chain in exclusion.sub_chains


def included(stores: list[Store], slug: str) -> set[str]:
    """The ids of the stores the basket counts for the chain. KeyError for a chain not in EXCLUDED."""
    return {store.id for store in stores if not _left_out(store, slug)}


def excluded(stores: list[Store], slug: str) -> list[Store]:
    """The stores the chain's exclusion leaves out, in the list's order."""
    return [store for store in stores if _left_out(store, slug)]


def day_store_list(raw_dir: Path, slug: str, day: date) -> tuple[bytes, date] | None:
    """The bytes of the day's store list and the day it is from; None when neither that day nor an earlier one has one."""
    chain_dir = raw_dir / f"chain={slug}"
    days = sorted((date.fromisoformat(folder.name.removeprefix("date=")) for folder in chain_dir.glob("date=*")),
                  reverse=True)
    for listed_day in (d for d in days if d <= day):
        folder = chain_dir / f"date={listed_day.isoformat()}"
        names = [path.name for path in folder.iterdir() if _is_store_list(path.name, listed_day)]
        if names:
            return (folder / max(names)).read_bytes(), listed_day
    return None


def _is_store_list(name: str, day: date) -> bool:
    parsed = parse_file_name(published_name(name))
    return parsed is not None and parsed.kind == "Stores" and parsed.day == day

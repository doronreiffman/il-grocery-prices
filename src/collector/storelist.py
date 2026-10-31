"""The store list: the store ids in a chain's Stores file, as published.

Shufersal's file is gzipped UTF-8 with root <Chain> and unpadded ids ("93"); Rami Levy's and
Carrefour's are plain UTF-16 LE XML with root <Root> and padded ids ("001"). Ids come back as
strings, as published; file names pad them, so compare store numbers as numbers.
"""
import gzip
import xml.etree.ElementTree as ET

from collector.payload import GZIP_MAGIC


def store_ids(data: bytes) -> set[str]:
    """The StoreID values in a Stores file, gzipped or plain (expat reads a UTF-8 or UTF-16 BOM).

    Raises xml.etree.ElementTree.ParseError when the file is not XML.
    """
    xml = gzip.decompress(data) if data.startswith(GZIP_MAGIC) else data
    ids = {(el.text or "").strip() for el in ET.fromstring(xml).iter("StoreID")}
    ids.discard("")
    return ids

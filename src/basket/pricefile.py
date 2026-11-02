"""Price files: the items one full price file lists, read alike from both layouts it comes in.

A full price file holds `<Item>` records. Two layouts are read (docs/portals.md): the common one,
which names an item's name `ItemName` and its update time `PriceUpdateTime`, and Rami Levy store
039's, which names them `ItemNm` and `PriceUpdateDate`; the other fields share their names. A file
is a gzip (one body), a ZIP (every file in it, in archive order, folders skipped), or plain XML with
or without a UTF-8 BOM, told apart by their first bytes as the collector's payload check tells them.
Each body must start like XML and parse whole. Each field is the element's text with the whitespace
around it stripped, and "" when the element is missing or empty.

An empty file, an HTML page, a bad gzip or ZIP, or a body that does not start like XML or does not
parse is refused with BadPriceFile, its message starting with the file's name. Items are read one at
a time and each is cleared once its fields are taken, so a file of 15,000 items (12 MB) is held as
its bytes and the items read, never as a whole tree.
"""
import gzip
import io
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass

from collector.payload import GZIP_MAGIC, XML_STARTS, ZIP_MAGICS

NAME_TAGS = ("ItemName", "ItemNm")
UPDATED_TAGS = ("PriceUpdateTime", "PriceUpdateDate")


class BadPriceFile(Exception):
    """A file is not a readable price file: empty, HTML, a bad gzip or ZIP, or XML that does not parse."""


@dataclass(frozen=True)
class Item:
    """One `<Item>`: `ItemCode`, the name, `ItemPrice`, `Quantity`, `UnitQty`, `UnitOfMeasure`, the update time."""
    code: str
    name: str
    price: str
    quantity: str
    unit: str
    unit_of_measure: str
    updated: str


def read_items(name: str, data: bytes) -> list[Item]:
    """The items in `data`, in file order; `name` goes in a refusal's message."""
    if data.startswith(ZIP_MAGICS):
        bodies = _zip_bodies(name, data)
    elif data.startswith(GZIP_MAGIC):
        try:
            bodies = [gzip.decompress(data)]
        except (EOFError, OSError, zlib.error) as exc:  # cut short; bad CRC, length or header; bad data
            raise BadPriceFile(f"{name}: the gzip is cut short or corrupt ({exc})") from exc
    else:
        bodies = [data]
    return [item for body in bodies for item in _parse(name, body)]


def _zip_bodies(name: str, data: bytes) -> list[bytes]:
    """Every file in the ZIP, in archive order; directory entries hold no file and are skipped."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            return [archive.read(member) for member in members]
    except Exception as exc:  # untrusted bytes: zipfile, zlib, bz2 and lzma fail in more ways than a list holds
        raise BadPriceFile(f"{name}: the zip is cut short or corrupt ({type(exc).__name__}: {exc})") from exc


def _parse(name: str, body: bytes) -> list[Item]:
    """The `<Item>`s in one XML body, each cleared once read."""
    if not body.startswith(XML_STARTS):
        raise BadPriceFile(f"{name}: not XML (it starts {body[:8]!r})")  # empty, HTML or unknown
    items = []
    try:
        for _, element in ET.iterparse(io.BytesIO(body), events=("end",)):
            if element.tag == "Item":
                items.append(Item(
                    code=_text(element, "ItemCode"),
                    name=_text(element, *NAME_TAGS),
                    price=_text(element, "ItemPrice"),
                    quantity=_text(element, "Quantity"),
                    unit=_text(element, "UnitQty"),
                    unit_of_measure=_text(element, "UnitOfMeasure"),
                    updated=_text(element, *UPDATED_TAGS),
                ))
                element.clear()
    except ET.ParseError as exc:
        raise BadPriceFile(f"{name}: the XML does not parse ({exc})") from exc
    return items


def _text(item: ET.Element, *tags: str) -> str:
    """The stripped text of the first of `tags` the item has; "" when it has none of them."""
    for tag in tags:
        element = item.find(tag)
        if element is not None:
            return (element.text or "").strip()
    return ""

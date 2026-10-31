"""Payload checks: a downloaded body must start like a price file, not an error or block page.

The starts seen (docs/portals.md): gzip; `<?xml`; a UTF-8 BOM before `<?xml` or `<Root>`; a UTF-16
LE BOM before `<` (Rami Levy's and Carrefour's Stores files, which carry no XML declaration). A gzip
is unzipped whole, so a cut-short or corrupt one is refused (its length and CRC are checked), and
what it holds must start like XML. Anything else is refused: empty, HTML, or unknown.
"""
import gzip
import zlib

GZIP_MAGIC = b"\x1f\x8b"
UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"
XML_STARTS = (b"<?xml", UTF8_BOM + b"<?xml", UTF8_BOM + b"<Root>", UTF16LE_BOM + b"<\x00")
HTML_STARTS = (b"<!doctype html", b"<html")
HEAD_BYTES = 1024  # enough to see past leading whitespace to the first tag


class BadPayload(Exception):
    """A downloaded body is not a price file: empty, HTML, or neither gzip nor XML."""


def _gunzip_head(data: bytes) -> bytes | None:
    """The first bytes inside a gzip; None when it does not unzip."""
    try:
        return zlib.decompressobj(wbits=31).decompress(data, HEAD_BYTES)
    except zlib.error:
        return None


def looks_like_html(data: bytes) -> bool:
    """True for an HTML page: plain, after a BOM or whitespace, in UTF-16, or inside a gzip."""
    head = data[:HEAD_BYTES]
    if head.startswith(GZIP_MAGIC):
        head = _gunzip_head(data) or b""
    if head.startswith(UTF16LE_BOM):
        head = head[2:].decode("utf-16-le", "replace").encode()
    return head.removeprefix(UTF8_BOM).lstrip().lower().startswith(HTML_STARTS)


def check_payload(name: str, data: bytes) -> None:
    """Raise BadPayload unless `data` starts like a price file; `name` goes in the message."""
    if not data:
        raise BadPayload(f"{name}: empty file")
    if looks_like_html(data):
        raise BadPayload(f"{name}: HTML where a file belongs")
    if data.startswith(GZIP_MAGIC):
        try:
            content = gzip.decompress(data)
        except (EOFError, OSError, zlib.error) as exc:  # cut short; bad CRC, length or header; bad data
            raise BadPayload(f"{name}: the gzip is cut short or corrupt ({exc})") from exc
        if not content.startswith(XML_STARTS):
            raise BadPayload(f"{name}: the gzip holds no XML (it starts {content[:8]!r})")
    elif not data.startswith(XML_STARTS):
        raise BadPayload(f"{name}: neither gzip nor XML (it starts {data[:8]!r})")

"""Payload checks: a downloaded body must start like a price file, not an error or block page.

The starts seen (docs/portals.md): gzip; `<?xml`; a UTF-8 BOM before `<?xml` or `<Root>`; a bare
`<Root>` (inside Rami Levy store 039's ZIPs, 2026-11-01); a UTF-16 LE BOM before `<` (Rami Levy's
and Carrefour's Stores files, which carry no XML declaration). A gzip is unzipped whole, so a cut-
short or corrupt one is refused (its length and CRC are checked), and what it holds must start like
XML. A ZIP (Rami Levy store 039's files, under .gz names, 2026-11-01) is read whole too, every entry
read through, and every file in it must start like XML. Anything else is refused: empty, HTML, or
unknown.
"""
import gzip
import io
import zipfile
import zlib

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06")  # a member's local header; an empty archive's end record
ZIP_HEAD = 16  # bytes of a member shown when it is not XML
SHOWN_MEMBERS = 3  # members a refusal names, at most
NAME_CHARS = 80  # of a member's name a refusal shows
ERROR_CHARS = 200  # of zipfile's error text a refusal shows
READ_CHUNK = 1 << 20  # bytes read at a time when a member is read through
UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"
XML_STARTS = (b"<?xml", UTF8_BOM + b"<?xml", UTF8_BOM + b"<Root>", b"<Root>", UTF16LE_BOM + b"<\x00")
HTML_STARTS = (b"<!doctype html", b"<html")
HEAD_BYTES = 1024  # enough to see past leading whitespace to the first tag


class BadPayload(Exception):
    """A downloaded body is not a price file: empty, HTML, a bad gzip or ZIP, or neither of those nor XML."""


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
    if data.startswith(ZIP_MAGICS):
        _check_zip(name, data)
    elif data.startswith(GZIP_MAGIC):
        try:
            content = gzip.decompress(data)
        except (EOFError, OSError, zlib.error) as exc:  # cut short; bad CRC, length or header; bad data
            raise BadPayload(f"{name}: the gzip is cut short or corrupt ({exc})") from exc
        if not content.startswith(XML_STARTS):
            raise BadPayload(f"{name}: the gzip holds no XML (it starts {content[:8]!r})")
    elif not data.startswith(XML_STARTS):
        raise BadPayload(f"{name}: neither gzip nor XML (it starts {data[:8]!r})")


def _check_zip(name: str, data: bytes) -> None:
    """Raise BadPayload unless `data` is a ZIP, as zipfile reads it, whose every file starts like XML.
    Every entry is read through to its end, by entry and not by name (a name can repeat, and only the
    last of a name is found by it), so each one's CRC is checked. Directory entries are taken to hold
    no data and are not checked for XML. zipfile tolerates bytes after the archive's end record (it
    searches the last 64 KB for it); the body is stored byte for byte either way. Names and zipfile's
    error text are cut short and written as ascii() writes them, so a refusal stays short and adds no
    line to the log or the email."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                with archive.open(member) as body:
                    while body.read(READ_CHUNK):
                        pass
            members = [member for member in archive.infolist() if not member.is_dir()]
            heads = [(member.filename, archive.open(member).read(ZIP_HEAD)) for member in members]
    except Exception as exc:  # untrusted bytes: zipfile, zlib, bz2 and lzma fail in more ways than a list holds
        raise BadPayload(f"{name}: the zip is cut short or corrupt ({type(exc).__name__}: {_cut(str(exc), ERROR_CHARS)})") from exc
    if not members:
        raise BadPayload(f"{name}: the zip holds no file")
    not_xml = [(member, head) for member, head in heads if not head.startswith(XML_STARTS)]
    if not_xml:
        count = "a file that is not XML" if len(not_xml) == 1 else f"{len(not_xml)} files that are not XML"
        shown = ", ".join(f"{_quoted(member)} starts {head!r}" for member, head in not_xml[:SHOWN_MEMBERS])
        more = f" and {len(not_xml) - SHOWN_MEMBERS} more" if len(not_xml) > SHOWN_MEMBERS else ""
        raise BadPayload(f"{name}: the zip holds {count}: {shown}{more}")


def _quoted(member: str) -> str:
    """A member's name for a refusal: at most NAME_CHARS of it, quoted and escaped as ascii() does."""
    return ascii(member[:NAME_CHARS]) + ("..." if len(member) > NAME_CHARS else "")


def _cut(text: str, limit: int) -> str:
    """At most `limit` characters of `text`, escaped as ascii() does, without its quotes."""
    return ascii(text[:limit])[1:-1] + ("..." if len(text) > limit else "")

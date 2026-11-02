"""Payload checks: a downloaded body must start like a price file, never like an HTML page."""
import gzip
import io
import re
import struct
import warnings
import zipfile
from pathlib import Path

import pytest

from collector.payload import BadPayload, check_payload, looks_like_html

FIXTURES = Path(__file__).parent / "fixtures"
NAME = "PriceFull7290027600007-001-030-20261031-030000.gz"
UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"
HTML_PAGE = b"<!DOCTYPE html><html><body>Please verify you are a human</body></html>"


def _fixture_files():
    files = sorted(p for p in FIXTURES.glob("*/*") if p.suffix in (".gz", ".xml"))
    assert len(files) == 11  # one of them a ZIP under a .gz name (Rami Levy store 039); one the basket's own
    return files


def test_every_fixture_file_passes():
    for path in _fixture_files():
        data = path.read_bytes()
        check_payload(path.name, data)
        assert not looks_like_html(data), path.name


@pytest.mark.parametrize("data", [
    pytest.param(gzip.compress(UTF8_BOM + b"<Root>\r\n  <ChainID>7290027600007</ChainID>\r\n</Root>"),
                 id="gzip, BOM, <Root> (price files)"),
    pytest.param(gzip.compress(UTF8_BOM + b'<?xml version="1.0" encoding="UTF-8"?><Chain/>'),
                 id="gzip, BOM, <?xml (Shufersal Stores)"),
    pytest.param(b'<?xml version="1.0" encoding="UTF-8"?><Root/>', id="<?xml"),
    pytest.param(UTF8_BOM + b'<?xml version="1.0" encoding="UTF-8"?><Root/>', id="BOM, <?xml"),
    pytest.param(UTF8_BOM + b"<Root>\r\n</Root>", id="BOM, <Root>"),
    pytest.param(b"<Root>\r\n  <ChainId>7290058140886</ChainId>\r\n</Root>", id="a bare <Root> (Rami Levy store 039)"),
    pytest.param(gzip.compress(b"<Root>\r\n</Root>"), id="gzip, a bare <Root>"),
    pytest.param(UTF16LE_BOM + "<Root><ChainID>7290058140886</ChainID></Root>".encode("utf-16-le"),
                 id="UTF-16 LE (NCR and Carrefour Stores)"),
])
def test_accepted_starts(data):
    check_payload(NAME, data)
    assert not looks_like_html(data)


def test_empty_file_refused():
    with pytest.raises(BadPayload, match="empty"):
        check_payload(NAME, b"")


@pytest.mark.parametrize("data", [
    pytest.param(b"<!DOCTYPE html>", id="doctype"),
    pytest.param(b"  <html", id="spaces, <html"),
    pytest.param(b"\r\n\t<HTML lang='he'><head>", id="line ends, upper case"),
    pytest.param(UTF8_BOM + b"<!doctype html><html>", id="BOM, doctype"),
    pytest.param(UTF16LE_BOM + "<html><body>blocked</body></html>".encode("utf-16-le"), id="UTF-16 LE"),
    pytest.param(gzip.compress(HTML_PAGE), id="inside a gzip"),
    pytest.param(gzip.compress(b"\n  " + HTML_PAGE), id="inside a gzip, after whitespace"),
])
def test_html_refused_as_html(data):
    assert looks_like_html(data)
    with pytest.raises(BadPayload, match="HTML where a file belongs"):
        check_payload(NAME, data)


@pytest.mark.parametrize("data, reason", [
    pytest.param(b"hello", "neither gzip nor XML", id="text"),
    pytest.param(b'{"error": "not found"}', "neither gzip nor XML", id="JSON"),
    pytest.param(b"PK\x03\x04\x14\x00", "the zip is cut short or corrupt", id="a zip header alone"),
    pytest.param(gzip.compress(b"hello"), "the gzip holds no XML", id="gzip of text"),
    pytest.param(b"<root>\r\n</root>", "neither gzip nor XML", id="a bare <root> in lower case"),
    pytest.param(gzip.compress(b""), "the gzip holds no XML", id="gzip of nothing"),
    pytest.param(gzip.compress(gzip.compress(HTML_PAGE)), "the gzip holds no XML", id="gzip of a gzip"),
    pytest.param(b"\x1f\x8b\x08junkjunkjunk", "cut short or corrupt", id="corrupt gzip header"),
    pytest.param(gzip.compress(HTML_PAGE, mtime=0)[:10] + b"\xff" * 16, "cut short or corrupt", id="corrupt gzip data"),
    pytest.param(gzip.compress(UTF8_BOM + b"<Root></Root>") + b"garbage", "cut short or corrupt",
                 id="bytes after the gzip"),
])
def test_anything_else_refused(data, reason):
    assert not looks_like_html(data)
    with pytest.raises(BadPayload, match=reason):
        check_payload(NAME, data)


def _gzip_fixtures():
    files = [p for p in _fixture_files() if p.read_bytes()[:2] == b"\x1f\x8b"]  # not store 039's ZIP
    assert len(files) == 8
    return files


@pytest.mark.parametrize("cut", [1, 8, 20])  # into the length, past the whole trailer, into the data
def test_cut_short_gzip_refused(cut):
    for path in _gzip_fixtures():
        data = path.read_bytes()[:-cut]
        assert not looks_like_html(data)
        with pytest.raises(BadPayload, match="cut short or corrupt"):
            check_payload(path.name, data)


@pytest.mark.parametrize("offset", [-8, -1], ids=["CRC", "length"])  # the trailer: CRC-32, then length
def test_gzip_with_a_wrong_trailer_refused(offset):
    for path in _gzip_fixtures():
        data = bytearray(path.read_bytes())
        data[offset] ^= 0x01
        with pytest.raises(BadPayload, match="cut short or corrupt"):
            check_payload(path.name, bytes(data))


# Rami Levy store 039's files are ZIP archives under .gz names: the first deployed run refused four
# of them, "neither gzip nor XML (it starts b'PK\\x03\\x04...')" (2026-11-01).
PRICE_XML = UTF8_BOM + b'<?xml version="1.0" encoding="utf-8"?><root><ChainId>7290058140886</ChainId></root>'


def a_zip(*members, compression=zipfile.ZIP_DEFLATED):
    """A ZIP holding (name, bytes) members, as Python's zipfile writes one."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive, warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Duplicate name", UserWarning)  # one test repeats a name on purpose
        for name, data in members:
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize("data", [
    pytest.param(a_zip(("price.xml", PRICE_XML)), id="one XML member"),
    pytest.param(a_zip(("price.xml", PRICE_XML), compression=zipfile.ZIP_STORED), id="stored, not deflated"),
    pytest.param(a_zip(("a.xml", PRICE_XML), ("b.xml", b'<?xml version="1.0"?><Root/>')), id="two XML members"),
    pytest.param(a_zip(("stores.xml", UTF16LE_BOM + "<Root/>".encode("utf-16-le"))), id="a UTF-16 member"),
    pytest.param(a_zip(("Price7290058140886-039-202611011002.xml", b"<Root>\r\n  <ChainId>7290058140886</ChainId>\r\n</Root>")),
                 id="a bare <Root> member, as store 039's"),
])
def test_a_zip_of_xml_is_accepted(data):
    check_payload(NAME, data)
    assert not looks_like_html(data)


def _corrupt_member(data: bytes) -> bytes:
    """The ZIP with one byte of its first member's compressed data flipped: its CRC no longer holds."""
    corrupt = bytearray(data)
    corrupt[30 + len("price.xml") + 4] ^= 0xFF  # past the 30-byte local header and the name
    return bytes(corrupt)


def _central_directory_past_the_end(data: bytes) -> bytes:
    """The end record's central-directory offset moved past the file: zipfile raises ValueError."""
    patched = bytearray(data)
    end = patched.rfind(b"PK\x05\x06")
    patched[end + 16:end + 20] = struct.pack("<I", 10**6)
    return bytes(patched)


def _undecodable_utf8_name(data: bytes) -> bytes:
    """The central directory's UTF-8 flag set on a name that is not UTF-8: zipfile raises
    UnicodeDecodeError."""
    patched = bytearray(data)
    entry = patched.find(b"PK\x01\x02")
    flags = struct.unpack("<H", patched[entry + 8:entry + 10])[0] | 0x800
    patched[entry + 8:entry + 10] = struct.pack("<H", flags)
    patched[entry + 46:entry + 51] = b"\xff\xfe\xfd.x"
    return bytes(patched)


def _corrupt_far_in(data: bytes) -> bytes:
    """One byte flipped 5,000 bytes into the first member's data, past the 16 bytes a head read takes
    and past the 4 KB zipfile reads ahead: only reading the member through to its end finds it."""
    corrupt = bytearray(data)
    corrupt[30 + 9 + 5000] ^= 0xFF  # 9: the length of "price.xml"; "a.xml" is 5, still inside the data
    return bytes(corrupt)




def _marked_encrypted(data: bytes) -> bytes:
    """The central directory's first entry flagged encrypted: zipfile raises RuntimeError, quoting the
    member's name."""
    patched = bytearray(data)
    entry = patched.find(b"PK\x01\x02")
    flags = struct.unpack("<H", patched[entry + 8:entry + 10])[0] | 0x1
    patched[entry + 8:entry + 10] = struct.pack("<H", flags)
    return bytes(patched)


def _garbled_lzma(data: bytes) -> bytes:
    """Two bytes of an LZMA member's data flipped: lzma raises LZMAError."""
    patched = bytearray(data)
    patched[43] ^= 0xFF
    patched[50] ^= 0xFF
    return bytes(patched)


@pytest.mark.parametrize("data", [
    pytest.param(a_zip(*[("n" * 60_000 + str(i), b"hello") for i in range(3)]), id="names shown"),
    pytest.param(_marked_encrypted(a_zip(("n" * 60_000, PRICE_XML))), id="a name in zipfile's error text"),
])
def test_a_refusal_stays_short_whatever_the_names(data):
    with pytest.raises(BadPayload) as caught:
        check_payload(NAME, data)
    assert len(str(caught.value)) < 1_000


def test_a_folder_entry_in_a_zip_is_skipped():
    """A directory entry holds no data; the files beside it are what is checked."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.mkdir("prices")
        archive.writestr("prices/price.xml", PRICE_XML)
    check_payload(NAME, buffer.getvalue())


def test_a_zip_of_folders_alone_holds_no_file():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.mkdir("prices")
    with pytest.raises(BadPayload, match="the zip holds no file"):
        check_payload(NAME, buffer.getvalue())


@pytest.mark.parametrize("data, reason", [
    pytest.param(a_zip(), "the zip holds no file", id="an empty zip"),
    pytest.param(a_zip(("price.xml", b"")), "not XML: 'price.xml' starts b''", id="an empty file inside"),
    pytest.param(_central_directory_past_the_end(a_zip(("a.xml", PRICE_XML))), "the zip is cut short or corrupt (ValueError:",
                 id="a central directory past the end"),
    pytest.param(_undecodable_utf8_name(a_zip(("a.xml", PRICE_XML))), "the zip is cut short or corrupt (UnicodeDecodeError:",
                 id="a name that is not UTF-8"),
    pytest.param(_garbled_lzma(a_zip(("price.xml", PRICE_XML * 50), compression=zipfile.ZIP_LZMA)),
                 "the zip is cut short or corrupt (LZMAError:", id="garbled LZMA data"),
    pytest.param(_marked_encrypted(a_zip(("\u05de\u05d7\u05d9\u05e8.xml", PRICE_XML))),
                 "\\u05de\\u05d7\\u05d9\\u05e8.xml'",  # the name, escaped; zipfile's own wording around it varies by version
                 id="an encrypted member with a Hebrew name"),
    pytest.param(a_zip(("price.xml", PRICE_XML))[:-30], "the zip is cut short or corrupt", id="cut short"),
    pytest.param(b"PK\x03\x04" + b"\x00" * 40, "the zip is cut short or corrupt", id="a header and nothing"),
    pytest.param(_corrupt_member(a_zip(("price.xml", PRICE_XML * 20))), "the zip is cut short or corrupt", id="a corrupt member"),
    pytest.param(_corrupt_far_in(a_zip(("price.xml", PRICE_XML * 200), compression=zipfile.ZIP_STORED)),
                 "the zip is cut short or corrupt (BadZipFile: Bad CRC-32 for file 'price.xml')", id="a stored member corrupt past its head"),
    pytest.param(_corrupt_far_in(a_zip(("a.xml", PRICE_XML * 200), ("a.xml", PRICE_XML), compression=zipfile.ZIP_STORED)),
                 "the zip is cut short or corrupt (BadZipFile: Bad CRC-32 for file 'a.xml')", id="the first of two members of one name corrupt"),
    pytest.param(a_zip(("page.html", HTML_PAGE)), "the zip holds a file that is not XML: 'page.html' starts b'<!DOCTYPE html><'", id="HTML inside"),
    pytest.param(a_zip(("a.xml", PRICE_XML), ("b.txt", b"hello")), "not XML: 'b.txt' starts b'hello'", id="one member of two not XML"),
    # mtime=0: a gzip stamped with the clock prints in double quotes whenever a stamp byte is ' (CI, 2026-11-01)
    pytest.param(a_zip(("inner.gz", gzip.compress(PRICE_XML, mtime=0))), "not XML: 'inner.gz' starts b'\\x1f\\x8b", id="a gzip inside"),
    pytest.param(a_zip(("a\nERROR forged.txt", b"x")), "not XML: 'a\\nERROR forged.txt' starts b'x'", id="a line break in a member name"),
])
def test_a_zip_that_is_not_a_zip_of_xml_is_refused(data, reason):
    with pytest.raises(BadPayload) as caught:
        check_payload(NAME, data)
    assert str(caught.value).startswith(NAME + ": ")
    assert reason in str(caught.value)
    assert str(caught.value).isascii() and str(caught.value).isprintable()


def test_a_refused_zip_names_at_most_three_members():
    data = a_zip(*[(f"m{i}.txt", b"hello") for i in range(5)])
    with pytest.raises(BadPayload) as caught:
        check_payload(NAME, data)
    assert "'m0.txt' starts b'hello', 'm1.txt' starts b'hello', 'm2.txt' starts b'hello' and 2 more" in str(caught.value)


def test_refusal_names_the_file():
    with pytest.raises(BadPayload, match=re.escape(NAME)):
        check_payload(NAME, b"hello")


def test_looks_like_html_false_for_non_html():
    assert not looks_like_html(b"")
    assert not looks_like_html(b"<Root><Html>not a page</Html></Root>")
    assert not looks_like_html(b"\x1f\x8b")  # a gzip cut off after its magic

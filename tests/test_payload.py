"""Payload checks: a downloaded body must start like a price file, never like an HTML page."""
import gzip
import re
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
    assert len(files) == 9
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
    pytest.param(b"PK\x03\x04\x14\x00", "neither gzip nor XML", id="zip"),
    pytest.param(gzip.compress(b"hello"), "the gzip holds no XML", id="gzip of text"),
    pytest.param(gzip.compress(b""), "the gzip holds no XML", id="gzip of nothing"),
    pytest.param(gzip.compress(gzip.compress(HTML_PAGE)), "the gzip holds no XML", id="gzip of a gzip"),
    pytest.param(b"\x1f\x8b\x08junkjunkjunk", "does not unzip", id="corrupt gzip"),
])
def test_anything_else_refused(data, reason):
    assert not looks_like_html(data)
    with pytest.raises(BadPayload, match=reason):
        check_payload(NAME, data)


def test_refusal_names_the_file():
    with pytest.raises(BadPayload, match=re.escape(NAME)):
        check_payload(NAME, b"hello")


def test_looks_like_html_false_for_non_html():
    assert not looks_like_html(b"")
    assert not looks_like_html(b"<Root><Html>not a page</Html></Root>")
    assert not looks_like_html(b"\x1f\x8b")  # a gzip cut off after its magic

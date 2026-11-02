"""Price files: one full price file's items, from both layouts, gzipped, zipped or plain."""
import gzip
import io
import zipfile
from pathlib import Path

import pytest

from basket.pricefile import BadPriceFile, Item, read_items

FIXTURES = Path(__file__).parent / "fixtures"
NCR_722 = FIXTURES / "ncr" / "PriceFull7290058140886-001-722-20261101-001016.gz"
NCR_039 = FIXTURES / "ncr" / "pricefull7290058140886-039-202611010514.gz"
BASKET = FIXTURES / "basket" / "PriceFull7290000000001-001-001-20260101-000000.gz"
BOM_XML = b"\xef\xbb\xbf<Root><Items><Item><ItemCode>96385074</ItemCode></Item></Items></Root>"


def _xml_of_one_item(code: str) -> bytes:
    return f"<Root>\r\n  <Items>\r\n    <Item>\r\n      <ItemCode>{code}</ItemCode>\r\n    </Item>\r\n  </Items>\r\n</Root>\r\n".encode()


def test_reads_the_common_layout():
    items = read_items(NCR_722.name, NCR_722.read_bytes())
    assert len(items) == 3
    assert items[0] == Item("2000000000015", "מוצר לדוגמה 1", "10.90", "100.00", "גרם", "100 גרם", "2026-07-21T13:42:46.000")


def test_reads_store_039_zip():
    # Rami Levy store 039: a ZIP under a .gz name, a bare <Root>, ItemNm and PriceUpdateDate
    items = read_items(NCR_039.name, NCR_039.read_bytes())
    assert items[0] == Item("2000000000015", "פריט בדיקה 1", "450", "1", "00000", "0000000000", "2026-10-31 07:00:00")


def test_reads_plain_xml_with_a_utf8_bom():
    assert [item.code for item in read_items("plain.xml", BOM_XML)] == ["96385074"]


def test_reads_plain_xml_without_a_bom():
    assert [item.code for item in read_items("plain.xml", _xml_of_one_item("96385074"))] == ["96385074"]


def test_missing_fields_are_empty():
    [item] = read_items("plain.xml", BOM_XML)
    assert item == Item("96385074", "", "", "", "", "", "")


def test_text_is_stripped():
    data = ("<Root><Items><Item><ItemCode>\r\n  96385074 </ItemCode>"
            "<ItemName> מוצר\r\n</ItemName><ItemPrice>  </ItemPrice></Item></Items></Root>").encode()
    [item] = read_items("plain.xml", data)
    assert (item.code, item.name, item.price) == ("96385074", "מוצר", "")


def test_the_basket_fixture_keeps_commas_quotes_and_line_breaks():
    items = read_items(BASKET.name, BASKET.read_bytes())
    assert [(item.code, item.price, item.unit) for item in items] == [
        ("2000000000015", "5.00", "גרם"), ("2000000000015", "6.00", "גרם"), ("1501", "abc", "לא ידוע")]
    name = items[1].name
    assert "," in name and '"' in name and "\n" in name


def test_zip_reads_every_member():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("folder/", b"")  # a directory entry holds no file
        archive.writestr("first.xml", _xml_of_one_item("111"))
        archive.writestr("second.xml", _xml_of_one_item("222"))
    assert [item.code for item in read_items("two.gz", buffer.getvalue())] == ["111", "222"]


@pytest.mark.parametrize("data", [
    b"",
    b"<html>",
    b"<html><body></body></html>",  # well-formed: it parses, and is still not a price file
    gzip.compress(b"<html><body></body></html>", mtime=0),
    b"\x1f\x8b junk",
    gzip.compress(b"<Root><Items><Item>", mtime=0),  # starts like XML, cut short
    b"PK\x03\x04 junk",
], ids=["empty", "html", "well-formed html", "html in a gzip", "bad gzip", "cut-short xml", "bad zip"])
def test_refuses_empty_html_and_not_xml(data):
    with pytest.raises(BadPriceFile) as refused:
        read_items("PriceFull7290000000001-001-001-20260101-000000.gz", data)
    assert str(refused.value).startswith("PriceFull7290000000001-001-001-20260101-000000.gz: ")


def test_every_pricefull_fixture_reads():
    paths = sorted(p for p in FIXTURES.rglob("*") if p.is_file() and p.name.lower().startswith("pricefull"))
    assert len(paths) >= 5  # Shufersal, Carrefour, NCR store 722, NCR store 039, the basket's own
    for path in paths:
        assert 1 <= len(read_items(path.name, path.read_bytes())) <= 3, path.name

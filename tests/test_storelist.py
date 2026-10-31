"""The store list: the store ids in each portal's Stores file, as published."""
import gzip
from pathlib import Path

from collector.storelist import store_ids

FIXTURES = Path(__file__).parent / "fixtures"


def test_shufersal_gzipped_utf8_ids_unpadded():
    data = (FIXTURES / "shufersal" / "Stores7290027600007-000-20261031-020.gz").read_bytes()
    assert store_ids(data) == {"756", "374", "314"}  # two sub-chains, root <Chain>


def test_ncr_plain_utf16_ids_padded():
    data = (FIXTURES / "ncr" / "Stores7290058140886-000-20261031-050500.xml").read_bytes()
    assert store_ids(data) == {"001", "002", "003"}


def test_carrefour_plain_utf16_ids_padded():
    data = (FIXTURES / "carrefour" / "Stores7290055700007-000-20261031-000100.xml").read_bytes()
    assert store_ids(data) == {"002", "004", "009"}


def test_blank_ids_skipped_and_spaces_trimmed():
    xml = (b'<?xml version="1.0" encoding="UTF-8"?><Root><SubChains><SubChain><Stores>'
           b"<Store><StoreID> 7 </StoreID></Store><Store><StoreID></StoreID></Store>"
           b"</Stores></SubChain></SubChains></Root>")
    assert store_ids(xml) == {"7"}
    assert store_ids(gzip.compress(xml)) == {"7"}

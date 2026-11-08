"""The store list: a chain's stores with their sub-chain, name and type, and the stores the basket counts (B2)."""
import gzip
from datetime import date
from pathlib import Path

import pytest

from basket.chains import EXCLUDED, SLUGS, Exclusion
from basket import build
from basket.stores import NoStoreList, Store, chain_stores, day_store_list, excluded, included, read_stores

FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 11, 2)
SHUFERSAL_LIST = gzip.compress(
    ('﻿<?xml version="1.0" encoding="UTF-8"?><Chain><ChainID>7290027600007</ChainID><SubChains>'
     "<SubChain><SubChainID>5</SubChainID><SubChainName>Be</SubChainName><Stores>"
     "<Store><StoreID>93</StoreID><StoreType>1</StoreType><StoreName>סניף לדוגמה 1</StoreName></Store>"
     "</Stores></SubChain>"
     "<SubChain><SubChainID>2</SubChainID><SubChainName>שופרסל דיל</SubChainName><Stores>"
     "<Store><StoreID>30</StoreID><StoreType>1</StoreType><StoreName>סניף לדוגמה 2</StoreName></Store>"
     "<Store><StoreID>413</StoreID><StoreType>2</StoreType><StoreName>שופרסל ONLINE</StoreName></Store>"
     "</Stores></SubChain></SubChains></Chain>").encode(), mtime=0)
NCR_LIST = (
    "<Root><ChainID>7290058140886</ChainID><SubChains><SubChain><SubChainID>001</SubChainID><Stores>"
    "<Store><StoreID>001</StoreID><StoreType>1</StoreType><StoreName>סניף לדוגמה 1</StoreName></Store>"
    "<Store><StoreID>039</StoreID><StoreType>1</StoreType><StoreName>סניף לדוגמה 2</StoreName></Store>"
    "</Stores></SubChain></SubChains></Root>").encode("utf-16")
SHUFERSAL_STORES = [Store("93", "5", "סניף לדוגמה 1", "1"), Store("30", "2", "סניף לדוגמה 2", "1"),
                    Store("413", "2", "שופרסל ONLINE", "2")]
NCR_STORES = [Store("1", "1", "סניף לדוגמה 1", "1"), Store("39", "1", "סניף לדוגמה 2", "1")]


def raw_tree(tmp_path: Path, files: dict[tuple[str, str], bytes], slug: str = "shufersal") -> Path:
    """Lay `files` ((YYYY-MM-DD, name) -> bytes) under raw/chain=<slug>/date=<day>/; the raw directory."""
    for (day, name), data in files.items():
        folder = tmp_path / "raw" / f"chain={slug}" / f"date={day}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    return tmp_path / "raw"


def test_reads_shufersal_and_ncr_layouts():
    assert NCR_LIST.startswith(b"\xff\xfe") and SHUFERSAL_LIST.startswith(b"\x1f\x8b")
    assert read_stores(SHUFERSAL_LIST) == SHUFERSAL_STORES  # gzipped UTF-8 with a BOM, root <Chain>
    assert read_stores(NCR_LIST) == NCR_STORES  # plain UTF-16 with a BOM, root <Root>, ids padded


def test_reads_the_other_spelling_of_the_tags_trimmed():
    xml = ("<Root><SubChains><SubChain><SubChainId> 007 </SubChainId><Stores><Store><StoreId> 012 </StoreId>"
           "<StoreType> 1 </StoreType><StoreName> סניף </StoreName></Store></Stores></SubChain></SubChains></Root>")
    assert read_stores(xml.encode()) == [Store("12", "7", "סניף", "1")]


def test_store_outside_a_sub_chain_has_none_and_a_store_without_an_id_is_skipped():
    xml = ("<Root><Stores><Store><StoreID>5</StoreID><StoreName>א</StoreName></Store>"
           "<Store><StoreID> </StoreID><StoreName>ב</StoreName></Store></Stores></Root>")
    assert read_stores(xml.encode()) == [Store("5", None, "א", "")]


def test_included_drops_be_and_online_for_shufersal():
    assert included(SHUFERSAL_STORES, "shufersal") == {"30"}


def test_included_drops_rami_levy_039_and_keeps_everything_for_the_others():
    assert included(NCR_STORES, "ramilevy") == {"1"}
    for slug in ("osherad", "carrefour", "yochananof"):
        assert included(NCR_STORES, slug) == {"1", "39"}


def test_excluded_lists_the_dropped_stores_with_names():
    assert excluded(SHUFERSAL_STORES, "shufersal") == [Store("93", "5", "סניף לדוגמה 1", "1"),
                                                        Store("413", "2", "שופרסל ONLINE", "2")]
    assert excluded(NCR_STORES, "osherad") == []


def test_exclusions_name_every_chain_and_say_why():
    assert SLUGS == ("shufersal", "ramilevy", "osherad", "carrefour", "yochananof")
    assert set(EXCLUDED) == set(SLUGS)
    assert EXCLUDED["shufersal"] == Exclusion(
        frozenset({"5"}), frozenset({"413"}),
        "sub-chain 5 'Be', 97 stores on 2026-11-02, carries 12% of the shared barcodes; store 413 'שופרסל ONLINE'")


def test_carrefour_online_store_471_is_out():
    online = Store("471", "1", "קרפור אונליין   כפר סבא @ קרפור (5304)", "2")  # its store list of 2026-11-02
    stores = [online, Store("2", "1", "סניף לדוגמה 1", "1")]
    assert included(stores, "carrefour") == {"2"}
    assert excluded(stores, "carrefour") == [online]
    assert "store 471 'קרפור אונליין   כפר סבא @ קרפור (5304)'" in EXCLUDED["carrefour"].why


def test_rami_levy_internet_store_039_is_out():
    online = Store("39", "1", "מרלוג אינטרנט", "2")  # its store list of 2026-11-02
    stores = [Store("1", "1", "סניף לדוגמה 1", "1"), online]
    assert included(stores, "ramilevy") == {"1"}
    assert excluded(stores, "ramilevy") == [online]
    assert "store 039 'מרלוג אינטרנט'" in EXCLUDED["ramilevy"].why


def test_the_survey_found_nothing_to_leave_out_at_the_other_two():
    nothing = Exclusion(frozenset(), frozenset(), "")
    assert [EXCLUDED[slug] for slug in ("osherad", "yochananof")] == [nothing] * 2


def test_an_unknown_chain_is_refused():
    with pytest.raises(KeyError):
        included(NCR_STORES, "victory")


def test_day_store_list_takes_the_latest_name_of_the_day(tmp_path):
    raw = raw_tree(tmp_path, {
        ("2026-11-02", "Stores7290027600007-000-20261102-020.gz"): b"early",
        ("2026-11-02", "Stores7290027600007-000-20261102-030.gz"): b"late",
        ("2026-11-02", "PriceFull7290027600007-001-030-20261102-040000.gz"): b"price",
    })
    assert day_store_list(raw, "shufersal", DAY) == (b"late", DAY)


def test_day_store_list_reads_a_conflict_copy_and_a_lower_case_name(tmp_path):
    raw = raw_tree(tmp_path, {("2026-11-02", "stores7290027600007-000-20261102-020.gz.0123456789ab"): b"copy"})
    assert day_store_list(raw, "shufersal", DAY) == (b"copy", DAY)


def test_day_store_list_falls_back_to_the_latest_earlier_day(tmp_path):
    raw = raw_tree(tmp_path, {
        ("2026-10-31", "Stores7290027600007-000-20261031-020.gz"): b"oct 31",
        ("2026-11-01", "Stores7290027600007-000-20261101-020.gz"): b"nov 1",
        ("2026-11-02", "PriceFull7290027600007-001-030-20261102-040000.gz"): b"price",
        ("2026-11-03", "Stores7290027600007-000-20261103-020.gz"): b"nov 3",
    })
    assert day_store_list(raw, "shufersal", DAY) == (b"nov 1", date(2026, 11, 1))
    assert day_store_list(raw, "shufersal", date(2026, 10, 30)) is None  # only later days have one
    assert day_store_list(raw, "ramilevy", DAY) is None  # no folder for the chain


def test_day_store_list_reads_only_names_of_the_folders_day(tmp_path):
    raw = raw_tree(tmp_path, {
        ("2026-11-01", "Stores7290027600007-000-20261101-020.gz"): b"nov 1",
        ("2026-11-02", "Stores7290027600007-000-20261103-020.gz"): b"named nov 3",
    })
    assert day_store_list(raw, "shufersal", DAY) == (b"nov 1", date(2026, 11, 1))


def test_chain_stores_reads_the_list_and_gives_its_day(tmp_path):
    raw = raw_tree(tmp_path, {("2026-11-01", "Stores7290027600007-000-20261101-020.gz"): SHUFERSAL_LIST,
                              ("2026-11-02", "PriceFull7290027600007-001-030-20261102-040000.gz"): b"price"})
    assert chain_stores(raw, "shufersal", DAY) == (SHUFERSAL_STORES, date(2026, 11, 1))  # the latest earlier day's


def test_chain_stores_without_a_list_on_or_before_the_day_is_refused_naming_the_chain(tmp_path):
    raw = raw_tree(tmp_path, {("2026-11-03", "Stores7290027600007-000-20261103-020.gz"): SHUFERSAL_LIST})
    with pytest.raises(NoStoreList) as refused:
        chain_stores(raw, "shufersal", DAY)
    assert str(refused.value) == f"no store list for chain 'shufersal' on or before 2026-11-02 under {raw}"
    assert build.NoStoreList is NoStoreList  # the build refuses a chain with the same error


def test_every_stores_fixture_reads():
    found = {path.parent.name: read_stores(path.read_bytes()) for path in FIXTURES.glob("*/Stores*")}
    assert {slug: [(s.id, s.sub_chain) for s in stores] for slug, stores in found.items()} == {
        "shufersal": [("756", "1"), ("374", "1"), ("314", "15")],
        "ncr": [("1", "1"), ("2", "1"), ("3", "1")],
        "carrefour": [("2", "1"), ("4", "1"), ("9", "1")],
    }
    assert all(s.name and s.store_type == "1" for stores in found.values() for s in stores)

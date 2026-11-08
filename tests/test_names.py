"""File names: the kind, chain, store and day each published name carries (docs/portals.md)."""
from datetime import date
from pathlib import Path

import pytest

from collector.names import KINDS, FileName, hour_of, parse_file_name

FIXTURES = Path(__file__).parent / "fixtures"
# By portal folder: the NCR portal's fixtures are Rami Levy's, Osher Ad's and Yochananof's; the basket's own fixture is a
# made-up chain in the common layout.
CHAIN_IDS = {"shufersal": ("7290027600007",), "ncr": ("7290058140886", "7290103152017", "7290803800003"),
             "carrefour": ("7290055700007",), "basket": ("7290000000001",)}


def test_kinds():
    assert KINDS == ("Stores", "PriceFull", "PromoFull", "Price", "Promo")


@pytest.mark.parametrize("name, kind, chain, sub_chain, store, day", [
    # Shufersal: the listing shows names without .gz; the blob path has it
    ("PriceFull7290027600007-002-045-20261031-030000", "PriceFull", "7290027600007", "002", "045", date(2026, 10, 31)),
    ("Stores7290027600007-000-20261031-020", "Stores", "7290027600007", None, None, date(2026, 10, 31)),
    ("Promo7290027600007-002-045-20261031-020000.gz", "Promo", "7290027600007", "002", "045", date(2026, 10, 31)),
    ("PromoFull7290027600007-000-878-20261031-030000", "PromoFull", "7290027600007", "000", "878", date(2026, 10, 31)),
    ("Price7290027600007-001-030-20261031-040000", "Price", "7290027600007", "001", "030", date(2026, 10, 31)),
    # Rami Levy on NCR
    ("PriceFull7290058140886-001-722-20261101-001016.gz", "PriceFull", "7290058140886", "001", "722", date(2026, 11, 1)),
    ("Stores7290058140886-000-20261031-050500.xml", "Stores", "7290058140886", None, None, date(2026, 10, 31)),
    # Rami Levy's store 039: lower case, no sub-chain, date and time run together (YYYYMMDDHHMM)
    ("pricefull7290058140886-039-202610310517.gz", "PriceFull", "7290058140886", None, "039", date(2026, 10, 31)),
    ("promofull7290058140886-039-202610310517.gz", "PromoFull", "7290058140886", None, "039", date(2026, 10, 31)),
    ("price7290058140886-039-202610310517.gz", "Price", "7290058140886", None, "039", date(2026, 10, 31)),
    ("promo7290058140886-039-202611010004.gz", "Promo", "7290058140886", None, "039", date(2026, 11, 1)),
    # Carrefour
    ("PriceFull7290055700007-001-472-20261031-051016.gz", "PriceFull", "7290055700007", "001", "472", date(2026, 10, 31)),
    ("Stores7290055700007-000-20261031-000100.xml", "Stores", "7290055700007", None, None, date(2026, 10, 31)),
])
def test_published_names(name, kind, chain, sub_chain, store, day):
    assert parse_file_name(name) == FileName(
        raw=name, kind=kind, chain_id=chain, store=store, day=day, sub_chain=sub_chain)


def test_full_kinds_never_read_as_the_short_ones():
    assert parse_file_name("PriceFull7290027600007-001-030-20261031-030000").kind == "PriceFull"
    assert parse_file_name("PromoFull7290027600007-000-878-20261031-030000").kind == "PromoFull"
    assert parse_file_name("pricefull7290058140886-039-202610310517.gz").kind == "PriceFull"
    assert parse_file_name("promofull7290058140886-039-202610310517.gz").kind == "PromoFull"


def test_store_is_the_group_before_the_date_not_the_sub_chain():
    assert parse_file_name("PriceFull7290027600007-001-030-20261031-030000").store == "030"


def test_sub_chain_is_the_group_before_the_store():
    shufersal = parse_file_name("PriceFull7290027600007-005-030-20261102-030000")
    assert (shufersal.sub_chain, shufersal.store) == ("005", "030")
    # store 039's names carry the store only: there is no sub-chain to read
    assert parse_file_name("pricefull7290058140886-039-202611010514.gz").sub_chain is None


def test_day_comes_from_the_name_not_the_clock():
    # Shufersal still lists a 2026-07-15 PromoFull of store 550 (docs/portals.md); its
    # sub-chain and time here are made up.
    names = ("PromoFull7290027600007-000-550-20260715-030000",
             "PriceFull7290058140886-001-722-20261101-001016.gz",
             "Stores7290055700007-000-20261031-000100.xml")
    assert [parse_file_name(n).day for n in names] == [date(2026, 7, 15), date(2026, 11, 1), date(2026, 10, 31)]


def test_every_fixture_file_name_parses():
    files = sorted(p for p in FIXTURES.glob("*/*") if p.suffix in (".gz", ".xml"))
    assert len(files) == 14
    for path in files:
        parsed = parse_file_name(path.name)
        assert parsed is not None, path.name
        assert parsed.chain_id in CHAIN_IDS[path.parent.name]
        assert path.name.lower().startswith(parsed.kind.lower())  # store 039's names are lower case


@pytest.mark.parametrize("name", [
    "index.html",
    "",
    "PriceFull",
    "PriceFull729002760000-001-030-20261031-030000",       # 12-digit chain id
    "PriceFull72900276000071-001-030-20261031-030000",     # 14-digit chain id
    "Prices7290027600007-001-030-20261031-030000",         # no such kind
    "PriceFull7290027600007-20261031-030000",              # a price file with no store
    "PriceFull7290027600007-001-030-20261341-030000",      # no such day
    "PriceFull7290027600007-001-030-20261031-030000.zip",
    "PriceFull7290027600007-001-030-20261031-030000.gz.part",
    "/file/d/PriceFull7290027600007-001-030-20261031-030000.gz",
])
def test_anything_else_is_none(name):
    assert parse_file_name(name) is None


NCR_NAME = "PriceFull7290058140886-001-722-20261101-001016.gz"


@pytest.mark.parametrize("name", [
    pytest.param(NCR_NAME.replace("-722-", "-٧٢٢-"), id="Arabic-Indic digits in the store"),
    pytest.param(NCR_NAME.replace("7290058140886", "٧290058140886"), id="an Arabic-Indic digit in the chain id"),
    pytest.param(NCR_NAME.replace("20261101", "2026110١"), id="an Arabic-Indic digit in the date"),
    pytest.param(NCR_NAME.replace("7290058140886", "７290058140886"), id="a full-width digit"),
    pytest.param(NCR_NAME.replace("-001016", "-00101०"), id="a Devanagari digit in the time"),
])
def test_non_ascii_digits_do_not_parse(name):
    """Ruling R20: a name is ASCII. A name that parses goes into a download link, and urllib raises
    UnicodeEncodeError, outside Http's handling, on a non-ASCII path."""
    assert parse_file_name(name) is None


@pytest.mark.parametrize("name", [
    pytest.param("ſtores7290058140886-000-20261031-050500.xml", id="a long s for the S of Stores"),
    pytest.param("PrıceFull7290058140886-001-722-20261101-001016.gz", id="a dotless i in PriceFull"),
    pytest.param("PRİCE7290058140886-001-722-20261101-001016.gz", id="a dotted capital I in PRICE"),
])
def test_non_ascii_letters_that_fold_to_a_kind_do_not_parse(name):
    """Unicode case-folding matches these to a kind's letters; they must read as no name, not raise."""
    assert parse_file_name(name) is None


@pytest.mark.parametrize("name, hour", [
    ("Price7290058140886-001-722-20261101-071016.gz", "07"),  # NCR: -YYYYMMDD-HHMMSS
    ("Price7290055700007-001-012-20261031-110008.gz", "11"),  # Carrefour
    ("Promo7290027600007-001-001-20261106-095959", "09"),  # Shufersal's batch stamp, listed without .gz
    ("price7290058140886-039-202611011002.gz", "10"),  # Rami Levy's store 039: -YYYYMMDDHHMM
    ("Stores7290027600007-000-20261031-020.gz", None),  # Shufersal's store list: a time of three digits
    ("Price7290058140886-001-099-20261031.gz", None),  # no time after the date
    ("Price7290058140886-001-099-20261031-250000.gz", None),  # no hour 25
    ("notes.txt", None),  # not a published name
])
def test_hour_of_reads_each_portals_time(name, hour):
    """Review focus 5: the hour in every portal's name shape, two digits; None when it cannot be read, so the check
    counts the name under "unknown" instead of dropping it."""
    assert hour_of(name) == hour

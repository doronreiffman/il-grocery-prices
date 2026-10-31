"""File names: the kind, chain, store and day each published name carries (docs/portals.md)."""
from datetime import date
from pathlib import Path

import pytest

from collector.names import KINDS, FileName, parse_file_name

FIXTURES = Path(__file__).parent / "fixtures"
CHAIN_IDS = {"shufersal": "7290027600007", "ncr": "7290058140886", "carrefour": "7290055700007"}


def test_kinds():
    assert KINDS == ("Stores", "PriceFull", "PromoFull", "Price", "Promo")


@pytest.mark.parametrize("name, kind, chain, store, day", [
    # Shufersal: the listing shows names without .gz; the blob path has it
    ("PriceFull7290027600007-002-045-20261031-030000", "PriceFull", "7290027600007", "045", date(2026, 10, 31)),
    ("Stores7290027600007-000-20261031-020", "Stores", "7290027600007", None, date(2026, 10, 31)),
    ("Promo7290027600007-002-045-20261031-020000.gz", "Promo", "7290027600007", "045", date(2026, 10, 31)),
    ("PromoFull7290027600007-000-878-20261031-030000", "PromoFull", "7290027600007", "878", date(2026, 10, 31)),
    ("Price7290027600007-001-030-20261031-040000", "Price", "7290027600007", "030", date(2026, 10, 31)),
    # Rami Levy on NCR
    ("PriceFull7290058140886-001-722-20261101-001016.gz", "PriceFull", "7290058140886", "722", date(2026, 11, 1)),
    ("Stores7290058140886-000-20261031-050500.xml", "Stores", "7290058140886", None, date(2026, 10, 31)),
    # Rami Levy's store 039: lower case, no sub-chain, date and time run together (YYYYMMDDHHMM)
    ("pricefull7290058140886-039-202610310517.gz", "PriceFull", "7290058140886", "039", date(2026, 10, 31)),
    ("promofull7290058140886-039-202610310517.gz", "PromoFull", "7290058140886", "039", date(2026, 10, 31)),
    ("price7290058140886-039-202610310517.gz", "Price", "7290058140886", "039", date(2026, 10, 31)),
    ("promo7290058140886-039-202611010004.gz", "Promo", "7290058140886", "039", date(2026, 11, 1)),
    # Carrefour
    ("PriceFull7290055700007-001-472-20261031-051016.gz", "PriceFull", "7290055700007", "472", date(2026, 10, 31)),
    ("Stores7290055700007-000-20261031-000100.xml", "Stores", "7290055700007", None, date(2026, 10, 31)),
])
def test_published_names(name, kind, chain, store, day):
    assert parse_file_name(name) == FileName(raw=name, kind=kind, chain_id=chain, store=store, day=day)


def test_full_kinds_never_read_as_the_short_ones():
    assert parse_file_name("PriceFull7290027600007-001-030-20261031-030000").kind == "PriceFull"
    assert parse_file_name("PromoFull7290027600007-000-878-20261031-030000").kind == "PromoFull"
    assert parse_file_name("pricefull7290058140886-039-202610310517.gz").kind == "PriceFull"
    assert parse_file_name("promofull7290058140886-039-202610310517.gz").kind == "PromoFull"


def test_store_is_the_group_before_the_date_not_the_sub_chain():
    assert parse_file_name("PriceFull7290027600007-001-030-20261031-030000").store == "030"


def test_day_comes_from_the_name_not_the_clock():
    # Shufersal still lists a 2026-07-15 PromoFull of store 550 (docs/portals.md); its
    # sub-chain and time here are made up.
    names = ("PromoFull7290027600007-000-550-20260715-030000",
             "PriceFull7290058140886-001-722-20261101-001016.gz",
             "Stores7290055700007-000-20261031-000100.xml")
    assert [parse_file_name(n).day for n in names] == [date(2026, 7, 15), date(2026, 11, 1), date(2026, 10, 31)]


def test_every_fixture_file_name_parses():
    files = sorted(p for p in FIXTURES.glob("*/*") if p.suffix in (".gz", ".xml"))
    assert len(files) == 9
    for path in files:
        parsed = parse_file_name(path.name)
        assert parsed is not None, path.name
        assert parsed.chain_id == CHAIN_IDS[path.parent.name]
        assert path.name.startswith(parsed.kind)


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

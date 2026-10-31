"""The chain list and the interface every portal adapter implements."""
import inspect
import urllib.parse
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields
from typing import get_args, get_type_hints

import pytest

from collector import chains
from collector.chains import CHAINS, Chain
from collector.http import Http
from collector.names import parse_file_name
from collector.sources import Listed, Source

GOV_IL = "https://www.gov.il/he/pages/cpfta_prices_regulations"


def test_exactly_the_five_chains():
    assert set(CHAINS) == {"shufersal", "ramilevy", "osherad", "carrefour", "yochananof"}


def test_each_chain_filed_under_its_own_slug():
    assert all(chain.slug == slug for slug, chain in CHAINS.items())


def test_names():
    assert {slug: c.name for slug, c in CHAINS.items()} == {
        "shufersal": "Shufersal", "ramilevy": "Rami Levy", "osherad": "Osher Ad",
        "carrefour": "Carrefour", "yochananof": "Yochananof"}


def test_portals():
    assert {slug: c.portal for slug, c in CHAINS.items()} == {
        "shufersal": "shufersal", "ramilevy": "ncr", "osherad": "ncr",
        "carrefour": "carrefour", "yochananof": "ncr"}
    assert set(get_args(get_type_hints(Chain)["portal"])) == {"shufersal", "ncr", "carrefour"}


def test_ncr_chains_carry_the_usernames_the_gov_il_list_prints_and_no_one_else_has_one():
    assert {slug: c.username for slug, c in CHAINS.items()} == {
        "shufersal": None, "ramilevy": "RamiLevi", "osherad": "osherad",
        "carrefour": None, "yochananof": "yohananof"}


def test_username_defaults_to_none():
    assert Chain("x", "X", "carrefour", "https://example.org").username is None


def test_no_password_anywhere_on_chain():
    assert [f.name for f in fields(Chain)] == ["slug", "name", "portal", "base_url", "username"]
    for chain in CHAINS.values():
        assert [a for a in dir(chain) if "pass" in a.lower() or "pwd" in a.lower()] == []


def test_base_urls_as_docs_portals_records_them():
    assert {slug: c.base_url for slug, c in CHAINS.items()} == {
        "shufersal": "https://prices.shufersal.co.il",
        "ramilevy": "https://url.publishedprices.co.il",
        "osherad": "https://url.publishedprices.co.il",
        "carrefour": "https://prices.carrefour.co.il",
        "yochananof": "https://url.publishedprices.co.il"}


def test_every_base_url_is_https():
    for chain in CHAINS.values():
        parts = urllib.parse.urlsplit(chain.base_url)
        assert (parts.scheme, bool(parts.netloc)) == ("https", True), chain.base_url


def test_usernames_cite_the_gov_il_page_and_its_update_date():
    source = inspect.getsource(chains)
    cited = source.find(GOV_IL)
    assert cited != -1
    assert "12.08.2026" in source[cited:cited + 200]
    assert cited < source.find('"RamiLevi"')


def test_chain_is_frozen():
    with pytest.raises(FrozenInstanceError):
        CHAINS["ramilevy"].username = "someone"


def test_listed_holds_the_parsed_name_and_its_link():
    name = parse_file_name("PriceFull7290058140886-001-722-20261101-001016.gz")
    item = Listed(name=name, url=f"https://url.publishedprices.co.il/file/d/{name.raw}")
    assert [f.name for f in fields(Listed)] == ["name", "url"]
    assert item.name.store == "722"
    assert item == Listed(name=name, url=item.url)
    with pytest.raises(FrozenInstanceError):
        item.url = "https://elsewhere.example"


def test_source_interface():
    assert list(inspect.signature(Source.listing).parameters) == ["self", "http", "kinds"]
    assert list(inspect.signature(Source.download).parameters) == ["self", "http", "item"]
    assert get_type_hints(Source.listing) == {"http": Http, "kinds": tuple[str, ...], "return": Iterator[Listed]}
    assert get_type_hints(Source.download) == {"http": Http, "item": Listed, "return": bytes}

"""The chain list, the adapter each chain gets, and the interface every portal adapter implements."""
import inspect
import urllib.parse
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields
from typing import get_args, get_type_hints

import pytest

from collector import chains
from collector.chains import CHAINS, Chain, source_for
from collector.http import Blocked, Http, HttpError
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, Source, checked_name
from collector.sources.carrefour import CarrefourSource
from collector.sources.ncr import NcrSource
from collector.sources.shufersal import ShufersalSource

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


def test_source_counts_the_names_it_skipped():
    """The run loop records how many listed names did not parse (the manifest's `unparsed`)."""
    assert get_type_hints(Source)["unparsed"] is int


def test_listing_unreadable_is_neither_a_block_nor_an_http_error():
    """The run loop fails the run on it (no latch, no retry): it must not be caught as either."""
    assert issubclass(ListingUnreadable, Exception)
    assert not issubclass(ListingUnreadable, (Blocked, HttpError))


# ---- the adapter each chain gets ----

@pytest.mark.parametrize("slug, adapter", [("shufersal", ShufersalSource), ("ramilevy", NcrSource),
                                           ("osherad", NcrSource), ("carrefour", CarrefourSource),
                                           ("yochananof", NcrSource)])
def test_source_for_gives_each_chain_its_portals_adapter(slug, adapter):
    assert type(source_for(CHAINS[slug])) is adapter


@pytest.mark.parametrize("slug", ["ramilevy", "osherad", "yochananof"])
def test_ncr_adapter_logs_in_as_the_chains_published_username(slug):
    assert source_for(CHAINS[slug]).username == CHAINS[slug].username


def test_each_call_gives_a_fresh_adapter():
    """An adapter holds its last listing's `unparsed` count: two runs must not share one."""
    assert source_for(CHAINS["carrefour"]) is not source_for(CHAINS["carrefour"])


def test_no_adapter_for_a_portal_not_in_version_one():
    with pytest.raises(ValueError, match="no adapter for the 'ftp' portal"):
        source_for(Chain("x", "X", "ftp", "https://example.org"))


# ---- names a download link is built from (ruling R19) ----

GOOD = "PriceFull7290058140886-001-722-20261101-001016.gz"


@pytest.mark.parametrize("name", [
    GOOD, "pricefull7290058140886-039-202610310517.gz", "Stores7290055700007-000-20261031-000100.xml",
    "PriceFull7290027600007-001-030-20261031-030000",
])
def test_safe_names_that_parse_are_parsed(name):
    assert checked_name(name, "here") == parse_file_name(name)


@pytest.mark.parametrize("name", ["index.html", "readme", "", "PriceFull7290058140886-001-722-20261399-001016.gz",
                                  "Price-list.gz", "~backup", "a%2Fb"])
def test_safe_names_that_do_not_parse_are_none(name):
    """Skipped and counted by the adapter (`unparsed`), not a reason to stop."""
    assert checked_name(name, "here") is None


@pytest.mark.parametrize("name", [
    pytest.param("sub/" + GOOD, id="a slash"),
    pytest.param("sub\\" + GOOD, id="a backslash"),
    pytest.param("..", id="two dots"),
    pytest.param("PriceFull..gz", id="two dots inside"),
    pytest.param(GOOD + "?x=1", id="a question mark"),
    pytest.param(GOOD + "#top", id="a hash"),
    pytest.param(GOOD + " ", id="a trailing space"),
    pytest.param("Price Full.gz", id="a space"),
    pytest.param(GOOD + "\t", id="a tab"),
    pytest.param(GOOD + "\n", id="a line break"),
    pytest.param(GOOD + "\x00", id="a NUL"),
    pytest.param(GOOD + "\x7f", id="DEL"),
    pytest.param(GOOD.replace("-722-", "-٧٢٢-"), id="Arabic-Indic digits, which parse"),
    pytest.param(GOOD + " ", id="a no-break space"),
    pytest.param("מחירים.gz", id="Hebrew"),
])
def test_unsafe_names_are_unreadable_and_named(name):
    """A link is built from the name: one that could leave the folder, end the path, or not go into a
    URL as it is raises, whether or not it parses. Arabic-Indic digits parse as digits, and would
    then fail inside urllib, outside Http's handling."""
    with pytest.raises(ListingUnreadable) as caught:
        checked_name(name, "the listing, entry 3")
    assert str(caught.value) == f"the listing, entry 3: the file name {name!r} is not safe to put in a link"


def test_arabic_indic_digits_do_parse():
    """Why the name check refuses non-ASCII before parsing: the parser's \\d takes these digits."""
    assert parse_file_name(GOOD.replace("-722-", "-٧٢٢-")) is not None

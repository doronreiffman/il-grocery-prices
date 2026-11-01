"""The Carrefour source: today's page, its file list read from the two literals in its inline script,
links built from the day's folder and each file's name.

The real Http runs over a fake portal (Portal), inside a real urllib opener built by `build_opener`, as
tests/test_shufersal.py does. The page is the fixture (docs/portals.md, "Carrefour"), or the fixture
with its `const path` or `const files` line rewritten.
"""
import http.client
import io
import json
import re
import urllib.request
import urllib.response
from pathlib import Path

import pytest

from collector.chains import CHAINS
from collector.http import Blocked, Http, build_opener
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, Source
from collector.sources import carrefour
from collector.sources.carrefour import CarrefourSource

UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
FIXTURES = Path(__file__).parent / "fixtures" / "carrefour"
BASE = "https://prices.carrefour.co.il"
PAGE = f"{BASE}/"
TEXT = (FIXTURES / "listing.html").read_text(encoding="utf-8")
PATH_LINE = "    const path = '20261031';\n"
FILES_LINE = re.compile(r"    const files = (\[.*\]);\n")
FILES = json.loads(FILES_LINE.search(TEXT).group(1))
NAMES = [file["name"] for file in FILES]
PRICEFULL = "PriceFull7290055700007-001-472-20261031-051016.gz"
GZ = (FIXTURES / PRICEFULL).read_bytes()
ALL_KINDS = ("Stores", "PriceFull", "PromoFull", "Price", "Promo")


def reply(status=200, body=b"", content_type="text/html; charset=UTF-8"):
    """One canned answer, built the way urllib's HTTP handler builds a real one."""
    def respond(req):
        message = http.client.HTTPMessage()
        message["Content-Type"] = content_type
        resp = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, status)
        resp.msg = http.client.responses.get(status, "")
        return resp
    return respond


def served(text):
    return reply(body=text.encode("utf-8"))


def page(path=None, files=None, files_line=None):
    """The fixture page, with `path` as its `const path`, `files` (a list, as JSON) as its
    `const files`, or `files_line` in place of that whole line."""
    text = TEXT
    if path is not None:
        text = text.replace(PATH_LINE, f"    const path = '{path}';\n")
    if files is not None:
        files_line = f"    const files = {json.dumps(files)};\n"
    if files_line is not None:
        text = FILES_LINE.sub(lambda m: files_line, text)
    return text


def file(name):
    return dict(FILES[0], name=name)


class Portal(urllib.request.BaseHandler):
    """The portal, in place of the network: answers by URL (a list is served in turn, its last answer
    kept); every other request fails the test. Every request is logged."""
    handler_order = 400  # after urllib's proxy handler (100), before its HTTP and HTTPS handlers (500)

    def __init__(self, routes):
        self.routes = dict(routes)
        self.requested = []

    def https_open(self, req):
        self.requested.append((req.get_method(), req.full_url))
        assert len(self.requested) <= 50
        route = self.routes.get(req.full_url)
        if route is None:
            raise AssertionError(f"unexpected request: {req.get_method()} {req.full_url}")
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        return route(req)

    http_open = https_open


def connect(listing=None):
    routes = {PAGE: listing if listing is not None else served(TEXT)}
    routes |= {f"{BASE}/20261031/{name}": reply(body=GZ, content_type="application/x-gzip") for name in NAMES}
    portal = Portal(routes)
    return Http(UA, opener=build_opener(portal), sleep=lambda seconds: None), portal


def test_page_helper_matches_the_served_page():
    assert TEXT.count(PATH_LINE) == 1
    assert len(FILES_LINE.findall(TEXT)) == 1
    assert page(path="20261031") == TEXT
    assert json.loads(FILES_LINE.search(page(files=FILES)).group(1)) == FILES
    assert len(FILES) == 9


# ---- the interface ----

def test_base_url_is_the_chains():
    assert carrefour.BASE_URL == CHAINS["carrefour"].base_url


def test_is_a_source():
    assert Source in CarrefourSource.__mro__


# ---- the listing ----

def test_listing_reads_todays_page_once_and_yields_every_file_with_its_link():
    """docs/portals.md: GET / shows today's files (Israel date); each links to /<path>/<name>."""
    http, portal = connect()
    listing = CarrefourSource().listing(http, ALL_KINDS)
    assert portal.requested == []  # nothing until the first item is asked for
    listed = list(listing)
    assert portal.requested == [("GET", PAGE)]
    assert listed == [Listed(parse_file_name(name), f"{BASE}/20261031/{name}") for name in NAMES]


def test_link_folder_is_the_pages_path():
    http, _ = connect(served(page(path="20261101")))
    assert {item.url.rsplit("/", 2)[1] for item in CarrefourSource().listing(http, ALL_KINDS)} == {"20261101"}


@pytest.mark.parametrize("kinds, count", [
    pytest.param(("Stores",), 1, id="Stores"),
    pytest.param(("PriceFull", "PromoFull"), 6, id="the full files"),
    pytest.param(("Price",), 2, id="Price, not PriceFull"),
    pytest.param(("Promo",), 0, id="no Promo files, as on 10-31"),
])
def test_only_the_kinds_asked_for_are_listed(kinds, count):
    """docs/portals.md: one page holds every kind; Carrefour published no Promo files on 10-31, and a
    kind with no files on a page that has files is not an unreadable listing."""
    http, _ = connect()
    listed = [item.name.raw for item in CarrefourSource().listing(http, kinds)]
    assert listed == [name for name in NAMES if parse_file_name(name).kind in kinds]
    assert len(listed) == count


@pytest.mark.parametrize("text, problem", [
    pytest.param(page(files=[]), "lists no files", id="zero files"),
    pytest.param(page(files_line=""), "has no const files", id="no const files"),
    pytest.param(page(files_line="    const files = [{\"name\": \"x\"},;\n"), "const files is not JSON", id="files not JSON"),
    pytest.param(page(files_line="    const files = ['x'];\n"), "const files is not JSON", id="a JavaScript array, not JSON"),
    pytest.param(page(files_line="    const files = {\"name\": \"x\"};\n"), "const files is not a list", id="files an object"),
    pytest.param(page(files=FILES[:2] + ["x"]), "file 3 has no name", id="a file not an object"),
    pytest.param(page(files=[{"size": 1}]), "file 1 has no name", id="a file without a name"),
    pytest.param(page(files=[{"name": 5}]), "file 1 has no name", id="a name that is not text"),
    pytest.param(TEXT.replace(PATH_LINE, ""), "has no const path", id="no const path"),
    pytest.param("<html><body>Not Found</body></html>", "has no const path", id="another page"),
    pytest.param("", "has no const path", id="an empty answer"),
])
def test_page_that_does_not_read_as_the_file_list_is_unreadable(text, problem):
    """A list with no files means the portal changed, or the day's folder has not filled yet: the run
    fails and alerts, never "nothing published"."""
    http, portal = connect(served(text))
    with pytest.raises(ListingUnreadable) as caught:
        next(CarrefourSource().listing(http, ALL_KINDS))
    assert str(caught.value).startswith("the Carrefour page")
    assert problem in str(caught.value)
    assert portal.requested == [("GET", PAGE)]


@pytest.mark.parametrize("path", [
    pytest.param("2026103", id="seven digits"),
    pytest.param("202610311", id="nine digits"),
    pytest.param("", id="empty"),
    pytest.param("../20261031", id="up a folder"),
    pytest.param("20261031/..", id="a folder after"),
    pytest.param("2026-10-31", id="with dashes"),
    pytest.param("٢٠٢٦١٠٣١", id="Arabic-Indic digits"),
    pytest.param("２０２６１０３１", id="full-width digits"),
])
def test_path_that_is_not_eight_digits_is_unreadable_and_named(path):
    """Ruling R19: the day's folder goes into every link; anything but eight ASCII digits raises."""
    http, portal = connect(served(page(path=path)))
    with pytest.raises(ListingUnreadable) as caught:
        next(CarrefourSource().listing(http, ALL_KINDS))
    assert str(caught.value) == f"the Carrefour page's path {path!r} is not eight digits"
    assert portal.requested == [("GET", PAGE)]


def test_names_that_do_not_parse_are_skipped_and_counted():
    files = [file("index.html"), file(PRICEFULL), file("readme"), file("PriceFull7290055700007-001-472-20261399-051016.gz")]
    http, _ = connect(served(page(files=files)))
    source = CarrefourSource()
    assert source.unparsed == 0
    assert [item.name.raw for item in source.listing(http, ("PriceFull",))] == [PRICEFULL]
    assert source.unparsed == 3


def test_names_of_other_kinds_are_not_counted_as_unparsed():
    http, _ = connect()
    source = CarrefourSource()
    list(source.listing(http, ("Stores",)))
    assert source.unparsed == 0


def test_unparsed_count_starts_again_with_each_listing():
    http, _ = connect([served(page(files=[file("index.html"), file(PRICEFULL)])), served(TEXT)])
    source = CarrefourSource()
    list(source.listing(http, ("PriceFull",)))
    assert source.unparsed == 1
    list(source.listing(http, ("PriceFull",)))
    assert source.unparsed == 0


@pytest.mark.parametrize("name", [
    pytest.param("../" + PRICEFULL, id="up a folder"),
    pytest.param("20261030/" + PRICEFULL, id="another folder"),
    pytest.param(PRICEFULL + "?x=1", id="a query"),
    pytest.param("\\" + PRICEFULL, id="a backslash"),
    pytest.param("Price Full.gz", id="a space"),
    pytest.param(PRICEFULL.replace("-472-", "-٤٧٢-"), id="digits that parse but are not ASCII"),
])
def test_unsafe_name_anywhere_stops_the_listing_before_its_first_item(name):
    """Ruling R19: a link is built from each name; a name that is not safe in one raises, naming it,
    even in a kind not asked for, and before any item is given."""
    http, portal = connect(served(page(files=[file(PRICEFULL), file(NAMES[-1]), file(name)])))
    with pytest.raises(ListingUnreadable) as caught:
        next(CarrefourSource().listing(http, ("PriceFull", "Stores")))
    assert str(caught.value) == f"the Carrefour page, file 3: the file name {name!r} is not safe to put in a link"
    assert portal.requested == [("GET", PAGE)]


def test_refusal_is_a_block():
    """docs/portals.md: the site is reported blocked from outside Israel; a refusal stops the chain."""
    http, portal = connect(reply(403, b"<html>Forbidden</html>"))
    with pytest.raises(Blocked):
        list(CarrefourSource().listing(http, ALL_KINDS))
    assert portal.requested == [("GET", PAGE)]


# ---- downloads ----

def test_download_returns_the_body_as_received():
    http, portal = connect()
    source = CarrefourSource()
    item = next(item for item in source.listing(http, ("PriceFull",)) if item.name.raw == PRICEFULL)
    assert source.download(http, item) == GZ
    assert portal.requested == [("GET", PAGE), ("GET", f"{BASE}/20261031/{PRICEFULL}")]

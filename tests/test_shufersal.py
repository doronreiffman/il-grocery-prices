"""The Shufersal source: listing pages read to the last page the pager names and no further, one page
at a time; links checked before anything is fetched; an expired signed link refreshed once.

The real Http runs over a fake network (Portal), inside a real urllib opener built by `build_opener`,
as tests/test_http.py does: a 403 is judged a block by the code production runs, and the cookie jar
is production's. Listing pages are the fixtures (docs/portals.md, "Shufersal"), or the fixtures with
their rows renamed and their pager rewritten in the same markup.
"""
import http.client
import inspect
import io
import itertools
import logging
import re
import time
import types
import urllib.parse
import urllib.request
import urllib.response
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from collector.chains import CHAINS
from collector.http import Blocked, Http, HttpError, HttpTimeout, build_opener
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, OutOfTime, PageRead, PageTimeout, Source, Start
from collector.sources import shufersal
from collector.sources.shufersal import CATEGORY, ShufersalSource

UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
FIXTURES = Path(__file__).parent / "fixtures" / "shufersal"
LISTING = "https://prices.shufersal.co.il/FileObject/UpdateCategory"
FILE_HOST = "https://pricesprodpublic.blob.core.windows.net"
SE = datetime(2026, 10, 31, 22, 36, 2, tzinfo=timezone.utc)  # the se= of every link on the PriceFull fixture
OLD_SIGNATURE = "sig=SCRUBBED&amp;se=2026-10-31T22%3A36%3A02Z"
FRESH_SIGNATURE = "sig=FRESH&amp;se=2026-10-31T23%3A10%3A00Z"
NAME = "PriceFull7290027600007-001-030-20261031-030000"  # row 17 of the PriceFull fixture
GZ = (FIXTURES / f"{NAME}.gz").read_bytes()
OLD_LINK = f"{FILE_HOST}/pricefull/{NAME}.gz?sv=2014-02-14&sr=b&sig=SCRUBBED&se=2026-10-31T22%3A36%3A02Z&sp=r"
FRESH_LINK = f"{FILE_HOST}/pricefull/{NAME}.gz?sv=2014-02-14&sr=b&sig=FRESH&se=2026-10-31T23%3A10%3A00Z&sp=r"
AZURE_403 = b'<?xml version="1.0" encoding="utf-8"?><Error><Code>AuthenticationFailed</Code></Error>'

ROW = re.compile(r'        <tr class="webgrid-(?:row-style|alternating-row)">\n.*?</tr>\n', re.S)
TBODY = re.compile(r"(    <tbody>\n).*?(    </tbody>)", re.S)
TFOOT = re.compile(r"    <tfoot>\n.*?</tfoot>\n", re.S)
PAGER = re.compile(r'<td colspan="8">.*?</td>', re.S)
NAME_CELL = re.compile(r"<td>((?:Price|Promo|Stores)\w*7290027600007[-\d]*)</td>")
KEEP = object()


# ---- the fake network and the pages it serves ----

def reply(status=200, body=b"", content_type="text/html; charset=utf-8", headers=()):
    """One canned answer, built the way urllib's HTTP handler builds a real one."""
    def respond(req):
        message = http.client.HTTPMessage()
        message["Content-Type"] = content_type
        for key, value in headers:
            message[key] = value
        resp = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, status)
        resp.msg = http.client.responses.get(status, "")
        return resp
    return respond


def served(text, headers=()):
    return reply(body=text.encode("utf-8"), headers=headers)


def gz():
    return reply(body=GZ, content_type="application/octet-stream")


def refused(status=403):
    return reply(status, AZURE_403, "application/xml")


class Portal(urllib.request.BaseHandler):
    """Both hosts, in place of the network. `routes` answers by exact URL (a list is served in turn,
    its last answer kept for any further request); any other file-host URL gets `files` when given.
    Every request is logged in `requested`; more than `limit` fails the test, so a listing that never
    ends cannot hang it."""
    handler_order = 400  # after urllib's proxy handler (100), before its HTTP and HTTPS handlers (500)

    def __init__(self, routes, files=None, limit=100):
        self.routes = dict(routes)
        self.files = files
        self.limit = limit
        self.requests = []

    @property
    def requested(self):
        return [req.full_url for req in self.requests]

    def https_open(self, req):
        self.requests.append(req)
        url = req.full_url
        assert len(self.requests) <= self.limit, f"more than {self.limit} requests"
        route = self.routes.get(url)
        if route is None and self.files is not None and url.startswith(FILE_HOST + "/"):
            route = self.files
        if route is None:
            raise AssertionError(f"unexpected request: {url}")
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        return route(req)

    http_open = https_open


def connect(routes, files=None, limit=100):
    portal = Portal(routes, files, limit)
    return Http(UA, opener=build_opener(portal), sleep=lambda seconds: None), portal


def listing_url(cat, page):
    return f"{LISTING}?catID={cat}&storeId=0&page={page}"


def fixture(cat):
    return (FIXTURES / f"listing-cat{cat}.html").read_text(encoding="utf-8")


def pager(cat, last):
    """The pager cell page 1 shows when `last` is the last page, in the fixture's markup."""
    def link(page, label):
        return f'<a data-swhglnk="true" href="/FileObject/UpdateCategory?catID={cat}&amp;storeId=0&amp;page={page}">{label}</a>'
    numbers = " ".join(link(page, page) for page in range(2, min(last, 5) + 1))
    return f'<td colspan="8">1 {numbers} {link(2, "&gt;")} {link(last, "&gt;&gt;")}</td>'


def page(cat, names=None, last=KEEP):
    """Category `cat`'s page 1 as served; with `names`, its rows replaced by rows of those names (each
    built from the first row's markup, link and name cell alike); with `last`, its pager rewritten to
    name that last page, or removed (None)."""
    text = fixture(cat)
    if names is not None:
        template = ROW.search(text).group()
        first = NAME_CELL.search(template).group(1)
        rows = "".join(template.replace(first, name) for name in names)
        text = TBODY.sub(lambda m: m.group(1) + rows + m.group(2), text)
    if last is None:
        text = TFOOT.sub("", text)
    elif last is not KEEP:
        text = PAGER.sub(lambda m: pager(cat, last), text)
    return text


def names(page_number, count=20):
    """`count` PriceFull names for a built page, distinct per page number and from the fixture's own
    (stores 040 and up; the fixture holds 001 to 034, NAME is 030)."""
    return [f"PriceFull7290027600007-001-{(page_number + 1) * 20 + i:03d}-20261031-030000" for i in range(count)]


def take(iterator, count):
    return [next(iterator) for _ in range(count)]


def segment(url):
    return urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]


def test_pager_helper_matches_the_served_markup():
    """The pages these tests build differ from the served ones only where they mean to."""
    for cat in (1, 2, 3, 4):
        assert PAGER.search(fixture(cat)).group() == pager(cat, 22)
    assert page(2, last=22) == fixture(2)
    assert len(ROW.findall(fixture(2))) == 20


# ---- the interface ----

def test_categories():
    assert CATEGORY == {"Price": 1, "PriceFull": 2, "Promo": 3, "PromoFull": 4, "Stores": 5}


def test_base_url_is_the_chains():
    assert shufersal.BASE_URL == CHAINS["shufersal"].base_url


def test_is_a_source():
    assert Source in ShufersalSource.__mro__


# ---- paging ----

def test_listing_reads_every_page_to_the_last_one_the_pager_names():
    """docs/portals.md: page 1's `>>` names page 22; a page past the last returns the last page again,
    so reading on "until a page has no rows" would never end."""
    last_rows = names(22, count=18)
    routes = {listing_url(2, 1): served(fixture(2))}
    routes |= {listing_url(2, p): served(page(2, names(p))) for p in range(2, 22)}
    routes |= {listing_url(2, p): served(page(2, last_rows)) for p in range(22, 30)}  # past the last: the last again
    http, portal = connect(routes)
    listed = list(ShufersalSource().listing(http, ("PriceFull",)))
    assert portal.requested == [listing_url(2, p) for p in range(1, 23)]
    assert len(listed) == 20 + 20 * 20 + 18
    assert len({item.name.raw for item in listed}) == len(listed)
    assert [item.name.raw for item in listed[20:40]] == names(2)
    assert [item.name.raw for item in listed[-18:]] == last_rows


def test_listed_items_carry_the_parsed_name_and_the_absolute_link():
    http, _ = connect({listing_url(2, 1): served(fixture(2))})
    listed = take(ShufersalSource().listing(http, ("PriceFull",)), 20)
    first, store_030 = listed[0], listed[16]
    assert first.url == (f"{FILE_HOST}/pricefull/PriceFull7290027600007-001-001-20261031-030000.gz"
                         "?sv=2014-02-14&sr=b&sig=SCRUBBED&se=2026-10-31T22%3A36%3A02Z&sp=r")
    assert store_030 == Listed(parse_file_name(NAME), OLD_LINK)
    assert (store_030.name.kind, store_030.name.store, store_030.name.day.isoformat()) == ("PriceFull", "030", "2026-10-31")


@pytest.mark.parametrize("cat, kind", [(1, "Price"), (2, "PriceFull"), (3, "Promo"), (4, "PromoFull"), (5, "Stores")])
def test_listed_name_is_the_link_file_without_gz(cat, kind):
    """The run loop files each download under the link's last path segment, the name as published
    (the listing's name cell leaves `.gz` off): the two must agree."""
    http, _ = connect({listing_url(cat, 1): served(page(cat, last=None))})
    listed = list(ShufersalSource().listing(http, (kind,)))
    assert len(listed) == (1 if cat == 5 else 20)
    for item in listed:
        assert segment(item.url) == item.name.raw + ".gz"
        assert item.name.kind == kind


def test_one_page_category_has_no_pager_and_one_page_is_read():
    """docs/portals.md: Stores (one row) has no <tfoot> at all, and page 2 repeats page 1."""
    http, portal = connect({listing_url(5, 1): served(fixture(5)), listing_url(5, 2): served(fixture(5))})
    listed = list(ShufersalSource().listing(http, ("Stores",)))
    assert portal.requested == [listing_url(5, 1)]
    assert [item.name.raw for item in listed] == ["Stores7290027600007-000-20261031-020"]
    assert listed[0].url == (f"{FILE_HOST}/stores/Stores7290027600007-000-20261031-020.gz"
                             "?sv=2014-02-14&sr=b&sig=SCRUBBED&se=2026-10-31T22%3A36%3A28Z&sp=r")


@pytest.mark.parametrize("text", [
    pytest.param(page(2, names=[], last=None), id="the table with no rows and no pager"),
    pytest.param(page(2, names=[]), id="the table with no rows and a pager"),
    pytest.param("<html><body><h1>Server Error in '/' Application.</h1></body></html>", id="another page"),
    pytest.param("", id="an empty answer"),
])
def test_zero_rows_is_unreadable(text):
    """A listing with no rows means the portal changed, never "nothing published today"."""
    http, portal = connect({listing_url(2, 1): served(text)})
    with pytest.raises(ListingUnreadable, match="PriceFull page 1: no rows"):
        list(ShufersalSource().listing(http, ("PriceFull",)))
    assert portal.requested == [listing_url(2, 1)]


def test_later_page_with_no_rows_is_unreadable():
    http, _ = connect({listing_url(2, 1): served(page(2, last=3)), listing_url(2, 2): served(page(2, names=[], last=3))})
    listing = ShufersalSource().listing(http, ("PriceFull",))
    assert len(take(listing, 20)) == 20
    with pytest.raises(ListingUnreadable, match="PriceFull page 2: no rows"):
        next(listing)


@pytest.mark.parametrize("text, problem", [
    pytest.param(fixture(2).replace('page=22">&gt;&gt;</a>', 'page=22">last</a>'), "names no last page", id="no >> link"),
    pytest.param(fixture(2).replace('page=22">&gt;&gt;', 'page=xx">&gt;&gt;'), "(page=xx)", id="a page that is no number"),
    pytest.param(fixture(2).replace('&amp;page=22">&gt;&gt;', '">&gt;&gt;'), "(page=)", id="no page in the link"),
    pytest.param(fixture(2).replace('page=22">&gt;&gt;', 'page=22&amp;page=3">&gt;&gt;'), "(page=22,3)", id="two pages in the link"),
    pytest.param(fixture(2).replace('page=22">&gt;&gt;', 'page=%C2%B2">&gt;&gt;'), "(page=\u00b2)", id="a superscript digit"),
])
def test_pager_without_a_readable_last_page_is_unreadable(text, problem):
    """Only page 1's pager was observed; one that does not name its last page is not guessed at."""
    http, portal = connect({listing_url(2, 1): served(text)})
    with pytest.raises(ListingUnreadable, match="PriceFull page 1: the pager") as caught:
        next(ShufersalSource().listing(http, ("PriceFull",)))
    assert problem in str(caught.value)
    assert portal.requested == [listing_url(2, 1)]


def test_kinds_are_read_in_turn_each_from_its_own_category():
    routes = {listing_url(5, 1): served(fixture(5)), listing_url(1, 1): served(page(1, last=None)),
              listing_url(2, 1): served(page(2, last=None))}
    http, portal = connect(routes)
    listed = list(ShufersalSource().listing(http, ("Stores", "Price", "PriceFull")))
    assert portal.requested == [listing_url(5, 1), listing_url(1, 1), listing_url(2, 1)]
    assert [item.name.kind for item in listed] == ["Stores"] + ["Price"] * 20 + ["PriceFull"] * 20


def test_rows_of_another_kind_are_not_listed():
    """Source.listing lists the kinds asked for: a Price file on the PriceFull pages is left out."""
    price = "Price7290027600007-001-001-20261031-020000"
    http, _ = connect({listing_url(2, 1): served(page(2, [price, NAME], last=None))})
    assert [item.name.raw for item in ShufersalSource().listing(http, ("PriceFull",))] == [NAME]


def test_names_that_do_not_parse_are_skipped_and_counted():
    routes = {listing_url(5, 1): served(page(5, ["index", "Stores-not-a-name"], last=None)),
              listing_url(2, 1): served(page(2, ["PriceFull7290027600007-001-001-20261399-030000", NAME], last=None))}
    http, _ = connect(routes)
    source = ShufersalSource()
    assert source.unparsed == 0
    listed = list(source.listing(http, ("Stores", "PriceFull")))
    assert [item.name.raw for item in listed] == [NAME]
    assert source.unparsed == 3  # counted across the kinds of one listing


def test_unparsed_count_starts_again_with_each_listing():
    http, _ = connect({listing_url(5, 1): [served(page(5, ["index"], last=None)), served(fixture(5))]})
    source = ShufersalSource()
    list(source.listing(http, ("Stores",)))
    assert source.unparsed == 1
    list(source.listing(http, ("Stores",)))
    assert source.unparsed == 0


def test_row_without_eight_cells_is_unreadable():
    """The name is the seventh of eight cells; a row of another shape means the table changed."""
    text = fixture(5).replace("            <td>All</td>\n", "")
    http, _ = connect({listing_url(5, 1): served(text)})
    with pytest.raises(ListingUnreadable, match="Stores page 1, row 1: 7 cells, not 8"):
        list(ShufersalSource().listing(http, ("Stores",)))


# ---- one page at a time ----

def test_listing_reads_each_page_only_after_the_previous_pages_rows_are_taken():
    """Signed links expire 30 minutes after their page is served, so the run loop downloads a page's
    files before the next page is read."""
    routes = {listing_url(2, 1): served(page(2, last=2)), listing_url(2, 2): served(page(2, names(2, count=3), last=2))}
    http, portal = connect(routes, files=gz())
    source = ShufersalSource()
    listing = source.listing(http, ("PriceFull",))
    assert portal.requested == []
    item = next(listing)
    assert portal.requested == [listing_url(2, 1)]
    downloaded = []
    while item is not None:
        assert source.download(http, item) == GZ
        downloaded.append(item.url)
        item = next(listing, None)
    first_page, second_page = downloaded[:20], downloaded[20:]
    assert len(second_page) == 3
    assert portal.requested == [listing_url(2, 1), *first_page, listing_url(2, 2), *second_page]


# ---- the record of each page read ----

NAME_THAT_DOES_NOT_PARSE = "index"
PRICE_NAME = "Price7290027600007-001-001-20261031-020000"  # a Price file on a PriceFull page: another kind


def ticks(step):
    """The adapter's timer in a test: each call `step` seconds after the one before, from 0."""
    calls = itertools.count()
    return lambda: next(calls) * step


def recorded(routes, kinds=("PriceFull",)):
    """The items a listing over `routes` gives, read to its end, and the pages it reports."""
    http, _ = connect(routes)
    reads = []
    listed = list(ShufersalSource(timer=ticks(41.2)).listing(http, kinds, on_page=reads.append))
    return listed, reads


def test_each_page_read_is_reported_before_its_rows_are_given():
    """The run loop records how far into each page it got, so a page's record comes before its first row."""
    http, _ = connect({listing_url(2, p): served(page(2, names(p), last=3)) for p in (1, 2, 3)})
    events, reads = [], []

    def on_page(read):
        reads.append(read)
        events.append(("page", read.page))

    for item in ShufersalSource(timer=ticks(41.2)).listing(http, ("PriceFull",), on_page=on_page):
        events.append(item.name.raw)
    assert events == [("page", 1), *names(1), ("page", 2), *names(2), ("page", 3), *names(3)]
    assert reads[0] == PageRead("PriceFull", 1, 20, names(1)[0], names(1)[-1], 3, 41.2, True)


def test_a_page_without_a_pager_records_no_last_page():
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)), listing_url(2, 2): served(page(2, names(2), last=None)),
              listing_url(2, 3): served(page(2, names(3), last=3))}
    listed, reads = recorded(routes)
    assert reads[1].last_page is None
    assert [read.page for read in reads] == [1, 2, 3]
    assert len(listed) == 60


@pytest.mark.parametrize("old, new", [
    pytest.param('page=3">&gt;&gt;</a>', 'page=3">last</a>', id="no >> link"),
    pytest.param('page=3">&gt;&gt;', 'page=xx">&gt;&gt;', id="a page that is no number"),
])
def test_a_later_pager_without_a_readable_last_page_is_recorded_not_refused(old, new):
    """Only page 1's pager has been seen (docs/portals.md), and only page 1's sets how far the listing reads: a later
    page's is recorded as it reads, never a stop."""
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)),
              listing_url(2, 2): served(page(2, names(2), last=3).replace(old, new)),
              listing_url(2, 3): served(page(2, names(3), last=3))}
    listed, reads = recorded(routes)
    assert [read.last_page for read in reads] == [3, None, 3]
    assert len(listed) == 60


def test_one_page_category_records_no_last_page():
    """Stores fits on one page and has no pager: a list of one page, as the adapter reads it."""
    _, reads = recorded({listing_url(5, 1): served(fixture(5))}, kinds=("Stores",))
    name = "Stores7290027600007-000-20261031-020"
    assert reads == [PageRead("Stores", 1, 1, name, name, None, 41.2, True)]


def test_the_last_row_given_from_each_page_ends_it():
    """A page's last rows may not parse or be of another kind; the last row the listing gives from the page still
    ends it, so a run that took it took every row the page gives."""
    routes = {listing_url(2, 1): served(page(2, [*names(1)[:18], NAME_THAT_DOES_NOT_PARSE, PRICE_NAME], last=2)),
              listing_url(2, 2): served(page(2, names(2), last=2))}
    listed, _ = recorded(routes)
    assert [item.name.raw for item in listed] == names(1)[:18] + names(2)
    assert [item.ends_page for item in listed] == [False] * 17 + [True] + [False] * 19 + [True]


def test_a_page_out_of_order_is_recorded_and_the_listing_goes_on():
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)), listing_url(2, 2): served(page(2, names(2)[::-1], last=3)),
              listing_url(2, 3): served(page(2, names(3), last=3))}
    listed, reads = recorded(routes)
    assert [read.in_order for read in reads] == [True, False, True]
    assert len(listed) == 60


def test_a_page_starting_before_the_last_name_of_the_page_before_is_out_of_order():
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)), listing_url(2, 2): served(page(2, names(2), last=3)),
              listing_url(2, 3): served(page(2, names(1), last=3))}
    _, reads = recorded(routes)
    assert [read.in_order for read in reads] == [True, True, False]


def test_a_name_repeated_across_a_page_boundary_is_in_order():
    """The list can move on by a row between two page reads: the next page then begins with the last name read."""
    routes = {listing_url(2, 1): served(page(2, names(1), last=2)),
              listing_url(2, 2): served(page(2, [names(1)[-1], *names(2)[1:]], last=2))}
    _, reads = recorded(routes)
    assert [read.in_order for read in reads] == [True, True]


def test_a_page_that_fails_its_checks_is_not_reported():
    routes = {listing_url(2, 1): served(page(2, names(1), last=2)),
              listing_url(2, 2): served(page(2, names(2), last=2).replace("pricesprodpublic.blob.core.windows.net",
                                                                         "files.example.org"))}
    http, _ = connect(routes)
    reads = []
    listing = ShufersalSource(timer=ticks(41.2)).listing(http, ("PriceFull",), on_page=reads.append)
    with pytest.raises(ListingUnreadable, match="PriceFull page 2, row 1: the download link is on https://files.example.org"):
        list(listing)
    assert [read.page for read in reads] == [1]


def test_a_listing_with_no_callback_reads_as_before():
    routes = {listing_url(2, p): served(page(2, names(p), last=3)) for p in (1, 2, 3)}
    http, _ = connect(routes)
    without = [item.name.raw for item in ShufersalSource().listing(http, ("PriceFull",))]
    with_one, _ = recorded(routes)
    assert without == [item.name.raw for item in with_one] == names(1) + names(2) + names(3)


# ---- where each kind starts ----

def listing_pages(portal):
    """The `page=` numbers of the listing requests `portal` answered, in order."""
    return [int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["page"][0])
            for url in portal.requested if url.startswith(LISTING)]


def twenty_one_pages(cat=2, named=names):
    """Category `cat`'s 21 pages, each of its own 20 names (`named(p)`), every pager naming page 21."""
    return {listing_url(cat, p): served(page(cat, named(p), last=21)) for p in range(1, 22)}


def promo_names(page_number):
    return [name.replace("PriceFull", "PromoFull") for name in names(page_number)]


def pages_of(*numbers):
    """The names of `numbers`' pages, in that order."""
    return [name for number in numbers for name in names(number)]


def started(start, routes=None):
    """A PriceFull listing from `start` over `routes` (the 21 pages by default), read to its end: the names it gives,
    the pages it reports and the portal."""
    http, portal = connect(routes or twenty_one_pages())
    reads = []
    listed = ShufersalSource(timer=ticks(41.2)).listing(http, ("PriceFull",), starts={"PriceFull": start},
                                                        on_page=reads.append)
    return [item.name.raw for item in listed], reads, portal


def test_a_fresh_pass_reads_page_1_to_the_last():
    given, reads, portal = started(Start())
    assert listing_pages(portal) == list(range(1, 22))
    assert [read.page for read in reads] == list(range(1, 22))
    assert given == pages_of(*range(1, 22))


def test_a_resumed_kind_reads_page_1_then_the_resume_page_again_and_on():
    """Page 1 first, since only its pager is known to name the last page; then the furthest page an earlier run read,
    again: one page of overlap, so a file whose download that run never reached gets a fresh link
    (docs/shufersal-resume.md, section 2)."""
    given, reads, portal = started(Start(page=12, furthest=names(12)[0]))
    assert listing_pages(portal) == [1, *range(12, 22)]
    assert [read.page for read in reads] == [1, *range(12, 22)]
    assert given == names(1) + pages_of(*range(12, 22))


def test_detours_come_first_once_each():
    """A file that failed on an earlier page is tried again by reading its page once, before page 1: a detour, not a
    restart there, so a file that fails every time cannot pull every later run back to its page."""
    given, _, portal = started(Start(page=12, furthest=names(12)[0], detours=(5, 7)))
    assert listing_pages(portal) == [5, 7, 1, *range(12, 22)]
    assert given == names(5) + names(7) + names(1) + pages_of(*range(12, 22))


def test_a_fresh_pass_with_a_detour_reads_it_before_page_1():
    given, _, portal = started(Start(detours=(5,)))
    assert listing_pages(portal) == [5, *range(1, 22)]
    assert given == names(5) + pages_of(*range(1, 22))


def test_a_shifted_list_steps_back_until_the_first_name_is_not_after_the_furthest():
    """Files that sorted before the furthest name taken left the list since the earlier run, so that name now sits on an
    earlier page: the resume page begins past it, and the names between are on the pages before it. The run steps back
    a page at a time, reporting each page it steps back over without giving its rows, and gives them when the reading
    reaches the page again, with fresh links."""
    given, reads, portal = started(Start(page=12, furthest=names(10)[5]))
    assert listing_pages(portal) == [1, 12, 11, 10, *range(11, 22)]
    assert given[:60] == names(1) + names(10) + names(11)
    assert given == names(1) + pages_of(*range(10, 22))
    assert [r.page for r in reads][:4] == [1, 12, 11, 10]
    assert [r.page for r in reads] == [1, 12, 11, 10, *range(11, 22)]


def test_no_step_back_when_the_first_name_is_the_furthest():
    _, _, portal = started(Start(page=12, furthest=names(12)[0]))
    assert 11 not in listing_pages(portal)


def test_the_step_back_stops_at_page_2():
    """Page 1 is read first anyway, so the step back never reads it again."""
    given, _, portal = started(Start(page=4, furthest=names(1)[5]))
    assert listing_pages(portal) == [1, 4, 3, 2, *range(3, 22)]
    assert given == pages_of(*range(1, 22))


def test_a_resume_page_past_the_last_starts_at_the_last():
    """The list shrank since the earlier run: page 1's pager names 21, and page 22 would serve page 21 again
    (docs/portals.md), so the run starts at page 21 and never asks for page 22."""
    routes = twenty_one_pages() | {listing_url(2, 22): served(page(2, names(21), last=21))}
    given, _, portal = started(Start(page=22, furthest=names(21)[3]), routes)
    assert listing_pages(portal) == [1, 21]
    assert given == names(1) + names(21)


def test_a_resume_on_a_one_page_list_reads_page_1_only():
    """A page past the last serves the last page again: on a list of one page, page 12 is page 1 again."""
    one_page = served(page(2, names(1), last=None))
    given, reads, portal = started(Start(page=12, furthest=names(12)[0]),
                                   {listing_url(2, 1): one_page, listing_url(2, 12): one_page})
    assert listing_pages(portal) == [1]
    assert [read.page for read in reads] == [1]
    assert given == names(1)


def test_pages_read_out_of_number_order_are_not_compared():
    """A page's first name is compared with the last of the page read just before it only when that page is numbered
    one less: a detour, page 1 after it and a step back read pages out of number order, which says nothing about the
    list's order."""
    _, reads, _ = started(Start(page=12, furthest=names(10)[5], detours=(5,)))
    assert [read.page for read in reads] == [5, 1, 12, 11, 10, *range(11, 22)]
    assert all(read.in_order for read in reads)


def test_each_kind_starts_at_its_own_point():
    http, portal = connect(twenty_one_pages() | twenty_one_pages(cat=4, named=promo_names))
    starts = {"PromoFull": Start(page=12, furthest=promo_names(12)[0])}
    listed = list(ShufersalSource().listing(http, ("PriceFull", "PromoFull"), starts=starts))
    assert portal.requested == [listing_url(2, p) for p in range(1, 22)] + [listing_url(4, p) for p in (1, *range(12, 22))]
    assert [item.name.raw for item in listed] == pages_of(*range(1, 22)) + [
        name for p in (1, *range(12, 22)) for name in promo_names(p)]


@pytest.mark.parametrize("start, short_from, stopped, requested", [
    pytest.param(Start(page=12, furthest=names(10)[5]), 3, 11, [1, 12], id="a step back"),
    pytest.param(Start(page=12, furthest=names(12)[0], detours=(5,)), 1, 5, [], id="a detour"),
])
def test_the_time_is_asked_before_detours_and_steps_back(start, short_from, stopped, requested):
    """Every page read asks the run's time check first, wherever the reading order puts it."""
    http, portal = connect(twenty_one_pages())
    listing = ShufersalSource().listing(http, ("PriceFull",), ShortFrom(short_from), starts={"PriceFull": start})
    with pytest.raises(OutOfTime, match=rf"^before page {stopped} of the PriceFull listing$"):
        list(listing)
    assert listing_pages(portal) == requested


# ---- links checked before anything is fetched ----

STORES_LINK = ("https://pricesprodpublic.blob.core.windows.net/stores/Stores7290027600007-000-20261031-020.gz"
               "?sv=2014-02-14&amp;sr=b&amp;sig=SCRUBBED&amp;se=2026-10-31T22%3A36%3A28Z&amp;sp=r")


@pytest.mark.parametrize("link, problem", [
    pytest.param(STORES_LINK.replace("https://", "http://"), "on http://pricesprodpublic", id="http"),
    pytest.param(STORES_LINK.replace("pricesprodpublic.blob.core.windows.net", "files.example.org"), "on https://files.example.org", id="another host"),
    pytest.param(STORES_LINK.replace(".windows.net/", ".windows.net:8443/"), "windows.net:8443", id="another port"),
    pytest.param(STORES_LINK.replace("https://", "https://user@"), "on https://user@", id="a user in the link"),
    pytest.param(STORES_LINK.replace("https://pricesprodpublic.blob.core.windows.net", ""), "on a relative path", id="relative"),
    pytest.param(STORES_LINK.replace("https://", "javascript:"), "on javascript:", id="javascript:"),
    pytest.param(STORES_LINK.replace("sv=2014", "sv=2014 02"), "malformed", id="a space"),
    pytest.param(STORES_LINK.replace("sv=2014", "sv=2014&#10;"), "malformed", id="a line break"),
    pytest.param(STORES_LINK.replace("sv=2014", "sv=2014é"), "malformed", id="outside ASCII"),
    pytest.param(STORES_LINK.replace("https://pricesprodpublic", "https://[pricesprodpublic"), "malformed", id="unsplittable"),
    pytest.param(STORES_LINK.replace("-020.gz", "-021.gz"), "Stores7290027600007-000-20261031-021.gz", id="another file's link"),
    pytest.param(STORES_LINK.replace("-020.gz", "-020"), "Stores7290027600007-000-20261031-020,", id="the link without .gz"),
])
def test_link_off_the_file_host_or_malformed_is_unreadable_and_never_fetched(link, problem):
    """Every link must be https on pricesprodpublic.blob.core.windows.net and name its row's file; any
    other means the portal changed. A malformed link would escape Http as urllib's ValueError."""
    http, portal = connect({listing_url(5, 1): served(fixture(5).replace(STORES_LINK, link))}, files=gz())
    with pytest.raises(ListingUnreadable, match="Stores page 1, row 1: the download link") as caught:
        list(ShufersalSource().listing(http, ("Stores",)))
    assert problem in str(caught.value)
    assert "sig=" not in str(caught.value)
    assert portal.requested == [listing_url(5, 1)]


def test_row_without_a_link_is_unreadable():
    text = fixture(5).replace(f'<a href="{STORES_LINK}" target="_blank">', '<a target="_blank">')
    http, _ = connect({listing_url(5, 1): served(text)})
    with pytest.raises(ListingUnreadable, match="Stores page 1, row 1: no download link"):
        list(ShufersalSource().listing(http, ("Stores",)))


def test_bad_link_on_a_row_whose_name_does_not_parse_is_still_unreadable():
    text = page(5, ["index"], last=None).replace("pricesprodpublic.blob.core.windows.net", "files.example.org")
    http, _ = connect({listing_url(5, 1): served(text)})
    with pytest.raises(ListingUnreadable, match="files.example.org"):
        list(ShufersalSource().listing(http, ("Stores",)))


def test_bad_link_anywhere_on_a_page_stops_it_before_its_first_row():
    text = page(2, last=None).replace(f"pricesprodpublic.blob.core.windows.net/pricefull/{NAME}",
                                      f"files.example.org/pricefull/{NAME}")
    http, portal = connect({listing_url(2, 1): served(text)}, files=gz())
    with pytest.raises(ListingUnreadable, match="PriceFull page 1, row 17"):
        next(ShufersalSource().listing(http, ("PriceFull",)))
    assert portal.requested == [listing_url(2, 1)]


# ---- cookies ----

def test_listing_host_cookies_are_not_sent_to_the_file_host():
    """docs/portals.md: the listing host sets ARRAffinity cookies; they belong to that host alone."""
    affinity = [("Set-Cookie", "ARRAffinity=0123abcd;Path=/;HttpOnly;Domain=prices.shufersal.co.il"),
                ("Set-Cookie", "ARRAffinitySameSite=0123abcd;Path=/;HttpOnly;SameSite=None;Secure;Domain=prices.shufersal.co.il")]
    http, portal = connect({listing_url(5, 1): served(fixture(5), headers=affinity)}, files=gz())
    source = ShufersalSource()
    (item,) = source.listing(http, ("Stores",))
    source.download(http, item)
    list(source.listing(http, ("Stores",)))
    first_listing, download, second_listing = portal.requests
    assert download.host == "pricesprodpublic.blob.core.windows.net"
    assert download.get_header("Cookie") is None
    assert first_listing.get_header("Cookie") is None
    assert "ARRAffinity=0123abcd" in second_listing.get_header("Cookie")  # the jar keeps them for their host


# ---- downloads and expired links ----

def item_030():
    return Listed(parse_file_name(NAME), OLD_LINK)


def test_download_returns_the_body_as_received():
    http, portal = connect({OLD_LINK: gz()})
    assert ShufersalSource().download(http, item_030()) == GZ
    assert portal.requested == [OLD_LINK]


@pytest.mark.parametrize("now", [
    pytest.param(SE - timedelta(seconds=120), id="two minutes before se=, the slack's edge"),
    pytest.param(SE - timedelta(seconds=119), id="119 s before se="),
    pytest.param(SE, id="at se="),
    pytest.param(SE + timedelta(seconds=1), id="a second after"),
    pytest.param(SE + timedelta(hours=3), id="hours after"),
    pytest.param(datetime(2026, 11, 1, 0, 36, 2, tzinfo=ZoneInfo("Asia/Jerusalem")), id="at se=, on an Israel clock"),
    pytest.param(datetime(2026, 11, 1, 0, 34, 3, tzinfo=ZoneInfo("Asia/Jerusalem")), id="119 s before, on an Israel clock"),
])
def test_expired_link_refreshes(now):
    """A 403 from the file host from two minutes before the link's se= on is the link expiring, not
    a block (ruling R17: the slack covers Azure's clock running ahead of ours): the category is read
    again from page 1 and the fresh link is downloaded once."""
    routes = {listing_url(2, 1): [served(fixture(2)), served(fixture(2).replace(OLD_SIGNATURE, FRESH_SIGNATURE))],
              OLD_LINK: refused(), FRESH_LINK: gz()}
    http, portal = connect(routes)
    source = ShufersalSource(now=lambda: now)
    item = next(item for item in source.listing(http, ("PriceFull",)) if item.name.raw == NAME)
    assert source.download(http, item) == GZ
    # page 1 lists it, so the re-read stops there
    assert portal.requested == [listing_url(2, 1), OLD_LINK, listing_url(2, 1), FRESH_LINK]


def test_refresh_reads_on_to_the_page_that_lists_the_file_and_no_further():
    routes = {listing_url(2, 1): served(page(2, names(1), last=4)), listing_url(2, 2): served(page(2, names(2), last=4)),
              listing_url(2, 3): served(page(2, [NAME], last=4).replace(OLD_SIGNATURE, FRESH_SIGNATURE)),
              OLD_LINK: refused(), FRESH_LINK: gz()}
    http, portal = connect(routes)
    assert ShufersalSource(now=lambda: SE).download(http, item_030()) == GZ
    assert portal.requested == [OLD_LINK, listing_url(2, 1), listing_url(2, 2), listing_url(2, 3), FRESH_LINK]


def test_expired_link_no_longer_listed_is_an_http_error():
    """Gone from the listing (a newer file replaced it): a transient miss the retry run handles."""
    routes = {listing_url(2, p): served(page(2, names(p), last=3)) for p in range(1, 5)} | {OLD_LINK: refused()}
    http, portal = connect(routes)
    with pytest.raises(HttpError, match=f"{NAME}: its link expired and the PriceFull listing no longer lists it"):
        ShufersalSource(now=lambda: SE).download(http, item_030())
    assert portal.requested == [OLD_LINK, listing_url(2, 1), listing_url(2, 2), listing_url(2, 3)]


def test_refreshed_link_is_downloaded_once():
    routes = {listing_url(2, 1): served(fixture(2).replace(OLD_SIGNATURE, FRESH_SIGNATURE)),
              OLD_LINK: refused(), FRESH_LINK: refused()}
    http, portal = connect(routes)
    with pytest.raises(Blocked) as caught:
        ShufersalSource(now=lambda: SE + timedelta(hours=1)).download(http, item_030())
    assert (caught.value.status, caught.value.url) == (403, FRESH_LINK)
    assert portal.requested == [OLD_LINK, listing_url(2, 1), FRESH_LINK]


class ShortFrom:
    """The run's time check, as the run loop lends it: short of time from its `n`th call on (counted from 1)."""

    def __init__(self, n):
        self.n, self.calls = n, 0

    def __call__(self):
        self.calls += 1
        return self.calls >= self.n


def test_the_refresh_stops_before_a_page_when_the_run_is_short_of_time():
    """The refresh reads the category again from page 1 on its own, at up to 39 s a page from il-central-1,
    so one begun late could outlast Lambda's 900 s, and a run Lambda kills writes no manifest. It asks the run's time
    check before each page it reads and stops with OutOfTime, naming the file and the page it did not read."""
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)), listing_url(2, 2): served(page(2, names(2), last=3)),
              listing_url(2, 3): served(page(2, [NAME], last=3).replace(OLD_SIGNATURE, FRESH_SIGNATURE)),
              OLD_LINK: refused(), FRESH_LINK: gz()}
    http, portal = connect(routes)
    with pytest.raises(OutOfTime) as caught:
        ShufersalSource(now=lambda: SE).download(http, item_030(), ShortFrom(2))
    assert str(caught.value) == f"{NAME}: its link expired; stopped before page 2 of the PriceFull listing"
    assert portal.requested == [OLD_LINK, listing_url(2, 1)]


def test_the_refresh_reads_no_page_when_the_run_is_already_short_of_time():
    http, portal = connect({OLD_LINK: refused(), listing_url(2, 1): served(fixture(2))})
    with pytest.raises(OutOfTime) as caught:
        ShufersalSource(now=lambda: SE).download(http, item_030(), ShortFrom(1))
    assert str(caught.value) == f"{NAME}: its link expired; stopped before page 1 of the PriceFull listing"
    assert portal.requested == [OLD_LINK]


def test_the_fresh_link_is_not_fetched_when_the_refresh_leaves_the_run_short_of_time():
    routes = {listing_url(2, 1): served(fixture(2).replace(OLD_SIGNATURE, FRESH_SIGNATURE)),
              OLD_LINK: refused(), FRESH_LINK: gz()}
    http, portal = connect(routes)
    with pytest.raises(OutOfTime) as caught:
        ShufersalSource(now=lambda: SE).download(http, item_030(), ShortFrom(2))
    assert str(caught.value) == f"{NAME}: its link expired; stopped before the fresh link's download"
    assert portal.requested == [OLD_LINK, listing_url(2, 1)]


def test_a_link_that_has_not_expired_never_asks_the_time():
    """Only the refresh makes requests of its own; a plain download is one request, after the run's own check."""
    http, _ = connect({OLD_LINK: gz()})
    check = ShortFrom(1)
    assert ShufersalSource().download(http, item_030(), check) == GZ
    assert check.calls == 0


def test_the_listing_asks_the_time_before_each_page():
    """The run loop checks between items too; asked before each page as well, a listing never begins a page short of
    time, and stops with OutOfTime."""
    routes = {listing_url(2, p): served(page(2, names(p), last=3)) for p in (1, 2, 3)}
    http, portal = connect(routes)
    listing = ShufersalSource().listing(http, ("PriceFull",), ShortFrom(2))
    assert len(take(listing, 20)) == 20
    with pytest.raises(OutOfTime, match=r"^before page 2 of the PriceFull listing$"):
        next(listing)
    assert portal.requested == [listing_url(2, 1)]


@pytest.mark.parametrize("now", [
    pytest.param(SE - timedelta(seconds=121), id="121 s before se="),
    pytest.param(SE - timedelta(minutes=29), id="just after the listing"),
    pytest.param(datetime(2026, 11, 1, 0, 34, 1, tzinfo=ZoneInfo("Asia/Jerusalem")), id="121 s before, on an Israel clock"),
])
def test_403_before_expiry_blocks(now):
    """More than the two minutes' slack before se=, a 403 is a refusal, not expiry."""
    http, portal = connect({OLD_LINK: refused(), listing_url(2, 1): served(fixture(2))})
    with pytest.raises(Blocked) as caught:
        ShufersalSource(now=lambda: now).download(http, item_030())
    assert (caught.value.status, caught.value.url) == (403, OLD_LINK)
    assert portal.requested == [OLD_LINK]


@pytest.mark.parametrize("answer", [
    pytest.param(refused(401), id="401"),
    pytest.param(refused(429), id="429"),
    pytest.param(reply(body=b"<html><div class='g-recaptcha'></div></html>"), id="a captcha page"),
])
def test_other_refusals_from_the_file_host_block_even_after_expiry(answer):
    http, portal = connect({OLD_LINK: answer, listing_url(2, 1): served(fixture(2))})
    with pytest.raises(Blocked):
        ShufersalSource(now=lambda: SE + timedelta(hours=1)).download(http, item_030())
    assert portal.requested == [OLD_LINK]


@pytest.mark.parametrize("link", [
    pytest.param(OLD_LINK.replace("&se=2026-10-31T22%3A36%3A02Z", ""), id="no se="),
    pytest.param(OLD_LINK.replace("se=2026-10-31T22%3A36%3A02Z", "se=yesterday"), id="se= unreadable"),
    pytest.param(OLD_LINK.replace("https://pricesprodpublic.blob.core.windows.net", "https://prices.shufersal.co.il"), id="another host"),
    pytest.param(OLD_LINK.replace("https://", "http://"), id="http"),
])
def test_403_without_a_file_host_expiry_blocks(link):
    http, portal = connect({link: refused(), listing_url(2, 1): served(fixture(2))})
    with pytest.raises(Blocked):
        ShufersalSource(now=lambda: SE + timedelta(hours=1)).download(http, Listed(parse_file_name(NAME), link))
    assert portal.requested == [link]


def test_403_from_the_listing_host_blocks():
    http, portal = connect({listing_url(2, 1): refused()})
    with pytest.raises(Blocked) as caught:
        list(ShufersalSource(now=lambda: SE + timedelta(hours=1)).listing(http, ("PriceFull",)))
    assert (caught.value.status, caught.value.url) == (403, listing_url(2, 1))
    assert portal.requested == [listing_url(2, 1)]


def test_403_from_the_listing_host_during_a_refresh_blocks():
    http, portal = connect({OLD_LINK: refused(), listing_url(2, 1): refused()})
    with pytest.raises(Blocked) as caught:
        ShufersalSource(now=lambda: SE + timedelta(hours=1)).download(http, item_030())
    assert caught.value.url == listing_url(2, 1)
    assert portal.requested == [OLD_LINK, listing_url(2, 1)]


def test_unreadable_listing_during_a_refresh_is_unreadable():
    http, _ = connect({OLD_LINK: refused(), listing_url(2, 1): served(page(2, names=[]))})
    with pytest.raises(ListingUnreadable, match="PriceFull page 1: no rows"):
        ShufersalSource(now=lambda: SE).download(http, item_030())


@pytest.mark.parametrize("se, refreshes", [("2000-01-01T00%3A00%3A00Z", True), ("2999-01-01T00%3A00%3A00Z", False)])
def test_default_clock_is_the_utc_now(se, refreshes):
    link = OLD_LINK.replace("se=2026-10-31T22%3A36%3A02Z", f"se={se}")
    http, portal = connect({link: refused(), listing_url(2, 1): served(fixture(2).replace(OLD_SIGNATURE, FRESH_SIGNATURE)),
                            FRESH_LINK: gz()})
    source = ShufersalSource()
    if refreshes:
        assert source.download(http, Listed(parse_file_name(NAME), link)) == GZ
    else:
        with pytest.raises(Blocked):
            source.download(http, Listed(parse_file_name(NAME), link))
    assert len(portal.requested) == (3 if refreshes else 1)


# ---- a listing page that times out is asked again (q24) ----

SERVER_ERROR = b"<html><body><h1>500 - Internal server error.</h1></body></html>"
WARNINGS = "collector.sources.shufersal"  # the logger each failed try is logged on


def timed_out(req):
    """A request for a listing page whose answer passes the socket wait, as the ssl module raises it."""
    raise TimeoutError("The read operation timed out")


def readings(*values):
    """The adapter's timer in a test: `values`, one a call, in turn; a reading past the last fails the test."""
    left = list(values)

    def read():
        assert left, "the timer was read more often than the test expects"
        return left.pop(0)
    return read


def tried(routes, timer, kinds=("PriceFull",), start=None, report_timeouts=True):
    """A listing over `routes` read to its end, its pauses recorded (`sleep=sleeps.append`): the names it gives, the
    pages (`on_page`) and the timed-out tries (`on_timeout`, unless `report_timeouts` is False) it reports, the pauses
    and the portal."""
    http, portal = connect(routes)
    reads, timeouts, sleeps = [], [], []
    source = ShufersalSource(timer=timer, sleep=sleeps.append)
    callbacks = {"on_page": reads.append} | ({"on_timeout": timeouts.append} if report_timeouts else {})
    listing = source.listing(http, kinds, starts=None if start is None else {kinds[0]: start}, **callbacks)
    given = [item.name.raw for item in listing]
    return types.SimpleNamespace(given=given, reads=reads, timeouts=timeouts, sleeps=sleeps, portal=portal)


def warnings_logged(caplog):
    return [(record.getMessage(), record.levelno) for record in caplog.records if record.name == WARNINGS]


def test_a_timed_out_page_is_asked_again_and_its_rows_given():
    """The page's record holds the successful request's seconds alone (70.5 to 112.0), not the failed try's or the
    pause's, and says it took two requests."""
    run = tried({listing_url(2, 1): [timed_out, served(page(2, names(1), last=None))]},
                readings(0.0, 60.5, 70.5, 112.0))
    assert run.given == names(1)
    assert run.reads == [PageRead("PriceFull", 1, 20, names(1)[0], names(1)[-1], None, 41.5, True, tries=2)]
    assert run.timeouts == [PageTimeout("PriceFull", 1, 1, 60.5)]
    assert run.sleeps == [10.0]
    assert run.portal.requested == [listing_url(2, 1)] * 2


def test_page_1_read_on_a_later_try_still_sets_the_last_page():
    """Page 1's pager names the last page; when page 1 times out the listing does not know it yet, and the try that is
    served still sets how far the listing reads."""
    routes = {listing_url(2, 1): [timed_out, served(page(2, names(1), last=3))]}
    routes |= {listing_url(2, p): served(page(2, names(p), last=3)) for p in (2, 3)}
    run = tried(routes, ticks(41.2))
    assert listing_pages(run.portal) == [1, 1, 2, 3]
    assert run.given == names(1) + names(2) + names(3)
    assert [read.tries for read in run.reads] == [2, 1, 1]


def test_a_page_read_on_its_third_try():
    run = tried({listing_url(2, 1): [timed_out, timed_out, served(page(2, names(1), last=None))]},
                readings(0.0, 60.5, 70.5, 131.0, 141.0, 175.2))
    assert [(read.tries, read.seconds) for read in run.reads] == [(3, 34.2)]
    assert run.timeouts == [PageTimeout("PriceFull", 1, 1, 60.5), PageTimeout("PriceFull", 1, 2, 60.5)]
    assert run.sleeps == [10.0, 10.0]
    assert run.portal.requested == [listing_url(2, 1)] * 3


def test_a_page_read_on_its_first_try_records_one_try():
    run = tried({listing_url(2, 1): served(page(2, names(1), last=None))}, readings(0.0, 41.2))
    assert [(read.tries, read.seconds) for read in run.reads] == [(1, 41.2)]
    assert (run.timeouts, run.sleeps) == ([], [])


def test_three_timeouts_raise_an_http_error_naming_the_page_and_the_tries():
    """A slow spell: every try of page 2 times out. Three requests 10 s apart, no fourth and no pause after the last,
    no record for page 2, and an HttpError that names the page and the tries, chained from the last try's timeout."""
    routes = {listing_url(2, 1): served(page(2, names(1), last=3)), listing_url(2, 2): [timed_out],
              listing_url(2, 3): served(page(2, names(3), last=3))}
    http, portal = connect(routes)
    reads, timeouts, sleeps = [], [], []
    listing = ShufersalSource(timer=ticks(60.5), sleep=sleeps.append).listing(
        http, ("PriceFull",), on_page=reads.append, on_timeout=timeouts.append)
    assert [item.name.raw for item in take(listing, 20)] == names(1)
    with pytest.raises(HttpError) as caught:
        next(listing)
    assert str(caught.value) == f"PriceFull page 2 timed out on 3 tries: GET {LISTING} failed: The read operation timed out"
    assert isinstance(caught.value.__cause__, HttpTimeout)
    assert [read.page for read in reads] == [1]
    assert [(timeout.page, timeout.attempt) for timeout in timeouts] == [(2, 1), (2, 2), (2, 3)]
    assert sleeps == [10.0, 10.0]
    assert listing_pages(portal) == [1, 2, 2, 2]


def test_a_later_try_checks_the_time_before_its_pause_and_again_before_its_request():
    """No pause is taken without time to spare, and every request still starts with the run's time check passed: the
    first try checks, then sends; a later try checks, pauses, checks again, then sends."""
    events = []

    def answered(route):
        def respond(req):
            events.append("request")
            return route(req)
        return respond

    def check():
        events.append("check")
        return False

    http, _ = connect({listing_url(5, 1): [answered(timed_out), answered(timed_out), answered(served(fixture(5)))]})
    source = ShufersalSource(timer=ticks(1.0), sleep=lambda seconds: events.append(("sleep", seconds)))
    assert len(list(source.listing(http, ("Stores",), check))) == 1
    assert events == ["check", "request", "check", ("sleep", 10.0), "check", "request",
                      "check", ("sleep", 10.0), "check", "request"]


@pytest.mark.parametrize("n", [2, 3])
def test_out_of_time_after_the_pause_sends_no_further_try(n):
    """The pause can leave the run short of time: the check after it stops the listing before try `n`, with OutOfTime
    naming the page and the try, and the try that timed out before it is still reported."""
    left, pauses, timeouts = [95.0], [], []

    def sleep(seconds):
        pauses.append(seconds)
        if len(pauses) == n - 1:
            left[0] = 85.0

    http, portal = connect({listing_url(2, 1): [timed_out]})
    listing = ShufersalSource(timer=ticks(60.5), sleep=sleep).listing(http, ("PriceFull",), lambda: left[0] < 90.0,
                                                                      on_timeout=timeouts.append)
    with pytest.raises(OutOfTime) as caught:
        list(listing)
    assert str(caught.value) == f"before try {n} of page 1 of the PriceFull listing"
    assert len(portal.requested) == n - 1
    assert len(timeouts) == n - 1
    assert pauses == [10.0] * (n - 1)


def test_a_run_short_of_time_after_a_timed_out_try_takes_no_pause(caplog):
    """A timed-out try can itself leave the run short of time (urllib's 60 s wait is per socket step, so a slow connect
    and a passed read wait can take more than 60 s together): the check before the pause stops the listing there, with
    OutOfTime naming the next try, so no pause eats into the time the manifest needs. The try that timed out is still
    reported, and its warning promises no further try: the check comes before the line is written."""
    left, sleeps, timeouts = [95.0], [], []

    def slow(req):
        left[0] = 85.0
        timed_out(req)

    http, portal = connect({listing_url(2, 1): [slow]})
    source = ShufersalSource(timer=ticks(60.5), sleep=sleeps.append)
    listing = source.listing(http, ("PriceFull",), lambda: left[0] < 90.0, on_timeout=timeouts.append)
    with pytest.raises(OutOfTime) as caught:
        list(listing)
    assert str(caught.value) == "before try 2 of page 1 of the PriceFull listing"
    assert portal.requested == [listing_url(2, 1)]
    assert len(timeouts) == 1
    assert sleeps == []
    assert warnings_logged(caplog) == [("shufersal PriceFull page 1: try 1 of 3 timed out after 60.5 s", logging.WARNING)]


def test_no_time_check_follows_the_last_try():
    """No pause follows the third try, so no time check does either: a run that the third timeout leaves short of time
    still ends on the error naming the page and the tries, not on a time stop before a fourth try."""
    left, served_requests = [95.0], []

    def slow_at_last(req):
        served_requests.append(req)
        if len(served_requests) == 3:
            left[0] = 85.0
        timed_out(req)

    http, portal = connect({listing_url(2, 1): [slow_at_last]})
    listing = ShufersalSource(timer=ticks(60.5), sleep=lambda seconds: None).listing(http, ("PriceFull",),
                                                                                     lambda: left[0] < 90.0)
    with pytest.raises(HttpError) as caught:
        list(listing)
    assert str(caught.value) == f"PriceFull page 1 timed out on 3 tries: GET {LISTING} failed: The read operation timed out"
    assert portal.requested == [listing_url(2, 1)] * 3


def dropped(req):
    raise ConnectionResetError(54, "Connection reset by peer")


@pytest.mark.parametrize("answer", [
    pytest.param(reply(500, SERVER_ERROR), id="a server error"),
    pytest.param(dropped, id="a dropped connection"),
    pytest.param(reply(body=fixture(2).encode("utf-8"), headers=[("Content-Length", "100000")]), id="a cut-short body"),
])
def test_other_failures_are_not_asked_again(answer):
    """Timeouts only (design, Call 1): any other failure says something new about the portal and shows plainly."""
    http, portal = connect({listing_url(2, 1): answer})
    sleeps, timeouts = [], []
    listing = ShufersalSource(timer=ticks(1.0), sleep=sleeps.append).listing(http, ("PriceFull",),
                                                                             on_timeout=timeouts.append)
    with pytest.raises(HttpError) as caught:
        list(listing)
    assert not isinstance(caught.value, HttpTimeout)
    assert portal.requested == [listing_url(2, 1)]
    assert (sleeps, timeouts) == ([], [])


def test_a_server_error_on_the_second_try_is_raised_at_once():
    http, portal = connect({listing_url(2, 1): [timed_out, reply(500, SERVER_ERROR)]})
    sleeps, timeouts = [], []
    listing = ShufersalSource(timer=ticks(1.0), sleep=sleeps.append).listing(http, ("PriceFull",),
                                                                             on_timeout=timeouts.append)
    with pytest.raises(HttpError, match="HTTP 500 from"):
        list(listing)
    assert portal.requested == [listing_url(2, 1)] * 2
    assert len(timeouts) == 1
    assert sleeps == [10.0]


def test_a_block_on_the_second_try_stops_the_listing():
    """A block is never asked again, whatever try it comes on."""
    http, portal = connect({listing_url(2, 1): [timed_out, refused(403)]})
    with pytest.raises(Blocked) as caught:
        list(ShufersalSource(timer=ticks(1.0), sleep=lambda seconds: None).listing(http, ("PriceFull",)))
    assert (caught.value.status, caught.value.url) == (403, listing_url(2, 1))
    assert portal.requested == [listing_url(2, 1)] * 2


def test_a_page_served_unreadable_after_a_timeout_is_not_asked_again():
    http, portal = connect({listing_url(2, 1): [timed_out, served(page(2, names=[]))]})
    with pytest.raises(ListingUnreadable, match="PriceFull page 1: no rows"):
        list(ShufersalSource(timer=ticks(1.0), sleep=lambda seconds: None).listing(http, ("PriceFull",)))
    assert portal.requested == [listing_url(2, 1)] * 2


@pytest.mark.parametrize("kind, start, slow, requested", [
    pytest.param("Stores", None, 1, [1, 1], id="a Stores page"),
    pytest.param("PriceFull", Start(page=12, furthest=names(12)[0], detours=(5,)), 5, [5, 5, 1, *range(12, 22)],
                 id="a detour"),
    pytest.param("PriceFull", Start(page=12, furthest=names(10)[5]), 11, [1, 12, 11, 11, 10, *range(11, 22)],
                 id="a step back"),
    pytest.param("PriceFull", Start(page=12, furthest=names(12)[0]), 12, [1, 12, 12, *range(13, 22)],
                 id="the resume page"),
])
def test_every_page_read_gets_the_tries(kind, start, slow, requested):
    """Every listing page request goes through the one page read, wherever the reading order puts it: page `slow`
    times out on its first request only."""
    cat = CATEGORY[kind]
    routes = {listing_url(5, 1): served(fixture(5))} if kind == "Stores" else twenty_one_pages()
    routes[listing_url(cat, slow)] = [timed_out, routes[listing_url(cat, slow)]]
    run = tried(routes, ticks(41.2), kinds=(kind,), start=start)
    assert listing_pages(run.portal) == requested
    assert next(read for read in run.reads if read.page == slow).tries == 2
    assert len(run.timeouts) == 1


def test_a_refresh_page_that_times_out_is_asked_again(caplog):
    """An expired link's refresh reads its pages through the same page read: the same tries and pause, reported to no
    one (a refresh reports no page) and logged all the same."""
    routes = {OLD_LINK: refused(), FRESH_LINK: gz(),
              listing_url(2, 1): [timed_out, served(fixture(2).replace(OLD_SIGNATURE, FRESH_SIGNATURE))]}
    http, portal = connect(routes)
    sleeps = []
    source = ShufersalSource(now=lambda: SE, timer=readings(0.0, 60.5, 70.5, 100.0), sleep=sleeps.append)
    assert source.download(http, item_030()) == GZ
    assert portal.requested == [OLD_LINK, listing_url(2, 1), listing_url(2, 1), FRESH_LINK]
    assert sleeps == [10.0]
    assert ("shufersal PriceFull page 1: try 1 of 3 timed out after 60.5 s; again in 10 s",
            logging.WARNING) in warnings_logged(caplog)


def test_a_refresh_page_that_times_out_on_every_try_fails_the_file():
    http, portal = connect({OLD_LINK: refused(), listing_url(2, 1): [timed_out]})
    with pytest.raises(HttpError) as caught:
        ShufersalSource(now=lambda: SE, timer=ticks(60.5), sleep=lambda seconds: None).download(http, item_030())
    assert str(caught.value) == f"PriceFull page 1 timed out on 3 tries: GET {LISTING} failed: The read operation timed out"
    assert portal.requested == [OLD_LINK, *[listing_url(2, 1)] * 3]


def test_each_failed_try_is_logged_at_warning(caplog):
    tried({listing_url(2, 1): [timed_out, timed_out, served(page(2, names(1), last=None))]},
          readings(0.0, 60.5, 70.5, 131.0, 141.0, 175.2))
    assert warnings_logged(caplog) == [
        ("shufersal PriceFull page 1: try 1 of 3 timed out after 60.5 s; again in 10 s", logging.WARNING),
        ("shufersal PriceFull page 1: try 2 of 3 timed out after 60.5 s; again in 10 s", logging.WARNING),
    ]
    caplog.clear()
    with pytest.raises(HttpError):
        tried({listing_url(2, 1): [timed_out]}, ticks(60.5))
    assert warnings_logged(caplog)[-1] == ("shufersal PriceFull page 1: try 3 of 3 timed out after 60.5 s",
                                           logging.WARNING)


def test_a_listing_without_on_timeout_still_asks_again():
    def routes():
        return {listing_url(2, 1): [timed_out, served(page(2, names(1), last=None))]}
    without = tried(routes(), ticks(41.2), report_timeouts=False)
    assert without.given == tried(routes(), ticks(41.2)).given == names(1)
    assert without.portal.requested == [listing_url(2, 1)] * 2


def test_three_tries_ten_seconds_apart_and_time_sleep_by_default():
    assert (shufersal.PAGE_TRIES, shufersal.RETRY_PAUSE) == (3, 10.0)
    assert inspect.signature(ShufersalSource).parameters["sleep"].default is time.sleep

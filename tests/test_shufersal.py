"""The Shufersal source: listing pages read to the last page the pager names and no further, one page
at a time; links checked before anything is fetched; an expired signed link refreshed once.

The real Http runs over a fake network (Portal), inside a real urllib opener built by `build_opener`,
as tests/test_http.py does: a 403 is judged a block by the code production runs, and the cookie jar
is production's. Listing pages are the fixtures (docs/portals.md, "Shufersal"), or the fixtures with
their rows renamed and their pager rewritten in the same markup.
"""
import http.client
import io
import itertools
import re
import urllib.parse
import urllib.request
import urllib.response
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from collector.chains import CHAINS
from collector.http import Blocked, Http, HttpError, build_opener
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, OutOfTime, PageRead, Source
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

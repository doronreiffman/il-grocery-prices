"""The NCR source: a login with the chain's published username and an empty password, the directory
listed as JSON (paged while fewer entries arrive than the answer's total), downloads in the session.

The real Http runs over a fake portal (Portal), inside a real urllib opener built by `build_opener`, as
tests/test_http.py and tests/test_shufersal.py do: redirects, cookies and blocks are judged by the code
production runs. Pages are the fixtures (docs/portals.md, "Rami Levy, through NCR"), with their
scrubbed tokens replaced by two different values, so the tests can tell which page's token went where.
"""
import http.client
import io
import json
import logging
import urllib.parse
import urllib.request
import urllib.response
from pathlib import Path

import pytest

from collector.chains import CHAINS, source_for
from collector.http import Blocked, Http, build_opener
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, Source
from collector.sources import ncr
from collector.sources.ncr import NcrSource

UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
FIXTURES = Path(__file__).parent / "fixtures" / "ncr"
BASE = "https://url.publishedprices.co.il"
LOGIN_PAGE = f"{BASE}/login"
LOGIN = f"{BASE}/login/user"
FILE_PAGE = f"{BASE}/file"
LISTING = f"{BASE}/file/json/dir"
SESSION_ONE = "cftpSID=one; Path=/; Secure; HttpOnly; SameSite=Lax"
SESSION_TWO = "cftpSID=two; Path=/; Secure; HttpOnly; SameSite=Lax"
SCRUBBED_META = '<meta name="csrftoken" content="SCRUBBED"/>'
PAGE_SIZE = "&quot;dtDisplayLength&quot;:10000,"
CD = '<input type="hidden" id="cd" name="cd" value="/" >'
CFTP = 'data-cftp="'
ENTRIES = json.loads((FIXTURES / "listing.json").read_text(encoding="utf-8"))["aaData"]
NAMES = [entry["fname"] for entry in ENTRIES]
PRICEFULL = "PriceFull7290058140886-001-722-20261101-001016.gz"
GZ = (FIXTURES / PRICEFULL).read_bytes()

LOGIN_FORM = [("r", ""), ("username", "RamiLevi"), ("password", ""), ("Submit", "Sign in"), ("csrftoken", "LOGIN-TOKEN")]


def listing_form(start=0, length=10000):
    """The listing POST as docs/portals.md lists it: DataTables 1.9's server-side parameters for the
    file table's five columns, then the directory and the file page's token."""
    columns = [("fname", "true"), ("typeLabel", "false"), ("size", "true"), ("ftime", "true"), ("", "false")]
    form = [("sEcho", "1"), ("iColumns", "5"), ("sColumns", ",,,,"), ("iDisplayStart", str(start)),
            ("iDisplayLength", str(length))]
    for i, (data, sortable) in enumerate(columns):
        form += [(f"mDataProp_{i}", data), (f"sSearch_{i}", ""), (f"bRegex_{i}", "false"),
                 (f"bSearchable_{i}", "true"), (f"bSortable_{i}", sortable)]
    return form + [("sSearch", ""), ("bRegex", "false"), ("iSortingCols", "0"), ("cd", "/"), ("csrftoken", "FILE-TOKEN")]


# ---- the fake portal and the pages it serves ----

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


def served(text, cookie=None):
    return reply(body=text.encode("utf-8"), headers=[("Set-Cookie", cookie)] if cookie else ())


def redirect(location, cookie=None):
    return reply(302, headers=[("Location", location)] + ([("Set-Cookie", cookie)] if cookie else []))


def as_json(data):
    return reply(body=json.dumps(data).encode(), content_type="application/json; charset=utf-8")


def login_html():
    return (FIXTURES / "login.html").read_text(encoding="utf-8").replace(SCRUBBED_META, '<meta name="csrftoken" content="LOGIN-TOKEN"/>')


def file_html(page_size=10000):
    text = (FIXTURES / "file-page.html").read_text(encoding="utf-8")
    text = text.replace(SCRUBBED_META, '<meta name="csrftoken" content="FILE-TOKEN"/>')
    return text.replace(PAGE_SIZE, f"&quot;dtDisplayLength&quot;:{page_size},")


def directory(entries=ENTRIES, total=None):
    """The listing as the portal answers it: the entries from iDisplayStart on, at most iDisplayLength
    of them, and the directory's total."""
    def respond(req):
        form = dict(urllib.parse.parse_qsl(req.data.decode(), keep_blank_values=True))
        start, length = int(form["iDisplayStart"]), int(form["iDisplayLength"])
        count = str(len(entries) if total is None else total)  # as text, as the portal sends it
        return as_json({"aaData": entries[start:start + length], "iTotalDisplayRecords": count,
                        "iTotalRecords": count, "sEcho": 1})(req)
    return respond


def entry(name):
    """A listing entry in the fixture's shape, naming `name`."""
    return dict(ENTRIES[0], DT_RowId=name, fname=name, name=name, value=name)


def gz():
    return reply(body=GZ, content_type="application/x-gzip")


class Portal(urllib.request.BaseHandler):
    """The portal, in place of the network: answers by (method, URL); a list is served in turn, its
    last answer kept. Every request is logged; more than `limit` fails the test."""
    handler_order = 400  # after urllib's proxy handler (100), before its HTTP and HTTPS handlers (500)

    def __init__(self, routes, limit=50):
        self.routes = dict(routes)
        self.limit = limit
        self.requests = []

    @property
    def requested(self):
        return [(req.get_method(), req.full_url) for req in self.requests]

    def sent(self, method, url):
        """The form each such request carried, as ordered pairs."""
        return [urllib.parse.parse_qsl(req.data.decode(), keep_blank_values=True)
                for req in self.requests if (req.get_method(), req.full_url) == (method, url)]

    def https_open(self, req):
        self.requests.append(req)
        assert len(self.requests) <= self.limit, f"more than {self.limit} requests"
        route = self.routes.get((req.get_method(), req.full_url))
        if route is None:
            raise AssertionError(f"unexpected request: {req.get_method()} {req.full_url}")
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        return route(req)

    http_open = https_open


def connect(**changes):
    """An Http on the portal as observed: the login page sets the session cookie, the login answers 302
    to /file with a new one, the file page, the listing, and every listed file. `changes` replaces
    routes by name: login_page, login, file_page, listing; `extra` adds routes."""
    routes = {("GET", LOGIN_PAGE): changes.get("login_page", served(login_html(), SESSION_ONE)),
              ("POST", LOGIN): changes.get("login", redirect("/file", SESSION_TWO)),
              ("GET", FILE_PAGE): changes.get("file_page", served(file_html())),
              ("POST", LISTING): changes.get("listing", directory())}
    routes |= {("GET", f"{BASE}/file/d/{name}"): gz() for name in NAMES}
    routes |= changes.get("extra", {})
    portal = Portal(routes)
    return Http(UA, opener=build_opener(portal), sleep=lambda seconds: None), portal


THROUGH_THE_LISTING = [("GET", LOGIN_PAGE), ("POST", LOGIN), ("GET", FILE_PAGE), ("POST", LISTING)]


def test_fixtures_hold_what_the_tests_replace():
    """The pages these tests serve differ from the fixtures only where they mean to."""
    for page in ("login.html", "file-page.html"):
        assert (FIXTURES / page).read_text(encoding="utf-8").count(SCRUBBED_META) == 1
    text = (FIXTURES / "file-page.html").read_text(encoding="utf-8")
    assert (text.count(PAGE_SIZE), text.count(CD), text.count(CFTP)) == (1, 1, 1)
    assert len(ENTRIES) == 14


# ---- the interface ----

@pytest.mark.parametrize("slug", ["ramilevy", "osherad", "yochananof"])
def test_base_url_is_the_ncr_chains(slug):
    assert ncr.BASE_URL == CHAINS[slug].base_url


def test_is_a_source():
    assert Source in NcrSource.__mro__


@pytest.mark.parametrize("username", ["", None])
def test_username_required(username):
    with pytest.raises(ValueError, match="NCR login needs the chain's username"):
        NcrSource(username)


# ---- the login ----

def test_logs_in_then_lists_one_request_at_a_time():
    """docs/portals.md: the login page, the login (302 to /file, followed), the listing."""
    http, portal = connect()
    listing = NcrSource("RamiLevi").listing(http, ("PriceFull",))
    assert portal.requested == []  # nothing until the first item is asked for
    next(listing)
    assert portal.requested == THROUGH_THE_LISTING


@pytest.mark.parametrize("slug", ["ramilevy", "osherad", "yochananof"])
def test_login_sends_the_published_username_an_empty_password_and_the_login_pages_token(slug):
    http, portal = connect()
    list(source_for(CHAINS[slug]).listing(http, ("Stores",)))
    username = CHAINS[slug].username
    assert portal.sent("POST", LOGIN) == [[(k, username if k == "username" else v) for k, v in LOGIN_FORM]]


def test_login_is_a_form_post_with_no_ajax_header():
    http, portal = connect()
    list(NcrSource("RamiLevi").listing(http, ("Stores",)))
    login = portal.requests[1]
    assert login.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert login.get_header("X-requested-with") is None


def test_session_cookie_kept_from_the_login_page_to_the_download():
    http, portal = connect()
    source = NcrSource("RamiLevi")
    item = next(item for item in source.listing(http, ("PriceFull",)) if item.name.raw == PRICEFULL)
    source.download(http, item)
    login_page, login, file_page, listing, download = portal.requests
    assert login_page.get_header("Cookie") is None
    assert login.get_header("Cookie") == "cftpSID=one"
    assert [r.get_header("Cookie") for r in (file_page, listing, download)] == ["cftpSID=two"] * 3


@pytest.mark.parametrize("path", ["/file", "/file/"])
def test_login_that_lands_on_the_file_browser_succeeds(path):
    """Ruling R22: the probe landed on /file; /file/ is the same browser."""
    http, portal = connect(login=redirect(path, SESSION_TWO), extra={("GET", f"{BASE}{path}"): served(file_html())})
    assert [item.name.raw for item in NcrSource("RamiLevi").listing(http, ("Stores",))] == NAMES[-3:]
    assert portal.requested == [("GET", LOGIN_PAGE), ("POST", LOGIN), ("GET", f"{BASE}{path}"), ("POST", LISTING)]


@pytest.mark.parametrize("changes, landed, where", [
    pytest.param({"login": redirect("/login")}, LOGIN_PAGE, "/login", id="sent back to the login page"),
    pytest.param({"login": served(login_html())}, LOGIN, "/login/user", id="the login form served again"),
    pytest.param({"file_page": served(login_html())}, FILE_PAGE, "the login form", id="the login form at /file"),
    pytest.param({"file_page": served(file_html().replace('<form id="file-op-form"', '<form action="/login/user"'))},
                 FILE_PAGE, "the login form", id="a form posting to the login at /file"),
    pytest.param({"file_page": served(login_html().replace('action="/login/user"', 'action="/login/other"'))},
                 FILE_PAGE, "the login form", id="the login form by its id at /file"),
    pytest.param({"login": redirect("/"), "extra": {("GET", f"{BASE}/"): served(file_html())}}, f"{BASE}/", "/",
                 id="landed on another page"),
    pytest.param({"login": redirect("/files"), "extra": {("GET", f"{BASE}/files"): served(file_html())}}, f"{BASE}/files",
                 "/files", id="landed on /files"),
    pytest.param({"login": redirect("/file/d/"), "extra": {("GET", f"{BASE}/file/d/"): served(file_html())}},
                 f"{BASE}/file/d/", "/file/d/", id="landed under /file/"),
])
def test_login_that_does_not_land_on_the_file_browser_is_a_block(changes, landed, where):
    """A failed login was not tried (docs/portals.md); landing anywhere but /file or /file/ (ruling
    R22), or on a page with the login form, is the portal refusing it. Never retried with anything else."""
    http, portal = connect(**changes)
    with pytest.raises(Blocked) as caught:
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert (caught.value.status, caught.value.url) == (200, landed)
    assert str(caught.value).startswith(f"the NCR login as 'RamiLevi' was not accepted (it landed on {where})")
    assert ("POST", LISTING) not in portal.requested


def test_refusal_of_the_login_page_is_a_block():
    http, portal = connect(login_page=reply(403, b"<html>Forbidden</html>"))
    with pytest.raises(Blocked) as caught:
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert caught.value.status == 403
    assert portal.requested == [("GET", LOGIN_PAGE)]


@pytest.mark.parametrize("text", [
    pytest.param(login_html().replace('<meta name="csrftoken" content="LOGIN-TOKEN"/>', ""), id="no token"),
    pytest.param(login_html().replace('content="LOGIN-TOKEN"', 'content=""'), id="an empty token"),
    pytest.param(login_html().replace('content="LOGIN-TOKEN"', ""), id="a token with no content"),
])
def test_login_page_without_a_token_is_unreadable(text):
    http, portal = connect(login_page=served(text))
    with pytest.raises(ListingUnreadable, match="the NCR login page carries no csrftoken"):
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert portal.requested == [("GET", LOGIN_PAGE)]


# ---- the file page ----

def test_listing_sends_the_datatables_parameters_and_the_file_pages_fresh_token():
    """docs/portals.md: the file page's own token, not the login page's; its page size; cd=/; and
    X-Requested-With and Accept, as jQuery and the probe sent them."""
    http, portal = connect()
    list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert portal.sent("POST", LISTING) == [listing_form()]
    listing = portal.requests[3]
    assert listing.get_header("X-requested-with") == "XMLHttpRequest"
    assert listing.get_header("Accept") == "application/json, text/javascript, */*; q=0.01"
    assert listing.get_header("Content-type") == "application/x-www-form-urlencoded"


@pytest.mark.parametrize("text, problem", [
    pytest.param(file_html().replace('<meta name="csrftoken" content="FILE-TOKEN"/>', ""), "carries no csrftoken", id="no token"),
    pytest.param(file_html().replace('content="FILE-TOKEN"', 'content=""'), "carries no csrftoken", id="an empty token"),
    pytest.param(file_html().replace(CD, ""), "names no directory (cd)", id="no cd"),
    pytest.param(file_html().replace(CD, CD.replace('value="/"', 'value="/2026"')), "directory is '/2026', not /", id="another directory"),
    pytest.param(file_html().replace(CD, CD.replace('value="/" ', "")), "names no directory (cd)", id="cd with no value"),
    pytest.param(file_html().replace(CFTP, 'data-other="'), "carries no data-cftp settings", id="no data-cftp"),
    pytest.param(file_html().replace(CFTP + "{", CFTP + "{,"), "data-cftp settings are not JSON", id="data-cftp not JSON"),
    pytest.param(file_html().replace(CFTP + "{", CFTP + "[{").replace('100000000}"', '100000000}]"'),
                 "page size (dtDisplayLength) is None", id="data-cftp a list"),
    pytest.param(file_html().replace(PAGE_SIZE, ""), "page size (dtDisplayLength) is None", id="no page size"),
    pytest.param(file_html(0), "page size (dtDisplayLength) is 0", id="a page size of 0"),
    pytest.param(file_html(-5), "page size (dtDisplayLength) is -5", id="a negative page size"),
    pytest.param(file_html("&quot;10000&quot;"), "page size (dtDisplayLength) is '10000'", id="a page size in quotes"),
    pytest.param(file_html("true"), "page size (dtDisplayLength) is True", id="a page size of true"),
    pytest.param(file_html("1.5"), "page size (dtDisplayLength) is 1.5", id="a fractional page size"),
])
def test_file_page_that_does_not_read_is_unreadable(text, problem):
    http, portal = connect(file_page=served(text))
    with pytest.raises(ListingUnreadable) as caught:
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert str(caught.value).startswith("the NCR file page")
    assert problem in str(caught.value)
    assert ("POST", LISTING) not in portal.requested


# ---- the listing ----

def test_listing_yields_every_listed_file_with_its_download_link():
    http, _ = connect()
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert listed == [Listed(parse_file_name(name), f"{BASE}/file/d/{name}") for name in NAMES]


def test_store_039s_lower_case_names_are_listed():
    """docs/portals.md: store 039 publishes lower-case names with no sub-chain and a 12-digit timestamp."""
    http, _ = connect()
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    store_039 = {item.name.raw: (item.name.kind, item.name.store, item.name.day.isoformat(), item.url)
                 for item in listed if item.name.store == "039"}
    assert store_039 == {
        "price7290058140886-039-202610300901.gz": ("Price", "039", "2026-10-30", f"{BASE}/file/d/price7290058140886-039-202610300901.gz"),
        "pricefull7290058140886-039-202610310517.gz": ("PriceFull", "039", "2026-10-31", f"{BASE}/file/d/pricefull7290058140886-039-202610310517.gz"),
        "promo7290058140886-039-202611010004.gz": ("Promo", "039", "2026-11-01", f"{BASE}/file/d/promo7290058140886-039-202611010004.gz"),
        "promofull7290058140886-039-202610310519.gz": ("PromoFull", "039", "2026-10-31", f"{BASE}/file/d/promofull7290058140886-039-202610310519.gz"),
    }


@pytest.mark.parametrize("kinds, count", [
    pytest.param(("Stores",), 3, id="Stores"),
    pytest.param(("PriceFull", "PromoFull"), 6, id="the full files"),
    pytest.param(("Price",), 3, id="Price, not PriceFull"),
    pytest.param(("Promo",), 2, id="Promo, not PromoFull"),
])
def test_only_the_kinds_asked_for_are_listed(kinds, count):
    """One listing holds every kind; Source.listing yields the kinds asked for, in the listing's order."""
    http, _ = connect()
    listed = [item.name.raw for item in NcrSource("RamiLevi").listing(http, kinds)]
    assert listed == [name for name in NAMES if parse_file_name(name).kind in kinds]
    assert len(listed) == count


def test_download_link_is_built_from_fname():
    """docs/portals.md: at the root the page's rule is /file/d/<fname>."""
    odd = dict(entry(PRICEFULL), DT_RowId="row-1", name="shown name", value="/elsewhere/x.gz")
    http, _ = connect(listing=directory([odd]))
    assert [item.url for item in NcrSource("RamiLevi").listing(http, ("PriceFull",))] == [f"{BASE}/file/d/{PRICEFULL}"]


def test_listing_pages_from_where_the_last_answer_ended_until_the_total():
    """Ruling R18: the page size changed per session (100000, 5000, 10000); fewer entries than
    iTotalDisplayRecords means another request from iDisplayStart = the entries received."""
    http, portal = connect(file_page=served(file_html(5)))
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert portal.sent("POST", LISTING) == [listing_form(0, 5), listing_form(5, 5), listing_form(10, 5)]
    assert portal.requested == THROUGH_THE_LISTING + [("POST", LISTING)] * 2


@pytest.mark.parametrize("total", ["14", "014", "000000014", 14])
def test_listing_reads_a_total_sent_as_text_or_as_a_number(total):
    """The portal sends the totals as text ("iTotalDisplayRecords": "<n>": the probe's raw answer of
    2026-10-31, the deployed runs of 2026-11-01). Text of the digits 0 to 9 alone, nine at most, reads
    as that number; a number reads as itself. The build read only numbers: the trimmed fixture had
    turned the text into a number."""
    http, portal = connect(listing=as_json({"aaData": ENTRIES, "iTotalDisplayRecords": total, "iTotalRecords": total, "sEcho": 1}))
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert portal.requested == THROUGH_THE_LISTING


def test_listing_pages_until_a_total_sent_as_text():
    answers = [as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": "14"}),
               as_json({"aaData": ENTRIES[5:], "iTotalDisplayRecords": "14"})]
    http, portal = connect(listing=answers)
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert [dict(form)["iDisplayStart"] for form in portal.sent("POST", LISTING)] == ["0", "5"]


def test_listing_pages_by_the_entries_received_not_the_page_size():
    """A server that sends fewer than it was asked for: the next request starts after what came."""
    answers = [as_json({"aaData": ENTRIES[:3], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[3:10], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[10:], "iTotalDisplayRecords": 14})]
    http, portal = connect(listing=answers)
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert [dict(form)["iDisplayStart"] for form in portal.sent("POST", LISTING)] == ["0", "3", "10"]


@pytest.mark.parametrize("answers, repeated", [
    pytest.param([as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 14})], NAMES[0], id="the first page again"),
    pytest.param([as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 14}),
                  as_json({"aaData": ENTRIES[4:9], "iTotalDisplayRecords": 14})], NAMES[4], id="one name again"),
])
def test_name_sent_again_on_both_reads_is_unreadable(answers, repeated):
    """Ruling R21: a server that ignores iDisplayStart sends its first page again and again, until the
    count reaches the total; the files after that page would be missed with no error. Such a server
    repeats on the second read from the start too (ruling R34), so the listing stops there."""
    http, portal = connect(file_page=served(file_html(5)), listing=answers)
    with pytest.raises(ListingUnreadable) as caught:
        list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert str(caught.value) == ("the NCR listing repeated a name on two reads from the start: "
                                 f"{repeated!r} again from iDisplayStart 5 (page size 5, total 14)")
    assert [dict(form)["iDisplayStart"] for form in portal.sent("POST", LISTING)] == ["0", "5", "0", "5"]
    assert portal.requested == THROUGH_THE_LISTING + [("POST", LISTING)] * 3  # one login, no download


def test_a_name_sent_again_reads_the_listing_again_from_the_start_once(caplog):
    """Ruling R34 (amends R21; QUEUE q8): retry run 101523Z-retry-8c22 (2026-11-01 10:15Z) stopped on a
    name sent again from iDisplayStart 890, and the next run, two minutes later, read the listing
    through. Likely, unproven: files published while the pages were read moved the order. A repeated
    name reads the listing again from iDisplayStart 0, in the same session, once, and logs that it did."""
    answers = [as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[4:9], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[5:10], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[10:], "iTotalDisplayRecords": 14})]
    http, portal = connect(file_page=served(file_html(5)), listing=answers)
    with caplog.at_level(logging.WARNING, logger="collector.sources.ncr"):
        listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert [dict(form)["iDisplayStart"] for form in portal.sent("POST", LISTING)] == ["0", "5", "0", "5", "10"]
    assert portal.requested == THROUGH_THE_LISTING + [("POST", LISTING)] * 4  # no second login
    assert [(r.levelname, r.getMessage()) for r in caplog.records if r.name == "collector.sources.ncr"] == [
        ("WARNING", f"the NCR listing as 'RamiLevi' sent {NAMES[4]!r} again from iDisplayStart 5 "
                    "(page size 5, total 14); reading it again from the start, once")]


def test_the_second_read_pages_to_its_own_total():
    """The directory can change between the reads: the second read goes by its own first answer's
    total. Kept at the first read's 20, it would ask again after the 14th name and stop on a repeat."""
    answers = [as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 20}),
               as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 20}),
               as_json({"aaData": ENTRIES[:5], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[5:10], "iTotalDisplayRecords": 14}),
               as_json({"aaData": ENTRIES[10:], "iTotalDisplayRecords": 14})]
    http, portal = connect(file_page=served(file_html(5)), listing=answers)
    listed = list(NcrSource("RamiLevi").listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo")))
    assert [item.name.raw for item in listed] == NAMES
    assert [dict(form)["iDisplayStart"] for form in portal.sent("POST", LISTING)] == ["0", "5", "0", "5", "10"]


@pytest.mark.parametrize("page_size, served_entries, total, received", [
    pytest.param(5, ENTRIES[:5], 14, 5, id="a later page empty"),
    pytest.param(10000, ENTRIES, 20, 14, id="the total more than the directory holds"),
])
def test_empty_answer_before_the_total_is_unreadable(page_size, served_entries, total, received):
    http, portal = connect(file_page=served(file_html(page_size)), listing=directory(served_entries, total))
    with pytest.raises(ListingUnreadable, match=f"the NCR listing stopped at {received} of {total} entries"):
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert len(portal.sent("POST", LISTING)) == 2
    assert not any(url.startswith(f"{BASE}/file/d/") for _, url in portal.requested)


@pytest.mark.parametrize("answer", [
    pytest.param({"aaData": [], "iTotalDisplayRecords": 0, "iTotalRecords": 0, "sEcho": 1}, id="nothing"),
    pytest.param({"aaData": ENTRIES, "iTotalDisplayRecords": 0, "iTotalRecords": 0, "sEcho": 1}, id="entries and a total of 0"),
    pytest.param({"aaData": ENTRIES, "iTotalDisplayRecords": "0", "iTotalRecords": "0", "sEcho": 1}, id="a total of 0 as text"),
])
def test_zero_total_is_unreadable(answer):
    """A directory with nothing in it means the portal changed, never "nothing published"."""
    http, portal = connect(listing=as_json(answer))
    with pytest.raises(ListingUnreadable, match="the NCR listing has no entries"):
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert portal.requested == THROUGH_THE_LISTING


@pytest.mark.parametrize("answer, problem", [
    pytest.param(served(login_html()), "is not JSON", id="an HTML page"),
    pytest.param(reply(body=b""), "is not JSON", id="an empty answer"),
    pytest.param(reply(body=b'{"aaData": [', content_type="application/json"), "is not JSON", id="cut short"),
    pytest.param(reply(body=b"\xff\xfe\x00", content_type="application/json"), "is not JSON", id="not text"),
    pytest.param(as_json([ENTRIES]), "no aaData list and iTotalDisplayRecords count", id="a list"),
    pytest.param(as_json({"iTotalDisplayRecords": 14}), "no aaData list and iTotalDisplayRecords count", id="no aaData"),
    pytest.param(as_json({"aaData": "x", "iTotalDisplayRecords": 14}), "no aaData list and iTotalDisplayRecords count", id="aaData not a list"),
    pytest.param(as_json({"aaData": ENTRIES}), "no aaData list and iTotalDisplayRecords count", id="no total"),
    pytest.param(as_json({"aaData": ENTRIES, "iTotalDisplayRecords": 14.0}), "no aaData list and iTotalDisplayRecords count", id="total a float"),
    *[pytest.param(as_json({"aaData": ENTRIES, "iTotalDisplayRecords": text}), "no aaData list and iTotalDisplayRecords count", id=f"total text {text!r}")
      for text in ("14.5", "-14", "+14", " 14", "14 ", "14\n", "", "1e3", "0x0e", "\u0661\u0664", "1234567890")],
    pytest.param(as_json({"aaData": ENTRIES, "iTotalDisplayRecords": True}), "no aaData list and iTotalDisplayRecords count", id="total true"),
    pytest.param(as_json({"aaData": ENTRIES[:2] + ["x"], "iTotalDisplayRecords": 3}), "entry 3 names no file (fname)", id="an entry not an object"),
    pytest.param(as_json({"aaData": [{"name": PRICEFULL}], "iTotalDisplayRecords": 1}), "entry 1 names no file (fname)", id="no fname"),
    pytest.param(as_json({"aaData": [{"fname": 5}], "iTotalDisplayRecords": 1}), "entry 1 names no file (fname)", id="fname not text"),
])
def test_listing_answer_of_another_shape_is_unreadable(answer, problem):
    http, portal = connect(listing=answer)
    with pytest.raises(ListingUnreadable) as caught:
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert str(caught.value).startswith("the NCR listing")
    assert problem in str(caught.value)
    assert portal.requested == THROUGH_THE_LISTING


@pytest.mark.parametrize("answer, held", [
    pytest.param(as_json([ENTRIES]), "(it held a list of 1)", id="a list"),
    pytest.param(as_json({"error": "SECRET-1", "code": 7}), "(it held an object with keys 'code': int, 'error': str)", id="an error object"),
    pytest.param(as_json({}), "(it held an object with no keys)", id="an empty object"),
    pytest.param(as_json("SECRET-1"), "(it held a str)", id="a string"),
    pytest.param(as_json({"aaData": [], "iTotalDisplayRecords": "x14", "n": None, "o": {}, "f": 1.5, "b": True}),
                 "(it held an object with keys 'aaData': list, 'b': bool, 'f': float, 'iTotalDisplayRecords': str, 'n': null, 'o': object)",
                 id="each type named"),
    pytest.param(as_json({f"k{i:02}": "SECRET-1" for i in range(12)}),
                 "(it held an object with keys " + ", ".join(f"'k{i:02}': str" for i in range(10)) + " and 2 more)", id="many keys"),
    pytest.param(as_json({"x" * 50: 1}), "(it held an object with keys '" + "x" * 40 + "...': int)", id="a long key"),
    pytest.param(as_json({"a\nERROR forged line": 1}), "(it held an object with keys 'a\\nERROR forged line': int)", id="a line break in a key"),
    pytest.param(as_json({"\ud800": 1, "\u05e9\u05dd": 2, "\x1b[31m": 3}),
                 "(it held an object with keys '\\x1b[31m': int, '\\u05e9\\u05dd': int, '\\ud800': int)", id="control, Hebrew and a lone surrogate"),
])
def test_unreadable_listing_says_what_the_answer_held_and_none_of_its_values(answer, held):
    """So the next unreadable answer shows its layout in the log, the manifest and the alert, and no
    value from it (a token or a session id could be one)."""
    http, portal = connect(listing=answer)
    with pytest.raises(ListingUnreadable) as caught:
        list(NcrSource("RamiLevi").listing(http, ("PriceFull",)))
    assert str(caught.value) == "the NCR listing has no aaData list and iTotalDisplayRecords count " + held
    assert "SECRET-1" not in str(caught.value)
    assert str(caught.value).isascii() and str(caught.value).isprintable()


def test_names_that_do_not_parse_are_skipped_and_counted():
    entries = [entry("index.html"), entry(PRICEFULL), entry("readme"), entry("PriceFull7290058140886-001-722-20261399-001016.gz")]
    http, _ = connect(listing=directory(entries))
    source = NcrSource("RamiLevi")
    assert source.unparsed == 0
    assert [item.name.raw for item in source.listing(http, ("PriceFull",))] == [PRICEFULL]
    assert source.unparsed == 3


@pytest.mark.parametrize("name", [
    pytest.param(PRICEFULL.replace("-722-", "-\u0667\u0662\u0662-"), id="Arabic-Indic digits"),
    pytest.param("\u05de\u05d7\u05d9\u05e8\u05d9\u05dd.gz", id="Hebrew"),
    pytest.param(PRICEFULL + "\x00", id="a NUL"),
    pytest.param("\u017ftores7290058140886-000-20261031-050500.xml", id="a long s for the S of Stores"),
])
def test_names_that_are_not_printable_ascii_are_skipped_and_counted(name):
    """Ruling R20: never fetched, counted in `unparsed`, not a reason to stop."""
    http, portal = connect(listing=directory([entry(name), entry(PRICEFULL)]))
    source = NcrSource("RamiLevi")
    assert [item.name.raw for item in source.listing(http, ("Stores", "PriceFull", "PromoFull", "Price", "Promo"))] == [PRICEFULL]
    assert source.unparsed == 1
    assert portal.requested == THROUGH_THE_LISTING


def test_names_of_other_kinds_are_not_counted_as_unparsed():
    http, _ = connect()
    source = NcrSource("RamiLevi")
    list(source.listing(http, ("Stores",)))
    assert source.unparsed == 0


def test_unparsed_count_starts_again_with_each_listing():
    http, _ = connect(listing=[directory([entry("index.html"), entry(PRICEFULL)]), directory()])
    source = NcrSource("RamiLevi")
    list(source.listing(http, ("PriceFull",)))
    assert source.unparsed == 1
    list(source.listing(http, ("PriceFull",)))
    assert source.unparsed == 0


@pytest.mark.parametrize("name", [
    pytest.param("../" + PRICEFULL, id="up a folder"),
    pytest.param("2026/" + PRICEFULL, id="a folder"),
    pytest.param(PRICEFULL + "?x=1", id="a query"),
    pytest.param(PRICEFULL + "#x", id="a fragment"),
    pytest.param("Price Full.gz", id="a space"),
    pytest.param(PRICEFULL + "\t", id="a tab"),
])
def test_unsafe_name_anywhere_stops_the_listing_before_its_first_item(name):
    """Ruling R19: a link is built from fname; a name that is not safe in one raises, naming it, even
    in a kind not asked for, and before any item is given."""
    entries = [entry(PRICEFULL), entry(NAMES[-1]), entry(name)]
    http, portal = connect(listing=directory(entries))
    with pytest.raises(ListingUnreadable) as caught:
        next(NcrSource("RamiLevi").listing(http, ("PriceFull", "Stores")))
    assert str(caught.value) == f"the NCR listing, entry 3: the file name {name!r} is not safe to put in a link"
    assert portal.requested == THROUGH_THE_LISTING


def test_every_listing_logs_in_again():
    http, portal = connect()
    source = NcrSource("RamiLevi")
    list(source.listing(http, ("Stores",)))
    list(source.listing(http, ("Stores",)))
    assert portal.requested == THROUGH_THE_LISTING * 2


# ---- downloads ----

def test_download_returns_the_body_as_received():
    http, portal = connect()
    source = NcrSource("RamiLevi")
    item = next(item for item in source.listing(http, ("PriceFull",)) if item.name.raw == PRICEFULL)
    assert source.download(http, item) == GZ
    assert portal.requested == THROUGH_THE_LISTING + [("GET", f"{BASE}/file/d/{PRICEFULL}")]

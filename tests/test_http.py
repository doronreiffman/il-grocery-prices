"""The HTTP client: identified, one request at a time, stopped by a block, never retried.

The fake network (FakeNet) answers in place of urllib's HTTPS handler, inside a real urllib opener
built by `build_opener`, so the cookie jar, the redirect rule and the proxy setting under test are
the ones production runs.
"""
import gzip
import http.client
import io
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path

import pytest

from collector import http as http_module
from collector.http import Blocked, Http, HttpError, HttpTimeout, Response, build_opener

UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
FIXTURES = Path(__file__).parent / "fixtures"
NCR = "https://url.publishedprices.co.il"
SHUFERSAL_LISTING = "https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&storeId=0&page=1"
BLOB_LINK = ("https://pricesprodpublic.blob.core.windows.net/pricefull/PriceFull7290027600007-001-030-20261031-030000.gz"
             "?sv=2014-02-14&sr=b&sig=SCRUBBED&se=2026-10-31T22%3A36%3A02Z&sp=r")
XML = b'<?xml version="1.0" encoding="UTF-8"?><Root><ChainID>7290027600007</ChainID></Root>'
# NCR's real Content-Security-Policy (probe, 2026-10-31) names reCAPTCHA on every answer; no captcha was served.
NCR_CSP = ("default-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.google.com/recaptcha/; "
           "frame-src 'self' https://www.google.com/recaptcha/ *.duosecurity.com")
SESSION_ONE = "cftpSID=one; Path=/; Secure; HttpOnly; SameSite=Lax"
SESSION_TWO = "cftpSID=two; Path=/; Secure; HttpOnly; SameSite=Lax"


def answer(status=200, body=XML, headers=(("Content-Type", "text/xml"),), fp=None):
    """One canned answer, built the way urllib's HTTP handler builds a real one."""
    def respond(req):
        message = http.client.HTTPMessage()
        for key, value in headers:
            message[key] = value
        resp = urllib.response.addinfourl(fp if fp is not None else io.BytesIO(body), message, req.full_url, status)
        resp.msg = http.client.responses.get(status, "")
        return resp
    return respond


def html(body, status=200, headers=()):
    return answer(status, body, (("Content-Type", "text/html; charset=utf-8"), *headers))


class FailingBody(io.BytesIO):
    """A body whose read fails part-way, as a timed-out or dropped connection does."""

    def __init__(self, error):
        super().__init__(b"")
        self.error = error

    def read(self, *args):
        raise self.error


class FakeNet(urllib.request.BaseHandler):
    """Answers every request in order, in place of the network. Its handler_order puts it after
    urllib's proxy handler (100) and before its HTTP and HTTPS handlers (500)."""
    handler_order = 400

    def __init__(self, *answers, events=None):
        self.answers = list(answers)
        self.requests = []
        self.events = events if events is not None else []

    def https_open(self, req):
        self.requests.append(req)
        self.events.append(("request", req.get_method(), req.full_url))
        if not self.answers:
            raise AssertionError(f"unexpected request: {req.get_method()} {req.full_url}")
        reply = self.answers.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply(req)

    http_open = https_open


def client(*answers, **kwargs):
    """An Http on a fake network; returns the client, the network and the list of pauses taken."""
    net = FakeNet(*answers)
    sleeps = []
    return Http(UA, opener=build_opener(net), sleep=sleeps.append, **kwargs), net, sleeps


# ---- the User-Agent ----

def test_user_agent_sent_on_every_request_and_redirect_hop():
    h, net, _ = client(answer(302, b"", [("Location", "/login")]), html(b"<html>login</html>"),
                       answer(302, b"", [("Location", "/file")]), html(b"<html>files</html>"))
    h.get(NCR)
    h.post(f"{NCR}/login/user", {"username": "RamiLevi", "password": ""})
    assert len(net.requests) == 4
    assert [r.get_header("User-agent") for r in net.requests] == [UA] * 4


@pytest.mark.parametrize("user_agent", [
    pytest.param("bad", id="neither"),
    pytest.param("il-grocery-prices/0.1 (+https://github.com/example/repo; no contact)", id="no @"),
    pytest.param("il-grocery-prices/0.1 (owner@example.org)", id="no +https://"),
    pytest.param("il-grocery-prices/0.1 (+http://example.org; owner@example.org)", id="+http:// only"),
    pytest.param("il-grocery-prices/0.1 (https://example.org; owner@example.org)", id="no +"),
    pytest.param("", id="empty"),
])
def test_user_agent_without_project_url_and_contact_refused(user_agent):
    with pytest.raises(ValueError, match="User-Agent"):
        Http(user_agent, opener=build_opener(FakeNet()))


# ---- blocks ----

@pytest.mark.parametrize("status", [401, 403, 429])
def test_refusal_statuses_are_blocks(status):
    h, net, _ = client(answer(status, b"no", [("Content-Type", "text/plain")]))
    with pytest.raises(Blocked) as caught:
        h.get(SHUFERSAL_LISTING)
    assert caught.value.status == status
    assert caught.value.url == SHUFERSAL_LISTING
    assert str(status) in caught.value.reason
    assert len(net.requests) == 1


def test_blob_host_403_carries_the_whole_link():
    """The Shufersal adapter reads `se=` from the refused link to tell expiry from a block."""
    h, _, _ = client(answer(403, b'<?xml version="1.0" encoding="utf-8"?><Error><Code>AuthenticationFailed</Code></Error>',
                            [("Content-Type", "application/xml")]))
    with pytest.raises(Blocked) as caught:
        h.get(BLOB_LINK)
    assert (caught.value.status, caught.value.url) == (403, BLOB_LINK)
    assert "se=2026-10-31T22%3A36%3A02Z" in caught.value.url
    # The message (logged, stored in the chain's latch) leaves the signed query out.
    assert "pricesprodpublic.blob.core.windows.net/pricefull/" in str(caught.value)
    assert "sig=" not in str(caught.value)


@pytest.mark.parametrize("body", [
    pytest.param(b"<!DOCTYPE html><html><head><script src='/cdn-cgi/challenge-platform/h/b/cf-chl/x.js'>", id="cf-chl"),
    pytest.param(b"<html><body><div class='g-recaptcha'></div></body></html>", id="captcha in recaptcha"),
    pytest.param(b"<html><body><h1>CAPTCHA</h1></body></html>", id="CAPTCHA, upper case"),
    pytest.param(b"<html><title>Attention Required! | Cloudflare</title></html>", id="Attention Required"),
    pytest.param(b"<html><title>attention required</title></html>", id="attention required, lower case"),
    pytest.param(b"<div class='g-recaptcha' data-sitekey='x'></div>", id="HTML fragment, known by its content type"),
])
def test_verification_page_with_200_is_a_block(body):
    h, net, _ = client(html(body))
    with pytest.raises(Blocked) as caught:
        h.get(SHUFERSAL_LISTING)
    assert caught.value.status == 200
    assert caught.value.url == SHUFERSAL_LISTING
    assert "captcha or verification" in caught.value.reason
    assert len(net.requests) == 1


def test_verification_page_seen_by_its_shape_without_an_html_content_type():
    h, _, _ = client(answer(200, b"\n  <!DOCTYPE html><html><body>captcha</body></html>",
                            [("Content-Type", "application/octet-stream")]))
    with pytest.raises(Blocked):
        h.get(BLOB_LINK)


def test_verification_page_with_an_error_status_is_a_block_not_an_error():
    """A captcha page is a block whatever its status, not only with 401, 403 or 429."""
    h, _, _ = client(html(b"<html><body><form id='challenge-form' action='/?__cf_chl_f_tk=x'>cf-chl</form>", 503))
    with pytest.raises(Blocked) as caught:
        h.get(SHUFERSAL_LISTING)
    assert caught.value.status == 503


@pytest.mark.parametrize("body, content_type", [
    pytest.param(b"\x1f\x8b\x08\x00 captcha cf-chl Attention Required", "application/x-gzip", id="gzip"),
    pytest.param(b"\x1f\x8b\x08\x00 captcha cf-chl Attention Required", "text/html", id="gzip labelled text/html"),
    pytest.param(gzip.compress(b"<html><body>captcha</body></html>"), "application/octet-stream",
                 id="HTML inside a gzip (the payload check's job)"),
    pytest.param(b'<?xml version="1.0"?><Root><ItemName>captcha cf-chl</ItemName></Root>', "text/xml", id="XML"),
    pytest.param(b'{"aaData":[{"fname":"captcha.gz"}]}', "application/json", id="JSON"),
])
def test_markers_not_sought_outside_html(body, content_type):
    """The marker bytes can turn up by chance in a gzip or in data; only an HTML body is read."""
    h, _, _ = client(answer(200, body, [("Content-Type", content_type)]))
    assert h.get(BLOB_LINK).body == body


def test_markers_not_sought_in_headers():
    page = b"<!DOCTYPE html><html><head><title>Cerberus Web Client</title></head></html>"
    h, _, _ = client(html(page, headers=[("Content-Security-Policy", NCR_CSP)]))
    assert h.get(f"{NCR}/login").body == page


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*/*.html")), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_portal_page_in_the_fixtures_passes(path):
    body = path.read_bytes()
    h, _, _ = client(html(body, headers=[("Content-Security-Policy", NCR_CSP)]))
    assert h.get(SHUFERSAL_LISTING).body == body


# ---- errors that are not blocks ----

@pytest.mark.parametrize("status", [400, 404, 500, 502, 503])
def test_other_error_statuses_are_http_errors(status):
    h, net, _ = client(answer(status, b"<?xml version='1.0'?><Error><Code>BlobNotFound</Code></Error>",
                              [("Content-Type", "application/xml")]))
    with pytest.raises(HttpError, match=str(status)):
        h.get(BLOB_LINK)
    assert len(net.requests) == 1


def test_server_error_html_page_is_an_http_error():
    h, _, _ = client(html(b"<html><body><h1>500 - Internal server error.</h1></body></html>", 500))
    with pytest.raises(HttpError, match="500"):
        h.get(SHUFERSAL_LISTING)


@pytest.mark.parametrize("reply", [
    pytest.param(urllib.error.URLError(TimeoutError("timed out")), id="connect timeout"),
    pytest.param(answer(fp=FailingBody(TimeoutError("timed out"))), id="read timeout"),
    pytest.param(ConnectionResetError("reset by peer"), id="connection reset"),
    pytest.param(urllib.error.URLError("[Errno 8] nodename nor servname provided"), id="DNS failure"),
    pytest.param(answer(fp=FailingBody(http.client.IncompleteRead(b"abc", 7))), id="cut short (http.client)"),
])
def test_network_failures_are_http_errors_and_not_retried(reply):
    h, net, _ = client(reply)
    with pytest.raises(HttpError):
        h.get(BLOB_LINK)
    assert len(net.requests) == 1


@pytest.mark.parametrize("in_the_body, error", [
    pytest.param(True, TimeoutError("The read operation timed out"), id="reading the answer"),
    pytest.param(False, TimeoutError("The read operation timed out"), id="waiting for the answer"),
    pytest.param(False, urllib.error.URLError(TimeoutError("timed out")), id="connecting"),
    pytest.param(False, urllib.error.URLError(TimeoutError("_ssl.c:1011: The handshake operation timed out")),
                 id="the TLS handshake"),
])
def test_a_timeout_is_an_http_timeout_and_not_retried(in_the_body, error):
    """urllib wraps a timeout while connecting or in the TLS handshake in a URLError; one while waiting
    for the answer or reading it arrives bare (docs/shufersal-page-retry.md, "Why")."""
    h, net, _ = client(answer(fp=FailingBody(error)) if in_the_body else error)
    with pytest.raises(HttpTimeout) as caught:
        h.get(BLOB_LINK)
    assert isinstance(caught.value, HttpError)
    assert caught.value.__cause__ is error
    assert str(caught.value) == f"GET {BLOB_LINK.split('?')[0]} failed: {error}"
    assert len(net.requests) == 1


@pytest.mark.parametrize("reply", [
    pytest.param(ConnectionResetError(54, "Connection reset by peer"), id="a dropped connection"),
    pytest.param(answer(fp=FailingBody(ConnectionResetError(54, "Connection reset by peer"))), id="dropped while reading"),
    pytest.param(urllib.error.URLError("[Errno 8] nodename nor servname provided"), id="a DNS failure"),
    pytest.param(urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")), id="a refused connection"),
    pytest.param(answer(fp=FailingBody(http.client.IncompleteRead(b"abc", 7))), id="cut short"),
    pytest.param(answer(200, b"\x1f\x8b\x08\x00short", [("Content-Type", "application/x-gzip"), ("Content-Length", "100")]),
                 id="shorter than its length"),
    pytest.param(answer(500, b"", [("Content-Type", "text/plain")]), id="a 500"),
])
def test_other_failures_are_plain_http_errors(reply):
    h, net, _ = client(reply)
    with pytest.raises(HttpError) as caught:
        h.get(BLOB_LINK)
    assert type(caught.value) is HttpError
    assert len(net.requests) == 1


def test_a_timeout_is_an_http_error_and_not_a_block():
    """Every `except HttpError` catches a timeout; a timeout never latches a chain."""
    assert issubclass(HttpTimeout, HttpError)
    assert not issubclass(HttpTimeout, Blocked)


def test_error_body_that_fails_to_read_still_blocks():
    h, _, _ = client(answer(403, fp=FailingBody(TimeoutError("timed out"))))
    with pytest.raises(Blocked):
        h.get(BLOB_LINK)


def test_body_shorter_than_content_length_is_an_http_error():
    h, net, _ = client(answer(200, b"\x1f\x8b\x08\x00short", [("Content-Type", "application/x-gzip"),
                                                              ("Content-Length", "100")]))
    with pytest.raises(HttpError, match="9 of 100"):
        h.get(BLOB_LINK)
    assert len(net.requests) == 1


@pytest.mark.parametrize("length", ["9", "8", "nine", ""])
def test_body_as_long_as_content_length_or_no_usable_length_is_kept(length):
    h, _, _ = client(answer(200, b"\x1f\x8b\x08\x00short", [("Content-Type", "application/x-gzip"),
                                                            ("Content-Length", length)]))
    assert h.get(BLOB_LINK).body == b"\x1f\x8b\x08\x00short"


# ---- cookies and redirects ----

def test_cookie_set_on_one_answer_is_sent_on_the_next():
    h, net, _ = client(html(b"<html>login</html>", headers=[("Set-Cookie", SESSION_ONE)]), html(b"<html>files</html>"))
    h.get(f"{NCR}/login")
    h.get(f"{NCR}/file")
    assert net.requests[0].get_header("Cookie") is None
    assert net.requests[1].get_header("Cookie") == "cftpSID=one"


def test_ncr_login_flow_follows_same_host_redirects_with_the_session():
    """docs/portals.md: the entry URL answers 302 to /login, the login POST 302 to /file; both set cftpSID."""
    login_page = (FIXTURES / "ncr" / "login.html").read_bytes()
    file_page = (FIXTURES / "ncr" / "file-page.html").read_bytes()
    csp = ("Content-Security-Policy", NCR_CSP)
    h, net, sleeps = client(
        answer(302, b"", [("Location", "/login"), ("Set-Cookie", SESSION_ONE), csp]),
        html(login_page, headers=[csp]),
        answer(302, b"", [("Location", "/file"), ("Set-Cookie", SESSION_TWO), ("Content-Type", "text/html"), csp]),
        html(file_page, headers=[csp]),
    )
    landing = h.get(NCR)
    assert (landing.url, landing.status, landing.body) == (f"{NCR}/login", 200, login_page)
    form = {"r": "", "username": "RamiLevi", "password": "", "Submit": "Sign in", "csrftoken": "SCRUBBED"}
    files = h.post(f"{NCR}/login/user", form)
    assert (files.url, files.status, files.body) == (f"{NCR}/file", 200, file_page)

    entry, login, post, file_get = net.requests
    assert (entry.get_method(), entry.get_header("Cookie")) == ("GET", None)
    assert (login.get_method(), login.full_url, login.get_header("Cookie")) == ("GET", f"{NCR}/login", "cftpSID=one")
    assert (post.get_method(), post.get_header("Cookie")) == ("POST", "cftpSID=one")
    # urllib turns the POST into a GET on 302, without the form.
    assert (file_get.get_method(), file_get.full_url, file_get.data) == ("GET", f"{NCR}/file", None)
    assert file_get.get_header("Cookie") == "cftpSID=two"
    assert sleeps == [0.5]  # one pause between the two calls; redirect hops follow at once


@pytest.mark.parametrize("location, refused", [
    pytest.param("https://evil.example/login", "https://evil.example", id="another host"),
    pytest.param("http://url.publishedprices.co.il/login", "http://url.publishedprices.co.il", id="https to http"),
    pytest.param("https://url.publishedprices.co.il:8443/login", "https://url.publishedprices.co.il:8443", id="another port"),
])
def test_redirect_off_the_host_refused(location, refused):
    h, net, _ = client(answer(302, b"", [("Location", location)]))
    with pytest.raises(HttpError, match="redirect") as caught:
        h.get(f"{NCR}/")
    assert refused in str(caught.value)
    assert len(net.requests) == 1  # not followed


def test_cookies_kept_per_instance():
    net = FakeNet(html(b"<html>a</html>", headers=[("Set-Cookie", SESSION_ONE)]), html(b"<html>b</html>"))
    first = Http(UA, opener=build_opener(net), sleep=lambda s: None)
    second = Http(UA, opener=build_opener(net), sleep=lambda s: None)
    first.get(f"{NCR}/login")
    second.get(f"{NCR}/file")
    assert net.requests[1].get_header("Cookie") is None


def test_default_opener_has_its_own_cookie_jar_and_the_redirect_rule():
    def parts(h):
        handlers = h._opener.handlers
        jar = next(x.cookiejar for x in handlers if isinstance(x, urllib.request.HTTPCookieProcessor))
        return jar, [type(x) for x in handlers]
    jar_a, types_a = parts(Http(UA))
    jar_b, _ = parts(Http(UA))
    assert jar_a is not jar_b
    assert http_module._SameHostRedirects in types_a
    assert urllib.request.HTTPRedirectHandler not in types_a


def test_no_proxy_taken_from_the_environment(monkeypatch):
    """Never a proxy: urllib otherwise routes through one named in the environment (or macOS settings)."""
    for name in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        monkeypatch.setenv(name, "http://proxy.invalid:3128")
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
    h, net, _ = client(answer())
    h.get(BLOB_LINK)
    assert net.requests[0].host == "pricesprodpublic.blob.core.windows.net"


# ---- pacing, retries, requests and answers ----

def test_pause_between_requests_and_not_before_the_first():
    events = []
    net = FakeNet(answer(), answer(), answer(), events=events)
    h = Http(UA, opener=build_opener(net), sleep=lambda s: events.append(("sleep", s)))
    h.get(BLOB_LINK)
    assert events == [("request", "GET", BLOB_LINK)]
    h.get(BLOB_LINK)
    h.post(BLOB_LINK, {"a": "1"})
    assert events == [("request", "GET", BLOB_LINK), ("sleep", 0.5), ("request", "GET", BLOB_LINK),
                      ("sleep", 0.5), ("request", "POST", BLOB_LINK)]


def test_pause_follows_a_failed_request_too():
    h, net, sleeps = client(answer(500, b"", [("Content-Type", "text/plain")]), answer())
    with pytest.raises(HttpError):
        h.get(BLOB_LINK)
    h.get(BLOB_LINK)
    assert sleeps == [0.5]
    assert len(net.requests) == 2


def test_pause_and_timeout_as_given():
    h, net, sleeps = client(answer(), answer(), pause=2.0, timeout=5.0)
    h.get(BLOB_LINK)
    h.get(BLOB_LINK)
    assert sleeps == [2.0]
    assert [r.timeout for r in net.requests] == [5.0, 5.0]


def test_default_timeout_is_30_seconds():
    h, net, _ = client(answer())
    h.get(BLOB_LINK)
    assert net.requests[0].timeout == 30.0


def test_get_sends_no_body():
    h, net, _ = client(answer())
    h.get(SHUFERSAL_LISTING)
    assert (net.requests[0].get_method(), net.requests[0].data) == ("GET", None)


def test_post_sends_the_form_url_encoded():
    h, net, _ = client(answer(200, b'{"aaData":[]}', [("Content-Type", "application/json; charset=utf-8")]))
    h.post(f"{NCR}/file/json/dir", {"sEcho": "1", "sColumns": ",,,,", "cd": "/", "Submit": "Sign in", "password": ""})
    sent = net.requests[0]
    assert sent.get_method() == "POST"
    assert sent.data == b"sEcho=1&sColumns=%2C%2C%2C%2C&cd=%2F&Submit=Sign+in&password="
    assert sent.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert sent.get_header("X-requested-with") is None


def test_post_sends_the_headers_given():
    """NCR's listing is an AJAX call; jQuery, and the probe, send X-Requested-With with it."""
    h, net, _ = client(answer(200, b'{"aaData":[]}', [("Content-Type", "application/json; charset=utf-8")]))
    h.post(f"{NCR}/file/json/dir", {"cd": "/"}, headers={"X-Requested-With": "XMLHttpRequest"})
    sent = net.requests[0]
    assert sent.get_header("X-requested-with") == "XMLHttpRequest"
    assert sent.get_header("User-agent") == UA
    assert sent.get_header("Content-type") == "application/x-www-form-urlencoded"


@pytest.mark.parametrize("name", ["User-Agent", "user-agent", "USER-AGENT", "Content-Type", "content-type"])
def test_headers_given_cannot_replace_the_user_agent_or_the_content_type(name):
    h, net, _ = client(answer())
    h.post(f"{NCR}/file/json/dir", {"cd": "/"}, headers={name: "Mozilla/5.0 (Macintosh)"})
    sent = net.requests[0]
    assert sent.get_header("User-agent") == UA
    assert sent.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert "Mozilla/5.0 (Macintosh)" not in [value for _, value in sent.header_items()]


def test_response_carries_url_status_body_and_lower_case_headers():
    h, _, _ = client(answer(200, XML, [("Content-Type", "text/xml"), ("Content-MD5", "abc=="),
                                       ("X-Twice", "one"), ("X-Twice", "two")]))
    got = h.get(BLOB_LINK)
    assert got == Response(url=BLOB_LINK, status=200, body=XML,
                           headers={"content-type": "text/xml", "content-md5": "abc==", "x-twice": "one, two"})

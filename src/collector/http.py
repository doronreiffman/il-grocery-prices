"""The HTTP client every portal adapter uses: identified, one request at a time, stopped by a block.

- Every request carries the deploy's User-Agent, which must name the project URL (`+https://`) and a
  contact email (`@`); Http refuses one without both.
- One Http serves one chain, so it holds that chain's cookies (NCR's `cftpSID` session). Each call to
  `get` or `post` after the first waits `pause` seconds; the redirect hops inside one call follow at once.
- A block raises Blocked: a 401, 403 or 429, or a captcha or verification page (a body that looks like
  HTML and contains `cf-chl`, `captcha` or `Attention Required`, whatever its status). Only an HTML
  body is read for those words: they can turn up by chance in a gzip or in data, and NCR's
  Content-Security-Policy header names reCAPTCHA on every answer.
- Anything else that goes wrong raises HttpError: a timeout or dropped connection, any other status
  outside 2xx, a body shorter than its Content-Length, a redirect to another scheme, host or port.
- Http never retries; the run loop decides (at most one retry per file). It never works around a block
  and never goes through a proxy, even one the environment names.
"""
import http.client
import http.cookiejar
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from collector.payload import GZIP_MAGIC, looks_like_html

BLOCK_STATUSES = frozenset({401, 403, 429})
MARKERS = (b"cf-chl", b"captcha", b"attention required")  # sought in the body lower-cased
FORM = "application/x-www-form-urlencoded"


class Blocked(Exception):
    """The portal refused: stop the chain and latch it until the owner clears it. Never work around it.

    `status` is the answer's HTTP status (None when an adapter raises it with no answer to blame),
    `url` the address that refused, query string included (the Shufersal adapter reads the signed
    link's `se=` from it), and `reason` what made it a block. The message leaves the query out."""

    def __init__(self, status: int | None, url: str, reason: str):
        super().__init__(f"{reason}: {_without_query(url)}")
        self.status = status
        self.url = url
        self.reason = reason


class HttpError(Exception):
    """A request failed in a way that is not a block: timeout, dropped connection, a status outside 2xx
    other than 401, 403 and 429, a cut-short body, or a redirect off the host. Worth one retry."""


@dataclass
class Response:
    url: str  # where the request landed, after any redirects
    status: int
    body: bytes
    headers: dict[str, str]  # names lower-cased; a repeated header's values joined with ", "


def check_user_agent(user_agent: str) -> str:
    """The User-Agent must name the project URL and a contact email:
    `il-grocery-prices/<version> (+<repo URL>; <contact email>)`."""
    if "+https://" not in user_agent or "@" not in user_agent:
        raise ValueError("the User-Agent must name the project URL (+https://...) and a contact email (@)")
    return user_agent


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same scheme and host (port included), as flights-archive does: a
    portal's files come from that portal, and a hop elsewhere would carry the request somewhere unchecked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (new.scheme, new.netloc) != (old.scheme, old.netloc):
            fp.close()
            raise HttpError(f"redirect from {old.scheme}://{old.netloc} to {new.scheme}://{new.netloc} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """A urllib opener with its own cookie jar, the same-host redirect rule and no proxy. Tests pass a
    fake network handler; production passes nothing."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                       _SameHostRedirects(), *handlers)


class Http:
    """One chain's HTTP client. `opener` is for tests (`build_opener(<fake network>)`); the default
    builds a fresh one, so each Http has its own cookies."""

    def __init__(self, user_agent: str, timeout: float = 30.0, pause: float = 0.5,
                 opener: urllib.request.OpenerDirector | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.user_agent = check_user_agent(user_agent)
        self.timeout = timeout
        self.pause = pause
        self._opener = opener if opener is not None else build_opener()
        self._sleep = sleep
        self._sent = False

    def get(self, url: str) -> Response:
        return self._send(urllib.request.Request(url, headers={"User-Agent": self.user_agent}))

    def post(self, url: str, form: dict[str, str]) -> Response:
        """POST `form` url-encoded, as an HTML form does."""
        data = urllib.parse.urlencode(form).encode()
        return self._send(urllib.request.Request(url, data=data, method="POST",
                                                 headers={"User-Agent": self.user_agent, "Content-Type": FORM}))

    def _send(self, req: urllib.request.Request) -> Response:
        if self._sent:
            self._sleep(self.pause)
        self._sent = True
        try:
            try:
                with self._opener.open(req, timeout=self.timeout) as resp:
                    answer = Response(resp.geturl(), resp.status, resp.read(), _headers(resp.headers))
            except urllib.error.HTTPError as err:  # a status outside 2xx: judged below like any answer
                answer = Response(err.geturl(), err.code, _read_quietly(err), _headers(err.headers))
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:  # timeouts, resets, DNS, TLS, cut short
            raise HttpError(f"{req.get_method()} {_without_query(req.full_url)} failed: {exc}") from exc
        return _judge(answer)


def _judge(answer: Response) -> Response:
    """Raise Blocked or HttpError unless `answer` is a whole 2xx that is not a verification page."""
    if answer.status in BLOCK_STATUSES:
        raise Blocked(answer.status, answer.url, f"HTTP {answer.status}")
    marker = _verification_marker(answer)
    if marker:
        raise Blocked(answer.status, answer.url,
                      f"a captcha or verification page (HTTP {answer.status}, it contains {marker.decode()!r})")
    if not 200 <= answer.status < 300:
        raise HttpError(f"HTTP {answer.status} from {_without_query(answer.url)}")
    length = answer.headers.get("content-length", "")
    if length.isdecimal() and len(answer.body) < int(length):
        raise HttpError(f"{_without_query(answer.url)}: the body was cut short ({len(answer.body)} of {length} bytes)")
    return answer


def _verification_marker(answer: Response) -> bytes | None:
    """The first block marker in an HTML body; None for any other body, gzip above all."""
    if answer.body.startswith(GZIP_MAGIC):
        return None
    if "text/html" not in answer.headers.get("content-type", "").lower() and not looks_like_html(answer.body):
        return None
    body = answer.body.lower()
    return next((m for m in MARKERS if m in body), None)


def _read_quietly(err: urllib.error.HTTPError) -> bytes:
    """An error answer's body, or b"" when it cannot be read (a 401, 403 or 429 is a block all the same)."""
    try:
        return err.read()
    except (OSError, http.client.HTTPException):
        return b""
    finally:
        err.close()


def _headers(message) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in message.items():
        name = name.lower()
        out[name] = f"{out[name]}, {value}" if name in out else value
    return out


def _without_query(url: str) -> str:
    """The URL without its query string, for messages: Shufersal's links carry a signature there."""
    return urllib.parse.urlsplit(url)._replace(query="", fragment="").geturl()

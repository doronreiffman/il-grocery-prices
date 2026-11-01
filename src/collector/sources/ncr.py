"""NCR's "Published Prices" portal (Rami Levy, Osher Ad, Yochananof): a web login with the chain's
published username and an empty password, then the one directory, listed as JSON.

What the portal does (docs/portals.md, "Rami Levy, through NCR", seen 2026-10-31):

- `GET /login` serves the login form and a `<meta name="csrftoken">`. The session lives in the
  `cftpSID` cookie, which the chain's Http keeps.
- `POST /login/user` with `r=`, the username, an empty password, `Submit=Sign in` and the login page's
  token answers 302 to `/file`, the file browser (`/file/` counts too, ruling R22). Landing anywhere
  else, or on a page showing the login form, is the portal refusing the login: Blocked (a failed login
  was not tried; the probe read it so).
- The file browser carries a second, fresh token (the listing's), the directory (`cd`, `/`) and the
  listing's page size (`dtDisplayLength`, in the HTML-escaped JSON of `data-cftp`; 100000, 5000 and
  10000 in three sessions).
- `POST /file/json/dir` with DataTables 1.9's server-side parameters answers JSON: `aaData`, the
  entries, each naming its file in `fname`, and `iTotalDisplayRecords`, the total. Fewer entries than
  the total means asking again from `iDisplayStart` = the entries received (ruling R18). A name an
  earlier answer already sent means the server is not paging (ruling R21): ListingUnreadable.
- At the root a file downloads from `GET /file/d/<fname>`, in the session.

The listing reads the whole directory and checks every name before giving the first.
"""
import json
import urllib.parse
from collections.abc import Iterator
from html.parser import HTMLParser

from collector.http import Blocked, Http
from collector.sources import Listed, ListingUnreadable, Source, checked_name

BASE_URL = "https://url.publishedprices.co.il"
LOGIN_PAGE = f"{BASE_URL}/login"
LOGIN = f"{BASE_URL}/login/user"
FILE_BROWSER = ("/file", "/file/")  # the paths a successful login lands on
LISTING = f"{BASE_URL}/file/json/dir"
DOWNLOAD = f"{BASE_URL}/file/d/"
ROOT = "/"
COLUMNS = (("fname", "true"), ("typeLabel", "false"), ("size", "true"), ("ftime", "true"), ("", "false"))  # (mDataProp, bSortable)
# As jQuery sends them with the listing, and the probe did. The first deployed run sent no Accept and got
# an answer with no aaData (2026-11-01).
AJAX = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"}
SHOWN_KEYS = 10  # an unreadable answer's keys named in its error, at most
KEY_CHARS = 40  # each cut to this length


class NcrSource(Source):
    """`username` is the chain's, as the gov.il list prints it; the password is always empty."""

    def __init__(self, username: str):
        if not username:
            raise ValueError("the NCR login needs the chain's username")
        self.username = username
        self.unparsed = 0

    def listing(self, http: Http, kinds: tuple[str, ...]) -> Iterator[Listed]:
        self.unparsed = 0
        file_page = self._log_in(http)
        listed = []
        for number, fname in enumerate(_fnames(http, file_page), 1):
            name = checked_name(fname, f"the NCR listing, entry {number}")
            if name is None:
                self.unparsed += 1
            elif name.kind in kinds:
                listed.append(Listed(name, DOWNLOAD + fname))
        yield from listed

    def download(self, http: Http, item: Listed) -> bytes:
        return http.get(item.url).body

    def _log_in(self, http: Http) -> "_Page":
        """The file browser, as the login lands on it; Blocked if it lands anywhere else."""
        token = _read(http.get(LOGIN_PAGE).body).csrftoken
        if not token:
            raise ListingUnreadable("the NCR login page carries no csrftoken")
        form = {"r": "", "username": self.username, "password": "", "Submit": "Sign in", "csrftoken": token}
        landed = http.post(LOGIN, form)
        page = _read(landed.body)
        path = urllib.parse.urlsplit(landed.url).path
        if path not in FILE_BROWSER or page.login_form:
            where = path if path not in FILE_BROWSER else "the login form"
            raise Blocked(landed.status, landed.url, f"the NCR login as {self.username!r} was not accepted (it landed on {where})")
        return page


def _fnames(http: Http, file_page: "_Page") -> list[str]:
    """Every entry's file name, page after page until the first answer's total is reached."""
    token = file_page.csrftoken
    if not token:
        raise ListingUnreadable("the NCR file page carries no csrftoken")
    if file_page.cd is None:
        raise ListingUnreadable("the NCR file page names no directory (cd)")
    if file_page.cd != ROOT:
        raise ListingUnreadable(f"the NCR file page's directory is {file_page.cd!r}, not {ROOT}")
    length = _page_size(file_page)
    fnames: list[str] = []
    total = None
    while total is None or len(fnames) < total:
        received, count = _answer(http.post(LISTING, _form(len(fnames), length, token), headers=AJAX).body)
        if total is None:
            total = count
            if total < 1:
                raise ListingUnreadable(f"the NCR listing has no entries (iTotalDisplayRecords {total})")
        if not received:
            raise ListingUnreadable(f"the NCR listing stopped at {len(fnames)} of {total} entries")
        sent = set(fnames)
        repeated = next((fname for fname in received if fname in sent), None)
        if repeated is not None:  # a server ignoring iDisplayStart, which would hide the files after its first page
            raise ListingUnreadable(f"the NCR listing sent {repeated!r} again from iDisplayStart {len(fnames)}")
        fnames += received
    return fnames


def _page_size(file_page: "_Page") -> int:
    if file_page.cftp is None:
        raise ListingUnreadable("the NCR file page carries no data-cftp settings")
    try:
        settings = json.loads(file_page.cftp)
    except ValueError:
        raise ListingUnreadable("the NCR file page's data-cftp settings are not JSON") from None
    length = settings.get("dtDisplayLength") if isinstance(settings, dict) else None
    if type(length) is not int or length < 1:  # not isinstance: JSON's true would pass as 1
        raise ListingUnreadable(f"the NCR file page's page size (dtDisplayLength) is {length!r}")
    return length


def _form(start: int, length: int, token: str) -> dict[str, str]:
    """The listing request, as the page's cftp.file.min.js sends it (docs/portals.md), in its order."""
    form = {"sEcho": "1", "iColumns": str(len(COLUMNS)), "sColumns": "," * (len(COLUMNS) - 1),
            "iDisplayStart": str(start), "iDisplayLength": str(length)}
    for i, (data, sortable) in enumerate(COLUMNS):
        form |= {f"mDataProp_{i}": data, f"sSearch_{i}": "", f"bRegex_{i}": "false",
                 f"bSearchable_{i}": "true", f"bSortable_{i}": sortable}
    return form | {"sSearch": "", "bRegex": "false", "iSortingCols": "0", "cd": ROOT, "csrftoken": token}


def _answer(body: bytes) -> tuple[list[str], int]:
    """One listing answer's file names and its total."""
    try:
        data = json.loads(body)
    except ValueError:  # bad JSON, or bytes that are no text
        raise ListingUnreadable("the NCR listing is not JSON") from None
    entries = data.get("aaData") if isinstance(data, dict) else None
    total = data.get("iTotalDisplayRecords") if isinstance(data, dict) else None
    if not isinstance(entries, list) or type(total) is not int:
        raise ListingUnreadable(f"the NCR listing has no aaData list and iTotalDisplayRecords count (it held {_held(data)})")
    fnames = []
    for number, entry in enumerate(entries, 1):
        fname = entry.get("fname") if isinstance(entry, dict) else None
        if not isinstance(fname, str):
            raise ListingUnreadable(f"the NCR listing, entry {number} names no file (fname)")
        fnames.append(fname)
    return fnames, total


def _held(data) -> str:
    """What an answer of another layout held: its type, and an object's keys with their values' types,
    sorted, at most SHOWN_KEYS, each cut to KEY_CHARS and written as ascii() writes it (quoted, with
    control characters and anything outside ASCII escaped), so a key can add no line to the log or the
    email and no character SNS cannot send. Never a value: a token or a session id could be one."""
    if isinstance(data, list):
        return f"a list of {len(data)}"
    if not isinstance(data, dict):
        return f"a {_type(data)}"
    if not data:
        return "an object with no keys"
    keys = sorted(data)
    shown = ", ".join(f"{ascii(key[:KEY_CHARS] + '...' if len(key) > KEY_CHARS else key)}: {_type(data[key])}"
                      for key in keys[:SHOWN_KEYS])
    more = f" and {len(keys) - SHOWN_KEYS} more" if len(keys) > SHOWN_KEYS else ""
    return f"an object with keys {shown}{more}"


def _type(value) -> str:
    """A JSON value's type, in the words the error uses."""
    if value is None:
        return "null"
    return "object" if isinstance(value, dict) else type(value).__name__


def _read(body: bytes) -> "_Page":
    page = _Page()
    page.feed(body.decode("utf-8", "replace"))
    page.close()
    return page


class _Page(HTMLParser):
    """What the NCR pages carry: the first `<meta name="csrftoken">`'s content, the `cd` input's value,
    the `data-cftp` settings (attribute values come unescaped), and whether a form posts to the login."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.csrftoken: str | None = None
        self.cd: str | None = None
        self.cftp: str | None = None
        self.login_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "csrftoken" and self.csrftoken is None:
            self.csrftoken = attrs.get("content")
        elif tag == "input" and attrs.get("id") == "cd" and self.cd is None:
            self.cd = attrs.get("value")
        elif tag == "script" and attrs.get("id") == "cftptemplate" and self.cftp is None:
            self.cftp = attrs.get("data-cftp")
        elif tag == "form" and (attrs.get("id") == "login-form" or attrs.get("action") == "/login/user"):
            self.login_form = True

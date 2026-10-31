"""Shufersal's portal: each kind's listing pages, and the signed links on them.

What the portal does (docs/portals.md, "Shufersal", seen 2026-10-31):

- Each kind is a category (CATEGORY), listed 20 rows a page at
  `/FileObject/UpdateCategory?catID=<n>&storeId=0&page=<p>`: an HTML table whose rows hold eight
  cells, the first with the download link, the seventh with the file name without `.gz`.
- A page past the last returns the last page again, so no page ever comes back empty: the listing
  reads page 1, then pages 2 to the one page 1's `>>` link names. A category that fits on one page
  has no pager. A page with no rows means the portal changed: ListingUnreadable, never "nothing
  published".
- Each link is signed and expires (`se=`, UTC) 30 minutes after its page was served. The listing reads
  a page only once the caller has taken the previous page's rows, so the run loop downloads each
  page's files before the next page is read. A link that is not https on the file host, or does not
  name its row's file, means the portal changed: ListingUnreadable, and nothing on that page is
  fetched.
- A 403 from the file host from two minutes before the link's `se=` on is the link expiring, not a
  block (ruling R17: the slack covers Azure's clock running ahead of ours): download reads the
  category again for a fresh link and fetches it once. Any other refusal is a block.
"""
import urllib.parse
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from collector.http import Blocked, Http, HttpError
from collector.names import parse_file_name
from collector.sources import Listed, ListingUnreadable, Source

BASE_URL = "https://prices.shufersal.co.il"
FILE_HOST = "pricesprodpublic.blob.core.windows.net"
CATEGORY = {"Price": 1, "PriceFull": 2, "Promo": 3, "PromoFull": 4, "Stores": 5}
CELLS = 8  # link, update time, size, type, category, branch, file name, row number
NAME_CELL = 6
LAST_PAGE = ">>"  # the pager's link to the last page
EXPIRY = "%Y-%m-%dT%H:%M:%SZ"  # se=, as the links carry it
EXPIRY_SLACK = timedelta(seconds=120)  # a 403 this long before se= is already expiry (ruling R17)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShufersalSource(Source):
    """`now` is the clock a link's `se=` is compared with; it must give aware datetimes."""

    def __init__(self, now: Callable[[], datetime] = _utc_now):
        self._now = now
        self.unparsed = 0

    def listing(self, http: Http, kinds: tuple[str, ...]) -> Iterator[Listed]:
        self.unparsed = 0
        for kind in kinds:
            for name_cell, link in _rows(http, kind):
                name = parse_file_name(name_cell)
                if name is None:
                    self.unparsed += 1
                elif name.kind in kinds:
                    yield Listed(name, link)

    def download(self, http: Http, item: Listed) -> bytes:
        """The body of `item`. On its link expiring, the item's category is read again from page 1 to
        the page that lists the file, and the fresh link is fetched once; HttpError if the file is no
        longer listed, ListingUnreadable if the listing no longer reads."""
        try:
            return http.get(item.url).body
        except Blocked as block:
            if not self._expired(block):
                raise
        return http.get(_fresh_link(http, item)).body

    def _expired(self, block: Blocked) -> bool:
        """Whether `block` is the file host refusing a link from EXPIRY_SLACK before its `se=` on."""
        if block.status != 403 or not _on_file_host(urllib.parse.urlsplit(block.url)):
            return False
        expires = _expiry(block.url)
        return expires is not None and expires - EXPIRY_SLACK <= self._now()


def _fresh_link(http: Http, item: Listed) -> str:
    for name_cell, link in _rows(http, item.name.kind):
        if name_cell == item.name.raw:
            return link
    raise HttpError(f"{item.name.raw}: its link expired and the {item.name.kind} listing no longer lists it")


def _rows(http: Http, kind: str) -> Iterator[tuple[str, str]]:
    """(file name, download link) for each row of `kind`'s pages, a page's rows all checked before
    the first of them is given."""
    for page, grid in _pages(http, kind):
        rows = []
        for number, cells in enumerate(grid.rows, 1):
            where = f"{kind} page {page}, row {number}"
            if len(cells) != CELLS:
                raise ListingUnreadable(f"{where}: {len(cells)} cells, not {CELLS}")
            name = cells[NAME_CELL].text
            rows.append((name, _checked_link(cells[0].href, name, where)))
        yield from rows


def _pages(http: Http, kind: str) -> Iterator[tuple[int, "_Grid"]]:
    """`kind`'s pages in order, each read when the caller asks for it."""
    first = _page(http, kind, 1)
    last = _last_page(first, kind)
    yield 1, first
    for page in range(2, last + 1):
        yield page, _page(http, kind, page)


def _page(http: Http, kind: str, page: int) -> "_Grid":
    url = f"{BASE_URL}/FileObject/UpdateCategory?catID={CATEGORY[kind]}&storeId=0&page={page}"
    grid = _Grid()
    grid.feed(http.get(url).body.decode("utf-8", "replace"))
    grid.close()
    if not grid.rows:
        raise ListingUnreadable(f"{kind} page {page}: no rows")
    return grid


def _last_page(first: "_Grid", kind: str) -> int:
    """The last page, as page 1's pager names it; 1 when there is no pager."""
    if not first.pager:
        return 1
    if first.last_href is None:
        raise ListingUnreadable(f"{kind} page 1: the pager names no last page")
    pages = urllib.parse.parse_qs(urllib.parse.urlsplit(first.last_href).query).get("page", [])
    if len(pages) != 1 or not pages[0].isdecimal():
        raise ListingUnreadable(f"{kind} page 1: the pager's last-page link does not name one page number"
                                f" (page={','.join(pages)})")
    return int(pages[0])


def _checked_link(href: str | None, name: str, where: str) -> str:
    """`href` if it is an https link on the file host naming `<name>.gz`; else ListingUnreadable. The
    message names the host, never the signed query."""
    if not href:
        raise ListingUnreadable(f"{where}: no download link")
    malformed = f"{where}: the download link is malformed"  # urllib would raise ValueError, outside Http's handling
    if not (href.isascii() and href.isprintable()) or " " in href:
        raise ListingUnreadable(malformed)
    try:
        parts = urllib.parse.urlsplit(href)
    except ValueError:
        raise ListingUnreadable(malformed) from None
    if not _on_file_host(parts):
        found = f"{parts.scheme}://{parts.netloc}" if parts.scheme else "a relative path"
        raise ListingUnreadable(f"{where}: the download link is on {found}, not on https://{FILE_HOST}")
    linked = parts.path.rsplit("/", 1)[-1]
    if linked != f"{name}.gz":
        raise ListingUnreadable(f"{where}: the download link names {linked}, not {name}.gz")
    return href


def _on_file_host(parts: urllib.parse.SplitResult) -> bool:
    return parts.scheme == "https" and parts.netloc == FILE_HOST


def _expiry(url: str) -> datetime | None:
    """A signed link's `se=` time, read as UTC; None if it has none in the shape the links carry."""
    values = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("se", [])
    try:
        return datetime.strptime(values[0], EXPIRY).replace(tzinfo=timezone.utc)
    except (IndexError, ValueError):
        return None


@dataclass
class _Cell:
    text: str = ""
    href: str | None = None  # the cell's first link


class _Grid(HTMLParser):
    """A listing page read: the file table's body rows, whether it has a pager (a <tfoot>), and the
    pager's `>>` link."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[_Cell]] = []
        self.pager = False
        self.last_href: str | None = None
        self._section: str | None = None  # "tbody" or "tfoot" while inside one
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None
        self._text: list[str] | None = None  # the text of the cell or pager link being read
        self._href: str | None = None  # the pager link's

    def handle_starttag(self, tag, attrs):
        if tag in ("tbody", "tfoot"):
            self._section = tag
            self.pager = self.pager or tag == "tfoot"
        elif tag == "tr" and self._section == "tbody":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell, self._text = _Cell(), []
        elif tag == "a" and self._cell is not None:
            self._cell.href = self._cell.href or dict(attrs).get("href")
        elif tag == "a" and self._section == "tfoot":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_endtag(self, tag):
        if tag == self._section:
            self._section = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "td" and self._cell is not None:
            self._cell.text = "".join(self._text).strip()
            self._row.append(self._cell)
            self._cell, self._text = None, None
        elif tag == "a" and self._section == "tfoot" and self._text is not None:
            if "".join(self._text).strip() == LAST_PAGE and self.last_href is None:
                self.last_href = self._href
            self._text = None

    def handle_data(self, data):
        if self._text is not None:
            self._text.append(data)

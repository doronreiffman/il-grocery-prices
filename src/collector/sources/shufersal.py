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
- A page took up to 39 s from il-central-1 on 2026-11-01 (docs/operations.md, Deploy step 6), so a
  category's 21 pages read again could outlast Lambda's 900 s. Both the listing and the refresh ask the run's time check before
  each page, and the refresh again before the fresh link's download: OutOfTime, naming the file and
  where it stopped.
- Each page the listing reads is reported (`on_page`, a PageRead) once every row on it is checked, before its first
  row is given: its rows, first and last name, the last page its pager names, the seconds its successful request took
  and whether its names are in order. Only page 1's pager sets how far the listing reads, and only page 1's has been
  seen: a later page's is read leniently and recorded, never a stop. The last row given from each page carries
  `ends_page`.
- The run loop says where each kind starts (Start; docs/shufersal-resume.md, section 2): any detour pages first, once
  each; page 1; on a resume, the resume page again (the last page, when the list now ends before it), stepping back a
  page at a time, no further than page 2, while the page's first name sorts after the furthest name earlier runs took;
  then on to the last page.
- A request for a listing page, the listing's or the refresh's, that passes the socket wait (HttpTimeout) is made again,
  up to PAGE_TRIES requests in all, each later try after the run's time check, a pause of RETRY_PAUSE and the time
  check again, so a pause is never taken without time to spare; any other failure, a block and a page that does not
  read are raised at once (docs/shufersal-page-retry.md). Each timed-out try is logged at WARNING and reported
  (`on_timeout`, a PageTimeout; the refresh reports none), a page read records the requests it took (`tries`), and a
  page whose every try timed out raises an HttpError naming the page and the tries.
"""
import itertools
import logging
import time
import urllib.parse
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from collector.http import Blocked, Http, HttpError, HttpTimeout
from collector.names import parse_file_name
from collector.sources import (Listed, ListingUnreadable, OutOfTime, PagedSource, PageRead, PageTimeout, Start,
                               never_short)

BASE_URL = "https://prices.shufersal.co.il"
FILE_HOST = "pricesprodpublic.blob.core.windows.net"
CATEGORY = {"Price": 1, "PriceFull": 2, "Promo": 3, "PromoFull": 4, "Stores": 5}
CELLS = 8  # link, update time, size, type, category, branch, file name, row number
NAME_CELL = 6
LAST_PAGE = ">>"  # the pager's link to the last page
EXPIRY = "%Y-%m-%dT%H:%M:%SZ"  # se=, as the links carry it
EXPIRY_SLACK = timedelta(seconds=120)  # a 403 this long before se= is already expiry (ruling R17)
PAGE_TRIES = 3  # requests for one listing page: the first and up to two more, each after one that timed out
RETRY_PAUSE = 10.0  # seconds before a second or third try, with the time checked before and after it

Row = tuple[str, str]  # a listing row's file name, as listed (without .gz), and its download link

log = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShufersalSource(PagedSource):
    """`now` is the clock a link's `se=` is compared with; it must give aware datetimes. `timer` times each listing
    page's request, in seconds; only differences between its readings count (a monotonic clock). `sleep` takes the
    pause before a timed-out page's next try."""

    def __init__(self, now: Callable[[], datetime] = _utc_now, timer: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._now = now
        self._timer = timer
        self._sleep = sleep
        self.unparsed = 0

    def listing(self, http: Http, kinds: tuple[str, ...], short_of_time: Callable[[], bool] = never_short,
                starts: Mapping[str, Start] | None = None,
                on_page: Callable[[PageRead], None] | None = None,
                on_timeout: Callable[[PageTimeout], None] | None = None) -> Iterator[Listed]:
        self.unparsed = 0
        for kind in kinds:
            start = (starts or {}).get(kind, Start())
            for _, rows in _pages(http, kind, short_of_time, start, on_page, on_timeout, self._timer, self._sleep):
                yield from self._given(rows, kinds)

    def _given(self, rows: list[Row], kinds: tuple[str, ...]) -> list[Listed]:
        """The items a page's rows give: those whose names parse and are of `kinds`, the last of them ending the page
        whatever rows after it were skipped; names that do not parse are counted in `unparsed`."""
        given = []
        for name_cell, link in rows:
            name = parse_file_name(name_cell)
            if name is None:
                self.unparsed += 1
            elif name.kind in kinds:
                given.append(Listed(name, link))
        if given:
            given[-1] = replace(given[-1], ends_page=True)
        return given

    def download(self, http: Http, item: Listed, short_of_time: Callable[[], bool] = never_short) -> bytes:
        """The body of `item`. On its link expiring, the item's category is read again from page 1 to
        the page that lists the file, and the fresh link is fetched once; HttpError if the file is no
        longer listed, ListingUnreadable if the listing no longer reads, OutOfTime if `short_of_time`
        says so before a page, before a later try of a page, or before the fresh link's download."""
        try:
            return http.get(item.url).body
        except Blocked as block:
            if not self._expired(block):
                raise
        try:
            link = _fresh_link(http, item, short_of_time, self._timer, self._sleep)
        except OutOfTime as stop:
            raise OutOfTime(f"{item.name.raw}: its link expired; stopped {stop}") from None
        if short_of_time():
            raise OutOfTime(f"{item.name.raw}: its link expired; stopped before the fresh link's download")
        return http.get(link).body

    def _expired(self, block: Blocked) -> bool:
        """Whether `block` is the file host refusing a link from EXPIRY_SLACK before its `se=` on."""
        if block.status != 403 or not _on_file_host(urllib.parse.urlsplit(block.url)):
            return False
        expires = _expiry(block.url)
        return expires is not None and expires - EXPIRY_SLACK <= self._now()


def _fresh_link(http: Http, item: Listed, short_of_time: Callable[[], bool], timer: Callable[[], float],
                sleep: Callable[[float], None]) -> str:
    """The fresh link to `item`, read from its category from page 1 on (a fresh pass, its pages and timed-out tries
    reported to no one: it serves one download, not the listing) to the page that lists it."""
    for _, rows in _pages(http, item.name.kind, short_of_time, Start(), None, None, timer, sleep):
        for name_cell, link in rows:
            if name_cell == item.name.raw:
                return link
    raise HttpError(f"{item.name.raw}: its link expired and the {item.name.kind} listing no longer lists it")


def _pages(http: Http, kind: str, short_of_time: Callable[[], bool], start: Start,
           on_page: Callable[[PageRead], None] | None, on_timeout: Callable[[PageTimeout], None] | None,
           timer: Callable[[], float], sleep: Callable[[float], None]) -> Iterator[tuple[PageRead, list[Row]]]:
    """`kind`'s pages whose rows are given, in the order `start` sets (`_reads`), each read when the caller asks for
    it, once `short_of_time` says there is time (OutOfTime otherwise). Every page read is reported to `on_page` before
    its rows are given; a page read while stepping back is reported, and its rows are not given. Each timed-out try of
    a page is reported to `on_timeout` (`_page_body`)."""
    report = on_page or _unreported
    reader = _PageReader(http, kind, short_of_time, timer, sleep, on_timeout or _unreported)
    for record, rows, given in _reads(reader, start):
        report(record)
        if given:
            yield record, rows


def _reads(read: "_PageReader", start: Start) -> Iterator[tuple[PageRead, list[Row], bool]]:
    """Each page `read` reads, in the order `start` sets, with whether its rows are given:
    1. each detour page, once, in the order given (a file that failed there is tried again: a detour, not a restart);
    2. page 1, whose pager names the last page;
    3. on a resume (`start.page` past 1, on a list of more than one page): the resume page again (one page of overlap,
       for fresh links to the files an earlier run never reached), or the last page when the list now ends before it;
       then, while the page read is past page 2 and its first name sorts after `start.furthest`, the page before it:
       files that sorted before the furthest name left the list since, so that name now sits on an earlier page. (Files
       newly listed before it push it to a later page instead, which reading on from the resume page covers with no
       step back.) A page stepped back from gives no rows;
    4. every page after the one whose rows were given last, to the last page; a page stepped back over is read again
       when reached, so its links are fresh and one page at a time stays the rule."""
    for page in start.detours:
        record, rows = read(page)
        yield record, rows, True
    first, rows = read(1)
    yield first, rows, True
    last = first.last_page or 1
    at = min(start.page, last)  # the page the reading goes on from: the resume page, 1 on a fresh pass
    if at > 1:
        record, rows = read(at)
        while at > 2 and record.first > start.furthest:
            yield record, rows, False
            at -= 1
            record, rows = read(at)
        yield record, rows, True
    for page in range(at + 1, last + 1):
        record, rows = read(page)
        yield record, rows, True


def _unreported(record: PageRead | PageTimeout) -> None:
    """The report of a caller that keeps no record of pages or of timed-out tries."""


class _PageReader:
    """One kind's pages for one pass: each page read, checked and recorded, its order checked against the page read
    just before it."""

    def __init__(self, http: Http, kind: str, short_of_time: Callable[[], bool], timer: Callable[[], float],
                 sleep: Callable[[float], None], on_timeout: Callable[[PageTimeout], None]):
        self.http, self.kind, self.short_of_time, self.timer = http, kind, short_of_time, timer
        self.sleep, self.on_timeout = sleep, on_timeout
        self.before: PageRead | None = None  # the page read just before

    def __call__(self, page: int) -> tuple[PageRead, list[Row]]:
        rows, grid, seconds, tries = _read_page(self.http, self.kind, page, self.short_of_time, self.timer, self.sleep,
                                                self.on_timeout)
        names = [name for name, _ in rows]
        record = PageRead(self.kind, page, len(rows), names[0], names[-1], _named_last_page(grid, self.kind, page),
                          round(seconds, 1), _in_order(names, self.before, page), tries)
        self.before = record
        return record, rows


def _read_page(http: Http, kind: str, page: int, short_of_time: Callable[[], bool], timer: Callable[[], float],
               sleep: Callable[[float], None],
               on_timeout: Callable[[PageTimeout], None]) -> tuple[list[Row], "_Grid", float, int]:
    """Page `page` of `kind`'s listing, requested once `short_of_time` says there is time and again on a timeout
    (`_page_body`): its rows, every one checked before any is returned; the page as read, for its pager; the seconds
    the successful try's request took, Http's pause before it included (the run's first request has none), the failed
    tries and the pauses between them left out; and the requests it took."""
    url = f"{BASE_URL}/FileObject/UpdateCategory?catID={CATEGORY[kind]}&storeId=0&page={page}"
    body, seconds, tries = _page_body(http, url, kind, page, short_of_time, timer, sleep, on_timeout)
    grid = _Grid()
    grid.feed(body.decode("utf-8", "replace"))
    grid.close()
    if not grid.rows:
        raise ListingUnreadable(f"{kind} page {page}: no rows")
    rows = []
    for number, cells in enumerate(grid.rows, 1):
        where = f"{kind} page {page}, row {number}"
        if len(cells) != CELLS:
            raise ListingUnreadable(f"{where}: {len(cells)} cells, not {CELLS}")
        name = cells[NAME_CELL].text
        rows.append((name, _checked_link(cells[0].href, name, where)))
    return rows, grid, seconds, tries


def _page_body(http: Http, url: str, kind: str, page: int, short_of_time: Callable[[], bool],
               timer: Callable[[], float], sleep: Callable[[float], None],
               on_timeout: Callable[[PageTimeout], None]) -> tuple[bytes, float, int]:
    """The body of page `page` of `kind`'s listing, at `url`; the seconds the request that got it took; and the
    requests it took. The first try asks `short_of_time`, then sends its request; a try after the first asks it, pauses
    RETRY_PAUSE, asks it again, then sends, so a pause is never taken without time to spare. Each request reads `timer`
    at its start and end only. Short of time: OutOfTime (naming the try when it is not the first), and nothing more is
    paused or sent. A try whose request passes the socket wait (HttpTimeout) is reported to `on_timeout`, logged at
    WARNING and followed by the next, up to PAGE_TRIES in all; after the last, an HttpError naming the page and the
    tries, chained from its timeout. Any other failure, a block included, is raised at once, whatever the try."""
    last = None
    for attempt in range(1, PAGE_TRIES + 1):
        stop = (f"before page {page} of the {kind} listing" if attempt == 1
                else f"before try {attempt} of page {page} of the {kind} listing")
        if attempt > 1:
            if short_of_time():  # a timed-out try can leave too little time for the pause and the manifest
                raise OutOfTime(stop)
            sleep(RETRY_PAUSE)
        if short_of_time():
            raise OutOfTime(stop)
        started = timer()
        try:
            body = http.get(url).body
        except HttpTimeout as timeout:
            last = timeout
            waited = round(timer() - started, 1)
            on_timeout(PageTimeout(kind, page, attempt, waited))
            again = f"; again in {RETRY_PAUSE:g} s" if attempt < PAGE_TRIES else ""
            log.warning("shufersal %s page %d: try %d of %d timed out after %.1f s%s", kind, page, attempt, PAGE_TRIES,
                        waited, again)
            continue
        seconds = timer() - started
        return body, seconds, attempt
    raise HttpError(f"{kind} page {page} timed out on {PAGE_TRIES} tries: {last}") from last


def _in_order(names: list[str], before: PageRead | None, page: int) -> bool:
    """Whether every name sorts at or after the one before it and, when the page read just before was the one numbered
    one less, the first at or after that page's last (a name repeated across the boundary is in order). Pages read out
    of number order are not compared with each other."""
    if not all(earlier <= later for earlier, later in itertools.pairwise(names)):
        return False
    return before is None or before.page != page - 1 or before.last <= names[0]


def _named_last_page(grid: "_Grid", kind: str, page: int) -> int | None:
    """The last page `grid`'s pager names; None when it has no pager (on page 1: a list of one page). Page 1's pager
    sets how far the listing reads and is read strictly (ListingUnreadable when it names no readable last page); a
    later page's is only recorded, None when it names none."""
    if not grid.pager:
        return None
    try:
        return _last_page(grid, kind, page)
    except ListingUnreadable:
        if page == 1:
            raise
        return None


def _last_page(grid: "_Grid", kind: str, page: int) -> int:
    """The last page `grid`'s pager names; ListingUnreadable when it names no readable one."""
    if grid.last_href is None:
        raise ListingUnreadable(f"{kind} page {page}: the pager names no last page")
    pages = urllib.parse.parse_qs(urllib.parse.urlsplit(grid.last_href).query).get("page", [])
    if len(pages) != 1 or not pages[0].isdecimal():
        raise ListingUnreadable(f"{kind} page {page}: the pager's last-page link does not name one page number"
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

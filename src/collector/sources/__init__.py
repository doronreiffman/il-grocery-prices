"""What every portal adapter offers the run loop: a listing of published files, and a download.

An adapter reads one portal (Shufersal's, NCR's or Carrefour's) through the chain's Http, so every
request is identified, paced and stopped by a block (collector.http). It names files as published and
leaves choosing them (that day's, not yet stored) and checking their bodies to the run loop.

The run loop checks its time left before the listing, between its items and before each download (ruling R32). An
adapter that makes requests of its own beyond those (Shufersal's re-read of a category for a fresh link, each answer
of an NCR listing read) asks the check the run lends it, `short_of_time`, before each, and raises OutOfTime when it
says so; the default, for a caller with no time limit, is never short.

A paged adapter (PagedSource: Shufersal's) also reports each listing page it reads (PageRead) and marks the last row
it gives from each page (`Listed.ends_page`), so the run loop can record how far into the list a run got; the run
loop tells it where to start each kind (Start).
"""
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol

from collector.http import Http
from collector.names import FileName, parse_file_name


class ListingUnreadable(Exception):
    """A listing that does not read as the portal's file list: no rows, or a page, row or link of
    another shape. The portal changed: the run fails and alerts, never reads it as "nothing
    published". Neither a block (no latch) nor an HttpError (no retry)."""


class OutOfTime(Exception):
    """The run's time check said short of time before a request the adapter would make on its own; the text says
    where it stopped. The run stops as it does on time: neither a block nor an error."""


def never_short() -> bool:
    """The time check for a caller with no time limit."""
    return False


@dataclass(frozen=True)
class Listed:
    """One file a portal lists: its parsed name and the absolute URL that downloads it."""

    name: FileName
    url: str
    ends_page: bool = False  # the last row a paged listing gives from its page: taking it takes the page to its last row


class Source(Protocol):
    """A portal adapter."""

    unparsed: int  # listed names the last listing skipped because they did not parse; final once it is used up

    def listing(self, http: Http, kinds: tuple[str, ...],
                short_of_time: Callable[[], bool] = never_short) -> Iterator[Listed]:
        """Every file the portal lists whose kind is in `kinds` (names.KINDS spelling), skipping names
        that do not parse (counted in `unparsed`). Raises ListingUnreadable when the listing does not
        read as one, OutOfTime when `short_of_time` says so before a request of its own."""

    def download(self, http: Http, item: Listed, short_of_time: Callable[[], bool] = never_short) -> bytes:
        """The body of `item`, as received; OutOfTime when `short_of_time` says so before a request of its own."""


@dataclass(frozen=True)
class PageRead:
    """One page of a paged listing, as the adapter reports it once the page is read and every row on it checked."""

    kind: str
    page: int
    rows: int
    first: str  # the first row's file name as listed (any date, parsed or not)
    last: str  # the last row's
    last_page: int | None  # the last page this page's pager names; None when it names none
    seconds: float  # the request's time, rounded to 0.1 s (Http's 0.5 s pause included)
    in_order: bool  # every name at or after the one before it, and the first at or after the last of the page before


@dataclass(frozen=True)
class Start:
    """Where a paged listing starts reading a kind."""

    page: int = 1  # 1: a fresh pass; more: after page 1, resume at this page
    furthest: str | None = None  # the furthest name the earlier runs took (the step-back compares with it)
    detours: tuple[int, ...] = ()  # pages read once each, before page 1


class PagedSource(Source):
    """A portal adapter whose listing comes in numbered pages. A plain class, not a Protocol, so the run loop can tell
    a paged adapter with isinstance."""

    def listing(self, http: Http, kinds: tuple[str, ...], short_of_time: Callable[[], bool] = never_short,
                starts: Mapping[str, Start] | None = None,
                on_page: Callable[[PageRead], None] | None = None) -> Iterator[Listed]:
        """As Source.listing, each kind read from `starts[kind]` (Start(), a fresh pass from page 1, when it has none).
        `on_page` is called with each page read, once every row on it is checked and before its first row is given; a
        page that fails a check raises and is not reported. The last row given from each page has `ends_page`."""


UNSAFE = ("/", "\\", "..", "?", "#")  # could leave the folder or end the path


def checked_name(name: str, where: str) -> FileName | None:
    """`name`, a listed file name that a download link is built from, parsed; None if it does not parse
    (the adapter skips it and counts it in `unparsed`, and never fetches it).

    A name holding any of UNSAFE, or any whitespace (which would split the request), raises
    ListingUnreadable naming it, whether or not it parses (ruling R19, as R15 for Shufersal's links).
    A name that is not printable ASCII never parses (names.py reads ASCII only), so it is skipped and
    counted, not a stop (ruling R20)."""
    if any(part in name for part in UNSAFE) or any(char.isspace() for char in name):
        raise ListingUnreadable(f"{where}: the file name {name!r} is not safe to put in a link")
    return parse_file_name(name)

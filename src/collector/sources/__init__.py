"""What every portal adapter offers the run loop: a listing of published files, and a download.

An adapter reads one portal (Shufersal's, NCR's or Carrefour's) through the chain's Http, so every
request is identified, paced and stopped by a block (collector.http). It names files as published and
leaves choosing them (that day's, not yet stored) and checking their bodies to the run loop.

The run loop checks its time left before the listing, between its items and before each download (ruling R32). An
adapter that makes requests of its own beyond those (Shufersal's re-read of a category for a fresh link, each answer
of an NCR listing read) asks the check the run lends it, `short_of_time`, before each, and raises OutOfTime when it
says so; the default, for a caller with no time limit, is never short.
"""
from collections.abc import Callable, Iterator
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

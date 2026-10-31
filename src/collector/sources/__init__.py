"""What every portal adapter offers the run loop: a listing of published files, and a download.

An adapter reads one portal (Shufersal's, NCR's or Carrefour's) through the chain's Http, so every
request is identified, paced and stopped by a block (collector.http). It names files as published and
leaves choosing them (that day's, not yet stored) and checking their bodies to the run loop.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from collector.http import Http
from collector.names import FileName


@dataclass(frozen=True)
class Listed:
    """One file a portal lists: its parsed name and the absolute URL that downloads it."""

    name: FileName
    url: str


class Source(Protocol):
    """A portal adapter."""

    def listing(self, http: Http, kinds: tuple[str, ...]) -> Iterator[Listed]:
        """Every file the portal lists whose kind is in `kinds` (names.KINDS spelling), skipping names
        that do not parse."""

    def download(self, http: Http, item: Listed) -> bytes:
        """The body of `item`, as received."""

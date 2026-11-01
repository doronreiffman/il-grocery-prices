"""Carrefour's portal: one page lists the day's files, as data in its inline script.

What the portal does (docs/portals.md, "Carrefour", seen 2026-10-31):

- `GET https://prices.carrefour.co.il/` shows today's files (the Israel date); no cookies, no tokens.
  The list is not in the markup but in the page's script, as two literals: `const path = '<YYYYMMDD>';`,
  the day's folder, and, on one line, `const files = [...]`, JSON giving each file's `name`, `size`
  and `modified`. No JavaScript needs to run.
- A file downloads from `https://prices.carrefour.co.il/<path>/<name>`.
- The day's folder fills through the night and morning (3 files at 00:07, 575 by evening). A page
  with no files is still a listing that does not read: the run fails and alerts, never "nothing
  published".

The listing checks the path and every name before giving the first file.
"""
import json
import re
from collections.abc import Iterator

from collector.http import Http
from collector.sources import Listed, ListingUnreadable, Source, checked_name

BASE_URL = "https://prices.carrefour.co.il"
PATH = re.compile(r"\bconst path\s*=\s*'([^']*)';")
FILES = re.compile(r"\bconst files\s*=\s*")
DAY = re.compile(r"[0-9]{8}")  # not \d, which takes other scripts' digits too


class CarrefourSource(Source):
    def __init__(self):
        self.unparsed = 0

    def listing(self, http: Http, kinds: tuple[str, ...]) -> Iterator[Listed]:
        self.unparsed = 0
        text = http.get(f"{BASE_URL}/").body.decode("utf-8", "replace")
        folder = _path(text)
        listed = []
        for number, name in enumerate(_names(text), 1):
            parsed = checked_name(name, f"the Carrefour page, file {number}")
            if parsed is None:
                self.unparsed += 1
            elif parsed.kind in kinds:
                listed.append(Listed(parsed, f"{BASE_URL}/{folder}/{name}"))
        yield from listed

    def download(self, http: Http, item: Listed) -> bytes:
        return http.get(item.url).body


def _path(text: str) -> str:
    """The day's folder, `const path`: eight ASCII digits, or ListingUnreadable naming what it is."""
    found = PATH.search(text)
    if found is None:
        raise ListingUnreadable("the Carrefour page has no const path")
    if not DAY.fullmatch(found.group(1)):
        raise ListingUnreadable(f"the Carrefour page's path {found.group(1)!r} is not eight digits")
    return found.group(1)


def _names(text: str) -> list[str]:
    """Each file's name from `const files`; ListingUnreadable unless it is a JSON list of at least one
    object with a name."""
    found = FILES.search(text)
    if found is None:
        raise ListingUnreadable("the Carrefour page has no const files")
    try:
        files, _ = json.JSONDecoder().raw_decode(text, found.end())  # the JSON value there, whatever follows it
    except ValueError:
        raise ListingUnreadable("the Carrefour page's const files is not JSON") from None
    if not isinstance(files, list):
        raise ListingUnreadable("the Carrefour page's const files is not a list")
    if not files:
        raise ListingUnreadable("the Carrefour page lists no files")
    names = []
    for number, file in enumerate(files, 1):
        name = file.get("name") if isinstance(file, dict) else None
        if not isinstance(name, str):
            raise ListingUnreadable(f"the Carrefour page, file {number} has no name")
        names.append(name)
    return names

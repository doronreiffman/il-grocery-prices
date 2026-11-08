"""Published file names: the kind, chain, store and day each one carries.

A file belongs to the day in its name, never to the time it was fetched. The shapes seen
(docs/portals.md), with or without `.gz` / `.xml`:

    PriceFull7290027600007-001-030-20261031-030000   kind, chain, sub-chain, store, date, time
    Stores7290058140886-000-20261031-050500.xml       a Stores file names no store
    pricefull7290058140886-039-202610310517.gz        Rami Levy's store 039: lower case, no
                                                      sub-chain, date and time run together

A name with two groups before the date carries the sub-chain, then the store. With one group
(store 039's names, the Stores files) there is no sub-chain to read, and `sub_chain` is None.

A name is ASCII (ruling R20): a name that parses goes into a download link, and urllib fails on a
non-ASCII path outside Http's handling. Without re.ASCII, `\\d` takes other scripts' digits and
case-folding reads `ſ` (long s) as an s and `ı` (dotless i) as an i.

The hour in a name (`hour_of`) is what the check's record counts each day's update files by (ruling R39): the time
after the date, or store 039's time run on into it. A name whose hour cannot be read is counted as unknown, never
dropped.
"""
import datetime
import re
from dataclasses import dataclass

KINDS = ("Stores", "PriceFull", "PromoFull", "Price", "Promo")

# Longest first: the kind is matched on its own, so "PriceFull..." must not stop at "Price".
_BY_LENGTH = sorted(KINDS, key=len, reverse=True)
_KIND = re.compile("|".join(_BY_LENGTH), re.IGNORECASE | re.ASCII)
_CANONICAL = {kind.lower(): kind for kind in KINDS}
_REST = re.compile(
    r"(?P<chain>\d{13})"
    r"(?P<groups>(?:-\d{1,4})*)"   # sub-chain and store; store 039's names carry the store only
    r"-(?P<day>\d{8})(?:\d{4})?"   # the first YYYYMMDD; store 039's names run on into HHMM
    r"(?:-\d+)?"                   # the time, as a group of its own
    r"(?:\.gz|\.xml)?",
    re.IGNORECASE | re.ASCII,
)
# The time after the date: `-HHMMSS`, or store 039's `HHMM` run on into the date; four digits or more.
_TIME = re.compile(r"-\d{8}-?(?P<hour>\d{2})\d{2,}(?:\.gz|\.xml)?\Z", re.IGNORECASE | re.ASCII)


@dataclass(frozen=True)
class FileName:
    """A parsed name: `raw` as given, `kind` as in KINDS, `store` as published (None for Stores),
    `sub_chain` as published (None unless the name carries a sub-chain and a store)."""

    raw: str
    kind: str
    chain_id: str
    store: str | None
    day: datetime.date
    sub_chain: str | None = None


def parse_file_name(name: str) -> FileName | None:
    """Read a published file name; None for anything that is not one."""
    prefix = _KIND.match(name)
    rest = prefix and _REST.fullmatch(name, prefix.end())
    if not rest:
        return None
    kind = _CANONICAL[prefix.group().lower()]
    groups = rest["groups"].split("-")[1:]
    if kind == "Stores":
        store = None
    elif groups:
        store = groups[-1]
    else:
        return None
    sub_chain = groups[0] if len(groups) == 2 else None
    digits = rest["day"]
    try:
        day = datetime.date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None
    return FileName(raw=name, kind=kind, chain_id=rest["chain"], store=store, day=day,
                    sub_chain=sub_chain)


def hour_of(name: str) -> str | None:
    """The hour of the time in a published name, two digits ("00" to "23"): from `-YYYYMMDD-HHMMSS`, or from store 039's
    `-YYYYMMDDHHMM`. None for anything that is not a published name, a name with no time of four digits or more after
    its date (Shufersal's Stores names carry three), or an hour past 23."""
    clock = _TIME.search(name) if parse_file_name(name) else None
    hour = clock and clock["hour"]
    return hour if hour and int(hour) <= 23 else None

"""Published file names: the kind, chain, store and day each one carries.

A file belongs to the day in its name, never to the time it was fetched. The shapes seen
(docs/portals.md), with or without `.gz` / `.xml`:

    PriceFull7290027600007-001-030-20261031-030000   kind, chain, sub-chain, store, date, time
    Stores7290058140886-000-20261031-050500.xml       a Stores file names no store
    pricefull7290058140886-039-202610310517.gz        Rami Levy's store 039: lower case, no
                                                      sub-chain, date and time run together
"""
import datetime
import re
from dataclasses import dataclass

KINDS = ("Stores", "PriceFull", "PromoFull", "Price", "Promo")

# Longest first: the kind is matched on its own, so "PriceFull..." must not stop at "Price".
_BY_LENGTH = sorted(KINDS, key=len, reverse=True)
_KIND = re.compile("|".join(_BY_LENGTH), re.IGNORECASE)
_CANONICAL = {kind.lower(): kind for kind in KINDS}
_REST = re.compile(
    r"(?P<chain>\d{13})"
    r"(?P<groups>(?:-\d{1,4})*)"   # sub-chain and store; store 039's names carry the store only
    r"-(?P<day>\d{8})(?:\d{4})?"   # the first YYYYMMDD; store 039's names run on into HHMM
    r"(?:-\d+)?"                   # the time, as a group of its own
    r"(?:\.gz|\.xml)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FileName:
    """A parsed name: `raw` as given, `kind` as in KINDS, `store` as published (None for Stores)."""

    raw: str
    kind: str
    chain_id: str
    store: str | None
    day: datetime.date


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
    digits = rest["day"]
    try:
        day = datetime.date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None
    return FileName(raw=name, kind=kind, chain_id=rest["chain"], store=store, day=day)

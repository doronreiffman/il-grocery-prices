"""The chains in version one, and nothing else: which portal each one publishes on, how to reach it,
and the adapter that reads it.

Dropping a chain means deleting its entry here and its schedules; its stored files stay.
"""
from dataclasses import dataclass
from typing import Literal

from collector.sources import Source
from collector.sources.carrefour import CarrefourSource
from collector.sources.ncr import NcrSource
from collector.sources.shufersal import ShufersalSource


@dataclass(frozen=True)
class Chain:
    """`slug` names the chain in storage keys; `portal` picks the adapter; `base_url` is the portal's
    https address with no trailing slash; `username` is the NCR login, None where the portal has no
    login. There is no password: the NCR chains in scope log in with an empty one."""

    slug: str
    name: str
    portal: Literal["shufersal", "ncr", "carrefour"]
    base_url: str
    username: str | None = None


NCR_URL = "https://url.publishedprices.co.il"

# The NCR usernames are the ones the Consumer Protection Authority's chain list prints, saying no
# password is needed and the field can be left empty: https://www.gov.il/he/pages/cpfta_prices_regulations
# (updated 12.08.2026). They are public. The base URLs are the portals docs/portals.md records.
CHAINS: dict[str, Chain] = {chain.slug: chain for chain in (
    Chain("shufersal", "Shufersal", "shufersal", "https://prices.shufersal.co.il"),
    Chain("ramilevy", "Rami Levy", "ncr", NCR_URL, username="RamiLevi"),
    Chain("osherad", "Osher Ad", "ncr", NCR_URL, username="osherad"),
    Chain("carrefour", "Carrefour", "carrefour", "https://prices.carrefour.co.il"),
    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof"),
)}


def source_for(chain: Chain) -> Source:
    """A fresh adapter for `chain`'s portal (it holds its last listing's `unparsed` count)."""
    match chain.portal:
        case "shufersal":
            return ShufersalSource()
        case "ncr":
            return NcrSource(chain.username)
        case "carrefour":
            return CarrefourSource()
    raise ValueError(f"no adapter for the {chain.portal!r} portal")

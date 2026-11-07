"""The chains in version one, and nothing else: which portal each one publishes on, how to reach it,
and the adapter that reads it.

Dropping a chain means deleting its entry here and its schedules; its stored files stay.
"""
from dataclasses import dataclass
from typing import Literal

from collector.names import KINDS
from collector.sources import Source
from collector.sources.carrefour import CarrefourSource
from collector.sources.ncr import NcrSource
from collector.sources.shufersal import ShufersalSource


@dataclass(frozen=True)
class Chain:
    """`slug` names the chain in storage keys; `portal` picks the adapter; `base_url` is the portal's
    https address with no trailing slash; `username` is the NCR login, None where the portal has no
    login. There is no password: the NCR chains in scope log in with an empty one. `timeout` is how
    long the chain's Http waits on one socket operation, in seconds. `kinds` are the file kinds the
    chain's main and retry runs collect, in KINDS order. `polled` are the update kinds its poll runs
    read through the day, in KINDS order; empty until the chain's poll schedules are deployed
    (docs/update-files.md, section 1)."""

    slug: str
    name: str
    portal: Literal["shufersal", "ncr", "carrefour"]
    base_url: str
    username: str | None = None
    timeout: float = 30.0
    kinds: tuple[str, ...] = KINDS
    polled: tuple[str, ...] = ()


NCR_URL = "https://url.publishedprices.co.il"

# The NCR usernames are the ones the Consumer Protection Authority's chain list prints, saying no
# password is needed and the field can be left empty: https://www.gov.il/he/pages/cpfta_prices_regulations
# (updated 12.08.2026). They are public. The base URLs are the portals docs/portals.md records.
# Shufersal's listing pages took 23 to 28 s each from il-central-1 on 2026-11-01 (7 to 9 s from the Mac
# on 2026-10-31), and 30 s cut two runs short: it gets 60. At that speed its update files never finish
# in a morning: its main and retry runs collect its store list and full files only, and the update files
# wait for poll runs (owner, 2026-11-01). How often it publishes them is not known: the one record,
# 2026-11-01, shows batches stamped across stores at about 03:00 and about 10:00, and how often a store
# replaces its file is what rollout step 3 measures. Its `polled` stays empty until its passes are
# scheduled (docs/update-files.md). The other four chains' polls read both update kinds.
CHAINS: dict[str, Chain] = {chain.slug: chain for chain in (
    Chain("shufersal", "Shufersal", "shufersal", "https://prices.shufersal.co.il", timeout=60.0,
          kinds=("Stores", "PriceFull", "PromoFull")),
    Chain("ramilevy", "Rami Levy", "ncr", NCR_URL, username="RamiLevi", polled=("Price", "Promo")),
    Chain("osherad", "Osher Ad", "ncr", NCR_URL, username="osherad", polled=("Price", "Promo")),
    Chain("carrefour", "Carrefour", "carrefour", "https://prices.carrefour.co.il", polled=("Price", "Promo")),
    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof", polled=("Price", "Promo")),
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

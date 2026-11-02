"""The day's record: the rules' result for one day with what went into it (B10, B11), its public form,
and what a rebuild compares with a published day (B12).

The record (B10). One record per run: the day, the basket's version, the run id, the code's
fingerprint (`code_fingerprint`: `collector.handler.code_sha` over every .py file of this package),
the build time in UTC, and "collected by" as given (B11: the time the day's extraction started).
Then, per chain by slug: its included stores, its stores with a file and whether it is in the
ranking (B8); its rank and total, or None (B9); its price for each basket item it lists, by code,
with its stores' lowest and highest price, the number of stores listing the item and how many of
them list it under two codes (B5); the keys of its stores with a file, by number; the files the
extraction read (B1); the run ids of the manifests that stored them (B11); and the extraction's
counts (B3). Then the basket codes that count, in the basket's order, those left out and why, and
the headline, or None. Money is a string with two decimals, rounded half up, for display only: a
total is the sum of the exact medians, rounded once. The day is YYYY-MM-DD. The JSON has its keys
sorted at every level and its Hebrew as written. Nothing here reads the clock, so two runs of one
day over the same inputs and code differ only in run id and build time.

The public day (B10, B12). The record less each chain's store keys, files and manifests (the counts
stay), with `revisions` (empty) and `revised` (None) for the publish step to fill, as JSON-ready
values: lists where the record holds tuples, as a day file reads back. What a rebuild compares with
the published day is the public day less the run's own fields: run id, fingerprint, build time,
revisions and revised.

Manifests (B11). A chain's manifests in the record are those of the day, under
`<manifest dir>/date=<day>/<slug>-<run id>.json`, that stored one of the files the extraction read.
A manifest that found a file already stored ("exists"), or stored it as a conflict copy, does not
count for that file.
"""
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import basket as basket_package
import collector.handler
from basket.basket_file import Basket
from basket.extract import ExtractReport
from basket.rules import ChainDay, ChainResult, DayResult, Headline, LeftOut

CENT = Decimal("0.01")
PRIVATE = ("stores_with_file", "files", "manifests")  # per chain; the public day keeps the counts only
RUN_FIELDS = ("run_id", "code_sha", "built_at", "revisions", "revised")


@dataclass(frozen=True)
class ItemPrice:
    """A chain's price for an item (B5) as money; the stores listing it, and how many of them double-coded."""
    median: str
    low: str
    high: str
    listing: int
    double_coded: int


@dataclass(frozen=True)
class ChainRecord:
    """A chain's day (B8), total and rank (B9), item prices by code, and its inputs: the keys of its stores with a
    file, the files read, the manifests that stored them, and the extraction's counts."""
    included: int
    with_file: int
    in_ranking: bool
    rank: int | None
    total: str | None
    items: dict[str, ItemPrice]
    stores_with_file: tuple[str, ...]
    files: tuple[str, ...]
    manifests: tuple[str, ...]
    extraction: dict[str, int]


@dataclass(frozen=True)
class DayRecord:
    """One run's record of one day; `built_at` an ISO time in UTC, `chains` by slug."""
    day: date
    basket_version: str
    run_id: str
    code_sha: str
    built_at: str
    collected_by: str
    chains: dict[str, ChainRecord]
    items_in: tuple[str, ...]
    left_out: tuple[LeftOut, ...]
    headline: Headline | None


def money(amount: Decimal) -> str:
    """`amount` with two decimals, rounded half up."""
    return str(amount.quantize(CENT, rounding=ROUND_HALF_UP))


def build_record(day: date, basket: Basket, result: DayResult, days: Sequence[ChainDay],
                 store_keys: Mapping[str, tuple[str, ...]], reports: Mapping[str, ExtractReport],
                 manifests: Mapping[str, tuple[str, ...]], run_id: str, code_sha: str, built_at: datetime,
                 collected_by: str) -> DayRecord:
    """The day's record from the rules' result and each chain's day, store keys (`stores_with_file_keys`),
    extraction report and manifests (`manifests_for`), all by slug; the chains in the result's (slug) order.
    `built_at` must carry a time zone."""
    by_slug = {chain_day.slug: chain_day for chain_day in days}
    chains = {slug: _chain_record(by_slug[slug], result.chains[slug], store_keys[slug], reports[slug],
                                  manifests[slug]) for slug in result.chains}
    return DayRecord(day, basket.version, run_id, code_sha, _utc_iso(built_at), collected_by, chains,
                     result.items_in, result.left_out, result.headline)


def _chain_record(chain_day: ChainDay, chain: ChainResult, store_keys: tuple[str, ...], report: ExtractReport,
                  manifests: tuple[str, ...]) -> ChainRecord:
    items = {code: ItemPrice(money(price.median), money(price.low), money(price.high), price.listing,
                             price.double_coded) for code, price in chain.items.items()}
    extraction = {"stores": report.stores, "rows": report.rows, "unreadable_prices": report.unreadable_prices,
                  "repeated": report.repeated, "conflicting": report.conflicting}
    return ChainRecord(chain_day.included, chain_day.with_file, chain_day.in_ranking, chain.rank,
                       None if chain.total is None else money(chain.total), items, tuple(store_keys),
                       tuple(report.files), tuple(manifests), extraction)


def _utc_iso(moment: datetime) -> str:
    # A naive time would be read as this machine's zone: Asia/Jerusalem here, UTC in CI.
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("the build time must carry a time zone")
    return moment.astimezone(timezone.utc).isoformat()


def record_json(record: DayRecord) -> str:
    """The private record as JSON: keys sorted, Hebrew as written, money as strings, the day as YYYY-MM-DD."""
    fields = asdict(record) | {"day": record.day.isoformat(), "headline": _headline(record.headline)}
    return json.dumps(fields, sort_keys=True, indent=1, ensure_ascii=False)


def _headline(headline: Headline | None) -> dict | None:
    if headline is None:
        return None
    return asdict(headline) | {"lowest_total": money(headline.lowest_total),
                               "highest_total": money(headline.highest_total)}


def public_day(record: DayRecord) -> dict:
    """The day file's content: the record without each chain's store keys, files and manifests, with no revisions."""
    public = json.loads(record_json(record))  # lists for tuples, as a published day file reads back
    for chain in public["chains"].values():
        for field in PRIVATE:
            del chain[field]
    return public | {"revisions": [], "revised": None}


def comparable(public: dict) -> dict:
    """What a rebuild compares with a published day (B12): the public day without the run's own fields."""
    return {key: value for key, value in public.items() if key not in RUN_FIELDS}


def manifests_for(manifest_dir: Path, day: date, slug: str, files: Sequence[str]) -> tuple[str, ...]:
    """The run ids, sorted, of the chain's manifests that day that stored any of `files`."""
    wanted = set(files)
    run_ids = []
    for path in (manifest_dir / f"date={day.isoformat()}").glob(f"{slug}-*.json"):
        manifest = json.loads(path.read_text())
        stored = {name for name, file in manifest["files"].items() if file["outcome"] == "stored"}
        if stored & wanted:
            run_ids.append(manifest["run_id"])
    return tuple(sorted(run_ids))


def code_fingerprint() -> str:
    """The fingerprint of this package's code: `code_sha` over its directory."""
    return collector.handler.code_sha(Path(basket_package.__file__).parent)

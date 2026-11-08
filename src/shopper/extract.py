"""One chain's day for the shopper site: its prices, promotions and items tables, in that order, by column
(docs/shopper-site.md, "Build and hosting" item 1 and P10, with its "Changed after the survey", S1; the plan's Task 7
and its second pre-flight's S2, S8 and S18).

In order. First the prices table, as the basket has always extracted it (`basket.extract.extract`, B1 and B3): a
price file that does not read stops the chain there (BadPriceFile), as it always has. Then the day's promotions and
items files an earlier run left in the local folders are removed, so whatever stops this run after its prices, those
folders hold only what it wrote (in Lambda each run's folder is new; on the Mac the hand path's is not). Then the day's
store list
(`basket.stores.chain_stores`): with none on or before the day the chain stops (NoStoreList), its prices table
standing, as the basket run already refuses such a chain. Then the columns (`shopper.columns.members`, over the list's
included stores, B2's store-list half) and each column's counted stores (Call 7): its members with a price file that
counts that day, as the basket counts a chain's stores with a file (`basket.rules.stores_with_file_keys` over the day's
prices table, B2's file-name half), so store 779, on the list in Express and named under Be's 005 in its files, is a
member of Express that is never counted; and the chain's counted stores in no column (`shopper.columns.outside`),
whose promotion files are passed over unread and listed apart (the second pre-flight's S2). Then the promotions table
(`shopper.promos.extract_promotions`), then the items table and the reader's texts table (`shopper.items.write_items`),
every column of the chain in them, empty ones included. Carrefour's columns are those of `table`: the hand-kept
`basket.chains.CARREFOUR_COLUMNS`, unless a test gives its own (S18), to `members`, `outside` and `write_items` alike.

When the promotions cannot be read (P10). A format change (`PromotionFormatChanged`: a field set, a code, a date or an
amount the chain's files were never seen to carry, from the promotions read, or a `MinQty` the items table cannot hold
exactly, from the items table) or a promotion file that does not read (`BadPriceFile`, S8) stops the chain's
promotions, not the chain: no `promotions.parquet` or `texts.parquet` is written (this run's is removed when the items
table refused it), so the folder holds only its `report.json`, naming the error; the items table is written with no
promotions and with `promotions_error`; the error is logged at ERROR; and the run goes on. The error's text is the
chain's slug, then the reader's message, which names the file, the field and its value as far as it knows them
(`dates` and `min_spend` name the field and value alone, so the chain is added here, once). An earlier run's
`promotions.parquet` of the day may still stand in the archive, since nothing there deletes, so every reader takes a
chain's promotion state from the items table's report, never from the promotions folder. Any other error stops the
chain.

Seconds. `timer` times each step: "prices" the prices table; "promotions" the store list, the columns and the
promotions table; "items" the items table, with its second writing when its own check refused the promotions.

    PYTHONPATH=src python -m shopper.extract --data data --day 2026-11-07 [--chains shufersal ...]

writes each chain's three tables under `<data>/tables/` from `<data>/raw/` and prints a line of JSON for each chain:
its prices table's counts and `summary`, counts only, no product name or promotion text.
"""
import argparse
import json
import logging
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from basket.chains import CARREFOUR_COLUMNS, EXCLUDED, SLUGS
from basket.extract import ExtractReport, extract
from basket.pricefile import BadPriceFile
from basket.rules import open_day, stores_with_file_keys
from basket.stores import NoStoreList, chain_stores, included
from shopper.columns import members, outside
from shopper.items import ItemsReport, items_path, texts_path, write_items
from shopper.promofile import PromotionFormatChanged
from shopper.promos import PromoReport, extract_promotions, promotions_path

log = logging.getLogger(__name__)

# The promotions report's counts the run's summary gives, beside how many files it read and passed over.
PROMOTION_COUNTS = ("promotions", "coupons", "gifts", "basket_rewards", "dropped_links", "expired", "before_start",
                    "rows")


@dataclass(frozen=True)
class ChainDayReport:
    """What one chain's day wrote: the three tables' reports (`promotions` None when they were not read) and each
    step's seconds, by "prices", "promotions" and "items"."""
    prices: ExtractReport
    promotions: PromoReport | None
    items: ItemsReport
    seconds: dict[str, float]

    def summary(self) -> dict:
        """The shopper's half of the extract run's summary: the promotions' counts (None when they were not read),
        the error, each column's items, wide items, hole and promotion hole, and the two steps' seconds to a tenth."""
        promo = self.promotions
        counts = None if promo is None else {
            "files": len(promo.files), "passed_over": len(promo.passed_over), "outside": len(promo.outside),
            **{name: getattr(promo, name) for name in PROMOTION_COUNTS}}
        return {"promotions": counts, "promotions_error": self.items.promotions_error,
                "columns": {key: {"items": column.items, "wide": column.wide, "hole": column.hole,
                                  "promo_hole": column.promo_hole} for key, column in self.items.columns.items()},
                "promotion_seconds": round(self.seconds["promotions"], 1),
                "items_seconds": round(self.seconds["items"], 1)}


def _named(slug: str, error: Exception) -> str:
    """The error's text with the chain first, once."""
    text = str(error)
    return text if text.startswith(f"{slug}: ") else f"{slug}: {text}"


def _clear(tables_dir: Path, slug: str, day: date) -> None:
    """Remove the day's promotions and items files an earlier run left in the local folders."""
    promotions, items = promotions_path(tables_dir, slug, day), items_path(tables_dir, slug, day)
    for path in (promotions, texts_path(tables_dir, slug, day), promotions.with_name("report.json"), items,
                 items.with_name("report.json")):
        path.unlink(missing_ok=True)


def _refused(tables_dir: Path, slug: str, day: date, error: Exception) -> str:
    """The promotions folder once the chain's promotions are refused: this run's promotions table removed (the items
    table's refusal comes after it was written), its report naming the error, which is logged at ERROR; the error's
    text."""
    named = _named(slug, error)
    out = promotions_path(tables_dir, slug, day)
    out.unlink(missing_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {"slug": slug, "day": day.isoformat(), "promotions_error": named}
    (out.parent / "report.json").write_text(json.dumps(report, sort_keys=True, indent=1))
    log.error("the promotions of %s on %s could not be read, its prices and items stand: %s", slug, day.isoformat(),
              named)
    return named


def extract_chain_day(raw_dir: Path, slug: str, day: date, tables_dir: Path,
                      timer: Callable[[], float] = time.perf_counter,
                      table: Mapping[str, str] = CARREFOUR_COLUMNS) -> ChainDayReport:
    """Write the chain's prices, promotions and items tables for the day under `tables_dir` from the day's files
    under `raw_dir`; the reports (the module's docstring)."""
    seconds: dict[str, float] = {}
    started = timer()
    prices = extract(raw_dir, slug, day, tables_dir)
    lap = timer()
    seconds["prices"], started = lap - started, lap
    _clear(tables_dir, slug, day)
    stores, _ = chain_stores(raw_dir, slug, day)   # NoStoreList: the prices table stands
    ids = included(stores, slug)
    sub_chains = EXCLUDED[slug].sub_chains
    with open_day(tables_dir, day, [slug]) as con:
        with_file = set(stores_with_file_keys(con, {slug: ids}, {slug: sub_chains})[slug])
    counted = {key: set(column & with_file) for key, column in members(slug, stores, ids, table).items()}
    in_no_column = {store.id for store in outside(slug, stores, ids, table)} & with_file
    promo: PromoReport | None = None
    error: str | None = None
    try:
        promo = extract_promotions(raw_dir, slug, day, counted, tables_dir, in_no_column)
    except (PromotionFormatChanged, BadPriceFile) as refused:
        error = _refused(tables_dir, slug, day, refused)
    lap = timer()
    seconds["promotions"], started = lap - started, lap
    try:
        items = write_items(tables_dir, slug, day, stores, ids, sub_chains, promo, error, table)
    except PromotionFormatChanged as refused:   # a MinQty the items table cannot hold exactly
        promo, error = None, _refused(tables_dir, slug, day, refused)
        items = write_items(tables_dir, slug, day, stores, ids, sub_chains, None, error, table)
    seconds["items"] = timer() - started
    return ChainDayReport(prices=prices, promotions=promo, items=items, seconds=seconds)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write each chain's prices, promotions and items tables for a day.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--chains", nargs="+", choices=SLUGS, default=list(SLUGS))
    args = parser.parse_args(None if argv is None else list(argv))
    for slug in args.chains:
        try:
            report = extract_chain_day(args.data / "raw", slug, args.day, args.data / "tables")
        except (BadPriceFile, NoStoreList) as error:
            print(error, file=sys.stderr)
            return 1
        prices = report.prices
        print(json.dumps({"chain": slug, "day": prices.day, "files": len(prices.files), "stores": prices.stores,
                          "rows": prices.rows, "seconds": round(report.seconds["prices"], 1), **report.summary()},
                         sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

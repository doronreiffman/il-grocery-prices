"""Candidates: the barcodes the basket is chosen from, measured on one day's tables.

A code is a candidate when, over the rows that count that day (the view `rows` of `basket.rules`):
- it is a real GS1 barcode (`basket.barcode.is_gs1`), its codes matched with leading zeros stripped;
- every chain given lists it;
- at every chain, the stores listing it are at least `min_share` (80%) of the chain's stores with a
  file that day;
- its size, each chain's most common readable size as rule B7 picks it (`basket.rules.chain_sizes`), is
  stated by at least `min_stating` (3) chains, and every chain stating one states the same. A count of
  one is no size (`basket.units`), so a chain that says "1 unit" neither states a size nor disagrees.

A candidate carries per chain the name string its rows give the code most often (a tie goes to the
first in plain string order), its coverage (stores listing it over stores with a file) and its price,
the median of rule B5 (`basket.rules.chain_prices`). Candidates are sorted by code. The owner picks the
basket from them; the page never shows these name strings, and the basket's names are written by hand.

The table is a CSV: `code` and `size`, then `<slug>_name`, `<slug>_coverage` and `<slug>_median` for
each chain of `basket.chains.SLUGS` in that order. Coverage is written to two places rounded down, so
1.00 means every store lists the code; the median is written exactly.

    python -m basket.candidates --day 2026-11-02 --raw data/raw --tables data/tables --out data/candidates-2026-11-02.csv
"""
import argparse
import csv
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import duckdb

from basket.chains import EXCLUDED, SLUGS
from basket.rules import apply_filters, chain_prices, chain_sizes, open_day, stores_with_file
from basket.stores import day_store_list, included, read_stores
from basket.units import Size, plain

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Candidate:
    """A code that passed every candidate rule; its agreed size; per chain its name string, coverage and median."""
    code: str
    names: dict[str, str]
    size: Size
    coverage: dict[str, Decimal]
    medians: dict[str, Decimal]


def candidates(con: duckdb.DuckDBPyConnection, with_file: dict[str, int], min_share: Decimal = Decimal("0.8"),
               min_stating: int = 3) -> list[Candidate]:
    """The day's candidates over the chains of `with_file` (each chain's stores with a file), sorted by code."""
    chains = sorted(with_file)
    listing: dict[str, dict[str, int]] = {}
    for code, chain, stores in con.execute(
            "SELECT code_norm, chain, count(DISTINCT store) FROM rows"
            " WHERE gs1 AND chain IN (SELECT unnest(?::VARCHAR[])) GROUP BY ALL", [chains]).fetchall():
        listing.setdefault(code, {})[chain] = stores
    covered = sorted(code for code, listed in listing.items() if listed.keys() == with_file.keys()
                     and all(listed[chain] >= min_share * with_file[chain] for chain in listed))
    sizes = chain_sizes(con, covered)
    prices = chain_prices(con, covered)
    names = _names(con, covered)
    found: list[Candidate] = []
    for code in covered:
        stated = [size for chain in chains if (size := sizes[(chain, code)]) is not None]
        if len(stated) < min_stating or len(set(stated)) != 1:
            continue
        found.append(Candidate(
            code=code, names={chain: names[(chain, code)] for chain in chains}, size=stated[0],
            coverage={chain: Decimal(listing[code][chain]) / with_file[chain] for chain in chains},
            medians={chain: prices[(chain, code)].median for chain in chains}))
    return found


def _names(con: duckdb.DuckDBPyConnection, codes: Sequence[str]) -> dict[tuple[str, str], str]:
    """Per (chain, code) listed in `rows`: the name string of most rows, a tie to the first in plain string order."""
    counted: dict[tuple[str, str], Counter[str]] = {}
    for chain, code, name, count in con.execute(
            "SELECT chain, code_norm, name, count(*) FROM rows WHERE code_norm IN (SELECT unnest(?::VARCHAR[]))"
            " GROUP BY ALL", [list(codes)]).fetchall():
        counted.setdefault((chain, code), Counter())[name] = count
    return {key: min(names, key=lambda name: (-names[name], name)) for key, names in counted.items()}


def write_candidates_csv(cands: Sequence[Candidate], path: Path) -> None:
    """Write the candidate table to `path`, replacing it (see the module's columns)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "size", *(f"{slug}_{column}" for slug in SLUGS
                                           for column in ("name", "coverage", "median"))])
        for cand in cands:
            writer.writerow([cand.code, f"{plain(cand.size.amount)} {cand.size.kind}",
                             *(value for slug in SLUGS for value in (
                                 cand.names[slug], cand.coverage[slug].quantize(CENT, rounding=ROUND_DOWN),
                                 cand.medians[slug]))])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the day's candidate table, for choosing the basket.")
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--tables", type=Path, default=Path("data/tables"))
    parser.add_argument("--out", type=Path, help="default: data/candidates-<day>.csv")
    args = parser.parse_args(argv)
    included_stores: dict[str, set[str]] = {}
    for slug in SLUGS:
        store_list = day_store_list(args.raw, slug, args.day)
        if store_list is None:
            raise SystemExit(f"no store list for chain {slug!r} on or before {args.day.isoformat()}")
        included_stores[slug] = included(read_stores(store_list[0]), slug)
    sub_chains = {slug: EXCLUDED[slug].sub_chains for slug in SLUGS}
    with open_day(args.tables, args.day, SLUGS) as con:
        apply_filters(con, included_stores, sub_chains)
        found = candidates(con, stores_with_file(con, included_stores, sub_chains))
    out = args.out or Path("data") / f"candidates-{args.day.isoformat()}.csv"
    write_candidates_csv(found, out)
    print(f"{len(found)} candidates written to {out}")


if __name__ == "__main__":
    main()

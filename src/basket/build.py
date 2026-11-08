"""The build command: one day's three steps on the Mac, extract, basket and page, and the revision rule (B12).

    PYTHONPATH=src .venv/bin/python -m basket.build --day 2026-11-02

The data folder (`--data`, default `data`) holds the day's raw files under `raw/chain=<slug>/date=<day>/`,
the collector's manifests under `manifests/date=<day>/`, the tables under `tables/` and the private records
under `basket/date=<day>/`. The pages go to the site folder (`--site`, default `site`).

Extract. A chain's table is extracted from its raw files unless it is there already with its `report.json`
and no rebuild is asked; a table kept is not read again, and its counts come from its report. Each
extraction is timed for the printout; no number of the record reads the clock.

Basket. Each chain's store list (`basket.stores.chain_stores`) gives its included stores (B2), the M of
B8; a chain with no list on or before the day stops the build with NoStoreList. The rules price the basket
over the chains' tables (B3 to B9), and the placeholder rows (B4) are counted per chain over its included
stores.

Record (B10, B11). The run id is `<HHMMSS>Z-basket-<4 hex>` of `now`, the build time is `now`, and
"collected by" is the one given, else `now` in Israel time as HH:MM. The record is written once, to
`basket/date=<day>/basket-<run id>.json`; a record already there stops the build with FileExistsError, so
every build of every day is kept, a refused one included.

Publish (B12). With no `days/<day>.json` on the site, the day is published as built. With one, the new
numbers are compared with it (`basket.record.comparable`). Equal: the day file is left as it is and the
index and method pages are rendered from it, so the page goes on showing the day as published, its
"collected by" time and any revision line included. Different: the build stops with RevisionNeeded naming
what differs, unless a one-line reason is given (stripped of the spaces around it; a blank reason, or one
holding a line break, is no reason); then the day file is rewritten with the earlier run added to the end
of `revisions` (its run id, code fingerprint, build time, totals and its own `revised`, None for the day as
first published, which is the first entry) and `revised` set to the reason and the Israel date of `now`. So
every revision's reason stays in the day file: the latest in `revised`, each earlier one in `revisions`.

Pages. The build writes the index and method pages and the marker beside the day file (`basket.page.build_site`).
With `write_pages` false (the shopper site's run, which renders the basket's page as `basket.html` in its own frame and
the basket's method inside its method page; the shopper plan's Task 18 and the second pre-flight's S13) it writes
neither page nor the marker, and still writes `days/<day>.json` unless the published one already holds the numbers.
Either way the outcome carries the day as the pages show it (`public`) and each chain's stores left out by rule
(`exclusions`, by slug), for those pages.

Only `main` reads the time of day, and gives it as `now`; the extraction timer feeds the printout alone.
"""
import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from basket.basket_file import DEFAULT_BASKET, BadBasket, load_basket
from basket.chains import EXCLUDED, SLUGS
from basket.extract import ExtractReport, extract, table_path
from basket.page import build_site, index_headline, write_day_file
from basket.record import (DayRecord, build_record, code_fingerprint, comparable, manifests_for, public_day,
                           record_json)
from basket.rules import (MissingTable, apply_filters, chain_day, chain_prices, chain_sizes, open_day, price_basket,
                          stores_with_file_keys)
from basket.stores import NoStoreList, Store, chain_stores, excluded, included
from collector.run import new_run_id

ISRAEL = ZoneInfo("Asia/Jerusalem")


class RevisionNeeded(Exception):
    """The rebuilt day's numbers differ from the published day file, and no reason was given (B12)."""


@dataclass(frozen=True)
class BuildOutcome:
    """The run's record and where it was written; `unchanged` when the published day file already held its
    numbers, `revised` when it was rewritten with a reason; each chain's extraction time in seconds, None for a
    table kept; the index page's two headline lines; the day as the pages show it (the published day file's when
    unchanged); each chain's stores left out by rule, by slug."""
    record: DayRecord
    unchanged: bool
    revised: bool
    record_path: Path
    extraction_seconds: dict[str, float | None]
    headline_lines: tuple[str, str]
    public: dict
    exclusions: dict[str, list[Store]]


def build_day(day: date, data_dir: Path, site_dir: Path, basket_path: Path, now: datetime, revise: str | None,
              rebuild: bool, chains: Sequence[str] = SLUGS, min_items: int = 25,
              collected_by: str | None = None, write_pages: bool = True) -> BuildOutcome:
    """Extract, price and publish the day over `chains`; `now` must carry a time zone. With `write_pages` false only
    the day file is written (the module's docstring, "Pages")."""
    run_id = new_run_id(now, "basket")  # first: it refuses a naive `now`, which would be read as this machine's zone
    basket = load_basket(basket_path, min_items=min_items)
    raw_dir, tables_dir = data_dir / "raw", data_dir / "tables"
    reports: dict[str, ExtractReport] = {}
    seconds: dict[str, float | None] = {}
    for slug in chains:
        reports[slug], seconds[slug] = _table(raw_dir, slug, day, tables_dir, rebuild)
    stores = {slug: chain_stores(raw_dir, slug, day)[0] for slug in chains}
    included_stores = {slug: included(stores[slug], slug) for slug in chains}
    sub_chains = {slug: EXCLUDED[slug].sub_chains for slug in chains}
    codes = [item.code for item in basket.items]
    with open_day(tables_dir, day, chains) as con:
        apply_filters(con, included_stores, sub_chains)
        store_keys = stores_with_file_keys(con, included_stores, sub_chains)
        days = [chain_day(slug, len(included_stores[slug]), len(store_keys[slug])) for slug in chains]
        result = price_basket(basket, days, chain_prices(con, codes), chain_sizes(con, codes))
        placeholders = _placeholders(con, chains)
    manifests = {slug: manifests_for(data_dir / "manifests", day, slug, reports[slug].files) for slug in chains}
    record = build_record(day, basket, result, days, store_keys, reports, placeholders, manifests, run_id,
                          code_fingerprint(), now,
                          collected_by if collected_by is not None else f"{now.astimezone(ISRAEL):%H:%M}")
    record_path = _write_record(data_dir, record)
    shown, unchanged, revised = _publish(record, site_dir, now, revise)
    exclusions = {slug: excluded(stores[slug], slug) for slug in chains}
    if write_pages:
        build_site(shown, basket, exclusions, site_dir, write_day=not unchanged)
    elif not unchanged:
        write_day_file(shown, site_dir)
    return BuildOutcome(record, unchanged, revised, record_path, seconds, index_headline(shown, basket), shown,
                        exclusions)


def _table(raw_dir: Path, slug: str, day: date, tables_dir: Path, rebuild: bool) -> tuple[ExtractReport, float | None]:
    """The chain's extraction report, extracting its table unless it is there with its report and no rebuild is
    asked; the seconds the extraction took, None for a table kept."""
    table = table_path(tables_dir, slug, day)
    report = table.parent / "report.json"
    if table.is_file() and report.is_file() and not rebuild:
        return ExtractReport(**json.loads(report.read_text())), None
    started = time.perf_counter()
    found = extract(raw_dir, slug, day, tables_dir)
    return found, time.perf_counter() - started


def _placeholders(con: duckdb.DuckDBPyConnection, chains: Sequence[str]) -> dict[str, int]:
    """Per chain: its rows priced at ₪0.01 or less at its included stores (B4)."""
    found = dict(con.execute(
        "SELECT p.chain, count(*) FROM prices p JOIN included i ON i.chain = p.chain AND i.store = p.store"
        " WHERE p.price <= 0.01 GROUP BY p.chain").fetchall())
    return {slug: found.get(slug, 0) for slug in chains}


def _write_record(data_dir: Path, record: DayRecord) -> Path:
    """Write the private record once; FileExistsError when the run's record is there already."""
    path = data_dir / "basket" / f"date={record.day.isoformat()}" / f"basket-{record.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:
        f.write(record_json(record))
    return path


def _publish(record: DayRecord, site_dir: Path, now: datetime, revise: str | None) -> tuple[dict, bool, bool]:
    """B12: the day the pages show, whether the published day file already holds the record's numbers, and
    whether it is revised."""
    public = public_day(record)
    published = site_dir / "days" / f"{record.day.isoformat()}.json"
    if not published.is_file():
        return public, False, False
    previous = json.loads(published.read_text(encoding="utf-8"))
    if comparable(public) == comparable(previous):
        return previous, True, False
    reason = _one_line(revise)
    if reason is None:
        raise RevisionNeeded(f"{published} is published with other numbers: {', '.join(_differing(public, previous))}"
                             " differ. To republish it, give a one-line reason with --revise.")
    earlier = {"run_id": previous["run_id"], "code_sha": previous["code_sha"], "built_at": previous["built_at"],
               "revised": previous["revised"],
               "totals": {slug: chain["total"] for slug, chain in previous["chains"].items()}}
    revised = {"on": now.astimezone(ISRAEL).date().isoformat(), "reason": reason}
    return public | {"revisions": previous["revisions"] + [earlier], "revised": revised}, False, True


def _one_line(revise: str | None) -> str | None:
    """The reason with the spaces around it stripped; None for no reason, a blank one, or one of more than a line."""
    if revise is None:
        return None
    reason = revise.strip()
    if not reason or "\n" in reason or "\r" in reason:
        return None
    return reason


def _differing(new: dict, old: dict) -> list[str]:
    """What differs between two days' numbers: the top-level keys, and inside `chains` the chain and its field or
    item ("chains.osherad.total", "chains.osherad.items.<code>")."""
    new, old = comparable(new), comparable(old)
    found = []
    for key in sorted(new.keys() | old.keys()):
        if new.get(key) == old.get(key):
            continue
        if key != "chains":
            found.append(key)
            continue
        for slug in sorted(new[key].keys() | old[key].keys()):
            one, other = new[key].get(slug, {}), old[key].get(slug, {})
            for field in sorted(one.keys() | other.keys()):
                if one.get(field) == other.get(field):
                    continue
                if field == "items":
                    items, earlier = one.get(field, {}), other.get(field, {})
                    found += [f"chains.{slug}.items.{code}" for code in sorted(items.keys() | earlier.keys())
                              if items.get(code) != earlier.get(code)]
                else:
                    found.append(f"chains.{slug}.{field}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one day's basket page: extract, price, publish (B12).")
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--basket", type=Path, default=DEFAULT_BASKET, help="default: the package's v1")
    parser.add_argument("--min-items", type=int, default=25)
    parser.add_argument("--chains", nargs="+", choices=SLUGS, default=list(SLUGS))
    parser.add_argument("--rebuild", action="store_true", help="extract every chain's table again")
    parser.add_argument("--revise", metavar="REASON", help="republish a published day whose numbers changed")
    parser.add_argument("--collected-by", metavar="HH:MM", help="default: now, in Israel time")
    args = parser.parse_args(argv)
    try:
        outcome = build_day(args.day, args.data, args.site, args.basket, datetime.now(timezone.utc), args.revise,
                            args.rebuild, tuple(args.chains), args.min_items, args.collected_by)
    except (BadBasket, MissingTable, NoStoreList, RevisionNeeded) as error:
        print(error, file=sys.stderr)
        return 1
    for slug, chain in outcome.record.chains.items():
        took = outcome.extraction_seconds[slug]
        done = "table kept" if took is None else f"extracted in {took:.1f} s"
        print(f"{slug}: {done}, {chain.extraction['rows']:,} rows")
    print(*outcome.headline_lines, sep="\n")
    day_file = args.site / "days" / f"{args.day.isoformat()}.json"
    if outcome.unchanged:
        print(f"unchanged: {day_file} already holds these numbers and is left as it is")
    elif outcome.revised:
        print(f"revised: {day_file}, the earlier totals kept under revisions")
    else:
        print(f"published: {day_file}")
    print(f"record: {outcome.record_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

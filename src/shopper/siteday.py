"""The site-day file: one day's numbers as the shopper site publishes them, `site-days/<day>.json`, and the rule that
publishes it (docs/shopper-site.md, "What a visitor sees" 7, Call 8, the anti-goal "a number nobody can reproduce, or
one that changes quietly", and "Changed after the survey", "Where the key lives"; the plan's Task 19 and its
pre-flights' N8, S5 and B2). The basket's day files keep their approved shape; this file is the site's own (Call 8).

What it holds. The day; the run's provenance (run id, code fingerprint, build time in UTC to the second, "collected
by", and B12's `revisions` and `revised`); the inputs: every items table the build read, by its archive key, and the
covered registry it carried forward (None for none); then:

- `columns`, a block per column in `shopper.columns.COLUMNS`' order: its chain and name; its day (a record or not, a
  hole, a promotion hole, its included stores, those with a price file, those counted, those with a promotion file,
  under the floor); its gate, its own, never its chain's (closed in step one: its conditions and which hold, from the
  scorecard); and its counts (the items table's items, those listed across it, those on a promotion listed across it,
  the valid deals running today, and its front page rows).
- `chains`, a block per chain, P10's state: its promotions error, or None, and its items table's key. P10's sentence
  goes on every section of a chain's columns, so it stays per chain. The error is published by its kind, its file and
  its field, never a value (`public_error`; the task review's finding 2): the kind is "file not read" when the message
  is one of `basket.pricefile`'s for a file that does not read, else "format changed"; the file is named only when the
  message names one the collector names, by its published name (`collector.names.parse_file_name` of
  `collector.store.published_name`, as the house reads a stored name: a conflict copy, the published name with a dot
  and 12 hex digits, is the copy read when it is the latest; a published name never holds a "/", so a head holding one,
  a chain's value with a path in it, is never read as a file name), and the field only when the message's
  first word is one of the fields the chains' files are known to carry, or a level of them
  (`shopper.promotions.KNOWN_FIELDS`). Whatever a chain puts in a field or a tag therefore stays out of the public file;
  the whole message, with the value, goes to the run's log and its alert only (the items table's private report and
  `shopper.build.SiteOutcome.promotions_errors`).
- `counts`, the front page's count line: the promotions listed across a column today (distinct by chain and id), the
  products they are on, and the products with a front page row (question A: products are barcodes).
- `front_rows`, the front page's rows in its order, each with every number the row shows: its column and barcode, the
  deal as shown (to the agora) and exact (the fraction's text), per unit or kilogram, "buy N", the 30-day median listed
  price as shown, the gap below it as shown (amount and whole percent, `shopper.words.shown_below`; None when the deal
  as shown is not below), and its conditions from the fields (restrictions, programmes' names, minimum spend). No
  product name or promotion text: the numbers, which the pages show beside the chains' own words.
- `forecasts`, the day's frozen forecasts file as the archive holds it: "frozen" (before the day's cutoff by S3's
  time), "late", or "none" when no file is frozen for the day; its SHA-256, S3's time (UTC to the second, as the
  ledger writes it), whether on time, and its rows. Whether this run wrote the file or met it ("same") is the run's,
  never the day's, so a rerun of an unchanged day compares equal.
- `scorecard` (`shopper.record.scorecard`, which the record page shows and the guard renders again); `scored_days`,
  every day scored to date, for the site check's links to past scores files (the second pre-flight's B2); and
  `out_of_reach`, the frozen days whose window the build's read no longer holds, left unscored (Task 13's ruling).

Every value is JSON-ready, as the file reads back: lists, text, numbers, None. The file is written as the basket's day
files are (`basket.page.render_day`: keys sorted, Hebrew as written).

Publishing (B12). `publish_site_day` is the basket's own rule, `basket.build.publish_day_file`: no published file, the
day as built; one whose numbers are the same, the published day, left as it is (not even written again), so the pages
go on showing it; other numbers, RevisionNeeded naming what differs, unless a one-line reason is given; then the earlier
run goes to the end of `revisions` with its count line's numbers, and `revised` is the reason and the Israel date. What
B12 compares is the file without the run's own fields and provenance, `basket.record.NOT_COMPARED`, imported, never a
second list: `site_day` writes the provenance under exactly those names.
"""
import csv
import gzip
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from pathlib import Path

from basket.archive import kind_key
from basket.build import publish_day_file
from basket.chains import SLUGS
from basket.page import render_day
from basket.record import NOT_COMPARED, comparable, money
from collector.names import parse_file_name
from collector.store import published_name
from shopper.columns import BY_KEY, COLUMNS
from shopper.deals import to_agora
from shopper.freeze import Frozen, utc_text
from shopper.history import ColumnDay
from shopper.pages import Counts, FrontRow, ordered
from shopper.promofile import FieldSets
from shopper.promotions import KNOWN_FIELDS
from shopper.words import shown_below

__all__ = ["NOT_COMPARED", "Inputs", "comparable", "public_error", "publish_site_day", "site_day", "site_day_path",
           "write_site_day"]

# A promotions error's public form (the module's docstring): `basket.pricefile`'s messages for a file that does not
# read, after its name; and the names a message may give as its field, the chains' known fields and their levels.
UNREADABLE = ("the gzip is cut short or corrupt", "the zip is cut short or corrupt", "not XML", "the XML does not parse")
FIELD_NAMES = frozenset({level.name for level in fields(FieldSets)} |
                        {tag for sets in KNOWN_FIELDS.values() for level in fields(FieldSets)
                         for tags in getattr(sets, level.name) for tag in tags})


@dataclass(frozen=True)
class Inputs:
    """What the build read, by archive key: every items table, and the covered registry carried forward (or None)."""
    items_tables: tuple[str, ...]
    registry: str | None


def _column(key: str, today: ColumnDay, report: Mapping, rows: Sequence[FrontRow], scorecard: Mapping) -> dict:
    """A column's block (the module's docstring)."""
    found = report["columns"][key]
    return {"chain": today.slug, "name": BY_KEY[key].name, "record": today.record, "hole": today.hole,
            "promo_hole": today.promo_hole, "included": today.included, "with_file": today.with_file,
            "counted": today.counted, "promo_files": today.promo_files, "under_floor": found["under_floor"],
            "gate": scorecard["columns"][key]["gate"],
            "counts": {"items": found["items"], "wide": found["wide"], "on_promotion": found["on_promotion"],
                       "valid_deals": found["valid_deals"], "front_rows": sum(row.column == key for row in rows)}}


def public_error(slug: str, message: str) -> dict:
    """A chain's promotions error as the site-day file publishes it: its kind, its file and its field, never a value
    (the module's docstring)."""
    rest = message.removeprefix(f"{slug}: ")
    head, said, tail = rest.partition(": ")
    file = None
    published = head if "/" in head else published_name(head)   # a conflict copy's suffix stripped, never a path
    if said and parse_file_name(published) is not None:
        file, rest = published, tail
    word = rest.split(" ", 1)[0]
    return {"kind": "file not read" if rest.startswith(UNREADABLE) else "format changed", "file": file,
            "field": word if word in FIELD_NAMES else None}


def _row(row: FrontRow) -> dict:
    """A front page row's numbers (the module's docstring)."""
    below = shown_below(row.gap)
    deal = row.deal
    return {"column": row.column, "barcode": row.code, "deal": str(to_agora(deal.price)), "deal_exact": str(deal.price),
            "per": deal.per, "buy": str(deal.buy), "median30": money(row.gap.median30),
            "below": None if below is None else str(below[0]), "percent": None if below is None else below[1],
            "restrictions": list(row.restrictions), "programmes": list(row.programmes),
            "min_spend": None if row.min_spend is None else str(row.min_spend)}


def _rows_in(body: bytes) -> int:
    """The forecast rows of a frozen file: its CSV's rows after the header."""
    return sum(1 for _ in csv.reader(io.StringIO(gzip.decompress(body).decode()))) - 1


def _forecasts(frozen: Frozen | None) -> dict:
    """The day's frozen file as the archive holds it (the module's docstring)."""
    if frozen is None:
        return {"status": "none", "sha256": None, "frozen_at": None, "on_time": None, "rows": 0}
    return {"status": "frozen" if frozen.on_time else "late", "sha256": frozen.sha256,
            "frozen_at": utc_text(frozen.frozen_at), "on_time": frozen.on_time, "rows": _rows_in(frozen.body)}


def _error(slug: str, message: str | None) -> dict | None:
    return None if message is None else public_error(slug, message)


def site_day(day: date, run_id: str, code_sha: str, built_at: datetime, collected_by: str, inputs: Inputs,
             column_days: Mapping[tuple[str, date], ColumnDay], chains: Mapping[str, Mapping], counts: Counts,
             rows: Sequence[FrontRow], frozen: Frozen | None, scorecard: Mapping,
             scored_days: Sequence[date] = (), out_of_reach: Sequence[date] = ()) -> dict:
    """The site-day file's content (the module's docstring), JSON-ready: `column_days` holds every column's day,
    `chains` each chain's items report of the day as written (Task 6's `report.json`), by slug; `rows` the front
    page's; `frozen` the day's forecasts file as the archive holds it, or None; `built_at` aware."""
    shown = ordered(rows)
    found = {
        "day": day.isoformat(), "run_id": run_id, "code_sha": code_sha, "built_at": utc_text(built_at),
        "collected_by": collected_by, "revisions": [], "revised": None,
        "inputs": {"items_tables": list(inputs.items_tables), "registry": inputs.registry},
        "columns": {column.key: _column(column.key, column_days[(column.key, day)], chains[column.slug], shown,
                                        scorecard) for column in COLUMNS},
        "chains": {slug: {"promotions_error": _error(slug, chains[slug]["promotions_error"]),
                          "items_table": kind_key("items", slug, day, "items.parquet")} for slug in SLUGS},
        "counts": {"promotions": counts.promotions, "products": counts.products, "below": counts.below},
        "front_rows": [_row(row) for row in shown],
        "forecasts": _forecasts(frozen),
        "scorecard": scorecard,
        "scored_days": sorted(scored.isoformat() for scored in scored_days),
        "out_of_reach": sorted(far.isoformat() for far in out_of_reach),
    }
    return json.loads(json.dumps(found))   # as the file reads back: lists for tuples


def site_day_path(site_dir: Path, day: date) -> Path:
    """site-days/<day>.json under `site_dir`."""
    return site_dir / "site-days" / f"{day.isoformat()}.json"


def _earlier(previous: dict) -> dict:
    """What a revision keeps of the earlier run's figures: its count line's numbers."""
    return {"counts": previous["counts"]}


def publish_site_day(new: dict, site_dir: Path, now: datetime, revise: str | None) -> tuple[dict, bool, bool]:
    """B12 for the site-day file `new` (the module's docstring): the day as the pages show it, whether the published
    file already holds its numbers, and whether it is revised. RevisionNeeded when it differs with no one-line reason."""
    return publish_day_file(new, site_day_path(site_dir, date.fromisoformat(new["day"])), now, revise, _earlier)


def write_site_day(shown: dict, site_dir: Path) -> Path:
    """Write the site-day file under `site_dir`, the folder made as needed; its path."""
    path = site_day_path(site_dir, date.fromisoformat(shown["day"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_day(shown), encoding="utf-8")
    return path

"""The site-day file (`shopper.siteday`; the plan's Task 19): `site-days/<day>.json`, a block per column and one per
chain (the design's Call 8 and "Where the key lives"), published under B12 by the basket's own rule
(`basket.build.publish_day_file`, the second pre-flight's S5).

Column-days, pairs and front rows are built by hand as tests/test_product.py and tests/test_shop_pages.py build them;
the items reports as Task 6 writes them; the forecasts file is tests/test_freeze.py's; the scored days' summaries as
tests/test_record_numbers.py builds them. Names and barcodes are synthetic."""
import json
import os
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import basket.record
from basket.build import RevisionNeeded
from basket.chains import SLUGS
from basket.page import render_day
from basket.record import comparable
from shopper.columns import COLUMNS, columns_of
from shopper.freeze import Frozen
from shopper.items import ColumnReport, ItemsReport
from shopper.measures import depth
from shopper.pages import Counts, ordered
from shopper.record import scorecard
from shopper.siteday import (NOT_COMPARED, Inputs, publish_site_day, site_day, site_day_path, write_site_day)
from shopper.words import shown_below
from test_freeze import forecasts_of, sha
from test_product import DAY, _days
from test_record_numbers import _good_days
from test_shop_pages import _rows

DEAL, SHELI, EXPRESS = "shufersal-deal", "shufersal-sheli", "shufersal-express"
BUILT = datetime(2026, 11, 20, 10, 33, 5, 250000, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 21, 23, 30, tzinfo=timezone.utc)        # 22 November in Israel
INPUTS = Inputs(items_tables=("tables/items/chain=osherad/date=2026-11-19/items.parquet",
                              "tables/items/chain=osherad/date=2026-11-20/items.parquet"),
                registry="tables/covered/date=2026-11-19/covered.parquet")
FROZEN_AT = datetime(2026, 11, 20, 10, 33, 9, tzinfo=timezone.utc)
ERROR = "carrefour: PromoFull7290055700007-001-002-20261120-0800.gz: RewardType 7 not seen in the chain's files"


def _reports(error: str | None = None) -> dict[str, dict]:
    """Each chain's items report of the day as Task 6 writes it (read back from its JSON), every column's counts
    distinct; Carrefour's promotions not read when `error`."""
    reports = {}
    for slug in SLUGS:
        columns = {}
        for column in columns_of(slug):
            n = COLUMNS.index(column)
            columns[column.key] = ColumnReport(
                column=column.key, included=20 + n, with_file=19 + n, hole=False, counted=18 + n, promo_files=17 + n,
                promo_hole=False, items=1000 + n, wide=500 + n, on_promotion=100 + n, valid_deals=90 + n,
                under_floor=column.key == "shufersal-universe")
        failed = error if slug == "carrefour" else None
        report = ItemsReport(slug=slug, day=DAY.isoformat(), columns=columns, outside=[], promotions_error=failed,
                             texts=0, promotions=None)
        reports[slug] = json.loads(json.dumps(asdict(report)))
    return reports


def _card() -> dict:
    """A scorecard in which Deal has three scored days and every other column none, so Deal's gate is its own."""
    return scorecard(_good_days(3, column=DEAL))


def _frozen(on_time: bool = True, status: str = "frozen") -> Frozen:
    body = forecasts_of()
    return Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=FROZEN_AT, on_time=on_time, status=status)


def _site_day(**more) -> dict:
    given = dict(day=DAY, run_id="103305Z-site-abcd", code_sha="c0dec0dec0de", built_at=BUILT, collected_by="11:48",
                 inputs=INPUTS, column_days=_days(holes={(EXPRESS, DAY)}), chains=_reports(ERROR),
                 counts=Counts(3, 2, 1), rows=_rows(), frozen=_frozen(), scorecard=_card(),
                 scored_days=[date(2026, 11, 5), date(2026, 11, 6)], out_of_reach=[date(2026, 8, 1)])
    given.update(more)
    return site_day(**given)


# ---- what the file holds ----

def test_the_site_day_file_has_a_block_per_column_and_per_chain():
    """Call 8 and "Where the key lives": a block per column (its chain and name, its day's state and counts, its gate)
    and a block per chain (P10's state: its promotions error, and its items table's key)."""
    found, reports, card, days = _site_day(), _reports(ERROR), _card(), _days(holes={(EXPRESS, DAY)})
    assert list(found["columns"]) == [column.key for column in COLUMNS]
    assert list(found["chains"]) == list(SLUGS)
    for column in COLUMNS:
        block, today = found["columns"][column.key], days[(column.key, DAY)]
        report = reports[column.slug]["columns"][column.key]
        assert block == {
            "chain": column.slug, "name": column.name, "record": today.record, "hole": today.hole,
            "promo_hole": today.promo_hole, "included": today.included, "with_file": today.with_file,
            "counted": today.counted, "promo_files": today.promo_files, "under_floor": report["under_floor"],
            "gate": card["columns"][column.key]["gate"],
            "counts": {"items": report["items"], "wide": report["wide"], "on_promotion": report["on_promotion"],
                       "valid_deals": report["valid_deals"],
                       "front_rows": sum(row.column == column.key for row in _rows())}}
    assert (found["columns"][EXPRESS]["record"], found["columns"][EXPRESS]["hole"]) == (False, True)
    assert found["columns"]["shufersal-universe"]["under_floor"] is True
    assert [found["columns"][key]["counts"]["front_rows"] for key in (DEAL, SHELI, EXPRESS)] == [1, 1, 0]
    assert found["chains"]["carrefour"] == {
        "promotions_error": ERROR, "items_table": "tables/items/chain=carrefour/date=2026-11-20/items.parquet"}
    assert found["chains"]["osherad"]["promotions_error"] is None


def test_each_columns_gate_is_its_own_never_its_chains():
    """The site check reads a column's gate from its own block (the amendment's "Where the key lives"): Deal's gate
    is Deal's, though Sheli, of the same chain, has none of its days."""
    found, card = _site_day(), _card()
    assert card["columns"][DEAL]["gate"] != card["columns"][SHELI]["gate"]                 # the premise
    for key in (DEAL, SHELI, EXPRESS, "carrefour-market"):
        assert found["columns"][key]["gate"] == card["columns"][key]["gate"]
        assert found["columns"][key]["gate"]["open"] is False
    assert not [slug for slug, block in found["chains"].items() if "gate" in block]


def test_the_day_its_inputs_and_its_provenance():
    found = _site_day()
    assert found["day"] == "2026-11-20"
    assert found["inputs"] == {"items_tables": list(INPUTS.items_tables), "registry": INPUTS.registry}
    assert _site_day(inputs=Inputs(items_tables=(), registry=None))["inputs"] == {"items_tables": [], "registry": None}
    assert (found["run_id"], found["code_sha"], found["built_at"], found["collected_by"]) == (
        "103305Z-site-abcd", "c0dec0dec0de", "2026-11-20T10:33:05Z", "11:48")
    assert (found["revisions"], found["revised"]) == ([], None)


def test_the_provenance_is_what_b12_leaves_out():
    """S5: the site-day file's provenance is written under the names B12's comparison leaves out, which are the
    basket's own, imported (never a second list)."""
    assert NOT_COMPARED is basket.record.NOT_COMPARED
    found = _site_day()
    assert set(NOT_COMPARED) <= set(found)
    other = _site_day(run_id="000000Z-site-0000", code_sha="000000000000", built_at=LATER, collected_by="09:00")
    assert comparable(other) == comparable(found) and other != found


def test_the_count_line_and_the_front_pages_rows_are_its_numbers():
    """Every number on the front page (the design's "Data files"): the count line's three, and each row in the
    page's order, its deal as shown and exact, the 30-day median and the gap below it as shown, its conditions."""
    found = _site_day()
    assert found["counts"] == {"promotions": 3, "products": 2, "below": 1}
    rows = ordered(_rows())
    assert depth(rows[0].gap) > depth(rows[1].gap) and [row.column for row in rows] == [SHELI, DEAL]   # the premise
    assert found["front_rows"] == [
        {"column": SHELI, "barcode": rows[0].code, "deal": "10.00", "deal_exact": "10", "per": "unit", "buy": "1",
         "median30": "20.00", "below": "10.00", "percent": 50, "restrictions": [], "programmes": [], "min_spend": None},
        {"column": DEAL, "barcode": rows[1].code, "deal": "7.90", "deal_exact": "79/10", "per": "unit", "buy": "1",
         "median30": "11.90", "below": "4.00", "percent": 34, "restrictions": [], "programmes": [], "min_spend": None}]
    assert found["front_rows"][1]["below"] == str(shown_below(rows[1].gap)[0])
    conditioned = replace(rows[1], restrictions=("club",), programmes=("מועדון",), min_spend=Decimal("150"))
    held = _site_day(rows=[conditioned])["front_rows"][0]
    assert (held["restrictions"], held["programmes"], held["min_spend"]) == (["club"], ["מועדון"], "150")


def test_the_forecasts_block_names_the_frozen_file():
    """The day's forecasts file as the archive holds it: on time ("frozen") or late, its SHA-256, S3's time to the
    second, and its rows; the run's own status ("same" on a rerun) is the run's, never the file's, so an unchanged rerun
    compares equal (B12)."""
    assert _site_day()["forecasts"] == {"status": "frozen", "sha256": sha(forecasts_of()),
                                        "frozen_at": "2026-11-20T10:33:09Z", "on_time": True, "rows": 3}
    assert _site_day(frozen=_frozen(status="same"))["forecasts"] == _site_day()["forecasts"]
    late = _site_day(frozen=_frozen(on_time=False, status="late"))["forecasts"]
    assert (late["status"], late["on_time"]) == ("late", False)
    assert _site_day(frozen=replace(_frozen(on_time=False), status="same"))["forecasts"]["status"] == "late"
    assert _site_day(frozen=None)["forecasts"] == {"status": "none", "sha256": None, "frozen_at": None,
                                                   "on_time": None, "rows": 0}


def test_the_scorecard_the_days_scored_and_those_out_of_reach():
    """The scorecard the record page shows (the guard renders it again, Task 21); every day scored to date, for the
    site check's links to past scores files (the second pre-flight's B2); the frozen days the read no longer reaches,
    never scored (Task 13's ruling)."""
    found = _site_day()
    assert found["scorecard"] == json.loads(json.dumps(_card()))
    assert found["scored_days"] == ["2026-11-05", "2026-11-06"]
    assert found["out_of_reach"] == ["2026-08-01"]
    assert _site_day(scored_days=[date(2026, 11, 6), date(2026, 11, 5)])["scored_days"] == ["2026-11-05", "2026-11-06"]


def test_the_file_reads_back_as_it_is_built():
    """JSON-ready, so B12 compares it with a published file as read back: the same dict through the file."""
    found = _site_day()
    assert json.loads(render_day(found)) == found


# ---- publishing (B12) ----

def test_an_unchanged_site_day_is_left_as_published(tmp_path):
    site = tmp_path / "site"
    first = _site_day()
    shown, unchanged, revised = publish_site_day(first, site, BUILT, None)
    assert (shown, unchanged, revised) == (first, False, False)
    path = write_site_day(shown, site)
    assert path == site_day_path(site, DAY) == site / "site-days" / "2026-11-20.json"
    published = path.read_bytes()
    assert published == render_day(first).encode()
    os.utime(path, ns=(10**18, 10**18))
    rerun = _site_day(run_id="113000Z-site-ffff", code_sha="ffffffffffff", built_at=LATER, collected_by="12:03",
                      frozen=_frozen(status="same"))
    shown, unchanged, revised = publish_site_day(rerun, site, LATER, "a reason is not needed")
    assert (shown, unchanged, revised) == (first, True, False)        # the day as published, its provenance with it
    assert path.read_bytes() == published and path.stat().st_mtime_ns == 10**18


def test_differing_numbers_need_a_reason(tmp_path):
    site = tmp_path / "site"
    write_site_day(_site_day(), site)
    published = site_day_path(site, DAY).read_bytes()
    changed = _site_day(counts=Counts(4, 2, 1), chains=_reports(None))
    for reason in (None, "", "  \t ", "a fix\nand more"):
        with pytest.raises(RevisionNeeded) as raised:
            publish_site_day(changed, site, LATER, reason)
        message = str(raised.value)
        assert message.startswith(f"{site_day_path(site, DAY)} is published with other numbers: ")
        assert "chains.carrefour.promotions_error, counts differ." in message and "--revise" in message
    assert site_day_path(site, DAY).read_bytes() == published
    shown, unchanged, revised = publish_site_day(changed, site, LATER, " a reader fix ")
    assert (unchanged, revised) == (False, True)
    assert shown["revised"] == {"on": "2026-11-22", "reason": "a reader fix"}     # the Israel date of now; stripped
    assert comparable(shown) == comparable(changed)


def test_a_revision_keeps_the_earlier_run(tmp_path):
    site = tmp_path / "site"
    first = _site_day()
    write_site_day(first, site)
    second = _site_day(counts=Counts(4, 2, 1), run_id="113000Z-site-0001", built_at=LATER)
    shown, _, _ = publish_site_day(second, site, LATER, "a reader fix")
    assert shown["revisions"] == [{"run_id": first["run_id"], "code_sha": first["code_sha"],
                                   "built_at": first["built_at"], "revised": None, "counts": first["counts"]}]
    write_site_day(shown, site)
    third = _site_day(counts=Counts(5, 3, 1), run_id="120000Z-site-0002", built_at=LATER + timedelta(days=1))
    shown, _, revised = publish_site_day(third, site, LATER + timedelta(days=1), "a second fix")
    assert revised and [run["counts"] for run in shown["revisions"]] == [
        first["counts"], {"promotions": 4, "products": 2, "below": 1}]       # the first publication stays first
    assert [run["revised"] for run in shown["revisions"]] == [None, {"on": "2026-11-22", "reason": "a reader fix"}]
    assert shown["revised"] == {"on": "2026-11-23", "reason": "a second fix"}
    assert shown["revisions"][1]["run_id"] == "113000Z-site-0001"

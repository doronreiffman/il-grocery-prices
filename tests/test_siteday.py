"""The site-day file (`shopper.siteday`; the plan's Task 19): `site-days/<day>.json`, a block per column and one per
chain (the design's Call 8 and "Where the key lives"), published under B12 by the basket's own rule
(`basket.build.publish_day_file`, the second pre-flight's S5).

Column-days, pairs and the store types' fronts are built by hand as tests/test_product.py and tests/test_shop_pages.py
build them;
the items reports as Task 6 writes them; the forecasts file is tests/test_freeze.py's; the scored days' summaries as
tests/test_record_numbers.py builds them. Names and barcodes are synthetic."""
import gzip
import json
import os
import re
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone

import pytest

import basket.record
from basket.build import RevisionNeeded
from basket.chains import SLUGS
from basket.page import render_day
from basket.pricefile import BadPriceFile, read_items
from basket.record import comparable
from shopper.columns import COLUMNS, columns_of
from shopper.freeze import Frozen
from shopper.items import ColumnReport, ItemsReport
from shopper.pages import StoreFront, render_store
from shopper.promofile import PromotionFormatChanged
from shopper.promotions import _reward_type
from shopper.record import scorecard
from shopper.siteday import (NOT_COMPARED, Inputs, public_error, publish_site_day, site_day, site_day_path,
                             write_site_day)
from test_freeze import forecasts_of, sha
from test_product import DAY, _days
from test_record_numbers import _good_days
from test_shop_pages import _deal_row, _front

DEAL, SHELI, EXPRESS = "shufersal-deal", "shufersal-sheli", "shufersal-express"
BUILT = datetime(2026, 11, 20, 10, 33, 5, 250000, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 21, 23, 30, tzinfo=timezone.utc)        # 22 November in Israel
INPUTS = Inputs(items_tables=("tables/items/chain=osherad/date=2026-11-19/items.parquet",
                              "tables/items/chain=osherad/date=2026-11-20/items.parquet"),
                registry="tables/covered/date=2026-11-19/covered.parquet")
FROZEN_AT = datetime(2026, 11, 20, 10, 33, 9, tzinfo=timezone.utc)
FILE = "PromoFull7290055700007-001-002-20261120-0800.gz"
ERROR = f"carrefour: {FILE}: RewardType 7 not seen in the chain's files"
PUBLIC_ERROR = {"kind": "format changed", "file": FILE, "field": "RewardType"}


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


def _fronts(checked: int = 4, sheli: int = 2) -> dict[str, StoreFront]:
    """Each store type's front: Sheli's deals (₪3.00 off, then ₪1.50, then more at ₪3.00 when `sheli` asks for more
    than two) of `checked`; Deal's one, with its conditions; every other store type's none; each with its own counts,
    Universe not ready."""
    more = [_deal_row(SHELI, code=str(1000 + n)) for n in range(sheli - 2)]
    rows = {SHELI: [_deal_row(SHELI, code="1"), _deal_row(SHELI, code="2", price="8.50"), *more],
            DEAL: [_deal_row(DEAL, code="3", restrictions=["club"], programmes=["מועדון"], min_spend="150")]}
    return {column.key: _front(column.key, rows=rows.get(column.key, []),
                               checked=checked if column.key == SHELI else len(rows.get(column.key, [])),
                               ready=column.key != "shufersal-universe", promotions=100 + n, products=200 + n)
            for n, column in enumerate(COLUMNS)}


def _site_day(**more) -> dict:
    given = dict(day=DAY, run_id="103305Z-site-abcd", code_sha="c0dec0dec0de", built_at=BUILT, collected_by="11:48",
                 inputs=INPUTS, column_days=_days(holes={(EXPRESS, DAY)}), chains=_reports(ERROR),
                 fronts=_fronts(), frozen=_frozen(), scorecard=_card(),
                 scored_days=[date(2026, 11, 5), date(2026, 11, 6)], out_of_reach=[date(2026, 8, 1)])
    given.update(more)
    return site_day(**given)


# ---- what the file holds ----

def test_the_site_day_file_has_a_block_per_column_and_per_chain():
    """Call 8 and "Where the key lives": a block per column (its chain and name, its day's state and counts, its gate,
    its store page's front) and a block per chain (P10's state: its promotions error, and its items table's key)."""
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
                       "valid_deals": report["valid_deals"]},
            "front": block["front"]}
    assert (found["columns"][EXPRESS]["record"], found["columns"][EXPRESS]["hole"]) == (False, True)
    assert found["columns"]["shufersal-universe"]["under_floor"] is True
    assert [found["columns"][key]["front"]["deals"] for key in (DEAL, SHELI, EXPRESS)] == [1, 2, 0]
    assert "counts" not in found and "front_rows" not in found
    assert found["chains"]["carrefour"] == {
        "promotions_error": PUBLIC_ERROR, "items_table": "tables/items/chain=carrefour/date=2026-11-20/items.parquet"}
    assert found["chains"]["osherad"]["promotions_error"] is None



VALUE = "<b>מבצע</b> \"x\""          # a chain's own text where a value should be: markup and Hebrew


@pytest.mark.parametrize("message, public", [
    (f"{FILE}: PromotionStartDateTime {VALUE!r} is not a date", ("format changed", FILE, "PromotionStartDateTime")),
    (f"carrefour: IsGiftItem {VALUE!r} is not a quantity", ("format changed", None, "IsGiftItem")),
    (f"carrefour: RewardType {VALUE} not seen in the chain's files", ("format changed", None, "RewardType")),
    (f"carrefour: ClubID form not seen in the chain's files: {VALUE!r}", ("format changed", None, "ClubID")),
    (f"{FILE}: MinPurchaseAmount {VALUE!r} is not an amount", ("format changed", FILE, "MinPurchaseAmount")),
    (f"MinQty {VALUE!r} does not fit the items table", ("format changed", None, "MinQty")),
    (f"{FILE}: item fields changed: added ['{VALUE}'], missing []", ("format changed", FILE, "item")),
    (f"{FILE}: {VALUE} after Groups", ("format changed", FILE, None)),
    (f"{VALUE}: RewardType 7 not seen in the chain's files", ("format changed", None, None)),
])
def test_a_promotions_error_is_published_by_its_kind_file_and_field_never_a_value(message, public):
    """Finding 2's ruling: the site-day file says what kind of error, in which file, on which field, and never a value
    from the chain's file; the whole message stays in the run's log and its alert. The file is named only when it is
    one the collector names, the field only when it is one of the fields the chains' files carry, so whatever a chain
    puts in a field or a tag stays out of the public file."""
    text = message if message.startswith("carrefour: ") else f"carrefour: {message}"
    assert public_error("carrefour", text) == dict(zip(("kind", "file", "field"), public))
    found = render_day(_site_day(chains=_reports(text)))
    assert "מבצע" not in found and "<b>" not in found and "\\\"x" not in found
    assert json.loads(found)["chains"]["carrefour"]["promotions_error"] == dict(zip(("kind", "file", "field"), public))


@pytest.mark.parametrize("data", [b"<html><body>\xd7\x9e</body></html>", gzip.compress(b"<Root/>", mtime=0)[:-6],
                                  b"PK\x03\x04 cut", b"<?xml version='1.0'?><Root><a></Root>"])
def test_a_promotion_file_that_does_not_read_is_published_as_such(data):
    """The four ways a file does not read (`basket.pricefile`'s own messages): the kind says so, the file is named, no
    field, and none of the file's bytes."""
    with pytest.raises(BadPriceFile) as refused:
        read_items(FILE, data)
    found = public_error("carrefour", f"carrefour: {refused.value}")
    assert found == {"kind": "file not read", "file": FILE, "field": None}


def test_a_conflict_copy_is_named_by_its_published_name():
    """A conflict copy is stored as its published name with a dot and 12 hex digits (collector.store) and is the copy
    `basket.extract.day_files` reads when it is the latest: its error is published under the published name, a file that
    does not read as such, and a format change with its field (the re-review's fix-round finding)."""
    copy = f"{FILE}.0123456789ab"
    with pytest.raises(BadPriceFile) as refused:
        read_items(copy, b"<html><body>\xd7\x9e</body></html>")
    assert public_error("carrefour", f"carrefour: {refused.value}") == {
        "kind": "file not read", "file": FILE, "field": None}
    assert public_error("carrefour", f"carrefour: {copy}: RewardType {VALUE} not seen in the chain's files") == {
        "kind": "format changed", "file": FILE, "field": "RewardType"}


@pytest.mark.parametrize("value", [f"x/{FILE}: the gzip is cut short or corrupt", f"<b>a</b>/{FILE}: tail"])
def test_a_value_with_a_slash_never_names_a_file(value):
    """A published name never holds a "/": a chain's value that puts a path to a file name before the message's first
    ": " (here a RewardType, through the real reader's check) names no file, and the kind and field stay the message's
    own (the second re-review's fix-round finding)."""
    with pytest.raises(PromotionFormatChanged) as raised:
        _reward_type("carrefour", {"RewardType": value})
    assert public_error("carrefour", str(raised.value)) == {"kind": "format changed", "file": None,
                                                            "field": "RewardType"}


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


def _row_cells(page: str, code: str) -> str:
    return re.search(rf'<tr data-column="[^"]+"[^>]*><th scope="row"><a href="\.\./p/{code}\.html">.*?</tr>', page).group(0)


def test_every_number_on_each_store_page_is_in_the_site_day_file():
    """The design's "Data files": each store type's front block holds every number its page shows, the headline's N
    (its deals, all of them) and M (its checked), whether it is ready, the promotions line's two, and each row the page
    shows (the first 100, none on a hole or a promotion hole: `shopper.pages.shown_rows`) with today's price, the usual
    price, the saving, the days its reason rests on, per unit or kilogram, buy N and its conditions from the fields. No
    product name or promotion text: the numbers, which the pages show beside the chains' own words."""
    fronts, days = _fronts(), _days(holes={(EXPRESS, DAY)})
    found = _site_day(fronts=fronts)
    plain = {"per": "unit", "buy": "1", "restrictions": [], "programmes": [], "min_spend": None}
    assert found["columns"][SHELI]["front"] == {
        "ready": True, "deals": 2, "checked": 4, "promotions": 106, "products": 206,
        "rows": [{"barcode": "1", "today": "7.00", "usual": "10.00", "saving": "3.00", "days": 90, **plain},
                 {"barcode": "2", "today": "8.50", "usual": "10.00", "saving": "1.50", "days": 90, **plain}]}
    deal, = found["columns"][DEAL]["front"]["rows"]
    assert (deal["restrictions"], deal["programmes"], deal["min_spend"]) == (["club"], ["מועדון"], "150")
    assert found["columns"]["shufersal-universe"]["front"]["ready"] is False
    for column in COLUMNS:
        block, page = found["columns"][column.key]["front"], render_store(fronts[column.key], days, DAY, "11:48", (), None)
        assert len(re.findall(r"<tr data-column=", page)) == len(block["rows"])
        assert f"lists {block['promotions']:,} promotions carried by at least half its stores, on {block['products']:,} " in page
        if block["ready"] and column.key != EXPRESS:
            said = (f"today: {block['deals']:,} of {block['checked']:,} promotions" if block["checked"]
                    else "today: no promotions to check")
            assert said in page, column.key
        for row in block["rows"]:
            cells = _row_cells(page, row["barcode"])
            assert all(f"₪{row[name]}" in cells for name in ("today", "usual", "saving")), cells
    # the page's rows, never more: the first 100 of 101, and none on a hole, though the build hands the rows in
    many = _fronts(checked=120, sheli=101) | {EXPRESS: _front(EXPRESS, rows=[_deal_row(EXPRESS)])}
    held = _site_day(fronts=many)["columns"]
    assert (held[SHELI]["front"]["deals"], len(held[SHELI]["front"]["rows"])) == (101, 100)
    assert (held[EXPRESS]["front"]["deals"], held[EXPRESS]["front"]["rows"]) == (1, [])


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
    changed = _site_day(fronts=_fronts(checked=9), chains=_reports(None))
    for reason in (None, "", "  \t ", "a fix\nand more"):
        with pytest.raises(RevisionNeeded) as raised:
            publish_site_day(changed, site, LATER, reason)
        message = str(raised.value)
        assert message.startswith(f"{site_day_path(site, DAY)} is published with other numbers: ")
        assert "chains.carrefour.promotions_error, columns differ." in message and "--revise" in message
    assert site_day_path(site, DAY).read_bytes() == published
    shown, unchanged, revised = publish_site_day(changed, site, LATER, " a reader fix ")
    assert (unchanged, revised) == (False, True)
    assert shown["revised"] == {"on": "2026-11-22", "reason": "a reader fix"}     # the Israel date of now; stripped
    assert comparable(shown) == comparable(changed)


def _numbers(shown: dict) -> dict:
    """What a revision keeps of a run's figures: each column's deals and checked."""
    return {key: {"deals": block["front"]["deals"], "checked": block["front"]["checked"]}
            for key, block in shown["columns"].items()}


def test_a_revision_keeps_the_earlier_run(tmp_path):
    site = tmp_path / "site"
    first = _site_day()
    write_site_day(first, site)
    second = _site_day(fronts=_fronts(checked=9), run_id="113000Z-site-0001", built_at=LATER)
    shown, _, _ = publish_site_day(second, site, LATER, "a reader fix")
    assert shown["revisions"] == [{"run_id": first["run_id"], "code_sha": first["code_sha"],
                                   "built_at": first["built_at"], "revised": None, "front": _numbers(first)}]
    write_site_day(shown, site)
    third = _site_day(fronts=_fronts(checked=11), run_id="120000Z-site-0002", built_at=LATER + timedelta(days=1))
    shown, _, revised = publish_site_day(third, site, LATER + timedelta(days=1), "a second fix")
    assert revised and [run["front"] for run in shown["revisions"]] == [_numbers(first), _numbers(second)]
    assert [run["revised"] for run in shown["revisions"]] == [None, {"on": "2026-11-22", "reason": "a reader fix"}]
    assert shown["revised"] == {"on": "2026-11-23", "reason": "a second fix"}
    assert shown["revisions"][1]["run_id"] == "113000Z-site-0001"


def test_a_revision_keeps_each_columns_deals_and_checked(tmp_path):
    """B12's revision keeps the earlier run's headline numbers, each store type's deals (N) and checked (M), every one
    of the nine, in place of the old front page's count."""
    site = tmp_path / "site"
    first = _site_day(fronts=_fronts(checked=7, sheli=3))
    write_site_day(first, site)
    shown, _, revised = publish_site_day(_site_day(), site, LATER, "a reader fix")
    kept = shown["revisions"][0]["front"]
    assert revised and list(kept) == [column.key for column in COLUMNS]
    assert kept[SHELI] == {"deals": 3, "checked": 7} and kept[DEAL] == {"deals": 1, "checked": 1}
    assert kept["ramilevy"] == {"deals": 0, "checked": 0}

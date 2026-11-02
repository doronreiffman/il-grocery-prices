"""The day record (B10, B11, B12): the private record, its public form, and what a revision compares."""
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import basket
from basket.basket_file import load_basket
from basket.extract import ExtractReport
from basket.record import (ChainRecord, ItemPrice, build_record, code_fingerprint, comparable, manifests_for, money,
                           public_day, record_json)
from basket.rules import ChainDay, ChainPrice, ChainResult, DayResult, Headline, LeftOut
from collector import handler
from collector.run import RunResult, manifest_bytes
from collector.store import manifest_key

BASKET = load_basket(Path(__file__).parent / "baskets" / "basket-test.json", min_items=1)
MILK, PASTA, EGGS = (item.code for item in BASKET.items)
DAY = date(2026, 11, 2)
BUILT = datetime(2026, 11, 2, 11, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))  # 09:30 UTC
RUN_ID = "093000Z-basket-0a1b"
SHA = "0123456789ab"
# Chains a, b and c are in the ranking; d has too few files. EGGS is left out.
DAYS = (ChainDay("d", 5, 1, False), ChainDay("c", 2, 2, True), ChainDay("b", 3, 2, True), ChainDay("a", 4, 4, True))
STORE_KEYS = {"a": ("1", "2", "10", "11"), "b": ("3", "4"), "c": ("1", "2"), "d": ("7",)}
MANIFESTS = {"a": ("030000Z-main-0001",), "b": ("030500Z-main-0002", "060500Z-retry-0003"), "c": ("031000Z-main-0004",),
             "d": ()}


def a_result(milk_at_a: str = "5.90", left_out: LeftOut = LeftOut(EGGS, "coverage", {"a": "1 of 4"})) -> DayResult:
    """The day's result for chains a to d, totals as given (12.405 at a: half up "12.41", half even "12.40")."""
    def at(median: str, low: str, high: str, listing: int, double_coded: int = 0) -> ChainPrice:
        return ChainPrice(Decimal(median), Decimal(low), Decimal(high), listing, double_coded)
    chains = {
        "a": ChainResult(Decimal("12.405"), 2, {MILK: at(milk_at_a, "5.50", "6.40", 3),
                                                PASTA: at("6.505", "6.00", "7.00", 2, double_coded=1),
                                                EGGS: at("12.00", "12.00", "12.00", 1)}),
        "b": ChainResult(Decimal("11.00"), 1, {MILK: at("5.00", "5.00", "5.00", 2), PASTA: at("6.00", "6.00", "6.00", 2)}),
        "c": ChainResult(Decimal("13.60"), 3, {MILK: at("6.50", "6.50", "6.50", 2), PASTA: at("7.10", "7.10", "7.10", 2)}),
        "d": ChainResult(None, None, {MILK: at("4.00", "4.00", "4.00", 1)}),
    }
    return DayResult((MILK, PASTA), (left_out,), chains, Headline("b", Decimal("11.00"), "c", Decimal("13.60"), 24))


def report(slug: str, stores: tuple[str, ...]) -> ExtractReport:
    """An extraction report naming one file per store, with every count set."""
    return ExtractReport(slug=slug, day=DAY.isoformat(), files=[f"PriceFull-{store}.gz" for store in stores],
                         skipped=["PriceFull-old.gz"], stores=len(stores), rows=10 * len(stores), unreadable_prices=1,
                         repeated=2, conflicting=3)


def a_record(result: DayResult | None = None, run_id: str = RUN_ID, code_sha: str = SHA, built_at: datetime = BUILT):
    """The record of `result` (default `a_result()`) over chains a to d, collected by 11:00."""
    return build_record(DAY, BASKET, result or a_result(), DAYS, STORE_KEYS,
                        {slug: report(slug, keys) for slug, keys in STORE_KEYS.items()}, MANIFESTS,
                        run_id, code_sha, built_at, "11:00")


# ---- money ----

def test_money():
    assert money(Decimal("7.2")) == "7.20"
    assert money(Decimal("312.455")) == "312.46"
    assert money(Decimal("0.125")) == "0.13"  # half up; half even would give 0.12
    assert money(Decimal("5.075")) == "5.08"
    assert money(Decimal("10000")) == "10000.00"


# ---- the record (B10, B11) ----

def test_build_record_carries_each_chain_by_slug_with_its_prices_files_and_manifests():
    record = a_record()
    assert list(record.chains) == ["a", "b", "c", "d"]  # by slug, whatever the order of the chain days
    assert record.chains["a"] == ChainRecord(
        included=4, with_file=4, in_ranking=True, rank=2, total="12.41",
        items={MILK: ItemPrice("5.90", "5.50", "6.40", 3, 0), PASTA: ItemPrice("6.51", "6.00", "7.00", 2, 1),
               EGGS: ItemPrice("12.00", "12.00", "12.00", 1, 0)},
        stores_with_file=("1", "2", "10", "11"),
        files=("PriceFull-1.gz", "PriceFull-2.gz", "PriceFull-10.gz", "PriceFull-11.gz"),
        manifests=("030000Z-main-0001",),
        extraction={"stores": 4, "rows": 40, "unreadable_prices": 1, "repeated": 2, "conflicting": 3})
    out = record.chains["d"]
    assert (out.included, out.with_file, out.in_ranking, out.rank, out.total) == (5, 1, False, None, None)
    assert out.items == {MILK: ItemPrice("4.00", "4.00", "4.00", 1, 0)}
    assert record.chains["b"].manifests == ("030500Z-main-0002", "060500Z-retry-0003")


def test_build_record_names_the_day_the_basket_the_run_and_the_result():
    record = a_record()
    assert (record.day, record.basket_version, record.run_id, record.code_sha, record.collected_by) == (
        DAY, "v1", RUN_ID, SHA, "11:00")
    assert record.built_at == "2026-11-02T09:30:00+00:00"  # UTC, whatever the zone given
    assert record.items_in == (MILK, PASTA)
    assert record.left_out == (LeftOut(EGGS, "coverage", {"a": "1 of 4"}),)
    assert record.headline == Headline("b", Decimal("11.00"), "c", Decimal("13.60"), 24)


def test_build_time_must_carry_a_time_zone():
    with pytest.raises(ValueError, match="time zone"):
        a_record(built_at=datetime(2026, 11, 2, 9, 30))


def test_built_at_utc_is_kept_as_given():
    record = a_record(built_at=datetime(2026, 11, 2, 9, 30, tzinfo=timezone.utc))
    assert record.built_at == "2026-11-02T09:30:00+00:00"


def test_record_json_is_sorted_and_keeps_hebrew():
    record = a_record(a_result(left_out=LeftOut(EGGS, "size", {"a": "12 ביצים"})))
    text = record_json(record)
    loaded = json.loads(text)
    assert text == json.dumps(loaded, sort_keys=True, indent=1, ensure_ascii=False)  # sorted at every level
    assert '"12 ביצים"' in text
    assert loaded["day"] == "2026-11-02"
    assert loaded["chains"]["a"]["total"] == "12.41"
    assert loaded["chains"]["a"]["items"][PASTA] == {"median": "6.51", "low": "6.00", "high": "7.00", "listing": 2,
                                                     "double_coded": 1}
    assert loaded["headline"] == {"lowest": "b", "lowest_total": "11.00", "highest": "c", "highest_total": "13.60",
                                  "gap_percent": 24}
    assert loaded["left_out"] == [{"code": EGGS, "reason": "size", "details": {"a": "12 ביצים"}}]
    assert loaded["chains"]["a"]["stores_with_file"] == ["1", "2", "10", "11"]


def test_record_json_without_a_headline():
    result = a_result()
    record = a_record(DayResult(result.items_in, result.left_out, result.chains, None))
    assert json.loads(record_json(record))["headline"] is None


# ---- the public day and what a revision compares (B12) ----

def test_public_day_has_counts_not_store_lists():
    record = a_record()
    public = public_day(record)
    for chain in public["chains"].values():
        assert set(chain) == {"included", "with_file", "in_ranking", "rank", "total", "items", "extraction"}
    assert public["chains"]["a"]["items"][MILK] == {"median": "5.90", "low": "5.50", "high": "6.40", "listing": 3,
                                                    "double_coded": 0}
    assert public["chains"]["b"]["with_file"] == 2
    text = json.dumps(public)
    assert "PriceFull" not in text and "main-0001" not in text
    assert (public["revisions"], public["revised"]) == ([], None)
    assert record.chains["a"].stores_with_file == ("1", "2", "10", "11")  # the record itself keeps them
    assert json.loads(json.dumps(public)) == public  # JSON-ready: lists, strings, numbers


def test_comparable_ignores_run_fields_but_not_a_median():
    first = a_record()
    published = json.loads(json.dumps(public_day(first)))  # as the day file reads back
    published["revisions"] = [{"run_id": "000000Z-basket-0000", "code_sha": "ffffffffffff", "built_at": "x"}]
    published["revised"] = {"on": "2026-11-03", "reason": "a parser fix"}
    second = a_record(run_id="113000Z-basket-ffff", code_sha="ba9876543210", built_at=BUILT + timedelta(hours=1))
    assert comparable(public_day(second)) == comparable(published)
    assert set(comparable(published)) == {"day", "basket_version", "collected_by", "chains", "items_in", "left_out",
                                          "headline"}
    one_agora = a_record(a_result(milk_at_a="5.91"))  # the median alone: the totals stay as given
    assert comparable(public_day(one_agora)) != comparable(published)


# ---- manifests (B11) ----

def write_manifest(root: Path, slug: str, run_id: str, outcomes: dict[str, str]) -> None:
    files = {name: {"outcome": outcome, "size": 10, "sha256": "0" * 64} for name, outcome in outcomes.items()}
    result = RunResult(chain=slug, run_id=run_id, mode="main", day=DAY, kinds=["PriceFull"], files=files)
    path = root / manifest_key(DAY, slug, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(manifest_bytes(result, "aaaaaaaaaaaa"))


def test_manifests_for_maps_stored_names_to_run_ids(tmp_path):
    write_manifest(tmp_path, "a", "030000Z-main-0001", {"PriceFull-1.gz": "stored", "PriceFull-9.gz": "stored"})
    write_manifest(tmp_path, "a", "020000Z-main-0002", {"PriceFull-1.gz": "exists", "PriceFull-2.gz": "conflict"})
    assert manifests_for(tmp_path / "manifests", DAY, "a", ["PriceFull-1.gz", "PriceFull-2.gz"]) == (
        "030000Z-main-0001",)


def test_manifests_for_sorts_and_keeps_to_the_chain_and_the_files(tmp_path):
    write_manifest(tmp_path, "a", "060000Z-retry-0003", {"PriceFull-2.gz": "stored"})
    write_manifest(tmp_path, "a", "030000Z-main-0001", {"PriceFull-1.gz": "stored"})
    write_manifest(tmp_path, "a", "040000Z-main-0004", {"PriceFull-8.gz": "stored"})  # not a file read
    write_manifest(tmp_path, "b", "030000Z-main-0005", {"PriceFull-1.gz": "stored"})  # another chain
    manifests = tmp_path / "manifests"
    assert manifests_for(manifests, DAY, "a", ["PriceFull-2.gz", "PriceFull-1.gz"]) == (
        "030000Z-main-0001", "060000Z-retry-0003")
    assert manifests_for(manifests, DAY, "a", []) == ()
    assert manifests_for(manifests, DAY + timedelta(days=1), "a", ["PriceFull-1.gz"]) == ()  # no folder that day


# ---- the code's fingerprint ----

def test_code_fingerprint_is_12_hex_and_changes_with_a_source_file(tmp_path, monkeypatch):
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "rules.py").write_text("a = 1\n")
    monkeypatch.setattr(basket, "__file__", str(tmp_path / "__init__.py"))
    before = code_fingerprint()
    assert re.fullmatch(r"[0-9a-f]{12}", before)
    assert before == handler.code_sha(tmp_path)
    (tmp_path / "rules.py").write_text("a = 2\n")
    assert code_fingerprint() != before

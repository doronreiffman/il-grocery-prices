"""The morning check: files listed and not stored, stopped chains, failed runs, and coverage.

Manifests are written as the run loop writes them (RunResult, manifest_bytes, manifest_key) into a
MemoryStore, which keeps S3Store's rules; raw files go in through put_raw.
"""
import gzip
import json
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from collector.check import Alert, check_day, mark_alerted
from collector.names import KINDS
from collector.run import RunResult, manifest_bytes
from collector.sources import PageTimeout
from collector.store import MemoryStore, manifest_key, raw_key
from test_pages import (A, A_ID, ALL_STORED, B, B_ID, BLOCKED, DAY as NOV_5, TIMED_OUT, gz, late, name as list_name,
                        pages, rec, tried)
from test_shufersal import LISTING

FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 10, 31)
NOW = datetime(2026, 10, 31, 8, 30, tzinfo=timezone.utc)
SLUGS = ["shufersal", "ramilevy", "osherad", "carrefour", "yochananof"]
SINCE = "2026-10-31T04:31:00+00:00"

CHAIN_ID = "7290027600007"


def price(store, kind="PriceFull", day=DAY):
    return f"{kind}{CHAIN_ID}-001-{store}-{day:%Y%m%d}-030000.gz"


def stores_name(day=DAY, time="050500"):
    return f"Stores{CHAIN_ID}-000-{day:%Y%m%d}-{time}.gz"


def stores_file(*ids):
    """A Shufersal-shaped store list: gzipped UTF-8, root <Chain>, the ids as given."""
    stores = "".join(f"<Store><StoreID>{i}</StoreID></Store>" for i in ids)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><Chain><SubChains><SubChain><Stores>{stores}'
           f"</Stores></SubChain></SubChains></Chain>").encode()
    return gzip.compress(xml)


def manifest(store, slug, mode, kinds=KINDS, listed=(), error=None, blocked=None, run_id=None, day=DAY, unparsed=0):
    """Write a manifest as collect_chain does; returns its run id."""
    run_id = run_id or f"0{len(store.objects):05d}Z-{mode}-abcd"
    result = RunResult(slug, run_id, mode, day, list(kinds), listed=list(listed), blocked=blocked, error=error,
                       unparsed=unparsed)
    store.put_record(manifest_key(day, slug, run_id), manifest_bytes(result, "0123456789ab"), NOW)
    return run_id


def stored(store, slug, *names, day=DAY, body=None):
    for name in names:
        store.put_raw(raw_key(slug, day, name), body if body is not None else gzip.compress(name.encode()), NOW)


def clean_day(store, slugs=SLUGS, day=DAY):
    """Every chain's retry ran over all five kinds without an error and listed the day's PriceFull and
    PromoFull of store 999, stored (a retry run lists the day's names, stored or not: ruling R31; each
    full kind is listed by some run: ruling R35). No other test names store 999, and no store list holds it."""
    for slug in slugs:
        names = [price("999", day=day), price("999", kind="PromoFull", day=day)]
        manifest(store, slug, "retry", listed=names, day=day)
        stored(store, slug, *names, day=day)


def latch(alerted=False):
    return {"stopped": True, "since": SINCE, "reason": "HTTP 403: https://portal.example/file", "alerted": alerted}


def kinds_of(alerts):
    return [(a.chain, a.kind) for a in alerts]


# ---- a quiet morning ----

def test_clean_day_has_no_alerts():
    store = MemoryStore()
    clean_day(store)
    names = [price("030"), price("031")]
    manifest(store, "shufersal", "main", listed=names)
    stored(store, "shufersal", *names)
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["day"] == "2026-10-31"
    assert record["alerts"] == []
    assert list(record["chains"]) == SLUGS
    assert record["chains"]["shufersal"]["listed"] == 4  # the two and the retry run's two
    assert record["chains"]["shufersal"]["stored"] == 4
    assert record["chains"]["shufersal"]["missing"] == []
    assert record["chains"]["shufersal"]["stopped"] is None
    assert record["chains"]["shufersal"]["failed"] is None
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_retry_runs_need_cover_only_the_kinds_the_chain_collects():
    """Shufersal collects its store list and full files only (owner, 2026-11-01): retries over those
    three are a clean morning; one of them uncovered is named, and Price and Promo never are."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    kinds = {"shufersal": ("Stores", "PriceFull", "PromoFull")}
    manifest(store, "shufersal", "retry", kinds=["Stores"])
    manifest(store, "shufersal", "retry", kinds=["PriceFull"], listed=[price("030")])
    stored(store, "shufersal", price("030"))
    alerts, record = check_day(store, SLUGS, DAY, kinds=kinds)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: no retry run covered PromoFull; "
                              "no run listed a PromoFull for the day.")
    manifest(store, "shufersal", "retry", kinds=["PromoFull"], listed=[price("030", kind="PromoFull")])
    stored(store, "shufersal", price("030", kind="PromoFull"))
    alerts, record = check_day(store, SLUGS, DAY, kinds=kinds)
    assert alerts == [] and record["chains"]["shufersal"]["failed"] is None


def test_a_chain_left_out_of_kinds_is_held_to_all_five():
    store = MemoryStore()
    names = [price("001"), price("001", kind="PromoFull")]
    manifest(store, "ramilevy", "retry", kinds=["Stores", "PriceFull", "PromoFull"], listed=names)
    stored(store, "ramilevy", *names)
    _, record = check_day(store, ["ramilevy"], DAY, kinds={"shufersal": ("Stores",)})
    assert record["chains"]["ramilevy"]["failed"] == "no retry run covered Price, Promo"


def test_only_the_chains_asked_for_are_checked():
    store = MemoryStore()
    manifest(store, "ramilevy", "retry", listed=[price("001")])
    alerts, record = check_day(store, ["shufersal"], DAY)
    assert list(record["chains"]) == ["shufersal"]
    assert all(a.chain == "shufersal" for a in alerts)


def test_each_chain_reads_its_own_manifests():
    store = MemoryStore()
    clean_day(store)
    manifest(store, "ramilevy", "main", listed=[price("001")])
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("ramilevy", "missing")]
    assert record["chains"]["shufersal"]["listed"] == 2 and record["chains"]["shufersal"]["manifests"] == 1
    assert record["chains"]["ramilevy"]["manifests"] == 2


# ---- listed and not stored ----

def test_missing_files_alert_once_naming_the_chain_and_the_count():
    store = MemoryStore()
    clean_day(store)
    names = [price("030"), price("031"), price("032")]
    manifest(store, "shufersal", "retry", listed=names)
    stored(store, "shufersal", names[1])
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "missing")]
    text = alerts[0].text
    assert "shufersal" in text and "2 files" in text
    assert names[0] in text and names[2] in text and names[1] not in text
    assert record["chains"]["shufersal"]["missing"] == [names[0], names[2]]
    assert record["chains"]["shufersal"]["listed"] == 5  # the three and clean_day's two
    assert record["chains"]["shufersal"]["stored"] == 3


def test_one_missing_file_is_one_file():
    store = MemoryStore()
    clean_day(store)
    manifest(store, "ramilevy", "main", listed=[price("001")])
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("ramilevy", "missing")]
    assert "1 file " in alerts[0].text


def test_names_listed_in_any_manifest_count():
    """A name the main run listed and the retry run no longer lists is still missing (Shufersal
    shows only the latest file per store)."""
    store = MemoryStore()
    clean_day(store)
    manifest(store, "shufersal", "main", listed=[price("030"), price("031")])
    manifest(store, "shufersal", "retry", listed=[price("031")])
    stored(store, "shufersal", price("031"))
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "missing")]
    assert record["chains"]["shufersal"]["missing"] == [price("030")]


def test_missing_alert_names_ten_and_the_record_holds_all():
    store = MemoryStore()
    clean_day(store)
    names = [price(f"{n:03d}") for n in range(12)]
    manifest(store, "carrefour", "main", listed=names)
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("carrefour", "missing")]
    text = alerts[0].text
    assert "12 files" in text
    assert all(name in text for name in names[:10])
    assert names[10] not in text and names[11] not in text
    assert "2 more" in text
    assert record["chains"]["carrefour"]["missing"] == names


def test_a_conflict_copy_counts_as_stored():
    store = MemoryStore()
    clean_day(store)
    manifest(store, "shufersal", "main", listed=[price("030")])
    store.put_raw(raw_key("shufersal", DAY, price("030")) + ".0123456789ab", b"changed body", NOW)
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["chains"]["shufersal"]["missing"] == []


def test_files_of_another_day_do_not_count():
    """Yesterday's manifest's names are yesterday's business; a file stored under another day is
    not stored for this one."""
    store = MemoryStore()
    clean_day(store)
    yesterday = DAY - timedelta(days=1)
    manifest(store, "shufersal", "main", listed=[price("030", day=yesterday)], day=yesterday)
    manifest(store, "shufersal", "main", listed=[price("031")])
    stored(store, "shufersal", price("031"), day=yesterday)
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "missing")]
    assert record["chains"]["shufersal"]["missing"] == [price("031")]


# ---- stopped chains ----

def test_a_stopped_chain_alerts_and_check_day_leaves_its_state():
    """check_day only reads: the state is marked once the email has gone (ruling R26)."""
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch())
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("osherad", "stopped")]
    assert "osherad" in alerts[0].text and "HTTP 403" in alerts[0].text and SINCE in alerts[0].text
    assert store.read_state("osherad") == latch()
    assert record["chains"]["osherad"]["stopped"] == {"since": SINCE, "reason": latch()["reason"]}


def test_mark_alerted_keeps_the_chain_stopped_with_its_reason():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch())
    mark_alerted(store, check_day(store, SLUGS, DAY)[0])
    assert store.read_state("osherad") == latch(alerted=True)


def test_a_second_check_after_the_email_sends_no_second_stopped_alert():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch())
    mark_alerted(store, check_day(store, SLUGS, DAY)[0])
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["chains"]["osherad"]["stopped"] == {"since": SINCE, "reason": latch()["reason"]}
    later = DAY + timedelta(days=1)
    clean_day(store, day=later)
    assert check_day(store, SLUGS, later)[0] == []


def test_a_check_whose_email_never_went_alerts_again():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch())
    check_day(store, SLUGS, DAY)
    assert kinds_of(check_day(store, SLUGS, DAY)[0]) == [("osherad", "stopped")]


def test_mark_alerted_marks_only_the_chains_a_stopped_alert_names():
    store = MemoryStore()
    store.write_state("osherad", latch())
    store.write_state("carrefour", latch())
    mark_alerted(store, [Alert("carrefour", "missing", "x"), Alert("osherad", "stopped", "y")])
    assert store.read_state("osherad") == latch(alerted=True)
    assert store.read_state("carrefour") == latch()


def test_mark_alerted_leaves_a_chain_cleared_since_the_check():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch())
    alerts, _ = check_day(store, SLUGS, DAY)
    store.write_state("osherad", {})  # the owner's unblock run, between the check and the email
    mark_alerted(store, alerts)
    assert store.read_state("osherad") == {}


def test_a_chain_already_alerted_stays_quiet():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", latch(alerted=True))
    assert check_day(store, SLUGS, DAY)[0] == []
    assert store.read_state("osherad") == latch(alerted=True)


def test_a_chain_that_is_not_stopped_does_not_alert():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", {})
    store.write_state("carrefour", {"stopped": False, "alerted": False})
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["chains"]["osherad"]["stopped"] is None
    assert store.read_state("osherad") == {} and store.read_state("carrefour") == {"stopped": False, "alerted": False}


def test_a_latch_without_an_alerted_flag_alerts():
    store = MemoryStore()
    clean_day(store)
    store.write_state("osherad", {"stopped": True, "since": SINCE, "reason": "HTTP 429"})
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("osherad", "stopped")]
    mark_alerted(store, alerts)
    assert store.read_state("osherad")["alerted"] is True


# ---- failed runs (ruling R4) ----

def test_failed_run_alerts():
    """No retry manifest for a chain that day, or one with an error (a listing that reads as no
    rows included, plan risk 1), is a failed run."""
    store = MemoryStore()
    clean_day(store, ["osherad", "carrefour", "yochananof"])
    manifest(store, "shufersal", "main")  # the main run went; no retry run did
    manifest(store, "ramilevy", "retry", error="listing unreadable: the listing has no rows", run_id="093000Z-retry-0a0a")
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed"), ("ramilevy", "failed")]
    assert "no retry run covered Stores, PriceFull, PromoFull, Price, Promo" in alerts[0].text
    assert "093000Z-retry-0a0a" in alerts[1].text and "listing unreadable: the listing has no rows" in alerts[1].text
    assert record["chains"]["shufersal"]["failed"] == ("no retry run covered Stores, PriceFull, PromoFull, Price, Promo; "
                                                       "no run listed a PriceFull for the day; no run listed a PromoFull for the day")
    assert "listing unreadable" in record["chains"]["ramilevy"]["failed"]


def test_shufersals_three_retry_runs_together_cover_the_five_kinds():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", kinds=["Stores"])
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "Price"], listed=[price("030")])
    stored(store, "shufersal", price("030"))
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: no retry run covered PromoFull, Promo; "
                              "no run listed a PromoFull for the day.")
    manifest(store, "shufersal", "retry", kinds=["PromoFull", "Promo"], listed=[price("030", kind="PromoFull")])
    stored(store, "shufersal", price("030", kind="PromoFull"))
    assert check_day(store, SLUGS, DAY)[0] == []


def test_main_runs_do_not_stand_in_for_the_retry():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "main")
    manifest(store, "shufersal", "unblock-test")
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed")]


def test_a_main_run_error_is_left_to_the_retry():
    store = MemoryStore()
    clean_day(store)
    manifest(store, "shufersal", "main", error="stopped: under 90 s left")
    assert check_day(store, SLUGS, DAY)[0] == []


def test_a_blocked_retry_is_not_a_failed_run():
    """The stopped alert covers it."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", blocked="stopped earlier")
    store.write_state("shufersal", latch(alerted=True))
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["chains"]["shufersal"]["failed"] is None


def test_a_blocked_retry_with_an_error_is_a_failed_run():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", blocked="HTTP 403: https://x", error="latch not written: ClientError: boom")
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert "latch not written" in alerts[0].text


def test_one_failed_alert_per_chain():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", kinds=["Stores"], error="listing failed: HTTP 500", run_id="093000Z-retry-0001")
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "Price"], error="stopped: under 90 s left", run_id="094500Z-retry-0002")
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    text = alerts[0].text
    assert "no retry run covered PromoFull, Promo" in text
    assert "093000Z-retry-0001" in text and "listing failed: HTTP 500" in text
    assert "094500Z-retry-0002" in text and "stopped: under 90 s left" in text


def test_every_kind_of_alert_for_one_chain():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", listed=[price("030")], blocked="HTTP 403: https://x",
             error="latch not written: ClientError: boom")
    store.write_state("shufersal", latch())
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "missing"), ("shufersal", "stopped"), ("shufersal", "failed")]
    assert record["alerts"] == [{"chain": a.chain, "kind": a.kind, "text": a.text} for a in alerts]


# ---- retry runs that list nothing (ruling R31) ----

def test_retry_runs_that_list_nothing_are_a_failed_run():
    """Ruling R31: a listing whose names all fail to parse, or all carry another day, ends without an
    error; retry runs that list nothing for the day are a failed run, naming the unparsed count."""
    store = MemoryStore()
    clean_day(store, [slug for slug in SLUGS if slug != "ramilevy"])
    manifest(store, "ramilevy", "retry", unparsed=2362)
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("ramilevy", "failed")]
    nothing = ("the retry runs listed nothing for the day (unparsed names: 2362); "
               "no run listed a PriceFull for the day; no run listed a PromoFull for the day")
    assert alerts[0].text == f"ramilevy: the day's runs fell short: {nothing}."
    assert record["chains"]["ramilevy"]["failed"] == nothing


def test_the_unparsed_count_sums_the_chains_retry_runs():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", kinds=["Stores"], unparsed=2)
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "Price"], unparsed=2000)
    manifest(store, "shufersal", "retry", kinds=["PromoFull", "Promo"], unparsed=360)
    manifest(store, "shufersal", "main", unparsed=5000)  # a main run's count is not the retry runs'
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert ": the retry runs listed nothing for the day (unparsed names: 2362);" in alerts[0].text


def test_a_retry_run_that_lists_nothing_is_not_alone_a_failed_run():
    """Shufersal's Stores run can list nothing while its other two list the day's files: the names
    are taken across all of a chain's retry runs."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    names = [price("030"), price("030", kind="PromoFull")]
    manifest(store, "shufersal", "retry", kinds=["Stores"], unparsed=1)
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "Price"], listed=names[:1])
    manifest(store, "shufersal", "retry", kinds=["PromoFull", "Promo"], listed=names[1:])
    stored(store, "shufersal", *names)
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == [] and record["chains"]["shufersal"]["failed"] is None


def test_a_blocked_chain_that_listed_nothing_alerts_only_as_stopped():
    """One blocked retry run is enough: the stopped alert covers the chain's empty morning."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "retry", kinds=["Stores"])
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "Price"], blocked="HTTP 403: https://x")
    manifest(store, "shufersal", "retry", kinds=["PromoFull", "Promo"], blocked="stopped earlier")
    store.write_state("shufersal", latch())
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "stopped")]
    assert record["chains"]["shufersal"]["failed"] is None


# ---- a full kind no run listed (ruling R35) ----

SHUFERSAL_KINDS = {"shufersal": ("Stores", "PriceFull", "PromoFull")}


def shufersal_morning(store, price_full=True, promo_full=True):
    """Shufersal's three retry runs, one kind each (owner, 2026-11-01), every name stored; the Stores
    run always lists the day's store list."""
    names = {"Stores": [stores_name()], "PriceFull": [price("030")] if price_full else [],
             "PromoFull": [price("030", kind="PromoFull")] if promo_full else []}
    for kind, listed in names.items():
        manifest(store, "shufersal", "retry", kinds=[kind], listed=listed)
        stored(store, "shufersal", *listed)


@pytest.mark.parametrize("kind", ["PriceFull", "PromoFull"])
def test_a_full_kind_no_run_listed_is_a_failed_run(kind):
    """Ruling R35 (QUEUE q7): R31 takes the union over a chain's retry runs, so a day Shufersal lists
    no PriceFull at all stayed silent while its Stores run listed something. Each full kind the chain
    collects must be listed by some run that day."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    shufersal_morning(store, price_full=kind != "PriceFull", promo_full=kind != "PromoFull")
    alerts, record = check_day(store, SLUGS, DAY, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == f"shufersal: the day's runs fell short: no run listed a {kind} for the day."
    assert record["chains"]["shufersal"]["failed"] == f"no run listed a {kind} for the day"


def test_a_block_cleared_before_the_retries_leaves_the_alarm_on():
    """Only a blocked retry run silences the alarm, as in R31: a main run blocked and cleared before
    the retry runs leaves no stopped alert, so a full kind the retries did not list must still alert."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    manifest(store, "shufersal", "main", kinds=["Stores"], blocked="HTTP 403: https://x")
    manifest(store, "shufersal", "main", kinds=["PriceFull"], blocked="stopped earlier")
    manifest(store, "shufersal", "main", kinds=["PromoFull"], blocked="stopped earlier")
    shufersal_morning(store, price_full=False)  # the owner cleared the latch before 09:30
    alerts, record = check_day(store, SLUGS, DAY, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert record["chains"]["shufersal"]["failed"] == "no run listed a PriceFull for the day"


def test_both_full_kinds_listed_is_a_clean_morning():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    shufersal_morning(store)
    alerts, record = check_day(store, SLUGS, DAY, kinds=SHUFERSAL_KINDS)
    assert alerts == [] and record["chains"]["shufersal"]["failed"] is None


def test_a_full_kind_a_main_run_listed_counts():
    """Any run that day counts, main or retry: a file the main run listed and stored is listed."""
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    shufersal_morning(store, price_full=False)
    manifest(store, "shufersal", "main", kinds=["PriceFull"], listed=[price("031")])
    stored(store, "shufersal", price("031"))
    alerts, _ = check_day(store, SLUGS, DAY, kinds=SHUFERSAL_KINDS)
    assert alerts == []


def test_update_files_do_not_stand_in_for_full_files():
    """A Price or Promo file is not a PriceFull or PromoFull: the kind is read from the name."""
    store = MemoryStore()
    clean_day(store, [slug for slug in SLUGS if slug != "ramilevy"])
    names = [price("001", kind="Price"), price("001", kind="Promo")]
    manifest(store, "ramilevy", "retry", listed=names)
    stored(store, "ramilevy", *names)
    alerts, _ = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("ramilevy", "failed")]
    assert alerts[0].text == ("ramilevy: the day's runs fell short: "
                              "no run listed a PriceFull for the day; no run listed a PromoFull for the day.")


def test_a_full_kind_the_chain_does_not_collect_is_not_required():
    store = MemoryStore()
    clean_day(store, SLUGS[1:])
    for kind, listed in (("Stores", [stores_name()]), ("PriceFull", [price("030")])):
        manifest(store, "shufersal", "retry", kinds=[kind], listed=listed)
        stored(store, "shufersal", *listed)
    alerts, _ = check_day(store, SLUGS, DAY, kinds={"shufersal": ("Stores", "PriceFull")})
    assert alerts == []


def test_alert_is_a_dataclass_with_chain_kind_and_text():
    alert = Alert("shufersal", "missing", "text")
    assert (alert.chain, alert.kind, alert.text) == ("shufersal", "missing", "text")


# ---- a retry run short of time on a day listed in full (ruling R36) ----

STOPPED = "stopped: under 90 s left"  # what the run loop writes when it stops itself (ruling R32)
NOV_3, NOV_4 = date(2026, 11, 3), date(2026, 11, 4)


def promo(n, day):
    return price(f"{n:03d}", kind="PromoFull", day=day)


def shufersal_promo_day(store, day, promo_runs, stored_promo, stores_retry=True):
    """A Shufersal morning shaped on the real manifests of 3 and 4 November 2026, six stores standing in
    for 417: the Stores retry (unless `stores_retry` is false) and the PriceFull main and retry runs
    clean, then the PromoFull runs as given, each (run id, the stores it listed, its error, its block),
    its mode read from the run id, and the PromoFull files of the `stored_promo` stores stored."""
    if stores_retry:
        manifest(store, "shufersal", "retry", kinds=["Stores"], listed=[stores_name(day)], day=day)
        stored(store, "shufersal", stores_name(day), day=day)
    prices = [price(f"{n:03d}", day=day) for n in range(1, 7)]
    manifest(store, "shufersal", "main", kinds=["PriceFull"], listed=prices, day=day, run_id="050002Z-main-54fa")
    manifest(store, "shufersal", "retry", kinds=["PriceFull"], listed=prices, day=day, run_id="074536Z-retry-9bb5")
    stored(store, "shufersal", *prices, day=day)
    for run_id, stores, error, blocked in promo_runs:
        manifest(store, "shufersal", run_id.split("-")[1], kinds=["PromoFull"], listed=[promo(n, day) for n in stores],
                 error=error, blocked=blocked, day=day, run_id=run_id)
    stored(store, "shufersal", *(promo(n, day) for n in stored_promo), day=day)


def nov_4(store, retry_error=STOPPED, stored_promo=range(1, 7), stores_retry=True):
    """4 November: the first main run stopped short, the second read the whole listing, the retry
    stopped short; every store's PromoFull stored."""
    shufersal_promo_day(store, NOV_4, [("051514Z-main-db2b", range(1, 6), STOPPED, None),
                                       ("053014Z-main-bd28", range(1, 7), None, None),
                                       ("081551Z-retry-9b10", range(1, 6), retry_error, None)], stored_promo, stores_retry)


def test_a_retry_short_of_time_on_a_day_listed_in_full_is_quiet_and_recorded():
    """Ruling R36, 4 November 2026: the retry stopped short, but a main run had read the whole PromoFull
    listing, listing every name the retry listed, and every name listed is stored. The run is no failed
    run; the record names it."""
    store = MemoryStore()
    nov_4(store)
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert alerts == []
    chain = record["chains"]["shufersal"]
    assert chain["failed"] is None and chain["missing"] == []
    assert chain["short_of_time"] == ["081551Z-retry-9b10 (PromoFull)"]  # a main run's stop is not named


def test_a_retry_short_of_time_with_no_run_that_read_the_listing_in_full_still_fails():
    """3 November 2026, a real shortfall: every PromoFull run stopped short, so no run listed the
    stores after the 4th, and nothing is missing only because nothing listed them."""
    store = MemoryStore()
    shufersal_promo_day(store, NOV_3, [("051514Z-main-4296", range(1, 4), STOPPED, None),
                                       ("053014Z-main-f155", range(1, 5), STOPPED, None),
                                       ("081551Z-retry-b079", range(1, 5), STOPPED, None)], range(1, 5))
    alerts, record = check_day(store, ["shufersal"], NOV_3, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: "
                              "retry run 081551Z-retry-b079 (PromoFull) ended with: stopped: under 90 s left.")
    assert record["chains"]["shufersal"]["missing"] == []
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_retry_short_of_time_on_a_day_with_something_missing_fails():
    store = MemoryStore()
    nov_4(store, stored_promo=range(1, 6))  # the complete run listed store 6's file; nothing stored it
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "missing"), ("shufersal", "failed")]
    assert "retry run 081551Z-retry-9b10 (PromoFull) ended with: stopped: under 90 s left" in alerts[1].text
    assert record["chains"]["shufersal"]["short_of_time"] == []


@pytest.mark.parametrize("error", ["listing failed: HTTP 500",
                                   # the time stop's words inside another error are not the time stop
                                   "unexpected error: RuntimeError: stopped: under 90 s left"])
def test_a_retry_with_another_error_on_a_day_listed_in_full_fails(error):
    store = MemoryStore()
    nov_4(store, retry_error=error)
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == f"shufersal: the day's runs fell short: retry run 081551Z-retry-9b10 (PromoFull) ended with: {error}."
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_blocked_run_did_not_read_its_listing_in_full():
    """The only PromoFull run that ended with no error was blocked (the owner cleared the latch before
    the retry), after it listed every name the retry would: a block stops the listing, so the retry's
    time stop still fails the morning."""
    store = MemoryStore()
    shufersal_promo_day(store, NOV_4, [("051514Z-main-db2b", range(1, 4), STOPPED, None),
                                       ("053014Z-main-bd28", range(1, 6), None, "HTTP 403: https://x"),
                                       ("081551Z-retry-9b10", range(1, 6), STOPPED, None)], range(1, 6))
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert "retry run 081551Z-retry-9b10 (PromoFull) ended with: stopped: under 90 s left" in alerts[0].text
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_retry_run_that_read_the_listing_in_full_counts_too():
    """Main or retry: a second retry run of the kind (by hand) that read the whole listing excuses the
    first one's time stop."""
    store = MemoryStore()
    shufersal_promo_day(store, NOV_4, [("051514Z-main-db2b", range(1, 6), STOPPED, None),
                                       ("081551Z-retry-9b10", range(1, 6), STOPPED, None),
                                       ("093000Z-retry-0c0c", range(1, 7), None, None)], range(1, 7))
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert alerts == []
    assert record["chains"]["shufersal"]["short_of_time"] == ["081551Z-retry-9b10 (PromoFull)"]


def test_each_kind_of_a_retry_short_of_time_needs_a_listing_read_in_full():
    """A retry over two kinds stopped short before its PromoFull listing: PriceFull's main run read its
    listing in full, PromoFull's stopped short, so the retry still fails; once a PromoFull run reads the
    whole listing, it does not."""
    store = MemoryStore()
    manifest(store, "shufersal", "retry", kinds=["Stores"], listed=[stores_name(NOV_4)], day=NOV_4)
    prices, promos = [price(f"{n:03d}", day=NOV_4) for n in range(1, 7)], [promo(n, NOV_4) for n in range(1, 7)]
    manifest(store, "shufersal", "main", kinds=["PriceFull"], listed=prices, day=NOV_4)
    manifest(store, "shufersal", "main", kinds=["PromoFull"], listed=promos[:4], error=STOPPED, day=NOV_4)
    manifest(store, "shufersal", "retry", kinds=["PriceFull", "PromoFull"], listed=prices, error=STOPPED,
             day=NOV_4, run_id="081551Z-retry-2k2k")
    stored(store, "shufersal", stores_name(NOV_4), *prices, *promos, day=NOV_4)
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert "retry run 081551Z-retry-2k2k (PriceFull, PromoFull) ended with: stopped: under 90 s left" in alerts[0].text
    assert record["chains"]["shufersal"]["short_of_time"] == []
    manifest(store, "shufersal", "main", kinds=["PromoFull"], listed=promos, day=NOV_4)
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert alerts == []
    assert record["chains"]["shufersal"]["short_of_time"] == ["081551Z-retry-2k2k (PriceFull, PromoFull)"]


@pytest.mark.parametrize("complete_run", [
    ("040000Z-main-0a0a", range(1, 1)),  # A: made before the day's files were up: it listed nothing, with no error
    ("051514Z-main-db2b", range(1, 4)),  # B: made before stores 4 and 5 published theirs
])
def test_a_retry_that_listed_names_no_complete_run_listed_fails(complete_run):
    """A run that ended with no error read only the listing that was up when it ran. The stopped retry
    listed names it never saw, and stopped where the stores after them were still unlisted: nothing
    shows as missing, yet the morning may be short."""
    run_id, stores = complete_run
    store = MemoryStore()
    shufersal_promo_day(store, NOV_4, [(run_id, stores, None, None),
                                       ("081551Z-retry-9b10", range(1, 6), STOPPED, None)], range(1, 6))
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: "
                              "retry run 081551Z-retry-9b10 (PromoFull) ended with: stopped: under 90 s left.")
    assert record["chains"]["shufersal"]["missing"] == []
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_retry_that_listed_nothing_still_needs_a_listing_read_in_full():
    """3 November's shape, the retry stopped before it listed a name of the day: no complete run is
    needed to have seen its names, but its kind still needs a run that read the whole listing."""
    store = MemoryStore()
    shufersal_promo_day(store, NOV_3, [("051514Z-main-4296", range(1, 4), STOPPED, None),
                                       ("053014Z-main-f155", range(1, 5), STOPPED, None),
                                       ("081551Z-retry-b079", range(1, 1), STOPPED, None)], range(1, 5))
    alerts, record = check_day(store, ["shufersal"], NOV_3, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_retry_short_of_time_leaves_the_chains_other_failures():
    """Only the excused run leaves the alert: a kind no retry run covered still fails the morning."""
    store = MemoryStore()
    nov_4(store, stores_retry=False)
    alerts, record = check_day(store, ["shufersal"], NOV_4, kinds=SHUFERSAL_KINDS)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert record["chains"]["shufersal"]["failed"] == "no retry run covered Stores"
    assert record["chains"]["shufersal"]["short_of_time"] == ["081551Z-retry-9b10 (PromoFull)"]


# ---- the day's pages joined across runs (ruling R37) ----

SHUFERSAL_FULL = {"shufersal": ("PriceFull", "PromoFull")}
RETRY_ID, PROMO_RETRY_ID = "074536Z-retry-2933", "081551Z-retry-9283"  # 2026-11-05's PriceFull and PromoFull retries


def paged(store, run_id, kind, records, listed=(), error=None, blocked=None, kinds=None):
    """Write a Shufersal manifest of `kind` (or of `kinds`) with its page records, as the run loop writes it, its mode
    read from the run id."""
    result = RunResult("shufersal", run_id, run_id.split("-")[1], NOV_5, list(kinds or [kind]), listed=list(listed),
                       error=error, blocked=blocked, pages=list(records))
    store.put_record(manifest_key(NOV_5, "shufersal", run_id), manifest_bytes(result, "0123456789ab"), NOW)


def legacy(store, run_id, kinds, listed, error=None):
    """Write a Shufersal manifest as the run loop wrote it before page records: no `pages` key."""
    result = RunResult("shufersal", run_id, run_id.split("-")[1], NOV_5, list(kinds), listed=list(listed), error=error)
    record = json.loads(manifest_bytes(result, "0123456789ab"))
    del record["pages"]
    store.put_record(manifest_key(NOV_5, "shufersal", run_id), json.dumps(record).encode(), NOW)


def whole(store, run_id, kind):
    """A run that read `kind`'s whole list in one go and ended clean, every name it listed stored."""
    paged(store, run_id, kind, pages(1, 21, kind=kind), gz(range(1, 421), kind))
    stored(store, "shufersal", *gz(range(1, 421), kind), day=NOV_5)


def nov_5(store):
    """2026-11-05's PriceFull morning as resumed (tests/test_pages.py): A read pages 1 to 11 and page 12's first row
    and stopped on time, B read page 1 and pages 12 to 21, and every name is stored; PromoFull's retry read its whole
    list."""
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, B_ID, "PriceFull", B["pages"], B["listed"])
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")


def check_nov_5(store, kinds=SHUFERSAL_FULL):
    return check_day(store, ["shufersal"], NOV_5, kinds=kinds)


def time_stop(run_id=RETRY_ID, kinds="PriceFull"):
    return f"retry run {run_id} ({kinds}) ended with: {STOPPED}"


def test_read_in_full_is_recorded_per_full_kind():
    """For each full kind a chain collects, the runs whose readings joined up: on 2026-11-05's PriceFull shape A and B,
    not the retry whose page 1 added nothing. A chain whose runs carry no page records reads by R36's rule: its clean
    retry read every kind in full."""
    store = MemoryStore()
    nov_5(store)
    paged(store, RETRY_ID, "PriceFull", [rec(1)], gz(range(1, 21)), error=TIMED_OUT)
    names = [price("001", day=NOV_5), price("001", kind="PromoFull", day=NOV_5)]
    manifest(store, "ramilevy", "retry", listed=names, day=NOV_5, run_id="093000Z-retry-0a0a")
    stored(store, "ramilevy", *names, day=NOV_5)
    _, record = check_day(store, ["shufersal", "ramilevy"], NOV_5, kinds=SHUFERSAL_FULL)
    assert record["chains"]["shufersal"]["read_in_full"] == {"PriceFull": [A_ID, B_ID], "PromoFull": [PROMO_RETRY_ID]}
    assert record["chains"]["ramilevy"]["read_in_full"] == {"PriceFull": ["093000Z-retry-0a0a"],
                                                            "PromoFull": ["093000Z-retry-0a0a"]}


def test_a_full_kind_the_chain_does_not_collect_is_neither_recorded_nor_judged():
    """A chain that no longer collects PromoFull (its kinds narrowed that day) has PromoFull pages not read in full:
    they are not its business."""
    store = MemoryStore()
    whole(store, RETRY_ID, "PriceFull")
    paged(store, "051514Z-main-b001", "PromoFull", pages(1, 5, kind="PromoFull"), gz(range(1, 101), "PromoFull"),
          error=STOPPED)
    stored(store, "shufersal", *gz(range(1, 101), "PromoFull"), day=NOV_5)
    alerts, record = check_nov_5(store, kinds={"shufersal": ("PriceFull",)})
    assert alerts == []
    assert record["chains"]["shufersal"]["read_in_full"] == {"PriceFull": [RETRY_ID]}


def test_a_stopped_retry_on_a_day_read_in_full_across_runs_is_quiet():
    """Ruling R37 amends R36: A and B read the PriceFull list in full between them; the retry's fresh pass stopped on
    time on page 2, after listing only names A or B listed. Nothing is missing: no alert, and the record names the
    retry."""
    store = MemoryStore()
    nov_5(store)
    paged(store, RETRY_ID, "PriceFull", [rec(1), rec(2, taken=5)], gz(range(1, 26)), error=STOPPED)
    alerts, record = check_nov_5(store)
    assert alerts == []
    chain = record["chains"]["shufersal"]
    assert chain["failed"] is None and chain["missing"] == []
    assert chain["short_of_time"] == ["074536Z-retry-2933 (PriceFull)"]


def test_a_retry_that_read_further_than_a_run_before_it_is_still_vouched_for():
    """The retry's fresh pass downloads nothing (every file is stored), so it reads on past where A stopped, to page
    16, before it stops on time. Joined with the retry's pages, the reading names the retry and B and leaves A out;
    without them, A and B. A listed what the retry listed before page 12, so the vouching runs are those whose
    readings join up without the retry's."""
    store = MemoryStore()
    nov_5(store)
    paged(store, RETRY_ID, "PriceFull", pages(1, 16), gz(range(1, 321)), error=STOPPED)
    alerts, record = check_nov_5(store)
    assert alerts == []
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] == [B_ID, RETRY_ID]
    assert record["chains"]["shufersal"]["short_of_time"] == ["074536Z-retry-2933 (PriceFull)"]


def test_a_stopped_retry_whose_names_only_it_listed_still_fails():
    """A file published on page 2 after A read it: the retry listed it, A and B did not, so the list changed after they
    read it, and the part past where the retry stopped may hold files no run listed."""
    store = MemoryStore()
    nov_5(store)
    paged(store, RETRY_ID, "PriceFull", [rec(1), rec(2, taken=5) | {"taken_through": late(25)}],
          gz(range(1, 26)) + [late(25) + ".gz"], error=STOPPED)
    stored(store, "shufersal", late(25) + ".gz", day=NOV_5)
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == f"shufersal: the day's runs fell short: {time_stop()}."
    assert record["chains"]["shufersal"]["missing"] == []
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_retry_never_vouches_for_its_own_names():
    """The retry resumed where A stopped, took the list to its last row, then met the time check before the listing
    said it had ended. Its pages complete the day's reading, but the names after page 12's first only it listed, and a
    run never vouches for itself."""
    store = MemoryStore()
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, RETRY_ID, "PriceFull", B["pages"], B["listed"], error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert alerts[0].text == f"shufersal: the day's runs fell short: {time_stop()}."
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] == [A_ID, RETRY_ID]
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_second_whole_pass_vouches_for_a_file_published_between_the_passes():
    """A fast morning: both main runs read the whole list, and a file was published on page 5 between them. The joined
    reading names only the first pass; the second read the whole list on its own, so it vouches for the file it and
    the stopped retry listed. Nothing is missing: quiet (controller ruling on R37's excuse, 2026-11-05)."""
    store = MemoryStore()
    published = late(85) + ".gz"
    paged(store, A_ID, "PriceFull", pages(1, 21), gz(range(1, 421)))
    paged(store, B_ID, "PriceFull", pages(1, 21), gz(range(1, 86)) + [published] + gz(range(86, 421)))
    paged(store, RETRY_ID, "PriceFull", [*pages(1, 4), rec(5, taken=5) | {"taken_through": late(85)}],
          gz(range(1, 86)) + [published], error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, published, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert alerts == []
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] == [A_ID]
    assert record["chains"]["shufersal"]["short_of_time"] == ["074536Z-retry-2933 (PriceFull)"]


def test_a_run_that_read_part_of_the_list_does_not_vouch():
    """The first main run read the whole list; the second made a fresh pass and stopped on time on page 5, after
    listing a file published there since; the stopped retry listed it too. A run that read part of the list proves
    nothing of the part it did not read: the retry's time stop still fails the morning."""
    store = MemoryStore()
    published = late(85) + ".gz"
    to_page_5 = [*pages(1, 4), rec(5, taken=5) | {"taken_through": late(85)}]
    paged(store, A_ID, "PriceFull", pages(1, 21), gz(range(1, 421)))
    paged(store, B_ID, "PriceFull", to_page_5, gz(range(1, 86)) + [published], error=STOPPED)
    paged(store, RETRY_ID, "PriceFull", to_page_5, gz(range(1, 86)) + [published], error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, published, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert alerts[0].text == f"shufersal: the day's runs fell short: {time_stop()}."
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_run_vouches_only_for_the_kinds_it_read():
    """A main run over both full kinds read PriceFull's whole list, then stopped on PromoFull's page 5 after listing a
    PromoFull file published there since PromoFull's own run read the whole list; the retry over both did the same.
    The main run vouches for the retry's PriceFull names, not for its PromoFull ones."""
    store = MemoryStore()
    published = list_name(85, "PromoFull").replace("-030000", "-060000")
    promo_to_page_5 = [*pages(1, 4, kind="PromoFull"), rec(5, taken=5, kind="PromoFull") | {"taken_through": published}]
    both = dict(kinds=("PriceFull", "PromoFull"), error=STOPPED)
    listed = gz(range(1, 421)) + gz(range(1, 86), "PromoFull") + [published + ".gz"]
    whole(store, "051514Z-main-b001", "PromoFull")
    paged(store, "053014Z-main-b002", "PriceFull", [*pages(1, 21), *promo_to_page_5], listed, **both)
    paged(store, RETRY_ID, "PriceFull", [*pages(1, 21), *promo_to_page_5], listed, **both)
    stored(store, "shufersal", *ALL_STORED, published + ".gz", day=NOV_5)
    alerts, record = check_nov_5(store)
    assert alerts[0].text == f"shufersal: the day's runs fell short: {time_stop(kinds='PriceFull, PromoFull')}."
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_full_kind_not_read_in_full_names_the_pages_never_read():
    """Design, Call 4: PromoFull's main runs read pages 1 to 16 between them and its retry stopped on time; the failed
    alert says what of the list no run read."""
    store = MemoryStore()
    whole(store, RETRY_ID, "PriceFull")
    first = [*pages(1, 11, kind="PromoFull"), rec(12, taken=1, kind="PromoFull")]
    paged(store, "051514Z-main-b001", "PromoFull", first, gz(range(1, 222), "PromoFull"), error=STOPPED)
    paged(store, "053014Z-main-b002", "PromoFull", [rec(1, kind="PromoFull"), *pages(12, 16, kind="PromoFull")],
          gz(range(1, 21), "PromoFull") + gz(range(221, 321), "PromoFull"), error=STOPPED)
    paged(store, PROMO_RETRY_ID, "PromoFull", [rec(1, kind="PromoFull")], gz(range(1, 21), "PromoFull"), error=STOPPED)
    stored(store, "shufersal", *gz(range(1, 321), "PromoFull"), day=NOV_5)
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: retry run 081551Z-retry-9283 (PromoFull) ended "
                              "with: stopped: under 90 s left; the PromoFull list was not read in full: pages 17 to 21 "
                              "never read.")
    assert record["chains"]["shufersal"]["read_in_full"]["PromoFull"] is None


def test_not_read_in_full_alerts_on_its_own():
    """Every retry run ended clean, yet the readings leave a gap: the list moved between A and the retry, whose page 12
    starts after the last name A took (a main run's time stop is left to the retry). The sentence alone fails the
    morning."""
    store = MemoryStore()
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, RETRY_ID, "PriceFull", [rec(1), rec(12) | {"first": list_name(225)}, *pages(13, 21)],
          gz(range(1, 21)) + gz(range(225, 421)))
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == ("shufersal: the day's runs fell short: the PriceFull list was not read in full: every "
                              "page was read, but the pages read do not join up.")


def test_a_retry_that_listed_nothing_needs_its_kind_read_in_full_from_the_pages():
    """A run that ended with no error no longer proves the list read in full: B ended clean on a list that moved under
    it, leaving a gap after A's last name. The retry stopped on time before it listed anything, so no name of its needs
    vouching; its kind still needs the pages joined up."""
    store = MemoryStore()
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, B_ID, "PriceFull", [rec(1), rec(12) | {"first": list_name(225)}, *pages(13, 21)],
          gz(range(1, 21)) + gz(range(225, 421)))
    paged(store, RETRY_ID, "PriceFull", [], error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert alerts[0].text == (f"shufersal: the day's runs fell short: {time_stop()}; the PriceFull list was not read "
                              "in full: every page was read, but the pages read do not join up.")
    assert record["chains"]["shufersal"]["short_of_time"] == []


def test_a_blocked_run_does_not_join_in_the_check():
    """B was blocked downloading its last file (the owner cleared the latch before the retries): its pages do not
    count, so the list was not read in full."""
    store = MemoryStore()
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, B_ID, "PriceFull", B["pages"], B["listed"], blocked=BLOCKED)
    paged(store, RETRY_ID, "PriceFull", [rec(1)], gz(range(1, 21)), error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == (f"shufersal: the day's runs fell short: {time_stop()}; the PriceFull list was not read "
                              "in full: pages 13 to 21 never read, page 12 read in part.")
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] is None


def test_an_out_of_order_page_turns_joining_off_in_the_check():
    store = MemoryStore()
    out_of_order = [*(rec(page, in_order=page != 7) for page in range(1, 12)), rec(12, taken=1)]
    paged(store, A_ID, "PriceFull", out_of_order, A["listed"], error=STOPPED)
    paged(store, B_ID, "PriceFull", B["pages"], B["listed"])
    paged(store, RETRY_ID, "PriceFull", [rec(1)], gz(range(1, 21)), error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "failed")]
    assert alerts[0].text == (f"shufersal: the day's runs fell short: {time_stop()}; the PriceFull list was not read "
                              "in full: every page was read, but the pages read do not join up (page 7 of run "
                              "044522Z-main-a001 was out of order, so only a run that read every page in one go "
                              "counts).")
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] is None


def test_no_sentence_when_a_retry_was_blocked():
    """As R35: B's block latched the chain, so the retry did nothing, and the stopped alert covers the morning."""
    store = MemoryStore()
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    paged(store, B_ID, "PriceFull", [rec(1), *pages(12, 14)], gz(range(1, 21)) + gz(range(221, 281)), blocked=BLOCKED)
    paged(store, RETRY_ID, "PriceFull", [], blocked="stopped earlier")
    stored(store, "shufersal", *gz(range(1, 281)), day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    store.write_state("shufersal", latch())
    alerts, record = check_nov_5(store)
    assert kinds_of(alerts) == [("shufersal", "stopped")]
    assert record["chains"]["shufersal"]["failed"] is None
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] is None


def test_no_sentence_without_page_records():
    """A chain whose manifests carry no page records (every chain but Shufersal) gets R4's reasons only, though no run
    of it read its full kinds in full."""
    store = MemoryStore()
    names = [price("001"), price("001", kind="PromoFull")]
    manifest(store, "ramilevy", "main", listed=names, error=STOPPED, run_id="043000Z-main-0a0a")
    manifest(store, "ramilevy", "retry", listed=names, error=STOPPED, run_id="073000Z-retry-0b0b")
    stored(store, "ramilevy", *names)
    alerts, record = check_day(store, ["ramilevy"], DAY)
    assert kinds_of(alerts) == [("ramilevy", "failed")]
    assert alerts[0].text == ("ramilevy: the day's runs fell short: retry run 073000Z-retry-0b0b (Stores, PriceFull, "
                              "PromoFull, Price, Promo) ended with: stopped: under 90 s left.")
    assert record["chains"]["ramilevy"]["read_in_full"] == {"PriceFull": None, "PromoFull": None}


def test_a_pre_change_manifest_ended_clean_reads_in_full():
    """Deploy day (review focus 3): the morning's first runs wrote no page records and ended clean, so they read their
    kinds in full as R36 reads them; the retry, with page records, stopped on time after names they listed."""
    store = MemoryStore()
    legacy(store, A_ID, ["PriceFull"], gz(range(1, 421)))
    legacy(store, "051514Z-main-b001", ["PromoFull"], gz(range(1, 421), "PromoFull"))
    paged(store, RETRY_ID, "PriceFull", [rec(1), rec(2, taken=5)], gz(range(1, 26)), error=STOPPED)
    stored(store, "shufersal", *ALL_STORED, day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    alerts, record = check_nov_5(store)
    assert alerts == []
    assert record["chains"]["shufersal"]["read_in_full"]["PriceFull"] == [A_ID]
    assert record["chains"]["shufersal"]["short_of_time"] == ["074536Z-retry-2933 (PriceFull)"]


# ---- a page read on a later try (q24) ----

class Tried(MemoryStore):
    """A MemoryStore that stores each manifest as test_pages' `tried` gives it: every page record read in `tries`
    requests, or, with None, as written before tries were recorded. `timeouts[run_id]` is that run's list in place of
    the one `tried` gives (left out with None)."""

    def __init__(self, tries, timeouts=None):
        super().__init__()
        self.tries, self.timeouts = tries, timeouts or {}

    def put_record(self, key, body, now):
        record = tried(json.loads(body), self.tries)
        if self.tries is not None and record["run_id"] in self.timeouts:
            record["timeouts"] = self.timeouts[record["run_id"]]
        super().put_record(key, json.dumps(record).encode(), now)


PAGE_1_TIMED_OUT = (f"listing failed: PriceFull page 1 timed out on 3 tries: GET {LISTING} failed: The read operation "
                    "timed out")
PAGE_1_TRIES = {RETRY_ID: [asdict(PageTimeout("PriceFull", 1, attempt, 60.5)) for attempt in (1, 2, 3)]}
CHECK_RECORD_KEYS = {"manifests", "listed", "stored", "missing", "stopped", "failed", "short_of_time", "read_in_full",
                     "coverage"}


def stopped_retry_day(store):
    """test_a_stopped_retry_on_a_day_read_in_full_across_runs_is_quiet's day: 2026-11-05 as resumed, and the retry's
    fresh pass stopped on time on page 2."""
    nov_5(store)
    paged(store, RETRY_ID, "PriceFull", [rec(1), rec(2, taken=5)], gz(range(1, 26)), error=STOPPED)


def page_1_timed_out_day(store):
    """2026-11-06's shape (docs/shufersal-page-retry.md, section 4): A stopped on time on page 12 with every name it
    listed stored, PromoFull's retry read its whole list, and the PriceFull retry's page 1 timed out on every try, so
    it recorded no page."""
    paged(store, A_ID, "PriceFull", A["pages"], A["listed"], error=STOPPED)
    stored(store, "shufersal", *gz(range(1, 222)), day=NOV_5)
    whole(store, PROMO_RETRY_ID, "PromoFull")
    paged(store, RETRY_ID, "PriceFull", [], error=PAGE_1_TIMED_OUT)


@pytest.mark.parametrize("tries", [1, 3, None])
@pytest.mark.parametrize("day, alerts, short_of_time, read_in_full", [
    pytest.param(stopped_retry_day, [], ["074536Z-retry-2933 (PriceFull)"],
                 {"PriceFull": [A_ID, B_ID], "PromoFull": [PROMO_RETRY_ID]}, id="quiet"),
    pytest.param(page_1_timed_out_day, [Alert("shufersal", "failed", (
        "shufersal: the day's runs fell short: retry run 074536Z-retry-2933 (PriceFull) ended with: listing failed: "
        "PriceFull page 1 timed out on 3 tries: GET https://prices.shufersal.co.il/FileObject/UpdateCategory failed: "
        "The read operation timed out; the PriceFull list was not read in full: pages 13 to 21 never read, page 12 "
        "read in part."))], [], {"PriceFull": None, "PromoFull": [PROMO_RETRY_ID]}, id="alerting"),
])
def test_tries_do_not_change_the_check(tries, day, alerts, short_of_time, read_in_full):
    """Design, section 4: the check reads nothing new. The same day alerts, stays quiet and records alike whether its
    pages took one request each, three, or were written before tries were recorded; a retry whose page 1 timed out on
    every try fails the morning with the run's own error, and the check record gains no field."""
    store = Tried(tries, PAGE_1_TRIES)
    day(store)
    manifests = [json.loads(body) for body in store.read_records("manifests/")]
    assert {record.get("tries") for manifest in manifests for record in manifest["pages"]} == {tries}
    assert all(("timeouts" in manifest) == (tries is not None) for manifest in manifests)
    got, record = check_nov_5(store)
    chain = record["chains"]["shufersal"]
    assert got == alerts
    assert chain["short_of_time"] == short_of_time
    assert chain["read_in_full"] == read_in_full
    assert set(chain) == CHECK_RECORD_KEYS


# ---- coverage: recorded, never alerted ----

def coverage(store, slug="shufersal", day=DAY):
    return check_day(store, [slug], day)[1]["chains"][slug]["coverage"]


def test_coverage_is_recorded_and_never_alerts():
    store = MemoryStore()
    clean_day(store)
    stored(store, "shufersal", stores_name(), body=stores_file("030", "031", "032"))
    stored(store, "shufersal", price("030"))
    alerts, record = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert record["chains"]["shufersal"]["coverage"] == {
        "published": 2, "expected": 3, "ratio": 0.3333,  # store 030 and clean_day's 999, on no list
        "store_list": raw_key("shufersal", DAY, stores_name()), "note": None}


def test_no_coverage_at_all_never_alerts():
    store = MemoryStore()
    clean_day(store)
    stored(store, "shufersal", stores_name(), body=stores_file("030", "031"))
    alerts, _ = check_day(store, SLUGS, DAY)
    assert alerts == []
    assert coverage(store)["ratio"] == 0.0


def test_coverage_counts_stored_full_price_files_only():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(), body=stores_file("030", "031", "032", "033"))
    stored(store, "shufersal", price("030"), price("031", "PromoFull"), price("032", "Price"), price("033", "Promo"))
    cov = coverage(store)
    assert (cov["published"], cov["expected"], cov["ratio"]) == (1, 4, 0.25)


def test_coverage_compares_store_numbers_as_numbers():
    """Shufersal's store list holds "93"; its file names pad it to "093"."""
    store = MemoryStore()
    stored(store, "shufersal", stores_name(), body=stores_file("93", "7"))
    stored(store, "shufersal", price("093"), price("007"))
    cov = coverage(store)
    assert (cov["published"], cov["expected"], cov["ratio"]) == (2, 2, 1.0)


def test_coverage_counts_only_listed_stores_that_published():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(), body=stores_file("030", "031"))
    stored(store, "shufersal", price("030"), price("099"))
    cov = coverage(store)
    assert (cov["published"], cov["expected"], cov["ratio"]) == (2, 2, 0.5)


def test_coverage_from_the_real_store_lists():
    """Each portal's own Stores file: Shufersal's gzipped UTF-8, NCR's and Carrefour's UTF-16."""
    store = MemoryStore()
    for slug, portal, name, ids in (("shufersal", "shufersal", "Stores7290027600007-000-20261031-020.gz", ("314",)),
                                    ("ramilevy", "ncr", "Stores7290058140886-000-20261031-050500.xml", ("001", "002")),
                                    ("carrefour", "carrefour", "Stores7290055700007-000-20261031-000100.xml", ("002", "004", "009"))):
        stored(store, slug, name, body=(FIXTURES / portal / name).read_bytes())
        stored(store, slug, *(f"PriceFull{name[6:19]}-001-{i}-20261031-030000.gz" for i in ids))
    record = check_day(store, ["shufersal", "ramilevy", "carrefour"], DAY)[1]["chains"]
    assert record["shufersal"]["coverage"]["ratio"] == 0.3333
    assert record["ramilevy"]["coverage"]["ratio"] == 0.6667
    assert record["carrefour"]["coverage"]["ratio"] == 1.0


def test_coverage_uses_that_days_store_list_first():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(DAY - timedelta(days=1)), day=DAY - timedelta(days=1),
           body=stores_file("030", "031", "032", "033"))
    stored(store, "shufersal", stores_name(), body=stores_file("030", "031"))
    stored(store, "shufersal", price("030"))
    cov = coverage(store)
    assert (cov["expected"], cov["ratio"], cov["store_list"]) == (2, 0.5, raw_key("shufersal", DAY, stores_name()))


def test_coverage_uses_the_days_latest_store_list():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(time="050500"), body=stores_file("030", "031", "032", "033"))
    stored(store, "shufersal", stores_name(time="120000"), body=stores_file("030", "031"))
    stored(store, "shufersal", price("030"))
    cov = coverage(store)
    assert (cov["expected"], cov["store_list"]) == (2, raw_key("shufersal", DAY, stores_name(time="120000")))


def test_coverage_falls_back_to_the_latest_store_list_of_the_last_seven_days():
    store = MemoryStore()
    for back, ids in ((2, ("030", "031")), (5, ("030", "031", "032", "033"))):
        day = DAY - timedelta(days=back)
        stored(store, "shufersal", stores_name(day), day=day, body=stores_file(*ids))
    stored(store, "shufersal", price("030"))
    cov = coverage(store)
    two_back = DAY - timedelta(days=2)
    assert (cov["expected"], cov["ratio"], cov["store_list"]) == (2, 0.5, raw_key("shufersal", two_back, stores_name(two_back)))


def test_coverage_looks_back_seven_days_and_no_further():
    store = MemoryStore()
    seven_back, eight_back = DAY - timedelta(days=7), DAY - timedelta(days=8)
    stored(store, "shufersal", stores_name(eight_back), day=eight_back, body=stores_file("030", "031", "032", "033"))
    stored(store, "shufersal", price("030"))
    cov = coverage(store)
    assert (cov["published"], cov["expected"], cov["ratio"], cov["store_list"]) == (1, None, "unknown", None)
    assert "no Stores file" in cov["note"]
    stored(store, "shufersal", stores_name(seven_back), day=seven_back, body=stores_file("030", "031"))
    assert coverage(store)["store_list"] == raw_key("shufersal", seven_back, stores_name(seven_back))


def test_coverage_unknown_when_the_store_list_names_no_stores():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(), body=stores_file())
    stored(store, "shufersal", price("030"))
    cov = coverage(store)
    assert (cov["published"], cov["expected"], cov["ratio"]) == (1, None, "unknown")
    assert "names no stores" in cov["note"]


def test_coverage_leaves_out_store_ids_that_are_not_numbers():
    store = MemoryStore()
    stored(store, "shufersal", stores_name(), body=stores_file("030", "A1", "٣"))
    stored(store, "shufersal", price("030"))
    assert (coverage(store)["expected"], coverage(store)["ratio"]) == (1, 1.0)


def test_an_unreadable_store_list_is_unknown_and_the_alerts_still_go():
    store = MemoryStore()
    clean_day(store)
    stored(store, "shufersal", stores_name(), body=b"<Chain><Stores><Store>")
    manifest(store, "shufersal", "main", listed=[price("030")])
    alerts, record = check_day(store, SLUGS, DAY)
    assert kinds_of(alerts) == [("shufersal", "missing")]
    cov = record["chains"]["shufersal"]["coverage"]
    assert (cov["expected"], cov["ratio"]) == (None, "unknown")
    assert cov["note"].startswith("the store list could not be read: ParseError")


def test_the_check_record_is_json():
    store = MemoryStore()
    clean_day(store)
    stored(store, "shufersal", stores_name(), body=stores_file("030"))
    manifest(store, "shufersal", "main", listed=[price("031")])
    store.write_state("osherad", latch())
    _, record = check_day(store, SLUGS, DAY)
    assert json.loads(json.dumps(record)) == record

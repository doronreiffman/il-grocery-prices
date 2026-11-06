"""The run loop: one chain's files for one day, chosen by the date in their names, fetched one at a
time, checked, stored write-once, and recorded in a manifest whatever happens.

Most tests drive collect_chain with FakeSource, an adapter in place of a real portal, and a
MemoryStore, which keeps S3Store's rules. Bodies are whole gzips holding the fixtures' XML (or the
fixtures' UTF-16 XML), since check_payload unzips each one in full. FakePagedSource is FakeSource as a
paged adapter (Shufersal's), reporting the pages it reads and the page requests that timed out. Three tests run
the real Shufersal adapter over test_shufersal's fake network, where a listed name and its link's last segment
differ.
"""
import dataclasses
import functools
import gzip
import hashlib
import json
import logging
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from botocore.exceptions import ClientError

from collector.chains import CHAINS
from collector.http import Blocked, Http, HttpError, build_opener
from collector.names import KINDS, parse_file_name
from collector.sources import (Listed, ListingUnreadable, OutOfTime, PagedSource, PageRead, PageTimeout, Start,
                               never_short)
from collector.sources.shufersal import ShufersalSource
from collector.store import MemoryStore, manifest_key, raw_key
from collector.run import RunResult, collect_chain, manifest_bytes, new_run_id, stored_name
from test_pages import A, A_STORED, ALL_STORED, B, DAY as PAGES_DAY, gz, name, run as earlier_run

FIXTURES = Path(__file__).parent / "fixtures"
UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
CHAIN = dataclasses.replace(CHAINS["shufersal"], kinds=KINDS)  # every kind: the loop's rules are tested on all five
SLUG = CHAIN.slug
DAY = date(2026, 10, 31)
ISRAEL = ZoneInfo("Asia/Jerusalem")
NOW = datetime(2026, 10, 31, 6, 30, tzinfo=ISRAEL)
NOW_UTC = "2026-10-31T04:30:00+00:00"  # Israel is UTC+2 after 2026-10-25
RUN_ID = "043000Z-main-ab12"
CODE_SHA = "0123456789abcdef0123456789abcdef01234567"
PORTAL = "https://portal.example/file/d"

PRICE = "PriceFull7290027600007-001-030-20261031-030000.gz"
PRICE_2 = "PriceFull7290027600007-001-031-20261031-030000.gz"
PRICE_3 = "PriceFull7290027600007-001-032-20261031-030000.gz"
PRICE_4 = "PriceFull7290027600007-001-033-20261031-030000.gz"
PROMO = "PromoFull7290027600007-001-030-20261031-030000.gz"
UPDATE = "Price7290027600007-001-030-20261031-090000.gz"
STORES = "Stores7290027600007-000-20261031-050500.xml"
YESTERDAY = "PriceFull7290027600007-001-030-20261030-030000.gz"
TOMORROW = "PriceFull7290027600007-001-030-20261101-030000.gz"
CLOSED_IN_MAY = "PriceFull7290027600007-001-099-20260512-030000.gz"  # a closed store's last file, still listed

XML = gzip.decompress((FIXTURES / "shufersal" / "PriceFull7290027600007-001-030-20261031-030000.gz").read_bytes())
UTF16_STORES = (FIXTURES / "carrefour" / "Stores7290055700007-000-20261031-000100.xml").read_bytes()
HTML = b"<!DOCTYPE html><html><head><title>Please wait</title></head><body>Checking your browser</body></html>"
TRUNCATED = gzip.compress(XML)[:-20]


def body(name):
    """A whole gzip holding the fixture's XML, its own per name; Stores files are UTF-16 XML, as
    Carrefour's and Rami Levy's are served."""
    if name.startswith("Stores"):
        return UTF16_STORES
    return gzip.compress(XML + f"<!-- {name} -->".encode(), mtime=0)  # one body per name: a clock stamp could differ between two calls


def item(name, url=None):
    """A listed file, its link ending in the name as NCR's and Carrefour's do."""
    return Listed(parse_file_name(name), url or f"{PORTAL}/{name}")


class Clock:
    """Seconds left in the invocation, as Lambda's context gives them; tests move it."""

    def __init__(self, left=900.0):
        self.left = left

    def __call__(self):
        return self.left

    def set(self, left):
        def move():
            self.left = left
        return move


UNPARSED = object()  # a listed name that does not parse, counted by the fake listing


class FakeSource:
    """A portal adapter in place of a real one.

    `entries` is what listing() goes through, in order: a Listed is given to the caller; an exception
    is raised there; UNPARSED adds one to `unparsed`; any other callable is called (a page read that
    takes time) and the listing goes on. As the real adapters do, `unparsed` resets on the first
    next() and is final only once the listing is used up; it starts with a stale count.

    `answers[name]` is what download() gives for the item stored under `name`, in turn (the last
    answer repeats): bytes, an exception to raise, or a callable whose result is the answer. A name
    with no answers gets body(name). `events` logs listing gives and downloads in order."""

    def __init__(self, entries, answers=None):
        self.entries = entries
        self.answers = {name: list(a) if isinstance(a, list) else [a] for name, a in (answers or {}).items()}
        self.unparsed = 99  # an earlier listing's count
        self.listing_calls = []
        self.given = 0
        self.downloads = []
        self.events = []
        self.time_checks = []  # the run's time check, as each call was lent it

    def listing(self, http, kinds, short_of_time=never_short):
        self.listing_calls.append((http, kinds))
        self.time_checks.append(("listing", short_of_time))
        self.unparsed = 0
        for entry in self.entries:
            if isinstance(entry, BaseException):
                raise entry
            if entry is UNPARSED:
                self.unparsed += 1
            elif isinstance(entry, Listed):
                self.given += 1
                self.events.append(("listed", stored_name(entry)))
                yield entry
            else:
                entry()

    def download(self, http, item, short_of_time=never_short):
        name = stored_name(item)
        self.downloads.append((http, item.url))
        self.time_checks.append(("download", short_of_time))
        self.events.append(("download", name))
        queue = self.answers.get(name)
        answer = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else body(name)
        if callable(answer):
            answer = answer()
        if isinstance(answer, BaseException):
            raise answer
        return answer

    @property
    def downloaded(self):
        return [url.rsplit("/", 1)[-1] for _, url in self.downloads]


class NoNetwork(urllib.request.BaseHandler):
    """A network handler that fails every request: the run loop sends none of its own."""

    handler_order = 400

    def https_open(self, req):
        raise AssertionError(f"the run loop sent a request: {req.full_url}")

    http_open = https_open


HTTP = Http(UA, opener=build_opener(NoNetwork()), sleep=lambda seconds: None)


def collect(source, store=None, kinds=KINDS, clock=None, mode="main", day=DAY, http=HTTP, run_id=RUN_ID):
    store = MemoryStore() if store is None else store
    result = collect_chain(CHAIN, source, http, store, day, run_id, mode, kinds,
                           clock or Clock(), lambda: NOW, CODE_SHA)
    return result, store


def manifest(store, run_id=RUN_ID):
    return json.loads(store.objects[manifest_key(DAY, SLUG, run_id)].body)


def stored_bodies(store):
    prefix = raw_key(SLUG, DAY, "")
    return {key[len(prefix):]: stored.body for key, stored in store.objects.items() if key.startswith(prefix)}


def store_with(*names):
    store = MemoryStore()
    for name in names:
        store.put_raw(raw_key(SLUG, DAY, name), body(name), NOW)
    return store


def block(url=f"{PORTAL}/{PRICE_2}"):
    return Blocked(403, url + "?sig=SECRET", "HTTP 403")


def latch(reason):
    return {"stopped": True, "since": NOW_UTC, "reason": reason, "alerted": False}


# ---- choosing that day's files ----

def test_only_that_days_files_selected():
    """Old files in a listing (plan, risk 4): yesterday's, tomorrow's and a closed store's May file
    are not listed and not fetched; that day's are, whatever the clock says."""
    source = FakeSource([item(YESTERDAY), item(PRICE), item(CLOSED_IN_MAY), item(PROMO), item(TOMORROW), item(STORES)])
    result, store = collect(source)
    assert result.listed == [PRICE, PROMO, STORES]
    assert source.downloaded == [PRICE, PROMO, STORES]
    assert set(result.files) == {PRICE, PROMO, STORES}
    assert stored_bodies(store) == {name: body(name) for name in (PRICE, PROMO, STORES)}
    assert result.error is None and result.blocked is None


def test_kinds_filtered_again_whatever_the_adapter_gives():
    """An adapter should leave out kinds not asked for; the run loop does not count on it."""
    source = FakeSource([item(PRICE), item(PROMO), item(UPDATE), item(STORES)])
    result, _ = collect(source, kinds=("PriceFull", "Price"))
    assert result.listed == [PRICE, UPDATE]
    assert source.downloaded == [PRICE, UPDATE]
    assert source.listing_calls == [(HTTP, ("PriceFull", "Price"))]


def test_kinds_recorded():
    result, store = collect(FakeSource([item(PRICE)]), kinds=("PriceFull", "Price"))
    assert result.kinds == ["PriceFull", "Price"]
    assert manifest(store)["kinds"] == ["PriceFull", "Price"]


@pytest.mark.parametrize("kinds", [(), ("PriceFul",), ("PriceFull", "pricefull")])
def test_unknown_or_no_kinds_refused(kinds):
    """A mistyped kind would select nothing and look like a quiet morning."""
    source = FakeSource([item(PRICE)])
    store = MemoryStore()
    with pytest.raises(ValueError, match="kinds"):
        collect(source, store=store, kinds=kinds)
    assert source.listing_calls == [] and store.objects == {}


def test_files_already_stored_are_skipped():
    """Listed, but not downloaded and not in `files`; the rest are fetched and recorded with their
    outcome, size and SHA-256."""
    store = store_with(PRICE, STORES)
    source = FakeSource([item(PRICE), item(PROMO), item(STORES), item(PRICE_2)])
    result, _ = collect(source, store=store)
    assert result.listed == [PRICE, PROMO, STORES, PRICE_2]
    assert source.downloaded == [PROMO, PRICE_2]
    assert result.files == {
        PROMO: {"outcome": "stored", "size": len(body(PROMO)), "sha256": hashlib.sha256(body(PROMO)).hexdigest()},
        PRICE_2: {"outcome": "stored", "size": len(body(PRICE_2)), "sha256": hashlib.sha256(body(PRICE_2)).hexdigest()},
    }


def test_conflict_copy_counts_as_stored():
    store = MemoryStore()
    store.put_raw(raw_key(SLUG, DAY, PRICE) + ".0123456789ab", body(PRICE), NOW)
    source = FakeSource([item(PRICE)])
    result, _ = collect(source, store=store)
    assert result.listed == [PRICE] and source.downloaded == []


def test_stored_names_read_once():
    class CountingStore(MemoryStore):
        reads = 0

        def stored_names(self, slug, day):
            CountingStore.reads += 1
            return super().stored_names(slug, day)

    collect(FakeSource([item(PRICE), item(PROMO), item(PRICE_2)]), store=CountingStore())
    assert CountingStore.reads == 1


def test_outcomes_exists_and_conflict_recorded():
    """A file stored by another run after this one read the stored names: the same body is "exists",
    a different one "conflict" (kept beside the first)."""
    store = MemoryStore()

    def stored_meanwhile(name, other):
        def answer():
            store.put_raw(raw_key(SLUG, DAY, name), other, NOW)
            return body(name)
        return answer

    source = FakeSource([item(PRICE), item(PROMO)],
                        {PRICE: stored_meanwhile(PRICE, body(PRICE)), PROMO: stored_meanwhile(PROMO, body(PRICE))})
    result, _ = collect(source, store=store)
    assert result.files[PRICE]["outcome"] == "exists"
    assert result.files[PROMO]["outcome"] == "conflict"
    assert result.files[PROMO]["sha256"] == hashlib.sha256(body(PROMO)).hexdigest()


def test_a_name_listed_twice_counts_once_the_first_kept():
    """A listing can change while it is read; the second time a name comes, it is ignored, even when
    its first download failed."""
    first, second = item(PRICE, f"{PORTAL}/first/{PRICE}"), item(PRICE, f"{PORTAL}/second/{PRICE}")
    source = FakeSource([first, item(PROMO), second], {PRICE: HttpError("timed out")})
    result, _ = collect(source)
    assert result.listed == [PRICE, PROMO]
    assert [url for _, url in source.downloads] == [first.url, first.url, item(PROMO).url]
    assert list(result.failed) == [PRICE]


def test_stored_name_is_the_links_last_segment():
    """Ruling R16: Shufersal lists a name without .gz and links `<name>.gz`; the file is stored, listed
    and compared under the link's name, without its signed query."""
    listed_name = PRICE_2.removesuffix(".gz")
    shufersal_like = Listed(parse_file_name(listed_name),
                            f"https://pricesprodpublic.blob.core.windows.net/pricefull/{PRICE_2}?sv=1&sig=SECRET&se=x")
    assert stored_name(shufersal_like) == PRICE_2
    store = store_with(PRICE)
    already = Listed(parse_file_name(PRICE.removesuffix(".gz")),
                     f"https://pricesprodpublic.blob.core.windows.net/pricefull/{PRICE}?sig=SECRET")
    source = FakeSource([already, shufersal_like])
    result, store = collect(source, store=store)
    assert result.listed == [PRICE, PRICE_2]
    assert len(source.downloads) == 1
    assert set(result.files) == {PRICE_2}
    assert raw_key(SLUG, DAY, PRICE_2) in store.objects


def test_the_real_shufersal_adapter_end_to_end():
    """ShufersalSource over the fake network test_shufersal.py uses: that day's rows are stored under
    their links' names (with .gz), yesterday's row is not fetched."""
    from test_shufersal import FILE_HOST, connect, gz, listing_url, page, served
    rows = ["PriceFull7290027600007-001-040-20261031-030000", "PriceFull7290027600007-001-041-20261030-030000",
            "PriceFull7290027600007-001-042-20261031-030000"]
    http, portal = connect({listing_url(2, 1): served(page(2, rows, last=None))}, files=gz())
    result, store = collect(ShufersalSource(), kinds=("PriceFull",), http=http)
    assert result.listed == [rows[0] + ".gz", rows[2] + ".gz"]
    assert [url.split("?")[0] for url in portal.requested[1:]] == [f"{FILE_HOST}/pricefull/{rows[0]}.gz",
                                                                    f"{FILE_HOST}/pricefull/{rows[2]}.gz"]
    assert set(stored_bodies(store)) == {rows[0] + ".gz", rows[2] + ".gz"}
    assert result.error is None and result.blocked is None and result.unparsed == 0


# ---- reading the listing ----

def test_listing_read_once():
    source = FakeSource([item(PRICE), item(PROMO)], {PRICE: [HttpError("timed out"), body(PRICE)]})
    collect(source)
    assert len(source.listing_calls) == 1


def test_listing_read_as_files_are_fetched():
    """Ruling R16: Shufersal's signed links expire, so each file is fetched before the listing is read
    on (the adapter reads a page only once the previous page's rows are taken)."""
    source = FakeSource([item(PRICE), item(YESTERDAY), item(PROMO)])
    collect(source)
    assert source.events == [("listed", PRICE), ("download", PRICE), ("listed", YESTERDAY),
                             ("listed", PROMO), ("download", PROMO)]


def test_http_given_to_the_adapter():
    source = FakeSource([item(PRICE)])
    collect(source)
    assert source.listing_calls[0][0] is HTTP and source.downloads[0][0] is HTTP


def test_listing_read_at_is_when_the_listing_was_read_in_utc():
    result, store = collect(FakeSource([item(PRICE)]))
    assert result.listing_read_at == NOW_UTC
    assert manifest(store)["listing_read_at"] == NOW_UTC


def test_unparsed_read_once_the_listing_is_used_up():
    """Ruling R13: the count is final only at the end (it resets on the first next())."""
    source = FakeSource([UNPARSED, item(PRICE), UNPARSED, item(PROMO), UNPARSED])
    result, store = collect(source)
    assert result.unparsed == 3
    assert manifest(store)["unparsed"] == 3


def test_unparsed_zero_when_the_listing_never_finished():
    source = FakeSource([UNPARSED, item(PRICE), UNPARSED, block(), item(PROMO)])
    result, _ = collect(source)
    assert result.unparsed == 0


def test_listing_unreadable():
    """R23: the run fails with the reason; nothing is stored, the manifest is written."""
    source = FakeSource([ListingUnreadable("PriceFull page 1: no rows")])
    result, store = collect(source)
    assert result.error == "listing unreadable: PriceFull page 1: no rows"
    assert stored_bodies(store) == {}
    assert result.blocked is None and store.read_state(SLUG) == {}
    assert manifest(store)["error"] == "listing unreadable: PriceFull page 1: no rows"


def test_listing_unreadable_after_some_files():
    source = FakeSource([item(PRICE), ListingUnreadable("PriceFull page 2: 7 cells, not 8"), item(PROMO)])
    result, store = collect(source)
    assert result.error == "listing unreadable: PriceFull page 2: 7 cells, not 8"
    assert set(stored_bodies(store)) == {PRICE}
    assert result.listed == [PRICE] and result.not_attempted == []


def test_listing_unreadable_from_a_download_stops_the_run():
    """R23: Shufersal's expired-link refresh reads the listing again, and it can fail to read."""
    source = FakeSource([item(PRICE), item(PROMO), item(PRICE_2)],
                        {PROMO: ListingUnreadable("PromoFull page 1: no rows")})
    result, store = collect(source)
    assert result.error == "listing unreadable: PromoFull page 1: no rows"
    assert source.downloaded == [PRICE, PROMO]
    assert result.failed == {PROMO: "listing unreadable: PromoFull page 1: no rows"}
    assert set(stored_bodies(store)) == {PRICE}
    assert source.given == 2


def test_listing_http_error_fails_the_run():
    """A listing that times out is not read again in this run (NCR would log in again); the retry run
    reads it afresh."""
    source = FakeSource([item(PRICE), HttpError("GET https://prices.shufersal.co.il/FileObject/UpdateCategory failed: timed out")])
    result, store = collect(source)
    assert result.error == "listing failed: GET https://prices.shufersal.co.il/FileObject/UpdateCategory failed: timed out"
    assert set(stored_bodies(store)) == {PRICE}
    assert len(source.listing_calls) == 1
    assert result.blocked is None and store.read_state(SLUG) == {}


# ---- blocks and the latch ----

def test_stopped_chain_does_nothing():
    store = MemoryStore()
    store.write_state(SLUG, latch("HTTP 403: earlier"))
    source = FakeSource([item(PRICE)])
    result, _ = collect(source, store=store)
    assert result.blocked == "stopped earlier"
    assert source.listing_calls == [] and source.downloads == []
    assert result.listed == [] and result.listing_read_at is None and result.error is None
    assert store.read_state(SLUG) == latch("HTTP 403: earlier")
    assert manifest(store)["blocked"] == "stopped earlier"


def test_state_that_is_not_stopped_runs():
    store = MemoryStore()
    store.write_state(SLUG, {"stopped": False})
    result, _ = collect(FakeSource([item(PRICE)]), store=store)
    assert result.blocked is None and set(result.files) == {PRICE}


def test_blocked_in_the_listing_latches_and_stops():
    refusal = Blocked(429, "https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&page=2", "HTTP 429")
    source = FakeSource([item(PRICE), refusal, item(PROMO)])
    result, store = collect(source)
    reason = "HTTP 429: https://prices.shufersal.co.il/FileObject/UpdateCategory"
    assert result.blocked == reason
    assert store.read_state(SLUG) == latch(reason)
    assert source.downloaded == [PRICE] and source.given == 1
    assert result.error is None
    assert manifest(store)["blocked"] == reason


def test_blocked_on_a_download_latches_and_stops():
    source = FakeSource([item(PRICE), item(PRICE_2), item(PROMO)], {PRICE_2: block()})
    result, store = collect(source)
    reason = f"HTTP 403: {PORTAL}/{PRICE_2}"
    assert result.blocked == reason and "SECRET" not in reason
    assert store.read_state(SLUG) == latch(reason)
    assert source.downloaded == [PRICE, PRICE_2]
    assert source.given == 2
    assert result.failed == {PRICE_2: reason}
    assert set(stored_bodies(store)) == {PRICE}
    assert result.not_attempted == []


def test_blocked_on_the_retry_latches():
    source = FakeSource([item(PRICE_2), item(PROMO)], {PRICE_2: [HttpError("reset"), block()]})
    result, store = collect(source)
    assert result.blocked == f"HTTP 403: {PORTAL}/{PRICE_2}"
    assert store.read_state(SLUG)["stopped"] is True
    assert source.downloaded == [PRICE_2, PRICE_2]


def test_html_where_a_file_belongs_latches():
    """A file link answering with an HTML page is a block, not a bad file: no retry."""
    source = FakeSource([item(PRICE), item(PRICE_2), item(PROMO)], {PRICE_2: HTML})
    result, store = collect(source)
    reason = f"{PRICE_2}: HTML where a file belongs"
    assert result.blocked == reason
    assert store.read_state(SLUG) == latch(reason)
    assert source.downloaded == [PRICE, PRICE_2]
    assert result.failed == {PRICE_2: reason}
    assert set(stored_bodies(store)) == {PRICE}


def test_gzipped_html_latches():
    source = FakeSource([item(PRICE)], {PRICE: gzip.compress(HTML)})
    result, store = collect(source)
    assert result.blocked == f"{PRICE}: HTML where a file belongs"
    assert store.read_state(SLUG)["stopped"] is True


def test_html_on_the_retry_latches():
    source = FakeSource([item(PRICE), item(PROMO)], {PRICE: [b"", HTML]})
    result, store = collect(source)
    assert result.blocked == f"{PRICE}: HTML where a file belongs"
    assert source.downloaded == [PRICE, PRICE]



class LatchFails(MemoryStore):
    """A store whose state put fails, as S3 can."""

    def write_state(self, slug, state):
        raise ClientError({"Error": {"Code": "InternalError", "Message": "We encountered an internal error"}}, "PutObject")


def test_a_block_in_the_listing_is_recorded_when_its_latch_cannot_be_written():
    """The chain is not stopped, so the manifest is the only record of what the portal did: it keeps
    the block and says the latch was not written; the invocation fails."""
    refusal = Blocked(403, "https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&page=2", "HTTP 403")
    source = FakeSource([item(PRICE), refusal, item(PROMO)])
    store = LatchFails()
    with pytest.raises(ClientError, match="PutObject"):
        collect(source, store=store)
    record = manifest(store)
    assert record["blocked"] == "HTTP 403: https://prices.shufersal.co.il/FileObject/UpdateCategory"
    assert record["error"].startswith("latch not written: ClientError: ") and "PutObject" in record["error"]
    assert record["listed"] == [PRICE] and list(record["files"]) == [PRICE]
    assert source.given == 1 and source.downloaded == [PRICE]
    assert store.read_state(SLUG) == {}


def test_a_block_on_a_download_is_recorded_when_its_latch_cannot_be_written():
    source = FakeSource([item(PRICE), item(PRICE_2), item(PROMO)], {PRICE_2: block()})
    store = LatchFails()
    with pytest.raises(ClientError, match="PutObject"):
        collect(source, store=store)
    record = manifest(store)
    reason = f"HTTP 403: {PORTAL}/{PRICE_2}"
    assert record["blocked"] == reason and record["failed"] == {PRICE_2: reason}
    assert record["error"].startswith("latch not written: ClientError: ") and "PutObject" in record["error"]
    assert source.given == 2 and source.downloaded == [PRICE, PRICE_2]
    assert store.read_state(SLUG) == {}


# ---- one retry ----

@pytest.mark.parametrize("bad", [b"", TRUNCATED, b"not a price file", gzip.compress(b"data")])
def test_bad_payload_retried_once_then_failed(bad):
    source = FakeSource([item(PRICE), item(PROMO)], {PRICE: bad})
    result, store = collect(source)
    assert source.downloaded == [PRICE, PRICE, PROMO]
    assert list(result.failed) == [PRICE] and result.failed[PRICE].startswith(PRICE + ": ")
    assert set(result.files) == {PROMO} and set(stored_bodies(store)) == {PROMO}
    assert result.error is None and result.blocked is None


def test_bad_payload_then_good_is_stored():
    source = FakeSource([item(PRICE)], {PRICE: [TRUNCATED, body(PRICE)]})
    result, store = collect(source)
    assert result.files[PRICE]["outcome"] == "stored" and result.failed == {}
    assert stored_bodies(store) == {PRICE: body(PRICE)}


def test_http_error_retried_once_then_failed():
    source = FakeSource([item(PRICE), item(PROMO)], {PRICE: HttpError("HTTP 500 from https://portal.example/file/d/x")})
    result, _ = collect(source)
    assert source.downloaded == [PRICE, PRICE, PROMO]
    assert result.failed == {PRICE: "HTTP 500 from https://portal.example/file/d/x"}
    assert set(result.files) == {PROMO}
    assert result.error is None and result.blocked is None


def test_http_error_then_good_is_stored():
    source = FakeSource([item(PRICE)], {PRICE: [HttpError("timed out"), body(PRICE)]})
    result, _ = collect(source)
    assert set(result.files) == {PRICE} and result.failed == {}


def test_a_failed_store_costs_that_file_only():
    """R23: a put that S3 refuses (here a 404 on the head after a 409: another write unfinished) is
    that file's failure; the run goes on."""
    class FlakyStore(MemoryStore):
        def put_raw(self, key, data, now):
            if key.endswith(PRICE):
                raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
            return super().put_raw(key, data, now)

    source = FakeSource([item(PRICE), item(PROMO)])
    result, store = collect(source, store=FlakyStore())
    assert list(result.failed) == [PRICE] and "HeadObject" in result.failed[PRICE]
    assert set(result.files) == {PROMO}
    assert source.downloaded == [PRICE, PROMO]
    assert result.error is None


# ---- time running out ----

def test_stops_before_timeout_and_records_not_attempted():
    """Plan, risk 2, with ruling R32's 90 s: after two files the next listing read leaves under 90 s;
    the file it gave is not attempted, the listing is read no further, nothing is half-stored, the
    manifest is written."""
    clock = Clock()
    source = FakeSource([item(PRICE), item(PROMO), clock.set(89.9), item(PRICE_2), item(PRICE_3)])
    result, store = collect(source, clock=clock)
    assert source.downloaded == [PRICE, PROMO]
    assert result.listed == [PRICE, PROMO, PRICE_2]
    assert result.not_attempted == [PRICE_2]
    assert source.given == 3
    assert result.error == "stopped: under 90 s left"
    assert set(stored_bodies(store)) == {PRICE, PROMO}
    assert manifest(store)["not_attempted"] == [PRICE_2]
    assert manifest(store)["error"] == "stopped: under 90 s left"


def test_time_checked_between_listing_items():
    """R23: a retry run that skips stored files reads page after page without a download; it stops
    reading when time runs short, not at Lambda's deadline."""
    clock = Clock()
    store = store_with(PRICE, PROMO, PRICE_2)
    source = FakeSource([item(PRICE), clock.set(30), item(PROMO), item(PRICE_2), item(PRICE_3)])
    result, _ = collect(source, store=store, clock=clock)
    assert source.given == 2 and source.downloads == []
    assert result.listed == [PRICE, PROMO]
    assert result.not_attempted == [] and result.error == "stopped: under 90 s left"


def test_time_checked_after_a_download():
    clock = Clock()
    source = FakeSource([item(PRICE), item(PROMO), item(PRICE_2)], {PROMO: lambda: (clock.set(10)(), body(PROMO))[1]})
    result, _ = collect(source, clock=clock)
    assert source.downloaded == [PRICE, PROMO] and set(result.files) == {PRICE, PROMO}
    assert source.given == 2 and result.not_attempted == []
    assert result.error == "stopped: under 90 s left"


def test_time_short_at_the_start_reads_nothing():
    source = FakeSource([item(PRICE)])
    result, store = collect(source, clock=Clock(45))
    assert source.given == 0 and source.downloads == []
    assert result.listing_read_at is None and result.listed == []
    assert result.error == "stopped: under 90 s left"
    assert manifest(store)["error"] == "stopped: under 90 s left"


def test_the_run_lends_the_adapter_its_own_time_check():
    """An adapter that makes requests of its own between the run's checks (Shufersal's refresh after an
    expired link, NCR's listing reads) asks the run's own check, ruling R32's 90 s, before each."""
    clock = Clock()
    source = FakeSource([item(PRICE)])
    collect(source, clock=clock)
    assert [kind for kind, _ in source.time_checks] == ["listing", "download"]
    for _, check in source.time_checks:
        clock.left = 90.0
        assert check() is False
        clock.left = 89.9
        assert check() is True


def test_out_of_time_in_the_listing_stops_the_run_as_time_does():
    source = FakeSource([item(PRICE), OutOfTime("before page 2 of the PriceFull listing"), item(PROMO)])
    result, store = collect(source)
    assert result.listed == [PRICE] and set(result.files) == {PRICE}
    assert result.error == "stopped: under 90 s left" and result.blocked is None
    assert result.failed == {} and result.not_attempted == []
    assert manifest(store)["error"] == "stopped: under 90 s left"


def test_out_of_time_in_a_download_fails_that_file_and_stops_the_run():
    """Shufersal's refresh stopped short: the file was tried (its link had expired), so it is failed with why, not
    tried again, and the run stops; the retry run lists it again."""
    stop = OutOfTime(f"{PROMO}: its link expired; stopped before page 2 of the PromoFull listing")
    source = FakeSource([item(PRICE), item(PROMO), item(PRICE_2)], {PROMO: stop})
    result, store = collect(source)
    assert source.downloaded == [PRICE, PROMO] and source.given == 2
    assert result.failed == {PROMO: f"{PROMO}: its link expired; stopped before page 2 of the PromoFull listing: "
                                     "under 90 s left"}
    assert result.error == "stopped: under 90 s left" and result.blocked is None
    assert result.not_attempted == [] and set(result.files) == {PRICE}
    assert manifest(store)["failed"] == result.failed


def test_ninety_seconds_left_is_enough():
    result, _ = collect(FakeSource([item(PRICE)]), clock=Clock(90.0))
    assert set(result.files) == {PRICE} and result.error is None


def test_no_retry_under_ninety_seconds():
    """The retry is a download too: with under 90 s left it is not tried, and the file is failed."""
    clock = Clock()
    source = FakeSource([item(PRICE), item(PROMO)], {PRICE: lambda: (clock.set(20)(), HttpError("timed out"))[1]})
    result, _ = collect(source, clock=clock)
    assert source.downloaded == [PRICE]
    assert result.failed == {PRICE: "timed out; not tried again: under 90 s left"}
    assert result.not_attempted == [] and result.error == "stopped: under 90 s left"


# ---- the manifest, in every outcome ----

def _unexpected():
    return FakeSource([item(PRICE), item(PROMO)], {PROMO: RuntimeError("an adapter bug")})


OUTCOMES = {  # name: (the source, seconds left at the start, blocked, error)
    "normal": (lambda: FakeSource([item(PRICE)]), 900, None, None),
    "blocked": (lambda: FakeSource([item(PRICE)], {PRICE: block(f"{PORTAL}/{PRICE}")}), 900, f"HTTP 403: {PORTAL}/{PRICE}", None),
    "html": (lambda: FakeSource([item(PRICE)], {PRICE: HTML}), 900, f"{PRICE}: HTML where a file belongs", None),
    "unreadable": (lambda: FakeSource([ListingUnreadable("no rows")]), 900, None, "listing unreadable: no rows"),
    "listing failed": (lambda: FakeSource([HttpError("reset")]), 900, None, "listing failed: reset"),
    "timed out": (lambda: FakeSource([item(PRICE)]), 30, None, "stopped: under 90 s left"),
}


@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_manifest_written_in_every_outcome(outcome):
    make, left, blocked, error = OUTCOMES[outcome]
    result, store = collect(make(), clock=Clock(left))
    key = manifest_key(DAY, SLUG, RUN_ID)
    assert store.objects[key].body == manifest_bytes(result, CODE_SHA)
    assert store.objects[key].lock_mode == "GOVERNANCE"
    assert store.objects[key].retain_until == NOW + timedelta(days=3650)
    assert (result.blocked, result.error) == (blocked, error)


def test_manifest_written_when_stopped_earlier():
    store = MemoryStore()
    store.write_state(SLUG, latch("HTTP 403: earlier"))
    result, _ = collect(FakeSource([item(PRICE)]), store=store)
    assert store.objects[manifest_key(DAY, SLUG, RUN_ID)].body == manifest_bytes(result, CODE_SHA)


def test_unexpected_error_recorded_in_the_manifest_and_raised():
    """A bug must not pass as a quiet morning: the manifest says what happened, and the invocation fails."""
    store = MemoryStore()
    source = _unexpected()
    with pytest.raises(RuntimeError, match="an adapter bug"):
        collect(source, store=store)
    record = manifest(store)
    assert record["error"] == "unexpected error: RuntimeError: an adapter bug"
    assert record["listed"] == [PRICE, PROMO] and list(record["files"]) == [PRICE]


def test_unexpected_error_reading_the_state_still_writes_a_manifest():
    class BrokenState(MemoryStore):
        def read_state(self, slug):
            raise ClientError({"Error": {"Code": "InternalError", "Message": "We encountered an internal error"}}, "GetObject")

    store = BrokenState()
    with pytest.raises(ClientError):
        collect(FakeSource([item(PRICE)]), store=store)
    assert manifest(store)["error"].startswith("unexpected error: ClientError: ")


def test_manifest_bytes():
    result = RunResult(chain=SLUG, run_id=RUN_ID, mode="retry", day=DAY, kinds=["PriceFull", "Price"],
                       listing_read_at=NOW_UTC, listed=[PROMO, PRICE],
                       files={PROMO: {"size": 3, "sha256": "ab", "outcome": "stored"}},
                       failed={PRICE: "timed out"}, not_attempted=[], unparsed=2, blocked=None, error=None)
    data = manifest_bytes(result, CODE_SHA)
    record = json.loads(data)
    assert record == {
        "chain": SLUG, "run_id": RUN_ID, "mode": "retry", "day": "2026-10-31", "kinds": ["PriceFull", "Price"],
        "listing_read_at": NOW_UTC, "listed": [PROMO, PRICE],
        "files": {PROMO: {"outcome": "stored", "size": 3, "sha256": "ab"}},
        "failed": {PRICE: "timed out"}, "not_attempted": [], "unparsed": 2, "blocked": None, "error": None,
        "pages": [], "timeouts": [], "code_sha": CODE_SHA,
    }
    assert list(record) == sorted(record)
    assert list(record["files"][PROMO]) == sorted(record["files"][PROMO])


def test_manifest_records_the_run():
    result, store = collect(FakeSource([item(PRICE)]), mode="retry", run_id="093000Z-retry-0f0f")
    record = manifest(store, "093000Z-retry-0f0f")
    assert (result.chain, result.run_id, result.mode, result.day) == (SLUG, "093000Z-retry-0f0f", "retry", DAY)
    assert (record["chain"], record["run_id"], record["mode"], record["day"]) == (SLUG, "093000Z-retry-0f0f", "retry", "2026-10-31")
    assert record["code_sha"] == CODE_SHA


@pytest.mark.parametrize("kinds", [("Price",), ("PriceFull", "Promo"), ("Stores", "PriceFull", "PromoFull", "Price", "Promo")])
def test_kinds_the_chain_does_not_collect_are_refused(kinds):
    """Shufersal collects its store list and full files only (owner, 2026-11-01)."""
    source = FakeSource([item(PRICE)])
    store = MemoryStore()
    with pytest.raises(ValueError, match=r"kinds must be some of \('Stores', 'PriceFull', 'PromoFull'\)"):
        collect_chain(CHAINS["shufersal"], source, HTTP, store, DAY, RUN_ID, "main", kinds, Clock(), lambda: NOW, CODE_SHA)
    assert source.listing_calls == [] and store.objects == {}


def test_naive_now_refused():
    source = FakeSource([item(PRICE)])
    store = MemoryStore()
    with pytest.raises(ValueError, match="time zone"):
        collect_chain(CHAIN, source, HTTP, store, DAY, RUN_ID, "main", KINDS, Clock(), lambda: datetime(2026, 10, 31, 6, 30), CODE_SHA)
    assert source.listing_calls == [] and store.objects == {}


# ---- run ids ----

def test_new_run_id_is_utc_time_mode_and_four_hex():
    run_id = new_run_id(datetime(2026, 10, 31, 6, 30, 5, tzinfo=ISRAEL), "main")
    assert re.fullmatch(r"043005Z-main-[0-9a-f]{4}", run_id)


def test_new_run_id_from_utc():
    assert new_run_id(datetime(2026, 11, 1, 23, 59, 59, tzinfo=timezone.utc), "retry").startswith("235959Z-retry-")


def test_new_run_id_differs_between_calls():
    """A manual re-run in the same second must not collide with a stored manifest."""
    ids = {new_run_id(NOW, "main") for _ in range(20)}
    assert len(ids) > 1


def test_new_run_id_refuses_a_naive_time():
    with pytest.raises(ValueError, match="time zone"):
        new_run_id(datetime(2026, 10, 31, 6, 30), "main")


# ---- a paged listing: where each kind starts, and the pages read (ruling R37) ----

class FakePagedSource(FakeSource, PagedSource):
    """FakeSource as a paged adapter (Shufersal's): a PageRead entry is reported to `on_page` and a PageTimeout entry
    to `on_timeout`, each where it stands in the listing, and the `starts` the run hands over are kept in `starts`."""

    def __init__(self, entries, answers=None):
        super().__init__(entries, answers)
        self.starts = None

    def listing(self, http, kinds, short_of_time=never_short, starts=None, on_page=None, on_timeout=None):
        self.starts = starts
        reported = {PageRead: on_page, PageTimeout: on_timeout}
        self.entries = [functools.partial(reported[type(entry)], entry) if type(entry) in reported else entry
                        for entry in self.entries]
        return super().listing(http, kinds, short_of_time)


def stored_day(day, manifests=(), stored=()):
    """A store holding the chain's earlier manifests of `day` (as JSON, under each one's run id) and the files the
    day stored (`<name>.gz`)."""
    store = MemoryStore()
    for record in manifests:
        store.put_record(manifest_key(day, SLUG, record["run_id"]), json.dumps(record).encode(), NOW)
    for file in stored:
        store.put_raw(raw_key(SLUG, day, file), b"stored", NOW)
    return store


def row(store, day=20261031, ends_page=False):
    """A PriceFull row of `store` (a number) as Shufersal lists it: the name without .gz, the link to `<name>.gz`
    (ruling R16)."""
    raw = f"PriceFull7290027600007-001-{store:03d}-{day}-030000"
    return Listed(parse_file_name(raw), f"{PORTAL}/{raw}.gz", ends_page)


def report(page, first, last, *, rows=20, last_page=None, kind="PriceFull", seconds=41.2, tries=1):
    """A page as the adapter reports it: in order, holding `rows` rows from `first` to `last`, read in `tries`
    requests."""
    return PageRead(kind, page, rows, first, last, last_page, seconds, True, tries)


def given(page, stores, last_page=None):
    """Page `page` as a paged listing goes through it, holding the rows of `stores`: its report, then its rows, the
    last one ending the page."""
    rows = [row(store) for store in stores]
    rows[-1] = dataclasses.replace(rows[-1], ends_page=True)
    return [report(page, rows[0].name.raw, rows[-1].name.raw, rows=len(rows), last_page=last_page), *rows]


def taken(read, through):
    """`read`'s record in the manifest, taken through `through`."""
    return dataclasses.asdict(read) | {"taken_through": through}


# A with its page 7 out of order
OUT_OF_ORDER = A | {"pages": [record | {"in_order": record["page"] != 7} for record in A["pages"]]}


@pytest.mark.parametrize("earlier, stored, start", [
    pytest.param([A], A_STORED, Start(page=12, furthest=name(221)), id="not yet read in full"),
    pytest.param([A], A_STORED - set(gz([85])), Start(page=12, furthest=name(221), detours=(5,)),
                 id="a failed file earlier on the list"),
    pytest.param([A, B], ALL_STORED, Start(), id="read in full"),
    pytest.param([OUT_OF_ORDER], A_STORED - set(gz([85])), Start(), id="no usable record"),
])
def test_a_paged_source_is_handed_a_start_per_kind(earlier, stored, start):
    """Design, section 2: the run reads the chain's earlier manifests of the day and hands the adapter a start per
    kind (collector.pages.start_for), the names the day stored included."""
    source = FakePagedSource([])
    collect(source, store=stored_day(PAGES_DAY, earlier, stored), kinds=("PriceFull",), day=PAGES_DAY)
    assert source.starts == {"PriceFull": start}


@pytest.mark.parametrize("key", [
    pytest.param(manifest_key(PAGES_DAY, "ramilevy", "043000Z-main-a000"), id="another chain"),
    pytest.param(manifest_key(PAGES_DAY - timedelta(days=1), SLUG, "043000Z-main-a000"), id="another day"),
])
def test_earlier_manifests_are_the_chains_own_for_the_day(key):
    """A clean manifest without page records reads the kind in full (as ruling R36 reads it): read here, it would turn
    the resume into a fresh pass."""
    store = stored_day(PAGES_DAY, [A], A_STORED)
    store.put_record(key, json.dumps(earlier_run("043000Z-main-a000")).encode(), NOW)
    source = FakePagedSource([])
    collect(source, store=store, kinds=("PriceFull",), day=PAGES_DAY)
    assert source.starts == {"PriceFull": Start(page=12, furthest=name(221))}


def test_a_source_that_does_not_page_reads_no_manifests_and_records_no_pages():
    """NCR's and Carrefour's listings are called as they were before page records existed: no manifest read, no start,
    no page."""
    class CountingStore(MemoryStore):
        reads = 0

        def read_records(self, prefix):
            CountingStore.reads += 1
            return super().read_records(prefix)

    result, store = collect(FakeSource([item(PRICE)]), store=CountingStore())
    assert CountingStore.reads == 0
    assert result.pages == [] and manifest(store)["pages"] == []
    assert set(result.files) == {PRICE}


def test_a_failed_read_of_the_earlier_manifests_fails_the_run():
    """A failed read of the day's earlier manifests fails the run as an unexpected error, as a failed read of the latch
    does, with no fall-back to a fresh pass: the manifest is still written, the error raised, and no listing asked
    for, so the manifest holds no listing time."""
    class BrokenRecords(MemoryStore):
        def read_records(self, prefix):
            raise ClientError({"Error": {"Code": "InternalError", "Message": "We encountered an internal error"}},
                              "ListObjectsV2")

    store = BrokenRecords()
    source = FakePagedSource([row(100, ends_page=True)])
    with pytest.raises(ClientError):
        collect(source, store=store, kinds=("PriceFull",))
    record = manifest(store)
    assert record["error"].startswith("unexpected error: ClientError: ")
    assert record["listing_read_at"] is None
    assert source.listing_calls == [] and source.downloads == []


def test_each_page_is_recorded_with_how_far_the_run_took_it():
    """The run can stop between any two rows, so a page is recorded taken through the last row the run took from it;
    the rows after it were never listed."""
    clock = Clock()
    page_1, page_2 = given(1, range(100, 120), last_page=2), given(2, range(120, 140), last_page=2)
    third = row(122)
    answers = {stored_name(third): lambda: (clock.set(30)(), body(stored_name(third)))[1]}  # the clock runs short
    source = FakePagedSource([*page_1, *page_2], answers)
    result, store = collect(source, kinds=("PriceFull",), clock=clock)
    assert result.error == "stopped: under 90 s left"
    assert result.pages == [taken(page_1[0], page_1[0].last), taken(page_2[0], third.name.raw)]
    assert manifest(store)["pages"] == result.pages


def test_a_row_of_another_day_counts_as_taken():
    """The run took the row, though it keeps only the day's: it was listed, so the page is taken this far."""
    clock = Clock()
    yesterday = row(101, day=20261030)
    entries = [report(1, row(100).name.raw, row(119).name.raw, last_page=1), row(100), clock.set(30), yesterday,
               *(row(store) for store in range(102, 119)), row(119, ends_page=True)]
    result, _ = collect(FakePagedSource(entries), kinds=("PriceFull",), clock=clock)
    assert result.pages[0]["taken_through"] == yesterday.name.raw
    assert result.listed == [stored_name(row(100))] and result.error == "stopped: under 90 s left"


def test_a_row_stopped_before_its_download_counts_as_taken():
    """Listed and recorded in `not_attempted`: the retry run finds it there, so the page is taken this far."""
    clock = Clock()
    entries = [report(1, row(100).name.raw, row(119).name.raw, last_page=1), row(100), clock.set(30), row(101),
               *(row(store) for store in range(102, 119)), row(119, ends_page=True)]
    result, _ = collect(FakePagedSource(entries), kinds=("PriceFull",), clock=clock)
    assert result.not_attempted == [stored_name(row(101))]
    assert result.pages[0]["taken_through"] == row(101).name.raw


def test_the_last_row_given_takes_the_page_to_its_end():
    """Review focus 2: the page's last rows did not parse (the adapter gives none of them), so the last row given is
    not the page's last; taking it takes the page to its last row, and the reading's end stays open."""
    entries = [report(1, row(100).name.raw, "PriceFull7290027600007-001-119", last_page=1),
               *(row(store) for store in range(100, 118)), row(118, ends_page=True)]
    result, _ = collect(FakePagedSource(entries), kinds=("PriceFull",))
    assert result.pages[0]["taken_through"] == "PriceFull7290027600007-001-119"
    assert result.error is None


def test_a_page_read_and_left_has_nothing_taken():
    """A step back: page 12 is read, its first name after the furthest an earlier run took, and left for page 11,
    whose rows are given. Page 12 keeps nothing taken."""
    left = report(12, row(140).name.raw, row(159).name.raw, last_page=21)
    page_11 = given(11, range(120, 140), last_page=21)
    result, _ = collect(FakePagedSource([left, *page_11]), kinds=("PriceFull",))
    assert result.pages == [taken(left, None), taken(page_11[0], page_11[0].last)]


@pytest.mark.parametrize("end, error, blocked", [
    pytest.param(ListingUnreadable("PriceFull page 2: no rows"), "listing unreadable: PriceFull page 2: no rows", None,
                 id="unreadable"),
    pytest.param(OutOfTime("before page 2 of the PriceFull listing"), "stopped: under 90 s left", None, id="time"),
    pytest.param(Blocked(429, "https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&page=2", "HTTP 429"),
                 None, "HTTP 429: https://prices.shufersal.co.il/FileObject/UpdateCategory", id="blocked"),
])
def test_page_records_are_in_the_manifest_whatever_the_run_ends_with(end, error, blocked):
    """The manifest is written whatever happens, so it holds the pages read before the run stopped."""
    page_1 = given(1, range(100, 120), last_page=2)
    result, store = collect(FakePagedSource([*page_1, end]), kinds=("PriceFull",))
    assert (result.error, result.blocked) == (error, blocked)
    assert manifest(store)["pages"] == [taken(page_1[0], page_1[0].last)]


def test_each_page_gets_a_log_line(caplog):
    """The page count is this run's page 1 of the kind (a list of one page has no pager: one page), `?` before it is
    read (a detour)."""
    def promo(store):
        return row(store).name.raw.replace("PriceFull", "PromoFull")

    reads = [report(5, row(180).name.raw, row(199).name.raw),
             report(1, row(100).name.raw, row(119).name.raw, last_page=21),
             report(7, row(220).name.raw, row(239).name.raw),
             report(3, promo(160), promo(179), kind="PromoFull", last_page=21, seconds=38.0),
             report(1, "Stores7290027600007-000-20261031-020", "Stores7290027600007-000-20261031-020", rows=1,
                    kind="Stores", seconds=0.6)]
    with caplog.at_level(logging.INFO, logger="collector.run"):
        collect(FakePagedSource(reads), kinds=("PriceFull", "PromoFull", "Stores"))
    assert [record.getMessage() for record in caplog.records if record.name == "collector.run"] == [
        "shufersal PriceFull page 5 of ?: 20 rows in 41.2 s",
        "shufersal PriceFull page 1 of 21: 20 rows in 41.2 s",
        "shufersal PriceFull page 7 of 21: 20 rows in 41.2 s",
        "shufersal PromoFull page 3 of ?: 20 rows in 38.0 s",
        "shufersal Stores page 1 of 1: 1 rows in 0.6 s",
    ]
    assert all(record.levelno == logging.INFO for record in caplog.records if record.name == "collector.run")


def test_the_real_shufersal_adapter_resumes_where_the_last_run_stopped():
    """2026-11-05's shape on a 4-page list: the morning's first run read pages 1 to 3 and stopped after page 3's 4th
    row, its files stored. The next run reads page 1, then page 3 again and on (a fresh pass would read page 2), and
    records each page it read taken to its last row."""
    from test_shufersal import connect, gz as files, listing_pages, listing_url, names, page, served, ticks
    http, portal = connect({listing_url(2, p): served(page(2, names(p), last=4)) for p in range(1, 5)}, files=files())

    def record(p, rows_taken=20):
        return taken(PageRead("PriceFull", p, 20, names(p)[0], names(p)[-1], 4, 30.0, True), names(p)[rows_taken - 1])

    took = [listed + ".gz" for listed in names(1) + names(2) + names(3)[:4]]
    first = RunResult(SLUG, "033000Z-main-a001", "main", DAY, ["PriceFull"], listed=took,
                      error="stopped: under 90 s left", pages=[record(1), record(2), record(3, rows_taken=4)])
    store = stored_day(DAY, [json.loads(manifest_bytes(first, CODE_SHA))], took)
    result, store = collect(ShufersalSource(timer=ticks(30.0)), store=store, kinds=("PriceFull",), http=http)
    assert listing_pages(portal) == [1, 3, 4]
    assert manifest(store)["pages"] == [record(1), record(3), record(4)]
    assert set(result.files) == {listed + ".gz" for listed in names(3)[4:] + names(4)}
    assert result.error is None and result.blocked is None


# ---- a listing page that timed out (q24) ----

def test_a_page_record_carries_its_tries():
    """Design, section 3: a page read on a later try is one page record, with the requests it took; a page read on its
    first try records 1."""
    reads = [report(1, row(100).name.raw, row(119).name.raw, last_page=2, tries=2),
             report(2, row(120).name.raw, row(139).name.raw, last_page=2)]
    result, store = collect(FakePagedSource(reads), kinds=("PriceFull",))
    assert manifest(store)["pages"][0]["tries"] == 2
    assert manifest(store)["pages"][1]["tries"] == 1
    assert result.error is None


PAGE_2_TIMED_OUT = PageTimeout("PriceFull", 2, 1, 60.5)
PAGE_2_ON_ITS_SECOND_TRY = [report(2, row(120).name.raw, row(139).name.raw, last_page=2, tries=2),
                            *(row(store) for store in range(120, 139)), row(139, ends_page=True)]


@pytest.mark.parametrize("then, error", [
    pytest.param(PAGE_2_ON_ITS_SECOND_TRY, None, id="read on the second try"),
    pytest.param([OutOfTime("before try 2 of page 2 of the PriceFull listing")], "stopped: under 90 s left",
                 id="time stop before the second try"),
    pytest.param([HttpError("HTTP 500 from https://prices.shufersal.co.il/FileObject/UpdateCategory")],
                 "listing failed: HTTP 500 from https://prices.shufersal.co.il/FileObject/UpdateCategory",
                 id="a 500 on the second try"),
])
def test_each_timed_out_try_is_in_the_manifest(then, error):
    """Review focus 3 and 4: a try that timed out is kept, in the order the listing reports it, whatever follows it: the
    page read on its next try, a time stop before that try (the run's error stays exactly the time stop's, which ruling
    R36 matches), or another failure raised at once."""
    entries = [*given(1, range(100, 120), last_page=2), PAGE_2_TIMED_OUT, *then]
    result, store = collect(FakePagedSource(entries), kinds=("PriceFull",))
    assert result.error == error
    expected = [{"kind": "PriceFull", "page": 2, "attempt": 1, "seconds": 60.5}]
    assert manifest(store)["timeouts"] == expected
    assert result.timeouts == expected


def test_a_block_on_a_later_try_latches_and_keeps_the_timed_out_try():
    """Review focus 4: page 2's first try timed out and its second was refused. The block latches the chain as a block
    anywhere in the listing does, and the try that timed out before it stays in the manifest."""
    refusal = Blocked(403, "https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&storeId=0&page=2",
                      "HTTP 403")
    entries = [*given(1, range(100, 120), last_page=2), PAGE_2_TIMED_OUT, refusal]
    result, store = collect(FakePagedSource(entries), kinds=("PriceFull",))
    reason = "HTTP 403: https://prices.shufersal.co.il/FileObject/UpdateCategory"
    assert (result.blocked, result.error) == (reason, None)
    assert store.read_state(SLUG) == latch(reason)
    assert manifest(store)["blocked"] == reason
    assert manifest(store)["timeouts"] == [{"kind": "PriceFull", "page": 2, "attempt": 1, "seconds": 60.5}]


def test_no_timeouts_on_a_run_without_one():
    """An empty list, on a paged run with none and on a source that does not page."""
    _, paged = collect(FakePagedSource(given(1, range(100, 120), last_page=1)), kinds=("PriceFull",))
    _, plain = collect(FakeSource([item(PRICE)]))
    assert manifest(paged)["timeouts"] == []
    assert manifest(plain)["timeouts"] == []


def test_a_page_read_on_a_later_try_says_so_in_its_log_line(caplog):
    """Design, section 3: the page's INFO line ends with the try that read it, when that is not the first."""
    reads = [report(1, row(100).name.raw, row(119).name.raw, last_page=21),
             report(7, row(220).name.raw, row(239).name.raw, tries=2),
             report(8, row(240).name.raw, row(259).name.raw, tries=3)]
    with caplog.at_level(logging.INFO, logger="collector.run"):
        collect(FakePagedSource(reads), kinds=("PriceFull",))
    assert [record.getMessage() for record in caplog.records if record.name == "collector.run"] == [
        "shufersal PriceFull page 1 of 21: 20 rows in 41.2 s",
        "shufersal PriceFull page 7 of 21: 20 rows in 41.2 s (try 2)",
        "shufersal PriceFull page 8 of 21: 20 rows in 41.2 s (try 3)",
    ]


def test_the_real_shufersal_adapter_records_the_tries():
    """A 3-page list: page 2 times out once and is read on its second try, page 3 times out on every try. The run ends
    with the adapter's error, pages 1 and 2 recorded with their tries and their files stored, and each of the four
    timed-out tries listed, ten seconds' pause before each later try."""
    from test_shufersal import LISTING, connect, gz as files, listing_url, names, page, served, ticks, timed_out
    http, _ = connect({listing_url(2, 1): served(page(2, names(1), last=3)),
                       listing_url(2, 2): [timed_out, served(page(2, names(2), last=3))],
                       listing_url(2, 3): [timed_out]}, files=files())
    sleeps = []
    result, store = collect(ShufersalSource(timer=ticks(30.0), sleep=sleeps.append), kinds=("PriceFull",), http=http)
    assert result.error == f"listing failed: PriceFull page 3 timed out on 3 tries: GET {LISTING} failed: The read operation timed out"
    assert [(record["page"], record["tries"]) for record in manifest(store)["pages"]] == [(1, 1), (2, 2)]
    tries = [(timeout["page"], timeout["attempt"]) for timeout in manifest(store)["timeouts"]]
    assert tries == [(2, 1), (3, 1), (3, 2), (3, 3)]
    assert set(stored_bodies(store)) == {listed + ".gz" for listed in names(1) + names(2)}
    assert sleeps == [10.0] * 3
    assert result.blocked is None

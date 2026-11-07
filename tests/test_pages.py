"""Ruling R37: whether the pages the day's runs read of a kind join up into one full reading, what of the list no run
read, and where the next run starts reading it (collector.pages).

Manifests are built as the run loop writes them (manifest_bytes over a RunResult), each page record as
`asdict(PageRead)` with `taken_through`. The list is Shufersal's PriceFull list on 2026-11-05's scale: 21 pages of 20
rows, page p holding rows 20(p-1)+1 to 20p, named in file-name order. A is that morning's first run (pages 1 to 11,
then page 12's first row, stopped on time before its download); B the second, resumed (page 1, then pages 12 to 21).
A run's `listed` holds the stored names (`<name>.gz`, ruling R16) of the rows it took. The last section (q23, ruling
R39) builds poll runs of the update kinds the same way, each with the time its listing was read.
"""
import json
from dataclasses import asdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from collector.names import KINDS
from collector.pages import has_pages, pass_start, passes, read_in_full, start_for, unread
from collector.run import RunResult, manifest_bytes
from collector.sources import PageRead, PageTimeout, Start

DAY = date(2026, 11, 5)
CODE_SHA = "0123456789abcdef0123456789abcdef01234567"
STOPPED = "stopped: under 90 s left"
TIMED_OUT = "listing failed: <urlopen error timed out>"
BLOCKED = "HTTP 403: https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&page=13"


def name(i, kind="PriceFull"):
    """The i-th name on the list."""
    return f"{kind}7290027600007-001-{i:03d}-20261105-030000"


def rec(page, taken=20, *, last_page=..., in_order=True, kind="PriceFull", rows=20):
    """The record of page `page`, holding `rows` rows from row 20(page-1)+1, taken through its `taken`-th row (None:
    nothing taken). Page 1's pager names page 21 unless `last_page` says otherwise; other pages' name none."""
    if last_page is ...:
        last_page = 21 if page == 1 else None
    before = 20 * (page - 1)
    read = PageRead(kind, page, rows, name(before + 1, kind), name(before + rows, kind), last_page, 30.0, in_order)
    return asdict(read) | {"taken_through": None if taken is None else name(before + taken, kind)}


def run(run_id, *records, kinds=("PriceFull",), error=None, blocked=None, listed=()):
    """A manifest as stored, its mode read from the run id."""
    result = RunResult(chain="shufersal", run_id=run_id, mode=run_id.split("-")[1], day=DAY, kinds=list(kinds),
                       listed=list(listed), error=error, blocked=blocked, pages=list(records))
    return json.loads(manifest_bytes(result, CODE_SHA))


def pages(first, last, **kwargs):
    """Records of pages `first` to `last`, each taken to its last row."""
    return [rec(page, **kwargs) for page in range(first, last + 1)]


def gz(rows, kind="PriceFull"):
    """The stored names (`<name>.gz`) of the rows, in their order."""
    return [name(i, kind) + ".gz" for i in rows]


def late(i):
    """A file of the i-th name's store published at 06:00, after the morning's first run read that part of the list:
    it sorts just after the i-th name."""
    return name(i).replace("-030000", "-060000")


A_ID, B_ID = "044522Z-main-a001", "050002Z-main-a002"
A = run(A_ID, *pages(1, 11), rec(12, taken=1), error=STOPPED, listed=gz(range(1, 222)))
B = run(B_ID, rec(1), *pages(12, 21), listed=gz(range(1, 21)) + gz(range(221, 421)))
A_STORED = set(gz(range(1, 221)))  # A stopped before downloading page 12's first file
ALL_STORED = set(gz(range(1, 421)))


def test_one_run_from_page_1_to_the_last_reads_in_full():
    assert read_in_full([run(A_ID, *pages(1, 21))], "PriceFull") == [A_ID]


def test_a_run_that_stopped_short_does_not_read_in_full():
    assert read_in_full([A], "PriceFull") is None


def test_two_runs_join_when_the_second_starts_where_the_first_stopped():
    """2026-11-05's shape: B reads page 12 again, so its first name is the last A took."""
    assert read_in_full([A, B], "PriceFull") == [A_ID, B_ID]


def test_a_run_that_adds_nothing_does_not_contribute():
    """Among blocks that start together, the one reaching furthest is taken first, so a run whose pages others
    covered is never named, wherever it stands in the day."""
    retry = run("074536Z-retry-2933", rec(1), error=TIMED_OUT)
    assert read_in_full([A, B, retry], "PriceFull") == [A_ID, B_ID]
    early = run("043000Z-main-a000", rec(1), error=TIMED_OUT)
    assert read_in_full([early, A, B], "PriceFull") == [A_ID, B_ID]


def test_a_gap_between_runs_is_not_read_in_full():
    assert read_in_full([A, run(B_ID, rec(1), *pages(13, 21))], "PriceFull") is None


def test_the_last_page_counts_only_to_the_row_taken():
    """Design, Call 6: the rows after the one taken were never listed."""
    assert read_in_full([A, run(B_ID, rec(1), *pages(12, 20), rec(21, taken=5))], "PriceFull") is None


def test_the_end_is_the_runs_own_pager_reading():
    """B's page 1 names 22 pages: its page 21 is not the last, whatever page it read last. A run that did not read
    page 1 has no pager reading of its own, so no page of it is the last."""
    assert read_in_full([A, run(B_ID, rec(1, last_page=22), *pages(12, 21))], "PriceFull") is None
    assert read_in_full([A, run(B_ID, *pages(12, 21))], "PriceFull") is None


def test_an_out_of_order_page_turns_joining_off():
    out_of_order = run(A_ID, *(rec(page, in_order=page != 7) for page in range(1, 12)), rec(12, taken=1), error=STOPPED)
    assert read_in_full([out_of_order, B], "PriceFull") is None
    whole = run("081551Z-retry-9283", *pages(1, 21))
    assert read_in_full([out_of_order, B, whole], "PriceFull") == ["081551Z-retry-9283"]
    blocked = run("074536Z-retry-2933", rec(1), rec(2, in_order=False), blocked=BLOCKED)
    assert read_in_full([A, B, blocked], "PriceFull") is None


def test_with_joining_off_a_detour_before_a_whole_pass_still_counts():
    """A run that read every page in one go counts, though a one-page detour came first."""
    out_of_order = run(A_ID, *(rec(page, in_order=page != 7) for page in range(1, 12)), rec(12, taken=1), error=STOPPED)
    whole = run("081551Z-retry-9283", rec(5), *pages(1, 21))
    assert read_in_full([out_of_order, whole], "PriceFull") == ["081551Z-retry-9283"]


def test_a_blocked_run_does_not_count():
    assert read_in_full([A, run(B_ID, rec(1), *pages(12, 21), blocked=BLOCKED)], "PriceFull") is None


def test_a_run_with_an_error_counts_for_the_pages_it_read():
    assert read_in_full([A, run(B_ID, rec(1), *pages(12, 21), error=TIMED_OUT)], "PriceFull") == [A_ID, B_ID]


def test_manifests_without_pages_and_no_error_read_in_full():
    """Other chains' manifests, and Shufersal's before this change, read as ruling R36 reads them; on deploy day they
    stand beside the new records."""
    absent = run(A_ID)
    del absent["pages"]
    empty = run(A_ID)
    for legacy in (absent, empty):
        assert read_in_full([legacy], "PriceFull") == [A_ID]
        assert read_in_full([legacy | {"error": STOPPED}], "PriceFull") is None
    early = run("043000Z-main-a000")
    assert read_in_full([early, A], "PriceFull") == ["043000Z-main-a000"]
    assert read_in_full([early, A, B], "PriceFull") == ["043000Z-main-a000", A_ID, B_ID]


def test_other_kinds_pages_do_not_count():
    promo = run(A_ID, *pages(1, 21, kind="PromoFull"), kinds=("PriceFull", "PromoFull"))
    assert read_in_full([promo], "PriceFull") is None
    assert read_in_full([promo], "PromoFull") == [A_ID]


def test_a_page_with_nothing_taken_is_left_out():
    """B stepped back from page 14 to page 12: the pages it stepped over gave no rows until it read them again."""
    stepped = run(B_ID, rec(1), rec(14, taken=None), rec(13, taken=None), *pages(12, 21))
    assert read_in_full([A, stepped], "PriceFull") == [A_ID, B_ID]


def test_a_page_taken_part_way_ends_its_block():
    """The rows after the one taken were never listed, wherever in the run the page stands: the next page starts a
    block of its own, though its number is the next one."""
    part_way = run(A_ID, *pages(1, 10), rec(11, taken=3), *pages(12, 21))
    assert read_in_full([part_way], "PriceFull") is None
    assert unread([part_way], "PriceFull") == "page 11 read in part"


def test_a_detour_page_alone_is_a_block_of_its_own():
    """A detour to page 25 after the list shrank: the portal serves the last page's rows under that number. The page
    is not the run's own last page, so it never opens the reading's end, even where it covers rows another run did
    not take."""
    detour = run("074536Z-retry-2933", rec(21) | {"page": 25}, rec(1), error=STOPPED)
    assert read_in_full([detour], "PriceFull") is None
    short = run(B_ID, *pages(1, 20), rec(21, taken=5), error=STOPPED)
    assert read_in_full([short, detour], "PriceFull") is None


def test_a_one_page_list_with_no_pager_reads_in_full():
    stores = run("043000Z-main-a000", rec(1, taken=1, last_page=None, rows=1, kind="Stores"), kinds=("Stores",))
    assert read_in_full([stores], "Stores") == ["043000Z-main-a000"]


def test_unread_names_the_pages_never_read():
    second = run(B_ID, rec(1), *pages(12, 16), error=STOPPED)
    assert unread([A, second], "PriceFull") == "pages 17 to 21 never read"


def test_unread_names_a_page_read_in_part():
    second = run(B_ID, rec(1), *pages(12, 15), rec(16, taken=3), error=STOPPED)
    assert unread([A, second], "PriceFull") == "pages 17 to 21 never read, page 16 read in part"


def test_unread_when_every_page_was_read_but_the_readings_do_not_join():
    """The list shifted between the runs: B's page 12 starts after the last name A took."""
    shifted = run(B_ID, rec(1), rec(12) | {"first": name(225)}, *pages(13, 21))
    assert read_in_full([A, shifted], "PriceFull") is None
    assert unread([A, shifted], "PriceFull") == "every page was read, but the pages read do not join up"


def test_unread_names_the_out_of_order_page():
    out_of_order = run(A_ID, *(rec(page, in_order=page not in (7, 9)) for page in range(1, 12)), rec(12, taken=1),
                       error=STOPPED)
    assert unread([out_of_order, B], "PriceFull") == (
        "every page was read, but the pages read do not join up (page 7 of run 044522Z-main-a001 was out of order, so "
        "only a run that read every page in one go counts)")


def test_unread_without_page_1():
    text = "page 1 never read, so the last page is not known"
    assert unread([run(B_ID, *pages(12, 21), error=STOPPED)], "PriceFull") == text
    assert unread([run(B_ID, *pages(1, 21), blocked=BLOCKED)], "PriceFull") == text


def test_unread_page_ranges():
    gaps = run(A_ID, *pages(1, 2), *pages(4, 16), error=STOPPED)
    assert unread([gaps], "PriceFull") == "pages 3, 17 to 21 never read"
    assert unread([run(A_ID, *pages(1, 20), error=STOPPED)], "PriceFull") == "page 21 never read"


def test_unread_reads_to_the_largest_last_page_any_pager_named():
    assert unread([A, run(B_ID, rec(1, last_page=22), *pages(12, 21))], "PriceFull") == "page 22 never read"


def test_has_pages():
    assert has_pages([A], "PriceFull")
    assert has_pages([run(B_ID, rec(1), blocked=BLOCKED)], "PriceFull")
    absent = run(A_ID)
    del absent["pages"]
    assert not has_pages([absent, run(B_ID)], "PriceFull")
    assert not has_pages([A], "PromoFull")


def test_no_earlier_run_starts_at_page_1():
    assert start_for([], "PriceFull", set()) == Start()


def test_earlier_runs_without_pages_that_ended_with_an_error_start_at_page_1():
    """Manifests from before page records: one that ended with an error says nothing of how far it read, and a file
    it did not store is on no page it recorded."""
    absent = run("043000Z-main-a000", error=TIMED_OUT, listed=gz(range(1, 41)))
    del absent["pages"]
    empty = run(A_ID, error=STOPPED, listed=gz(range(1, 41)))
    assert start_for([absent, empty], "PriceFull", set(gz(range(1, 21)))) == Start()


def test_an_out_of_order_page_that_day_starts_at_page_1():
    """Out of order, the day's records of the kind place no name: no resume, and no detour either."""
    stored = A_STORED - set(gz([85]))
    out_of_order = run(A_ID, *(rec(page, in_order=page != 7) for page in range(1, 12)), rec(12, taken=1),
                       error=STOPPED, listed=gz(range(1, 222)))
    assert start_for([out_of_order], "PriceFull", stored) == Start()
    blocked = run(B_ID, rec(1), rec(12, in_order=False), blocked=BLOCKED)
    assert start_for([A, blocked], "PriceFull", stored) == Start()


def test_the_2026_11_05_shape_resumes_at_page_12():
    """The resume reads page 12 again, so the file A stopped before is no detour."""
    assert start_for([A], "PriceFull", A_STORED) == Start(page=12, furthest=name(221))


def test_the_furthest_name_across_runs():
    """The furthest name any run took, wherever the run stands in the day, with its page; when two records hold it
    (the list grew by a page between the runs, moving it from page 12 to page 13), the larger page."""
    further = run(B_ID, rec(1), *pages(12, 15), rec(16, taken=3), error=STOPPED)
    retry = run("074536Z-retry-2933", rec(1), error=TIMED_OUT)
    assert start_for([A, further, retry], "PriceFull", ALL_STORED) == Start(page=16, furthest=name(303))
    to_page_12 = run(A_ID, *pages(1, 12), error=STOPPED)
    grown = run(B_ID, rec(1), rec(11) | {"page": 12}, rec(12) | {"page": 13}, error=STOPPED)
    assert start_for([to_page_12, grown], "PriceFull", set()) == Start(page=13, furthest=name(240))


def test_a_blocked_run_is_not_resumed_from():
    """The check leaves a blocked run out, so the start does too: this one took page 12 to its end."""
    blocked = run(B_ID, rec(1), rec(12), blocked=BLOCKED)
    assert start_for([A, blocked], "PriceFull", A_STORED) == Start(page=12, furthest=name(221))


def test_read_in_full_starts_a_fresh_pass():
    assert start_for([A, B], "PriceFull", ALL_STORED) == Start()


def test_a_failed_file_earlier_on_the_list_gets_a_detour():
    stored = A_STORED - set(gz([85]))
    assert start_for([A], "PriceFull", stored) == Start(page=12, furthest=name(221), detours=(5,))


def test_a_fresh_pass_detours_to_a_failed_files_page_first():
    assert start_for([A, B], "PriceFull", ALL_STORED - set(gz([85]))) == Start(detours=(5,))


def test_no_detour_for_page_1_or_the_resume_page_or_after():
    """Page 1 is read first anyway, and a resume reads on from the resume page (A's page 12 holds the file A stopped
    before). A failed name sits on a page after the resume page only when the list moved between runs: here it grew
    by four pages, and a later run, resumed at page 12, failed on page 15 a file published since A read that part."""
    grown = run("074536Z-retry-2933", rec(1), *(rec(page - 4) | {"page": page} for page in range(12, 16)),
                error=TIMED_OUT,
                listed=gz(range(1, 21)) + gz(range(141, 206)) + [late(205) + ".gz"] + gz(range(206, 221)))
    stored = A_STORED - set(gz([3]))
    assert start_for([A, grown], "PriceFull", stored) == Start(page=12, furthest=name(221))


def test_a_failed_name_is_found_without_its_gz():
    """The stored name ends in `.gz` and the page's names do not: the last name taken from page 5 is on page 5."""
    stored = A_STORED - set(gz([100]))
    assert start_for([A], "PriceFull", stored) == Start(page=12, furthest=name(221), detours=(5,))


def test_detours_are_sorted_and_each_once():
    """A retry's fresh pass that began with a detour to page 7 listed that page's names first. The file there failed
    again, and three records of page 7 hold it (the first run's, the retry's detour and its pass); a file published on
    page 5 since the first run read it failed too. Found in the order 7, 7, 7, 5, the detours are 5 and 7."""
    first = run(A_ID, *pages(1, 21), listed=gz(range(1, 421)))
    retry = run("074536Z-retry-2933", rec(7), *pages(1, 9), rec(10, taken=4), error=STOPPED,
                listed=gz(range(121, 141)) + gz(range(1, 86)) + [late(85) + ".gz"] + gz(range(86, 121))
                + gz(range(141, 185)))
    assert start_for([first, retry], "PriceFull", ALL_STORED - set(gz([130]))) == Start(detours=(5, 7))


def test_other_kinds_runs_are_ignored():
    """Each kind starts from its own runs and records: a run of another kind with no page records and no error, and
    another kind's pages in a run that covers both, change nothing for PriceFull."""
    promo_only = run("043000Z-main-a000", kinds=("PromoFull",))
    both = run(B_ID, *pages(1, 21, kind="PromoFull"), kinds=("PriceFull", "PromoFull"), error=STOPPED,
               listed=gz(range(1, 421), "PromoFull"))
    day = [promo_only, A, both]
    stored = A_STORED | (set(gz(range(1, 421), "PromoFull")) - set(gz([45], "PromoFull")))
    assert start_for(day, "PriceFull", stored) == Start(page=12, furthest=name(221))
    assert start_for(day, "PromoFull", stored) == Start(detours=(3,))


def test_a_mix_of_old_and_new_manifests_uses_the_records_there_are():
    """Deploy day: the morning's first run wrote no page records. Ended with an error, it leaves A's records to set the
    start; ended clean, it read the kind in full as R36 reads it, and the next run makes a fresh pass."""
    old = run("043000Z-main-a000", error=TIMED_OUT, listed=gz(range(1, 41)))
    del old["pages"]
    assert start_for([old, A], "PriceFull", A_STORED) == Start(page=12, furthest=name(221))
    clean = run("043000Z-main-a000", listed=gz(range(1, 421)))
    del clean["pages"]
    assert start_for([clean, A], "PriceFull", ALL_STORED) == Start()


def test_a_resume_at_page_1_is_a_fresh_pass():
    """A run that read page 1 and then timed out took its furthest name from page 1."""
    retry = run("074536Z-retry-2933", rec(1), error=TIMED_OUT, listed=gz(range(1, 21)))
    assert start_for([retry], "PriceFull", set(gz(range(1, 21)))) == Start()


def test_a_resume_at_page_1_keeps_its_detours():
    """A fresh pass carries every failed file's detour, wherever it comes from. Here the list shrank: an earlier run
    read pages 1 to 5 and stopped on page 5 with a file there failed; a later run's page 1 held rows 101 to 120, so its
    page 1 took the furthest name."""
    earlier = run(A_ID, *pages(1, 4), rec(5, taken=10), error=STOPPED, listed=gz(range(1, 91)))
    shrunk = run("074536Z-retry-2933", rec(6, last_page=16) | {"page": 1}, error=TIMED_OUT, listed=gz(range(101, 121)))
    stored = set(gz(range(1, 121))) - set(gz([85]))
    assert start_for([earlier, shrunk], "PriceFull", stored) == Start(detours=(5,))


def test_a_gap_between_blocks_still_resumes_at_the_furthest_page():
    """A run that left page 11 part-way and read on is not read in full (the rest of page 11 was never listed), yet
    the next run resumes at the furthest name taken, not where the joined reading ends."""
    gap = run(A_ID, *pages(1, 10), rec(11, taken=3), *pages(12, 15), error=STOPPED)
    assert read_in_full([gap], "PriceFull") is None
    assert start_for([gap], "PriceFull", set()) == Start(page=15, furthest=name(300))


# ---- a page read on a later try (q24) ----

def tried(manifest, tries):
    """`manifest` as the run loop writes it when every page took `tries` requests: each page record's `tries` set, and
    `timeouts` holding each page's tries before the one that read it (attempts 1 to `tries - 1`, 60.5 s each). With
    None, as a manifest written before tries were recorded: no `tries` on any record and no `timeouts` key."""
    records = manifest.get("pages", [])
    if tries is None:
        old = {key: value for key, value in manifest.items() if key != "timeouts"}
        return old | {"pages": [{key: value for key, value in record.items() if key != "tries"} for record in records]}
    timeouts = [asdict(PageTimeout(record["kind"], record["page"], attempt, 60.5))
                for record in records for attempt in range(1, tries)]
    return manifest | {"pages": [record | {"tries": tries} for record in records], "timeouts": timeouts}


@pytest.mark.parametrize("tries", [1, 3, None])
def test_tries_do_not_change_the_reading(tries):
    """Design, section 3: the reading never reads `tries` or `timeouts`, so 2026-11-05's shape joins, stops short,
    resumes and names what was never read alike with every page read on its first try, on its third, and in manifests
    written before tries were recorded."""
    a, b = tried(A, tries), tried(B, tries)
    assert {record.get("tries") for record in a["pages"] + b["pages"]} == {tries}
    assert ("timeouts" in a) == (tries is not None)
    assert read_in_full([a, b], "PriceFull") == [A_ID, B_ID]
    assert read_in_full([a], "PriceFull") is None
    assert start_for([a], "PriceFull", A_STORED) == Start(page=12, furthest=name(221))
    assert unread([a], "PriceFull") == "pages 13 to 21 never read, page 12 read in part"
    assert has_pages([a], "PriceFull")


# ---- update kinds: passes (q23, ruling R39) ----
#
# Poll runs of Shufersal's Promo list, on the scale above. P1 and P2 are the 10:30 pass in 2026-11-05's shape (P1 as
# A, P2 as B); P3 is the 15:10 pass's first run, stopped as P1 stopped. Q1 to Q3 are a quick chain's polls of both
# update kinds, which record no pages.

def at(clock):
    """The Israel time `clock` ("HH:MM") on DAY, as the run loop writes `listing_read_at`: aware, in UTC."""
    moment = datetime.combine(DAY, time.fromisoformat(clock), ZoneInfo("Asia/Jerusalem"))
    return moment.astimezone(timezone.utc).isoformat()


def poll(run_id, clock, *records, kinds=("Promo",), error=None, blocked=None, listed=(), read=True):
    """A poll run's manifest as stored, its listing read at `clock` (never read, with `read` false)."""
    manifest = run(run_id, *records, kinds=kinds, error=error, blocked=blocked, listed=listed)
    return manifest | {"mode": "poll", "listing_read_at": at(clock) if read else None}


def outline(cut):
    """Each pass as (its runs' ids, read_by, out_of_order, open)."""
    return [([manifest["run_id"] for manifest in one.runs], one.read_by, one.out_of_order, one.open) for one in cut]


P1_ID, P2_ID, P3_ID = "083000Z-poll-c001", "084500Z-poll-c002", "131000Z-poll-c003"
P1 = poll(P1_ID, "10:30", *pages(1, 11, kind="Promo"), rec(12, taken=1, kind="Promo"), error=STOPPED,
          listed=gz(range(1, 222), "Promo"))
P2 = poll(P2_ID, "10:45", rec(1, kind="Promo"), *pages(12, 21, kind="Promo"),
          listed=gz(range(1, 21), "Promo") + gz(range(221, 421), "Promo"))
P3 = poll(P3_ID, "15:10", *pages(1, 11, kind="Promo"), rec(12, taken=1, kind="Promo"), error=STOPPED,
          listed=gz(range(1, 222), "Promo"))
PROMO_STORED = set(gz(range(1, 421), "Promo"))

HTTP_500 = "listing failed: HTTP 500 from https://url.publishedprices.co.il/file/json/dir"
Q1_ID, Q2_ID, Q3_ID = "102000Z-poll-q001", "122000Z-poll-q002", "142000Z-poll-q003"
Q1 = poll(Q1_ID, "12:20", kinds=("Price", "Promo"), error=HTTP_500)
Q2 = poll(Q2_ID, "14:20", kinds=("Price", "Promo"))
Q3 = poll(Q3_ID, "16:20", kinds=("Price", "Promo"), error=HTTP_500)


def test_runs_that_join_up_make_one_pass_and_the_next_run_opens_another():
    """P2 completes the 10:30 pass, so P3 begins the next one, open."""
    assert outline(passes([P1, P2, P3], "Promo")) == [([P1_ID, P2_ID], [P1_ID, P2_ID], False, False),
                                                      ([P3_ID], None, False, True)]


def test_the_second_run_of_a_later_pass_resumes_it():
    """The 15:25 run resumes the 15:10 pass where P3 stopped. R37 alone reads the day as one reading: the 10:30 pass
    read the list in full, so it would start that run at page 1."""
    assert pass_start([P1, P2, P3], "Promo", PROMO_STORED) == Start(page=12, furthest=name(221, "Promo"))
    assert start_for([P1, P2, P3], "Promo", PROMO_STORED) == Start()


def test_after_a_pass_read_in_full_the_next_run_starts_a_fresh_pass():
    """With no detour, though a file on page 5 of the complete pass failed: the new pass reads page 5 in its turn."""
    assert pass_start([P1, P2], "Promo", PROMO_STORED) == Start()
    assert pass_start([], "Promo", set()) == Start()
    assert pass_start([P1, P2], "Promo", PROMO_STORED - set(gz([85], "Promo"))) == Start()


def test_passes_follow_when_the_listing_was_read_not_the_run_id():
    """00:20 Israel time on DAY is 22:20Z the day before, so that run's id sorts after every daytime run's."""
    early_id, late_id = "222000Z-poll-c000", "083000Z-poll-c001"
    early = poll(early_id, "00:20", *pages(1, 21, kind="Promo"))
    late = poll(late_id, "10:30", *pages(1, 10, kind="Promo"), error=STOPPED)
    assert outline(passes([late, early], "Promo")) == [([early_id], [early_id], False, False),
                                                       ([late_id], None, False, True)]
    assert pass_start([late, early], "Promo", PROMO_STORED) == Start(page=10, furthest=name(200, "Promo"))


def test_a_page_out_of_order_ends_its_pass_and_not_the_day():
    """D1's page 5 is out of order: its pass ends with it, unread, and D2 begins a fresh one, which D3 completes. R37
    over the whole day would keep joining off for the rest of it."""
    d1_id, d2_id, d3_id = "083000Z-poll-d001", "084500Z-poll-d002", "131000Z-poll-d003"
    d1 = poll(d1_id, "10:30", *(rec(page, in_order=page != 5, kind="Promo") for page in range(1, 12)),
              rec(12, taken=1, kind="Promo"), error=STOPPED)
    d2 = poll(d2_id, "10:45", *pages(1, 11, kind="Promo"), rec(12, taken=1, kind="Promo"), error=STOPPED)
    d3 = poll(d3_id, "15:10", rec(1, kind="Promo"), *pages(12, 21, kind="Promo"))
    assert outline(passes([d1, d2], "Promo")) == [([d1_id], None, True, False), ([d2_id], None, False, True)]
    assert pass_start([d1, d2], "Promo", PROMO_STORED) == Start(page=12, furthest=name(221, "Promo"))
    assert passes([d1, d2, d3], "Promo")[-1].read_by == [d2_id, d3_id]
    assert read_in_full([d1, d2, d3], "Promo") is None


def test_a_blocked_run_and_a_run_that_never_read_the_listing_are_left_out():
    """R37 leaves a blocked run out; a run stopped before its listing read nothing and has no time to be placed by."""
    blocked = poll("084000Z-poll-c005", "10:40", rec(1, kind="Promo"), blocked=BLOCKED)
    never_read = poll("084200Z-poll-c006", "10:42", error=STOPPED, read=False)
    assert passes([P1, blocked, never_read, P2], "Promo") == passes([P1, P2], "Promo")


def test_a_run_that_read_no_page_leaves_its_pass_open():
    """Review focus 3: page 1 failed on every try, so the run took nothing; the pass stays open, the next run still
    resumes it, and a run after that can complete it."""
    failed_id = "084500Z-poll-c009"
    failed = poll(failed_id, "10:45", error="listing failed: Promo page 1 timed out on 3 tries: GET "
                  "https://prices.shufersal.co.il/FileObject/UpdateCategory failed: timed out")
    assert outline(passes([P1, failed], "Promo")) == [([P1_ID, failed_id], None, False, True)]
    assert pass_start([P1, failed], "Promo", PROMO_STORED) == Start(page=12, furthest=name(221, "Promo"))
    later = P2 | {"listing_read_at": at("11:00")}
    assert passes([P1, failed, later], "Promo")[0].read_by == [P1_ID, P2_ID]


def test_runs_without_page_records_each_read_in_full_when_they_end_clean():
    """The quick chains: a poll that records no pages and ended with no error read the kind in full on its own, as
    R36 reads it, and ends its pass; one whose listing failed does not."""
    assert [([manifest["run_id"] for manifest in one.runs], one.read_by) for one in passes([Q1, Q2, Q3], "Price")] == [
        ([Q1_ID, Q2_ID], [Q2_ID]), ([Q3_ID], None)]


def test_only_poll_runs_of_the_kind_make_its_passes():
    """A quick chain's clean main run of every kind read its listing, so only its mode keeps it out; a Shufersal poll
    of Price, with its pages, changes nothing in Promo's passes."""
    main = run("043300Z-main-d001", kinds=KINDS) | {"listing_read_at": at("06:33")}
    assert outline(passes([main, Q1], "Price")) == [([Q1_ID], None, False, True)]
    price = poll("090000Z-poll-c004", "11:00", *pages(1, 21, kind="Price"), kinds=("Price",))
    assert passes([P1, P2, price], "Promo") == passes([P1, P2], "Promo")


def test_an_open_pass_detours_to_its_failed_files_pages():
    """P3 listed the 85th name, on page 5, and its file is not stored."""
    stored = PROMO_STORED - set(gz([85], "Promo"))
    assert pass_start([P1, P2, P3], "Promo", stored) == Start(page=12, furthest=name(221, "Promo"), detours=(5,))


def test_full_kinds_read_as_before_with_polls_beside():
    """Design, section 8: R37's functions filter by kind, so the morning reads PriceFull as before with the day's
    Promo polls beside it: after a full reading, a fresh pass with detours, as today."""
    assert read_in_full([A, B, P1, P2, P3], "PriceFull") == [A_ID, B_ID]
    assert start_for([A, B, P1, P2, P3], "PriceFull", ALL_STORED - set(gz([85]))) == Start(detours=(5,))
    assert start_for([A, P1, P2, P3], "PriceFull", A_STORED) == start_for([A], "PriceFull", A_STORED)
    assert unread([A, P3], "PriceFull") == unread([A], "PriceFull")
    assert has_pages([P1], "PriceFull") is False

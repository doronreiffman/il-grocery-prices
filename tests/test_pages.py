"""Ruling R37: whether the pages the day's runs read of a kind join up into one full reading, and what of the list no
run read (collector.pages).

Manifests are built as the run loop writes them (manifest_bytes over a RunResult), each page record as
`asdict(PageRead)` with `taken_through`. The list is Shufersal's PriceFull list on 2026-11-05's scale: 21 pages of 20
rows, page p holding rows 20(p-1)+1 to 20p, named in file-name order. A is that morning's first run (pages 1 to 11,
then page 12's first row, stopped on time); B the second, resumed (page 1, then pages 12 to 21).
"""
import json
from dataclasses import asdict
from datetime import date

from collector.pages import has_pages, read_in_full, unread
from collector.run import RunResult, manifest_bytes
from collector.sources import PageRead

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


A_ID, B_ID = "044522Z-main-a001", "050002Z-main-a002"
A = run(A_ID, *pages(1, 11), rec(12, taken=1), error=STOPPED)
B = run(B_ID, rec(1), *pages(12, 21))


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

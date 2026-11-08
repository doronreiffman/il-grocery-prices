"""2026-11-05's Shufersal morning, replayed through the real adapter, run loop and check, on the resume
(docs/shufersal-resume.md, "Why" and "2026-11-05 replayed").

The morning is synthetic, shaped like the real one: each full kind listed on 21 pages of 20 rows, read at the pace the
design works out from that morning's run times (40 to 45 s a page, 1 to 2 s a download), two main runs of each kind,
then one retry each whose second page passes the 60 s socket timeout on every try, 10 s apart (a slow spell: the
adapter asks a timed-out page again, docs/shufersal-page-retry.md, "Testing"). Every count asserted here is what that
pace and the 90 s rule give: expected, not measured.

2026-11-06's 05:00Z PriceFull run is replayed the same way (docs/shufersal-page-retry.md, "2026-11-06 replayed"): 22
pages, page 7 timing out once and then served, at the pace that design works out; its counts are expected too.

A day of Shufersal `Promo` polls on 2026-11-06 is replayed too (docs/update-files.md, section 3, "What a pass of two
runs gives"; ruling R39): 22 pages, four poll runs making two passes of two runs, and, apart, a store republishing the
resume page's first row between a pass's two runs. The day is synthetic and its counts are expected too.
"""
import dataclasses
import itertools
from datetime import date, datetime, timezone

from collector.chains import CHAINS
from collector.check import Alert, check_day, judge_update_day
from collector.run import OUT_OF_TIME, collect_chain
from collector.sources.shufersal import CATEGORY, ShufersalSource
from collector.store import MemoryStore
from test_run import CODE_SHA, Clock
from test_shufersal import LISTING, connect, gz, listing_pages, listing_url, page, served

DAY = date(2026, 11, 5)
CHAIN = CHAINS["shufersal"]
PAGES = 21
ROWS = 20  # a page
PACE = {"PriceFull": (42.0, 1.5), "PromoFull": (45.0, 2.0)}  # seconds a listing page, seconds a download
TIMED_OUT = {"PriceFull": f"listing failed: PriceFull page 2 timed out on 3 tries: GET {LISTING} failed: timed out",
             "PromoFull": f"listing failed: PromoFull page 19 timed out on 3 tries: GET {LISTING} failed: timed out"}
PRICE_1, PRICE_2, PRICE_RETRY = "044522Z-main-a001", "050002Z-main-a002", "074536Z-retry-2933"
PROMO_1, PROMO_2, PROMO_RETRY = "051514Z-main-b001", "053014Z-main-b002", "081551Z-retry-9283"


def name(kind, i):
    """The i-th name on `kind`'s list (1 to 420), as listed: in name order, page p holding rows 20(p-1)+1 to 20p."""
    return f"{kind}7290027600007-001-{i:03d}-20261105-030000"


def stored(kind, rows):
    """The stored names (`<name>.gz`, ruling R16) of `rows`."""
    return {name(kind, i) + ".gz" for i in rows}


def run(store, run_id, kind):
    """One run of `kind` into `store`, from 900 s left at the morning's pace, every pager naming page 21; a retry's
    second listing page passes the socket timeout on every try, and each pause before a try takes its seconds off the
    clock. The run's result, the listing pages it asked for, its seconds left at the end."""
    clock = Clock(900.0)
    per_page, per_download = PACE[kind]
    mode = run_id.split("-")[1]
    reads = itertools.count(1)

    def listing_page(p):
        text = page(CATEGORY[kind], [name(kind, i) for i in range(ROWS * (p - 1) + 1, ROWS * p + 1)], last=PAGES)

        def respond(req):
            if next(reads) in (2, 3, 4) and mode == "retry":
                clock.left -= CHAIN.timeout
                raise TimeoutError("timed out")
            clock.left -= per_page
            return served(text)(req)
        return respond

    def download(req):
        clock.left -= per_download
        return gz()(req)

    routes = {listing_url(CATEGORY[kind], p): listing_page(p) for p in range(1, PAGES + 1)}
    # `limit` caps the run's requests at 21 pages and 420 files; a page read twice shows in the page lists and the
    # seconds left asserted below.
    http, portal = connect(routes, files=download, limit=PAGES + PAGES * ROWS)
    at = datetime(2026, 11, 5, int(run_id[:2]), int(run_id[2:4]), int(run_id[4:6]), tzinfo=timezone.utc)

    def pause(seconds):
        clock.left -= seconds

    source = ShufersalSource(now=lambda: at, timer=lambda: -clock.left, sleep=pause)
    result = collect_chain(CHAIN, source, http, store, DAY, run_id, mode, (kind,), clock, lambda: at, CODE_SHA)
    return result, listing_pages(portal), clock.left


def taken(result):
    """Each page record as (page, the row it was taken through, None when none), in the order read."""
    return [(record["page"], None if record["taken_through"] is None else int(record["taken_through"].split("-")[2]))
            for record in result.pages]


def whole(*pages):
    """Each page as taken to its last row."""
    return [(p, ROWS * p) for p in pages]


def test_the_2026_11_05_morning_replayed():
    """PriceFull's second run reads page 1, then page 12 again and on to 21, so the day reads PriceFull in full, and the
    retry, which starts a fresh pass, still alerts for its failed read (design, Call 1). PromoFull's second run resumes
    at page 10 and stops at page 19; its retry resumes at page 19 and times out there; the failed alert says how much
    of the PromoFull list was never read, and row 361, listed and never fetched, is missing."""
    store = MemoryStore()
    price_1, price_1_pages, price_1_left = run(store, PRICE_1, "PriceFull")
    price_2, price_2_pages, price_2_left = run(store, PRICE_2, "PriceFull")
    promo_1, promo_1_pages, promo_1_left = run(store, PROMO_1, "PromoFull")
    promo_2, promo_2_pages, promo_2_left = run(store, PROMO_2, "PromoFull")
    price_retry, price_retry_pages, price_retry_left = run(store, PRICE_RETRY, "PriceFull")
    promo_retry, promo_retry_pages, promo_retry_left = run(store, PROMO_RETRY, "PromoFull")

    # PriceFull main 1: pages 1 to 12, 72 s each; page 12 leaves 66 s, under 90, before row 221's download.
    assert price_1_pages == list(range(1, 13))
    assert (price_1.error, price_1_left) == (OUT_OF_TIME, 66.0)
    assert taken(price_1) == whole(*range(1, 12)) + [(12, 221)]
    assert price_1.not_attempted == [name("PriceFull", 221) + ".gz"]
    assert set(price_1.files) == stored("PriceFull", range(1, 221))

    # PriceFull main 2: page 1 (stored already), then page 12 again and on to page 21, every file downloaded.
    assert price_2_pages == [1, *range(12, 22)]
    assert (price_2.error, price_2.blocked, price_2_left) == (None, None, 138.0)
    assert taken(price_2) == whole(1, *range(12, 22))
    assert [record["seconds"] for record in price_2.pages] == [42.0] * 11
    assert set(price_2.files) == stored("PriceFull", range(221, 421))
    assert {file["outcome"] for file in price_2.files.values()} == {"stored"}

    # PromoFull main 1: pages 1 to 10, 85 s each; row 181 is downloaded at 90 s left exactly, then the run stops.
    assert promo_1_pages == list(range(1, 11))
    assert (promo_1.error, promo_1_left) == (OUT_OF_TIME, 88.0)
    assert taken(promo_1) == whole(*range(1, 10)) + [(10, 181)]
    assert promo_1.not_attempted == []
    assert set(promo_1.files) == stored("PromoFull", range(1, 182))

    # PromoFull main 2: page 1, then page 10 again and on; page 19 leaves 47 s before row 361's download.
    assert promo_2_pages == [1, *range(10, 20)]
    assert (promo_2.error, promo_2_left) == (OUT_OF_TIME, 47.0)
    assert taken(promo_2) == whole(1, *range(10, 19)) + [(19, 361)]
    assert promo_2.not_attempted == [name("PromoFull", 361) + ".gz"]
    assert set(promo_2.files) == stored("PromoFull", range(182, 361))

    # The retries: PriceFull was read in full, so a fresh pass; PromoFull resumes at page 19. Each times out on every
    # try of its second page (three tries of 60 s, 10 s apart), so only page 1 is recorded, its files stored already.
    assert price_retry_pages == [1, 2, 2, 2]
    assert promo_retry_pages == [1, 19, 19, 19]
    # 900 s less page 1 (42 s, PromoFull's 45 s), three tries of 60 s and the two pauses between them, 10 s each
    assert (price_retry_left, promo_retry_left) == (658.0, 655.0)
    for retry, kind in ((price_retry, "PriceFull"), (promo_retry, "PromoFull")):
        assert retry.error == TIMED_OUT[kind]
        assert taken(retry) == whole(1)
        assert retry.listed == sorted(stored(kind, range(1, 21))) and retry.files == {}
    # Each try that timed out is in the retry's manifest: the three of its second page, 60 s each. No main run had one.
    for retry, kind, second in ((price_retry, "PriceFull", 2), (promo_retry, "PromoFull", 19)):
        assert retry.timeouts == [{"kind": kind, "page": second, "attempt": attempt, "seconds": 60.0}
                                  for attempt in (1, 2, 3)]
    assert [main.timeouts for main in (price_1, price_2, promo_1, promo_2)] == [[]] * 4

    every_record = [record for result in (price_1, price_2, promo_1, promo_2, price_retry, promo_retry)
                    for record in result.pages]
    assert all(record["in_order"] and record["last_page"] == PAGES for record in every_record)

    alerts, record = check_day(store, ["shufersal"], DAY, kinds={"shufersal": ("PriceFull", "PromoFull")})
    chain = record["chains"]["shufersal"]
    assert chain["read_in_full"] == {"PriceFull": [PRICE_1, PRICE_2], "PromoFull": None}
    missing = name("PromoFull", 361) + ".gz"
    assert (chain["listed"], chain["stored"], chain["missing"]) == (420 + 361, 420 + 360, [missing])
    assert chain["short_of_time"] == []
    assert alerts == [
        Alert("shufersal", "missing", f"shufersal: 1 file listed for 2026-11-05 and not stored: {missing}."),
        Alert("shufersal", "failed",
              "shufersal: the day's runs fell short: "
              f"retry run {PRICE_RETRY} (PriceFull) ended with: {TIMED_OUT['PriceFull']}; "
              f"retry run {PROMO_RETRY} (PromoFull) ended with: {TIMED_OUT['PromoFull']}; "
              "the PromoFull list was not read in full: pages 20 to 21 never read, page 19 read in part."),
    ]


# ---- 2026-11-06's 05:00Z PriceFull run (q24) ----

NOV_6, NOV_6_RUN, NOV_6_PAGES = date(2026, 11, 6), "050003Z-main-c001", 22


def nov_6_name(i):
    """The i-th name on 2026-11-06's PriceFull list, as listed: in name order, page p holding rows 20(p-1)+1 to 20p."""
    return f"PriceFull7290027600007-001-{i:03d}-20261106-030000"


def nov_6_run(store):
    """2026-11-06's 05:00Z PriceFull run into `store`, from 900 s left, every pager naming page 22: pages 1 to 6 take
    35 s each (the measured median, 34.7 s, rounded); page 7's first request passes the socket timeout, and every
    listing request after it takes 45 s (the design's "about 45 s"); each download takes 1.25 s (about 1.2 s a file);
    the pause before page 7's second try takes its 10 s off the clock too. The run's result, the listing pages it asked
    for, its seconds left at the end."""
    clock = Clock(900.0)
    cat = CATEGORY["PriceFull"]

    def listing_page(p, seconds):
        text = page(cat, [nov_6_name(i) for i in range(ROWS * (p - 1) + 1, ROWS * p + 1)], last=NOV_6_PAGES)

        def respond(req):
            clock.left -= seconds
            return served(text)(req)
        return respond

    def timed_out(req):
        clock.left -= CHAIN.timeout
        raise TimeoutError("timed out")

    def download(req):
        clock.left -= 1.25
        return gz()(req)

    def pause(seconds):
        clock.left -= seconds

    routes = {listing_url(cat, p): listing_page(p, 35.0 if p <= 6 else 45.0) for p in range(1, NOV_6_PAGES + 1)}
    routes[listing_url(cat, 7)] = [timed_out, listing_page(7, 45.0)]  # served in turn: the first try, then the second
    http, portal = connect(routes, files=download, limit=NOV_6_PAGES + 1 + NOV_6_PAGES * ROWS)
    at = datetime(2026, 11, 6, 5, 0, 3, tzinfo=timezone.utc)
    source = ShufersalSource(now=lambda: at, timer=lambda: -clock.left, sleep=pause)
    result = collect_chain(CHAIN, source, http, store, NOV_6, NOV_6_RUN, "main", ("PriceFull",), clock, lambda: at,
                           CODE_SHA)
    return result, listing_pages(portal), clock.left


def test_the_2026_11_06_pricefull_run_replayed():
    """2026-11-06's 05:00Z PriceFull run (docs/shufersal-page-retry.md, "2026-11-06 replayed"). On the day its page 7
    timed out and the run ended there, with 117 files stored. Asked again after the pause, page 7 is read on its second
    try, and the run reads on to page 12, where the 90 s rule stops it before row 221's download; the check names that
    file missing and the pages never read. The list and its pace are synthetic, shaped like that morning: every count
    here is expected, not measured.

    The arithmetic: six pages at 60 s with their files leave 540 s; page 7's first try 480, the pause 470, its second
    try 425, its files 400; pages 8 to 11 at 70 s leave 120; page 12 leaves 75, under 90 before row 221's download."""
    store = MemoryStore()
    result, asked, left = nov_6_run(store)
    assert asked == [1, 2, 3, 4, 5, 6, 7, 7, 8, 9, 10, 11, 12]
    assert (result.error, result.blocked, left) == (OUT_OF_TIME, None, 75.0)
    assert taken(result) == whole(*range(1, 12)) + [(12, 221)]
    assert result.not_attempted == [nov_6_name(221) + ".gz"]
    assert [(record["page"], record["tries"], record["seconds"]) for record in result.pages] == (
        [(p, 1, 35.0) for p in range(1, 7)] + [(7, 2, 45.0)] + [(p, 1, 45.0) for p in range(8, 13)])
    assert all(record["in_order"] and record["last_page"] == NOV_6_PAGES for record in result.pages)
    assert result.timeouts == [{"kind": "PriceFull", "page": 7, "attempt": 1, "seconds": 60.0}]
    assert set(result.files) == {nov_6_name(i) + ".gz" for i in range(1, 221)}

    alerts, record = check_day(store, ["shufersal"], NOV_6, kinds={"shufersal": ("PriceFull",)})
    chain = record["chains"]["shufersal"]
    missing = "PriceFull7290027600007-001-221-20261106-030000.gz"
    assert chain["read_in_full"] == {"PriceFull": None}
    assert (chain["listed"], chain["stored"], chain["missing"]) == (221, 220, [missing])
    assert alerts == [
        Alert("shufersal", "missing", f"shufersal: 1 file listed for 2026-11-06 and not stored: {missing}."),
        Alert("shufersal", "failed", "shufersal: the day's runs fell short: no retry run covered PriceFull; the "
              "PriceFull list was not read in full: pages 13 to 22 never read, page 12 read in part."),
    ]


# ---- 2026-11-06's Shufersal Promo polls (q23) ----

POLLING = dataclasses.replace(CHAIN, polled=("Price", "Promo"))  # Shufersal's own `polled` is empty for now
POLL_DAY, PROMO_PAGES, DAYS_ROWS = date(2026, 11, 6), 22, 13  # a Friday; rows 1 to 13 of each page are dated that day
POLL_PACE = (42.0, 0.5)  # seconds a listing page, seconds a download
MORNING = "095959"  # every name's stamp until 14:59:59
AFTERNOON = {i: "145959" for i in range(1, ROWS * PROMO_PAGES, ROWS)}  # rows 1, 21, ..., 421: published at 14:59:59
POLL_1, POLL_2 = "083000Z-poll-e001", "084500Z-poll-e002"  # 10:30 and 10:45 in Israel (UTC+2)
POLL_3, POLL_4 = "131000Z-poll-e003", "132500Z-poll-e004"  # 15:10 and 15:25 in Israel


def promo_name(i, stamp=MORNING):
    """Row i (1 to 440) of 2026-11-06's Promo list, as listed: in name order, page p holding rows 20(p-1)+1 to 20p;
    rows 1 to 13 of each page are dated the day, rows 14 to 20 the day before."""
    dated = "20261106" if (i - 1) % ROWS < DAYS_ROWS else "20261105"
    return f"Promo7290027600007-001-{i:03d}-{dated}-{stamp}"


def promo_poll(store, run_id, republished=None):
    """One poll run of Promo into `store`, from 900 s left, at 42 s a listing page and 0.5 s a download, every pager
    naming page 22. `republished` maps each row whose store published again after 09:59:59 to its new stamp. The run's
    result, the listing pages it asked for, its seconds left at the end."""
    clock = Clock(900.0)
    per_page, per_download = POLL_PACE
    stamps = republished or {}
    cat = CATEGORY["Promo"]

    def listing_page(p):
        rows = range(ROWS * (p - 1) + 1, ROWS * p + 1)
        text = page(cat, [promo_name(i, stamps.get(i, MORNING)) for i in rows], last=PROMO_PAGES)

        def respond(req):
            clock.left -= per_page
            return served(text)(req)
        return respond

    def download(req):
        clock.left -= per_download
        return gz()(req)

    def pause(seconds):
        clock.left -= seconds

    routes = {listing_url(cat, p): listing_page(p) for p in range(1, PROMO_PAGES + 1)}
    # `limit` only keeps a listing that never ends from hanging the test: every page twice and every row's file
    http, portal = connect(routes, files=download, limit=2 * PROMO_PAGES + PROMO_PAGES * ROWS)
    at = datetime(2026, 11, 6, int(run_id[:2]), int(run_id[2:4]), int(run_id[4:6]), tzinfo=timezone.utc)
    source = ShufersalSource(now=lambda: at, timer=lambda: -clock.left, sleep=pause)
    result = collect_chain(POLLING, source, http, store, POLL_DAY, run_id, "poll", ("Promo",), clock, lambda: at,
                           CODE_SHA)
    return result, listing_pages(portal), clock.left


def outcome(result, asked, left):
    """A poll run as the replay's table gives it: the listing pages it asked for, its error, its seconds left, how many
    names it listed and stored, the names it never tried and its other days' names."""
    return asked, result.error, left, len(result.listed), len(result.files), result.not_attempted, result.other_days


def update_day(store):
    """2026-11-06 judged as the next morning's check judges its update day, Promo the one kind polled: the alerts, and
    Shufersal's section of the record."""
    alerts, record = judge_update_day(store, {"shufersal": ("Promo",)}, POLL_DAY)
    assert record["day"] == "2026-11-06"
    return alerts, record["chains"]["shufersal"]


def test_a_day_of_shufersal_promo_passes_replayed():
    """2026-11-06's Promo polls (docs/update-files.md, section 3, "What a pass of two runs gives"; ruling R39). The
    10:30 run reads to page 17 and stops on time; the 10:45 run resumes the pass at page 17 and reads to page 22, so the
    two read the list in full. At 14:59:59 the store of each page's first row publishes again. The 15:10 run starts a
    fresh pass, the first being complete, and stops on time at page 20; the 15:25 run resumes it there and completes it.
    The day and its pace are synthetic, shaped like that design's pass of two runs: every count here is expected, not
    measured.

    The arithmetic: a morning page with its 13 files costs 48.5 s, so page 17 starts with 124 s left and ends with 82,
    under 90 before row 321's download; the second run starts at page 17 (the open pass's furthest name, row 321),
    reading page 1 (42 s, its files stored), page 17 and its 13 files (48.5 s), then pages 18 to 22 (5 x 48.5). In the
    afternoon a page holds one new file (42.5 s): page 20 starts with 92.5 s left and ends with 50.5; the fourth run
    reads page 1 (42), page 20 (42.5) and pages 21 and 22 (2 x 42.5)."""
    store = MemoryStore()
    first = promo_poll(store, POLL_1)
    second = promo_poll(store, POLL_2)
    third = promo_poll(store, POLL_3, AFTERNOON)

    # The table: listing pages asked, error, seconds left, names listed, stored, never tried, other days' names.
    assert outcome(*first) == (list(range(1, 18)), OUT_OF_TIME, 82.0, 209, 208, [promo_name(321) + ".gz"],
                               {"2026-11-05": 112})
    assert outcome(*second) == ([1, *range(17, 23)], None, 567.0, 91, 78, [], {"2026-11-05": 49})
    # The first pass was read in full, so the third run starts a fresh one from page 1.
    assert outcome(*third) == (list(range(1, 21)), OUT_OF_TIME, 50.5, 248, 19, [promo_name(381, "145959") + ".gz"],
                               {"2026-11-05": 133})

    alerts, chain = update_day(store)
    assert alerts == []
    assert chain["passes"]["Promo"] == {
        "complete": [[POLL_1, POLL_2]], "out_of_order": [],
        "open": {"runs": [POLL_3], "unread": "pages 21 to 22 never read, page 20 read in part"}}
    assert chain["not_tried"] == {"Promo": [promo_name(381, "145959") + ".gz"]}

    # The fourth run resumes the open pass at page 20, where the third stopped.
    fourth = promo_poll(store, POLL_4, AFTERNOON)
    assert outcome(*fourth) == ([1, 20, 21, 22], None, 730.5, 52, 3, [], {"2026-11-05": 28})
    every_record = [record for result, _, _ in (first, second, third, fourth) for record in result.pages]
    assert all(record["in_order"] and record["last_page"] == PROMO_PAGES for record in every_record)

    alerts, chain = update_day(store)
    assert alerts == []
    assert chain["passes"]["Promo"] == {"complete": [[POLL_1, POLL_2], [POLL_3, POLL_4]], "out_of_order": [],
                                        "open": None}
    assert (chain["not_tried"], chain["missing"], chain["failed"]) == ({"Promo": []}, [], None)
    assert chain["by_hour"] == {"Promo": {"09": 286, "14": 22}}
    mornings = {promo_name(i) + ".gz" for i in range(1, ROWS * PROMO_PAGES + 1) if (i - 1) % ROWS < DAYS_ROWS}
    afternoons = {promo_name(i, stamp) + ".gz" for i, stamp in AFTERNOON.items()}
    assert store.stored_names("shufersal", POLL_DAY) == mornings | afternoons


def test_a_store_republished_at_the_resume_point_still_completes_the_pass():
    """A store republishes the resume page's first row between a pass's two runs (docs/update-files-plan.md, Review
    Focus 2). The 10:30 run, as above, stops before row 321's download; at 10:44:59 row 321's store publishes again,
    so page 17's first name now sorts after the furthest name the pass took (row 321's 09:59:59 name). The 10:45 run
    reads page 1, then page 17, steps back to page 16 (R37's step back) and gives page 16's rows, then reads page 17
    again and on to page 22. The pass is complete with no alert, and the 09:59:59 file, replaced before any run took
    it, is counted in `not_tried`, never emailed. Synthetic, as above: every count is expected, not measured.

    The arithmetic: page 1, page 17 stepped back from and page 16 (its files stored) cost 42 s each and leave 774 s;
    page 17 again with its 13 files, the new one among them, and pages 18 to 22, 48.5 s each, leave 483."""
    store = MemoryStore()
    first, first_pages, _ = promo_poll(store, POLL_1)
    assert (first_pages, first.error, first.not_attempted) == (list(range(1, 18)), OUT_OF_TIME,
                                                               [promo_name(321) + ".gz"])

    second, asked, left = promo_poll(store, POLL_2, {321: "104459"})
    assert asked == [1, 17, 16, 17, 18, 19, 20, 21, 22]
    assert (second.error, second.blocked, left) == (None, None, 483.0)
    # Page 17, stepped back from, gives no row; every page is in order, page 17 after page 16 included.
    assert [record["taken_through"] is None for record in second.pages] == [False, True] + [False] * 7
    assert all(record["in_order"] for record in second.pages)
    assert len(second.files) == 78 and promo_name(321, "104459") + ".gz" in second.files

    alerts, chain = update_day(store)
    assert alerts == []
    assert chain["passes"]["Promo"] == {"complete": [[POLL_1, POLL_2]], "out_of_order": [], "open": None}
    assert (chain["not_tried"], chain["missing"], chain["failed"]) == ({"Promo": [promo_name(321) + ".gz"]}, [], None)
    assert chain["by_hour"] == {"Promo": {"09": 285, "10": 1}}

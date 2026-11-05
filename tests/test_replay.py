"""2026-11-05's Shufersal morning, replayed through the real adapter, run loop and check, on the resume
(docs/shufersal-resume.md, "Why" and "2026-11-05 replayed").

The morning is synthetic, shaped like the real one: each full kind listed on 21 pages of 20 rows, read at the pace the
design works out from that morning's run times (40 to 45 s a page, 1 to 2 s a download), two main runs of each kind,
then one retry each whose second page passes the 60 s socket timeout. Every count asserted here is what that pace and
the 90 s rule give: expected, not measured.
"""
import itertools
from datetime import date, datetime, timezone

from collector.chains import CHAINS
from collector.check import Alert, check_day
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
TIMED_OUT = f"listing failed: GET {LISTING} failed: timed out"
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
    second listing page passes the socket timeout. The run's result, the listing pages it asked for, its seconds left
    at the end."""
    clock = Clock(900.0)
    per_page, per_download = PACE[kind]
    mode = run_id.split("-")[1]
    reads = itertools.count(1)

    def listing_page(p):
        text = page(CATEGORY[kind], [name(kind, i) for i in range(ROWS * (p - 1) + 1, ROWS * p + 1)], last=PAGES)

        def respond(req):
            if next(reads) == 2 and mode == "retry":
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
    source = ShufersalSource(now=lambda: at, timer=lambda: -clock.left)
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
    price_retry, price_retry_pages, _ = run(store, PRICE_RETRY, "PriceFull")
    promo_retry, promo_retry_pages, _ = run(store, PROMO_RETRY, "PromoFull")

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

    # The retries: PriceFull was read in full, so a fresh pass; PromoFull resumes at page 19. Each times out on its
    # second page, so only page 1 is recorded, its files stored already.
    assert price_retry_pages == [1, 2]
    assert promo_retry_pages == [1, 19]
    for retry, kind in ((price_retry, "PriceFull"), (promo_retry, "PromoFull")):
        assert retry.error == TIMED_OUT
        assert taken(retry) == whole(1)
        assert retry.listed == sorted(stored(kind, range(1, 21))) and retry.files == {}

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
              f"retry run {PRICE_RETRY} (PriceFull) ended with: {TIMED_OUT}; "
              f"retry run {PROMO_RETRY} (PromoFull) ended with: {TIMED_OUT}; "
              "the PromoFull list was not read in full: pages 20 to 21 never read, page 19 read in part."),
    ]

"""The site side of the scheduled build (`basket.site`): the published files read back, the latest day on the site,
the site run's upload (its data files always, the record files among them in a call of their own before the files that
name them, its pages only for the site's latest day, the fixed pages among them), every site file put through the pool with the content type and cache-control `scripts/publish.sh` sets, one
invalidation, and nothing deleted.

The rules run on MemorySite and on S3Site over test_store's FakeS3 and a fake CloudFront client, which must give
the same outcomes. The Stubber test at the end runs S3Site against real boto3 clients, so the put's, the read's,
the listing's and the invalidation's parameter names are checked against botocore's models offline.
"""
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from basket.site import (CACHE_CONTROL, CONTENT_TYPES, FIXED_PAGES, HTML, JSON, UPLOAD_WORKERS, MemorySite,
                         RecordsNotUploaded, S3Site, _Site, day_key, day_of, is_record)
from shopper.build import LEDGER
from shopper.freeze import scores_site_key, site_key
from test_store import FakeS3, client_error

ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 11, 3)
EARLIER = date(2026, 11, 2)
INDEX = b"<!doctype html><title>index</title>"
REFERENCE = "113000Z-basket-ab12"
ONE_PATH_ALL = {"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": REFERENCE}
# The design's content type of each kind of site file, by its last suffix (the plan's Task 22).
TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".csv": "text/csv; charset=utf-8", ".gz": "application/gzip"}


class FakeCloudFront:
    """A boto3 CloudFront client in memory that records every call: create_invalidation answers with the id "I1";
    any other method (a delete, say) is recorded and does nothing."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def create_invalidation(self, **kwargs):
        self.calls.append(("create_invalidation", kwargs))
        return {"Invalidation": {"Id": "I1"}}

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(**kwargs):
            self.calls.append((name, kwargs))
            return {}

        return call


@pytest.fixture(params=["memory", "s3"])
def site(request):
    if request.param == "s3":
        return S3Site(FakeS3(page_size=2), FakeCloudFront(), "site-bucket", "E123")
    return MemorySite()


def held(site) -> dict[str, tuple[bytes, str | None, str | None]]:
    """What the site bucket holds, in the order it was put: key → (body, content type, cache-control)."""
    if isinstance(site, MemorySite):
        return dict(site.objects)
    return {key: (body, sent.get("ContentType"), sent.get("CacheControl"))
            for key, (body, sent) in site.s3.objects.items()}


def on_site(site, key: str, body: bytes) -> None:
    """An object already on the site, from an earlier upload."""
    site._put(key, body, HTML if key.endswith(".html") else JSON, CACHE_CONTROL)


# The shopper site's fixed pages, by name (the plan's question H): rebuilt every morning from the code.
FIXED = ("index.html", "method.html", "record.html", "basket.html", "search.js")
# A site run's data files of the day, as `shopper.build` lists them new: they go up whatever the day.
DATA = ["forecasts/2026-11-03.csv.gz", "forecasts/ledger.csv", "scores/2026-10-20.csv.gz", "site-days/2026-11-03.json",
        "days/2026-11-03.json"]
# Of them, the record files, which go up first, and the files that name them (the task review's finding 1).
RECORDS = ["forecasts/2026-11-03.csv.gz", "scores/2026-10-20.csv.gz"]
NAMING = ["forecasts/ledger.csv", "site-days/2026-11-03.json", "days/2026-11-03.json"]
# Its pages under the page folders, in the order the upload takes them: by folder, then by name.
FOLDER_PAGES = ["p/2000000000046.html", "p/2000000000053.html", "browse/05d0.html", "browse/other.html",
                "search/05d0.json", "search/pieces.json"]


def built(folder: Path) -> Path:
    """A site folder as the site run leaves it in Lambda: the fixed pages, the pages under the page folders, the day's
    data files, the published copies of the day before's site-day file and of an earlier day's file, and the marker;
    each file's bytes its own key, so a body put under another key shows. Only the files an upload names go up."""
    for key in (*FIXED, *FOLDER_PAGES, *DATA, "site-days/2026-11-02.json", "days/2026-11-02.json", ".shopper-site"):
        (folder / key).parent.mkdir(parents=True, exist_ok=True)
        (folder / key).write_bytes(key.encode())
    return folder


def shopper_files(folder: Path, count: int) -> list[str]:
    """`count` files as the shopper build leaves them, every kind at least once, each file's bytes its own key (so a
    body put under another key shows); their keys, product pages last."""
    keys = ["index.html", "record.html", "search.js", "search/pieces.json", "search/05e9.json", "browse/index.html",
            "site-days/2026-11-03.json", "days/2026-11-03.json", "forecasts/ledger.csv", "forecasts/2026-11-03.csv.gz",
            "scores/2026-10-20.csv.gz"]
    keys += [f"p/{2000000000000 + n}.html" for n in range(count - len(keys))]
    for key in keys:
        (folder / key).parent.mkdir(parents=True, exist_ok=True)
        (folder / key).write_bytes(key.encode())
    return keys


def refused_puts(site, refused: set[str]) -> list[str]:
    """The key of each put the site makes from now on, from whichever thread, in the order they run; a put of a key in
    `refused` fails, as when the bucket does not answer."""
    puts, put = [], site._put

    def put_or_refuse(key, *rest):
        if key in refused:
            raise OSError(f"{key}: the site bucket did not answer")
        puts.append(key)
        put(key, *rest)

    site._put = put_or_refuse
    return puts


def recorded_puts(site) -> list[str]:
    """The key of each put the site makes from now on, from whichever thread, in the order they run."""
    puts, put = [], site._put

    def recorded(key, *rest):
        puts.append(key)
        put(key, *rest)

    site._put = recorded
    return puts


def test_keys_and_the_upload_settings_are_those_publish_sh_uses():
    assert day_key(DAY) == "days/2026-11-03.json"
    assert (HTML, JSON, CACHE_CONTROL) == ("text/html; charset=utf-8", "application/json; charset=utf-8", "max-age=300")
    assert CONTENT_TYPES == TYPES
    assert UPLOAD_WORKERS == 16
    script = (ROOT / "scripts" / "publish.sh").read_text()
    for setting in (*(f"--content-type '{kind}'" for kind in TYPES.values()), f"--cache-control '{CACHE_CONTROL}'",
                    "--paths '/*'"):
        assert setting in script


def test_published_day_is_none_before_the_first_upload(site, tmp_path):
    assert site.published_day(DAY) is None
    site.upload(built(tmp_path), DATA, with_pages=True)
    assert site.published_day(DAY) == b"days/2026-11-03.json"
    assert site.published_day(EARLIER) is None  # in the folder, but not uploaded


def test_latest_published_day_is_the_greatest_day_file(site):
    assert site.latest_published_day() is None
    on_site(site, "days/2026-11-03.json", b"{}")  # put before the earlier day: the answer is not the last listed
    on_site(site, "days/2026-11-02.json", b"{}")
    on_site(site, "days/notes.txt", b"notes")
    assert site.latest_published_day() == DAY


def test_latest_published_day_ignores_what_only_looks_like_a_day_file(site):
    on_site(site, "days/notes.txt", b"notes")
    on_site(site, "index.html", INDEX)
    assert site.latest_published_day() is None
    on_site(site, "days/2026-11-02.json", b"{}")
    for key in ("days/2026-11-09.json.bak", "days/2026-11-31.json", "days/old/2026-11-08.json", "days/2026-11-7.json"):
        on_site(site, key, b"{}")
    assert site.latest_published_day() == EARLIER


def test_latest_day_reads_both_folders(site):
    """The basket's day files (`days/`) and the shopper site's (`site-days/`) are published together; the latest day
    is the greatest in either."""
    on_site(site, "site-days/2026-11-03.json", b"{}")
    assert site.latest_published_day() == DAY  # a site-day file alone
    on_site(site, "days/2026-11-02.json", b"{}")
    assert site.latest_published_day() == DAY  # the greater is the site-day file's
    on_site(site, "days/2026-11-04.json", b"{}")
    assert site.latest_published_day() == date(2026, 11, 4)  # the greater is the day file's
    for key in ("site-days/2026-11-09.json.bak", "site-days/old/2026-11-08.json", "site-days/2026-11-31.json",
                "site-day/2026-11-09.json", "forecasts/2026-11-09.json"):
        on_site(site, key, b"{}")
    assert site.latest_published_day() == date(2026, 11, 4)
    if isinstance(site, S3Site):
        assert {kwargs["Prefix"] for op, kwargs in site.s3.calls if op == "paginate"} == {"days/", "site-days/"}


def test_published_and_keys_read_what_is_on_the_site(site):
    assert site.published("forecasts/ledger.csv") is None
    assert site.keys("p/") == []
    on_site(site, "forecasts/ledger.csv", b"day,sha256,frozen_at\n")
    for key in ("p/2000000000053.html", "p/2000000000046.html", "index.html", "browse/index.html"):
        on_site(site, key, key.encode())
    assert site.published("forecasts/ledger.csv") == b"day,sha256,frozen_at\n"
    assert site.published("p/2000000000046.html") == b"p/2000000000046.html"
    assert sorted(site.keys("p/")) == ["p/2000000000046.html", "p/2000000000053.html"]
    assert site.keys("search/") == []


def test_s3_site_finds_the_latest_day_past_the_first_page():
    fake = FakeS3(page_size=2)
    site = S3Site(fake, FakeCloudFront(), "site-bucket", "E123")
    for n in range(1, 6):
        on_site(site, day_key(date(2026, 11, n)), b"{}")
    fake.calls.clear()
    assert site.latest_published_day() == date(2026, 11, 5)
    assert ("paginate", {"Bucket": "site-bucket", "Prefix": "days/"}) in fake.calls


def test_upload_puts_the_data_files_then_every_page_with_its_content_type(site, tmp_path):
    """The site's latest day: the data files the build lists new, then every file under `p/`, `browse/` and `search/`,
    then the fixed pages, each with its content type by its last suffix and max-age=300; nothing else of the folder
    (the published copies, the marker)."""
    keys = site.upload(built(tmp_path), DATA, with_pages=True)
    assert keys == [*RECORDS, *NAMING, *FOLDER_PAGES, *FIXED]
    assert held(site) == {key: (key.encode(), TYPES[Path(key).suffix], CACHE_CONTROL) for key in keys}


def test_store_pages_go_up_with_the_pages(site, tmp_path):
    """Store first (q33): each store type's front page, `store/<key>.html`, rebuilt every morning, goes up with the
    pages under the other page folders, after them and before the fixed pages, as HTML."""
    folder = built(tmp_path)
    stores = ["store/carrefour-market.html", "store/osherad.html"]
    for key in stores:
        (folder / key).parent.mkdir(parents=True, exist_ok=True)
        (folder / key).write_bytes(key.encode())
    keys = site.upload(folder, DATA, with_pages=True)
    assert keys == [*RECORDS, *NAMING, *FOLDER_PAGES, *stores, *FIXED]
    assert {key: held(site)[key] for key in stores} == {key: (key.encode(), TYPES[".html"], CACHE_CONTROL)
                                                        for key in stores}


def test_upload_puts_the_fixed_pages(site, tmp_path):
    """The shopper plan's question H (and the second pre-flight's S15): the five fixed pages, rebuilt every morning
    from the code, go up with the day's pages, whatever the build lists."""
    assert FIXED_PAGES == FIXED
    keys = site.upload(built(tmp_path), [], with_pages=True)
    assert [key for key in keys if key in FIXED] == list(FIXED)
    assert set(FIXED) <= set(held(site))


def test_upload_puts_each_fixed_page_with_its_content_type(site, tmp_path):
    """The second pre-flight's B3: the site sends nosniff, so a script served as HTML would not run; `search.js` goes up
    as JavaScript, the four pages as HTML."""
    site.upload(built(tmp_path), [], with_pages=True)
    assert {key: held(site)[key][1] for key in FIXED} == {
        "index.html": "text/html; charset=utf-8", "method.html": "text/html; charset=utf-8",
        "record.html": "text/html; charset=utf-8", "basket.html": "text/html; charset=utf-8",
        "search.js": "text/javascript; charset=utf-8"}


def test_upload_for_an_earlier_day_puts_the_data_files_only(site, tmp_path):
    """Call 9: a day before the site's latest puts its data files and leaves every page as the later day's; the pages
    it is not to put may be missing from the folder."""
    on_site(site, "index.html", b"the later day's page")
    site_dir = built(tmp_path)
    assert site.upload(site_dir, DATA, with_pages=False) == [*RECORDS, *NAMING]
    assert held(site)["index.html"] == (b"the later day's page", HTML, CACHE_CONTROL)
    assert sorted(held(site)) == sorted([*DATA, "index.html"])
    for key in (*FIXED, *FOLDER_PAGES):
        (site_dir / key).unlink()
    assert site.upload(site_dir, DATA, with_pages=False) == [*RECORDS, *NAMING]


def test_a_record_file_is_a_forecasts_or_a_scores_file():
    """The record files are each day's forecasts file and scores file, as `shopper.freeze` names them on the site; the
    ledger, the day files and the pages are not."""
    assert is_record(site_key(DAY)) and is_record(scores_site_key(EARLIER))
    for key in (LEDGER, "site-days/2026-11-03.json", "days/2026-11-03.json", "index.html", "p/2000000000046.html",
                "search/pieces.json", "forecasts/2026-11-03.csv"):
        assert not is_record(key)


def test_upload_puts_the_record_files_before_the_files_that_name_them(site, tmp_path):
    """The task review's finding 1: the record files go up in a call of their own, every put of it ended before the
    ledger, the site-day and day files and the pages, which name them, are put."""
    puts = refused_puts(site, set())
    assert site.upload(built(tmp_path), DATA, with_pages=True) == [*RECORDS, *NAMING, *FOLDER_PAGES, *FIXED]
    assert sorted(puts[:len(RECORDS)]) == sorted(RECORDS)


@pytest.mark.parametrize("refused", RECORDS)
def test_a_failed_record_put_stops_the_upload_before_anything_that_names_it(site, tmp_path, refused):
    """A record put that fails stops the upload (RecordsNotUploaded, naming what failed): the other record may be up,
    nothing that names one is, so the ledger can never name a file the site lacks."""
    refused_puts(site, {refused})
    with pytest.raises(RecordsNotUploaded, match=re.escape(refused)) as raised:
        site.upload(built(tmp_path), DATA, with_pages=True)
    assert str(raised.value).startswith("a record file did not go up, so nothing that names it was put: OSError: ")
    assert set(held(site)) <= set(RECORDS) - {refused}


def test_upload_puts_only_the_data_files_it_is_given(site, tmp_path):
    """An unchanged day lists no data file: the pages go up, and the folder's day files, the published copies among
    them, stay local; a data file it is not to put may be missing."""
    on_site(site, "days/2026-11-03.json", b"published")
    site_dir = built(tmp_path)
    assert site.upload(site_dir, [], with_pages=True) == [*FOLDER_PAGES, *FIXED]
    assert held(site)["days/2026-11-03.json"][0] == b"published"
    assert not [key for key in held(site) if key.startswith(("site-days/", "forecasts/", "scores/"))]
    (site_dir / "days" / "2026-11-03.json").unlink()
    assert site.upload(site_dir, ["forecasts/ledger.csv"], with_pages=False) == ["forecasts/ledger.csv"]


def test_upload_of_nothing_puts_nothing(site, tmp_path):
    assert site.upload(built(tmp_path), [], with_pages=False) == []
    assert held(site) == {}


def test_upload_takes_the_page_folders_whole(site, tmp_path):
    """Every file under the page folders, in sub-folders too, is a page to put; one of no known type stops the upload
    before anything goes up, as `put_files` refuses it."""
    site_dir = built(tmp_path)
    (site_dir / "p" / "more").mkdir()
    (site_dir / "p" / "more" / "2000000000060.html").write_bytes(b"deeper")
    assert "p/more/2000000000060.html" in site.upload(site_dir, [], with_pages=True)
    (site_dir / "search" / "notes.txt").write_bytes(b"")
    with pytest.raises(ValueError, match="search/notes.txt: no content type"):
        MemorySite().upload(site_dir, DATA, with_pages=True)


@pytest.mark.parametrize("missing", ["method.html", "search.js", "days/2026-11-03.json"])
def test_upload_refuses_a_missing_file_before_any_put(site, tmp_path, missing):
    """A fixed page or a data file missing from the folder stops the upload before anything goes up: not the data
    files found first either. (The page folders go up as they are: a product page the build lost is the guard's.)"""
    site_dir = built(tmp_path)
    (site_dir / missing).unlink()
    with pytest.raises(FileNotFoundError, match=re.escape(missing)):
        site.upload(site_dir, DATA, with_pages=True)
    assert held(site) == {}


def test_day_of_reads_a_day_file_or_a_site_day_file():
    """The day a published day file or site-day file names, the rule the latest day and the site run's previous
    site-day file share; None for anything else."""
    assert day_of("days/2026-11-03.json") == day_of("site-days/2026-11-03.json") == DAY
    for key in ("days/2026-11-31.json", "site-days/2026-11-03.json.bak", "forecasts/2026-11-03.csv.gz", "index.html"):
        assert day_of(key) is None


def test_put_files_puts_each_once_with_its_content_type(site, tmp_path):
    """2,000 files through the pool: each put once, its own bytes under its own key, its content type by its last
    suffix (a forecasts file `.csv.gz` is gzip, never text) and max-age=300; a key given twice goes up once."""
    keys = shopper_files(tmp_path, 2000)
    puts = recorded_puts(site)
    assert site.put_files(tmp_path, keys + ["index.html", "forecasts/ledger.csv"]) == keys
    assert len(puts) == 2000 and sorted(puts) == sorted(keys)
    assert held(site) == {key: (key.encode(), TYPES[Path(key).suffix], CACHE_CONTROL) for key in keys}
    assert held(site)["forecasts/2026-11-03.csv.gz"][1] == "application/gzip"
    assert held(site)["search.js"][1] == "text/javascript; charset=utf-8"
    assert held(site)["forecasts/ledger.csv"][1] == "text/csv; charset=utf-8"


def test_put_files_of_no_file_puts_nothing(site, tmp_path):
    assert site.put_files(tmp_path, []) == []
    assert held(site) == {}


def test_put_files_refuses_a_missing_file_before_any_put(site, tmp_path):
    keys = shopper_files(tmp_path, 40)
    (tmp_path / "scores/2026-10-20.csv.gz").unlink()
    with pytest.raises(FileNotFoundError, match="scores/2026-10-20.csv.gz"):
        site.put_files(tmp_path, keys)
    assert held(site) == {}  # not the 39 files that are there either
    (tmp_path / "scores/2026-10-20.csv.gz").mkdir()  # a folder in its place is no file
    with pytest.raises(FileNotFoundError, match="scores/2026-10-20.csv.gz"):
        site.put_files(tmp_path, keys)
    assert held(site) == {}


@pytest.mark.parametrize("odd", [".shopper-site", "notes.txt", "p/2000000000046.htm", "forecasts/ledger"])
def test_put_files_refuses_a_file_of_no_known_type_before_any_put(site, tmp_path, odd):
    """The content type is set, never guessed (the site's headers send nosniff): a file of another kind stops the
    upload before anything goes up."""
    keys = shopper_files(tmp_path, 40)
    (tmp_path / odd).write_bytes(b"")
    with pytest.raises(ValueError, match=f"{odd}: no content type"):
        site.put_files(tmp_path, keys + [odd])
    assert held(site) == {}


def test_put_files_puts_through_a_pool_of_16(tmp_path):
    """The first 16 puts each wait until all 16 are in flight at once: a pool of fewer threads, or puts one after
    another, never fills the barrier, which then breaks and fails the upload."""
    site = MemorySite()
    barrier, lock, started = threading.Barrier(16, timeout=10), threading.Lock(), []
    put = site._put

    def held_until_16_are_in_flight(key, *rest):
        with lock:
            started.append(key)
            first = len(started) <= 16
        if first:
            barrier.wait()
        put(key, *rest)

    site._put = held_until_16_are_in_flight
    keys = shopper_files(tmp_path, 40)
    assert site.put_files(tmp_path, keys) == keys
    assert sorted(site.objects) == sorted(keys)


def test_put_files_raises_a_failed_put(tmp_path):
    fake = FakeS3()
    fake.errors["put_object"] = [client_error("AccessDenied", 403, "PutObject")]
    site = S3Site(fake, FakeCloudFront(), "site-bucket", "E123")
    with pytest.raises(ClientError, match="AccessDenied"):
        site.put_files(tmp_path, shopper_files(tmp_path, 40))


def test_invalidate_sends_one_path_and_the_reference():
    cloudfront = FakeCloudFront()
    site = S3Site(FakeS3(), cloudfront, "site-bucket", "E123")
    assert site.invalidate(REFERENCE) == "I1"
    assert cloudfront.calls == [("create_invalidation", {"DistributionId": "E123", "InvalidationBatch": ONE_PATH_ALL})]


def test_memory_site_records_each_invalidation():
    site = MemorySite()
    assert site.invalidations == []
    first = site.invalidate(REFERENCE)
    second = site.invalidate("123000Z-basket-cd34")
    assert site.invalidations == [REFERENCE, "123000Z-basket-cd34"]
    assert first != second


@pytest.mark.parametrize("code", [None, "NoSuchKey", "404"])
def test_s3_site_reads_a_missing_day_as_none(code):
    fake = FakeS3()  # with nothing: get_object answers NoSuchKey
    if code:
        fake.errors["get_object"] = [client_error(code, 404, "GetObject")]
    site = S3Site(fake, FakeCloudFront(), "site-bucket", "E123")
    assert site.published_day(DAY) is None
    assert fake.calls == [("get_object", {"Bucket": "site-bucket", "Key": "days/2026-11-03.json"})]


def test_s3_site_does_not_hide_a_read_error():
    fake = FakeS3()
    fake.errors["get_object"] = [client_error("AccessDenied", 403, "GetObject")]
    site = S3Site(fake, FakeCloudFront(), "site-bucket", "E123")
    with pytest.raises(ClientError, match="AccessDenied"):
        site.published_day(DAY)


def test_no_method_ever_deletes(tmp_path):
    fake, cloudfront = FakeS3(page_size=2), FakeCloudFront()
    site = S3Site(fake, cloudfront, "site-bucket", "E123")
    site_dir = built(tmp_path)

    called = set()

    def call(method: str, *args, **kwargs):
        called.add(method)
        return getattr(site, method)(*args, **kwargs)

    call("published_day", DAY)
    call("latest_published_day")
    call("published", "days/2026-11-03.json")
    call("keys", "p/")
    shop_dir = tmp_path / "shop"
    shop_dir.mkdir()
    keys = shopper_files(shop_dir, 40)
    call("put_files", shop_dir, keys)
    call("put_files", shop_dir, keys)  # the same files again
    (shop_dir / "search.js").unlink()
    with pytest.raises(FileNotFoundError):
        call("put_files", shop_dir, keys)
    for with_pages in (True, False):
        for data in (DATA, []):
            call("upload", site_dir, data, with_pages=with_pages)
    call("upload", site_dir, DATA, with_pages=True)  # the same files again
    call("published_day", DAY)
    call("latest_published_day")
    call("invalidate", REFERENCE)
    (site_dir / "method.html").unlink()
    with pytest.raises(FileNotFoundError):
        call("upload", site_dir, DATA, with_pages=True)
    # every method _Site defines was run above
    assert called == {name for name in vars(_Site) if not name.startswith("_")}
    assert {op for op, _ in fake.calls} <= {"put_object", "get_object", "get_paginator", "paginate"}
    assert {op for op, _ in cloudfront.calls} == {"create_invalidation"}


# S3Site against real boto3 clients: parameter names checked against botocore's S3 and CloudFront models

def test_real_clients_take_the_put_the_read_the_listing_and_the_invalidation(tmp_path):
    keys = {"region_name": "il-central-1", "aws_access_key_id": "test", "aws_secret_access_key": "test"}
    s3, cloudfront = boto3.client("s3", **keys), boto3.client("cloudfront", **keys)
    site = S3Site(s3, cloudfront, "site-bucket", "E123")
    site_dir = built(tmp_path)
    with Stubber(s3) as s3_stub, Stubber(cloudfront) as cloudfront_stub:
        # one put: the pool's puts of several files run in no fixed order, and the Stubber answers in order
        s3_stub.add_response("put_object", {}, {"Bucket": "site-bucket", "Key": "days/2026-11-03.json",
                                                "Body": b"days/2026-11-03.json", "ContentType": JSON,
                                                "CacheControl": CACHE_CONTROL})
        s3_stub.add_client_error("get_object", "NoSuchKey", http_status_code=404,
                                 expected_params={"Bucket": "site-bucket", "Key": "days/2026-11-04.json"})
        s3_stub.add_response("list_objects_v2", {"Contents": [{"Key": "days/2026-11-02.json"}], "IsTruncated": True,
                                                 "NextContinuationToken": "t"},
                             {"Bucket": "site-bucket", "Prefix": "days/"})
        s3_stub.add_response("list_objects_v2", {"Contents": [{"Key": "days/2026-11-03.json"}], "IsTruncated": False},
                             {"Bucket": "site-bucket", "Prefix": "days/", "ContinuationToken": "t"})
        s3_stub.add_response("list_objects_v2", {"KeyCount": 0, "IsTruncated": False},
                             {"Bucket": "site-bucket", "Prefix": "site-days/"})
        created = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)
        cloudfront_stub.add_response(
            "create_invalidation",
            {"Location": "https://cloudfront.amazonaws.com/2020-05-31/distribution/E123/invalidation/I1",
             "Invalidation": {"Id": "I1", "Status": "InProgress", "CreateTime": created,
                              "InvalidationBatch": ONE_PATH_ALL}},
            {"DistributionId": "E123", "InvalidationBatch": ONE_PATH_ALL})
        assert site.upload(site_dir, ["days/2026-11-03.json"], with_pages=False) == ["days/2026-11-03.json"]
        assert site.published_day(date(2026, 11, 4)) is None
        assert site.latest_published_day() == DAY
        assert site.invalidate(REFERENCE) == "I1"
        s3_stub.assert_no_pending_responses()
        cloudfront_stub.assert_no_pending_responses()

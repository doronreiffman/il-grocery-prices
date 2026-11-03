"""The site side of the scheduled build (`basket.site`): the published day read back, the latest day on the site,
the pages and the day file put with the content types and cache-control `scripts/publish.sh` sets, one
invalidation, and nothing deleted.

The rules run on MemorySite and on S3Site over test_store's FakeS3 and a fake CloudFront client, which must give
the same outcomes. The Stubber test at the end runs S3Site against real boto3 clients, so the put's, the read's,
the listing's and the invalidation's parameter names are checked against botocore's models offline.
"""
from datetime import date, datetime, timezone
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from basket.site import CACHE_CONTROL, HTML, JSON, PAGES, MemorySite, S3Site, _Site, day_key
from test_store import FakeS3, client_error

ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 11, 3)
EARLIER = date(2026, 11, 2)
INDEX = b"<!doctype html><title>index</title>"
METHOD = b"<!doctype html><title>method</title>"
DAY_FILE = b'{"day": "2026-11-03"}'
REFERENCE = "113000Z-basket-ab12"
ONE_PATH_ALL = {"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": REFERENCE}


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


def built(folder: Path) -> Path:
    """A site folder as `basket.build` leaves it: the two pages, the day's file, an earlier day's file and the
    marker. Only the files an upload names go up."""
    (folder / "days").mkdir(parents=True)
    (folder / "index.html").write_bytes(INDEX)
    (folder / "method.html").write_bytes(METHOD)
    (folder / "days" / "2026-11-03.json").write_bytes(DAY_FILE)
    (folder / "days" / "2026-11-02.json").write_bytes(b'{"day": "2026-11-02"}')
    (folder / ".basket-site").write_bytes(b"")
    return folder


def test_keys_and_the_upload_settings_are_those_publish_sh_uses():
    assert day_key(DAY) == "days/2026-11-03.json"
    assert PAGES == ("index.html", "method.html")
    assert (HTML, JSON, CACHE_CONTROL) == ("text/html; charset=utf-8", "application/json; charset=utf-8", "max-age=300")
    script = (ROOT / "scripts" / "publish.sh").read_text()
    for setting in (f"--content-type '{HTML}'", f"--content-type '{JSON}'", f"--cache-control '{CACHE_CONTROL}'",
                    "--paths '/*'"):
        assert setting in script


def test_published_day_is_none_before_the_first_upload(site, tmp_path):
    assert site.published_day(DAY) is None
    site.upload(built(tmp_path), DAY, with_pages=True, with_day=True)
    assert site.published_day(DAY) == DAY_FILE
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


def test_s3_site_finds_the_latest_day_past_the_first_page():
    fake = FakeS3(page_size=2)
    site = S3Site(fake, FakeCloudFront(), "site-bucket", "E123")
    for n in range(1, 6):
        on_site(site, day_key(date(2026, 11, n)), b"{}")
    fake.calls.clear()
    assert site.latest_published_day() == date(2026, 11, 5)
    assert ("paginate", {"Bucket": "site-bucket", "Prefix": "days/"}) in fake.calls


def test_upload_puts_the_pages_then_the_day_file_with_content_types_and_cache_control(site, tmp_path):
    keys = site.upload(built(tmp_path), DAY, with_pages=True, with_day=True)
    assert keys == ["index.html", "method.html", "days/2026-11-03.json"]
    assert list(held(site).items()) == [
        ("index.html", (INDEX, HTML, CACHE_CONTROL)),
        ("method.html", (METHOD, HTML, CACHE_CONTROL)),
        ("days/2026-11-03.json", (DAY_FILE, JSON, CACHE_CONTROL)),
    ]


def test_upload_without_the_day_file_leaves_days_alone(site, tmp_path):
    on_site(site, "days/2026-11-03.json", b"published")
    site_dir = built(tmp_path)
    assert site.upload(site_dir, DAY, with_pages=True, with_day=False) == ["index.html", "method.html"]
    assert held(site)["days/2026-11-03.json"][0] == b"published"
    assert held(site)["index.html"] == (INDEX, HTML, CACHE_CONTROL)
    # a day file it is not to put may be missing from the folder
    (site_dir / "days" / "2026-11-03.json").unlink()
    assert site.upload(site_dir, DAY, with_pages=True, with_day=False) == ["index.html", "method.html"]
    assert sorted(held(site)) == ["days/2026-11-03.json", "index.html", "method.html"]


def test_upload_without_the_pages_puts_the_day_file_only(site, tmp_path):
    on_site(site, "index.html", b"the later day's page")
    site_dir = built(tmp_path)
    assert site.upload(site_dir, DAY, with_pages=False, with_day=True) == ["days/2026-11-03.json"]
    assert held(site) == {"index.html": (b"the later day's page", HTML, CACHE_CONTROL),
                          "days/2026-11-03.json": (DAY_FILE, JSON, CACHE_CONTROL)}
    # pages it is not to put may be missing from the folder
    (site_dir / "index.html").unlink()
    (site_dir / "method.html").unlink()
    assert site.upload(site_dir, DAY, with_pages=False, with_day=True) == ["days/2026-11-03.json"]


def test_upload_of_neither_puts_nothing(site, tmp_path):
    assert site.upload(built(tmp_path), DAY, with_pages=False, with_day=False) == []
    assert held(site) == {}


def test_upload_refuses_a_missing_page(site, tmp_path):
    site_dir = built(tmp_path / "no-method")
    (site_dir / "method.html").unlink()
    with pytest.raises(FileNotFoundError, match="method.html"):
        site.upload(site_dir, DAY, with_pages=True, with_day=True)
    assert held(site) == {}  # index.html, found first, was not put either
    site_dir = built(tmp_path / "no-day")
    (site_dir / "days" / "2026-11-03.json").unlink()
    with pytest.raises(FileNotFoundError, match="2026-11-03.json"):
        site.upload(site_dir, DAY, with_pages=True, with_day=True)
    assert held(site) == {}


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
    for with_pages in (True, False):
        for with_day in (True, False):
            call("upload", site_dir, DAY, with_pages=with_pages, with_day=with_day)
    call("upload", site_dir, DAY, with_pages=True, with_day=True)  # the same files again
    call("published_day", DAY)
    call("latest_published_day")
    call("invalidate", REFERENCE)
    (site_dir / "method.html").unlink()
    with pytest.raises(FileNotFoundError):
        call("upload", site_dir, DAY, with_pages=True, with_day=True)
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
        for key, body, content_type in (("index.html", INDEX, HTML), ("method.html", METHOD, HTML),
                                        ("days/2026-11-03.json", DAY_FILE, JSON)):
            s3_stub.add_response("put_object", {}, {"Bucket": "site-bucket", "Key": key, "Body": body,
                                                    "ContentType": content_type, "CacheControl": CACHE_CONTROL})
        s3_stub.add_client_error("get_object", "NoSuchKey", http_status_code=404,
                                 expected_params={"Bucket": "site-bucket", "Key": "days/2026-11-04.json"})
        s3_stub.add_response("list_objects_v2", {"Contents": [{"Key": "days/2026-11-02.json"}], "IsTruncated": True,
                                                 "NextContinuationToken": "t"},
                             {"Bucket": "site-bucket", "Prefix": "days/"})
        s3_stub.add_response("list_objects_v2", {"Contents": [{"Key": "days/2026-11-03.json"}], "IsTruncated": False},
                             {"Bucket": "site-bucket", "Prefix": "days/", "ContinuationToken": "t"})
        created = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)
        cloudfront_stub.add_response(
            "create_invalidation",
            {"Location": "https://cloudfront.amazonaws.com/2020-05-31/distribution/E123/invalidation/I1",
             "Invalidation": {"Id": "I1", "Status": "InProgress", "CreateTime": created,
                              "InvalidationBatch": ONE_PATH_ALL}},
            {"DistributionId": "E123", "InvalidationBatch": ONE_PATH_ALL})
        assert site.upload(site_dir, DAY, with_pages=True, with_day=True) == list(PAGES) + ["days/2026-11-03.json"]
        assert site.published_day(date(2026, 11, 4)) is None
        assert site.latest_published_day() == DAY
        assert site.invalidate(REFERENCE) == "I1"
        s3_stub.assert_no_pending_responses()
        cloudfront_stub.assert_no_pending_responses()

"""Storage: raw files and records written once and locked; state files plain; nothing ever deleted.

Most tests run against S3Store over FakeS3 (a boto3 client in memory that answers as S3 does) and
against MemoryStore, which must give the same outcomes for the same calls. The Stubber tests at the
end run S3Store against a real boto3 client, so every call's parameter names are checked against
botocore's S3 model offline.
"""
import base64
import hashlib
import io
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from collector.store import (
    AlreadyStored,
    MemoryStore,
    PutOutcome,
    S3Store,
    Stored,
    check_key,
    manifest_key,
    raw_key,
    state_key,
)

NOW = datetime(2026, 11, 1, 6, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
TEN_YEARS = NOW + timedelta(days=3650)
DAY = date(2026, 11, 1)
NAME = "PriceFull7290027600007-001-030-20261101-030000.gz"
KEY = f"raw/chain=shufersal/date=2026-11-01/{NAME}"
LOCKED = {"IfNoneMatch": "*", "ObjectLockMode": "GOVERNANCE", "ObjectLockRetainUntilDate": TEN_YEARS,
          "ChecksumAlgorithm": "SHA256"}


def sha12(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:12]


def b64sha(body: bytes) -> str:
    return base64.b64encode(hashlib.sha256(body).digest()).decode()


def client_error(code: str, status: int, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
                       operation)


class FakeS3:
    """A boto3 S3 client in memory that records every call.

    As S3: a put with IfNoneMatch="*" on a stored key fails with PreconditionFailed (412);
    head_object gives ChecksumSHA256 only with ChecksumMode="ENABLED" and only for an object put
    with ChecksumAlgorithm="SHA256"; a missing key is NoSuchKey on get and "404" on head; listings
    come in key order, `page_size` keys a page, and an empty one has no Contents. Errors queued in
    `errors[operation]` are raised by that operation's next calls. Any other method (a delete, say)
    is recorded and does nothing.
    """

    def __init__(self, page_size: int = 1000):
        self.page_size = page_size
        self.objects: dict[str, tuple[bytes, dict]] = {}
        self.calls: list[tuple[str, dict]] = []
        self.errors: dict[str, list[ClientError]] = {}

    def _call(self, operation: str, kwargs: dict) -> None:
        self.calls.append((operation, kwargs))
        if self.errors.get(operation):
            raise self.errors[operation].pop(0)

    def put_object(self, **kwargs):
        self._call("put_object", kwargs)
        if kwargs.get("IfNoneMatch") == "*" and kwargs["Key"] in self.objects:
            raise client_error("PreconditionFailed", 412, "PutObject")
        self.objects[kwargs["Key"]] = (kwargs["Body"], kwargs)
        return {}

    def head_object(self, **kwargs):
        self._call("head_object", kwargs)
        if kwargs["Key"] not in self.objects:
            raise client_error("404", 404, "HeadObject")
        body, put = self.objects[kwargs["Key"]]
        answer = {"ContentLength": len(body)}
        if kwargs.get("ChecksumMode") == "ENABLED" and put.get("ChecksumAlgorithm") == "SHA256":
            answer["ChecksumSHA256"] = b64sha(body)
        return answer

    def get_object(self, **kwargs):
        self._call("get_object", kwargs)
        if kwargs["Key"] not in self.objects:
            raise client_error("NoSuchKey", 404, "GetObject")
        return {"Body": io.BytesIO(self.objects[kwargs["Key"]][0])}

    def _pages(self, prefix: str):
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        if not keys:
            yield {"KeyCount": 0, "IsTruncated": False}
        for start in range(0, len(keys), self.page_size):
            page = keys[start:start + self.page_size]
            yield {"Contents": [{"Key": key} for key in page], "KeyCount": len(page),
                   "IsTruncated": start + self.page_size < len(keys)}

    def list_objects_v2(self, **kwargs):
        """One call is one page, as in boto3: the rest needs the paginator."""
        self._call("list_objects_v2", kwargs)
        return next(self._pages(kwargs["Prefix"]))

    def get_paginator(self, operation: str):
        self._call("get_paginator", {"operation": operation})
        assert operation == "list_objects_v2"
        fake = self

        class Paginator:
            def paginate(self, **kwargs):
                fake._call("paginate", kwargs)
                return fake._pages(kwargs["Prefix"])

        return Paginator()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(**kwargs):
            self.calls.append((name, kwargs))
            return {}

        return call


def put(key: str, body: bytes, **extra) -> tuple[str, dict]:
    return ("put_object", {"Bucket": "bucket", "Key": key, "Body": body, **extra})


def head(key: str) -> tuple[str, dict]:
    return ("head_object", {"Bucket": "bucket", "Key": key, "ChecksumMode": "ENABLED"})


@pytest.fixture
def fake():
    return FakeS3(page_size=2)


@pytest.fixture
def s3(fake):
    return S3Store(fake, "bucket")


@pytest.fixture(params=["s3", "memory"])
def store(request):
    if request.param == "s3":
        return S3Store(FakeS3(page_size=2), "bucket")
    return MemoryStore()


def lock_of(store, key: str) -> tuple[str | None, datetime | None]:
    if isinstance(store, MemoryStore):
        return store.objects[key].lock_mode, store.objects[key].retain_until
    sent = store.client.objects[key][1]
    return sent.get("ObjectLockMode"), sent.get("ObjectLockRetainUntilDate")


# keys and outcomes

def test_keys():
    assert raw_key("shufersal", DAY, NAME) == KEY
    assert manifest_key(DAY, "ramilevy", "063000Z-main-ab12") == "manifests/date=2026-11-01/ramilevy-063000Z-main-ab12.json"
    assert check_key(DAY, "070000Z-check-cd34") == "checks/date=2026-11-01/check-070000Z-check-cd34.json"
    assert state_key("osherad") == "state/osherad.json"


def test_outcome_values():
    assert [(o.name, o.value) for o in PutOutcome] == [("STORED", "stored"), ("EXISTS", "exists"),
                                                         ("CONFLICT_STORED", "conflict")]


# S3Store: what goes to S3

def test_put_raw_is_write_once_and_locked(s3, fake):
    assert s3.put_raw(KEY, b"gz", NOW) is PutOutcome.STORED
    assert fake.calls == [put(KEY, b"gz", **LOCKED)]


def test_lock_settings_come_from_the_arguments(fake):
    S3Store(fake, "bucket", retention_days=30, lock_mode="COMPLIANCE").put_raw(KEY, b"gz", NOW)
    assert fake.calls == [put(KEY, b"gz", **LOCKED | {"ObjectLockMode": "COMPLIANCE",
                                                      "ObjectLockRetainUntilDate": NOW + timedelta(days=30)})]


def test_put_record_is_write_once_and_locked(s3, fake):
    key = manifest_key(DAY, "carrefour", "063000Z-main-ab12")
    assert s3.put_record(key, b'{"a": 1}', NOW) is None
    assert fake.calls == [put(key, b'{"a": 1}', ContentType="application/json", **LOCKED)]


def test_a_records_content_type_is_the_callers_when_given(s3, fake):
    key = "forecasts/date=2026-11-01/forecasts.csv.gz"   # an object's type cannot be changed once it is locked
    s3.put_record(key, b"gz", NOW, "application/gzip")
    assert fake.calls == [put(key, b"gz", ContentType="application/gzip", **LOCKED)]


def test_identical_body_is_exists(s3, fake):
    s3.put_raw(KEY, b"one", NOW)
    fake.calls.clear()
    assert s3.put_raw(KEY, b"one", NOW) is PutOutcome.EXISTS
    assert fake.calls == [put(KEY, b"one", **LOCKED), head(KEY)]  # the checksum is enough; no second put
    assert list(fake.objects) == [KEY]


def test_different_body_gets_hash_suffix(s3, fake):
    s3.put_raw(KEY, b"one", NOW)
    fake.calls.clear()
    assert s3.put_raw(KEY, b"two", NOW) is PutOutcome.CONFLICT_STORED
    copy = f"{KEY}.{sha12(b'two')}"
    assert fake.calls == [put(KEY, b"two", **LOCKED), head(KEY), put(copy, b"two", **LOCKED)]
    assert fake.objects[KEY][0] == b"one" and fake.objects[copy][0] == b"two"


def test_409_counts_as_already_there(s3, fake):
    s3.put_raw(KEY, b"one", NOW)
    fake.errors["put_object"] = [client_error("ConditionalRequestConflict", 409, "PutObject")]
    assert s3.put_raw(KEY, b"one", NOW) is PutOutcome.EXISTS
    fake.errors["put_object"] = [client_error("ConditionalRequestConflict", 409, "PutObject")]
    assert s3.put_raw(KEY, b"two", NOW) is PutOutcome.CONFLICT_STORED
    assert fake.objects[f"{KEY}.{sha12(b'two')}"][0] == b"two"


def test_409_with_nothing_there_yet_is_not_hidden(s3, fake):
    fake.errors["put_object"] = [client_error("ConditionalRequestConflict", 409, "PutObject")]
    with pytest.raises(ClientError, match="404"):
        s3.put_raw(KEY, b"one", NOW)


@pytest.mark.parametrize("code, status", [("AccessDenied", 403), ("SlowDown", 503), ("InvalidRequest", 400)])
def test_other_put_errors_propagate(s3, fake, code, status):
    fake.errors["put_object"] = [client_error(code, status, "PutObject"), client_error(code, status, "PutObject")]
    with pytest.raises(ClientError, match=code):
        s3.put_raw(KEY, b"one", NOW)
    with pytest.raises(ClientError, match=code):
        s3.put_record("manifests/date=2026-11-01/x.json", b"{}", NOW)
    assert [op for op, _ in fake.calls] == ["put_object", "put_object"]


def test_without_a_stored_checksum_the_body_is_hashed(s3, fake):
    fake.objects[KEY] = (b"one", {})  # put without ChecksumAlgorithm: head gives no ChecksumSHA256
    assert s3.put_raw(KEY, b"one", NOW) is PutOutcome.EXISTS
    assert fake.calls == [put(KEY, b"one", **LOCKED), head(KEY), ("get_object", {"Bucket": "bucket", "Key": KEY})]
    assert s3.put_raw(KEY, b"two", NOW) is PutOutcome.CONFLICT_STORED


def test_refused_conflict_copy_with_the_same_body_is_exists(s3, fake):
    s3.put_raw(KEY, b"one", NOW)
    s3.put_raw(KEY, b"two", NOW)
    fake.calls.clear()
    copy = f"{KEY}.{sha12(b'two')}"
    assert s3.put_raw(KEY, b"two", NOW) is PutOutcome.EXISTS
    assert fake.calls == [put(KEY, b"two", **LOCKED), head(KEY), put(copy, b"two", **LOCKED), head(copy)]


def test_write_state_is_a_plain_put(s3, fake):
    s3.write_state("ramilevy", {"stopped": True, "alerted": False})
    assert fake.calls == [put("state/ramilevy.json", b'{"alerted": false, "stopped": true}',
                              ContentType="application/json")]


@pytest.mark.parametrize("code", ["NoSuchKey", "404"])
def test_missing_state_reads_as_empty(s3, fake, code):
    fake.errors["get_object"] = [client_error(code, 404, "GetObject")]
    assert s3.read_state("ramilevy") == {}


def test_state_read_error_is_not_hidden(s3, fake):
    fake.errors["get_object"] = [client_error("AccessDenied", 403, "GetObject")]
    with pytest.raises(ClientError, match="AccessDenied"):
        s3.read_state("ramilevy")


def test_stored_names_lists_the_day_through_the_paginator(s3, fake):
    for n in range(5):
        s3.put_raw(raw_key("shufersal", DAY, f"Price{n}.gz"), b"x", NOW)
    assert s3.stored_names("shufersal", DAY) == {f"Price{n}.gz" for n in range(5)}
    assert ("paginate", {"Bucket": "bucket", "Prefix": "raw/chain=shufersal/date=2026-11-01/"}) in fake.calls


def test_no_method_ever_deletes(s3, fake):
    s3.put_raw(KEY, b"one", NOW)
    s3.put_raw(KEY, b"two", NOW)
    s3.put_raw(KEY, b"two", NOW)
    fake.objects[KEY + ".x"] = (b"three", {})
    s3.put_raw(KEY + ".x", b"four", NOW)
    s3.put_record("checks/date=2026-11-01/check-1.json", b"{}", NOW)
    s3.put_record("checks/date=2026-11-01/check-1.json", b"{}", NOW)
    s3.write_state("shufersal", {"stopped": True})
    s3.write_state("shufersal", {})
    s3.read_state("shufersal")
    s3.read_state("carrefour")
    s3.read_raw(KEY)
    s3.read_records("checks/")
    s3.stored_names("shufersal", DAY)
    with pytest.raises(AlreadyStored):
        s3.put_record("checks/date=2026-11-01/check-1.json", b"[]", NOW)
    operations = {op for op, _ in fake.calls}
    assert operations <= {"put_object", "head_object", "get_object", "get_paginator", "paginate"}
    assert not any("delete" in op.lower() for op in operations)


# both stores: the same calls give the same outcomes

def test_first_put_is_stored(store):
    assert store.put_raw(KEY, b"one", NOW) is PutOutcome.STORED
    assert store.read_raw(KEY) == b"one"


def test_same_outcomes_for_a_re_run(store):
    assert store.put_raw(KEY, b"one", NOW) is PutOutcome.STORED
    assert store.put_raw(KEY, b"one", NOW) is PutOutcome.EXISTS
    assert store.put_raw(KEY, b"two", NOW) is PutOutcome.CONFLICT_STORED
    assert store.put_raw(KEY, b"two", NOW) is PutOutcome.EXISTS
    assert store.read_raw(KEY) == b"one"
    assert store.read_raw(f"{KEY}.{sha12(b'two')}") == b"two"
    assert store.stored_names("shufersal", DAY) == {NAME}


def test_conflict_copy_holding_another_body_raises(store):
    copy = f"{KEY}.{sha12(b'two')}"
    store.put_raw(copy, b"three", NOW)  # a different body whose SHA-256 begins as b"two"'s does
    store.put_raw(KEY, b"one", NOW)
    with pytest.raises(AlreadyStored, match="neither is replaced"):
        store.put_raw(KEY, b"two", NOW)
    assert store.read_raw(KEY) == b"one" and store.read_raw(copy) == b"three"


def test_locked_writes_and_plain_state(store):
    store.put_raw(KEY, b"one", NOW)
    store.put_raw(KEY, b"two", NOW)
    store.put_record("manifests/date=2026-11-01/shufersal-1.json", b"{}", NOW)
    store.write_state("shufersal", {"stopped": True})
    for key in (KEY, f"{KEY}.{sha12(b'two')}", "manifests/date=2026-11-01/shufersal-1.json"):
        assert lock_of(store, key) == ("GOVERNANCE", TEN_YEARS)
    assert lock_of(store, "state/shufersal.json") == (None, None)


def test_record_written_again(store):
    key = check_key(DAY, "070000Z-check-cd34")
    store.put_record(key, b'{"a": 1}', NOW)
    store.put_record(key, b'{"a": 1}', NOW)  # a put retried after its answer was lost: quiet
    with pytest.raises(AlreadyStored, match="another record"):
        store.put_record(key, b'{"a": 2}', NOW)
    assert store.read_records("checks/") == [b'{"a": 1}']


@pytest.mark.parametrize("call", ["put_raw", "put_record"])
def test_naive_now_refused(store, call):
    with pytest.raises(ValueError, match="time zone"):
        getattr(store, call)(KEY, b"one", datetime(2026, 11, 1, 6, 30))
    assert store.stored_names("shufersal", DAY) == set()  # nothing written


def test_stored_names_maps_conflict_copies_only(store):
    published = [NAME, "Stores7290027600007-000-20261101-020000.xml", "PromoFull7290027600007-001-030-20261101-030000.gz"]
    for name in published:
        store.put_raw(raw_key("shufersal", DAY, name), b"one", NOW)
    store.put_raw(KEY, b"two", NOW)  # its conflict copy
    others = [f"{NAME}.abc", f"{NAME}.0123456789AB", f"{NAME}.0123456789abc", f"{NAME}.0123456789a",
              f"{NAME}.0123456789abcd"]
    for name in others:
        store.put_raw(raw_key("shufersal", DAY, name), b"one", NOW)
    store.put_raw(raw_key("shufersal", date(2026, 10, 31), "Price-old.gz"), b"one", NOW)
    store.put_raw(raw_key("carrefour", DAY, "Price-other.gz"), b"one", NOW)
    assert store.stored_names("shufersal", DAY) == set(published) | set(others)


def test_stored_names_of_an_empty_day(store):
    assert store.stored_names("shufersal", DAY) == set()


def test_read_raw_of_a_missing_key(store):
    with pytest.raises(KeyError):
        store.read_raw(KEY)


def test_read_records_in_key_order(store):
    for run in ("3", "1", "4", "2"):
        store.put_record(manifest_key(DAY, "shufersal", run), run.encode(), NOW)
    store.put_record(manifest_key(date(2026, 11, 2), "shufersal", "0"), b"0", NOW)
    assert store.read_records("manifests/date=2026-11-01/") == [b"1", b"2", b"3", b"4"]
    assert store.read_records("manifests/date=2026-11-03/") == []


def test_state_round_trip(store):
    assert store.read_state("ramilevy") == {}
    store.write_state("ramilevy", {"stopped": True, "since": "2026-11-01T06:31:00+02:00"})
    assert store.read_state("ramilevy") == {"stopped": True, "since": "2026-11-01T06:31:00+02:00"}
    store.write_state("ramilevy", {})
    assert store.read_state("ramilevy") == {} and store.read_state("osherad") == {}


@pytest.mark.parametrize("make", [lambda: S3Store(FakeS3(), "bucket", retention_days=0),
                                  lambda: MemoryStore(retention_days=0)])
def test_retention_must_be_at_least_a_day(make):
    with pytest.raises(ValueError):
        make()


def test_memory_store_records_lock_settings():
    store = MemoryStore()
    store.put_raw(KEY, b"one", NOW)
    store.write_state("shufersal", {"stopped": True})
    assert store.objects == {KEY: Stored(b"one", "GOVERNANCE", TEN_YEARS),
                             "state/shufersal.json": Stored(b'{"stopped": true}', None, None)}


# S3Store against a real boto3 client: parameter names checked against botocore's S3 model

@pytest.fixture
def stub():
    client = boto3.client("s3", region_name="il-central-1", aws_access_key_id="test", aws_secret_access_key="test")
    with Stubber(client) as stubber:
        yield S3Store(client, "bucket"), stubber
        stubber.assert_no_pending_responses()


def test_real_client_put_and_refusal(stub):
    s3, stubber = stub
    stubber.add_response("put_object", {}, {"Bucket": "bucket", "Key": KEY, "Body": b"one", **LOCKED})
    stubber.add_client_error("put_object", "PreconditionFailed", http_status_code=412,
                             expected_params={"Bucket": "bucket", "Key": KEY, "Body": b"one", **LOCKED})
    stubber.add_response("head_object", {"ChecksumSHA256": b64sha(b"one")},
                         {"Bucket": "bucket", "Key": KEY, "ChecksumMode": "ENABLED"})
    assert s3.put_raw(KEY, b"one", NOW) is PutOutcome.STORED
    assert s3.put_raw(KEY, b"one", NOW) is PutOutcome.EXISTS


def test_real_client_conflict_copy_without_a_checksum(stub):
    s3, stubber = stub
    copy = f"{KEY}.{sha12(b'two')}"
    stubber.add_client_error("put_object", "ConditionalRequestConflict", http_status_code=409)
    stubber.add_response("head_object", {"ContentLength": 3}, {"Bucket": "bucket", "Key": KEY, "ChecksumMode": "ENABLED"})
    stubber.add_response("get_object", {"Body": StreamingBody(io.BytesIO(b"one"), 3)}, {"Bucket": "bucket", "Key": KEY})
    stubber.add_response("put_object", {}, {"Bucket": "bucket", "Key": copy, "Body": b"two", **LOCKED})
    assert s3.put_raw(KEY, b"two", NOW) is PutOutcome.CONFLICT_STORED


def test_real_client_record(stub):
    s3, stubber = stub
    key = manifest_key(DAY, "shufersal", "1")
    stubber.add_response("put_object", {}, {"Bucket": "bucket", "Key": key, "Body": b"{}",
                                            "ContentType": "application/json", **LOCKED})
    s3.put_record(key, b"{}", NOW)


def test_real_client_listing_pages(stub):
    s3, stubber = stub
    prefix = "raw/chain=shufersal/date=2026-11-01/"
    stubber.add_response("list_objects_v2", {"Contents": [{"Key": prefix + "A.gz"}], "IsTruncated": True,
                                             "NextContinuationToken": "t"}, {"Bucket": "bucket", "Prefix": prefix})
    stubber.add_response("list_objects_v2", {"Contents": [{"Key": f"{prefix}A.gz.{sha12(b'x')}"}, {"Key": prefix + "B.xml"}],
                                             "IsTruncated": False},
                         {"Bucket": "bucket", "Prefix": prefix, "ContinuationToken": "t"})
    assert s3.stored_names("shufersal", DAY) == {"A.gz", "B.xml"}


def test_real_client_state(stub):
    s3, stubber = stub
    body = b'{"stopped": true}'
    stubber.add_response("put_object", {}, {"Bucket": "bucket", "Key": "state/osherad.json", "Body": body,
                                            "ContentType": "application/json"})
    stubber.add_response("get_object", {"Body": StreamingBody(io.BytesIO(body), len(body))},
                         {"Bucket": "bucket", "Key": "state/osherad.json"})
    stubber.add_client_error("get_object", "NoSuchKey", http_status_code=404,
                             expected_params={"Bucket": "bucket", "Key": "state/carrefour.json"})
    s3.write_state("osherad", {"stopped": True})
    assert s3.read_state("osherad") == {"stopped": True}
    assert s3.read_state("carrefour") == {}

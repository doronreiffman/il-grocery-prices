"""The archive side of the scheduled build (`basket.archive`): the day's files fetched into the folders the
Mac's build reads, the tables put back plain, the record put back write-once and locked, and nothing deleted.

Most tests run on MemoryArchive; the listing and the plain put also run on S3Archive over test_store's FakeS3.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from basket.archive import (
    TABLE_FILES,
    MemoryArchive,
    S3Archive,
    _Archive,
    record_key,
    table_key,
)
from basket.extract import table_path
from basket.stores import day_store_list
from collector.store import AlreadyStored, check_key, manifest_key, raw_key
from test_store import FakeS3, lock_of

NOW = datetime(2026, 11, 2, 11, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
DAY = date(2026, 11, 2)
SLUG = "ramilevy"
PRICE = "PriceFull7290058140886-001-722-20261102-001016.gz"
PRICE_COPY = PRICE + ".0123456789ab"  # a different body stored beside PRICE
PRICE_OTHER_STORE = "PriceFull7290058140886-001-002-20261102-001500.gz"
PROMO = "PromoFull7290058140886-001-722-20261102-001016.gz"
STORES = "Stores7290058140886-000-20261102-050500.xml"
PRICE_DAY_BEFORE = "PriceFull7290058140886-001-723-20261101-231500.gz"  # in the day's folder, named the day before


def days_back(n: int) -> date:
    return DAY - timedelta(days=n)


def stores_name(day: date, time: str = "050500") -> str:
    return f"Stores7290058140886-000-{day:%Y%m%d}-{time}.xml"


@pytest.fixture
def archive():
    return MemoryArchive()


def stored(archive, day: date, name: str, body: bytes, slug: str = SLUG) -> str:
    key = raw_key(slug, day, name)
    archive.put_raw(key, body, NOW)
    return key


def local_files(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir()} if folder.is_dir() else {}


def test_keys():
    assert table_key(SLUG, DAY, "prices.parquet") == "tables/prices/chain=ramilevy/date=2026-11-02/prices.parquet"
    assert record_key(DAY, "093000Z-basket-ab12") == "basket/date=2026-11-02/basket-093000Z-basket-ab12.json"
    assert TABLE_FILES == ("prices.parquet", "report.json")
    # the table's key is its path under a local folder named tables, as basket.extract writes it
    assert Path(table_key(SLUG, DAY, "prices.parquet")) == table_path(Path("tables"), SLUG, DAY)


def test_day_checked_is_whether_the_day_has_a_check_record(archive):
    assert archive.day_checked(DAY) is False
    archive.put_record(check_key(days_back(1), "090000Z-check-0001"), b"{}", NOW)
    assert archive.day_checked(DAY) is False
    archive.put_record(check_key(DAY, "090000Z-check-0002"), b"{}", NOW)
    assert archive.day_checked(DAY) is True


def test_day_price_file_keys_are_the_days_pricefull_files_only(archive):
    # stored out of key order: the answer is sorted whatever order the listing gives
    stored(archive, DAY, PRICE_OTHER_STORE, b"other store")
    stored(archive, DAY, PRICE_COPY, b"changed")
    stored(archive, DAY, PROMO, b"promo")
    stored(archive, DAY, STORES, b"stores")
    stored(archive, DAY, PRICE_DAY_BEFORE, b"named the day before")
    stored(archive, DAY, PRICE, b"first")
    stored(archive, days_back(1), PRICE_DAY_BEFORE, b"the day before's folder")
    stored(archive, DAY, PRICE, b"another chain's", slug="shufersal")
    assert archive.day_price_file_keys(SLUG, DAY) == [raw_key(SLUG, DAY, PRICE_OTHER_STORE),
                                                      raw_key(SLUG, DAY, PRICE), raw_key(SLUG, DAY, PRICE_COPY)]


def test_fetch_raw_writes_under_the_days_folder_and_returns_stored_names(archive, tmp_path):
    assert archive.fetch_raw(SLUG, DAY, tmp_path / "empty") == []  # a day with no files: an empty folder
    assert local_files(tmp_path / "empty" / "chain=ramilevy" / "date=2026-11-02") == {}
    stored(archive, DAY, PRICE, b"first")
    stored(archive, DAY, PRICE_COPY, b"changed")
    stored(archive, DAY, PROMO, b"promo")
    stored(archive, DAY, PRICE_OTHER_STORE, b"other store")
    raw_dir = tmp_path / "raw"
    assert archive.fetch_raw(SLUG, DAY, raw_dir) == [PRICE_OTHER_STORE, PRICE, PRICE_COPY]
    assert local_files(raw_dir / "chain=ramilevy" / "date=2026-11-02") == {
        PRICE: b"first", PRICE_COPY: b"changed", PRICE_OTHER_STORE: b"other store"}
    assert [path.name for path in raw_dir.iterdir()] == ["chain=ramilevy"]


def test_fetch_store_list_takes_the_day_then_looks_back(archive, tmp_path):
    raw_dir = tmp_path / "raw"
    stored(archive, DAY, stores_name(days_back(1)), b"in the day's folder, named the day before")
    stored(archive, DAY, PRICE, b"a price file")
    stored(archive, days_back(3), stores_name(days_back(3), "020000"), b"earlier that day")
    stored(archive, days_back(3), stores_name(days_back(3), "050500"), b"three days back")
    stored(archive, days_back(5), stores_name(days_back(5)), b"five days back")
    stored(archive, DAY + timedelta(days=1), stores_name(DAY + timedelta(days=1)), b"the day after")
    assert archive.fetch_store_list(SLUG, DAY, raw_dir) == days_back(3)
    assert [path.name for path in (raw_dir / "chain=ramilevy").iterdir()] == ["date=2026-10-30"]
    assert local_files(raw_dir / "chain=ramilevy" / "date=2026-10-30") == {
        stores_name(days_back(3), "050500"): b"three days back"}
    assert day_store_list(raw_dir, SLUG, DAY) == (b"three days back", days_back(3))
    # the day's own list, once there, comes first
    stored(archive, DAY, stores_name(DAY), b"the day's")
    assert archive.fetch_store_list(SLUG, DAY, tmp_path / "again") == DAY
    assert day_store_list(tmp_path / "again", SLUG, DAY) == (b"the day's", DAY)


def test_fetch_store_list_stops_after_fourteen_days(archive, tmp_path):
    stored(archive, days_back(14), stores_name(days_back(14)), b"fourteen days back")
    assert archive.fetch_store_list(SLUG, DAY, tmp_path / "raw") is None
    assert not (tmp_path / "raw").exists()
    stored(archive, days_back(13), stores_name(days_back(13)), b"thirteen days back")
    assert archive.fetch_store_list(SLUG, DAY, tmp_path / "raw") == days_back(13)
    assert day_store_list(tmp_path / "raw", SLUG, DAY) == (b"thirteen days back", days_back(13))


def test_fetch_store_list_reads_a_name_in_any_case_as_the_mac_does(archive, tmp_path):
    """The Mac's build reads a published name in any case (`basket.stores.is_store_list`); an S3 prefix matches in
    one case only, so the fetch lists the day's whole folder and reads each name as the Mac does."""
    stored(archive, DAY, stores_name(DAY).lower(), b"named in lower case")
    stored(archive, DAY, PRICE, b"a price file")
    assert archive.fetch_store_list(SLUG, DAY, tmp_path / "raw") == DAY
    assert day_store_list(tmp_path / "raw", SLUG, DAY) == (b"named in lower case", DAY)


def test_fetch_manifests_takes_the_chains_only(archive, tmp_path):
    archive.put_record(manifest_key(DAY, SLUG, "063000Z-main-ab12"), b'{"run": 1}', NOW)
    archive.put_record(manifest_key(DAY, SLUG, "093000Z-retry-cd34"), b'{"run": 2}', NOW)
    archive.put_record(manifest_key(DAY, "shufersal", "063100Z-main-ef56"), b'{"run": 3}', NOW)
    archive.put_record(manifest_key(days_back(1), SLUG, "063000Z-main-0001"), b'{"run": 4}', NOW)
    manifests_dir = tmp_path / "manifests"
    assert archive.fetch_manifests(SLUG, DAY, manifests_dir) == 2
    assert local_files(manifests_dir / "date=2026-11-02") == {
        "ramilevy-063000Z-main-ab12.json": b'{"run": 1}', "ramilevy-093000Z-retry-cd34.json": b'{"run": 2}'}
    assert [path.name for path in manifests_dir.iterdir()] == ["date=2026-11-02"]


def test_fetch_table_needs_both_files(archive, tmp_path):
    folder = table_path(tmp_path / "tables", SLUG, DAY).parent
    archive._put_plain(table_key(SLUG, DAY, "prices.parquet"), b"PAR1", "application/vnd.apache.parquet")
    assert archive.fetch_table(SLUG, DAY, tmp_path / "tables") is False
    assert not (tmp_path / "tables").exists()

    alone = MemoryArchive()
    alone._put_plain(table_key(SLUG, DAY, "report.json"), b"{}", "application/json")
    assert alone.fetch_table(SLUG, DAY, tmp_path / "tables") is False
    assert not (tmp_path / "tables").exists()

    archive._put_plain(table_key(SLUG, DAY, "report.json"), b'{"rows": 1}', "application/json")
    assert archive.fetch_table(SLUG, DAY, tmp_path / "tables") is True
    assert local_files(folder) == {"prices.parquet": b"PAR1", "report.json": b'{"rows": 1}'}


def test_put_table_puts_both_files_plain(tmp_path):
    fake = FakeS3()
    archive = S3Archive(fake, "bucket")
    folder = table_path(tmp_path, SLUG, DAY).parent
    folder.mkdir(parents=True)
    (folder / "prices.parquet").write_bytes(b"PAR1")
    (folder / "report.json").write_bytes(b'{"rows": 1}')
    keys = archive.put_table(SLUG, DAY, tmp_path)
    assert keys == [table_key(SLUG, DAY, "prices.parquet"), table_key(SLUG, DAY, "report.json")]
    assert fake.calls == [
        ("put_object", {"Bucket": "bucket", "Key": keys[0], "Body": b"PAR1",
                        "ContentType": "application/vnd.apache.parquet"}),
        ("put_object", {"Bucket": "bucket", "Key": keys[1], "Body": b'{"rows": 1}', "ContentType": "application/json"}),
    ]
    assert not any("ObjectLockMode" in kwargs or "IfNoneMatch" in kwargs for _, kwargs in fake.calls)
    # a re-run of the extraction replaces the table
    (folder / "prices.parquet").write_bytes(b"PAR2")
    archive.put_table(SLUG, DAY, tmp_path)
    assert fake.objects[keys[0]][0] == b"PAR2"


def test_put_basket_record_is_write_once_and_locked(archive, tmp_path):
    path = tmp_path / "record.json"  # the key comes from the record's day and run id, not from the file's name
    body = json.dumps({"day": "2026-11-02", "run_id": "093000Z-basket-ab12", "headline": "ראשון"},
                      ensure_ascii=False, sort_keys=True).encode()
    path.write_bytes(body)
    key = archive.put_basket_record(path, NOW)
    assert key == record_key(DAY, "093000Z-basket-ab12")
    assert archive.read_raw(key) == body
    assert lock_of(archive, key) == ("GOVERNANCE", NOW + timedelta(days=3650))
    assert archive.put_basket_record(path, NOW) == key  # the same put retried
    path.write_bytes(body + b"\n")
    with pytest.raises(AlreadyStored):
        archive.put_basket_record(path, NOW)
    assert archive.read_raw(key) == body


def test_s3_archive_lists_through_the_paginator():
    fake = FakeS3(page_size=2)
    archive = S3Archive(fake, "bucket")
    keys = [stored(archive, DAY, name, b"gz") for name in (PRICE, PRICE_OTHER_STORE, PRICE_COPY)]
    fake.calls.clear()
    assert archive.day_price_file_keys(SLUG, DAY) == sorted(keys)
    assert ("paginate", {"Bucket": "bucket", "Prefix": "raw/chain=ramilevy/date=2026-11-02/"}) in fake.calls


def test_no_method_ever_deletes(tmp_path):
    fake = FakeS3(page_size=2)
    archive = S3Archive(fake, "bucket")
    stored(archive, DAY, PRICE, b"first")
    stored(archive, DAY, PRICE_COPY, b"changed")
    stored(archive, days_back(2), stores_name(days_back(2)), b"stores")
    archive.put_record(manifest_key(DAY, SLUG, "063000Z-main-ab12"), b"{}", NOW)
    archive.put_record(check_key(DAY, "090000Z-check-0001"), b"{}", NOW)
    tables = table_path(tmp_path / "out", SLUG, DAY).parent
    tables.mkdir(parents=True)
    (tables / "prices.parquet").write_bytes(b"PAR1")
    (tables / "report.json").write_bytes(b"{}")
    record = tmp_path / "record.json"
    record.write_text(json.dumps({"day": "2026-11-02", "run_id": "093000Z-basket-ab12"}))

    called = set()

    def call(method: str, *args):
        called.add(method)
        return getattr(archive, method)(*args)

    call("day_checked", DAY)
    call("day_price_file_keys", SLUG, DAY)
    call("fetch_raw", SLUG, DAY, tmp_path / "raw")
    call("fetch_store_list", SLUG, DAY, tmp_path / "raw")
    call("fetch_manifests", SLUG, DAY, tmp_path / "manifests")
    call("fetch_table", SLUG, DAY, tmp_path / "in")
    call("put_table", SLUG, DAY, tmp_path / "out")
    call("put_table", SLUG, DAY, tmp_path / "out")
    call("fetch_table", SLUG, DAY, tmp_path / "in")
    call("put_basket_record", record, NOW)
    call("put_basket_record", record, NOW)
    record.write_text(json.dumps({"day": "2026-11-02", "run_id": "093000Z-basket-ab12", "other": 1}))
    with pytest.raises(AlreadyStored):
        call("put_basket_record", record, NOW)
    # every method _Archive defines was run above
    assert called == {name for name in vars(_Archive) if not name.startswith("_")}
    operations = {op for op, _ in fake.calls}
    assert operations <= {"put_object", "head_object", "get_object", "get_paginator", "paginate"}
    assert not any("delete" in op.lower() for op in operations)

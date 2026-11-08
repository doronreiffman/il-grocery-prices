"""The archive side of the scheduled build (`basket.archive`): the day's files fetched into the folders the
Mac's build reads, the tables put back plain, the record put back write-once and locked, and nothing deleted.

Most tests run on MemoryArchive; the listing and the plain put also run on S3Archive over test_store's FakeS3.
"""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from basket.archive import (
    TABLE_FILES,
    TABLES,
    MemoryArchive,
    S3Archive,
    _Archive,
    kind_key,
    record_key,
    table_key,
)
from basket.extract import table_path
from shopper.freeze import archive_key, scores_archive_key
from shopper.history import READ_DAYS, covered_path
from shopper.items import items_path, texts_path
from shopper.promos import promotions_path
from shopper.score import ColumnSummary, DaySummary, summary_json, summary_path
from basket.stores import day_store_list
from collector.store import AlreadyStored, check_key, manifest_key, raw_key
from test_store import FakeS3, client_error, lock_of

NOW = datetime(2026, 11, 2, 11, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
DAY = date(2026, 11, 2)
SLUG = "ramilevy"
PRICE = "PriceFull7290058140886-001-722-20261102-001016.gz"
PRICE_COPY = PRICE + ".0123456789ab"  # a different body stored beside PRICE
PRICE_OTHER_STORE = "PriceFull7290058140886-001-002-20261102-001500.gz"
PROMO = "PromoFull7290058140886-001-722-20261102-001016.gz"
PROMO_LOWER = "promofull7290058140886-001-002-20261102-001500.gz"  # the Mac's parse reads a name in any case
STORES = "Stores7290058140886-000-20261102-050500.xml"
PRICE_DAY_BEFORE = "PriceFull7290058140886-001-723-20261101-231500.gz"  # in the day's folder, named the day before
PARQUET, JSON = "application/vnd.apache.parquet", "application/json"


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


def test_day_file_keys_of_pricefull_are_the_days_pricefull_files_only(archive):
    # stored out of key order: the answer is sorted whatever order the listing gives
    stored(archive, DAY, PRICE_OTHER_STORE, b"other store")
    stored(archive, DAY, PRICE_COPY, b"changed")
    stored(archive, DAY, PROMO, b"promo")
    stored(archive, DAY, STORES, b"stores")
    stored(archive, DAY, PRICE_DAY_BEFORE, b"named the day before")
    stored(archive, DAY, PRICE, b"first")
    stored(archive, days_back(1), PRICE_DAY_BEFORE, b"the day before's folder")
    stored(archive, DAY, PRICE, b"another chain's", slug="shufersal")
    assert archive.day_file_keys(SLUG, DAY, "PriceFull") == [raw_key(SLUG, DAY, PRICE_OTHER_STORE),
                                                             raw_key(SLUG, DAY, PRICE), raw_key(SLUG, DAY, PRICE_COPY)]


def test_day_file_keys_of_each_kind(archive):
    """The day's files of the kind asked for, as `basket.extract.day_files` reads them: a lower-case name read in any
    case, a conflict copy by its published name, sorted; of another kind or another day, none."""
    promo_copy = PROMO + ".0123456789ab"
    for name in (PROMO_LOWER, promo_copy, PRICE, STORES, PROMO, "PromoFull7290058140886-001-723-20261101-231500.gz"):
        stored(archive, DAY, name, b"body")
    assert archive.day_file_keys(SLUG, DAY, "PromoFull") == [raw_key(SLUG, DAY, PROMO), raw_key(SLUG, DAY, promo_copy),
                                                             raw_key(SLUG, DAY, PROMO_LOWER)]
    assert archive.day_file_keys(SLUG, DAY, "PriceFull") == [raw_key(SLUG, DAY, PRICE)]
    assert archive.day_file_keys(SLUG, DAY, "Stores") == [raw_key(SLUG, DAY, STORES)]


def test_fetch_raw_takes_each_kind_asked_for_from_one_listing(archive, tmp_path):
    stored(archive, DAY, PRICE, b"price")
    stored(archive, DAY, PROMO, b"promo")
    stored(archive, DAY, PROMO_LOWER, b"lower-case promo")
    stored(archive, DAY, STORES, b"stores")
    reads = []
    listing = archive._keys
    archive._keys = lambda prefix: reads.append(prefix) or listing(prefix)
    raw_dir = tmp_path / "raw"
    assert archive.fetch_raw(SLUG, DAY, raw_dir, kinds=("PriceFull", "PromoFull")) == [PRICE, PROMO, PROMO_LOWER]
    assert local_files(raw_dir / "chain=ramilevy" / "date=2026-11-02") == {
        PRICE: b"price", PROMO: b"promo", PROMO_LOWER: b"lower-case promo"}
    assert reads == [raw_key(SLUG, DAY, "")]  # one listing of the day's folder, whatever the kinds


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


def test_put_tables_puts_the_prices_files_plain(tmp_path):
    fake = FakeS3()
    archive = S3Archive(fake, "bucket")
    folder = table_path(tmp_path, SLUG, DAY).parent
    folder.mkdir(parents=True)
    (folder / "prices.parquet").write_bytes(b"PAR1")
    (folder / "report.json").write_bytes(b'{"rows": 1}')
    keys = archive.put_tables(SLUG, DAY, tmp_path)
    assert keys == [table_key(SLUG, DAY, "prices.parquet"), table_key(SLUG, DAY, "report.json")]
    assert fake.calls == [
        ("put_object", {"Bucket": "bucket", "Key": keys[0], "Body": b"PAR1",
                        "ContentType": "application/vnd.apache.parquet"}),
        ("put_object", {"Bucket": "bucket", "Key": keys[1], "Body": b'{"rows": 1}', "ContentType": "application/json"}),
    ]
    assert not any("ObjectLockMode" in kwargs or "IfNoneMatch" in kwargs for _, kwargs in fake.calls)
    # a re-run of the extraction replaces the table
    (folder / "prices.parquet").write_bytes(b"PAR2")
    archive.put_tables(SLUG, DAY, tmp_path)
    assert fake.objects[keys[0]][0] == b"PAR2"


def test_kind_key_names_each_kind():
    """A derived table's key, its kind's folder first; with no chain (the covered registry, the scored summaries),
    no chain segment (the second pre-flight's S4). Each key is its file's path under a local folder named tables."""
    assert TABLES == {"prices": ("prices.parquet", "report.json"),
                      "promotions": ("promotions.parquet", "texts.parquet", "report.json"),
                      "items": ("items.parquet", "report.json")}
    assert TABLE_FILES == TABLES["prices"]
    assert kind_key("promotions", SLUG, DAY, "texts.parquet") == (
        "tables/promotions/chain=ramilevy/date=2026-11-02/texts.parquet")
    assert kind_key("items", "shufersal", DAY, "items.parquet") == (
        "tables/items/chain=shufersal/date=2026-11-02/items.parquet")
    assert kind_key("covered", None, DAY, "covered.parquet") == "tables/covered/date=2026-11-02/covered.parquet"
    assert kind_key("prices", SLUG, DAY, "report.json") == table_key(SLUG, DAY, "report.json")
    assert Path(kind_key("promotions", SLUG, DAY, "promotions.parquet")) == promotions_path(Path("tables"), SLUG, DAY)
    assert Path(kind_key("items", SLUG, DAY, "items.parquet")) == items_path(Path("tables"), SLUG, DAY)
    assert Path(kind_key("promotions", SLUG, DAY, "texts.parquet")) == texts_path(Path("tables"), SLUG, DAY)
    assert Path(kind_key("covered", None, DAY, "covered.parquet")) == covered_path(Path("tables"), DAY)


def test_put_tables_puts_the_files_present(tmp_path):
    """Each kind's files that are there, plain, in TABLES' order: after a format change the promotions folder holds
    its report alone, and only that goes up (the first pre-flight's S7); a kind with no folder puts nothing."""
    fake = FakeS3()
    archive = S3Archive(fake, "bucket")
    files = {table_path(tmp_path, SLUG, DAY): b"PAR1", table_path(tmp_path, SLUG, DAY).with_name("report.json"): b"{}",
             promotions_path(tmp_path, SLUG, DAY).with_name("report.json"): b'{"promotions_error": "ramilevy: x"}',
             items_path(tmp_path, SLUG, DAY): b"PAR3", items_path(tmp_path, SLUG, DAY).with_name("report.json"): b"{}"}
    for path, body in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    keys = archive.put_tables(SLUG, DAY, tmp_path)
    assert keys == [table_key(SLUG, DAY, "prices.parquet"), table_key(SLUG, DAY, "report.json"),
                    kind_key("promotions", SLUG, DAY, "report.json"), kind_key("items", SLUG, DAY, "items.parquet"),
                    kind_key("items", SLUG, DAY, "report.json")]
    parquet, plain_json = "application/vnd.apache.parquet", "application/json"
    assert [(kwargs["Key"], kwargs["Body"], kwargs["ContentType"]) for _, kwargs in fake.calls] == [
        (keys[0], b"PAR1", parquet), (keys[1], b"{}", plain_json),
        (keys[2], b'{"promotions_error": "ramilevy: x"}', plain_json), (keys[3], b"PAR3", parquet),
        (keys[4], b"{}", plain_json)]
    assert not any("ObjectLockMode" in kwargs or "IfNoneMatch" in kwargs for _, kwargs in fake.calls)
    # once the promotions were read, its three files go up, the texts table among them
    promotions_path(tmp_path, SLUG, DAY).write_bytes(b"PAR2")
    texts_path(tmp_path, SLUG, DAY).write_bytes(b"PAR4")
    fake.calls.clear()
    assert archive.put_tables(SLUG, DAY, tmp_path)[2:5] == [kind_key("promotions", SLUG, DAY, name)
                                                           for name in TABLES["promotions"]]
    assert fake.objects[kind_key("promotions", SLUG, DAY, "texts.parquet")][0] == b"PAR4"
    assert MemoryArchive().put_tables(SLUG, DAY, tmp_path / "nothing") == []


def put_items(archive, slug: str, day: date, body: bytes = b"PAR1") -> None:
    archive._put_plain(kind_key("items", slug, day, "items.parquet"), body, PARQUET)
    archive._put_plain(kind_key("items", slug, day, "report.json"), b'{"day": "%s"}' % day.isoformat().encode(), JSON)


def tree(folder: Path) -> dict[str, bytes]:
    """Every file under `folder`, by its path there."""
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob("*"))
            if path.is_file()} if folder.is_dir() else {}


def test_fetch_items_needs_both_files(archive, tmp_path):
    tables = tmp_path / "tables"
    archive._put_plain(kind_key("items", SLUG, DAY, "items.parquet"), b"PAR1", PARQUET)
    assert archive.fetch_items(SLUG, DAY, tables) is False
    assert not tables.exists()

    alone = MemoryArchive()
    alone._put_plain(kind_key("items", SLUG, DAY, "report.json"), b"{}", JSON)
    assert alone.fetch_items(SLUG, DAY, tables) is False
    assert not tables.exists()

    archive._put_plain(kind_key("items", SLUG, DAY, "report.json"), b'{"slug": "ramilevy"}', JSON)
    assert archive.fetch_items(SLUG, DAY, tables) is True
    assert local_files(items_path(tables, SLUG, DAY).parent) == {"items.parquet": b"PAR1",
                                                                 "report.json": b'{"slug": "ramilevy"}'}


def test_fetch_history_takes_each_chains_items_tables_of_the_day_and_the_ninety_before(archive, tmp_path):
    tables = tmp_path / "tables"
    for back in (-1, 0, 1, READ_DAYS, READ_DAYS + 1):   # day + 1, the day, day - 1, day - 90, day - 91
        put_items(archive, SLUG, DAY - timedelta(days=back), b"PAR %d" % back)
    put_items(archive, "shufersal", DAY)
    put_items(archive, "yochananof", days_back(READ_DAYS))
    archive._put_plain(kind_key("items", "osherad", days_back(5), "report.json"), b"{}", JSON)   # its table missing
    archive._put_plain(kind_key("prices", "carrefour", days_back(5), "report.json"), b"{}", JSON)   # another kind
    keys = archive.fetch_history(DAY, tables)
    read = [("ramilevy", DAY), ("ramilevy", days_back(1)), ("ramilevy", days_back(READ_DAYS)), ("shufersal", DAY),
            ("yochananof", days_back(READ_DAYS))]
    assert keys == sorted(kind_key("items", slug, day, "items.parquet") for slug, day in read)
    assert set(tree(tables)) == {kind_key("items", slug, day, name).removeprefix("tables/")
                                 for slug, day in read for name in TABLES["items"]}
    assert items_path(tables, SLUG, days_back(READ_DAYS)).read_bytes() == b"PAR %d" % READ_DAYS
    assert MemoryArchive().fetch_history(DAY, tmp_path / "none") == []
    assert not (tmp_path / "none").exists()


def test_fetch_covered_takes_the_latest_registry_before_the_day(archive, tmp_path):
    def put(day: date) -> None:
        archive._put_plain(kind_key("covered", None, day, "covered.parquet"), day.isoformat().encode(), PARQUET)

    tables = tmp_path / "tables"
    assert archive.fetch_covered(DAY, tables) is None
    assert not tables.exists()
    for day in (days_back(9), days_back(3), DAY, DAY + timedelta(days=2)):
        put(day)
    archive._put_plain(kind_key("covered", None, days_back(1), "notes.json"), b"{}", JSON)   # not a registry
    archive._put_plain("tables/covered/date=20261101/covered.parquet", b"x", PARQUET)   # not a key the code writes
    archive._put_plain("tables/covered/date=soon/covered.parquet", b"x", PARQUET)   # nor a day
    assert archive.fetch_covered(DAY, tables) == days_back(3)
    assert tree(tables) == {"covered/date=2026-10-30/covered.parquet": b"2026-10-30"}
    assert covered_path(tables, days_back(3)).read_bytes() == b"2026-10-30"
    put(days_back(1))
    assert archive.fetch_covered(DAY, tmp_path / "later") == days_back(1)
    assert MemoryArchive().fetch_covered(DAY + timedelta(days=1), tmp_path / "none") is None


def test_put_covered_puts_the_days_registry_plain(tmp_path):
    fake = FakeS3()
    archive = S3Archive(fake, "bucket")
    path = covered_path(tmp_path, DAY)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"PAR1")
    key = archive.put_covered(DAY, tmp_path)
    assert key == "tables/covered/date=2026-11-02/covered.parquet"
    assert fake.calls == [("put_object", {"Bucket": "bucket", "Key": key, "Body": b"PAR1", "ContentType": PARQUET})]
    path.write_bytes(b"PAR2")   # a re-run of the day replaces it
    archive.put_covered(DAY, tmp_path)
    assert fake.objects[key][0] == b"PAR2"


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


# The daily freeze's keys: forecasts/date=<day>/forecasts.csv.gz, write-once and locked (F6, Task 12)

GZIP = "application/gzip"
FROZEN = b"\x1f\x8b frozen forecasts"   # the archive never reads a body; the freezer does


class ClockedS3(FakeS3):
    """FakeS3 whose head_object also gives each key's LastModified: `now` as it was when the key was put."""

    def __init__(self, now: datetime, **kwargs):
        super().__init__(**kwargs)
        self.now = now
        self.modified: dict[str, datetime] = {}

    def put_object(self, **kwargs):
        answer = super().put_object(**kwargs)
        self.modified[kwargs["Key"]] = self.now
        return answer

    def head_object(self, **kwargs):
        answer = super().head_object(**kwargs)
        return {**answer, "LastModified": self.modified[kwargs["Key"]]}


@pytest.fixture(params=["s3", "memory"])
def frozen_archive(request):
    return S3Archive(ClockedS3(NOW, page_size=2), "bucket") if request.param == "s3" else MemoryArchive()


def test_put_frozen_is_write_once_and_locked(frozen_archive):
    key = frozen_archive.put_frozen(DAY, FROZEN, NOW)
    assert key == archive_key(DAY) == "forecasts/date=2026-11-02/forecasts.csv.gz"
    assert frozen_archive.read_raw(key) == FROZEN
    assert lock_of(frozen_archive, key) == ("GOVERNANCE", NOW + timedelta(days=3650))
    assert frozen_archive.put_frozen(DAY, FROZEN, NOW) == key              # the same put retried
    with pytest.raises(AlreadyStored):
        frozen_archive.put_frozen(DAY, FROZEN + b"x", NOW)
    assert frozen_archive.read_raw(key) == FROZEN
    assert frozen_archive.frozen_days() == [DAY]                           # no second file beside it


def test_put_frozen_sends_the_lock_and_the_gzip_content_type():
    fake = ClockedS3(NOW)
    S3Archive(fake, "bucket").put_frozen(DAY, FROZEN, NOW)
    assert fake.calls == [("put_object", {
        "Bucket": "bucket", "Key": archive_key(DAY), "Body": FROZEN, "ContentType": GZIP, "IfNoneMatch": "*",
        "ObjectLockMode": "GOVERNANCE", "ObjectLockRetainUntilDate": NOW + timedelta(days=3650),
        "ChecksumAlgorithm": "SHA256"})]


def test_a_put_frozen_without_a_time_zone_is_refused(frozen_archive):
    with pytest.raises(ValueError, match="time zone"):
        frozen_archive.put_frozen(DAY, FROZEN, datetime(2026, 11, 2, 11, 30))
    assert frozen_archive.frozen_days() == []


def test_frozen_days_are_the_days_with_a_forecasts_file(frozen_archive):
    for day in (days_back(1), days_back(3), DAY):                          # out of order
        frozen_archive.put_frozen(day, FROZEN, NOW)
    frozen_archive.put_record(archive_key(days_back(5)) + ".0123456789ab", b"x", NOW)   # a key the code never writes
    frozen_archive.put_record("forecasts/date=soon/forecasts.csv.gz", b"x", NOW)
    frozen_archive.put_record("forecasts/ledger.csv", b"x", NOW)
    frozen_archive.put_record("scores/date=2026-10-20/scores.csv.gz", b"x", NOW)
    assert frozen_archive.frozen_days() == [days_back(3), days_back(1), DAY]


def test_frozen_days_of_an_empty_archive(frozen_archive):
    assert frozen_archive.frozen_days() == []


def test_a_memory_archives_s3_time_is_the_puts_now_unless_a_clock_is_given():
    archive = MemoryArchive()
    stamp = datetime(2026, 11, 2, 11, 30, 5, tzinfo=timezone.utc)
    archive.put_frozen(DAY, FROZEN, stamp)
    assert archive.last_modified(archive_key(DAY)) == stamp
    archive.put_record(check_key(DAY, "x"), b"{}", stamp + timedelta(hours=1))
    assert archive.last_modified(check_key(DAY, "x")) == stamp + timedelta(hours=1)
    assert archive.last_modified(archive_key(days_back(1))) is None        # nothing stored there
    clocked = MemoryArchive(s3_clock=lambda: stamp + timedelta(days=1))
    clocked.put_frozen(DAY, FROZEN, stamp)
    clocked.put_record(check_key(DAY, "x"), b"{}", stamp)
    clocked.put_raw(raw_key(SLUG, DAY, PRICE), b"gz", stamp)
    assert [clocked.last_modified(key) for key in (archive_key(DAY), check_key(DAY, "x"), raw_key(SLUG, DAY, PRICE))] == \
        [stamp + timedelta(days=1)] * 3


def test_a_memory_archive_times_a_plain_put_by_its_clock(tmp_path):
    stamp = datetime(2026, 11, 2, 11, 30, tzinfo=timezone.utc)
    clocked = MemoryArchive(s3_clock=lambda: stamp)
    path = covered_path(tmp_path, DAY)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"PAR1")
    key = clocked.put_covered(DAY, tmp_path)
    assert clocked.last_modified(key) == stamp
    assert MemoryArchive().last_modified(key) is None                      # no clock, no `now` to take


def test_a_memory_archive_keeps_the_first_time_of_a_key_it_refused_to_write():
    archive = MemoryArchive()
    first = datetime(2026, 11, 2, 11, 30, tzinfo=timezone.utc)
    archive.put_frozen(DAY, FROZEN, first)
    archive.put_frozen(DAY, FROZEN, first + timedelta(hours=3))            # a retry meets the first write
    assert archive.last_modified(archive_key(DAY)) == first


def test_s3_last_modified_is_what_head_object_says():
    stamp = datetime(2026, 11, 2, 8, 30, 1, tzinfo=timezone.utc)
    fake = ClockedS3(stamp)
    archive = S3Archive(fake, "bucket")
    key = archive.put_frozen(DAY, FROZEN, NOW)
    fake.calls.clear()
    assert archive.last_modified(key) == stamp
    assert fake.calls == [("head_object", {"Bucket": "bucket", "Key": key})]
    assert archive.last_modified(archive_key(days_back(1))) is None        # S3's bare 404 is a missing key


def test_s3_last_modified_does_not_hide_other_errors():
    fake = ClockedS3(NOW)
    fake.errors["head_object"] = [client_error("AccessDenied", 403, "HeadObject")]
    with pytest.raises(ClientError):
        S3Archive(fake, "bucket").last_modified(archive_key(DAY))


def test_s3_last_modified_against_the_real_clients_model():
    client = boto3.client("s3", region_name="il-central-1", aws_access_key_id="test", aws_secret_access_key="test")
    stamp = datetime(2026, 11, 2, 8, 30, 1, tzinfo=timezone.utc)
    with Stubber(client) as stubber:
        key = archive_key(DAY)
        stubber.add_response("head_object", {"LastModified": stamp}, {"Bucket": "bucket", "Key": key})
        stubber.add_client_error("head_object", "404", http_status_code=404,
                                 expected_params={"Bucket": "bucket", "Key": key})
        archive = S3Archive(client, "bucket")
        assert archive.last_modified(key) == stamp
        assert archive.last_modified(key) is None
        stubber.assert_no_pending_responses()


def test_s3_archive_lists_through_the_paginator():
    fake = FakeS3(page_size=2)
    archive = S3Archive(fake, "bucket")
    keys = [stored(archive, DAY, name, b"gz") for name in (PRICE, PRICE_OTHER_STORE, PRICE_COPY)]
    fake.calls.clear()
    assert archive.day_file_keys(SLUG, DAY, "PriceFull") == sorted(keys)
    assert ("paginate", {"Bucket": "bucket", "Prefix": "raw/chain=ramilevy/date=2026-11-02/"}) in fake.calls


# Scoring: scores/date=<day>/scores.csv.gz write-once and locked, and each day's summary plain (F7, Task 13)

SCORES = b"\x1f\x8b scores"   # the archive never reads a scores body; the freezer does


def test_scores_are_put_write_once_and_locked(frozen_archive):
    key = frozen_archive.put_scores(DAY, SCORES, NOW)
    assert key == scores_archive_key(DAY) == "scores/date=2026-11-02/scores.csv.gz"
    assert frozen_archive.read_raw(key) == SCORES
    assert lock_of(frozen_archive, key) == ("GOVERNANCE", NOW + timedelta(days=3650))
    assert frozen_archive.put_scores(DAY, SCORES, NOW) == key               # the same put retried
    with pytest.raises(AlreadyStored):
        frozen_archive.put_scores(DAY, SCORES + b"x", NOW)
    assert frozen_archive.read_raw(key) == SCORES
    assert frozen_archive._keys("scores/") == [key]                         # no second file beside it
    with pytest.raises(ValueError, match="time zone"):
        frozen_archive.put_scores(days_back(1), SCORES, datetime(2026, 11, 2, 11, 30))


def test_put_scores_sends_the_lock_and_the_gzip_content_type():
    fake = ClockedS3(NOW)
    S3Archive(fake, "bucket").put_scores(DAY, SCORES, NOW)
    assert fake.calls == [("put_object", {
        "Bucket": "bucket", "Key": scores_archive_key(DAY), "Body": SCORES, "ContentType": GZIP, "IfNoneMatch": "*",
        "ObjectLockMode": "GOVERNANCE", "ObjectLockRetainUntilDate": NOW + timedelta(days=3650),
        "ChecksumAlgorithm": "SHA256"})]


def day_summary(day: date, scored: int = 1) -> DaySummary:
    column = ColumnSummary(forecasts=scored + 1, scored=scored, unscored=1, outcome_1=1, sq_model=Decimal("0.0625"),
                           sq_a=Decimal("0.25"), sq_b=Decimal("0.5625"),
                           bins=tuple((1, Decimal("0.75"), 1) if i == 7 else (0, Decimal(0), 0) for i in range(10)))
    return DaySummary(day=day, frozen_at=datetime(2026, 10, 19, 10, 40, 5, tzinfo=timezone.utc), on_time=True,
                      model_version="1", target_version="1", by_column={"shufersal-deal": column})


def write_summary(tables: Path, summary: DaySummary) -> bytes:
    path = summary_path(tables, summary.day)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = summary_json(summary)
    path.write_bytes(body)
    return body


def test_put_summary_puts_the_days_summary_plain(tmp_path):
    fake = FakeS3()
    archive = S3Archive(fake, "bucket")
    body = write_summary(tmp_path, day_summary(days_back(14)))
    key = archive.put_summary(days_back(14), tmp_path)
    assert key == kind_key("scored", None, days_back(14), "summary.json") == \
        "tables/scored/date=2026-10-19/summary.json"
    assert Path(key) == summary_path(Path("tables"), days_back(14))       # its path under the work folder's tables
    assert fake.calls == [("put_object", {"Bucket": "bucket", "Key": key, "Body": body, "ContentType": JSON})]
    again = write_summary(tmp_path, day_summary(days_back(14), scored=2))  # derived: a re-run replaces it
    archive.put_summary(days_back(14), tmp_path)
    assert fake.objects[key][0] == again


def test_scored_days_are_the_days_with_a_summary(frozen_archive, tmp_path):
    for day in (days_back(1), days_back(3), DAY):                           # out of order
        write_summary(tmp_path, day_summary(day))
        frozen_archive.put_summary(day, tmp_path)
    # a scores file whose summary was never put (a run stopped between the two): not scored, so due again
    frozen_archive.put_scores(days_back(5), SCORES, NOW)
    frozen_archive._put_plain("tables/scored/date=soon/summary.json", b"{}", JSON)
    frozen_archive._put_plain(kind_key("scored", None, days_back(7), "summary.json") + ".bak", b"{}", JSON)
    frozen_archive._put_plain(kind_key("scored", "shufersal", days_back(8), "summary.json"), b"{}", JSON)
    assert frozen_archive.scored_days() == [days_back(3), days_back(1), DAY]
    assert MemoryArchive().scored_days() == []


def test_fetch_summaries_returns_day_summaries(frozen_archive, tmp_path):
    summaries = [day_summary(days_back(3)), day_summary(days_back(1), scored=4)]
    bodies = {}
    for summary in reversed(summaries):
        bodies[summary.day] = write_summary(tmp_path / "out", summary)
        frozen_archive.put_summary(summary.day, tmp_path / "out")
    found = frozen_archive.fetch_summaries(tmp_path / "in")
    assert found == summaries                                               # read through read_summary, by day
    assert all(isinstance(summary, DaySummary) for summary in found)
    for summary in summaries:                                               # and each one in the work folder
        assert summary_path(tmp_path / "in", summary.day).read_bytes() == bodies[summary.day]
    assert MemoryArchive().fetch_summaries(tmp_path / "none") == []


def test_no_method_ever_deletes(tmp_path):
    fake = ClockedS3(NOW, page_size=2)
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
    call("day_file_keys", SLUG, DAY, "PriceFull")
    call("fetch_raw", SLUG, DAY, tmp_path / "raw", ("PriceFull", "PromoFull"))
    call("fetch_store_list", SLUG, DAY, tmp_path / "raw")
    call("fetch_manifests", SLUG, DAY, tmp_path / "manifests")
    call("fetch_table", SLUG, DAY, tmp_path / "in")
    call("put_tables", SLUG, DAY, tmp_path / "out")
    call("put_tables", SLUG, DAY, tmp_path / "out")
    call("fetch_table", SLUG, DAY, tmp_path / "in")
    put_items(archive, SLUG, DAY)
    call("fetch_items", SLUG, DAY, tmp_path / "in")
    call("fetch_history", DAY, tmp_path / "in")
    registry = covered_path(tmp_path / "out", days_back(1))
    registry.parent.mkdir(parents=True)
    registry.write_bytes(b"PAR1")
    call("put_covered", days_back(1), tmp_path / "out")
    call("put_covered", days_back(1), tmp_path / "out")
    call("fetch_covered", DAY, tmp_path / "in")
    call("put_basket_record", record, NOW)
    call("put_basket_record", record, NOW)
    record.write_text(json.dumps({"day": "2026-11-02", "run_id": "093000Z-basket-ab12", "other": 1}))
    with pytest.raises(AlreadyStored):
        call("put_basket_record", record, NOW)
    call("put_frozen", DAY, FROZEN, NOW)
    call("put_frozen", DAY, FROZEN, NOW)
    with pytest.raises(AlreadyStored):
        call("put_frozen", DAY, FROZEN + b"x", NOW)
    call("frozen_days")
    assert archive.last_modified(archive_key(DAY)) == NOW
    call("put_scores", DAY, SCORES, NOW)
    call("put_scores", DAY, SCORES, NOW)
    with pytest.raises(AlreadyStored):
        call("put_scores", DAY, SCORES + b"x", NOW)
    write_summary(tmp_path / "out", day_summary(days_back(14)))
    call("put_summary", days_back(14), tmp_path / "out")
    call("put_summary", days_back(14), tmp_path / "out")
    call("scored_days")
    call("fetch_summaries", tmp_path / "in")
    # every method _Archive defines was run above
    assert called == {name for name in vars(_Archive) if not name.startswith("_")}
    operations = {op for op, _ in fake.calls}
    assert operations <= {"put_object", "head_object", "get_object", "get_paginator", "paginate"}
    assert not any("delete" in op.lower() for op in operations)

"""The daily freeze and the ledger (docs/shopper-site.md F6, Calls 15 to 17; the plan's Task 12, questions D and E).

The freezer is given the archive and the run's clock: tests use a MemoryArchive, whose S3 clock is fixed here (a time
per key, the put's `now` unless a clock is given), so no test reads the clock. The bodies are Task 11's files
(`forecasts_csv`, rows keyed by column), gzipped with no time in the header; a rerun's bytes are made at another
compression level to prove "same" reads the CSV inside, not the gzip.
"""
import gzip
import hashlib
import os
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from basket.archive import MemoryArchive
from shopper.forecast import Forecast, forecasts_csv
from shopper.freeze import (
    ISRAEL,
    LEDGER_HEADER,
    ArchiveFreezer,
    ForecastsDiffer,
    Frozen,
    ReadOnlyFreezer,
    ScoresDiffer,
    archive_key,
    cutoff,
    days_with,
    ledger,
    scores_archive_key,
    scores_site_key,
    site_key,
    utc_text,
)
from test_store import lock_of

DAY = date(2026, 11, 7)
NEXT = date(2026, 11, 8)
NOW = datetime(2026, 11, 7, 12, 33, tzinfo=ISRAEL)            # 10:33 UTC
CUTOFF = datetime(2026, 11, 7, 22, 0, tzinfo=timezone.utc)    # midnight ending DAY in Israel (UTC+2)
DEAL, EXPRESS = "shufersal-deal", "shufersal-express"
CODES = ("2000000000046", "2000000000053")


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _row(column: str, code: str, p: Fraction) -> Forecast:
    return Forecast(column=column, code=code, p=p, a=Fraction(1, 4), b=Fraction(3, 4), b_says=False, days_since=None,
                    n=0, a_from="column")


def forecasts_of(p: Fraction = Fraction(1, 2)) -> bytes:
    """A day's file: two columns, two products; `p` moves the first row's probability."""
    return forecasts_csv([_row(DEAL, CODES[0], p), _row(DEAL, CODES[1], Fraction(1, 3)),
                          _row(EXPRESS, CODES[0], Fraction(2, 3))], "f00d")


def recompressed(body: bytes, level: int) -> bytes:
    """The same CSV in other gzip bytes (the compression level is in the header and the deflate stream)."""
    return gzip.compress(gzip.decompress(body), compresslevel=level, mtime=0)


def clock_at(moment: datetime):
    return lambda: moment


def frozen_on(day: date, at: datetime) -> Frozen:
    return Frozen(day=day, body=forecasts_of(), sha256=sha(forecasts_of()), frozen_at=at, on_time=True, status="frozen")


# The cutoff and the keys

@pytest.mark.parametrize("day, utc", [
    (date(2026, 11, 7), datetime(2026, 11, 7, 22, 0, tzinfo=timezone.utc)),    # winter time, UTC+2
    (date(2026, 10, 24), datetime(2026, 10, 24, 21, 0, tzinfo=timezone.utc)),  # the night summer time ends: midnight is UTC+3
    (date(2026, 10, 25), datetime(2026, 10, 25, 22, 0, tzinfo=timezone.utc)),  # the day it ended: midnight is UTC+2
])
def test_cutoff_is_midnight_israel_time(day, utc):
    assert cutoff(day) == utc
    assert cutoff(day).utcoffset() is not None
    assert cutoff(day).astimezone(ISRAEL).time().isoformat() == "00:00:00"
    assert cutoff(day).astimezone(ISRAEL).date() == day + timedelta(days=1)


def test_the_keys():
    assert archive_key(DAY) == "forecasts/date=2026-11-07/forecasts.csv.gz"
    assert site_key(DAY) == "forecasts/2026-11-07.csv.gz"


# Freezing

def test_a_first_freeze_is_written_once_and_locked():
    archive = MemoryArchive()
    body = forecasts_of()
    frozen = ArchiveFreezer(archive, NOW).freeze(DAY, body)
    assert frozen == Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=NOW, on_time=True, status="frozen")
    assert list(archive.objects) == [archive_key(DAY)]
    assert archive.objects[archive_key(DAY)].body == body
    assert lock_of(archive, archive_key(DAY)) == ("GOVERNANCE", NOW + timedelta(days=3650))
    # the same run again changes nothing: one file, one lock
    again = ArchiveFreezer(archive, NOW + timedelta(hours=1)).freeze(DAY, body)
    assert again.status == "same"
    assert list(archive.objects) == [archive_key(DAY)]
    assert lock_of(archive, archive_key(DAY)) == ("GOVERNANCE", NOW + timedelta(days=3650))


def test_the_hash_is_of_the_gzip_bytes_the_ledger_and_the_site_carry():
    body = forecasts_of()
    frozen = ArchiveFreezer(MemoryArchive(), NOW).freeze(DAY, body)
    assert frozen.sha256 == hashlib.sha256(body).hexdigest() != sha(gzip.decompress(body))


def test_a_rerun_with_the_same_content_publishes_the_archives_bytes():
    archive = MemoryArchive()
    body = forecasts_of()
    other_bytes = recompressed(body, 1)
    assert other_bytes != body and gzip.decompress(other_bytes) == gzip.decompress(body)   # the premise
    ArchiveFreezer(archive, NOW).freeze(DAY, body)
    rerun = ArchiveFreezer(archive, NOW + timedelta(hours=2)).freeze(DAY, other_bytes)
    assert rerun == Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=NOW, on_time=True, status="same")
    assert rerun.body is not other_bytes and rerun.body == archive.objects[archive_key(DAY)].body
    assert list(archive.objects) == [archive_key(DAY)]          # no second file


def test_a_rerun_with_other_content_raises_naming_both_hashes():
    archive = MemoryArchive()
    stored, other = forecasts_of(), forecasts_of(Fraction(3, 4))
    ArchiveFreezer(archive, NOW).freeze(DAY, stored)
    with pytest.raises(ForecastsDiffer) as caught:
        ArchiveFreezer(archive, NOW + timedelta(hours=2)).freeze(DAY, other)
    message = str(caught.value)
    assert "2026-11-07" in message and sha(stored) in message and sha(other) in message
    assert archive.objects[archive_key(DAY)].body == stored and list(archive.objects) == [archive_key(DAY)]


def test_other_content_raises_past_the_cutoff_too():
    archive = MemoryArchive()
    ArchiveFreezer(archive, NOW).freeze(DAY, forecasts_of())
    with pytest.raises(ForecastsDiffer):
        ArchiveFreezer(archive, CUTOFF + timedelta(hours=10)).freeze(DAY, forecasts_of(Fraction(3, 4)))


def test_past_the_cutoff_nothing_stored_writes_none():
    for now in (CUTOFF, CUTOFF + timedelta(seconds=1), CUTOFF + timedelta(days=3)):   # at the cutoff counts as past
        archive = MemoryArchive()
        assert ArchiveFreezer(archive, now).freeze(DAY, forecasts_of()) is None
        assert archive.objects == {}


def test_one_second_before_the_cutoff_still_freezes():
    archive = MemoryArchive()
    now = CUTOFF - timedelta(seconds=1)
    frozen = ArchiveFreezer(archive, now).freeze(DAY, forecasts_of())
    assert (frozen.status, frozen.on_time, frozen.frozen_at) == ("frozen", True, now)
    assert list(archive.objects) == [archive_key(DAY)]


def test_past_the_cutoff_with_a_stored_file_publishes_it():
    archive = MemoryArchive()
    body = forecasts_of()
    ArchiveFreezer(archive, NOW).freeze(DAY, body)
    late_run = ArchiveFreezer(archive, CUTOFF + timedelta(days=2)).freeze(DAY, recompressed(body, 9))
    assert late_run == Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=NOW, on_time=True, status="same")
    assert list(archive.objects) == [archive_key(DAY)]


def test_s3s_time_past_the_cutoff_makes_the_day_late():
    archive = MemoryArchive(s3_clock=clock_at(datetime(2026, 11, 8, 0, 0, 1, tzinfo=ISRAEL)))
    now = datetime(2026, 11, 7, 23, 59, 59, tzinfo=ISRAEL)     # the run thought it was in time
    body = forecasts_of()
    frozen = ArchiveFreezer(archive, now).freeze(DAY, body)
    assert frozen == Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=datetime(2026, 11, 8, 0, 0, 1, tzinfo=ISRAEL),
                            on_time=False, status="late")
    assert list(archive.objects) == [archive_key(DAY)]         # written: S3's time is only known afterwards
    # a rerun sees the same lateness in the stored file's time
    rerun = ArchiveFreezer(archive, now).frozen(DAY)
    assert (rerun.status, rerun.on_time) == ("same", False)


def test_s3s_time_at_the_cutoff_is_late_and_a_second_before_is_on_time():
    for stamp, on_time, status in ((CUTOFF, False, "late"), (CUTOFF - timedelta(seconds=1), True, "frozen")):
        archive = MemoryArchive(s3_clock=clock_at(stamp))
        frozen = ArchiveFreezer(archive, NOW).freeze(DAY, forecasts_of())
        assert (frozen.on_time, frozen.status, frozen.frozen_at) == (on_time, status, stamp)


def test_the_s3_time_is_read_back_not_the_runs_clock():
    stamp = datetime(2026, 11, 7, 12, 33, 7, tzinfo=ISRAEL)
    archive = MemoryArchive(s3_clock=clock_at(stamp))
    frozen = ArchiveFreezer(archive, NOW).freeze(DAY, forecasts_of())
    assert frozen.frozen_at == stamp != NOW


def test_frozen_reads_what_the_archive_holds():
    archive = MemoryArchive()
    freezer = ArchiveFreezer(archive, NOW)
    assert freezer.frozen(DAY) is None
    body = forecasts_of()
    freezer.freeze(DAY, body)
    assert freezer.frozen(DAY) == Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=NOW, on_time=True,
                                         status="same")
    assert freezer.frozen(NEXT) is None
    assert ArchiveFreezer.writes is True


def test_one_file_a_day_for_every_column_and_each_day_its_own():
    archive = MemoryArchive()
    freezer = ArchiveFreezer(archive, NOW)
    freezer.freeze(DAY, forecasts_of())
    freezer.freeze(NEXT, forecasts_of(Fraction(3, 4)))
    assert sorted(archive.objects) == [archive_key(DAY), archive_key(NEXT)]
    assert archive.frozen_days() == [DAY, NEXT]


# The scores file (F7, Task 13): put once and locked through the freezer, like the day's forecasts, with no cutoff

def scores_of(outcome: str = "1") -> bytes:
    """A day's scores file, in short: what the freezer compares is the CSV inside the gzip."""
    return gzip.compress(f"column,barcode,outcome\n{DEAL},{CODES[0]},{outcome}\n".encode(), mtime=0)


def test_the_scores_keys():
    assert scores_archive_key(DAY) == "scores/date=2026-11-07/scores.csv.gz"
    assert scores_site_key(DAY) == "scores/2026-11-07.csv.gz"


def test_scores_are_put_once_and_locked():
    archive = MemoryArchive()
    body = scores_of()
    assert ArchiveFreezer(archive, NOW).put_scores(DAY, body) == body
    assert list(archive.objects) == [scores_archive_key(DAY)]
    assert archive.objects[scores_archive_key(DAY)].body == body
    assert lock_of(archive, scores_archive_key(DAY)) == ("GOVERNANCE", NOW + timedelta(days=3650))
    # the same scores again change nothing: one file, one lock
    assert ArchiveFreezer(archive, NOW + timedelta(hours=1)).put_scores(DAY, body) == body
    assert list(archive.objects) == [scores_archive_key(DAY)]
    assert lock_of(archive, scores_archive_key(DAY)) == ("GOVERNANCE", NOW + timedelta(days=3650))


def test_a_rescoring_with_the_same_rows_returns_the_archives_bytes():
    archive = MemoryArchive()
    body = scores_of()
    other_bytes = recompressed(body, 1)
    assert other_bytes != body and gzip.decompress(other_bytes) == gzip.decompress(body)   # the premise
    ArchiveFreezer(archive, NOW).put_scores(DAY, body)
    again = ArchiveFreezer(archive, NOW + timedelta(days=1)).put_scores(DAY, other_bytes)
    assert again == body and again is not other_bytes                      # the site publishes the archive's bytes
    assert list(archive.objects) == [scores_archive_key(DAY)]


def test_a_rescoring_with_other_rows_raises_naming_both_hashes():
    archive = MemoryArchive()
    stored, other = scores_of("1"), scores_of("0")
    ArchiveFreezer(archive, NOW).put_scores(DAY, stored)
    with pytest.raises(ScoresDiffer) as caught:
        ArchiveFreezer(archive, NOW + timedelta(days=1)).put_scores(DAY, other)
    message = str(caught.value)
    assert "scores" in message and "2026-11-07" in message and sha(stored) in message and sha(other) in message
    assert archive.objects[scores_archive_key(DAY)].body == stored and list(archive.objects) == [scores_archive_key(DAY)]


def test_scores_need_no_clock():
    # the build of day d + 14 scores day d, long past its cutoff, and a missed one is scored later still
    archive = MemoryArchive()
    now = CUTOFF + timedelta(days=30)
    assert ArchiveFreezer(archive, now).put_scores(DAY, scores_of()) == scores_of()
    assert lock_of(archive, scores_archive_key(DAY)) == ("GOVERNANCE", now + timedelta(days=3650))


def test_scores_and_forecasts_of_a_day_are_two_files():
    archive = MemoryArchive()
    freezer = ArchiveFreezer(archive, NOW)
    freezer.freeze(DAY, forecasts_of())
    freezer.put_scores(DAY, scores_of())
    assert sorted(archive.objects) == [archive_key(DAY), scores_archive_key(DAY)]
    assert archive.frozen_days() == [DAY]


# The ledger

def test_the_ledger_grows_by_one_line():
    first = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW, on_time=True, status="frozen")
    second = Frozen(day=NEXT, body=b"b", sha256=sha(b"b"), frozen_at=datetime(2026, 11, 8, 9, 5, 3, tzinfo=ISRAEL),
                    on_time=True, status="frozen")
    one = ledger(None, first)
    assert one == LEDGER_HEADER + f"2026-11-07,{sha(b'a')},2026-11-07T10:33:00Z\n".encode()
    assert LEDGER_HEADER == b"day,sha256,frozen_at\n"
    two = ledger(one, second)
    assert two == one + f"2026-11-08,{sha(b'b')},2026-11-08T07:05:03Z\n".encode()   # UTC, ISO, a Z; the published bytes kept
    assert two.startswith(one)


def test_a_day_already_in_the_ledger_leaves_it_as_it_is():
    first = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW, on_time=True, status="frozen")
    once = ledger(None, first)
    assert ledger(once, first) == once                          # a rerun after a failed upload
    assert ledger(once, replace(first, status="same")) == once


def test_the_ledger_appends_an_earlier_day_at_the_end():
    later = Frozen(day=NEXT, body=b"b", sha256=sha(b"b"), frozen_at=NOW + timedelta(days=1), on_time=True, status="frozen")
    earlier = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW, on_time=True, status="frozen")
    held = ledger(None, later)
    assert ledger(held, earlier) == held + f"2026-11-07,{sha(b'a')},2026-11-07T10:33:00Z\n".encode()


def test_the_ledger_refuses_another_line_for_a_day():
    first = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW, on_time=True, status="frozen")
    held = ledger(None, first)
    other_file = Frozen(day=DAY, body=b"b", sha256=sha(b"b"), frozen_at=NOW, on_time=True, status="frozen")
    other_time = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW + timedelta(seconds=1), on_time=True,
                        status="frozen")
    for changed in (other_file, other_time):
        with pytest.raises(ValueError, match="2026-11-07"):
            ledger(held, changed)


def test_a_records_time_is_utc_to_the_second_and_never_naive():
    assert utc_text(datetime(2026, 11, 7, 12, 33, tzinfo=ISRAEL)) == "2026-11-07T10:33:00Z"
    assert utc_text(datetime(2026, 11, 7, 10, 33, 0, 999_999, tzinfo=timezone.utc)) == "2026-11-07T10:33:00Z"
    with pytest.raises(ValueError, match="time zone"):
        utc_text(datetime(2026, 11, 7, 10, 33))
    # the ledger takes its line's time from it: a naive time is refused there too, not read as this machine's
    naive = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=datetime(2026, 11, 7, 10, 33), on_time=True,
                   status="frozen")
    with pytest.raises(ValueError, match="time zone"):
        ledger(None, naive)


def test_a_late_day_gets_its_line_with_its_late_time():
    late = Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=datetime(2026, 11, 8, 0, 0, 1, tzinfo=ISRAEL),
                  on_time=False, status="late")
    assert ledger(None, late).endswith(f"2026-11-07,{sha(b'a')},2026-11-07T22:00:01Z\n".encode())


def _a_day() -> Frozen:
    return Frozen(day=DAY, body=b"a", sha256=sha(b"a"), frozen_at=NOW, on_time=True, status="frozen")


def test_a_ledger_with_only_its_header_is_extended():
    assert ledger(LEDGER_HEADER, _a_day()) == ledger(None, _a_day())


def test_a_published_ledger_without_its_header_is_refused_not_extended():
    line = f"2026-11-08,{sha(b'b')},2026-11-08T07:05:03Z\n".encode()
    for damaged in (b"", line, b"day,sha256,frozen_at" + line, b"sha256,day,frozen_at\n" + line):
        with pytest.raises(ValueError, match="header"):
            ledger(damaged, _a_day())      # an empty file would otherwise get a first line and no header


def test_a_published_ledger_without_its_final_newline_is_refused_not_glued_to():
    held = ledger(None, _a_day())
    later = Frozen(day=NEXT, body=b"b", sha256=sha(b"b"), frozen_at=NOW + timedelta(days=1), on_time=True,
                   status="frozen")
    for damaged in (held[:-1], held.rstrip(b"\n") + b"\r"):
        with pytest.raises(ValueError, match="newline"):
            ledger(damaged, later)         # the new line would otherwise join the last one
    with pytest.raises(ValueError, match="newline"):
        ledger(held[:-1], _a_day())        # not even the day's own line being there makes a damaged ledger fit to publish


# The Mac's freezer

def _synced(data: Path, body: bytes, stamp: datetime, day: date = DAY) -> Path:
    path = data / "forecasts" / f"date={day.isoformat()}" / "forecasts.csv.gz"
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    os.utime(path, (stamp.timestamp(), stamp.timestamp()))
    return path


def _tree(root: Path) -> dict[str, tuple[bytes, float]]:
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime) for path in sorted(root.rglob("*"))
            if path.is_file()}


def test_the_read_only_freezer_never_writes(tmp_path):
    body = forecasts_of()
    stamp = datetime(2026, 11, 7, 10, 33, 12, tzinfo=timezone.utc)
    _synced(tmp_path, body, stamp)
    before = (_tree(tmp_path), sorted(str(p) for p in tmp_path.rglob("*")))
    freezer = ReadOnlyFreezer(tmp_path)
    assert freezer.writes is False
    # whatever the run computed, the bytes are the archive's, with the file's time as S3 gave it on the sync
    expected = Frozen(day=DAY, body=body, sha256=sha(body), frozen_at=stamp, on_time=True, status="same")
    assert freezer.freeze(DAY, forecasts_of(Fraction(3, 4))) == expected
    assert freezer.frozen(DAY) == expected
    assert freezer.frozen(DAY).frozen_at.utcoffset() == timedelta(0)
    # a day the sync did not bring: nothing, and nothing made
    assert freezer.freeze(NEXT, forecasts_of()) is None
    assert freezer.frozen(NEXT) is None
    assert (_tree(tmp_path), sorted(str(p) for p in tmp_path.rglob("*"))) == before


def test_the_read_only_freezer_with_no_data_folder_writes_none_and_makes_none(tmp_path):
    folder = tmp_path / "data"
    freezer = ReadOnlyFreezer(folder)
    assert freezer.freeze(DAY, forecasts_of()) is None and freezer.frozen(DAY) is None
    assert not folder.exists()


def test_the_read_only_freezer_reads_a_late_file_as_late(tmp_path):
    _synced(tmp_path, forecasts_of(), CUTOFF + timedelta(seconds=1))
    assert ReadOnlyFreezer(tmp_path).frozen(DAY).on_time is False
    other = tmp_path / "other"
    _synced(other, forecasts_of(), CUTOFF - timedelta(seconds=1))
    assert ReadOnlyFreezer(other).frozen(DAY).on_time is True


# What the build asks of a freezer (Task 19): the days frozen, and a stored scores file that differs

def test_the_archive_freezer_lists_the_archives_frozen_days():
    archive = MemoryArchive()
    freezer = ArchiveFreezer(archive, NOW)
    assert freezer.frozen_days() == []
    freezer.freeze(NEXT, forecasts_of())
    freezer.freeze(DAY, forecasts_of(Fraction(3, 4)))
    assert freezer.frozen_days() == [DAY, NEXT] == archive.frozen_days()


def test_the_archive_freezer_gives_the_stored_scores_file_the_record():
    """On ScoresDiffer the stored file is the record (Task 19's carry): the freezer gives its bytes, unchanged."""
    archive = MemoryArchive()
    stored = scores_of("1")
    ArchiveFreezer(archive, NOW).put_scores(DAY, stored)
    later = ArchiveFreezer(archive, NOW + timedelta(days=1))
    with pytest.raises(ScoresDiffer):
        later.put_scores(DAY, scores_of("0"))
    assert later.stored_scores(DAY) == stored
    assert later.stored_scores(NEXT) is None


def test_the_read_only_freezer_lists_the_days_the_sync_brought(tmp_path):
    assert ReadOnlyFreezer(tmp_path / "none").frozen_days() == []
    stamp = datetime(2026, 11, 7, 10, 33, 12, tzinfo=timezone.utc)
    _synced(tmp_path, forecasts_of(), stamp, NEXT)
    _synced(tmp_path, forecasts_of(), stamp, DAY)
    for odd in ("date=20261109/forecasts.csv.gz", "date=2026-11-10/other.csv.gz", "date=x/forecasts.csv.gz"):
        (tmp_path / "forecasts" / odd).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "forecasts" / odd).write_bytes(forecasts_of())          # names this code never writes
    before = _tree(tmp_path)
    assert ReadOnlyFreezer(tmp_path).frozen_days() == [DAY, NEXT]
    assert _tree(tmp_path) == before


def test_days_with_lists_only_the_files_a_key_names_earliest_first(tmp_path):
    def key_of(day: date) -> str:
        return f"scored/date={day.isoformat()}/summary.json"
    for name in ("scored/date=2026-11-08/summary.json", "scored/date=2026-11-07/summary.json",
                 "scored/date=20261106/summary.json", "scored/date=2026-11-05/other.json",
                 "scored/2026-11-04/summary.json"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"{}")
    (tmp_path / "scored" / "date=2026-11-03" / "summary.json").mkdir(parents=True)   # a folder, not a file
    assert days_with(tmp_path, key_of) == [DAY, NEXT]
    assert days_with(tmp_path / "none", key_of) == []

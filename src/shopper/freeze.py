"""The daily freeze and the ledger (docs/shopper-site.md F6, Calls 15 to 17; the plan's Task 12, questions D and E), and
the scores file put the same way (F7; the plan's Task 13).

Each day's forecasts file is written once, before the day's outcomes are known, so that anyone can see afterwards that
it was not changed. It is one file for all the columns (`shopper.forecast.forecasts_csv`), at `forecasts/date=<day>/
forecasts.csv.gz` in the archive (`archive_key`) and, with the same bytes, on the site at `forecasts/<day>.csv.gz`
(`site_key`).

The cutoff. A day counts only if its file was stored before midnight ending the day, Israel time (`cutoff`), about when
the chains' next files appear. The time that counts is the stored object's time as S3 reports it (`LastModified`), never
the time the run's own clock showed: a run that thought it was in time and was not is "late". Whether S3 stamps the start
or the end of the upload is UNVERIFIED (the design's F6 marks it so).

The freezer. Only the site run in Lambda writes the archive (question D): `ArchiveFreezer`, given the archive and the
run's time, `freeze`s the day's file. Its rules, in order:

- A file already stored for the day is compared with the new one by the CSV inside the gzip (question E), not by the
  gzip bytes, which can differ between the Mac's, CI's and Lambda's zlib for the same rows. The same rows: the result is
  the stored file ("same"), with the stored bytes and the time S3 gave it, whatever the run's time is, so a rerun after a
  failed upload publishes the archive's bytes. Other rows: `ForecastsDiffer` names the day and both SHA-256s and
  nothing is written or published. Every row names the code that made it, so a rerun of the day at other code differs.
- Nothing stored and the run's time at or past the cutoff: nothing is written and the result is None (a backfill or a
  late rerun freezes nothing; the day is a gap).
- Otherwise the file is put, write-once and locked like a manifest (`basket.archive`'s `put_frozen`), and S3's time is
  read back: on time when it is before the cutoff ("frozen"), else "late" (the file stays, and shows as late).

The scores file (F7). Each frozen day's scores file (`shopper.score.scores_csv`) is written once too, by the same
freezer (`put_scores`), at `scores/date=<day>/scores.csv.gz` in the archive (`scores_archive_key`) and, with the same
bytes, on the site at `scores/<day>.csv.gz` (`scores_site_key`): write-once and locked like the forecasts
(`basket.archive`'s `put_scores`), and compared the same way when one is already stored: the same rows return the
stored bytes, which are the ones the site publishes; other rows raise `ScoresDiffer`, naming the day and both SHA-256s,
and nothing is written. There is no cutoff: scoring needs no clock, so a day missed is scored by a later build, as
long as that build's 90-day read still holds the day's whole window (`shopper.score.due`); a day past that reach is
listed apart and left unscored, without stopping the build (`shopper.score.out_of_reach`).

The Mac's `ReadOnlyFreezer` writes nothing (question D): it reads the files `scripts/sync.sh` brought into
`<data dir>/forecasts/date=<day>/` and returns the synced file as "same", or None for a day it holds none of. It does
not compare: the bytes published are always the archive's. A synced file's time is its modification time, which the
AWS CLI sets on a download to the object's time in S3, to the second (`ProvideLastModifiedTimeSubscriber` in
`awscli/customizations/s3/subscribers.py`, read in awscli 2.34.9; the same fact `--exact-timestamps` relies on in
`scripts/sync.sh`).

The ledger (Call 17). `forecasts/ledger.csv` on the site gains one line a day, `<day>,<SHA-256 of the file's gzip
bytes>,<S3's time, UTC to the second, ISO with a Z>` (`utc_text`), and only grows: `ledger` returns the published
ledger's bytes with the day's line after them, so anyone who kept an earlier copy can see a changed line. The day's line
already there is left as it is (a rerun); another line for the day is refused (ValueError). A late day has its line too,
with its late time. A published ledger that does not start with the header line, or does not end in a newline, is
refused (ValueError) rather than extended: an empty file would get a first line and no header, and a last line without
its newline would have the new line joined to it, damage a check that only looks for the published bytes at the start
would let through. The upload check (Task 21) refuses a ledger that does not begin with the published one's bytes.
"""
import gzip
import hashlib
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ISRAEL = ZoneInfo("Asia/Jerusalem")
LEDGER_HEADER = b"day,sha256,frozen_at\n"


class ForecastsDiffer(Exception):
    """The archive holds a forecasts file for the day whose rows are not the ones this run made."""


class ScoresDiffer(Exception):
    """The archive holds a scores file for the day whose rows are not the ones this run made."""


@dataclass(frozen=True)
class Frozen:
    """A day's forecasts file as the archive holds it: its gzip `body`, the body's `sha256`, `frozen_at` (S3's time,
    aware) and `on_time` (before the day's cutoff). `status`: "frozen" (written by this run, on time), "same" (already
    there) or "late" (written by this run, S3's time past the cutoff)."""
    day: date
    body: bytes
    sha256: str
    frozen_at: datetime
    on_time: bool
    status: str


def utc_text(at: datetime) -> str:
    """An aware time as the records write it: in UTC, to the second (a finer part is dropped), ISO with a Z, as in
    "2026-11-07T10:33:00Z". The ledger's line keeps this form (F6, Task 12's bytes), and so does the scoring summary
    (`shopper.score.summary_json`), so a day's summary carries its ledger line's time. A naive time is a ValueError:
    `astimezone` would read it as this machine's own time (the Mac's is Israel's, CI's UTC)."""
    if at.utcoffset() is None:
        raise ValueError("a record's time must carry a time zone")
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cutoff(day: date) -> datetime:
    """Midnight ending `day`, Israel time (aware)."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=ISRAEL)


def archive_key(day: date) -> str:
    return f"forecasts/date={day.isoformat()}/forecasts.csv.gz"


def site_key(day: date) -> str:
    return f"forecasts/{day.isoformat()}.csv.gz"


def scores_archive_key(day: date) -> str:
    return f"scores/date={day.isoformat()}/scores.csv.gz"


def scores_site_key(day: date) -> str:
    return f"scores/{day.isoformat()}.csv.gz"


def _same(stored: bytes, body: bytes, differs: type[Exception], what: str, day: date) -> bytes:
    """`stored` when the CSV inside it is the one inside `body` (question E), else `differs` naming the day and both
    files' SHA-256."""
    if gzip.decompress(stored) != gzip.decompress(body):
        raise differs(
            f"the {what} for {day.isoformat()} differ from the stored file: the archive holds SHA-256 "
            f"{hashlib.sha256(stored).hexdigest()}, this run made {hashlib.sha256(body).hexdigest()}")
    return stored


def _frozen(day: date, body: bytes, at: datetime, status: str) -> Frozen:
    return Frozen(day=day, body=body, sha256=hashlib.sha256(body).hexdigest(), frozen_at=at, on_time=at < cutoff(day),
                  status=status)


class ArchiveFreezer:
    """The site run in Lambda's freezer (the module's docstring): `archive` is a `basket.archive` archive, `now` the
    run's time (aware). The build scores and freezes only through a freezer whose `writes` is true."""
    writes = True

    def __init__(self, archive, now: datetime):
        self.archive = archive
        self.now = now

    def frozen(self, day: date) -> Frozen | None:
        """The day's file as the archive holds it ("same"), or None when it holds none."""
        key = archive_key(day)
        at = self.archive.last_modified(key)
        if at is None:
            return None
        return _frozen(day, self.archive.read_raw(key), at, "same")

    def freeze(self, day: date, body: bytes) -> Frozen | None:
        """Freeze the day's file `body` (the module's docstring): the stored file when there is one, ForecastsDiffer
        when its rows are other ones, None when it is too late and none is stored, else the file just written."""
        stored = self.frozen(day)
        if stored is not None:
            _same(stored.body, body, ForecastsDiffer, "forecasts", day)
            return stored
        if self.now >= cutoff(day):
            return None
        self.archive.put_frozen(day, body, self.now)
        written = _frozen(day, body, self.archive.last_modified(archive_key(day)), "frozen")
        return written if written.on_time else replace(written, status="late")

    def put_scores(self, day: date, body: bytes) -> bytes:
        """Put the day's scores file `body` once, write-once and locked (the module's docstring), and return the bytes
        the archive then holds, the ones the site publishes: the stored file when there is one with the same rows
        (ScoresDiffer when its rows are other ones), else `body`, written now. No cutoff: scoring needs no clock."""
        key = scores_archive_key(day)
        if self.archive.last_modified(key) is not None:
            return _same(self.archive.read_raw(key), body, ScoresDiffer, "scores", day)
        self.archive.put_scores(day, body, self.now)
        return body


class ReadOnlyFreezer:
    """The Mac's freezer (the module's docstring): reads the synced files under `data_dir`, writes nothing."""
    writes = False

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def frozen(self, day: date) -> Frozen | None:
        """The synced file of the day ("same"), or None when the sync brought none."""
        path = self.data_dir / archive_key(day)
        if not path.is_file():
            return None
        return _frozen(day, path.read_bytes(), datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc), "same")

    def freeze(self, day: date, body: bytes) -> Frozen | None:
        """What `frozen` gives: the run's own `body` is not compared and never written."""
        return self.frozen(day)


def ledger(published: bytes | None, frozen: Frozen) -> bytes:
    """The published ledger (None: there is none yet) with the day's line after it when it is not there; the day's line
    there already is left as it is, and another line for the day is a ValueError, as is a published ledger that does not
    start with LEDGER_HEADER or does not end in a newline."""
    line = f"{frozen.day.isoformat()},{frozen.sha256},{utc_text(frozen.frozen_at)}"
    if published is None:
        return LEDGER_HEADER + (line + "\n").encode()
    if not published.startswith(LEDGER_HEADER):
        raise ValueError(f"the published ledger does not start with the header line {LEDGER_HEADER!r}")
    if not published.endswith(b"\n"):
        raise ValueError("the published ledger does not end in a newline")
    for held in published.decode().splitlines():
        if held.startswith(f"{frozen.day.isoformat()},"):
            if held == line:
                return published
            raise ValueError(f"the ledger holds another line for {frozen.day.isoformat()}: {held!r}, not {line!r}")
    return published + (line + "\n").encode()

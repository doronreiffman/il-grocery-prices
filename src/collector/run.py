"""The run loop: one chain's files for one day, fetched, checked, stored write-once, and a manifest of
what happened, written whatever happened (docs/collector.md, "How a morning runs", step 3).

- A chain whose state says `stopped` does nothing: no listing, no download; its manifest says
  `blocked: "stopped earlier"`.
- The listing is read once, as the files are fetched: each file is downloaded before the listing is
  asked for the next one (Shufersal's signed links expire 30 minutes after their page is served).
- A listed file counts when the date in its name is the run's day and its kind was asked for; the
  clock never decides. It is filed under its link's last path segment (ruling R16: Shufersal lists a
  name without `.gz` and links `<name>.gz`). A name already stored that day is listed but not
  fetched; a name listed a second time in one run is ignored (the first counts).
- A file is tried once, and once more after an HTTP error or a body that is not a price file; then
  it is failed and the run goes on. A put that S3 refuses fails that file only (ruling R23).
- A block (Blocked, or HTML where a file belongs) writes the chain's latch and stops the run; the
  owner clears it. A latch that cannot be written leaves the block in the manifest, with the error
  "latch not written: …", and the invocation fails. An unreadable listing, or a listing that cannot be fetched, stops the run with an
  error. So does time: under 90 s left (ruling R32), checked before the listing is read, between its
  items (a page is fetched inside the listing) and before each download.

In the result, `listed` holds that day's names as the listing gave them; `files` those stored or
found stored by this run; `failed` those tried and not stored, with why; `not_attempted` those
listed, not stored before, and never tried because the run stopped first. Names the listing had not
yet given when the run stopped are in none of them: the retry run lists them.
"""
import dataclasses
import hashlib
import json
import secrets
import urllib.parse
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import NoReturn

from collector.chains import Chain
from collector.http import Blocked, Http, HttpError
from collector.names import KINDS
from collector.payload import BadPayload, check_payload, looks_like_html
from collector.sources import Listed, ListingUnreadable, Source
from collector.store import manifest_key, raw_key

MIN_TIME_LEFT = 90.0  # seconds (ruling R32); with less, the run stops and writes its manifest
ATTEMPTS = 2  # a file is tried once, and once again after an HTTP error or a bad body
OUT_OF_TIME = "stopped: under 90 s left"
STOPPED_EARLIER = "stopped earlier"


@dataclass
class RunResult:
    """What one invocation did for one chain: the manifest's content, less the code's commit.
    `files[name]` is {"outcome": "stored" | "exists" | "conflict", "size": bytes, "sha256": hex}.
    `listing_read_at` is None when the listing was never read; `unparsed` (names the listing could
    not read) is 0 unless the listing was read to its end."""

    chain: str
    run_id: str
    mode: str
    day: date
    kinds: list[str]
    listing_read_at: str | None = None
    listed: list[str] = field(default_factory=list)
    files: dict[str, dict] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    not_attempted: list[str] = field(default_factory=list)
    unparsed: int = 0
    blocked: str | None = None
    error: str | None = None


def collect_chain(chain: Chain, source: Source, http: Http, store, day: date, run_id: str, mode: str,
                  kinds: tuple[str, ...], time_left: Callable[[], float], now: Callable[[], datetime],
                  code_sha: str) -> RunResult:
    """Collect `chain`'s `kinds` for `day` through `source` and `http` into `store`, and write the
    manifest under manifest_key(day, slug, run_id). `time_left` gives the invocation's seconds left;
    `now` must give aware datetimes. Anything unexpected is recorded in the manifest's `error`, then
    raised."""
    _utc(now())
    if not kinds or not set(kinds) <= set(KINDS):
        raise ValueError(f"kinds must be some of {KINDS}, not {kinds!r}")
    result = RunResult(chain.slug, run_id, mode, day, list(kinds))
    try:
        if store.read_state(chain.slug).get("stopped"):
            result.blocked = STOPPED_EARLIER
        else:
            _Run(chain.slug, source, http, store, day, tuple(kinds), time_left, now, result).collect()
    except Exception as exc:
        if result.error is None:  # a latch that could not be written has said so already
            result.error = f"unexpected error: {type(exc).__name__}: {exc}"
        raise
    finally:
        store.put_record(manifest_key(day, chain.slug, run_id), manifest_bytes(result, code_sha), now())
    return result


def manifest_bytes(result: RunResult, code_sha: str) -> bytes:
    """The manifest: the result and the code's commit, as JSON with sorted keys."""
    record = dataclasses.asdict(result) | {"day": result.day.isoformat(), "code_sha": code_sha}
    return json.dumps(record, sort_keys=True, indent=1).encode()


def new_run_id(now: datetime, mode: str) -> str:
    """`<HHMMSS>Z-<mode>-<4 random hex>`, the time in UTC: unique enough that a manual re-run in the
    same second does not meet a stored manifest."""
    return f"{_utc(now):%H%M%S}Z-{mode}-{secrets.token_hex(2)}"


def stored_name(item: Listed) -> str:
    """The name `item` is stored under: its link's last path segment, without the query (ruling R16)."""
    return urllib.parse.urlsplit(item.url).path.rsplit("/", 1)[-1]


def _utc(moment: datetime) -> datetime:
    # A naive time would be read as this machine's: Asia/Jerusalem here, UTC in CI.
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("the time must carry a time zone")
    return moment.astimezone(timezone.utc)


class _Stop(Exception):
    """The run ends early; why is already on the result."""


class _Run:
    def __init__(self, slug: str, source: Source, http: Http, store, day: date, kinds: tuple[str, ...],
                 time_left: Callable[[], float], now: Callable[[], datetime], result: RunResult):
        self.slug, self.source, self.http, self.store = slug, source, http, store
        self.day, self.kinds, self.time_left, self.now = day, kinds, time_left, now
        self.result = result
        self.stored = store.stored_names(slug, day)  # read once: a name is handled once per run
        self.seen: set[str] = set()

    def collect(self) -> None:
        try:
            self._check_time()
            self.result.listing_read_at = _utc(self.now()).isoformat()
            listing = iter(self.source.listing(self.http, self.kinds))
            while (item := self._next(listing)) is not None:
                self._take(item)
                self._check_time()
            self.result.unparsed = self.source.unparsed  # final only now: it resets on the first next()
        except _Stop:
            pass

    def _next(self, listing: Iterator[Listed]) -> Listed | None:
        try:
            return next(listing)
        except StopIteration:
            return None
        except Blocked as block:
            self._latch(str(block))
        except ListingUnreadable as exc:
            self._stop(f"listing unreadable: {exc}")
        except HttpError as exc:  # not read again: an NCR listing logs in afresh each time
            self._stop(f"listing failed: {exc}")

    def _take(self, item: Listed) -> None:
        if item.name.day != self.day or item.name.kind not in self.kinds:
            return
        name = stored_name(item)
        if name in self.seen:
            return  # listed again while the listing was read: the first counts
        self.seen.add(name)
        self.result.listed.append(name)
        if name in self.stored:
            return
        body = self._fetch(item, name)
        if body is not None:
            self._store(name, body)

    def _fetch(self, item: Listed, name: str) -> bytes | None:
        """`item`'s body once it reads as a price file; None after recording why not in `failed`."""
        problem = None
        for _ in range(ATTEMPTS):
            if self._short_of_time():
                if problem is None:
                    self.result.not_attempted.append(name)
                else:
                    self.result.failed[name] = f"{problem}; not tried again: under 90 s left"
                self._stop(OUT_OF_TIME)
            try:
                data = self.source.download(self.http, item)
            except Blocked as block:
                self._fail_and_latch(name, str(block))
            except ListingUnreadable as exc:  # Shufersal's expired-link refresh reads the listing again
                self.result.failed[name] = f"listing unreadable: {exc}"
                self._stop(f"listing unreadable: {exc}")
            except HttpError as exc:
                problem = str(exc)
                continue
            if looks_like_html(data):
                self._fail_and_latch(name, f"{name}: HTML where a file belongs")
            try:
                check_payload(name, data)
            except BadPayload as exc:
                problem = str(exc)
                continue
            return data
        self.result.failed[name] = problem
        return None

    def _store(self, name: str, data: bytes) -> None:
        try:
            outcome = self.store.put_raw(raw_key(self.slug, self.day, name), data, self.now())
        except Exception as exc:  # a storage hiccup costs this file, not the rest of the morning (R23)
            self.result.failed[name] = f"not stored: {type(exc).__name__}: {exc}"
            return
        self.result.files[name] = {"outcome": outcome.value, "size": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()}

    def _short_of_time(self) -> bool:
        return self.time_left() < MIN_TIME_LEFT

    def _check_time(self) -> None:
        if self._short_of_time():
            self._stop(OUT_OF_TIME)

    def _stop(self, error: str) -> NoReturn:
        self.result.error = error
        raise _Stop

    def _fail_and_latch(self, name: str, reason: str) -> NoReturn:
        self.result.failed[name] = reason
        self._latch(reason)

    def _latch(self, reason: str) -> NoReturn:
        """Stop the chain until the owner clears it; the check sends one alert for it. If the latch
        cannot be written, the manifest still records the block and says so, and the invocation fails."""
        self.result.blocked = reason  # first: the manifest may be the only record of what the portal did
        try:
            self.store.write_state(self.slug, {"stopped": True, "since": _utc(self.now()).isoformat(),
                                               "reason": reason, "alerted": False})
        except Exception as exc:
            self.result.error = f"latch not written: {type(exc).__name__}: {exc}"
            raise
        raise _Stop

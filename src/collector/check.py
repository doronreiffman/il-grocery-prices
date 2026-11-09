"""The morning check: what each chain listed that day and did not store, which chains are stopped,
and which runs failed (docs/collector.md, "How a morning runs", steps 4 and 5, and "Alerts"); and,
when asked, the update files of the day before (ruling R39, below).

For each chain, from that day's manifests of its main and retry runs (MORNING) and the bucket:

- missing: names any of the manifests listed that are not stored (a conflict copy counts as its
  original) → one `missing` alert for the chain, with the count and up to ten names; the check
  record holds them all. Names are the stored names, the link's last segment (ruling R16).
- stopped: the chain's state says stopped and not yet alerted → one `stopped` alert. check_day
  changes no state: once the email has gone, mark_alerted marks the chain `alerted: true` (its
  reason kept), so later checks stay quiet until the owner clears it; an email that fails leaves
  the state alone, and the next check alerts again (ruling R26).
- failed (ruling R4): that day's retry manifests do not together cover the kinds the chain collects
  (all five, or the chain's `kinds` when given: Shufersal's store list and full files, each in its own
  run), or one of them has an error → one `failed` alert. A retry manifest
  that is blocked with no error is not a failed run: the `stopped` alert covers it. A main run's
  error is left to the retry run. Ruling R31: retry runs that together list nothing for the day,
  none of them blocked, are a failed run too, with the sum of their unparsed names: a portal change
  that leaves every name unreadable, or dated another day, ends without an error. Ruling R35 (QUEUE
  q7): a full kind the chain collects (PriceFull, PromoFull) that no run that day listed, main or
  retry, is a failed run too, unless one of its retry runs was blocked (as R31): R31's union over
  the retry runs stayed silent on a day Shufersal listed no PriceFull while its Stores run listed
  something. Ruling R36, as ruling R37 amends it: a retry run whose error is the run's own time stop
  (OUT_OF_TIME, matched exactly) is not a failed run when three things hold. First, each kind it covers
  was read in full that day (collector.pages.read_in_full): the pages the day's runs read, the retry's
  own included, join up from page 1 to the last page. A run whose manifest holds no page records (other
  chains' runs, and Shufersal's before page records existed) reads its kinds in full when it ended with
  no error and was not blocked. Second, every name the retry listed was listed by another run that read
  the name's kind. Third, the chain has nothing missing. The check record names each such retry under
  `short_of_time`, and it raises no alert.

  A run vouches for the retry's names when it read the whole list on its own, or when, with the retry's
  own pages left out, the other runs' pages join up into a full reading and one of the run's blocks
  carries that reading's end further than the blocks joined before it (collector.pages.read_in_full
  names those runs; blocks are joined from the front of the list, the furthest-reaching first among
  those that start together). It vouches only for names of a kind it read. So a run that read only part
  of the list vouches only when its pages carry the joined reading further than the pages joined before
  them. A part that the pages joined before it already cover vouches for no name, nor does any part
  when the other runs' pages do not join up into a full reading without the retry's. The retry never
  vouches for its own.

  Why these conditions. Shufersal's slow listing pages stop its PromoFull retry short most mornings, so
  without R36 a complete morning would alert. Nothing missing proves nothing on its own: a run that stops
  while reading the listing never lists the rest. A run that read the whole list proves only the list
  that was up when it read it: one made before the day's files were up lists nothing, and one made early
  lists only the stores published by then. So a name only the retry listed shows the list changed after the other
  runs read it, and the part past where the retry stopped may hold names no run listed.

  Why the retry's pages are left out, and why a whole pass vouches on its own. The joined reading names
  only the runs that moved its end on. A second whole pass moves nothing on, since the first already
  reached the end. A retry whose fresh pass read further than an earlier run before it stopped would
  push that run out of the reading. Either way, names such a run listed would go unvouched, and a
  complete morning would alert.

  A retry whose listing failed for any other reason is still a failed run, read in full or not (R4).
  Ruling R37 also adds a reason of its own: a full kind the chain collects whose pages, recorded that
  day, do not join up into a full reading is a failed run too, and the alert names what of the list no
  run read (collector.pages.unread). The reason is left out when a retry run was blocked (as R35), and a
  chain or day with no page records gets none. The check record holds, per chain, `read_in_full`: for
  each full kind the chain collects, the ids of the runs that read it in full, or null. Those are always
  the runs without page records that ended with no error and were not blocked (one that listed nothing
  included); beside them, the runs whose pages make up the joined full reading (a second whole pass adds
  nothing and is not named), or, with joining off, every whole pass in the joined reading's place.
- coverage, recorded and never alerted: the stores with a stored PriceFull that day, read from the
  file names, against the store ids in that day's latest stored Stores file, or when that day has
  none the latest stored in the seven days before. Store numbers are compared as numbers
  (Shufersal's ids are unpadded, names pad them); ids that are not numbers are left out. No store
  list, one that names no stores, or one that cannot be read makes the ratio "unknown".

The morning reads main and retry runs only. A poll run of the same day can stop on time with names
listed and not yet stored, which a later poll takes, so a poll's names never reach `missing`, `listed`
or `manifests`; `stored` counts every stored name, a poll's files included. Rulings R4, R31 and R35 to
R37 read the same runs, so a poll's block never silences R35's or R37's reason: those are dropped only
when a retry run was blocked.

The update day (ruling R39; docs/update-files.md, section 5). Given `polled` (the chains whose polls
are on, each with the update kinds its polls read), the check of a day also judges the day before,
from every manifest of that day, polls included, and the names stored that day, and writes it into its
own record as `update_day`; its alerts follow the morning's. Each chain's, in this order:

- missing: the update files of the day that no run stored and no main or retry run of that day listed
  (those were judged by that day's own check and are never reported twice), in two parts: the names a
  poll run tried and failed (`failed`), and the names a poll listed and never tried because it stopped
  on time (`not_attempted`), less those in the first part → one `missing` alert, with the two counts
  apart and up to ten names, the two parts' names sorted together (ruling R40). The never-tried names
  are emailed only for a kind with no page records that day (collector.pages.has_pages): for a kind
  with page records, Shufersal's once it polls, they are counted, not emailed, until its polls are
  designed.
- failed: an update kind no pass read in full that day (collector.pages.passes): for Shufersal, a pass
  whose pages joined up; for a chain without page records, a poll run that ended with no error and was
  not blocked, as R36 reads it. A day no poll ran fails too, so a lost schedule shows → one `failed`
  alert naming the lists. Left out when a poll run of the day was blocked: the stopped alert covers
  it (as R35).

The record's `not_tried` holds those never-tried names, per kind and sorted, a paged kind's included:
the names in a poll's `not_attempted` that are not stored, not in `missing` and not listed by a main
or retry run of the day (ruling R40). How many there are is the measure of what the time rule costs.
The quick chains' are emailed because their listings are whole in memory: a poll of a listing that
does not page reads the rest of it after its own time stop, from memory (collector.sources and
collector.run), so it lists every name of its day it did not reach, and a name left in `not_tried` is
a file of the day that no run stored. The record also holds each poll's outcome (`polls`), each kind's
passes (`passes`: the runs that read each complete one, the runs of each that a page out of order
ended unread, and the open one with what of the list it has not read), and `by_hour`, the day's stored
files of each update kind counted by the hour in their names (collector.names.hour_of; "unknown" where
it cannot be read), the measure of each chain's rhythm.
"""
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Literal

from collector.names import KINDS, hour_of, parse_file_name
from collector.pages import Pass, has_pages, passes, read_in_full, unread
from collector.run import OUT_OF_TIME
from collector.store import manifest_key, raw_key
from collector.storelist import store_ids

MAX_NAMES = 10  # names a missing alert quotes; the check record holds all of them
LOOKBACK_DAYS = 7  # days before the check's day searched for a store list when that day has none
UNKNOWN = "unknown"
FULL_KINDS = ("PriceFull", "PromoFull")  # each must be listed by some run of the day (ruling R35)
MORNING = ("main", "retry")  # the modes of the runs the morning is judged from; a poll's day is judged the next morning


@dataclass
class Alert:
    chain: str
    kind: Literal["missing", "stopped", "failed"]
    text: str


def check_day(store, slugs: list[str], day: date, kinds: Mapping[str, tuple[str, ...]] | None = None,
              polled: Mapping[str, tuple[str, ...]] | None = None) -> tuple[list[Alert], dict]:
    """The alerts for `day` and the check record: per chain, from its main and retry runs (MORNING), the
    listed and stored counts, the missing names, whether it is stopped, why its runs failed, the retry
    runs short of time that are not failed runs (rulings R36 and R37), the runs that read each full kind
    in full (ruling R37), and its coverage. `kinds` gives the kinds a chain collects; a chain it leaves
    out is held to all five. With `polled` (each chain whose polls are on, with the update kinds they
    read), the record's `update_day` is the day before judged by judge_update_day, and its alerts follow
    the morning's; without it, `update_day` is null. Reads only."""
    manifests = _manifests(store, day)
    morning: list[Alert] = []
    chains = {}
    for slug in slugs:
        expected = (kinds or {}).get(slug, KINDS)
        runs = [manifest for manifest in manifests.get(slug, []) if manifest["mode"] in MORNING]
        chain_alerts, chains[slug] = _check_chain(store, slug, day, runs, expected)
        morning += chain_alerts
    update_alerts: list[Alert] = []
    update_day = None
    if polled is not None:
        update_alerts, update_day = judge_update_day(store, polled, day - timedelta(days=1))
    alerts = morning + update_alerts
    return alerts, {"day": day.isoformat(), "chains": chains, "update_day": update_day,
                    "alerts": [asdict(alert) for alert in alerts]}


def judge_update_day(store, polled: Mapping[str, tuple[str, ...]], day: date) -> tuple[list[Alert], dict]:
    """The update day `day` judged (ruling R39), for each chain in `polled` with the update kinds its polls read, from
    that day's manifests (every mode) and stored names: the alerts, chains in `polled`'s order, and the record's
    `update_day`, `{"day": "YYYY-MM-DD", "chains": {slug: section}}`. Reads only. It judges every chain it is handed,
    so check_day's caller (collector.handler) hands only the chains whose `polled` is set, and only while the poll
    switch is on or the check event asks for the update day."""
    manifests = _manifests(store, day)
    alerts: list[Alert] = []
    chains = {}
    for slug, kinds in polled.items():
        chain_alerts, chains[slug] = _judge_updates(store, slug, day, manifests.get(slug, []), kinds)
        alerts += chain_alerts
    return alerts, {"day": day.isoformat(), "chains": chains}


def mark_alerted(store, alerts: list[Alert]) -> None:
    """Mark each chain a `stopped` alert names as alerted, its other state kept; call it only once
    the email holding the alerts has gone (ruling R26). A chain whose state no longer says stopped
    (cleared since the check read it) is left as it is."""
    for alert in alerts:
        if alert.kind == "stopped":
            state = store.read_state(alert.chain)
            if state.get("stopped"):
                store.write_state(alert.chain, state | {"alerted": True})


def stopped_alert(slug: str, state: dict) -> Alert:
    """The `stopped` alert for a chain whose state says stopped: since when and why (ruling R26)."""
    return Alert(slug, "stopped", f"{slug} is stopped since {state.get('since')}: {state.get('reason')}. "
                                  "Nothing is fetched from it until an unblock run clears it.")


def _manifests(store, day: date) -> dict[str, list[dict]]:
    """That day's manifests by chain, in key order."""
    prefix = manifest_key(day, "", "").rsplit("/", 1)[0] + "/"
    by_chain: dict[str, list[dict]] = {}
    for body in store.read_records(prefix):
        manifest = json.loads(body)
        by_chain.setdefault(manifest["chain"], []).append(manifest)
    return by_chain


def _check_chain(store, slug: str, day: date, manifests: list[dict],
                 kinds: tuple[str, ...]) -> tuple[list[Alert], dict]:
    """The chain's alerts and its part of the record."""
    alerts = []
    listed = {name for manifest in manifests for name in manifest["listed"]}
    stored = store.stored_names(slug, day)
    missing = sorted(listed - stored)
    if missing:
        alerts.append(Alert(slug, "missing", _missing_text(slug, day, missing)))
    state = store.read_state(slug)
    if state.get("stopped") and not state.get("alerted"):
        alerts.append(stopped_alert(slug, state))
    excused = _short_of_time(manifests, missing)
    failure = _failure(manifests, kinds, excused)
    if failure:
        alerts.append(Alert(slug, "failed", f"{slug}: the day's runs fell short: {failure}."))
    record = {
        "manifests": len(manifests),
        "listed": len(listed),
        "stored": len(stored),
        "missing": missing,
        "stopped": {"since": state.get("since"), "reason": state.get("reason")} if state.get("stopped") else None,
        "failed": failure,
        "short_of_time": [f"{manifest['run_id']} ({', '.join(manifest['kinds'])})" for manifest in excused],
        "read_in_full": {kind: read_in_full(manifests, kind) for kind in FULL_KINDS if kind in kinds},
        "coverage": _coverage(store, slug, day, stored),
    }
    return alerts, record


def _missing_text(slug: str, day: date, missing: list[str]) -> str:
    count = f"{len(missing)} file{'s' if len(missing) != 1 else ''}"
    return f"{slug}: {count} listed for {day.isoformat()} and not stored: {_quoted(missing)}."


def _quoted(names: list[str]) -> str:
    """The first MAX_NAMES of `names`, and how many more; the check record holds them all."""
    more = len(names) - MAX_NAMES
    tail = f", and {more} more (the check record lists them all)" if more > 0 else ""
    return f"{', '.join(names[:MAX_NAMES])}{tail}"


def _short_of_time(manifests: list[dict], missing: list[str]) -> list[dict]:
    """The retry runs whose error is the run's time stop, on a day with nothing missing, each of their
    kinds read in full and every name they listed seen by other runs (rulings R36 and R37)."""
    if missing:
        return []
    return [manifest for manifest in manifests if manifest["mode"] == "retry" and manifest["error"] == OUT_OF_TIME
            and _seen_by_others(manifests, manifest)]


def _seen_by_others(manifests: list[dict], retry: dict) -> bool:
    """Whether each kind `retry` covers was read in full that day and every name it listed was listed by
    another run that read the name's kind (ruling R37): one that read the whole list on its own, or one
    that `read_in_full` names over the other runs, the retry left out, for a block that carried that
    joined reading's end further than the blocks joined before it. A run that read only part of the list
    vouches only in the second way: a part that the pages joined before it already cover vouches for no
    name, nor does any part when the other runs' pages do not join up without the retry's. The retry
    never vouches for its own."""
    if not all(read_in_full(manifests, kind) is not None for kind in retry["kinds"]):
        return False
    others = [manifest for manifest in manifests if manifest["run_id"] != retry["run_id"]]
    seen = set()
    for kind in retry["kinds"]:
        readers = read_in_full(others, kind) or []
        vouching = [manifest for manifest in others
                    if manifest["run_id"] in readers or read_in_full([manifest], kind) is not None]
        seen |= {name for manifest in vouching for name in _of_kind(manifest["listed"], kind)}
    return set(retry["listed"]) <= seen


def _of_kind(names: Iterable[str], kind: str) -> set[str]:
    """The names of `kind`, the kind read from each name."""
    return {name for name in names if (parsed := parse_file_name(name)) and parsed.kind == kind}


def _failure(manifests: list[dict], kinds: tuple[str, ...], excused: list[dict]) -> str | None:
    """Why the chain's retry runs fall short of `kinds` (ruling R4), the `excused` ones' time stops left
    out (rulings R36 and R37), why the day lacks a full kind (ruling R35) or a full reading of one
    (ruling R37), or None when none of these holds."""
    retries = [manifest for manifest in manifests if manifest["mode"] == "retry"]
    covered = {kind for manifest in retries for kind in manifest["kinds"]}
    problems = []
    uncovered = [kind for kind in kinds if kind not in covered]
    if uncovered:
        problems.append(f"no retry run covered {', '.join(uncovered)}")
    problems += [f"retry run {manifest['run_id']} ({', '.join(manifest['kinds'])}) ended with: {manifest['error']}"
                 for manifest in retries if manifest["error"] and manifest not in excused]
    listed = {name for manifest in retries for name in manifest["listed"]}
    if retries and not listed and not any(manifest["blocked"] for manifest in retries):
        unparsed = sum(manifest["unparsed"] for manifest in retries)
        problems.append(f"the retry runs listed nothing for the day (unparsed names: {unparsed})")
    reasons = problems + _unlisted(manifests, retries, kinds) + _not_read_in_full(manifests, retries, kinds)
    return "; ".join(reasons) or None


def _unlisted(manifests: list[dict], retries: list[dict], kinds: tuple[str, ...]) -> list[str]:
    """The full kinds the chain collects that no run of the day listed (ruling R35); none when a retry
    run was blocked, which the stopped alert covers (a main run's block may be cleared before them)."""
    if any(manifest["blocked"] for manifest in retries):
        return []
    listed = {parsed.kind for manifest in manifests for name in manifest["listed"] if (parsed := parse_file_name(name))}
    return [f"no run listed a {kind} for the day" for kind in FULL_KINDS if kind in kinds and kind not in listed]


def _not_read_in_full(manifests: list[dict], retries: list[dict], kinds: tuple[str, ...]) -> list[str]:
    """The full kinds the chain collects whose pages, recorded that day, do not join up into one full
    reading, with what of the list no run read (ruling R37). None for a kind no manifest of the day
    recorded pages of (other chains, and a deploy day's runs before page records), and none when a
    retry run was blocked, which the stopped alert covers (as R35)."""
    if any(retry["blocked"] for retry in retries):
        return []
    return [f"the {kind} list was not read in full: {unread(manifests, kind)}" for kind in FULL_KINDS
            if kind in kinds and has_pages(manifests, kind) and read_in_full(manifests, kind) is None]


def _judge_updates(store, slug: str, day: date, manifests: list[dict],
                   kinds: tuple[str, ...]) -> tuple[list[Alert], dict]:
    """The chain's update-day alerts and its section of the record (rulings R39 and R40): see the module's docstring."""
    polls = [manifest for manifest in manifests if manifest["mode"] == "poll"]
    stored_names = store.stored_names(slug, day)
    listed_by_morning = {name for manifest in manifests if manifest["mode"] in MORNING for name in manifest["listed"]}
    unstored = sorted({name for poll in polls for name in poll["failed"]} - stored_names - listed_by_morning)
    untried = ({name for poll in polls for name in poll["not_attempted"]} - stored_names - set(unstored)
               - listed_by_morning)
    not_tried = {kind: sorted(_of_kind(untried, kind)) for kind in kinds}
    emailed = [name for kind in kinds if not has_pages(manifests, kind) for name in not_tried[kind]]
    cut = {kind: passes(manifests, kind) for kind in kinds}
    unread_kinds = [kind for kind in kinds if all(one.read_by is None for one in cut[kind])]
    if any(poll["blocked"] for poll in polls):  # the stopped alert covers the day (as R35)
        unread_kinds = []
    alerts = [Alert(slug, "missing", _lost_text(slug, day, unstored, emailed))] if unstored or emailed else []
    if unread_kinds:
        alerts.append(Alert(slug, "failed", _unread_text(slug, day, unread_kinds)))
    section = {
        "polls": [{"run_id": poll["run_id"], "kinds": poll["kinds"], "listed": len(poll["listed"]),
                   "stored": len(poll["files"]), "failed": len(poll["failed"]),
                   "not_attempted": len(poll["not_attempted"]), "error": poll["error"], "blocked": poll["blocked"]}
                  for poll in polls],
        "passes": {kind: _passes_record(cut[kind], kind) for kind in kinds},
        "missing": unstored,
        "not_tried": not_tried,
        "by_hour": {kind: _by_hour(stored_names, kind) for kind in kinds},
        "failed": unread_kinds or None,
    }
    return alerts, section


def _passes_record(cut: list[Pass], kind: str) -> dict:
    """The day's passes over `kind`'s list: the runs that read each complete one, the runs of each a page out of order
    ended unread, and the open one, with what of the list it has not read (None without page records)."""
    last = cut[-1] if cut and cut[-1].open else None
    return {
        "complete": [one.read_by for one in cut if one.read_by is not None],
        "out_of_order": [[run["run_id"] for run in one.runs]
                         for one in cut if one.read_by is None and one.out_of_order],
        "open": None if last is None else {"runs": [run["run_id"] for run in last.runs],
                                           "unread": unread(last.runs, kind) if has_pages(last.runs, kind) else None},
    }


def _by_hour(stored_names: set[str], kind: str) -> dict[str, int]:
    """The day's stored names of `kind` counted by the hour in each (collector.names.hour_of), "unknown" where it cannot
    be read, in key order."""
    hours = Counter(hour_of(name) or UNKNOWN for name in _of_kind(stored_names, kind))
    return dict(sorted(hours.items()))


def _lost_text(slug: str, day: date, failed: list[str], untried: list[str]) -> str:
    """The update day's `missing` sentence (ruling R40): the files a poll tried and failed and those a poll stopped on
    time before reaching, counted apart, an empty part left out, and the names of both sorted together."""
    tried, never = len(failed), len(untried)
    count = f"{tried + never} update file{'s' if tried + never != 1 else ''}"
    parts = [f"{tried} tried and failed"] if tried else []
    if never:
        parts.append(f"{never} never tried: a poll stopped on time before reaching {'it' if never == 1 else 'them'}")
    return (f"{slug}: {count} listed on {day.isoformat()} and not stored ({', '.join(parts)}): "
            f"{_quoted(sorted([*failed, *untried]))}.")


def _unread_text(slug: str, day: date, kinds: list[str]) -> str:
    lists = f"the {' and '.join(kinds)} list{'s' if len(kinds) > 1 else ''}"
    return f"{slug}: no poll run read {lists} in full on {day.isoformat()}."


def _coverage(store, slug: str, day: date, stored: set[str]) -> dict:
    """Stores with a stored PriceFull against the store list; see the module's docstring."""
    published = {int(name.store) for name in map(parse_file_name, stored) if name and name.kind == "PriceFull"}
    coverage = {"published": len(published), "expected": None, "ratio": UNKNOWN, "store_list": None, "note": None}
    key = _store_list(store, slug, day, stored)
    if key is None:
        return coverage | {"note": f"no Stores file stored from {day - timedelta(days=LOOKBACK_DAYS)} to {day}"}
    coverage["store_list"] = key
    try:
        expected = {int(i) for i in store_ids(store.read_raw(key)) if i.isascii() and i.isdigit()}
    except Exception as exc:  # coverage is a record only: an odd store list must not cost the alerts
        return coverage | {"note": f"the store list could not be read: {type(exc).__name__}: {exc}"}
    if not expected:
        return coverage | {"note": "the store list names no stores"}
    return coverage | {"expected": len(expected), "ratio": round(len(published & expected) / len(expected), 4)}


def _store_list(store, slug: str, day: date, stored: set[str]) -> str | None:
    """The key of the latest Stores file stored for `day`, else for the nearest of the days before."""
    for back in range(LOOKBACK_DAYS + 1):
        on = day - timedelta(days=back)
        names = stored if back == 0 else store.stored_names(slug, on)
        lists = sorted(name for name in names if (parsed := parse_file_name(name)) and parsed.kind == "Stores")
        if lists:
            return raw_key(slug, on, lists[-1])
    return None

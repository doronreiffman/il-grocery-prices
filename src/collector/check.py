"""The morning check: what each chain listed that day and did not store, which chains are stopped,
and which runs failed (docs/collector.md, "How a morning runs", steps 4 and 5, and "Alerts").

For each chain, from that day's manifests (every run's, main and retry alike) and the bucket:

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
  (OUT_OF_TIME, matched exactly) is not a failed run when each kind it covers was read in full that
  day (collector.pages.read_in_full: the pages the day's runs read join up from page 1 to the last
  page; a run whose manifest holds no page records, as other chains' and Shufersal's before page
  records, reads its kinds in full when it ended with no error and was not blocked), every name the
  retry listed was listed by another run that read the name's kind, and the chain has nothing
  missing. A run read the kind when it is among the runs whose readings join up into a full reading
  with the retry's pages left out, or when it read the whole list on its own; a run that read only
  part of the list vouches for no name, and the retry never vouches for its own. The check record
  names each such run under `short_of_time`; it raises no alert. Shufersal's slow listing pages stop
  its PromoFull retry short most mornings, and "nothing missing" alone proves nothing: a run that
  stops while reading the listing never lists the rest. A run proves only the list that was up when
  it read it: one made before the day's files were up lists nothing, and one made early lists only
  the stores published by then. So a name only the retry listed shows the list changed after the
  other runs read it, and the part past where the retry stopped may hold names no run listed. The
  joined reading names only the runs that moved it on: it leaves out a second whole pass, and a run
  whose reading the retry's own went further than, though each listed what it saw. Hence the reading
  without the retry's pages, and a whole pass vouching on its own. A retry whose listing failed for
  any other reason is still a failed run, read in full or not (R4). Ruling R37 also: a full kind the
  chain collects whose pages, recorded that day, do not join up into a full reading is a failed run
  too, the alert naming what of the list no run read (collector.pages.unread), unless a retry run
  was blocked (as R35); a chain or day with no page records gets no such reason. The check record
  holds, per chain, `read_in_full`: for each full kind it collects, the ids of the runs whose
  readings joined up, or null.
- coverage, recorded and never alerted: the stores with a stored PriceFull that day, read from the
  file names, against the store ids in that day's latest stored Stores file, or when that day has
  none the latest stored in the seven days before. Store numbers are compared as numbers
  (Shufersal's ids are unpadded, names pad them); ids that are not numbers are left out. No store
  list, one that names no stores, or one that cannot be read makes the ratio "unknown".
"""
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Literal

from collector.names import KINDS, parse_file_name
from collector.pages import has_pages, read_in_full, unread
from collector.run import OUT_OF_TIME
from collector.store import manifest_key, raw_key
from collector.storelist import store_ids

MAX_NAMES = 10  # names a missing alert quotes; the check record holds all of them
LOOKBACK_DAYS = 7  # days before the check's day searched for a store list when that day has none
UNKNOWN = "unknown"
FULL_KINDS = ("PriceFull", "PromoFull")  # each must be listed by some run of the day (ruling R35)


@dataclass
class Alert:
    chain: str
    kind: Literal["missing", "stopped", "failed"]
    text: str


def check_day(store, slugs: list[str], day: date,
              kinds: Mapping[str, tuple[str, ...]] | None = None) -> tuple[list[Alert], dict]:
    """The alerts for `day` and the check record: per chain, the listed and stored counts, the
    missing names, whether it is stopped, why its runs failed, the retry runs short of time that are
    not failed runs (rulings R36 and R37), the runs that read each full kind in full (ruling R37), and
    its coverage. `kinds` gives the kinds a chain collects; a chain it leaves out is held to all five.
    Reads only."""
    manifests = _manifests(store, day)
    alerts: list[Alert] = []
    chains = {}
    for slug in slugs:
        expected = (kinds or {}).get(slug, KINDS)
        chain_alerts, chains[slug] = _check_chain(store, slug, day, manifests.get(slug, []), expected)
        alerts += chain_alerts
    return alerts, {"day": day.isoformat(), "chains": chains, "alerts": [asdict(alert) for alert in alerts]}


def mark_alerted(store, alerts: list[Alert]) -> None:
    """Mark each chain a `stopped` alert names as alerted, its other state kept; call it only once
    the email holding the alerts has gone (ruling R26). A chain whose state no longer says stopped
    (cleared since the check read it) is left as it is."""
    for alert in alerts:
        if alert.kind == "stopped":
            state = store.read_state(alert.chain)
            if state.get("stopped"):
                store.write_state(alert.chain, state | {"alerted": True})


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
        alerts.append(Alert(slug, "stopped", f"{slug} is stopped since {state.get('since')}: {state.get('reason')}. "
                                             "Nothing is fetched from it until an unblock run clears it."))
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
    more = len(missing) - MAX_NAMES
    tail = f", and {more} more (the check record lists them all)" if more > 0 else ""
    return f"{slug}: {count} listed for {day.isoformat()} and not stored: {', '.join(missing[:MAX_NAMES])}{tail}."


def _short_of_time(manifests: list[dict], missing: list[str]) -> list[dict]:
    """The retry runs whose error is the run's time stop, on a day with nothing missing, each of their
    kinds read in full and every name they listed seen by other runs (rulings R36 and R37)."""
    if missing:
        return []
    return [manifest for manifest in manifests if manifest["mode"] == "retry" and manifest["error"] == OUT_OF_TIME
            and _seen_by_others(manifests, manifest)]


def _seen_by_others(manifests: list[dict], retry: dict) -> bool:
    """Whether each kind `retry` covers was read in full that day and every name it listed was listed by
    another run that read the name's kind: one among the runs whose readings join up into a full
    reading with the retry's pages left out, or one that read the whole list on its own (ruling R37).
    Neither a run that read only part of the list nor the retry itself vouches for a name."""
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


def _of_kind(names: list[str], kind: str) -> set[str]:
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

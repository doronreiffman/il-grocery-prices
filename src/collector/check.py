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
- failed (ruling R4): that day's retry manifests do not together cover all five kinds (Shufersal
  runs as three invocations), or one of them has an error → one `failed` alert. A retry manifest
  that is blocked with no error is not a failed run: the `stopped` alert covers it. A main run's
  error is left to the retry run.
- coverage, recorded and never alerted: the stores with a stored PriceFull that day, read from the
  file names, against the store ids in that day's latest stored Stores file, or when that day has
  none the latest stored in the seven days before. Store numbers are compared as numbers
  (Shufersal's ids are unpadded, names pad them); ids that are not numbers are left out. No store
  list, one that names no stores, or one that cannot be read makes the ratio "unknown".
"""
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Literal

from collector.names import KINDS, parse_file_name
from collector.store import manifest_key, raw_key
from collector.storelist import store_ids

MAX_NAMES = 10  # names a missing alert quotes; the check record holds all of them
LOOKBACK_DAYS = 7  # days before the check's day searched for a store list when that day has none
UNKNOWN = "unknown"


@dataclass
class Alert:
    chain: str
    kind: Literal["missing", "stopped", "failed"]
    text: str


def check_day(store, slugs: list[str], day: date) -> tuple[list[Alert], dict]:
    """The alerts for `day` and the check record: per chain, the listed and stored counts, the
    missing names, whether it is stopped, why its runs failed, and its coverage. Reads only."""
    manifests = _manifests(store, day)
    alerts: list[Alert] = []
    chains = {}
    for slug in slugs:
        chain_alerts, chains[slug] = _check_chain(store, slug, day, manifests.get(slug, []))
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


def _check_chain(store, slug: str, day: date, manifests: list[dict]) -> tuple[list[Alert], dict]:
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
    failure = _failure(manifests)
    if failure:
        alerts.append(Alert(slug, "failed", f"{slug}: a retry run is missing or failed: {failure}."))
    record = {
        "manifests": len(manifests),
        "listed": len(listed),
        "stored": len(stored),
        "missing": missing,
        "stopped": {"since": state.get("since"), "reason": state.get("reason")} if state.get("stopped") else None,
        "failed": failure,
        "coverage": _coverage(store, slug, day, stored),
    }
    return alerts, record


def _missing_text(slug: str, day: date, missing: list[str]) -> str:
    count = f"{len(missing)} file{'s' if len(missing) != 1 else ''}"
    more = len(missing) - MAX_NAMES
    tail = f", and {more} more (the check record lists them all)" if more > 0 else ""
    return f"{slug}: {count} listed for {day.isoformat()} and not stored: {', '.join(missing[:MAX_NAMES])}{tail}."


def _failure(manifests: list[dict]) -> str | None:
    """Why the chain's retry runs fall short (ruling R4), or None when they do not."""
    retries = [manifest for manifest in manifests if manifest["mode"] == "retry"]
    covered = {kind for manifest in retries for kind in manifest["kinds"]}
    problems = []
    uncovered = [kind for kind in KINDS if kind not in covered]
    if uncovered:
        problems.append(f"no retry run covered {', '.join(uncovered)}")
    problems += [f"retry run {manifest['run_id']} ({', '.join(manifest['kinds'])}) ended with: {manifest['error']}"
                 for manifest in retries if manifest["error"]]
    return "; ".join(problems) or None


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

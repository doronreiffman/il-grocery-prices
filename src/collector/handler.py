"""The Lambda's entry point: one invocation per chain and mode (docs/collector.md, "How a morning
runs", and "Alerts"; docs/update-files.md for the polls). EventBridge Scheduler sends main, retry,
poll and the plain check; the owner sends unblock, and a check that asks for the update day.

    {"mode": "main", "chain": "<slug>", "kinds": [...]}    collect the chain's files for the Israel date
    {"mode": "retry", "chain": "<slug>", "kinds": [...]}   the same, hours later: what is still not stored
    {"mode": "poll", "chain": "<slug>", "kinds": [...]}    the same through the day, for update kinds it polls
    {"mode": "check"}                                      check every chain's day, email any alerts, ping
    {"mode": "check", "update_day": true}                  the same, and the day before's update files judged
    {"mode": "unblock", "chain": "<slug>"}                 clear the chain's stopped latch

`kinds` is optional for main and retry: the chain's kinds when absent (Shufersal's three, the others'
five). A poll event must name its kinds, some of the chain's `polled` (a default would hand Shufersal
both update kinds in one run). The day is the Israel calendar date when the invocation starts. main
and retry never email: their errors are logged and the check judges what they left. A poll run that
stops a chain (it latched it: blocked, and not "stopped earlier") emails the chain's stopped alert at
once, since the next check is the next day's, after that morning's runs have done nothing; the chain
is marked alerted once that email has gone (ruling R26), so the check does not send it again. If the
email fails, the invocation fails and nothing is marked, and the check sends it. No other collecting
run emails, and a poll of a chain stopped earlier sends nothing: that stop is the check's to alert.

The check writes its record whatever it finds, sends one email only when there are alerts, marks the
stopped chains it named as alerted once that email has gone (ruling R26), then pings healthchecks.io;
a failed ping is logged, not raised. If the check itself fails, the email included, nothing is marked
and nothing pings, and healthchecks.io emails about the missing ping. The ping's User-Agent names the
project and its URL, never the contact email (ruling R27). While the poll switch is on, or when the
check event's `update_day` is true (the JSON value true, nothing else), the check also judges the day
before's update files for the chains whose `polled` is set (ruling R39; collector.check.judge_update_day)
and its alerts go in the same email; otherwise the record's `update_day` is null.

Environment: BUCKET, USER_AGENT, ALERT_TOPIC_ARN, HEALTHCHECK_URL, POLL_SCHEDULE_STATE (each
required; the poll switch, ENABLED or DISABLED, as template.yaml's PollScheduleState sets it),
RETENTION_DAYS (default 3650).
"""
import hashlib
import json
import logging
import os
import re
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from collector.chains import CHAINS, Chain, source_for
from collector.check import Alert, check_day, mark_alerted, stopped_alert
from collector.http import Http, build_opener, check_user_agent
from collector.run import STOPPED_EARLIER, collect_chain, new_run_id
from collector.store import RETENTION_DAYS, S3Store, check_key, manifest_key

# INFO on the package's logger itself, so the runs' summaries reach CloudWatch whatever level the
# runtime gives the root logger (ruling R28); the records go to the runtime's handler on the root.
logging.getLogger("collector").setLevel(logging.INFO)
log = logging.getLogger(__name__)

ISRAEL = ZoneInfo("Asia/Jerusalem")
REQUIRED = ("BUCKET", "USER_AGENT", "ALERT_TOPIC_ARN", "HEALTHCHECK_URL", "POLL_SCHEDULE_STATE")
POLL_STATES = ("ENABLED", "DISABLED")  # the poll switch's values: template.yaml's PollScheduleState
COLLECTING = ("main", "retry", "poll")
SUBJECT_LIMIT = 100  # SNS takes a subject of fewer than 100 characters
PING_TIMEOUT = 10  # seconds
_PROJECT_URL = re.compile(r"\+https://[^\s;()@]+")


def code_sha(package: Path) -> str:
    """The code's fingerprint (ruling R25): the first 12 hex of a SHA-256 over every .py file under
    `package`, subpackages included, in order of their paths relative to it (with "/"); each file
    adds its path, a NUL byte and the SHA-256 of its bytes. Run it over any commit's src/collector/
    to find the code that wrote a manifest."""
    digest = hashlib.sha256()
    for rel in sorted(path.relative_to(package).as_posix() for path in package.rglob("*.py")):
        digest.update(rel.encode() + b"\0" + hashlib.sha256((package / rel).read_bytes()).digest())
    return digest.hexdigest()[:12]


CODE_SHA = code_sha(Path(__file__).parent)  # once per cold start


@dataclass(frozen=True)
class Config:
    bucket: str
    user_agent: str
    alert_topic_arn: str
    healthcheck_url: str
    retention_days: int
    polls_on: bool = False  # the poll switch: the check judges the update day while it is on

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        missing = [name for name in REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ValueError(f"missing environment variables: {', '.join(missing)}")
        polls = env["POLL_SCHEDULE_STATE"]
        if polls not in POLL_STATES:
            raise ValueError(f"POLL_SCHEDULE_STATE must be {' or '.join(POLL_STATES)}, not {polls!r}")
        return cls(bucket=env["BUCKET"], user_agent=check_user_agent(env["USER_AGENT"]),
                   alert_topic_arn=env["ALERT_TOPIC_ARN"], healthcheck_url=env["HEALTHCHECK_URL"],
                   retention_days=int(env.get("RETENTION_DAYS", RETENTION_DAYS)), polls_on=polls == "ENABLED")


@dataclass
class Deps:
    """What run() works through. `http_for(slug)` gives a fresh Http (own cookies) per chain run;
    `publish(subject, body)` sends the alert email; `ping(url, message)` reports to healthchecks.io;
    `time_left()` gives the invocation's seconds left; `code_sha` goes in every manifest and record."""

    store: Any
    http_for: Callable[[str], Http]
    publish: Callable[[str, str], None]
    ping: Callable[[str, str], None]
    time_left: Callable[[], float]
    code_sha: str


def run(cfg: Config, event: dict, deps: Deps, now: datetime) -> dict:
    """Do what `event` asks (see the module's docstring); `now` is the invocation's start, aware.
    Raises ValueError for an unknown mode or chain. Returns a summary, also logged."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must carry a time zone")
    mode = event.get("mode") if isinstance(event, dict) else None
    if mode not in (*COLLECTING, "check", "unblock"):
        raise ValueError(f"the event's mode must be main, retry, poll, check or unblock, not {mode!r} "
                         f"(event {event!r})")
    day = now.astimezone(ISRAEL).date()
    if mode == "check":
        summary = _check(cfg, event, deps, day, now)
    elif mode == "unblock":
        summary = _unblock(_chain(event), deps)
    else:
        summary = _collect(_chain(event), event, mode, deps, day, now)
    log.info(json.dumps(summary, sort_keys=True))
    return summary


def _chain(event: dict) -> Chain:
    slug = event.get("chain")
    if not isinstance(slug, str) or slug not in CHAINS:
        raise ValueError(f"unknown chain {slug!r}: one of {', '.join(CHAINS)}")
    return CHAINS[slug]


def _collect(chain: Chain, event: dict, mode: str, deps: Deps, day: date, now: datetime) -> dict:
    if mode == "poll" and "kinds" not in event:  # a default of `polled` would hand Shufersal both kinds in one run
        raise ValueError(f"a poll event names its kinds (event {event!r})")
    kinds = tuple(event["kinds"]) if "kinds" in event else chain.kinds
    run_id = new_run_id(now, mode)
    result = collect_chain(chain, source_for(chain), deps.http_for(chain.slug), deps.store, day, run_id, mode,
                           kinds, deps.time_left, _clock(now, deps.time_left), deps.code_sha)
    for name, why in result.failed.items():
        log.warning("%s %s not stored: %s", chain.slug, name, why)
    if result.blocked:
        log.error("%s blocked: %s", chain.slug, result.blocked)
    if result.error:
        log.error("%s run %s stopped: %s", chain.slug, run_id, result.error)
    if mode == "poll" and result.blocked and result.blocked != STOPPED_EARLIER:  # this run latched the chain
        _stopped_by_poll(chain.slug, deps, day, run_id)
    return {"mode": mode, "chain": chain.slug, "day": day.isoformat(), "run_id": run_id, "kinds": result.kinds,
            "listed": len(result.listed), "stored": len(result.files), "failed": len(result.failed),
            "not_attempted": len(result.not_attempted), "blocked": result.blocked, "error": result.error}


def _stopped_by_poll(slug: str, deps: Deps, day: date, run_id: str) -> None:
    """Email the stopped alert of a chain a poll run just latched, at once: the next check is the next day's. The chain
    is marked alerted only once the email has gone (ruling R26); a failed email is raised and marks nothing, so the
    check sends it. A latch cleared since, or already alerted, sends nothing."""
    state = deps.store.read_state(slug)
    if not state.get("stopped") or state.get("alerted"):
        return
    alert = stopped_alert(slug, state)
    subject, body = poll_message(day, alert, manifest_key(day, slug, run_id))
    log.warning("%s\n%s", subject, body)  # logged first: the email can still fail
    deps.publish(subject, body)
    mark_alerted(deps.store, [alert])  # only now: a failed email leaves the chain to the check (R26)


def _clock(start: datetime, time_left: Callable[[], float]) -> Callable[[], datetime]:
    """The run's clock: `start` moved on by the seconds Lambda's countdown has run since."""
    left_at_start = time_left()
    return lambda: start + timedelta(seconds=left_at_start - time_left())


def _check(cfg: Config, event: dict, deps: Deps, day: date, now: datetime) -> dict:
    # The update day while the polls are on, or when a manual check asks (rollout step 2); only chains that poll.
    polled = ({slug: c.polled for slug, c in CHAINS.items() if c.polled}
              if cfg.polls_on or event.get("update_day") is True else None)
    alerts, record = check_day(deps.store, list(CHAINS), day, kinds={slug: c.kinds for slug, c in CHAINS.items()},
                               polled=polled)
    run_id = new_run_id(now, "check")
    key = check_key(day, run_id)
    if alerts:
        subject, body = message(day, alerts, key)
        log.warning("%s\n%s", subject, body)  # logged first: the record write or the email can still fail
    record |= {"run_id": run_id, "checked_at": now.astimezone(timezone.utc).isoformat(), "code_sha": deps.code_sha}
    deps.store.put_record(key, json.dumps(record, sort_keys=True, indent=1).encode(), now)
    if alerts:
        deps.publish(subject, body)
        mark_alerted(deps.store, alerts)  # only now: a failed email leaves them to alert again (R26)
    summary = {"mode": "check", "day": day.isoformat(), "run_id": run_id, "record": key, "alerts": len(alerts)}
    try:
        deps.ping(cfg.healthcheck_url, json.dumps(summary, sort_keys=True))
    except Exception as exc:  # the morning is checked and recorded; a missed ping makes healthchecks.io email
        log.warning("health-check ping failed: %s: %s", type(exc).__name__, exc)
    return summary


def message(day: date, alerts: list[Alert], record_key: str) -> tuple[str, str]:
    """The alert email: a subject under SNS's 100 characters, and a body listing every alert."""
    count = f"{len(alerts)} alert{'s' if len(alerts) != 1 else ''}"
    subject = f"il-grocery-prices {day.isoformat()}: {count}"
    named = f"{subject} ({', '.join(dict.fromkeys(alert.chain for alert in alerts))})"
    if len(named) < SUBJECT_LIMIT:
        subject = named
    lines = [f"The check of {day.isoformat()} (Israel date) found {count}:", ""]
    lines += [f"- {alert.text}" for alert in alerts]
    lines += ["", f"The check record: {record_key}"]
    return subject, "\n".join(lines)


def poll_message(day: date, alert: Alert, manifest_key: str) -> tuple[str, str]:
    """A poll run's stopped email: the subject names the chain (SNS's 100 characters hold every chain's), the body
    holds the check's stopped alert and the run's manifest."""
    subject = f"il-grocery-prices {day.isoformat()}: {alert.chain} stopped by a poll run"
    lines = [f"A poll run of {day.isoformat()} (Israel date) stopped a chain:", "", f"- {alert.text}", "",
             f"The run's manifest: {manifest_key}"]
    return subject, "\n".join(lines)


def _unblock(chain: Chain, deps: Deps) -> dict:
    was = deps.store.read_state(chain.slug)
    deps.store.write_state(chain.slug, {})
    return {"mode": "unblock", "chain": chain.slug, "was": was}


def ping(url: str, message: str, user_agent: str, opener: urllib.request.OpenerDirector | None = None) -> None:
    """POST `message` to the healthchecks.io ping URL, identified, through an opener with no proxy.
    Raises when the ping fails; run() logs it."""
    opener = opener if opener is not None else build_opener()
    request = urllib.request.Request(url, data=message.encode(), method="POST", headers={"User-Agent": user_agent})
    with opener.open(request, timeout=PING_TIMEOUT) as answer:
        answer.read()


def ping_user_agent(user_agent: str) -> str:
    """The deploy's User-Agent without its contact email, for healthchecks.io (ruling R27):
    `il-grocery-prices/<version> (+<repo URL>)`, built from the first word and the `+https://` URL.
    A first word holding an @ gives way to the project's name."""
    words = user_agent.split()
    product = words[0] if words and "@" not in words[0] else "il-grocery-prices"
    url = _PROJECT_URL.search(user_agent)
    return f"{product} ({url[0]})" if url else product


def deps_for(cfg: Config, context, s3, sns) -> Deps:
    """The production Deps: the bucket through the boto3 client `s3`, the email through `sns`, a fresh
    Http (own cookies) for each chain run (ruling R6) that waits the chain's timeout, the ping identified
    without the contact email (R27), and Lambda's countdown."""
    return Deps(
        store=S3Store(s3, cfg.bucket, cfg.retention_days),
        http_for=lambda slug: Http(cfg.user_agent, timeout=CHAINS[slug].timeout),
        publish=lambda subject, body: sns.publish(TopicArn=cfg.alert_topic_arn, Subject=subject, Message=body),
        ping=partial(ping, user_agent=ping_user_agent(cfg.user_agent)),
        time_left=lambda: context.get_remaining_time_in_millis() / 1000,
        code_sha=CODE_SHA,
    )


def handler(event, context):  # pragma: no cover - the boto3 clients and the wall clock; deps_for and run() are tested
    import boto3

    cfg = Config.from_env(os.environ)
    return run(cfg, event, deps_for(cfg, context, boto3.client("s3"), boto3.client("sns")), datetime.now(timezone.utc))

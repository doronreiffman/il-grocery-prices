"""The Lambda's entry point: events to runs, the check's email and ping, unblock, the config and the
code's fingerprint.

run() is driven with a Deps of fakes: a MemoryStore, a recorded publish and ping, a time_left the
test moves, and an http_for that hands out a marked Http per chain. Some tests replace collect_chain
to see what run() hands it; others run the real run loop over a fake source.
"""
import dataclasses
import hashlib
import http.client
import io
import json
import logging
import re
import urllib.error
import urllib.request
import urllib.response
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
import pytest
from botocore.stub import Stubber

import collector
from collector import handler as handler_module
from collector.chains import CHAINS
from collector.check import Alert
from collector.handler import CODE_SHA, Config, Deps, code_sha, deps_for, message, ping, ping_user_agent, run
from collector.http import Blocked, Http, HttpError, build_opener
from collector.names import KINDS, parse_file_name
from collector.run import RunResult, manifest_bytes
from collector.sources import Listed
from collector.sources.carrefour import CarrefourSource
from collector.sources.ncr import NcrSource
from collector.sources.shufersal import ShufersalSource
from collector.store import MemoryStore, S3Store, check_key, manifest_key, raw_key

FIXTURES = Path(__file__).parent / "fixtures"
UA = "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)"
ISRAEL = ZoneInfo("Asia/Jerusalem")
NOW = datetime(2026, 10, 31, 6, 30, tzinfo=ISRAEL)
DAY = date(2026, 10, 31)
HEALTHCHECK = "https://hc-ping.example/0000-test"
TOPIC = "arn:aws:sns:il-central-1:000000000000:alerts"
CFG = Config(bucket="bucket", user_agent=UA, alert_topic_arn=TOPIC, healthcheck_url=HEALTHCHECK, retention_days=3650)
ENV = {"BUCKET": "bucket", "USER_AGENT": UA, "ALERT_TOPIC_ARN": TOPIC, "HEALTHCHECK_URL": HEALTHCHECK}
SHA = "0123456789ab"

PRICE_XML = (FIXTURES / "shufersal" / "PriceFull7290027600007-001-030-20261031-030000.gz").read_bytes()
PRICE = "PriceFull7290027600007-001-030-20261031-030000.gz"
PROMO_FULL = "PromoFull7290027600007-001-030-20261031-030000.gz"  # its body is PRICE_XML: the check reads names only
PRICE_2 = "PriceFull7290027600007-001-031-20261031-030000.gz"


class Recorder:
    """A publish or a ping: records each call in `calls` and in the shared `events`; raises
    `raises` when given."""

    def __init__(self, name, events, raises=None):
        self.name, self.events, self.raises = name, events, raises
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        self.events.append(self.name)
        if self.raises is not None:
            raise self.raises


class EventStore(MemoryStore):
    """A MemoryStore that logs its record and state writes in the shared `events`."""

    def __init__(self, events):
        super().__init__()
        self.events = events

    def put_record(self, key, body, now):
        self.events.append(("record", key))
        super().put_record(key, body, now)

    def write_state(self, slug, state):
        self.events.append(("state", slug))
        super().write_state(slug, state)


class Countdown:
    """Seconds left in the invocation; tests move it."""

    def __init__(self, left=900.0):
        self.left = left

    def __call__(self):
        return self.left


def make_deps(store=None, publish_raises=None, ping_raises=None, time_left=None):
    events = []
    https = {}

    def http_for(slug):
        https.setdefault(slug, []).append(Http(UA, opener=build_opener(), sleep=lambda s: None))
        return https[slug][-1]

    deps = Deps(store=store if store is not None else EventStore(events), http_for=http_for,
                publish=Recorder("publish", events, publish_raises), ping=Recorder("ping", events, ping_raises),
                time_left=time_left or Countdown(), code_sha=SHA)
    deps.events, deps.https = events, https
    return deps


class CollectRecorder:
    """In place of collect_chain: records its arguments and returns an empty result."""

    def __init__(self):
        self.calls = []

    def __call__(self, chain, source, http, store, day, run_id, mode, kinds, time_left, now, code_sha):
        self.calls.append(dict(chain=chain, source=source, http=http, store=store, day=day, run_id=run_id,
                               mode=mode, kinds=kinds, time_left=time_left, now=now, code_sha=code_sha))
        return RunResult(chain.slug, run_id, mode, day, list(kinds))


@pytest.fixture
def collect(monkeypatch):
    recorder = CollectRecorder()
    monkeypatch.setattr(handler_module, "collect_chain", recorder)
    return recorder


class FakeSource:
    """Lists `names`; download gives the fixture's gzip, or raises what `answers[name]` holds."""

    unparsed = 0

    def __init__(self, names, answers=None):
        self.names, self.answers = names, answers or {}

    def listing(self, http, kinds):
        for name in self.names:
            yield Listed(parse_file_name(name), f"https://portal.example/{name}")

    def download(self, http, item):
        answer = self.answers.get(item.name.raw)
        if answer is not None:
            raise answer
        return PRICE_XML


def clean_day(store, day=DAY):
    """Every chain's retry ran over the kinds that chain collects (Shufersal three, the others five) and
    listed the day's PriceFull and PromoFull, stored (a retry run that lists nothing is a failed run:
    ruling R31; each full kind is listed by some run: ruling R35)."""
    for slug in CHAINS:
        result = RunResult(slug, f"073000Z-retry-{slug[:4]}", "retry", day, list(CHAINS[slug].kinds), listed=[PRICE, PROMO_FULL])
        store.put_record(manifest_key(day, slug, result.run_id), manifest_bytes(result, SHA), NOW)
        for name in (PRICE, PROMO_FULL):
            store.put_raw(raw_key(slug, day, name), PRICE_XML, NOW)


# ---- main and retry ----

def test_main_runs_the_chain_with_every_kind_by_default(collect):
    deps = make_deps()
    summary = run(CFG, {"mode": "main", "chain": "ramilevy"}, deps, NOW)
    [call] = collect.calls
    assert call["chain"] is CHAINS["ramilevy"]
    assert isinstance(call["source"], NcrSource) and call["source"].username == "RamiLevi"
    assert call["http"] is deps.https["ramilevy"][0]
    assert call["store"] is deps.store
    assert call["day"] == DAY
    assert call["mode"] == "main"
    assert re.fullmatch(r"043000Z-main-[0-9a-f]{4}", call["run_id"])
    assert call["kinds"] == KINDS
    assert call["time_left"] is deps.time_left
    assert call["now"]() == NOW and call["now"]().utcoffset() is not None
    assert call["code_sha"] == SHA
    assert summary["run_id"] == call["run_id"]


def test_retry_runs_the_events_kinds(collect):
    deps = make_deps()
    run(CFG, {"mode": "retry", "chain": "shufersal", "kinds": ["PromoFull"]}, deps, NOW)
    [call] = collect.calls
    assert isinstance(call["source"], ShufersalSource)
    assert call["mode"] == "retry" and call["run_id"].startswith("043000Z-retry-")
    assert call["kinds"] == ("PromoFull",)


def test_a_run_without_kinds_takes_the_kinds_its_chain_collects(collect):
    run(CFG, {"mode": "main", "chain": "shufersal"}, make_deps(), NOW)
    [call] = collect.calls
    assert call["kinds"] == ("Stores", "PriceFull", "PromoFull")


def test_each_run_gets_a_fresh_source_and_http(collect):
    deps = make_deps()
    run(CFG, {"mode": "main", "chain": "carrefour"}, deps, NOW)
    run(CFG, {"mode": "main", "chain": "carrefour"}, deps, NOW)
    first, second = collect.calls
    assert isinstance(first["source"], CarrefourSource) and first["source"] is not second["source"]
    assert first["http"] is not second["http"] and len(deps.https["carrefour"]) == 2


def test_the_day_is_the_israel_date(collect):
    """23:30 UTC on 31 October is 01:30 on 1 November in Israel."""
    run(CFG, {"mode": "main", "chain": "shufersal"}, make_deps(), datetime(2026, 10, 31, 23, 30, tzinfo=timezone.utc))
    assert collect.calls[0]["day"] == date(2026, 11, 1)
    assert collect.calls[0]["run_id"].startswith("233000Z-main-")


def test_the_runs_clock_moves_with_lambdas_countdown(collect):
    countdown = Countdown(900.0)
    run(CFG, {"mode": "main", "chain": "shufersal"}, make_deps(time_left=countdown), NOW)
    now = collect.calls[0]["now"]
    assert now() == NOW
    countdown.left = 780.0
    assert now() == NOW + timedelta(seconds=120)


@pytest.mark.parametrize("event", [{"mode": "main", "chain": "shufersal"}, {"mode": "check"},
                                   {"mode": "unblock", "chain": "carrefour"}])
def test_a_naive_now_is_refused_before_anything_is_read_or_written(collect, event):
    """A naive time would be read as this machine's zone: the check would judge the wrong day and
    mark a stopped chain alerted before anything else noticed."""
    deps = make_deps()
    latch = {"stopped": True, "since": "x", "reason": "HTTP 403", "alerted": False}
    deps.store.write_state("carrefour", latch)
    deps.events.clear()
    with pytest.raises(ValueError, match="time zone"):
        run(CFG, event, deps, datetime(2026, 10, 31, 6, 30))
    assert collect.calls == [] and deps.events == []
    assert deps.store.read_state("carrefour") == latch


def test_main_end_to_end_logs_its_errors_and_never_emails(monkeypatch, caplog):
    source = FakeSource([PRICE, PRICE_2], {PRICE_2: HttpError("HTTP 500 from https://portal.example/x")})
    monkeypatch.setattr(handler_module, "source_for", lambda chain: source)
    deps = make_deps()
    with caplog.at_level(logging.INFO, logger="collector.handler"):
        summary = run(CFG, {"mode": "main", "chain": "shufersal"}, deps, NOW)
    assert summary == {"mode": "main", "chain": "shufersal", "day": "2026-10-31", "run_id": summary["run_id"],
                       "kinds": ["Stores", "PriceFull", "PromoFull"], "listed": 2, "stored": 1, "failed": 1, "not_attempted": 0,
                       "blocked": None, "error": None}
    record = json.loads(deps.store.read_raw(manifest_key(DAY, "shufersal", summary["run_id"])))
    assert record["code_sha"] == SHA and record["failed"] == {PRICE_2: "HTTP 500 from https://portal.example/x"}
    assert deps.store.read_raw(raw_key("shufersal", DAY, PRICE)) == PRICE_XML
    assert deps.publish.calls == [] and deps.ping.calls == []
    assert any(PRICE_2 in r.getMessage() and "HTTP 500" in r.getMessage() and r.levelno == logging.WARNING
               for r in caplog.records)


def test_a_blocked_run_is_logged_not_emailed(monkeypatch, caplog):
    source = FakeSource([PRICE], {PRICE: Blocked(403, "https://portal.example/x", "HTTP 403")})
    monkeypatch.setattr(handler_module, "source_for", lambda chain: source)
    deps = make_deps()
    with caplog.at_level(logging.INFO, logger="collector.handler"):
        summary = run(CFG, {"mode": "retry", "chain": "osherad"}, deps, NOW)
    assert summary["blocked"] == "HTTP 403: https://portal.example/x"
    assert deps.store.read_state("osherad")["stopped"] is True
    assert deps.publish.calls == [] and deps.ping.calls == []
    assert any("osherad" in r.getMessage() and "HTTP 403" in r.getMessage() and r.levelno == logging.ERROR
               for r in caplog.records)


def test_a_run_that_stops_with_an_error_is_logged_not_emailed(monkeypatch, caplog):
    monkeypatch.setattr(handler_module, "source_for", lambda chain: FakeSource([PRICE]))
    deps = make_deps(time_left=Countdown(30.0))
    with caplog.at_level(logging.INFO, logger="collector.handler"):
        summary = run(CFG, {"mode": "retry", "chain": "yochananof"}, deps, NOW)
    assert summary["error"] == "stopped: under 90 s left"
    assert deps.publish.calls == [] and deps.ping.calls == []
    assert any("yochananof" in r.getMessage() and "under 90 s" in r.getMessage() and r.levelno == logging.ERROR
               for r in caplog.records)


@pytest.mark.parametrize("kinds", [["pricefull"], ["Price"], ["PromoFull", "Promo"]])
def test_kinds_the_chain_does_not_collect_are_refused(monkeypatch, kinds):
    monkeypatch.setattr(handler_module, "source_for", lambda chain: FakeSource([PRICE]))
    with pytest.raises(ValueError, match="kinds"):
        run(CFG, {"mode": "main", "chain": "shufersal", "kinds": kinds}, make_deps(), NOW)


@pytest.mark.parametrize("event", [{"mode": "main"}, {"mode": "main", "chain": "victory"},
                                   {"mode": "retry", "chain": "Shufersal"}, {"mode": "unblock"},
                                   {"mode": "unblock", "chain": "victory"}])
def test_an_unknown_chain_is_refused(collect, event):
    deps = make_deps()
    with pytest.raises(ValueError, match="chain"):
        run(CFG, event, deps, NOW)
    assert collect.calls == [] and deps.store.objects == {}


@pytest.mark.parametrize("event", [{}, {"mode": "drill"}, {"mode": "MAIN", "chain": "shufersal"},
                                   {"chain": "shufersal"}, None, "check"])
def test_an_unknown_mode_is_refused(collect, event):
    deps = make_deps()
    with pytest.raises(ValueError, match="mode"):
        run(CFG, event, deps, NOW)
    assert collect.calls == [] and deps.store.objects == {} and deps.events == []


# ---- the check ----

def test_check_with_alerts_writes_the_record_emails_once_then_pings():
    deps = make_deps()
    summary = run(CFG, {"mode": "check"}, deps, datetime(2026, 10, 31, 10, 30, tzinfo=ISRAEL))
    run_id = summary["run_id"]
    assert re.fullmatch(r"083000Z-check-[0-9a-f]{4}", run_id)
    key = check_key(DAY, run_id)
    assert deps.events == [("record", key), "publish", "ping"]
    record = json.loads(deps.store.read_raw(key))
    assert record["run_id"] == run_id and record["code_sha"] == SHA
    assert record["checked_at"] == "2026-10-31T08:30:00+00:00"
    assert record["day"] == "2026-10-31" and sorted(record["chains"]) == sorted(CHAINS)
    assert [a["kind"] for a in record["alerts"]] == ["failed"] * 5  # no retry run for any chain
    [(subject, body)] = deps.publish.calls
    assert len(subject) < 100 and "5 alerts" in subject
    assert all(alert["text"] in body for alert in record["alerts"])
    assert key in body
    [(url, ping_message)] = deps.ping.calls
    assert url == HEALTHCHECK and json.loads(ping_message)["alerts"] == 5
    assert summary == {"mode": "check", "day": "2026-10-31", "run_id": run_id, "record": key, "alerts": 5}


def test_check_without_alerts_writes_the_record_and_pings_without_email(caplog):
    deps = make_deps()
    clean_day(deps.store)
    with caplog.at_level(logging.INFO, logger="collector.handler"):
        summary = run(CFG, {"mode": "check"}, deps, NOW)
    key = check_key(DAY, summary["run_id"])
    assert deps.events[-2:] == [("record", key), "ping"]
    assert deps.publish.calls == []
    assert json.loads(deps.store.read_raw(key))["alerts"] == []
    assert summary["alerts"] == 0 and deps.ping.calls[0][0] == HEALTHCHECK
    handler_records = [r for r in caplog.records if r.name == "collector.handler"]
    assert any(r.levelno == logging.INFO for r in handler_records)  # the summary: the log was captured
    assert not [r for r in handler_records if r.levelno >= logging.WARNING]  # no alert text logged


LATCH = {"stopped": True, "since": "x", "reason": "HTTP 429", "alerted": False}


def test_check_marks_a_stopped_chain_alerted_after_the_email_and_before_the_ping():
    """Ruling R26: the record, the email, the stopped chains marked alerted, then the ping."""
    deps = make_deps()
    clean_day(deps.store)
    deps.store.write_state("carrefour", LATCH)
    deps.events.clear()
    summary = run(CFG, {"mode": "check"}, deps, NOW)
    assert deps.events == [("record", summary["record"]), "publish", ("state", "carrefour"), "ping"]
    assert deps.store.read_state("carrefour") == LATCH | {"alerted": True}
    run(CFG, {"mode": "check"}, deps, NOW)
    assert len(deps.publish.calls) == 1 and "HTTP 429" in deps.publish.calls[0][1]
    assert len(deps.ping.calls) == 2


def test_a_failed_email_leaves_the_stopped_chain_to_alert_again():
    """Ruling R26: nothing is marked, the check fails (no ping), and the next check alerts again."""
    deps = make_deps(publish_raises=RuntimeError("SNS is down"))
    clean_day(deps.store)
    deps.store.write_state("carrefour", LATCH)
    with pytest.raises(RuntimeError, match="SNS is down"):
        run(CFG, {"mode": "check"}, deps, NOW)
    assert deps.store.read_state("carrefour") == LATCH and deps.ping.calls == []
    deps.publish.raises = None
    run(CFG, {"mode": "check"}, deps, NOW)
    assert len(deps.publish.calls) == 2 and "HTTP 429" in deps.publish.calls[1][1]
    assert deps.store.read_state("carrefour") == LATCH | {"alerted": True}


def test_check_ignores_a_chain_in_its_event():
    deps = make_deps()
    clean_day(deps.store)
    run(CFG, {"mode": "check", "chain": "shufersal"}, deps, NOW)
    assert deps.publish.calls == [] and len(deps.ping.calls) == 1


def test_check_on_the_israel_date():
    deps = make_deps()
    summary = run(CFG, {"mode": "check"}, deps, datetime(2026, 10, 31, 23, 30, tzinfo=timezone.utc))
    assert summary["day"] == "2026-11-01"
    assert summary["record"].startswith("checks/date=2026-11-01/")


def test_a_failed_ping_is_logged_not_raised(caplog):
    deps = make_deps(ping_raises=urllib.error.URLError("timed out"))
    clean_day(deps.store)
    with caplog.at_level(logging.WARNING, logger="collector.handler"):
        summary = run(CFG, {"mode": "check"}, deps, NOW)
    assert summary["alerts"] == 0 and len(deps.ping.calls) == 1
    assert any("ping failed" in r.getMessage() and "timed out" in r.getMessage() for r in caplog.records)


def test_a_check_that_fails_sends_no_ping():
    """healthchecks.io then emails about the missing ping."""
    class BrokenStore(EventStore):
        def read_records(self, prefix):
            raise RuntimeError("S3 is down")

    deps = make_deps()
    deps.store = BrokenStore(deps.events)
    with pytest.raises(RuntimeError, match="S3 is down"):
        run(CFG, {"mode": "check"}, deps, NOW)
    assert deps.events == []


def test_a_failed_email_fails_the_check_and_sends_no_ping():
    deps = make_deps(publish_raises=RuntimeError("SNS is down"))
    with pytest.raises(RuntimeError, match="SNS is down"):
        run(CFG, {"mode": "check"}, deps, NOW)
    assert [e if isinstance(e, str) else e[0] for e in deps.events] == ["record", "publish"]


def test_alerts_are_logged_before_the_record_is_written(caplog):
    """A record write that fails (an S3 error, a missing checks/ permission) still leaves the alerts
    in the logs; nothing is emailed, marked or pinged, and the error propagates."""
    class NoCheckRecords(EventStore):
        def put_record(self, key, body, now):
            if key.startswith("checks/"):
                self.events.append(("record", key))
                raise RuntimeError("AccessDenied on checks/")
            super().put_record(key, body, now)

    deps = make_deps()
    deps.store = NoCheckRecords(deps.events)
    clean_day(deps.store)
    deps.store.write_state("carrefour", LATCH)
    deps.events.clear()
    with caplog.at_level(logging.WARNING, logger="collector.handler"), pytest.raises(RuntimeError, match="AccessDenied"):
        run(CFG, {"mode": "check"}, deps, NOW)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "il-grocery-prices 2026-10-31: 1 alert (carrefour)" in logged
    assert "- carrefour is stopped since x: HTTP 429." in logged
    assert [e[0] for e in deps.events] == ["record"]  # the failed write only: no email, no mark, no ping
    assert deps.publish.calls == [] and deps.ping.calls == []
    assert deps.store.read_state("carrefour") == LATCH


def test_the_email_is_logged_before_it_is_sent(caplog):
    deps = make_deps(publish_raises=RuntimeError("SNS is down"))
    with caplog.at_level(logging.WARNING, logger="collector.handler"), pytest.raises(RuntimeError):
        run(CFG, {"mode": "check"}, deps, NOW)
    assert any("no retry run covered" in r.getMessage() for r in caplog.records)


def test_message_lists_every_alert():
    alerts = [Alert("shufersal", "missing", "shufersal: 2 files listed for 2026-10-31 and not stored: A, B."),
              Alert("osherad", "stopped", "osherad is stopped since x: HTTP 403.")]
    subject, body = message(DAY, alerts, "checks/date=2026-10-31/check-1.json")
    assert subject == "il-grocery-prices 2026-10-31: 2 alerts (shufersal, osherad)"
    assert body.splitlines()[0] == "The check of 2026-10-31 (Israel date) found 2 alerts:"
    assert "- shufersal: 2 files listed for 2026-10-31 and not stored: A, B." in body.splitlines()
    assert "- osherad is stopped since x: HTTP 403." in body.splitlines()
    assert body.splitlines()[-1] == "The check record: checks/date=2026-10-31/check-1.json"


def test_message_for_one_alert_and_one_chain_named_once():
    alerts = [Alert("shufersal", "missing", "a"), Alert("shufersal", "failed", "b")]
    assert message(DAY, alerts, "k")[0] == "il-grocery-prices 2026-10-31: 2 alerts (shufersal)"
    assert message(DAY, alerts[:1], "k")[0] == "il-grocery-prices 2026-10-31: 1 alert (shufersal)"


def test_message_subject_stays_under_100_characters():
    alerts = [Alert(f"chain-with-a-long-name-{n}", "failed", "x") for n in range(5)]
    subject = message(DAY, alerts, "k")[0]
    assert subject == "il-grocery-prices 2026-10-31: 5 alerts"
    every_chain = [Alert(slug, "failed", "x") for slug in CHAINS]
    assert len(message(DAY, every_chain, "k")[0]) < 100
    exactly = [Alert("c" * (99 - len("il-grocery-prices 2026-10-31: 1 alert ()")), "failed", "x")]
    assert len(message(DAY, exactly, "k")[0]) == 99
    over = [Alert("c" * (100 - len("il-grocery-prices 2026-10-31: 1 alert ()")), "failed", "x")]
    assert message(DAY, over, "k")[0] == "il-grocery-prices 2026-10-31: 1 alert"


# ---- unblock ----

def test_unblock_clears_the_chains_state():
    deps = make_deps()
    latch = {"stopped": True, "since": "x", "reason": "HTTP 403", "alerted": True}
    deps.store.write_state("ramilevy", latch)
    deps.store.write_state("osherad", latch)
    summary = run(CFG, {"mode": "unblock", "chain": "ramilevy"}, deps, NOW)
    assert deps.store.read_state("ramilevy") == {}
    assert deps.store.read_state("osherad") == latch
    assert summary == {"mode": "unblock", "chain": "ramilevy", "was": latch}
    assert deps.publish.calls == [] and deps.ping.calls == []


# ---- the config ----

def test_config_from_env():
    assert Config.from_env(ENV) == CFG
    assert Config.from_env(ENV | {"RETENTION_DAYS": "30"}).retention_days == 30


@pytest.mark.parametrize("name", ["BUCKET", "USER_AGENT", "ALERT_TOPIC_ARN", "HEALTHCHECK_URL"])
def test_config_requires_each_variable(name):
    with pytest.raises(ValueError, match=name):
        Config.from_env({k: v for k, v in ENV.items() if k != name})
    with pytest.raises(ValueError, match=name):
        Config.from_env(ENV | {name: "  "})


@pytest.mark.parametrize("user_agent", ["il-grocery-prices/0.1 (owner@example.org)",
                                        "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices)",
                                        "Mozilla/5.0"])
def test_config_refuses_a_user_agent_without_the_url_and_an_email(user_agent):
    with pytest.raises(ValueError, match="User-Agent"):
        Config.from_env(ENV | {"USER_AGENT": user_agent})


def test_config_refuses_a_retention_that_is_not_a_number():
    with pytest.raises(ValueError):
        Config.from_env(ENV | {"RETENTION_DAYS": "ten years"})


# ---- the healthchecks.io ping ----

class FakePingNet(urllib.request.BaseHandler):
    handler_order = 400

    def __init__(self, status=200):
        self.status = status
        self.requests = []

    def https_open(self, req):
        self.requests.append(req)
        message = http.client.HTTPMessage()
        resp = urllib.response.addinfourl(io.BytesIO(b"OK"), message, req.full_url, self.status)
        resp.msg = http.client.responses[self.status]
        return resp


def test_ping_posts_the_message_identified():
    net = FakePingNet()
    ping(HEALTHCHECK, '{"alerts": 0}', UA, opener=build_opener(net))
    [req] = net.requests
    assert req.full_url == HEALTHCHECK and req.get_method() == "POST"
    assert req.data == b'{"alerts": 0}'
    assert req.get_header("User-agent") == UA
    assert req.timeout == 10


@pytest.mark.parametrize("user_agent, expected", [
    (UA, "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices)"),
    ("il-grocery-prices/0.2 (owner@example.org; +https://github.com/example/x)", "il-grocery-prices/0.2 (+https://github.com/example/x)"),
    ("owner@example.org (+https://github.com/example/x)", "il-grocery-prices (+https://github.com/example/x)"),
    ("il-grocery-prices/0.1 (+https://owner@example.org/x; owner@example.org)", "il-grocery-prices/0.1 (+https://owner)"),
    ("il-grocery-prices/0.1 (+https://; owner@example.org)", "il-grocery-prices/0.1"),
])
def test_ping_user_agent_leaves_out_the_contact_email(user_agent, expected):
    assert ping_user_agent(user_agent) == expected
    assert "@" not in ping_user_agent(user_agent)


def test_ping_raises_when_refused():
    with pytest.raises(urllib.error.HTTPError):
        ping(HEALTHCHECK, "x", UA, opener=build_opener(FakePingNet(status=404)))


# ---- the code's fingerprint (ruling R25) ----

def write(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def expected_sha(root, rels):
    h = hashlib.sha256()
    for rel in sorted(rels):
        h.update(rel.encode() + b"\0" + hashlib.sha256((root / rel).read_bytes()).digest())
    return h.hexdigest()[:12]


def test_code_sha_over_every_py_file_sorted_by_path(tmp_path):
    write(tmp_path, {"run.py": "a = 1\n", "sources/ncr.py": "b = 2\n", "__init__.py": "", "notes.txt": "not code"})
    assert code_sha(tmp_path) == expected_sha(tmp_path, ["__init__.py", "run.py", "sources/ncr.py"])
    assert re.fullmatch(r"[0-9a-f]{12}", code_sha(tmp_path))


def test_code_sha_changes_with_a_file_in_a_subpackage(tmp_path):
    write(tmp_path, {"run.py": "a = 1\n", "sources/ncr.py": "b = 2\n"})
    before = code_sha(tmp_path)
    write(tmp_path, {"sources/ncr.py": "b = 3\n"})
    assert code_sha(tmp_path) != before


def test_code_sha_changes_with_a_files_path(tmp_path):
    write(tmp_path, {"run.py": "a = 1\n"})
    before = code_sha(tmp_path)
    (tmp_path / "run.py").rename(tmp_path / "check.py")
    assert code_sha(tmp_path) != before


def test_code_sha_ignores_other_files(tmp_path):
    write(tmp_path, {"run.py": "a = 1\n"})
    before = code_sha(tmp_path)
    write(tmp_path, {"run.pyc": "x", "README": "y"})
    assert code_sha(tmp_path) == before


def test_code_sha_of_the_collector_package():
    assert CODE_SHA == code_sha(Path(collector.__file__).parent)
    assert re.fullmatch(r"[0-9a-f]{12}", CODE_SHA)


# ---- the production wiring ----

class FakeContext:
    def __init__(self, millis):
        self.millis = millis

    def get_remaining_time_in_millis(self):
        return self.millis


def aws_client(service):
    return boto3.client(service, region_name="il-central-1", aws_access_key_id="test", aws_secret_access_key="test")


def test_deps_for_production():
    s3, sns, context = aws_client("s3"), aws_client("sns"), FakeContext(123_456)
    deps = deps_for(dataclasses.replace(CFG, retention_days=30), context, s3, sns)
    assert isinstance(deps.store, S3Store) and deps.store.client is s3 and deps.store.bucket == "bucket"
    assert deps.store.retention == timedelta(days=30)
    assert deps.time_left() == 123.456
    context.millis = 1_000
    assert deps.time_left() == 1.0
    assert deps.ping.func is ping and deps.ping.args == ()
    assert deps.ping.keywords == {"user_agent": "il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices)"}
    assert deps.code_sha == CODE_SHA


def test_deps_for_pings_without_the_contact_email():
    """Ruling R27: healthchecks.io never gets the owner's email."""
    deps = deps_for(CFG, FakeContext(1), aws_client("s3"), aws_client("sns"))
    net = FakePingNet()
    deps.ping.func(HEALTHCHECK, "{}", opener=build_opener(net), **deps.ping.keywords)
    [req] = net.requests
    assert "@" not in req.get_header("User-agent")
    assert req.get_header("User-agent").startswith("il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices")


def test_deps_for_gives_each_chain_run_its_own_http():
    """Ruling R6: an NCR session must not leak into another chain's run."""
    deps = deps_for(CFG, FakeContext(1), aws_client("s3"), aws_client("sns"))
    first, second = deps.http_for("ramilevy"), deps.http_for("osherad")
    assert isinstance(first, Http) and first.user_agent == UA
    assert first is not second and first._opener is not second._opener


def test_deps_for_gives_each_chain_run_its_chains_timeout():
    deps = deps_for(CFG, FakeContext(1), aws_client("s3"), aws_client("sns"))
    assert {slug: deps.http_for(slug).timeout for slug in CHAINS} == {slug: c.timeout for slug, c in CHAINS.items()}
    assert deps.http_for("shufersal").timeout == 60.0


def test_deps_for_publishes_to_the_alert_topic():
    """botocore's Stubber checks the call against the SNS model, so a misnamed parameter fails here,
    not on the first real alert."""
    sns = aws_client("sns")
    deps = deps_for(CFG, FakeContext(1), aws_client("s3"), sns)
    with Stubber(sns) as stubber:
        stubber.add_response("publish", {"MessageId": "m-1"},
                             {"TopicArn": TOPIC, "Subject": "il-grocery-prices 2026-10-31: 1 alert", "Message": "body"})
        deps.publish("il-grocery-prices 2026-10-31: 1 alert", "body")
        stubber.assert_no_pending_responses()


# ---- logging (ruling R28) ----

def test_the_collector_logs_at_info():
    assert logging.getLogger("collector").level == logging.INFO
    assert handler_module.log.getEffectiveLevel() == logging.INFO


def test_info_reaches_the_root_handler_whatever_the_root_level():
    """Lambda's runtime puts its handler on the root logger; the root's own level does not stop
    the package's INFO records on their way there."""
    seen = []

    class Keep(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    root, keep = logging.getLogger(), Keep()
    level = root.level
    root.addHandler(keep)
    root.setLevel(logging.WARNING)
    try:
        handler_module.log.info("a run's summary")
    finally:
        root.removeHandler(keep)
        root.setLevel(level)
    assert seen == ["a run's summary"]

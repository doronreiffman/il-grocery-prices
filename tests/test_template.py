"""Pin the deploy settings the collector's safety depends on (template.yaml), and keep the operations
doc's commands in step with them (docs/operations.md).

cfn-lint (run in CI) checks the template is valid CloudFormation and SAM; it cannot know that a
schedule must run in Israel time, that the bucket must keep what it holds, or that the role must
never delete, so those settings are asserted here. The template is read with cfn-lint's decoder,
which understands the CloudFormation tags (!Ref, !Sub, !GetAtt).
"""
import json
import re
import urllib.parse
from datetime import date
from pathlib import Path

import pytest
from cfnlint.decode import decode

from collector import handler, store
from collector.chains import CHAINS
from collector.http import check_user_agent
from collector.names import KINDS

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "template.yaml"
OPERATIONS = ROOT / "docs" / "operations.md"

ISRAEL = "Asia/Jerusalem"
# EventBridge Scheduler's cron: minutes, hours, day of month, month, day of week, year. Every
# schedule runs once a day, every day.
DAILY = re.compile(r"cron\((?P<minute>[0-9]{1,2}) (?P<hour>[0-9]{1,2}) \* \* \? \*\)")

# Rulings R7 and R30 (the controller's ledger), as amended by the owner on 2026-11-01: Shufersal's
# invocations start 15 minutes apart, Lambda's longest run, so one chain never gets two requests at
# once; so do the three NCR chains, which share one portal host, so their sessions never overlap (R30).
# Shufersal collects its store list and full files only, one kind an invocation, each full kind twice in
# the morning (the second run carries on where the first stopped) and once at the retry. A retry run
# starts three hours after the first main run of its kinds; the check starts 15 minutes after the last
# retry run can have finished (11:18 + 15 + 15 min). The four other chains fetch all five kinds in one run.
SCHEDULES = {
    "MainShufersalStores": ("06:30", {"mode": "main", "chain": "shufersal", "kinds": ["Stores"]}),
    "MainRamiLevy": ("06:33", {"mode": "main", "chain": "ramilevy"}),
    "MainCarrefour": ("06:39", {"mode": "main", "chain": "carrefour"}),
    "MainShufersalPrices": ("06:45", {"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}),
    "MainOsherAd": ("08:18", {"mode": "main", "chain": "osherad"}),
    "MainShufersalPricesAgain": ("07:00", {"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}),
    "MainYochananof": ("07:03", {"mode": "main", "chain": "yochananof"}),
    "MainShufersalPromos": ("07:15", {"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}),
    "MainShufersalPromosAgain": ("07:30", {"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}),
    "RetryShufersalStores": ("09:30", {"mode": "retry", "chain": "shufersal", "kinds": ["Stores"]}),
    "RetryRamiLevy": ("09:33", {"mode": "retry", "chain": "ramilevy"}),
    "RetryCarrefour": ("09:39", {"mode": "retry", "chain": "carrefour"}),
    "RetryShufersalPrices": ("09:45", {"mode": "retry", "chain": "shufersal", "kinds": ["PriceFull"]}),
    "RetryOsherAd": ("11:18", {"mode": "retry", "chain": "osherad"}),
    "RetryYochananof": ("10:03", {"mode": "retry", "chain": "yochananof"}),
    "RetryShufersalPromos": ("10:15", {"mode": "retry", "chain": "shufersal", "kinds": ["PromoFull"]}),
    "Check": ("11:48", {"mode": "check"}),
}
CHECK_MARGIN = 15  # minutes after the last retry run can have finished
SHUFERSAL_RUNS = {"main": [["Stores"], ["PriceFull"], ["PriceFull"], ["PromoFull"], ["PromoFull"]],
                  "retry": [["Stores"], ["PriceFull"], ["PromoFull"]]}


@pytest.fixture(scope="module")
def template():
    decoded, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return decoded


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


@pytest.fixture(scope="module")
def function(resources):
    return resources["CollectorFunction"]["Properties"]


@pytest.fixture(scope="module")
def statements(function):
    return function["Policies"][0]["Statement"]


@pytest.fixture(scope="module")
def schedules(function):
    """Each schedule's start, in minutes after Israel midnight, and its event."""
    found = {}
    for name, event in function["Events"].items():
        assert event["Type"] == "ScheduleV2", name
        expression = event["Properties"]["ScheduleExpression"]
        daily = DAILY.fullmatch(expression)
        assert daily, f"{name}: {expression} is not a once-a-day cron"
        found[name] = (int(daily["hour"]) * 60 + int(daily["minute"]), json.loads(event["Properties"]["Input"]))
    return found


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _actions(statement) -> list[str]:
    action = statement["Action"]
    return [action] if isinstance(action, str) else list(action)


def _resources(statement) -> list:
    resource = statement["Resource"]
    return [resource] if not isinstance(resource, list) else list(resource)


def _prefix(key: str) -> dict:
    """The role's resource for every key under `key`'s first path segment."""
    return {"Fn::Sub": "${ArchiveBucket.Arn}/" + key.split("/", 1)[0] + "/*"}


# --- the stack ---


def test_the_stack_holds_only_its_four_resources(resources):
    """Nothing else in the stack may hold permissions on the bucket (a bucket policy, another role)."""
    assert {name: resource["Type"] for name, resource in resources.items()} == {
        "ArchiveBucket": "AWS::S3::Bucket",
        "CollectorFunction": "AWS::Serverless::Function",
        "CollectorLogs": "AWS::Logs::LogGroup",
        "AlertTopic": "AWS::SNS::Topic",
    }


def test_outputs_name_the_bucket_and_the_function(template):
    """docs/operations.md reads both from the stack's outputs."""
    assert template["Outputs"] == {
        "ArchiveBucketName": {"Value": {"Ref": "ArchiveBucket"}},
        "CollectorFunctionName": {"Value": {"Ref": "CollectorFunction"}},
    }


# --- the bucket ---


def test_bucket_is_locked_kept_private_and_encrypted(resources):
    bucket = resources["ArchiveBucket"]
    props = bucket["Properties"]
    assert bucket["DeletionPolicy"] == "Retain"
    assert bucket["UpdateReplacePolicy"] == "Retain"
    assert props["ObjectLockEnabled"] is True
    assert props["VersioningConfiguration"] == {"Status": "Enabled"}
    assert props["OwnershipControls"] == {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
    assert props["BucketEncryption"] == {
        "ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}


def test_bucket_blocks_all_four_kinds_of_public_access(resources):
    assert resources["ArchiveBucket"]["Properties"]["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True}


def test_bucket_has_no_default_retention(resources):
    """Retention is set per object by the code; a bucket default would lock the state files too."""
    assert "ObjectLockConfiguration" not in resources["ArchiveBucket"]["Properties"]


# --- the function ---


def test_function_runs_the_handler_on_python_313_arm64(function):
    assert function["CodeUri"] == "src/"
    assert function["Handler"] == "collector.handler.handler"
    assert callable(handler.handler)
    assert function["Runtime"] == "python3.13"
    assert function["Architectures"] == ["arm64"]


def test_function_has_512_mb_and_lambdas_longest_run(function):
    assert function["MemorySize"] == 512
    assert function["Timeout"] == 900


def test_lambda_never_retries_a_failed_run(function):
    """Scheduler invokes asynchronously, and Lambda would otherwise run a failed invocation twice
    more; the retry run is the real retry."""
    assert function["EventInvokeConfig"] == {"MaximumRetryAttempts": 0}


def test_environment_is_what_the_handler_reads(function, resources):
    """Ruling R5: the names Config.from_env reads, and the ten-year retention the store uses."""
    variables = function["Environment"]["Variables"]
    assert set(variables) == set(handler.REQUIRED) | {"RETENTION_DAYS"}
    assert variables == {
        "BUCKET": {"Ref": "ArchiveBucket"},
        "USER_AGENT": {"Ref": "UserAgent"},
        "ALERT_TOPIC_ARN": {"Ref": "AlertTopic"},
        "HEALTHCHECK_URL": {"Ref": "HealthcheckUrl"},
        "RETENTION_DAYS": "3650",
    }
    assert variables["RETENTION_DAYS"] == str(store.RETENTION_DAYS)


def test_logs_go_to_a_group_created_first(function, resources):
    """Created before the function, under its own name, so the first run cannot race CloudFormation
    by creating /aws/lambda/<name> with no retention."""
    assert function["LoggingConfig"] == {"LogGroup": {"Ref": "CollectorLogs"}}
    assert resources["CollectorLogs"]["Properties"] == {
        "LogGroupName": {"Fn::Sub": "/${AWS::StackName}/collector"}, "RetentionInDays": 30}


# --- the role ---


def test_role_is_one_inline_policy(function):
    """No managed policy (AmazonS3FullAccess, a SAM policy template) can widen what the role may do."""
    assert len(function["Policies"]) == 1
    assert set(function["Policies"][0]) == {"Statement"}


def test_role_cannot_delete_bypass_the_lock_or_change_the_bucket(statements):
    actions = [action for statement in statements for action in _actions(statement)]
    assert not [a for a in actions if a.lower().startswith("s3:delete")]
    assert not [a for a in actions if "bypassgovernanceretention" in a.lower()]
    assert not [a for a in actions if a.lower().startswith("s3:putbucket")]
    assert not [a for a in actions if "*" in a]
    assert {statement["Effect"] for statement in statements} == {"Allow"}


def test_role_grants_exactly_what_the_code_does(statements):
    """Locked puts (each sets its retain-until date; S3 requires s3:PutObjectRetention to place a
    retention configuration) under raw/, manifests/ and checks/; reads there too (the check reads manifests and store lists, a
    taken key is compared through head_object, which needs s3:GetObject); plain reads and writes of
    state/; a list of the bucket; the alert email."""
    stored = [{"Fn::Sub": "${ArchiveBucket.Arn}/raw/*"}, {"Fn::Sub": "${ArchiveBucket.Arn}/manifests/*"},
              {"Fn::Sub": "${ArchiveBucket.Arn}/checks/*"}]
    by_sid = {statement["Sid"]: (sorted(_actions(statement)), _resources(statement)) for statement in statements}
    assert by_sid == {
        "WriteOnceLocked": (["s3:PutObject", "s3:PutObjectRetention"], stored),
        "ReadStored": (["s3:GetObject"], stored),
        "ReadWriteState": (["s3:GetObject", "s3:PutObject"], [{"Fn::Sub": "${ArchiveBucket.Arn}/state/*"}]),
        "ListBucketSoMissingKeyIs404": (["s3:ListBucket"], [{"Fn::GetAtt": ["ArchiveBucket", "Arn"]}]),
        "EmailAlerts": (["sns:Publish"], [{"Ref": "AlertTopic"}]),
    }
    assert not [statement for statement in statements if "Condition" in statement]


def test_role_prefixes_are_the_stores_keys(statements):
    """The prefixes the role names are the ones the code writes under."""
    day = date(2026, 11, 1)
    by_sid = {statement["Sid"]: _resources(statement) for statement in statements}
    locked = [store.raw_key("shufersal", day, "x"), store.manifest_key(day, "shufersal", "r"), store.check_key(day, "r")]
    assert by_sid["WriteOnceLocked"] == [_prefix(key) for key in locked]
    assert by_sid["ReadWriteState"] == [_prefix(store.state_key("shufersal"))]


# --- the alerts ---


def test_alerts_go_to_one_email_subscription(resources):
    assert resources["AlertTopic"]["Properties"] == {
        "Subscription": [{"Protocol": "email", "Endpoint": {"Ref": "AlertEmail"}}]}


# --- the parameters ---


def test_parameters_are_the_four_and_only_the_switch_has_a_default(template):
    """The User-Agent, the email and the ping URL are given at deploy; none of them is in the repo."""
    parameters = template["Parameters"]
    assert set(parameters) == {"UserAgent", "AlertEmail", "HealthcheckUrl", "ScheduleState"}
    assert [name for name, parameter in parameters.items() if "Default" in parameter] == ["ScheduleState"]


def test_schedules_start_switched_off(template):
    parameter = template["Parameters"]["ScheduleState"]
    assert parameter["Default"] == "DISABLED"
    assert sorted(parameter["AllowedValues"]) == ["DISABLED", "ENABLED"]


def test_user_agent_needs_the_project_url_and_an_email(template):
    """CloudFormation matches AllowedPattern against the whole value, as re.fullmatch does."""
    pattern = template["Parameters"]["UserAgent"]["AllowedPattern"]
    good = "il-grocery-prices/0.1.0 (+https://github.com/x/il-grocery-prices; me@example.org)"
    assert re.fullmatch(pattern, good)
    assert check_user_agent(good) == good  # the code takes what the deploy takes
    assert not re.fullmatch(pattern, "il-grocery-prices/0.1.0")  # what a space-split override leaves
    assert not re.fullmatch(pattern, "il-grocery-prices/0.1.0 (me@example.org)")
    assert not re.fullmatch(pattern, "il-grocery-prices/0.1.0 (+http://github.com/x/y; me@example.org)")
    assert not re.fullmatch(pattern, "il-grocery-prices/0.1.0 (+https://github.com/x/y)")


def test_health_check_url_is_a_hidden_healthchecks_ping_url(template):
    parameter = template["Parameters"]["HealthcheckUrl"]
    assert parameter["NoEcho"] is True
    pattern = parameter["AllowedPattern"]
    assert re.fullmatch(pattern, "https://hc-ping.com/0f3e2d1c-5b4a-4c3d-9e8f-7a6b5c4d3e2f")
    assert re.fullmatch(pattern, "https://hc-ping.com/AbCdEfGhIjKlMnOpQrStUv/il-grocery-prices")
    for bad in ("", "https://hc-ping.com/", "http://hc-ping.com/0f3e2d1c", "https://example.org/0f3e2d1c",
                "https://hc-ping.com.example.org/0f3e2d1c", "https://hc-ping.com/0f3e2d1c?x=1", "<url>"):
        assert not re.fullmatch(pattern, bad), bad


# --- the schedules ---


def test_schedules_are_rulings_r7_and_r30(schedules):
    assert schedules == {name: (_minutes(clock), event) for name, (clock, event) in SCHEDULES.items()}


def test_every_schedule_runs_on_time_in_israel_and_follows_the_switch(function):
    """Asia/Jerusalem, so daylight saving moves the runs with the shops; no flexible window, so the
    15-minute spacing holds; no Scheduler retries; on or off with ScheduleState, never on its own.
    The property names are pinned too: cfn-lint 1.57 lets a misspelled ScheduleV2 property through
    (and YAML reads an unquoted OFF as false)."""
    for name, event in function["Events"].items():
        properties = event["Properties"]
        assert set(properties) == {"ScheduleExpression", "ScheduleExpressionTimezone", "Input", "State",
                                   "FlexibleTimeWindow", "RetryPolicy"}, name
        assert properties["ScheduleExpressionTimezone"] == ISRAEL, name
        assert properties["State"] == {"Ref": "ScheduleState"}, name
        assert properties["FlexibleTimeWindow"] == {"Mode": "OFF"}, name
        assert properties["RetryPolicy"] == {"MaximumRetryAttempts": 0}, name


def test_no_two_schedules_share_a_start_minute(schedules):
    starts = [start for start, _ in schedules.values()]
    assert len(starts) == len(set(starts))


def test_every_event_is_one_the_handler_takes(schedules):
    for name, (_, event) in schedules.items():
        assert event["mode"] in ("main", "retry", "check"), name
        if event["mode"] == "check":
            assert event == {"mode": "check"}, name
            continue
        assert event["chain"] in CHAINS, name
        assert set(event.get("kinds", KINDS)) <= set(CHAINS[event["chain"]].kinds), name


@pytest.mark.parametrize("mode", ["main", "retry"])
def test_each_chain_has_runs_of_each_mode_over_the_kinds_it_collects(schedules, mode):
    """Ruling R4: the check fails a chain whose retry runs do not together cover the kinds it collects.
    Shufersal runs one kind an invocation, each full kind twice in the morning; the others run once,
    with no kinds, so the handler takes the chain's."""
    groups = {slug: [] for slug in CHAINS}
    for _, event in schedules.values():
        if event["mode"] == mode:
            groups[event["chain"]].append(event.get("kinds"))
    for slug, kinds in groups.items():
        if slug == "shufersal":
            assert sorted(kinds) == sorted(SHUFERSAL_RUNS[mode])
            assert {kind for group in kinds for kind in group} == set(CHAINS[slug].kinds)
        else:
            assert kinds == [None], slug


def test_retry_runs_start_three_hours_after_the_first_main_run_of_their_kinds(schedules):
    mains = {}
    for start, event in sorted(schedules.values(), key=lambda schedule: schedule[0]):
        if event["mode"] == "main":
            mains.setdefault((event["chain"], tuple(event.get("kinds", ()))), start)
    retries = {(event["chain"], tuple(event.get("kinds", ()))): start
               for start, event in schedules.values() if event["mode"] == "retry"}
    assert set(retries) == set(mains)
    assert {key: retries[key] - mains[key] for key in mains} == {key: 180 for key in mains}


def test_one_chain_never_runs_twice_at_once(schedules, function):
    """A chain's invocations start at least Lambda's timeout apart, so one has ended before the next
    starts: one request at a time per chain."""
    longest = function["Timeout"] / 60
    starts = {}
    for start, event in schedules.values():
        if event["mode"] != "check":
            starts.setdefault(event["chain"], []).append(start)
    for slug, times in starts.items():
        times.sort()
        assert all(later - earlier >= longest for earlier, later in zip(times, times[1:])), (slug, times)


def test_one_portal_host_never_serves_two_runs_at_once(schedules, function):
    """Ruling R30: chains on one portal host (the three NCR chains on url.publishedprices.co.il)
    start at least Lambda's timeout apart, whatever their mode, so their sessions never overlap."""
    longest = function["Timeout"] / 60
    hosts = {slug: urllib.parse.urlsplit(chain.base_url).netloc for slug, chain in CHAINS.items()}
    assert len(set(hosts.values())) < len(hosts)  # some chains do share a host
    starts = {}
    for start, event in schedules.values():
        if event["mode"] != "check":
            starts.setdefault(hosts[event["chain"]], []).append(start)
    for host, times in starts.items():
        times.sort()
        assert all(later - earlier >= longest for earlier, later in zip(times, times[1:])), (host, times)


def test_one_check_after_the_last_retry_run_can_have_finished(schedules, function):
    checks = [start for start, event in schedules.values() if event["mode"] == "check"]
    runs = [start for start, event in schedules.values() if event["mode"] != "check"]
    assert len(checks) == 1
    # 15 minutes more than the last retry run can take, for its manifest write and the schedulers'
    # start-up lag: with none, a slow last retry can still be writing when the check reads (review,
    # 2026-11-01).
    assert checks[0] >= max(runs) + function["Timeout"] / 60 + CHECK_MARGIN
    assert checks[0] < 24 * 60  # the same Israel day as the runs it checks


# --- the operations doc ---


def _commands(text: str) -> list[str]:
    """The commands in the doc's fenced code blocks, a backslash-continued command as one line."""
    commands = []
    for block in re.findall(r"```(?:bash|sh)?\n(.*?)```", text, re.DOTALL):
        command = ""
        for line in block.splitlines():
            command += line.rstrip("\\").strip() + " "
            if not line.endswith("\\"):
                if command.strip():
                    commands.append(command.strip())
                command = ""
    return commands


@pytest.fixture(scope="module")
def operations():
    return OPERATIONS.read_text()


def test_every_aws_command_in_the_doc_names_the_project_account(operations):
    """Every other profile on the owner's Mac is the employer's: a command without --profile
    flights-sam would run against the employer's default profile."""
    commands = [c for c in _commands(operations) if re.search(r"(^|[\s(])(aws|sam deploy)\s", c)]
    assert commands
    for command in commands:
        assert "--profile flights-sam" in command, command
        assert "--region il-central-1" in command, command


def test_the_docs_events_are_ones_the_handler_takes(operations):
    payloads = [json.loads(p) for p in re.findall(r"--payload '(\{[^']*\})'", operations)]
    assert payloads
    for event in payloads:
        assert event["mode"] in ("main", "retry", "check", "unblock"), event
        if "chain" in event:
            assert event["chain"] in CHAINS, event
            assert set(event.get("kinds", KINDS)) <= set(CHAINS[event["chain"]].kinds), event
    assert {"mode": "check"} in payloads
    assert any(event["mode"] == "unblock" for event in payloads)


def test_the_doc_runs_each_main_invocation_by_hand(operations, schedules):
    """A manual run per chain, the Shufersal ones by kinds group, as the schedule runs them."""
    payloads = [json.loads(p) for p in re.findall(r"--payload '(\{[^']*\})'", operations)]
    by_hand = sorted(json.dumps(event, sort_keys=True) for event in payloads if event["mode"] == "main")
    scheduled = sorted(json.dumps(event, sort_keys=True) for _, event in schedules.values() if event["mode"] == "main")
    assert by_hand == scheduled


def test_the_docs_timetable_is_the_schedules(operations, schedules):
    """The "What runs when" table: each row with an event shows a main run or the check at its time."""
    rows = re.findall(r"^\| ([0-9]{2}:[0-9]{2}) \| [^|]+ \| `(\{[^`]*\})` \|$", operations, re.MULTILINE)
    shown = sorted((_minutes(clock), json.dumps(json.loads(event), sort_keys=True)) for clock, event in rows)
    scheduled = sorted((start, json.dumps(event, sort_keys=True)) for start, event in schedules.values()
                       if event["mode"] in ("main", "check"))
    assert shown == scheduled


def test_the_doc_starts_collecting_runs_asynchronously(operations):
    """A collecting run can take 15 minutes; the CLI waits 60 s for a synchronous answer, then gives
    up and sends the invoke again, which would start a second run of the same chain."""
    lines = [line for line in operations.splitlines() if "--payload" in line]
    for line in lines:
        event = json.loads(re.search(r"--payload '(\{[^']*\})'", line)[1])
        if event["mode"] in ("main", "retry"):
            assert "--invocation-type Event" in line, line


@pytest.mark.parametrize("path", [TEMPLATE, OPERATIONS], ids=lambda p: p.name)
def test_no_contact_values_in_the_repo(path):
    """Only placeholders: no email address but example.org's, no healthchecks.io ping id."""
    text = path.read_text()
    emails = re.findall(r"[A-Za-z0-9._%+-]+@([A-Za-z][A-Za-z0-9.-]*\.[A-Za-z]{2,})", text)
    assert set(emails) <= {"example.org"}, emails
    assert not re.findall(r"hc-ping\.com/(?!<)[A-Za-z0-9]", text)

"""Pin what the basket function's part of the stack says (template.yaml: `BasketFunction`, its `DuckDbLayer`, its
`BasketLogs`, the four parameters it takes and its output) and what the layer's build files say (layer/).

cfn-lint (run in CI) checks the template is valid CloudFormation and SAM; it cannot know that the role must never
delete, that the extractions must wait for the collector's check, or that the basket event's "collected by" must be
the extractions' start, so those are asserted here, as `tests/test_template.py` does for the collector.

`sam build` builds the layer from `layer/Makefile`; nothing here runs a build, so the build command's flags are
asserted as text: a wheel for the wrong platform would install fine and fail only when Lambda imports it.
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from cfnlint.decode import decode

from basket import handler
from basket.archive import record_key, table_key
from basket.chains import SLUGS
from basket.duck import MEMORY_LIMIT_VAR, TEMP_DIRECTORY_VAR
from basket.handler import REQUIRED, SITE_BUCKET_PREFIX, Config, Deps, run
from basket.site import PAGES, day_key
from collector.store import RETENTION_DAYS, check_key, manifest_key, raw_key
from test_template import DAILY, ISRAEL, TEMPLATE, _actions, _prefix, _resources

ROOT = Path(__file__).parent.parent
LAYER = ROOT / "layer"
DUCKDB_HASH = "364992ba1089a2b327391cfcb68fd0bd0ce9090cf293baef861a0ba6847abfee"

EXTRACTIONS = {"ExtractShufersal": "shufersal", "ExtractRamiLevy": "ramilevy", "ExtractOsherAd": "osherad",
               "ExtractCarrefour": "carrefour", "ExtractYochananof": "yochananof"}
BASKET_MARGIN = 15  # minutes after the last extraction can have finished, for its table's put and the schedulers' lag
SITE = "arn:aws:s3:::${SiteBucketName}"


@pytest.fixture(scope="module")
def template():
    decoded, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return decoded


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


@pytest.fixture(scope="module")
def basket_function(resources):
    return resources["BasketFunction"]["Properties"]


@pytest.fixture(scope="module")
def basket_statements(basket_function):
    return basket_function["Policies"][0]["Statement"]


def _daily(function) -> dict:
    """Each of the function's schedules: its start, in minutes after Israel midnight, and its event."""
    found = {}
    for name, event in function["Events"].items():
        assert event["Type"] == "ScheduleV2", name
        expression = event["Properties"]["ScheduleExpression"]
        daily = DAILY.fullmatch(expression)
        assert daily, f"{name}: {expression} is not a once-a-day cron"
        found[name] = (int(daily["hour"]) * 60 + int(daily["minute"]), json.loads(event["Properties"]["Input"]))
    return found


@pytest.fixture(scope="module")
def basket_schedules(basket_function):
    return _daily(basket_function)


def _starts(schedules, mode: str) -> list[int]:
    return [start for start, event in schedules.values() if event["mode"] == mode]


def _site(path: str) -> dict:
    return {"Fn::Sub": f"{SITE}/{path}"}


def _site_prefix(key: str) -> dict:
    """The role's resource for every key under `key`'s first path segment, in the site bucket."""
    return _site(key.split("/", 1)[0] + "/*")


# --- the function ---


def test_function_runs_the_basket_handler_on_python_313_arm64_with_the_layer(basket_function):
    assert basket_function["CodeUri"] == "src/"
    assert basket_function["Handler"] == "basket.handler.handler"
    assert callable(handler.handler)
    assert basket_function["Runtime"] == "python3.13"
    assert basket_function["Architectures"] == ["arm64"]
    assert basket_function["Layers"] == [{"Ref": "DuckDbLayer"}]


def test_function_has_two_gb_two_gb_of_tmp_and_lambdas_longest_run(basket_function):
    """DuckDB's memory limit sits under the 2 GB; /tmp holds a chain's price files of the day, its table and
    DuckDB's spill folder."""
    assert basket_function["MemorySize"] == 2048
    assert basket_function["EphemeralStorage"] == {"Size": 2048}
    assert basket_function["Timeout"] == 900


def test_lambda_never_retries_a_failed_run(basket_function):
    """Scheduler invokes asynchronously, and Lambda would otherwise run a failed invocation twice more."""
    assert basket_function["EventInvokeConfig"] == {"MaximumRetryAttempts": 0}


def test_environment_is_what_the_handler_and_duckdb_read(basket_function):
    """The names Config.from_env reads, the ten-year retention the records are locked for, and DuckDB's temp folder
    under /tmp (Lambda's working directory is read-only) and its memory limit under the function's."""
    variables = basket_function["Environment"]["Variables"]
    assert set(variables) == set(REQUIRED) | {"RETENTION_DAYS", TEMP_DIRECTORY_VAR, MEMORY_LIMIT_VAR}
    assert variables == {
        "BUCKET": {"Ref": "ArchiveBucket"},
        "SITE_BUCKET": {"Ref": "SiteBucketName"},
        "DISTRIBUTION_ID": {"Ref": "SiteDistributionId"},
        "HEALTHCHECK_URL": {"Ref": "BasketHealthcheckUrl"},
        "USER_AGENT": {"Ref": "UserAgent"},
        "RETENTION_DAYS": "3650",
        "DUCKDB_TEMP_DIRECTORY": "/tmp/duckdb",
        "DUCKDB_MEMORY_LIMIT": "1200MB",
    }
    assert variables["RETENTION_DAYS"] == str(RETENTION_DAYS)


def test_logs_go_to_a_group_created_first(basket_function, resources):
    """Created before the function, under its own name, so the first run cannot race CloudFormation by creating
    /aws/lambda/<name> with no retention."""
    assert basket_function["LoggingConfig"] == {"LogGroup": {"Ref": "BasketLogs"}}
    assert resources["BasketLogs"]["Type"] == "AWS::Logs::LogGroup"
    assert resources["BasketLogs"]["Properties"] == {
        "LogGroupName": {"Fn::Sub": "/${AWS::StackName}/basket"}, "RetentionInDays": 30}


# --- the role ---


def test_role_is_one_inline_policy(basket_function):
    """No managed policy (AmazonS3FullAccess, a SAM policy template) can widen what the role may do."""
    assert len(basket_function["Policies"]) == 1
    assert set(basket_function["Policies"][0]) == {"Statement"}


def test_role_cannot_delete_bypass_the_lock_or_change_either_bucket(basket_statements):
    actions = [action for statement in basket_statements for action in _actions(statement)]
    assert not [a for a in actions if a.lower().startswith("s3:delete")]
    assert not [a for a in actions if "bypassgovernanceretention" in a.lower()]
    assert not [a for a in actions if a.lower().startswith("s3:putbucket")]
    assert not [a for a in actions if "*" in a]
    assert {statement["Effect"] for statement in basket_statements} == {"Allow"}


def test_role_grants_exactly_what_the_code_does(basket_statements):
    """Reads of the archive's raw files, manifests, check records, tables and basket records (a refused locked put
    of a record is compared through head_object, which needs s3:GetObject); plain puts of the tables; locked puts
    of the records (each sets its retain-until date, which needs s3:PutObjectRetention); a list of the archive;
    reads of the site's day files, puts of its two pages and day files, a list of it; one distribution's
    invalidation."""
    archive = [{"Fn::Sub": "${ArchiveBucket.Arn}/" + folder + "/*"}
               for folder in ("raw", "manifests", "checks", "tables", "basket")]
    by_sid = {statement["Sid"]: (sorted(_actions(statement)), _resources(statement)) for statement in basket_statements}
    assert by_sid == {
        "ReadArchive": (["s3:GetObject"], archive),
        "WriteTables": (["s3:PutObject"], [{"Fn::Sub": "${ArchiveBucket.Arn}/tables/*"}]),
        "WriteOnceLockedRecords": (["s3:PutObject", "s3:PutObjectRetention"],
                                   [{"Fn::Sub": "${ArchiveBucket.Arn}/basket/*"}]),
        "ListArchive": (["s3:ListBucket"], [{"Fn::GetAtt": ["ArchiveBucket", "Arn"]}]),
        "ReadPublishedDays": (["s3:GetObject"], [_site("days/*")]),
        "WriteSite": (["s3:PutObject"], [_site("index.html"), _site("method.html"), _site("days/*")]),
        "ListSite": (["s3:ListBucket"], [{"Fn::Sub": SITE}]),
        "Invalidate": (["cloudfront:CreateInvalidation"],
                       [{"Fn::Sub": "arn:aws:cloudfront::${AWS::AccountId}:distribution/${SiteDistributionId}"}]),
    }
    for statement in basket_statements:  # no Condition, NotAction or NotResource to widen or narrow a grant
        assert set(statement) == {"Sid", "Effect", "Action", "Resource"}, statement["Sid"]


def test_role_prefixes_are_the_codes_keys(basket_statements):
    """The prefixes the role names are the ones the code reads and writes under, and the pages are the site's."""
    day = date(2026, 11, 1)
    by_sid = {statement["Sid"]: _resources(statement) for statement in basket_statements}
    table, record = table_key("shufersal", day, "prices.parquet"), record_key(day, "r")
    read = [raw_key("shufersal", day, "x"), manifest_key(day, "shufersal", "r"), check_key(day, "r"), table, record]
    assert by_sid["ReadArchive"] == [_prefix(key) for key in read]
    assert by_sid["WriteTables"] == [_prefix(table)]
    assert by_sid["WriteOnceLockedRecords"] == [_prefix(record)]
    assert by_sid["ReadPublishedDays"] == [_site_prefix(day_key(day))]
    assert by_sid["WriteSite"] == [_site(page) for page in PAGES] + [_site_prefix(day_key(day))]


# --- the parameters ---


def test_parameters_are_the_eight_and_only_the_two_switches_have_defaults(template):
    """The site's bucket and distribution and the basket's ping URL are given at deploy, as the collector's are."""
    parameters = template["Parameters"]
    assert set(parameters) == {"UserAgent", "AlertEmail", "HealthcheckUrl", "ScheduleState",
                               "SiteBucketName", "SiteDistributionId", "BasketHealthcheckUrl", "BasketScheduleState"}
    assert sorted(name for name, parameter in parameters.items() if "Default" in parameter) == [
        "BasketScheduleState", "ScheduleState"]
    assert {parameter["Type"] for parameter in parameters.values()} == {"String"}


def test_site_parameters_are_pattern_checked(template):
    """CloudFormation matches AllowedPattern against the whole value, as re.fullmatch does. A bucket the deploy
    takes is one Config.from_env takes; the archive bucket is neither."""
    parameters = template["Parameters"]
    bucket = parameters["SiteBucketName"]["AllowedPattern"]
    assert bucket.startswith(SITE_BUCKET_PREFIX)
    assert re.fullmatch(bucket, SITE_BUCKET_PREFIX + "0123456789ab")
    for bad in ("", SITE_BUCKET_PREFIX, "il-grocery-prices-archivebucket-0123456789ab",
                "x-" + SITE_BUCKET_PREFIX + "0123456789ab", "<bucket>"):
        assert not re.fullmatch(bucket, bad), bad
    distribution = parameters["SiteDistributionId"]["AllowedPattern"]
    assert re.fullmatch(distribution, "E0123456789ABC")
    for bad in ("", "E", "e0123456789abc", "0123456789ABC", "E0123456789ABC.cloudfront.net",
                "d153udx05irk2f.cloudfront.net", "<distribution>"):
        assert not re.fullmatch(distribution, bad), bad
    ping = parameters["BasketHealthcheckUrl"]
    assert ping["NoEcho"] is True
    assert ping["AllowedPattern"] == parameters["HealthcheckUrl"]["AllowedPattern"]


# --- the schedules ---


def test_schedules_follow_the_baskets_own_switch_in_israel_time(basket_function, template):
    """Asia/Jerusalem, so daylight saving moves the runs with the collector's; no flexible window and no Scheduler
    retries; on or off with BasketScheduleState, so the collector keeps running while step two is tested. The switch
    starts off. The property names are pinned too: cfn-lint 1.57 lets a misspelled ScheduleV2 property through."""
    assert set(basket_function["Events"]) == set(EXTRACTIONS) | {"Basket"}
    for name, event in basket_function["Events"].items():
        properties = event["Properties"]
        assert set(properties) == {"ScheduleExpression", "ScheduleExpressionTimezone", "Input", "State",
                                   "FlexibleTimeWindow", "RetryPolicy"}, name
        assert properties["ScheduleExpressionTimezone"] == ISRAEL, name
        assert properties["State"] == {"Ref": "BasketScheduleState"}, name
        assert properties["FlexibleTimeWindow"] == {"Mode": "OFF"}, name
        assert properties["RetryPolicy"] == {"MaximumRetryAttempts": 0}, name
    switch = template["Parameters"]["BasketScheduleState"]
    assert switch["Default"] == "DISABLED"
    assert sorted(switch["AllowedValues"]) == ["DISABLED", "ENABLED"]


def test_five_extractions_share_one_minute_one_per_chain(basket_schedules):
    """The extractions read the archive bucket only and touch no portal, so they need no spacing."""
    extractions = {name: (start, event) for name, (start, event) in basket_schedules.items()
                   if event["mode"] == "extract"}
    assert {name: event["chain"] for name, (_, event) in extractions.items()} == EXTRACTIONS
    assert sorted(EXTRACTIONS.values()) == sorted(SLUGS)
    assert len({start for start, _ in extractions.values()}) == 1
    for name, (_, event) in extractions.items():
        assert set(event) == {"mode", "chain"}, name  # a scheduled run takes the day it runs on


class Checked(Exception):
    """Raised by the archive's first call: the event passed run()'s checks."""


class GateArchive:
    def day_checked(self, day):
        raise Checked(day)


CFG = Config(bucket="il-grocery-prices-archivebucket-0123456789ab", site_bucket=SITE_BUCKET_PREFIX + "0123456789ab",
             distribution_id="E0123456789ABC", healthcheck_url="https://hc-ping.example/0000-test",
             user_agent="il-grocery-prices/0.1 (+https://github.com/example/il-grocery-prices; owner@example.org)",
             retention_days=3650)
NOW = datetime(2026, 11, 3, 10, 3, tzinfo=timezone.utc)


def _deps(pinged: list) -> Deps:
    """An archive that stops the run at its first call, and a ping that records the URLs in `pinged`."""
    return Deps(archive=GateArchive(), site=None, ping=lambda url, message: pinged.append(url))


def test_every_event_is_one_the_handler_takes(basket_function, tmp_path):
    """Each scheduled event passes run()'s checks (the mode, the chain, collected_by as HH:MM) and reaches the
    check-record gate; an event that fails them raises ValueError before that, and pings nothing."""
    for event in basket_function["Events"].values():
        with pytest.raises(Checked):
            run(CFG, json.loads(event["Properties"]["Input"]), _deps([]), NOW, tmp_path)
    for bad in ({"mode": "collect", "chain": "shufersal"}, {"mode": "extract", "chain": "victory"},
                {"mode": "basket", "collected_by": "12:3"}, {"mode": "basket"}):
        pinged = []
        with pytest.raises(ValueError):
            run(CFG, bad, _deps(pinged), NOW, tmp_path)
        assert pinged == [], bad


def test_collected_by_is_the_extractions_start(basket_schedules):
    """B11: the day's "collected by" is the extractions' scheduled start, fixed in the template so the record stays
    deterministic."""
    [(_, event)] = [(start, event) for start, event in basket_schedules.values() if event["mode"] == "basket"]
    assert set(event) == {"mode", "collected_by"}  # a scheduled run takes the day it runs on
    starts = _starts(basket_schedules, "extract")
    assert {f"{start // 60:02d}:{start % 60:02d}" for start in starts} == {event["collected_by"]}


def test_basket_runs_after_the_last_extraction_can_have_finished(basket_schedules, basket_function):
    [basket] = _starts(basket_schedules, "basket")
    longest = basket_function["Timeout"] / 60
    assert basket >= max(_starts(basket_schedules, "extract")) + longest + BASKET_MARGIN
    assert basket < 24 * 60  # the same Israel day as the extractions


def test_extraction_starts_after_the_collectors_check_can_have_finished(basket_schedules, resources):
    """The check is the morning's last run, and both modes refuse a day without its record (call 11 of the
    step-two plan): an extraction scheduled before the check can have finished would fail on a slow morning."""
    collector = resources["CollectorFunction"]["Properties"]
    [check] = _starts(_daily(collector), "check")
    assert min(_starts(basket_schedules, "extract")) >= check + collector["Timeout"] / 60


# --- the layer ---


def test_layer_is_built_by_the_makefile_for_python_313_arm64(resources):
    """SAM builds a layer whose Metadata says makefile by running the target build-<LogicalId> of the Makefile
    under its ContentUri."""
    layer = resources["DuckDbLayer"]
    assert layer["Type"] == "AWS::Serverless::LayerVersion"
    assert layer["Properties"] == {"ContentUri": "layer/", "CompatibleRuntimes": ["python3.13"],
                                   "CompatibleArchitectures": ["arm64"], "RetentionPolicy": "Delete"}
    assert layer["Metadata"] == {"BuildMethod": "makefile"}
    assert (LAYER / "Makefile").read_text().splitlines()[0] == "build-DuckDbLayer:"


def test_layer_pins_duckdb_by_version_and_hash():
    lines = (LAYER / "requirements.txt").read_text().splitlines()
    assert lines == [f"duckdb==1.5.6 --hash=sha256:{DUCKDB_HASH}"]
    dev = [line for line in (ROOT / "requirements-dev.txt").read_text().splitlines() if line.startswith("duckdb==")]
    assert dev == [lines[0].split()[0]], "the layer and the tests must run the same DuckDB"


def test_layer_makefile_builds_for_lambdas_arm64_linux():
    lines = (LAYER / "Makefile").read_text().splitlines()
    assert lines[0] == "build-DuckDbLayer:"
    [command] = lines[1:]
    assert command.startswith("\t"), "a recipe line starts with a tab"
    for flag in ("--platform manylinux_2_28_aarch64", "--python-version 3.13", "--only-binary=:all:",
                 "--require-hashes", "--implementation cp", '"$(ARTIFACTS_DIR)/python"'):
        assert flag in command, flag


# --- the output ---


def test_the_stack_outputs_the_basket_function(template):
    """A manual run needs the function's name, which CloudFormation makes up; the stack's outputs give it."""
    assert template["Outputs"]["BasketFunctionName"] == {"Value": {"Ref": "BasketFunction"}}

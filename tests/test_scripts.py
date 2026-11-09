"""The hand scripts, run against a stand-in `aws` that records each call and answers as the CLI does; neither script
ever reaches AWS here.

The stand-in answers the identity check with the expected user (or `IDENTITY`); the site stack's outputs when
`SITE_BUCKET` is set, else AWS's words for a stack that does not exist yet (as sync.sh quotes them); a recursive
`s3 cp` from the bucket by copying that folder of `FAKE_BUCKET`, a local folder standing in for the bucket; the listing
of the `p/` keys with `P_KEYS`, as `--output text` prints it; and an invalidation with its id. `FAIL_READ` names one
read that fails instead, a folder's copy or `p` for the listing, as the CLI fails one; `FAIL_SYNC` one upload, by its
`--include` pattern. Every other call (each `s3 sync`) is recorded and does nothing. `publish.sh` runs with a stand-in
`python` that records each call too and answers the site check with `CHECK_EXIT` (the check's own tests are
`tests/test_shop_check.py`); every other module, the publish guard, runs for real (`shopper.guard`), over a build made
as `tests/test_shop_guard.py` makes one.
"""
import os
import re
import subprocess
import sys
from datetime import date
from fnmatch import fnmatch
from pathlib import Path

import pytest

from basket.site import CACHE_CONTROL, CONTENT_TYPES, day_key
from shopper.build import LEDGER, MARKER
from shopper.freeze import archive_key, scores_archive_key
from shopper.history import covered_path
from shopper.items import items_path
from shopper.score import summary_path
from shopper.siteday import site_day_path
from test_shop_guard import LATER_PUBLISHED, NEXT_DAY, PAGES, a_bucket, a_site

ROOT = Path(__file__).resolve().parent.parent
ARN = "arn:aws:iam::137953273942:user/doron-admin"
ARCHIVE = "il-grocery-prices-archivebucket-fmnv3dorojol"
SITE_BUCKET = "il-grocery-prices-site-sitebucket-0123456789ab"
PROFILE = ["--profile", "flights-sam", "--region", "il-central-1"]
# Each call's arguments one a line, then a line "--"; the stand-in python's calls start with a line "python".
FAKE_AWS = f"""#!/bin/sh
for arg in "$@"; do printf '%s\\n' "$arg"; done >> "$AWS_CALLS"
echo -- >> "$AWS_CALLS"
case "$1 $2" in
  "sts get-caller-identity") echo "${{IDENTITY-{ARN}}}" ;;
  "cloudformation describe-stacks")
    if [ -z "${{SITE_BUCKET:-}}" ]; then
      echo "An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id il-grocery-prices-site does not exist" >&2
      exit 254
    fi
    case "$*" in
      *SiteBucketName*) echo "$SITE_BUCKET" ;;
      *SiteDistributionId*) echo "${{DISTRIBUTION-E1EXAMPLE}}" ;;
      *SiteDomainName*) echo d1example.cloudfront.net ;;
    esac ;;
  "s3 cp")
    folder=${{3#s3://*/}}
    if [ "$folder" = "${{FAIL_READ:-}}/" ]; then echo "fatal error: An error occurred (AccessDenied)" >&2; exit 1; fi
    if [ -d "$FAKE_BUCKET/$folder" ]; then mkdir -p "$4" && cp -R "$FAKE_BUCKET/$folder." "$4"; fi ;;
  "s3api list-objects-v2")
    if [ "${{FAIL_READ:-}}" = p ]; then echo "An error occurred (AccessDenied)" >&2; exit 254; fi
    printf '%s' "$P_KEYS" ;;
  "s3 sync")
    case " $* " in
      *" --include ${{FAIL_SYNC:-}} "*) echo "upload failed: An error occurred (AccessDenied)" >&2; exit 1 ;;
    esac ;;
  "cloudfront create-invalidation") echo I1EXAMPLE ;;
esac
"""
FAKE_PYTHON = """#!/bin/sh
{ echo python; for arg in "$@"; do printf '%s\\n' "$arg"; done; echo --; } >> "$AWS_CALLS"
if [ "$2" = shopper.check ]; then exit "${CHECK_EXIT:-0}"; fi
exec "$REAL_PYTHON" "$@"
"""
# Variables the scripts or the stand-ins read, never taken from the environment the tests run in.
_OWN = ("SITE_DIR", "PYTHON", "SITE_BUCKET", "IDENTITY", "DISTRIBUTION", "CHECK_EXIT", "P_KEYS", "FAKE_BUCKET",
        "FAIL_READ", "FAIL_SYNC")


def _run(tmp_path: Path, script: str, *args: str, **env: str) -> tuple[subprocess.CompletedProcess, list[list[str]]]:
    """Run `scripts/<script>` with the stand-ins on PATH and `env` added; the run and each call's arguments."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, text in (("aws", FAKE_AWS), ("python", FAKE_PYTHON)):
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod(0o755)
    calls = tmp_path / "calls"
    calls.write_text("")
    base = {key: value for key, value in os.environ.items() if key not in _OWN}
    env = base | {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "AWS_CALLS": str(calls),
                  "TMPDIR": str(tmp_path), "PYTHON": str(bin_dir / "python"), "REAL_PYTHON": sys.executable,
                  "FAKE_BUCKET": str(tmp_path / "published"), "P_KEYS": "None\n"} | env
    run = subprocess.run(["sh", str(ROOT / "scripts" / script), *args], env=env, capture_output=True, text=True)
    return run, [call.strip("\n").split("\n") for call in calls.read_text().split("--\n") if call.strip()]


def _sync(tmp_path: Path, day: str, **env: str) -> list[list[str]]:
    """Run sync.sh for `day`; each AWS call's arguments."""
    run, calls = _run(tmp_path, "sync.sh", day, **env)
    assert run.returncode == 0, run.stderr
    return calls


def _syncs(calls: list[list[str]]) -> list[list[str]]:
    return [call for call in calls if call[:2] == ["s3", "sync"]]


def _filters(call: list[str]) -> list[tuple[str, str]]:
    return [(arg, call[i + 1]) for i, arg in enumerate(call) if arg in ("--exclude", "--include")]


def _passes(path: str, filters: list[tuple[str, str]]) -> bool:
    """Whether the CLI's filters let `path` (relative to the call's source) through: the last filter that matches
    decides, and with none every file goes (awscli's customizations/s3/filters.py)."""
    through = True
    for kind, pattern in filters:
        if fnmatch(path, pattern):
            through = kind == "--include"
    return through


def _code(script: str) -> list[str]:
    """The script's lines that are not comments."""
    return [line for line in (ROOT / "scripts" / script).read_text().splitlines() if not line.lstrip().startswith("#")]


# ---- sync.sh ----

def test_sync_sh_copies_the_days_promotion_files_with_its_price_files_and_store_lists(tmp_path):
    calls = _sync(tmp_path, "2026-11-07")
    [raw] = [call for call in calls if call[:2] == ["s3", "sync"] and call[2].endswith("/raw/")]
    includes = [raw[i + 1] for i, arg in enumerate(raw) if arg == "--include"]
    assert raw[raw.index("--exclude") + 1] == "*"
    assert includes == ["chain=*/date=2026-11-07/PriceFull*", "chain=*/date=2026-11-07/pricefull*",
                        "chain=*/date=2026-11-07/PromoFull*", "chain=*/date=2026-11-07/promofull*",
                        "chain=*/date=2026-11-07/Stores*"]
    assert calls[0][:2] == ["sts", "get-caller-identity"]  # the identity is checked before anything is read


DAY = date(2026, 11, 7)
# What the Mac's hand build reads beyond the day's own files, each by the key its reader names it by: from the archive
# into data/, each chain's items tables (with their reports), the covered registries, the scoring summaries, the frozen
# forecasts files (the read-only freezer) and the scores files; from the site into site/, the basket's and the site's
# day files and the published ledger (B12, and the build's NotSynced checks: the plan's Task 19).
_ITEMS = items_path(Path("tables"), "osherad", DAY)
FROM_THE_ARCHIVE = [str(_ITEMS), str(_ITEMS.with_name("report.json")), str(covered_path(Path("tables"), DAY)),
                    str(summary_path(Path("tables"), DAY)), archive_key(DAY), scores_archive_key(DAY)]
FROM_THE_SITE = [day_key(DAY), str(site_day_path(Path(""), DAY)), LEDGER]


def _brought(calls: list[list[str]], bucket: str, local: str, key: str) -> list[list[str]]:
    """The sync calls that bring the bucket's `key` to `local/key`."""
    found = []
    for call in _syncs(calls):
        source, target = call[2], call[3]
        prefix = source.removeprefix(f"s3://{bucket}/")
        if (source.startswith(f"s3://{bucket}/") and key.startswith(prefix) and target == f"{local}/{prefix}"
                and _passes(key.removeprefix(prefix), _filters(call))):
            found.append(call)
    return found


@pytest.mark.parametrize("key", FROM_THE_ARCHIVE)
def test_sync_sh_reads_what_the_hand_build_needs_from_the_archive(tmp_path, key):
    [call] = _brought(_sync(tmp_path, "2026-11-07", SITE_BUCKET=SITE_BUCKET), ARCHIVE, "data", key)
    assert call[-4:] == PROFILE
    assert _brought(_sync(tmp_path / "no-stack", "2026-11-07"), ARCHIVE, "data", key) == [call]  # stack or none


@pytest.mark.parametrize("key", FROM_THE_SITE)
def test_sync_sh_reads_what_the_hand_build_needs_from_the_site(tmp_path, key):
    [call] = _brought(_sync(tmp_path, "2026-11-07", SITE_BUCKET=SITE_BUCKET), SITE_BUCKET, "site", key)
    assert call[-4:] == PROFILE
    # the bucket's copy wins unless the local file has its size and its exact time (sync.sh's comment)
    assert "--exact-timestamps" in call
    assert not _brought(_sync(tmp_path / "no-stack", "2026-11-07"), SITE_BUCKET, "site", key)  # no stack yet


def test_sync_sh_keeps_s3s_time_on_the_forecasts_files(tmp_path):
    """The Mac's build reads a synced forecasts file's time from its modification time (`ReadOnlyFreezer`), which
    must be the object's time in S3, the time in the published ledger. The CLI sets it so on every download (awscli
    2.34.9, customizations/s3/subscribers.py, `ProvideLastModifiedTimeSubscriber`); --exact-timestamps downloads again
    a local file of the same size whose time is not S3's (syncstrategy/exacttimestamps.py), which the default leaves
    when it is older; and nothing else in the script writes there."""
    calls = _sync(tmp_path, "2026-11-07", SITE_BUCKET=SITE_BUCKET)
    [call] = _brought(calls, ARCHIVE, "data", archive_key(DAY))
    assert call[:4] == ["s3", "sync", f"s3://{ARCHIVE}/forecasts/", "data/forecasts/"]
    assert "--exact-timestamps" in call
    assert [other for other in calls if any(arg.startswith("data/forecasts") for arg in other)] == [call]


def test_sync_sh_never_writes_to_aws(tmp_path):
    stack = _sync(tmp_path / "stack", "2026-11-07", SITE_BUCKET=SITE_BUCKET)
    for calls in (stack, _sync(tmp_path / "no-stack", "2026-11-07")):
        assert {tuple(call[:2]) for call in calls} == {("sts", "get-caller-identity"),
                                                       ("cloudformation", "describe-stacks"), ("s3", "sync")}
        for call in _syncs(calls):
            assert call[2].startswith("s3://") and not call[3].startswith("s3://")
    lines = [line for line in _code("sync.sh") if re.search(r"\baws s3", line)]
    assert len(lines) == len(_syncs(stack))  # every copy in the script ran above
    for line in lines:
        assert re.search(r'aws s3 sync "s3://[^"]+" (?!"?s3:)', line), line


# ---- publish.sh ----

def a_build(tmp_path: Path) -> Path:
    """A shopper build as `tests/test_shop_guard.py` makes one, with the marker and a page or file of every other kind,
    and the bucket (`tmp_path / "published"`) as it published that same build."""
    site = a_site(tmp_path)
    for key in ("index.html", "method.html", "basket.html", "browse/index.html", "search/05e9.json"):
        (site / key).parent.mkdir(parents=True, exist_ok=True)
        (site / key).write_text("<html></html>")
    (site / "search.js").write_text("")
    (site / MARKER).write_text("")
    a_bucket(tmp_path, site)
    return site


def _publish(tmp_path: Path, site: Path, **env: str) -> tuple[subprocess.CompletedProcess, list[list[str]]]:
    return _run(tmp_path, "publish.sh", **({"SITE_DIR": str(site), "SITE_BUCKET": SITE_BUCKET} | env))


def _uploads(calls: list[list[str]]) -> list[list[str]]:
    return [call for call in calls if call[:2] in (["s3", "sync"], ["cloudfront", "create-invalidation"])]


def _index(calls: list[list[str]], test) -> list[int]:
    return [i for i, call in enumerate(calls) if test(call)]


def test_publish_sh_uploads_a_build_the_check_and_the_guard_pass(tmp_path):
    run, calls = _publish(tmp_path, a_build(tmp_path), P_KEYS="\t".join(PAGES) + "\n")
    assert run.returncode == 0, run.stderr
    assert run.stdout.endswith("published: https://d1example.cloudfront.net/\n")
    assert len(_syncs(calls)) == 5
    assert calls[-2][:2] == ["cloudfront", "create-invalidation"] and "/*" in calls[-2]


def test_publish_sh_deletes_nothing(tmp_path):
    run, calls = _publish(tmp_path, a_build(tmp_path))
    assert run.returncode == 0, run.stderr
    for call in calls:
        assert "--delete" not in call
        assert not (call[0] == "s3" and call[1] in ("rm", "mv"))
        assert not (call[0] == "s3api" and call[1].startswith("delete"))
    for line in _code("publish.sh"):
        assert "--delete" not in line and not re.search(r"\baws s3 (rm|mv)\b|delete-object", line), line


def test_publish_sh_runs_the_check_and_the_guard_before_any_upload(tmp_path):
    lines = _code("publish.sh")
    first_sync = next(i for i, line in enumerate(lines) if "aws s3 sync" in line)
    check = [i for i, line in enumerate(lines) if "-m shopper.check" in line]
    guard = [i for i, line in enumerate(lines) if "-m shopper.guard" in line]
    reads = [i for i, line in enumerate(lines) if re.search(r"aws s3 cp|aws s3api", line)]
    assert len(check) == len(guard) == 1 and len(reads) == 2
    assert check[0] < min(reads) and max(reads) < guard[0] < first_sync

    site = a_build(tmp_path / "passes")
    run, calls = _publish(tmp_path / "passes", site)
    assert run.returncode == 0, run.stderr
    [checked] = _index(calls, lambda call: call[:3] == ["python", "-m", "shopper.check"])
    [guarded] = _index(calls, lambda call: call[:3] == ["python", "-m", "shopper.guard"])
    read = _index(calls, lambda call: call[0] in ("s3", "s3api") and call[1] in ("cp", "list-objects-v2"))
    put = _index(calls, lambda call: call in _uploads(calls))
    assert calls[checked][3] == calls[guarded][3] == str(site)
    assert len(read) == 5 and len(put) == 6
    assert checked < min(read) and max(read) < guarded < min(put)

    site = a_build(tmp_path / "check")
    run, calls = _publish(tmp_path / "check", site, CHECK_EXIT="1")
    assert run.returncode == 1 and "the site check failed; nothing uploaded" in run.stderr
    assert not _uploads(calls) and not _index(calls, lambda call: call[:3] == ["python", "-m", "shopper.guard"])

    site = a_build(tmp_path / "guard")
    (site / "p/2000000000046.html").unlink()  # a published product page the build lacks
    run, calls = _publish(tmp_path / "guard", site, P_KEYS="\t".join(PAGES) + "\n")
    assert run.returncode == 1 and "the publish guard failed; nothing uploaded" in run.stderr
    assert "1 published product page is not in the build (p/2000000000046.html)" in run.stderr
    assert not _uploads(calls)


@pytest.mark.parametrize("folder", ["days", "site-days", "forecasts", "scores"])
def test_publish_sh_compares_the_build_with_each_published_folder(tmp_path, folder):
    """The bucket's published records are copied into the folder the guard reads them from: a published file in each
    that the build would replace stops the upload."""
    site = a_build(tmp_path)
    published = tmp_path / "published" / folder
    target = sorted(path for path in published.iterdir() if path.name != "ledger.csv")[0]
    target.write_bytes(b'{"other": 1}' if target.suffix == ".json" else b"other bytes")
    run, calls = _publish(tmp_path, site)
    assert run.returncode == 1 and "the publish guard failed; nothing uploaded" in run.stderr
    assert f"{folder}/{target.name}" in run.stderr
    assert not _uploads(calls)
    [copy] = [call for call in calls if call[:3] == ["s3", "cp", f"s3://{SITE_BUCKET}/{folder}/"]]
    assert copy[4:] == ["--recursive", *PROFILE]


def test_publish_sh_compares_the_build_with_the_published_ledger(tmp_path):
    site = a_build(tmp_path)
    (tmp_path / "published" / LEDGER).write_bytes((site / LEDGER).read_bytes() + b"2026-11-21,ab,2026-11-21T10:00:00Z\n")
    run, calls = _publish(tmp_path, site)
    assert run.returncode == 1 and f"{LEDGER} does not begin with the published ledger" in run.stderr
    assert not _uploads(calls)


@pytest.mark.parametrize(("read", "said"), [(folder, f"the bucket's {folder}/ could not be read")
                                           for folder in ("days", "site-days", "forecasts", "scores")]
                         + [("p", "the bucket's product pages could not be listed")])
def test_publish_sh_stops_on_a_failed_read_of_the_bucket(tmp_path, read, said):
    """A read of the bucket that fails stops the upload by its own test, not by `set -e` alone: taken for an empty
    bucket, it would leave the guard comparing the build with nothing, and a published record could be replaced."""
    run, calls = _publish(tmp_path, a_build(tmp_path), FAIL_READ=read)
    assert run.returncode == 2 and f"{said}; nothing uploaded" in run.stderr
    assert not _uploads(calls) and not _index(calls, lambda call: call[:3] == ["python", "-m", "shopper.guard"])


UPLOAD_ORDER = ["*.csv.gz", "*.csv", "*.json", "*.js", "*.html"]


def test_publish_sh_uploads_the_data_files_before_the_pages(tmp_path):
    """The final review's finding 8: the records first (the forecasts and scores files), then the ledger, the day and
    site-day files with the search pieces, `search.js`, and the pages last, as the site run puts them
    (`basket.site.upload`), so a stop part-way never leaves a live page naming a file not yet up."""
    run, calls = _publish(tmp_path, a_build(tmp_path))
    assert run.returncode == 0, run.stderr
    assert [_filters(call)[1][1] for call in _syncs(calls)] == UPLOAD_ORDER


@pytest.mark.parametrize("failing", UPLOAD_ORDER)
def test_publish_sh_stops_on_a_failed_upload(tmp_path, failing):
    """The final review's finding 8: an upload that fails stops the script by its own test, not by `set -e` alone,
    with the uploads after it not made and nothing invalidated; the message says what went up. A rerun then passes
    the guard, the files already up being the build's own (the first publish test publishes over a bucket holding
    them)."""
    run, calls = _publish(tmp_path, a_build(tmp_path), FAIL_SYNC=failing)
    assert run.returncode == 1
    assert (f"the upload of {failing} failed: the kinds before it went up, none after it, and nothing was invalidated; "
            "run it again") in run.stderr
    assert [_filters(call)[1][1] for call in _syncs(calls)] == UPLOAD_ORDER[:UPLOAD_ORDER.index(failing) + 1]
    assert not _index(calls, lambda call: call[:2] == ["cloudfront", "create-invalidation"])


def test_publish_sh_refuses_an_earlier_day_over_a_later_published_one(tmp_path):
    """A build whose site/ lacks the later day the bucket holds (a wrong --day, or a folder sync.sh did not fill) is
    refused by the guard before its pages go up over that day's."""
    site = a_build(tmp_path)
    (tmp_path / "published" / NEXT_DAY).write_text((site / sorted((site / "site-days").iterdir())[-1]).read_text())
    run, calls = _publish(tmp_path, site)
    assert run.returncode == 1 and "the publish guard failed; nothing uploaded" in run.stderr
    assert LATER_PUBLISHED in run.stderr
    assert not _uploads(calls)


@pytest.mark.parametrize(("listed", "passes"), [
    ("None\n", True),                                              # an empty prefix, as the CLI prints it
    ("", True),
    ("\t".join(PAGES) + "\n", True),
    ("\t".join(PAGES) + "\tp/2000000000099.html\n", False),        # a published page the build lacks
    ("\t".join(PAGES) + "\nNone\np/2000000000099.html\n", False),  # pages of a listing, a line each
])
def test_publish_sh_gives_the_guard_the_published_product_pages(tmp_path, listed, passes):
    run, calls = _publish(tmp_path, a_build(tmp_path), P_KEYS=listed)
    assert run.returncode == (0 if passes else 1), run.stderr
    assert bool(_uploads(calls)) is passes
    if not passes:
        assert "(p/2000000000099.html)" in run.stderr
    [listing] = [call for call in calls if call[:2] == ["s3api", "list-objects-v2"]]
    assert listing[2:] == ["--bucket", SITE_BUCKET, "--prefix", "p/", "--query", "Contents[].Key", "--output", "text",
                           *PROFILE]


def test_publish_sh_sets_each_content_type_and_cache_control(tmp_path):
    """One allowlisted sync per kind of file, each with its content type as `basket.site.CONTENT_TYPES` gives the
    site run's uploads, and max-age=300; every file the build writes matches one allowlist, its own type's, and the
    marker none."""
    site = a_build(tmp_path)
    run, calls = _publish(tmp_path, site)
    assert run.returncode == 0, run.stderr
    allowlists = {}
    for call in _syncs(calls):
        assert call[2:4] == [f"{site}/", f"s3://{SITE_BUCKET}/"]
        assert _filters(call)[0] == ("--exclude", "*") and len(_filters(call)) == 2
        assert call[call.index("--cache-control") + 1] == CACHE_CONTROL
        assert call[-4:] == PROFILE
        allowlists[_filters(call)[1][1]] = call[call.index("--content-type") + 1]
    assert allowlists == {"*.html": CONTENT_TYPES[".html"], "*.json": CONTENT_TYPES[".json"],
                          "*.js": CONTENT_TYPES[".js"], "*.csv": CONTENT_TYPES[".csv"],
                          "*.csv.gz": CONTENT_TYPES[".gz"]}
    files = sorted(path.relative_to(site).as_posix() for path in site.rglob("*") if path.is_file())
    assert {Path(key).suffix for key in files} == set(CONTENT_TYPES) | {""}
    for key in files:
        matched = [kind for pattern, kind in allowlists.items() if fnmatch(f"{site}/{key}", f"{site}/{pattern}")]
        assert matched == ([] if key == MARKER else [CONTENT_TYPES[Path(key).suffix]]), key


@pytest.mark.parametrize("marker", [None, ".basket-site"])
def test_publish_sh_needs_the_shopper_marker(tmp_path, marker):
    site = a_build(tmp_path)
    (site / MARKER).unlink()
    if marker:
        (site / marker).write_text("")
    run, calls = _publish(tmp_path, site)
    assert run.returncode == 1
    assert run.stderr == f"{site} has no {MARKER} marker, so it is not a shopper site build; nothing uploaded\n"
    assert calls == [["sts", "get-caller-identity", "--profile", "flights-sam", "--query", "Arn", "--output", "text"]]


@pytest.mark.parametrize(("env", "said"), [
    ({"IDENTITY": "arn:aws:iam::111111111111:user/someone"}, "profile flights-sam is arn:aws:iam::111111111111"),
    ({"SITE_BUCKET": ARCHIVE}, f"stack output SiteBucketName is '{ARCHIVE}'"),
    ({"SITE_BUCKET": "il-grocery-prices-site-sitebucket-"}, "not a il-grocery-prices-site-sitebucket-* bucket"),
    ({"DISTRIBUTION": ""}, "stack output SiteDistributionId is ''"),
    ({"DISTRIBUTION": "None"}, "stack output SiteDistributionId is 'None'"),
])
def test_publish_sh_uploads_nothing_to_another_account_bucket_or_distribution(tmp_path, env, said):
    run, calls = _publish(tmp_path, a_build(tmp_path), **env)
    assert run.returncode == 1 and said in run.stderr and "nothing uploaded" in run.stderr
    assert not [call for call in calls if call[0] in ("s3", "s3api", "cloudfront")]


def test_publish_sh_refuses_a_site_path_its_filters_would_misread(tmp_path):
    odd = a_build(tmp_path).rename(tmp_path / "site[1]")
    run, calls = _publish(tmp_path, odd)
    assert run.returncode == 1 and "has [, ], ? or *" in run.stderr
    assert [call[0] for call in calls] == ["sts"]

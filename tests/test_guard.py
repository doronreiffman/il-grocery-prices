"""The publish guard (`basket.guard`, B12): an upload replaces a published day file only with a revision of it.

The day files are the test day of `tests/test_page.py` as `basket.page.render_day` writes it, and its revision as
`basket.build` makes one: `revised` set and the published run added to `revisions`.
"""
import json
from pathlib import Path

import pytest

from basket.guard import guard_days, main
from basket.page import render_day
from test_page import a_public

NAME = "2026-11-02.json"
NOT_A_REVISION = (f"days/{NAME} differs from the published day and is not a revision of it: "
                  "run scripts/sync.sh first")


def published_day() -> dict:
    return a_public()


def revision_of(published: dict, reason: str = "a parser fix") -> dict:
    """`published` revised as `basket.build` revises it: the published run kept at the end of `revisions`."""
    earlier = {"run_id": published["run_id"], "code_sha": published["code_sha"], "built_at": published["built_at"],
               "revised": published["revised"],
               "totals": {slug: chain["total"] for slug, chain in published["chains"].items()}}
    return published | {"run_id": "100000Z-basket-9f9f", "revisions": published["revisions"] + [earlier],
                        "revised": {"on": "2026-11-03", "reason": reason}}


def folders(tmp_path: Path, local: dict | bytes | None, published: dict | bytes | None) -> tuple[Path, Path]:
    """A local and a published days folder, each holding the day file given (a dict as the build writes it, raw
    bytes as they are), or none."""
    found = []
    for name, day in (("local", local), ("published", published)):
        folder = tmp_path / name / "days"
        folder.mkdir(parents=True)
        if day is not None:
            data = day if isinstance(day, bytes) else render_day(day).encode("utf-8")
            (folder / NAME).write_bytes(data)
        found.append(folder)
    return found[0], found[1]


def test_the_same_day_passes(tmp_path):
    day = published_day()
    assert guard_days(*folders(tmp_path, day, day)) == []


def test_a_differing_day_that_is_not_a_revision_is_refused(tmp_path):
    published = published_day()
    rebuilt = published | {"run_id": "100000Z-basket-9f9f", "collected_by": "10:45"}  # a build that never saw it
    assert guard_days(*folders(tmp_path / "rebuilt", rebuilt, published)) == [NOT_A_REVISION]
    # A revision built from a site/ that lacked the published day's own revision: as many revisions, not more.
    revised = revision_of(published)
    stale = revision_of(published, "another fix")
    assert guard_days(*folders(tmp_path / "stale", stale, revised)) == [NOT_A_REVISION]


def test_a_revision_passes(tmp_path):
    published = published_day()
    assert guard_days(*folders(tmp_path / "first", revision_of(published), published)) == []
    revised = revision_of(published)
    assert guard_days(*folders(tmp_path / "second", revision_of(revised, "a second fix"), revised)) == []


@pytest.mark.parametrize("change", [
    {"revised": None},  # more revisions but no reason
    {"revised": "a parser fix"},  # a reason, but not as the build writes it
    {"revisions": "one"},  # revisions not a list
])
def test_a_revision_needs_a_reason_object_and_a_longer_revisions_list(tmp_path, change):
    published = published_day()
    assert guard_days(*folders(tmp_path, revision_of(published) | change, published)) == [NOT_A_REVISION]


def test_a_published_day_without_a_revisions_list_is_not_revised_over(tmp_path):
    published = published_day()
    damaged = {key: value for key, value in published.items() if key != "revisions"}
    assert guard_days(*folders(tmp_path, revision_of(published), damaged)) == [NOT_A_REVISION]


@pytest.mark.parametrize("data", [b"{", b"\xff\xfe", b"[1, 2]"])
def test_an_unreadable_day_file_is_refused_naming_the_file(tmp_path, data):
    local, published = folders(tmp_path / "local", data, published_day())
    assert guard_days(local, published) == [f"{local / NAME}: not a day file (a JSON object)"]
    local, published = folders(tmp_path / "published", revision_of(published_day()), data)
    assert guard_days(local, published) == [f"{published / NAME}: not a day file (a JSON object)"]


def test_a_new_day_and_a_day_only_published_pass(tmp_path):
    local, published = folders(tmp_path, published_day(), None)
    assert guard_days(local, published) == []  # new to the bucket
    assert guard_days(local, tmp_path / "absent") == []  # the bucket's days/ is empty before the first upload
    (published / "2026-11-01.json").write_text(json.dumps({"day": "2026-11-01"}), encoding="utf-8")
    assert guard_days(local, published) == []  # the day-file upload never deletes it


def test_every_day_is_checked_and_named(tmp_path):
    published = published_day()
    local, bucket = folders(tmp_path, published, published)
    other = published | {"day": "2026-11-01"}
    (bucket / "2026-11-01.json").write_text(render_day(other), encoding="utf-8")
    (local / "2026-11-01.json").write_text(render_day(other | {"collected_by": "10:45"}), encoding="utf-8")
    (local / "notes.txt").write_text("not a day file", encoding="utf-8")  # only .json files are uploaded as days
    assert guard_days(local, bucket) == [NOT_A_REVISION.replace(NAME, "2026-11-01.json")]


def test_main_exit_codes(tmp_path, capsys):
    published = published_day()
    local, bucket = folders(tmp_path / "same", published, published)
    assert main([str(local), str(bucket)]) == 0
    assert capsys.readouterr() == ("", "")
    local, bucket = folders(tmp_path / "other", published | {"collected_by": "10:45"}, published)
    assert main([str(local), str(bucket)]) == 1
    assert capsys.readouterr() == ("", NOT_A_REVISION + "\n")
    assert main([str(tmp_path / "absent"), str(bucket)]) == 2
    assert capsys.readouterr().err == f"no folder at {tmp_path / 'absent'}: no day file to compare\n"
    assert main([str(local)]) == 2
    assert capsys.readouterr().err.startswith("usage: python -m basket.guard")

"""The dbt layer's unit tests (docs/dbt-layer.md, section 4), run by dbt itself, and what no dbt run here may do: run
with telemetry on, or write outside its own temporary folders (tests/dbt_run.py).
"""
import pytest

from dbt_run import HOME, PROJECT, ROOT, TARGET, run_dbt

# What a run must never touch: the Mac's built database and dbt's own default output folders.
WATCHED = (ROOT / "data" / "dbt.duckdb", PROJECT / "target", PROJECT / "logs")


def _mtimes() -> dict[str, int]:
    """The mtime of each watched path that exists, and of everything under a watched folder."""
    found = {}
    for watched in WATCHED:
        for path in [watched, *watched.rglob("*")] if watched.is_dir() else [watched] if watched.exists() else []:
            found[str(path)] = path.lstat().st_mtime_ns
    return found


@pytest.fixture(scope="module")
def before():
    return _mtimes()


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    return tmp_path_factory.mktemp("units")


@pytest.fixture(scope="module")
def units(before, work):
    run = run_dbt(["test", "--select", "test_type:unit"], work)
    assert run.code == 0, run.output
    return run


def test_telemetry_is_off_as_dbt_reads_it(units):
    assert units.manifest["metadata"]["send_anonymous_usage_stats"] is False


def test_a_dbt_run_writes_nothing_outside_its_temporary_folders(units, before, work):
    assert sorted((work / HOME).iterdir()) == []
    assert not (PROJECT / ".user.yml").exists()
    assert _mtimes() == before   # nothing written there, and nothing made there that was not
    assert (work / TARGET / "manifest.json").is_file()

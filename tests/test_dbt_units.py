"""The dbt layer's unit tests (docs/dbt-layer.md, section 4), run by dbt itself; what no dbt run here may do: run with
telemetry on, or write outside its own temporary folders; and the runner's own rules (tests/dbt_run.py), each tried
on a stand-in for dbt, which needs no .venv-dbt and reaches nothing.
"""
import json
import stat
import sys
import textwrap
from pathlib import Path

import pytest

import dbt_run
from dbt_run import HOME, PROJECT, ROOT, TARGET, run_dbt


def _snapshot() -> dict[str, int]:
    """Every path under dbt/ (dbt's default target and log folders are there), and the Mac's built database if there
    is one, each with its mtime."""
    paths = [PROJECT, *PROJECT.rglob("*"), *(ROOT / "data").glob("dbt.duckdb*")]
    return {str(path): path.lstat().st_mtime_ns for path in paths}


@pytest.fixture(scope="module")
def before():
    return _snapshot()


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    return tmp_path_factory.mktemp("units")


@pytest.fixture(scope="module")
def units(before, work):
    """The project's unit tests, run once; whether they pass is test_every_unit_test_passes's to say."""
    return run_dbt(["test", "--select", "test_type:unit"], work)


@pytest.fixture
def stand_in(tmp_path, monkeypatch):
    """Makes a stand-in for dbt from a Python body, which sees `argv` (the arguments dbt would get) and `work` (the
    run's folder, above the home folder it is given), and puts it where the runner looks for dbt."""
    def make(body: str) -> Path:
        script = tmp_path / "stand-in" / "dbt"
        script.parent.mkdir()
        script.write_text(f"#!{sys.executable}\nimport json, os, sys, time\nfrom pathlib import Path\n"
                          "argv = sys.argv[1:]\nwork = Path(os.environ['HOME']).parent\n" + textwrap.dedent(body))
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setattr(dbt_run, "DBT", script)
        return script
    return make


def test_every_unit_test_passes(units):
    assert units.code == 0, units.output
    assert {name: status for name, (status, _) in units.results.items() if status != "pass"} == {}


def test_every_declared_unit_test_ran(units):
    declared = sorted(test["name"] for test in units.manifest["unit_tests"].values())
    assert declared != []
    assert sorted(units.results) == declared


def test_every_model_with_a_rule_has_a_unit_test(units):
    # The intermediate and analysis models are read from their folders, so each model a later task adds joins the list.
    ruled = {path.stem for folder in ("intermediate", "marts") for path in (PROJECT / "models" / folder).rglob("*.sql")}
    ruled |= {"stg_store_type_days", "stg_published_store_pages", "stg_published_basket", "known_differences"}
    tested = {test["model"] for test in units.manifest["unit_tests"].values()}
    assert sorted(ruled - tested) == []


def test_telemetry_is_off_as_dbt_reads_it(units):
    assert units.manifest["metadata"]["send_anonymous_usage_stats"] is False


def test_a_dbt_run_writes_nothing_outside_its_temporary_folders(units, before, work):
    assert sorted((work / HOME).iterdir()) == []
    assert not (PROJECT / ".user.yml").exists()
    assert _snapshot() == before   # nothing under dbt/ written, made or removed
    assert (work / TARGET / "manifest.json").is_file()


def test_dbt_s_output_holds_no_colour_codes(units):
    assert "\x1b" not in units.output


def test_no_setting_for_dbt_reaches_it_from_the_test_s_environment(stand_in, tmp_path, monkeypatch):
    stand_in("(work / 'env.json').write_text(json.dumps(dict(os.environ)))\n")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("GROCERY_DBT_DB", str(tmp_path / "elsewhere" / "dbt.duckdb"))
    work = tmp_path / "work"
    run_dbt(["parse"], work)
    env = json.loads((work / "env.json").read_text())
    assert "DO_NOT_TRACK" not in env
    assert [name for name in env if name.startswith("DBT_")] == []
    assert (env["GROCERY_DBT_DB"], env["HOME"]) == (str(work / "dbt.duckdb"), str(work / HOME))


def test_a_dbt_run_past_its_time_limit_is_stopped_and_fails(stand_in, tmp_path, monkeypatch):
    stand_in("time.sleep(5)\n")
    monkeypatch.setattr(dbt_run, "TIMEOUT", 0.5)
    with pytest.raises(pytest.fail.Exception, match=r"dbt parse did not finish within 0\.5 s and was stopped"):
        run_dbt(["parse"], tmp_path / "work")


def test_a_work_folder_already_used_is_refused(stand_in, tmp_path):
    stand_in("")
    work = tmp_path / "work"
    (work / TARGET).mkdir(parents=True)
    with pytest.raises(ValueError, match="is not empty: every dbt run needs a fresh folder"):
        run_dbt(["parse"], work)


def test_two_results_of_one_name_are_refused(stand_in, tmp_path):
    # A data test and a unit test of the same name: the second must not hide the first's result.
    stand_in("""
        target = Path(argv[argv.index("--target-path") + 1])
        target.mkdir(parents=True)
        nodes, units = {"test.grocery.same.1a2b": {"name": "same"}}, {"unit_test.grocery.a_model.same": {"name": "same"}}
        (target / "manifest.json").write_text(json.dumps({"nodes": nodes, "unit_tests": units}))
        results = [{"unique_id": node, "status": "pass", "failures": 0} for node in [*nodes, *units]]
        (target / "run_results.json").write_text(json.dumps({"results": results}))
    """)
    with pytest.raises(ValueError, match="two dbt nodes are named same"):
        run_dbt(["test"], tmp_path / "work")

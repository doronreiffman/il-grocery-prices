"""Run dbt for a test (docs/dbt-layer.md, section 6): always from inside dbt/, with .venv-dbt's dbt, each run in
folders of its own.

A run's target folder, log folder and home folder, and its database unless one is given, are all under `work`, a fresh
folder every call. So dbt's partial parse never reads an earlier run's project (a planted bug would go unseen), and no
run reads or writes data/, dbt/target/, dbt/logs/ or the home folder. The run's environment is the test's own, less
every DBT_ variable, GROCERY_DBT_DB and DO_NOT_TRACK, so none of the machine's settings for dbt reaches it. Its output
comes without colour codes, and a run past its time limit is stopped and fails the test.
"""
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "dbt"
DBT = ROOT / ".venv-dbt" / "bin" / "dbt"
MISSING = "make .venv-dbt: docs/operations.md, Develop"
TARGET, LOGS, HOME = "target", "logs", "home"   # a run's folders, under its work folder
DATABASE = "dbt.duckdb"                          # a run's database, under its work folder, unless one is given
# Taken out of a run's environment, besides every DBT_ variable. DO_NOT_TRACK set to a true value (1, t, true, y or
# yes, in any case) turns dbt's telemetry off whatever the project says (dbt-core 1.12.6, dbt/cli/flags.py), so a
# machine that sets it so would hide the project's own setting from the test that reads it.
CLEARED = ("GROCERY_DBT_DB", "DO_NOT_TRACK")
# Seconds a dbt run may take before it is stopped. A dbt command here starts in 4 to 5 s (the design's section 6) and
# the runs read small synthetic tables. The slowest are the golden's: the whole of tests/test_dbt_golden.py, its
# extraction and its four dbt runs, took 24 to 39 s on an 8 GB Apple M2 (two runs, 26 November 2026). 600 s leaves
# them room and still stops a run that waits forever (on the network, on a locked database) inside the 1,400 s the
# mutation check gives each of its pytest runs (scripts/mutation_check.py, TIME_LIMIT).
TIMEOUT = 600


@dataclass(frozen=True)
class DbtRun:
    code: int                                    # dbt's exit code
    output: str                                  # its stdout and stderr
    results: dict[str, tuple[str, int | None]]   # each node's name -> (status, failures), from run_results.json
    manifest: dict                               # target/manifest.json
    database: Path


def run_dbt(command: Sequence[str], work: Path, vars: Mapping[str, object] | None = None,
            database: Path | None = None) -> DbtRun:
    """Run `dbt <command>` from inside dbt/, its target, logs and home folders under `work`, which must be new or empty;
    `vars` given to dbt as JSON; the database `database`, else one under `work`."""
    if not DBT.is_file():
        pytest.fail(MISSING, pytrace=False)
    if work.exists() and any(work.iterdir()):
        raise ValueError(f"{work} is not empty: every dbt run needs a fresh folder")
    (work / HOME).mkdir(parents=True)
    database = database or work / DATABASE
    env = {name: value for name, value in os.environ.items() if not name.startswith("DBT_") and name not in CLEARED}
    env |= {"HOME": str(work / HOME), "GROCERY_DBT_DB": str(database)}
    args = [str(DBT), *command, "--no-use-colors", "--target-path", str(work / TARGET), "--log-path", str(work / LOGS)]
    if vars is not None:
        args += ["--vars", json.dumps(vars)]
    try:
        done = subprocess.run(args, cwd=PROJECT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired as stopped:
        so_far = stopped.output.decode(errors="replace") if isinstance(stopped.output, bytes) else stopped.output or ""
        pytest.fail(f"dbt {' '.join(command)} did not finish within {TIMEOUT} s and was stopped; its output so far:\n"
                    f"{so_far}", pytrace=False)
    manifest = _read(work / TARGET / "manifest.json") or {}
    return DbtRun(done.returncode, done.stdout, _results(work / TARGET / "run_results.json", manifest), manifest, database)


def query(database: Path, sql: str) -> list[tuple]:
    """The rows of `sql` over the database, opened read-only with the project's DuckDB."""
    with duckdb.connect(str(database), read_only=True) as connection:
        return connection.execute(sql).fetchall()


def _read(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.is_file() else None


def _results(path: Path, manifest: dict) -> dict[str, tuple[str, int | None]]:
    """Each node's (status, failures) by its name, which the manifest gives; a name two nodes share is refused, so one
    result never hides another."""
    nodes = {**manifest.get("nodes", {}), **manifest.get("unit_tests", {})}
    results = {}
    for result in (_read(path) or {}).get("results", []):
        name = nodes.get(result["unique_id"], {}).get("name", result["unique_id"])
        if name in results:
            raise ValueError(f"two dbt nodes are named {name}")
        results[name] = (result["status"], result["failures"])
    return results

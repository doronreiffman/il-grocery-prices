"""Run dbt for a test (docs/dbt-layer.md, section 6): always from inside dbt/, with .venv-dbt's dbt, each run in
folders of its own.

A run's target folder, log folder and home folder, and its database unless one is given, are all under `work`, a fresh
folder every call. So dbt's partial parse never reads an earlier run's project (a planted bug would go unseen), and no
run reads or writes data/, dbt/target/, dbt/logs/ or the home folder. The run's environment is the test's own, less
every DBT_ variable and GROCERY_DBT_DB, so a setting on the machine never reaches it.
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
    env = {name: value for name, value in os.environ.items() if not name.startswith("DBT_") and name != "GROCERY_DBT_DB"}
    env |= {"HOME": str(work / HOME), "GROCERY_DBT_DB": str(database)}
    args = [str(DBT), *command, "--target-path", str(work / TARGET), "--log-path", str(work / LOGS)]
    if vars is not None:
        args += ["--vars", json.dumps(vars)]
    done = subprocess.run(args, cwd=PROJECT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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

"""The DuckDB connection (`basket.duck`): the temp folder and the memory ceiling come from the environment.

In Lambda the working directory is read-only and the function has 2 GB; on the Mac both variables stay unset
and DuckDB's defaults stand (`.tmp` under the working directory, 80% of the machine's RAM).
"""
from datetime import date
from decimal import Decimal

import duckdb

from basket import duck
from basket.duck import MEMORY_LIMIT_VAR, TEMP_DIRECTORY_VAR, connect
from basket.extract import Row, table_path, write_table
from basket.rules import open_day


def test_unset_leaves_duckdbs_defaults():
    con = connect({})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == ".tmp"


def test_temp_directory_and_memory_limit_are_set_from_the_environment(tmp_path):
    con = connect({TEMP_DIRECTORY_VAR: str(tmp_path / "duck"), MEMORY_LIMIT_VAR: "100MB"})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == str(tmp_path / "duck")
    assert con.execute("SELECT current_setting('memory_limit')").fetchone()[0] == "95.3 MiB"


def test_no_argument_reads_the_process_environment(monkeypatch, tmp_path):
    """The Lambda calls connect() bare: the variables it sets in the function's configuration are the process's."""
    monkeypatch.setenv(TEMP_DIRECTORY_VAR, str(tmp_path / "duck"))
    monkeypatch.setenv(MEMORY_LIMIT_VAR, "100MB")
    con = connect()
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == str(tmp_path / "duck")
    assert con.execute("SELECT current_setting('memory_limit')").fetchone()[0] == "95.3 MiB"


def test_blank_values_count_as_unset():
    con = connect({TEMP_DIRECTORY_VAR: " ", MEMORY_LIMIT_VAR: ""})
    assert con.execute("SELECT current_setting('temp_directory')").fetchone()[0] == ".tmp"


def test_extract_and_rules_connect_through_duck(monkeypatch, tmp_path):
    """Both call sites take their connection from duck.connect, so the Lambda's settings reach both."""
    calls = []
    monkeypatch.setattr(duck, "connect", lambda env=None: calls.append("connect") or duckdb.connect())
    row = Row("1", None, "7290000000001", "7290000000001", True, "x", Decimal("1.00"), "1", "יחידות", "", "", "f.gz")
    write_table([row], table_path(tmp_path, "osherad", date(2026, 1, 1)))
    with open_day(tmp_path, date(2026, 1, 1), ["osherad"]) as con:
        assert con.execute("SELECT count(*) FROM prices").fetchone()[0] == 1
    assert calls == ["connect", "connect"]

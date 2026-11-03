"""The DuckDB connection the basket code opens: its temp folder and memory ceiling come from the environment.

In Lambda the working directory is read-only and DuckDB's default temp folder is `.tmp` under it, and its
default memory limit is 80% of what it reads as the machine's RAM, which is not the function's 2 GB. The
Lambda sets `DUCKDB_TEMP_DIRECTORY` (a folder under `/tmp`) and `DUCKDB_MEMORY_LIMIT` (e.g. `1200MB`); on the
Mac both stay unset and DuckDB's defaults stand. A variable that is unset, empty or only spaces is unset; a temp folder
is read without the spaces around it, as `basket.handler.Config` reads the folder it sweeps.
A temp folder that is not there yet is created, its parents too.
Both settings are passed as prepared parameters, never put into the SQL text.
"""
import os
from collections.abc import Mapping
from pathlib import Path

import duckdb

TEMP_DIRECTORY_VAR = "DUCKDB_TEMP_DIRECTORY"
MEMORY_LIMIT_VAR = "DUCKDB_MEMORY_LIMIT"


def connect(env: Mapping[str, str] | None = None) -> duckdb.DuckDBPyConnection:
    """An in-memory connection with the temp folder and memory limit `env` names (default `os.environ`)."""
    env = os.environ if env is None else env
    con = duckdb.connect()
    temp_directory = env.get(TEMP_DIRECTORY_VAR, "").strip()
    if temp_directory:
        Path(temp_directory).mkdir(parents=True, exist_ok=True)
        con.execute("SET temp_directory = ?", [temp_directory])
    memory_limit = env.get(MEMORY_LIMIT_VAR, "")
    if memory_limit.strip():
        con.execute("SET memory_limit = ?", [memory_limit])
    return con

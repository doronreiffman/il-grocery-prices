"""Pin the dbt layer's frame (docs/dbt-layer.md, section 6): the pins of its own environment, .venv-dbt, and the one
install of it, the project's settings, its rule constants held to the Python's, its seven sources, what git ignores,
and what is never in the project. Nothing here runs dbt: tests/test_dbt_units.py does.

The YAML files are read with yaml.safe_load, so a test reads the values dbt reads, not the text around them.
"""
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import yaml

from shopper.columns import COLUMNS
from shopper.history import READ_DAYS
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS
from shopper.promotions import KINDS
from shopper.verdict import DEAL_MIN

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "dbt"
REQUIREMENTS = ROOT / "requirements-dbt.txt"
DEV_REQUIREMENTS = ROOT / "requirements-dev.txt"
WORKFLOWS = (ROOT / ".github" / "workflows" / "ci.yml", ROOT / ".github" / "workflows" / "mutations.yml")
PIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*==[0-9][0-9A-Za-z.]*")
PACKAGES = 59   # dbt-core 1.12.6 and dbt-duckdb 1.11.0 with duckdb 1.5.6 on Python 3.13 (the design's section 6)

# Each source table, by source and name: the reader it calls on its files in place and the var naming where they are.
SOURCES = {
    ("tables", "prices"): ("read_parquet(", 'var("tables")'),
    ("tables", "items"): ("read_parquet(", 'var("tables")'),
    ("tables", "promotions"): ("read_parquet(", 'var("tables")'),
    ("tables", "items_reports"): ("read_json(", 'var("tables")'),
    ("published", "site_days"): ("read_json(", 'var("site")'),
    ("published", "basket_days"): ("read_json(", 'var("site")'),
    ("repo", "basket"): ("read_json(", 'var("basket_file")'),
}
# The design's names for the sources, which the README's lineage map draws.
LABELS = {
    ("tables", "prices"): "prices",
    ("tables", "items"): "items",
    ("tables", "promotions"): "promotions",
    ("tables", "items_reports"): "items reports",
    ("published", "site_days"): "published site-day files",
    ("published", "basket_days"): "published basket day files",
    ("repo", "basket"): "the basket",
}
# Where each path var's default points, from the repository's root.
PATHS = {"tables": "data/tables", "site": "site", "basket_file": "src/basket/baskets/v1.json"}

# Every way a model could read the clock: DuckDB 1.5.6's clock functions and keywords (duckdb_functions(); `localtime`
# alone is a keyword giving the time of day, so it is matched as a whole word), and dbt's own time of the run. The
# longer names come first, so a finding names the function exactly.
CLOCK = re.compile(r"current_localtimestamp|current_localtime|get_current_timestamp|get_current_time|transaction_timestamp"
                   r"|current_date|current_timestamp|current_time|localtimestamp|\blocaltime\b|\bnow\s*\(|\btoday\s*\("
                   r"|run_started_at|modules\.datetime", re.IGNORECASE)
FLOATING = re.compile(r"\b(?:double|float|float4|float8|real)\b", re.IGNORECASE)


def _load(path: Path):
    return yaml.safe_load(path.read_text())


def _project() -> dict:
    return _load(PROJECT / "dbt_project.yml")


def _name(name: str) -> str:
    """A package's name as pip compares it: case-blind, with '-', '_' and '.' the same."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _lines(path: Path) -> list[str]:
    """The file's lines that are neither blank nor a comment."""
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]


def _pins(path: Path) -> dict[str, str]:
    """The file's pins by package name, with those of any file it names with -r."""
    pins = {}
    for line in _lines(path):
        if line.startswith("-r "):
            pins |= _pins(path.parent / line.removeprefix("-r ").strip())
        else:
            name, _, version = line.partition("==")
            pins[_name(name)] = version
    return pins


def _runs(workflow: Path) -> list[str]:
    """Every `run` command of the workflow's jobs, in order."""
    return [step["run"].strip() for job in _load(workflow)["jobs"].values() for step in job["steps"] if "run" in step]


def _tables() -> dict[tuple[str, str], dict]:
    sources = _load(PROJECT / "models" / "sources.yml")["sources"]
    return {(source["name"], table["name"]): table for source in sources for table in source["tables"]}


def _column_names(location: str) -> list[str]:
    """The names a read_json call's `columns = {...}` reads, their quoted types left out."""
    bare = re.sub(r"'[^']*'", "''", location)
    found = re.search(r"columns\s*=\s*\{([^{}]*)\}", bare)
    return re.findall(r"(\w+)\s*:", found.group(1)) if found else []


def test_every_dbt_requirement_is_an_exact_pin():
    lines = _lines(REQUIREMENTS)
    assert [line for line in lines if not PIN.fullmatch(line)] == []
    names = [_name(line.partition("==")[0]) for line in lines]
    assert sorted({name for name in names if names.count(name) > 1}) == []
    assert len(names) == PACKAGES


def test_dbt_core_1_12_and_its_adapter_1_11():
    pins = _pins(REQUIREMENTS)
    assert pins.get("dbt-core") == "1.12.6"
    assert pins.get("dbt-duckdb") == "1.11.0"
    assert pins.get("packaging") == "26.3"   # installed first, for the parser's build (below)
    assert "dbt-oss" not in pins and "dbt" not in pins   # dbt v2's two packages (the design's section 6, "The version")
    # The one pin whose build fetches from GitHub, said so in the file's own comments.
    assert pins.get("dbt-core-experimental-parser") == "2.0.8"
    comments = " ".join(line.lstrip("# ") for line in REQUIREMENTS.read_text().splitlines() if line.startswith("#"))
    for words in ("dbt-core-experimental-parser", "GitHub release v2.0.8", "SHA-256"):
        assert words in comments, words


def test_both_environments_run_the_same_duckdb():
    dbt, dev = _pins(REQUIREMENTS), _pins(DEV_REQUIREMENTS)
    assert dbt.get("duckdb") == dev.get("duckdb") == "1.5.6"
    assert {name: (dbt[name], dev[name]) for name in dbt.keys() & dev.keys() if dbt[name] != dev[name]} == {}


def test_every_install_of_the_dbt_environment_is_the_same():
    expected = [f".venv-dbt/bin/pip install --no-deps packaging=={_pins(REQUIREMENTS)['packaging']}",
                ".venv-dbt/bin/pip install --no-deps --no-build-isolation -r requirements-dbt.txt",
                ".venv-dbt/bin/pip check"]
    for workflow in WORKFLOWS:
        runs = _runs(workflow)
        installs = [run for run in runs if ".venv-dbt/bin/pip" in run]
        assert [command.strip() for run in installs for command in run.split("&&")] == expected, workflow.name
        # The environment is made, then filled, before the tests that run dbt.
        tests = next(at for at, run in enumerate(runs) if run.startswith("pytest"))
        assert runs.index("python -m venv .venv-dbt") < runs.index(installs[0]) < tests, workflow.name


def test_telemetry_is_off():
    assert _project()["flags"] == {"send_anonymous_usage_stats": False}


def test_the_profile_is_one_local_file_and_one_thread():
    assert _load(PROJECT / "profiles.yml") == {"grocery": {"target": "mac", "outputs": {"mac": {
        "type": "duckdb", "path": "{{ env_var('GROCERY_DBT_DB', '../data/dbt.duckdb') }}", "threads": 1}}}}


def test_the_rule_constants_are_the_python_s():
    found = _project()["vars"]
    assert found["deal_min"] == "1.00" and Decimal(found["deal_min"]) == DEAL_MIN
    assert found["min_front_days"] == MIN_FRONT_DAYS == 20
    assert found["recent_days"] == RECENT_DAYS == 30
    assert found["read_days"] == READ_DAYS == 90
    assert found["kinds"] == KINDS


def test_the_store_types_are_the_nine():
    assert _project()["vars"]["store_types"] == {column.key: column.slug for column in COLUMNS}


def test_the_sources_read_their_files_in_place_and_never_a_store_number():
    tables = _tables()
    assert sorted(tables) == sorted(SOURCES)
    for key, (reader, var) in SOURCES.items():
        config = tables[key]["config"]
        location = config["external_location"]
        assert location.startswith(reader) and var in location, key
        if reader == "read_json(":   # its braces would break dbt-duckdb's default formatting (the design's trap 2)
            assert config.get("formatter") == "oldstyle", key
    assert {key: table["config"]["meta"]["label"] for key, table in tables.items()} == LABELS
    found = _project()["vars"]
    assert {var: (PROJECT / found[var]).resolve() for var in PATHS} == {var: ROOT / path for var, path in PATHS.items()}
    # The items reports: the counts and flags of each store type, and the promotions' error; never the list of stores
    # outside the set.
    reports = tables[("tables", "items_reports")]["config"]["external_location"]
    assert _column_names(reports) == ["columns", "promotions_error"]
    assert "outside" not in reports


def test_no_seed_no_package_and_no_python_in_dbt():
    assert "seed-paths" not in _project()
    assert not (PROJECT / "seeds").exists()
    assert not (PROJECT / "packages.yml").exists() and not (PROJECT / "dependencies.yml").exists()
    # A folder named dbt on Python's path joins the installed dbt package (the design's trap 5).
    assert sorted(str(path.relative_to(ROOT)) for path in PROJECT.rglob("*.py")) == []
    assert not (PROJECT / ".user.yml").exists()


def test_no_model_reads_the_clock_or_a_floating_point_type():
    # Every .sql file on disk under the folders the project names, never dbt/target/, where a plain `dbt build` writes
    # compiled SQL with the sources' paths in it.
    project, target = _project(), PROJECT / "target"
    folders = [PROJECT / folder for key in ("model-paths", "macro-paths", "test-paths") for folder in project[key]]
    found = []
    for path in sorted(path for folder in folders for path in folder.rglob("*.sql") if target not in path.parents):
        code = "\n".join(line.partition("--")[0] for line in path.read_text().splitlines())
        name = str(path.relative_to(PROJECT))
        found += [(name, word) for word in CLOCK.findall(code) + FLOATING.findall(code)]
        # A DECIMAL divided by a whole number is a DOUBLE in DuckDB 1.5.6: no division but the whole-number one.
        if "/" in code.replace("//", ""):
            found.append((name, "/"))
    assert found == []


def test_dbt_s_environment_and_output_are_ignored():
    for path in (".venv-dbt", "dbt/target/x", "dbt/logs/x", "data/dbt.duckdb"):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0, path


def test_nothing_asks_dbt_its_version():
    # In dbt-core 1.12.6 the version flag, under any of its three names, asks PyPI for the newest version (the
    # design's section 6). The pattern is built from parts, so this file does not match it.
    asked = re.compile("dbt" + r"\s+" + "(?:-" + "-version|-V|-v)" + r"\b")
    files = [path for folder in ("tests", "scripts", ".github") for path in (ROOT / folder).rglob("*") if path.is_file()]
    files += [ROOT / "README.md", ROOT / "docs" / "operations.md"]
    assert [str(path.relative_to(ROOT)) for path in files
            if asked.search(path.read_bytes().decode("utf-8", errors="replace"))] == []

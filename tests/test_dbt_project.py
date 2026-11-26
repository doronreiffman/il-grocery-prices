"""Pin the dbt layer's frame (docs/dbt-layer.md, section 6): the pins of its own environment, .venv-dbt, and the one
install of it, the project's settings, its rule constants held to the Python's, its seven sources, what git ignores,
and what is never in the project; the two lists held to the Python's and the owner's (section 2); every model and
column described. Nothing here runs dbt: tests/test_dbt_units.py does.

The YAML files are read with yaml.safe_load, so a test reads the values dbt reads, not the text around them.
"""
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import yaml

from basket.chains import EXCLUDED, SLUGS
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
# longer names come first, so a finding names the function exactly. `age` with one argument is the time from it to
# today; with two it reads no clock, so the pattern takes a call with no comma outside its own parentheses (two
# levels of them inside).
CLOCK = re.compile(r"current_localtimestamp|current_localtime|get_current_timestamp|get_current_time|transaction_timestamp"
                   r"|current_date|current_timestamp|current_time|localtimestamp|\blocaltime\b|\bnow\s*\(|\btoday\s*\("
                   r"|\bage\s*\((?:[^(),]|\((?:[^()]|\([^()]*\))*\))*\)"
                   r"|run_started_at|modules\.datetime", re.IGNORECASE)
# The floating-point types, and two aggregates no price may go through in DuckDB 1.5.6: `avg` gives a DOUBLE, over
# DECIMALs too; `median` gives a DOUBLE over whole numbers and over DECIMALs keeps their places, so the mean of two
# middle prices loses its last digit (7.60 for 7.60 and 7.61, where rule B5's is 7.605). The median is the macro
# median_price's.
FLOATING = re.compile(r"\b(?:double|float|float4|float8|real)\b|\b(?:avg|median)\s*\(", re.IGNORECASE)
# DuckDB 1.5.6's regular-expression functions, each called with its pattern second. A pattern that is a string
# literal is compiled once; one built from a row's values ('...' || strftime(day, ...) || '...') is compiled again for
# every row. And DuckDB runs a filter that reads only a group-by's keys below the group-by, so a check written to match
# once a file still matches once a row: on the Mac's tables of 2026-11-26 such a pattern took about 57 microseconds a
# row, and the file-name check ran past 36 minutes over 68,541,233 price rows without finishing.
REGEXP = re.compile(r"\bregexp_[a-z_]+\s*\(", re.IGNORECASE)
LITERAL = re.compile(r"'(?:[^']|'')*'")

# left_out_stores.sql holds one row a line: ('<chain>', 'sub_chain' or 'store', '<key>').
LEFT_OUT = PROJECT / "models" / "lists" / "left_out_stores.sql"
LEFT_OUT_ROW = re.compile(r"\s*\('([a-z]+)', '(sub_chain|store)', '([0-9]+)'\),?")
# The published days today's tables no longer give, as the owner listed them on 2026-11-25 (the design's answer 2).
OWNER_S_FOUR = [("basket", "shufersal", "2026-11-09"), ("store_page", "ramilevy", "2026-11-21"),
                ("store_page", "ramilevy", "2026-11-22"), ("store_page", "yochananof", "2026-11-22")]
WE = re.compile(r"\bwe\b", re.IGNORECASE)


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


def test_the_left_out_stores_are_b2_s():
    # Every line that opens a row is one of the pattern's, so no row can hide from this test in another spelling.
    lines = [line for line in LEFT_OUT.read_text().splitlines() if line.lstrip().startswith("(")]
    rows = [LEFT_OUT_ROW.fullmatch(line) for line in lines]
    assert [line for line, row in zip(lines, rows) if row is None] == []
    expected = ([(slug, "sub_chain", key) for slug, left_out in EXCLUDED.items() for key in left_out.sub_chains]
                + [(slug, "store", key) for slug, left_out in EXCLUDED.items() for key in left_out.stores])
    assert sorted(row.groups() for row in rows) == sorted(expected)


def test_the_known_differences_are_the_owner_s_four():
    found = _project()["vars"]
    listed = found["known_differences"]
    # The days as text: a day YAML read as a date would not be the one dbt writes into the SQL.
    assert sorted((entry["kind"], entry["key"], entry["day"]) for entry in listed) == OWNER_S_FOUR
    for entry in listed:
        assert sorted(entry) == ["day", "key", "kind", "reason"], entry
        assert entry["key"] in {"store_page": found["store_types"], "basket": SLUGS}[entry["kind"]], entry
        assert isinstance(entry["reason"], str) and len(entry["reason"]) >= 30, entry


def _descriptions(node) -> list[str]:
    """Every description in a loaded YAML file, at any depth."""
    if isinstance(node, dict):
        return [text for key, value in node.items()
                for text in ([value] if key == "description" and isinstance(value, str) else _descriptions(value))]
    if isinstance(node, list):
        return [text for value in node for text in _descriptions(value)]
    return []


def test_every_model_and_column_is_described():
    found = []
    for path in sorted((PROJECT / "models").rglob("*.sql")):
        name, properties = str(path.relative_to(PROJECT)), path.with_suffix(".yml")
        loaded = _load(properties) if properties.is_file() else {}
        model = {model["name"]: model for model in loaded.get("models", [])}.get(path.stem)
        if model is None or not model.get("description"):
            found.append((name, "no description"))
            continue
        found += [(name, column.get("name")) for column in model.get("columns", []) if not column.get("description")]
        found += [(name, text) for text in _descriptions(loaded) if WE.search(text)]
    assert found == []


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


def _arguments(code: str, opening: int) -> list[str]:
    """The arguments of the call whose opening parenthesis is at `opening`, split at the commas outside any other
    bracket, any quoted text and any Jinja braces. A doubled quote closes the text and opens it again."""
    arguments, depth, quoted, start = [], 0, False, opening + 1
    for at in range(opening, len(code)):
        char = code[at]
        if quoted:
            quoted = char != "'"
        elif char == "'":
            quoted = True
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return [*arguments, code[start:at]]
        elif char == "," and depth == 1:
            arguments.append(code[start:at])
            start = at + 1
    raise AssertionError(f"no closing parenthesis after {code[opening:opening + 40]!r}")


def test_every_regular_expression_s_pattern_is_a_literal():
    # Every .sql file on disk under the folders the project names, as in the clock check above.
    project, target = _project(), PROJECT / "target"
    folders = [PROJECT / folder for key in ("model-paths", "macro-paths", "test-paths") for folder in project[key]]
    with_calls, found = set(), []
    for path in sorted(path for folder in folders for path in folder.rglob("*.sql") if target not in path.parents):
        code = "\n".join(line.partition("--")[0] for line in path.read_text().splitlines())
        for call in REGEXP.finditer(code):
            with_calls.add(path.relative_to(PROJECT).as_posix())
            pattern = _arguments(code, call.end() - 1)[1].strip()
            if not LITERAL.fullmatch(pattern):
                found.append((str(path.relative_to(PROJECT)), pattern))
    # The file-name check, the one this test was written for, is among the files with a call, so the test cannot pass
    # on is_gs1.sql's call alone while that check's pattern goes unread.
    assert "tests/prices/prices_each_row_from_a_pricefull_file_of_its_day.sql" in with_calls
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


# The runbook's install of the dbt environment (Task 11): docs/operations.md makes and fills .venv-dbt as CI does, so
# the line a reader copies is the one CI proves. Every line of a fenced block there that runs .venv-dbt's pip is that
# install, whole.
OPERATIONS = ROOT / "docs" / "operations.md"


def _fenced(path: Path) -> list[str]:
    """The lines inside the file's fenced code blocks, stripped."""
    lines, inside = [], False
    for line in path.read_text().splitlines():
        if line.strip().startswith("```"):
            inside = not inside
        elif inside:
            lines.append(line.strip())
    return lines


def test_the_runbook_installs_the_dbt_environment_as_ci_does():
    ci = [command.strip() for run in _runs(WORKFLOWS[0]) if ".venv-dbt/bin/pip" in run for command in run.split("&&")]
    installs = [line for line in _fenced(OPERATIONS) if ".venv-dbt/bin/pip" in line]
    assert installs != []
    for line in installs:
        assert [command.strip() for command in line.split("&&")] == ["python3.13 -m venv .venv-dbt", *ci]


# The slow test (Task 8): one data test alone is tagged slow, the prices' one row per chain, day, store and code over
# every day's rows (docs/dbt-layer.md, section 3), so the runbook's `dbt test --exclude tag:slow` (docs/operations.md)
# leaves out that one and no other.
SLOW = [("models/sources.yml", "prices_one_row_per_chain_day_store_and_code")]


def _tagged_slow(node) -> list[str | None]:
    """The names of the entries a loaded YAML file tags slow, at any depth: by the entry's `tags` or `+tags`, or its
    config's, a list or one tag."""
    if isinstance(node, list):
        return [name for value in node for name in _tagged_slow(value)]
    if not isinstance(node, dict):
        return []
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    found = [node.get("name") for tags in (node.get("tags"), node.get("+tags"), config.get("tags"), config.get("+tags"))
             if tags == "slow" or (isinstance(tags, list) and "slow" in tags)]
    return found + [name for key, value in node.items() if key != "config" for name in _tagged_slow(value)]


def test_the_one_slow_test_is_the_prices_uniqueness():
    # Every YAML and SQL file under dbt/ but dbt/target/ and dbt/logs/, where dbt writes; a SQL file tags a test
    # through its config call, inside {{ }}.
    skipped = (PROJECT / "target", PROJECT / "logs")
    files = sorted(path for path in PROJECT.rglob("*") if path.suffix in (".yml", ".sql")
                   and not any(folder in path.parents for folder in skipped))
    found = [(str(path.relative_to(PROJECT)), name) for path in files if path.suffix == ".yml"
             for name in _tagged_slow(_load(path))]
    found += [(str(path.relative_to(PROJECT)), path.stem) for path in files if path.suffix == ".sql"
              and re.search(r"\{\{[^}]*\bslow\b[^}]*\}\}", path.read_text())]
    assert found == SLOW

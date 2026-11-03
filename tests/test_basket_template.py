"""Pin what the basket function's template and its DuckDB layer say (Task 8 of the step-two plan extends this
file with the template's own pins).

`sam build` builds the layer from `layer/Makefile`; nothing here runs a build, so the build command's flags are
asserted as text: a wheel for the wrong platform would install fine and fail only when Lambda imports it.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
LAYER = ROOT / "layer"
DUCKDB_HASH = "364992ba1089a2b327391cfcb68fd0bd0ce9090cf293baef861a0ba6847abfee"


# --- the layer ---


def test_layer_pins_duckdb_by_version_and_hash():
    lines = (LAYER / "requirements.txt").read_text().splitlines()
    assert lines == [f"duckdb==1.5.6 --hash=sha256:{DUCKDB_HASH}"]
    dev = [line for line in (ROOT / "requirements-dev.txt").read_text().splitlines() if line.startswith("duckdb==")]
    assert dev == [lines[0].split()[0]], "the layer and the tests must run the same DuckDB"


def test_layer_makefile_builds_for_lambdas_arm64_linux():
    lines = (LAYER / "Makefile").read_text().splitlines()
    assert lines[0] == "build-DuckDbLayer:"
    [command] = lines[1:]
    assert command.startswith("\t"), "a recipe line starts with a tab"
    for flag in ("--platform manylinux_2_28_aarch64", "--python-version 3.13", "--only-binary=:all:",
                 "--require-hashes", "--implementation cp", '"$(ARTIFACTS_DIR)/python"'):
        assert flag in command, flag

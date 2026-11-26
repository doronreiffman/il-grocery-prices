"""The README's lineage map (docs/dbt-layer.md, section 7) is the one dbt's manifest gives. scripts/dbt_lineage.py draws
each source as a table under its label, then each edge between the sources and the models, one a line, parent first,
sorted; a data test, a unit test and a model that reads nothing and that no model reads are not drawn. Its check exits
1 when a README's block is not the manifest's. The last test parses the project with dbt and holds README.md's block
equal to what the parse gives.
"""
import importlib.util
import json
from pathlib import Path

from dbt_run import run_dbt

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def _script():
    spec = importlib.util.spec_from_file_location("dbt_lineage", ROOT / "scripts" / "dbt_lineage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source(name: str, label: str) -> tuple[str, dict]:
    return f"source.shop.files.{name}", {"resource_type": "source", "name": name, "source_name": "files",
                                         "meta": {"label": label}}


def _node(kind: str, name: str, *parents: str) -> tuple[str, dict]:
    return f"{kind}.shop.{name}", {"resource_type": kind, "name": name,
                                   "depends_on": {"macros": [], "nodes": list(parents)}}


def _manifest() -> dict:
    """Two sources and three models, the sources, the nodes and a node's parents each given out of order."""
    return {
        "sources": dict([_source("stock", "the stock files"), _source("orders", "orders")]),
        "nodes": dict([
            _node("model", "summary", "model.shop.stg_stock", "model.shop.stg_orders"),
            _node("model", "stg_stock", "source.shop.files.stock"),
            _node("model", "stg_orders", "source.shop.files.orders"),
        ]),
        "unit_tests": {},
    }


# What _manifest() gives: the sources first, each a table under its label, then the edges, both sorted.
DRAWN = """```mermaid
graph LR
  orders[(orders)]
  stock[(the stock files)]
  orders --> stg_orders
  stg_orders --> summary
  stg_stock --> summary
  stock --> stg_stock
```"""


def _readme(block: str) -> str:
    script = _script()
    return f"# A README\n\n- **A lineage map.**\n\n{script.START}\n{block}\n{script.END}\n\nThe next paragraph.\n"


def test_mermaid_draws_sources_as_tables_and_one_edge_a_line():
    assert _script().mermaid(_manifest()) == DRAWN


def test_tests_unit_tests_and_unread_lists_are_not_drawn():
    manifest = _manifest()
    manifest["nodes"].update([
        _node("model", "notes"),   # reads nothing, and no model reads it: only a test does
        _node("test", "summary_matches_notes", "model.shop.summary", "model.shop.notes", "source.shop.files.stock"),
    ])
    manifest["unit_tests"].update([_node("unit_test", "an_order_is_counted", "model.shop.stg_orders")])
    assert _script().mermaid(manifest) == DRAWN


def test_the_check_exits_1_on_a_stale_readme(tmp_path):
    script = _script()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest()))
    stale, fresh = tmp_path / "stale.md", tmp_path / "fresh.md"
    stale.write_text(_readme(DRAWN.replace("  stock --> stg_stock\n", "")))
    fresh.write_text(_readme(DRAWN))
    assert script.main(["--check", str(stale), str(manifest)]) == 1
    assert script.main(["--check", str(fresh), str(manifest)]) == 0


def test_the_script_prints_the_block_for_the_readme(tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest()))
    assert _script().main([str(manifest)]) == 0
    assert capsys.readouterr().out == DRAWN + "\n"


def test_the_readme_diagram_is_the_project_s(tmp_path):
    script = _script()
    parsed = run_dbt(["parse"], tmp_path / "work")
    assert parsed.code == 0, parsed.output
    assert script.readme_block(README.read_text(encoding="utf-8")) == script.mermaid(parsed.manifest)

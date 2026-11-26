#!/usr/bin/env python3
"""The README's lineage map of the dbt layer (docs/dbt-layer.md, section 7), drawn from dbt's manifest.

    python scripts/dbt_lineage.py <manifest.json>                    # prints the block
    python scripts/dbt_lineage.py --check README.md <manifest.json>  # exit 1 when README's block is not that one

The block is a Mermaid diagram, which GitHub draws: each source as a table under the label its `meta` gives in
dbt/models/sources.yml, then each edge between the sources and the models, one a line, parent first, both sorted.
Only edges are drawn, so a model that reads nothing and that no model reads (known_differences, which only data tests
read) is left out, and so are the data tests and the unit tests. README.md holds the block between START and END;
tests/test_dbt_lineage.py parses the project and holds the two equal. After a change to the models, from dbt/:
`../.venv-dbt/bin/dbt parse`, then from the repository's root: `.venv/bin/python scripts/dbt_lineage.py
dbt/target/manifest.json`, and the block printed goes between the two markers.

Run by the project's .venv: it reads JSON only, and imports nothing of dbt's.
"""
import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

START = "<!-- dbt lineage: made by scripts/dbt_lineage.py from dbt's manifest; tests/test_dbt_lineage.py holds it equal -->"
END = "<!-- end of dbt lineage -->"


def mermaid(manifest: Mapping) -> str:
    """The diagram of the manifest's sources and models, as a fenced Mermaid block."""
    sources = {unique_id: source["name"] for unique_id, source in manifest["sources"].items()}
    models = {unique_id: node for unique_id, node in manifest["nodes"].items() if node["resource_type"] == "model"}
    names = sources | {unique_id: node["name"] for unique_id, node in models.items()}
    tables = [f"  {source['name']}[({source['meta']['label']})]" for source in manifest["sources"].values()]
    edges = [(names[parent], node["name"]) for node in models.values() for parent in node["depends_on"]["nodes"]
             if parent in names]
    lines = ["```mermaid", "graph LR", *sorted(tables), *[f"  {parent} --> {child}" for parent, child in sorted(edges)],
             "```"]
    return "\n".join(lines)


def readme_block(readme: str) -> str:
    """The text between START and END, less the line end after START and the one before END."""
    start = readme.index(START) + len(START)
    return readme[start:readme.index(END, start)].removeprefix("\n").removesuffix("\n")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="dbt_lineage.py", description=__doc__.splitlines()[0])
    parser.add_argument("--check", metavar="README", help="exit 1 when this file's block is not the manifest's")
    parser.add_argument("manifest", type=Path, help="dbt's target/manifest.json, as dbt parse writes it")
    args = parser.parse_args(argv)
    block = mermaid(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.check is None:
        print(block)
        return 0
    if readme_block(Path(args.check).read_text(encoding="utf-8")) != block:
        print(f"{args.check}: the dbt lineage between its markers is not the one {args.manifest} gives; print it "
              f"with: python scripts/dbt_lineage.py {args.manifest}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

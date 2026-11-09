"""The site run's timing script (`scripts/time_site_run.py`, the plan's Task 25a): `--make` replaces only tables it made
itself, which its marker `made.json` beside them names; a folder holding tables without the marker is refused and
left as it is, so the script pointed at a real data folder deletes nothing."""
import importlib.util
from pathlib import Path

import pytest

from shopper.items import items_path

ROOT = Path(__file__).resolve().parent.parent


def _script():
    spec = importlib.util.spec_from_file_location("time_site_run", ROOT / "scripts" / "time_site_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(folder: Path) -> dict[Path, bytes]:
    return {path.relative_to(folder): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def test_make_refuses_tables_it_did_not_make_and_replaces_its_own(tmp_path):
    script = _script()
    theirs = tmp_path / "theirs"
    for name in ("tables/items/chain=shufersal/date=2026-11-20/items.parquet", "tables/scored/summary.json"):
        (theirs / name).parent.mkdir(parents=True, exist_ok=True)
        (theirs / name).write_bytes(b"not the script's")
    before = _files(theirs)
    with pytest.raises(SystemExit, match="made.json"):
        script.make(theirs, 0.001, 15)
    assert _files(theirs) == before                                  # nothing deleted, nothing written

    mine = tmp_path / "mine"                                         # absent: made
    script.make(mine, 0.001, 15)
    stray = mine / "tables" / "stray.txt"
    stray.write_text("left from an earlier run")
    script.make(mine, 0.001, 15)                                     # the script's own: replaced
    assert not stray.exists() and (mine / script.MADE).is_file()
    assert items_path(mine / "tables", "shufersal", script.DAY).is_file()

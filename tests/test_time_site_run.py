"""The site run's timing script (`scripts/time_site_run.py`, the plan's Task 25a) deletes and writes only inside a work
folder it made itself: `make` refuses, touching nothing, a `--work` that is there, not empty and without the script's
marker `made.json`, such as the repository's root with its `site/` and `data/tables/`; every delete needs the marker and
refuses a symlink from the work folder down to what it deletes, so a link planted there cannot lead it to real tables;
a file it rewrites is deleted first, so never written through a link, and a linked marker is no marker. A folder the
script made is replaced."""
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
    """Every file and link under `folder`, by path: a file's bytes, a link's target."""
    return {path.relative_to(folder): str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
            for path in folder.rglob("*") if path.is_symlink() or path.is_file()}


def _put(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(f"not the script's: {name}".encode())


def test_the_repositorys_layout_is_refused_and_left_as_it_was(tmp_path):
    """The repository's root as `--work`: the published copies under `site/`, the real tables under `data/tables/`,
    no `tables/` and no marker. With `--make` and without, the script refuses, every file byte for byte, none added."""
    script = _script()
    _put(tmp_path, "site/days/2026-11-02.json", "site/site-days/2026-11-02.json", "site/forecasts/ledger.csv",
         "site/index.html", "data/tables/items/chain=shufersal/date=2026-11-02/items.parquet",
         "data/tables/scored/date=2026-10-19/summary.json")
    before = _files(tmp_path)
    with pytest.raises(SystemExit, match="made.json"):
        script.main(["--work", str(tmp_path), "--make", "--scale", "0.001", "--days", "15"])
    with pytest.raises(SystemExit, match="made.json"):
        script.main(["--work", str(tmp_path)])
    with pytest.raises(SystemExit, match="made.json"):
        script._remove(tmp_path, tmp_path / "site")
    assert _files(tmp_path) == before


def test_a_symlink_in_the_work_folder_is_refused_and_its_target_left(tmp_path):
    """A work folder the script made, its `tables/` swapped for a link to real tables: the run and a new `--make` both
    refuse; the link and everything it leads to stay as they were. A link given as `--work` is refused too, even to
    an empty folder."""
    script = _script()
    mine, real = tmp_path / "mine", tmp_path / "real"
    script.make(mine, 0.001, 15)
    _put(real, "covered/date=2026-11-19/covered.parquet", "scored/date=2026-11-06/summary.json", "items/keep.parquet")
    (mine / "tables").rename(tmp_path / "made-tables")
    (mine / "tables").symlink_to(real, target_is_directory=True)
    before, links = _files(real), _files(mine)
    with pytest.raises(SystemExit, match="symlink"):
        script.main(["--work", str(mine)])
    with pytest.raises(SystemExit, match="symlink"):
        script.make(mine, 0.001, 15)
    assert _files(real) == before and _files(mine) == links
    empty = tmp_path / "empty"                                       # a link as --work, to an empty folder
    empty.mkdir()
    (tmp_path / "link").symlink_to(empty, target_is_directory=True)
    with pytest.raises(SystemExit, match="symlink"):
        script.make(tmp_path / "link", 0.001, 15)
    assert not any(empty.iterdir())


def test_a_linked_file_in_the_work_folder_is_never_written_through(tmp_path):
    """A folder the script made, its frozen file or its marker swapped for a link to a file of the owner's: `--make`
    refuses rather than write through the link, and a linked marker is no marker, so the run refuses too."""
    script = _script()
    real = tmp_path / "ledger.csv"
    real.write_bytes(b"the owner's ledger")
    frozen, marker = tmp_path / "frozen", tmp_path / "marker"
    for mine, name in ((frozen, "frozen.csv.gz"), (marker, script.MADE)):
        script.make(mine, 0.001, 15)
        (mine / name).unlink()
        (mine / name).symlink_to(real)
    with pytest.raises(SystemExit, match="symlink"):
        script.make(frozen, 0.001, 15)
    with pytest.raises(SystemExit, match="made.json"):
        script.make(marker, 0.001, 15)
    with pytest.raises(SystemExit, match="made.json"):
        script.main(["--work", str(marker)])
    assert real.read_bytes() == b"the owner's ledger"


def test_a_folder_the_script_made_is_replaced(tmp_path):
    """An absent folder and an empty one are made; a folder the script made is made again, a stray file in it gone."""
    script = _script()
    empty = tmp_path / "empty"
    empty.mkdir()
    script.make(empty, 0.001, 15)
    assert (empty / script.MADE).is_file()
    mine = tmp_path / "mine"
    script.make(mine, 0.001, 15)
    stray = mine / "tables" / "stray.txt"
    stray.write_text("left from an earlier run")
    script.make(mine, 0.001, 15)
    assert not stray.exists() and (mine / script.MADE).is_file()
    assert items_path(mine / "tables", "shufersal", script.DAY).is_file()

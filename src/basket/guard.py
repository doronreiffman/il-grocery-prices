"""The publish guard (B12): an upload never replaces a published day file with one that is not a revision of it.

    PYTHONPATH=src .venv/bin/python -m basket.guard site/days <the published days, copied from the bucket>

A build compares its numbers with `site/days/<day>.json` on disk; a build into a `site/` that `scripts/sync.sh`
did not fill sees no published day, writes the day as new, and the upload would replace the published file,
its revision reason and earlier figures included. So `scripts/publish.sh` copies the bucket's `days/` into a
temporary folder and runs this before any upload.

For every `*.json` in the local folder that the published folder also holds: the same bytes pass; different
bytes pass only when the local file is a revision of the published one, as `basket.build` writes it:
`revised` set (an object) and a `revisions` list longer than the published file's. Anything else is a problem
naming the day. A local day the bucket lacks is new and passes; a published day the local folder lacks passes
too, since the day-file upload never deletes; a published folder that does not exist holds no day (the
bucket's `days/` is empty before the first upload). A file that does not read as a JSON object is a problem
naming the file. Exit 0 with no problem; 1 with problems, one a line on stderr; 2 when the local folder is
absent or the arguments are not two folders.
"""
import json
import sys
from pathlib import Path


def guard_days(local_days: Path, published_days: Path) -> list[str]:
    """The problems, one line each, with uploading `local_days` over `published_days`; [] when none."""
    problems = []
    for local in sorted(Path(local_days).glob("*.json")):
        published = Path(published_days) / local.name
        if not published.is_file() or local.read_bytes() == published.read_bytes():
            continue
        new, old = _read(local), _read(published)
        unreadable = [str(path) for path, day in ((local, new), (published, old)) if day is None]
        if unreadable:
            problems += [f"{path}: not a day file (a JSON object)" for path in unreadable]
        elif not _revises(new, old):
            problems.append(f"days/{local.name} differs from the published day and is not a revision of it: "
                            "run scripts/sync.sh first")
    return problems


def _read(path: Path) -> dict | None:
    """The day file as a dict; None when it does not read as a JSON object."""
    try:
        day = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return day if isinstance(day, dict) else None


def _revises(new: dict, old: dict) -> bool:
    """Whether `new` is a revision of `old`: `revised` an object, and more `revisions` than `old` has."""
    revisions, earlier = new.get("revisions"), old.get("revisions")
    return (isinstance(new.get("revised"), dict) and isinstance(revisions, list) and isinstance(earlier, list)
            and len(revisions) > len(earlier))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m basket.guard <local days folder> <published days folder>", file=sys.stderr)
        return 2
    local, published = Path(argv[0]), Path(argv[1])
    if not local.is_dir():
        print(f"no folder at {local}: no day file to compare", file=sys.stderr)
        return 2
    problems = guard_days(local, published)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

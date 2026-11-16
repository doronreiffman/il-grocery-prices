"""The fonts' maker, `scripts/subset_fonts.py` (docs/site-look.md, "The shared stylesheet and the font files"; the
site-look plan's Task 1): its pinned sources, its subsets against the stylesheet's `unicode-range`s, its refusal of a
source that is not the pinned one and of tools that are not the pinned versions.

The script is imported by its path and never runs here: fontTools is not in the project's requirements, and the script
imports it only inside the functions that make the fonts."""
import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "src" / "shopper" / "static" / "look.css"
README = ROOT / "src" / "shopper" / "static" / "fonts" / "README.md"

# The design's sources (site-look.md, "Sources, pinned, and licences"): (family, version, commit, file, SHA-256).
SOURCES = {
    ("archivo", "2.001", "6c70c829f09ea345d3590406693220ea35c6553f", "Archivo[wdth,wght].ttf",
     "0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053"),
    ("archivo", "2.001", "6c70c829f09ea345d3590406693220ea35c6553f", "OFL.txt",
     "108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b"),
    ("heebo", "3.100", "804ab16a8ff8ac0072e7c5ecc34e381b4a710177", "Heebo[wght].ttf",
     "18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30"),
    ("heebo", "3.100", "804ab16a8ff8ac0072e7c5ecc34e381b4a710177", "OFL.txt",
     "866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3"),
}
README_SOURCE = re.compile(r"^\| (\w+) \| ([\d.]+) \| `([0-9a-f]{40})` \| `ofl/(\w+)/([^`]+)` \| `([0-9a-f]{64})` \|$",
                           re.M)


def _script():
    spec = importlib.util.spec_from_file_location("subset_fonts", ROOT / "scripts" / "subset_fonts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _points(ranges: str) -> set[int]:
    """The code points of a `unicode-range` list ("U+0020-007E,U+00A0,...")."""
    points = set()
    for part in ranges.split(","):
        first, _, last = part.strip().removeprefix("U+").partition("-")
        points |= set(range(int(first, 16), int(last or first, 16) + 1))
    return points


def _faces() -> dict[str, list[set[int]]]:
    """The code points of each `@font-face` rule of the stylesheet, by the font file it names."""
    faces = {}
    for block in re.findall(r"@font-face\{([^}]*)\}", SHEET.read_text(encoding="utf-8")):
        font = re.search(r"url\(([^)]*)\)", block)[1]
        faces.setdefault(font, []).append(_points(re.search(r"unicode-range:([^;}]*)", block)[1]))
    return faces


def test_the_sources_are_pinned_at_the_designs_commits():
    script = _script()
    pinned = {(family, source.version, source.commit, file, sha256)
              for family, source in script.PINNED.items()
              for file, sha256 in ((source.font, source.font_sha256), ("OFL.txt", source.licence_sha256))}
    assert pinned == SOURCES
    readme = {(folder, version, commit, file, sha256)
              for family, version, commit, folder, file, sha256 in README_SOURCE.findall(README.read_text(encoding="utf-8"))
              if family.lower() == folder}
    assert readme == SOURCES


def test_each_subset_keeps_what_the_stylesheet_sends_it():
    """Each subset holds what the stylesheet's `unicode-range` sends to it: the Latin one both Archivo rules' ranges,
    the Hebrew one both Heebo rules' and the space."""
    script = _script()
    faces = _faces()
    assert len(faces["archivo-text.woff2"]) == len(faces["archivo-narrow.woff2"]) == 1
    assert len(faces["heebo-hebrew.woff2"]) == 2
    latin = set(script.codepoints(script.LATIN))
    hebrew = set(script.codepoints(script.HEBREW))
    assert faces["archivo-text.woff2"] == faces["archivo-narrow.woff2"] == [latin]
    assert 0x20 in hebrew and faces["heebo-hebrew.woff2"] == [hebrew - {0x20}] * 2
    assert {name: (family, ranges) for name, (family, ranges, _) in script.FILES.items()} == {
        "archivo-text.woff2": ("archivo", script.LATIN), "archivo-narrow.woff2": ("archivo", script.LATIN),
        "heebo-hebrew.woff2": ("heebo", script.HEBREW)}


def test_a_source_that_is_not_the_pinned_one_is_refused():
    script = _script()
    with pytest.raises(ValueError, match=re.escape("Heebo[wght].ttf")):
        script.verified(b"x", "18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30", "Heebo[wght].ttf")
    assert script.verified(b"x", hashlib.sha256(b"x").hexdigest(), "Heebo[wght].ttf") == b"x"


def test_the_tools_must_be_the_pinned_versions():
    script = _script()
    with pytest.raises(ValueError):
        script.check_tools("4.58.0", "1.2.0")
    with pytest.raises(ValueError):
        script.check_tools("4.59.0", "1.1.0")
    assert script.check_tools("4.59.0", "1.2.0") is None

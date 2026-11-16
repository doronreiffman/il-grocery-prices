"""Make the shopper site's three font files and copy the two families' licences beside them (docs/site-look.md, "The
shared stylesheet and the font files"; src/shopper/static/fonts/README.md).

From two variable fonts of the google/fonts repository, each read at a fixed commit and refused unless its SHA-256 is
the pinned one (`PINNED`), it makes (`FILES`):

- `archivo-text.woff2`: Archivo at width 100, weights 400 to 700, the Latin subset (`LATIN`);
- `archivo-narrow.woff2`: Archivo at width 70, weight 800, the Latin subset;
- `heebo-hebrew.woff2`: Heebo, weights 400 to 800, the Hebrew block, the shekel sign and the space (`HEBREW`);

and copies each family's `OFL.txt` as `OFL-<family>.txt`. Each font is instanced at its axes with fontTools'
varLib.instancer, subset with fontTools' subsetter (the layout features in `FEATURES`; the copyright and licence names
kept, `NAME_IDS`) and saved as WOFF2, which brotli compresses. Nothing in it reads the clock (the fonts' own `head`
times are kept), so the same sources give the same bytes. It prints each file's bytes and SHA-256.

The tools are fonttools 4.59.0 and brotli 1.2.0 (`TOOLS`), refused at any other version. They live only in a throwaway
virtual environment outside the repository: never in the project's requirements, and CI does not run this script. The
site's build reads the committed files in src/shopper/static/fonts/, whose README gives the commands. Run with that
environment's Python:

    python -I scripts/subset_fonts.py --sources <folder> --out <folder>

`--sources` keeps the files fetched: one already there with its pinned SHA-256 is not fetched again. fontTools is
imported only inside `make`, so the tests import this script without it.
"""
import argparse
import hashlib
import io
import sys
from importlib.metadata import version
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote
from urllib.request import Request, urlopen

TOOLS = ("4.59.0", "1.2.0")     # fonttools, brotli
URL = "https://raw.githubusercontent.com/google/fonts/{commit}/ofl/{family}/{file}"
USER_AGENT = "subset_fonts.py"  # the script alone: no contact address leaves the machine
TIMEOUT = 60                    # seconds a fetch may take


class Source(NamedTuple):
    version: str
    commit: str             # of google/fonts
    font: str               # the variable font, in ofl/<family>/ at that commit
    font_sha256: str
    licence_sha256: str     # of ofl/<family>/OFL.txt at that commit


PINNED = {
    "archivo": Source("2.001", "6c70c829f09ea345d3590406693220ea35c6553f", "Archivo[wdth,wght].ttf",
                      "0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053",
                      "108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b"),
    "heebo": Source("3.100", "804ab16a8ff8ac0072e7c5ecc34e381b4a710177", "Heebo[wght].ttf",
                    "18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30",
                    "866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3"),
}
# What each subset keeps: the stylesheet's unicode-range for each font (the Hebrew one less the space, which Archivo
# draws).
LATIN = "U+0020-007E,U+00A0-00FF,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2022,U+2026,U+2190,U+2192,U+2212"
HEBREW = "U+0020,U+0590-05FF,U+20AA"
# Each file: its family, its code points and the axes it is instanced at (a number pins an axis, a pair limits it).
FILES = {
    "archivo-text.woff2": ("archivo", LATIN, {"wdth": 100, "wght": (400, 700)}),
    "archivo-narrow.woff2": ("archivo", LATIN, {"wdth": 70, "wght": 800}),
    "heebo-hebrew.woff2": ("heebo", HEBREW, {"wght": (400, 800)}),
}
FEATURES = ["kern", "liga", "tnum", "lnum", "pnum", "case", "ccmp", "locl", "mark", "mkmk"]
NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 13, 14]    # 0 the copyright, 13 and 14 the licence and its URL


def check_tools(fonttools: str, brotli: str) -> None:
    """Refuse tools at any version but the pinned ones, which made the committed files."""
    if (fonttools, brotli) != TOOLS:
        raise ValueError(f"needs fonttools {TOOLS[0]} and brotli {TOOLS[1]}, not {fonttools} and {brotli}")


def verified(data: bytes, sha256: str, name: str) -> bytes:
    """`data`, when its SHA-256 is the pinned `sha256`; ValueError naming the file when not."""
    found = hashlib.sha256(data).hexdigest()
    if found != sha256:
        raise ValueError(f"{name}: SHA-256 {found}, not the pinned {sha256}")
    return data


def codepoints(ranges: str) -> list[int]:
    """The code points of a list of ranges ("U+0020-007E,U+00A0,..."), in order."""
    points = set()
    for part in ranges.split(","):
        first, _, last = part.removeprefix("U+").partition("-")
        points.update(range(int(first, 16), int(last or first, 16) + 1))
    return sorted(points)


def fetched(family: str, file: str, sha256: str, sources: Path) -> bytes:
    """The bytes of ofl/<family>/<file> at the family's pinned commit: from `sources` when it holds them with the pinned
    SHA-256, else fetched, checked and kept there."""
    path = sources / family / file
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
        return path.read_bytes()
    url = URL.format(commit=PINNED[family].commit, family=family, file=quote(file))
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT) as response:
        data = verified(response.read(), sha256, file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def make(source: bytes, unicodes: list[int], axes: dict) -> bytes:
    """One WOFF2 file: the variable font `source` instanced at `axes`, then subset to `unicodes`."""
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    instance = instantiateVariableFont(TTFont(io.BytesIO(source), recalcTimestamp=False), axes)
    saved = io.BytesIO()        # the subsetter trips on a freshly instanced font's gvar; saved and read back, it does not
    instance.save(saved)
    font = TTFont(io.BytesIO(saved.getvalue()), recalcTimestamp=False)
    options = Options()
    options.layout_features = FEATURES
    options.flavor = "woff2"
    options.name_IDs = NAME_IDS
    options.notdef_outline = True
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make the shopper site's fonts from their pinned sources.")
    parser.add_argument("--sources", type=Path, required=True, help="a folder for the fetched sources")
    parser.add_argument("--out", type=Path, required=True, help="the folder the five files are written to")
    args = parser.parse_args(argv)
    check_tools(version("fonttools"), version("brotli"))
    fonts = {family: fetched(family, source.font, source.font_sha256, args.sources)
             for family, source in PINNED.items()}
    made = {name: make(fonts[family], codepoints(ranges), axes) for name, (family, ranges, axes) in FILES.items()}
    for family, source in PINNED.items():
        made[f"OFL-{family}.txt"] = fetched(family, "OFL.txt", source.licence_sha256, args.sources)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in made.items():
        (args.out / name).write_bytes(data)
        print(f"{name}  {len(data):,} bytes  SHA-256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The site's shared files (`shopper.assets`; docs/site-look.md, "The shared stylesheet and the font files", "What the
tests should pin" 9 and 10; the site-look plan's Task 1): the three fonts under hashed names, the two licences, and the
stylesheet naming the fonts by their hashed names, under a hashed name of its own."""
import hashlib
import re
import shutil

import pytest

import shopper.assets as assets
from shopper.assets import FOLDER, FONTS, LICENCES, SHEET, STATIC, STYLESHEET, asset_files, hashed

FONT_DIR = STATIC / "fonts"
# The design's five files: bytes and SHA-256 (site-look.md, "The shared stylesheet and the font files").
FILES = {
    "archivo-text.woff2": (25660, "97c5421649b850b9161c7e708d16a93edf171ce7411eac77718a522cf413505c"),
    "archivo-narrow.woff2": (11420, "d5c5f1b561f4f5d6f922928132dfde05cdce396c1a6b64cceb14da856f10aad3"),
    "heebo-hebrew.woff2": (6072, "e5e35b81dd2288b1f96083c0d456861645c74fda66056d3bea1cfc40c15883c2"),
    "OFL-archivo.txt": (4388, "108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b"),
    "OFL-heebo.txt": (4474, "866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3"),
}
HASHED = ("archivo-text.97c5421649.woff2", "archivo-narrow.d5c5f1b561.woff2", "heebo-hebrew.e5e35b81dd.woff2")
README_FILE = re.compile(r"^\| `([^`]+)` \| ([\d,]+) \| `([0-9a-f]{64})` \|$", re.M)
URL = re.compile(r"url\(([^)]*)\)")


def test_each_font_and_licence_is_the_one_its_readme_names():
    """Design test 9: each committed file's bytes and SHA-256 are the README's, and the README's are the design's."""
    readme = {name: (int(size.replace(",", "")), sha256)
              for name, size, sha256 in README_FILE.findall((FONT_DIR / "README.md").read_text(encoding="utf-8"))}
    assert readme == FILES
    committed = {name: (len(data), hashlib.sha256(data).hexdigest())
                 for name in (*FONTS, *LICENCES) for data in [(FONT_DIR / name).read_bytes()]}
    assert committed == readme


def test_a_hashed_name_carries_ten_hex_of_its_bytes():
    assert hashed("archivo-text.woff2", (FONT_DIR / "archivo-text.woff2").read_bytes()) == "archivo-text.97c5421649.woff2"
    assert hashed("look.css", b"") == "look.e3b0c44298.css"


def test_the_shared_files_are_the_fonts_the_licences_and_the_stylesheet():
    files = asset_files()
    assert list(files) == [f"{FOLDER}/{name}" for name in (*HASHED, *LICENCES)] + [STYLESHEET]
    assert FOLDER == "assets" and re.fullmatch(r"assets/look\.[0-9a-f]{10}\.css", STYLESHEET)
    assert STYLESHEET == f"{FOLDER}/" + hashed("look.css", files[STYLESHEET])
    for name, published in zip((*FONTS, *LICENCES), (*HASHED, *LICENCES)):
        assert files[f"{FOLDER}/{published}"] == (FONT_DIR / name).read_bytes()


def test_the_stylesheet_names_the_fonts_by_their_hashed_names():
    published = asset_files()[STYLESHEET].decode("utf-8")
    assert URL.findall(published) == [HASHED[0], HASHED[2], HASHED[1], HASHED[2]]
    plain = published
    for font, name in zip(FONTS, HASHED):
        plain = plain.replace(f"url({name})", f"url({font})")
    assert plain.encode("utf-8") == (STATIC / SHEET).read_bytes()


@pytest.mark.parametrize("change", [
    lambda css: css.replace("}", ";src:url(other.woff2)}", 1),                  # a fourth file named
    lambda css: css.replace("url(archivo-narrow.woff2)", "local(Archivo)"),     # one font no longer named
])
def test_a_stylesheet_naming_another_file_is_refused(tmp_path, monkeypatch, change):
    shutil.copytree(STATIC, tmp_path / "static")
    sheet = tmp_path / "static" / SHEET
    sheet.write_text(change(sheet.read_text(encoding="utf-8")), encoding="utf-8")
    monkeypatch.setattr(assets, "STATIC", tmp_path / "static")
    with pytest.raises(ValueError, match="look.css"):
        asset_files()


def test_the_shared_files_stay_small():
    """Design test 10: the stylesheet under 22,000 bytes, the three fonts under 45,000 together."""
    files = asset_files()
    assert len(files[STYLESHEET]) < 22_000
    assert sum(len(files[f"{FOLDER}/{name}"]) for name in HASHED) < 45_000


def test_the_shared_files_are_the_same_bytes_twice():
    assert asset_files() == asset_files()

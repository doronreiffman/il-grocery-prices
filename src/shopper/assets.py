"""The shopper site's shared files, its `assets/` folder (docs/site-look.md, "The shared stylesheet and the font
files"): the three fonts, the two families' licences and the one stylesheet every page links; and the front page's
link preview picture (docs/link-preview.md, "What changes").

The repository keeps them under plain names: the stylesheet as `static/look.css` (the design's appendix), the fonts and
licences in `static/fonts/` (its README gives each file's source and SHA-256), the picture as `static/card.png`, a
1200 x 630 PNG drawn once and committed as made. The site gets each font and the picture under a hashed name, the
licences under their own names, and the stylesheet with each `url(<font>)` written as the font's hashed name, under a
hashed name of its own. A hashed name is the file's name with the first ten hex digits of its bytes' SHA-256
before its last suffix: a name changes when its bytes do, so a page cached for its five minutes still finds the
stylesheet it names, an app that keeps a link's preview never shows an old picture under a new card, and no file
ever needs replacing under its name. `STYLESHEET`, the stylesheet's path in the site, is worked out from the files when
the module loads; every page links it. `CARD_IMAGE`, the picture's path in the site, is worked out the same way; the
front page's card names it (`shopper.shell`).

The code fingerprint (`code_sha`) covers `.py` files only, so it does not cover these files, as it does not cover
`search.js`; the golden pages' pin catches a change to them.
"""
import hashlib
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"
FOLDER = "assets"                   # the site's folder of shared files
SHEET = "look.css"                  # in STATIC
FONTS = ("archivo-text.woff2", "archivo-narrow.woff2", "heebo-hebrew.woff2")   # in STATIC / "fonts"
LICENCES = ("OFL-archivo.txt", "OFL-heebo.txt")                                 # in STATIC / "fonts", published as named
CARD = "card.png"                   # in STATIC: the front page's link preview picture, 1200 x 630 (q45)
URL = re.compile(r"url\(([^)]*)\)")


def hashed(name: str, data: bytes) -> str:
    """`name` with the first ten hex digits of `data`'s SHA-256 before its last suffix: "look.e3b0c44298.css"."""
    stem, _, suffix = name.rpartition(".")
    return f"{stem}.{hashlib.sha256(data).hexdigest()[:10]}.{suffix}"


def asset_files() -> dict[str, bytes]:
    """The site's shared files, "assets/<name>" to bytes, in a fixed order: the fonts under their hashed names, the
    licences, the card's picture under its hashed name, then the stylesheet naming the fonts by their hashed names,
    under its own. ValueError when the stylesheet's `url()`s name anything but the fonts, or leave one out."""
    plain = (STATIC / SHEET).read_bytes()
    named = set(URL.findall(plain.decode("utf-8")))
    if named != set(FONTS):
        raise ValueError(f"{SHEET} names {sorted(named)}, not the fonts {sorted(FONTS)}")
    files, names = {}, {}
    for font in FONTS:
        data = (STATIC / "fonts" / font).read_bytes()
        names[font] = hashed(font, data)
        files[f"{FOLDER}/{names[font]}"] = data
    for licence in LICENCES:
        files[f"{FOLDER}/{licence}"] = (STATIC / "fonts" / licence).read_bytes()
    card = (STATIC / CARD).read_bytes()
    files[f"{FOLDER}/{hashed(CARD, card)}"] = card
    sheet = URL.sub(lambda url: f"url({names[url[1]]})", plain.decode("utf-8")).encode("utf-8")
    files[f"{FOLDER}/{hashed(SHEET, sheet)}"] = sheet
    return files


CARD_IMAGE, STYLESHEET = [*asset_files()][-2:]   # the picture's and the stylesheet's paths in the site: the last two

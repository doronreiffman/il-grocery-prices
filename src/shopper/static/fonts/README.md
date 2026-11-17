# The shopper site's fonts

The three font files the shopper site serves, and the two families' licences, committed as built: the site's build needs no font tool. `src/shopper/assets.py` publishes them in the site's `assets/` folder, each font under a name carrying its hash, the licences under these names; the stylesheet, `src/shopper/static/look.css`, names the fonts by these plain names. The design: `docs/site-look.md`, "Type" and "The shared stylesheet and the font files".

| File | Bytes | SHA-256 |
|---|---|---|
| `archivo-text.woff2` | 25,660 | `97c5421649b850b9161c7e708d16a93edf171ce7411eac77718a522cf413505c` |
| `archivo-narrow.woff2` | 11,420 | `d5c5f1b561f4f5d6f922928132dfde05cdce396c1a6b64cceb14da856f10aad3` |
| `heebo-hebrew.woff2` | 6,072 | `e5e35b81dd2288b1f96083c0d456861645c74fda66056d3bea1cfc40c15883c2` |
| `OFL-archivo.txt` | 4,388 | `108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b` |
| `OFL-heebo.txt` | 4,474 | `866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3` |

What each font holds:

- `archivo-text.woff2`: Archivo at its normal width (100), weights 400 to 700, the Latin subset. The stylesheet's "Shelf".
- `archivo-narrow.woff2`: Archivo at width 70, weight 800, the Latin subset. The stylesheet's "Shelf Narrow".
- `heebo-hebrew.woff2`: Heebo, weights 400 to 800: the Hebrew block, the shekel sign and the space. "Shelf" and "Shelf Narrow" both draw Hebrew and the shekel sign with it.

The Latin subset is Basic Latin, Latin-1, the en and em dashes, the curly quotes, the bullet, the ellipsis, the left and right arrows and the minus sign.

## Sources

Each family comes from a fixed commit of the `google/fonts` repository on GitHub. Each file was read at that commit and its SHA-256 compared with the one below:

| Family | Version | Commit | Source file | SHA-256 |
|---|---|---|---|---|
| Archivo | 2.001 | `6c70c829f09ea345d3590406693220ea35c6553f` | `ofl/archivo/Archivo[wdth,wght].ttf` | `0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053` |
| Archivo | 2.001 | `6c70c829f09ea345d3590406693220ea35c6553f` | `ofl/archivo/OFL.txt` | `108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b` |
| Heebo | 3.100 | `804ab16a8ff8ac0072e7c5ecc34e381b4a710177` | `ofl/heebo/Heebo[wght].ttf` | `18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30` |
| Heebo | 3.100 | `804ab16a8ff8ac0072e7c5ecc34e381b4a710177` | `ofl/heebo/OFL.txt` | `866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3` |

## Licence

Both families are under the SIL Open Font License 1.1. `OFL-archivo.txt` and `OFL-heebo.txt` are each family's `OFL.txt` at its commit, unchanged, and the site serves them beside the fonts, as the licence asks. Archivo's copyright line is "Copyright 2020 The Archivo Project Authors (https://github.com/Omnibus-Type/Archivo)", Heebo's "Copyright 2014 The Heebo Project Authors (https://github.com/OdedEzer/heebo)".

A subset is a modified version, and the licence forbids a modified version from using a Reserved Font Name. Neither family declares one (the words appear only in the licence's own definitions), so the subsets keep their names; the stylesheet calls them "Shelf" and "Shelf Narrow" all the same. The copyright and licence names stay inside each font file.

## Making them again

`scripts/subset_fonts.py` makes the five files from the sources above: it fetches each source (or takes it from `--sources` when it is already there), refuses one whose SHA-256 is not the pinned one, instances and subsets each font with fonttools and compresses it to WOFF2 with brotli. The tools live only in a throwaway virtual environment outside the repository: they are never in the project's requirements, and CI does not run the script. Made twice from the same sources, the files come out the same bytes.

With Python 3.13 on macOS, from the repository's root (the two hashes are those of the `cp313-cp313-macosx_10_13_universal2` wheels on PyPI; another system needs its own wheels' hashes):

```sh
WORK=$(mktemp -d)
python3.13 -m venv "$WORK/fonts-venv"
cat > "$WORK/font-tools.txt" <<'EOF'
fonttools==4.59.0 --hash=sha256:78813b49d749e1bb4db1c57f2d4d7e6db22c253cb0a86ad819f5dc197710d4b2
brotli==1.2.0 --hash=sha256:9e5825ba2c9998375530504578fd4d5d1059d09621a02065d1b6bfc41a8e05ab
EOF
"$WORK/fonts-venv/bin/pip" install --no-deps --require-hashes -r "$WORK/font-tools.txt"
"$WORK/fonts-venv/bin/python" -I scripts/subset_fonts.py --sources "$WORK/fonts-src" --out "$WORK/fonts-out"
```

The script prints each file's bytes and SHA-256; compare them with the table above before copying the files here. New bytes change the fonts' hashed names, and with them the stylesheet's.

"""The stylesheet is its design's appendix, byte for byte (docs/site-look.md, "Appendix: the stylesheet"; the
site-look plan's Global Constraints): the one ```css block of the design, the lines between its fences, is
src/shopper/static/look.css. A change to either without the other fails here.

Kept out of tests/test_look.py on purpose: every `(q36 look)` mutation breaks the stylesheet, and an equality test
among the tests those mutations run would fail under each of them, catching them all for the wrong reason (as
tests/test_mutation_targets.py stays out of tests/test_mutation_check.py)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "site-look.md"
SHEET = ROOT / "src" / "shopper" / "static" / "look.css"
FENCE, CLOSE = "```css\n", "```\n"


def appendix(design: str) -> str:
    """The design's stylesheet: the lines after its one ```css fence up to the next closing fence, as
    `sed -n '/^```css$/,/^```$/p' | sed '1d;$d'` gives them."""
    lines = design.splitlines(keepends=True)
    opens = [at for at, line in enumerate(lines) if line == FENCE]
    assert len(opens) == 1, f"{len(opens)} css blocks in the design"
    end = lines.index(CLOSE, opens[0] + 1)
    return "".join(lines[opens[0] + 1:end])


def test_the_stylesheet_is_the_designs_appendix_byte_for_byte():
    sheet = SHEET.read_bytes()
    assert appendix(DESIGN.read_text(encoding="utf-8")).encode("utf-8") == sheet
    assert sheet.endswith(b"}\n") and len(sheet) > 20_000


def test_the_appendix_is_read_as_sed_reads_it():
    design = "# A design\n```html\n<p>\n```\n\n```css\na{b:c}\nd{e:f}\n```\n\nMore.\n```\nx\n```\n"
    assert appendix(design) == "a{b:c}\nd{e:f}\n"

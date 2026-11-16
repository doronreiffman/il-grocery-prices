"""The shopper site's stylesheet, `src/shopper/static/look.css` (docs/site-look.md: "Colour", its "Contrast" table, "The
chart", "The shared stylesheet and the font files", "What the tests should pin" 1, 2, 4 and 8, and its appendix, which
the file is byte for byte; the site-look plan's Task 1).

The stylesheet is read by a small parser of its own: each rule as the @media around it, its selector and its
declarations in order. The light tokens are the top-level `:root` block's; the dark ones the `:root` block under
`@media (prefers-color-scheme:dark)`, laid over the light."""
import re
from pathlib import Path
from typing import NamedTuple

from shopper.pages import FRONT_HEADS

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "src" / "shopper" / "static" / "look.css"
DARK = "@media (prefers-color-scheme:dark)"
PHONE = "@media (max-width:47.99rem)"
WIDE = "@media (min-width:64rem)"
PRINT = "@media print"
# The three font files the stylesheet names, by their plain names (shopper.assets refuses a stylesheet whose url()s
# are not exactly its FONTS).
FONT_FILES = ("archivo-text.woff2", "archivo-narrow.woff2", "heebo-hebrew.woff2")

# The design's "Colour" table, both themes.
LIGHT = {"--bg": "#ffffff", "--ink": "#111111", "--ink-2": "#555555", "--line": "#d6d6d6", "--soft": "#f1f1ee",
         "--d1": "#c8f1d5", "--d2": "#6fdc9b", "--d3": "#22b35e", "--on-deal": "#111111", "--nd": "#ffd60a",
         "--on-nd": "#111111", "--nd-edge": "#111111", "--sale": "#0b7a3b", "--plate": "#ffffff", "--bars": "#111111"}
DARK_TOKENS = {**LIGHT, "--bg": "#131313", "--ink": "#f2f2ef", "--ink-2": "#b4b4b0", "--line": "#3d3d3a",
               "--soft": "#222220", "--d1": "#27995a", "--d2": "#34b76a", "--d3": "#4fe08c", "--nd": "#ffd60a",
               "--on-nd": "#111111", "--nd-edge": "#ffd60a", "--sale": "#4fe08c"}

# The design's "Contrast" table, by token: words at 4.5:1, lines, edges and marks at 3:1. The hairlines (line on bg)
# are decoration and have no line. The green labels' edges are added from the stylesheet's own --edge rules.
WORDS = 4.5
MARKS = 3
PAIRS = [("ink", "bg", WORDS), ("ink-2", "bg", WORDS), ("on-deal", "d1", WORDS), ("on-deal", "d2", WORDS),
         ("on-deal", "d3", WORDS), ("on-nd", "nd", WORDS), ("sale", "bg", WORDS), ("bg", "ink", WORDS),
         ("ink", "soft", WORDS), ("ink-2", "soft", WORDS), ("bars", "plate", WORDS),
         ("ink", "bg", MARKS), ("ink-2", "bg", MARKS), ("nd-edge", "bg", MARKS)]
GREENS = ("deal-1", "deal-2", "deal-3")
EDGE_RULE = ".deal-1,.deal-2,.deal-3,.brand b,h1 .yes"

# CSS Color 4's named colours (section 6.1, "Named Colors"; the W3C's published draft, read 2026-11-16), all 148.
NAMED_COLOURS = frozenset("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood
cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray
darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid
mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown
royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow
springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen
""".split())
COLOUR_FUNCTION = re.compile(r"\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
HEX = re.compile(r"#[0-9a-f]{3,8}\b", re.I)
STRING = re.compile(r'"[^"]*"|\'[^\']*\'')
WORD = re.compile(r"(?<![\w-])[a-z]+(?![\w-])", re.I)


class Rule(NamedTuple):
    media: str                              # the @media prelude around the rule, "" at the top
    selector: str
    declarations: list[tuple[str, str]]     # (property, value), in order


def split(text: str, sep: str) -> list[str]:
    """`text` cut at each `sep` outside quotes and brackets, each part trimmed, empty parts dropped."""
    parts, depth, quote, start = [], 0, None, 0
    for at, char in enumerate(text):
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == sep and depth == 0:
            parts.append(text[start:at])
            start = at + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def rules(css: str) -> list[Rule]:
    """Every rule of `css` in order, a group's (an @media's) rules with its prelude."""
    found, groups, buffer, quote = [], [], "", None
    for char in css:
        if quote:
            buffer += char
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
            buffer += char
        elif char == "{":
            if groups:
                groups[-1][1] = True            # the block around this one holds rules: a group
            groups.append([buffer.strip(), False])
            buffer = ""
        elif char == "}":
            prelude, group = groups.pop()
            if not group:
                declarations = [tuple(part.strip() for part in item.split(":", 1)) for item in split(buffer, ";")]
                found.append(Rule(" ".join(outer for outer, _ in groups), prelude, declarations))
            buffer = ""
        else:
            buffer += char
    assert groups == [] and buffer.strip() == ""
    return found


def _rules() -> list[Rule]:
    return rules(SHEET.read_text(encoding="utf-8"))


def _roots() -> tuple[Rule, Rule]:
    light = [rule for rule in _rules() if rule.media == "" and rule.selector == ":root"]
    dark = [rule for rule in _rules() if rule.media == DARK and rule.selector == ":root"]
    assert len(light) == 1 and len(dark) == 1
    return light[0], dark[0]


def _colours(declarations: list[tuple[str, str]]) -> dict[str, str]:
    return {name: value for name, value in declarations if name.startswith("--") and re.fullmatch(r"#[0-9a-f]{6}", value)}


def themes() -> dict[str, dict[str, str]]:
    """The colour tokens of each theme, by name without its dashes: the dark theme's laid over the light."""
    light, dark = _roots()
    light_tokens = _colours(light.declarations)
    dark_tokens = {**light_tokens, **_colours(dark.declarations)}
    return {theme: {name.removeprefix("--"): value for name, value in tokens.items()}
            for theme, tokens in (("light", light_tokens), ("dark", dark_tokens))}


def _label_tokens(theme: str) -> dict[str, dict[str, str]]:
    """Each green label's --fill and --edge in `theme`, as the token each names (`var(--fill)` read as the fill's)."""
    medias = ("",) if theme == "light" else ("", DARK)
    found = {label: {} for label in GREENS}
    for media in medias:                        # the dark query's rules come after the top level's and win
        for rule in _rules():
            if rule.media != media:
                continue
            for label in GREENS:
                if f".{label}" in split(rule.selector, ","):
                    for name, value in rule.declarations:
                        if name in ("--fill", "--edge"):
                            found[label][name.removeprefix("--")] = value
    resolved = {}
    for label, values in found.items():
        fill = re.fullmatch(r"var\(--([\w-]+)\)", values["fill"])[1]
        edge = re.fullmatch(r"var\(--([\w-]+)\)", values["edge"])[1]
        resolved[label] = {"fill": fill, "edge": fill if edge == "fill" else edge}
    return resolved


def luminance(colour: str) -> float:
    """WCAG 2.2's relative luminance of a `#rrggbb` colour."""
    channels = [int(colour[at:at + 2], 16) / 255 for at in (1, 3, 5)]
    red, green, blue = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _pixels(size: str) -> float:
    number, unit = re.fullmatch(r"(\d*\.?\d+)([a-z%]+)", size).groups()
    assert unit in ("rem", "px"), f"a chart size in {unit}: {size}"
    return float(number) * (16 if unit == "rem" else 1)


def _font_size(name: str, value: str) -> str | None:
    """The size a `font-size` or `font` declaration sets, as written; None for any other property."""
    if name == "font-size":
        return value
    if name == "font":
        sizes = [word.split("/")[0] for word in value.split() if re.match(r"\d*\.?\d+[a-z%]", word)]
        assert sizes, f"a font shorthand with no size: {value}"
        return sizes[0]
    return None


# ---- the tokens ----

def test_the_tokens_are_the_designs():
    assert themes() == {"light": {name.removeprefix("--"): value for name, value in LIGHT.items()},
                        "dark": {name.removeprefix("--"): value for name, value in DARK_TOKENS.items()}}


def test_every_pair_holds_its_contrast_in_both_themes():
    """Design test 1: every pair of the "Contrast" table at or above its line, light and dark, each green label's edge
    against the page as the stylesheet's --edge rules give it (ink on paper, the label's own green on the dark page)."""
    failing = []
    for theme, tokens in themes().items():
        labels = _label_tokens(theme)
        pairs = PAIRS + [(labels[label]["edge"], "bg", MARKS) for label in GREENS]
        for words, ground, line in pairs:
            ratio = contrast(tokens[words], tokens[ground])
            if ratio < line:
                failing.append(f"{theme}: {words} on {ground} {ratio:.2f} < {line}")
    assert failing == []


def test_a_green_labels_edge_is_ink_on_paper_and_its_own_green_on_the_dark_page():
    edges = [(rule.media, value) for rule in _rules() if rule.selector == EDGE_RULE
             for name, value in rule.declarations if name == "--edge"]
    assert edges == [("", "var(--ink)"), (DARK, "var(--fill)")]
    assert {label: _label_tokens("light")[label]["edge"] for label in GREENS} == dict.fromkeys(GREENS, "ink")
    assert {label: _label_tokens("dark")[label]["edge"] for label in GREENS} == {"deal-1": "d1", "deal-2": "d2",
                                                                                "deal-3": "d3"}


def test_no_colour_outside_the_tokens():
    """Design test 2: with the two :root blocks taken out, no colour is written: no #colour, no colour function, no
    named colour as a whole word of a value (`transparent` is the one keyword allowed)."""
    roots = _roots()
    written = []
    for rule in _rules():
        if rule in roots:
            continue
        for name, value in rule.declarations:
            bare = STRING.sub("", value)
            words = {word.lower() for word in WORD.findall(bare)} & NAMED_COLOURS
            if HEX.search(bare) or COLOUR_FUNCTION.search(bare) or words:
                written.append(f"{rule.selector}{{{name}:{value}}}")
    assert written == []
    assert "transparent" not in NAMED_COLOURS and len(NAMED_COLOURS) == 148


def test_every_token_used_is_defined():
    css = SHEET.read_text(encoding="utf-8")
    used = set(re.findall(r"var\((--[\w-]+)", css))
    defined = {name for rule in _rules() for name, _ in rule.declarations if name.startswith("--")}
    assert used and used - defined == set()


# ---- the chart, the hidden parts, the layout ----

def test_the_charts_words_never_shrink():
    """Design test 4, its stylesheet half: every size in a rule of the chart, its table or its key is 12 pixels or
    more, and every stroke of the lines' SVG (its paths and lines) keeps its width whatever the SVG's stretch."""
    sizes = []
    for rule in _rules():
        if not re.search(r"\.(chart|stats|key)(?![\w-])", rule.selector):
            continue
        for name, value in rule.declarations:
            size = _font_size(name, value)
            if size is not None:
                sizes.append((rule.media, rule.selector, size))
    small = [entry for entry in sizes if _pixels(entry[2]) < 12]
    assert len(sizes) >= 8 and small == []
    strokes = [rule for rule in _rules() if rule.media == "" and rule.selector == ".chart path,.chart line"]
    assert len(strokes) == 1 and ("vector-effect", "non-scaling-stroke") in strokes[0].declarations


def test_nothing_is_hidden_but_by_a_named_rule():
    """`[hidden]` wins over every rule (so a part the script hides stays hidden); the only other rules that hide are
    the two filters' rows, the badge's hidden separator, the chart's dates near an end on a phone, and print's."""
    hiding = [(rule.media, rule.selector, re.sub(r"\s*!\s*", "!", value)) for rule in _rules()
              for name, value in rule.declarations if name == "display" and value.startswith("none")]
    assert hiding == [
        ("", "[hidden]", "none!important"),
        ("", "#f-club:checked~.table tbody tr[data-club],#f-spend:checked~.table tbody tr[data-spend]", "none"),
        ("", "nav .badge i", "none"),
        (PHONE, ".chart .near", "none"),
        (PRINT, ".store,.search,.letters,.toc,.deals>input,.deals>label", "none"),
    ]
    important = [rule.selector for rule in _rules() for name, value in rule.declarations
                 if name == "display" and "important" in value]
    assert important == ["[hidden]"]


def test_the_two_column_rules_need_the_script():
    """Design test 8: the product page's two columns are the stylesheet's alone, and only while the script runs."""
    wide = [rule for rule in _rules() if rule.media == WIDE]
    selectors = [selector for rule in wide for selector in split(rule.selector, ",")]
    assert selectors and [selector for selector in selectors if not selector.startswith(".js ")] == []


def test_the_phones_label_for_the_usual_price_is_the_tables_head():
    """A phone's store row writes the usual price's column head before it: the first `content` for browsers without
    alternative text, then the same words with none, so a screen reader reads the cell's own head."""
    label = [rule for rule in _rules() if rule.media == PHONE and rule.selector == "table.front td:nth-child(4)::before"]
    assert len(label) == 1
    contents = [value for name, value in label[0].declarations if name == "content"]
    assert contents ==[f'"{FRONT_HEADS[3]} "', f'"{FRONT_HEADS[3]} "/""']


def test_no_motion_and_nothing_from_outside():
    css = SHEET.read_text(encoding="utf-8")
    moving = [(rule.selector, name) for rule in _rules() for name, _ in rule.declarations
              if name.split("-")[0] in ("transition", "animation")]
    assert moving == [] and "@keyframes" not in css and "@import" not in css
    named = re.findall(r"url\(([^)]*)\)", css)
    assert named and [name for name in named if name not in FONT_FILES] == []


def test_print_leaves_out_the_controls():
    hidden = {selector for rule in _rules() if rule.media == PRINT and ("display", "none") in rule.declarations
              for selector in split(rule.selector, ",")}
    assert hidden == {".store", ".search", ".letters", ".toc", ".deals>input", ".deals>label"}

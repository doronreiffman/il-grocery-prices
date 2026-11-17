"""The shopper site's stylesheet, `src/shopper/static/look.css` (docs/site-look.md: "Colour", its "Contrast" table, "The
chart", "The header's name: green and yellow", "The front page stays put, with a shortcut to your store", "The shared
stylesheet and the font files", "What the tests should pin" 1, 2, 4 and 8, and its appendix, which the file is byte for
byte; the site-look plan's Task 1).

The stylesheet is read by a small parser of its own: each rule as the @media around it, its selector and its
declarations in order. The light tokens are the top-level `:root` block's; the dark ones the `:root` block under
`@media (prefers-color-scheme:dark)`, laid over the light."""
import re
from pathlib import Path
from typing import NamedTuple

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


def _declared(selector: str) -> dict[str, str]:
    """The declarations of the one top-level rule with this selector."""
    (rule,) = [rule for rule in _rules() if rule.media == "" and rule.selector == selector]
    return dict(rule.declarations)


def test_the_date_line_is_quiet_and_the_dotted_stretch_is_not_the_usual_price():
    """The one line (docs/site-look.md, "The chart", the owner's of 2026-11-16): the date line and the dates' marks are
    1 pixel in the second ink, never the price line's colour or weight, so the date line never reads as a price; the
    dotted stretch over days with no price (`.gap`) and the usual price's dashes (`.usual`) each have a dash pattern,
    and not the same one; a sale's dotted stretch (`gap sale`) takes the sale's colour and weight from
    `.chart path.sale`, which sets no pattern of its own, so it keeps its dots."""
    line = _declared(".chart path.paid")["stroke"]
    assert line == "var(--ink)" and _declared(".chart path.paid")["stroke-width"] == "2"
    assert _declared(".chart .lines")["border-bottom"] == "1px solid var(--ink-2)"
    assert _declared(".chart line")["stroke"] == "var(--ink-2)" != line
    gap, usual = _declared(".chart .gap"), _declared(".chart .usual")
    assert gap["stroke"] == line and gap["stroke-width"] == "2"
    dots, dashes = gap.get("stroke-dasharray"), usual.get("stroke-dasharray")
    assert dots and dashes and dots != dashes
    assert "stroke-dasharray" not in _declared(".chart path.sale")
    selectors = [rule.selector for rule in _rules() if rule.media == ""]
    assert selectors.index(".chart .gap") < selectors.index(".chart path.sale")
    # the key's one swatch for a line is the sale's: the plain line has no entry
    assert _declared(".key i")["border-top"] == "3.5px solid var(--sale)" and ".key .sale" not in selectors
    assert not [selector for selector in selectors if re.search(r"\.listed(?![\w-])", selector)]


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
        (PRINT, ".store,.search,.letters,.toc,.deals>input,.deals>label,.yours", "none"),
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
    alternative text, then the same words with none, so a screen reader reads the cell's own head. FRONT_HEADS is
    imported here, not at the top: once the pages import shopper.assets, which reads the stylesheet when it loads, a
    module-level import would turn a break of a url() into a collection error, which the mutation check does not count
    as caught."""
    from shopper.pages import FRONT_HEADS

    label =[rule for rule in _rules() if rule.media == PHONE and rule.selector == "table.front td:nth-child(4)::before"]
    assert len(label) == 1
    contents = [value for name, value in label[0].declarations if name == "content"]
    assert contents == [f'"{FRONT_HEADS[3]} "', f'"{FRONT_HEADS[3]} "/""']


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
    assert hidden == {".store", ".search", ".letters", ".toc", ".deals>input", ".deals>label", ".yours"}


def test_the_headers_no_deal_is_the_yellow_label():
    """The owner (2026-11-16): the header's name drawn as the front page's headline, "No Deal" on the yellow label,
    with the yellow label's three tokens, so light and dark follow."""
    found = [rule for rule in _rules() if rule.selector == ".brand .no"]
    assert len(found) == 1 and found[0].media == ""
    taken = dict(found[0].declarations)
    assert ((taken["border-color"], taken["background"], taken["color"])
            == ("var(--nd-edge)", "var(--nd)", "var(--on-nd)"))


def test_the_shortcuts_arrow_is_not_read_aloud():
    """The root's "Your store" ends in an arrow the stylesheet draws: the first `content` for browsers without
    alternative text, then the same arrow with none, so a screen reader says "Your store Shufersal Deal, link"."""
    arrow = [rule for rule in _rules() if rule.media == "" and rule.selector == ".yours a::after"]
    assert len(arrow) == 1
    contents = [value for name, value in arrow[0].declarations if name == "content"]
    assert contents == ['"\\2192"', '"\\2192"/""']


# ---- the answer's colours and the marks that carry meaning, read from the rules (the whole-branch review, I3) ----

VAR = re.compile(r"var\(--([\w-]+)\)")
# The rules that set a ground and hold no words, each held by a test of its own below: a ticked filter's square, the
# barcode's plate in the dark theme, and the key's swatch for an unread sale price (a pattern in the sale's green).
NO_WORDS = {".deals>input:checked+label::before", ".code svg", ".key .unread"}
# Each label, by its rule: the ground it takes, as the tokens of every label it serves, and its words' token. A Deal is
# green in the shade of its saving, No deal yellow, both with dark words (site-look.md, "The label", "Small labels",
# "The front page", "The header's name: green and yellow").
LABELS = {
    ":is(.deal-1,.deal-2,.deal-3)>.say": ({"d1", "d2", "d3"}, "on-deal"),
    ".no-deal>.say": ({"nd"}, "on-nd"),
    "span.badge:is(.deal-1,.deal-2,.deal-3),nav :is(.deal-1,.deal-2,.deal-3) b": ({"d1", "d2", "d3"}, "on-deal"),
    "span.badge.no-deal,nav .no-deal b": ({"nd"}, "on-nd"),
    "h1 .yes": ({"d3"}, "on-deal"),
    "h1 .no": ({"nd"}, "on-nd"),
    ".brand b": ({"d3"}, "on-deal"),
    ".brand .no": ({"nd"}, "on-nd"),
}


def _token(value: str) -> str | None:
    """The token a value is, `var(--x)` read as "x"; None for anything else."""
    found = VAR.fullmatch(value)
    return found[1] if found else None


def _carriers(part: str) -> list[str]:
    """The selectors a selector part takes its `--fill` from: the classes inside its `:is(...)`, else itself."""
    inside = re.search(r":is\(([^)]*)\)", part)
    return split(inside[1], ",") if inside else [part]


def _fill(carrier: str) -> str:
    """The token of a label's `--fill`: the one top-level rule that lists `carrier` and sets `--fill`."""
    (value,) = [value for rule in _rules() if rule.media == "" and carrier in split(rule.selector, ",")
                for name, value in rule.declarations if name == "--fill"]
    return _token(value)


def _grounds(token: str, part: str) -> set[str]:
    """The tokens a ground of `token` set by the selector part `part` stands for: `fill` read as each label's own."""
    return {_fill(carrier) for carrier in _carriers(part)} if token == "fill" else {token}


def _in(rule: Rule, theme: str) -> bool:
    return theme == "dark" or DARK not in rule.media


def test_the_words_on_every_ground_hold_their_contrast():
    """Goal 3 ("every text ... passes WCAG 2.2 AA in both themes, checked by a test from the stylesheet's own
    colours"), read from the rules themselves rather than from a list of pairs. Each rule that sets a ground (a
    `background` token), but the three that hold no words, has words in the colour it names, or in the page's ink when
    it names none; a rule that names a colour and no ground stands on the ground of the rule whose selector it extends
    (`#pick a:hover small` on `#pick a:hover`'s ink), else on the page. A `var(--fill)` ground is read as each label it
    serves: the three greens of `.deal-1` to `.deal-3`, the full green of `.brand b` and `h1 .yes`. Every pair holds
    4.5:1 in each theme its rule applies in."""
    tokens = themes()
    grounds = {}                                # selector part: (its rule, the tokens it stands for)
    for rule in _rules():
        background = dict(rule.declarations).get("background")
        if background is None or rule.selector in NO_WORDS:
            continue
        token = _token(background)
        assert token, f"a ground that is not a token: {rule.selector}{{background:{background}}}"
        for part in split(rule.selector, ","):
            grounds[part] = (rule, _grounds(token, part))
    checked, failing = [], []
    for rule in _rules():
        declared = dict(rule.declarations)
        if "color" not in declared and ("background" not in declared or rule.selector in NO_WORDS):
            continue
        if declared.get("color") == "inherit":          # a link's words are the words around it
            continue
        words = _token(declared.get("color", "var(--ink)"))
        assert words, f"words not in a token: {rule.selector}{{color:{declared['color']}}}"
        for part in split(rule.selector, ","):
            if part in grounds:
                ground_rule, under = grounds[part]
            else:
                around = [ground for ground in grounds if part.startswith((ground + " ", ground + ">"))]
                ground_rule, under = grounds[max(around, key=len)] if around else (rule, {"bg"})
            for theme in ("light", "dark"):
                if not (_in(rule, theme) and _in(ground_rule, theme)):
                    continue
                for ground in sorted(under):
                    ratio = contrast(tokens[theme][words], tokens[theme][ground])
                    checked.append((part, theme, ground))
                    if ratio < WORDS:
                        failing.append(f"{theme}: {part} {words} on {ground} {ratio:.2f}")
    assert failing == []
    named = {part for part, _, _ in checked}
    assert {part for selector in LABELS for part in split(selector, ",")} <= named
    assert {".tile.lowest", "#pick a:hover", ".yours a:hover", "#pick a:hover small", "#pick a:hover b",
            ".yours a:hover small", ".letters a[aria-current]", "td.low"} <= named


def test_a_deal_is_green_and_no_deal_yellow_with_dark_words():
    """Each label's rule takes the ground its call has and the dark words on it: a Deal's own shade of green (the
    three for the label and the small labels, the full green for the headline's and the header's DEAL), No deal's
    yellow."""
    found = {}
    for selector in LABELS:
        (rule,) = [rule for rule in _rules() if rule.media == "" and rule.selector == selector]
        declared = dict(rule.declarations)
        ground = _token(declared["background"])
        found[selector] = ({token for part in split(selector, ",") for token in _grounds(ground, part)},
                           _token(declared["color"]))
    assert found == LABELS


def test_the_sale_is_drawn_in_the_sales_green():
    """The chart's sale stretch, today's sale price and its dot, and the ticks of an unread sale price take `--sale`
    (the "Contrast" table: 5.44:1 on paper, 10.95:1 on the dark page), never the line's ink or a label's green."""
    assert _declared(".chart path.sale")["stroke"] == "var(--sale)"
    assert _declared(".chart text.sale")["fill"] == "var(--sale)"
    assert _declared(".chart circle.sale")["fill"] == "var(--sale)"
    assert _declared(".chart .unread")["stroke"] == "var(--sale)"
    assert contrast(themes()["light"]["sale"], themes()["light"]["bg"]) >= WORDS


def test_the_bars_stand_on_their_plate():
    """The barcode (site-look.md, "The barcode"): its bars are `--bars`, dark in both themes, on what they stand on:
    the label's paper in the light theme, which draws no plate, and in the dark theme the white plate (`--plate`) it
    draws behind them, so a scanner reads them; 4.5:1 or more in both."""
    bars = _token(_declared("#ean")["stroke"])
    assert bars == "bars"
    light = [rule for rule in _rules() if rule.media == "" and rule.selector == ".code svg"
             and "background" in dict(rule.declarations)]
    (dark,) = [rule for rule in _rules() if rule.media == DARK and rule.selector == ".code svg"]
    assert light == [] and _token(dict(dark.declarations)["background"]) == "plate"
    tokens = themes()
    assert contrast(tokens["light"][bars], tokens["light"]["bg"]) >= WORDS
    assert contrast(tokens["dark"][bars], tokens["dark"]["plate"]) >= WORDS


def test_the_focus_and_a_ticked_filter_are_drawn_in_ink():
    """Focus (site-look.md, "Focus"): `:focus-visible` draws a 3-pixel ink ring; the filters' boxes are hidden, so
    their labels take it; and a ticked filter's square fills with ink ("Filters"), 18.88:1 on paper and 16.57:1 on the
    dark page."""
    assert _declared(":focus-visible")["outline"] == "3px solid var(--ink)"
    assert _declared(".deals>input:focus-visible+label")["outline"] == "3px solid var(--ink)"
    assert _declared(".deals>input:checked+label::before")["background"] == "var(--ink)"
    assert all(contrast(tokens["ink"], tokens["bg"]) >= MARKS for tokens in themes().values())

"""The pages: a day's public record (`basket.record.public_day`) as the index page, the method page and the
day's JSON, written into a site folder.

The index (the design's "What a visitor sees"): on a day that compares, the headline's figures as three
tiles; the headline's two lines, the revised line on a revised day (B12), the sentence on what a price here
is, the chains with their totals as bars, the item table, the notes and the credit line. The method page:
the rules in plain words, the basket, the stores left out, what the page does not claim, the law and how to
reproduce the number. Every page opens with a header band, the site's name (on the method page, the link
back) over the date line, and is one HTML file in English with one style block, no script, `noindex`, and
the credit line in its footer with the link to the method page. The words are `basket.words`', and the
tiles' labels are the headline's own: "Lowest listed total today", "Highest", and the gap as B9 defines it.

Look. One style block: colours as custom properties with a dark set for `prefers-color-scheme: dark`, the
system font stack, tabular figures in tables, a header band, cards, and the item table scrolling in its own
box on a narrow screen (its first column held in place) and its header row held at the top on a wide one.
The block has two parts: `BASE_STYLE`, the rules every page of this site and of the shopper site takes (the
colours and their dark set, the fonts, the body, links, the header band, sections, tables, the footer and the
phone's spacing), and `BASKET_STYLE`, the basket pages' own. The base rules are not the old block's first lines,
so both are cut from pieces kept in the old order, and `STYLE`, their join in that order, is the same bytes the
basket's pages carried before the split.

Order. Chains go by rank, the slug breaking a tie; a chain with no rank comes after those with one. Items
go in the basket's order.

Comparison. Only a day with a headline compares: the tiles; the bars, inline SVG starting at zero with the
highest total the full width, the chains ranked first (one, or several tied) marked "lowest"; the totals
row; and in each row whose item counts, the lowest price among the chains in the ranking marked "low"
(every chain at that price). Without a headline the chains and the table show no tiles, no totals, no bars
and no mark, and the item count in the headline is the table's rows; with one, it is the items that count.

A chain out of the ranking (B8) shows `too_few` in place of a bar; its prices are marked † and "out",
and a note says why.

Hebrew. A Hebrew name is wrapped whole in <span dir="rtl" lang="he"> (`HE_SPAN`), and so is every run of Hebrew in
a sentence (a store's name); the shopper site's check reads what such a span holds for markup only. In the shopper
site's frame (a `Frame` for the index page, a `page` for the method's parts) each store left out by rule is named
whole in that span, Latin letters and all ("שופרסל ONLINE"), since a chain's store name is the chain's text, not the
site's (its Call 11); the basket's own pages keep their bytes.

The shopper site's frame (`Frame`; the shopper plan's Task 18, its question M (c) and (d) and the second pre-flight's
S6). The shopper site shows the same index page as `basket.html` in its own frame: with a frame, the header band is
the frame's (the shopper site's name over its date line) and the basket's title opens the main part; the credit line is
the frame's, its link the frame's method link; a basket item whose product page the build has links to it
(`item_link`, None for no page); and the frame's note goes under the item table. Without a frame the page is the
basket's own, byte for byte as before. The method page's body is `method_parts`, the parts after its heading, so the
shopper site's method page carries the basket's method in a section of its own, the same parts in the same order.

Revisions. A revised day's public dict has `revised` ({"on": YYYY-MM-DD, "reason": text}) and `revisions`,
the earlier runs oldest first, each with `totals` by slug (None for a chain without one) and its own
`revised` (None for the first, the day as first published). The revised line names the latest revision,
then every earlier one, newest first, then the totals first published. A run kept in `revisions` without
a `revised` key (a day file written before the key was kept) adds no earlier revision.
"""
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html import escape as _escape
from pathlib import Path

from basket import words
from basket.basket_file import Basket
from basket.chains import EXCLUDED
from basket.record import money
from basket.rules import Headline, LeftOut
from basket.stores import Store

MARKER = ".basket-site"
HE_SPAN = '<span dir="rtl" lang="he">{}</span>'   # a Hebrew name, escaped (the module's docstring)
HEBREW = re.compile(r"[\u0590-\u05FF]+(?:[\s\d%'\".,()\-]+[\u0590-\u05FF]+)*")
# every page: the colours and their dark set, the fonts, the body, links, the header band, sections
_TOP = """\
:root {
  color-scheme: light dark;
  --bg: #f5f6f4; --surface: #ffffff; --surface-2: #f0f2ef; --hover: #f7f8f6;
  --border: #dde2de; --border-strong: #c3cac5; --axis: #9aa39d;
  --text: #151b17; --text-2: #3f4a43; --text-3: #58635c;
  --accent: #166534; --bar: #8b958f; --low-bg: #dcf3e3; --low-text: #0f4d27;
  --warn: #9a4a06; --warn-bg: #fdf3e7; --shadow: 0 1px 2px rgb(16 24 20 / 6%);
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 48px;
  --radius: 10px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1210; --surface: #151a17; --surface-2: #1c231f; --hover: #19201c;
    --border: #2b342f; --border-strong: #3d4842; --axis: #56615b;
    --text: #e7ebe8; --text-2: #b7c0ba; --text-3: #9aa59e;
    --accent: #5cc485; --bar: #6f7a74; --low-bg: #163a24; --low-text: #b5f0c9;
    --warn: #f0a45a; --warn-bg: #2a1f12; --shadow: 0 0 #0000;
  }
}
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 var(--font); }
.wrap, main { max-width: 67rem; margin: 0 auto; padding-left: var(--s4); padding-right: var(--s4); }
a { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
.band { background: var(--surface); border-top: 3px solid var(--accent); border-bottom: 1px solid var(--border); }
.band .wrap { padding-top: var(--s5); padding-bottom: var(--s5); }
.band h1, .band .wrap > a { display: inline-block; margin: 0; font-size: 1.25rem; font-weight: 700; line-height: 1.3;
                            letter-spacing: -0.01em; color: var(--text); }
.band .wrap > a { text-decoration: none; }
.band .wrap > a:hover { text-decoration: underline; }
.dateline { margin: var(--s1) 0 0; color: var(--text-3); font-size: .9375rem; }
main { padding-top: var(--s6); }
main > h1 { font-size: 1.75rem; line-height: 1.25; letter-spacing: -0.015em; margin: 0 0 var(--s3); }
h2 { font-size: 1.125rem; line-height: 1.35; margin: 0 0 var(--s4); }
p { margin: 0 0 var(--s3); }
main > p, main > section p, main > section ul { max-width: 46rem; }
main > section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                 box-shadow: var(--shadow); padding: var(--s5); margin: var(--s5) 0; }
main > section > :last-child { margin-bottom: 0; }
"""
# the basket's: the tiles, the headline, the revised line, the bars
_TILES_AND_BARS = """\
.tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--s4); margin: 0 0 var(--s5); }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
        box-shadow: var(--shadow); padding: var(--s4) var(--s5); }
.tile.lowest { box-shadow: inset 0 3px 0 var(--accent), var(--shadow); }
.tile dt { color: var(--text-3); font-size: .8125rem; font-weight: 600; }
.tile dd { margin: 0; color: var(--text-2); font-size: .9375rem; }
.tile dd.figure { margin: var(--s1) 0 var(--s1); color: var(--text); font-size: 2.25rem; font-weight: 650;
                  line-height: 1.15; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.headline { font-size: 1.25rem; font-weight: 600; line-height: 1.4; margin: 0 0 var(--s2); }
.headline + p { color: var(--text-2); }
.revised { border-left: 4px solid var(--warn); background: var(--warn-bg); padding: var(--s3) var(--s4);
           border-radius: 0 8px 8px 0; }
ol.bars, ol.rules { list-style: none; padding: 0; margin: 0; }
ol.bars li { display: grid; grid-template-columns: 1.5rem 9rem minmax(0, 1fr) 6.5rem;
             grid-template-areas: "rank name bar total" "rank note bar total"; column-gap: var(--s3);
             align-items: center; padding: var(--s2) 0; }
ol.bars li + li { border-top: 1px solid var(--border); }
.rank { grid-area: rank; align-self: start; color: var(--text-3); font-variant-numeric: tabular-nums; }
.name { grid-area: name; font-weight: 600; }
ol.bars .note { grid-area: note; color: var(--text-3); font-size: .8125rem; }
ol.bars svg { grid-area: bar; display: block; width: 100%; height: 14px; border-left: 1px solid var(--axis); }
.fill { fill: var(--bar); }
li.lowest .fill { fill: var(--accent); }
.total { grid-area: total; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
ol.bars li.out { grid-template-areas: "rank name name name" "rank note note note"; }
li.out .name { color: var(--text-3); }
"""
# every page: tables and their scrolling box
_TABLES = """\
.table { overflow-x: auto; }
table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: .875rem;
        font-variant-numeric: tabular-nums; }
th, td { text-align: left; vertical-align: top; padding: var(--s3); border-bottom: 1px solid var(--border); }
thead th { background: var(--surface-2); color: var(--text-2); font-size: .8125rem; font-weight: 600;
           vertical-align: bottom; border-bottom-color: var(--border-strong); }
th small, td small { display: block; margin-top: 2px; color: var(--text-3); font-size: .75rem; font-weight: 400;
                     line-height: 1.35; text-wrap: balance; }
tbody tr:hover > * { background: var(--hover); }
"""
# the basket's: the price and basket tables, the notes, the rules, the stores' details
_BASKET_TABLES = """\
table.prices { min-width: 44rem; }
table.prices thead th + th, table.prices td { text-align: right; }
table.prices td { font-size: .9375rem; font-weight: 600; }
table.prices thead th:first-child { width: 20%; }
table.prices th[scope="row"] { font-weight: 600; text-wrap: pretty; }
table.prices td { padding-left: var(--s2); padding-right: var(--s2); }
table.prices th[scope="row"] [lang="he"] { font-weight: 400; color: var(--text-2); }
table.prices tbody tr:hover > td.low, td.low { background: var(--low-bg); color: var(--low-text); font-weight: 700; }
.out, .left-out th, .left-out td { color: var(--text-3); }
tfoot th, tfoot td { border-top: 2px solid var(--border-strong); border-bottom: 0; font-weight: 700; }
table.basket { min-width: 40rem; }
table.basket td:first-child { color: var(--text-3); }
table.basket td:nth-child(4), table.basket th:nth-child(4) { text-align: right; padding-right: var(--s5); }
.notes ul, main > section ul { padding-left: 1.25rem; margin: 0 0 var(--s3); }
.notes li, main > section li { margin: 0 0 var(--s2); }
.notes li { color: var(--text-2); font-size: .9375rem; }
.lede { font-size: 1.0625rem; color: var(--text-2); }
ol.rules li { display: grid; grid-template-columns: 10rem minmax(0, 1fr); gap: var(--s4); margin: 0;
              padding: var(--s3) 0; border-top: 1px solid var(--border); }
ol.rules li:first-child { border-top: 0; padding-top: 0; }
ol.rules li > span { max-width: 46rem; color: var(--text-2); }
details { margin: 0 0 var(--s4); }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
details ul { columns: 3 13rem; column-gap: var(--s5); margin-top: var(--s2); font-size: .8125rem;
             color: var(--text-2); }
details li { break-inside: avoid; }
"""
# every page: the footer
_FOOTER = """\
footer { margin-top: var(--s7); background: var(--surface); border-top: 1px solid var(--border); color: var(--text-3);
         font-size: .8125rem; }
footer .wrap { padding-top: var(--s5); padding-bottom: var(--s6); }
footer p { max-width: 46rem; margin: 0; }
"""
# the basket's: the price table on wide and narrow screens
_BASKET_SCREENS = """\
@media (min-width: 50rem) {
  .table { overflow: visible; }
  table.prices thead th { position: sticky; top: 0; z-index: 1; }
}
@media (max-width: 49.99rem) {
  .table { margin: 0 calc(-1 * var(--s4)); }
  table.prices th[scope="row"], table.prices thead th:first-child {
    position: sticky; left: 0; z-index: 1; width: 9.5rem; background: var(--surface);
    box-shadow: 1px 0 0 var(--border); }
  table.prices thead th:first-child { background: var(--surface-2); }
  table.prices th:first-child { padding-left: var(--s4); }
}
"""
# every page, on a phone
_NARROW_BASE = """\
  main { padding-top: var(--s5); }
  main > section { padding: var(--s4); margin: var(--s4) 0; }
"""
# the basket's, on a phone
_NARROW_BASKET = """\
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s3); margin-bottom: var(--s4); }
  .tile { padding: var(--s3) var(--s4); }
  .tile.gap { grid-column: 1 / -1; }
  .tile dd.figure { font-size: 1.75rem; }
  .headline { font-size: 1.125rem; }
  ol.bars li { grid-template-columns: 1.5rem minmax(0, 1fr) auto;
               grid-template-areas: "rank name total" "rank bar bar" "rank note note"; row-gap: var(--s1); }
  ol.bars li.out { grid-template-areas: "rank name name" "rank note note"; }
  ol.rules li { grid-template-columns: minmax(0, 1fr); gap: var(--s1); }
"""
_NARROW = "@media (max-width: 37.5rem) {\n"
_END = "}\n"
BASE_STYLE = "\n" + _TOP + _TABLES + _FOOTER + _NARROW + _NARROW_BASE + _END      # every page of either site
BASKET_STYLE = _TILES_AND_BARS + _BASKET_TABLES + _BASKET_SCREENS + _NARROW + _NARROW_BASKET + _END   # the basket's own
# The two in the old block's order, so the basket's pages carry the same bytes as before the split.
STYLE = ("\n" + _TOP + _TILES_AND_BARS + _TABLES + _BASKET_TABLES + _FOOTER + _BASKET_SCREENS + _NARROW + _NARROW_BASE
         + _NARROW_BASKET + _END)


@dataclass(frozen=True)
class Frame:
    """The shopper site's frame for the index page (the module's docstring): `band` the header band as HTML, `credit`
    the credit line's text, `item_link` a basket item's page by barcode (None for no page), `method_href` where the
    method link goes, `note` a sentence under the item table ("" for none)."""
    band: str
    credit: str
    item_link: Callable[[str], str | None]
    method_href: str
    note: str = ""


def render_index(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]],
                 frame: Frame | None = None) -> str:
    """The index page of the day `public` holds; `exclusions` the stores each chain leaves out, by slug; in the shopper
    site's `frame` when one is given (the module's docstring)."""
    chains = _ordered(public["chains"])
    compare = public["headline"] is not None
    first, second = index_headline(public, basket)
    parts = [_tiles(_headline(public["headline"]))] if compare else []
    parts += [f'<p class="headline">{_prose(first)}</p>', f"<p>{_prose(second)}</p>"]
    if public["revised"]:
        parts.append(f'<p class="revised">{_prose(_revised(public))}</p>')
    parts.append(f'<p class="lede">{_prose(words.PRICES_SENTENCE)}</p>')
    parts.append(_bars(chains, compare))
    parts.append(_table(public, basket, chains, compare, frame))
    parts.append(_notes(public, basket, exclusions, chains, whole=frame is not None))
    if frame is None:
        return _page(_band(f"<h1>{_text(words.TITLE)}</h1>", public), words.TITLE, parts, _credit(public))
    credit = f'<p>{_prose(frame.credit)} <a href="{_escape(frame.method_href)}">{_text(words.METHOD_LINK)}</a></p>'
    return _page(frame.band, words.TITLE, [f"<h1>{_text(words.TITLE)}</h1>", *parts], credit)


def index_headline(public: dict, basket: Basket) -> tuple[str, str]:
    """The index page's two headline lines for the day `public` holds: the headline, or why there is none, and the
    items line."""
    headline = _headline(public["headline"])
    compare = headline is not None
    ranked = sum(chain["in_ranking"] for chain in public["chains"].values())
    count = len(public["items_in"]) if compare else len(basket.items)
    return words.headline_lines(headline, count, date.fromisoformat(public["day"]),
                                nothing_counted=ranked >= 3 and not public["items_in"])


def render_method(basket: Basket, exclusions: Mapping[str, Sequence[Store]], public: dict) -> str:
    """The method page: its heading, then `method_parts`."""
    parts = [f"<h1>{_text(words.METHOD_TITLE)}</h1>", *method_parts(basket, exclusions, public)]
    back = f'<a href="index.html">{_text(words.BACK_LINK)}</a>'
    return _page(_band(back, public), f"{words.METHOD_TITLE} · {words.TITLE}", parts, _credit(public))


def method_parts(basket: Basket, exclusions: Mapping[str, Sequence[Store]], public: dict,
                 page: str | None = None) -> list[str]:
    """The method page's body after its heading, as HTML parts: the intro, the rules, the basket, the stores left out,
    the claims not made, the law, reproducing. The shopper site's method page carries them in a section of its own and
    names the page they are about (`page`, "the basket page"), so "What this page does not claim" and "every number on
    the page" stay true there; None keeps the basket's own words."""
    day = date.fromisoformat(public["day"])
    rules = "".join(f"<li><b>{_text(name)}</b> <span>{_prose(text)}</span></li>" for name, text in words.RULES)
    not_claimed = "".join(f"<li>{_prose(line)}</li>" for line in words.NOT_CLAIMED)
    on = page or "the page"         # the page the day file's numbers are on
    return [f'<p class="lede">{_prose(words.METHOD_INTRO)}</p>',
            _section("<h2>The rules</h2>", f'<ol class="rules">{rules}</ol>'),
            _section('<h2 id="basket">The basket</h2>', f"<p>{_prose(words.basket_intro(basket))}</p>",
                     _basket_table(basket)),
            _section("<h2>Stores left out</h2>",
                     *(_excluded(slug, exclusions.get(slug, ()), whole=page is not None)
                       for slug in words.CHAIN_NAMES)),
            _section(f"<h2>What {_text(page or 'this page')} does not claim</h2>", f"<ul>{not_claimed}</ul>"),
            _section("<h2>The law</h2>", f"<p>{_prose(words.LAW)}</p>"),
            _section("<h2>To reproduce this number</h2>",
                     f"<p>{_prose(words.reproduce(day, public['basket_version'], public['code_sha'], on))}</p>",
                     _day_link(day))]


def render_day(public: dict) -> str:
    """The day's JSON: the public dict, keys sorted, Hebrew as written."""
    return json.dumps(public, sort_keys=True, indent=1, ensure_ascii=False)


def build_site(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]], site_dir: Path,
               write_day: bool) -> None:
    """Write `index.html`, `method.html`, `days/<day>.json` when `write_day` (else any day file is left as it
    is), and the empty marker file `.basket-site`."""
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(render_index(public, basket, exclusions), encoding="utf-8")
    (site_dir / "method.html").write_text(render_method(basket, exclusions, public), encoding="utf-8")
    if write_day:
        write_day_file(public, site_dir)
    (site_dir / MARKER).write_text("", encoding="utf-8")


def write_day_file(public: dict, site_dir: Path) -> None:
    """Write `days/<day>.json` under `site_dir`, the folders made as needed."""
    (site_dir / "days").mkdir(parents=True, exist_ok=True)
    (site_dir / "days" / f"{public['day']}.json").write_text(render_day(public), encoding="utf-8")


def _page(band: str, title: str, parts: Sequence[str], footer: str) -> str:
    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>{_text(title)}</title>
<style>{STYLE}</style>
</head>
<body>
{band}
<main>
{body}
</main>
<footer><div class="wrap">{footer}</div></footer>
</body>
</html>
"""


def _band(title: str, public: dict) -> str:
    """The header band every page opens with: the site's name (`title`, the index's <h1> or the method page's
    link back) and the date line."""
    line = words.files_of(date.fromisoformat(public["day"]))
    return f'<header class="band"><div class="wrap">{title}<p class="dateline">{_text(line)}</p></div></header>'


def _section(*parts: str) -> str:
    """A method page section: a card holding its heading and its parts."""
    return f"<section>{''.join(parts)}</section>"


def _tiles(headline: Headline) -> str:
    """The headline's figures as three tiles: the lowest listed total and its chain, the highest and its chain, the
    gap. Hidden from screen readers: the headline lines beneath say the same in words."""
    tiles = (("lowest", "Lowest listed total today", f"₪{money(headline.lowest_total)}",
              words.CHAIN_NAMES[headline.lowest]),
             ("highest", "Highest", f"₪{money(headline.highest_total)}", words.CHAIN_NAMES[headline.highest]),
             ("gap", "Gap", f"{headline.gap_percent}%", "(highest − lowest) ÷ lowest"))
    shown = "".join(f'<div class="tile {kind}"><dt>{_text(label)}</dt><dd class="figure">{_text(figure)}</dd>'
                    f"<dd>{_text(note)}</dd></div>" for kind, label, figure, note in tiles)
    return f'<dl class="tiles" aria-hidden="true">{shown}</dl>'


def _credit(public: dict) -> str:
    """The credit line with the link to the method page."""
    line = words.credit(date.fromisoformat(public["day"]), public["collected_by"])
    return f'<p>{_prose(line)} <a href="method.html">{_text(words.METHOD_LINK)}</a></p>'


def _text(text: str) -> str:
    """`text` escaped for a text node; quotes stay as written."""
    return _escape(text, quote=False)


def _he(text: str) -> str:
    return HE_SPAN.format(_text(text))


def _prose(text: str) -> str:
    """`text` as HTML: escaped, each run of Hebrew wrapped right to left."""
    out, end = [], 0
    for run in HEBREW.finditer(text):
        out += [_text(text[end:run.start()]), _he(run.group())]
        end = run.end()
    return "".join(out) + _text(text[end:])


def _prose_naming(text: str, names: Sequence[str]) -> str:
    """`text` as `_prose` writes it, but each of `names` quoted in it (“…”) wrapped whole (`_he`): the shopper site's
    frame (the module's docstring). With no names, `_prose`'s bytes."""
    if not names:
        return _prose(text)
    longest_first = sorted(set(names), key=len, reverse=True)
    quoted = re.compile("\u201c(" + "|".join(map(re.escape, longest_first)) + ")\u201d")
    out, end = [], 0
    for found in quoted.finditer(text):
        out += [_prose(text[end:found.start()]), "\u201c", _he(found.group(1)), "\u201d"]
        end = found.end()
    return "".join(out) + _prose(text[end:])


def _named(slug: str, stores: Sequence[Store], whole: bool) -> list[str]:
    """The names of the chain's stores left out by number, which its lines quote, when they are to be wrapped whole."""
    return [store.name for store in stores if store.id in EXCLUDED[slug].stores] if whole else []


def _ordered(chains: dict) -> list[tuple[str, dict]]:
    return sorted(chains.items(), key=lambda pair: (pair[1]["rank"] is None, pair[1]["rank"] or 0, pair[0]))


def _headline(found: dict | None) -> Headline | None:
    if found is None:
        return None
    return Headline(found["lowest"], Decimal(found["lowest_total"]), found["highest"], Decimal(found["highest_total"]),
                    found["gap_percent"])


def _revised(public: dict) -> str:
    revised = public["revised"]
    first = public["revisions"][0]["totals"] if public["revisions"] else {}
    earlier = [(date.fromisoformat(run["revised"]["on"]), run["revised"]["reason"])
               for run in reversed(public["revisions"]) if run.get("revised")]
    return words.revised_line(date.fromisoformat(revised["on"]), revised["reason"], first, earlier)


def _bars(chains: list[tuple[str, dict]], compare: bool) -> str:
    """Each chain's line: its rank, total and bar on a day that compares; `too_few` for a chain out of the ranking."""
    highest = max(Decimal(chain["total"]) for _, chain in chains if chain["total"] is not None) if compare else None
    rows = []
    for slug, chain in chains:
        name = f'<span class="name">{_text(words.CHAIN_NAMES[slug])}</span>'
        label = f'<span class="note">{_text(words.bar_label(chain["with_file"]))}</span>'
        if not chain["in_ranking"]:
            few = words.too_few(chain["with_file"], chain["included"])
            line = f'<span class="rank"></span>{name}<span class="note">{_text(few)}</span>'
        elif compare:
            width = Decimal(chain["total"]) * 100 / highest
            line = (f'<span class="rank">{chain["rank"]}</span>{name}'
                    f'<svg width="100%" height="14" aria-hidden="true">'
                    f'<rect class="fill" width="{width:.2f}%" height="14" rx="4"/>'
                    f'<rect class="fill" width="4" height="14"/></svg>'  # squares the end at zero
                    f'<span class="total">₪{chain["total"]}</span>{label}')
        else:
            line = f'<span class="rank"></span>{name}{label}'
        kind = "out" if not chain["in_ranking"] else "lowest" if compare and chain["rank"] == 1 else None
        attributes = f' class="{kind}"' if kind else ""
        rows.append(f'<li data-chain="{slug}"{attributes}>{line}</li>')
    heading = "Listed totals, lowest first" if compare else "The chains' files"
    return f'<section><h2>{heading}</h2><ol class="bars">{"".join(rows)}</ol></section>'


def _lowest(code: str, public: dict, chains: list[tuple[str, dict]], compare: bool) -> set[str]:
    """The chains to mark in an item's row: those at its lowest price among the chains in the ranking."""
    if not compare or code not in public["items_in"]:
        return set()
    prices = {slug: Decimal(chain["items"][code]["median"]) for slug, chain in chains
              if chain["in_ranking"] and code in chain["items"]}
    lowest = min(prices.values())
    return {slug for slug, price in prices.items() if price == lowest}


def _table(public: dict, basket: Basket, chains: list[tuple[str, dict]], compare: bool, frame: Frame | None) -> str:
    """One row per basket item, one column per chain: its price and, beneath, its stores' range; in a frame, an item's
    name linked to its page when it has one, and the frame's note under the table."""
    head = "".join(f'<th scope="col" class="out">{_text(words.CHAIN_NAMES[slug])} †</th>' if not chain["in_ranking"]
                   else f'<th scope="col">{_text(words.CHAIN_NAMES[slug])}</th>' for slug, chain in chains)
    rows = []
    for item in basket.items:
        counts = item.code in public["items_in"]
        low = _lowest(item.code, public, chains, compare)
        found = []
        for slug, chain in chains:
            classes = " ".join(name for name, on in (("low", slug in low), ("out", not chain["in_ranking"])) if on)
            attributes = f' class="{classes}"' if classes else ""
            price = chain["items"].get(item.code)
            if price is None:
                found.append(f'<td data-chain="{slug}"{attributes}>not listed</td>')
                continue
            mark = " †" if not chain["in_ranking"] else ""
            note = words.range_note(price["low"], price["high"], price["listing"], chain["with_file"])
            found.append(f'<td data-chain="{slug}"{attributes}>₪{price["median"]}{mark}<small>{_text(note)}</small></td>')
        name = _text(item.name_en)
        href = None if frame is None else frame.item_link(item.code)
        if href is not None:
            name = f'<a href="{_escape(href)}">{name}</a>'
        label = (f"{name}<br>{_he(item.name_he)}<small>{_text(words.size_text(item.size))} · "
                 f"{item.code}</small>" + ("" if counts else "<small>left out today</small>"))
        row_class = "" if counts else ' class="left-out"'
        rows.append(f'<tr data-code="{item.code}"{row_class}><th scope="row">{label}</th>{"".join(found)}</tr>')
    foot = ""
    if compare:
        totals = "".join(f'<td>₪{chain["total"]}</td>' if chain["total"] is not None else "<td>none</td>"
                         for _, chain in chains)
        foot = f'<tfoot><tr><th scope="row">Total of the items that count</th>{totals}</tr></tfoot>'
    note = f"<p>{_prose(frame.note)}</p>" if frame is not None and frame.note else ""
    return (f'<section><h2 id="prices">Listed prices by item</h2>{_scroller("prices")}<table class="prices">'
            f'<thead><tr><th scope="col">Item</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody>{foot}</table></div>'
            f"{note}</section>")


def _notes(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]],
           chains: list[tuple[str, dict]], whole: bool = False) -> str:
    """The items left out and why, chains out of the ranking, the stores each chain rests on, the median sentence;
    `whole` names each store left out by number whole (the shopper site's frame)."""
    lines = [words.left_out_line(LeftOut(**each), basket) for each in public["left_out"]] or [words.NOTHING_LEFT_OUT]
    lines += [words.out_note(slug, chain["with_file"], chain["included"]) for slug, chain in chains
              if not chain["in_ranking"]]
    shown = [_prose(line) for line in lines]
    shown += [_prose_naming(words.stores_line(slug, chain["included"], chain["with_file"], exclusions.get(slug, ())),
                            _named(slug, exclusions.get(slug, ()), whole)) for slug, chain in chains]
    double_coded = words.double_coded_line({slug: sum(price["double_coded"] for price in chain["items"].values())
                                            for slug, chain in chains})
    shown += [_prose(line) for line in ([double_coded] if double_coded else [])]
    shown.append(_prose(words.MEDIAN_SENTENCE))
    items = "".join(f"<li>{line}</li>" for line in shown)
    return (f'<section class="notes"><h2>Notes</h2><ul>{items}</ul>'
            f"{_day_link(date.fromisoformat(public['day']))}</section>")


def _scroller(heading: str) -> str:
    """The box a wide table scrolls in on a narrow screen, named by its section's heading and reachable by
    keyboard, so the table can be scrolled without a pointer."""
    return f'<div class="table" tabindex="0" role="region" aria-labelledby="{heading}">'


def _day_link(day: date) -> str:
    path = f"days/{day.isoformat()}.json"
    return f'<p>The day\'s numbers as data: <a href="{path}">{path}</a>.</p>'


def _basket_table(basket: Basket) -> str:
    rows = "".join(f"<tr><td>{item.code}</td><td>{_text(item.name_en)}</td><td>{_he(item.name_he)}</td>"
                   f"<td>{_text(words.size_text(item.size))}</td><td>{_text(item.category)}</td></tr>"
                   for item in basket.items)
    return (f'{_scroller("basket")}<table class="basket"><thead><tr><th scope="col">Barcode</th>'
            f'<th scope="col">Name</th><th scope="col">Hebrew name</th><th scope="col">Size</th>'
            f'<th scope="col">Category</th></tr></thead><tbody>{rows}</tbody></table></div>')


def _excluded(slug: str, stores: Sequence[Store], whole: bool = False) -> str:
    """A chain's stores left out (B2), and the names of those left out with their sub-chain; `whole` names each store
    left out by number whole (the shopper site's frame)."""
    line = f"<p>{_prose_naming(words.excluded_line(slug, stores), _named(slug, stores, whole))}</p>"
    grouped = [store for store in stores if store.id not in EXCLUDED[slug].stores]
    if not grouped:
        return line
    names = "".join(f"<li>store {_text(store.id)} {_he(store.name)}</li>" for store in grouped)
    return f"{line}<details><summary>The {len(grouped)} stores by name</summary><ul>{names}</ul></details>"

"""The pages: a day's public record (`basket.record.public_day`) as the index page, the method page and the
day's JSON, written into a site folder.

The index (the design's "What a visitor sees"): the headline's two lines, the revised line on a revised
day (B12), the sentence on what a price here is, the chains with their totals as bars, the item table, the
notes and the credit line. The method page: the rules in plain words, the basket, the stores left out,
what the page does not claim, the law and how to reproduce the number. Every page is one HTML file in
English with one style block, no script, `noindex`, and the credit line in its footer with the link to the
method page. The words are `basket.words`'.

Order. Chains go by rank, the slug breaking a tie; a chain with no rank comes after those with one. Items
go in the basket's order.

Comparison. Only a day with a headline compares: the bars, inline SVG with the highest total the full
width; the totals row; and in each row whose item counts, the lowest price among the chains in the
ranking marked "low" (every chain at that price). Without a headline the chains and the table show no
totals, no bars and no mark, and the item count in the headline is the table's rows; with one, it is the
items that count.

A chain out of the ranking (B8) shows `too_few` in place of a bar; its prices are marked † and "out",
and a note says why.

Hebrew. A Hebrew name is wrapped whole in <span dir="rtl" lang="he">, and so is every run of Hebrew in a
sentence (a store's name).

Revisions. A revised day's public dict has `revised` ({"on": YYYY-MM-DD, "reason": text}) and `revisions`,
the earlier runs oldest first, each with `totals` by slug (None for a chain without one) and its own
`revised` (None for the first, the day as first published). The revised line names the latest revision,
then every earlier one, newest first, then the totals first published. A run kept in `revisions` without
a `revised` key (a day file written before the key was kept) adds no earlier revision.
"""
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from html import escape as _escape
from pathlib import Path

from basket import words
from basket.basket_file import Basket
from basket.chains import EXCLUDED
from basket.rules import Headline, LeftOut
from basket.stores import Store

MARKER = ".basket-site"
HEBREW = re.compile(r"[\u0590-\u05FF]+(?:[\s\d%'\".,()\-]+[\u0590-\u05FF]+)*")
STYLE = """
body { margin: 0 auto; max-width: 52rem; padding: 0 16px 2rem; font: 16px/1.5 system-ui, sans-serif;
       color: #1a1a1a; background: #fff; }
h1 { font-size: 1.6rem; margin: 1.5rem 0 .5rem; }
h2 { font-size: 1.2rem; margin-top: 2rem; }
.headline { font-size: 1.25rem; font-weight: 600; margin: .25rem 0; }
.revised { border-left: 4px solid #b45309; padding-left: .75rem; }
ol.bars, ol.rules { list-style: none; padding: 0; }
ol.bars li { display: flex; flex-wrap: wrap; align-items: center; gap: .25rem .5rem; margin: .5rem 0; }
.rank { width: 1.25rem; }
.name { width: 6.5rem; }
ol.bars svg { flex: 1 1 8rem; height: .9rem; }
.fill { fill: #2563eb; }
.total { font-weight: 600; }
.note, small { color: #555; font-size: .8rem; }
ol.bars .note { flex-basis: 100%; padding-left: 1.75rem; }
.table { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; vertical-align: top; padding: .4rem; border-bottom: 1px solid #ddd; }
th small, td small { display: block; }
td.low { background: #dcfce7; font-weight: 600; }
.out, .left-out th { color: #6b7280; }
footer { margin-top: 3rem; border-top: 1px solid #ddd; padding-top: 1rem; font-size: .85rem; color: #444; }
"""


def render_index(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]]) -> str:
    """The index page of the day `public` holds; `exclusions` the stores each chain leaves out, by slug."""
    chains = _ordered(public["chains"])
    compare = public["headline"] is not None
    first, second = index_headline(public, basket)
    parts = [f"<h1>{_text(words.TITLE)}</h1>", f'<p class="headline">{_prose(first)}</p>', f"<p>{_prose(second)}</p>"]
    if public["revised"]:
        parts.append(f'<p class="revised">{_prose(_revised(public))}</p>')
    parts.append(f"<p>{_prose(words.PRICES_SENTENCE)}</p>")
    parts.append(_bars(chains, compare))
    parts.append(_table(public, basket, chains, compare))
    parts.append(_notes(public, basket, exclusions, chains))
    return _page(words.TITLE, parts, _credit(public))


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
    """The method page: the rules, the basket, the stores left out, the claims not made, the law, reproducing."""
    day = date.fromisoformat(public["day"])
    rules = "".join(f"<li><b>{_text(name)}</b> {_prose(text)}</li>" for name, text in words.RULES)
    not_claimed = "".join(f"<li>{_prose(line)}</li>" for line in words.NOT_CLAIMED)
    parts = [f'<p><a href="index.html">{_text(words.BACK_LINK)}</a></p>', f"<h1>{_text(words.METHOD_TITLE)}</h1>",
             f"<p>{_prose(words.METHOD_INTRO)}</p>",
             "<h2>The rules</h2>", f'<ol class="rules">{rules}</ol>',
             "<h2>The basket</h2>", f"<p>{_prose(words.basket_intro(basket))}</p>", _basket_table(basket),
             "<h2>Stores left out</h2>", *(_excluded(slug, exclusions.get(slug, ())) for slug in words.CHAIN_NAMES),
             "<h2>What this page does not claim</h2>", f"<ul>{not_claimed}</ul>",
             "<h2>The law</h2>", f"<p>{_prose(words.LAW)}</p>",
             "<h2>To reproduce this number</h2>",
             f"<p>{_prose(words.reproduce(day, public['basket_version'], public['code_sha']))}</p>", _day_link(day)]
    return _page(f"{words.METHOD_TITLE} · {words.TITLE}", parts, _credit(public))


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
        (site_dir / "days").mkdir(exist_ok=True)
        (site_dir / "days" / f"{public['day']}.json").write_text(render_day(public), encoding="utf-8")
    (site_dir / MARKER).write_text("", encoding="utf-8")


def _page(title: str, parts: Sequence[str], footer: str) -> str:
    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{_text(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
{body}
</main>
<footer>{footer}</footer>
</body>
</html>
"""


def _credit(public: dict) -> str:
    """The credit line with the link to the method page."""
    line = words.credit(date.fromisoformat(public["day"]), public["collected_by"])
    return f'<p>{_prose(line)} <a href="method.html">{_text(words.METHOD_LINK)}</a></p>'


def _text(text: str) -> str:
    """`text` escaped for a text node; quotes stay as written."""
    return _escape(text, quote=False)


def _he(text: str) -> str:
    return f'<span dir="rtl" lang="he">{_text(text)}</span>'


def _prose(text: str) -> str:
    """`text` as HTML: escaped, each run of Hebrew wrapped right to left."""
    out, end = [], 0
    for run in HEBREW.finditer(text):
        out += [_text(text[end:run.start()]), _he(run.group())]
        end = run.end()
    return "".join(out) + _text(text[end:])


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
                    f'<svg viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">'
                    f'<rect class="fill" width="{width:.2f}" height="10"/></svg>'
                    f'<span class="total">₪{chain["total"]}</span>{label}')
        else:
            line = f'<span class="rank"></span>{name}{label}'
        rows.append(f'<li data-chain="{slug}">{line}</li>')
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


def _table(public: dict, basket: Basket, chains: list[tuple[str, dict]], compare: bool) -> str:
    """One row per basket item, one column per chain: its price and, beneath, its stores' range."""
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
        label = (f"{_text(item.name_en)}<br>{_he(item.name_he)}<small>{_text(words.size_text(item.size))} · "
                 f"{item.code}</small>" + ("" if counts else "<small>left out today</small>"))
        row_class = "" if counts else ' class="left-out"'
        rows.append(f'<tr data-code="{item.code}"{row_class}><th scope="row">{label}</th>{"".join(found)}</tr>')
    foot = ""
    if compare:
        totals = "".join(f'<td>₪{chain["total"]}</td>' if chain["total"] is not None else "<td>none</td>"
                         for _, chain in chains)
        foot = f'<tfoot><tr><th scope="row">Total of the items that count</th>{totals}</tr></tfoot>'
    return (f'<section><h2>Listed prices by item</h2><div class="table"><table class="prices"><thead><tr>'
            f'<th scope="col">Item</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody>{foot}</table></div></section>')


def _notes(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]],
           chains: list[tuple[str, dict]]) -> str:
    """The items left out and why, chains out of the ranking, the stores each chain rests on, the median sentence."""
    lines = [words.left_out_line(LeftOut(**each), basket) for each in public["left_out"]] or [words.NOTHING_LEFT_OUT]
    lines += [words.out_note(slug, chain["with_file"], chain["included"]) for slug, chain in chains
              if not chain["in_ranking"]]
    lines += [words.stores_line(slug, chain["included"], chain["with_file"], exclusions.get(slug, ()))
              for slug, chain in chains]
    double_coded = words.double_coded_line({slug: sum(price["double_coded"] for price in chain["items"].values())
                                            for slug, chain in chains})
    if double_coded:
        lines.append(double_coded)
    lines.append(words.MEDIAN_SENTENCE)
    items = "".join(f"<li>{_prose(line)}</li>" for line in lines)
    return (f'<section class="notes"><h2>Notes</h2><ul>{items}</ul>'
            f"{_day_link(date.fromisoformat(public['day']))}</section>")


def _day_link(day: date) -> str:
    path = f"days/{day.isoformat()}.json"
    return f'<p>The day\'s numbers as data: <a href="{path}">{path}</a>.</p>'


def _basket_table(basket: Basket) -> str:
    rows = "".join(f"<tr><td>{item.code}</td><td>{_text(item.name_en)}</td><td>{_he(item.name_he)}</td>"
                   f"<td>{_text(words.size_text(item.size))}</td><td>{_text(item.category)}</td></tr>"
                   for item in basket.items)
    return (f'<div class="table"><table class="basket"><thead><tr><th scope="col">Barcode</th>'
            f'<th scope="col">Name</th><th scope="col">Hebrew name</th><th scope="col">Size</th>'
            f'<th scope="col">Category</th></tr></thead><tbody>{rows}</tbody></table></div>')


def _excluded(slug: str, stores: Sequence[Store]) -> str:
    """A chain's stores left out (B2), and the names of those left out with their sub-chain."""
    line = f"<p>{_prose(words.excluded_line(slug, stores))}</p>"
    grouped = [store for store in stores if store.id not in EXCLUDED[slug].stores]
    if not grouped:
        return line
    names = "".join(f"<li>store {_text(store.id)} {_he(store.name)}</li>" for store in grouped)
    return f"{line}<details><summary>The {len(grouped)} stores by name</summary><ul>{names}</ul></details>"

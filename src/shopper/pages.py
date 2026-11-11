"""The root, the store types' front pages, and the method, record and basket pages (docs/shopper-site.md, "What a
visitor sees" 1, 4, 5 and 6, P1 to P10, F1 to F11, "Words" and Q1 to Q4, with "Changed after the survey", S1 and "The
column"; the plan's Task 18, its questions A, K, M (c), (d) and (f) and O, and the second pre-flight's S1, S6 and S13;
docs/store-first.md, "What a visitor sees" 1, 3 and 4, and the store-first plan's Task 5). Every page is on the
site's shared shell (`shopper.shell`: the band with the site's name, the pick link and the date line, `noindex`, the
base style, the one script, the credit line); every chain-supplied text (a product's name, a programme's, a store's) is
escaped inside `CHAIN_SPAN`.

The root page, `index.html`, also the portfolio's landing page: the title question (`shopper.words.FRONT_TITLE`), one
line on what the site does (ROOT_LINE), the picker, then the hiring line (question M (f)). The picker is
`<section id="pick" data-page="root">`, the pick link's target and search.js's mark for the root (it sends a remembered
pick on to its store type's front page unless the hash is #pick, which is how the header's "change" reaches the picker
instead): "Which store are you in?" (PICK_TITLE), then each chain's name over a link to each of its store types' front
pages (`store_path`), in the design's order by chain (PICK_GROUPS), never COLUMNS' order by name. The root shows no
price, so it carries no ALWAYS phrase, and `shopper.check` holds it to none.

A store type's front page, `store/<key>.html` (`store_path`), one folder down (UP), with its main part marked
`data-store` (`shopper.shell.page`), from which search.js sets the pick. Until the store-first plan's Task 6
replaces it, its content is the old front page's for its column alone, under the old rule. Top to bottom, in the
owner's plain words (2026-11-10): the store type's name over the title, the owner's question; the line under it
(`shopper.words.FRONT_SUBTITLE`), what each promotion is checked against; the search box, `<input id="q">`, and a link
to the browse pages, which need no script; the lead line (`shopper.words.lead_line`), how many of the column's products
passed, its "None yet" form while the column has no record on MIN_FRONT_DAYS of the RECENT_DAYS before the day
(`column_ready`: a product's days of records at a column are days the column has one, so none can pass the front
test's days before then); the filters, CSS only: two checkboxes, the club-only one (hiding every restricted promotion,
question K) and the minimum-spend one, each ruled by a `:checked` sibling selector over the rows' `data-club` and
`data-spend`, and no store radio, since the page is one store type's; the table, the column's rows, each: the
product's link with its name, the column (its "Store"), the deal price per unit or kilogram with "buy N", the column's
30-day median listed price (its "Typical price"), the depth as a whole percent worked from the figures shown
(`shopper.words.shown_below`, as P7's first sentence works it; "under 1%" for a gap that rounds to 0%), and the
conditions with their source and the fine print label; directly under the table, one note saying what "Typical price"
and "Below by" are and carrying the four ALWAYS phrases, so the page carries them on a morning with no row too; a
fold-out, `<details>`, closed, needing no script: every condition `shopper.measures.on_front` applies, in the store
format's words (question O), as required, not as enough on their own (the review round, 2026-11-10), and that both
windows count only days with records; what the two filters hide and the chains whose files mark no restricted promotion
today (`shopper.words.marked_none`), the day's promotions and products, the site's whole until Task 6
(`shopper.words.promotions_line`), and the method page; the top row's P7 sentences as one deal's story. Every link
leads up to the site's root.

The rows (question A under S1). A row is a (column, product): `front_rows_of` gives at most one per column, in name
order, the product's lowest deal there, compared exactly, among its promotions running today (P3, read as the product
pages read them, `shopper.product.running_today`) that pass the front page's test (`shopper.measures.on_front`: listed
across the column, the price read, a record at the column today, at least 20 days of records in the 30 before today,
the deal as shown below every listed price of the 90 as shown). So a product can have a row on each of four Shufersal
store pages, each against its own column's median; a column with no record today (a hole, S1) has none. `ordered` sorts
the rows by the depth they show, a whole percent ("under 1%" as 0), deepest first, a row with no shown gap last, then
by the exact depth (`shopper.measures.depth`), then by column in name order, then by barcode as a number. A row keeps
the promotion's restrictions, programmes and minimum spend for its conditions and the filters. `Counts` holds the
site-day file's three numbers (the build counts them): the wide promotions listed today, distinct by chain and id, their
barcodes, and the barcodes with a front row.

The method page: what a column is and the nine, with how each one's stores are chosen and how many the day's store list
includes; the stores left out by rule, which of them sit in a column's part of the store list, and store 779 (Task 15's
carry: ALWAYS_SENTENCE says this page gives the rules); Carrefour's table, store by store, and how it was drawn; the
included stores in no column, chain by chain, each by id and its listed name (with its sub-chain where the columns go by
sub-chain); any column under the floor that day; P1 to P10 and F1 to F11 in plain words with the code's own constants;
the NEVER list as `<ul id="never-words">`, the only place its phrases appear; what is measured and what is inferred; the
law; how to reproduce a page; and the headline basket's method, `basket.page.method_parts` byte for byte, in a section
whose id (`BASKET_SECTION`) is not its inner heading's (S6).

The record page: `scorecard_section`, a function of the scorecard alone, so the guard can render it again from the
site-day file (Task 21): how many columns are tested at once, the model versions scored so far (the scorecard's
`versions_tried`, which counts the versions with a scored day: Task 14's carry), the version in force and the
bootstrap's numbers; "No forecast has been scored yet." before any scored day; then per column its gate, closed (an
open gate stops the page: step one shows no odds), its three conditions and whether each holds, with the reasons; and
per model version the whole and each month (the days on time and late, the scored days, the forecasts, scored and
unscored, the outcome-1 share; the three Brier scores, the model's less each baseline's and the two skills, each with
its 95% interval or "too few days"), the calibration as a table and an inline chart, and a sentence for each bin
holding 1% or more of the version's scored forecasts (`shopper.record.holds_share`). The scorecard has no
column-pooled block to show. After it: "Promotion fine print is not read yet."; the days the ledger names as frozen,
on time (`shopper.freeze.on_time`) and late, the days since the first with no forecasts file, and where the record
starts (the first day frozen on time, F6); every forecasts and scores file and the ledger, linked as test records, not
advice; and the days read with each column's days short of price files, of promotion files, or with no table.

The basket page, `basket.html` (question M (c), (d)): the basket's index page (`basket.page.render_index`) in the site's
frame: the site's band and credit line, an item linked to its product page only when the build has that page, and
`formats_note()` under its table, since the basket keeps each chain's median (the amendment). Never ALWAYS_SENTENCE,
which is the product pages'.

Words. The sentences are `shopper.words`' and `basket.words`', and the method and record pages' own below; they state
no more than the figures shown and the records support. Every page is a pure function of its inputs: the same bytes
whatever order the rows, mappings or files come in.
"""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from html import escape

from basket.barcode import normalize
from basket.basket_file import Basket
from basket.chains import EXCLUDED, SLUGS
from basket.page import BASKET_STYLE, Frame, method_parts, render_index
from basket.record import money
from basket.stores import Store
from basket.words import CHAIN_NAMES, TITLE as BASKET_TITLE, joined
from shopper.columns import BY_KEY, COLUMNS, FIXED_ON, FLOOR, FORMATS_ON_FIXED_DAY, column_of, columns_of
from shopper.deals import Deal, deal_from_row
from shopper.forecast import A_MIN_DAYS, DAYS_SINCE_CAP, FIRST_RECORD_DAY, MAX_HOLES, MODEL_VERSION, N0, TARGET_VERSION
from shopper.freeze import on_time
from shopper.history import ENOUGH, READ_DAYS, ColumnDay, Pair
from shopper.items import HORIZON, by_number
from shopper.measures import MIN_FRONT_DAYS, RECENT_DAYS, Gap, depth, gap, on_front, whole
from shopper.product import CHAIN_SPAN, field_conditions, page_path, running_today
from shopper.record import BIN_OFF, BIN_SHARE, BLOCK, CAL_MAX, DRAWS, GATE_DAYS, LEVEL, MIN_DAYS, SEED, holds_share
from shopper.shell import SCRIPT_TAG, band, page, text
from shopper.words import (BROWSE_LINK, FINE_PRINT, FRONT_SUBTITLE, FRONT_TITLE, GAP_HEADING, HIRING, METHOD_TITLE,
                           MORNING, NEVER, NUMBER_WORDS, RECORD_TITLE, SITE_NAME, buy, columns_tested, credit,
                           date_range, deal_price, formats_note, gap_sentences, lead_line, marked_none, no_odds_yet,
                           percent_text, promotions_line, shown_below, unreadable)

BASKET_SECTION = "headline-basket"     # the basket's method on the method page: not its inner heading's id, "basket"
BASKET_PAGE = "the basket page"        # what the basket's method section speaks of on the method page
GITHUB = HIRING[-1][1]
# The root's own words (store first, q33; provisional until the owner's read): the picker's title is the design's
PICK_TITLE = "Which store are you in?"
ROOT_LINE = ("Pick the store you're in, then look up a product: each sale is checked against what it usually costs "
             "there.")
# The picker's store types by chain, in the design's order ("What a visitor sees" 1), never COLUMNS' (by name)
PICK_GROUPS = (("shufersal", ("shufersal-deal", "shufersal-express", "shufersal-sheli", "shufersal-universe")),
               ("carrefour", ("carrefour-city", "carrefour-market")), ("ramilevy", ("ramilevy",)),
               ("osherad", ("osherad",)), ("yochananof", ("yochananof",)))
UP = "../"                  # a store type's front page, store/<key>.html, to the site's root
# The store pages' own words (the owner's plain words, 2026-11-10): plain labels; the rule in full in the fold-out
SEARCH_LABEL = "Find a product: name or barcode"
CLUB_FILTER = "Hide club-only deals"
SPEND_FILTER = "Hide deals with a minimum spend"
NO_DEALS = "No deals to show."                 # the lead line above says why
FRONT_HEADS = ("Product", "Store", "Deal", "Typical price", "Below by", "Conditions")
TABLE_NOTE = (f"Typical price: the {RECENT_DAYS}-day median listed price before promotions, as listed in the chain's "
              "price files. Below by: how far the deal is under the typical price. "
              f"Deals {MORNING}.")                             # the four ALWAYS phrases, under the table
RULES_TITLE = "How a deal passes"
# required, not enough on their own (the review round, 2026-11-10): the shown figures' rounding, a deal price above
# ₪0.01 (P4), one row per format's lowest deal
RULES_INTRO = "A deal passes only when all of these are true at the store format in its row:"
# every condition `shopper.measures.on_front` applies: the deal as shown below every listed price of the 90 as shown;
# the promotion wide; the column's day no hole; the deal price read; the 30-day window's days
FRONT_RULES = (
    f"Its deal price is below every listed price the product had at that store format in the {READ_DAYS} days before "
    "today.",
    "At least half of the format's stores that sent price files today carry the promotion.",
    "At least half of the format's stores sent price files today.",
    "Its deal price could be read.",
    f"The product had a listed price there on at least {MIN_FRONT_DAYS} of the {RECENT_DAYS} days before today.")
# both windows count only the column's days with a record (`shopper.history.counted`, read by `window` and so by
# `on_front`; `front_ready` too): the owner's "with records" of the old rule line, in plain words
WINDOWS_NOTE = (f"The {READ_DAYS} days and the {RECENT_DAYS} days count only days when at least half of the format's "
                "stores sent price files.")
CLUB_NOTE = (f'"{CLUB_FILTER}" hides the deals the chains\' fields mark for club members, the chain\'s card holders or '
             "some customers only.")                         # question K: every restricted promotion, `data-club`
SPEND_NOTE = f'"{SPEND_FILTER}" hides the deals whose fields give a minimum spend.'    # `min_spend`, the fields' alone
RULES_LINK = f"All the rules: {METHOD_TITLE}"
# The record page's own words
FINE_PRINT_UNREAD = "Promotion fine print is not read yet."
NOTHING_SCORED = "No forecast has been scored yet."
COLUMN_NOTHING_SCORED = "No forecast of this column has been scored yet."
GATE_CLOSED = "Gate: closed."
_BIN_SHARE = whole(100 * Fraction(BIN_SHARE))   # 1: the share of the scored forecasts a checked bin holds, in percent
CONDITIONS = {
    "days": f"At least {GATE_DAYS} scored days of the version in force, each frozen on time",
    "brier": f"The model's Brier score below both baselines', each difference's {LEVEL}% interval wholly below zero",
    "calibration": (f"A calibration error of at most {CAL_MAX}, with no bin holding {_BIN_SHARE}% or more of the "
                    f"scored forecasts off by more than {BIN_OFF}"),
}
TOO_FEW = "too few days"
SCORED_SO_FAR = ("Each column's tables below count only the days whose forecasts file has been scored so far: a "
                 f"day's file is scored {HORIZON} days after it is frozen (the days frozen are counted further down).")
FILES_LABEL = ("These files are this site's test records of its forecasts, published so that anyone can check them; "
               "they are not advice.")
# The method page: Shufersal's formats in no column on the fixed day, named where the design names them
FORMAT_NAMES = {"shufersal": {"6": "Yesh Chesed"}}
FOUR = 4                    # the digits of a figure on the record page
PAGE_STYLE = """
section h3 { font-size: 1rem; margin: var(--s4) 0 var(--s2); }
section small { display: block; color: var(--text-3); font-size: .8125rem; }
.lede { font-size: 1.0625rem; color: var(--text-2); }
"""
ROOT_STYLE = PAGE_STYLE + """
#pick h3 { color: var(--text-2); }
#pick ul { list-style: none; padding: 0; margin: 0 0 var(--s3); display: flex; flex-wrap: wrap; gap: var(--s2); }
#pick li a { display: inline-block; padding: var(--s2) var(--s3); border: 1px solid var(--border-strong);
             border-radius: var(--radius); background: var(--surface); font-weight: 600; text-decoration: none; }
.hiring { margin-top: var(--s5); }
"""
STORE_STYLE = PAGE_STYLE + """
.at { margin: 0; color: var(--accent); font-weight: 600; }
.sub { color: var(--text-3); }
.search label { display: block; font-weight: 600; margin-bottom: var(--s2); }
.search input { width: 100%; max-width: 32rem; font: inherit; padding: var(--s2) var(--s3); border-radius: 6px;
                border: 1px solid var(--border-strong); background: var(--surface); color: var(--text); }
.deals > input { margin: 0 var(--s1) var(--s3) 0; }
.deals > label { margin-right: var(--s4); }
.deals .note { margin: var(--s3) 0 0; color: var(--text-2); font-size: .9375rem; }
.deals details { margin: var(--s4) 0 0; }
.deals summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.deals details ul { padding-left: 1.25rem; margin: var(--s3) 0; }
.deals details li { margin: 0 0 var(--s2); }
table.front { min-width: 52rem; }
.story-head { font-weight: 600; }
#f-club:checked ~ .table tbody tr[data-club] { display: none; }
#f-spend:checked ~ .table tbody tr[data-spend] { display: none; }
"""
METHOD_STYLE = PAGE_STYLE + f"""
#{BASKET_SECTION} > section {{ margin: var(--s5) 0 0; }}
table.columns {{ min-width: 36rem; }}
"""
RECORD_STYLE = PAGE_STYLE + """
#scorecard > section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                       box-shadow: var(--shadow); padding: var(--s5); margin: var(--s5) 0; }
table.counts { min-width: 44rem; }
table.scores { min-width: 52rem; }
table.calibration { max-width: 32rem; }
svg.calibration { display: block; width: 100%; max-width: 14rem; height: auto; margin: var(--s3) 0; }
svg.calibration line { stroke: var(--axis); stroke-width: .5; }
svg.calibration circle { fill: var(--accent); }
"""
_ORDER = {column.key: index for index, column in enumerate(COLUMNS)}
_NINE = NUMBER_WORDS[len(COLUMNS)].lower()


@dataclass(frozen=True)
class FrontRow:
    """One front page row (the module's docstring): a product's lowest deal at a column passing the front page's test,
    its gap, and the promotion's conditions from the fields."""
    column: str
    code: str
    title: str
    deal: Deal
    gap: Gap
    restrictions: tuple[str, ...]
    min_spend: Decimal | None
    programmes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Counts:
    """The front page's numbers (question A; the site-day file's `counts`): the wide promotions listed today, distinct
    by chain and id; their barcodes; the barcodes with a front row."""
    promotions: int
    products: int
    below: int


@dataclass(frozen=True)
class ColumnsToday:
    """The method page's account of the columns that day (`shopper.columns`): each column's included stores by key,
    each chain's included stores in no column by slug, the columns under the floor, and Carrefour's table."""
    members: dict[str, frozenset[str]]
    outside: dict[str, list[Store]]
    under_floor: list[str]
    carrefour: Mapping[str, str]


def _span(value: str) -> str:
    return CHAIN_SPAN.format(text(value))


def _day(day: date) -> str:
    return f"{day:%-d %B %Y}"


def _scroller(label: str, table: str) -> str:
    """A wide table's box, scrolling on a narrow screen and reachable by keyboard, named `label`."""
    return f'<div class="table" tabindex="0" role="region" aria-label="{escape(label)}">{table}</div>'


# The front page

def front_rows_of(code: str, title: str, pairs: Mapping[str, Pair], column_days: Mapping[tuple[str, date], ColumnDay],
                  day: date) -> list[FrontRow]:
    """The product's front page rows on `day` (the module's docstring): at most one per column, in name order."""
    rows = []
    for column in COLUMNS:
        pair = pairs.get(column.key)
        if pair is None:
            continue
        best = None
        for struct in running_today(pair.points.get(day), day):
            deal = deal_from_row(struct)
            if on_front(deal, struct["wide"], pair, column_days, day) and (best is None or deal.price < best[0].price):
                best = deal, struct
        if best is not None:
            deal, struct = best
            rows.append(FrontRow(column=column.key, code=code, title=title, deal=deal,
                                 gap=gap(deal.price, pair, column_days, day),
                                 restrictions=tuple(struct["restrictions"]), min_spend=struct["min_spend"],
                                 programmes=tuple(struct["programmes"])))
    return rows


def store_path(column: str) -> str:
    """A store type's front page in the site: store/<column key>.html (search.js's own path for it)."""
    return f"store/{column}.html"


def column_ready(column_days: Mapping[tuple[str, date], ColumnDay], column: str, day: date) -> bool:
    """Whether `column` has a record on at least MIN_FRONT_DAYS of the RECENT_DAYS days before `day`: a product's days
    of records at a column are days the column has a record (P6), so before then none of its products can pass the
    front test's days (`shopper.measures.on_front`), and its lead line says none can be listed yet."""
    first = day - timedelta(days=RECENT_DAYS)
    held = sum(1 for (key, seen), found in column_days.items()
               if key == column and first <= seen < day and found.record)
    return held >= MIN_FRONT_DAYS


def _by_shown(row: FrontRow) -> tuple[bool, int]:
    """A row's place by the depth it shows: its whole percent (`shown_below`; "under 1%" is 0), deepest first, and a
    row with no shown gap last."""
    shown = shown_below(row.gap)
    return (shown is None, 0 if shown is None else -shown[1])


def ordered(rows: Iterable[FrontRow]) -> list[FrontRow]:
    """By the depth shown, deepest first (`_by_shown`), then by the exact depth, then by column in name order, then by
    barcode as a number: the table's order is its figures' order (deploy prep)."""
    return sorted(rows, key=lambda row: (*_by_shown(row), -depth(row.gap), _ORDER[row.column], by_number(row.code)))


def _search(browse: str | None) -> str:
    """The search box (search.js, the shell's one script, finds it) and the browse link, from the site's root."""
    link = f'<p><a href="{UP}{escape(browse)}">{text(BROWSE_LINK)}</a></p>' if browse else ""
    return (f'<section class="search"><label for="q">{text(SEARCH_LABEL)}</label>'
            f'<input id="q" type="search" autocomplete="off">{link}</section>')


def _filters() -> str:
    """The two checkboxes, siblings of the table, so CSS alone filters its rows (the module's docstring)."""
    return (f'<input type="checkbox" id="f-club"><label for="f-club">{text(CLUB_FILTER)}</label>'
            f'<input type="checkbox" id="f-spend"><label for="f-spend">{text(SPEND_FILTER)}</label>')


def _row(row: FrontRow) -> str:
    deal = row.deal
    said = text(deal_price(deal.price, deal.per)) + (f", {text(buy(deal.buy))}" if deal.buy != 1 else "")
    shown = shown_below(row.gap)
    percent = "" if shown is None else percent_text(shown[1])
    conditions = "; ".join([*field_conditions({"restrictions": row.restrictions, "programmes": row.programmes,
                                               "min_spend": row.min_spend}), text(FINE_PRINT)])
    marks = (' data-club=""' if row.restrictions else "") + (' data-spend=""' if row.min_spend is not None else "")
    return (f'<tr data-column="{row.column}"{marks}><th scope="row"><a href="{UP}{page_path(row.code)}">'
            f"{_span(row.title)}</a><small>{text(row.code)}</small></th><td>{text(BY_KEY[row.column].name)}</td>"
            f"<td>{said}</td>"
            f"<td>₪{money(row.gap.median30)}</td><td>{percent}</td><td>{conditions}</td></tr>")


def _rules(counts: Counts, marking_none: Sequence[str]) -> str:
    """The fold-out under the table's note (the module's docstring): closed until opened, with no script."""
    rules = "".join(f"<li>{text(rule)}</li>" for rule in FRONT_RULES)
    club = " ".join(part for part in (CLUB_NOTE, marked_none(marking_none)) if part)
    return (f"<details><summary>{text(RULES_TITLE)}</summary><p>{text(RULES_INTRO)}</p><ul>{rules}</ul>"
            f"<p>{text(WINDOWS_NOTE)}</p><p>{text(club)}</p><p>{text(SPEND_NOTE)}</p>"
            f"<p>{text(promotions_line(counts.promotions, counts.products))}</p>"
            f'<p><a href="{UP}method.html">{text(RULES_LINK)}</a></p></details>')


def _deals(rows: Sequence[FrontRow], counts: Counts, marking_none: Sequence[str]) -> str:
    heads = "".join(f'<th scope="col">{text(head)}</th>' for head in FRONT_HEADS)
    body = "".join(_row(row) for row in rows) or f'<tr><td colspan="{len(FRONT_HEADS)}">{text(NO_DEALS)}</td></tr>'
    table = f'<table class="front"><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table>'
    return (f'<section class="deals">{_filters()}{_scroller(FRONT_TITLE, table)}<p class="note">{text(TABLE_NOTE)}</p>'
            f"{_rules(counts, marking_none)}</section>")


def _story(row: FrontRow) -> str:
    """One deal's story: the top row's P7 sentences, in the product page's words."""
    return (f'<section class="story"><h2>{text(GAP_HEADING)}</h2><p class="story-head">'
            f'<a href="{UP}{page_path(row.code)}">{_span(row.title)}</a> · {text(BY_KEY[row.column].name)}</p>'
            f"<p>{text(' '.join(gap_sentences(row.gap)))}</p></section>")


def _hiring() -> str:
    links = " · ".join(f'<a href="{escape(href)}">{text(label)}</a>' for label, href in HIRING)
    return f'<p class="hiring">{links}</p>'


def _picker() -> str:
    """The picker (the module's docstring): each chain's name over its store types' links, in PICK_GROUPS' order."""
    groups = "".join(f"<h3>{text(CHAIN_NAMES[slug])}</h3><ul>"
                     + "".join(f'<li><a href="{store_path(key)}">{text(BY_KEY[key].name)}</a></li>' for key in keys)
                     + "</ul>" for slug, keys in PICK_GROUPS)
    return f'<section id="pick" data-page="root"><h2>{text(PICK_TITLE)}</h2>{groups}</section>'


def render_root(day: date, collected_by: str) -> str:
    """`index.html`, the picker (the module's docstring)."""
    parts = [f"<h1>{text(FRONT_TITLE)}</h1>", f'<p class="lede">{text(ROOT_LINE)}</p>', _picker()]
    parts.append(_hiring())
    links = [(BASKET_TITLE, "basket.html"), (RECORD_TITLE, "record.html"), (METHOD_TITLE, "method.html")]
    return page(f"{FRONT_TITLE} - {SITE_NAME}", "\n".join(parts), day, collected_by, links, ROOT_STYLE, up="")


def render_store(column: str, rows: Iterable[FrontRow], counts: Counts, day: date, collected_by: str,
                 marking_none: Sequence[str], browse: str | None = None, *, ready: bool) -> str:
    """`store/<column>.html` (the module's docstring): `rows` every column's front rows, of which the page shows
    `column`'s; `counts` the site's (its fold-out's count line, until the store-first plan's Task 6); `marking_none` the
    chains (slugs) whose files mark no restricted promotion today, `browse` a browse page's path from the root for the
    link to them, None when there is none, `ready` whether a product of the column could pass the front test's days
    (`column_ready`)."""
    name = BY_KEY[column].name
    shown = ordered(row for row in rows if row.column == column)
    parts = [f'<p class="at">{text(name)}</p>', f'<h1 id="deals">{text(FRONT_TITLE)}</h1>',
             f'<p class="sub">{text(FRONT_SUBTITLE)}</p>', _search(browse),
             f'<p class="lede">{text(lead_line(len(shown), ready))}</p>',
             _deals(shown, counts, marking_none)]
    if shown:
        parts.append(_story(shown[0]))
    links = [(BROWSE_LINK, browse)] if browse else []
    links += [(BASKET_TITLE, "basket.html"), (RECORD_TITLE, "record.html"), (METHOD_TITLE, "method.html")]
    return page(f"{name} - {SITE_NAME}", "\n".join(parts), day, collected_by, links, STORE_STYLE, up=UP, store=column)


# The method page

COLUMN_INTRO = ("A column is a store format this site shows as its own unit. Shufersal's and Carrefour's formats carry "
                "different promotions and list different prices (measured on the files of 5 and 7 November 2026), so "
                f"each of their formats with at least {FLOOR} included stores on the store lists of {_day(FIXED_ON)} "
                "is a column of its own (the floor below; the smaller ones then are in no column), and every measure "
                "on the front, product and record pages is a column's: which products are covered, listed prices, "
                "promotions listed across a column, the history, the forecasts and the record. The headline basket, "
                "in its section below, takes each chain's median instead. "
                f"{joined([CHAIN_NAMES[slug] for slug in SLUGS if len(columns_of(slug)) == 1])} are each shown as one "
                "format, whole.")
COLUMNS_FIXED = (f"The {_NINE} columns are fixed in the code for target version {TARGET_VERSION}. A format of a "
                 f"chain split into formats is a column when it had at least {FLOOR} included stores on the store "
                 f"lists of {_day(FIXED_ON)}; a chain shown whole is a column whatever its size. A column whose stores "
                 "later fall under that floor stays a column, and is named below; adding or dropping a column is a new "
                 "target version.")
LEFT_OUT_BY_RULE = ("The stores left out by rule are in no column either: the online stores named in the chains' store "
                    "lists, and Shufersal's Be sub-chain (the headline basket's rule B2, its stores named under "
                    "\"Stores left out\" in its section below).")
STORE_779 = ("A store is left out too on a day its price files are named under a sub-chain left out, whatever the "
             "store list says: on 2 and 7 November 2026, Shufersal's store 779, which the store list puts in Shufersal "
             "Express, had its files named under Be's sub-chain. The table above counts by the store list, so such a "
             "store is among its column's included stores there, though none of its files counts.")
CARREFOUR_DRAWN = ("Carrefour's store list names no format. Its stores were grouped by the promotions they carry, "
                   "measured on 5 and 7 November 2026: two stores were joined when at least half of the promotions, "
                   "coupons aside, that either one carries are carried by both, and a group is the stores joined "
                   "directly or through others. Each of the two largest groups is a column, named "
                   "after the word most of its stores' names carry (\"City\" or \"Market\", in Hebrew). A store the "
                   "table does not list is in no column until it is added.")
METHOD_LEDE = ("How these pages are made from the chains' own files: the columns this site shows and their stores, the "
               "rules each number follows, the words the site does not use, and how anyone with the files can make the "
               "same pages. The headline basket's own method comes last.")
NEVER_INTRO = ("This site does not use these words and phrases anywhere but in this list, nor any sentence that gives "
               "a chain a motive:")
MEASURED = ("Measured, from the files by rule: listed prices and their ranges, promotions and their dates, deal prices "
            "where the fields check out, the conditions the fields give, and the facts and counts of P7 and P8. "
            "Computed by rule and named as such: a column's median, whether a promotion is listed across a column, "
            "depth. Inferred, and labelled: the forecast, which no product page shows before its column's gate opens. "
            "Nothing here is read from a promotion's fine print yet.")
LAW = ("The five chains publish these price and promotion files under section 30 of the Food and Pharma Competition "
       "Promotion Law, 2014. Every number here is derived from those files; product and store names are shown as the "
       "chains publish them, and no file and no store's price list is republished.")
_LOW, _HIGH = f"{(100 - LEVEL) / 2:g}", f"{(100 + LEVEL) / 2:g}"
RULES = (
    ("P1 A product.",
     "A barcode that passes the GS1 check digit, leading zeros stripped; a chain's internal codes (weighed produce, "
     "its own codes) are not products here. The site covers a product once, on some day with records, at least half of "
     "a column's stores with a price file list it; from then on it keeps its page, rebuilt every morning, which says "
     "when it was last seen listed across each column."),
    ("P2 Listed price.",
     "A column's listed price for a product on a day is the median of the product's price across the column's included "
     "stores whose latest full price file that day lists it (with an even count, the mean of the two middle prices), "
     "prices of ₪0.01 or less dropped as placeholders; the lowest and highest store prices are shown beside it. A "
     "column whose files that day come from fewer than half its included stores is a hole: its prices are shown as "
     "from too few files, no listed price is claimed, every promotion that day is shown \"at some stores\", without "
     "P7's facts, no promotion is said to be listed to start, and the day counts in no window, front page or "
     "forecast."),
    ("P3 A promotion.",
     "A promotion in a chain's full promotion files of the day (each counted store's latest), linked to the product's "
     "barcode through its groups' items, whose start is on or before the day and whose end is on or after it. A "
     "column's counted stores are its stores whose price file counts that day (P2). A promotion is listed across a "
     "column when the promotion files of at least half those stores carry it; one carried by fewer is shown \"at some "
     "stores\" and never ranked. Coupons and promotions holding a reward on a whole basket (RewardType 12 or 6) are "
     "counted and never shown. A link of RewardType 0 carries no price: an item named only by such links shows its "
     "promotion with \"price not read\" and is not on promotion."),
    ("P4 Deal price.",
     "The price per unit after the promotion, per kilogram when the item is weighed, when buying the least that "
     "qualifies: a fixed price (RewardType 3) is the link's DiscountedPrice; \"N for ₪M\" (1 and 10) is M ÷ N, shown "
     "with \"buy N\"; percent off (2) is the median of the counted stores' own DiscountedPrice, its lowest and highest "
     "shown, and it must agree with the rate: within ₪0.01 of the column's listed price × (1 − DiscountRate ÷ 100), "
     "rounded to agorot. Every deal must be above ₪0.01 and below twice the listed price. A deal that fails a check, "
     "or whose fields give no price, is shown as \"price not read\" and never ranked. A deal price is kept exactly, as "
     "a fraction; the pages show it to the agora, and every comparison a page states is worked on the figures it "
     "shows."),
    ("P5 Conditions.",
     "Who a promotion is for comes from its ClubID field, every code in it: 1 club members only, 2 the chain's card "
     "holders only, 3 some customers only, and a programme named under code 0 some customers only; every programme's "
     "name is shown as the chain publishes it. A minimum spend is the largest MinPurchaseAmount above zero on any of "
     "the promotion's groups. Each condition names its source, \"from the chain's fields\". The fine print is not read "
     f"yet, so every promotion says \"{FINE_PRINT}\"."),
    ("P6 Windows.",
     f"The past {RECENT_DAYS} and {READ_DAYS} days are the calendar days before the page's day, counting only the days "
     "on which the column has a record and the product a listed price; holes are skipped, never filled. A window with "
     f"fewer than {ENOUGH[RECENT_DAYS]} of {RECENT_DAYS} or {ENOUGH[READ_DAYS]} of {READ_DAYS} such days says so (\"23 "
     "days of records since 1 November 2026\"), and every count over a window's days is out of its days with "
     "records."),
    ("P7 The gap.",
     f"Three measured facts about a deal listed across its column: its price against the {RECENT_DAYS}-day median "
     "listed price, as money and a whole percent (\"under 1%\" when a gap above ₪0 rounds to 0%); the lowest listed "
     f"price of the past {RECENT_DAYS} and {READ_DAYS} days, and on how many of the {READ_DAYS} days with records the "
     "item was listed at or below the deal; and each "
     f"change in the listed price in the past {RECENT_DAYS} days, dated where two consecutive days with records pin "
     f"it, else given with both days. Depth is ({RECENT_DAYS}-day median − deal price) ÷ that median. The front page "
     "lists a deal when it is listed across its column, its price is read (P4), the column has a record today, and the "
     f"item has at least {MIN_FRONT_DAYS} days of records in the past {RECENT_DAYS}, with the deal price as shown "
     f"below every listed price of the past {READ_DAYS} days as shown. Its rows are sorted by the depth they show, "
     "deepest first, then by the exact depth; a product listed across several columns can have a row at each."),
    ("P8 Promotion history.",
     f"Over the {READ_DAYS} days before today, at the column: the days on a promotion listed across it, of the days "
     "with records; each run of consecutive days on promotion (a day the files say nothing of, a hole, a day the "
     "product is not listed or whose promotions were not read, neither ends nor extends a run); the days between runs; "
     "the last run's end and the days since. An end beside such a day is given as a bound (\"or earlier\", \"or "
     "later\", \"at most\")."),
    ("P9 Across the columns.",
     "One row on each product page: each column's listed price today and its deal price today, if any, with the "
     "conditions marked; in name order, never by price, with no ranking word."),
    ("P10 A format change.",
     "A promotion file whose fields differ from what the chain's files were seen to carry, or a RewardType, ClubID or "
     "DiscountType value not seen, or an IsGiftItem of another form, stops that chain's promotions for the day with an "
     "error naming the field. Its prices still build, every section of its columns says so (\""
     f"{unreadable('carrefour')}\" for Carrefour), and the day is a hole for its columns' promotion history and "
     "forecasts."),
    (f"F1 Target, version {TARGET_VERSION}.",
     "For a product at a column on day d: 1 if a promotion carried by at least half the column's counted stores, with "
     "a price effect on the item (a link of RewardType 1, 2, 3 or 10; club-only and \"price not read\" included), is "
     f"listed in the morning full files of at least one of days d + 1 to d + {HORIZON}, else 0. A new definition is a "
     "new target version; no later reading changes a past outcome."),
    ("F2 Who gets a forecast.",
     "Every covered product listed across a column on day d and not on a promotion listed across it that day, on a day "
     "the column has a record and its promotions were read; a product with a promotion listed to start in d + 1 to "
     f"d + {HORIZON} gets none, and its page says when it is listed to start. A column's forecasts start on its "
     f"{FIRST_RECORD_DAY}th day of records, once it has a closed day to learn from."),
    ("F3 Inputs pinned to the day.",
     f"A forecast for day d reads only the files of days up to d, and learns only from past days t whose {HORIZON} "
     f"days have closed by then (t at most d − {HORIZON}), within the {READ_DAYS} days read and with at most "
     f"{MAX_HOLES} holes in their window."),
    (f"F4 Model, version {MODEL_VERSION}.",
     "For each column, the share of outcome 1 over its closed days among the products with the same days since their "
     f"last run ended (0 to {DAYS_SINCE_CAP}, more counted as {DAYS_SINCE_CAP}, or no run seen), blended with the "
     "product's own share (baseline A) by weight n ÷ (n + n0): n the product's closed days, n0 = "
     f"{N0}, fixed before the version's first frozen day."),
    ("F5 Two baselines.",
     "A, the product's base rate: its share of outcome 1 over its closed days, or the column's share with fewer than "
     f"{A_MIN_DAYS}. B, \"the last gap repeats\": with two or more runs seen, the next is taken to start at the last "
     "run's end plus the days from the end of the run before it to the start of the last; B says yes when that falls "
     f"in d + 1 to d + {HORIZON}, and is scored as the column's share of outcome 1 over its closed days on which B "
     "gave the same answer. Both are frozen beside the model and scored on the same forecasts."),
    ("F6 The daily freeze.",
     "Each day's forecasts file is written once, in the archive, write-once and locked, and published with the same "
     "bytes (forecasts/<day>.csv.gz); a later run with other rows stops. A day counts only when its file was stored "
     "before midnight ending it, Israel time, by the storage's clock, not the writer's. The ledger, "
     "forecasts/ledger.csv, gains a line per frozen day (the day, the file's SHA-256 and its storage time) and only "
     "grows. The record starts on the first day frozen on time."),
    ("F7 Scoring.",
     f"Day d's forecasts are scored once day d + {HORIZON}'s files are in, against F1's outcome, and the scores file "
     "(scores/<day>.csv.gz) is written once, each row with its outcome and its evidence (the first day in the window a "
     "promotion was listed across the column, and its PromotionID) or why it is unscored. A forecast whose window "
     f"holds more than {MAX_HOLES} holes is unscored and counted, the same for the model and both baselines. The Brier "
     "score is the mean of (p − outcome)² over a day's scored forecasts, then over days; the skill against a baseline "
     "is 1 − the model's Brier score ÷ the baseline's."),
    ("F8 Intervals and calibration.",
     f"Intervals come from a moving-block bootstrap over the scored days: blocks of {BLOCK} consecutive scored days, "
     f"{DRAWS:,} draws, seed {SEED}; {LEVEL}% intervals from the {_LOW}th and {_HIGH}th percentiles, none under "
     f"{MIN_DAYS} scored days. Calibration buckets the scored forecasts by the model's probability into ten bins of "
     "width 0.1; the calibration error is the count-weighted mean absolute gap between a bin's mean forecast and its "
     "share of outcome 1. With the published forecasts and scores files and this code, anyone gets the same tables, "
     "and the same intervals to rounding, on Python 3.13."),
    ("F9 The gate.",
     "A column's product pages show odds only when all of these hold for that column, and then only on the owner's go: "
     f"at least {GATE_DAYS} scored days of the model version in force, each frozen on time; the model's Brier score "
     f"below both baselines', with the {LEVEL}% interval of each difference wholly below zero; and a calibration error "
     f"of at most {CAL_MAX}, with no bin holding {_BIN_SHARE}% or more of the scored forecasts off by more than "
     f"{BIN_OFF}. A new version (new constants or a new target) starts its count from zero, and every version's days "
     "stay on the record page. In this version of the site no gate opens."),
    ("F10 Before the gate.",
     "While a column's gate is closed, its sections on a product page show the measured history (P8) and the fixed "
     f"sentence that begins \"{no_odds_yet('shufersal-deal').split('. ')[0]}.\", with no other odds word; the record "
     "page shows the scorecard, the gate's conditions and which hold, and the files, as test records, not advice."),
    ("F11 How the record is shown.",
     "Per column, per month and in all, per model version: the days frozen on time and late, and the days scored; the "
     "forecasts scored and unscored; the share of outcome 1; the Brier scores of the model and both baselines, their "
     "differences and the skills, with intervals; the calibration table and chart, and a sentence for each bin holding "
     f"{_BIN_SHARE}% or more of the scored forecasts."),
)

def _section(id_: str, heading: str, *parts: str) -> str:
    return f'<section id="{id_}"><h2>{text(heading)}</h2>{"".join(parts)}</section>'


def _stores_of(column) -> str:
    """How a column's stores are chosen, in the method page's table."""
    if column.sub_chain is not None:
        return f"sub-chain {column.sub_chain} on the day's store list"
    if len(columns_of(column.slug)) > 1:
        return "Carrefour's table, below"
    return "every included store"


def _left_out_in_columns(exclusions: Mapping[str, Sequence[Store]], table: Mapping[str, str]) -> str:
    """The stores left out by rule whose part of the store list is a column's, each with that column."""
    named = [f"{CHAIN_NAMES[slug]}'s store {store.id} ({BY_KEY[key].name})"
             for slug in SLUGS for store in exclusions.get(slug, ())
             if store.id in EXCLUDED[slug].stores and (key := column_of(slug, store, table)) is not None]
    if not named:
        return ""
    return f"<p>Of them, these are on the store list in a column's part and left out of it: {text(joined(named))}.</p>"


def _columns_section(columns: ColumnsToday, exclusions: Mapping[str, Sequence[Store]]) -> str:
    rows = "".join(f"<tr><td>{text(column.name)}</td><td>{text(CHAIN_NAMES[column.slug])}</td>"
                   f"<td>{text(_stores_of(column))}</td><td>{len(columns.members.get(column.key, ()))}</td></tr>"
                   for column in COLUMNS)
    table = ('<table class="columns"><thead><tr><th scope="col">Column</th><th scope="col">Chain</th>'
             '<th scope="col">Its stores</th><th scope="col">Included stores on today\'s store list</th></tr></thead>'
             f"<tbody>{rows}</tbody></table>")
    return _section("columns", "What a column is", f"<p>{text(COLUMN_INTRO)}</p>", f"<p>{text(COLUMNS_FIXED)}</p>",
                    _scroller("The columns", table),
                    f"<p>{text(LEFT_OUT_BY_RULE)}</p>", _left_out_in_columns(exclusions, columns.carrefour),
                    f"<p>{text(STORE_779)}</p>")


def _carrefour_section(table: Mapping[str, str]) -> str:
    lines = []
    for column in columns_of("carrefour"):
        ids = sorted((store for store, key in table.items() if key == column.key), key=by_number)
        said = f"{'store' if len(ids) == 1 else 'stores'} {joined(ids)}" if ids else "no store"
        lines.append(f"<p><b>{text(column.name)}</b>: {text(said)}.</p>")
    return _section("carrefour", "Carrefour's two columns, store by store", f"<p>{text(CARREFOUR_DRAWN)}</p>", *lines)


def _fixed_day_outside() -> str:
    """The formats in no column on the day the nine were fixed, from `shopper.columns.FORMATS_ON_FIXED_DAY`."""
    chosen = {column.sub_chain for column in columns_of("shufersal")}
    small = sorted(((key, count) for key, count in FORMATS_ON_FIXED_DAY["shufersal"].items() if key not in chosen),
                   key=lambda pair: (-pair[1], by_number(pair[0])))
    names = FORMAT_NAMES["shufersal"]
    shufersal = joined([f"sub-chain {key} ({names[key] + ', ' if key in names else ''}{count} "
                        f"{'store' if count == 1 else 'stores'})" for key, count in small])
    keys = {column.key for column in columns_of("carrefour")}
    carrefour = joined([f"the {name} ({count} {'store' if count == 1 else 'stores'})"
                        for name, count in FORMATS_ON_FIXED_DAY["carrefour"].items() if name not in keys])
    return (f"On the store lists of {_day(FIXED_ON)}, Shufersal's included stores in no column were those of "
            f"{shufersal}, each format under the floor; Carrefour's, over 5 and 7 November 2026, were {carrefour}. No "
            "product page shows them; the headline basket counts them in its chains' medians.")


def _outside_section(columns: ColumnsToday) -> str:
    parts = [f"<p>{text(_fixed_day_outside())}</p>"]
    for slug in SLUGS:
        stores = sorted(columns.outside.get(slug, ()), key=lambda store: by_number(store.id))
        if not stores:
            continue
        by_sub_chain = any(column.sub_chain is not None for column in columns_of(slug))
        items = "".join(f"<li>store {text(store.id)}"
                        + (f", sub-chain {text(store.sub_chain or 'none')}," if by_sub_chain else "")
                        + f" {_span(store.name)}</li>" for store in stores)
        count = f"{len(stores)} {'store' if len(stores) == 1 else 'stores'}"
        parts.append(f"<p>{text(CHAIN_NAMES[slug])}: {count} in no column today.</p>"
                     f"<details><summary>The {count} by id</summary><ul>{items}</ul></details>")
    if len(parts) == 1:
        parts.append("<p>Every included store is in a column today.</p>")
    return _section("outside", "Included stores in no column", *parts)


def _floor_section(columns: ColumnsToday) -> str:
    lines = [f"<p>{text(BY_KEY[key].name)}: {len(columns.members.get(key, ()))} included stores today, under the floor "
             f"of {FLOOR}; it stays a column, since the {_NINE} are fixed for target version {TARGET_VERSION}."
             "</p>" for key in columns.under_floor]
    return _section("floor", "Columns under the floor today", *lines or [
        f"<p>No column of a chain split into formats has fewer than {FLOOR} included stores today.</p>"])


def _rules_section() -> str:
    rules = "".join(f"<li><b>{text(name)}</b> <span>{text(said)}</span></li>" for name, said in RULES)
    return _section("rules", "The rules", f'<ol class="rules">{rules}</ol>')


def _never_section() -> str:
    items = "".join(f"<li>{text(phrase)}</li>" for phrase in NEVER)
    return _section("never", "Words this site does not use", f"<p>{text(NEVER_INTRO)}</p>",
                    f'<ul id="never-words">{items}</ul>')


def _reproduce_section(day: date, code_sha: str) -> str:
    site_day = f"site-days/{day.isoformat()}.json"
    # the archive holds no day before the collector's first morning, 1 November 2026: the build reads such a day as a
    # hole (the owner, 2026-11-10)
    take = (f"Take each chain's full price and promotion files and its store list of every day from {READ_DAYS} days "
            "before this site's first day to the day (this site has none from before 1 November 2026, when its "
            "collection began, and reads such a day as one without records), as the chains published them, this "
            f"site's code on GitHub at the fingerprint {code_sha}")
    same = ("and the rules above: the same files and code give the same numbers on every page, the record's "
            f"intervals to rounding (F8). A page's measures read the day and the {READ_DAYS} days before it; which "
            "products have a page, their names and sizes, and when each was last seen listed across a column come from "
            "a record carried from day to day since the site's first. The day's inputs are named in")
    rest = ("; the forecasts and scores files and the ledger, linked from the record page, let anyone recompute the "
            "record.")
    return _section("reproduce", "To reproduce a page",
                    f'<p>{text(take)} (<a href="{escape(GITHUB)}">{text(GITHUB)}</a>), {text(same)} '
                    f'<a href="{site_day}">{site_day}</a>{text(rest)}</p>')


def render_method(basket: Basket, exclusions: Mapping[str, Sequence[Store]], columns: ColumnsToday, day: date,
                  collected_by: str, code_sha: str, public: dict) -> str:
    """`method.html` (the module's docstring): `exclusions` each chain's stores left out by rule, by slug; `code_sha`
    the site's code fingerprint; `public` the basket's day as its pages show it, for its method's parts."""
    parts = [f"<h1>{text(METHOD_TITLE)}</h1>", f'<p class="lede">{text(METHOD_LEDE)}</p>',
             _columns_section(columns, exclusions), _carrefour_section(columns.carrefour), _outside_section(columns),
             _floor_section(columns), _rules_section(), _never_section(),
             _section("measured", "Measured and inferred", f"<p>{text(MEASURED)}</p>"),
             _section("law", "The law", f"<p>{text(LAW)}</p>"), _reproduce_section(day, code_sha),
             f'<section id="{BASKET_SECTION}"><h2>{text(BASKET_TITLE)}</h2>'
             f'{"".join(method_parts(basket, exclusions, public, BASKET_PAGE))}</section>']
    links = ((RECORD_TITLE, "record.html"), (BASKET_TITLE, "basket.html"))
    return page(f"{METHOD_TITLE} - {SITE_NAME}", "\n".join(parts), day, collected_by, links,
                BASKET_STYLE + METHOD_STYLE, up="")


# The record page

def _figure(value: str | Decimal | None, places: int = FOUR) -> str:
    """A record's number as the page shows it: `places` decimals, half up; "none" for none."""
    if value is None:
        return "none"
    return str(Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def _percent(share: Fraction | str | None) -> str:
    return "none" if share is None else f"{whole(100 * Fraction(share))}%"


def _month(month: str) -> str:
    return f"{date.fromisoformat(month + '-01'):%B %Y}"


def _interval(intervals: dict | None, name: str) -> str:
    if intervals is None:
        return f"<small>{text(TOO_FEW)}</small>"
    span = intervals[name]
    if span is None:
        return "<small>no interval</small>"
    return f"<small>{LEVEL}%: {span['low']:.{FOUR}f} to {span['high']:.{FOUR}f}</small>"


def _counts_row(period: str, record: dict) -> str:
    cells = (record["days_on_time"], record["days_late"], record["days_scored"], f"{record['forecasts']:,}",
             f"{record['scored']:,}", f"{record['unscored']:,}", _percent(record["outcome_1_share"]))
    return f'<tr><th scope="row">{text(period)}</th>{"".join(f"<td>{cell}</td>" for cell in cells)}</tr>'


def _scores_row(period: str, record: dict) -> str:
    brier, skill, spans = record["brier"], record["skill"], record["intervals"]
    if brier is None:
        cells = ["<td>none</td>"] * 7
    else:
        model, a, b = (Decimal(brier[key]) for key in ("model", "a", "b"))
        cells = [f"<td>{_figure(model)}</td>", f"<td>{_figure(a)}</td>", f"<td>{_figure(b)}</td>",
                 f"<td>{_figure(model - a)}{_interval(spans, 'model_minus_a')}</td>",
                 f"<td>{_figure(model - b)}{_interval(spans, 'model_minus_b')}</td>",
                 f"<td>{_figure(skill['a'])}{_interval(spans, 'skill_a')}</td>",
                 f"<td>{_figure(skill['b'])}{_interval(spans, 'skill_b')}</td>"]
    return f'<tr><th scope="row">{text(period)}</th>{"".join(cells)}</tr>'


def _calibration(name: str, calibration: dict, scored: int) -> str:
    """The calibration's table, its chart (hidden from screen readers: the table says the same) and a sentence for
    each bin holding 1% or more of the version's scored forecasts."""
    rows, points, said = [], [], []
    for row in calibration["bins"]:
        span = f"{row['low']} to {row['high']}"
        filled = row["count"] > 0
        rows.append(f'<tr><th scope="row">{span}</th><td>{row["count"]:,}</td>'
                    f"<td>{_figure(row['mean_p'], 3) if filled else 'none'}</td>"
                    f"<td>{_figure(row['share'], 3) if filled else 'none'}</td></tr>")
        if filled:
            x, y = Decimal(row["mean_p"]) * 100 + 10, 110 - Decimal(row["share"]) * 100
            points.append(f'<circle cx="{_figure(x, 1)}" cy="{_figure(y, 1)}" r="2.5"/>')
            if holds_share(row["count"], scored):
                said.append(f"Of the scored forecasts from {span} ({_percent(Fraction(row['count'], scored))} of this "
                            f"version's), {_percent(row['share'])} had a promotion listed across {name} in the "
                            f"{HORIZON} days after.")
    table = ('<table class="calibration"><thead><tr><th scope="col">Model\'s probability</th><th scope="col">Scored'
             '</th><th scope="col">Mean forecast</th><th scope="col">Share of outcome 1</th></tr></thead>'
             f"<tbody>{''.join(rows)}</tbody></table>")
    chart = ('<svg class="calibration" viewBox="0 0 120 120" aria-hidden="true" focusable="false">'
             '<line x1="10" y1="110" x2="110" y2="110"/><line x1="10" y1="110" x2="10" y2="10"/>'
             f'<line x1="10" y1="110" x2="110" y2="10"/>{"".join(points)}</svg>')
    error = f"<p>Calibration error: {_figure(calibration['error'])}.</p>"
    return table + chart + error + "".join(f"<p>{text(sentence)}</p>" for sentence in said)


def _version(name: str, version: dict) -> str:
    periods = [("All", version["all"]), *((_month(month["month"]), month) for month in version["months"])]
    counts_head = "".join(f'<th scope="col">{head}</th>' for head in (
        "Period", "Files scored, frozen on time", "Files scored, frozen late (not counted)",
        "Days with a scored forecast", "Forecasts", "Scored", "Unscored",
        "Outcome-1 share"))
    scores_head = "".join(f'<th scope="col">{head}</th>' for head in (
        "Period", "Brier score: model", "A", "B", "Model − A", "Model − B", "Skill against A", "Skill against B"))
    counts = (f'<table class="counts"><thead><tr>{counts_head}</tr></thead>'
              f"<tbody>{''.join(_counts_row(period, record) for period, record in periods)}</tbody></table>")
    scores = (f'<table class="scores"><thead><tr>{scores_head}</tr></thead>'
              f"<tbody>{''.join(_scores_row(period, record) for period, record in periods)}</tbody></table>")
    head = f"Model {version['model_version']}, target {version['target_version']}"
    whole_record = version["all"]
    return (f"<h3>{text(head)}</h3>{_scroller(f'{name}, {head}: days', counts)}"
            f"{_scroller(f'{name}, {head}: scores', scores)}"
            f"{_calibration(name, whole_record['calibration'], whole_record['scored'])}")


def _gate(column: str, found: dict) -> str:
    if found["open"]:
        raise ValueError(f"the gate is open at {column}, and step one shows no odds")
    held = found["conditions"]
    conditions = "".join(f"<li>{text(CONDITIONS[key])}: {'holds' if held[key] else 'does not hold'}.</li>"
                         for key in CONDITIONS)       # their order, not the mapping's: a file read back sorts its keys
    reasons = "".join(f"<li>{text(reason)}</li>" for reason in found["reasons"])
    return f"<p><b>{text(GATE_CLOSED)}</b></p><ul>{conditions}</ul><p>Why:</p><ul>{reasons}</ul>"


def scorecard_section(scorecard: dict) -> str:
    """The record page's tables, from the scorecard alone (the module's docstring). ValueError for an open gate."""
    columns = scorecard["columns"]
    force = scorecard["version_in_force"]
    boot = scorecard["bootstrap"]
    parts = [f"<p>{text(columns_tested(scorecard['columns_tested']))}</p>",
             f"<p>Model versions scored so far: {scorecard['versions_tried']}; the version in force is model "
             f"{text(force['model_version'])}, target {text(force['target_version'])}.</p>",
             f"<p>Intervals: a moving-block bootstrap over the scored days, blocks of {boot['block']} scored days, "
             f"{boot['draws']:,} draws, seed {boot['seed']}, {boot['level']}% intervals; none under {boot['min_days']} "
             "scored days.</p>"]
    if any(found["versions"] for found in columns.values()):        # only above a column's tables
        parts.append(f"<p>{text(SCORED_SO_FAR)}</p>")
    if not any(version["all"]["scored"] for found in columns.values() for version in found["versions"]):
        parts.append(f"<p><b>{text(NOTHING_SCORED)}</b></p>")
    for column in COLUMNS:       # their order, not the mapping's: the site-day file is written with its keys sorted
        key, found = column.key, columns[column.key]
        body = [f"<h2>{text(found['name'])}</h2>", _gate(key, found["gate"])]
        body += [_version(found["name"], version) for version in found["versions"]] or [
            f"<p>{text(COLUMN_NOTHING_SCORED)}</p>"]
        parts.append(f'<section data-column="{key}">{"".join(body)}</section>')
    return f'<div id="scorecard">{"".join(parts)}</div>'


def _ranges(days: Sequence[date]) -> str:
    """Days as runs of consecutive days ("3 to 5 December 2026; 9 December 2026"), or "none"."""
    runs: list[list[date]] = []
    for seen in sorted(days):
        if runs and runs[-1][1] + timedelta(days=1) == seen:
            runs[-1][1] = seen
        else:
            runs.append([seen, seen])
    return "; ".join(date_range(start, end) for start, end in runs) or "none"


def _frozen(ledger_days: Mapping[date, datetime], day: date) -> str:
    """The days the ledger names: frozen, on time and late, the days since the first with no file, the record's
    start."""
    frozen = sorted(ledger_days)
    if not frozen:
        return (f"<p>No forecasts have been frozen yet: a column's forecasts start on its {FIRST_RECORD_DAY}th day of "
                "records.</p>")
    timely = [seen for seen in frozen if on_time(seen, ledger_days[seen])]
    missed = [frozen[0] + timedelta(days=n) for n in range((day - frozen[0]).days + 1)
              if frozen[0] + timedelta(days=n) not in ledger_days]
    said = [f"Forecasts frozen on {len(frozen)} {'day' if len(frozen) == 1 else 'days'}, from {_day(frozen[0])} to "
            f"{_day(frozen[-1])}: {len(timely)} on time, {len(frozen) - len(timely)} late.",
            f"Days since {_day(frozen[0])} with no forecasts file: {_ranges(missed)}.",
            f"The record starts on {_day(timely[0])}, the first day frozen on time." if timely
            else "No day has been frozen on time yet, so the record has not started."]
    return "".join(f"<p>{text(sentence)}</p>" for sentence in said)


def _files(files: Sequence[str]) -> str:
    """The ledger, then each forecasts file and each scores file, newest first."""
    ledger = [path for path in files if path.endswith("ledger.csv")]
    forecasts = sorted((path for path in files if path.startswith("forecasts/") and path not in ledger), reverse=True)
    scores = sorted((path for path in files if path.startswith("scores/")), reverse=True)
    others = sorted(set(files) - set(ledger) - set(forecasts) - set(scores))
    links = "".join(f'<li><a href="{escape(path)}">{text(path)}</a></li>'
                    for path in (*ledger, *forecasts, *scores, *others))
    return f"<ul>{links}</ul>" if links else "<p>No file yet.</p>"


def _days_read(column_days: Mapping[tuple[str, date], ColumnDay]) -> str:
    days = sorted({seen for _, seen in column_days})
    rows = []
    for column in COLUMNS:
        mine = [column_days[(column.key, seen)] for seen in days if (column.key, seen) in column_days]
        cells = (str(sum(found.record for found in mine)),
                 _ranges([found.day for found in mine if found.present and found.hole]),
                 _ranges([found.day for found in mine if found.record and found.promo_hole]),
                 _ranges([found.day for found in mine if not found.present]))
        rows.append(f'<tr><th scope="row">{text(column.name)}</th>{"".join(f"<td>{cell}</td>" for cell in cells)}</tr>')
    head = "".join(f'<th scope="col">{label}</th>' for label in (
        "Column", "Days with records", "Short of price files", "Promotions short of files or not read", "No table"))
    said = "No day is read."
    if days:
        said = (f"The site's build reads the {len(days)} days from {_day(days[0])} to {_day(days[-1])}. A day short "
                "of price files is a hole (P2); a day whose promotions were short of files or not read is counted as "
                "neither on nor off promotion (P8); a day with no table is one its chain's extraction did not write.")
    table = f'<table class="days"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    return f"<p>{text(said)}</p>{_scroller('The days read', table)}"


def render_record(scorecard: dict, ledger_days: Mapping[date, datetime], files: Sequence[str],
                  column_days: Mapping[tuple[str, date], ColumnDay], day: date, collected_by: str) -> str:
    """`record.html` (the module's docstring): `ledger_days` each day the ledger names with its file's S3 time,
    `files` the site's paths of the ledger and every forecasts and scores file, `column_days` the days read."""
    # "on each day the rules allow": F2 gives a column no forecast on a hole for it or a day its promotions were not
    # read (deploy prep)
    lede = (f"From a column's {FIRST_RECORD_DAY}th day of records, once it has a closed day to learn from, this site "
            "freezes that column's forecasts on each day the rules allow (F2), before their outcomes are known, and "
            f"scores them {HORIZON} days later against two rules of thumb (F5). No product page shows odds: each column's gate (F9) is "
            "closed, and below are its conditions and which of them hold.")
    parts = [f"<h1>{text(RECORD_TITLE)}</h1>", f'<p class="lede">{text(lede)}</p>', scorecard_section(scorecard),
             f"<p>{text(FINE_PRINT_UNREAD)}</p>",
             _section("frozen", "The days frozen", _frozen(ledger_days, day)),
             _section("files", "The files: test records, not advice", f"<p>{text(FILES_LABEL)}</p>", _files(files)),
             _section("days", "The days read", _days_read(column_days))]
    links = ((METHOD_TITLE, "method.html"), (BASKET_TITLE, "basket.html"))
    return page(f"{RECORD_TITLE} - {SITE_NAME}", "\n".join(parts), day, collected_by, links, RECORD_STYLE, up="")


# The basket page

def render_basket(public: dict, basket: Basket, exclusions: Mapping[str, Sequence[Store]], day: date,
                  collected_by: str, product_pages: set[str]) -> str:
    """`basket.html` (the module's docstring): `public` the basket's day as its pages show it, `product_pages` the
    barcodes whose page the build has, leading zeros stripped, so an item's code is stripped to match (the final
    review's finding 12)."""
    frame = Frame(band=band(day, ""), credit=credit(day, collected_by),
                  item_link=lambda code: page_path(normalize(code)) if normalize(code) in product_pages else None,
                  method_href=f"method.html#{BASKET_SECTION}", note=formats_note(),
                  script=SCRIPT_TAG.format(up=""))
    return render_index(public, basket, exclusions, frame)

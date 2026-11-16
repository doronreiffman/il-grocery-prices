"""The page shell the shopper site's pages share: browse pages, product pages, the store types' front pages and the
root, method, record and basket pages (docs/shopper-site.md, "What a visitor sees", its paragraph on every page; the
plan's Tasks 16 and 17; docs/store-first.md, "What a visitor sees" 2 and "Q2's one script", the store-first plan's
Task 5; docs/site-look.md, "Components" and "The shared stylesheet and the font files", the site-look plan's Task 6).

Every page is one HTML file in English: `noindex` until the owner launches, light and dark colour schemes, then the
head's two links after the title (`head`): the site's one stylesheet (`shopper.assets.STYLESHEET`, under `assets/`)
and its one script (`SCRIPT_TAG`, `search.js`), each from the site's root; no page holds a style block of its own.
The body names the page's kind as its class, `t-<kind>` (KINDS: the front page, a store type's front page, a product
page, a browse page, the method, record and basket pages), from which the stylesheet lays each kind out; a kind not in
KINDS is refused. Then the header band, the main part, and the footer with the credit line (`shopper.words.credit`)
and the page's links. The band holds the brand, the site's name linking to the root, drawn as the front page's
headline (the owner, 2026-11-16; docs/site-look.md, "The header's name: green and yellow"): "Deal" in `<b>` (the green
label the stylesheet draws), " or ", "No Deal" in `<b class="no">` (the yellow one), so its text read is the name; the
store line; on the front page alone the chains' line (`shopper.words.CHAINS_LINE`); and the date line
(`shopper.words.date_line`), the chains' line in the date line's style. The store line is the pick link,
`<a id="pick-link" href="<up>index.html#pick">`, "Pick your store", in `<p class="store">` on every page, a store
type's front page included: search.js reads the site's root from its href and, once a store type is picked and
remembered, writes "<store type> · change" there, but on the front page, where it hides the store line beside its
"Your store" shortcut (its header comment). A store type's front page marks its main part with `data-store`
(`store`), from which the script sets the pick. Nothing else is loaded, from here or elsewhere. `up` is the path from
the page's folder to the site's root, "../" for `p/`, `browse/` and `store/` and "" for the root pages, so every link,
the stylesheet and the script resolve in the build.

The shell lives in its own module so that the front page's module can import the product pages' `page_path` while
the product pages import the shell: no import goes round in a circle.
"""
from collections.abc import Sequence
from datetime import date
from html import escape

from shopper.assets import STYLESHEET
from shopper.words import CHAINS_LINE, SITE_NAME, credit, date_line

PICK = "Pick your store"           # the header's store line before a pick (store-first.md, "Words")
SCRIPT_TAG = '<script src="{up}search.js" defer></script>'      # the site's one script, in every page's head
KINDS = ("front", "store", "product", "browse", "method", "record", "basket")    # the body's class, t-<kind>


def text(value: str) -> str:
    """`value` escaped for a text node; quotes stay as written."""
    return escape(value, quote=False)


def head(up: str) -> str:
    """The head's two links after the title: the site's one stylesheet, then its one script, each from the site's
    root (`up`); `basket.html`'s too, in the basket's frame."""
    return f'<link rel="stylesheet" href="{up}{STYLESHEET}">\n{SCRIPT_TAG.format(up=up)}'


def band(day: date, up: str, front: bool = False) -> str:
    """The header band: the brand linking to the root, the site's name on the headline's two labels, the store line's
    pick link, the chains' line on the front page alone (`front`), then the date line (`basket.html`'s too, in the
    basket's frame)."""
    yes, no = SITE_NAME.split(" or ")
    chains = f'<p class="dateline">{text(CHAINS_LINE)}</p>' if front else ""
    return (f'<header class="band"><div class="wrap"><a class="brand" href="{up}index.html"><b>{text(yes)}</b> or '
            f'<b class="no">{text(no)}</b></a><p class="store"><a id="pick-link" href="{up}index.html#pick">'
            f'{text(PICK)}</a></p>{chains}<p class="dateline">{text(date_line(day))}</p></div></header>')


def page(title: str, main: str, day: date, collected_by: str, links: Sequence[tuple[str, str]], kind: str,
         up: str = "../", store: str | None = None) -> str:
    """A whole page: `title` for the browser's tab (never a chain's text, which no span can hold there), `main` as
    HTML, the footer's `links` as (label, path from the root), `kind` the page's kind (one of KINDS, else ValueError),
    `store` the column key of a store type's front page (its main part's `data-store`), None on every other page."""
    if kind not in KINDS:
        raise ValueError(f"a page of a kind the shell does not know: {kind!r}, not one of {KINDS}")
    footer = " · ".join(f'<a href="{up}{escape(path)}">{text(label)}</a>' for label, path in links)
    opening = "<main>" if store is None else f'<main data-store="{escape(store)}">'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>{text(title)}</title>
{head(up)}
</head>
<body class="t-{kind}">
{band(day, up, front=kind == "front")}
{opening}
{main}
</main>
<footer><div class="wrap"><p>{text(credit(day, collected_by))} {footer}</p></div></footer>
</body>
</html>
"""

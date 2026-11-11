"""The page shell the shopper site's pages share: browse pages, product pages, the store types' front pages and the
root, method, record and basket pages (docs/shopper-site.md, "What a visitor sees", its paragraph on every page; the
plan's Tasks 16 and 17; docs/store-first.md, "What a visitor sees" 2 and "Q2's one script", the store-first plan's
Task 5).

Every page is one HTML file in English: `noindex` until the owner launches, light and dark colour schemes, one style
block (`basket.page.BASE_STYLE`, the rules the basket's pages share, then the page type's own), the site's one script
in the head (`SCRIPT_TAG`, `search.js` from the site's root), the header band, the main part, and the footer with the
credit line (`shopper.words.credit`) and the page's links. The band holds the site's name linking to the root, the
store line, and the chains' line (`shopper.words.CHAINS_LINE`) over the date line (`shopper.words.date_line`), both in
the date line's style. The store line is the pick link, `<a id="pick-link" href="<up>index.html#pick">`, "Pick your
store", on every page, a store type's front page included: search.js reads the site's root from its href and, once a
store type is picked and remembered, writes "<store type> · change" there (its header comment). A store type's front
page marks its main part with `data-store` (`store`), from which the script sets the pick. Nothing else is loaded,
from here or elsewhere. `up` is the path from the page's folder to the site's root, "../" for `p/`, `browse/` and
`store/` and "" for the root pages, so every link and the script resolve in the build.

The shell lives in its own module so that the front page's module can import the product pages' `page_path` while
the product pages import the shell: no import goes round in a circle.
"""
from collections.abc import Sequence
from datetime import date
from html import escape

from basket.page import BASE_STYLE
from shopper.words import CHAINS_LINE, SITE_NAME, credit, date_line

PICK = "Pick your store"           # the header's store line before a pick (store-first.md, "Words")
SCRIPT_TAG = '<script src="{up}search.js" defer></script>'      # the site's one script, in every page's head


def text(value: str) -> str:
    """`value` escaped for a text node; quotes stay as written."""
    return escape(value, quote=False)


def band(day: date, up: str) -> str:
    """The header band: the site's name linking to the root, the store line's pick link, then the chains' line and the
    date line (`basket.html`'s too, in the basket's frame)."""
    return (f'<header class="band"><div class="wrap"><a href="{up}index.html">{text(SITE_NAME)}</a>'
            f'<p class="store"><a id="pick-link" href="{up}index.html#pick">{text(PICK)}</a></p>'
            f'<p class="dateline">{text(CHAINS_LINE)}</p><p class="dateline">{text(date_line(day))}</p></div></header>')


def page(title: str, main: str, day: date, collected_by: str, links: Sequence[tuple[str, str]], style: str = "",
         up: str = "../", store: str | None = None) -> str:
    """A whole page: `title` for the browser's tab (never a chain's text, which no span can hold there), `main` as
    HTML, the footer's `links` as (label, path from the root), `style` the page type's own rules after the base,
    `store` the column key of a store type's front page (its main part's `data-store`), None on every other page."""
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
<style>{BASE_STYLE}{style}</style>
{SCRIPT_TAG.format(up=up)}
</head>
<body>
{band(day, up)}
{opening}
{main}
</main>
<footer><div class="wrap"><p>{text(credit(day, collected_by))} {footer}</p></div></footer>
</body>
</html>
"""

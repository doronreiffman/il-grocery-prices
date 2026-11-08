"""The page shell the shopper site's pages share: browse pages, product pages and the front, method, record and basket
pages (docs/shopper-site.md, "What a visitor sees", its paragraph on every page; the plan's Tasks 16 and 17).

Every page is one HTML file in English: `noindex` until the owner launches, light and dark colour schemes, one style
block (`basket.page.BASE_STYLE`, the rules the basket's pages share, then the page type's own), the header band with
the site's name linking to the front page over the date line (`shopper.words.date_line`), the main part, and the
footer with the credit line (`shopper.words.credit`) and the page's links. No script and nothing loaded from elsewhere:
`search.js`, the site's one script, belongs to the front page alone. `up` is the path from the page's folder to the
site's root, "../" for `p/` and `browse/` and "" for the root pages, so every link resolves in the build.

The shell lives in its own module so that the front page's module can import the product pages' `page_path` while
the product pages import the shell: no import goes round in a circle.
"""
from collections.abc import Sequence
from datetime import date
from html import escape

from basket.page import BASE_STYLE
from shopper.words import SITE_NAME, credit, date_line


def text(value: str) -> str:
    """`value` escaped for a text node; quotes stay as written."""
    return escape(value, quote=False)


def page(title: str, main: str, day: date, collected_by: str, links: Sequence[tuple[str, str]], style: str = "",
         up: str = "../") -> str:
    """A whole page: `title` for the browser's tab (never a chain's text, which no span can hold there), `main` as
    HTML, the footer's `links` as (label, path from the root), `style` the page type's own rules after the base."""
    footer = " · ".join(f'<a href="{up}{escape(path)}">{text(label)}</a>' for label, path in links)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>{text(title)}</title>
<style>{BASE_STYLE}{style}</style>
</head>
<body>
<header class="band"><div class="wrap"><a href="{up}index.html">{text(SITE_NAME)}</a>\
<p class="dateline">{text(date_line(day))}</p></div></header>
<main>
{main}
</main>
<footer><div class="wrap"><p>{text(credit(day, collected_by))} {footer}</p></div></footer>
</body>
</html>
"""

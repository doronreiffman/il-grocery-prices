"""The site check before every upload (`shopper.check`; the plan's Task 20 and its pre-flights' B5, B2, N3, N4 and N7):
a site `shopper.build.build_site` writes passes, and each fault put into it is named, alone where it can be, by its
file and its rule.

The site is tests/test_shop_build.py's tree (the basket's golden day and 40 days of Osher Ad), built once a module by
the hand build (the read-only freezer), with three things a real morning has and the tree lacks: Carrefour's
promotions not read today, with milk listed at both Carrefour columns, so P10's sentence is on both of milk's
Carrefour sections (question M (g)); a published ledger naming an earlier frozen day and the day itself, whose files
went up on their own day and are not in the build (B5); and a day scored 14 days back, listed in the site-day file's
`scored_days`, whose scores file is not in the build either (B2). Each test copies the site and breaks one thing; a
test of a store's name renames the store in a copy of the data's store list and builds the site again. Names,
barcodes and prices are synthetic."""
import gzip
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from basket.chains import SLUGS
from basket.check import NOT_ADVICE, NoPages
from basket.page import HE_SPAN
from basket.words import REVISED
from shopper.build import LEDGER, MARKER, build_site
from shopper.check import SEARCH_SCRIPT, check_site, main
from shopper.extract import extract_chain_day
from shopper.freeze import Frozen, ReadOnlyFreezer, scores_site_key, site_key
from shopper.product import page_path
from shopper.score import DaySummary, summary_json, summary_path
from shopper.search import CHAIN_SPAN
from shopper.siteday import site_day_path
from shopper.words import CREDIT_START, NEVER, ODDS_WORDS, date_line, no_odds_yet, unreadable
from test_build import BASKET, DAY, EGGS, MILK, golden_tree
from test_history import _row, _table
from test_shop_build import NOW, OSHER, STAMP, _frozen_file, _history, _published_ledger, _sha, _synced

ERROR = "carrefour: PromoFull7290055700007-001-002-20260101-0800.gz: RewardType 7 not seen in the chain's files"
EARLIER = DAY - timedelta(days=20)                    # a day frozen before, its file up since that day
T = DAY - timedelta(days=14)                          # the day scored on DAY, its scores file up since DAY
MILK_PAGE = page_path(MILK)
CITY, MARKET = "carrefour-city", "carrefour-market"
BODY = _frozen_file(((OSHER, EGGS),))
FROZEN = [Frozen(day=day, body=BODY, sha256=_sha(BODY), frozen_at=at, on_time=True, status="same")   # as published
          for day, at in ((EARLIER, datetime(2025, 12, 12, 10, 33, 7, tzinfo=timezone.utc)), (DAY, STAMP))]
ONLINE = "\u05e9\u05d5\u05e4\u05e8\u05e1\u05dc ONLINE"          # store 413's name in the tree's store list


def build(data: Path, site: Path) -> Path:
    """The site the hand build writes from `data`, beside the published ledger of the two frozen days."""
    _published_ledger(site, *FROZEN)
    build_site(DAY, data, site, NOW, "11:48", ReadOnlyFreezer(data), basket_path=BASKET, min_items=1)
    return site


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> tuple[Path, Path]:
    """The data folder and the site (the module's docstring), built once."""
    root = tmp_path_factory.mktemp("built")
    data = golden_tree(root / "golden")
    for slug in SLUGS:
        extract_chain_day(data / "raw", slug, DAY, data / "tables")
    _history(data, 40)
    _table(data / "tables", "carrefour", DAY, rows=[_row(CITY, MILK, "7.20"), _row(MARKET, MILK, "7.35")], error=ERROR)
    assert _synced(data, DAY, BODY, STAMP) == FROZEN[1]
    path = summary_path(data / "tables", T)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(summary_json(DaySummary(day=T, frozen_at=datetime(2025, 12, 18, 10, 33, tzinfo=timezone.utc),
                                             on_time=True, model_version="1", target_version="1", by_column={})))
    return data, build(data, root / "site")


@pytest.fixture(scope="module")
def built(tree) -> Path:
    return tree[1]


@pytest.fixture
def site(built, tmp_path) -> Path:
    """A copy of the built site, for one test to break."""
    return Path(shutil.copytree(built, tmp_path / "site"))


def replace(site: Path, name: str, old: str, new: str, count: int = 1) -> None:
    """The page `name` with its `count` copies of `old` replaced by `new` (count=0: every copy, at least one)."""
    path = site / name
    text = path.read_text(encoding="utf-8")
    assert (text.count(old) == count) if count else old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def add(site: Path, name: str, markup: str) -> None:
    """`markup` put at the top of the page's <main>."""
    replace(site, name, "<main>\n", f"<main>\n{markup}\n")


def in_section(site: Path, name: str, column: str, old: str, new: str) -> None:
    """In the page's section of `column`, its one copy of `old` replaced by `new`."""
    path = site / name
    text = path.read_text(encoding="utf-8")
    start = text.index(f'<section data-column="{column}"')
    end = text.index("</section>", start)
    section = text[start:end]
    assert section.count(old) == 1, old
    path.write_text(text[:start] + section.replace(old, new) + text[end:], encoding="utf-8")


def site_day(site: Path) -> dict:
    return json.loads(site_day_path(site, DAY).read_text(encoding="utf-8"))


def write_site_day(site: Path, found: dict) -> None:
    path = site / "site-days" / f"{found['day']}.json"
    path.write_text(json.dumps(found), encoding="utf-8")


# ---- the clean site ----

def test_a_clean_site_passes(site):
    found = site_day(site)
    assert found["chains"]["carrefour"]["promotions_error"] == {   # the premises (kind, file, field; never the value)
        "kind": "format changed", "file": "PromoFull7290055700007-001-002-20260101-0800.gz", "field": "RewardType"}
    assert not any(column["gate"]["open"] for column in found["columns"].values())
    milk = (site / MILK_PAGE).read_text(encoding="utf-8")
    for column in (CITY, MARKET):
        start = milk.index(f'<section data-column="{column}" id="c-{column}" data-chain="carrefour">')
        assert unreadable("carrefour") in milk[start:milk.index("</section>", start)]
    assert CHAIN_SPAN.split("{}")[0] in milk and SEARCH_SCRIPT in (site / "index.html").read_text(encoding="utf-8")
    assert check_site(site) == []


# ---- chains' spans ----

@pytest.mark.parametrize("words", ["a fake sale, we promise you", "the true price; trust us", "odds 1 in 3"])
def test_a_never_word_inside_a_chains_name_passes(site, words):
    """Call 11: a chain's text is read for markup only, so its own words count for no rule."""
    add(site, MILK_PAGE, CHAIN_SPAN.format(words))
    add(site, "method.html", CHAIN_SPAN.format(words))
    assert check_site(site) == []


@pytest.mark.parametrize("inside, more", [("<b>Milk</b>", []), ("Milk > water", []), ("Milk<", []),
                                          ("Milk<script>x</script>", [f"a script other than {SEARCH_SCRIPT}"])])
def test_markup_inside_a_chains_span_fails(site, inside, more):
    add(site, MILK_PAGE, CHAIN_SPAN.format(inside))
    assert check_site(site) == [f"{MILK_PAGE}: {problem}" for problem in ["markup inside a chain's span", *more]]


@pytest.mark.parametrize("store", ["Trick Mall US", ONLINE + " US"])
def test_a_store_left_out_by_rule_named_with_a_never_word_passes(tree, tmp_path, store):
    """Call 11 (the task review's finding 1, the re-review's probe): a store left out by rule is named on basket.html
    and method.html as its chain publishes it, Latin letters and all, whole in basket.page's span for a Hebrew name, and
    so read for markup only. The store is renamed in Shufersal's store list, and the site built again from it."""
    data = Path(shutil.copytree(tree[0], tmp_path / "data"))
    listed = next((data / "raw" / "chain=shufersal" / f"date={DAY.isoformat()}").glob("Stores*.gz"))
    xml = gzip.decompress(listed.read_bytes()).decode()
    assert xml.count(f"<StoreName>{ONLINE}</StoreName>") == 1
    listed.write_bytes(gzip.compress(xml.replace(ONLINE, store).encode(), mtime=0))
    site = build(data, tmp_path / "site")
    assert check_site(site) == []
    for name in ("basket.html", "method.html"):
        assert f"store 413 \u201c{HE_SPAN.format(store)}\u201d" in (site / name).read_text(encoding="utf-8"), name


def test_markup_inside_the_baskets_hebrew_span_fails(site):
    add(site, "basket.html", HE_SPAN.format("<b>Mall</b>"))
    assert check_site(site) == ["basket.html: markup inside a chain's span"]


def test_a_span_with_markup_is_still_read(site):
    """A span refused for its markup is not cut out: what it holds is read like the page's own words."""
    add(site, "browse/05d1.html", CHAIN_SPAN.format("<b>we</b>"))
    assert check_site(site) == ["browse/05d1.html: markup inside a chain's span", "browse/05d1.html: the word 'we'"]


def test_no_phrase_a_page_must_carry_comes_from_a_chains_span(site):
    replace(site, "index.html", "listed in the morning's files", "listed today", count=0)
    add(site, "index.html", CHAIN_SPAN.format("as listed in the morning's files"))
    assert check_site(site) == ["index.html: missing an always phrase: \"listed in the morning's files\""]


# ---- the NEVER list ----

@pytest.mark.parametrize("name, markup, phrase", [
    ("method.html", "<p>Not a scam.</p>", "scam"),
    ("method.html", "<p>The best <b>deal</b> in town.</p>", "best deal"),          # split by a tag: read
    ("index.html", '<p title="rip-off">x</p>', "rip-off"),                           # in an attribute: as written
    ("index.html", "<p>Expected&nbsp;to fall.</p>", "expected to"),                  # an entity
    (MILK_PAGE, "<p>You\nsave.</p>", "you save"),                                    # a line break, any case
    ("index.html", '<ul id="never-words"><li>scam</li></ul>', "scam"),               # the list on another page
])
def test_a_never_phrase_outside_the_method_list_fails(site, name, markup, phrase):
    add(site, name, markup)
    assert check_site(site) == [f"{name}: a never phrase: {phrase!r}"]


@pytest.mark.parametrize("change, missing, extra", [
    (("<li>scam</li>", ""), ["scam"], []),
    (("<li>scam</li>", "<li>scam</li><li>bargain</li>"), [], ["bargain"]),
    (("<li>scam</li><li>rip-off</li>", "<li>rip-off</li><li>scam</li>"), [], []),      # out of order
])
def test_a_method_list_short_of_one_fails(site, change, missing, extra):
    replace(site, "method.html", *change)
    assert check_site(site) == [f"method.html: the never list is not NEVER, in order (missing {missing}, extra {extra})"]


def test_a_method_page_without_the_never_list_fails(site):
    replace(site, "method.html", '<ul id="never-words">', '<ul id="words">')
    problems = check_site(site)
    assert problems[0] == 'method.html: no never list (<ul id="never-words">)'
    assert set(problems[1:]) == {f"method.html: a never phrase: {phrase!r}" for phrase in NEVER}


# ---- every page's notices, words and date ----

@pytest.mark.parametrize("name", ["index.html", MILK_PAGE, "browse/05d1.html", "basket.html", "record.html"])
def test_a_page_without_the_credit_line_fails(site, name):
    replace(site, name, CREDIT_START, "Prices from the files")
    assert check_site(site) == [f"{name}: missing the credit line"]


def test_a_page_without_not_shopping_advice_fails(site):
    replace(site, "method.html", NOT_ADVICE, "")
    assert check_site(site) == ['method.html: missing "Not shopping advice."']


def test_a_page_without_noindex_fails(site):
    replace(site, "browse/05d1.html", '<meta name="robots" content="noindex">\n', "")
    assert check_site(site) == ["browse/05d1.html: missing noindex"]


@pytest.mark.parametrize("name", [MILK_PAGE, "index.html", "basket.html"])
def test_we_our_us_fail(site, name):
    add(site, name, "<p>We list our prices for US.</p><p>Users focus on ours.</p>")    # inside words: not words
    assert check_site(site) == [f"{name}: the word 'our'", f"{name}: the word 'us'", f"{name}: the word 'we'"]


def test_basket_html_is_read_for_never_phrases_and_the_words(site):
    """Task 18's deferral: basket.html's own test skips them; the site check reads basket.html as every page."""
    add(site, "basket.html", "<p>It saves you time.</p>")
    assert check_site(site) == ["basket.html: a never phrase: 'saves you'"]


@pytest.mark.parametrize("body_too", [False, True])
def test_a_page_with_yesterdays_date_line_fails(site, body_too):
    """The anti-goal "a page that looks current but is not": the header's date line is the newest site-day file's day,
    whatever the rest of the page says."""
    replace(site, MILK_PAGE, date_line(DAY), date_line(DAY - timedelta(days=1)))
    if body_too:
        add(site, MILK_PAGE, f"<p>{date_line(DAY)}</p>")
    assert check_site(site) == [f"{MILK_PAGE}: no date line of 2026-01-01 in its header"]


def test_the_newest_site_day_file_gives_the_day(site):
    older = site_day(site) | {"day": (DAY - timedelta(days=1)).isoformat(), "scored_days": []}
    write_site_day(site, older)
    assert check_site(site) == []
    newer = site_day(site) | {"day": (DAY + timedelta(days=1)).isoformat()}
    write_site_day(site, newer)
    problems = check_site(site)
    assert "index.html: no date line of 2026-01-02 in its header" in problems
    assert len(problems) == len(list(site.rglob("*.html")))       # every page, from yesterday's files


def test_a_folder_without_a_site_day_file_fails(site):
    site_day_path(site, DAY).unlink()
    assert check_site(site) == [
        "method.html: a link to 'site-days/2026-01-01.json' reaches no file in the build",
        f"record.html: a link to '{scores_site_key(T)}' reaches no file in the build",
        "site-days/: no site-day file, so no day to read the pages by"]


# ---- ALWAYS ----

@pytest.mark.parametrize("name, phrase", [("index.html", "listed in the morning's files"),
                                          (MILK_PAGE, "before promotions"),
                                          (page_path(EGGS), "as listed in the chain's price files")])
def test_a_page_without_an_always_phrase_fails(site, name, phrase):
    replace(site, name, phrase, "x", count=0)
    assert check_site(site) == [f"{name}: missing an always phrase: {phrase!r}"]


def test_an_always_phrase_in_an_attribute_does_not_count(site):
    replace(site, "index.html", "listed in the morning's files", "listed today", count=0)
    add(site, "index.html", '<p title="listed in the morning\'s files">x</p>')
    assert check_site(site) == ["index.html: missing an always phrase: \"listed in the morning's files\""]


# ---- basket.html under the basket's index rules ----

def test_basket_html_without_a_baskets_always_phrase_fails(site):
    """N3: the basket's index rules name basket.html, not index.html."""
    phrase = "lowest listed total for this basket"
    replace(site, "basket.html", phrase, "lowest total", count=0)
    assert check_site(site) == [f"basket.html: missing an always phrase: {phrase!r}"]


def test_basket_html_saying_revised_on_an_unrevised_day_fails(site):
    add(site, "basket.html", "<p>Revised on 3 January 2026: a parser fix.</p>")
    assert check_site(site) == [f"basket.html: {REVISED!r} on a day not revised (days/2026-01-01.json)"]


# ---- scripts and other origins ----

@pytest.mark.parametrize("markup", ["<script>alert(1)</script>", '<SCRIPT defer src="search.js"></SCRIPT>',
                                    "<script\nsrc=search.js defer></script>"])
def test_a_second_script_fails(site, markup):
    add(site, "index.html", markup)
    assert check_site(site) == [f"index.html: a script other than {SEARCH_SCRIPT}"]


@pytest.mark.parametrize("markup, url", [
    ('<link rel="stylesheet" href="https://fonts.example.com/a.css">', "https://fonts.example.com/a.css"),
    ("<link rel=stylesheet href=//fonts.example.com/a.css>", "//fonts.example.com/a.css"),
    ('<img src="https://example.com/a.png" alt="">', "https://example.com/a.png"),
    ("<img src='data:image/png;base64,AAAA' alt=''>", "data:image/png;base64,AAAA"),
])
def test_an_outside_stylesheet_fails(site, markup, url):
    add(site, "index.html", markup)
    assert check_site(site) == [f"index.html: loads from another origin: {url!r}"]


def test_a_link_to_another_site_is_allowed(site):
    add(site, MILK_PAGE, '<a href="https://example.com/">x</a> <a href="mailto:a@example.com">y</a>')
    assert check_site(site) == []


# ---- product pages: sizes, F10 and P10 by column ----

@pytest.mark.parametrize("size, problems", [
    (60_000, []), (61_000, [f"{MILK_PAGE}: 61,000 bytes, over the 60,000 bytes a product page may hold"])])
def test_a_61_kb_product_page_fails(site, size, problems):
    """Task 16's carry: the refusal names the page, its size and the cap."""
    add(site, MILK_PAGE, " " * (size - (site / MILK_PAGE).stat().st_size - 1))
    assert (site / MILK_PAGE).stat().st_size == size
    assert check_site(site) == problems


@pytest.mark.parametrize("word", ODDS_WORDS)
def test_an_odds_word_in_a_closed_columns_section_fails(site, word):
    in_section(site, MILK_PAGE, OSHER, "<h2>Osher Ad</h2>", f"<h2>Osher Ad</h2><p>Say {word} 3.</p>")
    assert check_site(site) == [f"{MILK_PAGE}: the odds word {word!r} in the section of {OSHER}, its gate closed"]


def test_an_odds_word_inside_a_word_or_a_number_passes(site):
    """N4: the phrase "1 in" is matched whole, so "21 in" or "1 inch" holds none; a word is matched from its start, so a
    word that only ends in one ("perchance") holds none."""
    in_section(site, MILK_PAGE, OSHER, "<h2>Osher Ad</h2>",
               "<h2>Osher Ad</h2><p>On 21 in a row; 1 inch; perchance.</p>")
    assert check_site(site) == []


@pytest.mark.parametrize("said, word", [("forecasts", "forecast"), ("chances", "chance"), ("forecasting", "forecast"),
                                        ("Odds-on", "odds")])
def test_an_odds_words_other_forms_in_a_closed_columns_section_fail(site, said, word):
    """The design's odds words with their other forms: a word is matched from its start (the task review's point 2)."""
    in_section(site, MILK_PAGE, OSHER, "<h2>Osher Ad</h2>", f"<h2>Osher Ad</h2><p>The {said} here.</p>")
    assert check_site(site) == [f"{MILK_PAGE}: the odds word {word!r} in the section of {OSHER}, its gate closed"]


def test_f10_missing_fails(site):
    in_section(site, MILK_PAGE, CITY, f"<p>{no_odds_yet(CITY)}</p>", "")
    assert check_site(site) == [f"{MILK_PAGE}: no F10 sentence in the section of {CITY}, its gate closed"]


def test_f10_naming_another_column_fails(site):
    in_section(site, MILK_PAGE, CITY, no_odds_yet(CITY), no_odds_yet(MARKET))
    assert check_site(site) == [f"{MILK_PAGE}: no F10 sentence in the section of {CITY}, its gate closed",
                                f"{MILK_PAGE}: the odds word 'odds' in the section of {CITY}, its gate closed",
                                f"{MILK_PAGE}: the odds word 'forecast' in the section of {CITY}, its gate closed"]


def test_an_odds_word_outside_a_closed_columns_section_is_not_this_rule(site):
    add(site, MILK_PAGE, "<p>The forecast is on the record page.</p>")
    assert check_site(site) == []


@pytest.mark.parametrize("column", [CITY, MARKET])
def test_an_unread_chain_without_p10s_sentence_fails(site, column):
    """Question M (g): P10's sentence on every section of the chain's columns, both Carrefour's."""
    in_section(site, MILK_PAGE, column, f'<p class="warn">{unreadable("carrefour")}</p>', "")
    assert check_site(site) == [f"{MILK_PAGE}: no P10 sentence in the section of {column}: carrefour's promotions "
                                "were not read"]


@pytest.mark.parametrize("chain", ['', ' data-chain="osherad"'])
def test_p10_is_read_from_the_column_not_the_sections_chain_attribute(site, chain):
    """The final review's finding 11: a section of an unread chain's column without P10's sentence fails though its
    `data-chain` is missing or names another chain: the rule takes the chain from the column, so a markup slip cannot
    skip it."""
    in_section(site, MILK_PAGE, CITY, f'<p class="warn">{unreadable("carrefour")}</p>', "")
    replace(site, MILK_PAGE, f'<section data-column="{CITY}" id="c-{CITY}" data-chain="carrefour">',
            f'<section data-column="{CITY}" id="c-{CITY}"{chain}>')
    assert check_site(site) == [f"{MILK_PAGE}: no P10 sentence in the section of {CITY}: carrefour's promotions "
                                "were not read"]


def test_a_read_chain_needs_no_p10_sentence(site):
    found = site_day(site)
    found["chains"]["carrefour"]["promotions_error"] = None
    write_site_day(site, found)
    for column in (CITY, MARKET):
        in_section(site, MILK_PAGE, column, f'<p class="warn">{unreadable("carrefour")}</p>', "")
    assert check_site(site) == []


def test_a_section_of_a_column_the_site_day_file_does_not_name_fails(site):
    replace(site, MILK_PAGE, f'<section data-column="{OSHER}"', '<section data-column="osherad-online"')
    assert check_site(site) == [f"{MILK_PAGE}: a section of 'osherad-online', which the site-day file does not name"]


# ---- links ----

@pytest.mark.parametrize("name, markup, problem", [
    ("index.html", '<a href="nowhere.html">x</a>', "a link to 'nowhere.html' reaches no file in the build"),
    (MILK_PAGE, '<a href="../p/2000000000999.html">x</a>',
     "a link to '../p/2000000000999.html' reaches no file in the build"),
    (MILK_PAGE, '<a href="p/2000000000015.html">x</a>',              # relative to the page's folder
     "a link to 'p/2000000000015.html' reaches no file in the build"),
    ("browse/05d1.html", '<img src="logo.png" alt="">', "a link to 'logo.png' reaches no file in the build"),
    ("index.html", '<a href="browse/">x</a>', "a link to 'browse/' reaches no file in the build"),
    ("basket.html", '<a href="method.html#nowhere">x</a>', "a link to 'method.html#nowhere': method.html holds no id "
                                                           "'nowhere'"),
    (MILK_PAGE, '<a href="#nowhere">x</a>', f"a link to '#nowhere': {MILK_PAGE} holds no id 'nowhere'"),
    ("index.html", '<a href="../index.html">x</a>', "a link to '../index.html' leaves the build"),
    ("index.html", '<a href="/index.html">x</a>', "a link to '/index.html' from the root, not relative to the page"),
])
def test_a_link_to_a_missing_file_fails(site, name, markup, problem):
    add(site, name, markup)
    assert check_site(site) == [f"{name}: {problem}"]


@pytest.mark.parametrize("markup, url", [('<a href="https://[x]/">x</a>', "https://[x]/"),
                                         ('<img src="//[::1" alt="">', "//[::1")])
def test_a_link_that_is_not_a_url_is_named_not_a_crash(site, markup, url):
    """The task review's finding 2: `urlsplit` refuses a host in brackets that is no IPv6 address."""
    add(site, MILK_PAGE, markup)
    assert check_site(site) == [f"{MILK_PAGE}: a link that is not a URL: {url!r}"]


def test_a_page_that_is_not_utf8_is_named_not_a_crash(site):
    path = site / MILK_PAGE
    path.write_bytes(path.read_bytes().replace(b"<main>", b"<main>\xff", 1))
    assert check_site(site) == [f"{MILK_PAGE}: not UTF-8"]


def test_a_link_with_a_fragment_resolves_to_the_id(site):
    """Task 18's carry: basket.html's method link holds a fragment; the file must exist and hold that id."""
    assert 'href="method.html#headline-basket"' in (site / "basket.html").read_text(encoding="utf-8")
    add(site, MILK_PAGE, f'<a href="#c-{OSHER}">x</a> <a href="../method.html?x=1#headline-basket">y</a>')
    assert check_site(site) == []
    replace(site, "method.html", '<section id="headline-basket">', '<section id="basket-method">')
    assert check_site(site) == ["basket.html: a link to 'method.html#headline-basket': method.html holds no id "
                                "'headline-basket'",
                                f"{MILK_PAGE}: a link to '../method.html?x=1#headline-basket': method.html holds no id "
                                "'headline-basket'"]


def test_a_record_link_to_a_frozen_day_resolves_by_the_ledger(site):
    """B5: the record page links every frozen day's forecasts file, which went up on its own day; the build holds the
    ledger naming it, not the file."""
    record = (site / "record.html").read_text(encoding="utf-8")
    for day in (EARLIER, DAY):
        assert f'href="{site_key(day)}"' in record and not (site / site_key(day)).exists()
    assert check_site(site) == []


def test_a_record_link_to_a_day_the_ledger_lacks_fails(site):
    path = site / LEDGER
    path.write_text("".join(line for line in path.read_text().splitlines(keepends=True)
                            if not line.startswith(EARLIER.isoformat())))
    assert check_site(site) == [f"record.html: a link to '{site_key(EARLIER)}' reaches no file in the build"]


def test_a_record_link_with_no_ledger_fails(site):
    (site / LEDGER).unlink()
    assert check_site(site) == [f"record.html: a link to '{LEDGER}' reaches no file in the build",
                                f"record.html: a link to '{site_key(DAY)}' reaches no file in the build",
                                f"record.html: a link to '{site_key(EARLIER)}' reaches no file in the build"]


def test_a_record_link_to_a_day_scored_long_ago_resolves_by_the_newest_site_day(site):
    """B2: the newest site-day file lists every day scored to date, and the build folder (Lambda's) holds only it."""
    assert [path.name for path in (site / "site-days").iterdir()] == ["2026-01-01.json"]
    long_ago = DAY - timedelta(days=60)
    found = site_day(site)
    found["scored_days"] = [long_ago.isoformat(), T.isoformat()]
    write_site_day(site, found)
    replace(site, "record.html", f'<li><a href="{scores_site_key(T)}">',
            f'<li><a href="{scores_site_key(long_ago)}">x</a></li><li><a href="{scores_site_key(T)}">')
    assert not (site / scores_site_key(long_ago)).exists() and check_site(site) == []
    found["scored_days"] = [T.isoformat()]
    write_site_day(site, found)
    assert check_site(site) == [f"record.html: a link to '{scores_site_key(long_ago)}' reaches no file in the build"]


def test_a_scores_link_to_a_day_not_scored_fails(site):
    found = site_day(site)
    found["scored_days"] = []
    write_site_day(site, found)
    assert check_site(site) == [f"record.html: a link to '{scores_site_key(T)}' reaches no file in the build"]


# ---- search pieces ----

@pytest.mark.parametrize("piece", ["search/05d1.json", "search/05de-05d0.json"])
@pytest.mark.parametrize("size, over", [(150_000, False), (151_000, True)])
def test_a_151_kb_piece_fails(site, piece, size, over):
    (site / piece).write_bytes(b"[" + b" " * (size - 2) + b"]")
    assert check_site(site) == ([f"{piece}: {size:,} bytes, over the 150,000 bytes a search piece may hold"]
                                if over else [])


# ---- the folder ----

def test_a_folder_without_the_marker_fails(site):
    (site / MARKER).unlink()
    assert check_site(site) == [".shopper-site: missing; not a shopper site"]


def test_a_folder_without_the_index_fails(site):
    (site / "index.html").unlink()
    problems = check_site(site)
    assert problems[-1] == "index.html: missing"
    assert all(re.search(r"a link to '(\.\./)?index\.html' reaches no file in the build$", line)
               for line in problems[:-1])


def test_no_pages_exit_2(site, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    for page in site.rglob("*.html"):
        page.unlink()                                       # the marker, the data files and the pieces stay
    for folder in (empty, site, tmp_path / "absent"):
        with pytest.raises(NoPages):
            check_site(folder)
        assert main([str(folder)]) == 2
        assert capsys.readouterr().err == f"no HTML pages under {folder}\n"


def test_main_exit_codes(site, capsys):
    assert main([str(site)]) == 0
    assert capsys.readouterr() == ("", "")
    add(site, "index.html", "<p>We checked.</p>")
    (site / MARKER).unlink()
    assert main([str(site)]) == 1
    assert capsys.readouterr() == ("", "index.html: the word 'we'\n.shopper-site: missing; not a shopper site\n")

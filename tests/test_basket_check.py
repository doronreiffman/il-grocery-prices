"""The pre-upload check (`basket.check`): a site `build_site` writes passes; each fault put into a built page
is named, alone, by its file and its rule.

The sites are built from `tests/test_page.py`'s public day, basket and exclusions. (`tests/test_check.py` is
the collector's morning check.)
"""
import json
from pathlib import Path

import pytest

from basket.check import CREDIT_START, NOT_ADVICE, NoPages, check_site, main
from basket.page import build_site
from basket.words import REVISED, credit
from test_page import BASKET, DAY, EXCLUSIONS, a_public


def built(site: Path, public: dict | None = None) -> Path:
    """The site `build_site` writes into `site` for `public` (the test day by default), its day file included."""
    build_site(public or a_public(), BASKET, EXCLUSIONS, site, write_day=True)
    return site


def revised_public() -> dict:
    """The test day, revised on 3 November 2026 (B12)."""
    public = a_public()
    public["revisions"] = [{"run_id": "093000Z-basket-0a1b", "code_sha": "0123456789ab",
                            "built_at": "2026-11-02T09:30:00+00:00", "totals": {"ramilevy": "12.00"}}]
    public["revised"] = {"on": "2026-11-03", "reason": "a parser fix"}
    return public


def replace(site: Path, name: str, old: str, new: str) -> None:
    """The page `name` with its one copy of `old` replaced by `new`."""
    path = site / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def add(site: Path, name: str, markup: str) -> None:
    """`markup` put at the top of the page's <main>."""
    replace(site, name, "<main>\n", f"<main>\n{markup}\n")


def day_file(site: Path, day: str, revised: dict | None) -> None:
    (site / "days" / f"{day}.json").write_text(json.dumps({"day": day, "revised": revised}), encoding="utf-8")


def test_a_built_site_passes(tmp_path):
    assert check_site(built(tmp_path / "plain")) == []
    site = built(tmp_path / "revised", revised_public())
    assert REVISED in (site / "index.html").read_text(encoding="utf-8")
    assert check_site(site) == []


def test_the_credit_constants_are_the_credit_line_s():
    line = credit(DAY, "11:00")
    assert line.startswith(CREDIT_START + " section 30")
    assert line.endswith(" " + NOT_ADVICE)


def test_an_entity_cannot_hide_a_never_phrase(tmp_path):
    site = built(tmp_path / "site")
    replace(site, "index.html", "Listed totals, lowest first", "Listed totals, cheapest&nbsp;chain first")
    assert check_site(site) == ["index.html: a never phrase: 'cheapest chain'"]


@pytest.mark.parametrize("markup, phrase", [
    ("<p>It Saves You time.</p>", "saves you"),  # any case
    ("<p>Paid at the\n   till.</p>", "at the till"),  # a line break
    ("<p>Not real <b>prices</b>.</p>", "real prices"),  # split by a tag: found with tags stripped
    ('<p title="the chain charges">x</p>', "the chain charges"),  # in an attribute: found as written
    ("<p>you&#39;ll pay</p>", "you'll pay"),  # a numeric entity
    ("<p>you\u2019ll pay</p>", "you'll pay"),  # a right single quote, as typography writes the apostrophe
    ("<p>you&rsquo;ll pay</p>", "you'll pay"),  # the same as a named entity
    ('<p title="you\u2018ll pay">x</p>', "you'll pay"),  # a left single quote, in an attribute
])
def test_never_phrases_are_found_as_written_and_with_tags_stripped(tmp_path, markup, phrase):
    site = built(tmp_path / "site")
    add(site, "method.html", markup)
    assert check_site(site) == [f"method.html: a never phrase: {phrase!r}"]


def test_a_page_without_noindex_fails(tmp_path):
    site = built(tmp_path / "site")
    replace(site, "method.html", '<meta name="robots" content="noindex">\n', "")
    assert check_site(site) == ["method.html: missing noindex"]


@pytest.mark.parametrize("markup", ["<script>", '<SCRIPT src="a.js"></SCRIPT>'])
def test_a_script_fails(tmp_path, markup):
    site = built(tmp_path / "site")
    add(site, "index.html", markup)
    assert check_site(site) == ["index.html: a script"]


def test_we_our_us_are_found_as_whole_words(tmp_path):
    site = built(tmp_path / "we")
    add(site, "index.html", "<p>We list the totals.</p>")
    assert check_site(site) == ["index.html: the word 'we'"]
    site = built(tmp_path / "others")
    add(site, "method.html", '<p>Our basket, for US.</p><p>Users focus on weekly tours of ours.</p>'
                             '<p data-note="we" class="us">x</p>')  # inside words and in attributes: not read
    assert check_site(site) == ["method.html: the word 'our'", "method.html: the word 'us'"]


def test_a_page_without_the_credit_line_fails(tmp_path):
    site = built(tmp_path / "none")
    replace(site, "method.html", credit(DAY, "11:00"), "")
    assert check_site(site) == ["method.html: missing the credit line", 'method.html: missing "Not shopping advice."']
    site = built(tmp_path / "no-advice")
    replace(site, "index.html", NOT_ADVICE, "")
    assert check_site(site) == ['index.html: missing "Not shopping advice."']


def test_index_without_an_always_phrase_fails(tmp_path):
    site = built(tmp_path / "site")  # the method page lacks some ALWAYS phrases and passes
    replace(site, "index.html", "lowest listed total for this basket",
            '<span title="lowest listed total for this basket">lowest total</span>')  # an attribute does not count
    assert check_site(site) == ["index.html: missing an always phrase: 'lowest listed total for this basket'"]


def test_index_without_the_median_phrase_fails(tmp_path):
    site = built(tmp_path / "site")
    phrase = "the chain's median across its stores"
    replace(site, "index.html", phrase, "the median")
    assert check_site(site) == [f"index.html: missing an always phrase: {phrase!r}"]


def test_a_revised_day_without_revised_on_fails(tmp_path):
    site = built(tmp_path / "gone", revised_public())
    replace(site, "index.html", "Revised on 3 November", "Changed on 3 November")
    assert check_site(site) == ["index.html: no 'Revised on' on a revised day (days/2026-11-02.json)"]
    site = built(tmp_path / "attribute", revised_public())
    replace(site, "index.html", "Revised on 3 November", '<span title="Revised on">Changed on</span> 3 November')
    assert check_site(site) == ["index.html: no 'Revised on' on a revised day (days/2026-11-02.json)"]


def test_revised_on_an_unrevised_day_fails(tmp_path):
    site = built(tmp_path / "site")
    add(site, "index.html", "<p>Revised on 3 November 2026: a parser fix.</p>")
    assert check_site(site) == ["index.html: 'Revised on' on a day not revised (days/2026-11-02.json)"]


def test_the_newest_day_file_says_whether_the_day_is_revised(tmp_path):
    site = built(tmp_path / "site", revised_public())
    day_file(site, "2026-11-01", None)
    assert check_site(site) == []
    day_file(site, "2026-11-03", None)
    assert check_site(site) == ["index.html: 'Revised on' on a day not revised (days/2026-11-03.json)"]
    for each in (site / "days").iterdir():
        each.unlink()
    assert check_site(site) == ["index.html: 'Revised on' on a day not revised (no day file)"]


def test_a_folder_without_the_marker_fails(tmp_path):
    site = built(tmp_path / "site")
    (site / ".basket-site").unlink()
    assert check_site(site) == [".basket-site: missing; not a basket site"]


def test_a_folder_without_the_index_fails(tmp_path):
    site = built(tmp_path / "site")
    (site / "index.html").unlink()
    assert check_site(site) == ["index.html: missing"]


def test_no_pages_exit_2(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    site = built(tmp_path / "site")
    for page in ("index.html", "method.html"):
        (site / page).unlink()  # the marker and the day file stay
    for folder in (empty, site, tmp_path / "absent"):
        with pytest.raises(NoPages):
            check_site(folder)
        assert main([str(folder)]) == 2
        assert capsys.readouterr().err == f"no HTML pages under {folder}\n"


def test_main_exit_codes(tmp_path, capsys):
    site = built(tmp_path / "site")
    assert main([str(site)]) == 0
    assert capsys.readouterr() == ("", "")
    add(site, "index.html", "<p>We checked.</p><script>")
    assert main([str(site)]) == 1
    assert capsys.readouterr() == ("", "index.html: a script\nindex.html: the word 'we'\n")

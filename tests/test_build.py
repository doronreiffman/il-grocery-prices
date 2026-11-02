"""The build command: one day's three steps (extract, basket, page), the revision rule (B12), the golden day."""
import gzip
import json
import os
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path

import pytest

import collector.run
from basket import build
from basket.build import RevisionNeeded, build_day, main
from basket.chains import SLUGS
from basket.record import comparable
from basket.rules import LeftOut
from collector.run import RunResult, manifest_bytes
from collector.store import manifest_key

TESTS = Path(__file__).parent
BASKET = TESTS / "baskets" / "basket-test.json"
GOLDEN = TESTS / "golden" / "golden-day.json"
DAY = date(2026, 1, 1)
MILK, PASTA, EGGS = "2000000000015", "2000000000022", "2000000000039"  # the test basket's: 1 L, 500 g, 12 eggs
NOW = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)  # 14:05 in Israel
LATER = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)  # 11:00 in Israel, the next day
LAST = datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc)
PAST = 1_000_000_000_000_000_000  # a modification time, in ns, that no write of this test gives a file
CHAIN_IDS = {"shufersal": "7290027600007", "ramilevy": "7290058140886", "osherad": "7290103152017",
             "carrefour": "7290055700007", "yochananof": "7290803800003"}
SUB_CHAINS = {"shufersal": "001", "ramilevy": "001", "osherad": "001", "carrefour": "001", "yochananof": "000"}
# Each chain's two stores and their prices for MILK, PASTA and EGGS, every price a distinct one; None: the store
# does not list the code. A chain's price is the median of its stores', here their mean (B5). Totals: Osher Ad
# 6.15 + 4.90 + 11.60 = 22.65, Rami Levy 6.30 + 5.00 + 12.00 = 23.30, Yochananof 6.60 + 5.30 + 12.50 = 24.40
# (EGGS from store 1 alone, 1 of 2 stores, still half), Shufersal 7.00 + 5.70 + 13.10 = 25.80, Carrefour
# 7.35 + 6.105 + 13.70 = 27.155, shown 27.16; the gap (27.155 - 22.65) x 100 / 22.65 = 19.89, shown 20%.
PRICES = {
    "shufersal": {"001": ("6.90", "5.50", "12.90"), "002": ("7.10", "5.90", "13.30")},
    "ramilevy": {"001": ("6.20", "4.90", "11.90"), "002": ("6.40", "5.10", "12.10")},
    "osherad": {"001": ("6.00", "4.80", "11.40"), "002": ("6.30", "5.00", "11.80")},
    "carrefour": {"001": ("7.20", "5.95", "13.50"), "002": ("7.50", "6.26", "13.90")},
    "yochananof": {"001": ("6.50", "5.20", "12.50"), "002": ("6.70", "5.40", None)},
}
ITEMS = {MILK: ("חלב 3% 1 ליטר", "1", "ליטר"), PASTA: ("ספגטי 500 גרם", "500", "גרם"),
         EGGS: ("ביצים L 12", "12", "יחידות")}  # name, Quantity, UnitQty
# A placeholder row (B4) in Shufersal's store 1: a bag at one agora, not a basket code.
PLACEHOLDER = ("<Item><ItemCode>7290000000107</ItemCode><ItemName>שקית</ItemName><ItemPrice>0.01</ItemPrice>"
               "</Item>")
FIRST_TOTALS = {"carrefour": "27.16", "osherad": "22.65", "ramilevy": "23.30", "shufersal": "25.80",
                "yochananof": "24.40"}


def price_file(slug: str, prices: tuple[str | None, ...]) -> bytes:
    """A gzipped full price file in the common layout listing MILK, PASTA and EGGS at `prices`, None not listed."""
    items = "".join(
        f"<Item><ItemCode>{code}</ItemCode><ItemName>{ITEMS[code][0]}</ItemName><ItemPrice>{price}</ItemPrice>"
        f"<Quantity>{ITEMS[code][1]}</Quantity><UnitQty>{ITEMS[code][2]}</UnitQty>"
        f"<PriceUpdateTime>2025-12-31 08:00:00</PriceUpdateTime></Item>"
        for code, price in zip((MILK, PASTA, EGGS), prices) if price is not None)
    xml = (f'<?xml version="1.0" encoding="utf-8"?><Root><ChainId>{CHAIN_IDS[slug]}</ChainId><Items>{items}'
           "</Items></Root>")
    return gzip.compress(xml.encode(), mtime=0)


def price_file_name(slug: str, store: str) -> str:
    return f"PriceFull{CHAIN_IDS[slug]}-{SUB_CHAINS[slug]}-{store}-20260101-080000.gz"


def store_list(slug: str) -> tuple[str, bytes]:
    """The chain's `Stores` file and its name, in the layout its portal uses: Shufersal's gzipped UTF-8 with root
    <Chain> (and its online store 413, which the basket leaves out); plain UTF-16 with root <Root> for Rami Levy,
    Osher Ad and Carrefour; plain UTF-8 with the tags spelled `SubChainId` and `StoreId` for Yochananof."""
    chain_id = CHAIN_IDS[slug]
    if slug == "shufersal":
        stores = "".join(f"<Store><StoreID>{store}</StoreID><StoreType>1</StoreType><StoreName>סניף {store}</StoreName>"
                         "</Store>" for store in ("1", "2"))
        online = "<Store><StoreID>413</StoreID><StoreType>2</StoreType><StoreName>שופרסל ONLINE</StoreName></Store>"
        xml = (f'﻿<?xml version="1.0" encoding="UTF-8"?><Chain><ChainID>{chain_id}</ChainID><SubChains>'
               f"<SubChain><SubChainID>1</SubChainID><Stores>{stores}{online}</Stores></SubChain></SubChains></Chain>")
        return f"Stores{chain_id}-000-20260101-020.gz", gzip.compress(xml.encode(), mtime=0)
    if slug == "yochananof":
        stores = "".join(f"<Store><StoreId>{store}</StoreId><StoreName>סניף {store}</StoreName></Store>"
                         for store in ("1", "2"))
        xml = (f'<?xml version="1.0" encoding="utf-8"?><Root><ChainId>{chain_id}</ChainId><SubChains><SubChain>'
               f"<SubChainId>000</SubChainId><Stores>{stores}</Stores></SubChain></SubChains></Root>")
        return f"Stores{chain_id}-000-20260101-010000.xml", xml.encode()
    stores = "".join(f"<Store><StoreID>{store}</StoreID><StoreType>1</StoreType><StoreName>סניף {store}</StoreName>"
                     "</Store>" for store in ("001", "002"))
    xml = (f'<?xml version="1.0" encoding="UTF-16"?><Root><ChainID>{chain_id}</ChainID><SubChains><SubChain>'
           f"<SubChainID>001</SubChainID><Stores>{stores}</Stores></SubChain></SubChains></Root>")
    return f"Stores{chain_id}-000-20260101-050500.xml", xml.encode("utf-16")


def run_id_of(slug: str) -> str:
    """The run id of the chain's manifest in the golden tree."""
    return f"{SLUGS.index(slug) + 3:02d}0000Z-main-000{SLUGS.index(slug) + 1}"


def golden_tree(root: Path, prices: Mapping[str, Mapping[str, tuple[str | None, ...]]] = PRICES) -> Path:
    """The golden day under `root`/data: each chain's price files, its store list, and a manifest that stored
    them all; the data folder."""
    data = root / "data"
    for slug in SLUGS:
        files = {price_file_name(slug, store): price_file(slug, store_prices)
                 for store, store_prices in prices[slug].items()}
        if slug == "shufersal":
            name = price_file_name(slug, "001")
            body = gzip.decompress(files[name]).decode().replace("</Items>", PLACEHOLDER + "</Items>")
            files[name] = gzip.compress(body.encode(), mtime=0)
        list_name, list_bytes = store_list(slug)
        files[list_name] = list_bytes
        folder = data / "raw" / f"chain={slug}" / f"date={DAY.isoformat()}"
        folder.mkdir(parents=True)
        for name, body in files.items():
            (folder / name).write_bytes(body)
        stored = {name: {"outcome": "stored", "size": len(body), "sha256": "0" * 64} for name, body in files.items()}
        result = RunResult(chain=slug, run_id=run_id_of(slug), mode="main", day=DAY, kinds=["Stores", "PriceFull"],
                           files=stored)
        manifest = data / manifest_key(DAY, slug, run_id_of(slug))
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(manifest_bytes(result, "aaaaaaaaaaaa"))
    return data


def reprice(data: Path, slug: str, store: str, prices: tuple[str | None, ...]) -> None:
    """Replace a store's price file of the golden day with one at `prices`, under the same name."""
    (data / "raw" / f"chain={slug}" / f"date={DAY.isoformat()}" / price_file_name(slug, store)).write_bytes(
        price_file(slug, prices))


def build_at(data: Path, site: Path, now: datetime, revise: str | None = None, rebuild: bool = False, **more):
    return build_day(DAY, data, site, BASKET, now, revise, rebuild, min_items=1, **more)


def day_file(site: Path) -> Path:
    return site / "days" / f"{DAY.isoformat()}.json"


def read_index(site: Path) -> str:
    """The index page's text with entities unescaped and whitespace collapsed."""
    return " ".join(unescape((site / "index.html").read_text(encoding="utf-8")).split())


def records(data: Path) -> list[Path]:
    return sorted((data / "basket" / f"date={DAY.isoformat()}").glob("basket-*.json"))


# ---- the golden day ----

def test_golden_day_matches(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    outcome = build_at(data, site, NOW)
    public = json.loads(day_file(site).read_text(encoding="utf-8"))
    assert comparable(public) == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert (outcome.unchanged, outcome.revised) == (False, False)
    assert public["collected_by"] == "14:05"  # now, in Israel time (B11)
    assert public["run_id"].startswith("120500Z-basket-") and public["built_at"] == "2026-01-01T12:05:00+00:00"
    assert (public["revisions"], public["revised"]) == ([], None)
    private = json.loads(outcome.record_path.read_text(encoding="utf-8"))
    assert outcome.record_path == data / "basket" / "date=2026-01-01" / f"basket-{public['run_id']}.json"
    assert {slug: chain["manifests"] for slug, chain in private["chains"].items()} == {
        slug: [run_id_of(slug)] for slug in SLUGS}
    assert private["chains"]["shufersal"]["stores_with_file"] == ["1", "2"]  # store 413 is left out
    index = read_index(site)
    assert "Lowest listed total today: Osher Ad, ₪22.65." in index
    assert "Highest: Carrefour, ₪27.16, 20% more." in index
    assert outcome.headline_lines[0] == "Lowest listed total today: Osher Ad, ₪22.65."


def test_build_twice_is_unchanged(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    first = build_at(data, site, NOW)
    published = day_file(site).read_bytes()
    for page in (day_file(site), site / "index.html", site / "method.html"):
        os.utime(page, ns=(PAST, PAST))
    second = build_at(data, site, LATER)
    assert (second.unchanged, second.revised) == (True, False)
    assert day_file(site).read_bytes() == published  # the day file is left as it is (B12)
    assert day_file(site).stat().st_mtime_ns == PAST  # not even written again
    assert (site / "index.html").stat().st_mtime_ns != PAST and (site / "method.html").stat().st_mtime_ns != PAST
    assert "collected by 14:05 Israel time" in read_index(site)  # the pages show the day as published
    assert records(data) == sorted([first.record_path, second.record_path])  # every build of the day is kept
    assert first.record_path != second.record_path and second.record.collected_by == "11:00"


def test_refuses_to_overwrite_a_private_record(tmp_path, monkeypatch):
    monkeypatch.setattr(collector.run.secrets, "token_hex", lambda nbytes: "abcd")
    data, site = golden_tree(tmp_path), tmp_path / "site"
    first = build_at(data, site, NOW)
    written = first.record_path.read_bytes()
    with pytest.raises(FileExistsError):
        build_at(data, site, NOW, collected_by="09:00")
    assert first.record_path.read_bytes() == written and records(data) == [first.record_path]


def test_differing_numbers_without_reason_raise(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    build_at(data, site, NOW)
    published = day_file(site).read_bytes()
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))  # Yochananof's milk 6.60 -> 6.63
    with pytest.raises(RevisionNeeded) as raised:
        build_at(data, site, LATER, rebuild=True)
    message = str(raised.value)
    assert f"chains.yochananof.items.{MILK}" in message and "chains.yochananof.total" in message
    assert "headline" not in message and "chains.osherad" not in message  # only what differs is named
    assert "--revise" in message
    assert day_file(site).read_bytes() == published
    assert len(records(data)) == 2  # the refused run's record is kept all the same
    reprice(data, "carrefour", "002", ("7.50", "6.26", "14.10"))  # the highest total moves: the headline differs
    with pytest.raises(RevisionNeeded) as raised:
        build_at(data, site, LATER, rebuild=True)
    assert (f": chains.carrefour.items.{EGGS}, chains.carrefour.total, chains.yochananof.items.{MILK}, "
            "chains.yochananof.total, headline differ.") in str(raised.value)


def test_revise_keeps_first_totals_and_adds_the_line(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    first = build_at(data, site, NOW)
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))  # Yochananof 24.40 -> 24.43
    second = build_at(data, site, LATER, revise=" a parser fix \t", rebuild=True)
    assert (second.unchanged, second.revised) == (False, True)
    public = json.loads(day_file(site).read_text(encoding="utf-8"))
    assert public["chains"]["yochananof"]["total"] == "24.43" and public["run_id"] == second.record.run_id
    assert public["revised"] == {"on": "2026-01-02", "reason": "a parser fix"}  # the Israel date of now; stripped
    assert public["revisions"] == [{"run_id": first.record.run_id, "code_sha": first.record.code_sha,
                                    "built_at": first.record.built_at, "revised": None, "totals": FIRST_TOTALS}]
    assert ("Revised on 2 January 2026: a parser fix. First published: Osher Ad ₪22.65, Rami Levy ₪23.30, "
            "Yochananof ₪24.40, Shufersal ₪25.80, Carrefour ₪27.16.") in read_index(site)
    reprice(data, "yochananof", "001", ("6.60", "5.20", "12.50"))  # 24.43 -> 24.45
    build_at(data, site, LAST, revise="a second fix", rebuild=True)
    public = json.loads(day_file(site).read_text(encoding="utf-8"))
    assert [revision["totals"] for revision in public["revisions"]] == [
        FIRST_TOTALS, FIRST_TOTALS | {"yochananof": "24.43"}]  # the first publication stays first
    assert public["revisions"][1]["run_id"] == second.record.run_id
    # Every reason survives: the first revision's with the run it revised, the second's as the day's.
    assert [revision["revised"] for revision in public["revisions"]] == [
        None, {"on": "2026-01-02", "reason": "a parser fix"}]
    assert public["revised"] == {"on": "2026-01-03", "reason": "a second fix"}
    assert ("Revised on 3 January 2026: a second fix. Earlier: on 2 January 2026: a parser fix. First published: "
            "Osher Ad ₪22.65, Rami Levy ₪23.30, Yochananof ₪24.40,") in read_index(site)


def test_revise_then_unchanged(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    build_at(data, site, NOW)
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))
    build_at(data, site, LATER, revise="a one-line reason", rebuild=True)
    third = build_at(data, site, LAST)  # the revised numbers again
    assert (third.unchanged, third.revised) == (True, False)
    public = json.loads(day_file(site).read_text(encoding="utf-8"))
    assert len(public["revisions"]) == 1 and public["revisions"][0]["totals"] == FIRST_TOTALS
    assert public["revised"] == {"on": "2026-01-02", "reason": "a one-line reason"}
    assert "Revised on 2 January 2026: a one-line reason. First published: Osher Ad ₪22.65," in read_index(site)


def test_rebuild_flag_re_extracts(tmp_path):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    first = build_at(data, site, NOW)
    assert all(isinstance(first.extraction_seconds[slug], float) for slug in SLUGS)
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))
    kept = build_at(data, site, LATER)  # the tables are there: the new file is not read
    assert kept.extraction_seconds == {slug: None for slug in SLUGS}
    assert kept.unchanged and kept.record.chains["yochananof"].items[MILK].median == "6.60"
    rebuilt = build_at(data, site, LAST, revise="store 1's file replaced", rebuild=True)
    assert all(isinstance(rebuilt.extraction_seconds[slug], float) for slug in SLUGS)
    assert rebuilt.revised and rebuilt.record.chains["yochananof"].items[MILK].median == "6.63"


def test_a_store_whose_file_names_a_sub_chain_left_out_has_no_file(tmp_path):
    # As Shufersal's store 779 on 2026-11-02: in a kept sub-chain in the store list, Be (005) by its file's name.
    data, site = golden_tree(tmp_path), tmp_path / "site"
    folder = data / "raw" / "chain=shufersal" / f"date={DAY.isoformat()}"
    list_name, list_bytes = store_list("shufersal")
    store_3 = "<Store><StoreID>3</StoreID><StoreType>1</StoreType><StoreName>סניף 3</StoreName></Store>"
    online = "<Store><StoreID>413</StoreID>"
    listed = gzip.decompress(list_bytes).decode().replace(online, store_3 + online)
    (folder / list_name).write_bytes(gzip.compress(listed.encode(), mtime=0))
    (folder / f"PriceFull{CHAIN_IDS['shufersal']}-005-003-20260101-080000.gz").write_bytes(
        price_file("shufersal", ("1.00", "1.00", "1.00")))
    shufersal = build_at(data, site, NOW).record.chains["shufersal"]
    assert (shufersal.included, shufersal.with_file, shufersal.stores_with_file) == (3, 2, ("1", "2"))
    assert shufersal.items[MILK].listing == 2 and shufersal.total == "25.80"  # its rows are left out as well


def test_missing_basket_item_in_a_chain_is_left_out_not_a_crash(tmp_path):
    no_eggs = dict(PRICES, carrefour={"001": ("7.20", "5.95", None), "002": ("7.50", "6.26", None)})
    data, site = golden_tree(tmp_path, no_eggs), tmp_path / "site"
    record = build_at(data, site, NOW).record
    assert record.left_out == (LeftOut(EGGS, "coverage", {"carrefour": "0 of 2"}),)
    assert record.items_in == (MILK, PASTA) and EGGS not in record.chains["carrefour"].items
    assert {slug: chain.total for slug, chain in record.chains.items()} == {
        "carrefour": "13.46", "osherad": "11.05", "ramilevy": "11.30", "shufersal": "12.70", "yochananof": "11.90"}
    assert "Test eggs ×12: left out today" in read_index(site)


# ---- the command ----

def test_main_prints_each_chain_the_headline_and_what_it_did(tmp_path, capsys):
    data, site = golden_tree(tmp_path), tmp_path / "site"
    args = ["--day", "2026-01-01", "--data", str(data), "--site", str(site), "--basket", str(BASKET), "--min-items", "1"]
    assert main(args + ["--collected-by", "11:00"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"^osherad: extracted in \d+\.\d s, 6 rows$", out, re.MULTILINE)
    assert re.search(r"^shufersal: extracted in \d+\.\d s, 7 rows$", out, re.MULTILINE)  # and the placeholder
    assert "Lowest listed total today: Osher Ad, ₪22.65." in out and "Highest: Carrefour, ₪27.16, 20% more." in out
    assert f"published: {day_file(site)}" in out
    assert json.loads(day_file(site).read_text(encoding="utf-8"))["collected_by"] == "11:00"
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "osherad: table kept, 6 rows" in out and "unchanged:" in out
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))
    assert main(args + ["--rebuild", "--revise", "a parser fix"]) == 0
    assert f"revised: {day_file(site)}" in capsys.readouterr().out
    assert json.loads(day_file(site).read_text(encoding="utf-8"))["revised"]["reason"] == "a parser fix"


def test_main_exit_codes(tmp_path, capsys, monkeypatch):
    def args(data: Path, *more: str) -> list[str]:
        return ["--day", "2026-01-01", "--data", str(data), "--site", str(data.parent / "site"),
                "--basket", str(BASKET), *more]

    data = golden_tree(tmp_path / "bad-basket")
    assert main(args(data)) == 1  # the test basket's three items, under the default minimum of 25
    assert "3 items; the basket holds 25 to 40" in capsys.readouterr().err

    data = golden_tree(tmp_path / "revision")
    assert main(args(data, "--min-items", "1")) == 0
    reprice(data, "yochananof", "001", ("6.56", "5.20", "12.50"))
    capsys.readouterr()
    assert main(args(data, "--min-items", "1", "--rebuild")) == 1
    refused = capsys.readouterr().err
    assert f"chains.yochananof.items.{MILK}" in refused
    for blank in ("", "  \t ", "a parser fix\nand more", "a parser fix\rand more"):  # B12: one line of text
        assert main(args(data, "--min-items", "1", "--rebuild", "--revise", blank)) == 1
        assert capsys.readouterr().err == refused
    assert json.loads((data.parent / "site" / "days" / "2026-01-01.json").read_text(encoding="utf-8"))["revised"] is None

    data = golden_tree(tmp_path / "no-store-list")
    (data / "raw" / "chain=yochananof" / "date=2026-01-01" / store_list("yochananof")[0]).unlink()
    assert main(args(data, "--min-items", "1")) == 1
    assert "no store list for chain 'yochananof'" in capsys.readouterr().err

    # A chain's table is absent when its extraction did not run: here the extraction is stubbed to write nothing.
    monkeypatch.setattr(build, "extract", lambda raw_dir, slug, day, tables_dir: None)
    data = golden_tree(tmp_path / "no-table")
    assert main(args(data, "--min-items", "1")) == 1
    assert "no table for chain 'shufersal'" in capsys.readouterr().err

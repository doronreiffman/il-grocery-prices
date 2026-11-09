"""The columns: the nine store formats the shopper site shows, and which of a day's included stores each one holds
(docs/shopper-site.md, "The column")."""
import hashlib
import json
from collections import Counter
from datetime import date

from basket.chains import CARREFOUR_COLUMNS, SLUGS
from basket.extract import store_key
from basket.stores import Store, chain_stores, included
from shopper.columns import (BY_KEY, COLUMNS, FIXED_ON, FLOOR, FORMATS_ON_FIXED_DAY, chosen, column_of, columns_of,
                             members, outside, under_floor)

SHUFERSAL = "7290027600007"
TABLE = {"2": "carrefour-city", "3": "carrefour-market"}   # a synthetic table: the tests never lean on the real one


def _store(store_id: str, sub_chain: str | None = "1") -> Store:
    return Store(store_id, sub_chain, "סניף לדוגמה", "1")


def _shufersal(counts: dict[str, int]) -> list[Store]:
    """`counts[sub_chain]` stores in each sub-chain, numbered from 1 in the order given."""
    stores, number = [], 0
    for sub_chain, count in counts.items():
        for _ in range(count):
            number += 1
            stores.append(_store(str(number), sub_chain))
    return stores


def _stores_xml(stores: dict[str, str]) -> bytes:
    """A Shufersal store list: store id -> its sub-chain."""
    by_sub_chain: dict[str, list[str]] = {}
    for store, sub_chain in stores.items():
        by_sub_chain.setdefault(sub_chain, []).append(store)
    body = "".join(f"<SubChain><SubChainID>{sub}</SubChainID><Stores>"
                   + "".join(f"<Store><StoreID>{s}</StoreID><StoreName>סניף לדוגמה</StoreName><StoreType>1</StoreType>"
                             "</Store>" for s in ids) + "</Stores></SubChain>" for sub, ids in by_sub_chain.items())
    return f"<Chain><ChainID>{SHUFERSAL}</ChainID><SubChains>{body}</SubChains></Chain>".encode()


def test_the_nine_columns_their_keys_and_names():
    assert [(c.key, c.slug, c.name, c.sub_chain) for c in COLUMNS] == [
        ("carrefour-city", "carrefour", "Carrefour City", None),
        ("carrefour-market", "carrefour", "Carrefour Market", None),
        ("osherad", "osherad", "Osher Ad", None),
        ("ramilevy", "ramilevy", "Rami Levy", None),
        ("shufersal-deal", "shufersal", "Shufersal Deal", "2"),
        ("shufersal-express", "shufersal", "Shufersal Express", "7"),
        ("shufersal-sheli", "shufersal", "Shufersal Sheli", "1"),
        ("shufersal-universe", "shufersal", "Shufersal Universe", "8"),
        ("yochananof", "yochananof", "Yochananof", None)]
    assert [c.name for c in COLUMNS] == sorted(c.name for c in COLUMNS)  # in name order
    assert {c.slug for c in COLUMNS} == set(SLUGS)
    assert BY_KEY == {c.key: c for c in COLUMNS} and len(BY_KEY) == 9
    assert {slug: [c.key for c in columns_of(slug)] for slug in SLUGS} == {
        "shufersal": ["shufersal-deal", "shufersal-express", "shufersal-sheli", "shufersal-universe"],
        "ramilevy": ["ramilevy"], "osherad": ["osherad"],
        "carrefour": ["carrefour-city", "carrefour-market"], "yochananof": ["yochananof"]}


def test_the_floor_picks_the_nine_from_the_fixed_days_formats():
    assert (FLOOR, FIXED_ON) == (30, date(2026, 11, 7))
    split = {slug for slug in SLUGS if len(columns_of(slug)) > 1}
    assert set(FORMATS_ON_FIXED_DAY) == split == {"shufersal", "carrefour"}
    # Shufersal's included stores by the store list's sub-chain on 7 November, B2 applied
    assert FORMATS_ON_FIXED_DAY["shufersal"] == {"1": 71, "2": 76, "3": 2, "6": 22, "7": 94, "8": 31, "15": 9,
                                                 "18": 11, "32": 2, "36": 1}
    assert sum(FORMATS_ON_FIXED_DAY["shufersal"].values()) == 319
    assert chosen(FORMATS_ON_FIXED_DAY["shufersal"]) == {c.sub_chain for c in columns_of("shufersal")} \
        == {"1", "2", "7", "8"}
    assert "6" not in chosen(FORMATS_ON_FIXED_DAY["shufersal"])  # Yesh Chesed's 22 are under the floor
    # Carrefour's store groups, included stores over 5 and 7 November
    assert chosen(FORMATS_ON_FIXED_DAY["carrefour"]) == {c.key for c in columns_of("carrefour")}
    assert sum(FORMATS_ON_FIXED_DAY["carrefour"].values()) == 146
    assert (chosen({"a": 30, "b": 29}), chosen({"a": 30, "b": 29}, floor=29)) == ({"a"}, {"a", "b"})


def test_a_shufersal_store_takes_its_sub_chain_on_the_days_list():
    assert [column_of("shufersal", _store("1", sub)) for sub in ("1", "2", "7", "8", "6", "15", None)] == [
        "shufersal-sheli", "shufersal-deal", "shufersal-express", "shufersal-universe", None, None, None]


def test_a_store_that_moves_sub_chain_moves_column_that_day(tmp_path):
    lists = {date(2026, 11, 5): {"30": "2", "31": "2"}, date(2026, 11, 7): {"30": "8", "31": "2"}}
    for day, stores in lists.items():
        folder = tmp_path / "raw" / "chain=shufersal" / f"date={day.isoformat()}"
        folder.mkdir(parents=True)
        (folder / f"Stores{SHUFERSAL}-000-{day.strftime('%Y%m%d')}-050500.xml").write_bytes(_stores_xml(stores))
    found = {}
    for day in lists:
        stores, _ = chain_stores(tmp_path / "raw", "shufersal", day)
        found[day] = members("shufersal", stores, included(stores, "shufersal"))
    assert (found[date(2026, 11, 5)]["shufersal-deal"], found[date(2026, 11, 5)]["shufersal-universe"]) == (
        {"30", "31"}, set())
    assert (found[date(2026, 11, 7)]["shufersal-deal"], found[date(2026, 11, 7)]["shufersal-universe"]) == (
        {"31"}, {"30"})


def test_b2s_left_out_stores_are_in_no_column():
    stores = [_store("413", "2"), _store("93", "5"), _store("94", "5"), _store("30", "2")]  # 413 is Deal's on the list
    kept = included(stores, "shufersal")
    assert kept == {"30"}
    assert members("shufersal", stores, kept)["shufersal-deal"] == {"30"}
    assert all("413" not in ids and "93" not in ids for ids in members("shufersal", stores, kept).values())
    assert outside("shufersal", stores, kept) == []  # they are not included, so not "in no column" either


def test_store_779_is_a_member_of_express():
    # On the list it is Express's; its files are named under Be's 005, which B2's file-name half leaves out (Task 6)
    stores = [_store("779", "7"), _store("780", "7")]
    assert members("shufersal", stores, included(stores, "shufersal"))["shufersal-express"] == {"779", "780"}


def test_a_carrefour_store_not_in_the_table_is_in_no_column():
    stores = [_store("2"), _store("5"), _store("3"), _store("471"), _store("6")]
    kept = included(stores, "carrefour")  # 471, the online store, is left out by B2
    assert [column_of("carrefour", store, TABLE) for store in stores] == [
        "carrefour-city", None, "carrefour-market", None, None]
    assert members("carrefour", stores, kept, TABLE) == {"carrefour-city": {"2"}, "carrefour-market": {"3"}}
    assert outside("carrefour", stores, kept, TABLE) == [_store("5"), _store("6")]  # in the list's order


def test_the_stores_in_no_column_are_the_included_stores_members_leaves_out():
    # Task 7 passes the counted stores in no column to the promotions table (the second pre-flight's S2)
    stores = _shufersal({"1": 2, "2": 1, "6": 2, "15": 1, "5": 1}) + [_store("90", None)]
    kept = included(stores, "shufersal")
    placed = members("shufersal", stores, kept)
    assert {store.id for store in outside("shufersal", stores, kept)} == kept - set().union(*placed.values()) \
        == {"4", "5", "6", "90"}  # Yesh Chesed's two, the small format's one, a store outside any sub-chain
    stores = [_store("2"), _store("5"), _store("471")]
    kept = included(stores, "carrefour")
    assert {store.id for store in outside("carrefour", stores, kept, TABLE)} == \
        kept - set().union(*members("carrefour", stores, kept, TABLE).values()) == {"5"}


def test_a_whole_chain_is_one_column():
    stores = [_store("1", "1"), _store("39", "1"), _store("2", "2"), _store("3", None)]
    kept = included(stores, "ramilevy")  # store 039 is left out by B2
    assert members("ramilevy", stores, kept) == {"ramilevy": {"1", "2", "3"}}
    assert [column_of("ramilevy", store) for store in stores] == ["ramilevy"] * 4
    assert outside("ramilevy", stores, kept) == []
    for slug in ("osherad", "yochananof"):
        assert members(slug, stores, {"1", "2"}) == {slug: {"1", "2"}}


def test_members_names_every_column_of_the_chain():
    stores = _shufersal({"1": 3})
    assert members("shufersal", stores, included(stores, "shufersal")) == {
        "shufersal-deal": frozenset(), "shufersal-express": frozenset(), "shufersal-sheli": {"1", "2", "3"},
        "shufersal-universe": frozenset()}
    assert members("carrefour", [_store("5")], {"5"}, TABLE) == {"carrefour-city": frozenset(),
                                                                 "carrefour-market": frozenset()}
    assert members("yochananof", [], set()) == {"yochananof": frozenset()}


def test_a_column_under_the_floor_later_stays_a_column():
    stores = _shufersal({"1": 30, "2": 31, "7": 40, "8": 29})
    placed = members("shufersal", stores, included(stores, "shufersal"))
    assert {key: len(ids) for key, ids in placed.items()} == {
        "shufersal-deal": 31, "shufersal-express": 40, "shufersal-sheli": 30, "shufersal-universe": 29}
    whole = members("osherad", [_store(str(n)) for n in range(24)], {str(n) for n in range(24)})
    # Universe is named for the method page; Sheli at the floor is not; a whole chain is shown whatever its size
    assert under_floor({**placed, **whole}) == ["shufersal-universe"]
    assert under_floor(members("shufersal", [], set())) == ["shufersal-deal", "shufersal-express", "shufersal-sheli",
                                                            "shufersal-universe"]


def test_the_carrefour_table_is_the_measured_one():
    """The table as drawn on 2026-11-08: its counts, and a digest of its (store, column) pairs in order, so that a store
    moved from one column to the other, which keeps the counts, fails too (Task 4a's review)."""
    assert Counter(CARREFOUR_COLUMNS.values()) == {"carrefour-city": 75, "carrefour-market": 44}
    pairs = json.dumps(sorted(CARREFOUR_COLUMNS.items())).encode()
    assert hashlib.sha256(pairs).hexdigest() == "11d2d885e3000d5a7b5a02922615780b143d7b6ebec0e07c1411b25c669a7d5a"
    assert len(CARREFOUR_COLUMNS) == 75 + 44  # none in both
    assert all(key == store_key(key) and key.isdigit() for key in CARREFOUR_COLUMNS)  # store keys, no leading zero
    assert not {"471", "472", "473"} & set(CARREFOUR_COLUMNS)  # the online store and the type-2 stores
    assert {c.key for c in columns_of("carrefour")} == set(CARREFOUR_COLUMNS.values())

"""The word index and its Python lookup (`shopper.wordindex`; the product-names plan's Task 1): tokens, size words, the
word entry, the node files and their manifest, `pick`, the seven-step ranking, and `lookup`, checked against a brute-force
answer over a seeded synthetic registry (`tests/words_registry.py`). Names and barcodes are synthetic."""
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from itertools import combinations

import pytest

from shopper.history import Covered
from shopper.search import PIECE_MAX, normalize, pieces, today_lookup
from shopper.wordindex import (EMPTY_MANIFEST, FOLDER, MANIFEST, MANIFEST_MAX, SHOWN, TOP, VERSION, Extra, Found, Node,
                               as_word_entry, entry, files, lookup, node_key, order_key, pick, size_words, step, tokens)
from words_registry import brute, extras, matches, registry

DAY = date(2026, 10, 1)


def _item(code, names, size=None):
    """A covered product; its title the longest name, a tie to the first in code-point order, as the registry has it."""
    title = min(names.values(), key=lambda name: (-len(name), name))
    return Covered(code=code, title=title, names=names, size=size, first_covered=DAY, last_wide={})


def _catalogue(*items):
    return {item.code: item for item in items}


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _today_entries(covered):
    """Every product's entry in today's layout, by barcode, read from today's own pieces."""
    built = pieces(covered)
    return {item[0]: item for key, body in built.items() if key != "search/pieces.json" for item in json.loads(body)}


def _ranked(query, today):
    """`today` ranked, every entry read as all-published names."""
    return sorted((as_word_entry(item) for item in today), key=lambda item: order_key(query, item))


def _codes(found):
    return [item[0] for item in found.shown]


def _milk_and_chocolate(n):
    """`n` products, half "חלב שוקולד <n>" and half "שוקולד חלב <n>": "חלב" and "שוקולד" are whole tokens, "שוק" and
    "שוקו" only starts."""
    return _catalogue(*(_item(f"72900000{number:05d}",
                              {"ramilevy": f"חלב שוקולד {number}" if number % 2 else f"שוקולד חלב {number}"})
                        for number in range(n)))


# tokens and size words

def test_tokens():
    assert tokens("דאו.דריי") == ["דאו.דריי", "דאו", "דריי"]
    assert tokens("3% שומן") == ["3%", "3", "שומן"]
    assert tokens("חלב") == ["חלב"]
    assert tokens("a-b c") == ["a-b", "a", "b", "c"]
    assert tokens("פִיתה") == ["פִיתה", "פ", "יתה"]               # a Hebrew point (Mn) splits the word
    assert tokens("\U0001d400lpha.b") == ["\U0001d400lpha.b", "\U0001d400lpha", "b"]   # one code point outside the basic plane
    assert tokens("a.b a b.a") == ["a.b", "a", "b", "b.a"]                     # each once, in order of first sight
    assert tokens("%") == ["%"]                                                # a word with no letter or digit is a token
    assert tokens("") == []


@pytest.mark.parametrize("size, expected", [
    ((Decimal("80"), "gml"), ["80g", "80ml"]),
    ((Decimal("999"), "gml"), ["999g", "999ml"]),
    ((Decimal("1500"), "gml"), ["1500g", "1500ml", "1.5kg", "1.5l"]),
    ((Decimal("1000"), "gml"), ["1000g", "1000ml", "1kg", "1l"]),
    ((Decimal("6"), "unit"), []),
    (None, []),
])
def test_size_words(size, expected):
    assert size_words(size) == expected


# the word entry

def test_entry():
    names = {"carrefour-city": "קוטג' 5% 250 גר", "ramilevy": "קוטג תנובה 5%"}
    item = _item("7290000000017", names, (Decimal("250"), "gml"))
    extra = Extra("Tnuva cottage cheese 5%", ("Tnuva cottage cheese 5%", "גבינת קוטג"))
    assert entry(item, extra) == ["7290000000017", "קוטג' 5% 250 גר", "Tnuva cottage cheese 5%", 4, "קוטג 5% 250 גר",
                                  "קוטג תנובה 5%", "250g", "250ml", "tnuva cottage cheese 5%", "גבינת קוטג"]
    assert entry(item, None) == ["7290000000017", "קוטג' 5% 250 גר", "", 4, "קוטג 5% 250 גר", "קוטג תנובה 5%",
                                 "250g", "250ml"]


def test_entry_files_each_name_once():
    item = _item("7290000000024", {"ramilevy": "250g", "osherad": "חלב", "yochananof": "חלב"}, (Decimal("250"), "gml"))
    held = Extra("", ("Milk", "חלב", "MILK", "'", "חלב טרי"))     # held: the English is searched, not shown
    assert entry(item, held) == ["7290000000024", "250g", "", 3, "250g", "חלב", "250ml", "milk", "חלב טרי"]


def test_as_word_entry():
    assert as_word_entry(["7290000000017", "קוטג' 5%", "קוטג 5%", "קוטג תנובה"]) == [
        "7290000000017", "קוטג' 5%", "", 2, "קוטג 5%", "קוטג תנובה"]


# node keys

def test_node_key():
    assert FOLDER == "search/w" and MANIFEST == "search/w/manifest.json"
    assert node_key("ab") == "search/w/0061-0062.json"
    assert node_key("ab", 0) == "search/w/0061-0062.0.json"
    assert node_key("חלב", 12) == "search/w/05d7-05dc-05d1.12.json"
    assert node_key("\U0001d400l") == "search/w/1d400-006c.json"


def test_the_manifest_constants():
    assert MANIFEST_MAX == PIECE_MAX
    assert json.loads(EMPTY_MANIFEST) == {"v": VERSION, "nodes": {}} and _encode(json.loads(EMPTY_MANIFEST)) == EMPTY_MANIFEST
    assert list(files({})) == [(MANIFEST, EMPTY_MANIFEST)]                    # no product, no node


# the files

@pytest.fixture(scope="module")
def world():
    """The 400-product registry with its model names, its word entries, today's entries and the index at both limits."""
    covered = registry(400, "q50-a")
    extra = extras(covered, "q50-a")
    entries = sorted((entry(item, extra.get(code)) for code, item in covered.items()), key=lambda item: (item[4], item[0]))
    built = {limit: list(files(covered, extra, limit)) for limit in (600, 2000)}
    return covered, extra, entries, built


@pytest.mark.parametrize("limit", [600, 2000])
def test_files_are_pure_and_within_the_limit(world, limit):
    covered, extra, entries, built = world
    assert built[limit] == list(files(dict(reversed(covered.items())), dict(reversed(extra.items())), limit))
    *nodes, (last, body) = built[limit]
    assert last == MANIFEST
    manifest = json.loads(body)
    assert list(manifest) == ["v", "nodes"] and manifest["v"] == VERSION
    keys = [key for key, _ in nodes]
    assert len(keys) == len(set(keys))
    implied = {node_key(prefix) if parts == 0 else node_key(prefix, part)
               for prefix, (_, parts, _) in manifest["nodes"].items() for part in range(max(parts, 1))}
    assert set(keys) == implied
    for _, data in nodes:
        assert len(data) <= limit and _encode(json.loads(data)) == data
    # Every two-character start of a token is a node, and a big node has a child for each next character.
    starts, wholes = defaultdict(set), defaultdict(set)
    for item in entries:
        for token in {token for name in item[4:] for token in tokens(name)}:
            wholes[token].add(item[0])
            for end in range(2, len(token) + 1):
                starts[token[:end]].add(item[0])
    expected = {prefix for prefix in starts if len(prefix) == 2}
    for prefix, (_, parts, _) in manifest["nodes"].items():
        if parts:
            expected |= {start for start in starts if len(start) == len(prefix) + 1 and start.startswith(prefix)}
    assert set(manifest["nodes"]) == expected
    # Each node's count and whole, and what its files hold.
    held = dict(nodes)
    kinds = Counter()
    for prefix, (count, parts, whole) in manifest["nodes"].items():
        members = [item for item in entries if item[0] in starts[prefix]]
        assert count == len(members) and whole == int(bool(wholes[prefix]))
        if parts == 0:
            assert json.loads(held[node_key(prefix)]) == members
            kinds["leaf"] += 1
            continue
        assert len(_encode(members)) > limit
        ranked = sorted(members, key=lambda item: order_key(prefix, item))
        stored = [item for part in range(parts) for item in json.loads(held[node_key(prefix, part)])]
        assert stored == (ranked if whole else ranked[:TOP])
        kinds["whole" if whole else "start over 50" if count > TOP else "start"] += 1
    assert set(kinds) == {"leaf", "whole", "start", "start over 50"}


def test_a_whole_token_keeps_every_product_and_a_start_its_first_50():
    covered = _milk_and_chocolate(120)
    built = dict(files(covered, None, 2000))
    nodes = json.loads(built[MANIFEST])["nodes"]
    entries = [entry(item, None) for item in covered.values()]

    def stored(prefix):
        return [item for part in range(nodes[prefix][1]) for item in json.loads(built[node_key(prefix, part)])]

    assert nodes["חלב"][0] == 120 and nodes["חלב"][1] > 1 and nodes["חלב"][2] == 1
    assert stored("חלב") == sorted(entries, key=lambda item: order_key("חלב", item))
    ranked = sorted(entries, key=lambda item: order_key("שוק", item))
    assert nodes["שוק"][0] == 120 and nodes["שוק"][2] == 0
    assert stored("שוק") == ranked[:TOP]
    assert ranked[:TOP] != sorted(entries, key=lambda item: (item[4], item[0]))[:TOP]    # ranked, not in name order

    # One word on a whole token: its parts in order until 50 are found.
    one = lookup(built.get, "חלב", [])
    needed, total = 0, 0
    while total < SHOWN:
        total += len(json.loads(built[node_key("חלב", needed)]))
        needed += 1
    assert needed < nodes["חלב"][1]
    assert one == Found(stored("חלב")[:SHOWN], False, [MANIFEST, *(node_key("חלב", part) for part in range(needed))])
    # One word on a part-typed start: its first 50 are the 50 shown, not flagged.
    assert lookup(built.get, "שוק", []) == Found(ranked[:SHOWN], False,
                                                 [MANIFEST, *(node_key("שוק", part) for part in range(nodes["שוק"][1]))])
    # Several words, one a whole token: the whole token's every part, re-ranked by the search, not flagged.
    both = lookup(built.get, "חלב שוק", [])
    assert not both.flagged and _codes(both) == brute(entries, "חלב שוק", [])
    assert both.read == [MANIFEST, *(node_key("חלב", part) for part in range(nodes["חלב"][1]))]
    # Several words, each a part-typed start of more than 50 products: the first 50 re-ranked, flagged.
    starts = lookup(built.get, "שוקו שוק", [])
    assert starts.flagged and all(matches(item, "שוקו שוק") for item in starts.shown)
    assert starts.shown == sorted(stored("שוק"), key=lambda item: order_key("שוקו שוק", item))


# pick

NODES = {
    "ab": [10, 2, 0],       # a big start
    "abc": [3, 0, 0],       # a leaf under it
    "abd": [8, 3, 1],       # a big whole token under it
    "abde": [2, 0, 1],
    "cd": [5, 0, 1],        # a leaf
    "ef": [90, 4, 1],       # a big whole token
    "gh": [70, 3, 0],       # a big start with fewer products
    "pq": [3, 0, 0],
    "pr": [3, 0, 0],
    "xy": [100, 0, 0],      # a leaf with many products
    "xz": [3, 0, 0],
}


@pytest.mark.parametrize("words, expected", [
    (["abc"], Node("leaf", "abc", 3, 0)),
    (["abcz"], Node("leaf", "abc", 3, 0)),          # a leaf ends the walk
    (["ab"], Node("start", "ab", 10, 2)),           # a big node ends it where the word ends
    (["abd"], Node("whole", "abd", 8, 3)),
    (["abde"], Node("leaf", "abde", 2, 0)),
    (["ax"], None),                                 # a start missing from the manifest: no token starts with the word
    (["abx"], None),
    (["cd", "ax"], None),
    (["cd", "abc"], Node("leaf", "abc", 3, 0)),     # the leaf with the fewest products
    (["abc", "cd"], Node("leaf", "abc", 3, 0)),
    (["xy", "abd"], Node("leaf", "xy", 100, 0)),    # a leaf before a whole token
    (["ef", "gh"], Node("whole", "ef", 90, 4)),     # a whole token before a part-typed start
    (["ef", "abd"], Node("whole", "abd", 8, 3)),
    (["gh", "ab"], Node("start", "ab", 10, 2)),
    (["abc", "xz"], Node("leaf", "xz", 3, 0)),      # a tie: the shorter prefix
    (["pr", "pq"], Node("leaf", "pq", 3, 0)),       # then code-point order
    (["a", "abc"], Node("leaf", "abc", 3, 0)),      # a one-character word walks nothing
    (["a", "b"], None),
])
def test_pick(words, expected):
    assert pick({"v": VERSION, "nodes": NODES}, words) == expected


# the steps

def _word(code, names, published):
    return [code, names[0], "", published, *names]


# The crafted entries and their steps for STEP_QUERY; the script's twin is held to the same (tests/test_search_js.py).
STEP_QUERY = "Milk 3"
STEP_CASES = [
    (_word("7290000000101", ["milk 3"], 1), (1, 0)),
    (_word("7290000000102", ["fresh cream", "milk 3"], 1), (1, 1)),
    (_word("7290000000201", ["milk 3% fat"], 1), (2, 0)),
    (_word("7290000000301", ["fresh milk", "milk 3 pack"], 2), (3, 0)),
    (_word("7290000000302", ["fresh milk", "milk 3 pack"], 1), (3, 1)),
    (_word("7290000000401", ["fresh milk 3%"], 1), (4, 0)),
    (_word("7290000000402", ["cream", "fresh milk 3%"], 1), (4, 1)),
    (_word("7290000000501", ["fresh milky 30"], 1), (5, 0)),
    (_word("7290000000502", ["cream", "fresh milky 30"], 1), (5, 1)),
    (_word("7290000000601", ["fresh milk", "pack of 3"], 2), (6, 0)),     # whole tokens, but in two names
    (_word("7290000000602", ["fresh milk", "pack of 3"], 1), (6, 1)),     # one word in the model's name only
    (_word("7290000000701", ["semimilk 3"], 1), (7, 0)),
    (_word("7290000000702", ["cream", "semimilk 3"], 1), (7, 1)),
    (_word("7290000000703", ["cream"], 1), (7, 1)),
]
STEP_TIES = [_word("7290000000404", ["b fresh milk 3%"], 1), _word("7290000000403", ["a fresh milk 3%"], 1),
             _word("7290000000405", ["a fresh milk 3%"], 1)]


def test_steps():
    query, cases, ties = STEP_QUERY, STEP_CASES, STEP_TIES
    for item, expected in cases:
        assert step(query, item) == expected, item
    assert order_key(query, ties[0]) == (4, 0, "b fresh milk 3%", "7290000000404")
    everything = [item for item, _ in cases] + ties
    expected = ["7290000000101", "7290000000102", "7290000000201", "7290000000301", "7290000000302",
                "7290000000403", "7290000000405", "7290000000404", "7290000000401", "7290000000402",
                "7290000000501", "7290000000502", "7290000000601", "7290000000602",
                "7290000000701", "7290000000702", "7290000000703"]
    assert [item[0] for item in sorted(reversed(everything), key=lambda item: order_key(query, item))] == expected


# lookup

def test_every_shown_entry_is_in_the_word_layout():
    a = _item("7290000000031", {"ramilevy": "חלב תנובה"})
    b = _item("7290000000048", {"ramilevy": "משקה חלב"})
    d = _item("7290000000055", {"ramilevy": "חחלב"})          # holds the search inside a word, never at a token's start
    covered = _catalogue(a, b, d)
    extra = {code: Extra(f"English {number}", (f"English {number}",)) for number, code in enumerate(covered)}
    today_entries = _today_entries(covered)
    today = [today_entries[a.code], today_entries[d.code]]
    found = lookup(dict(files(covered, extra)).get, "חלב", today)
    assert _codes(found) == [a.code, b.code, d.code] and not found.flagged
    shown = {item[0]: item for item in found.shown}
    assert shown[d.code] == as_word_entry(today_entries[d.code]) and shown[d.code][2] == ""   # shown from today's entry
    assert shown[a.code] == entry(a, extra[a.code])           # in today, and held by the word file read: its word entry
    assert shown[b.code] == entry(b, extra[b.code])
    for item in found.shown:
        assert type(item[3]) is int and 1 <= item[3] <= len(item) - 4 and all(type(name) is str for name in item[4:])


def test_another_manifest_version_reads_no_word_file():
    a, b = _item("7290000000031", {"ramilevy": "חלב תנובה"}), _item("7290000000048", {"ramilevy": "משקה חלב"})
    covered = _catalogue(a, b)
    built = dict(files(covered))
    today = [_today_entries(covered)[a.code]]
    assert _codes(lookup(built.get, "חלב", today)) == [a.code, b.code]            # version 1 adds the word match
    other = _encode({**json.loads(built[MANIFEST]), "v": 2})
    assert lookup({**built, MANIFEST: other}.get, "חלב", today) == Found(_ranked("חלב", today), False, [MANIFEST])


def test_a_missing_part_shows_todays_list():
    covered = _milk_and_chocolate(120)
    built = dict(files(covered, None, 2000))
    nodes = json.loads(built[MANIFEST])["nodes"]
    today_entries = _today_entries(covered)
    today = [today_entries["7290000000000"], today_entries["7290000000001"]]
    assert lookup(built.get, "שוקו שוק", today).flagged
    for query, prefix in (("חלב", "חלב"), ("חלב שוק", "חלב"), ("שוקו שוק", "שוק")):
        assert nodes[prefix][1] > 1
        for broken in (None, b"[1", b"\xff", b'{"a": 1}'):
            found = lookup({**built, node_key(prefix, 1): broken}.get, query, today)
            assert found == Found(_ranked(query, today), False, [MANIFEST, node_key(prefix, 0), node_key(prefix, 1)])
    # A leaf missing: "17" starts one product's tokens only.
    assert nodes["17"] == [1, 0, 1]
    assert _codes(lookup(built.get, "חלב 17", today)) == ["7290000000017", "7290000000001", "7290000000000"]
    found = lookup({**built, node_key("17"): None}.get, "חלב 17", today)
    assert found == Found(_ranked("חלב 17", today), False, [MANIFEST, node_key("17")])
    # The manifest missing, unreadable, not an object, or naming no node.
    for broken in (None, b"{", b"\xff", b"[1]", EMPTY_MANIFEST):
        found = lookup({**built, MANIFEST: broken}.get, "חלב", today)
        assert found == Found(_ranked("חלב", today), False, [MANIFEST])


def test_parts_from_two_builds_show_each_product_once():
    covered = _milk_and_chocolate(120)
    built = dict(files(covered, None, 2000))
    today = [_today_entries(covered)["7290000000000"]]
    mixed = {**built, node_key("חלב", 1): built[node_key("חלב", 0)]}     # part 1 as an earlier build left it
    for query in ("חלב", "חלב שוק"):
        codes = _codes(lookup(mixed.get, query, today))
        assert len(codes) == SHOWN and len(set(codes)) == SHOWN and codes.count("7290000000000") == 1


def test_one_character_words_and_a_full_today_read_no_file():
    def read(key):
        raise AssertionError(f"read {key}")

    covered = _milk_and_chocolate(120)
    today_entries = sorted(_today_entries(covered).values(), key=lambda item: (item[2], item[0]))
    for query, today in (("2 מ", today_entries[:3]), ("ח ש", []), ("", []), ("  ", today_entries[:1]),
                         ("חלב", today_entries[:SHOWN]), ("חלב שוק", today_entries[:SHOWN])):
        assert lookup(read, query, today) == Found(_ranked(query, today), False, [])


def _searches(covered, extra, entries):
    """Every name typed in full, every title typed one letter at a time from two, every pair of a product's tokens and
    each pair cut to two letters each, and searches of one-character words."""
    by_code = {item[0]: item for item in entries}
    found = {"2 מ", "3 ח", "ח ש", "a c", "qq", "חלב qq"}
    for code, item in covered.items():
        found.update(item.names.values())
        found.update(extra[code].names if code in extra else ())
        found.update(item.title[:end] for end in range(2, len(item.title) + 1))
        words = sorted({token for name in by_code[code][4:] for token in tokens(name)})
        for first, second in combinations(words, 2):
            found.update((f"{first} {second}", f"{first[:2]} {second[:2]}"))
        found.add(" ".join(word[:1] for word in words[:2]))
    return sorted(found)


def test_lookup_is_brute_force(world):
    covered, extra, entries, built = world
    by_code = {item[0]: item for item in entries}
    todays = pieces(covered)              # today's lookup reads today's own pieces of the same registry
    reads = {limit: dict(files_) for limit, files_ in built.items()}
    manifests = {limit: json.loads(read[MANIFEST]) for limit, read in reads.items()}
    seen = Counter()
    for number, query in enumerate(_searches(covered, extra, entries)):
        today = today_lookup(todays.get, query)
        known = {item[0] for item in today}
        wanted = brute(entries, query, today)
        seen["today full" if len(today) == SHOWN else "searched"] += 1
        for limit, read in reads.items():
            found = lookup(read.get, query, today)
            codes = _codes(found)
            assert known <= set(codes), query
            assert len(codes) <= SHOWN and len(set(codes)) == len(codes), query
            added = [code for code in codes if code not in known]
            if found.flagged:
                assert all(matches(by_code[code], query) for code in added), query
                assert pick(manifests[limit], normalize(query).split(" ")).kind == "start", query
                seen["flagged"] += 1
            else:
                assert added == wanted, query
                seen["added" if added else "none added"] += 1
            if found.read:
                node = pick(manifests[limit], normalize(query).split(" "))
                seen[node.kind if node else "no node"] += 1
            if number % 50 == 0:
                assert found.shown == sorted(found.shown, key=lambda item: order_key(query, item)), query
    assert {"today full", "flagged", "added", "none added", "leaf", "whole", "start", "no node"} <= set(seen), seen

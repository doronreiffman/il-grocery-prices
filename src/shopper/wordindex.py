"""The word index: every start of every word of every product name, filed in small JSON files beside today's search
pieces, and the Python twin of its lookup and ranking, which the tests of `static/search.js` hold the script to
(docs/product-names.md, section 5; the product-names plan's Task 1 and its calls 2 to 9).

Names. Every name is compared after `shopper.search.normalize`. A product's names are its published names (the
normalised title first, then its other columns' names, distinct and sorted), then its size words not already a name,
then the model's names (`Extra.names`: the English name first, then the everyday Hebrew names), each once and none equal
to an earlier name. Size words count as published. They are filed only for a size in grams or millilitres (the registry
does not tell the two apart): "80g" and "80ml", and from 1,000 also "1.5kg" and "1.5l"; a count files none.

The word entry is `[barcode, title as published, English as shown or "", p, name_0, ..., name_n]`: the names from
name_0, the first `p` of them published. A held or search-only reading has its English searched but shows "". Today's
entry (`shopper.search`) is read in the same layout by `as_word_entry`, every name published and no English.

Tokens. Each space-separated word of a name is a token, and so is each longest run inside it of letters and digits
(Unicode categories L and N, tested a character at a time, never with `\\w`): "דאו.דריי" gives itself, "דאו" and
"דריי"; "3%" gives "3%" and "3". A product matches a search when every word of the search, of one character or more,
starts some token of some name.

Nodes and files. Every start of two or more characters of any product's token is a node, holding the products with a
token that starts with it. A node whose products' entries, in name order (normalised title, then barcode), make one
JSON list of at most `limit` bytes is a leaf, one file. A bigger node is cut into parts of at most `limit` bytes,
numbered from 0, in the order a search of its prefix ranks them: all its products when the prefix is itself a whole
token of some product, else only the first `TOP`. A big node has a child node for each next character of its products'
longer tokens; a leaf has none, since it already holds every product below it. A node's file is
`search/w/<hex>-<hex>...json`, each character's code point in at least four lower-case hex digits, and a part's
`search/w/<hex>-...<hex>.<n>.json`. The manifest, `search/w/manifest.json`, is `{"v": 1, "nodes": {prefix: [count,
parts, whole]}}`: the node's product count, its number of parts (0 for a leaf) and 1 when the prefix is a whole token.
`files` yields each node file as it is made and the manifest last, so a build never holds the whole index; the
manifest has its own cap, `MANIFEST_MAX`, which the build applies (Task 3).

Picking a file. Each search word of two or more characters walks its starts from two characters: a start missing from
the manifest means no product has a token starting with the word, so none matches; a leaf ends the walk; a big node
ends it where the word ends. Of the nodes the words end on, the lookup reads the leaf with the fewest products, else
the whole-token node with the fewest, else the part-typed start with the fewest; a tie goes to the shorter prefix, then
the first in code-point order. A one-character word only filters.

The ranking. For a search `q` (normalised) and its words, the first step that fits a product wins:
  1. a name equals q;
  2. the title (name_0) starts with q;
  3. another name starts with q;
  4. one name holds every word as a whole token;
  5. one name has every word starting one of its tokens;
  6. every word starts a token of some name;
  7. none of these (today's search found it inside a name).
Within a step, a product whose step a published name satisfies comes before one only a model's name satisfies (for
step 6: every word by a published name; for step 7: a published name holding q). Ties go to the normalised title,
then the barcode.

The lookup. `today` is the list today's search shows (at most 50). When it holds 50, or no word has two characters,
no word file is read and the list is `today` ranked. Otherwise the manifest is read; a manifest missing, unreadable or
of another version, or a search no node fits, also gives `today` ranked. From a leaf, every match not in `today` is
added. From a big node, a one-word search reads the parts in order until it has enough matches to fill the 50; a
search of several words reads every part and ranks the matches by the search, and when the node is a part-typed start
that stores only its first 50 of more, the list is flagged: its products all match, but others may too. A part
missing or unreadable gives `today` ranked, not flagged. The list shown is `today` and the matches, each product once,
ranked, at most 50, every one of today's products kept. A product is ranked and shown by its word entry when a word
file read holds it, else by its today's entry (so its English is "").
"""
import json
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from itertools import groupby

from basket.units import plain
from shopper.history import Covered
from shopper.search import PIECE_MAX, normalize

FOLDER = "search/w"
MANIFEST = "search/w/manifest.json"
VERSION = 1          # the manifest's "v"
SHOWN = 50           # the list's length, search.js's MAX_SHOWN
TOP = 50             # what a part-typed start keeps
MANIFEST_MAX = PIECE_MAX                       # the manifest's own cap (call 9); node files are held to `limit`
EMPTY_MANIFEST = b'{"v":1,"nodes":{}}'         # written in place of a manifest over its cap (Task 3, call 28)
KINDS = ("leaf", "whole", "start")             # pick's preference, first to last
THOUSAND = Decimal(1000)


@dataclass(frozen=True)
class Extra:
    """A product's model names, as the build passes them (Tasks 3 and 17)."""
    shown: str                   # the English name as shown; "" for none (held, search-only, names off, the probe)
    names: tuple[str, ...]       # the names searched, as written: the English name first, then the everyday Hebrew names


@dataclass(frozen=True)
class Node:
    kind: str                    # "leaf", "whole" (a big node that is a whole token) or "start" (a part-typed start)
    prefix: str
    count: int
    parts: int                   # 0 for a leaf


@dataclass(frozen=True)
class Found:
    shown: list[list]            # the entries shown, at most SHOWN, in order, each product once, each in the word layout
    flagged: bool                # a part-typed start's first 50 only, with more matching
    read: list[str]              # the word index's keys read, in order, the manifest first


def size_words(size: tuple[Decimal, str] | None) -> list[str]:
    """The words a size files (the module's docstring, "Names")."""
    if size is None or size[1] != "gml":
        return []
    amount = size[0]
    words = [f"{plain(amount)}g", f"{plain(amount)}ml"]
    if amount >= THOUSAND:
        words += [f"{plain(amount / THOUSAND)}kg", f"{plain(amount / THOUSAND)}l"]
    return words


def _letter_or_digit(char: str) -> bool:
    return unicodedata.category(char)[0] in "LN"


def tokens(name: str) -> list[str]:
    """A normalised name's tokens, each once, in order of first sight (the module's docstring, "Tokens")."""
    return list(_tokens(name))


@lru_cache(maxsize=1 << 14)   # a lookup ranks the same names again and again; bounded, so a build's memory stays flat
def _tokens(name: str) -> tuple[str, ...]:
    found = {}
    for word in name.split(" "):
        if word:
            found[word] = None
            for kept, run in groupby(word, _letter_or_digit):
                if kept:
                    found["".join(run)] = None
    return tuple(found)


def entry(item: Covered, extra: Extra | None) -> list:
    """The product's word entry (the module's docstring, "Names")."""
    title = normalize(item.title)
    names = [title, *sorted({name for name in map(normalize, item.names.values()) if name and name != title})]
    names += [word for word in size_words(item.size) if word not in names]
    published = len(names)
    for name in map(normalize, extra.names if extra else ()):
        if name and name not in names:
            names.append(name)
    return [item.code, item.title, extra.shown if extra else "", published, *names]


def as_word_entry(today: list) -> list:
    """Today's entry `[barcode, title, normalised title, other names...]` in the word layout, every name published."""
    return [today[0], today[1], "", len(today) - 2, *today[2:]]


def node_key(prefix: str, part: int | None = None) -> str:
    """The site key of a node's file, or of one of its parts."""
    hexes = "-".join(f"{ord(char):04x}" for char in prefix)
    return f"{FOLDER}/{hexes}.json" if part is None else f"{FOLDER}/{hexes}.{part}.json"


def _name_tokens(item: list) -> list[tuple[str, ...]]:
    return [_tokens(name) for name in item[4:]]


def _starts(word: str, name_tokens: tuple[str, ...]) -> bool:
    return any(token.startswith(word) for token in name_tokens)


def _step(query: str, words: list[str], item: list, toks: list[tuple[str, ...]]) -> tuple[int, int]:
    """`step` for a normalised query and its words, the entry's names' tokens given."""
    names, published = item[4:], item[3]
    per_name = (
        lambda i: names[i] == query,
        lambda i: i == 0 and names[i].startswith(query),
        lambda i: i > 0 and names[i].startswith(query),
        lambda i: all(word in toks[i] for word in words),
        lambda i: all(_starts(word, toks[i]) for word in words),
    )
    for number, fits in enumerate(per_name, 1):
        first = next((i for i in range(len(names)) if fits(i)), None)
        if first is not None:
            return number, int(first >= published)
    firsts = [next((i for i in range(len(names)) if _starts(word, toks[i])), None) for word in words]
    if None not in firsts:
        return 6, int(max(firsts) >= published)
    return 7, int(not any(query in name for name in names[:published]))


def _order_key(query: str, words: list[str], item: list, toks: list[tuple[str, ...]]) -> tuple:
    return (*_step(query, words, item, toks), item[4], item[0])


def step(query: str, entry: list) -> tuple[int, int]:
    """(the first step 1 to 7 that fits, 0 when a published name satisfies it or 1 when only a model's name does)."""
    wanted = normalize(query)
    return _step(wanted, wanted.split(" "), entry, _name_tokens(entry))


def order_key(query: str, entry: list) -> tuple:
    """The entry's place in a search's list: its step, then the normalised title, then the barcode."""
    wanted = normalize(query)
    return _order_key(wanted, wanted.split(" "), entry, _name_tokens(entry))


def _matches(words: list[str], toks: list[tuple[str, ...]]) -> bool:
    return all(any(_starts(word, name) for name in toks) for word in words)


def _encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _join(encoded: Iterable[bytes]) -> bytes:
    """The JSON list of entries already encoded: the bytes `_encode` gives the list."""
    return b"[" + b",".join(encoded) + b"]"


def _cut(encoded: list[bytes], limit: int) -> Iterator[bytes]:
    """The entries, in order, as JSON lists of at most `limit` bytes each, each as full as the next entry allows."""
    part, size = [], 1
    for item in encoded:
        if part and size + len(item) + 1 > limit:
            yield _join(part)
            part, size = [], 1
        part.append(item)
        size += len(item) + 1
    yield _join(part)


def files(covered: Mapping[str, Covered], extras: Mapping[str, Extra] | None = None,
          limit: int = PIECE_MAX) -> Iterator[tuple[str, bytes]]:
    """(site key, bytes) of each node file as it is made, then the manifest (the module's docstring, "Nodes and
    files"). The same products give the same bytes in any order."""
    extras = extras or {}
    entries = sorted((entry(item, extras.get(item.code)) for item in covered.values()),
                     key=lambda item: (item[4], item[0]))
    encoded = [_encode(item) for item in entries]
    toks = [_name_tokens(item) for item in entries]
    firsts = defaultdict(set)
    for number, names in enumerate(toks):
        for name in names:
            for token in name:
                if len(token) >= 2:
                    firsts[token[:2]].add((token, number))
    nodes = {}
    for prefix in sorted(firsts):
        yield from _node(prefix, firsts[prefix], entries, encoded, toks, limit, nodes)
    yield MANIFEST, _encode({"v": VERSION, "nodes": dict(sorted(nodes.items()))})


def _node(prefix: str, pairs: set[tuple[str, int]], entries: list[list], encoded: list[bytes], toks: list,
          limit: int, nodes: dict) -> Iterator[tuple[str, bytes]]:
    """The files of the node `prefix` and of its children; `pairs` are its (token, product number)s, a product's number
    its place in name order. Each node's manifest line goes into `nodes`."""
    members = sorted({number for _, number in pairs})
    whole = int(any(token == prefix for token, _ in pairs))
    if 1 + sum(len(encoded[number]) + 1 for number in members) <= limit:
        nodes[prefix] = [len(members), 0, whole]
        yield node_key(prefix), _join(encoded[number] for number in members)
        return
    ranked = sorted(members, key=lambda number: _order_key(prefix, [prefix], entries[number], toks[number]))
    kept = ranked if whole else ranked[:TOP]
    parts = 0
    for body in _cut([encoded[number] for number in kept], limit):
        yield node_key(prefix, parts), body
        parts += 1
    nodes[prefix] = [len(members), parts, whole]
    children = defaultdict(set)
    for token, number in pairs:
        if len(token) > len(prefix):
            children[token[:len(prefix) + 1]].add((token, number))
    for child in sorted(children):
        yield from _node(child, children[child], entries, encoded, toks, limit, nodes)


def pick(manifest: Mapping, words: list[str]) -> Node | None:
    """The node whose file the lookup reads, or None when some word starts no product's token or none has two
    characters (the module's docstring, "Picking a file")."""
    nodes = manifest["nodes"]
    found = []
    for word in words:
        for end in range(2, len(word) + 1):
            known = nodes.get(word[:end])
            if known is None:
                return None
            count, parts, whole = known
            if parts == 0:
                found.append(Node("leaf", word[:end], count, 0))
                break
            if end == len(word):
                found.append(Node("whole" if whole else "start", word, count, parts))
    if not found:
        return None
    return min(found, key=lambda node: (KINDS.index(node.kind), node.count, len(node.prefix), node.prefix))


def _load(read: Callable[[str], bytes | None], key: str, keys: list[str]):
    """The JSON a key holds, or None when it is missing or unreadable; the key is noted as read."""
    keys.append(key)
    body = read(key)
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def _ranked(query: str, words: list[str], items: list[list]) -> list[list]:
    return sorted(items, key=lambda item: _order_key(query, words, item, _name_tokens(item)))


def lookup(read: Callable[[str], bytes | None], query: str, today: list[list]) -> Found:
    """The list a search shows: `today` and the word index's best matches (the module's docstring, "The lookup").
    `read` gives a site key's bytes, or None when the file cannot be had."""
    wanted = normalize(query)
    words = wanted.split(" ")
    keys = []
    if len(today) >= SHOWN or not any(len(word) >= 2 for word in words):
        return _today_only(wanted, words, today, keys)
    manifest = _load(read, MANIFEST, keys)
    if not isinstance(manifest, dict) or manifest.get("v") != VERSION:
        return _today_only(wanted, words, today, keys)
    node = pick(manifest, words)
    if node is None:
        return _today_only(wanted, words, today, keys)
    room = SHOWN - len(today)
    known = {item[0] for item in today}
    held, added = {}, []
    word_files = [node_key(node.prefix)] if node.kind == "leaf" else [node_key(node.prefix, n) for n in range(node.parts)]
    for key in word_files:
        part = _load(read, key, keys)
        if not isinstance(part, list):
            return _today_only(wanted, words, today, keys)
        for item in part:
            if item[0] in held:
                continue
            held[item[0]] = item
            if item[0] not in known and _matches(words, _name_tokens(item)):
                added.append(item)
        if len(words) == 1 and len(added) >= room:
            break
    added = _ranked(wanted, words, added)[:room]
    shown = [held.get(item[0]) or as_word_entry(item) for item in today]
    flagged = node.kind == "start" and len(words) > 1 and node.count > TOP
    return Found(_ranked(wanted, words, shown + added)[:SHOWN], flagged, keys)


def _today_only(query: str, words: list[str], today: list[list], keys: list[str]) -> Found:
    """`today` ranked, every entry read as all-published names: the word step adds nothing."""
    return Found(_ranked(query, words, [as_word_entry(item) for item in today]), False, keys)

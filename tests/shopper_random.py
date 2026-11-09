"""Random histories for the speedups' equality tests (the plan's Task 25a): a speedup's test keeps the code as it stood
before the change and asks the code as it is for the same answers over these histories. Everything is synthetic:
barcodes, names, prices and promotions are made here, from a seeded `random.Random`.

`column_days` gives a column's days of every kind: a record, a price hole, a promotion hole, its chain's table missing,
or no column-day at all. `pair` gives points of every shape the items tables hold: listed or with no listed price, wide
or not, on a promotion, off one or unread (None), a start ahead or none, and promotions that run that day or do not,
wide or not, with a kind or none, valid or not, weighed or not, with conditions or none; prices change now and then,
and the days on a promotion come in runs. `write_tables` writes such a history as items tables through
`tests/test_history.py`'s writer, for the tests that read it back through `load`."""
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from shopper.columns import columns_of
from shopper.history import ColumnDay, Covered, Pair, Point

PRICES = tuple(Decimal(text) for text in ("4.90", "5.00", "5.40", "9.90", "10.00", "12.35", "12.40", "12.45"))
KINDS = ("record",) * 14 + ("price_hole", "promo_hole", "missing", "absent")


def days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=n) for n in range((last - first).days + 1)]


def column_days(rng: random.Random, column: str, slug: str, first: date, last: date) -> dict[tuple[str, date],
                                                                                            ColumnDay]:
    """The column's days from `first` to `last`, each of a random kind (the module's docstring)."""
    found = {}
    for day in days(first, last):
        kind = rng.choice(KINDS)
        if kind == "absent":
            continue
        present = kind != "missing"
        with_file = 0 if not present else 1 if kind == "price_hole" else 4
        promo_hole = kind == "promo_hole" or not present
        found[(column, day)] = ColumnDay(column=column, slug=slug, day=day, present=present,
                                         hole=kind == "price_hole" or not present, promo_hole=promo_hole,
                                         promotions_error=None, included=4 if present else 0, with_file=with_file,
                                         counted=with_file, promo_files=0 if promo_hole else with_file)
    return found


def promotion(rng: random.Random, day: date) -> dict:
    """A promotion on the item on `day`, in the items table's struct as read back (dates and Decimals)."""
    start = day + timedelta(days=rng.randrange(-9, 3))         # now and then not started yet
    end = start + timedelta(days=rng.randrange(0, 14))          # now and then ended already
    kind = rng.choice(("3", "1", "2", None))
    valid = rng.random() < 0.85
    exact = f"{rng.randrange(100, 1500)}/{rng.choice((100, 200, 300))}" if valid or rng.random() < 0.5 else None
    low, high = (Decimal("3.10"), Decimal("4.40")) if kind == "2" and rng.random() < 0.7 else (None, None)
    return {"promotion_id": str(rng.randrange(1, 10 ** 6)), "description": "promotion", "start": start, "end": end,
            "kind": kind, "buy": Decimal(rng.choice(("1.000", "1.000", "2.000", "1.500"))),
            "price": None if exact is None else Decimal("4.49"), "price_exact": exact,
            "per": rng.choice(("unit", "unit", "kg")), "low": low, "high": high, "valid": valid,
            "why": None if valid else "the price is not read",
            "restrictions": rng.sample(["club", "chain_card", "other"], rng.choice((0, 0, 1, 2))),
            "programmes": rng.choice(([], [], ["Programme A"], ["Programme A", "Programme B"])),
            "min_spend": rng.choice((None, None, Decimal("100.00"))), "stores": rng.randrange(1, 9),
            "wide": rng.random() < 0.8}


def pair(rng: random.Random, column: str, code: str, first: date, last: date, density: float = 0.85) -> Pair:
    """A pair with a point on most days from `first` to `last` (the module's docstring)."""
    points = {}
    price, on = rng.choice(PRICES), False
    wide = rng.random() < 0.8
    for day in days(first, last):
        if rng.random() < 0.08:
            price = rng.choice(PRICES)
        if rng.random() < 0.25:
            on = not on
        if rng.random() < 0.05:
            wide = not wide
        if rng.random() >= density:
            continue
        read = rng.random() >= 0.05                              # the chain's promotions read that day
        on_promotion = on if read else None
        structs = ()
        if read and (on or rng.random() < 0.15):
            structs = tuple(promotion(rng, day) for _ in range(rng.choice((1, 1, 1, 2))))
        listed = None if rng.random() < 0.03 else price
        points[day] = Point(day=day, listed=listed, low=None if listed is None else listed - Decimal("0.10"),
                            high=None if listed is None else listed + Decimal("0.20"), listing=rng.randrange(1, 9),
                            wide=wide, on_promotion=on_promotion,
                            next_start=day + timedelta(days=rng.randrange(1, 15)) if rng.random() < 0.05 else None,
                            promotions=structs)
    return Pair(column=column, code=code, points=points)


def code(n: int) -> str:
    """A synthetic barcode."""
    return f"2{n:012d}"


def covered(rng: random.Random, found: str, pairs: dict[str, Pair], first: date) -> Covered:
    """A covered product with the pairs' columns' names (and now and then a column with none), as the registry gives
    it."""
    names = {column: f"Product {found[-4:]}{' x' * index}" for index, column in enumerate(pairs)}
    return Covered(code=found, title=min(names.values(), key=lambda name: (-len(name), name)) if names else "Product",
                   names=names, size=rng.choice((None, (Decimal("1"), "kg"), (Decimal("500"), "g"))),
                   first_covered=first,
                   last_wide={column: first + timedelta(days=rng.randrange(0, 60)) for column in pairs
                              if rng.random() < 0.7})


def _json(struct: dict) -> dict:
    """A struct as the items table's writer takes it: dates and Decimals as text."""
    return {key: value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, Decimal) else value
            for key, value in struct.items()}


def write_tables(rng: random.Random, tables: Path, slug: str, first: date, last: date, codes: list[str],
                 extra: tuple[Pair, ...] = ()) -> None:
    """The chain's items tables from `first` to `last`, some days' missing, each column a hole or a promotion hole now
    and then, every code listed on most days at most columns (the module's docstring), and the `extra` pairs' points
    as given."""
    from test_history import _row, _table      # here, so that tests/test_history.py can import this module
    keys = [column.key for column in columns_of(slug)]
    shapes = {(key, found): pair(rng, key, found, first, last, density=0.8) for key in keys for found in codes
              if rng.random() < 0.8}
    shapes |= {(given.column, given.code): given for given in extra}
    for day in days(first, last):
        if rng.random() < 0.05:
            continue                                             # the chain's table missing that day
        rows = []
        for (key, found), shape in shapes.items():
            point = shape.points.get(day)
            if point is None or point.listed is None:
                continue
            rows.append(_row(key, found, listed=str(point.listed), wide=point.wide, on_promotion=point.on_promotion,
                             next_start=point.next_start, low=str(point.low), high=str(point.high),
                             listing=point.listing,
                             promotions=None if point.on_promotion is None else
                             [_json(struct) for struct in point.promotions]))
        _table(tables, slug, day, rows, holes=[key for key in keys if rng.random() < 0.06],
               promo_holes=[key for key in keys if rng.random() < 0.06])


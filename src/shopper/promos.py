"""The day's promotions table: one chain's full promotion files of one day, a row per column, promotion, group and item
code, counted at the column's counted stores (docs/shopper-site.md P3, Call 7 and "Build and hosting" item 1, with its
"Changed after the survey", S1, S2 and S4; the plan's Task 5 and its second pre-flight's S2, S3 and S9 to S12).

Which files. A column's counted stores are P2's: its included stores with a price file that counts that day (Task 7
passes them, column by column, and `outside`, the chain's counted stores in no column). Each counted store of a column
is read by its latest `PromoFull` of the day (`basket.extract.day_files`, as B1 takes price files); its earlier files
are passed over. The files of stores not counted (store 413, Be's stores, a store whose price file is named under 005
as store 779's is) are passed over unread, and so are those of counted stores in no column (Yesh Chesed's, the small
formats', Carrefour's stores outside its table), listed apart as `outside`. A file is never read for its store number
inside it, only by its name.

What is kept. A file's records are taken whole before any of them counts: with the chain's known field sets
(`shopper.promotions.KNOWN_FIELDS`) a changed root is refused only at `</Root>`, after the file's promotions were read,
so a file refused there leaves none of its promotions counted. Every promotion read is counted, each copy in each
store's file. Coupons are dropped as read (`keep`), their links counted. Every promotion `keep` keeps has its codes
checked (`check_codes`); one holding a `RewardType` 6 or 12 link is dropped whole, its links counted, as a gift or a basket
reward (`not_shelf`, S2: its "N for ₪M" links are that reward's terms); one that ended before the day is counted and
dropped; one that starts after the day is kept and counted (F2 forecasts from it); `RewardType` 0 links are kept with
no kind (S2: never a price effect, Task 6 shows them as "price not read"). A format change (`PromotionFormatChanged`)
is raised, not caught, and no table is written: a field set the chain's files never carried (its message names the
file), a code (it names the chain and the field), a date or a minimum spend that does not read (it names the field
only: Task 7, which catches the error, names the chain). A file that does not read at all stops it with
BadPriceFile, as a price file does.

The rows. One per (column, `PromotionID`, `GroupID`, item code) that at least one of the column's counted stores
carries (the plan's B4; the design's "Where the key lives"), its fields those of the variant most of the column's
carrying stores carry, a tie to the lowest store id's (as a number). A variant is a copy's fields, the promotion's, the
link's group's and the item's, with its minimum spend, which can sit on another group; `variants` counts the distinct
ones among the carrying stores, and `fields` holds the chosen one's as JSON text, {"promotion": {...}, "group": {...},
"item": {...}}, each as published (S11). From those fields: the texts as published (`description`, `start_at`,
`end_at`, `update_time`, `min_qty`, `max_qty`, `discount_rate`, `discounted_price`, "" when empty, a missing `MaxQty`
too); `start` and `end`, their dates (P3 compares date parts only); `restrictions` and `programmes` from `ClubID`
(`shopper.promotions.target`); `min_spend`, the largest `MinPurchaseAmount` above zero over every group of the
promotion (`shopper.promotions.min_spend`, item-less and `RewardType` 0 groups included), to the agora half up;
`reward_type`, `kind` (NULL for 0), `code_norm`, `gs1`, and `weighed` (`bIsWeighted` 1). A minimum spend too large for
the table's DECIMAL(12,2) stops the chain as an unreadable one does, since it could not be written.

The stores' figures. `discounted_median`, `discounted_low` and `discounted_high` are B5's median (`basket.rules.median`)
and range of the carrying stores' `DiscountedPrice` on the link, one price a store (its lowest, if its file lists the
link twice), written to three places half up; a price that is no number, or too large for DECIMAL(12,3), is none,
and a price is staged in its short form (1E-3000000, not three million digits).
For percent off (S4, measured, never a gate), `with_store_price` counts the carrying stores whose rows in the day's
prices table list the code (B5's one price a store, `basket.rules.store_prices_sql`, over the rows that count),
and `agrees_with_store` those of them whose rate is above 0 and below 100 and whose `DiscountedPrice` is within ₪0.01
of that store's own price x (1 − rate/100) rounded half up (`shopper.deals.rate_agrees`, the deal's own check, so a
rate such as 1E+30 never agrees); NULL for every other kind. `stores` counts the column's
counted stores whose latest file links that promotion to that code, each once however often its file lists it;
`promotion_stores` those carrying the promotion at all; `counted` the column's counted stores, with a promotion file
or not; `wide` is `stores` x 2 ≥ `counted` (P3 per column: half the column's counted stores).

The texts (S9). Every kept promotion's distinct (`PromotionID`, `PromotionDescription`, start, end) as published, over
every store read, with the stores carrying it and the first of those stores' copy, are the report's `texts`, for
Task 6's texts table: a text one store alone carries is there too. They stay out of `report.json`.

How. The day's prices table must be there (`basket.rules.open_day`'s MissingTable otherwise; Task 7 writes it first).
Each file's links, the promotions' copies and each new promotion and item variant go to CSVs in a temporary folder
inside the table's folder, written with `basket.extract`'s writer and read back by its `copy_sql`, and DuckDB groups
them; the stores' figures are worked out in Decimal, a row at a time, and the table is written to
`tables/promotions/chain=<slug>/date=<day>/promotions.parquet`, overwritten by each run, with `report.json` beside it.
A day with no files writes the columns.
"""
import json
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Set
from dataclasses import dataclass, fields
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from hashlib import blake2b
from pathlib import Path

import duckdb

from basket.barcode import is_gs1, normalize
from basket.chains import EXCLUDED
from basket.extract import DayFile, copy_sql, day_files, sql_text, write_csv
from basket.rules import apply_filters, median, open_day, store_prices_sql
from shopper.deals import rate_agrees
from shopper.promofile import PromotionFormatChanged, PromotionRead, Tally, read_promotions
from shopper.promotions import KNOWN_FIELDS, check_codes, dates, keep, kind, min_spend, not_shelf, number, target

KIND = "PromoFull"
PERCENT_OFF = "percent_off"
CENT = Decimal("0.01")
THREE = Decimal("0.001")
STORE_PRICE_LIMIT = Decimal(10) ** 9   # DECIMAL(12,3) holds nine digits before the point
MIN_SPEND_LIMIT = Decimal(10) ** 10    # DECIMAL(12,2) holds ten
DROPPED = {"gift": "gifts", "basket_reward": "basket_rewards"}   # `not_shelf`'s reasons, as the report counts them
BATCH = 10_000                         # rows fetched at a time while the stores' figures are worked out

# The staging tables, each a CSV per file read (and one with no rows, so a day of no files reads), then a Parquet file.
_LINKS = (("store", "VARCHAR"), ("store_number", "BIGINT"), ("seq", "BIGINT"), ("promotion_id", "VARCHAR"),
          ("group_id", "VARCHAR"), ("code", "VARCHAR"), ("code_norm", "VARCHAR"), ("promotion_variant", "VARCHAR"),
          ("item_variant", "VARCHAR"), ("price", "VARCHAR"), ("rate", "VARCHAR"))
_CARRIERS = (("store", "VARCHAR"), ("promotion_id", "VARCHAR"))
_PROMOTIONS = (("variant", "VARCHAR"), ("description", "VARCHAR"), ("start_at", "VARCHAR"), ("end_at", "VARCHAR"),
               ("start", "DATE"), ("end", "DATE"), ("update_time", "VARCHAR"), ("restrictions", "VARCHAR[]"),
               ("programmes", "VARCHAR[]"), ("min_spend", "DECIMAL(12,2)"), ("fields", "VARCHAR"))
_ITEMS = (("variant", "VARCHAR"), ("code_norm", "VARCHAR"), ("gs1", "BOOLEAN"), ("reward_type", "VARCHAR"),
          ("kind", "VARCHAR"), ("min_qty", "VARCHAR"), ("max_qty", "VARCHAR"), ("discount_rate", "VARCHAR"),
          ("discounted_price", "VARCHAR"), ("weighed", "BOOLEAN"), ("group_fields", "VARCHAR"),
          ("item_fields", "VARCHAR"))
_FIGURES = (("col", "VARCHAR"), ("promotion_id", "VARCHAR"), ("group_id", "VARCHAR"), ("code", "VARCHAR"),
            ("discounted_median", "DECIMAL(12,3)"), ("discounted_low", "DECIMAL(12,3)"),
            ("discounted_high", "DECIMAL(12,3)"), ("with_store_price", "INTEGER"), ("agrees_with_store", "INTEGER"))
_STAGED = {"links": (_LINKS, ("code_norm", "price")), "carriers": (_CARRIERS, ()),
           "promotions": (_PROMOTIONS, ("min_spend",)), "items": (_ITEMS, ("code_norm", "kind"))}


@dataclass(frozen=True)
class PromoText:
    """One distinct promotion text of the day (S9): as published, the counted stores carrying it (by number) and the
    first of those stores' copy, for its fields, groups and items."""
    promotion_id: str
    description: str
    start_at: str
    end_at: str
    stores: tuple[str, ...]
    record: PromotionRead


@dataclass(frozen=True)
class PromoReport:
    """What one chain-day's promotions read and wrote (the module's docstring); copies counted per store's file."""
    slug: str
    day: str
    counted: dict[str, int]       # per column: its counted stores
    files: list[str]              # read: each counted column store's latest PromoFull, by store number
    passed_over: list[str]        # not read: earlier files of a store, and the files of stores not counted; sorted
    outside: list[str]            # not read: the files of counted stores in no column, by store number
    promo_files: dict[str, int]   # per column: its counted stores with a promotion file
    promotions: int               # every promotion read, coupons included
    coupons: int
    gifts: int                    # dropped whole for a RewardType 6 link
    basket_rewards: int           # dropped whole for a RewardType 12 link
    dropped_links: int            # the links of every promotion dropped
    expired: int                  # ended before the day, dropped
    before_start: int             # kept promotions whose start is after the day
    rows: int
    texts: tuple[PromoText, ...]  # S9, for Task 6; left out of report.json

    def summary(self) -> dict:
        """What `report.json` holds: every field but the texts."""
        return {field.name: getattr(self, field.name) for field in fields(self) if field.name != "texts"}


def promotions_path(tables_dir: Path, slug: str, day: date) -> Path:
    return tables_dir / "promotions" / f"chain={slug}" / f"date={day.isoformat()}" / "promotions.parquet"


def _three(value: Decimal) -> Decimal:
    return value.quantize(THREE, rounding=ROUND_HALF_UP)


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _json(mapping: Mapping[str, str]) -> str:
    """Fields as JSON text, each as published, the names sorted so that equal fields read as one text."""
    return json.dumps(dict(mapping), ensure_ascii=False, sort_keys=True)


def _variant(*parts: str) -> str:
    return blake2b("\x1f".join(parts).encode(), digest_size=16).hexdigest()


def _store_price(text: str) -> Decimal | None:
    """A copy's `DiscountedPrice` for the stores' figures; None when it is no number or would not fit DECIMAL(12,3)."""
    amount = number(text)
    if amount is None or abs(amount) >= STORE_PRICE_LIMIT or abs(_three(amount)) >= STORE_PRICE_LIMIT:
        return None
    return amount


def _min_spend(record: PromotionRead) -> Decimal | None:
    """The promotion's minimum spend to the agora, half up; P10 when it would not fit the table's DECIMAL(12,2)."""
    amount = min_spend(record.groups)
    if amount is None:
        return None
    if amount >= MIN_SPEND_LIMIT or amount.quantize(CENT, rounding=ROUND_HALF_UP) >= MIN_SPEND_LIMIT:
        raise PromotionFormatChanged(f"MinPurchaseAmount {amount} does not fit the table")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class _Read:
    """What the files read so far gave: the counts, the texts, the variants written, the percent-off codes."""
    folder: Path
    counts: Counter
    texts: dict[tuple[str, str, str, str], tuple[list[str], PromotionRead]]
    promotion_variants: set[str]
    item_variants: set[str]
    percent_off: set[str]
    seq: int = 0
    files: int = 0

    def stage(self, name: str, rows: list[tuple]) -> None:
        columns, _ = _STAGED[name]
        write_csv(rows, self.folder / f"{name}-{self.files:05d}.csv", columns)


def _read_file(slug: str, day: date, day_file: DayFile, read: _Read) -> None:
    """One counted store's file, its records taken whole, then counted and staged."""
    tally = Tally()
    records = list(read_promotions(day_file.name, day_file.path.read_bytes(), keep(slug), tally, KNOWN_FIELDS[slug]))
    read.counts["promotions"] += tally.promotions
    read.counts["coupons"] += tally.dropped_promotions
    read.counts["dropped_links"] += tally.dropped_links
    store = day_file.store
    links, carriers, promotions, items = [], [], [], []
    for record in records:
        check_codes(slug, record)
        reason = not_shelf(slug, record)
        if reason is not None:
            read.counts[DROPPED[reason]] += 1
            read.counts["dropped_links"] += len(record.links)
            continue
        start, end = dates(record.fields)
        if end < day:
            read.counts["expired"] += 1
            read.counts["dropped_links"] += len(record.links)
            continue
        read.counts["before_start"] += start > day
        promotion = record.fields
        promotion_id = promotion["PromotionID"]
        spend = _min_spend(record)
        restricted = target(slug, promotion["ClubID"])
        promotion_json = _json(promotion)
        promotion_variant = _variant(promotion_json, _text(spend) or "")
        if promotion_variant not in read.promotion_variants:
            read.promotion_variants.add(promotion_variant)
            promotions.append((promotion_variant, promotion["PromotionDescription"],
                               promotion["PromotionStartDateTime"], promotion["PromotionEndDateTime"],
                               start.isoformat(), end.isoformat(), promotion["PromotionUpdateTime"],
                               json.dumps(list(restricted.restrictions)),
                               json.dumps(list(restricted.names), ensure_ascii=False), _text(spend), promotion_json))
        carriers.append((store, promotion_id))
        key = (promotion_id, promotion["PromotionDescription"], promotion["PromotionStartDateTime"],
               promotion["PromotionEndDateTime"])
        carrying = read.texts.setdefault(key, ([], record))[0]
        if not carrying or carrying[-1] != store:
            carrying.append(store)
        for link in record.links:
            group, item = link.group, link.item
            code = item["ItemCode"]
            code_norm = normalize(code)
            found = kind(slug, item)
            group_json, item_json = _json(group), _json(item)
            item_variant = _variant(group_json, item_json)
            if item_variant not in read.item_variants:
                read.item_variants.add(item_variant)
                items.append((item_variant, code_norm, is_gs1(code), item["RewardType"], found, item["MinQty"],
                              item.get("MaxQty", ""), item["DiscountRate"], item["DiscountedPrice"],
                              item["bIsWeighted"] == "1", group_json, item_json))
            if found == PERCENT_OFF and code_norm is not None:
                read.percent_off.add(code_norm)
            price = _store_price(item["DiscountedPrice"])
            links.append((store, int(store), read.seq, promotion_id, group["GroupID"], code, code_norm,
                          promotion_variant, item_variant, None if price is None else str(price),
                          item["DiscountRate"]))
            read.seq += 1
    for name, rows in (("links", links), ("carriers", carriers), ("promotions", promotions), ("items", items)):
        read.stage(name, rows)
    read.files += 1


def _agrees(price: Decimal | None, own: Decimal, rate: str) -> bool:
    return price is not None and rate_agrees(rate, price, own)


def _figures(result: duckdb.DuckDBPyConnection) -> Iterator[tuple]:
    """Each row's stores' figures (the module's docstring), from its carrying copies, a batch at a time."""
    while batch := result.fetchmany(BATCH):
        for column, promotion_id, group_id, code, found, copies in batch:
            lowest: dict[str, tuple[Decimal | None, str, Decimal | None]] = {}   # a store's copy at its lowest price
            for copy in copies:   # by store, then as the file lists them
                price = None if copy["price"] is None else Decimal(copy["price"])
                known = lowest.get(copy["store"])
                if known is None or (price is not None and (known[0] is None or price < known[0])):
                    lowest[copy["store"]] = (price, copy["rate"], copy["own"])
            held = list(lowest.values())
            prices = sorted(price for price, _, _ in held if price is not None)
            figures = (_three(median(prices)), _three(prices[0]), _three(prices[-1])) if prices else (None, None, None)
            with_price = agreeing = None
            if found == PERCENT_OFF:
                with_price = sum(1 for _, _, own in held if own is not None)
                agreeing = sum(1 for price, rate, own in held if own is not None and _agrees(price, own, rate))
            yield (column, promotion_id, group_id, code, *(_text(value) for value in figures), with_price, agreeing)


def _stage_table(con: duckdb.DuckDBPyConnection, folder: Path, name: str) -> Path:
    """The staged CSVs of `name` copied into one Parquet file; its path."""
    columns, nullable = _STAGED[name]
    out = folder / f"{name}.parquet"
    con.execute(copy_sql(folder / f"{name}-*.csv", out, columns, nullable))
    return out


def extract_promotions(raw_dir: Path, slug: str, day: date, counted: Mapping[str, Set[str]], tables_dir: Path,
                       outside: Set[str]) -> PromoReport:
    """Write the chain's promotions table for the day and `report.json` beside it; the report. `counted`: each column's
    counted stores; `outside`: the chain's counted stores in no column."""
    columns = {column: frozenset(stores) for column, stores in sorted(counted.items())}
    column_stores = set().union(*columns.values())
    latest, earlier = day_files(raw_dir, slug, day, kind=KIND)
    to_read: list[DayFile] = []
    outside_files: list[str] = []
    passed: list[str] = list(earlier)
    for day_file in latest:
        if day_file.store in column_stores:
            to_read.append(day_file)
        elif day_file.store in outside:
            outside_files.append(day_file.name)
        else:
            passed.append(day_file.name)
    out = promotions_path(tables_dir, slug, day)
    with open_day(tables_dir, day, [slug]) as con:   # MissingTable before any file is read
        apply_filters(con, {slug: column_stores}, {slug: EXCLUDED[slug].sub_chains})
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=out.parent) as temp:
            read = _Read(Path(temp), Counter(), {}, set(), set(), set())
            for name in _STAGED:
                read.stage(name, [])
            read.files += 1
            for day_file in to_read:
                _read_file(slug, day, day_file, read)
            rows = _write(con, read, columns, out)
    with_file = {day_file.store for day_file in to_read}
    texts = tuple(PromoText(*key, tuple(stores), record) for key, (stores, record) in sorted(read.texts.items()))
    report = PromoReport(
        slug=slug, day=day.isoformat(), counted={column: len(stores) for column, stores in columns.items()},
        files=[day_file.name for day_file in to_read], passed_over=sorted(passed), outside=outside_files,
        promo_files={column: len(stores & with_file) for column, stores in columns.items()},
        promotions=read.counts["promotions"], coupons=read.counts["coupons"], gifts=read.counts["gifts"],
        basket_rewards=read.counts["basket_rewards"], dropped_links=read.counts["dropped_links"],
        expired=read.counts["expired"], before_start=read.counts["before_start"], rows=rows, texts=texts)
    (out.parent / "report.json").write_text(json.dumps(report.summary(), sort_keys=True, indent=1))
    return report


def _write(con: duckdb.DuckDBPyConnection, read: _Read, columns: Mapping[str, frozenset[str]], out: Path) -> int:
    """Group the staged copies into the table's rows and write it to `out`; the number of rows."""
    staged = {name: sql_text(_stage_table(con, read.folder, name)) for name in _STAGED}
    con.execute("CREATE TEMP TABLE store_columns (col VARCHAR, store VARCHAR)")
    pairs = [(column, store) for column, stores in columns.items() for store in sorted(stores)]
    if pairs:
        con.executemany("INSERT INTO store_columns VALUES (?, ?)", pairs)
    con.execute(f"""
        CREATE TEMP TABLE held AS
        SELECT c.col, l.*, o.price AS own
        FROM read_parquet({staged["links"]}) l
        JOIN store_columns c ON c.store = l.store
        LEFT JOIN ({store_prices_sql()}) o ON o.store = l.store AND o.code_norm = l.code_norm
    """, [sorted(read.percent_off)])
    con.execute("""
        CREATE TEMP TABLE keyed AS
        SELECT col, promotion_id, group_id, code, count(DISTINCT store) AS stores,
               count(DISTINCT promotion_variant || item_variant) AS variants
        FROM held
        GROUP BY col, promotion_id, group_id, code
    """)
    con.execute("""
        CREATE TEMP TABLE chosen AS
        SELECT col, promotion_id, group_id, code, promotion_variant, item_variant
        FROM (SELECT col, promotion_id, group_id, code, promotion_variant, item_variant,
                     count(DISTINCT store) AS carrying, min(store_number) AS first_store
              FROM held GROUP BY ALL)
        QUALIFY row_number() OVER (PARTITION BY col, promotion_id, group_id, code
                                   ORDER BY carrying DESC, first_store, promotion_variant, item_variant) = 1
    """)
    copies = con.execute(f"""
        SELECT k.col, k.promotion_id, k.group_id, k.code, i.kind,
               list({{'store': h.store, 'price': h.price, 'rate': h.rate, 'own': h.own}}
                    ORDER BY h.store_number, h.seq) AS copies
        FROM keyed k
        JOIN chosen ch ON ch.col = k.col AND ch.promotion_id = k.promotion_id AND ch.group_id = k.group_id
                      AND ch.code = k.code
        JOIN read_parquet({staged["items"]}) i ON i.variant = ch.item_variant
        JOIN held h ON h.col = k.col AND h.promotion_id = k.promotion_id AND h.group_id = k.group_id AND h.code = k.code
        GROUP BY ALL
    """)
    figures_csv = read.folder / "figures.csv"
    write_csv(_figures(copies), figures_csv, _FIGURES)
    figures = read.folder / "figures.parquet"
    con.execute(copy_sql(figures_csv, figures, _FIGURES, [name for name, _ in _FIGURES[4:]]))
    return con.execute(f"""
        COPY (
            SELECT k.col AS "column", k.promotion_id, p.description, p.start_at, p.end_at, p."start", p."end",
                   p.update_time, p.restrictions, p.programmes, p.min_spend, k.group_id, k.code, i.code_norm, i.gs1,
                   i.reward_type, i.kind, i.min_qty, i.max_qty, i.discount_rate, i.discounted_price, i.weighed,
                   '{{"promotion":' || p.fields || ',"group":' || i.group_fields || ',"item":' || i.item_fields || '}}'
                       AS fields,
                   CAST(k.variants AS INTEGER) AS variants, f.discounted_median, f.discounted_low, f.discounted_high,
                   f.with_store_price, f.agrees_with_store, CAST(k.stores AS INTEGER) AS stores,
                   CAST(s.promotion_stores AS INTEGER) AS promotion_stores, CAST(n.counted AS INTEGER) AS counted,
                   k.stores * 2 >= n.counted AS wide
            FROM keyed k
            JOIN chosen ch ON ch.col = k.col AND ch.promotion_id = k.promotion_id AND ch.group_id = k.group_id
                          AND ch.code = k.code
            JOIN read_parquet({staged["promotions"]}) p ON p.variant = ch.promotion_variant
            JOIN read_parquet({staged["items"]}) i ON i.variant = ch.item_variant
            JOIN read_parquet({sql_text(figures)}) f ON f.col = k.col AND f.promotion_id = k.promotion_id
                                                     AND f.group_id = k.group_id AND f.code = k.code
            JOIN (SELECT c.col, r.promotion_id, count(DISTINCT r.store) AS promotion_stores
                  FROM read_parquet({staged["carriers"]}) r JOIN store_columns c ON c.store = r.store
                  GROUP BY ALL) s ON s.col = k.col AND s.promotion_id = k.promotion_id
            JOIN (SELECT col, count(*) AS counted FROM store_columns GROUP BY col) n ON n.col = k.col
            ORDER BY k.col, k.promotion_id, k.group_id, k.code
        ) TO {sql_text(out)} (FORMAT parquet)
    """).fetchone()[0]

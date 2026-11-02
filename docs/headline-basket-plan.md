# Headline Basket Implementation Plan (step one: by hand)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** price one fixed basket of about 30 barcodes at the five chains from one day's archived full price files, on the Mac, and produce the page, the method page and the day's JSON, ready for a hand upload.

**Architecture:** a new package `src/basket/` beside `collector`, stdlib plus DuckDB. Three pure steps over local files under a gitignored `data/`: extract (one chain's `PriceFull` files for a day into one Parquet table), basket (the five tables and `basket/v1.json` into a day record, rules B2 to B9 as SQL plus Python guards), page (the record into `site/`). One command runs the three; a pre-upload check and a publish script follow the flights-archive pattern. Step two (the scheduled Lambda) is a second plan, written after this one's timings exist.

**Tech Stack:** Python 3.13, `xml.etree.iterparse`, `duckdb==1.5.6` (released 28 September 2026; cp313 wheels for macOS arm64 and manylinux x86_64), pytest, the repo's `scripts/mutation_check.py`, AWS CLI (read-only sync; the site stack and uploads on the owner's go).

**Spec:** `docs/headline-basket.md` (rules B1 to B12, the words, the calls). Executors read both.

## Global Constraints

- Python `>=3.13`; no dependency younger than one month, pinned (`duckdb==1.5.6` is the only new one; it goes in `requirements-dev.txt`; the Lambda packaging is step two's).
- Every datetime is time-zone aware; never a naive `astimezone()`. Test data never reads the clock: fixed times, and `gzip.compress(..., mtime=0)`.
- Fixtures under `tests/fixtures/` are synthetic: at most three records a file, synthetic prices, names and barcodes, no addresses or tokens (`tests/test_fixtures.py` enforces it and reads a file's kind from its name).
- Raw files never enter the repo: `data/` and `site/` are gitignored; the real day is synced read-only from the archive bucket `il-grocery-prices-archivebucket-fmnv3dorojol` with profile `flights-sam`, after `aws sts get-caller-identity --profile flights-sam` shows account 137953273942 and user doron-admin.
- A test and a named mutation for every rule; coverage floor 95% on `basket` as on `collector` (CI: `pytest --cov=collector --cov=src/basket --cov-fail-under=95`). The mutation check edits source files in place: run nothing else from the checkout while it runs.
- Words: the "always" and "never" lists of the spec, verbatim; docs in plain words, no "we"; the credit line on every page; `noindex` on every page; no JavaScript.
- Money is `Decimal`, never float; written as strings with two decimals; rounding half up.
- Store and sub-chain keys are the published numbers with leading zeros stripped (`"093"` and `"93"` are one store).
- Every AWS write (`sam deploy`, an upload) on the owner's go; subagents never run `gh` or push.
- Commit after each task with the message given; the plan's `## Deviations` section records any departure.

## Review Focus

Input classes the spec implies and no task would otherwise exercise; each has its test in the task named.

1. A chain publishes a basket code with leading zeros (`07290000066738`) while the basket says `7290000066738`: the prices must still match (Task 8, `test_code_matched_by_normalized_form`).
2. A product name holding a comma, a double quote and a line break must reach the Parquet table intact through the CSV step (Task 4, `test_table_round_trips_hebrew_quotes_commas_and_newlines`).
3. A chain whose extraction found no files: an empty table, "0 of M", the other four still ranked (Task 8, `test_empty_chain_table_gives_zero_with_file`; Task 4, `test_extract_with_no_files_writes_an_empty_table`).
4. One store lists an item at ₪10,000: the median stands, the range shows it, the page renders (Task 8, `test_median_ignores_an_outlier`; Task 11, `test_range_note_wide_range_renders`).
5. Two runs of one day differ only in run id, build time and code fingerprint and must compare equal, while a one-agora change in one item's median must not (Task 9, `test_comparable_ignores_run_fields_but_not_a_median`; Task 13, `test_build_twice_is_unchanged`).

---

### Task 1: Barcodes

**Files:**
- Create: `src/basket/__init__.py` (a one-line docstring), `src/basket/barcode.py`
- Modify: `.github/workflows/ci.yml` (the pytest line: `--cov=collector --cov=src/basket`), `scripts/mutation_check.py`
- Test: `tests/test_barcode.py`

**Interfaces:**
- Produces: `normalize(code: str) -> str | None` (the ASCII digits of `code.strip()` with leading zeros stripped; `None` when the string is empty, has a non-ASCII-digit character, or is all zeros); `is_gs1(code: str) -> bool` (normalize succeeds, 8 to 14 significant digits, and the GS1 mod-10 check digit holds: weights 3 and 1 alternating from the digit left of the check digit, leading zeros changing nothing).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("code, norm", [
    ("7290000066738", "7290000066738"), ("0012345678905", "12345678905"), (" 96385074 ", "96385074"),
    ("0000", None), ("", None), ("72-9000", None),
    ("٧٢٩٠٠٠٠٠٦٦٧٣٨", None),  # Arabic-Indic digits: str.isdigit() says yes, the rule says no
])
def test_normalize(code, norm): assert normalize(code) == norm

@pytest.mark.parametrize("code, ok", [
    ("7290000066738", True), ("4006381333931", True), ("96385074", True), ("012345678905", True),
    ("12345678905", True), ("2000000000015", True), ("0000096385074", True),
    ("7290000000100", False), ("1501", False), ("725", False), ("7290111111111", False),
    ("72900000000221", False), ("1234567", False), ("123456789012345", False),
])
def test_is_gs1(code, ok): assert is_gs1(code) is ok
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_barcode.py -q` — Expected: FAIL, `ModuleNotFoundError: basket`.

- [ ] **Step 3: Implement `normalize` and `is_gs1` in `src/basket/barcode.py`**

Digits by `re.fullmatch(r"[0-9]+", ...)`, not `str.isdigit()`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_barcode.py -q` — Expected: PASS.

- [ ] **Step 5: Mutations and CI coverage**

Add to `MUTATIONS` (file `("src/basket/barcode.py", ["tests/test_barcode.py"])`): "check digit ignored" (the weights both 1), "leading zeros kept", "non-ASCII digits accepted" (`str.isdigit`), "seven significant digits accepted". Run: `.venv/bin/python scripts/mutation_check.py barcode` — Expected: every mutation caught. Edit `ci.yml` as above.

- [ ] **Step 6: Commit**

```bash
git add src/basket tests/test_barcode.py scripts/mutation_check.py .github/workflows/ci.yml
git commit -m "basket: barcodes: normalize and the GS1 check digit (B1 identity); CI covers the basket package"
```

---

### Task 2: The sub-chain in a file name

**Files:**
- Modify: `src/collector/names.py` (`FileName` gains `sub_chain: str | None = None`, the group before the store when a name carries two groups; `None` for `Stores` and for store 039's names), `tests/test_names.py` (`test_published_names` gains a `sub_chain` column: `"002"` for `PriceFull7290027600007-002-045-...`, `"001"` for the NCR and Carrefour full files, `None` for `Stores` and the 039 names), `scripts/mutation_check.py`

**Interfaces:**
- Produces: `FileName.sub_chain` as published (padded), for Task 4's B2 lookup.

- [ ] **Step 1: Extend the parametrized test and add `test_sub_chain_is_the_group_before_the_store`** (`PriceFull7290027600007-005-030-20261102-030000` → `"005"`, store `"030"`; `pricefull7290058140886-039-202611010514.gz` → `None`).
- [ ] **Step 2: Run `.venv/bin/pytest tests/test_names.py -q`** — Expected: FAIL (`unexpected keyword argument 'sub_chain'`).
- [ ] **Step 3: Implement** in `parse_file_name`: `sub_chain = groups[0] if len(groups) == 2 else None`.
- [ ] **Step 4: Run the collector's full suite** `.venv/bin/pytest -q` — Expected: PASS (nothing else constructs `FileName` positionally).
- [ ] **Step 5: Mutation** "sub-chain read as the store" (`groups[-1]`); run `scripts/mutation_check.py "sub-chain"` — caught.
- [ ] **Step 6: Commit** `git commit -am "names: FileName carries the sub-chain (Shufersal's Be stores are told apart by it, B2)"`.

---

### Task 3: Reading one price file

**Files:**
- Create: `src/basket/pricefile.py`, `tests/fixtures/basket/PriceFull7290000000001-001-001-20260101-000000.gz` (three `<Item>`s in the common layout: codes `2000000000015` at `5.00`, `2000000000015` again at `6.00`, `1501` at `abc`; the second name holds `,` and `"` and a line break; `UnitQty` values `גרם`, `גרם`, `לא ידוע`; built once with `gzip.compress(..., mtime=0)` and checked in)
- Test: `tests/test_pricefile.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Produces: `Item(code: str, name: str, price: str, quantity: str, unit: str, unit_of_measure: str, updated: str)` (frozen, text stripped, a missing element `""`); `read_items(name: str, data: bytes) -> list[Item]` (gzip: one body; ZIP: every non-directory member in archive order; plain XML with or without a BOM; raises `BadPriceFile(name: ...)` on empty, HTML or unparsable input); field names: `ItemCode`; `ItemName` or `ItemNm`; `ItemPrice`; `Quantity`; `UnitQty`; `UnitOfMeasure`; `PriceUpdateTime` or `PriceUpdateDate` (`docs/portals.md`, Rami Levy store 039).

- [ ] **Step 1: Write the failing tests**

```python
def test_reads_the_common_layout():  # tests/fixtures/ncr/PriceFull7290058140886-001-722-20261101-001016.gz
    items = read_items(NCR_722.name, NCR_722.read_bytes())
    assert len(items) == 3
    assert items[0] == Item("2000000000015", "מוצר לדוגמה 1", "10.90", "100.00", "גרם", "100 גרם", "2026-07-21T13:42:46.000")
def test_reads_store_039_zip():  # pricefull7290058140886-039-202611010514.gz: ItemNm, PriceUpdateDate
    assert read_items(...)[0] == Item("2000000000015", "פריט בדיקה 1", "450", "1", "00000", "0000000000", "2026-10-31 07:00:00")
def test_reads_plain_xml_with_a_utf8_bom(): ...   # b"\xef\xbb\xbf<Root><Items><Item><ItemCode>96385074</ItemCode></Item></Items></Root>"
def test_missing_fields_are_empty(): ...        # the item above: name == "" and price == ""
def test_zip_reads_every_member(): ...          # a ZIP built in the test with two one-item members → 2 items
def test_refuses_empty_html_and_not_xml():      # BadPayload-style: b"", b"<html>", b"\x1f\x8b junk" → BadPriceFile naming the file
def test_every_pricefull_fixture_reads(): ...   # every fixture whose name starts with "pricefull" (any case) gives 1 to 3 items
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_pricefile.py -q` — Expected: FAIL (import).
- [ ] **Step 3: Implement `read_items`** with `ET.iterparse(io.BytesIO(body), events=("end",))`, clearing each `Item` after reading it; gzip and ZIP detection by the magic bytes as `collector.payload` does (`GZIP_MAGIC`, `ZIP_MAGICS`, `XML_STARTS` imported from it).
- [ ] **Step 4: Run** the tests — Expected: PASS.
- [ ] **Step 5: Mutations** (`("src/basket/pricefile.py", ["tests/test_pricefile.py"])`): "ItemNm ignored", "PriceUpdateDate ignored", "second ZIP member skipped", "text not stripped". Run the check — caught.
- [ ] **Step 6: Commit** `git add src/basket/pricefile.py tests/test_pricefile.py tests/fixtures/basket scripts/mutation_check.py && git commit -m "basket: read one full price file, both layouts, gzip and ZIP"`.

---

### Task 4: The day's table

**Files:**
- Create: `src/basket/extract.py`, `scripts/sync.sh`
- Modify: `requirements-dev.txt` (add `duckdb==1.5.6`), `.gitignore` (add `data/` and `site/`), `scripts/mutation_check.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `collector.names.parse_file_name`, `collector.store.published_name` (strips a `.<12 hex>` conflict suffix), Task 3's `read_items`, Task 1's `normalize` and `is_gs1`.
- Produces: `store_key(published: str) -> str` (leading zeros stripped, `"0"` for all zeros); `DayFile(store: str, sub_chain: str | None, name: str, path: Path)`; `day_files(raw_dir: Path, slug: str, day: date) -> tuple[list[DayFile], list[str]]` (B1: under `raw_dir/chain=<slug>/date=<day>/`, names whose kind is `PriceFull` and day is `day`; per store key the greatest file name in plain string order, which is the latest time since the time precedes any suffix; the second list is the names passed over, sorted; the first is sorted by store key as a number then as text); `Row(store, sub_chain, code, code_norm, gs1, name, price: Decimal | None, quantity, unit, unit_of_measure, updated, file)`; `RowCounts(rows: int, unreadable_prices: int, repeated: int, conflicting: int)`; `rows_from(day_file: DayFile) -> tuple[list[Row], RowCounts]` (B3: one row per code as published, the last wins; a repeat at the same price counts in `repeated`, at another price in `conflicting`; a price that `Decimal()` refuses, or that has more than two decimals, is `None` and counted); `write_table(rows: Iterable[Row], out: Path) -> int` (a CSV written with `csv.QUOTE_ALL`, then DuckDB `COPY (SELECT ... FROM read_csv(...)) TO '<out>' (FORMAT parquet)` with columns `store VARCHAR, sub_chain VARCHAR, code VARCHAR, code_norm VARCHAR, gs1 BOOLEAN, name VARCHAR, price DECIMAL(12,2), quantity VARCHAR, unit VARCHAR, unit_of_measure VARCHAR, updated VARCHAR, file VARCHAR`; an empty input still writes a table with that schema); `table_path(tables_dir: Path, slug: str, day: date) -> Path` = `tables_dir/prices/chain=<slug>/date=<day>/prices.parquet`; `ExtractReport(slug, day, files: list[str], skipped: list[str], stores: int, rows: int, unreadable_prices: int, repeated: int, conflicting: int)`; `extract(raw_dir, slug, day, tables_dir) -> ExtractReport` (writes the table and `report.json` beside it, `json.dumps(sort_keys=True, indent=1)`); a CLI `python -m basket.extract --raw data/raw --tables data/tables --day D --chain SLUG` printing the report and the elapsed seconds (the only clock read, in `main`).

- [ ] **Step 1: Add the dependency and install**: `duckdb==1.5.6` in `requirements-dev.txt`; `.venv/bin/pip install -r requirements-dev.txt`.
- [ ] **Step 2: Write the failing tests** (a `raw_tree(tmp_path, {...})` helper lays files under `chain=<slug>/date=<day>/` from fixture bytes)

```python
def test_store_key(): assert [store_key(s) for s in ("093", "000", "39", "0413")] == ["93", "0", "39", "413"]
def test_day_files_takes_the_latest_name_per_store():       # 722 at -001016 and -071016 → the 071016 one; skipped == [the other]
def test_day_files_ignores_other_days_and_kinds():          # a PromoFull and a 2026-11-01 PriceFull are neither used nor skipped
def test_conflict_copy_never_beats_a_later_time():         # "X-001016.gz.0123456789ab" vs "X-071016.gz" → 071016
def test_sub_chain_and_store_are_keys():                   # Shufersal "...-005-093-..." → DayFile(store="93", sub_chain="5", ...)
def test_rows_last_duplicate_wins_and_conflicts_are_counted():  # the Task 3 fixture: 2000000000015 → 6.00; conflicting == 1; rows == 2
def test_unreadable_price_is_none_and_counted():           # "abc" → None; "7.123" → None; unreadable_prices == 2
def test_code_norm_and_gs1():                               # "0007290000066738" → ("7290000066738", True); "1501" → ("1501", False)
def test_store_comes_from_the_name_not_the_file():        # the Carrefour fixture ...-472-... holds <StoreID>903</StoreID>; rows say store "472"
def test_price_has_two_places():                           # "450" → Decimal("450.00"); "7.2" → Decimal("7.20")
def test_table_round_trips_hebrew_quotes_commas_and_newlines():  # duckdb reads back the fixture's second name unchanged
def test_extract_writes_parquet_and_report():              # two stores → stores == 2; report.json == asdict(report) with sort_keys
def test_extract_with_no_files_writes_an_empty_table():    # 0 rows; DESCRIBE lists the 12 columns in order
```

- [ ] **Step 3: Run** `.venv/bin/pytest tests/test_extract.py -q` — FAIL (import).
- [ ] **Step 4: Implement `src/basket/extract.py`.** `price`: `Decimal(text)`, refused when it raises or when `-exp > 2`; stored as `quantize(Decimal("0.01"))`.
- [ ] **Step 5: Run** the tests — PASS.
- [ ] **Step 6: Mutations** (`("src/basket/extract.py", ["tests/test_extract.py"])`): "older file wins", "first duplicate wins", "conflict not counted", "unreadable price kept as zero", "three-decimal price accepted", "empty table not written", "sub-chain padded". Run — caught.
- [ ] **Step 7: `scripts/sync.sh <day>`**: the flights `scripts/sync.sh` identity check verbatim (profile `flights-sam`, expected ARN `arn:aws:iam::137953273942:user/doron-admin`), then for the day: `aws s3 sync s3://il-grocery-prices-archivebucket-fmnv3dorojol/raw/ data/raw/ --exclude '*' --include 'chain=*/date=<day>/PriceFull*' --include 'chain=*/date=<day>/pricefull*' --include 'chain=*/date=<day>/Stores*'` and `manifests/date=<day>/` into `data/manifests/date=<day>/`. Read-only; no ask needed.
- [ ] **Step 8: The real day, on the Mac** (`sh scripts/sync.sh 2026-11-02`, about 370 MB; then `python -m basket.extract` for each of the five chains). Record in this plan's `## Deviations` the seconds per chain, the rows and the Parquet size per chain, and the report counts (unreadable, repeated, conflicting). These numbers go to step two's plan.
- [ ] **Step 9: Commit** `git add src/basket/extract.py tests/test_extract.py scripts/sync.sh requirements-dev.txt .gitignore scripts/mutation_check.py && git commit -m "basket: extract a chain's day into a Parquet table (B1, B3); sync one day from the archive"`.

---

### Task 5: Store lists and the included stores

**Files:**
- Create: `src/basket/stores.py`, `src/basket/chains.py`
- Test: `tests/test_stores.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `collector.payload.GZIP_MAGIC`.
- Produces: `Store(id: str, sub_chain: str | None, name: str, store_type: str)` (keys zero-stripped); `read_stores(data: bytes) -> list[Store]` (gzip or plain; root `Chain` or `Root`; `SubChainId`/`SubChainID`, `StoreID`/`StoreId`, `StoreName`, `StoreType`; UTF-8 or UTF-16 BOM, as `collector.storelist` reads); `SLUGS = ("shufersal", "ramilevy", "osherad", "carrefour", "yochananof")` and `Exclusion(sub_chains: frozenset[str], stores: frozenset[str], why: str)` with `EXCLUDED: dict[str, Exclusion]` in `chains.py`: `"shufersal": Exclusion({"5"}, {"413"}, "sub-chain 5 'Be', 97 stores on 2026-11-02, carries 12% of the shared barcodes; store 413 'שופרסל ONLINE'")`, the other four empty until the survey below; `included(stores: list[Store], slug: str) -> set[str]` (the store list's view: ids not excluded by id and not in an excluded sub-chain; this is B8's count M and the id rule for store 413; the row-level sub-chain rule, "the file name wins", is Task 8's `apply_filters`); `excluded(stores: list[Store], slug: str) -> list[Store]` (for the method page); `day_store_list(raw_dir: Path, slug: str, day: date) -> tuple[bytes, date] | None` (the greatest `Stores` name of `day`, else of the latest earlier day present under `raw_dir/chain=<slug>/`).

- [ ] **Step 1: Write the failing tests** with two inline documents: a Shufersal-style `<Chain>` (sub-chain 5 "Be" with store 93 type 1; sub-chain 2 with store 30 type 1 and store 413 "שופרסל ONLINE" type 2), gzipped with `mtime=0`; an NCR-style `<Root>` encoded `utf-16` (with BOM) with stores "001" and "039".

```python
def test_reads_shufersal_and_ncr_layouts():   # ids "93", "30", "413" / "1", "39"; sub_chain "5" and "2" / "1"
def test_included_drops_be_and_online_for_shufersal(): assert included(stores, "shufersal") == {"30"}
def test_included_keeps_everything_for_the_others(): assert included(ncr_stores, "ramilevy") == {"1", "39"}
def test_excluded_lists_the_dropped_stores_with_names(): ...  # [Store("93", "5", ...), Store("413", "2", "שופרסל ONLINE", "2")]
def test_day_store_list_falls_back_to_the_latest_earlier_day(): ...  # 2026-11-01 file used for 2026-11-02 when that day has none; None when no day has one
def test_every_stores_fixture_reads(): ...   # the three fixtures: 1 to 3 stores each
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`stores.py`, `chains.py`): "Be included", "online store included", "sub-chain compared padded", "fallback takes a later day". Run — caught.
- [ ] **Step 6: Survey the real store lists** (data synced in Task 4): a throwaway script in the scratchpad prints, per chain, every store whose name matches `online|אונליין|אינטרנט|משלוח` (case-insensitive) with its id, sub-chain and type. Add each finding to `EXCLUDED` by id with the name in `why`, and a test naming it; nothing found for a chain means its entry stays empty. Record the survey's result in `## Deviations`.
- [ ] **Step 7: Commit** `git commit -m "basket: store lists and the included stores (B2): Shufersal's Be and online store out; survey of the other chains recorded"`.

---

### Task 6: Sizes

**Files:**
- Create: `src/basket/units.py`
- Test: `tests/test_units.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Produces: `Size(amount: Decimal, kind: str)` (frozen; `kind` is `"gml"` for grams and millilitres, treated alike, or `"unit"`); `UNITS: dict[str, tuple[str, Decimal]]` published unit string → (kind, factor): `"גרם"` → (gml, 1), `"ק\"ג"` and `"קילוגרם"` and `"קילו"` → (gml, 1000), `"מ\"ל"` and `"מיליליטר"` → (gml, 1), `"ליטר"` → (gml, 1000), `"יחידה"` and `"יח'"` → (unit, 1); the rest filled in Step 5; `normal_size(quantity: str, unit: str) -> Size | None` (`None` for `"לא ידוע"`, `""`, a unit not in `UNITS`, a quantity `Decimal()` refuses or ≤ 0; otherwise `Decimal(quantity) * factor` normalized to a plain number); `plain(d: Decimal) -> str` (`"1000"`, `"1.5"`, never `"1E+3"`).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("q, u, size", [
    ("1", "ליטר", Size(Decimal(1000), "gml")), ("500.00", "גרם", Size(Decimal(500), "gml")),
    ("1.5", "ק\"ג", Size(Decimal(1500), "gml")), ("12", "יחידה", Size(Decimal(12), "unit")),
    ("1", "לא ידוע", None), ("", "גרם", None), ("0", "גרם", None), ("abc", "גרם", None), ("1", "", None),
])
def test_normal_size(q, u, size): assert normal_size(q, u) == size
def test_a_litre_equals_a_thousand_grams(): assert normal_size("1", "ליטר") == normal_size("1000", "גרם")
def test_plain(): assert [plain(Decimal(v)) for v in ("1000", "1.50", "1E+3")] == ["1000", "1.5", "1000"]
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: The vocabulary from the selection day**: over the real tables (Task 4, Step 8) run `SELECT unit, count(*) AS n FROM read_parquet('data/tables/prices/chain=*/date=2026-11-02/prices.parquet') GROUP BY 1 ORDER BY 2 DESC` with DuckDB; every string with at least 1,000 rows gets a `UNITS` entry (a kind and factor, or a comment line saying why it stays unknown, such as `"00000"`); the table carries a comment naming the day and the counts. Add the new strings to the parametrized test.
- [ ] **Step 6: Mutations** (`units.py`): "litre not scaled", "unknown unit read as grams", "zero quantity accepted", "unit and gml compared alike". Run — caught.
- [ ] **Step 7: Commit** `git commit -m "basket: sizes (B7): the unit vocabulary of 2026-11-02, kilos and litres scaled, g and ml alike"`.

---

### Task 7: The basket file

**Files:**
- Create: `src/basket/basket_file.py`, `tests/fixtures/basket/basket-test.json` (three items: `2000000000015` "Test milk 1 L" / "חלב בדיקה 1 ל'" size 1000 gml dairy; `2000000000022` "Test pasta 500 g" size 500 gml pantry; `2000000000039` "Test eggs ×12" size 12 unit dairy)
- Test: `tests/test_basket_file.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 1's `is_gs1`, `normalize`; Task 6's `Size`.
- Produces: `BasketItem(code: str, name_en: str, name_he: str, size: Size, category: str)`; `Basket(version: str, since: date, selection_day: date, items: tuple[BasketItem, ...])`; `load_basket(path: Path, min_items: int = 25, max_items: int = 40) -> Basket`; `BadBasket` raised for: a code failing `is_gs1`; two items with one `normalize(code)`; an empty name; a `size.kind` outside `{"gml", "unit"}`; an item count outside the limits. JSON layout: `{"version": "v1", "since": "YYYY-MM-DD", "selection_day": "2026-11-02", "items": [{"code": "...", "name_en": "...", "name_he": "...", "size": {"amount": "1000", "kind": "gml"}, "category": "dairy", "coverage": {"shufersal": "0.93", ...}}]}` (`coverage` is informational, kept as given).

- [ ] **Step 1: Tests**: `test_loads_the_fixture` (3 items with `min_items=1`); `test_rejects_a_bad_check_digit` (`7290000000100`); `test_rejects_duplicates_across_leading_zeros` (`2000000000015` and `02000000000015`); `test_rejects_an_unknown_kind`; `test_rejects_24_items_at_the_default_floor` (codes generated in the test by appending the check digit to `20000000001` + two digits); `test_rejects_41_items`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`basket_file.py`): "check digit not checked", "duplicates allowed", "floor at 24". Run — caught.
- [ ] **Step 6: Commit** `git commit -m "basket: the basket file and its checks"`.

---

### Task 8: The rules

**Files:**
- Create: `src/basket/rules.py`
- Test: `tests/test_rules.py` (a `day_tables(tmp_path, {slug: [Row, ...]})` helper writes one Parquet per chain with Task 4's `write_table`)
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 4's `table_path`, `write_table`, `Row`; Task 6's `normal_size`, `Size`; Task 7's `Basket`.
- Produces:
  - `MissingTable(Exception)` naming the slug; `open_day(tables_dir: Path, day: date, slugs: Sequence[str]) -> duckdb.DuckDBPyConnection` (an in-memory connection with a view `prices` = the union of `SELECT '<slug>' AS chain, * FROM read_parquet('<path>')`; raises `MissingTable` for an absent file).
  - `apply_filters(con, included: dict[str, set[str]], excluded_sub_chains: dict[str, frozenset[str]]) -> None` (a temp table `included(chain, store)`; a view `rows` = `prices` joined to it where the row's `sub_chain` is not in `excluded_sub_chains[chain]` (B2: the file name's sub-chain wins over the store list's) and `price IS NOT NULL AND price > 0.01` (B4)).
  - `stores_with_file(con, included) -> dict[str, int]` (distinct `store` in `prices`, before B4, per chain, among the included).
  - `ChainPrice(median: Decimal, low: Decimal, high: Decimal, listing: int)`; `chain_prices(con, codes: Sequence[str]) -> dict[tuple[str, str], ChainPrice]` keyed (chain, code_norm): the prices of `rows` listed by `list(price ORDER BY price, store)`, the median computed in Python (B5: the middle value, or the mean of the two middle ones), `low`/`high` the min and max, `listing` the distinct stores.
  - `chain_sizes(con, codes) -> dict[tuple[str, str], Size | None]` (per (chain, code_norm): `normal_size` over the distinct (quantity, unit) pairs weighted by row count; the most common readable size; a tie → the smaller amount; `None` when no row's size is readable).
  - `ChainDay(slug: str, included: int, with_file: int, in_ranking: bool)`; `chain_day(slug, included: int, with_file: int) -> ChainDay` (B8: `in_ranking` when `included > 0 and with_file * 2 >= included`).
  - `LeftOut(code: str, reason: str, details: dict[str, str])` (`reason` `"coverage"` with `{chain: "n of m"}`, or `"size"` with `{chain: "<plain amount> <kind>"}`); `Headline(lowest: str, lowest_total: Decimal, highest: str, highest_total: Decimal, gap_percent: int)`; `ChainResult(total: Decimal | None, rank: int | None, items: dict[str, ChainPrice])`; `DayResult(items_in: tuple[str, ...], left_out: tuple[LeftOut, ...], chains: dict[str, ChainResult], headline: Headline | None)`.
  - `gap_percent(low: Decimal, high: Decimal) -> int` ((high − low) × 100 ÷ low, `ROUND_HALF_UP` to a whole number).
  - `price_basket(basket: Basket, days: Sequence[ChainDay], prices, sizes, with_file: dict[str, int]) -> DayResult`: over the chains in the ranking only: B6 (an item stays when, at every such chain, `listing * 2 >= with_file[chain]`), B7 (every such chain's stated size equals the basket's), B9 (totals over `items_in`; rank from lowest, equal totals share a rank and sort by slug; the headline only with three or more chains in the ranking). Chains out of the ranking keep their `items` prices and have `total` and `rank` `None`.

- [ ] **Step 1: Write the failing tests** (five chains `a` to `e` unless said; codes from the Task 7 fixture)

```python
def test_filters_drop_excluded_stores_placeholders_and_null_prices()
def test_rows_of_an_excluded_sub_chain_drop_by_the_file_name()      # a store the list includes, whose file name says sub-chain "5": its rows go, M keeps it
def test_stores_with_file_counts_before_the_placeholder_rule()      # a store whose only row is 0.01 still has a file
def test_median_is_exact_for_even_and_odd_counts()                   # [5.00, 7.00] → 6.00; [5.00, 7.00, 20.00] → 7.00
def test_median_ignores_an_outlier()                                  # [5.90, 5.90, 5.90, 10000.00] → 5.90; high == 10000.00
def test_code_matched_by_normalized_form()                            # a row coded "02000000000015" prices basket code "2000000000015"
def test_chain_sizes_take_the_most_common_readable_size_ties_to_the_smaller()
def test_coverage_guard_half_of_stores_with_file()                   # 2 of 4 list it → in; 1 of 4 → LeftOut("…", "coverage", {"b": "1 of 4"})
def test_size_guard_only_a_stated_size_can_block()                   # chain b says 500 gml for a 1000 gml item → out; chain c with None does not block
def test_chain_with_too_few_files_is_out_of_ranking_but_priced()     # 1 of 3 included → in_ranking False, total None, items priced, guards skip it
def test_empty_chain_table_gives_zero_with_file()                    # chain e with no rows: with_file 0, out of ranking; four chains ranked
def test_fewer_than_three_chains_no_headline()
def test_totals_rank_and_gap():                                       # 100.00 and 127.40 → gap 27; 100.00 and 127.50 → 28; ties share rank 1, sorted by slug
def test_missing_table_raises_naming_the_chain()
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`rules.py`): "placeholders kept", "null prices kept", "median takes the lower middle", "coverage guard at a third", "size guard ignores a chain", "unstated size blocks", "half a chain's stores read as a third", "headline with two chains", "gap rounded down", "excluded store counted", "Be rows kept when the list includes the store", "chain out of ranking still guards". Run — caught.
- [ ] **Step 6: Commit** `git commit -m "basket: the rules B2 and B4 to B9 over the day's tables"`.

---

### Task 9: The day record

**Files:**
- Create: `src/basket/record.py`
- Test: `tests/test_record.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 8's `DayResult`, `ChainDay`, `ChainPrice`; Task 4's `ExtractReport`; `collector.run.new_run_id(now, "basket")`; `collector.handler.code_sha(package)`.
- Produces: `money(d: Decimal) -> str` (two decimals, `ROUND_HALF_UP`); `ItemPrice(median: str, low: str, high: str, listing: int)`; `ChainRecord(included: int, with_file: int, in_ranking: bool, rank: int | None, total: str | None, items: dict[str, ItemPrice], stores_with_file: tuple[str, ...], files: tuple[str, ...], manifests: tuple[str, ...], extraction: dict[str, int])`; `DayRecord(day: date, basket_version: str, run_id: str, code_sha: str, built_at: str, collected_by: str, chains: dict[str, ChainRecord], items_in: tuple[str, ...], left_out: tuple[LeftOut, ...], headline: Headline | None)`; `build_record(day, basket, result: DayResult, days, reports: dict[str, ExtractReport], manifests: dict[str, tuple[str, ...]], run_id, code_sha, built_at, collected_by) -> DayRecord`; `record_json(record) -> str` (`json.dumps(..., sort_keys=True, indent=1, ensure_ascii=False)`, money as strings, dates ISO); `public_day(record) -> dict` (the same without `stores_with_file`, `files` and `manifests`, with `"revisions": []` and `"revised": None`); `comparable(public: dict) -> dict` (without `run_id`, `code_sha`, `built_at`, `revisions`, `revised`); `manifests_for(manifest_dir: Path, day: date, slug: str, files: Sequence[str]) -> tuple[str, ...]` (the sorted run ids of the manifests `manifests/date=<day>/<slug>-<run id>.json` whose `files[<name>]["outcome"] == "stored"` for any of `files`, as `collector.run.RunResult` writes them); `code_fingerprint() -> str` = `code_sha(Path(basket.__file__).parent)`.

- [ ] **Step 1: Tests**: `test_money` (`"7.2"` → `"7.20"`, `"312.455"` → `"312.46"`); `test_record_json_is_sorted_and_keeps_hebrew`; `test_public_day_has_counts_not_store_lists`; `test_comparable_ignores_run_fields_but_not_a_median`; `test_manifests_for_maps_stored_names_to_run_ids` (two manifests written in `tmp_path`: one stores the file, one lists it as `"exists"`; only the first's run id is returned); `test_code_fingerprint_is_12_hex_and_changes_with_a_source_file` (monkeypatched package dir).
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`record.py`): "store lists leak to the public day", "comparable ignores medians", "half-up rounding dropped", "an 'exists' outcome counts as stored". Run — caught.
- [ ] **Step 6: Commit** `git commit -m "basket: the day record (B10), its public form and what a revision compares (B12)"`.

---

### Task 10: Candidates, and the basket itself

**Files:**
- Create: `src/basket/candidates.py`, later `basket/v1.json`
- Test: `tests/test_candidates.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 8's `open_day`, `apply_filters`, `stores_with_file`, `chain_sizes`; Task 5's store lists; Task 6's `Size`, `plain`.
- Produces: `Candidate(code: str, names: dict[str, str], size: Size, coverage: dict[str, Decimal], medians: dict[str, Decimal])`; `candidates(con, with_file: dict[str, int], min_share: Decimal = Decimal("0.8"), min_stating: int = 3) -> list[Candidate]` (codes with `gs1` true listed in every chain in `rows`; `listing / with_file[chain] >= min_share` at every chain; sizes stated by at least `min_stating` chains and all stated sizes equal; `names[chain]` the most common name string in that chain, ties to the alphabetically first; sorted by code); `write_candidates_csv(cands: Sequence[Candidate], path: Path) -> None` (columns `code, size`, then `<slug>_name, <slug>_coverage, <slug>_median` per slug in `SLUGS` order); a CLI `python -m basket.candidates --day D --raw data/raw --tables data/tables --out data/candidates-<day>.csv`.

- [ ] **Step 1: Tests** on a synthetic day: code A everywhere at 100% with equal sizes → in; B in four chains → out; C at 50% in one chain → out; D with two chains stating 500 against three stating 1000 → out; E with two chains stating → out; F non-GS1 → out; `test_names_are_the_most_common_string_per_chain`; `test_csv_columns`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`candidates.py`): "a four-chain code passes", "coverage share at half", "two stating chains enough", "non-GS1 code passes". Run — caught.
- [ ] **Step 6: The real candidate table** (Mac): `python -m basket.candidates --day 2026-11-02`. Record the count in `## Deviations` (the spec expects about 629 before the online store's exclusion).
- [ ] **Step 7: Propose the basket**: from the CSV, 25 to 40 items following the spec's "Size and shape" (everyday categories; at most two items from one brand line; no alcohol, tobacco or infant formula), with an English and a Hebrew name and the declared size written by hand against the five name strings. Save as `basket/v1-proposed.json` in the spec's layout and show the owner a table: code, both names, size, category, coverage and median per chain.
- [ ] **Step 8: Owner gate.** On the owner's approval in chat, save the list as `basket/v1.json` with `since` = the approval date, delete the proposal, and add `test_v1_basket_loads` (`load_basket(Path("basket/v1.json"))` with the default limits) to `tests/test_basket_file.py`.
- [ ] **Step 9: Commit** `git commit -m "basket: candidates for selection; basket v1 approved by the owner <date>"`.

---

### Task 11: Words and pages

**Files:**
- Create: `src/basket/words.py`, `src/basket/page.py`
- Test: `tests/test_page.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 9's public day dict; Task 7's `Basket`; Task 5's `excluded`.
- Produces, in `words.py`: `TITLE = "One basket, five chains"`; `CHAIN_NAMES = {"shufersal": "Shufersal", "ramilevy": "Rami Levy", "osherad": "Osher Ad", "carrefour": "Carrefour", "yochananof": "Yochananof"}`; `ALWAYS = ("listed price", "in the chain's price file", "before promotions", "lowest listed total for this basket", "median")`; `NEVER = ("cheapest chain", "cheaper than", "you'll pay", "you will pay", "saves you", "at the till", "real prices", "the chain charges")`; `REVISED = "Revised on"`; `MEDIAN_SENTENCE = "A chain's price for an item is the median of its stores' listed prices, so no single store need list exactly this total."`; `headline_lines(headline: Headline | None, item_count: int, day: date) -> tuple[str, str]` (with a headline: `"Lowest listed total today: {chain}, ₪{total}."` and `"Highest: {chain}, ₪{total}, {gap}% more. {n} everyday items, listed shelf prices before promotions, from the chains' price files of {day:%A %-d %B %Y}."`; without: `"No comparison today: fewer than three chains published enough files."` and `"{n} everyday items, listed shelf prices before promotions, from the chains' price files of {date}."`); `credit(day: date, collected_by: str) -> str` (`"Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish under section 30 of the Food and Pharma Competition Promotion Law, 2014: the files of {day:%-d %B %Y}, collected by {collected_by} Israel time. Listed prices, not a promise of what a till charges. Not shopping advice."`); `bar_label(with_file: int) -> str` (`"from 92 stores' files"`); `range_note(low: str, high: str, listing: int, with_file: int) -> str` (`"stores ₪3.90 to ₪4.20, 91 of 96 list it"`); `too_few(with_file: int, included: int) -> str` (`"too few files today: 1 of 24 stores"`); `left_out_line(item: LeftOut, basket: Basket) -> str`; `revised_line(on: date, reason: str, first_totals: dict[str, str]) -> str` (`"Revised on {on:%-d %B %Y}: {reason}. First published: Rami Levy ₪312.45, Osher Ad ₪…"` in rank order).
- Produces, in `page.py`: `render_index(public: dict, basket: Basket, exclusions: dict[str, list[Store]]) -> str`; `render_method(basket: Basket, exclusions, public: dict) -> str`; `render_day(public: dict) -> str` (`json.dumps(sort_keys=True, indent=1, ensure_ascii=False)`); `build_site(public, basket, exclusions, site_dir: Path, write_day: bool) -> None` (writes `index.html`, `method.html`, `days/<day>.json` when `write_day`, and the marker `.basket-site`). Every page: `<html lang="en">`, `<meta name="robots" content="noindex">`, one `<style>`, no `<script>`, the credit line, a link to `method.html`; Hebrew names in `<span dir="rtl" lang="he">`; the bars inline SVG scaled to the highest total; chains out of the ranking marked with `too_few(...)` and no bar; the lowest price in each table row marked `class="low"`; the notes block with the left-out lines, the stores sentence naming the exclusions, and `MEDIAN_SENTENCE`; the revised line only when `public["revised"]`. The method page: the rules B1 to B12 in plain words, the basket table (code, both names, size, category), the exclusions by chain with store names, "What this page does not claim", the law line, and "To reproduce this number" (the day's file set is in the day JSON; the code is this repo).

- [ ] **Step 1: Tests** (a public dict built from the Task 7 fixture basket and literal numbers, chains `shufersal`, `ramilevy`, `osherad`, `carrefour`, `yochananof`): `test_headline_lines_exact` (`Headline("ramilevy", Decimal("312.45"), "carrefour", Decimal("398.10"), 27)`, 30 items, `date(2026, 11, 2)` → the two strings above with "Monday 2 November 2026"); `test_headline_without_comparison`; `test_credit_line_exact`; `test_index_has_always_words_and_no_never_words`; `test_every_page_has_noindex_credit_one_style_and_no_script`; `test_lowest_marked_per_row`; `test_chain_out_of_ranking_is_marked_and_has_no_bar`; `test_range_note_wide_range_renders` (`"0.10"` to `"10000.00"`); `test_revised_line_shown_only_when_revised`; `test_day_json_is_the_public_dict`; `test_method_page_lists_every_item_and_exclusion`; `test_hebrew_names_are_rtl`; `test_build_site_writes_marker_and_day_file_only_when_asked`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`words.py`, `page.py`): "credit line dropped from the method page", "noindex dropped", "lowest marked as highest", "a never phrase in the template", "revised line always shown", "day file written when not asked", "bars for a chain out of ranking". Run — caught.
- [ ] **Step 6: Commit** `git commit -m "basket: the words and the three outputs: index, method, the day's JSON"`.

---

### Task 12: The pre-upload check

**Files:**
- Create: `src/basket/check.py`
- Test: `tests/test_check.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `words.NEVER`, `words.ALWAYS`, `words.REVISED`, the fixed prefix of `credit` (`"Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish under"`) and `"Not shopping advice."`.
- Produces: `NoPages(Exception)`; `check_site(site_dir: Path) -> list[str]` (problems, one line each; over every `.html`, as written and with tags stripped, entities unescaped and whitespace collapsed, case-insensitive: any `NEVER` phrase; a missing credit prefix or "Not shopping advice."; a missing `noindex`; a `<script`; the words `we`, `our`, `us` whole; `index.html` missing any `ALWAYS` phrase; `REVISED` present on `index.html` while `days/<day>.json` has `"revised": null`; the marker `.basket-site` missing; raises `NoPages` with no `.html`); `main(argv) -> int` (0 clean, 1 problems printed, 2 no pages) as `python -m basket.check site`, mirroring `flights-archive/src/timeline/check.py`.

- [ ] **Step 1: Tests**: `test_a_built_site_passes` (Task 11's `build_site` into `tmp_path`); then one injected fault each: `"cheapest&nbsp;chain"` (entity-hidden), a removed `noindex`, a `<script>`, `"we"` in a sentence, a removed credit, `"Revised on"` on an unrevised day; `test_no_pages_exit_2`; `test_main_exit_codes`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`check.py`): "entities not unescaped", "script allowed", "exit 0 on a hit", "'we' allowed". Run — caught.
- [ ] **Step 6: Commit** `git commit -m "basket: the pre-upload check: the never words, the credit line, noindex, no script"`.

---

### Task 13: The build command, revisions, the golden day

**Files:**
- Create: `src/basket/build.py`, `tests/fixtures/basket/golden/` (a raw tree for day `2026-01-01`: five chains, two stores each, each `PriceFull` with the three fixture codes at distinct prices, one chain with a store whose file lists only two codes, a `Stores` file per chain; the expected public day `golden-day.json`)
- Test: `tests/test_build.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `BuildOutcome(record: DayRecord, unchanged: bool, revised: bool, record_path: Path)`; `build_day(day: date, data_dir: Path, site_dir: Path, basket_path: Path, now: datetime, revise: str | None, rebuild: bool, chains: Sequence[str] = SLUGS, min_items: int = 25, collected_by: str | None = None) -> BuildOutcome`:
  1. per chain, `extract` unless the table exists and not `rebuild`;
  2. store lists (Task 5) → included; `open_day`, `apply_filters` with `{slug: EXCLUDED[slug].sub_chains}`, `stores_with_file`, `chain_day` per chain, `chain_prices`, `chain_sizes`, `price_basket`;
  3. the record with `run_id = new_run_id(now, "basket")`, `built_at = now` in UTC ISO, `collected_by` = the argument, else `now` in Israel time as `HH:MM`; written to `data_dir/basket/date=<day>/basket-<run id>.json` with `open(..., "x")`;
  4. B12: `previous = site_dir/days/<day>.json` if present: `comparable(public_day(record)) == comparable(previous)` → `unchanged`, the day file is left as it is; different and `revise is None` → `RevisionNeeded` raised naming the keys that differ; different with a reason → the public dict gets `revisions = previous["revisions"] + [{run_id, code_sha, built_at, totals} of previous]` and `revised = {"on": <now, Israel date ISO>, "reason": revise}`;
  5. `build_site(..., write_day = not unchanged)`.
  `main(argv) -> int` as `python -m basket.build --day D [--data data] [--site site] [--basket basket/v1.json] [--min-items 25] [--chains ...] [--rebuild] [--revise REASON] [--collected-by HH:MM]`, printing per chain the extraction seconds and rows, then the headline lines; exit 1 on `MissingTable`, `RevisionNeeded`, `BadBasket`, with the message.
  `now` comes from `datetime.now(timezone.utc)` in `main` only.

- [ ] **Step 1: Tests**: `test_golden_day_matches` (`comparable(public)` equals `golden-day.json`'s); `test_build_twice_is_unchanged` (second outcome `unchanged`, `days/<day>.json` unmodified, two private records); `test_refuses_to_overwrite_a_private_record` (same `now` twice with a fixed `secrets.token_hex` → `FileExistsError`); `test_differing_numbers_without_reason_raise` (a changed price in one store file and `--rebuild`); `test_revise_keeps_first_totals_and_adds_the_line`; `test_rebuild_flag_re_extracts`; `test_missing_basket_item_in_a_chain_is_left_out_not_a_crash`; `test_main_exit_codes`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Mutations** (`build.py`): "unchanged day rewritten", "revision without a reason accepted", "first totals dropped on revision", "record overwritten", "tables never rebuilt". Run — caught.
- [ ] **Step 6: The real day, twice** (Mac): `python -m basket.build --day 2026-11-02` with `basket/v1.json`; then again → "unchanged". The hand check: three items' prices in three chains' raw files read by eye against the page (read-only; nothing copied). Record both in `## Deviations` with the headline the page shows.
- [ ] **Step 7: Full suite, coverage, every mutation**: `.venv/bin/pytest --cov=collector --cov=src/basket --cov-fail-under=95 -q` and `.venv/bin/python scripts/mutation_check.py` — all pass, all caught.
- [ ] **Step 8: Commit** `git commit -m "basket: the build command: three steps in one, corrections never quiet (B12), the golden day"`.

---

### Task 14: The site stack, the publish script, the operating note, the gates

**Files:**
- Create: `site-template.yaml` (from `flights-archive/site-template.yaml`: Description "il-grocery-prices public site: a private S3 bucket read only by one CloudFront distribution", Comment "il-grocery-prices headline basket", the same outputs `SiteBucketName`, `SiteDistributionId`, `SiteDomainName`), `scripts/publish.sh` (from flights': `STACK=il-grocery-prices-site`, `BUCKET_PREFIX=il-grocery-prices-site-sitebucket-`, marker `.basket-site`, check `python -m basket.check`, uploads `*.html` as `text/html; charset=utf-8` and `*.json` as `application/json; charset=utf-8`, `--delete` only after the bucket-name guard, one `/*` invalidation), `docs/terms.md` (owner gate below)
- Modify: `.github/workflows/ci.yml` (`cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`), `scripts/sync.sh` (also `aws s3 sync s3://<SiteBucketName>/days/ site/days/` when the stack exists, read-only), `docs/operations.md` (a section "The headline basket, by hand": sync, build, read the printout, review the page, publish; revising a day; the measured timings from Task 4), `.claude/QUEUE.md` and `.claude/OPEN_ISSUES.md` (state), `scripts/mutation_check.py` (the `TEMPLATE`-style entries for the site template, if `tests/test_site_template.py` pins rules)
- Test: `tests/test_site_template.py` (public access blocked on the bucket; an origin access control; the three outputs; `DefaultRootObject: index.html`)

- [ ] **Step 1: Tests, run (FAIL), the template, run (PASS), `cfn-lint`.**
- [ ] **Step 2: The scripts** and the operations section; `sh -n scripts/publish.sh`; a dry read of `publish.sh` against `docs/headline-basket.md`'s "Before anything is published".
- [ ] **Step 3: Owner gate, the law.** Ask the owner to read section 30(ה) in an official copy (Nevo, or the Knesset's law database) in his browser and to give the wording and the date; write `docs/terms.md` from what he gives, nothing invented; a claim he did not give is marked UNVERIFIED.
- [ ] **Step 4: Owner gate, the stack.** On the owner's go: `sam deploy --template-file site-template.yaml --stack-name il-grocery-prices-site --profile flights-sam --region il-central-1` (after `aws sts get-caller-identity --profile flights-sam` shows account 137953273942 / doron-admin). Read the outputs.
- [ ] **Step 5: Owner gate, the first upload.** The owner reviews `site/index.html` and `site/method.html` on the Mac. On his go: `sh scripts/publish.sh`. Open the printed address; fetch `days/2026-11-02.json`.
- [ ] **Step 6: Records and commit** `git commit -m "basket: site stack, publish script, operating note; first page published <date> (owner's go)"`.

---

## Deviations

(Appended during execution: what reality forced, and why.)

- 2026-11-02, Task 3: adding `tests/fixtures/basket/` broke seven tests that pin the fixture count (`tests/test_payload.py`) and map each fixture folder to a chain id (`tests/test_names.py`); both were updated (11 files, 8 gzips, `basket` → `7290000000001`). Any later fixture folder forces the same two edits.
- 2026-11-02, Task 3: Task 2's commit split a source block that an older mutation entry quotes ("price file without a store accepted"), so the full mutation check exited 1; fixed in a Task 2 fix round. From here every task runs the full mutation check, not only its own filter, before committing.
- 2026-11-02, Task 4, the real day (2026-11-02 on this Mac; `sh scripts/sync.sh 2026-11-02` brought 356 MB of raw files and 16 manifests): seconds as `basket.extract` printed them, rows, Parquet size, peak memory (`/usr/bin/time -l`), and the report's counts. Shufersal 93.9 s, 2,322,336 rows, 41.2 MB, 937 MB peak, 416 files from 416 stores, none passed over. Rami Levy 38.8 s, 993,278 rows, 23.1 MB, 673 MB peak, 97 stores from 169 files (72 passed over). Osher Ad 5.9 s, 151,604 rows, 3.3 MB, 234 MB peak, 24 stores, none passed over. Carrefour 46.6 s, 1,196,548 rows, 21.0 MB, 733 MB peak, 147 stores from 159 files (12 passed over). Yochananof 18.2 s, 476,502 rows, 6.8 MB, 473 MB peak, 47 stores, none passed over. Unreadable prices 0 at every chain; repeated 22 at Carrefour (the spec's figure) and 0 elsewhere; conflicting 0 everywhere. Five chains: 203.4 s, 5,140,268 rows, 95.4 MB. Each table's row and store counts equal its report's. No store key spans two sub-chains that day.
- 2026-11-02, Task 4: DuckDB reads the `chain=`/`date=` folders of a table's path as two extra columns (Hive partitioning) unless `read_parquet(..., hive_partitioning = false)`; the table itself holds the twelve columns. A price is also unreadable when it is not finite (`NaN`, `Infinity`, which `Decimal()` accepts) or too large for DECIMAL(12,2), so one bad value cannot stop a chain's day; a file that does not read still stops it (BadPriceFile).
- 2026-11-02, Task 5, the survey of the five store lists of 2026-11-02 (`data/raw/chain=<slug>/date=2026-11-02/Stores*`; store names matching `online|אונליין|אינטרנט|משלוח`, case-insensitive). Shufersal: 418 stores, 418 distinct ids (the spec's B2 and its sources say 416; with Be's 97 and store 413 out, 320 remain, not 318), StoreType 1 ×417 and 2 ×1; one match, store 413 'שופרסל ONLINE' (sub-chain 2, type 2), already out. Rami Levy: 99 stores, type 1 ×98 and 2 ×1; one match, store 39 'מרלוג אינטרנט' (sub-chain 1, type 2), which B2 keeps in by name, so it stays in and is the owner's call. Osher Ad: 24 stores, type 1 only, no match. Carrefour: 147 stores, type 1 ×144 and 2 ×3; one match, store 471 'קרפור אונליין   כפר סבא @ קרפור (5304)' (sub-chain 1, type 2), now out by id. Yochananof: 51 stores, type 1 ×50 and 2 ×1, no match. Every match is a StoreType 2 store; the type 2 stores no name matches stay in and are the owner's call: Carrefour 472 '@ יהלומים ביתן (9032)' and 473 'כפר סבא @ קוויק', Yochananof 150 'הדרים פיקאפ'. What StoreType 2 means is UNVERIFIED. Of these, Rami Levy 039 and Carrefour 471, 472 and 473 published a PriceFull file that day; Yochananof 150 did not. Every list spells the tags `SubChainID` and `StoreID`; no id is listed twice.
- 2026-11-02, Task 5, a ruling on the survey: Rami Levy's store 039 'מרלוג אינטרנט' (StoreType 2, the chain's internet logistics centre) is excluded by id as an online store. B2's intent, online stores out as Shufersal 413 and Carrefour 471 are, wins over B2's sentence naming 039 as included, which was written before the store's name was known; that sentence is corrected in the spec separately. Store 039 published a PriceFull file that day; Task 8's `apply_filters` joins rows to the included stores, so its rows will be left out there.
- 2026-11-02, Task 6, two rulings on the unit vocabulary of 2026-11-02 (5,140,268 rows, 21 unit strings). First: a stated size of exactly one unit is "not stated", and a count above one is still a size. 791,019 of the 932,478 `יחידות` rows state quantity 1.00, among them products with real weights. Of the 1,449 GS1 codes with a readable size at all five chains (each chain's most common size, measured in SQL before this ruling), 79 had one chain stating units and another grams or millilitres, and in 60 of them every chain stating units said 1; B7 would have left those items out over a count that carries no size. Second: the unambiguous spellings seen below the 1,000-row threshold are read too: `ליטרים` 663 (litres), `קילוגרמים` 141 (kilograms), `יח` 13 (units), `מ'ל` 5 (millilitres), `גרמים` 1 (grams).
- 2026-11-02, Task 8, rulings on the rules' review: equal totals share a rank and the next rank counts every chain above it (1, 1, 3); when no item passes B6 and B7, no chain has a total or a rank and there is no headline, never a division by zero, while B8's ranking stands; `price_basket` reads each chain's stores with a file from its `ChainDay` and takes no separate `with_file`; `stores_with_file_keys` lists each chain's included stores with a file by number, for the record. Observed on the real day (2026-11-02): Shufersal store 779 is in sub-chain 7 in the store list, but its file is named with sub-chain 005 (Be); the file name wins (B2), so its rows are left out while it still counts among Shufersal's 318 stores with a file.
- 2026-11-02, Task 8, a review finding and two rulings. Finding: `chain_prices` listed every row's price but counted distinct stores, and the extraction keeps one row per raw code, so a store listing one product under two raw codes with one normalized form ("0" + code and the code) put two prices into the median while `listing` counted it once. Ruling (B5): one price per store and normalized code, the lowest of the store's rows, grouped in SQL before the median and the counts; `ChainPrice.double_coded` counts such stores for the record (no included store did this on 2026-11-02). Ruling (B10): `LeftOut.details` and `DayResult.chains` are keyed by slug in sorted order, never in the order of the chain days given; a chain's place in the ranking is its `rank`.
- 2026-11-02, Task 9, three rulings on the day record. First (B12): what a rebuild compares with a published day leaves out `collected_by` as well as the run id, the code fingerprint, the build time, `revisions` and `revised`, since it is provenance, not a number; kept in, step one's hand-built day (collected at the actual time) and step two's run of the same day (11:00) would never compare equal, which B12 calls the usual case. Second (B4): `build_record` takes each chain's count of placeholder rows (at or below ₪0.01 among its included stores, counted by Task 13), and the record and the public day carry it as `extraction.placeholders`. Third (B10): the private record keeps per-item counts only (how many stores list an item, never which); the day's tables, which are kept, answer which stores list it in one query, and spec B10 is relaxed to match.
- 2026-11-02, Task 10, the real candidate table (`python -m basket.candidates --day 2026-11-02`, 3.2 s): 507 candidates. The rules narrow the shared codes so: 2,440 GS1 codes are listed at all five chains (no non-GS1 code is); 630 of them reach 80% of every chain's stores with a file (Shufersal 318, Rami Levy 96, Osher Ad 24, Carrefour 146, Yochananof 47); 5 of those have fewer than three chains stating a size and 118 have chains stating different sizes, leaving 507. With the online stores (Shufersal 413, Carrefour 471, Rami Levy 039) counted in, as when the spec measured it, the same code gives 629 at 80%, the spec's figure, and 508 candidates. The spec's named staples sugar, flour and tea have no candidate, nor do eggs, tuna, toothpaste, toilet paper or dish soap; each falls to the 80% rule at one chain or more (Sugat white sugar 1 kg at Shufersal 29 of 318 stores; Osem Bamba 80 g at Rami Levy 75 of 96). The proposal of 32 items is `basket/v1-proposed.json`, awaiting the owner.
- 2026-11-02, Task 12: the plan names the check's tests `tests/test_check.py`, which already holds the collector's morning-check tests (`CHECK` and `STORE_FOR_CHECK` in `scripts/mutation_check.py` run it); the basket check's tests are `tests/test_basket_check.py`, and `CHECK_BASKET` names that file. Two readings of the rules: a site with no `index.html` is a problem ("index.html: missing"), since the index page must carry every ALWAYS phrase; and with no day file under `days/`, the day counts as never revised, so "Revised on" on the index page is then a problem.

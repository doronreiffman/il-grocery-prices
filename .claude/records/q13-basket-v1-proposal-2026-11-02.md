# Task 10 report: candidates, and the basket proposal

Status: DONE_WITH_CONCERNS (the concerns are owner calls on the proposal, listed at the end; the code has none open).

## Implemented

- `src/basket/candidates.py`: `Candidate(code, names, size, coverage, medians)`; `candidates(con, with_file, min_share=Decimal("0.8"), min_stating=3)`; `write_candidates_csv(cands, path)`; the CLI `python -m basket.candidates --day D [--raw data/raw] [--tables data/tables] [--out data/candidates-<day>.csv]` (the brief's Step 6 runs it with `--day` alone, so the three paths default to the brief's values).
  - Rules: GS1 codes (`rows.gs1`), matched by `code_norm`; listed at every chain of `with_file`; at each chain `listing >= min_share × with_file` (compared by multiplication, no division); each chain's size from `basket.rules.chain_sizes` (B7's mode over `normal_size`, so "1 unit" is no size); at least `min_stating` chains stating, all equal. Medians from `basket.rules.chain_prices` (B5). Names: the most common string over the chain's rows for the code, a tie to the first in plain string order. Sorted by code.
  - CSV: `code, size`, then `<slug>_name, <slug>_coverage, <slug>_median` per slug in `SLUGS` order. Size as "1000 gml"; coverage to two places rounded down (1.00 only when every store lists it); median exact.
  - CLI: reads each chain's store list (`day_store_list`, `read_stores`, `included`), opens the day, `apply_filters` with `EXCLUDED[slug].sub_chains`, `stores_with_file`, then `candidates`; stops with "no store list for chain '<slug>' on or before <day>" when a chain has none.
- `tests/test_candidates.py`: 13 tests (below).
- `scripts/mutation_check.py`: `CANDIDATES` tuple and 9 entries under `# basket: candidates`, every name starting "candidates " so `mutation_check.py candidates` selects them (no other entry's name contains the word).
- `basket/v1-proposed.json`: the proposed basket, 32 items.
- `docs/headline-basket-plan.md`: a Task 10 line in `## Deviations` (Step 6 asks for the count there).

## Tests

A synthetic day: five chains (the real slugs), ten stores each. A everywhere, 1 litre at two chains and 1000 ml at three, Osher Ad publishing it as "0" + A → in; B missing at Yochananof → out; C at 5 of 10 Carrefour stores → out; D 500 g at two chains, 1 kg at three → out; E 500 g at two chains, unknown at three → out; F non-GS1 → out; G at exactly 8 of 10 Rami Levy stores → in; H 500 g at three chains, "1 יחידות" at two → in.

- `test_candidates_are_the_codes_passing_every_rule_sorted_by_code` ([A, G, H]; H's rows come first in the tables)
- `test_a_code_everywhere_in_one_size_is_a_candidate_with_its_names_coverage_and_medians` (the whole Candidate: names, 1000 gml, coverage 1, medians 5.55 to 9.55)
- `test_a_code_breaking_a_rule_is_out` ×5 (B, C, D, E, F, each with its reason as the id)
- `test_exactly_the_share_is_enough` (G, coverage 0.8)
- `test_one_unit_states_no_size_and_three_stating_chains_are_enough` (H, 500 gml)
- `test_names_are_the_most_common_string_per_chain` (Shufersal 6 against 4 where the minority string sorts first; Rami Levy 5 against 5, the later-inserted string first in order)
- `test_csv_columns` (the header and one row; dicts given in reverse slug order; 2/3 → "0.66", 0.999 → "0.99", 0.8 → "0.80"; medians "12.075", "5.90")
- `test_main_counts_only_the_included_stores_and_writes_the_day_s_table` (defaults: run from a temp dir with `data/raw` and `data/tables`; Shufersal's store 413 is left out by `EXCLUDED`, so A at Shufersal's one other store is 1 of 1, and B, listed there only at 413, is out)
- `test_main_stops_without_a_store_list`

### TDD evidence

RED. First run, before any module: a collection error (`ModuleNotFoundError: No module named 'basket.candidates'`). To show each test failing on its own assertion, a stub with the interfaces (`candidates` returning `[]`, an empty CSV, a `main` that does nothing) was put in place and run:

```
$ .venv/bin/pytest tests/test_candidates.py
FAILED tests/test_candidates.py::test_candidates_are_the_codes_passing_every_rule_sorted_by_code
FAILED tests/test_candidates.py::test_a_code_everywhere_in_one_size_is_a_candidate_with_its_names_coverage_and_medians
FAILED tests/test_candidates.py::test_exactly_the_share_is_enough - KeyError:...
FAILED tests/test_candidates.py::test_one_unit_states_no_size_and_three_stating_chains_are_enough
FAILED tests/test_candidates.py::test_names_are_the_most_common_string_per_chain
FAILED tests/test_candidates.py::test_csv_columns - AssertionError: assert []...
FAILED tests/test_candidates.py::test_main_counts_only_the_included_stores_and_writes_the_day_s_table
FAILED tests/test_candidates.py::test_main_stops_without_a_store_list - Faile...
8 failed, 5 passed in 0.34s
```

The 5 that pass against the stub are the "is out" cases, which only assert absence; the mutations below prove each of them.

GREEN:

```
$ .venv/bin/pytest tests/test_candidates.py
13 passed in 0.37s
```

(The repo's `addopts = "-q"` plus a second `-q` hides pytest's summary line, so these runs drop the extra `-q`.)

Full suite before the commit:

```
$ .venv/bin/pytest -q            → exit 0   (without the extra -q: 937 passed in 8.06s)
$ .venv/bin/pytest --cov=collector --cov=basket --cov-fail-under=95 -q   → exit 0
  TOTAL 1138 statements, 0 missed, 100%; Required test coverage of 95% reached. Total coverage: 100.00%
```

### Mutations

`mutation_check.py candidates`, all caught:

```
CAUGHT candidates a four-chain code passes
CAUGHT candidates coverage share at half
CAUGHT candidates two stating chains enough
CAUGHT candidates non-GS1 code passes
CAUGHT candidates exactly the share refused
CAUGHT candidates disagreeing sizes pass
CAUGHT candidates name tie to the last in order
CAUGHT candidates name first in order, not most common
CAUGHT candidates coverage rounded half up in the table
Files restored. Every mutation was caught.
```

The brief's four, plus five pinning tests added here (the 80% boundary, D's disagreement, the name tie, the name count, the CSV's rounding). "A four-chain code passes" is caught by a `KeyError: ('yochananof', '7290000000114')` in the fixture (the code after the rule reads every chain's size and name), not by B's assertion; the run still fails.

Full check, run alone before the commit:

```
$ .venv/bin/python scripts/mutation_check.py      (exit 0; 643 lines CAUGHT, none MISSED, none STALE)
...
CAUGHT candidates name tie to the last in order
CAUGHT candidates name first in order, not most common
CAUGHT candidates coverage rounded half up in the table
Files restored. Every mutation was caught.
```

## The real candidate table (2026-11-02)

`PYTHONPATH=src .venv/bin/python -m basket.candidates --day 2026-11-02` → "507 candidates written to data/candidates-2026-11-02.csv", 3.2 s.

How the rules narrowed it (a throwaway script over the same view, with the same rules):

| step | codes |
|---|---|
| GS1 codes listed at all five chains (no non-GS1 code is listed at all five) | 2,440 |
| at 80% or more of every chain's stores with a file (Shufersal 318, Rami Levy 96, Osher Ad 24, Carrefour 146, Yochananof 47) | 630 |
| fewer than three chains state a size | −5 |
| the chains stating a size disagree | −118 |
| candidates | 507 |

With the three online stores counted in (Shufersal 413, Carrefour 471, Rami Levy 039), as when the spec measured, the same code gives 629 at 80% (the spec's figure exactly) and 508 candidates.

Staples the spec names that have no candidate: sugar, flour and tea; also eggs, tuna, toothpaste, toilet paper and dish soap. Each falls to the 80% rule at one chain or more: Sugat white sugar 1 kg is at Shufersal in 29 of 318 stores and Rami Levy 18 of 96; Osem Bamba 80 g misses only at Rami Levy, 75 of 96 (78%); eggs fall short at all five chains.

## The proposal (`basket/v1-proposed.json`), 32 items

Layout as `tests/baskets/basket-test.json`: `version` "v1", `since` "2026-11-02" (a placeholder the approval date replaces), `selection_day` "2026-11-02", each item with `code`, `name_en`, `name_he`, `size` (the candidate's agreed size, copied from the CSV by the script that wrote the file), `category`, and `coverage` per chain as the CSV's two-place strings. `load_basket(Path("basket/v1-proposed.json"))` with the default limits (25 to 40) loads it: 32 items, every size equal to the candidate table's.

Names were written by hand against the five chains' strings (brand, product, size); a brand is named only when at least one chain's string carries it.

Each chain cell: coverage / median price.

| # | code | name_en | name_he | size | category | shufersal | ramilevy | osherad | carrefour | yochananof |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 7290004131074 | Tnuva milk 3%, 1 L carton | חלב תנובה 3% בקרטון 1 ליטר | 1000 gml | dairy | 0.99 / ₪7.35 | 1.00 / ₪7.20 | 1.00 / ₪7.20 | 1.00 / ₪7.35 | 1.00 / ₪7.35 |
| 2 | 7290004127329 | Tnuva cottage cheese 5%, 250 g | קוטג' תנובה 5% 250 גרם | 250 gml | dairy | 0.98 / ₪6.40 | 1.00 / ₪5.90 | 1.00 / ₪5.90 | 1.00 / ₪6.10 | 1.00 / ₪5.90 |
| 3 | 7290000048185 | Tnuva white cheese 5%, 250 g | גבינה לבנה תנובה 5% 250 גרם | 250 gml | dairy | 0.95 / ₪5.87 | 1.00 / ₪5.80 | 1.00 / ₪5.80 | 0.96 / ₪5.87 | 1.00 / ₪5.87 |
| 4 | 7290116932033 | Tnuva butter, 200 g | חמאה תנובה 200 גרם | 200 gml | dairy | 0.91 / ₪10.70 | 1.00 / ₪8.90 | 0.95 / ₪8.90 | 1.00 / ₪10.30 | 1.00 / ₪9.50 |
| 5 | 7290000408316 | Danone Bio yogurt 3%, 200 g | יוגורט דנונה ביו 3% 200 גרם | 200 gml | dairy | 0.98 / ₪4.90 | 1.00 / ₪3.80 | 1.00 / ₪3.80 | 1.00 / ₪4.90 | 1.00 / ₪3.90 |
| 6 | 7290102394821 | Noam sliced yellow cheese 28%, 200 g | גבינה צהובה נעם 28% פרוסה 200 גרם | 200 gml | dairy | 0.92 / ₪21.30 | 0.85 / ₪18.50 | 1.00 / ₪18.50 | 0.97 / ₪23.50 | 0.97 / ₪18.90 |
| 7 | 7290003029181 | Yotvata chocolate milk, 1 L bottle | שוקו יטבתה בבקבוק 1 ליטר | 1000 gml | dairy | 0.98 / ₪14.20 | 1.00 / ₪12.30 | 1.00 / ₪12.30 | 1.00 / ₪13.90 | 1.00 / ₪12.30 |
| 8 | 7290000211442 | Sugat Persian rice, 1 kg | אורז פרסי סוגת 1 ק"ג | 1000 gml | pantry | 0.99 / ₪11.90 | 1.00 / ₪11.70 | 1.00 / ₪11.70 | 1.00 / ₪11.90 | 1.00 / ₪11.90 |
| 9 | 7290000060880 | Osem spaghetti no. 8, 500 g | ספגטי אסם מס' 8 500 גרם | 500 gml | pantry | 0.99 / ₪7.90 | 1.00 / ₪4.90 | 1.00 / ₪4.90 | 1.00 / ₪7.50 | 1.00 / ₪4.90 |
| 10 | 7290000060200 | Osem ptitim, couscous shape, 500 g | פתיתים אפויים קוסקוס אסם 500 גרם | 500 gml | pantry | 0.99 / ₪8.90 | 1.00 / ₪4.90 | 1.00 / ₪4.90 | 1.00 / ₪8.90 | 1.00 / ₪5.50 |
| 11 | 8076802085738 | Barilla penne rigate, 500 g | פנה ריגטה ברילה 500 גרם | 500 gml | pantry | 0.89 / ₪9.90 | 0.95 / ₪7.90 | 1.00 / ₪7.90 | 0.97 / ₪9.90 | 1.00 / ₪7.90 |
| 12 | 7290000144474 | Canola oil, 1 L | שמן קנולה 1 ליטר | 1000 gml | pantry | 0.92 / ₪15.90 | 0.98 / ₪14.90 | 1.00 / ₪14.90 | 1.00 / ₪17.90 | 1.00 / ₪14.90 |
| 13 | 7290000176420 | Elite instant coffee, 200 g | קפה נמס עלית 200 גרם | 200 gml | pantry | 0.98 / ₪26.90 | 1.00 / ₪24.90 | 1.00 / ₪24.90 | 1.00 / ₪26.90 | 1.00 / ₪24.90 |
| 14 | 7290000523804 | Melach HaAretz fine salt, 1 kg | מלח עדין מלח הארץ 1 ק"ג | 1000 gml | pantry | 0.91 / ₪8.90 | 0.92 / ₪7.90 | 1.00 / ₪7.90 | 0.98 / ₪8.90 | 1.00 / ₪7.90 |
| 15 | 7290112494351 | Telma Alufim cornflakes, 850 g | קורנפלקס אלופים תלמה 850 גרם | 850 gml | pantry | 0.99 / ₪23.90 | 1.00 / ₪19.90 | 1.00 / ₪19.90 | 1.00 / ₪23.90 | 1.00 / ₪19.90 |
| 16 | 7290106576537 | Tzabar restaurant hummus, 700 g | חומוס מסעדה צבר 700 גרם | 700 gml | spreads | 0.97 / ₪15.50 | 1.00 / ₪10.80 | 1.00 / ₪10.80 | 1.00 / ₪15.50 | 1.00 / ₪10.90 |
| 17 | 7290106577282 | Tzabar tahini salad, 400 g | סלט טחינה צבר 400 גרם | 400 gml | spreads | 0.87 / ₪15.50 | 0.97 / ₪11.90 | 1.00 / ₪11.90 | 0.98 / ₪17.90 | 0.97 / ₪12.90 |
| 18 | 5410126116953 | Lotus biscuit spread, 400 g | ממרח עוגיות לוטוס 400 גרם | 400 gml | spreads | 0.98 / ₪25.90 | 0.93 / ₪19.90 | 1.00 / ₪19.90 | 0.92 / ₪25.90 | 1.00 / ₪19.90 |
| 19 | 7290006374738 | Yad Mordechai strawberry jam, 340 g | קונפיטורת תות יד מרדכי 340 גרם | 340 gml | spreads | 0.95 / ₪16.80 | 1.00 / ₪12.90 | 1.00 / ₪12.90 | 0.99 / ₪17.90 | 1.00 / ₪13.90 |
| 20 | 7290000066196 | Bissli grill, 200 g | ביסלי גריל 200 גרם | 200 gml | snacks | 0.93 / ₪9.90 | 0.95 / ₪6.50 | 0.83 / ₪6.50 | 0.95 / ₪9.90 | 1.00 / ₪6.90 |
| 21 | 7290100687109 | Bamba nougat-filled, 60 g | במבה במילוי נוגט 60 גרם | 60 gml | snacks | 0.99 / ₪6.50 | 0.98 / ₪4.50 | 1.00 / ₪4.50 | 1.00 / ₪6.50 | 1.00 / ₪4.50 |
| 22 | 7290000178721 | Tapuchips plain potato chips, 200 g | תפוצ'יפס טבעי 200 גרם | 200 gml | snacks | 0.96 / ₪11.90 | 0.98 / ₪10.90 | 0.91 / ₪10.90 | 0.98 / ₪12.90 | 1.00 / ₪10.90 |
| 23 | 7290000170053 | Elite Para milk chocolate, 100 g | שוקולד חלב פרה עלית 100 גרם | 100 gml | snacks | 0.94 / ₪9.90 | 1.00 / ₪8.50 | 1.00 / ₪8.50 | 0.83 / ₪10.90 | 1.00 / ₪8.50 |
| 24 | 7290110115364 | Coca-Cola, 6 × 1.5 L | קוקה קולה 6 × 1.5 ליטר | 9000 gml | soft drinks | 0.99 / ₪47.90 | 0.96 / ₪45.90 | 1.00 / ₪46.90 | 1.00 / ₪47.90 | 1.00 / ₪45.90 |
| 25 | 7290110114961 | Prigat orange drink, 1.5 L | פריגת תפוזים 1.5 ליטר | 1500 gml | soft drinks | 0.99 / ₪9.50 | 1.00 / ₪8.20 | 1.00 / ₪8.20 | 0.99 / ₪9.50 | 1.00 / ₪8.20 |
| 26 | 7290110114855 | Neviot mineral water, 6 × 1.5 L | מים מינרליים נביעות 6 × 1.5 ליטר | 9000 gml | soft drinks | 0.99 / ₪17.50 | 1.00 / ₪15.90 | 1.00 / ₪15.90 | 1.00 / ₪17.50 | 1.00 / ₪16.50 |
| 27 | 7290019056164 | Schweppes soda, 4 × 1.5 L | סודה שוופס 4 × 1.5 ליטר | 6000 gml | soft drinks | 0.99 / ₪14.90 | 1.00 / ₪12.40 | 1.00 / ₪12.50 | 1.00 / ₪13.90 | 1.00 / ₪12.90 |
| 28 | 7290000288024 | Sano Javel bleach, lemon, 4 L | אקונומיקה סנו ז'אוול לימון 4 ליטר | 4000 gml | cleaning | 0.98 / ₪17.90 | 1.00 / ₪16.90 | 1.00 / ₪16.90 | 0.99 / ₪17.90 | 1.00 / ₪16.90 |
| 29 | 7290000412481 | 00 toilet cleaner, 1 L | מנקה אסלות 00 1 ליטר | 1000 gml | cleaning | 0.95 / ₪8.60 | 0.98 / ₪7.50 | 1.00 / ₪7.50 | 0.98 / ₪10.90 | 1.00 / ₪7.90 |
| 30 | 7290116536262 | Badin Extra Plus fabric softener, blue, 960 ml | מרכך כביסה בדין אקסטרה פלוס כחול 960 מ"ל | 960 gml | cleaning | 0.96 / ₪19.90 | 0.91 / ₪15.90 | 1.00 / ₪15.90 | 0.99 / ₪19.90 | 1.00 / ₪16.90 |
| 31 | 7290112492449 | Pinuk shampoo, regular hair, 700 ml | שמפו פינוק לשיער רגיל 700 מ"ל | 700 gml | hygiene | 0.98 / ₪15.90 | 0.97 / ₪13.90 | 1.00 / ₪13.90 | 0.99 / ₪15.90 | 1.00 / ₪13.90 |
| 32 | 8714789733289 | Palmolive shower gel, milk and honey, 750 ml | תחליב רחצה פלמוליב חלב ודבש 750 מ"ל | 750 gml | hygiene | 0.82 / ₪21.90 | 0.89 / ₪19.50 | 0.95 / ₪19.50 | 0.93 / ₪28.90 | 1.00 / ₪19.90 |

Shape: dairy 7, pantry 8, spreads 4, snacks 4, soft drinks 4, cleaning 3, hygiene 2. Lowest coverage anywhere 0.82, so B6's 50% guard has room. No alcohol, tobacco or infant formula; also left out: seasonal products (Krembo, ice cream), energy drinks, and the only diaper candidate (an alternate below).

Sum of the 32 medians per chain, for a sense of scale only (not the rules' output: no guards applied): Shufersal ₪470.82, Rami Levy ₪401.40, Osher Ad ₪402.50, Carrefour ₪487.42, Yochananof ₪408.92.

### Alternates (two or three per category)

| category | code | name (draft) | size | shufersal | ramilevy | osherad | carrefour | yochananof |
|---|---|---|---|---|---|---|---|---|
| dairy | 7290011194246 | Strauss cottage cheese 5%, 250 g | 250 gml | 0.98 / ₪7.20 | 1.00 / ₪6.60 | 1.00 / ₪6.70 | 1.00 / ₪6.80 | 1.00 / ₪6.70 |
| dairy | 7290004125455 | Tnuva sour cream 15%, 200 ml | 200 gml | 0.97 / ₪2.84 | 1.00 / ₪2.80 | 1.00 / ₪2.80 | 1.00 / ₪2.84 | 1.00 / ₪2.84 |
| dairy | 7290000042435 | Tnuva milk 1%, 1 L carton | 1000 gml | 0.97 / ₪6.92 | 0.97 / ₪6.80 | 1.00 / ₪6.80 | 0.96 / ₪6.92 | 1.00 / ₪6.92 |
| pantry | 7290003643004 | Sugat basmati rice, 1 kg | 1000 gml | 0.99 / ₪17.90 | 1.00 / ₪14.50 | 1.00 / ₪14.60 | 1.00 / ₪16.90 | 1.00 / ₪14.90 |
| pantry | 7290000072753 | Nescafé Taster's Choice instant coffee, 200 g | 200 gml | 0.99 / ₪39.90 | 1.00 / ₪35.90 | 1.00 / ₪35.90 | 1.00 / ₪39.90 | 1.00 / ₪35.90 |
| pantry | 7290000111186 | Telma mayonnaise, 500 g | 500 gml | 0.99 / ₪13.90 | 1.00 / ₪10.90 | 1.00 / ₪10.90 | 1.00 / ₪13.90 | 1.00 / ₪10.90 |
| spreads | 8719200998018 | Blue Band margarine, butter taste, 200 g | 200 gml | 0.93 / ₪6.90 | 0.95 / ₪6.10 | 1.00 / ₪6.10 | 0.95 / ₪6.90 | 1.00 / ₪6.20 |
| spreads | 7290107945165 | Yad Mordechai apricot jam, 340 g | 340 gml | 0.89 / ₪15.90 | 0.98 / ₪12.90 | 1.00 / ₪12.90 | 0.94 / ₪17.90 | 1.00 / ₪13.90 |
| spreads | 7290106573628 | Tzabar hummus with tahini, 400 g (a third Tzabar item: a swap, not an addition) | 400 gml | 0.86 / ₪13.90 | 0.95 / ₪11.90 | 1.00 / ₪11.90 | 0.90 / ₪16.90 | 1.00 / ₪12.90 |
| snacks | 7290100850930 | Doritos plain, 70 g | 70 gml | 0.98 / ₪5.50 | 0.98 / ₪3.90 | 1.00 / ₪3.90 | 0.98 / ₪5.50 | 0.97 / ₪4.00 |
| snacks | 7290000074184 | Osem Petit Beurre biscuits, 500 g | 500 gml | 0.99 / ₪13.90 | 1.00 / ₪8.90 | 1.00 / ₪8.90 | 1.00 / ₪13.90 | 1.00 / ₪8.90 |
| snacks | 72991008 | Pesek Zman classic, 45 g | 45 gml | 0.98 / ₪6.50 | 0.98 / ₪4.90 | 0.95 / ₪4.90 | 0.97 / ₪6.10 | 1.00 / ₪4.90 |
| soft drinks | 7290019056973 | Mey Eden mineral water, 6 × 1.5 L | 9000 gml | 0.98 / ₪16.50 | 1.00 / ₪14.90 | 1.00 / ₪14.90 | 1.00 / ₪16.50 | 1.00 / ₪14.90 |
| soft drinks | 7290110115463 | Fuze Tea peach, 1.5 L | 1500 gml | 0.99 / ₪10.50 | 1.00 / ₪8.60 | 1.00 / ₪8.60 | 1.00 / ₪10.50 | 1.00 / ₪8.60 |
| soft drinks | 7290001247129 | Spring orange nectar, 1 L carton | 1000 gml | 0.97 / ₪7.90 | 0.97 / ₪5.90 | 1.00 / ₪5.90 | 0.97 / ₪7.80 | 0.97 / ₪5.90 |
| cleaning | 7290108350616 | Maxima fabric softener, blue, 1 L | 1000 gml | 0.95 / ₪19.90 | 0.86 / ₪18.80 | 1.00 / ₪18.80 | 0.93 / ₪19.90 | 0.97 / ₪18.90 |
| cleaning | 7290013269621 | Ritzpaz Fresh Home floor cleaner, melon, 2 L | 2000 gml | 0.90 / ₪19.90 | 0.96 / ₪19.70 | 1.00 / ₪19.70 | 0.93 / ₪25.90 | 1.00 / ₪19.90 |
| cleaning | 7290000289069 | Sano Javel cleaning spray, lemon, 1 L | 1000 gml | 0.99 / ₪19.90 | 1.00 / ₪16.90 | 1.00 / ₪16.90 | 0.97 / ₪23.90 | 1.00 / ₪17.90 |
| hygiene | 7290112492593 | Pinuk shower gel, classic, 700 ml | 700 gml | 0.97 / ₪14.90 | 0.98 / ₪13.90 | 1.00 / ₪13.90 | 0.98 / ₪17.90 | 1.00 / ₪13.90 |
| hygiene | 7290112492531 | Pinuk conditioner, regular hair, 700 ml | 700 gml | 0.97 / ₪15.40 | 0.97 / ₪13.90 | 1.00 / ₪13.90 | 0.98 / ₪15.90 | 1.00 / ₪13.90 |
| hygiene | 7290000197463 | Huggies Freedom Dry 4+, 32 diapers | 32 unit | 0.92 / ₪44.90 | 0.80 / ₪41.50 | 1.00 / ₪41.50 | 0.93 / ₪48.90 | 0.97 / ₪41.90 |
| bread (not a spec category) | 7290018500361 | Angel sliced standard bread, 900 g | 900 gml | 0.89 / ₪10.05 | 0.97 / ₪8.30 | 0.95 / ₪8.30 | 1.00 / ₪10.05 | 1.00 / ₪8.40 |
| bread (not a spec category) | 7290014940901 | Angel plain whole-wheat bread, 750 g | 750 gml | 0.90 / ₪16.90 | 1.00 / ₪15.90 | 0.95 / ₪15.90 | 0.98 / ₪17.50 | 1.00 / ₪15.90 |

## Files changed

- `src/basket/candidates.py` (new)
- `tests/test_candidates.py` (new)
- `scripts/mutation_check.py` (the `CANDIDATES` tuple and 9 entries)
- `basket/v1-proposed.json` (new)
- `docs/headline-basket-plan.md` (one line in `## Deviations`)
- Not committed: `data/candidates-2026-11-02.csv` (gitignored)

Commit: `2b43ce8` basket: candidates for selection; basket v1 proposed (awaiting the owner)

## Self-review

- Against the brief: Steps 1 to 7 and 9 done; Step 8 not done (the owner's gate, as instructed). The interfaces match the brief's signatures; the CLI's flags are the brief's, with its paths as defaults so Step 6's `--day` alone works.
- Beyond the brief: the CLI's stop when a chain has no store list (one line, tested), and five mutations beyond the brief's four, each pinning a test written here. Nothing else.
- Tests check behaviour through the public functions on a real DuckDB view built by the real extraction writer; no mocks.
- The "every chain" reading: the brief says codes "listed in every chain in `rows`"; the code reads "every chain of `with_file`", which the CLI builds from the five slugs it opens, so the two are the same on any day the CLI runs.
- Output: the suite runs without warnings; the CLI prints one line.

## Concerns (owner calls on the proposal)

1. "At most two items from one brand line" is read as a product line within a brand (Osem pasta, Tzabar salads, Pinuk). Read as the maker, the proposal breaks it twice: Tnuva has 4 items (milk, cottage, white cheese, butter) and Osem 3 by the strings (spaghetti, ptitim, Bamba), 4 if Bissli is Osem's too (UNVERIFIED: no chain's string says so). Swaps that meet the stricter reading from the alternates: Tnuva cottage → Strauss cottage, Tnuva butter → Blue Band margarine, Osem ptitim → Sugat basmati rice, Bamba → Doritos.
2. The spec's named staples sugar, flour and tea have no candidate (all fall to the 80% rule; figures above). The basket has none of them unless the owner relaxes the rule for an item.
3. Bread has no category in the spec; two Angel breads are offered as alternates under "bread".
4. Several staples have nearly equal medians at every chain (milk 3% ₪7.20 to ₪7.35, white cheese ₪5.80 to ₪5.87, Persian rice ₪11.70 to ₪11.90); they add little to the gap. Whether they are price-controlled is UNVERIFIED.
5. Names resting on a cut string: the strawberry jam's strings stop at "יד מרד" / "יד מור" (the maker's apricot jam at Carrefour spells "יד מרדכי" in full); the canola oil's maker is cut at "עץ" in every string, so its name carries no brand.
6. Strings that differ in a detail, same code: Barilla penne is "פסטה ברילה צורות צ.ק" (Barilla shapes) at Yochananof; Tapuchips is "מלוח" (salted) at Osher Ad and "טבעי" (natural) elsewhere; the Tnuva cottage code reads "בעלז" at Shufersal and "מהדרי…" at Carrefour (a kashrut variant; another Tnuva 5% cottage code, 7290000041445, is also a candidate, at 0.90 minimum coverage against this one's 0.98).
7. `since` holds the placeholder "2026-11-02" until the approval date replaces it (Step 8).

For the decision log (choices made here, each the controller's or owner's to overturn):
- Coverage in the candidate CSV and the proposal is written to two places rounded down, so 1.00 means every store lists the item. Why: a share is never overstated.
- The candidate CLI defaults `--raw`, `--tables` and `--out` to `data/raw`, `data/tables` and `data/candidates-<day>.csv`. Why: the brief's Step 6 runs it with `--day` alone.

## Step 8: the owner's approval (2026-11-02, "approved for v1")

- `git mv basket/v1-proposed.json basket/v1.json`. The proposal already held `since` "2026-11-02", the approval date, so the file is byte-for-byte the proposal (`cmp` against `HEAD:basket/v1-proposed.json`: identical; git records a 100% rename). 32 items, `version` "v1", `selection_day` "2026-11-02".
- `tests/test_basket_file.py::test_v1_basket_loads`: `load_basket(Path(__file__).parent.parent / "basket" / "v1.json")` with the default limits; 32 items, version "v1", `since == date(2026, 11, 2)`, every code `is_gs1`.
- `.venv/bin/pytest tests/test_basket_file.py -q`: exit 0, 38 passed. `.venv/bin/pytest -q`: exit 0, 990 passed. `.venv/bin/python scripts/mutation_check.py "basket file"`: 17 caught, "Files restored. Every mutation was caught.", exit 0.
- Commit `c196785` "basket: v1 approved by the owner 2026-11-02: the 32 items, since 2026-11-02".
- Left alone (Task 13's): `src/basket/build.py` line 3, the module docstring's example run, still names `--basket basket/v1-proposed.json`, a file that no longer exists; the flag's default is `basket/v1.json`, so the command works without it.

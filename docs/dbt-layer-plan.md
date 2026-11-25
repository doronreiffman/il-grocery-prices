# The dbt layer: analysis models and data tests (implementation plan)

Grade, quoted from the approved design (`docs/dbt-layer.md`, line 3): "**Grade:** the project's grade: a test for every component, a planted bug for every rule, a fresh review before anything ships, dependencies pinned and at least a month old, docs in plain words. Not production: nothing here feeds the live site or runs in AWS."

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a dbt project in `dbt/`, run on the Mac from an environment of its own, that reads the prices, items and promotions tables the morning writes, builds fourteen models (four analysis tables, each a shopper's question), runs 29 data tests on the real rows, compares each analysis table with a number the site published, and shows its lineage in the README; proved by unit tests on synthetic rows, a build on the golden 90 days' real extraction, a bad-rows build in which every data test fails as it should, and a planted bug for every rule; $0 a month.

**Architecture:** seven sources read in place (`external_location`) from paths held in `dbt_project.yml` vars; six staging views, two lists, two intermediate models and four analysis tables, as the design's section 2 draws them. The tests call dbt as a subprocess (as Node is called for `search.js`), each run in temporary folders, from the project's own `.venv`; dbt itself lives in `.venv-dbt`, never in the environment the collector's tests run in. The sync gains the named day's prices and promotions tables and `--exact-timestamps` on its items line.

**Tech Stack:** dbt-core 1.12.6, dbt-duckdb 1.11.0, duckdb 1.5.6 on Python 3.13, in `.venv-dbt/` from `requirements-dbt.txt` (59 exact pins, one of whose builds fetches a wheel from GitHub); the project's `.venv` for the tests (pytest 9.1.1, pytest-cov 7.1.0, duckdb 1.5.6, and PyYAML 6.0.3, pinned here); `scripts/mutation_check.py`; Mermaid in the README, which GitHub draws.

**Spec:** `docs/dbt-layer.md` (approved 2026-11-25; section 6 amended the same day: "One pin fetches from GitHub" and "The version"). Read all of it first, "The owner's answers (2026-11-25)" and "Calls made in this design" included. Then what the SQL mirrors: the docstrings of `src/shopper/verdict.py` (S0 to S8, the front list), `src/shopper/measures.py` (`MIN_FRONT_DAYS`, `RECENT_DAYS`), `src/shopper/history.py` (`READ_DAYS`, `counted`, `covered`), `src/shopper/items.py` (the module docstring, `COLUMNS`, `ColumnReport`), `src/shopper/promos.py`, `src/shopper/promotions.py` (`KINDS`), `src/shopper/columns.py` (`COLUMNS`), `src/basket/rules.py` (B2 to B5), `src/basket/chains.py` (`EXCLUDED`), `src/basket/barcode.py` (`is_gs1`), `src/shopper/siteday.py` (the front block; `_row`, line 133), `src/shopper/build.py:255-310` (the promotions line); and the tests and scripts it joins: `tests/shopper_golden.py` (its docstring, `write_day`, `write_basket`), `tests/test_golden_90.py` (`test_the_golden_verdicts`), `tests/test_scripts.py` (the stand-in `aws` and every sync.sh test), `scripts/sync.sh`, `scripts/mutation_check.py`, `tests/test_mutation_targets.py`, both workflows, `docs/operations.md` ("Develop"; "The shopper site, by hand", step 1).

## How this plan runs

Branch `q28-dbt-layer`, worktree `../il-grocery-prices-q28-dbt`, on main at a54c6f3 plus the design's commit 52307bc. Run by superpowers:subagent-driven-development: a fresh implementer per task, a fresh reviewer per task, and a whole-branch review at the end (Task 12).

**Before wave 1** (the controller, in `../il-grocery-prices-q28-dbt`): measure the baseline (the full suite and the staleness check) and write it in "Deviations"; then commit this plan and the design's amendment on `q28-dbt-layer`: `git add docs/dbt-layer-plan.md docs/dbt-layer.md && git commit -m "The dbt layer's plan (q28), and the design's note on the one pin that fetches from GitHub"`. Every later branch is cut after that commit.

**"Deviations" has one writer:** the controller, in the `q28-dbt-layer` worktree. An implementer or reviewer reports in its reply what goes there; a step below that says "for Deviations" means that report.

| Wave | Tasks | Side by side? | Needs |
|---|---|---|---|
| 1 | Task 1 (the environment and the frame), Task 3 (the sync) | yes | the plan's commit |
| 2 | Task 2 (the staging views and the lists) | alone | Task 1 |
| 3 | Task 4 (the basket's models), Task 5 (the deals' models), Task 6 (the promotions' reach) | yes | Task 2 |
| 4 | Tasks 7, 8, 9, 10 in that order; Task 11 (the lineage and the docs) beside them | 7 to 10 serial; 11 beside | 7: Tasks 4 to 6. 11: Tasks 2 to 6 and 3 |
| 5 | Task 12 (the whole-branch review), then Task 13 (the Mac's real tables) | serial | everything before |

Tasks 7 to 10 stay serial: they share `tests/test_dbt_golden.py`, and each later task's bad rows must leave the earlier tasks' expected results standing. Side-by-side tasks share only `scripts/mutation_check.py`, each writing its targets and planted bugs right after the anchor comment named for it (Task 1 writes the anchors; Task 3 writes after the existing `(q42 archive)` lines), so two branches never edit the same lines. A side-by-side task works on a branch `q28-<name>` in a worktree `../il-grocery-prices-q28-<name>`, cut from `q28-dbt-layer`'s head when its wave starts; it gets dbt with `ln -s ../il-grocery-prices-q28-dbt/.venv-dbt .venv-dbt` (ignored: Task 1). The controller merges a wave's branches in task order, then runs the full suite on the merged branch before the next wave. The full suite runs in one worktree at a time.

**The count.** This plan plants 144 bugs: `(q28 project)` 17, `(q28 staging)` 8, `(q28 sync)` 7, `(q28 basket)` 11, `(q28 deals)` 33, `(q28 reach)` 7, `(q28 golden)` 3, `(q28 checks prices)` 7, `(q28 checks promotions)` 11, `(q28 checks items)` 21, `(q28 checks across)` 3, `(q28 checks published)` 12, `(q28 lineage)` 4, and one older planted bug re-pointed. The weekly run's added time is an estimate, about 45 to 60 minutes (UNVERIFIED until Task 12 measures it).

**The sync ahead of the rest.** Task 13 syncs real days with the new sync lines. The plan's route: once Task 3 has passed its review, **on the owner's go**, main fast-forwards to `q28-sync` (the design, this plan and the sync change) and is pushed, so the main checkout's `scripts/sync.sh` has the new lines; `q28-dbt-layer` is then rebased onto main (never pushed until Shipping, so the rebase rewrites nothing public). The other route, if the owner declines: Task 13 copies the branch's script beside the main checkout's own (`cp scripts/sync.sh ../il-grocery-prices/scripts/sync-q28.sh`), runs it there, and removes the copy after.

## Global Constraints

- **The grade** above binds every task: test-first; a planted bug for every rule; a fresh review per task and of the whole branch before anything ships; pins exact and each package first uploaded at least a month before the day it is pinned; docs in plain words.
- **The versions:** dbt-core 1.12.6, dbt-duckdb 1.11.0, duckdb 1.5.6, Python 3.13; all 59 packages pinned exactly in `requirements-dbt.txt`, no hashes, no extras (not dbt-duckdb's `md` extra, which pins another DuckDB), no `dbt-oss` or `dbt` (v2) package. Task 1 resolves again on its day with pip's `--uploaded-prior-to` (pip 26.2.2, the version a new Python 3.13 venv on this Mac gets, has the option: checked 2026-11-25); a pin may move only to a version first uploaded at least a month before that day, and any move is reported for "Deviations" with its upload date. dbt-duckdb stays 1.11.0 and dbt-core 1.12.6 unless the owner says otherwise.
- **The one pin that fetches from GitHub** (the design's section 6; the owner's choice, 2026-11-25: kept and documented). `dbt-core-experimental-parser` 2.0.8, which dbt-core 1.12.6 requires, is a 4,776-byte source package on PyPI whose build downloads a compiled wheel of about 50 MB from dbt's GitHub release v2.0.8 (published 2026-10-14) and refuses it unless its SHA-256 matches the one in the package's `_dbt_sa_build/assets.json`. That download is outside `--uploaded-prior-to`: its age is the release's date, its bytes the fingerprint. Its build needs `packaging`, which pip would fetch unpinned for an isolated build even under `--no-deps`; so `packaging==26.3`, one of the 59, is installed first, and the 59 are built with `--no-build-isolation`. dbt runs that parser only under `--use-v2-parser`, which this project never passes.
- **The environment:** `.venv-dbt/`, made with `python3.13 -m venv .venv-dbt && .venv-dbt/bin/pip install --no-deps packaging==26.3 && .venv-dbt/bin/pip install --no-deps --no-build-isolation -r requirements-dbt.txt && .venv-dbt/bin/pip check` (call 2), the same in CI and in `docs/operations.md` (a test holds them equal). Each fresh install fetches that one wheel from GitHub. Nothing is installed into the project's `.venv`. dbt's packages never enter `requirements-dev.txt`.
- **dbt, as run here:** always from inside `dbt/`; the database `data/dbt.duckdb`, `GROCERY_DBT_DB` overriding it (`profiles.yml`: `path: "{{ env_var('GROCERY_DBT_DB', '../data/dbt.duckdb') }}"`, `threads: 1`); the profile committed in `dbt/`; telemetry off by `flags: send_anonymous_usage_stats: false` in `dbt_project.yml`. dbt's own version flag is never run (in dbt-core 1.12.6 it asks PyPI for the newest version: the design's section 6); `pip show dbt-core` gives the version. On the Mac, `dbt run` then `dbt test` (call 3): in one `dbt build`, a failing error test skips the models downstream of what it reads, and `items_agree_with_their_reports` fails on the Mac today. No seeds, packages, snapshots, exposures, incremental models, Parquet outputs, dbt Cloud or schedule; no Python file under `dbt/` (a folder named `dbt` on Python's path joins the dbt package: trap 5).
- **The SQL:** no model, macro or test reads the clock; a model's day is always its table's day. No price goes through a floating-point type: in DuckDB 1.5.6 a DECIMAL divided by an integer is a DOUBLE (`typeof(1.50::decimal(13,3) / 2)` gives DOUBLE, checked 2026-11-25) while `(a + b) * 0.5` stays DECIMAL (DECIMAL(15,3), giving 7.605 for 7.60 and 7.61), so no `/` but `//` appears in any SQL file. `round` on a DECIMAL rounds half up (`round(4.995::decimal(13,3), 2)` is 5.00, DECIMAL(13,2); checked the same day), as the Python does. DuckDB lists are 1-based.
- **Unit tests:** every input `format: sql`; each test's `expect` lists every column a planted bug in its model can move, since dbt compares only the columns a dict-form `expect` lists.
- **Every dbt run in a test** uses its own temporary database, target folder, log folder and home folder (`tests/dbt_run.py`, Task 1), and never reuses a target folder across a change to the project: dbt's partial parse would read the old project, and a planted bug would go unseen. No test reads or writes `data/`, `site/`, `dbt/target/`, `dbt/logs/` or the home folder.
- **Test data never reads the clock:** fixed days, `gzip.compress(..., mtime=0)`. Fixtures and unit-test rows are synthetic: synthetic prices, names and barcodes (the golden's style: `2000000000121`), never a real row. The golden build's tables come from the golden's files through `shopper.extract.extract_chain_day`, never typed by hand.
- **A test of a script that calls AWS** (`scripts/sync.sh`) runs a copy of it in a temporary folder beside the stand-in `aws` of `tests/test_scripts.py`, from an empty environment: `HOME`, `PATH` set to the stand-ins' folder, `/usr/bin` and `/bin`, and the stand-ins' own variables (`AWS_CALLS`, `TMPDIR`, `FAKE_BUCKET`, `P_KEYS`, `GROCERY_AWS_ARN`, as `tests/test_scripts.py` sets them). The stand-ins' folder on `PATH` is the one addition the rule needs, since the script calls `aws` by name; `shutil.which("aws", path="/usr/bin:/bin")` is None, asserted. Never through a switch that falls back to the real script. Nothing in a test ever reaches AWS.
- **Commands.** `PY` is `../il-grocery-prices/.venv/bin/python`; the worktree has no `.venv` of its own, and pytest's `pythonpath` makes it test the worktree's code. Commands run from the worktree's root. The full suite: `$PY -m pytest -p no:cacheprovider --cov=collector --cov=src/basket --cov=src/shopper --cov-fail-under=95`, about 15 to 25 minutes: run it in the background, read its exit code (0: all passed) and its time from pytest's summary line. pytest already runs with `-q` (`pyproject.toml`): never add `-q`. Coverage stays at or above 95%; the dbt SQL is not Python, so its proof is the unit tests, the golden build and the planted bugs.
- **Planted bugs.** A named entry in `scripts/mutation_check.py` for every rule, added by the task that adds the rule: `((path, tests), old_text, new_text)`, the name saying what the break does, then the group in brackets, `(q28 <group>)`. Each break leaves the file parseable (YAML that loads, SQL that compiles): a test must fail on the rule, not on a parse error. A task runs its own groups, names given as literal quoted arguments (`$PY scripts/mutation_check.py "q28 deals"`) or from Python, never through a shell array or an unquoted variable (the shell is zsh, which never splits one), then the staleness check. Expected: every one CAUGHT, then `none stale`. Only pytest's exit 1 counts as caught. The check edits files in place: nothing else runs from that worktree meanwhile. The full check is CI's weekly run. An edit to a file that already carries planted bugs keeps each one's text found exactly once (`tests/test_mutation_targets.py`); a planted bug whose text moved is re-pointed with the same break and named in the commit message.
- **The staleness check** reads and edits nothing: `$PY -I -c "import importlib.util as u; s = u.spec_from_file_location('m', 'scripts/mutation_check.py'); m = u.module_from_spec(s); s.loader.exec_module(m); bad = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]; print(len(m.MUTATIONS), bad or 'none stale')"`.
- **After a merge or a rebase**, an edit both sides made can merge as one with no conflict: nothing about the merged branch is claimed until the full suite passes on it.
- **The owner's go**, asked right before each one and never assumed: every `git push`, every merge to main, the early ship of the sync. Read-only AWS calls (the sync, Task 3's look at a report) need no ask and run in the main session only, after the identity check of `docs/operations.md`'s "Deploy", step 1. Before any `gh` call or push, `gh auth status` shows the owner's account. Subagents never run `gh`, never push, never call AWS.
- **Public words.** This plan, the docs, the README, every model, column and test description: plain words, no "we", no em dash; every fact checked this session against a primary source or marked UNVERIFIED; no pointer to private notes, no account number, user name, email address, bucket name or local absolute path. No model's rows on any public page.
- **Models for subagents:** implementers and task reviews on the newest Opus (`opus`); the whole-branch review on Fable (`fable`), or on the newest Opus while Fable is at its usage limit, the report naming the swap; a task still open after fix round 3 escalates to Fable. A subagent's report is a claim, checked against its source before it is acted on. Subagents cannot write report files: briefs ask for the report in the reply.
- **Commits.** One commit per task (fix rounds add their own), each message naming q28. Before each, `git status`, and stage every file the message names and nothing else.

## Review Focus

1. **Days one source has and another lacks.** On the Mac the prices and promotions tables cover 12 days, the items tables 23, the published files their own days. Each model works on the days its sources hold, and each comparison checks only what both sides hold: a published chain-day with no table behind it is never reported as a difference. Tests: Task 10's day-29 basket file (the four chains with no prices table that day carry wrong figures on purpose and nothing fails); Task 4 `each_chain_and_day_on_its_own`.
2. **A half agora.** A median of 7.60 and 7.61, a listed price of 4.995: exact to three places, then rounded half up as the Python does, never through floating point. Tests: Task 4 `the_median_of_an_even_count_is_the_mean_of_the_middle_two_exactly` (7.605); Task 5 `the_day_price_is_the_listed_price_to_the_agora_half_up`; Task 10's Osher Ad median of 7.145 published "7.15"; Task 1 `test_no_model_reads_the_clock_or_a_floating_point_type`.
3. **A store type with nothing to check.** 77 of the 99 published store-type days are 0 of 0; a hole day and a promotion hole day. `store_type_deals` gives a row of zeros, never no row, and a hole's products are never judged. Tests: Task 5 `a_store_type_day_with_nothing_checked_is_0_of_0`, `no_row_without_a_promotion_counting_on_a_tracked_today`; Task 10's Shufersal Deal published 0 of 0.
4. **Leading zeros and internal codes.** A basket or published code written with a leading zero matches its product; a code that is no GS1 barcode is no product. Tests: Task 2 `each_chain_s_item_is_a_row_its_code_without_leading_zeros`; Task 4 `only_the_basket_s_codes_their_leading_zeros_stripped`; Task 6 `only_running_promotions_with_a_kind_on_listed_gs1_products_count`; Task 8's GS1 test.
5. **A run that reaches outside its folders.** A test touching the Mac's built database, `dbt/target/`, the home folder or `dbt/.user.yml`; telemetry on; anything asking dbt its version. Tests: Task 1 `test_a_dbt_run_writes_nothing_outside_its_temporary_folders`, `test_telemetry_is_off_as_dbt_reads_it`, `test_nothing_asks_dbt_its_version`.

---

## Questions for the owner

None blocks the build.

1. **The GS1 lengths** (the design's section 3: `basket.barcode.is_gs1` takes 8 to 14 digits, `docs/headline-basket.md`'s "Identity" says 8, 12, 13 or 14). Task 8 writes the GS1 test against `is_gs1`, the code the extraction runs, and its description says it waits on the owner's ruling. A ruling for the doc's lengths changes `is_gs1`, which is the extraction and out of this plan's scope; the test changes with it, in that change.
2. **The early ship of the sync** ("How this plan runs"): asked once Task 3 has passed its review.

## Where the design leaves room, this plan decides

The owner can overturn any of these.

1. **The known differences as a var.** The list lives in `dbt_project.yml` as `vars: known_differences:` (each entry `{kind, key, day, reason}`), rendered into rows by the SQL model `known_differences`, a reason's `'` doubled. The design writes it "as SQL" (section 2), but the bad-rows build must make "every known difference still differs" fail on golden days the real list cannot name; a var is replaced with `--vars` there. Still no seed file. *Alternative:* the list as SQL values, and the bad-rows build running on a copy of `dbt/` whose list it edits.
2. **The install** is `packaging==26.3` first, then `pip install --no-deps --no-build-isolation -r requirements-dbt.txt`, then `pip check`, here, in CI and in `docs/operations.md`: a plain install could pull a package the Mac's resolve did not list (a Linux-only requirement on CI's runner) unpinned, and an isolated build would fetch `packaging` unpinned for the parser's build. That the 59 install on CI's Linux runner with nothing missing is UNVERIFIED until CI's first run.
3. **The bad-rows build is `dbt run`, then `dbt test`,** not one `dbt build`: a failing source test stops the models built from it (section 3) and skips their tests, which then could not be seen to fail. The Mac's real runs take the same order, for the same reason (Task 13, `docs/operations.md`).
4. **The tests find dbt at `<checkout>/.venv-dbt/bin/dbt`** only; with none there they fail, saying how to make it. `.gitignore` gains `.venv-dbt` with no slash, as `.venv` has, so a link to another worktree's environment is ignored too.
5. **PyYAML 6.0.3 pinned in `requirements-dev.txt`.** `tests/test_dbt_project.py` reads YAML; the project's `.venv` holds PyYAML 6.0.3 today only through cfn-lint (checked 2026-11-25), the version `requirements-dbt.txt` pins too. Task 1 reads its upload date from PyPI.
6. **Every chain, every day** (the design's continuity warning) is checked for each chain from its own first day to the last day any chain has: the golden build holds Shufersal's last 29 days and one day of the other four (section 4), and a chain missing the latest day is still caught.
7. **Joins with a store type** go on chain, store type and day, so a row under a store type of another chain meets no report.
8. **The left-out filter** is two equality anti-joins, one on (chain, store) and one on (chain, sub-chain), never an `or` inside one join or a correlated `not exists`: the prototype's took 42 s against 6 s direct (section 3). A row with no sub-chain meets no left-out sub-chain, as B2 says.
9. **B5's median** is a macro, `median_price(prices)`, used by `basket_prices` and the across-table test: the middle price, or `(a + b) * 0.5` of the two middles, three places.
10. **The money vars are text:** `deal_min: "1.00"`, rendered `1.00` in SQL; `kinds` and `store_types` are vars too, each held equal to the Python by a test. The price floor, ₪0.01, has no Python constant and stays a literal, each use guarded by a test.
11. **Names.** Every data test has a name of its own (`name:` in YAML for a generic test, the file name for a singular one); tests read results by that name, from `run_results.json` and the manifest.
12. **Files.** One YAML a model, beside it (`<model>.yml`: description, columns, unit tests); singular tests under `dbt/tests/<group>/`, their descriptions in `dbt/tests/<group>/_<group>.yml` (that dbt 1.12 reads a singular test's description there is UNVERIFIED until Task 8's first parse; if it does not, the description is the file's first comment); folders `models/staging`, `models/lists`, `models/intermediate`, `models/marts`.
13. **The sync** brings each chain's folder of the named day under `tables/prices/` and `tables/promotions/` whole (each table and its `report.json`) but `texts.parquet`, so a table and its counts arrive together.
14. **CI** installs dbt in the test job: the dbt tests are part of pytest.
15. **The README's diagram** sits between two marker comments, made by `scripts/dbt_lineage.py` from dbt's manifest; each source drawn as a table with its `meta: {label: ...}` from `sources.yml` (the design's labels: "prices", "items", "promotions", "items reports", "published site-day files", "published basket day files", "the basket"). Only edges are drawn, so `known_differences`, which reads nothing and only tests read, stays out of it, as in the design's diagram.
16. **The TIME_LIMIT comment's count of target sets** (`scripts/mutation_check.py:46`, "The other 92 target sets": there are 95 today, counted 2026-11-25) is set right once, in Task 13, with the new sets' unmutated times, so no two branches edit that line.
17. **The promotions count against a store type with no reach row.** `promotion_reach` has a row only for a store-type day with a promotion on a listed product. The comparison reads a missing row as 0 when the chain has promotions rows that day (Shufersal Deal's published 0 on 30 April meets 0), and does not compare a store-type day whose chain has no promotions row that day (no promotions table).

## The models' columns

Every task's interfaces. Types are DuckDB's; prices stay DECIMAL throughout.

| Relation | Built as | One row per | Columns |
|---|---|---|---|
| `stg_prices` | view | price row | `chain`, `day` (DATE, the folder's), `store`, `sub_chain` (NULL when the file name has none), `code`, `barcode` (the table's `code_norm`), `gs1`, `price` (DECIMAL(12,2)), `file` |
| `stg_items` | view | items row | `chain`, `store_type` (the table's `column`), `day`, `barcode` (`code`), `listed` (DECIMAL(13,3)), `low`, `high` (DECIMAL(12,2)), `listing`, `wide`, `on_promotion`, `next_start`, `promotions` (the struct list as written) |
| `stg_promotions` | view | promotions row | `chain`, `store_type`, `day`, `promotion_id`, `group_id`, `code`, `barcode` (`code_norm`), `gs1`, `kind`, `reward_type`, `starts`, `ends`, `restrictions`, `min_spend`, `discounted_low`, `discounted_median`, `discounted_high`, `with_store_price`, `agrees_with_store`, `stores`, `promotion_stores`, `counted`, `wide` (names checked against `DESCRIBE` of a golden table in Task 2) |
| `stg_store_type_days` | view | store type and day | `chain`, `store_type`, `day` (the folder's, never the report's own `day` field), `hole`, `promo_hole`, `included`, `with_file`, `counted`, `promo_files`, `items`, `wide`, `on_promotion`, `valid_deals`, `promotions_error` |
| `stg_published_store_pages` | view | store type and day with a front block | `store_type`, `day`, `deals`, `checked`, `promotions`, `products`, `shown_rows` (list of `barcode`, `today`, `usual`, `saving`, `days`, as published) |
| `stg_published_basket` | view | chain, day and published item | `chain`, `day`, `barcode` (the published code, leading zeros stripped), `median`, `low`, `high` (VARCHAR, as published), `listing`, `double_coded` |
| `left_out_stores` | view | store or sub-chain left out by number | `chain`, `kind` (`sub_chain` or `store`), `key` |
| `known_differences` | view | listed published day | `kind` (`store_page` or `basket`), `key` (a store type or a chain), `day`, `reason` |
| `int_counted_prices` | view | price row that counts (B2 by number, B4) | `stg_prices`' columns |
| `int_day_prices` | table | store type, product and day listed | `chain`, `store_type`, `barcode`, `day`, `wide`, `listed_shown` (DECIMAL(13,2)), `sale_price` (the lowest promotion counting, S3), `on_sale`, `hole`, `promo_hole`, `tracked`, `day_price` (S1) |
| `product_deals` | table | store type, product and day on which a promotion counts | `store_type`, `barcode`, `day`, `today_price`, `usual_price`, `saving`, `days_tracked`, `days_priced`, `days_on_sale`, `days_unknown`, `days_recorded` (days with records in the 30 before), `checked`, `verdict` (`deal`, `no deal` or `no verdict`) |
| `store_type_deals` | table | store type and day | `store_type`, `day`, `checked` (M), `deals` (N), `on_sale_every_tracked_day`, `on_sale_more_than_half` |
| `promotion_reach` | table | store type and day with a promotion on a listed product | `store_type`, `day`, `promotions`, `at_most_branches`, `at_some_branches`, `restricted`, `with_min_spend` |
| `basket_prices` | table | chain, day and basket barcode | `chain`, `day`, `barcode`, `median` (DECIMAL, three places), `low`, `high`, `stores_listing`, `double_coded` |

## Files

| File | Task | What it holds |
|---|---|---|
| `requirements-dbt.txt`, `requirements-dev.txt` (PyYAML), `.gitignore` | 1 | the 59 pins and the note on the one GitHub download; the test's YAML reader; `.venv-dbt`, `dbt/target/`, `dbt/logs/` ignored |
| `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/models/sources.yml` | 1 (vars and source tests added in 2, 8, 9) | the project, its vars and flags; the profile; the seven sources |
| `dbt/models/staging/`, `dbt/models/lists/` | 2 | the six staging views, the two lists, each with its YAML |
| `dbt/models/intermediate/int_counted_prices.*`, `dbt/models/marts/basket_prices.*`, `dbt/macros/median_price.sql` | 4 | B2 and B4; B5 for the basket |
| `dbt/models/intermediate/int_day_prices.*`, `dbt/models/marts/product_deals.*`, `dbt/models/marts/store_type_deals.*` | 5 | S0 to S4, P1, the bar |
| `dbt/models/marts/promotion_reach.*` | 6 | P3, P5 |
| `dbt/macros/unique_together.sql`, `dbt/macros/is_gs1.sql`, `dbt/tests/{prices,promotions,items,across,published}/` | 8 to 10 | the data tests |
| `tests/dbt_run.py`, `tests/test_dbt_project.py`, `tests/test_dbt_units.py`, `tests/test_dbt_golden.py`, `tests/test_dbt_lineage.py` | 1, 1, 1, 7, 11 | the runner; the four test files of the design's section 4 |
| `scripts/sync.sh`, `tests/test_scripts.py` | 3 | the named day's prices and promotions tables; the items tables' times |
| `scripts/dbt_lineage.py` | 11 | the README's diagram from the manifest |
| `.github/workflows/ci.yml`, `.github/workflows/mutations.yml` | 1 (12: the run's time) | the two install lines and their comment |
| `scripts/mutation_check.py` | every task | the planted bugs |
| `README.md`, `docs/operations.md`, `docs/README.md`, `docs/dbt-layer.md` | 11, 12, 13 | the section and diagram; "Develop", "The dbt layer, on the Mac", the sync's step; the index; the design's status |

---

### Task 1: The environment, the pins and the project's frame

Wave 1, beside Task 3. Implementer: Opus.

**Files:**
- Create: `requirements-dbt.txt`, `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/models/sources.yml`, `tests/dbt_run.py`, `tests/test_dbt_project.py`, `tests/test_dbt_units.py`
- Modify: `requirements-dev.txt` (`PyYAML==6.0.3`), `.gitignore`, `.github/workflows/ci.yml`, `.github/workflows/mutations.yml`, `scripts/mutation_check.py` (targets, anchors, `(q28 project)`)

**Interfaces:**
- Produces, in `dbt/dbt_project.yml`: `name: grocery`, `profile: grocery`, `model-paths: ["models"]`, `test-paths: ["tests"]`, `macro-paths: ["macros"]`, no `seed-paths`; `flags: {send_anonymous_usage_stats: false}`; `models: grocery: {staging: {+materialized: view}, lists: {+materialized: view}, intermediate: {+materialized: view}, marts: {+materialized: table}}`; vars `tables: ../data/tables`, `site: ../site`, `basket_file: ../src/basket/baskets/v1.json`, `deal_min: "1.00"`, `min_front_days: 20`, `recent_days: 30`, `read_days: 90`, `kinds: {"1": n_for_m, "10": n_for_m, "2": percent_off, "3": fixed_price}`, `store_types: {carrefour-city: carrefour, carrefour-market: carrefour, osherad: osherad, ramilevy: ramilevy, shufersal-deal: shufersal, shufersal-express: shufersal, shufersal-sheli: shufersal, shufersal-universe: shufersal, yochananof: yochananof}`.
- Produces, in `dbt/models/sources.yml`: `source('tables', 'prices' | 'items' | 'promotions' | 'items_reports')`, `source('published', 'site_days' | 'basket_days')`, `source('repo', 'basket')`, each with `config: external_location:` naming its var (`read_parquet('{{ var("tables") }}/prices/*/*/prices.parquet', hive_partitioning = true)` and the like, as the design's prototype has them); the four `read_json` sources, `items_reports`, `site_days`, `basket_days` and `basket`, each with `formatter: oldstyle` (trap 2); the reports' `columns` naming only `columns` (the map of each store type's counts and flags) and `promotions_error`, never `outside`; each table a `meta: {label: ...}` (call 15).
- Produces, in `tests/dbt_run.py`:

```python
ROOT: Path; PROJECT = ROOT / "dbt"; DBT = ROOT / ".venv-dbt" / "bin" / "dbt"

@dataclass(frozen=True)
class DbtRun:
    code: int                                    # dbt's exit code
    output: str                                  # its stdout and stderr
    results: dict[str, tuple[str, int | None]]   # each node's name -> (status, failures), from run_results.json
    manifest: dict                               # target/manifest.json
    database: Path

def run_dbt(command: Sequence[str], work: Path, vars: Mapping[str, object] | None = None,
            database: Path | None = None) -> DbtRun
    # cwd PROJECT; --target-path work/target, --log-path work/logs; --vars as JSON when given;
    # env: the test's own less every DBT_ variable and GROCERY_DBT_DB, plus HOME=work/home (made empty) and
    # GROCERY_DBT_DB=database or work/dbt.duckdb. Fails with "make .venv-dbt: docs/operations.md, Develop" when DBT
    # is missing. `work` is a fresh folder every call.
def query(database: Path, sql: str) -> list[tuple]   # read-only DuckDB, the project's 1.5.6
```

- [ ] **Step 1: Resolve the pins and read the one GitHub download.** In a scratch venv outside the repository: `python3.13 -m venv <scratch>/resolve && <scratch>/resolve/bin/pip install --uploaded-prior-to=<today minus one month, ISO> dbt-core==1.12.6 dbt-duckdb==1.11.0 duckdb==1.5.6 && <scratch>/resolve/bin/pip freeze`. Compare with the design's 59 (the design's prototype's list). Expected: the same 59; a difference is reported for "Deviations" with each version's upload date. Then a second scratch venv with the install of Global Constraints ("The environment"). Expected: pip downloads nothing from PyPI but the 59, the parser's build fetches its one wheel from GitHub and accepts it, and `pip check` says "No broken requirements found." Read and report for "Deviations": the GitHub release v2.0.8's published date from its release page (expected 2026-10-14, at least a month before today), the PyPI SHA-256 of the source package `dbt-core-experimental-parser` 2.0.8 (4,776 bytes), the wheel's SHA-256 in that package's `_dbt_sa_build/assets.json`, and PyYAML 6.0.3's upload date on PyPI.
- [ ] **Step 2: Write the failing tests.** `tests/test_dbt_project.py` (no dbt; YAML through `yaml.safe_load`):
  - `test_every_dbt_requirement_is_an_exact_pin`: every line not blank and not a comment matches `[A-Za-z0-9][A-Za-z0-9._-]*==[0-9][0-9A-Za-z.]*`; names unique case- and `-_.`-blind; 59 of them.
  - `test_dbt_core_1_12_and_its_adapter_1_11`: `dbt-core==1.12.6`, `dbt-duckdb==1.11.0`, `dbt-core-experimental-parser==2.0.8` (the one pin whose build fetches from GitHub, as documented), `packaging==26.3`; no `dbt-oss`, no `dbt`.
  - `test_both_environments_run_the_same_duckdb`: `duckdb` is `1.5.6` in both files, and every package both files pin has one version.
  - `test_every_install_of_the_dbt_environment_is_the_same`: the install in `.github/workflows/ci.yml` and `.github/workflows/mutations.yml` is the same three commands: `pip install --no-deps packaging==<requirements-dbt.txt's version>`, then `pip install --no-deps --no-build-isolation -r requirements-dbt.txt`, then `pip check` (Task 11 adds `docs/operations.md`).
  - `test_telemetry_is_off`: `project["flags"] == {"send_anonymous_usage_stats": False}`.
  - `test_the_profile_is_one_local_file_and_one_thread`: the profile equals `{"grocery": {"target": "mac", "outputs": {"mac": {"type": "duckdb", "path": "{{ env_var('GROCERY_DBT_DB', '../data/dbt.duckdb') }}", "threads": 1}}}}`.
  - `test_the_rule_constants_are_the_python_s`: `deal_min == "1.00"` and `Decimal(deal_min) == shopper.verdict.DEAL_MIN`; `min_front_days == MIN_FRONT_DAYS == 20`; `recent_days == RECENT_DAYS == 30`; `read_days == READ_DAYS == 90`; `kinds == shopper.promotions.KINDS`.
  - `test_the_store_types_are_the_nine`: `store_types == {c.key: c.slug for c in shopper.columns.COLUMNS}`.
  - `test_the_sources_read_their_files_in_place_and_never_a_store_number`: the seven tables, by source and name; each `external_location` a `read_parquet(` or `read_json(` naming `var("tables")`, `var("site")` or `var("basket_file")`; each of the four `read_json` tables has `formatter: oldstyle`; the reports' column list names `columns` and `promotions_error` alone.
  - `test_no_seed_no_package_and_no_python_in_dbt`: no `seed-paths` and no `dbt/seeds/`; no `dbt/packages.yml` or `dbt/dependencies.yml`; no `*.py` under `dbt/`; no `dbt/.user.yml`.
  - `test_no_model_reads_the_clock_or_a_floating_point_type`: over every `.sql` under the folders `dbt_project.yml` names (`model-paths`, `macro-paths`, `test-paths`), never `dbt/target/` (a plain `dbt build` writes compiled SQL there with the sources' paths inlined), and found on disk, not through `git ls-files` (which misses a new file not yet committed); `--` comments left out: none of `current_date`, `current_timestamp`, `current_time`, `localtimestamp`, `now(`, `today(`, `run_started_at`, `modules.datetime` (case blind); no word `double`, `float`, `float4`, `float8` or `real`; no `/` outside `//`.
  - `test_dbt_s_environment_and_output_are_ignored`: `git check-ignore -q` passes for `.venv-dbt`, `dbt/target/x`, `dbt/logs/x`, `data/dbt.duckdb`.
  - `test_nothing_asks_dbt_its_version`: no `dbt --version` in `tests/`, `scripts/`, `.github/`, `README.md` or `docs/operations.md` (this test file's own pattern built from parts).

  `tests/test_dbt_units.py`, a module fixture `units` running `run_dbt(["test", "--select", "test_type:unit"], tmp)` (no unit test yet: dbt exits 0), after recording the mtimes of `data/dbt.duckdb`, `dbt/target/` and `dbt/logs/` where they exist:
  - `test_telemetry_is_off_as_dbt_reads_it`: `units.manifest["metadata"]["send_anonymous_usage_stats"] is False`.
  - `test_a_dbt_run_writes_nothing_outside_its_temporary_folders`: the run's home folder is empty; no `dbt/.user.yml`; each recorded mtime unchanged; `manifest.json` is in the run's own target folder.
- [ ] **Step 3: Run** `$PY -m pytest -p no:cacheprovider tests/test_dbt_project.py tests/test_dbt_units.py`. Expected: exit 1 or 2 (no files; no `.venv-dbt`).
- [ ] **Step 4: Implement:** the files above; `.gitignore` gains `.venv-dbt`, `dbt/target/`, `dbt/logs/` under a comment naming the design; `requirements-dbt.txt` opens with comments saying what it is, the resolve's command and both dates, and that `dbt-core-experimental-parser`'s build fetches its wheel from dbt's GitHub release v2.0.8 (published 2026-10-14), checked against the SHA-256 the package carries (Step 1's figures); make `.venv-dbt` in the worktree as Global Constraints say. CI: in both workflows, before the pytest line, `- run: python -m venv .venv-dbt` and `- run: .venv-dbt/bin/pip install --no-deps packaging==26.3 && .venv-dbt/bin/pip install --no-deps --no-build-isolation -r requirements-dbt.txt && .venv-dbt/bin/pip check`, under a comment: "dbt is for the dbt layer's tests only, in an environment of its own (docs/dbt-layer.md, section 6). Each fresh install fetches one wheel from GitHub: dbt-core-experimental-parser's, from dbt's release v2.0.8, checked against the SHA-256 the package carries; packaging goes in first so the build needs nothing unpinned."
- [ ] **Step 5: Run** the two files, then the full suite. Expected: exit 0.
- [ ] **Step 6: Planted bugs.** Targets after the existing `SYNC_SCRIPT` line, under a comment "the dbt layer (q28)": `REQUIREMENTS_DBT = ("requirements-dbt.txt", ["tests/test_dbt_project.py"])`, `DBT_PROJECT = ("dbt/dbt_project.yml", ["tests/test_dbt_project.py"])`, `DBT_PROFILE = ("dbt/profiles.yml", ["tests/test_dbt_project.py"])`, `DBT_SOURCES = ("dbt/models/sources.yml", ["tests/test_dbt_project.py"])`, `GITIGNORE_FOR_DBT = (".gitignore", ["tests/test_dbt_project.py"])`, `CI_FOR_DBT = (".github/workflows/ci.yml", ["tests/test_dbt_project.py"])`, then one anchor comment line for each of Tasks 2 and 4 to 11's targets. At the end of `MUTATIONS`, an anchor comment line for each of Tasks 1, 2 and 4 to 11. Group `(q28 project)`, 17: "dbt-core pinned loosely", "dbt's DuckDB not the project's", "dbt-duckdb with its md extra", "telemetry on in dbt", "a deal from 99 agorot in dbt", "the front list's bar at 19 days in dbt", "the bar's window 31 days in dbt", "the history 91 days in dbt", "a kind of promotion renamed in dbt", "a store type under another chain in dbt", "dbt threads at 2", "the dbt database at a fixed path", "the reports' store numbers read", "a JSON source without the old-style formatter" (its text from the source's `- name:` line through its `formatter: oldstyle` line, so it is found once), "a seed folder named", "dbt's output not ignored", "CI's dbt install with build isolation". Run `$PY scripts/mutation_check.py "q28 project"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add requirements-dbt.txt requirements-dev.txt .gitignore dbt tests/dbt_run.py tests/test_dbt_project.py tests/test_dbt_units.py .github/workflows/ci.yml .github/workflows/mutations.yml scripts/mutation_check.py && git commit -m "The dbt layer's frame (q28): .venv-dbt from 59 exact pins (the parser's wheel fetched from dbt's GitHub release, checked by its SHA-256), the project with telemetry off and its rule constants held to the Python's, the seven sources, a runner that keeps every dbt run in temporary folders, CI's install"`

### Task 2: The staging views and the two lists

Wave 2. Implementer: Opus.

**Files:**
- Create: `dbt/models/staging/stg_{prices,items,promotions,store_type_days,published_store_pages,published_basket}.{sql,yml}`, `dbt/models/lists/{left_out_stores,known_differences}.{sql,yml}`
- Modify: `dbt/dbt_project.yml` (the var `known_differences`), `tests/test_dbt_project.py`, `tests/test_dbt_units.py`, `scripts/mutation_check.py` (`(q28 staging)`)

**Interfaces:**
- Consumes: Task 1's sources and vars, `tests/dbt_run.py`.
- Produces: the eight relations of "The models' columns". `left_out_stores.sql` holds one row a line, `('<chain>', '<sub_chain|store>', '<key>')`: `('shufersal', 'sub_chain', '5')`, `('shufersal', 'store', '413')`, `('ramilevy', 'store', '39')`, `('carrefour', 'store', '471')`. The var `known_differences` holds the owner's four (the design's answer 2), reasons in plain words: `{kind: store_page, key: ramilevy, day: "2026-11-21"}`, `{kind: store_page, key: ramilevy, day: "2026-11-22"}`, `{kind: store_page, key: yochananof, day: "2026-11-22"}` (each "published before the 22 November fix to weighed N for ₪M prices; that chain's items tables of 1 to 22 November were written again after it"), `{kind: basket, key: shufersal, day: "2026-11-09"}` ("published from 171 Shufersal stores' files, the slow morning's; that day's prices table was rebuilt later from 416").

- [ ] **Step 1: Write the failing tests.** Unit tests, each input `format: sql`:
  - `stg_store_type_days` `a_report_gives_a_row_per_store_type`: a Carrefour report in the folder of 2026-01-01 (its own `day` field "2025-12-31", which is not read) with `carrefour-city` {hole false, promo_hole true, included 75, with_file 74, counted 74, promo_files 30, items 3, wide 2, on_promotion 1, valid_deals 1} and `carrefour-market` {hole true, promo_hole true, included 44, with_file 10, counted 10, promo_files 0, items 1, wide 0, on_promotion 0, valid_deals 0}: two rows with exactly those values, chain `carrefour`, day 2026-01-01.
  - `stg_published_store_pages` `a_front_block_is_a_row_and_a_store_type_without_one_none`: a site-day file of 2026-04-30 with `shufersal-universe`'s front {deals 4, checked 6, promotions 9, products 9, rows [{barcode "2000000000145", today "6.90", usual "8.90", saving "2.00", days 27}]} and `osherad` with no front: one row, those values.
  - `stg_published_basket` `each_chain_s_item_is_a_row_its_code_without_leading_zeros`: a day file of 2026-04-30, `osherad` {total "14.70", items {"02000000000121": {median "7.20", low "7.10", high "7.30", listing 2, double_coded 0}}}: one row, barcode `2000000000121`, the figures as published.
  - `known_differences` `each_known_difference_is_a_row_its_reason_kept_whole` (`overrides: vars: known_differences: [{kind: basket, key: osherad, day: "2026-04-30", reason: "Osher Ad's day, written again"}]`): that one row, its reason with its apostrophe; `an_empty_list_is_no_row` (the var `[]`): no row. If dbt 1.12 refuses a unit test with no input (`given: []`), these two move into Task 7's golden build, reported for "Deviations".
  - `tests/test_dbt_project.py`: `test_the_left_out_stores_are_b2_s` (the rows read from `left_out_stores.sql` by the line pattern above equal `{(slug, "sub_chain", key) ...} | {(slug, "store", key) ...}` over `basket.chains.EXCLUDED`); `test_the_known_differences_are_the_owner_s_four` (exactly the four `(kind, key, day)` above, each `kind` in `store_page`, `basket`, each `key` a store type of `store_types` or a chain of `basket.chains.SLUGS` as its kind asks, each reason at least 30 characters); `test_every_model_and_column_is_described` (every `.sql` under `dbt/models` has its `<model>.yml` with a description; every column listed there has one; no description holds the word "we").
  - `tests/test_dbt_units.py`: `test_every_unit_test_passes` (`units.code == 0`, every unit test's status `pass`); `test_every_declared_unit_test_ran` (the manifest's `unit_tests` names equal the results' unit-test names, at least one); `test_every_model_with_a_rule_has_a_unit_test` (each model under `models/intermediate/` and `models/marts/`, and `stg_store_type_days`, `stg_published_store_pages`, `stg_published_basket` and `known_differences`, is the `model` of at least one unit test; the models of Tasks 4 to 6 join the list as they come, since the rule reads the folders).
- [ ] **Step 2: Run** the two test files. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Staging views select and rename only, but for three reshapes: the reports' map and the published files' maps unnested to rows, and the published code's leading zeros stripped (`ltrim(code, '0')`), as every barcode match in the project strips them. Every day is the folder's (hive `date`), never a file's own `day` field. Check `stg_promotions`' column names against `DESCRIBE` of a promotions table the golden writes (`shopper.extract.extract_chain_day` over `tests/shopper_golden.py`'s files of one day, in a scratch folder).
- [ ] **Step 4: Run** the two files, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 2's anchors. Targets: `DBT_LEFT_OUT = ("dbt/models/lists/left_out_stores.sql", ["tests/test_dbt_project.py"])`, `DBT_KNOWN = ("dbt/models/lists/known_differences.sql", ["tests/test_dbt_units.py"])`, `DBT_KNOWN_LIST = DBT_PROJECT`, `DBT_STG_STORE_TYPE_DAYS`, `DBT_STG_PUBLISHED_STORE_PAGES`, `DBT_STG_PUBLISHED_BASKET` (each its `.sql` with `["tests/test_dbt_units.py"]`). Group `(q28 staging)`, 8: "Shufersal's online store kept in dbt", "Be left out as a store in dbt", "a known difference dropped", "a reason's apostrophe not doubled", "the hole read as the promotion hole", "the stores with a file read as the stores included", "a store type without a front block given a row", "a published code's leading zeros kept". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt tests/test_dbt_project.py tests/test_dbt_units.py scripts/mutation_check.py && git commit -m "The dbt layer's staging views and lists (q28): six views over the seven sources, the stores B2 leaves out by number held to basket.chains, the owner's four known differences with their reasons"`

### Task 3: The sync: the named day's prices and promotions tables, and the items tables' times

Wave 1, beside Task 1; on a branch `q28-sync` from `q28-dbt-layer`'s head. Implementer: Opus.

**Files:**
- Modify: `scripts/sync.sh`, `tests/test_scripts.py`, `scripts/mutation_check.py` (`(q28 sync)`, after the `(q42 archive)` lines)

**Interfaces:**
- Consumes: `basket.extract.table_path`, `shopper.promos.promotions_path`, `shopper.items.items_path`, `shopper.items.texts_path`, the file's `FAKE_AWS`, `FAKE_PYTHON`, `_copy`, `_syncs`, `_filters`, `_brought`, `ARCHIVE`, `ARN`, `PROFILE`, `DAY`.
- Produces: two new lines in `sync.sh` after the scores line, each `aws s3 sync "s3://$BUCKET/tables/<prices|promotions>/" data/tables/<prices|promotions>/ --exclude '*' --include "chain=*/date=$day/*" [--exclude "chain=*/date=$day/texts.parquet"] --exact-timestamps --profile "$PROFILE" --region "$REGION"`; the items line gains `--exact-timestamps`. In `tests/test_scripts.py`: `_stand_ins(tmp_path) -> Path` (the stand-ins' folder, factored out of `_run`, which calls it) and `_sync_alone(tmp_path, day, **env) -> list[list[str]]` (Global Constraints, "A test of a script that calls AWS").

- [ ] **Step 1 (the main session, read-only AWS, after the identity check): confirm the cause** (the design's section 3, "The three that fail today", 1). List, read-only on the main checkout's `data/tables/items/`, the store-type days whose table and report disagree on valid deals; take one (Osher Ad's of an early November day, say). `aws s3api head-object` on that report's key in the archive bucket (the collector stack's output `ArchiveBucketName`) and `aws s3 cp "s3://<archive bucket>/tables/items/chain=<slug>/date=<day>/report.json" - --profile flights-sam --region il-central-1`. Expected: the archive's report gives the table's own count; the local report has the same size and a modification time no newer than the object's (the case the default sync skips). Report what was seen for "Deviations". A different finding stops the items line's change (the two table lines go on) and goes to the owner.
- [ ] **Step 2: Write the failing tests** in `tests/test_scripts.py`. `_sync_alone` runs `_copy(tmp_path, "sync.sh", None)` with `sh` and the environment `{"HOME": <the test's HOME>, "PATH": f"{_stand_ins(tmp_path)}:/usr/bin:/bin", "AWS_CALLS": ..., "TMPDIR": str(tmp_path), "FAKE_BUCKET": str(tmp_path / "published"), "P_KEYS": "None\n", "GROCERY_AWS_ARN": ARN} | env` and nothing else, asserts `shutil.which("aws", path="/usr/bin:/bin") is None` and exit 0, and returns the calls:
  - `test_sync_sh_brings_the_named_day_s_prices_and_promotions_tables`, over the keys `table_path(Path("tables"), "osherad", DAY)`, its `report.json`, `promotions_path(Path("tables"), "osherad", DAY)` and its `report.json`: exactly one call brings each (`_brought(..., ARCHIVE, "data", key)`), with `--exact-timestamps`, ending `PROFILE`.
  - `test_sync_sh_leaves_out_the_promotion_texts_and_other_days_tables`: `texts_path(Path("tables"), "osherad", DAY)` is brought by no call; nor the prices or promotions table of 2026-11-06.
  - `test_sync_sh_keeps_s3s_time_on_the_items_tables`: the call that brings `items_path(Path("tables"), "osherad", DAY)` and its report carries `--exact-timestamps`.
  - `test_sync_sh_reads_the_archive_bucket_from_the_collector_stack` (`tests/test_scripts.py:227-235`) moves onto `_sync_alone`, its `len(archive) == 7` becoming 9.
- [ ] **Step 3: Run** `$PY -m pytest -p no:cacheprovider tests/test_scripts.py`. Expected: the new tests and the moved one fail; every other passes.
- [ ] **Step 4: Implement** the lines, with a comment above them (what the dbt layer reads, why the texts are left out, why `--exact-timestamps`) and one on the items line (a report rewritten with a count of the same width keeps its size and is skipped without it); the script's opening comment names the two tables.
- [ ] **Step 5: Run** `tests/test_scripts.py`, then the full suite. Expected: exit 0.
- [ ] **Step 6: Planted bugs,** target `SYNC_SCRIPT`, group `(q28 sync)`, 7: "the named day's prices tables not synced", "the named day's promotions tables not synced", "every day's prices tables synced", "the promotion texts synced", "the prices tables' times not kept", "the promotions tables' times not kept", "the items tables' times not kept". Re-point "the items tables not synced (q22 publish)" (`scripts/mutation_check.py:2500`) to the items line's new text, the same break. Run `$PY scripts/mutation_check.py "q28 sync" "the items tables not synced"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add scripts/sync.sh tests/test_scripts.py scripts/mutation_check.py && git commit -m "Sync (q28): the named day's prices and promotions tables but the promotion texts, with S3's times; the items tables with S3's times, so a rewritten report of the same size comes down again"`, the body naming the re-pointed planted bug and Step 1's finding.

### Task 4: The basket's models: the rows that count and the basket's prices

Wave 3, beside Tasks 5 and 6. Implementer: Opus.

**Files:**
- Create: `dbt/models/intermediate/int_counted_prices.{sql,yml}`, `dbt/models/marts/basket_prices.{sql,yml}`, `dbt/macros/median_price.sql`
- Modify: `scripts/mutation_check.py` (`(q28 basket)`)

**Interfaces:**
- Consumes: `stg_prices`, `left_out_stores`, `source('repo', 'basket')` (its `items`, a list of structs with `code`).
- Produces: `int_counted_prices` and `basket_prices` ("The models' columns"); `{% macro median_price(prices) %}` over a sorted list of DECIMAL prices: the middle one, or `(a + b) * 0.5` of the two middles, as DECIMAL with three places.

- [ ] **Step 1: Write the failing unit tests** (YAML beside each model; days 2026-04-30 unless said; barcodes synthetic; each `expect` lists every column of the model):
  - `int_counted_prices` `left_out_by_number_at_their_own_chain_only`: rows at Shufersal store 300 sub-chain 5, Shufersal 413 sub-chain 1, Rami Levy 39, Carrefour 471 are left out; Shufersal store 39 sub-chain 1, Rami Levy store 413, and Shufersal store 301 with no sub-chain count; `left_out_stores` given its four rows.
  - `int_counted_prices` `a_price_of_one_agora_or_less_does_not_count`: prices 0.00, 0.01 and NULL left out; 0.02 counts.
  - `basket_prices` `the_median_of_an_odd_count_is_the_middle_store_s`: Shufersal's stores 11, 12, 21, 22 and 61 at 8.00, 8.20, 7.00, 7.20 and 7.60 give median 7.600, low 7.00, high 8.20, stores_listing 5, double_coded 0 (the golden's G6).
  - `basket_prices` `the_median_of_an_even_count_is_the_mean_of_the_middle_two_exactly`: 7.40 and 7.60 give 7.500; 7.60 and 7.61 give 7.605.
  - `basket_prices` `a_double_coded_store_counts_once_at_its_lower_price`: store 1 listing `2000000000121` at 5.00 and `02000000000121` at 4.80 (one barcode), store 2 at 5.20: stores_listing 2, double_coded 1, low 4.80, high 5.20, median 5.000.
  - `basket_prices` `only_the_basket_s_codes_their_leading_zeros_stripped`: the basket names `02000000000121`; rows of `2000000000121` and `2000000000077`: rows for `2000000000121` only.
  - `basket_prices` `each_chain_and_day_on_its_own`: one barcode at two chains on two days: four rows, each its own median.
- [ ] **Step 2: Run** `$PY -m pytest -p no:cacheprovider tests/test_dbt_units.py tests/test_dbt_project.py`. Expected: fail (no models).
- [ ] **Step 3: Implement** as calls 8 and 9 say; `int_counted_prices` a view.
- [ ] **Step 4: Run** the two files, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 4's anchors. Targets `DBT_COUNTED_PRICES`, `DBT_BASKET_PRICES`, `DBT_MEDIAN` (each its file with `["tests/test_dbt_units.py"]`), and `DBT_MEDIAN_FOR_PROJECT = ("dbt/macros/median_price.sql", ["tests/test_dbt_project.py"])`. Group `(q28 basket)`, 11: "a left-out store kept", "a left-out sub-chain kept", "a store left out at another chain", "a row with no sub-chain left out", "a price of one agora counted", "the lower of the two middles taken", "the median through a division" (`* 0.5` to `/ 2`, caught by the project test), "a store counted once a code", "a double-coded store's higher price taken", "a double-coded store not counted", "a basket code's leading zeros kept". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt scripts/mutation_check.py && git commit -m "The dbt layer's basket (q28): the price rows that count (B2 by number, B4) and each chain's median, lowest, highest and stores for the basket's products (B5), exact to three places"`

### Task 5: The deals' models: day prices, product deals and store-type deals

Wave 3, beside Tasks 4 and 6. Implementer: Opus.

**Files:**
- Create: `dbt/models/intermediate/int_day_prices.{sql,yml}`, `dbt/models/marts/product_deals.{sql,yml}`, `dbt/models/marts/store_type_deals.{sql,yml}`
- Modify: `scripts/mutation_check.py` (`(q28 deals)`)

**Interfaces:**
- Consumes: `stg_items`, `stg_store_type_days`; vars `deal_min`, `min_front_days`, `recent_days`, `read_days`.
- Produces: `int_day_prices` (`{{ config(materialized='table') }}`), `product_deals`, `store_type_deals` ("The models' columns").

The rules, from `src/shopper/verdict.py`'s docstring and `history.counted`, written in each model's YAML description:
- **S3's filter:** a promotion counts on a day when its struct is `wide`, `valid`, has a `kind` and `start <= day <= end`. `sale_price` is the lowest `price` among those; `on_sale` is `coalesce(on_promotion, false)`.
- **S1:** `listed_shown` is `round(listed, 2)`; `day_price` is the lower of `listed_shown` and `sale_price`, NULL on a sale day of unknown price (`on_sale` and no promotion counting), else `listed_shown`. **S0:** `tracked` is `not hole and not promo_hole`.
- **The history** of a row on day d: the same store type's and product's rows on days d - `read_days` to d - 1 (today excluded). `days_tracked` the tracked ones; `days_priced` those with a day price; `days_unknown` the tracked without one; `days_on_sale` the tracked on sale, unknown prices included (S7); `days_recorded` the days d - `recent_days` to d - 1 with no `hole` (a promotion hole is a record).
- **A row** for a store type, product and day only when that day is tracked, `sale_price` is not NULL, and the product is covered by that day (P1: wide at some store type, on a day with no hole, on or before it). `today_price` is `sale_price`. **S2:** `usual_price` is element `len // 2 + 1` (1-based) of the sorted day prices: the middle, the higher middle of an even count. `saving` is `usual_price - today_price`. `checked` is `days_recorded >= min_front_days`.
- **S4:** `no verdict` when `days_priced = 0` or `2 * days_unknown > days_tracked`; else `deal` when `saving >= deal_min`; else `no deal`.
- **`store_type_deals`:** a row for every row of `stg_store_type_days`, zeros where nothing is checked; `checked` counts the checked rows, `deals` the checked deals, `on_sale_every_tracked_day` the checked with `days_tracked > 0 and days_on_sale = days_tracked`, `on_sale_more_than_half` the checked with `2 * days_on_sale > days_tracked`.

- [ ] **Step 1: Write the failing unit tests**, each `expect` listing every column its model's planted bugs move (for `product_deals`: `today_price`, `usual_price`, `saving`, `days_tracked`, `days_priced`, `days_on_sale`, `days_unknown`, `days_recorded`, `checked`, `verdict`). `int_day_prices` (inputs `stg_items` and `stg_store_type_days`; Osher Ad, 2026-04-30):
  - `the_day_price_is_the_listed_price_to_the_agora_half_up`: listed 4.995 gives listed_shown and day_price 5.00; 4.994 gives 4.99.
  - `the_lowest_promotion_that_counts_sets_the_day_price`: listed 5.00; structs (wide, valid, fixed_price, 4.00, running), (wide, valid, 3.80, running), (not wide, valid, 3.00), (wide, not valid, 2.00), (wide, valid, no kind, 1.00), (wide, valid, 2.50, starting 2026-05-01), (wide, valid, 2.40, ended 2026-04-29): sale_price 3.80, day_price 3.80.
  - `a_promotion_on_its_first_and_its_last_day_counts`.
  - `a_sale_above_the_listed_price_leaves_the_listed_price`: listed 5.00, sale 6.00: sale_price 6.00, day_price 5.00.
  - `a_sale_day_of_unknown_price_has_no_day_price`: on_promotion true, its one wide struct not valid: sale_price NULL, on_sale true, day_price NULL.
  - `a_day_is_tracked_only_with_its_prices_and_promotions_read`: a hole, a promotion hole (promotions unread: on_promotion and promotions NULL, on_sale false), and neither: tracked false, false, true.

  `product_deals` (input `int_day_prices`; Shufersal Universe; today 2026-04-30; history from 2026-04-02, rows typed with `range()`), the golden's day-120 cases (`tests/test_golden_90.py`, `test_the_golden_verdicts`) and the ones it lacks:
  - `always_on_is_no_deal`: 27 tracked days on sale at 9.90, today 9.90: usual 9.90, saving 0.00, days_tracked 27, days_priced 27, days_on_sale 27, checked true, `no deal`.
  - `a_monthly_sale_is_a_deal`: 17 days at 8.90 and 10 on sale at 6.90, today 6.90: usual 8.90, saving 2.00, days_on_sale 10, `deal`.
  - `on_sale_exactly_half_its_days_keeps_its_shelf_price`: 13 at 9.90 and 13 on sale at 7.90, today 7.90: usual 9.90, saving 2.00, `deal`.
  - `a_short_history_is_judged_and_not_checked`: 5 days at 4.50, today 3.20: usual 4.50, saving 1.30, `deal`, checked false.
  - `new_today_has_no_verdict`: no earlier row, today 5.00: usual and saving NULL, days_tracked 0, `no verdict`, checked false.
  - `a_saving_of_99_agorot_is_no_deal` (27 at 5.00, today 4.01: saving 0.99) and `a_saving_of_one_shekel_is_a_deal` (today 4.00: saving 1.00).
  - `a_day_whose_promotions_were_not_read_is_a_record_but_not_tracked`: 28 days with records, one a promotion hole: days_recorded 28, days_tracked 27.
  - `a_sale_day_of_unknown_price_is_on_sale_but_not_priced`: 20 days at 5.00 and 7 on sale unknown, today 4.00: days_tracked 27, days_priced 20, days_unknown 7, days_on_sale 7, usual 5.00, `deal`.
  - `more_than_half_the_days_unknown_has_no_verdict`: 14 unknown of 27: `no verdict`; 13 of 26: judged.
  - `a_product_never_covered_is_not_judged`: never wide, or wide only on a hole day: no row.
  - `the_history_is_the_90_days_before_today`: a day 2026-01-30 (90 before) counts, 2026-01-29 does not, today is not in its own history.
  - `the_bar_reads_the_30_days_before_today`: 20 records, the earliest 2026-03-31 (30 before): checked; the same with the earliest 2026-03-30: 19, not checked.
  - `no_row_without_a_promotion_counting_on_a_tracked_today`: today a hole, a promotion hole, or with no sale price: no row.

  `store_type_deals` (inputs `product_deals`, `stg_store_type_days`):
  - `m_and_n_count_the_checked_products_and_their_deals`: checked rows 2 `deal`, 1 `no deal`, 1 `no verdict`, and an unchecked `deal`: checked 4, deals 2.
  - `on_sale_every_tracked_day_and_on_more_than_half`: checked rows with (days_tracked, days_on_sale) (27, 27), (26, 13), (27, 14), (0, 0): every day 1, more than half 2.
  - `a_store_type_day_with_nothing_checked_is_0_of_0`: a report row and no product row: (0, 0, 0, 0).
- [ ] **Step 2: Run** `tests/test_dbt_units.py`. Expected: fail (no models).
- [ ] **Step 3: Implement** the three models.
- [ ] **Step 4: Run** `tests/test_dbt_units.py` and `tests/test_dbt_project.py`, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 5's anchors. Targets `DBT_DAY_PRICES`, `DBT_PRODUCT_DEALS`, `DBT_STORE_TYPE_DEALS` (each its file with `["tests/test_dbt_units.py"]`). Group `(q28 deals)`, 33: "a promotion at some stores counted", "an unread deal counted", "a promotion with no kind counted", "a promotion starting tomorrow counted", "a promotion ended yesterday counted", "the highest promotion taken", "a sale above the listed price taken", "a sale day of unknown price given the listed price", "the listed price not to the agora", "a promotion hole tracked", "a hole tracked", "the usual price the lower middle", "a saving of 99 agorot called a deal", "a saving of one shekel not a deal", "today in its own history", "the history one day short", "the history one day long", "the bar's window one day short", "the bar's window one day long", "the bar at 19 days", "a promotion hole not a record for the bar", "an untracked day priced", "a sale day of unknown price not on sale", "mostly unknown given a verdict", "exactly half unknown given no verdict", "a product never covered judged", "covered on a hole day", "a promotion hole today judged", "M counting products under the bar", "N counting no deals", "on sale every day with no tracked day", "on sale more than half at exactly half", "a store-type day with nothing checked left out". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt scripts/mutation_check.py && git commit -m "The dbt layer's deals (q28): each tracked day's price (S0, S1, S3), each promotion's verdict against the usual price (S2, S4, P1, the bar), and each store type's N of M"`

### Task 6: The promotions' reach

Wave 3, beside Tasks 4 and 5. Implementer: Opus.

**Files:**
- Create: `dbt/models/marts/promotion_reach.{sql,yml}`
- Modify: `scripts/mutation_check.py` (`(q28 reach)`)

**Interfaces:**
- Consumes: `stg_promotions`, `stg_items`.
- Produces: `promotion_reach` ("The models' columns"): over the rows with `gs1`, a `kind`, `starts <= day <= ends` and a product the items table lists at that store type and day, one entry a promotion (per store type and day), at most branches when any of its rows is `wide`; `restricted` and `with_min_spend` count those at most branches with a restriction or a minimum spend.

- [ ] **Step 1: Write the failing unit tests** (inputs `stg_promotions`, `stg_items`; 2026-04-30; each `expect` lists all five counts):
  - `a_promotion_counts_once_however_many_products_and_groups`: promotion 60 on two listed products in two groups: promotions 1.
  - `at_most_branches_when_any_of_its_rows_is`: 61 with one wide row and one not, 62 with none wide: at_most_branches 1, at_some_branches 1.
  - `only_running_promotions_with_a_kind_on_listed_gs1_products_count`: rows on an unlisted product, with gs1 false, with no kind, starting 2026-05-01, ended 2026-04-29, and one that counts: promotions 1.
  - `restrictions_and_minimum_spends_among_those_at_most_branches`: wide with `['club']`, not wide with `['club']`, wide with min_spend 50.00, wide with none: restricted 1, with_min_spend 1.
  - `each_store_type_and_day_on_its_own`.
- [ ] **Step 2: Run** `tests/test_dbt_units.py`. Expected: fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the unit and project test files, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 6's anchors, target `DBT_PROMOTION_REACH` (`["tests/test_dbt_units.py"]`), group `(q28 reach)`, 7: "a promotion at fewer than half the branches counted at most", "a promotion on an unlisted product counted", "a promotion not yet started counted", "an internal code counted", "a restriction counted at some branches", "a minimum spend counted at some branches", "a promotion counted once a product". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt scripts/mutation_check.py && git commit -m "The dbt layer's promotions reach (q28): each store type's promotions on listed products, at most branches or at a few (P3), with a restriction or a minimum spend (P5)"`

### Task 7: The golden build: the models on the golden's real extraction

After wave 3. Implementer: Opus.

**Files:**
- Create: `tests/test_dbt_golden.py`
- Modify: `scripts/mutation_check.py` (`(q28 golden)`)

**Interfaces:**
- Consumes: `tests/shopper_golden.py` (`write_day`, `write_basket`, `day_of`, the codes, `UNIVERSE_PROMOTIONS`), `shopper.extract.extract_chain_day`, `tests/dbt_run.py`.
- Produces, in `tests/test_dbt_golden.py`: `GOLDEN_DAYS = (1, *range(92, 121))`; a module fixture `golden` (the tables folder, the synthetic published folder, the basket file) that writes the golden's files for `GOLDEN_DAYS` and extracts Shufersal on days 92 to 120 and the four other chains on day 120 (33 chain-days); `published(site: Path) -> None` writing the synthetic published files from the golden's hand-worked numbers; `GOLDEN_VARS` (`tables`, `site`, `basket_file`, `known_differences: []`); a module fixture `clean = run_dbt(["build", "--exclude", "test_type:unit"], tmp, GOLDEN_VARS)`. Tasks 8 to 10 build on these names.

The synthetic published files `published()` writes here: `site-days/2026-04-30.json` with Shufersal Universe's front {deals 4, checked 6, promotions 9, products 9, rows U2 (today "6.90", usual "8.90", saving "2.00", days 27), U3 ("7.90", "9.90", "2.00", 26), U8 ("4.50", "6.00", "1.50", 27), U7 ("4.00", "5.00", "1.00", 27)} and Shufersal Deal's front {deals 0, checked 0, promotions 0, products 0, rows []} (on the golden's 29 days Deal has no promotion running on 30 April: G5's ended on day 106); `days/2026-04-30.json` with each chain's G1, G2 and G6 as the golden's docstring works them ("The basket"), the totals of day 120 beside them (Osher Ad 14.70, Rami Levy 15.00, Shufersal 15.10, Yochananof 15.40, Carrefour 15.80). The promotions count of 9 (every Universe promotion running on day 120 at all three stores, 60 and 62 to 68 and 70; 69 at store 81 alone does not count) is worked here from `UNIVERSE_PROMOTIONS`; Step 2 confirms it.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_clean_build_succeeds`: `clean.code == 0`; every model `success`; every data test `pass`.
  - `test_product_deals_gives_the_golden_s_eight_rows_at_universe`: `product_deals` at `shufersal-universe` on 2026-04-30, by barcode, (today, usual, saving, days_tracked, days_priced, days_on_sale, checked, verdict): U1 (9.90, 9.90, 0.00, 27, 27, 27, true, no deal), U2 (6.90, 8.90, 2.00, 27, 27, 10, true, deal), U3 (7.90, 9.90, 2.00, 26, 26, 13, true, deal), U4 (3.20, 4.50, 1.30, 5, 5, 0, false, deal), U5 (5.00, NULL, NULL, 0, 0, 0, false, no verdict), U6 (4.01, 5.00, 0.99, 27, 27, 0, true, no deal), U7 (4.00, 5.00, 1.00, 27, 27, 0, true, deal), U8 (4.50, 6.00, 1.50, 27, 27, 0, true, deal); no U9 or U10 row (from `tests/test_golden_90.py`'s `universe` and the golden's docstring).
  - `test_store_type_deals_gives_6_checked_and_4_deals_at_universe`: (checked 6, deals 4, on_sale_every_tracked_day 1, on_sale_more_than_half 1).
  - `test_basket_prices_gives_the_golden_s_medians`: G6 on 2026-04-30: Shufersal 7.600 (7.00 to 8.20, 5 stores), Carrefour 8.300 (7.90 to 8.60, 5), Rami Levy 7.500 (7.40 to 7.60, 2), Osher Ad 7.200 (7.10 to 7.30, 2), Yochananof 7.900 (7.80 to 8.00, 2); G1 5.000 and G2 2.500 at every chain, at 5, 5, 2, 2 and 2 stores; double_coded 0.
  - `test_promotion_reach_at_universe_on_its_last_day`: (promotions 10, at_most_branches 9, at_some_branches 1, restricted 0, with_min_spend 0).
- [ ] **Step 2: Confirm the worked figures** the golden's docstring does not state (the promotions count of 9, the reach of 10, 9 and 1, Deal's 0 of 0) with a read-only query of the golden's own tables, and the 9 and Deal's front against the golden run's own `site/site-days/2026-04-30.json` (`tests/shopper_golden.py`'s `run`, about eight minutes, in a scratch folder; that run holds all 120 days, so Deal's front there may differ, and only the 29 days' figure is written). Expected: equal; a difference is a finding, reported before Step 4.
- [ ] **Step 3: Run** `$PY -m pytest -p no:cacheprovider tests/test_dbt_golden.py`. Expected: the value tests fail only where a model is wrong; fix test-first through Task 4 to 6's unit tests, never by editing an expected value the golden works by hand.
- [ ] **Step 4: Run** the file, then the full suite. Expected: exit 0. Report the file's time for "Deviations".
- [ ] **Step 5: Planted bugs,** after Task 7's anchors, on the staging views that only rename, which no unit test reads: targets `DBT_STG_PRICES_FOR_GOLDEN`, `DBT_STG_ITEMS_FOR_GOLDEN`, `DBT_STG_PROMOTIONS_FOR_GOLDEN` (each its `.sql` with `["tests/test_dbt_golden.py"]`). Group `(q28 golden)`, 3: "the prices' store read as their sub-chain", "the items' store type read as their chain", "the promotions' start and end swapped". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add tests/test_dbt_golden.py scripts/mutation_check.py && git commit -m "The dbt layer on the golden 90 days (q28): the real extraction's tables of 33 chain-days, built by dbt, give the verdicts, N of M, basket medians and reach the golden works by hand"`

### Task 8: Data tests on the prices and promotions tables

After Task 7. Implementer: Opus.

**Files:**
- Create: `dbt/macros/unique_together.sql` (`{% test unique_together(model, columns) %}`: the groups with more than one row), `dbt/macros/is_gs1.sql` (`{% macro is_gs1(barcode) %}`: 8 to 14 ASCII digits, no leading zero, the check digit weighted 3, 1, 3, ... from the right, as `basket.barcode.is_gs1`), `dbt/tests/prices/*.sql`, `dbt/tests/promotions/*.sql`, `dbt/tests/prices/_prices.yml`, `dbt/tests/promotions/_promotions.yml`
- Modify: `dbt/models/sources.yml` (the two generic tests), `tests/test_dbt_golden.py`, `tests/test_dbt_project.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: Task 7's fixtures and names.
- Produces, in `tests/test_dbt_golden.py`: `plant_bad_rows(tables: Path, site: Path) -> None` (on a copy of the golden's folders: Parquet rewritten through DuckDB with every column's type kept, JSON through `json`); `BAD_VARS` (`GOLDEN_VARS` on the copy); `EXPECTED_BAD: dict[str, tuple[str, int]]` (each data test's name to its status, `fail` or `warn`, and its failures); a module fixture `bad`: `run_dbt(["run"], ..., BAD_VARS, database=d)` then `run_dbt(["test", "--exclude", "test_type:unit"], ..., BAD_VARS, database=d)` (call 3).

**The bad rows' rules,** for this task and Tasks 9 and 10: each planted bug a data test's rule can carry has a bad row it catches, so a weakened clause lowers that test's failures; a bad row breaks one clause of one test and keeps every other rule; a row added or changed in an items table moves its report's counts with it; bad rows stay away from what another test reads unless the table says so. A singular test returns one row per offending row of the relation it reads unless its table says otherwise; a generic uniqueness test one row per repeated key. The "Fails" column is `EXPECTED_BAD`'s entry: the builder confirms each against the build, and a count that differs is a finding about the bad rows' isolation, never a number to adjust.

| Name | Rule | Bad rows (30 April unless said) | Fails |
|---|---|---|---|
| `prices_one_row_per_chain_day_store_and_code` (generic, on the source, `"date"`, `chain`, `store`, `code`; tagged `slow`) | B3 | Universe store 81's U1 row twice | fail, 1 |
| `prices_one_file_per_store_and_day` (one row per store-day) | B1 | store 82's U2 row under a second `PriceFull` name of the day | fail, 1 |
| `prices_each_row_from_a_pricefull_file_of_its_day` (one row per file) | B1 | every row of store 83 under one `Price` file name of the day; every row of store 81 under one `PriceFull` name of 29 April | fail, 2 |
| `prices_gs1_is_the_check_digit` (one row per barcode and flag) | `is_gs1`; waits on the owner's ruling (Questions, 1) | a code with a wrong check digit flagged GS1; a valid 13-digit code flagged not; a 15-digit code with a valid check sum flagged not GS1 (right, so it fails only a weakened length) | fail, 2 |
| `promotions_one_row_per_day_store_type_promotion_group_and_code` (generic, on the source) | operations.md, "Where things land" | a Carrefour City row on U1 (which Carrefour does not list) twice; Universe's promotion 60 on U1 copied under a second group (unique, so it fails only a key without the group) | fail, 1 |
| `promotions_wide_is_half_the_counted_stores` | P3: `wide` is `stores * 2 >= counted`; 1 <= stores <= promotion stores <= counted | at Carrefour City on U1: wide false at 2 of 2; stores above promotion stores (the clean build's promotion 69, 1 of 3 and not wide, catches a weakened half) | fail, 2 |
| `promotions_run_today_and_start_before_they_end` | P3 | at Carrefour City on U1: one ended the day before; one starting after it ends | fail, 2 |
| `promotions_kind_follows_the_reward_type` | P3, the var `kinds`; never reward type 6 or 12 | reward type 2 with kind `fixed_price`; reward type 6 | fail, 2 |
| `promotions_minimum_spend_above_zero` | "Changed after the survey" | min spend 0.00 | fail, 1 |
| `promotions_store_prices_in_order` | survey 5: low <= median <= high; the percent-off counts in order, on percent off only | low above median; `with_store_price` on a fixed-price row | fail, 2 |
| `promotions_counted_is_the_reports` | P3: the stores counted are P2's | counted 3 where the report says 2 | fail, 1 |

The Carrefour City rows are on U1, which Carrefour does not list, so neither `promotion_reach` nor the across-table count reads them; Universe's copy under a second group leaves `promotion_reach` as it is (a promotion counts once however many groups).

- [ ] **Step 1: Write the failing tests:** `test_the_bad_rows_trip_exactly_their_tests` (`bad`'s `dbt test` exits 1, and its results for the data tests equal `EXPECTED_BAD`); `test_every_data_test_has_its_bad_row` (`set(EXPECTED_BAD)` is every data test in the manifest); `tests/test_dbt_project.py::test_the_one_slow_test_is_the_prices_uniqueness` (exactly one test tagged `slow`, that one).
- [ ] **Step 2: Run** `tests/test_dbt_golden.py` and `tests/test_dbt_project.py`. Expected: the new tests fail.
- [ ] **Step 3: Implement** the macros, the tests and their descriptions (confirm call 12's description file with one `dbt parse`), `plant_bad_rows` and `EXPECTED_BAD`.
- [ ] **Step 4: Run** the two files (the clean build must still pass every data test), then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 8's anchors, one target per test file (`["tests/test_dbt_golden.py"]`), `DBT_UNIQUE_TOGETHER`, `DBT_IS_GS1`, `DBT_SOURCES_FOR_GOLDEN = ("dbt/models/sources.yml", ["tests/test_dbt_golden.py"])`, and `DBT_SOURCES` for the tag. Group `(q28 checks prices)`, 7: "uniqueness allowing one repeat", "two files of a store's day allowed", "a file of another day allowed", "a file of another kind allowed", "the check digit weighted from the left", "a 15-digit code taken as GS1", "the slow tag lost". Group `(q28 checks promotions)`, 11: "the promotions' uniqueness without the group", "wide at a third of the stores", "stores above the promotion's stores allowed", "an ended promotion allowed", "a start after the end allowed", "a kind not its reward type's allowed", "reward type 6 allowed", "a minimum spend of zero allowed", "the stores' prices out of order allowed", "percent-off counts on another kind allowed", "counted not the report's allowed". Run both groups, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt tests/test_dbt_golden.py tests/test_dbt_project.py scripts/mutation_check.py && git commit -m "The dbt layer's data tests on the prices and promotions tables (q28), each proved to fail on a bad row planted in the golden's tables"`

### Task 9: Data tests on the items table and its reports

After Task 8. Implementer: Opus.

**Files:**
- Create: `dbt/tests/items/*.sql`, `dbt/tests/items/_items.yml`
- Modify: `dbt/models/sources.yml` (the items' generic test), `tests/test_dbt_golden.py` (`plant_bad_rows`, `EXPECTED_BAD`), `scripts/mutation_check.py` (`(q28 checks items)`)

The bad rows' rules are Task 8's.

| Name | Rule | Bad rows (Carrefour Market and Carrefour City, 30 April, unless said) | Fails |
|---|---|---|---|
| `items_one_row_per_day_store_type_and_product` (generic, on the source) | operations.md, "Where things land" | Market's G2 row twice | fail, 1 |
| `items_store_type_is_one_of_the_nine_under_its_chain` | store-first, "The rules", the var `store_types` | a row under `carrefour-express`; a row under `shufersal-deal` in Carrefour's table, of U1 | fail, 2 |
| `items_listed_price_in_range_and_listed_somewhere` | P2, B4, B5: low <= listed <= high; listed above ₪0.01; listing at least 1 | three Market rows, each breaking one clause alone | fail, 3 |
| `items_wide_is_half_the_stores_with_a_file` | B6 per store type, P1: `listing * 2 >= with_file` from the report | Market's G1 not wide at 2 of 2; a new Universe row (a synthetic barcode no other test reads) listed at 1 of 3 stores and not wide (right, so it fails only a weakened half), Universe's report moved with it | fail, 1 |
| `items_on_promotion_follows_its_promotions` | P3, as `shopper.items` reads it; NULL exactly when the promotions were not read | Market's G6 on promotion with no promotion running; on Carrefour's 28 April copy (below), whose promotions were not read, one row's on_promotion false instead of NULL | fail, 2 |
| `items_promotions_start_before_they_end_run_today_and_appear_once` | P3 | three Market structs, each breaking one clause alone | fail, 3 |
| `items_valid_deal_prices_are_above_an_agora_and_below_twice_the_listed` | P4, as shown | a valid struct at 0.01; one at twice the listed price | fail, 2 |
| `items_report_holes_follow_their_counts` (one row per store-type day) | B8 per store type, S0: hole is `included = 0 or with_file * 2 < included`; promotion hole is `promo_files * 2 < counted` or a promotions error | Market's hole set with every file; City's promotion hole set (promo_files under half of counted, the flag left false); the 28 April copy's promotion holes true from its promotions error (right, so it fails only a rule that forgets the error) | fail, 2 |
| `items_every_chain_every_day` (`severity: warn`; one row per missing chain-day) | call 6 | Carrefour's items table and report of 30 April copied under 28 April (not its prices table), the copy's report given a promotions error and both promotion holes true, its rows' promotions and on_promotion NULL (Carrefour has no promotion struct on 30 April, so the copy breaks nothing else) | warn, 1 |
| `items_agree_with_their_reports` (one row per store-type day) | the report is the table's own count: rows, wide, on promotion, valid deals, over the store-type days the report holds, by chain, store type and day (call 7); rows under a store type the report lacks (this task's `carrefour-express` and Carrefour's `shufersal-deal`) are left out | four store-type days, each one count off | fail, 4 |

Every row this task adds or changes comes with its report's counts moved to match, so that `items_agree_with_their_reports` fails on its own four alone. Every report's day is its folder's (`stg_store_type_days`), so the 28 April copy needs no edit of its `day` field.

- [ ] **Step 1: Write the failing tests:** the rows above in `plant_bad_rows` and `EXPECTED_BAD`; `test_every_data_test_has_its_bad_row` then fails until the tests exist.
- [ ] **Step 2: Run** `tests/test_dbt_golden.py`. Expected: fail.
- [ ] **Step 3: Implement** the tests.
- [ ] **Step 4: Run** the file, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** one target per test file with `["tests/test_dbt_golden.py"]`, group `(q28 checks items)`, 21: "a store type outside the nine allowed", "a store type under another chain allowed", "a low above the listed allowed", "a listed price of one agora allowed", "a product no store lists allowed", "wide at a third of the stores", "on promotion from a promotion at some stores", "on promotion with its promotions unread", "a promotion starting after it ends allowed", "an ended promotion allowed on a row", "a promotion twice on a row allowed", "a valid deal at one agora allowed", "a valid deal at twice the listed allowed", "a hole with every file allowed", "a promotion hole from its counts missed", "a promotions error not a promotion hole", "a missing day of a chain allowed", "the report's rows not compared", "the report's wide not compared", "the report's on promotion not compared", "the report's valid deals not compared". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt tests/test_dbt_golden.py scripts/mutation_check.py && git commit -m "The dbt layer's data tests on the items table and its reports (q28), each proved to fail on a bad row planted in the golden's tables"`

### Task 10: Data tests across tables and against the published files

After Task 9. Implementer: Opus.

**Files:**
- Create: `dbt/tests/across/*.sql`, `dbt/tests/published/*.sql`, their `_across.yml` and `_published.yml`
- Modify: `tests/test_dbt_golden.py` (`published`, `GOLDEN_VARS`, `plant_bad_rows`, `BAD_VARS`, `EXPECTED_BAD`), `scripts/mutation_check.py` (`(q28 checks across)`, `(q28 checks published)`)

**Interfaces:**
- Consumes: `median_price`, every model, `known_differences`.
- Produces: the clean published files gain Shufersal Sheli's front of 30 April {deals 1, checked 1, promotions 1, products 1, rows [G3: today "7.90", usual "10.90", saving "3.00", days 90]}, the full golden's figures, where the golden build's 29 days give 0 of 1 (its promotions count, G3's promotion 30, is the model's 1); Yochananof's G6 median "7.80" on 30 April (the model gives 7.900); and `days/2026-04-29.json`, with Shufersal's figures right and the four other chains' wrong on purpose (they have no prices table that day). `GOLDEN_VARS["known_differences"]` lists the first two (`store_page`, `shufersal-sheli`, 2026-04-30) and (`basket`, `yochananof`, 2026-04-30), each with its reason.

The bad rows' rules are Task 8's.

| Name | Rule | Bad rows (30 April) | Fails |
|---|---|---|---|
| `listed_price_is_the_median_of_the_prices_table` (one row per chain, day and barcode) | P2, B5: at each chain of one store type (read from `store_types`), the items' listed price, range and stores are B5 over `int_counted_prices`' GS1 rows, both ways | a Rami Levy store's G4 price changed (G4 is no basket product); a GS1 price row at Rami Levy store 1 with no items row; Rami Levy store 39's price file of the day, G4 alone (left out, so right, failing only a check that reads the rows that do not count); Osher Ad's G6 at 7.10 and 7.19, the items row moved with it (listed 7.145, high 7.19: right) | fail, 2 |
| `promotions_at_most_branches_agree_across_tables` (one row per store-type day) | P3: `promotion_reach`'s count at most branches equals the items table's, on the store-type days both have | a wide, running fixed-price promotions row on Osher Ad's G2 | fail, 1 |
| `store_type_deals_match_published` (one row per published store-type day) | N and M, skipping a known store page | Universe's checked 7; Carrefour City's front with N 1 where the model gives 0 of 0, M right | fail, 2 |
| `product_deals_match_published_rows` (one row per shown row) | each shown row's today, usual and saving, and its published `days` against `days_priced` (the site writes `len(found.priced)`: `src/shopper/siteday.py:133`), skipping a known store page | U2's usual "8.80" | fail, 1 |
| `promotion_reach_matches_published` (one row per published store-type day) | the published promotions count against `at_most_branches`, as call 17 reads a missing row | Universe's promotions 8 | fail, 1 |
| `basket_prices_match_published` (one row per published chain, day and item) | median (to two places, half up), lowest, highest, stores, double-coded, at the four chains, skipping a known basket day | Rami Levy's G6 median "7.40"; Osher Ad's G6 published "7.15", high "7.19" (the model's 7.145, rounded half up: right, so it fails only a rounding that is not half up) | fail, 1 |
| `basket_prices_at_shufersal_match_published` (`severity: warn`) | the same at Shufersal; its description gives store 678's reason (the design's section 3, 3) | Shufersal's G6 listing 6 | warn, 1 |
| `known_differences_still_differ` (one row per listed entry) | each listed day has both sides and still differs | `BAD_VARS`' list gains Carrefour's basket and Shufersal Deal's store page (its published front 0 of 0, as the model gives) of 30 April, which match | fail, 2 |

- [ ] **Step 1: Write the failing tests:** the published additions, the rows above in `plant_bad_rows`, `BAD_VARS` and `EXPECTED_BAD`.
- [ ] **Step 2: Run** `tests/test_dbt_golden.py`. Expected: fail.
- [ ] **Step 3: Implement** the tests.
- [ ] **Step 4: Run** the file, then the full suite. Expected: exit 0: the clean build passes with its two known differences skipped, Shufersal Deal's 0 of 0 and its promotions 0 matched, the day-29 basket's four chains unread, and every data test passing.
- [ ] **Step 5: Planted bugs,** one target per test file with `["tests/test_dbt_golden.py"]`. Group `(q28 checks across)`, 3: "the listed price compared one way only", "the prices table's left-out stores counted", "the reach compared with the items' promotions at some stores". Group `(q28 checks published)`, 12: "N not compared", "M not compared", "a known store page compared", "a shown row's usual price not compared", "a known store page's rows compared", "the promotions count not compared", "the basket's median not rounded half up", "a known basket day compared", "a chain-day with no table compared", "Shufersal's basket an error", "a known store page that matches allowed", "a known basket day that matches allowed". Run both groups, then the staleness check.
- [ ] **Step 6: Commit:** `git add dbt tests/test_dbt_golden.py scripts/mutation_check.py && git commit -m "The dbt layer's data tests across tables and against the published files (q28): N of M, the shown rows, the promotions count and the basket compared, the known differences skipped and held to still differ"`

### Task 11: The lineage map, the README section and the docs

Beside Tasks 7 to 10, after waves 2 and 3 and Task 3. Implementer: Opus.

**Files:**
- Create: `scripts/dbt_lineage.py`, `tests/test_dbt_lineage.py`
- Modify: `README.md`, `docs/operations.md`, `docs/README.md`, `tests/test_dbt_project.py`, `scripts/mutation_check.py` (`(q28 lineage)`)

**Interfaces:**
- Consumes: the manifest of `run_dbt(["parse"], ...)`.
- Produces:

```python
# scripts/dbt_lineage.py (run by the project's .venv; reads JSON only)
START = "<!-- dbt lineage: made by scripts/dbt_lineage.py from dbt's manifest; tests/test_dbt_lineage.py holds it equal -->"
END = "<!-- end of dbt lineage -->"
def mermaid(manifest: Mapping) -> str        # "```mermaid\ngraph LR\n...```": each source as id[(label)], then one edge a
                                             # line, parent --> child, models and sources only, sorted; a model with
                                             # no edge (known_differences) is not drawn
def readme_block(readme: str) -> str         # the text between START and END
def main(argv: Sequence[str]) -> int         # <manifest.json>: prints the block; --check <README>: 1 when they differ
```

- [ ] **Step 1: Write the failing tests** in `tests/test_dbt_lineage.py` (the script loaded by path, as `tests/test_mutation_targets.py` loads its):
  - `test_mermaid_draws_sources_as_tables_and_one_edge_a_line`: a made-up manifest of two sources and three models, its nodes and their parents given out of order, gives the exact sorted text.
  - `test_tests_unit_tests_and_unread_lists_are_not_drawn`: a data test, a unit test and a model with no parent and no child in the made-up manifest draw nothing.
  - `test_the_check_exits_1_on_a_stale_readme`: `main(["--check", <a README with another block>, <manifest>]) == 1`.
  - `test_the_readme_diagram_is_the_project_s`: `readme_block(README) == mermaid(<the parse's manifest>)`.
  - In `tests/test_dbt_project.py`, `test_every_install_of_the_dbt_environment_is_the_same` gains `docs/operations.md`.
- [ ] **Step 2: Run** the file. Expected: fail.
- [ ] **Step 3: Implement** the script; then the docs:
  - `README.md`: the stack line gains "dbt (DuckDB adapter)"; a new section after "Engineering choices worth a look", the design's section 9 draft word for word, "(the diagram)" replaced by `START`, the block and `END`, and after its first paragraph one sentence for the owner's read: "Installing it fetches one compiled wheel from dbt's GitHub release, its parser's, checked against a fingerprint the package carries." Its figures are the design's, measured 2026-11-25; Task 13 checks them again, and the owner settles the words (Shipping).
  - `docs/operations.md`, "Develop": the dbt tests need `.venv-dbt` (the install of Global Constraints, word for word), as `search.js`'s need `node`; that each fresh install fetches the parser's wheel from dbt's GitHub release v2.0.8, checked against the SHA-256 the package carries, and why `packaging` goes first; "`pip show dbt-core` gives the version; dbt's own version flag asks PyPI, so it is never run" (in those words: the flag itself is never written, which `test_nothing_asks_dbt_its_version` holds). A new section, "The dbt layer, on the Mac": once (the install) and each time (the sync, then from `dbt/`: `../.venv-dbt/bin/dbt run`, then `../.venv-dbt/bin/dbt test`, or `dbt test --exclude tag:slow`, then `dbt docs generate --static` for dbt's page, read on the Mac only), with why `run` then `test` (in one `dbt build` a failing error test skips the models downstream of what it reads, and `items_agree_with_their_reports` fails on the Mac until a sync with the new items line); the folders and the database; what `fail` and `warn` mean and that a failing data test is never dropped or left without a reason; the known differences and their rule; the store 678 warning; "How long" with the design's measured figures, to be replaced by Task 13's. "The shopper site, by hand", step 1: the two tables and the items tables' times.
  - `docs/README.md`: `dbt-layer-plan.md` joins the build plans' line.
- [ ] **Step 4: Run** the file and `tests/test_dbt_project.py`, then the full suite. Expected: exit 0.
- [ ] **Step 5: Planted bugs,** after Task 11's anchors, target `DBT_LINEAGE = ("scripts/dbt_lineage.py", ["tests/test_dbt_lineage.py"])`, group `(q28 lineage)`, 4: "a source drawn as a model", "a data test drawn", "the edges unsorted", "a stale README passing the check". Run the group, then the staleness check.
- [ ] **Step 6: Commit:** `git add scripts/dbt_lineage.py tests/test_dbt_lineage.py tests/test_dbt_project.py README.md docs/operations.md docs/README.md scripts/mutation_check.py && git commit -m "The dbt layer's lineage in the README, made from dbt's manifest and held equal by a test; README's section on where dbt earns its place; operations.md's runbook (q28)"`

### Task 12: The whole-branch review

- [ ] **Step 1:** Dispatch a reviewer that has not seen the build, on Fable (`fable`), or on the newest Opus at Fable's limit, the report naming the swap. Give it `git diff a54c6f3...q28-dbt-layer` (main may have taken Task 3 early), `docs/dbt-layer.md` and this plan's Global Constraints, Review Focus, calls and "The models' columns". Ask for findings by severity against: the design's anti-goals; each model's SQL against the Python rule it mirrors (`shopper.verdict`, `shopper.history`, `shopper.items`, `basket.rules`); each data test against its design note, and whether its bad rows catch each of its planted bugs and trip it alone; prices kept DECIMAL; no clock; every dbt run in temporary folders; telemetry; the install and its one GitHub download; the sync read-only and its filters; the pins; every public fact. The reviewer reads only: no commits, no `gh`, no push, no AWS, no network.
- [ ] **Step 2:** Check each finding against its source before acting on it. Fix what holds, test-first, each fix with its planted bug; a scoped re-review of the fixes (Opus). Report every change for "Deviations".
- [ ] **Step 3:** The full suite, `$PY scripts/mutation_check.py "q28" "the items tables not synced"` (timed), the staleness check, `../il-grocery-prices/.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: exit 0, every planted bug CAUGHT, `none stale`, clean. Report the counts and times for "Deviations". Then the weekly run: the newest weekly run's duration (the main session reads it from the Actions tab or with one `gh run view`, never a subagent) plus the measured q28 time is the new weekly estimate, set beside `mutations.yml`'s `timeout-minutes: 300` (under about 240 minutes: noted; above it: a finding for the owner). The "1 h 51 min" lines (`.github/workflows/mutations.yml:3-4`, README's "Tests that are themselves tested", `docs/operations.md`'s "Develop") gain the new estimate beside the measured figure, said as an estimate. Commit: `git add .github/workflows/mutations.yml README.md docs/operations.md && git commit -m "The weekly mutation run's estimate with the dbt layer's planted bugs (q28)"`.

### Task 13: On the Mac's real tables: the build, its figures and timings, the appendix checked again

Last. The syncs are the main session's; the build and the queries are the implementer's (Opus), reading the main checkout's data, never writing it but for `data/dbt.duckdb`.

- [ ] **Step 1 (the main session, read-only AWS):** with the new sync lines in the main checkout ("How this plan runs", "The sync ahead of the rest"), `sh ../il-grocery-prices/scripts/sync.sh <day>` for each day the main checkout's `data/tables/prices/` covers (12 days on 2026-11-25), then the latest day. Record for "Deviations" the days, the megabytes the tables brought, and how many items reports came down again.
- [ ] **Step 2: The sources counted** (read-only DuckDB, a scratch script outside the repository): files, days and rows of each source, against the design's section 1. Differences reported for "Deviations", with their reason.
- [ ] **Step 3: The build,** from the worktree's `dbt/`, each command with `GROCERY_DBT_DB=../../il-grocery-prices/data/dbt.duckdb` and `--vars '{tables: ../../il-grocery-prices/data/tables, site: ../../il-grocery-prices/site}'`: `../.venv-dbt/bin/dbt run`, then `../.venv-dbt/bin/dbt test`, then `dbt test --exclude tag:slow`, then `dbt docs generate --static` (dbt's page stays on the Mac). Record the exit codes; each data test's status and failures; each node's time from that command's own `run_results.json` (copied aside before the next command overwrites it); each command's time; and any node skipped (expected: none, since `run` and `test` are apart). Expected, against the design's section 3: every test holds as there, but `items_agree_with_their_reports` now passes if the re-sync brought the archive's reports (Task 3, Step 1's cause); the known differences still differ, or one stops differing now that the archive's tables replaced the Mac's (Shufersal's of 9 November most likely): then `known_differences_still_differ` fails as it should, and the entry goes only on the owner's word, recorded in "Deviations". Any other failure is a finding, fixed test-first with its planted bug and a scoped review, never by weakening a test.
- [ ] **Step 4: The appendix checked again** by read-only queries on the built database: `store_type_deals` of 23 November at each store type and in all; `product_deals`' rows and the published rows matched on 21, 22 and 23 November; `promotion_reach` of 23 November summed; `basket_prices`' rows and the figures matched by chain. Each figure beside the design's; differences and their reasons reported for "Deviations", and the design's appendix gains a dated line saying what moved and why.
- [ ] **Step 5: The docs:** README's section's figures checked against Step 4 (changed only with the reason, for the owner's read); `docs/operations.md`'s "How long" filled with Step 3's figures, with the left-out filter's cost against the 6.2 s direct query (call 8; over 20 s is a finding to report); the `TIME_LIMIT` comment's count of target sets (call 16) and the new sets' unmutated times; `docs/dbt-layer.md`'s status line: built, with this plan's "Deviations" for what changed.
- [ ] **Step 6:** The full suite, every `q28` group and the re-pointed one, the staleness check. Write the counts (tests, coverage, planted bugs, the date) in README's "At a glance" row "Tests" (`README.md:31`) and "Tests that are themselves tested" (`README.md:70`), and report them for "Deviations".
- [ ] **Step 7:** A scoped review (Opus) of Steps 3 to 6's changes. Then commit: `git add README.md docs scripts/mutation_check.py && git commit -m "The dbt layer on the Mac's real tables (q28): the build's results and timings, the design's appendix checked again, README's counts"`.

## Shipping (the owner's go; not a task)

- **The owner's read** of README's new section, its words the owner's to settle (the design's section 9), its sentence on the GitHub download included; changes are a fix round, Task 11's lineage test passing after them.
- **On the owner's go:** `git fetch`; if main moved, `git rebase origin/main` (the branch was never pushed); the full suite and every `q28` group again on the rebased branch; `gh auth status`; merge to main and push. CI's first run is the first install of the 59 pins on Linux, its parser's wheel fetched from GitHub there too (call 2: UNVERIFIED until then). Nothing deploys: nothing here runs in AWS.
- Then the post-merge quiz, and the local branches of this plan's waves removed with `git branch -d` once merged.

## Deviations

(Append here when reality forces a change from this plan: what changed, why, and when.)

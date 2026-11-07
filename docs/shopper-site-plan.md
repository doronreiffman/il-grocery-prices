# The shopper site, step one: implementation plan

Grade: portfolio grade, as the approved design states (`docs/shopper-site.md`, "Grade"): tested, reproducible, honest in its words; not production. The forecast record is held to the design's record standard: frozen forecasts and their scores write-once, the ledger only grows. The build practice is the design's "Testing" section and the project's rules: test-first, a named mutation for every rule, the coverage floor, a fresh reviewer on every task and on the whole branch.

Status: approved by the owner on 2026-11-07, with questions A to M answered as recommended; for question H the owner rewords the project's rule on deleting. The build runs after q23's merges.

Monthly cost of step one: about $4 to $6 in year one, worst case about $10.30 (the design's figures, checked in "Cost" below).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** step one of the shopper site: every morning, from the chains' own files, a page per product with its listed prices, its promotions and their measured gaps, a front page of deals below their recent listed prices, browse pages and search, the method, record and basket pages, and a forecast frozen in public each day and scored 14 days later, with no odds shown to anyone.

**Architecture:** a new package `src/shopper/` beside `basket` and `collector`, stdlib plus the DuckDB already pinned. The scheduled function stays `BasketFunction` in its two modes (design, Call 5): `extract` (12:03, one run per chain) now writes three tables per chain-day, prices (as today), promotions and items; `basket` (12:33) now builds the whole site: it reads 90 days of items tables, scores the forecasts frozen 14 days back, freezes today's forecasts write-once in the archive, prices the basket, renders every page, runs the site check and the guard, uploads and invalidates. The Mac runs the same code by hand (`python -m shopper.build`), as the basket's hand build does. Pages are plain HTML; `search.js` is the one script.

**Tech Stack:** Python 3.13 (`xml.etree.ElementTree.iterparse`, `fractions`, `decimal`, `random`, `concurrent.futures`), `duckdb==1.5.6` (already in `requirements-dev.txt` and the layer), boto3 from the Lambda runtime, SAM and CloudFormation, EventBridge Scheduler (unchanged), pytest and pytest-cov, `scripts/mutation_check.py`; Node 22.11.0 for the tests of `search.js` only (CI step `actions/setup-node@v4`; the Mac has Node 24).

**Spec:** `docs/shopper-site.md`, approved by the owner on 2026-11-07 with every question answered as recommended. Read all of it before any task: "Definitions and rules", "The forecast", "What the site needs from the reader", "Build and hosting", "Words", "Testing", "Cost", "Calls", "Left to the builder". The code this builds on: `docs/headline-basket.md` (B1 to B12, the words) and its two plans, `src/basket/`, `docs/operations.md` ("The headline basket, by hand" and "every morning"), `template.yaml`, `site-template.yaml`, `scripts/publish.sh`, `scripts/sync.sh`.

Tasks:

1. Promotion files read one link at a time (`shopper.promofile`)
2. The survey: each chain's promotion fields measured, two new fixtures, the readings recorded
3. Which promotions count, their conditions from the fields, and a format change stopping a chain (P3, P5, P10)
4. The deal price (P4)
5. The promotions table, counted at the stores P2 counts (Call 7)
6. The items table and the reader's input (P1's day test, P2, the day's promotions)
7. The extract mode writes prices, promotions and items
8. History and coverage: 90 days read, the covered registry, the windows (P1, Call 10, P6)
9. The measured facts: the gap, the promotion history, the front page's test (P7, P8)
10. Outcomes, who gets a forecast, inputs pinned to the day (F1, F2, F3)
11. The model, the two baselines and the forecasts file (F4, F5)
12. The daily freeze and the ledger (F6)
13. Scoring (F7)
14. The record's numbers: intervals, calibration, the gate, the scorecard (F8, F9, F11)
15. The site's words
16. Product pages (with P9's row)
17. Browse pages and search (`search.js`)
18. The front, method, record and basket pages
19. The site-day file and the build command
20. The site check
21. The guard
22. Uploads, `publish.sh` and `sync.sh`
23. The site run in Lambda
24. The templates: the function's role and the site bucket's lifecycle rule
25. The golden 90 days, determinism and F3 end to end
26. The docs
27. Full test run, coverage and the full mutation check
28. The whole-branch review

## Questions for the owner

Each is something the design leaves open beyond "Left to the builder", or a fact measured since the design. They are lettered, A to M, so as not to be read as the design's Q1 to Q10. The plan is written around each recommendation; an answer the other way changes the tasks named.

- (Owner, 2026-11-07: as recommended.) **A. Several promotions on one item at one chain on one day.** The design speaks of "today's promotion" and "the deal" in the singular. Recommended: the product page lists every chain-wide promotion of the item at the chain (each with its deal price, conditions and P7 facts); the front page has one row per (chain, product), its lowest validated deal price; P8 and F1 count a day as on promotion when any chain-wide promotion with a price effect is listed; the count line's "N products" and "K of them" count barcodes (a product passing at two chains counts once, and shows as two rows). Changes: Tasks 6, 9, 18.
- (Owner, 2026-11-07: as recommended.) **B. The survey decides each chain's codes, and stops the build only on a contradiction.** The design leaves to step one each chain's gift marking (`IsGiftItem`), what its `ClubID` and `RewardType` values mean, which group carries `MinPurchaseAmount`, and each chain's field set (P3, P5, P10; there are no Osher Ad or Yochananof promotion fixtures yet). Recommended: Task 2 measures them on two real days and the controller writes them into Task 3's constants, with the evidence in `docs/operations.md`; the build stops for your word only when a finding contradicts a reading the design states (a `RewardType` meaning other than P3's, `ClubID` codes other than 0 to 3, a chain whose promotions mostly differ by store so that "chain-wide" is rare). Changes: Tasks 2 and 3.
- (Owner, 2026-11-07: as recommended.) **C. What "the fields agree with each other" means (P4).** Only percent off has two fields to compare. Recommended: a fixed price (`RewardType` 3) and "N for ₪M" (1 and 10) agree when their price fields read as numbers; percent off (2) agrees when `DiscountRate` is above 0 and below 100 and, where `DiscountedPrice` is given, it is within ₪0.01 of the listed price × (1 − rate/100) rounded half up to agorot; then the range check (above ₪0.01, below twice the listed price). If Task 2 finds a chain whose `DiscountedPrice` means something else on percent-off links (the discount itself, say), that chain's check follows the survey and you are told. Changes: Task 4.
- (Owner, 2026-11-07: as recommended.) **D. Freezing and scoring happen only in Lambda; the deploy comes before the first hand upload, schedules off.** The design ships "by hand first, then scheduled". Recommended: only the function's site run writes `forecasts/` and `scores/` in the archive (the Mac never writes the archive; its build reads what the archive holds, synced read-only, and freezes nothing); and since today's scheduled 12:33 run would overwrite the new `index.html` and `method.html` with the basket's, both stacks deploy with `BasketScheduleState=DISABLED` before the hand upload. The basket page stops refreshing from that deploy until the schedules go on. If the hand phase runs past a chain's 30th day of records (about 30 November), a manual site run in Lambda freezes that day. Changes: Tasks 12, 19, 26.
- (Owner, 2026-11-07: as recommended.) **E. F6's "same" or "differs" compares the CSV inside the gzip, and "differs" stops the run before any upload.** Gzip bytes can differ between the Mac's, CI's and Lambda's zlib for the same content. Recommended: compare the decompressed CSV; the bytes published are always the archive's; on "differs" the run stops with `ForecastsDiffer` naming both SHA-256s and pings `/fail`, uploading nothing, as `RevisionNeeded` does. Consequence: every forecast row names the code fingerprint (F6), so a same-day rerun after any change under `src/` (the collector's included) stops; the day's pages then come from a rerun at the commit that froze it. Changes: Tasks 12, 23.
- (Owner, 2026-11-07: as recommended.) **F. The model's details the design leaves open (F4, F5).** Recommended: (a) days since the last run ended above 60 are counted as 60 ("60 or more"); (b) the history the model and both baselines learn from is the site run's 90-day read: closed days t from d − 90 to d − 14, each t's features from days up to t within that read; (c) a closed day whose window holds more than 4 holes is left out of the history too, by the scoring rule; (d) a hazard bucket with no closed days, and a "B gave the same answer" set with none, take the chain's share; (e) B's next start: the last run's end plus the days from the end of the run before it to the start of the last run; (f) days since are calendar days from the last run's end. n0 is the builder's (30, under "Where the design leaves room"). Changes: Tasks 10, 11.
- (Owner, 2026-11-07: as recommended.) **G. Products covered more than 90 days ago (Call 10).** The site run reads 90 days, so a product last chain-wide 120 days ago would lose its page's facts. Recommended: a derived registry, `tables/covered/date=<d>/covered.parquet` (plain, overwritable like every table), each day's being the latest earlier one joined with the day's chain-wide listings: each product's names, size, first covered day and last chain-wide day per chain. A page beyond the read says when it was last listed chain-wide and shows no history. It bites only from late January 2027, so it could wait; it is about one task's worth and keeps Call 10 true from day one. Changes: Tasks 8, 19, 23.
- (Owner, 2026-11-07: as recommended.) **H. No `--delete` in `publish.sh`, and the project's rule on deleting.** The basket's hand upload deletes pages the build no longer writes; under Call 10 the build never stops writing a page, and a hand build from a partly synced `data/` would delete thousands of product pages. Recommended: no `--delete` anywhere; the guard refuses any upload whose build lacks a product page the bucket holds (Task 21). The design's Q10 lifecycle rule then makes S3 itself the one thing that removes anything, and only noncurrent versions: the project's hard rule "`scripts/publish.sh` is the only thing that deletes" needs your amendment in the project notes (not a plan task). The rule's "fixed pages" are read as `index.html`, `method.html`, `record.html`, `basket.html` and `search.js` (rebuilt every morning from the code). Changes: Tasks 21, 22, 24.
- (Owner, 2026-11-07: as recommended.) **I. The reader's contract in step one (R1, R2).** The design's "Testing" lists tests and mutations for R1 and R2, while step one has no reader. Recommended: step one honours the input side to the letter (Task 6's texts table, one record per distinct text per chain per day with every input field) and treats every promotion as having no reading ("fine print not read"); the output schema file, its validator and R2's accuracy table come with the reader in step two, since nothing in step one would read them. Changes: none in this plan.
- (Owner, 2026-11-07: as recommended.) **J. The site's name.** The design names the views, not the site; today's header says "One basket, five chains". Recommended working title: "Five chains, listed prices" (one constant, `shopper.words.SITE_NAME`). Changes: Task 15.
- (Owner, 2026-11-07: as recommended.) **K. Club-only from the fields (P5).** Recommended: `ClubID` codes 1 (club) and 2 (the chain's credit card) are shown as "club members only" and "the chain's card holders only", code 3 as "some customers only", each "from the chain's fields"; the club-only filter hides all three; its label names the chains whose files mark no restricted promotion that day ("from the chains' fields; Shufersal's files mark none" on a day when that is true of Shufersal alone), so the label never states what the day's files contradict. Changes: Tasks 3, 15, 18.
- (Owner, 2026-11-07: as recommended.) **L. The account's Lambda concurrency is 400, not 5** (`aws lambda get-account-settings`, 2026-11-07). The design keeps promotions inside the five extract runs partly because of 5 ("Build and hosting", Call 5). Recommended: build as approved; if the manual runs after the deploy measure Shufersal's extract run (prices, promotions, items) above about 600 s of its 900, a separate promotions mode per chain at 12:03 is cheap at 400, as a change on your word. Changes: none now.
- (Owner, 2026-11-07: as recommended.) **M. Smaller readings, each planned as stated:** (a) a P10 failure is emailed by pinging `/fail` after the upload, naming the chain and the field, since the design wants the page up and "an email, not a quiet zero"; (b) the 12:33 event keeps `"mode": "basket"` (renaming it touches the template, the docs and many tests for no change in behaviour; the docs call it the site run); (c) `basket.html` carries the site's header band and credit line, and the basket's method (B1 to B12, the list, the stores left out) becomes a section of `method.html`; (d) `basket.html` links an item to its product page only when the build has that page; (e) Node in CI for the behaviour tests of `search.js` (Task 17); (f) the hiring line reads "Built by Doron Reiffman" (LinkedIn, as the README links it), "How this is made", "Track record", "Code on GitHub" (https://github.com/doronreiffman/il-grocery-prices); (g) the check's "a chain's missing items table must be said on the page (P10's sentence)" is read as: every section of a chain whose promotions could not be read today carries P10's sentence (its items table is still written, Task 7), while a chain whose tables are missing for the run's own day stops the run (`MissingTable`), as a missing prices table stops the basket run today; the other reading, building without that chain, would also take it out of the basket's day.

## Where the design leaves room, this plan decides

From "Left to the builder", each settled here:

- **Package layout:** `src/shopper/` beside `basket`: `promofile`, `survey`, `promotions`, `deals`, `promos`, `items`, `extract`, `history`, `measures`, `forecast`, `freeze`, `score`, `record`, `words`, `product`, `search` (with `static/search.js`), `pages`, `siteday`, `build`, `check`, `guard`. The S3 adapters stay one per bucket: `basket.archive` and `basket.site` gain the new methods. The Lambda entry stays `basket.handler.handler`.
- **The tables' columns:** as Tasks 5 and 6 give them. One promotions row per link variant (the promotion's id, text and dates, the group and the item's fields); a row is "carried" by a store when that store's latest promotion file holds an identical row. One items row per (chain, GS1 barcode) listed at an included store that day.
- **The upload thread pool:** 16 workers (`basket.site.UPLOAD_WORKERS`).
- **Search:** normalisation strips `'`, `"`, geresh `׳` (U+05F3) and gershayim `״` (U+05F4), turns the five final letters into their plain forms (ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ), lower-cases Latin and collapses spaces; one piece per first letter of the normalised longest name, `search/<hex code point>.json`, split by second letter (`search/<hex>-<hex>.json`) when over 150,000 bytes, listed in `search/pieces.json`. Browse pages `browse/<hex code point>.html` and `browse/other.html`.
- **The look:** the basket page's style (`basket.page.STYLE`) with each page type's own rules added; product pages carry the base rules and their own only, to stay near the design's 12 KB estimate. The front page's filters are CSS only (radio and checkbox inputs with `:checked` sibling selectors), so `search.js` stays the one script.
- **P7 and P8 sentences** beyond the forms: as Task 15 gives them.
- **The record page's tables:** as Task 14's scorecard and Task 18 give them; intervals need at least two 14-day blocks (28 scored days) and show "too few days" before.
- **n0 = 30**, fixed now, before any chain's 30th day: a pair with a month of closed days takes half its weight from its own share.
- **Fixtures:** two new trimmed promotion fixtures (Osher Ad, Yochananof) from Task 2; every other trap is synthetic, built in the tests.
- **Test layout:** a test file per module (`tests/test_<module>.py`, prefixed `shop_` where a basket file has the name), a golden 90 days in `tests/shopper_golden.py`, Node behaviour tests in `tests/test_search_js.py`.
- **Not in step one:** opening and closing the gate (F9's owner's go and its 60-day closing rule) and the odds line are step three's; step one evaluates the gate's conditions and shows them, closed. A rescoring tool (the grade line's "a second file beside the first") waits for the first fix that needs one.
- **The day's promotion files:** each counted store's latest `PromoFull` of the day by the time in its name, as B1 takes price files; files of stores not counted are passed over unread and listed.
- **A missing past items table** (an extraction that never ran) is a hole for that chain-day; a missing items table for the run's own day stops the run (`MissingTable`), as a missing prices table does today.

## Global Constraints

- Branch `q22-shopper-site`, working copy `/Users/doronreiffman/Projects/il-grocery-prices-q22`, one commit per task, each message naming q22. Never push; no `gh`; no AWS write, no deploy, no upload (each is the owner's go, outside this plan). Read-only AWS (Task 2's sync) only after `aws sts get-caller-identity --profile flights-sam` shows account 137953273942 and user doron-admin. Before each commit, `git status`: only the task's files staged.
- `PY` below is `.venv/bin/python` where the working copy has one, else `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/python`. Commands run from the repo root.
- Test-first: a failing test before the code, for every rule.
- A named mutation in `scripts/mutation_check.py` for every rule, in the task that adds the rule: what the break does, then the group in brackets, `(q22 <group>)`, the groups as each task names them. A target constant per new module, as `BUILD = ("src/basket/build.py", ["tests/test_build.py"])` is written. Only pytest exit 1 counts as caught. An existing mutation whose text a change moves is re-pointed at the new text, never dropped (the script prints `STALE`).
- Every task's mutation step ends with `$PY scripts/mutation_check.py "q22 <group>" ...` over its groups and any name it re-pointed, then the staleness check. Expected: every one CAUGHT; `none stale`.
- **The staleness check** (reads, edits nothing, safe any time): `$PY -I -c "import importlib.util as u; s = u.spec_from_file_location('m', 'scripts/mutation_check.py'); m = u.module_from_spec(s); s.loader.exec_module(m); bad = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]; print(len(m.MUTATIONS), bad or 'none stale')"`. Expected: the count, then `none stale`.
- The mutation check edits files in place: nothing else runs from this checkout while it runs.
- Coverage floor 95% over `collector`, `src/basket` and `src/shopper` (Task 1 adds `--cov=src/shopper` to CI). Baseline, measured on this branch at 291e0c3 on 2026-11-07: `$PY -m pytest --cov=collector --cov=src/basket --cov-fail-under=95` passes 1,367 tests at 99.83%; 1,092 mutations, none stale.
- Test data never reads the clock: fixed times, `gzip.compress(..., mtime=0)`, a fake S3 clock in `MemoryArchive`. Every datetime aware; never a naive `astimezone()` (this Mac is Asia/Jerusalem, CI is UTC). Dates in the chains' files are Israel wall-clock with no zone: P3 compares their date parts only.
- Money and probabilities are exact: `Decimal` for money (written with two decimals, half up), `Fraction` for shares and blends, written to six decimals half up in the forecasts file; floats only inside the bootstrap.
- No new Python dependency. Node is a CI tool for one test file, pinned at 22.11.0.
- Fixtures under `tests/fixtures/` keep the real files' structure (trimming changes values only; a trimmed file is checked against the archived file it came from), at most three records of a kind a file, synthetic prices, names and barcodes. Raw files and Hebrew sample texts from the archive never enter the repo.
- Raw files are never published; only derived numbers, credited to the chains' files. The site's words: Task 15's lists, verbatim from the design.
- Nothing in the code deletes: no `delete_object`, no `s3:Delete*` in the role, no `--delete` in the scripts (question H). Archive writes of `forecasts/` and `scores/` are write-once and locked (`If-None-Match: *`, ten-year governance lock), as manifests are.
- Docs (this plan included) in plain words; no "we"; public docs never point at the owner's private notes.
- Implementers on the newest Opus (`opus`); every task review and re-review on the newest Opus too; the whole-branch review on Fable (`fable`), or the newest Opus while Fable is at its usage limit, the report naming the swap; a task still open after fix round 3 escalates to Fable (the owner's model rule of 2026-11-07). Subagents never run `gh` or push.
- Every AWS command in `docs/operations.md` names `--profile flights-sam --region il-central-1` (`tests/test_template.py` pins it).
- The design's values, copied, never re-derived: 30 and 90 days; 20 of 30 and 60 of 90; half the stores; the deal between ₪0.01 and twice the listed price; d + 1 to d + 14; t ≤ d − 14; more than 4 holes unscored; the 30th day of records; midnight ending day d, Israel time; 14-day blocks, 10,000 draws, a fixed seed; ten bins of width 0.1; the gate's 90 days, 95% intervals, calibration error 0.03, 1% and 0.10; 60 KB a product page; 150 KB an index piece; 30 days for noncurrent pages.

## Review Focus

1. **A chain changes its promotion format** (a new field, a missing one, a code never seen): that chain's promotions stop with an error naming the field, its prices and items still build, its sections say "Promotions from Carrefour's files could not be read today", the day counts as a hole for its outcomes, and the owner gets an email the same morning. Tests in Task 3 (`test_an_unknown_reward_type_stops_the_chain_naming_the_field`), Task 7 (`test_a_format_change_keeps_prices_and_items_and_names_the_field`) and Task 23 (`test_a_chains_promotions_error_publishes_then_pings_fail`).
2. **A day run twice, or late:** a same-day rerun after a failed upload publishes the archive's forecast bytes; a rerun whose forecasts differ stops before any upload; a run past the cutoff with nothing frozen writes none and the day shows as a gap; S3's time past the cutoff makes the day late however early the run thought it was. Tests in Task 12 (`test_a_rerun_with_the_same_content_publishes_the_archives_bytes`, `test_s3s_time_past_the_cutoff_makes_the_day_late`) and Task 23 (`test_a_rerun_after_a_failed_upload_publishes_the_frozen_bytes`).
3. **A hand build from a partly synced data folder:** fewer covered products, or a missing published site-day file: the guard refuses the upload (a published product page missing, a site-day file that is not a revision), nothing is deleted. Tests in Task 21 (`test_a_build_missing_a_published_product_page_is_refused`) and Task 22 (`test_publish_sh_deletes_nothing`).
4. **A chain's product name that looks like markup or a forbidden word** ("<b>", "FAKE", a quote, a line break): escaped inside its own span, the page still passes the check, and the same text unescaped fails it. Tests in Task 16 (`test_a_chains_name_is_escaped_in_its_own_span`) and Task 20 (`test_a_never_word_inside_a_chains_name_passes`, `test_markup_inside_a_chains_span_fails`).
5. **A lifecycle rule that reaches a record:** a prefix such as `s` or an empty one would expire old versions of `scores/` or `site-days/`. Expected: only the rebuilt pages' prefixes, each matching no record key. Test in Task 24 (`test_no_lifecycle_prefix_matches_a_record_key`).

## Where step one lands in AWS

Deploys, uploads and runs are the owner's, by hand, in this order (question D); none is a task of this plan. `docs/operations.md` gets the commands in Task 26.

- **The budget first:** the account's AWS Budget "My Monthly Cost Budget" ($5 a month, in no template) goes to $20, the owner's answer to the design's Q8, set by the owner in the console. Not a plan task.
- **Stack `il-grocery-prices`** (`sam build`, `sam deploy` with all eight parameters and `'BasketScheduleState=DISABLED'`): no new function, schedule, layer or log group. The change set should show `BasketFunction` (Modify: its code, now `src/` with `shopper`) and `BasketFunctionRole` (Modify: its inline policy, Task 24's grants); nothing else, unless a collector change committed since the last deploy. The 12:33 event is unchanged.
- **Stack `il-grocery-prices-site`** (`aws cloudformation deploy --template-file site-template.yaml ...`): `SiteBucket` (Modify, no replacement: `LifecycleConfiguration` added).
- **The first hand upload** (Mac): sync the past days and today read-only, extract each on the Mac, build, check, review, then `scripts/publish.sh` on the owner's go after the Nevo date check (`docs/terms.md`).
- **The backfill** (Lambda, on the owner's go): one `extract` run per chain for each day from 2026-11-01 to yesterday, so the archive holds the items tables the site run reads; then today's five extractions and one manual site run. Expected: `days/` and `site-days/` unchanged against the hand upload, the pages up, the measured seconds and memory noted in "Sizing".
- **Schedules on** (`'BasketScheduleState=ENABLED'`), on the owner's go.
- **Lambda concurrency:** 400 in il-central-1 (measured 2026-11-07), shared with the flight-board collector; step one's peak is five extractions at once.

## Cost (monthly; the design's figures, checked)

- **Lambda.** Promotions about 600 s a day at 2 GB: 600 × 2 × 30 = 36,000 GB-s. The site run 300 to 500 s at 2 GB: 18,000 to 30,000. In all 54,000 to 66,000 ("about 55,000 to 65,000"), beside the basket's measured 19,000. At $0.0000166667 per GB-s outside the free tier: $0.90 to $1.10, so $0 to $1.10 as the account sits at the free tier's edge. Worst case, six runs at 900 s: 6 × 900 × 2 × 30 = 324,000 GB-s, $5.40. All checked.
- **S3 writes.** 22,000 to 25,000 product pages a day plus about 100 other files: about 22,100 to 25,100 a day, 663,000 to 753,000 a month, $3.65 to $4.14 at $0.0055 per 1,000 ("$3.60 to $4.20"). Checked.
- **S3 reads.** The design's about 1,350 a day, $0.22 a month. This plan adds the items tables' reports (450 a day), one scoring summary per scored day (up to about 365 a day after a year), a listing of `p/` (about 25 calls a day) and a few heads: under $0.15 a month more, priced at the write rate as the design prices reads.
- **S3 storage.** The design's $0.01 for the site, $0.23 for old versions under the 30-day rule, about $0.15 a month after a year for tables, $0.04 for forecasts and scores: checked (300 MB × 30 days = 9 GB × $0.025 = $0.225; 12 months × $0.225 = $2.70 without the rule). If pages average 25 KB rather than 12 KB (the inline style block is 8.5 KB), old versions come to about $0.47.
- **Total:** about $4 to $6 a month in year one: low, $0 + $3.65 + $0.22 + $0.25 = $4.12; high, $1.10 + $4.14 + $0.22 + $0.43 = $5.89. With this plan's reads (up to $0.15) and pages of 25 KB (old versions $0.47, not $0.23), about $4.40 to $6.30. Worst case about $10.30 ($5.40 + $4.20 + $0.22 + about $0.45). The account's alarm moves to $20 (the design's Q8).

---

### Task 1: Promotion files read one link at a time

**Files:**
- Create: `src/shopper/__init__.py` (one-line docstring naming `docs/shopper-site.md`), `src/shopper/promofile.py`
- Modify: `src/basket/pricefile.py` (the gzip, ZIP and plain branches of `read_items` move into a public `bodies(name, data) -> list[bytes]`, which `read_items` calls); `.github/workflows/ci.yml` (`--cov=collector --cov=src/basket --cov=src/shopper`); `scripts/mutation_check.py`
- Test: `tests/test_promofile.py`

**Interfaces:**
- Consumes: `basket.pricefile.bodies`, `BadPriceFile`; `collector.payload.XML_STARTS`.
- Produces (in `shopper.promofile`):

```python
@dataclass(frozen=True)
class FieldSets:
    root: frozenset[str]        # <Root>'s child tags (ChainID, SubChainID, StoreID, BikoretNo, Promotions, ...)
    promotion: frozenset[str]   # a <Promotion>'s child tags, Groups included
    group: frozenset[str]       # a <Group>'s child tags, PromotionItems included
    item: frozenset[str]        # a <PromotionItem>'s child tags

@dataclass(frozen=True)
class Link:                     # one item of one group of one promotion; texts stripped, "" when empty
    promotion: Mapping[str, str]    # the promotion's fields, Groups left out
    group: Mapping[str, str]        # the group's fields, PromotionItems left out
    item: Mapping[str, str]

@dataclass
class Tally:
    promotions: int = 0; links: int = 0; dropped_promotions: int = 0; dropped_links: int = 0
    seen: dict[str, set[str]] = field(default_factory=dict)   # level -> every tag seen, for the survey

class PromotionFormatChanged(Exception): """P10: a field or code the chain's files are not known to carry."""

def read_links(name: str, data: bytes, keep: Callable[[Mapping[str, str]], bool], tally: Tally,
               known: FieldSets | None = None) -> Iterator[Link]: ...
```

- The rule: bodies as `pricefile.bodies` gives them (gzip, ZIP, plain, a BOM), each refused by `BadPriceFile` as price files are; `iterparse` with start and end events; a promotion's fields are its children before `Groups` (a field after `Groups` raises `PromotionFormatChanged`, `"<name>: <tag> after Groups"`); `keep` is asked once per promotion, when its `Groups` starts; a promotion not kept has its items counted in `dropped_links` and never built into links; every element is cleared once read. With `known`, each element's tag set must equal its level's: `"<name>: <level> fields changed: added [...], missing [...]"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_promofile.py`:
  - `test_each_fixture_gives_its_three_links`, over the Shufersal (`PromoFull7290027600007-000-878-…`), Rami Levy (`…-001-731-…`) and Carrefour (`…-001-472-…`) fixtures with `keep=lambda p: True`: three links; the first's `promotion["PromotionID"] == "900001"`, `group["GroupID"] == "1"`, `item["ItemCode"] == "2000000000046"`; Shufersal's `promotion["ClubID"] == "0 - כלל הלקוחות"` and `promotion["IsGiftItem"] == ""`.
  - `test_a_promotion_not_kept_is_counted_and_never_built`: a synthetic voucher (`AdditionalIsCoupon` 1) of 5,000 items between two kept promotions of one item each, `keep=lambda p: p["AdditionalIsCoupon"] != "1"` → two links; tally `promotions == 3`, `dropped_promotions == 1`, `dropped_links == 5000`, `links == 2`.
  - `test_a_voucher_of_100000_items_is_read_in_flat_memory`: plain XML of one 100,000-item voucher built before `tracemalloc.start()`; the read's peak under 16 MB (a tree kept whole takes several times that).
  - `test_a_field_after_groups_is_refused` → `PromotionFormatChanged` matching `"ClubID after Groups"`.
  - `test_known_field_sets_hold`: each fixture read with `known` equal to its own sets passes; `test_a_new_or_missing_field_is_refused`, parametrized over each level, a tag added and a tag removed → the message names the file, the level and the tag.
  - `test_text_is_stripped_and_an_empty_element_is_empty`, `test_a_zip_and_a_bom_read_alike`, `test_an_html_page_or_a_bad_gzip_is_a_bad_file` (`BadPriceFile`, the name first).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_promofile.py -q`. Expected: fails, `shopper` does not import.
- [ ] **Step 3: Implement** `bodies` in `basket.pricefile` (no change in what `read_items` returns) and `shopper.promofile` as above. Module docstring: the layouts, what is dropped as read and why (one Shufersal store's file of 2026-10-31 held 21,244 links, about three quarters of them two meal-card vouchers': the design's research sample, UNVERIFIED there, so say so), P10's field half.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass, `tests/test_pricefile.py` unchanged.
- [ ] **Step 5: Mutations**, `(q22 promo read)`, target `PROMOFILE`: "a dropped promotion's links built"; "dropped links not counted"; "keep asked of nothing" (every promotion kept); "a field after Groups taken"; "the promotion's fields not checked"; "a group's fields not checked"; "an item's fields not checked"; "the root's fields not checked"; "elements not cleared"; "text not stripped". Re-point any `PRICEFILE` mutation the move made stale. Run `$PY scripts/mutation_check.py "q22 promo read" "pricefile"`, then the staleness check. Expected: every one CAUGHT; `none stale`.
- [ ] **Step 6: Commit** `git add src/shopper src/basket/pricefile.py tests/test_promofile.py .github/workflows/ci.yml scripts/mutation_check.py && git commit -m "Shopper site: promotion files read one link at a time, vouchers counted and dropped as read (q22)"`.

### Task 2: The survey: each chain's promotion fields measured, two new fixtures, the readings recorded

**Files:**
- Create: `src/shopper/survey.py`; `tests/fixtures/ncr/PromoFull7290103152017-<rest of the archived name>` (Osher Ad) and `tests/fixtures/ncr/PromoFull7290803800003-<…>` (Yochananof), each trimmed from an archived file of the survey day
- Modify: `scripts/sync.sh` (the day's `PromoFull*` and `promofull*` files with the price files); `docs/operations.md` (a section "Measured for the shopper site", after "Measured on 2026-11-02"); this plan's "Deviations"; `scripts/mutation_check.py`
- Test: `tests/test_survey.py`

**Interfaces:**
- Consumes: `read_links` and `Tally` (Task 1); `basket.extract.day_files`; `basket.stores.day_store_list`, `read_stores`, `included`.
- Produces: `survey(raw_dir: Path, tables_dir: Path, slug: str, day: date) -> dict` and `python -m shopper.survey --data data --day YYYY-MM-DD [--chain SLUG]`, printing JSON per chain: the latest file per store and the stores passed over; each level's field sets and how many files carry each; value counts of `RewardType`, `ClubID`, `IsGiftItem`, `AdditionalIsCoupon`, `DiscountType`, `bIsWeighted`, and `MinPurchaseAmount` by group position; how often `IsGiftItem` equals `MinQty`; up to five `PromotionDescription`s per (field, value) for the eye, printed and never written to a file; distinct texts (chain, id, description, start, end); promotions listed before their start, and by how many days; the share of promotions carried by at least half the included stores (Shufersal's also by sub-chain, from its store list); links per store; coupons over 1,000 items; on percent-off links, how often `DiscountedPrice` agrees with the day's median price × (1 − rate/100) within ₪0.01 (the prices table read with DuckDB); the read's seconds and peak memory (`resource.getrusage`).

- [ ] **Step 1: Failing tests** in `tests/test_survey.py` on the three fixtures and synthetic files: `test_counts_each_stores_latest_file_once`, `test_counts_gift_codes_against_min_qty` (Rami Levy's fixture: 3 of 3 equal), `test_counts_promotions_listed_before_their_start` (a start one day after the day counts, one on the day does not), `test_share_carried_by_half_the_stores` (2 of 3 stores: carried; 1 of 3: not), `test_the_survey_writes_no_file` (the folder's file list before and after).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_survey.py -q`. Expected: fails on import.
- [ ] **Step 3: Implement** the survey and `sync.sh`'s two includes (`--include "chain=*/date=$day/PromoFull*" --include "chain=*/date=$day/promofull*"`). Run `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 4: Run it on two real days, read-only.** After the identity check, `sh scripts/sync.sh 2026-11-07` (a Saturday: full kinds) and `sh scripts/sync.sh 2026-11-05`; extract the prices tables (`PYTHONPATH=src $PY -m basket.extract …` per chain); `PYTHONPATH=src /usr/bin/time -l $PY -m shopper.survey --data data --day <day>` for each. Then `curl -sI https://d153udx05irk2f.cloudfront.net/index.html` and note whether a `Last-Modified` header comes through (design, step one's last measurement).
- [ ] **Step 5: The two fixtures.** From one Osher Ad and one Yochananof `PromoFull` of 2026-11-07 (under `data/raw/`): keep the root, three promotions and at most three items in all, every field and its layout as published; replace prices with synthetic ones, names with `מבצע לדוגמה N`, barcodes with `2000000000046`, `…053`, `…060`. Check the trimmed file's field sets against the archived file's (the survey's output for that file). `$PY -m pytest tests/test_fixtures.py -q` passes.
- [ ] **Step 6: Record and settle.** In `docs/operations.md`, "Measured for the shopper site": per chain, the figures above (no Hebrew sample text beyond a word or two quoted to show a meaning), and the Mac's seconds and peak for Shufersal's promotion read. In "Deviations": the constants Task 3 takes, each with its evidence: `KNOWN_FIELDS` per chain, `REWARD_TYPES`, `TARGET_CODES`, `GIFT_CODES` and the gift values seen per chain, the group rule for `MinPurchaseAmount`, and the percent-off agreement rate per chain (question C). **Checkpoint:** a finding that contradicts a design reading (question B) stops here for the owner's word; otherwise Task 3 goes on with these.
- [ ] **Step 7: Mutations**, `(q22 survey)`, target `SURVEY`: "every file of a store counted"; "gift code compared with MaxQty"; "a promotion starting on the day counted as before its start"; "half the stores not enough". Run `$PY scripts/mutation_check.py "q22 survey"`, then the staleness check.
- [ ] **Step 8: Commit** `git add src/shopper/survey.py tests/test_survey.py tests/fixtures/ncr scripts/sync.sh docs/operations.md docs/shopper-site-plan.md scripts/mutation_check.py && git commit -m "Shopper site: the promotion survey, Osher Ad's and Yochananof's promotion fixtures, and the readings of 2026-11-05 and 2026-11-07 (q22)"`.

### Task 3: Which promotions count, their conditions from the fields, and a format change stopping a chain (P3, P5, P10)

**Files:**
- Create: `src/shopper/promotions.py`
- Test: `tests/test_promotions.py`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `FieldSets`, `PromotionFormatChanged` (Task 1); Task 2's settled values.
- Produces (in `shopper.promotions`):

```python
KNOWN_FIELDS: dict[str, FieldSets]          # per chain, the fixtures' sets as Task 2 confirmed them
REWARD_TYPES = frozenset({"0", "1", "2", "3", "10"})   # with any Task 2 adds and the design reads
KINDS = {"1": "n_for_m", "10": "n_for_m", "2": "percent_off", "3": "fixed_price", "0": "none"}
TARGET_CODES = {"0": "none", "1": "club", "2": "chain_card", "3": "other"}
GIFT_VALUES: dict[str, frozenset[str]]       # per chain: every IsGiftItem value seen (Task 2), "" included
GIFT_CODES: dict[str, frozenset[str]]        # per chain: the values that mark a gift (Task 2)

def target(club_id: str) -> str              # the leading code of "0" or "0 - כלל הלקוחות"; P10 otherwise
def is_coupon(promotion: Mapping[str, str]) -> bool        # AdditionalIsCoupon == "1"
def is_gift(slug: str, promotion: Mapping[str, str]) -> bool   # P10 on a value outside GIFT_VALUES[slug]
def keep(slug: str) -> Callable[[Mapping[str, str]], bool]  # neither coupon nor gift: Task 1's `keep`
def kind(item: Mapping[str, str]) -> str     # KINDS; P10 on a RewardType outside REWARD_TYPES
def has_price_effect(item: Mapping[str, str]) -> bool   # False for a kind "none" link with no DiscountedPrice and no DiscountRate
def dates(promotion: Mapping[str, str]) -> tuple[date, date]   # the date parts of PromotionStartDateTime and PromotionEndDateTime
def in_day(promotion: Mapping[str, str], day: date) -> bool   # start <= day <= end (P3)
def min_spend(groups: Iterable[Mapping[str, str]]) -> Decimal | None   # the largest MinPurchaseAmount above 0, by Task 2's group rule
```

- P10's messages name the chain, the field and the value: `"carrefour: RewardType 7 not seen in the chain's files"`.

- [ ] **Step 1: Failing tests**: `test_club_id_as_a_bare_code_and_as_a_labelled_string` (`"0"`, `"0 - כלל הלקוחות"`, `"1"`, `"2 - כרטיס"` → none, none, club, chain_card); `test_an_unknown_club_code_stops_the_chain_naming_the_field`; `test_an_unknown_reward_type_stops_the_chain_naming_the_field`; `test_an_unknown_gift_value_stops_the_chain`; `test_a_coupon_is_not_kept`; `test_each_chains_gift_marking` (parametrized from Task 2's table; Rami Levy's 6, 2, 2 equal to `MinQty` as Task 2 reads them); `test_a_link_with_no_price_effect` (`RewardType` 0, no price fields → False; with `DiscountedPrice` → True); `test_in_day_boundaries` (start on the day, end on the day: in; end the day before, start the day after: out); `test_min_spend_from_a_second_group` (group 1 empty, group 2 `50.00` → 50.00; `0.00` and empty → None); `test_known_fields_are_each_fixtures` (each chain's `KNOWN_FIELDS` equals its fixture's sets as Task 1 reads them).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_promotions.py -q`. Expected: fails on import.
- [ ] **Step 3: Implement** as above; the module docstring gives P3, P5's field half and P10 in plain words with Task 2's evidence named.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 P3)`, `(q22 P5)`, `(q22 P10)`, target `PROMOTIONS`: "coupons kept"; "gifts kept"; "gift tested on IsGiftItem being set"; "a no-price link given an effect"; "a promotion ending on the day out"; "a promotion starting on the day out"; "club code read from the label's end"; "an unknown club code read as none"; "an unknown reward type read as none"; "an unknown gift value passed"; "min spend from the first group only"; "min spend of zero kept".
- [ ] **Step 6: Commit** `git add src/shopper/promotions.py tests/test_promotions.py scripts/mutation_check.py && git commit -m "Shopper site: which promotions count, their conditions from the chains' fields, and a format change stopping the chain (P3, P5, P10; q22)"`.

### Task 4: The deal price (P4)

**Files:** Create `src/shopper/deals.py`; Test `tests/test_deals.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `kind` (Task 3).
- Produces:

```python
AGREE = Decimal("0.01")      # question C
@dataclass(frozen=True)
class Deal:
    price: Decimal | None    # a unit's price (a kilogram's when weighed) when buying the least that qualifies; exact
    per: str                 # "unit" or "kg" (bIsWeighted 1)
    buy: Decimal             # N for "N for ₪M" (1.5 for a weighed 1.5 for ₪75), else 1
    valid: bool
    why: str | None          # when not valid: "no price in the fields", "the fields disagree",
                             # "not above ₪0.01", "not below twice the listed price", "no listed price"
def deal(item: Mapping[str, str], listed: Decimal | None) -> Deal
```

- The rule: fixed price, `DiscountedPrice`; percent off, listed × (1 − `DiscountRate`/100), with question C's check of `DiscountedPrice`; "N for ₪M", `DiscountedPrice` ÷ `MinQty`, `buy` = `MinQty`; then valid when above ₪0.01 and below twice the listed price (both exclusive). A deal that is not valid keeps its price when one was read, so a page can show it, and is never ranked.

- [ ] **Step 1: Failing tests**: `test_fixed_price` (Carrefour fixture 900001: 8.72, listed 10.90 → 8.72 a unit, valid); `test_percent_off_agrees_with_its_discounted_price` (900002: rate 20, listed 5.50 → 4.40, valid; `DiscountedPrice` 4.42 → "the fields disagree"); `test_n_for_m_is_m_over_n` (Rami Levy 900001: 6 for 8.72 → 8.72/6 exactly, buy 6); `test_a_weighed_two_for_100_stored_as_1_5_for_75_is_50_a_kilogram`; `test_the_range_is_exclusive` (0.01 out, 0.02 in; twice the listed price out, an agora under in); `test_percent_off_without_a_listed_price_has_no_price`; `test_no_price_fields`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_deals.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 P4)`, target `DEALS`: "n for m read as m"; "n for m read as m times n"; "percent off read as the rate"; "the discounted price not checked"; "agreement within a shekel"; "range lower bound inclusive"; "range upper bound inclusive"; "range against the deal, not the listed price"; "weighed priced per unit"; "MinQty read as a whole number".
- [ ] **Step 6: Commit** `git add src/shopper/deals.py tests/test_deals.py scripts/mutation_check.py && git commit -m "Shopper site: the deal price from the chains' fields and its checks (P4; q22)"`.

### Task 5: The promotions table, counted at the stores P2 counts (Call 7)

**Files:** Create `src/shopper/promos.py`; Modify `src/basket/extract.py` (`day_files(raw_dir, slug, day, kind="PriceFull")`; re-point any extract mutation the change moves); Test `tests/test_promos.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: Tasks 1 and 3; `basket.extract.day_files`, `store_key`; `basket.duck.connect`.
- Produces:

```python
@dataclass(frozen=True)
class PromoReport:
    slug: str; day: str
    counted: int                 # P2's stores: included, with a price file that counts that day
    files: list[str]; passed_over: list[str]   # read (each counted store's latest PromoFull); not read
    promo_files: int             # counted stores with a promotion file
    promotions: int; coupons: int; gifts: int; dropped_links: int; no_price_links: int; expired: int
    before_start: int            # kept promotions whose start is after the day
    rows: int
def promotions_path(tables_dir: Path, slug: str, day: date) -> Path   # tables/promotions/chain=<slug>/date=<day>/promotions.parquet
def extract_promotions(raw_dir: Path, slug: str, day: date, counted: set[str], tables_dir: Path) -> PromoReport
```

- Columns of `promotions.parquet`, one row per link variant: `promotion_id`, `description`, `start_at`, `end_at` (as published), `start`, `end` (DATE), `update_time`, `target` (Task 3's word), `min_spend` (DECIMAL(12,2), the promotion's, Task 3), `group_id`, `code`, `code_norm`, `gs1`, `reward_type`, `kind`, `min_qty`, `max_qty`, `discount_rate`, `discounted_price` (as published), `weighed` (BOOLEAN), `fields` (JSON text: the promotion's, the group's and the item's fields), `stores` (counted stores carrying the identical row), `promotion_stores` (counted stores carrying the promotion at all), `chain_wide` (`stores` × 2 ≥ `counted`, P3). Links of coupons and gifts are dropped as read (Task 1's `keep`), links with no price effect and promotions ended before the day are counted and dropped, promotions starting after the day are kept (F2). The links go through a CSV in a temporary folder under the table's folder and DuckDB groups them, as `basket.extract` does for prices. `report.json` beside it. A `PromotionFormatChanged` is raised, not caught: Task 7 catches it.

- [ ] **Step 1: Failing tests**: `test_each_fixture_gives_its_rows` (the three fixtures and Task 2's two, one counted store each); `test_a_row_in_one_of_three_stores_is_at_some_stores` (and in two of three: chain-wide; two of four: chain-wide); `test_files_of_stores_not_counted_are_not_read` (a Shufersal store whose price file is named under sub-chain 005, as store 779's was on 2026-11-02, while its promotion file is named under 000: passed over; store 413: passed over); `test_each_stores_latest_file_is_read`; `test_a_voucher_of_thousands_of_items_is_counted_not_kept`; `test_an_expired_promotion_is_counted_and_a_future_one_kept`; `test_hebrew_quotes_commas_and_line_breaks_round_trip`; `test_a_day_with_no_files_writes_the_columns`; `test_a_format_change_raises_naming_the_field`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_promos.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 promotions table)`, target `PROMOS`: "stores counted per file, not per store"; "chain-wide at a third of the stores"; "chain-wide counted over every store, not the counted ones"; "a store not counted read"; "an earlier file of a store read"; "expired promotions kept"; "future promotions dropped"; "no-price links kept"; "rows told apart by their store".
- [ ] **Step 6: Commit** `git add src/shopper/promos.py src/basket/extract.py tests/test_promos.py scripts/mutation_check.py && git commit -m "Shopper site: the day's promotions table, each row counted at the stores P2 counts (P3, Call 7; q22)"`.

### Task 6: The items table and the reader's input (P1's day test, P2, the day's promotions)

**Files:** Create `src/shopper/items.py`; Test `tests/test_items.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: Tasks 3 to 5; `basket.rules.open_day`, `apply_filters`, `stores_with_file_keys`, `chain_day`; `basket.units.normal_size`.
- Produces:

```python
HORIZON = 14
@dataclass(frozen=True)
class ItemsReport:
    slug: str; day: str; included: int; with_file: int; hole: bool   # B8: with_file * 2 < included
    counted: int; promo_files: int; promo_hole: bool                  # promo_files * 2 < counted, or promotions unread
    promotions_error: str | None; items: int; chain_wide: int; on_promotion: int; valid_deals: int; texts: int
    promotions: dict | None                                           # the PromoReport's counts
def items_path(tables_dir: Path, slug: str, day: date) -> Path   # tables/items/chain=<slug>/date=<day>/items.parquet
def texts_path(tables_dir: Path, slug: str, day: date) -> Path   # tables/promotions/chain=<slug>/date=<day>/texts.parquet
def write_items(tables_dir: Path, slug: str, day: date, included: set[str], excluded_sub_chains: frozenset[str],
                promo: PromoReport | None, promotions_error: str | None) -> ItemsReport
```

- Columns of `items.parquet`, one row per GS1 barcode listed above ₪0.01 at an included store that day: `code` (normalised), `name` (the chain's most common name that day; a tie to the longest, then the first in code-point order), `size_amount`, `size_kind` (B7's most common readable size, or NULL), `listed` (P2: B5's median, exact, DECIMAL(12,3)), `low`, `high`, `listing` (stores listing it), `chain_wide` (B6: `listing` × 2 ≥ `with_file`), `on_promotion` (BOOLEAN: a chain-wide row of the promotions table in the day with a price effect, valid or not; NULL when promotions are unread), `next_start` (DATE: the earliest start in d + 1 to d + 14 among chain-wide rows starting after the day), `promotions` (a list of structs, every promotion row on the item in the day or starting after it: `promotion_id`, `description`, `start`, `end`, `kind`, `buy`, `price`, `per`, `valid`, `why`, `target`, `min_spend`, `stores`, `chain_wide`). Deals by Task 4 with `listed`. `report.json` beside it.
- `texts.parquet` (the reader's input, design "What the site needs from the reader"): one row per distinct (`promotion_id`, `description`, `start_at`, `end_at`): `chain`, those four, `update_time`, `fields` (JSON: the promotion's fields, its groups and items), `listed` (JSON: each of its items' `listed` that day, by code), `stores` (`promotion_stores`).

- [ ] **Step 1: Failing tests** over a synthetic two-store chain day and the golden day of `tests/test_build.py`: `test_the_median_is_the_baskets` (for the golden day's three codes, `listed`, `low`, `high`, `listing` equal `basket.rules.chain_prices`'s); `test_internal_codes_get_no_row`; `test_chain_wide_is_half_the_stores_with_a_file` (2 of 4 yes, 1 of 3 no); `test_a_chain_day_under_half_its_stores_is_a_hole`; `test_the_name_is_the_most_common_then_the_longest`; `test_on_promotion_counts_a_chain_wide_promotion_whose_price_is_not_read`; `test_a_promotion_at_some_stores_is_not_on_promotion`; `test_next_start_is_within_fourteen_days` (d + 14 yes, d + 15 no); `test_unread_promotions_make_a_promotion_hole_and_no_promotion_rows`; `test_texts_carry_every_input_field_and_the_listed_prices`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_items.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 items)`, `(q22 P1)`, `(q22 P2)`, target `ITEMS`: "chain-wide over included stores, not stores with a file"; "chain-wide at a third"; "a hole at half"; "placeholders kept in the median"; "excluded sub-chain rows counted"; "on promotion only when the deal is valid"; "at some stores counted as on promotion"; "next start fifteen days out"; "next start of a promotion in the day"; "unread promotions not a hole"; "texts without listed prices".
- [ ] **Step 6: Commit** `git add src/shopper/items.py tests/test_items.py scripts/mutation_check.py && git commit -m "Shopper site: the day's items table and the reader's input table (P1, P2; q22)"`.

### Task 7: The extract mode writes prices, promotions and items

**Files:** Create `src/shopper/extract.py`; Modify `src/basket/archive.py`, `src/basket/handler.py` (`_extract`), `scripts/mutation_check.py`; Test `tests/test_shop_extract.py`, `tests/test_archive.py`, `tests/test_basket_handler.py`.

**Interfaces:**
- Consumes: `basket.extract.extract`, `basket.stores.day_store_list`, `read_stores`, `included`, `basket.chains.EXCLUDED`, `basket.rules`; Tasks 5 and 6.
- Produces:

```python
# shopper.extract
@dataclass(frozen=True)
class ChainDayReport:
    prices: ExtractReport; promotions: PromoReport | None; items: ItemsReport
    seconds: dict[str, float]          # "prices", "promotions", "items"
def extract_chain_day(raw_dir: Path, slug: str, day: date, tables_dir: Path,
                      timer: Callable[[], float] = time.perf_counter) -> ChainDayReport
# python -m shopper.extract --data data --day YYYY-MM-DD [--chains ...]

# basket.archive._Archive
def day_file_keys(self, slug, day, kind: str) -> list[str]    # day_price_file_keys becomes day_file_keys(..., "PriceFull")
def fetch_raw(self, slug, day, raw_dir, kinds=("PriceFull",)) -> list[str]
TABLES = {"prices": ("prices.parquet", "report.json"),
          "promotions": ("promotions.parquet", "texts.parquet", "report.json"),
          "items": ("items.parquet", "report.json")}
def put_tables(self, slug, day, tables_dir) -> list[str]       # every file of the three, plain
```

- The counted stores (Call 7) are the chain's included stores with a price file that counts that day: `basket.rules.stores_with_file_keys` over the day's prices table, as the basket counts them. A missing store list raises `basket.build.NoStoreList`. A `PromotionFormatChanged` is caught: the promotions table is not written, the items table is (with `promotions_error`), the error is logged at ERROR, and the run goes on. The handler's extract summary keeps its keys and adds `promotions` (Task 5's counts), `promotions_error`, `items`, `chain_wide`, `promotion_seconds`, `items_seconds` (`seconds` stays the prices extraction's, as the docs read it).

- [ ] **Step 1: Failing tests**: `test_extract_chain_day_writes_the_three_tables` (the golden day with one promotion file per store); `test_a_format_change_keeps_prices_and_items_and_names_the_field`; `test_no_store_list_stops_the_chain`; in `tests/test_archive.py`, `test_day_file_keys_of_each_kind` (lower-case `promofull` names and conflict copies included) and `test_put_tables_puts_every_file_plain`; in `tests/test_basket_handler.py`, `test_extract_puts_the_three_tables_and_reports_them` (each slug) and `test_the_extract_summary_names_a_promotions_error`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_extract.py tests/test_archive.py tests/test_basket_handler.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass. The existing handler and archive tests pass, re-pointed where a name moved.
- [ ] **Step 5: Mutations**, `(q22 extract)`: "promotion files not fetched"; "a format change stops the prices"; "a format change writes no items"; "the items table not put"; "the promotions error not in the summary"; re-point the archive's "price files of another kind fetched" and its kin.
- [ ] **Step 6: Commit** `git add src/shopper/extract.py src/basket/archive.py src/basket/handler.py tests/test_shop_extract.py tests/test_archive.py tests/test_basket_handler.py scripts/mutation_check.py && git commit -m "Extract mode: a chain's day gives its prices, promotions and items tables; a promotion format change leaves the prices and items standing (q22)"`.

### Task 8: History and coverage: 90 days read, the covered registry, the windows (P1, Call 10, P6)

**Files:** Create `src/shopper/history.py`; Modify `src/basket/archive.py` (`fetch_items(slug, day, tables_dir) -> bool`, `fetch_history(day, tables_dir) -> list[str]`, `fetch_covered(day, tables_dir) -> date | None`, `put_covered(day, tables_dir) -> str`); Test `tests/test_history.py`, `tests/test_archive.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: Task 6's tables.
- Produces:

```python
READ_DAYS = 90
@dataclass(frozen=True)
class Point:
    day: date; listed: Decimal | None; low: Decimal | None; high: Decimal | None; listing: int
    chain_wide: bool; on_promotion: bool | None; next_start: date | None; promotions: tuple[dict, ...]
@dataclass(frozen=True)
class ChainDay:
    slug: str; day: date; present: bool; hole: bool; promo_hole: bool; promotions_error: str | None
    included: int; with_file: int
    @property
    def record(self) -> bool: ...      # present and not a hole
@dataclass(frozen=True)
class Pair: slug: str; code: str; points: dict[date, Point]     # only days with a row
@dataclass(frozen=True)
class Covered:
    code: str; title: str; names: dict[str, str]; size: tuple[Decimal, str] | None
    first_covered: date; last_chain_wide: dict[str, date]
@dataclass(frozen=True)
class Window: days: int; since: date | None; listed: tuple[Decimal, ...]; short: bool
class History:
    day: date; chain_days: dict[tuple[str, date], ChainDay]
    def pairs(self) -> Iterator[Pair]          # by code, then slug; streamed from DuckDB
    def record_days(self, slug: str) -> int    # chain-days with a record up to the day
def load(tables_dir: Path, day: date, slugs: Sequence[str]) -> History   # days day-90..day; MissingTable for the day's own
def covered(history: History, previous: Path | None, out: Path) -> dict[str, Covered]   # Call 10 (question G)
def window(pair: Pair, chain_days, day: date, length: int) -> Window      # P6
```

- P6: the window is the `length` days ending the day before `day`, counting the days with a listed price at the chain on a chain-day with a record; short when fewer than 20 of 30 or 60 of 90; `since` the first such day. `covered`: a product is covered when chain-wide at some chain on some day read; the registry carries every product the previous registry held, with its names and last chain-wide days; written to `tables/covered/date=<d>/covered.parquet`. `fetch_covered` takes the latest registry before the day.

- [ ] **Step 1: Failing tests**: `test_the_days_own_items_table_is_required`; `test_a_missing_earlier_table_is_a_hole`; `test_a_hole_day_has_no_record`; `test_later_days_are_not_read` (a table of day + 1 present: the same history); `test_ninety_one_days_are_read_and_no_more`; `test_covered_is_chain_wide_somewhere_once` and `test_a_product_stays_covered_after_the_read_window` (Call 10); `test_the_window_ends_the_day_before` (d − 30 in, d out); `test_short_windows` (19 and 20 of 30; 59 and 60 of 90); `test_a_window_skips_holes_and_days_not_listed`; archive tests for the new fetches.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_history.py tests/test_archive.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 history)`, `(q22 P1)`, `(q22 P6)`: "the day's own table optional"; "a missing earlier table read as no promotion"; "a hole day counted"; "a later day read"; "ninety days read, not ninety-one"; "covered needs every chain"; "the registry not carried"; "the window takes the day itself"; "a short 30-day window at 21"; "a short 90-day window at 61".
- [ ] **Step 6: Commit** `git add src/shopper/history.py src/basket/archive.py tests/test_history.py tests/test_archive.py scripts/mutation_check.py && git commit -m "Shopper site: 90 days of items read, the covered registry carried day to day, and the 30- and 90-day windows (P1, P6, Call 10; q22)"`.

### Task 9: The measured facts: the gap, the promotion history, the front page's test (P7, P8)

**Files:** Create `src/shopper/measures.py`; Test `tests/test_measures.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `Pair`, `window`, `Deal`.
- Produces:

```python
MIN_FRONT_DAYS = 20
@dataclass(frozen=True)
class Change: day: date; before: Decimal; after: Decimal
@dataclass(frozen=True)
class Gap:
    deal: Decimal; median30: Decimal; below: Decimal; percent: int   # median30 - deal; whole percent, half up
    low30: Decimal; low90: Decimal; at_or_below: int                 # days of the 90 listed at or below the deal
    window30: Window; window90: Window; changes: tuple[Change, ...]
@dataclass(frozen=True)
class Run: start: date; end: date
def gap(deal: Decimal, pair, chain_days, day) -> Gap | None      # None with no day of records in 30
def depth(gap: Gap) -> Decimal                                     # (median30 - deal) / median30
def on_front(deal: Deal, chain_wide: bool, pair, chain_days, day) -> bool
def runs(pair, chain_days, day) -> list[Run]                       # over P6's 90-day window
def gaps(runs: Sequence[Run]) -> list[int]                         # days strictly between runs
def days_since(runs: Sequence[Run], day: date) -> int | None
def promotion_days(pair, chain_days, day) -> tuple[int, int]       # (on a chain-wide promotion, with records)
```

- The rules: the 30-day median is the median of the window's daily listed prices (an even count, the mean of the two middle); a change is a pair of consecutive days with records whose prices differ, the later in the 30-day window; the front page's test (the design's Q3(b)): chain-wide, valid, at least 20 days of records in the 90, the deal below every listed price of those days. A run is a maximal sequence of consecutive days with records on promotion; a day without a record neither extends nor breaks it.

- [ ] **Step 1: Failing tests**: `test_the_designs_example` (page day 20 November 2026; listed 10.90 every day from 22 August to 27 October and 11.90 from 28 October; deal 7.90 → `median30` 11.90, `below` 4.00, 34%, `low30` and `low90` 10.90, 0 days at or below, one change, 10.90 → 11.90 on 28 October); `test_depth`; `test_the_front_page_needs_twenty_days` (19 no, 20 yes); `test_a_deal_equal_to_the_90_day_low_is_not_on_the_front_page`; `test_a_price_raised_before_the_promotion_does_not_lift_the_low` (7.90 for 60 days, 11.90 for 14, deal 7.90 → not on the front page); `test_an_invalid_or_some_stores_deal_is_not_on_the_front_page`; `test_a_hole_inside_a_run_does_not_break_it`; `test_a_day_off_promotion_breaks_a_run`; `test_gaps_and_days_since`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_measures.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 P7)`, `(q22 P8)`, `(q22 front)`: "median of the 90 days"; "percent rounded down"; "at or below counted as below"; "a change before the window counted"; "front page at or below the low"; "front page without the twenty days"; "front page over the 30-day low"; "a hole breaks a run"; "gaps counted with their ends"; "days since from the run's start".
- [ ] **Step 6: Commit** `git add src/shopper/measures.py tests/test_measures.py scripts/mutation_check.py && git commit -m "Shopper site: the deal against its listed prices, the promotion history and the front page's test (P7, P8; q22)"`.

### Task 10: Outcomes, who gets a forecast, inputs pinned to the day (F1, F2, F3)

**Files:** Create `src/shopper/forecast.py` (first part); Test `tests/test_forecast.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
MAX_HOLES = 4; FIRST_RECORD_DAY = 30; TARGET_VERSION = "1"   # HORIZON (14) is shopper.items'
@dataclass(frozen=True)
class Outcome: value: int | None; holes: int; first_day: date | None; promotion_id: str | None
def outcome(pair: Pair, chain_days, day: date) -> Outcome   # F1 over day+1..day+14 at the pair's chain; a promo hole or a missing table is a hole; > 4 holes: value None
def eligible(pair: Pair, chain_days, day: date) -> str      # "yes", "not_chain_wide", "on_promotion", "starts_soon" (F2, Call 22)
def closed_days(pair: Pair, chain_days, day: date) -> list[tuple[date, Outcome]]   # t in day-90..day-14, eligible, at most 4 holes (question F (b), (c))
```

- `first_day` and `promotion_id`: the first day in the window on a chain-wide promotion and its smallest `PromotionID` by number (F7's evidence).

- [ ] **Step 1: Failing tests**: `test_a_promotion_on_day_14_counts_and_on_day_15_does_not`; `test_a_promotion_on_the_day_itself_does_not_count`; `test_an_at_some_stores_promotion_does_not_count`; `test_a_coupon_never_reaches_the_outcome` (a coupon is not in the table); `test_four_holes_score_and_five_do_not`; `test_who_gets_a_forecast` (each of the four answers); `test_t_equal_to_d_minus_14_is_closed_and_d_minus_13_is_not`; `test_later_days_change_nothing` (the same answers with and without points after d, F3).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_forecast.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 F1)`, `(q22 F2)`, `(q22 F3)`: "the horizon fifteen days"; "the day itself in the window"; "at some stores counted"; "five holes scored"; "a forecast for an item on promotion"; "a forecast for an item starting soon"; "a forecast at some stores"; "a closed day at d − 13"; "a day after d read".
- [ ] **Step 6: Commit** `git add src/shopper/forecast.py tests/test_forecast.py scripts/mutation_check.py && git commit -m "Shopper site: the forecast's target, who gets a forecast, and inputs pinned to the day (F1 to F3; q22)"`.

### Task 11: The model, the two baselines and the forecasts file (F4, F5)

**Files:** Modify `src/shopper/forecast.py`; Test `tests/test_forecast.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
MODEL_VERSION = "1"; N0 = 30; DAYS_SINCE_CAP = 60; A_MIN_DAYS = 20
@dataclass(frozen=True)
class Forecast:
    slug: str; code: str; p: Fraction; a: Fraction; b: Fraction; b_says: bool
    days_since: int | None; n: int; a_from: str          # "pair" or "chain"
def forecasts(history: History, day: date) -> list[Forecast]   # chains with at least 30 days of records; sorted by chain, code
COLUMNS = ("chain", "barcode", "p_model", "p_a", "p_b", "b_says", "days_since", "n", "a_from",
           "model_version", "target_version", "n0", "code_sha")
def forecasts_csv(rows: Sequence[Forecast], code_sha: str) -> bytes    # gzip.compress(..., mtime=0); fractions to six decimals, half up
```

- The rules, F4 and F5 with question F: per chain, the hazard is the share of outcome 1 over its pairs' closed days with the same `days_since` bucket (0 to 60, "60 or more" at 60, and none); A is the pair's share over its closed days, the chain's share with fewer than 20; p = w × A + (1 − w) × hazard, w = n ÷ (n + 30); B says yes when, with two or more runs before the day, the last run's end plus the days from the end of the run before it to the start of the last run falls in d + 1 to d + 14; B's probability is the chain's share over its closed days on which B gave the same answer.

- [ ] **Step 1: Failing tests**: `test_the_hazard_by_days_since` (a hand-built chain of three pairs); `test_days_since_over_60_is_60`; `test_a_falls_back_to_the_chain_under_20_days`; `test_the_blend_weight_is_n_over_n_plus_30`; `test_b_says_yes_when_the_last_gap_repeats_in_the_window`; `test_b_scored_at_its_calibrated_rate`; `test_no_forecast_before_the_30th_day_of_records`; `test_the_file_names_the_versions_n0_and_the_code` and `test_the_file_is_sorted_and_its_bytes_reproducible` (two calls, the same bytes, gzip header time 0); `test_golden_forecasts_are_pinned_to_the_version_name` (Call 19: a fixed history's rows stored in the test under `"1"`; a model version the test does not hold fails with "a new version needs its golden rows").
- [ ] **Step 2: Run** `$PY -m pytest tests/test_forecast.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 F4)`, `(q22 F5)`: "n0 of 3"; "the weight on the hazard"; "days since uncapped"; "the hazard pooled over every chain"; "A from the pair under 20 days"; "A over all days, not closed ones"; "B with one run"; "B's gap from the runs' starts"; "B scored as a bare yes or no"; "probabilities to two decimals"; "rows unsorted"; "the version not in the file".
- [ ] **Step 6: Commit** `git add src/shopper/forecast.py tests/test_forecast.py scripts/mutation_check.py && git commit -m "Shopper site: the version 1 model, its two rules of thumb and the forecasts file (F4, F5; q22)"`.

### Task 12: The daily freeze and the ledger (F6)

**Files:** Create `src/shopper/freeze.py`; Modify `src/basket/archive.py` (`put_frozen`, `last_modified`, `frozen_days`; `MemoryArchive(s3_clock=None)`: an S3 time per key, the put's `now` unless a clock is given; `S3Archive.last_modified` through `head_object`); Test `tests/test_freeze.py`, `tests/test_archive.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
ISRAEL = ZoneInfo("Asia/Jerusalem")
LEDGER_HEADER = b"day,sha256,frozen_at\n"
class ForecastsDiffer(Exception): ...
@dataclass(frozen=True)
class Frozen:
    day: date; body: bytes; sha256: str; frozen_at: datetime; on_time: bool
    status: str               # "frozen" (written now), "same" (already there), "late" (written, S3's time past the cutoff)
def cutoff(day: date) -> datetime                       # midnight ending the day, Israel time, aware
def archive_key(day: date) -> str                       # forecasts/date=<d>/forecasts.csv.gz
def site_key(day: date) -> str                          # forecasts/<d>.csv.gz
class ArchiveFreezer:                                   # the Lambda's (question D)
    def __init__(self, archive, now: datetime): ...
    def freeze(self, day: date, body: bytes) -> Frozen | None   # None: past the cutoff and none stored
    def frozen(self, day: date) -> Frozen | None
    def put_scores(self, day: date, body: bytes) -> None        # Task 13
    writes = True                                       # the build scores and freezes only through a freezer that writes
class ReadOnlyFreezer:                                  # the Mac's: reads data/forecasts and data/scores, writes nothing
    writes = False
    def __init__(self, data_dir: Path): ...
    def freeze(self, day: date, body: bytes) -> Frozen | None   # the synced file as status "same", else None
    def frozen(self, day: date) -> Frozen | None
def ledger(published: bytes | None, frozen: Frozen) -> bytes    # the published ledger plus the day's line when absent
```

- The rules (question E): an archive object for the day is compared by its decompressed CSV: the same gives `status="same"` with the archive's bytes and S3 time; different raises `ForecastsDiffer` naming the day and both SHA-256s. None stored and `now` at or past the cutoff: no write, `None`. Else a locked, write-once put, then S3's time read back: `on_time` when it is before the cutoff. The ledger's line is `<day>,<sha256 of the gz bytes>,<S3 time, UTC, ISO with Z>`; a published ledger holding another line for the day is refused (`ValueError`).

- [ ] **Step 1: Failing tests**: `test_cutoff_is_midnight_israel_time` (2026-11-07 → 2026-11-07T22:00Z; 2026-10-24, the night summer time ends → 2026-10-24T21:00Z; 2026-10-25 → 2026-10-25T22:00Z); `test_a_first_freeze_is_written_once_and_locked`; `test_a_rerun_with_the_same_content_publishes_the_archives_bytes` (the archive's bytes compressed at another level: still "same"); `test_a_rerun_with_other_content_raises_naming_both_hashes`; `test_past_the_cutoff_nothing_stored_writes_none`; `test_past_the_cutoff_with_a_stored_file_publishes_it`; `test_s3s_time_past_the_cutoff_makes_the_day_late` (`now` 23:59:59 Israel time, the S3 clock 00:00:01); `test_the_ledger_grows_by_one_line` and `test_the_ledger_refuses_another_line_for_a_day`; `test_the_read_only_freezer_never_writes`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_freeze.py tests/test_archive.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 F6)`: "the cutoff in UTC"; "the cutoff a day late"; "on time by the writer's clock"; "a second file written"; "differing content published"; "gzip bytes compared"; "a write past the cutoff"; "a stored file refused past the cutoff"; "the ledger rewritten"; "the ledger's hash of the CSV, not the published bytes"; "a freeze put plain".
- [ ] **Step 6: Commit** `git add src/shopper/freeze.py src/basket/archive.py tests/test_freeze.py tests/test_archive.py scripts/mutation_check.py && git commit -m "Shopper site: each day's forecasts frozen once, write-once and locked, on time by S3's clock, and the ledger that only grows (F6; q22)"`.

### Task 13: Scoring (F7)

**Files:** Create `src/shopper/score.py`; Modify `src/basket/archive.py` (`put_scores`, `scored_days`, `put_summary`, `fetch_summaries`), `src/shopper/freeze.py` (`ArchiveFreezer.put_scores`: locked, write-once); Test `tests/test_score.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ChainSummary:
    forecasts: int; scored: int; unscored: int; outcome_1: int
    sq_model: Decimal; sq_a: Decimal; sq_b: Decimal                  # sums of (p - outcome)^2 over the scored
    bins: tuple[tuple[int, Decimal, int], ...]                      # ten: count, sum of p, outcomes 1
@dataclass(frozen=True)
class DaySummary:
    day: date; frozen_at: datetime; on_time: bool; model_version: str; target_version: str
    by_chain: dict[str, ChainSummary]
def due(frozen_days: Iterable[date], scored_days: Iterable[date], day: date) -> list[date]   # frozen, t <= day-14, unscored; oldest first
def scores_csv(frozen: Frozen, history: History) -> bytes    # each forecast row, then outcome, holes, first_day, promotion_id, unscored
def summarize(scores: bytes, frozen: Frozen) -> DaySummary
def summary_json(summary: DaySummary) -> bytes                 # tables/scored/date=<t>/summary.json, plain, derived
```

- Scored rows use the frozen file's six-decimal strings as `Decimal`. `scores/date=<t>/scores.csv.gz` in the archive (locked, write-once) and `scores/<t>.csv.gz` on the site carry the same bytes.

- [ ] **Step 1: Failing tests**: `test_model_and_baselines_are_scored_on_the_same_rows`; `test_more_than_four_holes_is_unscored_and_counted`; `test_the_evidence_is_the_first_day_and_its_smallest_promotion_id`; `test_a_missed_scoring_is_done_by_the_next_build` (`due` with a gap of three days); `test_a_late_days_summary_is_not_on_time`; `test_the_summary_recomputes_from_the_published_file`; `test_bins_are_tenths_with_1_in_the_last`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_score.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 F7)`: "scored at d + 13"; "the model scored on its own rows"; "five holes scored"; "an unscored row counted in the Brier"; "the latest evidence day"; "a scored day scored again"; "bin edges at 0.05".
- [ ] **Step 6: Commit** `git add src/shopper/score.py src/shopper/freeze.py src/basket/archive.py tests/test_score.py scripts/mutation_check.py && git commit -m "Shopper site: each frozen day scored 14 days later, with each outcome's evidence (F7; q22)"`.

### Task 14: The record's numbers: intervals, calibration, the gate, the scorecard (F8, F9, F11)

**Files:** Create `src/shopper/record.py`; Test `tests/test_record_numbers.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
BLOCK = 14; DRAWS = 10_000; SEED = 20261107; GATE_DAYS = 90
CAL_MAX = Decimal("0.03"); BIN_SHARE = Decimal("0.01"); BIN_OFF = Decimal("0.10")
@dataclass(frozen=True)
class Interval: low: float; high: float
def brier(summaries, slug: str | None = None) -> tuple[Decimal, Decimal, Decimal] | None   # daily means, then over days
def intervals(summaries, slug=None) -> dict[str, Interval] | None   # "model_minus_a", "model_minus_b", "skill_a", "skill_b"; None under 28 days
def calibration(summaries, slug=None) -> tuple[list[dict], Decimal]  # ten bins (mean p, share of 1, count), error
@dataclass(frozen=True)
class Gate: slug: str; conditions: dict[str, bool]; reasons: list[str]; open: bool   # open is False in step one
def gate(summaries, slug: str) -> Gate
def scorecard(summaries) -> dict      # F11: per chain, per month, in all, per model version; the gate per chain
```

- The rules: moving blocks of 14 consecutive scored days in date order, drawn with `random.Random(SEED)`, 10,000 draws, each draw cut to the number of days; 95% intervals by the 2.5th and 97.5th percentiles; the gate's three conditions (F9) over the model version in force and days frozen on time.

- [ ] **Step 1: Failing tests**: `test_brier_is_a_mean_of_daily_means`; `test_constant_differences_give_a_point_interval` (the design's "known by hand"); `test_no_interval_under_28_days`; `test_the_seed_block_and_draws_are_the_designs`; `test_calibration_error_by_hand`; `test_the_gate_fails_on_each_condition_alone` (89 days; Brier above B; an interval touching zero; error 0.031; a bin of 1% off by 0.11); `test_a_late_day_does_not_count_toward_the_gate`; `test_a_new_version_starts_from_zero`; `test_the_gate_stays_closed_in_step_one`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_record_numbers.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 F8)`, `(q22 F9)`, `(q22 F11)`: "blocks of 7 days"; "1,000 draws"; "the seed from the clock"; "a 90% interval"; "calibration weighted equally"; "the gate at 60 days"; "a gate interval allowed to touch zero"; "calibration error 0.05"; "a bin of 1% not checked"; "late days counted"; "versions pooled"; "the gate open".
- [ ] **Step 6: Commit** `git add src/shopper/record.py tests/test_record_numbers.py scripts/mutation_check.py && git commit -m "Shopper site: the record's numbers: Brier, block-bootstrap intervals, calibration and the gate's conditions (F8, F9, F11; q22)"`.

### Task 15: The site's words

**Files:** Create `src/shopper/words.py`; Test `tests/test_shop_words.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `basket.words.NEVER`, `CHAIN_NAMES`, `basket.record.money`.
- Produces (the design's "Words", "What a visitor sees", F10 and P10, verbatim where quoted):

```python
SITE_NAME = "Five chains, listed prices"          # question J
FRONT_TITLE = "Deals below their recent listed prices"
FRONT_RULE = ("promotion prices lower than every price the chain listed for the item over the past 90 days "
              "with records")
GAP_HEADING = "The deal against its listed prices"; HISTORY_HEADING = "How often it goes on promotion"
METHOD_TITLE = "How this is made"; RECORD_TITLE = "Track record"
ALWAYS = ("listed price", "as listed in the chain's price files", "before promotions", "listed in the morning's files")
NEVER = basket.words.NEVER + ("fake", "fake discount", "fake sale", "real deal", "scam", "rip-off", "trick", "inflated",
        "misleading", "deceptive", "pretends", "true price", "you save", "best deal", "guaranteed", "will be on sale",
        "will go on sale", "expected to", "likely to")
ODDS_WORDS = ("odds", "chance", "1 in", "forecast")
FROM_FIELDS = "from the chain's fields"; FROM_TEXT = "read from the fine print"
FINE_PRINT = "fine print not read: club-only or other conditions may apply"
PRICE_NOT_READ = "price not read"; AT_SOME_STORES = "at some stores"
def date_line(day) -> str      # "from the chains' price and promotion files of Friday 6 November 2026"
def credit(day, collected_by) -> str
#  "Prices and promotions from the price and promotion files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof
#   publish under section 30 of the Food and Pharma Competition Promotion Law, 2014: the files of 6 November 2026,
#   collected by 12:03 Israel time. Listed prices and listed promotions, not a promise of what a till charges.
#   Not shopping advice."
def no_odds_yet(slug) -> str   # "No odds yet for Shufersal. Every day this site freezes a forecast for each item and scores
                               #  it two weeks later; the odds appear here once they beat two rules of thumb over 90 days
                               #  (Track record)."
def unreadable(slug) -> str    # "Promotions from Carrefour's files could not be read today."
def as_listed(slug) -> str     # "(as Shufersal lists it)"
def count_line(promotions, products, below) -> str   # "Today the five chains list 1,840 promotions on 6,210 products;
                                                    #  410 of them are below every listed price of the past 90 days at that chain."
def club_label(marking_none: Sequence[str]) -> str   # question K: "from the chains' fields; Shufersal's files mark none"
def targets(target: str) -> str                       # question K's three phrases
def gap_sentences(gap: Gap, day) -> tuple[str, str, str]   # P7
def history_sentences(on, days, runs, gaps, since, day) -> tuple[str, ...]   # P8
def window_note(window: Window) -> str    # "23 days of records since 1 November 2026"
def starts_on(start: date) -> str         # "Listed to start on 9 November 2026."
HIRING = (("Built by Doron Reiffman", "https://www.linkedin.com/in/doronreiffman"), ("How this is made", "method.html"),
          ("Track record", "record.html"), ("Code on GitHub", "https://github.com/doronreiffman/il-grocery-prices"))  # question M (f)
```

- P7, in the design's forms, every count over days with "of the N days with records": "Deal price ₪7.90: ₪4.00, 34%, below the 30-day median listed price of ₪11.90 (of the 30 days with records)." (or "not below the 30-day median listed price of ₪11.90"); "The lowest listed price was ₪10.90 over the past 30 days and ₪10.90 over the past 90; listed at ₪7.90 or less on 0 of the 87 days with records." (a short window says "of the 23 days of records since 1 November 2026"); "The listed price rose from ₪10.90 to ₪11.90 on 28 October 2026." (each change, in order; or "The listed price did not change in the past 30 days."). P8: "On a promotion on 12 of the 87 days with records, as listed in the morning's files."; "Runs: 3 to 9 November 2026; 24 to 30 November 2026."; "Days between runs: 14."; "The last run ended on 30 November 2026, 6 days ago." (or "No promotion listed in the 87 days with records."). No verdict word anywhere.

- [ ] **Step 1: Failing tests**: `test_the_lists_are_the_designs_verbatim`; `test_credit_date_line_and_f10_are_the_designs`; `test_p7_sentences_for_the_designs_example`; `test_p7_and_p8_with_a_short_window`; `test_count_line_with_thousands_separators`; `test_club_label_names_the_chains_marking_none`; `test_no_sentence_says_a_never_phrase_or_we` (every function over a spread of inputs, flattened as the check flattens).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_words.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 words)`: "a never phrase dropped from the list"; "an always phrase dropped"; "the credit line's law missing"; "F10's two weeks"; "a count without its days with records"; "rose for fell"; "the club label names every chain".
- [ ] **Step 6: Commit** `git add src/shopper/words.py tests/test_shop_words.py scripts/mutation_check.py && git commit -m "Shopper site: the words, the credit and date lines, and the sentences of P7, P8 and F10 (q22)"`.

### Task 16: Product pages (with P9's row)

**Files:** Create `src/shopper/product.py`; Test `tests/test_product.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `Covered`, `Pair`, `ChainDay`, Tasks 9, 14 (`Gate`), 15; `basket.page.STYLE`'s base.
- Produces:

```python
MAX_PAGE = 60_000
CHAIN_SPAN = '<span class="as-listed" lang="he" dir="rtl">{}</span>'   # every chain-supplied text, escaped
def page_path(code: str) -> str                                    # p/<code>.html
def render_product(covered: Covered, pairs: Mapping[str, Pair], chain_days, day: date, collected_by: str,
                   gates: Mapping[str, Gate]) -> str
```

- The page, top to bottom: the header band (site name linking to `index.html`, the date line); the title (the longest name, in its span) and each chain's name "(as X lists it)"; the barcode and the size the chains state; one `<section data-chain="<slug>">` per chain that lists it: today's listed price ("listed price", "before promotions", "as listed in the chain's price files") and its stores' range; each promotion today (deal price per unit or per kilogram, "buy N", or "price not read"; its conditions from the fields with their source; `FINE_PRINT`; "listed in the morning's files"; "at some stores" when so); `GAP_HEADING` with P7's sentences for each valid chain-wide deal; `HISTORY_HEADING` with P8's sentences and `no_odds_yet(slug)`; the listed-price history as text (each change) and an inline SVG of the window's daily listed prices with promotion days marked; "last listed chain-wide on <date>" when not today; `starts_on(start)` for a chain-wide promotion listed to start within 14 days (F2, Call 22: measured, and the item gets no forecast); `unreadable(slug)` on a promotions error. Then P9's row: each chain's listed price and deal price today, conditions marked, chains in name order, no ranking words. The footer: credit, links to the browse page, record and method pages. No script.

- [ ] **Step 1: Failing tests**: `test_every_always_phrase_and_no_never_phrase`; `test_each_chain_section_carries_f10_and_no_probability`; `test_a_chains_name_is_escaped_in_its_own_span` (`<b>FAKE "x"\n` as a name); `test_p9_in_chain_name_order_without_rank_words`; `test_a_weighed_deal_is_per_kilogram`; `test_a_promotions_error_says_so_in_that_chains_section`; `test_a_product_beyond_the_read_says_when_last_listed_chain_wide`; `test_the_largest_page_is_under_60_kb` (five chains, three promotions each, a daily price change for 90 days, 40-character names); `test_the_page_is_the_same_bytes_twice`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_product.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass. Then note the median page size of the test's typical product in "Deviations" (the cost line depends on it).
- [ ] **Step 5: Mutations**, `(q22 product)`, `(q22 P9)`: "a name unescaped"; "a name outside its span"; "F10 left out"; "fine print label left out"; "P9 sorted by price"; "a deal per unit when weighed"; "the history chart without promotion days"; "a script tag".
- [ ] **Step 6: Commit** `git add src/shopper/product.py tests/test_product.py scripts/mutation_check.py && git commit -m "Shopper site: the product page, each chain's section and the row across chains (P9; q22)"`.

### Task 17: Browse pages and search (`search.js`)

**Files:** Create `src/shopper/search.py`, `src/shopper/static/search.js`, `tests/search_harness.js` (loads `search.js` under Node and prints its answers as JSON); Test `tests/test_search.py`, `tests/test_search_js.py`; Modify `.github/workflows/ci.yml` (`- uses: actions/setup-node@v4` with `node-version: "22.11.0"`, before the pytest step; both named from memory when this plan was written, UNVERIFIED: confirm the release and its date, at least a month old, before pinning), `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
PIECE_MAX = 150_000
NORMALIZE: dict[str, str]                 # the one table; search.js holds the same JSON between /*NORMALIZE*/ markers
def normalize(text: str) -> str
def pieces(covered: Mapping[str, Covered]) -> dict[str, bytes]    # "search/<key>.json" -> bytes, and "search/pieces.json"
def browse_pages(covered, day, collected_by) -> dict[str, str]   # "browse/<hex>.html" and "browse/other.html"
```

- `search.js`, plain and small: `normalize(text)`, `pieceFor(query, pieces)`, `matches(entries, query)` (every entry whose normalised names contain the query, at most 50, in name order), `barcodeOf(query)` (8 to 14 ASCII digits, leading zeros stripped, else null); on the first keystroke it fetches `search/pieces.json`; a barcode asks for `p/<code>.html` (`HEAD`) and on any answer but 200 says "This site has no page for that barcode." (Call 12); it exports its four functions when `module` exists.

- [ ] **Step 1: Failing tests**: in `tests/test_search.py`, `test_normalize` (quotes, geresh, gershayim, final letters, Latin case, spaces); `test_every_covered_product_is_in_one_piece`; `test_a_piece_over_150_kb_splits_by_its_second_letter`; `test_the_scripts_table_is_the_pythons`; `test_browse_pages_reach_every_product` and `test_a_product_with_no_hebrew_name_is_on_other`. In `tests/test_search_js.py` (Node, `subprocess.run(["node", "tests/search_harness.js", ...])`): `test_normalize_agrees_with_python` (30 names); `test_the_piece_for_a_split_letter`; `test_matches_at_most_50_in_name_order`; `test_a_barcode_is_asked_for_by_its_page` (a fake `fetch` recording the URL and method; a 403 answer → the no-page sentence).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_search.py tests/test_search_js.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 search)`, targets `SEARCH` and `SEARCH_JS` (`src/shopper/static/search.js` with `tests/test_search_js.py`): "final letters kept"; "geresh kept"; "pieces never split"; "split at 300 KB"; "a product in two pieces"; "the JS table differs"; "a 403 read as a page"; "leading zeros kept in a barcode"; "more than 50 matches".
- [ ] **Step 6: Commit** `git add src/shopper/search.py src/shopper/static tests/test_search.py tests/test_search_js.py tests/search_harness.js .github/workflows/ci.yml scripts/mutation_check.py && git commit -m "Shopper site: browse pages, the search index and search.js, the one script (q22)"`.

### Task 18: The front, method, record and basket pages

**Files:** Create `src/shopper/pages.py`; Modify `src/basket/page.py` (`render_index(..., frame: Frame | None = None)`: the band, the credit, an item's link and the method link, today's output when None), `src/basket/build.py` (`build_day(..., write_pages: bool = True)`; `BuildOutcome` gains `public: dict` and `exclusions: dict[str, list[Store]]`); Test `tests/test_shop_pages.py` (and `tests/test_page.py`, `tests/test_build.py` pass unchanged); Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class FrontRow: slug: str; code: str; title: str; deal: Deal; gap: Gap; target: str; min_spend: Decimal | None
@dataclass(frozen=True)
class Counts: promotions: int; products: int; below: int   # the count line (question A): chain-wide promotions listed today, their barcodes, barcodes with a front row
def front_rows_of(code: str, title: str, pairs: Mapping[str, Pair], chain_days, day: date) -> list[FrontRow]   # question A: at most one per chain, its lowest valid chain-wide deal passing on_front
def ordered(rows: Iterable[FrontRow]) -> list[FrontRow]   # by depth (deepest first), then chain, then code
def scorecard_section(scorecard: dict) -> str             # the record page's tables; the guard renders it again (Task 21)
def render_front(rows, counts, day, collected_by, club_marking_none) -> str
def render_method(basket, exclusions, day, collected_by, code_sha) -> str
def render_record(scorecard: dict, ledger_days, files: Sequence[str], chain_days, day, collected_by) -> str
def render_basket(public: dict, basket, exclusions, day, collected_by, product_pages: set[str]) -> str   # basket.html (question M (c), (d))
```

- Front: `FRONT_TITLE`, `FRONT_RULE`, the date line, `count_line`, the search box (`<input id="q">` and exactly `<script src="search.js" defer></script>`), the CSS filters (chain radios, "club-only" and "minimum spend" checkboxes; `club_label` beside the first), the table (product link, chain, deal price per unit or kilogram and "buy N", the 30-day median listed price, depth as a whole percent, conditions with their source, `FINE_PRINT`), the top row's P7 sentences as the story, the hiring line, the credit. Method: P1 to P10 and F1 to F11 in plain words (n0, seed, block, draws, versions), the NEVER list as `<ul id="never-words">`, what is measured and what is inferred, the law, how to reproduce a page, and the basket's method as `<section id="basket">`. Record: Task 14's scorecard per chain, per month and in all, per version; the calibration table and an inline SVG; one sentence per bin holding 1% or more of the scored forecasts; each chain's gate, closed, with which conditions hold; links to every day's forecasts and scores files and the ledger, labelled as test records, not advice; "Promotion fine print is not read yet."; the days the site has and the chain-days short of files.

- [ ] **Step 1: Failing tests**: `test_front_rows_one_per_chain_and_product_by_depth`; `test_the_front_page_has_the_always_phrases_and_one_script`; `test_the_filters_need_no_script` (the CSS rules for each input); `test_the_story_is_the_top_rows_p7`; `test_the_method_pages_never_list_is_the_words_list`; `test_the_record_page_from_the_scorecard` (before any scored day: "No forecast has been scored yet"); `test_basket_html_keeps_the_baskets_always_phrases_and_links_covered_items_only`; `test_render_index_without_a_frame_is_unchanged`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_pages.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 pages)`: "front rows by price"; "two rows for one chain and product"; "a row not passing the front test"; "a second script"; "the never list short of one"; "the record's gate shown open"; "basket items all linked".
- [ ] **Step 6: Commit** `git add src/shopper/pages.py src/basket/page.py src/basket/build.py tests/test_shop_pages.py scripts/mutation_check.py && git commit -m "Shopper site: the front page of deals below their recent listed prices, the method and record pages, and the basket page (q22)"`.

### Task 19: The site-day file and the build command

**Files:** Create `src/shopper/siteday.py`, `src/shopper/build.py`; Test `tests/test_siteday.py`, `tests/test_shop_build.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: every task above.
- Produces:

```python
# shopper.siteday
NOT_COMPARED = ("run_id", "code_sha", "built_at", "collected_by", "revisions", "revised")
def site_day(day, run_id, code_sha, built_at, collected_by, inputs, chain_days, counts, rows, frozen, scorecard) -> dict
def publish_site_day(new: dict, site_dir: Path, now: datetime, revise: str | None) -> tuple[dict, bool, bool]   # B12, as basket.build._publish
# shopper.build
MARKER = ".shopper-site"
@dataclass(frozen=True)
class SiteOutcome:
    day: date; run_id: str; unchanged: bool; basket: BuildOutcome; frozen: Frozen | None; scored: list[date]
    pages: list[str]; data: list[str]; promotions_errors: dict[str, str]
def build_site(day: date, data_dir: Path, site_dir: Path, now: datetime, collected_by: str, freezer,
               revise: str | None = None, rebuild: bool = False, extract: bool = True,
               basket_path: Path = DEFAULT_BASKET, min_items: int = 25) -> SiteOutcome
# PYTHONPATH=src $PY -m shopper.build --day YYYY-MM-DD --collected-by 11:48 [--revise REASON] [--rebuild]
```

- The site-day file (Call 8): the day, the run's provenance, the inputs (each items table's key and the registry read), per chain its record, holes, promotions error and gate, the count line's numbers, the front page's rows, the forecasts (status, SHA-256, S3 time, on time, rows) and the scorecard. The build, in order: with `extract` (the Mac's command), extract the day's tables when missing, or all of them with `rebuild`; the Lambda passes `extract=False`, having fetched them, so an absent raw folder can never become an empty table; load the history; write the registry; when `freezer.writes`, score each due day and write its summary; forecasts and the freeze (the read-only freezer returns what the archive holds); the ledger; the scorecard; the basket (`build_day(..., write_pages=False)`); the site-day file by B12; every page, the index pieces, `search.js`, the marker. `data/` holds `raw/`, `manifests/`, `tables/{prices,promotions,items,covered,scored}/`, `forecasts/date=*/`, `scores/date=*/`; the site folder holds what goes up.

- [ ] **Step 1: Failing tests**: `test_an_unchanged_site_day_is_left_as_published`; `test_differing_numbers_need_a_reason`; `test_a_revision_keeps_the_earlier_run`; `test_the_build_writes_every_covered_products_page_and_the_marker`; `test_the_hand_build_freezes_nothing` (the read-only freezer; `data/forecasts` untouched); `test_the_build_names_its_inputs`; `test_the_command_prints_what_it_did`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_siteday.py tests/test_shop_build.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 site-day)`, `(q22 build)`: "the site-day file revised without a reason"; "provenance compared"; "scores before forecasts" (the order); "pages for today's chain-wide products only"; "the marker not written".
- [ ] **Step 6: Commit** `git add src/shopper/siteday.py src/shopper/build.py tests/test_siteday.py tests/test_shop_build.py scripts/mutation_check.py && git commit -m "Shopper site: the site-day file under B12 and the build command (q22)"`.

### Task 20: The site check

**Files:** Create `src/shopper/check.py`; Test `tests/test_shop_check.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `basket.check.flatten`, `strip_tags`; `basket.words.ALWAYS`, `REVISED`; Task 15's lists.
- Produces: `check_site(site_dir: Path) -> list[str]` and `python -m shopper.check site` (exit 0, 1 with problems one a line, 2 with no page), as `basket.check`.
- The rules (design, "Checks before upload", Call 11): each chain span (`CHAIN_SPAN`) must hold no markup, then is cut out before the word checks; no NEVER phrase as written or as read, except inside `method.html`'s `<ul id="never-words">`, whose items must equal `NEVER`; every page: the credit line's fixed start, "Not shopping advice.", `noindex`, and in its header the date line of the newest site-day file's day (`date_line`; the anti-goal "a page that looks current but is not"); "we", "our", "us" never; `index.html` and every `p/*.html` carry every ALWAYS phrase; `<script` only as `<script src="search.js" defer></script>`; no `src=` or `<link` to another origin; in each `p/*.html` chain section whose chain's gate is closed (the newest site-day file), `no_odds_yet(slug)` present and no ODDS_WORD once it is cut out; in each section of a chain whose promotions are unread today (the same file), `unreadable(slug)` present (question M (g)); every relative `href` and `src` resolves to a file in the build; `p/*.html` at most 60,000 bytes, `search/*.json` at most 150,000; `basket.html` under the basket's index rules (its ALWAYS phrases, REVISED by the newest `days/` file); `index.html` and the marker present.

- [ ] **Step 1: Failing tests**, each rule failing alone on a small built site: `test_a_never_word_inside_a_chains_name_passes`; `test_markup_inside_a_chains_span_fails`; `test_a_never_phrase_outside_the_method_list_fails`; `test_a_method_list_short_of_one_fails`; `test_a_second_script_fails`; `test_an_odds_word_in_a_closed_chains_section_fails`; `test_f10_missing_fails`; `test_an_unread_chain_without_p10s_sentence_fails`; `test_a_link_to_a_missing_file_fails`; `test_a_61_kb_product_page_fails`; `test_a_page_with_yesterdays_date_line_fails`; `test_a_151_kb_piece_fails`; `test_an_outside_stylesheet_fails`; `test_a_clean_site_passes`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_check.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 check)`: one per rule (its condition made `False`, as the basket check's mutations are), plus "a chain span cut out unchecked" and "odds words sought before F10 is cut".
- [ ] **Step 6: Commit** `git add src/shopper/check.py tests/test_shop_check.py scripts/mutation_check.py && git commit -m "Shopper site: the check before every upload (q22)"`.

### Task 21: The guard

**Files:** Create `src/shopper/guard.py`; Test `tests/test_shop_guard.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces: `guard_site(site_dir: Path, published_dir: Path, published_pages: Iterable[str]) -> list[str]` and `python -m shopper.guard <site> <published> <file of published p/ keys>` (exit codes as `basket.guard`).
- The rules: `days/` and `site-days/` by `basket.guard.guard_days`; a local `forecasts/<d>.csv.gz` or `scores/<d>.csv.gz` that the published folder holds must be the same bytes; the published `forecasts/ledger.csv` must be a prefix of the local one; `record.html`'s scorecard section equals Task 18's rendering of the newest site-day file's scorecard; every published `p/*.html` key is in the build (question H).

- [ ] **Step 1: Failing tests**: `test_a_build_missing_a_published_product_page_is_refused`; `test_a_replaced_forecasts_file_is_refused`; `test_a_replaced_scores_file_is_refused`; `test_a_ledger_that_does_not_extend_the_published_one_is_refused`; `test_a_site_day_that_is_not_a_revision_is_refused`; `test_a_record_page_that_differs_from_its_site_day_is_refused`; `test_an_empty_bucket_passes`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_guard.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 guard)`: one per rule.
- [ ] **Step 6: Commit** `git add src/shopper/guard.py tests/test_shop_guard.py scripts/mutation_check.py && git commit -m "Shopper site: the guard: published records never replaced, the ledger only grows, no product page lost (q22)"`.

### Task 22: Uploads, `publish.sh` and `sync.sh`

**Files:** Modify `src/basket/site.py`, `scripts/publish.sh`, `scripts/sync.sh`; Test `tests/test_site.py`, `tests/test_scripts.py` (new); Modify `scripts/mutation_check.py`.

**Interfaces:**
- Produces (in `basket.site`):

```python
UPLOAD_WORKERS = 16
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".csv": "text/csv; charset=utf-8", ".gz": "application/gzip"}
def published(self, key: str) -> bytes | None
def keys(self, prefix: str) -> list[str]
def latest_published_day(self) -> date | None        # the greatest of days/ and site-days/
def put_files(self, site_dir: Path, keys: Sequence[str]) -> list[str]   # every file checked present first; then put through the pool, max-age=300
```

- `publish.sh`: the marker `.shopper-site`; `shopper.check`; reads `days/`, `site-days/`, `forecasts/` and `scores/` from the bucket into a temporary folder and the `p/` keys into a file (`aws s3api list-objects-v2 … --prefix p/ --query 'Contents[].Key' --output text`), then `shopper.guard`; uploads by allowlist, one content type each (`*.html`, `*.json`, `*.js`, `*.csv`, `*.csv.gz`), every one with `--cache-control 'max-age=300'` and none with `--delete`; then the invalidation. `sync.sh`: also the archive's `tables/items/`, `tables/covered/`, `tables/scored/`, `forecasts/` and `scores/` into `data/`, and the site's `site-days/` and `forecasts/ledger.csv` into `site/`, read-only, with `--exact-timestamps` for the site's files as today.

- [ ] **Step 1: Failing tests**: `test_put_files_puts_each_once_with_its_content_type` (2,000 files through the pool); `test_put_files_refuses_a_missing_file_before_any_put`; `test_latest_day_reads_both_folders`; `test_no_method_ever_deletes` (extended); in `tests/test_scripts.py`, `test_publish_sh_deletes_nothing`, `test_publish_sh_runs_the_check_and_the_guard_before_any_upload` (their lines before the first `aws s3 sync`), `test_publish_sh_sets_each_content_type_and_cache_control`, `test_publish_sh_needs_the_shopper_marker`, `test_sync_sh_reads_what_the_hand_build_needs` (each prefix), `test_sync_sh_never_writes_to_aws` (no `cp` or `sync` towards `s3://`).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_site.py tests/test_scripts.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 upload)`, `(q22 publish)`, target `PUBLISH_SCRIPT = ("scripts/publish.sh", ["tests/test_scripts.py"])` and `SYNC_SCRIPT`: "a missing file noticed after the puts"; "gz served as text"; "one worker"; "--delete back on the pages"; "the guard after the upload"; "the marker not checked"; "promotion files not synced".
- [ ] **Step 6: Commit** `git add src/basket/site.py scripts/publish.sh scripts/sync.sh tests/test_site.py tests/test_scripts.py scripts/mutation_check.py && git commit -m "Uploads: every site file with its content type through a pool of 16, and publish.sh and sync.sh for the shopper site, with no delete (q22)"`.

### Task 23: The site run in Lambda

**Files:** Modify `src/basket/handler.py` (`_basket`), `src/basket/archive.py` (the fetches the run needs into the work folder); Test `tests/test_basket_handler.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- Consumes: `build_site`, `ArchiveFreezer`, `check_site`, `guard_site`, `put_files`.
- Produces: the basket mode runs the site. In order: the check-record gate (as today); fetch today's five prices tables (`MissingTable`), store lists, manifests; the items tables and reports of the past 90 days and today (today's missing: `MissingTable` naming the chain and key); the latest registry; every scored summary; the frozen files the build will score; the published `days/<d>.json`, `site-days/<d>.json`, `forecasts/ledger.csv` and the `p/` keys; `build_site(..., freezer=ArchiveFreezer(archive, now), extract=False)`; `check_site` and `guard_site` (`SiteCheckFailed`); the upload (every page, piece and `search.js` only when the day is the site's latest; the data files written new, always; Call 9); one invalidation when anything went up; the basket's record as today; the success ping with the summary, or, after the upload, `/fail` naming each chain's promotions error (question M (a)). `ForecastsDiffer` stops before any upload and pings `/fail`. The run also puts back, plain, the day's registry (`put_covered`) and each new scoring summary (`put_summary`). The published copies it fetches for the guard include the site's `forecasts/<d>.csv.gz` and the `scores/<t>.csv.gz` of each due day, when present. The summary adds `site_day_unchanged`, `forecasts` (status, SHA-256, on time), `scored`, `pages_uploaded` (a count; `pages` keeps its meaning) and `promotions_errors`.

- [ ] **Step 1: Failing tests** (the golden day stretched over a few days, a `MemoryArchive` with its S3 clock): `test_the_first_site_run_publishes_every_page_and_freezes`; `test_an_earlier_day_uploads_its_data_files_only`; `test_an_unchanged_rerun_uploads_pages_not_the_day_files`; `test_a_rerun_after_a_failed_upload_publishes_the_frozen_bytes`; `test_forecasts_that_differ_stop_before_any_upload`; `test_a_run_past_the_cutoff_freezes_nothing_and_records_the_gap`; `test_todays_missing_items_table_names_the_chain`; `test_a_missing_past_table_is_a_hole`; `test_a_chains_promotions_error_publishes_then_pings_fail`; `test_a_guard_failure_uploads_nothing`; `test_the_work_folder_is_removed`.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_basket_handler.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the interfaces and rules above, each module's docstring stating its rules in plain words.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q22 site run)`: "pages put for an earlier day"; "data files withheld when unchanged pages go up" (the reverse of Call 9); "the success ping on a promotions error"; "the fail ping before the upload"; "a differing freeze uploaded"; "the guard skipped"; "today's missing table read as a hole".
- [ ] **Step 6: Commit** `git add src/basket/handler.py src/basket/archive.py tests/test_basket_handler.py scripts/mutation_check.py && git commit -m "Site run: the 12:33 run builds, checks, guards and publishes the whole site, freezing the day's forecasts and scoring those due (q22)"`.

### Task 24: The templates: the function's role and the site bucket's lifecycle rule

**Files:** Modify `template.yaml` (`BasketFunction`'s statements), `site-template.yaml` (`SiteBucket`'s `LifecycleConfiguration`); Test `tests/test_basket_template.py`, `tests/test_site_template.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- The role, as the design's "Where the site lives" lists it: `ReadArchive` adds `forecasts/*` and `scores/*` (`tables/*` covers the new tables); `WriteOnceLockedRecords` adds `forecasts/*` and `scores/*`; `ReadPublishedDays` becomes `ReadPublished`: `days/*`, `site-days/*`, `forecasts/*`, `scores/*`; `WriteSite`: `index.html`, `method.html`, `record.html`, `basket.html`, `search.js`, `p/*`, `browse/*`, `search/*`, `days/*`, `site-days/*`, `forecasts/*`, `scores/*`. Still no `s3:Delete*`, no bypass, no `*`.
- The lifecycle rule (the design's Q10; question H):

```yaml
      LifecycleConfiguration:
        Rules:
          - {Id: old-product-pages, Status: Enabled, Prefix: p/, NoncurrentVersionExpiration: {NoncurrentDays: 30}}
          - {Id: old-browse-pages, Status: Enabled, Prefix: browse/, NoncurrentVersionExpiration: {NoncurrentDays: 30}}
          - {Id: old-search-pieces, Status: Enabled, Prefix: search/, NoncurrentVersionExpiration: {NoncurrentDays: 30}}
          # and one rule each, the same, for index.html, method.html, record.html, basket.html and search.js
```

- [ ] **Step 1: Failing tests**: `test_role_grants_exactly_what_the_code_does` and `test_role_prefixes_are_the_codes_keys` updated to the lists above (the prefixes from the code's own key functions); `test_old_versions_of_rebuilt_pages_expire_after_30_days` (exactly those eight rules, `NoncurrentDays` 30, no `ExpirationInDays`, no transition); `test_no_lifecycle_prefix_matches_a_record_key` (no rule prefix is a prefix of `days/2026-11-07.json`, `site-days/2026-11-07.json`, `forecasts/2026-11-07.csv.gz`, `forecasts/ledger.csv`, `scores/2026-11-07.csv.gz`); `test_the_bucket_keeps_every_version_of_a_published_file` still passes; `test_only_the_four_expected_resources` still passes.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_basket_template.py tests/test_site_template.py -q`. Expected: the new tests fail (what they import or assert is not there yet).
- [ ] **Step 3: Implement** the grants and the rules above, each with a comment saying why, as the template's other statements have.
- [ ] **Step 4: Run** `$PY -m pytest -q`. Expected: all pass. Then `"$(dirname "$PY")/cfn-lint" --regions il-central-1 -- template.yaml site-template.yaml`. Expected: clean.
- [ ] **Step 5: Mutations**, `(q22 template)`, `(q22 lifecycle)`: "a site write left out"; "scores not locked"; "forecasts written plain"; "a delete granted"; "pages kept forever" (one rule removed); "rules on 7 days"; "a rule on scores/"; "a prefix of s".
- [ ] **Step 6: Commit** `git add template.yaml site-template.yaml tests/test_basket_template.py tests/test_site_template.py scripts/mutation_check.py && git commit -m "Templates: the site run's grants, and old versions of rebuilt pages expiring after 30 days (the design's Q10; q22)"`.

### Task 25: The golden 90 days, determinism and F3 end to end

**Files:** Create `tests/shopper_golden.py` (writes items tables and reports straight from a plan of days, through Task 6's writer), `tests/test_golden_90.py`; Modify `scripts/mutation_check.py`.

**Interfaces:**
- The history (design, "Testing"): five chains, two stores each, days 2026-01-01 to 2026-04-30; product G1 on a chain-wide promotion every 21 days for 7 days at every chain; G2 never; G3 at Shufersal listed 10.90, raised to 11.90 on day 60, then on a 7.90 promotion from day 75; G4 at one chain only, with that chain's files missing on days 40 and 41 (holes: with two stores, one store's files are half, which is not a hole) and a weighed "2 for ₪100" stored as 1.5 for ₪75. The expected values are worked by hand in the module's docstring, as `tests/test_build.py`'s golden day is.
- One module-scoped run of `build_site` for every day from the first forecast day to 2026-04-30 over a `MemoryArchive` and its S3 clock at 12:33 Israel time.

- [ ] **Step 1: Write the tests**: `test_the_golden_pages_windows_and_gaps` (G3's P7 sentences and its front-page row on day 75; G1's runs, gaps and days since; G4's holes skipped); `test_the_golden_forecasts_baselines_and_scores` (by hand, a few days and pairs named); `test_the_golden_intervals_and_calibration` (the record page's intervals and calibration recomputed from the published scores files with the printed seed, block and draws: the same numbers; design, "Testing": the record page recomputed from the published files and seed); `test_the_gates_conditions_each_fail_alone` (summaries edited one condition at a time); `test_the_same_days_give_the_same_bytes` (two builds, every page and frozen file, provenance apart); `test_day_d_is_the_same_with_and_without_later_days` (F3: the tables of days after d present or not).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_golden_90.py -q`. Expected: pass (Tasks 1 to 24 built the behaviour; a value that does not come out as written is checked against the arithmetic first, and any change logged in "Deviations").
- [ ] **Step 3: Mutations**, `(q22 golden)`, a target naming `tests/test_golden_90.py` alone: the same breaks as "the horizon fifteen days (q22 F1)", "n0 of 3 (q22 F4)", "front page at or below the low (q22 front)", "a day after d read (q22 F3)", so the golden catches each by itself. Run them, then the staleness check.
- [ ] **Step 4: Commit** `git add tests/shopper_golden.py tests/test_golden_90.py scripts/mutation_check.py && git commit -m "Test: the golden 90 days, determinism and day d without later days (q22)"`.

### Task 26: The docs

**Files:** Modify `docs/operations.md`, `README.md`, `docs/README.md`, `docs/terms.md`.

- [ ] **Step 1: `docs/operations.md`.** "The shopper site, by hand" (replacing "The headline basket, by hand" as the hand path): sync each day read-only, extract (`python -m shopper.extract`), build (`python -m shopper.build --day … --collected-by 11:48`), check (`python -m shopper.check site`), review in a browser (front, a product, record, basket, method; the search box with a name and a barcode), publish on the owner's go after the Nevo date check; what the build prints; revising a day (site-day and day files). "The shopper site, every morning": the timetable unchanged (the 12:33 run now builds the whole site; the event keeps `"mode": "basket"`); where things land (the new archive and site keys); "Sizing" with the step-one measurements to fill at the manual runs (Shufersal's promotion and items seconds and `Max Memory Used`; the site run's duration; page counts and the median page size); "Deploying step one": the budget to $20 (the owner, in AWS Budgets), both deploys with the schedules off and the change sets to expect (this plan's "Where step one lands in AWS"), the first hand upload, the backfill (an `extract` invocation per chain per day from 2026-11-01, each `--invocation-type Event`, one at a time), the manual site run and its expected answer, the schedules on; "Measured later": the share of covered products with a promotion run in their first 90 days, once 90 days of records exist (design, step one's measurements). Every `--payload` in the doc stays a literal `'{...}'` that the doc's tests read as JSON (`tests/test_template.py`), so the backfill is written as the scheduled extract command with "put each day in the payload", as "The manual runs" does, not as a loop over a payload file. "What a /fail email means" gains `ForecastsDiffer` (rerun at the commit that froze the day, whose fingerprint the file names) and a promotions error (the chain, the field; the survey to read the new format; Task 3's constants to change on the owner's word). "Cost": this plan's figures.
- [ ] **Step 2: `README.md`:** the title and opening (the site's three per-product features, the basket kept), "What it does today", "How it works" (text only; the diagram's images wait for the owner), "At a glance" (runs unchanged; counts in Task 27), "What's next" (the reader, the odds once earned). `docs/README.md`: the design and this plan listed.
- [ ] **Step 3: `docs/terms.md`:** one dated line recording the owner's approval of 2026-11-07, which extends the reading to this site's derived numbers and data files (design, "Status"); flagged in the final report for the owner's read, since the file speaks in the owner's voice.
- [ ] **Step 4: Verify** `$PY -m pytest -q` (the operations tests: every AWS command names the profile and region; every payload is one the handler takes; the timetable is the schedules) and the staleness check (`docs/operations.md` carries mutations). Every fact added is checked against the code built or a measurement written down in Task 2.
- [ ] **Step 5: Commit** `git add docs README.md && git commit -m "Docs: the shopper site by hand and every morning, deploying step one, its cost; README (q22)"`.

### Task 27: Full test run, coverage and the full mutation check

- [ ] **Step 1:** `$PY -m pytest --cov=collector --cov=src/basket --cov=src/shopper --cov-fail-under=95`. Expected: every test passes (baseline 1,367), coverage at or above 95% (baseline 99.83%), each `src/shopper` module listed.
- [ ] **Step 2:** `$PY scripts/mutation_check.py`. It edits files in place: nothing else from this checkout until "Files restored." Expected: every mutation CAUGHT, none MISSED, STALE or ERROR (baseline 1,092).
- [ ] **Step 3:** `"$(dirname "$PY")/cfn-lint" --regions il-central-1 -- template.yaml site-template.yaml`. Expected: clean.
- [ ] **Step 4:** the counts Steps 1 and 2 printed, with the date, in README's "At a glance" and "Tests that are themselves tested", and in "Deviations". Commit `git add README.md docs/shopper-site-plan.md && git commit -m "README: test and mutation counts after the shopper site's step one (q22)"`.

### Task 28: The whole-branch review

- [ ] **Step 1:** a reviewer that has not seen the build, on Fable (`model: "fable"`), or the newest Opus (`opus`) while Fable is at its usage limit, the report naming the swap (the owner's model rule of 2026-11-07). Give it `git diff main...q22-shopper-site`, `docs/shopper-site.md`, this plan, `docs/headline-basket.md` and `docs/operations.md`. Ask for findings by severity against the design's anti-goals (a claim the files cannot back; a forbidden word; odds before the gate; a record that changes quietly; a page that looks current and is not; raw files published; a page needing a script for a fact), its rules P1 to P10 and F1 to F11, its calls, and this plan's Review Focus. The reviewer reads only: no commits, no `gh`, no push, no AWS, no network.
- [ ] **Step 2:** check each finding against its source before acting (a finding is a claim); fix what holds, test-first, each fix with its mutation; log every change from this plan in "Deviations"; rerun Task 27's Steps 1 and 2.
- [ ] **Step 3:** stop. Merge, push, the deploys, the budget, the first upload, the backfill and the schedules are the owner's go ("Where step one lands in AWS").

## Deviations

(Append here when reality forces a change from this plan: what changed, why, and when.)

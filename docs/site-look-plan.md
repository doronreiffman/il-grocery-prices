# The site's look, "Shelf label" (implementation plan)

Grade, quoted from the approved design ([site-look.md](site-look.md), "Grade", the owner's, 2026-11-15): "a portfolio piece for job applications at production quality: professional, elegant and impressive at first glance; accessible (WCAG 2.2 AA in both themes); fast; light and dark; phone and desktop."

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every page of the shopper site takes the approved "Shelf label" look: one shared stylesheet and two typefaces served from the site, a deal as a green shelf label in the shade of its saving, NO DEAL as a yellow one, the price set as on a shelf edge with the product's own barcode, a price chart with a ₪ axis, dates and step lines whose words never shrink, and the word changes the owner decided, with nothing the rules compute changed but the two counts the design calls.

**Architecture:** a new module, `shopper.assets`, turns the committed stylesheet and fonts into the site's `assets/` folder under hashed names; every page links that one stylesheet in place of its inline style block, and names its kind on `<body>`. A new module, `shopper.bars`, encodes a product's barcode. `shopper.chart` is rewritten to four SVGs, only one of which scales. `shopper.product`, `shopper.pages`, `shopper.shell` and `basket.page` change their markup; `shopper.words` gains the decided words. The build writes `assets/`, the site check holds pages and assets to new rules, and both uploads (`basket.site` in Lambda, `scripts/publish.sh` on the Mac) put an asset once, before any page names it. `search.js` does not change.

**Tech Stack:** Python 3.13 standard library, `duckdb==1.5.6` (already pinned), pytest and pytest-cov, `scripts/mutation_check.py`; Node 22.11.0 (already in CI) for the script's tests. No new dependency of the project. The fonts are made once, outside the project's requirements, by `scripts/subset_fonts.py` in a throwaway environment with fonttools 4.59.0 and brotli 1.2.0.

**Spec:** [site-look.md](site-look.md) (approved by the owner 2026-11-15). Read it in full first, its appendix (the stylesheet) included. Then the rules the look keeps: [store-first.md](store-first.md) ("The rules", S0 to S8, S5's shades, "The chart", "Page size") and [shopper-site.md](shopper-site.md) ("Words", "Build and hosting", "Checks before upload"). The code this changes: `src/shopper/` (`shell.py`, `pages.py`, `product.py`, `search.py`, `chart.py`, `words.py`, `verdict.py`, `check.py`, `build.py`), `src/basket/page.py` (`Frame`, `STYLE`, `BASE_STYLE`, `BASKET_STYLE`), `src/basket/site.py`, `scripts/publish.sh`, `scripts/time_site_run.py`, `template.yaml` (`WriteSite`), and the tests that pin pages, styles and uploads: `tests/test_product.py`, `tests/test_shop_pages.py`, `tests/test_chart.py`, `tests/test_shop_words.py`, `tests/test_shop_check.py`, `tests/test_shop_build.py`, `tests/test_page.py`, `tests/test_site.py`, `tests/test_scripts.py`, `tests/test_basket_template.py`, `tests/test_basket_handler.py`, `tests/test_golden_90.py`, `tests/shopper_golden.py`, `tests/golden/golden-90.sha256`.

## Global Constraints

- The grade above binds every task: test-first, a planted bug (mutation) for every rule, a fresh review per task and of the whole branch, and the owner's read of a real day's built pages before the merge.
- Branch `q36-site-look`, worktree `/Users/doronreiffman/Projects/il-grocery-prices-q36-site-look`, from main at 16fb85b (the approved design's commit). A task that runs beside another (the waves under "Running tasks side by side") gets its own branch `q36-<name>` and worktree `/Users/doronreiffman/Projects/il-grocery-prices-q36-<name>`, made from `q36-site-look`'s head when its wave starts; the controller merges each into `q36-site-look` in task order. One commit per task (fix rounds add their own), each message naming q36. Never push; no `gh`; no AWS write, deploy or upload (each is the owner's go, outside this plan). Before each commit, run `git status` and stage only the task's files.
- `PY` is `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/python`. A worktree has no venv; pytest's `pythonpath` (`src`, `tests`) makes it test the worktree's code. Commands run from the worktree's root.
- The full test command: `$PY -m pytest -o addopts="" --cov=collector --cov=src/basket --cov=src/shopper --cov-fail-under=95 -q`. Baseline: 2,649 tests at 99.86% on main at 9a74f15 (2026-11-15, CI green); `pytest --collect-only` at 16fb85b also collects 2,649. Measure once on the branch before Task 1 and write it in "Deviations". The floor is 95%; `assets.py`, `bars.py` and the rewritten `chart.py` reach 100%.
- Test-first: a failing test before the code, for every rule.
- A named mutation in `scripts/mutation_check.py` for every rule, added in the task that adds the rule. The name says what the break does, then the group in brackets: `(q36 look)`, `(q36 assets)`, `(q36 fonts)`, `(q36 bars)`, `(q36 words)`, `(q36 upload)`, `(q36 chart)`, `(q36 shell)`, `(q36 check)`, `(q36 product)`, `(q36 front)`, `(q36 method)`. New targets: `LOOK = ("src/shopper/static/look.css", ["tests/test_look.py"])`, `SHOP_ASSETS = ("src/shopper/assets.py", ["tests/test_assets.py"])`, `SUBSET_FONTS = ("scripts/subset_fonts.py", ["tests/test_subset_fonts.py"])`, `SHOP_BARS = ("src/shopper/bars.py", ["tests/test_bars.py"])`; the `TIME_LIMIT` comment's count of target sets is updated in the task that adds one. Only pytest exit 1 counts as caught. `tests/test_mutation_targets.py` runs with the suite and refuses a mutation whose text or test is gone. In a wave, each task adds its new mutations as one block right after the anchor its task names, so two worktrees never append at the same line.
- Each task's mutation step runs from that task's own worktree: `$PY scripts/mutation_check.py "q36 <group>" ...` over its groups and every name it re-pointed, then the staleness check. Expected: every one CAUGHT, then `none stale`. The check edits files in place, so nothing else runs from that worktree while it runs. The full check is CI's weekly run.
- **The staleness check** reads and edits nothing: `$PY -I -c "import importlib.util as u; s = u.spec_from_file_location('m', 'scripts/mutation_check.py'); m = u.module_from_spec(s); s.loader.exec_module(m); bad = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]; print(len(m.MUTATIONS), bad or 'none stale')"`. At 16fb85b it prints `2456 none stale`.
- **Re-point or retire.** A mutation whose rule stays but whose text moved is re-pointed at the new text, with the same break. A mutation of a rule the design removes (the inline style blocks, the chart's side labels and today's dashed line, the pixels-a-day width, the grey No deal) is retired with its code. Each retired mutation is named in its task's commit message and in "Deviations", with the rule it guarded; each re-pointed one in the commit message.
- **Golden repins.** Run `GOLDEN_90_REPIN=1 $PY -m pytest tests/test_golden_90.py -k pinned` only after every other golden test passes, and only after reading what changed: build the golden site at the task's base and at its head (`PYTHONPATH=src:tests $PY tests/shopper_golden.py <folder>`, which writes `<folder>/run/site`; about eight minutes each), `diff` one moved page of each kind, and confirm every difference is the task's. Then list the moved names with `git diff -U0 tests/golden/golden-90.sha256 | grep '^[-+][0-9a-f]' | awk '{print $2}' | sort -u`, compare that list with the task's expected list, and name the reason and the kinds of change in the commit message. A task merged after another task's repin re-runs the repin on the merged tree; the pin file is never merged by hand.
- Test data never reads the clock: fixed days and times, `gzip.compress(..., mtime=0)`. Every datetime is time-zone aware; the look works on dates only.
- **The design's values, copied, never re-derived:** the colour tokens of "Colour", both themes; the type scale; the chart's numbers (a plot 200 pixels high, 224 with the dates; the axis column 46 pixels and the today column 64; steps of 1, 2, 5 times a power of ten, two to five of them, half a shekel for prices less than a shekel apart, the axis a step lower when the lowest price is within 8% of the bottom; a date a week under 46 days, the months from 46; a date nearer than 22% of the span to the first date or 16% to today hidden on a phone; today's labels 17 pixels apart; dots of radius 4.5; the unread ticks 7 pixels high, 2 on and 2 off); the barcode's rules; the byte lines (the stylesheet under 22,000, the three fonts under 45,000 together, a product page under 45,000, the site check's `MAX_PAGE` of 60,000 kept).
- **The stylesheet is the design's appendix, byte for byte** (20,884 bytes, SHA-256 `ade437b4164b6d00549fdf9eabbe17d45e46a8b60fcf9e2657e2408f3d4d184e`). Any later change to it is a deviation with its reason, and it moves the stylesheet's hashed name in every page.
- **`search.js` does not change.** After every task, `git diff --stat main -- src/shopper/static/search.js` prints nothing and `LC_ALL=C grep -c '[^ -~	]' src/shopper/static/search.js` prints 0. `src/shopper/search.py`'s `NORMALIZE` table holds backslash-u escapes as well: Task 6 deletes `BROWSE_STYLE` alone with an edit that does not touch the table, and the staleness check proves the `(q22 search)` mutations' texts still there.
- **Public page words.** Every headline and label is what a shopper would say out loud; the words are the owner's, listed under "Words"; never "we", "our" or "us" (`shopper.check` refuses them), never a NEVER phrase.
- No new dependency of the project. The font tools live only in a throwaway virtual environment outside the repo: fonttools 4.59.0 (on PyPI since 2025-07-16) and brotli 1.2.0 (on PyPI since 2025-11-05), both more than a month old (PyPI's release data, read 2026-11-15), installed with `--no-deps --require-hashes` from their pinned wheels (Task 1).
- Nothing in the code deletes: no `delete_object`, no `s3:Delete*` in the role, no `--delete` in the scripts. Old hashed assets stay in the site bucket.
- Every page is a pure function of its inputs and of the repo's files (the stylesheet and fonts, as `search.js` already is): the same bytes whatever order the rows or mappings come in.
- Docs, this plan included, are in plain words with no "we". This plan and every doc are public: no pointer to the owner's private notes, no email address, no claude.ai link, no health-check URL, no site address.
- Models (the owner's rule): implementers and task reviews on the newest Opus (`opus`), Task 2's implementer (a transcription of GS1's tables, pinned by its tests) on the newest Sonnet (`sonnet`). The whole-branch review runs on Fable (`fable`), or on the newest Opus while Fable is at its usage limit, the report naming the swap. A task still open after fix round 3 escalates to Fable. Subagents never run `gh` or push.

## Review Focus

1. **A product whose barcode cannot be drawn.** A code of 10 or 11 digits, a chain's own code, or a wrong check digit: the label shows its price part without bars, no `<svg class="defs">` or `<use>` is written, the page's "Barcode …" line still gives the digits, and the site check's fragment rule passes. Tests: Task 2 (`test_a_code_that_is_not_a_barcode_gets_no_bars`) and Task 8 (`test_a_product_with_no_bars_has_no_drawing_and_no_mark`).
2. **Prices that make an awkward axis.** One price for every day, prices under a shekel, a product over ₪1,000, a sale far below the shelf price: two to five round steps, no price on the date line, never an error. Tests: Task 5 (`test_the_axis_takes_round_steps`, `test_no_price_sits_on_the_date_line`).
3. **A store type whose day was not read.** Osher Ad's promotions on 14 November, or a hole: its label on the front page shows the name alone, never "0 promotions today", and its store page says no count either. Test: Task 9 (`test_each_store_label_carries_its_promotions_today`).
4. **An upload that finds the assets already there, or must not send them.** A run for an earlier day puts no asset; a hand publish or a later morning re-puts none the bucket holds; a changed stylesheet's new name is up before any page names it, and a failed asset put stops the upload before any page. Tests: Task 4 (`test_upload_puts_each_asset_before_any_page`, `test_an_asset_the_bucket_holds_is_not_put_again`, `test_assets_go_up_only_with_the_pages`, `test_a_failed_asset_put_stops_the_upload_before_the_pages`, `test_publish_sh_puts_an_asset_only_when_the_bucket_lacks_it`).
5. **A history of one or two days, and a sale that starts today.** The chart still shows the first date and "today" without a mark between, and a sale starting today is a short green line ending in its dot. Tests: Task 5 (`test_a_short_history_has_its_first_date_and_today`, `test_a_sale_that_starts_today_is_a_short_green_line_ending_in_its_dot`).

---

## Questions for the owner

None blocks the build. Each is a reading this plan takes where the design is silent, built as stated below unless the owner says otherwise.

The owner read the plan on 2026-11-16 and gave the go: readings 1, 2, 4 and 5 stand; reading 3 is overturned. On an unread sale price today, today shows no price at all: no shelf point and no label at the chart's right end, only the tick for a sale whose price was not read. The shelf line ends at the day before today. The reason is the owner's ruling of 2026-11-11 (no today's price on an unread sale price), which the design keeps ("the chart still shows the days before"). The owner has no iPhone, so Task 12 reads the pages in Safari and Firefox on the Mac and on the owner's own phone.

1. **The role** (a template change the design does not name): `WriteSite` gains `assets/*`, deployed with the code ("Where the design leaves room", "The role"). Without it the first morning's site run is refused at its first asset and puts no page.
2. **Today's two labels at the chart's right end are both bold**, since the appendix's `.chart .now` rule matches the today column itself; the design's words say the lower alone. The stylesheet stays the appendix and the owner judges it by eye (Task 12, Step 6).
3. **An unread sale price today** (`price_unread`): overturned by the owner on 2026-11-16 (above). The shelf line ends at the day before today, today's column holds "today" alone, and the tick marks today as on sale, price not read ("The chart, call by call").
4. **Over 45,000 bytes**, should the largest real page pass it: nothing is cut without the owner's word; the order proposed is store-first.md's, then site-look.md's ("If the largest real product page is over 45,000 bytes").
5. **The assets' caching** stays five minutes, as every file's; a year's `Cache-Control` for the hashed files is a later step (the design's "Left to the builder").

## Where the design leaves room, this plan decides

From "Left to the builder" and from places the design is silent. The owner can overturn any of these.

- **Modules.** `shopper.assets` makes the shared files; `shopper.bars` encodes a barcode (named so, not "barcode", since `basket.barcode` already exists); `shopper.chart` is rewritten in place; the words go in `shopper.words`. "Lowest and highest count today" (the design's call 3) is a rule, so `extremes` lives in `shopper.verdict`, which imports neither `words` nor `chart`; both read it.
- **The hashed names come from the repo's files.** `shopper.assets.STYLESHEET`, the stylesheet's path in the site, is worked out when the module loads, from `src/shopper/static/look.css` and the fonts. Every page names it; the build writes `asset_files()`; the site check reads `STYLESHEET` as it reads `SCRIPT_TAG`. The code fingerprint (`code_sha`) covers `.py` files only, so the stylesheet and fonts sit outside it, as `search.js` does; the golden pin catches any change to them.
- **The fonts in the repo** keep their plain names (`archivo-text.woff2`, `archivo-narrow.woff2`, `heebo-hebrew.woff2`, `OFL-archivo.txt`, `OFL-heebo.txt`) in `src/shopper/static/fonts/`, beside a `README.md` giving each file's bytes, SHA-256, source and licence. The build hashes them.
- **The role.** The design names no template change, but the site run cannot put `assets/` without one: `template.yaml`'s `WriteSite` gains `arn:aws:s3:::${SiteBucketName}/assets/*`. Code and permission deploy together ("Deploying this branch").
- **The site stack does not change.** A content type and a `Cache-Control` belong to each object, set at upload; the lifecycle rules name the files a morning rebuilds under the same key, and an asset is never put twice under its name, so it has no older version to expire; the distribution serves any key. `Cache-Control` stays `max-age=300` for the assets, as for every file (the design leaves a year's caching to a later step).
- **The upload in Lambda** (`basket.site.upload`), with the pages only: the record files in a call of their own, as today; then every file under `assets/` that a listing of the bucket's `assets/` does not hold, in a `put_files` call of its own, ended before anything else starts; then the data files and the pages. A failed asset put raises and nothing after it is put.
- **The upload by hand** (`scripts/publish.sh`): three allowlisted syncs, `assets/*.css`, `assets/*.woff2` and `assets/*.txt`, each with its content type, after `*.js` and before `*.html`. `aws s3 sync` uploads a file whose size or time differs, and every build writes the assets afresh, so each of the three passes `--size-only`: a name carries its bytes' hash, so a name the bucket holds is the same file and the same size.
- **One more site check rule:** each hashed asset's name carries the first ten hex digits of its own SHA-256. The upload skips a name the bucket already holds, so a name that did not match its bytes would never be corrected.
- **The chart, call by call.** Today's shelf price is `money(point.listed)` when the point exists, has a listed price, today is a record day (`today.record`) and the call is neither `price_unread` nor `unread_today`; otherwise none. Today's sale point is the verdict's today's price when a promotion counts (`found.counting`) and the price is known. Today is a sale day of unknown price on `price_unread`.

  | Call | Shelf line through today | Sale point today | Tick under today | Today's labels | Table cells |
  |---|---|---|---|---|---|
  | `deal`, `no_deal` | yes | yes | no | shelf, sale | Lowest, Highest, Usual, Today |
  | `no_sale`, `some_stores` | yes | no | no | shelf | Lowest, Highest, Today |
  | `mostly_unknown` | yes | yes | no | shelf, sale | Lowest, Highest (when a price is known), Today |
  | `price_unread` | no (ends the day before) | no | yes | none ("today" alone) | Lowest, Highest |
  | `unread_today` | no (ends the day before) | no | no | none ("today" alone) | Lowest, Highest |
  | `not_sold`, `too_few` | no | no | no | none ("today" alone) | Lowest, Highest |
  | `new`, `no_history` | no chart: no tracked day, as today | | | | |

  On `price_unread` and `unread_today` the chart shows no price for today: the shelf line ends at the day before and today's column holds "today" alone; on `price_unread` the tick under today marks the sale whose price was not read. "Price today" is not shown either. The owner's rulings of 2026-11-11 and 2026-11-16: a shelf price written at the line's end reads as what the shopper pays today, and a shopper holding a sale tag does not pay it. The fold-out still gives that day's listed price.
- **The label, call by call.**

  | Call | What the section shows |
  |---|---|
  | `deal` | `<div class="tag deal-N">`: the verdict, the reason, the conditions, a coming sale; the price part |
  | `no_deal` | `<div class="tag no-deal">`, the same parts |
  | `no_sale`, `some_stores`, `new`, `mostly_unknown`, `no_history`, `price_unread`, `unread_today` | `<div class="tag none">`: `NO_VERDICT`'s line as `<p class="verdict">`, the conditions when a promotion is judged, a coming sale; the price part |
  | `too_few` | `<p class="few">` (`basket.words.too_few`), no label |
  | `not_sold` | `<p class="not-sold">`, the empty slot, no label |

  The price part, `<div class="pay">`, holds the price line when today's price is known and the barcode's mark when the code has bars; with neither it is left out.
- **The front page's counts** are the store pages' own number: `promotions_shown(front, today)`, `front.promotions` on a day read and None on a hole or a promotion hole, read by both the picker's labels and the store page's fold-out line. The site-day file already holds it (each column's `front.promotions`, null on a day not read).
- **Dead code goes with its last caller,** each proved by `grep`: `BADGE_STYLE`, `PRODUCT_STYLE`, `PAGE_STYLE`, `ROOT_STYLE`, `STORE_STYLE`, `METHOD_STYLE`, `RECORD_STYLE`, `BROWSE_STYLE`, `basket.page.BASE_STYLE` and `BASKET_STYLE` (the shopper pages were their only callers), `chart.DAY_WIDTH` and the old label placing, `pages.ROOT_LINE` (moved to `shopper.words`). `basket.page.STYLE` stays, byte for byte, for the basket's own stand-alone pages.
- **If the largest real product page is over 45,000 bytes** (Task 8), nothing is cut without the owner's word. The task stops and reports the page and its bytes part by part. The order to propose: store-first.md's, simplify the chart's drawing first; then site-look.md's two cuts, the digits under each label's barcode (29 bytes a part), then the barcode's mark in every part but the first (146 a part).
- **The real day for measuring and for the owner's read** is the latest day whose five chains' items tables are in the main checkout's `data/tables/items/` (2026-11-10 when this plan was written). The controller may bring a later one with a read-only `sh scripts/sync.sh <day>` after the identity check (`aws sts get-caller-identity --profile flights-sam`: account 137953273942, user doron-admin). The build writes into the worktree's own `site/` (gitignored); in the main checkout's `data/` it rewrites the day's covered registry (same rules, same bytes) and adds one basket record, as store first's measurements did.

## Words

All decided by the owner on 2026-11-15 (site-look.md, "Word changes"); none is waiting. The constant each lives in:

- `shopper.words.ROOT_TITLE = "Deal or No Deal?"`, set in capitals by the stylesheet, "Deal" and "No Deal" each on its label; the front page's tab title is `SITE_NAME` ("Deal or No Deal"). The nine store pages keep `FRONT_TITLE`, "Is it actually a deal?", its last word on the green label.
- `shopper.words.ROOT_LINE = "Find out if a sale is actually a deal: pick the store you're in, then look up the product. Each sale is checked against what it usually costs there."` (in place of `shopper.pages.ROOT_LINE`).
- `shopper.words.PRICE_TODAY = "Price today:"`; `price_line(found)`: "Price today: ₪14.00", "Price today: ₪50.00 a kilogram".
- `shopper.words.STATS_HEADS = ("Lowest", "Highest", "Usual", "Today")`; short dates `short_day`: "16 Aug", "13 Nov"; month names `month_name`: "Sep"; `TODAY_WORD = "today"`, the chart's last date and the date of a lowest or highest that is today's. Sentences keep the long form ("ended 11 November").
- "Days tracked" stays every tracked day (S7). `reason` (its three forms) and `last_low` say "days tracked" when `len(found.priced) == len(found.days)` and name their own count when not: "Usually ₪22.90, sales included (83 days with a known price).", "It's been ₪10.90 or less on 9 of the 9 days with a known price.", "Only ₪0.40 below its usual ₪3.20 (12 days with a known price).", "Lowest in the 83 days with a known price."; one day is "1 day with a known price".
- A store's label on the front page: `promotions_today(1347) == ("1,347", "promotions today")`, shown as "1,347 PROMOTIONS TODAY". This plan adds the singular, `promotions_today(1) == ("1", "promotion today")`, by the rule every count on the site follows.
- The method page's row of links: `shopper.pages.ON_THIS_PAGE = "On this page"`, spoken, not shown.
- A store page's row: the badge is `verdict_words(found)` ("DEAL · ₪1.90 off", "NO DEAL"), without "At <store>:".
- The chains' line (`CHAINS_LINE`) in the front page's header only.
- Following from these, not new words: the chart's spoken summary counts today in its lowest and highest; the stylesheet writes "Usually " before the usual price in a phone's store row (`FRONT_HEADS[3]`); the barcode's digits show a second time, under the bars, hidden from screen readers.

## Running tasks side by side

Each wave starts from `q36-site-look`'s head once the wave before it is merged. Within a wave, each task has its own worktree; the controller merges them in task order, runs the full suite on the merged branch, and re-runs the golden repin there when two tasks of the wave moved it.

| Wave | Tasks, side by side | Needs |
|---|---|---|
| 1 | Task 1 (the stylesheet, the fonts, `shopper.assets`), Task 2 (`shopper.bars`), Task 3 (the words), Task 4 (the uploads and the role) | nothing |
| 2 | Task 5 (the chart), Task 6 (the shell and every page's frame) | Task 5: Task 3. Task 6: Task 1 |
| 3 | Task 7 (the site check), Task 8 (the product page), Task 9 (the front and store pages) | Task 7: Tasks 1 and 6. Task 8: Tasks 2, 3, 5 and 6. Task 9: Tasks 3 and 6 |
| 4 | Task 10 (the method page's links; the docs) | Tasks 4, 6, 7, 8, 9 |
| then, in order | Task 11 (the full checks), Task 12 (the owner's read), Task 13 (the whole-branch review) | everything before |

Task 3 is the only wave-1 task that moves the golden (the reason line, the chart's spoken summary); Tasks 5 and 6 both move it in wave 2, and Tasks 8 and 9 in wave 3, so the second of each pair re-runs the repin after the merge.

---

### Task 1: The stylesheet, the fonts and the shared files

Wave 1. Its own worktree, `q36-assets`. Nothing renders with it yet: Task 6 links it from every page.

**Files:**
- Create: `src/shopper/static/look.css` (the design's appendix, byte for byte), `src/shopper/static/fonts/` (`archivo-text.woff2`, `archivo-narrow.woff2`, `heebo-hebrew.woff2`, `OFL-archivo.txt`, `OFL-heebo.txt`, `README.md`), `scripts/subset_fonts.py`, `src/shopper/assets.py`
- Test: `tests/test_assets.py`, `tests/test_look.py`, `tests/test_subset_fonts.py`
- Modify: `scripts/mutation_check.py` (the three new targets and the block after the last `(q33 method)` entry)

**Interfaces:**
- Consumes: `shopper.pages.FRONT_HEADS` (read by one test of the stylesheet).
- Produces:

```python
# shopper.assets
STATIC: Path                                   # src/shopper/static
FOLDER = "assets"                              # the site's folder of shared files
SHEET = "look.css"                             # in STATIC
FONTS = ("archivo-text.woff2", "archivo-narrow.woff2", "heebo-hebrew.woff2")   # in STATIC / "fonts"
LICENCES = ("OFL-archivo.txt", "OFL-heebo.txt")                                 # in STATIC / "fonts", published as named
def hashed(name: str, data: bytes) -> str      # "archivo-text.97c5421649.woff2": the first ten hex of SHA-256(data) before the last suffix
def asset_files() -> dict[str, bytes]          # "assets/<name>" -> bytes, in a fixed order: the three fonts under their hashed names,
                                               # the two licences, then the stylesheet with each url(<font>) written as url(<hashed font>),
                                               # under its own hashed name; ValueError when look.css's url()s are not exactly FONTS
STYLESHEET: str                                # the stylesheet's path in the site, "assets/look.<hash>.css", from asset_files() at import
```

- `scripts/subset_fonts.py`, run as `python -I scripts/subset_fonts.py --sources <folder> --out <folder>` in the throwaway environment:
  - `PINNED`, by family: Archivo 2.001 at `google/fonts` commit `6c70c829f09ea345d3590406693220ea35c6553f`, `ofl/archivo/Archivo[wdth,wght].ttf` (SHA-256 `0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053`) and `ofl/archivo/OFL.txt` (`108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b`); Heebo 3.100 at commit `804ab16a8ff8ac0072e7c5ecc34e381b4a710177`, `ofl/heebo/Heebo[wght].ttf` (`18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30`) and `ofl/heebo/OFL.txt` (`866747cbccae229433e946b90fcfc457b81c33ac89e593855770851354f9e6c3`). Each file is fetched from `https://raw.githubusercontent.com/google/fonts/<commit>/ofl/<family>/<file>` with a User-Agent naming the script alone (no email), unless `--sources` already holds it with that SHA-256.
  - `LATIN = "U+0020-007E,U+00A0-00FF,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2022,U+2026,U+2190,U+2192,U+2212"`; `HEBREW = "U+0020,U+0590-05FF,U+20AA"`.
  - `FILES`: `archivo-text.woff2` from Archivo, `LATIN`, axes `{"wdth": 100, "wght": (400, 700)}`; `archivo-narrow.woff2` from Archivo, `LATIN`, `{"wdth": 70, "wght": 800}`; `heebo-hebrew.woff2` from Heebo, `HEBREW`, `{"wght": (400, 800)}`.
  - How each is made: `TTFont(source, recalcTimestamp=False)`; `fontTools.varLib.instancer.instantiateVariableFont(font, axes)`; saved to memory and read back with `recalcTimestamp=False` (the subsetter trips on a freshly instanced font's `gvar`); `fontTools.subset.Options` with `layout_features = ["kern", "liga", "tnum", "lnum", "pnum", "case", "ccmp", "locl", "mark", "mkmk"]`, `flavor = "woff2"`, `name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]` (the copyright and licence names stay in the file), `notdef_outline = True`; `Subsetter.populate(unicodes=...)`, `.subset(font)`; saved with `flavor = "woff2"`. Each family's `OFL.txt` is copied as `OFL-<family>.txt`. It prints each file's bytes and SHA-256.
  - `verified(data: bytes, sha256: str, name: str) -> bytes`: ValueError when the bytes are not the pinned ones.
  - `check_tools(fonttools: str, brotli: str) -> None`: ValueError unless `("4.59.0", "1.2.0")`, read with `importlib.metadata.version`. `fontTools` is imported inside the functions that use it, so the tests import the script without it.

- [ ] **Step 1: Copy the stylesheet** from the design's appendix: `sed -n '/^```css$/,/^```$/p' docs/site-look.md | sed '1d;$d' > src/shopper/static/look.css`. Expected: `wc -c` prints 20884 and `shasum -a 256` prints `ade437b4164b6d00549fdf9eabbe17d45e46a8b60fcf9e2657e2408f3d4d184e`.
- [ ] **Step 2: Write the failing tests** for the stylesheet, `tests/test_look.py`. It reads `look.css`: the light tokens from `:root{…}`, the dark ones from `@media (prefers-color-scheme:dark){:root{…}}` laid over the light.
  - `test_the_tokens_are_the_designs`: both sets equal site-look.md's "Colour" table. Light: `--bg #ffffff`, `--ink #111111`, `--ink-2 #555555`, `--line #d6d6d6`, `--soft #f1f1ee`, `--d1 #c8f1d5`, `--d2 #6fdc9b`, `--d3 #22b35e`, `--on-deal #111111`, `--nd #ffd60a`, `--on-nd #111111`, `--nd-edge #111111`, `--sale #0b7a3b`, `--plate #ffffff`, `--bars #111111`. Dark: `--bg #131313`, `--ink #f2f2ef`, `--ink-2 #b4b4b0`, `--line #3d3d3a`, `--soft #222220`, `--d1 #27995a`, `--d2 #34b76a`, `--d3 #4fe08c`, `--nd #ffd60a`, `--on-nd #111111`, `--nd-edge #ffd60a`, `--sale #4fe08c`, the rest as light.
  - `test_every_pair_holds_its_contrast_in_both_themes` (design test 1; WCAG 2.2's relative luminance): each pair of the design's "Contrast" table, by token, at or above its line in both themes. Words, 4.5: `ink`/`bg`, `ink-2`/`bg`, `on-deal` on each of `d1`, `d2`, `d3`, `on-nd`/`nd`, `sale`/`bg`, `bg`/`ink` (the inverse label), `ink`/`soft`, `ink-2`/`soft`, `bars`/`plate`. Lines, edges and marks, 3: `ink`/`bg`, `ink-2`/`bg`, `nd-edge`/`bg`, and each green label's edge on `bg`, the edge being `ink` in the light theme and the label's own green in the dark. The hairlines (`line`/`bg`) are decoration and have no line. The S5 contrast test of `tests/test_product.py` is replaced by this one (Task 6 retires it).
  - `test_a_green_labels_edge_is_ink_on_paper_and_its_own_green_on_the_dark_page`: the rule `.deal-1,.deal-2,.deal-3,.brand b,h1 .yes{--edge:var(--ink)}` and, under the dark query, `{--edge:var(--fill)}`: what the edge pairs above assume.
  - `test_no_colour_outside_the_tokens` (design test 2): with the two `:root` blocks taken out, no `#` colour, no colour function (`rgb(`, `rgba(`, `hsl(`, `hsla(`, `hwb(`, `lab(`, `lch(`, `oklab(`, `oklch(`, `color(`), and no named colour of CSS Color 4's list (the test holds the list) as a whole value word; `transparent` is the one keyword allowed.
  - `test_every_token_used_is_defined`: every `var(--x)` has a `--x:` declaration somewhere in the stylesheet.
  - `test_the_charts_words_never_shrink` (design test 4, its stylesheet half): every font size in a rule whose selector holds `.chart`, `.stats` or `.key` (a `font-size` or the size of a `font` shorthand, in rem at 16 pixels) is at least 12 pixels; the rule `.chart path,.chart line` sets `vector-effect:non-scaling-stroke`, which every stroke of the lines' SVG falls under.
  - `test_nothing_is_hidden_but_by_a_named_rule`: the rules that set `display:none` are exactly `[hidden]` (with `!important`), the two filter rows (`#f-club:checked~…`, `#f-spend:checked~…`), `nav .badge i` (the badge's hidden separator), `.chart .near` (under the phone query) and the print rule; no other rule sets `display` with `!important`, so a part the script hides stays hidden.
  - `test_the_two_column_rules_need_the_script` (design test 8): every selector inside `@media (min-width:64rem)` starts with `.js `.
  - `test_the_phones_label_for_the_usual_price_is_the_tables_head`: the `content:"…"` before a phone row's fourth cell is `FRONT_HEADS[3] + " "` ("Usually ").
  - `test_no_motion_and_nothing_from_outside`: no `transition`, `animation` or `@keyframes`; no `@import`; every `url(` is a bare name in `FONTS`.
  - `test_print_leaves_out_the_controls`: the print rule hides `.store`, `.search`, `.letters`, `.toc`, `.deals>input` and `.deals>label`.
- [ ] **Step 3: Write the failing tests** for the fonts' maker, `tests/test_subset_fonts.py`, importing the script by its path (`importlib.util`), never fontTools:
  - `test_the_sources_are_pinned_at_the_designs_commits`: `PINNED`'s commits and four SHA-256s are the ones above, and the same as the README's.
  - `test_each_subset_keeps_what_the_stylesheet_sends_it`: the code points of `LATIN` equal those of the two Archivo `@font-face` rules' `unicode-range`s in `look.css`; those of `HEBREW` less U+0020 equal the two Heebo rules'.
  - `test_a_source_that_is_not_the_pinned_one_is_refused`: `verified(b"x", "18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30", "Heebo[wght].ttf")` raises ValueError naming the file; the same bytes' own SHA-256 passes them through.
  - `test_the_tools_must_be_the_pinned_versions`: `check_tools("4.58.0", "1.2.0")` and `check_tools("4.59.0", "1.1.0")` raise; `check_tools("4.59.0", "1.2.0")` does not.
- [ ] **Step 4: Run** `$PY -m pytest tests/test_look.py tests/test_subset_fonts.py -q`. Expected: `test_look.py` passes, since it pins a stylesheet already in place (its mutations, Step 12, prove each test can fail); `test_subset_fonts.py` fails, the script missing. A stylesheet test that fails is a finding against the appendix: report it, never change the stylesheet to pass it.
- [ ] **Step 5: Write `scripts/subset_fonts.py`** to the interface; its docstring says what it makes, from what, with which tools, that it is never in the project's requirements and that CI does not run it. Run its tests. Expected: pass.
- [ ] **Step 6: Make the fonts** in a throwaway environment in the session's scratch folder (`$SCRATCH`), never in the repo:
  1. `$PY -m venv $SCRATCH/fonts-venv`.
  2. A requirements file `$SCRATCH/font-tools.txt` holding `fonttools==4.59.0 --hash=sha256:78813b49d749e1bb4db1c57f2d4d7e6db22c253cb0a86ad819f5dc197710d4b2` and `brotli==1.2.0 --hash=sha256:9e5825ba2c9998375530504578fd4d5d1059d09621a02065d1b6bfc41a8e05ab` (the `cp313-cp313-macosx_10_13_universal2` wheels, PyPI's digests read 2026-11-15).
  3. `$SCRATCH/fonts-venv/bin/pip install --no-deps --require-hashes -r $SCRATCH/font-tools.txt`. It needs the network, as step 4 does; if the session's sandbox refuses either, stop and ask the controller.
  4. `$SCRATCH/fonts-venv/bin/python -I scripts/subset_fonts.py --sources $SCRATCH/fonts-src --out $SCRATCH/fonts-a`, then again with `--out $SCRATCH/fonts-b`. Expected: `cmp` finds each file of `fonts-a` equal to `fonts-b`'s.
  5. The controller hands over the designer's six built assets in a folder, `$DESIGNER`. Expected: `cmp $SCRATCH/fonts-a/archivo-text.woff2 $DESIGNER/archivo-text.97c5421649.woff2`, and the same for `archivo-narrow.woff2` (`archivo-narrow.d5c5f1b561.woff2`), `heebo-hebrew.woff2` (`heebo-hebrew.e5e35b81dd.woff2`), `OFL-archivo.txt` and `OFL-heebo.txt`, each identical. Bytes and SHA-256 expected: `archivo-text.woff2` 25,660, `97c5421649b850b9161c7e708d16a93edf171ce7411eac77718a522cf413505c`; `archivo-narrow.woff2` 11,420, `d5c5f1b561f4f5d6f922928132dfde05cdce396c1a6b64cceb14da856f10aad3`; `heebo-hebrew.woff2` 6,072, `e5e35b81dd2288b1f96083c0d456861645c74fda66056d3bea1cfc40c15883c2`; `OFL-archivo.txt` 4,388, `108b4e57…`; `OFL-heebo.txt` 4,474, `866747cb…`. A file that differs stops the task: report it with both SHA-256s, never commit other bytes.
  6. Copy the five into `src/shopper/static/fonts/`.
- [ ] **Step 7: Write `src/shopper/static/fonts/README.md`**: a table of the five files (name, bytes, SHA-256), each font's family, version, upstream commit, source file and its SHA-256, the licence (SIL Open Font License 1.1, neither family declaring a Reserved Font Name, so the subsets keep their names; the stylesheet calls them "Shelf" and "Shelf Narrow"), and how to make them again (Step 6's commands, with `scripts/subset_fonts.py`). Plain words, no "we".
- [ ] **Step 8: Write the failing tests** for the shared files, `tests/test_assets.py`:
  - `test_each_font_and_licence_is_the_one_its_readme_names` (design test 9): each committed file's bytes and SHA-256 are the README's, and the README's are the five above.
  - `test_a_hashed_name_carries_ten_hex_of_its_bytes`: `hashed("archivo-text.woff2", <its bytes>) == "archivo-text.97c5421649.woff2"`; `hashed("look.css", b"") == "look.e3b0c44298.css"`.
  - `test_the_shared_files_are_the_fonts_the_licences_and_the_stylesheet`: `asset_files()`'s keys are `assets/archivo-text.97c5421649.woff2`, `assets/archivo-narrow.d5c5f1b561.woff2`, `assets/heebo-hebrew.e5e35b81dd.woff2`, `assets/OFL-archivo.txt`, `assets/OFL-heebo.txt` and `STYLESHEET`; `STYLESHEET == "assets/" + hashed("look.css", asset_files()[STYLESHEET])`; the fonts' and licences' bytes are the committed files'.
  - `test_the_stylesheet_names_the_fonts_by_their_hashed_names`: the published stylesheet's `url(...)`s are the three hashed names (Heebo's twice), and with the plain names written back it equals `look.css` byte for byte.
  - `test_a_stylesheet_naming_another_file_is_refused`: with `STATIC` monkeypatched to a copy whose `look.css` adds `url(other.woff2)`, or drops one font's `url(`, `asset_files()` raises ValueError.
  - `test_the_shared_files_stay_small` (design test 10): the published stylesheet under 22,000 bytes; the three fonts under 45,000 together.
  - `test_the_shared_files_are_the_same_bytes_twice`.
- [ ] **Step 9: Run** `$PY -m pytest tests/test_assets.py -q`. Expected: fail, `shopper.assets` missing.
- [ ] **Step 10: Implement `src/shopper/assets.py`**, its docstring saying what the folder holds, how a name is hashed and why (a name changes when its bytes do, so a page cached for its five minutes still finds the stylesheet it names), and that the code fingerprint does not cover these files. Run the three test files. Expected: pass. Then: `$PY -c "import sys; sys.path[:0] = ['src']; from shopper.assets import STYLESHEET; print(STYLESHEET)"` prints `assets/look.dc1312dbfc.css`, and the built stylesheet's bytes equal `$DESIGNER/look.dc1312dbfc.css` (SHA-256 `dc1312dbfcf244d0dfb10a1f68f4fe37d0b26ac2c788de1402672ac82b1f9950`, 20,928 bytes): the appendix with the designer's fonts gives the designer's stylesheet. A difference is a finding.
- [ ] **Step 11: Run** the full test command. Expected: all pass; `assets.py` at 100%.
- [ ] **Step 12: Mutations.** `(q36 look)`, target `LOOK`:
  - "the dark theme's first green too dark for its words" (`--d1:#27995a` to `--d1:#1f7a48`, 3.54:1)
  - "the sale line too pale on paper" (`--sale:#0b7a3b` to `--sale:#2e9e57`, 3.42:1)
  - "small print too pale on paper" (`--ink-2:#555555` to `--ink-2:#8a8a8a`, 3.45:1)
  - "a green label's edge its fill on paper" (the light `--edge:var(--ink)` to `--edge:var(--fill)`)
  - "the dark NO DEAL edge in ink on the dark page" (`--nd-edge:#ffd60a` to `--nd-edge:#111111`)
  - "a colour written outside the tokens" (`.chart text{fill:var(--ink-2)}` to `.chart text{fill:#555555}`)
  - "an undefined token" (`.chart .grid{stroke:var(--line)}` to `stroke:var(--lines)`)
  - "the chart's words at 11 pixels" (`.chart{…font-size:.78125rem` to `.6875rem`)
  - "a chart stroke that scales" (`;vector-effect:non-scaling-stroke` dropped)
  - "the hidden rule without !important"
  - "a two-column rule without the script" (`.js .t-product main{display:grid` to `.t-product main{display:grid`)
  - "the phone's usual label not the table's head" (the first `content:"Usually "` to `content:"Usual "`)
  - "a transition" (`a:hover{text-decoration-thickness:3px}` gains `;transition:all .2s`)

  `(q36 assets)`, target `SHOP_ASSETS`: "a hash of nine hex digits"; "a font's url left unhashed"; "a stylesheet naming another file accepted"; "the stylesheet's name from its plain bytes". `(q36 fonts)`, target `SUBSET_FONTS`: "the Latin subset without the dashes"; "a source not checked against its SHA-256"; "another fonttools accepted". Run `$PY scripts/mutation_check.py "q36 look" "q36 assets" "q36 fonts"`, then the staleness check.
- [ ] **Step 13: Commit:** `git add src/shopper/static/look.css src/shopper/static/fonts src/shopper/assets.py scripts/subset_fonts.py tests/test_look.py tests/test_assets.py tests/test_subset_fonts.py scripts/mutation_check.py && git commit -m "Site look: the shared stylesheet, the design's appendix; Archivo and Heebo subset from pinned upstream commits, byte for byte the design's; shopper.assets names them by hash (q36)"`.

### Task 2: The barcode

Wave 1. Its own worktree, `q36-bars`. Nothing renders it yet: Task 8 puts it on the label.

**Files:**
- Create: `src/shopper/bars.py`, `tests/test_bars.py`
- Modify: `scripts/mutation_check.py` (the target `SHOP_BARS` and a block after the last `(q33 verdict)` entry)

**Interfaces:**
- Consumes: `basket.barcode.is_gs1` (ASCII digits and the GS1 check digit). A code as the site shows it never starts with 0 (`basket.barcode.normalize` strips leading zeros), so `is_gs1` on it is exact.
- Produces:

```python
def modules(code: str) -> str   # the bars as "1" (bar) and "0" (space): EAN-13's 95 for 13 digits whose check digit holds;
                                # for 12 such digits (a UPC-A) the bars of "0" + code; EAN-8's 67 for 8; "" for any other code
def drawing(code: str) -> str   # once a page: '<svg class="defs" aria-hidden="true"><defs><path id="ean" d="M0 .5h95"
                                # stroke-dasharray="1 1 1 3 …"/></defs></svg>', the dashes the runs of modules(code); "" with no bars
def mark(code: str) -> str      # each label's: '<div class="code" aria-hidden="true"><svg viewBox="0 0 95 1" preserveAspectRatio="none">
                                # <use href="#ean"/></svg><small>2000000000046</small></div>'; EAN-8's svg has class="short"
                                # and viewBox "0 0 67 1"; "" with no bars
```

- The tables, written out from GS1's: the L codes of 0 to 9 (`0001101`, `0011001`, `0010011`, `0111101`, `0100011`, `0110001`, `0101111`, `0111011`, `0110111`, `0001011`); a G code is the R code reversed; an R code is the L code with each module flipped; the first digit's parity of the left six (`LLLLLL`, `LLGLGG`, `LLGGLG`, `LLGGGL`, `LGLLGG`, `LGGLLG`, `LGGGLL`, `LGLGLG`, `LGLGGL`, `LGGLGL`). EAN-13: `101`, the six left digits by the parity, `01010`, the six right digits in R codes, `101`. EAN-8: `101`, four L, `01010`, four R, `101`.

- [ ] **Step 1: Write the failing tests** in `tests/test_bars.py`. Codes are synthetic (prefix 2, the GS1 prefix for codes kept inside a store).
  - `test_known_codes_give_their_modules` (worked from the GS1 tables for this plan; the implementer works each again from the tables, and a disagreement is a finding):
    - `modules("2000000000046") == "10100011010001101010011101001110001101010011101010111001011100101110010111001010111001010000101"` (first digit 2, parity `LLGGLG`);
    - `modules("200000000004") == "10100100110001101000110100011010001101000110101010111001011100101110010111001011100101011100101"` (the UPC-A as `0200000000004`, parity `LLLLLL`);
    - `modules("20000004") == "1010010011000110100011010001101010101110010111001011100101011100101"`.
  - `test_every_pattern_has_its_length_and_guards`: over 200 codes of each length made by a seeded `random.Random(36)` with their check digit worked in the test: 95 or 67 modules, `101` at both ends, `01010` at module 45 (EAN-13) or 31 (EAN-8).
  - `test_each_pattern_decodes_to_its_digits`: the test's own decoder, from the same GS1 tables read the other way (the first digit from the left half's parity), gives back each code (a 12-digit one with its leading 0).
  - `test_a_code_that_is_not_a_barcode_gets_no_bars` (Review Focus 1), parametrized: a wrong check digit (`"2000000000047"`); 7, 9, 10, 11 and 14 digits; a letter (`"20000000000A6"`); Arabic-Indic digits (`"٢٠٠٠٠٠٠٠٠٠٠٤٦"`); `""`; a space. Each gives `modules == drawing == mark == ""`.
  - `test_the_drawing_is_one_dashed_path`: for `"2000000000046"` the drawing is exactly `<svg class="defs" aria-hidden="true"><defs><path id="ean" d="M0 .5h95" stroke-dasharray="1 1 1 3 2 1 1 3 2 1 1 1 1 2 3 1 1 2 3 3 2 1 1 1 1 2 3 1 1 1 1 1 3 2 1 1 3 2 1 1 3 2 1 1 3 2 1 1 1 1 3 2 1 1 1 4 1 1 1"/></defs></svg>` (222 bytes); for every code above, the dashes are the runs of its modules, starting with a bar, and sum to 95 or 67.
  - `test_each_label_shows_the_drawing_by_reference`: `mark("2000000000046")` is exactly `<div class="code" aria-hidden="true"><svg viewBox="0 0 95 1" preserveAspectRatio="none"><use href="#ean"/></svg><small>2000000000046</small></div>` (146 bytes); `mark("20000004")`'s svg is `class="short"` with `viewBox="0 0 67 1"`; the digits under the bars are hidden from screen readers (the page's barcode line already says them).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_bars.py -q`. Expected: fail, `shopper.bars` missing.
- [ ] **Step 3: Implement** to the interface. The module's docstring states the encoding, that nothing that looks like a barcode and is not one is ever drawn, and why the bars are always dark on a white plate (a scanner needs them so, in both themes: the stylesheet's `--bars` on `--plate`).
- [ ] **Step 4: Run** the full test command. Expected: all pass; `bars.py` at 100%.
- [ ] **Step 5: Mutations**, `(q36 bars)`, target `SHOP_BARS`: "the check digit not checked"; "a UPC-A drawn without its leading zero"; "the left half all in L codes"; "the right half in L codes"; "the centre guard left out"; "a 14-digit code drawn"; "the digits under the bars read aloud" (`aria-hidden` dropped from the mark); "the drawing's dashes from the bars alone". Run `$PY scripts/mutation_check.py "q36 bars"`, then the staleness check.
- [ ] **Step 6: Commit:** `git add src/shopper/bars.py tests/test_bars.py scripts/mutation_check.py && git commit -m "Site look: a product's barcode drawn from its own digits, EAN-13, UPC-A and EAN-8, and nothing for any other code (q36)"`.

### Task 3: The words

Wave 1. Its own worktree, `q36-words`. The pages take most of these words in Tasks 5, 8 and 9; this task moves only what the words already reach (the reason, "Lowest in the …", the chart's spoken summary).

**Files:**
- Modify: `src/shopper/words.py`, `src/shopper/verdict.py` (`extremes`)
- Test: `tests/test_shop_words.py`, `tests/test_verdict.py`, `tests/test_golden_90.py` (the golden's reason and "Lowest in the" lines where its counts differ), `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py` (a block after the last `(q33 words)` entry)

**Interfaces:**
- Consumes: `Verdict`, `Day` (`shopper.verdict`).
- Produces:

```python
# shopper.verdict
def extremes(found: Verdict) -> tuple[tuple[Decimal, date | None], tuple[Decimal, date | None]] | None
    # (lowest, highest) over the tracked days' day prices and today's price, each with the latest day at that price,
    # None for that day when it is today's; None when no price is known (the design's call 3)
# shopper.words
ROOT_TITLE = "Deal or No Deal?"
ROOT_LINE = "Find out if a sale is actually a deal: pick the store you're in, then look up the product. Each sale is checked against what it usually costs there."
PRICE_TODAY = "Price today:"
STATS_HEADS = ("Lowest", "Highest", "Usual", "Today")
TODAY_WORD = "today"
def short_day(day: date) -> str                       # "16 Aug"
def month_name(day: date) -> str                      # "Sep"
def price_line(found: Verdict) -> str | None          # "Price today: ₪14.00" / "Price today: ₪50.00 a kilogram"; None without today's price
def verdict_words(found: Verdict) -> str              # "DEAL · ₪1.90 off" / "NO DEAL" (today's private _verdict, made public)
def short_verdict(found: Verdict) -> str              # what follows the name in a badge of "Elsewhere today": "DEAL · ₪1.90 off", "no sale today"
def promotions_today(count: int) -> tuple[str, str]   # ("1,347", "promotions today"), ("1", "promotion today")
# changed: reason and last_low name "days with a known price" when the counts differ; chart_summary takes its lowest and
# highest from extremes; short_badge(found) == f"{name} · {short_verdict(found)}"
```

- [ ] **Step 1: Write the failing tests.** In `tests/test_shop_words.py`:
  - `test_the_reason_names_its_own_count_when_it_differs`, rewriting `test_the_reason_counts_the_days_with_a_price` (its forms with a day of unknown price now say "with a known price"): with four tracked days, three of them priced, `reason` gives "Usually ₪11.90, sales included (3 days with a known price).", "It's been ₪9.90 or less on 2 of the 3 days with a known price." and "Only ₪0.90 below its usual ₪5.00 (2 days with a known price)." (that case with three days, two priced); with every day priced, "(3 days tracked)" as today; two days, one priced, "(1 day with a known price)"; `last_low` "Lowest in the 3 days with a known price." and "Lowest in the 1 day tracked."; `how_often` unchanged, "On sale on 2 of the 4 days tracked.".
  - `test_a_page_never_shows_two_numbers_called_days_tracked`: over every verdict of `tests/shopper_random.py`'s histories, the numbers before "days tracked" (or "day tracked") in `reason`, `last_low` and `how_often` together are one number.
  - `test_the_front_pages_words`: `ROOT_TITLE` and `ROOT_LINE` verbatim, as above; `ROOT_TITLE.removesuffix("?").split(" or ") == ["Deal", "No Deal"]`.
  - `test_the_price_line`: "Price today: ₪14.00"; a weighed deal's "Price today: ₪50.00 a kilogram"; None on `unread_today`, `price_unread`, `not_sold` and `too_few`.
  - `test_the_charts_words`: `short_day(date(2026, 8, 16)) == "16 Aug"`, `short_day(date(2026, 11, 7)) == "7 Nov"`, `month_name(date(2026, 9, 1)) == "Sep"`; `STATS_HEADS`; `TODAY_WORD`.
  - `test_the_verdict_alone_and_the_badge_rows_words`: `verdict_words` "DEAL · ₪1.90 off" and "NO DEAL"; `short_verdict` of a deal and of each call without a verdict ("no sale today", "too few files today", "not sold today"); `short_badge(found) == f"{BY_KEY[found.column].name} · {short_verdict(found)}"`.
  - `test_promotions_today`: `promotions_today(1347) == ("1,347", "promotions today")`; `promotions_today(1) == ("1", "promotion today")`.
  - `test_the_summary_counts_today`: a deal whose today's price is a new low says "Price chart: usually ₪22.90, lowest ₪17.90, highest ₪24.90, today ₪17.90." (the design's example).
  - The new words join `test_no_sentence_says_a_never_phrase_or_we`.

  In `tests/test_verdict.py`, `test_lowest_and_highest_count_today`: day prices 24.90 on 13 November and 19.90 on 14 November with today's 17.90 give `((Decimal("17.90"), None), (Decimal("24.90"), date(2026, 11, 13)))`; today's price equal to an earlier lowest gives that lowest's day as None (today is the latest at that price); with no today's price, a tie is dated by its later day; no day price and no today's price gives None; a today's price alone gives it for both.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_words.py tests/test_verdict.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** The words module's docstring gains the new words and the rule for the two counts (site-look.md, "Word changes", 3); `verdict.py`'s docstring states call 3.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the golden's pin, and any golden assertion that quotes a reason or "Lowest in the" line whose counts differ: rewrite those to the new words, each change named in the commit.
- [ ] **Step 5: Repin the golden.** Expected moved names: only `day/` lines, `site/p/` pages and `site/store/` pages (their stories quote the reason); none other. Reason: the reason and "Lowest in the" name their own count when it differs from the days tracked, and the chart's spoken summary counts today.
- [ ] **Step 6: Mutations.** `(q36 words)`, target `SHOP_WORDS`: "the reason saying days tracked when the counts differ"; "the reason naming the known-price count when the counts are equal"; "last this low saying days tracked when the counts differ"; "one day with a known price said as days"; "a short date with its year"; "a month's full name"; "the price line without a kilogram"; "one promotion said as promotions"; "the badge row's name and verdict run together". Target `SHOP_VERDICT`: "the lowest leaving today out"; "the highest leaving today out"; "a lowest of today dated by an earlier day"; "a tie dated by its earlier day". Re-point the `(q33 chart)` mutations on `words.py` whose text moved ("the summary without the usual price", "the summary's lowest from the listed prices alone", "the summary's highest the listed maximum", "the summary without today's price"), or retire one whose rule `extremes` now holds, naming the mutation that guards it there. Run `$PY scripts/mutation_check.py "q36 words" "q33 words" "q33 chart" "q33 verdict"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/words.py src/shopper/verdict.py tests/test_shop_words.py tests/test_verdict.py tests/test_golden_90.py tests/golden/golden-90.sha256 scripts/mutation_check.py && git commit -m "Site look: the decided words; one 'days tracked' on a page; lowest and highest count today (q36)"`, the body naming the repin's moved kinds.

### Task 4: The uploads and the role

Wave 1. Its own worktree, `q36-upload`. Nothing builds `assets/` yet; the tests make their own.

**Files:**
- Modify: `src/basket/site.py`, `scripts/publish.sh`, `template.yaml` (`WriteSite`)
- Test: `tests/test_site.py`, `tests/test_scripts.py`, `tests/test_basket_template.py`
- Modify: `scripts/mutation_check.py` (a block after the last `(q22 publish)` entry)

**Interfaces:**
- Produces:

```python
# basket.site
ASSET_FOLDER = "assets"     # the shared stylesheet, fonts and licences (shopper.assets.FOLDER; Task 6 tests the two agree)
CONTENT_TYPES = {..., ".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}
def upload(self, site_dir, data, with_pages) -> list[str]   # the records first, in a call of their own; then, with the pages,
    # every file under assets/ that the bucket's assets/ listing lacks, in a call of its own, ended before anything else;
    # then the data files and the pages; the keys put, in that order
```

- `scripts/publish.sh`: after `upload --include '*.js' …` and before `upload --include '*.html' …`, three more: `upload --include 'assets/*.css' --content-type 'text/css; charset=utf-8' --size-only`, `upload --include 'assets/*.woff2' --content-type 'font/woff2' --size-only`, `upload --include 'assets/*.txt' --content-type 'text/plain; charset=utf-8' --size-only`. The comment above the uploads says why each asset goes up before the pages and why by size alone.
- `template.yaml`: `WriteSite` gains `- !Sub "arn:aws:s3:::${SiteBucketName}/assets/*"`, after `store/*`; its comment says the site run puts the shared files there, each once.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_site.py`:
    - `test_upload_puts_each_asset_before_any_page` (Review Focus 4): a `MemorySite` that records each `put_files` call's keys; the assets are in a call before the call holding any page or data file, and after the records' call.
    - `test_an_asset_the_bucket_holds_is_not_put_again`: the bucket holds `assets/look.aaaaaaaaaa.css`; the upload puts the other assets, and its returned keys leave that one out.
    - `test_assets_go_up_only_with_the_pages`: `with_pages=False` puts no asset.
    - `test_each_asset_goes_up_with_its_content_type`: `.css` as `text/css; charset=utf-8`, `.woff2` as `font/woff2`, `.txt` as `text/plain; charset=utf-8`, each with `max-age=300`.
    - `test_a_failed_asset_put_stops_the_upload_before_the_pages`: a put of an asset that raises leaves no page and no data file put.
    - `test_keys_and_the_upload_settings_are_those_publish_sh_uses`: `TYPES` gains the three.
    - `test_put_files_refuses_a_file_of_no_known_type_before_any_put`: its case `notes.txt`, now a known type, becomes `notes.md` (stale since `.txt` has a type).
    - `test_no_method_ever_deletes`: unchanged, passing with assets in the build.
  - `tests/test_scripts.py`:
    - `UPLOAD_ORDER` becomes `["*.csv.gz", "*.csv", "*.json", "*.js", "assets/*.css", "assets/*.woff2", "assets/*.txt", "*.html"]`, so `test_publish_sh_uploads_the_data_files_before_the_pages` and `test_publish_sh_stops_on_a_failed_upload` cover the assets; `test_publish_sh_uploads_a_build_the_check_and_the_guard_pass` expects 8 syncs.
    - `a_build` writes `assets/look.0123456789.css`, `assets/archivo-text.0123456789.woff2` and `assets/OFL-archivo.txt`, so `test_publish_sh_sets_each_content_type_and_cache_control` holds every file to one allowlist, its own type's, the three new ones included.
    - `test_publish_sh_puts_an_asset_only_when_the_bucket_lacks_it`: the three asset syncs, and no other, carry `--size-only`.
  - `tests/test_basket_template.py`: `test_role_grants_exactly_what_the_code_does` with `WriteSite` gaining `_site("assets/*")`; `test_role_prefixes_are_the_codes_keys` reading the prefix from `basket.site.ASSET_FOLDER`.
- [ ] **Step 2: Run** those three files. Expected: the new tests fail.
- [ ] **Step 3: Implement**, with `basket.site`'s docstring (the content types' table, the order, an asset put once) and `publish.sh`'s comments updated.
- [ ] **Step 4: Run** the full test command, then `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: all pass, lint clean. `git diff --stat -- site-template.yaml` prints nothing.
- [ ] **Step 5: Mutations**, `(q36 upload)`: `SITE`: "the assets put with the pages"; "an asset the bucket holds put again"; "the assets put for an earlier day"; "a stylesheet served as text/plain"; "a font served as text/plain"; `PUBLISH_SCRIPT`: "the stylesheet uploaded after the pages"; "an asset synced by its time"; "the fonts sent with no content type"; `BASKET_TEMPLATE`: "the role without assets/". Run `$PY scripts/mutation_check.py "q36 upload" "q22 upload" "q22 site run" "q22 publish"`, then the staleness check.
- [ ] **Step 6: Commit:** `git add src/basket/site.py scripts/publish.sh template.yaml tests/test_site.py tests/test_scripts.py tests/test_basket_template.py scripts/mutation_check.py && git commit -m "Site look: the shared files go up once each, before any page names them, in Lambda and by hand; the role may put assets/ (q36)"`.

### Task 5: The chart

Wave 2, after Task 3. Its own worktree, `q36-chart`. `render_product` keeps calling `render_chart(found, day)` until Task 8 passes today's shelf price.

**Files:**
- Modify: `src/shopper/chart.py` (rewritten), `tests/test_chart.py` (rewritten), `tests/test_product.py` (the assertions that read the old SVG: `'<svg class="chart"'`, `aria-labelledby`), `tests/test_golden_90.py` (the same), `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py` (the `(q33 chart)` block, re-pointed or retired in place, and a block after it)

**Interfaces:**
- Consumes: `Verdict`, `Day`, `extremes` (Task 3), `shopper.words` (`CHART_KEY`, `chart_label`, `chart_summary`, `STATS_HEADS`, `TODAY_WORD`, `short_day`, `month_name`), `shopper.measures.whole`.
- Produces:

```python
PLOT = 200                       # the plot's height in pixels; the SVGs beside it are 224 high with the dates (the stylesheet)
AXIS_X, NOW_X = 40, 12           # the axis column's text anchor (46 wide, less 6) and the today column's text start (64 wide)
LABEL_GAP = 17                   # today's two labels' least distance, centre to centre
NEAR = (Fraction(22, 100), Fraction(84, 100))    # a date outside this share of the span is hidden on a phone
WEEKLY_UNDER = 46                # days in the span below which the dates are a week apart, else the months
TICK = Decimal("196.5")          # the unread ticks' line: 7 pixels standing on the date line
def axis(low: Decimal, high: Decimal) -> tuple[Decimal, Decimal, Decimal]    # (bottom, top, step)
def render_chart(found: Verdict, day: date, listed_today: Decimal | None = None) -> str
    # '<div class="history"><div class="chart">…</div><p class="key">…</p><table class="stats">…</table></div>';
    # "" when found.days is empty
```

- The axis, for the lowest and highest of the prices drawn (the shelf prices, the sale prices, the usual price):

```python
def axis(low, high):
    steps = [Decimal("0.5")] if 0 < high - low < 1 else []
    steps += [m * 10 ** k for k in range(0, 9) for m in (1, 2, 5)]        # 1, 2, 5, 10, 20, 50, …
    for step in steps:
        bottom, top = floor(low / step) * step, ceil(high / step) * step
        while (top - bottom) / step < 2:                  # one price, or two close ones: room on the side with less
            if bottom >= step and low - bottom <= top - high:
                bottom -= step
            else:
                top += step
        if low - bottom < Decimal("0.08") * (top - bottom) and bottom >= step:   # no price on the date line
            bottom -= step
        if (top - bottom) / step <= 5:
            return bottom, top, step
```

  A height is `up(price) = whole(Fraction(top - price) / Fraction(top - bottom) * PLOT)`, whole pixels, half up.
- The markup, in this order (the design's "How it is drawn"; no `style` attribute, no `width` or `height` attribute anywhere):
  - `<div class="chart">`, then `<svg class="ax" aria-hidden="true">`: a `<text x="40" y="{up(t) + 4}">` per tick, top to bottom, "₪26" for a whole shekel, "₪4.50" for a half.
  - `<div class="plot">`, then `<svg class="lines" role="img" aria-label="{chart_summary(found)}" viewBox="0 0 {span} 200" preserveAspectRatio="none">`, where `span` is the days from the first tracked day to today, today included, and day `d` is the unit from `(d - first).days`. It holds, in order: `<path class="grid">` (`M0 {y}H{span}` at each tick above the bottom); `<path class="usual">` with a Deal or No deal, at the usual price over the shelf line's days; `<path class="listed">`; `<path class="sale">` when it has a day; `<path class="unread">` at `TICK` when it has a day. Each is a step line: each run of consecutive days from an `M{x} {y}`, `H{x}V{y}` where the height changes, and `H{last + 1}` at the run's end, so a day with no record is a gap in every line and a run of one price is one segment. It holds no text.
  - `<svg class="over" aria-hidden="true">`: with a usual price, `<text class="usually" x="100%" dx="-12" y="…">` in `chart_label("usually", …)`'s words; then the first tracked day's `<text y="217">{short_day(first)}</text>`; then, for each day after the first and before today that is a month's first day (a span of `WEEKLY_UNDER` days or more) or a whole number of weeks before today (a shorter span), `<line x1="{p}%" x2="{p}%" y1="200" y2="206"/>` and `<text x="{p}%" dx="5" y="217">` with `month_name` or `short_day`, `class="near"` when the day's share of the span is outside `NEAR`. `p` is the day's x over `span` times 100, two places half up, trailing zeros dropped ("17.58", "50").
  - The usual label's `y`: with `level = up(usual)` and `busy` the heights of the shelf and sale points on the last 30% of the span's days, it sits above the line (`level - 6`) when `level >= 20` and no busy height is in `[level - 21, level - 1]`, or when below is busy too (no busy height in `[level + 1, level + 21]` fails, or `level > 180`); else below (`level + 15`).
  - `</div>`, then `<svg class="now" aria-hidden="true">`: for today's shelf point and today's sale point, by "The chart, call by call", sorted by height, a `<circle class="listed|sale" cy="{y}" r="4.5"/>` and `<text class="listed|sale" x="12" y="{centre + 5}">₪17.90</text>`, the centres pushed `LABEL_GAP` apart downward and then back up to at most 200; the lower price (the larger `y`; both when equal) adds `now` to its text's class; then `<text class="end" x="12" y="217">today</text>`.
  - `</div>`, then the key, `<p class="key">`: `<i class="{mark}"></i>{words}` for each mark drawn, today's included, in `CHART_KEY`'s order, set apart by " · ".
  - The table, `<table class="stats"><tr>` a `<th scope="col">` per cell `</tr><tr>` a `<td>` per cell `</tr></table>`: "Lowest" and "Highest" from `extremes(found)`, each figure followed by `<small>` and its day (`short_day`, or `TODAY_WORD` for today's); "Usual" with a usual price; "Today" with today's price. No table when it has no cell.
- Today's points follow "The chart, call by call": the shelf point at `listed_today` when given; the sale point at `found.today_price` when `found.counting` and it is known; the tick under today on `price_unread`.

- [ ] **Step 1: Write the failing tests** in `tests/test_chart.py`, rewritten (the old tests of today's dashed line, the side labels, `DAY_WIDTH` and the labels' column go with their rules):
  - `test_the_axis_takes_round_steps`, parametrized, `axis(low, high) == (bottom, top, step)`: (17.90, 24.90) → (16, 26, 2); (5.00, 5.00) → (4, 6, 1); (6.90, 8.90) → (6, 9, 1); (4.20, 4.50) → (4.0, 5.0, 0.5); (3.00, 3.40) → (2.5, 3.5, 0.5); (10.10, 13.90) → (9, 14, 1); (10.10, 14.90) → (8, 16, 2); (19.90, 69.90) → (0, 80, 20); (99.90, 129.90) → (90, 130, 10); (1000.00, 1450.00) → (800, 1600, 200); (0.40, 0.40) → (0, 2, 1). (Worked for this plan from the rule above; a disagreement is a finding.)
  - `test_no_price_sits_on_the_date_line` (Review Focus 2): over 1,000 pairs from a seeded `random.Random(36)`, shekel prices from 0.10 to 2,000.00: two to five steps, `bottom <= low` and `top >= high`, and `low - bottom >= 0.08 * (top - bottom)` unless `bottom` is 0.
  - `test_only_the_lines_scale_and_they_hold_no_text` (design test 4): exactly one `<svg` with a `viewBox`, the lines', with `preserveAspectRatio="none"` and no `<text`; no `width=`, `height=` or `style=` anywhere.
  - `test_a_day_is_one_unit_and_today_is_the_last`: a 14-day and a 90-day history each give `viewBox="0 0 {span} 200"`, the span counting today; the shelf line of a history listed every day ends at `H{span}` when today's shelf price is given.
  - `test_a_day_with_no_record_is_a_gap_in_every_line`: a promotion hole between two tracked days starts the shelf, sale and usual lines again with an `M` after it, with nothing across it.
  - `test_the_shelf_line_runs_through_today_only_with_todays_shelf_price`: with `listed_today` the last run ends at `H{span}` and the today column has a `circle class="listed"`; without it the run ends at `H{span - 1}` and the column holds "today" alone.
  - `test_a_sale_that_starts_today_is_a_short_green_line_ending_in_its_dot` (Review Focus 5): a deal whose sale starts today gives `<path class="sale" d="M{span - 1} {y}H{span}"/>` and a `circle class="sale"` at `cy="{y}"`.
  - `test_a_sale_day_of_unknown_price_is_a_tick_on_the_date_line`: such a day gives `<path class="unread" d="M{x} 196.5H{x + 1}"/>`; `price_unread` adds today's.
  - `test_todays_prices_are_written_in_their_lines_colours`: a deal gives a `text class="listed"` with the shelf price and a `text class="sale now"` with today's price; two prices 10 pixels apart are labelled 17 apart; no label's centre below 200.
  - `test_the_usual_line_and_its_label`: drawn only with a Deal or No deal, over the shelf line's days with the same gaps; its label above the line, and below it when the last 30% of the span's shelf or sale heights run within 21 pixels above.
  - `test_the_dates_by_span`: a 14-day span, 1 to 14 November, has "1 Nov" at x 0 and one mark, at 7 November (`p` "42.86"), none on today; a 90-day span, 16 August to 13 November, has "16 Aug" and marks at "Sep" (`p` "17.78"), "Oct" ("51.11") and "Nov" ("85.56"), where "Sep" and "Nov" carry `class="near"` (nearer than 22% of the span to the first date, and than 16% to today) and keep their marks, and "Oct" does not.
  - `test_a_short_history_has_its_first_date_and_today` (Review Focus 5): one tracked day and today give the first date, "today" and no mark between.
  - `test_the_table_counts_today_in_lowest_and_highest` (the design's call 3): a deal at a new low reads "Lowest ₪17.90 today", "Highest ₪24.90 13 Nov", "Usual ₪22.90", "Today ₪17.90"; `no_sale` has no "Usual"; `unread_today` and `not_sold` no "Today".
  - `test_the_text_alternative_is_the_summary`: the lines' `aria-label` is `chart_summary(found)`, escaped.
  - `test_the_key_names_only_the_marks_drawn`, `test_a_run_of_one_price_is_one_segment`, `test_no_chart_without_a_tracked_day`, `test_the_chart_is_the_same_bytes_twice` (the days in any order), kept to the new markup.
  - `test_ninety_days_of_daily_changes_stay_small`: a price change every day of 90 and a three-day sale every week, with its key and table, under 3,500 bytes; the size goes in "Deviations".
- [ ] **Step 2: Run** `$PY -m pytest tests/test_chart.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** `chart.py`'s docstring is rewritten to the drawing rules above and "The chart, call by call"; it no longer names the old style.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the golden's pin; `chart.py` at 100%. Rewrite the product page's and the golden's assertions that read the old SVG (`'<svg class="chart"'`, `aria-labelledby="chart-…"`) to the new markup (`<div class="history">`, the lines' `aria-label`).
- [ ] **Step 5: Repin the golden.** Expected moved names: every `day/` line with a product page, the `site/p/` pages; nothing else. Reason: the price chart redrawn (the axis, the dates, the step lines, today at the right, the table).
- [ ] **Step 6: Mutations.** The twenty `(q33 chart)` mutations, each re-pointed where its rule stays ("an untracked day drawn across", "a sale stretch on a day off sale", "the unknown-price mark at the listed price's height", "the text alternative left out", "a run of one price drawn day by day", "the days drawn in the order given", "the key naming every mark, drawn or not", "the key's entries run together", "today's price left out of the heights" as today's prices left out of the axis, "the span a fixed 90 days") and retired where it does not ("the dashed line stopping at today", "today's dot at the usual price", the side labels' four, "the labels drawn over each other" and "the labels stacked at the top" re-pointed to today's labels if the builder finds the rule the same, else retired); Task 3 has already handled the summary's. New, `(q36 chart)`, target `SHOP_CHART`: "the axis from zero"; "six steps allowed"; "a price on the date line" (the 8% rule dropped); "no half-shekel step for prices under a shekel apart"; "a gap bridged in the usual line"; "a sale starting today not drawn"; "the shelf line stopping before today with today's shelf price known"; "today's labels drawn over each other"; "the higher of today's prices in bold"; "the dates a week apart on a long history"; "a date near an end shown on a phone"; "the table's lowest leaving today out"; "a lowest of today given a date"; "text in the lines' SVG"; "the lines' SVG keeping its aspect". Run `$PY scripts/mutation_check.py "q36 chart" "q33 chart" "q33 product"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/chart.py tests/test_chart.py tests/test_product.py tests/test_golden_90.py tests/golden/golden-90.sha256 scripts/mutation_check.py && git commit -m "Site look: the price chart with a ₪ axis, dates and step lines; four SVGs, only the lines stretching, so no word shrinks; lowest and highest in a table (q36)"`, the body listing each retired mutation with its rule.

### Task 6: The shell, the head and every page's frame

Wave 2, after Task 1. Its own worktree, `q36-shell`. Every page links the stylesheet in place of its style block, names its kind, and the build writes `assets/`.

**Files:**
- Modify: `src/shopper/shell.py`, `src/basket/page.py` (`Frame`, `_page`; `BASE_STYLE` and `BASKET_STYLE` removed with their last caller; `STYLE` kept), `src/shopper/pages.py` (the style constants go; each `page(…)` passes its kind; `render_basket`'s frame), `src/shopper/product.py` (`BADGE_STYLE`, `PRODUCT_STYLE` go), `src/shopper/search.py` (`BROWSE_STYLE` goes, the `NORMALIZE` table untouched), `src/shopper/build.py` (the fixed files gain `asset_files()`)
- Test: `tests/test_product.py`, `tests/test_shop_pages.py`, `tests/test_search.py`, `tests/test_page.py`, `tests/test_shop_build.py`, `tests/test_basket_handler.py` (the built site's listing gains `assets`), `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py` (a block after the last `(q33 picker)` entry)

**Interfaces:**
- Consumes: `shopper.assets.STYLESHEET`, `asset_files`, `FOLDER` (Task 1); `basket.site.ASSET_FOLDER` (Task 4).
- Produces:

```python
# shopper.shell
KINDS = ("front", "store", "product", "browse", "method", "record", "basket")    # the body's class, t-<kind>
def head(up: str) -> str      # '<link rel="stylesheet" href="{up}{STYLESHEET}">\n<script src="{up}search.js" defer></script>'
def band(day: date, up: str, front: bool = False) -> str
    # '<header class="band"><div class="wrap"><a class="brand" href="{up}index.html"><b>Deal</b> or No Deal</a>'
    # + the store line as today + (front only) '<p class="dateline">{CHAINS_LINE}</p>' + the date line + '</div></header>'
def page(title, main, day, collected_by, links, kind: str, up: str = "../", store: str | None = None) -> str
    # `kind` in KINDS (ValueError otherwise) in place of `style`; the head is head(up) after <title>; <body class="t-{kind}">;
    # the band is band(day, up, front=kind == "front")
# basket.page
@dataclass(frozen=True)
class Frame:                  # `script` goes
    band: str; credit: str; item_link: Callable[[str], str | None]; method_href: str
    note: str = ""
    head: str = ""            # HTML written after <title> in place of the style block ("" keeps <style>{STYLE}</style>)
    kind: str = ""            # the body's class, t-<kind> ("" keeps a bare <body>)
```

- The brand is `SITE_NAME`'s first word in `<b>` and the rest after it, so its text read is `SITE_NAME`. The kinds: `index.html` front, `store/*` store, `p/*` product, `browse/*` browse, `method.html` method, `record.html` record, `basket.html` basket (`Frame(head=head(""), kind="basket", band=band(day, ""))`).

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_shop_pages.py`:
    - `test_every_page_links_the_one_stylesheet_at_its_depth`: the root, method, record and basket pages end their head with `<link rel="stylesheet" href="{STYLESHEET}">\n<script src="search.js" defer></script>\n</head>`; a store page with `../`; none holds `<style` or a `style=` attribute.
    - `test_every_page_names_its_kind_on_its_body`: `<body class="t-front">`, `t-store`, `t-method`, `t-record`, `t-basket`.
    - `test_the_chains_line_is_on_the_front_page_only`: `CHAINS_LINE` in `index.html`'s header; in no other page's.
    - `test_basket_html_takes_the_sites_frame_whole`: the frame's head and kind, the site's band.
  - `tests/test_product.py`:
    - `test_the_brand_dresses_its_first_word`: `<a class="brand" href="../index.html"><b>Deal</b> or No Deal</a>`, its text read `SITE_NAME`.
    - `test_a_product_page_links_the_stylesheet_and_the_one_script`, rewriting `test_a_product_page_carries_the_one_script_and_the_pick_link`: one `<link`, the stylesheet's at `../`; one `<script`; with both taken out, no `https?:`, `//`, `@import`, `url(`, `<link`, `<img`, `<iframe` or `src=`.
    - `test_page_refuses_a_kind_it_does_not_know`.
    - Rewritten to the new head: `test_the_shell_band_and_footer`, `test_the_product_page_and_the_browse_pages_share_one_shell` (the same head, band and footer frame, the title and kind aside).
    - `test_nothing_is_hidden_without_the_script` keeps its HTML half (the only `hidden` is the Elsewhere heading's); its style half is Task 1's `test_nothing_is_hidden_but_by_a_named_rule`.
    - Retired with their rules: `test_the_charts_style` (the chart's strokes are the stylesheet's, Task 1); `test_every_shade_reads_in_both_themes` (Task 1's contrast test reads the stylesheet); the grey half of `test_a_no_deal_badge_is_grey_and_writes_its_words` (NO DEAL is the owner's yellow, pinned by Task 1's tokens; its words half stays); `test_the_style_split_keeps_the_baskets_block_byte_for_byte`, moved to `tests/test_page.py` as `test_the_baskets_own_style_keeps_its_bytes` (`STYLE`'s SHA-256 `8179d0e4d8567b8c1426100ab5f171aee6dd502f2d84fc87ae5848f83ce768b4`).
  - `tests/test_search.py`: a browse page's head and `<body class="t-browse">`.
  - `tests/test_page.py`: `test_a_frame_with_a_head_writes_it_in_place_of_the_style_and_the_baskets_own_pages_keep_their_bytes`, rewriting the script test: with `head` and `kind`, `<title>…</title>\n{head}\n</head>\n<body class="t-basket">` and no `<style`; a frame without them, and the basket's own pages, `<style>{STYLE}</style>\n</head>\n<body>`, with the index's and method page's SHA-256 pins unchanged (`1700a3aa625e52bc4a1cf1e77991bc34c83eb8c174eabceccb4d58f2c757eaf1`, `6c873ce3a1bb6100a5cbd51e4399e23a70f0027b9d609cd266e3c681b0e391c3`).
  - `tests/test_shop_build.py`: `test_the_build_writes_the_shared_files`: the site's `assets/` holds `asset_files()` byte for byte and nothing else; `outcome.pages` lists them; `shopper.assets.FOLDER == basket.site.ASSET_FOLDER`.
- [ ] **Step 2: Run** those files. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Remove each style constant and every reference to it (afterwards `grep -rn "BADGE_STYLE\|PRODUCT_STYLE\|PAGE_STYLE\|ROOT_STYLE\|STORE_STYLE\|METHOD_STYLE\|RECORD_STYLE\|BROWSE_STYLE\|BASE_STYLE\|BASKET_STYLE" src tests scripts` prints only `scripts/mutation_check.py`'s retired names until Step 6 removes them, then nothing). Edit `search.py` by deleting the `BROWSE_STYLE` block and the argument alone; then `$PY -I -c` the staleness check prints the `(q22 search)` texts still found. Rewrite the docstrings that describe the old style: `shopper.shell` (the stylesheet link, the body's kind, the brand, the chains' line on the front page only), `basket.page`'s "Look" and "The shopper site's frame", `shopper.product`'s last paragraphs, `shopper.pages`', `shopper.search`'s.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the golden's pin.
- [ ] **Step 5: Repin the golden.** Expected moved names: all 91 `day/` lines; every final page, `site/index.html`, `site/method.html`, `site/record.html`, `site/basket.html`, the 12 `site/browse/`, 16 `site/p/` and 9 `site/store/` pages; and six new lines, `site/assets/` (three fonts, two licences, the stylesheet). No `site-days/`, `days/`, `forecasts/`, `scores/`, ledger, `site/search/` or `site/search.js` line. Reason: one shared stylesheet in place of each page's style block, the body's kind, the brand, the chains' line on the front page only.
- [ ] **Step 6: Mutations.** `(q36 shell)`: `SHOP_SHELL`: "the stylesheet linked from the page's own folder"; "the body without its kind"; "the chains' line on every page"; "the brand without its green box"; "a kind the shell does not know accepted". `PAGE`: "basket.html with the basket's own style" (the frame's head ignored); "the basket's own pages with a body class". `SHOP_BUILD`: "the shared files not written". Retire, each in the commit with its rule: "a page without the base style (q22 product)", "the base style without the footer's rules (q22 product)", "the base style holding the basket's tables (q22 product)" (the shopper pages' style blocks), "the store pages without the badges' shades (q33 front)" (the shades are the stylesheet's), "the style without its hidden rule (q33 product)" (the rule is the stylesheet's: Task 1's "the hidden rule without !important"). Re-point "the basket's style out of its old order (q22 product)" to `PAGE` (its test moved), and every mutation whose text the new head, band or `page` call moved ("the shell without the one script (q22 pages)", "the site's name linked from the page's own folder (q22 product)", "a script tag (q22 product)" and the others the staleness check names). Run `$PY scripts/mutation_check.py "q36 shell" "q22 product" "q22 pages" "q22 search" "q33 picker" "q33 product" "q33 front"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper src/basket/page.py tests scripts/mutation_check.py && git commit -m "Site look: every page links the one shared stylesheet in place of its style block and names its kind; the brand's DEAL on its label; the chains' line on the front page only; the build writes assets/ (q36)"`, the body naming the repin's kinds and each retired mutation.

### Task 7: The site check's new rules

Wave 3, after Tasks 1 and 6. Its own worktree, `q36-check`.

**Files:**
- Modify: `src/shopper/check.py`
- Test: `tests/test_shop_check.py`
- Modify: `scripts/mutation_check.py` (a block after the last `(q22 check)` entry)

**Interfaces:**
- Consumes: `shopper.assets` (`STYLESHEET`, `FOLDER`, `FONTS`, `LICENCES`, `hashed`).
- The rules, added to `check_site` and its docstring:
  1. A page's `<link` tags are exactly one, `<link rel="stylesheet" href="<up><STYLESHEET>">` with `up` "../" for each folder the page is in; any other `<link`, a second, or none is refused.
  2. No `<style` as written, and no tag with a `style` attribute.
  3. `assets/` holds exactly: `STYLESHEET`, each `.woff2` the stylesheet names, and `OFL-archivo.txt` and `OFL-heebo.txt`; anything else there is refused, and each of them missing is a problem.
  4. The stylesheet holds no `@import`, and each `url(…)` in it is a bare file name (no scheme, no `/`, no quote mark) ending `.woff2` that is in `assets/`.
  5. Each hashed file of `assets/` (the stylesheet and the fonts) carries in its name the first ten hex digits of its own SHA-256.

- [ ] **Step 1: Write the failing tests** in `tests/test_shop_check.py`, each breaking a copy of the built site and asserting its problem line, naming the file and the rule; alone where it can be (a test that edits the stylesheet's bytes also breaks rule 5, and that is then the only other line):
  - rule 1: `test_a_second_stylesheet_fails`; `test_a_stylesheet_at_the_wrong_depth_fails` (a product page linking `assets/…` with no `../`); `test_a_page_without_the_stylesheet_fails`; `test_another_link_fails` (`<link rel="icon" href="search.js">`);
  - rule 2: `test_a_style_block_fails`; `test_a_style_attribute_fails`;
  - rule 3: `test_a_stray_file_in_assets_fails` (`assets/notes.txt`); `test_a_missing_font_or_licence_fails`, parametrized over the five; `test_a_second_stylesheet_in_assets_fails`;
  - rule 4: `test_an_import_in_the_stylesheet_fails`; `test_a_font_url_from_elsewhere_fails`, parametrized (`url(https://example.org/a.woff2)`, `url(//example.org/a.woff2)`, `url(/a.woff2)`, `url(../p/a.woff2)`, `url("a.woff2")`); `test_a_url_to_a_file_not_in_assets_fails`; `test_a_url_to_a_file_that_is_not_a_font_fails` (`url(OFL-heebo.txt)`);
  - rule 5: `test_an_asset_whose_name_is_not_its_hash_fails` (one font's bytes changed).

  The built site still passes (`test_a_built_site_passes`, or its existing name), and the existing other-origin test (`<link>` to another origin) still names its rule.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_shop_check.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement**, the module's docstring gaining the five rules in its plain words.
- [ ] **Step 4: Run** the full test command. Expected: all pass. No golden change.
- [ ] **Step 5: Mutations**, `(q36 check)`, target `SHOP_CHECK`, one a rule: "a second stylesheet passes"; "a stylesheet at any depth passes"; "a page with no stylesheet passes"; "another link passes"; "a style block passes"; "a style attribute passes"; "a stray file in assets passes"; "a missing licence passes"; "an import passes"; "a font from another origin passes"; "a url to a file not in assets passes"; "a url to a file that is not a font passes"; "an asset's name not its hash passes". Re-point the `(q22 check)` mutations the edits moved. Run `$PY scripts/mutation_check.py "q36 check" "q22 check"`, then the staleness check.
- [ ] **Step 6: Commit:** `git add src/shopper/check.py tests/test_shop_check.py scripts/mutation_check.py && git commit -m "Site look: the site check holds every page to the one stylesheet and no inline style, and assets/ to the stylesheet, the fonts it names and their licences, each named by its hash (q36)"`.

### Task 8: The product page: the label, the price part, the barcode, "Elsewhere today"; the 45,000-byte measure

Wave 3, after Tasks 2, 3, 5 and 6. Its own worktree, `q36-product`. Its Step 7 measures the largest real page before anything else is built on this markup.

**Files:**
- Modify: `src/shopper/product.py`
- Test: `tests/test_product.py`, `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py` (a block after the last `(q33 product)` entry), and this plan's "Deviations" (the sizes)

**Interfaces:**
- Consumes: `drawing`, `mark` (Task 2); `price_line`, `verdict_words`, `short_verdict` (Task 3); `render_chart(found, day, listed_today)` (Task 5); `page(…, "product")` (Task 6).
- Produces: `render_product`'s signature unchanged. The page, top to bottom: the title, the names, the barcode line, then `drawing(covered.code)` once when the code has bars; the badge row; a section per column; `ALWAYS_SENTENCE`. A section:

```html
<section data-column="k" id="c-k" data-chain="slug"><h2>{name}</h2>[<p class="warn">…</p>]
<div class="tag {badge_class}"><div class="say">
  <p class="verdict">At {name}: <b>{verdict_words}</b></p> | <p class="verdict">{NO_VERDICT[call]}</p>
  [<p class="reason">…</p>][<p class="conditions">…</p>][<p>A sale starts on …</p>]
</div>[<div class="pay">[<p class="price">Price today: <b><i>₪</i>14<sup>.00</sup></b>[<small> a kilogram</small>]</p>][mark(code)]</div>]</div>
| <p class="few">…</p> | <p class="not-sold">…</p>
{render_chart(found, day, listed_today)}
[<p class="fact">Last this low: …</p>][<p class="fact">On sale on …</p>]
<details>…</details></section>
```

  (written on one line, as today; "The label, call by call" says which form). `listed_today` is `Decimal(money(point.listed))` when the point exists, has a listed price and `today.record`, and the call is neither `price_unread` nor `unread_today`; else None. The price's figure is today's price as shown, split at its point: the shekels, then `<sup>` with the point and the agorot. A badge of the row: `<a data-column="{key}" href="#c-{key}" class="badge {badge_class}">{name}<i> · </i><b>{short_verdict}</b></a>`.

- [ ] **Step 1: Write the failing tests** in `tests/test_product.py`:
  - `test_a_deal_is_a_green_label_in_its_shade`: a ₪3.00 deal at Shufersal Deal gives `<div class="tag deal-2"><div class="say"><p class="verdict">At Shufersal Deal: <b>DEAL · ₪3.00 off</b></p><p class="reason">`; the verdict's text read is `badge(found)`.
  - `test_no_deal_is_the_yellow_label`: `<div class="tag no-deal">` with `<b>NO DEAL</b>` (its colours are the stylesheet's `--nd` tokens, Task 1).
  - `test_each_line_that_is_not_a_verdict_is_a_plain_label`, parametrized over `NO_VERDICT`'s calls, rewriting `test_each_no_verdict_line`: `<div class="tag none"><div class="say"><p class="verdict">{NO_VERDICT[call]}</p>`, the line verbatim; `too_few` gives `<p class="few">` and `not_sold` `<p class="not-sold">`, neither inside a `tag`.
  - `test_the_price_part_sets_todays_price_as_on_a_shelf_edge`: today's 14.00 gives exactly `<p class="price">Price today: <b><i>₪</i>14<sup>.00</sup></b></p>`, whose text with its tags removed is `price_line(found)`; a weighed deal adds `<small> a kilogram</small>` and reads "Price today: ₪50.00 a kilogram"; `unread_today` and `price_unread` have no `class="price"`; `too_few` and `not_sold` no `class="pay"`.
  - `test_the_label_carries_the_products_barcode`: `drawing(code)` once, right after the barcode line, so `id="ean"` once; every label's `pay` part ends with `mark(code)`; a `price_unread` label's part holds the mark alone.
  - `test_a_product_with_no_bars_has_no_drawing_and_no_mark` (Review Focus 1): an 11-digit code gives no `<svg class="defs"`, no `<use`, a `pay` part holding the price alone, and the barcode line with its digits.
  - `test_the_chart_takes_todays_shelf_price_from_the_day`: a section's history is `render_chart(found, DAY, Decimal(money(point.listed)))` on a record day, and `render_chart(found, DAY, None)` on a hole, for a product not sold today, and on `price_unread` and `unread_today` (the owner's ruling of 2026-11-16 and the design's state table: their chart's today column holds "today" alone, no `<circle` and no `₪`).
  - `test_the_facts_follow_the_history`: the section reads label, `<div class="history">`, `<p class="fact">` for "Last this low" and for "On sale on", then `<details>`.
  - `test_elsewhere_badges_read_as_their_words`: each badge's markup as above; its text with tags removed is `short_badge(found)`.
  - Rewritten to the new markup, their rules unchanged: `test_each_section_says_the_verdict_with_the_store_types_name`, `test_with_the_script_blocked_every_store_types_part_is_in_the_html` (each section's label, history and facts, in `COLUMNS` order), `test_a_weighed_deal_is_per_kilogram`, `test_a_product_sold_nowhere_today_has_no_badges_and_every_part` (`<div class="history">` in place of `<svg class="chart"`), `test_the_largest_page_is_under_60_kb` (`MAX_PAGE`; its size goes in "Deviations"; 42,314 bytes at 16fb85b, measured for this plan).

  In `tests/test_golden_90.py`: the product pages' assertions in `test_the_golden_pages_windows_and_gaps` read the new markup (the words unchanged but Task 3's); `test_every_golden_product_page_is_under_45_000_bytes` (design test 10; the golden's largest is 18,674 bytes at 16fb85b, measured for this plan).
- [ ] **Step 2: Run** `$PY -m pytest tests/test_product.py tests/test_golden_90.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Rewrite `product.py`'s docstring to the label, the price part, the barcode and the badge's markup.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the golden's pin.
- [ ] **Step 5: Repin the golden.** Expected moved names: every `day/` line and the 16 `site/p/` pages; nothing else. Reason: the verdict as a shelf label with its price part and barcode; the facts ruled; the badges' markup.
- [ ] **Step 6: Mutations.** `(q36 product)`, target `SHOP_PRODUCT`: "a deal's label without its shade"; "no deal on the plain label"; "a line that is not a verdict on a deal's label"; "the price part on a day with no price today"; "the agorot left off the price"; "a kilogram's price without its unit"; "the barcode's drawing in every part"; "a mark with no drawing on the page"; "today's shelf price on a hole"; "today's shelf price on an unread sale price"; "today's shelf price on a day whose sale prices were not read"; "the chart without today's shelf price"; "a badge's name and verdict run together"; "the facts before the chart". Re-point the `(q33 product)` and `(q22 product)` mutations whose text moved ("the chart left out", "the reason line left out", "the store type's name left out of the verdict" and the others the staleness check names). Run `$PY scripts/mutation_check.py "q36 product" "q33 product" "q22 product"`, then the staleness check.
- [ ] **Step 7: Measure a real day** (the day under "Where the design leaves room"):
  1. `PYTHONPATH=src $PY -m shopper.build --day <the day> --collected-by 12:03 --data /Users/doronreiffman/Projects/il-grocery-prices/data --site site`, into the worktree's `site/`.
  2. `PYTHONPATH=src $PY -m shopper.check site`. Expected: exit 0.
  3. `find site/p -name '*.html' -exec stat -f '%z %N' {} + | sort -n | tail -3`, and the median.
  4. Expected: the largest page under 45,000 bytes (the design estimates 43,100 to 43,700 bytes for a page as large as store-first's 39,264 grown as the measured pages did). Write in "Deviations": the largest page, its barcode, the median, the history's days of records, the synthetic worst case and the golden's largest.
  5. If the largest page is over 45,000 bytes: stop and report it with its bytes part by part (each part's label, chart, key, table, mark; the drawing; the rest). Nothing is cut without the owner's word; the order to propose is under "Where the design leaves room".
- [ ] **Step 8: Commit:** `git add src/shopper/product.py tests/test_product.py tests/test_golden_90.py tests/golden/golden-90.sha256 scripts/mutation_check.py docs/site-look-plan.md && git commit -m "Site look: a product page's verdict as a shelf label, green in the shade of its saving or yellow for NO DEAL, the price as on a shelf edge with the product's barcode, the chart through today (q36)"`.

### Task 9: The front page and the store pages

Wave 3, after Tasks 3 and 6. Its own worktree, `q36-front`.

**Files:**
- Modify: `src/shopper/pages.py`, `src/shopper/build.py` (`render_root`'s call), `scripts/time_site_run.py` (the same call)
- Test: `tests/test_shop_pages.py`, `tests/test_shop_build.py`, `tests/test_siteday.py`, `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py` (a block after the last `(q33 front)` entry)

**Interfaces:**
- Consumes: `ROOT_TITLE`, `ROOT_LINE`, `promotions_today`, `verdict_words` (Task 3); the shell (Task 6).
- Produces:

```python
def promotions_shown(front: StoreFront, today: ColumnDay) -> int | None   # front.promotions on a day read; None on a hole or a
    # promotion hole: the one number the store page's fold-out line and the front page's label both show
def render_root(day: date, collected_by: str, fronts: Mapping[str, StoreFront],
                column_days: Mapping[tuple[str, date], ColumnDay]) -> str
```

- The root, at `up=""`, tab title `SITE_NAME`: `<div class="hero"><h1><span class="yes">Deal</span> or <span class="no">No Deal</span>?</h1>`, a line break, `<p class="lede">{ROOT_LINE}</p></div>` (the two words from `ROOT_TITLE.removesuffix("?").split(" or ")`); the picker, `<section id="pick" data-page="root"><h2>{PICK_TITLE}</h2>`, then each chain of `PICK_GROUPS` as `<div class="chain"><h3>{chain}</h3><ul>…</ul></div>`, each store type `<li><a href="store/{key}.html">{name} <small><b>1,347</b> promotions today</small></a></li>`, the `<small>` only when `promotions_shown` is a number; the hiring line, `<p class="hiring">` with its four links and nothing between them.
- A store page: `<p class="at">{name}</p>`, `<h1 id="deals">Is it actually a <span class="yes">deal?</span></h1>` (`FRONT_TITLE`'s last word on the label); the lead line with "{N:,} of {M:,}" in `<b>` when it is the headline (`store_lead`'s words unchanged); the table with its roles: `role="table"` on the table, `rowgroup` on `thead` and `tbody`, `row` on each `tr`, `columnheader` on each `th scope="col"`, `rowheader` on each `th scope="row"`, `cell` on each `td`, the "No deals to show." row's included; a row's badge `<span class="badge {class}">{verdict_words(found)}</span>`; the fold-out's promotions line from `promotions_shown`. The story keeps `badge(found)`, naming the store type.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_shop_pages.py`:
    - `test_the_front_headline_is_deal_or_no_deal`: the `<h1>` above, its text read `ROOT_TITLE`; `ROOT_LINE` in the hero's lede; `<title>Deal or No Deal</title>`.
    - `test_each_store_label_carries_its_promotions_today` (Review Focus 3): a front of 1,347 gives `Carrefour Market <small><b>1,347</b> promotions today</small>`; of 1, "promotion today"; on a hole and on a promotion hole the label is the name alone, with no `<small>` and no "0".
    - `test_the_labels_number_is_the_store_pages_own`: each label's figure is the number in that store page's promotions line.
    - `test_the_chains_headings_stay_for_screen_readers`: each chain a `<div class="chain">` holding its `<h3>`, in `PICK_GROUPS`' order.
    - `test_the_hiring_links_stand_alone`: no " · " between them.
    - `test_a_store_pages_title_puts_its_last_word_on_the_deal_label`: its text read `FRONT_TITLE`.
    - `test_the_headlines_two_numbers_are_bold`: `At Carrefour Market today: <b>14 of 4,196</b> promotions are actually deals.`, the text read `store_lead`'s; no `<b>` in the lines for "None yet", a hole, a promotion hole, or no promotions to check.
    - `test_a_store_row_badge_is_the_verdict_alone`: `<span class="badge deal-1">DEAL · ₪1.90 off</span>`; no "At " in the table; the story's badge still names the store type.
    - `test_the_store_table_keeps_its_roles`: every element of the table carries its role.
    - The tests that pinned the old root (`FRONT_TITLE` over the picker, the old `ROOT_LINE`, the dotted hiring line) and the old row badge, rewritten.
  - `tests/test_shop_build.py`: `test_the_root_counts_each_store_types_promotions`: the build's `index.html` carries each front's number.
  - `tests/test_siteday.py`: `test_every_number_on_the_front_page_is_in_the_site_day_file`: each label's figure is its column's `front.promotions`; no figure where that is null.
  - `tests/test_golden_90.py`: `test_the_golden_root_is_the_picker` with the labels' counts on day 120 (Shufersal Universe's; Shufersal Express, a hole every day, its name alone), and the store pages' assertions with the badge alone and the lead line's `<b>`.
- [ ] **Step 2: Run** those files. Expected: the new tests fail.
- [ ] **Step 3: Implement**, with `pages.py`'s docstring (the root and the store pages) updated. `ROOT_LINE` leaves `pages.py` for `shopper.words`.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the golden's pin.
- [ ] **Step 5: Repin the golden.** Expected moved names: every `day/` line, `site/index.html` and the 9 `site/store/` pages; nothing else. Reason: the front page's headline, line and labels with their counts; the store pages' title label, bold numbers, table roles and badges.
- [ ] **Step 6: Mutations.** `(q36 front)`, target `SHOP_PAGES`: "the headline's DEAL off its label"; "the headline's NO DEAL on the deal's label"; "the old line under the headline"; "the root's tab title the question"; "a count on a store type not read"; "the picker without the chains' headings"; "the hiring links with dots"; "the store title's last word off the label"; "the headline's numbers not bold"; "a row badge naming its store type"; "a table row without its role"; "a cell without its role"; target `SHOP_BUILD`: "the root without the fronts". Re-point the `(q33 front)`, `(q33 picker)` and `(q22 pages)` mutations whose text moved. Run `$PY scripts/mutation_check.py "q36 front" "q33 front" "q33 picker" "q22 pages" "front words"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/pages.py src/shopper/build.py scripts/time_site_run.py tests scripts/mutation_check.py && git commit -m "Site look: the front page asks DEAL OR NO DEAL? with each store's promotions today; store pages put DEAL? on the label, the headline's numbers in bold, the row's badge without the store's name, the table's roles kept for a phone's layout (q36)"`.

### Task 10: The method page's row of links; the docs

Wave 4, after Tasks 4 and 6 to 9. On `q36-site-look` itself.

**Files:**
- Modify: `src/shopper/pages.py` (`ON_THIS_PAGE`; `render_method`'s row), `tests/test_shop_pages.py`, `tests/golden/golden-90.sha256`, `scripts/mutation_check.py` (a block at the end of the dict)
- Modify: `docs/operations.md`, `docs/README.md`, `docs/shopper-site.md`, `docs/store-first.md`, `README.md` (where a line on the pages' look or uploads is now false)

**Interfaces:**
- Produces: `ON_THIS_PAGE = "On this page"`; after the method page's lead, `<nav class="toc" aria-label="On this page"><ol>` with an `<li><a href="#{id}">{heading}</a></li>` for each of the page's own sections, in order (`columns`, `carrefour`, `outside`, `floor`, `rules`, `never`, `measured`, `law`, `reproduce`, `headline-basket`), each link's words the section's `<h2>` as it stands, then `</ol></nav>`.

- [ ] **Step 1: Write the failing test** `test_the_method_page_lists_its_own_sections`: the row comes right after the lead; its `aria-label` is `ON_THIS_PAGE`; its links are the page's top-level section ids in order, each once, each link's text that section's `<h2>` text; every fragment resolves (the site check's rule holds them to an id on the page).
- [ ] **Step 2: Run** it. Expected: fail.
- [ ] **Step 3: Implement**, the module's docstring naming the row.
- [ ] **Step 4: Update the docs,** each sentence checked against the code at the branch's head, never against this plan:
  - `docs/operations.md`: "The shopper site, by hand", step 4 (the site check's rules: the one stylesheet at the page's depth, no inline style, `assets/` holding the stylesheet, the fonts it names and their licences, each named by its hash), step 5 (what to look at, the look's states among them), step 6 (eight uploads, the three of `assets/` by size alone, before the pages, with their content types); "Where things land" (the site bucket's `assets/`, each file put once and never replaced); the site run's upload order where the doc gives it.
  - `docs/README.md`: `site-look-plan.md` among the plans.
  - `docs/shopper-site.md`, its "Every page" line ("the look of the basket page (one style block, system fonts, …)"): the look is site-look.md's, one shared stylesheet and two typefaces served from the site, nothing loaded from elsewhere.
  - `docs/store-first.md`, its "Changed after the build": the chart's drawing and S5's colours are now site-look.md's ("A short history makes a short chart" no longer holds; the shades are three greens; No deal is a yellow label), the rules S0 to S8 unchanged.
  - `README.md`: any line on the pages' look; the counts wait for Task 11.
- [ ] **Step 5: Run** the full test command, then repin the golden. Expected moved names: every `day/` line and `site/method.html`; nothing else. Reason: the method page's row of links to its own sections.
- [ ] **Step 6: Mutations**, `(q36 method)`, target `SHOP_PAGES`: "a section left out of the row"; "the row without its spoken label"; "a link's words not its section's heading". Run `$PY scripts/mutation_check.py "q36 method"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/pages.py tests/test_shop_pages.py tests/golden/golden-90.sha256 scripts/mutation_check.py docs README.md && git commit -m "Site look: the method page's row of links to its sections, named On this page for screen readers; the operations notes and the designs follow the new look (q36)"`.

### Task 11: The full checks, a real day, README's counts

On `q36-site-look`, after Task 10, from a worktree no other run uses.

- [ ] **Step 1:** Run the full test command. Expected: every test passes; coverage at or above 95%; `assets.py`, `bars.py` and `chart.py` at 100%. Write the count, the coverage and the time in "Deviations".
- [ ] **Step 2:** Run `$PY scripts/mutation_check.py "q36"` and every older group a task re-pointed into or whose test file a task rewrote (the tasks' commit messages name them: at least "q33 chart", "q33 product", "q33 words", "q33 front", "q33 picker", "q22 product", "q22 pages", "q22 check", "q22 search", "q22 upload", "q22 site run", "q22 publish", "q22 golden", "q33 golden", "front words"); it edits files in place, so nothing else runs from that worktree until it prints that the files are restored. Then the staleness check. Expected: every one CAUGHT, `none stale`. Write the counts and the time in "Deviations".
- [ ] **Step 3:** `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: clean. `git diff --stat main -- src/shopper/static/search.js site-template.yaml` prints nothing; `LC_ALL=C grep -c '[^ -~	]' src/shopper/static/search.js` prints 0.
- [ ] **Step 4: A real day, built and checked** (the day under "Where the design leaves room"; the latest the controller can sync): Task 8 Step 7's build and check into the worktree's `site/`, `shopper.check` exit 0. Write in "Deviations": the largest product page, its barcode and the median; the stylesheet's and the three fonts' bytes; each page type's bytes beside site-look.md's "Page bytes" table (the front page, a store page, a product page of nine parts, the two largest browse pages, the method, record and basket pages); and the characters of the built pages' text that neither subset draws (each character outside `LATIN` and `HEBREW`; expected: none, or only letters of other scripts in the chains' own names, which fall back to the system's font).
- [ ] **Step 5:** Write the counts Steps 1 and 2 printed (the tests, the coverage, the mutations from the staleness check), with the date, in README.md's "Tests" row and "Tests that are themselves tested". `docs/site-look.md`'s status line says the look is built, on this branch, with "Deviations" here for what changed. Commit `git add README.md docs/site-look.md docs/site-look-plan.md && git commit -m "README: test and mutation counts after the site's look (q36)"`.

### Task 12: The owner's read of the real pages

- [ ] **Step 1:** Keep Task 11's real `site/`; build the golden's final site too (`PYTHONPATH=src:tests $PY tests/shopper_golden.py <scratch folder>`), for the states the real day cannot show yet: a store page with rows, 90-day charts, "Not sold … today", "days with a known price", a weighed product, all three greens.
- [ ] **Step 2:** Serve both folders from the Mac in the background, on the Mac's address on the home network so the owner's phone on the same network reaches them: `$PY -m http.server --bind <the Mac's address> --directory site 8000` and the golden's on 8001 (`--bind 127.0.0.1` when no phone is used). Stop both as soon as the read ends.
- [ ] **Step 3:** Give the owner the two addresses and a reading list; the owner navigates, and this session never drives the browser:
  - the front page: the headline and its line; the nine labels with their counts (a store type not read that day showing its name alone);
  - a store page with no rows (the real day) and with rows (the golden's Shufersal Universe): the title's label, the bold numbers, the filters, the table on a phone as blocks;
  - product pages: a Deal in each shade, a No deal, each no-verdict line the day holds, a weighed product, one sold at all nine store types, the largest page, one not sold at the picked store type, one whose code has no bars; the chart on a short and a 90-day history;
  - the browse, method (its row of links), record and basket pages;
  - each with the script on and blocked; at a phone's width and a desktop's; light and dark.
- [ ] **Step 4:** The looks the design leaves to the builder, by the owner (who has no iPhone; 2026-11-16): Safari and Firefox on the Mac (with Firefox's setting that overrides a page's colours with the reader's own, for forced colours: UNVERIFIED where Firefox keeps that setting), and the owner's own phone's browser; Windows when a device is at hand. Safari on an iPhone is not looked at; "Deviations" says so, with every other device not looked at. What to look at (site-look.md, "Left to the builder"): the lines' SVG stretching, the strokes and dashes not scaling, a barcode shown from a part that is hidden, the Hebrew beside the narrow cut (`size-adjust`), a heading the label repeats hidden (`:has()`), a long verdict's wrap, the variable font's weights. With VoiceOver in Safari on the Mac: a badge of "Elsewhere today" read as the store's name and then its verdict, the chart read as its spoken summary, the barcode's digits read once.
- [ ] **Step 5:** A barcode scan: a product page's label on the Mac's screen, at a phone's width; the owner's phone's barcode-scanning app reads its bars, in the light theme and the dark one. Expected: the digits of the page's barcode line.
- [ ] **Step 6:** One reading this plan made is the owner's to confirm by eye: both of today's labels at the chart's right end are bold, since the appendix's `.chart .now` rule matches the today column itself and not only the lower price's label (one rule, `.chart text.now`, would make it the lower alone, and move the stylesheet's hash). The owner also sees a product with an unread sale price today: the chart ends the day before, with no price at today (ruled 2026-11-16).
- [ ] **Step 7:** The owner's word and look changes are a fix round, test-first: the words pinned, the stylesheet changed only as a logged deviation, the golden repinned with its reason. Log each under "Deviations". Stop the servers. Merging waits for the owner's go.

### Task 13: The whole-branch review

- [ ] **Step 1:** Dispatch a reviewer that has not seen the build, on Fable (`fable`), or on the newest Opus while Fable is at its usage limit, the report naming the swap. Give it `git diff main...q36-site-look`, `docs/site-look.md`, the parts of `docs/store-first.md` and `docs/shopper-site.md` the look keeps, and this plan. Ask for findings by severity against: the grade (WCAG 2.2 AA in both themes; phone and desktop; fast); the design's 18 calls and its "Word changes"; this plan's Review Focus and "Where the design leaves room"; a fact that needs the script; page bytes; nothing loaded from another origin; the upload order, the role and nothing deleting; `search.js` unchanged; each golden repin's reason. The reviewer reads only: no commits, no `gh`, no push, no AWS, no network.
- [ ] **Step 2:** Check each finding against its source before acting on it, since a finding is a claim. Fix what holds, test-first, each fix with its mutation, and re-review the fixes in a scoped review (Opus). Run the full suite and the fixes' mutation groups again. Log every change under "Deviations".

## Deploying this branch (the owner's go; not a task)

After the merge and the push, each on the owner's go:

- **One stack changes, the collector's** (`template.yaml`): `BasketFunction`'s `WriteSite` gains `assets/*`, and the function's code ships in the same deploy, so the code never puts `assets/` without the permission. The site stack (`site-template.yaml`) does not change and is not deployed.
- **When.** After a morning's 12:33 site run has published and before the next morning's 12:03 extractions, at a time when no run of either function is in flight (the timetables in `docs/operations.md`, "What runs when", "Through the day: the update-file polls" and "The shopper site, every morning").
- **The build and the change set.** From a clean, committed tree, `sam build`; then, a read, `ls .aws-sam/build/BasketFunction/shopper/static/ .aws-sam/build/BasketFunction/shopper/static/fonts/`: `look.css` and the five font files are in the function's code. Then `sam deploy` as operations.md's Deploy, step 3, gives it, all nine parameters as they stand (`'ScheduleState=ENABLED'`, `PollScheduleState` and `'BasketScheduleState=ENABLED'` as they are). Read the change set as step 3 says. Expected: `BasketFunction` and `CollectorFunction` modified, not replaced (both zips change); the role SAM builds from `BasketFunction`'s `Policies` modified (`WriteSite`); the DuckDB layer removed and added under a new logical id, as on every build; nothing else, nothing on `ArchiveBucket`, `AlertTopic` or the log groups. Anything else: cancel and find out why. After it, each schedule's state as step 3 reads it.
- **The first morning after** rewrites every page (each loses its style block and links the stylesheet); its site run puts the six assets before any page; the morning after puts none of them. Read, on the first morning: the run's summary (no alert, `pages_uploaded`), its `REPORT` line's duration and `Max Memory Used` against 15 November's step total of 199.6 s and 1,681 MB (operations.md, "Sizing"); the stylesheet and a font fetched from the site with `curl -sI`, each answering 200 with its content type (`text/css; charset=utf-8`, `font/woff2`). On the second morning, a read of the bucket's versions under `assets/` (`aws s3api list-object-versions --bucket <the site bucket> --prefix assets/ --profile flights-sam --region il-central-1`, after the identity check): one version of each file. Write the figures in operations.md's "Sizing" (a doc commit, pushed on the owner's go).
- **Page size later.** The real day's history is about two weeks of records; charts grow with sale runs and price changes over the 90 days. Re-measure the largest product page against 45,000 bytes as the history fills (late January). The site check refuses a page over 60,000 bytes, and the site run then uploads nothing (`SiteCheckFailed`).
- **Cost:** about $0.04 a month more (site-look.md, "Cost", whose rates are marked UNVERIFIED there): about 2 KB more on each product page kept for 30 days of old versions, and 73 KB of assets once. No new schedule, alarm or dependency. The site stays `noindex`.

## Deviations

(Append here when reality forces a change from this plan: what changed, why, and when.)

- **Baseline** (2026-11-16, on `q36-site-look` at 09e5cdd): 2,649 tests passed, coverage 99.86%, 1,064 s.
- **Branched from 09e5cdd, not 16fb85b** (Global Constraints): the commits between are this plan and its rulings, docs only.
- **The owner's ruling of 2026-11-16 reaches `unread_today` too** (before Task 1): the design's state table gives "On sale, price not read today" and "sale prices not read today" one row, "no price; … the chart still shows the days before", so on both calls today's shelf price is not drawn and the shelf line ends the day before. site-look.md's chart section says so now; "The chart, call by call" and Task 8 follow.
- **Wave 1** (Tasks 1 to 4, built side by side 2026-11-16, merged in task order; full suites took about an hour each with four running at once on the Mac, which swapped 17.6 of 18.4 GB, so later waves run at most two full suites at once):
  - Task 1: the published stylesheet `assets/look.dc1312dbfc.css` measures 20,928 bytes (line 22,000) and the three fonts 43,152 bytes together (line 45,000), the design's figures; the fonts rebuilt from the pinned sources match the designer's byte for byte. `tests/test_look.py` names the three fonts itself, since Step 4 runs before `shopper.assets` exists, and imports `FRONT_HEADS` inside its one test, so a later stylesheet mutation never fails at collection. Four rules the Step 12 list missed got their mutations in the review's fix round (print hiding the controls, no `@import`, the pinned sources, a font left out of the stylesheet), by the project's rule of a mutation for every rule.
  - Task 2: the review asked for a second statement of every EAN-13 parity row: each of rows 1, 3, 5, 6, 7, 8 and 9 is pinned by a code whose pattern is assembled from its parity typed literally (7290000144474 for row 7, the Israeli prefix's); `isascii()` left the guard, unreachable once `isdigit()` and `is_gs1`'s ASCII-only match both hold. Two more mutations than listed: a padded code drawn, EAN-8's right half in L codes.
  - Task 3: two tests outside its files quoted a reason whose counts differ and took the new words (`tests/test_siteday.py`, `tests/test_product.py`); `tests/test_chart.py` took transitional edits for the summary's new lowest and highest. The golden moved 7 `day/` lines and 4 `site/p/` pages, the chart's spoken summary alone; no store page, since no golden verdict with a reason has differing counts. The target `WORDS_FOR_SHOP_CHART` is gone, its four mutations moved to `SHOP_WORDS`, whose test pins the whole sentence; the `TIME_LIMIT` comment's count of target sets is left for Task 10. No mutation retired.
  - Task 4: `test_publish_sh_runs_the_check_and_the_guard_before_any_upload` counts 9 uploads, not 6; `test_upload_takes_the_page_folders_whole` uses `.md` for its file of no known type. Two mutations beyond the list (an asset of no known type found after the records went up; a failed asset put letting the upload go on). Re-pointed: `_PUBLISH_ORDER`, `_PUBLISH_UPLOAD`, "site puts before every file is found". None retired.
  - Merged: 2,514 mutations, none stale.

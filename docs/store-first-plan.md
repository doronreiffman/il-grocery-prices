# Store first: the verdict, the price chart and the store picker (implementation plan)

Grade, quoted from the approved design (`docs/store-first.md`, "Grade"): "the public site's production grade, as for the shopper site: test-first, a mutation for every rule, a fresh review before merge, and the owner's read of the built pages before merge."

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the shopper picks a store type once; every product page then answers for that store type with "Deal" or "No deal" against what the product usually costs, sales included, with the shekel saving, one measured reason, a price chart, "Last this low" and "How often on sale"; each store type gets its own front page of deals, biggest saving first.

**Architecture:** two new modules beside the existing ones. `shopper.verdict` holds rules S0 to S8 and the front list, pure functions over the history `shopper.history.load` already reads (no new table, no change to collecting or extracting). `shopper.chart` draws one SVG per store type from a verdict. `shopper.product` renders the verdict, chart and fold-out in place of P7, P8, the price-change text and P9. `shopper.pages` renders the root page as the picker and one front page per store type under `store/`. The one script, `static/search.js`, keeps its name and gains the picker: it is loaded on every page, remembers the pick under one localStorage key, and rearranges a product page for the pick. Every fact stays in the HTML. The build computes each pair's verdict once, in its existing single pass, and the site-day file gains a front block per store type.

**Tech Stack:** Python 3.13 standard library, `duckdb==1.5.6` (already pinned), pytest and pytest-cov, `scripts/mutation_check.py`; Node 22.11.0 (already in CI, `.github/workflows/ci.yml`) for the script's tests through `tests/search_harness.js`. No new dependency.

**Spec:** `docs/store-first.md` (approved by the owner 2026-11-11). Read it in full first. Then read the parts of `docs/shopper-site.md` it changes: "What a visitor sees", P6 to P10, Q2 to Q4, "Words", "Build and hosting" ("Checks before upload"), and "Changed after the survey" ("The column"). The code this builds on: `src/shopper/` (`history.py`, `items.py`, `deals.py`, `measures.py`, `product.py`, `pages.py`, `words.py`, `shell.py`, `build.py`, `siteday.py`, `check.py`, `static/search.js`), `src/basket/site.py`, `src/basket/page.py` (`BASE_STYLE`, `Frame`), `template.yaml` (`WriteSite`), `site-template.yaml` (the lifecycle rules), `tests/shopper_golden.py`, `tests/test_golden_90.py`, `tests/search_harness.js`.

## Global Constraints

- The grade above binds every task: test-first, a mutation for every rule, a fresh review per task and of the whole branch, and the owner's read of a real day's built pages before merge.
- Branch `q33-store-first`, worktree `/Users/doronreiffman/Projects/il-grocery-prices-q33-store-first`. One commit per task, each message naming q33. Never push; no `gh`; no AWS write, deploy or upload (each is the owner's go, outside this plan). Before each commit, run `git status` and stage only the task's files.
- `PY` is `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/python`. The worktree has no venv; pytest's `pythonpath` (`src`, `tests`) makes it test the worktree's code. Commands run from the worktree root.
- The full test command: `$PY -m pytest -o addopts="" --cov=collector --cov=src/basket --cov=src/shopper --cov-fail-under=95 -q`. Baseline on main at fd2d30d: 2,514 tests, 99.86%. Measure it once on the new branch before Task 1 and write it in "Deviations". The floor is 95%. The new modules `verdict.py` and `chart.py` reach 100%.
- Test-first: a failing test before the code, for every rule.
- A named mutation in `scripts/mutation_check.py` for every rule, added in the task that adds the rule. The name says what the break does, then the group in brackets: `(q33 verdict)`, `(q33 golden)`, `(q33 chart)`, `(q33 product)`, `(q33 words)`, `(q33 script)`, `(q33 picker)`, `(q33 front)`, `(q33 siteday)`, `(q33 method)`. New targets: `SHOP_VERDICT = ("src/shopper/verdict.py", ["tests/test_verdict.py"])`, `SHOP_CHART = ("src/shopper/chart.py", ["tests/test_chart.py"])`, `VERDICT_FOR_SHOP_GOLDEN = ("src/shopper/verdict.py", ["tests/test_golden_90.py"])`. Only pytest exit 1 counts as caught. `tests/test_mutation_targets.py` runs with the suite and refuses a target whose text or test is gone.
- Each task's mutation step runs `$PY scripts/mutation_check.py "q33 <group>" ...` over its groups and every name it re-pointed, then the staleness check. Expected: every one CAUGHT, then `none stale`. The mutation check edits files in place, so nothing else runs from the worktree while it runs. The full check runs weekly in CI.
- **The staleness check** reads and edits nothing, so it is safe at any time: `$PY -I -c "import importlib.util as u; s = u.spec_from_file_location('m', 'scripts/mutation_check.py'); m = u.module_from_spec(s); s.loader.exec_module(m); bad = [n for n, ((f, _), old, _) in m.MUTATIONS.items() if (m.ROOT / f).read_text().count(old) != 1]; print(len(m.MUTATIONS), bad or 'none stale')"`.
- **Re-point or retire.** A mutation whose code stays but whose text moved is re-pointed at the new text, with the same break. A mutation of a rule the design removes (P7's sentences, P8's sentences, the price-change text, P9's row, the old front test, the old chart) is retired with its code, because the rule it guarded no longer exists. Each retired mutation is named in its task's commit message and in "Deviations", with the rule it guarded.
- **Golden repins.** Run `GOLDEN_90_REPIN=1 $PY -m pytest tests/test_golden_90.py -k pinned` only after every other golden test passes. Then list the moved names with `git diff -U0 tests/golden/golden-90.sha256 | grep '^[-+][0-9a-f]' | awk '{print $2}' | sort -u`. Compare that list with the task's expected list, and name the reason and the kinds of lines that moved in the commit message.
- Test data never reads the clock: fixed days and times, `gzip.compress(..., mtime=0)`. Every datetime is time-zone aware; never a naive `astimezone()` (the Mac runs Asia/Jerusalem, CI runs UTC). The rules here work on dates only.
- **Figures as shown** (design, call 13). Every comparison and threshold works on two-place figures, half up: a listed price by `basket.record.money`, a deal price by `shopper.deals.to_agora`. A day price, the usual price, today's price and the saving are `Decimal`s with two places.
- **The design's values, copied, never re-derived:** ₪1.00 for a deal (≥); shades ₪1.00 to ₪2.99, ₪3.00 to ₪4.99, ₪5.00 or more; the window is `READ_DAYS` (90), today excluded; the higher middle value for an even count; `MIN_FRONT_DAYS` (20) of `RECENT_DAYS` (30) for the front bar; the top 100 per store type; the nine store types of `shopper.columns.COLUMNS`; the page-size shrink line of 45,000 bytes, with the check's `MAX_PAGE` of 60,000 kept; one script file; one localStorage key.
- **Public page words.** Every headline and label is what a shopper would say out loud. Shopper text says "shelf price"; fold-outs and the method page say "listed price" with its definition. Never "we", "our" or "us" (`shopper.check` refuses them), never a NEVER phrase, never a word that says a chain did wrong ("No deal" is neutral grey, never red). The design's Words table is copied verbatim. The words this plan adds are listed under "Words this plan adds"; they are provisional until the owner's read (Task 9).
- No new dependency. Nothing in the code deletes: no `delete_object`, no `s3:Delete*` in the role, no `--delete` in the scripts.
- Every page is a pure function of its inputs: the same bytes whatever order the rows or mappings come in.
- Docs, this plan included, are in plain words with no "we". This plan and every doc are public: no pointer to the owner's private notes, no email address, no claude.ai link, no health-check URL.
- Models (the owner's rule): implementers and task reviews on the newest Opus (`opus`). The whole-branch review runs on Fable (`fable`), or on the newest Opus while Fable is at its usage limit, with the report naming the swap. A task still open after fix round 3 escalates to Fable. Subagents never run `gh` or push.

## Review Focus

1. **A pick that no longer fits.** Storage may hold a key that is not one of the nine (an old value, garbage), or reading storage may throw (private browsing). Either way the page behaves as with no pick: every part listed, search working, no error stops the script. Tests in Task 4: `test_read_pick` (the unknown-key and throwing-storage cases) and `test_blocked_storage_leaves_search_working`.
2. **The picked store type's day is not readable.** Its promotions were not read today (a promotion hole, as at Shufersal Deal on 2026-11-08), or its prices came from too few files (a hole). The product page gives no verdict and never says "No sale today" or "No deal". That store type's front page lists no deal and says why. Tests in Task 1 (`test_each_no_verdict_call`, the `too_few` and `unread_today` cases) and Task 6 (`test_a_store_type_not_read_today_says_so_and_lists_none`).
3. **The ₪1.00 line on figures as shown.** "3 for ₪10.00" shows ₪3.33; against a usual ₪4.33 that is ₪1.00 off, a Deal, although the exact saving is ₪0.9966. Every shade band edge works the same way (₪2.99 and ₪3.00, ₪4.99 and ₪5.00). Test in Task 1: `test_deal_from_one_shekel_on_figures_as_shown`.
4. **A product the picked store type does not sell.** If the store type never sold it, the page has no part for it; if the product is sold nowhere today, no store type does. The page says "Not sold at … today" and shows the badge row, which may be empty, with no script error and with every fact in the HTML. Tests in Task 3 (`test_a_product_sold_nowhere_today_has_no_badges_and_every_part`) and Task 4 (`test_arrange`, the cases with the pick absent from the parts and with no badges).
5. **"change" from a store page.** The root shows the picker instead of sending the visitor straight back to the remembered store; picking another store type replaces the pick. Test in Task 4: `test_the_root_sends_a_remembered_pick_to_its_store_page_and_change_does_not`.

---

## Questions for the owner

Answered by the owner 2026-11-11: question 1, the recommendation (tapping a badge with no pick yet sets the pick). Nothing in this plan waits on the owner now.

1. **Tapping a badge on a product page with no pick yet** (design, "What a visitor sees" 6: the badge row is shown "as the picker"; call 6 covers taps once a pick exists). **Recommended:** with no pick, tapping a badge both shows that part and sets the pick, because the row is the picker on that page. With a pick, tapping only shows that part (call 6). Why: a shopper who arrives from a shared link or from search and taps their store expects the next product page to remember it. **The alternative:** a pick is set only by opening a store type's front page. Task 4 is built on the recommendation. The other answer changes one function (`onBadge`), one test and one mutation. This blocks Task 4 only.

## Where the design leaves room, this plan decides

From "Left to the builder", and from places where the rules are silent. The owner can overturn any of these.

- **Modules.** The rules go in `shopper.verdict` and the drawing in `shopper.chart`. The words go in `shopper.words`, as every page word already does.
- **The store-type front pages' file names:** `store/<column key>.html` (`store/carrefour-market.html`). A folder of their own means one more line in `BasketFunction`'s role (`WriteSite`: `store/*`) and one more lifecycle rule in the site stack (`old-store-pages`, prefix `store/`), each pinned by the existing template tests. Both are part of the deploy ("Deploying this branch", below).
- **The script's structure.** The file keeps its name, `search.js`, because the role, the lifecycle rule, `basket.site.FIXED_PAGES` and `scripts/publish.sh` already name it. The picker is pure functions exported for the Node harness, beside a thin DOM wiring. The script finds the site's root from the header's pick link (`#pick-link`, whose `href` is `<up>index.html#pick`). Search builds its requests from that root, so it works from `store/` pages.
- **The pick.** It is kept under the localStorage key `store` and holds a column key; any other value counts as no pick. It is set when a store type's front page opens, and on a badge tap when there is no pick yet (Question 1). Every storage read and write is inside try/catch.
- **Ties in the front list:** the saving as shown, largest first, then the barcode as a number (`shopper.items.by_number`).
- **The colours.** The tokens live in `shopper.product.BADGE_STYLE`, light and dark, shared by product and store pages: a light, a middle and a deep green for the three deal bands, and a neutral grey for No deal. Each badge's text must contrast at least 4.5:1 with its background in both themes (WCAG AA for normal text), and a test checks it.
- **The chart.** Each calendar day from the first tracked day to today is `DAY_WIDTH` (4) units, so the viewBox width follows the span and a short history draws a short chart. Heights run between the lowest and highest of the shown listed prices, day prices and today's price. A run of one price is one segment from the start (the design's first simplification is built in). The labels sit at the right, and a `<title>` holds a text alternative. Untracked days are gaps; a sale day of unknown price gets a mark at the foot and no price.
- **The order of the calls** (S4, where several no-verdict lines could apply). The first that applies wins:
  1. `too_few`: today is a hole for the store type (prices from too few files). The section shows `basket.words.too_few`, as today.
  2. `not_sold`: no point today, or no listed price.
  3. `unread_today`: today is a promotion hole.
  4. `no_sale`, `some_stores` or `price_unread`, by today's promotions.
  5. `new`: the pair has no point on any day before today.
  6. `mostly_unknown`: sale days of unknown price are more than half the tracked days.
  7. `no_history`: no tracked day has a day price.
  8. `deal` or `no_deal`.
- **A `RewardType` 0 promotion is not a sale.** A struct with no `kind` never counts for S1, S3 or S7, as the approved amendment's S2 reads it (an item named only by 0 links is not on promotion). S7's "on sale" is the items table's `Point.on_promotion`: a wide link with a kind, running that day. "Some stores only" is a running struct with a kind on a day that is not `on_promotion`.
- **Which No-deal reason is used.** When today's price is at or above the usual price (saving ≤ ₪0.00), the reason is the "always on" form, "It's been ₪X or less on K of the N days tracked.". With the higher middle value, K is then more than half of N. When 0 < saving < ₪1.00, the reason is the "small" form.
- **What the counts count.** The reason line and S6 count the days that have a day price (S8: "the number of days it rests on"). S7 counts every tracked day, unknown-price sale days included.
- **S6's today.** S6 uses S3's price when a promotion counts, else the listed price. It shows only when today's price is known: not on `too_few`, `not_sold`, `unread_today` or `price_unread` (the owner, 2026-11-11: a sale whose price could not be read gives no price today, never the listed price). On those days the chart draws no today mark.
- **S7's last sale.** Runs are made over the tracked days by `on_sale`; an untracked day neither breaks nor extends a run. A run that reaches the last tracked day while today is on sale is "this one". The last sale before it is the latest earlier run. Its price is the day price on its last day, left out when that price is unknown.
- **The fold-out "How this is worked out"** holds, in this order:
  - today's listed price with its range and store count (today's `_today`, moved);
  - "last seen listed across …" when the product is listed today but not wide;
  - every promotion running today, in today's words;
  - F10's sentence (`no_odds_yet`).
  P10's sentence stays at the top of the section. `ALWAYS_SENTENCE` moves to one note after the sections.
- **The badge row.** There is one badge per store type with a point today, sorted by saving as shown (largest first; deals, then No deals). The rest follow in `COLUMNS` order. Each badge links to its section (`#c-<key>`). The row sits after the name block. Its heading, "Elsewhere today", is `hidden` until the script finds a pick.
- **Nothing is hidden without the script.** The script adds the class `js` to `<html>`, and only `.js` rules hide parts.
- **The ALWAYS check moves.** `shopper.check` holds every `store/*.html` and every `p/*.html` to the four ALWAYS phrases. `index.html`, now the picker, shows no price and is not held to them. Each store page carries the phrases in its fold-out.
- **The site-day file.** Each column's block gains `front`: `ready`, `deals` (N), `checked` (M), `promotions`, `products`, and the shown rows' numbers. The top-level `counts` and `front_rows` go. B12's revision keeps each column's `deals` and `checked`.
- **Code that only the removed rules used is removed** (Task 6), with its tests and mutations: in `measures`, `gap`, `Gap`, `depth`, `on_front`, `changes`, `Change`, `gaps` and `promoted_today`; in `words`, `gap_sentences`, `history_sentences`, `price_history` and their helpers; in `pages`, `FrontRow`, `front_rows_of` and `ordered`; in `product`, `_across`, `_cell` and the old `_chart`. `runs`, `days_since`, `promotion_points` and `whole` stay, because the forecast and the record use them.
- **The real day for measuring and for the owner's read.** Use the latest day for which all five chains' items tables are in the main checkout's `data/tables/items/` (2026-11-10 when this plan was written). A read-only `sh scripts/sync.sh` may bring a later one, after the identity check.

## Words this plan adds (provisional until the owner's read, Task 9)

The design's Words table is used verbatim. The design's words do not cover the cases below, so these are proposed and pinned in tests, and changed on the owner's word.

- A product seen before whose tracked days have no day price: "No price history yet."
- S7 with no sale today: "The last sale ended 12 October, at ₪9.90."; with no readable price: "The last sale before this one ended 12 October." (or "The last sale ended 12 October.").
- One day: "(1 day tracked)", "Lowest in the 1 day tracked.", "On sale on 1 of the 1 day tracked.".
- Weighed products: "DEAL · ₪19.90 off a kilogram", "Usually ₪69.90 a kilogram, sales included (82 days tracked).", "When you buy 1.5 kilograms".
- Conditions beyond the design's two, from question K's phrases with a capital letter: "The chain's card holders only", "Some customers only", "Minimum spend ₪150.00", joined by "; ". A programme's name goes in the chain's span, in the fold-out only.
- Badges under "Elsewhere today": "Rami Levy · DEAL · ₪1.90 off", "Rami Levy · NO DEAL", "Rami Levy · no sale today" (each no-verdict line in lower case, without its full stop).
- The chart: the labels "usually ₪8.90", "lowest ₪6.90", "highest ₪8.90", "today ₪6.90"; the key "shelf price", "on sale", "on sale, price not read"; the text alternative "Price chart: usually ₪8.90, lowest ₪6.90, highest ₪8.90, today ₪6.90.".
- The root page's line on what the site does: "Pick the store you're in, then look up a product: each sale is checked against what it usually costs there."
- The header: "Pick your store"; "Carrefour Market · change" (the design's).
- A store type's front page:
  - the list's heads: "Product", "Deal", "Price today", "Usually";
  - the headline, with the noun always plural and the verb by N: "At Shufersal Sheli today: 1 of 3 promotions is actually a deal.";
  - with M = 0: "At Shufersal Sheli today: no promotions to check.";
  - on a promotion hole: "Sale prices could not be read today.";
  - on a hole: `basket.words.too_few`;
  - the fold-out's count line: "Today Shufersal Sheli lists 1,840 promotions carried by at least half its stores, on 6,210 products.";
  - the story's heading: "One of today's deals";
  - the fold-out's rules in shopper words (Task 6).

---

### Task 1: The rules: tracked days, the usual price, the verdict, last this low, how often, the front list (S0 to S8)

**Files:**
- Create: `src/shopper/verdict.py`, `tests/test_verdict.py`
- Modify: `tests/shopper_golden.py` (Shufersal Universe's three stores from day 92; products U1 to U10; the docstring's worked values), `tests/test_golden_90.py` (`test_the_golden_verdicts`), `tests/golden/golden-90.sha256` (repinned)
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `shopper.history` (`Pair`, `Point`, `ColumnDay`, `window`, `READ_DAYS`), `shopper.measures` (`promotion_points`, `MIN_FRONT_DAYS`, `RECENT_DAYS`), `shopper.deals` (`deal_from_row`, `to_agora`), `basket.record.money`, `shopper.items.by_number`. `shopper.verdict` imports nothing from `words`, `product`, `pages` or `chart`, which all import it. That keeps the imports from going round in a circle, so `counts_today` checks start ≤ day ≤ end itself, without `product.running_today`.
- Produces (in `shopper.verdict`):

```python
DEAL_MIN = Decimal("1.00")                                                       # S4
SHADES = ((Decimal("5.00"), "deal-3"), (Decimal("3.00"), "deal-2"), (Decimal("1.00"), "deal-1"))   # S5, deepest first
FRONT_LIMIT = 100
CALLS = ("deal", "no_deal", "too_few", "not_sold", "unread_today", "no_sale", "some_stores", "price_unread",
         "new", "mostly_unknown", "no_history")

@dataclass(frozen=True)
class Day:                       # one tracked day (S0) of the window
    day: date
    listed: Decimal              # as shown
    price: Decimal | None        # S1, as shown; None on a sale day of unknown price
    on_sale: bool                # S7: Point.on_promotion

@dataclass(frozen=True)
class Verdict:
    column: str
    call: str                    # one of CALLS (the order under "Where the design leaves room")
    days: tuple[Day, ...]        # the tracked days of the READ_DAYS before the day, in day order
    today_price: Decimal | None  # S6's today: S3's price when a promotion counts, else the listed price; None when unknown
    struct: Mapping | None       # S3: the counting promotion with the lowest exact price (its conditions); a tie to the first
    usual: Decimal | None        # S2, with call deal or no_deal
    saving: Decimal | None       # usual - today_price, with call deal or no_deal
    last_low: Day | None         # S6
    last_sale: Day | None        # S7: the last day of the last sale before this one
    on_sale_today: bool

    @property
    def priced(self) -> tuple[Day, ...]: ...     # the days with a day price
    @property
    def shade(self) -> str | None: ...           # S5, a deal's only
    @property
    def counting(self) -> bool: ...              # a promotion counts today (struct is not None)

def counts_today(struct: Mapping, day: date) -> bool       # S3's filter: wide, valid, start <= day <= end
def day_price(point: Point, day: date) -> Decimal | None   # S1
def tracked(pair: Pair, column_days, day: date) -> tuple[Day, ...]           # S0 and S1, over promotion_points
def usual_price(prices: Sequence[Decimal]) -> Decimal                         # S2: sorted, element len // 2
def verdict(pair: Pair | None, column: str, column_days, day: date) -> Verdict
def passes_bar(pair: Pair, column_days, day: date) -> bool   # window(..., RECENT_DAYS).days >= MIN_FRONT_DAYS
def on_list(found: Verdict, pair: Pair, column_days, day: date) -> bool       # call "deal" and passes_bar
def checked(found: Verdict, pair: Pair, column_days, day: date) -> bool       # found.counting and passes_bar (M)

@dataclass(frozen=True)
class DealRow:
    column: str
    code: str
    title: str
    verdict: Verdict

def front_list(rows: Iterable[DealRow]) -> list[DealRow]   # saving desc, then barcode as a number; all N of them
```

- [ ] **Step 1: Write the failing tests** in `tests/test_verdict.py`. Build the pairs in the style of `tests/test_measures.py`'s `_pair` and `_days` (day `DAY = date(2026, 11, 20)`, synthetic code `2000000000046`), extended with promotion structs as `shopper.items` writes them (`wide`, `valid`, `kind`, `start`, `end`, `price_exact`, `per`, `buy`, `restrictions`, `programmes`, `min_spend`).
  - `test_a_tracked_day_has_prices_and_promotions_read` (S0): a price hole, a promotion hole, a missing table and a day not listed are each absent from `[d.day for d in tracked(...)]`; every other day of the 90 is present.
  - `test_the_day_price_is_the_lower_of_listed_and_the_lowest_counting_deal` (S1): with listed 5.00, counting deals 4.20 and 4.50, a not-wide 3.00 and an invalid 2.00, the day price is `Decimal("4.20")`. A valid deal of 5.50 gives 5.00.
  - `test_a_sale_day_of_unknown_price_has_no_day_price_and_is_on_sale` (S1, S7): `on_promotion` True and only invalid structs give `Day(price=None, on_sale=True)`.
  - `test_the_usual_price_is_the_higher_middle` (S2): `usual_price([D("3"), D("1"), D("2")]) == D("2")`; `usual_price([D("1"), D("2"), D("3"), D("4")]) == D("3")`; thirteen 7.90 and thirteen 9.90 give `D("9.90")`.
  - `test_unknown_price_days_never_push_the_usual_price_up` (call 9): ten 4.00 sale days, eight unknown-price sale days and nine 6.00 days give usual 4.00 over the 19 priced days.
  - `test_todays_price_is_the_lowest_counting_deal_club_only_included` (S3): a club-only struct at 3.90 and a plain one at 4.20 give `today_price == D("3.90")`, and `struct["restrictions"] == ["club"]`.
  - `test_deal_from_one_shekel_on_figures_as_shown` (S4, call 13; Review Focus 3): usual 5.00 against today 4.00 is a `deal` (saving 1.00); 4.01 is a `no_deal` (0.99). "3 for ₪10.00" (`price_exact` "10/3", shown 3.33) against a usual 4.33 is a `deal` with `saving == D("1.00")`.
  - `test_the_shades` (S5): savings 1.00 and 2.99 give `deal-1`, 3.00 and 4.99 give `deal-2`, 5.00 and 19.90 give `deal-3`. A `no_deal` has `shade is None`.
  - `test_each_no_verdict_call`, parametrized (Review Focus 2), the call expected each time:
    - `too_few`: a hole today, with a point and a wide valid struct;
    - `not_sold`: no point today;
    - `unread_today`: a promotion hole today, with a wide valid struct;
    - `no_sale`: no running struct;
    - `some_stores`: a running struct with a kind, not wide;
    - `price_unread`: `on_promotion` True, wide, not valid;
    - `new`: a counting struct and no point before today;
    - `no_history`: points before today, none tracked;
    - `mostly_unknown`: 14 unknown-price sale days of 27 tracked;
    - with 13 of 27, a verdict (`deal` or `no_deal`, by its prices), judged on the 14 priced days.
  - `test_a_zero_link_promotion_is_not_a_sale`: a running wide struct with `kind` None and `on_promotion` False gives `no_sale`.
  - `test_last_this_low` (S6): the latest priced day at or below today's price, an equal price included. With none at or below, `last_low is None`. On a `no_sale`, today's price is the listed price. On `unread_today`, `today_price is None` and `last_low is None`.
  - `test_how_often_and_the_last_sale_before_this_one` (S7):
    - a run across an untracked day is one run;
    - a sale running into today makes the run before it the last sale;
    - with no sale today, the latest run is the last sale;
    - a last day of unknown price gives `last_sale.price is None`;
    - the on-sale count is `sum(d.on_sale for d in days)`.
  - `test_the_bar_is_twenty_days_with_records_in_the_thirty`: 19 days fail and 20 pass; a promotion-hole day counts (it is a record).
  - `test_the_front_list`: `front_list` sorts by saving (largest first), then by barcode as a number (`"9"` before `"10"`). `on_list` is false for a `no_deal`, and false for a deal failing the bar. `checked` is true for a `no_deal` with a counting promotion that passes the bar.
  - `test_random_histories_keep_the_rules`: over the histories of `tests/shopper_random.py`, check:
    - `usual` is one of the priced prices;
    - `saving == usual - today_price`;
    - every `Day` is a day `promotion_points` reads;
    - the call is `deal` exactly when `saving >= DEAL_MIN`.
- [ ] **Step 2: Extend the golden history** in `tests/shopper_golden.py`.
  - `store_list` takes the day. From day 92 (2 April), Shufersal's list holds stores 81, 82 and 83 in sub-chain 8 (Shufersal Universe); before day 92 the list is unchanged.
  - Those three stores publish price files and promotion files every day from 92 to 120, except day 110 (20 April), when they publish price files only. Day 110 is Universe's promotion hole, the design's "a hole".
  - They list only the new products, U1 to U10. These are ten synthetic GS1 barcodes in ascending numeric order (so ties sort as listed here), with synthetic Hebrew names, at the same price in each of the three stores unless said:

  | Product | Case | Listed | Promotion |
  |---|---|---|---|
  | U1 | always on | 12.90, days 92 to 120 | fixed 9.90, days 92 to 125 |
  | U2 | a monthly sale | 8.90, days 92 to 120 | fixed 6.90, days 95 to 101 and days 117 to 123 (two ids) |
  | U3 | exactly half | 9.90, days 93 to 120 | fixed 7.90, days 106 to 125 |
  | U4 | a short history | 4.50, days 115 to 120 | fixed 3.20, days 120 to 126 |
  | U5 | new today | 6.00, day 120 | fixed 5.00, days 120 to 126 |
  | U6 | saves ₪0.99 | 5.00, days 92 to 120 | fixed 4.01, days 120 to 126 |
  | U7 | saves ₪1.00 | 5.00, days 92 to 120 | fixed 4.00, days 120 to 126 |
  | U8 | buy 2 | 6.00, days 92 to 120 | `RewardType` 1, `MinQty` 2, `DiscountedPrice` 9.00, days 120 to 126 |
  | U9 | some stores only | 7.00, days 92 to 120 | fixed 5.00 at store 81 alone, days 120 to 126 |
  | U10 | an unreadable price | 3.00, days 92 to 120 | fixed 6.50 (twice the listed price or more: not valid), days 120 to 126 |

  Universe's 29 days of records (92 to 120) stay under the forecasts' 30th day (`FIRST_RECORD_DAY`), so the golden gains no forecast or score. Rewrite the docstring's paragraph on the stores, add the products, and work the values below by hand in the docstring.
- [ ] **Step 3: Write the golden's failing test** in `tests/test_golden_90.py`. `test_the_golden_verdicts` loads the day's history (`load(golden.data / "tables", day_of(n), SLUGS)`), finds each pair, and asserts `verdict(...)`'s `call`, `usual`, `saving`, `shade`, `len(priced)`, `len(days)`, `last_low`, `sum(on_sale)` and `last_sale`. These values were worked by hand for this plan. The implementer works each one again in the golden's docstring; a disagreement is reported as a finding, never fixed quietly.
  - G3 at Shufersal Sheli:
    - day 75 (16 March): `deal`, usual 10.90 over 74 days, saving 3.00, `deal-2`, `last_low` None, 0 on sale;
    - day 120 (30 April): `deal`, usual 10.90 over 90 days, 45 of them on sale. This is exactly half the days: the higher middle value holds the shelf price.
  - G4 at Rami Levy, day 85: `deal`, usual 69.90 over 82 days (holes 40 and 41 skipped), saving 19.90, `deal-3`.
  - G5 at Shufersal Deal, day 99: `deal`, usual 6.00 over 88 days, saving 1.50, `deal-1`, `last_low` day 44 (13 February) at 4.50. G5 at Shufersal Sheli, day 99: `no_sale`.
  - G1:
    - at Osher Ad, day 120: `no_sale`, today's price 5.00, `last_low` day 119 at 5.00, 31 of 90 on sale, `last_sale` day 116 (26 April) at 3.90;
    - at Osher Ad, day 50: `deal`, usual 5.00 over 49 days, saving 1.10, 17 on sale, `last_sale` day 32 (1 February) at 3.90;
    - at Shufersal Deal, day 50: `too_few`.
  - Universe, day 120 (27 tracked days, day 110 left out):

    | Product | Call | Values |
    |---|---|---|
    | U1 | `no_deal` | usual 9.90, saving 0.00, 27 of 27 on sale, `last_low` day 119 at 9.90, `last_sale` None |
    | U2 | `deal` | usual 8.90, saving 2.00, `deal-1`, 10 of 27 on sale, `last_sale` day 101 (11 April) at 6.90 |
    | U3 | `deal` | usual 9.90 over 26 days, saving 2.00, 13 of 26 on sale |
    | U4 | `deal` | usual 4.50 over 5 days, saving 1.30, fails the bar |
    | U5 | `new` | |
    | U6 | `no_deal` | saving 0.99 |
    | U7 | `deal` | saving 1.00, `deal-1` |
    | U8 | `deal` | saving 1.50, `struct["buy"] == Decimal("2")` |
    | U9 | `some_stores` | |
    | U10 | `price_unread` | |

  - The front list at Universe, day 120: `[row.code for row in front_list(...)]` is U2, U3, U8, U7. `checked` holds for U1, U2, U3, U6, U7 and U8: N = 4 and M = 6.
- [ ] **Step 4: Run** `$PY -m pytest tests/test_verdict.py tests/test_golden_90.py -q`. Expected: the new tests fail, because `shopper.verdict` does not exist. Of the existing golden tests, only `test_the_golden_bytes_are_pinned` fails. Any other failure is a finding (the extension disturbed a worked value): report it before going on.
- [ ] **Step 5: Implement** `src/shopper/verdict.py` to the interfaces and the order under "Where the design leaves room". Its module docstring states S0 to S8 and the front list in plain words, with the readings this plan takes.
- [ ] **Step 6: Run** the full test command. Expected: everything passes except `test_the_golden_bytes_are_pinned`.
- [ ] **Step 7: Repin the golden.** The moved names must all be among these:
  - `day/2026-04-02` to `day/2026-04-30`;
  - the final site's product pages, search pieces, browse pages, `index.html`, `method.html` and `record.html`;
  - `site-days/` and `days/` files from 2026-04-02 (Shufersal's included stores).

  None may be a `day/` line before 2026-04-02, nor a `forecasts/`, `scores/`, `ledger` or `tables/scored/` line. A name outside the list is a finding: stop and report it.
- [ ] **Step 8: Mutations.** Group `(q33 verdict)`, target `SHOP_VERDICT`:
  - "a promotion hole counted as tracked"
  - "a price hole counted as tracked"
  - "the day price the listed price alone"
  - "a not-wide deal in the day price"
  - "an invalid deal in the day price"
  - "a sale day of unknown price given the listed price"
  - "the usual price the lower middle"
  - "the usual price the mean of the middle two"
  - "₪1.00 not a deal"
  - "the minimum compared on exact prices"
  - "the shade bands an agora off"
  - "a hole today judged"
  - "a promotion hole today judged"
  - "a not-wide promotion judged"
  - "an unreadable price judged"
  - "unknown days at exactly half called most days"
  - "a zero link counted as a sale"
  - "last this low strictly below"
  - "the sale running into today taken as the last sale"
  - "the front list smallest saving first"
  - "a no deal on the front list"
  - "the bar at 19 days"

  Group `(q33 golden)`, target `VERDICT_FOR_SHOP_GOLDEN`: "the usual price the lower middle, in the golden". Run `$PY scripts/mutation_check.py "q33 verdict" "q33 golden"`, then the staleness check.
- [ ] **Step 9: Commit:** `git add src/shopper/verdict.py tests/test_verdict.py tests/shopper_golden.py tests/test_golden_90.py tests/golden/golden-90.sha256 scripts/mutation_check.py && git commit -m "Store first: the verdict rules (days tracked, the usual price sales included, a deal from ₪1.00, last this low, how often) and the front list; the golden 90 days gain Shufersal Universe's three stores from 2 April and ten products (q33)"`, the commit body naming the repin's moved kinds.

### Task 2: The price chart

**Files:**
- Create: `src/shopper/chart.py`, `tests/test_chart.py`
- Modify: `src/shopper/words.py` (`CHART_KEY`, `chart_label`, `chart_summary`), `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `Verdict`, `Day` (Task 1).
- Produces:

```python
DAY_WIDTH = 4
def render_chart(found: Verdict, day: date) -> str   # "" when found.days is empty
# shopper.words
CHART_KEY = ("shelf price", "on sale", "on sale, price not read")
def chart_label(kind: str, price: Decimal) -> str     # kind: "usually" | "lowest" | "highest" | "today"
def chart_summary(found: Verdict) -> str              # the <title> text
```

- The SVG: `<svg class="chart" role="img" aria-labelledby="chart-<column>" viewBox=...>` with `<title id="chart-<column>">` first. It contains:
  - `<path class="listed">`: the shown listed price over the tracked days, broken at every untracked day;
  - `<path class="sale">`: the day price on `on_sale` days with a price;
  - `<path class="unread">`: marks at the foot for sale days of unknown price;
  - when `today_price` is known, `<line class="today">` across the whole width at its height and `<circle class="today">` at today's x;
  - `<text>` labels for the usual price (when there is one), the lowest and the highest shown prices, and today's.

  After the SVG comes the key as text (`<p class="key">`), so colour is never the only signal. The style rules (`.chart .listed` grey, `.chart .sale` green, `.today` dashed) go in `PRODUCT_STYLE` (Task 3) and are tested there.

- [ ] **Step 1: Write the failing tests** in `tests/test_chart.py`:
  - `test_the_span_is_the_tracked_days_then_today`: the first tracked day is at x 0 and today at `(day - first).days * DAY_WIDTH`. A 5-day history's viewBox is narrower than a 27-day one's.
  - `test_untracked_days_are_gaps`: a promotion-hole day between two tracked days makes the listed path start again (an `M`) after the gap, with no segment across it.
  - `test_the_listed_price_grey_and_sale_days_green`: a sale day's stretch is drawn at its day price's height; a day not on sale has no sale stretch.
  - `test_a_sale_day_of_unknown_price_is_marked_without_a_price`.
  - `test_todays_price_is_a_dot_with_a_dashed_line_across`: the line runs from x 0 to the chart's right edge at today's height.
  - `test_no_today_mark_without_todays_price`: covers `not_sold`, `too_few` and `unread_today`.
  - `test_the_labels_name_the_usual_lowest_and_highest_prices` (`chart_label`'s words, in the SVG's text).
  - `test_a_text_alternative_inside_the_svg`: `<title>` is the first child, its id is unique per column, and it holds `chart_summary`.
  - `test_a_run_of_one_price_is_one_segment`: 27 days at one price give one horizontal segment.
  - `test_heights_span_the_lowest_and_highest_prices_shown`: today's price is included.
  - `test_no_chart_without_a_tracked_day`.
  - `test_the_chart_is_the_same_bytes_twice`.
  - `test_ninety_days_of_daily_changes_stay_small`: a price change every day plus weekly sale runs stays under 3,000 bytes.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_chart.py -q`. Expected: fail on import.
- [ ] **Step 3: Implement** `render_chart` and the three words. The module docstring states the drawing rules above.
- [ ] **Step 4: Run** the full test command. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q33 chart)`, target `SHOP_CHART`:
  - "an untracked day drawn across"
  - "a sale stretch on a day off sale"
  - "the unknown-price mark at the listed price's height"
  - "today's dot at the usual price"
  - "the dashed line stopping at today"
  - "the span a fixed 90 days"
  - "the lowest label from the listed prices alone"
  - "the text alternative left out"
  - "a run of one price drawn day by day"

  Run `$PY scripts/mutation_check.py "q33 chart"`, then the staleness check.
- [ ] **Step 6: Commit:** `git add src/shopper/chart.py src/shopper/words.py tests/test_chart.py scripts/mutation_check.py && git commit -m "Store first: the price chart, a store type's tracked days then today, sales in green, today's price dashed across (q33)"`.

### Task 3: The product page: the verdict, the chart, how often, the fold-out, "Elsewhere today"

**Files:**
- Modify: `src/shopper/product.py`, `src/shopper/words.py`, `src/shopper/build.py` (one verdict per pair in `_Pages`, passed to `render_product`)
- Test: `tests/test_product.py`, `tests/test_shop_words.py`, `tests/test_shop_build.py`, `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py`, and this plan's "Deviations" (the page sizes)

**Interfaces:**
- Consumes: `verdict`, `Verdict`, `counts_today` (Task 1); `render_chart` (Task 2).
- Produces:

```python
# shopper.product
def render_product(covered: Covered, pairs: Mapping[str, Pair], verdicts: Mapping[str, Verdict],
                   column_days: Mapping[tuple[str, date], ColumnDay], day: date, collected_by: str,
                   gates: Mapping[str, Gate], promotions_errors: Mapping[str, str]) -> str
BADGE_STYLE: str                                  # the shades, light and dark (Task 6 imports it)
def badge_class(found: Verdict) -> str            # "deal-1" | "deal-2" | "deal-3" | "no-deal" | "none"
# shopper.words
def on_day(day: date) -> str                       # "12 October" (shopper text: no year)
def badge(found: Verdict) -> str                   # "At Carrefour Market: DEAL · ₪1.90 off" / "At Carrefour Market: NO DEAL"
def reason(found: Verdict) -> str | None           # the design's three forms; None without a verdict
NO_VERDICT: dict[str, str]                         # the design's lines, verbatim, by call; "no_history" provisional
def not_sold(column: str, last: date | None) -> str   # "Not sold at Carrefour Market today, last seen 3 November"
def conditions(struct: Mapping) -> list[str]       # "Club members only", "When you buy 2", ...
def last_low(found: Verdict) -> str | None         # "Last this low: 12 October, at ₪9.90." / "Lowest in the 10 days tracked."
def how_often(found: Verdict) -> str | None        # "On sale on 12 of the 60 days tracked." + the last sale's sentence
def coming_sale(start: date) -> str                # "A sale starts on 14 November"
def short_badge(found: Verdict) -> str             # the badge row's text (Words this plan adds)
ELSEWHERE = "Elsewhere today"
WORKED_OUT = "How this is worked out"
```

- `build._Pages` computes `verdict(pair, key, column_days, day)` once per pair as it streams. For a covered product's column with no pair, it calls `verdict(None, key, ...)`. The front page's rows in this task are still the old rule's (`front_rows_of`).
- The page, top to bottom:
  - the title, names, barcode and size, as today;
  - the badge row with its hidden heading;
  - a `<section id="c-<key>" data-column data-chain>` per column that lists the product or has its history, in `COLUMNS` order, holding:
    - P10's warning when the chain's promotions were not read;
    - the verdict: the badge `<p class="badge <class>">`, then the reason; or the no-verdict line (`too_few` from `basket.words`, `not_sold` with `covered.last_wide`);
    - the conditions;
    - the coming sale (a record day and `next_start`);
    - the chart;
    - last this low;
    - how often;
    - `<details><summary>How this is worked out</summary>…</details>` (its contents under "Where the design leaves room");
  - `ALWAYS_SENTENCE` once.

  P7's sentences, `GAP_HEADING`, `HISTORY_HEADING`, P8's sentences, `price_history`, P9's table and the old chart go.

- [ ] **Step 1: Write the failing tests.** In `tests/test_product.py`:
  - `test_each_section_says_the_verdict_with_the_store_types_name`: "At Shufersal Deal: DEAL · ₪1.50 off" is in Deal's section (anti-goal 1).
  - `test_a_no_deal_badge_is_grey_and_writes_its_words`: class `no-deal`, text "NO DEAL". The no-deal tokens in `BADGE_STYLE` are greys in both themes: each colour's red, green and blue channels differ by at most 0x10.
  - `test_the_reason_line_names_its_days` (S8).
  - `test_each_no_verdict_line`, parametrized over every no-verdict call: the line is `NO_VERDICT[call]` verbatim and the section has no badge.
  - `test_a_not_sold_section_says_when_last_seen`: "Not sold at Shufersal Deal today, last seen 3 November".
  - `test_the_condition_beside_the_verdict`: "Club members only" and "When you buy 2".
  - `test_a_coming_sale_line`: "A sale starts on 14 November"; none on a hole morning.
  - `test_the_fold_out_holds_the_range_the_definition_every_promotion_and_no_odds`: inside `<details>`: the range note; "Listed price ₪…, before promotions, as listed in the chain's price files"; each running promotion with `FINE_PRINT` and `MORNING`; `AT_SOME_STORES` on a not-wide one; `no_odds_yet(key)`.
  - `test_elsewhere_today_has_a_badge_per_store_type_selling_it_by_saving`: badges in saving order; none for a store type not listing it today; each `href="#c-<key>"` names an existing id.
  - `test_with_the_script_blocked_every_store_types_part_is_in_the_html` (the design's "Testing"): every section, in `COLUMNS` order, holds its verdict words, reason and chart.
  - `test_nothing_is_hidden_without_the_script`: the only `hidden` is the Elsewhere heading, and every hiding rule in the style starts with `.js`.
  - `test_a_product_sold_nowhere_today_has_no_badges_and_every_part` (Review Focus 4).
  - `test_p7_p8_and_p9_are_gone`: none of `GAP_HEADING`, `HISTORY_HEADING`, "30-day median" or "Today at each column".
  - `test_every_shade_reads_in_both_themes` (S5): the WCAG contrast ratio of each badge's text on its background is at least 4.5 in the light and dark sets of `BADGE_STYLE`, and the three greens differ.

  Rewrite for the new page: `test_a_weighed_deal_is_per_kilogram` ("₪19.90 off a kilogram") and `test_the_largest_page_is_under_60_kb` (nine columns, each with 90 days of a daily price change, weekly sale runs, three promotions, 40-character names). Keep: always and never phrases, F10 per section, an open gate stops the page, names and programmes escaped in their spans, the promotions error in each of the chain's sections, the same bytes twice, the shell. Retire with their code: the P7, P8, P9, `price_history` and old-chart tests (`test_the_chart_is_the_same_with_each_prices_height_worked_once` included).

  In `tests/test_shop_words.py`, pin every phrase above with the design's examples verbatim: the badge forms; the three reason forms; `NO_VERDICT`; `not_sold` with and without a day; `last_low`'s two forms; `how_often` with "before this one", with no sale today, and with no price; `coming_sale`; `on_day` giving "12 October"; one day said as "1 day". Assert that none holds a NEVER phrase, "we", "our" or "us".
- [ ] **Step 2: Rewrite the golden's product-page assertions** in `test_the_golden_pages_windows_and_gaps` (the front page's assertions stay for Task 6).
  - G3, day 75: Sheli says "At Shufersal Sheli: DEAL · ₪3.00 off", "Usually ₪10.90, sales included (74 days tracked).", "Lowest in the 74 days tracked." and "On sale on 0 of the 74 days tracked."; Deal says "No sale today".
  - G1, day 120, at Osher Ad: "No sale today", "Last this low: 29 April, at ₪5.00." and "On sale on 31 of the 90 days tracked. The last sale ended 26 April, at ₪3.90.".
  - G4, day 85: "At Rami Levy: DEAL · ₪19.90 off a kilogram".
  - G5, day 99, at Deal: "At Shufersal Deal: DEAL · ₪1.50 off" and "Last this low: 13 February, at ₪4.50.".
  - G1, day 50, at Deal: "too few files today: 0 of 2 stores".
  - Universe, day 120:
    - U1: "It's been ₪9.90 or less on 27 of the 27 days tracked.";
    - U2: "On sale on 10 of the 27 days tracked. The last sale before this one ended 11 April, at ₪6.90.";
    - U5: "New today: no price history yet.";
    - U6: "Only ₪0.99 below its usual ₪5.00 (27 days tracked).";
    - U7: "DEAL · ₪1.00 off";
    - U8: "When you buy 2";
    - U9: "On sale at some stores only";
    - U10: "On sale, but the sale price could not be read".
- [ ] **Step 3: Run** `$PY -m pytest tests/test_product.py tests/test_shop_words.py tests/test_golden_90.py -q`. Expected: the new tests fail.
- [ ] **Step 4: Implement** the interfaces and the page. Rewrite `product.py`'s docstring to the new page. `words.py` gains the new words in its docstring's plain-words account; P7 and P8 stay there until Task 6.
- [ ] **Step 5: Run** the full test command. Expected: all pass but the pin.
- [ ] **Step 6: Repin the golden.** Expected moved names:
  - every `day/` line from the first built day (2026-01-30);
  - every final product page.

  No `site-days/`, `days/`, `forecasts/`, `scores/` or `ledger` line moves, nor the front, method, record or basket page. The reason in the commit: the product pages' verdict, chart and fold-out replace P7, P8, the price-change text and P9.
- [ ] **Step 7: Measure a real day.**
  1. Run `PYTHONPATH=src $PY -m shopper.build --day <the real day> --collected-by 11:48 --data /Users/doronreiffman/Projects/il-grocery-prices/data --site site`. This writes into the worktree's own `site/`, which is gitignored. In the main checkout's `data/` it rewrites the day's covered registry (same rules, same bytes) and adds one basket record.
  2. Run `PYTHONPATH=src $PY -m shopper.check site`. Expected: exit 0.
  3. Run `find site/p -name '*.html' -exec stat -f '%z %N' {} + | sort -n | tail -3`, and take the median too.
  4. Expected: the largest page is under 45,000 bytes. Write in "Deviations" the largest page, its barcode, the median, the days of records the day's history holds, and the golden's largest day-120 page.
  5. If the largest page is over 45,000 bytes, the chart already draws a run of one price as one segment (the design's first simplification), so stop and ask the owner. Nothing is dropped without the owner's word.
- [ ] **Step 8: Mutations.** `(q33 product)`, target `SHOP_PRODUCT`:
  - "the store type's name left out of the verdict"
  - "a no deal given a deal's shade"
  - "the badge row in COLUMNS order"
  - "a store type not listing it given a badge"
  - "the fold-out without F10"
  - "a section hidden in the HTML"
  - "a coming sale on a hole morning"
  - "a not-sold section without its last-seen day"
  - "the reason line left out"

  `(q33 words)`, target `SHOP_WORDS`:
  - "a shopper date with its year"
  - "the always-on form for a small saving"
  - "'before this one' with no sale today"
  - "the day count from every tracked day in the reason"

  Re-point `(q22 product)` mutations whose code stayed. Retire those of the removed P7, P8 and P9 code, the old chart (including "every price drawn at the lowest's height (q22 speed)") and `price_history`; list each in the commit. Run `$PY scripts/mutation_check.py "q33 product" "q33 words" "q22 product" "q22 P9"`, then the staleness check.
- [ ] **Step 9: Commit:** `git add src/shopper/product.py src/shopper/words.py src/shopper/build.py tests/test_product.py tests/test_shop_words.py tests/test_shop_build.py tests/test_golden_90.py tests/golden/golden-90.sha256 scripts/mutation_check.py docs/store-first-plan.md && git commit -m "Store first: product pages say Deal or No deal for each store type, with the reason, the price chart, last this low, how often, a fold-out and Elsewhere today; P7, P8 and P9 retired (q33)"`.

### Task 4: The script: search plus the picker

Built on Question 1's answer.

**Files:**
- Modify: `src/shopper/static/search.js`, `tests/search_harness.js` (an op `picker` and an op per pure function), `tests/test_search_js.py`, `scripts/mutation_check.py`

**Interfaces:**
- Consumes: the page markup Task 5 renders. Tests use the harness's fake pages until then:
  - every page's header holds `<a id="pick-link" href="<up>index.html#pick">`;
  - a store page's `<main data-store="<key>">`;
  - the root's `<section id="pick" data-page="root">`;
  - a product page's `section[data-column]` (id `c-<key>`), `nav.badges` with `a[data-column]`, and `h2.elsewhere[hidden]`.
- Produces, exported when `module` exists:

```js
const NAMES = /*COLUMNS*/[["carrefour-city", "Carrefour City"], ...]/*COLUMNS*/;  // COLUMNS as JSON; a test reads it back
const PICK_KEY = "store";
readPick(storage)            // a key of NAMES, or null (missing, unknown, or storage throws)
writePick(storage, key)      // never throws
rootOf(href)                 // "../index.html#pick" -> "../"
redirectFor(pick, hash)      // "store/<pick>.html", or null with no pick or hash "#pick"
headerFor(pick, root)        // {name, href: root + "store/<pick>.html", change: root + "index.html#pick"} or null
arrange(pick, parts, badges) // {open, notSold, elsewhere, heading} (below)
notSoldLine(key)             // "Not sold at <name> today"
onBadge(pick, key)           // {show: key, setPick: key or null}: per Question 1
```

- `arrange`:
  - a pick among the parts: `open` is the pick, `elsewhere` the badges without it, `heading` true;
  - a pick not among the parts: `notSold` is the pick, `elsewhere` all the badges, `heading` true;
  - no pick: `open` is the first badge (else the first part, else null), `elsewhere` all the badges, `heading` false.
- `start()`:
  - adds `js` to `<html>`;
  - finds the root from `#pick-link`;
  - rewrites the header for a pick;
  - on a store page, writes the pick;
  - on the root, redirects (`location.replace`) unless the hash is `#pick`;
  - on a product page, shows the `open` part, writes the not-sold line, moves the badge row after the open part and unhides its heading, and on a badge click acts as `onBadge` says;
  - starts search where `#q` exists, asking for `<root>search/…` and `<root>p/<code>.html` and linking `<root>p/<code>.html`.

- [ ] **Step 1: Write the failing tests** in `tests/test_search_js.py`:
  - `test_the_scripts_store_names_are_the_columns`: the JSON between the `/*COLUMNS*/` markers equals `[[c.key, c.name] for c in COLUMNS]`.
  - `test_the_scripts_not_sold_line_is_the_words`: `notSoldLine(key) == not_sold(key, None)` for every key.
  - `test_read_pick`, parametrized: a valid key; an unknown key gives null; missing gives null; a `getItem` that throws gives null. Covers Review Focus 1.
  - `test_write_pick_never_throws`.
  - `test_root_of`: "index.html#pick" gives "" and "../index.html#pick" gives "../".
  - `test_redirect_for`, parametrized.
  - `test_arrange`, parametrized, with the cases above plus no parts and no badges. Covers Review Focus 4.
  - `test_on_badge`: per Question 1.
  - `test_a_store_page_remembers_its_store`.
  - `test_the_root_sends_a_remembered_pick_to_its_store_page_and_change_does_not` (Review Focus 5).
  - `test_the_header_names_the_pick_on_every_page`.
  - `test_a_product_page_opens_the_picks_part_and_lists_the_rest_elsewhere`.
  - `test_a_badge_tap_shows_its_part_and_keeps_the_pick` (call 6).
  - `test_search_from_a_store_page_asks_from_the_root`: requests `../search/pieces.json` and `HEAD ../p/<code>.html`, and links `../p/<code>.html`.
  - `test_blocked_storage_leaves_search_working` (Review Focus 1).

  Every existing search test passes unchanged, since its fake page sits at the root.
- [ ] **Step 2: Run** `$PY -m pytest tests/test_search_js.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Rewrite the script's header comment: one script for the site, search and the picker; what it keeps (one key, never sent anywhere); and that no fact needs it.
- [ ] **Step 4: Run** the full test command. Expected: all pass.
- [ ] **Step 5: Mutations**, `(q33 script)`, target `SHOP_SEARCH_JS`:
  - "an unknown stored key taken as the pick"
  - "blocked storage throws"
  - "the root redirect ignoring #pick"
  - "a badge tap with a pick changing it"
  - "the open part not the pick"
  - "the picked store's badge kept in Elsewhere"
  - "a store page not remembering"
  - "search asking from the page's folder"
  - "the names table a key short"
  - "nothing marked js"

  Run `$PY scripts/mutation_check.py "q33 script" "q22 search"`, then the staleness check.
- [ ] **Step 6: Commit:** `git add src/shopper/static/search.js tests/search_harness.js tests/test_search_js.py scripts/mutation_check.py && git commit -m "Store first: search.js gains the store picker: one remembered store type, the header, the root's redirect, a product page arranged for the pick (q33)"`.

### Task 5: The root picker, the nine store-type front pages, the header and the upload paths

**Files:**
- Modify: `src/shopper/shell.py` (the header's store link, the script tag on every page), `src/shopper/pages.py` (`render_root`, `render_store`, `store_path`, `PICK_GROUPS`; `render_front` replaced), `src/basket/page.py` (`Frame.script`, written into the head when given; the basket's own pages byte for byte), `src/shopper/build.py` (writes `index.html` and the nine `store/<key>.html`), `src/shopper/check.py`, `src/basket/site.py` (`PAGE_FOLDERS` gains `"store"`), `template.yaml` (`WriteSite` gains `store/*`), `site-template.yaml` (rule `old-store-pages`, prefix `store/`, 30 days)
- Test: `tests/test_shop_pages.py`, `tests/test_product.py` (the shell), `tests/test_page.py`, `tests/test_shop_check.py`, `tests/test_shop_build.py`, `tests/test_site.py`, `tests/test_basket_template.py`, `tests/test_site_template.py`, `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: the script's markup contract (Task 4).
- Produces:

```python
# shopper.shell
def page(title, main, day, collected_by, links, style="", up="../", store: str | None = None) -> str
SCRIPT_TAG = '<script src="{up}search.js" defer></script>'   # in every page's <head>
# shopper.pages
PICK_TITLE = "Which store are you in?"
PICK_GROUPS = (("shufersal", ("shufersal-deal", "shufersal-express", "shufersal-sheli", "shufersal-universe")),
               ("carrefour", ("carrefour-city", "carrefour-market")), ("ramilevy", ("ramilevy",)),
               ("osherad", ("osherad",)), ("yochananof", ("yochananof",)))     # the design's order, by chain
def store_path(column: str) -> str            # "store/<key>.html"
def render_root(day: date, collected_by: str) -> str
def render_store(column: str, rows, counts, day, collected_by, marking_none, browse, *, ready: bool) -> str
def column_ready(column_days, column: str, day: date) -> bool   # front_ready for one column
```

- The header (`band`) holds `<p class="store">`. With no store it holds `<a id="pick-link" href="{up}index.html#pick">Pick your store</a>`. On a store page it holds the store's name linking to its page, " · ", and `<a id="pick-link" …>change</a>`.
- The root page, at `up=""`:
  - `FRONT_TITLE`;
  - `ROOT_LINE`;
  - `<section id="pick" data-page="root">` with `PICK_TITLE` and, per chain, its name and a link per store type to `store_path(key)`;
  - the hiring line kept from today's front page.
- A store page, at `up="../"`, with `<main data-store="<key>">`, holds today's front content for that column alone, under the old rule: the column's rows, a lead line over them, the old fold-out, and no store radios. Task 6 replaces this content.
- `check.py`:
  - the one script is allowed as `<script src="<up>search.js" defer></script>` at the page's own depth (`"../" * name.count("/")`) and refused in any other form;
  - every `store/*.html` and `p/*.html` carries the ALWAYS phrases;
  - `index.html` is held to the rest;
  - each `store_path(key)` must be in the build.
- `basket.site.upload` puts `store/` with the pages. `scripts/publish.sh` syncs by suffix, so it needs no change; read it and confirm that `store/*.html` falls under `--include '*.html'`.

- [ ] **Step 1: Write the failing tests.**
  - `test_shop_pages.py`:
    - `test_the_root_is_the_picker_grouped_by_chain`: nine links in `PICK_GROUPS` order; `PICK_TITLE`; `FRONT_TITLE`; `ROOT_LINE`; the hiring line; `id="pick"`; no deals table.
    - `test_each_store_page_names_its_store_and_puts_search_first`.
    - `test_a_store_page_lists_only_its_own_rows`.
  - `test_product.py` / `test_shop_pages.py`:
    - `test_every_page_carries_the_one_script_at_its_depth`: root, method and record pages use `search.js`; `p/`, `browse/` and `store/` pages use `../search.js`.
    - `test_the_header_says_pick_your_store_before_a_pick`.
  - `test_page.py`: `test_a_frame_with_a_script_writes_it_and_the_baskets_own_pages_keep_their_bytes`.
  - `test_shop_check.py`:
    - `test_a_script_at_the_wrong_depth_fails`;
    - `test_the_one_script_passes_on_every_page`;
    - `test_a_store_page_without_an_always_phrase_fails`;
    - `test_index_html_needs_no_always_phrase`;
    - `test_a_missing_store_page_fails`;
    - the existing `test_a_second_script_fails`, still passing.
  - `test_site.py`: `test_store_pages_go_up_with_the_pages`.
  - Template tests:
    - `test_role_grants_exactly_what_the_code_does`: `built` gains `store_path("osherad")`;
    - `test_old_versions_of_rebuilt_pages_expire_after_30_days`: nine rules, `_rebuilt_prefixes` from `store_path`;
    - `test_no_lifecycle_prefix_matches_a_record_key`, still passing.
  - `test_shop_build.py`: `test_the_build_writes_the_root_and_nine_store_pages`.
  - Golden: the front assertions read `store/<key>.html` in place of `index.html`, under the old rule, with the same rows per column. Add `test_the_golden_root_is_the_picker`.
- [ ] **Step 2: Run** those test files. Expected: the new tests fail.
- [ ] **Step 3: Implement**, with each touched module's docstring updated: shell, pages, check, site, and the templates' comments.
- [ ] **Step 4: Run** the full test command, then `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: all pass, lint clean.
- [ ] **Step 5: Repin the golden.** Expected: every `day/` line and every final page moves (the header and the script tag). Also the new `store/` pages. `site-days/`, `days/`, `forecasts/`, `scores/` and `ledger` do not move. Reason: the header and the one script on every page, the root as the picker, a front page per store type.
- [ ] **Step 6: Mutations**, `(q33 picker)`:
  - `SHOP_SHELL`: "the script at the root's depth on every page"; "the pick link without #pick";
  - `SHOP_PAGES`: "a store page without data-store"; "the picker a store type short"; "the picker in COLUMNS order";
  - `SHOP_CHECK`: "a script allowed at any depth"; "store pages not held to the always phrases"; "a missing store page passes";
  - `SITE`: "store/ pages not uploaded";
  - the role test's target: "the role without store/*";
  - `SITE_TEMPLATE`: "no lifecycle rule for store/".

  Re-point the `(q22 lifecycle)` and `(q22 check)` mutations the edits moved. Run `$PY scripts/mutation_check.py "q33 picker" "q22 lifecycle" "q22 check" "q22 front"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/shell.py src/shopper/pages.py src/shopper/build.py src/shopper/check.py src/basket/page.py src/basket/site.py template.yaml site-template.yaml tests scripts/mutation_check.py && git commit -m "Store first: the root page is the store picker, a front page per store type under store/, the header and the one script on every page; the role and the lifecycle rule name store/ (q33)"`.

### Task 6: The front pages' rule and words

**Files:**
- Modify: `src/shopper/pages.py` (`render_store` to the new rule; `FrontRow`, `front_rows_of`, `ordered` and the store radios removed), `src/shopper/words.py` (the store page's words; P7 and P8 removed), `src/shopper/build.py` (per-column `DealRow`s and counts; "count line" out of names and docstrings), `src/shopper/siteday.py` (the per-column `front` block), `src/shopper/measures.py` (the removed functions, under "Where the design leaves room")
- Test: `tests/test_shop_pages.py`, `tests/test_shop_build.py`, `tests/test_siteday.py`, `tests/test_measures.py`, `tests/test_shop_words.py`, `tests/test_golden_90.py`, `tests/golden/golden-90.sha256`
- Modify: `scripts/mutation_check.py`

**Interfaces:**
- Consumes: `DealRow`, `front_list`, `on_list`, `checked`, `FRONT_LIMIT` (Task 1); `BADGE_STYLE`, `badge_class` (Task 3); `store_path`, `column_ready` (Task 5).
- Produces:

```python
# shopper.pages
@dataclass(frozen=True)
class StoreFront:
    column: str
    ready: bool                 # column_ready
    rows: tuple[DealRow, ...]   # front_list order, all N
    checked: int                # M
    promotions: int             # the column's wide promotions running today, distinct by id
    products: int               # their products
def render_store(front: StoreFront, column_days, day, collected_by, marking_none, browse) -> str   # replaces Task 5's signature
# shopper.words
SEARCH_LABEL = "Type a product name or the barcode"
FOLD_INTRO = "Promotions checked against what the product usually costs, sales included, over up to 3 months."
def headline(column: str, deals: int, checked: int) -> str   # "At Carrefour Market today: 1,130 of 4,210 promotions are actually deals."
def store_lead(front: StoreFront, today: ColumnDay) -> str   # the "None yet" line, the hole's too_few, the promotion hole's line, or headline()
STORE_RULES: tuple[str, ...]                                  # the fold-out's rules in shopper words (provisional)
def store_promotions_line(column: str, promotions: int, products: int) -> str
```

- A store page, top to bottom (design, "What a visitor sees" 4):
  - `FRONT_TITLE` and `FRONT_SUBTITLE`;
  - the search box (`SEARCH_LABEL`);
  - `store_lead`;
  - the two filter checkboxes;
  - the table of the first `FRONT_LIMIT` rows: the product's link and barcode; the deal badge, with its shade class and `conditions`; the price today; the usual price;
  - the fold-out "How a deal passes", in the design's order, holding:
    - `FOLD_INTRO`;
    - `STORE_RULES`, with what the filters hide and `marked_none` for the store's chain;
    - the one-deal story: the top row's badge, reason, last this low and how often, under "One of today's deals";
    - `store_promotions_line`;
    - a note carrying the four ALWAYS phrases;
    - the method link.

  The rows carry `data-club` and `data-spend` from the verdict's struct.
- The site-day file: `columns[key]["front"] = {"ready", "deals", "checked", "promotions", "products", "rows": [...]}`. Each shown row records the barcode, today's price, the usual price, the saving, the days its reason rests on, `per`, `buy`, `restrictions`, `programmes` and `min_spend`. The top-level `counts` and `front_rows` go, and `_earlier` keeps each column's `deals` and `checked`.

- [ ] **Step 1: Write the failing tests.**
  - `test_shop_pages.py`:
    - `test_a_store_types_list_is_its_deals_passing_the_bar_by_saving` (Goal 6).
    - `test_the_list_shows_the_top_100`: 101 deals give 100 rows, and the headline says 101.
    - `test_the_headline_counts_the_same_set`.
    - `test_none_yet_until_the_store_type_has_20_days`.
    - `test_a_store_type_not_read_today_says_so_and_lists_none` (Review Focus 2): a promotion hole gives "Sale prices could not be read today."; a hole gives the too-few line.
    - `test_a_row_shows_the_badge_its_condition_todays_price_and_the_usual_price`.
    - `test_the_filters_need_no_script`, rewritten: two checkboxes, no store radios.
    - `test_the_fold_out_says_how_a_deal_passes_for_that_store_type`: `FOLD_INTRO` verbatim, the count line naming the store type, and the four ALWAYS phrases.
    - `test_the_story_is_the_top_rows_verdict`.
    - `test_the_store_page_is_the_same_bytes_whatever_the_rows_order`.

    Retire the old front tests (depth order, P7's story, the radios, `front_rows_of`).
  - `test_siteday.py`: `test_every_number_on_each_store_page_is_in_the_site_day_file`, replacing the "Every number on the front page" test; `test_a_revision_keeps_each_columns_deals_and_checked`.
  - `test_shop_build.py`: `test_the_build_counts_each_store_types_deals_and_checked`, with the tests named for "count line" renamed. Afterwards, `grep -rn "count line" src tests` prints nothing.
  - Golden, front assertions under the new rule:
    - day 75: `store/shufersal-sheli.html` holds one row, G3's "DEAL · ₪3.00 off".
    - day 99: `store/shufersal-deal.html` holds G5's row. The old rule listed none: ₪4.50 equals Deal's 90-day low, but the usual price is ₪6.00.
    - day 50: City, Market, Osher Ad, Rami Levy, Sheli and Yochananof each list G1's "DEAL · ₪1.10 off"; `store/shufersal-deal.html` says "too few files today: 0 of 2 stores" and lists none.
    - day 120: `store/shufersal-universe.html` lists U2, U3, U8 and U7 in that order, with "At Shufersal Universe today: 4 of 6 promotions are actually deals.".
- [ ] **Step 2: Run** those test files. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Remove the dead code listed under "Where the design leaves room". Afterwards `grep -rn "gap_sentences\|history_sentences\|price_history\|on_front\|front_rows_of\|GAP_HEADING\|HISTORY_HEADING\|ACROSS_HEADING" src tests` prints nothing. Update the docstrings of `pages.py`, `build.py` and `siteday.py`.
- [ ] **Step 4: Run** the full test command. Expected: all pass but the pin. Coverage stays at or above 95%, and `verdict.py` and `chart.py` stay at 100%.
- [ ] **Step 5: Repin the golden.** Expected moved names: `day/` lines; every `site-days/` file (the per-column front block); the `store/` pages; `record.html` only if it moves. `forecasts/`, `scores/`, `ledger`, `days/` and the product pages do not move. Reason: the front pages' rule, Deal by the usual price, per store type.
- [ ] **Step 6: Mutations.**
  - `(q33 front)`, target `SHOP_PAGES`:
    - "a store page listing another store type's rows"
    - "the list cut at 10"
    - "the rows smallest saving first"
    - "a promotion-hole day listing deals"
    - "the headline's N from the shown rows"
    - "the fold-out without the ALWAYS note"
  - `SHOP_BUILD`: "checked counted below the bar"; "a no deal counted in N".
  - `(q33 siteday)`, target `SHOP_SITEDAY`: "the site-day rows not the page's"; "a revision dropping a column's numbers".
  - `(q33 golden)`: "a deal from ₪0.99, in the golden".

  Retire, listing each in the commit: "front page at or below the low, in the golden (q22 golden)", the `(q22 front)`, `(q22 P7)` and `(q22 P8)` mutations, `(q31 words)` on P7 and P8, and any `(q32 …)` mutation on the removed front words. Run `$PY scripts/mutation_check.py "q33 front" "q33 siteday" "q33 golden"`, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper tests scripts/mutation_check.py && git commit -m "Store first: each store type's front page lists its deals by saving, the top 100, under a headline counting the same set; P7's front test and P7 and P8's words retired (q33)"`.

### Task 7: The method page, README and the docs

**Files:**
- Modify: `src/shopper/pages.py` (`RULES`: P7, P8 and P9 replaced by S0 to S8 and the front list, in plain words, using `DEAL_MIN`, `SHADES`, `FRONT_LIMIT`, `READ_DAYS`, `MIN_FRONT_DAYS` and `RECENT_DAYS`), `tests/test_shop_pages.py` (`test_the_method_page_states_the_rules_with_the_codes_constants`), `README.md`, `docs/operations.md`, `docs/README.md`, `tests/golden/golden-90.sha256` (`method.html` and the `day/` lines), `scripts/mutation_check.py`

- [ ] **Step 1: Write the failing test.** `test_the_method_page_states_the_rules_with_the_codes_constants` asserts:
  - each of S0 to S8 is named;
  - "₪1.00", the three bands, "the higher of the two middle values", "90 days" and "20 of the 30 days" appear, each from its constant;
  - the store-type picker is explained: the pick is kept in the browser and sent nowhere;
  - "listed price" has its definition.
- [ ] **Step 2: Run** the test. Expected: fail.
- [ ] **Step 3: Implement the method page.**
- [ ] **Step 4: Update the docs.**
  - `README.md`: the lines saying "a front page of deals below every price of the past 90 days", and the product-page summary (line 5 and the shopper site's state), rewritten to the new rule. Every fact is checked against the code.
  - `docs/operations.md`: the site check's description ("every always-phrase on each store type's page and every product page"; "`search.js` the one script, on every page at its own depth"; "the nine store pages present"), and the hand build's list of pages (the root picker and `store/`).
  - `docs/README.md`: `store-first.md` (the store picker, the verdict and the chart) and `store-first-plan.md` among the plans.
- [ ] **Step 5: Run** the full test command, then repin the golden. Expected: `method.html` and the `day/` lines move.
- [ ] **Step 6: Mutations**, `(q33 method)`, target `SHOP_PAGES`: "the method page's ₪1.00 not the code's"; "the lower middle stated". Run the group, then the staleness check.
- [ ] **Step 7: Commit:** `git add src/shopper/pages.py tests/test_shop_pages.py tests/golden/golden-90.sha256 README.md docs/operations.md docs/README.md scripts/mutation_check.py && git commit -m "Store first: the method page states S0 to S8 and the front list; README and the operations notes follow (q33)"`.

### Task 8: The whole-branch review

- [ ] **Step 1:** Dispatch a reviewer that has not seen the build, on Fable (`fable`), or on the newest Opus while Fable is at its usage limit, with the report naming the swap. Give it `git diff main...q33-store-first`, `docs/store-first.md`, the sections of `docs/shopper-site.md` it changes, and this plan. Ask for findings by severity against:
  - the design's anti-goals: a verdict for the wrong store read as if right; "Deal" on a price sold most days; a verdict hiding thin history; colour as the only signal; words saying a chain did wrong; a fact that needs the script;
  - its calls;
  - this plan's Review Focus and its readings under "Where the design leaves room";
  - page size;
  - the upload paths, role and lifecycle rule.

  The reviewer reads only: no commits, no `gh`, no push, no AWS, no network.
- [ ] **Step 2:** Check each finding against its source before acting on it, since a finding is a claim. Fix what holds, test-first, each fix with its mutation, and re-review the fixes in a scoped review (Opus). Log every change from this plan under "Deviations".

### Task 9: The owner's read of a real day's build

- [ ] **Step 1:** Build the real day into the worktree's `site/` and check it, as in Task 3 Step 7. Expected: `shopper.check` exits 0. Write in "Deviations" the largest product page and the history's days of records.
- [ ] **Step 2:** Serve the folder locally: `$PY -m http.server --directory site 8000`, run in the background. Search pieces do not load from `file://`. Give the owner the address `http://localhost:8000/` and a reading list:
  - the root picker, and "change" from a store page;
  - each of the nine store pages;
  - product pages chosen from the build:
    - a Deal in each shade;
    - a No deal of each form;
    - each no-verdict line the day holds;
    - a weighed product;
    - a product sold at many store types;
    - the largest page;
    - a product not sold at a picked store type;
  - each read with the script on and with it blocked in the browser, at phone width (390 px), in light and dark themes.

  The owner navigates; this session never drives the browser.
- [ ] **Step 3:** The owner's word changes are a fix round, test-first: the words pinned, the golden repinned with the reason. Log each under "Deviations", with the provisional words this plan proposed and the owner's final ones. Stop the server. Merging waits for the owner's go.

### Task 10: Full test run, coverage, the q33 mutation groups, README's counts

- [ ] **Step 1:** Run the full test command. Expected: every test passes, coverage is at or above 95%, and `verdict.py` and `chart.py` are at 100%.
- [ ] **Step 2:** Run `$PY scripts/mutation_check.py "q33"` (every q33 group; it edits files in place, so nothing else runs until it prints that the files are restored), then the staleness check. Expected: every q33 mutation CAUGHT, `none stale`. The full check is CI's weekly run.
- [ ] **Step 3:** Run `/Users/doronreiffman/Projects/il-grocery-prices/.venv/bin/cfn-lint --regions il-central-1 -- template.yaml site-template.yaml`. Expected: clean.
- [ ] **Step 4:** Write the counts Steps 1 and 2 printed (the test count, the coverage, the mutation count from the staleness check), with the date, in README.md's "Tests" row and "Tests that are themselves tested", and in "Deviations". Commit `git add README.md docs/store-first-plan.md && git commit -m "README: test and mutation counts after store first (q33)"`. Stop: the merge, push and deploy are the owner's go.

## Deploying this branch (the owner's go; not a task)

What the deploy needs to know, after the merge:

- **Both stacks change.**
  - The collector stack (`template.yaml`): `BasketFunction`'s `WriteSite` gains `store/*`. The function's code ships in the same deploy, so the code never writes `store/` without the permission. Deploy after a morning's 12:33 site run has published and before the next one.
  - The site stack (`site-template.yaml`): one lifecycle rule, `old-store-pages`. It can go any time; until it does, old versions of the nine store pages are kept, at cents.
  - Read each change set as the operations notes say. Expected:
    - the collector stack: `BasketFunction` and `CollectorFunction` modified (their zips); the role SAM builds from `BasketFunction`'s `Policies` modified (`WriteSite` gains `store/*`); and the DuckDB layer churn seen on every deploy;
    - the site stack: `SiteBucket` modified.

    Nothing else should be replaced or removed.
- **The first morning after the deploy rewrites every page.** Every product, browse and fixed page changes bytes: the header, the script tag, the verdict sections. This is no change in cost, since every page goes up every morning anyway (Q2). The new pages are the nine `store/<key>.html`, about 270 writes a month. `index.html` becomes the picker, so a link to the old front table now opens the picker. `search.js` is the same key with new content. Browsers keep it five minutes after the invalidation, so search on a `store/` page can fail for those minutes.
- **The site-day file changes shape** from the first day the new code builds: a front block per store type, and no top-level `counts` or `front_rows`. Earlier days' files keep their shape. A hand rebuild of a day the old code published would differ and need `--revise` with a reason (B12), so leave old days alone.
- **Page size.** The measurement (Task 3, Task 9) rests on the real day's history, about ten days of records. Charts grow with sale runs over the 90 days. Re-measure the largest product page against 45,000 bytes as the history fills (late January). The site check refuses a page over 60,000 bytes, and the site run then uploads nothing (`SiteCheckFailed`).
- `scripts/publish.sh` needs no change: it syncs by suffix, and `store/*.html` goes up with `*.html`. The first upload after the deploy follows "Deploying step one" in `docs/operations.md` as before.
- No new schedule, alarm or dependency. Monthly cost: under $0.10 more, the design's estimate. The site stays `noindex`.

## Deviations

(Append here when reality forces a change from this plan: what changed, why, and when.)

- Baseline on q33-store-first at 0e689af (2026-11-11): 2,529 tests passed, coverage 99.86%, 820.7 s (the plan's fd2d30d figure, 2,514, predates the mutation-check work merged since).
- Task 1, from the pre-flight scan before it (2026-11-11), each a reading the plan left open or a case it could not catch:
  - S0 is read per product, as the plan's worked golden values read it: a day the product is not listed is not one of its tracked days. `shopper.verdict`'s docstring says so.
  - `counts_today` also requires a `kind`: a `RewardType` 0 struct (`kind` None) never counts, as "A `RewardType` 0 promotion is not a sale" reads it. The interface's comment named only wide, valid and the dates.
  - With no promotion counting today, a running wide struct with a kind (its price unread) gives `price_unread` before a running struct with a kind that is not wide gives `some_stores`; the plan's order put both in its step 4 without an order between them.
  - `test_each_no_verdict_call` gains a case of 13 unknown-price sale days of 26 tracked, which must be judged: the plan's 14-of-27 and 13-of-27 cases cannot catch "more than half" broken to "at least half" on an odd count.
  - `tests/test_golden_90.py` imports `shopper.verdict` inside `test_the_golden_verdicts`, so before the module existed only that test failed and the rest of the golden module still ran.
- Task 1, the RED run (Step 4) added `--continue-on-collection-errors` to the brief's command: `tests/test_verdict.py` imports `shopper.verdict` at module level, and without the flag its collection error stops pytest before the golden module runs.
- Task 1, readings the plan was silent on, made in `shopper.verdict`:
  - The calls before today's promotions (`too_few`, `not_sold`, `unread_today`) carry no `struct`, no today's price, no `last_low` and no `last_sale`, and `on_sale_today` False: today is not known, so S7 cannot tell "this one" from the last sale. Their tracked days are given all the same.
  - `on_sale_today` is today's `Point.on_promotion` from call 4 on (a running wide struct with a kind, its price read or not), so `price_unread` is on sale today and `some_stores` is not.
  - `front_list` sorts every row it is given; the caller keeps the deals (`on_list`) and cuts to `FRONT_LIMIT`.
- Task 1, the mutations: "a not-wide deal in the day price" and "an invalid deal in the day price" break `day_price`'s call of `counts_today`, and "a not-wide promotion judged" and "an unreadable price judged" break `verdict`'s, so each rule's own test must catch its own break. "The shade bands an agora off" raises the two upper bands' floors by ₪0.01. The `TIME_LIMIT` comment in `scripts/mutation_check.py` now counts 86 other target sets (`tests/test_verdict.py` is a new one).
- Task 1, the golden: every hand-worked value of the plan's Step 3 was worked again in `tests/shopper_golden.py`'s docstring and agrees; none is disputed. `store_list` takes the day (day 1 by default), and `stores_on` gives a chain's stores of a day.
- Task 1, the repin (Step 7): 128 names moved, all of Step 7's kinds, and one more: the final site's `basket.html`. The basket page states each chain's store counts, and from 2 April Shufersal's are 8 rather than 5 ("from 8 stores' files", "5 of 8 list it", "files from 8 of its 8 stores"); every total is unchanged (Shufersal ₪15.10). It is the cause Step 7 gives for the `days/` files, Shufersal's included stores, on a page Step 7's list left out. No `day/` line before 2026-04-02 and no `forecasts/`, `scores/`, `ledger` or `tables/scored/` line moved. Reported to the controller before the commit, as Step 7 says; the controller accepted it (2026-11-11), the basket's words printing each chain's store count (`src/basket/words.py`).
- Task 4 was built in a worktree of its own (branch `q33-script`, from 0e689af) beside Tasks 1 to 3, then cherry-picked onto q33-store-first after Task 1; `scripts/mutation_check.py` merged without a conflict.
- Task 4, the harness: there is no op named `picker`. The `page` op gained a small fake DOM (elements, single compound selectors, `before` and `after`, `hidden`, `classList`), fakes for `documentElement`, `localStorage` (an object, one whose `getItem` and `setItem` throw, or a getter that throws) and `location`, and taps on badges; each pure picker function has an op of its own. A page given no DOM is a search box alone at the root, so every earlier search test runs unchanged.
- Task 4, the words: `test_the_scripts_not_sold_line_is_the_words` checks the design's Words table, "Not sold at <name> today" without the last-seen part, since `shopper.words.not_sold` does not exist yet; Task 3 re-points it to `not_sold(key, None)`.
- Task 4, readings made in the script:
  - The script hides with its own `hidden` attribute rather than `.js` CSS rules ("Nothing is hidden without the script"), so a script that fails after adding `js` hides nothing. Later pages keep both halves of that rule (Tasks 3 and 5): their style carries `[hidden]{display:none!important}`, so that no `display` rule of theirs shows a hidden part or badge, and no rule of it sets `display` on `section[data-column]`, `nav.badges a` or `h2.elsewhere`. Task 3's `test_nothing_is_hidden_without_the_script` holds the product page to both, exempting the `[hidden]` rule from "only `.js` rules hide" (a controller ruling, in place of the brief's "every hiding rule starts with `.js`").
  - A product page is arranged only where `nav.badges` is, since the record page's scorecard also has `section[data-column]` sections. Every product page carries `nav.badges`, empty when no store type sells the product today (Task 3), and no other page does.
  - A store type's front page writes its pick before the header is drawn, so its header names its own store type on the first visit and with storage blocked (the brief listed the header first).
  - A badge tap only shows its part and never hides one: the pick's own badge is not in the row, so hiding the pick's part would leave no way back to it. With no pick, the first tap sets the pick and later taps on that page only show (Question 1 and call 6). The header is not redrawn after a tap; it names the pick from the next page on.
  - The not-sold line is a `<p class="not-sold">` before the "Elsewhere today" heading and the row.
  - `rootOf` gives "" (the page's own folder, as before q33) for an href that is not `<root>index.html#pick`, and a pick link with no href gives the same, so search still works there (the review's Minor 2).
  - The script stays ASCII, as before: the header's middle dot is written as the JavaScript escape for U+00B7.
- Task 4, tests beyond the brief's list: `test_header_for`, `test_the_script_marks_every_page_js`, `test_the_header_without_a_pick_asks_for_one`, `test_a_store_pages_header_names_its_own_store`, `test_a_product_page_without_the_picks_part_says_not_sold`, `test_a_product_page_with_no_pick_opens_the_first_badge_and_keeps_the_row_first`, `test_a_badge_tap_with_no_pick_shows_its_part_and_sets_the_pick` and, from the review, `test_a_pick_link_with_no_href_leaves_search_working`.
- Task 4, the mutations: 32 `(q33 script)` on `SHOP_SEARCH_JS`, the brief's ten and 22 more: a throwing getItem, and a throwing setItem, stopping the script; the pick kept under another key; a redirect from a page that is not the root; a redirect with no pick; a badge tap with no pick not setting it; a second tap changing the pick the first set; a badge tap not showing its part; with no pick, the first part opened over the first badge; with no pick and no badges, no part opened; the not-sold line not written, and naming the key; the badge row not moved after the open part, and moved with no pick; Elsewhere today never shown; the header without its change link; the header's store link, and its change link, not from the root; a store page's header not naming its own store; the root always the page's folder; a link that is not the picker's taken as the root; a pick link with no href stopping the script. The review's Minor 1 asked for five of them (the first-badge and first-part fallbacks, the redirect with no pick, `rootOf`, the header's root prefix). "A code unescaped in the link (q22 search)" is re-pointed at `"p/" + escapeHtml(code)` with the same break, since a result's link now starts with the root. No new target set: the `TIME_LIMIT` comment's count stands.
- Task 4, the golden: the brief missed that the golden pin moves with `search.js`. Each day's build copies the script into the site (`src/shopper/build.py`, the fixed pages), so its bytes are in every `day/` line and in `site/search.js`. The repin on top of Task 1's pin moved 92 names: the 91 `day/` lines and `site/search.js`, nothing else.
- Task 4, a tooling trap: a backslash-u escape typed through the editing tools can arrive as the raw character. It changed `search.js`'s NORMALIZE table once while the task was built; the staleness check caught it (five q22 mutations stale), and the table's bytes were restored from git.
- Task 2 was built in a worktree of its own (branch `q33-chart`, from bfff635) beside Task 1's review and Task 4's build, then cherry-picked onto q33-store-first after Task 4 and its two commits (the build and fix round 1) squashed into one; `scripts/mutation_check.py` merged without a conflict.
- Task 2, the labels (the controller's ruling): the lowest and highest labels are the lowest and highest DAY prices of the tracked days, as the design says ("Labelled: the usual price, the lowest and highest day prices in the span"), not this plan's "lowest and highest shown prices". The heights still span the listed prices drawn, so the grey line fits; with no day price, neither label is drawn. A listed price above every day price (listed ₪12.90, on sale at ₪9.90 every day) is tested, and "the highest label the shown maximum" must be caught by it.
- Task 2, the dashed line at today's price runs across the plot, from x 0 to the end of today's day, not through the labels' column (the controller accepts this reading of the design's "across the whole chart"). Today's dot is at today's x, `(day - first).days * DAY_WIDTH`, where yesterday's line ends.
- Task 2, the SVG also carries `width`, `height` and `font-size` (in units), beyond the attributes this plan lists, so a short history draws a short chart without a style, and the labels' spacing (14 units) and column (7 units a character) match their 12-unit text. Task 3's PRODUCT_STYLE should set only `max-width: 100%` and `height: auto` on `.chart`, never `width: 100%` (it would blow a 5-day chart up to the full width), and no font size on `.chart text`.
- Task 2, the key names only the kinds of mark the chart draws ("shelf price" always, "on sale" with a sale stretch, "on sale, price not read" with a foot mark), each after an `<i class="listed|sale|unread">` swatch for Task 3 to style, set apart by " · " as CHAINS_LINE's names are (fix round 1).
- Task 2, the words: `shopper.words.CHART_KINDS` was added beside the three names this plan lists, the labels' kinds in the text alternative's order; `chart_label` refuses any other kind. One more provisional word: "Price chart.", the text alternative of a chart with no label (every tracked day a sale day of unknown price, and today's price unknown).
- Task 2, the labels' choice is written twice, in `shopper.chart` (the labels drawn) and in `chart_summary` (the title), since the brief fixes `chart_summary(found)` and `shopper.words` cannot import `shopper.chart`; `_names_the_labels` in `tests/test_chart.py` pins the two together over every partial verdict the file builds (fix round 1).
- Task 2, the mutations: 20 `(q33 chart)`, the plan's nine and eleven more: "the highest label the shown maximum" (the controller's ruling); "the labels drawn over each other" and "the labels stacked at the top" (each label at its price's height, fix round 1); "today's price left out of the heights"; "the days drawn in the order given"; "the key naming every mark, drawn or not"; "the key's entries run together"; and four on `chart_summary`'s own copy of the labels' choice, under a new cross-target, `WORDS_FOR_SHOP_CHART = ("src/shopper/words.py", ["tests/test_chart.py"])`, since `tests/test_shop_words.py` does not test the chart's words. "The span a fixed 90 days" writes a literal 90, so a NameError cannot catch it. The `TIME_LIMIT` comment now counts 87 other target sets (`tests/test_chart.py` is a new one; `WORDS_FOR_SHOP_CHART` runs the same file).
- Task 2, the size: a 90-day chart whose listed price changes every day, with a three-day sale every week, is 1,677 bytes with its key; a more typical 90 days (two shelf prices, a sale week a month) is 745 bytes. The old chart's drawing was at most 257 bytes, plus its key.
- Task 3, the controller's rulings from the pre-flight scan and the earlier tasks' reviews (2026-11-11), each in place of a reading of the brief:
  - The markup `search.js` reads: `<section data-column="<key>" id="c-<key>" data-chain="<chain>">` per part (the brief's bare `data-column` was a slip: the script reads the attribute's value); `<nav class="badges">` with `<a data-column="<key>" href="#c-<key>" class="badge <shade>">` badges, there and empty when nothing sells the product today; `<h2 class="elsewhere" hidden>` before it. `test_the_markup_search_js_reads` pins it on rendered pages, the empty row included.
  - Nothing is hidden by a `.js` rule (the script hides with its own `hidden` attribute, Task 4): `BADGE_STYLE` carries `[hidden]{display:none!important}`, and no rule sets `display` on a part, a badge or the heading. `test_nothing_is_hidden_without_the_script` asserts that, in place of the brief's "every hiding rule starts with `.js`".
  - The chart's style: `.chart` sets `max-width: 100%` and `height: auto` (never `width: 100%`) and no font size; paths `fill: none`; the shelf price `var(--bar)`, the sale days and the unread marks `var(--accent)`, today's line dashed, all tokens with a dark value in the base style. `test_the_charts_style` pins it (the plan sent the chart's style test here).
  - `last_low` gives nothing unless today's price is known and a day before today has a day price; `how_often` gives nothing with no tracked day, so no page says "0 days tracked".
  - `test_the_scripts_not_sold_line_is_the_words` (Task 4's) now reads `notSoldLine(key) == not_sold(key, None)` for every key.
- Task 3, code removed with its last caller (the controller's ruling: `price_history` and the P7, P8, P9 code when this task removes their last caller, else Task 6). In `shopper.product`: P9's `_across` and `_cell`, the old `_chart` with `_x`, `_runs`, `DAY_WIDTH`, `TOP`, `BOTTOM` and `MARK`, P7's and P8's calls, and `field_conditions`' `programmes` switch, which only P9 turned off. In `shopper.words`: P8's `history_sentences` and `_run` (the product page was their only caller, so this plan's "P7 and P8 stay there until Task 6" now holds for P7 alone, which the front page's story still reads), `price_history`, `chart_key`, `across`, `starts_on` (now `coming_sale`), `HISTORY_HEADING`, `NOT_LISTED` and `ACROSS_HEADING`; the docstring's P8, price-history and P9 accounts with them. Left for Task 6, in `shopper.measures` outside this task's files: `promoted_today`, `gaps`, `promotion_days` and `promotion_days_of` now have no caller outside the module (P8's; this plan's Task 6 list names the first two).
- Task 3, a file the brief did not list: `tests/test_shop_check.py` reads a product page's section tag (`<section data-column="…" data-chain="…">`, now with `id="c-…"` between) and linked P9's `#across` anchor, which is gone; its three lines follow the new markup (a section's id in place of `#across`). It is in this task's commit.
- Task 3, readings the brief left open, made in `shopper.words` and `shopper.product` (provisional, with the words, until the owner's read):
  - The conditions beside the verdict, joined by "; ": the restrictions in question K's order (club, card, other), then the quantity ("When you buy 2"), then the minimum spend.
  - A weighed product's three reasons all say "a kilogram" after the usual price, or after today's price in the always-on form; the badge after the saving. "Last this low" and "How often" give their prices bare, as the chart's labels do.
  - The badge row's words for the two calls without a NO_VERDICT line: "too few files today" (a hole; the counts are the section's) and "not sold today".
  - A part of a product with no point today has nothing about today in its fold-out but F10's sentence: the verdict's line says not sold, or too few files. On a hole with a point, the fold-out keeps today's median from too few files (`_today`, moved), so a hole's too-few line shows twice in the part, beside the verdict and in the fold-out.
  - A badge with no verdict ("none") is the page's surface with a border; `.badge` sizes itself with `width: fit-content`, never a `display` rule.
  - The not-sold line takes the last day from the registry's `last_wide`, as Call 10's line did; shopper text drops the year, so a last-seen day more than a year back would read as this year's (none can before November 2027).
- Task 3, tests beyond the brief's list: `test_the_badge_class`, `test_the_charts_style`, `test_the_markup_search_js_reads`, `test_a_hole_day_says_no_last_listed_across` and `test_a_hole_morning_lists_no_promotion_across_the_column` (kept, rewritten for the fold-out), and in `tests/test_shop_words.py` `test_the_conditions_in_shopper_words`, `test_a_weighed_verdict_is_a_kilograms` and `test_last_this_low_needs_todays_price_and_a_day_price`; in `tests/test_shop_build.py` `test_the_one_pass_works_each_sections_verdict_once_and_the_page_says_it`. `test_each_no_verdict_line` covers the plan's `no_history` too (seven calls; `too_few` and `not_sold` have their own tests).
- Task 3, the golden repin: 107 names moved, exactly this task's Step 6 kinds: all 91 `day/` lines (2026-01-30 to 2026-04-30) and all 16 final product pages (`site/p/*.html`). No `site-days/`, `days/`, `forecasts/`, `scores/` or `ledger` line moved, nor the front, method, record or basket page. The reason: the product pages' verdict, chart and fold-out replace P7, P8, the price-change text and P9.
- Task 3, the real day (Step 7, 2026-11-10, the latest day with all five chains' items tables in the main checkout's `data/`): the build wrote 24,730 product pages and 223 others in 96 s; `shopper.check site` exit 0. The largest page is 36,586 bytes (`p/7290111347863.html`, nine store types, every one listing it), then 36,585 and 36,212; the median 13,570; no page over 45,000 bytes, so nothing was simplified. The day's history holds 9 days of records before the day (1 to 9 November 2026), so no part says more than "9 days tracked". The golden's largest day-120 page is 18,547 bytes (G1, `p/2000000000077.html`); the test's synthetic worst case (nine columns, a daily price change, a three-day sale every week, three promotions today, 40-character names) is 42,187 bytes, under the 45,000 line.
- Task 3, the mutations retired with their code (the rule each guarded):
  - P7's sentences on the product page (P7 itself stays, on the front page's story, with its words mutations): "P7 on a hole morning (q22 product)"; "P7 for a deal at some stores (q22 product)"; "P7's change sentence once per deal (q22 product)"; "P7's change sentence left out (q22 product)"; "an empty change paragraph on one day of records (q31 product)".
  - The old chart (its rules live on in `shopper.chart`: gaps never filled, nothing drawn from nothing, a text alternative, a key, each height worked once; Task 2's (q33 chart) mutations guard the gaps, the text alternative and the key, and none guards the other two: with `shopper.chart`'s guard of a verdict with no tracked day removed, a test fails only on an IndexError, and the new chart keeps no cache of heights to guard): "the history chart without promotion days (q22 product)"; "a gap in the chart's line filled (q22 product)"; "a chart drawn with no day counted (q22 product)"; "the chart read out to a screen reader (q22 product)"; "the chart's key left off (q22 product)"; "every price drawn at the lowest's height (q22 speed)"; and its key's words, "the chart's key naming the chain (q22 words)", with `across`'s, "across names the chain (q22 words)".
  - The price-change text: "the price history left off (q22 product)"; "the price history's changes of 30 days (q22 words)"; "the price history said with no day of records (q22 words)".
  - P9's row: "P9 sorted by price (q22 P9)"; "P9 without the columns that do not list it (q22 P9)"; "a P9 deal per unit when weighed (q22 P9)"; "P9's conditions left out (q22 P9)"; "P9's minimum spend left out (q22 P9)"; "a P9 deal at some stores (q22 P9)"; "a P9 deal on a hole morning (q22 P9)"; "a P9 hole claimed as listed (q22 P9)"; "P9 without the morning's files (q22 P9)"; "P9's buy N left out (q22 P9)"; "P9's conditions without their source (q22 P9)"; "P9's deals without the fine print (q22 P9)"; "P9 with the programmes' names (q22 P9)".
  - P8's sentences (`history_sentences`): "P8's days with records over 30 days (q22 words)"; "the days not read left unsaid (q22 words)"; "no promotion said when some days were not read (q22 words)"; "no history said with no day of records (q22 words)"; "on promotion today not said (q22 words)"; "the runs not said to be before today (q22 words)"; "a run said to end while on promotion today (q22 words)"; "a run from the first day read pinned (q22 words)"; "a run seen to the last day read pinned when today is not known (q22 words)"; "a run open at the end when today is off promotion (q22 words)"; "a run on promotion today and yesterday said open (q22 words)"; "every run shown open (q22 words)"; "one run read as plural (q22 words)"; "the days between runs left out (q22 words)"; "days ago in the plural for one day (q22 words)"; "the last run said ended with a gap after it (q22 words)"; "the last run said seen with no gap after it (q22 words)"; "the last run said ended with today unknown (q22 words)"; "the runs said seen when every day was read (q22 words)"; "the runs not said seen with a gap outside them (q22 words)"; "a gap inside a run said to hide a run (q22 words)"; "a gap before the first run not said to hide one (q22 words)"; "a gap after the last run not said to hide one (q22 words)"; "a gap between the runs not said to hide one (q22 words)"; "the window's days the files say nothing of from its second day (q22 words)"; "P8 not naming the column when no promotion was listed across it (q22 words)"; "P8's promotions not said to be across the column (q22 words)"; "a run's start beside a gap pinned (q22 words)"; "a run's end beside a gap pinned (q22 words)"; "days between runs beside a gap stated exactly (q22 words)"; "days between runs bounded by the earlier end only (q22 words)"; "days between runs bounded by the later start only (q22 words)"; "days ago beside a gap stated exactly (q22 words)"; "an end beside a gap dated exactly (q22 words)"; "an end said when nothing after it was read (q22 words)"; "an end said only on today's reading (q22 words)"; "P8's one day of records said as a count of days (q31 words)"; "P8's one day not read said to hold no promotion (q31 words)"; "P8's one day on promotion said to hold none (q31 words)"; "P8's one day with no promotion said in, not on, it (q31 words)"; "the promotion history's days read over 30 days (q22 speed)".
- Task 3, the mutations re-pointed, each with its break: "F10 for the chain, not the column (q22 product)" (F10 is in the fold-out, where the chain is `BY_KEY[key]`'s); "a hole's price claimed as listed (q22 product)", "last listed across said when listed across today (q22 product)" and "last listed across said on a hole (q22 product)" (the fold-out's today, `point` never None there); "fine print label left out (q22 product)" (the local is `labels`, beside `words.conditions`); "a section for every column (q22 product)" and "sections out of name order (q22 product)" (in `section_keys`); "the section's conditions without the programmes' names (q22 product)" (`field_conditions` names every programme, its switch gone with P9); "not listed today said on a hole (q22 product)" (no page says "not listed today" now: the break makes a hole's line the not-sold line, the same claim the few files cannot make).
- Task 3, the new mutations: 18 `(q33 product)`, the brief's nine ("the coming sale on a hole morning" breaks `today.record` to `today.present`, since "a start date on a hole morning (q22 product)" already drops it) and nine more: every deal in the lightest shade; the badge row's heading shown in the HTML; an empty badge row left out; the style without its hidden rule; every no-verdict call said as no sale; the conditions left out; the chart left out; how often left out; and, on `SHOP_BUILD`, a section's verdict worked from no pair. 12 `(q33 words)`, the brief's four and eight more: the badge without the store type's name; a weighed saving without its kilogram; the badge row's line not in lower case; the not-sold line without its last-seen day; the conditions without their capital; how often counting only the days with a price; last this low with no day price before today; how often said with no tracked day. No new target set.
- Task 3, the mutation run: `scripts/mutation_check.py "q33 product" "q33 words" "q22 product" "q22 P9" "q22 words" "q31 words"` (every P9 one retired, `q22 words` and `q31 words` run since `shopper.words` lost P8 and its tests were rewritten): 168 CAUGHT, none timed out, "Files restored. Every mutation was caught."; the staleness check: 2514, none stale.
- Task 5 was built in a worktree of its own (branch `q33-picker`) and its report carried these lines for this section; Task 6 folded them in.
- Task 5, the controller's ruling (2026-11-11, option A): every page's HTML header reads "Pick your store" with `<a id="pick-link" href="{up}index.html#pick">`, store pages included. This replaces the brief's "<store name> · change" in a store page's HTML: Task 4's search.js always writes the name before the pick link, so the two together named the store twice (measured through the harness). `page(..., store=key)` sets only `<main data-store="<key>">`. With the script blocked, a store page names its store in its tab title and in the line over its title.
- Task 5, readings accepted by the controller: both role tests gain store/ (`built` is in `test_role_prefixes_are_the_codes_keys`); `ROOT_LINE` and `PICK_TITLE` are in `shopper.pages`, "Pick your store" in `shopper.shell` (`PICK`), and "change" stays search.js's alone; a store page's lead line counted its own column's rows, and its fold-out's promotion count stayed the site's whole until Task 6.
- Task 5, readings made in the build:
  - a store page was: the store's name over the title (`<p class="at">`), the title, the subtitle, the search box, the lead line, the two filters (no store radios), the column's rows, the note, the fold-out, the story;
  - no hiring line on a store page (the root keeps it);
  - the root has no search box and no browse link;
  - the header's store line sits between the site's name and the chains' line;
  - the script tag goes on its own line after `</style>`.
- Task 5, `front_ready` was removed with its last caller; `column_ready(column_days, column, day)` replaces it. Its test is rewritten for one column, another column's days counting nothing.
- Task 5, files the brief did not list: `scripts/time_site_run.py` (it imported `render_front` and `front_ready`); `tests/test_search.py` (the browse page's script); `tests/test_basket_handler.py` (the built site's listing gains `store`); the docstrings of `src/shopper/product.py` and `src/shopper/search.py` (both said "no script").
- Task 5, the mutations: 16 new (q33 picker), the brief's 11 and five more. Two retired: "a column's filter rule left out (q22 pages)" (the store radios) and "the front page not held to the always phrases (q22 check)" (index.html is held to none now). 19 re-pointed, as listed in its commit message. The run covered the brief's four groups plus the whole "q22 pages" and "front words" groups (test_shop_pages' front tests were rewritten) and the shell's six earlier mutations: 250 CAUGHT; staleness 2528, none stale. No new target set.
- Task 5, the repin: 132 names, all of Step 5's kinds: 91 `day/` lines, every final page (index, method, record, basket, 12 browse, 16 product) and the 9 new store pages. No `site-days/`, `days/`, `forecasts/`, `scores/`, ledger or `search.js` line moved.
- Task 5, `test_index_html_needs_no_always_phrase`: the root carries "listed price" in the credit line, so the test pins the three phrases it lacks.
- Task 5, the full suite: 2,673 passed, 99.86%, 751.0 s.
- Task 6, the controller's rulings from the pre-flight scan and the earlier tasks' reviews (2026-11-11), each in place of a reading of the brief:
  - "a store page listing another store type's rows (q33 front)" is on `SHOP_BUILD`, with a `tests/test_shop_build.py` test that each store type's front holds its own column's rows alone: `render_store` neither filters nor sorts, since its `StoreFront` arrives per column in `front_list`'s order. The brief's "the rows smallest saving first" is dropped: Task 1's "the front list smallest saving first (q33 verdict)" guards the order.
  - `store_lead`'s order: a hole today (`basket.words.too_few`), then a promotion hole ("Sale prices could not be read today."), then "None yet: a product needs 20 days of price history first." while the store type is not ready, else `headline`.
  - Store pages keep Task 5's header (option A: the HTML reads "Pick your store"; the script names the store), `<main data-store="<key>">`, links from `../` and no `<nav class="badges">`. Their badges are `shopper.product.BADGE_STYLE`'s, with its `[hidden]` rule; no rule sets `display` on `section[data-column]`, `nav.badges a` or `h2.elsewhere`.
  - Dead code went with its last caller, each proved by grep: in `shopper.measures`, `promoted_today`, `gaps`, `promotion_days` and `promotion_days_of` (P8's, left by Task 3) beside the plan's `gap`, `Gap`, `depth`, `on_front`, `changes` and `Change`; in `shopper.words`, `lead_line`, `promotions_line`, `window_note`, `shown_below`, `percent_text` and P7's helpers (`starts_on` was already gone, renamed `coming_sale` in Task 3); `shopper.pages.SEARCH_LABEL` ("Find a product: name or barcode") gave way to the brief's `shopper.words.SEARCH_LABEL`. `whole`, `promotion_points` (its promotion-hole filter and READ_DAYS default), `runs`, `runs_of` and `days_since` stay, used by the chart, the record page, the verdict and the forecast, with their (q22 P7) and (q22 P8) mutations.
  - The mutation "the search box without its script (q22 pages)", which since Task 5 removes the shell's one script from every page, is renamed "the shell without the one script (q22 pages)", the same break (Task 5's review).
  - The stale references to Task 5's removed `front_ready` went: the comment in `shopper.pages` (with WINDOWS_NOTE), `lead_line`'s docstring (with `lead_line`) and a docstring in `tests/test_shop_build.py`, now `column_ready` (Task 5's review).
- Task 6, readings made in the build:
  - A store page keeps Task 5's line naming the store over the title (`<p class="at">`): on a hole or a promotion hole the lead line names no store, and the header names it only with the script. The brief's order otherwise holds: the title and subtitle, the search box, the lead line, the filters, the table, the fold-out.
  - A row's deal badge is `badge`'s words, the design's "At Carrefour Market: DEAL · ₪1.90 off", in a `<span class="badge <shade>">`, so every verdict on the page names its store type (the design's first anti-goal); the golden's "DEAL · ₪3.00 off" is inside it. Its conditions (`conditions`, shopper words) follow in a `<small>`. Today's price and the usual price are `price_text`'s, a new function: "₪3.50", or "₪50.00 a kilogram" for a weighed product. The heads: "Product", "Deal", "Price today", "Usually". A row with none keeps the old empty row, "No deals to show.".
  - The old row's conditions carried "fine print not read: club-only or other conditions may apply"; the new row's are the product page verdict's shopper words, without it. The product page's fold-out keeps the label on every promotion; the store page carries it nowhere now (for the owner's read).
  - The fold-out's note is ALWAYS_SENTENCE, the product pages' fixed sentence (its comment and the module's docstring now say product and store pages), in `<p class="note">`; TABLE_NOTE under the table went.
  - `shopper.pages.shown_rows(front, today)` gives the rows a page shows: the first FRONT_LIMIT, none on a hole or a promotion hole even when rows are handed in (Review Focus 2; the verdicts' own calls already make none). The site-day file records the same rows through it, and its `deals` is every deal of the front, as the headline's N is.
  - The promotions line counts, per store type, the promotions listed across it today distinct by promotion id, and their products (the old count was the site's, distinct by chain and id); as before only at a store type with a record today and its promotions read. The deals and the checked count covered products only, those with a page to link, as the old rows did.
  - The marked-none sentence names the store's own chain alone, when its files mark no restricted promotion today.
  - The column block's `counts` lost `front_rows` with the top-level `counts` and `front_rows`: `front.deals` says it per store type. `_earlier` keeps `{"front": {<key>: {"deals", "checked"}}}` for all nine. A day published by the old code has no front block, so `--revise` of such a day stops on a KeyError; "Deploying this branch" already says to leave old days alone.
  - `build.main` prints "store pages: 1 deal of 1 checked" (the deals and checked over the nine) in place of the old "front page" line.
  - The provisional words, pinned in `tests/test_shop_words.py` until the owner's read (Task 9): STORE_RULES' six rules, STORY_HEADING "One of today's deals", NONE_YET, NOT_READ_TODAY (NO_VERDICT's line with its full stop), the headline's forms and the promotions line ("Today Shufersal Sheli lists 1,840 promotions carried by at least half its stores, on 6,210 products.").
- Task 6, files the brief did not list: `scripts/time_site_run.py` (it called `render_store`'s old signature and `pages.counts()`); `tests/test_shop_guard.py` (its "other numbers" came from `Counts`); `tests/test_product.py` (GAP_HEADING went; its literal stays in the "gone" list); `tests/shopper_golden.py` (its docstring's account of the front pages, under the new rule); `src/shopper/product.py` (two docstrings that named the front page's rows).
- Task 6, tests beyond the brief's list: in `tests/test_shop_words.py`, `test_the_store_pages_words`, `test_the_store_pages_lead_line` and `test_the_front_title_and_subtitle_are_the_owners_plain_words` (the subtitle's half of the lead line's old test); in `tests/test_shop_build.py`, `test_the_store_page_has_the_days_deal_and_headline`, `test_a_store_page_says_none_yet_before_its_store_type_has_20_days_of_records` and `test_the_headline_says_none_of_the_promotions_once_a_store_type_has_20_days` (the old lead line's, rewritten) and `test_the_promotions_line_counts_each_store_types_promotions_today` (renamed from "the count line"); in `tests/test_measures.py`, `test_whole_is_half_up_and_a_tie_goes_away_from_zero` and `test_the_front_lists_bar_is_twenty_of_the_30_days`, since `whole` and the bar's constants lost their tests with `gap` and `on_front`. The golden day of the build tests has no promotion file, so every store type read that day is a promotion hole there; the "None yet" build test writes Osher Ad's 19 days by hand.
- Task 6, the golden: the front assertions under the new rule, the brief's four days and day 85 (G4 at Rami Levy, a kilogram's, beside G3 at Sheli). The repin moved 191 names, exactly Step 5's kinds: all 91 `day/` lines, all 91 `site-days/` files (the front block) and the 9 `store/` pages. `record.html` did not move, nor any `forecasts/`, `scores/`, ledger, `days/` or product page line. The reason: the front pages' rule, Deal by the usual price, per store type.
- Task 6, the mutations retired with their code (the rule each guarded), 123:
  - P7's gap, its lows and its changes (`shopper.measures.gap`, `changes`, `depth`), which only the old front page's story still read: "median of the 90 days (q22 P7)"; "the median taken in day order, not sorted (q22 P7)"; "depth over the deal, not the median (q22 P7)"; "at or below counted as below (q22 P7)"; "the deal rounded to two places in the days at or below (q22 P7)"; "a gap with no day of records in 30 (q22 P7)"; "the 90-day low from the 30-day window (q22 P7)"; "the 30-day low from the 90-day window (q22 P7)"; "a change before the window counted (q22 P7)"; "a change on the window's first day left out (q22 P7)"; "the changes read from the 30-day window alone (q22 P7)"; "a change's earlier record day taken as its own (q22 P7)"; "the changes' window length ignored (q22 P7)"; "the gap's changes over the 90 days (q22 P7)".
  - the old front page's test (`shopper.measures.on_front`: the deal below every listed price of the 90 days, the 20 days, a record today), replaced by Deal against the usual price and the bar (`shopper.verdict.on_list`): "front page at or below the low (q22 front)"; "front page without the twenty days (q22 front)"; "front page's twenty days of the past 90 (q22 front)"; "front page over the 30-day low (q22 front)"; "the front test on the exact deal (q22 front)"; "the front test on the exact low (q22 front)"; "front page on an invalid deal (q22 front)"; "front page on a deal at some stores (q22 front)"; "front page on a day with no record (q22 front)"; "front page needing more than twenty days (q22 front)"; "a front row on a hole day (q22 pages)"; "front page at or below the low, in the golden (q22 golden)".
  - P8's days between runs and its reading of today (`shopper.measures.gaps`, `promoted_today`), whose last caller, P8's sentences, went in Task 3: "gaps counted with their ends (q22 P8)"; "today read from the window's last day (q22 P8)"; "today read without the history's rule (q22 P8)".
  - the old front rows (`shopper.pages.front_rows_of`: one per column, the lowest deal passing the old test), their order by depth (`ordered`), the old row's cells (the depth, the fine print label), FRONT_RULES' bar sentence and P7's story: "front rows by price (q22 pages)"; "front rows by the exact depth alone (q22 pages)"; "front rows of one shown percent not by the exact depth (q22 pages)"; "a front row with no shown gap ranked as 0% (q22 pages)"; "front rows by the shown percent, shallowest first (q22 pages)"; "two rows for one column and product (q22 pages)"; "one row for a product's two columns (q22 pages)"; "a row not passing the front test (q22 pages)"; "the highest deal shown, not the lowest (q22 pages)"; "a front row for a promotion not running today (q22 pages)"; "front rows ordered by barcode as text (q22 pages)"; "what a row needs said over the 90 days (q22 pages)"; "a front row's depth from the exact figures (q22 pages)"; "a front row's gap under half a percent shown as 0% (q22 pages)"; "a front row's conditions without the fine print label (q22 pages)"; "the story with no P7 (q22 pages)"; "the shown gap's percent from the exact figures on the front page (q22 pages)".
  - the old lead line's readiness passed by the page and its rows beating "None yet", the note under the table (TABLE_NOTE) and the old fold-out's rules (RULES_INTRO, FRONT_RULES, WINDOWS_NOTE): "the lead line deaf to whether a product could pass (front words)"; "the lead line's "None yet" said beside a row (front words)"; "the note under the table without before promotions (front words)"; "the note under the table without the morning's files (front words)"; "the note left off the page (front words)"; "the note under the table without what Below by is (front words)"; "the fold-out without the price read (front words)"; "the fold-out without the hole morning (front words)"; "the fold-out's low not at the store format (front words)"; "the fold-out's low said of every price the chain listed (front words)"; "the fold-out's rules said to be enough on their own (front words)"; "the windows sentence naming the 30 days twice (front words)"; "the fold-out without the windows' days with records (front words)".
  - the count line (its below, its promotions distinct by chain and id across the site) and the old front rows in the site-day file (each column's count of them, their order, their deal and gap, the revision's count line): "the count line's below not the front rows' products (q22 build)"; "a promotion counted once a column, not a chain (q22 build)"; "a column's front rows counted over every column (q22 site-day)"; "the front rows not in the page's order (q22 site-day)"; "a front row's deal written exact for the eye (q22 site-day)"; "a front row's gap from the exact figures (q22 site-day)"; "a revision keeps no count line (q22 site-day)".
  - P7's sentences (`shopper.words.gap_sentences` and its helpers, `window_note`, `shown_below`, `percent_text`, CHANGES_SHOWN): "P7's change sentence dropped when there is one (q31 words)"; "P7's first sentence not saying its one day inside its brackets (q31 words)"; "P7's percent written without the words' rule (q22 words)"; "a capped list without its tail (q22 words)"; "a change across a gap in the records dated one day (q22 words)"; "a change between consecutive days given two days (q22 words)"; "a change list not capped (q22 words)"; "a change the shown figures do not show stated (q22 words)"; "a change's figures not rounded for the eye (q22 words)"; "a count without its days with records (q22 words)"; "a gap under half a percent said as 0% (q22 words)"; "a low said on its days with records, not over them (q22 words)"; "a short window counted as a full one (q22 words)"; "a short window's low said as one with gaps (q22 words)"; "a short window's low without its first day (q22 words)"; "a tail on five changes (q22 words)"; "a window count without before today (q22 words)"; "a window note in the plural for one day (q22 words)"; "a window note's one day in figures beside the one-day form's words (q22 words)"; "a window with gaps' days at or below said of the 90 (q22 words)"; "changes joined without then (q22 words)"; "no change left unsaid on two days of records (q31 words)"; "no change said on one day of records (q31 words)"; "not below said of a deal below the median (q22 words)"; "one day of records in a count said since its date (q31 words)"; "one day of records said as a count of days (q22 words)"; "one day's date after a comma outside brackets (q31 words)"; "one day's date in brackets inside P7's brackets (q31 words)"; "one day's price above the deal said below it (q22 words)"; "one day's price against the deal compared exactly, not as shown (q22 words)"; "one day's price at the deal said above it (q22 words)"; "one day's price at the deal said as a figure, not as the deal (q31 words)"; "one day's price at the deal said below it (q22 words)"; "one day's price below the deal said at it (q22 words)"; "one low said when the windows hold other days (q22 words)"; "rose for fell (q22 words)"; "the 30's one day of records beside more in the 90 said as a count of days (q22 words)"; "the 30-day low said over the 90's days (q22 words)"; "the cap at six changes (q22 words)"; "the days at or below counted on the exact deal (q22 words)"; "the days at or below out of the 30's days (q22 words)"; "the days at or below without P6's days with records (q22 words)"; "the gap worked from the exact figures (q22 words)"; "the gap written as the deal (q22 words)"; "the lows from one window (q22 words)"; "the median not rounded for the eye (q22 words)"; "the median's days counted over the 90 (q22 words)"; "the oldest five changes shown, not the newest (q22 words)"; "the one window's days at or below said of the 90 (q22 words)"; "the percent worked from the exact figures (q22 words)"; "the tail counting the changes shown, not seen (q22 words)"; "the tail's window phrase not the sentence's (q22 words)"; "the unchanged 30 days not said before today (q22 words)"; "two lows said when the windows hold the same days (q22 words)"; "unchanged in the past 30 days said of a window with gaps (q22 words)"; "under 1% said of a gap of 1% (q22 words)".
  - Not stale but missed in the run (its text stays in `shopper.product`, read now by no store page): "a front row's conditions without their source (q22 pages)", the old rows' conditions with their source. The same break of the same text, `field_conditions`' source, is guarded on the product page by "a condition without its source (q22 product)", so a re-pointed copy would only repeat it.
- Task 6, the mutations re-pointed, each with its break, 24: "the club-only filter hiding nothing (q22 pages)" and "the minimum-spend filter hiding nothing (q22 pages)" (the marks read the verdict's promotion); "the story from the last row (q22 pages)"; "a store page listing every column's rows (q33 picker)" (now on `SHOP_BUILD`: the fronts' own-column filter dropped; the new "(q33 front)" one breaks the same filter to the chain's columns, a distinct break); "the lead line left off", "the fold-out open by default", "the fold-out left off", "the chains marking none left out of the fold-out", "the fold-out's counts left off", "the build's front always ready", "the build's front never ready", "the promotions line said to be every promotion", "the lead line without thousands separators", "the lead line's \"None yet\" never said", "the lead line's one product said as products" and "the lead line's rows said as none" (front words: the lead line is `store_lead` and `headline`, the counts the store type's promotions line); "a product counted with no promotion listed across", "a store page not built" (q33 picker), "pages for today's wide products only" and "the front page without the browse pages" (q22 build); "a front row without its conditions (q22 site-day)" (a shown row's); "the count line without thousands separators (q22 words)" (the store type's promotions line); and "the percent rounded down in the words (q22 words)", renamed "the percent rounded down on the record page (q22 words)" and retargeted from `tests/test_shop_words.py` to `tests/test_shop_pages.py` (`MEASURES_FOR_SHOP_PAGES`): the words state no percent now, and with `whole` rounding down only the record page's tests fail (its scores by month and its calibration; `tests/test_chart.py`, `tests/test_product.py` and `tests/test_record_numbers.py` pass); and "a front row for a promotion that starts tomorrow (q22 pages)", renamed "a store type's promotion that starts tomorrow counted (q22 pages)" and retargeted from `tests/test_shop_pages.py` to `tests/test_shop_build.py` (a new constant, `PRODUCT_FOR_SHOP_BUILD`): the store pages no longer read `shopper.product.running_today`, the build's promotions line does.
- Task 6, the new mutations, 12: 9 (q33 front), the brief's five ("a store page listing another store type's rows" on `SHOP_BUILD`, breaking the fronts' filter to the chain's columns; "the list cut at 10"; "a promotion-hole day listing deals"; "the headline's N from the shown rows"; "the fold-out without the ALWAYS note") and its two on `SHOP_BUILD` ("checked counted below the bar", "a no deal counted in N"), and two more: "the fold-out naming every chain marking none" and "a store type's promotion counted once a product" (`SHOP_BUILD`); 2 (q33 siteday), "the site-day rows not the page's" and "a revision dropping a column's numbers"; 1 (q33 golden), "a deal from ₪0.99, in the golden", which lowers the comparison by an agora on `VERDICT_FOR_SHOP_GOLDEN`. Four target constants left with no mutation were removed (`MEASURES_FOR_SHOP_GOLDEN`, `SHOP_WORDS_FOR_SHOP_PAGES`, `MEASURES_FOR_SHOP_WORDS`, `PRODUCT_FOR_SHOP_PAGES`) and one added (`PRODUCT_FOR_SHOP_BUILD`); the target sets are 88 as before, so the `TIME_LIMIT` comment's count stands.
- Task 6, the mutation run: `scripts/mutation_check.py "q33 front" "q33 siteday" "q33 golden" "q22 pages" "q33 picker" "front words" "q22 build" "q22 site-day" "q22 words" "q22 P7" "q22 P8" "q22 front" "q33 words" "q22 guard"` (the brief's three groups and every group whose code or tests this task changed): 323 selected, 321 CAUGHT, none timed out, 2 missed, the two `shopper.product` mutations above; after the one was re-pointed and the other retired, `"a store type's promotion that starts tomorrow counted" "a section's verdict worked from no pair"`: both CAUGHT, "Every mutation was caught."; the staleness check: 2417, none stale.
- Task 6, the full suite: 2,637 passed (the old front, P7 and P8 tests went), 99.86%, `verdict.py` and `chart.py` at 100%, 744.7 s.
- Task 7, the method page as built: `shopper.pages.store_rules()` writes S0 to S8, the front page's list and the pick when the page is rendered, from the constants as they stand, so `test_the_method_page_states_the_rules_with_the_codes_constants` changes each one (DEAL_MIN, SHADES, READ_DAYS, MIN_FRONT_DAYS, RECENT_DAYS, FRONT_LIMIT) and sees the page change. Built at import, like P1 to P10, a figure written in by hand ("₪1.00") would pass any test of the page as it is, so the brief's "each from its constant" could not be caught. RULES now holds P1 to P6 and P10 and FORECAST_RULES F1 to F11; the page lists P, then S0 to S8, the list and the pick, then F. The no-verdict lines and "None yet" are `shopper.words`' NO_VERDICT and NONE_YET, so the method page follows any change to those words at the owner's read (Task 9). The pick's key is `shopper.pages.PICK_KEY`, which the test checks against search.js's own.
- Task 7, text on the method page that the removal of P7, P8 and P9 made false or left pointing at nothing, rewritten to the code at HEAD: P2's hole ("without P7's facts" now "with no verdict (S4)"), and its first sentence gives the listed price's definition (the brief's) and the chart's name for it; P6's second sentence ("A window with fewer than 20 of 30 or 60 of 90 such days says so ('23 days of records since 1 November 2026')": no page says so since Task 6 removed P7's window note), now the front list's 30 days, the verdict's 90 and S8; P10's "promotion history", now S0's days tracked; F4's run, now S7's (the same runs: `shopper.measures.runs_of` over `promotion_points`, as S7's over the tracked days); F10's "measured history (P8)"; MEASURED's "facts and counts of P7 and P8" and "depth".
- Task 7, S3 states a promotion's conditions as "their conditions from the chain's fields (P5) named beside the verdict", the wording of Task 6's fix to STORE_RULES (the controller's note, 2026-11-11).
- Task 7, README.md: beyond line 5 and the shopper site's state (the brief's), two more lines stated the old rule and were rewritten: the "Why" paragraph ("whether today's promotion is below the prices it has been listed at lately") and the claims bullet ("reports a promotion's measured gap to the product's own listed prices"). The state line says the code deployed on 10 November 2026 came before the store picker and the verdict, and line 5 that an earlier version of the code has been in AWS since then: this branch's deploy is the owner's go ("Deploying this branch"). README's test and mutation counts are left for Task 10.
- Task 7, docs/operations.md: beyond the brief's three places (the hand build's pages, the site check, the review step's root and store pages), five more statements this branch had made false: the build's printed line, now `store pages: N deals of M checked` (the controller's addition, from Task 6's review; `shopper.build.main`); the review step's product page (P9's row and P7's and P8's headings are gone) and its search box (the root has none); the lifecycle rules, nine since Task 5's `old-store-pages`; and the site run's page folders, `store/` among them (`basket.site.PAGE_FOLDERS`). The check's script rule is stated as `shopper.check` enforces it: no script but `search.js`, at the page's own depth; that the build puts it on every page is `tests/test_shop_check.py`'s `test_the_one_script_passes_on_every_page`.
- Task 7, left as it is, for the controller: the record page's days-read sentence still points at "(P8)" ("counted as neither on nor off promotion (P8)", `shopper.pages._days_read`), which the method page no longer has; the rule it means is S0 now. Changing it moves `record.html` in the golden, outside this task's expected repin.
- Task 7, the mutations: retired "the front's order on the method page without the exact depth (q22 pages)" (P7's front order by depth, gone with it); re-pointed, each with its break: "P2's hole not said to show its promotions at some stores", "P2's hole not said to give no start date" and "P6 saying every count says of the N days with records" (q22 pages), and "P7's front test on the method page said over the 90", renamed "the front list's bar on the method page said over the 90 (q22 pages)". New, 10 (q33 method) on `SHOP_PAGES`: the brief's two ("the method page's ₪1.00 not the code's", "the lower middle stated") and eight more: the bands, the 90 days, the 20 of the 30 days and the top 100 each written in by hand; the front list's order without its tie; the pick under another key; the listed price without its definition; the store rules left off the method page. No new target set.
- Task 7, the repin: 92 names moved, exactly the brief's: `site/method.html` and all 91 `day/` lines (2026-01-30 to 2026-04-30). The reason: the method page states S0 to S8, the front page's list and the pick in place of P7, P8 and P9.
- Task 7, the mutation run: `scripts/mutation_check.py "q33 method" "q22 pages"` (the new group, the four re-pointed, and every other mutation guarded by the rewritten test's file): 83 CAUGHT, none timed out, "Files restored. Every mutation was caught."; the staleness check: 2426, none stale.
- Task 7, the full suite: 2,637 passed (the method page's test rewritten in place), 99.86%, `pages.py`, `verdict.py` and `chart.py` at 100%, 792.1 s. The run before the repin: 2,636 passed and only the golden pin failed, 184 lines (92 names), 1,321.9 s.
- Task 6, fix round 1 (the review's findings, 2026-11-11):
  - The store pages broke the design's Always rule, "the source of every condition" (docs/shopper-site.md, "Words"): the rows' conditions are shopper words, and nothing on the page said where they come from or that the fine print was not read. The fold-out gains one line after the filter notes, `shopper.pages.CONDITIONS_NOTE`, "The conditions beside each deal are from the chain's fields; fine print not read: club-only or other conditions may apply." (FROM_FIELDS and FINE_PRINT, the words the product pages use). STORE_RULES' fourth rule now says "its condition from the chain's fields named beside it". So this task's own reading above ("the store page carries it nowhere now") no longer holds.
  - A revision of a site-day file the code before store first published (top-level `counts`, no front block), as the deploy morning's will be, stopped on a bare `KeyError: 'front'`. `_earlier` now keeps such a file's `counts`, as that code kept them; the reading above that such a day cannot be revised no longer holds.
  - New mutations, 11: (q33 front) "the fold-out without where the conditions come from", "the fold-out not saying the conditions are the chain's fields", "the fold-out not saying the fine print was not read", "the rules' condition without its source" (`SHOP_WORDS`), "a row without its condition" (design call 12; nothing guarded it since "a front row's conditions without their source (q22 pages)" was retired), "a weighed row's prices without a kilogram" (`price_text`, through `SHOP_WORDS_FOR_SHOP_PAGES`, back as a target set's constant), "the store pages without the badges' shades" (BADGE_STYLE in STORE_STYLE), "the story without its reason", "the story without last this low" and "the story without how often"; (q33 siteday) "a revision of a day published before the store pages keeping nothing". Each is caught by a failing assertion: the fold-out's three and the rule's by `test_the_fold_out_says_how_a_deal_passes_for_that_store_type` and `test_the_store_pages_words` as amended in this round, the row's, the kilogram's, the shades' and the story's by tests Task 6 already had, and the old file's revision by its new test, `test_a_revision_of_a_day_published_before_the_store_pages_keeps_its_counts`. The target sets stay 88.
  - The repin: 100 names moved, all 91 `day/` lines and the 9 `store/` pages (the fold-out's new line and rule); nothing else.
  - The run: `scripts/mutation_check.py "q33 front" "q33 siteday"`, 22 CAUGHT, "Every mutation was caught."; the staleness check, 2428, none stale; the golden but the pin, 9 passed; the full suite, 2,638 passed, 99.86%, `verdict.py` and `chart.py` at 100%, 1,083.2 s (beside another worktree's runs).
  - Fix round 1 was built in a worktree of its own (branch `q33-front-fix`, from 4aa4a05) and cherry-picked onto q33-store-first after Task 7. The conflicts were the import lists of `src/shopper/pages.py` and `tests/test_shop_pages.py` (both sides' names kept), this section's tail (Task 7's lines, then these) and the golden pin (repinned). `scripts/mutation_check.py` merged without a conflict: 2437 mutations, none stale, 88 target sets, so the `TIME_LIMIT` comment's count stands. After the pick: `"q33 front" "q33 siteday" "q33 method"`, 32 CAUGHT; the golden but the pin, 9 passed; the repin against Task 7's moved 100 names, the 91 `day/` lines and the 9 `store/` pages (`method.html` did not move: its S3 sentence is its own words, not STORE_RULES'); the full suite, 2,638 passed, 99.86%, 1,240.0 s.
- Task 7's review, fix round 1 (2026-11-11), each a sentence of public text made true of what the pages do:
  - S5 said every badge writes its verdict "and the shekels"; a No deal badge ("At X: NO DEAL") shows none. It now says every badge writes its verdict in words, a Deal's with the shekels off ("NO DEAL" has none).
  - The record page's days-read sentence cites S0 in place of P8, which the method page no longer has: a day whose promotions were not read is no day tracked (S0). `test_every_rule_a_page_cites_is_one_the_method_page_names` holds one page of each kind to the rules the method page lists (no P7, P8 or P9).
  - P5 said each condition names its source and every promotion says "fine print not read"; true of a product page's fold-out (`shopper.product._promotion`), not of a store page, whose rows give their conditions in shopper words and whose fold-out says it once (Task 6's fix, CONDITIONS_NOTE). P5 now says both. README's "every promotion is shown with 'fine print not read'" the same.
  - README's line 5 gives "Deal" or "No deal" only when today's promotion can be judged, as line 43 does.
  - S4 lists the no-verdict lines as their own case ("There is no verdict, only a plain line, when one of these applies"), after the No deal reasons, no longer "Otherwise …", which read as a third reason.
  - Mutations, 5 new (q33 method): "the method page's No deal badge said to show shekels", "the no-verdict lines read as a No deal's reason", "P5 saying every page lists each promotion's conditions with their source", "P5 quoting the fine print label as the store pages' note", "the record page citing a rule the method page lacks". None retired or re-pointed.
  - The repin: 93 names moved, exactly the expected: `site/method.html`, `site/record.html` and all 91 `day/` lines. The reason: the method page says only what the pages do (S4, S5, P5), and the record page cites S0.
  - The mutation run: `scripts/mutation_check.py "q33 method" "q22 pages"` (q22 pages again, since the record page's test changed): 88 CAUGHT, none timed out, "Files restored. Every mutation was caught."; the staleness check: 2442, none stale.
  - The full suite: 2,639 passed, 99.86%, `pages.py` at 100%, 924.9 s.

### Fix wave after the whole-branch review

The whole-branch review (2026-11-11) found the problems below; each was checked against the code at 6eb6df1 and fixed in one round, test first.

- The owner's answer (2026-11-11), the subtitle: every store page's subtitle is the fold-out's first line, the design's "Promotions checked against what the product usually costs, sales included, over up to 3 months.", in place of "Promotions checked against up to 3 months of shelf prices.", which described the rule before the usual price included sales. The fold-out keeps its own first line, so the sentence shows twice on a store page.
- The owner's answer (2026-11-11), an unread sale price: when a sale listed across the column runs today with its price not read (`price_unread`), there is no today's price, in place of this plan's reading that S6's today is then the listed price ("S6's today", above, now says so). The chart draws no today mark or "today" label and no "Last this low" line shows; today still counts as on sale for S7, so a past sale is "the last sale before this one". `no_sale` and `some_stores` keep the listed price as today's.
- A store page on a hole or a promotion hole said its store type "lists 0 promotions carried by at least half its stores, on 0 products" beside the line saying the day was not read: the build counts no promotion on such a day (`shopper.build._Pages._today` returns early). `shopper.pages._rules` now leaves the promotions line out on such a day, and the site-day file writes the front block's `promotions` and `products` as null there, beside the column's `hole` and `promo_hole`. Tests: `test_a_store_type_not_read_today_says_so_and_lists_none` (no line on either kind of day; the line on a day read beside another store type's hole) and `test_a_store_type_not_read_today_has_no_promotions_count` (a hole, a promotion hole, a day read); the site-day test of every store page's numbers reads a null count as no line. Mutations: "the promotions line on a hole day", "the promotions line on a promotion-hole day" (q33 front); "the site-day promotions counted on a hole day", "the site-day promotions counted on a promotion-hole day" (q33 siteday).
- The subtitle (the owner's answer above): `shopper.words.FRONT_SUBTITLE` is the fold-out's sentence, still built from READ_DAYS // 30; it is used on the store pages alone (the root page has no subtitle). Pinned in `test_the_front_title_and_subtitle_are_the_owners_plain_words` (equal to FOLD_INTRO and quoted in docs/store-first.md) and `test_each_store_page_names_its_store_and_puts_search_first`. Mutation: "the store pages' subtitle the old rule's" (q33 front). Re-pointed with their breaks: "the subtitle's 90 days said as other than 3 months" and "the subtitle's "up to" dropped" (front words).
- An unread sale price (the owner's answer above): `shopper.verdict.verdict` passes no today's price for `price_unread`, and `_judged` gives no last this low without one. The verdict's docstring (S3 and the calls that know no price today), the chart's docstring, the plan's "S6's today" and the method page's S3 and S6 sentences say so. Tests: `test_an_unread_sale_price_gives_no_price_today` (and `test_no_sale_and_some_stores_take_the_listed_price`, the old test without `price_unread`), the `price_unread` case of `test_no_today_mark_without_todays_price`, `test_each_no_verdict_line`'s today mark and "Last this low" for the four calls it concerns, `test_an_unread_sale_price_counts_today_as_on_sale`, `test_an_unread_sale_price_says_no_last_this_low`, and the method page's S3 and S6 pins. The golden's worked value moved: U10 at Universe on day 120, worked again from the rule, has no today's price and no last this low (it was day 119 at ₪3.00); its 27 tracked days, 0 on sale and no last sale stand (`tests/shopper_golden.py`'s docstring and `test_the_golden_verdicts`). Mutations: "an unread sale price given the listed price as today's" (q33 verdict); "S3 giving an unread sale price the listed price", "S6 giving an unread sale price the listed price" (q33 method).
- "Elsewhere today" showed over an empty row: `arrange` set `heading` whenever there was a pick. It is now true only when `elsewhere` holds a badge; with a pick and an empty row, the row stays where it is (`arrangeProduct` moves it after the open part only under a shown heading), and the script's header comment says so. Harness cases: a pick among the parts with only its own badge, and with none; a pick not among the parts with no badges; `test_elsewhere_today_never_heads_an_empty_row`, and `test_a_product_page_without_the_picks_part_says_not_sold` with the heading hidden over an empty row. Mutation: "Elsewhere today over an empty row" (q33 script). `search.js` is still ASCII (`LC_ALL=C grep -c` prints 0) and its NORMALIZE table's escapes are as they were.
- The site-day file's `days` (a row's days with a day price) was not pinned: `test_a_rows_days_are_the_days_its_reason_rests_on` gives a deal two sale days of unknown price among its 90 tracked days and reads 88, the number its reason names. It failed with `len(found.days)` in place of `len(found.priced)`. Mutation: "a row's days counted over every tracked day" (q33 siteday).
- The badge row's tail (the badges with no verdict, in COLUMNS order) was not pinned: `test_the_badges_without_a_verdict_follow_in_columns_order` has three no-verdict badges (some stores, an unread sale price, no sale) after a deal; it failed with the tail reversed, which the older badge-row test passed. Mutation: "the badges without a verdict out of COLUMNS order" (q33 product).
- docs/operations.md said a revision keeps "the site-day file's count line"; it keeps each store type's deals and checked (`shopper.siteday._earlier`), and a day published before the store pages its earlier counts.
- `shopper.siteday`'s docstring said `front` holds "every number its store type's front page shows"; the story's "Last this low" and "How often on sale" figures are not in it. It now says so, and that `promotions` and `products` are null on a day not read.
- Task 7's review line above said `test_every_rule_a_page_cites_is_one_the_method_page_names` holds "every page of each kind"; the test reads one page of each kind. The line says so.
- The method page's S4 had lost its lead, so the no-verdict lines' place before Deal and No deal was only implied: "There is no verdict, only a plain line, when one of these applies (they come before Deal and No deal), the first that applies: …". S5's "Every badge writes its verdict in words" is now "Every Deal and No deal badge writes its verdict in words", since a no-verdict badge writes a line. Mutations: "the no-verdict lines' place before Deal and No deal left unsaid" and "every badge said to write a verdict" (q33 method); re-pointed with their breaks: "the no-verdict lines read as a No deal's reason" and "the method page's No deal badge said to show shekels" (q33 method).
- Internal docstrings that still cited P7 and P8 now cite the current rules and say only what the code does: `shopper.forecast` (the runs over the days tracked, S0, as S7 makes them), `shopper.measures` (the days tracked and the runs S7 makes; the older measures named by what they were), `shopper.check` (no figure pattern tells a probability from another percent a page could show) and `shopper.words`.
- Re-pointed with their breaks besides those above: "the fold-out left off" and "the fold-out's counts left off" (front words), since `_rules` takes the day and builds the promotions line apart. None retired. The target sets stay 88, so the `TIME_LIMIT` comment's count stands.
- The repin, after the golden but the pin passed (9 passed, 408.2 s): 194 names moved, exactly the expected kinds: all 91 `day/` lines; all 91 `site-days/` files (the front block's null counts: Shufersal Express, which has no store in the golden, is a hole on every day); the 9 `store/` pages (the subtitle, and the promotions line gone from Express's); `site/method.html` (S3 to S6); `site/search.js`; and U10's page, `site/p/2000000000220.html` (no today mark, no "Last this low"). Nothing else moved.
- The mutation run: `scripts/mutation_check.py "q33 front" "q33 siteday" "q33 verdict" "q33 script" "q33 product" "q33 method" "q33 chart" "front words"` (the brief's groups and the group of the four re-pointed there): 169 CAUGHT, none timed out, "Files restored. Every mutation was caught."; the staleness check: 2455, none stale.
- The full suite: 2,648 passed, 99.86%, `verdict.py`, `chart.py`, `pages.py` and `siteday.py` at 100%, 750.2 s.

### Task 10: the final checks, README and the design (2026-11-11)

- The full suite at ea96a4e: 2,648 passed, 99.86%, `verdict.py` and `chart.py` at 100%, 835.8 s.
- The mutation run: `scripts/mutation_check.py "q33" "q22 golden"` (every q33 group, and the "q22 golden" mutations, whose test file, `tests/test_golden_90.py`, this build rewrote and which no task had re-run; the brief counted six, the script holds five): 177 selected, 177 CAUGHT (the seven whose test is the golden among them), none timed out, "Files restored. Every mutation was caught.", 1,790 s; the staleness check: 2455, none stale.
- cfn-lint over `template.yaml` and `site-template.yaml`: clean.
- README.md, beyond the counts (2,648 tests, 99.86%, 2,455 planted bugs, as of 11 November 2026, in the "Tests" row and "Tests that are themselves tested"): the shopper site's step one is live since 10 November 2026 (deployed that evening with the owner's hand upload of that day's pages); its first scheduled morning, 11 November, published the day's pages (25,003 files) with no alerts; its front page lists no deal yet ("None yet: a product needs 20 days of price history first."), since no product has 20 days of records until about 21 November; this branch's store picker, verdict per store type and chart are built and tested, not yet deployed. Changed for it: the opening paragraph, the "Shopper site" row, the "Why" paragraph's "once …", the basket and site bullets, step one's bullet (its pages as step one builds them, and a new bullet for this branch's step), the paragraph under the diagram (the basket's morning as it ran, the site's in the present), the forecast record's deploy state, the claims bullet ("No deal" is the next step's), the cost row and bullet ("once it runs" dropped), the first line of "What's next" (this branch's deploy) and the license paragraph's promotions.
- docs/store-first.md: a final section, "Changed after the build", with the owner's two answers of 2026-11-11 (the store pages' subtitle; no today's price for an unread sale price), pointing here for the rest.

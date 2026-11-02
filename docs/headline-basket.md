# The headline basket: design

**Status:** design, 2026-11-02, written from the research of that day on the owner's "skip the questions, remember the goal". Builder check (a fresh Fable reader) done the same day and folded in: one question, settled as call 1 below. The calls are listed at the end; the owner can overturn any. **Approved by the owner 2026-11-02.** Nothing is built yet; the plan comes next.
**Grade:** portfolio grade: tested, reproducible, honest in its words; not production. The collector keeps every morning's files, so a day this job misses or gets wrong is rebuilt from the archive. Nothing is lost, unlike a missed collection.

## What the project is, and what this piece is

The project is a public site that prices the same everyday basket at Israel's biggest supermarket chains every morning, from the price files the law makes them publish, later with an AI that reads product names and promotion fine print and a published score for how often it is right. It is a portfolio project: it exists to show data engineering done honestly on messy public data, with one number a visitor understands in five seconds and the owner can defend in an interview: how it was made, what it does not claim, and that anyone with the chains' files gets the same one.

The headline basket is that first number. One fixed basket of about 30 everyday products, identified by barcode so the product is identical at every chain, priced at the five chains from that morning's full price files, shown on one page with the method and the barcode list beside it. Everything later (history, promotions, product matching, the AI) reads the same tables and keeps the same words. The owner approved this picture on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print later).

What to expect from the number: on 2026-11-02 Carrefour's median price was the highest of the five on 2,112 of the 2,467 barcodes all five chains listed, Rami Levy's and Osher Ad's the lowest on about 2,030 each, and the typical gap between a barcode's highest and lowest chain median was 1.28 to 1 (measured on that day's full price files; sources at the end). So the first page will most likely rank Rami Levy or Osher Ad lowest and Carrefour highest, with a gap of roughly a quarter. The page shows whatever the day's files say.

## What a visitor sees

One page in English, with each product's Hebrew name beside its English one. Working title: "One basket, five chains".

1. **The headline**, two lines. Figures here are illustrative; the day's files set them.
   - "Lowest listed total today: Rami Levy, ₪312.45."
   - "Highest: Carrefour, ₪398.10, 27% more. 30 everyday items, listed shelf prices before promotions, from the chains' price files of Monday 2 November 2026."
2. **Five bars**, one per chain, lowest first, each with its total and "from 92 stores' files".
3. **The item table**: one row per product (English name, Hebrew name, declared size, barcode), one column per chain with the chain's listed price; the lowest in each row marked. Under or beside each price, in small text, the range across that chain's stores and how many list it: "stores ₪3.90 to ₪4.20, 91 of 96 list it". The range is shown as the files give it, never clipped; an absurd endpoint is the file's content, and the median carries the total.
4. **Notes**: the items left out today and why; which stores each chain's number rests on and what was excluded (Shufersal's Be stores and its online store); and the sentence "A chain's price for an item is the median of its stores' listed prices, so no single store need list exactly this total."
5. **The credit line**, on every page: "Prices from the price files Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof publish under section 30 of the Food and Pharma Competition Promotion Law, 2014: the files of 2 November 2026, collected by 11:00 Israel time. Listed prices, not a promise of what a till charges. Not shopping advice. How this is made →"
6. **The method page**: the rules below in plain words, the basket list with barcodes, the exclusions, what the page does not claim, the law, and how anyone with the chains' files reproduces the number.
7. **The day's numbers as data**: `days/YYYY-MM-DD.json` on the site, one per day, holding everything on the page and the counts behind it (counts only: how many stores list an item, never which). These accrue from day one, so a history view later needs no rebuild. A day that was rebuilt says so inside the file and on its page (B12).

Served the way the flights site is: a private S3 bucket behind CloudFront, `noindex`, reached by link until the owner launches it (flights-archive `docs/publishing.md`). No JavaScript is needed; the bars are inline SVG.

## Goals

- A number anyone can reproduce: the basket's barcodes, the rules and the day's file set are published, and the same code on the same files gives the same record.
- Honest words: every price is a "listed" price from a named chain's published file, before promotions; the ranking is of this basket's listed totals and nothing wider.
- A fresh page every morning without the owner (step two below), from the files the collector stored that day.
- Cheap: well under $1 a month on top of the collector in year one (cost section).

## Non-goals (version one)

- Promotions. "N for ₪M", club-only and card-only deals need rules of their own and are the AI piece's territory; the headline says "before promotions" in its own sentence.
- Prices by store, format or city. The page shows chain-level medians and ranges; the tables keep sub-chain and store, so that cut is a query later.
- A Hebrew page, history charts, a custom domain, search-engine indexing: each a later step. The per-day JSON makes history free.
- A wide index ("every product all five chains stock, one of each"): a later number, once the headline stands.
- Product matching by name or by AI. The basket is identical barcodes by construction, so there is nothing to match.
- Airflow and dbt. This slice is two steps and two schedules; the rules are SQL over Parquet tables, so dbt can take them over unchanged when the second slice has several models (the 2026-10-31 decision: Airflow arrives with the processing pipeline, where it earns its place).
- Chains beyond the five.

## Anti-goals (a failure even if everything else works)

- A number nobody can reproduce, or one that changes quietly when the code changes. The basket is versioned, every rule is tested, and the day's record names the code and the basket version it used.
- "Cheapest chain", "you'll pay", "at the till", or a store named as dear: wording the chains or the Authority could call misleading. The Consumer Protection Authority's spokesman said manipulative use of the data exposes the user to misleading-claims suits (Globes via N12, 2025-12-16, a secondary source).
- Raw files or per-store price lists published. Derived numbers only, credited to the chains' files.
- A page that looks current but is stale. The date sits in the headline sentence, and a morning with no new page emails the owner.
- Anything that touches the portals. This piece reads the archive only.

## The basket

- **Identity.** A product is a barcode. Codes match with leading zeros stripped; a basket code must pass the GS1 check digit at 8, 12, 13 or 14 digits (an 11-digit code is read as a 12-digit one with a leading zero). Internal codes fail it and are never candidates: weighed produce has no shared code (on 2026-11-02 "tomato" carried five different codes across the chains), and the files' `ItemType` field says nothing useful (Rami Levy sets 1 on everything; Carrefour sets 1 on 36,301 rows that fail the check digit).
- **Candidates**, measured on a selection day (2026-11-02, or a later clean day the builder names): listed in all five chains (2,467 codes on 2026-11-02); in at least 80% of each chain's included stores that day (629 codes at 80% with Shufersal's Be stores out; the online store was not yet excluded in that count); quantity and unit readable and agreeing wherever a chain states them, stated by at least three chains (of 1,499 shared codes with a readable unit in all five chains, 927 agree; 44.6% of Osher Ad's rows say "לא ידוע", unknown).
- **Size and shape.** About 30 items (25 to 40), one of each: a screen's worth, with names written by hand, and enough that one odd price does not reorder the chains. Everyday categories: dairy, pantry staples (rice, pasta, oil, sugar, flour, coffee, tea), spreads, snacks, soft drinks, cleaning, hygiene. At most two items from one brand line, so the basket is not twelve soft drinks. No alcohol, tobacco or infant formula (a call: a controversy the number does not need).
- **Names.** Three chains cut product names at 20 characters (Carrefour, Osher Ad, Rami Levy), Shufersal's run to 40, and 2,465 of the 2,467 shared codes are named differently across chains (measured 2026-11-02). So the page never shows a chain's name string: each item carries an English name, a Hebrew name and a declared size written by hand and checked against the chains' strings.
- **Who picks.** The builder proposes the list from the candidate table (each code with its five name strings, its sizes and its coverage per chain); the owner approves it. The list lives in the repo as `basket/v1.json`: barcode, both names, declared size, category, and the selection day's coverage per chain. A change is a new version with a date; the page names the version it shows, and every day's record names the version it used.

## The number: rules

Each rule has a name, tests of its own and a mutation in `scripts/mutation_check.py`.

- **B1 Files.** For each chain and day, the `PriceFull` files under `raw/chain=<slug>/date=<day>/` at the moment the extraction runs, their keys listed in the day's record so a rebuild's inputs are visible; when a store published more than once (Rami Levy republishes hourly; store 732 nine times on 2026-11-02), the latest by the time in the file name. The store is the number in the file name, never the one inside (74 Carrefour files on 2026-11-02 disagreed with their names; `docs/portals.md`).
- **B2 Included stores.** Every store of Rami Levy, Osher Ad, Carrefour and Yochananof except the online ones their store lists name (the build's survey of the lists of 2026-11-02): Rami Levy's store 039 "מרלוג אינטרנט", its internet logistics centre (whose files also have a layout of their own, `docs/portals.md`; the design first listed it as included, before its name was read), and Carrefour's store 471 "קרפור אונליין"; Osher Ad's and Yochananof's lists name none. Shufersal without sub-chain 005 "Be" (97 stores) and without store 413 "שופרסל ONLINE" (its store list of 2026-11-02: 11 sub-chains, 418 stores, of which 416 published a full price file that day; 320 remain). Stores of list type 2 whose names say nothing of online (Carrefour 472 and 473; Yochananof 150 "הדרים פיקאפ", a pickup point) stay in; what type 2 means is UNVERIFIED and is the owner's to settle. Be's stores list a median 4,395 items and carry 12% of the barcodes all five chains share (measured 2026-11-02), which is not a grocery assortment; what Be is as a format is UNVERIFIED and does not matter to the rule. The sub-chain comes from the file name. Any other chain's online or non-grocery store the builder finds in the store lists is excluded by name and named on the method page.
- **B3 Rows.** One row per store and barcode after B1 and B2. The same barcode twice in one file: the last row wins, and a pair with different prices is counted in the day's record (Carrefour store 001-221 listed 22 codes twice at the same price on 2026-11-02).
- **B4 Placeholders.** A row whose price is ₪0.01 or less is dropped before anything else and counted (338 such rows at Carrefour and 279 at Rami Levy on 2026-11-02, some of them real foods).
- **B5 Chain price.** A chain's listed price for an item that day is the median of the item's price across the chain's included stores whose latest file lists it, after B4; with an even count, the mean of the two middle values. Rounded to agorot for display only.
- **B6 Coverage guard.** An item counts that day only if, at every chain in the ranking, at least half of the chain's included stores that published a file that day list it. Otherwise the item is left out of every chain's total that day and named in "left out today" with the chain and the share. (80% to enter the basket, 50% to stay on a day, so a thin morning shows as one dropped item, not a flicker in the ranking.)
- **B7 Size guard.** For each chain, the item's most common readable (quantity, unit) pair across its stores, with "לא ידוע" and empty values as "not stated", kg converted to g and litres to ml, and g and ml treated alike (84 shared codes differ only in that, measured 2026-11-02). The unit vocabulary comes from the selection day's data; a unit string outside it is "not stated" and counted. A stated size of exactly one unit is "not stated" too: a count of one carries no size, and 791,019 rows of 2026-11-02 say "1 unit" for products other chains state in grams or millilitres (79 of the 1,449 shared codes with a readable size at all five chains would otherwise fall to a units-against-grams disagreement, 60 of them with every "units" chain at one); a count above one is a size. Metres (rolls of paper and foil, 22,272 rows) are "not stated" in version one. If any chain's stated size differs from the basket's declared size, the item is left out that day for every chain and named with the sizes seen.
- **B8 A chain's day.** A chain whose files that day come from fewer than half of its included stores in that day's store list (or the latest stored one), down to none at all (an extraction that finds no files writes an empty table, and the page says "0 of M"), is shown as "too few files today: N of M stores" and left out of the ranking and the totals; its item prices are still shown, marked. With fewer than three chains in the ranking, the page carries no headline comparison, says so, and still shows the table.
- **B9 Totals and the gap.** A chain's total is the sum of B5 over the items that passed B6 and B7; chains rank from lowest to highest; the gap is (highest − lowest) ÷ lowest as a whole percent. Equal totals share a rank and sort alphabetically.
- **B10 The record.** One JSON per run with every number on the page and the counts behind it: items in and out and why, each chain's included stores, stores with a file, stores listing each item (the private record lists them; the public day file carries counts only), the file keys and the manifests they came from (run ids), the basket version, the code's fingerprint, the run id and the build time. Everything but the run id and the build time is deterministic: inputs are sorted and nothing reads the clock. "The day's record" is the latest run's; the determinism test compares two runs with those two fields removed.
- **B11 As of.** The page's date is the Israel date of the files' names; "collected by" is the time the day's extraction started (11:00 Israel time in step two; the actual time in step one). The record keeps each chain's manifests, so the exact listing times are a lookup away.
- **B12 Rebuilds and revisions.** A day may be rebuilt (a parser fix, a rule fix), never quietly. The publish step, finding `days/<day>.json` already on the site, compares the new numbers with the published ones: equal (the usual case, step one's hand upload followed by step two's run of the same day) is a no-op; different needs a reason, so a scheduled run fails loudly and the owner looks, and only a manual run given a one-line reason republishes. A republished day keeps its earlier figures: the day file holds a `revisions` list (each run's id, code fingerprint, build time and headline numbers), and the day's page says "Revised on <date>: <reason>. First published: <the earlier totals>." The private records under `basket/date=<day>/` stay write-once, one per run, so every build of every day exists. The word lists gain "Revised on" as an "always" string on a revised page and a "never" string on an unrevised one.

## The pipeline

Three steps, each a pure function of (day, chain) or (day), run the same way on the Mac and in Lambda:

1. **Extract.** One chain's `PriceFull` files for one day become one Parquet table, `tables/prices/chain=<slug>/date=<day>/prices.parquet`: store (from the file name), sub-chain, barcode as published and normalized, name, price, quantity, unit, unit of measure, price-update time, and the file's key. Every row, not only the basket's: the scan costs the same, and the second slice (history, the wide index, promotions) reads the same table. Two layouts: the common `<Root><Items><Item>` (`ChainID`, `ItemName`, `PriceUpdateTime`) and Rami Levy store 039's ZIP (`ChainId`, `ItemNm`, `PriceUpdateDate`), both in `docs/portals.md`. About 5.4 million rows a day (each chain's store count times its median items per store, measured 2026-11-02).
2. **Basket.** The day's five tables and `basket/vN.json` become the day's record, `basket/date=<day>/basket-<run id>.json` (B10), written write-once like a manifest (`If-None-Match: *` and the ten-year lock). Rules B3 to B9 are SQL run by DuckDB from Python; B1 and B2 sit in the extraction.
3. **Page.** The day's record becomes `index.html`, `method.html` and `days/<day>.json`, uploaded to the site bucket, and a healthchecks.io check with a period of one day is pinged, so a morning with no page emails the owner.

Tables are derived and overwritable: a parser fix rebuilds a day from the raw files, which are the truth. The private day records are write-once, one per run. The site bucket is rewritten by uploads, as the flights site is, and a published day changes only by the revision rule (B12).

**Step one: by hand.** The three steps as one command on the Mac over a day synced read-only from the archive into a gitignored `data/` directory (about 370 MB a day; the flights pattern, `scripts/sync.sh`). The candidate table and the proposed basket come out of the same code. The owner reviews the first page; the first upload is by hand on his go (`scripts/publish.sh`, the flights pattern), after the legal read below. Step one also measures what step two needs: the extraction's time and memory per chain, and the table's size.

**Step two: every morning.** The same code as a second Lambda function in the collector's stack: five extraction schedules at 11:00 Israel time, one per chain (after the 10:45 check; they read S3 only and touch no portal, so they may overlap), and one basket-and-page run at 11:30. Memory from step one's measurement (the collector runs at 512 MB; CPU scales with memory, per AWS's pricing page). Its role reads `raw/`, `manifests/` and `checks/`, writes `tables/` and `basket/` and the site bucket, and deletes nothing. If a chain's table for the day is missing at 11:30 (a run that did not happen, as against one that found no files and wrote an empty table), the run fails loudly and the dead-man check reports the missing page; it never publishes a four-chain page as a five-chain one. The schedules deploy off, one manual run per step is checked (on a day step one already published by hand, the publish step's equal-numbers no-op of B12 is the expected outcome), then they go on, on the owner's go, which is the go for the daily writes. The five extraction schedules share a start minute on purpose; the template tests that pin the collector's timetable (`tests/test_template.py`: no two schedules on one minute, one chain never twice at once) are scoped to the collector's events. The times move if step one's measurement says a chain needs a split. The site itself is a stack of its own (`site-template.yaml`, the flights pattern).

## Words

Always: "listed price", "in the chain's price file", "before promotions", "lowest listed total for this basket", "the chain's median across its stores", the day's date in the headline sentence, the credit line on every page.

Never: "cheapest chain", "cheaper than" as a flat fact, "you'll pay", "saves you", "at the till", "real prices", "the chain charges", a store named as dear or cheap, any claim about promotions, and any claim about what the number means beyond this basket on this day. The method page says in one sentence that a different basket gives a different order.

The page tests pin both lists: every "always" string present, no "never" string anywhere; "Revised on" moves between the lists by B12.

## Before anything is published

1. The owner reads section 30(ה) in an official copy (Nevo, or the Knesset's law database) in his own browser and records the wording and the date in `docs/terms.md`. Today's basis is a Hebrew Wikisource copy of 2026-07-21, read 2026-10-31: anyone may access the publication, the information and the data in it and use them freely and without payment, for private or commercial purposes. Changes since July 2026 are UNVERIFIED.
2. The first page is reviewed on the Mac; the first upload is by hand on the owner's go.
3. The repo stays private and the site is `noindex`, reached by link, until the owner launches; the agent notes leave the repo first (QUEUE q11). The credit line does not need the repo's address.

## Testing (the project's standard)

- A test and a named mutation for every rule B1 to B11; coverage floor 95% on the new package, as on `collector`.
- Extraction tests on the trimmed fixtures in `tests/fixtures/` (Shufersal, NCR store 722, NCR store 039's ZIP, Carrefour) plus new synthetic ones for the traps: a duplicate barcode in one file, a ₪0.01 row, an 11-digit code, "לא ידוע", a store published twice in a day, a Carrefour file whose inside store differs from its name, a bare `<Root>`. Fixtures stay synthetic, at most three items a file, as the collector's.
- A golden day: a synthetic five-chain day of a few stores and items whose record is known by hand, compared byte for byte apart from the build time.
- Determinism: the real 2026-11-02 day run twice on the Mac gives identical records.
- A hand check on the first real day: three items' prices read by eye in three chains' raw files (read-only, never copied into the repo).
- Page tests: the "always" and "never" word lists, the date in the headline, the credit line, `noindex`, and a valid page with no JavaScript.
- Test data never reads the clock. A fresh Fable reviewer reads the code before it ships. Step two deploys with its schedules off, one manual run per step, then on, on the owner's go.

## Cost (monthly, estimates)

- **Lambda.** The free tier is one million requests and 400,000 GB-seconds a month; beyond it, $0.0000166667 per GB-second and $0.20 per million requests in US East (N. Virginia) (https://aws.amazon.com/lambda/pricing/, read 2026-11-02; the il-central-1 rate was not read, UNVERIFIED). The collector's 17 runs a day at 512 MB could use up to about 230,000 GB-seconds a month if every run took its full 15 minutes (they do not; not measured). Extraction at an estimated 5 minutes a chain at 2 GB is 3,000 GB-seconds a day, 90,000 a month; the worst case, 15 minutes a chain, is 270,000. Likely inside the free tier together; the worst case is about 100,000 GB-seconds over, about $1.70 a month at the US East rate.
- **S3 storage.** The tables at an estimated 50 to 100 MB a day (5.4 million rows in Parquet; UNVERIFIED until step one measures) are 1.5 to 3 GB a month: $0.04 to $0.08 the first month, under $1 a month after a year, at $0.025 per GB-month (il-central-1, AWS price list, flights-archive `docs/publishing.md`). Day records and pages are kilobytes.
- **S3 requests.** About 820 reads and 10 writes a day. The read rate was not read; even at the write rate of $0.0055 per 1,000 (same source) 25,000 a month is $0.14.
- **Site.** A handful of files a day into S3 behind CloudFront: under $0.05 a month (flights-archive `docs/publishing.md`: inside CloudFront's free tier; a daily upload of 961 files there came to $0.16, this one uploads under ten).
- **healthchecks.io.** One more check on the account already in use; whether the free plan's check count allows it is UNVERIFIED (the owner sees it in the dashboard).
- **Total:** about $0.10 to $0.30 a month in year one; worst case about $2.50. The account's $5 monthly budget alarm is the guard.

## Calls made in this draft (the owner can overturn any; most likely his to overturn first)

1. **A published day can be corrected, never quietly** (B12; the builder check's one question). A rebuild that changes a day's numbers republishes it with a dated reason and the earlier figures kept on the page and in the day file; a scheduled run never revises, only a manual one with a reason. The smaller alternative, "the first published number stands for good", was rejected: it keeps a known-wrong number public, which is its own quiet dishonesty. This is the site's honesty policy, so it is the call most worth the owner's eye.
2. One page in English with Hebrew product names; a Hebrew page is a later step. The portfolio reader comes first.
3. The chain's price is the median across its grocery stores; the page shows chain rows and ranges, and names no store. Shufersal's Be stores and online store are excluded.
4. About 30 hand-named items, proposed by the builder from the candidate table and approved by the owner, rather than the 629-item "everything stocked everywhere" set, which no one can read and no one can name.
5. Promotions out, said in the headline sentence.
6. Every row extracted to Parquet, not only the basket's; DuckDB runs the rules as SQL; no Airflow or dbt in this slice.
7. Step one by hand on the Mac, step two a scheduled Lambda in the collector's stack with a site stack of its own.
8. The thresholds: 80% of stores to enter the basket, 50% to count on a day, half a chain's stores for the chain's day, three chains for a headline; rows at ₪0.01 or less dropped; kg and litres converted, g and ml treated alike.
9. Tables overwritable; private day records write-once, one per run; the public day file carries counts, never store numbers.
10. A dead-man check for the page; no new CloudWatch alarm.
11. The working title "One basket, five chains".

## Left to the builder

- The candidate table and the proposed basket, with the five name strings beside each code for the owner's approval.
- The extraction's memory and, if a chain does not fit one 15-minute run, its split; measured in step one.
- The library for Parquet and SQL (DuckDB is the call; polars for ingest if DuckDB's is slow), pinned and older than a month, small enough for a Lambda package.
- The page's layout and style; the content and the words are fixed here.
- Code layout (a package beside `collector`), the fixtures, the sync and publish scripts, the site template.
- Which other chains' store lists hold an online or non-grocery store, excluded by name and listed on the method page.
- Store 039's price format: its fixture shows whole-number prices (`<ItemPrice>450</ItemPrice>`, equal to its unit price), synthetic values; the real archived file is read in step one before the extraction's number parsing is settled.

## Sources

- The measurement of 2026-11-02: every `PriceFull` file of that day in the archive (814 files, 370.5 MB; 730 analysed, the latest per sub-chain and store), read-only, recorded that day. All counts above marked "measured 2026-11-02" come from it.
- Shufersal's store list of 2026-11-02 (`Stores7290027600007-000-20261102-020`), read from the archive 2026-11-02: 11 sub-chains, 416 stores, sub-chain 5 "Be" 97 stores, store 413 "שופרסל ONLINE" of `StoreType` 2.
- `docs/portals.md` (file layouts, store 039, Carrefour's store numbers), `docs/collector.md`, `docs/operations.md` (the morning's timetable).
- The law: section 30 of the Food and Pharma Competition Promotion Law, 2014, in the Hebrew Wikisource copy of 2026-07-21, read 2026-10-31; the official text is unread.
- AWS Lambda pricing, read 2026-11-02; S3 and CloudFront figures from flights-archive `docs/publishing.md`.

# Product names: the site's first language model, release 1 (design)

**Grade:** production (the owner's, 2026-11-18): it changes the live public site.

**Status:** second version, 2026-11-23, for the owner's approval. Nothing is built. It folds in an outside review of the first draft, a check of each finding against its source, a trial run of 50 products and the owner's read of the trial's names; the last section gives each finding's fate. Each decision is marked as the owner's (with its date), the agent's call from the design talks, or a call of this draft ("draft's call"; listed near the end; the owner can overturn any). Built, deployed and paid for only on the owner's go. Line numbers are main's at 48e1f41. Tags like (q41) are items in the project's work queue.

## Why

The site answers "is it actually a deal?" for one product at one store. The shopper must find the product first, and search is the weak step.

- A product's search entry sits in one index piece, chosen by the first characters of its longest name (`src/shopper/search.py:12-22`). On the registry of 18 November 2026 (25,071 covered products), the 25,639 names that differ from their product's longest name, typed as searches, reach today's first 10 results 54.5% of the time.
- The chains publish Hebrew names, often abbreviated. A search in English, or in a product's everyday word, has nothing to match.

The second reason is the owner's job search: the roles carry AI in the title, and no site the owner runs calls a model. This piece is small, measured against a baseline with no model, and published with its misses and cost. Release 2's shopping-list agent needs the same names first, to match products across chains.

## Goals

1. A shopper finds a product by any word of any of its names, by its everyday Hebrew name, or in English.
2. The model's share of that is measured: against today's search, a $0 word index and a second model, on searches the tuned system never saw.
3. The scorecard is public: numbers, misses, cost.
4. The morning build stays static, with no model key and no model call. The catalogue changes slowly, so a model call per search would buy only delay, cost and an open endpoint.
5. A shopper can always tell the chain's words from the model's.

## Non-goals

- Release 2: the shopping-list agent and its live endpoint (owner, 2026-11-18).
- Kind (category): dropped (owner, 2026-11-23).
- Showing the model's brand or size, but for a count inside the English name (section 1); using its size in any price, verdict or basket rule; splitting grams from millilitres (q41).
- Promotions' fine print (q19), a schedule, hand-written test searches, spelling correction, a search server.

## Anti-goals

A failure even if everything else works: a model's name shown as the chain's, or before the owner's read passes; a score from searches the scored model wrote, or seen while tuning; a morning build that fails, waits or changes a number because of the model; model text unescaped on a page; one blended score that hides what the word index gives for free; spending with no ceiling.

## What is decided

| # | Decision | Whose |
|---|---|---|
| 1 | An offline batch writes, per covered product: an English name, everyday Hebrew names, brand, size. | Owner, 2026-11-18; kind dropped 2026-11-23 |
| 2 | Readings go to a versioned S3 file the 12:33 site build reads. The build holds no model key and calls no model. A product with no reading is searched by its published names. | Owner, 2026-11-18 |
| 3 | The price files' manufacturer field is an input and a brand cross-check. Kept after the trial. | Owner, 2026-11-18; kept: agent, 2026-11-23 |
| 4 | Search files a product under the words of its names, within `PIECE_MAX` (150,000 bytes). No word searchable today is dropped. The chains' size is also filed in Latin letters ("1.5l", "80g"). | Owner, 2026-11-18; the last two: agent, 2026-11-23 |
| 5 | Scoring: a frozen held-out part; today's search and a $0 word index as baselines; two models; misses and cost printed; size as agreement, not truth. | Owner, 2026-11-18 |
| 6 | The owner's personal Anthropic API account, under a monthly cap on the project's own workspace. | Owner, 2026-11-23; the workspace: agent |
| 7 | No hand-written test searches. Source 2: 300 products, written once in Cursor by Grok 4.7, picked by name. | Owner, 2026-11-23 |
| 8 | The score: the product searched for is in the first 10 results. | Owner, 2026-11-23 |
| 9 | The trial ran first. English names reach pages only after the owner's read of 50 passes: at most 1 wrong. | Owner, 2026-11-23 |
| 10 | The English name may say what kind of product it is from general knowledge ("Old Spice deodorant"), marked as written by AI. | Owner, 2026-11-23 |
| 11 | `claude-haiku-5-5` and `claude-opus-5-5` [S2], compared on a 3,000-product sample in two tables. The owner picks which ships after the scoring, with the trial's quality and cost beside it. | Owner, 2026-11-23; the pair: draft |
| 12 | The English name is marked as written by AI wherever shown. Brand and size are scored, not shown. The scorecard is on the method page and in the README. The batch runs by hand. | Agent |
| 13 | Natural English word order ("Bundle of rosemary"). A count of items kept in the English name where the page shows a weight. Lengths kept. A common Hebrew word is never a brand. Pages for the owner's reads show the manufacturer strings. | Agent, 2026-11-23 |

## What the trial measured

A trial run of 50 products on 2026-11-23, drawn by seed from the registry of 18 November 2026: four batches of 50, one product a request, effort low, the shared instructions (1,686 tokens) cached for an hour. A product's names took about 61 tokens. All 200 requests succeeded, for $0.07.

| | Haiku 5.5 | Haiku 5.5, thinking off | Opus 5.5 |
|---|---|---|---|
| Output tokens a product (of them thinking) | 312 (231) | 76 (0) | 82 (0) |
| Input read from the cache | 94.1% | 96.0% | 94.1% |
| Answers failing a check, of 50 | 3 | 2 | 1 |
| The owner's read of 50: wrong, missing, a guess, style | 2, 6, 2, 11 | not read | 0, 3, 2, 9 |

- **The manufacturer field earns its place.** A fourth batch without it left 35 of 50 products with no brand. With it 25 had none, and ten brands came from it alone.
- **Size:** 15 or 16 agree with the registry's, 2 or 3 differ. Both models read the tortillas as 6 units where the registry has 390 g: both true.
- **The owner's read.** By decision 9's bar Haiku fails (a cut-off "שוואר", shawarma, read as sour cream; a grape syrup named a juice) and Opus passes. Missing: the tortillas' 6, the pitas' 10, a knife's 14.4 cm.
- **Brands are the weak field.** The read and a second pass found three kinds of miss. A common Hebrew word as a brand: Haiku read "צאן" (sheep) as "Tzan" and "נשנושי" (nibbles) as "Nashnushi". A better-known brand for the one written: Haiku wrote "Kinder" where the manufacturer field reads "קינד". A stated brand left out: Haiku four times, Opus once.

## 1. What the model writes

One reading per product. The code enforces the bounds, not the schema.

| Field | What it is | Bounds |
|---|---|---|
| `en` | The English name in natural word order: the brand in Latin letters when the input states one, what the product is (from general knowledge when the names do not say), the variant. Never a weight or a volume: the page shows the chains' own (`src/shopper/product.py:303`). Lengths stay: the size reader reads no metres (`src/basket/units.py:40-41`). | 3 to 60 characters: unaccented Latin letters, digits, spaces, `% . , ' & / - + ( )` |
| `he` | Up to three everyday Hebrew names, each unlike every published name after normalising. | each 2 to 30: Hebrew or Latin letters, digits, spaces, `% . ' " +` |
| `brand` | The pack's brand as the input writes it, or empty. Never a guess, a common Hebrew word, a better-known brand in its place, an importer or a parent company. | up to 30, of `he`'s set |
| `size` | The amount and unit the names state (g, kg, ml, l, units), or none. | a decimal string above zero, within `basket.units.bounded` (`src/basket/units.py:83-88`) |

**Given to the model:** a product's distinct published names and its manufacturer strings, placeholders such as "לא ידוע" dropped. Not the barcode, prices, or the size the code already reads: decision 5's size agreement would then mean nothing.

**The count (agent's call; the mechanism is the draft's).** When the model's size is a count and the registry's is a weight or a volume, the code adds the count to the shown name ("Whole wheat tortillas, 6 pack"). The name can then never contradict the page's size line.

**Brand, measured (draft's call).** The first draft's check, that the brand is found in the input, stays. It shows only that the model invented no brand: it passes a common word and cannot see a swapped or a dropped brand. Nothing automatic catches those, so release 1 counts them by hand: in each owner's read of 50 (section 6) every brand is marked right, a common word, another brand, or left out, and the counts go on the scorecard. Beside them, for free: how often the two models name different brands. In the trial that was 15 of 50 products, seven of the eight misses among them.

**Size** is compared with the registry's (`Covered.size`, `src/shopper/history.py:145-153`), a count against a weight kept apart from a real difference. On 18 November 2026 the registry had 18,789 products in grams or millilitres (one kind there), 962 in units, 5,320 with none.

## 2. The batch

One command on the Mac, by hand. It picks the products to read, sends Message Batches [S3], checks every answer (section 3), and writes a complete names file, the raw answers and a record that reproduces and prices the run (the `model` each answer names, the prompt, tokens, dollars, the workspace billed). Uploading is a separate step, on the owner's go.

**Which products (draft's call).** Those with no reading, and those whose input grew. The input is a product's normalised names and manufacturer strings, and it only grows, so a day with a chain's files missing changes nothing. A changed prompt or model re-reads everything only when the command is told to.

**A request,** as in the trial: one product, the barcode as its `custom_id` and never in the input, so a hostile name can touch one reading only. The shared instructions cached for an hour, the names as JSON in the user turn, effort low, a JSON schema [S7], `max_tokens` 4,096. No sampling parameter (a 400) and no `thinking` field (both models then think adaptively; Opus 5.5 refuses "disabled") [S6]. The answer is the block of type text, after any thinking block [S8]. A refused or cut-off answer gives no reading.

**The ceiling (draft's call).** Token counting is free but counts input only [S9], and an Opus run with no cache hit costs six times the measured one. So a run goes in slices. The command never sends one whose worst case (no cache hit, every answer at the trial's 95th-percentile length) could pass `--max-usd`, and it stops if under half the input came from the cache.

**Where the code lives (draft's call).** Outside `src/`, the function's zip: its fingerprint goes into each day's frozen forecasts (`src/basket/record.py:168-171`), and a prompt tweak must not change it. The new folder joins the test path (`pyproject.toml:8`), CI's coverage list (`.github/workflows/ci.yml:23`) and the mutation check. The SDK and every package it pulls are pinned, each at least a month old.

**The manufacturer strings** come from the batch's own reader over a day's synced price files, built on `pricefile.bodies` and `parse_events` (`src/basket/pricefile.py:51`, `:75`). The price reader does not change; the first draft changed it.

## 3. Untrusted text, both ways

**Into the model.** A chain's name is data: a JSON value in the user turn, never part of the instructions. The guarantee is in code. A schema cannot carry a bound (a minimum, a maximum or an item count returns a 400 [S7]), so every answer passes the project's own check: section 1's bounds, no `<` or `>`, no control character, no web address, and the word rules below. A reading that fails is dropped whole and counted by rule; its product keeps published-name search.

**Onto the page.**

- The English name is escaped, in a span of its own, never the chains' (`CHAIN_SPAN`, `src/shopper/search.py:53`).
- The site check reads that span for markup, the banned phrases (`src/shopper/words.py:141-143`) and "we", "our" and "us". Then it cuts the span out, as it cuts a chain's (`src/shopper/check.py:14-18`), so no phrase a page must carry can come from the model. The first draft left the span in.
- The page's rules find a banned phrase even inside a word (`src/basket/check.py:64-66`), which would refuse "Breaded scampi" for "scam". In the model's span it must match whole words (draft's call). "US" still trips the pronoun rule; such a name is dropped and counted.
- One function applies these rules when the file is made, when the build reads it and in the site check, so a name the check would refuse never reaches a page and cannot stop a morning.

## 4. Where the file lives, and how the site reads it

**In the archive bucket (draft's call),** under a new prefix, one folder per run: the names file, the record, the gzipped raw answers and the scorecard, each put once under the ten-year lock (`src/collector/store.py:115-119`). Tuning runs stay on the Mac. A bad version is never removed. A newer one supersedes it: an older one's copy, or an empty one, which turns the names off and leaves word-filed search alone. **One wrong name:** a new version without the named barcodes, held back until the owner releases them.

**Who writes.** The Mac, as the owner's AWS user and no other (as `scripts/sync.sh:25-37`). The build's function gains read access to the prefix only (`ReadArchive`, `template.yaml:620-629`).

**How the build reads.**

- The newest version uploaded before the day it builds, by the date in the key, as it takes the registry (`src/basket/archive.py:227-239`). So a version counts from the morning after its upload. A same-day rerun and a rebuilt past day read what was read then, and a held-back name leaves the next morning (draft's call).
- The site-day file names the version read (`src/shopper/siteday.py:92-95`) and leaves the field out when none was, so a day built before the first names file still compares equal when rebuilt.
- A faulty file: the build goes on with published names and one more line in the run's alerts. A faulty line is skipped and counted.
- `scripts/sync.sh` fetches the names file and its record, not the raw answers.

## 5. Search, filed by word

Today a search loads one piece and matches a name that holds the whole search (`src/shopper/static/search.js:91-112`). Release 1 files a copy of the entry under each word of each of its names (decision 4). The $0 baseline is the same build with no names file. The rest are the draft's calls unless marked.

- **A match.** Every search word starts a word of one of the product's names, and the words may sit in different names: "tnuva cottage 250" finds "Tnuva" in the English name and "250" in a chain's. A one-character word is matched too, and never picks the piece.
- **Size words (agent's call).** The registry's size is filed as extra words in Latin letters, never shown: "80g", "1.5l". Grams and millilitres are both filed: the registry does not tell them apart.
- **Order,** a starting point: a name equal to the search; then whole words of one name; then word starts in one name; then words spread over several names. So "חלב" lists milk before "חלבה". At each step a published name's match comes first. Ties end on the barcode.
- **No word is dropped (agent's call).** A piece is keyed by a word's first two characters and, over `PIECE_MAX`, split by one more, as far as the whole word; a word that ends where a split goes on has its own key. The first draft left out a whole word that still did not fit. Projected on the registry of 18 November 2026 with the trial's Opus readings (137 bytes more an entry), nine such words pass the limit, "שוקולד" (697 products) among them, against two with published names alone. So such a key keeps its entries in the order a search for it alone shows them, cut into numbered parts, and the word typed alone loads the first. A split key keeps a first part too, so letters typed part-way through a word still show results.
- **Which piece.** The list of pieces gives every key and its count, so the script knows with no fetch whether typed letters have a piece, are split or match nothing. A search loads its rarest word's piece: "שוקולד מריר" loads "מריר". Word-filed search ships first and alone, with published names only (draft's call): most of the hole closed for $0, and row B live before any model runs.

A Python sketch of the first draft's rules, published names only, came to 17.4 MB of pieces against today's 3.3 MB. With the model's names an entry is about twice as long and filed about twice as often (the trial: 269 bytes against 132, 9.7 keys against 4.7): about 70 MB a morning, projected from 50 readings.

Before any code, the plan's sketch must show on the whole registry, at that entry size: every word of every published name, typed alone, finds products; no piece passes the limit; and the most pieces one search fetches.

## 6. What a shopper sees

- **The bar (owner, 2026-11-23).** English names reach pages only after the owner's read of 50 passes: at most 1 wrong. Its details are the draft's calls. The read is of the frozen prompt and the model that ships: 50 readings drawn by seed, none the trial's, each shown as its product page will show it, with the manufacturer strings. Each name is marked wrong, missing, a guess or style, and each brand as section 1 says. Wrong means the name says something the product is not; a swapped brand counts. A failed read leaves the names search-only, shown nowhere, until a fixed prompt passes a fresh 50. The trial's read is evidence, not this pass: the prompt has changed since.
- **A coarse gate.** Zero wrong in 50 fits a true rate of up to 6%, one wrong up to 9% (95% bounds): possibly over a thousand wrong names on 25,071 pages. So a wrong name is cheap to take off (section 4), and the scorecard gives the read's counts, not "passed".
- **Product page.** Under the names as listed (`src/shopper/product.py:284-291`): the English name in its own span, labelled "English name written by AI", outside every store type's part, never the tab's title.
- **Search results.** A matched English name shows under the chain's, with "in English, by AI".
- **Everyday Hebrew names** are searched and never shown (draft's call). While tuning, the report lists every result found only through one, so a wrong one can be held back.
- **Method page.** The scorecard (section 8) and the count of products with a reading, built each morning from the scorecard file beside the names file (`render_method`, `src/shopper/pages.py:780-793`). Its words must clear the site's banned phrases, "expected to" and "likely to" among them. No alert fires for products without one: it would fire every morning between hand runs (draft's call).

The exact words are the plan's. The owner reads the built pages before merge.

## 7. The test searches

Both sources are drawn by seed from one recorded registry day. The trial's 50 products are left out: their answers were read, and that changed the prompt (draft's call).

**Source 1, other chains' wording.** 500 products with two or more names. Each name that is not the product's longest is one search, as published: about 1,000. A sketch of the $0 index already finds 99.6% of such names, so this source can only show harm: a model's names pushing the right product out of the first 10.

**Source 2, shopper-style.** 300 other products (owner, 2026-11-23), 100 from each of three bands by how many of the nine store types list the product (1; 2 to 4; 5 to 9). Three searches each: short everyday Hebrew, Hebrew with the brand or the variant, English. Written as people type, never copying a listed name.

**The owner's session in Cursor.** The owner picks Grok 4.7 by name and runs the plan's prompt over the sample, in six files of 50. Grok 4.7 is not Claude, and Cursor's Plus plan and up include it; Plus has no other vendor's models and no Auto mode [S10]. The model as shown, Cursor's version and the date are recorded. Once a loader accepts the answers they are never written again. Optional: the owner's yes or no, "would someone type this?", on 30 tuning searches.

**The split** is by product, never by search, inside each source and band. Source 1: 250 tuning, 250 held-out. Source 2: 100 and 200 (draft's call). At 200 products a share is good to about 7 points either way, against 11 at the first draft's 75.

**The freeze.** Samples, searches and split are one file, put once in the archive under the lock, its SHA-256 committed, before the first tuning call.

## 8. Scoring

Four rows. A: today's search, the code at 48e1f41. B: filed by word, published names only, the $0 baseline. C and D: B with `claude-haiku-5-5`'s names, and with `claude-opus-5-5`'s.

**Columns.** Source 1; source 2 by style and band, with a total weighted by the bands' share of the registry. A cell is hits over searches. Beside it: the first 1 and the first 3 for English, and anywhere in the 50 shown. Every miss is printed with its cause.

**Two tables (owner, 2026-11-23).**

1. **Which model.** Both models read 3,000 products: the 800 test products and 2,200 more by seed. The index is the whole registry's published names, with a model's names on the 3,000 (draft's call). Hebrew searches meet the live crowd of published names. English searches meet an eighth of it, hence the first 1 and the first 3.
2. **The live site.** The whole registry with the shipped model's names, after its full run, on the same held-out searches.

All rows are scored at one commit, named on the scorecard. A later change to the search code re-scores every row.

**Tuning** uses the tuning part only and reads only its products. One prompt for both models, tuned with Haiku 5.5 and checked on Opus 5.5 before the freeze. Haiku keeps its default thinking, as the owner read it: thinking off would save $1.55 a full run, and its names were not read (draft's call).

**The held-out part** is scored when everything is frozen. Looking spends it, so every scoring adds a line to a write-once log, and the scorecard gives the count.

**Run to run.** The same request can give another answer, and no sampling parameter can be set. So each model reads the held-out products three times. The first reading is named, before any score is seen, as the one scored and the one that goes live. The others replace only the held-out products' names. All three scores are shown.

**Also on the scorecard:** the searches only one of two rows found; the brand counts and the size table; readings dropped by rule, refused, cut off; each model's full-run cost; the owner's reads; the model that wrote source 2; that both models are one vendor's. Every miss goes in a document in this repository.

## 9. The key and the spending cap

- **A workspace of the project's own** in the Claude Console, with its own monthly limit and API key [S4] [S5]. The owner set both up on 2026-11-23. An organisation limit would cap every workspace of the account (agent's call).
- **The amount (draft's call):** $75 for the month of the build, $10 a month after. An Opus month with no cache hit, $21, would stop at the limit. A batch "might go slightly over" a workspace's limit [S3], hence `--max-usd` and the slices.
- **The key (draft's call)** stays in the Mac's login keychain. The command removes every `ANTHROPIC_` variable from its own environment before it hands the key to the client, as the trial did.

## 10. Cost

**Batch prices per million tokens** [S1], read 2026-11-23, half the standard ones. Haiku 5.5: $0.05 in, $0.25 out, $0.005 for a cache read, $0.10 for a one-hour cache write. Opus 5.5: $2, $10, $0.10 and $4. A cache write costs 2 times input for an hour, 1.25 times for five minutes.

**Runs,** from the trial's means per product: 1,678 tokens of shared instructions through the cache, 69 more of input, and the answers of the trial's table. First at the trial's cache pattern, 94% of input read from the cache and 2% written; in brackets, no cache hit at all. Opus's full run, worked: 69.3 × $2 + 33.6 × $4 + 1,644.4 × $0.10 + 82.4 × $10 is 1,261 millionths of a dollar a product.

| Run | Products | Haiku 5.5 | Haiku 5.5, thinking off | Opus 5.5 |
|---|---|---|---|---|
| Full | 25,071 | $2.33 ($6.25) | $0.78 ($4.77) | $31.62 ($192.41) |
| One pass of the sample | 3,000 | $0.28 ($0.75) | $0.09 ($0.57) | $3.78 ($23.02) |
| A month | 2,700 | $0.25 ($0.67) | $0.08 ($0.51) | $3.41 ($20.72) |

**A month** is the 341 products that joined the registry between 10 and 18 November 2026 and the 390 whose names changed, scaled up. Inputs that only grow will cut the second count, by an unmeasured amount.

**The build, once,** at the trial's pattern: about $7 before the full run (20 tuning passes of the 350 tuning products, three checks on Opus, the sample and two more readings of the 450 held-out products by each model), then about $10 in all with Haiku or $39 with Opus. With no cache hit anywhere, $47 or $233; section 2's ceiling stops a run long before.

**Each month after:** the model, as the table, and about $0.50 of S3 for the larger search index (2,500 to 4,000 pieces a morning against 209 today; prices in `docs/collector.md:114-115`). In all, under $1 a month with Haiku, about $4 with Opus.

**Still estimates:** the cache share at full size (measured on batches of 50; best-effort in a batch [S3]); the final prompt's tokens, more than the trial's; the month's re-reads; the count and bytes of the search pieces.

## 11. What the plan holds

The order of work, each step on the owner's go: the test searches and their freeze, word-filed search, the batch and the prompt, the comparison and the owner's pick, the full run and the owner's read of 50, the site. Also the tests (test-first, a planted bug for every rule, a fresh review before anything ships), every name, the prompt's wording, the pieces' keys, and the files and docs that change, the stylesheet, `docs/site-look.md` and the runbook in `docs/operations.md` among them.

## Calls made in this draft (the owner can overturn any)

From the first draft, still standing, each marked where it applies: the pair of models; one product a request; the code outside `src/`; the archive bucket and its supersede rule; word-filed search shipped first; Hebrew names never shown; one prompt and three readings; the keychain.

New in this version, by section:

- **1:** brands counted by hand in the reads, with nothing automatic gating one; the count added by code, only beside a weight or a volume; unaccented English names, with `+ ( )` allowed; the size table's split, with nothing classified by hand.
- **2:** inputs that only grow; everything re-read only when told; slices under a worst-case ceiling; the batch's own manufacturer reader, reversing the first draft.
- **3:** banned phrases match whole words in the model's span.
- **4:** a names version counts from the morning after its upload; tuning runs are not uploaded.
- **5:** words match from their start, across names; the rarest word's piece; parts and first parts; the new order.
- **6:** the bar's details (a fresh read on the frozen prompt; a swapped brand is wrong; a failed read hides the name in results too); no alert for products without a reading.
- **7:** source 2 split 100 and 200; six files; the trial's 50 left out.
- **8:** the comparison's index is the whole registry, with first 1 and first 3; Haiku with thinking off is not compared.
- **9:** $75 for the build's month, $10 after.

## Sources

Anthropic's and Cursor's pages, read 2026-11-23.

- [S1] Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- [S2] Models overview: https://platform.claude.com/docs/en/models/overview
- [S3] Batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- [S4] Rate limits and spend limits: https://platform.claude.com/docs/en/api/rate-limits
- [S5] Workspaces: https://platform.claude.com/docs/en/manage-claude/workspaces
- [S6] Thinking: https://platform.claude.com/docs/en/build-with-claude/thinking
- [S7] Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- [S8] Claude Opus 5.5 migration guide: https://platform.claude.com/docs/en/models/opus-5-5/migration-guide
- [S9] Token counting: https://platform.claude.com/docs/en/build-with-claude/token-counting
- [S10] Cursor's models: https://cursor.com/docs/models

The figures of 18 November 2026 come from that day's synced registry, the trial's from each answer's own token counts, and section 5's from Python sketches, not built code.

## Resolved review findings

The outside review of the first draft gave 6 critical, 11 significant, 3 minor and 3 small findings, and 22 on direction. Each was checked against its source before this version: 27 confirmed, 14 in part, 4 could not be checked, none wrong. Where a finding held only in part, the checked fact is in brackets. Ids are the review's.

| Id | Checked | What this version did |
|---|---|---|
| C1 | Confirmed | Folded (section 2): no sampling parameter; no `thinking` field means adaptive thinking on both models; the answer is the block of type text. |
| C2 | Confirmed | Folded (section 7): Grok 4.7, which Cursor's Plus plan and up include, picked by name (owner, 2026-11-23). No Auto. |
| C3 | Confirmed | Folded (section 3): the check reads the model's span, then cuts it out. Banned phrases match whole words there, so "scampi" passes; "US" is dropped and counted. |
| C4 | In part (a rebuilt past day already needs `--revise`; the gap was a same-day rerun after an upload) | Folded (section 4): a version counts from the morning after its upload; the site-day file leaves the field out when no version was read. |
| C5 | In part (the test path is `pyproject.toml:8`; packages pulled by others are unpinned project-wide) | Folded (section 2): the new folder joins the test path, CI's coverage list and the mutation check; the SDK and what it pulls are pinned. |
| C6 | Confirmed | Folded (section 1): 18,789, 962 and 5,320. |
| S1 | Confirmed, as a projection | Folded (section 5): no word dropped; parts in result order. Projected again with the trial's readings: nine words over the limit. |
| S2 | Confirmed | Folded (section 5): a word that ends where a split goes on has its own key; the list of pieces tells split from missing with no fetch. |
| S3 | In part ("1.5l" and "80g" always fail; a bare "1.5" can match) | Folded (section 5): the chains' size filed in Latin letters; a search's words may sit in different names. |
| S4 | Confirmed | Folded (section 5): whole word before word start, published before model-only, the barcode last, one-character words matched. |
| S5 | Confirmed | Folded (section 10): every figure worked again from the trial's tokens, cache writes at 2 times input for an hour and 1.25 for five minutes. The first draft's $74 to $158 and the review's $180 to $248 for Opus both rested on a guessed 250 output tokens; Opus wrote 82. |
| S6 | Confirmed | Folded (sections 2 and 10): inputs only grow and are compared after normalising; the month's cost counts the products whose names changed. |
| S7 | In part (its 1.6 to 2.1 GB rests on guessed multipliers) | Folded (sections 4, 5 and 10): raw answers gzipped and not synced; the index projected from the trial at about 70 MB a morning. |
| S8 | In part (no word passes the limit in a 3,000 sample; the Cursor cut-off is unchecked) | Folded (sections 7 and 8): the sample sits inside the whole registry's index; the first reading is named the live one; later readings replace the held-out names only; six files of 50. |
| S9 | In part (every response carries the workspace header, batch creation too) | Folded (sections 2 and 9): the limit on the workspace; every `ANTHROPIC_` variable removed; the workspace billed kept in the run's record. |
| S10 | Confirmed | Folded (sections 1 to 3): bounds in code, not the schema; the amount a decimal string above zero; `+ ( )` allowed; `he` compared after normalising; `max_tokens` 4,096. |
| S11 | In part (what the change would cost in memory is unmeasured) | Folded (section 2): the price reader stays; the batch has its own reader. |
| M1 | Confirmed | Folded: the missing files join the plan's list (section 11); the method section must clear the banned phrases (section 6); turning names off leaves word-filed search (section 4). |
| M2 | Confirmed (why the counts differ is unchecked) | Folded: the 13,507 figure is cut; the trial's brand counts carry the point. |
| M3 | Confirmed | Folded in part: about 5,000 words before this section, from 6,758, with the trial, the bar and the brand counts added; runbooks, task order and test lists moved to the plan. |
| N1 | Confirmed | Folded: the script's full path throughout. |
| N2 | Confirmed | Folded: the citation is now `src/collector/store.py:115-119`. |
| N3 | Confirmed | Folded: no word is dropped, so no message for one; the live reading is named in plain words (section 8). |
| D1 | Could not be checked | Kept, framed in "Why" as what release 2 needs first. |
| D2 | Could not be checked (its latency figures have no source) | Kept; the reason is in goal 4, without the figures. |
| D3 | In part | Declined: the field stays (agent's call). In the trial 35 of 50 products had no brand without it, 25 with it. Its churn and the reader change are fixed under S6 and S11. |
| D4 | In part | Folded: 200 held-out products in source 2. Declined: 50 size differences classified by hand; the table splits a count against a weight from a real difference instead. |
| D5 | Confirmed | Kept: one vendor, two models, and the scorecard says so. |
| D6 | In part (its held-out-name figure is 33.0%, not 27.3%) | Folded: source 2 at 300; source 1 named the no-harm check. Declined by the owner (2026-11-23): 60 to 100 hand-written searches. |
| D7 | Could not be checked | Folded as the owner's bar: at most 1 wrong in 50 (section 6). |
| D8 | Confirmed | Folded (section 8): the sample inside the whole registry's index; first 1 and first 3 for English. |
| D9 | Confirmed | Kept. The trial was the spike. |
| D10 | Confirmed | Kind dropped (owner, 2026-11-23); the AI label kept. Declined: a grams-against-millilitres table for q41, a non-goal; the readings keep the unit. |
| D11 | Confirmed | Folded (section 6): the count of products without a reading, on the method page. Declined: an alert, which would fire every morning between hand runs. |
| D12 | In part | The trial ran Haiku with thinking off and 50 products on Opus. Declined: thinking off in the comparison; it saves $1.55 a full run and its names were not read. The prompt is checked on Opus before the freeze. |
| D13 | In part (its "$22 packed" figure is wrong) | Kept: one product a request, the barcode out. The cache share measured 94 to 96%; a run stops under half. |
| D14 | Confirmed | Kept, with C5's wiring. |
| D15 | Confirmed | Folded (section 4): tuning runs are not uploaded; raw answers are gzipped. |
| D16 | Confirmed | Folded (section 8): all rows scored at one commit; a later change to the search code re-scores every row. |
| D17 | Could not be checked | Folded: tuning lists results found only through a model's Hebrew name. Declined for release 1: a "matched" note on the page, a second kind of AI text to gate. |
| D18 | Confirmed | Folded (sections 2, 9 and 10): the limit on the workspace; the ceiling worked from measured output; both models' months given. |
| D19 | Confirmed | Folded (section 2): inputs compared after normalising; a changed prompt or model re-reads everything only when told. |
| D20 | In part (the widely sold band is over-weighted, not under; its power figure does not reproduce) | Folded: 300 products, cells by band, a weighted total. Three readings kept: they now cost about $1. |
| D21 | Confirmed | Done: the trial, $0.07. Its figures are in this document. |
| D22 | In part | Folded: Latin size words; kind dropped. Declined: checking the fields against release 2's lists now; reading everything again costs $0.78 to $32. |

## Review findings

### Critical

- **[S1, S2, S4] Section 5 does not define a complete multi-piece lookup.** The browser currently selects one piece and caps the filtered result at 50 (`src/shopper/static/search.js:91-112`). The draft adds terminal keys, descendant keys, numbered exact-word parts and parent "first parts", but never says which combination a query loads or when it advances past a first part. A multiword search can reject every entry in an oversized word's first part while a valid product sits in a later part; an exact word that is also a prefix needs both its terminal products and longer-word descendants. "Rarest" is also undefined unless each manifest count is a unique-product count over all relevant descendants and parts. A whole-registry simulation under one reasonable reading needed as many as 31 files to exhaust a partial prefix now and 68 after adding 137 bytes per posting. The claimed S1/S2/S4 fixes are therefore not complete. **Fix:** specify a versioned manifest or trie, unique-product counts, terminal and child metadata, part order, deduplication, failure handling and an algorithm that fetches until 50 globally ranked matches are found or every candidate is exhausted; prove its request and byte bounds.

- **[S4] Section 5's compatibility claim is false as written.** Current search matches the whole normalised query as a substring (`src/shopper/static/search.js:104-112`) after requiring only two characters overall (`:283-288`). On the 18 November registry, `2 מ` returns seven products and `3 ב` returns one, but every word is one character and the new rule says such words never select a piece. Current matches also begin after punctuation: `דריי` finds `דאו.דריי...`, and `שמרים` finds `שמרית-שמרים...`; the draft never defines whether punctuation starts a word. This can break searches that work today despite decision 4. **Fix:** define one tokenizer shared by Python and JavaScript, including punctuation and size forms; add a fallback when every term is one character; regression-test all 25,639 alternate published-name searches, barcodes and punctuation cases against current results.

- **Section 2's spending ceiling is not a ceiling.** It calls the trial's 95th-percentile output length the "worst case", although each request permits 4,096 output tokens and [S8] says `max_tokens` is the hard limit over thinking plus text. The measured p95 was 823 tokens for Haiku and 101 for Opus, not a bound; [S9] also says an input token count is an estimate. One submitted slice can therefore pass `--max-usd` before usage is observable, contrary to the anti-goal. **Fix:** reserve each request at its full `max_tokens`, the one-hour no-hit write price and an input-count margin; lower `max_tokens` if that reserve is impractical; submit the next slice only after the previous slice's final usage is recorded.

- **Sections 2 and 3 put the shared validator where Lambda cannot import it.** Section 2 places the new package outside `src/`, while the deployed function's `CodeUri` is exactly `src/` (`template.yaml:574-579`). Section 3 then requires one function to validate when the offline file is made, when the Lambda build reads it and in the site check. That function cannot live only in the outside package, and putting the SDK package in `src/` would change the function zip and fingerprint. **Fix:** put the pure artifact and page validator in `src/`; keep only the prompt, API client and SDK-dependent caller outside `src/`; test that the Lambda artifact contains no SDK dependency.

- **Section 4's names release is not atomic.** The names file, record, raw answers and scorecard are four independent locked puts. `put_record` makes one object immutable (`src/collector/store.py:115-121`), not a folder complete; a stopped upload can leave a partial run that "newest version" may select. The same gap can mix a names file and scorecard from different attempts. **Fix:** upload immutable content-addressed artifacts first, then put one immutable release manifest last with every key and SHA-256, schema version, approval/display state and explicit enabled or disabled state. The build must ignore a folder without that valid final manifest.

- **Sections 4 and 6 omit a required scorecard input.** Section 4 says the archive run contains a scorecard and section 6 builds the method page from the scorecard beside the names file, but the sync list explicitly fetches only the names file and record. The current sync has no names or scorecard path at all (`scripts/sync.sh:49-88`). A hand build or reproducible past-day rebuild therefore cannot perform the stated method-page build. **Fix:** sync the selected release manifest, names, record and public scorecard, with enough history to resolve the version pinned by a site-day file; continue to exclude raw answers. Name the README update path as well, since decision 12 promises the scorecard there.

### Significant

- **Section 5 lacks the data needed for its ranking rule.** Current entries are flat lists with no source or display tag (`src/shopper/search.py:82-86`), while the proposed order needs to distinguish published, model-English, model-Hebrew and generated-size matches and to know whether all terms occur in one name. Query-term order, duplicate terms, mixed match strengths, phrase equality, duplicate postings and the final 50-result cutoff are not settled. **Fix:** define the entry schema and one complete ranking tuple, including barcode deduplication and a deterministic tie-break, and use the same scorer in the browser and evaluation code.

- **The live search publication can expose a mixed build.** The current uploader starts data and page puts in one concurrent pool (`src/basket/site.py:130-187`); a failed run may have replaced `pieces.json` but not every referenced piece, or the reverse. Dynamic split keys make that worse. Keys that disappear also remain current objects forever because the lifecycle expires only noncurrent versions (`site-template.yaml:23-42`). **Fix:** give pieces content-addressed names, upload and verify every piece first, publish the manifest last, retain old referenced pieces through the cache window and expire orphaned build prefixes.

- **Section 5's size and performance projection is not enough for production planning.** A whole-registry remeasurement found 17,633,893 bytes before recursive splitting, 21,471,749 bytes and 1,409 pieces when each oversized prefix keeps a first part, and 49,731,158 bytes and 2,273 pieces after only 137 bytes are added to each existing posting. That lower bound still adds no model words or size aliases; its largest partial-prefix traversal was 68 files. The draft's 70 MB projection from 50 model readings does not measure browser requests, parse time, build memory or upload time in the 3,008 MB Lambda (`template.yaml:580-590`). **Fix:** make a disposable whole-registry index with worst-valid readings before the plan and measure piece bytes, manifest bytes, peak RSS, build/check/upload time and browser fetch/parse time.

- **Section 4's fallback and version selection can silently change a day's site.** "A faulty file" falls back to published names, but malformed released data, an S3 list failure, a denied read and a transient network error need different outcomes: treating all alike can remove model names during an infrastructure fault. "Newest ... by the date in the key" also leaves the Israel-time boundary, same-day tie, backdated upload and past-day pinning unspecified. **Fix:** define the full error matrix; fail the build on access failures, deterministically reject malformed releases, record attempted and effective release ids, pin an existing site-day to its effective release, and derive release dates from aware Israel times.

- **[S6, D19] Section 2's "input only grows" state does not exist in the described readers.** `Covered` keeps the later listing for each column and can replace a name (`src/shopper/history.py:309-356`); `basket.pricefile.Item` has no manufacturer field (`src/basket/pricefile.py:34-43,88-99`); a reader over one synced day cannot reconstruct an all-time union. Permanent growth would also preserve corrected, removed or hostile values forever. The S6 and D19 dispositions do not define separate input and prompt/schema/model fingerprints or a full-reread operation. **Fix:** define a versioned input snapshot with day and field provenance, current-versus-last-known-good retention rules, exact merge/removal rules and separate fingerprints that automatically select delta reads or an explicit full reread.

- **Sections 1 to 4 never give the complete names-file contract.** "One reading per product" does not settle envelope and JSON types, duplicate or unknown barcodes, missing products, an intentional empty release versus an all-invalid file, canonical whitespace and decimal syntax, per-line versus whole-file failure, or how a complete file proves its source registry. The run record also omits the generator commit/dirty state, dependency-lock hash, input snapshot hash, schema hash, arguments, seeds, batch ids and per-entry model provenance needed by the stated reproduction goal. **Fix:** make the artifact schema and validation order normative and put every provenance and artifact hash in the release manifest and run record.

- **Section 1's generated count and length rules can publish unsupported text.** `normal_size` accepts any bounded decimal count above one, including fractions (`src/basket/units.py:63-80`); metres and centimetres are deliberately not represented (`:40-52`). The trial already produced `Pita bread 10 pack` without that being a validation rule, so code can append another count. Appending `, 6 pack` can also take a valid 60-character name over its bound. **Fix:** accept only a source-stated canonical integer count above one within a stated bound, reject or deduplicate counts already in `en`, validate the final displayed name, and either add a separately validated source-stated length field or drop the claim that lengths are preserved.

- **Section 1's brand rule and manual count do not enforce the displayed-name contract.** The input-presence check accepts ordinary words; "a common Hebrew word is never a brand" can also reject a real ordinary-word brand. The trial shows every failure class: rows 32 and 40 turn ordinary words into brands, row 42 keeps structured brand `קינד` but displays the different brand "Kinder", rows 25, 28, 30 and 39 drop stated brands for Haiku, and row 15 drops one for Opus. Structured-brand disagreement cannot catch row 42, because both structured fields say `קינד`. **Fix:** show source names, manufacturer values, structured brand and displayed English together; make source/English mismatches automatic review flags; use model disagreement as another flag, not proof; and make every invented, swapped or dropped required brand affect an explicit gate.

- **"What the trial measured" mixes historical marks with the new wrong-name rule.** The table says Haiku had two wrong names, but under section 6's new rule the two invented brands and the Kinder substitution are wrong too, making at least five. The owner did not use that rubric during the first read. Opus's zero wrong remains a useful observation but includes one stated brand left out. **Fix:** label 2/0 as the original reader's marks, publish the second reader's reclassification separately and do not use the old count as evidence that the final gate was applied.

- **Section 6's display gate leaves important failure classes unbounded.** The document itself says one wrong in 50 permits a true wrong rate near 9%, yet calls that a pass over 25,071 pages. Missing, unsupported guess and style counts have no threshold at all, and the fresh 50 is seeded but not stratified by truncation, non-food goods, manufacturer-only brands or no-Hebrew products. **Fix:** use a blind stratified sample of at least 200, define whether unsupported guesses and required-brand omissions fail display, set thresholds for every category, and have a second reader adjudicate all failures or a random overlap.

- **Section 8 uses the held-out set to choose the shipping model.** Once the owner sees C and D and chooses a model, that set is validation data, not an untouched estimate of the chosen system. Showing three stochastic readings of the same held-out products does not restore independence. **Fix:** add a final untouched test split, or predeclare the selection rule and label the reported result honestly as selection-set performance; calculate uncertainty by product because three searches from one product are correlated.

- **[D16] Section 8 cannot both preserve row A and score every row at one commit.** Row A is explicitly the search at `48e1f41`; "all rows are scored at one commit" and later re-scoring after search changes would instead run current code unless the old algorithm is preserved. Reimplementing it risks changing the baseline. **Fix:** execute the exact baseline commit against frozen inputs in an isolated checkout, or retain and test a versioned baseline function; record both implementation commit and scoring commit. The D16 disposition is not complete.

- **The source-2 split silently changes the owner's held-out-half decision.** The owner's 18 November decision says a frozen held-out half; section 7 uses 100 tuning and 200 held-out and labels that only as a draft call. More held-out data can be sensible, but it is a direction change, not a faithful restatement. **Fix:** use 150/150 or obtain explicit approval for 100/200 and update the decision table, tuning cost and uncertainty statements.

- **Section 7 overstates the precision of source 2's reported cells.** A worst-case 95% margin near seven points applies to one proportion over 200 independent products. A style-by-band cell has only about 66 or 67 held-out products, near a 12-point margin, and the three searches from one product are correlated. **Fix:** state the denominator and interval for every reported cell, cluster or bootstrap by product, and call the band/style cells descriptive unless the sample grows.

- **Section 8 cannot append to one write-once log.** Every scoring is said to "add a line to a write-once log"; an object protected by `IfNoneMatch="*"` and Object Lock cannot be appended or replaced. **Fix:** write one immutable access record per scoring event under a run-id key and derive the displayed count from those records.

- **The public-launch decision is missing.** The owner decided at 13:03 on 23 November that sharing the site waits for all of release 1, not only word-filed search. Section 5 says word search ships first and section 11 gives build order, but nowhere says that this is a private/noindex deployment and that public sharing remains gated. **Fix:** state the launch gate explicitly and separate technical deployment from the public post.

- **[D11] Section 6 does not do what the resolved row claims.** It publishes the count *with* a reading, not the count without one, and explicitly has no alert. An alert need not fire every morning: a fall in coverage, an oldest-unread age or a backlog above the expected hand-run interval can signal a regression without routine noise. **Fix:** publish total, read and unread counts and alert only on a threshold or adverse change. The D11 disposition is not resolved.

- **The hard test rules are incomplete for model code.** Section 11 mentions tests, planted bugs and review, but not the 95% floor, fixed times, recorded model answers instead of live calls, or proof that every direct and transitive dependency is pinned and at least a month old. CI currently covers only the three existing targets (`.github/workflows/ci.yml:23`), and the new package is not on `pythonpath` (`pyproject.toml:7-10`). **Fix:** make recorded response fixtures and no network/model call in tests explicit; require fixed aware times, add the package to both coverage workflows, keep the 95% floor and add a planted bug for every new rule.

- **"Never shown" is not "not public" on this static site.** Search aliases must be shipped in public JSON for the browser, and CloudFront can read every site-bucket object (`site-template.yaml:83-93`). Thus model Hebrew names and pre-display-gate English terms remain downloadable even when the UI hides them. The manufacturer's strings on the owner's review page could also become raw published fields if that page is built under `site/`. **Fix:** state that search aliases are public but UI-hidden, label a result whose match depended on AI if goal 5 requires that disclosure, and generate manufacturer review pages in an excluded local folder that upload code refuses.

- **The manufacturer reader's filtering contract is too small.** Section 1 names only `לא ידוע`, while registry verification found frequent placeholders `Unknown` (2,890 rows), `כללי` (2,172) and `משתנה` (1,033). The design also does not name the exact manufacturer tags, duplicate/conflict handling or barcode normalisation used to join rows. **Fix:** define a normalised, tested placeholder set, exact source tags, raw-value provenance and use the existing barcode normaliser; report every dropped or conflicting value.

### Minor

- **[S8] Six files of 50 mitigate an unknown Cursor cutoff but do not verify it.** The S8 row still calls an unchecked limit folded. **Fix:** make the loader require exactly 50 distinct sampled products per file, validate file and product hashes, reject truncation or prose around the schema and retry a smaller chunk before the freeze.

- **[S10] Section 3 overstates structured-output limits.** [S7] supports `minItems` of 0 or 1; SDK helpers can strip unsupported bounds and validate locally, while raw unsupported constraints return 400. "An item count returns a 400" is therefore not generally true. **Fix:** say that raw schemas cannot enforce numeric bounds, string lengths, `maxItems` or `minItems` above one, and that this design deliberately validates every bound in its own code.

- **The trial's "1,686 tokens cached" is not the measured cache block.** The dry-run empty-product request was 1,686 tokens, while actual usage shows 1,678 cacheable tokens for A/C and 1,677 for B/D; mean uncached input was 69.3 for A-C. **Fix:** distinguish empty-request token count, cacheable block, product increment and billed uncached input.

- **The trial invalid counts describe the old checker, not this draft.** A plus sign caused one invalid answer in every configuration, but section 1 now allows `+`. With only that rule changed, A/B/C/D have 2/1/0/1 invalid answers rather than 3/2/1/2. **Fix:** label the existing row "failed the trial checker" and add the counts under the final proposed checker.

- **"All 200 requests succeeded" hides validation failure.** All 200 API requests returned, but eight outputs failed at least one trial rule. **Fix:** use those two statements explicitly.

- **The trial size summary omits most outcomes.** The trial table gives A as 16 agree, 2 differ, 18 model-missing, 1 registry-missing and 10 both-none; C is 16, 2, 18, 3 and 10. All four A/C "differences" are count versus weight, not contrary quantities. **Fix:** give all categories and valid denominators and show the promised count-versus-weight split.

- **The thinking-off saving is rounded and not like-for-like.** The observed full-run difference is $2.33356 minus $0.77595, or $1.56, and A had cache writes while B had none; equalising cache treatment gives about $1.48. **Fix:** call $1.56 the observed configuration difference and distinguish the cache-adjusted estimate.

- **[N2] The Object Lock citation is still wrong.** `src/collector/store.py:115-119` delegates to the locked put, but `IfNoneMatch`, governance mode and retain-until are at `:168-180`. **Fix:** cite the latter range and say these exact arguments apply to every names-release object.

- **[D13] The resolved row omits the verified packed-request correction.** Under the first draft's guessed 250 output tokens, output alone was $62.68 and a packed Opus run about $73, not $22. Trial-measured 82-token answers support a new, separately labelled estimate; they do not make the old correction disappear. **Fix:** record both the corrected old assumption and the measured replacement.

- **The API contract lacks two qualifiers.** The no-sampling-parameter 400 is tied to API version `2026-10-21` in [S6], but the design pins no API version. Haiku's quoted price in [S1] is for prompts up to 100,000 tokens under default global routing. **Fix:** pin and record the API version and add the pricing scope; also state that US-only routing costs 10% more if it is ever selected.

- **Section 8's four-row statement does not fit both tables.** The model table has A-D; the live table has today's search, word-only and the selected model, not four model rows. "Each model's full-run cost" also sits beside a plan to run only the selected model in full. **Fix:** name the rows and cost status of each table separately.

- **[M3] The main design still misses its length aim.** It has 4,998 whitespace-delimited words before the resolved section, about 500 above the 4,500 aim. Removing "What is decided" helps; the exact request shape, keychain/environment mechanics, CI wiring, sync/IAM edits, detailed cost multiplication and task order can move to the plan or an appendix. Keep the search contract, ranking, release state and public gates here because they are decisions, not build detail.

- **[D5, D6, D7, D12, D18] Five direction dispositions still lack a reason that survives the evidence.** D5 says only that the scorecard names one vendor; D6 and D7 cite the owner rather than a reason; D12 uses "not read" as the reason not to read an already-produced configuration; D18 sets one recurring cap even though the selected model is undecided and Opus's no-hit month is $20.72. D10, D17 and D22 also make unattributed release-scope declines despite the status promise that every decision is marked. **Fix:** record the actual tradeoff or a cheap deciding measurement and mark whose call each decline is.

- **The monthly cost is not yet complete.** It counts model calls and about $0.50 for the index, but not immutable names/releases/raw answers, orphan current search keys, failed or repeated batches, or CloudFront request and egress variation. **Fix:** add low, expected and high monthly totals after the index spike, with retention and retry assumptions.

### Nit

- **Section 8's "an eighth" is loose.** `3,000 / 25,071` is 11.97%, not 12.5%. **Fix:** say "about 12%".

- **"$0 word index" means no model-call spend, not no cost.** It increases build, S3 and CloudFront work. **Fix:** call it the "$0 model-call baseline".

- **"Pass" and "freeze" name different gates without warning.** Opus met the trial's numerical threshold but has not passed the fresh release read; the samples/searches freeze before tuning while the prompt/model freeze comes later. **Fix:** name the trial threshold, release gate, evaluation freeze and prompt freeze distinctly.

- **"The manufacturer field earns its place" is causal wording for one stochastic pair.** The measured 25 versus 35 no-brand answers and ten manufacturer-only brands are useful evidence, not a repeat-run effect estimate. **Fix:** say "the trial supports keeping it".

### Direction findings

- **D1 — Product understanding before the free index (decision 1).** **Case against:** the model delays the largest known gain; source 1 is about 54.5% today and 99.6% under the sketch's free index. **Evidence to settle it:** score row B first on the frozen shopper-style searches and count misses that only model aliases recover. **Recommendation: change** to a free-index release first, with model aliases as the next independently gated release.

- **D2 — Hold public launch for the whole release (decision 1 and the 13:03 launch decision).** **Case against:** feature completion is not a quality criterion, and the free index may make search good enough to share while model display work continues. **Evidence to settle it:** set Hebrew, everyday-name and English launch targets, then score row B and the model row against them. **Recommendation: change** the gate to measured search quality; keep English as a separate gate if row B still fails English.

- **D3 — Offline batch, no request-time model (decision 2).** **Case against:** hand runs leave new or changed products stale; 341 products joined and 390 names changed in eight days. **Evidence to settle it:** replay 30 days and measure unread age and the searches affected between runs. **Recommendation: keep** the offline design; static reliability, key isolation and cost outweigh live inference for a slowly changing catalogue.

- **D4 — Compare two Claude models rather than choose Opus now (decision 11).** **Case against:** under the final brand rubric Haiku has at least five wrong trial names, while Opus had zero wrong in the owner's read, and the full Opus run is about $32. **Evidence to settle it:** a blind 100-200-product read on the frozen final prompt, stratified for the observed hard cases. **Recommendation: change** to Opus as the provisional shipping model; keep Haiku as a published benchmark and reopen shipping choice only if the larger read reverses the quality result.

- **D5 — Drop structured kind (non-goal; decision 10 still lets English infer one).** **Case against:** release 2 may need a kind, and inferred kind words can drive useful searches even though the field is gone. **Evidence to settle it:** count held-out searches found only through inferred kind and inspect release 2's minimum contract. **Recommendation: keep** kind out of release 1; do not create a taxonomy until measured value justifies it.

- **D6 — No hand-written searches; 300 products written by Grok (decision 7).** **Case against:** another vendor is independent of Claude but not representative of shoppers, and 200 held-out products cannot support precise style-by-band claims. **Evidence to settle it:** blind-compare 30 Grok-written and 30 owner-written searches for realism and row ranking. **Recommendation: change** to a mixed set with at least 60 human-written queries retained as a separate reported source.

- **D7 — Display AI English names, including inferred kind (decision 10).** **Case against:** an AI label discloses origin but does not make a wrong general-knowledge inference safe; retrieval can tolerate aliases that a product page should not assert. **Evidence to settle it:** audit source-grounded translations separately from inferred additions on a stratified display sample. **Recommendation: change** to separate retrieval aliases from displayed text and display inferred kinds only after their own gate.

- **D8 — At most one wrong in one person's 50-name read (decision 9 and section 6).** **Case against:** the draft's own bound allows roughly 9% wrong, and the trial shows rubric drift around brands. **Evidence to settle it:** a blind stratified read of at least 200, with a second reader on every failure and a random overlap. **Recommendation: change** the gate accordingly and make unsupported guesses and required-brand omissions explicit pass/fail categories.

- **D9 — Compare models on 3,000 products in two tables (decision 11).** **Case against:** English ranking against model names on only 11.97% of products is optimistic relative to the final crowd, while normal-cache full runs of Haiku and Opus together cost about $34. **Evidence to settle it:** compare sparse-index and full-index ranks for the same English queries, stopping in slices if cache performance falls. **Recommendation: change** to a small elimination round followed by a full-registry comparison of finalists, or at least the chosen model against a full competitor index.

- **D10 — Production grade for release 1 (grade and decision 12).** **Case against:** treating every evaluation script as permanent production infrastructure can turn a one-week feature into a large platform. **Evidence to settle it:** separate public-runtime, archive and rollback risks from disposable tuning tooling and estimate the critical path. **Recommendation: keep** production grade for anything that changes the live site or evidence; allow small, reproducible local evaluation tools to remain deliberately temporary.

- **D11 — Add a model count beside a weight or volume and retain lengths (decision 13).** **Case against:** a count can be wrong independently of the page's weight, and the current size field cannot represent or validate length. **Evidence to settle it:** enumerate all count/length trial and tuning cases and verify each value appears in a published source name. **Recommendation: change** to source-stated structured counts and lengths with final-name validation; keep unverified values search-only or omit them.

- **D12 — "A common Hebrew word is never a brand"; brands checked by hand (decision 13).** **Case against:** real brands can be ordinary words, manual review of 50 does not cover 25,071 products, and seven of eight observed misses fell in model disagreements. **Evidence to settle it:** audit 100-200 common-word, manufacturer-only and model-disagreement cases against source evidence. **Recommendation: change** to evidence-backed brand rules and an automatic disagreement/mismatch review queue; disagreement flags uncertainty but does not decide truth.

- **D13 — Rarest-word pieces, recursive parts, first parts and the new order (section 5).** **Case against:** the scheme has no complete retrieval proof and one reasonable whole-registry interpretation needed 68 files for a prefix. **Evidence to settle it:** the disposable index spike required in the significant finding above, with exhaustive recall and browser timing. **Recommendation: measure first** and do not write the implementation plan until one precise scheme passes.

- **D14 — Ship word-filed search first and alone (section 5).** **Case against:** a staged deployment can spend the baseline or be mistaken for the public launch. **Evidence to settle it:** deploy it while the site stays noindex, freeze its commit and score it before any model index changes. **Recommendation: keep**, but state explicitly that technical deployment is not public launch and preserve a reproducible row B.

- **D15 — Put names under the ten-year lock; supersede, never remove; hold back one bad name (section 4).** **Case against:** copying whole versions and using an empty file as an off switch creates non-atomic operational baggage. **Evidence to settle it:** rehearse partial upload, withdrawal, one-barcode holdback and rollback locally. **Recommendation: change** to immutable content-addressed runs plus an atomic append-only release/withdraw manifest; retain the evidence without making partial folders selectable.

- **D16 — Keep model-calling code outside `src/` (section 2).** **Case against:** validation shared with Lambda cannot stay outside the deployed package. **Evidence to settle it:** inspect the built Lambda zip and run the same artifact corpus through offline and runtime validation. **Recommendation: change** the boundary: API caller outside `src/`, pure schema and validator inside it, SDK absent from the function.

- **D17 — $75 build-month and $10 recurring caps (section 9).** **Case against:** $10 cannot cover the documented $20.72 no-hit Opus month, while a cap below a legitimate run creates a stale partial catalogue. **Evidence to settle it:** one frozen full run and a 30-day delta replay with actual cache and retry behavior. **Recommendation: measure first**; keep $75 provisional, then set a model-specific recurring cap above a complete worst-plausible run with alerting below it.

- **D18 — Inputs only grow; reread only when told (section 2).** **Case against:** stale, corrected and hostile values become permanent, and a schema or prompt fix can leave old readings mixed with new ones. **Evidence to settle it:** replay 30-90 days and classify additions, corrections, removals and missing-chain days. **Recommendation: change** to current plus last-known-good inputs with grace rules and automatic invalidation by separate input, prompt, schema and model fingerprints.

- **D19 — Do not compare Haiku with thinking off (section 8).** **Case against:** 50 outputs already exist at no further API cost; "not read" is a reason to inspect them, not omit them, and the projected full run is $0.78. **Evidence to settle it:** blind the labels and have the owner apply the final rubric to B now. **Recommendation: measure first**; include it only if that read is competitive.

- **D20 — No alert for products without a reading (section 6).** **Case against:** a broken delta job can silently leave coverage falling for weeks. **Evidence to settle it:** replay expected hand-run intervals and choose a stable bound for unread age, backlog or coverage change. **Recommendation: change** to threshold-based staleness/regression alerts, not one alert per unread product.

- **D21 — One product per request; barcode outside model input (section 2).** **Case against:** 25,071 requests add batch overhead and more individual failure points. **Evidence to settle it:** a full dry manifest against documented batch limits and measured cache behavior. **Recommendation: keep** because the trial had 200/200 API returns, 94-96% cache reads and much smaller prompt-injection blast radius.

- **D22 — Keep manufacturer values and a dedicated reader (decisions 3 and section 2).** **Case against:** manufacturers are often parents, importers or placeholders and can reduce brand precision even while improving recall. **Evidence to settle it:** a by-chain audit of manufacturer-only brand decisions and placeholder/conflict rates. **Recommendation: keep conditionally**, with provenance, exact filtering and no change to the production `Item` reader.

- **D23 — First-round dispositions and owner-unseen drift.** **Case against:** every D row exists, but D5, D6, D7, D12 and D18 lack an adequate reason; new search, gate, split, retention, caps, monotonic inputs and alert rules were not approved merely because they are labelled draft calls. **Evidence to settle it:** one owner checkpoint over a short list of those choices, with the trial and registry measurements beside each. **Recommendation: change** the document only after that explicit checkpoint and record the reason, not only the chooser.

- **D24 — Sequencing before an implementation plan.** **Case against:** planning now would turn unproved search and quality assumptions into tasks and tests. **Evidence to settle it:** complete five cheap spikes: whole-registry search prototype; blind read of existing Haiku-off answers; Grok-versus-human query check; manufacturer/brand audit; and 30-90-day input-churn replay. Then set the display sample and error budget. **Recommendation: measure first**; these results are design inputs, not plan tasks.

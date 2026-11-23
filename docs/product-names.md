# Product names: the site's first language model, release 1 (design)

**Grade:** production (the owner's, 2026-11-18): it changes the live public site.

**Status:** third version, 2026-11-23, for the owner's approval. Nothing is built. It folds in two outside reviews, each finding checked against its source, a paid trial of 50 products through three models, a throwaway search measurement on the whole registry, and the owner's decisions of 2026-11-23. The last section gives each finding's fate. A decision is marked as the owner's (with its date), the agent's call (the AI assistant the owner designs with), or this draft's ("draft's call"); the owner can overturn any call. No question for the owner is open: the last is answered among the decisions (decision 18). Built, deployed and paid for only on the owner's go. Line numbers are main's at 7ff9faf.

## Why

The site answers "is it actually a deal?" for one product at one store. The shopper must find the product first, and search is the weak step.

- A product's search entry sits in one index piece, chosen by the first characters of its longest name (`src/shopper/search.py:12-22`). On the registry of 18 November 2026 (25,071 covered products), the 25,639 names that differ from their product's longest name, typed as searches, reach today's first 10 results 54.5% of the time.
- The chains publish Hebrew names, often abbreviated. A search in English, or in a product's everyday word, has nothing to match.

The second reason is the owner's job search: the roles carry AI in the title, and no site the owner runs calls a model. This piece is small, measured against a baseline with no model, and published with its misses and cost. Release 2's shopping-list agent needs the same names first.

## Goals

1. A shopper finds a product by any word of any of its names, by its everyday Hebrew name, or in English.
2. No search that works today stops working.
3. The model's share is measured against today's search and a word index with no model, on searches the tuned system never saw.
4. The scorecard is public: numbers, misses, cost.
5. The morning build stays static: no model key, no model call. The catalogue changes slowly, so a model call per search would buy only delay, cost and an open endpoint.
6. A shopper can always tell the chain's words from the model's.

## Non-goals

- Release 2: the shopping-list agent and its live endpoint (owner, 2026-11-18).
- Showing the model's brand or size, but for a count beside the English name; using its size in any price, verdict or basket rule; splitting grams from millilitres.
- Promotions' fine print, a schedule, hand-written test searches, spelling correction, a search server.

## Anti-goals

A failure even if everything else works: a model's name shown as the chain's, or on a page before the read of 200 passes; a search that works today lost; a score from searches the scored model wrote, or seen while tuning, or used to choose anything; a morning build that fails, waits or changes a number because of the model; model text unescaped on a page; one blended score that hides what the word index gives with no model; spending with no ceiling.

## What is decided

| # | Decision | Whose |
|---|---|---|
| 1 | An offline batch writes, per covered product: an English name, everyday Hebrew names, brand, size. | Owner, 2026-11-18 |
| 2 | Readings go to a versioned S3 file the 12:33 site build reads; the build holds no model key and calls no model. | Owner, 2026-11-18 |
| 3 | The price files' manufacturer field is an input and a brand cross-check. The trial supports keeping it: without it Haiku (thinking off) left 35 of 50 products with no brand, with it 25, in one pair of runs. | Owner, 2026-11-18; kept: agent |
| 4 | `claude-opus-5-5` [S2] writes the names that ship, picked after a paid trial through Haiku 5.5, Sonnet 5.5 and Opus 5.5. | Owner, 2026-11-23 |
| 5 | Haiku 5.5 and Sonnet 5.5 stay as small comparison rows on the scorecard. | Agent, 2026-11-23; the owner was not asked |
| 6 | English names reach pages only after a read of 200 names by two readers, the owner and an AI model that never sees the owner's marks (a fresh Fable subagent; Opus at Fable's limit, named), passes: at most 4 wrong, counting only names that say something the product is not. | Owner, 2026-11-23 |
| 7 | Sonnet 5.5 also reads every product for its brand. A product where both models name a brand and the two differ is held search-only on a review list until reviewed. | Owner, 2026-11-23 |
| 8 | The public launch waits for the AI names: all of this release, not the word index alone. | Owner, 2026-11-23 |
| 9 | The English name may add the kind of product from general knowledge ("Old Spice deodorant"), marked as written by AI. | Owner, 2026-11-23 |
| 10 | Kind (category) is dropped as a field. | Owner, 2026-11-23 |
| 11 | Search keeps today's pieces and lookup unchanged, with a word index beside them: a whole word keeps its full list, a part-typed start its first 50. Its files keep fixed names, as today's pieces do. | Owner, 2026-11-23 |
| 12 | Every product today's search shows stays among the 50 shown, ranked by best match in section 5's seven steps. | Owner, 2026-11-23 |
| 13 | Scoring: a frozen held-out half; today's search and a word index with no model as baselines; misses and cost printed; size as agreement, not truth. | Owner, 2026-11-18 |
| 14 | No hand-written test searches. Source 2: 300 products, written once in Cursor by Grok 4.7. | Owner, 2026-11-23 |
| 15 | The score: the product searched for is in the first 10 results. | Owner, 2026-11-23 |
| 16 | The owner's personal Anthropic API account, under a monthly cap on the project's own workspace: $35 a month after the build. | Owner, 2026-11-23; the workspace and the build month's $75: agent |
| 17 | The English name: marked as written by AI wherever shown; natural word order; whole English when the input name is cut; a count kept beside a weight; lengths kept. Brand and size scored, not shown. The scorecard on the method page and in the README. The batch by hand. The chains' size also filed in Latin letters. | Agent |
| 18 | The launch also waits until the review list is cleared: every held product reviewed before the post. | Owner, 2026-11-23 |

## What the trial measured

A paid trial on 2026-11-23: 50 products drawn by seed from the registry of 18 November 2026, one a request, effort low, the shared instructions cached for an hour. Five batches: Haiku 5.5, Haiku with thinking off, Opus 5.5, Haiku without the manufacturer strings, and Sonnet 5.5 on Opus's requests. All 250 requests returned an answer, 10 answers failed a check, and it cost $0.10. The cached instructions measured 1,678 tokens (1,686 by the free counter), a product's own input 69; 94 to 96% of input was read from the cache.

| | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|
| Output tokens a product (of them thinking) | 312 (231) | 84 (0) | 82 (0) |
| Answers failing the trial's checker, of 50 (with `+` allowed, as now) | 3 (2) | 2 (1) | 1 (0) |
| Products given no brand, of 50 | 24 | 28 | 19 |
| The owner's read: wrong, missing, a guess, style | 2, 6, 2, 11 | 1, 1, 3, 2 | 0, 3, 2, 9 |
| A full run at the trial's cache pattern | $2.33 | $15.99 | $31.62 |

- **Two reads.** After the owner's read, the agent read all 50 with the manufacturer strings beside each name and marked three more of Haiku's names wrong. So Haiku has at least 5 wrong, Sonnet 1, Opus 0 by both readers. Neither read is the release's (section 6).
- **Brands are the weak field.** A common Hebrew word as a brand: Haiku read "צאן" (sheep) as "Tzan" and "נשנושי" (nibbles) as "Nashnushi". A better-known brand for the one written: "Kinder" where the manufacturer field reads "קינד". A stated brand left out: Haiku four times, Sonnet at least six, Opus once.
- **Size, Opus.** Of 49 valid readings 16 agree with the registry's, 18 give none where it has one, 3 the reverse, 10 neither, and 2 differ, each a count against a weight (the tortillas' 6 against 390 g).

## 1. What the model writes

One reading per product. The code enforces the bounds, not the schema.

| Field | What it is | Bounds |
|---|---|---|
| `en` | The English name in natural word order: the brand in Latin letters when the input states one, what the product is (from general knowledge when the names do not say), the variant. Never a weight or a volume: the page shows the chains' own (`src/shopper/product.py:303`). A length stays ("14.4 cm"): the size reader reads no metres (`src/basket/units.py:40-41`). | 3 to 60 characters: unaccented Latin letters, digits, spaces, `% . , ' & / - + ( )` |
| `he` | Up to three everyday Hebrew names, each unlike every published name after normalising. | each 2 to 30: Hebrew or Latin letters, digits, spaces, `% . ' " +` |
| `brand` | The pack's brand as the input writes it, or empty. Never a guess, a better-known brand in its place, an importer or a parent company. A common Hebrew word is a brand only where the input shows it as one. | up to 30, of `he`'s set |
| `size` | The amount and unit the names state (g, kg, ml, l, units), or none. | a decimal string above zero, within `basket.units.bounded` (`src/basket/units.py:83-88`) |

**Given to the model:** a product's distinct published names and its manufacturer strings, placeholders dropped. Never the barcode, prices, or the size the code already reads: decision 13's size agreement would then mean nothing.

**Numbers (draft's call).** Every number in `en` must stand in the product's input, and a number followed by a weight or volume unit fails. So a count, a length or a percentage in a name is the chains' own.

**The count (agent's call; the conditions are the draft's).** When the registry's size is a weight or a volume and the model's `size` is a count, the code adds it to the shown name ("Whole wheat tortillas, 6 pack"): a whole number from 2 to 999 that stands in a published name and is not in the name already. The longer name must pass every check. Otherwise nothing is added, and the case is counted.

**Whole English (agent's call).** In the trial Haiku read a cut-off "שוואר" (shawarma) as sour cream, and Sonnet wrote "Candy gift set in shape of". The prompt asks for whole English, and a check drops a name that ends in a joining word such as "of" (draft's call).

**Brand** is checked three ways.

- *By code:* the brand is found in the input. That passes a common word, and cannot see a swapped or a dropped brand.
- *By a second model (decision 7):* Sonnet 5.5 reads every product too, and a product is held when both models name a brand and the two differ. In the trial Sonnet's and Opus's brands differed on 12 of 50 products: on 10 Sonnet left out a brand Opus gave, on 1 the reverse, and on 1 both named the same brand in two scripts ("MAM", "מאמ"). Only that last kind is held: at 1 in 50, about 500 products, though 50 products place it anywhere from about 90 to 2,600. The rule cannot catch a brand Opus invents where Sonnet gives none; Opus invented none in the trial, and the read of 200 marks every brand. (Haiku's and Opus's brands differed on 15 of 50, seven of the trial's eight brand misses among them, most of them Haiku's.)
- *By the readers:* the read of 200 marks each brand right, a common word, another brand, or left out. A swapped or invented brand makes the name wrong.

**Size** is compared with the registry's (`Covered.size`, `src/shopper/history.py:151`), a count against a weight kept apart from a real difference. On 18 November 2026 the registry had 18,789 products in grams or millilitres (one kind there), 962 in units, 5,320 with none.

## 2. The batch

One command on the Mac, by hand. It picks the products to read, sends Message Batches [S3], checks every answer (section 3) and writes a release's files (section 4). Uploading is a separate step, on the owner's go.

**Where the code lives.** The names file's schema, its check and the page rules are plain code inside `src/shopper`: the build runs them, and the function's zip is `src/` alone (`template.yaml:576`, `:591-592`). The prompt, the API client and the command live outside `src/`, whose fingerprint goes into each day's frozen forecasts (`src/basket/record.py:168-171`) and must not change with a prompt. A test holds that nothing under `src/` imports the SDK.

**The input snapshot (draft's call).** No reader today holds a product's inputs over time: the registry replaces a store type's earlier name with its later one (`src/shopper/history.py:309-316`), and the price reader keeps no manufacturer field (`src/basket/pricefile.py:34-43`). So the batch keeps a file of its own: per product, every name and manufacturer string a reading has seen, each with its day and chain. A run adds what the day's registry and price files hold that the snapshot lacks, compared after normalising. Nothing leaves by itself, so a day with a chain's files missing changes nothing. A corrected or hostile value leaves by the owner's command, which the record logs.

**Which products.** Those with no reading, and those whose snapshot grew. A reading carries four fingerprints: its input, the prompt, the schema and the model. A run whose prompt, schema or model differs from the last release's is refused unless told to read everything again, so no release mixes two prompts' readings.

**The manufacturer strings** come from the batch's own reader over a day's synced price files, built on `pricefile.bodies` and `parse_events` (`src/basket/pricefile.py:51`, `:75`); the price reader does not change. It takes the tags `ManufactureName` and `ManufacturerName` (`docs/portals.md:36`), joins rows by `basket.barcode.normalize` (`src/basket/barcode.py:17-26`), and drops and counts a tested list of placeholders ("לא ידוע", "Unknown", "כללי", "משתנה").

**A request** holds one product, with the barcode as its `custom_id` and never in the input, so a hostile name can touch one reading only. The shared instructions are cached for an hour and effort is low, as in the trial. It sets no sampling parameter and no `thinking` field: Opus 5.5 always thinks adaptively and refuses "disabled" [S6] [S8]. The answer is the block of type text [S8]. `max_tokens` is 1,024 (draft's call), ten times Opus's longest answer in the trial. A refused or cut-off answer gives no reading.

**The ceiling.** `max_tokens` is a hard limit on thinking plus text [S8], and the only bound on a request's cost. Token counting is free, counts input only, and is an estimate [S9]. So the command reserves for each request its full `max_tokens` of output, and its counted input plus 5% at the one-hour cache-write price. It never sends a slice whose reserve passes what is left of `--max-usd`, sends the next only after the last one's usage is recorded, and stops if under half the input came from the cache. The reserve is about $0.018 a request: about 4,200 products in a first slice under $75, about eight slices for a full run.

**The record** keeps what reproduces and prices the run: the commit, the hashes of the lock file, snapshot, prompt and schema, the arguments, seeds and batch ids, the API version, and each answer's `model`, tokens, dollars and workspace.

## 3. Untrusted text, both ways

**Into the model.** A chain's name is data: a JSON value in the user turn, never part of the instructions. The guarantee is in code. A schema sent raw cannot carry a number's bounds, a string's length, or an item count past a minimum of 0 or 1: each returns a 400 [S7]. So every answer passes the project's own check: section 1's bounds and rules, no `<` or `>`, no control character, no web address, and the word rules below. A reading that fails is dropped whole and counted by rule; its product keeps published-name search.

**Onto the page.**

- The English name is escaped, in a span of its own, never the chains' (`CHAIN_SPAN`, `src/shopper/search.py:53`).
- The site check reads that span for markup, the banned phrases (`src/shopper/words.py:141-143`) and "we", "our" and "us", then cuts it out, as it cuts a chain's (`src/shopper/check.py:14-19`). So no phrase a page must carry can come from the model.
- The page's rules find a banned phrase even inside a word (`src/basket/check.py:64-66`), which would refuse "Breaded scampi" for "scam". In the model's span it must match whole words (draft's call). "US" still trips the pronoun rule; such a name is dropped and counted.
- One function applies these rules when the file is made, when the build reads it and in the site check, so a name the check would refuse cannot stop a morning.

**In the files.** A name that is searched and not shown is still public: CloudFront serves every object in the site bucket (`site-template.yaml:88-93`), the index among them. "Search-only" keeps a name off the pages, not out of the files. The reads' pages carry manufacturer strings, which the site never publishes, so they are built outside `site/`, which is all the upload walks (`src/basket/site.py:137-141`).

## 4. Where the files live, and how the site reads them

**A release.** A run's files go to the archive bucket under a new prefix: the names file, the input snapshot, the record, the gzipped raw answers and the scorecard, each put once under the ten-year lock (`put_record`, `src/collector/store.py:115-123`; the lock's arguments, `:171-180`). A locked put makes one object permanent, not a set complete. So one more file goes last, the release file. It names every file with its SHA-256, the schema's version, whether the names are on, whether they are shown or search-only, and the barcodes held back. The build reads nothing a release file does not name, so a stopped upload leaves nothing it can pick up. The Mac writes, as the owner's AWS user (as `scripts/sync.sh:25-37`); the build's function gains read access to the prefix only (`ReadArchive`, `template.yaml:620-629`).

**Changing a release** is a new release file over the same names file: a longer or shorter held list, shown after a passed read, or names off, which leaves the word index of published names. One wrong name is one more held barcode. Nothing is removed or replaced. Tuning runs stay on the Mac.

**The names file's contract** is the plan's schema, which settles at least these. JSON lines, one per barcode, sorted, none twice, after a first line with the schema's version, the registry day and the line count. A barcode the morning's registry lacks, or a line that fails its check, is skipped and counted. A bad first line, a wrong count or more than 1% of lines failing fails the release. Names off is the release file's word, never an empty names file.

**How the build reads.**

- A release's id is the Israel date of its upload, from an aware time, and a sequence number; the upload refuses an id not later than every stored one. The build takes the newest release dated before the day it builds, as it takes the registry (`src/basket/archive.py:227-239`), so a release counts from the morning after its upload.
- The site-day file names the release tried and the release used (beside `Inputs`, `src/shopper/siteday.py:91-95`), and leaves both out when there is none. A same-day rerun and a rebuilt past day use the release the day's file names.
- `scripts/sync.sh` fetches every release file and each release's names file, record and scorecard, never the raw answers. Today it fetches none of these (`scripts/sync.sh:49-67`).
- When the newest release fails (a file missing, a hash that differs, the contract broken), the build takes the newest earlier one that passes and alerts with the cause.
- When the prefix cannot be listed or read after the client's retries, the build goes on with published names only, alerts with the cause and records it in the site-day file (draft's call). The second review asked for a failed build there; a morning's prices outrank its names.

## 5. Search: today's lookup kept, a word index beside it

Decided by the owner on 2026-11-23 (decisions 11 and 12), after a throwaway measurement on the registry of 18 November 2026, run 23 November 2026. It built both indexes in Python and checked every search against a brute-force answer; it is not the site's code.

**Today's search stays unchanged:** its pieces (`src/shopper/search.py:89-107`; 210 files, 3.3 MB) and its lookup (`src/shopper/static/search.js:91-112`). Every product it shows, up to 50, is among the 50 shown. So a search of one-character words ("2 מ", seven products) and a match inside a word work as today, and barcodes take today's path (`src/shopper/static/search.js:277-282`).

**The word index** adds the products that search misses.

- *Names filed:* the published names, the model's names, and the registry's size in Latin letters, never shown: "80g" and "80ml" both, since the registry does not tell them apart, and from 1,000 also "1.5kg" and "1.5l". Counts are not filed.
- *Tokens:* each space-separated word of a normalised name, and each run of letters and digits inside one: "דאו.דריי" gives itself, "דאו" and "דריי".
- *A match:* every search word starts some token of the product, in any of its names. A one-character word filters and never picks a file.
- *Files:* every start of two or more characters of a token is a node. A node whose products fit `PIECE_MAX` (150,000 bytes, `src/shopper/search.py:45`) is one file, a leaf. A bigger node has a child for each next character. If it is a whole token of some product ("שוקולד", "milk") it also keeps every product, in parts, in the order a search of that word shows; if only the start of longer tokens ("שוקו"), its first 50.
- *Lookup:* a manifest lists every node, its product count, its parts and whether it is a whole token. Each search word of two or more characters walks it to a leaf, or to the big node where the word ends. The script reads the leaf with the fewest products; with no leaf, the whole-token node with the fewest; else the part-typed start with the fewest. A one-word search reads a big node's parts until it has enough; a several-word search reads them all.
- *A flagged list:* when every word of a several-word search is a part-typed start, only a first 50 is stored. The list holds valid matches and may miss others, and the page says so and asks for more letters.
- *An entry* is today's (`src/shopper/search.py:82-86`) plus the English name as shown, the model's names, the size words and a mark telling published names from the model's.

**The list shown.** Every product today's search shows, then the word index's best matches until there are 50, each product once, ordered by the first step that fits:

1. a name equal to the search;
2. the title (the longest name) starts with the search;
3. another name starts with it;
4. every word is a whole token of one name;
5. every word starts a token of one name;
6. the words are spread over several names;
7. today's match only: the search sits inside a name.

Within a step a published name's match comes before the model's. Ties end in today's order, the normalised title and then the barcode (`src/shopper/static/search.js:100-103`). When today's search alone fills the 50 the word index is not read, so a better match outside them does not show. The tokenizer and the ranking each exist in Python and in the script, held together by shared tests, as `normalize` is today (`src/shopper/search.py:5-10`).

**What the measurement found,** on three sets of names: the published names and size words; "realistic", with one of the trial's 50 Opus readings on each product (real bytes and words, but repeated, so common words pile up more than real names would); and "ceiling", each reading padded to section 1's longest.

| | Published | Realistic | Ceiling |
|---|---|---|---|
| Files | 1,797 | 5,721 | 7,613 |
| MB a day | 34.5 | 228.4 | 402.4 |
| Largest file, bytes | 149,999 | 149,999 | 149,998 |
| Lists that differ from brute force | 0 of 288,811 | 0 of 290,134 | 0 of 290,134 |
| Flagged lists, each of valid matches | 0 | 28 | 35 |
| Most word files one search reads | 5 | 8 | 14 |
| KB fetched typing a whole title: median, 95th, most | 167, 316, 495 | 233, 611, 2,485 | 274, 845, 3,835 |

- **Ranked.** The table's runs listed today's results first, unranked. Two ranked runs followed: published names in the owner's order, and realistic names with steps 2 and 3 as one step. Both kept their files and megabytes to within one file, with 30 flagged lists on realistic names. A ranked several-word search reads all of a big node's parts, so the tail grows: 167, 318 and 829 KB published; 233, 757 and 3,647 realistic. Today's search alone fetches 49, 119 and 132 KB. The ceiling was not run ranked.
- **Found.** No product today's search showed left the 50, on any search of any run. Other chains' names typed in full (25,639) reach the first 10 for 13,974 today and 25,533 ranked (99.6%). Titles typed in full (25,071): 25,058 today, 25,044 ranked; why 14 dropped was not examined.
- **Typing.** A product first shows after 3.54 typed letters on average, as today (4,000 titles). It reaches the first 10 after 5.66 in the owner's order on published names, against 5.92 today, and after 6.23 with steps 2 and 3 as one step, on either set.
- **Neighbours.** Of the products in today's first 10, 11.7% leave the ranked first 10 while a title is typed, and 0.7% for names typed in full. They stay in the 50.
- **On the wire (estimates).** The site compresses JSON (`site-template.yaml:77`); the largest word files gzip 6.3 times, one live piece 4 times. A whole title typed then costs about 37, 120 and 580 KB with ranked realistic names, against about 12, 30 and 33 today.
- **On the Mac.** The index built in 2 to 17 s in Python, and Node 24 filtered the largest file for a two-word search in 2.3 to 6.6 ms. The manifest was 27 to 104 KB.

**Not measured:** the site run on Lambda with these files (memory; build, check and upload time); a phone; real model names over the whole registry; the owner's order on realistic and ceiling names. The plan's first task measures these on Lambda (section 11). Today's margin: on 15 November 2026 the site run took 199.6 s of its 900 and 1,681 MB of 3,008 at 15 days of history, and an earlier estimate reached 700 to 770 s at 91 days (`docs/operations.md:577`, `:581`; `template.yaml:584-586`).

**Publishing (draft's call).** Today one pool uploads data and pages together (`src/basket/site.py:144-151`). The word index's files go up first, in a call of their own, and the manifest last. The script falls back to today's list when a word file is missing or unreadable. Keys are fixed, as today's pieces', under a lifecycle rule of the same kind (`site-template.yaml:36`) (owner, 2026-11-23). A folder for each build would keep two days' files from ever mixing, but it needs a rule that removes current files, and the site bucket's rules expire only earlier versions (`site-template.yaml:26-37`).

**First and alone.** The word index deploys with published names only, before any model runs: the baseline with no model, live. That is a deployment, not the launch (decision 8): the site stays `noindex` (`src/shopper/shell.py:76`) and unshared until the AI names are on it, since the launch post's readers search in English and every published name is Hebrew.

## 6. What a shopper sees

- **The bar** is decision 6. Fifty names cannot bound the rate: zero wrong in 50 fits a true rate of up to 5.8% (a one-sided 95% bound).
- **The read (draft's calls).** 200 products drawn plainly by seed from the frozen prompt's full run, none a trial or tuning product, none held. Each shows as its page will, beside its published names, manufacturer strings and `brand`. Each reader marks alone: wrong, missing, a guess or style; the brand, as section 1 says; and whether the name adds a kind the names do not state. Wrong means the name says something the product is not. The owner settles marks that differ, and the scorecard gives both readers' counts and the settled one.
- **The pass mark** (owner, 2026-11-23): at most 4 wrong in 200, counting only names that say something the product is not; missing details and guesses are counted and printed, with no limit of their own. A pass fits a true rate of up to 4.5%, about 1,100 names. A failed read leaves every name search-only until a fixed prompt passes a fresh 200. A pass still bounds little, so a wrong name stays cheap to take off (section 4).
- **The review list** (decision 7). A held product is found through its model names and shown without them. The list is a local page: names, manufacturer strings, both brands, the English name. A reviewed product leaves by a new release file. The launch waits until the list is cleared (decision 18).
- **Product page.** Under the names as listed (`src/shopper/product.py:284-291`): the English name in its own span, labelled "English name written by AI", outside every store type's part, never the tab's title.
- **Search results.** A matched English name shows under the chain's, with "in English, by AI". A held or search-only product shows the chain's name alone.
- **Everyday Hebrew names** are searched and never shown (draft's call). While tuning, the report lists every result found only through one, so a wrong one can be held back.
- **Method page.** The scorecard and three counts (covered products, with a reading, without), built each morning from the release's scorecard (`render_method`, `src/shopper/pages.py:793-806`). Its words must clear the site's banned phrases.
- **Alerts (draft's call).** One line in the run's alerts on the morning the count without a reading first passes a limit the plan sets, and whenever the count with a reading falls from the day before.

The exact words are the plan's. The owner reads the built pages before merge.

## 7. The test searches

Both sources are drawn by seed from one recorded registry day. The trial's 50 products are left out: their answers were read, and that changed the prompt (draft's call).

**Source 1, other chains' wording.** 500 products with two or more names. Each name that is not the product's longest is one search, as published: about 1,000. The word index with no model already puts 99.6% of such names in the first 10 (section 5). So this source can only show harm: a model's names pushing the right product out.

**Source 2, shopper-style.** 300 other products, 100 from each of three bands by how many of the nine store types list the product (1; 2 to 4; 5 to 9). Three searches each: short everyday Hebrew, Hebrew with the brand or the variant, English. Written as people type, never copying a listed name.

**The owner's session in Cursor.** The owner picks Grok 4.7 by name and runs the plan's prompt over the sample, in six files of 50. Grok 4.7 is not Claude, and Cursor's Plus plan and up include it; Plus has no other vendor's models and no Auto mode [S10]. The model as shown, Cursor's version and the date are recorded. Where Cursor cuts a long answer off is not known, so the loader takes a file only with exactly its 50 sampled products, three searches each and nothing around the JSON, and records its hash. A file that fails is run again in smaller pieces before the freeze. Once accepted, the answers are never written again. Optional: the owner's yes or no, "would someone type this?", on 30 tuning searches.

**The split** is by product, never by search, inside each source and band: half for tuning, half held out (decision 13). Source 1: 250 and 250. Source 2: 150 and 150. The second version's 100 and 200 changed the owner's half without the owner's word, and is withdrawn.

**The test's freeze.** Samples, searches and split are one file, put once in the archive under the lock, its SHA-256 committed, before the first tuning call. The prompt's freeze comes later (section 8).

## 8. Scoring

**The live table.** Three rows on the held-out searches, over the whole registry. A: today's search. B: A with the word index of published names, the baseline with no model. C: B with Opus's names from the full run.

**Row A** runs from a checkout of commit 7ff9faf against the frozen inputs, not from a copy of old code. The scorecard names that commit and the commit that scored. A test holds the new search's first step equal to row A's lists.

**Columns.** Source 1; source 2 by style and band, with a total weighted by the bands' share of the registry. A cell is hits over searches, with its count of products and an interval from resampling products, since a product's three searches fall together. Beside it: the first 1 and the first 3 for English, and anywhere in the 50 shown. With 150 held-out products a source-2 share is good to about 8 points either way at best. A band-by-style cell rests on 50 products, about 14 points, and is description only. Every miss is printed with its cause.

**No held-out score chooses anything.** Opus was picked from the trial's reads, before a held-out score existed.

**The comparison rows (decision 5; their form is the draft's).** Haiku 5.5 and Sonnet 5.5 each read a 3,000-product sample once: the 800 test products and 2,200 more by seed. Each is scored beside Opus's names on the same 3,000, over the whole registry's published names. English searches there meet about 12% of the live crowd of English names, hence the first 1 and the first 3, and the table's label: a comparison on a sample. The owner approved this sample on 2026-11-23 as the way to choose the model; the pick overtook that use.

**Tuning** uses the tuning half only and reads only its products, with Opus. The prompt freezes before the full run. After that a changed prompt means a new full run and a fresh read.

**The held-out half** is scored when everything is frozen. Looking spends it. A locked object cannot grow (`src/collector/store.py:176`), so each scoring writes one locked record under a key of its own, and the scorecard gives their count.

**Run to run.** The same request can give another answer, and no sampling parameter can be set. So Opus reads the held-out products three times. The first reading is named, before any score is seen, as the one scored and the one that goes live. All three scores are shown.

**Also on the scorecard:** the searches only one of two rows found; the read of 200, names that add a kind counted apart; the brand counts, the review list's size and the size table; readings dropped, refused, cut off; the full runs' measured cost, Opus's and Sonnet's as the second reader, and Haiku's, projected and labelled so; the model that wrote source 2; that all three models are one vendor's. Every miss goes in a document in this repository. The README's copy is updated by hand at each release.

## 9. The key and the spending cap

- **A workspace of the project's own** in the Claude Console, with its own monthly limit and API key [S4] [S5], set up by the owner on 2026-11-23. An organisation limit would cap every workspace of the account (agent's call).
- **The amount:** $75 for the month of the build (draft's call), $35 a month after (owner, 2026-11-23), both until the first full run shows the real cache share. $35 covers a month of Opus and Sonnet with no cache hit, $31.10; the second version's $10 did not. A second full run in the build's month needs the owner to raise the limit. A batch "might go slightly over" a workspace's limit [S3], hence `--max-usd` and the reserve.
- **The key (draft's call)** stays in the Mac's login keychain, and the command clears every `ANTHROPIC_` variable from its environment first, as the trial did.

## 10. Cost

**Batch prices per million tokens** [S1], read 2026-11-23, half the standard ones, under default routing. Opus 5.5: $2 in, $10 out, $0.10 for a cache read, $4 for a one-hour cache write. Sonnet 5.5: $1, $5, $0.05 and $2. Haiku 5.5, for prompts up to 100,000 tokens: $0.05, $0.25, $0.005 and $0.10.

**Runs,** from the trial's means: 1,678 cached tokens and 69 more of input a product, and each model's output. First at the trial's cache pattern, 94% of input read from the cache and 2% written; in brackets, no cache hit at all.

| Run | Products | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| Full | 25,071 | $31.62 ($192.41) | $15.99 ($96.38) | $2.33 ($6.25) |
| The sample, once | 3,000 | $3.78 ($23.02) | $1.91 ($11.53) | $0.28 ($0.75) |
| A month | 2,700 | $3.41 ($20.72) | $1.72 ($10.38) | $0.25 ($0.67) |

**A month** is the 341 products that joined the registry between 10 and 18 November 2026 and the 390 whose names changed, scaled up.

**The build, once,** at the trial's pattern: about $10 of tuning (20 passes of the 400 tuning products), $31.62 for the full run, $1 for two more readings of the 400 held-out products, $2.19 for the comparison rows: about $45. Sonnet's brands on every product (decision 7) add $15.99: about $61. The reserve stops a run long before the full run's $192 with no cache hit.

**Each month after,** about $6 expected: $3.41 of Opus, $1.72 of Sonnet as the second reader, and about $1.10 of S3 for the index (5,721 files rewritten each morning, old versions kept 30 days, at the prices in `docs/collector.md:114-115`). About $33 at the high end: no cache hit all month ($20.72 and $10.38) and the index at its ceiling ($1.60). A release's files in the archive are a few tens of megabytes by estimate (UNVERIFIED), under a cent a month at that size. Not estimated: CloudFront's requests and bytes, which grow with visitors; this repository holds no price for them (UNVERIFIED).

**Still estimates:** the cache share at full size (measured on batches of 50; best-effort in a batch [S3]); the final prompt's tokens; the month's re-reads.

## 11. What the plan holds

The plan's first task builds the word index inside the site run on Lambda, measures what section 5 could not, and reads the result on a phone. The design is confirmed or changed on those figures before any other task. Then, each step on the owner's go: the test searches and their freeze; the word index, deployed and scored as row B; the batch and the prompt; the full run; the read of 200 and the review list; the names on the site; the launch.

The plan also holds: a rehearsal, against a test store, of a stopped upload, a held name, names off and a return to an older release; the tests (test-first; recorded model answers, never a live call or the network; fixed aware times; the new folder on the test path and in both workflows' coverage at the 95% floor (`pyproject.toml:8`, `.github/workflows/ci.yml:23`, `.github/workflows/mutations.yml:32`); a planted bug for every rule; a fresh review before anything ships); the SDK and all it pulls pinned, each at least a month old; every name; the prompt's wording; and the files and docs that change, `docs/site-look.md` and the runbook in `docs/operations.md` among them.

## Open questions for the owner

None. The last one, whether the launch waits until the review list is cleared, is answered: it waits (decision 18, owner, 2026-11-23). That is about 500 reviews before the post, at the trial's rate of 1 in 50 (anywhere from about 90 to 2,600), each one look at a local page with both brands, the names and the manufacturer strings.

The owner's answers of 2026-11-23 to the second model (Sonnet, held when both name a brand and they differ), the pass mark (at most 4 wrong in 200), the index's keys (fixed) and the monthly cap ($35) are in the decisions above.

## Calls made in this draft (the owner can overturn any)

Most are marked where they apply. Also this draft's, unmarked above:

- **Standing from the earlier versions:** one product a request; the archive bucket, where nothing is removed; three readings, the first named live; six files in Cursor.
- **New:** a brand needing the input's evidence, which rewords the agent's "a common Hebrew word is never a brand"; the checker inside `src/shopper`; four fingerprints and the refused run; the reserve; the placeholder list; the release file, its held list and its ids; the contract's 1%; the tokenizer and the ranking in two languages; the loader's checks; row A from a checkout; one locked record a scoring; intervals by resampling; tuning with Opus.

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

The figures of 18 November 2026 come from that day's synced registry, the trial's from each answer's own token counts, and section 5's from the throwaway measurement, not built code.

## Resolved review findings

Two outside reviews, each checked finding by finding against its source before the next version. Where a finding held only in part, the checked fact is in brackets. A fate names whose call a decline is.

### The first review (of the first draft)

6 critical, 11 significant, 3 minor and 3 small findings, and 22 on direction: 45. Checked: 27 confirmed, 14 in part, 4 could not be checked, none wrong. Ids are the review's.

| Id | Checked | Fate in this version |
|---|---|---|
| C1 | Confirmed | Folded (section 2): no sampling parameter, no `thinking` field, the answer is the block of type text. |
| C2 | Confirmed | Folded (section 7): Grok 4.7, picked by name; no Auto. |
| C3 | Confirmed | Folded (section 3): the check reads the model's span, then cuts it out; banned phrases match whole words there. |
| C4 | In part (a rebuilt past day already needs `--revise`; the gap was a same-day rerun after an upload) | Folded (section 4): a release counts from the morning after its upload, and the site-day file names it. |
| C5 | In part (the test path is `pyproject.toml:8`; packages pulled by others are unpinned project-wide) | Folded (section 11): the test path, both workflows' coverage and the mutation check; the SDK and what it pulls pinned. |
| C6 | Confirmed | Folded (section 1): 18,789, 962 and 5,320. |
| S1 | Confirmed, as a projection | Replaced by section 5's measured scheme: every file under the limit at the bounds' ceiling. |
| S2 | Confirmed | Replaced by section 5: the manifest tells a leaf, a whole word and a part-typed start. |
| S3 | In part ("1.5l" and "80g" always fail; a bare "1.5" can match) | Folded (section 5): size words in Latin letters; a search's words may sit in different names. |
| S4 | Confirmed | Replaced by section 5: the owner's ranking; today's search kept, so one-character searches work as today. |
| S5 | Confirmed | Folded (section 10): every figure from the trial's tokens. The first draft's $74 to $158 and the review's $180 to $248 for Opus both rested on a guessed 250 output tokens; Opus wrote 82. |
| S6 | Confirmed | Folded (sections 2 and 10): the input snapshot; the month's cost counts the products whose names changed. |
| S7 | In part (its 1.6 to 2.1 GB rested on guessed multipliers) | Replaced by section 5's measured 228 MB a day; raw answers gzipped and never synced. |
| S8 | In part (no word passes the limit in a 3,000 sample; Cursor's cut-off is unchecked) | Folded (sections 7 and 8): six files, each checked by the loader; the sample inside the whole registry's index; the first reading named live. |
| S9 | In part (every response carries the workspace header, batch creation too) | Folded (sections 2 and 9): the limit on the workspace; every `ANTHROPIC_` variable removed; the workspace in the record. |
| S10 | Confirmed | Folded (sections 1 to 3): bounds in code; the amount a decimal string above zero; `+ ( )` allowed; `he` compared after normalising. |
| S11 | In part (the memory a changed reader would cost is unmeasured) | Folded (section 2): the price reader stays; the batch has its own. |
| M1 | Confirmed | Folded (sections 4, 6 and 11): names off leaves the word index; the method page clears the banned phrases; the plan lists the files. |
| M2 | Confirmed (why the counts differ is unchecked) | Folded: the 13,507 figure is cut; the trial's brand counts carry the point. |
| M3 | Confirmed | Not met: see M12 of the second review. |
| N1 | Confirmed | Folded: the script's full path throughout. |
| N2 | Confirmed | Folded (section 4), corrected again by the second review's M8. |
| N3 | Confirmed | Folded: no word is dropped, so no message for one. |
| D1 | Could not be checked | Kept (owner, 2026-11-18): release 2 needs the names first. |
| D2 | Could not be checked (its latency figures have no source) | Kept (owner, 2026-11-18): the catalogue changes slowly, and a static build needs no key and no endpoint. |
| D3 | In part | Declined (agent): the field stays. In the trial 35 of 50 products had no brand without it, 25 with it. |
| D4 | In part | Declined (draft): 50 size differences classified by hand; the table splits a count against a weight by code. Its larger held-out part was folded, then withdrawn (S13 of the second review). |
| D5 | Confirmed | Kept, as the review advised: one vendor's models, and the scorecard says so. |
| D6 | In part (its held-out-name figure is 33.0%, not 27.3%) | Folded: source 2 at 300; source 1 named the no-harm check. Declined by the owner, twice (2026-11-23): hand-written searches. The owner's call; no reason beyond it is recorded. |
| D7 | Could not be checked | Folded and raised (owner, 2026-11-23): a read of 200 by two readers, since 50 cannot bound the rate. |
| D8 | Confirmed | Folded (section 8): the sample inside the whole registry's index; the first 1 and the first 3 for English. |
| D9 | Confirmed | Kept. The trial was the measurement it asked for. |
| D10 | Confirmed | Kind dropped (owner, 2026-11-23). Declined (draft): a grams-against-millilitres table; splitting them is a non-goal, and the readings keep the unit. |
| D11 | Confirmed | Folded (section 6): the counts on the method page, and now an alert on a limit. |
| D12 | In part | Overtaken: Opus ships, and Haiku with thinking off is not compared (D19 of the second review). |
| D13 | In part (its "$22 packed" is wrong: at the first draft's guessed 250 output tokens a packed Opus run is about $73, output alone $62.68) | Kept (draft): one product a request, the barcode out. At the measured 82 tokens the full run is $31.62. |
| D14 | Confirmed | Kept, then split by the second review's C4: the caller outside `src/`, the checker inside. |
| D15 | Confirmed | Folded (section 4): tuning runs stay on the Mac; raw answers gzipped. |
| D16 | Confirmed | Folded (section 8), and made exact by the second review's S12. |
| D17 | Could not be checked | Folded: tuning lists results found only through a model's Hebrew name. Declined (draft): a "matched" note on the page, a second kind of AI text to gate. |
| D18 | Confirmed | Folded (sections 2, 9 and 10): the limit on the workspace; the ceiling from the reserve; $35 a month (owner). |
| D19 | Confirmed | Folded (section 2): four fingerprints; everything re-read only when told. |
| D20 | In part (the widely sold band is over-weighted, not under; its power figure does not reproduce) | Folded: 300 products, cells by band, a weighted total. Three readings kept for the model that ships. |
| D21 | Confirmed | Done: the trial, $0.10 in all. |
| D22 | In part | Folded: Latin size words; kind dropped. Declined (draft): checking the fields against release 2's lists now; a full re-read costs about $32. |

### The second review (of the second version)

6 critical, 20 significant, 14 minor and 4 small findings, and 24 on direction: 68. Checked: 50 confirmed, 12 in part, 6 could not be checked, none wrong. The review numbered only its direction findings; the others are numbered here in its order.

| Id | What it said | Checked | Fate in this version |
|---|---|---|---|
| C1 | Section 5 defined no complete lookup over several files | Confirmed | Folded (section 5): the manifest, the lookup and the flagged list; every list equal to brute force in about 290,000 lookups a run. |
| C2 | Searches that work today would break | In part (one-character searches found nothing; its two punctuation examples still worked) | Folded (section 5): today's search runs unchanged; tokens include the runs inside a word; one tested tokenizer. |
| C3 | The spending ceiling was no ceiling | Confirmed | Folded (section 2): the reserve at full `max_tokens` and the cache-write price; one slice at a time; `max_tokens` 1,024. |
| C4 | The shared checker sat where Lambda cannot import it | Confirmed | Folded (section 2): the checker in `src/shopper`, the caller outside, a test that `src/` imports no SDK. |
| C5 | A release was four separate puts | Confirmed | Folded (section 4): the release file, put last; nothing else is read. |
| C6 | The scorecard was never synced | Confirmed | Folded (sections 4 and 8): the sync fetches each release's files but the raw answers; the README is updated by hand. |
| S1 | No entry layout and no full ranking rule | Confirmed | Folded (section 5): the entry marks published from model names; seven steps, then today's order; one ranking function. |
| S2 | An upload can leave a mixed index; unused keys stay | Confirmed | Folded in part (section 5): files first, the manifest last, a fall-back. A folder a build declined by the owner: fixed keys, as today's pieces. |
| S3 | The size projection was too thin for a plan | Confirmed | Folded (sections 5 and 11): the whole-registry measurement. Lambda and a phone are the plan's first task. |
| S4 | Faults treated alike; release dates loose | In part (pinning a past day was already stated) | Folded (section 4): four cases told apart and recorded; ids from aware Israel dates. Declined (draft): failing the build when the prefix cannot be read; prices outrank names. |
| S5 | No reader holds inputs that only grow | In part (a full re-read was already stated) | Folded (section 2): the input snapshot; four fingerprints. |
| S6 | No full contract for the names file | In part (the record already kept each answer's model) | Folded (sections 2 and 4): the contract's points; the record's added fields. |
| S7 | Counts and lengths could publish text no source states | Confirmed | Folded (section 1): numbers must stand in the input; the count's conditions; the final name checked. Declined (draft): a length field; the number rule covers lengths. |
| S8 | The brand rule and the hand count gate nothing | Confirmed | Folded (sections 1 and 6): the review list (owner); the read shows names, manufacturer strings, brand and English together; a swapped or invented brand is wrong. Declined (draft): an automatic English-against-brand flag; no code can tell "Kinder" from "Kind". |
| S9 | The trial's marks mixed two rubrics | Confirmed | Folded (the trial): the owner's marks and the second reader's, apart. |
| S10 | One wrong in 50 bounds little | Confirmed | Folded (section 6): 200 names, two readers (owner). Declined (draft): strata; a plain draw estimates the site's rate. The pass mark: at most 4 wrong in 200 (owner). |
| S11 | The held-out set chose the model | Confirmed | Folded (section 8): Opus picked from the trial's reads; no held-out score chooses; intervals by product. |
| S12 | Row A could not be both kept and re-scored | Confirmed | Folded (section 8): row A from a checkout of its commit; both commits named. |
| S13 | 100 and 200 changed the owner's half | In part (it was marked a draft's call) | Folded (section 7): halves restored. |
| S14 | Source 2's precision overstated | Confirmed | Folded (section 8): each cell's count and interval; band-by-style cells description only. |
| S15 | A locked log cannot grow | In part (the second version did not say the log was one object) | Folded (section 8): one locked record a scoring. |
| S16 | The launch decision was missing | Confirmed | Folded (decision 8; section 5). |
| S17 | The method page counted the wrong thing; no alert | Confirmed | Folded (section 6): three counts; an alert on a limit and on a fall. |
| S18 | The test rules were incomplete | In part (pins and CI wiring were there) | Folded (sections 2 and 11): recorded answers, fixed aware times, both workflows. |
| S19 | "Never shown" is not "not public" | Confirmed | Folded (section 3): said plainly; the read pages built outside `site/`. |
| S20 | The placeholder list was too small | Confirmed | Folded (section 2): the tags, the barcode join, a tested list, counts in the record. |
| M1 | Six files do not check Cursor's cut-off | Confirmed | Folded (section 7): the loader's checks. |
| M2 | "An item count returns a 400" overstated | Confirmed | Folded (section 3). |
| M3 | 1,686 was not the cached block | Confirmed | Folded (the trial): 1,678 cached, 1,686 counted, 69 a product. |
| M4 | The invalid counts were the old checker's | Confirmed | Folded (the trial's table): both counts. |
| M5 | "All succeeded" hid failed answers | In part (the table showed them) | Folded (the trial): 250 returned, 10 failed a check. |
| M6 | The size summary left out most outcomes | Confirmed | Folded (the trial): all five outcomes for Opus. |
| M7 | The thinking-off saving was rounded | Confirmed ($1.56; $1.48 at equal caching) | Cut with the comparison it served: Opus ships. |
| M8 | The lock's citation | In part (the arguments are at `src/collector/store.py:171-180`) | Folded (section 4). |
| M9 | The packed-request correction was left out | Confirmed | Folded (the first review's D13). |
| M10 | No API version; no price scope | In part (the 400 holds at any version) | Folded (sections 2 and 10): the price scope; the API version in the record. |
| M11 | Four rows did not fit two tables | Confirmed | Folded (section 8): three live rows; the comparison rows apart; projected costs labelled. |
| M12 | Still over its length aim | Confirmed | Declined in effect (draft): the model comparison and request mechanics are cut, but the folds above add more than they save. This version is longer than the second, most of it section 5's measured figures, the release's contract and the open questions. |
| M13 | Five declines lacked a reason | In part (two had one) | Folded (the first review's table): each decline gives its reason and whose call. |
| M14 | The monthly cost was incomplete | Confirmed | Folded (section 10): expected and high totals, and what is not estimated. |
| N1 | "An eighth" | Confirmed | Folded: about 12%. |
| N2 | "$0 word index" | Confirmed | Folded: "with no model"; its S3 cost is in section 10. |
| N3 | "Pass" and "freeze" each named two gates | Confirmed | Folded: the trial's reads, the read of 200, the test's freeze, the prompt's freeze. |
| N4 | Causal wording for one pair of runs | Confirmed | Folded (decision 3): "supports keeping it", "in one pair of runs". |
| D1 | The free index as its own release | In part (it already deployed first) | Kept: deployed first, scored as row B. Declined by the owner (2026-11-23): a launch on it alone. |
| D2 | Gate the launch on measured quality | Confirmed | Declined by the owner (2026-11-23): the launch waits for the AI names; the post's readers search in English. |
| D3 | Keep the offline batch | Confirmed | Kept. |
| D4 | Opus now | Confirmed | Folded: Opus ships (owner, 2026-11-23); Haiku and Sonnet as comparison rows (agent). |
| D5 | Keep kind out | Confirmed | Kept (owner). |
| D6 | Add 60 hand-written searches | Confirmed | Declined by the owner, twice (2026-11-23). Folded: an interval for every cell. |
| D7 | Split search names from shown text | Could not be checked | Declined: decision 9 is the owner's. Folded: the read counts names that add a kind apart. |
| D8 | 200 stratified, a second reader | Confirmed | Folded (owner): 200 names, two readers. Strata declined (S10). |
| D9 | An elimination round, then a full comparison | Confirmed | Folded: the trial eliminated; the live table is the whole registry. Sonnet reads the whole registry for the second brand (owner). |
| D10 | Production grade, with temporary tools allowed | Could not be checked | Kept: the grade is the owner's, one for the release. The scorecard is public evidence, so its code is tested as the rest. |
| D11 | Source-stated counts and lengths | Confirmed | Folded (S7). The agent's calls to keep both stand. |
| D12 | Evidence rules and a review queue | Confirmed | Folded (sections 1 and 6): the review list (owner); a brand needs the input's evidence. |
| D13 | Measure the search scheme first | Confirmed | Done: section 5 is the measured scheme. |
| D14 | Keep the word index first; say it is not the launch | Confirmed | Folded (section 5). |
| D15 | A release manifest | Could not be checked | Folded (C5). Its rehearsal is the plan's (section 11). |
| D16 | The checker inside `src/` | Confirmed | Folded (C4). |
| D17 | The caps | Confirmed | Folded (section 9): $35 a month (owner), above the no-hit month; both amounts until the full run's figures. |
| D18 | Current plus last-known-good inputs | Could not be checked | Folded in part (S5). Declined (draft): removal rules that run by themselves; the replay they need has not run, and a value leaves by command. |
| D19 | Read Haiku with thinking off | Confirmed | Declined (draft): Opus ships, and no read of those names would change that. |
| D20 | Threshold alerts | Could not be checked | Folded (S17). |
| D21 | One product a request | Confirmed | Kept. A full run fits one batch's limit of 100,000 requests [S3]; the reserve splits it anyway. |
| D22 | Keep the manufacturer field, with provenance | Confirmed | Kept (S20); the snapshot keeps each value's day and chain. |
| D23 | An owner checkpoint over the drift | Confirmed | Done: the owner's decisions of 2026-11-23. The calls left are listed for this read. |
| D24 | Five measurements before the plan | Could not be checked | The search measurement is done. Declined: the thinking-off read (D19) and the Grok-against-human check (D6). The brand audit becomes the review list. The input replay has not run; the first month measures it. |

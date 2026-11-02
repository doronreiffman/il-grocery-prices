# q13 research (2026-11-02): the headline basket

Two research agents, 2026-11-02. (1) A digest of the q19 notes (flights-archive `.remember/q19/`: STATE.md, supermarket/access-and-law.md "AL", data-sample.md "DS", prior-art.md "PA", ideas/five-second-wow.md "FSW") and this repo's docs. (2) A measurement on every PriceFull file of 2026-11-02 (814 files, 370.5 MB, read-only from the archive; 730 analysed, the latest file per sub-chain + store; sha256 = manifest for all; no DOCTYPE/ENTITY). Working copy (raw rows, never published): scratchpad `grocery-2026-11-02/` of session e0b3ee41 (temporary).

## May derived comparisons be published?

- s.30(ה) (AL §2, checked 2026-10-31, Hebrew Wikisource revision 3025772 of 2026-07-21, https://he.wikisource.org/wiki/חוק_קידום_התחרות_בענפי_המזון_והפארם): "כל אדם רשאי לגשת לפרסום, למידע ולנתונים הכלולים בו לפי סעיפים קטנים (א) ו־(ד), ולהשתמש בהם, באופן חופשי ובלא תמורה, לצרכים פרטיים או מסחריים; ...". A Wikisource copy, not the official text; changes after 2026-07-21 UNVERIFIED.
- s.30(ב): the files exist to allow "השוואה עדכנית שוטפת של מחירי מצרכים וסלי מצרכים" across large retailers. Reg. 4(2): "כל גולש יוכל לשלוף כל קובץ באופן שוטף".
- No duty on a reuser found (credit, accuracy, timeliness bind the retailer; AL's reading). "Credited to the chains' published files" is this project's own rule.
- Risk: misleading use. The Authority's spokesman (Globes via N12, 2025-12-16, secondary): "מי שישתמש במידע באופן מניפולטיבי, יהיה חשוף לתביעות הטעיה גם מצד הציבור וגם מהרשתות הקמעונאיות". Naming a chain "cheapest" is not addressed beyond that.
- The five chains' portals show no terms (curl scans 2026-10-31). Nibit/laibcatalog (Victory, H. Cohen, Mahsanei HaShuk) claims the price list: those chains are out of v1.
- Not read: amendments after July 2026, the official law text (Nevo 403), the economy.gov.il regulations PDF, the Authority's 2025 report.
- Approved-apps list (gov.il cpfta_apps, 2021): voluntary, not a licence; Pricez, MySupermarket, CHP.

## What one day's files support (measured, 2026-11-02, Monday)

| Chain | Stores | Items/store median (min-max) | Barcode share | Weighted |
|---|---|---|---|---|
| Shufersal | 416 (incl. Online 413) | 5,446.5 (1,672-15,833) | 99.9% | 5.4% |
| Rami Levy | 96 | 13,001 (2,703-14,881) | 98.5% | 4.0% |
| Osher Ad | 24 | 6,354 (5,944-6,747) | 99.9% | 7.9% |
| Carrefour | 147 | 8,202 (2,628-12,505) | 95.0% | 4.8% |
| Yochananof | 47 | 10,934 (3,778-12,101) | 95.2% | 6.8% |

- Barcode rule: GS1 check digit at 8/12/13/14 digits (11-digit codes get a leading zero), at least 8 significant digits; matched with leading zeros stripped. `ItemType` is useless (Rami Levy sets 1 on everything; Carrefour sets 1 on 36,301 rows that fail the check digit).
- Overlap: union 70,604 barcodes; all 5 chains 2,467; exactly 4: 4,241 (missing chain usually Osher Ad); 3: 5,079; 2: 7,777; 1: 51,040.
- "Safe basket" (all 5 chains and at least 80% of each chain's stores): 89. Shufersal is the bottleneck: its sub-chain 005 "Be" (97 stores, median 4,395 items) carries 12% of the all-5 set. Without Be (319 Shufersal stores): 629 at 80%, 356 at 90%.
- Within-chain spread on all-5 codes (median max/min across a chain's stores): Shufersal 1.382, Rami Levy 1.340, Osher Ad 1.084, Carrefour 1.403, Yochananof 1.144; within one Shufersal sub-chain 1.18-1.19. Across chains (chain medians) typical max/min 1.282. Carrefour's median is highest on 2,112 of 2,467 codes; Rami Levy and Osher Ad lowest on about 2,030 each. Shelf prices only, no promotions.
- Staples table (20 items, median [min-max] and stores carrying) is in the measurement agent's report of 2026-11-02; examples: Tnuva milk 3% 1L 7.20-7.35 everywhere; Bamba 80g 5.90 (Shufersal, Carrefour) vs 3.90-4.00 (the rest); Osem spaghetti 500g 7.90 / 4.90 / 4.90 / 7.50 / 4.90.

## Traps found in the data

- Names: 2,465 of the 2,467 shared barcodes are named differently across chains; Carrefour, Osher Ad, Rami Levy cut names at 20 characters, Shufersal's reach 40 (DS's "24" is out of date). Select and match by barcode, never by name.
- Sizes: of 1,499 shared barcodes with a readable unit in all 5 chains, only 927 (61.8%) agree on quantity + unit (84 differ only g vs ml; 488 in the number). UnitQty "לא ידוע" on 44.6% of Osher Ad rows. A basket item needs a size check.
- Produce: no shared code (tomato: 7290000000022 / 7290000000100 / 7290009000122 / 1501 / 725). No egg 12-pack in all 5.
- Stores: in 74 Carrefour files the StoreID inside differs from the file name; key stores by the file name. Rami Levy republishes PriceFull hourly for many stores (store 732: 9 times): take the latest per store.
- Outliers: Shufersal tomato 7290000000015 at ₪10,000 in one store; ₪0.01 rows (Carrefour 338, Rami Levy 279; some real foods). Duplicates: Carrefour 001-221 lists 22 codes twice (same price).
- Thin stocking: some all-5 staples sit in few stores of one chain (eggs ×18 in 1 Rami Levy store; Coca-Cola 1.5L in 44 Shufersal stores).
- Osher Ad's files appear after its 06:48 run (QUEUE q12).

## Prior art (PA)

CHP (by area, 85% coverage threshold, no method), Pricez (behind most press and Consumer Council baskets; no method found), MySupermarket, Salai (stale, 3 chains, ~40 items, no method), Smoody, super-mcp, israeli-prices, OpenIsraeliSupermarkets (non-commercial). Consumer Council (Sept 2025): 808 products, promotions in, credit-card deals out, 80% coverage, a missing item gets the others' average. Gap named in the notes: no daily basket with a written method, no published matching-accuracy score, no documented rule for the price after promotions.

## Open questions for the design session

- Which stores stand for a chain: all stores' median, one city, a format? Exclude Shufersal Be (a non-grocery format, UNVERIFIED) and Online?
- Basket size and selection: a fixed list of staples (by barcode), or "every product in all chains at 80% of stores" (89 / 629 without Be)?
- Promotions in or out for v1 (club and card limits sit only in the text; coupons out; "N for ₪M" needs a rule).
- Size check: drop a barcode whose quantity + unit disagree across chains, or show it?
- Wording: "listed price in the chain's file", never "you'll pay"; how to say "cheapest" without misleading; credit line; "as of" time.
- Whether to read s.30(ה) in an official copy (owner, in the browser) before publishing.

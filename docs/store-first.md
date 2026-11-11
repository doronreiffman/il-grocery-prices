# Store first: the verdict, the price chart and the store picker (design)

**Grade:** the public site's production grade, as for the shopper site: test-first, a mutation for every rule, a fresh review before merge, and the owner's read of the built pages before merge.

**Status:** approved by the owner 2026-11-11, after a builder check whose questions are folded in. It changes parts of [shopper-site.md](shopper-site.md), listed under "Changes to the shopper-site design". Everything there that this document does not change stands.

## Why

A shopper stands in a supermarket aisle holding a product with a sale tag. The question is the site's: is this actually a deal, or the price it nearly always sells at? The owner's words (2026-11-11): a promotion that is almost always on "is not a deal. that's the whole idea", and "most users will be at the store, not picking which store to go to".

So the site asks which store the shopper is in first, then answers per product with two things readable at a glance: the price history, and a verdict, "Deal" or "No deal", with the shekel saving and one line of measured reason.

## Goals

1. The store type comes first on every page, picked once and remembered in the shopper's browser.
2. Each product page answers for the picked store type: the verdict, the saving in shekels and one line of reason.
3. A price-history chart per store type: today's price against recent prices, and when it was last this low.
4. "How often it goes on sale" under the verdict, as measured counts.
5. Finding the product fast in the aisle: search first on the front page (a typed barcode already opens the product).
6. One front page per store type: search, a headline for that store ("At Carrefour Market today: 1,130 of 4,210 promotions are actually deals"; numbers made up for the example), then that store's deals, biggest saving first.
7. Every headline and label is what a shopper would say out loud; precision goes in the fold-outs and the method page.

## Non-goals

- Prices by branch. The records keep prices per store type, and for promotions only how many branches carry one, not which (owner, 2026-11-11: the picker is by store type).
- Tap or hover on the chart (owner, 2026-11-11: fine for version one).
- A camera barcode scanner (owner, 2026-11-11: a future change).
- Accounts, sign-ups, price-drop alerts.
- Where the forecast's odds show once they exist. The no-odds sentence moves into the fold-out; the odds' place is a later design.
- Any change to collecting or extracting.

## Anti-goals (a failure even if everything else works)

- A verdict for the wrong store read as if right. The store type's name is inside every verdict ("At Carrefour Market: DEAL"), so a pick left over from last week shows itself.
- "Deal" on a price the product sells at most days.
- A verdict that hides how little history it rests on.
- Colour as the only signal: the badge always writes the verdict and the shekels.
- Words or colours saying a chain did something wrong. "No deal" is neutral grey, never red, and no "fake" or kin.
- A fact that needs the script. Every price, verdict and chart is in the page's HTML and readable with the script blocked.

## The rules

Each rule is for one product at one store type (a "column", `shopper.columns.COLUMNS`: nine of them).

- **S0 Days tracked.** A day counts as tracked for a store type when both its prices and its promotions were read that day (not a promotion hole: the items report's `promo_hole`). A day with prices but promotions unread (for example Shufersal Deal on 2026-11-08: prices from 50 stores, no promotion files) is left out of S2, S6, S7 and every "days tracked" count, and is a gap in the chart, as P8 already leaves such days out of its runs.
- **S1 Day price.** For a tracked day: the lower of the listed price (the items table's `listed`: the median shelf price across the store type's stores, before promotions) and the lowest per-item deal price among that day's promotions that count (S3's filter). A day without the product listed has no day price. A day with a promotion on (`wide`, start ≤ day ≤ end) but none of its prices readable (`valid` false) is a sale day of unknown price: it has no day price, it counts as on sale in S7, and the chart marks it as on sale without a price.
- **S2 Usual price.** The median of the day prices over the days tracked (S0) in the 90 days before today (today excluded; the window the site already reads, `READ_DAYS`). With an even number of days, the higher of the two middle values, so a product on sale on exactly half the days keeps its shelf price as its usual price ("almost always on" means more than half the days; owner, 2026-11-11).
- **S3 Today's price.** The lowest per-item deal price (P4) among today's promotions that count: entries of the items table's `promotions` with `wide` true (carried by at least half the store type's counted stores, P3), `valid` true, and start ≤ day ≤ end. The same set the page shows as today's deal, club-only included, so today and the past compare like for like; a promotion's conditions (club only, buy 2) are named beside the verdict.
- **S4 Verdict.** Given only when the product has a promotion that counts today and at least one day price before today:
  - **Deal:** the saving, usual price minus today's price, is ₪1.00 or more (owner, 2026-11-11: "shekel savings matter more than percentages").
  - **No deal:** otherwise.
  - No verdict, a plain line instead: no promotion today ("No sale today"); the product first seen today ("New today: no price history yet."); a promotion at some stores only ("On sale at some stores only"); a promotion whose price could not be read ("On sale, but the sale price could not be read"); the store type's promotions not read today ("Sale prices could not be read today", beside P10's existing warning); sale days of unknown price (S1) on more than half the days tracked ("On sale most days; earlier sale prices could not be read"; owner, 2026-11-11, over calling it "No deal" or judging on the readable days alone).
- **S5 Shade.** Deal badges: ₪1.00 to ₪2.99 light green, ₪3.00 to ₪4.99 green, ₪5.00 or more deep green. No deal: neutral grey. Each shade checked for contrast in light and dark themes.
- **S6 Last this low.** Today's price for this rule is S3's when there is a promotion, else the listed price. The latest day before today whose day price is at or below it: "Last this low: 12 October, at ₪9.90." None in the window: "Lowest in the 10 days tracked."
- **S7 How often on sale.** Of the days tracked in the window, on how many a promotion was on (`wide`, start ≤ day ≤ end, its price read or not), and when the last sale before today's ended and at what price (the price left out when it could not be read): "On sale on 12 of the 60 days tracked. The last sale before this one ended 12 October, at ₪9.90." Days not tracked (S0) are not counted, which is why every count says "days tracked".
- **S8 Days tracked.** Every reason line names the number of days it rests on, so a short history shows (owner, 2026-11-11: "call it a deal but be honest about lack of data").

**The front page's list (per store type).** A product is listed when its verdict there is Deal and it passes the existing bar: at least `MIN_FRONT_DAYS` (20) days with records in the last `RECENT_DAYS` (30) (`shopper.measures.on_front`'s window test). Sorted by saving in shekels, largest first; the top 100 shown, the rest reached through search and browse. The headline counts the same set: N is the listed products, M the products with a promotion that counts today and passing the 20-day bar. Until any product passes, the existing lead line stays: "None yet: a product needs 20 days of price history first."

## What a visitor sees

1. **The picker.** The first visit to any page, with no store type remembered, shows "Which store are you in?" and the nine store types grouped by chain (Shufersal Deal, Shufersal Express, Shufersal Sheli, Shufersal Universe; Carrefour City, Carrefour Market; Rami Levy; Osher Ad; Yochananof). Each is a link to that store type's front page. Whether shoppers know these names from the store signs is UNVERIFIED; the watched outsider sessions are where to find out.
2. **The header**, on every page: "Carrefour Market · change" once a store type is picked, "Pick your store" before.
3. **The root page** (`index.html`), also the portfolio's landing page: the site's name, the title question ("Is it actually a deal?"), one line on what the site does, the picker, and the links line kept from today's front page ("Built by …", "Code on GitHub"). With the script and a remembered pick, it opens that store type's front page; the header's "change" link reaches the picker without being sent straight back.
4. **A store type's front page**, in this order: the title and subtitle as today; the search box ("Type a product name or the barcode"); the headline; the two filters kept from today ("Hide club-only deals", "Hide deals with a minimum spend"); the deals list (product, badge with the condition beside it when there is one, today's price, usual price); the fold-out "How a deal passes" ("Promotions checked against what the product usually costs, sales included, over up to 3 months.", then the rules in shopper words, the one-deal story and the counts, now for that store type).
5. **A product page**, in this order:
   - the product's name and size, as today;
   - for the picked store type: the verdict badge ("At Carrefour Market: DEAL · ₪1.90 off"), the reason line, the condition if any, a coming sale when one is listed to start ("A sale starts on 14 November", today's F2 line in shopper words), the chart, "Last this low", "How often on sale";
   - the fold-out "How this is worked out": the store type's price range across its stores, how many stores list it, the listed-price definition, every promotion running today with its source labels, "at some stores" and the stores' range (today's full list), the fine-print warning, the no-odds sentence;
   - "Elsewhere today": one badge per other store type selling it ("Rami Levy · no sale today"). Tapping one shows its part on this page; the pick stays as it was.
6. **A product page with no pick yet** shows the badge row first, as the picker, sorted by saving, largest first, with the first one open.
7. **The picked store type does not sell it today:** "Not sold at Carrefour Market today", with the last day it was (today's Call 10 line: "last seen 3 November"), then the badge row.
8. **With the script blocked:** every store type's part is listed in `COLUMNS` order, as today, and the picker's links still reach each store type's front page.

## The chart

One per store type, in that store type's part of the product page; a fixed SVG, as today's `_chart`, drawn larger.

- Across: the days tracked in the window (S0), then today. Up: the price per item.
- The listed price per day as a grey line; the day price as green stretches on days a promotion that counts was on.
- Today's price as a dot, with a dashed line at its height across the whole chart, so every earlier day at or below it stands out.
- Labelled: the usual price, the lowest and highest day prices in the span. "Last this low" is said in words beside the chart (S6).
- Days not tracked are gaps in the lines, never filled in; sale days of unknown price (S1) are marked as on sale, with no price drawn.
- A short history makes a short chart: the span is what was tracked, not a fixed 90 days.
- Readable on a 390-pixel-wide phone and in both themes; text labels, so colour is never the only signal.

**Page size.** Every product page stays under 45,000 bytes, the line the owner set on 2026-11-10 for shrinking pages; the site check's hard limit stays 60,000 (`MAX_PAGE`). The largest page is 39,264 bytes today; the current chart costs a few hundred bytes a section, its key included (its drawing alone, at most 257 bytes over 10,169 charts in 3,000 pages of the 2026-11-10 build). The builder measures the largest real page after the change; if it passes 45,000, the chart's drawing is simplified first (runs of one price drawn as one segment), before anything is dropped.

## Words

Shopper text says "shelf price"; the fold-outs and the method page say "listed price" with its definition (the price in the chain's price file, before promotions). This settles the mismatch the 2026-11-10 handoff review found (the front subtitle's "shelf prices" against "listed price" elsewhere).

| Where | Words |
|---|---|
| Picker | "Which store are you in?" |
| Header | "Carrefour Market · change" / "Pick your store" |
| Deal badge | "At Carrefour Market: DEAL · ₪1.90 off" |
| No deal badge | "At Carrefour Market: NO DEAL" |
| Deal reason | "Usually ₪11.90, sales included (9 days tracked)." |
| No deal reason, always on | "It's been ₪10.90 or less on 9 of the 9 days tracked." |
| No deal reason, small | "Only ₪0.40 below its usual ₪3.20 (12 days tracked)." |
| Condition | "Club members only" / "When you buy 2" |
| Last this low | "Last this low: 12 October, at ₪9.90." / "Lowest in the 10 days tracked." |
| How often | "On sale on 9 of the 9 days tracked." |
| No verdict | "No sale today" / "New today: no price history yet." / "On sale at some stores only" / "On sale, but the sale price could not be read" / "Sale prices could not be read today" / "On sale most days; earlier sale prices could not be read" / "Not sold at Carrefour Market today, last seen 3 November" |
| Coming sale | "A sale starts on 14 November" |
| Other store types | "Elsewhere today" |
| Front headline | "At Carrefour Market today: 1,130 of 4,210 promotions are actually deals." |
| Front fold-out | "How a deal passes": "Promotions checked against what the product usually costs, sales included, over up to 3 months." |

The final words are the owner's, read on the built pages before merge, as for the front page on 2026-11-10.

## Changes to the shopper-site design

- **P7** (the gap): its three sentences go (the gap against the 30-day median, the 30- and 90-day lows, the listed-price change sentence); the verdict's reason line, the chart's labels and "Last this low" replace them, against S2's usual price, sales included.
- **P8** (promotion history): its sentences give way to S7. The run sentence ("Run seen before today: from 19 November 2026 or earlier to 19 November 2026.", which repeats the day on a one-day run) goes with them.
- **The 90-day price-change text** (`price_history`) goes; the chart replaces it, with a short text alternative inside the SVG for screen readers.
- **P9** (the table "Today at each column") goes; "Elsewhere today" replaces it.
- **Kept, moved:** the coming-sale line (F2) under the verdict; today's full promotion list into the fold-out; Call 10's "last seen" into the "Not sold at … today" line.
- **Q3** (which deals the front page lists): the front page's list rule above, per store type.
- **Q2's one script:** one script file for the whole site, search plus the picker, loaded on every page; the upload check allows that one script tag on every page and still refuses any other. Anti-goal kept in spirit: no measured fact needs the script. The pick is kept in the browser's local storage under one key, never sent anywhere; when storage is blocked the site simply forgets the pick.
- **"What a visitor sees"** items 1 and 2: replaced by this document's.
- **Q4's public names:** "The deal against its listed prices" and "How often it goes on promotion" give way to this document's Words.

Also carried, small: the test names and docstrings that still say "count line", which the front page no longer has (`tests/test_shop_build.py`, `tests/test_siteday.py`, `src/shopper/build.py`); README's lines describing the deal rule ("below every price of the past 90 days"), rewritten to the new rule.

## Building order

Each step test-first, its groups' mutations run before it commits, a fresh review; a whole-branch review at the end; nothing deployed until the owner's go.

1. **The rules** (S1 to S8, the front list) in `src/shopper/`, with the 90-day golden history extended for: always on, a monthly sale, on sale exactly half the days, a short history, new today, savings of ₪0.99 and ₪1.00, a buy-2 promotion, a hole, a promotion at some stores only, an unreadable price.
2. **The product page:** verdict, reason, chart, how often, fold-out, "Elsewhere today"; the words pinned; the golden pages repinned with the reason in the commit; page sizes measured on a real day's build.
3. **The store picker:** the script, the root picker, the nine store-type front pages, the header, the upload check's script rule.
4. **The front pages' rule and words**, the method page, README.
5. **The owner's read** of a real day's build, all pages, before merge.

## Testing

As the project's standard (shopper-site.md "Testing"): a test and a mutation for every rule. With the script blocked, each page's facts are checked in Python (every store type's verdict, reason and chart present in the HTML). How the script itself is tested is the plan's call.

## Cost (monthly, estimates)

- Nine more pages uploaded each morning: about 270 writes a month, under one cent at the shopper site's write rate (about $5.50 a million, from "Cost" in shopper-site.md).
- Larger product pages (the chart): more storage for the 30 days of old page versions the site bucket keeps, a few cents.
- Total: under $0.10 a month more.

## Left to the builder

- The chart's exact drawing within the rules above: sizes, ticks, label placement.
- The colours, within S5 and the contrast check.
- The store-type front pages' file names, and the script's structure.
- Ties in the front list's order.

## Calls made in this design (the owner can overturn any)

These were not settled in the design talk of 2026-11-11; the agent writing this design made them.

1. Exactly half the days on sale: the shelf price stays the usual price (S2's higher middle value).
2. The promotions that count are the set the page already calls today's deal, club-only included, with the condition named.
3. No verdict for a promotion at some stores only, or with an unreadable price (S4).
4. How often on sale is said as counts ("on 12 of the 60 days tracked"), not as a pattern ("about one week a month", the wording shown in the design talk), since a pattern is an inference.
5. The front list shows the top 100 deals per store type; the headline counts only products passing the 20-day bar.
6. Tapping a store type under "Elsewhere today" shows it without changing the pick.
7. One script file on every page, in place of a second script.
8. "Shelf price" in shopper text, "listed price" in the fold-outs and the method page.
9. Days whose promotions were not read are left out of everything (S0), and a sale whose price could not be read counts as on sale without a price (S1), so neither pushes the usual price up.
10. Of today's product page: P7's sentences, the price-change text and the per-store-type table go; the coming-sale line, the full promotion list and "last seen" stay, moved (see "Changes to the shopper-site design").
11. The root page keeps the title question, a line on what the site does and the "Built by" links, since it is also the portfolio's landing page.
12. Each store type's front page keeps today's two filters, and each deal row names its condition.
13. The ₪1.00 minimum and the shade bands compare the figures as shown, rounded to the agora, as P4's prices already are.

## Measurements behind the design

From the hand build of 2026-11-10 (`site/p`, 24,730 product pages), each promotion's figures as the pages state them against the 30-day median listed price:

- 32,894 promotions with a stated saving: the middle saves ₪2.90 (half between ₪1.40 and ₪4.90; one in ten ₪7.90 or more), the middle 17% off.
- Under ₪1: about 17%; ₪1 to ₪2.99: about 38%; ₪3 to ₪4.99: about 22%; ₪5 or more: about 22%.
- Of 42,659 store-type sections with a promotion and some history, about 70% were on promotion on more than half their recorded days, and 36% on every one. With 9 or 10 days of records, a month-long promotion that began before 1 November counts as always on; the share should fall as the history grows.

## Changed after the build

The design above stays the record as approved; this note keeps it true. The owner answered two questions on 2026-11-11, after the build; [the plan's Deviations](store-first-plan.md#deviations) ("Fix wave after the whole-branch review") hold the rest.

- **Each store page's subtitle** is the fold-out's sentence, "Promotions checked against what the product usually costs, sales included, over up to 3 months.", in place of "the title and subtitle as today" in "What a visitor sees" 4. The sentence therefore shows twice on a store page: as the subtitle and as the fold-out's first line.
- **A product on sale whose sale price could not be read has no today's price** (S6's today's price, for that case, in place of the listed price): the chart draws no dot, dashed line or label for today's price, and the page says no "Last this low".

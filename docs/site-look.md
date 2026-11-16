# The site's look: "Shelf label" (design)

**Grade (the owner's, 2026-11-15):** a portfolio piece for job applications at production quality: professional, elegant and impressive at first glance; accessible (WCAG 2.2 AA in both themes); fast; light and dark; phone and desktop.

**Status:** approved 2026-11-15, built on branch q36-site-look (2026-11-16; "Deviations" in site-look-plan.md for what changed), not yet merged. The owner saw three directions as mockups and chose this one, "Shelf label", on 2026-11-15 ("I actually prefer A"), read its full design the same day and changed three things: deals are green, not yellow; the front page's headline is "DEAL OR NO DEAL?"; and the line under it is new. The owner also settled the questions that design left open ("go with your recommendations on the open questions"). Last, the owner chose NO DEAL's look by eye from two drawn variants: the yellow label ("Yellow"; "NO DEAL: the yellow label"). This document replaces two earlier versions, both rejected: a careful clean-up ("nothing really changed - I want a widespread redesign to make it look professional and impressive") and a redesign in navy and indigo with cards, pills and a shaded chart ("better but I don't think it looks very elegant. And the chart is just too confusing for the layperson ... I don't want it to look AI-y either").

It restyles the shopper site of [shopper-site.md](shopper-site.md) and [store-first.md](store-first.md). What the rules compute does not change. What a page says changes only where "Word changes" and "Calls made in this design" say so.

## Two readers

1. **A hiring manager or engineer** who opens the link from a CV, on a laptop or a phone. In five seconds the site has to read as a real, finished product made by someone with taste and care.
2. **The shopper in the aisle** on a phone, who needs "Deal" or "No deal", how much, and why, at a glance.

## What the owner has decided

All on 2026-11-15, but those dated 2026-11-16, after the owner read the built pages. Five of the first were this design's recommendations, which the owner took as a whole ("go with your recommendations on the open questions"); each is marked.

- **The direction: "Shelf label"**: the shelf label's shape and type: a coloured sale label for a deal, the price set as on a shelf edge, the barcode on the label.
- **Deals are green, throughout** ("let's do green. I want to see what it looks like. I don't think the yellow on its own is such a strong idea anyway."): the verdict's label, the small labels of "Elsewhere today" and of a store's table, the box in the header's wordmark, the chart's sale line.
- **The front page's headline is "DEAL OR NO DEAL?"**, in place of "Is it actually a deal?": DEAL set as the green deal label, NO DEAL as the no-deal label. **The nine store pages keep "Is it actually a deal?"** as their headline (recommended to the owner; the owner's go).
- **The line under the front page's headline:** "Find out if a sale is actually a deal: pick the store you're in, then look up the product. Each sale is checked against what it usually costs there."
- **The chart reads like a familiar price-history chart** (after the owner showed camelcamelcamel's and asked "why can't it look more like this?"; as redrawn on 2026-11-16, below): a price axis at the left with a few round ₪ values and light gridlines; dates along the bottom; one step line of the price paid each day, a sale a drop in it in the sale's green; today's price written at the line's end, in the line's colour; a small plain table under it; a key in words for the marks that need them; no shaded areas and no bands. With it, its words: the table's heads "Lowest", "Highest", "Today", and short dates ("16 Aug", "13 Nov", "Sep") (recommended to the owner; the owner's go).
- **A short history is not drawn narrow.** (This replaces store-first.md's "a short history makes a short chart".)
- **A page never shows two different numbers both called "days tracked"** (recommended to the owner; the owner's go; the rule under "Word changes").
- **Each store's label on the front page carries its count of promotions today** ("1,347 promotions today"; recommended to the owner; the owner's go).
- **The method page's row of links is named "On this page"** for screen readers (recommended to the owner; the owner's go).
- **Four earlier word changes:** "Price today: ₪14.00" under the verdict on a product page; the first tracked day's date along the chart's bottom and "today" at its right end; the chains' line ("Shufersal · Rami Levy · ...") in the front page's header only; on a store's own page, the table's badge without "At <store>:".
- **NO DEAL is a yellow label** (the owner's choice by eye between two drawn variants, 2026-11-15: "Yellow").
- **The chart is one line, the price paid each day** (2026-11-16, after reading the built pages, where the shelf line and the sale line together were "absolutely unreadable": "yes - one line. obviously. what does 'shelf price' even mean in this context?"; "exactly. I gave an example of what I wanted with camelcamelcamel"). It replaces "the shelf price as a step line and the sale price as a second step line in a second colour". With it, this design's recommendations on its open questions, which the owner took ("go with your recommendations on all five"): the chart's table is "Lowest", "Highest", "Today", without "Usual"; up to seven days in a row with no price are joined by a dotted stretch, longer runs left open (in place of "a day with no record is a gap"); no chart when no tracked day has a price; and "How often on sale" counts out of the days before today ("On sale on 12 of the 60 days before today."), since today is not a tracked day and beside a Deal today "On sale on 0 of the 13 days tracked" read wrong. ("The chart", "Word changes".) The owner's rulings stand: no price at today on an unread sale price or on a day whose sale prices were not read.

## Why: what was measured on the live pages

Measured on the live pages of 14 November 2026, in headless Chrome at 390 pixels wide, before any redesign:

- The header takes 186 pixels before anything about the product shows.
- The verdict is a pill 34 pixels high, the same size as the nine pills of the other store types, starting 534 pixels down a product page with a store picked.
- The chart is drawn at 4 pixels a day, so two weeks of history is a drawing 56 pixels wide; and its labels shrink with it once the history is long: 12 pixels on a short history, 8.3 pixels for a 90-day one.
- A store page's table needs 36rem, so its two price columns are off-screen.
- Green does four jobs (links, the focus ring, deals, the chart's sale line), so it means nothing; in the dark theme the badge of the biggest saving is the palest of the three.
- Things to tap are small: the header's store line is 18 pixels high, a fold-out's title 24, a badge 34.
- Nothing on any page says whose site this is or that it is a product: no mark, no colour of its own, one grey column of text on every page type.

## The idea

The site speaks the supermarket's own graphic language, which every shopper already reads: on a shelf, a sale has a coloured label of its own and a regular price a plain white one. So:

- **A deal is a green label** with a dark edge, the saving in heavy narrow figures: "DEAL · ₪5.00 off". Its green is one of three, by the size of the saving.
- **No deal** is the same label in another dress, a yellow label: green for a deal, yellow for "careful, on sale but not really a deal" (the owner's choice).
- **No sale today** is the plain white label.
- **The price is set as on a shelf edge**: the shekels large, the ₪ sign and the agorot small and raised beside them.
- **The label carries the product's barcode**, drawn from its own digits.
- **A product the store does not sell** is an empty slot: the label's outline, dashed.

Everything else is ink on paper and steps back: rules, type and white space. Colour is kept for the answer. It is the opposite of a kit's look on purpose: no cards with shadows on a tinted ground, no pills, no gradient, no icon set, no navy, indigo or purple, no hero band.

## Goals

1. A hiring reader's first screen, on the front page or on any product page, looks designed: a point of view a reader can name, real figures, precise type.
2. The shopper's answer is first and largest: on a phone the label is the first thing under the product's name.
3. Every text and every mark that carries meaning passes WCAG 2.2 AA in both themes, checked by a test from the stylesheet's own colours.
4. A 390-pixel phone is first-class: no sideways page scroll, chart words at a fixed readable size, things to tap at least 24 pixels high and 44 where practical.
5. A desktop uses its width: a product page in two columns, a store's deals as a real table, a browse page in three columns.
6. Nothing from another origin; one script, unchanged.
7. Every product page under 45,000 bytes.

## Non-goals

- Any change to `search.js`, or to what the rules compute.
- Tap or hover on the chart (store-first's non-goal stands), animation, an icon set, photographs.
- A Hebrew or right-to-left layout. The pages stay English with Hebrew product names.
- The basket's own stand-alone pages (`basket.page.STYLE`): the public site shows the basket only as `basket.html` and as a section of `method.html`, in the shopper site's frame.

## Type

Two families, three files, served from the site itself.

- **Archivo** (Omnibus-Type; SIL Open Font License 1.1) draws all Latin text. It is a grotesque with a width axis, used in two cuts:
  - **the text cut**: normal width, weights 400 to 700 in one variable file, for everything read as a sentence, for names and for small labels;
  - **the narrow cut**: width 70, weight 800, one static file, for what a label prints large: the verdict, the prices, the page titles, the counts, section headings.
- **Heebo** (Oded Ezer; SIL Open Font License 1.1), weights 400 to 800 in one variable file, draws the Hebrew product names and the ₪ sign, which Archivo lacks. Beside the narrow cut it is drawn at 84% (`size-adjust`), since Heebo has no narrow cut.

The stylesheet declares two families, "Shelf" (the text cut with Heebo) and "Shelf Narrow" (the narrow cut with Heebo), each `@font-face` limited by `unicode-range`, so a page with no Hebrew and no ₪ never fetches the Hebrew file (measured: the front page and a store page with no rows load two files, a product page three). `font-display: swap`; the fallbacks are the system's sans and a system narrow face.

**The scale** (rem; a phone, then from 48rem up):

| Use | Cut | Size |
|---|---|---|
| The front page's headline | narrow, capitals | 4.4, then 8.25 |
| A store page's title question | narrow, capitals | 2.75, then 4.5 |
| Other pages' titles (method, record, basket, browse) | narrow, capitals | 2.5, then 3.75 |
| A product's name | text 700 (Heebo for Hebrew) | 1.875, then 2.75 |
| The verdict ("DEAL · ₪5.00 off") | narrow | 3.25, then 4.5; in the two-column product page between 3 and 4, by the window's width |
| The price on the label | narrow | 4, then 5.25; the ₪ and the agorot at 44% of it, raised |
| A plain line on a label ("No sale today"), the empty slot's line | narrow | 1.875, then 2.5 |
| The chart's table figures | narrow | 1.625, then 2 |
| Section headings | narrow, capitals | 1.375 |
| Body text | text 400 | 1 (16 pixels), line height 1.5 |
| Small labels ("AT CARREFOUR MARKET:", table heads) | text 600, capitals, letter-spaced 0.09em | 0.75 |
| Small print (footer, notes, barcodes) | text 400 | 0.8125 |
| The chart's axis and dates | text 500 | 0.78125 (12.5 pixels); today's prices 0.9375 |

Figures are tabular wherever they sit in a column or change from day to day.

## Colour

Ink, paper and green, as tokens; every rule of the stylesheet names a token, never a colour.

| Token | Light | Dark | Job |
|---|---|---|---|
| `--bg` | `#ffffff` | `#131313` | the page |
| `--ink` | `#111111` | `#f2f2ef` | words, rules, a label's edge, the chart's price line |
| `--ink-2` | `#555555` | `#b4b4b0` | small print, table heads, the chart's axis words, its date line and marks, and its dashed usual line |
| `--line` | `#d6d6d6` | `#3d3d3a` | hairlines between rows, the chart's grid (decoration) |
| `--soft` | `#f1f1ee` | `#222220` | a quiet ground: the basket table's lowest price in a row |
| `--d1` | `#c8f1d5` | `#27995a` | a Deal's label, a saving of ₪1.00 to ₪2.99 |
| `--d2` | `#6fdc9b` | `#34b76a` | a Deal's label, ₪3.00 to ₪4.99 |
| `--d3` | `#22b35e` | `#4fe08c` | a Deal's label, ₪5.00 or more; the wordmark's box; the headline's DEAL and a store page's "DEAL?" |
| `--on-deal` | `#111111` | `#111111` | words on any green label, in both themes |
| `--nd`, `--on-nd`, `--nd-edge` | `#ffd60a`, `#111111`, `#111111` | `#ffd60a`, `#111111`, `#ffd60a` | the NO DEAL label's fill, words and edge ("NO DEAL: the yellow label") |
| `--sale` | `#0b7a3b` | `#4fe08c` | the chart's sale stretch and today's sale price beside it |
| `--plate`, `--bars` | `#ffffff`, `#111111` | the same | the barcode: dark bars on a white plate in both themes, so a scanner reads it |

Green means one thing, a deal: a label's fill, and in the chart the sale price. Nothing else is green. A green label's edge is ink on paper, where the palest green is close to the page (1.24:1), and the label's own green on the dark page. Links are ink, underlined; there is no link colour.

### Contrast

Computed by a script that reads the tokens out of the stylesheet in both themes, as the test under "What the tests should pin" will (4.5:1 for words, 3:1 for lines, edges and marks that carry meaning). No pair fell under its line: the greens were picked to hold dark words at 4.5:1 or better, and the dark theme's first green was lightened once for margin (4.71:1 to 5.21:1).

| What | Light | Ratio | Dark | Ratio | Needs |
|---|---|---|---|---|---|
| Words on the page | `#111111` on `#ffffff` | 18.88 | `#f2f2ef` on `#131313` | 16.57 | 4.5 |
| Small print on the page | `#555555` on `#ffffff` | 7.46 | `#b4b4b0` on `#131313` | 8.93 | 4.5 |
| Words on the green label, a saving of ₪1.00 to ₪2.99 | `#111111` on `#c8f1d5` | 15.29 | `#111111` on `#27995a` | 5.21 | 4.5 |
| Words on the green label, ₪3.00 to ₪4.99 | `#111111` on `#6fdc9b` | 11.14 | `#111111` on `#34b76a` | 7.31 | 4.5 |
| Words on the green label, ₪5.00 or more; the wordmark and the headline's DEAL | `#111111` on `#22b35e` | 6.90 | `#111111` on `#4fe08c` | 11.13 | 4.5 |
| Words on the NO DEAL label | `#111111` on `#ffd60a` | 13.38 | `#111111` on `#ffd60a` | 13.38 | 4.5 |
| Today's sale price and the chart's green sale stretch, its dotted stretch and the ticks | `#0b7a3b` on `#ffffff` | 5.44 | `#4fe08c` on `#131313` | 10.95 | 4.5 |
| The chart's price line, its dotted stretch, today's price and dot | `#111111` on `#ffffff` | 18.88 | `#f2f2ef` on `#131313` | 16.57 | 3 (4.5 for the figure) |
| The chart's dashed usual line, its date line and the dates' marks, the axis words | `#555555` on `#ffffff` | 7.46 | `#b4b4b0` on `#131313` | 8.93 | 3 (4.5 for words) |
| A green label against its edge or the page (light: its ink edge on the page; dark: its fill on the page), ₪1.00 to ₪2.99 | `#111111` on `#ffffff` | 18.88 | `#27995a` on `#131313` | 5.12 | 3 |
| The same, ₪3.00 to ₪4.99 | `#111111` on `#ffffff` | 18.88 | `#34b76a` on `#131313` | 7.19 | 3 |
| The same, ₪5.00 or more | `#111111` on `#ffffff` | 18.88 | `#4fe08c` on `#131313` | 10.95 | 3 |
| The NO DEAL label's edge against the page | `#111111` on `#ffffff` | 18.88 | `#ffd60a` on `#131313` | 13.16 | 3 |
| A plain label's edge, a search box's and a checkbox's edge, the focus ring | `#111111` on `#ffffff` | 18.88 | `#f2f2ef` on `#131313` | 16.57 | 3 |
| Words on the inverse label (the basket's lowest total, the current letter, a store's label under the pointer) | `#ffffff` on `#111111` | 18.88 | `#131313` on `#f2f2ef` | 16.57 | 4.5 |
| Words on the soft ground (the basket's lowest price in a row) | `#111111` on `#f1f1ee` | 16.69 | `#f2f2ef` on `#222220` | 14.21 | 4.5 |
| Small print on the soft ground | `#555555` on `#f1f1ee` | 6.59 | `#b4b4b0` on `#222220` | 7.66 | 4.5 |
| The barcode's bars on their plate | `#111111` on `#ffffff` | 18.88 | `#111111` on `#ffffff` | 18.88 | 4.5 |
| Hairlines between rows, the chart's grid | `#d6d6d6` on `#ffffff` | 1.45 | `#3d3d3a` on `#131313` | 1.70 | decoration |

The chart's two line colours were also put through the dataviz palette validator on both grounds: apart under colour-blind simulation (worst pair ΔE 33.7 light, 14.1 dark, against a target of 8), apart for normal vision (35.7 and 22.7, against a floor of 15), and each at least 3:1 on its ground. The validator's lightness-band and colour-strength checks are written for coloured series and mark any neutral ink as outside them, which is expected for one ink line and one coloured line.

## Components

**Header.** A paper band with a 2.5-pixel ink rule under it. At the left the name as a wordmark in the narrow cut, capitals: "DEAL" on a small green label, then "OR NO DEAL". At the right the date line, then the store line ("Carrefour Market · change", or "Pick your store"); the chains' line before the date on the front page only. On a phone the date and the store line drop to rows of their own. The store line's links are 43 pixels high.

**The label** (`div.tag`): the picked store's answer on a product page. A 2.5-pixel edge, corners of 5 pixels, two parts:

- **the saying part**, at the left (on top on a phone): the small label "AT CARREFOUR MARKET:", the verdict in the narrow cut, the reason, then the conditions in bold ("When you buy 2", "Club members only") and a coming sale's line. Green, in the shade of its saving, with dark words for a Deal; yellow, with dark words, for No deal; paper for every line that is not a verdict.
- **the price part**, at the right (below on a phone), always paper: "PRICE TODAY:" over the price, then the barcode with its digits under it. A weighed product's "a kilogram" follows the price in small print. With no price known today the part holds the barcode alone.

A line that is not a verdict ("No sale today", "On sale at some stores only", "Sale prices could not be read today" and the rest of `NO_VERDICT`) is set in the narrow cut at the smaller size on a white label; the store's name then shows as a small label above it (it is the section's heading, hidden only where the label itself says "At <store>:").

**The empty slot** (`.not-sold`): "Not sold at Carrefour City today", with "last seen 13 November" when the page knows it, in the narrow cut inside a dashed 2.5-pixel outline of the label's shape.

**Small labels** (the badges of "Elsewhere today" and of a store page's table): the verdict in bold 13-pixel type in a 1.5-pixel edge with 3-pixel corners; green in its shade for a deal; for no deal, yellow. A line that is not a verdict ("no sale today") is plain small print with no edge.

**A warning** ("Promotions from Osher Ad's files could not be read today."): bold text behind a 6-pixel ink bar at its left. No colour of its own: a warning is ink.

**Tables.** Heads as small capitals in the second ink over a 2.5-pixel rule; rows parted by hairlines; figures tabular; the last column flush right. A table too wide for a phone scrolls inside its own box (`div.table`, as today), never the page; the basket's price table keeps its first column in place while it scrolls.

**The store picker** (front page): nine labels in a grid, three across (two on a phone), each a 2-pixel ink edge: the store type's name in bold, and under it its count of promotions today in the narrow cut with "PROMOTIONS TODAY" in small capitals, set like a price. A label turns to ink, its words to paper, under the pointer. The chains' headings stay in the markup for screen readers and are not shown: every label already carries its chain's name.

**Search.** The label in bold over a box with a 2.5-pixel ink edge, 55 pixels high on a phone. Results are rows: the name in bold, the barcode in small print under it, a hairline between.

**Filters** ("Hide club-only deals", "Hide deals with a minimum spend"): real checkboxes, hidden from sight, each label drawing a 20-pixel square with an ink edge that fills when checked. The keyboard's focus shows on the label.

**Fold-outs** (`details`): the title in bold over a hairline, a 2.5-pixel rule under the whole, the browser's own triangle.

**"Elsewhere today".** The heading in the narrow cut under a 2.5-pixel rule; each other store type a row 48 pixels high: its name in bold at the left, its small label at the right. With no store picked the same rows stand first, as the picker, with no heading (store-first's rule).

**Footer.** A 2.5-pixel rule, then the credit line in small print in the second ink; its links in ink, bold.

**Focus.** `:focus-visible` draws a 3-pixel ink ring 3 pixels off the element (18.88:1 on paper, 16.57:1 on the dark page).

**Motion.** None: no transition, no animation.

**Print.** The store line, the search box, the filters, a browse page's letters and the method page's row of links are left out. Browsers print no backgrounds by default, so a coloured label prints as its outline, which still reads.

## Page by page

**The front page.** The headline "DEAL OR NO DEAL?" in the narrow cut, capitals, at 132 pixels on a desktop (one line there, two on a phone): DEAL on the full green label, NO DEAL on the yellow no-deal label, "OR" and the question mark plain. The owner's line under it; a rule; "WHICH STORE ARE YOU IN?" and the nine labels; then the four links ("Built by ...", "How this is made", "Track record", "Code on GitHub") as small capitals, underlined.

**A store page.** The store's name as a small label; the title question "IS IT ACTUALLY A DEAL?", smaller, on one line on a desktop, its last word on the full green label; the subtitle; the search box and "Browse by first letter"; a rule; the headline in bold with its two numbers in the narrow cut ("At Carrefour Market today: **14 of 4,196** promotions are actually deals."); the two filters; the table.

- **On a desktop** the table has four columns: the product's name in bold with its barcode under it; the small green label, in its shade, with the condition under it; the price today in bold, right-aligned; the usual price in the second ink, right-aligned.
- **On a phone** each row is a block: the name and barcode; under them the label at the left with its condition, and at the right the price today in bold over "Usually ₪26.80". Nothing scrolls sideways. The table keeps its table roles for screen readers.
- With no row to show, the line the page already has ("None yet: a product needs 20 days of price history first.") stands as the headline and the table says "No deals to show."

**A product page.** The name; the names as each chain lists it; the barcode and size line. Then, for the picked store type, the label, the chart with its key and its table, "Last this low" and "How often" as two ruled lines, and the fold-out. On a desktop (64rem and up, while the script runs) the page is two columns of a 12-column grid: the label, chart and facts in eight, "Elsewhere today" in four, level with the label. The states:

| State | What shows |
|---|---|
| Deal | the green label, in the shade of its saving; the price part; the chart with today's sale price in green at the right end |
| No deal | the same label in yellow: "NO DEAL", its reason, its condition |
| No sale today | a white label: "No sale today" and the price part; a chart with the shelf line alone |
| On sale, price not read today; sale prices not read today | a white label with that line; no price; the warning above it when the chain's promotions could not be read; the chart still shows the days before |
| Not sold at the picked store | the empty slot; under it "Elsewhere today"; when the store listed it before, the chart of those days and no price today |
| A first visit, no store picked | the rows of all store types first, then the first one's label and chart |
| A short history | the same chart at the same width, with a date a week along the bottom |
| A long history | the months along the bottom |
| The script blocked | every store type's part in turn, each with its own label and chart, in one column |

**Search results.** Under the search box, as rows (above). The script's own sentences ("Nothing found. ...") are plain text.

**Browse pages.** The title in the narrow cut with its Hebrew letter; the letters as small square labels with a 2-pixel edge, 44 by 46 pixels, the current one ink-filled; the count; the names in three columns on a desktop, one on a phone, each a bold name over its barcode.

**The method page** and **the record page.** Documents: the title, the lead paragraph, sections under 2.5-pixel rules with headings in the narrow cut, text held to 44rem. The method page gains a row of links to its own sections. Its rules list is two columns on a desktop (the rule's name, then its text). Tables as above.

**The basket page.** The three figures as three labels: the lowest total ink-filled (paper words on ink), the highest and the gap with an ink edge. The totals as bars in the second ink, the lowest in ink, each with its total in the narrow cut. The price table with the lowest price of each row in bold on the soft ground.

## The chart

As the owner redrew it on 2026-11-16, after reading the built pages ("What the owner has decided"). One per store type, in that store type's part of the product page. What it shows is store-first's ("The rules", S0 to S8). It reads like a familiar price-history chart: one line of the price, a sale a drop in it, today's price written at its end.

**What is drawn.**

- **Up:** the price, on an axis of round ₪ values with a light gridline at each: the smallest step of 1, 2, 5, 10, 20, 50 ... shekels that holds every drawn price in at most five steps and at least two; half a shekel for prices less than a shekel apart; no price on the bottom line; not from zero. The prices drawn are the days' prices, today's price and the usual price. A sale day's listed price is not drawn, so it does not stretch the axis.
- **Across:** each calendar day from the first tracked day to today, today the last; the first tracked day's date at the left; a mark and a name each week under 46 days, each month from 46; a name written only between 8% and 91% of the span, a phone hiding those outside 22% to 84% and, from 28 days, every other week's.
- **The line:** what the product cost each day. A tracked day's price is its day price (S1: the lower of the listed price and the lowest promotion that counts that day). Today's is the verdict's price today (S3), the same figure as the label's "Price today". A 2-pixel ink step line on the days with no sale; on the days a promotion counted, the same line in the sale's green at 3.5 pixels, with the steps down into the sale and back out of it, so a sale reads as one notch.
- **Today:** one dot at the line's end, at today's price; beside it, in a column of its own, the price in the line's colour there (green when a promotion counts today) and "today" under the price. With no price today (an unread sale price, sale prices not read today, not sold, too few files) the line ends at its last day with a price, and "today" stands alone on the dates' line; an unread sale price keeps its tick under today.
- **The usual price** (S2, with a Deal or No deal): dashes in the second ink at its height, on every day of the span except those on which the line runs within 6 pixels of that height. Its words, "usually ₪9.90", are always written, at the right, 8 pixels above the level; below it instead when the line runs just above in the last 30% of the days (a point, a dotted stretch, or a step crossing that band) and below is free. At the very top of the plot the words stand in the chart's top margin.
- **A day with no price** (no record that day, promotions not read, the product not listed, or a sale whose price could not be read): when seven or fewer such days lie in a row between two days with a price, the line goes on dotted at the last price, in the colour of the day it carries, and steps at the next day with a price. When more than seven, the line stops and starts again: a gap. Nothing is carried past the last day with a price. No number counts a carried day.
- **A sale day whose price could not be read:** short ticks in the sale's green standing on the date line under that day, 7 pixels high, 2 on and 2 off.
- **The date line and the dates' marks:** 1 pixel, the second ink. Never the line's colour or weight.
- **The key,** only for marks that need words: "on sale" when a sale stretch is drawn, "on sale, price not read" when a tick is. A chart with neither has no key (on the real day, 96,073 of 133,372 charts).
- **The table:** "Lowest" and "Highest", each over the latest day at that price ("today" when it is today's), and "Today". No "Usual" cell: the chart writes the usual price at its own height and the label's reason says it.
- **No chart** when no tracked day has a price: there is no line to draw. On the real day that is 460 of 133,832 parts, 450 of them "On sale, but the sale price could not be read" with no sale price ever read.

**Lowest and highest count today** (`shopper.verdict.extremes`; the design's call 3) and are exactly the line's lowest and highest points, so the table agrees with the line under it ("Lowest in the 83 days with a known price.") and never shows a "lowest" above today's price.

**How it is drawn, so no word ever shrinks:** four SVGs in a row, only the lines' one with a `viewBox` and `preserveAspectRatio="none"`, every stroke `vector-effect: non-scaling-stroke`, no text in it, its text alternative an `aria-label`; the axis 46 pixels wide, today's column 64, the plot the rest; 200 pixels high, 224 with the dates; no `style` attribute.

```html
<div class="history"><div class="chart">
<svg class="ax" aria-hidden="true"><text x="40" y="4">₪10</text> ... <text x="40" y="204">₪2</text></svg>
<div class="plot">
<svg class="lines" role="img" aria-label="Price chart: usually ₪9.90, lowest ₪2.90, highest ₪10.00, today ₪2.90."
     viewBox="0 0 16 200" preserveAspectRatio="none">
<path class="grid" d="M0 150H16M0 100H16M0 50H16M0 0H16"/>
<path class="usual" d="M15 3H16"/>
<path class="gap" d="M5 3H6M7 3H8"/>
<path class="paid" d="M0 3H5M6 3H7M8 3H9V0H10V3H15"/>
<path class="sale" d="M15 3V178H16"/></svg>
<svg class="over" aria-hidden="true"><text class="usually" x="100%" dx="-12" y="-5">usually ₪9.90</text>
<text y="217">1 Nov</text><line x1="6.25%" x2="6.25%" y1="200" y2="206"/> ... </svg>
</div>
<svg class="now" aria-hidden="true"><circle class="sale" cy="178" r="4.5"/>
<text class="sale" x="12" y="183">₪2.90</text><text class="end" x="12" y="197">today</text></svg>
</div>
<p class="key"><i class="sale"></i>on sale</p>
<table class="stats"> Lowest ₪2.90 today · Highest ₪10.00 10 Nov · Today ₪2.90 </table></div>
```

That is the owner's screenshot (p/7290000000053.html at Shufersal Universe), whole. The paths, in order: `grid`; `usual`; `gap` and `gap sale` (the dotted stretch after an ordinary day and after a sale day); `paid`; `sale`; `unread`. The class is `paid`, not `price`: `.price` is the label's own class in the stylesheet.

**Width** (the owner's "not drawn narrow"). The plot always takes the whole width its column has, whatever the number of days: there is no pixels-a-day rule any more, so a 14-day history is drawn as wide as a 90-day one. Measured in the preview: 248 pixels at a 390-pixel phone and 602 at 1,280, the same on the 13-day pages and the 90-day example; the axis column is 46 pixels and the today column 64. On a 320-pixel phone the plot has 178 pixels (measured on one page), and there the label's barcode drops under its price and the table's figures are set smaller. The chart never scrolls sideways. Its height is 200 pixels at every width, 224 with the dates.

## The barcode

The label shows the product's own barcode, the detail that makes it a shelf label and not a box. It is kept, with these rules:

- **It is a true encoding, made by the build**: for a code of 13 digits whose check digit holds, EAN-13 (95 modules); for 12 digits whose check digit holds, the same bars as that UPC-A (the EAN-13 with a leading zero); for 8 digits whose check digit holds, EAN-8 (67 modules). `basket.barcode.is_gs1` already tests the check digit.
- **Any other code gets no bars**: the label then shows the price part without them, and the page's "Barcode ..." line still gives the digits. Nothing that looks like a barcode and is not one is ever drawn. In the 2,753 codes of the downloaded browse pages and search pieces, 2,645 have 13 digits, 68 have 12, 13 have 8 (every one of the three kinds with a valid check digit), and 27 have 10 or 11 and would get no bars.
- **It is drawn once a page and reused**: one path whose dashes are the bars' and spaces' widths (`stroke-dasharray`), 222 bytes, in a `<defs>` after the barcode line; each store type's label shows it with `<use href="#ean">`, 146 bytes with the digits under it: 1,536 bytes on a page of nine parts. The digits under the bars are hidden from screen readers; the barcode line already says them.
- **A scanner needs dark bars on a light ground**, so the bars are always `--bars` on `--plate`: in the dark theme they sit on a white plate with room at each side. A module is 2 pixels wide on a desktop and 1.5 on a phone (3 or more of a phone screen's own pixels).
- **A test pins it**: known codes against their module patterns (worked by hand from the GS1 tables), every pattern's length (95 or 67), decoding each pattern back to its digits, and the refusals (a wrong check digit, other lengths, letters, digits that are not ASCII).

## The deal shades (store-first S5): kept, as three greens

store-first.md's S5 colours a Deal by the size of the saving. The first draft of this design, with one yellow, proposed to stop drawing the shades. With green they fit again, and S5 is the approved rule with its tests, so they stay (a call; see "Calls"):

| Saving | Class | Light | Dark | Ink words on it, light and dark |
|---|---|---|---|---|
| ₪1.00 to ₪2.99 | `deal-1` | `#c8f1d5` | `#27995a` | 15.29:1 and 5.21:1 |
| ₪3.00 to ₪4.99 | `deal-2` | `#6fdc9b` | `#34b76a` | 11.14:1 and 7.31:1 |
| ₪5.00 or more | `deal-3` | `#22b35e` | `#4fe08c` | 6.90:1 and 11.13:1 |

- **More green is more saving, in both themes.** On paper the label deepens from pale to full green; on the dark page it brightens from dim to full. Either way the biggest saving is the strongest mark on the page (the look before this one had it the palest of the three in the dark theme).
- **The words on every green are the same dark ink**, so a label reads the same whatever its shade.
- **The shade is never the only signal**: the figure says the saving ("₪5.00 off"), and "Elsewhere today" and a store's table are sorted by it, largest first.
- **Where it shows:** the verdict's label on a product page, the small labels of "Elsewhere today", the small labels of a store's table. The wordmark, the headline's DEAL and a store page's "DEAL?" take the full green.
- **In the code nothing changes:** `Verdict.shade` and `badge_class` give the three classes as today.

## NO DEAL: the yellow label

A product on sale that is not a deal gets the verdict NO DEAL. Its label is yellow: the owner chose it on 2026-11-15 from two variants drawn on the same four pages, Y (yellow) and W (the plain white label). The table keeps W for the record; the builder writes Y's three tokens only.

| | Variant Y: a yellow label | Variant W: the plain white label |
|---|---|---|
| The idea | green for a deal, yellow for "careful, on sale but not really a deal", as a traffic light | a deal has a colour; everything else is the ordinary shelf label |
| `--nd` (fill), light and dark | `#ffd60a` and `#ffd60a` | `#ffffff` and `#131313` (the page) |
| `--on-nd` (words) | `#111111` and `#111111` (13.38:1) | `#111111` and `#f2f2ef` (18.88:1 and 16.57:1) |
| `--nd-edge` (edge) | `#111111` on paper; the yellow itself on the dark page | `#111111` on paper; `#f2f2ef` on the dark page |
| The verdict's label, No deal | yellow, dark words | paper, ink edge |
| Small labels "NO DEAL" in "Elsewhere today" | yellow | paper, ink edge |
| The headline's NO DEAL | on a yellow label | on a white label with an ink edge |
| "No sale today" and the other lines that are not a verdict | the plain white label | the plain white label |

What each gives:

- **Y** gives three states three looks: a deal is green, a sale that is not a deal is yellow, no sale is white. The case the site exists to catch, "on sale, but not actually a deal", has a colour of its own. Its price: a second loud colour, and a product that is No deal at seven store types shows seven yellow labels.
- **W** keeps green the only colour on the site, which is the calmer and more formal page. Its price: NO DEAL and "No sale today" then differ only in their words.

The header's wordmark is the same in both: DEAL in the green box, "OR NO DEAL" plain.

## Hebrew names in English pages

Product names are wrapped in `<span class="as-listed" lang="he" dir="rtl">` (`CHAIN_SPAN`), and the basket's Hebrew names in `<span dir="rtl" lang="he">`. The `dir` attribute already isolates the name from the English around it, so a name's digits and Latin letters stay in the right order and the text after the name is not disturbed. Checked on the live pages: names such as "שמן קנולה+נוגדי חימצון1ל" and "evrest 150*200 שמיכת" read correctly in headings, tables, lists and search results. So:

- Keep `dir="rtl"`. Do not switch to `dir="auto"`: it takes the direction from the name's first letter, and on the live "other" browse page 130 of 667 names start with a Latin brand and go on in Hebrew ("AROY-D נוזל אגוז קוק"); `auto` would lay those out left to right and put the Hebrew words in the wrong order for a Hebrew reader.
- A name stays left-aligned with the rest of the page: the page is English, and one left edge reads better than names jumping to the right.
- One flaw, left alone: a name with no Hebrew letter at all still gets `lang="he" dir="rtl"`. On that page it is 17 of 667 names (DOVE, REXONA ...), none starting or ending with a sign, so all 17 draw the same either way; a screen reader may read them with a Hebrew voice.
- New here: within a name the Hebrew letters come from Heebo and the digits and Latin letters from Archivo, by `unicode-range`. Checked in the preview on the names above.

## The dark theme

Drawn and measured, not only planned (`prefers-color-scheme: dark`; the preview's dark screenshots):

- The page is `#131313` and the inks turn light; rules and plain labels' edges are the light ink.
- **A green label keeps dark words** on its own three greens of the dark theme (5.21:1, 7.31:1 and 11.13:1) and loses its dark edge: on the dark page each green is its own edge (5.12:1, 7.19:1 and 10.95:1 against the page). The wordmark's "DEAL" and the headline's DEAL do the same.
- **The price part** is the dark page inside the label's edge, its price in the light ink; the barcode sits on its white plate.
- **NO DEAL**: the yellow stays, with dark words, and is its own edge (13.16:1 against the page).
- **The chart**: the shelf line and the axis in the light ink, the sale line and today's sale price in `#4fe08c` (10.95:1), the grid `#3d3d3a`.
- The basket's lowest total is the light ink with dark words on it; the soft ground is `#222220`.

## The shared stylesheet and the font files

Today each page carries its style inline: 6,244 bytes of the largest of the 14 product pages measured. This design's style is 20,928 bytes (5,316 gzipped), too much to repeat in about 25,000 pages, and fonts cannot be inline at all. So the site gains one folder of files that pages share.

**In the site** (`assets/`):

| File | Bytes | What |
|---|---|---|
| `look.<hash>.css` | 20,928 | the stylesheet; every page links it and nothing else |
| `archivo-text.<hash>.woff2` | 25,660 | Archivo, normal width, weights 400 to 700 |
| `archivo-narrow.<hash>.woff2` | 11,420 | Archivo, width 70, weight 800 |
| `heebo-hebrew.<hash>.woff2` | 6,072 | Heebo: the Hebrew block and ₪, weights 400 to 800 |
| `OFL-archivo.txt`, `OFL-heebo.txt` | 4,388 and 4,474 | each family's licence, as its makers ship it |

Each `<hash>` is the first ten hex digits of the SHA-256 of the file's bytes, so a file's name changes when its bytes do. The stylesheet names the fonts by bare file name (`url(archivo-text.<hash>.woff2)`), resolved beside it. A first product page fetches the stylesheet and three fonts, 64,080 bytes in all beside the page; every later page fetches nothing but itself.

**In the repository:**

- `src/shopper/static/look.css`: the stylesheet as written (the appendix), with the fonts' plain names.
- `src/shopper/static/fonts/`: the three `.woff2` files, the two licence texts, and a short `README` giving each file's source and SHA-256. They are committed as built: **the site's build needs no font tool and gains no dependency.**
- `scripts/subset_fonts.py`: how the three files were made, for the day one is remade: it needs fonttools and brotli in a throwaway environment (4.59.0 and 1.2.0 made these), never in the project's requirements, and CI does not run it. Made twice from the same sources it gave the same bytes.

**Sources, pinned, and licences.** Each family comes from a fixed commit of the `google/fonts` repository, more than a month old:

| Family | Version | Commit of `google/fonts` (its date) | Source file's SHA-256 |
|---|---|---|---|
| Archivo | 2.001 | `6c70c829f09ea345d3590406693220ea35c6553f` (2021-02-04) | `0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053` |
| Heebo | 3.100 | `804ab16a8ff8ac0072e7c5ecc34e381b4a710177` (2023-11-24) | `18f930b583fa8fe6b40b2f8263b7ac6afbac07adc91a12467874e7467d3ace30` |

Both are under the SIL Open Font License 1.1. A subset is a modified version, and the licence forbids a modified version from using a Reserved Font Name. Each family's own `OFL.txt` at its commit was read for one: Archivo's copyright line is "Copyright 2020 The Archivo Project Authors (https://github.com/Omnibus-Type/Archivo)" and Heebo's "Copyright 2014 The Heebo Project Authors (https://github.com/OdedEzer/heebo)"; neither declares a Reserved Font Name (the words appear only in the licence's own definitions). So the subsets may keep their names; the stylesheet calls them "Shelf" and "Shelf Narrow" all the same. The licence asks that its text go with the fonts: the two `OFL-*.txt` files are served beside them, and the copyright and licence names stay inside each file.

**What each subset keeps.** Latin: Basic Latin, Latin-1, the dashes, the curly quotes, the bullet, the ellipsis, two arrows and the minus sign. Hebrew: the Hebrew block, ₪ and the space. Every one of the 121 different characters on the downloaded pages and search pieces is drawn by one of the files. A character outside them falls back to the system's font, by the stylesheet's own fallbacks.

**The build** (`src/shopper/build.py`) writes `assets/`: each font under its hashed name, the licence texts, and the stylesheet with the fonts' hashed names written into it, under its own hashed name. Every page links `<link rel="stylesheet" href="<up>assets/look.<hash>.css">` in place of the `<style>` block.

**The site check** (`src/shopper/check.py`) already refuses a `<link>` or a `src` to another origin and asks every relative `href` to resolve to a file in the build, and a fragment to an id on the page (so the barcode's `href="#ean"` needs its `id="ean"`). It gains:

- a page links exactly one stylesheet, the build's, at the page's own depth, and holds no `<style` and no `style=`;
- the stylesheet holds no `@import`, and every `url(` in it is a bare file name that is in `assets/` and ends `.woff2`;
- `assets/` holds nothing but the stylesheet, the fonts it names and the licence texts.

**The upload.** `src/basket/site.py` refuses a file with no content type, so `CONTENT_TYPES` gains `.css` (`text/css; charset=utf-8`), `.woff2` (`font/woff2`) and `.txt` (`text/plain; charset=utf-8`), and `upload` sends `assets/` before any page. An asset is put only when the bucket has no object of that name: the name carries the hash of the bytes, so one that is there is the same file, and no morning piles up a new version of a file that did not change. `scripts/publish.sh` gains three allowlisted syncs before its `*.html` one, each with its content type.

**Nothing in the code deletes, so old hashed files stay** in the site bucket: about 21 KB for each change of the stylesheet and 43 KB if the fonts are ever remade. A page cached for its five minutes still finds the stylesheet it names. Every file is sent with `max-age=300` today; the assets could be kept for a year, since a name never changes its bytes, which needs its own `Cache-Control` at upload and is left as a later step.

## What changes in the code

No function changes what it computes, but for the two counts under "Calls".

- **`src/shopper/shell.py`:** `page` links the stylesheet in place of the `<style>` block and takes the page's kind, written as a class on `<body>` (`t-front`, `t-store`, `t-product`, `t-browse`, `t-method`, `t-record`, `t-basket`); its `style` argument goes. `band` gives the name's link `class="brand"` and writes it as `<b>Deal</b> or No Deal` (the green box around the first word), and writes the chains' line on the front page only.
- **`src/basket/page.py`:** `Frame` carries the stylesheet's link and the body's class, so `basket.html` takes the frame's head; the stand-alone pages keep `STYLE`.
- **`src/shopper/pages.py`:** the style constants go (`PAGE_STYLE`, `ROOT_STYLE`, `STORE_STYLE`, `METHOD_STYLE`, `RECORD_STYLE`). `render_root` writes the headline with DEAL and NO DEAL each in a `<span>` (`class="yes"`, `class="no"`), and a store page's title question has its last word in `<span class="yes">`. `_picker` wraps each chain in `<div class="chain">` and adds each store's count when it is known. `_hiring` drops the dots between its links. `_row` writes the badge without "At <store>:" (decided) and `_deals` gives the table its roles (`role="table"`, `rowgroup`, `row`, `columnheader`, `rowheader`, `cell`), which a phone's block layout would otherwise take away. `render_store` puts the headline's two numbers in a `<b>`. The method page gains its row of section links.
- **`src/shopper/product.py`:** `BADGE_STYLE` and `PRODUCT_STYLE` go. `_section` builds the label: `<div class="tag <class>">` holding `<div class="say">` (the verdict as `<p class="verdict">At <store>: <b>DEAL · ₪5.00 off</b></p>`, or the plain line; the reason; the conditions; a coming sale) and `<div class="pay">` (the price line; the barcode's mark). `render_product` writes the barcode's drawing once after the barcode line. `_row` writes each badge as the name, a hidden separator and the verdict in a `<b>`. The chart, its key and its table go in `<div class="history">`; the two facts get `class="fact"`.
- **`src/shopper/chart.py`:** rewritten to the markup above. `render_chart(found, day)` draws from the verdict and the day alone: the one line's last point is the verdict's today's price (2026-11-16; the first build also took today's listed price, for the shelf line). `DAY_WIDTH`, the label column and `_placed`'s labels go; the axis, the dates and the table come.
- **A new module for the barcode**, for example `src/shopper/barcode.py`: the modules of a code, and its drawing.
- **`src/shopper/words.py`:** the front page's headline and its line (`FRONT_TITLE` stays the store pages'; the root page gets its own two constants); the price line ("Price today: ₪14.00", from `price_text`); the table's four heads; the short date ("13 Nov"); `chart_summary` and the table take lowest and highest over the tracked days and today; `reason` and `last_low` name "days with a known price" when `len(found.priced)` differs from `len(found.days)` ("Word changes", 3).
- **`src/shopper/search.py`:** `BROWSE_STYLE` goes.
- **`src/shopper/build.py`, `src/shopper/check.py`, `src/basket/site.py`, `scripts/publish.sh`:** as under "The shared stylesheet and the font files".
- **`src/shopper/static/search.js`: no change.** Its hooks stay as they are: `#pick-link` inside `p.store`, `#pick` with `data-page`, `main[data-store]`, `nav.badges`, `a[data-column]`, `section[data-column]`, `h2.elsewhere`, `.not-sold`, `#q`, `#results`, and the `js` class it puts on `<html>`. The preview runs the live script unchanged against the new markup.

## What the tests should pin

1. **Contrast, from the stylesheet.** A test reads the light and dark token sets out of `look.css`, computes every pair of the table above in both themes, and fails under the line. A new use of a colour adds a pair; the words on each of the three greens are three of them, so the S5 contrast test in `tests/test_product.py` moves here and reads the stylesheet.
2. **No colour outside the tokens.** No colour is written in the stylesheet outside the two `:root` blocks; every `var(--x)` used is defined.
3. **Nothing from outside.** The check's new rules, each with a page or a stylesheet that breaks it: a second stylesheet, a `<style` block, a `style=`, an `@import`, a `url(` with a scheme, a slash or a name not in `assets/`.
4. **The chart cannot shrink its words.** The only SVG of a chart with a `viewBox` is the lines' one, and it holds no `<text>`; it has `preserveAspectRatio="none"`; the stylesheet gives every stroke under `.chart` `vector-effect:non-scaling-stroke`; the stylesheet's chart sizes are at least 12 pixels.
5. **The chart's rules:** the axis (round steps, two to five, no price on the bottom line); one line of the price paid each day, a sale its green stretch; seven days or fewer with no price dotted, more left open; the usual price's dashes only where the line is not; the dates by span; today's price at the line's end, or "today" alone; lowest and highest counting today; the table's cells by call.
6. **The barcode:** as under "The barcode".
7. **The words:** the label's text is `badge(found)`; the front page's headline and line, the price line and the chart's dates are the decided words; `reason` and `last_low` in both forms, with equal counts ("days tracked") and unequal ("days with a known price"); a store row's badge is the verdict without the store's name; the stylesheet's phone label for the usual price is `FRONT_HEADS[3]`.
8. **The table's roles**; **the hidden rule** (`[hidden]`); every two-column rule under `.js`.
9. **The fonts:** each committed file's SHA-256 is the one its `README` gives; the build's `assets/` holds them under their hashed names with both licence texts.
10. **Bytes.** The stylesheet under 22,000 bytes; the three fonts under 45,000 together; the largest product page of the golden build under 45,000 (store-first.md's line).
11. **The golden pages pinned anew** (`tests/golden/golden-90.sha256`, `GOLDEN_90_REPIN=1`), the reason in the commit: every page's bytes change.

## Page bytes

Measured on the live pages of 14 November 2026 and on the same pages in this design (the build with the yellow NO DEAL). "Gzipped" is `gzip -6`.

| Page type | Bytes now | Bytes after | Change | Gzipped now | Gzipped after |
|---|---|---|---|---|---|
| Front page | 6,765 | 3,064 | -3,701 | 2,443 | 1,181 |
| Store page, no rows yet (the 9 live pages, mean) | 10,366 | 4,428 | -5,938 | 3,657 | 1,841 |
| Store page with 14 rows (example) | 15,801 | 10,449 | -5,352 | 4,702 | 2,902 |
| Product page, 9 parts (14 live pages, mean) | 22,068 | 24,227 | +2,159 | 4,474 | 3,113 |
| Product page, 9 parts, 90-day charts (example) | 24,873 | 29,300 | +4,427 | 5,219 | 4,292 |
| Browse page, alef (1,571 names) | 262,754 | 258,448 | -4,306 | 33,899 | 32,238 |
| Browse page, other (667 names) | 115,141 | 110,835 | -4,306 | 17,715 | 16,137 |
| Method page | 63,174 | 54,895 | -8,279 | 17,809 | 15,547 |
| Record page | 15,240 | 10,782 | -4,458 | 3,459 | 2,035 |
| Basket page | 38,438 | 29,876 | -8,562 | 7,819 | 5,468 |
| The stylesheet (new, once) | | 20,928 | | | 5,316 |
| The three fonts (new, once) | | 43,152 | | | (already compressed) |

- **A product page grows** by 1,689 to 3,871 bytes on the 14 measured, though its inline style goes: the label, the price line, the barcode and the richer chart cost more than the style block saved. A store type's part costs: the chart 632 bytes on average (568 to 874) against 565 for today's chart with its key; its key 59; its table 222; the barcode's mark 146; and the barcode's drawing 222 once a page. Sent gzipped, the same pages shrink, from 4,474 to 3,113 bytes on average.
- **The largest of the 14** goes from 26,488 to 30,359 bytes. All 14 are sold at all nine store types, the heaviest kind of page.
- **Against the 45,000-byte line.** The largest page of a whole build was not measured here. store-first.md gives 39,264 bytes for the largest page of its day; a page of that size growing as the 14 did at most (+3,871), or as the 90-day example did (+4,427), would be about 43,100 to 43,700 bytes: under the line by about 1,300 to 1,900. That is close, so the builder measures the largest real page first. If it is over, what goes first: the digits under each label's barcode (29 bytes a part), then the barcode's mark in every part but the first shown (146 a part).

## Cost (monthly, estimate)

Rates are the ones shopper-site.md's "Cost" uses for il-central-1 ($0.025 a GB-month of storage, $0.0055 for 1,000 writes); UNVERIFIED: not read from AWS's price list for this design.

- **Storage.** About 2,159 bytes more on each product page, by the 14 measured (the heaviest kind, so an upper figure), on about 25,000 pages (shopper-site.md's "about 22,000 to 25,000") is 54 MB more a morning. Over the 30 days of old versions the site bucket keeps, 1.62 GB more held: **about $0.04 a month more**. The assets are 73 KB, once.
- **Writes.** The six assets are put only when new: nothing a month.
- **Transfer.** A first visit fetches 64 KB more (the stylesheet and three fonts), then nothing. Inside CloudFront's free tier as before.
- **Lambda.** The same pages and 54 MB more to upload each morning; the run's time was not measured for this design and is read on the first morning.
- **Total: about $0.04 a month more.**

## Word changes

All decided (the owner, 2026-11-15); none is waiting.

1. **The front page's headline: "DEAL OR NO DEAL?"** (written "Deal or No Deal?", set in capitals), in place of "Is it actually a deal?" there. The nine store pages keep "Is it actually a deal?".
2. **The line under it:** "Find out if a sale is actually a deal: pick the store you're in, then look up the product. Each sale is checked against what it usually costs there."
3. **One "days tracked" on a page.** "Days tracked" stays every tracked day, sale days of unknown price included (S7's count), which "How often on sale" counts: since 2026-11-16 it says them as the days before today, "On sale on 21 of the 86 days before today." (`how_often`; the owner: today is not a tracked day, so beside a Deal today "On sale on 0 of the 13 days tracked" read wrong). A line that rests only on the days with a known price says "days tracked" when the two counts are equal, as today, and names its own count when they differ:
   - `reason` (line 361, all three of its forms): "Usually ₪22.90, sales included (83 days with a known price)."; "It's been ₪10.90 or less on 9 of the 9 days with a known price."; "Only ₪0.40 below its usual ₪3.20 (12 days with a known price)."
   - `last_low` (line 394): "Lowest in the 83 days with a known price."
   - One day is "1 day with a known price". The two counts are `len(found.priced)` and `len(found.days)`; they differ by the sale days whose price could not be read (three in the preview's example). Tests pin both forms of each line: equal counts and unequal.
4. **Each store's label on the front page carries its count: "1,347 promotions today"**, the number the store's own page already states ("Today Carrefour Market lists 1,347 promotions ..."). A store whose promotions could not be read that day shows its name alone, with no figure and nothing in its place (Osher Ad on 14 November).
5. **The chart's table heads: "Lowest", "Highest", "Today".** They replace the chart's side labels ("highest ₪24.90", "lowest ₪19.90", "today ₪17.90"); "usually ₪22.90" stays, written at its height. "Usual" was a fourth head until 2026-11-16: the chart writes the usual price at its own height and the label's reason says it.
6. **Short dates in the chart and its table: "16 Aug", "13 Nov", and month names "Sep", "Oct", "Nov"**; "today" as the date of a lowest or highest that is today's. Sentences keep the long form ("ended 11 November").
7. **A spoken label for the method page's row of links: "On this page"** (`aria-label`, read by screen readers, not shown).
8. **The four earlier ones**: "Price today: ₪14.00"; the first date along the chart's bottom, and "today" under today's price at the line's end (on the dates' line only when today has no price); the chains' line on the front page only; a store row's badge without "At <store>:".
9. **The chart's key says "on sale" and "on sale, price not read", and nothing else** (2026-11-16): the plain line needs no name, so "shelf price" is gone from the product pages and the method page; the fold-out and the method page say "listed price" with its definition.

Following from these, not new words: the chart's spoken summary changes its numbers where today is a new low or high ("lowest ₪17.90" for "lowest ₪19.90"); "Usually" stands before the usual price in a phone's store row (the column's own head, written by the stylesheet); the product's barcode digits show a second time, under the bars; the front page's tab title becomes "Deal or No Deal".

## Calls made in this design (the owner can overturn any)

1. **Three greens for a Deal, by its saving**: store-first's S5 kept, the words on every green the same dark ink. ("The deal shades".)
2. **The chart's sale line is green**, the deal's colour, and today's sale price beside it. (The yellow draft had it red.)
3. **Lowest and highest count today's price**, in the table and in the chart's spoken summary. ("The chart".)
4. **The barcode is kept**, as a true EAN-13 or EAN-8 made by the build and pinned by a test; a code that is neither gets no bars. ("The barcode".)
5. **The chart's side labels become a table**, and today's dashed line across the chart goes: today's price is written at the line's end.
6. **Today is drawn as a day**: the line runs through today's price, and a sale that starts today is the step down and one green day ending in its dot.
7. **The usual price is dashes wherever the line is not** (call 22; until 2026-11-16 a dotted line with the data's own gaps).
8. **The chart has no pixels-a-day rule**: it takes its column's width.
9. **A self-hosted typeface** in three files, 43,152 bytes, and with it a shared `assets/` folder. The earlier design took none; this look is its type.
10. **No link colour**: links are ink, underlined.
11. **The store's name over a label shows only where the label does not say it.**
12. **The chains' headings in the picker are kept for screen readers and not shown.**
13. **A not-sold line is drawn as an empty slot**, a dashed outline.
14. **The product page in two columns on a desktop**, laid out by the stylesheet alone, only while the script runs.
15. **The basket's lowest total in ink, not green**: green stays the mark of a deal. A store's label on the front page turns to ink under the pointer for the same reason.
16. **The header's wordmark keeps "OR NO DEAL" plain**; only the big headline dresses NO DEAL.
17. **The price part of a label stays paper**; only its edge takes the label's colour.
18. **Hebrew names keep `dir="rtl"` and stay left-aligned.**

The one line's, after the owner's read of 2026-11-16 ("The chart"):

19. **Sale days are the line itself in green, heavier, with green steps**; not a segment over an ink line.
20. **The listed price of a sale day is drawn nowhere**; the axis fits the prices paid.
21. **"today" moves from the dates' line to under today's price**, and stays on the dates' line only when today has no price.
22. **The usual price's dashes are left out where the line runs within 6 pixels of them**; its words stand 8 pixels above the level (6 in the first build, where a "y" and its halo nicked a line running along the level) and may stand in the chart's top margin.
23. **The dotted stretch takes the colour of the day it carries**, so a sale with a missing morning in it stays one green notch.
24. **A sale day that cost the regular price** (a promotion counted and was no cheaper) is green at the regular price's height: on sale, no lower.
25. **The key has no entry for the plain line**, and no key at all when nothing needs words.
26. **`chart_summary` keeps its words.**
27. **The date line and the dates' marks take the second ink at 1 pixel.**

## Left to the builder

- The stylesheet's exact spelling; the appendix is the reference for values.
- The chart's code, its tests and mutations, and the barcode's.
- The largest real product page against 45,000 bytes, before anything else is built on the markup.
- The site run's time and memory on the first morning.
- A look in Safari on an iPhone, in Firefox, on Windows and on Android before the owner's read. The preview was drawn in Chrome on macOS only. What to look at: the lines' SVG as a stretching flex item; `vector-effect: non-scaling-stroke` and the dashes under it; `<use>` of the barcode from a part that is hidden; `size-adjust`; `:has()` (it only hides a heading the label repeats, so a browser without it shows the store's name twice); `text-wrap: balance` on a long verdict; the variable font's weights.
- A real scan of a drawn barcode from a phone's screen, light and dark.
- Windows' high-contrast mode (`forced-colors`): not designed. Verdicts say everything in words; the filters' checked state and the chart's strokes should be checked.
- States the live site did not show on 14 November and the preview draws from examples: a store's table with rows; a 90-day chart; "Not sold ... today"; "days with a known price". States not drawn at all: a weighed product's label ("a kilogram"); "New today"; too few files; a revised basket day; the record page once a forecast is scored.
- The assets' own `Cache-Control`, if wanted.

## How this was checked

- The live pages of 14 November 2026 were downloaded (the front page, the nine store pages, 14 product pages, two browse pages, the method, record and basket pages, the script and two search pieces), and this design's stylesheet and markup were applied to copies by a script, each live chart redrawn from its own geometry.
- Four pages the live site cannot show yet were made as examples and restyled: a product with 90-day charts and a store page with 14 rows, from invented prices drawn by the project's own code in an earlier round; a store page with the list the script writes for two typed letters, frozen from a real search piece; and a product not sold at the picked store, made from a live page by taking a store type's part out.
- **The layout** was drawn in full in the draft before the owner's change of colour, when a deal was yellow: fifteen pages in headless Chrome at 390 and 1,280 pixels wide, light and dark (60 pictures), with the live script running, a store picked or none. Measured on each: none scrolls sideways at either width; no chart text is under 12 pixels; the plot is 248 pixels wide at 390 and 602 at 1,280 on every product page. One product page was also drawn at 320 pixels wide: it does not scroll sideways and its plot is 178 pixels wide.
- **With green deals**, both NO DEAL variants were built as whole previews, and four pages of each were drawn again at both widths, light and dark (32 pictures): the front page with the new headline and line, a product with a Deal and No deal rows beside it (the 90-day example, with all three greens), a product with No deal, and a store page with rows. The same measures hold on all 32: none scrolls sideways, no chart text under 12 pixels. The other page types were not drawn again in green; nothing but colour changed on them.
- Things to tap, measured at 390 pixels wide in the yellow draft's preview (pixels high; green changed no size): the header's store line 43; a fold-out's title 51; a row of "Elsewhere today" 48; a filter 43; a browse letter 46; a store's label on the front page 102; the search box 55; a name in the search results 35; a name on a browse page 35; a name in a store's table 25; a link in the method page's row 34; one of the front page's four links 37. The header is 124 pixels high with a store picked (186 today).
- The contrast table is the output of a script that reads both variants' stylesheets; the fonts' sources were fetched at their commits and their SHA-256 compared; the three subsets were made twice and came out the same.
- The previews and the screenshots are throwaway and are not in the repository.

## Appendix: the stylesheet

`src/shopper/static/look.css` as built, written with the yellow NO DEAL's three tokens and the one line's chart rules (2026-11-16): 20,901 bytes as written here, 20,945 once the build has written the fonts' hashed names into its four `url(...)`.

```css
@font-face{font-family:Shelf;src:url(archivo-text.woff2) format("woff2");font-weight:400 700;font-display:swap;unicode-range:U+0020-007E,U+00A0-00FF,U+2013-2014,U+2018-2019,U+201C-201D,U+2022,U+2026,U+2190,U+2192,U+2212}
@font-face{font-family:Shelf;src:url(heebo-hebrew.woff2) format("woff2");font-weight:400 700;font-display:swap;unicode-range:U+0590-05FF,U+20AA}
@font-face{font-family:"Shelf Narrow";src:url(archivo-narrow.woff2) format("woff2");font-weight:800;font-display:swap;unicode-range:U+0020-007E,U+00A0-00FF,U+2013-2014,U+2018-2019,U+201C-201D,U+2022,U+2026,U+2190,U+2192,U+2212}
@font-face{font-family:"Shelf Narrow";src:url(heebo-hebrew.woff2) format("woff2");font-weight:800;font-display:swap;size-adjust:84%;unicode-range:U+0590-05FF,U+20AA}
:root{color-scheme:light dark;--bg:#ffffff;--ink:#111111;--ink-2:#555555;--line:#d6d6d6;--soft:#f1f1ee;--d1:#c8f1d5;--d2:#6fdc9b;--d3:#22b35e;--on-deal:#111111;--nd:#ffd60a;--on-nd:#111111;--nd-edge:#111111;--sale:#0b7a3b;--plate:#ffffff;--bars:#111111;--rule:2.5px solid var(--ink);--text:Shelf,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--narrow:"Shelf Narrow","Arial Narrow","Roboto Condensed",Impact,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#131313;--ink:#f2f2ef;--ink-2:#b4b4b0;--line:#3d3d3a;--soft:#222220;--d1:#27995a;--d2:#34b76a;--d3:#4fe08c;--nd:#ffd60a;--on-nd:#111111;--nd-edge:#ffd60a;--sale:#4fe08c}}
.deal-1{--fill:var(--d1)}
.deal-2{--fill:var(--d2)}
.deal-3,.brand b,h1 .yes{--fill:var(--d3)}
.deal-1,.deal-2,.deal-3,.brand b,h1 .yes{--edge:var(--ink)}
@media (prefers-color-scheme:dark){.deal-1,.deal-2,.deal-3,.brand b,h1 .yes{--edge:var(--fill)}}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:400 1rem/1.5 var(--text)}
[hidden]{display:none!important}
.wrap,main{max-width:72rem;margin:0 auto;padding:0 1rem}
a{color:inherit;text-decoration-thickness:1.5px;text-underline-offset:.2em}
a:hover{text-decoration-thickness:3px}
:focus-visible{outline:3px solid var(--ink);outline-offset:3px;border-radius:2px}
h1,h2,h3,p,ul,ol,dl,dd{margin:0}
h1{font:800 2.5rem/.95 var(--narrow);letter-spacing:-.005em;text-transform:uppercase}
h2{font:800 1.375rem/1.05 var(--narrow);letter-spacing:.02em;text-transform:uppercase}
h3,.at,.verdict,.price,thead th,.stats th,.tile dt{font:600 .75rem/1.35 var(--text);letter-spacing:.09em;text-transform:uppercase}
main p,main li{max-width:44rem}
small{font-size:.8125rem}
main{padding-top:2rem;padding-bottom:1rem}
.lede{margin-top:1rem;font-size:1.125rem;line-height:1.45}
.band{border-bottom:var(--rule)}
.band .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:0 1.5rem;padding-top:.5rem;padding-bottom:.5rem}
.brand{margin-right:auto;padding:.3rem 0;font:800 1.375rem/1 var(--narrow);letter-spacing:.02em;text-transform:uppercase;text-decoration:none;white-space:nowrap}
.brand b{display:inline-block;margin-right:.1em;padding:.2em .32em .14em;border:2px solid var(--edge);border-radius:3px;background:var(--fill);color:var(--on-deal)}
.dateline{flex-basis:100%;color:var(--ink-2);font-size:.8125rem}
.store{order:3;font-size:.9375rem;font-weight:600}
.store a{display:inline-block;padding:.65rem 0}
.store a:first-child:not(:only-child){text-decoration:none}
footer{margin-top:3.5rem;border-top:var(--rule)}
footer p{max-width:46rem;padding:1.1rem 0 2.5rem;color:var(--ink-2);font-size:.8125rem;line-height:1.55}
footer a{color:var(--ink);font-weight:600}
.table{overflow-x:auto;margin-top:1rem}
table{width:100%;border-collapse:collapse;font-size:.9375rem;font-variant-numeric:tabular-nums}
th,td{padding:.7rem 1rem .7rem 0;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th:last-child,td:last-child{padding-right:0}
thead th{border-bottom:var(--rule);color:var(--ink-2);vertical-align:bottom}
th small,td small,section small{display:block;color:var(--ink-2);font-weight:400}
details{margin-top:1.5rem;border-top:1px solid var(--line);border-bottom:var(--rule)}
summary{padding:.85rem 0;font-weight:700;cursor:pointer}
details>:not(summary){margin-bottom:.85rem;font-size:.9375rem}
details ul{padding-left:1.25rem}
details li{margin-bottom:.4rem;break-inside:avoid}
details .note{color:var(--ink-2);font-size:.8125rem}
details h3{margin-top:1rem}
.story-head{font-weight:700}
.badge,.verdict b,.price b,.stats td{font-variant-numeric:tabular-nums}
span.badge,nav .badge b{display:inline-block;padding:.28em .55em .22em;border:1.5px solid var(--ink);border-radius:3px;font:700 .8125rem/1.2 var(--text);white-space:nowrap}
span.badge:is(.deal-1,.deal-2,.deal-3),nav :is(.deal-1,.deal-2,.deal-3) b{border-color:var(--edge);background:var(--fill);color:var(--on-deal)}
span.badge.no-deal,nav .no-deal b{border-color:var(--nd-edge);background:var(--nd);color:var(--on-nd)}
.warn,.few{margin-top:1.25rem;padding:.35rem 0 .35rem .875rem;border-left:.375rem solid var(--ink);font-weight:600}
.hero{padding:2.25rem 0 2.25rem}
.hero h1{font-size:4.4rem;line-height:.88}
h1 .yes,h1 .no{display:inline-block;margin:.04em 0 0 -.06em;padding:.07em .14em 0;border:3px solid var(--ink);border-radius:6px}
h1 .yes{border-color:var(--edge);background:var(--fill);color:var(--on-deal)}
h1 .no{margin-left:0;border-color:var(--nd-edge);background:var(--nd);color:var(--on-nd)}
.hero .lede{max-width:31rem;margin-top:1.4rem}
#pick{padding-top:.9rem;border-top:var(--rule)}
#pick h2{font-size:1.625rem}
#pick h3{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
#pick{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}
#pick h2{grid-column:1/-1;margin-bottom:.4rem}
#pick .chain,#pick ul{display:contents}
#pick li{display:block;max-width:none}
#pick a{display:flex;flex-direction:column;justify-content:space-between;height:100%;min-height:6.4rem;padding:.7rem .8rem .6rem;border:2px solid var(--ink);border-radius:5px;font-weight:700;line-height:1.2;text-decoration:none}
#pick a:hover{background:var(--ink);color:var(--bg)}
#pick small{margin-top:.8rem;color:var(--ink-2);font-size:.6875rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase;white-space:nowrap}
#pick small b{display:block;color:var(--ink);font:800 2.125rem/.95 var(--narrow);letter-spacing:0;font-variant-numeric:tabular-nums}
#pick a:hover small,#pick a:hover b{color:var(--bg)}
.hiring{display:flex;flex-wrap:wrap;gap:.25rem 1.75rem;max-width:none;margin-top:1.75rem}
.hiring a{padding:.5rem 0;font-size:.875rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;text-decoration-thickness:2px;text-underline-offset:.3em}
.at{color:var(--ink-2)}
.t-store h1{margin-top:.5rem;font-size:2.75rem;line-height:.9}
.sub{max-width:34rem;margin-top:1rem;font-size:1.0625rem}
.search{margin-top:1.75rem}
.search label{display:block;margin-bottom:.4rem;font-weight:700}
.search input{width:100%;padding:.8rem .9rem;border:2.5px solid var(--ink);border-radius:5px;background:var(--bg);color:var(--ink);font:inherit;font-size:1.0625rem}
.search p{font-size:.9375rem}
.search p a{display:inline-block;padding:.7rem 0 0}
#results ul,.t-browse ul.names{padding:0;list-style:none}
#results li,.t-browse ul.names li{max-width:none;padding-bottom:.5rem;border-bottom:1px solid var(--line);break-inside:avoid}
#results a,table.front th a,.t-browse ul.names a{display:block;padding:.6rem 0 .1rem;font-weight:700;text-decoration:none}
#results small,.t-browse ul.names small{color:var(--ink-2);font-variant-numeric:tabular-nums}
#results p{margin-top:.75rem}
.t-store main>.lede{max-width:none;margin-top:2.25rem;padding-top:.9rem;border-top:var(--rule);font-size:1.375rem;font-weight:700;line-height:1.25}
.t-store .lede b{font:800 1.3em/1 var(--narrow);font-variant-numeric:tabular-nums}
.deals{margin-top:.5rem}
.deals>input{position:absolute;opacity:0}
.deals>label{display:inline-flex;align-items:center;gap:.6rem;margin-right:1.5rem;padding:.65rem 0;font-size:.9375rem;font-weight:600;cursor:pointer}
.deals>label::before{content:"";flex:none;width:1.25rem;height:1.25rem;border:2px solid var(--ink);border-radius:3px}
.deals>input:checked+label::before{background:var(--ink);box-shadow:inset 0 0 0 3px var(--bg)}
.deals>input:focus-visible+label{outline:3px solid var(--ink);outline-offset:3px}
#f-club:checked~.table tbody tr[data-club],#f-spend:checked~.table tbody tr[data-spend]{display:none}
table.front th{font-weight:400}
table.front th a{padding:0 0 .15rem}
table.front td+td{font-weight:700}
table.front td+td+td{color:var(--ink-2);font-weight:400}
.t-product h1{font:700 1.875rem/1.15 var(--text);letter-spacing:0;text-transform:none}
.t-product .names{margin-top:.6rem;padding:0;list-style:none;color:var(--ink-2);font-size:.875rem;line-height:1.55}
.names .as-listed{color:var(--ink);font-weight:500}
.names+p{margin-top:.5rem;color:var(--ink-2);font-size:.875rem;font-variant-numeric:tabular-nums}
.t-product section[data-column]>h2{margin-top:1.75rem;font:600 .75rem/1.35 var(--text);letter-spacing:.09em;color:var(--ink-2)}
.t-product section[data-column]:has(.verdict b)>h2{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.tag{margin-top:1.5rem;border:2.5px solid var(--ink);border-radius:5px;overflow:hidden}
section[data-column]>h2+.tag{margin-top:.5rem}
section[data-column]:has(.verdict b)>h2+.tag{margin-top:1.5rem}
.tag:is(.deal-1,.deal-2,.deal-3){border-color:var(--edge)}
.tag.no-deal{border-color:var(--nd-edge)}
.say{display:flex;flex-direction:column;padding:1.1rem 1.1rem 1rem}
:is(.deal-1,.deal-2,.deal-3)>.say{background:var(--fill);color:var(--on-deal)}
.no-deal>.say{background:var(--nd);color:var(--on-nd)}
.verdict b{display:block;margin-top:.55rem;font:800 3.25rem/.9 var(--narrow);letter-spacing:-.005em;text-transform:none;text-wrap:balance}
.tag.none .verdict{font:800 1.875rem/1 var(--narrow);letter-spacing:0;text-transform:none}
.reason{margin-top:auto;padding-top:.8rem;font-weight:500;line-height:1.35}
.conditions{margin-top:.35rem;font-weight:700}
.say>p:not([class]){margin-top:.6rem}
.pay{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:1rem;padding:1rem 1.1rem;border-top:2.5px solid var(--ink)}
:is(.deal-1,.deal-2,.deal-3)>.pay{border-color:var(--edge)}
.no-deal>.pay{border-color:var(--nd-edge)}
.price b{display:block;margin-top:.45rem;font:800 4rem/.8 var(--narrow);letter-spacing:0;text-transform:none;white-space:nowrap}
.price i,.price sup{font-style:normal;font-size:.44em;line-height:1;vertical-align:top;position:relative;top:-.04em}
.price i{margin-right:.08em}
.price small{margin-top:.5rem;letter-spacing:0;text-transform:none}
.code{flex:none}
.defs{position:absolute;width:0;height:0}
.code svg{display:block;width:8.90625rem;height:2.1rem;shape-rendering:crispEdges}
.code svg.short{width:6.28125rem}
#ean{fill:none;stroke:var(--bars);stroke-width:1}
.code small{margin-top:.2rem;color:var(--ink);font-size:.6875rem;letter-spacing:.3em;font-variant-numeric:tabular-nums}
@media (prefers-color-scheme:dark){.code svg{box-sizing:content-box;padding:.4rem .6rem .4rem .95rem;border-radius:3px;background:var(--plate)}}
.not-sold{max-width:none;margin-top:1.5rem;padding:1.1rem;border:2.5px dashed var(--ink);border-radius:5px;font:800 1.875rem/1.05 var(--narrow)}
section .not-sold{margin-top:.5rem}
.chart{display:flex;align-items:flex-start;margin-top:1.75rem;font-size:.78125rem;font-weight:500;font-variant-numeric:tabular-nums}
.chart svg{display:block;flex:none;overflow:visible}
.chart .ax,.chart .over,.chart .now{height:224px}
.chart .ax{width:46px;text-anchor:end}
.chart .now{width:64px}
.chart .plot{position:relative;flex:1 1 auto;min-width:0}
.chart .lines{width:100%;height:200px;border-bottom:1px solid var(--ink-2)}
.chart .over{position:absolute;left:0;top:0;width:100%;pointer-events:none}
.chart path,.chart line{fill:none;vector-effect:non-scaling-stroke}
.chart text{fill:var(--ink-2)}
.chart .grid{stroke:var(--line)}
.chart .usual{stroke:var(--ink-2);stroke-dasharray:6 4}
.chart .gap{stroke:var(--ink);stroke-width:2;stroke-dasharray:2 3}
.chart path.paid{stroke:var(--ink);stroke-width:2}
.chart path.sale{stroke:var(--sale);stroke-width:3.5}
.chart .unread{stroke:var(--sale);stroke-width:7;stroke-dasharray:2 2}
.chart line{stroke:var(--ink-2)}
.chart circle.paid{fill:var(--ink)}
.chart circle.sale{fill:var(--sale)}
.chart text.paid,.chart text.sale{font-size:.9375rem}
.chart text.paid{fill:var(--ink)}
.chart text.sale{fill:var(--sale)}
.chart .now,.chart text.end{font-weight:700}
.chart text.usually,.chart text.end{fill:var(--ink)}
.chart text.usually{text-anchor:end;font-weight:600;paint-order:stroke;stroke:var(--bg);stroke-width:5px;stroke-linejoin:round}
.key{margin-top:.9rem;color:var(--ink-2);font-size:.8125rem;font-weight:500}
.key i{display:inline-block;width:1.4em;margin-right:.45em;border-top:3.5px solid var(--sale);vertical-align:middle}
.key .unread{height:7px;border:0;background:repeating-linear-gradient(90deg,var(--sale) 0 2px,transparent 2px 4px)}
.stats{margin-top:1.4rem;border-top:var(--rule)}
.stats th,.stats td{padding:0;border:0}
.stats th{padding-top:.6rem;color:var(--ink-2)}
.stats td{padding-bottom:.6rem;font:800 1.625rem/1.1 var(--narrow)}
.stats small{margin-top:.15rem;font:500 .78125rem/1.2 var(--text)}
.fact{max-width:none;padding:.7rem 0;border-top:1px solid var(--line)}
section[data-column]>details{margin-top:0}
.today small,ul.deals small{display:block}
.elsewhere{margin-top:2.5rem;padding-top:.7rem;border-top:var(--rule)}
nav.badges{display:grid;margin-top:1.5rem;border-top:1px solid var(--line)}
.elsewhere:not([hidden])+nav.badges{margin-top:.6rem;border-top:0}
nav .badge{display:flex;align-items:center;justify-content:space-between;gap:.75rem;min-height:3rem;border-bottom:1px solid var(--line);font-weight:600;text-decoration:none}
nav .badge i{display:none}
nav .none b{padding-right:0;border-color:transparent;color:var(--ink-2);font-size:.875rem;font-weight:400;white-space:normal;text-align:right}
.t-product main>.lede{margin-top:2rem;color:var(--ink-2);font-size:.8125rem;line-height:1.5}
.letters{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:1.25rem;padding:0;list-style:none}
.letters a{display:block;min-width:2.75rem;padding:.55rem .5rem;border:2px solid var(--ink);border-radius:3px;font-weight:700;text-align:center;text-decoration:none}
.letters a[aria-current]{background:var(--ink);color:var(--bg)}
.t-browse ul.names{margin-top:1.5rem;border-top:var(--rule)}
.toc{margin-top:1.5rem}
.toc ol{display:flex;flex-wrap:wrap;gap:.1rem 1.5rem;padding:0;list-style:none}
.toc a{display:inline-block;padding:.35rem 0;font-size:.9375rem;font-weight:600}
main>section,#scorecard>section{margin-top:2.5rem;padding-top:.9rem;border-top:var(--rule)}
main>section[data-column],main>.search,main>.deals,main>#pick,.t-browse main>section{margin-top:0;padding-top:0;border-top:0}
main>.search{margin-top:1.75rem}
main>.deals{margin-top:.5rem}
main>#pick{padding-top:.9rem;border-top:var(--rule)}
section>p,section>ul,section>ol,#scorecard>p,section>section{margin-top:.75rem}
section>section{padding-top:.75rem;border-top:1px solid var(--line)}
main>section ul,.notes ul{padding-left:1.25rem}
main>section li,.notes li{margin-bottom:.4rem}
ol.rules,ol.bars{padding:0;list-style:none}
ol.rules li{display:grid;gap:.25rem;max-width:none;padding:.8rem 0;border-top:1px solid var(--line)}
ol.rules li>span{color:var(--ink-2)}
.t-method details ul,.t-basket details ul{columns:3 13rem;column-gap:1.5rem;font-size:.8125rem}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem;margin-top:1.5rem}
.tile{padding:.8rem .9rem;border:2px solid var(--ink);border-radius:5px}
.tile.gap{grid-column:1/-1}
.tile.lowest{background:var(--ink);color:var(--bg)}
.tile dd{font-size:.9375rem}
.tile dd.figure{margin:.3rem 0 .1rem;font:800 2.5rem/.95 var(--narrow);font-variant-numeric:tabular-nums}
.headline{margin-top:1.5rem;font-size:1.375rem;font-weight:700;line-height:1.25}
.headline+p{margin-top:.4rem}
.revised{margin-top:1rem;padding:.35rem 0 .35rem .875rem;border-left:.375rem solid var(--ink);font-weight:600}
ol.bars li{display:grid;grid-template-columns:1.5rem minmax(0,1fr) auto;grid-template-areas:"rank name total" "rank bar bar" "rank note note";gap:.25rem .75rem;align-items:center;max-width:none;padding:.65rem 0;border-bottom:1px solid var(--line)}
.rank{grid-area:rank;align-self:start;color:var(--ink-2);font-weight:700}
.name{grid-area:name;font-weight:700}
ol.bars .note{grid-area:note;color:var(--ink-2);font-size:.8125rem}
ol.bars svg{grid-area:bar;display:block;width:100%;height:14px}
.fill{fill:var(--ink-2)}
li.lowest .fill{fill:var(--ink)}
.total{grid-area:total;font:800 1.375rem/1 var(--narrow);font-variant-numeric:tabular-nums}
ol.bars li.out{grid-template-areas:"rank name name" "rank note note"}
li.out .name,.out,.left-out th,.left-out td{color:var(--ink-2)}
table.prices{min-width:44rem}
table.prices thead th+th,table.prices td{padding-right:.625rem;text-align:right}
table.prices th[scope=row]{width:22%;font-weight:700}
table.prices th[scope=row] [lang=he]{font-weight:400}
td.low{background:var(--soft);font-weight:700}
tfoot th,tfoot td{border-top:var(--rule);border-bottom:0;font-weight:700}
table.basket{min-width:38rem}
table.columns{min-width:36rem}
table.counts{min-width:44rem}
table.scores{min-width:52rem}
table.calibration{max-width:32rem}
svg.calibration{display:block;width:100%;max-width:14rem;height:auto;margin-top:.75rem}
svg.calibration line{stroke:var(--ink-2);stroke-width:.5}
svg.calibration circle{fill:var(--ink)}
@media (max-width:22.49rem){.stats td{font-size:1.25rem}}
@media (max-width:47.99rem){
.chart .near{display:none}
table.front thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
table.front,table.front tbody{display:block}
table.front tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.3rem 1rem;align-items:start;padding:.9rem 0;border-bottom:1px solid var(--line)}
table.front th,table.front td{display:block;padding:0;border:0}
table.front th,table.front td:only-child{grid-column:1/-1}
table.front td:nth-child(2){grid-row:2/4}
table.front td:nth-child(n+3){text-align:right}
table.front td:nth-child(3){font-size:1.125rem}
table.front td:nth-child(4){font-size:.875rem}
table.front td:nth-child(4)::before{content:"Usually ";content:"Usually "/""}
table.prices th[scope=row],table.prices thead th:first-child{position:sticky;left:0;z-index:1;width:9rem;background:var(--bg);box-shadow:1px 0 0 var(--line)}
}
@media (min-width:48rem){
.wrap,main{padding-left:2rem;padding-right:2rem}
main{padding-top:3rem}
h1{font-size:3.75rem}
.brand{font-size:1.5rem}
.dateline{flex-basis:auto}
.hero{padding:4rem 0 3.5rem}
.hero h1{font-size:8.25rem}
.hero .lede{max-width:34rem;margin-top:2rem;font-size:1.3125rem}
#pick{grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;padding-top:1.1rem}
#pick h2{font-size:2rem}
#pick a{min-height:8.2rem;padding:1rem 1.2rem .9rem;font-size:1.3125rem}
#pick small{font-size:.75rem}
#pick small b{font-size:3rem}
.hiring{margin-top:2.75rem}
.t-store h1{font-size:4.5rem}
.t-store main>.lede{font-size:1.625rem}
.search input,#results{max-width:40rem}
table.front td+td,table.front th+th+th{text-align:right}
table.front td+td{font-size:1.0625rem}
.t-product h1{font-size:2.75rem}
.tag{display:grid;grid-template-columns:minmax(0,1fr) auto}
.say{padding:1.4rem 1.6rem 1.3rem}
.verdict b{font-size:4.5rem}
.tag.none .verdict{font-size:2.5rem}
.reason{font-size:1.0625rem}
.pay{display:block;padding:1.4rem 1.5rem 1.2rem;border-top:0;border-left:2.5px solid var(--ink)}
.price b{font-size:5.25rem}
.code svg{width:11.875rem;margin-top:1.1rem}
.code svg.short{width:8.375rem}
.not-sold{font-size:2.5rem}
.stats td{font-size:2rem}
.t-browse ul.names{columns:3 17rem;column-gap:2.5rem}
.tiles{grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}
.tile.gap{grid-column:auto}
.tile{padding:1rem 1.2rem}
.tile dd.figure{font-size:3.5rem}
ol.bars li{grid-template-columns:1.5rem 9rem minmax(0,1fr) 7rem;grid-template-areas:"rank name bar total" "rank note bar total"}
.total{text-align:right}
ol.rules li{grid-template-columns:11rem minmax(0,1fr);gap:1rem}
}
@media (min-width:64rem){
.js .t-product main{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:2.5rem;align-items:start}
.js .t-product main>*{grid-column:1/-1}
.js .t-product main>section[data-column],.js .t-product main>.not-sold{grid-column:1/9}
.js .t-product main>.elsewhere,.js .t-product main>nav.badges{grid-column:9/13;grid-row:4/span 20}
.js .t-product main>.elsewhere{margin-top:1.5rem}
.js .t-product main>nav.badges{margin-top:1.5rem}
.js .t-product main>.elsewhere:not([hidden])+nav.badges{margin-top:4.2rem}
.js .verdict b{font-size:clamp(3rem,4.9vw,4rem)}
}
@media print{.store,.search,.letters,.toc,.deals>input,.deals>label{display:none}}
```

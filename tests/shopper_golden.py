"""The golden 90 days: a synthetic history of 1 January to 30 April 2026 (day 1 to day 120) at the five chains, written
as the chains' own files, store by store and day by day (docs/shopper-site.md, "Testing", and "Changed after the
survey"'s "a chain of two formats"; the plan's Task 25), and `run`, which builds it through the real code. Every table
comes from these files through `shopper.extract.extract_chain_day` (the first pre-flight's S18): no table is written by
hand. Names, barcodes and prices are synthetic. tests/test_golden_90.py asserts the values worked below.

Day n is 1 January plus n - 1 days: day 31 is 31 January, 59 is 28 February, 90 is 31 March, 120 is 30 April.

The stores (the store lists of day 1 hold for every day, but Shufersal's of day 92). Shufersal: Sheli (sub-chain 1) 11
and 12, Deal (2) 21 and 22, Yesh Chesed (6, in no column) 61, and from day 92 (2 April), when its list of that day adds
them, Universe (8) 81, 82 and 83; its files are named under the store's own sub-chain. Carrefour: 62 and 64 in
`CARREFOUR_COLUMNS`' City, 2 and 12 in its Market, 1 in neither. Rami Levy, Osher Ad and Yochananof: 1 and 2, each
chain one column. Express has no store: a hole every day (`chain_day` with no included store), so it has no day of
records and no forecast; so is Universe before day 92. Every store publishes a promotion file every day it publishes a
price file (an empty one when it lists no promotion), but Universe's three stores on day 110 (20 April), when they
publish price files only: Universe's promotion hole, the store-first design's "a hole" (0 of its 3 counted stores with
a promotion file), its prices read. No other column-day is a promotion hole. Files missing: both Rami Levy stores' on
days 40 and 41 (9 and 10 February); both Deal stores' on days 50 and 51 (19 and 20 February), while Sheli's and Yesh
Chesed's are there.

The products (`PRODUCTS`, `listed`, `promotions`):

- G1 at every store, 5.00, on a fixed-price 3.90 promotion every 21 days for 7 days at every store: days 5-11, 26-32,
  47-53, 68-74, 89-95 and 110-116 (5 to 11 January, 26 January to 1 February, 16 to 22 February, 9 to 15 March, 30
  March to 5 April, 20 to 26 April), run k (from 0) being promotion 10 + k. Each run is listed only on its days.
- G2 at every store, 2.50, never on promotion.
- G3 at Shufersal: Sheli's two stores 10.90, then 11.90 from day 60 (1 March), on a 7.90 promotion (30) from day 75 (16
  March) on; Deal's two 9.90 throughout, with no promotion; Yesh Chesed does not list it.
- G4 at Rami Levy alone, weighed: 69.90 a kilogram; "2 for ₪100" stored as `RewardType` 1, `MinQty` 1.5,
  `DiscountedPrice` 75.00, `bIsWeighted` 1 (promotion 40), on days 85 to 98 (26 March to 8 April).
- G5 at Shufersal: Sheli 6.50, Yesh Chesed 6.20, Deal 6.00, but 4.50 on days 30 to 44 (30 January to 13 February); a
  4.50 promotion (50) carried by Deal's store 21 from day 99 (9 April) and by store 22 from day 100, to day 106; neither
  Sheli store nor Yesh Chesed carries it.
- G6, the basket's item priced apart: Shufersal 8.00 (11), 8.20 (12), 7.00 (21), 7.20 (22), 7.60 (61); Carrefour 8.40
  (62), 8.60 (64), 7.90 (2), 8.10 (12), 8.30 (1); Rami Levy 7.40 and 7.60; Osher Ad 7.10 and 7.30; Yochananof 7.80 and
  8.00. Never on promotion.
- U1 to U10 at Universe's three stores alone, and nothing else there, each at the same price in the three unless said
  (`UNIVERSE`; the store-first design's "Building order" 1), each promotion a fixed price (`RewardType` 3) unless said,
  listed in a promotion file on its days only:
  - U1, always on: 12.90 on days 92 to 120; 9.90 (promotion 60) on days 92 to 125.
  - U2, a monthly sale: 8.90 on days 92 to 120; 6.90 on days 95 to 101 (61) and on days 117 to 123 (62).
  - U3, on sale exactly half its days: 9.90 on days 93 to 120; 7.90 (63) on days 106 to 125.
  - U4, a short history: 4.50 on days 115 to 120; 3.20 (64) on days 120 to 126.
  - U5, new today: 6.00 on day 120 alone; 5.00 (65) on days 120 to 126.
  - U6, saving ₪0.99: 5.00 on days 92 to 120; 4.01 (66) on days 120 to 126.
  - U7, saving ₪1.00: 5.00 on days 92 to 120; 4.00 (67) on days 120 to 126.
  - U8, buy 2: 6.00 on days 92 to 120; "2 for ₪9.00", `RewardType` 1, `MinQty` 2, `DiscountedPrice` 9.00 (68), on
    days 120 to 126.
  - U9, at some stores only: 7.00 on days 92 to 120; 5.00 (69) at store 81 alone, on days 120 to 126.
  - U10, an unreadable price: 3.00 on days 92 to 120; 6.50 (70), twice the listed price or more, on days 120 to 126.

The run (`run`): days 1 to 29 extracted; from day 30, the first forecast day, the site run of each day at 12:33 Israel
time, S3's clock at 12:33:07, so every day is frozen on time. The basket is G1, G2 and G6, with at least 3 items.

Worked by hand.

The days of records. Sheli, City, Market, Osher Ad and Yochananof: every day. Deal: no record on days 50 and 51 (0 of
its 2 stores with a file: 0 x 2 < 2), Sheli's those days are (2 of 2), and Shufersal's chain-day for the basket has 3 of
5 (3 x 2 >= 5: no hole). Rami Levy: none on days 40 and 41. Universe: days 92 to 120 (29), its promotion hole of day
110 one of them (a record: its prices were read). Day 120's read is days 30 to 120 (91 days): Deal and Rami Levy have
89 days with records there, Sheli 91, Universe 29, Express none (a hole on each of the 91). From day 92 Shufersal's
chain-day for the basket has 8 included stores, every one with a file; Universe's stores list no basket item, so
every chain price of the basket stands.

The first forecast day. Day 30 is each column's 30th day of records (days 1 to 30), with closed days to learn from
(days 1 to 16); day 29 has 29, and no forecast. Universe's 29 days of records, 92 to 120, never reach its 30th
(`FIRST_RECORD_DAY`): it has no forecast and no score. Day 30's rows: G2 and G6 at City, Market, Osher Ad and
Yochananof (G1 is on its run of days 26 to 32), G2, G4 and G6 at Rami Levy, G2, G3, G5 and G6 at Sheli and at Deal: 8 +
3 + 4 + 4 = 19.
At City on day 30 the closed days are 1 to 16: G2 and G6 16 each with outcome 0, G1 9 (1-4, 12-16) with outcome 1, so
the column's share is 9/41; G2's A, from 16 closed days (under 20), is the column's, 9/41 = 0.219512; the hazard of "no
run seen" is G1's 4 ones of 36 days, 1/9; p = (16/46)(9/41) + (30/46)(1/9) = 0.148816; B, with no two runs before any
of its days, says no on all 41, 9 ones: 9/41.

The outcomes (F1, days t + 1 to t + 14). G1 off promotion: 1 (its next run starts within 14 days: the runs are 14 days
apart). G2 and G6: 0. Sheli's G3: 1 for t in 61 to 74 (day 75 in the window), else 0; from day 75 it is on promotion and
gets no forecast. Deal's G3: 0. Rami Levy's G4: 1 for t in 71 to 84. Deal's G5: 1 for t in 85 to 98, its first day on
promotion being day 99, when store 21 alone carries it (1 of Deal's 2 counted stores is half: wide). Sheli's G5: 0.
Holes in a window: Deal's days 50 and 51 for t in 36 to 50 (2 for t in 37 to 49), Rami Levy's 40 and 41 for t in 26
to 40; never more than 2, so every forecast is scored. No forecast on a hole: none at Rami Levy on days 40 and 41, none
at Deal on 50 and 51.

1 March (day 60). The closed days are t = 1 to 46, the eligible ones.
- City (and Market, Osher Ad, Yochananof): G2 and G6 46 days each, outcome 0, no run seen; G1's days off promotion,
  1-4 (no run seen), 12-25 and 33-46 (days since its last run 1 to 14), 32 days, outcome 1. The hazard of "no run
  seen": 4 ones of 96 days, 1/24; of days since 1 to 14: 1. B says yes on G1's days 33 to 46 (two runs before, the next
  start 32 + (26 - 11) = 47 within 14 days), all ones, and no on the other 110, 18 of them ones: 9/55 = 0.163636.
  G1: n = 32, A = 1; days since 60 - 53 = 7, hazard 1; p = w x 1 + (1 - w) x 1 = 1; B yes (53 + 15 = 68 in days 61 to
  74): 1. G2 and G6: n = 46, A = 0; w = 46/76; p = (30/76)(1/24) = 5/304 = 0.016447; B no: 0.163636.
- Rami Levy: closed days 1 to 46 but 40 and 41: G2, G4 and G6 44 days each, 0; G1 30 (1-4, 12-25, 33-39, 42-46), 1. The
  hazard of no run seen 4/136 = 1/34; B no: 18 ones of 150, 3/25. G2, G4, G6: p = (30/74)(1/34) = 15/1258 = 0.011924,
  B 0.120000. G1: 1, 1, 1, n = 30.
- Sheli and Deal (Deal's holes come after day 46): G2, G3, G5 and G6 46 days each, 0; G1 32, 1. The hazard of no run
  seen 4/188 = 1/47; B no: 18/202 = 9/101 = 0.089109. G2, G3, G5, G6: p = (30/76)(1/47) = 15/1786 = 0.008399. G1: 1, 1,
  1, n = 32.
Scored on day 74: G1's outcome 1, its first day 68 (9 March), promotion 13; the others 0; no hole. City's summary: 3
forecasts, 3 scored, 1 outcome 1; the model's squares 0 + 2 x 0.016447^2 = 0.000541007618, A's 0 (written "0"), B's 2 x 0.163636^2 =
0.053553480992; G2 and G6 in the first bin (2 rows, their p summing to 0.032894, no 1), G1 in the last (1, 1.000000, 1).

15 March (day 74), G3 at Sheli, its last day before the promotion. Closed days 1 to 60: G2, G3, G5 and G6 60 days each,
0 (day 75 lies in no window up to t = 60); G1 39 (1-4, 12-25, 33-46, 54-60), 1. The hazard of no run seen 4/244 = 1/61;
B no: 18 ones of 258, 3/43 = 0.069767. G3: n = 60, A = 0, w = 60/90, p = (1/3)(1/61) = 1/183 = 0.005464. Scored on day
88: outcome 1, its first day 75 (16 March), promotion 30. Deal's G3 that day: outcome 0.

16 March (day 75) at Sheli: G3 on promotion, so no forecast for it; G1's day since is 1 (its run ended on day 74). Closed
days 1 to 61: G2, G3, G5 and G6 61 days each, all 0 but G3's day 61 (day 75 in its window); G1 40 (1-4, 12-25, 33-46,
54-61), 1. The hazard of no run seen (4 + 1)/248 = 5/248; B no: 244 + 18 days, 1 + 18 ones, 19/262 = 0.072519. G2, G5
and G6: n = 61, w = 61/91, p = (30/91)(5/248) = 75/11284 = 0.006647. (A closed day's window read a day late would take
G3's day 60 as a 1 too: 6/248, p = 0.007976.)

31 March (day 90), G5 at Deal. Closed days 1 to 76 but 50 and 51: G2, G3, G5 and G6 74 days each, 0; G1 48 (1-4, 12-25,
33-46, 54-67, 75-76), 1. The hazard of no run seen 4/300 = 1/75; B no: 18 ones of 314, 9/157 = 0.057325. G5: n = 74,
A = 0, w = 74/104, p = (30/104)(1/75) = 1/260 = 0.003846. Outcome 1, its first day 99 (9 April), promotion 50; Sheli's
G5 that day: 0.

The pages.
- 16 March (day 75), G3 at Sheli. The 30-day window (days 45 to 74) lists 10.90 on 45-59 and 11.90 on 60-74: of 30
  prices the median is the mean of the 15th and 16th, (10.90 + 11.90)/2 = 11.40; 11.40 - 7.90 = 3.50, and 3.50/11.40 =
  30.7%: 31%. The 90-day window (days -15 to 74) holds days 1 to 74, 74 days, its low 10.90, no day at or below 7.90.
  One change in the 30 days: 10.90 to 11.90 on day 60, day 59 a day with records. Its front row: wide (2 of 2), valid
  (7.90 between 0.01 and 23.80), today a record, 30 >= 20 days of records in the 30, 7.90 below the 90's 10.90. The
  count line: one promotion (Shufersal's 30) on one product, one below. Deal's 9.90, with no promotion, has no row.
- 26 March (day 85), G4 at Rami Levy: 75.00/1.5 = 50.00 a kilogram, "buy 1.5"; the 30-day window (days 55 to 84) lists
  69.90 throughout: 19.90 below, 19.90/69.90 = 28.5%: 28%; the 90-day window, days 1 to 84 but 40 and 41: 82 days. The
  front page: G3's row first (its median now 11.90, 25 of the 30 days at 11.90: 4.00/11.90 = 34%), then G4's.
- 9 April (day 99), G5 at Deal: store 21's alone, 1 x 2 >= 2 counted stores: wide, so listed across Deal, not "at some
  stores". The 30-day window (days 69 to 98) lists 6.00: 1.50 below, 25%. The 90-day window, days 9 to 98 but 50 and
  51: 88 days, its low 4.50 (days 30 to 44: 15 days at or below the deal). The deal is not below every listed price of
  the 90 days, so it has no front row: the front page holds G3's alone. Sheli's G5: no promotion in its 90 days.
- 19 February (day 50): G1 on its run of days 47 to 53 at every column; Deal a hole, so the front rows are the six other
  columns' G1 (each 1.10, 22%, below 5.00), in name order; G1's Deal section says "too few files today: 0 of 2 stores".
- 30 April (day 120), G1. The 90-day window is days 30 to 119. Osher Ad: 90 days with records; on promotion on 30-32
  (the run of 26 to 32, started before the window: "or earlier"), 47-53, 68-74, 89-95 and 110-116, 3 + 4 x 7 = 31 days;
  14 days between runs (46 - 32); the last run ended on day 116, 4 days ago. Deal: 88 days (not 50 and 51), on promotion
  on 3 + 5 + 7 x 3 = 29; the holes inside the run of 47 to 53 break no run and hide none. Rami Levy: 88 days (not 40
  and 41), on promotion on 31; days 40 and 41 lie between the runs of 26-32 and 47-53, where a one-day run could hide:
  "Runs seen", "at most 14". G4 at Rami Levy: on promotion on 14 of its 88 days (85 to 98), the run "seen" (40 and 41
  outside it), ended on day 98, 22 days ago; its listed price "did not change on the 88 days with records of the 90".

The verdicts (docs/store-first.md, S0 to S8; `shopper.verdict`). The tracked days are those of the 90 before the day
with records at the column, its promotions read and the product listed (S0, per product); a day price is the lower of
the listed price and the lowest promotion that counts (S1); the usual price is the higher middle of the sorted day
prices (S2), and the figures are as shown, to the agora.
- G3 at Sheli, day 75: the 90 days before reach back past day 1, so days 1 to 74 are tracked, 74: 59 at 10.90 (1-59)
  and 15 at 11.90 (60-74), none on sale. Of the 74 sorted, the 38th (index 37) is 10.90. Today 7.90 (promotion 30):
  10.90 - 7.90 = 3.00, a deal, shade deal-2 (3.00 to 4.99). No day at or below 7.90: no "last this low". On sale on 0
  of 74, no last sale.
- G3 at Sheli, day 120: days 30 to 119, 90 tracked: 30 at 10.90 (30-59), 15 at 11.90 (60-74) and 45 on sale at 7.90
  (75-119: the lower of 11.90 and 7.90). Of the 90 sorted, the 46th (index 45) is 10.90, the first 45 being 7.90: on
  sale on exactly half the days, the higher middle holds the shelf price. Today 7.90: 3.00 off, deal-2; last this low
  day 119 at 7.90; on sale on 45 of 90; the run of 75 to 119 runs into today, with no sale before it: no last sale.
- G4 at Rami Levy, day 85: days 1 to 84 but 40 and 41 (no files), 82 tracked, all 69.90; today 75.00 / 1.5 = 50.00 a
  kilogram (promotion 40): 19.90 off, deal-3 (5.00 or more); no day at or below 50.00; on sale on 0 of 82.
- G5 at Deal, day 99: days 9 to 98 but 50 and 51, 88 tracked: 15 at 4.50 (30-44) and 73 at 6.00. Of the 88 sorted, the
  45th (index 44) is 6.00. Today 4.50 (promotion 50, store 21's alone, wide): 1.50 off, deal-1 (1.00 to 2.99); last
  this low day 44 (13 February) at 4.50, equal to today's; on sale on 0 of 88. At Sheli that day no promotion runs on
  G5: no sale, today's price the listed 6.50, 90 tracked (days 9 to 98), last this low day 98 at 6.50.
- G1 at Osher Ad, day 120: days 30 to 119, 90 tracked, on sale on 30-32, 47-53, 68-74, 89-95 and 110-116 (31 days at
  3.90), 59 at 5.00. No promotion runs today (the next run starts on day 131): no sale, today's price the listed 5.00,
  last this low day 119 at 5.00; the latest run, 110 to 116, is the last sale: it ended on day 116 (26 April) at 3.90.
- G1 at Osher Ad, day 50: days 1 to 49, 49 tracked, on sale on 5-11, 26-32 and 47-49 (17 days at 3.90), 32 at 5.00. Of
  the 49 sorted, the 25th (index 24) is 5.00. Today 3.90 (promotion 12): 1.10 off, deal-1; last this low day 49 at
  3.90; the run of 47 to 49 runs into today, so the last sale before this one is the run of 26 to 32: it ended on day 32
  (1 February) at 3.90.
- G1 at Deal, day 50: Deal is a hole (0 of its 2 stores with a file): too few files, no verdict; its 49 tracked days
  (1 to 49) are given all the same, 17 of them on sale.
- Universe, day 120: the 90 days before are 30 to 119; Universe's records are 92 to 119, its promotions unread on day
  110, so a product listed from day 92 has 27 tracked days (92-109 and 111-119). Today every promotion running at all
  three stores counts but U10's.
  - U1: on sale every day at 9.90 (below 12.90): 27 at 9.90, usual 9.90, today 9.90: 0.00 off, no deal; last this low
    day 119 at 9.90; on sale on 27 of 27, one run into today and none before it: no last sale.
  - U2: 10 days on sale at 6.90 (95-101, 117-119), 17 at 8.90; of the 27 sorted, the 14th (index 13) is 8.90. Today
    6.90 (promotion 62): 2.00 off, deal-1; last this low day 119; on sale on 10 of 27; the run of 117 to 119 runs into
    today, so the last sale before this one ended on day 101 (11 April) at 6.90.
  - U3: listed from day 93, 26 tracked (93-109, 111-119): 13 at 9.90 (93-105) and 13 on sale at 7.90 (106-109,
    111-119, one run across day 110). Of the 26 sorted, the 14th (index 13) is 9.90: on sale on exactly half, the shelf
    price is usual. Today 7.90: 2.00 off, deal-1; on sale on 13 of 26; no last sale before this one.
  - U4: listed from day 115, 5 tracked (115-119) at 4.50: usual 4.50, today 3.20: 1.30 off, deal-1, resting on 5 days.
    Its 5 days with records in the 30 before are under the front list's 20.
  - U5: first listed today, a promotion counting: new, no verdict, no tracked day.
  - U6: 27 days at 5.00, today 4.01: 0.99 off, no deal. U7: today 4.00: 1.00 off, deal-1.
  - U8: 27 days at 6.00, today 9.00 / 2 = 4.50, buy 2: 1.50 off, deal-1.
  - U9: its promotion is carried by store 81 alone, 1 of 3 counted stores (1 x 2 < 3): not wide, on sale at some
    stores only, no verdict; today's price the listed 7.00, last this low day 119.
  - U10: 6.50 is not below twice 3.00 (6.00): not valid, on sale with its price unread, no verdict; today's price the
    listed 3.00, last this low day 119.
  The front list: the deals with 20 days with records in the 30 before (days 90 to 119: Universe's 92 to 119, 28, its
  promotion hole a record; U3 27): U2 (2.00), U3 (2.00, after U2 by barcode), U8 (1.50) and U7 (1.00); N = 4. Checked
  (a promotion counting today, the bar passed): U1, U2, U3, U6, U7 and U8; M = 6 (U4 and U5 under the bar).

The basket. Shufersal's G6 is the median of its five stores' 7.00, 7.20, 7.60, 8.00 and 8.20: 7.60, Yesh Chesed's own,
not Sheli's 8.10 nor Deal's 7.10, the product page's; on days 50 and 51, of the three with a file, 7.60, 8.00 and 8.20:
8.00. Carrefour's: 7.90, 8.10, 8.30, 8.40 and 8.60: 8.30, store 1's. Rami Levy is out of the ranking on days 40 and 41.
The totals of day 120: Osher Ad 5.00 + 2.50 + 7.20 = 14.70, Rami Levy 15.00, Shufersal 15.10, Yochananof 15.40,
Carrefour 15.80; 1.10/14.70 = 7.48%: 7%.

The record on day 120: the days frozen 30 January to 30 April, scored 30 January to 16 April (each on its 14th day
after): 77 days at each column with forecasts but Deal and Rami Levy, with 75 (no forecast on their holes); Express and
Universe have none. Every gate is closed, its days short of 90.
"""
import gzip
import hashlib
import json
import re
import shutil
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import basket.build
import shopper.build
from basket.archive import MemoryArchive
from basket.barcode import is_gs1
from basket.chains import SLUGS
from collector.run import new_run_id
from shopper.build import SiteOutcome, build_site
from shopper.extract import extract_chain_day
from shopper.freeze import ArchiveFreezer
from test_build import CHAIN_IDS
from test_promos import _group, _item, _promotion

FIRST = date(2026, 1, 1)
LAST = date(2026, 4, 30)
DAYS = (LAST - FIRST).days + 1        # 120


def day_of(n: int) -> date:
    """Day n of the history: day 1 is 1 January 2026, day 120 is 30 April 2026."""
    return FIRST + timedelta(days=n - 1)


# The stores of day 1: (store, sub-chain), as the store lists name them. Shufersal: Sheli (sub-chain 1) 11 and 12, Deal
# (2) 21 and 22, Yesh Chesed (6, in no column) 61. Carrefour: 62 and 64 in CARREFOUR_COLUMNS' City, 2 and 12 in its
# Market, 1 in neither (outside the table). The other three chains: stores 1 and 2, each chain one column.
STORES: dict[str, tuple[tuple[str, str], ...]] = {
    "shufersal": (("11", "1"), ("12", "1"), ("21", "2"), ("22", "2"), ("61", "6")),
    "ramilevy": (("1", "1"), ("2", "1")),
    "osherad": (("1", "1"), ("2", "1")),
    "carrefour": (("1", "1"), ("2", "1"), ("12", "1"), ("62", "1"), ("64", "1")),
    "yochananof": (("1", "0"), ("2", "0")),
}
SHELI, DEAL, YESH_CHESED = ("11", "12"), ("21", "22"), ("61",)
# Shufersal Universe (sub-chain 8): stores 81, 82 and 83, on Shufersal's store list from day 92 (2 April); on day 110
# (20 April) they publish price files only, Universe's promotion hole
UNIVERSE, UNIVERSE_SUB_CHAIN, UNIVERSE_FROM, UNIVERSE_PROMO_HOLE = ("81", "82", "83"), "8", 92, 110

# The products, each a synthetic GS1 barcode (the check digit is checked below)
G1, G2, G3, G4, G5, G6 = ("2000000000077", "2000000000084", "2000000000091", "2000000000107", "2000000000114",
                          "2000000000121")
# Universe's ten, in ascending numeric order, so a tie between them sorts as listed here
U1, U2, U3, U4, U5, U6, U7, U8, U9, U10 = (
    "2000000000138", "2000000000145", "2000000000152", "2000000000169", "2000000000176", "2000000000183",
    "2000000000190", "2000000000206", "2000000000213", "2000000000220")
UNIVERSE_CODES = (U1, U2, U3, U4, U5, U6, U7, U8, U9, U10)
PRODUCTS = {   # code: (name, Quantity, UnitQty), as every price file states them
    G1: ("חטיף בדיקה 500 גרם", "500", "גרם"),
    G2: ("משקה בדיקה 1 ליטר", "1", "ליטר"),
    G3: ("שמן בדיקה 1 ליטר", "1", "ליטר"),
    G4: ("בשר בדיקה לק\"ג", "1", "קילוגרם"),
    G5: ("גבינה בדיקה 200 גרם", "200", "גרם"),
    G6: ("ביצי בדיקה 12", "12", "יחידות"),
    U1: ("קפה בדיקה 200 גרם", "200", "גרם"),
    U2: ("אורז בדיקה 1 קילוגרם", "1", "קילוגרם"),
    U3: ("פסטה בדיקה 500 גרם", "500", "גרם"),
    U4: ("יוגורט בדיקה 150 גרם", "150", "גרם"),
    U5: ("מיץ בדיקה 1 ליטר", "1", "ליטר"),
    U6: ("קמח בדיקה 1 קילוגרם", "1", "קילוגרם"),
    U7: ("סוכר בדיקה 1 קילוגרם", "1", "קילוגרם"),
    U8: ("עוגיות בדיקה 300 גרם", "300", "גרם"),
    U9: ("תה בדיקה 100 גרם", "100", "גרם"),
    U10: ("מלח בדיקה 500 גרם", "500", "גרם"),
}
assert all(is_gs1(code) for code in PRODUCTS)

# Whose files are missing: Rami Levy's every store on days 40 and 41 (9 and 10 February); Deal's two stores on days 50
# and 51 (19 and 20 February), while Sheli's and Yesh Chesed's are there.
MISSING: dict[str, dict[int, tuple[str, ...]]] = {
    "ramilevy": {40: ("1", "2"), 41: ("1", "2")},
    "shufersal": {50: DEAL, 51: DEAL},
}

# G1's runs on promotion, 7 days every 21 days, at every store of every chain: days 5-11, 26-32, 47-53, 68-74, 89-95
# and 110-116; run k (from 0) is promotion 10 + k, a fixed price of 3.90.
G1_RUNS = tuple((5 + 21 * k, 11 + 21 * k) for k in range(6))
G5_LOW = (30, 44)                     # Deal lists G5 at 4.50 on these days, at 6.00 on the others
G3_RISE, G3_PROMOTION = 60, 75        # Sheli's G3: 10.90, then 11.90 from day 60; a 7.90 promotion from day 75
G4_PROMOTION = (85, 98)               # Rami Levy's G4: "2 for 100" stored as 1.5 for 75.00, weighed
G5_PROMOTION = {"21": (99, 106), "22": (100, 106)}   # Deal's G5 at 4.50: store 21 a day before store 22
BASKET_ITEMS = (G1, G2, G6)
# Universe's products: code: (its listed price, its first day listed), each to day 120 (U5 on day 120 alone)
UNIVERSE_LISTED = {U1: ("12.90", 92), U2: ("8.90", 92), U3: ("9.90", 93), U4: ("4.50", 115), U5: ("6.00", 120),
                   U6: ("5.00", 92), U7: ("5.00", 92), U8: ("6.00", 92), U9: ("7.00", 92), U10: ("3.00", 92)}
# Universe's promotions: (id, code, RewardType, MinQty, DiscountedPrice, first day, last day, the stores carrying it)
UNIVERSE_PROMOTIONS = (
    ("60", U1, "3", "1", "9.90", 92, 125, UNIVERSE),
    ("61", U2, "3", "1", "6.90", 95, 101, UNIVERSE),
    ("62", U2, "3", "1", "6.90", 117, 123, UNIVERSE),
    ("63", U3, "3", "1", "7.90", 106, 125, UNIVERSE),
    ("64", U4, "3", "1", "3.20", 120, 126, UNIVERSE),
    ("65", U5, "3", "1", "5.00", 120, 126, UNIVERSE),
    ("66", U6, "3", "1", "4.01", 120, 126, UNIVERSE),
    ("67", U7, "3", "1", "4.00", 120, 126, UNIVERSE),
    ("68", U8, "1", "2", "9.00", 120, 126, UNIVERSE),
    ("69", U9, "3", "1", "5.00", 120, 126, ("81",)),
    ("70", U10, "3", "1", "6.50", 120, 126, UNIVERSE),
)


def stores_on(slug: str, n: int) -> tuple[tuple[str, str], ...]:
    """The chain's stores on day n, (store, sub-chain): day 1's, and Universe's three at Shufersal from day 92."""
    if slug == "shufersal" and n >= UNIVERSE_FROM:
        return STORES[slug] + tuple((store, UNIVERSE_SUB_CHAIN) for store in UNIVERSE)
    return STORES[slug]


def listed(slug: str, store: str, code: str, n: int) -> str | None:
    """The store's listed price of `code` on day n as its price file states it; None when it does not list it."""
    if slug == "shufersal" and store in UNIVERSE:
        if code not in UNIVERSE_LISTED:
            return None
        price, first = UNIVERSE_LISTED[code]
        return price if n >= first else None
    if code in UNIVERSE_LISTED:
        return None
    if code == G1:
        return "5.00"
    if code == G2:
        return "2.50"
    if code == G3:
        if slug != "shufersal" or store in YESH_CHESED:
            return None
        if store in DEAL:
            return "9.90"
        return "10.90" if n < G3_RISE else "11.90"
    if code == G4:
        return "69.90" if slug == "ramilevy" else None
    if code == G5:
        if slug != "shufersal":
            return None
        if store in DEAL:
            return "4.50" if G5_LOW[0] <= n <= G5_LOW[1] else "6.00"
        return "6.50" if store in SHELI else "6.20"
    return G6_PRICES[slug][store]


# G6, the basket's item priced apart at Shufersal's formats and at Carrefour's: the chain's median over all its stores
# with a file is the price of the store in no column (Shufersal 7.60 at Yesh Chesed's 61, Carrefour 8.30 at store 1)
G6_PRICES = {
    "shufersal": {"11": "8.00", "12": "8.20", "21": "7.00", "22": "7.20", "61": "7.60"},
    "carrefour": {"62": "8.40", "64": "8.60", "2": "7.90", "12": "8.10", "1": "8.30"},
    "ramilevy": {"1": "7.40", "2": "7.60"},
    "osherad": {"1": "7.10", "2": "7.30"},
    "yochananof": {"1": "7.80", "2": "8.00"},
}


def _iso(n: int) -> str:
    return day_of(n).isoformat()


def promotions(slug: str, store: str, n: int) -> list[str]:
    """The promotions the store's full promotion file lists on day n, as XML."""
    if slug == "shufersal" and store in UNIVERSE:
        return [_promotion(promotion_id, _group(items=[_item(code, reward=reward, min_qty=quantity, price=price)]),
                           start=_iso(start), end=_iso(end))
                for promotion_id, code, reward, quantity, price, start, end, carrying in UNIVERSE_PROMOTIONS
                if store in carrying and start <= n <= end]
    found = []
    for k, (start, end) in enumerate(G1_RUNS):
        if start <= n <= end:
            found.append(_promotion(str(10 + k), _group(items=[_item(G1, reward="3", price="3.90")]),
                                    start=_iso(start), end=_iso(end)))
    if slug == "shufersal" and store in SHELI and n >= G3_PROMOTION:
        found.append(_promotion("30", _group(items=[_item(G3, reward="3", price="7.90")]), start=_iso(G3_PROMOTION),
                                end="2026-05-31"))
    if slug == "ramilevy" and G4_PROMOTION[0] <= n <= G4_PROMOTION[1]:
        found.append(_promotion("40", _group(items=[_item(G4, reward="1", min_qty="1.5", price="75.00",
                                                          weighed="1")]),
                                start=_iso(G4_PROMOTION[0]), end=_iso(G4_PROMOTION[1])))
    if slug == "shufersal" and store in G5_PROMOTION and G5_PROMOTION[store][0] <= n <= G5_PROMOTION[store][1]:
        found.append(_promotion("50", _group(items=[_item(G5, reward="3", price="4.50")]), start=_iso(99),
                                end=_iso(106)))
    return found


def _sub(sub_chain: str) -> str:
    """A sub-chain as file names and promotion files write it: three digits."""
    return f"{int(sub_chain):03d}"


def _name(kind: str, slug: str, store: str, sub_chain: str, n: int) -> str:
    return f"{kind}{CHAIN_IDS[slug]}-{_sub(sub_chain)}-{int(store):03d}-{day_of(n):%Y%m%d}-080000.gz"


def price_file(slug: str, store: str, n: int) -> bytes:
    """The store's gzipped full price file of day n, in the common layout."""
    items = "".join(
        f"<Item><ItemCode>{code}</ItemCode><ItemName>{name}</ItemName><ItemPrice>{price}</ItemPrice>"
        f"<Quantity>{quantity}</Quantity><UnitQty>{unit}</UnitQty>"
        f"<PriceUpdateTime>2025-12-31 08:00:00</PriceUpdateTime></Item>"
        for code, (name, quantity, unit) in PRODUCTS.items()
        if (price := listed(slug, store, code, n)) is not None)
    xml = (f'<?xml version="1.0" encoding="utf-8"?><Root><ChainId>{CHAIN_IDS[slug]}</ChainId><Items>{items}'
           "</Items></Root>")
    return gzip.compress(xml.encode(), mtime=0)


def promo_file(slug: str, store: str, sub_chain: str, n: int) -> bytes:
    """The store's gzipped full promotion file of day n, its root the fields every chain's files carry; a day with
    no promotion still has its file, with none in it."""
    xml = (f"<Root><ChainID>{CHAIN_IDS[slug]}</ChainID><SubChainID>{_sub(sub_chain)}</SubChainID>"
           f"<StoreID>{int(store):03d}</StoreID><BikoretNo>0</BikoretNo><Promotions>"
           + "".join(promotions(slug, store, n)) + "</Promotions></Root>")
    return gzip.compress(xml.encode(), mtime=0)


def store_list(slug: str, n: int = 1) -> tuple[str, bytes]:
    """The chain's `Stores` file of day n and its name, in the layout its portal uses (as tests/test_build.py's
    `store_list`): Shufersal's gzipped UTF-8 with root <Chain>, a <SubChain> per sub-chain; Yochananof's plain UTF-8
    with the tags spelled `SubChainId` and `StoreId`; the others' plain UTF-16 with root <Root>."""
    chain_id, day = CHAIN_IDS[slug], f"{day_of(n):%Y%m%d}"
    by_sub: dict[str, list[str]] = {}
    for store, sub_chain in stores_on(slug, n):
        by_sub.setdefault(sub_chain, []).append(store)
    if slug == "yochananof":
        stores = "".join(f"<Store><StoreId>{store}</StoreId><StoreName>סניף {store}</StoreName></Store>"
                         for store in by_sub["0"])
        xml = (f'<?xml version="1.0" encoding="utf-8"?><Root><ChainId>{chain_id}</ChainId><SubChains><SubChain>'
               f"<SubChainId>000</SubChainId><Stores>{stores}</Stores></SubChain></SubChains></Root>")
        return f"Stores{chain_id}-000-{day}-010000.xml", xml.encode()
    subs = "".join(
        f"<SubChain><SubChainID>{sub_chain}</SubChainID><Stores>"
        + "".join(f"<Store><StoreID>{store}</StoreID><StoreType>1</StoreType><StoreName>סניף {store}</StoreName>"
                  "</Store>" for store in stores)
        + "</Stores></SubChain>" for sub_chain, stores in by_sub.items())
    if slug == "shufersal":
        xml = (f'﻿<?xml version="1.0" encoding="UTF-8"?><Chain><ChainID>{chain_id}</ChainID><SubChains>{subs}'
               "</SubChains></Chain>")
        return f"Stores{chain_id}-000-{day}-020.gz", gzip.compress(xml.encode(), mtime=0)
    xml = (f'<?xml version="1.0" encoding="UTF-16"?><Root><ChainID>{chain_id}</ChainID><SubChains>{subs}</SubChains>'
           "</Root>")
    return f"Stores{chain_id}-000-{day}-050500.xml", xml.encode("utf-16")


def write_day(raw_dir: Path, n: int) -> None:
    """Every chain's files of day n under `raw_dir`: each store's price and promotion files (none for a store whose
    files are missing that day, no promotion file for Universe's on day 110) and, on day 1, the store lists, which hold
    for every later day but Shufersal's, written again on day 92 with Universe's stores."""
    for slug in STORES:
        folder = raw_dir / f"chain={slug}" / f"date={day_of(n).isoformat()}"
        folder.mkdir(parents=True, exist_ok=True)
        if n == 1 or (slug == "shufersal" and n == UNIVERSE_FROM):
            name, body = store_list(slug, n)
            (folder / name).write_bytes(body)
        for store, sub_chain in stores_on(slug, n):
            if store in MISSING.get(slug, {}).get(n, ()):
                continue
            (folder / _name("PriceFull", slug, store, sub_chain, n)).write_bytes(price_file(slug, store, n))
            if n == UNIVERSE_PROMO_HOLE and slug == "shufersal" and store in UNIVERSE:
                continue
            (folder / _name("PromoFull", slug, store, sub_chain, n)).write_bytes(promo_file(slug, store, sub_chain, n))


def write_basket(path: Path) -> Path:
    """The golden basket: G1, G2 and G6, each a size its price files state."""
    sizes = {G1: ("500", "gml"), G2: ("1000", "gml"), G6: ("12", "unit")}
    items = [{"code": code, "name_en": f"Golden item {index}", "name_he": PRODUCTS[code][0],
              "size": {"amount": sizes[code][0], "kind": sizes[code][1]}, "category": "pantry"}
             for index, code in enumerate(BASKET_ITEMS, 1)]
    path.write_text(json.dumps({"version": "golden", "since": FIRST.isoformat(), "selection_day": FIRST.isoformat(),
                                "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ---- the run ----

ISRAEL = ZoneInfo("Asia/Jerusalem")
FIRST_BUILD = 30          # the first forecast day: every column with stores has its 30th day of records on day 30
COLLECTED_BY = "11:48"    # the collector's check, as the site run gives it
FINGERPRINT = "0123456789ab"   # the code fingerprint every build is given, so a change under src/ moves no byte
F3_DAY = 88               # the day built again with the later days' tables present (F3): 29 March, the day before a G1 run
KEEP = (50, 75, 85, 99)   # the days whose written pages are kept for the tests (the last day's are in the site folder)
S3_LAG = timedelta(seconds=7)   # S3's time of every put: the run's time and 7 seconds


def build_time(day: date) -> datetime:
    """The site run's time on `day`: 12:33 Israel time."""
    return datetime(day.year, day.month, day.day, 12, 33, tzinfo=ISRAEL)


def fixed_run_id(now: datetime, mode: str) -> str:
    """`collector.run.new_run_id` with its four random hex digits fixed at 0000: the run's time and mode as ever."""
    return new_run_id(now, mode)[:-4] + "0000"


@contextmanager
def fixed_provenance():
    """Every build given the same provenance: the code fingerprint FINGERPRINT and run ids ending 0000, the basket's and
    the site's (the brief's "provenance apart": the only inputs a run does not take from the archive)."""
    with mock.patch.object(shopper.build, "code_fingerprint", lambda: FINGERPRINT), \
            mock.patch.object(basket.build, "code_fingerprint", lambda: FINGERPRINT), \
            mock.patch.object(shopper.build, "new_run_id", fixed_run_id), \
            mock.patch.object(basket.build, "new_run_id", fixed_run_id):
        yield


_HEX = re.compile(rb"[0-9a-f]{64}")


def portable(path: str, body: bytes, labels: dict[bytes, bytes]) -> str:
    """A file's SHA-256 as the pinned manifest takes it, the same on any machine: a gzip file's over its 10-byte header
    and the bytes inside it, since the compressed stream is zlib's and the Mac's, CI's and Lambda's zlib may differ
    (`shopper.freeze`'s question E); any other file's over its bytes with each gzip file's SHA-256 in it (the ledger's
    lines, a site-day file's forecasts) replaced by that file's name (`labels`)."""
    if path.endswith(".gz"):
        return hashlib.sha256(body[:10] + gzip.decompress(body)).hexdigest()
    return hashlib.sha256(_HEX.sub(lambda found: labels.get(found.group(), found.group()), body)).hexdigest()


@dataclass
class GoldenRun:
    """One run of the golden days: the folders, the archive, each built day's outcome, the files it wrote (by site
    path, their exact SHA-256 and the portable one), the pages of the KEEP days, and the state just before F3_DAY's
    build (its data and site folders copied under `before`, the archive's objects and times)."""
    root: Path
    data: Path
    site: Path
    archive: MemoryArchive
    outcomes: dict[date, SiteOutcome] = field(default_factory=dict)
    written: dict[date, dict[str, tuple[str, str]]] = field(default_factory=dict)
    kept: dict[date, dict[str, bytes]] = field(default_factory=dict)
    before: Path | None = None
    archive_before: tuple[dict, dict] | None = None
    labels: dict[bytes, bytes] = field(default_factory=dict)

    def page(self, n: int, path: str) -> str:
        """A page as day n's build wrote it: a KEEP day's, or the last day's from the site folder."""
        if n == DAYS:
            return (self.site / path).read_text(encoding="utf-8")
        return self.kept[day_of(n)][path].decode("utf-8")


def build_day(day: date, data: Path, site: Path, archive: MemoryArchive, basket_path: Path) -> SiteOutcome:
    """The site run of `day` at 12:33 Israel time, freezing and scoring through the archive's freezer, S3's clock
    at the run's time and 7 seconds."""
    now = build_time(day)
    archive.s3_clock = lambda: now + S3_LAG
    return build_site(day, data, site, now, COLLECTED_BY, ArchiveFreezer(archive, now), basket_path=basket_path,
                      min_items=len(BASKET_ITEMS))


def copy_archive(archive: MemoryArchive) -> MemoryArchive:
    copied = MemoryArchive(s3_clock=archive.s3_clock)
    copied.objects, copied.times = dict(archive.objects), dict(archive.times)
    return copied


def run(root: Path, keep: tuple[int, ...] = KEEP, f3_day: int | None = F3_DAY) -> GoldenRun:
    """The golden days under `root`, a day at a time as the collector and the site run would see them: each day's
    files written, then its tables extracted (days 1 to 29, `extract_chain_day` for each chain) or its whole site built
    (days 30 to 120, `build_site`, which extracts the day first); nothing of a later day is there while a day is
    built."""
    data, site = root / "data", root / "site"
    root.mkdir(parents=True, exist_ok=True)
    basket_path = write_basket(root / "basket.json")
    archive = MemoryArchive()
    golden = GoldenRun(root=root, data=data, site=site, archive=archive)
    with fixed_provenance():
        for n in range(1, DAYS + 1):
            day = day_of(n)
            write_day(data / "raw", n)
            if n < FIRST_BUILD:
                for slug in SLUGS:
                    extract_chain_day(data / "raw", slug, day, data / "tables")
                continue
            if n == f3_day:
                golden.before = root / "before"
                for folder in (data, site):
                    shutil.copytree(folder, golden.before / folder.name)
                golden.archive_before = dict(archive.objects), dict(archive.times)
            outcome = build_day(day, data, site, archive, basket_path)
            golden.outcomes[day] = outcome
            written = {path: (site / path).read_bytes() for path in [*outcome.data, *outcome.pages]}
            for path, body in written.items():     # gzip files first: a day's ledger names its own forecasts file
                if path.endswith(".gz"):
                    golden.labels[hashlib.sha256(body).hexdigest().encode()] = f"sha256 of {path}".encode()
            golden.written[day] = {path: (hashlib.sha256(body).hexdigest(), portable(path, body, golden.labels))
                                   for path, body in written.items()}
            if n in keep:
                golden.kept[day] = {path: body for path, body in written.items() if path.endswith(".html")}
    return golden


def final_files(golden: GoldenRun) -> dict[str, bytes]:
    """What the run leaves: every file of the site folder, the archive's objects and the scoring summaries, by a name
    under `site/`, `archive/` and `tables/`."""
    found = {f"site/{path.relative_to(golden.site).as_posix()}": path.read_bytes()
             for path in sorted(golden.site.rglob("*")) if path.is_file()}
    found |= {f"archive/{key}": stored.body for key, stored in sorted(golden.archive.objects.items())}
    scored = golden.data / "tables" / "scored"
    found |= {f"tables/{path.relative_to(golden.data / 'tables').as_posix()}": path.read_bytes()
              for path in sorted(scored.rglob("*.json"))}
    return found


def exact_digests(golden: GoldenRun) -> dict:
    """Each built day's written files and the run's final files, by their exact SHA-256: two runs on one machine
    compare by these."""
    return {"days": {day.isoformat(): {path: digests[0] for path, digests in written.items()}
                     for day, written in golden.written.items()},
            "final": {name: hashlib.sha256(body).hexdigest() for name, body in final_files(golden).items()}}


def manifest(golden: GoldenRun) -> str:
    """The pinned manifest's lines (portable SHA-256s, `portable`): one per built day, over that day's written files,
    then one per final file but the archive's (the site folder holds the same bytes, which a test checks), sorted."""
    lines = []
    for day, written in sorted(golden.written.items()):
        listing = "".join(f"{written[path][1]}  {path}\n" for path in sorted(written))
        lines.append(f"{hashlib.sha256(listing.encode()).hexdigest()}  day/{day.isoformat()}")
    lines += [f"{portable(name, body, golden.labels)}  {name}" for name, body in final_files(golden).items()
              if not name.startswith("archive/")]
    return "\n".join(sorted(lines, key=lambda line: line[66:])) + "\n"


def main(out: str) -> None:
    """The run in a process of its own (the determinism test runs it under TZ=UTC): its exact digests to
    `<out>/digests.json`."""
    golden = run(Path(out) / "run", keep=(), f3_day=None)
    (Path(out) / "digests.json").write_text(json.dumps(exact_digests(golden), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])

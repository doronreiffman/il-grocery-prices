# Shufersal: reading the file list across runs (design)

Grade: production. The collector is live and its files feed the public basket page every morning.
Status: draft of 2026-11-05. The owner chose this fix (resume plus per-page timing) and skipped the design questions; every choice the owner did not make is marked "Call" and listed at the end.

## Why

Shufersal lists each full kind (`PriceFull`, `PromoFull`) on about 21 pages of 20 rows (`docs/portals.md`, "Shufersal"). Every run reads the list from page 1, because a download link expires 30 minutes after its page is served. A page takes 25 to 35 s on a good morning and 50 s or more on a slow one, so on a slow morning no 15-minute run reads the whole list, and the second morning run spends most of its time re-reading the pages the first one already read.

What the manifests show, per full kind (two main runs, then one retry):

| Morning | PriceFull runs listed | PromoFull runs listed | Outcome |
|---|---|---|---|
| 2026-11-03 | 257, 297, retry 416 | 234, 340, retry 310 | PriceFull saved by the retry; about 77 stores' PromoFull never listed |
| 2026-11-04 | 373, 416 | 349, 417 | complete |
| 2026-11-05 | 237, 314, retry 20 | 214, 307, retry 19 | about 103 stores' PriceFull and 110 stores' PromoFull never listed |

On 2026-11-05 every main run stopped on the time rule (`stopped: under 90 s left`), and both retries ended after two minutes when page 2 passed the 60 s socket timeout (`074536Z-retry-2933`, `081551Z-retry-9283`). The check reported one missing file, because `missing` covers only names some run listed. The basket that day rested on 214 of Shufersal's 319 included stores (317 the day before).

The list's order makes a fix possible: in every Shufersal run from 2026-11-03 to 2026-11-05, main and retry, each run's `listed` names were in file-name order and each was the start of the longest run's list for that kind and day. So a later run can pick up where an earlier one stopped, and the pages several runs read can be joined into one full reading.

## Goals

- On a slow morning, the day's runs of a kind together read Shufersal's whole list for it.
- Every page read is timed and recorded, so the next diagnosis rests on measured page times, not on run durations.
- The check judges "read in full" from the pages actually read, across runs, and an alert says how much of the list was never read.

## Non-goals

- No schedule change, no new runs, no change to other chains, no change to the 60 s socket timeout or the 90 s time rule.
- No retry of a single slow page (considered and not chosen by the owner on 2026-11-05: at 60 s a page it would not have saved that morning).
- No sort parameter added to Shufersal's request: the request stays as it is, and the order is checked instead.

## Anti-goals

- A day reported complete when part of the list was never read.
- A run that skips a page because the list shifted between runs.

## What changes

### 1. Every page read is recorded

A Shufersal run's manifest gains `pages`: one entry per listing page it read and checked, in the order read, with the kind, the page number, the number of rows, the first and last file name on the page as listed (any date; the run still keeps only the day's names in `listed`), the last page the page's pager names (null when it has none; only page 1's pager has ever been seen, `docs/portals.md`), the seconds the request took, and the last row the run took from the page before it stopped or moved on ("taken through"; the run can stop between any two rows, `src/collector/run.py`, so the rows after it were never listed). Each page also gets one log line: `shufersal PriceFull page 7 of 21: 20 rows in 41.2 s`. Manifests of other chains carry an empty `pages`.

A page whose names are out of order, or whose first name sorts before the last name of the page read just before it, is recorded with `in_order: false`. Call: the run goes on reading as today; only resuming and the check's joining stop trusting that kind's pages for the day (below).

### 2. A run picks up where the day's earlier runs stopped

Before reading a kind, a Shufersal run reads the day's earlier Shufersal manifests (one listing of `manifests/date=<day>/shufersal-*` and a read of each).

- **Not yet read in full** (rule in section 3): the run reads page 1 first (Call: it is the only page whose pager is known to name the last page, and it costs one page), then goes to the furthest page an earlier run read and reads it again (one page of overlap, so a file whose download the earlier run never reached gets a fresh link). If that page's first name sorts after the furthest name the earlier runs took, the list has shifted forward: the run steps back one page at a time until the first name does not, or it reaches page 2. From there it reads on to the last page. If the last page the pager now names is before the resume page, it starts at the last page.
- **A failed file earlier on the list:** if a name an earlier run listed is not stored and sits on an earlier page than where the run would start (from the earlier run's `pages`), the run reads that page first, once, so the file is tried again as it would be today, then goes on to its start page. Call (builder check): a detour, not a restart there, so a file that fails every time cannot pull every later run back to its page. This holds for a fresh pass too: the detour comes before page 1.
- **Already read in full:** the run starts a fresh pass at page 1, as every run does today. This is the retry's job: files published after the first pass.
- **No usable record:** no earlier run of the kind that day, earlier manifests without `pages` (before this change), or any earlier page of the kind that day recorded `in_order: false`: the run starts at page 1, as today.

Call: the run loop reads the manifests and hands the adapter a start point per kind (the detour pages, the start page and the furthest name taken); paging stays in the Shufersal adapter, which reports each page it reads; the run loop owns the page records, since only it knows how far into a page it got. The builder may place it otherwise if the tests read the same.

### 3. The check judges "read in full" across runs (ruling R37, amends R36)

A full kind of a chain counts as read in full for the day when the pages the day's runs read join up from page 1 to the last page:

- Take every run of the chain that day, main or retry, that covers the kind and was not blocked; a run that stopped on time or on an error still counts for the pages it read before it stopped.
- Each run's pages split into blocks of consecutive page numbers. A block covers the names from its first page's first name to its last page's taken-through name; a block that starts at page 1 covers everything before too; a block that ends at the last page its own pager reading named, with every row of that page taken, covers everything after too. Call (builder check): a page counts only up to the last row the run took; without this, a run that stopped five rows into the last page would make the day read in full while those rows were never listed, and R36 would then excuse the retry with no email.
- The kind is read in full when those blocks, taken together, leave no gap: sorted by their first name, each block starts at or before the end of the blocks before it.
- Joining needs every page of the kind that day to be `in_order`. If one is not, only a single run that read page 1 to the last page in one go counts.
- A manifest with no `pages` (other chains, and Shufersal before this change) and no error counts as reading its kinds in full, exactly as R36 reads it today.

R36's other two conditions stay: every name the stopped retry listed was listed by a run that contributed to the full reading, and nothing is missing. The check record gains, per chain, `read_in_full`: for each full kind, the run ids whose pages joined up, or null.

When a full kind was not read in full that day, the failed alert says so with the pages never read, for example "shufersal: the PriceFull list was not read in full: pages 17 to 21 never read". Call: this sentence is added to the existing failed alert, not a new kind of alert.

## 2026-11-05 replayed (expected, not measured)

PriceFull: `044522Z` reads pages 1 to 12 as it did. `050002Z` reads page 1, then 12 to 21: 11 pages and about 180 downloads. At that morning's pace (worked out from run times: about 40 to 45 s a page and 1 to 2 s a download) that is about 12 to 13 minutes, close to the 13.5 a run has. If it reaches page 21 the kind is read in full by about 07:15 Israel time and the retry at 09:45 starts a fresh pass from page 1; if it stops short, the retry resumes from where it stopped instead of from page 1. That morning the retries' early pages timed out, and a timeout on whichever page the retry reads still ends it. So the replay does not promise a complete 2026-11-05. It shows the second run spending its time on pages 12 to 21 instead of 1 to 16, which on that morning is the difference between stopping at page 16 and reaching about page 21; and whatever happens, the check and the email say how much of the list was read.

## Cost

A Shufersal run makes one S3 listing and up to eight small reads of the day's manifests: well under $0.01 a month. Lambda time is unchanged or less (fewer pages re-read).

## Risks kept

- The name order is observed, not promised by Shufersal: the per-page order check guards it, and a broken order falls back to today's behaviour.
- A file published, after its part of the list was read, into a part only an earlier run covered is not collected until a fresh pass reaches it; if no fresh pass does, it is never collected and sends no email. R36 accepts the same risk today.
- Each resumed run spends one page on page 1. The page records show whether middle pages carry the pager; if they do, a later change can drop that page.

## Testing

Test-first, as every collector change (`docs/collector.md`, "Testing and shipping"): the adapter's page records, start point, overlap and step-back, and order check; the run loop's reading of earlier manifests and each start case above; the check's joining (2026-11-05's shape joining up, a gap, an out-of-order page, a blocked run, manifests without `pages`), `read_in_full` and the alert sentence; a mutation for each rule in `scripts/mutation_check.py`; coverage stays at or above 95%. A fresh reviewer reads the change before it ships; the owner gives the go for the deploy.

## Calls made in this draft (the owner can overturn any)

1. A retry whose list read fails for any reason other than the time rule still alerts, even when the day was read in full (R36 kept as narrow as the owner set it on 2026-11-04). On 2026-11-05 that means a failed email on a morning whose files were all stored.
2. A resumed run reads page 1 first.
3. A page out of order turns joining off for that kind and day, and the run carries on reading as today.
4. The failed alert names the pages never read.
5. The run loop computes the start point and owns the page records; the adapter pages.
6. A page counts as read only up to the last row the run took (from the builder check).
7. A file that failed earlier on the list gets a one-page detour, not a restart from its page (from the builder check).

## Left to the builder

Field names and the exact log line, how the start point is passed, and the test layout, within the rules above.

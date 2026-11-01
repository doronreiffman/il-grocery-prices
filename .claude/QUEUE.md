# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: schedules on since 2026-11-01 (Shufersal full files only, check 10:45); left: the first scheduled morning, 2026-11-02: read its check record after 10:45 Israel time; done when every chain's files are stored and no alert remains but Shufersal retries out of time with nothing missing (owner, 2026-11-01). State: `.claude/OPEN_ISSUES.md`, Collector, "Live".
- [q10] Full kinds on Saturdays and holidays: read the first Saturday's check record (2026-11-07) for "no run listed a PriceFull / PromoFull"; a chain that skips Saturdays → the owner decides on an exemption. State: `.claude/OPEN_ISSUES.md`, Collector, "Full kinds on Saturdays and holidays: unknown".
- [q9] Shufersal's link refresh and NCR's second listing read have no time check. State: `.claude/OPEN_ISSUES.md`, Collector, "Shufersal's link refresh and NCR's second listing read have no time check".
- [q6] Mutation check counts any non-zero exit as caught. State: `.claude/OPEN_ISSUES.md`, Collector, "Mutation check counts any non-zero exit as caught".
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).
- [q11] Before this repo goes public: move the agent notes (CLAUDE.md, `.claude/`) out of it, the way flights-archive did on 2026-11-01 (its `.claude/` became a local-only git repo ignored by the code repo), and bring the q19 research from flights-archive's `.remember/q19/` (gitignored, no backup) into those notes. Owner's call when. Added 2026-11-01 (tooling audit).

## Done / Dropped
- [q7] 2026-11-01: the check fails a chain's day when no run that day, main or retry, listed a PriceFull, or a PromoFull, of the kinds it collects, unless a retry run was blocked (ruling R35); failed alerts now read "the day's runs fell short:"; two Fable reviews, no Critical (a main-run block cleared before the retries had silenced it: fixed). Deployed 12:42Z; live code_sha 90a1ee51cd20 = 50f3a07; first scheduled use 2026-11-02 10:45. Proof: ae0619c, 50f3a07, 527d21e; CI green at 527d21e.
- [q8] 2026-11-01: NCR listing paging under a moving directory: a repeated name reads the listing again from the start, once, logged; a repeat on that read too stops the run (ruling R34); every listing answer logged; two Fable reviews, no Critical; the second read's time check folded into q9 (owner). Deployed 12:01Z; manual run `120241Z-main-4c25` clean, its code_sha 97b839030d0a matching e239afe. Proof: 25ed78f, e239afe, 1306c9f; CI green at 186be99.
- [q4] 2026-11-01: `docs/operations.md` steps 7 and 9 rewritten from healthchecks.io's docs (a ping un-pauses a paused check; the period runs from the last ping). Proof: 4070f49.
- [q2] 2026-11-01: the owner acknowledged the build's deferred review findings: eleven left as they are, two queued (q6, q7). Proof: 4070f49 (the records).
- [q5] 2026-11-01: Rami Levy store 039's ZIP files accepted (4070f49, every entry read through) and their bare `<Root>` (b3f02a3), deployed; that day's ten archives stored by retry run `104159Z-retry-dcb5`, locked to 2036-10-29; a trimmed real fixture added (a53abd3). Proof: `docs/portals.md`, Rami Levy, store 039.

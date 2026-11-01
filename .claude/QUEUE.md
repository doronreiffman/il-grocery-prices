# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: schedules on since 2026-11-01 (Shufersal full files only, check 10:45); left: the first scheduled morning, 2026-11-02: read its check record after 10:45 Israel time; done when every chain's files are stored and no alert remains but Shufersal retries out of time with nothing missing (owner, 2026-11-01). State: `.claude/OPEN_ISSUES.md`, Collector, "Live".
- [q8] NCR listing paging under a moving directory. State: `.claude/OPEN_ISSUES.md`, Collector, "NCR listing paging under a moving directory".
- [q7] "Listed nothing" alarm takes the union over a chain's retry runs. State: `.claude/OPEN_ISSUES.md`, Collector, ""Listed nothing" alarm takes the union over a chain's retry runs".
- [q9] Shufersal's link refresh has no time check. State: `.claude/OPEN_ISSUES.md`, Collector, "Shufersal's link refresh has no time check".
- [q6] Mutation check counts any non-zero exit as caught. State: `.claude/OPEN_ISSUES.md`, Collector, "Mutation check counts any non-zero exit as caught".
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).

## Done / Dropped
- [q4] 2026-11-01: `docs/operations.md` steps 7 and 9 rewritten from healthchecks.io's docs (a ping un-pauses a paused check; the period runs from the last ping). Proof: 4070f49.
- [q2] 2026-11-01: the owner acknowledged the build's deferred review findings: eleven left as they are, two queued (q6, q7). Proof: 4070f49 (the records).
- [q5] 2026-11-01: Rami Levy store 039's ZIP files accepted (4070f49, every entry read through) and their bare `<Root>` (b3f02a3), deployed; that day's ten archives stored by retry run `104159Z-retry-dcb5`, locked to 2036-10-29; a trimmed real fixture added (a53abd3). Proof: `docs/portals.md`, Rami Levy, store 039.

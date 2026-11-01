# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: merged and deployed 2026-11-01 with the schedules off; first-deploy fixes deployed (Shufersal timeout, NCR Accept header, NCR text total); Shufersal full files only (owner's decision), on branch `shufersal-full-files`; left: review fold-ins, CI, deploy, the manual check, schedules on (owner's go given), then the first scheduled morning. State: `.claude/OPEN_ISSUES.md`, Collector, "Deployed 2026-11-01" and "Shufersal: full files only".
- [q5] Rami Levy store 039's files are ZIP archives under `.gz` names (`PK\x03\x04`; 4 refused on 2026-11-01 as "neither gzip nor XML", run 074709Z-main-a07f): accept a valid ZIP holding XML in the payload check, stored byte for byte, test-first with a mutation and a review. Until then the check reports them missing every day. State: this line.
- [q2] Owner acknowledges or reopens the review findings deferred during the build. State: `.claude/OPEN_ISSUES.md`, Collector, "Deferred review findings".
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).
- [q4] Fix `docs/operations.md` steps 7 and 9 on healthchecks.io: its docs (read 2026-11-01, configuring_checks) say a ping takes a paused check out of pause, so the manual check un-pauses it and the first scheduled ping resumes it; replace the two UNVERIFIED notes. State: this line (one doc edit, after the first deploy).

## Done / Dropped

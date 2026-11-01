# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: merged and deployed 2026-11-01 with the schedules off; manual runs found three fixes (Shufersal timeout and the NCR Accept header, deployed; the NCR text total, branch `fix-ncr-total`) and a Shufersal timetable redesign; left: redeploy and rerun on the owner's go, the Shufersal design, then the manual check and the schedules on (plan Task 11). State: `.claude/OPEN_ISSUES.md`, Collector, "Deployed 2026-11-01" and "Shufersal's daily runs".
- [q2] Owner acknowledges or reopens the review findings deferred during the build. State: `.claude/OPEN_ISSUES.md`, Collector, "Deferred review findings".
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).
- [q4] Fix `docs/operations.md` steps 7 and 9 on healthchecks.io: its docs (read 2026-11-01, configuring_checks) say a ping takes a paused check out of pause, so the manual check un-pauses it and the first scheduled ping resumes it; replace the two UNVERIFIED notes. State: this line (one doc edit, after the first deploy).

## Done / Dropped

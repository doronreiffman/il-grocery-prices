# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: built and reviewed on branch `collector` (plan Tasks 1–10, final whole-branch review clean, 2026-11-01); left: the owner's call on merging to `main` and pushing, then plan Task 11 (first deploy with the schedules off, manual runs, the Shufersal duration gate, Carrefour from il-central-1, schedules on), all on the owner's go. State: `.claude/OPEN_ISSUES.md`, Collector, "Not deployed".
- [q2] Owner acknowledges or reopens the review findings deferred during the build. State: `.claude/OPEN_ISSUES.md`, Collector, "Deferred review findings".
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).

## Done / Dropped

# Work queue

Most important first. One line per item: a `[qN]` id (never reused), what it is, where its state lives. A finished item moves to Done / Dropped with the date and a proof pointer; an item is dropped only on the owner's word.

## Queue

- [q1] Collector live: schedules on since 2026-11-01 (Shufersal full files only, check 10:45); left: the first scheduled morning, 2026-11-02, read its check record after 10:45 Israel time; clean → done with the proof. State: `.claude/OPEN_ISSUES.md`, Collector, "Live".
- [q5] Rami Levy store 039's files are ZIP archives under `.gz` names (`PK\x03\x04`; 4 refused on 2026-11-01 as "neither gzip nor XML", run 074709Z-main-a07f): accept a valid ZIP holding XML in the payload check, stored byte for byte, test-first with a mutation and a review. Until then the check reports them missing every day. Built and deployed (4070f49); their members start with a bare `<Root>`, accepted on branch `bare-root`; left: deploy it, store that day's files, record an archive's member list, a trimmed real fixture. State: this line.
- [q6] The mutation check counts any non-zero pytest exit as caught, so a test id that no longer exists (exit 4) passes as caught (happened 2026-11-01, a renamed template test): count exit 1 only, treat any other as an error; a test for the runner, and for its duplicate-name guard. State: this line.
- [q7] The "listed nothing" alarm (ruling R31) takes the union over a chain's retry runs, so a day Shufersal lists no PriceFull at all stays silent while its Stores run lists something (sharper since Shufersal runs one kind an invocation): alarm per full kind, when no run that day listed a chain's PriceFull, or its PromoFull. State: this line.
- [q8] NCR listing paging under a moving directory: retry run `101523Z-retry-8c22` (Rami Levy, 2026-11-01 10:15Z, 92 s) stopped "the NCR listing sent 'PriceFull7290058140886-001-732-20261101-111131.gz' again from iDisplayStart 890" (ruling R21: a repeated name means a server ignoring iDisplayStart); the next run, two minutes later, read all 1,256 names. Likely (unproven) cause: files published while the pages were read shifted the order. Hit in a retry run, it alerts "failed" for that chain. Next: the owner chooses, e.g. read the listing again from the start once on a repeat, or ask for the whole directory in one answer. State: this line.
- [q3] The rest of the project: the site, the processing pipeline (Airflow, dbt) and the AI parts, designed in conversation from the picture the owner approved on 2026-10-31 (one headline basket of identical barcodes; an AI that reads promotion fine print). Research and state: `/Users/doronreiffman/Projects/flights-archive/.remember/q19/` (local, untracked: `STATE.md`, `supermarket/`).

## Done / Dropped
- [q4] 2026-11-01: `docs/operations.md` steps 7 and 9 rewritten from healthchecks.io's docs (a ping un-pauses a paused check; the period runs from the last ping). Proof: the commit that closes q5.
- [q2] 2026-11-01: the owner acknowledged the build's deferred review findings: eleven left as they are, two queued (q6, q7). Proof: this session's records commit.

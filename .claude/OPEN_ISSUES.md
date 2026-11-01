# Open issues

Currently open blockers, deferred bugs and "fix someday" items, each with its current state and next move. Replace an entry when its state changes; delete it when resolved.

## Collector

- **Live: schedules on since 2026-11-01 about 11:10 Israel time** (stack `il-grocery-prices`, commit 4fe53e8; function `il-grocery-prices-CollectorFunction-ZqTXXHocLDX9`, bucket `il-grocery-prices-archivebucket-fmnv3dorojol`; 17 schedules, Asia/Jerusalem; first scheduled run 2026-11-02 06:30, first scheduled check 10:45). Day one (2026-11-01, manual runs): every chain collected (Shufersal Stores, 416 PriceFull, 417 PromoFull, 279 Promo; Carrefour 453; Rami Levy 666 of 670; Osher Ad 92; Yochananof 237); the manual check (`checks/date=2026-11-01/check-090642Z-check-a312.json`, locked to 2036-10-29) raised 7 alerts, all expected (no retry runs that day; store 039's four ZIP files, q5; one Shufersal update file a morning run listed and never reached). Alert email subscription confirmed by the owner, and the manual check's alert email arrived (Gmail, from no-reply@sns.amazonaws.com, "il-grocery-prices 2026-11-01: 7 alerts"); healthchecks.io check created, paused, then pinged by the manual check; the owner turned it back on. Next move: read the 2026-11-02 check record after 10:45 Israel time; clean → q1 done.
- **Shufersal: full files only, each full kind run twice in the morning** (owner, 2026-11-01; `.claude/DECISIONS.md`), live with the schedules (4fe53e8). Risks kept: on a day Shufersal's pages run much slower than 25 s, a second morning run may stop short (the retry picks up the rest) and a retry may run out of time with nothing missing, which alerts as failed. Shufersal's update files (`Price`, `Promo`, hourly) are not collected until a polling run is designed (QUEUE q3).

## Portals

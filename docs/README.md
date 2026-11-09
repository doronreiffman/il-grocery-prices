# Design notes

Written while building the project: each note says what was decided and why, the alternatives rejected, and what a review changed. Tags like (q7) are items in the project's work queue, kept outside this repository.

- [collector.md](collector.md): the collector's design: which chains and files, how a morning runs, the write-once archive, identification, alerts and cost.
- [portals.md](portals.md): how each chain's portal serves its files, as observed, and what the code must handle because of it.
- [update-files.md](update-files.md): the update files through the day: the polls, Shufersal's passes, and the update day the next morning's check judges.
- [operations.md](operations.md): deploying the collector, running it by hand, reading what it wrote and a day of update files, clearing a stopped chain, dropping a chain and what it costs; then building and publishing the shopper site by hand, the headline basket among it, the site run every morning, and deploying step one.
- [headline-basket.md](headline-basket.md): the headline basket's design: the basket, the number rules, the pipeline, and the words the page may and may not use.
- [shopper-site.md](shopper-site.md): the shopper site's design: a page per product at nine store formats, the deal against its listed prices, how often it goes on promotion, the front page's deals, the daily forecast and its public record, and what the promotion survey changed.
- [terms.md](terms.md): the law's clause on using the price files, quoted, and what it asks of the project.
- The build plans, task by task, each with what changed during the build ("Deviations"): [collector-plan.md](collector-plan.md), [headline-basket-plan.md](headline-basket-plan.md) (step one, by hand), [headline-basket-step-two-plan.md](headline-basket-step-two-plan.md) (step two, every morning), [update-files-plan.md](update-files-plan.md) (the update files through the day) and [shopper-site-plan.md](shopper-site-plan.md) (the shopper site's step one).

# il-grocery-prices

Personal portfolio project. Collects, every morning, the price files Israeli supermarket chains must publish under the food-competition law (s.30), for a later site that prices one basket across chains. The collector's design is `docs/collector.md` (read it before changing the collector), its build plan `docs/collector-plan.md`, each portal's mechanics `docs/portals.md`.

## Hard rules

- Personal accounts only. Nothing touches the owner's employer: no work systems, accounts, cloud or credentials.
- AWS: profile `flights-sam`, region `il-central-1`, the stacks `il-grocery-prices` (collector) and `il-grocery-prices-site` (the public site), and nothing else. `scripts/publish.sh` is the only thing that deletes, and only in the site bucket, after `basket.check` and `basket.guard` pass. Before any AWS command, run `aws sts get-caller-identity --profile flights-sam` and confirm account 137953273942 and user doron-admin. Every other profile on this machine belongs to the employer.
- GitHub: before any `gh` call or `git push`, `gh auth status` must show doronreiffman as the active account; any other account is the employer's: stop and tell the owner. Subagents never run `gh` or push; the main session does.
- On the owner's go only: every `git push`, `sam deploy`, any AWS write, enabling or disabling the schedules. Read-only AWS calls need no ask.
- Chains in version one, and nothing else: `shufersal`, `ramilevy`, `osherad`, `carrefour`, `yochananof`. The NCR chains log in with the usernames the gov.il list prints (https://www.gov.il/he/pages/cpfta_prices_regulations, updated 12.08.2026) and an empty password, through the web form the list links (https://url.publishedprices.co.il); never FTP unless the owner says so.
- A block stops the chain: a 401, 403 or 429, a captcha or verification page, or HTML where a file belongs stops that chain, latches it until the owner clears it, and raises one alert. Never a browser User-Agent, another IP, a proxy or another route. One exception: a 403 from Shufersal's file host (`pricesprodpublic.blob.core.windows.net`) from two minutes before the link's `se=` expiry on means re-read the listing for a fresh link, once.
- Polite and identified: one request at a time per chain; User-Agent `il-grocery-prices/<version> (+<repo URL>; <contact email>)`, given at deploy (or in `GROCERY_USER_AGENT` for `scripts/probe.py`); code refuses one without `+https://` and `@`.
- Raw files are never published; only derived numbers, credited to the chains' published files. Fixtures under `tests/fixtures/` keep the portals' real structure (trimming changes values only, never a field's type or layout: check a trimmed file against the raw probe answer), at most three items a file, synthetic prices, names and barcodes, and no `sig=` values, cookies or tokens. `probe-out/` (raw probe output) stays gitignored.
- Storage is write-once: every raw, manifest and check write uses `IfNoneMatch="*"` and a ten-year governance Object Lock. Never delete, overwrite or bypass retention.
- Keep credentials, the owner's email, the health-check URL and any session token out of the repo.
- Every datetime is time-zone aware; a file belongs to the Israel date in its name. Never a naive `astimezone()`: this Mac runs on Asia/Jerusalem and CI on UTC, so a naive conversion passes in CI and is wrong here.
- Tests for every component and a mutation for every rule (`scripts/mutation_check.py`); coverage floor 95% on `collector`. Before anything ships, a fresh subagent that has not seen your reasoning reviews it. Test data never reads the clock: fixed times, and `gzip.compress(..., mtime=0)`.
- No dependency younger than one month; pin versions. Cheap, boring infrastructure; every proposal carries a monthly cost estimate.
- Docs in plain words; no "we".

## Active threads

- Collector: live since 2026-11-01 (17 schedules, Shufersal full files only, check 11:48); first scheduled morning clean 2026-11-02; next: the Saturday check (q10) · `.claude/OPEN_ISSUES.md` Collector.
- Showcase (headline basket): design `docs/headline-basket.md` (read it before touching the basket); step one live since 2026-11-02 at https://d153udx05irk2f.cloudfront.net (noindex, by link; stack `il-grocery-prices-site`), each day a hand build until step two goes on; step two (q14) deployed 2026-11-03 with its schedules off (`BasketFunction`, six schedules at 12:03 and 12:33; q12's moved Osher Ad runs with it) and its manual runs clean; `BasketScheduleState=ENABLED` on the owner's go, then the first scheduled morning: `docs/operations.md`, "The headline basket, every morning"; the basket is `src/basket/baskets/v1.json` (approved 2026-11-02; a change is a new version); how to run it by hand: `docs/operations.md`, "The headline basket, by hand" · q13, q14, `.claude/OPEN_ISSUES.md` Showcase.

## Working notes

- Test baseline (2026-11-03, branch `q14-step-two` at d11719a): 1,145 tests, coverage 99.81% over `collector` and `src/basket`, 906 mutations, all caught.

- Work queue `.claude/QUEUE.md`; open issues `.claude/OPEN_ISSUES.md`; decisions `.claude/DECISIONS.md`.

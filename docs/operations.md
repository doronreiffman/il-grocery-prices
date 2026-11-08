# Operating the collector

How to deploy the collector, run it by hand, read what it wrote, read a day of update files, clear a stopped chain, drop a chain, and what it costs; then how to build and publish the headline basket by hand, and how the basket function does it every morning. What the collector does and why: [collector.md](collector.md); each portal's mechanics: [portals.md](portals.md).

## What runs when

One Lambda function (stack `il-grocery-prices`, region il-central-1, Tel Aviv) runs on daily schedules in Israel time, so daylight saving needs no handling: the morning's 17, below, and 27 update-file polls through the day on a switch of their own ("Through the day: the update-file polls", below). The morning's:

| Israel time | Run | Event |
|---|---|---|
| 06:30 | Shufersal store list | `{"mode": "main", "chain": "shufersal", "kinds": ["Stores"]}` |
| 06:33 | Rami Levy, every kind | `{"mode": "main", "chain": "ramilevy"}` |
| 06:39 | Carrefour, every kind | `{"mode": "main", "chain": "carrefour"}` |
| 06:45 | Shufersal full price files | `{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}` |
| 07:00 | Shufersal full price files, carrying on | `{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}` |
| 07:03 | Yochananof, every kind | `{"mode": "main", "chain": "yochananof"}` |
| 07:15 | Shufersal full promotion files | `{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}` |
| 07:30 | Shufersal full promotion files, carrying on | `{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}` |
| 08:18 | Osher Ad, every kind | `{"mode": "main", "chain": "osherad"}` |
| 09:30 to 11:18 | One retry per chain, Shufersal's one per kind, three hours after that kind's first morning run | the main events with `"mode": "retry"`: Shufersal at 09:30 (Stores), 09:45 (PriceFull) and 10:15 (PromoFull); Osher Ad at 11:18 |
| 11:48 | The check | `{"mode": "check"}` |

A run can take up to 15 minutes (Lambda's longest), so Shufersal's runs start 15 minutes apart and one chain never gets two requests at once. Shufersal collects its store list and full files only (owner, 2026-11-01): its listing pages took 15 to 39 s each from AWS that day (medians 25 to 35 s), and a full kind took two runs, so its update files wait for poll runs of their own, which come with its passes (rollout step 3, [update-files.md](update-files.md), section 7). How often it publishes them is not known: the one record, 2026-11-01, shows batches stamped across stores at about 03:00 and about 10:00, and how often a store replaces its file is measured once its passes run. Its second run of a full kind picks up where the first stopped instead of re-reading the pages the first already read: it reads the day's earlier manifests, then page 1, then the furthest page the first run read, again, and on to the last page ([shufersal-resume.md](shufersal-resume.md), ruling R37). A Shufersal listing page whose request times out (its wait is 60 s) is asked for again, up to two more times, ten seconds apart, while the run has time ([shufersal-page-retry.md](shufersal-page-retry.md), ruling R38). Rami Levy, Osher Ad and Yochananof share one portal host (`url.publishedprices.co.il`), so their runs start at least 15 minutes apart, and their sessions never overlap. Osher Ad's files are stamped from about 07:00 to 09:00, most at 08:00 and the store list at 08:05 (on 2026-11-02), so its main run starts at 08:18. A retry run fetches only what is still not stored. The check starts after the last retry run can have finished; it writes a check record, emails when a chain's morning is incomplete, a chain is stopped or a retry run failed, and pings healthchecks.io. It judges the morning from that day's main and retry runs only: a poll's names, listed and perhaps not yet stored, are judged with the rest of its day the next morning ("Reading an update day", below). A chain's retry runs fail when none covered one of the kinds the chain collects, when one ended with an error, or when together they listed nothing for the day and none was blocked (`the retry runs listed nothing for the day (unparsed names: N)`): a portal that renames its files so that none can be read, or dates them all another day, ends its runs without an error, and this alert is how it shows. They fail too when no run that day, main or retry, listed a full kind the chain collects (`no run listed a PriceFull for the day`, or `a PromoFull`) and no retry run was blocked: the retry runs' names are taken together, so a Shufersal morning with no PriceFull at all would otherwise pass on its Stores run's names. A day a chain publishes nothing at all alerts the same way. The design gave 10:00 for the check; it is at 11:48 because the last retry run (Osher Ad's) starts at 11:18 and may run until 11:33, and 15 minutes more leave room for its manifest write and the schedulers' start-up lag. A retry run that runs out of time (`"error": "stopped: under 90 s left"`) is a failed run even with nothing missing, since it may not have read the whole list, and a name it never reached is missing without showing as missing: on a kind already read in full, a retry makes a fresh pass of its 21 pages within about 810 s, so on a day the pages average more than about 38 s (2026-11-01: 15 to 39 s, medians 25 to 35) it runs out of time. The one exception (ruling R36, as ruling R37 amends it): each kind the stopped retry covers was read in full that day, every name the retry listed was listed by another run that read that kind, and the chain has nothing missing. Then the retry is not a failed run: no email goes, and the check record names it under `short_of_time`. A kind is read in full when the listing pages the day's runs read, as their manifests record them, join up from page 1 to the last page; a run of a chain that records no pages (every chain but Shufersal) reads its kinds in full when it ended with no error and was not blocked. The runs that vouch for the retry's names are any run that read the whole list on its own and, when the other runs' pages join up into a full reading without the retry's own, each run whose pages carry that reading further along the list than the pages joined before them (the reading is joined from the front of the list; among pages that start at the same place, the furthest-reaching are joined first). A run that read only part of the list, where the pages joined before it already cover that part, vouches for no name, and the retry never vouches for itself. On a day the runs did not read the kind in full, or the stopped retry listed a name no such run did (a run made before the day's files were all up lists only what was up), the alert still goes, and it is the sign that the morning fell short. When the pages of a Shufersal full kind do not join up, the failed alert says so and names the pages no run read, for example `the PriceFull list was not read in full: pages 17 to 21 never read` (a page a run read only part of is named apart: `page 19 read in part`); it does not when a retry run was blocked, which the stopped alert covers.

Neither the schedules nor Lambda retry a failed invocation: the retry run is the retry. A block (a 401, 403 or 429, a captcha or verification page, or an HTML page where a file belongs) stops that chain until you clear it (below).

A second function in the same stack, the headline basket's, runs six schedules of its own after the check, on a switch of its own ("The headline basket, every morning", below).

Where things land in the bucket:

- `raw/chain=<chain>/date=YYYY-MM-DD/<file name as published>`: the files, byte for byte, locked for ten years (governance mode). A different file under a stored name is kept beside it with 12 hex digits of its SHA-256 added to the name.
- `manifests/date=YYYY-MM-DD/<chain>-<run id>.json`: one per run, locked.
- `checks/date=YYYY-MM-DD/check-<run id>.json`: one per check, locked.
- `state/<chain>.json`: the chain's stopped latch, plain and rewritable.

The date is an Israel date: for a raw file the one in its name, for a manifest or check record the day the run was for. A run id is `<HHMMSS>Z-<mode>-<4 hex>`, the start time in UTC. Logs go to the log group `/il-grocery-prices/collector`, kept 30 days.

### Through the day: the update-file polls

These 27 schedules follow a switch of their own, `PollScheduleState`, not `ScheduleState`:

| Israel time | Run | Event |
|---|---|---|
| 12:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 12:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 12:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 13:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 14:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 14:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 14:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 15:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 16:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 16:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 16:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 17:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 18:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 18:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 18:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 19:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 20:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 20:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 20:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 21:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 22:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 22:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 22:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |
| 23:05 | Carrefour, update files | `{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}` |
| 23:20 | Rami Levy, update files | `{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}` |
| 23:35 | Yochananof, update files | `{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}` |
| 23:50 | Osher Ad, update files | `{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}` |

A poll is a run like the morning's, held to the update files (`Price` and `Promo`, the chain's `polled` in `src/collector/chains.py`): it reads the chain's listing, takes that day's update files not yet stored, and writes a manifest whose run id says `poll` ([update-files.md](update-files.md); ruling R39). The NCR portal and Carrefour's keep the day's files listed through the day and past midnight ([portals.md](portals.md)), so a poll takes everything published since the one before, and a poll that stops on time or fails leaves the rest to a later poll that day. Every two hours from 12:20, so a poll has about two hours' files to fetch (Rami Levy publishes about 150 update files an hour, about 300 files in 5 to 7 minutes: [update-files.md](update-files.md), section 2), and once more at 23:20 so the day's last poll comes as late as the day allows; Osher Ad's 23:50 poll can run past midnight, and the next day's names it sees are counted (`other_days`), not taken: the next morning's main run takes them. Rami Levy, Yochananof and Osher Ad share the NCR host, so their polls start 15 minutes apart (ruling R30), and Carrefour, on a host of its own, follows them. The first poll starts at 12:20, once the morning's last run, the check and the basket's five extractions (12:03, up to 15 minutes) can have ended: no poll is in flight while they run, a rule `tests/test_template.py` pins. The basket run at 12:33 can overlap the 12:20 and 12:35 polls, another function that touches no portal. The design spaced the polls this way when the account's Lambda concurrency quota read 5; it read 400 on 2026-11-07, and the spacing is kept ("Cost", below). The polls follow `PollScheduleState`, `DISABLED` until the owner turns it on (Deploy, step 9); the function reads the same switch, and the 11:48 check judges the day before's update files only while it is on ("Reading an update day", below). Shufersal's passes, three a day for each update kind, each of two runs 15 minutes apart, come with rollout step 3 ([update-files.md](update-files.md), sections 2 and 7).

## Deploy

You need the personal AWS account (nothing from an employer) with il-central-1 enabled, the AWS CLI and the AWS SAM CLI as flights-archive uses them, and Python 3.13 on your Mac for `sam build` (or `sam build --use-container` with Docker). Every `aws` and `sam deploy` command below names the `flights-sam` profile and the region: every other profile on this Mac is the employer's, and a command without `--profile` would run against one of them.

1. **Account check.** Sign in as for flights-archive (`aws login --profile flights`), then:

   ```bash
   aws sts get-caller-identity --profile flights-sam --region il-central-1
   ```

   It must show account `137953273942` and a user ARN ending in `user/doron-admin`. Anything else: stop.

2. **healthchecks.io.** Create a check with period 1 day and grace 2 hours, and copy its ping URL (`https://hc-ping.com/<uuid>`). The 11:48 check pings it each morning; when no ping arrives, healthchecks.io emails. That catches a morning where nothing ran at all. Create a second check the same way for the basket run; its URL is `BasketHealthcheckUrl` ("The headline basket, every morning", below).

3. **Build and deploy with the schedules off.** Deploy from a clean, committed tree (`git status --porcelain src/` prints nothing): every manifest and check record carries `code_sha`, a fingerprint of `src/collector/`, and only a committed tree lets you find the commit behind it (step 8). The values go on the command line, never into a file in the repo; don't use `sam deploy --guided`, which offers to save them to `samconfig.toml` (that file is gitignored as a second guard).

   The command below, with every switch `DISABLED`, is a first deploy's; on the live stack, pass each switch as it stands ("On the live stack", after the command).

   ```bash
   sam build
   sam deploy --profile flights-sam --region il-central-1 --stack-name il-grocery-prices \
     --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset --parameter-overrides \
     'UserAgent="il-grocery-prices/0.1.0 (+https://github.com/<you>/il-grocery-prices; <email>)"' \
     'AlertEmail=<email>' \
     'HealthcheckUrl=https://hc-ping.com/<uuid>' \
     'ScheduleState=DISABLED' \
     'PollScheduleState=DISABLED' \
     'SiteBucketName=il-grocery-prices-site-sitebucket-<suffix>' \
     'SiteDistributionId=<distribution id>' \
     'BasketHealthcheckUrl=https://hc-ping.com/<basket uuid>' \
     'BasketScheduleState=DISABLED'
   ```

   The inner double quotes around the User-Agent matter: `--parameter-overrides` splits on spaces, and without them the value is cut at the first space (the template refuses a value without `+https://` and an `@`, which catches that). Review the change set and confirm. The site's bucket and distribution are the site stack's outputs `SiteBucketName` and `SiteDistributionId` ("The two gates", step 1, below), so that stack is deployed first; the template refuses a bucket whose name does not start `il-grocery-prices-site-sitebucket-`, so the archive bucket can never be given for it. `BasketScheduleState` is the basket function's own switch; `sam build` also builds its DuckDB layer ("The headline basket, every morning", below). `PollScheduleState` is the update-file polls' own switch, `DISABLED` until the polls have been run by hand (steps 6, 7 and 9).

   On the live stack, the deploy that first carries the polls passes `'ScheduleState=ENABLED'` and `'BasketScheduleState=ENABLED'` as they stand, with `'PollScheduleState=DISABLED'`: the command's values are what keeps the morning and the basket running, since `sam deploy`'s change-set table looks the same either way. Reading its change set ([update-files-plan.md](update-files-plan.md), "Deploying this branch"): `CollectorFunction` and `BasketFunction` modified, not replaced (both are built from `src/`, so both zips change; the collector's environment gains `POLL_SCHEDULE_STATE`); 27 new schedules, each with its own IAM role (SAM adds one per `ScheduleV2` event: the 2026-11-07 deploy's change set listed 23 schedules and 23 `<schedule>Role` roles); the existing 23 schedules and their 23 roles modified, not replaced, as on every deploy, and the 23 schedules must stay enabled, which `sam deploy`'s change-set table does not show: it gives each resource's operation, logical id, type and replacement only, and on 2026-11-07 it listed every one of the 23 schedules as `Modify`, no replacement, with no switch changed, so the command's `ENABLED` values are the guard and the state check after the deploy (below) the proof; the DuckDB layer removed and added under a new logical id, as on every build (on 2026-11-04 and 2026-11-07 only the 41 cpython-314 `.pyc` caches differed, never loaded by python3.13: compare the live layer's files with `.aws-sam/build/DuckDbLayer` before executing); nothing else removed or replaced, and nothing on `ArchiveBucket`, `AlertTopic` or the log groups. Anything else: cancel the change set and find out why first.

   On the live stack, after the deploy and before the next 06:30, read each schedule's state (it only reads):

   ```bash
   aws scheduler list-schedules --query "Schedules[].[Name, State]" --output table --profile flights-sam --region il-central-1
   ```

   SAM names each schedule for its function and its event in `template.yaml` (`CollectorFunctionMainRamiLevy`, `CollectorFunctionCheck`, `CollectorFunctionPollRamiLevy1220`, `BasketFunctionExtractShufersal`). Every `CollectorFunctionMain…`, `CollectorFunctionRetry…` and `CollectorFunctionCheck` schedule and the basket's six (`BasketFunction…`) must say `ENABLED`, and every `CollectorFunctionPoll…` one `DISABLED` until the polls' switch goes on (step 9). The list also holds other stacks' schedules in the account, such as flights-archive's `CollectorFunctionEveryTwoMinutes`. A schedule in the wrong state: deploy again before 06:30 with its switch as it should stand.

4. **Confirm the alert email.** AWS sends a subscription confirmation to the `AlertEmail` address; confirm it, or no alert reaches you.

5. **Names and the live User-Agent.** The function's and the bucket's names are in the stack's outputs:

   ```bash
   FN=$(aws cloudformation describe-stacks --stack-name il-grocery-prices --query "Stacks[0].Outputs[?OutputKey=='CollectorFunctionName'].OutputValue" --output text --profile flights-sam --region il-central-1)
   BUCKET=$(aws cloudformation describe-stacks --stack-name il-grocery-prices --query "Stacks[0].Outputs[?OutputKey=='ArchiveBucketName'].OutputValue" --output text --profile flights-sam --region il-central-1)
   aws lambda get-function-configuration --function-name "$FN" --query Environment.Variables.USER_AGENT --profile flights-sam --region il-central-1
   ```

   The User-Agent must read exactly as you gave it.

6. **One manual run per chain.** Run the manual runs only once that day's files are on the portals: after the chains' morning publishing, not just after midnight Israel time. A run that finds nothing listed stores nothing, and a manifest with `"listed": 0` is not a clean run. Start each run asynchronously (`--invocation-type Event`), the way the schedules do. A run can take 15 minutes; a plain invoke waits for the answer, the CLI gives up after 60 seconds and sends the invoke again, and the chain then has two runs at once. Each command answers `"StatusCode": 202` at once. Start them one at a time and let each finish before the next: Shufersal's runs must never overlap (one request at a time per chain), nor may the three chains on the NCR portal, and one at a time keeps the logs readable.

   ```bash
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "shufersal", "kinds": ["Stores"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "ramilevy"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "osherad"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "carrefour"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "main", "chain": "yochananof"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   ```

   Watch a run in its logs; it ends with one JSON line (`mode`, `chain`, `day`, `run_id`, `kinds`, and counts of `listed`, `stored`, `failed`, `not_attempted`, plus `blocked` and `error`), then Lambda's `REPORT` line with the duration:

   ```bash
   aws logs tail /il-grocery-prices/collector --follow --since 10m --profile flights-sam --region il-central-1
   ```

   A Shufersal run also logs one line for each listing page it reads, before taking the page's files: `shufersal PriceFull page 7 of 21: 20 rows in 41.2 s` (the page count is the last page this run's page 1 named; `?` for a detour read before page 1). A page whose request timed out is asked for again (ruling R38): the run logs a warning for each try that timed out, `shufersal PriceFull page 7: try 1 of 3 timed out after 60.5 s; again in 10 s`, ending "again in 10 s" only when another try follows (after the third try, or when the run has too little time left for another, the line ends at the seconds), and the page's line then names the try that read it: `shufersal PriceFull page 7 of 21: 20 rows in 45.0 s (try 2)`.

   A good run has `"blocked": null`, `"error": null` and `"failed": 0`. A run that ran short of time ends with `"error": "stopped: under 90 s left"`; start the same event again (or the retry event, `"mode": "retry"`): stored files are skipped, so it carries on where the first stopped. Carrefour's first run decides whether it stays (below).

   **Shufersal's full files take two runs each.** The first run of a full kind usually ends with `"error": "stopped: under 90 s left"`; the second, the same event again, picks up where the first stopped (page 1, then the first run's furthest page again and on) and finishes. If the second stops short too, start it a third time; it picks up where the second stopped. On 2026-11-01 its pages took 15 to 39 s each, and a day much slower than that needs more runs. On 2026-11-06 PriceFull's pages took a median of 34.7 s (29.1 to 44.9 s) and PromoFull's 41.75 s (28.8 to 60.0 s), and 6 of about 39 page requests timed out at the 60 s wait. A page that times out is now asked for again, up to twice (ruling R38), but a slow spell still ends a run with `"error": "listing failed: … timed out on 3 tries: …"`; the next run of that kind picks up where it stopped. (The duration gate this step once held is gone: at that page speed one kind alone does not fit a run.)

   **The update-file polls by hand,** before their switch goes on, so with `PollScheduleState` still `DISABLED`: with it on, a manual poll of an NCR chain after 12:20 could overlap a scheduled one on the same host (ruling R30). One per chain that polls, each its scheduled event ("Through the day: the update-file polls", above), in the afternoon after 12:20, clear of the basket's extractions (12:03, up to 15 minutes), started asynchronously and one at a time as above: never two NCR chains together. Start Rami Levy's first, soon after 12:20, in its first scheduled poll's slot: the design estimates that poll at about 420 files in 7 to 10 minutes, what the 09:33 retry run left ([update-files.md](update-files.md), section 2), and Rami Levy publishes about 150 update files an hour, so a manual poll started later has more to take and can run out of time. A manual poll that ends with `"error": "stopped: under 90 s left"` is started again, the same event, once it has ended and at least 15 minutes after it started (ruling R30), and again until one ends with `"error": null`, before the next chain's: stored files are skipped, so each carries on where the one before stopped, and the chain's last poll of the day reads its list in full.

   ```bash
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "poll", "chain": "yochananof", "kinds": ["Price", "Promo"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$FN" --invocation-type Event --payload '{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   ```

   Read each poll's manifest (step 8): `listed` (that day's update files the listing gave), `files` (what it stored; names the day had already stored, such as those the morning's runs took, are listed and skipped), `failed` (none, on a good run) and `other_days` (the names of other days it saw); and its `REPORT` line in the logs: its `Duration` is in milliseconds, and the design estimates a two-hourly poll at about 400 s for Rami Levy, 150 for Yochananof, 100 for Osher Ad and 60 for Carrefour ([update-files.md](update-files.md), section 6), and Rami Levy's 12:20 poll at 7 to 10 minutes (section 2); a manual poll started later than its chain's first scheduled poll has more to take. A good poll has `"blocked": null` and `"error": null`, as a morning run does. A poll that stops on time still lists the rest of its listing, taking nothing (ruling R40): each name of the day it did not reach is in `listed`, and in `not_attempted` unless the day had stored it before; the next poll's `listed` holds each of them, and its `files` those it stored.

7. **A manual check.** The check is short, so a plain invoke is fine; `--cli-read-timeout 900` keeps the CLI waiting rather than sending it again, which would check twice and could email twice:

   ```bash
   aws lambda invoke --function-name "$FN" --payload '{"mode": "check"}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-check.json --profile flights-sam --region il-central-1
   ```

   `/tmp/il-grocery-check.json` names the check record (`record`) and counts the alerts. The check pings healthchecks.io, which should show the ping within a minute. healthchecks.io measures a check's period from its last ping (the worked example on https://healthchecks.io/docs/, read 2026-11-01), so from that ping on it expects the next within a day and two hours. If the schedules will be on before then (step 9), leave the check running: the first scheduled check pings in time. If not, pause it: pausing is how its docs say to avoid unwanted alerts (same page; that a paused check sends none is implied, not stated). A ping normally takes a paused check out of pause: "Normally, when you ping a paused check, it leaves the paused state and goes into the 'up' state" (https://healthchecks.io/docs/configuring_checks/). The exception is on the same page: a check whose filtering rule for pinging a paused check is set to "Ignore the ping, stay in the paused state" stays paused, ignoring every ping, until it is resumed by hand. Leave that rule unset, and a manual check run while the check is paused un-pauses it. It also expects the day's retry runs: with none run that day, it reports each chain as failed ("the day's runs fell short: no retry run covered …") and emails you, which proves the email works. For a clean check, first run each retry event of the timetable (one per chain, Shufersal's one per kind) by hand, one at a time as there; each downloads only what is still missing. Do this only once that day's files are on the portals (step 6): the check fails a chain whose retry runs list nothing for the day, so a retry started too early makes the manual check alert every chain.

   A manual check can also ask for the day before's update files, which the scheduled check judges only while `PollScheduleState` is on; this one judges them whatever the switch says. Run it the morning after the manual polls (step 6), after the 11:48 check, so the day before is the day of the manual polls: run on a morning after a day with no poll, it emails `<chain>: no poll run read the Price and Promo lists in full on <day>.` for each of the four chains. It judges that morning too, so its email repeats any alert the 11:48 check sent that morning, a stopped chain's apart (already marked alerted):

   ```bash
   aws lambda invoke --function-name "$FN" --payload '{"mode": "check", "update_day": true}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-check.json --profile flights-sam --region il-central-1
   ```

   Read its record's `update_day` as "Reading an update day" (below) has it: each chain's poll in `polls`, a complete pass for each update kind in `passes`, nothing in `missing`, `failed` null. A chain whose last manual poll stopped on time (not started again until one ended clean, step 6) reads otherwise, from the procedure, not from a fault in the collector: that poll's `"error": "stopped: under 90 s left"` in `polls` and its run in each kind's `open` in `passes`; and when none of the chain's polls that day ended clean, no `complete` pass, `failed` naming both kinds, and the email `<chain>: no poll run read the Price and Promo lists in full on <day>.` That poll's `not_attempted` holds every name of the day it did not reach and the day had not stored before (ruling R40), and its count is in `polls`; the names no later poll stored are in `not_tried` and in the email `<chain>: <n> update files listed on <day> and not stored (… never tried: a poll stopped on time before reaching them): <names>.`

8. **Read what it wrote.** List a day's manifests, print one, and print the check record:

   ```bash
   aws s3 ls "s3://$BUCKET/manifests/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/manifests/date=YYYY-MM-DD/<chain>-<run id>.json" - --profile flights-sam --region il-central-1
   aws s3 ls "s3://$BUCKET/checks/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/checks/date=YYYY-MM-DD/check-<run id>.json" - --profile flights-sam --region il-central-1
   ```

   A manifest holds: `mode` (`main`, `retry` or `poll`, as its run id says), `kinds` (the kinds the run was asked for), `listed` (that day's file names the listing gave, of the kinds asked for), `files` (each stored or found stored, with `outcome` `stored`, `exists` or `conflict`, `size` and `sha256`), `failed` (tried and not stored, with why), `not_attempted` (listed, never tried because the run stopped; for a poll of a chain whose listing does not page that stopped on time, also every name of the day it did not reach and the day had not stored before, ruling R40), `unparsed` (listed names that could not be read), `listing_read_at` (null when the listing was never read), `blocked`, `error`, `code_sha`, `pages`: empty for every chain but Shufersal, whose runs record each listing page they read, in the order read, with `kind`, `page`, `rows`, `first` and `last` (the first and last file name on the page as listed, without `.gz`, any date), `last_page` (the last page the page's pager names, null when it names none), `seconds` (the time of the request that read the page, rounded to 0.1 s, the 0.5 s pause before it included, except on the run's first request, which has none), `tries` (the requests the page took: 1, or 2 or 3 when earlier tries timed out), `in_order` (false when the page's names are out of order, or its first name sorts before the last name of the page numbered one less read just before it) and `taken_through` (the last name the run took from the page, or the page's last name once the run took the last row the page gave; null for a page it took nothing from, such as one it stepped back from); and `timeouts`: each Shufersal listing page request that timed out, in the order they came, with `kind`, `page`, `attempt` (the try's number) and `seconds` (how long it waited), whatever the run then ended with, and empty on every other run (an expired link's refresh logs its tries and does not list them); and `other_days`: for each date other than the run's that names of the kinds asked for carry, how many distinct such names the listing gave (`{"YYYY-MM-DD": count}`, empty when none). The run never stores those names or puts them in `listed`. In a morning's main run it shows how much of the day before the listing still holds; in Osher Ad's 23:50 poll, the next day's names, which the next morning's main run takes. "The store published nothing" shows as a store with no file in `listed` (coverage counts those); "listed but not stored" as a name in `listed` that the bucket does not hold (the check record's `missing`). Only the second is the collector's failure.

   A check record holds, per chain: `manifests` (how many main and retry runs), `listed` and `stored` counts, `missing` (every listed name not stored), `stopped` (since when and why, or null), `failed` (why the retry runs fall short, or null), `short_of_time` (each retry run that stopped short of time on a day its kinds were read in full, every name it listed was listed by another run that read that kind, and nothing is missing, as `<run id> (<kinds>)`: not a failed run, and no email), `read_in_full` (for each full kind the chain collects, the ids of the runs that read it in full: every run whose manifest holds no page records, as other chains' runs and Shufersal's from before page records, that covered the kind, was not blocked and ended with no error, one that listed nothing included; beside them, Shufersal's runs whose pages make up the joined full reading, a run that adds nothing to it, such as a second whole pass, not named, or, with a page out of order that day, each Shufersal run that read every page in one go; null when the kind was not read in full) and `coverage` (stores with that day's full price file against the stores in the latest store list: `published`, `expected`, `ratio`, or `"unknown"` with a `note`). The chains' figures are judged from the day's main and retry runs only; a poll's files count only in `stored`. Then `update_day` (null, unless the poll switch is on or the check asked for it: then the day before's update files, "Reading an update day", below), `alerts`, `run_id`, `checked_at` (UTC) and `code_sha`.

   Check that a stored file is locked:

   ```bash
   aws s3 ls "s3://$BUCKET/raw/chain=ramilevy/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3api head-object --bucket "$BUCKET" --key "raw/chain=ramilevy/date=YYYY-MM-DD/<file name>" --query "[ObjectLockMode, ObjectLockRetainUntilDate]" --profile flights-sam --region il-central-1
   ```

   It should show `GOVERNANCE` and a date ten years on. To find the commit behind a `code_sha`, check out a candidate commit and run `PYTHONPATH=src .venv/bin/python -c 'from pathlib import Path; from collector.handler import code_sha; print(code_sha(Path("src/collector")))'`.

9. **Turn the schedules on**, on the owner's go: the same `sam deploy` command with all nine parameters again and `'ScheduleState=ENABLED'`, the other two switches (`PollScheduleState`, `BasketScheduleState`) as they stand, only that one switch changed. Always pass all nine, so no value is left to what the stack held before. If the healthchecks.io check is paused, the first scheduled check's ping normally takes it out of pause (step 7); see on healthchecks.io that it did. The next morning, read the manifests and the check record, and see the 11:48 ping on healthchecks.io. To turn them off, deploy again with `'ScheduleState=DISABLED'`, the other two switches as they stand (`'BasketScheduleState=ENABLED'` while the basket is live, `'PollScheduleState=ENABLED'` while the polls are), only that one switch changed.

   **Turn the polls on**, on the owner's go, once the manual polls (step 6) and the manual check that asks for the update day (step 7) read well: the same `sam deploy` command with all nine parameters and `'PollScheduleState=ENABLED'`, the others as they stand (`'ScheduleState=ENABLED'` while the collector is live). The first scheduled check after it judges the day before, and emails `no poll run read …` for each chain that day had no poll of: so turn the polls on after the 11:48 check and before 12:20: switched on later, Rami Levy's first poll that day takes everything published since its 09:33 retry run, not two hours' files, and may stop on time. To turn them off, deploy again with `'PollScheduleState=DISABLED'`: the polls stop, and so do the check's judgement of the update day and its emails, while the morning's runs and the check go on. The morning's switch does not stop the polls: they follow `PollScheduleState` alone, and with `ScheduleState` off no scheduled check judges their day.

## A stopped chain

The commands here use `FN` and `BUCKET` as set in step 5 of Deploy. A block stops the chain: its state file says `stopped`, with when and why, and every later run of that chain does nothing (its manifest says `"blocked": "stopped earlier"`). The next check emails once; later checks stay quiet about it until you clear it. When a poll run stopped it, that run emails at once instead ("Reading an update day", below), and the check does not email it again. Read why in the email, the manifest's `blocked`, or the state file:

```bash
aws s3 cp "s3://$BUCKET/state/ramilevy.json" - --profile flights-sam --region il-central-1
```

Find out why the portal refused before anything else. Never switch to a browser User-Agent, another IP, a proxy or any other way around a block. One refusal is not a block: a 403 from Shufersal's file host (`pricesprodpublic.blob.core.windows.net`) once a link has expired makes the collector read the listing again for a fresh link, once.

Not every stop is a refusal. The NCR portal (Rami Levy, Osher Ad, Yochananof) sends a visitor without a session to its login page, so a session that ends in the middle of a run should answer the next download with that page. The collector reads it as "HTML where a file belongs" and stops the chain: the reason reads `<file name>: HTML where a file belongs`, and the same run's manifest shows files stored before it. Read the reason and the manifest; when they point to an ended session and not to a refusal, unblock the chain (below).

When the cause is sorted out, clear the latch (here Rami Levy; use the stopped chain's name from the table above):

```bash
aws lambda invoke --function-name "$FN" --payload '{"mode": "unblock", "chain": "ramilevy"}' --cli-binary-format raw-in-base64-out /tmp/il-grocery-unblock.json --profile flights-sam --region il-central-1
```

`/tmp/il-grocery-unblock.json` shows the state it cleared (`was`). The chain's next scheduled run collects again; or start one by hand as in step 6; with the polls on, start an NCR chain's or Carrefour's at least 15 minutes after that host's last scheduled poll started and at least 15 minutes before its next (ruling R30).

## Reading an update day

The update files a chain published through a day are judged the next morning: while `PollScheduleState` is on (or when a manual check asks, step 7), each morning's 11:48 check also judges the day before for the chains that poll (today Rami Levy, Osher Ad, Carrefour and Yochananof), from every manifest of that day, polls and morning runs alike, and the files stored that day. It writes the result into that morning's check record under `update_day`, so a reader of a day's update files opens the next day's record (step 8 lists and prints them). `update_day` holds `day`, the day judged, and `chains`, one section per chain:

- `polls`: each poll run of the day, with its `run_id`, `kinds`, its counts of names `listed`, `stored`, `failed` and `not_attempted`, and its `error` and `blocked`. A poll stopped on time (`"error": "stopped: under 90 s left"`) or whose listing failed once is not a fault: a later poll that day takes the rest.
- `passes`: for each update kind, the day's readings of its list. `complete` names the runs that read each complete one; for these four chains, whose runs record no listing pages, each poll that ended with no error and was not blocked reads the list on its own. `open` holds the runs after the last complete reading when the day's last polls did not end clean (null when they did); for Shufersal it will also say what of the list they did not read. `out_of_order` is for Shufersal's passes, the runs of a pass a page out of order ended; it stays empty for these four.
- `missing`: the names a poll tried and did not store that are still not stored, leaving out any a morning run listed (those were judged by the day's own check).
- `not_tried`: for each update kind, the names, sorted, that a poll listed and never tried because it stopped on time, still not stored, not in `missing` and not listed by a morning run (those were judged by the day's own check). For these four chains they are emailed, in the `missing` sentence below: a poll that stops on time lists every name of the day it did not reach, so a name here is a file of the day that no run stored. For a kind with listing pages (Shufersal's, once it polls) they are only counted here, not emailed, until its polls are designed. They are what the 90 s time rule cost that day, mostly from the day's last poll, whose leftovers no later poll that day takes.
- `by_hour`: for each update kind, the day's stored files counted by the hour in their names (`"00"` to `"23"`, and `"unknown"` for a name whose hour cannot be read), the morning's files included: each chain's publishing rhythm.
- `failed`: the update kinds no poll read in full that day (a day with no poll at all included), or null. It stays null when a poll of the day was blocked: the stopped alert covers that day.

Two things email, in the same email as the morning's alerts:

- `<chain>: <n> update files listed on <day> and not stored (<k> tried and failed, <m> never tried: a poll stopped on time before reaching them): <names>.` (`update file` for one, `reaching it` for one never tried; a part with none is left out; the names of both parts come sorted together.) Tried and failed: read why in the manifests of the day's polls (each name's reason is in its run's `failed`); a single one can be a passing fault, and the same reason day after day points to a portal change or a bug. Never tried: a poll stopped on time before reaching them and no later poll stored them, usually because it was the chain's last poll of the day; read that poll's `REPORT` duration against the estimates in step 6. Either way the day's files are lost: nothing re-fetches a past day (a run takes only the day it runs on), so the collector does not try these names again.
- `<chain>: no poll run read the Price and Promo lists in full on <day>.` (or `the Price list`, `the Promo list`). No poll that day ended with no error: read `polls` for each run's `error`, and the log group around the polls' times. With `polls` empty, none ran that day: the switch went on after that day's polls, or the schedules did not fire, and the log group shows no poll that afternoon or evening. A whole day of failed polls is a portal change, a bad deploy or a lost schedule, and nothing else reports it: the healthchecks.io ping covers only the check.

A poll run that stops a chain (a block, as in "A stopped chain") emails at once, with the subject `il-grocery-prices <day>: <chain> stopped by a poll run` and, in the body, the stopped alert and the run's manifest: after an afternoon or evening poll the next check is the next morning's, after that morning's runs have done nothing. The chain is marked alerted once the email has gone, so the check does not send it again; if the email failed, the next check sends it. Clear the chain as in "A stopped chain" once the cause is sorted out, the same evening if it can be, so the next morning's runs collect.

For the first weeks (rollout steps 2 to 4, [update-files.md](update-files.md), section 7), read beside each `update_day`:

- The bytes a chain stored in a day (`--summarize` prints the total after the list, the morning's full files included); the design estimates the update files at 80 to 550 MB a day in all, almost all of it Rami Levy's `Price` files:

  ```bash
  aws s3 ls "s3://$BUCKET/raw/chain=ramilevy/date=YYYY-MM-DD/" --recursive --summarize --profile flights-sam --region il-central-1
  ```

- The polls' durations, from the last day's `REPORT` lines (each run's summary line, naming its mode and chain, comes before its `REPORT` line in the full log, step 6), against the estimates in step 6:

  ```bash
  aws logs tail /il-grocery-prices/collector --since 24h --profile flights-sam --region il-central-1 | grep REPORT
  ```

- `by_hour`, for each chain's afternoon and evening rhythm; `not_tried`, which should be empty: a name in it is a file lost, and emailed; and `other_days` in the morning's main runs, how much of the day before the next morning still sees: the case for a sweep of the day before, which does not exist yet.

Every command here only reads.

## Carrefour from il-central-1

Carrefour is reported to refuse visitors from outside Israel; whether AWS's Tel Aviv addresses get through is unknown until its first run from the stack. If that run is blocked, drop Carrefour (below) and record it in the project notes. Never another route to it.

## Dropping a chain

1. Delete the chain's schedules from `template.yaml`: its main and retry events (Shufersal has five main and three retry) and its poll events (`Poll<Chain><HHMM>`: seven for Rami Levy, Yochananof and Osher Ad, six for Carrefour, none yet for Shufersal).
2. Delete its entry in `CHAINS` in `src/collector/chains.py`; its `polled` goes with it (`tests/test_template.py` refuses poll schedules for a chain without `polled`, and `polled` for a chain without poll schedules).
3. Bring the tests in line: its rows in the `SCHEDULES` table in `tests/test_template.py`, its rows in this file's timetables ("What runs when"), its manual-run and manual-poll lines (step 6), its cases in `tests/test_chains.py`, and any mutation in `scripts/mutation_check.py` that quotes it. Run the tests, cfn-lint and the mutation check (below).
4. Commit, then deploy with step 3's command and all nine parameters, the three switches (`ScheduleState`, `PollScheduleState`, `BasketScheduleState`) as they stand, not step 3's `DISABLED`.

Its stored files stay, locked; so does its state file. The check stops looking at it, since it checks only the chains in `CHAINS`, and judges the update day only of chains whose `polled` is set.

## Develop

From the repo root:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest --cov=collector --cov-fail-under=95
cfn-lint --regions il-central-1 -- template.yaml site-template.yaml
python scripts/mutation_check.py
```

The mutation check breaks each rule in turn and expects a test to fail. It edits source files in place while it runs, so run nothing else from the checkout meanwhile. CI runs all three on every push. `tests/test_template.py` pins the deploy settings safety depends on (the bucket's lock and privacy, the role's permissions, the schedules, the parameters) and checks this file's commands against them, `tests/test_basket_template.py` the basket function's: cfn-lint lets a misspelled schedule property through.

## Cost

Estimates from [collector.md](collector.md), "Cost", and, for the update files through the day, from [update-files.md](update-files.md), section 6, with the build plan's check of its arithmetic ([update-files-plan.md](update-files-plan.md), Task 6, "Cost"; where the check differs, both are given). The update files' figures are estimates until rollout step 4 measures them (MB a day per chain, GB-seconds a month from CloudWatch: [update-files.md](update-files.md), section 7); the measured figures replace them here then.

- **Volume:** Shufersal's full files were about 162 MB on 2026-10-31 (measured from its listing); the other four chains have fewer stores. About 250 to 300 MB a day, so 8 to 9 GB a month. The update files add about 80 to 550 MB a day, almost all of it Rami Levy's afternoon `Price` files (by hour, a mean of 22 KB at 07:00 and 357 KB at 14:00).
- **S3 storage** at $0.025 per GB-month (il-central-1): about $0.25 the first month, about $2.70 a month after a year. Nothing is deleted (every file is locked for ten years), so storage grows every month; moves to colder storage wait until the bucket passes about 50 GB. The update files add 2.4 to 16.5 GB a month: after a year 29 to 198 GB, $0.73 to $4.95 a month; after ten years 290 to 1,980 GB, $7.30 to $49.50 a month; about $440 to $2,970 paid over the ten years (the check: about $430 to $440 at the low bound and $2,950 to $3,000 at the high one).
- **S3 writes:** about 2,000 a day at $0.0055 per 1,000: about $0.35 a month. The polls add about 3,000 to 4,200 a day: $0.50 to $0.70 a month.
- **Lambda:** the morning's runs are a few invocations of up to 15 minutes a day, inside the monthly free tier. The 27 polls are expected to take about 2,450 GB-seconds a day at 512 MB, about 74,000 a month: Rami Levy's seven at about 400 s each, 1,400 a day, and Yochananof's, Osher Ad's and Carrefour's 20 at about 150, 100 and 60 s, 1,050 a day (the check: 1,055); Shufersal's twelve pass runs, at rollout step 3, about 3,780 a day more (6,230 a day in all, about 187,000 a month). With the collector's mornings (about 60,000 to 100,000 a month), the basket (about 19,000, up to 95,000) and flights-archive's flight-board collector in the same account (a few tens of thousands, its durations not read), the account's expected total is about 290,000 to 420,000 GB-seconds a month against the free tier's 400,000: $0 to $0.35 a month beyond it (the check: $0.33), at $0.0000166667 a GB-second (US East's x86 rate; the arm64 and il-central-1 rates not checked). If every poll, Shufersal's included, ran its full 900 s, about $5 to $6 more in that month (the check: a total of $3.80 to $6.00 beyond the free tier in that month). The polls add 27 invocations a day (39 with Shufersal's, about 1,200 a month), inside the free million. The worst case, all 43 collecting runs (the morning's 16 and the 27 polls) and the check running the full 15 minutes at 512 MB, is 19,800 GB-seconds a day, about 594,000 a month: about 194,000 over the free tier's 400,000, about $3.23 a month at the US East x86 rate above ($0.0000166667 a GB-second), with the basket's and the flight-board collector's time on top. A timed-out Shufersal page's further tries (ruling R38) use time a run already has, so that worst case does not move; the most they can add is the time the runs leave unused: on 2026-11-06 the six Shufersal runs that ended on an error left 3,691 s unused, about 1,850 GB-seconds at 512 MB, about 55,000 a month, inside the free tier's 400,000.
- **Concurrency:** the 27 polls never overlap one another (each starts at least 15 minutes after the one before), and none is in flight while the basket's extractions run. The design set that spacing for a Lambda quota of 5 concurrent runs in il-central-1, recorded on 2026-10-29; the account's quota read 400 on 2026-11-07 (`aws lambda get-account-settings`: `ConcurrentExecutions` 400; Service Quotas `L-B99A9384`, "Concurrent executions", 400.0), so the spacing is kept as approved, not as a limit the polls come near.
- **S3 reads:** each Shufersal run lists the day's Shufersal manifests once and reads each earlier one: on the eight scheduled Shufersal runs, 8 listings and 28 reads a day, about 1,100 requests a month, under $0.01 a month if they cost no more than the writes above. The polls' listings of the day's stored files and Shufersal's manifest reads add about 400 a day: under $0.07 a month at the write rate, an upper bound.
- **Total:** about $1 to $3 a month in the first year. The update files add about $1 to $3 a month averaged over the first year (the check: about $0.90 to $3.70), $1.20 to $6 in its last month, and storage alone $7 to $50 a month in year ten. The account's $5 monthly budget alarm ([headline-basket.md](headline-basket.md), "Cost") would sound within the first year at the high bound, which is why rollout step 4's measurement is a gate.

## The headline basket, by hand

Step one of the headline basket (`docs/headline-basket.md`, "The pipeline"): one day's page, built on the Mac from the archive and uploaded by hand. The site has a stack of its own, `il-grocery-prices-site` (`site-template.yaml`: a private S3 bucket that only one CloudFront distribution reads), separate from the collector's so a site change never touches the archive. It costs under $0.05 a month (`docs/headline-basket.md`, "Cost"). Two steps wait on the owner's go: the stack's deploy and the first upload ("The two gates", below). Once step two builds the page every morning ("The headline basket, every morning", below), the hand build is for revising a day and for a day the morning missed.

### Five steps

1. **Sync the day** (read-only on AWS):

   ```bash
   sh scripts/sync.sh YYYY-MM-DD
   ```

   After the identity check it copies the day's full price files and store lists into `data/raw/`, the day's manifests into `data/manifests/`, and, once the site's stack exists, every published day file into `site/days/`, the bucket's copy replacing a local file unless the two have the same size and the same modification time (`--exact-timestamps`; without it the sync keeps a same-sized local file that is no newer than the bucket's). Before the stack exists it says so in one line and goes on; any other failure to read the stack stops it. The published day files are what the build compares with ("Revising a day", below): a build that cannot see a day's published file writes the day as new. So once a day is published, build it only into a `site/` that step 1 filled; step 5 refuses to upload a day file that would replace a published one it does not revise.

2. **Build:**

   ```bash
   PYTHONPATH=src .venv/bin/python -m basket.build --day YYYY-MM-DD --collected-by 11:48
   ```

   Extract, basket and page in one command. Each chain's table is extracted from the raw files unless it is already under `data/tables/prices/chain=<slug>/date=<day>/` with its `report.json`; the basket (`src/basket/baskets/v1.json`) is priced; the run's private record is written once to `data/basket/date=<day>/basket-<run id>.json`; the pages go to `site/` (`index.html`, `method.html`, `days/<day>.json` and the marker `.basket-site`). `--collected-by` sets the time on the credit line: "the files of 2 November 2026, collected by 10:45 Israel time" (that day's check time). Without it the build takes the clock as it runs, which on a hand build hours after the morning says nothing about the files, so the hand build passes the day's check time, 11:48: the collector's last schedule, which starts after the last retry run can have finished ("What runs when", above). On 2026-11-02 the last run started at 10:15 and stored nothing, and the last run that stored a file started at 10:03 (the day's 16 manifests). A later build of the same day leaves this time out of its comparison (B12), so it never makes a day "changed". `index.html` shows the day that was built last (and both pages its credit line), so when several days are built, build the latest last.

3. **Check:**

   ```bash
   PYTHONPATH=src .venv/bin/python -m basket.check site
   ```

   The same check `scripts/publish.sh` runs before it uploads: no never-phrase and no "we", "our" or "us" on any page; the credit line, "Not shopping advice." and `noindex` on every page, and no script; every always-phrase on the index page, and "Revised on" there on a revised day and only then; the marker. Exit 0 when clean; 1 with problems, one a line naming the file and the rule; 2 when there is no page.

4. **Review** `site/index.html` and `site/method.html` in a browser (`open site/index.html site/method.html`): the headline, the bars, the item table and the notes against the printout, and the method page.

5. **Publish,** on the owner's go only, given after the owner has checked the "current as of" date on Nevo's page against `docs/terms.md` (a date past 19-07-2026 means the clause is read again first):

   ```bash
   sh scripts/publish.sh
   ```

   It writes to AWS, and uploads nothing unless every check passes, in this order: the identity check; `site/` carries the marker `.basket-site`, and its full path holds no `[`, `]`, `?` or `*` (the upload's filters would misread them); the check of step 3; the bucket and the distribution from the stack's outputs, the bucket's name starting `il-grocery-prices-site-sitebucket-` (so never the archive bucket) and the distribution's ID not empty; the published-day guard: the bucket's `days/` copied (a read) into a temporary folder and compared with `site/days/` by `basket.guard`, which refuses a day file that differs from its published copy unless it is a revision of it (`revised` set and a longer `revisions` list), naming the day (a day new to the bucket passes, and so does an empty bucket). Then two uploads, each an allowlist with its content type set: `*.html` as `text/html; charset=utf-8` and `*.json` as `application/json; charset=utf-8`, both with `Cache-Control: max-age=300`; then one CloudFront invalidation of `/*`; then it prints the site's address. Nothing else in `site/` (the marker, a `.DS_Store`) is uploaded. The page upload runs with `--delete`, so a page the build no longer writes leaves the site; the day-file upload never deletes: `days/` is append-only, and each day's file holds its revision reasons, which exist nowhere else once published. The site bucket keeps every version of a file (versioning, `site-template.yaml`), so a file replaced or deleted all the same is still there as an earlier version.

### What the build prints

One line per chain, in slug order: `extracted in N.N s` or `table kept`, and its rows. Then the page's two headline lines, word for word. Then what happened to the day file: `published: site/days/<day>.json` for a day not yet on the site; `unchanged: site/days/<day>.json already holds these numbers and is left as it is` for a day published with the same numbers (the pages are then rendered from the published file, its "collected by" time included); or `revised: site/days/<day>.json, the earlier totals kept under revisions`. Last, the record's path. A bad basket file, a chain with no store list on or before the day, or a published day with other numbers and no `--revise` stops the build with a message and exit 1.

### Revising a day

A published day comes back into `site/days/` with the sync, and the build compares its numbers with the published ones (B12), leaving out the run id, the code fingerprint, the build time and the "collected by" time. Equal: `unchanged`, and the day file stays as it is. Different: the build stops, names what differs, and asks for a reason. To republish, build again with a one-line reason:

```bash
PYTHONPATH=src .venv/bin/python -m basket.build --day YYYY-MM-DD --collected-by 11:48 --revise "<one-line reason>"
```

The day file then keeps the earlier run at the end of `revisions` (its run id, code fingerprint, build time, totals and its own `revised`; the first entry is the day as first published, its `revised` null), `revised` holds the reason and the Israel date, and the index page says "Revised on <date>: <reason>. First published: <the earlier totals>." A day revised again also names each earlier revision, newest first: "Revised on <date>: <reason>. Earlier: on <date>: <reason>. First published: …". A blank reason, or one with a line break, is refused. Every build writes its private record, a refused one included. Then check, review and publish as above. A scheduled run (step two, "The headline basket, every morning", below) never revises; only a hand build given a reason does.

`--rebuild` extracts every chain's table again from the raw files, for instance after a parser fix; without it a table already there with its `report.json` is kept, and its counts come from the report. If the new tables change the day's numbers, the day needs `--revise` as above.

### Measured on 2026-11-02

On this Mac, from `docs/headline-basket-plan.md`, "Deviations" (Task 4 and Task 13). The sync brought 356 MB of raw files and 16 manifests. Extraction, as `basket.extract` printed it, with peak memory from `/usr/bin/time -l`:

| Chain | Seconds | Rows | Parquet | Peak memory |
|---|---|---|---|---|
| Shufersal | 93.9 | 2,322,336 | 41.2 MB | 937 MB |
| Rami Levy | 38.8 | 993,278 | 23.1 MB | 673 MB |
| Osher Ad | 5.9 | 151,604 | 3.3 MB | 234 MB |
| Carrefour | 46.6 | 1,196,548 | 21.0 MB | 733 MB |
| Yochananof | 18.2 | 476,502 | 6.8 MB | 473 MB |
| Five chains | 203.4 | 5,140,268 | 95.4 MB | |

A build with every table kept took 1.2 s, and a second build of the day 0.9 s (`unchanged`); with `--rebuild`, 205 s in all and 930 MB peak resident memory, also `unchanged`. The day's totals for basket v1's 32 items, lowest first: Rami Levy ₪401.40 (96 of its 98 included stores with a file), Osher Ad ₪402.50 (24 of 24), Yochananof ₪408.92 (47 of 51), Shufersal ₪470.82 (317 of 320: store 779, listed in sub-chain 7 but Be by its file's name, has no file that counts; 318 before the final review fixes, the totals the same), Carrefour ₪487.42 (146 of 146); every chain in the ranking and all 32 items counted. The headline lines:

- "Lowest listed total today: Rami Levy, ₪401.40."
- "Highest: Carrefour, ₪487.42, 21% more. 32 everyday items, listed shelf prices before promotions, from the chains' price files of Monday 2 November 2026."

### The two gates

1. **The stack,** once, on the owner's go. The identity must show account `137953273942` and a user ARN ending in `user/doron-admin`; then the deploy, as flights-archive deploys its site (no SAM: the template holds no code); then the outputs:

   ```bash
   aws sts get-caller-identity --profile flights-sam --region il-central-1
   aws cloudformation deploy --template-file site-template.yaml --stack-name il-grocery-prices-site --profile flights-sam --region il-central-1
   aws cloudformation describe-stacks --stack-name il-grocery-prices-site --query "Stacks[0].Outputs" --output table --profile flights-sam --region il-central-1
   ```

   The outputs name the bucket (`SiteBucketName`), the distribution (`SiteDistributionId`) and the address (`SiteDomainName`); both scripts read them from the stack. The bucket is created with versioning on, and AWS asks for 15 minutes after versioning is first enabled before objects are written (the `VersioningConfiguration` description in the AWS::S3::Bucket resource schema, as cfn-lint bundles it), so the first upload waits that long after the deploy.

2. **The first upload,** on the owner's go: the owner reviews `site/index.html` and `site/method.html` on the Mac and checks the date on Nevo's page; then `sh scripts/publish.sh` (step 5). Open the printed address, and fetch `days/2026-11-02.json` from it.

## The headline basket, every morning

Step two of the headline basket (`docs/headline-basket.md`, "The pipeline"): a second Lambda function in the collector's stack, `BasketFunction`, runs the hand build's code every morning over what the collector stored and publishes the day's page. Its six schedules have a switch of their own, `BasketScheduleState`, apart from the collector's `ScheduleState`, and they deploy off. It costs about $0.10 to $0.90 a month in year one on top of the collector, about $3.50 at worst (`docs/headline-basket.md`, "Cost").

### What runs when

| Israel time | Run | Event |
|---|---|---|
| 12:03 | Shufersal's table of the day | `{"mode": "extract", "chain": "shufersal"}` |
| 12:03 | Rami Levy's table of the day | `{"mode": "extract", "chain": "ramilevy"}` |
| 12:03 | Osher Ad's table of the day | `{"mode": "extract", "chain": "osherad"}` |
| 12:03 | Carrefour's table of the day | `{"mode": "extract", "chain": "carrefour"}` |
| 12:03 | Yochananof's table of the day | `{"mode": "extract", "chain": "yochananof"}` |
| 12:33 | The basket run: the day's record, pages and day file | `{"mode": "basket", "collected_by": "12:03"}` |

An extraction fetches its chain's full price files of the day from the archive bucket, runs `basket.extract` over them as the hand build does, and puts the chain's table back. The five read S3 only and touch no portal, so they start together, 15 minutes after the collector's check: Lambda's longest run, so the check can have finished. The basket run starts 30 minutes after them, 15 minutes after the last extraction can have finished, for its table's put and the schedulers' lag. It fetches the five tables, the store lists, the manifests and the site's published copy of the day; runs `basket.build` as the hand build does, never with a reason to revise; checks the built site with `basket.check` and the published-day guard (`basket.guard`), as `scripts/publish.sh` does; and uploads. Its `collected_by` is the extraction's time, fixed in the event (B11), so the record does not depend on when the run starts.

Both modes first look for a key under `checks/date=<day>/` (a list of the archive bucket; no check record is read) and refuse the day without one (`MorningNotChecked`). The check is the morning's last run, so its record shows that every chain's runs are over, and a late or failed check stops the build rather than letting it work on a partial morning. A scheduled run is for the Israel date it starts on; a manual run names its day (`"day": "YYYY-MM-DD"`).

The basket run puts the two pages only when its day is the site's latest or the site has none, so a run for an earlier day writes that day's file and record but leaves the front page to the site's latest day. It puts the day file only when the build wrote it: a day already published with the same numbers (`unchanged`, B12) keeps its published file, and a day published with other numbers stops the run (`RevisionNeeded`), since a scheduled run never revises. One CloudFront invalidation of `/*` follows any upload. Neither the schedules nor Lambda retry a failed invocation; a rerun is by hand ("The manual runs", below).

### Where things land

In the archive bucket, beside the collector's keys:

- `tables/prices/chain=<slug>/date=<day>/prices.parquet` and `report.json`: a chain's table of the day and its counts, plain and overwritable; a later extraction of the same day replaces them.
- `basket/date=<day>/basket-<run id>.json`: the basket run's private record (B10), written once and locked for ten years (governance mode), as a manifest is. Every build writes one, a refused one included (`RevisionNeeded`, `SiteCheckFailed`); a run that stops before the build has priced the day (`MorningNotChecked`, `MissingTable`, `NoStoreList`) writes none.

In the site bucket: `index.html` and `method.html` (only for the site's latest day) and `days/<day>.json` (only when the build wrote it), with the content types and the `Cache-Control: max-age=300` that `scripts/publish.sh` sets. Nothing is deleted in either bucket.

Logs go to the log group `/il-grocery-prices/basket`, kept 30 days. A run ends with one JSON line, its summary (a failed run logs none), then Lambda's `REPORT` line with the duration and `Max Memory Used`. An extraction's summary: `mode`, `chain`, `day`, `run_id`, `files` (the price files in the table, each store's latest), `skipped` (the day's files passed over), `stores`, `rows`, `unreadable_prices` (the rows whose price could not be read, kept with none), `seconds` (the extraction alone, the fetch and the put left out) and `keys`. The basket run's: `mode`, `day`, `run_id`, `headline` (the page's two lines), `unchanged`, `pages` (whether the pages went up), `uploaded` (the keys put in the site bucket), `invalidation` (its id, or null) and `record` (the record's key).

### Sizing

The function has 2,048 MB of memory, 2,048 MB of `/tmp` and 900 s. DuckDB's temp folder is `/tmp/duckdb` and its memory limit 1,200 MB, both set in the function's environment (`DUCKDB_TEMP_DIRECTORY`, `DUCKDB_MEMORY_LIMIT`). `/tmp` holds one chain's price files of the day, the temporary CSV its rows go through, its table and DuckDB's spill folder. The first three are in the run's work folder (`/tmp/basket-<random>`), which the run removes when it ends; a run Lambda kills at its timeout cannot, and Lambda keeps `/tmp` between invocations of one execution environment (https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html, read 2026-11-03), so each run, before it makes its own, removes any `basket-*` folder an earlier run left, and DuckDB's temp folder when it holds anything (spill files a killed run left; the basket code makes the folder again when it next connects to DuckDB), and logs how many of each when there were any. DuckDB's folder is swept only when it is a folder of its own under `/tmp`: a link, `/tmp` itself or a folder elsewhere is left as it is, with a warning. A removal that fails is logged as a warning (`could not remove <path>: <error>`) and the run goes on. On the Mac, Shufersal's extraction, the largest, took 93.9 s and 937 MB at its peak ("Measured on 2026-11-02", above), and its temporary CSV comes to about 480 MB at about 200 bytes a row, about 650 MB of `/tmp` with the day's raw files and the table (`docs/headline-basket-step-two-plan.md`, "Deviations", the first entry).

In Lambda, measured on the first run (2026-11-03, the 2026-11-02 day, by hand): every chain's `rows` equal to the Mac's, and about 1.1 times the Mac's seconds, not the 3 the plan estimated. `Max Memory Used` read 1,121 MB in Shufersal's run, the first in its execution environment, and the same 1,121 MB in every run after it, the basket run included, which all ran in that warm environment: the figure is the environment's peak, so the smaller chains' own peaks are not known beyond being at most that. Shufersal's init, the DuckDB import included, took 0.47 s.

| Run | `rows` | `seconds` (the basket run: `Duration`) | `Max Memory Used` |
|---|---|---|---|
| Shufersal's extraction | 2,322,336 | 102.1 (`Duration` 122.9) | 1,121 MB |
| Rami Levy's extraction | 993,278 | 44.7 (54.3) | 1,121 MB, the same warm environment |
| Osher Ad's extraction | 151,604 | 6.9 (8.3) | same |
| Carrefour's extraction | 1,196,548 | 54.0 (64.0) | same |
| Yochananof's extraction | 476,502 | 20.9 (23.5) | same |
| The basket run | | 6.0 | same |

### Deploying step two

1. **A second healthchecks.io check,** period 1 day and grace 2 hours, as in step 2 of Deploy, for the basket run alone; copy its ping URL. The basket run pings it: `/start` as it begins, the plain URL with its summary when it succeeds, and `/fail` with the error's name and text (its first 100,000 bytes, a character the cut would split dropped) when anything fails, `MorningNotChecked` included; an event refused as bad sends no ping at all (the `/start` and `/fail` endpoints and the 100 kB limit on a ping's body: https://healthchecks.io/docs/http_api/, read 2026-11-03). A ping that fails is logged as a warning naming its kind (start, success or fail) and never stops the run. The extractions never ping: one that fails shows in the basket run as a missing table. There is no CloudWatch alarm for the basket: a morning with no page, or a failed one, reaches you through this check.

2. **Build and deploy with the basket's schedules off,** on the owner's go, from a clean, committed tree as in step 3 of Deploy. The function's zip is `src/` alone, so the record's `code_sha` is the fingerprint of `src/` that the Mac computes at the deployed commit:

   ```bash
   PYTHONPATH=src .venv/bin/python -c 'from basket.record import code_fingerprint; print(code_fingerprint())'
   ```

   `sam build` now also builds the DuckDB layer from `layer/Makefile` (SAM's makefile build: the target `build-DuckDbLayer`, its output in `$(ARTIFACTS_DIR)`; https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/building-layers.html, read 2026-11-03). It downloads the hash-pinned `duckdb==1.5.6` wheel for Lambda's arm64 Linux from PyPI, so the build needs the network: 18.6 MB, 53 MB unpacked, against Lambda's limit of 250 MB unzipped (https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html). Then deploy with step 3's `sam deploy` command, all nine parameters: the collector's five as they stand (`'ScheduleState=ENABLED'` while the collector is live, `PollScheduleState` as it is), the site stack's bucket and distribution, the second check's URL as `BasketHealthcheckUrl`, and `'BasketScheduleState=DISABLED'`. Pass all nine on every deploy, so no value is left to what the stack held before. In the change set, what is new is the basket's: its function, layer, log group and role, and its six schedules with what SAM adds for them; a change to one of the collector's resources should be one committed since its last deploy.

3. **The function's name,** from the stack's outputs (and `BUCKET` as in step 5 of Deploy):

   ```bash
   BASKET_FN=$(aws cloudformation describe-stacks --stack-name il-grocery-prices --query "Stacks[0].Outputs[?OutputKey=='BasketFunctionName'].OutputValue" --output text --profile flights-sam --region il-central-1)
   ```

### The manual runs

One manual run per step, on the owner's go (each writes to AWS), on a day already published by hand that is the site's latest, so the answer is known in advance: the day's numbers unchanged. The site's latest day is the last of its day files:

```bash
SITE_BUCKET=$(aws cloudformation describe-stacks --stack-name il-grocery-prices-site --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text --profile flights-sam --region il-central-1)
aws s3 ls "s3://$SITE_BUCKET/days/" --profile flights-sam --region il-central-1
```

The commands below name 2026-11-02, the first day published by hand; put the site's latest day in its place.

1. **The five extractions,** each the scheduled event with the day added. Start each asynchronously (`--invocation-type Event`), the way the schedules do: Shufersal's took 93.9 s on the Mac, and a plain invoke the CLI gives up on after 60 seconds is sent again (step 6 of Deploy), starting a second extraction of the same chain. Start them one at a time and let each finish before the next, which keeps the logs readable:

   ```bash
   aws lambda invoke --function-name "$BASKET_FN" --invocation-type Event --payload '{"mode": "extract", "chain": "shufersal", "day": "2026-11-02"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$BASKET_FN" --invocation-type Event --payload '{"mode": "extract", "chain": "ramilevy", "day": "2026-11-02"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$BASKET_FN" --invocation-type Event --payload '{"mode": "extract", "chain": "osherad", "day": "2026-11-02"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$BASKET_FN" --invocation-type Event --payload '{"mode": "extract", "chain": "carrefour", "day": "2026-11-02"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   aws lambda invoke --function-name "$BASKET_FN" --invocation-type Event --payload '{"mode": "extract", "chain": "yochananof", "day": "2026-11-02"}' --cli-binary-format raw-in-base64-out /dev/null --profile flights-sam --region il-central-1
   ```

   Watch each in the logs:

   ```bash
   aws logs tail /il-grocery-prices/basket --follow --since 10m --profile flights-sam --region il-central-1
   ```

   Read its summary's `rows` (for 2026-11-02, against the Mac's in "Measured on 2026-11-02", above) and `seconds`, and the `REPORT` line's `Max Memory Used` against the function's 2,048 MB; note them in "Sizing", above. A run with no summary line failed: read the lines before its `REPORT` line.

2. **The basket run,** once the five have finished: the scheduled event with the day added, its `collected_by` the extraction's time as the schedule sends it. A plain invoke, so the answer file holds the run's summary; `--cli-read-timeout 900` keeps the CLI waiting rather than sending it again, which would start a second run of the day:

   ```bash
   aws lambda invoke --function-name "$BASKET_FN" --payload '{"mode": "basket", "day": "2026-11-02", "collected_by": "12:03"}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-basket.json --profile flights-sam --region il-central-1
   ```

   On a day already published by hand that is the site's latest, the expected answer in `/tmp/il-grocery-basket.json` is `"unchanged": true` and `"pages": true`: the numbers equal the published ones (B12 leaves the run id, the code fingerprint, the build time and the "collected by" time out of the comparison), so the day file stays as published and only the two pages go up, rendered from it, its "collected by" time included; `uploaded` names the two pages and `invalidation` an id. Then check as in "The two gates": open the site's address and see the day's page as before. Read the record and its lock:

   ```bash
   aws s3 ls "s3://$BUCKET/basket/date=2026-11-02/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/basket/date=2026-11-02/basket-<run id>.json" - --profile flights-sam --region il-central-1
   aws s3api head-object --bucket "$BUCKET" --key "basket/date=2026-11-02/basket-<run id>.json" --query "[ObjectLockMode, ObjectLockRetainUntilDate]" --profile flights-sam --region il-central-1
   ```

   The record's `code_sha` is the deployed commit's (step 2 of "Deploying step two"), and the lock reads `GOVERNANCE` with a date ten years on. On healthchecks.io the second check shows the run's pings. From that ping on it expects the next within a day and two hours; if the schedules will not be on by then, pause it as step 7 of Deploy describes. Any other answer is a failure: read it as below ("What a /fail email means").

### Turning it on

On the owner's go: step 3's `sam deploy` command with all nine parameters again and `'BasketScheduleState=ENABLED'`, the other two switches as they stand (`'ScheduleState=ENABLED'` while the collector is live, `PollScheduleState` as it is), only that one switch changed. The next morning, after the basket run's time, check:

- the log group `/il-grocery-prices/basket`: six summary lines, the five extractions' and the basket run's;
- the record under `basket/date=<day>/` (`aws s3 ls` as above);
- the success ping on the second healthchecks.io check;
- the page's date on the site: the day's.

To turn the basket off, deploy again with `'BasketScheduleState=DISABLED'`, the other two switches as they stand (`'ScheduleState=ENABLED'` while the collector is live, `'PollScheduleState=ENABLED'` while the polls are), only that one switch changed; the collector's schedules follow `ScheduleState` and, for the polls, `PollScheduleState`. The hand build ("The headline basket, by hand", above) stays for revising a day and for a day the morning missed.

### What a /fail email means

The second check emails when the basket run pings `/fail`, or when no ping arrives in time. The ping's body is the error's name and text; then read the log group `/il-grocery-prices/basket` around the basket run's time.

- `MorningNotChecked`: the collector's check has not written its record for the day: it has not run, or it failed. Read `/il-grocery-prices/collector` around the check's time, and the collector's own healthchecks.io check. Once the check has written its record, run the day's five extractions and its basket run by hand ("The manual runs", above): the extractions refused the day too.
- `MissingTable`: it names the chain whose table of the day is missing, and the table's key: that chain's extraction did not run or did not finish. Read that extraction in the log group around the extraction's time, then run it and the basket run again by hand.
- `NoStoreList`: it names the chain that has no store list on the day or any of the 13 days before it. The build stopped before it wrote the record, so there is none, and nothing went up. Look under the chain's `raw/chain=<slug>/` in the archive bucket for a `Stores` file of those days, and read `/il-grocery-prices/collector` for the chain's runs. Once the collector has stored a store list, run the basket run again by hand.
- `RevisionNeeded`: the day is published with other numbers, and the error names what differs: a code or rule change moved a published number. The run published nothing and kept its record. When the new numbers are right, revise the day with a hand build given `--revise` and a one-line reason ("Revising a day", above), then check, review and publish as there.
- `SiteCheckFailed`: the built page failed the word check (`basket.check`) or the published-day guard (`basket.guard`); the error lists the problems, one a line. Nothing went up. Fix the cause before the day is built again.

A manual basket run for a day earlier than the site's latest writes that day's file (when the site has none for it) and its record, and leaves the front page to the site's latest day; so a day the morning missed can also be run by hand in Lambda, the five extractions first.

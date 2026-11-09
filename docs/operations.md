# Operating the collector

How to deploy the collector, run it by hand, read what it wrote, read a day of update files, clear a stopped chain, drop a chain, and what it costs; then how to build and publish the shopper site by hand, the headline basket among it, how the site's function does it every morning, and how step one is deployed. What the collector does and why: [collector.md](collector.md); each portal's mechanics: [portals.md](portals.md).

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

A second function in the same stack, the shopper site's (the headline basket's before it), runs six schedules of its own after the check, on a switch of its own ("The shopper site, every morning", below).

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

2. **healthchecks.io.** Create a check with period 1 day and grace 2 hours, and copy its ping URL (`https://hc-ping.com/<uuid>`). The 11:48 check pings it each morning; when no ping arrives, healthchecks.io emails. That catches a morning where nothing ran at all. Create a second check the same way for the 12:33 run (the site run); its URL is `BasketHealthcheckUrl` ("The shopper site, every morning", below).

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

   The inner double quotes around the User-Agent matter: `--parameter-overrides` splits on spaces, and without them the value is cut at the first space (the template refuses a value without `+https://` and an `@`, which catches that). Review the change set and confirm. The site's bucket and distribution are the site stack's outputs `SiteBucketName` and `SiteDistributionId` ("The site's stack", below), so that stack is deployed first; the template refuses a bucket whose name does not start `il-grocery-prices-site-sitebucket-`, so the archive bucket can never be given for it. `BasketScheduleState` is the basket function's own switch; `sam build` also builds its DuckDB layer ("The shopper site, every morning", below). `PollScheduleState` is the update-file polls' own switch, `DISABLED` until the polls have been run by hand (steps 6, 7 and 9).

   On the live stack, the deploy that first carries the polls passes `'ScheduleState=ENABLED'` and `'BasketScheduleState=ENABLED'` as they stand, with `'PollScheduleState=DISABLED'`: the command's values are what keeps the morning and the basket running, since `sam deploy`'s change-set table looks the same either way. Reading its change set ([update-files-plan.md](update-files-plan.md), "Deploying this branch"): `CollectorFunction` and `BasketFunction` modified, not replaced (both are built from `src/`, so both zips change; the collector's environment gains `POLL_SCHEDULE_STATE`); 27 new schedules, each with its own IAM role (SAM adds one per `ScheduleV2` event: the 2026-11-07 deploy's change set listed 23 schedules and 23 `<schedule>Role` roles); the existing 23 schedules and their 23 roles modified, not replaced, as on every deploy, and the 23 schedules must stay enabled, which `sam deploy`'s change-set table does not show: it gives each resource's operation, logical id, type and replacement only, and on 2026-11-07 it listed every one of the 23 schedules as `Modify`, no replacement, with no switch changed, so the command's `ENABLED` values are the guard and the state check after the deploy (below) the proof; the DuckDB layer removed and added under a new logical id, as on every build (on 2026-11-04 and 2026-11-07 only the 41 cpython-314 `.pyc` caches differed, never loaded by python3.13: compare the live layer's files with `.aws-sam/build/DuckDbLayer` before executing); nothing else removed or replaced, and nothing on `ArchiveBucket`, `AlertTopic` or the log groups. Anything else: cancel the change set and find out why first.

   On the live stack, after the deploy and before the next 06:30, read each schedule's state (it only reads):

   ```bash
   aws scheduler list-schedules --query "Schedules[].[Name, State]" --output table --profile flights-sam --region il-central-1
   ```

   SAM names each schedule for its function and its event in `template.yaml` (`CollectorFunctionMainRamiLevy`, `CollectorFunctionCheck`, `CollectorFunctionPollRamiLevy1220`, `BasketFunctionExtractShufersal`). Every `CollectorFunctionMain…`, `CollectorFunctionRetry…` and `CollectorFunctionCheck` schedule must say `ENABLED`, the basket's six (`BasketFunction…`) `ENABLED` too while their switch is on (`DISABLED` from step one's deploy until they go back on: "Deploying step one", below), and every `CollectorFunctionPoll…` one `DISABLED` until the polls' switch goes on (step 9). The list also holds other stacks' schedules in the account, such as flights-archive's `CollectorFunctionEveryTwoMinutes`. A schedule in the wrong state: deploy again before 06:30 with its switch as it should stand.

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
pytest --cov=collector --cov=src/basket --cov=src/shopper --cov-fail-under=95
cfn-lint --regions il-central-1 -- template.yaml site-template.yaml
python scripts/mutation_check.py
```

The tests of `search.js` run it under Node, so `node` must be on the path (CI pins 22.11.0). The mutation check breaks each rule in turn and expects a test to fail. It edits source files in place while it runs, so run nothing else from the checkout meanwhile. CI runs the tests and cfn-lint on every push, with a check that every mutation's text is still found once in its file (`.github/workflows/ci.yml`); the full mutation check takes one to two hours, so it runs weekly on main, Saturday 03:00 UTC, and on demand from the Actions tab (`.github/workflows/mutations.yml`). `tests/test_template.py` pins the deploy settings safety depends on (the bucket's lock and privacy, the role's permissions, the schedules, the parameters) and checks this file's commands against them, `tests/test_basket_template.py` the basket function's: cfn-lint lets a misspelled schedule property through.

## Cost

Estimates from [collector.md](collector.md), "Cost", and, for the update files through the day, from [update-files.md](update-files.md), section 6, with the build plan's check of its arithmetic ([update-files-plan.md](update-files-plan.md), Task 6, "Cost"; where the check differs, both are given). The update files' figures are estimates until rollout step 4 measures them (MB a day per chain, GB-seconds a month from CloudWatch: [update-files.md](update-files.md), section 7); the measured figures replace them here then.

- **Volume:** Shufersal's full files were about 162 MB on 2026-10-31 (measured from its listing); the other four chains have fewer stores. About 250 to 300 MB a day, so 8 to 9 GB a month. The update files add about 80 to 550 MB a day, almost all of it Rami Levy's afternoon `Price` files (by hour, a mean of 22 KB at 07:00 and 357 KB at 14:00).
- **S3 storage** at $0.025 per GB-month (il-central-1): about $0.25 the first month, about $2.70 a month after a year. Nothing is deleted (every file is locked for ten years), so storage grows every month; moves to colder storage wait until the bucket passes about 50 GB. The update files add 2.4 to 16.5 GB a month: after a year 29 to 198 GB, $0.73 to $4.95 a month; after ten years 290 to 1,980 GB, $7.30 to $49.50 a month; about $440 to $2,970 paid over the ten years (the check: about $430 to $440 at the low bound and $2,950 to $3,000 at the high one).
- **S3 writes:** about 2,000 a day at $0.0055 per 1,000: about $0.35 a month. The polls add about 3,000 to 4,200 a day: $0.50 to $0.70 a month.
- **Lambda:** the morning's runs are a few invocations of up to 15 minutes a day, inside the monthly free tier. The 27 polls are expected to take about 2,450 GB-seconds a day at 512 MB, about 74,000 a month: Rami Levy's seven at about 400 s each, 1,400 a day, and Yochananof's, Osher Ad's and Carrefour's 20 at about 150, 100 and 60 s, 1,050 a day (the check: 1,055); Shufersal's twelve pass runs, at rollout step 3, about 3,780 a day more (6,230 a day in all, about 187,000 a month). With the collector's mornings (about 60,000 to 100,000 a month), the basket (about 19,000, up to 95,000) and flights-archive's flight-board collector in the same account (a few tens of thousands, its durations not read), the account's expected total is about 290,000 to 420,000 GB-seconds a month against the free tier's 400,000: $0 to $0.35 a month beyond it (the check: $0.33), at $0.0000166667 a GB-second (US East's x86 rate; the arm64 and il-central-1 rates not checked). If every poll, Shufersal's included, ran its full 900 s, about $5 to $6 more in that month (the check: a total of $3.80 to $6.00 beyond the free tier in that month). The polls add 27 invocations a day (39 with Shufersal's, about 1,200 a month), inside the free million. The worst case, all 43 collecting runs (the morning's 16 and the 27 polls) and the check running the full 15 minutes at 512 MB, is 19,800 GB-seconds a day, about 594,000 a month: about 194,000 over the free tier's 400,000, about $3.23 a month at the US East x86 rate above ($0.0000166667 a GB-second), with the basket's and the flight-board collector's time on top. A timed-out Shufersal page's further tries (ruling R38) use time a run already has, so that worst case does not move; the most they can add is the time the runs leave unused: on 2026-11-06 the six Shufersal runs that ended on an error left 3,691 s unused, about 1,850 GB-seconds at 512 MB, about 55,000 a month, inside the free tier's 400,000.
- **Concurrency:** the 27 polls never overlap one another (each starts at least 15 minutes after the one before), and none is in flight while the basket's extractions run. The design set that spacing for a Lambda quota of 5 concurrent runs in il-central-1, recorded on 2026-10-29; the account's quota read 400 on 2026-11-07 (`aws lambda get-account-settings`: `ConcurrentExecutions` 400; Service Quotas `L-B99A9384`, "Concurrent executions", 400.0), so the spacing is kept as approved, not as a limit the polls come near.
- **S3 reads:** each Shufersal run lists the day's Shufersal manifests once and reads each earlier one: on the eight scheduled Shufersal runs, 8 listings and 28 reads a day, about 1,100 requests a month, under $0.01 a month if they cost no more than the writes above. The polls' listings of the day's stored files and Shufersal's manifest reads add about 400 a day: under $0.07 a month at the write rate, an upper bound.
- **Total:** about $1 to $3 a month in the first year. The update files add about $1 to $3 a month averaged over the first year (the check: about $0.90 to $3.70), $1.20 to $6 in its last month, and storage alone $7 to $50 a month in year ten. The account's $5 monthly budget alarm ([headline-basket.md](headline-basket.md), "Cost") would sound within the first year at the high bound, which is why rollout step 4's measurement is a gate.

### The shopper site

Estimates from [shopper-site-plan.md](shopper-site-plan.md), "Cost" (the design's figures, checked, and its amendment's: [shopper-site.md](shopper-site.md), "Cost" and "Changed after the survey"), on top of the collector's, the update files' and the basket's above; step one's measured figures (GB-seconds from CloudWatch, the month's bill) replace them here.

- **Lambda.** The promotions and items steps in the five extractions, estimated at about 600 s a day at 2 GB: about 36,000 GB-seconds a month (Shufersal's took 157.2 s of them on the Mac: "Sizing", below). The site run, an estimate from the Mac's measure, to be replaced by the first manual site run's in Lambda: from about 430 s a run (329.8 s of CPU for its compute, measured on the Mac at full scale, and about 104 s for the site check over 34,708 pages at Task 20's 3.0 ms a page: "Sizing", below) up to the function's 900 s, its timeout, since the fetches, the guard and the uploads are not measured and Lambda's speed against the Mac's is not known for this work. At 2,048 MB and about 30 runs a month that is about 26,000 to 54,000 GB-seconds a month. In all about 62,000 to 90,000 a month, beside the basket's measured 19,000 or so: $0 to $1.50 a month, as the account sits at the free tier's edge ("Lambda", above). Worst case, all six runs a day at their full 900 s: 324,000 GB-seconds, $5.40 a month. The function's `/tmp` is 10,240 MB since step one ("Sizing", below), and Lambda bills `/tmp` above 512 MB by the GB-second, at $0.0000000309 a GB-second in US East ([headline-basket.md](headline-basket.md), "Cost", from AWS's pricing page; il-central-1's rate UNVERIFIED). Every run of the function carries it: about 9.5 GB over the five extractions' about 870 s a day (about 270 s measured for their prices tables, about 600 s estimated for their promotions and items) and the site run's 430 to 900 s, about 370,000 to 505,000 GB-seconds a month: about $0.01 to $0.02 a month, the site run's share under a cent; all six runs at 900 s, about $0.05.
- **S3 writes.** Every page goes up every morning (the design's Q2): about 24,500 to 27,500 files a day, the nine columns' covered products (24,394 on 7 November 2026 against 22,051 counted chain by chain, the design's direct read of that day's prices tables, Carrefour's stores placed by the word in their names; the items tables of the same day, by the code's rules and the hand-kept Carrefour table, cover 24,234: "Sizing", below) and about 100 other files; 735,000 to 825,000 a month at $0.0055 per 1,000: $4.04 to $4.54.
- **S3 reads.** About 1,350 a day for the design's reads, $0.22 a month; the items tables' reports, the scoring summaries, the listing of `p/` and a few heads add under $0.15 a month, priced at the write rate as an upper bound.
- **S3 storage.** The pages about $0.01 a month; their old versions under the 30-day rule about $0.52 (the plan's figure, at pages of about 25 KB with nine columns; at the median of 12,355 bytes measured on full-scale synthetic tables, "Sizing", below, about half that); the tables about $0.15 a month after a year; the forecasts and scores files a few cents.
- **Total:** about $4.80 to $7.20 a month in year one, an estimate (the `/tmp` line above adds a cent or two): the plan's $4.80 to $6.80 with its Lambda line at the site run's range above ($1.50 at most, against the plan's $1.10 for a run of 300 to 500 s); worst case about $11. The account's $5 budget alarm goes to $20 with step one ("Deploying step one", step 1, below; the design's Q8).

## The shopper site, by hand

Step one of the shopper site ([shopper-site.md](shopper-site.md), "Order of building"; its build plan, [shopper-site-plan.md](shopper-site-plan.md)): the whole site for one day, built on the Mac from what the archive holds and uploaded by hand, as the headline basket's step one was. It is the basket's site grown, in the same stack, `il-grocery-prices-site` (`site-template.yaml`: a private S3 bucket that only one CloudFront distribution reads; "The site's stack", below), separate from the collector's so a site change never touches the archive. The pages: the front page (`index.html`), a page per product the site covers (`p/<barcode>.html`), the browse pages (`browse/`), the search pieces (`search/`) and `search.js`, and the method, record and basket pages (`method.html`, `record.html`, `basket.html`); beside them the data files (`days/`, `site-days/`, `forecasts/`, `scores/`). The hand build runs the site run's code ("The shopper site, every morning", below) with two differences: it never scores and never freezes forecasts, taking what the site run froze and scored as the sync brings it, and it adds no line to the forecasts ledger. It is the path for the first upload, for revising the site's latest day, and for the latest day when the morning's run did not publish it.

### The steps

1. **Sync each day** the build reads (read-only on AWS):

   ```bash
   sh scripts/sync.sh YYYY-MM-DD
   ```

   After the identity check it copies the day's full price files, full promotion files and store lists into `data/raw/` and the day's manifests into `data/manifests/`; then, whatever the day, every items table, covered registry and scoring summary in the archive into `data/tables/`, and the frozen forecasts files and the scores files into `data/forecasts/` and `data/scores/` (the forecasts files with `--exact-timestamps`: the build compares a synced file's time with the published ledger's); then, once the site's stack exists, the published day files, site-day files and the ledger into `site/days/`, `site/site-days/` and `site/forecasts/`, the bucket's copy replacing a local file unless the two have the same size and the same modification time (`--exact-timestamps`; without it the sync keeps a same-sized local file that is no newer than the bucket's). Before the stack exists it says so in one line and goes on; any other failure to read the stack stops it. The published files are what the build compares with ("Revising a day", below) and what its forecasts checks read (step 3): once a day is published, build it only into a `site/` the sync filled.

   The build reads the day and the 90 days before it. Until the archive holds the items tables of the past days (the backfill, "Deploying step one", below), sync each past day too and extract it (step 2).

2. **Extract** each day whose items tables the archive does not hold. The build extracts its own day when its tables are missing; past days only this command extracts:

   ```bash
   PYTHONPATH=src .venv/bin/python -m shopper.extract --data data --day YYYY-MM-DD
   ```

   Each chain's prices, promotions and items tables go under `data/tables/`, with a line of JSON a chain on the terminal (counts only, no product name or promotion text); `--chains` names some of the five. Shufersal's day took 249.5 s on the Mac (prices 91.8 s, promotions 150.9 s, items 6.3 s), at a peak of 977 MiB resident with DuckDB held to Lambda's 1,200 MB ([shopper-site-plan.md](shopper-site-plan.md), "Deviations", Task 5's review fix round 2). A chain whose promotions cannot be read (a format change: a field, a code, a date or an amount its files were never seen to carry; or a promotion file that does not read) keeps its prices and items tables, the items table marking the error, and its line names it (`promotions_error`; what to do: "What a /fail email means", below). A price file that does not read, or a chain with no store list on or before the day, stops the command there (exit 1).

3. **Build:**

   ```bash
   PYTHONPATH=src .venv/bin/python -m shopper.build --day YYYY-MM-DD --collected-by 11:48
   ```

   The whole day in one command. Each chain's tables of the day are extracted when missing (`--rebuild` extracts all five again); the history of the day and the 90 days before it is read from `data/tables/items/`, a day with no items table a hole; the covered registry is written under `data/tables/covered/`; one pass over the history gives the forecasts (from a column's 30th day of records) and every covered product's page; the basket is priced, its private record written once to `data/basket/date=<day>/`; then the site-day file and the basket's day file are published by the revision rule (B12); then every page, the search pieces, `search.js` and the marker `.shopper-site` go into `site/`. `--collected-by` sets the time on the credit line ("the files of …, collected by 11:48 Israel time"), as for the basket: the hand build may run hours after the morning, so it passes the check's time, 11:48, the collector's last schedule, which starts after the last retry run can have finished ("What runs when", above). A later build of the same day leaves this time out of its comparison (B12).

   The forecasts on the Mac. Only the site run in Lambda freezes a day's forecasts and scores the days due ([shopper-site-plan.md](shopper-site-plan.md), question D); the hand build takes the day's forecasts file as the sync brought it, with the published ledger's line for it, and the scores as the site run published them. So:

   - A hand build of a day with forecasts that the site run has not frozen stops before midnight ending the day, Israel time (`NotFrozenYet`), since the site run can still freeze it and a day published without forecasts stays so. From a column's 30th day of records, then, a daytime hand build needs the site run first (a manual one, "The manual runs", below) and a sync after it; or it waits until after midnight, when the day's forecasts can no longer be frozen and the build publishes the day with none.
   - A synced forecasts file the published ledger does not name, a day the ledger names whose file the sync did not bring, or a synced file whose time is not the ledger's, stops the build (`NotSynced`): sync again, or let the site run publish the day.
   - A hand build past midnight, with days due for scoring that the site run has not scored, publishes a record page without them. A later site run of that day (a manual one) then finds other numbers in its site-day file and refuses it (`RevisionNeeded`), and the day needs a revision ("Revising a day", below).

4. **Check:**

   ```bash
   PYTHONPATH=src .venv/bin/python -m shopper.check site
   ```

   The same check `scripts/publish.sh` runs before it uploads, and the site run before its upload (every rule is in `src/shopper/check.py`'s docstring): no never-phrase outside the method page's list of them, and no "we", "our" or "us"; a chain's own text (a product's, a store's or a programme's name) only inside its span, holding no markup, and cut out before the word rules; on every page the credit line, "Not shopping advice.", `noindex` and the newest site-day file's date line; every always-phrase on the front page and on every product page; `search.js` the only script, and nothing loaded from another origin; on a product page, each column whose gate is closed carrying its "No odds yet" sentence and no odds word, and each section of a chain whose promotions were not read carrying "Promotions from <chain>'s files could not be read today."; every link resolving to a file in the build (a link to a past day's forecasts or scores file by the ledger and the site-day file); a product page at most 60,000 bytes and a search piece at most 150,000; `basket.html` held to the basket's own index rules; `index.html` and the marker present. Exit 0 when clean; 1 with problems, one a line naming the file and the rule; 2 when there is no page.

5. **Review** in a browser. `search.js` fetches the search pieces and asks for product pages, which a page opened from disk may not be allowed to do (UNVERIFIED: not tried), so serve the folder on the Mac alone:

   ```bash
   .venv/bin/python -m http.server --bind 127.0.0.1 --directory site 8000
   ```

   and open http://127.0.0.1:8000/. Read the front page (the count line, the deals, the filters); a product listed at Shufersal's columns (each column's section, "The deal against its listed prices", "How often it goes on promotion", the row across the columns); the record page; the basket page; and the method page. In the search box, type a product's name and then its barcode: each should reach its page.

6. **Publish,** on the owner's go only, given after the owner has checked the "current as of" date on Nevo's page against `docs/terms.md` (a date past 19-07-2026 means the clause is read again first):

   ```bash
   sh scripts/publish.sh
   ```

   It writes to AWS. It checks and guards the folder the build wrote (it does not build), and uploads nothing unless every check passes, in this order: the identity check; `site/` carries the marker `.shopper-site`, and its full path holds no `[`, `]`, `?` or `*` (the upload's filters would misread them); the check of step 4; the bucket and the distribution from the stack's outputs, the bucket's name starting `il-grocery-prices-site-sitebucket-` (so never the archive bucket) and the distribution's ID not empty; the publish guard (`shopper.guard`). For the guard, the bucket's `days/`, `site-days/`, `forecasts/` and `scores/` are copied (reads) into a temporary folder and its product pages listed, and a read that fails stops the upload (exit 2): let through, it would leave the guard comparing the build with an empty bucket. The guard refuses a day file or site-day file that differs from its published copy unless it is a revision of it, a forecasts or scores file that differs from the published one, a ledger that does not begin with the published one, a record page whose scorecard is not the newest site-day file's, a build whose newest site-day file is an earlier day than the bucket's newest, and a build that lacks a product page the bucket holds. Then five uploads, the data files first and the pages last, as the site run puts them, each an allowlist with its content type set: `*.csv.gz` as `application/gzip` (the forecasts and scores files), `*.csv` as `text/csv; charset=utf-8` (the ledger), `*.json` as `application/json; charset=utf-8` (the day and site-day files and the search pieces), `*.js` as `text/javascript; charset=utf-8` and `*.html` as `text/html; charset=utf-8`, each with `Cache-Control: max-age=300`; then one CloudFront invalidation of `/*`; then it prints the site's address. An upload that fails stops the script (exit 1) and says which: the kinds before it are up, none after it, and nothing is invalidated, so no live page names a file not yet up; run it again, and the guard passes the files already up, which are the build's own bytes. Nothing else in `site/` (the marker, a `.DS_Store`) is uploaded, and no upload deletes: a page the build no longer writes stays on the site ([shopper-site-plan.md](shopper-site-plan.md), question H). The bucket keeps an earlier version of each file an upload replaces, and its lifecycle rules expire those of the rebuilt pages 30 days after each was replaced ("The site's stack", below).

The hand path publishes the site's latest day only. A build of an earlier day, into a `site/` the sync filled, fails the check (its pages' date line is not the newest site-day file's) and the guard (its newest site-day file is earlier than the bucket's), so a day earlier than the site's latest cannot be revised by hand, and its pages never go up over a later day's.

### What the build prints

One line per chain, in slug order: `<slug>: extracted in N.N s` or `<slug>: tables kept`. A line for each chain whose promotions could not be read: `promotions not read: <chain>: <message>`. Then `covered: N products`; the day's forecasts, `forecasts: none frozen for <day>` or, for a file the sync brought, `forecasts: same, N rows, SHA-256 <hash>, S3 time <time>`; the days due for scoring, which only the site run scores, and the frozen days out of the read's reach, when there are any; the front page's rows and the count line's three numbers; the basket's two headline lines, word for word; then, for the basket's day file and the site-day file each, `published`, `unchanged` (the published file already holds these numbers and is left as it is; the pages are then drawn from it, its "collected by" time included) or `revised`, with its path; the pages written; and the data files new to the site. A bad basket file, a price file that does not read, a chain with no store list, a missing table, the forecasts checks of step 3 (`NotFrozenYet`, `NotSynced`) and a published day with other numbers and no `--revise` (`RevisionNeeded`) stop the build with a message and exit 1, the pages in `site/` left as they were.

### Revising a day

A published day comes back into `site/` with the sync: its basket day file (`days/<day>.json`), its site-day file (`site-days/<day>.json`) and the ledger. The build compares each day file's numbers with its published copy's (B12), leaving out the run id, the code fingerprint, the build time and the "collected by" time. Equal: `unchanged`, and the file stays as it is. Different: the build stops (`RevisionNeeded`), names what differs, and asks for a reason. To republish, build again with a one-line reason:

```bash
PYTHONPATH=src .venv/bin/python -m shopper.build --day YYYY-MM-DD --collected-by 11:48 --revise "<one-line reason>"
```

The reason serves both files. Each that differs keeps its earlier run at the end of its `revisions` (its run id, code fingerprint, build time and its own `revised`, with the basket's totals or the site-day file's count line; the first entry is the day as first published, its `revised` null), and `revised` holds the reason and the Israel date; a file whose numbers are the same stays unchanged. The basket page says "Revised on <date>: <reason>. First published: <the earlier totals>.", and a day revised again also names each earlier revision, newest first: "Revised on <date>: <reason>. Earlier: on <date>: <reason>. First published: …". A blank reason, or one with a line break, is refused. Every build writes its private basket record, a refused one included. Then check, review and publish as above. The site run never revises; only a hand build given a reason does, and only of the site's latest day (above). The forecasts and scores files are never revised: they are the record, written once in the archive.

`--rebuild` extracts every chain's tables of the day again from the raw files, for instance after a parser fix; without it the day's tables already there are kept. A past day's tables are extracted again with `shopper.extract` (step 2). If the new tables change the day's numbers, the day needs `--revise` as above.

### Placing a Carrefour store

Carrefour's store list names no format, so its two columns, Carrefour City and Carrefour Market, come from a hand-kept table of store ids, `CARREFOUR_COLUMNS` in `src/basket/chains.py`, drawn from the survey's store groups of 5 and 7 November 2026 ("Measured for the shopper site", "Store groups", below). A store the table lacks, a new one included, is in no column: the basket still counts it, as it counts every included store, but its promotion files are passed over, no column's figures include it, and the method page names it among the included stores in no column. To place it, take a day on which it has a price file that counts: sync the day ("The steps", step 1), extract Carrefour's tables of it (step 2, with `--chains carrefour`: the survey reads the day's prices table, which the sync does not bring), then run the survey for Carrefour at the terminal and find the store in `store_groups`:

```bash
PYTHONPATH=src .venv/bin/python -m shopper.extract --data data --day YYYY-MM-DD --chains carrefour
PYTHONPATH=src .venv/bin/python -m shopper.survey --data data --day YYYY-MM-DD --chain carrefour
```

If it sits in the City group or the Market group, the owner's word adds its id to that column's list in `src/basket/chains.py` (`_CARREFOUR_CITY` or `_CARREFOUR_MARKET`, from which `CARREFOUR_COLUMNS` is made), in a commit naming the store and the day; until then it stays in no column. A table that changes moves the column's history from the day the deployed code first counts the store, as a store opening does.

### Measured on 2026-11-02

The headline basket's hand build (`basket.build`), on this Mac, from `docs/headline-basket-plan.md`, "Deviations" (Task 4 and Task 13). The sync brought 356 MB of raw files and 16 manifests. Extraction, as `basket.extract` printed it, with peak memory from `/usr/bin/time -l`:

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

### Measured for the shopper site

The promotion survey (`src/shopper/survey.py`) read each included store's latest full promotion file of Saturday 7 November 2026 and Thursday 5 November 2026, synced read-only by `sh scripts/sync.sh <day>` (which copies the day's `PromoFull` files beside the price files), against each day's prices table:

```bash
PYTHONPATH=src .venv/bin/python -m shopper.survey --data data --day 2026-11-07
```

It prints one JSON document per chain, and no promotion text. With `--samples` it also prints up to five texts per code, for the eye: run it so at the terminal only, its output never redirected, piped or saved; none is quoted here. The figures are 7 November's; 5 November's are in brackets where given. On 5 November the archive holds price files from 214 of Shufersal's 319 included stores, so that day's Shufersal figures cover two thirds of the chain.

**Files.** The stores counted are P2's: included, with a price file that counts that day.

| Chain | Included | Counted | Files read | Earlier files passed over | Promotions | Item links | Distinct texts | Links a file, median | Most |
|---|---|---|---|---|---|---|---|---|---|
| Shufersal | 319 | 317 (214) | 318 (208) | 0 | 321,893 (258,624) | 5,461,315 (4,162,130) | 8,191 (7,965) | 17,904 | 28,288 |
| Rami Levy | 98 | 97 | 97 | 62 (73) | 189,189 (187,961) | 1,035,778 (1,034,920) | 6,128 (5,841) | 13,521 | 14,467 |
| Osher Ad | 24 | 21 (24) | 21 (24) | 20 (24) | 15,697 (18,345) | 61,163 (72,150) | 1,282 (1,352) | 2,930 | 3,061 |
| Carrefour | 146 | 136 (145) | 136 (145) | 11 (10) | 223,231 (236,175) | 1,024,064 (1,092,921) | 7,087 (7,064) | 7,392 | 24,205 |
| Yochananof | 51 | 47 | 47 | 0 | 53,275 (52,172) | 175,136 (172,777) | 2,399 (2,349) | 4,060 | 4,375 |

The files of stores not included were passed over unread: Shufersal's 99 (96 named under Be's sub-chain 005; store 413; store 678, named under 002 but in Be's sub-chain on the store list; store 878, not on the day's store list), Rami Levy's store 039 and Carrefour's store 471. Store 039's promotion file has a layout of its own (elements inside `AdditionalRestrictions`), which the reader refuses; it is left out by B2 in any case. Shufersal's promotion files of 7 November are named under the sub-chains its price files carry (001 to 032; one file under 000), not under 000 as P3 records from 31 October. Shufersal's two largest coupons (9,107 and 9,110 item links, at 312 stores) hold 3,557,570 of its 5,461,315 links; Carrefour has four coupons of 1,104 to 3,122 links, each at one store; no other chain has a coupon over 1,000 links.

**Fields.** Every file of every chain on both days carries the same tags at each level: the root's 5 (`ChainID`, `SubChainID`, `StoreID`, `BikoretNo`, `Promotions`), a promotion's 17 (`PromotionUpdateTime`, `AllowMultipleDiscounts`, `PromotionID`, `PromotionDescription`, `PromotionStartDateTime`, `PromotionEndDateTime`, `PromotionStartHour`, `PromotionEndHour`, `PromotionDays`, `RedemptionLimit`, `MinNoOfItemOffered`, `ClubID`, `IsGiftItem`, `AdditionalIsCoupon`, `AdditionalRestrictions`, `Remarks`, `Groups`), a group's 4 (`GroupID`, `MinPurchaseAmount`, `DiscountType`, `PromotionItems`) and an item's 9 (`ItemCode`, `ItemType`, `RewardType`, `MinQty`, `MaxQty`, `DiscountRate`, `DiscountedPrice`, `DiscountedPricePerMida`, `bIsWeighted`). Element by element, one set per level, except items: at Shufersal 9,831 items (6,886) and at Yochananof 652 (653) have no `MaxQty`, every one of them in the second group of a promotion of two groups (a one-off read of 60 of Shufersal's files and all of Yochananof's).

**Codes**: the values seen on either day; the counts, of item links or promotion copies over the files read, are 7 November's.

- `RewardType`: Shufersal 0, 1, 2, 3, 6, 10, 12; Rami Levy and Yochananof 0, 1, 2, 3, 10; Carrefour 0, 1, 2, 3, 10, 12; Osher Ad 1, 3, 10. Read with the texts for the eye: 1 and 10 "N for ₪M", 2 percent off (and gift coupons), 3 a fixed price, as P3 reads them; 12 basket-level rewards (a voucher, delivery over a basket, paying by credit card: Shufersal's 2 promotions, 68,053 links; Carrefour's 18, 81,394 links); 6 at Shufersal "buy and get a gift" (one promotion and 4 links at the stores read; Be's stores, not read, carry more). 0 sits in promotions of two groups: in the first group at Rami Levy (all 54,415 links), mostly the first at Carrefour (16,157 links; 2,295 coupon links in the second), both at Yochananof (1,413 in the first, 652 in the second), and at Shufersal on coupons (99.6% of its 0 links in 60 files; a one-off read of the files). On 7 November, `RewardType` 0 links with a `DiscountedPrice`: Shufersal 4,349,017 of 4,352,201, Rami Levy 15,580 of 54,415, Carrefour 2,305 of 18,604, Yochananof 1,413 of 2,065; none has a `DiscountRate`.
- `ClubID`: Osher Ad writes "0" only. Shufersal and Yochananof write a code and a label, "0 - " with "all customers", Shufersal also "2 - " with the retailer's credit club (272 copies, 2 promotions), Yochananof "1 - " with its employees' club (593, 13). Rami Levy writes "0" or an expression of codes and names, as `((1=…|1=…))&(3=…|3=…)` and `(1=…|1=…)`: 12 expressions, codes 1, 2 and 3. Carrefour writes "0", "()" (61 copies) or one of 7 lists, as `(2=…|2=…)`: codes 0 to 3, code 0 with its credit and app clubs named on 1,834 copies (the five texts printed for each of those two forms all begin with "app"), and code 3 with other programmes (a benefits card, two municipalities).
- `IsGiftItem`: Shufersal "" and 0.5 to 6.5; Rami Levy "" and 1 to 10; Osher Ad "" and 1 to 10 and 12; Carrefour "" and 1 to 8 and 10; Yochananof "" and 0.5, 2.0, 3.0, 4.0. Where set, it equals the link's `MinQty` (both days) on 100% of Osher Ad's links, 98.6% of Carrefour's, 93.3% of Rami Levy's, every one of Shufersal's 1.5 to 6.5 (0.5 never), and none of Yochananof's. Read with the texts, it is the deal's quantity ("N for ₪M", or kilograms of a weighed deal) at every chain, never a gift marker.
- `AdditionalIsCoupon` 0 and 1 (Osher Ad 0 only); `DiscountType` "", 0 and 1 (Osher Ad "" and 1, Yochananof "" and 0); `bIsWeighted` 0 and 1.

**Minimum spend** (`MinPurchaseAmount` above zero, by the group's place in its promotion): Shufersal on 8,331 first groups (5,664), 2,050 second groups (1,594) and 2 each of third and fourth groups (the same), those of its 2 promotion copies of four groups (a copy is a promotion as one store's file holds it: the survey counts every copy); Rami Levy on 6,079 first groups (6,672; 75.00 on 5,650 of 7 November's), none of its second groups; Carrefour on 104 first groups (3,128), none of its second or third groups; Yochananof on 652 second groups (653) and none of its first groups, which leave it empty; Osher Ad on none. No group without items carries one.

**Chain-wide** (P3: carried by at least half the counted stores). By promotion id, and by item code: the codes a promotion that is no coupon links at a counted store, and those on a link (promotion, group, item code) at least half the counted stores carry.

| Chain | Promotions, chain-wide of all | Not coupons | Item codes, chain-wide of all |
|---|---|---|---|
| Shufersal | 121 of 8,191 (134 of 7,962) | 11 of 8,039 (22 of 7,812) | 681 of 7,942 (732 of 8,710) |
| Rami Levy | 2,353 of 5,465 (2,359 of 5,173) | 2,006 of 5,115 (2,012 of 4,823) | 7,605 of 9,523 (7,690 of 9,502) |
| Osher Ad | 754 of 1,255 (761 of 1,318) | 754 of 1,255 (761 of 1,318) | 2,898 of 3,411 (2,957 of 3,513) |
| Carrefour | 376 of 7,077 (1,632 of 7,042) | 282 of 6,967 (1,538 of 6,932) | 2,623 of 7,446 (6,016 of 7,374) |
| Yochananof | 1,226 of 2,399 (1,193 of 2,349) | 1,202 of 2,374 (1,169 of 2,324) | 3,894 of 5,595 (3,821 of 5,526) |

Over the included stores instead (7 November), the promotions chain-wide are the same at Shufersal and Rami Levy, and Osher Ad 746, Carrefour 252, Yochananof 1,207. Shufersal's promotions are its sub-chains': within each, most are carried by half its stores (sub-chain 1, 71 stores: 1,233 of 1,646 promotions, 3,193 of 4,777 codes; 2, 76 stores: 1,446 of 1,793 and 3,905 of 5,360; 7, 93 stores: 832 of 1,445 and 1,822 of 4,270; 8, 31 stores: 1,552 of 1,780 and 4,352 of 5,212). Carrefour's swing between the days comes from about 1,300 promotions carried by about half its stores: at 50% to 59% of 145 stores on 5 November and at 40% to 49% of 136 on 7 November (a one-off read); of the 1,538 not coupons at half or more on 5 November, 216 were at half or more on 7 November.

**Store groups** (`store_groups`; the source of Carrefour's store table, `basket.chains.CARREFOUR_COLUMNS`). Each counted store with a promotion file gives its set of the promotions none of whose copies is a coupon; two stores are joined when their sets' Jaccard index (the promotions both carry over those either carries) is at least 1/2, and the groups are the connected components. A group's wide set is the promotions at least half its stores carry. Carrefour on 7 November (5 November in brackets): groups of 67 (74), 43 (44), 18 (18), 7 (7) and 1 (2) stores; wide sets of 1,555 (1,538), 1,514 (1,508), 1,579 (1,574), 1,525 (1,520) and 1,435 (1,439) promotions; the least store's share of its group's wide set 90.5% (90.7%), 98.2% (98.2%), 98.9% (98.6%), 99.3% (99.4%) and 100% (99.9%), the median store's 100% (100%), 100% (100%), 99.7% (99.5%), 99.6% (99.9%) and 100% (99.9%). Of the 135 stores counted on both days, none is in two groups. The two large groups' stores over both days are the table: 75 stores in Carrefour City and 44 in Carrefour Market, each named by the word most of its stores' names carry on the store list ("סיטי", City, on 65 of the 75; "מרקט", Market, on 32 of the 44). The other 27 included stores, the groups of 18 and 7 and the type-2 stores 472 and 473, are in no column.

**The same link at different stores** (one (promotion, group, item code) whose copies differ in some field): Shufersal 47,855 of 71,268 links, Rami Levy 16,679 of 22,341, Carrefour 19,412 of 42,288, Osher Ad 2,180 of 5,102, Yochananof 573 of 8,356. The fields that differ most: `PromotionUpdateTime` (Shufersal 28,455 links, Rami Levy 13,653, Carrefour 19,384), the price fields (`DiscountedPrice` at Shufersal on 44,962 links), and at Rami Levy the text (3,075 links).

**Percent off** (`RewardType` 2): `DiscountedPrice` against the day's median price (B5) × (1 − `DiscountRate`/100), rounded half up to agorot, within ₪0.01; and against the store's own price.

| Chain | Links | Agree with the median | No median | Disagree | Agree with the store's own price |
|---|---|---|---|---|---|
| Shufersal | 299,008 | 206,625 (69%) | 0 | 92,383 | 297,859 of 298,402 |
| Rami Levy | 57,564 | 52,258 (91%) | 2,445 | 2,861 | 38,209 of 39,172 |
| Carrefour | 206,362 | 109,734 (53%) | 85,425 | 11,203 | 15,131 of 15,131 |
| Yochananof | 1,202 | 1,035 (86%) | 0 | 167 | 1,040 of 1,202 |

None reads as the discount itself; Osher Ad has no percent-off links. Most of Carrefour's percent-off links name codes the store's own price file does not list, and about 40% codes no Carrefour price file lists that day (a one-off read of 40 files).

**Dates.** No promotion of either day is listed before its start, and none ended before the day; every date reads.

**Time and memory.** Shufersal's survey took 231 to 296 s on this Mac over three runs of the same files (the last with the final measures, other work beside it), the five chains 350 to 445 s, at a peak of 571 to 783 MB resident (`/usr/bin/time -l`). The site's `Last-Modified` header passes through CloudFront (`curl -sI https://d153udx05irk2f.cloudfront.net/index.html` on 8 November: `last-modified: Sat, 07 Nov 2026 10:33:27 GMT`).

### The site's stack

The stack was first deployed for the headline basket. To deploy it where it does not exist yet (to update it, "Deploying step one", step 3, below), on the owner's go: the identity must show account `137953273942` and a user ARN ending in `user/doron-admin`; then the deploy, as flights-archive deploys its site (no SAM: the template holds no code); then the outputs:

```bash
aws sts get-caller-identity --profile flights-sam --region il-central-1
aws cloudformation deploy --template-file site-template.yaml --stack-name il-grocery-prices-site --profile flights-sam --region il-central-1
aws cloudformation describe-stacks --stack-name il-grocery-prices-site --query "Stacks[0].Outputs" --output table --profile flights-sam --region il-central-1
```

The outputs name the bucket (`SiteBucketName`), the distribution (`SiteDistributionId`) and the address (`SiteDomainName`); both scripts read them from the stack. The bucket is created with versioning on, and AWS asks for 15 minutes after versioning is first enabled before objects are written (the `VersioningConfiguration` description in the AWS::S3::Bucket resource schema, as cfn-lint bundles it), so the first upload waits that long after the first deploy.

The bucket keeps an earlier version of each file an upload replaces. Its lifecycle rules (`LifecycleConfiguration` in `site-template.yaml`, eight of them, one per prefix) expire an earlier version of a rebuilt page 30 days after it was replaced: the files under `p/`, `browse/` and `search/`, and `index.html`, `method.html`, `record.html`, `basket.html` and `search.js`, which every morning rewrites. It never expires a current file, nor any version under `days/`, `site-days/`, `forecasts/` or `scores/`, the record. Those rules are the one thing that removes anything from the site bucket; nothing in the code deletes.

## The shopper site, every morning

Step one of the shopper site, scheduled: the basket's function, `BasketFunction` in the collector's stack, in its two modes. Its five extractions write each chain's prices, promotions and items tables, and its 12:33 run, the site run (its event keeps `"mode": "basket"`), builds, checks, guards and publishes the whole site, the basket's day among it, with the hand build's code. Its six schedules have a switch of their own, `BasketScheduleState`, apart from the collector's `ScheduleState`. Until step one's deploy ("Deploying step one", below), the function in AWS runs the headline basket's code: five extractions of the prices tables and a 12:33 run that builds the basket's two pages ([headline-basket.md](headline-basket.md), "The pipeline"). What it costs: "Cost", above.

### What runs when

| Israel time | Run | Event |
|---|---|---|
| 12:03 | Shufersal's tables of the day | `{"mode": "extract", "chain": "shufersal"}` |
| 12:03 | Rami Levy's tables of the day | `{"mode": "extract", "chain": "ramilevy"}` |
| 12:03 | Osher Ad's tables of the day | `{"mode": "extract", "chain": "osherad"}` |
| 12:03 | Carrefour's tables of the day | `{"mode": "extract", "chain": "carrefour"}` |
| 12:03 | Yochananof's tables of the day | `{"mode": "extract", "chain": "yochananof"}` |
| 12:33 | The site run: the whole site of the day, the basket's record and day file among it | `{"mode": "basket", "collected_by": "12:03"}` |

An extraction fetches its chain's full price and promotion files of the day and its store list from the archive bucket, runs `shopper.extract` over them as the hand build does (step 2 of "The shopper site, by hand"), and puts the chain's tables back: the prices table, as the basket has always had it; the promotions table and the promotion texts; and the items table, a row per column and product. A promotion format change, or a promotion file that does not read, stops only the chain's promotions: its prices and items tables still go up, the items table marking the error, and the site run alerts on it. The five read S3 only and touch no portal, so they start together, 15 minutes after the collector's check: Lambda's longest run, so the check can have finished. The site run starts 30 minutes after them, 15 minutes after the last extraction can have finished, for its tables' put and the schedulers' lag. It fetches each chain's prices table of the day, its store list and its manifests; each chain's items tables of the day and of the 90 days before it (a past day's missing table is a hole in each of the chain's columns); the latest covered registry and every scoring summary; and the site's published copies the build and the guard compare with. It runs `shopper.build` as the hand build does, but through a freezer that writes: it scores each frozen day whose 14 days have passed, its scores file written once in the archive; it freezes the day's forecasts (from a column's 30th day of records), written once, and adds the day's line to the ledger; and it never revises. Then it checks the built site with `shopper.check` and the publish guard (`shopper.guard`), as `scripts/publish.sh` does, and uploads. Its `collected_by` is the extractions' time, fixed in the event (B11), so the record does not depend on when the run starts.

Both modes first look for a key under `checks/date=<day>/` (a list of the archive bucket; no check record is read) and refuse the day without one (`MorningNotChecked`). The check is the morning's last run, so its record shows that every chain's runs are over, and a late or failed check stops the build rather than letting it work on a partial morning. A scheduled run is for the Israel date it starts on; a manual run names its day (`"day": "YYYY-MM-DD"`).

The site run uploads the data files the build wrote new, always: first the day's forecasts file and the scores files, in a call of their own, so that a record put that fails stops the run (`RecordsNotUploaded`) before anything names the file; then the ledger, and the site-day and basket day files when they are not unchanged. Then, only when its day is the site's latest or later (or the site has none), every page under `p/`, `browse/` and `search/` and the five fixed pages, `index.html`, `method.html`, `record.html`, `basket.html` and `search.js`; so a run for an earlier day writes that day's files and record and leaves every page to the site's latest day. A day published with the same numbers (`unchanged`, B12) keeps its published files, and one published with other numbers stops the run (`RevisionNeeded`), since the site run never revises. One CloudFront invalidation of `/*` follows any upload. The day's covered registry and each new scoring summary go back to the archive after the upload, so a run whose upload fails leaves its days due for the next run. Neither the schedules nor Lambda retry a failed invocation; a rerun is by hand ("The manual runs", below).

### Where things land

In the archive bucket, beside the collector's keys:

- `tables/prices/chain=<slug>/date=<day>/prices.parquet` and `report.json`: a chain's prices table of the day and its counts.
- `tables/promotions/chain=<slug>/date=<day>/promotions.parquet`, `texts.parquet` and `report.json`: the promotions table, a row per column, promotion, group and item code, with the column's stores carrying it and whether it is wide there; the chain's distinct promotion texts, for the promotion reader; and the counts, or, for a chain whose promotions could not be read, the error alone.
- `tables/items/chain=<slug>/date=<day>/items.parquet` and `report.json`: the items table, a row per column and product (its `column` field one of the nine keys, as `shufersal-deal`), and its counts. The tables of all nine columns stay under their chain's folder: the extraction runs once per chain.
- `tables/covered/date=<day>/covered.parquet`: every product the site has covered so far (the covered registry), and `tables/scored/date=<day>/summary.json`: a scored day's summary, both written by the site run.
- The tables are plain and overwritable: a later run of the same day replaces them, and the archive keeps the replaced one as an earlier version ([headline-basket.md](headline-basket.md), "Cost").
- `forecasts/date=<day>/forecasts.csv.gz` and `scores/date=<day>/scores.csv.gz`: the day's frozen forecasts and a scored day's scores, written once and locked for ten years (governance mode), as a manifest is.
- `basket/date=<day>/basket-<run id>.json`: the basket's private record (B10), written once and locked for ten years, as a manifest is. Every build writes one, a refused one included (`RevisionNeeded`, `SiteCheckFailed`); a run that stops before the build has priced the day (`MorningNotChecked`, `MissingTable`, `NoStoreList`) writes none.

In the site bucket: `index.html`, `method.html`, `record.html`, `basket.html`, `search.js` and every page under `p/`, `browse/` and `search/` (only for the site's latest day); `days/<day>.json` and `site-days/<day>.json` (only when the build wrote them); `forecasts/<day>.csv.gz` and `forecasts/ledger.csv` (when the ledger gains the day's line) and `scores/<day>.csv.gz` (for each day scored); with the content types and the `Cache-Control: max-age=300` that `scripts/publish.sh` sets. Nothing in the code deletes, in either bucket: the site bucket's lifecycle rules are the one thing that removes anything, the earlier versions of rebuilt pages 30 days after each was replaced ("The site's stack", above).

Logs go to the log group `/il-grocery-prices/basket`, kept 30 days. A run ends with one JSON line, its summary (a failed run logs none), then Lambda's `REPORT` line with the duration and `Max Memory Used`. An extraction's summary: `mode`, `chain`, `day`, `run_id`, `files` (the price files in the table, each store's latest), `skipped` (the day's files passed over), `stores`, `rows`, `unreadable_prices` (the rows whose price could not be read, kept with none), `seconds` (the prices table alone, the fetch and the put left out) and `keys`; then `promotions` (the promotion files read, passed over and of stores in no column, the promotions, coupons, gifts and basket rewards, the links dropped, the promotions expired and those before their start, and the table's rows; null when the promotions were not read), `promotions_error` (null, or the error), `columns` (each column's `items`, `wide`, `hole` and `promo_hole`), `promotion_seconds` and `items_seconds`. The site run's: `mode`, `day`, `run_id`, `headline` (the basket's two lines), `unchanged` (the basket's day file), `site_day_unchanged`, `pages` (whether the pages went up), `uploaded` (the data files put, by key, the record files first), `pages_uploaded` (a count), `invalidation` (its id, or null), `record` (the basket record's key), `forecasts` (its status, "frozen", "late", "same" or "none", its SHA-256 and whether it was on time), `scored` (the days scored), `promotions_errors` (by chain), `alerts` and `seconds`: `fetch`, `build` and within it `scoring` and `pass` (the one pass over the history that gives the forecasts and the product pages), `check`, `guard`, `upload` and `total`. Each step also logs a line as it ends, `step <name>: <seconds> s` (as `step fetch: 12.3 s`), so a run refused, or killed at its 900 s, still leaves the seconds of the steps it finished.

### Sizing

The function has 2,048 MB of memory, 10,240 MB of `/tmp` since step one (2,048 MB before it) and 900 s. DuckDB's temp folder is `/tmp/duckdb` and its memory limit 1,200 MB, both set in the function's environment (`DUCKDB_TEMP_DIRECTORY`, `DUCKDB_MEMORY_LIMIT`). `/tmp` holds one chain's price files of the day (and, since step one, its promotion files and its promotions and items tables), the temporary CSV its rows go through, its table and DuckDB's spill folder. All but DuckDB's spill folder are in the run's work folder (`/tmp/basket-<random>`), which the run removes when it ends; a run Lambda kills at its timeout cannot, and Lambda keeps `/tmp` between invocations of one execution environment (https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html, read 2026-11-03), so each run, before it makes its own, removes any `basket-*` folder an earlier run left, and DuckDB's temp folder when it holds anything (spill files a killed run left; the basket code makes the folder again when it next connects to DuckDB), and logs how many of each when there were any. DuckDB's folder is swept only when it is a folder of its own under `/tmp`: a link, `/tmp` itself or a folder elsewhere is left as it is, with a warning. A removal that fails is logged as a warning (`could not remove <path>: <error>`) and the run goes on. On the Mac, Shufersal's extraction, the largest, took 93.9 s and 937 MB at its peak ("Measured on 2026-11-02", above), and its temporary CSV comes to about 480 MB at about 200 bytes a row, about 650 MB of `/tmp` with the day's raw files and the table (`docs/headline-basket-step-two-plan.md`, "Deviations", the first entry).

The site run's `/tmp`, estimates all: every chain's items tables of the day and of the 90 days before it, about 440 MB at full scale on synthetic tables (22 MB for 91 days measured at a twentieth of the scale with `scripts/time_site_run.py --make`, on 9 November 2026), whose names and promotion texts are far shorter than the real ones, so plausibly two to four times that with real rows, about 0.9 to 1.8 GB (UNVERIFIED); about 430 MB of product pages (34,708 at the median of 12,355 bytes, below), drawn into a folder of their own in the work folder and moved into its `site/` (twice that on a morning whose pages are drawn a second time, at the published day's "collected by" time); the day's five prices tables (about 95 MB in all on 2 November 2026: [headline-basket.md](headline-basket.md), "Cost"); and DuckDB's spill folder. So perhaps 1.5 to 3 GB, which is why `/tmp` is 10,240 MB rather than 2,048 (UNVERIFIED until measured). The first manual site run tells whether it fits (a write that finds `/tmp` full fails the run); what it used shows in no log line, so the measure is on the Mac: after the first hand upload's syncs and build ("Deploying step one", step 4), `du -sh data/tables/items` over the days it holds, divided by them and times 91, and `du -sh site/p`. A site run Lambda kills leaves its staged pages inside its work folder, so the next run's start removes them with it.

In Lambda, measured on the first run (2026-11-03, the 2026-11-02 day, by hand): every chain's `rows` equal to the Mac's, and about 1.1 times the Mac's seconds, not the 3 the plan estimated. `Max Memory Used` read 1,121 MB in Shufersal's run, the first in its execution environment, and the same 1,121 MB in every run after it, the basket run included, which all ran in that warm environment: the figure is the environment's peak, so the smaller chains' own peaks are not known beyond being at most that. Shufersal's init, the DuckDB import included, took 0.47 s.

| Run | `rows` | `seconds` (the basket run: `Duration`) | `Max Memory Used` |
|---|---|---|---|
| Shufersal's extraction | 2,322,336 | 102.1 (`Duration` 122.9) | 1,121 MB |
| Rami Levy's extraction | 993,278 | 44.7 (54.3) | 1,121 MB, the same warm environment |
| Osher Ad's extraction | 151,604 | 6.9 (8.3) | same |
| Carrefour's extraction | 1,196,548 | 54.0 (64.0) | same |
| Yochananof's extraction | 476,502 | 20.9 (23.5) | same |
| The basket run | | 6.0 | same |

Step one's measurements, to note here at its manual runs ("Deploying step one", below):

- **Shufersal's extraction, with its promotions and items.** On the Mac, 249.5 s (prices 91.8, promotions 150.9, items 6.3), a peak of 977 MiB resident, DuckDB's temp folder at most 42 MiB and the tables' folders at most 539 MiB, with DuckDB held to 1,200 MB ([shopper-site-plan.md](shopper-site-plan.md), "Deviations", Task 5's review fix round 2 and Task 7): at Lambda's measured 1.1 times, about 275 s of the 900, and about 760 MiB of `/tmp`'s 10,240 MB with the day's raw files. In Lambda, to note: the summary's `seconds`, `promotion_seconds` and `items_seconds`, and the `REPORT` line's `Duration` and `Max Memory Used`. Above about 600 s of the 900, the plan's answer is a promotions run of its own per chain at 12:03, on the owner's word ([shopper-site-plan.md](shopper-site-plan.md), question L).
- **The site run.** On the Mac, over 91 days of synthetic items tables at the full scale of 7 November 2026 (131,035 rows a day, 34,708 covered products), after the speed-ups of the plan's Task 25a: 329.8 s of CPU (538.8 s before them) for the history load, the covered registry, one due day's scoring, the scorecard, the one pass (the forecasts and every product page) and the remaining pages, at a peak of 1,208 MiB resident with DuckDB at the Mac's default limit ([shopper-site-plan.md](shopper-site-plan.md), "Deviations", Task 25a). Not in that figure: the archive fetches, the site check (about 3.0 ms of CPU a page, Task 20: about 104 s for 34,708 pages), the guard and the uploads. The synthetic tables have the real scale but not its shape, and the real count of covered products is not known: more products, more pages. Lambda ran the basket's extractions at about 1.1 times the Mac's seconds (above); for the site run's work its speed against the Mac is UNVERIFIED, so whether the run fits the function's 900 s is not known until the first manual site run. To note then: each `step` line, the summary's `seconds`, and the `REPORT` line's `Duration` and `Max Memory Used`.
- **The pages.** To note at the first manual site run: `pages_uploaded`, and the median and the largest product page. Before it: 24,234 products covered by the items tables of 7 November 2026, the first day's covered set only (the plan's "Deviations", Task 20), so about as many product pages, more as the 90 days fill; product pages on the full-scale synthetic tables a median of 12,355 bytes and at most 23,539 (Task 25a), against the check's cap of 60,000; that day's search pieces 192, 3,239,861 bytes in all, the largest 148,061 bytes against the cap of 150,000 (Task 20).

### Deploying the function (the headline basket's step two)

1. **A second healthchecks.io check,** period 1 day and grace 2 hours, as in step 2 of Deploy, for the basket run alone; copy its ping URL. The basket run pings it: `/start` as it begins, the plain URL with its summary when it succeeds, and `/fail` with the error's name and text (its first 100,000 bytes, a character the cut would split dropped) when anything fails, `MorningNotChecked` included; an event refused as bad sends no ping at all (the `/start` and `/fail` endpoints and the 100 kB limit on a ping's body: https://healthchecks.io/docs/http_api/, read 2026-11-03). A ping that fails is logged as a warning naming its kind (start, success or fail) and never stops the run. The extractions never ping: one that fails shows in the 12:33 run, since step one as a missing prices table, or a missing items table when it stopped after its prices ("What a /fail email means", below). There is no CloudWatch alarm for the basket: a morning with no page, or a failed one, reaches you through this check.

2. **Build and deploy with the basket's schedules off,** on the owner's go, from a clean, committed tree as in step 3 of Deploy. The function's zip is `src/` alone, so the record's `code_sha` is the fingerprint of `src/` that the Mac computes at the deployed commit:

   ```bash
   PYTHONPATH=src .venv/bin/python -c 'from basket.record import code_fingerprint; print(code_fingerprint())'
   ```

   `sam build` now also builds the DuckDB layer from `layer/Makefile` (SAM's makefile build: the target `build-DuckDbLayer`, its output in `$(ARTIFACTS_DIR)`; https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/building-layers.html, read 2026-11-03). It downloads the hash-pinned `duckdb==1.5.6` wheel for Lambda's arm64 Linux from PyPI, so the build needs the network: 18.6 MB, 53 MB unpacked, against Lambda's limit of 250 MB unzipped (https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html). Then deploy with step 3's `sam deploy` command, all nine parameters: the collector's five as they stand (`'ScheduleState=ENABLED'` while the collector is live, `PollScheduleState` as it is), the site stack's bucket and distribution, the second check's URL as `BasketHealthcheckUrl`, and `'BasketScheduleState=DISABLED'`. Pass all nine on every deploy, so no value is left to what the stack held before. In the change set, what is new is the basket's: its function, layer, log group and role, and its six schedules with what SAM adds for them; a change to one of the collector's resources should be one committed since its last deploy.

3. **The function's name,** from the stack's outputs (and `BUCKET` as in step 5 of Deploy):

   ```bash
   BASKET_FN=$(aws cloudformation describe-stacks --stack-name il-grocery-prices --query "Stacks[0].Outputs[?OutputKey=='BasketFunctionName'].OutputValue" --output text --profile flights-sam --region il-central-1)
   ```

### Deploying step one

Each step but the reads writes to AWS and is on the owner's go, in this order ([shopper-site-plan.md](shopper-site-plan.md), "Where step one lands in AWS"), from a clean, committed tree (`git status --porcelain src/` prints nothing) as every deploy.

1. **The budget.** The account's AWS Budget "My Monthly Cost Budget", $5 a month and in no template, goes to $20, the owner's answer to the design's question Q8 ("Cost", above): the owner sets it in the AWS Budgets console.

2. **The collector's stack, the basket's schedules off.** `sam build`, then step 3's `sam deploy` command of Deploy with all nine parameters: `'ScheduleState=ENABLED'` and `PollScheduleState` as they stand, and only `'BasketScheduleState=DISABLED'` changed (always all nine, so no value is left to what the stack held before: Deploy, step 9). Read the change set as Deploy, step 3, reads every deploy's ("On the live stack"): `CollectorFunction` and `BasketFunction` modified, not replaced (both zips are built from `src/`, so adding `src/shopper/` changes both; `BasketFunction`'s `/tmp` also goes from 2,048 to 10,240 MB: "Sizing", above); the DuckDB layer removed and added under a new logical id; every schedule and its role modified, no replacement; and, beyond those, `BasketFunctionRole` modified, its inline policy given the site run's grants (`template.yaml`: the archive's `forecasts/` and `scores/` read, and written once and locked; the site bucket's `site-days/`, `forecasts/` and `scores/` read, and its new pages and those three folders written). No new function, schedule or log group, no layer but the DuckDB one under its new logical id, and nothing on `ArchiveBucket`, `AlertTopic` or the log groups. Anything else: cancel the change set and find out why first. After the deploy, read each schedule's state as Deploy, step 3, does: the basket's six (`BasketFunction…`) must say `DISABLED`, the collector's as they stood. With its schedules off, the basket's healthchecks.io check gets no ping: pause it as Deploy, step 7, describes. From this deploy until the schedules go back on (step 7, below), nothing refreshes the site but the hand upload and the manual site run.

3. **The site's stack, with its lifecycle rules.** The identity check (Deploy, step 1), then the deploy as a change set read before it runs:

   ```bash
   aws cloudformation deploy --template-file site-template.yaml --stack-name il-grocery-prices-site --no-execute-changeset --profile flights-sam --region il-central-1
   aws cloudformation describe-change-set --change-set-name <change set id> --query "Changes[].ResourceChange.[Action, LogicalResourceId, Replacement]" --output table --profile flights-sam --region il-central-1
   aws cloudformation execute-change-set --change-set-name <change set id> --profile flights-sam --region il-central-1
   ```

   The first prints the change set's id (an ARN) and stops; the second shows its changes. What it lists is UNVERIFIED here: no change set for this template change has been read. The template's one change is `SiteBucket` `Modify`, `Replacement` `False`: its `LifecycleConfiguration` added. CloudFormation may also list the two resources that reference the bucket, `SiteBucketPolicy` (`!Ref SiteBucket` and the bucket's ARN) and `SiteDistribution` (`!GetAtt SiteBucket.RegionalDomainName`), as `Modify` with no property change of their own, as it listed the 23 schedules whose function changed on 2026-11-07 (Deploy, step 3): such rows, with `Replacement` `False`, are expected. `SiteBucketPolicy`'s row may read `Replacement` `Conditional` instead (UNVERIFIED): its `Bucket` is `!Ref SiteBucket`, a property set only when the policy is created (`createOnlyProperties` in the `AWS::S3::BucketPolicy` resource schema, as cfn-lint 1.57.1 bundles it for il-central-1), and a change to such a property whose value comes from a `Ref` or `Fn::GetAtt` (`RequiresRecreation` `Always`, `Evaluation` `Dynamic`) reads `Conditional` (botocore 1.43.106's CloudFormation model, `ResourceChange.Replacement`). Then read that row's details:

   ```bash
   aws cloudformation describe-change-set --change-set-name <change set id> --query "Changes[?ResourceChange.LogicalResourceId=='SiteBucketPolicy'].ResourceChange.Details" --profile flights-sam --region il-central-1
   ```

   Executing it is then the owner's call, and only when all three hold: every detail reads `Evaluation` `Dynamic` with `SiteBucket` as its `CausingEntity` (or one of its attributes, written after it: the form UNVERIFIED here); no detail's `ChangeSource` is `DirectModification`; and `SiteBucket`'s own row reads `Replacement` `False`. Any other resource, any `Add` or `Remove`, a `Replacement` of `True` on any row, or `Conditional` on any other row or with other details: do not execute it, and find out why first. A stop here comes after step 2 switched the basket's schedules off, so nothing refreshes the live site until the steps go on. Once the change set is executed (the first block's third command), the lifecycle rules expire each earlier version of a rebuilt page 30 days after it was replaced ("The site's stack", above). The first to go are the basket's `index.html` and `method.html`, replaced every morning since the basket's schedules went on: their versions replaced 30 days or more before this deploy go soon after it, the rest as each turns 30 days old (S3 applies lifecycle rules in the background; how soon after the 30 days, UNVERIFIED here).

4. **The first hand upload** ("The shopper site, by hand", above): for each day from 2026-11-01, the collector's first, to today that has a check record in the archive (`aws s3 ls "s3://$BUCKET/checks/" --profile flights-sam --region il-central-1` lists them), the sync and the extraction (steps 1 and 2). Leave a day without one out, with no items table of its own under `data/tables/items/`: the backfill (step 5) refuses it, so the site run reads it as a hole, and extracted on the Mac alone it would give the site run other numbers than the hand upload's at step 6 (`RevisionNeeded`, the items tables read being among the numbers compared). Then today's build, check and review (steps 3 to 5); then `scripts/publish.sh` on the owner's go after the Nevo date check (step 6). Open the printed address, and fetch `site-days/<today>.json` from it. From a column's 30th day of records (about 30 November 2026, counting from 1 November: [shopper-site.md](shopper-site.md), "Changed after the survey"), a daytime build stops (`NotFrozenYet`, step 3): then build after midnight, or run steps 5 and 6 below first and sync again.

5. **The backfill,** in Lambda: an extraction per chain for each day from 2026-11-01 to yesterday, so the archive holds the items tables the site run reads. Each is the extraction command of "The manual runs" (below) with that day put in its payload, started as there; a day's five may also start together, as the 12:03 schedules start them. Read each summary before the next day's. A day with no check record in the archive is refused (`MorningNotChecked`) and stays a hole. Where the archive already holds the day's prices table (the basket's own extraction ran for it), each extraction replaces it with one of the same rows, which the archive keeps as an earlier version ([headline-basket.md](headline-basket.md), "Cost"); for a day it lacks, the extraction writes the first.

6. **The manual site run,** today: today's five extractions, then the site run ("The manual runs", steps 1 and 2, today's day in each payload). Expected: `"unchanged": true` and `"site_day_unchanged": true` (the hand upload's day and site-day files unchanged, which holds when steps 4 and 5 extracted the same days), `"pages": true` with the pages' count in `pages_uploaded`, and an invalidation's id. Note the measured seconds and memory in "Sizing", above. Any other answer: read it as "What a /fail email means", below.

7. **The schedules on,** on the owner's go: "Turning it on", below, `'BasketScheduleState=ENABLED'` the only switch changed.

### The manual runs

One manual run per step, on the owner's go (each writes to AWS), on a day already published that is the site's latest, so the answer is known in advance: the day's numbers unchanged. The site's latest day is the last of its day files and site-day files:

```bash
SITE_BUCKET=$(aws cloudformation describe-stacks --stack-name il-grocery-prices-site --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text --profile flights-sam --region il-central-1)
aws s3 ls "s3://$SITE_BUCKET/days/" --profile flights-sam --region il-central-1
aws s3 ls "s3://$SITE_BUCKET/site-days/" --profile flights-sam --region il-central-1
```

The commands below name 2026-11-02, the first day published by hand; put the site's latest day in its place (or, for the backfill, the day to extract).

1. **The five extractions,** each the scheduled event with the day added. Start each asynchronously (`--invocation-type Event`), the way the schedules do: Shufersal's took 249.5 s on the Mac with its promotions and items, and a plain invoke the CLI gives up on after 60 seconds is sent again (step 6 of Deploy), starting a second extraction of the same chain. Start them one at a time and let each finish before the next, which keeps the logs readable:

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

   Read its summary's `rows` (for 2026-11-02, against the Mac's in "Measured on 2026-11-02", above), `seconds`, `promotion_seconds`, `items_seconds` and `promotions_error`, and the `REPORT` line's `Max Memory Used` against the function's 2,048 MB; note them in "Sizing", above. A run with no summary line failed: read the lines before its `REPORT` line.

2. **The site run,** once the five have finished: the scheduled event with the day added, its `collected_by` the extractions' time as the schedule sends it. A plain invoke, so the answer file holds the run's summary; `--cli-read-timeout 900` keeps the CLI waiting rather than sending it again, which would start a second run of the day:

   ```bash
   aws lambda invoke --function-name "$BASKET_FN" --payload '{"mode": "basket", "day": "2026-11-02", "collected_by": "12:03"}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-basket.json --profile flights-sam --region il-central-1
   ```

   On a day already published that is the site's latest, the expected answer in `/tmp/il-grocery-basket.json` is `"unchanged": true`, `"site_day_unchanged": true` and `"pages": true`: the numbers equal the published ones (B12 leaves the run id, the code fingerprint, the build time and the "collected by" time out of the comparison), so the day files stay as published and the pages go up, drawn from them, their "collected by" time included; `uploaded` lists the data files put, by key (none when the day's are all published already), `pages_uploaded` counts the pages, and `invalidation` gives an id. Then open the site's address and see the day's pages, and read the record and its lock:

   ```bash
   aws s3 ls "s3://$BUCKET/basket/date=2026-11-02/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/basket/date=2026-11-02/basket-<run id>.json" - --profile flights-sam --region il-central-1
   aws s3api head-object --bucket "$BUCKET" --key "basket/date=2026-11-02/basket-<run id>.json" --query "[ObjectLockMode, ObjectLockRetainUntilDate]" --profile flights-sam --region il-central-1
   ```

   The record's `code_sha` is the deployed commit's (step 2 of "Deploying the function"), and the lock reads `GOVERNANCE` with a date ten years on. On healthchecks.io the second check shows the run's pings. From that ping on it expects the next within a day and two hours; if the schedules will not be on by then, pause it as step 7 of Deploy describes. Any other answer is a failure: read it as below ("What a /fail email means").

### Turning it on

On the owner's go: step 3's `sam deploy` command with all nine parameters again and `'BasketScheduleState=ENABLED'`, the other two switches as they stand (`'ScheduleState=ENABLED'` while the collector is live, `PollScheduleState` as it is), only that one switch changed. The next morning, after the site run's time, check:

- the log group `/il-grocery-prices/basket`: six summary lines, the five extractions' and the site run's;
- the record under `basket/date=<day>/` (`aws s3 ls` as above);
- the success ping on the second healthchecks.io check, or its `/fail` ("What a /fail email means", below);
- the date on the site's front page and on a product page: the day's; and `site-days/<day>.json` on the site.

To turn the site run off, deploy again with `'BasketScheduleState=DISABLED'`, the other two switches as they stand (`'ScheduleState=ENABLED'` while the collector is live, `'PollScheduleState=ENABLED'` while the polls are), only that one switch changed; the collector's schedules follow `ScheduleState` and, for the polls, `PollScheduleState`. The hand build ("The shopper site, by hand", above) stays for revising the site's latest day and for the latest day when the morning's run did not publish it.

### Measured later

- **The share of covered products with a promotion run in their first 90 days**, once 90 days of records exist (from about 30 January 2027, counting from 1 November 2026): one of the design's step-one measurements ([shopper-site.md](shopper-site.md), "Order of building", step 1), read from the archive's items tables, read-only, and written here then.

### What a /fail email means

The second check emails when the site run pings `/fail`, or when no ping arrives in time. The ping's body is the error's name and text; or, for a run that published with alerts, `SiteAlert: the site went up, and:`, then a line per alert, then the run's summary. Then read the log group `/il-grocery-prices/basket` around the site run's time.

- `SiteAlert`, the site up, with one or more of these lines:
  - `promotions not read: <chain>: <message>`: the chain's promotion files changed format, or one did not read (P10). The line carries the extraction's whole message, which names, by kind: for a level whose fields changed, or an element out of its place, the file and the fields added and missing (or the element); for a code or a `ClubID` form not seen before, or an `IsGiftItem` that is not a quantity, the field and the value; for a date or an amount that does not read, or a `MinQty` or minimum spend the tables cannot hold, the field and the value; for a promotion file that does not read, the file and what is wrong with it (cut short, not XML, not parsing). The alert reaches the owner alone, in the healthchecks.io email; the public site-day file says only the error's kind ("format changed" or "file not read"), the file when the message names one and the field when it is a known one, never a value (`shopper.siteday.public_error`). The pages went up with every section of the chain's columns saying "Promotions from <chain>'s files could not be read today.", its prices and items as every day, and the day is a promotion hole for each of its columns. To read the new format, sync the day, extract the chain's tables of it (`PYTHONPATH=src .venv/bin/python -m shopper.extract --data data --day <day> --chains <slug>`: the survey reads the day's prices table, which a format change does not stop), then run the survey for the chain at the terminal (`PYTHONPATH=src .venv/bin/python -m shopper.survey --data data --day <day> --chain <slug>`, as "Measured for the shopper site" ran it, above). A new field set, code or value form goes into the chain's constants in `src/shopper/promotions.py` (`KNOWN_FIELDS`, `REWARD_TYPES`, `DISCOUNT_TYPES` and the others) only on the owner's word. A file that does not read: find it in the day's manifests (its size and SHA-256) before anything else.
  - `scores differ, the stored file kept: <message>`: the archive holds a day's scores file whose rows are not the ones this run made, both SHA-256s named. The stored file is the record and went up as it is. Find out why before the next change: a rescoring is a second file beside the first, a tool the plan leaves to the first fix that needs one ([shopper-site-plan.md](shopper-site-plan.md), "Where the design leaves room").
  - `out of reach, never scored: <days>`: frozen days whose 14 days the run's 90-day read no longer holds, so the site run never scores them (they stay without a summary, so a longer read could still score them: `shopper.score`); each day is alerted once, on the morning it goes out of reach. Their scoring was missed while it could be done: read the site runs of the days after them.
- `MorningNotChecked`: the collector's check has not written its record for the day: it has not run, or it failed. Read `/il-grocery-prices/collector` around the check's time, and the collector's own healthchecks.io check. Once the check has written its record, run the day's five extractions and its site run by hand ("The manual runs", above): the extractions refused the day too.
- `MissingTable`: it names the chain and the table's key: the chain's prices table of the day, when its extraction did not run or did not finish; or its items table, when its extraction stopped after the prices table (a chain with no store list, or a failure in its promotions or items step). One chain's missing table stops the site run for all five chains. Read that extraction in the log group around 12:03, then run it and the site run again by hand.
- `NoStoreList`: it names the chain that has no store list on the day or any of the 13 days before it. The build stopped before it wrote the record, so there is none, and nothing went up. Look under the chain's `raw/chain=<slug>/` in the archive bucket for a `Stores` file of those days, and read `/il-grocery-prices/collector` for the chain's runs. Once the collector has stored a store list, run the chain's extraction and the site run again by hand.
- `RevisionNeeded`: the day's site-day file or its basket day file is published with other numbers, and the error names what differs: a code or rule change moved a published number. Nothing went up, and the run kept its record; the day's forecasts file and any scores due may already be in the archive, written once, and a rerun meets them as the same. When the new numbers are right, revise the day by hand: sync, build with `--revise` and a one-line reason ("Revising a day", above), check, review and publish. The hand build takes the day's forecasts file only once the published ledger names it (`NotSynced` otherwise).
- `ForecastsDiffer`: the archive holds a forecasts file of the day whose rows are not the ones this run made. Every row names the code fingerprint it was frozen with (`code_sha`, the fingerprint of `src/`), so a change under `src/` since the day was frozen is enough. Nothing went up. Rerun the site run at the commit that froze the day: find it by the file's `code_sha` (check out a candidate commit and compare its fingerprint, as "Deploying the function", step 2, prints it), deploy it (step 3's `sam deploy` command of Deploy with all nine parameters, as every deploy), run the site run of the day by hand, then deploy the current commit again. Both functions are built from `src/`, so that deploy rolls the collector's code back to that commit too: every collector run until the current commit is deployed again runs the old code. A hand build can then put up pages from the later code, with `--revise` and a one-line reason when its numbers differ.
- `RecordsNotUploaded`: the upload of the day's forecasts file or of a scores file failed, before anything that names it went up. Run the site run of the day again by hand: it puts the archive's same record files first, then the ledger, the day files and the pages.
- `SiteCheckFailed`: the built site failed the site check (`shopper.check`) or the publish guard (`shopper.guard`); the error lists the problems, one a line. Nothing went up. Fix the cause before the day is built again.

A manual site run for a day earlier than the site's latest writes that day's files (when the site has none for it) and its record, and leaves the pages to the site's latest day; so a day the morning missed can also be run by hand in Lambda, its five extractions first.

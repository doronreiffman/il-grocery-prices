# Operating the collector

How to deploy the collector, run it by hand, read what it wrote, clear a stopped chain, drop a chain, and what it costs; then how to build and publish the headline basket by hand, and how the basket function does it every morning. What the collector does and why: [collector.md](collector.md); each portal's mechanics: [portals.md](portals.md).

## What runs when

One Lambda function (stack `il-grocery-prices`, region il-central-1, Tel Aviv) runs on 17 daily schedules in Israel time, so daylight saving needs no handling:

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

A run can take up to 15 minutes (Lambda's longest), so Shufersal's runs start 15 minutes apart and one chain never gets two requests at once. Shufersal collects its store list and full files only (owner, 2026-11-01): its listing pages took 15 to 39 s each from AWS that day (medians 25 to 35 s), a full kind took two runs, and its update files come out every hour, so they wait for a polling run. Its second run of a full kind picks up where the first stopped instead of re-reading the pages the first already read: it reads the day's earlier manifests, then page 1, then the furthest page the first run read, again, and on to the last page ([shufersal-resume.md](shufersal-resume.md), ruling R37). Rami Levy, Osher Ad and Yochananof share one portal host (`url.publishedprices.co.il`), so their runs start at least 15 minutes apart, and their sessions never overlap. Osher Ad's files are stamped from about 07:00 to 09:00, most at 08:00 and the store list at 08:05 (on 2026-11-02), so its main run starts at 08:18. A retry run fetches only what is still not stored. The check starts after the last retry run can have finished; it writes a check record, emails when a chain's morning is incomplete, a chain is stopped or a retry run failed, and pings healthchecks.io. A chain's retry runs fail when none covered one of the kinds the chain collects, when one ended with an error, or when together they listed nothing for the day and none was blocked (`the retry runs listed nothing for the day (unparsed names: N)`): a portal that renames its files so that none can be read, or dates them all another day, ends its runs without an error, and this alert is how it shows. They fail too when no run that day, main or retry, listed a full kind the chain collects (`no run listed a PriceFull for the day`, or `a PromoFull`) and no retry run was blocked: the retry runs' names are taken together, so a Shufersal morning with no PriceFull at all would otherwise pass on its Stores run's names. A day a chain publishes nothing at all alerts the same way. The design gave 10:00 for the check; it is at 11:48 because the last retry run (Osher Ad's) starts at 11:18 and may run until 11:33, and 15 minutes more leave room for its manifest write and the schedulers' start-up lag. A retry run that runs out of time (`"error": "stopped: under 90 s left"`) is a failed run even with nothing missing, since it may not have read the whole list, and a name it never reached is missing without showing as missing: on a kind already read in full, a retry makes a fresh pass of its 21 pages within about 810 s, so on a day the pages average more than about 38 s (2026-11-01: 15 to 39 s, medians 25 to 35) it runs out of time. The one exception (ruling R36, as ruling R37 amends it): each kind the stopped retry covers was read in full that day, every name the retry listed was listed by another run that read that kind, and the chain has nothing missing. Then the retry is not a failed run: no email goes, and the check record names it under `short_of_time`. A kind is read in full when the listing pages the day's runs read, as their manifests record them, join up from page 1 to the last page; a run of a chain that records no pages (every chain but Shufersal) reads its kinds in full when it ended with no error and was not blocked. The runs that vouch for the retry's names are any run that read the whole list on its own and, when the other runs' pages join up into a full reading without the retry's own, each run whose pages carry that reading further along the list than the pages joined before them (the reading is joined from the front of the list; among pages that start at the same place, the furthest-reaching are joined first). A run that read only part of the list, where other runs' pages already cover that part, vouches for no name, and the retry never vouches for itself. On a day the runs did not read the kind in full, or the stopped retry listed a name no such run did (a run made before the day's files were all up lists only what was up), the alert still goes, and it is the sign that the morning fell short. When the pages of a Shufersal full kind do not join up, the failed alert says so and names the pages no run read, for example `the PriceFull list was not read in full: pages 17 to 21 never read` (a page a run read only part of is named apart: `page 19 read in part`); it does not when a retry run was blocked, which the stopped alert covers.

Neither the schedules nor Lambda retry a failed invocation: the retry run is the retry. A block (a 401, 403 or 429, a captcha or verification page, or an HTML page where a file belongs) stops that chain until you clear it (below).

A second function in the same stack, the headline basket's, runs six schedules of its own after the check, on a switch of its own ("The headline basket, every morning", below).

Where things land in the bucket:

- `raw/chain=<chain>/date=YYYY-MM-DD/<file name as published>`: the files, byte for byte, locked for ten years (governance mode). A different file under a stored name is kept beside it with 12 hex digits of its SHA-256 added to the name.
- `manifests/date=YYYY-MM-DD/<chain>-<run id>.json`: one per run, locked.
- `checks/date=YYYY-MM-DD/check-<run id>.json`: one per check, locked.
- `state/<chain>.json`: the chain's stopped latch, plain and rewritable.

The date is an Israel date: for a raw file the one in its name, for a manifest or check record the day the run was for. A run id is `<HHMMSS>Z-<mode>-<4 hex>`, the start time in UTC. Logs go to the log group `/il-grocery-prices/collector`, kept 30 days.

## Deploy

You need the personal AWS account (nothing from an employer) with il-central-1 enabled, the AWS CLI and the AWS SAM CLI as flights-archive uses them, and Python 3.13 on your Mac for `sam build` (or `sam build --use-container` with Docker). Every `aws` and `sam deploy` command below names the `flights-sam` profile and the region: every other profile on this Mac is the employer's, and a command without `--profile` would run against one of them.

1. **Account check.** Sign in as for flights-archive (`aws login --profile flights`), then:

   ```bash
   aws sts get-caller-identity --profile flights-sam --region il-central-1
   ```

   It must show account `137953273942` and a user ARN ending in `user/doron-admin`. Anything else: stop.

2. **healthchecks.io.** Create a check with period 1 day and grace 2 hours, and copy its ping URL (`https://hc-ping.com/<uuid>`). The 11:48 check pings it each morning; when no ping arrives, healthchecks.io emails. That catches a morning where nothing ran at all. Create a second check the same way for the basket run; its URL is `BasketHealthcheckUrl` ("The headline basket, every morning", below).

3. **Build and deploy with the schedules off.** Deploy from a clean, committed tree (`git status --porcelain src/` prints nothing): every manifest and check record carries `code_sha`, a fingerprint of `src/collector/`, and only a committed tree lets you find the commit behind it (step 8). The values go on the command line, never into a file in the repo; don't use `sam deploy --guided`, which offers to save them to `samconfig.toml` (that file is gitignored as a second guard).

   ```bash
   sam build
   sam deploy --profile flights-sam --region il-central-1 --stack-name il-grocery-prices \
     --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset --parameter-overrides \
     'UserAgent="il-grocery-prices/0.1.0 (+https://github.com/<you>/il-grocery-prices; <email>)"' \
     'AlertEmail=<email>' \
     'HealthcheckUrl=https://hc-ping.com/<uuid>' \
     'ScheduleState=DISABLED' \
     'SiteBucketName=il-grocery-prices-site-sitebucket-<suffix>' \
     'SiteDistributionId=<distribution id>' \
     'BasketHealthcheckUrl=https://hc-ping.com/<basket uuid>' \
     'BasketScheduleState=DISABLED'
   ```

   The inner double quotes around the User-Agent matter: `--parameter-overrides` splits on spaces, and without them the value is cut at the first space (the template refuses a value without `+https://` and an `@`, which catches that). Review the change set and confirm. The site's bucket and distribution are the site stack's outputs `SiteBucketName` and `SiteDistributionId` ("The two gates", step 1, below), so that stack is deployed first; the template refuses a bucket whose name does not start `il-grocery-prices-site-sitebucket-`, so the archive bucket can never be given for it. `BasketScheduleState` is the basket function's own switch; `sam build` also builds its DuckDB layer ("The headline basket, every morning", below).

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

   A Shufersal run also logs one line for each listing page it reads, before taking the page's files: `shufersal PriceFull page 7 of 21: 20 rows in 41.2 s` (the page count is the last page this run's page 1 named; `?` for a detour read before page 1).

   A good run has `"blocked": null`, `"error": null` and `"failed": 0`. A run that ran short of time ends with `"error": "stopped: under 90 s left"`; start the same event again (or the retry event, `"mode": "retry"`): stored files are skipped, so it carries on where the first stopped. Carrefour's first run decides whether it stays (below).

   **Shufersal's full files take two runs each.** The first run of a full kind usually ends with `"error": "stopped: under 90 s left"`; the second, the same event again, picks up where the first stopped (page 1, then the first run's furthest page again and on) and finishes. If the second stops short too, start it a third time; it picks up where the second stopped. On 2026-11-01 its pages took 15 to 39 s each, and a day much slower than that needs more runs. (The duration gate this step once held is gone: at that page speed one kind alone does not fit a run.)

7. **A manual check.** The check is short, so a plain invoke is fine; `--cli-read-timeout 900` keeps the CLI waiting rather than sending it again, which would check twice and could email twice:

   ```bash
   aws lambda invoke --function-name "$FN" --payload '{"mode": "check"}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-check.json --profile flights-sam --region il-central-1
   ```

   `/tmp/il-grocery-check.json` names the check record (`record`) and counts the alerts. The check pings healthchecks.io, which should show the ping within a minute. healthchecks.io measures a check's period from its last ping (the worked example on https://healthchecks.io/docs/, read 2026-11-01), so from that ping on it expects the next within a day and two hours. If the schedules will be on before then (step 9), leave the check running: the first scheduled check pings in time. If not, pause it: pausing is how its docs say to avoid unwanted alerts (same page; that a paused check sends none is implied, not stated). A ping normally takes a paused check out of pause: "Normally, when you ping a paused check, it leaves the paused state and goes into the 'up' state" (https://healthchecks.io/docs/configuring_checks/). The exception is on the same page: a check whose filtering rule for pinging a paused check is set to "Ignore the ping, stay in the paused state" stays paused, ignoring every ping, until it is resumed by hand. Leave that rule unset, and a manual check run while the check is paused un-pauses it. It also expects the day's retry runs: with none run that day, it reports each chain as failed ("the day's runs fell short: no retry run covered …") and emails you, which proves the email works. For a clean check, first run each retry event of the timetable (one per chain, Shufersal's one per kind) by hand, one at a time as there; each downloads only what is still missing. Do this only once that day's files are on the portals (step 6): the check fails a chain whose retry runs list nothing for the day, so a retry started too early makes the manual check alert every chain.

8. **Read what it wrote.** List a day's manifests, print one, and print the check record:

   ```bash
   aws s3 ls "s3://$BUCKET/manifests/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/manifests/date=YYYY-MM-DD/<chain>-<run id>.json" - --profile flights-sam --region il-central-1
   aws s3 ls "s3://$BUCKET/checks/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/checks/date=YYYY-MM-DD/check-<run id>.json" - --profile flights-sam --region il-central-1
   ```

   A manifest holds: `listed` (that day's file names the listing gave, of the kinds asked for), `files` (each stored or found stored, with `outcome` `stored`, `exists` or `conflict`, `size` and `sha256`), `failed` (tried and not stored, with why), `not_attempted` (listed, never tried because the run stopped), `unparsed` (listed names that could not be read), `listing_read_at` (null when the listing was never read), `blocked`, `error`, `code_sha`, and `pages`: empty for every chain but Shufersal, whose runs record each listing page they read, in the order read, with `kind`, `page`, `rows`, `first` and `last` (the first and last file name on the page as listed, without `.gz`, any date), `last_page` (the last page the page's pager names, null when it names none), `seconds` (the request's time, rounded to 0.1 s, the 0.5 s pause before it included, except on the run's first request, which has none), `in_order` (false when the page's names are out of order, or its first name sorts before the last name of the page numbered one less read just before it) and `taken_through` (the last name the run took from the page, or the page's last name once the run took the last row the page gave; null for a page it took nothing from, such as one it stepped back from). "The store published nothing" shows as a store with no file in `listed` (coverage counts those); "listed but not stored" as a name in `listed` that the bucket does not hold (the check record's `missing`). Only the second is the collector's failure.

   A check record holds, per chain: `manifests` (how many runs), `listed` and `stored` counts, `missing` (every listed name not stored), `stopped` (since when and why, or null), `failed` (why the retry runs fall short, or null), `short_of_time` (each retry run that stopped short of time on a day its kinds were read in full, every name it listed was listed by another run that read that kind, and nothing is missing, as `<run id> (<kinds>)`: not a failed run, and no email), `read_in_full` (for each full kind the chain collects, the ids of the runs that read it in full: the clean runs of a chain that records no pages, and Shufersal's runs whose pages make up the joined full reading, a run that adds nothing to it, such as a second whole pass, not named; with a page out of order that day, each Shufersal run that read every page in one go; null when the kind was not read in full) and `coverage` (stores with that day's full price file against the stores in the latest store list: `published`, `expected`, `ratio`, or `"unknown"` with a `note`); then `alerts`, `run_id`, `checked_at` (UTC) and `code_sha`.

   Check that a stored file is locked:

   ```bash
   aws s3 ls "s3://$BUCKET/raw/chain=ramilevy/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3api head-object --bucket "$BUCKET" --key "raw/chain=ramilevy/date=YYYY-MM-DD/<file name>" --query "[ObjectLockMode, ObjectLockRetainUntilDate]" --profile flights-sam --region il-central-1
   ```

   It should show `GOVERNANCE` and a date ten years on. To find the commit behind a `code_sha`, check out a candidate commit and run `PYTHONPATH=src .venv/bin/python -c 'from pathlib import Path; from collector.handler import code_sha; print(code_sha(Path("src/collector")))'`.

9. **Turn the schedules on**, on the owner's go: the same `sam deploy` command with all eight parameters again and `'ScheduleState=ENABLED'`. Always pass all eight, so no value is left to what the stack held before. If the healthchecks.io check is paused, the first scheduled check's ping normally takes it out of pause (step 7); see on healthchecks.io that it did. The next morning, read the manifests and the check record, and see the 11:48 ping on healthchecks.io. To turn them off, deploy again with `'ScheduleState=DISABLED'`.

## A stopped chain

The commands here use `FN` and `BUCKET` as set in step 5 of Deploy. A block stops the chain: its state file says `stopped`, with when and why, and every later run of that chain does nothing (its manifest says `"blocked": "stopped earlier"`). The next check emails once; later checks stay quiet about it until you clear it. Read why in the email, the manifest's `blocked`, or the state file:

```bash
aws s3 cp "s3://$BUCKET/state/ramilevy.json" - --profile flights-sam --region il-central-1
```

Find out why the portal refused before anything else. Never switch to a browser User-Agent, another IP, a proxy or any other way around a block. One refusal is not a block: a 403 from Shufersal's file host (`pricesprodpublic.blob.core.windows.net`) once a link has expired makes the collector read the listing again for a fresh link, once.

Not every stop is a refusal. The NCR portal (Rami Levy, Osher Ad, Yochananof) sends a visitor without a session to its login page, so a session that ends in the middle of a run should answer the next download with that page. The collector reads it as "HTML where a file belongs" and stops the chain: the reason reads `<file name>: HTML where a file belongs`, and the same run's manifest shows files stored before it. Read the reason and the manifest; when they point to an ended session and not to a refusal, unblock the chain (below).

When the cause is sorted out, clear the latch (here Rami Levy; use the stopped chain's name from the table above):

```bash
aws lambda invoke --function-name "$FN" --payload '{"mode": "unblock", "chain": "ramilevy"}' --cli-binary-format raw-in-base64-out /tmp/il-grocery-unblock.json --profile flights-sam --region il-central-1
```

`/tmp/il-grocery-unblock.json` shows the state it cleared (`was`). The chain's next scheduled run collects again; or start one by hand as in step 6.

## Carrefour from il-central-1

Carrefour is reported to refuse visitors from outside Israel; whether AWS's Tel Aviv addresses get through is unknown until its first run from the stack. If that run is blocked, drop Carrefour (below) and record it in the project notes. Never another route to it.

## Dropping a chain

1. Delete the chain's schedules from `template.yaml`: its main and retry events (Shufersal has five main and three retry).
2. Delete its entry in `CHAINS` in `src/collector/chains.py`.
3. Bring the tests in line: its rows in the `SCHEDULES` table in `tests/test_template.py`, its manual-run line in this file (step 6), its cases in `tests/test_chains.py`, and any mutation in `scripts/mutation_check.py` that quotes it. Run the tests, cfn-lint and the mutation check (below).
4. Commit, then deploy as in step 3 of Deploy, with the same eight parameters.

Its stored files stay, locked; so does its state file. The check stops looking at it, since it checks only the chains in `CHAINS`.

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

Estimates from [collector.md](collector.md), "Cost":

- **Volume:** Shufersal's full files were about 162 MB on 2026-10-31 (measured from its listing); the other four chains have fewer stores. About 250 to 300 MB a day, so 8 to 9 GB a month.
- **S3 storage** at $0.025 per GB-month (il-central-1): about $0.25 the first month, about $2.70 a month after a year. Nothing is deleted (every file is locked for ten years), so storage grows every month; moves to colder storage wait until the bucket passes about 50 GB.
- **S3 writes:** about 2,000 a day at $0.0055 per 1,000: about $0.35 a month.
- **Lambda:** a few invocations of up to 15 minutes a day, inside the monthly free tier. The worst case, all 16 collecting runs and the check running the full 15 minutes at 512 MB, is 7,650 GB-seconds a day, about 230,000 a month.
- **S3 reads:** each Shufersal run lists the day's Shufersal manifests once and reads each earlier one: on the eight scheduled Shufersal runs, 8 listings and 28 reads a day, about 1,100 requests a month, under $0.01 a month if they cost no more than the writes above.
- **Total:** about $1 to $3 a month in the first year.

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

   `sam build` now also builds the DuckDB layer from `layer/Makefile` (SAM's makefile build: the target `build-DuckDbLayer`, its output in `$(ARTIFACTS_DIR)`; https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/building-layers.html, read 2026-11-03). It downloads the hash-pinned `duckdb==1.5.6` wheel for Lambda's arm64 Linux from PyPI, so the build needs the network: 18.6 MB, 53 MB unpacked, against Lambda's limit of 250 MB unzipped (https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html). Then deploy with step 3's `sam deploy` command, all eight parameters: the collector's four as they stand (`'ScheduleState=ENABLED'` while the collector is live), the site stack's bucket and distribution, the second check's URL as `BasketHealthcheckUrl`, and `'BasketScheduleState=DISABLED'`. Pass all eight on every deploy, so no value is left to what the stack held before. In the change set, what is new is the basket's: its function, layer, log group and role, and its six schedules with what SAM adds for them; a change to one of the collector's resources should be one committed since its last deploy.

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

On the owner's go: step 3's `sam deploy` command with all eight parameters again and `'BasketScheduleState=ENABLED'`. The next morning, after the basket run's time, check:

- the log group `/il-grocery-prices/basket`: six summary lines, the five extractions' and the basket run's;
- the record under `basket/date=<day>/` (`aws s3 ls` as above);
- the success ping on the second healthchecks.io check;
- the page's date on the site: the day's.

To turn the basket off, deploy again with `'BasketScheduleState=DISABLED'`; the collector's schedules follow `ScheduleState` alone. The hand build ("The headline basket, by hand", above) stays for revising a day and for a day the morning missed.

### What a /fail email means

The second check emails when the basket run pings `/fail`, or when no ping arrives in time. The ping's body is the error's name and text; then read the log group `/il-grocery-prices/basket` around the basket run's time.

- `MorningNotChecked`: the collector's check has not written its record for the day: it has not run, or it failed. Read `/il-grocery-prices/collector` around the check's time, and the collector's own healthchecks.io check. Once the check has written its record, run the day's five extractions and its basket run by hand ("The manual runs", above): the extractions refused the day too.
- `MissingTable`: it names the chain whose table of the day is missing, and the table's key: that chain's extraction did not run or did not finish. Read that extraction in the log group around the extraction's time, then run it and the basket run again by hand.
- `NoStoreList`: it names the chain that has no store list on the day or any of the 13 days before it. The build stopped before it wrote the record, so there is none, and nothing went up. Look under the chain's `raw/chain=<slug>/` in the archive bucket for a `Stores` file of those days, and read `/il-grocery-prices/collector` for the chain's runs. Once the collector has stored a store list, run the basket run again by hand.
- `RevisionNeeded`: the day is published with other numbers, and the error names what differs: a code or rule change moved a published number. The run published nothing and kept its record. When the new numbers are right, revise the day with a hand build given `--revise` and a one-line reason ("Revising a day", above), then check, review and publish as there.
- `SiteCheckFailed`: the built page failed the word check (`basket.check`) or the published-day guard (`basket.guard`); the error lists the problems, one a line. Nothing went up. Fix the cause before the day is built again.

A manual basket run for a day earlier than the site's latest writes that day's file (when the site has none for it) and its record, and leaves the front page to the site's latest day; so a day the morning missed can also be run by hand in Lambda, the five extractions first.

# Operating the collector

How to deploy the collector, run it by hand, read what it wrote, clear a stopped chain, drop a chain, and what it costs. What the collector does and why: [collector.md](collector.md); each portal's mechanics: [portals.md](portals.md).

## What runs when

One Lambda function (stack `il-grocery-prices`, region il-central-1, Tel Aviv) runs on 17 daily schedules in Israel time, so daylight saving needs no handling:

| Israel time | Run | Event |
|---|---|---|
| 06:30 | Shufersal store list | `{"mode": "main", "chain": "shufersal", "kinds": ["Stores"]}` |
| 06:33 | Rami Levy, every kind | `{"mode": "main", "chain": "ramilevy"}` |
| 06:39 | Carrefour, every kind | `{"mode": "main", "chain": "carrefour"}` |
| 06:45 | Shufersal full price files | `{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}` |
| 06:48 | Osher Ad, every kind | `{"mode": "main", "chain": "osherad"}` |
| 07:00 | Shufersal full price files, carrying on | `{"mode": "main", "chain": "shufersal", "kinds": ["PriceFull"]}` |
| 07:03 | Yochananof, every kind | `{"mode": "main", "chain": "yochananof"}` |
| 07:15 | Shufersal full promotion files | `{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}` |
| 07:30 | Shufersal full promotion files, carrying on | `{"mode": "main", "chain": "shufersal", "kinds": ["PromoFull"]}` |
| 09:30 to 10:15 | One retry per chain, Shufersal's one per kind, three hours after that kind's first morning run | the main events with `"mode": "retry"`: Shufersal at 09:30 (Stores), 09:45 (PriceFull) and 10:15 (PromoFull) |
| 10:45 | The check | `{"mode": "check"}` |

A run can take up to 15 minutes (Lambda's longest), so Shufersal's runs start 15 minutes apart and one chain never gets two requests at once. Shufersal collects its store list and full files only (owner, 2026-11-01): its listing pages took 15 to 39 s each from AWS that day (medians 25 to 35 s), a full kind took two runs, and its update files come out every hour, so they wait for a polling run. Its second run of a full kind reads the listing from page 1 again, skips what the first stored and carries on. Rami Levy, Osher Ad and Yochananof share one portal host (`url.publishedprices.co.il`), so their runs start 15 minutes apart too, and their sessions never overlap. A retry run fetches only what is still not stored. The check starts after the last retry run can have finished; it writes a check record, emails when a chain's morning is incomplete, a chain is stopped or a retry run failed, and pings healthchecks.io. A chain's retry runs fail when none covered one of the kinds the chain collects, when one ended with an error, or when together they listed nothing for the day and none was blocked (`the retry runs listed nothing for the day (unparsed names: N)`): a portal that renames its files so that none can be read, or dates them all another day, ends its runs without an error, and this alert is how it shows. They fail too when no run that day, main or retry, listed a full kind the chain collects (`no run listed a PriceFull for the day`, or `a PromoFull`) and none was blocked: the retry runs' names are taken together, so a Shufersal morning with no PriceFull at all would otherwise pass on its Stores run's names. A day a chain publishes nothing at all alerts the same way. The design gave 10:00 for the check; it is at 10:45 because the last retry run (Shufersal's full promotion files) starts at 10:15 and may run until 10:30, and 15 minutes more leave room for its manifest write and the schedulers' start-up lag. A retry run that runs out of time is a failed run even with nothing missing, since it could not read the whole listing: a retry re-reads its kind's 21 pages within about 810 s, so on a day the pages average more than about 38 s (2026-11-01: 15 to 39 s, medians 25 to 35) it runs out of time, and that alert is the sign.

Neither the schedules nor Lambda retry a failed invocation: the retry run is the retry. A block (a 401, 403 or 429, a captcha or verification page, or an HTML page where a file belongs) stops that chain until you clear it (below).

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

2. **healthchecks.io.** Create a check with period 1 day and grace 2 hours, and copy its ping URL (`https://hc-ping.com/<uuid>`). The 10:45 check pings it each morning; when no ping arrives, healthchecks.io emails. That catches a morning where nothing ran at all.

3. **Build and deploy with the schedules off.** Deploy from a clean, committed tree (`git status --porcelain src/` prints nothing): every manifest and check record carries `code_sha`, a fingerprint of `src/collector/`, and only a committed tree lets you find the commit behind it (step 8). The four values go on the command line, never into a file in the repo; don't use `sam deploy --guided`, which offers to save them to `samconfig.toml` (that file is gitignored as a second guard).

   ```bash
   sam build
   sam deploy --profile flights-sam --region il-central-1 --stack-name il-grocery-prices \
     --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset --parameter-overrides \
     'UserAgent="il-grocery-prices/0.1.0 (+https://github.com/<you>/il-grocery-prices; <email>)"' \
     'AlertEmail=<email>' \
     'HealthcheckUrl=https://hc-ping.com/<uuid>' \
     'ScheduleState=DISABLED'
   ```

   The inner double quotes around the User-Agent matter: `--parameter-overrides` splits on spaces, and without them the value is cut at the first space (the template refuses a value without `+https://` and an `@`, which catches that). Review the change set and confirm.

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

   A good run has `"blocked": null`, `"error": null` and `"failed": 0`. A run that ran short of time ends with `"error": "stopped: under 90 s left"`; start the same event again (or the retry event, `"mode": "retry"`): stored files are skipped, so it carries on where the first stopped. Carrefour's first run decides whether it stays (below).

   **Shufersal's full files take two runs each.** The first run of a full kind usually ends with `"error": "stopped: under 90 s left"`; the second, the same event again, skips what the first stored and finishes. If the second stops short too, start it a third time: on 2026-11-01 its pages took 15 to 39 s each, and a day much slower than that needs more runs. (The duration gate this step once held is gone: at that page speed one kind alone does not fit a run.)

7. **A manual check.** The check is short, so a plain invoke is fine; `--cli-read-timeout 900` keeps the CLI waiting rather than sending it again, which would check twice and could email twice:

   ```bash
   aws lambda invoke --function-name "$FN" --payload '{"mode": "check"}' --cli-read-timeout 900 --cli-binary-format raw-in-base64-out /tmp/il-grocery-check.json --profile flights-sam --region il-central-1
   ```

   `/tmp/il-grocery-check.json` names the check record (`record`) and counts the alerts. The check pings healthchecks.io, which should show the ping within a minute. healthchecks.io measures a check's period from its last ping (the worked example on https://healthchecks.io/docs/, read 2026-11-01), so from that ping on it expects the next within a day and two hours. If the schedules will be on before then (step 9), leave the check running: the first scheduled check pings in time. If not, pause it: pausing is how its docs say to avoid unwanted alerts (same page; that a paused check sends none is implied, not stated). A ping normally takes a paused check out of pause: "Normally, when you ping a paused check, it leaves the paused state and goes into the 'up' state" (https://healthchecks.io/docs/configuring_checks/). The exception is on the same page: a check whose filtering rule for pinging a paused check is set to "Ignore the ping, stay in the paused state" stays paused, ignoring every ping, until it is resumed by hand. Leave that rule unset, and a manual check run while the check is paused un-pauses it. It also expects the day's retry runs: with none run that day, it reports each chain as failed ("a retry run is missing or failed: no retry run covered …") and emails you, which proves the email works. For a clean check, first run each retry event of the timetable (one per chain, Shufersal's one per kind) by hand, one at a time as there; each downloads only what is still missing. Do this only once that day's files are on the portals (step 6): the check fails a chain whose retry runs list nothing for the day, so a retry started too early makes the manual check alert every chain.

8. **Read what it wrote.** List a day's manifests, print one, and print the check record:

   ```bash
   aws s3 ls "s3://$BUCKET/manifests/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/manifests/date=YYYY-MM-DD/<chain>-<run id>.json" - --profile flights-sam --region il-central-1
   aws s3 ls "s3://$BUCKET/checks/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3 cp "s3://$BUCKET/checks/date=YYYY-MM-DD/check-<run id>.json" - --profile flights-sam --region il-central-1
   ```

   A manifest holds: `listed` (that day's file names the listing gave, of the kinds asked for), `files` (each stored or found stored, with `outcome` `stored`, `exists` or `conflict`, `size` and `sha256`), `failed` (tried and not stored, with why), `not_attempted` (listed, never tried because the run stopped), `unparsed` (listed names that could not be read), `listing_read_at` (null when the listing was never read), `blocked`, `error` and `code_sha`. "The store published nothing" shows as a store with no file in `listed` (coverage counts those); "listed but not stored" as a name in `listed` that the bucket does not hold (the check record's `missing`). Only the second is the collector's failure.

   A check record holds, per chain: `manifests` (how many runs), `listed` and `stored` counts, `missing` (every listed name not stored), `stopped` (since when and why, or null), `failed` (why the retry runs fall short, or null) and `coverage` (stores with that day's full price file against the stores in the latest store list: `published`, `expected`, `ratio`, or `"unknown"` with a `note`); then `alerts`, `run_id`, `checked_at` (UTC) and `code_sha`.

   Check that a stored file is locked:

   ```bash
   aws s3 ls "s3://$BUCKET/raw/chain=ramilevy/date=YYYY-MM-DD/" --profile flights-sam --region il-central-1
   aws s3api head-object --bucket "$BUCKET" --key "raw/chain=ramilevy/date=YYYY-MM-DD/<file name>" --query "[ObjectLockMode, ObjectLockRetainUntilDate]" --profile flights-sam --region il-central-1
   ```

   It should show `GOVERNANCE` and a date ten years on. To find the commit behind a `code_sha`, check out a candidate commit and run `PYTHONPATH=src .venv/bin/python -c 'from pathlib import Path; from collector.handler import code_sha; print(code_sha(Path("src/collector")))'`.

9. **Turn the schedules on**, on the owner's go: the same `sam deploy` command with all four parameters again and `'ScheduleState=ENABLED'`. Always pass all four, so no value is left to what the stack held before. If the healthchecks.io check is paused, the first scheduled check's ping normally takes it out of pause (step 7); see on healthchecks.io that it did. The next morning, read the manifests and the check record, and see the 10:45 ping on healthchecks.io. To turn them off, deploy again with `'ScheduleState=DISABLED'`.

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

Carrefour is reported to refuse visitors from outside Israel; whether AWS's Tel Aviv addresses get through is unknown until its first run from the stack. If that run is blocked, drop Carrefour (below) and record it in `.claude/OPEN_ISSUES.md`. Never another route to it.

## Dropping a chain

1. Delete the chain's schedules from `template.yaml`: its main and retry events (Shufersal has five main and three retry).
2. Delete its entry in `CHAINS` in `src/collector/chains.py`.
3. Bring the tests in line: its rows in the `SCHEDULES` table in `tests/test_template.py`, its manual-run line in this file (step 6), its cases in `tests/test_chains.py`, and any mutation in `scripts/mutation_check.py` that quotes it. Run the tests, cfn-lint and the mutation check (below).
4. Commit, then deploy as in step 3 of Deploy, with the same four parameters.

Its stored files stay, locked; so does its state file. The check stops looking at it, since it checks only the chains in `CHAINS`.

## Develop

From the repo root:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest --cov=collector --cov-fail-under=95
cfn-lint --regions il-central-1 -- template.yaml
python scripts/mutation_check.py
```

The mutation check breaks each rule in turn and expects a test to fail. It edits source files in place while it runs, so run nothing else from the checkout meanwhile. CI runs all three on every push. `tests/test_template.py` pins the deploy settings safety depends on (the bucket's lock and privacy, the role's permissions, the schedules, the parameters) and checks this file's commands against them: cfn-lint lets a misspelled schedule property through.

## Cost

Estimates from [collector.md](collector.md), "Cost":

- **Volume:** Shufersal's full files were about 162 MB on 2026-10-31 (measured from its listing); the other four chains have fewer stores. About 250 to 300 MB a day, so 8 to 9 GB a month.
- **S3 storage** at $0.025 per GB-month (il-central-1): about $0.25 the first month, about $2.70 a month after a year. Nothing is deleted (every file is locked for ten years), so storage grows every month; moves to colder storage wait until the bucket passes about 50 GB.
- **S3 writes:** about 2,000 a day at $0.0055 per 1,000: about $0.35 a month.
- **Lambda:** a few invocations of up to 15 minutes a day, inside the monthly free tier. The worst case, all 16 collecting runs and the check running the full 15 minutes at 512 MB, is 7,650 GB-seconds a day, about 230,000 a month.
- **Total:** about $1 to $3 a month in the first year.

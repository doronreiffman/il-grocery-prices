#!/bin/sh
# Copy what the hand build of a day reads from the archive into data/, and from the site into site/ (read-only on AWS):
#   sh scripts/sync.sh 2026-11-02
# The day's full price files, full promotion files and store lists of every chain into data/raw/, the day's manifests
# into data/manifests/, then every day's items tables, covered registries, scoring summaries, frozen forecasts files
# and scores files into data/; then, once the site's stack exists, the published day files into site/days/, the
# site-day files into site/site-days/ and the ledger into site/forecasts/.
set -eu
PROFILE=flights-sam
REGION=il-central-1
STACK=il-grocery-prices
ARCHIVE_PREFIX=il-grocery-prices-archivebucket-

day=${1:-}
case "$day" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) echo "usage: sh scripts/sync.sh YYYY-MM-DD" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
# The user the profile must be: GROCERY_AWS_ARN from the environment, else from scripts/local.env (untracked; a copy of
# scripts/local.env.example), so the repo names no account. With neither, nothing is asked of AWS.
# Only GROCERY_AWS_ARN is taken from the file, read in a subshell: a line there setting anything else (the profile,
# the day) never reaches this script.
if [ -z "${GROCERY_AWS_ARN:-}" ] && [ -f scripts/local.env ]; then
  GROCERY_AWS_ARN=$(. ./scripts/local.env && printf %s "${GROCERY_AWS_ARN:-}")
fi
EXPECTED=${GROCERY_AWS_ARN:-}
if [ -z "$EXPECTED" ]; then
  echo "GROCERY_AWS_ARN is not set: put your deploy user's ARN in scripts/local.env (a copy of scripts/local.env.example) or in the environment; nothing synced" >&2
  exit 1
fi
who=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text)
if [ "$who" != "$EXPECTED" ]; then
  echo "profile $PROFILE is $who, not $EXPECTED; nothing synced" >&2
  exit 1
fi
# The archive bucket from the collector stack's outputs (template.yaml), as publish.sh reads the site bucket from the
# site stack's: a read that fails, or a name that is not the stack's archive bucket's, stops the sync.
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" --profile "$PROFILE" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ArchiveBucketName'].OutputValue" --output text) || {
  echo "the outputs of stack $STACK could not be read; nothing synced" >&2
  exit 1
}
case "$BUCKET" in
  "$ARCHIVE_PREFIX"?*) ;;
  *) echo "stack output ArchiveBucketName is '$BUCKET', not a $ARCHIVE_PREFIX* bucket; nothing synced" >&2; exit 1 ;;
esac
aws s3 sync "s3://$BUCKET/raw/" data/raw/ --exclude '*' \
  --include "chain=*/date=$day/PriceFull*" --include "chain=*/date=$day/pricefull*" \
  --include "chain=*/date=$day/PromoFull*" --include "chain=*/date=$day/promofull*" \
  --include "chain=*/date=$day/Stores*" --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/manifests/date=$day/" "data/manifests/date=$day/" --profile "$PROFILE" --region "$REGION"

# What the shopper build reads beyond the day's own files (shopper.build's folders): the items tables, the covered
# registries, the scoring summaries, the frozen forecasts files and the scores files, as the site run in Lambda wrote
# them. Every day of each comes down, though the build reads only the 90 days before its own; the CLI copies only
# what is new or changed. --exact-timestamps on the forecasts: the Mac's build
# takes a synced forecasts file's time from its modification time (shopper.freeze.ReadOnlyFreezer) and stops
# (NotSynced) when it is not the published ledger's; the CLI sets it to the object's time in S3 on every download
# (awscli 2.34.9, customizations/s3/subscribers.py), and with --exact-timestamps a local file of the same size whose
# time is not S3's is downloaded again (syncstrategy/exacttimestamps.py), which the default leaves when it is older.
aws s3 sync "s3://$BUCKET/tables/items/" data/tables/items/ --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/tables/covered/" data/tables/covered/ --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/tables/scored/" data/tables/scored/ --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/forecasts/" data/forecasts/ --exact-timestamps --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/scores/" data/scores/ --profile "$PROFILE" --region "$REGION"

# The published day files, the site-day files and the ledger, so a build compares its numbers with what is on the
# site (B12) and the Mac's build finds every record its checks read (shopper.build's NotSynced: the published ledger
# and the site-day files beside the forecasts files above). Only a stack that does not exist yet is skipped; any other
# failure stops. AWS's answer for a missing stack, as seen on 2026-11-02:
# "An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id
# il-grocery-prices-site does not exist".
SITE_STACK=il-grocery-prices-site
err=$(mktemp)
trap 'rm -f "$err"' EXIT
if site_bucket=$(aws cloudformation describe-stacks --stack-name "$SITE_STACK" --profile "$PROFILE" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text 2>"$err"); then
  # --exact-timestamps: the bucket's copy wins unless the local file has its size and its exact time. Without
  # it a download skips a local file of the same size that is no newer than the object (awscli 2.34.9,
  # customizations/s3/syncstrategy/base.py), so a day file built here before a same-sized published one was
  # uploaded would stay and be compared with.
  aws s3 sync "s3://$site_bucket/days/" site/days/ --exact-timestamps --profile "$PROFILE" --region "$REGION"
  aws s3 sync "s3://$site_bucket/site-days/" site/site-days/ --exact-timestamps --profile "$PROFILE" --region "$REGION"
  aws s3 sync "s3://$site_bucket/forecasts/" site/forecasts/ --exclude '*' --include ledger.csv --exact-timestamps \
    --profile "$PROFILE" --region "$REGION"
elif grep -q "does not exist" "$err"; then
  echo "no stack $SITE_STACK yet, so no published day files, site-day files or ledger to sync"
else
  cat "$err" >&2
  exit 1
fi

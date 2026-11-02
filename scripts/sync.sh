#!/bin/sh
# Copy one day of the archive into data/ for the basket (read-only on AWS):
#   sh scripts/sync.sh 2026-11-02
# The day's full price files and store lists of every chain into data/raw/, then the day's manifests
# into data/manifests/, then, once the site's stack exists, the published day files into site/days/.
set -eu
PROFILE=flights-sam
REGION=il-central-1
EXPECTED=arn:aws:iam::137953273942:user/doron-admin
BUCKET=il-grocery-prices-archivebucket-fmnv3dorojol

day=${1:-}
case "$day" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) echo "usage: sh scripts/sync.sh YYYY-MM-DD" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
who=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text)
if [ "$who" != "$EXPECTED" ]; then
  echo "profile $PROFILE is $who, not $EXPECTED (account 137953273942); nothing synced" >&2
  exit 1
fi
aws s3 sync "s3://$BUCKET/raw/" data/raw/ --exclude '*' \
  --include "chain=*/date=$day/PriceFull*" --include "chain=*/date=$day/pricefull*" \
  --include "chain=*/date=$day/Stores*" --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/manifests/date=$day/" "data/manifests/date=$day/" --profile "$PROFILE" --region "$REGION"

# The published day files, so a build compares its numbers with what is on the site (B12). Only a stack that does
# not exist yet is skipped; any other failure stops. AWS's answer for a missing stack, as seen on 2026-11-02:
# "An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id
# il-grocery-prices-site does not exist".
SITE_STACK=il-grocery-prices-site
err=$(mktemp)
trap 'rm -f "$err"' EXIT
if site_bucket=$(aws cloudformation describe-stacks --stack-name "$SITE_STACK" --profile "$PROFILE" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text 2>"$err"); then
  aws s3 sync "s3://$site_bucket/days/" site/days/ --profile "$PROFILE" --region "$REGION"
elif grep -q "does not exist" "$err"; then
  echo "no stack $SITE_STACK yet, so no published day files to sync"
else
  cat "$err" >&2
  exit 1
fi

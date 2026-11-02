#!/bin/sh
# Copy one day of the archive into data/ for the basket (read-only on AWS):
#   sh scripts/sync.sh 2026-11-02
# The day's full price files and store lists of every chain into data/raw/, then the day's manifests
# into data/manifests/.
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

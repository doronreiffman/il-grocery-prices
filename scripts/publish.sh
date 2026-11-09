#!/bin/sh
# Upload the built shopper site to its bucket behind CloudFront (docs/operations.md):
#   sh scripts/publish.sh
# This writes to AWS: run it only on the owner's go, given after the owner has checked the "current as of"
# date on Nevo's page against docs/terms.md. Nothing is uploaded unless the site check (shopper.check) and the
# publish guard (shopper.guard) both pass, and nothing in the bucket is ever deleted (the shopper plan's
# question H): a page the build no longer writes stays on the site.
set -eu
PROFILE=flights-sam
REGION=il-central-1
EXPECTED=arn:aws:iam::137953273942:user/doron-admin
STACK=il-grocery-prices-site
BUCKET_PREFIX=il-grocery-prices-site-sitebucket-
PYTHON=${PYTHON:-.venv/bin/python}

ROOT=$(cd "$(dirname "$0")/.." && pwd)
# SITE_DIR, when given, is read from where the script was run; the default is the repo's site/.
SITE=$(cd "${SITE_DIR:-$ROOT/site}" 2>/dev/null && pwd) || {
  echo "no folder at ${SITE_DIR:-$ROOT/site}; nothing uploaded" >&2
  exit 1
}
cd "$ROOT"
who=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text)
if [ "$who" != "$EXPECTED" ]; then
  echo "profile $PROFILE is $who, not $EXPECTED (account 137953273942); nothing uploaded" >&2
  exit 1
fi
if [ ! -f "$SITE/.shopper-site" ]; then
  echo "$SITE has no .shopper-site marker, so it is not a shopper site build; nothing uploaded" >&2
  exit 1
fi
# aws s3 sync matches its filters against the full local path with fnmatch: a [ ] pair in the folder's
# path makes the allowlist below match nothing, and unmatched files are uploaded. ? and * would still
# match themselves; they are refused too, to be safe.
case "$SITE" in
  *'['* | *']'* | *'?'* | *'*'*)
    echo "the site folder's path ($SITE) has [, ], ? or *, which the upload filters would misread; nothing uploaded" >&2
    exit 1 ;;
esac
if ! PYTHONPATH=src "$PYTHON" -m shopper.check "$SITE"; then
  echo "the site check failed; nothing uploaded" >&2
  exit 1
fi

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" --profile "$PROFILE" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
bucket=$(output SiteBucketName)
distribution=$(output SiteDistributionId)
# The uploads below go to this stack's bucket only, never to the archive bucket, whose files are locked records.
case "$bucket" in
  "$BUCKET_PREFIX"?*) ;;
  *) echo "stack output SiteBucketName is '$bucket', not a $BUCKET_PREFIX* bucket; nothing uploaded" >&2; exit 1 ;;
esac
if [ -z "$distribution" ] || [ "$distribution" = None ]; then
  echo "stack output SiteDistributionId is '$distribution'; nothing uploaded" >&2
  exit 1
fi

# The publish guard (shopper.guard; B12 and question H): a published record is replaced only by a revision of it,
# the ledger only gains lines, the pages never go up over a later published day, and a published product page is
# never dropped. The bucket's day files, site-day files, forecasts files with the ledger, and scores files are copied
# (a read) into a temporary folder, its product page keys listed into a file, and both compared with the build's: a
# build into a site/ that sync.sh did not fill, or from a data folder only partly synced, would otherwise write over
# what is published. So each read that fails stops the upload by its own test (exit 2), never by set -e alone: let
# through, it would leave the guard comparing the build with an empty bucket, which passes anything. On an empty
# bucket (the first upload) each copy finds no object and exits 0, and the guard reads an empty folder: the CLI
# creates the destination folder and returns 1 or 2 only for a failed or warned transfer (awscli 2.34.9,
# customizations/s3/subcommands.py), and either stops here. The listing of an empty prefix prints "None" (seen on
# 2026-11-09), which the guard reads as no page: it takes only p/*.html keys.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for folder in days site-days forecasts scores; do
  aws s3 cp "s3://$bucket/$folder/" "$tmp/published/$folder/" --recursive --profile "$PROFILE" --region "$REGION" || {
    echo "the bucket's $folder/ could not be read; nothing uploaded" >&2
    exit 2
  }
done
aws s3api list-objects-v2 --bucket "$bucket" --prefix p/ --query 'Contents[].Key' --output text \
  --profile "$PROFILE" --region "$REGION" > "$tmp/pages" || {
  echo "the bucket's product pages could not be listed; nothing uploaded" >&2
  exit 2
}
if ! PYTHONPATH=src "$PYTHON" -m shopper.guard "$SITE" "$tmp/published" "$tmp/pages"; then
  echo "the publish guard failed; nothing uploaded" >&2
  exit 1
fi

# One allowlisted sync per kind of file, its content type set rather than guessed (the response headers send
# nosniff), the types basket.site.CONTENT_TYPES gives the site run's uploads. The marker and anything else in the
# folder stay local. Browsers keep a file five minutes, so an upload shows within minutes of the invalidation. No
# sync here removes anything: a published file the build lacks stays (question H).
# The data files go up first and the pages last, as the site run puts them (basket.site.upload): the forecasts and
# scores files, the ledger, the day and site-day files with the search pieces, search.js, then the pages; so a stop
# part-way never leaves a live page naming a file not yet up. Each upload that fails stops the script by its own
# test, never by set -e alone, before the next upload and the invalidation (the final review's finding 8). A rerun
# then passes the guard: what went up is the build's own bytes.
upload() {
  aws s3 sync "$SITE/" "s3://$bucket/" --exclude '*' "$@" --cache-control 'max-age=300' --profile "$PROFILE" --region "$REGION" || {
    echo "the upload of $2 failed: the kinds before it went up, none after it, and nothing was invalidated; run it again" >&2
    exit 1
  }
}
upload --include '*.csv.gz' --content-type 'application/gzip'
upload --include '*.csv' --content-type 'text/csv; charset=utf-8'
upload --include '*.json' --content-type 'application/json; charset=utf-8'
upload --include '*.js' --content-type 'text/javascript; charset=utf-8'
upload --include '*.html' --content-type 'text/html; charset=utf-8'
aws cloudfront create-invalidation --distribution-id "$distribution" --paths '/*' \
  --profile "$PROFILE" --query Invalidation.Id --output text
echo "published: https://$(output SiteDomainName)/"

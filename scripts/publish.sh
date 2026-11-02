#!/bin/sh
# Upload the built basket site to its bucket behind CloudFront (docs/operations.md, "The headline basket, by hand"):
#   sh scripts/publish.sh
# This writes to AWS: run it only on the owner's go, given after the owner has checked the "current as of"
# date on Nevo's page against docs/terms.md. Nothing is uploaded unless every check passes.
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
if [ ! -f "$SITE/.basket-site" ]; then
  echo "$SITE has no .basket-site marker, so it is not a basket build; nothing uploaded" >&2
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
if ! PYTHONPATH=src "$PYTHON" -m basket.check "$SITE"; then
  echo "the pre-upload check failed; nothing uploaded" >&2
  exit 1
fi

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" --profile "$PROFILE" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
bucket=$(output SiteBucketName)
distribution=$(output SiteDistributionId)
# --delete below (the pages) removes objects: only ever aim it at this stack's bucket. On the archive bucket a
# delete would add markers that hide locked files.
case "$bucket" in
  "$BUCKET_PREFIX"?*) ;;
  *) echo "stack output SiteBucketName is '$bucket', not a $BUCKET_PREFIX* bucket; nothing uploaded" >&2; exit 1 ;;
esac
if [ -z "$distribution" ] || [ "$distribution" = None ]; then
  echo "stack output SiteDistributionId is '$distribution'; nothing uploaded" >&2
  exit 1
fi

# One allowlisted sync per file type, content type set rather than guessed (the response headers
# send nosniff). The marker and anything else in the folder stay local. Browsers keep a file five
# minutes, so an upload shows within minutes of the invalidation.
upload() {
  aws s3 sync "$SITE/" "s3://$bucket/" "$@" --cache-control 'max-age=300' --profile "$PROFILE" --region "$REGION"
}
# The pages, with --delete: a page the build no longer writes leaves the site.
upload --delete --exclude '*' --include '*.html' --content-type 'text/html; charset=utf-8'
# The day files, never with --delete: days/ is append-only, and each day's file holds its revision reason, which
# exists nowhere else once published, so an upload from a site/ that lacks a day must not remove it.
upload --exclude '*' --include '*.json' --content-type 'application/json; charset=utf-8'
aws cloudfront create-invalidation --distribution-id "$distribution" --paths '/*' \
  --profile "$PROFILE" --query Invalidation.Id --output text
echo "published: https://$(output SiteDomainName)/"

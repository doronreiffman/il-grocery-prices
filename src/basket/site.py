"""The site bucket's side of the scheduled build: the published day read back, the latest day on the site, the
build's files put up, and one CloudFront invalidation. It does in the Lambda what `scripts/publish.sh` does on
the Mac, with the same settings:

    index.html, method.html     text/html; charset=utf-8         max-age=300
    days/<day>.json             application/json; charset=utf-8  max-age=300

The content type is set rather than guessed (the site's response headers send nosniff), and browsers keep a file
five minutes, so an upload shows within minutes of the invalidation. The invalidation covers every path (`/*`), as
publish.sh's does. Its CallerReference is the caller's, one per run (the run's id): CloudFront answers a second
request with the same reference and the same paths with the first one's invalidation, and creates no new one.

`upload` puts only the files it is told to: the two pages when `with_pages` (a run for a day earlier than the
site's latest leaves them alone, call 12 of `docs/headline-basket-step-two-plan.md`), then the day's file when
`with_day` (a day whose published file is unchanged need not go up again). It checks that each of those files is
in the site folder before it puts any, so a missing one leaves the site as it was. Anything else in the folder
(the `.basket-site` marker, other days' files) stays local.

Nothing here ever deletes. `days/` is append-only, as on the Mac; and a page the build no longer writes stays on
the site until a hand upload, whose `--delete` on the pages removes it.

S3Site works through boto3's S3 and CloudFront clients; MemorySite keeps the same rules in a dict, for other
modules' tests. Every rule above the bare operations lives in _Site, which both share.
"""
import re
from datetime import date
from pathlib import Path

from botocore.exceptions import ClientError

from collector.store import MISSING, error_code

PAGES = ("index.html", "method.html")
HTML = "text/html; charset=utf-8"
JSON = "application/json; charset=utf-8"
CACHE_CONTROL = "max-age=300"
_DAY_FILE = re.compile(r"^days/(\d{4}-\d{2}-\d{2})\.json$")


def day_key(day: date) -> str:
    return f"days/{day.isoformat()}.json"


def _day_of(key: str) -> date | None:
    """The day a key `days/<YYYY-MM-DD>.json` names; None for any other key."""
    match = _DAY_FILE.match(key)
    if match is None:
        return None
    try:
        return date.fromisoformat(match[1])
    except ValueError:  # the shape of a date that is no day, as days/2026-11-31.json
        return None


class _Site:
    """The site bucket and its distribution, over four bare operations the subclasses supply:

        _put(key, body, content_type, cache_control) -> None   write, replacing what is there
        _get(key) -> bytes | None                              the stored body; None when there is none
        _keys(prefix) -> list[str]                             every key under the prefix
        _invalidate(reference) -> str                          invalidate every path; the invalidation's id
    """

    def published_day(self, day: date) -> bytes | None:
        """The day's file as published; None when the site has none."""
        return self._get(day_key(day))

    def latest_published_day(self) -> date | None:
        """The greatest day among the site's `days/<YYYY-MM-DD>.json` files; None when it has none."""
        days = [day for day in map(_day_of, self._keys("days/")) if day is not None]
        return max(days, default=None)

    def upload(self, site_dir: Path, day: date, with_pages: bool, with_day: bool) -> list[str]:
        """Put the two pages from `site_dir` when `with_pages`, then the day's file when `with_day`; their keys,
        in that order. Refuses (FileNotFoundError), putting nothing, when one of those files is missing."""
        files = []
        if with_pages:
            files += [(name, HTML) for name in PAGES]
        if with_day:
            files.append((day_key(day), JSON))
        for key, _ in files:
            if not (site_dir / key).is_file():
                raise FileNotFoundError(f"{site_dir / key}: not in the built site; nothing uploaded")
        for key, content_type in files:
            self._put(key, (site_dir / key).read_bytes(), content_type, CACHE_CONTROL)
        return [key for key, _ in files]

    def invalidate(self, reference: str) -> str:
        """Invalidate every path of the distribution once, under the caller's reference; the invalidation's id."""
        return self._invalidate(reference)


class S3Site(_Site):
    """The site bucket and its distribution, through boto3's S3 and CloudFront clients."""

    def __init__(self, s3, cloudfront, bucket: str, distribution_id: str):
        self.s3 = s3
        self.cloudfront = cloudfront
        self.bucket = bucket
        self.distribution_id = distribution_id

    def _put(self, key: str, body: bytes, content_type: str, cache_control: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, CacheControl=cache_control)

    def _get(self, key: str) -> bytes | None:
        try:
            answer = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as err:
            if error_code(err) in MISSING:
                return None
            raise
        return answer["Body"].read()

    def _keys(self, prefix: str) -> list[str]:
        # One list_objects_v2 call gives at most 1,000 keys; days/ gains one a day.
        keys = []
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def _invalidate(self, reference: str) -> str:
        answer = self.cloudfront.create_invalidation(
            DistributionId=self.distribution_id,
            InvalidationBatch={"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": reference},
        )
        return answer["Invalidation"]["Id"]


class MemorySite(_Site):
    """The same rules in a dict, for tests. `objects` holds each key's body, content type and cache-control;
    `invalidations` each invalidation's reference, in order."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str, str]] = {}
        self.invalidations: list[str] = []

    def _put(self, key: str, body: bytes, content_type: str, cache_control: str) -> None:
        self.objects[key] = (bytes(body), content_type, cache_control)

    def _get(self, key: str) -> bytes | None:
        stored = self.objects.get(key)
        return None if stored is None else stored[0]

    def _keys(self, prefix: str) -> list[str]:
        return [key for key in self.objects if key.startswith(prefix)]

    def _invalidate(self, reference: str) -> str:
        self.invalidations.append(reference)
        return f"memory-{len(self.invalidations)}"

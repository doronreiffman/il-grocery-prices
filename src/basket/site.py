"""The site bucket's side of the scheduled build: the published files read back, the latest day on the site, the
build's files put up, and one CloudFront invalidation. It does in the Lambda what `scripts/publish.sh` does on the
Mac, with the same settings. A file's content type is set by its last suffix, never guessed (the site's response
headers send nosniff), so a forecasts file `.csv.gz` goes up as gzip, not as text; and browsers keep a file five
minutes, so an upload shows within minutes of the invalidation:

    .html   text/html; charset=utf-8          .csv   text/csv; charset=utf-8
    .json   application/json; charset=utf-8   .gz    application/gzip
    .js     text/javascript; charset=utf-8    every file: max-age=300

The invalidation covers every path (`/*`), as publish.sh's does. Its CallerReference is the caller's, one per run (the
run's id): CloudFront answers a second request with the same reference and the same paths with the first one's
invalidation, and creates no new one.

`upload` is the site run's upload (the shopper plan's Task 23, Call 9): the data files it is given, always (the ones
the build lists new: the day's forecasts file, the ledger, each scored day's scores file, the site-day and day files
when not unchanged); then, only when `with_pages` (the day is the site's latest, so a run for an earlier day leaves
every page as the later day's), every file under the page folders `p/`, `browse/` and `search/` (`PAGE_FOLDERS`), and
the fixed pages, `FIXED_PAGES`: `index.html`, `method.html`, `record.html`, `basket.html` and `search.js`, rebuilt every
morning from the code (the shopper plan's question H). Every file is checked first, before any put. The record files
(`is_record`: each day's forecasts file and scores file, never the ledger) go up in a `put_files` call of their own,
ended before anything else is put; a record put that fails stops the upload there (RecordsNotUploaded), so the ledger,
the site-day and day files and the pages, which name the records, never name a file the site lacks (the task review's
finding 1: a rerun lists the day's forecasts file only when the ledger gains its line). Then the rest, in the order
above, in a second call. Each file takes its content type by its last suffix: `search.js` goes up as JavaScript, never
as HTML (the second pre-flight's B3). Anything else in the folder (the marker, the published copies the build compared
with) stays local.

`put_files` puts the shopper site's files, any number of them, each once (a key given twice goes up once): it checks
first that every file is in the site folder and has a content type above, and refuses (FileNotFoundError, ValueError)
before any put when one is not, so a missing or unknown file leaves the site as it was; then it puts them through a
pool of `UPLOAD_WORKERS` threads (a morning puts every product page, about 22,000 to 25,000 by the design's count),
started in the order given. A put that fails is raised: the puts made before it are not undone, and those not yet
started when it is raised are not made. The latest day on the site is the greatest of the basket's day files (`days/`)
and the shopper site's (`site-days/`), which go up together; `day_of` reads the day such a key names.

Nothing here ever deletes. `days/`, `site-days/` and the data files are append-only, as on the Mac; and a page the
build no longer writes stays on the site, since the hand upload deletes nothing either (the shopper plan's question H).

S3Site works through boto3's S3 and CloudFront clients; MemorySite keeps the same rules in a dict, for other
modules' tests. Every rule above the bare operations lives in _Site, which both share.
"""
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path, PurePosixPath

from botocore.exceptions import ClientError

from collector.store import MISSING, error_code

FIXED_PAGES = ("index.html", "method.html", "record.html", "basket.html", "search.js")   # the pre-flight's S14
PAGE_FOLDERS = ("p", "browse", "search")   # the product pages, the browse pages and the search pieces
RECORD_FOLDERS = ("forecasts/", "scores/")   # the record files: each day's forecasts and scores files, as .csv.gz
UPLOAD_WORKERS = 16
HTML = "text/html; charset=utf-8"
JSON = "application/json; charset=utf-8"
CONTENT_TYPES = {".html": HTML, ".json": JSON, ".js": "text/javascript; charset=utf-8", ".csv": "text/csv; charset=utf-8",
                 ".gz": "application/gzip"}
CACHE_CONTROL = "max-age=300"
_DAY_FILE = re.compile(r"^(?:site-)?days/(\d{4}-\d{2}-\d{2})\.json$")


def day_key(day: date) -> str:
    return f"days/{day.isoformat()}.json"


class RecordsNotUploaded(Exception):
    """A record file's put failed, so nothing that names one was put (the module's docstring)."""


def is_record(key: str) -> bool:
    """Whether the site key is a record file: a day's forecasts file or scores file (`shopper.freeze.site_key`,
    `scores_site_key`), never the ledger."""
    return key.startswith(RECORD_FOLDERS) and key.endswith(".csv.gz")


def day_of(key: str) -> date | None:
    """The day a key `days/<YYYY-MM-DD>.json` or `site-days/<YYYY-MM-DD>.json` names; None for any other key."""
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

    def published(self, key: str) -> bytes | None:
        """The file at `key` as published; None when the site has none."""
        return self._get(key)

    def keys(self, prefix: str) -> list[str]:
        """Every published key under `prefix`."""
        return self._keys(prefix)

    def published_day(self, day: date) -> bytes | None:
        """The day's file as published; None when the site has none."""
        return self.published(day_key(day))

    def latest_published_day(self) -> date | None:
        """The greatest day among the site's `days/<YYYY-MM-DD>.json` and `site-days/<YYYY-MM-DD>.json` files; None
        when it has none."""
        days = [day for day in map(day_of, self._keys("days/") + self._keys("site-days/")) if day is not None]
        return max(days, default=None)

    def upload(self, site_dir: Path, data: Sequence[str], with_pages: bool) -> list[str]:
        """Put the data files `data` from `site_dir`, then, when `with_pages`, every file under PAGE_FOLDERS and the
        FIXED_PAGES: the record files among them first, in a `put_files` call of their own, then the rest; their keys,
        in that order. Refuses, putting nothing, when one of them is not in the folder (FileNotFoundError) or has no
        content type (ValueError); RecordsNotUploaded, with nothing else put, when a record put fails."""
        keys = list(data)
        if with_pages:
            keys += [path.relative_to(site_dir).as_posix() for folder in PAGE_FOLDERS
                     for path in sorted((site_dir / folder).rglob("*")) if path.is_file()]
            keys += FIXED_PAGES
        self._checked(site_dir, keys)  # every file found and typed before any put
        records = [key for key in keys if is_record(key)]
        try:
            put = self.put_files(site_dir, records)
        except Exception as error:  # a put failed: the files were checked above
            raise RecordsNotUploaded(f"a record file did not go up, so nothing that names it was put: "
                                     f"{type(error).__name__}: {error}") from error
        return put + self.put_files(site_dir, [key for key in keys if key not in records])

    def _checked(self, site_dir: Path, keys: Sequence[str]) -> list[tuple[str, Path, str]]:
        """Each file `site_dir / key` once, with its path and content type; FileNotFoundError for a file not in the
        folder, ValueError for one of no content type."""
        puts = []
        for key in dict.fromkeys(keys):
            path = site_dir / key
            if not path.is_file():
                raise FileNotFoundError(f"{path}: not in the built site; nothing uploaded")
            kind = CONTENT_TYPES.get(PurePosixPath(key).suffix)
            if kind is None:
                raise ValueError(f"{key}: no content type for a file of its kind; nothing uploaded")
            puts.append((key, path, kind))
        return puts

    def put_files(self, site_dir: Path, keys: Sequence[str]) -> list[str]:
        """Put each file `site_dir / key` at `key` with its content type and max-age=300, through a pool of
        UPLOAD_WORKERS threads; the keys, in the order given, each once. Refuses, putting nothing, when a file is not
        in the folder (FileNotFoundError) or has no content type (ValueError); a put that fails is raised (the module's
        docstring)."""
        puts = self._checked(site_dir, keys)

        def put(file: tuple[str, Path, str]) -> None:
            key, path, kind = file
            self._put(key, path.read_bytes(), kind, CACHE_CONTROL)

        with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
            list(pool.map(put, puts))  # reading every result raises a failed put here
        return [key for key, _, _ in puts]

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

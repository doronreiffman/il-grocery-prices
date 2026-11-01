"""Where the collector keeps what it fetches. Keys:

    raw/chain=<slug>/date=YYYY-MM-DD/<file name as published>
    raw/chain=<slug>/date=YYYY-MM-DD/<file name>.<first 12 hex of its SHA-256>   a different body under a stored name
    manifests/date=YYYY-MM-DD/<slug>-<run id>.json
    checks/date=YYYY-MM-DD/check-<run id>.json
    state/<slug>.json                                                         the chain's stopped latch

Raw files, manifests and checks are written once: each of their puts carries IfNoneMatch="*", so S3
refuses to replace a stored key, and its own Object Lock settings (governance mode, ten years). The
lock is set per object, not as a bucket default, so the state files stay plain, overwritable puts.
Nothing here ever deletes.

S3Store works through a boto3 client; MemoryStore keeps the same rules in a dict, for other
modules' tests. Every rule above the bare read, write and list lives in _Store, which both share, so
the same calls give the same outcomes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from botocore.exceptions import ClientError

RETENTION_DAYS = 3650
LOCK_MODE = "GOVERNANCE"
# S3's refusals of IfNoneMatch="*": 412 when the key holds an object, 409 when another write to it
# is under way. Either way the key is taken; what it holds decides the outcome.
REFUSED = ("PreconditionFailed", "ConditionalRequestConflict")
# A missing key: NoSuchKey from GetObject, a bare 404 when S3 sends no error body.
MISSING = ("NoSuchKey", "404")
# A conflict copy's name: the published name, a dot, and 12 lower-case hex digits.
_CONFLICT_COPY = re.compile(r"(?P<name>.+)\.[0-9a-f]{12}")


def raw_key(slug: str, day: date, name: str) -> str:
    return f"raw/chain={slug}/date={day.isoformat()}/{name}"


def manifest_key(day: date, slug: str, run_id: str) -> str:
    return f"manifests/date={day.isoformat()}/{slug}-{run_id}.json"


def check_key(day: date, run_id: str) -> str:
    return f"checks/date={day.isoformat()}/check-{run_id}.json"


def state_key(slug: str) -> str:
    return f"state/{slug}.json"


def published_name(key: str) -> str:
    """The name a raw key's file was published under: the key's last part, less a conflict copy's hash."""
    name = key.rsplit("/", 1)[-1]
    copy = _CONFLICT_COPY.fullmatch(name)
    return copy["name"] if copy else name


class PutOutcome(Enum):
    STORED = "stored"
    EXISTS = "exists"
    CONFLICT_STORED = "conflict"


class AlreadyStored(Exception):
    """A write-once key holds a different body, and this body has nowhere else to go."""


@dataclass(frozen=True)
class Stored:
    """One object in a MemoryStore, with the lock it was written under (None for a plain put)."""

    body: bytes
    lock_mode: str | None
    retain_until: datetime | None


class _Store:
    """The rules both stores share. Each subclass supplies the bare operations:

        _put_locked(key, body, until, content_type=None) -> bool   write once, locked; False when the key is taken
        _put_plain(key, body, content_type)                        write, replacing what is there
        _sha256(key) -> str                                        the hex SHA-256 of the stored body
        _get(key) -> bytes | None                                  the stored body; None when there is none
        _keys(prefix) -> list[str]                                 every key under the prefix
    """

    def __init__(self, retention_days: int, lock_mode: str):
        if retention_days < 1:
            raise ValueError("retention_days must be at least 1")
        self.retention = timedelta(days=retention_days)
        self.lock_mode = lock_mode

    def put_raw(self, key: str, body: bytes, now: datetime) -> PutOutcome:
        """Store a file as received. The same body already under the key is EXISTS (a re-run); a
        different one is kept beside it under the key plus its hash, and the stored one stays."""
        until = self._retain_until(now)
        if self._put_locked(key, body, until):
            return PutOutcome.STORED
        digest = hashlib.sha256(body).hexdigest()
        if self._sha256(key) == digest:
            return PutOutcome.EXISTS
        copy = f"{key}.{digest[:12]}"
        if self._put_locked(copy, body, until):
            return PutOutcome.CONFLICT_STORED
        if self._sha256(copy) == digest:
            return PutOutcome.EXISTS  # this changed body was kept beside the first on an earlier run
        raise AlreadyStored(f"{copy}: holds another body whose SHA-256 starts the same; neither is replaced")

    def put_record(self, key: str, body: bytes, now: datetime) -> None:
        """Store a manifest or a check record, write-once and locked like a raw file."""
        if self._put_locked(key, body, self._retain_until(now), "application/json"):
            return
        # The same record already there is this put's own earlier try: botocore retries a put whose
        # answer was lost (a dropped connection, a read timeout), and the retry meets the first write.
        if self._sha256(key) != hashlib.sha256(body).hexdigest():
            raise AlreadyStored(f"{key}: another record is stored under this key")

    def stored_names(self, slug: str, day: date) -> set[str]:
        """The names stored for the chain's day, as published; a conflict copy counts as its original."""
        return {published_name(key) for key in self._keys(raw_key(slug, day, ""))}

    def read_raw(self, key: str) -> bytes:
        body = self._get(key)
        if body is None:
            raise KeyError(key)
        return body

    def read_records(self, prefix: str) -> list[bytes]:
        """Every object under the prefix, in key order."""
        return [self.read_raw(key) for key in sorted(self._keys(prefix))]

    def read_state(self, slug: str) -> dict:
        """The chain's state; {} when it has none."""
        body = self._get(state_key(slug))
        return {} if body is None else json.loads(body)

    def write_state(self, slug: str, state: dict) -> None:
        self._put_plain(state_key(slug), json.dumps(state, sort_keys=True).encode(), "application/json")

    def _retain_until(self, now: datetime) -> datetime:
        # botocore sends a naive time as if it were UTC: on this Mac (Asia/Jerusalem, two or three
        # hours ahead of UTC) a naive datetime.now() would end the lock that much late, and pass in
        # CI, which runs on UTC.
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must carry a time zone")
        return now + self.retention


def _code(err: ClientError) -> str | None:
    return err.response.get("Error", {}).get("Code")


class S3Store(_Store):
    """The bucket, through a boto3 S3 client."""

    def __init__(self, client, bucket: str, retention_days: int = RETENTION_DAYS, lock_mode: str = LOCK_MODE):
        super().__init__(retention_days, lock_mode)
        self.client = client
        self.bucket = bucket

    def _put_locked(self, key: str, body: bytes, until: datetime, content_type: str | None = None) -> bool:
        extra = {"ContentType": content_type} if content_type else {}
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                **extra,
                IfNoneMatch="*",
                ObjectLockMode=self.lock_mode,
                ObjectLockRetainUntilDate=until,
                ChecksumAlgorithm="SHA256",
            )
        except ClientError as err:
            if _code(err) in REFUSED:
                return False
            raise
        return True

    def _put_plain(self, key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def _sha256(self, key: str) -> str:
        # Every object this collector writes goes up in one put_object with ChecksumAlgorithm="SHA256",
        # so S3 keeps the whole body's SHA-256 and gives it back with ChecksumMode="ENABLED".
        checksum = self.client.head_object(Bucket=self.bucket, Key=key, ChecksumMode="ENABLED").get("ChecksumSHA256")
        if checksum:
            return base64.b64decode(checksum).hex()
        return hashlib.sha256(self.read_raw(key)).hexdigest()

    def _get(self, key: str) -> bytes | None:
        try:
            answer = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as err:
            if _code(err) in MISSING:
                return None
            raise
        return answer["Body"].read()

    def _keys(self, prefix: str) -> list[str]:
        # One list_objects_v2 call gives at most 1,000 keys; Shufersal alone stores more in a day.
        keys = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys


class MemoryStore(_Store):
    """The same rules in a dict, for tests. `objects` holds every write with the lock it was given."""

    def __init__(self, retention_days: int = RETENTION_DAYS, lock_mode: str = LOCK_MODE):
        super().__init__(retention_days, lock_mode)
        self.objects: dict[str, Stored] = {}

    def _put_locked(self, key: str, body: bytes, until: datetime, content_type: str | None = None) -> bool:
        if key in self.objects:
            return False
        self.objects[key] = Stored(bytes(body), self.lock_mode, until)
        return True

    def _put_plain(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = Stored(bytes(body), None, None)

    def _sha256(self, key: str) -> str:
        return hashlib.sha256(self.objects[key].body).hexdigest()

    def _get(self, key: str) -> bytes | None:
        stored = self.objects.get(key)
        return None if stored is None else stored.body

    def _keys(self, prefix: str) -> list[str]:
        return [key for key in self.objects if key.startswith(prefix)]

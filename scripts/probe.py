#!/usr/bin/env python3
"""Probe one chain's price portal and save what it serves.

    GROCERY_USER_AGENT='il-grocery-prices/0.1 (+https://<repo>; <contact email>)' \
        python3 scripts/probe.py <slug> [--day YYYY-MM-DD] [--list-only]

    NCR only: --login-page-only [--asset PATH ...] reads the login page (and the
    scripts named) and stops; --landing-only [--asset PATH ...] logs in, saves the
    file page and its new scripts, and stops. Both exist to read how the portal
    works before posting anything.

Reads the chain's file listing (logging in with the published username for the
NCR chains), prints row counts by kind and by date, then downloads one Stores
file, the smallest PriceFull and the smallest PromoFull of the day. "The day"
is --day, or today's Israel date; when the listing has none of a kind for it,
the newest date that has that kind is used, and the probe says so.

One request at a time, 2 s apart, at most 10 requests a run, no automatic
redirects (each hop is a counted request). Every response is saved under
probe-out/<slug>/<run>/ (gitignored). The first refusal (401, 403, 429, a
captcha or verification page, HTML where a file belongs) stops the run and is
printed. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html
import html.parser
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe-out"
ISRAEL = ZoneInfo("Asia/Jerusalem")
PAUSE_S = 2.0
MAX_REQUESTS = 10
TIMEOUT_S = 60

# Usernames as printed by the Consumer Protection Authority's chain list,
# https://www.gov.il/he/pages/cpfta_prices_regulations (updated 12.08.2026):
# "password not needed, the field can be left empty".
NCR_BASE = "https://url.publishedprices.co.il"
CHAINS = {
    "shufersal": {"portal": "shufersal", "base": "https://prices.shufersal.co.il"},
    "ramilevy": {"portal": "ncr", "base": NCR_BASE, "username": "RamiLevi"},
    "osherad": {"portal": "ncr", "base": NCR_BASE, "username": "osherad"},
    "yochananof": {"portal": "ncr", "base": NCR_BASE, "username": "yohananof"},
    "carrefour": {"portal": "carrefour", "base": "https://prices.carrefour.co.il"},
}

# Kinds longest first where one is a prefix of another (PriceFull before Price).
NAME_RE = re.compile(r"(?<![A-Za-z])(PriceFull|PromoFull|Price|Promo|Stores)(\d{13})-[0-9-]+(?:\.(?:gz|xml))?")
SIZE_RE = re.compile(r"^\s*([\d.,]+)\s*(b|bytes|kb|mb|gb)?\s*$", re.I)
UNIT = {None: 1, "b": 1, "bytes": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
REFUSAL_STATUSES = (401, 403, 429)
REFUSAL_MARKERS = ("captcha", "cf-chl", "attention required", "verify you are human",
                   "are you a robot", "incapsula", "request unsuccessful")
SECRET_QUERY_RE = re.compile(r"(sig=)[^&\s\"'<>]+")
CSRF_META_RE = re.compile(r'(name="csrftoken" content=")[^"]*')


class Refused(Exception):
    """The portal refused (status, captcha page, or HTML where a file belongs)."""


class Stop(Exception):
    """The probe cannot go on (budget spent, unexpected answer)."""


class Finished(Exception):
    """An early stop the caller asked for (--login-page-only, --landing-only)."""


@dataclass
class Resp:
    method: str
    url: str
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def text(self) -> str:
        m = re.search(r"charset=([\w-]+)", self.content_type, re.I)
        return self.body.decode(m.group(1) if m else "utf-8", errors="replace")

    def looks_like_html(self) -> bool:
        head = self.body[:512].lstrip().lower()
        return "html" in self.content_type.lower() or head.startswith((b"<!doctype html", b"<html"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then raises HTTPError with the 3xx; the caller follows by hand


class Client:
    """One request at a time, a pause between requests, a hard request budget."""

    def __init__(self, user_agent: str, outdir: Path, hosts: set[str]):
        self.user_agent = user_agent
        self.outdir = outdir
        self.hosts = hosts
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect())
        self.count = 0
        self._last_end: float | None = None

    def request(self, method: str, url: str, label: str, form: dict[str, str] | None = None,
                headers: dict[str, str] | None = None) -> Resp:
        host = urllib.parse.urlsplit(url).hostname
        if host not in self.hosts:
            raise Stop(f"refusing a request to {host}: not this portal ({sorted(self.hosts)})")
        if self.count >= MAX_REQUESTS:
            raise Stop(f"request budget of {MAX_REQUESTS} spent")
        if self._last_end is not None:
            wait = PAUSE_S - (time.monotonic() - self._last_end)
            if wait > 0:
                time.sleep(wait)
        self.count += 1
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"User-Agent": self.user_agent, **(headers or {})})
        try:
            with self.opener.open(req, timeout=TIMEOUT_S) as r:
                resp = Resp(method, r.geturl(), r.status, _headers(r.headers), r.read())
        except urllib.error.HTTPError as e:
            resp = Resp(method, url, e.code, _headers(e.headers), e.read())
        finally:
            self._last_end = time.monotonic()
        self._save(resp, label, form)
        print(f"  #{self.count} {method} {_scrub(url)} -> {resp.status}, {len(resp.body)} bytes, "
              f"{resp.content_type or '-'}")
        if resp.status in REFUSAL_STATUSES:
            raise Refused(f"HTTP {resp.status} from {_scrub(url)}: {_snippet(resp)}")
        if resp.looks_like_html() and any(m in resp.text.lower() for m in REFUSAL_MARKERS):
            hit = [m for m in REFUSAL_MARKERS if m in resp.text.lower()]
            raise Refused(f"captcha or verification marker {hit} in {_scrub(url)}: {_snippet(resp)}")
        return resp

    def follow(self, method: str, url: str, label: str, form: dict[str, str] | None = None,
               headers: dict[str, str] | None = None) -> Resp:
        """Request, then follow same-portal redirects by hand (each hop counted)."""
        resp = self.request(method, url, label, form, headers)
        hops = 0
        while resp.status in (301, 302, 303, 307, 308):
            hops += 1
            location = resp.headers.get("location")
            if not location or hops > 3:
                raise Stop(f"redirect without a usable Location from {_scrub(resp.url)}")
            target = urllib.parse.urljoin(resp.url, location)
            if resp.status in (307, 308) and method != "GET":
                raise Stop(f"{resp.status} asks to repeat the {method} at {_scrub(target)}")
            resp = self.request("GET", target, f"{label}-redirect{hops}")
        if resp.status >= 400:
            raise Stop(f"HTTP {resp.status} from {_scrub(resp.url)}: {_snippet(resp)}")
        return resp

    def _save(self, resp: Resp, label: str, form: dict[str, str] | None) -> None:
        self.outdir.mkdir(parents=True, exist_ok=True)
        stem = f"{self.count:02d}-{re.sub(r'[^A-Za-z0-9._-]+', '_', label)}"
        (self.outdir / (stem + _extension(resp, label))).write_bytes(resp.body)
        meta = {"method": resp.method, "url": resp.url, "status": resp.status,
                "headers": resp.headers, "form_fields": sorted(form) if form else None,
                "at": dt.datetime.now(dt.timezone.utc).isoformat()}
        (self.outdir / (stem + ".meta.json")).write_text(json.dumps(meta, indent=1, ensure_ascii=False))


def _headers(msg) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in msg.items():
        k = k.lower()
        out[k] = f"{out[k]}\n{v}" if k in out else v
    return out


def _extension(resp: Resp, label: str) -> str:
    if re.search(r"\.(gz|xml)$", label):
        return ""
    if resp.body[:2] == b"\x1f\x8b":
        return ".gz"
    if resp.looks_like_html():
        return ".html"
    if "json" in resp.content_type or resp.body[:1] in (b"{", b"["):
        return ".json"
    if resp.body.lstrip()[:5] == b"<?xml":
        return ".xml"
    return ".bin"


def _scrub(url: str) -> str:
    return SECRET_QUERY_RE.sub(r"\1SCRUBBED", url)


def _snippet(resp: Resp, n: int = 400) -> str:
    text = resp.body[:n].decode("utf-8", errors="replace")
    return " ".join(CSRF_META_RE.sub(r"\1SCRUBBED", _scrub(text)).split())


class Page(html.parser.HTMLParser):
    """Title, links, scripts, metas, forms with their fields, and table rows."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self.metas: list[dict[str, str]] = []
        self.forms: list[dict] = []
        self.rows: list[dict] = []
        self._in_title = False
        self._in_script = False
        self._script: list[str] = []
        self._form: dict | None = None
        self._row: dict | None = None
        self._cell: list[str] | None = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
            if self._row is not None:
                self._row["links"].append(a["href"])
        elif tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            else:
                self._in_script, self._script = True, []
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "form":
            self._form = {"action": a.get("action", ""), "method": a.get("method", "get").lower(),
                          "id": a.get("id", ""), "fields": []}
            self.forms.append(self._form)
        elif tag in ("input", "button", "select", "textarea") and self._form is not None:
            self._form["fields"].append({"tag": tag, **a})
        elif tag == "tr":
            self._close_cell()
            self._row = {"cells": [], "links": []}
            self.rows.append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._close_cell()
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_script:
            self.inline_scripts.append("".join(self._script))
            self._in_script = False
        elif tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_cell()
            self._row = None
        elif tag == "form":
            self._form = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_script:
            self._script.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            self._row["cells"].append(" ".join("".join(self._cell).split()))
        self._cell = None


@dataclass
class Row:
    name: str
    kind: str
    day: dt.date | None
    url: str
    size: int | None = None
    extra: dict = field(default_factory=dict)


def parse_name(text: str) -> tuple[str, str, dt.date | None] | None:
    """(name, kind, day) for the first published file name in text, else None."""
    m = NAME_RE.search(text)
    if not m:
        return None
    name, kind = m.group(0), m.group(1)
    return name, kind, _day_in(name[m.end(2) - m.start(0):])


def _day_in(rest: str) -> dt.date | None:
    for m in re.finditer(r"(?=(20\d{2})(\d{2})(\d{2}))", rest):
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return None


def parse_size(text: str) -> int | None:
    m = SIZE_RE.match(text or "")
    if not m:
        return None
    try:
        return int(float(m.group(1).replace(",", "")) * UNIT[(m.group(2) or "").lower() or None])
    except ValueError:
        return None


def rows_from_table(page: Page, base_url: str) -> list[Row]:
    out = []
    for tr in page.rows:
        hit = None
        for text in tr["cells"] + tr["links"]:
            hit = parse_name(urllib.parse.unquote(text))
            if hit:
                break
        if not hit:
            continue
        name, kind, day = hit
        link = next((h for h in tr["links"] if name in urllib.parse.unquote(h)), tr["links"][0] if tr["links"] else "")
        sizes = [s for s in (parse_size(c) for c in tr["cells"]) if s is not None]
        out.append(Row(name, kind, day, urllib.parse.urljoin(base_url, link) if link else "",
                       sizes[0] if sizes else None, {"cells": tr["cells"]}))
    return out


def print_unparsed(names: list[str]) -> None:
    if names:
        print(f"  {len(names)} names not in the expected pattern, e.g. {names[:4]}")


def print_counts(rows: list[Row], title: str) -> None:
    counts = Counter((r.kind, r.day.isoformat() if r.day else "?") for r in rows)
    print(f"{title}: {len(rows)} rows")
    for (kind, day), n in sorted(counts.items()):
        print(f"    {kind:<10} {day}  {n}")


def pick(rows: list[Row], kind: str, day: dt.date) -> Row | None:
    """One Stores file, or the smallest file of the kind, for the day (or the newest day it has)."""
    of_kind = [r for r in rows if r.kind == kind and r.day is not None]
    if not of_kind:
        print(f"  no {kind} row in the listing")
        return None
    on_day = [r for r in of_kind if r.day == day]
    if not on_day:
        newest = max(r.day for r in of_kind)
        print(f"  no {kind} for {day}; using the newest day listed, {newest}")
        on_day = [r for r in of_kind if r.day == newest]
    sized = [r for r in on_day if r.size is not None]
    return min(sized, key=lambda r: r.size) if sized else sorted(on_day, key=lambda r: r.name)[0]


def download(client: Client, row: Row) -> None:
    resp = client.follow("GET", row.url, row.name)
    if resp.looks_like_html():
        raise Refused(f"HTML where a file belongs ({row.name}): {_snippet(resp)}")
    if not (resp.body[:2] == b"\x1f\x8b" or resp.body.lstrip()[:5] == b"<?xml"
            or resp.body[:3] == b"\xef\xbb\xbf" or resp.body[:2] in (b"\xff\xfe", b"\xfe\xff")):
        print(f"  note: {row.name} starts with {resp.body[:16]!r}, neither gzip nor XML")
    size = len(resp.body)
    inner = None
    if resp.body[:2] == b"\x1f\x8b":
        try:
            inner = len(gzip.decompress(resp.body))
        except OSError as e:
            print(f"  note: {row.name} does not gunzip: {e}")
    print(f"  saved {row.name}: {size} bytes" + (f", {inner} bytes unzipped" if inner else ""))


# --- portals ---------------------------------------------------------------

SHUFERSAL_CATEGORIES = {1: "Price", 2: "PriceFull", 3: "Promo", 4: "PromoFull", 5: "Stores"}


def probe_shufersal(client: Client, chain: dict, day: dt.date, args) -> None:
    base = chain["base"]
    rows: list[Row] = []
    for cat, kind in SHUFERSAL_CATEGORIES.items():
        url = f"{base}/FileObject/UpdateCategory?catID={cat}&storeId=0&page=1"
        resp = client.follow("GET", url, f"listing-cat{cat}")
        page = Page(resp.text)
        got = rows_from_table(page, resp.url)
        print_counts(got, f"  category {cat} ({kind}), page 1")
        pager = sorted({h for h in page.links if "page=" in h})
        if pager:
            print(f"    pager links: {pager[:3]} ... {pager[-3:]}")
        rows += got
    # What a page past the end looks like (Stores has few rows, so page 2 is past it).
    resp = client.follow("GET", f"{base}/FileObject/UpdateCategory?catID=5&storeId=0&page=2", "listing-cat5-page2")
    print_counts(rows_from_table(Page(resp.text), resp.url), "  category 5, page 2")
    _download_three(client, rows, day, args)


CARREFOUR_PATH_RE = re.compile(r"const\s+path\s*=\s*'(\d{8})'\s*;")
CARREFOUR_FILES_RE = re.compile(r"const\s+files\s*=\s*(\[.*?\])\s*;\s*$", re.M)


def probe_carrefour(client: Client, chain: dict, day: dt.date, args) -> None:
    # The page's own date picker reloads "/?date=YYYYMMDD"; without it the page shows today.
    url = chain["base"] + "/" + (f"?date={day:%Y%m%d}" if args.day else "")
    resp = client.follow("GET", url, "listing")
    page = Page(resp.text)
    print(f"  title: {page.title.strip()!r}; scripts {page.scripts[:6]}")
    script = "\n".join(page.inline_scripts)
    path, files = CARREFOUR_PATH_RE.search(script), CARREFOUR_FILES_RE.search(script)
    if not (path and files):
        raise Stop("no `const path` / `const files` in the page's inline script; inspect the saved page")
    print(f"  path {path.group(1)}, files array {len(files.group(1))} chars")
    rows, unparsed = [], []
    for f in json.loads(files.group(1)):
        hit = parse_name(f["name"])
        if hit:  # the page builds each link as origin + "/" + path + "/" + name
            rows.append(Row(hit[0], hit[1], hit[2], f"{chain['base']}/{path.group(1)}/{f['name']}",
                            f.get("size"), {"modified": f.get("modified")}))
        else:
            unparsed.append(f["name"])
    print_unparsed(unparsed)
    print_counts(rows, "  listing")
    _download_three(client, rows, day, args)


def _password_form(page: Page) -> dict | None:
    return next((f for f in page.forms
                 if any(x.get("type", "").lower() == "password" for x in f["fields"])), None)


def _csrf_token(page: Page) -> str | None:
    return next((m.get("content") for m in page.metas if m.get("name") == "csrftoken"), None)


def _fetch_assets(client: Client, page_url: str, paths: list[str]) -> None:
    for path in paths:  # scripts a page loads, read to see how it submits or lists
        client.follow("GET", urllib.parse.urljoin(page_url, path),
                      "asset-" + path.rsplit("/", 1)[-1].split("?")[0])


def ncr_login(client: Client, chain: dict, args) -> Resp:
    """Log in as a browser would: the form's fields, the published username, an empty password.

    The gov.il list links the site root, which redirects to /login. The portal's
    common.min.js appends a hidden "csrftoken" input (the <meta name="csrftoken">
    value) to every form, so the browser's POST carries it; this does the same.
    """
    resp = client.follow("GET", chain["base"] + "/login", "login-page")
    page = Page(resp.text)
    print(f"  title: {page.title.strip()!r}; at {resp.url}")
    for f in page.forms:
        print(f"  form id={f['id']!r} {f['method'].upper()} action={f['action']!r}: "
              + ", ".join(f"{x['tag']}:{x.get('type', '')}:{x.get('name', '')}" for x in f["fields"]))
    print(f"  metas: {[m.get('name') for m in page.metas if m.get('name')]}; scripts: {page.scripts}")
    form = _password_form(page)
    if form is None:
        raise Stop("no login form with a password field on the page the gov.il list links")
    if args.login_page_only:
        _fetch_assets(client, resp.url, args.asset)
        raise Finished("--login-page-only: stopped before the login")
    fields: dict[str, str] = {}
    for x in form["fields"]:
        name = x.get("name")
        kind = x.get("type", "").lower() or ("submit" if x["tag"] == "button" else "text")
        if not name:
            continue
        if kind == "password":
            fields[name] = ""  # the gov.il list: no password needed, the field may be left empty
        elif kind in ("text", "email"):
            fields[name] = chain["username"]
        elif kind in ("hidden", "submit"):
            fields[name] = x.get("value", "")
    token = _csrf_token(page)
    if token:
        fields["csrftoken"] = token
    print(f"  login: POST {form['action']} with fields {sorted(fields)}")
    landing = client.follow("POST", urllib.parse.urljoin(resp.url, form["action"]), "login-post", form=fields)
    lpage = Page(landing.text)
    # Success lands on the file browser; a refusal shows the login form again. (The file
    # browser has a password field of its own, in its share dialog, so look for the form.)
    if (urllib.parse.urlsplit(landing.url).path.startswith("/login")
            or any(f["action"] == form["action"] for f in lpage.forms)):
        raise Refused(f"login not accepted, landed on {landing.url}: {_snippet(landing)}")
    print(f"  logged in: landed on {landing.url}, title {lpage.title.strip()!r}, scripts {lpage.scripts}")
    if args.landing_only:
        login_scripts = set(page.scripts)
        _fetch_assets(client, landing.url, args.asset or [s for s in lpage.scripts if s not in login_scripts])
        raise Finished("--landing-only: stopped after the login")
    return landing


NCR_COLUMNS = (("fname", True), ("typeLabel", False), ("size", True), ("ftime", True), ("", False))


def ncr_dir_form(cd: str, token: str | None, length: int, search: str = "") -> dict[str, str]:
    """The POST cftp.file.min.js sends to /file/json/dir (DataTables 1.9 server-side
    parameters for its five columns, plus "cd"; common.min.js adds "csrftoken")."""
    form = {"sEcho": "1", "iColumns": str(len(NCR_COLUMNS)), "sColumns": "," * (len(NCR_COLUMNS) - 1),
            "iDisplayStart": "0", "iDisplayLength": str(length)}
    for i, (data, sortable) in enumerate(NCR_COLUMNS):
        form.update({f"mDataProp_{i}": data, f"sSearch_{i}": "", f"bRegex_{i}": "false",
                     f"bSearchable_{i}": "true", f"bSortable_{i}": "true" if sortable else "false"})
    form.update({"sSearch": search, "bRegex": "false", "iSortingCols": "0", "cd": cd})
    if token:
        form["csrftoken"] = token
    return form


def probe_ncr(client: Client, chain: dict, day: dt.date, args) -> None:
    landing = ncr_login(client, chain, args)
    lpage = Page(landing.text)
    m = re.search(r'data-cftp="([^"]*)"', landing.text)
    if not m:
        raise Stop("no data-cftp settings on the file page; inspect the saved page")
    cfg = json.loads(html.unescape(m.group(1)))
    cd = next((x.get("value", "") for f in lpage.forms for x in f["fields"] if x.get("id") == "cd"),
              cfg.get("curDir", "/"))
    length = int(cfg.get("dtDisplayLength") or 1000)
    print(f"  file page settings: curDir {cfg.get('curDir')!r}, curDirParam {cfg.get('curDirParam')!r}, "
          f"rows per page {length}; cd {cd!r}")
    resp = client.request("POST", chain["base"] + "/file/json/dir", "listing",
                          form=ncr_dir_form(cd, _csrf_token(lpage), length),
                          headers={"X-Requested-With": "XMLHttpRequest",
                                   "Accept": "application/json, text/javascript, */*; q=0.01"})
    if resp.status != 200 or resp.looks_like_html():
        raise Stop(f"listing answered {resp.status} {resp.content_type}: {_snippet(resp)}")
    data = json.loads(resp.body)
    entries = data.get("aaData") or []
    print(f"  listing keys {sorted(data)}; iTotalRecords {data.get('iTotalRecords')}, "
          f"iTotalDisplayRecords {data.get('iTotalDisplayRecords')}, {len(entries)} entries")
    if entries:
        print(f"  first entry fields: {sorted(entries[0])}")
    rows, types_seen, unparsed = [], Counter(), []
    cur_dir, cur_param = cfg.get("curDir", "/"), cfg.get("curDirParam", "/")
    for e in entries:
        types_seen[e.get("type")] += 1
        if e.get("type") != "file":
            continue
        hit = parse_name(e.get("fname", ""))
        if not hit:
            unparsed.append(e.get("fname"))
            continue
        # The page's link rule: "d" + value if value starts with "/", else
        # "d" + curDirParam + ("" if curDir == "/" else "/") + fname, under /file/.
        value = e.get("value", "")
        rel = ("d" + value if value.startswith("/")
               else "d" + cur_param + ("" if cur_dir == "/" else "/") + e["fname"])
        rows.append(Row(hit[0], hit[1], hit[2], f"{chain['base']}/file/{rel}", e.get("size"),
                        {"ftime": e.get("ftime"), "time": e.get("time")}))
    print(f"  entry types: {dict(types_seen)}")
    print_unparsed(unparsed)
    print_counts(rows, "  listing")
    if len(entries) < int(data.get("iTotalDisplayRecords") or 0):
        print("  note: the listing has more entries than one page returned")
    _download_three(client, rows, day, args)


def _download_three(client: Client, rows: list[Row], day: dt.date, args) -> None:
    for kind in ("Stores", "PriceFull", "PromoFull"):
        row = pick(rows, kind, day)
        if row is None:
            continue
        print(f"  {kind}: {row.name} ({row.size if row.size is not None else 'size unknown'} bytes listed)")
        if args.list_only:
            continue
        if not row.url:
            raise Stop(f"no download link for {row.name}")
        download(client, row)


PROBES = {"shufersal": probe_shufersal, "ncr": probe_ncr, "carrefour": probe_carrefour}


def user_agent_from_env(env=os.environ) -> str:
    ua = env.get("GROCERY_USER_AGENT", "")
    if "+https://" not in ua or "@" not in ua:
        raise SystemExit("GROCERY_USER_AGENT must name the project, its +https:// URL and a contact address with @")
    return ua


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slug", choices=sorted(CHAINS))
    ap.add_argument("--day", type=dt.date.fromisoformat, help="the Israel date to pick files for")
    ap.add_argument("--list-only", action="store_true", help="read the listing, download nothing")
    ap.add_argument("--login-page-only", action="store_true", help="NCR: read the login page and stop")
    ap.add_argument("--asset", action="append", default=[],
                    help="with --login-page-only or --landing-only: also read this same-site script")
    ap.add_argument("--landing-only", action="store_true",
                    help="NCR: log in, save the landing page and the new scripts it loads, stop")
    args = ap.parse_args(argv)
    ua = user_agent_from_env()
    chain = CHAINS[args.slug]
    day = args.day or dt.datetime.now(ISRAEL).date()
    started = dt.datetime.now(dt.timezone.utc)
    outdir = OUT / args.slug / started.strftime("%Y%m%dT%H%M%SZ")
    hosts = {urllib.parse.urlsplit(chain["base"]).hostname}
    if chain["portal"] == "shufersal":
        hosts.add("pricesprodpublic.blob.core.windows.net")
    client = Client(ua, outdir, hosts)
    print(f"{args.slug}: day {day}, saving to {outdir.relative_to(ROOT)}")
    try:
        PROBES[chain["portal"]](client, chain, day, args)
    except Refused as e:
        print(f"REFUSED after {client.count} requests: {e}")
        return 2
    except Stop as e:
        print(f"STOPPED after {client.count} requests: {e}")
        return 3
    except Finished as e:
        print(f"{e}; {client.count} requests")
        return 0
    print(f"done: {client.count} requests")
    return 0


if __name__ == "__main__":
    sys.exit(main())

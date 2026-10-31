"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py            # every mutation
    .venv/bin/python scripts/mutation_check.py "HTML"     # only those whose name contains one of the arguments

Each mutation names the file it breaks and the test files that must catch it. It edits source files
in place while it runs: run nothing else from this checkout until it finishes. Files are restored
afterwards. Exit code 1 if any mutation goes unnoticed, or if its text to break is not found exactly
once (the script is out of date).

Copied from flights-archive's harness, with one change: the test runs write no bytecode. Python
trusts a cached .pyc whose source has the same size and the same whole-second mtime, so a
same-length mutation written and restored within one second could otherwise leave the broken code
cached for the next run.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("src/collector/names.py", ["tests/test_names.py"])
PAYLOAD = ("src/collector/payload.py", ["tests/test_payload.py"])
STORELIST = ("src/collector/storelist.py", ["tests/test_storelist.py"])
HTTP = ("src/collector/http.py", ["tests/test_http.py"])
CHAINS = ("src/collector/chains.py", ["tests/test_chains.py"])
SOURCES = ("src/collector/sources/__init__.py", ["tests/test_chains.py"])

# name -> (file and the tests that must catch it, text as it stands, the broken replacement)
MUTATIONS = {
    # names
    "PriceFull read as Price": (NAMES, "_BY_LENGTH = sorted(KINDS, key=len, reverse=True)", "_BY_LENGTH = sorted(KINDS, key=len)"),
    "day taken from the clock": (NAMES, "        day = datetime.date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))", "        day = datetime.date.today()"),
    "lower-case names refused": (NAMES, '_KIND = re.compile("|".join(_BY_LENGTH), re.IGNORECASE)', '_KIND = re.compile("|".join(_BY_LENGTH))'),
    "kind returned as published, not as in KINDS": (NAMES, "    kind = _CANONICAL[prefix.group().lower()]", "    kind = prefix.group()"),
    "store 039's date and time run together refused": (NAMES, r'r"-(?P<day>\d{8})(?:\d{4})?"', r'r"-(?P<day>\d{8})"'),
    "store taken from the sub-chain": (NAMES, "        store = groups[-1]", "        store = groups[0]"),
    "price file without a store accepted": (NAMES, '    else:\n        return None\n    digits = rest["day"]', '    else:\n        store = None\n    digits = rest["day"]'),
    "text after the name accepted": (NAMES, "_REST.fullmatch(name, prefix.end())", "_REST.match(name, prefix.end())"),
    # payload
    "HTML accepted as a file": (PAYLOAD, "    if looks_like_html(data):", "    if False:"),
    "empty file accepted": (PAYLOAD, "    if not data:", "    if False:"),
    "HTML inside a gzip not seen": (PAYLOAD, '        head = _gunzip_head(data) or b""', '        head = b""'),
    "UTF-16 HTML not seen": (PAYLOAD, '        head = head[2:].decode("utf-16-le", "replace").encode()', "        pass"),
    "HTML after whitespace not seen": (PAYLOAD, ".removeprefix(UTF8_BOM).lstrip().lower()", ".removeprefix(UTF8_BOM).lower()"),
    "upper-case HTML not seen": (PAYLOAD, ".removeprefix(UTF8_BOM).lstrip().lower()", ".removeprefix(UTF8_BOM).lstrip()"),
    "gzip taken on its magic alone": (PAYLOAD, "        if not content.startswith(XML_STARTS):", "        if False:"),
    "truncated gzip accepted": (PAYLOAD, "            content = gzip.decompress(data)", "            content = _gunzip_head(data)"),
    "cut-short gzip escapes as EOFError": (PAYLOAD, "        except (EOFError, OSError, zlib.error) as exc:", "        except (OSError, zlib.error) as exc:"),
    "corrupt gzip escapes as zlib.error": (PAYLOAD, "    except zlib.error:", "    except ValueError:"),
    "UTF-16 Stores file refused": (PAYLOAD, ', UTF16LE_BOM + b"<\\x00")', ")"),
    "UTF-8 BOM before <Root> refused": (PAYLOAD, 'UTF8_BOM + b"<Root>", ', ""),
    # store list
    "gzipped Stores file read as plain XML": (STORELIST, "    xml = gzip.decompress(data) if data.startswith(GZIP_MAGIC) else data", "    xml = data"),
    "store ids lose their leading zeros": (STORELIST, '{(el.text or "").strip() for el', "{str(int(el.text)) for el"),
    # http
    "429 not a block": (HTTP, "BLOCK_STATUSES = frozenset({401, 403, 429})", "BLOCK_STATUSES = frozenset({401, 403})"),
    "403 not a block": (HTTP, "BLOCK_STATUSES = frozenset({401, 403, 429})", "BLOCK_STATUSES = frozenset({401, 429})"),
    "401 not a block": (HTTP, "BLOCK_STATUSES = frozenset({401, 403, 429})", "BLOCK_STATUSES = frozenset({403, 429})"),
    "captcha page accepted": (HTTP, "    if marker:", "    if False:"),
    "upper-case marker missed": (HTTP, "    body = answer.body.lower()", "    body = answer.body"),
    "HTML content type not enough to seek markers": (HTTP, '"text/html" not in answer.headers.get("content-type", "").lower() and ', ""),
    "markers sought outside HTML": (HTTP, '    if "text/html" not in answer.headers.get("content-type", "").lower() and not looks_like_html(answer.body):', "    if False:"),
    "markers sought in gzip bodies": (HTTP, "    if answer.body.startswith(GZIP_MAGIC):", "    if False:"),
    "User-Agent dropped": (HTTP, 'headers={"User-Agent": self.user_agent}))', "headers={}))"),
    "User-Agent dropped from POST": (HTTP, '{"User-Agent": self.user_agent, "Content-Type": FORM}', '{"Content-Type": FORM}'),
    "User-Agent without +https:// accepted": (HTTP, 'if "+https://" not in user_agent or "@" not in user_agent:', 'if "@" not in user_agent:'),
    "User-Agent without @ accepted": (HTTP, 'if "+https://" not in user_agent or "@" not in user_agent:', 'if "+https://" not in user_agent:'),
    "pause skipped": (HTTP, "            self._sleep(self.pause)", "            pass"),
    "pause before the first request": (HTTP, "        if self._sent:", "        if True:"),
    "timeout not passed": (HTTP, "self._opener.open(req, timeout=self.timeout)", "self._opener.open(req)"),
    "redirect to another host followed": (HTTP, "        if (new.scheme, new.netloc) != (old.scheme, old.netloc):", "        if False:"),
    "redirect from https to http followed": (HTTP, "if (new.scheme, new.netloc) != (old.scheme, old.netloc):", "if new.netloc != old.netloc:"),
    "cookies not kept": (HTTP, "urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),", ""),
    "proxy taken from the environment": (HTTP, "urllib.request.ProxyHandler({})", "urllib.request.ProxyHandler()"),
    "server error returned as an answer": (HTTP, "    if not 200 <= answer.status < 300:", "    if False:"),
    "cut-short body accepted": (HTTP, "    if length.isdecimal() and len(answer.body) < int(length):", "    if False:"),
    "dropped connection escapes as OSError": (HTTP, "except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:", "except (urllib.error.URLError, http.client.HTTPException) as exc:"),
    "cut-short read escapes as http.client's error": (HTTP, "except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:", "except (urllib.error.URLError, OSError) as exc:"),
    "unreadable refusal body turns a block into an error": (HTTP, '    except (OSError, http.client.HTTPException):\n        return b""', '    except http.client.HTTPException:\n        return b""'),
    "block loses the link's query": (HTTP, "        self.url = url", "        self.url = _without_query(url)"),
    "signed query in the block message": (HTTP, 'super().__init__(f"{reason}: {_without_query(url)}")', 'super().__init__(f"{reason}: {url}")'),
    "first URL reported, not where redirects landed": (HTTP, "answer = Response(resp.geturl(), resp.status", "answer = Response(req.full_url, resp.status"),
    "form not url-encoded": (HTTP, "        data = urllib.parse.urlencode(form).encode()", "        data = str(form).encode()"),
    # chains
    "a sixth chain added": (CHAINS, '    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof"),\n', '    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof"),\n    Chain("extra", "Extra", "carrefour", "https://example.org"),\n'),
    "a chain dropped": (CHAINS, '    Chain("carrefour", "Carrefour", "carrefour", "https://prices.carrefour.co.il"),\n', ""),
    "a chain filed under its name, not its slug": (CHAINS, "{chain.slug: chain for chain in (", "{chain.name: chain for chain in ("),
    "a chain's name changed": (CHAINS, '"Osher Ad"', '"osherad"'),
    "a chain on the wrong portal": (CHAINS, 'Chain("osherad", "Osher Ad", "ncr"', 'Chain("osherad", "Osher Ad", "shufersal"'),
    "a password field": (CHAINS, "    username: str | None = None\n", '    username: str | None = None\n    password: str = ""\n'),
    "a password attribute that is not a field": (CHAINS, "    username: str | None = None\n", '    username: str | None = None\n    password = ""\n'),
    "username defaults to empty, not None": (CHAINS, "    username: str | None = None", '    username: str | None = ""'),
    "an http base URL": (CHAINS, '"https://prices.carrefour.co.il"', '"http://prices.carrefour.co.il"'),
    "the NCR portal over http": (CHAINS, 'NCR_URL = "https://url.publishedprices.co.il"', 'NCR_URL = "http://url.publishedprices.co.il"'),
    "Rami Levy's username in the wrong case": (CHAINS, 'username="RamiLevi"', 'username="ramilevi"'),
    "Yochananof's username spelled as its slug": (CHAINS, 'username="yohananof"', 'username="yochananof"'),
    "Osher Ad without a username": (CHAINS, 'NCR_URL, username="osherad"),', "NCR_URL),"),
    "a username on a portal with no login": (CHAINS, '"https://prices.carrefour.co.il"),', '"https://prices.carrefour.co.il", username="carrefour"),'),
    "Chain not frozen": (CHAINS, "@dataclass(frozen=True)\nclass Chain:", "@dataclass\nclass Chain:"),
    "gov.il citation dropped": (CHAINS, "https://www.gov.il/he/pages/cpfta_prices_regulations", "the gov.il page"),
    "citation without its update date": (CHAINS, "(updated 12.08.2026)", "()"),
    # sources
    "Listed not frozen": (SOURCES, "@dataclass(frozen=True)\nclass Listed:", "@dataclass\nclass Listed:"),
    "Listed without its URL": (SOURCES, "    name: FileName\n    url: str\n", "    name: FileName\n"),
    "listing takes no kinds": (SOURCES, "def listing(self, http: Http, kinds: tuple[str, ...])", "def listing(self, http: Http)"),
    "download takes a URL, not the listed item": (SOURCES, "def download(self, http: Http, item: Listed)", "def download(self, http: Http, item: str)"),
    "download returns text": (SOURCES, ") -> bytes:", ") -> str:"),
}


def main(wanted: list[str]) -> int:
    """Run every mutation, or with `wanted` only those whose name contains one of its strings."""
    chosen = {name: m for name, m in MUTATIONS.items() if not wanted or any(w in name for w in wanted)}
    if not chosen:
        print(f"No mutation name contains any of {wanted}.")
        return 2
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
    originals = {}
    missed = []
    try:
        for name, ((rel, tests), old, new) in chosen.items():
            path = ROOT / rel
            original = originals.setdefault(path, path.read_text())
            if original.count(old) != 1:
                print(f"STALE  {name}: the text to break occurs {original.count(old)} times in {rel}; update this script")
                missed.append(name)
                continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q", "-x", "-p", "no:cacheprovider"],
                                     capture_output=True, text=True, cwd=ROOT, env=env)
            finally:
                path.write_text(original)
            caught = run.returncode != 0
            print(("CAUGHT " if caught else "MISSED ") + name)
            if not caught:
                missed.append(name)
    finally:
        for path, original in originals.items():
            path.write_text(original)
    print("Files restored." + (f" Missed: {missed}" if missed else " Every mutation was caught."))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

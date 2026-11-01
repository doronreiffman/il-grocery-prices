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
SHUFERSAL = ("src/collector/sources/shufersal.py", ["tests/test_shufersal.py"])
NAME_CHECK = ("src/collector/sources/__init__.py", ["tests/test_chains.py"])
NCR = ("src/collector/sources/ncr.py", ["tests/test_ncr.py"])
CARREFOUR = ("src/collector/sources/carrefour.py", ["tests/test_carrefour.py"])
STORE = ("src/collector/store.py", ["tests/test_store.py"])
RUN = ("src/collector/run.py", ["tests/test_run.py"])

# name -> (file and the tests that must catch it, text as it stands, the broken replacement)
MUTATIONS = {
    # names
    "PriceFull read as Price": (NAMES, "_BY_LENGTH = sorted(KINDS, key=len, reverse=True)", "_BY_LENGTH = sorted(KINDS, key=len)"),
    "day taken from the clock": (NAMES, "        day = datetime.date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))", "        day = datetime.date.today()"),
    "lower-case names refused": (NAMES, '_KIND = re.compile("|".join(_BY_LENGTH), re.IGNORECASE | re.ASCII)', '_KIND = re.compile("|".join(_BY_LENGTH), re.ASCII)'),
    "non-ASCII letters read as a kind": (NAMES, '"|".join(_BY_LENGTH), re.IGNORECASE | re.ASCII)', '"|".join(_BY_LENGTH), re.IGNORECASE)'),
    "non-ASCII digits parse": (NAMES, "    re.IGNORECASE | re.ASCII,\n)", "    re.IGNORECASE,\n)"),
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
    "User-Agent dropped from POST": (HTTP, '**(headers or {}), "User-Agent": self.user_agent, "Content-Type": FORM}', '**(headers or {}), "Content-Type": FORM}'),
    "headers given to POST dropped": (HTTP, '{**(headers or {}), "User-Agent"', '{"User-Agent"'),
    "a header given replaces the User-Agent or the Content-Type": (HTTP, '{**(headers or {}), "User-Agent": self.user_agent, "Content-Type": FORM}', '{"User-Agent": self.user_agent, "Content-Type": FORM, **(headers or {})}'),
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
    # chains: the adapter each chain gets (ruling R1)
    "Shufersal given another adapter": (CHAINS, "            return ShufersalSource()", "            return CarrefourSource()"),
    "an NCR chain given another adapter": (CHAINS, "            return NcrSource(chain.username)", "            return ShufersalSource()"),
    "Carrefour given another adapter": (CHAINS, "            return CarrefourSource()", "            return ShufersalSource()"),
    "NCR adapter given the slug as its username": (CHAINS, "NcrSource(chain.username)", "NcrSource(chain.slug)"),
    "one adapter shared between calls": (CHAINS, "            return CarrefourSource()", '            return globals().setdefault("_shared", CarrefourSource())'),
    "a portal outside version one given an adapter": (CHAINS, '    raise ValueError(f"no adapter for the {chain.portal!r} portal")', "    return ShufersalSource()"),
    # sources
    "Listed not frozen": (SOURCES, "@dataclass(frozen=True)\nclass Listed:", "@dataclass\nclass Listed:"),
    "Listed without its URL": (SOURCES, "    name: FileName\n    url: str\n", "    name: FileName\n"),
    "listing takes no kinds": (SOURCES, "def listing(self, http: Http, kinds: tuple[str, ...])", "def listing(self, http: Http)"),
    "download takes a URL, not the listed item": (SOURCES, "def download(self, http: Http, item: Listed)", "def download(self, http: Http, item: str)"),
    "download returns text": (SOURCES, ") -> bytes:", ") -> str:"),
    "ListingUnreadable is an HttpError": (SOURCES, "class ListingUnreadable(Exception):", 'class ListingUnreadable(__import__("collector.http").http.HttpError):'),
    "Source without its unparsed count": (SOURCES, "    unparsed: int  #", "    #"),
    # shufersal: paging (ruling R11) and one page at a time (R16)
    "stops after page 1": (SHUFERSAL, "    for page in range(2, last + 1):", "    for page in range(2, 2):"),
    "a page past the last read": (SHUFERSAL, "range(2, last + 1)", "range(2, last + 2)"),
    "last page taken from the > link": (SHUFERSAL, 'LAST_PAGE = ">>"', 'LAST_PAGE = ">"'),
    "pager text read with its entities": (SHUFERSAL, "super().__init__(convert_charrefs=True)", "super().__init__(convert_charrefs=False)"),
    "no pager read as two pages": (SHUFERSAL, "        return 1\n    if first.last_href is None:", "        return 2\n    if first.last_href is None:"),
    "pager without >> read as one page": (SHUFERSAL, '        raise ListingUnreadable(f"{kind} page 1: the pager names no last page")', "        return 1"),
    "last-page link naming two pages read as its first": (SHUFERSAL, "    if len(pages) != 1 or not pages[0].isdecimal():", "    if not pages or not pages[0].isdecimal():"),
    "last page that is no number escapes as ValueError": (SHUFERSAL, " or not pages[0].isdecimal():", ":"),
    "zero rows read as empty day": (SHUFERSAL, "    if not grid.rows:", "    if False:"),
    "all pages read before the first row": (SHUFERSAL, "    yield 1, first\n    for page in range(2, last + 1):\n        yield page, _page(http, kind, page)\n",
                                            "    rest = [(page, _page(http, kind, page)) for page in range(2, last + 1)]\n    yield 1, first\n    yield from rest\n"),
    "a page's rows given before all are checked": (SHUFERSAL, "            rows.append((name, _checked_link(cells[0].href, name, where)))\n        yield from rows\n",
                                                   "            yield name, _checked_link(cells[0].href, name, where)\n"),
    "listing URL without storeId=0": (SHUFERSAL, "&storeId=0&page={page}", "&page={page}"),
    "categories swapped": (SHUFERSAL, '"Promo": 3, "PromoFull": 4', '"Promo": 4, "PromoFull": 3'),
    # shufersal: rows and links (ruling R15)
    "row of another shape read": (SHUFERSAL, "            if len(cells) != CELLS:", "            if False:"),
    "name read from the branch cell": (SHUFERSAL, "NAME_CELL = 6", "NAME_CELL = 5"),
    "row without a link read": (SHUFERSAL, "    if not href:", "    if False:"),
    "link on another host accepted": (SHUFERSAL, '    return parts.scheme == "https" and parts.netloc == FILE_HOST', '    return parts.scheme == "https"'),
    "http link accepted": (SHUFERSAL, '    return parts.scheme == "https" and parts.netloc == FILE_HOST', "    return parts.netloc == FILE_HOST"),
    "link outside ASCII accepted": (SHUFERSAL, "    if not (href.isascii() and href.isprintable()) or", "    if not href.isprintable() or"),
    "control character in a link accepted": (SHUFERSAL, "    if not (href.isascii() and href.isprintable()) or", "    if not href.isascii() or"),
    "space in a link accepted": (SHUFERSAL, ' or " " in href:', ":"),
    "unsplittable link escapes as ValueError": (SHUFERSAL, "    except ValueError:\n        raise ListingUnreadable(malformed)", "    except TypeError:\n        raise ListingUnreadable(malformed)"),
    "link not matched to its row's name": (SHUFERSAL, '    if linked != f"{name}.gz":', "    if False:"),
    # shufersal: names
    "unparsed names not counted": (SHUFERSAL, "                    self.unparsed += 1", "                    pass"),
    "unparsed count carried over from the last listing": (SHUFERSAL, "        self.unparsed = 0\n        for kind in kinds:", "        for kind in kinds:"),
    "rows of another kind listed": (SHUFERSAL, "                elif name.kind in kinds:", "                else:"),
    # shufersal: expired links
    "expiry refresh on any 403": (SHUFERSAL, "        return expires is not None and expires - EXPIRY_SLACK <= self._now()", "        return True"),
    "refresh on any refusal from the file host": (SHUFERSAL, "if block.status != 403 or not _on_file_host", "if not _on_file_host"),
    "refresh on a 403 from another host": (SHUFERSAL, " or not _on_file_host(urllib.parse.urlsplit(block.url)):", ":"),
    "no refresh at the slack's edge": (SHUFERSAL, "expires - EXPIRY_SLACK <= self._now()", "expires - EXPIRY_SLACK < self._now()"),
    "slack removed": (SHUFERSAL, "expires - EXPIRY_SLACK <= self._now()", "expires <= self._now()"),
    "slack made unbounded": (SHUFERSAL, "EXPIRY_SLACK = timedelta(seconds=120)", "EXPIRY_SLACK = timedelta(days=3650)"),
    "slack widened by a second": (SHUFERSAL, "EXPIRY_SLACK = timedelta(seconds=120)", "EXPIRY_SLACK = timedelta(seconds=121)"),
    "se= read as Israel time": (SHUFERSAL, ".replace(tzinfo=timezone.utc)", '.replace(tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Jerusalem"))'),
    "default clock without a time zone": (SHUFERSAL, "    return datetime.now(timezone.utc)", "    return datetime.now()"),
    "unreadable se= escapes as ValueError": (SHUFERSAL, "    except (IndexError, ValueError):", "    except IndexError:"),
    "missing se= escapes as IndexError": (SHUFERSAL, "    except (IndexError, ValueError):", "    except ValueError:"),
    "refresh takes another file's link": (SHUFERSAL, "        if name_cell == item.name.raw:", "        if True:"),
    "refreshed link not used": (SHUFERSAL, "        return http.get(_fresh_link(http, item)).body", "        _fresh_link(http, item)\n        return http.get(item.url).body"),
    "refreshed more than once": (SHUFERSAL, "        return http.get(_fresh_link(http, item)).body", "        return self.download(http, Listed(item.name, _fresh_link(http, item)))"),
    "file gone after expiry read as unreadable": (SHUFERSAL, '    raise HttpError(f"{item.name.raw}: its link expired', '    raise ListingUnreadable(f"{item.name.raw}: its link expired'),
    # names a link is built from (ruling R19)
    "slash in a linked name accepted": (NAME_CHECK, 'UNSAFE = ("/", ', "UNSAFE = ("),
    "backslash in a linked name accepted": (NAME_CHECK, r'"\\", "..", ', '"..", '),
    "two dots in a linked name accepted": (NAME_CHECK, ', "..", ', ", "),
    "question mark in a linked name accepted": (NAME_CHECK, ', "?", ', ", "),
    "hash in a linked name accepted": (NAME_CHECK, ', "#")', ")"),
    "whitespace in a linked name accepted": (NAME_CHECK, " or any(char.isspace() for char in name)", ""),
    "only a plain space refused": (NAME_CHECK, "any(char.isspace() for char in name)", '" " in name'),
    "unsafe name counted as unparsed": (NAME_CHECK, '        raise ListingUnreadable(f"{where}: the file name {name!r} is not safe to put in a link")', "        return None"),
    # ncr: the login
    "NCR sends a password": (NCR, '"password": "", "Submit"', '"password": self.username, "Submit"'),
    "NCR sends no username": (NCR, '"username": self.username, ', '"username": "", '),
    "login without the login page's token": (NCR, '"Submit": "Sign in", "csrftoken": token}', '"Submit": "Sign in"}'),
    "login page without a token posted anyway": (NCR, 'raise ListingUnreadable("the NCR login page carries no csrftoken")', "pass"),
    "failed login treated as success": (NCR, "        if path not in FILE_BROWSER or page.login_form:", "        if False:"),
    "landing elsewhere than /file accepted": (NCR, "if path not in FILE_BROWSER or page.login_form:", "if page.login_form:"),
    "login form on the file browser accepted": (NCR, "if path not in FILE_BROWSER or page.login_form:", "if path not in FILE_BROWSER:"),
    "landing on /file/ refused": (NCR, 'FILE_BROWSER = ("/file", "/file/")', 'FILE_BROWSER = ("/file",)'),
    "landing path matched by its start": (NCR, "if path not in FILE_BROWSER or page.login_form:", 'if not path.startswith("/file") or page.login_form:'),
    "login form seen by its id alone": (NCR, '(attrs.get("id") == "login-form" or attrs.get("action") == "/login/user")', 'attrs.get("id") == "login-form"'),
    "login form seen by its action alone": (NCR, '(attrs.get("id") == "login-form" or attrs.get("action") == "/login/user")', 'attrs.get("action") == "/login/user"'),
    "NCR username not required": (NCR, "        if not username:", "        if False:"),
    # ncr: the file page and the listing request
    "listing sent the login page's token": (NCR, "        return page\n", "        page.csrftoken = token\n        return page\n"),
    "file page without a token accepted": (NCR, 'raise ListingUnreadable("the NCR file page carries no csrftoken")', "pass"),
    "listing request without the token": (NCR, ', "cd": ROOT, "csrftoken": token}', ', "cd": ROOT}'),
    "directory other than / accepted": (NCR, "    if file_page.cd != ROOT:", "    if False:"),
    "file page without a directory read as another directory": (NCR, "    if file_page.cd is None:", "    if False:"),
    "page size not taken from the file page": (NCR, '"iDisplayLength": str(length)}', '"iDisplayLength": "10000"}'),
    "page size of 0 accepted": (NCR, "if type(length) is not int or length < 1:", "if type(length) is not int:"),
    "true accepted as a page size": (NCR, "if type(length) is not int or length < 1:", "if not isinstance(length, int) or length < 1:"),
    "settings not JSON escape as ValueError": (NCR, "    except ValueError:\n        raise ListingUnreadable(\"the NCR file page's data-cftp", "    except TypeError:\n        raise ListingUnreadable(\"the NCR file page's data-cftp"),
    "listing sent without X-Requested-With": (NCR, ", headers=AJAX).body", ").body"),
    "a column's sorting flag changed": (NCR, '("typeLabel", "false")', '("typeLabel", "true")'),
    # ncr: paging (ruling R18) and the answer
    "paging stops after the first answer": (NCR, "    while total is None or len(fnames) < total:", "    for _ in range(1):"),
    "paging restarts from the first entry": (NCR, "_form(len(fnames), length, token)", "_form(0, length, token)"),
    "empty answer before the total read as the end": (NCR, '            raise ListingUnreadable(f"the NCR listing stopped at', '            break\n            raise ListingUnreadable(f"the NCR listing stopped at'),
    "zero total read as an empty day": (NCR, "            if total < 1:", "            if False:"),
    "a name sent again read on": (NCR, "        if repeated is not None:", "        if False:"),
    "listing not JSON escapes as ValueError": (NCR, "    except ValueError:  # bad JSON", "    except TypeError:  # bad JSON"),
    "true accepted as a total": (NCR, "or type(total) is not int:", "or not isinstance(total, int):"),
    "entry without a file name read": (NCR, "        if not isinstance(fname, str):", "        if False:"),
    "link built from another field": (NCR, 'fname = entry.get("fname")', 'fname = entry.get("value")'),
    "download link not under /file/d/": (NCR, 'DOWNLOAD = f"{BASE_URL}/file/d/"', 'DOWNLOAD = f"{BASE_URL}/file/"'),
    # ncr: names and kinds
    "NCR kinds filter ignored": (NCR, "            elif name.kind in kinds:", "            else:"),
    "NCR names not checked": (NCR, 'checked_name(fname, f"the NCR listing, entry {number}")', '__import__("collector.names").names.parse_file_name(fname)'),
    "NCR names checked only as they are given": (NCR, "                listed.append(Listed(name, DOWNLOAD + fname))\n        yield from listed\n", "                yield Listed(name, DOWNLOAD + fname)\n"),
    "NCR unparsed names not counted": (NCR, "                self.unparsed += 1", "                pass"),
    "NCR unparsed count carried over from the last listing": (NCR, "        self.unparsed = 0\n        file_page", "        file_page"),
    "NCR download returns nothing": (NCR, "        return http.get(item.url).body", '        return b""'),
    # carrefour
    "Carrefour listing not today's page": (CARREFOUR, 'http.get(f"{BASE_URL}/")', 'http.get(f"{BASE_URL}/?date=20261031")'),
    "Carrefour kinds filter ignored": (CARREFOUR, "            elif parsed.kind in kinds:", "            else:"),
    "zero Carrefour files read as an empty day": (CARREFOUR, "    if not files:", "    if False:"),
    "Carrefour path not checked": (CARREFOUR, "    if not DAY.fullmatch(found.group(1)):", "    if False:"),
    "Carrefour path read in part": (CARREFOUR, "DAY.fullmatch(found.group(1))", "DAY.match(found.group(1))"),
    "other scripts' digits taken in the Carrefour path": (CARREFOUR, 'DAY = re.compile(r"[0-9]{8}")', r'DAY = re.compile(r"\d{8}")'),
    "Carrefour link without the day's folder": (CARREFOUR, 'f"{BASE_URL}/{folder}/{name}"', 'f"{BASE_URL}/{name}"'),
    "page without const path escapes as AttributeError": (CARREFOUR, '    if found is None:\n        raise ListingUnreadable("the Carrefour page has no const path")', '    if False:\n        raise ListingUnreadable("the Carrefour page has no const path")'),
    "page without const files escapes as AttributeError": (CARREFOUR, '    if found is None:\n        raise ListingUnreadable("the Carrefour page has no const files")', '    if False:\n        raise ListingUnreadable("the Carrefour page has no const files")'),
    "Carrefour files not JSON escape as ValueError": (CARREFOUR, "    except ValueError:", "    except TypeError:"),
    "Carrefour files that are not a list read": (CARREFOUR, "    if not isinstance(files, list):", "    if False:"),
    "Carrefour file without a name read": (CARREFOUR, "        if not isinstance(name, str):", "        if False:"),
    "Carrefour names not checked": (CARREFOUR, 'checked_name(name, f"the Carrefour page, file {number}")', '__import__("collector.names").names.parse_file_name(name)'),
    "Carrefour names checked only as they are given": (CARREFOUR, '                listed.append(Listed(parsed, f"{BASE_URL}/{folder}/{name}"))\n        yield from listed\n', '                yield Listed(parsed, f"{BASE_URL}/{folder}/{name}")\n'),
    "Carrefour unparsed names not counted": (CARREFOUR, "                self.unparsed += 1", "                pass"),
    "Carrefour unparsed count carried over from the last listing": (CARREFOUR, "        self.unparsed = 0\n        text", "        text"),
    "Carrefour download returns nothing": (CARREFOUR, "        return http.get(item.url).body", '        return b""'),
    # store: the brief's four
    "IfNoneMatch dropped": (STORE, '                IfNoneMatch="*",\n', ""),
    "conflict overwrites": (STORE, "        if self._put_locked(copy, body, until):\n            return PutOutcome.CONFLICT_STORED",
                            "        self._put_plain(key, body, None)\n        if True:\n            return PutOutcome.CONFLICT_STORED"),
    "identical re-run makes a conflict copy": (STORE, "        if self._sha256(key) == digest:\n            return PutOutcome.EXISTS\n", "        if False:\n            return PutOutcome.EXISTS\n"),
    "retention shortened": (STORE, "RETENTION_DAYS = 3650", "RETENTION_DAYS = 365"),
    # store: the lock
    "lock mode not governance": (STORE, 'LOCK_MODE = "GOVERNANCE"', 'LOCK_MODE = "COMPLIANCE"'),
    "lock mode argument ignored": (STORE, "ObjectLockMode=self.lock_mode,", "ObjectLockMode=LOCK_MODE,"),
    "retention argument ignored": (STORE, "self.retention = timedelta(days=retention_days)", "self.retention = timedelta(days=RETENTION_DAYS)"),
    "zero retention accepted": (STORE, "        if retention_days < 1:", "        if retention_days < 0:"),
    "ChecksumAlgorithm dropped": (STORE, '                ChecksumAlgorithm="SHA256",\n', ""),
    "naive time accepted": (STORE, "        if now.tzinfo is None or now.utcoffset() is None:", "        if False:"),
    "record not locked": (STORE, '        if self._put_locked(key, body, self._retain_until(now), "application/json"):\n            return',
                          '        self._put_plain(key, body, "application/json")\n        if True:\n            return'),
    "MemoryStore overwrites": (STORE, "        if key in self.objects:\n            return False\n", ""),
    "MemoryStore lock not recorded": (STORE, "Stored(bytes(body), self.lock_mode, until)", "Stored(bytes(body), None, None)"),
    # store: refusals (412 and 409) and what the key holds
    "412 not read as already there": (STORE, 'REFUSED = ("PreconditionFailed", "ConditionalRequestConflict")', 'REFUSED = ("ConditionalRequestConflict",)'),
    "409 not read as already there": (STORE, 'REFUSED = ("PreconditionFailed", "ConditionalRequestConflict")', 'REFUSED = ("PreconditionFailed",)'),
    "any put error read as already there": (STORE, "            if _code(err) in REFUSED:\n                return False\n            raise", "            return False"),
    "stored checksum not asked for": (STORE, ', ChecksumMode="ENABLED")', ")"),
    "no checksum read as a different body": (STORE, "        return hashlib.sha256(self.read_raw(key)).hexdigest()", '        return ""'),
    "conflict copy named without its hash": (STORE, 'copy = f"{key}.{digest[:12]}"', "copy = key"),
    "conflict copy's hash cut short": (STORE, 'copy = f"{key}.{digest[:12]}"', 'copy = f"{key}.{digest[:8]}"'),
    "conflict copy named by the stored body": (STORE, 'copy = f"{key}.{digest[:12]}"', 'copy = f"{key}.{self._sha256(key)[:12]}"'),
    "same changed body on a re-run raises": (STORE, "        if self._sha256(copy) == digest:", "        if False:"),
    "collision on the conflict copy read as exists": (STORE, '        raise AlreadyStored(f"{copy}:', '        return PutOutcome.EXISTS\n        raise AlreadyStored(f"{copy}:'),
    "different record under a taken key passes": (STORE, "        if self._sha256(key) != hashlib.sha256(body).hexdigest():", "        if False:"),
    "retried identical record raises": (STORE, "        if self._sha256(key) != hashlib.sha256(body).hexdigest():", "        if True:"),
    # store: listing
    "only the first page listed": (STORE, '        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):',
                                   "        for page in [self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)]:"),
    "conflict copy not mapped back": (STORE, '    return copy["name"] if copy else name', "    return name"),
    "suffix of any length read as a conflict copy": (STORE, r'\.[0-9a-f]{12}")', r'\.[0-9a-f]+")'),
    "upper-case suffix read as a conflict copy": (STORE, r'\.[0-9a-f]{12}")', r'\.[0-9a-fA-F]{12}")'),
    "conflict copy suffix matched from the start only": (STORE, "_CONFLICT_COPY.fullmatch(name)", "_CONFLICT_COPY.match(name)"),
    "records out of key order": (STORE, "for key in sorted(self._keys(prefix))]", "for key in self._keys(prefix)]"),
    # store: state
    "state write made write-once": (STORE, "Body=body, ContentType=content_type)", 'Body=body, ContentType=content_type, IfNoneMatch="*")'),
    "a delete before the state write": (STORE, "        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)",
                                        "        self.client.delete_object(Bucket=self.bucket, Key=key)\n        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)"),
    "missing state as NoSuchKey read as an error": (STORE, 'MISSING = ("NoSuchKey", "404")', 'MISSING = ("404",)'),
    "missing state as a bare 404 read as an error": (STORE, 'MISSING = ("NoSuchKey", "404")', 'MISSING = ("NoSuchKey",)'),
    "any read error read as missing": (STORE, "            if _code(err) in MISSING:\n                return None\n            raise", "            return None"),
    # store: keys
    "raw key without chain=": (STORE, 'f"raw/chain={slug}/', 'f"raw/{slug}/'),
    "raw key's day not ISO": (STORE, 'f"raw/chain={slug}/date={day.isoformat()}/{name}"', 'f"raw/chain={slug}/date={day:%Y%m%d}/{name}"'),
    "manifest key without the slug": (STORE, '/{slug}-{run_id}.json"', '/{run_id}.json"'),
    "check key without check-": (STORE, '/check-{run_id}.json"', '/{run_id}.json"'),
    "state key outside state/": (STORE, 'f"state/{slug}.json"', 'f"{slug}.json"'),
    # run: the brief's five
    "clock date instead of file date": (RUN, "        if item.name.day != self.day or", "        if _utc(self.now()).date() != self.day or"),
    "stored files fetched again": (RUN, "        if name in self.stored:\n            return\n", ""),
    "no latch on block": (RUN, '        self.store.write_state(self.slug, {"stopped": True,', '        (self.slug, {"stopped": True,'),
    "timeout guard removed": (RUN, "            if self._short_of_time():\n                if problem is None:", "            if False:\n                if problem is None:"),
    "manifest skipped on error": (RUN, "        store.put_record(manifest_key(", "        result.error is None and store.put_record(manifest_key("),
    # run: choosing that day's files
    "older files selected": (RUN, "        if item.name.day != self.day or", "        if item.name.day > self.day or"),
    "kinds not filtered again": (RUN, " or item.name.kind not in self.kinds:", ":"),
    "unknown kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(KINDS):", "    if not kinds:"),
    "no kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(KINDS):", "    if not set(kinds) <= set(KINDS):"),
    "kinds not recorded (R4)": (RUN, "RunResult(chain.slug, run_id, mode, day, list(kinds))", "RunResult(chain.slug, run_id, mode, day, [])"),
    "stored name taken from the listing, not the link (R16)": (RUN, "        name = stored_name(item)\n", "        name = item.name.raw\n"),
    "stored name keeps the link's query (R16)": (RUN, '    return urllib.parse.urlsplit(item.url).path.rsplit("/", 1)[-1]', '    return item.url.rsplit("/", 1)[-1]'),
    "skipped names not listed": (RUN, "        self.result.listed.append(name)\n        if name in self.stored:\n            return\n",
                                 "        if name in self.stored:\n            return\n        self.result.listed.append(name)\n"),
    "a name listed twice fetched again": (RUN, "        if name in self.seen:\n            return  #", "        if False:\n            return  #"),
    # run: the listing
    "listing read before the files are fetched (R16)": (RUN, "            listing = iter(self.source.listing(self.http, self.kinds))", "            listing = iter(list(self.source.listing(self.http, self.kinds)))"),
    "listing read twice": (RUN, "            listing = iter(self.source.listing(self.http, self.kinds))",
                           "            listing = iter(self.source.listing(self.http, self.kinds)) if list(self.source.listing(self.http, self.kinds)) or True else None"),
    "listing_read_at in local time": (RUN, "self.result.listing_read_at = _utc(self.now()).isoformat()", "self.result.listing_read_at = self.now().isoformat()"),
    "unparsed not recorded (R13)": (RUN, "            self.result.unparsed = self.source.unparsed  #", "            pass  #"),
    "unparsed read before the listing is used up (R13)": (RUN, "                self._take(item)\n                self._check_time()\n            self.result.unparsed = self.source.unparsed  # final only now: it resets on the first next()\n",
                                                          "                self.result.unparsed = self.source.unparsed\n                self._take(item)\n                self._check_time()\n"),
    "unparsed taken from an unfinished listing (R13)": (RUN, "        except _Stop:\n            pass", "        except _Stop:\n            self.result.unparsed = self.source.unparsed"),
    "block in the listing escapes": (RUN, "        except Blocked as block:\n            self._latch(str(block))", "        except ZeroDivisionError as block:\n            self._latch(str(block))"),
    "unreadable listing escapes (R23)": (RUN, "        except ListingUnreadable as exc:\n", "        except ZeroDivisionError as exc:\n"),
    "unreadable listing not recorded as an error (R23)": (RUN, '            self._stop(f"listing unreadable: {exc}")\n        except HttpError', "            raise _Stop\n        except HttpError"),
    "listing HTTP error escapes": (RUN, "        except HttpError as exc:  # not read again", "        except ZeroDivisionError as exc:  # not read again"),
    "listing HTTP error not recorded as an error": (RUN, '            self._stop(f"listing failed: {exc}")', "            raise _Stop"),
    # run: blocks and the latch
    "stopped chain collected": (RUN, '        if store.read_state(chain.slug).get("stopped"):', "        if False:"),
    "any state read as stopped": (RUN, 'if store.read_state(chain.slug).get("stopped"):', "if store.read_state(chain.slug):"),
    "a block does not stop the run": (RUN, "        self.result.blocked = reason\n        raise _Stop", "        self.result.blocked = reason"),
    "latch since in local time": (RUN, '"since": _utc(self.now()).isoformat(),', '"since": self.now().isoformat(),'),
    "latch already alerted": (RUN, '"reason": reason, "alerted": False}', '"reason": reason, "alerted": True}'),
    "latch without its reason": (RUN, '"reason": reason, "alerted"', '"reason": "", "alerted"'),
    "HTML retried instead of latched": (RUN, "            if looks_like_html(data):\n", "            if False:\n"),
    "blocked file not recorded as failed": (RUN, "        self.result.failed[name] = reason\n        self._latch(reason)", "        self._latch(reason)"),
    # run: one retry
    "a file not tried again": (RUN, "ATTEMPTS = 2", "ATTEMPTS = 1"),
    "a file tried three times": (RUN, "ATTEMPTS = 2", "ATTEMPTS = 3"),
    "HTTP error on a download escapes": (RUN, "            except HttpError as exc:\n                problem", "            except ZeroDivisionError as exc:\n                problem"),
    "bad payload escapes": (RUN, "            except BadPayload as exc:", "            except ZeroDivisionError as exc:"),
    "payload not checked": (RUN, "                check_payload(name, data)", "                pass"),
    "failed file not recorded": (RUN, "        self.result.failed[name] = problem\n", ""),
    "unreadable listing from a download escapes (R23)": (RUN, "            except ListingUnreadable as exc:  # Shufersal's", "            except ZeroDivisionError as exc:  # Shufersal's"),
    "a failed put stops the run (R23)": (RUN, "        except Exception as exc:  # a storage hiccup", "        except ZeroDivisionError as exc:  # a storage hiccup"),
    "files entry's SHA-256 not the body's": (RUN, '"sha256": hashlib.sha256(data).hexdigest()', '"sha256": hashlib.sha256(name.encode()).hexdigest()'),
    "files entry's size not the body's": (RUN, '"size": len(data),', '"size": len(name),'),
    # run: time (R23)
    "time guard at 0 s": (RUN, "MIN_TIME_LEFT = 60.0", "MIN_TIME_LEFT = 0.0"),
    "sixty seconds left read as too few": (RUN, "        return self.time_left() < MIN_TIME_LEFT", "        return self.time_left() <= MIN_TIME_LEFT"),
    "time not checked before the listing": (RUN, "            self._check_time()\n            self.result.listing_read_at", "            self.result.listing_read_at"),
    "time not checked between listing items": (RUN, "                self._take(item)\n                self._check_time()\n", "                self._take(item)\n"),
    "not attempted not recorded": (RUN, "                    self.result.not_attempted.append(name)", "                    pass"),
    "retry tried with under 60 s left": (RUN, "            if self._short_of_time():\n", "            if problem is None and self._short_of_time():\n"),
    "failed first try recorded as not attempted": (RUN, "                if problem is None:\n", "                if True:\n"),
    # run: the manifest and run ids
    "manifest under another run's key": (RUN, "manifest_key(day, chain.slug, run_id)", 'manifest_key(day, chain.slug, "run")'),
    "manifest without the code's commit": (RUN, ', "code_sha": code_sha}', "}"),
    "manifest keys unsorted": (RUN, "json.dumps(record, sort_keys=True, indent=1)", "json.dumps(record, indent=1)"),
    "manifest day not ISO": (RUN, '{"day": result.day.isoformat(), ', '{"day": f"{result.day:%Y%m%d}", '),
    "unexpected error not recorded": (RUN, '        result.error = f"unexpected error: {type(exc).__name__}: {exc}"\n', ""),
    "unexpected error swallowed": (RUN, '{exc}"\n        raise\n    finally:', '{exc}"\n    finally:'),
    "naive time accepted by the run loop": (RUN, "    if moment.tzinfo is None or moment.utcoffset() is None:", "    if False:"),
    "run id in local time": (RUN, 'f"{_utc(now):%H%M%S}Z-', 'f"{now:%H%M%S}Z-'),
    "run id without its random part": (RUN, "-{secrets.token_hex(2)}", "-0000"),
    "run id's random part not four hex": (RUN, "secrets.token_hex(2)", "secrets.token_hex(3)"),
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

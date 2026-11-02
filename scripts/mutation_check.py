"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py            # every mutation
    .venv/bin/python scripts/mutation_check.py "HTML"     # only those whose name contains one of the arguments

Each mutation names the file it breaks and the test files that must catch it. It edits source files
in place while it runs: run nothing else from this checkout until it finishes. Files are restored
afterwards. Exit code 1 if any mutation goes unnoticed, or if its text to break is not found exactly
once (the script is out of date). Exit code 2, before anything runs, if two entries share a name: the
dict literal would keep only the last, and the first would never run.

Copied from flights-archive's harness, with one change: the test runs write no bytecode. Python
trusts a cached .pyc whose source has the same size and the same whole-second mtime, so a
same-length mutation written and restored within one second could otherwise leave the broken code
cached for the next run.
"""
import ast
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
CHECK = ("src/collector/check.py", ["tests/test_check.py"])
STORE_FOR_CHECK = ("src/collector/store.py", ["tests/test_check.py"])
HANDLER = ("src/collector/handler.py", ["tests/test_handler.py"])
TEMPLATE = ("template.yaml", ["tests/test_template.py"])
OPERATIONS = ("docs/operations.md", ["tests/test_template.py"])
# Rules the R7/R30 table in test_template.py also pins: each of these names the one test that must
# catch it by itself, so the rule's own test is proved, not only the table.
_T = "tests/test_template.py::"
R7_TABLE = ("template.yaml", [_T + "test_schedules_are_rulings_r7_and_r30"])
ONE_MINUTE_EACH = ("template.yaml", [_T + "test_no_two_schedules_share_a_start_minute"])
ONE_RUN_AT_A_TIME = ("template.yaml", [_T + "test_one_chain_never_runs_twice_at_once"])
ONE_HOST_AT_A_TIME = ("template.yaml", [_T + "test_one_portal_host_never_serves_two_runs_at_once"])
RETRY_THREE_HOURS_ON = ("template.yaml", [_T + "test_retry_runs_start_three_hours_after_the_first_main_run_of_their_kinds"])
CHECK_LAST = ("template.yaml", [_T + "test_one_check_after_the_last_retry_run_can_have_finished"])
ALL_KINDS = ("template.yaml", [_T + "test_each_chain_has_runs_of_each_mode_over_the_kinds_it_collects"])
HANDLER_EVENTS = ("template.yaml", [_T + "test_every_event_is_one_the_handler_takes"])
BARCODE = ("src/basket/barcode.py", ["tests/test_barcode.py"])

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
    "a bare <Root> refused": (PAYLOAD, 'UTF8_BOM + b"<Root>", b"<Root>", ', 'UTF8_BOM + b"<Root>", '),
    "a zip read as neither gzip nor XML": (PAYLOAD, "    if data.startswith(ZIP_MAGICS):\n        _check_zip(name, data)\n    elif data.startswith(GZIP_MAGIC):", "    if data.startswith(GZIP_MAGIC):"),
    "an empty archive not read as a zip": (PAYLOAD, 'ZIP_MAGICS = (b"PK\\x03\\x04", b"PK\\x05\\x06")', 'ZIP_MAGICS = (b"PK\\x03\\x04",)'),
    "zip members not read through": (PAYLOAD, "                with archive.open(member) as body:\n                    while body.read(READ_CHUNK):\n                        pass\n", "                pass\n"),
    "zip members read through by name": (PAYLOAD, "                with archive.open(member) as body:", "                with archive.open(member.filename) as body:"),
    "a refusal's member names not cut": (PAYLOAD, "return ascii(member[:NAME_CHARS])", "return ascii(member)"),
    "a refusal's error text not cut": (PAYLOAD, "return ascii(text[:limit])[1:-1]", "return ascii(text)[1:-1]"),
    "zip errors beyond zipfile's own escape": (PAYLOAD, "    except Exception as exc:  # untrusted bytes", "    except (zipfile.BadZipFile, OSError) as exc:  # untrusted bytes"),
    "a zip's folder entries checked as files": (PAYLOAD, "if not member.is_dir()]", "]"),
    "a zip error's text shown raw": (PAYLOAD, "{_cut(str(exc), ERROR_CHARS)}", "{exc}"),
    "an empty zip accepted": (PAYLOAD, '    if not members:\n        raise BadPayload(f"{name}: the zip holds no file")\n', ""),
    "a zip member not checked for XML": (PAYLOAD, "if not head.startswith(XML_STARTS)]", "if False]"),
    "zip member names shown raw": (PAYLOAD, "{_quoted(member)} starts", "{member} starts"),
    "every non-XML zip member named": (PAYLOAD, "not_xml[:SHOWN_MEMBERS])", "not_xml)"),
    "a zip refusal counts no further members": (PAYLOAD, 'more = f" and {len(not_xml) - SHOWN_MEMBERS} more" if', 'more = "" if'),
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
    "Shufersal waits only 30 s": (CHAINS, '"https://prices.shufersal.co.il", timeout=60.0,', '"https://prices.shufersal.co.il",'),
    "Shufersal collects every kind": (CHAINS, '\n          kinds=("Stores", "PriceFull", "PromoFull")),', "),"),
    "chains collect only the full files by default": (CHAINS, "    kinds: tuple[str, ...] = KINDS\n", '    kinds: tuple[str, ...] = ("Stores", "PriceFull", "PromoFull")\n'),
    "chains wait 60 s by default": (CHAINS, "    timeout: float = 30.0\n", "    timeout: float = 60.0\n"),
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
    "listing sent without Accept": (NCR, ', "Accept": "application/json, text/javascript, */*; q=0.01"}', "}"),
    "unreadable listing error without its layout": (NCR, ' count (it held {_held(data)})")', ' count")'),
    "unreadable listing error shows a value": (NCR, 'return f"a {_type(data)}"', 'return f"a {data!r}"'),
    "unreadable listing error shows a key's value": (NCR, ": {_type(data[key])}", ": {data[key]!r}"),
    "unreadable listing error names every key": (NCR, "for key in keys[:SHOWN_KEYS])", "for key in keys)"),
    "unreadable listing error counts no further keys": (NCR, 'more = f" and {len(keys) - SHOWN_KEYS} more" if', 'more = "" if'),
    "unreadable listing error shows keys raw": (NCR, "{ascii(key[:KEY_CHARS] + '...' if len(key) > KEY_CHARS else key)}", "{key[:KEY_CHARS] + '...' if len(key) > KEY_CHARS else key}"),
    "unreadable listing error keeps long keys whole": (NCR, "key[:KEY_CHARS] + '...' if len(key) > KEY_CHARS else key", "key"),
    "unreadable listing error names null NoneType": (NCR, '    if value is None:\n        return "null"\n', ""),
    "unreadable listing error calls an object a dict": (NCR, 'return "object" if isinstance(value, dict) else', "return"),
    "unreadable listing error lists an empty object's keys": (NCR, '    if not data:\n        return "an object with no keys"\n', ""),
    "a column's sorting flag changed": (NCR, '("typeLabel", "false")', '("typeLabel", "true")'),
    # ncr: paging (ruling R18) and the answer
    "paging stops after the first answer": (NCR, "    while total is None or len(fnames) < total:", "    for _ in range(1):"),
    "paging restarts from the first entry": (NCR, "_form(len(fnames), length, token)", "_form(0, length, token)"),
    "empty answer before the total read as the end": (NCR, '            raise ListingUnreadable(f"the NCR listing stopped at', '            break\n            raise ListingUnreadable(f"the NCR listing stopped at'),
    "zero total read as an empty day": (NCR, "            if total < 1:", "            if False:"),
    "a name sent again read on": (NCR, "        if repeated is not None:", "        if False:"),
    "a repeated name stops the listing at once": (NCR, "    try:\n        fnames, repeat = _read_through(http, length, token, username)\n", "    raise ListingUnreadable(repeat)\n    try:\n        fnames, repeat = _read_through(http, length, token, username)\n"),
    "the read again goes unlogged": (NCR, '    log.warning("the NCR listing as %r sent %s; reading it again from the start, once", username, repeat)\n', ""),
    "a repeat on the second read accepted": (NCR, '    raise ListingUnreadable(f"the NCR listing repeated a name on two reads from the start: {repeat}")', "    return fnames"),
    "an error on the second read unmarked": (NCR, 'raise ListingUnreadable(f"on the second read from the start, after a repeated name: {exc}") from None', "raise"),
    "a listing answer goes unlogged": (NCR, '        log.info("the NCR listing as %r answered from iDisplayStart %d: %d entries of the %d asked for; total %d",\n                 username, len(fnames), len(received), length, count)\n', ""),
    "listing not JSON escapes as ValueError": (NCR, "    except ValueError:  # bad JSON", "    except TypeError:  # bad JSON"),
    "true accepted as a total": (NCR, "    if type(value) is int:  # not isinstance", "    if isinstance(value, int):  # not isinstance"),
    "a total sent as text refused": (NCR, "    if isinstance(value, str) and TOTAL_TEXT.fullmatch(value):\n        return int(value)\n", ""),
    "any digit text read as a total": (NCR, "TOTAL_TEXT.fullmatch(value)", "value.isdigit()"),
    "a total text of any length read": (NCR, 're.compile(r"[0-9]{1,9}")', 're.compile(r"[0-9]+")'),
    "a total text matched at its start only": (NCR, "TOTAL_TEXT.fullmatch(value)", "TOTAL_TEXT.match(value)"),
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
    "no latch on block": (RUN, '            self.store.write_state(self.slug, {"stopped": True,', '            (self.slug, {"stopped": True,'),
    "timeout guard removed": (RUN, "            if self._short_of_time():\n                if problem is None:", "            if False:\n                if problem is None:"),
    "manifest skipped on error": (RUN, "        store.put_record(manifest_key(", "        result.error is None and store.put_record(manifest_key("),
    # run: choosing that day's files
    "older files selected": (RUN, "        if item.name.day != self.day or", "        if item.name.day > self.day or"),
    "kinds not filtered again": (RUN, " or item.name.kind not in self.kinds:", ":"),
    "unknown kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(chain.kinds):", "    if not kinds:"),
    "no kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(chain.kinds):", "    if not set(kinds) <= set(chain.kinds):"),
    "kinds the chain does not collect accepted": (RUN, "set(kinds) <= set(chain.kinds)", "set(kinds) <= {'Stores', 'PriceFull', 'PromoFull', 'Price', 'Promo'}"),
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
    "a block does not stop the run": (RUN, "            raise\n        raise _Stop\n", "            raise\n"),
    "latch since in local time": (RUN, '"since": _utc(self.now()).isoformat(),', '"since": self.now().isoformat(),'),
    "latch already alerted": (RUN, '"reason": reason, "alerted": False}', '"reason": reason, "alerted": True}'),
    "latch without its reason": (RUN, '"reason": reason, "alerted"', '"reason": "", "alerted"'),
    "HTML retried instead of latched": (RUN, "            if looks_like_html(data):\n", "            if False:\n"),
    "block recorded only once the latch is written": (RUN, "        self.result.blocked = reason  # first: the manifest may be the only record of what the portal did\n        try:\n            self.store.write_state(self.slug, {\"stopped\": True, \"since\": _utc(self.now()).isoformat(),\n                                               \"reason\": reason, \"alerted\": False})\n",
                                                       "        try:\n            self.store.write_state(self.slug, {\"stopped\": True, \"since\": _utc(self.now()).isoformat(),\n                                               \"reason\": reason, \"alerted\": False})\n            self.result.blocked = reason\n"),
    "latch failure not recorded": (RUN, '            self.result.error = f"latch not written: {type(exc).__name__}: {exc}"\n', "            pass\n"),
    "latch failure swallowed": (RUN, '{exc}"\n            raise\n        raise _Stop', '{exc}"\n        raise _Stop'),
    "latch failure overwritten by the unexpected-error text": (RUN, "        if result.error is None:  # a latch", "        if True:  # a latch"),
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
    "time guard at 0 s": (RUN, "MIN_TIME_LEFT = 90.0", "MIN_TIME_LEFT = 0.0"),
    "time guard back at the old 60 s (R32)": (RUN, "MIN_TIME_LEFT = 90.0", "MIN_TIME_LEFT = 60.0"),
    "ninety seconds left read as too few": (RUN, "        return self.time_left() < MIN_TIME_LEFT", "        return self.time_left() <= MIN_TIME_LEFT"),
    "time not checked before the listing": (RUN, "            self._check_time()\n            self.result.listing_read_at", "            self.result.listing_read_at"),
    "time not checked between listing items": (RUN, "                self._take(item)\n                self._check_time()\n", "                self._take(item)\n"),
    "not attempted not recorded": (RUN, "                    self.result.not_attempted.append(name)", "                    pass"),
    "retry tried with under 90 s left": (RUN, "            if self._short_of_time():\n", "            if problem is None and self._short_of_time():\n"),
    "failed first try recorded as not attempted": (RUN, "                if problem is None:\n", "                if True:\n"),
    # run: the manifest and run ids
    "manifest under another run's key": (RUN, "manifest_key(day, chain.slug, run_id)", 'manifest_key(day, chain.slug, "run")'),
    "manifest without the code's commit": (RUN, ', "code_sha": code_sha}', "}"),
    "manifest keys unsorted": (RUN, "json.dumps(record, sort_keys=True, indent=1)", "json.dumps(record, indent=1)"),
    "manifest day not ISO": (RUN, '{"day": result.day.isoformat(), ', '{"day": f"{result.day:%Y%m%d}", '),
    "unexpected error not recorded": (RUN, '            result.error = f"unexpected error: {type(exc).__name__}: {exc}"\n', "            pass\n"),
    "unexpected error swallowed": (RUN, '{exc}"\n        raise\n    finally:', '{exc}"\n    finally:'),
    "naive time accepted by the run loop": (RUN, "    if moment.tzinfo is None or moment.utcoffset() is None:", "    if False:"),
    "run id in local time": (RUN, 'f"{_utc(now):%H%M%S}Z-', 'f"{now:%H%M%S}Z-'),
    "run id without its random part": (RUN, "-{secrets.token_hex(2)}", "-0000"),
    "run id's random part not four hex": (RUN, "secrets.token_hex(2)", "secrets.token_hex(3)"),
    # check: listed and not stored
    "missing files not alerted": (CHECK, '    if missing:\n        alerts.append(Alert(slug, "missing"', '    if False:\n        alerts.append(Alert(slug, "missing"'),
    "an alert per missing file": (CHECK, '    if missing:\n        alerts.append(Alert(slug, "missing", _missing_text(slug, day, missing)))',
                                  '    for name in missing:\n        alerts.append(Alert(slug, "missing", _missing_text(slug, day, [name])))'),
    "every missing name in the alert": (CHECK, "{', '.join(missing[:MAX_NAMES])}{tail}", "{', '.join(missing)}{tail}"),
    "the record holds only ten missing names": (CHECK, '        "missing": missing,', '        "missing": missing[:MAX_NAMES],'),
    "only the retry's names checked": (CHECK, 'listed = {name for manifest in manifests for name in manifest["listed"]}',
                                       'listed = {name for manifest in manifests if manifest["mode"] == "retry" for name in manifest["listed"]}'),
    "missing judged against another day's files": (CHECK, "    stored = store.stored_names(slug, day)\n", "    stored = store.stored_names(slug, day - timedelta(days=1))\n"),
    "manifests of every day read": (CHECK, '    prefix = manifest_key(day, "", "").rsplit("/", 1)[0] + "/"', '    prefix = "manifests/"'),
    "a chain reads every chain's manifests": (CHECK, "_check_chain(store, slug, day, manifests.get(slug, []), expected)",
                                              "_check_chain(store, slug, day, [m for ms in manifests.values() for m in ms], expected)"),
    "the check ignores the kinds it is given": (CHECK, "(kinds or {}).get(slug, KINDS)", "KINDS"),
    "a chain left out of kinds held to none": (CHECK, "(kinds or {}).get(slug, KINDS)", "(kinds or {}).get(slug, ())"),
    "uncovered kinds read from all five, not the chain's": (CHECK, "    uncovered = [kind for kind in kinds if kind not in covered]", "    uncovered = [kind for kind in KINDS if kind not in covered]"),
    "conflict copy not counted as stored by the check": (STORE_FOR_CHECK, '    return copy["name"] if copy else name', "    return name"),
    # check: stopped chains
    "stopped alerted every check": (CHECK, 'if state.get("stopped") and not state.get("alerted"):', 'if state.get("stopped"):'),
    "a state that is not stopped alerts": (CHECK, 'if state.get("stopped") and not state.get("alerted"):', 'if not state.get("alerted"):'),
    "stopped state not marked alerted": (CHECK, '                store.write_state(alert.chain, state | {"alerted": True})', "                pass"),
    "stopped state replaced, not updated": (CHECK, 'store.write_state(alert.chain, state | {"alerted": True})', 'store.write_state(alert.chain, {"alerted": True})'),
    "check_day marks the state itself (R26)": (CHECK, "        alerts += chain_alerts\n    return alerts, {", "        alerts += chain_alerts\n    mark_alerted(store, alerts)\n    return alerts, {"),
    "chains with other alerts marked alerted (R26)": (CHECK, '        if alert.kind == "stopped":\n', "        if True:\n"),
    "a chain cleared since the check marked alerted (R26)": (CHECK, '            if state.get("stopped"):\n                store.write_state(alert.chain', "            if True:\n                store.write_state(alert.chain"),
    "stopped alert without its reason": (CHECK, "{state.get('since')}: {state.get('reason')}. ", "{state.get('since')}. "),
    "stopped chain not in the record": (CHECK, '"stopped": {"since": state.get("since"), "reason": state.get("reason")} if state.get("stopped") else None,', '"stopped": None,'),
    # check: failed runs (R4)
    "retry manifest not required": (CHECK, "    if uncovered:\n        problems.append", "    if False:\n        problems.append"),
    "main runs stand in for the retry (R4)": (CHECK, '    retries = [manifest for manifest in manifests if manifest["mode"] == "retry"]', "    retries = list(manifests)"),
    "one retry run enough for every kind (R4)": (CHECK, "    uncovered = [kind for kind in kinds if kind not in covered]", "    uncovered = [] if retries else list(kinds)"),
    "retry error not alerted (R4)": (CHECK, 'for manifest in retries if manifest["error"]]', "for manifest in retries if False]"),
    "blocked retry read as failed (R4)": (CHECK, 'for manifest in retries if manifest["error"]]', 'for manifest in retries if manifest["error"] or manifest["blocked"]]'),
    # check: retry runs that list nothing (R31)
    "nothing listed read as a quiet day": (CHECK, '    if retries and not listed and not any(manifest["blocked"] for manifest in retries):', "    if False:"),
    "one retry run listing nothing read as failed (R31)": (CHECK, "    if retries and not listed and not any(", '    if retries and not all(manifest["listed"] for manifest in retries) and not any('),
    "a blocked chain's empty morning read as failed (R31)": (CHECK, ' and not listed and not any(manifest["blocked"] for manifest in retries):', " and not listed:"),
    "every retry run must be blocked to excuse an empty morning (R31)": (CHECK, 'not any(manifest["blocked"] for manifest in retries):', 'not all(manifest["blocked"] for manifest in retries):'),
    "no retry run read as one that listed nothing (R31)": (CHECK, "    if retries and not listed and", "    if not listed and"),
    "unparsed of one retry run only (R31)": (CHECK, 'sum(manifest["unparsed"] for manifest in retries)', 'retries[-1]["unparsed"]'),
    "main runs' unparsed counted (R31)": (CHECK, 'sum(manifest["unparsed"] for manifest in retries)', 'sum(manifest["unparsed"] for manifest in manifests)'),
    # check: coverage, never alerted
    "coverage alerts": (CHECK, '        "coverage": _coverage(store, slug, day, stored),\n    }\n',
                        '        "coverage": _coverage(store, slug, day, stored),\n    }\n    if record["coverage"]["ratio"] != 1.0:\n        alerts.append(Alert(slug, "missing", "low coverage"))\n'),
    "coverage counts every kind of price file": (CHECK, 'if name and name.kind == "PriceFull"}', 'if name and name.kind != "Stores"}'),
    "store numbers compared as text": (CHECK, "    published = {int(name.store) for", "    published = {name.store for"),
    "store list ids compared as text": (CHECK, "        expected = {int(i) for i in", "        expected = {i for i in"),
    "store numbers compared as text on both sides": (CHECK, '    published = {int(name.store) for name in map(parse_file_name, stored) if name and name.kind == "PriceFull"}\n    coverage = {"published": len(published), "expected": None, "ratio": UNKNOWN, "store_list": None, "note": None}\n    key = _store_list(store, slug, day, stored)\n    if key is None:\n        return coverage | {"note": f"no Stores file stored from {day - timedelta(days=LOOKBACK_DAYS)} to {day}"}\n    coverage["store_list"] = key\n    try:\n        expected = {int(i) for i in',
                                                     '    published = {name.store for name in map(parse_file_name, stored) if name and name.kind == "PriceFull"}\n    coverage = {"published": len(published), "expected": None, "ratio": UNKNOWN, "store_list": None, "note": None}\n    key = _store_list(store, slug, day, stored)\n    if key is None:\n        return coverage | {"note": f"no Stores file stored from {day - timedelta(days=LOOKBACK_DAYS)} to {day}"}\n    coverage["store_list"] = key\n    try:\n        expected = {i for i in'),
    "ratio over every published store": (CHECK, "round(len(published & expected) / len(expected), 4)", "round(min(1.0, len(published) / len(expected)), 4)"),
    "no fallback to an older store list": (CHECK, "    for back in range(LOOKBACK_DAYS + 1):", "    for back in range(1):"),
    "store list sought eight days back": (CHECK, "    for back in range(LOOKBACK_DAYS + 1):", "    for back in range(LOOKBACK_DAYS + 2):"),
    "store list sought six days back": (CHECK, "LOOKBACK_DAYS = 7", "LOOKBACK_DAYS = 6"),
    "oldest store list preferred": (CHECK, "    for back in range(LOOKBACK_DAYS + 1):", "    for back in reversed(range(LOOKBACK_DAYS + 1)):"),
    "the day's first store list used": (CHECK, "            return raw_key(slug, on, lists[-1])", "            return raw_key(slug, on, lists[0])"),
    "any file read as the store list": (CHECK, "if (parsed := parse_file_name(name)) and parsed.kind == \"Stores\")", "if (parsed := parse_file_name(name)))"),
    "an empty store list divides by zero": (CHECK, '    if not expected:\n        return coverage', "    if False:\n        return coverage"),
    "an unreadable store list stops the check": (CHECK, "    except Exception as exc:  # coverage is a record only", "    except ZeroDivisionError as exc:  # coverage is a record only"),
    "store ids that are not numbers stop the coverage": (CHECK, " if i.isascii() and i.isdigit()}", "}"),
    "other scripts' digits read as store numbers": (CHECK, " if i.isascii() and i.isdigit()}", " if i.isdigit()}"),
    "a full kind no run listed passes": (CHECK, "    return \"; \".join(problems + _unlisted(manifests, retries, kinds)) or None", "    return \"; \".join(problems) or None"),
    "a full kind counted from the retry runs alone": (CHECK, "problems + _unlisted(manifests, retries, kinds)", "problems + _unlisted(retries, retries, kinds)"),
    "a blocked run leaves the full-kind alarm on": (CHECK, '    if any(manifest["blocked"] for manifest in retries):\n        return []\n', ""),
    "a main run's block silences the full-kind alarm": (CHECK, 'if any(manifest["blocked"] for manifest in retries):', 'if any(manifest["blocked"] for manifest in manifests):'),
    "a full kind the chain does not collect required": (CHECK, "if kind in kinds and kind not in listed]", "if kind not in listed]"),
    "PromoFull left out of the full kinds": (CHECK, 'FULL_KINDS = ("PriceFull", "PromoFull")', 'FULL_KINDS = ("PriceFull",)'),
    # handler: main and retry
    "day in UTC": (HANDLER, "    day = now.astimezone(ISRAEL).date()", "    day = now.astimezone(timezone.utc).date()"),
    "naive now accepted by the handler": (HANDLER, '    if now.tzinfo is None or now.utcoffset() is None:\n        raise ValueError("now must carry a time zone")',
                                          '    if False:\n        raise ValueError("now must carry a time zone")'),
    "kinds from the event ignored": (HANDLER, '    kinds = tuple(event["kinds"]) if "kinds" in event else chain.kinds', "    kinds = chain.kinds"),
    "default kinds all five, not the chain's": (HANDLER, 'if "kinds" in event else chain.kinds', 'if "kinds" in event else ("Stores", "PriceFull", "PromoFull", "Price", "Promo")'),
    "default kinds short of the chain's": (HANDLER, 'if "kinds" in event else chain.kinds', 'if "kinds" in event else chain.kinds[1:]'),
    "run id under another mode": (HANDLER, "    run_id = new_run_id(now, mode)", '    run_id = new_run_id(now, "main")'),
    "mode not given to the run loop": (HANDLER, "deps.store, day, run_id, mode,", 'deps.store, day, run_id, "main",'),
    "one Http for every chain": (HANDLER, "deps.http_for(chain.slug)", 'deps.http_for("shufersal")'),
    "one source for every chain": (HANDLER, "source_for(chain), deps.http_for", 'source_for(CHAINS["shufersal"]), deps.http_for'),
    "code_sha not given to the run loop": (HANDLER, "_clock(now, deps.time_left), deps.code_sha)", '_clock(now, deps.time_left), "")'),
    "time_left not given to the run loop": (HANDLER, "kinds, deps.time_left, _clock(", "kinds, lambda: 900.0, _clock("),
    "clock frozen at the start": (HANDLER, "    return lambda: start + timedelta(seconds=left_at_start - time_left())", "    return lambda: start"),
    "clock runs backwards": (HANDLER, "seconds=left_at_start - time_left()", "seconds=time_left() - left_at_start"),
    "main and retry email their errors": (HANDLER, "    if result.error:\n        log.error(", "    if result.error:\n        deps.publish(chain.slug, result.error)\n        log.error("),
    "failed files not logged": (HANDLER, '        log.warning("%s %s not stored: %s", chain.slug, name, why)', "        pass"),
    "block not logged": (HANDLER, '        log.error("%s blocked: %s", chain.slug, result.blocked)', "        pass"),
    "run error not logged": (HANDLER, '        log.error("%s run %s stopped: %s", chain.slug, run_id, result.error)', "        pass"),
    # handler: events
    "unknown mode read as a run": (HANDLER, '    if mode not in (*COLLECTING, "check", "unblock"):', "    if mode is None:"),
    "unknown chain accepted": (HANDLER, "    if not isinstance(slug, str) or slug not in CHAINS:", "    if not isinstance(slug, str):"),
    "a check event needs a chain": (HANDLER, '    if mode == "check":\n        summary = _check(', '    if mode == "check":\n        _chain(event)\n        summary = _check('),
    "unblock leaves the state": (HANDLER, "    deps.store.write_state(chain.slug, {})", "    pass"),
    "unblock clears every chain": (HANDLER, "    deps.store.write_state(chain.slug, {})", "    [deps.store.write_state(slug, {}) for slug in CHAINS]"),
    # handler: the check, its email and its ping
    "check of one chain only": (HANDLER, "check_day(deps.store, list(CHAINS), day,", 'check_day(deps.store, ["shufersal"], day,'),
    "the check given no chain's kinds": (HANDLER, ", kinds={slug: c.kinds for slug, c in CHAINS.items()})", ")"),
    "email without alerts": (HANDLER, "    if alerts:\n        deps.publish(subject, body)", "    if True:\n        deps.publish(subject, body)"),
    "alerts logged on a quiet morning": (HANDLER, "    if alerts:\n        subject, body = message(day, alerts, key)", "    if True:\n        subject, body = message(day, alerts, key)"),
    "check record written only with alerts": (HANDLER, "    deps.store.put_record(key, json.dumps(record, sort_keys=True, indent=1).encode(), now)\n    if alerts:\n",
                                              "    if alerts:\n        deps.store.put_record(key, json.dumps(record, sort_keys=True, indent=1).encode(), now)\n"),
    "check record without the code's fingerprint": (HANDLER, ', "code_sha": deps.code_sha}', "}"),
    "checked_at in local time": (HANDLER, '"checked_at": now.astimezone(timezone.utc).isoformat()', '"checked_at": now.isoformat()'),
    "alerts logged only once the record is written": (HANDLER, '    if alerts:\n        subject, body = message(day, alerts, key)\n        log.warning("%s\\n%s", subject, body)  # logged first: the record write or the email can still fail\n    record |= {"run_id": run_id, "checked_at": now.astimezone(timezone.utc).isoformat(), "code_sha": deps.code_sha}\n    deps.store.put_record(key, json.dumps(record, sort_keys=True, indent=1).encode(), now)\n',
                                                         '    record |= {"run_id": run_id, "checked_at": now.astimezone(timezone.utc).isoformat(), "code_sha": deps.code_sha}\n    deps.store.put_record(key, json.dumps(record, sort_keys=True, indent=1).encode(), now)\n    if alerts:\n        subject, body = message(day, alerts, key)\n        log.warning("%s\\n%s", subject, body)  # logged first: the record write or the email can still fail\n'),
    "one email per alert": (HANDLER, "        deps.publish(subject, body)", "        for alert in alerts:\n            deps.publish(subject, alert.text)"),
    "email not logged before it is sent": (HANDLER, '        log.warning("%s\\n%s", subject, body)  # logged first', "        pass  # logged first"),
    "ping failure raises": (HANDLER, "    except Exception as exc:  # the morning is checked", "    except ZeroDivisionError as exc:  # the morning is checked"),
    "ping skipped": (HANDLER, "        deps.ping(cfg.healthcheck_url, json.dumps(summary, sort_keys=True))", "        pass"),
    "ping to another address": (HANDLER, "deps.ping(cfg.healthcheck_url,", "deps.ping(cfg.alert_topic_arn,"),
    "ping sent before the check": (HANDLER, "    alerts, record = check_day(deps.store, list(CHAINS), day,",
                                   '    deps.ping(cfg.healthcheck_url, "started")\n    alerts, record = check_day(deps.store, list(CHAINS), day,'),
    "ping sent before the email": (HANDLER, "        deps.publish(subject, body)\n", '        deps.ping(cfg.healthcheck_url, "")\n        deps.publish(subject, body)\n'),
    "subject of 100 characters accepted": (HANDLER, "    if len(named) < SUBJECT_LIMIT:", "    if len(named) <= SUBJECT_LIMIT:"),
    "subject names no chains": (HANDLER, "        subject = named\n", "        pass\n"),
    "a chain named twice in the subject": (HANDLER, "', '.join(dict.fromkeys(alert.chain for alert in alerts))", "', '.join(alert.chain for alert in alerts)"),
    "an alert left out of the email": (HANDLER, 'lines += [f"- {alert.text}" for alert in alerts]', 'lines += [f"- {alert.text}" for alert in alerts[:1]]'),
    # handler: the config
    "a chain's Http not given the chain's timeout": (HANDLER, "Http(cfg.user_agent, timeout=CHAINS[slug].timeout)", "Http(cfg.user_agent)"),
    "User-Agent not checked by the config": (HANDLER, 'user_agent=check_user_agent(env["USER_AGENT"])', 'user_agent=env["USER_AGENT"]'),
    "alert topic and ping URL not required": (HANDLER, 'REQUIRED = ("BUCKET", "USER_AGENT", "ALERT_TOPIC_ARN", "HEALTHCHECK_URL")', 'REQUIRED = ("BUCKET", "USER_AGENT")'),
    "a blank variable accepted": (HANDLER, 'if not env.get(name, "").strip()]', "if name not in env]"),
    "RETENTION_DAYS ignored": (HANDLER, 'retention_days=int(env.get("RETENTION_DAYS", RETENTION_DAYS))', "retention_days=RETENTION_DAYS"),
    "RETENTION_DAYS default not ten years": (HANDLER, 'env.get("RETENTION_DAYS", RETENTION_DAYS)', 'env.get("RETENTION_DAYS", 365)'),
    # handler: the ping and the code's fingerprint (R25)
    "ping without its message": (HANDLER, "data=message.encode(), method=", 'data=b"", method='),
    "ping unidentified": (HANDLER, 'headers={"User-Agent": user_agent})', "headers={})"),
    "ping without a timeout": (HANDLER, "opener.open(request, timeout=PING_TIMEOUT)", "opener.open(request)"),
    "fingerprint leaves out subpackages": (HANDLER, 'package.rglob("*.py")', 'package.glob("*.py")'),
    "fingerprint ignores paths": (HANDLER, 'digest.update(rel.encode() + b"\\0" + hashlib', "digest.update(hashlib"),
    "fingerprint not 12 hex": (HANDLER, "    return digest.hexdigest()[:12]", "    return digest.hexdigest()"),
    "stopped chains marked before the email (R26)": (HANDLER, "        deps.publish(subject, body)\n        mark_alerted(deps.store, alerts)", "        mark_alerted(deps.store, alerts)\n        deps.publish(subject, body)"),
    "stopped chains never marked by the check (R26)": (HANDLER, "        mark_alerted(deps.store, alerts)  # only now", "        pass  # only now"),
    "stopped chains marked after the ping (R26)": (HANDLER, '        mark_alerted(deps.store, alerts)  # only now: a failed email leaves them to alert again (R26)\n    summary = {"mode": "check", "day": day.isoformat(), "run_id": run_id, "record": key, "alerts": len(alerts)}\n    try:\n        deps.ping(cfg.healthcheck_url, json.dumps(summary, sort_keys=True))\n    except Exception as exc:  # the morning is checked and recorded; a missed ping makes healthchecks.io email\n        log.warning("health-check ping failed: %s: %s", type(exc).__name__, exc)\n',
                                                   '    summary = {"mode": "check", "day": day.isoformat(), "run_id": run_id, "record": key, "alerts": len(alerts)}\n    try:\n        deps.ping(cfg.healthcheck_url, json.dumps(summary, sort_keys=True))\n    except Exception as exc:  # the morning is checked and recorded; a missed ping makes healthchecks.io email\n        log.warning("health-check ping failed: %s: %s", type(exc).__name__, exc)\n    if alerts:\n        mark_alerted(deps.store, alerts)  # only now: a failed email leaves them to alert again (R26)\n'),
    # handler: the ping's User-Agent (R27) and the log level (R28)
    "ping carries the contact email (R27)": (HANDLER, "ping=partial(ping, user_agent=ping_user_agent(cfg.user_agent)),", "ping=partial(ping, user_agent=cfg.user_agent),"),
    "ping User-Agent without the project URL (R27)": (HANDLER, '    return f"{product} ({url[0]})" if url else product', "    return product"),
    "an @ in the first word kept in the ping's User-Agent (R27)": (HANDLER, 'if words and "@" not in words[0] else', "if words else"),
    "a project URL holding an @ kept whole (R27)": (HANDLER, r'_PROJECT_URL = re.compile(r"\+https://[^\s;()@]+")', r'_PROJECT_URL = re.compile(r"\+https://[^\s;()]+")'),
    "collector logs below INFO dropped (R28)": (HANDLER, 'logging.getLogger("collector").setLevel(logging.INFO)', 'logging.getLogger("collector").setLevel(logging.WARNING)'),
    "collector log level left to the runtime (R28)": (HANDLER, 'logging.getLogger("collector").setLevel(logging.INFO)\n', "\n"),
    # handler: the production wiring
    "one Http for every chain run (R6)": (HANDLER, "        http_for=lambda slug: Http(cfg.user_agent, timeout=CHAINS[slug].timeout),", "        http_for=lambda slug, shared=Http(cfg.user_agent): shared,"),
    "email to another topic": (HANDLER, "sns.publish(TopicArn=cfg.alert_topic_arn,", "sns.publish(TopicArn=cfg.bucket,"),
    "email without its subject": (HANDLER, "Subject=subject, Message=body)", "Message=body)"),
    "time left read in milliseconds": (HANDLER, "context.get_remaining_time_in_millis() / 1000", "context.get_remaining_time_in_millis()"),
    "store retention not the config's": (HANDLER, "S3Store(s3, cfg.bucket, cfg.retention_days)", "S3Store(s3, cfg.bucket)"),
    "production ping unidentified": (HANDLER, "ping=partial(ping, user_agent=ping_user_agent(cfg.user_agent)),", 'ping=partial(ping, user_agent=""),'),
    "production code_sha not the package's": (HANDLER, "        code_sha=CODE_SHA,\n    )", '        code_sha="",\n    )'),
    # template: the three the plan names
    "schedule enabled by default": (TEMPLATE, "    Default: DISABLED\n", "    Default: ENABLED\n"),
    "delete allowed": (TEMPLATE, "                - s3:PutObjectRetention\n", "                - s3:PutObjectRetention\n                - s3:DeleteObject\n"),
    "UTC schedule": (TEMPLATE, 'ScheduleExpression: "cron(30 6 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem', 'ScheduleExpression: "cron(30 6 * * ? *)"\n            ScheduleExpressionTimezone: UTC'),
    # template: the bucket
    "bucket without Object Lock": (TEMPLATE, "      ObjectLockEnabled: true\n", "      ObjectLockEnabled: false\n"),
    "bucket default retention locks the state files": (TEMPLATE, "      ObjectLockEnabled: true\n", "      ObjectLockEnabled: true\n      ObjectLockConfiguration:\n        ObjectLockEnabled: Enabled\n        Rule:\n          DefaultRetention:\n            Mode: GOVERNANCE\n            Days: 3650\n"),
    "bucket versioning suspended": (TEMPLATE, "        Status: Enabled\n", "        Status: Suspended\n"),
    "bucket deleted with the stack": (TEMPLATE, "    DeletionPolicy: Retain\n", "    DeletionPolicy: Delete\n"),
    "bucket deleted when replaced": (TEMPLATE, "    UpdateReplacePolicy: Retain\n", "    UpdateReplacePolicy: Delete\n"),
    "public ACLs accepted": (TEMPLATE, "        BlockPublicAcls: true", "        BlockPublicAcls: false"),
    "public bucket policy accepted": (TEMPLATE, "        BlockPublicPolicy: true", "        BlockPublicPolicy: false"),
    "public ACLs honoured": (TEMPLATE, "        IgnorePublicAcls: true", "        IgnorePublicAcls: false"),
    "public bucket not restricted": (TEMPLATE, "        RestrictPublicBuckets: true", "        RestrictPublicBuckets: false"),
    "ACLs enabled on the bucket": (TEMPLATE, "ObjectOwnership: BucketOwnerEnforced", "ObjectOwnership: ObjectWriter"),
    "bucket unencrypted": (TEMPLATE, "      BucketEncryption:\n        ServerSideEncryptionConfiguration:\n          - ServerSideEncryptionByDefault:\n              SSEAlgorithm: AES256\n", ""),
    "a public bucket policy added": (TEMPLATE, "  AlertTopic:\n    Type: AWS::SNS::Topic\n",
                                     '  OpenPolicy:\n    Type: AWS::S3::BucketPolicy\n    Properties:\n      Bucket: !Ref ArchiveBucket\n      PolicyDocument:\n        Statement:\n          - Effect: Allow\n            Principal: "*"\n            Action: s3:GetObject\n            Resource: !Sub "${ArchiveBucket.Arn}/*"\n\n  AlertTopic:\n    Type: AWS::SNS::Topic\n'),
    # template: the function
    "function on x86": (TEMPLATE, "Architectures: [arm64]", "Architectures: [x86_64]"),
    "function on an older Python": (TEMPLATE, "Runtime: python3.13", "Runtime: python3.12"),
    "function memory halved": (TEMPLATE, "MemorySize: 512", "MemorySize: 256"),
    "function timeout cut to five minutes": (TEMPLATE, "      Timeout: 900\n", "      Timeout: 300\n"),
    "Lambda retries a failed run": (TEMPLATE, "      EventInvokeConfig:\n        MaximumRetryAttempts: 0", "      EventInvokeConfig:\n        MaximumRetryAttempts: 2"),
    "handler pointed elsewhere": (TEMPLATE, "Handler: collector.handler.handler", "Handler: collector.handler.run"),
    "code from the repo root": (TEMPLATE, "CodeUri: src/", "CodeUri: ./"),
    "alert topic not given to the function (R5)": (TEMPLATE, "          ALERT_TOPIC_ARN: !Ref AlertTopic\n", ""),
    "retention not ten years (R5)": (TEMPLATE, 'RETENTION_DAYS: "3650"', 'RETENTION_DAYS: "365"'),
    "logs to Lambda's default group": (TEMPLATE, "      LoggingConfig:\n        LogGroup: !Ref CollectorLogs\n", ""),
    "logs kept forever": (TEMPLATE, "      RetentionInDays: 30\n", ""),
    "function name not in the outputs": (TEMPLATE, "  CollectorFunctionName:\n    Value: !Ref CollectorFunction\n", ""),
    # template: the role
    "governance bypass allowed": (TEMPLATE, "                - s3:PutObjectRetention\n", "                - s3:PutObjectRetention\n                - s3:BypassGovernanceRetention\n"),
    "bucket settings writable": (TEMPLATE, "                - s3:PutObjectRetention\n", "                - s3:PutObjectRetention\n                - s3:PutBucketObjectLockConfiguration\n"),
    "S3 full access added": (TEMPLATE, "      Policies:\n        - Statement:\n", "      Policies:\n        - AmazonS3FullAccess\n        - Statement:\n"),
    "every S3 action on state": (TEMPLATE, "              Action:\n                - s3:GetObject\n                - s3:PutObject\n", '              Action: "s3:*"\n'),
    "locked writes anywhere in the bucket": (TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/raw/*"\n                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n                - !Sub "${ArchiveBucket.Arn}/checks/*"\n            # The check reads',
                                             '                - !Sub "${ArchiveBucket.Arn}/*"\n            # The check reads'),
    "check records not writable": (TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/checks/*"\n            # The check reads', "            # The check reads"),
    "manifests not readable by the check": (TEMPLATE, '              Action: s3:GetObject\n              Resource:\n                - !Sub "${ArchiveBucket.Arn}/raw/*"\n                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n',
                                            '              Action: s3:GetObject\n              Resource:\n                - !Sub "${ArchiveBucket.Arn}/raw/*"\n'),
    "state not readable": (TEMPLATE, "                - s3:GetObject\n                - s3:PutObject\n              Resource: !Sub", "                - s3:PutObject\n              Resource: !Sub"),
    "no ListBucket": (TEMPLATE, "              Action: s3:ListBucket\n", "              Action: s3:ListAllMyBuckets\n"),
    "a condition on the bucket list": (TEMPLATE, "              Resource: !GetAtt ArchiveBucket.Arn\n", '              Resource: !GetAtt ArchiveBucket.Arn\n              Condition:\n                StringLike:\n                  s3:prefix: ["raw/*"]\n'),
    "alerts publishable to any topic": (TEMPLATE, "              Resource: !Ref AlertTopic\n", '              Resource: "*"\n'),
    # template: the parameters and the alert email
    "User-Agent pattern takes http": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", r"AllowedPattern: '.*\+https?://.*@.*'"),
    "User-Agent pattern without the email": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", r"AllowedPattern: '.*\+https://.*'"),
    "User-Agent pattern dropped": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", "AllowedPattern: '.*'"),
    "health-check URL of any shape": (TEMPLATE, r"AllowedPattern: 'https://hc-ping\.com/[-A-Za-z0-9_/]+'", "AllowedPattern: '.*'"),
    "health-check URL shown in the stack": (TEMPLATE, "    NoEcho: true\n", "    NoEcho: false\n"),
    "alert email given a default": (TEMPLATE, "  AlertEmail:\n    Type: String\n", "  AlertEmail:\n    Type: String\n    Default: you@example.org\n"),
    "schedule switch takes any value": (TEMPLATE, "    AllowedValues: [ENABLED, DISABLED]\n", ""),
    "alerts not by email": (TEMPLATE, "        - Protocol: email\n", "        - Protocol: email-json\n"),
    "a ping URL in the template": (TEMPLATE, "e.g. https://hc-ping.com/<uuid>;", "e.g. https://hc-ping.com/0f3e2d1c-5b4a;"),
    # template: the schedules (ruling R7)
    "a schedule without a time zone": (TEMPLATE, 'ScheduleExpression: "cron(33 6 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n', 'ScheduleExpression: "cron(33 6 * * ? *)"\n'),
    "a misspelled schedule property": (TEMPLATE, 'ScheduleExpression: "cron(39 6 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem', 'ScheduleExpression: "cron(39 6 * * ? *)"\n            ScheduleExpressionTimeZone: Asia/Jerusalem'),
    "a schedule always on": (TEMPLATE, "Input: '{\"mode\": \"check\"}'\n            State: !Ref ScheduleState", "Input: '{\"mode\": \"check\"}'\n            State: ENABLED"),
    "a flexible start window": (TEMPLATE, "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}",
                                "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: \"FLEXIBLE\", MaximumWindowInMinutes: 15}"),
    "Shufersal's promotion retry three hours after the wrong run": (TEMPLATE, '"cron(15 10 * * ? *)"', '"cron(0 10 * * ? *)"'),
    "OFF unquoted, which YAML reads as false": (TEMPLATE, "Input: '{\"mode\": \"main\", \"chain\": \"osherad\"}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}",
                                                "Input: '{\"mode\": \"main\", \"chain\": \"osherad\"}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: OFF}"),
    "Scheduler retries a failed invoke": (TEMPLATE, "Input: '{\"mode\": \"retry\", \"chain\": \"carrefour\"}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}\n            RetryPolicy: {MaximumRetryAttempts: 0}",
                                          "Input: '{\"mode\": \"retry\", \"chain\": \"carrefour\"}'\n            State: !Ref ScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}\n            RetryPolicy: {MaximumRetryAttempts: 185}"),
    "a schedule weekly, not daily": (TEMPLATE, '"cron(39 9 * * ? *)"', '"cron(39 9 ? * SUN *)"'),
    "a run moved off rulings R7 and R30": (R7_TABLE, '"cron(33 6 * * ? *)"', '"cron(34 6 * * ? *)"'),
    "two schedules share a start minute": (ONE_MINUTE_EACH, '"cron(39 6 * * ? *)"', '"cron(33 6 * * ? *)"'),
    "Shufersal's runs overlap": (ONE_RUN_AT_A_TIME, '"cron(0 7 * * ? *)"', '"cron(50 6 * * ? *)"'),
    "two NCR chains 3 minutes apart (R30)": (ONE_HOST_AT_A_TIME, '"cron(48 6 * * ? *)"', '"cron(36 6 * * ? *)"'),
    "a retry run not three hours after its main run": (RETRY_THREE_HOURS_ON, '"cron(3 10 * * ? *)"', '"cron(5 10 * * ? *)"'),
    "check at the design's 10:00": (CHECK_LAST, '"cron(45 10 * * ? *)"', '"cron(0 10 * * ? *)"'),
    "check before the last retry run can finish": (CHECK_LAST, '"cron(45 10 * * ? *)"', '"cron(10 10 * * ? *)"'),
    "check with no margin after the last retry run": (CHECK_LAST, '"cron(45 10 * * ? *)"', '"cron(30 10 * * ? *)"'),
    "Shufersal's retries short of a kind (R4)": (ALL_KINDS, "Input: '{\"mode\": \"retry\", \"chain\": \"shufersal\", \"kinds\": [\"PromoFull\"]}'", "Input: '{\"mode\": \"retry\", \"chain\": \"shufersal\", \"kinds\": [\"PriceFull\"]}'"),
    "Shufersal's store-list run also fetching full prices": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'", "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\", \"PriceFull\"]}'"),
    "another chain narrowed to some kinds": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\", \"kinds\": [\"PriceFull\"]}'"),
    "a chain without a retry run": (ALL_KINDS, "Input: '{\"mode\": \"retry\", \"chain\": \"yochananof\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"yochananof\"}'"),
    "a chain with no main run": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"yochananof\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"osherad\"}'"),
    "a chain the code does not know": (HANDLER_EVENTS, "Input: '{\"mode\": \"main\", \"chain\": \"carrefour\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"victory\"}'"),
    "the check given a chain": (HANDLER_EVENTS, "Input: '{\"mode\": \"check\"}'", "Input: '{\"mode\": \"check\", \"chain\": \"shufersal\"}'"),
    # the operations doc
    "a manual collecting run started synchronously": (OPERATIONS, "--invocation-type Event --payload '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'", "--payload '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'"),
    "an aws command in the doc without the project profile": (OPERATIONS, "aws logs tail /il-grocery-prices/collector --follow --since 10m --profile flights-sam --region il-central-1", "aws logs tail /il-grocery-prices/collector --follow --since 10m --region il-central-1"),
    "sam deploy in the doc without the project profile": (OPERATIONS, "sam deploy --profile flights-sam --region il-central-1 --stack-name", "sam deploy --region il-central-1 --stack-name"),
    "a chain's manual run missing from the doc": (OPERATIONS, "--payload '{\"mode\": \"main\", \"chain\": \"yochananof\"}'", "--payload '{\"mode\": \"main\", \"chain\": \"osherad\"}'"),
    "a Shufersal manual run missing from the doc": (OPERATIONS, "--payload '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'", "--payload '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"PriceFull\"]}'"),
    "an unknown chain unblocked in the doc": (OPERATIONS, "--payload '{\"mode\": \"unblock\", \"chain\": \"ramilevy\"}'", "--payload '{\"mode\": \"unblock\", \"chain\": \"victory\"}'"),
    "a real address in the doc": (OPERATIONS, "'AlertEmail=<email>'", "'AlertEmail=owner@mail.example.net'"),
    "the doc's timetable off the schedules": (OPERATIONS, "| 06:39 | Carrefour", "| 06:40 | Carrefour"),
    # basket: barcodes
    "barcode check digit ignored": (BARCODE, "(3 if place % 2 == 0 else 1)", "(1 if place % 2 == 0 else 1)"),
    "barcode leading zeros kept": (BARCODE, 'significant = digits.lstrip("0")', "significant = digits"),
    "barcode non-ASCII digits accepted": (BARCODE, "if not _DIGITS.fullmatch(digits):", "if not digits.isdigit():"),
    "barcode seven significant digits accepted": (BARCODE, "8 <= len(digits) <= 14", "7 <= len(digits) <= 14"),
    "barcode fifteen significant digits accepted": (BARCODE, "8 <= len(digits) <= 14", "8 <= len(digits) <= 15"),
}


def duplicate_names(source: str) -> list[str]:
    """The names more than one entry of the MUTATIONS literal in `source` gives: a dict literal keeps
    only the last entry under a name, so the dict itself cannot show them; the source can."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MUTATIONS" for t in node.targets):
            names = [key.value if isinstance(key, ast.Constant) else ast.unparse(key)
                     for key in node.value.keys if key is not None]  # None: a ** unpacking
            return sorted({name for name in names if names.count(name) > 1}, key=str)
    raise RuntimeError("no MUTATIONS = {...} in the source")


def main(wanted: list[str]) -> int:
    """Run every mutation, or with `wanted` only those whose name contains one of its strings."""
    duplicates = duplicate_names(Path(__file__).read_text())
    if duplicates:
        print(f"DUPLICATE mutation names, each given to more than one entry (only the last would run): {duplicates}")
        return 2
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

"""Break each rule on purpose and confirm a test fails. Run from the repo root:

    .venv/bin/python scripts/mutation_check.py            # every mutation
    .venv/bin/python scripts/mutation_check.py "HTML"     # only those whose name contains one of the arguments

Each mutation names the file it breaks and the test files that must catch it. It edits source files
in place while it runs: run nothing else from this checkout until it finishes. Files are restored
afterwards. A mutation is caught only when pytest exits 1 (a test failed or errored); any other
non-zero exit means pytest could not run the tests as asked (a test id that no longer exists, 4; a
module that no longer imports, 2; no tests collected, 5), which proves nothing about the rule, so it
is reported as ERROR. That includes a break that stops the broken module importing (a syntax error,
a name a test imports removed): pick a break that leaves the module importable. Exit code 1 if any
mutation goes unnoticed or errs, or if its text to break is not found exactly once (the script is
out of date). Exit code 2, before anything runs, if two entries share a name: the dict literal would
keep only the last, and the first would never run.

Copied from flights-archive's harness, with two changes: only exit 1 counts as caught (above), and
the test runs write no bytecode. Python trusts a cached .pyc whose source has the same size and the
same whole-second mtime, so a same-length mutation written and restored within one second could
otherwise leave the broken code cached for the next run.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

from pytest import ExitCode

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("src/collector/names.py", ["tests/test_names.py"])
PAYLOAD = ("src/collector/payload.py", ["tests/test_payload.py"])
STORELIST = ("src/collector/storelist.py", ["tests/test_storelist.py"])
HTTP = ("src/collector/http.py", ["tests/test_http.py"])
CHAINS = ("src/collector/chains.py", ["tests/test_chains.py"])
SOURCES = ("src/collector/sources/__init__.py", ["tests/test_chains.py"])
SHUFERSAL = ("src/collector/sources/shufersal.py", ["tests/test_shufersal.py"])
# The start rules the 2026-11-05 replay rests on: the morning replayed (tests/test_replay.py) must catch them too.
SHUFERSAL_REPLAYED = ("src/collector/sources/shufersal.py", ["tests/test_shufersal.py", "tests/test_replay.py"])
# The 2026-11-06 replay, which must catch a timed-out page not asked again by itself.
NOV_6_REPLAY = ("src/collector/sources/shufersal.py", ["tests/test_replay.py::test_the_2026_11_06_pricefull_run_replayed"])
# The 2026-11-06 Promo polls (q23), which must catch a poll started by R37's rule by themselves.
PROMO_REPLAY = ("src/collector/run.py", ["tests/test_replay.py::test_a_day_of_shufersal_promo_passes_replayed"])
# A store republished at a pass's resume point (q23), the only test of that case, which must catch R37's step back left
# out by itself.
PROMO_REPUBLISHED = ("src/collector/sources/shufersal.py",
                     ["tests/test_replay.py::test_a_store_republished_at_the_resume_point_still_completes_the_pass"])
# Two q24 breaks that pause where the rule has no pause. The older tests in test_shufersal.py build their sources with
# the default sleep, time.sleep, so under these breaks they would wait for real (10 s a page) before -x reached the q24
# tests near the end of the file: each names the one test that must catch it by itself.
_S = "tests/test_shufersal.py::"
PAUSE_ON_FIRST_TRY = ("src/collector/sources/shufersal.py", [_S + "test_a_page_read_on_its_first_try_records_one_try"])
BLOCK_TRIED_AGAIN = ("src/collector/sources/shufersal.py", [_S + "test_a_block_on_the_second_try_stops_the_listing"])
NAME_CHECK = ("src/collector/sources/__init__.py", ["tests/test_chains.py"])
NCR = ("src/collector/sources/ncr.py", ["tests/test_ncr.py"])
# The NCR directory read to its last answer before the first row (q26, ruling R40): the one test that takes a row from a
# listing of several answers before reading it to the end, which must catch rows given answer by answer by itself.
NCR_WHOLE_READ = ("src/collector/sources/ncr.py",
                  ["tests/test_ncr.py::test_every_answer_of_the_directory_is_read_before_the_first_row"])
NEVER_SHORT = ("src/collector/sources/__init__.py", ["tests/test_chains.py"])
CARREFOUR = ("src/collector/sources/carrefour.py", ["tests/test_carrefour.py"])
STORE = ("src/collector/store.py", ["tests/test_store.py"])
RUN = ("src/collector/run.py", ["tests/test_run.py"])
CHECK = ("src/collector/check.py", ["tests/test_check.py"])
STORE_FOR_CHECK = ("src/collector/store.py", ["tests/test_check.py"])
PAGES = ("src/collector/pages.py", ["tests/test_pages.py"])
PAGES_FOR_CHECK = ("src/collector/pages.py", ["tests/test_check.py"])
HANDLER = ("src/collector/handler.py", ["tests/test_handler.py"])
TEMPLATE = ("template.yaml", ["tests/test_template.py"])
OPERATIONS = ("docs/operations.md", ["tests/test_template.py"])
SITE_TEMPLATE = ("site-template.yaml", ["tests/test_site_template.py"])
LAYER_PIN = ("layer/requirements.txt", ["tests/test_basket_template.py"])
LAYER_MAKEFILE = ("layer/Makefile", ["tests/test_basket_template.py"])
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
NO_POLL_DURING_EXTRACTION = ("template.yaml", [_T + "test_no_poll_is_in_flight_while_the_extractions_run"])
POLL_SWITCH = ("template.yaml", [_T + "test_every_schedule_runs_on_time_in_israel_and_follows_the_switch"])
POLLED_CHAINS = ("src/collector/chains.py", [_T + "test_the_chains_that_poll_are_the_chains_with_update_kinds"])
BASKET_TEMPLATE = ("template.yaml", ["tests/test_basket_template.py"])
# The basket function's rules, each named for the one test in test_basket_template.py that must catch it by itself.
_B = "tests/test_basket_template.py::"
BASKET_OWN_SWITCH = ("template.yaml", [_B + "test_schedules_follow_the_baskets_own_switch_in_israel_time"])
BASKET_AFTER_EXTRACT = ("template.yaml", [_B + "test_basket_runs_after_the_last_extraction_can_have_finished"])
EXTRACT_AFTER_CHECK = ("template.yaml", [_B + "test_extraction_starts_after_the_collectors_check_can_have_finished"])
COLLECTED_BY_PINNED = ("template.yaml", [_B + "test_collected_by_is_the_extractions_start"])
NO_DELETE_BASKET = ("template.yaml", [_B + "test_role_cannot_delete_bypass_the_lock_or_change_either_bucket"])
READ_RECORDS_FOR_RETRY = ("template.yaml", [_B + "test_role_grants_exactly_what_the_code_does"])
TMP_SIZE = ("template.yaml", [_B + "test_function_has_two_gb_two_gb_of_tmp_and_lambdas_longest_run"])
LAYER_ATTACHED = ("template.yaml", [_B + "test_function_runs_the_basket_handler_on_python_313_arm64_with_the_layer"])
BARCODE = ("src/basket/barcode.py", ["tests/test_barcode.py"])
PRICEFILE = ("src/basket/pricefile.py", ["tests/test_pricefile.py"])
EXTRACT = ("src/basket/extract.py", ["tests/test_extract.py"])
DUCK = ("src/basket/duck.py", ["tests/test_duck.py"])
EXTRACT_FOR_DUCK = ("src/basket/extract.py", ["tests/test_duck.py"])
RULES_FOR_DUCK = ("src/basket/rules.py", ["tests/test_duck.py"])
STORES = ("src/basket/stores.py", ["tests/test_stores.py"])
CHAINS_BASKET = ("src/basket/chains.py", ["tests/test_stores.py"])
UNITS_BASKET = ("src/basket/units.py", ["tests/test_units.py"])
BASKET_FILE = ("src/basket/basket_file.py", ["tests/test_basket_file.py"])
RULES = ("src/basket/rules.py", ["tests/test_rules.py"])
RECORD = ("src/basket/record.py", ["tests/test_record.py"])
CANDIDATES = ("src/basket/candidates.py", ["tests/test_candidates.py"])
WORDS = ("src/basket/words.py", ["tests/test_page.py"])
PAGE = ("src/basket/page.py", ["tests/test_page.py"])
# tests/test_check.py is the collector's morning check; the basket check's tests have their own file
CHECK_BASKET = ("src/basket/check.py", ["tests/test_basket_check.py"])
BUILD = ("src/basket/build.py", ["tests/test_build.py"])
GUARD = ("src/basket/guard.py", ["tests/test_guard.py"])
ARCHIVE = ("src/basket/archive.py", ["tests/test_archive.py"])
SITE = ("src/basket/site.py", ["tests/test_site.py"])
BASKET_HANDLER = ("src/basket/handler.py", ["tests/test_basket_handler.py"])
MUTATION_CHECK = ("scripts/mutation_check.py", ["tests/test_mutation_check.py"])  # this file: the run has loaded it
CANDIDATES_MAIN = ("src/basket/candidates.py", ["tests/test_candidates.py::test_main_counts_only_the_included_stores_and_writes_the_day_s_table"])

# The run loop's take of a row, in three parts, for the mutations that move how far a page counts as taken (q21 run).
_RUN_TAKEN = ('        if self.result.pages:  # first: a row of another day, a repeat or one never downloaded was still listed\n'
              '            page = self.result.pages[-1]\n'
              '            page["taken_through"] = page["last"] if item.ends_page else item.name.raw\n')
# The day filter is the kind filter, then the other-day count (q23): `_RUN_KIND_FILTER + _RUN_OTHER_DAY`, the first two
# steps of `_listed`, the sorting the take and a poll's read after its time stop share (q26).
_RUN_KIND_FILTER = ("        if item.name.kind not in self.kinds:\n"
                    "            return None\n")
_RUN_OTHER_DAY = ("        if item.name.day != self.day:\n"
                  "            self._other_day(item)\n"
                  "            return None\n")
# The rest of the take (q26): `_listed`'s call and its None return, the skip of a name stored before, the download.
_RUN_LISTED = "        name = self._listed(item)\n"
_RUN_SKIP = ("        if name is None or name in self.stored:\n"
             "            return\n")
_RUN_TO_DOWNLOAD = _RUN_LISTED + _RUN_SKIP + "        body = self._fetch(item, name)\n"
_RUN_STORED = ("        if body is not None:\n"
               "            self._store(name, body)\n")
# The run's stop (q26): its handler's first line, the test for reading on after a poll's time stop, the call.
_RUN_STOP = "        except _Stop:  # `unparsed` stays 0, drained or not: this loop did not read the listing to its end (R13)\n"
_RUN_DRAIN_IF = ('            if (self.result.error == OUT_OF_TIME and self.result.mode == "poll" and listing is not None\n'
                 "                    and not isinstance(self.source, PagedSource)):  # a paged listing's page records stay as taken\n")
_RUN_DRAIN_CALL = "                self._drain(listing)  # ruling R40\n"
# The drain's read of a row and what it may meet (q26), for the break that puts a latch's failure under the catch-all.
_RUN_DRAIN_NEXT = ("            try:\n"
                   "                item = next(listing)\n"
                   "            except (StopIteration, OutOfTime):  # the end, or an adapter's own request short of time\n"
                   "                return\n"
                   "            except Blocked as block:\n"
                   "                try:\n"
                   "                    self._latch(str(block))  # a latch not written raises past the handler below, its error kept\n"
                   "                except _Stop:\n"
                   "                    return\n"
                   "            except Exception as exc:\n")
_RUN_READ_EARLIER = ('        prefix = manifest_key(self.day, self.slug, "").removesuffix(".json")  # this chain\'s runs of the day\n'
                     "        earlier = [json.loads(record) for record in self.store.read_records(prefix)]\n")
# NCR's listing as it stands: every name read and checked, then given (q26). And a rewrite that reads the directory answer
# by answer, checking each answer's names and giving its rows before it asks for the next: the rows after a poll's time
# stop would then wait on requests the drain cannot make.
_NCR_LISTED = ("        listed = []\n"
               "        for number, fname in enumerate(_fnames(http, file_page, self.username, short_of_time), 1):\n"
               '            name = checked_name(fname, f"the NCR listing, entry {number}")\n'
               "            if name is None:\n"
               "                self.unparsed += 1\n"
               "            elif name.kind in kinds:\n"
               "                listed.append(Listed(name, DOWNLOAD + fname))\n"
               "        yield from listed\n")
_NCR_ANSWER_BY_ANSWER = ("        length, fnames, total = _page_size(file_page), [], None\n"
                         "        while total is None or len(fnames) < total:\n"
                         "            if short_of_time():\n"
                         '                raise OutOfTime(f"before the NCR listing\'s answer from iDisplayStart {len(fnames)}")\n'
                         "            received, total = _answer(http.post(LISTING, _form(len(fnames), length, file_page.csrftoken),\n"
                         "                                                headers=AJAX).body)\n"
                         "            if not received:\n"
                         '                raise ListingUnreadable(f"the NCR listing stopped at {len(fnames)} of {total} entries")\n'
                         "            answer = []\n"
                         "            for fname in received:\n"
                         "                fnames.append(fname)\n"
                         '                name = checked_name(fname, f"the NCR listing, entry {len(fnames)}")\n'
                         "                if name is None:\n"
                         "                    self.unparsed += 1\n"
                         "                elif name.kind in kinds:\n"
                         "                    answer.append(Listed(name, DOWNLOAD + fname))\n"
                         "            yield from answer\n")

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
    "sub-chain read as the store": (NAMES, "    sub_chain = groups[0] if len(groups) == 2 else None", "    sub_chain = groups[-1]"),
    "price file without a store accepted": (NAMES, "    else:\n        return None\n    sub_chain = groups[0]", "    else:\n        store = None\n    sub_chain = groups[0]"),
    "text after the name accepted": (NAMES, "_REST.fullmatch(name, prefix.end())", "_REST.match(name, prefix.end())"),
    # names: the hour in a name, which the update day's by_hour counts by (q23)
    "the minute read as the hour (q23 names)": (NAMES, r"(?P<hour>\d{2})\d{2,}", r"\d{2}(?P<hour>\d{2})\d*"),
    "store 039's hour not read (q23 names)": (NAMES, r'r"-\d{8}-?(?P<hour>', r'r"-\d{8}-(?P<hour>'),
    "an hour past 23 kept (q23 names)": (NAMES, "    return hour if hour and int(hour) <= 23 else None", "    return hour or None"),
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
    # http: a timeout told apart (q24)
    "a timeout raised as a plain HttpError (q24 timeout)": (HTTP, "error_type = HttpTimeout if _timed_out(exc) else HttpError", "error_type = HttpError"),
    "every network failure raised as a timeout (q24 timeout)": (HTTP, "error_type = HttpTimeout if _timed_out(exc) else HttpError", "error_type = HttpTimeout"),
    "a URLError's timeout not read as one (q24 timeout)": (HTTP, "        return isinstance(exc.reason, TimeoutError)", "        return False"),
    "a bare timeout not read as one (q24 timeout)": (HTTP, "    return isinstance(exc, TimeoutError)", "    return False"),
    "a timeout not an HttpError (q24 timeout)": (HTTP, "class HttpTimeout(HttpError):", "class HttpTimeout(Exception):"),
    "a timeout not chained from its cause (q24 timeout)": (HTTP, 'failed: {exc}") from exc', 'failed: {exc}")'),
    # chains
    "a sixth chain added": (CHAINS, '    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof", polled=("Price", "Promo")),\n', '    Chain("yochananof", "Yochananof", "ncr", NCR_URL, username="yohananof", polled=("Price", "Promo")),\n    Chain("extra", "Extra", "carrefour", "https://example.org"),\n'),
    "a chain dropped": (CHAINS, '    Chain("carrefour", "Carrefour", "carrefour", "https://prices.carrefour.co.il", polled=("Price", "Promo")),\n', ""),
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
    "Osher Ad without a username": (CHAINS, 'NCR_URL, username="osherad", polled=', "NCR_URL, polled="),
    "a username on a portal with no login": (CHAINS, '"https://prices.carrefour.co.il", polled=', '"https://prices.carrefour.co.il", username="carrefour", polled='),
    "Chain not frozen": (CHAINS, "@dataclass(frozen=True)\nclass Chain:", "@dataclass\nclass Chain:"),
    # chains: the update kinds each chain's poll runs read (q23)
    "a quick chain that does not poll (q23 chains)": (CHAINS, 'username="RamiLevi", polled=("Price", "Promo")),', 'username="RamiLevi"),'),
    "a full kind among the polled (q23 chains)": (CHAINS, '"https://prices.carrefour.co.il", polled=("Price", "Promo")),',
                                                  '"https://prices.carrefour.co.il", polled=("PriceFull", "Price", "Promo")),'),
    "chains poll their update files by default (q23 chains)": (CHAINS, "    polled: tuple[str, ...] = ()\n", '    polled: tuple[str, ...] = ("Price", "Promo")\n'),
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
    "listing takes no kinds": (SOURCES, "def listing(self, http: Http, kinds: tuple[str, ...],\n", "def listing(self, http: Http,\n"),
    "download takes a URL, not the listed item": (SOURCES, "def download(self, http: Http, item: Listed,", "def download(self, http: Http, item: str,"),
    "download returns text": (SOURCES, ") -> bytes:", ") -> str:"),
    "ListingUnreadable is an HttpError": (SOURCES, "class ListingUnreadable(Exception):", 'class ListingUnreadable(__import__("collector.http").http.HttpError):'),
    "Source without its unparsed count": (SOURCES, "    unparsed: int  #", "    #"),
    # shufersal: paging (ruling R11) and one page at a time (R16)
    "stops after page 1": (SHUFERSAL, "    for page in range(at + 1, last + 1):", "    for page in range(at + 1, at + 1):"),
    "a page past the last read": (SHUFERSAL, "range(at + 1, last + 1)", "range(at + 1, last + 2)"),
    "last page taken from the > link": (SHUFERSAL, 'LAST_PAGE = ">>"', 'LAST_PAGE = ">"'),
    "pager text read with its entities": (SHUFERSAL, "super().__init__(convert_charrefs=True)", "super().__init__(convert_charrefs=False)"),
    "no pager read as two pages": (SHUFERSAL, "first.last_page or 1", "first.last_page or 2"),
    "pager without >> read as one page": (SHUFERSAL, '        raise ListingUnreadable(f"{kind} page {page}: the pager names no last page")', "        return 1"),
    "last-page link naming two pages read as its first": (SHUFERSAL, "    if len(pages) != 1 or not pages[0].isdecimal():", "    if not pages or not pages[0].isdecimal():"),
    "last page that is no number escapes as ValueError": (SHUFERSAL, " or not pages[0].isdecimal():", ":"),
    "zero rows read as empty day": (SHUFERSAL, "    if not grid.rows:", "    if False:"),
    "all pages read before the first row": (SHUFERSAL, "    for record, rows, given in _reads(reader, start):",
                                            "    for record, rows, given in list(_reads(reader, start)):"),
    "a page's rows given before all are checked": (SHUFERSAL, "        rows.append((name, _checked_link(cells[0].href, name, where)))\n    return rows, grid, seconds, tries\n",
                                                   "        rows.append((name, _checked_link(cells[0].href, name, where)))\n        return rows, grid, seconds, tries\n"),
    "listing URL without storeId=0": (SHUFERSAL, "&storeId=0&page={page}", "&page={page}"),
    "categories swapped": (SHUFERSAL, '"Promo": 3, "PromoFull": 4', '"Promo": 4, "PromoFull": 3'),
    # shufersal: rows and links (ruling R15)
    "row of another shape read": (SHUFERSAL, "        if len(cells) != CELLS:", "        if False:"),
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
    "unparsed names not counted": (SHUFERSAL, "                self.unparsed += 1", "                pass"),
    "unparsed count carried over from the last listing": (SHUFERSAL, "        self.unparsed = 0\n        for kind in kinds:", "        for kind in kinds:"),
    "rows of another kind listed": (SHUFERSAL, "            elif name.kind in kinds:", "            else:"),
    # shufersal: the record of each page read (q21)
    "a page reported after its rows (q21 pages)": (SHUFERSAL, "        report(record)\n        if given:\n            yield record, rows\n",
                                                   "        if given:\n            yield record, rows\n        report(record)\n"),
    "rows not checked for order (q21 pages)": (SHUFERSAL, "    if not all(earlier <= later for earlier, later in itertools.pairwise(names)):", "    if False:"),
    "a page's first name not compared with the page before (q21 pages)": (SHUFERSAL, "    return before is None or before.page != page - 1 or before.last <= names[0]", "    return True"),
    "the page boundary compared strictly (q21 pages)": (SHUFERSAL, "before.last <= names[0]", "before.last < names[0]"),
    "every row given ends its page (q21 pages)": (SHUFERSAL, "                given.append(Listed(name, link))", "                given.append(Listed(name, link, ends_page=True))"),
    "a page's last row ends it only when it parses (q21 pages)": (SHUFERSAL, "        if given:\n            given[-1] = replace(given[-1], ends_page=True)",
                                                                  "        if given and given[-1].name.raw == rows[-1][0]:\n            given[-1] = replace(given[-1], ends_page=True)"),
    "seconds not timed (q21 pages)": (SHUFERSAL, "    seconds = timer() - started", "    seconds = 0.0"),
    "a later page's pager read strictly (q21 pages)": (SHUFERSAL, "        if page == 1:\n            raise\n        return None", "        raise"),
    # shufersal: where each kind starts (q21)
    "no overlap: the resume reads the page after the furthest (q21 start)": (SHUFERSAL_REPLAYED, "at = min(start.page, last)", "at = min(start.page + 1, last)"),
    "page 1 skipped on a resume (q21 start)": (SHUFERSAL_REPLAYED, "    yield first, rows, True\n", "    yield first, rows, start.page == 1\n"),
    "detours after page 1 (q21 start)": (SHUFERSAL, "    for page in start.detours:\n        record, rows = read(page)\n        yield record, rows, True\n    first, rows = read(1)\n    yield first, rows, True\n",
                                         "    first, rows = read(1)\n    yield first, rows, True\n    for page in start.detours:\n        record, rows = read(page)\n        yield record, rows, True\n"),
    "no step back (q21 start)": (SHUFERSAL, "        while at > 2 and record.first > start.furthest:", "        while False:"),
    "the step back goes below page 2 (q21 start)": (SHUFERSAL, "while at > 2 and", "while at > 1 and"),
    "the step back on an equal first name (q21 start)": (SHUFERSAL, "record.first > start.furthest", "record.first >= start.furthest"),
    "a resume page past the last read as given (q21 start)": (SHUFERSAL, "at = min(start.page, last)", "at = start.page"),
    "starts ignored (q21 start)": (SHUFERSAL, "start = (starts or {}).get(kind, Start())", "start = Start()"),
    "a page stepped back over gives its rows (q21 start)": (SHUFERSAL, "            yield record, rows, False\n", "            yield record, rows, True\n"),
    "a page stepped back over not reported (q21 start)": (SHUFERSAL, "        report(record)\n        if given:\n", "        if given:\n            report(record)\n"),
    "pages read out of number order compared (q21 start)": (SHUFERSAL, "before.page != page - 1 or ", ""),
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
    "refreshed link not used": (SHUFERSAL, "        return http.get(link).body", "        return http.get(item.url).body"),
    "refreshed more than once": (SHUFERSAL, "        return http.get(link).body", "        return self.download(http, Listed(item.name, link), short_of_time)"),
    "file gone after expiry read as unreadable": (SHUFERSAL, '    raise HttpError(f"{item.name.raw}: its link expired', '    raise ListingUnreadable(f"{item.name.raw}: its link expired'),
    # shufersal: a listing page that times out is asked again (q24)
    "a timed-out page not asked again (q24 tries)": (SHUFERSAL_REPLAYED, "PAGE_TRIES = 3  #", "PAGE_TRIES = 1  #"),
    "a timed-out page not asked again, the 2026-11-06 replay alone (q24 replay)": (NOV_6_REPLAY, "PAGE_TRIES = 3  #", "PAGE_TRIES = 1  #"),
    "a fourth try (q24 tries)": (SHUFERSAL, "PAGE_TRIES = 3  #", "PAGE_TRIES = 4  #"),
    "no pause (q24 tries)": (SHUFERSAL, "            sleep(RETRY_PAUSE)\n", "            pass\n"),
    "a pause before the first try (q24 tries)": (PAUSE_ON_FIRST_TRY, "        if attempt > 1:\n            sleep(RETRY_PAUSE)\n", "        sleep(RETRY_PAUSE)\n"),
    "a pause of another length (q24 tries)": (SHUFERSAL, "RETRY_PAUSE = 10.0", "RETRY_PAUSE = 1.0"),
    "no time check before the pause (q24 tries)": (SHUFERSAL, "            stopped = attempt < PAGE_TRIES and short_of_time()", "            stopped = False"),
    "a time check after the last try (q24 tries)": (SHUFERSAL, "stopped = attempt < PAGE_TRIES and short_of_time()", "stopped = short_of_time()"),
    "a try the time check then stops still says again in 10 s (q24 tries)": (SHUFERSAL, 'again = "" if attempt == PAGE_TRIES or stopped else', 'again = "" if attempt == PAGE_TRIES else'),
    "the time stop before the pause naming the try that timed out (q24 tries)": (SHUFERSAL, "raise OutOfTime(_time_stop(kind, page, attempt + 1))", "raise OutOfTime(_time_stop(kind, page, attempt))"),
    "the pause after the time check (q24 tries)": (SHUFERSAL, "        if attempt > 1:\n            sleep(RETRY_PAUSE)\n        if short_of_time():\n            raise OutOfTime(stop)\n",
                                                   "        if short_of_time():\n            raise OutOfTime(stop)\n        if attempt > 1:\n            sleep(RETRY_PAUSE)\n"),
    "the time not checked after the pause (q24 tries)": (SHUFERSAL, "        if short_of_time():\n            raise OutOfTime(stop)\n        started", "        if attempt == 1 and short_of_time():\n            raise OutOfTime(stop)\n        started"),
    "any HttpError asked again (q24 tries)": (SHUFERSAL, "        except HttpTimeout as timeout:", "        except HttpError as timeout:"),
    "a block asked again (q24 tries)": (BLOCK_TRIED_AGAIN, "        except HttpTimeout as timeout:", "        except (HttpTimeout, Blocked) as timeout:"),
    "tries not recorded (q24 tries)": (SHUFERSAL, "_in_order(names, self.before, page), tries)", "_in_order(names, self.before, page))"),
    "the failed tries' seconds kept (q24 tries)": (SHUFERSAL, "        started = timer()\n", "        started = timer() if attempt == 1 else started\n"),
    "the error not naming the page and the tries (q24 tries)": (SHUFERSAL, '    raise HttpError(f"{kind} page {page} timed out on {PAGE_TRIES} tries: {last}") from last', "    raise last"),
    "a timed-out try not reported (q24 tries)": (SHUFERSAL, "            on_timeout(PageTimeout(kind, page, attempt, waited))", "            pass"),
    "a failed try not logged at WARNING (q24 tries)": (SHUFERSAL, "            log.warning(", "            log.info("),
    "a time stop before a later try not naming it (q24 tries)": (SHUFERSAL, '            else f"before try {attempt} of page {page} of the {kind} listing")',
                                                                 '            else f"before page {page} of the {kind} listing")'),
    "the refresh not given the pause (q24 tries)": (SHUFERSAL, "link = _fresh_link(http, item, short_of_time, self._timer, self._sleep)", "link = _fresh_link(http, item, short_of_time, self._timer, lambda seconds: None)"),
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
    "a repeated name stops the listing at once": (NCR, "    try:\n        fnames, repeat = _read_through(http, length, token, username, short_of_time)\n", "    raise ListingUnreadable(repeat)\n    try:\n        fnames, repeat = _read_through(http, length, token, username, short_of_time)\n"),
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
    # ncr: an adapter that does not page makes no request after its first row (q26, ruling R40; Carrefour's below)
    "an NCR request between rows (q26 adapters)": (NCR, "        yield from listed\n", "        for item in listed:\n            yield item\n            http.get(LOGIN_PAGE)\n"),
    "NCR rows given answer by answer (q26 adapters)": (NCR_WHOLE_READ, _NCR_LISTED, _NCR_ANSWER_BY_ANSWER),
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
    "a Carrefour request between rows (q26 adapters)": (CARREFOUR, "        yield from listed\n", '        for item in listed:\n            yield item\n            http.get(f"{BASE_URL}/")\n'),
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
    "clock date instead of file date": (RUN, "        if item.name.day != self.day:", "        if _utc(self.now()).date() != self.day:"),
    "stored files fetched again": (RUN, _RUN_SKIP, "        if name is None:\n            return\n"),
    "no latch on block": (RUN, '            self.store.write_state(self.slug, {"stopped": True,', '            (self.slug, {"stopped": True,'),
    "timeout guard removed": (RUN, "            if self._short_of_time():\n                if problem is None:", "            if False:\n                if problem is None:"),
    "manifest skipped on error": (RUN, "        store.put_record(manifest_key(", "        result.error is None and store.put_record(manifest_key("),
    # run: choosing that day's files
    "older files selected": (RUN, "        if item.name.day != self.day:", "        if item.name.day > self.day:"),
    "kinds not filtered again": (RUN, _RUN_KIND_FILTER, ""),
    "unknown kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(allowed):", "    if not kinds:"),
    "no kinds accepted": (RUN, "    if not kinds or not set(kinds) <= set(allowed):", "    if not set(kinds) <= set(allowed):"),
    "kinds the chain does not collect accepted": (RUN, "set(kinds) <= set(allowed)", "set(kinds) <= {'Stores', 'PriceFull', 'PromoFull', 'Price', 'Promo'}"),
    "kinds not recorded (R4)": (RUN, "RunResult(chain.slug, run_id, mode, day, list(kinds))", "RunResult(chain.slug, run_id, mode, day, [])"),
    "stored name taken from the listing, not the link (R16)": (RUN, "        name = stored_name(item)\n        if name in self.seen:\n",
                                                               "        name = item.name.raw\n        if name in self.seen:\n"),
    "stored name keeps the link's query (R16)": (RUN, '    return urllib.parse.urlsplit(item.url).path.rsplit("/", 1)[-1]', '    return item.url.rsplit("/", 1)[-1]'),
    "skipped names not listed": (RUN, "        self.seen.add(name)\n        self.result.listed.append(name)\n",
                                 "        self.seen.add(name)\n        if name in self.stored:\n            return None\n"
                                 "        self.result.listed.append(name)\n"),
    "a name listed twice fetched again": (RUN, "        if name in self.seen:\n            return None  #", "        if False:\n            return None  #"),
    # run: the listing
    "listing read before the files are fetched (R16)": (RUN, "            listing = iter(self.source.listing(self.http, self.kinds, self._short_of_time, **paged))", "            listing = iter(list(self.source.listing(self.http, self.kinds, self._short_of_time, **paged)))"),
    "listing read twice": (RUN, "            listing = iter(self.source.listing(self.http, self.kinds, self._short_of_time, **paged))",
                           "            listing = iter(self.source.listing(self.http, self.kinds, self._short_of_time, **paged)) if list(self.source.listing(self.http, self.kinds, self._short_of_time, **paged)) or True else None"),
    "listing_read_at in local time": (RUN, "self.result.listing_read_at = _utc(self.now()).isoformat()", "self.result.listing_read_at = self.now().isoformat()"),
    "unparsed not recorded (R13)": (RUN, "            self.result.unparsed = self.source.unparsed  #", "            pass  #"),
    "unparsed read before the listing is used up (R13)": (RUN, "                self._take(item)\n                self._check_time()\n            self.result.unparsed = self.source.unparsed  # final only now: it resets on the first next()\n",
                                                          "                self.result.unparsed = self.source.unparsed\n                self._take(item)\n                self._check_time()\n"),
    "unparsed taken from an unfinished listing (R13)": (RUN, _RUN_STOP + _RUN_DRAIN_IF,
                                                        _RUN_STOP + "            self.result.unparsed = self.source.unparsed\n" + _RUN_DRAIN_IF),
    "block in the listing escapes": (RUN, "        except Blocked as block:\n            self._latch(str(block))", "        except ZeroDivisionError as block:\n            self._latch(str(block))"),
    "unreadable listing escapes (R23)": (RUN, "        except ListingUnreadable as exc:\n", "        except ZeroDivisionError as exc:\n"),
    "unreadable listing not recorded as an error (R23)": (RUN, '            self._stop(f"listing unreadable: {exc}")\n        except OutOfTime:', "            raise _Stop\n        except OutOfTime:"),
    "listing HTTP error escapes": (RUN, "        except HttpError as exc:  # not read again", "        except ZeroDivisionError as exc:  # not read again"),
    "listing HTTP error not recorded as an error": (RUN, '            self._stop(f"listing failed: {exc}")', "            raise _Stop"),
    # run: a paged listing, where each kind starts and the pages it reads (ruling R37)
    "earlier manifests not read (q21 run)": (RUN, "        starts = {kind: rule(earlier, kind, self.stored) for kind in self.kinds}\n", "        starts = {}\n"),
    "starts read for a source that does not page (q21 run)": (RUN, "        if not isinstance(self.source, PagedSource):\n            return {}\n" + _RUN_READ_EARLIER,
                                                              _RUN_READ_EARLIER + "        if not isinstance(self.source, PagedSource):\n            return {}\n"),
    "another chain's manifests read (q21 run)": (RUN, 'prefix = manifest_key(self.day, self.slug, "").removesuffix(".json")', 'prefix = manifest_key(self.day, "", "").removesuffix("-.json")'),
    "another day's manifests read (q21 run)": (RUN, "        earlier = [json.loads(record) for record in self.store.read_records(prefix)]\n",
                                               "        earlier = [json.loads(record) for day in (date.fromordinal(self.day.toordinal() - 1), self.day)"
                                               " for record in self.store.read_records(manifest_key(day, self.slug, \"\").removesuffix(\".json\"))]\n"),
    "taken through not recorded (q21 run)": (RUN, '            page["taken_through"] = page["last"] if item.ends_page else item.name.raw\n', ""),
    "taken through recorded after the day filter (q21 run)": (RUN, _RUN_TAKEN + _RUN_LISTED + _RUN_SKIP,
                                                              _RUN_LISTED + "        if name is None:\n            return\n" + _RUN_TAKEN
                                                              + "        if name in self.stored:\n            return\n"),
    "taken through recorded after the download (q21 run)": (RUN, _RUN_TAKEN + _RUN_TO_DOWNLOAD + _RUN_STORED,
                                                            _RUN_TO_DOWNLOAD + _RUN_STORED + _RUN_TAKEN),
    "taken through set on a page before the latest (q21 run)": (RUN, "            page = self.result.pages[-1]\n", "            page = self.result.pages[0]\n"),
    "ends_page ignored (q21 run)": (RUN, 'page["taken_through"] = page["last"] if item.ends_page else item.name.raw', 'page["taken_through"] = item.name.raw'),
    "a page recorded taken before a row is given (q21 run)": (RUN, '| {"taken_through": None})', '| {"taken_through": read.last})'),
    "pages left out of the manifest (q21 run)": (RUN, '| {"day": result.day.isoformat(), "code_sha": code_sha}', '| {"day": result.day.isoformat(), "code_sha": code_sha, "pages": []}'),
    "page logged below INFO (q21 run)": (RUN, '        log.info("%s %s page %d of %s:', '        log.debug("%s %s page %d of %s:'),
    "page count read from any page (q21 run)": (RUN, "        if read.page == 1:\n            self.page_counts", "        if True:\n            self.page_counts"),
    "page count not per kind (q21 run)": (RUN, 'self.page_counts.get(read.kind, "?")', 'next(iter(self.page_counts.values()), "?")'),
    "a one-page list's count not 1 (q21 run)": (RUN, "read.last_page or 1  #", "read.last_page  #"),
    "a failed read of the earlier manifests falls back to a fresh pass (q21 run)": (RUN,
        "            paged = self._paged()  # first: a failed read of the earlier manifests leaves no listing time\n",
        "            try:\n                paged = self._paged()\n            except Exception:\n                paged = {}\n"),
    # run: a listing page that timed out, its tries kept and logged (q24)
    "the log line without the try (q24 run)": (RUN, 'f" (try {read.tries})" if read.tries > 1 else ""', '""'),
    "the try shown on a page read on its first try (q24 run)": (RUN, 'if read.tries > 1 else ""', 'if read.tries >= 1 else ""'),
    "a failed try not listed (q24 run)": (RUN, "        self.result.timeouts.append(dataclasses.asdict(timeout))\n", "        pass\n"),
    "the failed tries not handed to the listing (q24 run)": (RUN, ', "on_timeout": self._timeout}', "}"),
    "the failed tries dropped when the run stops on time (q24 run)": (RUN,
        "        except OutOfTime:  # an adapter's own request, short of time\n            self._stop(OUT_OF_TIME)\n",
        "        except OutOfTime:  # an adapter's own request, short of time\n            self.result.timeouts.clear()\n"
        "            self._stop(OUT_OF_TIME)\n"),
    "the failed tries left out of the manifest (q24 run)": (RUN, '| {"day": result.day.isoformat(), "code_sha": code_sha}',
                                                            '| {"day": result.day.isoformat(), "code_sha": code_sha, "timeouts": []}'),
    # run: a poll run held to the chain's polled kinds, other days' names counted, a paged poll's start (q23)
    "a poll held to the morning's kinds (q23 run)": (RUN, '    allowed = chain.polled if mode == "poll" else chain.kinds\n', "    allowed = chain.kinds\n"),
    "a main or retry run held to the polled kinds (q23 run)": (RUN, '    allowed = chain.polled if mode == "poll" else chain.kinds\n', "    allowed = chain.polled\n"),
    "a refused poll's kinds named as the kinds the chain collects (q23 run)": (RUN, "{'polls' if mode == 'poll' else 'collects'}", "collects"),
    "the run's own day counted in other_days (q23 run)": (RUN, _RUN_OTHER_DAY, "        self._other_day(item)\n        if item.name.day != self.day:\n            return None\n"),
    "other_days left empty (q23 run)": (RUN, "        self.result.other_days[day] = self.result.other_days.get(day, 0) + 1\n", ""),
    "a name listed twice counted twice in other_days (q23 run)": (RUN, "        if name in self.others:\n            return  # listed again: counted once\n", ""),
    "kinds not asked for counted in other_days (q23 run)": (RUN, _RUN_KIND_FILTER + _RUN_OTHER_DAY, _RUN_OTHER_DAY + _RUN_KIND_FILTER),
    "other_days left out of the manifest (q23 run)": (RUN, '| {"day": result.day.isoformat(), "code_sha": code_sha}',
                                                      '| {"day": result.day.isoformat(), "code_sha": code_sha, "other_days": {}}'),
    "a poll started by R37's rule (q23 run)": (RUN, '        rule = pass_start if self.result.mode == "poll" else start_for\n', "        rule = start_for\n"),
    "a poll started by R37's rule, the Promo replay alone (q23 replay)": (PROMO_REPLAY, '        rule = pass_start if self.result.mode == "poll" else start_for\n', "        rule = start_for\n"),
    "no step back, the republish replay alone (q23 replay)": (PROMO_REPUBLISHED, "        while at > 2 and record.first > start.furthest:", "        while False:"),
    "a full kind started by the passes rule (q23 run)": (RUN, '        rule = pass_start if self.result.mode == "poll" else start_for\n', "        rule = pass_start\n"),
    # run: a poll's time stop reads the rest of a listing that does not page, taking nothing, and a fault met there
    # never reads as a time stop (q26, ruling R40)
    "a main or retry run drained (q26 drain)": (RUN, 'OUT_OF_TIME and self.result.mode == "poll" and listing', "OUT_OF_TIME and listing"),
    "a poll's time stop not drained (q26 drain)": (RUN, _RUN_DRAIN_CALL, "                pass\n"),
    "a drained name stored before put in not_attempted (q26 drain)": (RUN, "            if name is not None and name not in self.stored:\n",
                                                                      "            if name is not None:\n"),
    "the drain downloads and stores (q26 drain)": (RUN,
        "            if name is not None and name not in self.stored:\n                self.result.not_attempted.append(name)\n",
        "            if name is not None and name not in self.stored:\n"
        "                self._store(name, self.source.download(self.http, item))\n"),
    "the drain lists every row (q26 drain)": (RUN, "            name = self._listed(item)\n",
                                              "            name = stored_name(item)\n            self.result.listed.append(name)\n"),
    "any stop drains (q26 drain)": (RUN, "            if (self.result.error == OUT_OF_TIME and self.result.mode", "            if (self.result.mode"),
    "a paged listing drained (q26 drain)": (RUN, " and listing is not None\n                    and not isinstance(self.source, PagedSource)):",
                                            " and listing is not None):"),
    "OutOfTime in the drain escapes (q26 drain)": (RUN, "            except (StopIteration, OutOfTime):", "            except StopIteration:"),
    "a stop before the listing drained (q26 drain)": (RUN, ' and self.result.mode == "poll" and listing is not None\n',
                                                      ' and self.result.mode == "poll"\n'),
    "a fault in the drain left as a time stop (q26 drain)": (RUN,
        '                self.result.error = f"unexpected error: {type(exc).__name__}: {exc}"\n                raise\n',
        "                raise\n"),
    "a block in the drain not latched (q26 drain)": (RUN, "            except Blocked as block:\n                try:\n",
                                                     "            except ZeroDivisionError as block:\n                try:\n"),
    "a latch not written in the drain swallowed (q26 drain)": (RUN, "                except _Stop:\n                    return\n",
                                                               "                except Exception:\n                    return\n"),
    "a latch not written in the drain rewritten by its catch-all (q26 drain)": (RUN, _RUN_DRAIN_NEXT,
        "            try:\n"
        "                try:\n"
        "                    item = next(listing)\n"
        "                except Blocked as block:\n"
        "                    try:\n"
        "                        self._latch(str(block))\n"
        "                    except _Stop:\n"
        "                        return\n"
        "            except (StopIteration, OutOfTime):\n"
        "                return\n"
        "            except Exception as exc:\n"),
    "unparsed read after a drain (q26 drain)": (RUN, _RUN_DRAIN_CALL,
                                                _RUN_DRAIN_CALL + "                self.result.unparsed = self.source.unparsed\n"),
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
    # the run's time check, lent to the adapters for the requests they make on their own
    "Shufersal page read short of time": (SHUFERSAL, "        if short_of_time():\n            raise OutOfTime(stop)\n        started", "        if False:\n            raise OutOfTime(stop)\n        started"),
    "Shufersal listing not given the time check": (SHUFERSAL, "for _, rows in _pages(http, kind, short_of_time, start, on_page, on_timeout, self._timer, self._sleep):", "for _, rows in _pages(http, kind, never_short, start, on_page, on_timeout, self._timer, self._sleep):"),
    "Shufersal refresh not given the time check": (SHUFERSAL, "link = _fresh_link(http, item, short_of_time, self._timer, self._sleep)", "link = _fresh_link(http, item, never_short, self._timer, self._sleep)"),
    "Shufersal fresh link fetched short of time": (SHUFERSAL, "        if short_of_time():\n            raise OutOfTime(f\"{item.name.raw}: its link expired; stopped before the fresh", "        if False:\n            raise OutOfTime(f\"{item.name.raw}: its link expired; stopped before the fresh"),
    "Shufersal refresh stop not naming the file": (SHUFERSAL, '            raise OutOfTime(f"{item.name.raw}: its link expired; stopped {stop}") from None', "            raise"),
    "NCR listing answer asked for short of time": (NCR, "        if short_of_time():\n            raise OutOfTime(f\"before the NCR listing's answer", "        if False:\n            raise OutOfTime(f\"before the NCR listing's answer"),
    "NCR listing not given the time check": (NCR, "_fnames(http, file_page, self.username, short_of_time)", "_fnames(http, file_page, self.username, never_short)"),
    "NCR first read not given the time check": (NCR, "    length = _page_size(file_page)\n    fnames, repeat = _read_through(http, length, token, username, short_of_time)", "    length = _page_size(file_page)\n    fnames, repeat = _read_through(http, length, token, username, never_short)"),
    "NCR second read not given the time check": (NCR, "    try:\n        fnames, repeat = _read_through(http, length, token, username, short_of_time)", "    try:\n        fnames, repeat = _read_through(http, length, token, username, never_short)"),
    "NCR second read's time stop not saying so": (NCR, '    except OutOfTime as stop:\n        raise OutOfTime(f"{stop}, on the second read") from None\n', ""),
    "run lends the listing no time check": (RUN, "self.source.listing(self.http, self.kinds, self._short_of_time, **paged)", "self.source.listing(self.http, self.kinds, **paged)"),
    "run lends the download no time check": (RUN, "self.source.download(self.http, item, self._short_of_time)", "self.source.download(self.http, item)"),
    "run an adapter's time stop in the listing escapes": (RUN, "        except OutOfTime:  # an adapter's own request, short of time\n", "        except ZeroDivisionError:  # an adapter's own request, short of time\n"),
    "run an adapter's time stop in the listing not recorded": (RUN, "            self._stop(OUT_OF_TIME)\n        except HttpError", "            raise _Stop\n        except HttpError"),
    "run a download's time stop not failing the file": (RUN, '                self.result.failed[name] = f"{exc}: under 90 s left"\n', ""),
    "run a download's time stop retried": (RUN, '                self.result.failed[name] = f"{exc}: under 90 s left"\n                self._stop(OUT_OF_TIME)\n', "                problem = str(exc)\n                continue\n"),
    "a caller with no time limit always short": (NEVER_SHORT, '    """The time check for a caller with no time limit."""\n    return False', '    """The time check for a caller with no time limit."""\n    return True'),
    "a failed put stops the run (R23)": (RUN, "        except Exception as exc:  # a storage hiccup", "        except ZeroDivisionError as exc:  # a storage hiccup"),
    "files entry's SHA-256 not the body's": (RUN, '"sha256": hashlib.sha256(data).hexdigest()', '"sha256": hashlib.sha256(name.encode()).hexdigest()'),
    "files entry's size not the body's": (RUN, '"size": len(data),', '"size": len(name),'),
    # run: time (R23)
    "time guard at 0 s": (RUN, "MIN_TIME_LEFT = 90.0", "MIN_TIME_LEFT = 0.0"),
    "time guard back at the old 60 s (R32)": (RUN, "MIN_TIME_LEFT = 90.0", "MIN_TIME_LEFT = 60.0"),
    "ninety seconds left read as too few": (RUN, "        return self.time_left() < MIN_TIME_LEFT", "        return self.time_left() <= MIN_TIME_LEFT"),
    "time not checked before the listing": (RUN, "            self._check_time()\n            paged = self._paged()", "            paged = self._paged()"),
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
    "every missing name in the alert": (CHECK, "{', '.join(names[:MAX_NAMES])}{tail}", "{', '.join(names)}{tail}"),
    "the record holds only ten missing names": (CHECK, '        "missing": missing,', '        "missing": missing[:MAX_NAMES],'),
    "only the retry's names checked": (CHECK, 'listed = {name for manifest in manifests for name in manifest["listed"]}',
                                       'listed = {name for manifest in manifests if manifest["mode"] == "retry" for name in manifest["listed"]}'),
    "missing judged against another day's files": (CHECK, "    stored = store.stored_names(slug, day)\n", "    stored = store.stored_names(slug, day - timedelta(days=1))\n"),
    "manifests of every day read": (CHECK, '    prefix = manifest_key(day, "", "").rsplit("/", 1)[0] + "/"', '    prefix = "manifests/"'),
    "a chain reads every chain's manifests": (CHECK, 'for manifest in manifests.get(slug, []) if manifest["mode"] in MORNING]',
                                              'for manifest in [m for ms in manifests.values() for m in ms] if manifest["mode"] in MORNING]'),
    "the check ignores the kinds it is given": (CHECK, "(kinds or {}).get(slug, KINDS)", "KINDS"),
    "a chain left out of kinds held to none": (CHECK, "(kinds or {}).get(slug, KINDS)", "(kinds or {}).get(slug, ())"),
    "uncovered kinds read from all five, not the chain's": (CHECK, "    uncovered = [kind for kind in kinds if kind not in covered]", "    uncovered = [kind for kind in KINDS if kind not in covered]"),
    "conflict copy not counted as stored by the check": (STORE_FOR_CHECK, '    return copy["name"] if copy else name', "    return name"),
    # check: stopped chains
    "stopped alerted every check": (CHECK, 'if state.get("stopped") and not state.get("alerted"):', 'if state.get("stopped"):'),
    "a state that is not stopped alerts": (CHECK, 'if state.get("stopped") and not state.get("alerted"):', 'if not state.get("alerted"):'),
    "stopped state not marked alerted": (CHECK, '                store.write_state(alert.chain, state | {"alerted": True})', "                pass"),
    "stopped state replaced, not updated": (CHECK, 'store.write_state(alert.chain, state | {"alerted": True})', 'store.write_state(alert.chain, {"alerted": True})'),
    "check_day marks the state itself (R26)": (CHECK, "    alerts = morning + update_alerts\n", "    alerts = morning + update_alerts\n    mark_alerted(store, alerts)\n"),
    "chains with other alerts marked alerted (R26)": (CHECK, '        if alert.kind == "stopped":\n', "        if True:\n"),
    "a chain cleared since the check marked alerted (R26)": (CHECK, '            if state.get("stopped"):\n                store.write_state(alert.chain', "            if True:\n                store.write_state(alert.chain"),
    "stopped alert without its reason": (CHECK, "{state.get('since')}: {state.get('reason')}. ", "{state.get('since')}. "),
    "stopped chain not in the record": (CHECK, '"stopped": {"since": state.get("since"), "reason": state.get("reason")} if state.get("stopped") else None,', '"stopped": None,'),
    # check: failed runs (R4)
    "retry manifest not required": (CHECK, "    if uncovered:\n        problems.append", "    if False:\n        problems.append"),
    "main runs stand in for the retry (R4)": (CHECK, '    retries = [manifest for manifest in manifests if manifest["mode"] == "retry"]', "    retries = list(manifests)"),
    "one retry run enough for every kind (R4)": (CHECK, "    uncovered = [kind for kind in kinds if kind not in covered]", "    uncovered = [] if retries else list(kinds)"),
    "retry error not alerted (R4)": (CHECK, 'for manifest in retries if manifest["error"] and manifest not in excused]', "for manifest in retries if False]"),
    "blocked retry read as failed (R4)": (CHECK, 'for manifest in retries if manifest["error"] and manifest not in excused]',
                                          'for manifest in retries if (manifest["error"] or manifest["blocked"]) and manifest not in excused]'),
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
    "a full kind no run listed passes": (CHECK, "problems + _unlisted(manifests, retries, kinds) + ", "problems + "),
    "a full kind counted from the retry runs alone": (CHECK, "problems + _unlisted(manifests, retries, kinds)", "problems + _unlisted(retries, retries, kinds)"),
    "a blocked run leaves the full-kind alarm on": (CHECK, '    if any(manifest["blocked"] for manifest in retries):\n        return []\n', ""),
    "a main run's block silences the full-kind alarm": (CHECK, 'if any(manifest["blocked"] for manifest in retries):', 'if any(manifest["blocked"] for manifest in manifests):'),
    "a full kind the chain does not collect required": (CHECK, "if kind in kinds and kind not in listed]", "if kind not in listed]"),
    "PromoFull left out of the full kinds": (CHECK, 'FULL_KINDS = ("PriceFull", "PromoFull")', 'FULL_KINDS = ("PriceFull",)'),
    # check: a retry run short of time on a day read in full (R36, as R37 amends it); what reads a listing in full
    # moved to pages.py with R37, and the R36 tests still prove it there
    "a retry short of time excused with something missing (R36)": (CHECK, "    if missing:\n        return []\n", ""),
    "a retry short of time excused with no listing read in full (R36)": (CHECK, '    if not all(read_in_full(manifests, kind) is not None for kind in retry["kinds"]):\n        return False\n', ""),
    "one kind read in full excuses a retry over several (R36)": (CHECK, 'if not all(read_in_full(manifests, kind) is not None', 'if not any(read_in_full(manifests, kind) is not None'),
    "a retry's names not checked against the complete runs' (R36)": (CHECK, '    return set(retry["listed"]) <= seen\n', "    return True\n"),
    "a run that ended with an error read as a listing read in full (R36)": (PAGES_FOR_CHECK, 'if not manifest.get("pages") and not manifest["error"]}', 'if not manifest.get("pages")}'),
    "a blocked run read as a listing read in full (R36)": (PAGES_FOR_CHECK, 'if kind in manifest["kinds"] and not manifest["blocked"]]', 'if kind in manifest["kinds"]]'),
    "only a main run read as a listing read in full (R36)": (PAGES_FOR_CHECK, 'if not manifest.get("pages") and not manifest["error"]}',
                                                             'if manifest["mode"] == "main" and not manifest.get("pages") and not manifest["error"]}'),
    "any error excused, not only the time stop (R36)": (CHECK, 'manifest["error"] == OUT_OF_TIME', 'manifest["error"]'),
    "the time stop matched as part of an error (R36)": (CHECK, 'manifest["error"] == OUT_OF_TIME', 'OUT_OF_TIME in (manifest["error"] or "")'),
    "a main run's time stop recorded as an excused retry (R36)": (CHECK, 'if manifest["mode"] == "retry" and manifest["error"] == OUT_OF_TIME', 'if manifest["error"] == OUT_OF_TIME'),
    "an excused retry still a failed run (R36)": (CHECK, ' and manifest not in excused]', "]"),
    "an excused retry not in the record (R36)": (CHECK, "\"short_of_time\": [f\"{manifest['run_id']} ({', '.join(manifest['kinds'])})\" for manifest in excused],", '"short_of_time": [],'),
    # check: the day's pages joined across runs, in the record, the excuse and the alert (R37)
    "read_in_full left out of the record (R37)": (CHECK, '        "read_in_full": {kind: read_in_full(manifests, kind) for kind in FULL_KINDS if kind in kinds},\n',
                                                  '        "read_in_full": {},\n'),
    "a full kind the chain does not collect recorded (R37)": (CHECK, "read_in_full(manifests, kind) for kind in FULL_KINDS if kind in kinds}", "read_in_full(manifests, kind) for kind in FULL_KINDS}"),
    "the retry's own names vouch for it (R37)": (CHECK, '    others = [manifest for manifest in manifests if manifest["run_id"] != retry["run_id"]]', "    others = manifests"),
    "the vouching runs found with the retry's own pages (R37)": (CHECK, "        readers = read_in_full(others, kind) or []", "        readers = read_in_full(manifests, kind) or []"),
    "a kind not read in full excuses the retry (R37)": (CHECK, 'read_in_full(manifests, kind) is not None for kind in retry["kinds"]',
                                                        'any(not run["error"] and not run["blocked"] for run in manifests if kind in run["kinds"]) for kind in retry["kinds"]'),
    "a second whole pass does not vouch (R37)": (CHECK, " or read_in_full([manifest], kind) is not None]", "]"),
    "a run that read part of the list vouches (R37)": (CHECK, 'if manifest["run_id"] in readers or read_in_full([manifest], kind) is not None]', 'if kind in manifest["kinds"]]'),
    "a run vouches for every kind it listed (R37)": (CHECK, " and parsed.kind == kind}", "}"),
    "not read in full never alerts (R37)": (CHECK, " + _not_read_in_full(manifests, retries, kinds)\n", "\n"),
    "not read in full alerts with a retry blocked (R37)": (CHECK, '    if any(retry["blocked"] for retry in retries):\n        return []\n', ""),
    "not read in full alerts on a chain with no page records (R37)": (CHECK, " and has_pages(manifests, kind)", ""),
    "a full kind the chain does not collect judged (R37)": (CHECK, "            if kind in kinds and has_pages(manifests, kind)", "            if has_pages(manifests, kind)"),
    "the pages never read left out of the sentence (R37)": (CHECK, 'f"the {kind} list was not read in full: {unread(manifests, kind)}"', 'f"the {kind} list was not read in full"'),
    # check: the morning judged from main and retry runs only (q23); a blocked poll silencing R35's or R37's reason is
    # pinned by test_a_blocked_poll_never_silences_the_mornings_reasons, which no single break can fail
    "the morning judgement reads the polls (q23 morning)": (CHECK, ' if manifest["mode"] in MORNING]', "]"),
    # check: the update day, the day before judged the next morning (q23, ruling R39)
    "the update day judged on the check's own day (q23 update day)": (CHECK, "judge_update_day(store, polled, day - timedelta(days=1))", "judge_update_day(store, polled, day)"),
    "every chain judged, polled or not (q23 update day)": (CHECK, "judge_update_day(store, polled, day - timedelta(days=1))",
                                                           'judge_update_day(store, dict.fromkeys(slugs, ("Price", "Promo")), day - timedelta(days=1))'),
    "the update day judged with no polled given (q23 update day)": (CHECK, "    if polled is not None:\n        update_alerts, update_day = judge_update_day(store, polled, ",
                                                                    "    if True:\n        update_alerts, update_day = judge_update_day(store, polled or {}, "),
    "the update day's alerts left out of the record (q23 update day)": (CHECK, '"alerts": [asdict(alert) for alert in alerts]}', '"alerts": [asdict(alert) for alert in morning]}'),
    "the update day's alerts before the morning's (q23 update day)": (CHECK, "    alerts = morning + update_alerts\n", "    alerts = update_alerts + morning\n"),
    "a name the morning listed reported again (q23 update day)": (CHECK, ' - stored_names - listed_by_morning)', " - stored_names)"),
    "a name stored since still missing (q23 update day)": (CHECK, 'poll["failed"]} - stored_names - listed_by_morning)', 'poll["failed"]} - listed_by_morning)'),
    "a name a poll never tried emailed (q23 update day)": (CHECK, 'for name in poll["failed"]} - stored_names', 'for name in [*poll["failed"], *poll["not_attempted"]]} - stored_names'),
    "not_tried left at zero (q23 update day)": (CHECK, '"not_tried": {kind: len(_of_kind(untried, kind)) for kind in kinds},', '"not_tried": {kind: 0 for kind in kinds},'),
    "a missing name counted in not_tried too (q23 update day)": (CHECK, " - stored_names - set(unstored)", " - stored_names"),
    "an open pass taken as read in full (q23 update day)": (CHECK, "if all(one.read_by is None for one in cut[kind])]", "if all(one.read_by is None and not one.open for one in cut[kind])]"),
    "no failed alert for a chain without page records (q23 update day)": (CHECK, "unread_kinds = [kind for kind in kinds if all(",
                                                                          "unread_kinds = [kind for kind in kinds if has_pages(manifests, kind) and all("),
    "the failed alert sent beside a block (q23 update day)": (CHECK, '    if any(poll["blocked"] for poll in polls):  # the stopped alert covers the day (as R35)\n        unread_kinds = []\n', ""),
    "a pass a page out of order ended left out of the record (q23 update day)": (CHECK, "for one in cut if one.read_by is None and one.out_of_order]", "for one in cut if False]"),
    "by_hour over every kind (q23 update day)": (CHECK, "for name in _of_kind(stored_names, kind))", "for name in stored_names)"),
    # pages: the day's readings of a kind joined across runs (R37)
    "a blocked run counted (R37 join)": (PAGES, 'if kind in manifest["kinds"] and not manifest["blocked"]]', 'if kind in manifest["kinds"]]'),
    "a legacy run with an error read in full (R37 join)": (PAGES, 'if not manifest.get("pages") and not manifest["error"]}', 'if not manifest.get("pages")}'),
    "pages not split into blocks at a jump (R37 join)": (PAGES, ' and record["page"] == before["page"] + 1 and', " and"),
    "a page taken part-way mid-run joined (R37 join)": (PAGES, ' and before["taken_through"] == before["last"]:', ":"),
    "a block from page 1 not open at the front (R37 join)": (PAGES, '    return BEFORE if record["page"] == 1 else (1, record["first"])', '    return 1, record["first"]'),
    "the last page open without every row taken (R37 join)": (PAGES, ' and record["taken_through"] == record["last"]:\n        return AFTER', ":\n        return AFTER"),
    "the end read from the highest page, not the run's own pager (R37 join)": (PAGES, 'own_last = next((record["last_page"] or 1 for record in records if record["page"] == 1), None)',
                                                                             'own_last = max((record["page"] for record in records), default=None)'),
    "a page past the run's own last page opens the end (R37 join)": (PAGES, '    if record["page"] == own_last and', '    if record["page"] >= own_last and'),
    "a block starting exactly where the reading ends left out (R37 join)": (PAGES, "        if start <= reading < end:", "        if start < reading < end:"),
    "a gap joined (R37 join)": (PAGES, "        if start <= reading < end:", "        if reading < end:"),
    "blocks not taken from the front (R37 join)": (PAGES, "    blocks.sort(key=lambda block: block[1])", "    pass"),
    "blocks that start together not taken furthest first (R37 join)": (PAGES, "    blocks.sort(key=lambda block: block[2], reverse=True)", "    pass"),
    "an out-of-order page ignored (R37 join)": (PAGES, '            if not record["in_order"]:', "            if False:"),
    "an out-of-order page in a blocked run ignored (R37 join)": (PAGES, '            if not record["in_order"]:', '            if not record["in_order"] and not manifest["blocked"]:'),
    "with joining off, a run that read every page in one go not counted (R37 join)": (PAGES, "if (BEFORE, AFTER) in _blocks(manifest, kind)}", "if False}"),
    "a run that adds nothing named a contributor (R37 join)": (PAGES, "        if start <= reading < end:  # the block joins the reading and moves its end on\n            reading = end\n",
                                                               "        if start <= reading:\n            reading = max(reading, end)\n"),
    "other kinds' pages counted (R37 join)": (PAGES, ' if record["kind"] == kind]', "]"),
    "unread counts a page read in part as read (R37 join)": (PAGES, 'read = {record["page"] for record in records if record["taken_through"] == record["last"]}', "read = touched"),
    # pages: where a Shufersal run starts each kind, from the day's earlier manifests
    "an out-of-order page ignored for the start (q21 resume)": (PAGES, "if _out_of_order(manifests, kind) is not None:", "if False:"),
    "a blocked run resumed from (q21 resume)": (PAGES, "    earlier = _counted(manifests, kind)", '    earlier = [manifest for manifest in manifests if kind in manifest["kinds"]]'),
    "another kind's run counted (q21 resume)": (PAGES, 'if kind in manifest["kinds"] and not manifest["blocked"]]', 'if not manifest["blocked"]]'),
    "resume from the first page read, not the furthest (q21 resume)": (PAGES, '    furthest = max(taken, key=lambda record: (record["taken_through"], record["page"]))', "    furthest = taken[0]"),
    "the smaller page taken when two records hold the furthest name (q21 resume)": (PAGES, 'key=lambda record: (record["taken_through"], record["page"]))',
                                                                                     'key=lambda record: record["taken_through"])'),
    "a fresh pass when not read in full (q21 resume)": (PAGES, "    if read_in_full(manifests, kind) is not None:", "    if True:"),
    "a resume when read in full (q21 resume)": (PAGES, "    if read_in_full(manifests, kind) is not None:", "    if False:"),
    "a resume at page 1 kept as a resume (q21 resume)": (PAGES, '    if furthest["page"] == 1:', "    if False:"),
    "a resume at page 1 drops its detours (q21 resume)": (PAGES, "        return Start(detours=detours)  # a resume at page 1 is a fresh pass", "        return Start()"),
    "resume at the end of the joined reading (q21 resume)": (PAGES, '    furthest = max(taken, key=lambda record: (record["taken_through"], record["page"]))',
                                                             '    furthest = next((record for record in taken if record["taken_through"] != record["last"]), taken[-1])'),
    "no detours (q21 resume)": (PAGES, "    detours = tuple(sorted(set(found)))", "    detours = ()"),
    "detours not sorted (q21 resume)": (PAGES, "tuple(sorted(set(found)))", "tuple(dict.fromkeys(found))"),
    "a detour read twice (q21 resume)": (PAGES, "tuple(sorted(set(found)))", "tuple(sorted(found))"),
    "a detour for page 1 (q21 resume)": (PAGES, " if page != 1]", "]"),
    "a detour for the resume page (q21 resume)": (PAGES, 'if page < furthest["page"])', 'if page <= furthest["page"])'),
    "a stored file given a detour (q21 resume)": (PAGES, ' for listed in manifest["listed"] if listed not in stored]', ' for listed in manifest["listed"]]'),
    "a stored name located with its .gz (q21 resume)": (PAGES, '    failed = [listed.removesuffix(".gz") for listed', "    failed = [listed for listed"),
    # pages: an update kind's poll runs cut into passes, and a poll's start from the open pass (q23, ruling R39)
    "passes in run-id order (q23 passes)": (PAGES, '    runs.sort(key=lambda manifest: datetime.fromisoformat(manifest["listing_read_at"]))', "    pass"),
    "a pass read in full not cut (q23 passes)": (PAGES, "        if read_by is not None or out_of_order:", "        if out_of_order:"),
    "the run after a complete reading joins the completed pass (q23 passes)": (PAGES, "        read_by = read_in_full(current, kind)",
                                                                               "        read_by = read_in_full(current[:-1], kind)"),
    "a page out of order does not end its pass (q23 passes)": (PAGES, "        if read_by is not None or out_of_order:", "        if read_by is not None:"),
    "the day's poll runs given to the start, not the open pass (q23 passes)": (PAGES, "        return start_for(cut[-1].runs, kind, stored)",
                                                                               "        return start_for([run for one in cut for run in one.runs], kind, stored)"),
    "an open pass not resumed (q23 passes)": (PAGES, "    if cut and cut[-1].open:", "    if False:"),
    "a fresh pass after a full reading takes detours (q23 passes)": (PAGES, "    if cut and cut[-1].open:", "    if cut:"),
    "blocked runs kept in the passes (q23 passes)": (PAGES, '            and not manifest["blocked"] and manifest["listing_read_at"] is not None]',
                                                     '            and manifest["listing_read_at"] is not None]'),
    "runs of every mode in the passes (q23 passes)": (PAGES, 'if manifest["mode"] == "poll" and kind in manifest["kinds"]', 'if kind in manifest["kinds"]'),
    "runs of another kind in the passes (q23 passes)": (PAGES, 'if manifest["mode"] == "poll" and kind in manifest["kinds"]', 'if manifest["mode"] == "poll"'),
    "a run that never read the listing kept in the passes (q23 passes)": (PAGES, ' and manifest["listing_read_at"] is not None]', "]"),
    "a pass ended by a page out of order counted open (q23 passes)": (PAGES, "        return self.read_by is None and not self.out_of_order",
                                                                      "        return self.read_by is None"),
    "a pass read in full counted open (q23 passes)": (PAGES, "        return self.read_by is None and not self.out_of_order", "        return not self.out_of_order"),
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
    "the check given no chain's kinds": (HANDLER, ", kinds={slug: c.kinds for slug, c in CHAINS.items()},", ","),
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
    "alert topic and ping URL not required": (HANDLER, 'REQUIRED = ("BUCKET", "USER_AGENT", "ALERT_TOPIC_ARN", "HEALTHCHECK_URL", "POLL_SCHEDULE_STATE")',
                                              'REQUIRED = ("BUCKET", "USER_AGENT", "POLL_SCHEDULE_STATE")'),
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
    # handler: the poll mode, the poll switch and a poll's stopped email (q23)
    "poll not a collecting mode (q23 handler)": (HANDLER, 'COLLECTING = ("main", "retry", "poll")', 'COLLECTING = ("main", "retry")'),
    "a poll without kinds takes the chain's (q23 handler)": (HANDLER, '        raise ValueError(f"a poll event names its kinds (event {event!r})")\n',
                                                             '        event = event | {"kinds": chain.polled}\n'),
    "the poll switch not required (q23 handler)": (HANDLER, '"HEALTHCHECK_URL", "POLL_SCHEDULE_STATE")', '"HEALTHCHECK_URL")'),
    "the switch read as on for any value (q23 handler)": (HANDLER, 'polls_on=polls == "ENABLED")', "polls_on=True)"),
    "a poll switch that is neither ENABLED nor DISABLED accepted (q23 handler)": (
        HANDLER, "        if polls not in POLL_STATES:\n            raise ValueError(f\"POLL_SCHEDULE_STATE must be {' or '.join(POLL_STATES)}, not {polls!r}\")\n", ""),
    "the update day judged with the switch off (q23 handler)": (HANDLER, 'if cfg.polls_on or event.get("update_day") is True else None', "if True else None"),
    "a manual check's update_day ignored (q23 handler)": (HANDLER, 'if cfg.polls_on or event.get("update_day") is True else None', "if cfg.polls_on else None"),
    "an update_day that is not true taken as asked (q23 handler)": (HANDLER, 'event.get("update_day") is True else None', 'event.get("update_day") else None'),
    "a chain that does not poll judged (q23 handler)": (HANDLER, "for slug, c in CHAINS.items() if c.polled}", "for slug, c in CHAINS.items()}"),
    "the update day judged over the morning's kinds (q23 handler)": (HANDLER, "{slug: c.polled for slug, c in CHAINS.items() if c.polled}",
                                                                     "{slug: c.kinds for slug, c in CHAINS.items() if c.polled}"),
    "a poll's email sent for a latch cleared or alerted since (q23 handler)": (HANDLER, '    if not state.get("stopped") or state.get("alerted"):\n        return\n', ""),
    "the poll's stopped email not sent (q23 handler)": (HANDLER, "    deps.publish(subject, body)\n    mark_alerted(deps.store, [alert])", "    mark_alerted(deps.store, [alert])"),
    "the chain marked alerted before the email (q23 handler)": (HANDLER, "    deps.publish(subject, body)\n    mark_alerted(deps.store, [alert])",
                                                                "    mark_alerted(deps.store, [alert])\n    deps.publish(subject, body)"),
    "the poll's chain never marked alerted (q23 handler)": (HANDLER, "mark_alerted(deps.store, [alert])  # only now", "pass  # only now"),
    "the poll's stopped email not logged before it is sent (q23 handler)": (HANDLER, '    log.warning("%s\\n%s", subject, body)  # logged first: the email can still fail',
                                                                            "    pass  # logged first: the email can still fail"),
    "every collecting run that stops a chain emails (q23 handler)": (HANDLER, '    if mode == "poll" and result.blocked and result.blocked != STOPPED_EARLIER:',
                                                                     "    if result.blocked and result.blocked != STOPPED_EARLIER:"),
    "a poll of a chain stopped earlier emails (q23 handler)": (HANDLER, "result.blocked and result.blocked != STOPPED_EARLIER:", "result.blocked:"),
    # template: the three the plan names
    "schedule enabled by default": (TEMPLATE, "  ScheduleState:\n    Type: String\n    Default: DISABLED\n", "  ScheduleState:\n    Type: String\n    Default: ENABLED\n"),
    "delete allowed": (TEMPLATE, "                - s3:PutObjectRetention\n              Resource:\n", "                - s3:PutObjectRetention\n                - s3:DeleteObject\n              Resource:\n"),
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
    "function on x86": (TEMPLATE, "Architectures: [arm64]\n      MemorySize: 512", "Architectures: [x86_64]\n      MemorySize: 512"),
    "function on an older Python": (TEMPLATE, "Handler: collector.handler.handler\n      Runtime: python3.13", "Handler: collector.handler.handler\n      Runtime: python3.12"),
    "function memory halved": (TEMPLATE, "MemorySize: 512", "MemorySize: 256"),
    "function timeout cut to five minutes": (TEMPLATE, "not attempted.\n      Timeout: 900\n", "not attempted.\n      Timeout: 300\n"),
    "Lambda retries a failed run": (TEMPLATE, "is the real retry.\n      EventInvokeConfig:\n        MaximumRetryAttempts: 0", "is the real retry.\n      EventInvokeConfig:\n        MaximumRetryAttempts: 2"),
    "handler pointed elsewhere": (TEMPLATE, "Handler: collector.handler.handler", "Handler: collector.handler.run"),
    "code from the repo root": (TEMPLATE, "CodeUri: src/\n      Handler: collector.handler.handler", "CodeUri: ./\n      Handler: collector.handler.handler"),
    "alert topic not given to the function (R5)": (TEMPLATE, "          ALERT_TOPIC_ARN: !Ref AlertTopic\n", ""),
    "retention not ten years (R5)": (TEMPLATE, 'HEALTHCHECK_URL: !Ref HealthcheckUrl\n          RETENTION_DAYS: "3650"', 'HEALTHCHECK_URL: !Ref HealthcheckUrl\n          RETENTION_DAYS: "365"'),
    "logs to Lambda's default group": (TEMPLATE, "      LoggingConfig:\n        LogGroup: !Ref CollectorLogs\n", ""),
    "logs kept forever": (TEMPLATE, '/collector"\n      RetentionInDays: 30\n', '/collector"\n'),
    "function name not in the outputs": (TEMPLATE, "  CollectorFunctionName:\n    Value: !Ref CollectorFunction\n", ""),
    # template: the role
    "governance bypass allowed": (TEMPLATE, "                - s3:PutObjectRetention\n              Resource:\n", "                - s3:PutObjectRetention\n                - s3:BypassGovernanceRetention\n              Resource:\n"),
    "bucket settings writable": (TEMPLATE, "                - s3:PutObjectRetention\n              Resource:\n", "                - s3:PutObjectRetention\n                - s3:PutBucketObjectLockConfiguration\n              Resource:\n"),
    "S3 full access added": (TEMPLATE, "      Policies:\n        - Statement:\n            # Raw files,", "      Policies:\n        - AmazonS3FullAccess\n        - Statement:\n            # Raw files,"),
    "every S3 action on state": (TEMPLATE, "              Action:\n                - s3:GetObject\n                - s3:PutObject\n", '              Action: "s3:*"\n'),
    "locked writes anywhere in the bucket": (TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/raw/*"\n                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n                - !Sub "${ArchiveBucket.Arn}/checks/*"\n            # The check reads',
                                             '                - !Sub "${ArchiveBucket.Arn}/*"\n            # The check reads'),
    "check records not writable": (TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/checks/*"\n            # The check reads', "            # The check reads"),
    "manifests not readable by the check": (TEMPLATE, '- Sid: ReadStored\n              Effect: Allow\n              Action: s3:GetObject\n              Resource:\n                - !Sub "${ArchiveBucket.Arn}/raw/*"\n                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n',
                                            '- Sid: ReadStored\n              Effect: Allow\n              Action: s3:GetObject\n              Resource:\n                - !Sub "${ArchiveBucket.Arn}/raw/*"\n'),
    "state not readable": (TEMPLATE, "                - s3:GetObject\n                - s3:PutObject\n              Resource: !Sub", "                - s3:PutObject\n              Resource: !Sub"),
    "no ListBucket": (TEMPLATE, "- Sid: ListBucketSoMissingKeyIs404\n              Effect: Allow\n              Action: s3:ListBucket\n", "- Sid: ListBucketSoMissingKeyIs404\n              Effect: Allow\n              Action: s3:ListAllMyBuckets\n"),
    "a condition on the bucket list": (TEMPLATE, "              Resource: !GetAtt ArchiveBucket.Arn\n            - Sid: EmailAlerts\n", '              Resource: !GetAtt ArchiveBucket.Arn\n              Condition:\n                StringLike:\n                  s3:prefix: ["raw/*"]\n            - Sid: EmailAlerts\n'),
    "alerts publishable to any topic": (TEMPLATE, "              Resource: !Ref AlertTopic\n", '              Resource: "*"\n'),
    # template: the parameters and the alert email
    "User-Agent pattern takes http": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", r"AllowedPattern: '.*\+https?://.*@.*'"),
    "User-Agent pattern without the email": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", r"AllowedPattern: '.*\+https://.*'"),
    "User-Agent pattern dropped": (TEMPLATE, r"AllowedPattern: '.*\+https://.*@.*'", "AllowedPattern: '.*'"),
    "health-check URL of any shape": (TEMPLATE, "the morning check pings it.\n    AllowedPattern: 'https://hc-ping\\.com/[-A-Za-z0-9_/]+'", "the morning check pings it.\n    AllowedPattern: '.*'"),
    "health-check URL shown in the stack": (TEMPLATE, "  HealthcheckUrl:\n    Type: String\n    NoEcho: true\n", "  HealthcheckUrl:\n    Type: String\n    NoEcho: false\n"),
    "alert email given a default": (TEMPLATE, "  AlertEmail:\n    Type: String\n", "  AlertEmail:\n    Type: String\n    Default: you@example.org\n"),
    "schedule switch takes any value": (TEMPLATE, "    AllowedValues: [ENABLED, DISABLED]\n    Description: Start DISABLED", "    Description: Start DISABLED"),
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
    "two NCR chains 3 minutes apart (R30)": (ONE_HOST_AT_A_TIME, '"cron(18 8 * * ? *)"', '"cron(36 6 * * ? *)"'),
    "a retry run not three hours after its main run": (RETRY_THREE_HOURS_ON, '"cron(3 10 * * ? *)"', '"cron(5 10 * * ? *)"'),
    "check at the design's 10:00": (CHECK_LAST, '"cron(48 11 * * ? *)"', '"cron(0 10 * * ? *)"'),
    "check before the last retry run can finish": (CHECK_LAST, '"cron(48 11 * * ? *)"', '"cron(25 11 * * ? *)"'),
    "check with no margin after the last retry run": (CHECK_LAST, '"cron(48 11 * * ? *)"', '"cron(33 11 * * ? *)"'),
    "Shufersal's retries short of a kind (R4)": (ALL_KINDS, "Input: '{\"mode\": \"retry\", \"chain\": \"shufersal\", \"kinds\": [\"PromoFull\"]}'", "Input: '{\"mode\": \"retry\", \"chain\": \"shufersal\", \"kinds\": [\"PriceFull\"]}'"),
    "Shufersal's store-list run also fetching full prices": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'", "Input: '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\", \"PriceFull\"]}'"),
    "another chain narrowed to some kinds": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\", \"kinds\": [\"PriceFull\"]}'"),
    "a chain without a retry run": (ALL_KINDS, "Input: '{\"mode\": \"retry\", \"chain\": \"yochananof\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"yochananof\"}'"),
    "a chain with no main run": (ALL_KINDS, "Input: '{\"mode\": \"main\", \"chain\": \"yochananof\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"osherad\"}'"),
    "a chain the code does not know": (HANDLER_EVENTS, "Input: '{\"mode\": \"main\", \"chain\": \"carrefour\"}'", "Input: '{\"mode\": \"main\", \"chain\": \"victory\"}'"),
    "the check given a chain": (HANDLER_EVENTS, "Input: '{\"mode\": \"check\"}'", "Input: '{\"mode\": \"check\", \"chain\": \"shufersal\"}'"),
    # template: the poll switch (q23)
    "the poll switch on by default (q23 template)": (TEMPLATE, "  PollScheduleState:\n    Type: String\n    Default: DISABLED\n",
                                                     "  PollScheduleState:\n    Type: String\n    Default: ENABLED\n"),
    "the poll switch takes any value (q23 template)": (TEMPLATE, "    AllowedValues: [ENABLED, DISABLED]\n    Description: The update-file polls through the day",
                                                       "    Description: The update-file polls through the day"),
    "the function not told the poll switch (q23 template)": (TEMPLATE, "          POLL_SCHEDULE_STATE: !Ref PollScheduleState\n", ""),
    # template: the polls (q23). Each Input repeats 6 or 7 times, so a text to break that quotes one names its cron line.
    "a poll moved into the extractions' window (q23 template)": (NO_POLL_DURING_EXTRACTION, '"cron(20 12 * * ? *)"', '"cron(10 12 * * ? *)"'),
    "a poll still running when the extractions start (q23 template)": (NO_POLL_DURING_EXTRACTION, '"cron(20 12 * * ? *)"', '"cron(50 11 * * ? *)"'),
    "a poll on the morning's switch (q23 template)": (
        POLL_SWITCH, '"cron(20 14 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}\'\n            State: !Ref PollScheduleState',
        '"cron(20 14 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "ramilevy", "kinds": ["Price", "Promo"]}\'\n            State: !Ref ScheduleState'),
    "a morning run on the poll switch (q23 template)": (POLL_SWITCH, "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'\n            State: !Ref ScheduleState",
                                                        "Input: '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'\n            State: !Ref PollScheduleState"),
    "a poll of a full kind (q23 template)": (
        HANDLER_EVENTS, '"cron(5 13 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "carrefour", "kinds": ["Price", "Promo"]}\'',
        '"cron(5 13 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "carrefour", "kinds": ["PriceFull", "Promo"]}\''),
    "a poll without its kinds (q23 template)": (
        HANDLER_EVENTS, '"cron(50 14 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "osherad", "kinds": ["Price", "Promo"]}\'',
        '"cron(50 14 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "poll", "chain": "osherad"}\''),
    "two NCR polls 10 minutes apart (q23 template)": (ONE_HOST_AT_A_TIME, '"cron(35 12 * * ? *)"', '"cron(30 12 * * ? *)"'),
    "a chain's polls 10 minutes apart (q23 template)": (ONE_RUN_AT_A_TIME, '"cron(5 15 * * ? *)"', '"cron(15 13 * * ? *)"'),
    "two polls in one minute (q23 template)": (ONE_MINUTE_EACH, '"cron(5 17 * * ? *)"', '"cron(50 16 * * ? *)"'),
    "Shufersal polled before its schedules (q23 template)": (POLLED_CHAINS, '\n          kinds=("Stores", "PriceFull", "PromoFull")),',
                                                             '\n          kinds=("Stores", "PriceFull", "PromoFull"), polled=("Price", "Promo")),'),
    # the operations doc
    "a manual collecting run started synchronously": (OPERATIONS, "--invocation-type Event --payload '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'", "--payload '{\"mode\": \"main\", \"chain\": \"ramilevy\"}'"),
    "an aws command in the doc without the project profile": (OPERATIONS, "aws logs tail /il-grocery-prices/collector --follow --since 10m --profile flights-sam --region il-central-1", "aws logs tail /il-grocery-prices/collector --follow --since 10m --region il-central-1"),
    "sam deploy in the doc without the project profile": (OPERATIONS, "sam deploy --profile flights-sam --region il-central-1 --stack-name", "sam deploy --region il-central-1 --stack-name"),
    "a chain's manual run missing from the doc": (OPERATIONS, "--payload '{\"mode\": \"main\", \"chain\": \"yochananof\"}'", "--payload '{\"mode\": \"main\", \"chain\": \"osherad\"}'"),
    "a Shufersal manual run missing from the doc": (OPERATIONS, "--payload '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"Stores\"]}'", "--payload '{\"mode\": \"main\", \"chain\": \"shufersal\", \"kinds\": [\"PriceFull\"]}'"),
    "an unknown chain unblocked in the doc": (OPERATIONS, "--payload '{\"mode\": \"unblock\", \"chain\": \"ramilevy\"}'", "--payload '{\"mode\": \"unblock\", \"chain\": \"victory\"}'"),
    "a real address in the doc": (OPERATIONS, "'AlertEmail=<email>'", "'AlertEmail=owner@mail.example.net'"),
    "the doc's timetable off the schedules": (OPERATIONS, "| 06:39 | Carrefour", "| 06:40 | Carrefour"),
    "the basket's timetable off its schedules": (OPERATIONS, "| 12:33 | The basket run", "| 12:30 | The basket run"),
    "an extraction's manual run missing from the doc": (OPERATIONS, "--payload '{\"mode\": \"extract\", \"chain\": \"yochananof\", \"day\": \"2026-11-02\"}'", "--payload '{\"mode\": \"extract\", \"chain\": \"osherad\", \"day\": \"2026-11-02\"}'"),
    "a manual extraction started synchronously": (OPERATIONS, "--invocation-type Event --payload '{\"mode\": \"extract\", \"chain\": \"carrefour\"", "--payload '{\"mode\": \"extract\", \"chain\": \"carrefour\""),
    "a manual run for a day that is no date": (OPERATIONS, "\"chain\": \"shufersal\", \"day\": \"2026-11-02\"", "\"chain\": \"shufersal\", \"day\": \"2026-11-31\""),
    "a manual basket run collected by another time": (OPERATIONS, "\"collected_by\": \"12:03\"}' --cli-read-timeout", "\"collected_by\": \"12:30\"}' --cli-read-timeout"),
    "a manual basket run's day misspelled": (OPERATIONS, "{\"mode\": \"basket\", \"day\":", "{\"mode\": \"basket\", \"dya\":"),
    "a poll's row at another time in the doc (q23 doc)": (OPERATIONS, "| 12:20 | Rami Levy, update files", "| 12:25 | Rami Levy, update files"),
    "a chain's manual poll missing from the doc (q23 doc)": (OPERATIONS, "--payload '{\"mode\": \"poll\", \"chain\": \"yochananof\", \"kinds\": [\"Price\", \"Promo\"]}'",
                                                             "--payload '{\"mode\": \"poll\", \"chain\": \"osherad\", \"kinds\": [\"Price\", \"Promo\"]}'"),
    "a manual poll started synchronously (q23 doc)": (OPERATIONS, "--invocation-type Event --payload '{\"mode\": \"poll\", \"chain\": \"carrefour\"",
                                                      "--payload '{\"mode\": \"poll\", \"chain\": \"carrefour\""),
    "the manual update-day check's field misspelled in the doc (q23 doc)": (OPERATIONS, "'{\"mode\": \"check\", \"update_day\": true}'",
                                                                            "'{\"mode\": \"check\", \"update_dya\": true}'"),
    "the manual update-day check asks with a string in the doc (q23 doc)": (OPERATIONS, "'{\"mode\": \"check\", \"update_day\": true}'",
                                                                            "'{\"mode\": \"check\", \"update_day\": \"true\"}'"),
    # site template: the bucket
    "public access unblocked": (SITE_TEMPLATE, "      PublicAccessBlockConfiguration:\n        BlockPublicAcls: true\n        BlockPublicPolicy: true\n        IgnorePublicAcls: true\n        RestrictPublicBuckets: true\n", ""),
    "site bucket public policies allowed": (SITE_TEMPLATE, "        RestrictPublicBuckets: true", "        RestrictPublicBuckets: false"),
    "site bucket with ACLs": (SITE_TEMPLATE, "ObjectOwnership: BucketOwnerEnforced", "ObjectOwnership: ObjectWriter"),
    "site bucket unencrypted": (SITE_TEMPLATE, "      BucketEncryption:\n        ServerSideEncryptionConfiguration:\n          - ServerSideEncryptionByDefault:\n              SSEAlgorithm: AES256\n", ""),
    # site template: the policy, the origin and the viewers
    "site readable by anyone": (SITE_TEMPLATE, "            Principal:\n              Service: cloudfront.amazonaws.com", '            Principal: "*"'),
    "site policy without the distribution condition": (SITE_TEMPLATE, '            Condition:\n              StringEquals:\n                AWS:SourceArn: !Sub "arn:aws:cloudfront::${AWS::AccountId}:distribution/${SiteDistribution}"\n', ""),
    "signing not always": (SITE_TEMPLATE, "SigningBehavior: always", "SigningBehavior: no-override"),
    "site origin without the access control": (SITE_TEMPLATE, "            OriginAccessControlId: !GetAtt SiteOriginAccessControl.Id\n", ""),
    "global bucket name as origin": (SITE_TEMPLATE, "DomainName: !GetAtt SiteBucket.RegionalDomainName", "DomainName: !GetAtt SiteBucket.DomainName"),
    "site served over http": (SITE_TEMPLATE, "ViewerProtocolPolicy: redirect-to-https", "ViewerProtocolPolicy: allow-all"),
    "no default root object": (SITE_TEMPLATE, "        DefaultRootObject: index.html\n", ""),
    "site bucket name not in the outputs": (SITE_TEMPLATE, "  SiteBucketName:\n    Value: !Ref SiteBucket\n", ""),
    # basket: barcodes
    "barcode check digit ignored": (BARCODE, "(3 if place % 2 == 0 else 1)", "(1 if place % 2 == 0 else 1)"),
    "barcode leading zeros kept": (BARCODE, 'significant = digits.lstrip("0")', "significant = digits"),
    "barcode non-ASCII digits accepted": (BARCODE, "if not _DIGITS.fullmatch(digits):", "if not digits.isdigit():"),
    "barcode seven significant digits accepted": (BARCODE, "8 <= len(digits) <= 14", "7 <= len(digits) <= 14"),
    "barcode fifteen significant digits accepted": (BARCODE, "8 <= len(digits) <= 14", "8 <= len(digits) <= 15"),
    # basket: price files
    "pricefile ItemNm ignored": (PRICEFILE, 'NAME_TAGS = ("ItemName", "ItemNm")', 'NAME_TAGS = ("ItemName",)'),
    "pricefile PriceUpdateDate ignored": (PRICEFILE, 'UPDATED_TAGS = ("PriceUpdateTime", "PriceUpdateDate")', 'UPDATED_TAGS = ("PriceUpdateTime",)'),
    "pricefile second ZIP member skipped": (PRICEFILE, "return [archive.read(member) for member in members]", "return [archive.read(member) for member in members[:1]]"),
    "pricefile text not stripped": (PRICEFILE, 'return (element.text or "").strip()', 'return element.text or ""'),
    "pricefile ZIP folder read as a file": (PRICEFILE, "members = [member for member in archive.infolist() if not member.is_dir()]", "members = archive.infolist()"),
    "pricefile well-formed HTML read as a file of no items": (PRICEFILE, "    if not body.startswith(XML_STARTS):", "    if False:"),
    # basket: extract
    "extract older file wins": (EXTRACT, "latest = max(named)", "latest = min(named)"),
    "extract first duplicate wins": (EXTRACT, "        latest[row.code] = row", "        latest.setdefault(row.code, row)"),
    "extract conflict not counted": (EXTRACT, "                conflicting += 1", "                pass"),
    "extract unreadable price kept as zero": (EXTRACT, "    except InvalidOperation:\n        return None", "    except InvalidOperation:\n        return Decimal(0)"),
    "extract three-decimal price accepted": (EXTRACT, "-value.as_tuple().exponent > 2", "-value.as_tuple().exponent > 3"),
    "extract empty table not written": (EXTRACT, "        with duck.connect() as con:", "        if count == 0:\n            return 0\n        with duck.connect() as con:"),
    "extract sub-chain padded": (EXTRACT, "sub_chain = None if parsed.sub_chain is None else store_key(parsed.sub_chain)", "sub_chain = parsed.sub_chain"),
    "extract conflict copy not read": (EXTRACT, "parse_file_name(published_name(path.name))", "parse_file_name(path.name)"),
    "extract another day's file read": (EXTRACT, ' or parsed.day != day:', ":"),
    "extract another kind's file read": (EXTRACT, 'parsed.kind != "PriceFull"', 'parsed.kind not in ("PriceFull", "PromoFull")'),
    "extract stores sorted as text": (EXTRACT, "key=lambda f: (int(f.store), f.store)", "key=lambda f: f.store"),
    "extract price too large for the table accepted": (EXTRACT, " or abs(value) >= PRICE_LIMIT:", ":"),
    "extract NaN price accepted": (EXTRACT, "if not value.is_finite() or -value", "if -value"),
    "extract a store of no rows counted": (EXTRACT, "stores=sum(1 for c in counts if c.rows)", "stores=len(counts)"),
    "extract None written as empty text": (EXTRACT, 'NULLABLE = ("sub_chain", "code_norm", "price")', 'NULLABLE = ("price",)'),
    "extract empty text read as NULL": (EXTRACT, "allow_quoted_nulls = false", "allow_quoted_nulls = true"),
    "extract CSV in the system temp folder": (EXTRACT, "tempfile.TemporaryDirectory(dir=out.parent)", "tempfile.TemporaryDirectory()"),
    # basket: duck
    "duck temp directory not set": (DUCK, '        con.execute("SET temp_directory = ?", [temp_directory])', "        pass"),
    "duck memory limit not set": (DUCK, '        con.execute("SET memory_limit = ?", [memory_limit])', "        pass"),
    "duck blank temp directory set": (DUCK, 'temp_directory = env.get(TEMP_DIRECTORY_VAR, "").strip()', 'temp_directory = env.get(TEMP_DIRECTORY_VAR, "")'),
    "duck temp directory made with its spaces": (DUCK, "        Path(temp_directory).mkdir(", "        Path(env[TEMP_DIRECTORY_VAR]).mkdir("),
    "duck blank memory limit set": (DUCK, "    if memory_limit.strip():", "    if True:"),
    "duck process environment ignored": (DUCK, "    env = os.environ if env is None else env", "    env = {} if env is None else env"),
    "duck temp directory not created": (DUCK, "        Path(temp_directory).mkdir(parents=True, exist_ok=True)\n", ""),
    "duck temp directory's parents not created": (DUCK, "mkdir(parents=True, exist_ok=True)", "mkdir(exist_ok=True)"),
    "duck temp directory already there refused": (DUCK, "mkdir(parents=True, exist_ok=True)", "mkdir(parents=True)"),
    "extract connects without duck": (EXTRACT_FOR_DUCK, "        with duck.connect() as con:", '        with __import__("duckdb").connect() as con:'),
    "rules connects without duck": (RULES_FOR_DUCK, "    con = duck.connect()\n", "    con = duckdb.connect()\n"),
    # basket: stores
    "stores Be included": (CHAINS_BASKET, 'frozenset({"5"})', "frozenset()"),
    "stores online store included": (CHAINS_BASKET, 'frozenset({"413"})', "frozenset()"),
    "stores Carrefour online store included": (CHAINS_BASKET, 'frozenset({"471"})', "frozenset()"),
    "stores Rami Levy 039 included": (CHAINS_BASKET, 'frozenset({"39"})', "frozenset()"),
    "stores sub-chain compared padded": (STORES, "_stores_in(child, store_key(published) if published else None)", "_stores_in(child, published or None)"),
    "stores store id kept padded": (STORES, "yield Store(store_key(store_id), sub_chain", "yield Store(store_id, sub_chain"),
    "stores StoreId spelling ignored": (STORES, 'STORE_ID_TAGS = ("StoreID", "StoreId")', 'STORE_ID_TAGS = ("StoreID",)'),
    "stores SubChainId spelling ignored": (STORES, 'SUB_CHAIN_TAGS = ("SubChainID", "SubChainId")', 'SUB_CHAIN_TAGS = ("SubChainID",)'),
    "stores store without an id kept": (STORES, "            if store_id:\n", "            if True:\n"),
    "stores fallback takes a later day": (STORES, "for listed_day in (d for d in days if d <= day):", "for listed_day in days:"),
    "stores older list of the day wins": (STORES, "(folder / max(names))", "(folder / min(names))"),
    "stores another kind read as the store list": (STORES, 'parsed.kind == "Stores"', 'parsed.kind in ("Stores", "PriceFull")'),
    "stores another day's list read": (STORES, " and parsed.day == day", ""),
    "stores conflict copy not read": (STORES, "parse_file_name(published_name(name))", "parse_file_name(name)"),
    # basket: units
    "units litre not scaled": (UNITS_BASKET, '"ליטר": ("gml", THOUSAND)', '"ליטר": ("gml", ONE)'),
    "units unknown unit read as grams": (UNITS_BASKET, "known = UNITS.get(unit.strip())", 'known = UNITS.get(unit.strip(), ("gml", ONE))'),
    "units zero quantity accepted": (UNITS_BASKET, "amount <= 0", "amount < 0"),
    "units unit and gml compared alike": (UNITS_BASKET, "    kind: str\n", '    kind: str = __import__("dataclasses").field(compare=False)\n'),
    "units unit string not trimmed": (UNITS_BASKET, "UNITS.get(unit.strip())", "UNITS.get(unit)"),
    "units non-finite quantity accepted": (UNITS_BASKET, "if not amount.is_finite() or amount", "if amount"),
    "units amount not made plain": (UNITS_BASKET, "Size(Decimal(plain(amount * factor)), kind)", "Size(amount * factor, kind)"),
    "units one unit read as a size": (UNITS_BASKET, 'if kind == "unit" and amount == 1:', "if False:"),
    # basket: basket file
    "basket file check digit not checked": (BASKET_FILE, "    if not is_gs1(code):", "    if False:"),
    "basket file duplicates allowed": (BASKET_FILE, "        if digits in first_with:", "        if False:"),
    "basket file leading zeros told apart": (BASKET_FILE, "digits = normalize(item.code)", "digits = item.code"),
    "basket file floor at 24": (BASKET_FILE, "min_items: int = 25", "min_items: int = 24"),
    "basket file ceiling at 41": (BASKET_FILE, "max_items: int = 40", "max_items: int = 41"),
    "basket file floor excluded": (BASKET_FILE, "if not min_items <= len(items) <= max_items:", "if not min_items < len(items) <= max_items:"),
    "basket file ceiling excluded": (BASKET_FILE, "if not min_items <= len(items) <= max_items:", "if not min_items <= len(items) < max_items:"),
    "basket file empty English name allowed": (BASKET_FILE, "if not name_en.strip() or not name_he.strip():", "if not name_he.strip():"),
    "basket file empty Hebrew name allowed": (BASKET_FILE, "if not name_en.strip() or not name_he.strip():", "if not name_en.strip():"),
    "basket file blank name allowed": (BASKET_FILE, "if not name_en.strip() or not name_he.strip():", "if not name_en or not name_he:"),
    "basket file unknown kind allowed": (BASKET_FILE, "    if kind not in KINDS:", "    if False:"),
    "basket file zero amount allowed": (BASKET_FILE, "or amount <= 0:", "or amount < 0:"),
    "basket file non-finite amount allowed": (BASKET_FILE, "if not amount.is_finite() or amount <= 0:", "if amount <= 0:"),
    "basket file amount not made plain": (BASKET_FILE, "Size(Decimal(plain(amount)), kind)", "Size(amount, kind)"),
    "basket file coverage not a dict accepted": (BASKET_FILE, "        if not isinstance(coverage, dict):", "        if False:"),
    "basket file items not a list accepted": (BASKET_FILE, "        if not isinstance(listed, list):", "        if False:"),
    "basket file text accepted as a field": (BASKET_FILE, "    if not isinstance(value, str):", "    if False:"),
    # basket: rules
    "rules placeholders kept": (RULES, "p.price > 0.01", "p.price >= 0.01"),
    "rules null prices kept": (RULES, "p.price IS NOT NULL AND p.price > 0.01", "(p.price IS NULL OR p.price > 0.01)"),
    "rules excluded store counted": (RULES, "if store in included.get(chain, ()) and", "if chain in present and"),
    "rules store keys sorted as text": (RULES, "sorted(stores, key=lambda store: (int(store), store))", "sorted(stores)"),
    "rules Be rows kept when the list includes the store": (RULES, "AND NOT EXISTS (SELECT 1 FROM excluded_sub_chains x WHERE x.chain = p.chain AND x.sub_chain = p.sub_chain)", "AND true"),
    "rules median takes the lower middle": (RULES, "return (ordered[middle - 1] + ordered[middle]) / 2", "return ordered[middle - 1]"),
    "rules a double-coded store weighs twice": (RULES, "GROUP BY chain, code_norm, store)", "GROUP BY chain, code_norm, store, code)"),
    "rules a double-coded store at its higher price": (RULES, "min(price) AS price", "max(price) AS price"),
    "rules coverage guard at a third": (RULES, "listing[day.slug] * 2 >= day.with_file", "listing[day.slug] * 3 >= day.with_file"),
    "rules size guard ignores a chain": (RULES, "sizes.get((day.slug, code)) for day in ranking}", "sizes.get((day.slug, code)) for day in ranking[:-1]}"),
    "rules unstated size blocks": (RULES, "if size is not None and size != item.size", "if size != item.size"),
    "rules half a chain's stores read as a third": (RULES, "with_file * 2 >= included", "with_file * 3 >= included"),
    "rules chain out of ranking still guards": (RULES, "_guard(item, ranking, prices", "_guard(item, days, prices"),
    "rules headline with two chains": (RULES, "if len(totals) >= 3:", "if len(totals) >= 2:"),
    "rules gap rounded down": (RULES, "rounding=ROUND_HALF_UP", 'rounding="ROUND_DOWN"'),
    "rules no items still totalled": (RULES, "    if items_in:", "    if True:"),
    "rules left-out chains in the days' order": (RULES, "ranking = sorted((day for day in days if day.in_ranking), key=lambda day: day.slug)", "ranking = [day for day in days if day.in_ranking]"),
    "rules chain results in the days' order": (RULES, "for slug in sorted(listed)}", "for slug in listed}"),
    # basket: record
    "record store lists leak to the public day": (RECORD, 'PRIVATE = ("stores_with_file", "files", "manifests")', 'PRIVATE = ("files", "manifests")'),
    "record comparable ignores medians": (RECORD, '"revisions", "revised")', '"revisions", "revised", "chains")'),
    "record half-up rounding dropped": (RECORD, "amount.quantize(CENT, rounding=ROUND_HALF_UP)", "amount.quantize(CENT)"),
    "record an 'exists' outcome counts as stored": (RECORD, 'if file["outcome"] == "stored"}', 'if file["outcome"] in ("stored", "exists")}'),
    "record another chain's manifests read": (RECORD, '.glob(f"{slug}-*.json")', '.glob("*.json")'),
    "record double-coded count dropped": (RECORD, "price.double_coded)", "0)"),
    "record build time left in its own zone": (RECORD, "return moment.astimezone(timezone.utc).isoformat()", "return moment.isoformat()"),
    "record naive build time accepted": (RECORD, "if moment.tzinfo is None or moment.utcoffset() is None:", "if False:"),
    "record Hebrew escaped": (RECORD, "ensure_ascii=False", "ensure_ascii=True"),
    "record keys not sorted": (RECORD, "sort_keys=True, indent=1", "sort_keys=False, indent=1"),
    "record comparable keeps collected_by": (RECORD, '"built_at", "collected_by", "revisions"', '"built_at", "revisions"'),
    "record placeholder count dropped": (RECORD, '"placeholders": placeholders}', '"placeholders": 0}'),
    # basket: candidates
    "candidates a four-chain code passes": (CANDIDATES, "listed.keys() == with_file.keys()", "len(listed) >= len(with_file) - 1"),
    "candidates coverage share at half": (CANDIDATES, 'min_share: Decimal = Decimal("0.8")', 'min_share: Decimal = Decimal("0.5")'),
    "candidates two stating chains enough": (CANDIDATES, "min_stating: int = 3", "min_stating: int = 2"),
    "candidates non-GS1 code passes": (CANDIDATES, '" WHERE gs1 AND chain IN', '" WHERE true AND chain IN'),
    "candidates exactly the share refused": (CANDIDATES, "listed[chain] >= min_share * with_file[chain]", "listed[chain] > min_share * with_file[chain]"),
    "candidates disagreeing sizes pass": (CANDIDATES, "len(set(stated)) != 1", "len(set(stated)) < 1"),
    "candidates name tie to the last in order": (CANDIDATES, "min(names, key=lambda name: (-names[name], name))", "max(names, key=lambda name: (names[name], name))"),
    "candidates name first in order, not most common": (CANDIDATES, "min(names, key=lambda name: (-names[name], name))", "min(names)"),
    "candidates coverage rounded half up in the table": (CANDIDATES, "rounding=ROUND_DOWN", 'rounding="ROUND_HALF_UP"'),
    # basket: words and pages
    "page credit line dropped from the method page": (PAGE, 'f"{words.METHOD_TITLE} · {words.TITLE}", parts, _credit(public))', 'f"{words.METHOD_TITLE} · {words.TITLE}", parts, "")'),
    "page noindex dropped": (PAGE, '<meta name="robots" content="noindex">\n', ""),
    "page lowest marked as highest": (PAGE, "lowest = min(prices.values())", "lowest = max(prices.values())"),
    "page a never phrase in the template": (PAGE, 'heading = "Listed totals, lowest first"', 'heading = "Listed totals, cheapest chain first"'),
    "page revised line always shown": (PAGE, '    if public["revised"]:\n', "    if True:\n"),
    "page day file written when not asked": (PAGE, "    if write_day:\n", "    if True:\n"),
    "page bars for a chain out of ranking": (PAGE, '        if not chain["in_ranking"]:\n            few =', "        if False:\n            few ="),
    "page lowest taken over a chain out of ranking": (PAGE, 'if chain["in_ranking"] and code in chain["items"]}', 'if code in chain["items"]}'),
    "page lowest marked in a row left out": (PAGE, 'if not compare or code not in public["items_in"]:', "if not compare:"),
    "page bars scaled to the lowest total": (PAGE, "highest = max(Decimal(chain", "highest = min(Decimal(chain"),
    "page item count from the basket on a day that compares": (PAGE, 'count = len(public["items_in"]) if compare else len(basket.items)', "count = len(basket.items)"),
    "page Hebrew name not right to left": (PAGE, "<br>{_he(item.name_he)}<small>", "<br>{_text(item.name_he)}<small>"),
    "page Hebrew in a sentence not right to left": (PAGE, "_he(run.group())]", "_text(run.group())]"),
    "page headline totals not rounded": (WORDS, "₪{money(headline.lowest_total)}.", "₪{headline.lowest_total}."),
    "page no-items reason never given": (WORDS, "return NO_ITEMS if nothing_counted else NO_CHAINS, items", "return NO_CHAINS, items"),
    "page first totals sorted as text": (WORDS, "sorted((Decimal(total), slug, total)", "sorted((total, slug, total)"),
    "page Be sub-chain not named": (WORDS, 'SUB_CHAIN_NAMES = {"shufersal": {"5": "Be"}}', "SUB_CHAIN_NAMES = {}"),
    "page store id unescaped": (PAGE, "<li>store {_text(store.id)} {_he(store.name)}</li>", "<li>store {store.id} {_he(store.name)}</li>"),
    "page one everyday item read as plural": (WORDS, "{'item' if item_count == 1 else 'items'}", "items"),
    "page one product read as plural": (WORDS, "{'product' if count == 1 else 'products'}", "products"),
    "page tile's lowest total the highest": (PAGE, 'f"₪{money(headline.lowest_total)}",', 'f"₪{money(headline.highest_total)}",'),
    "page tile's lowest chain the highest": (PAGE, "words.CHAIN_NAMES[headline.lowest]),", "words.CHAIN_NAMES[headline.highest]),"),
    "page tile's total not rounded": (PAGE, 'f"₪{money(headline.lowest_total)}",', 'f"₪{headline.lowest_total}",'),
    "page tiles read out beside the headline lines": (PAGE, '<dl class="tiles" aria-hidden="true">', '<dl class="tiles">'),
    "page tiles on a day without a comparison": (PAGE, '    parts = [_tiles(_headline(public["headline"]))] if compare else []\n', '    parts = [_tiles(_headline(public["headline"]))] if compare else ["<dl class=\\"tiles\\"></dl>"]\n'),
    "page lowest bar marked at rank 2": (PAGE, 'compare and chain["rank"] == 1 else None', 'compare and chain["rank"] == 2 else None'),
    "page lowest bar marked without a comparison": (PAGE, '"lowest" if compare and chain["rank"] == 1', '"lowest" if chain["rank"] == 1'),
    "page bars offset from zero": (PAGE, '<rect class="fill" width="{width:.2f}%"', '<rect class="fill" x="10%" width="{width:.2f}%"'),
    "page date line not in the header": (PAGE, '<p class="dateline">{_text(line)}</p>', '<p class="dateline"></p>'),
    "page header after the main part": (PAGE, "<body>\n{band}\n<main>\n{body}\n</main>\n", "<body>\n<main>\n{body}\n</main>\n{band}\n"),
    "page table box named by no heading": (PAGE, '<h2 id="prices">', "<h2>"),
    "page no dark set": (PAGE, "@media (prefers-color-scheme: dark) {", "@media (prefers-color-scheme: light) {"),
    "page body without a background": (PAGE, "body { margin: 0; background: var(--bg);", "body { margin: 0;"),
    "page a font fetched from outside": (PAGE, "*, *::before, *::after { box-sizing: border-box; }", '@import url("https://fonts.example/a.css");\n*, *::before, *::after { box-sizing: border-box; }'),
    # basket: check
    "basket check entities not unescaped": (CHECK_BASKET, "html.unescape(text)", "text"),
    "basket check tags not stripped": (CHECK_BASKET, "flatten(strip_tags(raw))", "flatten(raw)"),
    "basket check never phrases not sought": (CHECK_BASKET, "for phrase in NEVER if", "for phrase in () if"),
    "basket check never phrase sought only with tags stripped": (CHECK_BASKET, "if _says(phrase, written, read)]", "if _says(phrase, read)]"),
    "basket check never phrase sought only as written": (CHECK_BASKET, "if _says(phrase, written, read)]", "if _says(phrase, written)]"),
    "basket check credit line not required": (CHECK_BASKET, 'NOTICES = {"the credit line": CREDIT_START, ', "NOTICES = {"),
    "basket check shopping advice not required": (CHECK_BASKET, """CREDIT_START, f'"{NOT_ADVICE}"': NOT_ADVICE}""", "CREDIT_START}"),
    "basket check noindex not required": (CHECK_BASKET, "        if not _says(NOINDEX, written):\n", "        if False:\n"),
    "basket check script allowed": (CHECK_BASKET, "        if SCRIPT in written:\n", "        if False:\n"),
    "basket check 'we' allowed": (CHECK_BASKET, "(?:we|our|us)", "(?:our|us)"),
    "basket check words matched inside words": (CHECK_BASKET, r'r"\b(?:we|our|us)\b"', r'r"(?:we|our|us)"'),
    "basket check always phrases not required": (CHECK_BASKET, "for phrase in ALWAYS if", "for phrase in () if"),
    "basket check always phrase counted in an attribute": (CHECK_BASKET, "for phrase in ALWAYS if not _says(phrase, read)]", "for phrase in ALWAYS if not _says(phrase, written, read)]"),
    "basket check revised on allowed on an unrevised day": (CHECK_BASKET, "    elif _says(REVISED, written, read):", "    elif False:"),
    "basket check oldest day file read": (CHECK_BASKET, "newest = days[-1]", "newest = days[0]"),
    "basket check missing index allowed": (CHECK_BASKET, "    if not (site_dir / INDEX).is_file():\n", "    if False:\n"),
    "basket check marker not required": (CHECK_BASKET, "    if not (site_dir / MARKER).is_file():\n", "    if False:\n"),
    "basket check no pages passes": (CHECK_BASKET, "    if not pages:\n        raise NoPages", "    if False:\n        raise NoPages"),
    "basket check exit 0 on a hit": (CHECK_BASKET, "return 1 if problems else 0", "return 0"),
    # basket: build
    "basket build unchanged day rewritten": (BUILD, "write_day=not unchanged)", "write_day=True)"),
    "basket build revision without a reason accepted": (BUILD, "    if reason is None:\n        raise RevisionNeeded", "    if False:\n        raise RevisionNeeded"),
    "basket build blank reason accepted": (BUILD, r'if not reason or "\n" in reason or "\r" in reason:', r'if "\n" in reason or "\r" in reason:'),
    "basket build multi-line reason accepted": (BUILD, r'if not reason or "\n" in reason or "\r" in reason:', "if not reason:"),
    "basket build reason stored unstripped": (BUILD, '"reason": reason}', '"reason": revise}'),
    "basket build first totals dropped on revision": (BUILD, 'previous["revisions"] + [earlier]', "[earlier]"),
    "basket build record overwritten": (BUILD, 'open(path, "x", encoding="utf-8")', 'open(path, "w", encoding="utf-8")'),
    "basket build tables never rebuilt": (BUILD, "and report.is_file() and not rebuild:", "and report.is_file():"),
    "basket build unchanged pages show the new run": (BUILD, "return previous, True, False", "return public, True, False"),
    "basket build collected by in UTC": (BUILD, 'f"{now.astimezone(ISRAEL):%H:%M}"', 'f"{now:%H:%M}"'),
    # basket: final fix wave
    "final revision keeps no earlier reason": (BUILD, '"revised": previous["revised"],', '"revised": None,'),
    "final earlier revisions not on the page": (WORDS, 'earlier_part = f" Earlier: {before}." if before else ""', 'earlier_part = ""'),
    "final earlier revisions oldest first": (PAGE, 'for run in reversed(public["revisions"]) if run.get("revised")]', 'for run in public["revisions"] if run.get("revised")]'),
    "final site bucket unversioned": (SITE_TEMPLATE, "      VersioningConfiguration:\n        Status: Enabled\n", ""),
    "final site bucket versioning suspended": (SITE_TEMPLATE, "        Status: Enabled", "        Status: Suspended"),
    "final guard passes a differing day as unchanged": (GUARD, "if not published.is_file() or local.read_bytes() == published.read_bytes():", "if True:"),
    "final guard compares a day new to the bucket": (GUARD, "if not published.is_file() or local.read_bytes()", "if local.read_bytes()"),
    "final guard takes a revision without a reason": (GUARD, 'isinstance(new.get("revised"), dict) and ', ""),
    "final guard takes a reason as text": (GUARD, 'isinstance(new.get("revised"), dict)', 'new.get("revised") is not None'),
    "final guard takes as many revisions": (GUARD, "len(revisions) > len(earlier)", "len(revisions) >= len(earlier)"),
    "final guard takes revisions that are not a list": (GUARD, 'isinstance(new.get("revised"), dict) and isinstance(revisions, list)', 'isinstance(new.get("revised"), dict) and revisions'),
    "final guard reads a published day without revisions": (GUARD, " and isinstance(earlier, list)", ""),
    "final guard reads an unreadable day as empty": (GUARD, "    except (UnicodeDecodeError, json.JSONDecodeError):\n        return None", "    except (UnicodeDecodeError, json.JSONDecodeError):\n        return {}"),
    "final guard crashes on a file not UTF-8": (GUARD, "except (UnicodeDecodeError, json.JSONDecodeError):", "except json.JSONDecodeError:"),
    "final guard reads a JSON list as a day": (GUARD, "return day if isinstance(day, dict) else None", "return day"),
    "final guard reads only the local day": (GUARD, "for path, day in ((local, new), (published, old)) if day is None]", "for path, day in ((local, new),) if day is None]"),
    "final guard exits 0 on a problem": (GUARD, "return 1 if problems else 0", "return 0"),
    "final guard passes with no local folder": (GUARD, "    if not local.is_dir():\n", "    if False:\n"),
    "final check needs no revised on on a revised day": (CHECK_BASKET, "        if not _says(REVISED, read):\n", "        if False:\n"),
    "final check counts revised on in an attribute": (CHECK_BASKET, "if not _says(REVISED, read):", "if not _says(REVISED, written, read):"),
    "final check right curly apostrophe not folded": (CHECK_BASKET, 'str.maketrans("\\u2018\\u2019", "\'\'")', 'str.maketrans("\\u2018", "\'")'),
    "final check left curly apostrophe not folded": (CHECK_BASKET, 'str.maketrans("\\u2018\\u2019", "\'\'")', 'str.maketrans("\\u2019", "\'")'),
    "final check apostrophes never folded": (CHECK_BASKET, ".translate(APOSTROPHES)", ""),
    "final always says only median": (WORDS, '"the chain\'s median across its stores")', '"median")'),
    "final fingerprint over the basket package only": (RECORD, "Path(basket_package.__file__).parent.parent)", "Path(basket_package.__file__).parent)"),
    "final store of a sub-chain left out counted with a file": (RULES, " and sub_chain not in excluded_sub_chains.get(chain, ())", ""),
    "final build counts a store of a sub-chain left out": (BUILD, "stores_with_file_keys(con, included_stores, sub_chains)", "stores_with_file_keys(con, included_stores, {})"),
    "final candidates count a store of a sub-chain left out": (CANDIDATES_MAIN, "stores_with_file(con, included_stores, sub_chains)", "stores_with_file(con, included_stores, {})"),
    # basket: archive (step two)
    "archive table key out of the tables folder": (ARCHIVE, 'return f"tables/prices/chain={slug}', 'return f"tables/chain={slug}'),
    "archive record key out of the basket folder": (ARCHIVE, 'basket-{run_id}.json"', '{run_id}.json"'),
    "archive day checked without a check record": (ARCHIVE, "return bool(self._keys(folder))", "return True"),
    "archive another day's check counted": (ARCHIVE, 'folder = check_key(day, "x").rsplit("/", 1)[0] + "/"', 'folder = "checks/"'),
    "archive price files of another kind fetched": (ARCHIVE, 'parsed.kind != "PriceFull"', 'parsed.kind != "Stores"'),
    "archive price file of another day fetched": (ARCHIVE, " or parsed.day != day", ""),
    "archive conflict copy not fetched": (ARCHIVE, "parse_file_name(published_name(_stored_name(key)))", "parse_file_name(_stored_name(key))"),
    "archive price file keys unsorted": (ARCHIVE, "return sorted(keys)", "return keys"),
    "archive raw file written under its published name": (ARCHIVE, "            name = _stored_name(key)\n", "            name = published_name(key)\n"),
    "archive store list looked for one day only": (ARCHIVE, "STORE_LIST_LOOKBACK_DAYS = 14", "STORE_LIST_LOOKBACK_DAYS = 1"),
    "archive store list looked for a day too far back": (ARCHIVE, "range(STORE_LIST_LOOKBACK_DAYS)", "range(STORE_LIST_LOOKBACK_DAYS + 1)"),
    "archive store list of another day taken": (ARCHIVE, " if is_store_list(name, listed_day)]", "]"),
    "archive store list found by a case-bound prefix": (ARCHIVE, 'self._keys(raw_key(slug, listed_day, ""))', 'self._keys(raw_key(slug, listed_day, "Stores"))'),
    "archive store list's oldest name taken": (ARCHIVE, "name = max(names)", "name = min(names)"),
    "archive store list written under the asked day": (ARCHIVE, "folder = _day_folder(raw_dir, slug, listed_day)", "folder = _day_folder(raw_dir, slug, day)"),
    "archive every chain's manifests fetched": (ARCHIVE, 'manifest_key(day, slug, "").removesuffix(".json")', 'manifest_key(day, slug, "").rsplit("/", 1)[0]'),
    "archive table's parquet written without its report": (ARCHIVE, "        if None in bodies.values():\n            return False\n        folder.mkdir(parents=True, exist_ok=True)\n        for name, body in bodies.items():\n            (folder / name).write_bytes(body)\n",
                                                           "        folder.mkdir(parents=True, exist_ok=True)\n        for name, body in bodies.items():\n            if body is not None:\n                (folder / name).write_bytes(body)\n        if None in bodies.values():\n            return False\n"),
    "archive table without its parquet taken": (ARCHIVE, "if None in bodies.values():", 'if bodies["report.json"] is None:'),
    "archive table put locked": (ARCHIVE, "self._put_plain(key, (folder / name).read_bytes(), _CONTENT_TYPES[name])", "self._put_locked(key, (folder / name).read_bytes(), None, _CONTENT_TYPES[name])"),
    "archive table content types swapped": (ARCHIVE, '{"prices.parquet": "application/vnd.apache.parquet", "report.json": "application/json"}', '{"prices.parquet": "application/json", "report.json": "application/vnd.apache.parquet"}'),
    "archive a delete before a table put": (ARCHIVE, "            self._put_plain(key, (folder / name).read_bytes(), _CONTENT_TYPES[name])\n",
                                            '            getattr(self, "client", None) and self.client.delete_object(Bucket=self.bucket, Key=key)\n            self._put_plain(key, (folder / name).read_bytes(), _CONTENT_TYPES[name])\n'),
    "archive record put plain": (ARCHIVE, "self.put_record(key, body, now)", 'self._put_plain(key, body, "application/json")'),
    # basket: site (step two)
    "site day file always put": (SITE, "        if with_day:\n", "        if True:\n"),
    "site pages always put": (SITE, "        if with_pages:\n", "        if True:\n"),
    "site S3 put without cache control": (SITE, ", CacheControl=cache_control)", ")"),
    "site upload without cache control": (SITE, "content_type, CACHE_CONTROL)", 'content_type, "")'),
    "site invalidates the index page only": (SITE, '"Items": ["/*"]', '"Items": ["/index.html"]'),
    "site latest day the smallest": (SITE, "return max(days, default=None)", "return min(days, default=None)"),
    "site cache control not publish.sh's": (SITE, 'CACHE_CONTROL = "max-age=300"', 'CACHE_CONTROL = "max-age=3000"'),
    "site day file under another key": (SITE, 'return f"days/{day.isoformat()}.json"', 'return f"day/{day.isoformat()}.json"'),
    "site pages put as JSON": (SITE, "files += [(name, HTML) for name in PAGES]", "files += [(name, JSON) for name in PAGES]"),
    "site day file put as HTML": (SITE, "files.append((day_key(day), JSON))", "files.append((day_key(day), HTML))"),
    "site day file put before the pages": (SITE, "        if with_pages:\n            files += [(name, HTML) for name in PAGES]\n        if with_day:\n            files.append((day_key(day), JSON))\n",
                                           "        if with_day:\n            files.append((day_key(day), JSON))\n        if with_pages:\n            files += [(name, HTML) for name in PAGES]\n"),
    "site puts before every file is found": (SITE, "            if not (site_dir / key).is_file():\n", "            if False:\n"),
    "site key with more after .json read as a day": (SITE, r'\.json$")', r'\.json")'),
    "site impossible date stops the latest day": (SITE, "except ValueError:", "except TypeError:"),
    "site bare 404 read as an error": (SITE, "if _code(err) in MISSING:", 'if _code(err) == "NoSuchKey":'),
    "site read error hidden": (SITE, "if _code(err) in MISSING:", "if True:"),
    "site listing stops at the first page": (SITE, 'for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):',
                                             "for page in [self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)]:"),
    "site invalidation under a fixed reference": (SITE, '"CallerReference": reference}', '"CallerReference": "basket"}'),
    "site invalidation id not CloudFront's": (SITE, 'return answer["Invalidation"]["Id"]', "return reference"),
    "site a delete before a put": (SITE, "        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, CacheControl=cache_control)\n",
                                   "        self.s3.delete_object(Bucket=self.bucket, Key=key)\n        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, CacheControl=cache_control)\n"),
    # basket: the scheduled build's handler (step two)
    "basket handler site bucket outside the prefix accepted": (BASKET_HANDLER, '        if not env["SITE_BUCKET"].startswith(SITE_BUCKET_PREFIX):\n', "        if False:\n"),
    "basket handler runs before the morning's check": (BASKET_HANDLER, "    if not deps.archive.day_checked(day):\n", "    if False:\n"),
    "basket handler work folder left behind": (BASKET_HANDLER, "            _remove(work)\n", "            pass\n"),
    "basket handler table put before the extraction": (BASKET_HANDLER, '    report = extract(work / "raw", slug, day, work / "tables")\n    seconds = time.perf_counter() - started\n    keys = deps.archive.put_table(slug, day, work / "tables")\n',
                                                       '    keys = deps.archive.put_table(slug, day, work / "tables")\n    report = extract(work / "raw", slug, day, work / "tables")\n    seconds = time.perf_counter() - started\n'),
    "basket handler work folder removed only after a success": (BASKET_HANDLER, "        finally:\n            _remove(work)\n",
                                                                "        except ZeroDivisionError:\n            raise\n        _remove(work)\n"),
    "basket handler work folder outside tmp_root": (BASKET_HANDLER, 'tempfile.mkdtemp(prefix="basket-", dir=tmp_root)', 'tempfile.mkdtemp(prefix="basket-")'),
    "basket handler an earlier run's work folder not swept": (BASKET_HANDLER, "        _sweep(tmp_root, cfg.duckdb_temp_directory)\n", ""),
    "basket handler sweep given no DuckDB folder": (BASKET_HANDLER, "_sweep(tmp_root, cfg.duckdb_temp_directory)", "_sweep(tmp_root, None)"),
    "basket handler DuckDB's temp folder not swept": (BASKET_HANDLER, "        _remove(spill)\n", ""),
    "basket handler DuckDB's temp folder swept without a word": (BASKET_HANDLER, '        log.info("removed what earlier runs left in DuckDB', '        log.debug("removed what earlier runs left in DuckDB'),
    "basket handler an empty DuckDB temp folder reported": (BASKET_HANDLER, "    if left:\n", "    if True:\n"),
    "basket handler a missing DuckDB temp folder listed": (BASKET_HANDLER, "    if spill is not None and spill.is_dir():\n", "    if spill is not None:\n"),
    "basket handler a linked DuckDB temp folder swept": (BASKET_HANDLER, "    if spill.is_symlink() or tmp_root", "    if tmp_root"),
    "basket handler a DuckDB temp folder outside tmp_root swept": (BASKET_HANDLER, "tmp_root.resolve() not in spill.resolve().parents:", "False:"),
    "basket handler tmp_root itself swept as DuckDB's folder": (BASKET_HANDLER, "not in spill.resolve().parents:", "not in (spill.resolve(), *spill.resolve().parents):"),
    "basket handler an unreadable DuckDB temp folder fails the run": (BASKET_HANDLER, "    except OSError as error:\n        log.warning(\"could not read", "    except ZeroDivisionError as error:\n        log.warning(\"could not read"),
    "basket handler a blank DuckDB folder read as one": (BASKET_HANDLER, "Path(spill) if spill else None", "Path(spill)"),
    "basket handler a failed removal logged below a warning": (BASKET_HANDLER, '    log.warning("could not remove', '    log.info("could not remove'),
    "basket handler config ignores DuckDB's temp folder": (BASKET_HANDLER, "duckdb_temp_directory=Path(spill) if spill else None)", "duckdb_temp_directory=None)"),
    "basket handler config reads DuckDB's folder with its spaces": (BASKET_HANDLER, 'spill = env.get(TEMP_DIRECTORY_VAR, "").strip()', 'spill = env.get(TEMP_DIRECTORY_VAR, "")'),
    "basket handler a failed removal passes in silence": (BASKET_HANDLER, "shutil.rmtree(path, onexc=_not_removed)", "shutil.rmtree(path, ignore_errors=True)"),
    "basket handler a failed removal fails the run": (BASKET_HANDLER, "shutil.rmtree(path, onexc=_not_removed)", "shutil.rmtree(path)"),
    "basket handler a failed removal's warning without the path": (BASKET_HANDLER, '"could not remove %s: %s: %s", path,', '"could not remove %s: %s: %s", "a path",'),
    "basket handler extract summary's unreadable count always 0": (BASKET_HANDLER, '"unreadable_prices": report.unreadable_prices', '"unreadable_prices": 0'),
    "basket handler sweep removes folders not its own": (BASKET_HANDLER, 'tmp_root.glob("basket-*")', 'tmp_root.glob("*")'),
    "basket handler stale work folders removed without a word": (BASKET_HANDLER, "    if stale:\n        log.info(", "    if False:\n        log.info("),
    "basket handler naive now accepted by run": (BASKET_HANDLER, "    _aware(now)\n    day = event_day(event, now)\n", "    day = event_day(event, now)\n"),
    "basket handler naive now read as this machine's": (BASKET_HANDLER, "        return _aware(now).astimezone(ISRAEL).date()\n", "        return now.astimezone(ISRAEL).date()\n"),
    "basket handler day in UTC": (BASKET_HANDLER, "_aware(now).astimezone(ISRAEL).date()", "_aware(now).astimezone(timezone.utc).date()"),
    "basket handler event's day ignored": (BASKET_HANDLER, '    if "day" not in event:\n', "    if True:\n"),
    "basket handler a day that is no string raised as a TypeError": (BASKET_HANDLER, "    except (TypeError, ValueError):", "    except ValueError:"),
    "basket handler unknown mode read as a basket run": (BASKET_HANDLER, "    if mode not in MODES:\n", "    if mode is None:\n"),
    "basket handler unknown chain accepted": (BASKET_HANDLER, '        if event.get("chain") not in SLUGS:\n', '        if "chain" not in event:\n'),
    "basket handler collected_by not a clock accepted": (BASKET_HANDLER, "if not isinstance(collected_by, str) or not CLOCK.fullmatch(collected_by):", "if collected_by is None:"),
    "basket handler collected_by with a trailing newline accepted": (BASKET_HANDLER, "CLOCK.fullmatch(collected_by)", "CLOCK.match(collected_by)"),
    "basket handler User-Agent not checked by the config": (BASKET_HANDLER, 'user_agent=check_user_agent(env["USER_AGENT"])', 'user_agent=env["USER_AGENT"]'),
    "basket handler a blank variable accepted": (BASKET_HANDLER, 'if not env.get(name, "").strip()]', "if name not in env]"),
    "basket handler distribution and ping URL not required": (BASKET_HANDLER, 'REQUIRED = ("BUCKET", "SITE_BUCKET", "DISTRIBUTION_ID", "HEALTHCHECK_URL", "USER_AGENT")', 'REQUIRED = ("BUCKET", "SITE_BUCKET", "USER_AGENT")'),
    "basket handler RETENTION_DAYS ignored": (BASKET_HANDLER, 'retention_days=int(env.get("RETENTION_DAYS", RETENTION_DAYS))', "retention_days=RETENTION_DAYS"),
    "basket handler RETENTION_DAYS default not ten years": (BASKET_HANDLER, 'env.get("RETENTION_DAYS", RETENTION_DAYS)', 'env.get("RETENTION_DAYS", 365)'),
    "basket handler run id under another mode": (BASKET_HANDLER, 'new_run_id(now, "extract")', 'new_run_id(now, "basket")'),
    "basket handler summary not logged": (BASKET_HANDLER, "    log.info(json.dumps(summary, sort_keys=True))\n", "    pass\n"),
    "basket log level left to the runtime": (BASKET_HANDLER, 'logging.getLogger("basket").setLevel(logging.INFO)\n', "\n"),
    # basket: the handler's basket mode
    "basket handler the scheduled run revises": (BASKET_HANDLER, "revise=None", 'revise="scheduled"'),
    "basket handler record put only after a success": (BASKET_HANDLER, "    finally:  # every build of every day is kept, a refused one included\n",
                                                       "    except ZeroDivisionError:\n        raise\n    if True:\n"),
    "basket handler an unchanged day file uploaded again": (BASKET_HANDLER, "with_day=not outcome.unchanged", "with_day=True"),
    "basket handler pages uploaded for a day before the site's latest": (BASKET_HANDLER, "day >= latest", "day <= latest"),
    "basket handler no /fail ping": (BASKET_HANDLER, '            _ping(deps, cfg.healthcheck_url, "fail", _cut(f"{type(err).__name__}: {err}", FAIL_BYTES))\n', "            pass\n"),
    "basket handler a missing table passed over": (BASKET_HANDLER, "                raise MissingTable(f\"no table for chain {slug!r} on {day}: its extraction run did not run or did not \"\n"
                                                                   "                                   f\"finish ({table_key(slug, day, 'prices.parquet')})\")\n",
                                                   "                continue\n"),
    "basket handler no /start ping": (BASKET_HANDLER, '        _ping(deps, cfg.healthcheck_url, "start", "")\n', "        pass\n"),
    "basket handler a day without a check record not pinged as a failure": (BASKET_HANDLER, "    except Exception as err:\n        if pings:\n",
                                                                            "    except Exception as err:\n        if pings and not isinstance(err, MorningNotChecked):\n"),
    "basket handler the extract mode pings": (BASKET_HANDLER, '    pings = mode == "basket"  # the extract mode never pings\n', "    pings = True\n"),
    "basket handler no success ping": (BASKET_HANDLER, '                _ping(deps, cfg.healthcheck_url, "success", json.dumps(summary))\n', "                pass\n"),
    "basket handler a failing ping raised": (BASKET_HANDLER, "    except Exception as exc:  # healthchecks.io down or slow: the run's outcome stands\n", "    except ZeroDivisionError as exc:\n"),
    "basket handler site not checked": (BASKET_HANDLER, "        problems = check_site(site)\n", "        problems = []\n"),
    "basket handler days not guarded": (BASKET_HANDLER, '        problems = guard_days(site / "days", published / "days")\n', "        problems = []\n"),
    "basket handler invalidated with nothing uploaded": (BASKET_HANDLER, "deps.site.invalidate(outcome.record.run_id) if uploaded else None", "deps.site.invalidate(outcome.record.run_id)"),
    "basket handler build not given the published day": (BASKET_HANDLER, '            for folder in (site / "days", published / "days"):\n', '            for folder in (published / "days",):\n'),
    "basket handler guard not given the published day": (BASKET_HANDLER, '            for folder in (site / "days", published / "days"):\n', '            for folder in (site / "days",):\n'),
    "basket handler collected_by not the event's": (BASKET_HANDLER, 'collected_by=event["collected_by"]', "collected_by=None"),
    "basket handler /fail body not cut": (BASKET_HANDLER, "    return text.encode()[:limit].decode(errors=\"ignore\")\n", "    return text\n"),
    "basket handler /fail body cut by characters": (BASKET_HANDLER, "    return text.encode()[:limit].decode(errors=\"ignore\")\n", "    return text[:limit]\n"),
    "basket handler /fail body cut inside a character": (BASKET_HANDLER, 'decode(errors="ignore")', 'decode(errors="replace")'),
    "basket handler /fail body over healthchecks.io's 100 kB": (BASKET_HANDLER, "FAIL_BYTES = 100_000  #", "FAIL_BYTES = 100_001  #"),
    "basket handler item floor lowered": (BASKET_HANDLER, "MIN_ITEMS = 25  #", "MIN_ITEMS = 1  #"),
    "basket handler a failed ping logged by its URL": (BASKET_HANDLER, 'failed: %s: %s", kind, type(exc).__name__', 'failed: %s: %s", base + PING_PATHS[kind], type(exc).__name__'),
    "basket handler a failed ping's error text logged unmasked": (BASKET_HANDLER, "_masked(str(exc), base))", "exc)"),
    "basket handler the ping's id left in an error's text": (BASKET_HANDLER, "(url, parts.netloc, *parts.path.split(\"/\"))", "(url, parts.netloc)"),
    "basket handler the ping's host left in an error's text": (BASKET_HANDLER, "(url, parts.netloc, *parts.path.split(\"/\"))", "(url, *parts.path.split(\"/\"))"),
    # the DuckDB layer
    "layer wheel's hash altered": (LAYER_PIN, "sha256:364992ba", "sha256:464992ba"),
    "layer built for x86": (LAYER_MAKEFILE, "manylinux_2_28_aarch64", "manylinux_2_28_x86_64"),
    "layer installs the wheel's dependencies too": (LAYER_MAKEFILE, " --no-deps", ""),
    # template: the basket function (step two), the rules the plan names
    "basket schedule on the collector's switch": (BASKET_OWN_SWITCH, "Input: '{\"mode\": \"basket\", \"collected_by\": \"12:03\"}'\n            State: !Ref BasketScheduleState",
                                                  "Input: '{\"mode\": \"basket\", \"collected_by\": \"12:03\"}'\n            State: !Ref ScheduleState"),
    "basket run before the last extraction can have finished": (BASKET_AFTER_EXTRACT, '"cron(33 12 * * ? *)"', '"cron(13 12 * * ? *)"'),
    "an extraction before the collector's check can have finished": (EXTRACT_AFTER_CHECK, '"cron(3 12 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "extract", "chain": "yochananof"}\'',
                                                                     '"cron(50 11 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "extract", "chain": "yochananof"}\''),
    "collected by the check's time, not the extractions'": (COLLECTED_BY_PINNED, '"collected_by": "12:03"', '"collected_by": "11:48"'),
    "basket role deletes in the site bucket": (NO_DELETE_BASKET, "- Sid: WriteSite\n              Effect: Allow\n              Action: s3:PutObject\n", "- Sid: WriteSite\n              Effect: Allow\n              Action: s3:DeleteObject\n"),
    "basket records not readable for a refused put": (READ_RECORDS_FOR_RETRY, '                - !Sub "${ArchiveBucket.Arn}/tables/*"\n                - !Sub "${ArchiveBucket.Arn}/basket/*"\n',
                                                      '                - !Sub "${ArchiveBucket.Arn}/tables/*"\n'),
    "basket /tmp at 512 MB": (TMP_SIZE, "{Size: 2048}", "{Size: 512}"),
    "basket function without the DuckDB layer": (LAYER_ATTACHED, "      Layers: [!Ref DuckDbLayer]\n", ""),
    # template: the basket function
    "basket function on x86": (BASKET_TEMPLATE, "Handler: basket.handler.handler\n      Runtime: python3.13\n      Architectures: [arm64]", "Handler: basket.handler.handler\n      Runtime: python3.13\n      Architectures: [x86_64]"),
    "basket function on an older Python": (BASKET_TEMPLATE, "Handler: basket.handler.handler\n      Runtime: python3.13", "Handler: basket.handler.handler\n      Runtime: python3.12"),
    "basket handler pointed elsewhere": (BASKET_TEMPLATE, "Handler: basket.handler.handler", "Handler: basket.handler.run"),
    "basket code from the repo root": (BASKET_TEMPLATE, "CodeUri: src/\n      Handler: basket.handler.handler", "CodeUri: ./\n      Handler: basket.handler.handler"),
    "basket function memory halved": (BASKET_TEMPLATE, "MemorySize: 2048", "MemorySize: 1024"),
    "basket function timeout cut to five minutes": (BASKET_TEMPLATE, "spaced by it.\n      Timeout: 900\n", "spaced by it.\n      Timeout: 300\n"),
    "basket Lambda retries a failed run": (BASKET_TEMPLATE, "rerun is by hand.\n      EventInvokeConfig:\n        MaximumRetryAttempts: 0", "rerun is by hand.\n      EventInvokeConfig:\n        MaximumRetryAttempts: 2"),
    "basket logs to Lambda's default group": (BASKET_TEMPLATE, "      LoggingConfig:\n        LogGroup: !Ref BasketLogs\n", ""),
    "basket logs kept forever": (BASKET_TEMPLATE, '/basket"\n      RetentionInDays: 30\n', '/basket"\n'),
    "basket logs under another group name": (BASKET_TEMPLATE, 'LogGroupName: !Sub "/${AWS::StackName}/basket"', 'LogGroupName: !Sub "/${AWS::StackName}/collector-basket"'),
    "basket function name not in the outputs": (BASKET_TEMPLATE, "  BasketFunctionName:\n    Value: !Ref BasketFunction\n", ""),
    "basket site bucket not given to the function": (BASKET_TEMPLATE, "          SITE_BUCKET: !Ref SiteBucketName\n", ""),
    "basket pings the collector's check": (BASKET_TEMPLATE, "HEALTHCHECK_URL: !Ref BasketHealthcheckUrl", "HEALTHCHECK_URL: !Ref HealthcheckUrl"),
    "basket retention not ten years": (BASKET_TEMPLATE, 'USER_AGENT: !Ref UserAgent\n          RETENTION_DAYS: "3650"', 'USER_AGENT: !Ref UserAgent\n          RETENTION_DAYS: "365"'),
    "DuckDB temp folder in the read-only working directory": (BASKET_TEMPLATE, "DUCKDB_TEMP_DIRECTORY: /tmp/duckdb", "DUCKDB_TEMP_DIRECTORY: .tmp"),
    "DuckDB memory limit over the function's": (BASKET_TEMPLATE, "DUCKDB_MEMORY_LIMIT: 1200MB", "DUCKDB_MEMORY_LIMIT: 4GB"),
    # template: the basket function's role
    "basket role with S3 full access": (BASKET_TEMPLATE, "      Policies:\n        - Statement:\n            # The extractions", "      Policies:\n        - AmazonS3FullAccess\n        - Statement:\n            # The extractions"),
    "basket records deletable": (BASKET_TEMPLATE, "                - s3:PutObjectRetention\n              Resource: !Sub", "                - s3:PutObjectRetention\n                - s3:DeleteObject\n              Resource: !Sub"),
    "basket governance bypass allowed": (BASKET_TEMPLATE, "                - s3:PutObjectRetention\n              Resource: !Sub", "                - s3:PutObjectRetention\n                - s3:BypassGovernanceRetention\n              Resource: !Sub"),
    "basket bucket settings writable": (BASKET_TEMPLATE, "                - s3:PutObjectRetention\n              Resource: !Sub", "                - s3:PutObjectRetention\n                - s3:PutBucketPolicy\n              Resource: !Sub"),
    "basket records put without their retention": (BASKET_TEMPLATE, "                - s3:PutObject\n                - s3:PutObjectRetention\n              Resource: !Sub", "                - s3:PutObject\n              Resource: !Sub"),
    "basket records writable anywhere in the archive": (BASKET_TEMPLATE, 'Resource: !Sub "${ArchiveBucket.Arn}/basket/*"', 'Resource: !Sub "${ArchiveBucket.Arn}/*"'),
    "basket tables writable anywhere in the archive": (BASKET_TEMPLATE, 'Resource: !Sub "${ArchiveBucket.Arn}/tables/*"', 'Resource: !Sub "${ArchiveBucket.Arn}/*"'),
    "basket tables not readable": (BASKET_TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n                - !Sub "${ArchiveBucket.Arn}/tables/*"\n', '                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n'),
    "basket role reads the check records": (BASKET_TEMPLATE, '                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n                - !Sub "${ArchiveBucket.Arn}/tables/*"\n',
                                            '                - !Sub "${ArchiveBucket.Arn}/manifests/*"\n                - !Sub "${ArchiveBucket.Arn}/checks/*"\n                - !Sub "${ArchiveBucket.Arn}/tables/*"\n'),
    "basket every S3 action on the site": (BASKET_TEMPLATE, "- Sid: WriteSite\n              Effect: Allow\n              Action: s3:PutObject\n", '- Sid: WriteSite\n              Effect: Allow\n              Action: "s3:*"\n'),
    "basket site writable anywhere": (BASKET_TEMPLATE, '                - !Sub "arn:aws:s3:::${SiteBucketName}/index.html"\n', '                - !Sub "arn:aws:s3:::${SiteBucketName}/*"\n'),
    "basket no list of the archive": (BASKET_TEMPLATE, "- Sid: ListArchive\n              Effect: Allow\n              Action: s3:ListBucket\n", "- Sid: ListArchive\n              Effect: Allow\n              Action: s3:ListAllMyBuckets\n"),
    "basket no list of the site": (BASKET_TEMPLATE, "- Sid: ListSite\n              Effect: Allow\n              Action: s3:ListBucket\n", "- Sid: ListSite\n              Effect: Allow\n              Action: s3:ListAllMyBuckets\n"),
    "basket a condition on the site list": (BASKET_TEMPLATE, '              Resource: !Sub "arn:aws:s3:::${SiteBucketName}"\n', '              Resource: !Sub "arn:aws:s3:::${SiteBucketName}"\n              Condition:\n                StringLike:\n                  s3:prefix: ["days/*"]\n'),
    "basket invalidates any distribution": (BASKET_TEMPLATE, ":distribution/${SiteDistributionId}", ":distribution/*"),
    # template: the basket's parameters
    "site bucket of any name": (BASKET_TEMPLATE, "AllowedPattern: 'il-grocery-prices-site-sitebucket-.+'", "AllowedPattern: '.+'"),
    "site bucket pattern takes the bare prefix": (BASKET_TEMPLATE, "AllowedPattern: 'il-grocery-prices-site-sitebucket-.+'", "AllowedPattern: 'il-grocery-prices-site-sitebucket-.*'"),
    "distribution id of any shape": (BASKET_TEMPLATE, "AllowedPattern: 'E[A-Z0-9]+'", "AllowedPattern: '.*'"),
    "a site parameter given a default": (BASKET_TEMPLATE, "  SiteDistributionId:\n    Type: String\n", "  SiteDistributionId:\n    Type: String\n    Default: E0123456789ABC\n"),
    "basket ping URL shown in the stack": (BASKET_TEMPLATE, "  BasketHealthcheckUrl:\n    Type: String\n    NoEcho: true\n", "  BasketHealthcheckUrl:\n    Type: String\n    NoEcho: false\n"),
    "basket ping URL of any shape": (BASKET_TEMPLATE, "e.g. https://hc-ping.com/<uuid>\n    AllowedPattern: 'https://hc-ping\\.com/[-A-Za-z0-9_/]+'", "e.g. https://hc-ping.com/<uuid>\n    AllowedPattern: '.*'"),
    "basket schedules enabled by default": (BASKET_TEMPLATE, "  BasketScheduleState:\n    Type: String\n    Default: DISABLED\n", "  BasketScheduleState:\n    Type: String\n    Default: ENABLED\n"),
    "basket switch takes any value": (BASKET_TEMPLATE, "    AllowedValues: [ENABLED, DISABLED]\n    Description: The basket's", "    Description: The basket's"),
    # template: the basket's schedules
    "a basket schedule in UTC": (BASKET_TEMPLATE, 'ScheduleExpression: "cron(33 12 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem', 'ScheduleExpression: "cron(33 12 * * ? *)"\n            ScheduleExpressionTimezone: UTC'),
    "a basket schedule always on": (BASKET_TEMPLATE, "Input: '{\"mode\": \"extract\", \"chain\": \"ramilevy\"}'\n            State: !Ref BasketScheduleState", "Input: '{\"mode\": \"extract\", \"chain\": \"ramilevy\"}'\n            State: ENABLED"),
    "a basket schedule with a flexible start window": (BASKET_TEMPLATE, "Input: '{\"mode\": \"extract\", \"chain\": \"shufersal\"}'\n            State: !Ref BasketScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}",
                                                       "Input: '{\"mode\": \"extract\", \"chain\": \"shufersal\"}'\n            State: !Ref BasketScheduleState\n            FlexibleTimeWindow: {Mode: \"FLEXIBLE\", MaximumWindowInMinutes: 15}"),
    "Scheduler retries a failed basket invoke": (BASKET_TEMPLATE, "\"12:03\"}'\n            State: !Ref BasketScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}\n            RetryPolicy: {MaximumRetryAttempts: 0}",
                                                 "\"12:03\"}'\n            State: !Ref BasketScheduleState\n            FlexibleTimeWindow: {Mode: \"OFF\"}\n            RetryPolicy: {MaximumRetryAttempts: 185}"),
    "two extractions at different minutes": (BASKET_TEMPLATE, '"cron(3 12 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "extract", "chain": "carrefour"}\'',
                                             '"cron(4 12 * * ? *)"\n            ScheduleExpressionTimezone: Asia/Jerusalem\n            Input: \'{"mode": "extract", "chain": "carrefour"}\''),
    "an extraction of a chain the code does not know": (BASKET_TEMPLATE, "Input: '{\"mode\": \"extract\", \"chain\": \"carrefour\"}'", "Input: '{\"mode\": \"extract\", \"chain\": \"victory\"}'"),
    "a chain without an extraction": (BASKET_TEMPLATE, "Input: '{\"mode\": \"extract\", \"chain\": \"yochananof\"}'", "Input: '{\"mode\": \"extract\", \"chain\": \"osherad\"}'"),
    "a scheduled extraction pinned to a day": (BASKET_TEMPLATE, "Input: '{\"mode\": \"extract\", \"chain\": \"osherad\"}'", "Input: '{\"mode\": \"extract\", \"chain\": \"osherad\", \"day\": \"2026-11-03\"}'"),
    "the basket event without collected_by": (BASKET_TEMPLATE, "Input: '{\"mode\": \"basket\", \"collected_by\": \"12:03\"}'", "Input: '{\"mode\": \"basket\"}'"),
    "collected_by not a clock": (BASKET_TEMPLATE, '"collected_by": "12:03"', '"collected_by": "12.03"'),
    # template: the DuckDB layer
    "layer built without the Makefile": (BASKET_TEMPLATE, "    Metadata:\n      BuildMethod: makefile\n", "    Metadata:\n      BuildMethod: python3.13\n"),
    "layer read as x86_64 by sam build": (BASKET_TEMPLATE, "      BuildArchitecture: arm64\n", ""),
    "layer for x86": (BASKET_TEMPLATE, "CompatibleArchitectures: [arm64]", "CompatibleArchitectures: [x86_64]"),
    "layer for an older Python": (BASKET_TEMPLATE, "CompatibleRuntimes: [python3.13]", "CompatibleRuntimes: [python3.12]"),
    "layer from the repo root": (BASKET_TEMPLATE, "ContentUri: layer/", "ContentUri: ./"),
    "layer's old versions retained": (BASKET_TEMPLATE, "RetentionPolicy: Delete", "RetentionPolicy: Retain"),
    # the mutation check itself (each text to break spans a line end, so it occurs once: here it is written \n)
    "mutation check counts any non-zero exit as caught": (MUTATION_CHECK, '    if returncode == ExitCode.TESTS_FAILED:\n        return "CAUGHT"', '    if returncode != ExitCode.OK:\n        return "CAUGHT"'),
    "mutation check passes with errors": (MUTATION_CHECK, '(found or " Every mutation was caught."))\n    return 1 if missed or errors else 0', '(found or " Every mutation was caught."))\n    return 1 if missed else 0'),
    "mutation check runs with duplicate names": (MUTATION_CHECK, '    if duplicates:\n        print(f"DUPLICATE', '    if False:\n        print(f"DUPLICATE'),
    "mutation check shows the file, not a collection error's cause": (MUTATION_CHECK, '    exception = [line for line in lines if line.startswith("E ")]\n', '    exception = []\n'),
    "mutation check shows pytest's last line, not a missing test's id": (MUTATION_CHECK, '    error = [line for line in lines if line.startswith("ERROR")]\n', '    error = []\n'),
    "mutation check crashes on a signal's exit": (MUTATION_CHECK, '    try:\n        return ExitCode(returncode).name\n    except ValueError:', '    if True:\n        return ExitCode(returncode).name\n    if False:'),
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


def verdict(returncode: int) -> str:
    """CAUGHT when pytest says a test failed, MISSED when every test passed, ERROR for any other exit."""
    if returncode == ExitCode.TESTS_FAILED:
        return "CAUGHT"
    if returncode == ExitCode.OK:
        return "MISSED"
    return "ERROR"


def _exit_name(returncode: int) -> str:
    try:
        return ExitCode(returncode).name
    except ValueError:  # a signal, or a code pytest does not define
        return "not pytest's"


def _telling_line(run: subprocess.CompletedProcess) -> str:
    """The line of pytest's output that names why it could not run the tests: its last `E ` line (a collection
    error's exception; the `ERROR` line after it names only the file), else its last `ERROR` line (a test id not
    found), else its last line."""
    lines = [line for line in (run.stdout + run.stderr).splitlines() if line.strip()]
    exception = [line for line in lines if line.startswith("E ")]
    error = [line for line in lines if line.startswith("ERROR")]
    return (exception or error or lines or ["(no output)"])[-1]


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
    errors = []
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
            outcome = verdict(run.returncode)
            if outcome == "ERROR":
                print(f"ERROR  {name}: pytest exited {run.returncode} ({_exit_name(run.returncode)}), not a test "
                      f"failure: {_telling_line(run)}")
                errors.append(name)
            else:
                print(f"{outcome} {name}")
                if outcome == "MISSED":
                    missed.append(name)
    finally:
        for path, original in originals.items():
            path.write_text(original)
    found = (f" Missed: {missed}" if missed else "") + (f" Errors: {errors}" if errors else "")
    print("Files restored." + (found or " Every mutation was caught."))
    return 1 if missed or errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

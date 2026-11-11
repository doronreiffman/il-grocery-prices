"""The mutation check's runner (`scripts/mutation_check.py`): what counts as caught, its time limit, and its guard on
duplicate names.

A mutation is caught only when pytest says a test failed (exit 1). Any other non-zero exit means pytest could not run
the tests as asked: a test id that no longer exists (4), a module that no longer imports (2), no tests collected (5).
That proves nothing about the rule, so it is an error, not a catch (it happened on 2026-11-01: a renamed test's old id
passed as caught). A run past the time limit is killed with everything it started (q25). It counts as caught (a break
that makes a test hang is a break the tests noticed) only when the same tests, unmutated, pass within the clean run's
limit; otherwise the time-out proves nothing and is an error too. A Ctrl-C kills the run as well: in a session of its
own, it does not get the terminal's interrupt. `main` is driven first with a fake `run_limited` whose answer the mutated
file sets, over a file of the test's own, so no real mutation runs; the last tests run real processes and real pytest,
with a limit of a second where one is hit.
"""
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "mutation_check.py"
HANG = "hang"
RULE_TESTS = ("tests/test_rule.py",)


def load():
    spec = importlib.util.spec_from_file_location("mutation_check_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check():
    return load()


@pytest.mark.parametrize("code, verdict", [(0, "MISSED"), (1, "CAUGHT"), (2, "ERROR"), (3, "ERROR"), (4, "ERROR"),
                                           (5, "ERROR"), (6, "ERROR"), (-9, "ERROR")])
def test_only_a_test_failure_counts_as_caught(check, code, verdict):
    assert check.verdict(code) == verdict


def fake_run(rule: Path, seen: list, clean: dict | None = None):
    """A stand-in for run_limited. The mutated `rule` file holds pytest's exit code, or `hang` for a run past the limit
    (run_limited's None). The file as it was (LIMIT = 0) is answered from `clean` by its target tests: exit 0 when they
    are not named there, `hang` for a clean run past its limit too. `seen` records each run's file, tests and limit."""
    def run(args, limit, **popen):
        text = rule.read_text()
        tests = tuple(args[3:args.index("-q")])
        seen.append((text, tests, limit))
        value = (clean or {}).get(tests, 0) if text == "LIMIT = 0\n" else text.split("=")[1].strip()
        if value == HANG:
            return None
        return subprocess.CompletedProcess(args, int(value), stdout="1 failed\n", stderr="ERROR: not found\n")
    return run


def mutations(tests=RULE_TESTS, **codes):
    return {name: (("rule.py", list(tests)), "LIMIT = 0", f"LIMIT = {code}") for name, code in codes.items()}


@pytest.fixture
def rule(check, tmp_path, monkeypatch):
    path = tmp_path / "rule.py"
    path.write_text("LIMIT = 0\n")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    return path


def test_main_reports_each_mutation_by_pytests_exit_and_restores_the_file(check, rule, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, missed=0, renamed=4, unimportable=2, killed=-9))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, seen))
    assert check.main([]) == 1
    assert [text for text, _, _ in seen] == ["LIMIT = 1\n", "LIMIT = 0\n", "LIMIT = 4\n", "LIMIT = 2\n", "LIMIT = -9\n"]
    assert rule.read_text() == "LIMIT = 0\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "CAUGHT caught"
    assert lines[1] == "MISSED missed"
    assert lines[2] == "ERROR  renamed: pytest exited 4 (USAGE_ERROR), not a test failure: ERROR: not found"
    assert lines[3] == "ERROR  unimportable: pytest exited 2 (INTERRUPTED), not a test failure: ERROR: not found"
    # a pytest killed by a signal (the out-of-memory killer's -9) exits with a code pytest does not define
    assert lines[4] == "ERROR  killed: pytest exited -9 (not pytest's), not a test failure: ERROR: not found"
    assert lines[5] == "Files restored. Missed: ['missed'] Errors: ['renamed', 'unimportable', 'killed']"


# What pytest 9.1.1 prints with the check's flags (-qq -x -p no:cacheprovider), measured 2026-11-03.
COLLECTION_ERROR = ("    import rule\nE   ModuleNotFoundError: No module named 'rule'\n"
                    "=========================== short test summary info ============================\n"
                    "ERROR tests/test_rule.py\n!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                    "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n")


@pytest.mark.parametrize("stdout, stderr, shown", [
    ("\n", "ERROR: not found: tests/test_rule.py::test_gone\n(no match in any of [<Module test_rule.py>])\n",
     "ERROR: not found: tests/test_rule.py::test_gone"),  # a test id that no longer exists (4)
    (COLLECTION_ERROR, "", "E   ModuleNotFoundError: No module named 'rule'"),  # a module that does not import (2)
    ("\n", "", "(no output)"),  # no tests collected (5)
    ("something else\n", "", "something else"),  # nothing that names a cause: the last line
])
def test_an_error_shows_the_line_that_names_its_cause(check, stdout, stderr, shown):
    """The cause is pytest's last `E ` line (a collection error's exception; the `ERROR` line after it names only the
    file), else its last `ERROR` line (a test id not found), else its last line."""
    assert check._telling_line(subprocess.CompletedProcess([], 4, stdout=stdout, stderr=stderr)) == shown


def test_an_error_alone_fails_the_check(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, renamed=4))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, []))
    assert check.main([]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Errors: ['renamed']"


def test_every_mutation_caught_passes(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, second=1))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, []))
    assert check.main([]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Every mutation was caught."


def test_duplicate_names_are_found_in_the_source(check):
    source = 'MUTATIONS = {\n    "a": 1,\n    "b": 2,\n    "a": 3,\n}\n'
    assert check.duplicate_names(source) == ["a"]
    assert check.duplicate_names('MUTATIONS = {"a": 1, "b": 2}\n') == []


def test_a_duplicate_name_stops_the_check_before_anything_runs(check, rule, monkeypatch, capsys):
    """A dict literal keeps only the last entry under a name, so the first would never run: the check reads its own
    source and refuses (exit 2). The mutations it would run are the test's own, over a file of its own, so a check
    that ran anyway touches nothing of the repo and fails on the assertions."""
    source = rule.parent / "mutation_check.py"
    source.write_text('MUTATIONS = {\n    "a": 1,\n    "a": 2,\n}\n')
    calls = []
    monkeypatch.setattr(check, "__file__", str(source))
    monkeypatch.setattr(check, "MUTATIONS", mutations(a=1))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, calls))
    assert check.main([]) == 2
    assert calls == []
    assert capsys.readouterr().out.startswith("DUPLICATE mutation names")


def test_the_real_mutations_have_no_duplicate_names(check):
    assert check.duplicate_names(SCRIPT.read_text()) == []


# ---- the time limit (q25) ----

def test_a_time_out_counts_as_caught_when_its_tests_pass_unmutated(check, rule, monkeypatch, capsys):
    """The tests are run once more, unmutated (the file as it was), under the clean run's own limit; they pass, so the
    break made them hang. The closing line names each mutation counted by a time-out."""
    seen = []
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, hung=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, seen))
    assert check.main([], limit=5, clean_limit=7) == 0
    assert seen == [("LIMIT = 1\n", RULE_TESTS, 5), ("LIMIT = hang\n", RULE_TESTS, 5), ("LIMIT = 0\n", RULE_TESTS, 7)]
    assert rule.read_text() == "LIMIT = 0\n"
    assert capsys.readouterr().out.splitlines() == [
        "CAUGHT first",
        "CAUGHT hung (timed out after 5 s; its tests pass unmutated)",
        "Files restored. Every mutation was caught. Timed out, counted as caught: ['hung']"]


def test_a_time_out_is_an_error_when_its_tests_run_past_the_clean_limit_unmutated_too(check, rule, monkeypatch, capsys):
    """A machine too slow for the limit, or tests that hang by themselves: the time-out proves nothing."""
    monkeypatch.setattr(check, "MUTATIONS", mutations(hung=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, [], clean={RULE_TESTS: HANG}))
    assert check.main([], limit=5, clean_limit=7) == 1
    assert capsys.readouterr().out.splitlines() == [
        "ERROR  hung: timed out after 5 s, but its tests ran past 7 s unmutated too, so the time-out proves nothing",
        "Files restored. Errors: ['hung']"]


def test_a_time_out_is_an_error_when_its_tests_fail_unmutated(check, rule, monkeypatch, capsys):
    monkeypatch.setattr(check, "MUTATIONS", mutations(hung=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, [], clean={RULE_TESTS: 1}))
    assert check.main([], limit=5, clean_limit=7) == 1
    assert capsys.readouterr().out.splitlines() == [
        "ERROR  hung: timed out after 5 s, but its tests fail unmutated too (pytest exited 1, TESTS_FAILED): "
        "ERROR: not found",
        "Files restored. Errors: ['hung']"]


def test_the_clean_run_is_made_once_for_each_set_of_target_tests(check, rule, monkeypatch, capsys):
    other = ("tests/test_other.py",)
    seen = []
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=HANG, second=HANG) | mutations(other, third=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, seen, clean={other: 1}))
    assert check.main([], limit=5, clean_limit=7) == 1
    assert seen == [("LIMIT = hang\n", RULE_TESTS, 5), ("LIMIT = 0\n", RULE_TESTS, 7), ("LIMIT = hang\n", RULE_TESTS, 5),
                    ("LIMIT = hang\n", other, 5), ("LIMIT = 0\n", other, 7)]
    assert capsys.readouterr().out.splitlines() == [
        "CAUGHT first (timed out after 5 s; its tests pass unmutated)",
        "CAUGHT second (timed out after 5 s; its tests pass unmutated)",
        "ERROR  third: timed out after 5 s, but its tests fail unmutated too (pytest exited 1, TESTS_FAILED): "
        "ERROR: not found",
        "Files restored. Errors: ['third'] Timed out, counted as caught: ['first', 'second']"]


def test_the_runs_have_the_measured_limits_unless_given_others(check, rule, monkeypatch):
    seen = []
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, hung=HANG))
    monkeypatch.setattr(check, "run_limited", fake_run(rule, seen))
    assert check.main([]) == 0
    assert [limit for _, _, limit in seen] == [check.TIME_LIMIT, check.TIME_LIMIT, check.CLEAN_LIMIT]


def test_an_interrupt_stops_the_check_with_the_file_restored(check, rule, monkeypatch):
    def run(args, limit, **popen):
        raise KeyboardInterrupt
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1))
    monkeypatch.setattr(check, "run_limited", run)
    with pytest.raises(KeyboardInterrupt):
        check.main([])
    assert rule.read_text() == "LIMIT = 0\n"


# ---- real processes from here on ----

def test_a_run_within_the_limit_returns_its_exit_code_and_output(check):
    run = check.run_limited([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
                            30)
    assert (run.returncode, run.stdout, run.stderr) == (3, "out\n", "err\n")


def test_a_run_that_fills_both_pipes_does_not_stall(check):
    """Both pipes are read while the run goes on: a run waited on first would stall once a pipe's buffer was full."""
    run = check.run_limited([sys.executable, "-c",
                             "import sys; sys.stdout.write('o' * 1_000_000); sys.stderr.write('e' * 1_000_000)"], 5)
    assert (run.returncode, len(run.stdout), len(run.stderr)) == (0, 1_000_000, 1_000_000)


def started_with_a_child(ending: str) -> str:
    """A process that starts one of its own (as tests/test_golden_90.py starts its second run), writes both pids,
    then `ending`."""
    return ("import os, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
            "open(sys.argv[1], 'w').write(f'{os.getpid()} {child.pid}')\n" + ending)


HANGS_WITH_A_CHILD = started_with_a_child("time.sleep(20)\n")
# Ends at once with exit 3, its child left holding the pipes.
ENDS_LEAVING_A_CHILD = started_with_a_child("print('done')\nsys.exit(3)\n")


def gone(pid: int, within: float = 5.0) -> bool:
    """True once no process `pid` is left; a killed process whose parent died is reaped by init, not at once."""
    end = time.monotonic() + within
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def pidfile(tmp_path):
    """Where the process writes its pid and its child's; whatever is still running when the test ends is killed."""
    path = tmp_path / "pids"
    yield path
    for pid in map(int, path.read_text().split() if path.exists() else []):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def all_gone(pidfile: Path) -> bool:
    pids = [int(pid) for pid in pidfile.read_text().split()]
    return len(pids) == 2 and all(gone(pid) for pid in pids)


def test_a_run_past_the_limit_is_killed_with_everything_it_started(check, pidfile):
    started = time.monotonic()
    assert check.run_limited([sys.executable, "-c", HANGS_WITH_A_CHILD, str(pidfile)], 1.0) is None
    assert time.monotonic() - started < 10  # the limit, not the 20 s it would hang
    assert all_gone(pidfile)


def test_a_run_that_ended_in_time_keeps_its_exit_code_though_its_child_held_the_pipes(check, pidfile):
    """The pipes stay open past the limit, held by the child; the run itself had ended, so its exit code stands."""
    run = check.run_limited([sys.executable, "-c", ENDS_LEAVING_A_CHILD, str(pidfile)], 1.0)
    assert (run.returncode, run.stdout) == (3, "done\n")
    assert all_gone(pidfile)


def test_an_interrupt_kills_the_run_with_everything_it_started(check, pidfile):
    """The run is in a session of its own, so a Ctrl-C at the terminal does not reach it: run_limited kills it."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGALRM, interrupt)
    signal.setitimer(signal.ITIMER_REAL, 1.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            check.run_limited([sys.executable, "-c", HANGS_WITH_A_CHILD, str(pidfile)], 30)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    assert all_gone(pidfile)


def test_killing_a_group_with_nothing_left_to_kill_is_no_error(check):
    """A run can end right at the limit: its group then holds only its exited, unreaped first process (macOS answers
    PermissionError), or nothing at all once that is reaped (ProcessLookupError)."""
    process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)  # ended, not reaped
    check._kill_group(process.pid)
    process.wait()
    check._kill_group(process.pid)


def test_main_over_real_pytest_stops_a_hung_run_at_the_limit(check, tmp_path, monkeypatch, capsys):
    """A break that makes the rule's test hang, run as the check runs it: stopped at a one-second limit, then the test
    run once unmutated, which passes, so the mutation is caught by its time-out."""
    (tmp_path / "rule.py").write_text("LIMIT = 0\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_rule.py").write_text("import rule\n\n\ndef test_limit():\n    assert rule.LIMIT == 0\n")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", {
        "hangs": (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", "import time\ntime.sleep(20)\nLIMIT = 0"),
    })
    started = time.monotonic()
    assert check.main([], limit=1, clean_limit=60) == 0
    assert time.monotonic() - started < 15  # the limit, not the 20 s it would hang
    assert capsys.readouterr().out.splitlines() == [
        "CAUGHT hangs (timed out after 1 s; its tests pass unmutated)",
        "Files restored. Every mutation was caught. Timed out, counted as caught: ['hangs']"]
    assert (tmp_path / "rule.py").read_text() == "LIMIT = 0\n"

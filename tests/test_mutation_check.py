"""The mutation check's runner (`scripts/mutation_check.py`): what counts as caught, its time limit, and its guard on
duplicate names.

A mutation is caught only when pytest says a test failed (exit 1). Any other non-zero exit means pytest could not run
the tests as asked: a test id that no longer exists (4), a module that no longer imports (2), no tests collected (5).
That proves nothing about the rule, so it is an error, not a catch (it happened on 2026-11-01: a renamed test's old id
passed as caught). A run still going at the time limit is killed and counts as caught (q25): a break that makes a test
hang is a break the tests noticed. `main` is driven here with a fake `subprocess.run` whose exit code the mutated file
sets, over a file of the test's own, so no real mutation runs; the one run that hangs is a real process that sleeps.
"""
import importlib.util
import signal
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "mutation_check.py"


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


def fake_pytest(rule: Path, seen: list):
    """A stand-in for subprocess.run: pytest's exit code is the number the mutated `rule` file holds."""
    def run(args, **kwargs):
        text = rule.read_text()
        seen.append(text)
        return subprocess.CompletedProcess(args, int(text.split("=")[1]), stdout="1 failed\n", stderr="ERROR: not found\n")
    return run


def mutations(**codes):
    return {name: (("rule.py", ["tests/test_rule.py"]), "LIMIT = 0", f"LIMIT = {code}") for name, code in codes.items()}


def test_main_reports_each_mutation_by_pytests_exit_and_restores_the_file(check, tmp_path, monkeypatch, capsys):
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    seen = []
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, missed=0, renamed=4, unimportable=2, killed=-9))
    monkeypatch.setattr(check.subprocess, "run", fake_pytest(rule, seen))
    assert check.main([]) == 1
    assert seen == ["LIMIT = 1\n", "LIMIT = 0\n", "LIMIT = 4\n", "LIMIT = 2\n", "LIMIT = -9\n"]  # each its own
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


def test_an_error_alone_fails_the_check(check, tmp_path, monkeypatch, capsys):
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, renamed=4))
    monkeypatch.setattr(check.subprocess, "run", fake_pytest(rule, []))
    assert check.main([]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Errors: ['renamed']"


def test_every_mutation_caught_passes(check, tmp_path, monkeypatch, capsys):
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, second=1))
    monkeypatch.setattr(check.subprocess, "run", fake_pytest(rule, []))
    assert check.main([]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Files restored. Every mutation was caught."


def test_duplicate_names_are_found_in_the_source(check):
    source = 'MUTATIONS = {\n    "a": 1,\n    "b": 2,\n    "a": 3,\n}\n'
    assert check.duplicate_names(source) == ["a"]
    assert check.duplicate_names('MUTATIONS = {"a": 1, "b": 2}\n') == []


def test_a_duplicate_name_stops_the_check_before_anything_runs(check, tmp_path, monkeypatch, capsys):
    """A dict literal keeps only the last entry under a name, so the first would never run: the check reads its own
    source and refuses (exit 2). The mutations it would run are the test's own, over a file of its own, so a check
    that ran anyway touches nothing of the repo and fails on the assertions."""
    source = tmp_path / "mutation_check.py"
    source.write_text('MUTATIONS = {\n    "a": 1,\n    "a": 2,\n}\n')
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    calls = []
    monkeypatch.setattr(check, "__file__", str(source))
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(a=1))
    monkeypatch.setattr(check.subprocess, "run", fake_pytest(rule, calls))
    assert check.main([]) == 2
    assert calls == []
    assert capsys.readouterr().out.startswith("DUPLICATE mutation names")


def test_the_real_mutations_have_no_duplicate_names(check):
    assert check.duplicate_names(SCRIPT.read_text()) == []


REAL_RUN = subprocess.run
HANG = [sys.executable, "-c", "import time; time.sleep(30)"]  # a pytest stuck on a planted pause, as far as the check sees


def test_a_run_past_the_time_limit_is_killed_and_counts_as_caught(check, tmp_path, monkeypatch, capsys):
    """A break that makes a test hang is a break the tests noticed: the run is stopped at the limit, its process is
    killed and waited for (not left running), the mutation is CAUGHT and says why, and the next mutation runs. The
    hanging run is a real process given a half-second limit; the other is faked as above."""
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    limits, started = [], []

    class Recorded(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    def run(args, **kwargs):
        limits.append(kwargs.get("timeout"))
        assert kwargs.get("timeout") == 0.5, "the run was not given the limit"  # fails at once instead of in 30 s
        if rule.read_text() == "LIMIT = 9\n":
            return REAL_RUN(HANG, **kwargs)
        return fake_pytest(rule, [])(args, **kwargs)

    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(hangs=9, caught=1))
    monkeypatch.setattr(check.subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", Recorded)
    assert check.main([], limit=0.5) == 0
    assert limits == [0.5, 0.5]
    assert [process.args for process in started] == [HANG]
    assert started[0].returncode == -signal.SIGKILL  # killed at the limit and waited for
    assert rule.read_text() == "LIMIT = 0\n"
    assert capsys.readouterr().out.splitlines() == ["CAUGHT hangs (timed out after 0.5 s)", "CAUGHT caught",
                                                    "Files restored. Every mutation was caught."]


def limited(rule: Path, limits: list):
    """fake_pytest, recording the time limit each run is given."""
    def run(args, **kwargs):
        limits.append(kwargs.get("timeout"))
        return fake_pytest(rule, [])(args, **kwargs)
    return run


def test_a_run_under_the_time_limit_is_judged_by_its_exit_as_before(check, tmp_path, monkeypatch, capsys):
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    limits = []
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(caught=1, missed=0, renamed=4))
    monkeypatch.setattr(check.subprocess, "run", limited(rule, limits))
    assert check.main([], limit=0.5) == 1
    assert limits == [0.5, 0.5, 0.5]
    assert capsys.readouterr().out.splitlines() == [
        "CAUGHT caught", "MISSED missed",
        "ERROR  renamed: pytest exited 4 (USAGE_ERROR), not a test failure: ERROR: not found",
        "Files restored. Missed: ['missed'] Errors: ['renamed']"]


def test_every_run_has_the_measured_limit_unless_given_another(check, tmp_path, monkeypatch):
    rule = tmp_path / "rule.py"
    rule.write_text("LIMIT = 0\n")
    limits = []
    monkeypatch.setattr(check, "ROOT", tmp_path)
    monkeypatch.setattr(check, "MUTATIONS", mutations(first=1, second=1))
    monkeypatch.setattr(check.subprocess, "run", limited(rule, limits))
    assert check.main([]) == 0
    assert limits == [check.TIME_LIMIT, check.TIME_LIMIT]

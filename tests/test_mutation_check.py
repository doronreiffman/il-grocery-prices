"""The mutation check's runner (`scripts/mutation_check.py`): what counts as caught, and its guard on duplicate names.

A mutation is caught only when pytest says a test failed (exit 1). Any other non-zero exit means pytest could not run
the tests as asked: a test id that no longer exists (4), a module that no longer imports (2), no tests collected (5).
That proves nothing about the rule, so it is an error, not a catch (it happened on 2026-11-01: a renamed test's old id
passed as caught). `main` is driven here with a fake `subprocess.run` whose exit code the mutated file sets, over a
file of the test's own, so no real mutation runs.
"""
import importlib.util
import subprocess
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

"""The full suite runs under a time limit on the Mac: `perl -e 'alarm shift; exec @ARGV' 1400 <python> -m pytest ...`,
a SIGALRM timer that survives the exec into pytest. A process has one such timer, and one test arms it for itself
(tests/test_mutation_check.py, `test_an_interrupt_kills_the_run_with_everything_it_started`). These tests run that one
test in a Python of its own, its timer armed right before the test starts, and read what the timer holds after it
(q52: the test used to clear it, so every full run after it had no limit).
"""
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTERRUPT_TEST = "tests/test_mutation_check.py::test_an_interrupt_kills_the_run_with_everything_it_started"

# argv[1]: the limit in seconds, or "none" for a run with no limit (as in CI); argv[2]: the test to run.
UNDER_A_LIMIT = """
import signal, sys, time
import pytest

class Limit:
    armed = None

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_call(self, item):
        if sys.argv[1] != "none":
            signal.setitimer(signal.ITIMER_REAL, float(sys.argv[1]))
        Limit.armed = time.monotonic()

code = pytest.main(["-p", "no:cacheprovider", sys.argv[2]], plugins=[Limit()])
left = signal.getitimer(signal.ITIMER_REAL)[0]
print(f"code={int(code)} left={left:.3f} spent={time.monotonic() - Limit.armed:.3f}")
"""


def _run(limit: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", UNDER_A_LIMIT, limit, INTERRUPT_TEST],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def _reading(run: subprocess.CompletedProcess) -> dict[str, float]:
    assert run.returncode == 0, run.stdout + run.stderr
    return {key: float(value) for key, value in (part.split("=") for part in run.stdout.splitlines()[-1].split())}


def test_the_run_s_limit_is_still_running_after_the_test_less_the_time_spent():
    reading = _reading(_run("600"))
    assert reading["code"] == 0
    assert abs(reading["left"] - (600 - reading["spent"])) < 0.25  # neither cleared (0) nor given back the test's second


def test_a_limit_that_ran_out_during_the_test_still_stops_the_run():
    run = _run("0.2")  # the test's own 1 s timer outlasts it
    assert run.returncode == -signal.SIGALRM, run.stdout + run.stderr


def test_a_run_with_no_limit_is_given_none():
    reading = _reading(_run("none"))
    assert (reading["code"], reading["left"]) == (0, 0)

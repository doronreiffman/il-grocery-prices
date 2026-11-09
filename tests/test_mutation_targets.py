"""Every planted bug in scripts/mutation_check.py still points at real code and real tests.

The full mutation check runs weekly (.github/workflows/mutations.yml), so a mutation made stale by a change would
otherwise surface days later. Each push runs these two checks with the tests instead: a mutation's original text is
found exactly once in its file (the check's own STALE rule), and every test file and `file::test` id it names exists.
Kept out of tests/test_mutation_check.py on purpose: the check's own mutations name that file, and a staleness test
there would fail under each of them, catching them for the wrong reason. A text that now sits in other code still
counts once and passes here; only the weekly run shows that.
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mutations():
    spec = importlib.util.spec_from_file_location("mutation_check", ROOT / "scripts" / "mutation_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MUTATIONS


def test_every_mutation_finds_its_text_exactly_once():
    stale = [name for name, ((path, _), old, _) in _mutations().items() if (ROOT / path).read_text().count(old) != 1]
    assert stale == []


def test_every_test_a_mutation_names_exists():
    targets = {test for (_, tests), _, _ in _mutations().values() for test in tests}
    missing = [test for test in sorted(targets) if not (ROOT / test.split("::")[0]).is_file()]
    for test in sorted(target for target in targets if "::" in target):
        path, *parts = test.split("::")
        name = re.sub(r"\[.*\]$", "", parts[-1])
        if (ROOT / path).is_file() and not re.search(rf"^\s*def {re.escape(name)}\(", (ROOT / path).read_text(), re.M):
            missing.append(test)
    assert missing == []

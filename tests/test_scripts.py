"""The hand scripts, run against a stand-in `aws` that records each call and answers the identity check."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARN = "arn:aws:iam::137953273942:user/doron-admin"
# A stand-in for the AWS CLI: each call's arguments one a line, then a line "--"; the identity check answers the
# expected user, and the site stack is not there yet (AWS's words for that, as sync.sh quotes them).
FAKE_AWS = f"""#!/bin/sh
for arg in "$@"; do printf '%s\\n' "$arg"; done >> "$AWS_CALLS"
echo -- >> "$AWS_CALLS"
case "$1" in
  sts) echo {ARN} ;;
  cloudformation) echo "Stack with id il-grocery-prices-site does not exist" >&2; exit 254 ;;
esac
"""


def _sync(tmp_path: Path, day: str) -> list[list[str]]:
    """Run sync.sh for `day` with the stand-in on PATH; each AWS call's arguments."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "aws").write_text(FAKE_AWS)
    (bin_dir / "aws").chmod(0o755)
    calls = tmp_path / "calls"
    env = os.environ | {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "AWS_CALLS": str(calls),
                        "TMPDIR": str(tmp_path)}
    subprocess.run(["sh", str(ROOT / "scripts" / "sync.sh"), day], env=env, check=True, capture_output=True)
    return [call.strip("\n").split("\n") for call in calls.read_text().split("--\n") if call.strip()]


def test_sync_sh_copies_the_days_promotion_files_with_its_price_files_and_store_lists(tmp_path):
    calls = _sync(tmp_path, "2026-11-07")
    [raw] = [call for call in calls if call[:2] == ["s3", "sync"] and call[2].endswith("/raw/")]
    includes = [raw[i + 1] for i, arg in enumerate(raw) if arg == "--include"]
    assert raw[raw.index("--exclude") + 1] == "*"
    assert includes == ["chain=*/date=2026-11-07/PriceFull*", "chain=*/date=2026-11-07/pricefull*",
                        "chain=*/date=2026-11-07/PromoFull*", "chain=*/date=2026-11-07/promofull*",
                        "chain=*/date=2026-11-07/Stores*"]
    assert calls[0][:2] == ["sts", "get-caller-identity"]  # the identity is checked before anything is read

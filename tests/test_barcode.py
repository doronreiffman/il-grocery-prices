"""Barcodes: the digits a code is compared by, and whether its GS1 check digit holds."""
import pytest

from basket.barcode import is_gs1, normalize


@pytest.mark.parametrize("code, norm", [
    ("7290000066738", "7290000066738"), ("0012345678905", "12345678905"), (" 96385074 ", "96385074"),
    ("0000", None), ("", None), ("72-9000", None),
    ("٧٢٩٠٠٠٠٠٦٦٧٣٨", None),  # Arabic-Indic digits: str.isdigit() says yes, the rule says no
])
def test_normalize(code, norm):
    assert normalize(code) == norm


@pytest.mark.parametrize("code, ok", [
    ("7290000066738", True), ("4006381333931", True), ("96385074", True), ("012345678905", True),
    ("12345678905", True), ("2000000000015", True), ("0000096385074", True),
    ("7290000000100", False), ("1501", False), ("725", False), ("7290111111111", False),
    ("72900000000221", False), ("1234567", False), ("123456789012345", False),
    # the length bounds on their own: each of these has a valid check digit, only its length is wrong or on the edge
    ("1234565", False), ("123456789012343", False), ("12345678901231", True),
])
def test_is_gs1(code, ok):
    assert is_gs1(code) is ok

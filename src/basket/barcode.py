"""Barcodes: the digits a product is matched by, and whether a code is a real GS1 barcode.

A product is a barcode. Two codes name the same product when their digits agree with leading zeros
stripped, so a 12-digit UPC-A and the 13-digit EAN made of it with a leading zero are one product.
A code is a real barcode, and not a chain's own internal code, when it has 8 to 14 digits once the
leading zeros are gone and its last digit is the GS1 check digit: counting left from that digit, the
digits are weighted 3, 1, 3, 1, ... and the weighted sum plus the check digit ends in 0.

Digits are the ASCII 0 to 9 only: `str.isdigit()` and `\\d` also take other scripts' digits, which
would let a code in Arabic-Indic numerals through as a barcode.
"""
import re

_DIGITS = re.compile(r"[0-9]+")


def normalize(code: str) -> str | None:
    """The code's digits with leading zeros stripped, or None when it has no ASCII digits to match by.

    None for an empty string, for a character that is not 0 to 9 (a hyphen, a letter, a digit of
    another script), and for a code of zeros only."""
    digits = code.strip()
    if not _DIGITS.fullmatch(digits):
        return None
    significant = digits.lstrip("0")
    return significant or None


def is_gs1(code: str) -> bool:
    """True when `normalize(code)` succeeds, has 8 to 14 digits and the GS1 check digit holds."""
    digits = normalize(code)
    if digits is None or not 8 <= len(digits) <= 14:
        return False
    *body, check = digits
    weighted = sum(int(digit) * (3 if place % 2 == 0 else 1) for place, digit in enumerate(reversed(body)))
    return (weighted + int(check)) % 10 == 0

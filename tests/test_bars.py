"""The barcode drawn from a product's own digits (q36): the tables, the known patterns, the refusals."""
import random
import re

import pytest

from shopper import bars

# GS1's three tables as printed, written out in full and kept apart from the module's own (which flips and reverses).
L_TABLE = ("0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011")
G_TABLE = ("0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111")
R_TABLE = ("1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100")
PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


def check_digit(body: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def make(length: int, rng: random.Random) -> str:
    body = "2" + "".join(rng.choice("0123456789") for _ in range(length - 2))
    return body + check_digit(body)


def test_the_module_tables_match_gs1s_printed_ones():
    assert bars._L == L_TABLE
    assert bars._G == G_TABLE
    assert bars._R == R_TABLE
    assert bars._PARITY == PARITY


def test_a_real_ean13_gives_the_pattern_worked_from_the_printed_tables():
    # 4006381333931: first digit 4, parity LGLLGG over 0 0 6 3 8 1, then 3 3 3 9 3 1 in R codes.
    expected = ("101"
                "0001101" "0100111" "0101111" "0111101" "0001001" "0110011"
                "01010"
                "1000010" "1000010" "1000010" "1110100" "1000010" "1100110"
                "101")
    assert bars.modules("4006381333931") == expected


@pytest.mark.parametrize("code, expected", [
    ("2000000000046", "10100011010001101010011101001110001101010011101010111001011100101110010111001010111001010000101"),
    ("200000000004", "10100100110001101000110100011010001101000110101010111001011100101110010111001011100101011100101"),
    ("20000004", "1010010011000110100011010001101010101110010111001011100101011100101"),
])
def test_known_codes_give_their_modules(code, expected):
    assert bars.modules(code) == expected


def test_every_pattern_has_its_length_and_guards():
    rng = random.Random(36)
    for length, size, centre in ((13, 95, 45), (8, 67, 31)):
        for _ in range(200):
            code = make(length, rng)
            pattern = bars.modules(code)
            assert len(pattern) == size
            assert pattern[:3] == pattern[-3:] == "101"
            assert pattern[centre:centre + 5] == "01010"


def decode(pattern: str) -> str:
    """The test's own decoder: the tables read the other way, the first digit from the left half's parity."""
    if len(pattern) == 67:
        left = [pattern[3 + 7 * i:10 + 7 * i] for i in range(4)]
        right = [pattern[36 + 7 * i:43 + 7 * i] for i in range(4)]
        return "".join(str(L_TABLE.index(each)) for each in left) + "".join(str(R_TABLE.index(each)) for each in right)
    left = [pattern[3 + 7 * i:10 + 7 * i] for i in range(6)]
    right = [pattern[50 + 7 * i:57 + 7 * i] for i in range(6)]
    parity = "".join("L" if each in L_TABLE else "G" for each in left)
    digits = [(L_TABLE if kind == "L" else G_TABLE).index(each) for kind, each in zip(parity, left)]
    return str(PARITY.index(parity)) + "".join(map(str, digits)) + "".join(str(R_TABLE.index(each)) for each in right)


def test_each_pattern_decodes_to_its_digits():
    rng = random.Random(36)
    for length in (13, 12, 8):
        for _ in range(200):
            code = make(length, rng)
            assert decode(bars.modules(code)) == ("0" + code if length == 12 else code)


@pytest.mark.parametrize("code", [
    "2000000000047",    # the check digit fails
    "2000008",          # 7 digits, check digit valid
    "200000008",        # 9
    "2000000004",       # 10
    "20000000008",      # 11
    "20000000000004",   # 14
    "20000000000A6",
    "٢٠٠٠٠٠٠٠٠٠٠٤٦",
    "",
    " ",
    " 2000000000046",
])
def test_a_code_that_is_not_a_barcode_gets_no_bars(code):
    assert bars.modules(code) == bars.drawing(code) == bars.mark(code) == ""


def test_the_refusal_cases_have_valid_check_digits():
    for code in ("2000008", "200000008", "2000000004", "20000000008", "20000000000004"):
        assert check_digit(code[:-1]) == code[-1], code


def test_the_drawing_is_one_dashed_path():
    assert bars.drawing("2000000000046") == (
        '<svg class="defs" aria-hidden="true"><defs><path id="ean" d="M0 .5h95" stroke-dasharray="1 1 1 3 2 1 1 3 2 1 1 1 1 2 3 1 1 2 3 3 2 1 1 1 1 2 3 1 1 1 1 1 3 2 1 1 3 2 1 1 3 2 1 1 3 2 1 1 1 1 3 2 1 1 1 4 1 1 1"/></defs></svg>')
    assert len(bars.drawing("2000000000046").encode()) == 222
    rng = random.Random(36)
    for length in (13, 12, 8):
        for _ in range(20):
            code = make(length, rng)
            pattern = bars.modules(code)
            dashes = [int(each) for each in re.search(r'stroke-dasharray="([^"]+)"', bars.drawing(code)).group(1).split()]
            assert sum(dashes) == len(pattern)
            rebuilt = "".join(("1" if i % 2 == 0 else "0") * width for i, width in enumerate(dashes))
            assert rebuilt == pattern
            assert f'd="M0 .5h{len(pattern)}"' in bars.drawing(code)


def test_each_label_shows_the_drawing_by_reference():
    assert bars.mark("2000000000046") == (
        '<div class="code" aria-hidden="true"><svg viewBox="0 0 95 1" preserveAspectRatio="none"><use href="#ean"/></svg><small>2000000000046</small></div>')
    assert len(bars.mark("2000000000046").encode()) == 146
    assert bars.mark("20000004") == (
        '<div class="code" aria-hidden="true"><svg class="short" viewBox="0 0 67 1" preserveAspectRatio="none"><use href="#ean"/></svg><small>20000004</small></div>')
    assert bars.mark("200000000004").count("viewBox=\"0 0 95 1\"") == 1

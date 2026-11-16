"""A product's barcode drawn as SVG, from its own digits.

The encoding is GS1's. Each digit is seven modules (1 a bar, 0 a space). The L codes of 0 to 9 are
written out below; a G code is the R code reversed, and an R code is the L code with each module
flipped. EAN-13 is `101`, the six left digits, `01010`, the six right digits in R codes, `101`
(95 modules); the first digit is not drawn but picks the parity (L or G) of the left six. A UPC-A
of 12 digits is drawn as the EAN-13 made of it with a leading 0. EAN-8 is `101`, four L digits,
`01010`, four R digits, `101` (67 modules).

The input is a code as `basket.barcode.normalize` gives it, with no leading zeros (an EAN-8 that
starts with 0 gets no bars). Nothing that looks like a barcode and is not one is ever drawn: a code
with other than 8, 12 or 13 ASCII digits, or whose GS1 check digit fails (`basket.barcode.is_gs1`),
gets no bars at all, and every function here returns "".

The bars are always dark on a white plate (the stylesheet's `--bars` on `--plate`, in both themes):
a scanner needs dark bars on a light ground, so the dark theme does not invert them.

The bars are drawn once a page as one dashed path (`drawing`); each label shows it by reference
(`mark`).
"""
from itertools import groupby

from basket.barcode import is_gs1

_L = ("0001101", "0011001", "0010011", "0111101", "0100011",
      "0110001", "0101111", "0111011", "0110111", "0001011")
_R = tuple(code.translate(str.maketrans("01", "10")) for code in _L)
_G = tuple(code[::-1] for code in _R)
_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
           "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")
_EDGE = "101"
_CENTRE = "01010"


def modules(code: str) -> str:
    """The bars as "1" (bar) and "0" (space): 95 for an EAN-13 or a UPC-A, 67 for an EAN-8, "" for any other code."""
    if not (code.isdigit() and is_gs1(code)):
        return ""
    if len(code) == 8:
        digits = [int(each) for each in code]
        return _EDGE + "".join(_L[each] for each in digits[:4]) + _CENTRE + "".join(_R[each] for each in digits[4:]) + _EDGE
    if len(code) not in (12, 13):
        return ""
    digits = [int(each) for each in code.zfill(13)]
    left = "".join((_L, _G)[parity == "G"][each] for parity, each in zip(_PARITY[digits[0]], digits[1:7]))
    return _EDGE + left + _CENTRE + "".join(_R[each] for each in digits[7:]) + _EDGE


def drawing(code: str) -> str:
    """The once-a-page definition: one path whose dashes are the runs of the bars and spaces, "" with no bars."""
    bars = modules(code)
    if not bars:
        return ""
    dashes = " ".join(str(len(list(run))) for _, run in groupby(bars))
    return (f'<svg class="defs" aria-hidden="true"><defs><path id="ean" d="M0 .5h{len(bars)}" '
            f'stroke-dasharray="{dashes}"/></defs></svg>')


def mark(code: str) -> str:
    """One label's barcode: the drawing shown by reference, with the digits under it, "" with no bars."""
    bars = modules(code)
    if not bars:
        return ""
    short = ' class="short"' if len(bars) == 67 else ""
    return (f'<div class="code" aria-hidden="true"><svg{short} viewBox="0 0 {len(bars)} 1" preserveAspectRatio="none">'
            f'<use href="#ean"/></svg><small>{code}</small></div>')

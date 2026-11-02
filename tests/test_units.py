"""Sizes: a product's quantity and unit as the price files state them, in grams-or-millilitres or units (B7)."""
from decimal import Decimal

import pytest

from basket.units import Size, normal_size, plain


@pytest.mark.parametrize("q, u, size", [
    ("1", "ליטר", Size(Decimal(1000), "gml")), ("500.00", "גרם", Size(Decimal(500), "gml")),
    ("1.5", "ק\"ג", Size(Decimal(1500), "gml")), ("12", "יחידה", Size(Decimal(12), "unit")),
    ("1", "לא ידוע", None), ("", "גרם", None), ("0", "גרם", None), ("abc", "גרם", None), ("1", "", None),
    # the rest of the vocabulary of 2026-11-02
    ("6.00", "יחידות", Size(Decimal(6), "unit")), ("750.00", "מיליליטר", Size(Decimal(750), "gml")),
    ("0.25", "קילוגרם", Size(Decimal(250), "gml")), ("2", "קילו", Size(Decimal(2000), "gml")),
    ("330", "מ\"ל", Size(Decimal(330), "gml")), ("4", "יח'", Size(Decimal(4), "unit")),
    ("150.00", "מטרים", None),  # metres: a length, not stated
    ("0.00", "יחידות", None),  # the published form of a zero quantity
    (" 500 ", " גרם ", Size(Decimal(500), "gml")),  # spaces around either are noise
    ("NaN", "גרם", None), ("Infinity", "ליטר", None), ("-1", "גרם", None),
])
def test_normal_size(q, u, size):
    assert normal_size(q, u) == size


def test_a_litre_equals_a_thousand_grams():
    assert normal_size("1", "ליטר") == normal_size("1000", "גרם")


def test_a_unit_is_not_a_gram():
    assert normal_size("12", "יחידות") != normal_size("12", "גרם")


def test_amounts_are_plain():
    assert [str(normal_size(q, u).amount) for q, u in (("1.5", "ק\"ג"), ("500.00", "גרם"), ("0.75", "ליטר"))] \
        == ["1500", "500", "750"]


def test_plain():
    assert [plain(Decimal(v)) for v in ("1000", "1.50", "1E+3")] == ["1000", "1.5", "1000"]

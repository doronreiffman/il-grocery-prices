"""The basket file: its list of barcodes is read, and a list that breaks a rule is refused."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from basket.barcode import is_gs1
from basket.basket_file import BadBasket, Basket, BasketItem, load_basket
from basket.units import Size

FIXTURE = Path(__file__).parent / "baskets" / "basket-test.json"
MILK = "2000000000015"


def with_check_digit(body: str) -> str:
    """`body` followed by its GS1 check digit."""
    weighted = sum(int(digit) * (3 if place % 2 == 0 else 1) for place, digit in enumerate(reversed(body)))
    return body + str(-weighted % 10)


def item(code: str = MILK, **changes) -> dict:
    """One item of the file's layout, with `changes` laid over it."""
    return {"code": code, "name_en": "Test milk", "name_he": "חלב בדיקה",
            "size": {"amount": "1000", "kind": "gml"}, "category": "dairy"} | changes


def codes(count: int) -> list[str]:
    """`count` valid, distinct codes: a fixed prefix, two digits and the check digit."""
    return [with_check_digit(f"20000000001{number:02d}") for number in range(count)]


def write(tmp_path: Path, items: list[dict], **changes) -> Path:
    document = {"version": "v1", "since": "2026-11-02", "selection_day": "2026-11-02", "items": items} | changes
    path = tmp_path / "basket.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_helper_makes_real_barcodes():
    assert all(is_gs1(code) for code in codes(100))


def test_loads_the_fixture():
    basket = load_basket(FIXTURE, min_items=1)
    assert (basket.version, basket.since, basket.selection_day) == ("v1", date(2026, 11, 2), date(2026, 11, 2))
    assert [(i.code, i.name_en, i.size, i.category) for i in basket.items] == [
        ("2000000000015", "Test milk 1 L", Size(Decimal(1000), "gml"), "dairy"),
        ("2000000000022", "Test pasta 500 g", Size(Decimal(500), "gml"), "pantry"),
        ("2000000000039", "Test eggs ×12", Size(Decimal(12), "unit"), "dairy"),
    ]
    assert basket.items[0].name_he == "חלב בדיקה 1 ל'"
    assert isinstance(basket, Basket) and isinstance(basket.items, tuple) and isinstance(basket.items[0], BasketItem)


def test_coverage_is_kept_as_given_and_may_be_absent():
    milk, pasta, _ = load_basket(FIXTURE, min_items=1).items
    assert milk.coverage == {"shufersal": "0.93", "ramilevy": "0.88"}
    assert pasta.coverage == {}


def test_items_keep_the_order_of_the_file(tmp_path):
    listed = codes(30)[::-1]
    basket = load_basket(write(tmp_path, [item(code) for code in listed]))
    assert [i.code for i in basket.items] == listed


def test_rejects_a_bad_check_digit(tmp_path):
    path = write(tmp_path, [item("7290000000100")])
    with pytest.raises(BadBasket, match="7290000000100"):
        load_basket(path, min_items=1)


def test_rejects_duplicates_across_leading_zeros(tmp_path):
    path = write(tmp_path, [item("2000000000015"), item("02000000000015")])
    with pytest.raises(BadBasket, match="02000000000015"):
        load_basket(path, min_items=1)


def test_rejects_an_unknown_kind(tmp_path):
    path = write(tmp_path, [item(size={"amount": "1", "kind": "kg"})])
    with pytest.raises(BadBasket, match=MILK):
        load_basket(path, min_items=1)


@pytest.mark.parametrize("field", ["name_en", "name_he"])
@pytest.mark.parametrize("name", ["", "   "])
def test_rejects_an_empty_name(tmp_path, field, name):
    path = write(tmp_path, [item(**{field: name})])
    with pytest.raises(BadBasket, match=MILK):
        load_basket(path, min_items=1)


def test_rejects_24_items_at_the_default_floor(tmp_path):
    path = write(tmp_path, [item(code) for code in codes(24)])
    with pytest.raises(BadBasket, match="24"):
        load_basket(path)


@pytest.mark.parametrize("count", [25, 40])
def test_accepts_the_limits_themselves(tmp_path, count):
    assert len(load_basket(write(tmp_path, [item(code) for code in codes(count)])).items) == count


def test_rejects_41_items(tmp_path):
    path = write(tmp_path, [item(code) for code in codes(41)])
    with pytest.raises(BadBasket, match="41"):
        load_basket(path)


def test_the_limits_are_arguments(tmp_path):
    path = write(tmp_path, [item(code) for code in codes(5)])
    assert len(load_basket(path, min_items=5, max_items=5).items) == 5
    with pytest.raises(BadBasket):
        load_basket(path, min_items=6)
    with pytest.raises(BadBasket):
        load_basket(path, max_items=4)


@pytest.mark.parametrize("changes", [
    {"size": {"amount": "abc", "kind": "gml"}}, {"size": {"amount": "NaN", "kind": "gml"}},
    {"size": {"amount": "0", "kind": "gml"}}, {"size": {"amount": "-5", "kind": "gml"}},
    {"size": {"amount": 1000, "kind": "gml"}},  # a number, not the string the file keeps amounts in
    {"size": {"kind": "gml"}}, {"size": "1 L"}, {"name_en": None}, {"category": 3},
    {"coverage": ["shufersal"]}, {"code": 2000000000015},
])
def test_rejects_an_item_that_is_not_in_the_layout(tmp_path, changes):
    path = write(tmp_path, [item(**changes)])
    with pytest.raises(BadBasket, match="item"):
        load_basket(path, min_items=1)


def test_rejects_an_item_missing_a_field(tmp_path):
    without_category = {key: value for key, value in item().items() if key != "category"}
    with pytest.raises(BadBasket, match=MILK):
        load_basket(write(tmp_path, [without_category]), min_items=1)


@pytest.mark.parametrize("changes", [
    {"since": "yesterday"}, {"selection_day": "2026-13-01"}, {"version": 1}, {"items": "none"}, {"items": 5}, {"items": [3]},
])
def test_rejects_a_file_that_is_not_in_the_layout(tmp_path, changes):
    document = {"items": [item()]} | changes
    path = write(tmp_path, document.pop("items"), **document)
    with pytest.raises(BadBasket):
        load_basket(path, min_items=1)


def test_rejects_a_file_missing_a_field(tmp_path):
    path = write(tmp_path, [item()])
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["selection_day"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BadBasket, match="selection_day"):
        load_basket(path, min_items=1)


def test_rejects_text_that_is_not_json(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(BadBasket):
        load_basket(path, min_items=1)


def test_amounts_are_plain(tmp_path):
    basket = load_basket(write(tmp_path, [item(size={"amount": "1000.00", "kind": "gml"})]), min_items=1)
    assert str(basket.items[0].size.amount) == "1000"


def test_v1_basket_loads():
    basket = load_basket(Path(__file__).parent.parent / "basket" / "v1.json")  # the default limits, 25 to 40
    assert len(basket.items) == 32
    assert basket.version == "v1"
    assert basket.since == date(2026, 11, 2)
    assert all(is_gs1(item.code) for item in basket.items)

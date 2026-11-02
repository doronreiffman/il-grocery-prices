"""Candidates: the codes all five chains stock widely in one agreeing size, and the table they go to."""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from basket.barcode import is_gs1, normalize
from basket.candidates import Candidate, candidates, main, write_candidates_csv
from basket.chains import SLUGS
from basket.extract import Row, table_path, write_table
from basket.rules import apply_filters, open_day
from basket.units import Size

DAY = date(2026, 11, 2)
STORES = [str(number) for number in range(1, 11)]  # ten stores a chain: 80% is eight of them
WITH_FILE = {slug: len(STORES) for slug in SLUGS}
A, B, C, D, E, F, G, H = ("7290000000107", "7290000000114", "7290000000121", "7290000000138",
                          "7290000000145", "7290000000100", "7290000000152", "7290000000169")
assert not is_gs1(F) and all(is_gs1(code) for code in (A, B, C, D, E, G, H))
LITRE, ML_1000, G_500, KG_1 = ("1", "ליטר"), ("1000", "מיליליטר"), ("500", "גרם"), ("1", "קילוגרם")
ONE_UNIT, UNKNOWN = ("1", "יחידות"), ("0", "לא ידוע")
# A's names: Shufersal's most common string is not the first in order; Rami Levy's two tie, the later one first
A_NAMES = {"shufersal": ["חלב תנובה 1 ל"] * 6 + ["חלב 1 ליטר"] * 4, "ramilevy": ["חלב ב"] * 5 + ["חלב א"] * 5}


def row(store: str, code: str, price: str, size: tuple[str, str], name: str = "מוצר") -> Row:
    """One row of a day's table; `size` is the (quantity, unit) the file states."""
    quantity, unit = size
    return Row(store=store, sub_chain="1", code=code, code_norm=normalize(code), gs1=is_gs1(code), name=name,
               price=Decimal(price), quantity=quantity, unit=unit, unit_of_measure="", updated="2026-11-02 08:00",
               file=f"PriceFull-{store}.gz")


def listed(code: str, size: tuple[str, str], stores: list[str] = STORES, base: str = "5.00",
           names: list[str] | None = None) -> list[Row]:
    """`code` at each of `stores`, store n at `base` + n x 0.10, named `names[n - 1]` (or "מוצר")."""
    return [row(store, code, str(Decimal(base) + Decimal("0.10") * int(store)), size,
                names[int(store) - 1] if names else "מוצר") for store in stores]


def synthetic_day() -> dict[str, list[Row]]:
    """Five chains of ten stores. A everywhere in one size (1 litre, 1000 ml) -> in; B missing at Yochananof;
    C at half of Carrefour's stores; D at 500 g in two chains, 1 kg in three; E at 500 g in two chains, unknown in
    three; F not a GS1 code; G at exactly 80% of Rami Levy's stores -> in; H at 500 g in three chains, one unit in
    two -> in."""
    chains = {}
    for index, slug in enumerate(SLUGS):
        rows = listed(H, G_500 if index < 3 else ONE_UNIT)  # first, so the table's order is not the code order
        rows += listed("0" + A if slug == "osherad" else A, LITRE if index < 2 else ML_1000, base=f"{5 + index}.00",
                       names=A_NAMES.get(slug, ["חלב " + slug] * len(STORES)))
        rows += listed(B, G_500) if slug != "yochananof" else []
        rows += listed(C, G_500, STORES[:5] if slug == "carrefour" else STORES)
        rows += listed(D, G_500 if index < 2 else KG_1)
        rows += listed(E, G_500 if index < 2 else UNKNOWN)
        rows += listed(F, G_500)
        rows += listed(G, G_500, STORES[:8] if slug == "ramilevy" else STORES)
        chains[slug] = rows
    return chains


@pytest.fixture(scope="module")
def found(tmp_path_factory) -> list[Candidate]:
    tables = tmp_path_factory.mktemp("day") / "tables"
    for slug, rows in synthetic_day().items():
        write_table(rows, table_path(tables, slug, DAY))
    with open_day(tables, DAY, SLUGS) as con:
        apply_filters(con, {slug: set(STORES) for slug in SLUGS}, {slug: frozenset() for slug in SLUGS})
        return candidates(con, WITH_FILE)


def by_code(found: list[Candidate]) -> dict[str, Candidate]:
    return {candidate.code: candidate for candidate in found}


def test_candidates_are_the_codes_passing_every_rule_sorted_by_code(found):
    assert [candidate.code for candidate in found] == [A, G, H]


def test_a_code_everywhere_in_one_size_is_a_candidate_with_its_names_coverage_and_medians(found):
    assert by_code(found)[A] == Candidate(
        code=A,  # Osher Ad's "0" + A is the same code
        names={"shufersal": "חלב תנובה 1 ל", "ramilevy": "חלב א", "osherad": "חלב osherad",
               "carrefour": "חלב carrefour", "yochananof": "חלב yochananof"},
        size=Size(Decimal("1000"), "gml"),  # 1 litre and 1000 ml are one size
        coverage={slug: Decimal(1) for slug in SLUGS},
        medians={"shufersal": Decimal("5.55"), "ramilevy": Decimal("6.55"), "osherad": Decimal("7.55"),
                 "carrefour": Decimal("8.55"), "yochananof": Decimal("9.55")})


@pytest.mark.parametrize("code", [B, C, D, E, F], ids=[
    "missing at one chain", "at half of one chain's stores", "two chains state 500 g, three 1 kg",
    "two chains state a size", "not a GS1 code"])
def test_a_code_breaking_a_rule_is_out(found, code):
    assert code not in by_code(found)


def test_exactly_the_share_is_enough(found):
    assert by_code(found)[G].coverage["ramilevy"] == Decimal("0.8")


def test_one_unit_states_no_size_and_three_stating_chains_are_enough(found):
    assert by_code(found)[H].size == Size(Decimal("500"), "gml")


def test_names_are_the_most_common_string_per_chain(found):
    names = by_code(found)[A].names
    assert names["shufersal"] == "חלב תנובה 1 ל"  # six rows against four, though "חלב 1 ליטר" comes first in order
    assert names["ramilevy"] == "חלב א"  # five rows each: the first in order, not the first seen


def test_csv_columns(tmp_path):
    candidate = Candidate(
        code=A, names={slug: "שם " + slug for slug in reversed(SLUGS)}, size=Size(Decimal("1000"), "gml"),
        coverage={"yochananof": Decimal(1), "carrefour": Decimal(2) / 3, "osherad": Decimal("0.8"),
                  "ramilevy": Decimal("0.999"), "shufersal": Decimal(1)},
        medians={"yochananof": Decimal("5.55"), "carrefour": Decimal("5.55"), "osherad": Decimal("5.55"),
                 "ramilevy": Decimal("12.075"), "shufersal": Decimal("5.90")})
    out = tmp_path / "out" / "candidates.csv"
    write_candidates_csv([candidate], out)
    with out.open(newline="", encoding="utf-8") as f:
        table = list(csv.reader(f))
    assert table == [
        ["code", "size",
         "shufersal_name", "shufersal_coverage", "shufersal_median", "ramilevy_name", "ramilevy_coverage",
         "ramilevy_median", "osherad_name", "osherad_coverage", "osherad_median", "carrefour_name",
         "carrefour_coverage", "carrefour_median", "yochananof_name", "yochananof_coverage", "yochananof_median"],
        [A, "1000 gml",
         "שם shufersal", "1.00", "5.90", "שם ramilevy", "0.99", "12.075",  # 1.00 only when every store lists it
         "שם osherad", "0.80", "5.55", "שם carrefour", "0.66", "5.55", "שם yochananof", "1.00", "5.55"],
    ]


def store_list(*ids: str) -> bytes:
    """A store list of the stores `ids`, all in sub-chain 1."""
    stores = "".join(f"<Store><StoreID>{store}</StoreID><StoreName>סניף {store}</StoreName>"
                     f"<StoreType>1</StoreType></Store>" for store in ids)
    return (f"<Root><SubChains><SubChain><SubChainID>1</SubChainID><Stores>{stores}</Stores></SubChain>"
            f"</SubChains></Root>").encode()


def test_main_counts_only_the_included_stores_and_writes_the_day_s_table(tmp_path, monkeypatch, capsys):
    data = tmp_path / "data"
    for slug in SLUGS:
        folder = data / "raw" / f"chain={slug}" / "date=2026-11-02"
        folder.mkdir(parents=True)
        (folder / "Stores7290027600007-000-20261102-020.xml").write_bytes(store_list("1", "413"))
        if slug == "shufersal":  # store 413, Shufersal's online store, is left out: A is at its one store with a file
            rows = listed(A, G_500, ["1"]) + listed(B, G_500, ["413"])
        else:
            rows = listed(A, G_500, ["1", "413"]) + listed(B, G_500, ["1", "413"])
        write_table(rows, table_path(data / "tables", slug, DAY))
    monkeypatch.chdir(tmp_path)
    main(["--day", "2026-11-02"])
    with (data / "candidates-2026-11-02.csv").open(newline="", encoding="utf-8") as f:
        table = list(csv.DictReader(f))
    assert [(line["code"], line["shufersal_coverage"], line["shufersal_median"]) for line in table] == [
        (A, "1.00", "5.10")]
    assert capsys.readouterr().out == "1 candidates written to data/candidates-2026-11-02.csv\n"


def test_main_stops_without_a_store_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="no store list for chain 'shufersal' on or before 2026-11-02"):
        main(["--day", "2026-11-02"])

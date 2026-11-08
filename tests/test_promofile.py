"""Promotion files: a record per promotion kept, with its groups and links; one not kept is counted and dropped as read."""
import gzip
import io
import re
import tracemalloc
import zipfile
from pathlib import Path

import pytest

from basket.pricefile import BadPriceFile
from shopper.promofile import FieldSets, PromotionFormatChanged, PromotionRead, Tally, read_promotions

FIXTURES = Path(__file__).parent / "fixtures"
SHUFERSAL = FIXTURES / "shufersal" / "PromoFull7290027600007-000-878-20261031-030000.gz"
RAMI_LEVY = FIXTURES / "ncr" / "PromoFull7290058140886-001-731-20261101-001049.gz"
CARREFOUR = FIXTURES / "carrefour" / "PromoFull7290055700007-001-472-20261031-051058.gz"
PROMO_FIXTURES = [SHUFERSAL, RAMI_LEVY, CARREFOUR]
FIXTURE_IDS = ["shufersal", "rami levy", "carrefour"]
MB = 1024 * 1024
ZIP_TIME = (2026, 1, 1, 0, 0, 0)  # a fixed time: ZipFile.writestr with a bare name reads the clock


def _everything(promotion):
    return True


def _nothing(promotion):
    return False


def _not_a_coupon(promotion):
    return promotion["AdditionalIsCoupon"] != "1"


def _records(name, data, keep=_everything, tally=None, known=None):
    return list(read_promotions(name, data, keep, Tally() if tally is None else tally, known))


def _links(records):
    return [link for record in records for link in record.links]


def _own_sets(path):
    """The fixture's field sets, as the reader saw them."""
    tally = Tally()
    _records(path.name, path.read_bytes(), tally=tally)
    return FieldSets(**{level: frozenset(tags) for level, tags in tally.seen.items()})


def _item(code):
    return (f"<PromotionItem><ItemCode>{code}</ItemCode><ItemType>1</ItemType><RewardType>3</RewardType>"
            "<MinQty>1</MinQty><MaxQty/><DiscountRate/><DiscountedPrice>5.00</DiscountedPrice><DiscountedPricePerMida/>"
            "<bIsWeighted>0</bIsWeighted></PromotionItem>")


def _promotion(promotion_id, codes, coupon="0", groups=None):
    """A promotion of one group holding `codes`, or of the `groups` given as XML."""
    if groups is None:
        groups = ("<Group><GroupID>1</GroupID><MinPurchaseAmount/><DiscountType/><PromotionItems>"
                  + "".join(_item(code) for code in codes) + "</PromotionItems></Group>")
    return (f"<Promotion><PromotionID>{promotion_id}</PromotionID>"
            "<PromotionDescription>מבצע לדוגמה 1</PromotionDescription>"
            f"<ClubID>0</ClubID><IsGiftItem/><AdditionalIsCoupon>{coupon}</AdditionalIsCoupon><Remarks/>"
            f"<Groups>{groups}</Groups></Promotion>")


def _file(*promotions):
    return ('<?xml version="1.0" encoding="utf-8"?><Root><ChainID>7290027600007</ChainID><SubChainID>000</SubChainID>'
            "<StoreID>878</StoreID><BikoretNo>3</BikoretNo><Promotions>" + "".join(promotions)
            + "</Promotions></Root>").encode()


@pytest.mark.parametrize("path, club, gift", [
    (SHUFERSAL, "0 - כלל הלקוחות", ""),  # Shufersal labels the code and leaves the gift field empty
    (RAMI_LEVY, "0", "6"),
    (CARREFOUR, "0", "1"),
], ids=FIXTURE_IDS)
def test_each_fixture_gives_its_three_links(path, club, gift):
    tally = Tally()
    records = _records(path.name, path.read_bytes(), tally=tally)
    links = _links(records)
    assert len(records) == 3 and len(links) == 3
    first = links[0]
    assert first.promotion["PromotionID"] == "900001"
    assert (first.group["GroupID"], first.item["ItemCode"]) == ("1", "2000000000046")
    assert (first.promotion["ClubID"], first.promotion["IsGiftItem"]) == (club, gift)
    assert "Groups" not in first.promotion and "PromotionItems" not in first.group
    assert first.promotion is records[0].fields and records[0].groups == (first.group,)
    assert (tally.promotions, tally.links, tally.dropped_promotions, tally.dropped_links) == (3, 3, 0, 0)


def test_a_promotion_not_kept_is_counted_and_never_built():
    data = _file(_promotion("900001", ["2000000000046"]),
                 _promotion("900002", [f"{n:013d}" for n in range(5000)], coupon="1"),  # a voucher
                 _promotion("900003", ["2000000000053"]))
    asked = []

    def keep(promotion):
        asked.append(promotion["PromotionID"])
        return _not_a_coupon(promotion)

    tally = Tally()
    records = _records("synthetic.xml", data, keep, tally)
    assert asked == ["900001", "900002", "900003"]  # once each
    assert [record.fields["PromotionID"] for record in records] == ["900001", "900003"]
    assert [link.item["ItemCode"] for link in _links(records)] == ["2000000000046", "2000000000053"]
    assert (tally.promotions, tally.dropped_promotions, tally.dropped_links, tally.links) == (3, 1, 5000, 2)


def test_a_voucher_of_100000_items_is_read_in_flat_memory():
    data = _file(_promotion("900001", [f"{n:013d}" for n in range(100_000)], coupon="1"))
    tally = Tally()
    tracemalloc.start()
    try:
        records = _records("voucher.xml", data, _not_a_coupon, tally)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert records == [] and tally.dropped_links == 100_000
    assert peak < 16 * MB  # a tree kept whole takes several times that


def test_a_field_after_groups_is_refused():
    promotion = _promotion("900001", ["2000000000046"]).replace("<ClubID>0</ClubID>", "")
    promotion = promotion.replace("</Groups>", "</Groups><ClubID>0</ClubID>")
    with pytest.raises(PromotionFormatChanged, match="^late.xml: ClubID after Groups$"):
        _records("late.xml", _file(promotion))


@pytest.mark.parametrize("path", PROMO_FIXTURES, ids=FIXTURE_IDS)
def test_known_field_sets_hold(path):
    known = _own_sets(path)
    assert known.root == {"ChainID", "SubChainID", "StoreID", "BikoretNo", "Promotions"}
    assert "Groups" in known.promotion and "PromotionItems" in known.group and "ItemCode" in known.item
    data = path.read_bytes()
    assert _records(path.name, data, known=known) == _records(path.name, data)


@pytest.mark.parametrize("keep", [_everything, _nothing], ids=["kept", "dropped"])  # a dropped promotion is checked too
@pytest.mark.parametrize("level, old, new, added, missing", [
    ("root", "<BikoretNo>3</BikoretNo>", "<BikoretNo>3</BikoretNo><Extra>1</Extra>", ["Extra"], []),
    ("root", "<BikoretNo>3</BikoretNo>", "", [], ["BikoretNo"]),
    ("promotion", "<Remarks />", "<Remarks /><Extra />", ["Extra"], []),
    ("promotion", "<Remarks />", "", [], ["Remarks"]),
    ("group", "<DiscountType>1</DiscountType>", "<DiscountType>1</DiscountType><Extra />", ["Extra"], []),
    ("group", "<DiscountType>1</DiscountType>", "", [], ["DiscountType"]),
    ("item", "<bIsWeighted>0</bIsWeighted>", "<bIsWeighted>0</bIsWeighted><Extra />", ["Extra"], []),
    ("item", "<bIsWeighted>0</bIsWeighted>", "", [], ["bIsWeighted"]),
], ids=["root added", "root missing", "promotion added", "promotion missing", "group added", "group missing",
        "item added", "item missing"])
def test_a_new_or_missing_field_is_refused(level, old, new, added, missing, keep):
    known = _own_sets(SHUFERSAL)
    body = gzip.decompress(SHUFERSAL.read_bytes())
    changed = body.replace(old.encode(), new.encode(), 1)  # in the first element of the level only
    assert changed != body
    with pytest.raises(PromotionFormatChanged) as refused:
        _records(SHUFERSAL.name, changed, keep, known=known)
    assert str(refused.value) == f"{SHUFERSAL.name}: {level} fields changed: added {added}, missing {missing}"


def test_text_is_stripped_and_an_empty_element_is_empty():
    promotion = ("<Promotion><PromotionID>\r\n  900001 </PromotionID><Remarks /><ClubID>  </ClubID>"
                 "<AdditionalIsCoupon>0</AdditionalIsCoupon><Groups><Group><GroupID> 1\r\n</GroupID>"
                 "<DiscountType></DiscountType><PromotionItems><PromotionItem><ItemCode>\t2000000000046 </ItemCode>"
                 "<MaxQty/></PromotionItem></PromotionItems></Group></Groups></Promotion>")
    [record] = _records("plain.xml", _file(promotion))
    [link] = record.links
    assert dict(record.fields) == {"PromotionID": "900001", "Remarks": "", "ClubID": "", "AdditionalIsCoupon": "0"}
    assert dict(link.group) == {"GroupID": "1", "DiscountType": ""}
    assert dict(link.item) == {"ItemCode": "2000000000046", "MaxQty": ""}


def test_a_zip_and_a_bom_read_alike():
    gzipped = SHUFERSAL.read_bytes()
    with_bom = gzip.decompress(gzipped)
    assert with_bom.startswith(b"\xef\xbb\xbf")
    without_bom = with_bom[3:]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("folder/", ZIP_TIME), b"")  # a directory entry holds no file
        archive.writestr(zipfile.ZipInfo("first.xml", ZIP_TIME), with_bom)
        archive.writestr(zipfile.ZipInfo("second.xml", ZIP_TIME), without_bom)
    expected = _records(SHUFERSAL.name, gzipped)
    assert len(expected) == 3
    assert _records(SHUFERSAL.name, with_bom) == expected
    assert _records(SHUFERSAL.name, without_bom) == expected
    assert _records(SHUFERSAL.name, buffer.getvalue()) == expected + expected


@pytest.mark.parametrize("data", [
    b"",
    b"<html><body></body></html>",
    gzip.compress(b"<html><body></body></html>", mtime=0),
    b"\x1f\x8b junk",
    gzip.compress(b"<Root><Promotions><Promotion>", mtime=0),  # starts like XML, cut short
    b"PK\x03\x04 junk",
], ids=["empty", "html", "html in a gzip", "bad gzip", "cut-short xml", "bad zip"])
def test_an_html_page_or_a_bad_gzip_is_a_bad_file(data):
    with pytest.raises(BadPriceFile) as refused:
        _records(SHUFERSAL.name, data)
    assert str(refused.value).startswith(f"{SHUFERSAL.name}: ")


def test_an_item_less_group_is_kept_with_its_fields():
    groups = ("<Group><GroupID>1</GroupID><MinPurchaseAmount/><PromotionItems>" + _item("2000000000046")
              + _item("2000000000053") + "</PromotionItems></Group>"
              "<Group><GroupID>2</GroupID><MinPurchaseAmount>50.00</MinPurchaseAmount></Group>")  # min spend, no items
    tally = Tally()
    [record] = _records("plain.xml", _file(_promotion("900001", [], groups=groups)), tally=tally)
    assert [dict(group) for group in record.groups] == [{"GroupID": "1", "MinPurchaseAmount": ""},
                                                        {"GroupID": "2", "MinPurchaseAmount": "50.00"}]
    assert [link.item["ItemCode"] for link in record.links] == ["2000000000046", "2000000000053"]
    assert all(link.group is record.groups[0] for link in record.links)
    assert tally.links == 2


def test_a_promotion_without_groups_is_asked_at_its_end():
    asked = []
    tally = Tally()
    promotion = "<Promotion><PromotionID>900001</PromotionID><AdditionalIsCoupon>0</AdditionalIsCoupon></Promotion>"
    records = _records("plain.xml", _file(promotion), lambda p: asked.append(dict(p)) or True, tally)
    assert asked == [{"PromotionID": "900001", "AdditionalIsCoupon": "0"}]
    assert records == [PromotionRead({"PromotionID": "900001", "AdditionalIsCoupon": "0"}, (), ())]
    assert (tally.promotions, tally.links) == (1, 0)


@pytest.mark.parametrize("old, new, message", [
    ("<PromotionDays />", "<PromotionDays><Day>1</Day></PromotionDays>", "Day inside PromotionDays"),
    ("<BikoretNo>3</BikoretNo>", "<BikoretNo><No>3</No></BikoretNo>", "No inside BikoretNo"),
], ids=["promotion field", "root field"])
def test_an_element_inside_a_field_is_refused(old, new, message):
    body = gzip.decompress(SHUFERSAL.read_bytes())
    changed = body.replace(old.encode(), new.encode(), 1)  # read as a field, it would be an empty one
    assert changed != body
    with pytest.raises(PromotionFormatChanged, match=f"^{re.escape(SHUFERSAL.name)}: {message}$"):
        _records(SHUFERSAL.name, changed)


def test_a_groups_field_after_its_items_is_taken():
    groups = ("<Group><GroupID>1</GroupID><PromotionItems>" + _item("2000000000046")
              + "</PromotionItems><MinPurchaseAmount>50.00</MinPurchaseAmount></Group>")  # links wait for the end
    [record] = _records("plain.xml", _file(_promotion("900001", [], groups=groups)))
    [link] = record.links
    assert dict(link.group) == {"GroupID": "1", "MinPurchaseAmount": "50.00"}

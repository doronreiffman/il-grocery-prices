"""The saved portal fixtures carry no secrets and no more than three records a file."""
import collections
import gzip
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
PLACEHOLDER = "SCRUBBED"

# Domain part must start with a letter: NCR's page links "logo@2x.png", which is not an address.
EMAIL_RE = re.compile(r"[\w.+-]+@[A-Za-z][\w-]*(?:\.[\w-]+)*\.[A-Za-z]{2,}")
SIG_RE = re.compile(r"sig=([^&\s\"'<>]*)")
# A CSRF token's value, wherever the page puts one: an attribute of a tag that names it,
# or "csrf...=value" / "csrf...": "value" in a query string, script or JSON.
CSRF_TAG_RE = re.compile(r"<[^<>]*csrf[^<>]*>", re.I)
CSRF_ATTR_RE = re.compile(r"""\b(?:content|value)\s*=\s*["']([^"']*)["']""", re.I)
CSRF_ASSIGN_RE = re.compile(r"""csrf[\w-]*["']?\s*[:=]\s*["']?([\w+/=.%-]*)""", re.I)
FORBIDDEN = ("set-cookie", "cftoken", "cftpsid")
RECORD_TAGS = ("Item", "Promotion", "PromotionItem", "Store")
MAIN_RECORD = {"pricefull": "Item", "price": "Item", "promofull": "Promotion", "promo": "Promotion",
               "stores": "Store"}


def _files():
    files = sorted(p for p in FIXTURES.rglob("*") if p.is_file())
    assert files, "no fixtures found"
    return files


def _payload(path: Path) -> bytes:
    """The file's XML: a gzip unzipped, a ZIP's one member (Rami Levy store 039), or the file itself."""
    data = path.read_bytes()
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            assert len(members) == 1, f"{path.name}: a ZIP fixture holds one file, as store 039's do"
            return archive.read(members[0])
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def _text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("utf-8", errors="replace")


def test_fixtures_have_no_secrets():
    problems = []
    for path in _files():
        name = path.relative_to(FIXTURES)
        texts = {_text(path.read_bytes()), _text(_payload(path))}
        for text in texts:
            low = text.lower()
            problems += [f"{name}: contains {word!r}" for word in FORBIDDEN if word in low]
            problems += [f"{name}: sig={v[:6]}..." for v in SIG_RE.findall(text) if v != PLACEHOLDER]
            values = [v for tag in CSRF_TAG_RE.findall(text) for v in CSRF_ATTR_RE.findall(tag)]
            values += CSRF_ASSIGN_RE.findall(text)
            problems += [f"{name}: csrf value {v[:6]}..." for v in values if v not in ("", PLACEHOLDER)]
            problems += [f"{name}: email address {m}" for m in EMAIL_RE.findall(text)]
    assert not problems, "\n".join(sorted(set(problems)))


def test_fixture_xml_trimmed():
    checked = 0
    for path in _files():
        if path.suffix not in (".gz", ".xml"):
            continue
        root = ET.fromstring(_payload(path))  # expat reads the BOM: UTF-8 or UTF-16
        counts = collections.Counter(el.tag for el in root.iter())
        over = {t: counts[t] for t in RECORD_TAGS if counts[t] > 3}
        assert not over, f"{path.relative_to(FIXTURES)}: more than three records {over}"
        main = MAIN_RECORD[re.match(r"[A-Za-z]+", path.name).group(0).lower()]
        assert counts[main] >= 1, f"{path.relative_to(FIXTURES)}: no <{main}> left"
        checked += 1
    assert checked >= 9, f"expected the three kinds for three portals, checked {checked}"

"""Ruling R37: whether the day's runs read a kind's whole file list between them, what of it no run read, and where
the next run starts reading it.

Shufersal lists each full kind on about 21 pages, and on a slow morning no one run reads them all, so a later run picks
up where an earlier one stopped (docs/shufersal-resume.md). A kind counts as read in full for the day when the pages
the day's runs read join up from page 1 to the last page:

- The runs that count are those that cover the kind and were not blocked. A run that stopped on time or on an error
  counts for the pages it read before it stopped.
- A counted run whose manifest holds no page records (other chains' runs, and Shufersal's before this ruling) and that
  ended with no error reads the kind in full on its own, as ruling R36 reads it.
- A run's pages of the kind that it took rows from, in the order it read them, form blocks: a new block starts
  wherever a page number is not one more than the one before, and after a page the run did not take to its last row.
  A page it took no row from (one it stepped back over) is left out.
- A block covers the names from its first page's first name to the last name the run took from its last page. A block
  that starts at page 1 also covers everything before it. A block also covers everything after it when it ends at the
  last page the run's own page 1 named (page 1 when that page names none; a run that did not read page 1 has no such
  block), with that page's last row taken.
- The blocks of every counted run, taken from the front (by where they start; among blocks that start together, the
  one reaching furthest first), join up while each starts at or before the end of the reading so far. The kind is read
  in full when the reading reaches past the last name. The runs named are those with a block that moved the end on.
- Joining needs every page of the kind recorded that day to be in order, blocked runs' pages included. When one is
  not, joining is off: beside the runs without page records above, only a run that read page 1 to the last page in
  one go counts.

The kind is read by the runs without page records that read it in full on their own, and by the runs named in the
joining (with joining off, each run that read page 1 to the last page in one go); when there are none, it is not read
in full.

Where a run starts reading a kind follows from the same records (docs/shufersal-resume.md, section 2):

- No usable record: when a page of the kind recorded that day is out of order (blocked runs' pages included), or no
  counted run took a name of the kind and it is not read in full, a fresh pass from page 1, as every run made before
  page records existed.
- A failed file: a name a counted run listed that the day has not stored sits on that run's page whose first name and
  last name taken it falls between (the stored name without its `.gz`). Each such page but page 1, which is read
  anyway, is a detour, read once before page 1.
- Read in full: a fresh pass, after a detour to each failed file's page.
- Not read in full: a resume at the page of the furthest name the counted runs took (the larger page when two records
  hold that name), after a detour to each failed file's page before it. A resume at page 1 is a fresh pass.

A manifest's page record is `dataclasses.asdict` of a `collector.sources.PageRead` with `taken_through`: the last name
the run took from the page, as listed (without `.gz`), or None. Names compare as plain strings.

Ruling R39: an update kind (`Price`, `Promo`) is read several times a day, by poll runs (docs/update-files.md, section
3), so its day is cut into passes, each a reading of its own:

- The runs that make a kind's passes are its poll runs that were not blocked and read the listing, in the order they
  read it (`listing_read_at`, never the run id, whose time is UTC).
- Each run joins the current pass. After it joins, the pass ends when the pass's own runs read the kind in full, as
  R37 reads them (a run without page records that ended with no error reads it on its own), or when this run recorded
  a page of the kind out of order; the next run begins a new pass. The runs left at the end make the last pass, open.
- A poll run starts from the last pass: when it is open, R37's start over that pass's runs alone (a resume at its
  furthest page, detours to its failed files' pages); otherwise a fresh pass from page 1, with no detour.

So a page out of order costs one pass, not the day. R37's functions are unchanged and read the full kinds as before:
each reads only the runs that cover the kind it is asked about, and only that kind's pages.
"""
from dataclasses import dataclass
from datetime import datetime

from collector.sources import Start

BEFORE = (0, "")  # before every name: where a block from page 1 starts, and where a reading starts
AFTER = (2, "")  # after every name: where a block that reaches past the last name ends

Bound = tuple[int, str]  # BEFORE, (1, a name) or AFTER: tuples order as the names they stand for


def read_in_full(manifests: list[dict], kind: str) -> list[str] | None:
    """The ids of the runs that read `kind` in full (ruling R37), in the manifests' order: the counted runs without page
    records that ended with no error, and beside them the runs with a block that moved the joined reading's end on,
    when the blocks join up past the last name, or, with joining off, every run that read page 1 to the last page in
    one go. None when there are none: the kind is not read in full."""
    counted = _counted(manifests, kind)
    readers = {manifest["run_id"] for manifest in counted if not manifest.get("pages") and not manifest["error"]}
    if _out_of_order(manifests, kind) is None:
        readers |= _joined(counted, kind)
    else:  # joining is off: only a run that read every page in one go counts
        readers |= {manifest["run_id"] for manifest in counted if (BEFORE, AFTER) in _blocks(manifest, kind)}
    return [manifest["run_id"] for manifest in counted if manifest["run_id"] in readers] or None


def unread(manifests: list[dict], kind: str) -> str:
    """What of `kind`'s list no counted run read, for the failed alert; for a kind not read in full."""
    records = [record for manifest in _counted(manifests, kind) for record in _records(manifest, kind)]
    last_pages = [record["last_page"] or 1 for record in records if record["page"] == 1]
    if not last_pages:
        text = "page 1 never read, so the last page is not known"
    else:
        every = range(1, max(last_pages) + 1)
        touched = {record["page"] for record in records if record["taken_through"] is not None}
        read = {record["page"] for record in records if record["taken_through"] == record["last"]}
        never = [page for page in every if page not in touched]
        in_part = [page for page in every if page in touched and page not in read]
        parts = [f"{_pages(pages)} {what}" for pages, what in ((never, "never read"), (in_part, "read in part")) if pages]
        text = ", ".join(parts) or "every page was read, but the pages read do not join up"
    disorder = _out_of_order(manifests, kind)
    if disorder is not None:
        page, run_id = disorder
        text += f" (page {page} of run {run_id} was out of order, so only a run that read every page in one go counts)"
    return text


def start_for(manifests: list[dict], kind: str, stored: set[str]) -> Start:
    """Where a run starts reading `kind`, from the day's earlier manifests and the names stored that day (`<name>.gz`,
    ruling R16)."""
    if _out_of_order(manifests, kind) is not None:
        return Start()  # the day's records of the kind place no name
    earlier = _counted(manifests, kind)  # blocked runs are left out, as the check leaves them out
    found = [page for manifest in earlier for page in _failed_pages(manifest, kind, stored) if page != 1]
    detours = tuple(sorted(set(found)))
    if read_in_full(manifests, kind) is not None:
        return Start(detours=detours)  # a fresh pass, for the files published since the list was read
    taken = [record for manifest in earlier for record in _records(manifest, kind)
             if record["taken_through"] is not None]
    if not taken:
        return Start()
    furthest = max(taken, key=lambda record: (record["taken_through"], record["page"]))
    if furthest["page"] == 1:
        return Start(detours=detours)  # a resume at page 1 is a fresh pass
    before = tuple(page for page in detours if page < furthest["page"])
    return Start(page=furthest["page"], furthest=furthest["taken_through"], detours=before)


def has_pages(manifests: list[dict], kind: str) -> bool:
    """Whether any manifest of the day recorded a page of `kind`."""
    return any(_records(manifest, kind) for manifest in manifests)


@dataclass
class Pass:
    """One reading of an update kind's list by the day's poll runs (ruling R39)."""

    runs: list[dict]  # the pass's poll manifests, in listing_read_at order
    read_by: list[str] | None  # read_in_full(runs, kind): the runs that read the list in full; None when it did not
    out_of_order: bool  # its last run recorded a page of the kind out of order

    @property
    def open(self) -> bool:
        """Not read in full and not ended by a page out of order: the pass the next run carries on."""
        return self.read_by is None and not self.out_of_order


def passes(manifests: list[dict], kind: str) -> list[Pass]:
    """The day's passes over update kind `kind`'s list (ruling R39), in order: its poll runs that were not blocked and
    read the listing, in the order they read it, cut after each run that completes its pass's reading or records a
    page of the kind out of order. The runs left at the end make the last pass, open."""
    runs = [manifest for manifest in manifests if manifest["mode"] == "poll" and kind in manifest["kinds"]
            and not manifest["blocked"] and manifest["listing_read_at"] is not None]
    runs.sort(key=lambda manifest: datetime.fromisoformat(manifest["listing_read_at"]))  # aware, UTC
    cut: list[Pass] = []
    current: list[dict] = []
    for manifest in runs:
        current.append(manifest)
        read_by = read_in_full(current, kind)  # the pass's own runs: an earlier pass's reading is done with
        out_of_order = _out_of_order([manifest], kind) is not None
        if read_by is not None or out_of_order:
            cut.append(Pass(current, read_by, out_of_order))
            current = []
    if current:
        cut.append(Pass(current, None, False))
    return cut


def pass_start(manifests: list[dict], kind: str, stored: set[str]) -> Start:
    """Where a poll run starts reading update kind `kind` (ruling R39), from the day's earlier manifests and the names
    stored that day (`<name>.gz`): R37's start over the last pass's runs alone when that pass is open."""
    cut = passes(manifests, kind)
    if cut and cut[-1].open:
        return start_for(cut[-1].runs, kind, stored)
    return Start()  # a fresh pass: no pass yet, or the last read in full or ended by a page out of order


def _counted(manifests: list[dict], kind: str) -> list[dict]:
    """The runs that count for `kind`: those that cover it and were not blocked, whatever they ended with."""
    return [manifest for manifest in manifests if kind in manifest["kinds"] and not manifest["blocked"]]


def _records(manifest: dict, kind: str) -> list[dict]:
    """The manifest's page records of `kind`, in the order read; none for a manifest written before page records."""
    return [record for record in manifest.get("pages", []) if record["kind"] == kind]


def _failed_pages(manifest: dict, kind: str, stored: set[str]) -> list[int]:
    """The run's pages of `kind` that hold a name it listed and the day has not stored: a page for each name and record
    that holds it, in the order listed."""
    records = [record for record in _records(manifest, kind) if record["taken_through"] is not None]
    failed = [listed.removesuffix(".gz") for listed in manifest["listed"] if listed not in stored]
    return [record["page"] for name in failed for record in records
            if record["first"] <= name <= record["taken_through"]]


def _out_of_order(manifests: list[dict], kind: str) -> tuple[int, str] | None:
    """The first page of `kind` recorded out of order that day, blocked runs' included, as (page, run id); None when
    every page is in order."""
    for manifest in manifests:
        for record in _records(manifest, kind):
            if not record["in_order"]:
                return record["page"], manifest["run_id"]
    return None


def _blocks(manifest: dict, kind: str) -> list[tuple[Bound, Bound]]:
    """The run's blocks of `kind`, each as (start, end), in the order read."""
    records = _records(manifest, kind)
    own_last = next((record["last_page"] or 1 for record in records if record["page"] == 1), None)
    blocks: list[list[dict]] = []
    for record in records:
        if record["taken_through"] is None:
            continue  # read and left (a step back) or nothing given: no name of it was taken
        before = blocks[-1][-1] if blocks else None  # the page taken from just before, in the order read
        if before and record["page"] == before["page"] + 1 and before["taken_through"] == before["last"]:
            blocks[-1].append(record)
        else:  # a jump in page numbers, or the run left the page before part-way: its later rows were never listed
            blocks.append([record])
    return [(_start(block[0]), _end(block[-1], own_last)) for block in blocks]


def _start(record: dict) -> Bound:
    return BEFORE if record["page"] == 1 else (1, record["first"])


def _end(record: dict, own_last: int | None) -> Bound:
    if record["page"] == own_last and record["taken_through"] == record["last"]:
        return AFTER
    return 1, record["taken_through"]


def _joined(counted: list[dict], kind: str) -> set[str]:
    """The runs with a block that moved the reading's end on, when the blocks join up to past the last name; none
    when they do not."""
    blocks = [(manifest["run_id"], start, end) for manifest in counted for start, end in _blocks(manifest, kind)]
    blocks.sort(key=lambda block: block[2], reverse=True)  # among blocks that start together, the furthest first
    blocks.sort(key=lambda block: block[1])  # from page 1 first, then by name; the sort keeps the order above
    reading, readers = BEFORE, set()
    for run_id, start, end in blocks:
        if start <= reading < end:  # the block joins the reading and moves its end on
            reading = end
            readers.add(run_id)
    return readers if reading == AFTER else set()


def _pages(numbers: list[int]) -> str:
    """Sorted page numbers as ranges: "page 16", "pages 20 to 21", "pages 3, 17 to 21"."""
    ranges: list[list[int]] = []
    for number in numbers:
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1][1] = number
        else:
            ranges.append([number, number])
    text = ", ".join(str(first) if first == last else f"{first} to {last}" for first, last in ranges)
    return f"{'page' if len(numbers) == 1 else 'pages'} {text}"

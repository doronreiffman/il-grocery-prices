/* search.js, the site's one script, loaded on every page (docs/shopper-site.md, Q2 and Call 12; docs/store-first.md,
   "Q2's one script"): search, which finds a product's page from a typed name or barcode, and the store picker, which
   remembers the store type the shopper is in and arranges each page for it. No fact needs it: every price, verdict and
   chart is in the page's HTML, the browse pages reach every product, and the picker's links reach every store type's
   front page. It adds the class `js` to <html>, and only rules under it, or what it hides itself, hide anything.

   What it keeps: one key, `store`, in the browser's local storage, holding the key of the store type picked, one of the
   columns of shopper/columns.py, whose keys and names are the JSON between the two COLUMNS markers below (a test reads
   it back). It is never sent anywhere. Any other value counts as no pick, and where storage is blocked (reading it, or
   its getItem or setItem, throws) the site simply forgets the pick: no error stops the script.

   The picker. The site's root is read from the header's pick link (#pick-link, whose href is <root>index.html#pick), so
   the script works from a page in a folder. With a pick, the header reads "<store type> \u00b7 change" (a middle dot):
   the name links to the store type's front page (store/<key>.html), "change" to the picker (index.html#pick). A store
   type's front page (main[data-store]) sets the pick. The root page (#pick[data-page="root"]) sends a remembered pick
   on to its store type's front page with location.replace, unless its hash is #pick, which is how "change" reaches the
   picker. A product page (nav.badges: a badge per store type selling it today, each linking to that store type's part,
   section[data-column] with id c-<key>; the row's heading h2.elsewhere, "Elsewhere today", hidden in the HTML):
   - with a pick it has a part for: that part shown and the others hidden, the row moved after it under its heading,
     without the pick's own badge;
   - with a pick it has no part for: every part hidden, "Not sold at <store type> today" before the heading and the row;
   - with no pick: the row stays first, as the picker, its heading hidden, the first badge's part shown (else the first
     part's).
   Tapping a badge shows its part, and the badge's link then scrolls to it; with no pick yet, the tap also sets the pick
   (the owner's answer of 2026-11-11), and with one, the pick stays as it was (store-first.md, call 6).

   Search, where a search box (#q) is. Every request and link starts from the site's root.

   Names. A query and a name are compared after the same steps as shopper/search.py's `normalize`: lower-case, each
   character through the table below (quotes, geresh and gershayim dropped; the five final letters made plain; tab,
   line break and no-break space made a space), runs of spaces collapsed, the ends trimmed. The table is the one in
   shopper/search.py, as JSON between the two NORMALIZE markers; a test reads it back.

   Pieces. search/pieces.json lists the keys of the index pieces; a key is the hex of the first character's code point
   ("05e9"), or of its first two ("05e9-05de") for a letter split in two levels. A query goes to the piece of its first
   character, or of its first two when the letter is split, so it needs two characters, counted after normalising (a
   typed quote or space does not count), before it is searched. A piece is a list of entries [barcode, title as
   published, normalised title, other normalised names...]; the products whose longest name starts with the query's
   letters are in it, and a query matches an entry when any of its names holds it. At most 50 entries are shown, in
   name order.

   Barcodes. A query of 8 to 14 ASCII digits is a barcode; with its leading zeros stripped it is the page p/<barcode>.html,
   and the script asks for that page with HEAD. Anything but 200 means the site has no page for it (the bucket answers a
   missing page with 403), and the script says so.

   One request per piece, once: answers are kept, and a failed request is dropped from the keep so the next key asks
   again. An answer that arrives after the query changed is not shown. Results are written as text the script has
   escaped; they go in a box it adds after the search box. It exports normalize, pieceFor, matches and barcodeOf, and
   the picker's NAMES, PICK_KEY and functions, when `module` exists, for tests/search_harness.js. */
"use strict";

const NORMALIZE = /*NORMALIZE*/{
  "'": "", "\"": "", "\u05f3": "", "\u05f4": "",
  "\u05da": "\u05db", "\u05dd": "\u05de", "\u05df": "\u05e0", "\u05e3": "\u05e4", "\u05e5": "\u05e6",
  "\t": " ", "\n": " ", "\r": " ", "\u00a0": " "
}/*NORMALIZE*/;
const MAX_SHOWN = 50;
const NO_PAGE = "This site has no page for that barcode.";
const NOTHING = "Nothing found. Try fewer letters, or browse by first letter.";
const FAILED = "Could not reach the site just now. Try again.";

const NAMES = /*COLUMNS*/[
  ["carrefour-city", "Carrefour City"], ["carrefour-market", "Carrefour Market"], ["osherad", "Osher Ad"],
  ["ramilevy", "Rami Levy"], ["shufersal-deal", "Shufersal Deal"], ["shufersal-express", "Shufersal Express"],
  ["shufersal-sheli", "Shufersal Sheli"], ["shufersal-universe", "Shufersal Universe"], ["yochananof", "Yochananof"]
]/*COLUMNS*/;
const PICK_KEY = "store";
const PICKER = "index.html#pick";   // the picker, from the site's root
const CHANGE = "change";

// search

function normalize(text) {
  let mapped = "";
  for (const char of String(text).toLowerCase()) {
    const to = NORMALIZE[char];
    mapped += to === undefined ? char : to;
  }
  return mapped.split(" ").filter(Boolean).join(" ");
}

function hex(char) {
  return char.codePointAt(0).toString(16).padStart(4, "0");
}

function pieceFor(query, pieces) {
  const letters = Array.from(normalize(query));
  if (letters.length === 0) return null;
  const whole = hex(letters[0]);
  if (pieces.includes(whole)) return whole;
  if (letters.length > 1 && pieces.includes(whole + "-" + hex(letters[1]))) return whole + "-" + hex(letters[1]);
  return null;
}

function byName(a, b) {
  if (a[2] !== b[2]) return a[2] < b[2] ? -1 : 1;
  return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
}

function matches(entries, query) {
  const wanted = normalize(query);
  if (wanted === "") return [];
  return entries
    .filter((entry) => entry.slice(2).some((name) => name.includes(wanted)))
    .sort(byName)
    .slice(0, MAX_SHOWN);
}

function barcodeOf(query) {
  const typed = String(query).trim();
  if (!/^[0-9]{8,14}$/.test(typed)) return null;
  return typed.replace(/^0+/, "") || null;
}

function escapeHtml(text) {
  const escapes = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" };
  return String(text).replace(/[&<>"']/g, (char) => escapes[char]);
}

function link(root, code, label) {   // root: "" or "../"s, from the page's own pick link
  return "<a href=\"" + root + "p/" + escapeHtml(code) + ".html\">" + label + "</a>";
}

function listing(root, found) {
  const rows = found.map(([code, title]) =>
    "<li>" + link(root, code, "<span class=\"as-listed\" lang=\"he\" dir=\"rtl\">" + escapeHtml(title) + "</span>") +
    " <small>" + escapeHtml(code) + "</small></li>");
  const more = found.length === MAX_SHOWN ? "<p>Showing up to " + MAX_SHOWN + " names. Type more of the name to narrow them.</p>" : "";
  return "<ul>" + rows.join("") + "</ul>" + more;
}

// the picker

function nameOf(key) {
  const found = NAMES.find(([known]) => known === key);
  return found ? found[1] : null;
}

function readPick(storage) {
  let value;
  try {
    value = storage.getItem(PICK_KEY);   // no storage (null) throws here too
  } catch (error) {
    return null;
  }
  return nameOf(value) === null ? null : value;
}

function writePick(storage, key) {
  try {
    storage.setItem(PICK_KEY, key);
  } catch (error) {
    // blocked, full or none: the site forgets the pick
  }
}

function rootOf(href) {
  return href.endsWith(PICKER) ? href.slice(0, href.length - PICKER.length) : "";
}

function redirectFor(pick, hash) {
  if (pick === null || hash === "#pick") return null;
  return "store/" + pick + ".html";
}

function headerFor(pick, root) {
  const name = nameOf(pick);
  if (name === null) return null;
  return { name, href: root + "store/" + pick + ".html", change: root + PICKER };
}

function arrange(pick, parts, badges) {
  if (pick === null) {
    return { open: badges[0] ?? parts[0] ?? null, notSold: null, elsewhere: badges.slice(), heading: false };
  }
  if (parts.includes(pick)) {
    return { open: pick, notSold: null, elsewhere: badges.filter((key) => key !== pick), heading: true };
  }
  return { open: null, notSold: pick, elsewhere: badges.slice(), heading: true };
}

function notSoldLine(key) {
  return "Not sold at " + nameOf(key) + " today";
}

function onBadge(pick, key) {
  return { show: key, setPick: pick === null ? key : null };
}

// the page

function storageOf() {
  try {
    return window.localStorage;
  } catch (error) {
    return null;   // reading it throws where the browser blocks site data
  }
}

function showHeader(pickLink, header) {
  if (pickLink === null || header === null) return;
  const name = document.createElement("a");
  name.setAttribute("href", header.href);
  name.textContent = header.name;
  pickLink.before(name, " \u00b7 ");
  pickLink.setAttribute("href", header.change);
  pickLink.textContent = CHANGE;
}

function arrangeProduct(nav, pick, storage) {
  const keyOf = (element) => element.getAttribute("data-column");
  const parts = Array.from(document.querySelectorAll("section[data-column]"));
  const badges = Array.from(nav.querySelectorAll("a[data-column]"));
  const heading = document.querySelector("h2.elsewhere");
  const layout = arrange(pick, parts.map(keyOf), badges.map(keyOf));
  for (const part of parts) part.hidden = keyOf(part) !== layout.open;
  for (const badge of badges) badge.hidden = !layout.elsewhere.includes(keyOf(badge));
  const open = parts.find((part) => keyOf(part) === layout.open);
  if (open !== undefined && layout.heading) open.after(nav);
  if (heading !== null) {
    nav.before(heading);
    heading.hidden = !layout.heading;
  }
  if (layout.notSold !== null) {
    const line = document.createElement("p");
    line.className = "not-sold";
    line.textContent = notSoldLine(layout.notSold);
    (heading === null ? nav : heading).before(line);
  }
  let current = pick;
  for (const badge of badges) {
    badge.addEventListener("click", () => {   // not prevented: the link then scrolls to the part
      const tap = onBadge(current, keyOf(badge));
      for (const part of parts) if (keyOf(part) === tap.show) part.hidden = false;
      if (tap.setPick !== null) {
        writePick(storage, tap.setPick);
        current = tap.setPick;
      }
    });
  }
}

function startSearch(box, root) {
  const results = document.createElement("div");
  results.id = "results";
  results.setAttribute("aria-live", "polite");
  box.after(results);
  const kept = {};
  let latest = 0;

  function fetched(url) {
    if (!kept[url]) {
      kept[url] = fetch(url).then((response) => {
        if (response.status !== 200) throw new Error(url + ": " + response.status);
        return response.json();
      });
      kept[url].catch(() => { delete kept[url]; });
    }
    return kept[url];
  }

  async function answer(raw) {
    const code = barcodeOf(raw);
    if (code) {
      const response = await fetch(root + "p/" + code + ".html", { method: "HEAD" });
      if (response.status !== 200) return "<p>" + NO_PAGE + "</p>";
      return "<p>" + link(root, code, "Open the page for barcode " + code) + "</p>";   // code: ASCII digits (barcodeOf)
    }
    const query = normalize(raw);
    if (Array.from(query).length < 2) return "";
    const key = pieceFor(query, await fetched(root + "search/pieces.json"));
    if (key === null) return "<p>" + NOTHING + "</p>";
    const found = matches(await fetched(root + "search/" + key + ".json"), query);
    return found.length ? listing(root, found) : "<p>" + NOTHING + "</p>";
  }

  async function run(raw) {
    const mine = ++latest;
    fetched(root + "search/pieces.json");   // the first key starts it; a barcode never waits for it
    let html;
    try {
      html = await answer(raw);
    } catch (error) {
      html = "<p>" + FAILED + "</p>";
    }
    if (mine === latest) results.innerHTML = html;
  }

  box.addEventListener("input", () => run(box.value));
}

function start() {
  document.documentElement.classList.add("js");
  const storage = storageOf();
  const pickLink = document.getElementById("pick-link");
  const root = pickLink === null ? "" : rootOf(pickLink.getAttribute("href") || "");   // no href: the page's folder
  let pick = readPick(storage);
  const store = document.querySelector("main[data-store]");
  if (store !== null) {
    pick = store.getAttribute("data-store");   // this page is the store type's, remembered or not
    writePick(storage, pick);
  }
  showHeader(pickLink, headerFor(pick, root));
  const picker = document.getElementById("pick");
  if (picker !== null && picker.getAttribute("data-page") === "root") {
    const target = redirectFor(pick, window.location.hash);
    if (target !== null) window.location.replace(root + target);
  }
  const nav = document.querySelector("nav.badges");
  if (nav !== null) arrangeProduct(nav, pick, storage);
  const box = document.getElementById("q");
  if (box !== null) startSearch(box, root);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    normalize, pieceFor, matches, barcodeOf,
    NAMES, PICK_KEY, readPick, writePick, rootOf, redirectFor, headerFor, arrange, notSoldLine, onBadge,
  };
}
if (typeof document !== "undefined") {
  start();
}

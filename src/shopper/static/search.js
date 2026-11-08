/* search.js, the one script on the site (docs/shopper-site.md, Q2 and Call 12): it finds a product's page from a typed
   name or barcode. The pages work without it: the browse pages reach every product.

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
   escaped; they go in a box it adds after the search box (#q). It exports normalize, pieceFor, matches and barcodeOf
   when `module` exists, for tests/search_harness.js. */
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

function link(code, label) {
  return "<a href=\"p/" + escapeHtml(code) + ".html\">" + label + "</a>";
}

function listing(found) {
  const rows = found.map(([code, title]) =>
    "<li>" + link(code, "<span class=\"as-listed\" lang=\"he\" dir=\"rtl\">" + escapeHtml(title) + "</span>") +
    " <small>" + escapeHtml(code) + "</small></li>");
  const more = found.length === MAX_SHOWN ? "<p>Showing the first " + MAX_SHOWN + ". Type more of the name to narrow them.</p>" : "";
  return "<ul>" + rows.join("") + "</ul>" + more;
}

function start() {
  const box = document.getElementById("q");
  if (!box) return;
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
      const response = await fetch("p/" + code + ".html", { method: "HEAD" });
      if (response.status !== 200) return "<p>" + NO_PAGE + "</p>";
      return "<p>" + link(code, "Open the page for barcode " + code) + "</p>";   // code: ASCII digits (barcodeOf)
    }
    const query = normalize(raw);
    if (Array.from(query).length < 2) return "";
    const key = pieceFor(query, await fetched("search/pieces.json"));
    if (key === null) return "<p>" + NOTHING + "</p>";
    const found = matches(await fetched("search/" + key + ".json"), query);
    return found.length ? listing(found) : "<p>" + NOTHING + "</p>";
  }

  async function run(raw) {
    const mine = ++latest;
    fetched("search/pieces.json");   // the first key starts it; a barcode never waits for it
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

if (typeof module !== "undefined" && module.exports) {
  module.exports = { normalize, pieceFor, matches, barcodeOf };
}
if (typeof document !== "undefined") {
  start();
}

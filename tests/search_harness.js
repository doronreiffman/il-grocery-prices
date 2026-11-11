"use strict";
/* Loads src/shopper/static/search.js under Node and prints its answers as JSON, for tests/test_search_js.py.

   node tests/search_harness.js <op>     the op's JSON on stdin, its answer as JSON on stdout

   Search:
   normalize   [text, ...]                                  -> [normalised, ...]
   pieceFor    {pieces: [key, ...], queries: [text, ...]}   -> [key or null, ...]
   matches     {entries: [...], query: text}                -> the matching entries
   barcodeOf   [text, ...]                                  -> [barcode or null, ...]

   The picker, one op per function, each over a list of calls. A storage is described as null (none: reading
   localStorage threw), {value} (getItem gives the value; null is a missing key) or {throws: true} (getItem and setItem
   throw):
   readPick    [storage, ...]                               -> [pick or null, ...]
   writePick   [{storage, key}, ...]                        -> [{threw, stored: what the storage holds after}, ...]
   rootOf      [href, ...]                                  -> [root, ...]
   redirectFor [[pick, hash], ...]                          -> [url or null, ...]
   headerFor   [[pick, root], ...]                          -> [{name, href, change} or null, ...]
   arrange     [[pick, parts, badges], ...]                 -> [{open, notSold, elsewhere, heading}, ...]
   notSoldLine [key, ...]                                   -> [line, ...]
   onBadge     [[pick, key], ...]                           -> [{show, setPick}, ...]

   A page:
   page        {dom?, storage?, hash?, clicks?, inputs?, responses?}
               dom is the page's elements inside <html>, each [tag, {attribute: value}, [child, ...]], a child an
               element or a text; without it the page is a search box (#q) alone, at the site's root. storage is
               {key: value} (the default, {}), "throws" (getItem and setItem throw) or "blocked" (reading localStorage
               throws, as when the browser blocks site data). hash is location.hash (default ""). The script runs; then
               each click taps the badge (a[data-column]) of that key; then each input's value is typed into the search
               box, waiting for its answer unless wait is false, with a fake fetch that answers {status, body, delay?,
               reject?} and records every request. The answer: {requests: [{url, method}, ...], html: the results box's
               content, page: the page as HTML, stored: the storage's {key: value} after (null unless an object),
               replaced: the urls given to location.replace}. A throw anywhere in the script fails the op (exit 1). */
const fs = require("fs");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "src", "shopper", "static", "search.js");

// The fake page: only the DOM the script uses. A selector is one compound selector (a tag, #id, .class, [attribute]),
// never a combinator; any other throws, so a script that needs more of the DOM fails here instead of passing by luck.
function matcher(selector) {
  const found = /^([a-z0-9]+)?((?:[#.][\w-]+|\[[\w-]+\])*)$/.exec(selector);
  if (!found) throw new Error("the fake page cannot match " + selector);
  const bits = found[2].match(/[#.][\w-]+|\[[\w-]+\]/g) || [];
  return (element) => (!found[1] || element.tag === found[1]) && bits.every((bit) =>
    bit[0] === "#" ? element.getAttribute("id") === bit.slice(1)
      : bit[0] === "." ? (element.getAttribute("class") || "").split(" ").includes(bit.slice(1))
        : element.hasAttribute(bit.slice(1, -1)));
}

class Element {
  constructor(tag, attributes = {}, children = []) {
    this.tag = tag;
    this.attributes = { ...attributes };
    this.children = [];
    this.parent = null;
    this.listeners = {};
    this.value = "";
    this.innerHTML = "";
    this.append(...children.map((child) => (Array.isArray(child) ? new Element(...child) : child)));
  }

  adopt(node) {
    if (!(node instanceof Element)) return String(node);
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1);
    node.parent = this;
    return node;
  }
  append(...nodes) { this.children.push(...nodes.map((node) => this.adopt(node))); }
  insert(nodes, offset) {
    const siblings = this.parent.children;
    const adopted = nodes.map((node) => this.parent.adopt(node));   // moved out first, then placed
    siblings.splice(siblings.indexOf(this) + offset, 0, ...adopted);
  }
  before(...nodes) { this.insert(nodes, 0); }
  after(...nodes) { this.insert(nodes, 1); }

  getAttribute(name) { return Object.hasOwn(this.attributes, name) ? this.attributes[name] : null; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
  removeAttribute(name) { delete this.attributes[name]; }
  get id() { return this.getAttribute("id") || ""; }
  set id(value) { this.setAttribute("id", value); }
  set className(value) { this.setAttribute("class", value); }
  get hidden() { return this.hasAttribute("hidden"); }
  set hidden(value) { if (value) this.setAttribute("hidden", ""); else this.removeAttribute("hidden"); }
  get classList() {
    return {
      add: (name) => {
        const names = (this.getAttribute("class") || "").split(" ").filter(Boolean);
        if (!names.includes(name)) this.setAttribute("class", [...names, name].join(" "));
      },
    };
  }
  set textContent(text) {
    for (const child of this.children) if (child instanceof Element) child.parent = null;
    this.children = [String(text)];
  }

  addEventListener(type, listener) { (this.listeners[type] = this.listeners[type] || []).push(listener); }
  fire(type, event) { return Promise.all((this.listeners[type] || []).map((listener) => listener(event))); }

  descendants() { return this.children.filter((c) => c instanceof Element).flatMap((c) => [c, ...c.descendants()]); }
  querySelectorAll(selector) { return this.descendants().filter(matcher(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }

  html() {
    const attributes = Object.entries(this.attributes).map(([name, value]) =>
      (name === "hidden" && value === "" ? " hidden" : " " + name + "=\"" + value + "\"")).join("");
    const inside = this.children.map((child) => (child instanceof Element ? child.html() : child)).join("");
    return "<" + this.tag + attributes + ">" + inside + this.innerHTML + "</" + this.tag + ">";
  }
}

// A storage as the header describes it; what is set goes into held.
function storageFrom(description, held = {}) {
  if (description === null) return null;
  if (description.throws) {
    const refuse = () => { throw new Error("SecurityError: the storage is blocked"); };
    return { getItem: refuse, setItem: refuse };
  }
  return {
    getItem: (key) => (Object.hasOwn(held, key) ? held[key] : (description.value ?? null)),
    setItem: (key, value) => { held[key] = String(value); },
  };
}

async function page({ dom, storage = {}, hash = "", clicks = [], inputs = [], responses = {} }) {
  const requests = [];
  const replaced = [];
  const root = new Element("html", {}, dom || [["input", { id: "q" }, []]]);
  globalThis.document = {
    documentElement: root,
    getElementById: (id) => root.querySelectorAll("[id]").find((element) => element.id === id) || null,
    querySelector: (selector) => root.querySelector(selector),
    querySelectorAll: (selector) => root.querySelectorAll(selector),
    createElement: (tag) => new Element(tag),
  };
  const held = typeof storage === "object" ? { ...storage } : null;
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    get() {
      if (storage === "blocked") throw new Error("SecurityError: the browser blocks site data");
      return storage === "throws" ? storageFrom({ throws: true }) : storageFrom({ value: null }, held);
    },
  });
  globalThis.location = { hash, replace: (url) => { replaced.push(url); } };
  globalThis.window = globalThis;
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, method: options.method || "GET" });
    let answer = responses[url];
    if (Array.isArray(answer)) answer = answer.length > 1 ? answer.shift() : answer[0];
    if (!answer) throw new Error("no answer set for " + url);
    if (answer.delay) await new Promise((resolve) => setTimeout(resolve, answer.delay));
    if (answer.reject) throw new Error("the network is down");
    return { status: answer.status, json: async () => answer.body };
  };
  require(SCRIPT);
  for (const key of clicks) {
    const badge = root.querySelectorAll("a[data-column]").find((a) => a.getAttribute("data-column") === key);
    if (!badge) throw new Error("no badge for " + key);
    await badge.fire("click", { type: "click", target: badge, preventDefault() {} });
  }
  const box = document.getElementById("q");
  const pending = [];
  for (const input of inputs) {
    box.value = input.value;
    const done = box.fire("input", { type: "input", target: box });
    if (input.wait === false) pending.push(done);
    else await done;
  }
  await Promise.all(pending);
  const results = document.getElementById("results");
  return { requests, html: results ? results.innerHTML : "", page: root.html(), stored: held, replaced };
}

function picker(op, payload, script) {
  if (op === "readPick") return payload.map((storage) => script.readPick(storageFrom(storage)));
  if (op === "writePick") {
    return payload.map(({ storage, key }) => {
      const held = {};
      let threw = false;
      try {
        script.writePick(storageFrom(storage, held), key);
      } catch (error) {
        threw = true;
      }
      return { threw, stored: held };
    });
  }
  if (op === "rootOf") return payload.map((href) => script.rootOf(href));
  if (op === "redirectFor") return payload.map(([pick, hash]) => script.redirectFor(pick, hash));
  if (op === "headerFor") return payload.map(([pick, root]) => script.headerFor(pick, root));
  if (op === "arrange") return payload.map(([pick, parts, badges]) => script.arrange(pick, parts, badges));
  if (op === "notSoldLine") return payload.map((key) => script.notSoldLine(key));
  if (op === "onBadge") return payload.map(([pick, key]) => script.onBadge(pick, key));
  throw new Error("unknown op " + op);
}

async function main() {
  const op = process.argv[2];
  const payload = JSON.parse(fs.readFileSync(0, "utf8"));
  let answer;
  if (op === "page") {
    answer = await page(payload);
  } else {
    const search = require(SCRIPT);
    if (op === "normalize") answer = payload.map((text) => search.normalize(text));
    else if (op === "pieceFor") answer = payload.queries.map((query) => search.pieceFor(query, payload.pieces));
    else if (op === "matches") answer = search.matches(payload.entries, payload.query);
    else if (op === "barcodeOf") answer = payload.map((text) => search.barcodeOf(text));
    else answer = picker(op, payload, search);
  }
  process.stdout.write(JSON.stringify(answer));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error) + "\n");
  process.exit(1);
});

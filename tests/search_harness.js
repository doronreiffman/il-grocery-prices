"use strict";
/* Loads src/shopper/static/search.js under Node and prints its answers as JSON, for tests/test_search_js.py.

   node tests/search_harness.js <op>     the op's JSON on stdin, its answer as JSON on stdout

   normalize   [text, ...]                                  -> [normalised, ...]
   pieceFor    {pieces: [key, ...], queries: [text, ...]}   -> [key or null, ...]
   matches     {entries: [...], query: text}                -> the matching entries
   barcodeOf   [text, ...]                                  -> [barcode or null, ...]
   page        {inputs: [{value, wait?}, ...], responses: {url: answer or [answer, ...]}}
               types each value into a fake search box (waiting for its answer unless wait is false) with a fake
               fetch that answers {status, body, delay?, reject?} and records every request; the answer is
               {requests: [{url, method}, ...], html: the results box's content}. */
const fs = require("fs");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "src", "shopper", "static", "search.js");

async function page({ inputs, responses }) {
  const requests = [];
  const listeners = {};
  const box = {
    value: "",
    addEventListener(type, listener) { listeners[type] = listener; },
    after() {},
  };
  const results = { innerHTML: "", setAttribute() {} };
  globalThis.document = { getElementById: (id) => (id === "q" ? box : null), createElement: () => results };
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
  const pending = [];
  for (const input of inputs) {
    box.value = input.value;
    const done = listeners.input();
    if (input.wait === false) pending.push(done);
    else await done;
  }
  await Promise.all(pending);
  return { requests, html: results.innerHTML };
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
    else throw new Error("unknown op " + op);
  }
  process.stdout.write(JSON.stringify(answer));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error) + "\n");
  process.exit(1);
});

/**
 * Headless smoke test for the viewer (Node, no dependencies).
 *
 *   node test/viewer_smoke.mjs <viewer.html> [expectations.json]
 *
 * Runs in two phases against a built viewer (`mustrd report --viewer`):
 *
 *  1. The data layer — the page's own Turtle parser, store and model readers —
 *     evaluated on its own, since it touches no DOM. Asserts the run it reads
 *     out of the graph is self-consistent.
 *  2. The whole app, VanJS included, booted against the minimal DOM below and
 *     driven through every tab. VanJS builds real nodes, so the shim implements
 *     just enough of the DOM to construct and serialise a tree.
 *
 * Expectations, if given, are {tests, passed, failed, terms, covered, pct, …} —
 * only the keys present are checked. Exits non-zero with a message on failure.
 */
import { readFileSync } from "node:fs";

const [, , htmlPath, expectPath] = process.argv;
if (!htmlPath) {
  console.error("usage: node test/viewer_smoke.mjs <viewer.html> [expectations.json]");
  process.exit(2);
}
const html = readFileSync(htmlPath, "utf8");

function fail(msg) {
  console.error("viewer smoke test FAILED: " + msg);
  process.exit(1);
}

/* ---------------------------------------------------------------- extraction */
function jsonBlock(id) {
  const re = new RegExp(
    `<script id="${id}" type="application/json">([\\s\\S]*?)</script>`);
  const m = html.match(re);
  if (!m) fail(`no #${id} block in the page`);
  return m[1];
}
const rawData = jsonBlock("mustrd-data");
const ttl = JSON.parse(rawData);
if (typeof ttl !== "string" || !ttl.trim()) fail("embedded data is not a Turtle string");
if (ttl.startsWith("__MUSTRD")) fail("embedded data placeholder was never substituted");

const scripts = [...html.matchAll(
  /<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)];
if (!scripts.length) fail("no app script in the page");
const app = scripts[scripts.length - 1][1];

// The page is assembled from mustrd/templates/viewer/, so the data layer can be
// read from its own sources rather than cut back out of the rendered page. The
// rendered page is still what phase 2 runs, and each part is checked to be in it.
const SRC = new URL("../mustrd/templates/viewer/", import.meta.url);
const part = (name) => readFileSync(new URL(name, SRC), "utf8");
for (const [name, marker] of [
  ["van.js", "let stateProto"],
  ["turtle.js", "function parseTurtle"],
  ["store.js", "function makeStore"],
  ["model.js", "function readTests"],
  ["ui.js", "van.add(document.body, Shell())"],
]) {
  if (!part(name).includes(marker)) fail(`${name} no longer contains ${marker}`);
  if (!app.includes(marker)) fail(`the rendered page did not inline ${name}`);
}
const dataLayer = ["turtle.js", "store.js", "model.js"].map(part).join("\n");

/* ------------------------------------------------------- phase 1: data layer */
const api = eval(dataLayer + `
;({parseTurtle, makeStore, readSpecs, readTests, readCoverage, readCqs, readIssues,
   readRun, sourcesByPath});`);

const parsed = api.parseTurtle(ttl);
if (!parsed.triples.length) fail("parsed 0 triples");
const store = api.makeStore();
store.add(parsed);
const distinct = new Set(parsed.triples.map((t) => t.join(""))).size;
if (store.size() !== distinct) {
  fail(`store holds ${store.size()} of ${distinct} distinct parsed triples`);
}

const specs = api.readSpecs(store);
const model = {
  run: api.readRun(store),
  tests: api.readTests(store, specs),
  coverage: api.readCoverage(store, specs),
  cqs: api.readCqs(store, specs),
  issues: api.readIssues(store, specs),
};

const actual = {
  triples: store.size(),
  tests: model.tests.totals.total,
  passed: model.tests.totals.passed,
  failed: model.tests.totals.failed,
  skipped: model.tests.totals.skipped,
  groups: model.tests.groups.length,
  terms: model.coverage ? model.coverage.declared : 0,
  covered: model.coverage ? model.coverage.covered : 0,
  pct: model.coverage ? model.coverage.pct : 0,
  cqPct: model.coverage ? model.coverage.cqPct : 0,
  ontologies: model.coverage ? model.coverage.ontologies.length : 0,
  cqs: model.cqs.length,
  undeclared: model.issues.undeclared.length,
  tbox: model.issues.tbox.length,
};

for (const t of model.tests.rows) {
  if (!["passed", "failed", "skipped"].includes(t.status)) {
    fail(`bad status ${t.status} on ${t.name}`);
  }
  if (!t.name) fail("a test result has no cov:testName");
}
if (model.coverage) {
  const C = model.coverage;
  if (C.rows.length !== C.declared) {
    fail(`term ordering lost rows: ${C.rows.length} rendered vs ${C.declared} declared`);
  }
  if (new Set(C.rows.map((r) => r.iri)).size !== C.rows.length) {
    fail("duplicate rows in the term tree");
  }
  if (C.denom !== C.declared - C.schema) {
    fail("coverage denominator does not exclude structural terms");
  }
  if (C.pct !== (C.denom ? Math.round((100 * C.covered) / C.denom) : 0)) {
    fail("coverage percentage disagrees with its own counts");
  }
  if (C.ratio != null && Math.abs(C.ratio - C.covered / C.denom) > 0.001) {
    fail(`dqv measurement ${C.ratio} disagrees with recomputed ${C.covered}/${C.denom}`);
  }
}
for (const c of model.cqs) {
  if (!c.questions.length && !c.name) fail("a competency question has no text or name");
}

const embedded = Object.values(specs).flatMap((s) => s.sources || []);
if (embedded.length) {
  actual.sources = embedded.length;
  actual.sourceBytes = embedded.reduce((n, s) => n + s.body.length, 0);
  for (const s of embedded) {
    if (!s.body.trim()) fail(`an embedded source (${s.path || s.media}) is empty`);
    if (!/turtle|sparql/i.test(s.media)) fail(`unexpected media type ${s.media}`);
  }
}

if (expectPath) {
  const want = JSON.parse(readFileSync(expectPath, "utf8"));
  for (const [k, v] of Object.entries(want)) {
    if (actual[k] !== v) fail(`${k}: expected ${v}, got ${actual[k]}`);
  }
}

/* --------------------------------------------------------- a very small DOM */
// Enough for VanJS: element creation, children, attributes, the handful of
// properties it prefers to set directly, and events. Property *descriptors*
// matter — van looks for a setter on the prototype and falls back to
// setAttribute — so the ones a browser exposes are defined here too.
const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input",
  "link", "meta", "source", "track", "wbr"]);

class Node {
  constructor() { this.childNodes = []; this.parentNode = null; this.isConnected = true; }
  append(...kids) {
    for (const k of kids) {
      const node = k instanceof Node ? k : new Text(String(k));
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  remove() {
    const p = this.parentNode;
    if (!p) return;
    p.childNodes.splice(p.childNodes.indexOf(this), 1);
    this.parentNode = null;
    this.isConnected = false;
  }
  replaceWith(other) {
    const p = this.parentNode;
    if (!p) return;
    p.childNodes[p.childNodes.indexOf(this)] = other;
    other.parentNode = p;
    this.parentNode = null;
    this.isConnected = false;
  }
}

class Text extends Node {
  constructor(data) { super(); this.data = String(data); this.nodeType = 3; }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v); }
}

class Element extends Node {
  constructor(tag) {
    super();
    this.nodeType = 1;                           // van checks this to spot a node
    this.tagName = tag;
    this.attributes = {};
    this.listeners = {};
    this.props = {};
  }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; }
  removeAttribute(k) { delete this.attributes[k]; }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
  }
  dispatch(type, ev = {}) {
    for (const fn of this.listeners[type] || []) {
      fn({ target: this, currentTarget: this, preventDefault() {}, ...ev });
    }
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(v) { this.childNodes = []; this.append(String(v)); }
  querySelectorAll(sel) {                        // only "details" is ever asked for
    const want = sel.trim().split(/\s+/).pop();
    const out = [];
    const walk = (n) => {
      for (const c of n.childNodes) {
        if (c instanceof Element) { if (c.tagName === want) out.push(c); walk(c); }
      }
    };
    walk(this);
    return out;
  }
  closest(sel) {
    const want = sel.replace(/^a$/, "a");
    let n = this;
    while (n) {
      if (n instanceof Element && n.tagName === want) return n;
      n = n.parentNode;
    }
    return null;
  }
}
// Properties van prefers over attributes (a browser has setters for these).
for (const [prop, tags] of Object.entries({
  hidden: null, open: null, value: null, checked: null, className: null,
})) {
  void tags;
  Object.defineProperty(Element.prototype, prop, {
    get() { return this.props[prop]; },
    set(v) { this.props[prop] = v; },
    configurable: true,
  });
}

function serialise(node) {
  if (node instanceof Text) return node.data;
  const attrs = Object.entries(node.attributes)
    .map(([k, v]) => ` ${k}="${v}"`).join("");
  const props = Object.entries(node.props)
    .filter(([, v]) => v === true || (v !== false && v != null && v !== ""))
    .map(([k, v]) => (v === true ? ` ${k}` : ` ${k}="${v}"`)).join("");
  const open = `<${node.tagName}${attrs}${props}>`;
  if (VOID.has(node.tagName)) return open;
  return open + node.childNodes.map(serialise).join("") + `</${node.tagName}>`;
}

const documentStub = {
  title: "test",
  createElement: (tag) => new Element(tag),
  createElementNS: (_ns, tag) => new Element(tag),
  createTextNode: (d) => new Text(d),
  documentElement: new Element("html"),
  addEventListener() {},
  getElementById(id) {
    if (id === "mustrd-data") return { textContent: rawData };
    if (id === "mustrd-config") return { textContent: jsonBlock("mustrd-config") };
    const found = this.body.querySelectorAll("*");
    void found;
    const walk = (n) => {
      for (const c of n.childNodes) {
        if (c instanceof Element) {
          if (c.attributes.id === id) return c;
          const hit = walk(c);
          if (hit) return hit;
        }
      }
      return null;
    };
    return walk(this.body);
  },
};
documentStub.body = new Element("body");

/* ------------------------------------------------ phase 2: boot the real app */
globalThis.Text = Text;
const ui = eval(
  "(function(document, window, localStorage, location, FileReader, fetch, URLSearchParams) {" +
  app +
  "\n;return {van, model, tab, query, show, roleOn, sheet, failure, highlight," +
  " liveTabs, TABS, srcRef, setAllOpen};" +
  "})"
)(
  documentStub,
  { addEventListener() {} },
  { getItem: () => null, setItem() {} },
  { search: "" },
  function () {},
  function () { throw new Error("the smoke test must not need the network"); },
  class { getAll() { return []; } get() { return null; } },
);

// VanJS batches DOM updates into a microtask, so every state change needs a
// tick before the DOM reflects it.
const flush = () => new Promise((r) => setTimeout(r, 0));
await flush();

if (!ui.model.val) fail("the app booted without building a model");
if (ui.model.val.store.size() !== store.size()) {
  fail("the booted app loaded a different number of triples");
}

const bodyHtml = () => serialise(documentStub.body);
if (!bodyHtml().includes("spec-by-example")) fail("the page shell did not render");

const rendered = {};
for (const t of ui.liveTabs(ui.model.val)) {
  ui.tab.val = t.id;
  ui.query.val = "";
  await flush();
  const out = bodyHtml();
  if (/undefined|NaN|\[object Object\]/.test(out)) {
    fail(`tab "${t.id}" rendered a placeholder value: ` +
      out.match(/.{0,70}(undefined|NaN|\[object Object\]).{0,70}/)[0]);
  }
  rendered[t.id] = out.length;
}

// Tests tab: every test named, every embedded source present and highlighted.
ui.tab.val = "tests";
await flush();
const testsHtml = bodyHtml();
for (const t of model.tests.rows) {
  if (!testsHtml.includes(t.name)) fail(`tests tab omits "${t.name}"`);
}
if (embedded.length) {
  if (!testsHtml.includes('class="src"')) fail("the tests tab does not show embedded sources");
  if (!/tok-(kw|iri|pname|string)/.test(testsHtml)) fail("embedded source is not highlighted");
  const withPath = embedded.find((s) => s.path);
  if (withPath) {
    // A path whose text is embedded must open in place, not link to the filesystem.
    if (!testsHtml.includes('class="srclink"')) {
      fail(`reference to ${withPath.path} does not open the embedded copy`);
    }
    if (testsHtml.includes(`href="${withPath.path}"`)) {
      fail(`reference to ${withPath.path} still links to the bare path`);
    }
  }
  // Highlighting is pure re-presentation: the tokens must concatenate back.
  const one = embedded[0];
  const joined = ui.highlight(one.body, one.media)
    .map((n) => (typeof n === "string" ? n : n.textContent)).join("");
  if (joined !== one.body) fail("the highlighter altered the source text");
}

// Outcome filters must filter.
ui.show.passed.val = false;
ui.show.failed.val = false;
ui.show.skipped.val = false;
await flush();
if (!bodyHtml().includes("No tests match")) fail("the outcome filters do not filter");
ui.show.passed.val = true;
ui.show.failed.val = true;
ui.show.skipped.val = true;
await flush();

// Coverage tab: every declared term shown, and the term filter filters.
if (model.coverage) {
  ui.tab.val = "coverage";
  await flush();
  const covHtml = bodyHtml();
  for (const r of model.coverage.rows) {
    if (!covHtml.includes(store.short(r.iri))) fail(`coverage tab omits term ${r.iri}`);
  }
  ui.query.val = "zzz-no-such-term";
  await flush();
  if (!bodyHtml().includes("No terms match")) fail("the term filter does not filter");
  ui.query.val = "";
}

// The source sheet opens and closes.
if (embedded.length) {
  const withPath = embedded.find((s) => s.path);
  if (withPath) {
    ui.sheet.val = ui.model.val.sources[withPath.path];
    await flush();
    if (!bodyHtml().includes('class="path"')) fail("the source sheet did not render");
    if (!bodyHtml().includes(withPath.path)) fail("the source sheet omits the path");
    ui.sheet.val = null;
  }
}

console.log(JSON.stringify({ ...actual, rendered }, null, 2));

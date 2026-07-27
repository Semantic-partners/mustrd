/**
 * Headless smoke test for the viewer's data layer (Node, no dependencies).
 *
 * The viewer template carries its own Turtle parser and reads the whole report
 * out of the graph, so that layer is where the risk is — and it is pure: no DOM.
 * This harness slices the template's script up to the rendering section, evals
 * it, and asserts the model it builds from a real run graph.
 *
 *   node test/viewer_smoke.mjs <viewer.html> [expectations.json]
 *
 * `viewer.html` is a built viewer (mustrd report --viewer). Expectations, if
 * given, are {tests, passed, failed, skipped, terms, covered, pct, cqs} — only
 * the keys present are checked. Exits non-zero with a message on failure.
 */
import { readFileSync } from "node:fs";

const [, , htmlPath, expectPath] = process.argv;
if (!htmlPath) {
  console.error("usage: node test/viewer_smoke.mjs <viewer.html> [expectations.json]");
  process.exit(2);
}
const html = readFileSync(htmlPath, "utf8");

/* ---- pull the app script and the embedded run data out of the page ---- */
const dataMatch = html.match(
  /<script id="mustrd-data" type="application\/json">([\s\S]*?)<\/script>/
);
if (!dataMatch) fail("no #mustrd-data block in the page");
const ttl = JSON.parse(dataMatch[1]);
if (typeof ttl !== "string" || !ttl.trim()) fail("embedded data is not a Turtle string");
if (ttl.startsWith("__MUSTRD")) fail("embedded data placeholder was never substituted");

// The last <script> is the app; everything before "5. Rendering helpers" is the
// DOM-free data layer.
const scripts = [...html.matchAll(/<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)];
if (!scripts.length) fail("no app script in the page");
const app = scripts[scripts.length - 1][1];
const cut = app.indexOf("5. Rendering helpers");
if (cut < 0) fail("could not find the rendering-section marker to cut at");
const dataLayer = app.slice(0, app.lastIndexOf("/* =", cut));

const api = eval(dataLayer + "\n;({parseTurtle, makeStore, readSpecs, readTests, readCoverage, readCqs, readIssues, readRun});");

/* ---- parse and build the model, exactly as the page does ---- */
const parsed = api.parseTurtle(ttl);
if (!parsed.triples.length) fail("parsed 0 triples");
const store = api.makeStore();
store.add(parsed);

// Re-serialising is not the job; but every triple must survive interning.
if (store.size() !== new Set(parsed.triples.map((t) => t.join(""))).size) {
  fail(`store holds ${store.size()} of ${parsed.triples.length} parsed triples`);
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

/* ---- invariants that must hold for any run ---- */
for (const t of model.tests.rows) {
  if (!["passed", "failed", "skipped"].includes(t.status)) fail(`bad status ${t.status} on ${t.name}`);
  if (!t.name) fail("a test result has no cov:testName");
}
if (model.coverage) {
  const C = model.coverage;
  if (C.rows.length !== C.declared) {
    fail(`term ordering lost rows: ${C.rows.length} rendered vs ${C.declared} declared`);
  }
  if (new Set(C.rows.map((r) => r.iri)).size !== C.rows.length) fail("duplicate rows in the term tree");
  if (C.denom !== C.declared - C.schema) fail("coverage denominator does not exclude structural terms");
  const expectedPct = C.denom ? Math.round((100 * C.covered) / C.denom) : 0;
  if (C.pct !== expectedPct) fail("coverage percentage disagrees with its own counts");
  // The DQV measurement in the graph must agree with what we recomputed.
  if (C.ratio !== undefined && C.ratio !== null && Math.abs(C.ratio - C.covered / C.denom) > 0.001) {
    fail(`dqv measurement ${C.ratio} disagrees with recomputed ${C.covered}/${C.denom}`);
  }
}
for (const c of model.cqs) {
  if (!c.questions.length && !c.name) fail("a competency question has neither text nor a name");
}

/* ---- declared expectations ---- */
if (expectPath) {
  const want = JSON.parse(readFileSync(expectPath, "utf8"));
  for (const [k, v] of Object.entries(want)) {
    if (actual[k] !== v) fail(`${k}: expected ${v}, got ${actual[k]}`);
  }
}

/* ---- phase 2: boot the whole app against a stub DOM and render every tab ----
   The views are pure string builders, so a stub that records innerHTML is enough
   to prove they run and produce the expected content — no browser needed. */
const configMatch = html.match(
  /<script id="mustrd-config" type="application\/json">([\s\S]*?)<\/script>/
);
const payloads = {
  "mustrd-data": dataMatch[1],
  "mustrd-config": configMatch ? configMatch[1] : "{}",
};
const els = new Map();
function el(id) {
  if (!els.has(id)) {
    els.set(id, {
      id,
      innerHTML: "",
      textContent: payloads[id] !== undefined ? payloads[id] : "",
      value: "",
      hidden: false,
      dataset: {},
      addEventListener() {},
      removeAttribute() {},
      setAttribute() {},
      getAttribute() { return null; },
      focus() {},
      setSelectionRange() {},
      querySelectorAll: () => [],
      closest: () => null,
    });
  }
  return els.get(id);
}
const documentStub = {
  getElementById: el,
  addEventListener() {},
  querySelectorAll: () => [],
  documentElement: {
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
  },
};
const ui = eval(
  "(function(document, window, localStorage, location, FileReader, fetch) {" +
  app +
  "\n;return {state: state, TABS: TABS, renderMain: renderMain, model: M," +
  " highlight: highlight, srcLink: srcLink};" +
  "})"
)(
  documentStub,
  { addEventListener() {} },
  { getItem: () => null, setItem() {} },
  { search: "" },
  function () {},
  function () { throw new Error("the smoke test must not need the network"); }
);

if (!ui.model) fail("the app booted without building a model");
const rendered = {};
for (const tab of ui.TABS) {
  ui.state.tab = tab.id;
  ui.state.q = "";
  ui.renderMain();
  const out = el("main").innerHTML;
  if (!out || out.length < 40) fail(`tab "${tab.id}" rendered nothing`);
  if (/undefined|NaN|\[object Object\]/.test(out)) {
    fail(`tab "${tab.id}" rendered a placeholder value: ` +
      out.match(/.{0,60}(undefined|NaN|\[object Object\]).{0,60}/)[0]);
  }
  rendered[tab.id] = out.length;
}
// The tests tab must name every test, and the coverage tab every declared term.
ui.state.tab = "tests"; ui.renderMain();
const testsHtml = el("main").innerHTML;
for (const t of model.tests.rows) {
  if (!testsHtml.includes(escapeHtml(t.name))) fail(`tests tab omits "${t.name}"`);
}

// Embedded sources: every spec's text must be reachable in the page, references
// to it must open in place rather than link to a path the reader does not have,
// and the highlighter must not corrupt the content.
const embedded = Object.values(specs).flatMap((s) => s.sources || []);
if (embedded.length) {
  actual.sources = embedded.length;
  actual.sourceBytes = embedded.reduce((n, s) => n + s.body.length, 0);
  for (const s of embedded) {
    if (!s.body.trim()) fail(`an embedded source (${s.path || s.media}) is empty`);
    if (!/turtle|sparql/i.test(s.media)) fail(`unexpected media type ${s.media}`);
  }
  if (!testsHtml.includes('class="src"')) fail("the tests tab does not show embedded sources");
  if (!/tok-(kw|iri|pname|string)/.test(testsHtml)) fail("embedded source is not highlighted");
  // A path with embedded text must render as an in-page reference, not an <a href>
  // to the filesystem.
  const withPath = embedded.find((s) => s.path);
  if (withPath) {
    if (!testsHtml.includes(`data-src="${escapeHtml(withPath.path)}"`)) {
      fail(`reference to ${withPath.path} does not open the embedded copy`);
    }
    if (testsHtml.includes(`href="${escapeHtml(withPath.path)}"`)) {
      fail(`reference to ${withPath.path} still links to the bare path`);
    }
  }
  // Highlighting is a pure re-presentation: stripping the tags must give the
  // original text back.
  const one = embedded[0];
  const stripped = ui.highlight(one.body, one.media)
    .replace(/<span class="tok-[a-z]+">/g, "").replace(/<\/span>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
  if (stripped !== one.body) fail("the highlighter altered the source text");
}
if (model.coverage) {
  ui.state.tab = "coverage"; ui.renderMain();
  const covHtml = el("main").innerHTML;
  for (const r of model.coverage.rows) {
    if (!covHtml.includes(escapeHtml(store.short(r.iri)))) {
      fail(`coverage tab omits term ${r.iri}`);
    }
  }
  // The filter must actually filter.
  ui.state.q = "zzz-no-such-term"; ui.renderMain();
  if (!el("main").innerHTML.includes("No terms match")) fail("the term filter does not filter");
}

console.log(JSON.stringify({ ...actual, rendered }, null, 2));

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function fail(msg) {
  console.error("viewer smoke test FAILED: " + msg);
  process.exit(1);
}

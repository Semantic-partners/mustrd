/* ======================================================================
   5. UI — VanJS

   Builds DOM, never HTML strings: text goes in as Text nodes, so there is no
   escaping to get wrong, and state drives the updates. The whole UI is a
   function of six states — the loaded model, the current tab, the filter text,
   the outcome and role toggles, and the open source sheet — bound at the
   smallest useful granularity, so typing in a filter re-renders the list but
   not the toolbar it is typed into.
   ====================================================================== */
const {
  a, abbr, button, code, dd, details, div, dl, dt, em, footer, h1, h2, header,
  input, label, li, main: mainTag, nav, p, pre, section, small, span, strong,
  summary, table, tbody, td, th, thead, tr, ul
} = van.tags;
const { state } = van;

let CFG = {};

/* ---- state ---- */
const model = state(null);                  // the run, read out of the graph
const tab = state("tests");
const query = state("");
const show = { passed: state(true), failed: state(true), skipped: state(true) };
const ROLES = ["covered", "query-only", "schema", "unused"];
const roleOn = Object.fromEntries(ROLES.map(r => [r, state(false)]));
const sheet = state(null);                  // source file shown over the page
const dragging = state(false);
const failure = state("");                  // a load/parse error to surface

/* ---- presentational helpers ---- */
const pill = (kind, txt) => span({ class: "pill " + kind }, txt || kind);
const tick = on => span({ class: on ? "yes" : "no" }, on ? "✓" : "–");
const dur = s => s == null ? "" : s < 1 ? Math.round(s * 1000) + "ms" : s.toFixed(2) + "s";
const secHead = (title, n) =>
  div({ class: "sec-head" }, h2(title), span({ class: "rule" }),
      n === undefined ? [] : span({ class: "n" }, n));
const empty = msg => div({ class: "card" }, p({ class: "empty" }, msg));
const short = iri => model.val ? model.val.store.short(iri) : iri;
const hits = text =>
  !query.val || String(text).toLowerCase().includes(query.val.toLowerCase());

/* ---- source references ----------------------------------------------------
   A path in the graph only resolves from the directory the run happened in, so
   prefer the copy embedded in this page (opens in place), then a configured base
   URL (a repo link, when published from CI), and otherwise plain text rather
   than a link that would 404. */
const srcBase = () => CFG.srcBase || "";

const srcRef = (path, name = path) => {
  if (!path) return name || "";
  const src = model.val?.sources[path];
  if (src) {
    return a({ class: "srclink", href: "#", title: "Show " + path,
               onclick: ev => { ev.preventDefault(); sheet.val = src; } }, name);
  }
  const base = srcBase();
  return base ? a({ href: base + path, title: path }, name)
              : span({ title: path }, name);
};

/* ---- syntax highlighting for the embedded Turtle / SPARQL -----------------
   Returns Text nodes and <span>s, so highlighting cannot alter the content it
   presents. */
const TTL_RE = new RegExp([
  "(#[^\\n]*)",                                                   // comment
  "(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')",
  "(<[^>\\s]*>)",                                                 // IRI
  "(@prefix|@base|\\ba\\b|\\btrue\\b|\\bfalse\\b)",               // keyword
  "([A-Za-z][\\w.-]*:[\\w.\\-%]*)",                               // prefixed name
  "(-?\\b\\d+(?:\\.\\d+)?\\b)"                                    // number
].join("|"), "g");
const TTL_CLASSES = [null, "comment", "string", "iri", "kw", "pname", "num"];

const SPARQL_RE = new RegExp([
  "(#[^\\n]*)",
  "(\"\"\"[\\s\\S]*?\"\"\"|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')",
  "(<[^>\\s]*>)",
  "([?$][A-Za-z_]\\w*)",                                          // variable
  "\\b(SELECT|CONSTRUCT|ASK|DESCRIBE|WHERE|INSERT|DELETE|DATA|GRAPH|OPTIONAL|" +
    "FILTER|BIND|VALUES|UNION|MINUS|SERVICE|PREFIX|BASE|DISTINCT|REDUCED|ORDER|" +
    "GROUP|BY|HAVING|LIMIT|OFFSET|AS|NOT|EXISTS|IN|WITH|USING|FROM|NAMED|SILENT|" +
    "CLEAR|DROP|CREATE|LOAD|INTO|COPY|MOVE|ADD|TRUE|FALSE)\\b",
  "([A-Za-z][\\w.-]*:[\\w.\\-%]*)"
].join("|"), "gi");
const SPARQL_CLASSES = [null, "comment", "string", "iri", "var", "kw", "pname"];

const highlight = (body, media) => {
  const sparql = /sparql/i.test(media || "");
  const re = sparql ? SPARQL_RE : TTL_RE;
  const classes = sparql ? SPARQL_CLASSES : TTL_CLASSES;
  const out = [];
  let last = 0, m;
  re.lastIndex = 0;
  while ((m = re.exec(body)) !== null) {
    if (!m[0].length) { re.lastIndex++; continue; }        // never loop forever
    const cls = classes.find((c, g) => g && m[g] !== undefined);
    if (m.index > last) out.push(body.slice(last, m.index));
    out.push(cls ? span({ class: "tok-" + cls }, m[0]) : m[0]);
    last = m.index + m[0].length;
  }
  if (last < body.length) out.push(body.slice(last));
  return out;
};

const sourceLabel = src =>
  src.path || (/sparql/i.test(src.media) ? "SPARQL (as executed)" : "source");
const codeBlock = src => pre({ class: "code" }, highlight(src.body, src.media));
const sourceDetails = sources => (sources || []).map(src =>
  details({ class: "src" },
    summary(sourceLabel(src), " · ", src.media),
    codeBlock(src)));

/* ---- toolbar pieces ---- */
const searchBox = placeholder => input({
  class: "search", type: "search", placeholder, value: query.val,
  oninput: ev => query.val = ev.target.value
});
const toggleChip = (st, cls, name, count) => button({
  class: "chip " + (cls || ""),
  "aria-pressed": () => String(st.val),
  onclick: () => st.val = !st.val
}, name, count === undefined ? [] : span({ class: "n" }, count));

/** Expand/collapse every disclosure in the results area. Plain DOM: which
    <details> are open is view state the model has no opinion about. */
const setAllOpen = open => document.getElementById("main")
  ?.querySelectorAll("details").forEach(d => d.open = open);

/* ======================================================================
   6. Tabs
   ====================================================================== */
const CHIP_CLASS = { passed: "pass", failed: "fail", skipped: "skip" };

const TestsTab = M => div(
  div({ class: "toolbar" },
    searchBox("Filter tests…"),
    div({ class: "chips" }, Object.keys(show).map(s =>
      toggleChip(show[s], CHIP_CLASS[s], s, M.tests.totals[s] || 0))),
    button({ onclick: () => setAllOpen(true) }, "Expand all"),
    button({ onclick: () => setAllOpen(false) }, "Collapse all")),
  () => TestGroups(M));

const testShown = t => show[t.status]?.val &&
  hits(`${t.name} ${t.module} ${t.cls} ${t.spec ? t.spec.iri : ""}`);

const TestGroups = M => {
  const groups = M.tests.groups.map(g => {
    const visible = g.tests.filter(testShown);
    if (!visible.length) return null;
    return details({ class: "grp", open: visible.some(t => t.status === "failed") || !!query.val },
      summary(
        span({ class: "gname" }, g.label),
        span({ class: "gmeta" },
          g.failed ? pill("failed", g.failed + " failed") : [],
          g.skipped ? pill("skipped", g.skipped + " skipped") : [],
          span(`${visible.length} test${visible.length === 1 ? "" : "s"}`),
          span({ class: "dur" }, dur(g.duration)))),
      ul({ class: "tests" }, visible.map(TestRow)));
  }).filter(Boolean);
  return groups.length ? div({ class: "card" }, groups)
                       : empty("No tests match the current filter.");
};

const termChips = iris => div({ class: "terms" },
  iris.map(t => span({ class: "term-chip", title: t }, short(t))));

const TestRow = t => {
  const kv = [];
  const row = (k, v) => kv.push(dt(k), dd(v));
  if (t.spec) {
    if (t.spec.source) row("spec file", srcRef(t.spec.source));
    row("spec IRI", code(t.spec.iri));
    if (t.spec.inData?.length) row("in data", termChips(t.spec.inData));
    if (t.spec.inQuery?.length) row("in SPARQL", termChips(t.spec.inQuery));
    const answers = model.val.cqs.filter(c =>
      c.tests.some(x => x.spec && x.spec.iri === t.spec.iri));
    if (answers.length) row("answers", answers.map(c => div(c.questions[0] || c.name)));
  } else if (t.source) {
    row("file", srcRef(t.source));
  }
  if (t.type) row("type", t.type);

  const sources = sourceDetails(t.spec?.sources);
  return li(details(
    summary({ class: "t" },
      pill(t.status),
      span({ class: "name" }, t.name),
      span({ class: "right" }, span({ class: "dur" }, dur(t.duration)))),
    kv.length || sources.length
      ? div({ class: "detail" }, kv.length ? dl({ class: "kv" }, kv) : [], sources)
      : []));
};

const CoverageTab = M => {
  const C = M.coverage;
  if (!C) {
    return empty(["This run has no ontology term coverage. Re-run with ",
                  code("--term-coverage"), ", and declare ",
                  code("mustrdTest:hasOntologyPath"), " in the config."]);
  }
  const count = role => Object.values(C.terms).filter(t => t.role === role).length;
  return div(
    div({ class: "toolbar" },
      searchBox("Filter terms…"),
      div({ class: "chips" }, ROLES.map(r => toggleChip(roleOn[r], "", r, count(r))))),
    p({ class: "note" },
      "A term counts as ", strong("covered"), " when a passing test ",
      strong("populates it in input data"), ". A term named only in a query is ",
      strong("query-only"), " and does not count. ", strong("structural"),
      " terms are load-bearing but excluded from the denominator. Classes nest by ",
      code("rdfs:subClassOf"), " (↳), properties under their ", code("rdfs:domain"),
      " (▸). Click a row for the per-test breakdown."),
    div({ class: "card tblwrap" }, table(
      thead(tr(
        th("Term"), th("Kind"),
        th({ class: "c" }, abbr({ title: "A passing test asserts the term in its given data" }, "In data")),
        th({ class: "c" }, abbr({ title: "A passing test's SPARQL names the term" }, "In SPARQL")),
        th({ class: "c" }, "Test coverage"),
        th({ class: "c" }, "CQ coverage"))),
      () => TermRows(C))),
    C.ontologies.length
      ? [secHead("Ontologies measured", C.ontologies.length),
         div({ class: "card" }, C.ontologies.map(OntologyCard))]
      : []);
};

const OntologyCard = o => div({ class: "cq" },
  p({ class: "q mono" }, o.iri),
  o.comment ? p({ class: "note" }, o.comment) : [],
  o.path ? p({ class: "note" }, srcRef(o.path)) : [],
  o.version ? p({ class: "note mono" }, "version: " + o.version) : []);

const TermRows = C => {
  const anyRole = ROLES.some(r => roleOn[r].val);
  const rows = [];
  C.rows
    .filter(r => (!anyRole || roleOn[r.t.role].val) && hits(`${short(r.iri)} ${r.iri}`))
    .forEach(({ iri, depth, glyph, t }) => {
      const pad = depth * 1.15;
      // Per-row disclosure: a bound `hidden`, so expanding one term does not
      // rebuild the table.
      const open = state(false);
      const hidden = () => !open.val;
      const indent = extra => `padding-left:${pad + extra}rem`;

      rows.push(tr({ class: "term", title: iri,
                     onclick: ev => { if (!ev.target.closest("a")) open.val = !open.val; } },
        td({ class: "tname", style: indent(0.7) },
           glyph ? [span({ class: "glyph" }, glyph), " "] : [], short(iri)),
        td(t.kind),
        td({ class: "c" }, tick(t.inData)),
        td({ class: "c" }, tick(t.inQuery)),
        td({ class: "c" }, pill(t.role)),
        td({ class: "c" }, t.cqRole ? pill(t.cqRole) : [])));

      if (t.reasons.length) {
        rows.push(tr({ class: "ex", hidden },
          td({ colspan: 6, class: "note", style: indent(2.2) },
             "structural because: " + t.reasons.join("; "))));
      }
      t.exercises.forEach(e => rows.push(tr({ class: "ex", hidden },
        td({ style: indent(2.2) },
           span({ class: "glyph" }, "•"), " ", srcRef(e.source, e.name)),
        td(), td({ class: "c" }, tick(e.inData)), td({ class: "c" }, tick(e.inQuery)),
        td(), td())));
    });
  return tbody(rows.length ? rows : tr(td({ colspan: 6, class: "empty" }, "No terms match.")));
};

const CqsTab = M => {
  if (!M.cqs.length) {
    return empty(["No competency questions in this graph. Re-run with ", code("--cq"), "."]);
  }
  return div(
    div({ class: "toolbar" }, searchBox("Filter questions…")),
    () => {
      const cards = M.cqs
        .filter(c => hits(c.questions.join(" ") + " " + c.name))
        .map(CqCard);
      return cards.length ? div({ class: "card" }, cards) : empty("No questions match.");
    });
};

const cqBadges = c => [
  c.duplicate ? pill("query-only", "duplicate question") : [],
  !c.tests.length ? pill("unused", "no linked test")
    : c.tests.some(t => t.status === "failed") ? pill("failed", "failing")
    : pill("passed", "verified")
];

const CqCard = c => div({ class: "cq" },
  p({ class: "q" }, c.questions[0] || c.name),
  div({ class: "badges" }, cqBadges(c)),
  c.questions.length > 1
    ? p({ class: "note" }, "also asked as: " + c.questions.slice(1).join(" · ")) : [],
  c.tests.length || c.missing.length
    ? ul(
        c.tests.map(t => li(
          pill(t.status || "plain", t.status || "unknown"), " ",
          t.spec ? srcRef(t.spec.source, t.spec.name) : "?",
          t.requiresOntology ? [" ", pill("schema", "needs ontology")] : [])),
        c.missing.map(iri => li({ class: "warnrow" },
          "cq:cqSpec points at ", code(iri),
          ", which no test in this run provides")))
    : [],
  c.source ? p({ class: "note" }, "defined in ", srcRef(c.source)) : []);

const where = r =>
  " — " + [r.inData && "in data", r.inQuery && "in SPARQL"].filter(Boolean).join(" and ");

const IssuesTab = M => {
  const { undeclared, tbox } = M.issues;
  if (!undeclared.length && !tbox.length) return empty("No quality issues found in this run. ✨");
  return div(
    undeclared.length ? [
      secHead("Used but not declared", undeclared.length),
      p({ class: "note" },
        "Terms a test references inside a measured ontology’s namespace that the " +
        "ontology never declares — usually a typo or a missing definition."),
      div({ class: "card" }, undeclared.map(u => div({ class: "cq" },
        p({ class: "q mono" }, short(u.term)),
        p({ class: "note mono" }, u.term),
        ul(u.refs.map(r => li(srcRef(r.source, r.name),
                              span({ class: "note" }, where(r))))))))
    ] : [],
    tbox.length ? [
      secHead("TBox in test data", tbox.length),
      p({ class: "note" },
        "Schema axioms found in a test’s input data, where only instance data belongs."),
      div({ class: "card" }, tbox.map(t => div({ class: "cq" },
        p({ class: "q" }, srcRef(t.source, t.name)),
        ul(t.axioms.map(ax => li({ class: "mono" }, ax))))))
    ] : []);
};

const SourceTab = M => {
  const prefixes = Object.keys(M.store.prefixes).sort();
  return div(
    div({ class: "toolbar" },
      M.raw ? a({ class: "btn", download: "mustrd-run.ttl",
                  href: "data:text/turtle;charset=utf-8," + encodeURIComponent(M.raw) },
                "Download TTL") : [],
      span({ class: "note" }, `${M.store.size()} triples, ${prefixes.length} prefixes`)),
    prefixes.length
      ? div({ class: "card tblwrap" }, table(
          thead(tr(th("Prefix"), th("Namespace"))),
          tbody(prefixes.map(pfx => tr(td({ class: "mono" }, pfx + ":"),
                                       td({ class: "mono" }, M.store.prefixes[pfx]))))))
      : [],
    M.raw
      ? [secHead("Turtle"),
         div({ class: "card" }, pre({
           class: "code", style: "max-height:70vh;border:none;border-radius:0"
         }, highlight(M.raw, "text/turtle")))]
      : []);
};

const TABS = [
  { id: "tests", label: "Tests", count: M => M.tests.totals.total, view: TestsTab },
  { id: "coverage", label: "Coverage", count: M => M.coverage ? M.coverage.declared : 0, view: CoverageTab },
  { id: "cqs", label: "Competency questions", count: M => M.cqs.length, view: CqsTab },
  { id: "issues", label: "Issues", count: M => M.issues.undeclared.length + M.issues.tbox.length, view: IssuesTab },
  { id: "source", label: "Source", count: () => null, view: SourceTab }
];

const liveTabs = M => {
  const live = TABS.filter(t => { const c = t.count(M); return c === null || c > 0; });
  return live.length ? live : [TABS.at(-1)];
};

/* ======================================================================
   7. Summary tiles, shell
   ====================================================================== */
const bar = parts => div({ class: "bar" },
  parts.filter(([, pct]) => pct > 0)
       .map(([cls, pct]) => span({ class: cls, style: `width:${pct}%` })));

const tile = (name, big, sub, parts) => div({ class: "tile" },
  div({ class: "label" }, name),
  div({ class: "big" }, big[0], " ", small(big[1])),
  div({ class: "sub" }, sub),
  parts ? bar(parts) : []);

const Tiles = M => {
  const tiles = [], t = M.tests.totals, C = M.coverage;
  if (t.total) {
    const pc = k => 100 * (t[k] || 0) / t.total;
    tiles.push(tile("Tests", [t.passed || 0, `/ ${t.total} passed`],
      `${t.failed || 0} failed · ${t.skipped || 0} skipped · ${dur(t.duration)}`,
      [["p", pc("passed")], ["f", pc("failed")], ["s", pc("skipped")]]));
  }
  if (C) {
    tiles.push(tile("Term coverage by tests", [C.pct + "%", `${C.covered}/${C.denom} terms`],
      `${C.declared} declared · ${C.schema} structural excluded`, [["c", C.pct]]));
    if (C.hasCq) {
      tiles.push(tile("Coverage by competency question",
        [C.cqPct + "%", `${C.coveredCq}/${C.denom} terms`],
        `${C.covered - C.coveredCq} covered by tests but no CQ`, [["q", C.cqPct]]));
    }
  }
  if (M.cqs.length) {
    const verified = M.cqs.filter(c =>
      c.tests.length && c.tests.every(x => x.status === "passed")).length;
    tiles.push(tile("Competency questions", [verified, `/ ${M.cqs.length} verified`],
      `${M.cqs.filter(c => !c.tests.length).length} with no linked test`,
      [["p", 100 * verified / M.cqs.length]]));
  }
  return section({ class: "tiles" }, tiles);
};

const RunMeta = M => {
  const { run } = M, bits = [];
  const item = (k, v) => bits.push(span(span({ class: "k" }, k), " ", v));
  if (run.slug && run.slug !== "local") item("run", code(run.slug.slice(0, 12)));
  if (run.commit) item("commit", a({ href: run.commit }, localName(run.commit).slice(0, 8)));
  if (run.version) item("mustrd", run.version);
  item("triples", String(M.store.size()));
  return div({ class: "runmeta" }, bits);
};

/** Cycle explicit light → explicit dark → follow the OS. */
const toggleTheme = () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "light" ? "dark" : cur === "dark" ? "" : "light";
  if (next) document.documentElement.setAttribute("data-theme", next);
  else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("mustrd-theme", next); } catch (e) { /* private mode */ }
};

const NoData = () => div({ class: "card" }, p({ class: "empty" },
  "No run data loaded.", div(), div(),
  "Drop a ", code(".ttl"), " / ", code(".jsonld"), " from ",
  code("mustrd report --term-coverage-rdf"), " or ", code("--results-rdf"),
  " onto this page, use ", em("Load TTL"), ", or append ",
  code("?ttl=path/to/run.ttl"), " to the URL."));

const Shell = () => [
  div({ class: "wrap" },
    header({ class: "top" },
      div(
        p({ class: "eyebrow" }, "mustrd · spec-by-example for RDF & SPARQL"),
        div({ class: "brand" }, span({ class: "dot" }),
            h1({ id: "pageTitle" }, document.title || "Run report")),
        () => model.val ? RunMeta(model.val) : div({ class: "runmeta" })),
      div({ class: "actions" },
        label({ class: "btn" }, "Load TTL", input({
          type: "file", hidden: true, multiple: true,
          accept: ".ttl,.turtle,.n3,.nt,.jsonld,.json",
          onchange: ev => loadFiles(ev.target.files)
        })),
        button({ title: "Toggle light / dark", onclick: toggleTheme }, "◐"))),

    () => model.val ? Tiles(model.val) : section({ class: "tiles" }),

    nav({ class: "tabs", role: "tablist" }, () => {
      const M = model.val;
      return div({ class: "tabrow" }, !M ? [] : liveTabs(M).map(t => button({
        role: "tab", "data-tab": t.id,
        "aria-selected": () => String(tab.val === t.id),
        onclick: () => { tab.val = t.id; query.val = ""; }
      }, t.label, t.count(M) === null ? [] : span({ class: "n" }, t.count(M)))));
    }),

    mainTag({ id: "main" }, () => {
      if (failure.val) return div({ class: "err" }, failure.val);
      const M = model.val;
      if (!M?.store.size()) return NoData();
      const live = liveTabs(M);
      return (live.find(t => t.id === tab.val) || live[0]).view(M);
    }),

    footer(() => div(
      "Rendered in the browser from ",
      strong(model.val ? String(model.val.store.size()) : "0"),
      " triples of RDF (", code("cov:"), "/", code("must:"), "/", code("cq:"), "/",
      code("dqv:"), "). Drop another ", code(".ttl"), " or ", code(".jsonld"),
      " anywhere on the page to merge it in."))),

  div({ class: "drop", hidden: () => !dragging.val },
    div({ class: "inner" }, "Drop ", code(".ttl"), " / ", code(".jsonld"), " to load")),

  div({ class: "sheet", hidden: () => !sheet.val,
        onclick: ev => { if (ev.target === ev.currentTarget) sheet.val = null; } },
    () => div({ class: "panel" },
      div({ class: "head" },
        span({ class: "path" },
              sheet.val ? `${sourceLabel(sheet.val)}  ·  ${sheet.val.media}` : ""),
        button({ onclick: () => sheet.val = null }, "Close ✕")),
      sheet.val ? codeBlock(sheet.val) : pre({ class: "code" })))
];

/* ======================================================================
   8. Loading data
   ====================================================================== */
const STORE = makeStore();
let RAW = "";

const rebuild = () => {
  const specs = readSpecs(STORE);
  model.val = {
    store: STORE, raw: RAW, specs, sources: sourcesByPath(specs),
    run: readRun(STORE),
    tests: readTests(STORE, specs),
    coverage: readCoverage(STORE, specs),
    cqs: readCqs(STORE, specs),
    issues: readIssues(STORE, specs)
  };
  // Keep the selected tab valid as data arrives — a results-only graph has no
  // Coverage tab, for instance.
  const live = liveTabs(model.val);
  if (!live.some(t => t.id === tab.val)) tab.val = live[0].id;
};

const ingest = (name, body) => {
  STORE.add(/\.(jsonld|json)$/i.test(name) ? parseJsonLd(body) : parseTurtle(body));
  RAW = RAW ? `${RAW}\n\n# ---- ${name} ----\n${body}` : body;
  failure.val = "";
  rebuild();
};

const loadFiles = files => [...files].forEach(f => {
  const reader = new FileReader();
  reader.onload = () => {
    try { ingest(f.name, String(reader.result)); }
    catch (e) { failure.val = `${f.name}: ${e.message}`; }
  };
  reader.readAsText(f);
});

/* ---- page-level events ---- */
document.addEventListener("keydown", ev => { if (ev.key === "Escape") sheet.val = null; });
let dragDepth = 0;
window.addEventListener("dragenter", ev => {
  ev.preventDefault();
  if (++dragDepth === 1) dragging.val = true;
});
window.addEventListener("dragover", ev => ev.preventDefault());
window.addEventListener("dragleave", () => {
  if (--dragDepth <= 0) { dragDepth = 0; dragging.val = false; }
});
window.addEventListener("drop", ev => {
  ev.preventDefault();
  dragDepth = 0;
  dragging.val = false;
  if (ev.dataTransfer?.files.length) loadFiles(ev.dataTransfer.files);
});

/* ---- boot: mount, then the inlined data, then ?ttl= ---- */
(() => {
  const readJson = id => {
    try { return JSON.parse(document.getElementById(id).textContent); }
    catch (e) { return null; }
  };
  CFG = readJson("mustrd-config") || {};

  try {
    const saved = localStorage.getItem("mustrd-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
  } catch (e) { /* private mode */ }

  const params = new URLSearchParams(location.search);
  const title = params.get("title");
  if (title) document.title = title;

  van.add(document.body, Shell());

  const inline = readJson("mustrd-data");
  if (typeof inline === "string" && inline.trim()) {
    try { ingest("run.ttl", inline); }
    catch (e) { failure.val = "Embedded data: " + e.message; }
  }

  params.getAll("ttl").concat(params.getAll("jsonld")).forEach(url =>
    fetch(url)
      .then(r => r.ok ? r.text() : Promise.reject(new Error(`${r.status} ${r.statusText}`)))
      .then(body => ingest(url, body))
      .catch(e => failure.val = `Could not load ${url}: ${e.message}`));
})();

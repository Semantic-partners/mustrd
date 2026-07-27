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
const filePick = state(null);               // id of the file open in the Files tab
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
               onclick: ev => {
                 ev.preventDefault();
                 copied.val = false;          // no stale "Copied ✓" on a new file
                 sheet.val = src;
               } }, name);
  }
  const base = srcBase();
  return base ? a({ href: base + path, title: path }, name)
              : span({ title: path }, name);
};

/* ---- syntax highlighting for the embedded Turtle / SPARQL -----------------
   A token walk rather than a chain of replacements, because two things a reader
   of a mustrd spec actually needs cannot be done with a flat regex:

   Nested SPARQL. A spec's query arrives as `must:queryText """SELECT …"""`. As
   one string token that is a wall of a single colour, which is exactly the part
   you came to read. So the walk remembers the predicate it just passed, and when
   a long string belongs to a query predicate — or simply opens like a query —
   its contents are highlighted as SPARQL inside the quotes.

   Navigable references. `must:file "mayor.ttl"` names a file this page has
   embedded (see sources_rdf.py). Rendered as a link, it opens that file, so a
   spec can be read outwards to its data instead of dead-ending at a name.

   Everything is Text nodes and <span>s, so highlighting can only ever change how
   the source looks, never what it says. */

const TOKEN = {
  turtle: {
    re: new RegExp([
      "(#[^\\n]*)",                                             // 1 comment
      "(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?''')",              // 2 long string
      "(\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')", // 3 short string
      "(<[^>\\s]*>)",                                           // 4 IRI
      "(@prefix|@base|\\bPREFIX\\b|\\bBASE\\b)",                // 5 directive
      "(\\ba\\b|\\btrue\\b|\\bfalse\\b)",                       // 6 keyword
      "(\\^\\^|@[A-Za-z][\\w-]*)",                              // 7 datatype / language
      "([A-Za-z][\\w.-]*:[\\w.\\-%]*)",                         // 8 prefixed name
      "(_:[\\w.-]+)",                                           // 9 blank node
      "(-?\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)",           // 10 number
      "([;,.\\[\\]()])"                                         // 11 punctuation
    ].join("|"), "g"),
    classes: [null, "comment", "string", "string", "iri", "kw", "kw", "suffix",
              "pname", "bnode", "num", "punct"],
    long: 2, short: 3, iri: 4, pname: 8, punct: 11
  },
  sparql: {
    re: new RegExp([
      "(#[^\\n]*)",                                             // 1 comment
      "(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?''')",              // 2 long string
      "(\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')", // 3 short string
      "(<[^>\\s]*>)",                                           // 4 IRI
      "([?$][A-Za-z_]\\w*)",                                    // 5 variable
      "\\b(SELECT|CONSTRUCT|ASK|DESCRIBE|WHERE|INSERT|DELETE|DATA|GRAPH|" +
        "OPTIONAL|FILTER|BIND|VALUES|UNION|MINUS|SERVICE|PREFIX|BASE|DISTINCT|" +
        "REDUCED|ORDER|GROUP|BY|HAVING|LIMIT|OFFSET|AS|NOT|EXISTS|IN|WITH|" +
        "USING|FROM|NAMED|SILENT|CLEAR|DROP|CREATE|LOAD|INTO|COPY|MOVE|ADD|" +
        "TRUE|FALSE|A)\\b",                                     // 6 keyword
      "\\b(COUNT|SUM|MIN|MAX|AVG|SAMPLE|GROUP_CONCAT|STR|LANG|DATATYPE|BOUND|" +
        "IRI|URI|BNODE|RAND|ABS|CEIL|FLOOR|ROUND|CONCAT|STRLEN|UCASE|LCASE|" +
        "CONTAINS|STRSTARTS|STRENDS|STRBEFORE|STRAFTER|REPLACE|REGEX|NOW|YEAR|" +
        "MONTH|DAY|HOURS|MINUTES|SECONDS|COALESCE|IF|SAMETERM|ISIRI|ISBLANK|" +
        "ISLITERAL|ISNUMERIC)\\b",                              // 7 function
      "(\\^\\^|@[A-Za-z][\\w-]*)",                              // 8 datatype / language
      "([A-Za-z][\\w.-]*:[\\w.\\-%]*)",                         // 9 prefixed name
      "(-?\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)",           // 10 number
      // Punctuation, including the property-path operators — `a/rdfs:subClassOf*`
      // is idiomatic in these specs and reads badly as undifferentiated text.
      "([{};,.()\\[\\]*/|!+?^-])"                               // 11 punctuation
    ].join("|"), "gi"),
    classes: [null, "comment", "string", "string", "iri", "var", "kw", "fn",
              "suffix", "pname", "num", "punct"],
    long: 2, short: 3, iri: 4, pname: 9, punct: 11
  }
};

/** Predicates whose value is a query, and the shape of a query that arrives
    without one (a bare string dropped into the page, say). */
const QUERY_PREDICATE = /(?:^|:)(?:queryText|queryString|query)$/i;
const LOOKS_LIKE_QUERY =
  /^\s*(?:#[^\n]*\n\s*)*(PREFIX|BASE|SELECT|CONSTRUCT|ASK|DESCRIBE|INSERT|DELETE|WITH)\b/i;

const tok = (cls, s) => cls ? span({ class: "tok-" + cls }, s) : s;

/** The embedded file a spec's reference names, if this page has it. */
const findSource = ref => {
  const index = model.val && model.val.sourceRefs;
  if (!index || !ref) return null;
  return index[ref]
    || index[String(ref).replace(/^file:\/\//, "").replace(/^\.\//, "")]
    || index[String(ref).split("/").pop()]
    || null;
};

const quoteOf = raw =>
  raw.startsWith('"""') ? '"""' : raw.startsWith("'''") ? "'''" : raw[0];

const fileLink = (src, name) => a({
  class: "srclink tok-file", href: "#", title: `Show ${src.path}`,
  onclick: ev => { ev.preventDefault(); copied.val = false; sheet.val = src; }
}, name);

/** A string token: SPARQL inside the quotes when it is a query, a link when it
    names a file this page carries, and otherwise just a string. */
const stringToken = (raw, predicate) => {
  const quote = quoteOf(raw);
  const inner = raw.slice(quote.length, raw.length - quote.length);
  const wrap = body => [tok("string", quote), body, tok("string", quote)].flat();

  if (QUERY_PREDICATE.test(predicate || "") || LOOKS_LIKE_QUERY.test(inner)) {
    return wrap(highlightAs(inner, "sparql"));
  }
  const src = findSource(inner);
  return src ? wrap(fileLink(src, inner)) : tok("string", raw);
};

/** An IRI token. A file can be named as one too — `must:fileurl
    <file://./select-query.sparql>` — so it gets the same treatment as a string
    that names a file. */
const iriToken = raw => {
  const inner = raw.slice(1, -1);
  const src = findSource(inner);
  return src
    ? [tok("punct", "<"), fileLink(src, inner), tok("punct", ">")]
    : tok("iri", raw);
};

const highlightAs = (body, lang) => {
  const { re, classes, long, short, iri, pname, punct } = TOKEN[lang];
  const out = [];
  let last = 0, m, predicate = null;
  re.lastIndex = 0;
  while ((m = re.exec(body)) !== null) {
    if (!m[0].length) { re.lastIndex++; continue; }        // never loop forever
    if (m.index > last) out.push(body.slice(last, m.index));
    last = m.index + m[0].length;

    const group = classes.findIndex((c, g) => g && m[g] !== undefined);
    if (group === long || group === short) {
      out.push(stringToken(m[0], predicate));
      continue;
    }
    if (group === iri) { out.push(iriToken(m[0])); continue; }
    if (group === pname) predicate = m[0];
    else if (group === punct && (m[0] === ";" || m[0] === ".")) predicate = null;
    out.push(tok(classes[group], m[0]));
  }
  if (last < body.length) out.push(body.slice(last));
  return out.flat();
};

/** Which grammar, if any, fits a media type. N-Triples and N-Quads are Turtle
    subsets so they read correctly as Turtle; a CSV or an EDN file does not, and
    gets left alone rather than mis-coloured. */
const grammarFor = media => {
  const m = String(media || "");
  if (/sparql/i.test(m)) return "sparql";
  if (/turtle|n-triples|n-quads|trig|n3/i.test(m)) return "turtle";
  return null;
};

const highlight = (body, media) => {
  const lang = grammarFor(media);
  return lang ? highlightAs(body, lang) : [body];
};

const sourceLabel = src =>
  src.path || (/sparql/i.test(src.media) ? "SPARQL (as executed)" : "source");

/* ---- taking a file with you ---- */
const fileName = src => src.path ? src.path.split("/").pop()
  : /sparql/i.test(src.media) ? "query.rq" : "source.ttl";

const dataHref = src =>
  `data:${src.media};charset=utf-8,${encodeURIComponent(src.body)}`;

/** Copy without the Clipboard API where it is unavailable — which includes a
    report opened over plain http, or from file:// in some browsers. */
const selectAndCopy = body => {
  const area = document.createElement("textarea");
  area.value = body;
  area.setAttribute("readonly", "");
  area.setAttribute("style", "position:fixed;left:-9999px;top:0");
  document.body.appendChild(area);
  area.select();
  try { document.execCommand("copy"); } finally { area.remove(); }
};

const copyText = body => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(body).catch(() => selectAndCopy(body));
    }
  } catch (e) { /* fall through */ }
  selectAndCopy(body);
  return Promise.resolve();
};

const copied = state(false);
let copiedTimer = null;

const copyButton = body => button({
  title: "Copy to the clipboard",
  onclick: () => {
    copyText(body);
    copied.val = true;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => copied.val = false, 1600);
  }
}, () => copied.val ? "Copied ✓" : "Copy");

const downloadButton = src => a({
  class: "btn", download: fileName(src), href: dataHref(src),
  title: `Download ${fileName(src)}`
}, "Download");

const fileActions = src => div({ class: "btns" }, downloadButton(src), copyButton(src.body));
const codeBlock = src => pre({ class: "code" }, highlight(src.body, src.media));
const sourceDetails = sources => (sources || []).map(src =>
  details({ class: "src" },
    summary(sourceLabel(src), " · ", src.media),
    codeBlock(src)));

/* ---- toolbar pieces ---- */
/** Note `rawVal`, not `val`.

    Reading `query.val` here would register the filter state as a dependency of
    whichever binding is rendering the toolbar — the tab body — so every keystroke
    would rebuild the toolbar, replace this input, and take the caret with it.
    `rawVal` seeds the field without subscribing, leaving the only subscribers the
    inner bindings that render the filtered list. */
const searchBox = placeholder => input({
  class: "search", type: "search", placeholder, value: query.rawVal,
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

/* ---- Files ----------------------------------------------------------------
   Everything the run read, in one place. Reachable by clicking a reference in a
   spec too, but that opens the sheet over what you were reading; this is for
   browsing what the report actually carries — often the first surprise is how
   much that is. */
const FILE_GROUPS = ["Specs", "Queries", "Data"];

const fileEntry = src => button({
  class: "fileitem",
  "aria-pressed": () => String(filePick.val === src.id),
  onclick: () => filePick.val = src.id
},
  span({ class: "fname" }, src.path ? src.path.split("/").pop() : "query"),
  span({ class: "fmeta" }, src.path ? src.path.replace(/\/[^/]*$/, "") : localName(src.owner)));

const FilesTab = M => div(
  div({ class: "toolbar" },
    searchBox("Filter files…"),
    span({ class: "note" },
      `${M.files.length} file${M.files.length === 1 ? "" : "s"} embedded in this report`)),
  () => FilePane(M));

/** Matches on content as well as name: finding which spec mentions a term is the
    thing you actually want from a filter over a pile of Turtle. */
const fileHits = src =>
  hits(`${src.path || ""} ${src.owner} ${src.media}`) ||
  (query.val.length > 2 && hits(src.body));

const FilePane = M => {
  const files = M.files.filter(fileHits);
  if (!files.length) return empty("No files match.");

  const chosen = files.find(f => f.id === filePick.val) || files[0];
  return div({ class: "filepane" },
    div({ class: "filelist card" }, FILE_GROUPS.map(group => {
      const inGroup = files.filter(f => f.group === group);
      return inGroup.length
        ? [div({ class: "filegroup" }, group, span({ class: "n" }, inGroup.length)),
           inGroup.map(fileEntry)]
        : [];
    })),
    div({ class: "card filebody" },
      div({ class: "head" },
        span({ class: "path" }, sourceLabel(chosen), " · ", chosen.media),
        fileActions(chosen)),
      codeBlock(chosen)));
};

const GraphTab = M => {
  const prefixes = Object.keys(M.store.prefixes).sort();
  const graph = { path: "mustrd-run.ttl", media: "text/turtle", body: M.raw };
  return div(
    div({ class: "toolbar" },
      M.raw ? fileActions(graph) : [],
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
  { id: "files", label: "Files", count: M => M.files.length, view: FilesTab },
  { id: "graph", label: "Graph", count: () => null, view: GraphTab }
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
      code("dqv:"), "). Drop another mustrd run — ", code(".ttl"), " or ",
      code(".jsonld"), " — anywhere on the page to merge it in."))),

  div({ class: "drop", hidden: () => !dragging.val },
    div({ class: "inner" }, "Drop ", code(".ttl"), " / ", code(".jsonld"), " to load")),

  div({ class: "sheet", hidden: () => !sheet.val,
        onclick: ev => { if (ev.target === ev.currentTarget) sheet.val = null; } },
    () => div({ class: "panel" },
      div({ class: "head" },
        span({ class: "path" },
              sheet.val ? `${sourceLabel(sheet.val)}  ·  ${sheet.val.media}` : ""),
        div({ class: "btns" },
          sheet.val ? [downloadButton(sheet.val), copyButton(sheet.val.body)] : [],
          button({ onclick: () => sheet.val = null }, "Close ✕"))),
      sheet.val ? codeBlock(sheet.val) : pre({ class: "code" })))
];

/* ======================================================================
   8. Loading data
   ====================================================================== */
const STORE = makeStore();
let RAW = "";

const rebuild = () => {
  const specs = readSpecs(STORE);
  const index = sourceIndex(specs);
  model.val = {
    store: STORE, raw: RAW, specs,
    sources: index.byPath, sourceRefs: index.byRef, files: index.list,
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

/** The reader in turtle.js is compact by design (see its header). It covers what
    mustrd emits and ordinary Turtle besides, but it is not a conformance-tested
    parser — so when it gives up on someone else's file, say which limitation
    they have hit and point at the path that uses JSON.parse instead. */
const loadError = (name, message) => /\.(jsonld|json)$/i.test(name)
  ? `${name}: ${message}`
  : `${name}: ${message}

This page reads Turtle with a small parser that covers what mustrd emits — it \
does not implement RDF-star, TriG named graphs, or every Turtle corner. If the \
file is valid, convert it (rdflib: --term-coverage-jsonld / --results-jsonld, or \
riot --output=jsonld) and drop the JSON-LD instead.`;

const loadFiles = files => [...files].forEach(f => {
  const reader = new FileReader();
  reader.onload = () => {
    try { ingest(f.name, String(reader.result)); }
    catch (e) { failure.val = loadError(f.name, e.message); }
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

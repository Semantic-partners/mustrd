/* ======================================================================
   4. Model — read the run out of the graph
   ====================================================================== */
var OUTCOME = {};
OUTCOME[COV + "Passed"] = "passed";
OUTCOME[COV + "Failed"] = "failed";
OUTCOME[COV + "Skipped"] = "skipped";
var ROLE = {};
ROLE[COV + "Covered"] = "covered";
ROLE[COV + "QueryOnly"] = "query-only";
ROLE[COV + "Structural"] = "schema";
ROLE[COV + "Unused"] = "unused";

function outcomeOf(st, s, p) {
  var o = st.one(s, p);
  return o && isIri(o) ? (OUTCOME[iriOf(o)] || "failed") : null;
}

/** cov:SourceFile nodes attached to a spec: the verbatim Turtle it is defined by
    and the SPARQL it ran, so the report needs no access to the original files. */
function readSources(st, s) {
  return st.objs(s, COV + "embeddedSource").map(function (n) {
    return {
      path: text(st.one(n, COV + "filePath")),
      media: text(st.one(n, COV + "mediaType")) || "text/turtle",
      body: text(st.one(n, COV + "fileText")) || ""
    };
  }).sort(function (a, b) {                     // the spec first, then its queries
    return (a.path ? 0 : 1) - (b.path ? 0 : 1) || (a.path || "").localeCompare(b.path || "");
  });
}

/** {iri: {name, source, sources, …}} for every must:TestSpec in the graph. */
function readSpecs(st) {
  var out = {};
  st.typed(MUST + "TestSpec").forEach(function (s) {
    if (!isIri(s)) return;
    out[iriOf(s)] = {
      iri: iriOf(s),
      name: text(st.one(s, MUST + "specFileName")) || localName(iriOf(s)),
      source: text(st.one(s, MUST + "specSourceFile")),
      sources: readSources(st, s),
      inData: st.objs(s, COV + "usesInData").filter(isIri).map(iriOf).sort(),
      inQuery: st.objs(s, COV + "usesInQuery").filter(isIri).map(iriOf).sort()
    };
  });
  return out;
}

/** {path: source} across every spec — lets any file reference in the report open
    the text that was actually read, instead of a link into a filesystem the
    reader does not have. */
function sourcesByPath(specs) {
  var by = {};
  Object.keys(specs).forEach(function (k) {
    (specs[k].sources || []).forEach(function (src) {
      if (src.path && !by[src.path]) by[src.path] = src;
    });
  });
  return by;
}

/** cov:TestResult records, grouped module -> class, Playwright-style. */
function readTests(st, specs) {
  var rows = st.typed(COV + "TestResult").map(function (r) {
    var spec = st.one(r, COV + "resultTest");
    var specIri = spec && isIri(spec) ? iriOf(spec) : null;
    return {
      status: outcomeOf(st, r, COV + "resultOutcome") || "failed",
      type: text(st.one(r, COV + "testType")) || "",
      module: text(st.one(r, COV + "module")) || "",
      cls: text(st.one(r, COV + "className")) || "",
      name: text(st.one(r, COV + "testName")) || localName(iriOf(r)),
      duration: num(st.one(r, COV + "duration")),
      spec: specIri ? specs[specIri] || { iri: specIri, name: localName(specIri) } : null,
      source: text(st.one(r, COV + "sourceFile"))
    };
  });
  rows.sort(function (a, b) { return a.name.localeCompare(b.name); });

  var groups = [], byKey = new Map();
  rows.forEach(function (t) {
    var label = [t.module, t.cls].filter(Boolean).join(" › ") || "tests";
    var g = byKey.get(label);
    if (!g) { g = { label: label, tests: [], passed: 0, failed: 0, skipped: 0, duration: 0 }; byKey.set(label, g); groups.push(g); }
    g.tests.push(t);
    g[t.status] = (g[t.status] || 0) + 1;
    g.duration += t.duration || 0;
  });
  groups.sort(function (a, b) { return a.label.localeCompare(b.label); });
  var totals = { passed: 0, failed: 0, skipped: 0, duration: 0, total: rows.length };
  rows.forEach(function (t) { totals[t.status] = (totals[t.status] || 0) + 1; totals.duration += t.duration || 0; });
  return { groups: groups, totals: totals, rows: rows };
}

/** dqv:QualityMeasurement values, keyed by metric IRI. */
function readMeasurements(st) {
  var out = {};
  st.typed(DQV + "QualityMeasurement").forEach(function (m) {
    var metric = st.one(m, DQV + "isMeasurementOf");
    if (metric && isIri(metric)) out[iriOf(metric)] = num(st.one(m, DQV + "value"));
  });
  return out;
}

function readOntologies(st) {
  return st.typed(OWL + "Ontology").filter(isIri).map(function (o) {
    return {
      iri: iriOf(o),
      path: text(st.one(o, COV + "sourceFile")),
      version: text(st.one(o, OWL + "versionIRI")),
      comment: text(st.one(o, RDFS + "comment")) || text(st.one(o, RDFS + "label"))
    };
  }).sort(function (a, b) { return a.iri.localeCompare(b.iri); });
}

/** cov:TermCoverage records -> {iri: {kind, role, cqRole, inData, inQuery, reasons, exercises}}. */
function readTerms(st, specs) {
  var terms = {};
  st.typed(COV + "TermCoverage").forEach(function (tc) {
    var t = st.one(tc, COV + "term");
    if (!t || !isIri(t)) return;
    var role = st.one(tc, COV + "role"), cq = st.one(tc, COV + "cqRole");
    var exercises = st.objs(tc, COV + "exercise").map(function (e) {
      var tst = st.one(e, COV + "test");
      var iri = tst && isIri(tst) ? iriOf(tst) : null;
      var meta = iri ? specs[iri] : null;
      return {
        iri: iri, name: (meta && meta.name) || (iri && localName(iri)) || "?",
        source: meta && meta.source,
        inData: truthy(st.one(e, COV + "inData")), inQuery: truthy(st.one(e, COV + "inQuery"))
      };
    }).sort(function (a, b) { return a.name.localeCompare(b.name); });
    terms[iriOf(t)] = {
      iri: iriOf(t),
      kind: text(st.one(tc, COV + "kind")) || "class",
      role: (role && isIri(role) && ROLE[iriOf(role)]) || "unused",
      cqRole: cq && isIri(cq) ? ROLE[iriOf(cq)] || "unused" : null,
      inData: truthy(st.one(tc, COV + "inData")),
      inQuery: truthy(st.one(tc, COV + "inQuery")),
      reasons: st.objs(tc, COV + "structuralReason").map(text).sort(),
      exercises: exercises
    };
  });
  return terms;
}

/** Order terms as an rdfs:subClassOf forest with rdfs:domain properties nested
    beneath their class — the shape the Markdown report uses. Falls back to a
    flat, namespace-sorted list when the ontology TBox is not in the graph. */
function orderTerms(st, terms) {
  var iris = Object.keys(terms);
  var declared = new Set(iris);
  var classes = iris.filter(function (t) { return terms[t].kind === "class"; });
  var props = iris.filter(function (t) { return terms[t].kind !== "class"; });
  var byShort = function (a, b) { return st.short(a).localeCompare(st.short(b)); };

  var parent = {}, children = {};
  classes.forEach(function (c) {
    var sup = st.objs(K(c), RDFS + "subClassOf").filter(isIri).map(iriOf)
      .filter(function (p) { return declared.has(p) && p !== c; }).sort(byShort);
    if (sup.length) { parent[c] = sup[0]; (children[sup[0]] = children[sup[0]] || []).push(c); }
  });
  var attached = {}, loose = [];
  props.sort(byShort).forEach(function (p) {
    var dom = st.objs(K(p), RDFS + "domain").filter(isIri).map(iriOf)
      .filter(function (d) { return declared.has(d); }).sort(byShort);
    if (dom.length) (attached[dom[0]] = attached[dom[0]] || []).push(p);
    else loose.push(p);
  });

  var rows = [], seen = new Set();
  function walk(iri, depth, glyph) {
    if (seen.has(iri)) return;
    seen.add(iri);
    rows.push({ iri: iri, depth: depth, glyph: glyph, t: terms[iri] });
    (attached[iri] || []).forEach(function (p) { walk(p, depth + 1, "▸"); });
    (children[iri] || []).sort(byShort).forEach(function (c) { walk(c, depth + 1, "↳"); });
  }
  classes.filter(function (c) { return !parent[c]; }).sort(byShort).forEach(function (c) { walk(c, 0, ""); });
  classes.sort(byShort).forEach(function (c) { walk(c, 0, ""); });      // cycle safety net
  loose.forEach(function (p) { walk(p, 0, ""); });
  return rows;
}

function readCoverage(st, specs) {
  var terms = readTerms(st, specs);
  var iris = Object.keys(terms);
  if (!iris.length) return null;
  var m = readMeasurements(st);
  var schema = iris.filter(function (t) { return terms[t].role === "schema"; });
  var denom = iris.length - schema.length;
  var covered = iris.filter(function (t) { return terms[t].role === "covered"; }).length;
  var hasCq = m[COV + "termCoverageByCompetencyQuestions"] !== undefined;
  var coveredCq = iris.filter(function (t) { return terms[t].cqRole === "covered"; }).length;
  return {
    terms: terms, rows: orderTerms(st, terms), ontologies: readOntologies(st),
    declared: iris.length, schema: schema.length, denom: denom, covered: covered,
    pct: denom ? Math.round(100 * covered / denom) : 0,
    hasCq: hasCq, coveredCq: coveredCq,
    cqPct: denom ? Math.round(100 * coveredCq / denom) : 0,
    ratio: m[COV + "termCoverageByTests"], cqRatio: m[COV + "termCoverageByCompetencyQuestions"]
  };
}

function readCqs(st, specs) {
  var byCq = {};
  st.typed(COV + "Assertion").forEach(function (a) {
    var cq = st.one(a, COV + "onCompetencyQuestion"), t = st.one(a, COV + "onTest");
    if (!cq || !isIri(cq)) return;
    (byCq[iriOf(cq)] = byCq[iriOf(cq)] || []).push({
      spec: t && isIri(t) ? specs[iriOf(t)] || { iri: iriOf(t), name: localName(iriOf(t)) } : null,
      status: outcomeOf(st, a, COV + "outcome"),
      requiresOntology: truthy(st.one(a, COV + "requiresOntology"))
    });
  });
  var out = st.typed(CQNS + "CompetencyQuestion").filter(isIri).map(function (c) {
    var iri = iriOf(c);
    var linked = st.objs(c, CQNS + "cqSpec").filter(isIri).map(iriOf);
    var tests = (byCq[iri] || []).sort(function (a, b) {
      return ((a.spec && a.spec.name) || "").localeCompare((b.spec && b.spec.name) || "");
    });
    var resolved = new Set(tests.map(function (t) { return t.spec && t.spec.iri; }));
    return {
      iri: iri, name: localName(iri),
      questions: st.objs(c, CQNS + "question").map(text).sort(),
      source: text(st.one(c, COV + "sourceFile")),
      duplicate: truthy(st.one(c, COV + "duplicate")),
      tests: tests,
      missing: linked.filter(function (l) { return !resolved.has(l) && !specs[l]; })
    };
  });
  out.sort(function (a, b) { return ((a.questions[0] || a.name)).localeCompare(b.questions[0] || b.name); });
  return out;
}

function readIssues(st, specs) {
  function refs(issue) {
    return st.objs(issue, COV + "reference").map(function (r) {
      var t = st.one(r, COV + "test");
      var iri = t && isIri(t) ? iriOf(t) : null;
      var meta = iri ? specs[iri] : null;
      return {
        name: (meta && meta.name) || (iri && localName(iri)) || "?", source: meta && meta.source,
        inData: truthy(st.one(r, COV + "inData")), inQuery: truthy(st.one(r, COV + "inQuery"))
      };
    }).sort(function (a, b) { return a.name.localeCompare(b.name); });
  }
  var undeclared = st.subj(COV + "issueType", K(COV + "UsedButNotDeclared")).map(function (issue) {
    var t = st.one(issue, COV + "aboutTerm");
    return { term: t && isIri(t) ? iriOf(t) : "?", refs: refs(issue) };
  }).sort(function (a, b) { return a.term.localeCompare(b.term); });
  var tbox = st.subj(COV + "issueType", K(COV + "TBoxInTestData")).map(function (issue) {
    var t = st.one(issue, COV + "aboutTest");
    var meta = t && isIri(t) ? specs[iriOf(t)] : null;
    return {
      name: (meta && meta.name) || (t && isIri(t) ? localName(iriOf(t)) : "?"),
      source: meta && meta.source,
      axioms: st.objs(issue, COV + "detail").map(text).sort()
    };
  }).sort(function (a, b) { return a.name.localeCompare(b.name); });
  return { undeclared: undeclared, tbox: tbox };
}

function readRun(st) {
  var runs = st.typed(COV + "CoverageRun");
  if (!runs.length) return {};
  var r = runs[0];
  var agent = st.one(r, PROV + "wasAssociatedWith");
  return {
    iri: isIri(r) ? iriOf(r) : null,
    slug: isIri(r) ? localName(iriOf(r)) : null,
    commit: st.objs(r, PROV + "used").filter(isIri).map(iriOf)
      .filter(function (u) { return /\/commit\//.test(u); })[0] || null,
    version: agent ? text(st.one(agent, OWL + "versionInfo")) : null
  };
}

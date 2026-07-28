/* ======================================================================
   1. Turtle parser  —  text -> {triples, prefixes}

   Yes, a hand-written Turtle parser. Three reasons it earns its place:

   Nothing to compromise. This report is meant to travel — a CI artifact, an
   email attachment, a file on a static site opened years later. Every line it
   executes is in the file you are reading, it fetches nothing at view time, and
   its only vendored dependency is 127 auditable lines of VanJS. A page that
   pulls a parser from a CDN at view time is a supply chain, and a report is a
   record: it should not be able to change its mind about what a run said, and
   nobody should have to trust a registry to read one.

   It is cheap. 235 lines against roughly 50KB for a minified N3.js — which is an
   excellent library and the right answer if this ever needs to be a general RDF
   reader. Note what the page actually invites: dropping in *another mustrd run*,
   to compare or merge it. That input is Turtle mustrd emitted, from a version of
   this same codebase. Arbitrary RDF from anywhere is explicitly not the promise;
   it usually works, and when it does not it fails loudly and says so, with the
   JSON-LD reader below as the way through. If that promise ever widens, this is
   the file to replace, and `parseTurtle` has exactly one call site.

   And it is a fair advertisement for the format. That a usefully complete
   reader for a graph serialisation fits in 235 lines is most of the argument
   for Turtle: the grammar is small, the data is self-describing, and the whole
   pipeline — spec, ontology, coverage, results — stays one kind of thing all
   the way to the browser.

   Scope: prefix/base directives (both syntaxes), IRIs, prefixed names with
   escapes and %-encoding, all four string forms, datatypes and language tags,
   numbers, booleans, `a`, blank node labels, [] property lists, () collections.
   Not RDF-star, not TriG graphs, no full Unicode PN_CHARS validation. It throws
   with an offset and a snippet rather than quietly mis-parsing, and the JSON-LD
   reader below is the escape hatch when a real parser produced the file.

   TriG is the intended next step, not a reason to reach for N3.js. Runs
   accumulated over time want a graph each — `GRAPH <…/run/{sha}> { … }` — so the
   viewer can hold a history and diff it, which is the whole point of minting
   stable IRIs in the first place. The grammar delta is small: a `GRAPH`-prefixed
   or bare `<iri> { … }` block, and `{ … }` for the default graph. The work is
   downstream of the parse, not in it — `triples.push` here is a single funnel
   that becomes `quads.push`, `makeStore` grows a graph dimension, and the model
   readers gain an opinion about which run they are reading. Deliberately not
   started: half a graph model — parsing TriG and then flattening it — would lose
   exactly the information a run history is for.

   Terms are interned as strings so the indexes can use plain Maps:
     IRI      "<iri>"
     blank    "_:id"
     literal  "L" SEP lang SEP datatype SEP lexical-form   (SEP = U+0001)
   ====================================================================== */
var RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
var RDFS = "http://www.w3.org/2000/01/rdf-schema#";
var OWL  = "http://www.w3.org/2002/07/owl#";
var XSD  = "http://www.w3.org/2001/XMLSchema#";
var SKOS = "http://www.w3.org/2004/02/skos/core#";
var COV  = "https://mustrd.org/coverage/";
var MUST = "https://mustrd.org/model/";
var CQNS = "https://mustrd.org/competencyQuestion/";
var DQV  = "http://www.w3.org/ns/dqv#";
var PROV = "http://www.w3.org/ns/prov#";

var SEP = "\u0001";                 // never occurs in an IRI or a sane literal
function K(iri) { return "<" + iri + ">"; }
function isIri(k) { return k.charCodeAt(0) === 60; }
function isLit(k) { return k.charCodeAt(0) === 76 && k.charCodeAt(1) === 1; }
function iriOf(k) { return k.slice(1, -1); }
function litOf(k) {
  var a = k.indexOf(SEP, 2), b = k.indexOf(SEP, a + 1);
  return { lang: k.slice(2, a), dt: k.slice(a + 1, b), v: k.slice(b + 1) };
}
function mkLit(v, dt, lang) { return "L" + SEP + (lang || "") + SEP + (dt || "") + SEP + v; }
/** Display string for any term: a literal's lexical form, else the IRI / bnode id. */
function text(k) {
  if (k === null || k === undefined) return null;
  return isLit(k) ? litOf(k).v : isIri(k) ? iriOf(k) : k;
}
function truthy(k) { return k !== null && k !== undefined && litOf(k).v === "true"; }
function num(k) { if (k === null || k === undefined) return null; var f = parseFloat(litOf(k).v); return isNaN(f) ? null : f; }

var PN_LOCAL_STOP = "\t\r\n \"'`;,()[]{}^";
var NUM_RE = /[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?/y;
var BNODE_RE = /[^\t\r\n "'`;,()[\]{}^.]+/y;

function parseTurtle(src) {
  var i = 0, n = src.length, base = "", bn = 0;
  var prefixes = Object.create(null), triples = [];

  function fail(msg) {
    var near = src.slice(Math.max(0, i - 40), i + 40).replace(/\s+/g, " ");
    throw new Error("Turtle: " + msg + " at offset " + i + " near …" + near + "…");
  }
  function ws() {
    for (;;) {
      while (i < n && (src[i] === " " || src[i] === "\t" || src[i] === "\n" || src[i] === "\r")) i++;
      if (src[i] === "#") { while (i < n && src[i] !== "\n") i++; } else return;
    }
  }
  function eat(s) { if (src.startsWith(s, i)) { i += s.length; return true; } return false; }
  function eatCI(s) {
    if (src.substr(i, s.length).toLowerCase() === s.toLowerCase()) { i += s.length; return true; }
    return false;
  }
  function escape() {
    i++;                                     // the backslash
    var c = src[i++];
    if (c === "t") return "\t";
    if (c === "b") return "\b";
    if (c === "n") return "\n";
    if (c === "r") return "\r";
    if (c === "f") return "\f";
    if (c === "u") { var h = src.substr(i, 4); i += 4; return String.fromCharCode(parseInt(h, 16)); }
    if (c === "U") { var H = src.substr(i, 8); i += 8; return String.fromCodePoint(parseInt(H, 16)); }
    return c;                                // \" \' \\ and reserved-char escapes
  }
  function resolve(iri) {
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(iri) || !base) return iri;
    try { return new URL(iri, base).href; } catch (e) { return iri; }
  }
  function iriRef() {
    i++;                                     // '<'
    var s = "";
    while (i < n && src[i] !== ">") s += src[i] === "\\" ? escape() : src[i++];
    if (src[i] !== ">") fail("unterminated IRI");
    i++;
    return resolve(s);
  }
  function pname() {
    var start = i;
    while (i < n && src[i] !== ":" && PN_LOCAL_STOP.indexOf(src[i]) < 0 && src[i] !== ".") i++;
    if (src[i] !== ":") { i = start; return null; }
    var pfx = src.slice(start, i);
    i++;
    var local = "";
    while (i < n) {
      var c = src[i];
      if (c === "\\") { local += escape(); continue; }
      if (c === "%") { local += src.substr(i, 3); i += 3; continue; }
      if (PN_LOCAL_STOP.indexOf(c) >= 0) break;
      if (c === ".") {                        // '.' is legal inside a local name, not at its end
        var nx = src[i + 1];
        if (nx === undefined || PN_LOCAL_STOP.indexOf(nx) >= 0 || nx === ".") break;
      }
      local += c; i++;
    }
    var ns = prefixes[pfx];
    if (ns === undefined) fail('undefined prefix "' + pfx + ':"');
    return ns + local;
  }
  function stringLit() {
    var q = eat('"""') ? '"""' : eat("'''") ? "'''"
          : src[i] === '"' ? (i++, '"') : src[i] === "'" ? (i++, "'") : null;
    if (q === null) return null;
    var s = "";
    for (;;) {
      if (i >= n) fail("unterminated string");
      if (src.startsWith(q, i)) { i += q.length; return s; }
      s += src[i] === "\\" ? escape() : src[i++];
    }
  }
  function numberLit() {
    NUM_RE.lastIndex = i;                    // sticky: no slicing, so parsing stays linear
    var m = NUM_RE.exec(src);
    if (!m) return null;
    var lex = m[0];
    i += lex.length;
    var dt = /[eE]/.test(lex) ? XSD + "double" : lex.indexOf(".") >= 0 ? XSD + "decimal" : XSD + "integer";
    return mkLit(lex, dt, null);
  }
  /** Any subject/object. Emits nested triples for [] property lists and () lists. */
  function term() {
    ws();
    var c = src[i];
    if (c === "<") return K(iriRef());
    if (c === "_" && src[i + 1] === ":") {
      i += 2;
      BNODE_RE.lastIndex = i;                // '.' is not accepted, so "_:b0 ." terminates cleanly
      var m = BNODE_RE.exec(src);
      if (!m) fail("empty blank node label");
      i += m[0].length;
      return "_:" + m[0];
    }
    if (c === "[") {
      i++;
      var b = "_:b" + (bn++);
      ws();
      if (src[i] === "]") { i++; return b; }
      predObjList(b);
      ws();
      if (src[i] !== "]") fail("expected ]");
      i++;
      return b;
    }
    if (c === "(") {
      i++;
      var items = [];
      for (;;) { ws(); if (src[i] === ")") { i++; break; } if (i >= n) fail("unterminated collection"); items.push(term()); }
      if (!items.length) return K(RDF + "nil");
      var head = "_:b" + (bn++), cur = head;
      for (var x = 0; x < items.length; x++) {
        triples.push([cur, K(RDF + "first"), items[x]]);
        var rest = x === items.length - 1 ? K(RDF + "nil") : "_:b" + (bn++);
        triples.push([cur, K(RDF + "rest"), rest]);
        cur = rest;
      }
      return head;
    }
    if (c === '"' || c === "'") {
      var v = stringLit();
      if (eat("^^")) { ws(); var dt = src[i] === "<" ? iriRef() : pname(); return mkLit(v, dt, null); }
      if (src[i] === "@") { i++; var lg = ""; while (i < n && /[A-Za-z0-9-]/.test(src[i])) lg += src[i++]; return mkLit(v, null, lg); }
      return mkLit(v, null, null);
    }
    if (c === "+" || c === "-" || c === "." || (c >= "0" && c <= "9")) {
      var nl = numberLit();
      if (nl) return nl;
    }
    if (src.startsWith("true", i) && PN_LOCAL_STOP.indexOf(src[i + 4] || " ") >= 0) { i += 4; return mkLit("true", XSD + "boolean", null); }
    if (src.startsWith("false", i) && PN_LOCAL_STOP.indexOf(src[i + 5] || " ") >= 0) { i += 5; return mkLit("false", XSD + "boolean", null); }
    var p = pname();
    if (p === null) fail("unrecognised term");
    return K(p);
  }
  function verb() {
    ws();
    if (src[i] === "a" && PN_LOCAL_STOP.indexOf(src[i + 1] || " ") >= 0) { i++; return K(RDF + "type"); }
    if (src[i] === "<") return K(iriRef());
    var p = pname();
    if (p === null) fail("expected a predicate");
    return K(p);
  }
  function predObjList(s) {
    for (;;) {
      var p = verb();
      for (;;) {
        triples.push([s, p, term()]);
        ws();
        if (src[i] === ",") { i++; continue; }
        break;
      }
      ws();
      if (src[i] === ";") {
        i++; ws();
        if (src[i] === "." || src[i] === "]" || i >= n) return;   // trailing ';'
        continue;
      }
      return;
    }
  }

  for (;;) {
    ws();
    if (i >= n) break;
    if (src[i] === "@" || /^(prefix|base)\b/i.test(src.slice(i, i + 7))) {
      var sparqlStyle = src[i] !== "@";
      if (!sparqlStyle) i++;
      if (eatCI("prefix")) {
        ws();
        var start = i;
        while (i < n && src[i] !== ":") i++;
        var pfx = src.slice(start, i);
        i++; ws();
        prefixes[pfx] = iriRef();
        ws();
        if (!sparqlStyle) { if (!eat(".")) fail("expected . after @prefix"); }
        else eat(".");
        continue;
      }
      if (eatCI("base")) {
        ws(); base = iriRef(); ws();
        if (!sparqlStyle) { if (!eat(".")) fail("expected . after @base"); } else eat(".");
        continue;
      }
      fail("unknown directive");
    }
    var subj = term();
    ws();
    if (src[i] === ".") { i++; continue; }          // bare [] block
    predObjList(subj);
    ws();
    if (!eat(".")) fail("expected . at end of statement");
  }
  return { triples: triples, prefixes: prefixes };
}

/* ======================================================================
   2. JSON-LD (rdflib's expanded output) -> the same {triples, prefixes}
   ====================================================================== */
function parseJsonLd(src) {
  var doc = JSON.parse(src);
  var nodes = Array.isArray(doc) ? doc : doc["@graph"] ? doc["@graph"] : [doc];
  var triples = [];
  function objTerm(o) {
    if (typeof o === "string") return K(o);
    if (o["@id"]) return o["@id"].indexOf("_:") === 0 ? o["@id"] : K(o["@id"]);
    if ("@value" in o) {
      var v = o["@value"];
      var dt = o["@type"] || (typeof v === "number" ? (Number.isInteger(v) ? XSD + "integer" : XSD + "decimal")
                            : typeof v === "boolean" ? XSD + "boolean" : null);
      return mkLit(String(v), dt, o["@language"] || null);
    }
    return null;
  }
  nodes.forEach(function (node) {
    var id = node["@id"];
    if (!id) return;
    var s = id.indexOf("_:") === 0 ? id : K(id);
    Object.keys(node).forEach(function (p) {
      if (p === "@id") return;
      var vals = Array.isArray(node[p]) ? node[p] : [node[p]];
      var pk = p === "@type" ? K(RDF + "type") : K(p);
      vals.forEach(function (v) {
        var o = p === "@type" ? K(typeof v === "string" ? v : v["@id"]) : objTerm(v);
        if (o) triples.push([s, pk, o]);
      });
    });
  });
  return { triples: triples, prefixes: Object.create(null) };
}

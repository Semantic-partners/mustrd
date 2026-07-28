/* ======================================================================
   3. Store — two indexes over interned terms, plus IRI shortening

   SPO answers "objects of (subject, predicate)" and POS answers "subjects of
   (predicate, object)", which between them cover every question the model layer
   asks: walk out from a node, or find all nodes of a type. OSP would answer
   "everything that points at this object" — nothing needs it yet, and an unused
   index is just memory and a third place for `add` to go wrong. If TriG lands
   (see turtle.js), a graph dimension is the addition that will matter, not OSP.
   ====================================================================== */
function makeStore() {
  var spo = new Map(), pos = new Map(), all = [], seen = new Set();
  var prefixes = Object.create(null), ordered = [];

  function idx(m, a, b, c) {
    var x = m.get(a); if (!x) { x = new Map(); m.set(a, x); }
    var y = x.get(b); if (!y) { y = []; x.set(b, y); }
    y.push(c);
  }
  function rebuildPrefixes() {
    ordered = Object.keys(prefixes).map(function (p) { return [prefixes[p], p]; })
      .sort(function (a, b) { return b[0].length - a[0].length; });
  }
  return {
    prefixes: prefixes,
    size: function () { return all.length; },
    add: function (parsed) {
      // First binding for a prefix wins, so merging a second file cannot silently
      // rebind a prefix the first one already used for display.
      Object.keys(parsed.prefixes).forEach(function (p) {
        if (p && prefixes[p] === undefined) prefixes[p] = parsed.prefixes[p];
      });
      rebuildPrefixes();
      parsed.triples.forEach(function (t) {
        var sig = t[0] + "\u0002" + t[1] + "\u0002" + t[2];
        if (seen.has(sig)) return;            // graphs merge cleanly (stable IRIs, no dupes)
        seen.add(sig);
        all.push(t);
        idx(spo, t[0], t[1], t[2]);
        idx(pos, t[1], t[2], t[0]);
      });
    },
    /** Objects of (subjectKey, predicateIRI). */
    objs: function (s, p) { var x = spo.get(s); if (!x) return []; return x.get(K(p)) || []; },
    one: function (s, p) { var v = this.objs(s, p); return v.length ? v[0] : null; },
    /** Subjects of (predicateIRI, objectKey). */
    subj: function (p, oKey) { var x = pos.get(K(p)); if (!x) return []; return x.get(oKey) || []; },
    typed: function (cls) { return this.subj(RDF + "type", K(cls)); },
    has: function (s, p, oKey) { return this.objs(s, p).indexOf(oKey) >= 0; },
    triples: function () { return all; },
    /** IRI -> qname using the loaded @prefix bindings (longest namespace wins). */
    short: function (iri) {
      for (var x = 0; x < ordered.length; x++) {
        if (iri.indexOf(ordered[x][0]) === 0) return ordered[x][1] + ":" + iri.slice(ordered[x][0].length);
      }
      return iri;
    }
  };
}

function localName(iri) {
  var s = String(iri), h = s.lastIndexOf("#"), sl = s.lastIndexOf("/");
  var cut = Math.max(h, sl);
  return cut >= 0 ? s.slice(cut + 1) : s;
}

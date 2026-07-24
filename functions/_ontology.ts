// Shared helpers for the mustrd ontology namespace Functions.
//
// Files whose name starts with "_" are ignored by the Pages Functions router,
// so this module is importable but never itself a route.

export interface Env {
  ASSETS: Fetcher;
}

export type Format = { accept: string; mime: string; suffix: string };

// Only these slugs are served; each must have artifacts emitted by
// scripts/build.py under the matching /<slug>... paths.
export const SLUGS = new Set(['model', 'triplestore', 'mustrdTest', 'coverage', 'competencyQuestion']);

export const FORMATS: Record<string, Format> = {
  // The HTML doc is written to disk as <slug>-doc.html, but Pages' automatic
  // HTML handling 308-redirects a ".html" URL to its extensionless clean URL.
  // The ASSETS binding follows that into the not-found fallback, so we must
  // fetch the clean URL (<slug>-doc) — never the ".html" path.
  html:   { accept: 'text/html',             mime: 'text/html; charset=utf-8',   suffix: '-doc' },
  ttl:    { accept: 'text/turtle',           mime: 'text/turtle; charset=utf-8', suffix: '.ttl' },
  rdf:    { accept: 'application/rdf+xml',   mime: 'application/rdf+xml',        suffix: '.rdf' },
  jsonld: { accept: 'application/ld+json',   mime: 'application/ld+json',        suffix: '.jsonld' },
  nt:     { accept: 'application/n-triples', mime: 'application/n-triples',      suffix: '.nt' },
};

export const EXT_ALIAS: Record<string, keyof typeof FORMATS> = {
  ttl: 'ttl', rdf: 'rdf', xml: 'rdf', jsonld: 'jsonld', json: 'jsonld', nt: 'nt', html: 'html',
};

export function pickFormat(accept: string): Format {
  const ranked = accept
    .split(',')
    .map(part => {
      const [type, ...params] = part.trim().split(';');
      const q = params.find(p => p.trim().startsWith('q='));
      return { type: type.trim().toLowerCase(), q: q ? parseFloat(q.split('=')[1]) : 1 };
    })
    .sort((a, b) => b.q - a.q);

  for (const { type } of ranked) {
    for (const f of Object.values(FORMATS)) if (f.accept === type) return f;
    if (type === '*/*') return FORMATS.html;
  }
  return FORMATS.html;
}

// Split "name.ext" into [name, Format] when ext is a known serialization,
// otherwise [raw, null]. A leading dot is not treated as an extension.
export function splitExt(raw: string): [string, Format | null] {
  const dot = raw.lastIndexOf('.');
  if (dot > 0 && EXT_ALIAS[raw.slice(dot + 1).toLowerCase()]) {
    return [raw.slice(0, dot), FORMATS[EXT_ALIAS[raw.slice(dot + 1).toLowerCase()]]];
  }
  return [raw, null];
}

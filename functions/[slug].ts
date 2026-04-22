// Cloudflare Pages Function: content negotiation for mustrd ontology namespaces.
//
// URL layout:
//   /<slug>         -- negotiated: serves HTML doc or the best RDF match
//   /<slug>.<ext>   -- explicit: serves that serialization directly
//
// Backed by flat static files emitted by scripts/build.py:
//   /<slug>-doc.html, /<slug>.ttl, /<slug>.rdf, /<slug>.jsonld, /<slug>.nt
//
// Only the slugs listed in SLUGS are handled; other URLs routed here return 404.
// The sibling directory /<slug>/ contains the individual source TTL files and
// is served as static assets (see _routes.json excludes).

interface Env {
  ASSETS: Fetcher;
}

type Format = { accept: string; mime: string; suffix: string };

const SLUGS = new Set(['model', 'triplestore', 'mustrdTest']);

const FORMATS: Record<string, Format> = {
  html:   { accept: 'text/html',             mime: 'text/html; charset=utf-8',   suffix: '-doc.html' },
  ttl:    { accept: 'text/turtle',           mime: 'text/turtle; charset=utf-8', suffix: '.ttl' },
  rdf:    { accept: 'application/rdf+xml',   mime: 'application/rdf+xml',        suffix: '.rdf' },
  jsonld: { accept: 'application/ld+json',   mime: 'application/ld+json',        suffix: '.jsonld' },
  nt:     { accept: 'application/n-triples', mime: 'application/n-triples',      suffix: '.nt' },
};

const EXT_ALIAS: Record<string, keyof typeof FORMATS> = {
  ttl: 'ttl', rdf: 'rdf', xml: 'rdf', jsonld: 'jsonld', json: 'jsonld', nt: 'nt', html: 'html',
};

function pickFormat(accept: string): Format {
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

const handler: PagesFunction<Env> = async ({ request, params, env }) => {
  const raw = String(params.slug ?? '');
  let slug = raw;
  let format: Format;

  const dot = raw.lastIndexOf('.');
  if (dot > 0 && EXT_ALIAS[raw.slice(dot + 1).toLowerCase()]) {
    slug = raw.slice(0, dot);
    format = FORMATS[EXT_ALIAS[raw.slice(dot + 1).toLowerCase()]];
  } else {
    format = pickFormat(request.headers.get('accept') || '');
  }

  if (!SLUGS.has(slug)) {
    return new Response('Not found', { status: 404 });
  }

  const assetUrl = new URL(`/${slug}${format.suffix}`, request.url);
  const resp = await env.ASSETS.fetch(assetUrl.toString());
  if (!resp.ok) return resp;

  const headers = new Headers(resp.headers);
  headers.set('content-type', format.mime);
  headers.set('vary', 'accept');
  headers.set('access-control-allow-origin', '*');
  headers.set('cache-control', 'public, max-age=300, s-maxage=3600');
  return new Response(resp.body, { status: resp.status, headers });
};

export const onRequestGet = handler;
export const onRequestHead = handler;

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
// Term dereferencing (/<slug>/<term>) is handled by the sibling [term] function;
// the individual source TTL files under /<slug>/ are served as static assets.

import { Env, SLUGS, pickFormat, splitExt } from './_ontology';

const handler: PagesFunction<Env> = async ({ request, params, env }) => {
  const raw = String(params.slug ?? '');
  const [slug, ext] = splitExt(raw);
  const format = ext ?? pickFormat(request.headers.get('accept') || '');

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

// Cloudflare Pages Function: term dereferencing for the ontology namespaces.
//
// The namespaces are slash-based (e.g. cov: <https://mustrd.org/coverage/>), so
// an individual term such as /coverage/TermCoverage has no file of its own; a
// slash namespace resolves each term to the ontology document that defines it:
//
//   Accept: text/html  -> 303 to /<slug>#<term>  (anchored at the definition)
//   Accept: <rdf type>  -> 303 to /<slug>.<ext>   (the serialization)
//   /<slug>/<term>.<ext> -> 303 to /<slug>.<ext>  (explicit)
//
// The source TTL files copied under /<slug>/ (e.g. /coverage/coverage-ontology.ttl)
// are real static assets and are served directly, taking precedence over the
// term resolution above.

import { Env, SLUGS, FORMATS, pickFormat, splitExt } from '../_ontology';

const handler: PagesFunction<Env> = async ({ request, params, env }) => {
  const slug = String(params.slug ?? '');
  const raw = String(params.term ?? '');

  if (!SLUGS.has(slug)) {
    return new Response('Not found', { status: 404 });
  }

  // A real file copied under /<slug>/ (the source TTLs) wins over term resolution.
  const asset = await env.ASSETS.fetch(request.url);
  if (asset.ok) {
    if (raw.toLowerCase().endsWith('.ttl')) {
      const headers = new Headers(asset.headers);
      headers.set('content-type', 'text/turtle; charset=utf-8');
      headers.set('access-control-allow-origin', '*');
      return new Response(asset.body, { status: asset.status, headers });
    }
    return asset;
  }

  // Otherwise treat it as a term IRI and 303 to the canonical document.
  const [term, ext] = splitExt(raw);
  const format = ext ?? pickFormat(request.headers.get('accept') || '');
  const target = format === FORMATS.html
    ? `/${slug}${term ? '#' + term : ''}`
    : `/${slug}${format.suffix}`;
  return Response.redirect(new URL(target, request.url).toString(), 303);
};

export const onRequestGet = handler;
export const onRequestHead = handler;

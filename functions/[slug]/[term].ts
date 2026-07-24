// Cloudflare Pages Function: term dereferencing for the ontology namespaces.
//
// The namespaces are slash-based (e.g. cov: <https://mustrd.org/coverage/>), so
// an individual term such as /coverage/TermCoverage has no file of its own; a
// slash namespace resolves each term to the ontology document that defines it.
// The trailing-slash namespace IRI itself (/coverage/) resolves the same way.
//
//   /<slug>/            -> 303 to /<slug>            (the namespace document)
//   /<slug>/<term>      -> 303 to /<slug>#<term>     (HTML, anchored at the term)
//                          303 to /<slug>.<ext>      (RDF, by content negotiation)
//   /<slug>/<name>.<ext> -> the copied source file, served as a static asset
//
// The decision is made from the URL shape, not by probing for a file: a known
// serialization extension means "a file under the namespace dir" (the source
// TTLs copied by scripts/build.py); anything else is a term IRI. Term IRIs are
// never dereferenced with an extension, so this stays unambiguous.

import { Env, SLUGS, FORMATS, pickFormat, splitExt } from '../_ontology';

const handler: PagesFunction<Env> = async ({ request, params, env }) => {
  const slug = String(params.slug ?? '');
  const raw = String(params.term ?? '');

  if (!SLUGS.has(slug)) {
    return new Response('Not found', { status: 404 });
  }

  const [term, ext] = splitExt(raw);

  // /<slug>/<name>.<ext> — a copied source file. Serve it as a static asset,
  // pinning the turtle content-type (matching docs/_headers).
  if (ext) {
    const asset = await env.ASSETS.fetch(request.url);
    if (raw.toLowerCase().endsWith('.ttl') && asset.ok) {
      const headers = new Headers(asset.headers);
      headers.set('content-type', 'text/turtle; charset=utf-8');
      headers.set('access-control-allow-origin', '*');
      return new Response(asset.body, { status: asset.status, headers });
    }
    return asset;
  }

  // /<slug>/ or /<slug>/<term> — dereference to the ontology document.
  const format = pickFormat(request.headers.get('accept') || '');
  const target = format === FORMATS.html
    ? `/${slug}${term ? '#' + term : ''}`
    : `/${slug}${format.suffix}`;
  return Response.redirect(new URL(target, request.url).toString(), 303);
};

export const onRequestGet = handler;
export const onRequestHead = handler;

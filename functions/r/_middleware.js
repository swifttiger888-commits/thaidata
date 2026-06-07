// ThaiData UK — /r/ middleware
// Resolves short-name aliases to canonical restaurant pages.
// Only triggers for /r/{city}/{name} URLs (3+ path segments).
// Existing static pages pass through unchanged (via env.ASSETS.fetch).
// Unknown URLs return 404 instead of the SPA fallback (root index.html).

function slugify(s) {
  s = (s || '').toLowerCase().trim();
  s = s.replace(/[^\w\s-]/g, '');
  s = s.replace(/[-\s]+/g, '-');
  s = s.replace(/^-+|-+$/g, '');
  return s;
}

function pageUrl(name, city) {
  return '/r/' + slugify(city) + '/' + slugify(name) + '/';
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);
  const segments = url.pathname.replace(/\/$/, '').split('/').filter(Boolean);

  // Only intercept /r/{city}/{name} (3+ path segments)
  // Pass through for /r/ (hub) and /r/{city} (city pages)
  if (segments.length < 3 || segments[0] !== 'r') {
    return next();
  }

  const city = segments[1];
  const name = segments.slice(2).join('/');

  try {
    // Try to serve the static file. If it's a real page (has "Hygiene" marker),
    // return it directly — no alias resolution needed.
    const { ASSETS } = env;
    const assetResponse = await ASSETS.fetch(url.toString());

    if (assetResponse.ok) {
      const text = await assetResponse.clone().text();
      // Real restaurant pages contain "FSA X/5 Hygiene Rating" (from Kimi template)
      // The SPA fallback (homepage) does NOT have "Hygiene" anywhere
      if (text.includes('Hygiene')) {
        // This is a real restaurant page — serve from static assets
        return new Response(text, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            'cache-control': 'public, max-age=3600',
          },
        });
      }
    }

    // No static page at this URL — the request hit the SPA fallback.
    // Check curated alias list before returning 404.
    let aliasData;
    try {
      const aliasesRes = await fetch('https://thaidata.uk/data/r-aliases.json');
      if (aliasesRes.ok) {
        aliasData = await aliasesRes.json();
      }
    } catch (_) {} // fetch error — treat as no aliases available

    if (aliasData) {
      const aliasList = aliasData.aliases || [];
      const aliasSlug = name.toLowerCase().replace(/[-\s]+/g, '-').replace(/^-+|-+$/g, '');
      const aliasCity = city.toLowerCase();

      const match = aliasList.find(a =>
        a.slug === aliasSlug && a.city.toLowerCase() === aliasCity
      );

      if (match) {
        const correctUrl = pageUrl(match.canonical, match.city);
        return new Response(null, {
          status: 301,
          headers: { 'Location': correctUrl },
        });
      }
    }

    // Claim-specific 404 (?source=claim) — helpful state for first-time claimants
    const isClaimSource = url.searchParams.get('source') === 'claim';

    if (isClaimSource) {
      const claimSubject = 'Claim help: ' + url.pathname;
      return new Response(
        '<!DOCTYPE html><html lang="en"><head><title>Claimed Listing — ThaiData</title>'
        + '<meta name="robots" content="noindex"><style>body{font-family:sans-serif;'
        + 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;'
        + 'background:#0C1220;color:white;text-align:center;padding:20px;}'
        + 'h1{font-size:2.5rem;margin-bottom:16px;}'
        + 'p{color:#94A3B8;line-height:1.6;margin:8px 0;}'
        + '.actions{margin-top:32px;display:flex;flex-direction:column;align-items:center;gap:16px;}'
        + '.btn{display:inline-block;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:600;}'
        + '.btn-primary{background:#10B981;color:white;}'
        + '.btn-primary:hover{background:#059669;}'
        + '.btn-secondary{color:#10B981;text-decoration:underline;font-size:0.9rem;}'
        + '</style></head><body><div>'
        + '<h1>Page not ready yet</h1>'
        + '<p>You\'ve claimed this restaurant listing, but the public page hasn\'t been generated yet.</p>'
        + '<p>It will go live once your claim is approved.</p>'
        + '<div class="actions">'
        + '<a href="/admin/" class="btn btn-primary">Find my restaurant</a>'
        + '<a href="mailto:hello@thaidata.uk?subject=' + encodeURIComponent(claimSubject) + '" class="btn-secondary">Contact ThaiData &rarr;</a>'
        + '</div></div></body></html>',
        {
          status: 404,
          headers: { 'content-type': 'text/html; charset=utf-8' },
        }
      );
    }

    // Standard 404 — concise, minimal, for general users
    return new Response(
      '<!DOCTYPE html><html lang="en"><head><title>Not Found — ThaiData</title>'
      + '<meta name="robots" content="noindex"><style>body{font-family:sans-serif;'
      + 'display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'
      + 'background:#0C1220;color:white;text-align:center;}'
      + 'h1{font-size:3rem;margin-bottom:8px;opacity:0.5;}p{color:#94A3B8;}'
      + 'a{color:#10B981;}</style></head><body><div><h1>404</h1>'
      + '<p>Restaurant not found in our directory.</p>'
      + '<p><a href="/">thaidata.uk</a></p></div></body></html>',
      {
        status: 404,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      }
    );

  } catch (err) {
    console.error('/r/ middleware error:', err.message);
    return next();
  }
}

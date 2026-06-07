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

    // Not found — return proper 404
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

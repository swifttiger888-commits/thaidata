// ThaiData UK — /r/{city}/{name}
// Redirects fuzzy URLs to canonical restaurant pages.
// Example: /r/leeds/chaophraya/ → /r/leeds/chao-phraya-thai-restaurant/
// Also serves existing static pages when URL is already canonical.

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

export async function onRequestGet(context) {
  const { request, env, params } = context;
  const { city, name } = params;

  try {
    // Step 1: Try to serve static file if it exists
    // Real restaurant pages have an FSA rating reference; fallback (root index.html) doesn't
    const assetResponse = await env.ASSETS.fetch(request);
    const assetText = await assetResponse.clone().text();
    
    if (assetText.includes('FSA') || assetResponse.headers.get('content-length') > 50000) {
      return new Response(assetText, {
        status: 200,
        headers: {
          'content-type': 'text/html; charset=utf-8',
          'cache-control': 'public, max-age=3600',
        },
      });
    }

    // Step 2: No static page — search restaurants.json for correct name
    // Strip hyphens and spaces from search term for flexible matching
    const cityLower = city.toLowerCase().replace(/-/g, ' ');
    const nameClean = name.toLowerCase().replace(/[-\s]/g, '');

    const jsonUrl = 'https://thaidata.uk/data/restaurants.json';
    const jsonRes = await fetch(jsonUrl);
    
    if (jsonRes.ok) {
      const data = await jsonRes.json();
      const restaurants = data.restaurants || [];

      const match = restaurants.find(r => {
        const rCity = (r.city || '').toLowerCase();
        const rName = (r.name || '').toLowerCase().replace(/\s+/g, '');
        return rCity === cityLower && rName.includes(nameClean);
      });

      if (match) {
        const correctUrl = pageUrl(match.name, match.city);
        return Response.redirect(new URL(correctUrl, request.url), 301);
      }
    }

    // Step 3: Check D1 listings (approved claims)
    try {
      const listing = await env.DB.prepare(
        "SELECT * FROM listings WHERE LOWER(city) = ? AND LOWER(restaurant_name) LIKE ? LIMIT 1"
      ).bind(cityLower, `%${name}%`).first();
      
      if (listing) {
        const correctUrl = pageUrl(listing.restaurant_name, listing.city);
        return Response.redirect(new URL(correctUrl, request.url), 301);
      }
    } catch (dbErr) {
      console.error('D1 search error:', dbErr.message);
    }

    return notFound(city, name);

  } catch (err) {
    console.error('Restaurant catch-all error:', err.message);
    return new Response(JSON.stringify({ error: 'Internal error' }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    });
  }
}

function notFound(city, name) {
  return new Response(JSON.stringify({
    error: 'Restaurant not found',
    message: `No restaurant matching "${name}" found in ${city}`,
  }), {
    status: 404,
    headers: { 'content-type': 'application/json' },
  });
}

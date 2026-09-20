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

/**
 * Escape HTML entities to prevent XSS in D1-sourced content.
 */
function htmlEscape(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Inject claimed listing enrichment into restaurant page HTML.
 * Extracts restaurant name + city from existing JSON-LD, queries D1,
 * enriches the Restaurant schema and adds a Quick Facts card.
 * Returns original HTML unchanged if no claimed data found or on any error.
 */
async function injectClaimedEnrichment(html, env) {
  if (!env.DB) return html;  // No D1 binding — skip

  // 1. Extract restaurant name + city from existing JSON-LD
  const ldMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  if (!ldMatch) return html;

  let ld;
  try { ld = JSON.parse(ldMatch[1]); } catch (_) { return html; }

  // Find the Restaurant object (handles both array and single-object formats)
  const schemas = Array.isArray(ld) ? ld : [ld];
  const restaurant = schemas.find(s => s['@type'] === 'Restaurant');
  if (!restaurant) return html;

  const name = restaurant.name;
  const city = restaurant.address?.addressLocality;
  if (!name || !city) return html;

  // Google rating lifted from build-time schema (visible on claimed pages only)
  const agg = restaurant.aggregateRating || {};
  const ratingValue = typeof agg.ratingValue === 'number' ? agg.ratingValue : parseFloat(agg.ratingValue);
  const reviewCount = agg.reviewCount ? parseInt(agg.reviewCount, 10) : null;
  const hasRating = Number.isFinite(ratingValue) && ratingValue > 0;

  // 2. Query D1 for claimed listing enrichment
  let listing;
  try {
    listing = await env.DB.prepare(
      'SELECT l.cuisine_specialty, l.features, l.price_range, l.opening_hours, l.website, l.description, l.phone, l.photos FROM listings l JOIN claims c ON l.claim_id = c.id WHERE l.restaurant_name = ? AND l.city = ? AND c.claim_status = ?'
    ).bind(name, city, 'approved').first();
  } catch (_) { return html; }

  if (!listing) return html;

  // Parse owner photos (stored as JSON string or array by /api/upload)
  let photoUrls = [];
  if (listing.photos) {
    if (typeof listing.photos === 'string') {
      try { photoUrls = JSON.parse(listing.photos); } catch (_) { photoUrls = []; }
    } else if (Array.isArray(listing.photos)) {
      photoUrls = listing.photos;
    }
  }
  // Allowlist: only Cloudflare Images delivery URLs (stored by our own /api/upload).
  // Anything else is rejected — prevents script-tag breakout and external hotlinking.
  photoUrls = photoUrls.filter(u => u.startsWith('https://imagedelivery.net/'));

  // 3. Enrich the JSON-LD Restaurant schema
  if (listing.description) {
    restaurant.description = listing.description;
  }
  if (listing.cuisine_specialty) {
    restaurant.servesCuisine = listing.cuisine_specialty;
  }
  if (listing.price_range) {
    restaurant.priceRange = listing.price_range;
  }
  if (listing.phone) {
    restaurant.telephone = listing.phone;
  }
  if (listing.opening_hours) {
    try {
      restaurant.openingHours = listing.opening_hours;
    } catch (_) {}
  }
  if (listing.website) {
    try {
      restaurant.sameAs = restaurant.sameAs || [];
      if (!restaurant.sameAs.includes(listing.website)) {
        restaurant.sameAs.push(listing.website);
      }
    } catch (_) {}
  }
  if (photoUrls.length > 0) {
    restaurant.image = photoUrls;
  }

  // Replace the JSON-LD block with enriched version
  const ldBlock = ldMatch[0];
  // Escape '</' so no JSON string can terminate the surrounding <script> element
  const enrichedLd = JSON.stringify(ld).replace(/<\//g, '<\\/');
  html = html.replace(ldBlock, '<script type="application/ld+json">' + enrichedLd + '</script>');

  // 4. Build Quick Facts HTML card
  const facts = [];
  if (hasRating) {
    // Visible rating on claimed pages only — with Google attribution (Maps ToS 3.2.3(a))
    const mapsUrl = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(name + ' ' + city);
    const stars = Math.min(5, Math.max(0, Math.round(ratingValue)));
    const countText = reviewCount ? ' · ' + reviewCount.toLocaleString('en-GB') + ' reviews' : '';
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Google rating</span><span class="qf-value" style="font-weight:600;color:var(--ink2, #1f2937);">' + '★'.repeat(stars) + ' ' + htmlEscape(String(ratingValue)) + '<span style="font-weight:400;color:var(--ink4, #6b7280);">' + htmlEscape(countText) + '</span></span></div>');
    facts.push('<div style="padding-top:4px;font-size:0.7rem;color:var(--ink4, #6b7280);"><a href="' + htmlEscape(mapsUrl) + '" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;">Data from Google</a></div>');
  }
  if (listing.cuisine_specialty) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Cuisine</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);">' + htmlEscape(listing.cuisine_specialty) + '</span></div>');
  }
  if (listing.features) {
    let feats = listing.features;
    if (typeof feats === 'string') {
      try { feats = JSON.parse(feats); } catch (_) { feats = [feats]; }
    }
    if (Array.isArray(feats) && feats.length > 0) {
      facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);flex-shrink:0;padding-top:1px;">Features</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);text-align:right;">' + feats.map(f => htmlEscape(f)).join('<br>') + '</span></div>');
    }
  }
  if (listing.price_range) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Price</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);">' + htmlEscape(listing.price_range) + '</span></div>');
  }
  if (listing.opening_hours) {
    const hours = Array.isArray(listing.opening_hours) ? listing.opening_hours : [listing.opening_hours];
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);flex-shrink:0;">Hours</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);text-align:right;">' + htmlEscape(hours.join('<br>')) + '</span></div>');
  }
  if (listing.website) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Website</span><span class="qf-value" style="font-weight:500;"><a href="' + htmlEscape(listing.website) + '" target="_blank" rel="noopener" style="color:var(--accent, #10B981);text-decoration:none;">Visit →</a></span></div>');
  }
  if (listing.description) {
    facts.push('<div class="qf-desc" style="padding-top:8px;font-size:0.9rem;color:var(--ink3, #374151);line-height:1.6;">' + htmlEscape(listing.description) + '</div>');
  }

  // 5. Build injected HTML: Quick Facts card + owner photo gallery
  let injection = '';
  if (facts.length > 0) {
    injection += '\n            <!-- Quick Facts (server-injected from claimed listing) -->\n            <div id="quick-facts" class="card" style="margin-bottom:24px;">\n                <h3 style="margin:0 0 16px;font-weight:600;">Quick Facts</h3>\n                ' + facts.join('\n                ') + '\n            </div>\n';
  }

  if (photoUrls.length > 0) {
    // CF Images flexible variants: stored URL is /{id}/public → swap for /w=400, /w=800
    const imgs = photoUrls.slice(0, 12).map((u, i) => {
      const base = u.replace(/\/public$/, '');
      const w400 = base + '/w=400';
      const w800 = base + '/w=800';
      return '<img src="' + htmlEscape(w400) + '" srcset="' + htmlEscape(w400) + ' 400w, ' + htmlEscape(w800) + ' 800w" sizes="(max-width: 640px) 100vw, 300px" alt="Owner photo ' + (i + 1) + '" loading="lazy" decoding="async" style="width:100%;height:auto;border-radius:10px;aspect-ratio:4/3;object-fit:cover;display:block;">';
    }).join('');
    injection += '\n            <!-- Owner Photos (server-injected) -->\n            <div id="owner-photos" class="card" style="margin-bottom:24px;">\n                <h3 style="margin:0 0 16px;font-weight:600;">Photos</h3>\n                <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));gap:10px;">' + imgs + '</div>\n            </div>\n';
  }

  if (injection) {
    // Claimed pages with data: Quick Facts already carries contact info,
    // so drop the static hero contact strip to avoid duplication.
    if (facts.length > 0) {
      html = html.replace(/<div class="contact-strip" id="contact-strip"[^>]*>[\s\S]*?<\/div>/, '');
    }
    // Inject before Trust Sidebar anchor
    if (html.includes('<!-- Trust Sidebar -->')) {
      html = html.replace('<!-- Trust Sidebar -->', injection + '            <!-- Trust Sidebar -->');
    } else {
      // Fallback: inject before Schema: Restaurant (visible anchor always present)
      html = html.replace('<!-- Schema: Restaurant -->', injection + '    <!-- Schema: Restaurant -->');
    }
  }

  return html;
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

  // Enforce trailing slash on restaurant detail pages (3+ segments).
  // Cloudflare Pages serves index.html at both /r/city/slug and /r/city/slug/,
  // creating duplicate URLs. Canonical tags use trailing-slash form — redirect
  // the bare version so Google only indexes one URL per restaurant.
  if (!url.pathname.endsWith('/')) {
    return new Response(null, {
      status: 301,
      headers: { 'Location': url.pathname + '/' + url.search },
    });
  }

  // Nested restaurant sub-pages, e.g. /r/{city}/{name}/menu/.
  // These are real static files generated by scripts/build_menu_page.py, never
  // the SPA fallback. We can't just trust `ASSETS.fetch` returning ok, because
  // Pages answers unmatched paths with the homepage and HTTP 200 — so we look
  // for the generator's marker meta tag before serving.
  if (segments.length > 3) {
    const nested = await env.ASSETS.fetch(url.toString());
    if (nested.ok) {
      const nestedText = await nested.clone().text();
      if (nestedText.includes('name="thaidata-page"')) {
        return new Response(nestedText, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            'cache-control': 'public, max-age=3600',
          },
        });
      }
    }
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
        // Inject claimed listing enrichment for AEO/SEO visibility
        let enrichedText = text;
        try {
          enrichedText = await injectClaimedEnrichment(text, env);
        } catch (e) {
          // D1 failure or parse error — serve original page unchanged
          console.warn('Enrichment injection failed:', e.message);
        }
        return new Response(enrichedText, {
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
        const redirectCity = match.target_city || match.city;
        const correctUrl = pageUrl(match.canonical, redirectCity);
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
        + '<p>It will go live once your claim is approved and the listing is set up in our system.</p>'
        + '<div class="actions">'
        + '<a href="/admin/" class="btn btn-primary">Manage my claim</a>'
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

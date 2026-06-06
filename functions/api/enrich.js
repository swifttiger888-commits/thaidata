// ThaiData UK — POST /api/enrich
// Scrape restaurant website for structured data (JSON-LD, OG, footer)
// Stores enrichment JSON on the listing. Supports ?id= param for dry-run.

/**
 * Heuristic: extract candidate page links (contact/about/menu) from homepage body.
 * Returns array of up to 2 relative/absolute URLs most likely to contain
 * structured contact data.
 */
function discoverPages(html, baseUrl) {
  const hrefs = [];
  const re = /<a[^>]+href="([^"]+)"/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    hrefs.push(m[1]);
  }

  const scored = [];
  for (const h of hrefs) {
    const lower = h.toLowerCase();
    let score = 0;
    if (/\bcontact\b/.test(lower)) score = 10;
    else if (/about/.test(lower)) score = 5;
    else if (/\bmenu\b/.test(lower)) score = 3;
    else if (/\bfind[-\s]?us\b/.test(lower)) score = 4;
    if (score > 0) scored.push({ href: h, score });
  }

  scored.sort((a, b) => b.score - a.score);

  const resolved = [];
  for (const item of scored.slice(0, 2)) {
    try {
      resolved.push(new URL(item.href, baseUrl).toString());
    } catch (_) { /* skip malformed */ }
  }
  return resolved;
}

/**
 * Extract a reasonable short description. Priority: JSON-LD > meta > first
 * quality paragraph. Falls back to null if nothing passes the quality gate.
 */
function extractDescription(html, jsonld) {
  // 1. JSON-LD description
  if (jsonld && jsonld.description) {
    const d = String(jsonld.description).trim();
    if (d.length >= 30 && d.length <= 300) return { value: d, found_in: 'json-ld', confidence: 'high' };
  }

  // 2. OG / meta description
  const ogMatch = html.match(/<meta[^>]+name="description"[^>]+content="([^"]+)"/i)
    || html.match(/<meta[^>]+property="og:description"[^>]+content="([^"]+)"/i);
  if (ogMatch) {
    const d = ogMatch[1].trim();
    if (d.length >= 30 && d.length <= 300 && !lowQuality(d)) return { value: d, found_in: 'meta', confidence: 'medium' };
  }

  // 3. First reasonable paragraph (strict quality gate)
  const paraRe = /<p[^>]*>([\s\S]*?)<\/p>/gi;
  let pm;
  while ((pm = paraRe.exec(html)) !== null) {
    const text = pm[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (text.length >= 50 && text.length <= 300 && !lowQuality(text)) {
      return { value: text, found_in: 'homepage', confidence: 'low' };
    }
  }

  return null;
}

function lowQuality(text) {
  const lower = text.toLowerCase();
  const spam = ['404', 'not found', 'enable javascript', 'browser does not support',
    'please enable', '©', 'all rights reserved', 'terms of service', 'privacy policy'];
  for (const s of spam) {
    if (lower.includes(s)) return true;
  }
  return false;
}

/**
 * Extract phone number. Priority: JSON-LD > footer > contact page.
 */
function extractPhone(html, jsonld) {
  // JSON-LD
  if (jsonld && jsonld.telephone) {
    const val = String(jsonld.telephone).trim();
    if (val.length >= 8) return { value: val, found_in: 'json-ld', confidence: 'high' };
  }

  // Footer or anywhere with a strict UK phone pattern
  // Must start with 0[1-9] (not 00) and have 10-11 total digits
  const phoneRe = /(0[1-9]\d{1,4}[\s-]?\d{3,4}[\s-]?\d{3,4})/g;
  const phones = [];
  let pm;
  while ((pm = phoneRe.exec(html)) !== null) {
    const num = pm[0].replace(/[\s-]/g, '');
    if (num.length >= 10 && num.length <= 11 && !num.startsWith('00')) {
      phones.push(pm[0]);
    }
  }
  if (phones.length > 0) {
    // Prefer phone near "phone" / "call" / "tel"
    return { value: phones[0], found_in: 'footer', confidence: 'medium' };
  }
  return null;
}

/**
 * Extract opening hours. v1: JSON-LD only (strict — no heuristic text parsing).
 */
function extractHours(html, jsonld) {
  if (!jsonld) return null;

  // openingHoursSpecification array
  if (Array.isArray(jsonld.openingHoursSpecification) && jsonld.openingHoursSpecification.length > 0) {
    const parts = jsonld.openingHoursSpecification.map(s => {
      const day = (s.dayOfWeek || '').replace(/^https?:\/\/schema\.org\//, '').slice(0, 3);
      return day + ' ' + (s.opens || '?') + '-' + (s.closes || '?');
    });
    return { value: parts.join(', '), found_in: 'json-ld', confidence: 'high' };
  }

  // Single openingHours string — try to validate it looks like hours
  if (jsonld.openingHours) {
    const val = String(jsonld.openingHours).trim();
    if (/[0-2]?\d[:.]\d{2}/.test(val) && val.length > 10) {
      return { value: val, found_in: 'json-ld', confidence: 'high' };
    }
  }

  return null;
}

/**
 * Extract social links. Priority: JSON-LD sameAs > footer icon links.
 */
function extractSocial(html, jsonld) {
  let instagram = null;
  let facebook = null;

  // JSON-LD sameAs
  if (jsonld && Array.isArray(jsonld.sameAs)) {
    for (const u of jsonld.sameAs) {
      const url = String(u);
      if (!instagram && url.includes('instagram.com')) {
        instagram = { value: url, found_in: 'json-ld', confidence: 'high' };
      }
      if (!facebook && url.includes('facebook.com')) {
        facebook = { value: url, found_in: 'json-ld', confidence: 'high' };
      }
    }
  }

  // Footer links
  const linkRe = /<a[^>]+href="([^"]+)"[^>]*>/gi;
  let lm;
  while ((lm = linkRe.exec(html)) !== null) {
    const url = lm[1];
    if (!instagram && url.includes('instagram.com')) {
      instagram = { value: url, found_in: 'footer', confidence: 'medium' };
    }
    if (!facebook && url.includes('facebook.com')) {
      facebook = { value: url, found_in: 'footer', confidence: 'medium' };
    }
  }

  const result = {};
  if (instagram) result.social_instagram = instagram;
  if (facebook) result.social_facebook = facebook;
  return Object.keys(result).length > 0 ? result : null;
}

/**
 * Main enrichment function: fetch homepage, discover candidate pages,
 * extract fields, return structured enrichment JSON.
 */
async function runEnrichment(sourceUrl, env) {
  const now = new Date().toISOString();
  const base = { scraped_at: now, source_url: sourceUrl, fields: {} };

  // Fetch homepage
  let homeHtml;
  try {
    const homeRes = await fetch(sourceUrl, {
      headers: { 'User-Agent': 'ThaiData/1.0 (+https://thaidata.uk)' },
      signal: AbortSignal.timeout(8000),
    });
    if (!homeRes.ok) {
      base.status = homeRes.status === 403 || homeRes.status === 429 ? 'blocked' : 'failed';
      base.error = 'http_' + homeRes.status;
      return base;
    }
    homeHtml = await homeRes.text();
  } catch (err) {
    base.status = err.name === 'TimeoutError' ? 'timeout' : 'failed';
    base.error = err.name === 'TimeoutError' ? 'timeout' : 'dns';
    return base;
  }

  if (!homeHtml || homeHtml.length < 100) {
    base.status = 'partial';
    base.error = 'empty_page';
    return base;
  }

  // Detect JS-only shells (no text content, just <script>/<style>)
  const stripped = homeHtml.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<style[\s\S]*?<\/style>/gi, '');
  if (stripped.replace(/<[^>]+>/g, '').trim().length < 50) {
    base.status = 'partial';
    base.error = 'js_only';
    return base;
  }

  // Parse JSON-LD
  let jsonld = null;
  const ldRe = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/gi;
  let lm;
  while ((lm = ldRe.exec(homeHtml)) !== null) {
    try {
      const parsed = JSON.parse(lm[1]);
      if (parsed['@type'] === 'LocalBusiness' || parsed['@type'] === 'Restaurant' ||
          parsed['@type'] === 'FoodEstablishment') {
        jsonld = parsed;
        break;
      }
    } catch (_) { /* skip malformed */ }
  }

  // Extract homepage fields
  base.fields.description = extractDescription(homeHtml, jsonld);
  base.fields.phone = extractPhone(homeHtml, jsonld);
  base.fields.opening_hours = extractHours(homeHtml, jsonld);

  const social = extractSocial(homeHtml, jsonld);
  if (social) Object.assign(base.fields, social);

  // Discover contact/about/menu pages and extract from them
  const extraUrls = discoverPages(homeHtml, sourceUrl);
  for (const url of extraUrls) {
    if (url === sourceUrl) continue;
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': 'ThaiData/1.0 (+https://thaidata.uk)' },
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) continue;
      const pageHtml = await res.text();

      // Phone (if not found yet)
      if (!base.fields.phone) {
        base.fields.phone = extractPhone(pageHtml, null);
      }
      // Description (if not found yet and page looks like an about page)
      if (!base.fields.description && /\babout\b/i.test(url)) {
        base.fields.description = extractDescription(pageHtml, null);
      }
    } catch (_) { /* skip individual page failures */ }
  }

  // Remove null fields
  for (const key of Object.keys(base.fields)) {
    if (base.fields[key] === null) delete base.fields[key];
  }

  base.status = Object.keys(base.fields).length > 0 ? 'success' : 'partial';
  return base;
}

// ─── Cloudflare Worker handlers ──────────────────────────────────────────────

export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { listing_id, url } = body;

    if (!url) {
      return new Response(JSON.stringify({ error: 'url required' }), {
        status: 400, headers: corsHeaders,
      });
    }

    // Normalize URL
    let sourceUrl = url.trim();
    if (!/^https?:\/\//i.test(sourceUrl)) sourceUrl = 'https://' + sourceUrl;

    const result = await runEnrichment(sourceUrl, env);

    // Store on listing if listing_id provided
    if (listing_id) {
      await env.DB.prepare(
        'UPDATE listings SET enrichment = ?, updated_at = datetime(\'now\') WHERE id = ?'
      ).bind(JSON.stringify(result), listing_id).run();
    }

    return new Response(JSON.stringify(result), {
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    console.error('Enrichment error:', err.message);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

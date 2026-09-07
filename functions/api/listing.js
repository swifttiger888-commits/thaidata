// ThaiData UK — /api/listing
// Get and update enhanced restaurant listings

import { sha256, sendMagicLinkEmail } from './_email.js';

function slugify(s) {
  s = s.toLowerCase().trim();
  s = s.replace(/[^\w\s-]/g, '');    // remove non-word chars (matches Python slugify)
  s = s.replace(/[-\s]+/g, '-');      // collapse hyphens and spaces
  s = s.replace(/^-+|-+$/g, '');      // strip leading/trailing hyphens
  return s;
}

function pageUrl(name, city) {
  return '/r/' + slugify(city) + '/' + slugify(name) + '/';
}

/**
 * Handles GET /api/listing — get enhanced listing(s)
 * Supports: ?restaurant=X&city=Y, ?fsa_id=X, ?city=X, or Authorization: Bearer token
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request
 * @param {object} context.env - Environment bindings with DB (D1Database)
 * @returns {Promise<Response>} JSON response with listing(s) or error
 * @throws {Error} When database query fails (caught internally)
 */
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const url = new URL(request.url);
    const auth = request.headers.get('Authorization');

    // Token-based auth: return listing for the authenticated owner
    if (auth && auth.startsWith('Bearer ')) {
      const rawToken = auth.slice(7);
      const tokenHash = await sha256(rawToken);
      const tokenRecord = await env.DB.prepare(
        "SELECT listing_id FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
      ).bind(tokenHash).first();

      if (!tokenRecord) {
        return new Response(JSON.stringify({ error: 'Invalid or expired token' }), {
          status: 403,
          headers: corsHeaders,
        });
      }

      const listing = await env.DB.prepare('SELECT * FROM listings WHERE id = ?').bind(tokenRecord.listing_id).first();
      if (!listing) {
        return new Response(JSON.stringify({ listings: [], count: 0 }), {
          status: 200,
          headers: corsHeaders,
        });
      }

      listing.features = listing.features ? JSON.parse(listing.features) : [];
      listing.photos = listing.photos ? JSON.parse(listing.photos) : [];
      listing.menu_highlights = listing.menu_highlights ? JSON.parse(listing.menu_highlights) : [];
      listing.enrichment = listing.enrichment ? JSON.parse(listing.enrichment) : null;
      listing.page_url = pageUrl(listing.restaurant_name, listing.city);

      return new Response(JSON.stringify({ listings: [listing], count: 1 }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Public queries
    const restaurant = url.searchParams.get('restaurant');
    const city = url.searchParams.get('city');
    const fsaId = url.searchParams.get('fsa_id');

    let query = 'SELECT * FROM listings WHERE 1=1';
    const params = [];

    if (restaurant && city) {
      query += ' AND restaurant_name = ? AND city = ?';
      params.push(restaurant, city);
    } else if (fsaId) {
      query += ' AND fsa_id = ?';
      params.push(fsaId);
    } else if (city) {
      query += ' AND city = ?';
      params.push(city);
    } else {
      return new Response(JSON.stringify({ error: 'Provide restaurant+city, fsa_id, city, or auth token' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    const results = await env.DB.prepare(query).bind(...params).all();

    // Parse JSON fields
    const listings = results.results.map(l => ({
      ...l,
      features: l.features ? JSON.parse(l.features) : [],
      photos: l.photos ? JSON.parse(l.photos) : [],
      menu_highlights: l.menu_highlights ? JSON.parse(l.menu_highlights) : [],
      enrichment: l.enrichment ? JSON.parse(l.enrichment) : null,
      page_url: pageUrl(l.restaurant_name, l.city),
    }));

    return new Response(JSON.stringify({ listings, count: listings.length }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Listing GET error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles PUT /api/listing — update enhanced listing (owner only, via magic link token)
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with Authorization: Bearer token and JSON body
 * @param {object} context.env - Environment bindings with DB (D1Database)
 * @returns {Promise<Response>} JSON response indicating success or error
 * @throws {Error} When database operation fails (caught internally)
 */
export async function onRequestPut(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    // Auth via magic link token
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized. Use your magic link to get a token.' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    const rawToken = auth.slice(7);
    const tokenHash = await sha256(rawToken);
    const tokenRecord = await env.DB.prepare(
      "SELECT listing_id, expires_at, used FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
    ).bind(tokenHash).first();

    if (!tokenRecord) {
      return new Response(JSON.stringify({ error: 'Invalid or expired token. Request a new magic link.' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    const body = await request.json();
    const allowedFields = [
      'description', 'cuisine_specialty', 'website', 'phone', 'email',
      'social_instagram', 'social_facebook', 'social_twitter',
      'address', 'postcode', 'opening_hours', 'price_range', 'features', 'photos', 'menu_highlights'
    ];

    // Build SET clause from allowed fields
    const sets = [];
    const params = [];

    for (const field of allowedFields) {
      if (body[field] !== undefined) {
        sets.push(`${field} = ?`);
        // Stringify arrays/objects
        params.push(
          (field === 'features' || field === 'photos' || field === 'menu_highlights')
            ? JSON.stringify(body[field])
            : body[field]
        );
      }
    }

    if (sets.length === 0) {
      return new Response(JSON.stringify({ error: 'No valid fields to update' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    sets.push("updated_at = datetime('now')");
    params.push(tokenRecord.listing_id);

    await env.DB.prepare(
      `UPDATE listings SET ${sets.join(', ')} WHERE id = ?`
    ).bind(...params).run();

    // Mark token as used
    await env.DB.prepare(
      'UPDATE auth_tokens SET used = 1 WHERE token_hash = ?'
    ).bind(tokenHash).run();

    return new Response(JSON.stringify({
      success: true,
      message: 'Listing updated successfully. Get a new magic link to edit again.',
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Listing PUT error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles POST /api/listing — request a magic link to edit listing
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with JSON body {restaurant_name, city, email}
 * @param {object} context.env - Environment bindings with DB (D1Database) and RESEND_API_KEY
 * @param {Function} context.waitUntil - Extends request lifecycle for background tasks
 * @returns {Promise<Response>} JSON response with magic link or error
 * @throws {Error} When database operation or email send fails (caught internally)
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { restaurant_name, city, email, fsa_id } = body;

    if (!restaurant_name || !city || !email) {
      return new Response(JSON.stringify({ error: 'restaurant_name, city, and email required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Find the approved claim — by fsa_id when available, fall back to text match
    let matchQuery, matchParams;
    if (fsa_id) {
      matchQuery = "SELECT c.id as claim_id, c.claimer_email, l.id as listing_id FROM claims c LEFT JOIN listings l ON l.claim_id = c.id WHERE CAST(c.fsa_id AS TEXT) = ? AND c.claimer_email = ? AND c.claim_status = 'approved'";
      matchParams = [String(fsa_id), email];
    } else {
      matchQuery = "SELECT c.id as claim_id, c.claimer_email, l.id as listing_id FROM claims c LEFT JOIN listings l ON l.claim_id = c.id WHERE c.restaurant_name = ? AND c.city = ? AND c.claimer_email = ? AND c.claim_status = 'approved'";
      matchParams = [restaurant_name, city, email];
    }
    const claim = await env.DB.prepare(matchQuery).bind(...matchParams).first();

    if (!claim) {
      return new Response(JSON.stringify({ success: true, message: 'If an approved claim exists, a magic link has been sent to the registered email.' }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Generate token — raw for magic link, SHA-256 hash for DB storage
    const token = crypto.randomUUID();
    const tokenHash = await sha256(token);
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString(); // 1 hour

    await env.DB.prepare(
      'INSERT INTO auth_tokens (listing_id, token_hash, expires_at) VALUES (?, ?, ?)'
    ).bind(claim.listing_id, tokenHash, expiresAt).run();

    // Send magic link email inline (not waitUntil)
    const magicLink = `https://thaidata.uk/listing/manage?token=${token}`;
    await sendMagicLinkEmail(env, {
      email: claim.claimer_email,
      restaurant_name,
      city,
      magicLink,
      variant: 'self_service',
      claimId: claim.claim_id,
    });

    return new Response(JSON.stringify({
      success: true,
      message: 'If an approved claim exists, a magic link has been sent to the registered email.',
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Magic link error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// ThaiData UK — /api/admin
// Admin panel: review claims, approve/reject, manage listings

import { sha256, sendMagicLinkEmail, sendRecoveryEmail, sendClaimRejectedEmail } from './_email.js';

// ADMIN_PASSWORD is read from env.ADMIN_PASSWORD at runtime

/**
 * Checks Authorization header against ADMIN_PASSWORD
 * @param {Request} request - Incoming HTTP request
 * @param {object} env - Environment bindings with ADMIN_PASSWORD
 * @returns {Response|null} Response with error if unauthorized, null if authorized
 */
function requireAdmin(request, env) {
  const auth = request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Bearer ')) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const password = auth.slice(7);
  if (password !== env.ADMIN_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return null; // Authorized
}

/**
 * Handles POST /api/admin/login — authenticates admin with password, returns session token
 * Rate-limited: 5 attempts per 15 minutes per IP
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with JSON body {password}
 * @param {object} context.env - Environment bindings with ADMIN_PASSWORD and DB (D1Database)
 * @returns {Promise<Response>} JSON response with session token or error
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  // Get real client IP (Cloudflare provides this header)
  const clientIp = request.headers.get('CF-Connecting-IP') || 'unknown';

  // Ensure rate limit table exists
  await env.DB.prepare(
    `CREATE TABLE IF NOT EXISTS login_attempts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ip TEXT NOT NULL,
      attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
    )`
  ).run();

  // Clean old entries (older than 15 minutes)
  await env.DB.prepare(
    "DELETE FROM login_attempts WHERE attempted_at < datetime('now', '-15 minutes')"
  ).run();

  // Count recent attempts from this IP
  const recentAttempts = await env.DB.prepare(
    "SELECT COUNT(*) as count FROM login_attempts WHERE ip = ? AND attempted_at > datetime('now', '-15 minutes')"
  ).bind(clientIp).first();

  const attemptCount = recentAttempts ? recentAttempts.count : 0;

  // Rate limit: 5 attempts per 15 minutes
  if (attemptCount >= 5) {
    return new Response(JSON.stringify({
      error: 'Too many login attempts. Please wait 15 minutes before trying again.',
    }), {
      status: 429,
      headers: corsHeaders,
    });
  }

  try {
    const body = await request.json();
    const { password } = body;

    if (!password || password !== env.ADMIN_PASSWORD) {
      // Record failed attempt
      await env.DB.prepare(
        'INSERT INTO login_attempts (ip) VALUES (?)'
      ).bind(clientIp).run();

      return new Response(JSON.stringify({ error: 'Invalid password' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    // Successful login — clear previous attempts for this IP
    await env.DB.prepare(
      'DELETE FROM login_attempts WHERE ip = ?'
    ).bind(clientIp).run();

    // Create session token
    const token = crypto.randomUUID();
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(); // 24h

    await env.DB.prepare(
      'INSERT INTO admin_sessions (token, expires_at) VALUES (?, ?)'
    ).bind(token, expiresAt).run();

    return new Response(JSON.stringify({ token, expires: expiresAt }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Admin login error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles GET /api/admin — lists all claims (admin only, session auth required)
 * Supports ?status=pending|approved|rejected, ?city filter, ?limit
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with Authorization: Bearer session token
 * @param {object} context.env - Environment bindings with DB (D1Database)
 * @returns {Promise<Response>} JSON response with claims list or error
 */
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    // Auth check via Bearer token (session)
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    const token = auth.slice(7);
    const session = await env.DB.prepare(
      "SELECT id FROM admin_sessions WHERE token = ? AND expires_at > datetime('now')"
    ).bind(token).first();

    if (!session) {
      return new Response(JSON.stringify({ error: 'Session expired or invalid' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    const url = new URL(request.url);
    const status = url.searchParams.get('status') || 'pending';
    const city = url.searchParams.get('city');
    const limit = parseInt(url.searchParams.get('limit') || '50');

    let query = `SELECT c.*, l.id as listing_id, l.is_closed, l.enrichment
      FROM claims c
      LEFT JOIN listings l ON l.claim_id = c.id AND c.claim_status = 'approved'`;
    const params = [];
    if (status !== 'all') {
      query += ' WHERE c.claim_status = ?';
      params.push(status);
    }

    if (city) {
      query += ' AND c.city = ?';
      params.push(city);
    }

    query += ' ORDER BY c.created_at DESC LIMIT ?';
    params.push(limit);

    const results = await env.DB.prepare(query).bind(...params).all();

    return new Response(JSON.stringify({ claims: results.results, count: results.results.length }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Admin list error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles PUT /api/admin — approve or reject a claim (admin only, session auth required)
 * Also sends magic link email when a claim is approved
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with Authorization: Bearer and JSON body {claim_id, action, admin_notes}
 * @param {object} context.env - Environment bindings with DB (D1Database) and RESEND_API_KEY
 * @param {Function} context.waitUntil - Extends request lifecycle for background tasks
 * @returns {Promise<Response>} JSON response indicating success or error
 */
export async function onRequestPut(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    // Auth check
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    const token = auth.slice(7);
    const session = await env.DB.prepare(
      "SELECT id FROM admin_sessions WHERE token = ? AND expires_at > datetime('now')"
    ).bind(token).first();

    if (!session) {
      return new Response(JSON.stringify({ error: 'Session expired or invalid' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    const body = await request.json();
    const { claim_id, action, admin_notes } = body;

    if (!claim_id || !action || !['approved', 'rejected', 'recover', 'reopen', 'reset', 'dismiss'].includes(action)) {
      return new Response(JSON.stringify({ error: 'claim_id and action (approved|rejected|recover|reopen|reset|dismiss) required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    if (action === 'approved') {
      // Get claim data
      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404,
          headers: corsHeaders,
        });
      }

      // Idempotency guard: prevent approving an already-approved claim
      if (claim.claim_status === 'approved') {
        return new Response(JSON.stringify({
          error: 'Claim is already approved. No action taken.',
        }), { status: 409, headers: corsHeaders });
      }

      // Check if this restaurant already has an approved listing
      let listingId;
      const existing = await env.DB.prepare(
        'SELECT id FROM listings WHERE restaurant_name = ? AND city = ?'
      ).bind(claim.restaurant_name, claim.city).first();

      if (existing) {
        // Update existing listing owner
        await env.DB.prepare(
          'UPDATE listings SET claim_id = ?, updated_at = datetime(\'now\') WHERE id = ?'
        ).bind(claim_id, existing.id).run();
        listingId = existing.id;
      } else {
        // Create new listing
        const result = await env.DB.prepare(
          `INSERT INTO listings (claim_id, restaurant_name, city, fsa_id, claimed_at)
           VALUES (?, ?, ?, ?, datetime('now'))`
        ).bind(claim_id, claim.restaurant_name, claim.city, claim.fsa_id).run();
        listingId = result.meta.last_row_id;
      }

      // Pre-fill with FSA data (address, postcode, description) for SEO/AEO
      if (claim.fsa_id) {
        context.waitUntil((async () => {
          try {
            const fsaRes = await fetch(
              `https://api.ratings.food.gov.uk/Establishments/${claim.fsa_id}`,
              { headers: { 'x-api-version': '2', 'Accept': 'application/json' } }
            );
            if (fsaRes.ok) {
              const fsa = await fsaRes.json();
              // FSA returns { Message: "No establishment found..." } for bad IDs
              if (!fsa || fsa.Message || !fsa.BusinessName) {
                console.log(`FSA returned no data for fsa_id ${claim.fsa_id} — skipping pre-fill`);
                return;
              }
              const addrParts = [fsa.AddressLine1, fsa.AddressLine2, fsa.AddressLine3].filter(Boolean);
              const address = addrParts.join(', ');
              const postcode = fsa.PostCode || '';
              const rating = fsa.RatingValue || '';
              const isTakeaway = (fsa.BusinessType || '').toLowerCase().includes('takeaway');
              const typeLabel = isTakeaway ? 'takeaway' : 'restaurant';
              const hygieneScore = fsa.scores ? fsa.scores.Hygiene : null;
              const structuralScore = fsa.scores ? fsa.scores.Structural : null;
              const managementScore = fsa.scores ? fsa.scores.ConfidenceInManagement : null;

              // --- Generate rich, varied description ---
              const ratingMap = { '5': 'top-rated', '4': 'highly regarded', '3': 'well-established', '2': 'popular', '1': 'local' };
              const ratingWord = ratingMap[rating] || 'local';
              const stars = rating === '5' ? 'five' : rating === '4' ? 'four' : rating === '3' ? 'three' : rating === '2' ? 'two' : 'one';
              const shortAddr = address || addrParts[0] || city;

              // Hygiene insight
              let hygieneInsight = '';
              if (hygieneScore !== null && hygieneScore !== undefined) {
                if (hygieneScore <= 5) hygieneInsight = ` Backed by an excellent FSA hygiene score of ${hygieneScore}/25 (lower is better), diners can eat with confidence.`;
                else if (hygieneScore <= 10) hygieneInsight = ` With a strong FSA hygiene score of ${hygieneScore}/25, cleanliness is clearly a priority here.`;
                else if (hygieneScore <= 15) hygieneInsight = ` Holding a satisfactory FSA hygiene score of ${hygieneScore}/25.`;
              }

              // Rating tail
              let ratingTail = '';
              if (rating === '5') ratingTail = ` — earning a perfect ${stars}-star food hygiene rating from the Food Standards Agency.`;
              else if (rating === '4') ratingTail = ` — holding a strong ${stars}-star food hygiene rating.`;
              else if (rating >= '1') ratingTail = ` — rated ${stars}-star by the Food Standards Agency.`;

              // Multiple templates for variety (seeded by restaurant name + city)
              const seed = (claim.restaurant_name.length + claim.city.length) % 4;
              let desc;
              if (seed === 0) {
                desc = `${claim.restaurant_name} is a ${ratingWord} Thai ${typeLabel} on ${shortAddr} in ${claim.city}${ratingTail}${hygieneInsight} The menu features authentic Thai dishes crafted with traditional recipes and fresh ingredients. Whether you're stopping by for a quick lunch or a relaxed evening meal, expect the warm hospitality and bold, aromatic flavours that have made Thai cuisine a favourite across the UK.`;
              } else if (seed === 1) {
                desc = `Located on ${shortAddr}, ${claim.restaurant_name} brings the vibrant tastes of Thailand to ${claim.city}${ratingTail}${hygieneInsight} From fragrant curries to sizzling stir-fries, every dish is prepared with care using time-honoured techniques and quality produce. The welcoming atmosphere and attentive service make it a favourite for ${typeLabel === 'takeaway' ? 'takeaway Thai food' : 'a meal out'} in the area.`;
              } else if (seed === 2) {
                desc = `${claim.restaurant_name} serves authentic Thai cuisine from its ${typeLabel === 'takeaway' ? 'kitchen' : 'restaurant'} on ${shortAddr}, ${claim.city}${ratingTail}${hygieneInsight} Known for generous portions and consistent quality, it has built a loyal following among locals who appreciate genuine Thai cooking. The menu covers all the classics — from pad thai and green curry to som tam and tom yum — all made fresh to order.`;
              } else {
                desc = `For authentic Thai food in ${claim.city}, ${claim.restaurant_name} on ${shortAddr} delivers${ratingTail}${hygieneInsight} The kitchen takes pride in sourcing quality ingredients and staying true to traditional recipes passed down through generations. Expect balanced flavours, fresh herbs, and the perfect blend of sweet, sour, salty, and spicy that defines great Thai cooking.`;
              }

              // Append customisation hint
              desc += ` [The owner can edit this description to add their story, signature dishes, and what makes ${claim.restaurant_name} unique.]`;

              await env.DB.prepare(
                `UPDATE listings SET address = ?, postcode = ?, description = ?, updated_at = datetime('now') WHERE id = ?`
              ).bind(address, postcode, desc, listingId).run();
            }
          } catch (e) {
            console.error(`FSA pre-fill error for listing ${listingId}: ${e.message}`);
          }
        })());
      }

      // Update claim status
      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'approved', reviewed_at = datetime('now'), admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      // Auto-generate magic link and email it to the owner
      const rawToken = crypto.randomUUID();
      const tokenHash = await sha256(rawToken);
      const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString(); // 1 hour

      await env.DB.prepare(
        'INSERT INTO auth_tokens (listing_id, token_hash, expires_at) VALUES (?, ?, ?)'
      ).bind(listingId, tokenHash, expiresAt).run();

const magicLink = 'https://thaidata.uk/listing/manage?token=' + rawToken;
      // Send magic link email inline (not waitUntil — confirmed unreliable for Resend)
      await sendMagicLinkEmail(env, {
        email: claim.claimer_email,
        restaurant_name: claim.restaurant_name,
        city: claim.city,
        magicLink,
        claimId: claim_id,
      });

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim approved. Magic link emailed to owner.',
        claim_id,
      }), {
        status: 200,
        headers: corsHeaders,
      });

    } else if (action === 'recover') {
      const { new_email } = body;
      if (!new_email) {
        return new Response(JSON.stringify({ error: 'new_email required' }), {
          status: 400, headers: corsHeaders,
        });
      }

      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404, headers: corsHeaders,
        });
      }
      if (claim.claim_status !== 'approved') {
        return new Response(JSON.stringify({ error: 'Claim must be approved first' }), {
          status: 400, headers: corsHeaders,
        });
      }

      const oldEmail = claim.claimer_email;
      const auditLine = `[${new Date().toISOString()}] Admin session ${session.id} recovery: claimer_email changed from ${oldEmail} to ${new_email}.`;
      const updatedNotes = [claim.admin_notes, auditLine].filter(Boolean).join('\n');

      await env.DB.prepare(
        "UPDATE claims SET claimer_email = ?, admin_notes = ? WHERE id = ?"
      ).bind(new_email, updatedNotes, claim_id).run();

      // Generate fresh magic link
      const rawToken = crypto.randomUUID();
      const tokenHash = await sha256(rawToken);
      const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();

      const listing = await env.DB.prepare(
        'SELECT id FROM listings WHERE claim_id = ?'
      ).bind(claim_id).first();

      if (listing) {
        await env.DB.prepare(
          'INSERT INTO auth_tokens (listing_id, token_hash, expires_at) VALUES (?, ?, ?)'
        ).bind(listing.id, tokenHash, expiresAt).run();

        await sendRecoveryEmail(env, {
          email: new_email,
          restaurant_name: claim.restaurant_name,
          city: claim.city,
          magicLink: `https://thaidata.uk/listing/manage?token=${rawToken}`,
          claimId: claim_id,
        });
      }

      return new Response(JSON.stringify({
        success: true,
        message: `Recovery email sent to ${new_email}.`,
        claim_id,
      }), { status: 200, headers: corsHeaders });
    } else if (action === 'reopen') {
      // Reopen a rejected claim back to pending for re-review
      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404, headers: corsHeaders,
        });
      }
      if (claim.claim_status !== 'rejected') {
        return new Response(JSON.stringify({ error: 'Can only reopen rejected claims' }), {
          status: 400, headers: corsHeaders,
        });
      }

      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'pending', reviewed_at = NULL, admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim reopened for review.',
        claim_id,
      }), { status: 200, headers: corsHeaders });
    } else if (action === 'dismiss') {
      // Archive a rejected claim — removes from active review
      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404, headers: corsHeaders,
        });
      }
      if (claim.claim_status === 'archived') {
        return new Response(JSON.stringify({ error: 'Claim is already archived' }), {
          status: 400, headers: corsHeaders,
        });
      }

      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'archived', reviewed_at = datetime('now'), admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim archived. No longer appears in active review.',
        claim_id,
      }), { status: 200, headers: corsHeaders });
    } else if (action === 'reset') {
      // Reset a listing back to defaults + reopen claim for re-review
      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404, headers: corsHeaders,
        });
      }

      // Clear owner-editable listing fields, keep name/city/fsa address/postcode
      await env.DB.prepare(
        `UPDATE listings SET
          description = NULL, cuisine_specialty = NULL, phone = NULL, email = NULL,
          website = NULL, social_instagram = NULL, social_facebook = NULL, social_twitter = NULL,
          opening_hours = NULL, price_range = NULL, features = NULL, menu_highlights = NULL,
          enrichment = NULL, updated_at = datetime('now')
        WHERE claim_id = ?`
      ).bind(claim_id).run();

      // Invalidate existing auth tokens
      await env.DB.prepare(
        'DELETE FROM auth_tokens WHERE listing_id IN (SELECT id FROM listings WHERE claim_id = ?)'
      ).bind(claim_id).run();

      // Set claim back to pending for re-review
      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'pending', reviewed_at = NULL, admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      return new Response(JSON.stringify({
        success: true,
        message: 'Listing reset. Claim reopened for review.',
        claim_id,
      }), { status: 200, headers: corsHeaders });
    } else {
      // Reject — fetch claim data first, then send email
      const claim = await env.DB.prepare('SELECT * FROM claims WHERE id = ?').bind(claim_id).first();
      if (!claim) {
        return new Response(JSON.stringify({ error: 'Claim not found' }), {
          status: 404,
          headers: corsHeaders,
        });
      }

      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'rejected', reviewed_at = datetime('now'), admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      // Send rejection email inline (not waitUntil)
      await sendClaimRejectedEmail(env, {
        claimer_name: claim.claimer_name,
        claimer_email: claim.claimer_email,
        restaurant_name: claim.restaurant_name,
        city: claim.city,
        claimId: claim_id,
      });

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim rejected.',
        claim_id,
      }), {
        status: 200,
        headers: corsHeaders,
      });
    }

  } catch (err) {
    console.error('Admin action error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles DELETE /api/admin — deletes a claim and associated listing (admin only, session auth required)
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with Authorization: Bearer and ?claim_id param
 * @param {object} context.env - Environment bindings with DB (D1Database)
 * @returns {Promise<Response>} JSON response indicating success or error
 */
export async function onRequestDelete(context) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };
  return new Response(JSON.stringify({
    error: 'DELETE is disabled. No destructive operations permitted in the legacy admin.',
  }), { status: 405, headers: corsHeaders });
}

/**
 * Handles PATCH /api/admin — update a single listing field (admin only)
 * Body: { listing_id, field, value }
 * Whitelist: restaurant_name, city, description, phone, opening_hours, website,
 *   social_instagram, social_facebook, email, address, postcode, cuisine_specialty
 */
export async function onRequestPatch(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: corsHeaders,
      });
    }
    const token = auth.slice(7);
    const session = await env.DB.prepare(
      "SELECT id FROM admin_sessions WHERE token = ? AND expires_at > datetime('now')"
    ).bind(token).first();
    if (!session) {
      return new Response(JSON.stringify({ error: 'Session expired or invalid' }), {
        status: 403, headers: corsHeaders,
      });
    }

    const body = await request.json();
    const { listing_id, field, value } = body;
    const allowed = new Set([
      'restaurant_name', 'city', 'description', 'phone', 'opening_hours',
      'website', 'social_instagram', 'social_facebook', 'email', 'address',
      'postcode', 'cuisine_specialty'
    ]);
    if (!listing_id || !field || !allowed.has(field)) {
      return new Response(JSON.stringify({ error: 'listing_id, field (whitelisted), and value required' }), {
        status: 400, headers: corsHeaders,
      });
    }

    await env.DB.prepare(
      `UPDATE listings SET ${field} = ?, updated_at = datetime('now') WHERE id = ?`
    ).bind(value, listing_id).run();

    return new Response(JSON.stringify({ success: true, listing_id, field, value }), {
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    console.error('Admin patch error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

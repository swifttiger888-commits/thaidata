// ThaiData UK — /api/admin
// Admin panel: review claims, approve/reject, manage listings

/**
 * Computes SHA-256 hex digest of a string
 * @param {string} text - Text to hash (e.g. auth token)
 * @returns {Promise<string>} Hex-encoded SHA-256 hash
 */
async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Sends approval email with magic link via Resend API
 * @param {object} env - Cloudflare Workers environment bindings
 * @param {string} env.RESEND_API_KEY - Resend API key for sending emails
 * @param {object} options - Email parameters
 * @param {string} options.email - Recipient email address
 * @param {string} options.restaurant_name - Name of the restaurant
 * @param {string} options.city - City of the restaurant
 * @param {string} options.magicLink - One-time magic link URL
 * @returns {Promise<void>}
 */
async function sendMagicLinkEmail(env, { email, restaurant_name, city, magicLink }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    console.error('Missing RESEND_API_KEY — cannot send magic link email');
    return;
  }

  const html = '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>\n<body style="margin:0;padding:0;background-color:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;">\n  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:40px 0;">\n    <tr>\n      <td align="center">\n        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">\n          <tr>\n            <td style="padding:32px 40px 0;">\n              <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#10B981,#059669);border-radius:12px;">\n                <tr>\n                  <td style="padding:32px 32px 24px;text-align:center;">\n                    <img src="https://thaidata.uk/static/logo-email.png" width="180" height="72" alt="ThaiData UK" style="display:block;border:0;outline:none;margin:0 auto 20px;">\n                    <h1 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">Your Listing Is Ready!</h1>\n                    <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;line-height:1.5;">' + restaurant_name + '<br>\n                      <span style="font-size:13px;opacity:0.7;">' + city + '</span>\n                    </p>\n                  </td>\n                </tr>\n              </table>\n            </td>\n          </tr>\n          <tr>\n            <td style="padding:24px 40px 32px;">\n              <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;border:1px solid #e8e8dc;">\n                <tr>\n                  <td style="padding:32px;">\n                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">\n                      Great news — your claim for ' + restaurant_name + ' has been approved! 🎉\n                    </p>\n                    <p style="margin:0 0 20px;color:#555;font-size:14px;line-height:1.6;">\n                      You can now add photos, description, opening hours, and more to your listing on ThaiData UK.\n                    </p>\n                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">\n                      <tr>\n                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Photos, description & cuisine specialities</td>\n                      </tr>\n                      <tr>\n                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Opening hours, website & social links</td>\n                      </tr>\n                      <tr>\n                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Contact details & price range</td>\n                      </tr>\n                    </table>\n                    <table width="100%" cellpadding="0" cellspacing="0">\n                      <tr>\n                        <td align="center">\n                          <a href="' + magicLink + '" style="display:inline-block;background:#10B981;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">Edit My Listing →</a>\n                        </td>\n                      </tr>\n                    </table>\n                    <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">\n                      This link expires in 1 hour and can only be used once.<br>\n                      Need another? Visit thaidata.uk/listing/manage\n                    </p>\n                  </td>\n                </tr>\n              </table>\n            </td>\n          </tr>\n          <tr>\n            <td style="padding:0 40px 32px;text-align:center;">\n              <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">\n                ThaiData UK · The UK\'s Thai restaurant directory<br>\n                <a href="https://thaidata.uk" style="color:#10B981;text-decoration:none;">thaidata.uk</a>\n              </p>\n            </td>\n          </tr>\n        </table>\n      </td>\n    </tr>\n  </table>\n</body>\n</html>';

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'ThaiData UK <noreply@thaidata.uk>',
        to: [email],
        subject: '🎉 Your listing is ready — ' + restaurant_name,
        html: html,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error('Resend API error ' + res.status + ': ' + errBody);
    } else {
      console.log('Approval email sent to ' + email + ' for ' + restaurant_name);
    }
  } catch (err) {
    console.error('Resend send failed:', err.message);
  }
}

/**
 * Sends claim rejection email via Resend API
 * @param {object} env - Cloudflare Workers environment bindings
 * @param {string} env.RESEND_API_KEY - Resend API key
 * @param {object} options - Email parameters
 * @param {string} options.claimer_name - Name of the claimant
 * @param {string} options.claimer_email - Recipient email address
 * @param {string} options.restaurant_name - Name of the restaurant
 * @param {string} options.city - City of the restaurant
 * @returns {Promise<void>}
 */
async function sendClaimRejectedEmail(env, { claimer_name, claimer_email, restaurant_name, city }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    console.error('Missing RESEND_API_KEY — cannot send rejection email');
    return;
  }

  const html = '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>\n<body style="margin:0;padding:0;background-color:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;">\n  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:40px 0;">\n    <tr>\n      <td align="center">\n        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">\n          <tr>\n            <td style="padding:32px 40px 0;">\n              <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#10B981,#059669);border-radius:12px;">\n                <tr>\n                  <td style="padding:32px 32px 24px;text-align:center;">\n                    <img src="https://thaidata.uk/static/logo-email.png" width="180" height="72" alt="ThaiData UK" style="display:block;border:0;outline:none;margin:0 auto 20px;">\n                    <h1 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">Claim Update</h1>\n                    <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;line-height:1.5;">' + restaurant_name + '<br>\n                      <span style="font-size:13px;opacity:0.7;">' + city + '</span>\n                    </p>\n                  </td>\n                </tr>\n              </table>\n            </td>\n          </tr>\n          <tr>\n            <td style="padding:24px 40px 32px;">\n              <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;border:1px solid #e8e8dc;">\n                <tr>\n                  <td style="padding:32px;">\n                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">\n                      Hi ' + claimer_name + ',</p>\n                    <p style="margin:0 0 16px;color:#555555;font-size:14px;line-height:1.6;">\n                      Thanks for submitting a claim for <strong>' + restaurant_name + '</strong> in ' + city + '.</p>\n                    <p style="margin:0 0 16px;color:#555555;font-size:14px;line-height:1.6;">\n                      We&rsquo;ve reviewed the request and couldn&rsquo;t verify the claim at this time.</p>\n                    <p style="margin:0 0 24px;color:#555555;font-size:14px;line-height:1.6;">\n                      If you believe this was a mistake, please reply to this email with any extra details that help confirm your connection to the restaurant.</p>\n                    <p style="margin:0;color:#555555;font-size:14px;line-height:1.6;">\n                      Thanks,<br>The ThaiData team</p>\n                  </td>\n                </tr>\n              </table>\n            </td>\n          </tr>\n          <tr>\n            <td style="padding:0 40px 32px;text-align:center;">\n              <p style="margin:0;color:#aaaaaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#10B981;text-decoration:none;">thaidata.uk</a></p>\n            </td>\n          </tr>\n        </table>\n      </td>\n    </tr>\n  </table>\n</body>\n</html>';

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'ThaiData UK <noreply@thaidata.uk>',
        to: [claimer_email],
        subject: 'Update on your ThaiData claim for ' + restaurant_name,
        html: html,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error('Resend API error ' + res.status + ': ' + errBody);
    } else {
      console.log('Rejection email sent to ' + claimer_email + ' for ' + restaurant_name);
    }
  } catch (err) {
    console.error('Resend send failed:', err.message);
  }
}

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

    let query = `SELECT c.*, l.enrichment
      FROM claims c
      LEFT JOIN listings l ON l.claim_id = c.id`;
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

    if (!claim_id || !action || !['approved', 'rejected', 'recover'].includes(action)) {
      return new Response(JSON.stringify({ error: 'claim_id and action (approved|rejected|recover) required' }), {
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

        await sendMagicLinkEmail(env, {
          email: new_email,
          restaurant_name: claim.restaurant_name,
          city: claim.city,
          magicLink: `https://thaidata.uk/listing/manage?token=${rawToken}`,
        });
      }

      return new Response(JSON.stringify({
        success: true,
        message: `Recovery email sent to ${new_email}.`,
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

    const url = new URL(request.url);
    const claimId = url.searchParams.get('claim_id');

    if (!claimId) {
      return new Response(JSON.stringify({ error: 'claim_id required' }), {
        status: 400, headers: corsHeaders,
      });
    }

    // Delete listing if exists
    await env.DB.prepare('DELETE FROM listings WHERE claim_id = ?').bind(claimId).run();
    // Delete auth tokens for this listing
    await env.DB.prepare('DELETE FROM auth_tokens WHERE listing_id NOT IN (SELECT id FROM listings)').run();
    // Delete the claim
    await env.DB.prepare('DELETE FROM claims WHERE id = ?').bind(claimId).run();

    return new Response(JSON.stringify({
      success: true,
      message: `Claim ${claimId} and associated listing deleted.`,
    }), {
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    console.error('Admin delete error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
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

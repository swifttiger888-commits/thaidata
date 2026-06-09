// ThaiData UK — /api/listing
// Get and update enhanced restaurant listings

// --- Crypto helper ---
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

// --- Resend email sender ---
/**
 * Sends a magic-link email via Resend API to a restaurant owner
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

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

          <!-- Hero + Logo combined -->
          <tr>
            <td style="padding:32px 40px 0;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#10B981,#059669);border-radius:12px;">
                <tr>
                  <td style="padding:32px 32px 24px;text-align:center;">
                    <img src="https://thaidata.uk/static/logo-email.png" width="180" height="72" alt="ThaiData UK" style="display:block;border:0;outline:none;margin:0 auto 20px;">
                    <h1 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">Manage Your Listing</h1>
                    <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;line-height:1.5;">
                      ${restaurant_name}<br>
                      <span style="font-size:13px;opacity:0.7;">${city}</span>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:24px 40px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;border:1px solid #e8e8dc;">
                <tr>
                  <td style="padding:32px;">
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                      You're one click away from editing your restaurant listing on ThaiData UK — the UK's fastest-growing Thai restaurant directory.
                    </p>

                    <p style="margin:0 0 20px;color:#555;font-size:14px;line-height:1.6;">
                      What you can update:
                    </p>

                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Photos, description & cuisine specialities</td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Opening hours, website & social links</td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Contact details & price range</td>
                      </tr>
                    </table>

                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center">
                          <a href="${magicLink}" style="display:inline-block;background:#10B981;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">Edit My Listing →</a>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">
                      This link expires in 1 hour and can only be used once.<br>
                      If you didn't request this, you can safely ignore this email.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">
                ThaiData UK · The UK's Thai restaurant directory<br>
                <a href="https://thaidata.uk" style="color:#10B981;text-decoration:none;">thaidata.uk</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
`;

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'ThaiData UK <noreply@thaidata.uk>',
        to: [email],
        subject: `🔑 Your magic link for ${restaurant_name}`,
        html,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error(`Resend API error ${res.status}: ${errBody}`);
    } else {
      console.log(`Magic link email sent to ${email} for ${restaurant_name}`);
    }
  } catch (err) {
    console.error('Resend send failed:', err.message);
  }
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

    // Public queries — archived. No active public listings.
    return new Response(JSON.stringify({
      listings: [],
      count: 0,
      message: 'Listing system is archived.',
    }), {
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
      matchQuery = "SELECT c.id as claim_id, c.claimer_email, l.id as listing_id FROM claims c LEFT JOIN listings l ON l.claim_id = c.id WHERE c.fsa_id = ? AND c.claimer_email = ? AND c.claim_status = 'approved'";
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

// ThaiData UK — /api/listing
// Get and update enhanced restaurant listings

// --- Crypto helper ---
async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// --- Resend email sender ---
async function sendMagicLinkEmail(env, { email, restaurant_name, city, magicLink }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    console.error('Missing RESEND_API_KEY — cannot send magic link email');
    return;
  }

  const html = `<html lang="en">
  <head> </head>
  <body style="margin:0;padding:0;background-color:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:40px 0;">
      <tr>
        <td align="center">
          <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
            <tr>
              <td style="padding:24px 40px;text-align:center;background-color:#0C1220;border-radius:10px 10px 0 0;">
                <img src="https://thaidata.uk/static/logo-email.png" width="200" height="80" alt="ThaiData UK" style="display:block;border:0;outline:none;">
              </td>
            </tr>

            <tr>
              <td style="padding:32px 40px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#10B981,#059669);border-radius:12px;">
                  <tr>
                    <td style="padding:36px 32px;text-align:center;">
                      <h1 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">
                        Manage Your Listing
                      </h1>
                      <p style="margin:0;color:rgba(255,255,255,0.85);font-size:15px;line-height:1.5;">
                        ${restaurant_name}<br />
                        <span style="font-size:13px;opacity:0.8;">${city}</span>
                      </p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:32px 40px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;border:1px solid #e8e8dc;">
                  <tr>
                    <td style="padding:32px;">
                      <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                        You're one click away from editing your restaurant listing on ThaiData UK — the UK's
                        fastest-growing Thai restaurant directory.
                      </p>

                      <p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6;">What you can update:</p>

                      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                        <tr>
                          <td style="padding:6px 0;color:#444;font-size:14px;vertical-align:top;width:24px;">✓</td>
                          <td style="padding:6px 0;color:#444;font-size:14px;">
                            Photos, description &amp; cuisine specialities
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:6px 0;color:#444;font-size:14px;vertical-align:top;">✓</td>
                          <td style="padding:6px 0;color:#444;font-size:14px;">
                            Opening hours, website &amp; social links
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:6px 0;color:#444;font-size:14px;vertical-align:top;">✓</td>
                          <td style="padding:6px 0;color:#444;font-size:14px;">Contact details &amp; price range</td>
                        </tr>
                      </table>

                      <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                          <td align="center">
                            <a href="${magicLink}" style="display:inline-block;background:#10B981;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;letter-spacing:-0.2px;">Edit My Listing →</a>
                          </td>
                        </tr>
                      </table>

                      <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">
                        This link expires in 1 hour and can only be used once.<br />
                        If you didn't request this, you can safely ignore this email.
                      </p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:0 40px 32px;text-align:center;">
                <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">
                  ThaiData UK · The UK's Thai restaurant directory<br />
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

// GET /api/listing — get enhanced listing(s)
// Supports:
//   ?restaurant=X&city=Y  — specific listing
//   ?fsa_id=X             — by FSA ID
//   ?city=X               — all listings in a city
//   Authorization: Bearer ***  — get listing by auth token (owner view)
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

// PUT /api/listing — update enhanced listing (owner only, via magic link token)
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
      'address', 'postcode', 'opening_hours', 'price_range', 'features', 'photos'
    ];

    // Build SET clause from allowed fields
    const sets = [];
    const params = [];

    for (const field of allowedFields) {
      if (body[field] !== undefined) {
        sets.push(`${field} = ?`);
        // Stringify arrays/objects
        params.push(
          (field === 'features' || field === 'photos')
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

// POST /api/listing — request a magic link to edit listing
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { restaurant_name, city, email } = body;

    if (!restaurant_name || !city || !email) {
      return new Response(JSON.stringify({ error: 'restaurant_name, city, and email required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Find the approved claim for this restaurant + email match
    const claim = await env.DB.prepare(
      "SELECT c.id as claim_id, c.claimer_email, l.id as listing_id FROM claims c LEFT JOIN listings l ON l.claim_id = c.id WHERE c.restaurant_name = ? AND c.city = ? AND c.claimer_email = ? AND c.claim_status = 'approved'"
    ).bind(restaurant_name, city, email).first();

    if (!claim) {
      return new Response(JSON.stringify({ error: 'No approved claim found for this restaurant and email combination' }), {
        status: 404,
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

    // Send magic link email via Resend (fire-and-forget)
    const magicLink = `https://thaidata.uk/listing/manage?token=${token}`;
    context.waitUntil(sendMagicLinkEmail(env, {
      email: claim.claimer_email,
      restaurant_name,
      city,
      magicLink,
    }));

    return new Response(JSON.stringify({
      success: true,
      message: 'Magic link sent! Check your email.',
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

// ThaiData UK — /api/admin
// Admin panel: review claims, approve/reject, manage listings

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

const ADMIN_PASSWORD = typeof ADMIN_PASSWORD !== 'undefined' ? ADMIN_PASSWORD : null;

function requireAdmin(request, env) {
  const auth = request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Bearer ')) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const password = auth.slice(7);
  // Simple constant-time-ish comparison via env variable
  if (password !== env.ADMIN_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return null; // Authorized
}

// POST /api/admin/login — simple password auth, returns session token
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { password } = body;

    if (!password || password !== env.ADMIN_PASSWORD) {
      return new Response(JSON.stringify({ error: 'Invalid password' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

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

// GET /api/admin — list all claims (admin only)
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

    let query = 'SELECT * FROM claims WHERE claim_status = ?';
    const params = [status];

    if (city) {
      query += ' AND city = ?';
      params.push(city);
    }

    query += ' ORDER BY created_at DESC LIMIT ?';
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

// PUT /api/admin — approve or reject a claim
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

    if (!claim_id || !action || !['approved', 'rejected'].includes(action)) {
      return new Response(JSON.stringify({ error: 'claim_id and action (approved|rejected) required' }), {
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
              const shortAddr = addrParts[0] || city;

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
                desc = `Located on ${shortAddr}, ${claim.restaurant_name} brings the vibrant tastes of Thailand to ${claim.city}${ratingTail}${hygieneInsight} From fragrant curries to sizzling stir-fries, every dish is prepared with care using time-honoured techniques and quality produce. The welcoming atmosphere and attentive service make it a go-to for ${typeLabel === 'takeaway' ? 'takeaway Thai food' : 'dining in'} in the area.`;
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
      context.waitUntil(sendMagicLinkEmail(env, {
        email: claim.claimer_email,
        restaurant_name: claim.restaurant_name,
        city: claim.city,
        magicLink,
      }));

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim approved. Magic link emailed to owner.',
        claim_id,
      }), {
        status: 200,
        headers: corsHeaders,
      });

    } else {
      // Reject
      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'rejected', reviewed_at = datetime('now'), admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

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

// ThaiData UK — POST /api/claim
// Submit a claim for a Thai restaurant listing

/**
 * Handles POST /api/claim — submits a new claim for a restaurant listing
 * Validates required fields, checks for duplicates, inserts claim, and sends admin notification
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with JSON body {restaurant_name, city, fsa_id, business_type, claimer_name, claimer_email, ...}
 * @param {object} context.env - Environment bindings with DB (D1Database), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
 * @param {Function} context.waitUntil - Extends request lifecycle for background tasks
 * @returns {Promise<Response>} JSON response with claim result or error
 * @throws {Error} When database operation fails (caught internally)
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { restaurant_name, city, fsa_id, business_type, claimer_name, claimer_email, claimer_phone, claimer_role, verification_notes } = body;

    // Validate required fields
    if (!restaurant_name || !city || !claimer_name || !claimer_email) {
      return new Response(JSON.stringify({ error: 'Missing required fields: restaurant_name, city, claimer_name, claimer_email' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Validate email format
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(claimer_email)) {
      return new Response(JSON.stringify({ error: 'Invalid email address' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Check if restaurant is already claimed
    const existing = await env.DB.prepare(
      'SELECT id FROM claims WHERE restaurant_name = ? AND city = ? AND claim_status = ?'
    ).bind(restaurant_name, city, 'approved').first();

    if (existing) {
      return new Response(JSON.stringify({ error: 'This restaurant has already been claimed', status: 'already_claimed' }), {
        status: 409,
        headers: corsHeaders,
      });
    }

    // Check for duplicate pending claim
    const pending = await env.DB.prepare(
      'SELECT id FROM claims WHERE restaurant_name = ? AND city = ? AND claimer_email = ? AND claim_status = ?'
    ).bind(restaurant_name, city, claimer_email, 'pending').first();

    if (pending) {
      return new Response(JSON.stringify({ message: 'You already have a pending claim for this restaurant', status: 'duplicate', id: pending.id }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Check if restaurant is marked as permanently closed
    const closedListing = await env.DB.prepare(
      'SELECT id FROM listings WHERE restaurant_name = ? AND city = ? AND is_closed = 1'
    ).bind(restaurant_name, city).first();

    if (closedListing) {
      return new Response(JSON.stringify({
        error: 'This venue has been marked as permanently closed and cannot be claimed.',
        status: 'permanently_closed'
      }), {
        status: 410,
        headers: corsHeaders,
      });
    }

    // Insert claim
    const result = await env.DB.prepare(
      `INSERT INTO claims (restaurant_name, city, fsa_id, business_type, claimer_name, claimer_email, claimer_phone, claimer_role, verification_notes)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(restaurant_name, city, fsa_id || null, business_type || 'restaurant', claimer_name, claimer_email, claimer_phone || null, claimer_role || 'owner', verification_notes || null).run();

    const claimId = result.meta.last_row_id;

    // Send both notifications before responding (inline, not waitUntil)
    await Promise.allSettled([
      sendAdminNotification(env, {
        id: claimId,
        restaurant_name,
        city,
        claimer_name,
        claimer_email,
        claimer_phone,
        claimer_role,
        business_type,
      }),
      sendClaimConfirmationEmail(env, {
        claimer_name,
        claimer_email,
        restaurant_name,
        city,
      }),
    ]);

    return new Response(JSON.stringify({
      success: true,
      message: 'Claim submitted successfully. We will review and get back to you within 48 hours.',
      id: claimId,
    }), {
      status: 201,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Claim submission error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles GET /api/claim — checks claim status by email (and optional restaurant+city)
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with ?email (and ?restaurant & ?city) params
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
    const url = new URL(request.url);
    const email = url.searchParams.get('email');
    const restaurant = url.searchParams.get('restaurant');
    const city = url.searchParams.get('city');

    if (!email) {
      return new Response(JSON.stringify({ error: 'Email parameter required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    let query = 'SELECT id, restaurant_name, city, claim_status, created_at, reviewed_at FROM claims WHERE claimer_email = ?';
    const params = [email];

    if (restaurant && city) {
      query += ' AND restaurant_name = ? AND city = ?';
      params.push(restaurant, city);
    }

    query += ' ORDER BY created_at DESC LIMIT 10';

    const results = await env.DB.prepare(query).bind(...params).all();

    return new Response(JSON.stringify({ claims: results.results }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Claim lookup error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Sends a Telegram notification to the admin about a new claim submission
 * @param {object} env - Cloudflare Workers environment bindings
 * @param {string} env.TELEGRAM_BOT_TOKEN - Telegram bot token for sending messages
 * @param {string} env.TELEGRAM_CHAT_ID - Telegram chat ID to send notifications to
 * @param {object} claim - Claim data object
 * @param {number} claim.id - Claim ID
 * @param {string} claim.restaurant_name - Restaurant name
 * @param {string} claim.city - City
 * @param {string} claim.claimer_name - Name of the person claiming
 * @param {string} claim.claimer_email - Email of the person claiming
 * @param {string} [claim.claimer_phone] - Phone number (optional)
 * @param {string} [claim.claimer_role] - Role (owner, manager, head_chef, staff)
 * @param {string} [claim.business_type] - Type of business (restaurant, takeaway)
 * @returns {Promise<void>}
 */
async function sendAdminNotification(env, claim) {
  const botToken = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;

  if (!botToken || !chatId) {
    console.log('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — skipping notification');
    return;
  }

  const businessType = claim.business_type === 'takeaway' ? 'Takeaway' : 'Restaurant';
  const phoneLine = claim.claimer_phone ? `\n📞 ${claim.claimer_phone}` : '';
  const role = claim.claimer_role === 'owner' ? 'Owner' : claim.claimer_role === 'manager' ? 'Manager' : claim.claimer_role === 'head_chef' ? 'Head Chef' : 'Staff';

  const text = `🔔 *New Claim Submitted* #${claim.id}\n\n` +
    `*${claim.restaurant_name}*\n` +
    `📍 ${claim.city}  ·  ${businessType}\n\n` +
    `👤 ${claim.claimer_name} (${role})\n` +
    `✉️ ${claim.claimer_email}${phoneLine}\n\n` +
    `[Review now →](https://thaidata.uk/admin/)`;

  try {
    const res = await fetch(
      `https://api.telegram.org/bot${botToken}/sendMessage`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chatId,
          text: text,
          parse_mode: 'Markdown',
          disable_web_page_preview: true,
        }),
      }
    );

    if (!res.ok) {
      console.error(`Telegram API error: ${res.status} — ${await res.text()}`);
    } else {
      console.log(`Telegram notification sent for claim #${claim.id}`);
    }
  } catch (err) {
    console.error('Telegram notification failed:', err.message);
  }
}

/**
 * Sends a confirmation email to the claimant about their submitted claim
 * @param {object} env - Cloudflare Workers environment bindings
 * @param {string} env.RESEND_API_KEY - Resend API key for sending emails
 * @param {object} data - Claim data
 * @param {string} data.claimer_name - Name of the person claiming
 * @param {string} data.claimer_email - Email of the person claiming
 * @param {string} data.restaurant_name - Restaurant name
 * @param {string} data.city - City
 * @returns {Promise<void>}
 */
async function sendClaimConfirmationEmail(env, { claimer_name, claimer_email, restaurant_name, city }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    console.error('Missing RESEND_API_KEY — cannot send claim confirmation email');
    return;
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" style="padding:40px 0;"><tr><td align="center">
<table width="560" style="max-width:560px;">
<tr><td style="padding:0 40px;">
<table width="100%" style="background:linear-gradient(135deg,#10B981,#059669);border-radius:12px;">
<tr><td style="padding:32px;text-align:center;">
<img src="https://thaidata.uk/static/logo-email.png" width="180" height="72" alt="ThaiData" style="display:block;border:0;margin:0 auto 16px;">
<h1 style="margin:0 0 4px;color:#fff;font-size:20px;font-weight:700;">Claim Received</h1>
<p style="margin:0;color:rgba(255,255,255,0.85);font-size:13px;">${restaurant_name} &middot; ${city}</p>
</td></tr></table>
</td></tr>
<tr><td style="padding:24px 40px;">
<table width="100%" style="background:#fff;border-radius:10px;border:1px solid #e8e8dc;">
<tr><td style="padding:32px;">
<p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">Hi ${claimer_name},</p>
<p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">We&rsquo;ve received your claim for <strong>${restaurant_name}</strong> in ${city}.</p>
<p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">We&rsquo;ll review your details and, if everything looks good, send you a one&shy;time magic link so you can edit your ThaiData listing.</p>
<p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6;">You don&rsquo;t need to do anything else right now. If you made this request by mistake, you can ignore this email.</p>
<p style="margin:0;color:#555;font-size:14px;line-height:1.6;">Thanks,<br>The ThaiData team</p>
</td></tr></table>
</td></tr>
<tr><td style="padding:0 40px 32px;text-align:center;">
<p style="margin:0;color:#aaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#10B981;text-decoration:none;">thaidata.uk</a></p>
</td></tr></table>
</td></tr></table>
</body>
</html>`;

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'ThaiData UK <noreply@thaidata.uk>',
        to: [claimer_email],
        subject: `We\u2019ve received your claim for ${restaurant_name}`,
        html,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error(`Resend API error ${res.status}: ${errBody}`);
    } else {
      console.log(`Claim confirmation email sent to ${claimer_email} for ${restaurant_name}`);
    }
  } catch (err) {
    console.error('Resend claim confirmation failed:', err.message);
  }
}

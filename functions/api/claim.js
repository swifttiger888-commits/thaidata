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

    // Insert claim
    const result = await env.DB.prepare(
      `INSERT INTO claims (restaurant_name, city, fsa_id, business_type, claimer_name, claimer_email, claimer_phone, claimer_role, verification_notes)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(restaurant_name, city, fsa_id || null, business_type || 'restaurant', claimer_name, claimer_email, claimer_phone || null, claimer_role || 'owner', verification_notes || null).run();

    const claimId = result.meta.last_row_id;

    // Fire-and-forget email notification to admin
    context.waitUntil(sendAdminNotification(env, {
      id: claimId,
      restaurant_name,
      city,
      claimer_name,
      claimer_email,
      claimer_phone,
      claimer_role,
      business_type,
    }));

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

// ThaiData UK — POST /api/claim
// Submit a claim for a Thai restaurant listing

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

// GET /api/claim?email=... — check claim status
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

// --- Email notification via MailChannels (free for Cloudflare Workers) ---

async function sendAdminNotification(env, claim) {
  const adminEmail = env.ADMIN_EMAIL || env.ADMIN_EMAIL_FALLBACK;
  if (!adminEmail) {
    console.log('No ADMIN_EMAIL set — skipping notification');
    return;
  }

  const claimUrl = `https://thaidata.uk/admin/`;
  const businessType = claim.business_type === 'takeaway' ? 'Takeaway' : 'Restaurant';
  const phoneLine = claim.claimer_phone ? `\nPhone: ${claim.claimer_phone}` : '';
  const role = claim.claimer_role === 'owner' ? 'Owner' : claim.claimer_role === 'manager' ? 'Manager' : claim.claimer_role === 'head_chef' ? 'Head Chef' : 'Staff';

  try {
    const res = await fetch('https://api.mailchannels.net/tx/v1/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        personalizations: [{
          to: [{ email: adminEmail }],
        }],
        from: {
          email: 'claims@thaidata.uk',
          name: 'ThaiData Claims',
        },
        subject: `🔔 New Claim: ${claim.restaurant_name} (${claim.city})`,
        content: [{
          type: 'text/plain',
          value: `New claim submitted on ThaiData.uk\n\n` +
            `${claim.restaurant_name} — ${claim.city}\n` +
            `${businessType} | Claim #${claim.id}\n\n` +
            `Claimer: ${claim.claimer_name} (${role})\n` +
            `Email: ${claim.claimer_email}${phoneLine}\n\n` +
            `Review now: ${claimUrl}\n\n` +
            `— ThaiData UK`,
        }],
      }),
    });

    if (!res.ok) {
      console.error(`MailChannels error: ${res.status} — ${await res.text()}`);
    } else {
      console.log(`Notification sent to ${adminEmail} for claim #${claim.id}`);
    }
  } catch (err) {
    console.error('Notification send failed:', err.message);
  }
}

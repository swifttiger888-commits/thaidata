// ThaiData UK — /api/admin
// Admin panel: review claims, approve/reject, manage listings

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
      const existing = await env.DB.prepare(
        'SELECT id FROM listings WHERE restaurant_name = ? AND city = ?'
      ).bind(claim.restaurant_name, claim.city).first();

      if (existing) {
        // Update existing listing owner
        await env.DB.prepare(
          'UPDATE listings SET claim_id = ?, updated_at = datetime(\'now\') WHERE id = ?'
        ).bind(claim_id, existing.id).run();
      } else {
        // Create new listing
        await env.DB.prepare(
          `INSERT INTO listings (claim_id, restaurant_name, city, fsa_id, claimed_at)
           VALUES (?, ?, ?, ?, datetime('now'))`
        ).bind(claim_id, claim.restaurant_name, claim.city, claim.fsa_id).run();
      }

      // Update claim status
      await env.DB.prepare(
        "UPDATE claims SET claim_status = 'approved', reviewed_at = datetime('now'), admin_notes = ? WHERE id = ?"
      ).bind(admin_notes || null, claim_id).run();

      return new Response(JSON.stringify({
        success: true,
        message: 'Claim approved. Listing created.',
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

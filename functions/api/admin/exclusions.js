// ThaiData UK — /api/admin/exclusions
// Admin-only: exclude or restore a restaurant by FSA ID

/**
 * Shared session auth check for admin endpoints
 */
async function requireSession(request, env) {
  const auth = request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Bearer ')) return null;

  const token = auth.slice(7);
  const session = await env.DB.prepare(
    "SELECT id FROM admin_sessions WHERE token = ? AND expires_at > datetime('now')"
  ).bind(token).first();

  return session || null;
}

/**
 * Handles POST /api/admin/exclusions — exclude an FSA ID
 * Body: { fsa_id: number, reason: string }
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const session = await requireSession(request, env);
    if (!session) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: corsHeaders,
      });
    }

    const body = await request.json();
    const { fsa_id, reason } = body;

    if (!fsa_id || !reason) {
      return new Response(JSON.stringify({ error: 'fsa_id and reason required' }), {
        status: 400, headers: corsHeaders,
      });
    }

    // Upsert: if a restored row exists, re-activate it; otherwise insert
    const existing = await env.DB.prepare(
      'SELECT fsa_id, restored_at FROM exclusions WHERE fsa_id = ?'
    ).bind(fsa_id).first();

    if (existing) {
      if (existing.restored_at === null) {
        return new Response(JSON.stringify({ error: 'Already excluded' }), {
          status: 409, headers: corsHeaders,
        });
      }
      // Re-activate a previously restored exclusion
      await env.DB.prepare(
        `UPDATE exclusions SET
          reason = ?,
          excluded_by = 'admin',
          excluded_at = datetime('now'),
          restored_by = NULL,
          restored_at = NULL
        WHERE fsa_id = ?`
      ).bind(reason, fsa_id).run();
    } else {
      await env.DB.prepare(
        `INSERT INTO exclusions (fsa_id, reason, excluded_by, excluded_at)
         VALUES (?, ?, 'admin', datetime('now'))`
      ).bind(fsa_id, reason).run();
    }

    return new Response(JSON.stringify({
      success: true,
      message: `FSA ID ${fsa_id} excluded.`,
    }), { status: 200, headers: corsHeaders });

  } catch (err) {
    console.error('Exclusion create error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

/**
 * Handles PATCH /api/admin/exclusions — restore (un-exclude) an FSA ID
 * Body: { fsa_id: number }
 * Sets restored_by / restored_at instead of deleting the row.
 */
export async function onRequestPatch(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const session = await requireSession(request, env);
    if (!session) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: corsHeaders,
      });
    }

    const body = await request.json();
    const { fsa_id } = body;

    if (!fsa_id) {
      return new Response(JSON.stringify({ error: 'fsa_id required' }), {
        status: 400, headers: corsHeaders,
      });
    }

    const existing = await env.DB.prepare(
      'SELECT fsa_id, restored_at FROM exclusions WHERE fsa_id = ?'
    ).bind(fsa_id).first();

    if (!existing) {
      return new Response(JSON.stringify({ error: 'Exclusion not found' }), {
        status: 404, headers: corsHeaders,
      });
    }

    if (existing.restored_at !== null) {
      return new Response(JSON.stringify({ error: 'Already restored' }), {
        status: 409, headers: corsHeaders,
      });
    }

    await env.DB.prepare(
      `UPDATE exclusions SET
        restored_by = 'admin',
        restored_at = datetime('now')
      WHERE fsa_id = ?`
    ).bind(fsa_id).run();

    return new Response(JSON.stringify({
      success: true,
      message: `FSA ID ${fsa_id} restored.`,
    }), { status: 200, headers: corsHeaders });

  } catch (err) {
    console.error('Exclusion restore error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

/**
 * Handles GET /api/admin/exclusions — list all exclusions (for admin UI)
 */
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const session = await requireSession(request, env);
    if (!session) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: corsHeaders,
      });
    }

    const results = await env.DB.prepare(
      'SELECT * FROM exclusions ORDER BY excluded_at DESC LIMIT 100'
    ).all();

    return new Response(JSON.stringify({ exclusions: results.results }), {
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    console.error('Exclusions list error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

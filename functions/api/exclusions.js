// ThaiData UK — /api/exclusions
// Public endpoint: returns active exclusion FSA IDs for pipeline consumption

/**
 * Handles GET /api/exclusions — returns active exclusion IDs
 * Public, no auth required. Returns only fsa_id for excluded records
 * where restored_at IS NULL (active exclusions only).
 */
export async function onRequestGet(context) {
  const { env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const results = await env.DB.prepare(
      'SELECT fsa_id FROM exclusions WHERE restored_at IS NULL'
    ).all();

    const excludedIds = results.results.map(r => r.fsa_id);

    return new Response(JSON.stringify({ excluded_ids: excludedIds }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Exclusions list error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// ThaiData UK — GET /api/claimed
// Returns a flat list of all approved claimed restaurant names + cities
// Used by city pages to show "Claimed" badges on restaurant listings
// Cache: 5 minutes (claims don't change often)
/**
 * Handles GET /api/claimed — returns all approved claimed restaurants (name + city)
 * Used by city pages to show "Claimed" badges on restaurant listings
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with optional ?city filter
 * @param {object} context.env - Environment bindings with DB (D1Database)
 * @returns {Promise<Response>} JSON response with claimed restaurants list or error
 * @throws {Error} When database query fails (caught internally)
 */
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
    'Cache-Control': 'public, max-age=300',
  };

  try {
    const url = new URL(request.url);
    const cityFilter = url.searchParams.get('city');

    let query = "SELECT l.restaurant_name, l.city FROM listings l JOIN claims c ON c.id = l.claim_id WHERE c.claim_status = 'approved'";
    const params = [];

    if (cityFilter) {
      query += ' AND l.city = ?';
      params.push(cityFilter);
    }

    query += ' ORDER BY l.restaurant_name';

    const results = await env.DB.prepare(query).bind(...params).all();

    const claimed = results.results.map(r => ({
      name: r.restaurant_name,
      city: r.city,
    }));

    return new Response(JSON.stringify({
      count: claimed.length,
      claimed: claimed,
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Claimed list error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error', claimed: [], count: 0 }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

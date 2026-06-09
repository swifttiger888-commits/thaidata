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
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
    'Cache-Control': 'public, max-age=300',
  };
  // Claim system is archived — no active claims to surface.
  return new Response(JSON.stringify({
    count: 0,
    claimed: [],
  }), { status: 200, headers: corsHeaders });
}

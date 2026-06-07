// ThaiData UK — API Middleware
// Handles CORS, OPTIONS preflight, and shared utilities

/**
 * API middleware — handles CORS headers, OPTIONS preflight, and passes through to next handler
 * @param {object} context - Cloudflare Workers Pages function context
 * @param {Request} context.request - Incoming HTTP request
 * @param {Function} context.next - Callback to invoke the next handler in the chain
 * @returns {Promise<Response>} HTTP response with CORS headers set
 */
export async function onRequest(context) {
  const { request, next } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': 'https://thaidata.uk',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  const response = await next();
  const newHeaders = new Headers(response.headers);
  Object.entries(corsHeaders).forEach(([k, v]) => newHeaders.set(k, v));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

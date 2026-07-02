// ThaiData UK — API Middleware
// Handles CORS, OPTIONS preflight, and shared utilities
// Injects Microsoft Clarity tracking into all HTML pages

const CLARITY_SNIPPET = `<!-- Microsoft Clarity -->
<script>
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i+"?ref=bwt";
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "xg39360lal");
    // Default consent: denied until user accepts via cookie banner
    // Updated to granted when user clicks "Accept All" in privacy-banner.js
    if (window.clarity) clarity("consent", localStorage.getItem("thaidata_consent") === "granted");
</script>`;

/**
 * Injects Clarity snippet into HTML responses right before </head>
 * @param {Response} response - The original response
 * @returns {Promise<Response>} Modified response with Clarity injected
 */
async function injectClarity(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('text/html')) return response;

  try {
    const text = await response.clone().text();
    const modified = text.replace('</head>', CLARITY_SNIPPET + '\n</head>');
    const newHeaders = new Headers(response.headers);
    return new Response(modified, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  } catch {
    // If body can't be read (stream issues etc.), return the original
    return response;
  }
}

/**
 * API middleware — handles CORS headers, OPTIONS preflight, injects Clarity
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
  const enriched = await injectClarity(response);
  const newHeaders = new Headers(enriched.headers);
  Object.entries(corsHeaders).forEach(([k, v]) => newHeaders.set(k, v));
  return new Response(enriched.body, {
    status: enriched.status,
    statusText: enriched.statusText,
    headers: newHeaders,
  });
}

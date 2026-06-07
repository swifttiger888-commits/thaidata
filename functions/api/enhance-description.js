// ThaiData UK — /api/enhance-description
// AI-powered description enhancer for listing owners
// Uses Workers AI to rewrite website copy into a short listing summary
// Grounded in trusted DB fields — user copy is optional secondary context
// One-shot, human-review only, no auto-publish

/**
 * Simple in-memory IP rate limiter (per-worker instance)
 * @type {Map<string, number>}
 */
const ipRateMap = new Map();

/**
 * Checks if an IP has exceeded the rate limit (1 req per 10 seconds)
 * @param {string} ip - Client IP address
 * @returns {boolean} True if rate limited
 */
function isRateLimited(ip) {
  const now = Date.now();
  const last = ipRateMap.get(ip);
  if (last && (now - last) < 10_000) return true;
  ipRateMap.set(ip, now);
  return false;
}

/**
 * Sanitize user text: strip control chars and prompt-injection patterns
 * @param {string} text
 * @returns {string}
 */
function sanitizeInput(text) {
  if (!text) return '';
  let s = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

/**
 * Validate AI output: ensure it's reasonable length and doesn't contain
 * injected content like URLs, markdown, or obviously nonsensical text.
 * @param {string} text
 * @returns {{ valid: boolean, reason?: string }}
 */
function validateOutput(text) {
  if (!text || text.length < 10) {
    return { valid: false, reason: 'too_short' };
  }
  if (text.length > 500) {
    return { valid: false, reason: 'too_long' };
  }
  const injectionPatterns = [
    /ignore\s+(your\s+)?(previous|above|all|system)/i,
    /you\s+are\s+(an?\s+)?(AI|assistant|model|language\s+model)/i,
    /as\s+an?\s+(AI|assistant)/i,
    /system\s*(prompt|instruction|message)/i,
    /###\s*(system|user|assistant)/i,
  ];
  for (const pattern of injectionPatterns) {
    if (pattern.test(text)) {
      return { valid: false, reason: 'injection_detected' };
    }
  }
  if (/https?:\/\/[^\s]+/.test(text)) {
    return { valid: false, reason: 'contains_url' };
  }
  return { valid: true };
}

/**
 * SHA-256 hash for token comparison
 * @param {string} text
 * @returns {Promise<string>}
 */
async function sha256(text) {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Build the AI messages with grounded listing data + optional user copy.
 * Trusted DB fields are the primary source of truth; user copy is
 * secondary and may not override stored facts.
 * @param {object} listing - Listing record from the DB
 * @param {string} sourceText - Optional user-pasted text
 * @returns {Array} Messages array for Workers AI
 */
function buildMessages(listing, sourceText) {
  // Extract trusted DB fields
  const name = listing.restaurant_name || '';
  const city = listing.city || '';
  const cuisine = listing.cuisine_specialty || '';

  let features = [];
  if (listing.features) {
    try { features = JSON.parse(listing.features); } catch { features = []; }
  }

  const priceRange = listing.price_range || '';

  // Build TRUSTED LISTING DATA block — only include non-empty fields.
  // Current description is deliberately excluded — we're rewriting, not preserving.
  const trustedLines = [];
  if (name) trustedLines.push(`Restaurant: ${sanitizeInput(name)}`);
  if (city) trustedLines.push(`City: ${sanitizeInput(city)}`);
  if (cuisine) trustedLines.push(`Cuisine: ${sanitizeInput(cuisine)}`);
  if (features.length > 0) trustedLines.push(`Features: ${sanitizeInput(features.join(', '))}`);
  if (priceRange) trustedLines.push(`Price range: ${sanitizeInput(priceRange)}`);

  const trustedData = trustedLines.length > 0
    ? trustedLines.join('\n')
    : '(no listing data available)';

  const system = `You are a restaurant listing editor for ThaiData UK, a Thai restaurant directory.
Write a short, factual description for diners.

RULES — follow every rule strictly:
- TRUSTED LISTING DATA is the source of truth. If it conflicts with USER COPY, ignore the USER COPY and follow the trusted data.
- Use ONLY facts from TRUSTED LISTING DATA and USER COPY. Invent NOTHING.
- CRITICAL: Actively rewrite the USER COPY. Do NOT simply copy or lightly rephrase it. Produce something shorter, tighter, and diner-focused.
- Remove all of these from the output: restaurant name, city, address, postcode, hygiene scores, phone numbers, URLs. They are shown elsewhere on the listing page, not in the description.
- Do NOT add dish names, prices, opening hours, awards, ratings, or years-in-business unless explicitly present in TRUSTED LISTING DATA or USER COPY.
- Do NOT use generic fillers like: "warm hospitality", "authentic flavours", "gem", "must-visit", "hidden treasure", "culinary journey", "taste of Thailand".
- No exclamation marks or emojis.
- HARD LIMIT: Maximum 300 characters. Count your output. If it exceeds 300, shorten it.
- Third person, plain English, one or two sentences.
- Return ONLY the generated description text — no preamble, no labels, no quotes.
- If there is less than 50 characters total across TRUSTED LISTING DATA + USER COPY, return exactly: "NEEDS_MORE_TEXT"`;

  const user = `--- TRUSTED LISTING DATA (ground truth) ---
${trustedData}

--- USER COPY (optional — wording reference only) ---
--- BEGIN SOURCE ---
${sanitizeInput(sourceText || '')}
--- END SOURCE ---

Generate the short description now following all rules above. The output must not start with the restaurant name, city, or address — begin with the cuisine or what the restaurant offers.`;

  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ];
}

/**
 * Handles POST /api/enhance-description
 * Expects: { source_text?: string, restaurant_name?: string }
 * Auth: Bearer token (same as listing manage page) — validated against DB
 */
export async function onRequestPost(context) {
  const { request, env } = context;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  // --- Auth: validate Bearer token and resolve listing ---
  const auth = request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Bearer ')) {
    return new Response(JSON.stringify({ success: false, error: 'unauthorized' }), {
      status: 401,
      headers: corsHeaders,
    });
  }

  let listing;
  try {
    const rawToken = auth.slice(7);
    const tokenHash = await sha256(rawToken);
    const tokenRecord = await env.DB.prepare(
      "SELECT listing_id FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
    ).bind(tokenHash).first();

    if (!tokenRecord) {
      return new Response(JSON.stringify({ success: false, error: 'unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    listing = await env.DB.prepare('SELECT * FROM listings WHERE id = ?').bind(tokenRecord.listing_id).first();

    if (!listing) {
      return new Response(JSON.stringify({ success: false, error: 'unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }
  } catch (dbErr) {
    console.error('Auth DB error:', dbErr.message);
    return new Response(JSON.stringify({ success: false, error: 'server_error', message: 'Authentication failed.' }), {
      status: 500,
      headers: corsHeaders,
    });
  }

  // --- Rate limit ---
  const cfIp = request.headers.get('CF-Connecting-IP') || 'unknown';
  if (isRateLimited(cfIp)) {
    return new Response(JSON.stringify({
      success: false,
      error: 'rate_limited',
      message: 'Please wait a few seconds before trying again.',
    }), {
      status: 429,
      headers: corsHeaders,
    });
  }

  // --- Parse & validate body ---
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: corsHeaders,
    });
  }

  const rawSource = body.source_text || '';
  const sourceText = sanitizeInput(rawSource);

  if (sourceText.length > 2000) {
    return new Response(JSON.stringify({
      success: false,
      error: 'text_too_long',
      message: 'Source text is too long. Maximum 2000 characters.',
    }), {
      status: 200,
      headers: corsHeaders,
    });
  }

  // --- Build grounded messages ---
  const messages = buildMessages(listing, sourceText);

  // --- Call Workers AI ---
  try {
    const aiResponse = await env.AI.run('@cf/meta/llama-3.2-3b-instruct', {
      messages,
      max_tokens: 350,
      temperature: 0.3,
    });

    let rawOutput = (aiResponse.response || '').trim();

    // Handle NEEDS_MORE_TEXT signal from model
    if (rawOutput === 'NEEDS_MORE_TEXT') {
      return new Response(JSON.stringify({
        success: false,
        error: 'needs_more_text',
        message: 'Add more detail about the restaurant, then try again.',
      }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Validate output
    const validation = validateOutput(rawOutput);
    if (!validation.valid) {
      console.error(`AI output validation failed: ${validation.reason}`, rawOutput);
      return new Response(JSON.stringify({
        success: false,
        error: 'generation_error',
        message: 'The generated description didn\'t meet quality checks. Try rewording your source text.',
      }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Trim to 300 chars hard cap
    const description = rawOutput.substring(0, 300);

    return new Response(JSON.stringify({
      success: true,
      description,
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('AI enhance error:', err.message);
    return new Response(JSON.stringify({
      success: false,
      error: 'server_error',
      message: 'AI service temporarily unavailable. Try again shortly.',
    }), {
      status: 200,
      headers: corsHeaders,
    });
  }
}

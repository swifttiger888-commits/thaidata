// ThaiData UK — /api/enhance-description
// AI-powered description enhancer for listing owners
// Uses Workers AI to condense website copy into a short listing summary
// One-shot, human-review only, no auto-publish

/**
 * Simple in-memory IP rate limiter (per-worker instance)
 * Tracks request timestamps per IP, rejects if <10s since last request.
 * Cloudflare Workers are per-isolate — this is approximate but good enough.
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
 * before it enters the AI prompt boundary.
 * @param {string} text
 * @returns {string}
 */
function sanitizeInput(text) {
  if (!text) return '';
  // Strip null bytes and control characters (except newlines and tabs)
  let s = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  // Collapse multiple whitespace
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
  // Reject if output appears to contain injection artifacts
  // (e.g. the model leaked instructions or system prompt content)
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
  // Reject if it contains raw URLs (owners shouldn't want links in descriptions)
  if (/https?:\/\/[^\s]+/.test(text)) {
    return { valid: false, reason: 'contains_url' };
  }
  return { valid: true };
}

/**
 * Build the system prompt with strict instructions and clear user-data boundaries.
 * The source text is treated as untrusted data — delimited explicitly.
 * @param {string} restaurantName
 * @param {string} sourceText
 * @returns {Array} Messages array for Workers AI
 */
function buildMessages(restaurantName, sourceText) {
  const system = `You are a restaurant listing editor for ThaiData UK, a Thai restaurant directory.
Your only job: condense the source text below into a short description.

RULES — follow every rule strictly:
- Use ONLY facts from the source text. Invent NOTHING.
- Do NOT add dish names, prices, hours, awards, ratings, or history unless explicitly in the source.
- Do NOT use any of these phrases: "warm hospitality", "authentic flavours", "gem", "must-visit", "hidden treasure", "culinary journey", "taste of Thailand", "family-run", "attention to detail".
- No exclamation marks or emojis.
- Maximum 300 characters.
- Third person, plain English, one or two sentences.
- Return ONLY the generated description text — no preamble, no labels, no quotes.
- If the source text below is empty, under 50 characters, or has no usable content, return exactly: "NEEDS_MORE_TEXT"`;

  const user = `--- BEGIN SOURCE ---
Restaurant: ${restaurantName}
Description source: ${sourceText}
--- END SOURCE ---

Generate the short description now following all rules above.`;

  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ];
}

/**
 * Handles POST /api/enhance-description
 * Expects: { source_text: string, restaurant_name?: string }
 * Auth: Bearer token (same as listing manage page)
 */
export async function onRequestPost(context) {
  const { request, env } = context;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  // --- Auth ---
  const auth = request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Bearer ')) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 403,
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
  const restaurantName = sanitizeInput(body.restaurant_name || '');

  // Sanitize input (strip injection vectors, control chars)
  const sourceText = sanitizeInput(rawSource);

  if (!sourceText || sourceText.length < 50) {
    return new Response(JSON.stringify({
      success: false,
      error: 'needs_more_text',
      message: 'Please provide at least 50 characters of website copy or description text.',
    }), {
      status: 200,
      headers: corsHeaders,
    });
  }

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

  // --- Build messages ---
  const messages = buildMessages(restaurantName, sourceText);

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
        message: 'The source text is too short or lacks usable content. Add more detail about the restaurant.',
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

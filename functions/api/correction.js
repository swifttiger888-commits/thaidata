// ThaiData UK — POST /api/correction
// Owner-help "report an error" flow: validate, throttle, store in D1, notify admin.

import { sendCorrectionNotification, sendCorrectionAck } from './_email.js';

const ALLOWED_CATEGORIES = ['hours', 'address', 'contact', 'closed', 'menu', 'other', 'general'];
const MAX_PER_HOUR = 5;
const MIN_DETAILS = 10;
const MAX_DETAILS = 2000;
const MAX_NAME = 200;
const MAX_CITY = 100;
const MAX_EMAIL = 254;
const MAX_PAGE_URL = 300;

/**
 * Handles POST /api/correction — records a correction report for a listing.
 * Body: {restaurant_name, city, fsa_id?, category, details, reporter_email?, page_url?, website (honeypot)}
 *       restaurant_name/city are optional when category is 'general' (contact page).
 * @param {object} context - Cloudflare Workers function context
 * @param {Request} context.request - Incoming HTTP request with JSON body
 * @param {object} context.env - Environment bindings (DB: D1Database, RESEND_API_KEY, ADMIN_EMAIL, TELEGRAM_*)
 * @returns {Promise<Response>} 201 success; 400 invalid; 429 throttled; 200 silent drop on honeypot
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== 'object') {
      return jsonResponse({ error: 'Invalid request body' }, 400, corsHeaders);
    }

    // Honeypot: real users never fill a field called "website". Pretend success, store nothing.
    if (String(body.website || '').trim()) {
      console.log('Correction report: honeypot triggered — discarded');
      return jsonResponse({ success: true }, 200, corsHeaders);
    }

    const category = String(body.category || '').trim();
    let restaurant_name = String(body.restaurant_name || '').trim().slice(0, MAX_NAME);
    let city = String(body.city || '').trim().slice(0, MAX_CITY);
    // General enquiries from /contact carry no restaurant context. Fill sentinels so the
    // NOT NULL columns stay meaningful and 'general' rows stay separable in queries.
    if (category === 'general') {
      if (!restaurant_name) restaurant_name = 'General enquiry';
      if (!city) city = 'n/a';
    }
    const fsa_id = body.fsa_id != null && String(body.fsa_id).trim() ? String(body.fsa_id).trim().slice(0, 20) : null;
    const details = String(body.details || '').trim().slice(0, MAX_DETAILS);
    const reporter_email = String(body.reporter_email || '').trim().slice(0, MAX_EMAIL) || null;
    const page_url = String(body.page_url || '').trim().slice(0, MAX_PAGE_URL) || null;

    if (!restaurant_name || !city || !ALLOWED_CATEGORIES.includes(category)) {
      return jsonResponse({ error: 'Missing or invalid fields' }, 400, corsHeaders);
    }
    if (details.length < MIN_DETAILS) {
      return jsonResponse({ error: 'Please provide a little more detail (at least 10 characters).' }, 400, corsHeaders);
    }
    if (reporter_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(reporter_email)) {
      return jsonResponse({ error: 'Invalid email address' }, 400, corsHeaders);
    }

    // Ensure tables exist (runtime-create pattern, same as email_log / login_attempts)
    await env.DB.prepare(
      `CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fsa_id TEXT,
        restaurant_name TEXT NOT NULL,
        city TEXT NOT NULL,
        category TEXT NOT NULL,
        details TEXT NOT NULL,
        reporter_email TEXT,
        page_url TEXT,
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      )`
    ).run();
    await env.DB.prepare(
      `CREATE TABLE IF NOT EXISTS correction_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
      )`
    ).run();
    await env.DB.prepare(
      'CREATE INDEX IF NOT EXISTS idx_corrections_created ON corrections(created_at)'
    ).run();
    // Retention: messages/reports are deleted after 12 months (matches privacy.html).
    await env.DB.prepare(
      "DELETE FROM corrections WHERE created_at < datetime('now', '-12 months')"
    ).run();

    // Spam throttle: 5 accepted submissions per hour per IP
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    await env.DB.prepare(
      "DELETE FROM correction_attempts WHERE attempted_at < datetime('now', '-1 hour')"
    ).run();
    const recent = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM correction_attempts WHERE ip = ? AND attempted_at > datetime('now', '-1 hour')"
    ).bind(ip).first();
    if (recent && recent.count >= MAX_PER_HOUR) {
      return jsonResponse({ error: 'Too many reports — please try again later.' }, 429, corsHeaders);
    }
    await env.DB.prepare('INSERT INTO correction_attempts (ip) VALUES (?)').bind(ip).run();

    const result = await env.DB.prepare(
      `INSERT INTO corrections (fsa_id, restaurant_name, city, category, details, reporter_email, page_url)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    ).bind(fsa_id, restaurant_name, city, category, details, reporter_email, page_url).run();

    const id = result.meta.last_row_id;

    // Notifications are best-effort — never block or fail the response (claim.js pattern)
    await Promise.allSettled([
      notifyTelegram(env, { id, restaurant_name, city, category, details, reporter_email, page_url }),
      sendCorrectionNotification(env, { id, restaurant_name, city, category, details, reporter_email, page_url }),
      reporter_email ? sendCorrectionAck(env, { to: reporter_email, restaurant_name, city, category }) : Promise.resolve(null),
    ]);

    return jsonResponse({ success: true, id }, 201, corsHeaders);
  } catch (err) {
    console.error('Correction submission error:', err);
    return jsonResponse({ error: 'Internal server error' }, 500, corsHeaders);
  }
}

function jsonResponse(payload, status, headers) {
  return new Response(JSON.stringify(payload), { status, headers });
}

/**
 * Telegram ping for a new correction report. Plain text on purpose — the details are
 * free text, so Markdown parsing would be at the mercy of whatever the reporter typed.
 */
async function notifyTelegram(env, report) {
  const botToken = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!botToken || !chatId) {
    console.log('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — skipping notification');
    return;
  }

  const snippet = report.details.length > 300 ? report.details.slice(0, 300) + '…' : report.details;
  const reporterLine = report.reporter_email ? `\nReply-to: ${report.reporter_email}` : '';
  const pageLine = (report.page_url && report.page_url.startsWith('/')) ? `\nhttps://thaidata.uk${report.page_url}` : '';
  const header = report.category === 'general'
    ? `✍️ General enquiry #${report.id}`
    : `🛠 Correction report #${report.id}\n\n${report.restaurant_name} — ${report.city}\nType: ${report.category}`;
  const text = `${header}\n\n${snippet}${reporterLine}${pageLine}`;

  try {
    const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, disable_web_page_preview: true }),
    });
    if (!res.ok) {
      console.error(`Telegram API error: ${res.status} — ${await res.text()}`);
    }
  } catch (err) {
    console.error('Telegram notification failed:', err.message);
  }
}

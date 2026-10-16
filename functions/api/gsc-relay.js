// ThaiData UK — GSC reconnect relay
// GET  /api/gsc-relay  -> tiny form for pasting the localhost callback URL
// POST /api/gsc-relay  -> stores the OAuth code against a pre-created pending state row
//
// Security: only accepts a code when `state` matches a pending row (code IS NULL,
// created within the last 60 minutes). The row is consumed once. No other data read.
// Hermes-side ops: create pending row before handing out the consent URL; read the
// code, exchange it serve-side, then DELETE the row.

const PAGE_HEAD = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Search Console reconnect</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:48px auto;padding:0 20px;color:#2B2B2B;line-height:1.55}
h1{font-size:1.35rem;margin:0 0 12px}
ol{padding-left:1.2em}li{margin:6px 0}
input[type=url],input[type=text],textarea{width:100%;box-sizing:border-box;padding:12px;font:inherit;border:1px solid #CFC7C0;border-radius:10px;margin:10px 0}
button{background:#A3132B;color:#fff;border:0;border-radius:10px;padding:12px 22px;font:inherit;font-weight:600;cursor:pointer}
.note{color:#6B605B;font-size:.92em}
.ok{background:#F2FBF3;border:1px solid #BCE3C2;border-radius:10px;padding:14px 16px}
.bad{background:#FDF3F3;border:1px solid #E9BFBF;border-radius:10px;padding:14px 16px}
</style></head><body>`;

function html(body, status = 200) {
  return new Response(PAGE_HEAD + body + `</body></html>`, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'X-Robots-Tag': 'noindex' },
  });
}

export async function onRequestGet() {
  return html(`
    <h1>Search Console reconnect</h1>
    <ol>
      <li>Open the Google link Hermes sent you and approve access.</li>
      <li>Your browser will land on a page saying <em>&ldquo;This site can&rsquo;t be reached&rdquo;</em> or a similar error. That is expected.</li>
      <li>Copy the <strong>entire address</strong> from the address bar of that error page.</li>
      <li>Paste it below and press <strong>Send</strong>.</li>
    </ol>
    <form method="POST">
      <input type="text" name="u" placeholder="http://localhost:9876/callback?code=…&amp;state=…" required autocomplete="off" spellcheck="false" data-clarity-mask="true">
      <button type="submit">Send</button>
    </form>
    <p class="note">This page only accepts a callback link for a reconnect Hermes has already started, within 60 minutes. Nothing else is stored.</p>`);
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let pasted = '';
  try {
    const form = await request.formData();
    pasted = String(form.get('u') || '').trim();
  } catch {
    return html(`<div class="bad"><h1>Couldn&rsquo;t read that</h1><p>Ask Hermes for a fresh link.</p></div>`, 400);
  }

  // extract code + state from the pasted URL (accepts full URL or query string)
  let code = null, state = null;
  try {
    const qs = pasted.includes('?') ? pasted.slice(pasted.indexOf('?') + 1) : pasted;
    const params = new URLSearchParams(qs);
    code = params.get('code');
    state = params.get('state');
  } catch { /* fallthrough */ }

  if (!code || !state || !/^[a-f0-9]{32}$/.test(state)) {
    return html(`<div class="bad"><h1>That doesn&rsquo;t look right</h1><p>Make sure you copied the <strong>whole</strong> address from the error page &mdash; then ask Hermes if it still fails.</p></div>`, 400);
  }

  const row = await env.DB.prepare(
    `SELECT id FROM gsc_relay WHERE state = ? AND code IS NULL AND consumed = 0 AND created_at >= datetime('now', '-60 minutes')`
  ).bind(state).first();

  if (!row) {
    return html(`<div class="bad"><h1>No matching request</h1><p>This link doesn&rsquo;t match an active reconnect (or it already went through). Ask Hermes to start a fresh one.</p></div>`, 400);
  }

  await env.DB.prepare(`UPDATE gsc_relay SET code = ?, consumed = 1 WHERE id = ?`).bind(code, row.id).run();

  return html(`<div class="ok"><h1>Got it &mdash; done </h1><p>You can close this tab and tell Hermes. It will finish the rest.</p></div>`);
}

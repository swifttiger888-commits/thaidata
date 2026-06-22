export async function onRequest(context) {
  const { env, request } = context;
  const url = new URL(request.url);
  if (url.searchParams.get('token') !== env.ADMIN_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 403, headers: { 'Content-Type': 'application/json' } });
  }

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: 'ThaiData Test <hello@thaidata.uk>',
      to: ['hello@thaidata.uk'],
      subject: 'Test — hello@ forwarding to Gmail',
      html: '<p style="font-size:15px;line-height:1.6;">This is a test to confirm hello@thaidata.uk forwards to your Gmail inbox. If you received this, Cloudflare Email Routing is working. Sent at <strong>' + new Date().toLocaleString() + '</strong></p>'
    })
  });

  return new Response(JSON.stringify({ status: res.status, ok: res.ok }), {
    status: 200, headers: { 'Content-Type': 'application/json' }
  });
}

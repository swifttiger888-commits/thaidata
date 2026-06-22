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
      subject: 'TEST — hello@thaidata.uk forwarding check',
      html: '<p style="font-size:15px;line-height:1.6;">If you can read this, hello@thaidata.uk forwards correctly to Gmail. Resend → Cloudflare Email Routing → your inbox. Sent at <strong>' + new Date().toLocaleString() + '</strong></p>'
    })
  });

  return new Response(JSON.stringify({ status: res.status, ok: res.ok }), {
    status: 200, headers: { 'Content-Type': 'application/json' }
  });
}

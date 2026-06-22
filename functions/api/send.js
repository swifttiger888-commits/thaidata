// One-shot test email sender for outreach drafts
// Hit once, then delete from repo
import { sha256 } from './_email.js';

export async function onRequest(context) {
  const { request, env } = context;
  
  // Auth
  const url = new URL(request.url);
  if (url.searchParams.get('token') !== env.ADMIN_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 403,
      headers: { 'Content-Type': 'application/json' } });
  }

  const emails = [
    {
      to: 'info@zaapthai.co.uk',
      subject: 'Zaap Thai on ThaiData — claim your listings across all 7 branches',
      html: `<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Hi,</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Zaap Thai is already on ThaiData across Leeds, Manchester, York, Sheffield, Durham, Newcastle and Nottingham — all pulled from the Food Standards Agency public register.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Claiming your listings takes a few minutes per branch: <a href="https://thaidata.uk/claim/" style="color:#10B981;">thaidata.uk/claim/</a></p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Once claimed, you can add photos, opening hours, menus and your website to every location. Most chain profiles sit empty — claim yours and stand out.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 24px;">No contract, no cost, no catch.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 4px;">Jonathan</p>
<p style="font-size:13px;color:#9CA3AF;margin:0;">ThaiData UK · thaidata.uk</p>`
    },
    {
      to: 'contact@fanthaisticks.co.uk',
      subject: 'Fan Thai Sticks — free listing on ThaiData UK',
      html: `<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Hi,</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">I found Fan Thai Sticks on the festival circuit — most directories only list restaurants, so street food operators like yours don't get found between events.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">I run ThaiData UK (<a href="https://thaidata.uk" style="color:#10B981;">thaidata.uk</a>). I'd like to add you — completely free, no forms, no sign-up.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 12px;">All I need:</p>
<ul style="padding-left:20px;margin:0 0 16px;">
  <li style="font-size:15px;margin-bottom:6px;">Your trading name</li>
  <li style="font-size:15px;">Any Instagram, Facebook page or website you'd like linked</li>
</ul>
<p style="font-size:15px;line-height:1.6;margin:0 0 24px;">Reply with whatever you have — even just a social link is enough.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 4px;">Jonathan</p>
<p style="font-size:13px;color:#9CA3AF;margin:0;">ThaiData UK · thaidata.uk</p>`
    },
    {
      to: 'Thipsthaistreetfood@gmail.com',
      subject: 'Thips Thai — free listing on ThaiData UK',
      html: `<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Hi,</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">I found Thips Thai Street Food at Victory Field, Sunninghill — your market stall setup looks great.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">I run ThaiData UK (<a href="https://thaidata.uk" style="color:#10B981;">thaidata.uk</a>), a free directory of Thai food across the UK. Most directories ignore market traders and mobile operators, so I'm reaching out directly to make sure you're included.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 12px;">Getting listed takes one reply from you:</p>
<ul style="padding-left:20px;margin:0 0 16px;">
  <li style="font-size:15px;margin-bottom:6px;">Your trading name</li>
  <li style="font-size:15px;">Any Instagram, Facebook or website link</li>
</ul>
<p style="font-size:15px;line-height:1.6;margin:0 0 24px;">That's it. No forms, no cost.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 4px;">Jonathan</p>
<p style="font-size:13px;color:#9CA3AF;margin:0;">ThaiData UK · thaidata.uk</p>`
    }
  ];

  const results = [];
  for (const email of emails) {
    try {
      const r = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: 'Jonathan at ThaiData <hello@thaidata.uk>', to: [email.to], subject: email.subject, html: email.html })
      });
      const body = await r.json();
      results.push({ to: email.to, status: r.status, id: body.id || 'error', error: body.message });
    } catch(e) { results.push({ to: email.to, error: e.message }); }
  }
  return new Response(JSON.stringify({ sent: results.length, results }), {
    status: 200, headers: { 'Content-Type': 'application/json' }
  });
}

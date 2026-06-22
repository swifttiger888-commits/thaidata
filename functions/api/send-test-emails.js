export async function onRequest(context) {
  const { env, request } = context;
  
  // Auth check — only allow from admin token
  const url = new URL(request.url);
  if (url.searchParams.get('token') !== env.ADMIN_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 403,
      headers: { 'Content-Type': 'application/json' } });
  }
  
  if (!env.RESEND_API_KEY) {
    return new Response(JSON.stringify({ error: 'RESEND_API_KEY not configured' }), { 
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const testEmails = [
    {
      to: 'swifttiger888@gmail.com',
      subject: 'Zaap Thai on ThaiData — claim your listings across all 7 branches',
      html: `<p>Hi,</p>
<p>Zaap Thai is already on ThaiData across Leeds, Manchester, York, Sheffield, Durham, Newcastle and Nottingham — all pulled from the Food Standards Agency public register.</p>
<p>Claiming your listings takes a few minutes per branch:<br><a href="https://thaidata.uk/claim/">thaidata.uk/claim/</a></p>
<p>Once claimed, you can add photos, opening hours, menus and your website to every location. Most chain profiles sit empty — claim yours and stand out.</p>
<p>No contract, no cost, no catch.</p>
<p>Jonathan<br>ThaiData UK · thaidata.uk</p>`
    },
    {
      to: 'swifttiger888@gmail.com',
      subject: 'Fan Thai Sticks — free listing on ThaiData UK',
      html: `<p>Hi,</p>
<p>I found Fan Thai Sticks on the festival circuit — most directories only list restaurants, so street food operators like yours don't get found between events.</p>
<p>I run ThaiData UK (<a href="https://thaidata.uk">thaidata.uk</a>). I'd like to add you — completely free, no forms, no sign-up.</p>
<p>All I need:</p>
<ul>
  <li>Your trading name</li>
  <li>Any Instagram, Facebook page or website you'd like linked</li>
</ul>
<p>Reply with whatever you have — even just a social link is enough.</p>
<p>Jonathan<br>ThaiData UK · thaidata.uk</p>`
    },
    {
      to: 'swifttiger888@gmail.com',
      subject: 'Thips Thai — free listing on ThaiData UK',
      html: `<p>Hi,</p>
<p>I found Thips Thai Street Food at Victory Field, Sunninghill — your market stall setup looks great.</p>
<p>I run ThaiData UK (<a href="https://thaidata.uk">thaidata.uk</a>), a free directory of Thai food across the UK. Most directories ignore market traders and mobile operators, so I'm reaching out directly to make sure you're included.</p>
<p>Getting listed takes one reply from you:</p>
<ul>
  <li>Your trading name</li>
  <li>Any Instagram, Facebook or website link</li>
</ul>
<p>That's it. No forms, no cost.</p>
<p>Jonathan<br>ThaiData UK · thaidata.uk</p>`
    }
  ];

  const results = [];
  for (const email of testEmails) {
    try {
      const res = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ***,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'ThaiData UK <hello@thaidata.uk>',
          to: [email.to],
          subject: `[TEST] ${email.subject}`,
          html: email.html,
        }),
      });
      const body = await res.json();
      results.push({ subject: email.subject, status: res.status, id: body.id || body.error });
    } catch (err) {
      results.push({ subject: email.subject, error: err.message });
    }
  }

  return new Response(JSON.stringify({ sent: results.length, results }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

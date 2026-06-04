// ThaiData UK — GET /api/diag — diagnostic endpoint for env vars and Telegram
export async function onRequestGet(context) {
  const { env } = context;
  const results = {};

  // Check each env var
  results.ADMIN_PASSWORD = env.ADMIN_PASSWORD ? 'SET (length ' + env.ADMIN_PASSWORD.length + ')' : 'MISSING';
  results.TELEGRAM_BOT_TOKEN = env.TELEGRAM_BOT_TOKEN ? 'SET (length ' + env.TELEGRAM_BOT_TOKEN.length + ')' : 'MISSING';
  results.TELEGRAM_CHAT_ID = env.TELEGRAM_CHAT_ID ? 'SET: ' + env.TELEGRAM_CHAT_ID : 'MISSING';
  results.ADMIN_EMAIL = env.ADMIN_EMAIL ? 'SET: ' + env.ADMIN_EMAIL : 'MISSING';
  results.RESEND_API_KEY = env.RESEND_API_KEY ? 'SET (length ' + env.RESEND_API_KEY.length + ')' : 'MISSING';

  // Test Telegram send
  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    try {
      const res = await fetch(
        `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: env.TELEGRAM_CHAT_ID,
            text: '🔧 Diagnostic ping from ThaiData Functions — env vars working.',
          }),
        }
      );
      const data = await res.json();
      results.telegram_test = data.ok ? 'OK' : 'FAIL: ' + JSON.stringify(data);
    } catch (e) {
      results.telegram_test = 'ERROR: ' + e.message;
    }
  } else {
    results.telegram_test = 'SKIPPED (missing vars)';
  }

  return new Response(JSON.stringify(results, null, 2), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

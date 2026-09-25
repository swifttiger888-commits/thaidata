// Tests for /api/correction handler
// Run: node tests/test_correction_api.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

// correction.js imports ./_email.js — inline the email module as a data: URL so the
// handler can be imported in isolation (same trick as test_middleware_photos.mjs).
const emailSrc = readFileSync(new URL('../functions/api/_email.js', import.meta.url), 'utf8');
const emailDataUrl = 'data:text/javascript;base64,' + Buffer.from(emailSrc).toString('base64');

let corrSrc = readFileSync(new URL('../functions/api/correction.js', import.meta.url), 'utf8');
assert.ok(corrSrc.includes("from './_email.js'"), 'correction.js should import ./_email.js');
corrSrc = corrSrc.replace("from './_email.js'", `from '${emailDataUrl}'`);
const mod = await import('data:text/javascript;base64,' + Buffer.from(corrSrc).toString('base64'));

function makeDB({ attemptCount = 0, insertId = 42 } = {}) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      const stmt = {
        _sql: sql,
        _args: [],
        bind(...args) { stmt._args = args; return stmt; },
        async first() {
          calls.push({ kind: 'first', sql, args: stmt._args });
          if (/SELECT COUNT\(\*\) AS count FROM correction_attempts/.test(sql)) return { count: attemptCount };
          return null;
        },
        async run() {
          calls.push({ kind: 'run', sql, args: stmt._args });
          if (/INSERT INTO corrections/.test(sql)) return { meta: { last_row_id: insertId } };
          return { meta: {} };
        },
        async all() { return { results: [] }; },
      };
      return stmt;
    },
  };
}

function makeReq(body) {
  return new Request('https://thaidata.uk/api/correction', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.9' },
    body: JSON.stringify(body),
  });
}

const BASE = {
  restaurant_name: 'My Thai',
  city: 'Leeds',
  fsa_id: '842597',
  category: 'hours',
  details: 'We now close at 9pm on Sundays, not 10pm.',
  reporter_email: '',
  page_url: '/r/leeds/my-thai/',
};

const savedFetch = globalThis.fetch;
function stubFetch(impl) { globalThis.fetch = impl; }
function restoreFetch() { globalThis.fetch = savedFetch; }

let passed = 0;
async function check(name, fn) {
  await fn();
  passed++;
  console.log(`PASS ${passed}: ${name}`);
}

const insertCalls = (env) => env.DB.calls.filter(c => /INSERT INTO corrections/.test(c.sql));

// 1. Honeypot filled → silent 200, nothing stored
await check('honeypot discarded silently', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, website: 'http://spam.example' }), env });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.success, true);
  assert.equal(insertCalls(env).length, 0, 'no insert for honeypot');
});

// 2. Missing restaurant_name → 400
await check('missing restaurant_name rejected', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, restaurant_name: '' }), env });
  assert.equal(res.status, 400);
});

// 3. Unknown category → 400
await check('bad category rejected', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, category: 'pricing' }), env });
  assert.equal(res.status, 400);
});

// 4. Details too short → 400
await check('short details rejected', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, details: 'too short' }), env });
  assert.equal(res.status, 400);
});

// 5. Bad reporter email → 400
await check('bad reporter email rejected', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, reporter_email: 'not-an-email' }), env });
  assert.equal(res.status, 400);
});

// 6. Valid submission → 201, correct binds, attempt recorded
await check('valid submission stored', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestPost({ request: makeReq({ ...BASE, reporter_email: 'sarah@example.com' }), env });
  assert.equal(res.status, 201);
  const data = await res.json();
  assert.equal(data.success, true);
  assert.equal(data.id, 42);

  const inserts = insertCalls(env);
  assert.equal(inserts.length, 1, 'one corrections insert');
  assert.deepEqual(inserts[0].args, [
    '842597', 'My Thai', 'Leeds', 'hours',
    'We now close at 9pm on Sundays, not 10pm.', 'sarah@example.com', '/r/leeds/my-thai/',
  ]);

  const attempts = env.DB.calls.filter(c => /INSERT INTO correction_attempts/.test(c.sql));
  assert.equal(attempts.length, 1, 'attempt recorded');
  assert.deepEqual(attempts[0].args, ['203.0.113.9']);
});

// 7. Rate limit: already 5 attempts this hour → 429, no insert
await check('rate limited after 5 per hour', async () => {
  const env = { DB: makeDB({ attemptCount: 5 }) };
  const res = await mod.onRequestPost({ request: makeReq(BASE), env });
  assert.equal(res.status, 429);
  assert.equal(insertCalls(env).length, 0, 'no insert when throttled');
});

// 8. fsa_id optional → stored as NULL
await check('fsa_id optional', async () => {
  const env = { DB: makeDB() };
  const body = { ...BASE };
  delete body.fsa_id;
  const res = await mod.onRequestPost({ request: makeReq(body), env });
  assert.equal(res.status, 201);
  assert.equal(insertCalls(env)[0].args[0], null);
});

// 9. Notification transport failure (Telegram + Resend both throw) → still 201
await check('notification failure tolerated', async () => {
  stubFetch(() => { throw new Error('network down'); });
  try {
    const env = {
      DB: makeDB(),
      RESEND_API_KEY: 'test-key',
      TELEGRAM_BOT_TOKEN: 'test-token',
      TELEGRAM_CHAT_ID: '12345',
    };
    const res = await mod.onRequestPost({ request: makeReq(BASE), env });
    assert.equal(res.status, 201);
  } finally {
    restoreFetch();
  }
});

// 10. Non-JSON body → 400
await check('non-JSON body rejected', async () => {
  const env = { DB: makeDB() };
  const request = new Request('https://thaidata.uk/api/correction', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: 'not json at all',
  });
  const res = await mod.onRequestPost({ request, env });
  assert.equal(res.status, 400);
});

console.log(`\nAll ${passed} checks passed.`);

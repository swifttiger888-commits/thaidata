// Tests for /api/listing — public queries must only serve approved-claim listings.
// Run: node tests/test_listing_filter.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

// listing.js imports { sha256, sendMagicLinkEmail } from './_email.js' — inline it
// as a data: URL so the handler can be imported in isolation (same trick as
// test_correction_api.mjs / test_middleware_photos.mjs).
const emailSrc = readFileSync(new URL('../functions/api/_email.js', import.meta.url), 'utf8');
const emailDataUrl = 'data:text/javascript;base64,' + Buffer.from(emailSrc).toString('base64');

let src = readFileSync(new URL('../functions/api/listing.js', import.meta.url), 'utf8');
assert.ok(src.includes("from './_email.js'"), 'listing.js should import ./_email.js');
src = src.replace("from './_email.js'", `from '${emailDataUrl}'`);
const mod = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

function makeDB({ rows = [], tokenRow = null, listingRow = null } = {}) {
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
          if (/FROM auth_tokens/.test(sql)) return tokenRow;
          if (/SELECT \* FROM listings WHERE id = \?/.test(sql)) return listingRow;
          return null;
        },
        async all() {
          calls.push({ kind: 'all', sql, args: stmt._args });
          return { results: rows };
        },
        async run() { calls.push({ kind: 'run', sql, args: stmt._args }); return { meta: {} }; },
      };
      return stmt;
    },
  };
}

function makeReq(qs, headers = {}) {
  return new Request('https://thaidata.uk/api/listing' + qs, { headers });
}

let passed = 0;
async function check(name, fn) { await fn(); passed++; console.log(`PASS ${passed}: ${name}`); }

const APPROVED_FILTER = /JOIN claims c ON c\.id = l\.claim_id WHERE c\.claim_status = 'approved'/;

const ROW = {
  id: 2, restaurant_name: 'Chao Phraya Thai Restaurant', city: 'Leeds',
  features: null, photos: null, menu_highlights: null, enrichment: null,
};

// 1. restaurant+city → approved-join + l.* filters, binds preserved
await check('restaurant+city query filters approved claims', async () => {
  const env = { DB: makeDB({ rows: [ROW] }) };
  const res = await mod.onRequestGet({ request: makeReq('?restaurant=Chao%20Phraya%20Thai%20Restaurant&city=Leeds'), env });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.count, 1);
  const q = env.DB.calls.find(c => c.kind === 'all');
  assert.ok(APPROVED_FILTER.test(q.sql), 'public query must join approved claims');
  assert.ok(/AND l\.restaurant_name = \? AND l\.city = \?/.test(q.sql), 'filters use l.* columns');
  assert.deepEqual(q.args, ['Chao Phraya Thai Restaurant', 'Leeds']);
});

// 2. fsa_id → approved-join
await check('fsa_id query filters approved claims', async () => {
  const env = { DB: makeDB({ rows: [ROW] }) };
  const res = await mod.onRequestGet({ request: makeReq('?fsa_id=349033'), env });
  assert.equal(res.status, 200);
  const q = env.DB.calls.find(c => c.kind === 'all');
  assert.ok(APPROVED_FILTER.test(q.sql));
  assert.ok(/AND l\.fsa_id = \?/.test(q.sql));
  assert.deepEqual(q.args, ['349033']);
});

// 3. city-only → approved-join
await check('city query filters approved claims', async () => {
  const env = { DB: makeDB({ rows: [] }) };
  const res = await mod.onRequestGet({ request: makeReq('?city=Leeds'), env });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.count, 0);
  const q = env.DB.calls.find(c => c.kind === 'all');
  assert.ok(APPROVED_FILTER.test(q.sql));
  assert.ok(/AND l\.city = \?/.test(q.sql));
});

// 4. no params → 400, no DB access
await check('no params rejected without DB access', async () => {
  const env = { DB: makeDB() };
  const res = await mod.onRequestGet({ request: makeReq(''), env });
  assert.equal(res.status, 400);
  assert.equal(env.DB.calls.length, 0);
});

// 5. token (Bearer) path unchanged — owner still gets their listing by id, no claim filter
await check('token path returns listing by id (no claim filter)', async () => {
  const env = { DB: makeDB({
    tokenRow: { listing_id: 9 },
    listingRow: { ...ROW, id: 9 },
  }) };
  const res = await mod.onRequestGet({ request: makeReq('', { Authorization: 'Bearer test-token-123' }), env });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.count, 1);
  assert.equal(data.listings[0].id, 9);
  const q = env.DB.calls.find(c => c.kind === 'first' && /SELECT \* FROM listings WHERE id = \?/.test(c.sql));
  assert.ok(q, 'listing fetched by id for token path');
  assert.ok(!APPROVED_FILTER.test(q.sql), 'token path must NOT be claim-filtered');
});

// 6. archived-claim result → empty response stays empty (count 0), not an error
await check('archived-only match returns empty payload', async () => {
  const env = { DB: makeDB({ rows: [] }) };
  const res = await mod.onRequestGet({ request: makeReq('?restaurant=Thai%20Sun&city=Leeds'), env });
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.deepEqual(data.listings, []);
  assert.equal(data.count, 0);
});

console.log(`\nAll ${passed} checks passed.`);

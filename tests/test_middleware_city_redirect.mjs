// Tests for /r/_middleware.js dropped-venue → city-page redirect
// Run: node tests/test_middleware_city_redirect.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const src = readFileSync(new URL('../functions/r/_middleware.js', import.meta.url), 'utf8');
const mod = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

// Real venue page: contains the Hygiene marker the middleware looks for.
const VENUE_HTML = `<!DOCTYPE html><html><head><title>Venue</title></head><body>
<p>FSA 5/5 Hygiene Rating</p><!-- Trust Sidebar --><div id="trust">trust</div></body></html>`;

// SPA fallback: what Pages returns for an unmatched path (homepage, 200).
const FALLBACK_HTML = `<!DOCTYPE html><html><head><title>ThaiData</title></head><body>home</body></html>`;

const CITY_HTML = `<!DOCTYPE html><html><head><title>Thai Restaurants in Leeds</title>
<link rel="canonical" href="https://thaidata.uk/cities/leeds"></head><body>city</body></html>`;

function req(path) {
  return new Request('https://thaidata.uk' + path, { headers: { accept: 'text/html' } });
}

function makeEnv({ cityExists = true, throwOnAssets = false } = {}) {
  return {
    DB: {
      prepare() {
        return { bind() { return this; }, async first() { return null; } };
      },
    },
    ASSETS: {
      async fetch(input) {
        const href = typeof input === 'string' ? input : input.url;
        if (throwOnAssets) throw new Error('asset layer down');
        if (href.includes('/cities/')) {
          const city = href.split('/cities/')[1].replace(/[/?].*$/, '');
          if (cityExists && city === 'leeds') {
            return new Response(CITY_HTML, { status: 200 });
          }
          return new Response(FALLBACK_HTML, { status: 200 });
        }
        // Venue paths: known venue serves the real page, unknown falls back.
        if (href.includes('thai-2-go')) {
          return new Response(VENUE_HTML, { status: 200 });
        }
        // Mantra Thai Dining: parent listing exists, its /menu/ page does not.
        if (href.includes('mantra-thai-dining') && !href.includes('/menu/')) {
          return new Response(VENUE_HTML, { status: 200 });
        }
        return new Response(FALLBACK_HTML, { status: 200 });
      },
    },
  };
}

const next = () => { throw new Error('should not fall through to next()'); };

// 1. Dropped venue + city page exists → 301 to the city page
{
  const res = await mod.onRequest({
    request: req('/r/leeds/lamoon-thai-kitchen/'),
    env: makeEnv({ cityExists: true }),
    next,
  });
  assert.equal(res.status, 301);
  assert.equal(res.headers.get('Location'), '/cities/leeds');
  console.log('PASS 1: dropped venue → 301 city page');
}

// 2. Unknown city (no city page) → 404, no redirect loop
{
  const res = await mod.onRequest({
    request: req('/r/nowhere/lamoon-thai-kitchen/'),
    env: makeEnv({ cityExists: true }),
    next,
  });
  assert.equal(res.status, 404);
  console.log('PASS 2: unknown city → 404');
}

// 3. Claimant deep-link (?source=claim) keeps the helpful claim 404
{
  const res = await mod.onRequest({
    request: req('/r/leeds/lamoon-thai-kitchen/?source=claim'),
    env: makeEnv({ cityExists: true }),
    next,
  });
  assert.equal(res.status, 404);
  const body = await res.text();
  assert.ok(body.includes('Page not ready yet'), 'claim help page');
  console.log('PASS 3: claim-source 404 preserved');
}

// 4. Asset layer failure → falls through to next() (pre-existing fallback), never throws
{
  let nextCalled = false;
  const res = await mod.onRequest({
    request: req('/r/leeds/lamoon-thai-kitchen/'),
    env: makeEnv({ throwOnAssets: true }),
    next: () => { nextCalled = true; return new Response('fallback', { status: 200 }); },
  });
  assert.equal(nextCalled, true, 'next() called on asset failure');
  assert.equal(res.status, 200, 'fallback response returned');
  console.log('PASS 4: asset failure → next() fallback (no crash)');
}

// 5. Existing venue still serves 200 (regression)
{
  const res = await mod.onRequest({
    request: req('/r/leeds/thai-2-go/'),
    env: makeEnv(),
    next,
  });
  assert.equal(res.status, 200);
  const body = await res.text();
  assert.ok(body.includes('Hygiene'), 'venue page served');
  console.log('PASS 5: existing venue unaffected');
}

// 6. Bare venue URL still 301s to the trailing-slash form (regression)
{
  const res = await mod.onRequest({
    request: req('/r/leeds/test-thai'),
    env: makeEnv(),
    next,
  });
  assert.equal(res.status, 301);
  assert.equal(res.headers.get('Location'), '/r/leeds/test-thai/');
  console.log('PASS 6: trailing-slash redirect intact');
}

// 7. Stale /menu/ URL with a live parent → 301 to the parent listing, not the city
{
  const res = await mod.onRequest({
    request: req('/r/newcastle/mantra-thai-dining/menu/'),
    env: makeEnv({ cityExists: true }),
    next,
  });
  assert.equal(res.status, 301);
  assert.equal(res.headers.get('Location'), '/r/newcastle/mantra-thai-dining/');
  console.log('PASS 7: stale menu URL → 301 parent listing');
}

console.log('ALL MIDDLEWARE CITY-REDIRECT TESTS PASSED');

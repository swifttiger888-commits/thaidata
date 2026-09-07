// Tests for /r/_middleware.js owner-photo injection
// Run: node tests/test_middleware_photos.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const src = readFileSync(new URL('../functions/r/_middleware.js', import.meta.url), 'utf8');
const mod = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

const SAMPLE_HTML = `<!DOCTYPE html><html><head><title>Test</title>
<script type="application/ld+json">{"@type":"Restaurant","name":"Test Thai","address":{"addressLocality":"Leeds","streetAddress":"1 Test St"}}</script>
</head><body>
<p>FSA 5/5 Hygiene Rating</p>
<!-- Trust Sidebar --><div id="trust">trust</div>
</body></html>`;

function makeEnv(listing) {
  return {
    DB: {
      prepare() {
        return {
          bind() { return this; },
          async first() { return listing; },
        };
      },
    },
    ASSETS: {
      async fetch() { return new Response(SAMPLE_HTML, { status: 200 }); },
    },
  };
}

function req(path) {
  return new Request('https://thaidata.uk' + path, { headers: { 'accept': 'text/html' } });
}

// 1. Photos (JSON string) render gallery + srcset variants + JSON-LD image array
{
  const env = makeEnv({
    cuisine_specialty: 'Thai curries',
    price_range: '£',
    opening_hours: ['Monday: 12:00–22:00'],
    website: 'https://example.com',
    description: 'Family run.',
    phone: '0113 000 0000',
    photos: JSON.stringify([
      'https://imagedelivery.net/hash/id1/public',
      'https://imagedelivery.net/hash/id2/public',
    ]),
  });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('should not fall through'); } });
  assert.equal(res.status, 200);
  const body = await res.text();
  assert.ok(body.includes('id="owner-photos"'), 'gallery present');
  assert.ok(body.includes('srcset="https://imagedelivery.net/hash/id1/w=400 400w, https://imagedelivery.net/hash/id1/w=800 800w"'), 'srcset variants');
  assert.equal((body.match(/loading="lazy"/g) || []).length, 2, 'two lazy imgs');
  const ldMatch = body.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  const ld = JSON.parse(ldMatch[1]);
  assert.ok(Array.isArray(ld.image) && ld.image.length === 2, 'JSON-LD image array');
  assert.ok(body.includes('id="quick-facts"'), 'quick facts still present');
  assert.ok(body.includes('<!-- Trust Sidebar -->'), 'anchor intact');
  console.log('PASS 1: photos JSON string → gallery + srcset + JSON-LD');
}

// 2. Photos as array (not string) also work
{
  const env = makeEnv({
    photos: ['https://imagedelivery.net/hash/id3/public'],
  });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('id="owner-photos"'), 'gallery present (array input)');
  console.log('PASS 2: photos as array');
}

// 3. No photos → no gallery, no image in JSON-LD, page unchanged structure
{
  const env = makeEnv({ description: 'just facts' });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('owner-photos'), 'no gallery');
  const ld = JSON.parse(body.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1]);
  assert.ok(!('image' in ld), 'no image key');
  console.log('PASS 3: no photos → unchanged');
}

// 4. Malformed photos JSON does not break page
{
  const env = makeEnv({ photos: '{broken json', description: 'still renders' });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('owner-photos'), 'no gallery on malformed');
  assert.ok(body.includes('Quick Facts'), 'facts still render');
  console.log('PASS 4: malformed photos JSON tolerated');
}

// 5. XSS: non-imagedelivery URL is dropped entirely (allowlist)
{
  const env = makeEnv({ photos: ['https://x.example/"><script>alert(1)</script>/public'] });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('owner-photos'), 'no gallery for foreign URL');
  assert.ok(!body.includes('alert(1)'), 'malicious URL dropped');
  console.log('PASS 5: foreign URL dropped (allowlist)');
}

// 6. XSS: imagedelivery URL containing markup is safe (escaped + JSON-LD </ escaped)
{
  const env = makeEnv({ photos: ['https://imagedelivery.net/hash/"><script>alert(1)</script>/public'] });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('id="owner-photos"'), 'gallery present');
  assert.ok(!body.includes('"><script>alert(1)</script>" srcset'), 'attrs escaped in img');
  assert.ok(!/<script>alert\(1\)<\/script>\s*<\/script>/.test(body), 'no script breakout');
  console.log('PASS 6: imagedelivery URL escaped safely');
}

console.log('ALL MIDDLEWARE PHOTO TESTS PASSED');

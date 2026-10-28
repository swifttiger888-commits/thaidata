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

// 7. Features (JSON string) render in Quick Facts, escaped
{
  const env = makeEnv({
    features: JSON.stringify(['Vegetarian options', 'Happy hour 12<5 daily']),
  });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('>Features</span>'), 'features row present');
  assert.ok(body.includes('Vegetarian options'), 'feature 1');
  assert.ok(!body.includes('12<5 daily'), 'feature escaped (no raw <)');
  assert.ok(body.includes('12&lt;5 daily'), 'escaped feature text');
  console.log('PASS 7: features rendered + escaped');
}

// 8. Features as array also render
{
  const env = makeEnv({ features: ['BYOB', 'Halal'] });
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('BYOB') && body.includes('Halal'), 'array features render');
  console.log('PASS 8: features as array');
}

const SAMPLE_HTML_RATED = `<!DOCTYPE html><html><head><title>Test</title>
<script type="application/ld+json">{"@type":"Restaurant","name":"Test Thai","address":{"addressLocality":"Leeds","streetAddress":"1 Test St"},"aggregateRating":{"@type":"AggregateRating","ratingValue":4.4,"reviewCount":2040,"bestRating":5}}</script>
</head><body>
<p>FSA 5/5 Hygiene Rating</p>
<!-- Trust Sidebar --><div id="trust">trust</div>
</body></html>`;

// 9. aggregateRating + claimed listing → visible rating + attribution
{
  const env = makeEnv({ description: 'x', photos: [] });
  env.ASSETS = { async fetch() { return new Response(SAMPLE_HTML_RATED, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('Google rating'), 'rating row present');
  assert.ok(body.includes('4.4'), 'rating value shown');
  assert.ok(body.includes('2,040 reviews'), 'review count formatted');
  assert.ok(body.includes('Data from Google'), 'attribution present');
  assert.ok(body.includes('google.com/maps/search/?api=1&amp;query=Test%20Thai%20Leeds'), 'maps attribution link');
  console.log('PASS 9: rating visible on claimed page + attribution');
}

// 10. aggregateRating but NOT claimed → rating stays schema-only
{
  const env = makeEnv(null);
  env.ASSETS = { async fetch() { return new Response(SAMPLE_HTML_RATED, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('Google rating'), 'no visible rating on unclaimed page');
  assert.ok(body.includes('aggregateRating'), 'schema still carries rating');
  console.log('PASS 10: unclaimed page keeps rating schema-only');
}

// 11. Malformed ratingValue → skipped safely
{
  const ratedBad = SAMPLE_HTML_RATED.replace('"ratingValue":4.4', '"ratingValue":"abc"');
  const env = makeEnv({ description: 'x' });
  env.ASSETS = { async fetch() { return new Response(ratedBad, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('Google rating'), 'malformed rating not shown');
  assert.ok(body.includes('Quick Facts'), 'rest of card intact');
  console.log('PASS 11: malformed ratingValue skipped');
}

// 12. Contact strip kept on claimed page — it carries the only above-the-fold
// visitor action (Directions). It holds no contact data, so it cannot duplicate
// Quick Facts. It used to be stripped here, which left claimed pages with no
// visitor action in the hero.
{
  const htmlWithStrip = SAMPLE_HTML.replace('<p>FSA 5/5 Hygiene Rating</p>',
    '<div class="contact-strip" id="contact-strip" style="margin-top:10px;"><a class="cs-item" href="https://www.google.com/maps/search/?api=1&amp;query=Test%20Thai">Directions</a></div><p>FSA 5/5 Hygiene Rating</p>');
  const env = makeEnv({ description: 'owner data here' });
  env.ASSETS = { async fetch() { return new Response(htmlWithStrip, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('contact-strip'), 'directions strip survives on claimed page');
  assert.ok(body.includes('maps/search'), 'directions link survives');
  assert.ok(body.includes('Quick Facts'), 'facts still injected');
  console.log('PASS 12: directions strip kept on claimed page');
}

// 13. Contact strip kept on unclaimed page
{
  const htmlWithStrip = SAMPLE_HTML.replace('<p>FSA 5/5 Hygiene Rating</p>',
    '<div class="contact-strip" id="contact-strip" style="margin-top:10px;"><a class="cs-item" href="tel:0113 245 9245">0113 245 9245</a></div><p>FSA 5/5 Hygiene Rating</p>');
  const env = makeEnv(null);
  env.ASSETS = { async fetch() { return new Response(htmlWithStrip, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/leeds/test-thai/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('contact-strip'), 'strip kept on unclaimed page');
  console.log('PASS 13: contact strip kept on unclaimed page');
}

// 14. Menu page older than 90 days → staleness notice injected
{
  const old = new Date(Date.now() - 200 * 86400000).toISOString().slice(0, 10);
  const menuHtml = `<!DOCTYPE html><html><head><meta name="thaidata-page" content="menu">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Menu","name":"Test Menu","dateModified":"${old}"}</script>
</head><body><header class="masthead"></header>
<main class="wrap">
  <div class="notice">Published by ThaiData UK…</div>
</main></body></html>`;
  const env = makeEnv({});
  env.ASSETS = { async fetch() { return new Response(menuHtml, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/bristol/brother-thai/menu/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(body.includes('id="menu-stale"'), 'stale notice present');
  assert.ok(body.includes('it may have changed since'), 'notice copy');
  console.log('PASS 14: stale menu notice injected (>90 days)');
}

// 15. Fresh menu page → no notice, page intact
{
  const fresh = new Date(Date.now() - 10 * 86400000).toISOString().slice(0, 10);
  const menuHtml = `<!DOCTYPE html><html><head><meta name="thaidata-page" content="menu">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Menu","name":"Test Menu","dateModified":"${fresh}"}</script>
</head><body><header class="masthead"></header>
<main class="wrap">
  <div class="notice">Published by ThaiData UK…</div>
</main></body></html>`;
  const env = makeEnv({});
  env.ASSETS = { async fetch() { return new Response(menuHtml, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/bristol/brother-thai/menu/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.ok(!body.includes('id="menu-stale"'), 'no stale notice on fresh menu');
  assert.ok(body.includes('masthead'), 'page served intact');
  console.log('PASS 15: fresh menu unmarked');
}

// 16. A real built menu page still serves through the nested branch
{
  const real = readFileSync(new URL('../r/bristol/brother-thai/menu/index.html', import.meta.url), 'utf8');
  const env = makeEnv({});
  env.ASSETS = { async fetch() { return new Response(real, { status: 200 }); } };
  const res = await mod.onRequest({ request: req('/r/bristol/brother-thai/menu/'), env, next: () => { throw new Error('no'); } });
  const body = await res.text();
  assert.equal(res.status, 200, 'served');
  assert.ok(body.includes('thaidata-page'), 'marker present');
  assert.ok(body.includes('masthead'), 'real page intact');
  console.log('PASS 16: real built menu page serves via nested branch');
}

console.log('ALL MIDDLEWARE PHOTO TESTS PASSED');

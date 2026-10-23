// ThaiData UK — /r/ middleware
// Resolves short-name aliases to canonical restaurant pages.
// Only triggers for /r/{city}/{name} URLs (3+ path segments).
// Existing static pages pass through unchanged (via env.ASSETS.fetch).
// Unknown URLs return 404 instead of the SPA fallback (root index.html).

function slugify(s) {
  s = (s || '').toLowerCase().trim();
  s = s.replace(/[^\w\s-]/g, '');
  s = s.replace(/[-\s]+/g, '-');
  s = s.replace(/^-+|-+$/g, '');
  return s;
}

function pageUrl(name, city) {
  return '/r/' + slugify(city) + '/' + slugify(name) + '/';
}

/**
 * Escape HTML entities to prevent XSS in D1-sourced content.
 */
function htmlEscape(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Sample claimed listing — static HTML served at /r/demo/claimed-listing/.
 *
 * Deliberately not a generated restaurant page: there is no FSA record behind
 * it, so it carries no fsa_id and no Restaurant JSON-LD (never fabricate
 * structured data for a venue that does not exist). Image slots are inline
 * SVG placeholders — the Cloudflare Images API needs an account-scoped token,
 * which we will not embed in a public renderer.
 */
const DEMO_LISTING_HTML = `<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Example Claimed Listing — What You Get | ThaiData UK</title>
    <meta name="description" content="An example of a claimed ThaiData listing: owner photos, opening hours, price range, features and an owner-written description. This is a sample record, not a real restaurant.">
    <meta name="robots" content="noindex, nofollow">
    <meta name="thaidata-page" content="demo">
    <link rel="canonical" href="https://thaidata.uk/r/demo/claimed-listing/">
    <meta property="og:type" content="website">
    <meta property="og:title" content="Example Claimed Listing — ThaiData UK">
    <meta property="og:description" content="See what a claimed ThaiData listing looks like: photos, hours, price range, features and owner description.">
    <link rel="icon" type="image/svg+xml" href="/favicon-emblem.3a4d8ed8.png">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" /></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" media="print" onload="this.media='all'" /><noscript><link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" /></noscript>
    <style>
        :root {
            --ivory: #FBF7F0; --paper: #FFFFFF; --white: #FFFFFF; --cream: #FBF7F0;
            --ink: #1A1614; --ink-soft: #4A403C; --ink-mute: #7A6F6A;
            --hairline: #E7DFD5; --border: #E7DFD5; --border-light: #F2EDE6;
            --brand: #A3132B; --brand-press: #7E0E20; --brand-tint: #F7E8EB;
            --turmeric: #F2B21A; --jade: #047857;
            --success: #047857; --success-dark: #065F46; --success-light: #D1FAE5;
            --amber: #B45309; --amber-light: #FEF3C7;
            --danger: #B91C1C; --danger-light: #FEE2E2;
            --green: var(--brand); --green-dark: var(--brand-press); --green-light: var(--brand-tint);
            --ink-secondary: var(--ink-soft); --ink-tertiary: var(--ink-mute);
            --radius: 14px; --radius-sm: 8px;
            --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
            --shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1);
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--ivory); color: var(--ink); margin: 0; line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }
        a { color: var(--brand); }
        .nav { background: var(--paper); border-bottom: 1px solid var(--hairline); position: sticky; top: 0; z-index: 50; }
        .nav-inner { max-width: 1080px; margin: 0 auto; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
        .logo { display: inline-flex; align-items: center; gap: 8px; font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 1.05rem; color: var(--ink); text-decoration: none; }
        .nav-back { font-size: 0.9rem; text-decoration: none; color: var(--ink-soft); white-space: nowrap; }

        /* Demo banner — must be unmissable. This page shows invented data. */
        .demo-banner {
            background: var(--amber-light); border-bottom: 1px solid #FCD34D;
            color: #78350F; font-size: 0.88rem; padding: 10px 20px; text-align: center;
        }
        .demo-banner strong { font-weight: 700; }

        .hero { background: var(--paper); border-bottom: 1px solid var(--hairline); padding: 28px 20px 24px; }
        .hero-inner { max-width: 1080px; margin: 0 auto; }
        .badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
        .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
        .badge-rating { background: var(--success-light); color: var(--success-dark); }
        .badge-type { background: var(--border-light); color: var(--ink-soft); }
        .badge-sample { background: var(--amber-light); color: #78350F; }
        .hero h1 { font-family: 'Archivo', sans-serif; font-size: clamp(1.5rem, 4vw, 2.1rem); margin: 0 0 8px; line-height: 1.2; }
        .hero h1 em { color: var(--brand); font-style: normal; }
        .hero-location { color: var(--ink-mute); font-size: 0.95rem; margin-bottom: 12px; }
        .hero-blurb { font-size: 0.95rem; color: var(--ink-soft); max-width: 660px; margin: 0; }

        .main { max-width: 1080px; margin: 0 auto; padding: 24px 20px 48px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; }
        @media (min-width: 900px) { .main { grid-template-columns: minmax(0, 1fr) 320px; align-items: start; } }
        .content-col, .sidebar-col { display: flex; flex-direction: column; gap: 20px; min-width: 0; }

        .card { background: var(--paper); border: 1px solid var(--hairline); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow-sm); }
        .card-title { font-family: 'Archivo', sans-serif; font-size: 1.2rem; margin: 0 0 14px; font-weight: 700; }
        .card-title em { color: var(--brand); font-style: normal; }

        .qf-item { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 9px 0; border-bottom: 1px solid var(--border-light); }
        .qf-item:last-child { border-bottom: none; }
        .qf-label { font-size: 0.85rem; color: var(--ink-mute); flex-shrink: 0; }
        .qf-value { font-weight: 500; color: var(--ink); text-align: right; }
        .qf-desc { padding-top: 4px; font-size: 0.9rem; color: var(--ink-soft); line-height: 1.65; }

        .photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .photo-grid .ph {
            aspect-ratio: 4 / 3; border-radius: 10px; overflow: hidden; display: block;
            background: var(--border-light); border: 1px solid var(--hairline);
        }
        .photo-grid .ph svg { width: 100%; height: 100%; display: block; }
        .photo-note { font-size: 0.78rem; color: var(--ink-mute); margin: 12px 0 0; }

        .feature-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .feature-tag { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; background: var(--brand-tint); color: var(--brand-press); border-radius: 20px; font-size: 0.82rem; font-weight: 500; }
        .feature-tag i { font-size: 0.7rem; }

        .hours-line { display: flex; justify-content: space-between; gap: 16px; font-size: 0.9rem; padding: 4px 0; }
        .hours-line span:first-child { color: var(--ink-soft); }

        .menu-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
        .menu-card { background: var(--paper); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 16px; }
        .menu-cat { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--brand); font-weight: 700; margin-bottom: 6px; }
        .menu-name { font-weight: 600; color: var(--ink); margin-bottom: 4px; }
        .menu-desc { color: var(--ink-soft); font-size: 0.85rem; line-height: 1.5; margin-bottom: 6px; }
        .menu-price { font-weight: 700; color: var(--brand-press); font-size: 0.95rem; }

        .claimed-badge-card { background: linear-gradient(135deg, rgba(163,19,43,0.08), rgba(163,19,43,0.04)); border: 1px solid rgba(163,19,43,0.2); border-radius: var(--radius); padding: 20px; text-align: center; }
        .claimed-badge-card .tick { font-size: 2.4rem; color: var(--brand); line-height: 1; margin-bottom: 6px; }
        .claimed-badge-card h3 { font-family: 'Archivo', sans-serif; color: var(--brand-press); margin: 0 0 4px; font-size: 1.05rem; }
        .claimed-badge-card p { color: var(--ink-soft); font-size: 0.85rem; margin: 0; }

        .cta-card { background: var(--brand); border-radius: var(--radius); padding: 22px; color: #fff; text-align: center; }
        .cta-card h3 { font-family: 'Archivo', sans-serif; margin: 0 0 8px; font-size: 1.15rem; }
        .cta-card p { font-size: 0.88rem; margin: 0 0 16px; color: rgba(255,255,255,0.88); }
        .cta-btn { display: inline-block; background: #fff; color: var(--brand-press); font-weight: 700; text-decoration: none; padding: 12px 24px; border-radius: 999px; font-size: 0.95rem; }
        .cta-note { font-size: 0.78rem; color: rgba(255,255,255,0.8); margin: 10px 0 0; }

        .trust-list { list-style: none; margin: 0; padding: 0; }
        .trust-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid var(--border-light); font-size: 0.88rem; color: var(--ink-soft); }
        .trust-item:last-child { border-bottom: none; }
        .trust-item i { color: var(--brand); width: 18px; margin-top: 3px; }
        .trust-item strong { display: block; color: var(--ink); }

        .related { background: var(--paper); border-top: 1px solid var(--hairline); padding: 24px 20px; text-align: center; }
        .related-inner a { display: inline-block; margin: 4px 12px; font-size: 0.9rem; }
        .site-footer { background: var(--ink); color: rgba(255,255,255,0.75); text-align: center; padding: 26px 20px; font-size: 0.85rem; }
        .site-footer a { color: var(--turmeric); }
    </style>
</head>
<body>

    <!-- Demo notice: this page shows invented data, never a real FSA record. -->
    <div class="demo-banner">
        <strong>Sample listing.</strong> Everything on this page is made up to show what a claimed listing looks like — it is not a real restaurant and not an FSA record.
    </div>

    <nav class="nav">
        <div class="nav-inner">
            <a href="/index.html" class="logo">
                <img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" style="height:34px;width:auto;display:block;">
            </a>
            <a href="/claim/" class="nav-back"><i class="fas fa-arrow-left"></i> Back to claiming</a>
        </div>
    </nav>

    <section class="hero">
        <div class="hero-inner">
            <div class="badge-row">
                <span class="badge badge-sample"><i class="fas fa-flask"></i> Example</span>
                <span class="badge badge-rating"><i class="fas fa-star"></i> FSA 5/5</span>
                <span class="badge badge-type"><i class="fas fa-utensils"></i> Restaurant</span>
            </div>
            <h1>Example Thai <em>Restaurant</em> — Thai Restaurant in Leeds</h1>
            <div class="hero-location"><i class="fas fa-map-marker-alt"></i> Leeds</div>
            <p class="hero-blurb">A worked example of a claimed listing. Compare this with an unclaimed page: your real details, your photos and your story, in place of a bare FSA record.</p>
        </div>
    </section>

    <div class="main">
        <div class="content-col">

            <div class="card">
                <h2 class="card-title">Quick <em>Facts</em></h2>
                <div class="qf-item"><span class="qf-label">Cuisine</span><span class="qf-value">Northern Thai (Isaan)</span></div>
                <div class="qf-item"><span class="qf-label">Features</span><span class="qf-value">Family run<br>Vegetarian options<br>Takeaway<br>Dog friendly</span></div>
                <div class="qf-item"><span class="qf-label">Price</span><span class="qf-value">££</span></div>
                <div class="qf-item"><span class="qf-label">Hours</span><span class="qf-value">Mon–Sat: 12:00 – 22:00<br>Sunday: closed</span></div>
                <div class="qf-item"><span class="qf-label">Website</span><span class="qf-value"><a href="#" style="color:var(--brand);text-decoration:none;">Visit &rarr;</a></span></div>
                <div class="qf-desc">A worked example of the description an owner can write. Two or three sentences about the food, the room and the people behind it is usually enough — this is the field that turns a data record into something a diner actually wants to visit.</div>
            </div>

            <div class="card">
                <h2 class="card-title">Photo <em>Gallery</em></h2>
                <div class="photo-grid">
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of the dining room"><rect width="160" height="120" fill="#F2EDE6"/><path d="M0 96h160v24H0z" fill="#E7DFD5"/><circle cx="80" cy="52" r="18" fill="#D8CFC2"/><path d="M46 96V70h68v26z" fill="#D8CFC2"/></svg></span>
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of a dish"><rect width="160" height="120" fill="#F2EDE6"/><ellipse cx="80" cy="76" rx="46" ry="12" fill="#D8CFC2"/><path d="M40 76a40 26 0 0 1 80 0z" fill="#C9BEB0"/></svg></span>
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of the kitchen"><rect width="160" height="120" fill="#F2EDE6"/><rect x="18" y="30" width="124" height="12" rx="4" fill="#D8CFC2"/><rect x="30" y="56" width="40" height="34" rx="4" fill="#C9BEB0"/><rect x="90" y="56" width="40" height="34" rx="4" fill="#C9BEB0"/></svg></span>
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of the shopfront"><rect width="160" height="120" fill="#F2EDE6"/><rect x="24" y="34" width="112" height="62" fill="#D8CFC2"/><rect x="68" y="66" width="24" height="30" fill="#F2EDE6"/></svg></span>
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of a table setting"><rect width="160" height="120" fill="#F2EDE6"/><circle cx="60" cy="60" r="20" fill="#D8CFC2"/><circle cx="104" cy="60" r="20" fill="#C9BEB0"/></svg></span>
                    <span class="ph"><svg viewBox="0 0 160 120" role="img" aria-label="Placeholder for an owner photo of a detail shot"><rect width="160" height="120" fill="#F2EDE6"/><path d="M30 90l30-40 26 30 18-20 26 30z" fill="#D8CFC2"/></svg></span>
                </div>
                <p class="photo-note">Placeholders above. On a claimed listing these are your own photos, served from Cloudflare Images and shown at the top of the page.</p>
            </div>

            <div class="card">
                <h2 class="card-title">Menu <em>Highlights</em></h2>
                <div class="menu-grid">
                    <div class="menu-card"><div class="menu-cat">Starters</div><div class="menu-name">Som Tam</div><div class="menu-desc">Green papaya salad with peanuts, lime and chilli.</div><div class="menu-price">£7.50</div></div>
                    <div class="menu-card"><div class="menu-cat">Starters</div><div class="menu-name">Gai Satay</div><div class="menu-desc">Grilled chicken skewers with peanut sauce.</div><div class="menu-price">£6.95</div></div>
                    <div class="menu-card"><div class="menu-cat">Mains</div><div class="menu-name">Pad Thai</div><div class="menu-desc">Rice noodles, tamarind, egg, beansprouts and lime.</div><div class="menu-price">£11.50</div></div>
                    <div class="menu-card"><div class="menu-cat">Mains</div><div class="menu-name">Gaeng Massaman</div><div class="menu-desc">Slow-cooked beef curry with potato and roasted peanuts.</div><div class="menu-price">£13.95</div></div>
                    <div class="menu-card"><div class="menu-cat">Mains</div><div class="menu-name">Pad Krapow</div><div class="menu-desc">Stir-fried holy basil with chilli and jasmine rice.</div><div class="menu-price">£11.95</div></div>
                    <div class="menu-card"><div class="menu-cat">Desserts</div><div class="menu-name">Khao Niaow Ma Muang</div><div class="menu-desc">Sticky rice with mango and coconut cream.</div><div class="menu-price">£6.50</div></div>
                </div>
            </div>

            <div class="card">
                <h2 class="card-title">Opening <em>Hours</em></h2>
                <div class="hours-line"><span>Monday</span><span>12:00 – 22:00</span></div>
                <div class="hours-line"><span>Tuesday</span><span>12:00 – 22:00</span></div>
                <div class="hours-line"><span>Wednesday</span><span>12:00 – 22:00</span></div>
                <div class="hours-line"><span>Thursday</span><span>12:00 – 22:00</span></div>
                <div class="hours-line"><span>Friday</span><span>12:00 – 23:00</span></div>
                <div class="hours-line"><span>Saturday</span><span>12:00 – 23:00</span></div>
                <div class="hours-line"><span>Sunday</span><span>Closed</span></div>
            </div>

            <div class="card">
                <h2 class="card-title">About <em>This Restaurant</em></h2>
                <p style="font-size:0.95rem;color:var(--ink-soft);line-height:1.7;margin:0;">This is where an owner-written introduction sits. On a real claimed listing it replaces the generic one-line summary, and it is the difference between a page a diner scrolls past and one they read to the end.</p>
            </div>

            <div class="card">
                <h2 class="card-title">Amenities <em>&amp; Features</em></h2>
                <div class="feature-tags">
                    <span class="feature-tag"><i class="fas fa-check"></i> Family run</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Vegetarian options</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Vegan options</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Takeaway</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Wheelchair accessible</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Dog friendly</span>
                    <span class="feature-tag"><i class="fas fa-check"></i> Card payments</span>
                </div>
            </div>

        </div>

        <aside class="sidebar-col">

            <div class="claimed-badge-card">
                <div class="tick"><i class="fas fa-check-circle"></i></div>
                <h3>Owner Verified &#10003;</h3>
                <p>This listing is managed by the restaurant owner.</p>
            </div>

            <div class="cta-card">
                <h3>Own a Thai restaurant?</h3>
                <p>Find your listing and claim it free. It takes a couple of minutes and you control what appears on the page.</p>
                <a href="/claim/?src=demo" class="cta-btn">Claim My Restaurant Listing <i class="fas fa-arrow-right"></i></a>
                <p class="cta-note">Free. No card details. You can edit or remove your details at any time.</p>
            </div>

            <div class="card">
                <h2 class="card-title" style="font-size:1.05rem;">Price <em>Range</em></h2>
                <div style="font-size:1.5rem;color:var(--ink);font-weight:600;text-align:center;padding:4px 0;">££</div>
                <p style="font-size:0.8rem;color:var(--ink-mute);text-align:center;margin:4px 0 0;">Typical spend per person</p>
            </div>

            <div class="card">
                <h2 class="card-title" style="font-size:1.05rem;">Contact <em>Details</em></h2>
                <div style="color:var(--ink-soft);font-size:0.9rem;line-height:2;">
                    <div><i class="fas fa-globe" style="color:var(--brand);width:20px;margin-right:6px;"></i> example-restaurant.co.uk</div>
                    <div><i class="fas fa-phone" style="color:var(--brand);width:20px;margin-right:6px;"></i> 0113 000 0000</div>
                    <div><i class="fas fa-envelope" style="color:var(--brand);width:20px;margin-right:6px;"></i> hello@example-restaurant.co.uk</div>
                </div>
            </div>

            <div class="card">
                <h2 class="card-title" style="font-size:1.05rem;">At a <em>Glance</em></h2>
                <ul class="trust-list">
                    <li class="trust-item"><i class="fas fa-shield-check"></i><div><strong>FSA Verified</strong>Government inspection data</div></li>
                    <li class="trust-item"><i class="fas fa-utensils"></i><div><strong>Thai Cuisine</strong>Authentic flavours</div></li>
                    <li class="trust-item"><i class="fas fa-map-pin"></i><div><strong>Leeds</strong>UK</div></li>
                    <li class="trust-item"><i class="fas fa-calendar-check"></i><div><strong>Owner Managed</strong>Details kept up to date</div></li>
                </ul>
            </div>

        </aside>
    </div>

    <div class="related">
        <div class="related-inner">
            <a href="/claim/"><i class="fas fa-arrow-left"></i> Claim your listing</a>
            <a href="/r/"><i class="fas fa-arrow-left"></i> Browse all Thai restaurants by city</a>
        </div>
    </div>

    <footer class="site-footer">
        <p>Data sourced from the <a href="https://ratings.food.gov.uk" target="_blank" rel="noopener">Food Standards Agency</a></p>
        <p style="margin-top: 8px;"><a href="/data-quality">Data Quality</a> · <a href="/sitemap.xml">Sitemap</a></p>
        <p style="margin-top: 8px;">This page is a sample and is excluded from search engines.</p>
    </footer>

</body>
</html>
`;

/**
 * Inject claimed listing enrichment into restaurant page HTML.
 * Extracts restaurant name + city from existing JSON-LD, queries D1,
 * enriches the Restaurant schema and adds a Quick Facts card.
 * Returns original HTML unchanged if no claimed data found or on any error.
 */
async function injectClaimedEnrichment(html, env) {
  if (!env.DB) return html;  // No D1 binding — skip

  // 1. Extract restaurant name + city from existing JSON-LD
  const ldMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  if (!ldMatch) return html;

  let ld;
  try { ld = JSON.parse(ldMatch[1]); } catch (_) { return html; }

  // Find the Restaurant object (handles both array and single-object formats)
  const schemas = Array.isArray(ld) ? ld : [ld];
  const restaurant = schemas.find(s => s['@type'] === 'Restaurant');
  if (!restaurant) return html;

  const name = restaurant.name;
  const city = restaurant.address?.addressLocality;
  if (!name || !city) return html;

  // Google rating lifted from build-time schema (visible on claimed pages only)
  const agg = restaurant.aggregateRating || {};
  const ratingValue = typeof agg.ratingValue === 'number' ? agg.ratingValue : parseFloat(agg.ratingValue);
  const reviewCount = agg.reviewCount ? parseInt(agg.reviewCount, 10) : null;
  const hasRating = Number.isFinite(ratingValue) && ratingValue > 0;

  // 2. Query D1 for claimed listing enrichment
  let listing;
  try {
    listing = await env.DB.prepare(
      'SELECT l.cuisine_specialty, l.features, l.price_range, l.opening_hours, l.website, l.description, l.phone, l.photos FROM listings l JOIN claims c ON l.claim_id = c.id WHERE l.restaurant_name = ? AND l.city = ? AND c.claim_status = ?'
    ).bind(name, city, 'approved').first();
  } catch (_) { return html; }

  if (!listing) return html;

  // Parse owner photos (stored as JSON string or array by /api/upload)
  let photoUrls = [];
  if (listing.photos) {
    if (typeof listing.photos === 'string') {
      try { photoUrls = JSON.parse(listing.photos); } catch (_) { photoUrls = []; }
    } else if (Array.isArray(listing.photos)) {
      photoUrls = listing.photos;
    }
  }
  // Allowlist: only Cloudflare Images delivery URLs (stored by our own /api/upload).
  // Anything else is rejected — prevents script-tag breakout and external hotlinking.
  photoUrls = photoUrls.filter(u => u.startsWith('https://imagedelivery.net/'));

  // 3. Enrich the JSON-LD Restaurant schema
  if (listing.description) {
    restaurant.description = listing.description;
  }
  if (listing.cuisine_specialty) {
    restaurant.servesCuisine = listing.cuisine_specialty;
  }
  if (listing.price_range) {
    restaurant.priceRange = listing.price_range;
  }
  if (listing.phone) {
    restaurant.telephone = listing.phone;
  }
  if (listing.opening_hours) {
    try {
      restaurant.openingHours = listing.opening_hours;
    } catch (_) {}
  }
  if (listing.website) {
    try {
      restaurant.sameAs = restaurant.sameAs || [];
      if (!restaurant.sameAs.includes(listing.website)) {
        restaurant.sameAs.push(listing.website);
      }
    } catch (_) {}
  }
  if (photoUrls.length > 0) {
    restaurant.image = photoUrls;
  }

  // Replace the JSON-LD block with enriched version
  const ldBlock = ldMatch[0];
  // Escape '</' so no JSON string can terminate the surrounding <script> element
  const enrichedLd = JSON.stringify(ld).replace(/<\//g, '<\\/');
  html = html.replace(ldBlock, '<script type="application/ld+json">' + enrichedLd + '</script>');

  // 4. Build Quick Facts HTML card
  const facts = [];
  if (hasRating) {
    // Visible rating on claimed pages only — with Google attribution (Maps ToS 3.2.3(a))
    const mapsUrl = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(name + ' ' + city);
    const stars = Math.min(5, Math.max(0, Math.round(ratingValue)));
    const countText = reviewCount ? ' · ' + reviewCount.toLocaleString('en-GB') + ' reviews' : '';
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Google rating</span><span class="qf-value" style="font-weight:600;color:var(--ink2, #1f2937);">' + '★'.repeat(stars) + ' ' + htmlEscape(String(ratingValue)) + '<span style="font-weight:400;color:var(--ink4, #6b7280);">' + htmlEscape(countText) + '</span></span></div>');
    facts.push('<div style="padding-top:4px;font-size:0.7rem;color:var(--ink4, #6b7280);"><a href="' + htmlEscape(mapsUrl) + '" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;">Data from Google</a></div>');
  }
  if (listing.cuisine_specialty) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Cuisine</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);">' + htmlEscape(listing.cuisine_specialty) + '</span></div>');
  }
  if (listing.features) {
    let feats = listing.features;
    if (typeof feats === 'string') {
      try { feats = JSON.parse(feats); } catch (_) { feats = [feats]; }
    }
    if (Array.isArray(feats) && feats.length > 0) {
      facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);flex-shrink:0;padding-top:1px;">Features</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);text-align:right;">' + feats.map(f => htmlEscape(f)).join('<br>') + '</span></div>');
    }
  }
  if (listing.price_range) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Price</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);">' + htmlEscape(listing.price_range) + '</span></div>');
  }
  if (listing.opening_hours) {
    const hours = Array.isArray(listing.opening_hours) ? listing.opening_hours : [listing.opening_hours];
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);flex-shrink:0;">Hours</span><span class="qf-value" style="font-weight:500;color:var(--ink2, #1f2937);text-align:right;">' + htmlEscape(hours.join('<br>')) + '</span></div>');
  }
  if (listing.website) {
    facts.push('<div class="qf-item" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--ink1, #e5e7eb);"><span class="qf-label" style="font-size:0.85rem;color:var(--ink4, #6b7280);">Website</span><span class="qf-value" style="font-weight:500;"><a href="' + htmlEscape(listing.website) + '" target="_blank" rel="noopener" style="color:var(--accent, #A3132B);text-decoration:none;">Visit →</a></span></div>');
  }
  if (listing.description) {
    facts.push('<div class="qf-desc" style="padding-top:8px;font-size:0.9rem;color:var(--ink3, #374151);line-height:1.6;">' + htmlEscape(listing.description) + '</div>');
  }

  // 5. Build injected HTML: Quick Facts card + owner photo gallery
  let injection = '';
  if (facts.length > 0) {
    injection += '\n            <!-- Quick Facts (server-injected from claimed listing) -->\n            <div id="quick-facts" class="card" style="margin-bottom:24px;">\n                <h3 style="margin:0 0 16px;font-weight:600;">Quick Facts</h3>\n                ' + facts.join('\n                ') + '\n            </div>\n';
  }

  if (photoUrls.length > 0) {
    // CF Images flexible variants: stored URL is /{id}/public → swap for /w=400, /w=800
    const imgs = photoUrls.slice(0, 12).map((u, i) => {
      const base = u.replace(/\/public$/, '');
      const w400 = base + '/w=400';
      const w800 = base + '/w=800';
      return '<img src="' + htmlEscape(w400) + '" srcset="' + htmlEscape(w400) + ' 400w, ' + htmlEscape(w800) + ' 800w" sizes="(max-width: 640px) 100vw, 300px" alt="Owner photo ' + (i + 1) + '" loading="lazy" decoding="async" style="width:100%;height:auto;border-radius:10px;aspect-ratio:4/3;object-fit:cover;display:block;">';
    }).join('');
    injection += '\n            <!-- Owner Photos (server-injected) -->\n            <div id="owner-photos" class="card" style="margin-bottom:24px;">\n                <h3 style="margin:0 0 16px;font-weight:600;">Photos</h3>\n                <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));gap:10px;">' + imgs + '</div>\n            </div>\n';
  }

  if (injection) {
    // Claimed pages with data: Quick Facts already carries contact info,
    // so drop the static hero contact strip to avoid duplication.
    if (facts.length > 0) {
      html = html.replace(/<div class="contact-strip" id="contact-strip"[^>]*>[\s\S]*?<\/div>/, '');
    }
    // Inject before Trust Sidebar anchor
    if (html.includes('<!-- Trust Sidebar -->')) {
      html = html.replace('<!-- Trust Sidebar -->', injection + '            <!-- Trust Sidebar -->');
    } else {
      // Fallback: inject before Schema: Restaurant (visible anchor always present)
      html = html.replace('<!-- Schema: Restaurant -->', injection + '    <!-- Schema: Restaurant -->');
    }
  }

  return html;
}

/**
 * Inject a "Full Menu" call-to-action when the restaurant has a generated menu page.
 *
 * Menu pages are produced by scripts/build_menu_page.py and carry a
 * name="thaidata-page" marker meta tag. We cannot trust ASSETS.fetch() returning ok,
 * because Pages answers unmatched paths with the homepage and HTTP 200. If no menu
 * page exists the HTML is returned unchanged, so this is a no-op for the other
 * ~1,263 restaurants until their menus are generated.
 */
async function injectMenuLink(html, city, name, origin, env) {
  if (!env.ASSETS) return html;

  const menuPath = '/r/' + city + '/' + name + '/menu/';
  let res;
  try {
    res = await env.ASSETS.fetch(new URL(menuPath, origin).toString());
  } catch (_) {
    return html;  // asset layer unavailable — serve the page untouched
  }
  if (!res || !res.ok) return html;

  let menuHtml;
  try { menuHtml = await res.text(); } catch (_) { return html; }
  if (!menuHtml.includes('name="thaidata-page"')) return html;

  // Dish count from the Menu schema so the CTA can be specific rather than vague.
  let count = 0;
  try {
    const ld = menuHtml.match(/<script type="application\/ld\+json">(\{"@context":"https:\/\/schema\.org","@type":"Menu"[\s\S]*?)<\/script>/);
    if (ld) {
      const menu = JSON.parse(ld[1]);
      count = (menu.hasMenuSection || []).reduce((n, s) => n + (s.hasMenuItem || []).length, 0);
    }
  } catch (_) {}

  const blurb = count
    ? htmlEscape(String(count)) + ' dishes &middot; every dish with prices, taken from the restaurant&rsquo;s own menu.'
    : 'Every dish with prices, taken from the restaurant&rsquo;s own menu.';

  const card =
    '\n                <!-- Full Menu CTA (server-injected) -->\n'
    + '                <div class="card" id="full-menu-cta" style="margin-bottom:24px;border-color:#A7F3D0;background:linear-gradient(180deg,#F0FDF9,#FFFFFF);">\n'
    + '                    <h2 class="card-title" style="margin-top:0;">Full <em>Menu</em></h2>\n'
    + '                    <p style="margin:6px 0 14px;color:var(--ink-secondary,#6B7280);font-size:0.9rem;">' + blurb + '</p>\n'
    + '                    <a href="' + htmlEscape(menuPath) + '" style="display:inline-block;background:#A3132B;color:#fff;text-decoration:none;font-weight:600;padding:10px 20px;border-radius:999px;font-size:0.9rem;">View the full menu &rarr;</a>\n'
    + '                </div>\n';

  if (html.includes('<!-- === HYGIENE RATING === -->')) {
    return html.replace('<!-- === HYGIENE RATING === -->', card + '                <!-- === HYGIENE RATING === -->');
  }
  if (html.includes('<!-- ============ MAIN CONTENT ============ -->')) {
    return html.replace('<!-- ============ MAIN CONTENT ============ -->', '<!-- ============ MAIN CONTENT ============ -->' + card);
  }
  return html;
}

/**
 * Menu staleness flag — a read date older than STALE_MENU_DAYS gets a notice.
 * The builder stamps the read date into Menu schema dateModified; computing the
 * age per request means old pages are flagged without waiting for a rebuild.
 */
const STALE_MENU_DAYS = 90;

function injectStaleMenuNotice(html) {
  const m = html.match(/"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"/);
  if (!m) return html;
  const readMs = Date.parse(m[1] + 'T00:00:00Z');
  if (!Number.isFinite(readMs)) return html;
  if ((Date.now() - readMs) / 86400000 <= STALE_MENU_DAYS) return html;
  const human = new Date(readMs).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
  const notice =
    '\n  <div class="notice" id="menu-stale" style="border-color:#E7B45A;background:#FFF8EC;">\n'
    + '    This menu was read on ' + human + ' &mdash; it may have changed since. Please confirm prices and dishes with the restaurant before ordering.\n'
    + '  </div>';
  if (html.includes('<main class="wrap">')) {
    return html.replace('<main class="wrap">', '<main class="wrap">' + notice);
  }
  return html;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);
  const segments = url.pathname.replace(/\/$/, '').split('/').filter(Boolean);

  // Sample claimed listing shown from the claim flow.
  // Served from here rather than its own functions/r/demo/ middleware: a nested
  // _middleware.js under an existing one did not get its own route (probed —
  // still 404 with /r/* explicitly listed in _routes.json), so this file owns
  // the path. Static by design — it shows the claimed state (photos, menu,
  // features) that injectClaimedEnrichment only adds for a real approved claim.
  if (url.pathname === '/r/demo/claimed-listing/') {
    return new Response(DEMO_LISTING_HTML, {
      status: 200,
      headers: {
        'content-type': 'text/html; charset=utf-8',
        'cache-control': 'public, max-age=300',
      },
    });
  }

  // Only intercept /r/{city}/{name} (3+ path segments)
  // Pass through for /r/ (hub) and /r/{city} (city pages)
  if (segments.length < 3 || segments[0] !== 'r') {
    return next();
  }

  // Enforce trailing slash on restaurant detail pages (3+ segments).
  // Cloudflare Pages serves index.html at both /r/city/slug and /r/city/slug/,
  // creating duplicate URLs. Canonical tags use trailing-slash form — redirect
  // the bare version so Google only indexes one URL per restaurant.
  if (!url.pathname.endsWith('/')) {
    return new Response(null, {
      status: 301,
      headers: { 'Location': url.pathname + '/' + url.search },
    });
  }

  // Nested restaurant sub-pages, e.g. /r/{city}/{name}/menu/.
  // These are real static files generated by scripts/build_menu_page.py, never
  // the SPA fallback. We can't just trust `ASSETS.fetch` returning ok, because
  // Pages answers unmatched paths with the homepage and HTTP 200 — so we look
  // for the generator's marker meta tag before serving.
  if (segments.length > 3) {
    const nested = await env.ASSETS.fetch(url.toString());
    if (nested.ok) {
      const nestedText = await nested.clone().text();
      if (nestedText.includes('name="thaidata-page"')) {
        let nestedOut = nestedText;
        if (segments[3] === 'menu') {
          try {
            nestedOut = injectStaleMenuNotice(nestedText);
          } catch (e) {
            console.warn('Stale menu notice failed:', e.message);
          }
        }
        return new Response(nestedOut, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            'cache-control': 'public, max-age=3600',
          },
        });
      }
    }
  }

  const city = segments[1];
  const name = segments.slice(2).join('/');

  try {
    // Try to serve the static file. If it's a real page (has "Hygiene" marker),
    // return it directly — no alias resolution needed.
    const { ASSETS } = env;
    const assetResponse = await ASSETS.fetch(url.toString());

    if (assetResponse.ok) {
      const text = await assetResponse.clone().text();
      // Real restaurant pages contain "FSA X/5 Hygiene Rating" (from Kimi template)
      // The SPA fallback (homepage) does NOT have "Hygiene" anywhere
      if (text.includes('Hygiene')) {
        // This is a real restaurant page — serve from static assets
        // Inject claimed listing enrichment for AEO/SEO visibility
        let enrichedText = text;
        try {
          enrichedText = await injectClaimedEnrichment(text, env);
        } catch (e) {
          // D1 failure or parse error — serve original page unchanged
          console.warn('Enrichment injection failed:', e.message);
        }
        // Link to the generated full menu page, when one exists for this venue.
        try {
          enrichedText = await injectMenuLink(enrichedText, city, name, url.origin, env);
        } catch (e) {
          console.warn('Menu link injection failed:', e.message);
        }
        return new Response(enrichedText, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            'cache-control': 'public, max-age=3600',
          },
        });
      }
    }

    // No static page at this URL — the request hit the SPA fallback.
    // Check curated alias list before returning 404.
    let aliasData;
    try {
      const aliasesRes = await fetch('https://thaidata.uk/data/r-aliases.json');
      if (aliasesRes.ok) {
        aliasData = await aliasesRes.json();
      }
    } catch (_) {} // fetch error — treat as no aliases available

    if (aliasData) {
      const aliasList = aliasData.aliases || [];
      const aliasSlug = name.toLowerCase().replace(/[-\s]+/g, '-').replace(/^-+|-+$/g, '');
      const aliasCity = city.toLowerCase();

      const match = aliasList.find(a =>
        a.slug === aliasSlug && a.city.toLowerCase() === aliasCity
      );

      if (match) {
        const redirectCity = match.target_city || match.city;
        const correctUrl = pageUrl(match.canonical, redirectCity);
        return new Response(null, {
          status: 301,
          headers: { 'Location': correctUrl },
        });
      }
    }

    // Claim-specific 404 (?source=claim) — helpful state for first-time claimants
    const isClaimSource = url.searchParams.get('source') === 'claim';

    // Venue no longer in the dataset (delisted, excluded or renamed): redirect
    // to the city page instead of 404ing. Dropped venues used to leave dead
    // URLs behind; a 301 keeps inbound links and crawl equity working and
    // covers every future drop automatically. Claimant deep-links keep the
    // helpful "page not ready" 404 below.
    if (!isClaimSource) {
      try {
        const cityRes = await env.ASSETS.fetch(new URL('/cities/' + city, url.origin).toString());
        if (cityRes.ok) {
          const cityText = await cityRes.clone().text();
          // Pages answers unmatched paths with the homepage + 200, so require
          // the city page's own canonical before trusting the response.
          if (cityText.includes('rel="canonical" href="https://thaidata.uk/cities/' + city + '"')) {
            return new Response(null, {
              status: 301,
              headers: { 'Location': '/cities/' + city },
            });
          }
        }
      } catch (_) {
        // Asset layer unavailable — fall through to the 404 below.
      }
    }

    if (isClaimSource) {
      const claimSubject = 'Claim help: ' + url.pathname;
      return new Response(
        '<!DOCTYPE html><html lang="en"><head><title>Claimed Listing — ThaiData</title>'
        + '<meta name="robots" content="noindex"><style>body{font-family:sans-serif;'
        + 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;'
        + 'background:#FBF7F0;color:#1A1614;text-align:center;padding:20px;}'
        + 'h1{font-size:2.5rem;margin-bottom:16px;}'
        + 'p{color:#94A3B8;line-height:1.6;margin:8px 0;}'
        + '.actions{margin-top:32px;display:flex;flex-direction:column;align-items:center;gap:16px;}'
        + '.btn{display:inline-block;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:600;}'
        + '.btn-primary{background:#A3132B;color:white;}'
        + '.btn-primary:hover{background:#7E0E20;}'
        + '.btn-secondary{color:#A3132B;text-decoration:underline;font-size:0.9rem;}'
        + '</style></head><body><div>'
        + '<h1>Page not ready yet</h1>'
        + '<p>You\'ve claimed this restaurant listing, but the public page hasn\'t been generated yet.</p>'
        + '<p>It will go live once your claim is approved and the listing is set up in our system.</p>'
        + '<div class="actions">'
        + '<a href="/admin/" class="btn btn-primary">Manage my claim</a>'
        + '<a href="mailto:hello@thaidata.uk?subject=' + encodeURIComponent(claimSubject) + '" class="btn-secondary">Contact ThaiData &rarr;</a>'
        + '</div></div></body></html>',
        {
          status: 404,
          headers: { 'content-type': 'text/html; charset=utf-8' },
        }
      );
    }

    // Standard 404 — concise, minimal, for general users
    return new Response(
      '<!DOCTYPE html><html lang="en"><head><title>Not Found — ThaiData</title>'
      + '<meta name="robots" content="noindex"><style>body{font-family:sans-serif;'
      + 'display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'
      + 'background:#FBF7F0;color:#1A1614;text-align:center;}'
      + 'h1{font-size:3rem;margin-bottom:8px;opacity:0.5;}p{color:#94A3B8;}'
      + 'a{color:#A3132B;}</style></head><body><div><h1>404</h1>'
      + '<p>Restaurant not found in our directory.</p>'
      + '<p><a href="/">thaidata.uk</a></p></div></body></html>',
      {
        status: 404,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      }
    );

  } catch (err) {
    console.error('/r/ middleware error:', err.message);
    return next();
  }
}

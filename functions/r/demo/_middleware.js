// ThaiData UK — /r/demo/ middleware
//
// Serves a fully-formed "example claimed listing" preview so prospective owners
// can see what a claimed listing looks like before they claim.
//
// On-demand image generation: api.cloudflare.com/client/v4/accounts/<id>/images/v1
// requests the ACCOUNT-scoped API token. If that token is account-scoped we would
// be embedding a credential with write access to every Cloudflare resource in the
// account inside a public static renderer. We therefore refuse to generate images
// at runtime and the demo page uses inline SVG placeholders instead.

const HTML = `<!DOCTYPE html>
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
    <link rel="icon" type="image/svg+xml" href="/elephant-icon.svg">
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
                <img src="/elephant-icon.svg" alt="" width="32" height="32" style="width:32px;height:32px;">
                ThaiData
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

export async function onRequest(context) {
  const { request, next } = context;
  const url = new URL(request.url);

  // Only handle the demo listing itself; everything else falls through.
  if (url.pathname !== '/r/demo/claimed-listing/') {
    return next();
  }

  return new Response(HTML, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      // Short cache so edits to this file show up quickly.
      'cache-control': 'public, max-age=300',
    },
  });
}

#!/usr/bin/env python3
"""
Generate individual restaurant listing pages from restaurants.json.
Output: /r/[city-slug]/[restaurant-slug]/index.html
"""
import json, os, re, sys
from datetime import datetime

REPO = '/tmp/thaidata-repo'
OUT_DIR = os.path.join(REPO, 'r')

def slugify(s):
    """Convert a string to URL-safe slug"""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

def format_date(datestr):
    """'2025-11-25T00:00:00' → 'November 2025'"""
    if not datestr: return 'Unknown'
    try:
        dt = datetime.fromisoformat(datestr.replace('Z', '+00:00'))
        return dt.strftime('%B %Y')
    except:
        return datestr[:7] if len(datestr) >= 7 else datestr

def score_bar(score):
    """FSA 0-25 (lower=better) → width% and color class"""
    if score is None: return None, None
    # Invert: 0 → 100%, 25 → 0%
    pct = max(0, min(100, (25 - score) / 25 * 100))
    if score <= 10:
        cls = 'good'
    elif score <= 20:
        cls = 'ok'
    else:
        cls = 'bad'
    return round(pct), cls

def score_label(score):
    """Human-readable score label"""
    if score is None: return '—'
    if score <= 5: return f'{score} <span style="color:var(--c2);">(excellent)</span>'
    if score <= 10: return f'{score} <span style="color:var(--c2);">(good)</span>'
    if score <= 15: return f'{score} <span style="color:var(--amber);">(fair)</span>'
    if score <= 20: return f'{score} <span style="color:var(--amber);">(needs work)</span>'
    return f'{score} <span style="color:var(--red);">(poor)</span>'

def rating_class(rating):
    """CSS class for rating badge"""
    return {'5': 'max', '4': 'high', '3': 'mid', '2': 'low', '1': 'low'}.get(rating, 'mid')

def rating_label(rating):
    return {'5': 'Very Good', '4': 'Good', '3': 'Generally Satisfactory', '2': 'Improvement Necessary', '1': 'Major Improvement Necessary'}.get(rating, 'Rated')

def generate_page(r):
    """Generate HTML for a single restaurant"""
    name = r['name']
    city = r['city']
    city_slug = slugify(city)
    rest_slug = slugify(name)
    fsa_id = r['id']
    rtype = r['type']
    rating = r.get('hygiene_rating', 'N/A')
    postcode = r.get('postcode', '')
    address = r.get('address', '')
    lat = r.get('latitude')
    lng = r.get('longitude')
    authority = r.get('local_authority', city)
    region = r.get('region', '')
    date_str = format_date(r.get('rating_date', ''))
    
    hy_score = r.get('hygiene_score')
    st_score = r.get('structural_score')
    mg_score = r.get('management_score')
    has_details = hy_score is not None or st_score is not None or mg_score is not None

    # Type badge
    type_icon = 'fa-utensils' if rtype == 'restaurant' else 'fa-box'
    type_label = rtype.replace('_', ' ').title()

    # Map link
    map_html = ''
    if lat is not None and lng is not None:
        map_html = f'<a class="map-link" href="https://www.google.com/maps?q={lat},{lng}" target="_blank" rel="noopener"><i class="fas fa-map"></i> View on Google Maps</a>'

    # Score bars HTML
    scores_html = ''
    if has_details:
        scores_html = '<div style="margin-top:20px;">'
        for field, label_text in [('hygiene_score', 'Hygiene'), ('structural_score', 'Structural'), ('management_score', 'Management')]:
            val = r.get(field)
            if val is not None:
                pct, cls = score_bar(val)
                scores_html += f'''
            <div class="score-row">
                <span class="score-label">{label_text}</span>
                <div class="score-bar-bg"><div class="score-bar-fill {cls}" style="width:{pct}%"></div></div>
                <span class="score-num">{score_label(val)}</span>
            </div>'''
        scores_html += '\n<p style="color:var(--ink3);font-size:0.75rem;margin-top:12px;">Scores from the Food Standards Agency. 0–25 scale — lower is better.</p>'
        scores_html += '</div>'

    # Page title
    title = f'{name}, {city} — FSA {rating}/5 Hygiene Rating | ThaiData'
    desc = f'{name} in {city}: FSA {rating}/5 hygiene rating. {type_label}.{ " " + address + "." if address else "" } View inspection scores and claim this listing.'

    # Canonical
    canonical = f'https://thaidata.uk/r/{city_slug}/{rest_slug}/'

    html = f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{desc}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical}">

    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{name}, {city} — FSA {rating}/5 | ThaiData">
    <meta property="og:description" content="FSA {rating}/5 hygiene rating. {type_label} in {city}. View inspection scores and claim this listing.">
    <meta property="og:locale" content="en_GB">

    <link rel="icon" type="image/svg+xml" href="/logo-icon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <style>
        :root {{ --c1: #0A7A6F; --c2: #10B981; --dark: #0C1220; --ink: #0F172A; --ink2: #334155; --ink3: #64748B; --ink4: #94A3B8; --line: rgba(255,255,255,0.1); --bg: #0C1220; --amber: #F59E0B; --red: #EF4444; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: white; background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("https://grainy-gradients.vercel.app/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        img, svg {{ max-width: 100%; height: auto; }}
        .wrap {{ max-width: 720px; margin: 0 auto; padding: 0 20px; }}

        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 720px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; position: relative; }}
        .logo {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.3rem; color: white; text-decoration: none; }}
        .logo-icon {{ height: 32px; width: auto; }}
        .hamburger {{ display: none; background: none; border: none; color: white; font-size: 1.5rem; cursor: pointer; }}
        .nav-links {{ display: flex; gap: 20px; align-items: center; }}
        .nav-links a {{ color: var(--ink4); text-decoration: none; font-size: 0.85rem; transition: color 0.2s; }}
        .nav-links a:hover {{ color: white; }}
        @media(max-width:768px) {{
            .hamburger {{ display: block; }}
            .nav-links {{ display: none; position: absolute; top: 72px; left: 0; right: 0; background: var(--dark); border-bottom: 1px solid var(--line); flex-direction: column; padding: 16px 20px; gap: 14px; }}
            .nav-links.open {{ display: flex; }}
        }}

        .breadcrumb {{ padding: 16px 0 0; color: var(--ink4); font-size: 0.8rem; }}
        .breadcrumb a {{ color: var(--ink4); text-decoration: none; }}
        .breadcrumb a:hover {{ color: white; }}
        .breadcrumb span {{ color: var(--ink3); }}

        .hero {{ padding: 40px 0 30px; }}
        .hero .badge-row {{ display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }}
        .hero .badge {{ display: inline-flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }}
        .badge.r5 {{ background: #1a3a2a; color: var(--c2); }}
        .badge.r4 {{ background: #1a3a2a; color: #84cc16; }}
        .badge.r3 {{ background: #3a3a1a; color: var(--amber); }}
        .badge.r2, .badge.r1 {{ background: #3a1a1a; color: var(--red); }}
        .badge.type {{ background: rgba(255,255,255,0.04); color: var(--ink4); border: 1px solid var(--line); }}

        .hero h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(2rem, 5vw, 2.6rem); font-weight: 400; line-height: 1.15; margin-bottom: 6px; }}
        .hero h1 em {{ font-style: italic; color: var(--c2); }}
        .hero .location {{ color: var(--ink4); font-size: 1rem; margin-bottom: 4px; }}

        .card {{ background: rgba(255,255,255,0.02); border: 1px solid var(--line); border-radius: 16px; padding: 28px 32px; margin: 20px 0; }}
        .card h2 {{ font-family: 'Instrument Serif', serif; font-size: 1.5rem; font-weight: 400; margin-bottom: 18px; }}
        .card h2 em {{ font-style: italic; color: var(--c2); }}

        .rating-hero {{ display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }}
        .rating-circle {{ width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 3px solid var(--line); }}
        .rating-circle .stars {{ font-family: 'Instrument Serif', serif; font-size: 2rem; color: var(--ink3); line-height: 1; }}
        .rating-circle.max {{ border-color: var(--c2); background: rgba(16,185,129,0.08); }}
        .rating-circle.max .stars {{ color: var(--c2); }}
        .rating-circle.high {{ border-color: #84cc16; background: rgba(132,204,22,0.06); }}
        .rating-circle.high .stars {{ color: #84cc16; }}
        .rating-circle.mid {{ border-color: var(--amber); background: rgba(245,158,11,0.06); }}
        .rating-circle.mid .stars {{ color: var(--amber); }}
        .rating-circle.low {{ border-color: var(--red); background: rgba(239,68,68,0.06); }}
        .rating-circle.low .stars {{ color: var(--red); }}
        .rating-meta {{ color: var(--ink4); font-size: 0.85rem; line-height: 1.6; }}

        .score-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }}
        .score-label {{ width: 100px; color: var(--ink4); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; flex-shrink: 0; }}
        .score-bar-bg {{ flex: 1; min-width: 80px; height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }}
        .score-bar-fill {{ height: 100%; border-radius: 4px; }}
        .score-bar-fill.good {{ background: var(--c2); }}
        .score-bar-fill.ok {{ background: var(--amber); }}
        .score-bar-fill.bad {{ background: var(--red); }}
        .score-num {{ font-size: 0.78rem; color: var(--ink3); white-space: nowrap; }}

        .address-block {{ display: flex; gap: 16px; }}
        .address-block i {{ color: var(--c2); font-size: 1.1rem; margin-top: 3px; flex-shrink: 0; }}
        .addr {{ color: var(--ink4); font-size: 0.95rem; line-height: 1.7; }}
        .addr strong {{ color: white; }}

        .map-link {{ display: inline-flex; align-items: center; gap: 8px; color: var(--c2); text-decoration: none; font-size: 0.9rem; font-weight: 500; margin-top: 14px; }}
        .map-link:hover {{ text-decoration: underline; }}

        .claim-card {{ background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.2); border-radius: 16px; padding: 28px 32px; margin: 30px 0; text-align: center; }}
        .claim-card h2 {{ font-family: 'Instrument Serif', serif; font-size: 1.4rem; font-weight: 400; margin-bottom: 8px; color: white; }}
        .claim-card p {{ color: var(--ink4); font-size: 0.9rem; margin-bottom: 18px; }}
        .claim-card .btn {{ display: inline-block; background: var(--c2); color: white; padding: 12px 28px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 0.95rem; transition: background 0.2s; }}
        .claim-card .btn:hover {{ background: var(--c1); }}

        .related {{ margin: 30px 0; padding: 20px 0; border-top: 1px solid var(--line); }}
        .related h3 {{ font-family: 'Instrument Serif', serif; font-size: 1.2rem; font-weight: 400; margin-bottom: 12px; }}
        .related a {{ color: var(--c2); text-decoration: none; font-size: 0.9rem; }}
        .related a:hover {{ text-decoration: underline; }}

        footer {{ text-align: center; padding: 30px 0 50px; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.8rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: white; }}
    </style>

    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": "{name}",
        "description": "{name} is a {type_label.lower()} in {city} with a {rating}/5 FSA hygiene rating.",
        "servesCuisine": "Thai",
        "address": {{
            "@type": "PostalAddress",
            "streetAddress": "{address}",
            "addressLocality": "{city}",
            "postalCode": "{postcode}",
            "addressCountry": "GB"
        }},
        {f'"geo": {{"@type": "GeoCoordinates", "latitude": {lat}, "longitude": {lng}}},' if lat and lng else ''}
        "aggregateRating": {{
            "@type": "AggregateRating",
            "ratingValue": "{rating}",
            "bestRating": "5",
            "ratingCount": "1",
            "reviewAspect": "Hygiene"
        }}
    }}
    </script>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/"}},
            {{"@type": "ListItem", "position": 2, "name": "{city}", "item": "https://thaidata.uk/cities/{city_slug}"}},
            {{"@type": "ListItem", "position": 3, "name": "{name}"}}
        ]
    }}
    </script>
</head>
<body>
    <div class="grain"></div>

    <nav>
        <div class="nav-bar">
            <a href="/index.html" class="logo"><img src="/logo-horizontal.svg" alt="ThaiData" class="logo-icon" width="100" height="36"></a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Menu">&#9776;</button>
            <div class="nav-links">
                <a href="/cities/{city_slug}">← {city}</a>
                <a href="/thai-restaurants-city-breakdown-uk">All Cities</a>
                <a href="/claim/">List Your Restaurant</a>
            </div>
        </div>
    </nav>

    <div class="wrap">

        <div class="breadcrumb">
            <a href="/">Home</a> › 
            <a href="/cities/{city_slug}">{city}</a> › 
            <span>{name}</span>
        </div>

        <div class="hero">
            <div class="badge-row">
                <span class="badge r{rating}"><i class="fas fa-star"></i> FSA {rating}/5</span>
                <span class="badge type"><i class="fas {type_icon}"></i> {type_label}</span>
            </div>
            <h1>{name}</h1>
            <div class="location"><i class="fas fa-map-marker-alt"></i> {city}{', ' + region if region else ''}</div>
        </div>

        <div class="card">
            <h2>FSA <em>Hygiene Rating</em></h2>
            <div class="rating-hero">
                <div class="rating-circle {rating_class(rating)}">
                    <span class="stars">{rating}</span>
                </div>
                <div class="rating-meta">
                    <strong style="font-size:1.1rem;">{rating_label(rating)}</strong><br>
                    Last inspected: {date_str}<br>
                    <span style="color:var(--ink3);">Local authority: {authority}</span>
                </div>
            </div>
            {scores_html}
        </div>

        <div class="card">
            <h2>Location</h2>
            <div class="address-block">
                <i class="fas fa-location-dot"></i>
                <div class="addr">
                    <strong>{name}</strong><br>
                    {address}<br>
                    {city}<br>
                    {postcode}
                </div>
            </div>
            {map_html}
        </div>

        <div class="claim-card">
            <h2>Own this restaurant?</h2>
            <p>Claim your free listing to add photos, opening hours, menu links, and more.</p>
            <a href="/claim/" class="btn">Claim This Listing <i class="fas fa-arrow-right" style="margin-left:6px;"></i></a>
        </div>

        <div class="related">
            <h3>Related</h3>
            <p>
                <a href="/cities/{city_slug}">← All Thai restaurants in {city}</a><br>
                <a href="/thai-restaurants-city-breakdown-uk">← All UK cities</a>
            </p>
        </div>

    </div>

    <footer>
        <p>Data sourced from the <a href="https://ratings.food.gov.uk" target="_blank" rel="noopener">Food Standards Agency</a>. Last updated June 2026.</p>
        <p style="margin-top:6px;"><a href="/data-quality">Data Quality</a> · <a href="/sitemap.xml">Sitemap</a></p>
    </footer>

    <script>
        function toggleMenu() {{
            document.querySelector('.nav-links').classList.toggle('open');
        }}
    </script>
</body>
</html>'''
    return html


def main():
    with open(os.path.join(REPO, 'data', 'restaurants.json')) as f:
        data = json.load(f)
    
    restaurants = data['restaurants']
    total = len(restaurants)
    generated = 0
    skipped = 0
    errors = 0
    sitemap_entries = []

    print(f"Generating {total} restaurant pages...")

    for i, r in enumerate(restaurants):
        try:
            city_slug = slugify(r['city'])
            rest_slug = slugify(r['name'])
            
            # Handle duplicates in same city by appending FSA ID
            dir_path = os.path.join(OUT_DIR, city_slug, rest_slug)
            
            # If path exists (same name, same city), append FSA ID
            if os.path.exists(dir_path):
                dir_path = os.path.join(OUT_DIR, city_slug, f"{rest_slug}-{r['id']}")
                rest_slug = f"{rest_slug}-{r['id']}"
            
            os.makedirs(dir_path, exist_ok=True)
            
            html = generate_page(r)
            with open(os.path.join(dir_path, 'index.html'), 'w') as f:
                f.write(html)
            
            url_path = f'/r/{city_slug}/{rest_slug}/'
            sitemap_entries.append(f'  <url>\n    <loc>https://thaidata.uk{url_path}</loc>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>')
            
            generated += 1
            
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{total}...")
                
        except Exception as e:
            print(f"  ERROR on {r.get('name', '?')}: {e}", file=sys.stderr)
            errors += 1
    
    # Write sitemap entries
    sitemap_path = os.path.join(REPO, 'sitemap-r-restaurants.xml')
    with open(sitemap_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write('\n'.join(sitemap_entries))
        f.write('\n</urlset>\n')
    
    print(f"\nDone. Generated: {generated}, Errors: {errors}")
    print(f"Sitemap entries written to: {sitemap_path}")
    print(f"Output directory: {OUT_DIR}/")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Generate individual restaurant listing pages from restaurants.json
using the Kimi-designed template v2 (cream bg, green hero, 2-col layout).
"""
import json, os, re, sys
from datetime import datetime

REPO = '/tmp/thaidata-repo'
OUT_DIR = os.path.join(REPO, 'r')

# Load the Kimi template
with open(os.path.join(OUT_DIR, 'leeds', 'my-thai', 'index.html')) as f:
    TEMPLATE = f.read()

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

def format_date(datestr):
    if not datestr: return 'Unknown'
    try:
        dt = datetime.fromisoformat(datestr.replace('Z', '+00:00'))
        return dt.strftime('%B %Y')
    except:
        return datestr[:7] if len(datestr) >= 7 else datestr

def rating_class(rating):
    return {'5': 'r5', '4': 'r4', '3': 'r3', '2': 'r2', '1': 'r1'}.get(rating, 'r3')

def rating_label(rating):
    return {'5': 'Very Good', '4': 'Good', '3': 'Generally Satisfactory', '2': 'Improvement Necessary', '1': 'Major Improvement Necessary'}.get(rating, 'Rated')

def rating_color(rating):
    return {'5': 'var(--green-dark)', '4': '#3F6212', '3': '#92400E', '2': 'var(--red)', '1': 'var(--red)'}.get(rating, 'var(--ink)')

def score_bar_html(label, score):
    """Generate a single score bar div. FSA 0-25, lower=better."""
    if score is None:
        return ''
    # Invert: 0 → 100%, 25 → 0%
    pct = max(0, min(100, (25 - score) / 25 * 100))
    if score <= 10:
        fill_class, color = 'fill-green', 'var(--green)'
    elif score <= 20:
        fill_class, color = 'fill-amber', 'var(--amber)'
    else:
        fill_class, color = 'fill-red', 'var(--red)'
    return f'''                <div class="score-bar-wrap">
                    <div class="score-bar-header">
                        <span class="score-bar-label">{label}</span>
                        <span class="score-bar-value" style="color: {color};">{score}</span>
                    </div>
                    <div class="score-bar-track">
                        <div class="score-bar-fill {fill_class}" style="width: {pct}%"></div>
                    </div>
                </div>'''

def generate_page(r):
    """Fill the Kimi template with restaurant data."""
    html = TEMPLATE

    name = r['name']
    city = r['city']
    city_slug = slugify(city)
    rest_slug = slugify(name)
    rating = r.get('hygiene_rating', 'N/A')
    postcode = r.get('postcode', '')
    address = r.get('address', '')
    lat = r.get('latitude')
    lng = r.get('longitude')
    authority = r.get('local_authority', city)
    region = r.get('region', '')
    rtype = r.get('type', 'restaurant')
    date_str = format_date(r.get('rating_date', ''))
    rclass = rating_class(rating)
    rlabel = rating_label(rating)
    rcolor = rating_color(rating)
    rtype_icon = 'fa-utensils' if rtype == 'restaurant' else 'fa-box'
    rtype_label = rtype.replace('_', ' ').title()
    fsa_id = r['id']
    canonical = f'https://thaidata.uk/r/{city_slug}/{rest_slug}/'

    # ---- Head replacements ----
    html = html.replace(
        '<!-- DYNAMIC: title -->\n    <title>My Thai, Leeds — FSA 5/5 Hygiene Rating | ThaiData</title>',
        f'    <title>{name}, {city} — FSA {rating}/5 Hygiene Rating | ThaiData</title>'
    )
    html = html.replace(
        'content="My Thai in Leeds: FSA 5/5 restaurant. Full address, hygiene inspection scores, and map. Claim this free listing."',
        f'content="{name} in {city}: FSA {rating}/5 {rtype_label.lower()}.{ " " + address + "." if address else "" } Full address, hygiene inspection scores, and map. Claim this free listing."'
    )
    html = html.replace(
        '<!-- DYNAMIC: canonical_url -->\n    <link rel="canonical" href="https://thaidata.uk/r/leeds/my-thai/"',
        f'    <link rel="canonical" href="{canonical}"'
    )
    html = html.replace(
        '<!-- DYNAMIC: og_url -->\n    <meta property="og:url" content="https://thaidata.uk/r/leeds/my-thai/"',
        f'    <meta property="og:url" content="{canonical}"'
    )
    html = html.replace(
        '<!-- DYNAMIC: og_title -->\n    <meta property="og:title" content="My Thai, Leeds — FSA 5/5 | ThaiData"',
        f'    <meta property="og:title" content="{name}, {city} — FSA {rating}/5 | ThaiData"'
    )
    html = html.replace(
        '<!-- DYNAMIC: og_description -->\n    <meta property="og:description" content="FSA 5/5 hygiene rating. Thai restaurant in Leeds. View inspection scores and claim this listing."',
        f'    <meta property="og:description" content="FSA {rating}/5 hygiene rating. {rtype_label} in {city}. View inspection scores and claim this listing."'
    )

    # ---- Schema ----
    geo_json = ''
    if lat is not None and lng is not None:
        geo_json = f''',
        "geo": {{
            "@type": "GeoCoordinates",
            "latitude": {lat},
            "longitude": {lng}
        }}'''
    
    schema_restaurant = f'''    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": "{name}",
        "servesCuisine": "Thai",
        "address": {{
            "@type": "PostalAddress",
            "streetAddress": "{address}",
            "addressLocality": "{city}",
            "postalCode": "{postcode}",
            "addressCountry": "GB"
        }}{geo_json},
        "aggregateRating": {{
            "@type": "AggregateRating",
            "ratingValue": "{rating}",
            "bestRating": "5",
            "reviewAspect": "Hygiene"
        }}
    }}
    </script>'''
    
    # Replace from marker to end of current schema block
    html = re.sub(
        r'<!-- DYNAMIC: schema_restaurant -->.*?</script>',
        schema_restaurant,
        html, flags=re.DOTALL
    )

    schema_breadcrumb = f'''    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/"}},
            {{"@type": "ListItem", "position": 2, "name": "{city}", "item": "https://thaidata.uk/cities/{city_slug}"}},
            {{"@type": "ListItem", "position": 3, "name": "{name}"}}
        ]
    }}
    </script>'''
    html = re.sub(
        r'<!-- DYNAMIC: schema_breadcrumb -->.*?</script>',
        schema_breadcrumb,
        html, flags=re.DOTALL
    )

    # ---- Nav / Breadcrumb ----
    html = html.replace(
        '<!-- DYNAMIC: nav_back_link -->\n                <li><a href="/cities/leeds"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i>Leeds</a></li>',
        f'                <li><a href="/cities/{city_slug}"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i>{city}</a></li>'
    )
    html = html.replace(
        '<!-- DYNAMIC: breadcrumb -->\n        <a href="/">Home</a>\n        <span> › </span>\n        <a href="/cities/leeds">Leeds</a>\n        <span> › </span>\n        <span>My Thai</span>',
        f'        <a href="/">Home</a>\n        <span> › </span>\n        <a href="/cities/{city_slug}">{city}</a>\n        <span> › </span>\n        <span>{name}</span>'
    )

    # ---- Hero badges ----
    html = html.replace(
        '<!-- DYNAMIC: badge_rating -->\n                <span class="badge badge-rating">\n                    <i class="fas fa-star"></i> FSA 5/5\n                </span>',
        f'                <span class="badge badge-rating">\n                    <i class="fas fa-star"></i> FSA {rating}/5\n                </span>'
    )
    html = html.replace(
        '<!-- DYNAMIC: badge_type -->\n                <span class="badge badge-type">\n                    <i class="fas fa-utensils"></i> Restaurant\n                </span>',
        f'                <span class="badge badge-type">\n                    <i class="fas {rtype_icon}"></i> {rtype_label}\n                </span>'
    )

    # ---- Restaurant name (keep "My <em>Thai</em>" style if it fits, otherwise just plain) ----
    # Kimi italicized the last word. Let's keep it simple: wrap last word in <em> if multi-word
    words = name.split()
    if len(words) > 1:
        name_html = ' '.join(words[:-1]) + f' <em>{words[-1]}</em>'
    else:
        name_html = name
    
    html = html.replace(
        '<!-- DYNAMIC: restaurant_name -->\n            <h1>My <em>Thai</em></h1>',
        f'            <h1>{name_html}</h1>'
    )
    
    location_text = f'{city}'
    if region:
        location_text += f', {region}'
    html = html.replace(
        '<!-- DYNAMIC: location_line -->\n            <div class="hero-location">\n                <i class="fas fa-map-marker-alt"></i> Leeds, West Yorkshire\n            </div>',
        f'            <div class="hero-location">\n                <i class="fas fa-map-marker-alt"></i> {location_text}\n            </div>'
    )

    # ---- Action buttons ----
    if lat is not None and lng is not None:
        directions_href = f'https://www.google.com/maps/dir/?api=1&destination={lat},{lng}'
        map_href = f'https://www.google.com/maps?q={lat},{lng}'
    else:
        # Fallback: search by address
        addr_query = address.replace(' ', '+').replace(',', '') + '+' + postcode
        directions_href = f'https://www.google.com/maps/dir/?api=1&destination={addr_query}'
        map_href = f'https://www.google.com/maps?q={addr_query}'
    
    html = html.replace(
        '<!-- DYNAMIC: action_directions -->\n            <a href="https://www.google.com/maps/dir/?api=1&amp;destination=53.801537,-1.543306" target="_blank" rel="noopener" class="action-btn action-btn-primary">\n                <i class="fas fa-directions"></i> Get Directions\n            </a>',
        f'            <a href="{directions_href}" target="_blank" rel="noopener" class="action-btn action-btn-primary">\n                <i class="fas fa-directions"></i> Get Directions\n            </a>'
    )
    html = html.replace(
        '<!-- DYNAMIC: action_map -->\n            <a href="https://www.google.com/maps?q=53.801537,-1.543306" target="_blank" rel="noopener" class="action-btn action-btn-secondary">\n                <i class="fas fa-map"></i> View on Map\n            </a>',
        f'            <a href="{map_href}" target="_blank" rel="noopener" class="action-btn action-btn-secondary">\n                <i class="fas fa-map"></i> View on Map\n            </a>'
    )

    # ---- Hygiene rating card ----
    html = html.replace(
        '<!-- DYNAMIC: rating_circle -->\n                    <div class="rating-circle r5">\n                        <span class="score">5</span>\n                        <span class="of">of 5</span>\n                    </div>',
        f'                    <div class="rating-circle {rclass}">\n                        <span class="score">{rating}</span>\n                        <span class="of">of 5</span>\n                    </div>'
    )
    html = html.replace(
        '<!-- DYNAMIC: rating_label -->\n                        <div class="rating-meta-label" style="color: var(--green-dark);">Very Good</div>',
        f'                        <div class="rating-meta-label" style="color: {rcolor};">{rlabel}</div>'
    )
    html = html.replace(
        '<!-- DYNAMIC: rating_date -->\n                        <div class="rating-meta-detail">\n                            Last inspected: November 2025<br>',
        f'                        <div class="rating-meta-detail">\n                            Last inspected: {date_str}<br>'
    )
    html = html.replace(
        '<!-- DYNAMIC: local_authority -->\n                            <span style="color: var(--ink-tertiary);">Local authority: Leeds</span>',
        f'                            <span style="color: var(--ink-tertiary);">Local authority: {authority}</span>'
    )

    # ---- Score bars ----
    hy_score = r.get('hygiene_score')
    st_score = r.get('structural_score')
    mg_score = r.get('management_score')
    
    scores_html = ''
    if hy_score is not None:
        scores_html += score_bar_html('Hygiene', hy_score)
    if st_score is not None:
        scores_html += score_bar_html('Structural', st_score)
    if mg_score is not None:
        scores_html += score_bar_html('Management', mg_score)
    
    # Replace the three hardcoded score bars with dynamic ones
    html = re.sub(
        r'<!-- DYNAMIC: score_bars -->.*?<p class="score-note">',
        scores_html + '\n                <p class="score-note">' if scores_html else '                <p class="score-note">',
        html, flags=re.DOTALL
    )

    # ---- Address ----
    html = html.replace(
        '<!-- DYNAMIC: address_block -->\n                        <strong>My Thai</strong><br>\n                        43 New York Street<br>\n                        Leeds<br>\n                        LS2 8NJ',
        f'                        <strong>{name}</strong><br>\n                        {address}<br>\n                        {city}<br>\n                        {postcode}'
    )

    # ---- Map iframe ----
    if lat is not None and lng is not None:
        map_html = f'''                <div class="map-wrap">
                    <iframe
                        src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d300!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2z{lat}!5e0!3m2!1sen!2suk!4v1"
                        allowfullscreen=""
                        loading="lazy"
                        referrerpolicy="no-referrer-when-downgrade"
                        title="Map showing location of {name} in {city}">
                    </iframe>
                </div>'''
    else:
        map_html = ''
    
    html = re.sub(
        r'<!-- DYNAMIC: map_iframe.*?-->.*?<div class="map-wrap">.*?</div>',
        map_html if map_html else '',
        html, flags=re.DOTALL
    )

    # ---- Trust items ----
    trust_items = f'''                    <li class="trust-item">
                        <i class="fas fa-shield-check"></i>
                        <div><strong>FSA Verified</strong>Government inspection data</div>
                    </li>
                    <li class="trust-item">
                        <i class="fas fa-utensils"></i>
                        <div><strong>Thai Cuisine</strong>Authentic flavours</div>
                    </li>
                    <li class="trust-item">
                        <i class="fas fa-map-pin"></i>
                        <div><strong>{city}</strong>{region or 'UK'}</div>
                    </li>
                    <li class="trust-item">
                        <i class="fas fa-calendar-check"></i>
                        <div><strong>Inspected {date_str.split()[-1] if ' ' in date_str else date_str}</strong>Rating up to date</div>
                    </li>'''
    
    html = re.sub(
        r'<!-- DYNAMIC: trust_items -->.*?</ul>',
        trust_items + '\n                </ul>',
        html, flags=re.DOTALL
    )

    # ---- Related links ----
    html = html.replace(
        '<!-- DYNAMIC: related_city_link -->\n            <a href="/cities/leeds"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i> All Thai restaurants in Leeds</a>',
        f'            <a href="/cities/{city_slug}"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i> All Thai restaurants in {city}</a>'
    )

    # ---- Claim link (same for all unclaimed) ----
    html = html.replace(
        '<!-- DYNAMIC: claim_link -->\n                <a href="/claim/" class="btn">',
        '                <a href="/claim/" class="btn">'
    )

    # ---- Clean up remaining DYNAMIC markers (claimed content, not shown yet) ----
    # These are commented out HTML blocks — leave them as-is (they're hidden)
    # Just remove the marker comments for cleanliness
    html = re.sub(r'<!-- DYNAMIC: [^-]+ -->\n', '', html)

    # ---- Fix double braces from JSON-LD in Python strings ----
    # The schema had {{ }} for JSON which got single-braced. Fix:
    html = html.replace('"@context": "https://schema.org",', '"@context": "https://schema.org",')
    
    return html


def main():
    with open(os.path.join(REPO, 'data', 'restaurants.json')) as f:
        data = json.load(f)
    
    restaurants = data['restaurants']
    total = len(restaurants)
    generated = 0
    errors = 0

    print(f"Generating {total} restaurant pages with Kimi v2 template...")

    for i, r in enumerate(restaurants):
        try:
            city_slug = slugify(r['city'])
            rest_slug = slugify(r['name'])
            
            dir_path = os.path.join(OUT_DIR, city_slug, rest_slug)
            
            # Handle duplicates in same city by appending FSA ID
            if os.path.exists(os.path.join(dir_path, 'index.html')):
                dir_path = os.path.join(OUT_DIR, city_slug, f"{rest_slug}-{r['id']}")
            
            os.makedirs(dir_path, exist_ok=True)
            
            html = generate_page(r)
            with open(os.path.join(dir_path, 'index.html'), 'w') as f:
                f.write(html)
            
            generated += 1
            
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{total}...")
                
        except Exception as e:
            print(f"  ERROR on {r.get('name', '?')} ({r.get('city', '?')}): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            errors += 1
    
    print(f"\nDone. Generated: {generated}, Errors: {errors}")


if __name__ == '__main__':
    main()

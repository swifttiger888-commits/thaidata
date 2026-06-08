#!/usr/bin/env python3
"""
Generate individual restaurant listing pages from restaurants.json
using the Kimi-designed template v2 (cream bg, green hero, 2-col layout).
"""
import json, os, re, sys, unicodedata
from datetime import datetime
from typing import Any

REPO = '/tmp/thaidata-repo'
OUT_DIR = os.path.join(REPO, 'r')

# Load the Kimi template
with open(os.path.join(OUT_DIR, 'leeds', 'my-thai', 'index.html')) as f:
    TEMPLATE = f.read()

def slugify(s: str) -> str:
    s = unicodedata.normalize('NFC', s.lower().strip())
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

def format_date(datestr: str) -> str:
    if not datestr: return 'Unknown'
    try:
        dt = datetime.fromisoformat(datestr.replace('Z', '+00:00'))
        return dt.strftime('%B %Y')
    except:
        return datestr[:7] if len(datestr) >= 7 else datestr

def extract_neighbourhood(address: str, city: str) -> str:
    """Extract neighbourhood from address. e.g. '33 Town Street, Horsforth, Leeds' -> 'Horsforth'"""
    if not address or not city:
        return ''
    # Split on commas, strip whitespace
    parts = [p.strip() for p in address.split(',')]
    # Look for the part right before the city
    city_lower = city.lower()
    for i, p in enumerate(parts):
        if p.lower() == city_lower and i > 0:
            # Return the part before the city, stripping street numbers
            prev = parts[i-1]
            # Remove leading numbers/street prefixes
            prev = prev.strip()
            if prev and not prev[0].isdigit():
                return prev
            # If it starts with a number, try the part before that
            if i > 1:
                prev2 = parts[i-2].strip()
                if prev2 and not prev2[0].isdigit():
                    return prev2
    # Fallback: return the last non-city, non-postcode part
    for p in reversed(parts):
        p = p.strip()
        if p.lower() != city_lower and not any(c.isdigit() for c in p[:4]) and p and not p[0].isdigit():
            return p
    return ''

def build_intro(r: dict[str, Any]) -> str:
    """Build a 1-2 sentence intro paragraph for the listing page.
    Uses only FSA source data: name, type, address (neighbourhood), city, hygiene_rating, rating_date."""
    name = r['name']
    city = r['city']
    rtype = r.get('type', 'restaurant')
    rating = r.get('hygiene_rating', '')
    rating_date = format_date(r.get('rating_date', ''))
    address = r.get('address', '')

    type_word = 'restaurant' if rtype == 'restaurant' else 'takeaway'

    neighbourhood = extract_neighbourhood(address, city)
    if neighbourhood:
        location = f'{neighbourhood}, {city}'
    else:
        location = city

    intro = f'{name} is a Thai {type_word} in {location}.'

    # Add hygiene rating sentence if we have both rating and date
    if rating and rating != 'N/A':
        date_str = f', last inspected {rating_date}' if rating_date and rating_date != 'Unknown' else ''
        intro += f' FSA hygiene rating {rating}/5{date_str}.'

    return intro

def build_serves_cuisine(rtype: str) -> str:
    """Map restaurant type to servesCuisine. Conservative mapping — only use type field for safe hints."""
    if rtype == 'takeaway':
        return 'Thai takeaway'
    return 'Thai'

def rating_class(rating: str) -> str:
    return {'5': 'r5', '4': 'r4', '3': 'r3', '2': 'r2', '1': 'r1'}.get(rating, 'r3')

def rating_label(rating: str) -> str:
    return {'5': 'Very Good', '4': 'Good', '3': 'Generally Satisfactory', '2': 'Improvement Necessary', '1': 'Major Improvement Necessary'}.get(rating, 'Rated')

def rating_color(rating: str) -> str:
    return {'5': 'var(--green-dark)', '4': '#3F6212', '3': '#92400E', '2': 'var(--red)', '1': 'var(--red)'}.get(rating, 'var(--ink)')

def score_bar_html(label: str, score: int | None) -> str:
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

def build_nearby_section(city: str, city_slug: str, city_open: dict[str, list[dict[str, Any]]]) -> str:
    """Build the 'Nearby Thai restaurants' section for closed venues."""
    open_list = city_open.get(city, [])[:4]  # top 4 by hygiene rating
    if not open_list:
        return ''
    
    cards = []
    for rest in open_list:
        name = rest['name']
        rating = rest.get('hygiene_rating', '')
        addr = rest.get('address', '')
        # Extract just the street part for display
        street = addr.split(',')[0].strip() if addr else city
        rest_slug = slugify(name)
        rclass = rating_class(rating) if rating else ''
        rcolor = '#3F6212' if rating == '5' else '#92400E' if rating in ('3', '2', '1') else 'var(--green-dark)'
        
        cards.append(f'''            <a href="/r/{city_slug}/{rest_slug}/" class="nearby-card">
                <div class="nearby-rating" style="background:{'var(--green-light)' if rating == '5' else 'var(--amber-light)' if rating in ('3','4') else 'var(--red-light)'};color:{rcolor};">{rating}</div>
                <div class="nearby-info">
                    <div class="nearby-name">{name}</div>
                    <div class="nearby-addr">{street}</div>
                </div>
            </a>''')
    
    nearby_html = f'''    <section class="nearby-section">
        <div class="nearby-inner">
            <h3>Nearby Thai restaurants in {city}</h3>
            <p style="color: var(--ink-secondary); font-size: 0.85rem; margin-bottom: 20px;">Looking for Thai food in {city}? These nearby Thai restaurants are open and highly rated.</p>
            <div class="nearby-grid">
{chr(10).join(cards)}
            </div>
        </div>
    </section>'''
    return nearby_html


def generate_page(r: dict[str, Any], closed_ids: set[str] = None, city_open: dict[str, list[dict[str, Any]]] = None) -> str:
    """Fill the Kimi template with restaurant data."""
    if closed_ids is None:
        closed_ids = set()
    if city_open is None:
        city_open = {}
    html = TEMPLATE
    is_closed = str(r['id']) in closed_ids

    def safe_sub(pattern: str, replacement: str, text: str) -> str:
        """re.sub that doesn't interpret backslashes in replacement (safe for names with smart quotes)."""
        return re.sub(pattern, lambda m: replacement, text, flags=re.DOTALL)

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
    # ---- Robots meta (closed = noindex) ----
    if is_closed:
        html = html.replace(
            '<!-- DYNAMIC: robots_meta -->\n    <meta name="robots" content="index, follow">',
            '    <meta name="robots" content="noindex, follow">'
        )
    else:
        html = html.replace('<!-- DYNAMIC: robots_meta -->\n', '')
    # ---- FSA ID meta tag (inspectable from devtools) ----
    html = html.replace(
        '<!-- DYNAMIC: fsa_id_meta -->\n    <meta name="thaidata:fsa-id" content="842597">',
        f'    <meta name="thaidata:fsa-id" content="{fsa_id}">'
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

    # Build schema variables from FSA data only (no D1)
    cuisine = build_serves_cuisine(rtype)
    intro_text = build_intro(r)

    # dateModified as ISO date string from rating_date
    date_modified = ''
    raw_date = r.get('rating_date', '')
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            date_modified = dt.strftime('%Y-%m-%d')
        except:
            pass

    # additionalProperty for FSA scores (only if numeric scores exist — Scottish FHIS has none)
    addprop_parts = []
    hy_score = r.get('hygiene_score')
    st_score = r.get('structural_score')
    mg_score = r.get('management_score')
    if hy_score is not None:
        addprop_parts.append(f'''            {{
                "@type": "PropertyValue",
                "name": "FSA Hygiene Score",
                "value": {hy_score},
                "description": "Hygiene score (0=best, 25=worst)"
            }}''')
    if st_score is not None:
        addprop_parts.append(f'''            {{
                "@type": "PropertyValue",
                "name": "FSA Structural Score",
                "value": {st_score},
                "description": "Structural score (0=best, 25=worst)"
            }}''')
    if mg_score is not None:
        addprop_parts.append(f'''            {{
                "@type": "PropertyValue",
                "name": "FSA Management Score",
                "value": {mg_score},
                "description": "Management confidence score (0=best, 25=worst)"
            }}''')

    addprop_block = ''
    if addprop_parts:
        addprop_block = ',\n        "additionalProperty": [\n' + ',\n'.join(addprop_parts) + '\n        ]'

    # Only include dateModified if we have it, otherwise omit
    date_line = f',\n        "dateModified": {json.dumps(date_modified)}' if date_modified else ''
    
    schema_restaurant = f'''    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": {json.dumps(name)},
        "description": {json.dumps(intro_text)},
        "servesCuisine": {json.dumps(cuisine)},
        "address": {{
            "@type": "PostalAddress",
            "streetAddress": {json.dumps(address)},
            "addressLocality": {json.dumps(city)},
            "postalCode": {json.dumps(postcode)},
            "addressCountry": "GB"
        }}{geo_json}{date_line}{addprop_block}
    }}
    </script>'''
    
    # Replace from marker to end of current schema block
    anchor = '<!-- DYNAMIC: schema_restaurant -->'
    anchor_idx = html.find(anchor)
    if anchor_idx >= 0:
        end_tag = html.find('</script>', anchor_idx)
        if end_tag >= 0:
            end_idx = end_tag + len('</script>')
            html = html[:anchor_idx] + schema_restaurant + html[end_idx:]

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
    html = safe_sub(r'<!-- DYNAMIC: schema_breadcrumb -->.*?</script>', schema_breadcrumb, html)

    # ---- Nav / Breadcrumb ----
    html = html.replace(
        '<!-- DYNAMIC: nav_back_link -->\n                <li><a href="/cities/leeds"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i>Leeds</a></li>',
        f'                <li><a href="/cities/{city_slug}"><i class="fas fa-arrow-left" style="font-size:0.75em;margin-right:4px;"></i>{city}</a></li>'
    )
    html = html.replace(
        '<!-- DYNAMIC: breadcrumb -->\n        <a href="/">Home</a>\n        <span> › </span>\n        <a href="/cities/leeds">Leeds</a>\n        <span> › </span>\n        <span>My Thai</span>',
        f'        <a href="/">Home</a>\n        <span> › </span>\n        <a href="/cities/{city_slug}">{city}</a>\n        <span> › </span>\n        <span>{name}</span>'
    )

    # ---- Closed banner ----
    if is_closed:
        closed_banner_html = f'''    <div class="closed-banner">
        <i class="fas fa-door-closed"></i> <strong>Permanently Closed</strong>
        <span class="closed-note">This venue has been reported as permanently closed. Information kept for reference.</span>
    </div>'''
        html = html.replace('<!-- DYNAMIC: closed_banner -->\n', closed_banner_html + '\n')
    else:
        html = html.replace('<!-- DYNAMIC: closed_banner -->\n', '')

    # ---- Hero badges ----
    html = html.replace(
        '<!-- DYNAMIC: badge_rating -->\n                <span class="badge badge-rating">\n                    <i class="fas fa-star"></i> FSA 5/5\n                </span>',
        f'                <span class="badge badge-rating">\n                    <i class="fas fa-star"></i> FSA {rating}/5\n                </span>'
    )
    html = html.replace(
        '<!-- DYNAMIC: badge_type -->\n                <span class="badge badge-type">\n                    <i class="fas fa-utensils"></i> Restaurant\n                </span>',
        f'                <span class="badge badge-type">\n                    <i class="fas {rtype_icon}"></i> {rtype_label}\n                </span>'
    )

    # ---- Restaurant name (keep "<em>last word</em>" style, add type + city suffix) ----
    # Kimi italicized the last word. Let's keep it simple: wrap last word in <em> if multi-word
    words = name.split()
    if len(words) > 1:
        name_html = ' '.join(words[:-1]) + f' <em>{words[-1]}</em>'
    else:
        name_html = name

    type_word_label = 'Restaurant' if rtype == 'restaurant' else 'Takeaway'
    name_html += f' — Thai {type_word_label} in {city}'
    
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

    # ---- Intro paragraph ----
    intro_text = build_intro(r)
    # Use string find/replace instead of re.sub to avoid backslash escaping issues
    # with restaurant names containing smart quotes (e.g. \u2019)
    anchor = '<!-- DYNAMIC: intro_paragraph -->'
    anchor_idx = html.find(anchor)
    if anchor_idx >= 0:
        end_tag = html.find('</p>', anchor_idx)
        if end_tag >= 0:
            end_idx = end_tag + len('</p>')
            replacement = f'{anchor}\n            <p class="intro-blurb" style="margin-top:10px;font-size:0.95rem;color:rgba(255,255,255,0.92);line-height:1.5;max-width:650px;">\n                {intro_text}\n            </p>'
            html = html[:anchor_idx] + replacement + html[end_idx:]

    # ---- Hero claim CTA (closed = show closed notice) ----
    if is_closed:
        hero_closed_notice = f'''            <p style="margin-top:12px;font-size:0.85rem;color:rgba(255,200,200,0.9);">
                <i class="fas fa-door-closed" style="margin-right:4px;"></i>This venue has been reported as permanently closed.
            </p>'''
        # Replace the marker + claim CTA paragraph
        html = safe_sub(
            r'<!-- DYNAMIC: hero_claim_cta -->\s*\n\s*<p style="margin-top:12px;font-size:0\.85rem;color:var\(--ink-secondary\);">.*?</p>',
            hero_closed_notice,
            html
        )
    else:
        html = html.replace('<!-- DYNAMIC: hero_claim_cta -->\n', '')

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
    
    html = safe_sub(r'<!-- DYNAMIC: map_iframe.*?-->.*?<div class="map-wrap">.*?</div>', map_html if map_html else '', html)

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
    
    html = safe_sub(r'<!-- DYNAMIC: trust_items -->.*?</ul>', trust_items + '\n                </ul>', html)

    # ---- Related links ----
    html = html.replace(
        '<!-- DYNAMIC: related_city_link -->\n            <h3>Explore More</h3>\n            <a href="/cities/leeds">\n                <i class="fas fa-arrow-left"></i> All Thai restaurants in Leeds',
        f'            <a href="/cities/{city_slug}#browse">\n                <i class="fas fa-arrow-left"></i> All Thai restaurants in {city}'
    )

    # ---- Claim link (same for all unclaimed) ----
    html = html.replace(
        '<!-- DYNAMIC: claim_link -->\n                <a href="/claim/" class="btn">',
        '                <a href="/claim/" class="btn">'
    )

    # ---- Sidebar claim CTA (closed = replace with closed notice) ----
    if is_closed:
        sidebar_closed = f'''            <div class="closed-notice-card">
                <h3>Permanently Closed</h3>
                <p>This venue has been reported as permanently closed. The information on this page is kept for historical reference only.</p>
            </div>'''
        html = safe_sub(
            r'<!-- DYNAMIC: sidebar_claim_cta -->\s*\n\s*<!-- Claim CTA.*?id="claim">.*?</div>',
            '<!-- DYNAMIC: sidebar_claim_cta -->\n' + sidebar_closed + '\n',
            html
        )
    else:
        html = html.replace('<!-- DYNAMIC: sidebar_claim_cta -->\n', '')

    # ---- JS variables for enrichment script ----
    html = html.replace(
        "                const RESTAURANT_NAME = 'My Thai';",
        f"                const RESTAURANT_NAME = '{name}';"
    )
    html = html.replace(
        "                const RESTAURANT_CITY = 'Leeds';",
        f"                const RESTAURANT_CITY = '{city}';"
    )

    # ---- Nearby section (closed venues only) ----
    if is_closed:
        nearby_html = build_nearby_section(city, city_slug, city_open)
        html = html.replace('<!-- DYNAMIC: nearby_section -->\n', nearby_html)
    else:
        html = html.replace('<!-- DYNAMIC: nearby_section -->\n', '')

    # ---- Clean up remaining DYNAMIC markers ----
    # These are commented out HTML blocks — leave them as-is (they're hidden)
    # Just remove the marker comments for cleanliness
    html = re.sub(r'<!-- DYNAMIC: [^-]+ -->\n', '', html)

    # ---- Fix double braces from JSON-LD in Python strings ----
    # The schema had {{ }} for JSON which got single-braced. Fix:
    html = html.replace('"@context": "https://schema.org",', '"@context": "https://schema.org",')
    
    return html


def main() -> None:
    with open(os.path.join(REPO, 'data', 'restaurants.json')) as f:
        data = json.load(f)
    
    restaurants = data['restaurants']
    
    # Load exclusions (moderation layer — local file primary, API as override)
    excluded_ids: set[int] = set()

    # 1. Load from local file (always available)
    local_excl = os.path.join(REPO, 'data', 'exclusions.json')
    if os.path.exists(local_excl):
        with open(local_excl) as f:
            excl_local = json.load(f)
        excluded_ids.update(excl_local.get('excluded_fsa_ids', []))
        print(f"Loaded {len(excluded_ids)} exclusion(s) from local file")

    # 2. Supplement with D1 API (authoritative override)
    try:
        import urllib.request
        req = urllib.request.Request('https://thaidata.uk/api/exclusions', headers={'User-Agent': 'ThaiData-Pipeline/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            excl_data = json.loads(resp.read())
        api_ids = set(excl_data.get('excluded_ids', []))
        if api_ids:
            excluded_ids.update(api_ids)
            print(f"Loaded {len(api_ids)} additional exclusion(s) from D1 API")
    except Exception as e:
        print(f"Note: D1 exclusions unavailable ({e}) — using local file only")

    # Cleanup: delete pages for excluded restaurants
    if excluded_ids:
        cleaned = 0
        for dirpath, dirnames, filenames in os.walk(OUT_DIR):
            for fname in filenames:
                if fname != 'index.html':
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath) as f:
                        content = f.read()
                    # Extract FSA ID from schema JSON-LD
                    match = re.search(r'"identifier":\s*"?(\d+)"?', content)
                    if not match:
                        # Fallback: search for "fsa_id" or "FHRSID" in schema
                        match = re.search(r'fsa_id.*?(\d{5,7})', content)
                    if match and int(match.group(1)) in excluded_ids:
                        os.remove(fpath)
                        cleaned += 1
                        # Remove parent dirs if empty
                        parent = os.path.dirname(fpath)
                        try:
                            os.rmdir(parent)  # only removes if empty
                        except OSError:
                            pass
                except Exception:
                    pass
        if cleaned:
            print(f"Cleaned up {cleaned} excluded page(s)")
    
    # Load closed venues
    closed_ids: set[str] = set()
    closed_path = os.path.join(REPO, 'data', 'closed_venues.json')
    if os.path.exists(closed_path):
        with open(closed_path) as f:
            closed_data = json.load(f)
        for entry in closed_data:
            closed_ids.add(str(entry['fsa_id']))
        print(f"Loaded {len(closed_ids)} closed venue(s) from closed_venues.json")
    
    # Build city → open restaurants map (for nearby section)
    city_open: dict[str, list[dict[str, Any]]] = {}
    for r in restaurants:
        fsa_id_str = str(r['id'])
        if fsa_id_str in closed_ids:
            continue
        city = r['city']
        if city not in city_open:
            city_open[city] = []
        city_open[city].append(r)
    
    # Sort each city by hygiene rating desc (best first)
    for city in city_open:
        city_open[city].sort(key=lambda r: (-int(r.get('hygiene_rating', '0') or '0') if (r.get('hygiene_rating', '') or '').isdigit() else 0, r['name']))
    total = len(restaurants)
    generated = 0
    errors = 0

    print(f"Generating {total} restaurant pages with Kimi v2 template...")

    written_slugs: set[str] = set()

    for i, r in enumerate(restaurants):
        try:
            # Skip excluded restaurants (moderation layer)
            if r['id'] in excluded_ids:
                continue
            city_slug = slugify(r['city'])
            rest_slug = slugify(r['name'])
            
            dir_path = os.path.join(OUT_DIR, city_slug, rest_slug)
            
            # Handle duplicates: track written slugs per run; same slug again = collision → use -id suffix
            collision_key = f"{city_slug}/{rest_slug}"
            if collision_key in written_slugs:
                dir_path = os.path.join(OUT_DIR, city_slug, f"{rest_slug}-{r['id']}")
            written_slugs.add(collision_key)
            
            os.makedirs(dir_path, exist_ok=True)
            
            html = generate_page(r, closed_ids, city_open)
            
            # Don't overwrite the template file (r/leeds/my-thai/index.html)
            template_path = os.path.join(OUT_DIR, 'leeds', 'my-thai', 'index.html')
            out_path = os.path.join(dir_path, 'index.html')
            if os.path.abspath(out_path) == os.path.abspath(template_path):
                continue
            
            with open(out_path, 'w') as f:
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

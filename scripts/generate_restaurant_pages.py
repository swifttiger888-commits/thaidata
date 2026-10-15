#!/usr/bin/env python3
"""
Generate individual restaurant listing pages from restaurants.json
using the Kimi-designed template v2 (cream bg, green hero, 2-col layout).
"""
import json, os, re, sys, unicodedata, shutil
from datetime import datetime
from typing import Any
from urllib.parse import quote

REPO = '/tmp/thaidata-repo'
OUT_DIR = os.path.join(REPO, 'r')

# ── Meta description: A/B test concluded (Sep 2026) ──────────────
# The name-first variant showed no lift over 2 weeks and has been
# removed — every page uses the standard FSA-first description.
# Audit: .hermes/audits/2026-09-25-gsc-audit.md

# Load the Kimi template (pristine master — lives OUTSIDE the generated
# page tree so regeneration can never overwrite it and poison the
# DYNAMIC placeholders. NEVER write to this file from generate_page.)
with open(os.path.join(REPO, 'templates', 'restaurant.html')) as f:
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

    if rtype == 'pub':
        type_word = 'kitchen in a pub'
    else:
        type_word = 'restaurant' if rtype == 'restaurant' else 'takeaway'

    if rtype == 'pub':
        # Pub address lines start with the pub's own name, which the neighbourhood
        # extractor mis-reads as an area — pubs show the plain city instead.
        location = city
    else:
        neighbourhood = extract_neighbourhood(address, city)
        if neighbourhood:
            location = f'{neighbourhood}, {city}'
        else:
            location = city

    intro = f'{name} is a Thai {type_word} in {location}.'

    # Add hygiene rating sentence if we have both rating and date
    if rating and rating != 'N/A':
        date_str = f', last inspected {rating_date}' if rating_date and rating_date != 'Unknown' else ''
        # A colon only in the non-numeric case, so the numeric sentence stays byte-identical
        # to what is already live. "FSA hygiene rating Pass" reads as a typo; with the colon
        # it reads as a status.
        if rating_scheme(rating) == 'FHIS':
            intro += f' FHIS rating: {rating_text(rating)}{date_str}.'
        else:
            sep = '' if rating_is_scored(rating) else ':'
            intro += f' FSA hygiene rating{sep} {rating_text(rating)}{date_str}.'

    return intro

def build_serves_cuisine(rtype: str) -> str:
    """Map restaurant type to servesCuisine. Conservative mapping — only use type field for safe hints."""
    if rtype == 'takeaway':
        return 'Thai takeaway'
    return 'Thai'

# A numeric rating is a score out of 5. FSA Scotland instead publishes 'Pass' or
# 'Improvement Required', and 'Exempt' means the premises is outside the scheme: none of
# those are scores, and writing them as "Pass/5" is meaningless. Every place that turns a
# rating into text goes through these helpers so there is one answer, not eight.
SCORED_RATINGS = {'0', '1', '2', '3', '4', '5'}

# Pass is a pass, Improvement Required is a fail, Exempt is neutral — so they must not all
# collapse to the same amber default the way an unknown rating previously did.
NON_SCORED_CLASS = {'Pass': 'r5', 'Improvement Required': 'r2', 'Exempt': 'rn'}
NON_SCORED_COLOR = {'Pass': 'var(--green-dark)',
                    'Improvement Required': 'var(--red)',
                    'Exempt': 'var(--ink)'}


def rating_is_scored(rating: str) -> bool:
    """True when the rating is a 0-5 score (so '/5' is meaningful)."""
    return str(rating or '').strip() in SCORED_RATINGS


def rating_text(rating: str) -> str:
    """The rating written for a reader: '5/5', or 'Pass', or 'Improvement Required'."""
    r = str(rating or '').strip()
    return f'{r}/5' if r in SCORED_RATINGS else (r or 'Not rated')


def rating_scheme(rating: str) -> str:
    """'FHIS' for Scotland's Pass/Improvement Required statuses, else 'FHRS'.

    Only Pass and Improvement Required are exclusive to the Scottish scheme;
    'Exempt' is used by both schemes so it stays scheme-neutral in wording.
    """
    return 'FHIS' if str(rating or '').strip() in ('Pass', 'Improvement Required') else 'FHRS'


def rating_phrase(rating: str) -> str:
    """The rating as a clause in a sentence, for meta descriptions."""
    r = str(rating or '').strip()
    if r in SCORED_RATINGS:
        return f'{r}/5 hygiene rating'
    if rating_scheme(r) == 'FHIS':
        return f'FHIS status: {r}'
    return f'FSA status: {r}' if r else 'no FSA rating on record'


def rating_class(rating: str) -> str:
    r = str(rating or '').strip()
    if r in SCORED_RATINGS:
        return {'5': 'r5', '4': 'r4', '3': 'r3', '2': 'r2', '1': 'r1'}.get(r, 'r3')
    return NON_SCORED_CLASS.get(r, 'rn')

def rating_label(rating: str) -> str:
    r = str(rating or '').strip()
    if r in SCORED_RATINGS:
        return {'5': 'Very Good', '4': 'Good', '3': 'Generally Satisfactory', '2': 'Improvement Necessary', '1': 'Major Improvement Necessary'}.get(r, 'Rated')
    return r or 'Rated'

def rating_color(rating: str) -> str:
    r = str(rating or '').strip()
    if r in SCORED_RATINGS:
        return {'5': 'var(--green-dark)', '4': '#3F6212', '3': '#92400E', '2': 'var(--red)', '1': 'var(--red)'}.get(r, 'var(--ink)')
    return NON_SCORED_COLOR.get(r, 'var(--ink)')

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


def generate_page(r: dict[str, Any], closed_ids: set[str] = None, city_open: dict[str, list[dict[str, Any]]] = None, enrichment: dict[str, Any] = None, rest_slug: str | None = None, canonical_url: str | None = None) -> str:
    """Fill the Kimi template with restaurant data.
    enrichment: optional dict with google_place_id, rating, review_count, phone,
                website, opening_hours, photos, description, price_level.
                Keyed by fsa_id string.
    rest_slug: resolved slug for this page (may include an -{fsa_id} suffix for
               name-collisions). If None, slugify(name) is used.
    canonical_url: canonical URL for this page. If None, self-referencing URL
               is built from city_slug + rest_slug. Pass the clean-slug URL to
               make this page a proper alternate (non-indexable duplicate)."""
    if closed_ids is None:
        closed_ids = set()
    if city_open is None:
        city_open = {}
    if enrichment is None:
        enrichment = {}
    html = TEMPLATE
    is_closed = str(r['id']) in closed_ids

    def safe_sub(pattern: str, replacement: str, text: str) -> str:
        """re.sub that doesn't interpret backslashes in replacement (safe for names with smart quotes)."""
        return re.sub(pattern, lambda m: replacement, text, flags=re.DOTALL)

    name = r['name']
    city = r['city']
    city_slug = slugify(city)
    rest_slug = rest_slug or slugify(name)
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
    is_fhis = rating_scheme(rating) == 'FHIS'
    rtype_icon = {'restaurant': 'fa-utensils', 'takeaway': 'fa-box',
                  'pub': 'fa-beer-mug-empty'}.get(rtype, 'fa-utensils')
    rtype_label = 'Pub Kitchen' if rtype == 'pub' else rtype.replace('_', ' ').title()

    # The rating card. A score circle when the rating is a number; a status badge when it is
    # not, because 'of 5' is only meaningful against a score.
    if rating_is_scored(rating):
        circle_html = (f'                    <div class="rating-circle {rclass}">\n'
                       f'                        <span class="score">{rating}</span>\n'
                       f'                        <span class="of">of 5</span>\n'
                       f'                    </div>')
    else:
        circle_html = (f'                    <div class="rating-circle {rclass} status">\n'
                       f'                        <span class="score">{rlabel}</span>\n'
                       f'                    </div>')
    fsa_id = r['id']
    canonical = canonical_url or f'https://thaidata.uk/r/{city_slug}/{rest_slug}/'

    # ---- Head replacements ----
    tail = f'{ " " + address + "." if address else "" } Updated {format_date(r.get("rating_date", ""))}.'
    if is_fhis:
        meta_desc = f'content="FHIS inspection data for {name}, {city} (Food Standards Scotland). {rating_phrase(rating)}.{tail}"'
        og_desc = f'content="FHIS inspection data for {name}, {city} (Food Standards Scotland). {rating_phrase(rating)}.{tail}"'
    else:
        meta_desc = f'content="FSA inspection data for {name}, {city}. {rating_phrase(rating)}. See hygiene, structural, and management breakdown scores.{tail}"'
        og_desc = f'content="FSA inspection data for {name}, {city}. {rating_phrase(rating)}. See the full hygiene, structural, and management breakdown.{tail}"'
    scheme_label = 'FHIS' if is_fhis else 'FSA'
    html = html.replace(
        '<!-- DYNAMIC: title -->\n    <title>My Thai, Leeds — FSA 5/5 Hygiene Rating | ThaiData</title>',
        f'    <title>{name} {city} · {address if address else city} · {scheme_label} {rating_text(rating)} | ThaiData UK</title>'
    )
    html = html.replace(
        'content="FSA inspection data for My Thai, Leeds. 5/5 hygiene rating. See hygiene, structural, and management breakdown scores. 43 Wade Lane, Leeds City Centre, Leeds. Updated November 2025."',
        meta_desc
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
        f'    <meta property="og:title" content="{name} {city} · {address if address else city} · {scheme_label} {rating_text(rating)} | ThaiData UK"'
    )
    html = html.replace(
        '<!-- DYNAMIC: og_description -->\n    <meta property="og:description" content="FSA 5/5 hygiene rating. Thai restaurant in Leeds. View inspection scores and claim this listing."',
        f'    <meta property="og:description" {og_desc}'
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

    # ---- Google Places enrichment (auto-populated, separate from D1 listings) ----
    enr = enrichment.get(str(fsa_id)) or {}
    enr_rating = enr.get('rating')
    enr_review_count = enr.get('review_count')
    enr_phone = enr.get('phone')
    enr_website = enr.get('website')
    enr_desc = enr.get('description')
    enr_price = enr.get('price_level')
    enr_hours_raw = enr.get('opening_hours')  # JSON string of weekdayDescriptions
    enr_photos_raw = enr.get('photos')  # JSON string of photo references
    # Parse JSON strings from enrichment file
    try:
        enr_hours = json.loads(enr_hours_raw) if isinstance(enr_hours_raw, str) else enr_hours_raw
    except (json.JSONDecodeError, TypeError):
        enr_hours = None
    try:
        enr_photos = json.loads(enr_photos_raw) if isinstance(enr_photos_raw, str) else enr_photos_raw
    except (json.JSONDecodeError, TypeError):
        enr_photos = None

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

    # ---- Enrichment schema fields ----
    enrichment_schema_parts = []

    # Use enrichment description if available (richer than FSA-only intro)
    schema_desc = enr_desc if enr_desc else intro_text

    # NOTE: aggregateRating + googleMapsUri photo removed from schema (Oct 2026)
    # — Google Places ToS attribution fix: less un-attributed Google content.
    # telephone / priceRange / openingHours kept (attributed on-page).

    if enr_phone:
        enrichment_schema_parts.append(f'        "telephone": {json.dumps(enr_phone)}')

    if enr_price:
        enrichment_schema_parts.append(f'        "priceRange": {json.dumps(enr_price)}')

    if enr_hours and len(enr_hours) > 0:
        enrichment_schema_parts.append(f'''        "openingHours": {json.dumps(enr_hours)}''')

    enrichment_block = ''
    if enrichment_schema_parts:
        enrichment_block = ',\n' + ',\n'.join(enrichment_schema_parts)

    schema_restaurant = f'''    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": {json.dumps(name)},
        "description": {json.dumps(schema_desc)},
        "servesCuisine": {json.dumps(cuisine)},
        "address": {{
            "@type": "PostalAddress",
            "streetAddress": {json.dumps(address)},
            "addressLocality": {json.dumps(city)},
            "postalCode": {json.dumps(postcode)},
            "addressCountry": "GB"
        }}{geo_json}{date_line}{addprop_block}{enrichment_block}
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
            {{"@type": "ListItem", "position": 2, "name": {json.dumps(city)}, "item": "https://thaidata.uk/cities/{city_slug}"}},
            {{"@type": "ListItem", "position": 3, "name": {json.dumps(name)}}}
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
        f'                <span class="badge badge-rating">\n                    <i class="fas {"fa-star" if rating_is_scored(rating) else "fa-clipboard-check"}"></i> {scheme_label} {rating_text(rating)}\n                </span>'
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

    type_word_label = {'restaurant': 'Restaurant', 'takeaway': 'Takeaway',
                       'pub': 'Pub Kitchen'}.get(rtype, 'Restaurant')
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

    # ---- Contact strip (mobile-first: phone/website/hours anchor in first fold) ----
    # Claimed listings get contact data from Quick Facts (middleware strips this).
    if not is_closed:
        strip_items = []
        if enr_phone:
            strip_items.append(
                '<a class="cs-item" href="tel:' + enr_phone + '" style="color:rgba(255,255,255,0.95);text-decoration:none;font-size:0.9rem;font-weight:500;white-space:nowrap;"><i class="fas fa-phone-alt" style="margin-right:5px;"></i>' + enr_phone + '</a>'
            )
        if enr_website:
            strip_items.append(
                '<a class="cs-item" href="' + enr_website + '" target="_blank" rel="noopener" style="color:rgba(255,255,255,0.95);text-decoration:none;font-size:0.9rem;font-weight:500;white-space:nowrap;"><i class="fas fa-globe" style="margin-right:5px;"></i>Website</a>'
            )
        if enr_hours:
            strip_items.append(
                '<a class="cs-item" href="#contact" style="color:rgba(255,255,255,0.95);text-decoration:none;font-size:0.9rem;font-weight:500;white-space:nowrap;"><i class="far fa-clock" style="margin-right:5px;"></i>Hours</a>'
            )
        if strip_items:
            # Google Places ToS: attribution wherever Places content displays.
            strip_items.append(
                '<span class="cs-attr" translate="no" style="color:rgba(255,255,255,0.9);font-size:0.75rem;font-weight:400;white-space:nowrap;border:1px solid rgba(255,255,255,0.3);padding:1px 6px;border-radius:3px;">Google Maps</span>'
            )
            sep = '<span class="cs-sep" style="color:rgba(255,255,255,0.4);">·</span>'
            strip = ('<div class="contact-strip" id="contact-strip" style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;">'
                     + sep.join(strip_items) + '</div>')
            html = re.sub(r'<!-- DYNAMIC: contact_strip -->.*?</div>', strip, html, flags=re.DOTALL)
        else:
            html = re.sub(r'<!-- DYNAMIC: contact_strip -->.*?</div>', '', html, flags=re.DOTALL)
    else:
        html = re.sub(r'<!-- DYNAMIC: contact_strip -->.*?</div>', '', html, flags=re.DOTALL)

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
        # Closed venues offer no reporting path — drop the hero report link too
        html = safe_sub(
            r'\s*<!-- DYNAMIC: hero_report_cta -->.*?</p>',
            '',
            html
        )
    else:
        html = html.replace('<!-- DYNAMIC: hero_claim_cta -->\n', '')
        html = html.replace('<!-- DYNAMIC: hero_report_cta -->\n', '')
        if '<a href="#claim"' not in html:
            raise ValueError(f'hero claim anchor missing for {name} ({city})')
        html = html.replace(
            '<a href="#claim"',
            f'<a href="/claim/?restaurant={quote(name)}&amp;city={quote(city)}&amp;fsa_id={str(fsa_id)}&amp;src=hero-claim"',
        )

    # ---- Contact & Info section (replaces action bar + quick-info) ----
    has_enrichment = any([enr_hours, enr_price, enr_phone, enr_website])
    if has_enrichment:
        html = html.replace('<!-- DYNAMIC: contact_info_open -->\n', '')
        # Google Places ToS: per-page attribution inside the same visual container
        # as the Google-sourced fields (hours/phone/website/price).
        html = html.replace(
            '            <!-- DYNAMIC: contact_info_close -->\n',
            '            <div class="gm-attribution" style="margin-top:14px;padding-top:10px;border-top:1px solid rgba(0,0,0,0.08);font-family:Roboto,sans-serif;font-size:0.75rem;font-weight:400;color:#5e5e5e;white-space:nowrap;" translate="no">Google Maps</div>\n'
        )
        if enr_hours and len(enr_hours) > 0:
            hours_str = '<br>'.join(enr_hours[:7])
            html = re.sub(
                r'<!-- DYNAMIC: contact_hours -->.*?\n                    </div>',
                '<!-- DYNAMIC: contact_hours -->\n                    <div class="contact-block">\n                        <h4 class="contact-block-title"><i class="far fa-clock" style="margin-right:6px;"></i> Opening Hours</h4>\n                        <div class="contact-hours-text">' + hours_str + '</div>\n                    </div>',
                html, flags=re.DOTALL
            )
        else:
            html = re.sub(r'<!-- DYNAMIC: contact_hours -->.*?\n                    </div>', '', html, flags=re.DOTALL)

        detail_items = []
        if enr_phone:
            detail_items.append('<div class="contact-detail"><a href="tel:' + enr_phone + '">' + enr_phone + '</a></div>')
        if enr_website:
            detail_items.append('<div class="contact-detail"><a href="' + enr_website + '" target="_blank" rel="noopener">Visit website →</a></div>')
        if enr_price:
            detail_items.append('<div class="contact-detail"><span class="price-label">Price: ' + enr_price + '</span></div>')

        if detail_items:
            details_str = '\n                        '.join(detail_items)
            html = re.sub(
                r'<!-- DYNAMIC: contact_details -->.*?\n                    </div>',
                '<!-- DYNAMIC: contact_details -->\n                    <div class="contact-block">\n                        <h4 class="contact-block-title"><i class="fas fa-phone-alt" style="margin-right:6px;"></i> Contact</h4>\n                        ' + details_str + '\n                    </div>',
                html, flags=re.DOTALL
            )
        else:
            html = re.sub(r'<!-- DYNAMIC: contact_details -->.*?\n                    </div>', '', html, flags=re.DOTALL)
    else:
        html = re.sub(r'<!-- DYNAMIC: contact_info_open -->.*?<!-- DYNAMIC: contact_info_close -->\n', '', html, flags=re.DOTALL)

    # ---- Hygiene rating card ----
    html = html.replace(
        '<!-- DYNAMIC: rating_circle -->\n                    <div class="rating-circle r5">\n                        <span class="score">5</span>\n                        <span class="of">of 5</span>\n                    </div>',
        circle_html
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
    if lat and lng:
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
        map_html = f'''                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:32px 24px;text-align:center;margin-top:16px;">
                    <p style="color:#64748b;margin:0 0 8px;"><i class="fas fa-map-marker-alt" style="margin-right:6px;color:#94a3b8;"></i> Map coordinates unavailable for this location.</p>
                    <p style="color:#94a3b8;font-size:0.85rem;margin:0;">Use <strong>Get Directions</strong> or <strong>View on Map</strong> above to open this address in Google Maps.</p>
                </div>'''
    
    html = safe_sub(r'<!-- DYNAMIC: map_iframe.*?-->.*?<div class="map-wrap">.*?</div>', map_html if map_html else '', html)

    # ---- Trust items ----
    trust_strong = 'FHIS Verified' if is_fhis else 'FSA Verified'
    trust_sub = 'Food Standards Scotland inspection data' if is_fhis else 'Government inspection data'
    trust_items = f'''                    <li class="trust-item">
                        <i class="fas fa-shield-check"></i>
                        <div><strong>{trust_strong}</strong>{trust_sub}</div>
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

    # ---- Claim link (prefill context — the owner lands on /claim/ already searching) ----
    claim_url = (f'/claim/?restaurant={quote(name)}&amp;city={quote(city)}'
                 f'&amp;fsa_id={str(fsa_id)}&amp;src=restaurant-card')
    claim_link_old = ('<!-- DYNAMIC: claim_link -->\n'
                      '                <a href="/claim/?src=restaurant-card" class="btn">')
    if claim_link_old not in html:
        raise ValueError(f'claim_link marker/anchor drifted — check template ({name}, {city})')
    html = html.replace(claim_link_old, f'                <a href="{claim_url}" class="btn">')

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

    # ---- Report card (owner-help): closed venues don't offer reporting ----
    if is_closed:
        html = safe_sub(
            r'\s*<!-- DYNAMIC: report_card -->.*?<!-- DYNAMIC: report_card_end -->',
            '',
            html
        )

    # ---- JS variables for enrichment script ----
    html = html.replace(
        "                const RESTAURANT_NAME = 'My Thai';",
        f"                const RESTAURANT_NAME = {json.dumps(name)};"
    )
    html = html.replace(
        "                const RESTAURANT_CITY = 'Leeds';",
        f"                const RESTAURANT_CITY = {json.dumps(city)};"
    )
    html = html.replace(
        "                const RESTAURANT_FSA_ID = '0000000';",
        f'                const RESTAURANT_FSA_ID = {json.dumps(str(fsa_id))};'
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
    
    # ---- Owner-help phase 1 sanity checks (fail loudly, per page) ----
    if not is_closed:
        if f'RESTAURANT_FSA_ID = {json.dumps(str(fsa_id))}' not in html:
            raise ValueError(f'FSA id const missing ({name}, {city})')
        if claim_url not in html:
            raise ValueError(f'claim link not prefilled ({name}, {city})')
        if 'id="report-card"' not in html:
            raise ValueError(f'report card missing ({name}, {city})')
        if 'id="hero-report-cta"' not in html:
            raise ValueError(f'hero report link missing ({name}, {city})')
    elif 'id="report-card"' in html or 'id="hero-report-cta"' in html:
        raise ValueError(f'report UI leaked into closed page ({name}, {city})')

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
    
    # ---- Load Google Places enrichment ----
    enrichment_lookup: dict[str, dict[str, Any]] = {}
    enrichment_path = os.path.join(REPO, 'data', 'google_enrichment.json')
    if os.path.exists(enrichment_path):
        with open(enrichment_path) as f:
            enrichment_data = json.load(f)
        # Include entries with usable data: a successful Places lookup
        # (google_place_id) OR a manually-maintained entry that carries at
        # least one rendered field. Empty shells (all fields None) stay out.
        for entry in enrichment_data:
            if entry.get('google_place_id') or any(
                entry.get(k) for k in ('phone', 'website', 'opening_hours', 'price_level', 'description')
            ):
                enrichment_lookup[str(entry['fsa_id'])] = entry
        print(f"Loaded {len(enrichment_lookup)} enrichment entries")
    else:
        print("No enrichment data found — pages will use FSA-only content")
    total = len(restaurants)
    generated = 0
    errors = 0

    print(f"Generating {total} restaurant pages with Kimi v2 template...")

    # Pre-scan existing pages: which record currently owns each clean slug.
    # Preserves the live URL -> restaurant mapping across regeneration runs
    # (restaurants.json order is not stable across pipeline runs).
    clean_owner: dict[tuple[str, str], str] = {}
    for root, dirs, files in os.walk(OUT_DIR):
        if 'index.html' not in files:
            continue
        rel = os.path.relpath(root, OUT_DIR)
        parts = rel.split(os.sep)
        if len(parts) != 2:
            continue
        rest_slug_d = parts[1]
        if re.search(r'-\d+$', rest_slug_d):
            continue
        try:
            with open(os.path.join(root, 'index.html'), encoding='utf-8', errors='ignore') as f:
                m = re.search(r'fsa-id" content="(\d+)"', f.read())
            if m:
                clean_owner[(parts[0], rest_slug_d)] = m.group(1)
        except OSError:
            continue
    print(f"  Loaded {len(clean_owner)} clean-slug owners from existing pages")

    def slug_sort_key(r: dict[str, Any]) -> tuple:
        """Deterministic order: owner of the existing clean slug first (if any),
        then by id ascending. Guarantees slug assignment is stable across runs."""
        ck = (slugify(r['city']), slugify(r['name']))
        owner = clean_owner.get(ck)
        return (slugify(r['city']), slugify(r['name']), 0 if owner == str(r['id']) else 1, int(r['id']))

    ordered = sorted(restaurants, key=slug_sort_key)
    slug_owner: dict[tuple[str, str], dict[str, Any]] = {}
    generated_ids: set[str] = set()
    generated_paths: dict[str, str] = {}
    # The hero typeahead index, written at the end of the run from the pages actually
    # generated. Previously this file was hand-made and drifted from the data.
    names_index: list[dict[str, str]] = []
    canonical_by_id: dict[str, str] = {}

    for i, r in enumerate(ordered):
        try:
            # Skip excluded restaurants (moderation layer)
            if r['id'] in excluded_ids:
                continue
            city_slug = slugify(r['city'])
            rest_slug = slugify(r['name'])
            collision_key = (city_slug, rest_slug)

            dir_path = os.path.join(OUT_DIR, city_slug, rest_slug)
            canonical_url = None
            if collision_key in slug_owner:
                # Name collision in this city — write as {slug}-{fsa_id}
                dir_path = os.path.join(OUT_DIR, city_slug, f"{rest_slug}-{r['id']}")
                owner = slug_owner[collision_key]
                if (owner.get('address') == r.get('address')
                        and str(owner.get('hygiene_rating', '')) == str(r.get('hygiene_rating', ''))):
                    # Identical duplicate record — keep as a proper alternate
                    # (canonical to the clean slug, non-indexable by design).
                    canonical_url = f'https://thaidata.uk/r/{city_slug}/{rest_slug}/'
            else:
                slug_owner[collision_key] = r

            if canonical_url:
                canonical_by_id[str(r['id'])] = canonical_url

            os.makedirs(dir_path, exist_ok=True)

            html = generate_page(r, closed_ids, city_open, enrichment_lookup,
                                 rest_slug=os.path.basename(dir_path),
                                 canonical_url=canonical_url)

            out_path = os.path.join(dir_path, 'index.html')

            with open(out_path, 'w') as f:
                f.write(html)

            generated_ids.add(str(r['id']))
            generated_paths[str(r['id'])] = dir_path
            generated += 1
            names_index.append({
                'c': city_slug,
                'n': r['name'],
                't': r['city'],
                's': os.path.basename(dir_path),
            })
            
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{total}...")
                
        except Exception as e:
            print(f"  ERROR on {r.get('name', '?')} ({r.get('city', '?')}): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            errors += 1
    
    print(f"\nDone. Generated: {generated}, Errors: {errors}")

    # ── Hero typeahead index ──────────────────────────────────────
    # Derived from this run, so it can never disagree with the pages on disk. Sorted by name
    # then city so the file is stable between runs (the typeahead returns the first 6 matches
    # in file order, so alphabetical makes which-6-it-shows deterministic rather than arbitrary).
    if errors == 0:
        names_index.sort(key=lambda e: (e['n'].casefold(), e['c']))
        names_path = os.path.join(REPO, 'names.json')
        with open(names_path, 'w', encoding='utf-8') as f:
            json.dump(names_index, f, ensure_ascii=False, separators=(',', ':'))
        print(f"  names.json: {len(names_index)} entries -> {names_path}")

        # ── fsa_id -> live listing URL map (claim page 'View current listing') ──
        url_map = {
            str(i): canonical_by_id.get(str(i)) or f"https://thaidata.uk/{os.path.relpath(p, REPO)}/"
            for i, p in generated_paths.items()
        }
        out_js = (
            "// AUTO-GENERATED by generate_restaurant_pages.py — fsa_id -> live listing URL.\n"
            "// Regenerated on every restaurant-page build; do not edit by hand.\n"
            "export const LISTING_URLS = " + json.dumps(url_map, sort_keys=True) + ";\n"
        )
        with open(os.path.join(REPO, 'functions', 'api', 'listing_urls.js'), 'w', encoding='utf-8') as f:
            f.write(out_js)
        print(f"  listing_urls.js: {len(url_map)} entries")

        # ── Search index for /api/search-restaurants ──────────────────
        # Consumers: homepage search, claim page, /listing/manage. Rebuilt from
        # THIS run's generated records so it can never drift from the data.
        # (The previous index was a one-off June-2026 build that went stale and
        # hid takeaways + newer venues from claim search — fixed 2026-10-15.)
        search_index = []
        for r in ordered:
            fid = str(r['id'])
            if fid not in generated_paths:
                continue  # excluded or failed this run — never in the index
            search_index.append({
                'id': r['id'],
                'name': r['name'],
                'city': r.get('city') or '',
                'pc': r.get('postcode') or '',
                'address': r.get('address') or '',
                'rating': r.get('hygiene_rating') or '',
                'business_type': r.get('type') or 'restaurant',
                'listing_url': url_map.get(fid),
            })
        search_index.sort(key=lambda e: (e['name'].casefold(), e['city'].casefold()))
        search_path = os.path.join(REPO, 'data', 'restaurants-search.json')
        with open(search_path, 'w', encoding='utf-8') as f:
            json.dump(search_index, f, ensure_ascii=False, separators=(',', ':'))
        print(f"  restaurants-search.json: {len(search_index)} entries -> {search_path}")
    else:
        print(f"  names.json NOT written ({errors} generation errors) — "
              f"a partial index would hide restaurants from the hero search")

    # ── Prune stale pages ─────────────────────────────────────────
    # Remove dirs whose embedded fsa-id is not written AT THIS PATH this
    # run. Catches: records removed from restaurants.json, moderation
    # exclusions, AND stale duplicate dirs (an id that moved to a
    # different slug — e.g. clean-slug ownership reassigned). Only prune
    # when the run was clean — a partial run must never delete pages for
    # records that merely failed to generate.
    pruned = 0
    if errors == 0 and not os.environ.get('SKIP_PRUNE'):
        expected_paths = {str(fid): os.path.abspath(p) for fid, p in generated_paths.items()}
        for root, dirs, files in os.walk(OUT_DIR):
            if 'index.html' not in files:
                continue
            rel = os.path.relpath(root, OUT_DIR)
            parts = rel.split(os.sep)
            if len(parts) != 2:
                continue
            idx_path = os.path.join(root, 'index.html')
            with open(idx_path, encoding='utf-8', errors='ignore') as f:
                m = re.search(r'fsa-id" content="(\d+)"', f.read())
            if m and os.path.abspath(root) != expected_paths.get(m.group(1)):
                shutil.rmtree(root)
                pruned += 1
                try:
                    os.rmdir(os.path.join(OUT_DIR, parts[0]))  # clean up empty city dir
                except OSError:
                    pass
        print(f"  Pruned {pruned} stale page(s) not at their expected path")
    else:
        print(f"  Skipped stale-page pruning ({errors} generation errors)")


if __name__ == '__main__':
    main()

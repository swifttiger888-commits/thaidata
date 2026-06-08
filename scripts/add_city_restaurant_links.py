#!/usr/bin/env python3
"""Add restaurant listing links to city pages."""
import json, os, re
from typing import Any

REPO = '/tmp/thaidata-repo'

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

def extract_neighbourhood(address: str, city: str) -> str:
    """Extract neighbourhood from address. e.g. '33 Town Street, Horsforth, Leeds' -> 'Horsforth'"""
    if not address or not city:
        return ''
    parts = [p.strip() for p in address.split(',')]
    city_lower = city.lower()
    for i, p in enumerate(parts):
        if p.lower() == city_lower and i > 0:
            prev = parts[i-1].strip()
            if prev and not prev[0].isdigit():
                return prev
            if i > 1:
                prev2 = parts[i-2].strip()
                if prev2 and not prev2[0].isdigit():
                    return prev2
    for p in reversed(parts):
        p = p.strip()
        if p.lower() != city_lower and not any(c.isdigit() for c in p[:4]) and p and not p[0].isdigit():
            return p
    return ''

def outward_postcode(postcode: str) -> str:
    """Extract outward postcode. e.g. 'LS22 6NQ' -> 'LS22'"""
    if not postcode:
        return ''
    match = re.match(r'([A-Z0-9]+)', postcode.strip())
    return match.group(1) if match else postcode.strip()

def build_location_label(address: str, city: str, postcode: str) -> str:
    """Build compact location label: 'Neighbourhood • LS22' or 'LS22' or first address line."""
    neighbourhood = extract_neighbourhood(address, city)
    outward = outward_postcode(postcode)
    if neighbourhood and outward:
        return f"{neighbourhood} • {outward}"
    if outward:
        return outward
    if address:
        return address.split(',')[0].strip()
    return ''

# Build city → top restaurants map
with open(os.path.join(REPO, 'data', 'restaurants.json')) as f:
    data = json.load(f)

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
    import urllib.request as _ur
    req = _ur.Request('https://thaidata.uk/api/exclusions', headers={'User-Agent': 'ThaiData-Pipeline/1.0'})
    with _ur.urlopen(req, timeout=10) as resp:
        excl_data = json.loads(resp.read())
    api_ids = set(excl_data.get('excluded_ids', []))
    if api_ids:
        excluded_ids.update(api_ids)
        print(f"Loaded {len(api_ids)} additional exclusion(s) from D1 API")
except Exception as e:
    print(f"Note: D1 exclusions unavailable ({e}) — using local file only")

from collections import defaultdict
city_restaurants: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
for r in data['restaurants']:
    if r['id'] in excluded_ids:
        continue
    city_restaurants[r['city']].append(r)

# Sort each city's restaurants: 5-star first, then 4-star, etc.
def rating_sort_key(r: dict[str, Any]) -> int:
    val = r.get('hygiene_rating', '0')
    try:
        return -int(val)
    except (ValueError, TypeError):
        return 1  # 'Exempt', 'AwaitingPublication' etc. at the end

for city in city_restaurants:
    city_restaurants[city].sort(key=lambda r: (rating_sort_key(r), r['name'].lower()))

# Process each city page
cities_dir = os.path.join(REPO, 'cities')
updated: int = 0
skipped: int = 0

for filename in sorted(os.listdir(cities_dir)):
    if not filename.endswith('.html'):
        continue
    
    filepath = os.path.join(cities_dir, filename)
    city_name = filename.replace('.html', '').replace('-', ' ').title()
    
    # Normalize city name for matching
    city_slug = filename.replace('.html', '')
    
    # Find matching restaurants
    matches = []
    for city_key, rests in city_restaurants.items():
        if slugify(city_key) == city_slug:
            matches = rests
            city_name = city_key  # Use the actual city name from data
            break
    
    if not matches:
        print(f"  SKIP {filename} — no restaurant data match")
        skipped += 1
        continue
    
    with open(filepath) as f:
        html = f.read()
    
    # Remove any existing Browse Restaurants section (avoid duplicates)
    BEGIN_MARKER = '<!-- BEGIN Browse Restaurants -->'
    END_MARKER   = '<!-- END Browse Restaurants -->'
    
    # Remove sentinel-wrapped section if present
    if BEGIN_MARKER in html:
        start = html.find(BEGIN_MARKER)
        stop  = html.find(END_MARKER, start)
        if stop != -1:
            html = html[:start] + html[stop + len(END_MARKER):]
    
    # Remove old-format sections (boundary-based: robust against nested divs)
    OLD_MARKER = '<!-- Individual Restaurant Listings -->'
    while OLD_MARKER in html:
        start = html.find(OLD_MARKER)
        # Find the next boundary: another old marker, sentinel, or footer
        boundaries = []
        for b in [OLD_MARKER, '<!-- BEGIN Browse', '<footer>', '</body>']:
            pos = html.find(b, start + len(OLD_MARKER))
            if pos != -1:
                boundaries.append(pos)
        end = min(boundaries) if boundaries else len(html)
        html = html[:start] + html[end:]

    # Strip deprecated AUTO:top-rated zone (no longer generated)
    html = re.sub(
        r'\n?<!-- AUTO:top-rated -->.*?<!-- END:AUTO:top-rated -->\n?',
        '',
        html,
        flags=re.DOTALL
    )

    # Strip inline 🍜 Top Rated table (redundant with browse cards)
    html = re.sub(
        r'<div style="background:white;border-radius:12px;padding:20px 24px;margin:20px 0;'
        r'box-shadow:0 1px 3px rgba\(0,0,0,0\.08\);">\s*'
        r'<h3[^>]*>🍜 Top Rated</h3>.*?</div>',
        '',
        html,
        flags=re.DOTALL
    )
    
    # Build the restaurant links section
    MAX_DISPLAY = 100  # show all for typical cities; London (358) gets capped
    displayed = matches[:MAX_DISPLAY]
    links_html = ''
    for r in displayed:
        r_slug = slugify(r['name'])
        r_city_slug = slugify(r['city'])
        rating = r.get('hygiene_rating', '?')
        try:
            stars = '★' * int(rating) if rating.isdigit() else '—'
        except:
            stars = '—'
        rtype_label = 'Restaurant' if r.get('type') == 'restaurant' else 'Takeaway'
        rtype_icon = 'fa-utensils' if r.get('type') == 'restaurant' else 'fa-box'
        location = build_location_label(r.get('address', ''), r['city'], r.get('postcode', ''))
        location_html = f'<span style="font-size:0.73rem;color:var(--ink4);display:block;margin-top:2px;">{location}</span>' if location else ''
        links_html += f'''                    <a href="/r/{r_city_slug}/{r_slug}/" style="display:flex;align-items:center;gap:10px;padding:12px 16px;background:rgba(255,255,255,0.03);border:1px solid var(--line);border-radius:10px;text-decoration:none;transition:border-color 0.2s;">
                        <div style="flex:1;min-width:0;">
                            <span style="font-weight:600;font-size:0.9rem;color:white;display:block;">{r['name']}</span>
                            {location_html}
                        </div>
                        <span style="font-size:0.8rem;color:var(--ink4);"><i class="fas {rtype_icon}" style="margin-right:4px;"></i>{rtype_label}</span>
                        <span style="font-size:0.8rem;color:var(--c2);">{stars}</span>
                        <i class="fas fa-chevron-right" style="color:var(--ink3);font-size:0.7rem;"></i>
                    </a>\n'''
    
    section = f'''{BEGIN_MARKER}
        <div class="card" style="margin-top:20px;">
            <h2 id="browse" style="scroll-margin-top:80px;">Browse <em>Restaurants</em> in {city_name}</h2>
            <p style="color:var(--ink4);font-size:0.9rem;margin-bottom:16px;">View individual restaurant pages with full FSA hygiene scores, maps, and details. <a href="/r/" style="color:var(--c2);">What's this?</a></p>
            <div style="display:flex;flex-direction:column;gap:8px;">
{links_html}            </div>
            <p style="margin-top:14px;text-align:center;">
                <a href="/r/" style="color:var(--c2);font-size:0.85rem;text-decoration:none;">Browse all restaurant pages →</a>
            </p>
        </div>
{END_MARKER}
'''
    
    # Insert before footer or before the last </div> in .wrap
    if '<footer>' in html:
        html = html.replace('<footer>', section + '\n    <footer>')
    elif '</body>' in html:
        html = html.replace('</body>', section + '\n</body>')
    
    with open(filepath, 'w') as f:
        f.write(html)
    
    updated += 1
    if updated % 50 == 0:
        print(f"  {updated} cities...")

print(f"\nUpdated: {updated}, Skipped: {skipped}")

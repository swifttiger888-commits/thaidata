#!/usr/bin/env python3
"""Add restaurant listing links to city pages."""
import json, os, re

REPO = '/tmp/thaidata-repo'

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

# Build city → top restaurants map
with open(os.path.join(REPO, 'data', 'restaurants.json')) as f:
    data = json.load(f)

from collections import defaultdict
city_restaurants = defaultdict(list)
for r in data['restaurants']:
    city_restaurants[r['city']].append(r)

# Sort each city's restaurants: 5-star first, then 4-star, etc.
def rating_sort_key(r):
    val = r.get('hygiene_rating', '0')
    try:
        return -int(val)
    except (ValueError, TypeError):
        return 1  # 'Exempt', 'AwaitingPublication' etc. at the end

for city in city_restaurants:
    city_restaurants[city].sort(key=lambda r: (rating_sort_key(r), r['name'].lower()))

# Process each city page
cities_dir = os.path.join(REPO, 'cities')
updated = 0
skipped = 0

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
    
    # Build the restaurant links section
    top_restaurants = matches[:8]  # Top 8 by rating
    links_html = ''
    for r in top_restaurants:
        r_slug = slugify(r['name'])
        r_city_slug = slugify(r['city'])
        rating = r.get('hygiene_rating', '?')
        try:
            stars = '★' * int(rating) if rating.isdigit() else '—'
        except:
            stars = '—'
        rtype_label = 'Restaurant' if r.get('type') == 'restaurant' else 'Takeaway'
        rtype_icon = 'fa-utensils' if r.get('type') == 'restaurant' else 'fa-box'
        links_html += f'''                    <a href="/r/{r_city_slug}/{r_slug}/" style="display:flex;align-items:center;gap:10px;padding:12px 16px;background:rgba(255,255,255,0.03);border:1px solid var(--line);border-radius:10px;text-decoration:none;transition:border-color 0.2s;">
                        <span style="font-weight:600;font-size:0.9rem;color:white;flex:1;">{r['name']}</span>
                        <span style="font-size:0.8rem;color:var(--ink4);"><i class="fas {rtype_icon}" style="margin-right:4px;"></i>{rtype_label}</span>
                        <span style="font-size:0.8rem;color:var(--c2);">{stars}</span>
                        <i class="fas fa-chevron-right" style="color:var(--ink3);font-size:0.7rem;"></i>
                    </a>\n'''
    
    section = f'''
        <!-- Individual Restaurant Listings -->
        <div class="card" style="margin-top:20px;">
            <h2>Browse <em>Restaurants</em> in {city_name}</h2>
            <p style="color:var(--ink4);font-size:0.9rem;margin-bottom:16px;">View individual restaurant pages with full FSA hygiene scores, maps, and details. <a href="/r/" style="color:var(--c2);">What's this?</a></p>
            <div style="display:flex;flex-direction:column;gap:8px;">
{links_html}            </div>
            <p style="margin-top:14px;text-align:center;">
                <a href="/r/" style="color:var(--c2);font-size:0.85rem;text-decoration:none;">View all {len(matches)} restaurants in {city_name} →</a>
            </p>
        </div>
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

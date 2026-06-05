#!/usr/bin/env python3
"""
Fetch ALL UK Thai restaurant data from FSA API and save as structured JSON.
Generates:
  - data/restaurants.json  — individual restaurant records
  - api/v1/cities.json     — expanded city-level statistics
  - api/v1/data.json       — updated overview with correct counts

Run: python3 fetch_all_thai_data.py
"""

import json, time, urllib.request, urllib.parse, os, sys
from collections import defaultdict
from datetime import datetime
from typing import Any

from city_mapper import LA_TO_CITY, CITY_POPULATIONS, map_la_to_city, get_population
from fsa_client import fetch_all

# ── Configuration ────────────────────────────────────────────────────
REPO_DIR = '/tmp/thaidata-dl'
RESTAURANTS_FILE = os.path.join(REPO_DIR, 'data', 'restaurants.json')
CITIES_FILE = os.path.join(REPO_DIR, 'api', 'v1', 'cities.json')
DATA_FILE = os.path.join(REPO_DIR, 'api', 'v1', 'data.json')

# Rate limiting
DELAY = 0.35  # seconds between API calls


def main() -> None:
    start = datetime.now()
    print(f"=== Fetching ALL UK Thai Restaurant Data ===\n")
    print(f"Started: {start.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # ── Step 1: Fetch all establishments ─────────────────────────────
    print("Step 1/5: Fetching from FSA API...")
    all_ests = []
    
    # Core Thai search
    for scheme in ['FHRS', 'FHIS']:
        for bt in ['1', '7844']:
            label = f"{scheme} {'Restaurant/Cafe' if bt == '1' else 'Takeaway'}"
            ests = fetch_all('Thai', bt, scheme)
            print(f"  {label}: {len(ests)} establishments")
            all_ests.extend(ests)
            time.sleep(DELAY)
    
    # Chain searches (many Thai restaurants don't have "Thai" in the name)
    CHAINS = ['Giggling Squid', 'Busaba', 'Chaophraya', 'Patara', 'Sukhothai', 'Zaap',
              'Rosa\'s Thai', 'Thaikhun', 'Thai Square', 'Banana Tree', 'Mango Tree']
    chain_added = 0
    for chain in CHAINS:
        for scheme in ['FHRS', 'FHIS']:
            for bt in ['1', '7844']:
                time.sleep(DELAY)
                try:
                    ests = fetch_all(chain, bt, scheme)
                    for e in ests:
                        all_ests.append(e)
                        chain_added += 1
                except Exception:
                    pass
    print(f"  Chain additions: {chain_added}")
    
    # Deduplicate by FHRSID
    seen = {}
    for e in all_ests:
        fid = e['FHRSID']
        if fid not in seen:
            seen[fid] = e
    all_ests = list(seen.values())
    print(f"  After dedup: {len(all_ests)} unique establishments\n")
    
    # ── Step 2: Process into restaurant records ──────────────────────
    print("Step 2/5: Processing restaurant records...")
    restaurants = []
    skipped = 0
    for e in all_ests:
        rating = e.get('RatingValue', '')
        if rating in ('Awaiting Inspection', 'AwaitingInspection', '', None):
            skipped += 1
            continue
        
        la_name = e.get('LocalAuthorityName', 'Unknown')
        city = map_la_to_city(la_name)
        
        # Extract address
        addr_parts = []
        for i in range(1, 5):
            line = e.get(f'AddressLine{i}', '').strip()
            if line:
                addr_parts.append(line)
        
        btype = e.get('BusinessType', '')
        is_takeaway = 'Takeaway' in btype or 'takeaway' in btype.lower()
        
        record = {
            'id': e['FHRSID'],
            'name': e.get('BusinessName', 'Unknown'),
            'type': 'takeaway' if is_takeaway else 'restaurant',
            'city': city,
            'local_authority': la_name,
            'postcode': e.get('PostCode', '').strip(),
            'address': ', '.join(addr_parts),
            'hygiene_rating': str(rating) if rating else 'Unknown',
            'rating_date': e.get('RatingDate', ''),
            'longitude': e.get('Geocode', {}).get('Longitude', ''),
            'latitude': e.get('Geocode', {}).get('Latitude', ''),
        }
        restaurants.append(record)
    
    print(f"  {len(restaurants)} restaurants with ratings")
    print(f"  {skipped} skipped (awaiting inspection)\n")
    
    # ── Step 3: Generate city statistics ─────────────────────────────
    print("Step 3/5: Computing city statistics...")
    by_city = defaultdict(lambda: {
        'total': 0, 'restaurants': 0, 'takeaways': 0,
        'ratings': [], 'postcodes': set()
    })
    
    for r in restaurants:
        c = by_city[r['city']]
        c['total'] += 1
        if r['type'] == 'restaurant':
            c['restaurants'] += 1
        else:
            c['takeaways'] += 1
        try:
            c['ratings'].append(int(r['hygiene_rating']))
        except (ValueError, TypeError):
            pass
        if r['postcode']:
            c['postcodes'].add(r['postcode'][:3].strip())  # Outcode only
    
    # Build city list
    cities = []
    for city_name, data in sorted(by_city.items(), key=lambda x: x[1]['total'], reverse=True):
        avg_rating = sum(data['ratings']) / len(data['ratings']) if data['ratings'] else 0
        pop = get_population(city_name)
        per_100k = round(data['total'] / pop * 100000, 1) if pop else None
        
        cities.append({
            'name': city_name,
            'population': pop,
            'total_thai_businesses': data['total'],
            'restaurants': data['restaurants'],
            'takeaways': data['takeaways'],
            'per_100k': per_100k,
            'avg_hygiene_rating': round(avg_rating, 1),
            'postcode_areas': len(data['postcodes']),
        })
    
    print(f"  {len(cities)} cities with Thai restaurants\n")
    
    # ── Step 4: Save files ───────────────────────────────────────────
    today = start.strftime('%Y-%m-%d')
    total = len(restaurants)
    
    # 4a. Save restaurants.json
    print("Step 4/5: Saving files...")
    os.makedirs(os.path.dirname(RESTAURANTS_FILE), exist_ok=True)
    with open(RESTAURANTS_FILE, 'w') as f:
        json.dump({
            'name': 'ThaiData UK — Restaurant Directory',
            'updated': today,
            'total': total,
            'sources': ['FSA FHRS', 'FSA FHIS'],
            'restaurants': restaurants
        }, f, indent=2)
    print(f"  ✅ {RESTAURANTS_FILE} ({total} records)")
    
    # 4b. Save expanded cities.json
    os.makedirs(os.path.dirname(CITIES_FILE), exist_ok=True)
    with open(CITIES_FILE, 'w') as f:
        json.dump({
            'name': 'ThaiData UK — Thai Restaurant Data API',
            'version': '2.0',
            'description': 'Free, open data on UK Thai restaurants. Sourced from FSA. No API key required.',
            'attribution': 'Data from ThaiData.uk / Food Standards Agency',
            'updated': today,
            'total_uk': total,
            'cities_tracked': len(cities),
            'cities': cities
        }, f, indent=2)
    print(f"  ✅ {CITIES_FILE} ({len(cities)} cities)")
    
    # 4c. Update data.json overview
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            overview = json.load(f)
        overview['last_updated'] = today
        overview['statistics']['total_uk_thai_businesses'] = total
        # Recompute from cities
        all_total = sum(c['total_thai_businesses'] for c in cities)
        dine_in_total = sum(c['restaurants'] for c in cities)
        takeaway_total = sum(c['takeaways'] for c in cities)
        overview['statistics']['total_full_service_restaurants'] = dine_in_total
        overview['statistics']['total_quick_service_takeaways'] = takeaway_total
        overview['top_cities'] = cities[:15]
        with open(DATA_FILE, 'w') as f:
            json.dump(overview, f, indent=2)
        print(f"  ✅ {DATA_FILE} updated")
    
    # ── Step 5: Summary ──────────────────────────────────────────────
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nStep 5/5: Done in {elapsed:.1f}s")
    print(f"\n{'='*60}")
    print(f"Total restaurants: {total}")
    print(f"Cities tracked: {len(cities)}")
    print(f"Dine-in: {dine_in_total}, Takeaway: {takeaway_total}")
    print(f"\nTop 20 cities:")
    for i, c in enumerate(cities[:20]):
        print(f"  {i+1:2d}. {c['name']:20s} {c['total_thai_businesses']:4d} restaurants  ★{c['avg_hygiene_rating']:.1f}  {c['per_100k'] or '?':>5} /100k")
    
    # Print for shell consumption
    print(f"\nCITY_COUNT={len(cities)}")
    print(f"RESTAURANT_COUNT={total}")


if __name__ == '__main__':
    main()

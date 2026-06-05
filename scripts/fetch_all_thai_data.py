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

# ── Configuration ────────────────────────────────────────────────────
REPO_DIR = '/tmp/thaidata-dl'
RESTAURANTS_FILE = os.path.join(REPO_DIR, 'data', 'restaurants.json')
CITIES_FILE = os.path.join(REPO_DIR, 'api', 'v1', 'cities.json')
DATA_FILE = os.path.join(REPO_DIR, 'api', 'v1', 'data.json')

# Rate limiting
DELAY = 0.35  # seconds between API calls

# ── Local Authority → City mapping ───────────────────────────────────
# London boroughs → London, others mapped by common name
LA_TO_CITY = {
    # London boroughs
    'Westminster': 'London', 'Camden': 'London', 'Tower Hamlets': 'London',
    'Kensington and Chelsea': 'London', 'Hammersmith and Fulham': 'London',
    'Wandsworth': 'London', 'Islington': 'London', 'Lambeth': 'London',
    'Southwark': 'London', 'Hackney': 'London', 'Haringey': 'London',
    'Brent': 'London', 'Ealing': 'London', 'Barnet': 'London',
    'Hounslow': 'London', 'Newham': 'London', 'Croydon': 'London',
    'Bromley': 'London', 'Enfield': 'London', 'Lewisham': 'London',
    'Richmond upon Thames': 'London', 'Hillingdon': 'London',
    'Waltham Forest': 'London', 'Redbridge': 'London', 'Greenwich': 'London',
    'Merton': 'London', 'Harrow': 'London', 'Kingston upon Thames': 'London',
    'Bexley': 'London', 'Sutton': 'London', 'Barking and Dagenham': 'London',
    'Havering': 'London', 'City of London': 'London',
    # Named city corrections
    'Edinburgh (City of)': 'Edinburgh',
    'Glasgow City': 'Glasgow',
    'Manchester': 'Manchester',
    'Birmingham': 'Birmingham',
    'Leeds': 'Leeds',
    'Bristol': 'Bristol',
    'Liverpool': 'Liverpool',
    'Sheffield': 'Sheffield',
    'Newcastle upon Tyne': 'Newcastle',
    'Cardiff': 'Cardiff',
    'Belfast': 'Belfast',
    'Leicester': 'Leicester',
    'Bradford': 'Bradford',
    'Coventry': 'Coventry',
    'Nottingham': 'Nottingham',
    'Kingston upon Hull': 'Hull',
    'Plymouth': 'Plymouth',
    'Stoke-on-Trent': 'Stoke-on-Trent',
    'Wolverhampton': 'Wolverhampton',
    'Derby': 'Derby',
    'Southampton': 'Southampton',
    'Portsmouth': 'Portsmouth',
    'Brighton and Hove': 'Brighton',
    'Bournemouth, Christchurch and Poole': 'Bournemouth',
    'Swansea': 'Swansea',
    'Norwich': 'Norwich',
    'Oxford': 'Oxford',
    'Cambridge': 'Cambridge',
    'York': 'York',
    'Bath and North East Somerset': 'Bath',
    'Cheltenham': 'Cheltenham',
    'Sunderland': 'Sunderland',
    'Milton Keynes': 'Milton Keynes',
    'Luton': 'Luton',
    'Warrington': 'Warrington',
    'Slough': 'Slough',
    'Reading': 'Reading',
    'Blackpool': 'Blackpool',
    'Bolton': 'Bolton',
    'Stockport': 'Stockport',
    'Oldham': 'Oldham',
    'Wigan': 'Wigan',
    'Chelmsford': 'Chelmsford',
    'Huddersfield': 'Kirklees',  # Kirklees → Huddersfield
    'Kirklees': 'Huddersfield',
    'Northampton': 'Northampton',
    'Swindon': 'Swindon',
    'Peterborough': 'Peterborough',
    'Dundee City': 'Dundee',
    'Aberdeen City': 'Aberdeen',
    'Inverness': 'Inverness',
    'Perth and Kinross': 'Perth',
    'Stirling': 'Stirling',
    'Exeter': 'Exeter',
    'Gloucester': 'Gloucester',
    'Worcester': 'Worcester',
    'Lincoln': 'Lincoln',
    'Canterbury': 'Canterbury',
    'Colchester': 'Colchester',
    'Ipswich': 'Ipswich',
    'Preston': 'Preston',
    'Blackburn with Darwen': 'Blackburn',
    'Southend-on-Sea': 'Southend',
    'Doncaster': 'Doncaster',
    'Wakefield': 'Wakefield',
    'Rotherham': 'Rotherham',
    'Telford and Wrekin': 'Telford',
    'Middlesbrough': 'Middlesbrough',
    'Darlington': 'Darlington',
    'Halton': 'Warrington',  # Halton includes Widnes/Runcorn
}

# ── Population data (ONS 2024 estimates, rounded) ────────────────────
CITY_POPULATIONS = {
    'London': 8970000, 'Birmingham': 1166000, 'Leeds': 812000,
    'Glasgow': 635000, 'Sheffield': 584000, 'Manchester': 568000,
    'Edinburgh': 548000, 'Liverpool': 500000, 'Bristol': 483000,
    'Bradford': 547000, 'Huddersfield': 437000, 'Leicester': 374000,
    'Coventry': 370000, 'Cardiff': 372000, 'Belfast': 345000,
    'Nottingham': 328000, 'Newcastle': 307000, 'Bolton': 300000,
    'Sunderland': 278000, 'Brighton': 277000, 'Hull': 266000,
    'Plymouth': 265000, 'Wolverhampton': 263000, 'Derby': 260000,
    'Southampton': 256000, 'Swansea': 247000, 'Oldham': 243000,
    'Milton Keynes': 292000, 'Stockport': 295000, 'Wigan': 333000,
    'Luton': 228000, 'York': 211000, 'Portsmouth': 208000,
    'Warrington': 212000, 'Slough': 164000, 'Bournemouth': 401000,
    'Norwich': 148000, 'Oxford': 164000, 'Cambridge': 146000,
    'Bath': 196000, 'Reading': 175000, 'Blackpool': 142000,
    'Northampton': 250000, 'Swindon': 236000, 'Peterborough': 218000,
    'Dundee': 152000, 'Aberdeen': 202000, 'Inverness': 71000,
    'Perth': 51000, 'Stirling': 49000, 'Exeter': 135000,
    'Cheltenham': 120000, 'Chelmsford': 184000, 'Gloucester': 132000,
    'Worcester': 105000, 'Lincoln': 104000, 'Canterbury': 64000,
    'Colchester': 195000, 'Ipswich': 150000, 'Preston': 150000,
    'Blackburn': 150000, 'Southend': 185000, 'Doncaster': 310000,
    'Wakefield': 345000, 'Rotherham': 265000, 'Telford': 160000,
    'Middlesbrough': 148000, 'Darlington': 108000, 'Stoke-on-Trent': 260000,
    'Salford': 260000, 'Wirral': 325000, 'Sefton': 275000,
    'Knowsley': 155000, 'St Helens': 185000, 'Rochdale': 227000,
    'Bury': 195000, 'Tameside': 230000, 'Trafford': 237000,
    'Cheshire East': 390000, 'Cheshire West and Chester': 357000,
    'Lancaster': 145000, 'East Riding of Yorkshire': 345000,
    'North Lincolnshire': 170000, 'North East Lincolnshire': 160000,
    'Shropshire': 325000, 'Staffordshire': 880000, 'Warwickshire': 590000,
    'West Northamptonshire': 430000, 'North Northamptonshire': 365000,
    'Bedford': 185000, 'Central Bedfordshire': 300000, 'Buckinghamshire': 560000,
    'Oxfordshire': 725000, 'West Berkshire': 162000, 'Wokingham': 180000,
    'Bracknell Forest': 128000, 'Windsor and Maidenhead': 158000,
    'Surrey': 1216000, 'Hertfordshire': 1200000, 'Essex': 1500000,
    'Kent': 1600000, 'Medway': 285000, 'East Sussex': 560000,
    'West Sussex': 890000, 'Hampshire': 1400000, 'Isle of Wight': 142000,
    'Dorset': 380000, 'Somerset': 580000, 'Devon': 820000,
    'Cornwall': 575000, 'Wiltshire': 520000, 'Gloucestershire': 650000,
    'Herefordshire': 195000, 'Worcestershire': 605000, 'Warrington': 212000,
}


def map_la_to_city(local_authority):
    """Map a Local Authority name to its parent city."""
    if local_authority in LA_TO_CITY:
        return LA_TO_CITY[local_authority]
    # Try stripping county suffixes
    for suffix in [' City', ' District', ' Borough', ' County', ' (B)', ' City Council']:
        if local_authority.endswith(suffix):
            stripped = local_authority[:-len(suffix)].strip()
            if stripped in CITY_POPULATIONS:
                return stripped
    # If LA contains a known city name, use that
    for city in sorted(CITY_POPULATIONS.keys(), key=len, reverse=True):
        if city.lower() in local_authority.lower():
            return city
    return local_authority


def get_population(city_name):
    """Get population for a city, with fallbacks."""
    if city_name in CITY_POPULATIONS:
        return CITY_POPULATIONS[city_name]
    # Try removing county suffixes
    for suffix in [' City', ' District', ' Borough', ' County', ' (B)']:
        if city_name.endswith(suffix):
            stripped = city_name[:-len(suffix)].strip()
            if stripped in CITY_POPULATIONS:
                return CITY_POPULATIONS[stripped]
    return None


def fetch_all(name, business_type_id, scheme_key):
    """Fetch all establishments matching criteria from FSA API. Returns list of dicts."""
    all_ests = []
    page = 1
    page_size = 500
    encoded = urllib.parse.quote(name)
    while True:
        url = (f'https://api.ratings.food.gov.uk/Establishments'
               f'?name={encoded}&businessTypeId={business_type_id}'
               f'&schemeTypeKey={scheme_key}'
               f'&pageNumber={page}&pageSize={page_size}')
        try:
            req = urllib.request.Request(url, headers={
                'x-api-version': '2',
                'accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            break
        ests = data.get('establishments', [])
        if not ests:
            break
        all_ests.extend(ests)
        if len(ests) < page_size:
            break
        page += 1
        time.sleep(0.15)
    return all_ests


def main():
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

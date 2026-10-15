"""Harvest pub-typed FSA venues with 'Thai' in the name (type 7843).
Output: analysis/pub_venues.json (candidates for the pub section, verified later).
"""
import json, time, urllib.request, urllib.parse

API = 'https://api.ratings.food.gov.uk'
HEADERS = {'x-api-version': '2', 'User-Agent': 'thaidata-research', 'accept': 'application/json'}

def fetch(page_number=1, name='Thai', bt='7843', scheme='FHRS'):
    qs = urllib.parse.urlencode({'name': name, 'businessTypeId': bt, 'pageNumber': page_number, 'pageSize': 200})
    url = f'{API}/Establishments?{qs}'
    req = urllib.request.Request(url, headers=HEADERS)
    return json.load(urllib.request.urlopen(req, timeout=45))

records = []
for scheme in ('FHRS', 'FHIS'):
    page = 1
    while True:
        d = fetch(page, scheme=scheme)
        ests = d.get('establishments', [])
        records.extend(ests)
        meta = d.get('meta', {})
        total = meta.get('totalCount', 0)
        pages = meta.get('totalPages', 1)
        print(f'{scheme} page {page}/{pages}: {len(ests)} (total {total})')
        if page >= pages:
            break
        page += 1
        time.sleep(1)

# keep only name-contains-thai (type filter already applied server-side, belt & braces)
kept = [e for e in records if 'thai' in e['BusinessName'].lower()]
print(f'\nkept Thai-named pubs: {len(kept)}')
out = []
for e in kept:
    out.append({
        'id': e['FHRSID'],
        'name': e['BusinessName'],
        'address': ', '.join(x for x in [e['AddressLine1'], e['AddressLine2'], e['AddressLine3'], e['AddressLine4']] if x),
        'postcode': e['PostCode'],
        'city': e['LocalAuthorityName'],
        'rating': e['RatingValue'],
        'type_id': e['BusinessTypeID'],
        'scheme': e['SchemeType'],
        'lat': e.get('geocode', {}).get('latitude'),
        'lon': e.get('geocode', {}).get('longitude'),
    })
# sort, dedupe
out = {o['id']: o for o in out}
out = sorted(out.values(), key=lambda o: (o['city'], o['name']))
with open('/opt/thaidata-repo/analysis/pub_venues.json', 'w') as f:
    json.dump(out, f, indent=2)
print(f'written analysis/pub_venues.json: {len(out)} venues')
for o in out:
    print(f"  {o['id']:>8} | {o['name'][:48]:<48} | {o['city'][:24]:<24} | {o['rating'][:12]}")

#!/usr/bin/env python3
"""Tests for /r/ alias resolver — exact static, alias redirect, 404 behavior."""

import json, re, os, sys, subprocess, time

BASE = 'https://thaidata.uk'
ALIASES_FILE = '/tmp/thaidata-repo/data/r-aliases.json'
REPO = '/tmp/thaidata-repo'

# Load aliases for reference
with open(ALIASES_FILE) as f:
    ALIASES = json.load(f)['aliases']

# Load restaurants data for validation
with open(f'{REPO}/data/restaurants.json') as f:
    RESTAURANTS = json.load(f)['restaurants']

results = {'pass': 0, 'fail': 0, 'errors': []}

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')

def test(name, url, expected_status, expected_location=None, check_fsa=False):
    """Curl a URL and check status + optional redirect location."""
    try:
        # Use -L to NOT follow redirects, -o /dev/null -w to get status
        cmd = ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        status = int(r.stdout.strip())
        
        # For redirects, get the Location header
        location = None
        if status in (301, 302):
            loc_cmd = ['curl', '-sI', url]
            loc_r = subprocess.run(loc_cmd, capture_output=True, text=True, timeout=10)
            for line in loc_r.stdout.split('\n'):
                if line.lower().startswith('location:'):
                    location = line.split(':', 1)[1].strip()
                    break
        
        # Check FSA marker on 200 responses
        has_fsa = False
        if status == 200:
            fsa_cmd = ['curl', '-s', url]
            fsa_r = subprocess.run(fsa_cmd, capture_output=True, text=True, timeout=10)
            has_fsa = 'FSA' in fsa_r.stdout and 'Restaurant' in fsa_r.stdout
        
        status_ok = status == expected_status
        location_ok = True
        fsa_ok = True
        
        if expected_location:
            location_ok = location and expected_location in location
        
        if check_fsa:
            fsa_ok = has_fsa
        
        all_ok = status_ok and location_ok and fsa_ok
        
        if all_ok:
            results['pass'] += 1
            status_msg = ''
        else:
            results['fail'] += 1
            issues = []
            if not status_ok: issues.append(f'expected status {expected_status}, got {status}')
            if not location_ok: issues.append(f'expected location containing "{expected_location}", got "{location}"')
            if not fsa_ok: issues.append('page missing FSA/Restaurant markers')
            status_msg = f' — FAIL: {"; ".join(issues)}'
        
        print(f'  {name}: {"✓" if all_ok else "✗"}{status_msg}')
        print(f'    {url} → {status}' + (f' → {location}' if location else ''))
        
    except Exception as e:
        results['fail'] += 1
        print(f'  {name}: ✗ — ERROR: {e}')
        results['errors'].append(str(e))


print('=' * 60)
print('Test 1: Exact static route still 200 with FSA content')
print('=' * 60)
# Verify a known existing restaurant page returns 200 with FSA marker
test('Chaophraya Leeds (canonical)',
     f'{BASE}/r/leeds/chao-phraya-thai-restaurant/',
     200, check_fsa=True)
test('Giggling Squid Leeds (canonical)',
     f'{BASE}/r/leeds/giggling-squid/',
     200, check_fsa=True)

print()
print('=' * 60)
print('Test 2: Alias routes 301 to canonical URL')
print('=' * 60)
for alias in ALIASES:
    city = alias['city']
    slug = alias['slug']
    canonical = alias['canonical']
    expected_path = f'/r/{city}/{slugify(canonical)}/'
    
    test(f'Alias "{slug}" in {city} → "{canonical}"',
         f'{BASE}/r/{city}/{slug}/',
         301, expected_location=expected_path)

print()
print('=' * 60)
print('Test 3: Ambiguous / non-aliased routes 404')
print('=' * 60)
test('Short ambiguous term in Leeds',
     f'{BASE}/r/leeds/thai/',
     404)
test('Very short name (3 chars)',
     f'{BASE}/r/leeds/ab/',
     404)
test('Completely nonexistent in Leeds',
     f'{BASE}/r/leeds/pizza-express/',
     404)
test('No alias for partial first-word match',
     f'{BASE}/r/leeds/giggling/',
     404)

print()
print('=' * 60)
print('Test 4: Nonexistent city + restaurant 404')
print('=' * 60)
test('Nonexistent city + restaurant',
     f'{BASE}/r/london/pizza-express/',
     404)
test('Nonexistent city only',
     f'{BASE}/r/atlantis/',
     200)  # 2 segments = pass through, Cloudflare SPA fallback returns homepage

print()
print('=' * 60)
print('Test 5: Hub / city pages still work (pass through)')
print('=' * 60)
test('Root /r/ hub',
     f'{BASE}/r/',
     200)
test('Leeds city /r/ page',
     f'{BASE}/r/leeds/',
     200)

print()
print('=' * 60)
print(f'Results: {results["pass"]} passed, {results["fail"]} failed')
print('=' * 60)

if results['fail'] > 0:
    sys.exit(1)

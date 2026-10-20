#!/usr/bin/env python3
"""Quick CI consistency check — exits non-zero if data is inconsistent."""
import json, sys
from typing import Any

with open('data/restaurants.json') as f:
    r: dict[str, Any] = json.load(f)
with open('api/v1/cities.json') as f:
    c: dict[str, Any] = json.load(f)

errors: list[str] = []
pubs = sum(1 for rec in r['restaurants'] if rec.get('type') == 'pub')
core = len(r['restaurants']) - pubs
if r['total'] != core:
    errors.append(f'restaurants.json: metadata total={r["total"]} != non-pub records={core}')
if r.get('pubs', 0) != pubs:
    errors.append(f'restaurants.json: metadata pubs={r.get("pubs", 0)} != actual pubs={pubs}')
city_sum = sum(ci['total_thai_businesses'] for ci in c['cities'])
if city_sum != r['total']:
    errors.append(f'City totals ({city_sum}) != restaurants total ({r["total"]})')
# FHIS (Scotland) cities must not carry numeric averages, and their status
# counts must add up to the city total.
for ci in c['cities']:
    if ci.get('scheme') == 'FHIS':
        if ci.get('avg_hygiene_rating') is not None:
            errors.append(f'{ci["name"]}: FHIS city must not carry a numeric avg_hygiene_rating')
        fhis_sum = ci.get('fhis_pass', 0) + ci.get('fhis_improvement', 0) + ci.get('fhis_exempt', 0)
        if fhis_sum != ci['total_thai_businesses']:
            errors.append(f'{ci["name"]}: FHIS status counts ({fhis_sum}) != total ({ci["total_thai_businesses"]})')

if errors:
    for e in errors:
        print(f'ERROR: {e}')

# Self-hosted webfonts: every /assets/fonts/*.woff2 referenced by shipped HTML must
# exist on disk. A missing file is invisible in text/diff checks — the metric-matched
# fallback renders instead — so it has to be asserted here.
import glob, os, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
refs = set()
for path in glob.glob(os.path.join(REPO, '**', '*.html'), recursive=True):
    with open(path, encoding='utf-8', errors='ignore') as f:
        refs.update(re.findall(r'/assets/fonts/[A-Za-z0-9._-]+\.woff2', f.read()))
for ref in sorted(refs):
    if not os.path.isfile(os.path.join(REPO, ref.lstrip('/'))):
        errors.append(f'missing font asset referenced by HTML: {ref}')
if refs:
    print(f'Font references checked: {len(refs)}')

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
print('All JSON consistency checks passed')

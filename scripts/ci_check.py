#!/usr/bin/env python3
"""Quick CI consistency check — exits non-zero if data is inconsistent."""
import json, sys
from typing import Any

with open('data/restaurants.json') as f:
    r: dict[str, Any] = json.load(f)
with open('api/v1/cities.json') as f:
    c: dict[str, Any] = json.load(f)

errors: list[str] = []
if r['total'] != len(r['restaurants']):
    errors.append(f'restaurants.json: metadata total={r["total"]} != actual={len(r["restaurants"])}')
city_sum = sum(ci['total_thai_businesses'] for ci in c['cities'])
if city_sum != r['total']:
    errors.append(f'City totals ({city_sum}) != restaurants total ({r["total"]})')
if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
print('All JSON consistency checks passed')

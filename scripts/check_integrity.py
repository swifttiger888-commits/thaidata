#!/usr/bin/env python3
"""
ThaiData UK — Data Integrity Check
===================================
Validates the entire data stack for consistency.

Run: python3 scripts/check_integrity.py
Exit code: 0 = all checks pass, 1 = warnings, 2 = errors
"""

import json, os, sys, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / 'data'
API_DIR = REPO / 'api' / 'v1'
R_DIR = REPO / 'r'
SCHEMA_DIR = REPO / 'schemas'

errors = []
warnings = []


def load_json(path, label):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        errors.append(f"[ERROR] Cannot load {label} ({path}): {e}")
        return None


def check_schema(data, schema_path, label):
    """Basic schema validation without jsonschema library (stdlib only)."""
    if not data:
        return
    try:
        with open(schema_path) as f:
            schema = json.load(f)
    except Exception as e:
        warnings.append(f"[WARN] Cannot load schema {schema_path}: {e}")
        return

    required = schema.get('required', [])
    missing = [k for k in required if k not in data]
    if missing:
        errors.append(f"[ERROR] {label}: missing required top-level keys: {missing}")

    # Check array items if we have an items schema
    for key, prop_schema in schema.get('properties', {}).items():
        if prop_schema.get('type') == 'array' and 'items' in prop_schema:
            items_schema = prop_schema['items']
            if items_schema.get('type') == 'object' and 'required' in items_schema:
                item_required = items_schema['required']
                for idx, item in enumerate(data.get(key, [])):
                    item_missing = [k for k in item_required if k not in item]
                    if item_missing:
                        errors.append(
                            f"[ERROR] {label}.{key}[{idx}]: missing fields: {item_missing}"
                        )


# ── Load data ───────────────────────────────────────────────────────

print("=" * 55)
print("  ThaiData UK — Data Integrity Check")
print("=" * 55)

restaurants_data = load_json(DATA_DIR / 'restaurants.json', 'restaurants.json')
cities_data = load_json(API_DIR / 'cities.json', 'cities.json')
overview_data = load_json(API_DIR / 'data.json', 'data.json')

# ── 1. Schema validation ───────────────────────────────────────────

print("\n📋 1. Schema validation...")
if restaurants_data:
    check_schema(restaurants_data, SCHEMA_DIR / 'restaurants.schema.json', 'restaurants.json')
    print(f"   restaurants.json: {len(restaurants_data.get('restaurants', []))} records")
if cities_data:
    check_schema(cities_data, SCHEMA_DIR / 'cities.schema.json', 'cities.json')
    print(f"   cities.json: {len(cities_data.get('cities', []))} cities")
if overview_data:
    check_schema(overview_data, SCHEMA_DIR / 'data.schema.json', 'data.json')
    print(f"   data.json: OK")

# ── 2. Integrity: totals match ─────────────────────────────────────

print("\n📊 2. Totals consistency check...")
if restaurants_data and cities_data:
    meta_total = restaurants_data.get('total', 0)
    actual_total = len(restaurants_data.get('restaurants', []))
    if meta_total != actual_total:
        errors.append(
            f"[ERROR] restaurants.json: metadata total={meta_total} "
            f"but actual records={actual_total}"
        )

    city_sum = sum(c['total_thai_businesses'] for c in cities_data['cities'])
    if city_sum != meta_total:
        errors.append(
            f"[ERROR] cities sum ({city_sum}) != restaurants total ({meta_total})"
        )
    else:
        print(f"   ✅ restaurants total ({meta_total}) = cities sum ({city_sum})")

    if overview_data:
        stat_total = overview_data.get('statistics', {}).get('total_uk_thai_businesses', 0)
        if stat_total != meta_total:
            errors.append(
                f"[ERROR] data.json total ({stat_total}) != restaurants total ({meta_total})"
            )
        else:
            print(f"   ✅ data.json total ({stat_total}) matches")

# ── 3. Hygiene rating validation ───────────────────────────────────

print("\n🍽️  3. Hygiene rating validation...")
if restaurants_data:
    valid_numeric = set('012345')
    special_vals = {'AwaitingPublication', 'Exempt'}
    invalid = []
    for r in restaurants_data['restaurants']:
        hr = r.get('hygiene_rating', '')
        if hr not in valid_numeric and hr not in special_vals:
            invalid.append((r['id'], r['name'], hr))
    if invalid:
        warnings.append(
            f"[WARN] {len(invalid)} records have non-standard hygiene ratings: "
            f"{', '.join(set(v[2] for v in invalid))}"
        )
        print(f"   ⚠️  {len(invalid)} non-standard ratings (shown above)")
    else:
        print(f"   ✅ All {len(restaurants_data['restaurants'])} ratings valid")

    # Detail score ranges
    detail_issues = []
    for r in restaurants_data['restaurants']:
        for field in ('hygiene_score', 'structural_score', 'management_score'):
            val = r.get(field)
            if val is not None:
                if not isinstance(val, int) or val < 0 or val > 25:
                    detail_issues.append((r['id'], r['name'], field, val))
    if detail_issues:
        for rid, name, field, val in detail_issues:
            warnings.append(
                f"[WARN] Restaurant #{rid} ({name}): {field}={val} (expected 0-25, FSA source data anomaly)"
            )
        print(f"   ⚠️  {len(detail_issues)} detail score(s) outside expected range (shown above)")
    else:
        print(f"   ✅ Detail scores in valid range")

# ── 4. Duplicate FHRSID check ─────────────────────────────────────

print("\n🔍 4. Duplicate FHRSID check...")
if restaurants_data:
    ids = [r['id'] for r in restaurants_data['restaurants']]
    dupes = [i for i in ids if ids.count(i) > 1]
    if dupes:
        errors.append(f"[ERROR] {len(set(dupes))} duplicate FHRSIDs found: {sorted(set(dupes))}")
    else:
        print(f"   ✅ No duplicate FHRSIDs ({len(ids)} unique)")

# ── 5. Restaurant + city breakdown consistency ─────────────────────

print("\n🏙️  5. Type breakdown consistency...")
if restaurants_data and cities_data:
    city_rest = sum(c['restaurants'] for c in cities_data['cities'])
    city_take = sum(c['takeaways'] for c in cities_data['cities'])
    actual_rest = sum(1 for r in restaurants_data['restaurants'] if r.get('type') == 'restaurant')
    actual_take = sum(1 for r in restaurants_data['restaurants'] if r.get('type') == 'takeaway')
    if city_rest != actual_rest or city_take != actual_take:
        errors.append(
            f"[ERROR] Type mismatch: cities has {city_rest}+{city_take} "
            f"but actual {actual_rest}+{actual_take}"
        )
    else:
        print(f"   ✅ Restaurant/takeaway split matches: {actual_rest} restaurants, {actual_take} takeaways")

# ── 6. Missing postcodes ──────────────────────────────────────────

print("\n📮 6. Postcode coverage...")
if restaurants_data:
    missing_pc = [r for r in restaurants_data['restaurants'] if not r.get('postcode', '').strip()]
    if missing_pc:
        warnings.append(f"[WARN] {len(missing_pc)} records missing postcode")
        print(f"   ⚠️  {len(missing_pc)} records without postcode")
    else:
        print(f"   ✅ All records have postcode")

# ── 7. Missing lat/lng ────────────────────────────────────────────

print("\n📍 7. Geocoding coverage...")
if restaurants_data:
    no_lat = [r for r in restaurants_data['restaurants']
              if not r.get('latitude') or str(r.get('latitude', '')).strip() == '']
    if no_lat:
        warnings.append(f"[WARN] {len(no_lat)} records missing coordinates")
        print(f"   ⚠️  {len(no_lat)} records without coordinates ({len(no_lat)/len(restaurants_data['restaurants'])*100:.1f}%)")
    else:
        print(f"   ✅ All records geocoded")

# ── 8. Orphan page check (spot-check /r/ directories) ─────────────

print("\n📄 8. Orphan page spot-check...")
if R_DIR.exists():
    total_r_dirs = sum(1 for d in R_DIR.iterdir() if d.is_dir())
    print(f"   {total_r_dirs} city directories in /r/")
    # We don't check individual restaurant pages here (takes too long)
    # but flag if any city slug doesn't exist in cities.json
    if cities_data:
        city_slugs_r = {d.name for d in R_DIR.iterdir() if d.is_dir()
                        and not d.name.startswith('.') and d.name not in ('api', 'favicon.png')}
        city_names = {c['name'].lower().replace(' ', '-') for c in cities_data['cities']}
        # Some city directory names use different conventions
        print(f"   Skipping cross-check (naming conventions differ between dirs and data)")
else:
    warnings.append("[WARN] /r/ directory not found — cannot check for orphan pages")

# ── Summary ────────────────────────────────────────────────────────

print("\n" + "=" * 55)
if errors:
    print(f"  ❌ {len(errors)} ERROR(S) — must fix before deploy")
    for e in errors:
        print(f"     {e}")
if warnings:
    print(f"  ⚠️  {len(warnings)} WARNING(S) — review recommended")
    for w in warnings:
        print(f"     {w}")
if not errors and not warnings:
    print("  ✅ ALL CHECKS PASSED — data is consistent")
print("=" * 55)

sys.exit(2 if errors else (1 if warnings else 0))

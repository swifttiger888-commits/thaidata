#!/usr/bin/env python3
"""Quick CI consistency check — exits non-zero if data is inconsistent."""
import glob, json, os, re, sys
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

def _skippable(path):
    """Test fixtures and vendored dirs are not deployable site pages."""
    rel = os.path.relpath(path, REPO).replace(os.sep, '/')
    return rel.startswith(('tests/', '.venv/', 'node_modules/'))

refs = set()
for path in glob.glob(os.path.join(REPO, '**', '*.html'), recursive=True):
    if _skippable(path):
        continue
    with open(path, encoding='utf-8', errors='ignore') as f:
        refs.update(re.findall(r'/assets/fonts/[A-Za-z0-9._-]+\.woff2', f.read()))
for ref in sorted(refs):
    if not os.path.isfile(os.path.join(REPO, ref.lstrip('/'))):
        errors.append(f'missing font asset referenced by HTML: {ref}')
if refs:
    print(f'Font references checked: {len(refs)}')

# Font Awesome is gone: icons are inline <symbol> sprites. Two failure modes are
# invisible — a leftover <i class="fa..."> renders nothing (the stylesheet is gone),
# and a <use href="#id"> with no matching symbol renders nothing either. Both are
# asserted here, plus the sprite source and its mapping.
import json as _json
_icon_pages = 0
for path in glob.glob(os.path.join(REPO, '**', '*.html'), recursive=True):
    if _skippable(path):
        continue
    with open(path, encoding='utf-8', errors='ignore') as f:
        html = f.read()
    rel = os.path.relpath(path, REPO)
    if 'font-awesome' in html.lower():
        errors.append(f'Font Awesome stylesheet still linked: {rel}')
    if re.search(r'<i class="[^"]*\bfa-', html):
        errors.append(f'Font Awesome <i> icon markup left in: {rel}')
    uses = {u for u in re.findall(r'<use href="#([^"]+)"', html) if '$' not in u}
    # a ${...} id is a JS template literal, filled in at runtime
    if uses:
        _icon_pages += 1
        missing = uses - set(re.findall(r'<symbol id="([^"]+)"', html))
        if missing:
            errors.append(f'{rel}: <use> without an inline symbol: {sorted(missing)[:3]}')
    # An inline <svg> with no sizing rule falls back to 300x150 px, so the icon
    # dwarfs the text. Generated shells that omit </head> used to skip the rule.
    if 'class="ic"' in html and '.ic{display:inline-block;width:1em' not in html:
        errors.append(f'{rel}: <svg class="ic"> without the .ic sizing rule')
for needed in ('assets/icons.svg', 'data/icon_map.json'):
    if not os.path.isfile(os.path.join(REPO, needed)):
        errors.append(f'missing icon asset: {needed}')
else:
    if os.path.isfile(os.path.join(REPO, 'assets', 'icons.svg')):
        with open(os.path.join(REPO, 'assets', 'icons.svg'), encoding='utf-8') as f:
            _sprite = f.read()
        _map = _json.load(open(os.path.join(REPO, 'data', 'icon_map.json'), encoding='utf-8'))
        _ids = {'i-%s--%s' % (v['style'], v['name']) for v in _map.values()}
        _absent = _ids - set(re.findall(r'<symbol id="([^"]+)"', _sprite))
        if _absent:
            errors.append(f'icon_map entries with no symbol in assets/icons.svg: {sorted(_absent)[:5]}')
        print(f'Icon pages checked: {_icon_pages} ({len(_ids)} mapped icons)')


if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
print('All JSON consistency checks passed')
